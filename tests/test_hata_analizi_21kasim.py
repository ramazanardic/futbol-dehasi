"""21 Kas gece hata analizi: arşivle doğrulanan kuyruk kaymaları, sınanmamış pazar büzmesi, beraberlik riski."""

import math

import pytest

from quantfoot import settings as S
from quantfoot.markets import market_reliability as MR
from quantfoot.strategy import banko_guard as bg
from quantfoot.strategy import kupon_modu as KM


def test_tail_file_has_only_validated_small_shifts():
    cal = MR.load_tail_calibration()
    tail = cal["tail"]
    assert tail, "kuyruk dosyası boş"
    for name, t in tail.items():
        assert abs(t["delta"]) <= 0.10, name               # yalnız küçük düzeltmeler
        assert t["ci"][1] < 0, name                          # test LL farkının GA üst ucu < 0
        assert t["n_test"] >= 300
    assert "draw_adjust" in cal and "reliability" in cal


def test_normalize_name_variants():
    assert MR.normalize_name("Ev İY 0,5 Üst") == "Ev İY 0.5 Üst"
    assert MR.normalize_name("Çifte Şans: 1-2") == "ÇŞ 12"
    assert MR.normalize_name("1. Yarı Çifte Şans: 1-X") == "İY ÇŞ 1X"


def test_tail_adjust_only_inside_band_and_listed():
    cal = {"tail": {"ÇŞ 12": {"delta": -0.10, "lo": 0.55, "hi": 0.90}}}
    assert MR.tail_adjust("ÇŞ 12", 0.75, cal) < 0.75
    assert MR.tail_adjust("ÇŞ 12", 0.50, cal) == 0.50            # bant dışı
    assert MR.tail_adjust("2.5 Alt", 0.75, cal) == 0.75          # listede yok


def test_tail_adjust_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(S, "TAIL_CALIBRATION_ON", False)
    assert MR.tail_adjust("ÇŞ 12", 0.75, {"tail": {"ÇŞ 12": {"delta": -0.5}}}) == 0.75


def test_archive_tested_lookup():
    cal = {"reliability": {"2.5 Üst": {}, "KG Var": {}, "Ev Her İki Yarıyı Kazanır": {}}}
    assert MR.is_archive_tested("2.5 Alt", cal) is True
    assert MR.is_archive_tested("KG Yok", cal) is True
    assert MR.is_archive_tested("DEĞİL(Ev Her İki Yarıyı Kazanır)", cal) is True
    assert MR.is_archive_tested("İlk Gol Ev", cal) is False
    assert MR.is_archive_tested("", cal) is None
    assert MR.is_archive_tested("İlk Gol Ev", {}) is None       # dosya yoksa bilinmiyor → büzme yok


def test_untested_derived_market_gets_extra_shrink_but_direct_does_not():
    base = bg.ShrinkConfig(untested_extra=0.0)
    d_untested = bg.BankoLeg(1, "x İlk Gol Ev", 1.40, 0.70, direct=False, name="İlk Gol Ev")
    assert bg.effective_prob(d_untested) < bg.effective_prob(d_untested, base)
    direct = bg.BankoLeg(2, "x İlk Gol Ev", 1.40, 0.70, direct=True, name="İlk Gol Ev")
    assert bg.effective_prob(direct) == pytest.approx(0.70)
    tested = bg.BankoLeg(3, "x 2.5 Alt", 1.40, 0.70, direct=False, name="2.5 Alt")
    assert bg.effective_prob(tested) == pytest.approx(bg.effective_prob(tested, base))


def test_draw_risk_low_total_zone_raises_risk():
    hi_total = MR.draw_risk(0.28, 0.55)
    lo_total = MR.draw_risk(0.28, 0.40)
    assert lo_total > hi_total
    assert abs(hi_total - 0.28) < 0.01                 # bölge dışında piyasa P'sine çok yakın
    assert MR.draw_risk(None, 0.4) is None


def test_ms_prob_after_draw_risk_never_increases():
    assert MR.ms_prob_after_draw_risk(0.66, 0.24, 0.40) < 0.66
    assert MR.ms_prob_after_draw_risk(0.66, 0.24, 0.60) <= 0.66
    assert MR.ms_prob_after_draw_risk(0.66, None, None) == 0.66


def test_banko_rejects_ms_leg_with_high_draw_risk_and_warns_medium():
    high = bg.BankoLeg(1, "a MS 1", 1.30, 0.80, direct=True, name="MS 1", p_draw=0.27, p_over25=0.38)
    err, _ = bg.check_leg(high)
    assert any("beraberlik riski" in e for e in err)
    mid = bg.BankoLeg(2, "b MS 1", 1.30, 0.80, direct=True, name="MS 1", p_draw=0.245, p_over25=0.55)
    err, warn = bg.check_leg(mid)
    assert not any("beraberlik riski" in e for e in err)
    assert any("beraberlik riski" in w for w in warn)
    low = bg.BankoLeg(3, "c MS 1", 1.30, 0.80, direct=True, name="MS 1", p_draw=0.15, p_over25=0.60)
    err, warn = bg.check_leg(low)
    assert not any("beraberlik" in x for x in err + warn)


