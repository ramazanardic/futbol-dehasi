"""21 Kasım kupon post-mortem kuralları: aile beyaz listesi, büzülmüş kalibrasyon, banko kupon kurucu."""

from __future__ import annotations

import math

import pytest

from quantfoot.coupons.coupon_rules import (
    BANNED_FAMILIES,
    MIN_CALIBRATED_P,
    Calibration,
    build_rules_coupon,
    calibrate_p,
    canonical_name,
    classify_family,
    default_calibration,
    family_allowed,
    family_shrunk_residual,
    filter_legs,
    is_draw_leg,
    leg_decision,
    shrink_residual,
)


def test_canonical_name_and_family_taxonomy():
    assert canonical_name("2,5 Alt") == "2.5 Alt"
    assert canonical_name("1") == "MS 1"
    assert canonical_name("X") == "MS 0"
    assert classify_family("2Y KG Yok") == "2Y karşılıklı gol"
    assert classify_family("MS 1") == "Maç sonucu"
    assert classify_family("İY 1.5 Alt") == "İlk yarı"
    assert classify_family("Ev 1.5 Üst") == "Ev sahibi golleri"
    assert classify_family("Dep İY 0.5 Alt") == "Deplasman golleri"
    assert classify_family("KG Var") == "Karşılıklı gol"
    assert classify_family("ÇŞ 1X") == "Çifte şans"
    assert classify_family("DEĞİL(Ev İki Yarıda Gol)") == "Yarı özel"
    assert classify_family("2.5 Üst") == "Alt/Üst"
    assert classify_family("İlk Gol Ev") == "İlk gol"


def test_draw_legs_detected_and_complements_are_not_draws():
    for name in ("MS 0", "MS X", "X", "İY X", "İY 0", "2Y 0", "İY/MS 1/X", "İY/MS X/X",
                 "İY/MS 0/1", "Skor 0-0", "MS 0 (beraberlik)"):
        assert is_draw_leg(name), name
    for name in ("MS 1", "MS 2", "İY 1", "ÇŞ 1X", "DEĞİL(MS 0)", "2Y KG Yok"):
        assert not is_draw_leg(name), name


def test_shrink_residual_and_positive_clip_in_calibrate():
    assert shrink_residual(-0.04, 90, 150) == pytest.approx(-0.04 * 90 / 240)
    assert shrink_residual(0.10, 0, 150) == 0.0
    # pozitif aile residuali P'ye eklenmez (Yarı özel / 2Y KG bugün artıdaydı)
    p = calibrate_p(0.59, "DEĞİL(Ev İki Yarıda Gol)")
    assert p == pytest.approx(0.59)  # 0.00–0.60 bandı da artı, kırpılır


def test_default_allowlist_is_data_driven():
    cal = default_calibration()
    assert family_allowed("İlk yarı", cal)
    assert family_allowed("Yarı özel", cal)
    assert family_allowed("Maç sonucu", cal)
    assert family_allowed("2Y karşılıklı gol", cal)
    assert family_allowed("Alt/Üst", cal)
    # sert yasak
    for fam in BANNED_FAMILIES:
        assert not family_allowed(fam, cal)
    # büzülmüş residual / küçük n / ana tercih sapması
    assert not family_allowed("Çifte şans", cal)      # ana tercihte −10 puan
    assert not family_allowed("Handikap", cal)        # tüm seçim residuali eşiğin altında
    assert not family_allowed("İY/MS", cal)           # n=4 < 40
    assert not family_allowed("İkinci yarı", cal)     # n=26 < 40
    assert not family_allowed("Tek/Çift", cal)
    # Handikap residuali büzülünce hâlâ −1.2 puan (eşik −1.0)
    assert family_shrunk_residual("Handikap", cal) < cal.max_negative_residual


