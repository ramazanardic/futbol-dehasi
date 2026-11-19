"""Sharp-vs-soft scan on a synthetic The Odds API payload (no network)."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("sharp_scan", Path(__file__).resolve().parents[1] / "scripts" / "sharp_scan.py")
sharp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sharp)

PAYLOAD = [{
    "id": "e1", "commence_time": "2099-01-01T15:00:00Z", "home_team": "Ev", "away_team": "Dep",
    "bookmakers": [
        {"key": "pinnacle", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Ev", "price": 2.00}, {"name": "Dep", "price": 4.00}, {"name": "Draw", "price": 3.60}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.95, "point": 2.5}, {"name": "Under", "price": 1.95, "point": 2.5}]},
        ]},
        {"key": "softbook", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Ev", "price": 2.20}, {"name": "Dep", "price": 3.70}, {"name": "Draw", "price": 3.30}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.85, "point": 2.5}, {"name": "Under", "price": 2.10, "point": 2.5}]},
        ]},
        {"key": "betfair_ex_eu", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Ev", "price": 2.12}, {"name": "Dep", "price": 4.1}, {"name": "Draw", "price": 3.7}]},
        ]},
    ],
}]


def test_parse_and_fair_prices():
    ev = sharp.parse_events(PAYLOAD)[0]
    assert ev["books"]["pinnacle"]["1"] == 2.0 and ev["books"]["softbook"]["Alt 2.5"] == 2.10
    fair = sharp.pinnacle_fair(ev["books"]["pinnacle"])
    assert fair["1"] + fair["X"] + fair["2"] == pytest.approx(1.0)
    assert fair["Üst 2.5"] == pytest.approx(0.5)


def test_find_value_picks_soft_prices_above_fair():
    picks = sharp.find_value(sharp.parse_events(PAYLOAD), min_ev=0.02, max_odds=3.5, commission=0.02)
    sels = {(p["selection"], p["book"]) for p in picks}
    assert ("1", "softbook") in sels       # 2.20 vs fair ~2.06
    assert ("Alt 2.5", "softbook") in sels  # 2.10 vs fair 2.00
    assert all(p["odds"] <= 3.5 for p in picks)
    assert not any(p["selection"] == "2" for p in picks)  # 4.10 exceeds max odds
    assert all(p["ev"] >= 0.02 for p in picks)
