"""21 Kasım denetimi düzeltmeleri: canlı market durumu, kırmızı kart, piyasaya büzme, banko koruması."""

import pytest

from quantfoot.data import live_scan as ls
from quantfoot.strategy import banko_guard as bg


def _event(ms_status, mtid=53, odds=(2.5, 3.1, 2.8)):
    return {"sg": {"EA": [{"C": 1, "HN": "A", "AN": "B", "TYPE": 1, "ESD": 0,
                           "MA": [{"MTID": mtid, "MS": ms_status,
                                   "OCA": [{"N": i + 1, "O": o} for i, o in enumerate(odds)]}]}]}}


@pytest.mark.parametrize("status,expected", [(1, True), (0, False), (-2, False), ("x", False)])
def test_market_status_filters_closed_and_suspended(status, expected):
    mk = ls.parse_nesine_live(_event(status))[0]["markets"]
    assert ("MS 1" in mk) is expected


def test_market_status_missing_treated_as_open():
    ev = _event(1)
    del ev["sg"]["EA"][0]["MA"][0]["MS"]
    assert ls.parse_nesine_live(ev)[0]["markets"]["MS 2"] == 2.8


def test_red_cards_take_max_of_status_and_stats():
    assert ls.red_cards([0, 0], {"home": {"red": 1.0}, "away": {"red": None}}) == [1, 0]
    assert ls.red_cards([0, 2], {"home": {}, "away": {"red": 1}}) == [0, 2]
    assert ls.red_cards(None, None) == [0, 0]


def test_live_from_fotmob_uses_stats_red_when_status_lags():
    details = {"header": {"status": {"numberOfHomeRedCards": 0, "numberOfAwayRedCards": 0},
                          "teams": [{"score": 0}, {"score": 1}]},
               "content": {"stats": {"Periods": {"All": {"stats": [{"stats": [
                   {"key": "red_cards", "stats": [1, 0]}]}]}}}}}
    lv = ls.live_from_fotmob({"id": 9, "home": "Millwall", "away": "QPR", "minute": 50}, details)
    assert (lv["home_red"], lv["away_red"]) == (1, 0)


def test_market_fair_probs_devig_groups():
    p = ls.market_fair_probs({"MS 1": 1.26, "MS X": 3.08, "MS 2": 6.06, "2.5 Alt": 1.32, "2.5 Üst": 1.9})
    assert sum(p[k] for k in ("MS 1", "MS X", "MS 2")) == pytest.approx(1.0)
    assert p["2.5 Alt"] + p["2.5 Üst"] == pytest.approx(1.0)
    assert p["MS 1"] < 1 / 1.26


def test_blend_with_market():
    assert ls.blend_with_market(0.8, 0.6, 0.5) == pytest.approx(0.7)
    assert ls.blend_with_market(0.8, None, 0.5) == 0.8
    assert ls.blend_with_market(0.8, 0.6, 2.0) == pytest.approx(0.8)


def test_evaluate_shrinks_live_model_toward_market():
    nes = {"code": 1, "home": "Kokand", "away": "Sogdiana", "markets": {"MS 1": 3.79, "MS X": 1.90, "MS 2": 2.02}}
    live = {"minute": 45, "hg": 0, "ag": 0, "home_red": 0, "away_red": 0}
    kw = {"min_ev": -1.0, "reserve": 100, "kelly_mult": 0.25, "cap_frac": 0.1, "step": 5, "min_stake": 5}
    raw = {o["market"]: o for o in ls.evaluate(nes, live, (1.6, 1.0, "t"), None, model_weight=1.0, **kw)}
    mixed = {o["market"]: o for o in ls.evaluate(nes, live, (1.6, 1.0, "t"), None, **kw)}
    assert mixed["MS 1"]["model_weight"] == ls.LIVE_MODEL_WEIGHT_NO_STATS
    assert mixed["MS 1"]["fair_prob"] < raw["MS 1"]["fair_prob"]
    assert mixed["MS 1"]["ev"] < raw["MS 1"]["ev"]
    assert mixed["MS 1"]["market_prob"] is not None


def test_evaluate_reads_red_from_stats():
    nes = {"code": 1, "home": "A", "away": "B", "markets": {"MS 1": 2.0, "MS X": 3.2, "MS 2": 4.0}}
    live = {"minute": 30, "hg": 0, "ag": 0, "home_red": 0, "away_red": 0}
    kw = {"min_ev": -1.0, "reserve": 100, "kelly_mult": 0.25, "cap_frac": 0.1, "step": 5, "min_stake": 5, "model_weight": 1.0}
    clean = {o["market"]: o for o in ls.evaluate(nes, live, (1.5, 1.1, "t"), {"home": {}, "away": {}}, **kw)}
    red = {o["market"]: o for o in ls.evaluate(nes, live, (1.5, 1.1, "t"), {"home": {"red": 1}, "away": {}}, **kw)}
    assert red["MS 1"]["red"] == "1-0"
    assert red["MS 1"]["fair_prob"] < clean["MS 1"]["fair_prob"]


def test_banko_guard_rejects_audit_mistakes():
    lottery = [bg.BankoLeg(1, "Norwich İY 2", 4.07, 0.23), bg.BankoLeg(2, "Galatasaray 2.5Ü&KG Yok", 3.41, 0.27),
               bg.BankoLeg(3, "Charleroi MS 0", 3.31, 0.27)]
    r = bg.check_coupon(lottery)
    assert not r.ok and any("piyango" in e for e in r.errors) and any("> 1.80" in e for e in r.errors)
    pecs = bg.BankoLeg(3, "Pécs Dep 0,5 Alt", 1.38, 0.83, offered=False)
    assert any("bülteninde yok" in e for e in bg.check_coupon([pecs]).errors)
    live = bg.BankoLeg(4, "Khor Fakkan MS 2", 1.26, 0.81, live=True, p_market=0.627)
    assert bg.check_coupon([live]).ok   # min(0.81, 0.627+0.05)=0.677 ≥ 0.65
    live_low = bg.BankoLeg(5, "Reading Ev 1.5 Üst", 1.60, 0.644, live=True, p_market=0.505)
    assert not bg.check_coupon([live_low]).ok
    no_mkt = bg.BankoLeg(6, "canlı", 1.5, 0.9, live=True)
    assert not bg.check_coupon([no_mkt]).ok


def test_banko_guard_floor_buffer_and_exposure():
    leg = bg.BankoLeg(10, "Tottenham Dep 1.5 Alt", 1.21, 0.73)
    r = bg.check_coupon([leg])
    assert r.ok and any("tabana çok yakın" in w for w in r.warnings)
    assert not bg.check_coupon([bg.BankoLeg(10, "x", 1.17, 0.75)]).ok
    r2 = bg.check_coupon([bg.BankoLeg(11, "Linfield", 1.26, 0.70)], open_exposure={11: 2})
    assert not r2.ok and any("açık kuponda" in e for e in r2.errors)
    dup = [bg.BankoLeg(12, "a", 1.3, 0.75), bg.BankoLeg(12, "b", 1.3, 0.75)]
    assert any("aynı maçtan" in e for e in bg.check_coupon(dup).errors)


def test_banko_10_leg_coupon_passes_and_max_total():
    legs = [bg.BankoLeg(i, f"l{i}", 1.22, 0.72) for i in range(5)]
    r = bg.check_coupon(legs)
    assert r.ok and r.total_odds == pytest.approx(1.22 ** 5)
    assert bg.max_banko_total(5) < 5.0   # 5 bacak × P≥%65 ile 5.00+ banko kurulamaz (denetim bulgusu)