def test_leg_decision_rejects_banned_draw_low_odds_and_low_calibrated_p():
    def d(**kw):
        base = {"code": 1, "match": "Ev - Dep", "odds": 1.35, "p": 0.80}
        base.update(kw)
        return leg_decision(base)

    assert d(name="MS 0").ok is False and any("beraberlik" in r for r in d(name="MS 0").reasons)
    assert d(name="KG Var").ok is False and any("yasak" in r for r in d(name="KG Var").reasons)
    assert d(name="Ev 1.5 Alt").ok is False
    assert d(name="Dep İY 0.5 Alt").ok is False
    assert d(name="İlk Gol Ev").ok is False
    assert d(name="ÇŞ 1X").ok is False
    assert d(name="2Y KG Var").ok is False
    assert d(name="2.5 Üst & KG Yok").ok is False
    assert d(name="MS 1", odds=1.15).ok is False
    assert d(name="MS 1", odds=1.95).ok is False  # banko tavanı 1.80
    # %70 ham P, 0.70–0.75 bandı ~1.6 puan kırpılır → tabanın altında
    low = d(name="MS 1", p=0.70)
    assert low.ok is False and low.p_cal is not None and low.p_cal < MIN_CALIBRATED_P
    assert any("düzeltilmiş P" in r for r in low.reasons)


def test_leg_decision_accepts_good_families_at_high_calibrated_p():
    ok_legs = [
        {"code": 1, "match": "A - B", "name": "2Y KG Yok", "odds": 1.35, "p": 0.72},
        {"code": 2, "match": "C - D", "name": "İY 1.5 Alt", "odds": 1.40, "p": 0.75},
        {"code": 3, "match": "E - F", "name": "MS 1", "odds": 1.28, "p": 0.73},
        {"code": 4, "match": "G - H", "name": "DEĞİL(Ev İki Yarıda Gol)", "odds": 1.45, "p": 0.75},
        {"code": 5, "match": "I - J", "name": "3.5 Alt", "odds": 1.32, "p": 0.75},
    ]
    for leg in ok_legs:
        dec = leg_decision(leg)
        assert dec.ok, (leg["name"], dec.reasons, dec.p_cal)
        assert dec.p_cal >= MIN_CALIBRATED_P
    # 2.5 Üst bugün −11 puan; isim kalıbı aile residualinin yerine geçer, yüksek P gerek
    weak_ou = leg_decision({"code": 9, "match": "U - V", "name": "2.5 Üst", "odds": 1.40, "p": 0.70})
    assert weak_ou.ok is False and weak_ou.p_cal < 0.70


def test_calibrate_p_uses_name_pattern_instead_of_family_for_25_over():
    # 2.5 Üst residuali aile genelinden (~−1 puan) çok daha kötü; büzülmüş isim düzeltmesi uygulanır
    p_over = calibrate_p(0.70, "2.5 Üst")
    p_under = calibrate_p(0.70, "3.5 Alt")
    assert p_over < p_under
    assert p_over < 0.70  # negatif isim residuali
    # 3.5 Alt artı residuali kırpılır; yalnız bant (0.70–0.75) düşer
    assert p_under == pytest.approx(0.70 + shrink_residual(-0.0428, 90, 150))


def test_filter_and_one_leg_per_match_highest_calibrated_p():
    cands = [
        {"code": 1, "match": "A - B", "name": "MS 1", "odds": 1.30, "p": 0.73},
        {"code": 1, "match": "A - B", "name": "İY 1.5 Alt", "odds": 1.35, "p": 0.78},
        {"code": 2, "match": "C - D", "name": "KG Var", "odds": 1.40, "p": 0.80},
        {"code": 3, "match": "E - F", "name": "2Y KG Yok", "odds": 1.33, "p": 0.74},
    ]
    kept = filter_legs(cands)
    assert {x["name"] for x in kept} == {"MS 1", "İY 1.5 Alt", "2Y KG Yok"}
    coupon = build_rules_coupon(cands, min_legs=2, prefer_n=2, max_legs=2)
    assert not coupon.short
    assert [L.match_id for L in coupon.legs] == ["1", "3"]
    assert coupon.legs[0].name == "İY 1.5 Alt"  # aynı maçtan daha yüksek p_cal
    assert coupon.total_odds == pytest.approx(1.35 * 1.33)
    assert coupon.p_win == pytest.approx(math.prod(L.p_cal for L in coupon.legs))


