"""21 Kas akşam denetimi dersleri: türetilmiş P büzmesi, "diğer" lig ek büzmesi, zayıf aileler (ev golleri, çifte şans)."""

import pytest

from quantfoot import settings as S
from quantfoot.strategy import banko_guard as bg
from quantfoot.strategy import kupon_modu as KM


def test_selection_family_detects_weak_families_only():
    for n in ("Ev 1.5 Üst", "Ev 0,5 Üst", "Ev İY 0.5 Alt", "Ev 2.5 Alt"):
        assert bg.selection_family(n) == "ev_golleri"
    for n in ("ÇŞ 1X", "ÇŞ X2", "Çifte Şans: 1-X"):
        assert bg.selection_family(n) == "cifte_sans"
    for n in ("Dep 1.5 Alt", "2.5 Üst", "MS 1", "İY ÇŞ 1X", "KG Var", "Ev En Az Bir Yarıyı Kazanır", ""):
        assert bg.selection_family(n) is None


def test_league_tier_classification():
    assert bg.league_tier("İngiltere Premier Lig") == "1"
    assert bg.league_tier("İtalya Serie B") == "2"
    assert bg.league_tier("İspanya 3. Federasyon") == "3"
    assert bg.league_tier("Almanya U19 Bundesliga") == "3"
    assert bg.league_tier("Kuzey Makedonya 1. Lig") == "other"
    assert bg.league_tier(None) is None and bg.league_tier("") is None


def test_shrink_toward_half_never_raises_low_p():
    assert bg.shrink_toward_half(0.70, 0.10) == pytest.approx(0.68)
    assert bg.shrink_toward_half(0.45, 0.50) == 0.45
    assert bg.shrink_toward_half(0.80, 0.0) == 0.80


def test_effective_prob_direct_vs_derived_vs_other_tier():
    direct = bg.BankoLeg(1, "a 2.5 Alt", 1.40, 0.70, direct=True, league="İngiltere Premier Lig")
    derived = bg.BankoLeg(2, "b 2.5 Alt", 1.40, 0.70, direct=False, league="İngiltere Premier Lig")
    unknown = bg.BankoLeg(3, "c 2.5 Alt", 1.40, 0.70)
    other = bg.BankoLeg(4, "d 2.5 Alt", 1.40, 0.70, direct=False, league="Kuzey Makedonya 1. Lig")
    other_direct = bg.BankoLeg(5, "e 2.5 Alt", 1.40, 0.70, direct=True, league="Kuzey Makedonya 1. Lig")
    assert bg.effective_prob(direct) == pytest.approx(0.70)                       # SHRINK_DIRECT = 0
    assert bg.effective_prob(derived) == pytest.approx(0.5 + 0.2 * (1 - S.SHRINK_DERIVED))
    assert bg.effective_prob(unknown) == pytest.approx(bg.effective_prob(derived))  # bilinmeyen = temkinli
    k = 1 - (1 - S.SHRINK_DERIVED) * (1 - S.SHRINK_OTHER_TIER_EXTRA)
    assert bg.effective_prob(other) == pytest.approx(0.5 + 0.2 * (1 - k))
    assert bg.effective_prob(other) < bg.effective_prob(derived)
    assert bg.effective_prob(direct) > bg.effective_prob(other_direct) > bg.effective_prob(other)
    # yapılandırılabilir: büzme kapatılınca ham P
    off = bg.ShrinkConfig(derived=0.0, direct=0.0, other_tier_extra=0.0)
    assert bg.effective_prob(other, off) == pytest.approx(0.70)


def test_live_leg_keeps_market_cap_not_shrink():
    live = bg.BankoLeg(9, "canlı MS 2", 1.30, 0.81, live=True, p_market=0.70, direct=False)
    assert bg.effective_prob(live) == pytest.approx(0.75)


def test_banko_min_prob_applies_after_shrink():
    # ham %66 türetilmiş → %64,4 < %65 → banko reddi; doğrudan fiyatlıysa geçer
    derived = bg.BankoLeg(1, "x 2.5 Alt", 1.35, 0.66, direct=False)
    direct = bg.BankoLeg(1, "x 2.5 Alt", 1.35, 0.66, direct=True)
    err, _ = bg.check_leg(derived)
    assert any("büzülmüş" in e and "< %65" in e for e in err)
    assert bg.check_leg(direct)[0] == []


def test_coupon_p_win_uses_shrunk_probabilities():
    legs = [bg.BankoLeg(i, f"l{i} 2.5 Alt", 1.30, 0.75, direct=False) for i in range(5)]
    r = bg.check_coupon(legs)
    assert r.p_win == pytest.approx((0.5 + 0.25 * (1 - S.SHRINK_DERIVED)) ** 5)


def test_weak_family_requires_direct_and_higher_p_in_banko():
    der = bg.BankoLeg(1, "A - B Ev 1.5 Üst", 1.30, 0.80, direct=False)
    err, _ = bg.check_leg(der)
    assert any("ev_golleri" in e for e in err)
    dc_low = bg.BankoLeg(2, "A - B ÇŞ 1X", 1.30, 0.68, direct=True)        # %68 < %70 (65 + 5)
    assert any("< %70" in e for e in bg.check_leg(dc_low)[0])
    dc_ok = bg.BankoLeg(3, "A - B ÇŞ 1X", 1.25, 0.74, direct=True)
    assert bg.check_leg(dc_ok)[0] == []
    # aile kuralı kapatılabilir
    cfg = bg.GuardConfig(weak_families=())
    assert bg.check_leg(der, cfg)[0] == []


def test_kupon_modu_to_leg_carries_direct_league_family_and_risk_mode_skips_family_rule():
    d = {"code": 7, "match": "A - B", "name": "Ev 1.5 Üst", "odds": 1.50, "p": 0.72, "tier": "keskin",
         "direct": False, "league": "Kuzey Makedonya 1. Lig"}
    leg = KM.to_leg(d)
    assert leg.direct is False and leg.family == "ev_golleri" and leg.league == "Kuzey Makedonya 1. Lig"
    assert not KM.leg_mode_ok(d, "banko")
    assert KM.leg_mode_ok(d, "risk")                         # risk: aile kuralı yok, büzülmüş P ≥ %45
    assert KM.leg_effective_prob(d) < 0.72
    ok = {"code": 8, "match": "C - D", "name": "2.5 Alt", "odds": 1.40, "p": 0.75, "tier": "keskin", "direct": True,
          "league": "İngiltere Premier Lig"}
    assert KM.leg_mode_ok(ok, "banko") and KM.leg_effective_prob(ok) == pytest.approx(0.75)


def test_nesine_pool_filter_drops_legs_failing_after_shrink():
    import importlib.util
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "nesine_kupon.py"
    spec = importlib.util.spec_from_file_location("nesine_kupon_t", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    keep = {"code": 1, "match": "A - B", "name": "2.5 Alt", "odds": 1.40, "p": 0.74, "tier": "keskin", "direct": True}
    drop = {"code": 2, "match": "C - D", "name": "2.5 Alt", "odds": 1.40, "p": 0.66, "tier": "keskin", "direct": False}
    weak = {"code": 3, "match": "E - F", "name": "ÇŞ 1X", "odds": 1.30, "p": 0.80, "tier": "keskin", "direct": False}
    out = mod.filter_pools_for_mode([[keep, drop], [weak]], KM.policy("banko"))
    assert out == [[keep]]
