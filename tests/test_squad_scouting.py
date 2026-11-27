"""Unit & integration tests for Deep Line-by-Line Squad Scouting, Player/GK Form, Derby Intelligence, and Algorithm Wiring."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.data.fotmob import parse_details
from quantfoot.data.match_research import summarize_recent_player_form
from quantfoot.markets.high_odds_engine import analyze_close_match, score_comeback_htft
from quantfoot.markets.match_intelligence import build_boxscore_match_view, enrich_match_record
from quantfoot.markets.squad_scouting import (
    build_match_scouting_report,
    build_team_unit_ratings,
    detect_derby_rivalry,
    render_scouting_markdown,
)


def test_detect_derby_rivalry_turkey_and_world():
    bjk_gs = detect_derby_rivalry("Beşiktaş", "Galatasaray")
    assert bjk_gs is not None
    assert bjk_gs["tier"] == "mega_derbi"
    assert bjk_gs["draw_boost"] > 0

    fb_gs = detect_derby_rivalry("Galatasaray", "Fenerbahçe")
    assert fb_gs is not None and fb_gs["tier"] == "mega_derbi"

    clasico = detect_derby_rivalry("Real Madrid", "FC Barcelona")
    assert clasico is not None and clasico["label"] == "El Clásico"

    # Non-derby & Inter Miami false-positive guard
    assert detect_derby_rivalry("Inter Miami", "AC Milan") is None
    assert detect_derby_rivalry("Beşiktaş", "Sivasspor") is None


def test_recent_player_form_aggregation_extracts_hot_players_and_gk():
    squads = [
        {
            "1": {"name": "Mert Günok", "starter": True, "pos": "G", "goals": 0, "assists": 0, "shots": 0, "sot": 0, "saves": 5, "conceded": 1, "yellow": 0, "red": 0},
            "9": {"name": "Ciro Immobile", "starter": True, "pos": "F", "goals": 2, "assists": 0, "shots": 5, "sot": 3, "saves": 0, "conceded": 0, "yellow": 0, "red": 0},
            "10": {"name": "Rafa Silva", "starter": True, "pos": "M", "goals": 0, "assists": 2, "shots": 3, "sot": 2, "saves": 0, "conceded": 0, "yellow": 1, "red": 0},
        },
        {
            "1": {"name": "Mert Günok", "starter": True, "pos": "G", "goals": 0, "assists": 0, "shots": 0, "sot": 0, "saves": 4, "conceded": 0, "yellow": 0, "red": 0},
            "9": {"name": "Ciro Immobile", "starter": True, "pos": "F", "goals": 1, "assists": 1, "shots": 4, "sot": 2, "saves": 0, "conceded": 0, "yellow": 0, "red": 0},
            "10": {"name": "Rafa Silva", "starter": True, "pos": "M", "goals": 1, "assists": 1, "shots": 2, "sot": 1, "saves": 0, "conceded": 0, "yellow": 0, "red": 0},
        },
        {
            "1": {"name": "Mert Günok", "starter": True, "pos": "G", "goals": 0, "assists": 0, "shots": 0, "sot": 0, "saves": 3, "conceded": 1, "yellow": 0, "red": 0},
            "9": {"name": "Ciro Immobile", "starter": True, "pos": "F", "goals": 1, "assists": 0, "shots": 3, "sot": 2, "saves": 0, "conceded": 0, "yellow": 0, "red": 0},
        },
    ]
    summary = summarize_recent_player_form(squads)
    assert summary["matches"] == 3
    assert summary["hot_players"][0]["name"] == "Ciro Immobile"
    assert summary["hot_players"][0]["goals"] == 4
    assert summary["recent_gk"]["name"] == "Mert Günok"
    assert summary["recent_gk"]["save_pct"] == round(12 / 14, 3)
    assert summary["by_line"]["F"]["goals"] == 4
    assert summary["by_line"]["M"]["assists"] == 3


def test_bjk_gs_full_unit_scouting_and_gk_absence_drop():
    base_bjk = build_team_unit_ratings(
        "Beşiktaş",
        team_rec={
            "form": "WWWDW",
            "profile": {
                "goalkeeper": {"name": "Mert Günok", "apps": 18, "save_pct": 0.78, "conceded_per_game": 0.85},
                "backup_goalkeeper": {"name": "Ersin Destanoğlu", "apps": 2, "save_pct": 0.61, "conceded_per_game": 1.50},
                "top_scorers": [{"name": "Immobile", "goals": 12, "assists": 3}],
                "by_position": {"M": {"goals": 7, "assists": 11}},
            },
            "team_stats": {"Topla oynama": "%58", "Pas isabeti": "%86", "Net pozisyon": "3.1 / maç"},
            "recent_player_form": {
                "matches": 5,
                "hot_players": [{"name": "Immobile", "goals": 5, "assists": 1, "sot": 11}],
                "recent_gk": {"name": "Mert Günok", "starts": 5, "save_pct": 0.80, "conceded_per_game": 0.8},
            },
        },
        xg_side={"xg_for": 1.95, "xg_against": 0.95, "goals_for": 2.0, "goals_against": 0.85, "defensive_luck": 0.10},
        box_side={"shots_for": 15.5, "shots_against": 9.0, "shot_share": 0.63, "sot_for": 5.8, "sot_against": 3.1, "clean_sheet_rate": 0.45, "corners_for": 6.5, "corners_against": 3.8, "corner_share": 0.63, "sot_conversion": 0.34, "gk_save_rate": 0.77},
    )
    # Now simulate #1 GK out + 2 defenders out
    depleted_bjk = build_team_unit_ratings(
        "Beşiktaş",
        team_rec={
            "form": "WWWDW",
            "goalkeeper_changed": True,
            "missing_regulars": [
                {"name": "Mert Günok", "pos": "G"},
                {"name": "Paulista", "pos": "D"},
                {"name": "Uduokhai", "pos": "D"},
            ],
            "profile": {
                "goalkeeper": {"name": "Mert Günok", "apps": 18, "save_pct": 0.78, "conceded_per_game": 0.85},
                "backup_goalkeeper": {"name": "Ersin Destanoğlu", "apps": 2, "save_pct": 0.61, "conceded_per_game": 1.50},
                "top_scorers": [{"name": "Immobile", "goals": 12, "assists": 3}],
                "by_position": {"M": {"goals": 7, "assists": 11}},
            },
        },
        xg_side={"xg_for": 1.95, "xg_against": 0.95, "goals_for": 2.0, "goals_against": 0.85, "defensive_luck": 0.10},
    )
    assert base_bjk.goalkeeper > 75.0
    assert base_bjk.attack > 75.0
    assert base_bjk.midfield > 70.0
    assert base_bjk.defense > 70.0
    assert depleted_bjk.goalkeeper <= base_bjk.goalkeeper - 10.0
    assert depleted_bjk.defense <= base_bjk.defense - 9.0


def test_bjk_gs_close_match_derby_and_markdown_dossier():
    rec = {
        "code": 1903,
        "kickoff": "2026-11-28 20:00",
        "kickoff_iso": "2026-11-28T20:00:00+03:00",
        "league": "Türkiye Süper Lig",
        "home": "Beşiktaş",
        "away": "Galatasaray",
        "mu_home": 1.42,
        "mu_away": 1.38,
        "fair_1x2": [0.39, 0.28, 0.33],
        "selections": [
            {"name": "MS 1", "odds": 2.25, "fair_prob": 0.39},
            {"name": "MS 0", "odds": 3.35, "fair_prob": 0.28},
            {"name": "MS 2", "odds": 2.55, "fair_prob": 0.33},
            {"name": "ÇŞ 10", "odds": 1.38, "fair_prob": 0.67},
        ],
        "research": {
            "teams": {
                "home": {
                    "name": "Beşiktaş",
                    "form": "WWWDW",
                    "profile": {
                        "goalkeeper": {"name": "Mert Günok", "apps": 12, "save_pct": 0.79, "conceded_per_game": 0.80},
                        "top_scorers": [{"name": "Immobile", "goals": 10, "assists": 2}],
                        "by_position": {"M": {"goals": 6, "assists": 9}},
                    },
                    "team_stats": {"Topla oynama": "%57", "Pas isabeti": "%85"},
                },
                "away": {
                    "name": "Galatasaray",
                    "form": "WDWLW",
                    "profile": {
                        "goalkeeper": {"name": "Muslera", "apps": 12, "save_pct": 0.66, "conceded_per_game": 1.35},
                        "top_scorers": [{"name": "Osimhen", "goals": 9, "assists": 3}],
                        "by_position": {"M": {"goals": 4, "assists": 5}},
                    },
                    "team_stats": {"Topla oynama": "%52", "Pas isabeti": "%81"},
                },
            }
        },
    }
    report = build_match_scouting_report(rec)
    assert report is not None
    assert report.derby is not None
    assert report.derby["tier"] == "mega_derbi"
    assert report.goalkeeper_edge > 10.0
    # Strict calibration safety bounds
    assert -0.025 <= report.scouting_edge_1x2["MS 1"] <= 0.025
    assert abs(sum(report.scouting_edge_1x2.values())) < 1e-4
    assert 0.95 <= report.scouting_goal_mult["home"] <= 1.05
    assert 0.95 <= report.scouting_goal_mult["away"] <= 1.05

    rec["research"]["squad_scouting"] = report.to_dict()
    cm = analyze_close_match(rec)
    assert cm is not None
    assert cm.is_close_match is True
    assert any("Derbi" in r for r in cm.reasons)
    assert cm.draw_regime_score > 40.0

    cbs = score_comeback_htft(rec)
    assert len(cbs) == 2

    md = "\n".join(render_scouting_markdown(report))
    assert "Kaleci" in md and "Defans" in md and "Orta Saha" in md and "Forvet / Hücum" in md
    assert "Beşiktaş" in md and "Galatasaray" in md


def test_live_2026_27_super_lig_boxscore_and_enrich_match_record():
    bx = build_boxscore_match_view("Türkiye Süper Lig", "Beşiktaş", "Galatasaray", as_of=dt.date(2026, 11, 25))
    if bx is None:
        pytest.skip("T1 2026/27 CSV not present or insufficient rows")
    assert bx["division"] == "T1"
    assert bx["home"]["shots_for"] > 0
    assert 0.35 <= bx["home"]["gk_save_rate"] <= 0.92
    assert 0.35 <= bx["away"]["gk_save_rate"] <= 0.92

    rec = {
        "league": "Türkiye Süper Lig",
        "home": "Beşiktaş",
        "away": "Galatasaray",
        "kickoff_iso": "2026-11-25T20:00:00+03:00",
        "mu_home": 1.45,
        "mu_away": 1.35,
    }
    enrich_match_record(rec)
    res = rec["research"]
    assert "boxscore_profile" in res
    assert "squad_scouting" in res
    sc = res["squad_scouting"]
    assert sc["confidence"] >= 0.4
    assert sc["derby"]["tier"] == "mega_derbi"
    assert 20.0 <= sc["home"]["goalkeeper"] <= 96.0
    assert 20.0 <= sc["home"]["attack"] <= 96.0
    assert 20.0 <= sc["away"]["defense"] <= 96.0


def test_simulasyon_rates_uses_bounded_squad_scouting_multiplier():
    import simulasyon

    row = {"teams": {"home": {"gf": 1.5, "ga": 1.1, "n": 10}, "away": {"gf": 1.3, "ga": 1.2, "n": 10}}}
    m_base = {"research": {}}
    m_scout = {
        "research": {
            "squad_scouting": {
                "confidence": 0.80,
                "scouting_goal_mult": {"home": 1.04, "away": 0.96},
            }
        }
    }
    mh0, ma0, _ = simulasyon.rates(row, m_base, home_adv=True)
    mh1, ma1, why1 = simulasyon.rates(row, m_scout, home_adv=True)
    assert mh1 > mh0
    assert ma1 < ma0
    assert any("kadro hat eşleşmesi" in w for w in why1)


def test_fotmob_parse_details_keeps_starter_ratings():
    payload = {
        "header": {"status": {}, "teams": [{"score": 1}, {"score": 1}]},
        "content": {
            "lineup": {
                "lineupType": "confirmed",
                "homeTeam": {
                    "formation": "4-2-3-1",
                    "rating": 7.1,
                    "starters": [
                        {"name": "Mert Günok", "positionId": 11, "usualPlayingPositionId": 0, "performance": {"rating": 7.8}},
                    ],
                    "unavailable": [{"name": "Paulista", "unavailability": {"type": "injury", "expectedReturn": "Dec"}}],
                },
                "awayTeam": {"formation": "4-2-3-1", "rating": 6.9, "starters": [], "unavailable": []},
            }
        },
    }
    parsed = parse_details(payload)
    assert parsed["home_lineup"]["starters"] == ["Mert Günok"]
    assert parsed["home_lineup"]["starter_details"][0]["rating"] == 7.8
    assert parsed["home_lineup"]["rating"] == 7.1
