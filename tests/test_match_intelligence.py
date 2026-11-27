"""Comprehensive unit tests for the unified pre-match intelligence & multi-sharp fusion pipeline."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.data.match_research import research as espn_research
from quantfoot.data.weather import resolve_coords
from quantfoot.markets.match_intelligence import (
    assess_fatigue_asymmetry,
    build_xg_match_view,
    enrich_match_record,
    evaluate_match_lineup_shock,
    lookup_referee_profile,
    weather_goal_multiplier,
)
import dc_model
import derin_tahmin
import gunluk_analiz
import nesine_global as ng
import nesine_kupon as nk
import simulasyon


def test_live_season_2627_xg_match_view_and_causal_cutoff():
    view = build_xg_match_view("İngiltere Premier Lig", "Arsenal", "Liverpool", as_of=dt.date(2026, 11, 26))
    assert view is not None
    assert view.division == "E0"
    assert 0.35 <= view.xg_mu_home <= 3.8
    assert 0.35 <= view.xg_mu_away <= 3.8
    assert view.home_profile.matches >= 5 and view.away_profile.matches >= 5
    # Strict causal cutoff before season start returns None (zero future leakage)
    assert build_xg_match_view("İngiltere Premier Lig", "Arsenal", "Liverpool", as_of=dt.date(2026, 8, 1)) is None


def test_finishing_luck_regression_flag_detected(tmp_path: Path):
    csv_path = tmp_path / "E0.csv"
    lines = ["Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HxG,AxG,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR"]
    # TeamA scores 3 goals/match on 0.9 xG (massive unsustainable finishing bubble)
    for i in range(1, 9):
        lines.append(f"E0,0{i}/10/2026,TeamA,Opp{i},3,0,0.90,0.80,10,8,4,3,5,4,1,1,0,0")
        lines.append(f"E0,0{i}/10/2026,TeamB,Opp{i},1,1,1.10,1.10,11,11,4,4,4,4,1,1,0,0")
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    view = build_xg_match_view("İngiltere Premier Lig", "TeamA", "TeamB", as_of=dt.date(2026, 11, 1), data_dir=str(tmp_path))
    assert view is not None
    assert view.home_profile.finishing_overperformance > 1.5
    assert any("xG şişkinliği (Ev)" in f for f in view.flags)


def test_live_season_2627_referee_fuzzy_lookup():
    prof = lookup_referee_profile("Michael Oliver")
    assert prof is not None
    assert "oliver" in prof.referee.lower()
    assert prof.matches >= 4 and prof.cards_per_match >= 1.0


def test_t60_lineup_shock_anti_double_counting_and_enrich():
    base_res = {
        "referee": "Michael Oliver",
        "teams": {
            "home": {"rest_days": 2.5, "goalkeeper_changed": True, "top_scorer_missing": True, "missing_regulars": [{"id": "1"}, {"id": "2"}, {"id": "3"}]},
            "away": {"rest_days": 7.0},
        },
        "flags": [],
    }
    # Public news already priced in -> applied=False, theoretical_home_mult < 1, theoretical_away_mult > 1
    s_priced = evaluate_match_lineup_shock(1.8, 1.0, base_res, research_block=False)
    assert s_priced is not None and not s_priced.applied
    assert s_priced.mu_home_adj == pytest.approx(1.8)
    assert s_priced.theoretical_home_mult < 1.0 and s_priced.theoretical_away_mult > 1.0

    # News broke AFTER sharp snapshot -> applied=True, bounded adjustment
    s_fresh = evaluate_match_lineup_shock(1.8, 1.0, base_res, research_block=True)
    assert s_fresh is not None and s_fresh.applied
    assert s_fresh.mu_home_adj < 1.8 and s_fresh.mu_away_adj > 1.0

    rec = {
        "code": 9999, "league": "İngiltere Premier Lig", "home": "Arsenal", "away": "Liverpool",
        "kickoff_iso": "2026-11-26T20:00:00+03:00", "mu_home": 1.8, "mu_away": 1.1,
        "research": base_res, "research_block": True,
    }
    enrich_match_record(rec, as_of=dt.date(2026, 11, 26))
    r = rec["research"]
    assert "xg_intelligence" in r and r["xg_intelligence"]["division"] == "E0"
    assert "referee_profile" in r and r["referee_profile"]["matches"] >= 4
    assert r["fatigue"]["fatigued_side"] == "home"
    assert r["lineup_shock"]["applied"] is True


def test_fatigue_and_severe_weather_dampener():
    fat = assess_fatigue_asymmetry(2.8, 7.0)
    assert fat["fatigued_side"] == "home" and fat["home_mult"] < 1.0 and fat["away_mult"] > 1.0
    assert weather_goal_multiplier({"severe": False, "rain_mm": 0.5}) == 1.0
    assert weather_goal_multiplier({"severe": True, "rain_mm": 8.0, "wind_kmh": 48.0, "snow_cm": 0.0}) < 0.93
    assert resolve_coords("İspanya La Liga", city="Bilbao") is not None
    assert resolve_coords("Türkiye Süper Ligi", city="Antalya") is not None


def test_fuse_sharp_references_merges_pinnacle_and_exchange_direct_markets():
    ko = dt.datetime(2026, 11, 26, 19, 0, tzinfo=dt.timezone.utc)
    ev = SimpleNamespace(home="Arsenal", away="Chelsea", kickoff=ko)
    pin = {"source": "Pinnacle (football-data)", "home": "Arsenal", "away": "Chelsea", "kickoff": ko,
           "x12": [1.85, 3.60, 4.40], "ou": [2.5, [1.82, 2.04]], "markets": {}}
    smk = {"source": "Smarkets (borsa)", "home": "Arsenal", "away": "Chelsea", "kickoff": ko,
           "x12": [1.88, 3.65, 4.35], "ou": [2.5, [1.84, 2.06]],
           "markets": {"Both teams to score": {"YES|Yes": 0.54, "NO|No": 0.46}}}
    mbk = {"source": "Matchbook (borsa)", "home": "Arsenal", "away": "Chelsea", "kickoff": ko,
           "x12": [1.86, 3.62, 4.45], "ou": [2.5, [1.83, 2.05]],
           "markets": {"Over/Under 3.5": {"UNDER|Under 3.5": 0.72}}}

    fused, contra = ng.fuse_sharp_references(ev, pin, [pin, smk, mbk], league="İngiltere Premier Lig")
    assert not contra and fused is not None
    assert ng.is_sharp_source(fused["source"])
    assert fused["consensus_dispersion"]["n_books"] == 3
    dp = ng.direct_probabilities(fused)
    assert dp["KG Var"] == pytest.approx(0.54, abs=1e-4)
    assert dp["3.5 Alt"] == pytest.approx(0.72, abs=1e-4)

    # Exchange contradiction (>8pp) must still return contradiction=True
    smk_bad = {**smk, "x12": [3.80, 3.40, 2.00]}
    bad_ref, bad_contra = ng.fuse_sharp_references(ev, smk_bad, [smk_bad, mbk], league="İngiltere Premier Lig")
    assert bad_ref is None and bad_contra is True


def test_espn_research_extracts_venue_city_and_referee(monkeypatch):
    fake_summary = {
        "header": {"competitions": [{"date": "2026-11-26T20:00Z", "competitors": []}], "league": {"slug": "eng.1"}},
        "gameInfo": {
            "venue": {"fullName": "Emirates Stadium", "address": {"city": "London", "country": "England"}},
            "officials": [{"displayName": "Michael Oliver", "position": {"name": "Referee"}}],
        },
        "lastFiveGames": [],
    }
    monkeypatch.setattr("quantfoot.data.match_research._summary", lambda eid: fake_summary)
    res = espn_research("evt-123")
    assert res is not None
    assert res["venue_name"] == "Emirates Stadium"
    assert res["venue_city"] == "London"
    assert res["referee"] == "Michael Oliver"


def test_dc_model_uses_season_2627_and_league_half_share():
    rows, src = dc_model.league_results("İngiltere Premier Lig", dt.date(2026, 11, 26))
    assert src == "football-data-2627" and len(rows) >= 40
    # Strict causal check: all rows must be strictly before 2026-11-26
    assert all(r[0] < dt.date(2026, 11, 26) for r in rows)


def test_simulasyon_xg_weather_fatigue_and_mean_conserving_game_state():
    row = {
        "league": "İngiltere Premier Lig",
        "teams": {"home": {"gf": 1.6, "ga": 1.0, "n": 10}, "away": {"gf": 1.2, "ga": 1.4, "n": 10}},
        "games": {"home": [], "away": []},
        "flags": [],
    }
    m_base = {"research": {"xg_intelligence": {"xg_mu_home": 2.0, "xg_mu_away": 0.9}, "flags": []}}
    m_storm = {
        "research": {
            "xg_intelligence": {"xg_mu_home": 2.0, "xg_mu_away": 0.9},
            "weather": {"severe": True, "rain_mm": 9.0, "wind_kmh": 50.0, "snow_cm": 0.0},
            "fatigue": {"fatigued_side": "home", "home_mult": 0.96, "away_mult": 1.03, "flag": "Yorgunluk"},
            "flags": [],
        }
    }
    mh0, ma0, why0 = simulasyon.rates(row, m_base, home_adv=True)
    mh1, ma1, why1 = simulasyon.rates(row, m_storm, home_adv=True)
    assert any("sezon xG profili" in w for w in why0)
    assert mh1 < mh0 and any("şiddetli hava" in w for w in why1)

    j_plain, _ = simulasyon.simulate(1.7, 1.1, 25000, seed=7, game_state=False)
    j_gs, _ = simulasyon.simulate(1.7, 1.1, 25000, seed=7, game_state=True)
    assert j_gs.sum() == pytest.approx(1.0, abs=1e-6)
    # Mean-conserving check: expected total goals stays virtually unchanged (~2.80)
    idx = np.indices(j_gs.shape)
    tot_plain = float(np.sum((idx[0] + idx[1] + idx[2] + idx[3]) * j_plain))
    tot_gs = float(np.sum((idx[0] + idx[1] + idx[2] + idx[3]) * j_gs))
    assert abs(tot_gs - tot_plain) < 0.08


def test_builder_pickers_share_directional_steam_and_consensus_kl_guards():
    now = dt.datetime(2026, 11, 26, 15, 0, tzinfo=ng.TSI)
    m = {
        "code": 5001, "kickoff": "2026-11-26 20:00", "kickoff_iso": "2026-11-26T20:00:00+03:00",
        "league": "İngiltere Premier Lig", "home": "Ev", "away": "Dep",
        "status": "fiyatlandı", "reference": "Pinnacle + Smarkets + Matchbook (keskin konsensüs)",
        "mu_home": 1.85, "mu_away": 0.75, "fair_1x2": [0.66, 0.21, 0.13],
        "steam_1x2": [-0.06, 0.03, 0.03],  # Sharp money aggressively AGAINST MS 1!
        "consensus_dispersion": {"max_kl_divergence": 0.004, "n_books": 3},
        "research": {"teams": {"home": {"form": "GGGGG"}, "away": {"form": "MMMMM"}}, "flags": []},
        "selections": [
            {"key": "1|MS 1|0", "market": "Maç Sonucu", "selection": "1", "name": "MS 1",
             "odds": 1.55, "fair_prob": 0.66, "ev": 0.023, "mbs": 1, "direct": True},
        ],
    }
    # derin_tahmin must reject MS 1 fighting -6pp sharp steam
    assert derin_tahmin.candidates(m, 5, calibration={}) == []
    # nesine_kupon must flag diagnosis_ok=False on MS 1 fighting sharp steam
    pools = nk.candidates([m], now, 1.20, 0.55, allow_espn=False, market_calibration=None, family_ev=False)
    assert pools and pools[0][0]["diagnosis_ok"] is False
    # leg_sigma tightens on 3-book low-KL consensus vs 1-book, and widens on high KL
    sig_3 = nk.leg_sigma("MS 1", True, "Pinnacle + Smarkets + Matchbook", True, False, consensus_kl=0.002, n_books=3)
    sig_1 = nk.leg_sigma("MS 1", True, "Pinnacle", True, False, consensus_kl=None, n_books=1)
    sig_hi = nk.leg_sigma("MS 1", True, "Pinnacle + Smarkets", True, False, consensus_kl=0.025, n_books=2)
    assert sig_3 < sig_1 and sig_hi > sig_1
    # gunluk_analiz also evaluates directional steam without crashing
    pick, _ = gunluk_analiz.best_pick(m)
    assert pick is not None
