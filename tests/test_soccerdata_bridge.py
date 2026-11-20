"""Unit tests for probberechts/soccerdata integration bridge and CLI (offline, synthetic data)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantfoot.cli import build_parser
from quantfoot.data import match_research as mr
from quantfoot.data import soccerdata_bridge as sdb
from quantfoot.markets.market_book import build_market_book


def test_league_and_season_normalization():
    assert sdb.to_soccerdata_league("E0") == "ENG-Premier League"
    assert sdb.to_soccerdata_league("T1") == "TUR-Super Lig"
    assert sdb.to_soccerdata_league("eng.1") == "ENG-Premier League"
    assert sdb.to_soccerdata_league("tur.1") == "TUR-Super Lig"
    assert sdb.to_soccerdata_league("ENG-Premier League") == "ENG-Premier League"

    assert sdb.to_quantfoot_division("ENG-Premier League") == "E0"
    assert sdb.to_quantfoot_division("TUR-Super Lig") == "T1"
    assert sdb.to_quantfoot_division("esp.1") == "SP1"
    assert sdb.to_quantfoot_division("UNKNOWN-League") is None

    assert sdb.resolve_leagues(["E0", "T1", "eng.1"]) == ["ENG-Premier League", "TUR-Super Lig"]
    assert sdb.normalize_season("2026-27") == "2627"
    assert sdb.normalize_season("2025/26") == "2526"
    assert sdb.normalize_season(2026) == "2627"
    assert sdb.normalize_season("2627") == "2627"
    assert sdb.normalize_season(None, today=dt.date(2026, 11, 19)) == "2627"
    assert sdb.normalize_season(None, today=dt.date(2027, 2, 10)) == "2627"


def test_normalize_match_history_and_merge():
    raw = pd.DataFrame(
        [
            {
                "league": "ENG-Premier League",
                "season": "2627",
                "game": "2026-08-21 Arsenal-Brighton",
                "date": pd.Timestamp("2026-08-21 19:00:00"),
                "home_team": "Arsenal",
                "away_team": "Brighton & Hove Albion",
                "FTHG": 2,
                "FTAG": 1,
                "FTR": "H",
                "HTHG": 1,
                "HTAG": 0,
                "HTR": "H",
                "HS": 18,
                "AS": 8,
                "HST": 7,
                "AST": 3,
                "HC": 8,
                "AC": 2,
                "HY": 1,
                "AY": 3,
                "HR": 0,
                "AR": 0,
                "B365H": 1.55,
                "B365D": 4.20,
                "B365A": 6.00,
                "MaxH": 1.62,
                "MaxD": 4.40,
                "MaxA": 6.50,
                "B365>2.5": 1.75,
                "B365<2.5": 2.05,
                "AHh": -1.3,
                "B365AHH": 1.92,
                "B365AHA": 1.98,
                "PSH": 1.58,
                "PSD": 4.35,
                "PSA": 6.10,
            },
            {
                "league": "TUR-Super Lig",
                "season": "2627",
                "game": "2026-08-22 Galatasaray-Fenerbahce",
                "date": pd.Timestamp("2026-08-22 18:45:00"),
                "home_team": "Galatasaray",
                "away_team": "Fenerbahce",
                "FTHG": 1,
                "FTAG": 1,
                "FTR": "D",
                "B365H": 2.10,
                "B365D": 3.40,
                "B365A": 3.30,
                "AHh": -0.3,
                "B365AHH": 1.88,
                "B365AHA": 2.02,
            },
        ]
    ).set_index(["league", "season", "game"])

    norm = sdb.normalize_match_history_df(raw)
    assert list(norm["Division"]) == ["E0", "T1"]
    assert list(norm["y"]) == [0, 1]
    assert norm.loc[0, "AwayTeam"] == "Brighton"
    assert norm.loc[0, "HandiSizeExact"] == pytest.approx(-1.25)
    assert norm.loc[1, "HandiSizeExact"] == pytest.approx(-0.25)
    assert norm.loc[0, "PinHome"] == pytest.approx(1.58)
    assert norm.loc[0, "OddHome"] == pytest.approx(1.55)

    # Merging identical + 1 new match deduplicates cleanly
    base = norm.iloc[:1].copy()
    merged = sdb.merge_match_history(base, norm)
    assert len(merged) == 2
    assert set(merged["Division"]) == {"E0", "T1"}


def test_summarize_understat_teams_and_player_profiles():
    team_matches = pd.DataFrame(
        [
            {
                "league": "ENG-Premier League",
                "season": "2627",
                "game": "2026-08-21 Arsenal-Chelsea",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "home_goals": 3,
                "away_goals": 1,
                "home_xg": 2.45,
                "away_xg": 0.95,
                "home_np_xg": 2.45,
                "away_np_xg": 0.95,
                "home_ppda": 7.8,
                "away_ppda": 11.4,
                "home_deep_completions": 14,
                "away_deep_completions": 6,
            },
            {
                "league": "ENG-Premier League",
                "season": "2627",
                "game": "2026-08-29 Chelsea-Arsenal",
                "home_team": "Chelsea",
                "away_team": "Arsenal",
                "home_goals": 1,
                "away_goals": 2,
                "home_xg": 1.15,
                "away_xg": 1.95,
                "home_np_xg": 1.15,
                "away_np_xg": 1.19,
                "home_ppda": 10.6,
                "away_ppda": 8.2,
                "home_deep_completions": 8,
                "away_deep_completions": 10,
            },
        ]
    ).set_index(["league", "season", "game"])

    summary = sdb.summarize_understat_teams(team_matches)
    assert list(summary["team"]) == ["Arsenal", "Chelsea"]
    ars = summary.iloc[0]
    assert ars["matches"] == 2
    assert ars["xg_per_match"] == pytest.approx(2.20)
    assert ars["xga_per_match"] == pytest.approx(1.05)
    assert ars["ppda"] == pytest.approx(8.0)

    players_df = pd.DataFrame(
        [
            {"league": "ENG-Premier League", "season": "2627", "team": "Arsenal", "player": "Bukayo Saka",
             "matches": 10, "minutes": 860, "goals": 7, "xg": 6.2, "assists": 5, "xa": 4.8, "shots": 32, "yellow_cards": 2},
            {"league": "ENG-Premier League", "season": "2627", "team": "Arsenal", "player": "Kai Havertz",
             "matches": 10, "minutes": 820, "goals": 5, "xg": 5.5, "assists": 2, "xa": 2.1, "shots": 28, "yellow_cards": 3},
            {"league": "ENG-Premier League", "season": "2627", "team": "Arsenal", "player": "Youth Sub",
             "matches": 2, "minutes": 30, "goals": 0, "xg": 0.1, "assists": 0, "xa": 0.0, "shots": 1, "yellow_cards": 0},
        ]
    ).set_index(["league", "season", "team", "player"])

    profiles = sdb.understat_to_player_profiles(players_df, "Arsenal", side="Ev", min_minutes=180)
    assert [p.name for p in profiles] == ["Bukayo Saka", "Kai Havertz"]
    assert all(0.0 <= p.goal_share + p.assist_share <= 1.0 for p in profiles)
    assert profiles[0].starter is True

    # Plug directly into QuantFoot's 20-family market book!
    book = build_market_book(2.1, 0.9, league="eng.1", division="E0", players=profiles)
    assert "16. Golcü" in book and "Bukayo Saka: Gol Atar" in book["16. Golcü"]
    assert 0.10 < book["16. Golcü"]["Bukayo Saka: Gol Atar"] < 0.90
    assert "17. Oyuncu Özel" in book
    assert "Bukayo Saka: Kart Görür" in book["19. Kart"]


def test_espn_summary_parsers_handle_new_boxscore_teams_schema():
    summary = {
        "gameInfo": {"attendance": 60250, "venue": {"fullName": "Emirates Stadium", "capacity": 60704}},
        "boxscore": {
            "teams": [
                {"team": {"displayName": "Arsenal"}, "statistics": [{"name": "possessionPct", "displayValue": "64.2"}]},
                {"team": {"displayName": "Coventry City"}, "statistics": [{"name": "possessionPct", "displayValue": "35.8"}]},
            ]
        },
        "rosters": [
            {
                "team": {"displayName": "Arsenal"},
                "roster": [
                    {"starter": True, "athlete": {"displayName": "David Raya"}, "position": {"name": "Goalkeeper", "abbreviation": "G"},
                     "formationPlace": "1", "stats": [{"name": "saves", "value": 3.0}]},
                ],
            },
            {
                "team": {"displayName": "Coventry City"},
                "roster": [
                    {"starter": False, "athlete": {"displayName": "Bench Sub"}, "position": {"name": "Forward", "abbreviation": "F"},
                     "stats": [{"name": "totalGoals", "value": 0.0}]},
                ],
            },
        ],
    }

    ms = sdb.parse_espn_summary_matchsheet(summary, league="ENG-Premier League", season="2627", game="2026-08-21 Arsenal-Coventry City")
    assert len(ms) == 2
    assert ms.loc[("ENG-Premier League", "2627", "2026-08-21 Arsenal-Coventry City", "Arsenal"), "possessionPct"] == "64.2"

    lu = sdb.parse_espn_summary_lineup(summary, league="ENG-Premier League", season="2627", game="2026-08-21 Arsenal-Coventry City")
    assert len(lu) == 2
    assert bool(lu.loc[("ENG-Premier League", "2627", "2026-08-21 Arsenal-Coventry City", "Arsenal", "David Raya"), "starter"]) is True


def test_corrupt_html_cache_cleanup_on_understat_maintenance(tmp_path: Path, monkeypatch):
    client = sdb.SoccerDataClient(data_dir=tmp_path)
    understat_dir = tmp_path / "Understat"
    understat_dir.mkdir(parents=True)
    poisoned = understat_dir / "leagues.json"
    poisoned.write_text("<!DOCTYPE html><html><body><p>We will come back soon</p></body></html>", encoding="utf-8")

    class BrokenUnderstat:
        def read_team_match_stats(self, force_cache=False):
            raise json.JSONDecodeError("Expecting value", "<!DOCTYPE html>", 0)

    monkeypatch.setattr(client, "get_reader", lambda *a, **k: BrokenUnderstat())
    res = client.understat_team_xg("E0", "2627")
    assert res.ok is False
    assert "HTML maintenance/error cache cleaned: 1 file(s)" in (res.error or "")
    assert not poisoned.exists()


def test_enrich_match_and_match_research_hook(tmp_path: Path, monkeypatch):
    client = sdb.SoccerDataClient(data_dir=tmp_path)

    elo_df = pd.DataFrame(
        [
            {"team": "Arsenal", "rank": 2.0, "country": "ENG", "level": 1, "elo": 2015.4, "league": "ENG-Premier League"},
            {"team": "Chelsea", "rank": 9.0, "country": "ENG", "level": 1, "elo": 1852.1, "league": "ENG-Premier League"},
        ]
    ).set_index("team")

    sched_df = pd.DataFrame(
        [
            {"league": "ENG-Premier League", "season": "2627", "game": "2026-11-22 Arsenal-Chelsea",
             "date": pd.Timestamp("2026-11-22 16:30:00+00:00"), "home_team": "Arsenal", "away_team": "Chelsea",
             "game_id": 999001, "league_id": "eng.1"},
        ]
    ).set_index(["league", "season", "game"])

    monkeypatch.setattr(client, "club_elo", lambda date=None, team=None: sdb.SoccerDataResult("ClubElo", True, elo_df))
    monkeypatch.setattr(
        client,
        "understat_team_xg",
        lambda *a, **k: sdb.SoccerDataResult("Understat", False, pd.DataFrame(), error="JSONDecodeError: maintenance"),
    )
    monkeypatch.setattr(
        client,
        "understat_player_stats",
        lambda *a, **k: sdb.SoccerDataResult("Understat", False, pd.DataFrame(), error="JSONDecodeError: maintenance"),
    )
    monkeypatch.setattr(client, "espn_schedule", lambda *a, **k: sdb.SoccerDataResult("ESPN", True, sched_df))

    ctx = client.enrich_match("Arsenal", "Chelsea", "E0", season="2627")
    assert ctx.club_elo["elo_diff"] == pytest.approx(163.3)
    assert ctx.espn_fixture is not None and ctx.espn_fixture["game_id"] == 999001
    assert ctx.source_status["ClubElo"] == "ok"
    assert ctx.source_status["ESPN"] == "ok"
    assert "maintenance" in ctx.source_status["Understat"]
    assert ctx.to_markdown_rows()["ClubElo"] == ("2015 (#2)", "1852 (#9)")

    base_research = {
        "espn_event": "999001",
        "league_slug": "eng.1",
        "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}},
    }
    enriched = mr.enrich_with_soccerdata(base_research, season="2627", client=client)
    assert "soccerdata" in enriched
    assert enriched["soccerdata"]["club_elo"]["elo_diff"] == pytest.approx(163.3)
    assert "soccerdata" not in base_research  # original dict is not mutated


def test_cli_soccerdata_leagues_subcommand(capsys):
    parser = build_parser()
    args = parser.parse_args(["soccerdata", "--action", "leagues"])
    args.func(args)
    out = capsys.readouterr().out
    assert "TUR-Super Lig" in out
    assert "ClubElo" in out
    assert "Understat" in out
    assert "MatchHistory" in out


def test_extended_soccerdata_client_wrappers(tmp_path, monkeypatch):
    """Verify all newly wrapped Understat/FBref/Sofascore/SoFIFA/WhoScored methods delegate cleanly."""
    client = sdb.SoccerDataClient(data_dir=tmp_path)
    sample = pd.DataFrame([{"ok": 1}])

    class _DummyReader:
        def __init__(self, name: str):
            self.name = name
            self.calls: list[tuple[str, dict]] = []

        def _rec(self, method: str, **kwargs):
            self.calls.append((method, kwargs))
            return sample.assign(source=self.name, method=method)

        def read_schedule(self, **kw):
            return self._rec("read_schedule", **kw)

        def read_player_match_stats(self, **kw):
            return self._rec("read_player_match_stats", **kw)

        def read_team_match_stats(self, **kw):
            return self._rec("read_team_match_stats", **kw)

        def read_lineup(self, **kw):
            return self._rec("read_lineup", **kw)

        def read_events(self, **kw):
            return self._rec("read_events", **kw)

        def read_versions(self, **kw):
            return self._rec("read_versions", **kw)

        def read_player_ratings(self, **kw):
            return self._rec("read_player_ratings", **kw)

    readers: dict[str, _DummyReader] = {}

    def _fake_get_reader(source: str, **kwargs):
        r = _DummyReader(source)
        readers[source] = r
        return r

    monkeypatch.setattr(client, "get_reader", _fake_get_reader)

    checks = [
        client.understat_schedule("E0", "2627"),
        client.understat_player_match_stats("E0", "2627", match_id=123),
        client.fbref_schedule("E0", "2627"),
        client.fbref_team_match_stats("E0", "2627", stat_type="shooting", team="Arsenal"),
        client.fbref_player_match_stats("E0", "2627", stat_type="passing", match_id="abc"),
        client.fbref_lineup("E0", "2627", match_id="abc"),
        client.fbref_events("E0", "2627", match_id="abc"),
        client.sofascore_schedule("T1", "2627"),
        client.sofifa_versions("E0"),
        client.sofifa_player_ratings("E0", team="Arsenal"),
        client.whoscored_schedule("E0", "2627"),
        client.whoscored_events("E0", "2627", match_id=456),
    ]
    assert all(r.ok and r.rows == 1 for r in checks)
    assert set(readers) == {"Understat", "FBref", "Sofascore", "SoFIFA", "WhoScored"}
