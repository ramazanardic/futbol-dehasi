"""Offline unit tests for self-learning calibration, optional API connectors, weather, Telegram, and dashboard."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from quantfoot.data import api_football as af
from quantfoot.data import oddspapi as op
from quantfoot.data import weather as wx
from quantfoot.evaluation import auto_learn as al

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# ---- 1. Self-learning & live calibration (auto_learn.py) -------------------------------------


def test_auto_learn_empirical_bayes_calibration_and_kupon_integration(tmp_path):
    daily = tmp_path / "daily"
    day1 = daily / "2026-11-19"
    day1.mkdir(parents=True)

    # Create 60 synthetic settled selections:
    # - 'OverconfidentBook' predicts 0.75 on MS 1 but hits only 55% (-20 pts bias!) -> positive sigma penalty + auto_block warning
    # - 'Matchbook + Smarkets (borsa)' predicts 0.70 on 2.5 Üst and hits 70% -> well-calibrated!
    store = {}
    results = {}
    for i in range(60):
        c1 = str(1000 + i)
        store[c1] = {
            "home": f"H{i}", "away": f"A{i}", "league": "Test Lig", "kickoff_iso": "2026-11-19T20:00:00+03:00",
            "reference": "OddsMath (OverconfidentBook)",
            "s": {"2Y 1": [0.75, 1.45, 0]},
        }
        results[c1] = {"completed": True, "ht": [0, 0], "ft90": [1, 0], "won": {"2Y 1": i < 33}}  # 33/60 = 55%

        c2 = str(2000 + i)
        store[c2] = {
            "home": f"SH{i}", "away": f"SA{i}", "league": "Bundesliga", "kickoff_iso": "2026-11-19T20:00:00+03:00",
            "reference": "Matchbook + Smarkets (borsa)",
            "s": {"2.5 Üst": [0.70, 1.42, 1]},
        }
        results[c2] = {"completed": True, "ht": [1, 0], "ft90": [2, 1], "won": {"2.5 Üst": i < 42}}  # 42/60 = 70%

    (day1 / "takip_kayit.json").write_text(json.dumps(store), encoding="utf-8")
    (day1 / "takip_sonuc.json").write_text(json.dumps(results), encoding="utf-8")

    cal_path = tmp_path / "live_calibration.json"
    rep_path = tmp_path / "ogrenme_raporu.md"
    snap = al.run_auto_learn(daily_dir=daily, calibration_path=cal_path, report_path=rep_path)

    assert cal_path.exists() and rep_path.exists()
    assert snap["total_matches_settled"] == 120
    assert snap["overall"]["n"] == 120
    adj = snap["adjustments"]

    # Overconfident source and family MUST receive positive sigma penalty & warning
    assert adj["source_sigma_delta"]["OddsMath (OverconfidentBook)"] > 0.01
    assert adj["family_sigma_delta"]["İkinci yarı"] > 0.01
    assert "İkinci yarı" in adj["auto_blocked_families"]

    # Calibration delta feeds cleanly into nesine_kupon.leg_sigma
    assert al.load_live_calibration(cal_path)["adjustments"]["source_sigma_delta"] == {}   # 120 < 300: neutral in production
    loaded = al.load_live_calibration(cal_path, min_matches=100)
    delta_bad = al.calibration_sigma_adjustment("OddsMath (OverconfidentBook)", "2Y 1", loaded)
    delta_good = al.calibration_sigma_adjustment("Matchbook + Smarkets (borsa)", "2.5 Üst", loaded)
    assert delta_bad > 0.02
    assert delta_good <= 0.0

    kupon = _load_script("nesine_kupon")
    sig_base = kupon.leg_sigma("2Y 1", False, "OddsMath (OverconfidentBook)", True, False, calibration=None)
    sig_cal = kupon.leg_sigma("2Y 1", False, "OddsMath (OverconfidentBook)", True, False, calibration=loaded)
    assert sig_cal == pytest.approx(sig_base + delta_bad, abs=1e-6)
    assert "Öz-Öğrenme" in rep_path.read_text(encoding="utf-8")


# ---- 2. Optional API-Football & OddsPapi connectors ------------------------------------------


def test_api_football_noop_and_parser(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    assert af.fetch_api_football_references(["2026-11-20"]) == []

    fx_by_id = {
        777: {
            "fixture": {"id": 777, "date": "2026-11-20T16:00:00+00:00"},
            "league": {"country": "Rwanda", "name": "National Soccer League"},
            "teams": {"home": {"name": "Gasogi United"}, "away": {"name": "Kiyovu Sports"}},
        }
    }
    odds_items = [
        {
            "fixture": {"id": 777},
            "bookmakers": [
                {
                    "name": "Bet365",
                    "bets": [
                        {"name": "Match Winner", "values": [{"value": "Home", "odd": "2.90"}, {"value": "Draw", "odd": "3.00"}, {"value": "Away", "odd": "2.40"}]},
                    ],
                },
                {
                    "name": "Pinnacle",
                    "bets": [
                        {"name": "Match Winner", "values": [{"value": "Home", "odd": "3.05"}, {"value": "Draw", "odd": "3.15"}, {"value": "Away", "odd": "2.45"}]},
                        {"name": "Goals Over/Under", "values": [{"value": "Over 2.5", "odd": "2.15"}, {"value": "Under 2.5", "odd": "1.75"}]},
                    ],
                },
            ],
        }
    ]
    refs = af.parse_api_football_odds(fx_by_id, odds_items)
    assert len(refs) == 1
    assert refs[0]["source"] == "Pinnacle (API-Football)"
    assert refs[0]["x12"] == [3.05, 3.15, 2.45]
    assert refs[0]["ou"] == [2.5, [2.15, 1.75]]


def test_oddspapi_noop_and_parser(monkeypatch):
    monkeypatch.delenv("ODDSPAPI_KEY", raising=False)
    assert op.fetch_oddspapi_references(["2026-11-20"]) == []

    fixtures = [
        {
            "participant1Name": "Al-Zawraa",
            "participant2Name": "Al-Talaba",
            "startTime": "2026-11-20T15:30:00Z",
            "tournamentName": "Iraq Stars League",
            "bookmakerOdds": {
                "pinnacle": {
                    "markets": {
                        "101": {"outcomes": {"101": {"price": 1.95}, "102": {"price": 3.30}, "103": {"price": 4.10}}},
                        "104": {"outcomes": {"over": {"price": 2.05}, "under": {"price": 1.85}}},
                    }
                }
            },
        }
    ]
    refs = op.parse_oddspapi_fixtures(fixtures)
    assert len(refs) == 1
    assert refs[0]["source"] == "Pinnacle (OddsPapi)"
    assert refs[0]["x12"] == [1.95, 3.30, 4.10]
    assert refs[0]["ou"] == [2.5, [2.05, 1.85]]


# ---- 3. Open-Meteo severe weather evaluator --------------------------------------------------


def test_weather_severe_vs_calm():
    assert wx.resolve_coords("Almanya Bundesliga") is not None
    assert wx.resolve_coords("Bilinmeyen Gezegen Ligi") is None

    payload = {
        "hourly": {
            "time": ["2026-11-20T17:00", "2026-11-20T18:00"],
            "temperature_2m": [8.5, 4.2],
            "precipitation": [0.2, 6.4],
            "wind_speed_10m": [12.0, 45.0],
            "snowfall": [0.0, 0.0],
        }
    }
    calm = wx.evaluate_hourly_weather(payload, dt.datetime(2026, 11, 20, 17, 30, tzinfo=dt.timezone.utc))
    storm = wx.evaluate_hourly_weather(payload, dt.datetime(2026, 11, 20, 18, 0, tzinfo=dt.timezone.utc))
    assert calm is not None and calm["severe"] is False and calm["flag"] is None
    assert storm is not None and storm["severe"] is True and "şiddetli yağmur" in storm["flag"] and "sert rüzgar" in storm["flag"]


# ---- 4. Telegram & Dashboard builder ---------------------------------------------------------


def test_telegram_and_dashboard_builder(tmp_path, monkeypatch):
    daily = tmp_path / "daily"
    d20 = daily / "2026-11-20"
    d20.mkdir(parents=True)

    ng_sample = {
        "date": "2026-11-20",
        "generated_at": "2026-11-20T08:00:00+03:00",
        "matches": [
            {
                "code": 9001,
                "kickoff": "2026-11-20 20:00",
                "kickoff_iso": "2026-11-20T20:00:00+03:00",
                "league": "Almanya Bundesliga",
                "home": "Mainz",
                "away": "Hoffenheim",
                "status": "fiyatlandı",
                "price_tier": "keskin",
                "reference": "Matchbook + Smarkets (borsa)",
                "fair_1x2": [0.45, 0.27, 0.28],
                "nesine_ms": [2.05, 3.20, 2.95],
                "mu_home": 1.60,
                "mu_away": 1.25,
                "steam_1x2": [0.08, -0.03, -0.05],
                "selections": [
                    {"market": "Alt/Üst", "selection": "1.5 Üst", "name": "1.5 Üst", "odds": 1.22, "fair_prob": 0.78, "ev": -0.048, "direct": True},
                    {"market": "Alt/Üst", "selection": "2.5 Üst", "name": "2.5 Üst", "odds": 1.75, "fair_prob": 0.56, "ev": -0.02, "direct": True},
                ],
                "research": {
                    "teams": {"home": {"form": "WWDLW", "table": {"rank": 8, "size": 18, "points": 16}}, "away": {"form": "LDWLL"}},
                    "flags": ["⚡ Sharp steam: Ev +8.0p", "TM: Dep: 1. kaleci (Baumann) eksik"],
                },
            }
        ],
    }
    (d20 / "nesine_global.json").write_text(json.dumps(ng_sample, ensure_ascii=False), encoding="utf-8")

    # Test dashboard builder
    bd = _load_script("build_dashboard")
    out_dir = tmp_path / "docs_data"
    dash_path = bd.build_dashboard_data(daily_dir=daily, calibration_path=tmp_path / "none.json", out_dir=out_dir,
                                        open_from="2026-11-21")  # the 20th is a settled day here
    dash = json.loads(dash_path.read_text(encoding="utf-8"))
    assert dash["default_date"] == "2026-11-20"
    assert dash["latest"]["summary"]["keskin"] == 1
    assert dash["latest"]["summary"]["steam_alerts"] == 1
    assert dash["latest"]["matches"][0]["best_pick"]["selection"] == "1.5 Üst"

    # Test Telegram message formatter + safe no-op when token absent
    nt = _load_script("notify_telegram")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    msg = nt.build_telegram_message("2026-11-20", daily_dir=daily, calibration_path=tmp_path / "none.json")
    assert "QuantFoot" in msg and "Mainz - Hoffenheim" in msg and "1.5 Üst" in msg
    assert "Sharp Steam" in msg and "1. kaleci" in msg
    assert nt.send_telegram_message(msg) is False
