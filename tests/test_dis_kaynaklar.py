"""Club Elo view, archive update, closing price of every pick and the simulation scorecard (21 Nov)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
TSI = dt.timezone(dt.timedelta(hours=3))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_elo_table_from_archive_and_view(tmp_path, monkeypatch):
    el = _load("elo_gorus")
    rows = [{"HomeElo": 1600, "AwayElo": 1600, "FTResult": r} for r in "H" * 45 + "D" * 30 + "A" * 25 for _ in range(4)]
    rows += [{"HomeElo": 1800, "AwayElo": 1600, "FTResult": r} for r in "H" * 70 + "D" * 20 + "A" * 10 for _ in range(4)]
    pd.DataFrame(rows).to_csv(tmp_path / "m.csv", index=False)
    t = el.calibrate(tmp_path / "m.csv", tmp_path / "t.json")
    assert set(t["rows"]) == {"0", "200"} and t["rows"]["0"][:3] == [0.45, 0.30, 0.25]
    monkeypatch.setattr(el, "TABLE", tmp_path / "t.json")
    el._table.cache_clear()
    p1, px, p2 = el.probs_1x2(100)
    assert abs(p1 - 0.575) < 1e-9 and abs(px - 0.25) < 1e-9 and abs(p1 + px + p2 - 1) < 1e-9
    (tmp_path / "elo.csv").write_text("Rank,Club,Country,Level,Elo,From,To\n1,Arsenal,ENG,1,1800,x,y\n2,Chelsea,ENG,1,1600,x,y\n",
                                      encoding="utf-8")
    monkeypatch.setattr(el, "RATINGS", tmp_path / "elo.csv")
    el.ratings.cache_clear()
    v = el.match_view({"home": "Arsenal", "away": "Chelsea"})
    assert abs(v["MS 1"] - 0.70) < 1e-9 and abs(v["ÇŞ X2"] - 0.30) < 1e-9
    assert el.match_view({"home": "Unknown FC", "away": "Chelsea"}) is None


def test_archive_update_appends_only_new_matches(tmp_path):
    ar = _load("arsiv_guncelle")
    cols = ["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "FTResult", "HTHome", "HTAway",
            "OddHome"]
    (tmp_path / "m.csv").write_text(",".join(cols) + "\nE0,2026-08-21,,Arsenal,Coventry,3.0,0.0,H,2.0,0.0,1.5\n", encoding="utf-8")
    season = tmp_path / "season_2627"
    season.mkdir()
    season.joinpath("E0.csv").write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,AvgH\n"
        "E0,21/08/2026,20:00,Arsenal,Coventry,3,0,H,2,0,H,1.5\n"
        "E0,22/08/2026,15:00,Hull,Man United,2,0,H,2,0,H,4.2\n"
        "E0,30/11/2026,15:00,Hull,Arsenal,,,,,,,3.1\n", encoding="utf-8")
    before = (tmp_path / "m.csv").read_text(encoding="utf-8")
    assert ar.update(tmp_path / "m.csv", tmp_path) == 1
    after = (tmp_path / "m.csv").read_text(encoding="utf-8")
    assert after.startswith(before) and "2026-08-22" in after          # old rows untouched, only the new one added
    assert ar.update(tmp_path / "m.csv", tmp_path) == 0                  # idempotent


def test_record_clv_keeps_pick_price_and_updates_close(tmp_path):
    at = _load("ai_tahmin")
    m = {"code": 1, "kickoff_iso": "2026-11-20T22:00:00+03:00", "status": "fiyatlandı",
         "selections": [{"name": "2.5 Üst", "fair_prob": 0.66}]}
    picks = [{"nesine_kodu": "1", "mac": "A - B", "secim_adi": "2.5 Üst", "olasilik": "0.6300"}]
    t1, t2 = dt.datetime(2026, 11, 20, 18, 0, tzinfo=TSI), dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI)
    at.record_clv(tmp_path, picks, [m], t1)
    m["selections"][0]["fair_prob"] = 0.68
    clv = at.record_clv(tmp_path, picks, [m], t2)
    rec = clv["1|2.5 Üst"]
    assert rec["p_pick"] == 0.63 and rec["p_close"] == 0.68 and rec["first_seen"].startswith("2026-11-20T18:00")
    m["selections"][0]["fair_prob"] = 0.50
    at.record_clv(tmp_path, picks, [m], dt.datetime(2026, 11, 20, 22, 30, tzinfo=TSI))   # after kick-off: frozen
    assert json.loads((tmp_path / "tahmin_clv.json").read_text(encoding="utf-8"))["1|2.5 Üst"]["p_close"] == 0.68
    assert at.clv_summary(clv) == {"n": 1, "mean": 0.68 - 0.63, "positive": 1}


def test_simulation_scorecard(tmp_path):
    g = _load("gun_degerlendirme")
    (tmp_path / "simulasyon.json").write_text(json.dumps([{"code": 5, "bets": [
        {"name": "2.5 Üst", "verdict": "üçlü onay", "market": 0.66, "sim": 0.68},
        {"name": "MS 1", "verdict": "çelişki", "market": 0.60, "sim": 0.45}]}]), encoding="utf-8")
    v = g.simulation_verdicts(tmp_path, {5: {"completed": True, "ht": [1, 0], "ft90": [2, 1]}})
    assert v["üçlü onay"]["won"] == 1 and v["çelişki"]["won"] == 1 and v["üçlü onay"]["n"] == 1


def test_export_records_first_pick_and_omits_new_started_matches(tmp_path, monkeypatch):
    at = _load("ai_tahmin")
    date = "2026-11-20"
    now = dt.datetime(2026, 11, 20, 18, tzinfo=TSI)
    pick = dict(name="MS 1", market="MS", selection="1", odds=1.25, fair_prob=.8)
    monkeypatch.setattr(at, "best_pick", lambda m: (pick, ""))
    match = dict(code=1, kickoff="2026-11-20 22:00", kickoff_iso="2026-11-20T22:00:00+03:00",
                 status="fiyatlandı", price_tier="keskin", league="L", home="A", away="B", selections=[pick])
    started = dict(match, code=2, kickoff_iso=now.isoformat())
    assert at.export(date, [match, started], area=tmp_path, now=now) == (1, 0)
    rec = json.loads((tmp_path / date / "tahmin_clv.json").read_text())["1|MS 1"]
    assert rec["p_pick"] == rec["p_close"] == .8
