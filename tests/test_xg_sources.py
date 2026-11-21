import importlib.util
import json
from pathlib import Path

from quantfoot.data import fotmob as fm
from quantfoot.data import understat

FIX = Path(__file__).parent / "fixtures"


def test_fotmob_flag_defaults():
    assert fm.enabled({"QUANTFOOT_AI": "grokbottahmin"}) is True
    assert fm.enabled({"QUANTFOOT_AI": "claudetahmin"}) is False
    assert fm.enabled({"QUANTFOOT_AI": "grokbottahmin", "QUANTFOOT_FOTMOB": "0"}) is False
    assert fm.enabled({"QUANTFOOT_AI": "geminitahmin", "QUANTFOOT_FOTMOB": "1"}) is True


def test_fotmob_details_finished_match():
    d = fm.parse_details(json.loads((FIX / "canli" / "fotmob_detail_finished.json").read_text()))
    assert d["stats"]["home"]["xg"] == 2.83 and d["stats"]["away"]["sot"] == 6.0
    assert d["referee"] == "Peter Bankes" and d["stadium"]["lat"]
    assert d["home_lineup"]["formation"] == "3-4-3" and len(d["home_lineup"]["starters"]) == 11
    assert d["home_lineup"]["unavailable"][0]["reason"] == "injury"


def test_fotmob_minute_parsing():
    assert fm.parse_minute({"long": "51:30"}) == 51.5
    assert fm.parse_minute({"short": "8\u200e\u2019\u200e"}) == 8.0
    assert fm.parse_minute(None) is None


def test_understat_embedded_json_and_form():
    teams = {"1": {"title": "Manchester City", "history": [
        {"xG": 2.0, "xGA": 0.5, "scored": 4, "missed": 0}, {"xG": 1.5, "xGA": 1.0, "scored": 3, "missed": 1},
        {"xG": 1.0, "xGA": 0.8, "scored": 3, "missed": 0}]}}
    raw = json.dumps(teams).encode("unicode_escape").decode().replace('"', "\\x22")
    html = f"<script>var teamsData = JSON.parse('{raw}');</script>"
    blobs = understat.extract_json_blobs(html)
    assert blobs["teamsData"]["1"]["title"] == "Manchester City"
    f = understat.team_xg_form(blobs["teamsData"], "Man City")
    assert f["n"] == 3 and f["xg"] == 1.5 and "üstünde" in f["flag"]
    assert understat.extract_json_blobs("<html>We will come back soon</html>") == {}


def test_api_football_fixture_xg_rows():
    spec = importlib.util.spec_from_file_location("xg_doldur", Path(__file__).parents[1] / "scripts" / "xg_doldur.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = mod.parse_fixture_xg(json.loads((FIX / "af_fixture_finished.json").read_text()))
    assert len(rows) == 2 and {r["venue"] for r in rows} == {"home", "away"}
    assert all(isinstance(r["xg"], float) for r in rows)