def test_build_rules_coupon_prefers_five_legs_and_reports_shortfall_honestly():
    def leg(i, p=0.76, name="İY 1.5 Alt"):
        return {"code": i, "match": f"Ev{i} - Dep{i}", "name": name, "odds": 1.30, "p": p}

    five = build_rules_coupon([leg(i) for i in range(5)])
    assert len(five.legs) == 5 and not five.short
    assert five.p_win == pytest.approx(math.prod(L.p_cal for L in five.legs))
    # 6 aday olsa bile varsayılan 5 bacak (maksimum 5 maç kuralı, 6. bacak ürün P'yi düşürür)
    six_pool = build_rules_coupon([leg(i) for i in range(6)])
    assert len(six_pool.legs) == 5
    # açıkça max_legs=6 ve prefer_n=6 istendiğinde 6
    six = build_rules_coupon([leg(i) for i in range(6)], prefer_n=6, max_legs=6)
    assert len(six.legs) == 6 and not six.short
    # yetersiz havuz: kısa kupon, dürüst çarpım
    short = build_rules_coupon([leg(i) for i in range(3)])
    assert short.short and len(short.legs) == 3
    assert any("yalnızca 3 bacak" in n for n in short.notes)
    assert short.p_win == pytest.approx(math.prod(L.p_cal for L in short.legs))
    empty = build_rules_coupon([leg(1, name="MS 0"), leg(2, name="KG Var")])
    assert empty.short and empty.legs == () and empty.p_win == 0.0


def test_injected_calibration_drives_allowlist():
    cal = Calibration(
        prior_n=10,
        min_family_n=5,
        max_negative_residual=-0.01,
        headline_min_n=30,
        families={
            "Maç sonucu": {"n": 20, "residual": 0.0, "headline": {"n": 0}},
            "Alt/Üst": {"n": 20, "residual": -0.20, "headline": {"n": 0}},
        },
        bands=({"lo": 0.0, "hi": 1.01, "n": 1, "residual": 0.0},),
    )
    assert family_allowed("Maç sonucu", cal)
    assert not family_allowed("Alt/Üst", cal)  # büzülmüş residual = -0.20*20/30 ≈ -0.133
    ok = {"code": 1, "match": "A - B", "name": "MS 1", "odds": 1.30, "p": 0.80}
    bad = {"code": 2, "match": "C - D", "name": "2.5 Alt", "odds": 1.30, "p": 0.80}
    assert leg_decision(ok, cal).ok and not leg_decision(bad, cal).ok


def test_nesine_kupon_banko_path_applies_rules_without_breaking_legacy_filter():
    import importlib.util
    from pathlib import Path

    from quantfoot.strategy import kupon_modu as KM

    p = Path(__file__).resolve().parents[1] / "scripts" / "nesine_kupon.py"
    spec = importlib.util.spec_from_file_location("nesine_kupon_rules_t", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # eski süzgeç: p=0.70 2.5 Alt, oran 1.30 banko'da kalır (0.65 tabanı)
    legacy = {"code": 1, "match": "A - B", "name": "2.5 Alt", "odds": 1.30, "p": 0.70, "tier": "keskin"}
    out = mod.filter_pools_for_mode([[legacy]], KM.policy("banko"))
    assert out == [[legacy]]
    # yeni kural: aynı bacak düzeltilmiş P < %70 → elenir; yüksek P'li 2Y KG Yok kalır
    strong = {"code": 2, "match": "C - D", "name": "2Y KG Yok", "odds": 1.33, "p": 0.74, "tier": "keskin"}
    ruled = mod.apply_coupon_rules_to_pools([[legacy, strong]], "banko")
    assert len(ruled) == len(ruled[0]) == 1
    assert ruled[0][0]["code"] == strong["code"]
    assert ruled[0][0]["p_before_rules"] == strong["p"]
    # risk moduna uygulanmaz
    assert mod.apply_coupon_rules_to_pools([[legacy]], "risk") == [[legacy]]
