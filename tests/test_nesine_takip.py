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
