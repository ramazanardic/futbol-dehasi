"""Results tracking: settle recorded predictions and coupons, then aggregate hit rates."""

import importlib.util
import json
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("nesine_takip", SCRIPTS / "nesine_takip.py")
takip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(takip)


def test_settle_and_report(tmp_path, monkeypatch):
    day = tmp_path / "2026-11-19"
    day.mkdir()
    store = {"7": {"home": "A", "away": "B", "league": "L", "kickoff_iso": "2026-11-19T20:00:00+03:00", "reference": "Smarkets",
                   "espn_event": "123", "s": {"MS 1": [0.6, 1.5, 1], "2.5 Üst": [0.55, 1.7, 1], "İY/MS 1/1": [0.4, 2.2, 0],
                                              "DEĞİL(Ev İki Yarıda Gol)": [0.7, 1.25, 0]}}}
    (day / "takip_kayit.json").write_text(json.dumps(store), encoding="utf-8")
    (day / "kupon_2x_2000.json").write_text(json.dumps({"coupons": [{"nesine_odds": 2.55, "probability": 0.33, "legs": [
        {"code": 7, "key": "1|MS 1|0"}, {"code": 7, "key": "2|2.5 Üst|0"}]}]}), encoding="utf-8")
    monkeypatch.setattr(takip, "DAILY", tmp_path)
    monkeypatch.setattr(takip, "OUT", tmp_path / "ozet.md")
    monkeypatch.setattr(takip, "fetch_espn_result", lambda eid: {"completed": True, "ht": [1, 0], "ft90": [2, 0]})
    monkeypatch.setattr(takip, "fetch_nesine_results", lambda dates: {})
    res = takip.settle_day("2026-11-19")
    won = res["7"]["won"]
    assert won["MS 1"] is True and won["2.5 Üst"] is False and won["İY/MS 1/1"] is True
    assert won["DEĞİL(Ev İki Yarıda Gol)"] is False  # home scored in both halves (1-0 HT, 2-0 FT)
    rows, coupons = takip._rows(["2026-11-19"])
    assert len(rows) == 4 and coupons == [{"file": "2026-11-19/kupon_2x_2000.json", "odds": 2.55, "p": 0.33,
                                           "won": False, "legs_won": 1, "legs": 2}]
    assert sum(r[4] for r in rows) == 1  # exactly one 'safest pick' per match
    takip.report()
    text = (tmp_path / "ozet.md").read_text(encoding="utf-8")
    assert "Olasılık bandına göre" in text and "yattı" in text


def test_nesine_results_feed_is_parsed_on_90_minutes():
    from quantfoot.data.nesine import parse_results

    payload = {"d": [
        {"C": 1, "ST": "MS", "ES": [{"T": 1, "H": 3, "A": 0}, {"T": 2, "H": 2, "A": 0}, {"T": 3, "H": 3, "A": 0}]},
        {"C": 2, "ST": "PEN", "ES": [{"T": 1, "H": 1, "A": 1}, {"T": 2, "H": 1, "A": 0}, {"T": 3, "H": 1, "A": 1},
                                    {"T": 9, "H": 5, "A": 3}]},
        {"C": 3, "ST": "Başlamadı.", "ES": []},
        {"C": 4, "ST": "Ksl.", "ES": [{"T": 2, "H": 0, "A": 0}, {"T": 3, "H": 0, "A": 0}]}]}
    r = parse_results(payload)
    assert r[1] == {"completed": True, "status": "MS", "ht": [2, 0], "ft90": [3, 0]}
    assert r[2]["ft90"] == [1, 1]  # penalties do not count
    assert not r[3]["completed"] and not r[4]["completed"]  # not started / abandoned stay open


def test_nesine_results_settle_matches_espn_does_not_list(tmp_path, monkeypatch):
    day = tmp_path / "2026-11-19"
    day.mkdir()
    store = {"9": {"home": "ZED", "away": "Smouha", "league": "Mısır Kupası", "kickoff_iso": "2026-11-19T21:00:00+03:00",
                   "reference": "Matchbook", "espn_event": None, "s": {"KG Yok": [0.6, 1.4, 0]}}}
    (day / "takip_kayit.json").write_text(json.dumps(store), encoding="utf-8")
    monkeypatch.setattr(takip, "DAILY", tmp_path)
    monkeypatch.setattr(takip, "fetch_nesine_results", lambda dates: {9: {"completed": True, "ht": [0, 0], "ft90": [1, 0]}})
    monkeypatch.setattr(takip, "espn_events", lambda d: [])
    assert takip.settle_day("2026-11-19")["9"]["won"] == {"KG Yok": True}


def test_played_coupons_settle_from_nesine_and_screen(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "placed_bets_2026_11_19.csv").write_text(
        "coupon_id,placed_at,stake_tl,total_odds,n_legs,event_id,match,selection,odds,source,note,nesine_code,kickoff,leg_screen,coupon_screen,payout_tl\n"
        "W,2026-11-19 11:00,100,3.00,2,,A - B,MS 1,1.50,ekran,,11,2026-11-19 20:00,,KAZANDI,300\n"
        "W,2026-11-19 11:00,100,3.00,2,,C - D,İlk Gol Ev,2.00,ekran,,12,2026-11-19 21:00,✓,KAZANDI,300\n"
        "L,2026-11-19 12:00,50,10.0,2,,A - B,MS 2,4.00,ekran,,11,2026-11-19 20:00,,yattı,0\n"
        "L,2026-11-19 12:00,50,10.0,2,,E - F,KG Var,2.50,ekran,,13,2026-11-19 22:00,,yattı,0\n", encoding="utf-8")
    day = tmp_path / "daily" / "2026-11-19"
    day.mkdir(parents=True)
    (day / "takip_kayit.json").write_text(json.dumps({"11": {"s": {"MS 1": [0.6, 1.5, 1], "MS 2": [0.2, 4.0, 1]}}}), encoding="utf-8")
    monkeypatch.setattr(takip, "LEDGER", ledger)
    monkeypatch.setattr(takip, "NESINE_CACHE", ledger / "results_nesine.json")
    monkeypatch.setattr(takip, "DAILY", tmp_path / "daily")
    monkeypatch.setattr(takip, "fetch_nesine_results", lambda dates: {11: {"completed": True, "ht": [1, 0], "ft90": [2, 1]},
                                                                      13: {"completed": False}})
    out = {c["id"]: c for c in takip.played_coupons()}
    assert out["W"]["status"] == "TUTTU" and out["W"]["payout"] == 300.0  # 'İlk Gol' leg settled from the screen
    assert out["L"]["status"] == "yattı" and out["L"]["p"] is None  # MS 2 lost; KG Var leg unknown to the system
    lines = "\n".join(takip._played_section())
    assert "net **+150.00 TL**" in lines