def test_risk_mode_draw_pick_filter():
    pol = KM.policy("risk")
    bad = bg.BankoLeg(1, "Sampdoria MS 0", 2.91, 0.30, direct=True, name="MS 0", p_draw=0.303, p_over25=0.459)
    err, _ = bg.check_leg(bad, pol.guard)
    assert any("beraberlik seçimi süzgeci" in e for e in err)
    good_ok, why = MR.draw_pick_ok(0.33, 0.38, 3.30)
    assert good_ok, why
    assert not MR.draw_pick_ok(0.33, 0.38, 2.80)[0]               # Nesine payı: EV negatif
    assert not MR.draw_pick_ok(None, 0.38, 3.30)[0]
    # banko modu MS 0 süzgecini uygulamaz (zaten P < %65 ile reddedilir)
    assert KM.policy("banko").guard.draw_pick_filter is False


def test_to_leg_carries_name_and_draw_inputs():
    leg = KM.to_leg({"code": 5, "match": "A - B", "name": "MS 1", "odds": 1.4, "p": 0.7, "fair_1x2": [0.7, 0.2, 0.1],
                     "p_over25": 0.5, "direct": True})
    assert leg.name == "MS 1" and leg.p_draw == pytest.approx(0.2) and leg.p_over25 == pytest.approx(0.5)
    leg2 = KM.to_leg({"code": 6, "name": "2.5 Alt", "odds": 1.4, "p": 0.7, "p_draw": 0.3})
    assert leg2.p_draw == pytest.approx(0.3) and leg2.p_over25 is None


def test_today_draw_picks_all_filtered():
    """21 Kas'ın 7 beraberlik seçiminden fiyatı olan 6'sı (2 tuttu) yeni süzgeçten geçemezdi (hepsi Nesine'de −EV)."""
    picks = [(0.2494, 0.6252, 3.31), (0.3211, 0.5053, 2.75), (0.2794, 0.5168, 3.10), (0.3123, 0.4318, 2.79),
             (0.2446, 0.6042, 3.57), (0.3029, 0.4591, 2.91)]
    assert not any(MR.draw_pick_ok(p0, po, o)[0] for p0, po, o in picks)


def test_settings_present():
    for k in ("TAIL_CALIBRATION_ON", "UNTESTED_MARKET_SHRINK", "BANKO_DRAW_RISK_MAX", "BANKO_DRAW_RISK_WARN",
              "DRAW_ZONE_MAX_OVER25", "DRAW_PICK_MIN_P", "DRAW_PICK_MIN_EV"):
        assert hasattr(S, k)
    assert S.BANKO_DRAW_RISK_WARN < S.BANKO_DRAW_RISK_MAX
    assert not math.isnan(S.UNTESTED_MARKET_SHRINK)


# ---------------------------------------------------------------- yüksek oranlı pazarlar (t100u)
def test_high_odds_market_detection():
    for n in ("İY/MS 1/2", "İY/MS 0/0", "İY 1", "2Y 0", "İki Yarıda KG Var", "Skor 2-1", "İY Skor 1-0"):
        assert MR.is_high_odds_market(n), n
    for n in ("MS 1", "2.5 Üst", "İY 0.5 Üst", "KG Var"):
        assert not MR.is_high_odds_market(n), n


def test_high_odds_requires_model_sharp_agreement():
    ok, why, _ = MR.high_odds_pick_ok("İY/MS 1/1", 0.40, 3.0, p_sharp=0.30)
    assert not ok and "uyuşmuyor" in why
    ok, why, p = MR.high_odds_pick_ok("İY/MS 1/1", 0.31, 3.6, p_sharp=0.30)
    assert ok and p == pytest.approx(0.30)                      # EV ikisinin küçüğüyle
    ok, _, _ = MR.high_odds_pick_ok("İY/MS 1/1", 0.31, 3.3, p_sharp=0.30)
    assert not ok                                               # EV −1 % < taban


def test_high_odds_without_sharp_needs_archive_and_haircut():
    ok, why, p = MR.high_odds_pick_ok("İY/MS 1/2", 0.05, 30.0)
    assert not ok and "piyango" in why
    ok, why, p = MR.high_odds_pick_ok("İY 1", 0.40, 3.2)
    assert ok and p == pytest.approx(0.36)
    ok, why, _ = MR.high_odds_pick_ok("İY 1", 0.40, 2.8)
    assert not ok


def test_select_high_odds_orders_by_ev():
    c = [{"name": "İY 1", "p": 0.40, "odds": 3.2}, {"name": "İY 2", "p": 0.40, "odds": 3.5},
         {"name": "MS 1", "p": 0.6, "odds": 2.0}]
    out = MR.select_high_odds(c)
    assert [x["name"] for x in out] == ["İY 2", "İY 1"]


def test_yuksek_oran_mode_guard():
    pol = KM.policy("yuksek_oran")
    assert "yuksek_oran" in KM.MODES and pol.max_legs == S.HIGH_ODDS_MAX_LEGS
    good = {"code": 1, "match": "A - B", "name": "İY/MS 1/1", "odds": 3.6, "p": 0.30, "direct": True}
    bad = {"code": 2, "match": "C - D", "name": "MS 1", "odds": 1.9, "p": 0.6, "direct": True}
    assert KM.leg_mode_ok(good, "yuksek_oran")
    assert not KM.leg_mode_ok(bad, "yuksek_oran")
    res = KM.guard_legs([good], "yuksek_oran")
    assert res.ok, res.errors


def test_htft_archive_results_written():
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "reports" / "research" / "hata_analizi_21kasim.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    y = d["yuksek_oranli"]
    for k in [f"İY/MS {a}/{b}" for a in "102" for b in "102"]:
        assert abs(y[k]["fark"]) < 0.01, k                     # arşivde kalibre
    assert d["beraberlik_tablolari"]["favori_oran"]
