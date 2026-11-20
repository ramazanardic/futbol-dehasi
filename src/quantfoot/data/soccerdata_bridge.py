"""Integration bridge for probberechts/soccerdata (https://github.com/probberechts/soccerdata).

Provides a lazy-loaded, project-local-cached, failure-resilient interface connecting all eight
upstream ``soccerdata`` scrapers (ClubElo, ESPN, FBref, MatchHistory, SoFIFA, Sofascore,
Understat, WhoScored) to QuantFoot's league codes, historical match schema, team/player xG
profiles, and match research dossiers.

Design principles:
- Zero side effects on ``import quantfoot``: ``soccerdata`` (which configures root logging and
  creates cache directories on import) is imported lazily only when first invoked, with
  ``SOCCERDATA_DIR`` pinned to ``<repo>/data/soccerdata``.
- Extended league registry: QuantFoot's full default + pyramid club league set (including
  ``T1`` Süper Lig, ``E1`` Championship, ``N1`` Eredivisie, ``P1`` Primeira Liga, and 2nd
  tiers) is registered into ``soccerdata._config.LEAGUE_DICT``.
- Honest failure handling: upstream outages (e.g. HTTP 502), maintenance HTML responses,
  geo-restrictions (e.g. ``football-data.co.uk`` from Turkey), or anti-bot 403 blocks are
  never bypassed; they are returned cleanly inside :class:`SoccerDataResult` with diagnostics.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
import datetime as dt
import difflib
import json
import os
from pathlib import Path
import re
from typing import Any
import unicodedata

import numpy as np
import pandas as pd

from quantfoot.data.live_espn import normalize_club_team
from quantfoot.data.loader import default_data_dir, normalize_quarter_handicap
from quantfoot.markets.player_markets import PlayerProfile

# ---- QuantFoot <-> soccerdata league mappings ------------------------------------------------

#: Bidirectional mapping between QuantFoot division codes and canonical soccerdata league IDs.
SOCCERDATA_LEAGUES: dict[str, str] = {
    "E0": "ENG-Premier League",
    "E1": "ENG-Championship",
    "SP1": "ESP-La Liga",
    "SP2": "ESP-La Liga 2",
    "D1": "GER-Bundesliga",
    "D2": "GER-2. Bundesliga",
    "I1": "ITA-Serie A",
    "I2": "ITA-Serie B",
    "F1": "FRA-Ligue 1",
    "F2": "FRA-Ligue 2",
    "T1": "TUR-Super Lig",
    "N1": "NED-Eredivisie",
    "P1": "POR-Primeira Liga",
    "B1": "BEL-Pro League",
    "SC0": "SCO-Premiership",
    "WC": "INT-World Cup",
    "EURO": "INT-European Championship",
    "WWC": "INT-Women's World Cup",
}

DIVISION_FROM_SOCCERDATA: dict[str, str] = {v: k for k, v in SOCCERDATA_LEAGUES.items()}

#: Additional league definitions registered into ``soccerdata._config.LEAGUE_DICT`` so
#: MatchHistory, ESPN, ClubElo, FBref, and Sofascore work beyond the Big-5 defaults.
EXTRA_LEAGUE_DICT: dict[str, dict[str, str]] = {
    "ENG-Championship": {
        "ClubElo": "ENG_2",
        "MatchHistory": "E1",
        "ESPN": "eng.2",
        "FBref": "EFL Championship",
        "Sofascore": "Championship",
        "season_start": "Aug",
        "season_end": "May",
    },
    "TUR-Super Lig": {
        "ClubElo": "TUR_1",
        "MatchHistory": "T1",
        "ESPN": "tur.1",
        "FBref": "Süper Lig",
        "Sofascore": "Trendyol Süper Lig",
        "season_start": "Aug",
        "season_end": "May",
    },
    "NED-Eredivisie": {
        "ClubElo": "NED_1",
        "MatchHistory": "N1",
        "ESPN": "ned.1",
        "FBref": "Eredivisie",
        "Sofascore": "Eredivisie",
        "season_start": "Aug",
        "season_end": "May",
    },
    "POR-Primeira Liga": {
        "ClubElo": "POR_1",
        "MatchHistory": "P1",
        "ESPN": "por.1",
        "FBref": "Primeira Liga",
        "Sofascore": "Liga Portugal Betclic",
        "season_start": "Aug",
        "season_end": "May",
    },
    "ESP-La Liga 2": {
        "ClubElo": "ESP_2",
        "MatchHistory": "SP2",
        "ESPN": "esp.2",
        "FBref": "Segunda División",
        "season_start": "Aug",
        "season_end": "May",
    },
    "GER-2. Bundesliga": {
        "ClubElo": "GER_2",
        "MatchHistory": "D2",
        "ESPN": "ger.2",
        "FBref": "2. Bundesliga",
        "season_start": "Aug",
        "season_end": "May",
    },
    "ITA-Serie B": {
        "ClubElo": "ITA_2",
        "MatchHistory": "I2",
        "ESPN": "ita.2",
        "FBref": "Serie B",
        "season_start": "Aug",
        "season_end": "May",
    },
    "FRA-Ligue 2": {
        "ClubElo": "FRA_2",
        "MatchHistory": "F2",
        "ESPN": "fra.2",
        "FBref": "Ligue 2",
        "season_start": "Aug",
        "season_end": "May",
    },
    "BEL-Pro League": {
        "ClubElo": "BEL_1",
        "MatchHistory": "B1",
        "ESPN": "bel.1",
        "FBref": "Belgian Pro League",
        "season_start": "Jul",
        "season_end": "May",
    },
    "SCO-Premiership": {
        "ClubElo": "SCO_1",
        "MatchHistory": "SC0",
        "ESPN": "sco.1",
        "FBref": "Scottish Premiership",
        "season_start": "Aug",
        "season_end": "May",
    },
}

_ESPN_SLUG_TO_LEAGUE: dict[str, str] = {
    "eng.1": "ENG-Premier League",
    "eng.2": "ENG-Championship",
    "esp.1": "ESP-La Liga",
    "esp.2": "ESP-La Liga 2",
    "ger.1": "GER-Bundesliga",
    "ger.2": "GER-2. Bundesliga",
    "ita.1": "ITA-Serie A",
    "ita.2": "ITA-Serie B",
    "fra.1": "FRA-Ligue 1",
    "fra.2": "FRA-Ligue 2",
    "tur.1": "TUR-Super Lig",
    "ned.1": "NED-Eredivisie",
    "por.1": "POR-Primeira Liga",
    "bel.1": "BEL-Pro League",
    "sco.1": "SCO-Premiership",
}

_SOURCE_CATALOG: dict[str, dict[str, Any]] = {
    "ClubElo": {
        "transport": "http",
        "scope": "Global European club Elo ratings & historical trajectories",
        "methods": ["read_by_date", "read_team_history"],
    },
    "ESPN": {
        "transport": "http",
        "scope": "Fixtures, box-score matchsheets, and lineups across QuantFoot leagues",
        "methods": ["read_schedule", "read_matchsheet", "read_lineup"],
    },
    "MatchHistory": {
        "transport": "http",
        "scope": "Football-Data.co.uk historical scores, box-score stats, Bet365 & Pinnacle odds",
        "methods": ["read_games"],
    },
    "Understat": {
        "transport": "http",
        "scope": "Big-5 league xG, NPxG, PPDA, deep completions, player xG/xA, shot events",
        "methods": [
            "read_schedule",
            "read_team_match_stats",
            "read_player_season_stats",
            "read_player_match_stats",
            "read_shot_events",
        ],
    },
    "Sofascore": {
        "transport": "http",
        "scope": "League tables, schedules, and seasons",
        "methods": ["read_leagues", "read_seasons", "read_league_table", "read_schedule"],
    },
    "FBref": {
        "transport": "browser",
        "scope": "Team & player season/match stats, lineups, events (SeleniumBase)",
        "methods": [
            "read_schedule",
            "read_team_season_stats",
            "read_team_match_stats",
            "read_player_season_stats",
            "read_player_match_stats",
            "read_lineup",
            "read_events",
        ],
    },
    "SoFIFA": {
        "transport": "browser",
        "scope": "FIFA / EA FC team & player attribute ratings (SeleniumBase)",
        "methods": ["read_versions", "read_teams", "read_players", "read_team_ratings", "read_player_ratings"],
    },
    "WhoScored": {
        "transport": "browser",
        "scope": "Opta-style match events & missing-player lists (SeleniumBase)",
        "methods": ["read_schedule", "read_missing_players", "read_events"],
    },
}

_RESULT_MAP = {"H": 0, "D": 1, "A": 2}
_CONFIGURED = False


def supported_sources() -> dict[str, dict[str, Any]]:
    """Return metadata for all upstream ``probberechts/soccerdata`` scrapers."""
    return {k: dict(v) for k, v in _SOURCE_CATALOG.items()}


def default_soccerdata_dir(data_dir: Path | None = None) -> Path:
    """Return the project-local directory used for soccerdata caches, configs, and logs."""
    return Path(data_dir) if data_dir is not None else default_data_dir() / "soccerdata"


def to_soccerdata_league(league: str) -> str:
    """Convert a QuantFoot division code (e.g. ``'E0'``, ``'T1'``) or ESPN slug to soccerdata ID."""
    key = league.strip()
    upper = key.upper()
    if upper in SOCCERDATA_LEAGUES:
        return SOCCERDATA_LEAGUES[upper]
    lower = key.lower()
    if lower in _ESPN_SLUG_TO_LEAGUE:
        return _ESPN_SLUG_TO_LEAGUE[lower]
    return key


def to_quantfoot_division(league: str | None) -> str | None:
    """Convert a soccerdata league name (or division code) back to a QuantFoot division code."""
    if not league:
        return None
    key = str(league).strip()
    if key in DIVISION_FROM_SOCCERDATA:
        return DIVISION_FROM_SOCCERDATA[key]
    if key.upper() in SOCCERDATA_LEAGUES:
        return key.upper()
    if key.lower() in _ESPN_SLUG_TO_LEAGUE:
        return DIVISION_FROM_SOCCERDATA.get(_ESPN_SLUG_TO_LEAGUE[key.lower()])
    return None


def resolve_leagues(leagues: str | Iterable[str] | None) -> list[str] | None:
    """Normalize one or more QuantFoot/ESPN/soccerdata league identifiers into soccerdata IDs."""
    if leagues is None:
        return None
    if isinstance(leagues, str):
        return [to_soccerdata_league(leagues)]
    out: list[str] = []
    for item in leagues:
        mapped = to_soccerdata_league(str(item))
        if mapped not in out:
            out.append(mapped)
    return out


def current_european_season(today: dt.date | None = None) -> str:
    """Return the current European split-year season code (e.g. ``'2627'`` for Nov 2026)."""
    ref = today or dt.date.today()
    start_year = ref.year if ref.month >= 7 else ref.year - 1
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def normalize_season(season: str | int | None, today: dt.date | None = None) -> str:
    """Normalize season inputs (``None``, ``2026``, ``'2026-27'``, ``'2627'``) to ``'YYZZ'``."""
    if season is None:
        return current_european_season(today=today)
    s = str(season).strip()
    if re.fullmatch(r"\d{4}", s):
        val = int(s)
        # Disambiguate calendar year (2025, 2026) vs split-year code (2526, 2627)
        if 1990 <= val <= 2099 and (val // 100) in (19, 20):
            return f"{val % 100:02d}{(val + 1) % 100:02d}"
        return s
    m = re.fullmatch(r"(?:19|20)?(\d{2})[-/](?:19|20)?(\d{2})", s)
    if m:
        return f"{m.group(1)}{m.group(2)}"
    if re.fullmatch(r"\d{2}", s):
        y = int(s)
        return f"{y:02d}{(y + 1) % 100:02d}"
    return s


def resolve_seasons(seasons: str | int | Iterable[str | int] | None) -> list[str]:
    """Normalize one or more season specs to a list of ``'YYZZ'`` codes."""
    if seasons is None:
        return [current_european_season()]
    if isinstance(seasons, (str, int)):
        return [normalize_season(seasons)]
    return [normalize_season(s) for s in seasons]


def configure_soccerdata(
    data_dir: Path | None = None,
    log_level: str = "WARNING",
    persist_league_dict: bool = False,
) -> Any:
    """Lazily import ``soccerdata`` with project-local storage and QuantFoot extended leagues."""
    global _CONFIGURED
    base_dir = default_soccerdata_dir(data_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SOCCERDATA_DIR", str(base_dir))
    os.environ.setdefault("SOCCERDATA_LOGLEVEL", log_level.upper())

    if persist_league_dict:
        cfg_dir = base_dir / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        ld_path = cfg_dir / "league_dict.json"
        if not ld_path.exists():
            ld_path.write_text(json.dumps(EXTRA_LEAGUE_DICT, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        import soccerdata as sd
        import soccerdata._config as sd_cfg
    except ImportError as exc:
        raise ImportError(
            "soccerdata is not installed. Install it via: "
            "uv pip install 'git+https://github.com/probberechts/soccerdata.git'"
        ) from exc

    if not _CONFIGURED:
        for league_name, meta in EXTRA_LEAGUE_DICT.items():
            if league_name not in sd_cfg.LEAGUE_DICT:
                sd_cfg.LEAGUE_DICT[league_name] = dict(meta)
            else:
                for k, v in meta.items():
                    sd_cfg.LEAGUE_DICT[league_name].setdefault(k, v)
        _CONFIGURED = True

    return sd


def _ascii_key(name: str) -> str:
    norm = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch if ch.isalnum() else " " for ch in norm.lower())
    return " ".join(cleaned.split())


def _match_team_in_list(query: str, candidates: Iterable[str]) -> str | None:
    """Fuzzy-match a team name across QuantFoot, ESPN, ClubElo, and Understat conventions."""
    cand_list = [str(c) for c in candidates if pd.notna(c)]
    if not cand_list:
        return None
    if query in cand_list:
        return query
    canonical = normalize_club_team(query, set(cand_list))
    if canonical in cand_list:
        return canonical

    q_key = _ascii_key(query)
    key_map = {_ascii_key(c): c for c in cand_list}
    if q_key in key_map:
        return key_map[q_key]

    stop = {"fc", "cf", "ac", "as", "sc", "rc", "fk", "sk", "afc", "sv", "vfb", "tsg", "rb", "cd", "ud"}
    q_strip = " ".join(w for w in q_key.split() if w not in stop)
    strip_map = {" ".join(w for w in _ascii_key(c).split() if w not in stop): c for c in cand_list}
    if q_strip and q_strip in strip_map:
        return strip_map[q_strip]

    for k, orig in strip_map.items():
        if q_strip and (q_strip in k or k in q_strip) and min(len(q_strip), len(k)) >= 4:
            return orig

    close = difflib.get_close_matches(q_strip or q_key, list(strip_map.keys()), n=1, cutoff=0.72)
    return strip_map[close[0]] if close else None


def _pick_first_col(df: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    """Return the first matching numeric column from candidates, coalescing missing values."""
    out = pd.Series(np.nan, index=df.index, dtype=float)
    for col in candidates:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce")
            out = out.fillna(vals)
    return out


# ---- Pure DataFrame transformers (testable offline without network) --------------------------


def normalize_match_history_df(
    raw_df: pd.DataFrame,
    known_teams: set[str] | None = None,
) -> pd.DataFrame:
    """Convert a ``soccerdata.MatchHistory.read_games()`` DataFrame to QuantFoot's ``load_matches()`` schema."""
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(
            columns=[
                "Division",
                "MatchDate",
                "MatchTime",
                "HomeTeam",
                "AwayTeam",
                "FTHome",
                "FTAway",
                "FTResult",
                "y",
                "OddHome",
                "OddDraw",
                "OddAway",
            ]
        )

    df = raw_df.reset_index().copy()

    if "date" in df.columns:
        dt_series = pd.to_datetime(df["date"], errors="coerce")
    elif "Date" in df.columns:
        dt_series = pd.to_datetime(df["Date"], errors="coerce", dayfirst=True)
    else:
        raise ValueError("MatchHistory DataFrame missing 'date'/'Date' column.")

    out = pd.DataFrame(index=df.index)
    if "league" in df.columns:
        out["Division"] = df["league"].map(lambda x: to_quantfoot_division(str(x)) or str(x))
    elif "Div" in df.columns:
        out["Division"] = df["Div"].astype(str)
    else:
        out["Division"] = "UNK"

    out["MatchDate"] = dt_series.dt.normalize()
    out["MatchTime"] = dt_series.dt.strftime("%H:%M").where(dt_series.notna(), "")

    home_col = "home_team" if "home_team" in df.columns else "HomeTeam"
    away_col = "away_team" if "away_team" in df.columns else "AwayTeam"
    out["HomeTeam"] = df[home_col].astype(str).map(lambda x: normalize_club_team(x, known_teams))
    out["AwayTeam"] = df[away_col].astype(str).map(lambda x: normalize_club_team(x, known_teams))

    out["FTHome"] = _pick_first_col(df, ("FTHG", "HG", "FTHome"))
    out["FTAway"] = _pick_first_col(df, ("FTAG", "AG", "FTAway"))
    if "FTR" in df.columns:
        out["FTResult"] = df["FTR"].astype(str).str.strip().str.upper()
    elif "Res" in df.columns:
        out["FTResult"] = df["Res"].astype(str).str.strip().str.upper()
    else:
        out["FTResult"] = np.where(
            out["FTHome"] > out["FTAway"],
            "H",
            np.where(out["FTHome"] < out["FTAway"], "A", "D"),
        )

    out["HTHome"] = _pick_first_col(df, ("HTHG", "HTHome"))
    out["HTAway"] = _pick_first_col(df, ("HTAG", "HTAway"))
    if "HTR" in df.columns:
        out["HTResult"] = df["HTR"].astype(str).str.strip().str.upper()
    else:
        out["HTResult"] = np.nan

    out["HomeShots"] = _pick_first_col(df, ("HS", "HomeShots"))
    out["AwayShots"] = _pick_first_col(df, ("AS", "AwayShots"))
    out["HomeTarget"] = _pick_first_col(df, ("HST", "HomeTarget"))
    out["AwayTarget"] = _pick_first_col(df, ("AST", "AwayTarget"))
    out["HomeFouls"] = _pick_first_col(df, ("HF", "HomeFouls"))
    out["AwayFouls"] = _pick_first_col(df, ("AF", "AwayFouls"))
    out["HomeCorners"] = _pick_first_col(df, ("HC", "HomeCorners"))
    out["AwayCorners"] = _pick_first_col(df, ("AC", "AwayCorners"))
    out["HomeYellow"] = _pick_first_col(df, ("HY", "HomeYellow"))
    out["AwayYellow"] = _pick_first_col(df, ("AY", "AwayYellow"))
    out["HomeRed"] = _pick_first_col(df, ("HR", "HomeRed"))
    out["AwayRed"] = _pick_first_col(df, ("AR", "AwayRed"))

    out["OddHome"] = _pick_first_col(df, ("B365H", "AvgH", "BbAvH", "PSH", "OddHome"))
    out["OddDraw"] = _pick_first_col(df, ("B365D", "AvgD", "BbAvD", "PSD", "OddDraw"))
    out["OddAway"] = _pick_first_col(df, ("B365A", "AvgA", "BbAvA", "PSA", "OddAway"))
    out["MaxHome"] = _pick_first_col(df, ("MaxH", "BbMxH", "MaxHome"))
    out["MaxDraw"] = _pick_first_col(df, ("MaxD", "BbMxD", "MaxDraw"))
    out["MaxAway"] = _pick_first_col(df, ("MaxA", "BbMxA", "MaxAway"))
    out["Over25"] = _pick_first_col(df, ("B365>2.5", "Avg>2.5", "BbAv>2.5", "P>2.5", "Over25"))
    out["Under25"] = _pick_first_col(df, ("B365<2.5", "Avg<2.5", "BbAv<2.5", "P<2.5", "Under25"))
    out["MaxOver25"] = _pick_first_col(df, ("Max>2.5", "BbMx>2.5", "MaxOver25"))
    out["MaxUnder25"] = _pick_first_col(df, ("Max<2.5", "BbMx<2.5", "MaxUnder25"))

    out["HandiSize"] = _pick_first_col(df, ("AHh", "BbAHh", "HandiSize"))
    out["HandiSizeExact"] = normalize_quarter_handicap(out["HandiSize"])
    out["HandiHome"] = _pick_first_col(df, ("B365AHH", "AvgAHH", "PAHH", "HandiHome"))
    out["HandiAway"] = _pick_first_col(df, ("B365AHA", "AvgAHA", "PAHA", "HandiAway"))

    # Preserve Pinnacle opening & closing odds when present for sharp-benchmark research
    out["PinHome"] = _pick_first_col(df, ("PSH", "PH"))
    out["PinDraw"] = _pick_first_col(df, ("PSD", "PD"))
    out["PinAway"] = _pick_first_col(df, ("PSA", "PA"))
    out["PinCloseHome"] = _pick_first_col(df, ("PSCH",))
    out["PinCloseDraw"] = _pick_first_col(df, ("PSCD",))
    out["PinCloseAway"] = _pick_first_col(df, ("PSCA",))

    out["y"] = out["FTResult"].map(_RESULT_MAP)
    out = out.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "y"]).copy()
    out["y"] = out["y"].astype(int)
    out = out.sort_values(["MatchDate", "MatchTime", "Division", "HomeTeam"]).reset_index(drop=True)
    return out


def merge_match_history(base_df: pd.DataFrame, extra_df: pd.DataFrame) -> pd.DataFrame:
    """Merge normalized MatchHistory rows onto ``load_matches()`` without duplicating fixtures."""
    if extra_df is None or extra_df.empty:
        return base_df.copy()
    if base_df is None or base_df.empty:
        return extra_df.copy()

    combined = pd.concat([base_df, extra_df], ignore_index=True, sort=False)
    combined["_dedup_date"] = pd.to_datetime(combined["MatchDate"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined["_dedup_home"] = combined["HomeTeam"].astype(str).map(_ascii_key)
    combined["_dedup_away"] = combined["AwayTeam"].astype(str).map(_ascii_key)
    combined = (
        combined.drop_duplicates(subset=["Division", "_dedup_date", "_dedup_home", "_dedup_away"], keep="last")
        .drop(columns=["_dedup_date", "_dedup_home", "_dedup_away"])
        .sort_values(["MatchDate", "Division", "HomeTeam"])
        .reset_index(drop=True)
    )
    return combined


def summarize_understat_teams(team_match_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ``Understat.read_team_match_stats()`` into per-team season xG/PPDA/deep summaries."""
    if team_match_df is None or team_match_df.empty:
        return pd.DataFrame(
            columns=[
                "team",
                "matches",
                "goals_for",
                "goals_against",
                "xg_for",
                "xg_against",
                "npxg_for",
                "npxg_against",
                "xg_per_match",
                "xga_per_match",
                "xg_diff_per_match",
                "ppda",
                "deep_per_match",
            ]
        )

    df = team_match_df.reset_index().copy()
    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        for side, opp in (("home", "away"), ("away", "home")):
            team = r.get(f"{side}_team")
            if pd.isna(team):
                continue
            rows.append(
                {
                    "league": r.get("league"),
                    "season": r.get("season"),
                    "team": str(team),
                    "gf": pd.to_numeric(r.get(f"{side}_goals"), errors="coerce"),
                    "ga": pd.to_numeric(r.get(f"{opp}_goals"), errors="coerce"),
                    "xgf": pd.to_numeric(r.get(f"{side}_xg"), errors="coerce"),
                    "xga": pd.to_numeric(r.get(f"{opp}_xg"), errors="coerce"),
                    "npxgf": pd.to_numeric(r.get(f"{side}_np_xg"), errors="coerce"),
                    "npxga": pd.to_numeric(r.get(f"{opp}_np_xg"), errors="coerce"),
                    "ppda": pd.to_numeric(r.get(f"{side}_ppda"), errors="coerce"),
                    "deep": pd.to_numeric(r.get(f"{side}_deep_completions"), errors="coerce"),
                }
            )

    long_df = pd.DataFrame(rows).dropna(subset=["xgf", "xga"])
    if long_df.empty:
        return pd.DataFrame()

    grp = (
        long_df.groupby("team", as_index=False)
        .agg(
            matches=("gf", "count"),
            goals_for=("gf", "sum"),
            goals_against=("ga", "sum"),
            xg_for=("xgf", "sum"),
            xg_against=("xga", "sum"),
            npxg_for=("npxgf", "sum"),
            npxg_against=("npxga", "sum"),
            ppda=("ppda", "mean"),
            deep_per_match=("deep", "mean"),
        )
        .copy()
    )
    grp["xg_per_match"] = grp["xg_for"] / grp["matches"]
    grp["xga_per_match"] = grp["xg_against"] / grp["matches"]
    grp["xg_diff_per_match"] = grp["xg_per_match"] - grp["xga_per_match"]
    return grp.sort_values("xg_diff_per_match", ascending=False).reset_index(drop=True)


def understat_to_player_profiles(
    player_df: pd.DataFrame,
    team_name: str,
    side: str = "Ev",
    min_minutes: int = 180,
    top_n: int = 6,
) -> list[PlayerProfile]:
    """Convert ``Understat.read_player_season_stats()`` rows into QuantFoot :class:`PlayerProfile` objects.

    Blends observed goal/assist shares with xG/xA shares (50/50 shrinkage) so small-sample hot
    streaks do not blow up player-prop probabilities in ``quantfoot.markets.player_markets``.
    """
    if player_df is None or player_df.empty:
        return []
    df = player_df.reset_index().copy()
    if "team" not in df.columns or "player" not in df.columns:
        return []

    matched_team = _match_team_in_list(team_name, df["team"].dropna().unique())
    if matched_team is None:
        return []

    sub = df[df["team"] == matched_team].copy()
    for col in ("matches", "minutes", "goals", "xg", "assists", "xa", "shots", "yellow_cards"):
        sub[col] = pd.to_numeric(sub[col], errors="coerce").fillna(0.0) if col in sub.columns else 0.0

    team_goals = max(float(sub["goals"].sum()), 1.0)
    team_xg = max(float(sub["xg"].sum()), 1.0)
    team_xa = max(float(sub["xa"].sum()), 1.0)

    sub = sub[sub["minutes"] >= float(min_minutes)].copy()
    if sub.empty:
        return []

    sub["_rank_score"] = sub["xg"] + 0.6 * sub["xa"] + 0.35 * sub["goals"]
    sub = sub.sort_values("_rank_score", ascending=False).head(top_n)

    profiles: list[PlayerProfile] = []
    for _, row in sub.iterrows():
        mins = float(row["minutes"])
        matches = max(float(row["matches"]), 1.0)
        avg_min = float(np.clip(mins / matches, 10.0, 90.0))
        g_share = 0.5 * (float(row["goals"]) / team_goals) + 0.5 * (float(row["xg"]) / team_xg)
        a_share = 0.5 * (float(row["assists"]) / team_goals) + 0.5 * (float(row["xa"]) / team_xa)
        # Keep PlayerProfile invariant: 0 <= goal_share + assist_share <= 1.0
        total_share = g_share + a_share
        if total_share > 0.95:
            scale = 0.95 / total_share
            g_share *= scale
            a_share *= scale
        p90_scale = 90.0 / max(mins, 1.0)
        profiles.append(
            PlayerProfile(
                name=str(row["player"]),
                team=side,
                goal_share=round(max(0.0, g_share), 4),
                assist_share=round(max(0.0, a_share), 4),
                minutes=round(avg_min, 1),
                starter=avg_min >= 55.0,
                shots_p90=round(float(row["shots"]) * p90_scale, 3),
                sot_p90=round(float(row["shots"]) * 0.35 * p90_scale, 3),
                yellow_p90=round(float(row["yellow_cards"]) * p90_scale, 3),
            )
        )
    return profiles


def lookup_club_elo(elo_df: pd.DataFrame, team_name: str) -> dict[str, Any] | None:
    """Look up a team's ClubElo rating record from ``ClubElo.read_by_date()`` output."""
    if elo_df is None or elo_df.empty:
        return None
    df = elo_df.reset_index().copy()
    team_col = "team" if "team" in df.columns else df.columns[0]
    matched = _match_team_in_list(team_name, df[team_col].dropna().unique())
    if matched is None:
        return None
    row = df[df[team_col] == matched].iloc[0]
    elo_val = pd.to_numeric(row.get("elo"), errors="coerce")
    rank_val = pd.to_numeric(row.get("rank"), errors="coerce")
    return {
        "team": str(matched),
        "elo": round(float(elo_val), 1) if pd.notna(elo_val) else None,
        "rank": int(rank_val) if pd.notna(rank_val) else None,
        "country": str(row.get("country")) if pd.notna(row.get("country")) else None,
        "level": int(row.get("level")) if pd.notna(pd.to_numeric(row.get("level"), errors="coerce")) else None,
    }


def parse_espn_summary_matchsheet(
    summary_data: dict[str, Any],
    *,
    league: str,
    season: str,
    game: str,
) -> pd.DataFrame:
    """Parse an ESPN summary JSON into a soccerdata-compatible matchsheet DataFrame.

    Handles both legacy ``boxscore.form`` and newer ``boxscore.teams`` ESPN schemas (fixing the
    upstream ``KeyError: 'form'`` issue in ``soccerdata==2026.43.0``).
    """
    boxscore = summary_data.get("boxscore") or {}
    teams_block = boxscore.get("teams") or []
    form_block = boxscore.get("form") or []
    rosters = summary_data.get("rosters") or []
    game_info = summary_data.get("gameInfo") or {}
    venue_info = game_info.get("venue") or {}

    n_teams = max(len(teams_block), len(form_block), len(rosters))
    if n_teams == 0:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for idx in range(min(2, n_teams)):
        team_name = None
        if idx < len(teams_block):
            team_name = (teams_block[idx].get("team") or {}).get("displayName")
        if not team_name and idx < len(form_block):
            team_name = (form_block[idx].get("team") or {}).get("displayName")
        if not team_name and idx < len(rosters):
            team_name = (rosters[idx].get("team") or {}).get("displayName")
        if not team_name:
            continue

        rec: dict[str, Any] = {
            "league": league,
            "season": season,
            "game": game,
            "team": team_name,
            "is_home": idx == 0,
            "venue": venue_info.get("fullName"),
            "attendance": game_info.get("attendance"),
            "capacity": venue_info.get("capacity"),
        }
        if idx < len(teams_block):
            for st in teams_block[idx].get("statistics") or []:
                name = st.get("name")
                if name:
                    rec[name] = st.get("displayValue")
        rows.append(rec)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index(["league", "season", "game", "team"]).sort_index()


def parse_espn_summary_lineup(
    summary_data: dict[str, Any],
    *,
    league: str,
    season: str,
    game: str,
) -> pd.DataFrame:
    """Parse an ESPN summary JSON into a soccerdata-compatible player lineup DataFrame."""
    rosters = summary_data.get("rosters") or []
    box_teams = (summary_data.get("boxscore") or {}).get("teams") or []
    rows: list[dict[str, Any]] = []
    for idx, roster_block in enumerate(rosters[:2]):
        team_name = (roster_block.get("team") or {}).get("displayName")
        if not team_name and idx < len(box_teams):
            team_name = (box_teams[idx].get("team") or {}).get("displayName")
        for p in roster_block.get("roster") or []:
            athlete = p.get("athlete") or {}
            player_name = athlete.get("displayName")
            if not player_name:
                continue
            rec: dict[str, Any] = {
                "league": league,
                "season": season,
                "game": game,
                "team": team_name or f"team_{idx}",
                "is_home": idx == 0,
                "player": player_name,
                "position": (p.get("position") or {}).get("name"),
                "position_abbr": (p.get("position") or {}).get("abbreviation"),
                "starter": bool(p.get("starter")),
                "formation_place": p.get("formationPlace"),
            }
            for st in p.get("stats") or []:
                if st.get("name"):
                    rec[st["name"]] = st.get("value")
            rows.append(rec)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index(["league", "season", "game", "team", "player"]).sort_index()


def _purge_corrupt_json_cache(directory: Path) -> list[Path]:
    """Delete cached ``.json`` files that actually contain HTML (e.g. maintenance pages)."""
    removed: list[Path] = []
    if not directory.exists():
        return removed
    for path in directory.glob("*.json"):
        try:
            head = path.read_bytes()[:64].lstrip()
        except OSError:
            continue
        if head.startswith(b"<"):
            try:
                path.unlink()
                removed.append(path)
            except OSError:
                pass
    return removed


# ---- Result & Enriched Match Context Dataclasses ---------------------------------------------


@dataclass
class SoccerDataResult:
    """Structured return envelope for every ``SoccerDataClient`` call."""

    source: str
    ok: bool
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None
    cache_dir: Path | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def rows(self) -> int:
        return int(len(self.data))


@dataclass
class SoccerDataMatchContext:
    """Aggregated soccerdata intelligence for a single fixture."""

    home: str
    away: str
    league: str
    division: str | None
    season: str
    club_elo: dict[str, Any] = field(default_factory=dict)
    understat_teams: dict[str, Any] = field(default_factory=dict)
    understat_players: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    espn_fixture: dict[str, Any] | None = None
    source_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home": self.home,
            "away": self.away,
            "league": self.league,
            "division": self.division,
            "season": self.season,
            "club_elo": self.club_elo,
            "understat_teams": self.understat_teams,
            "understat_players": self.understat_players,
            "espn_fixture": self.espn_fixture,
            "source_status": self.source_status,
        }

    def to_markdown_rows(self) -> dict[str, tuple[str, str]]:
        """Format key metrics as ``label -> (home_str, away_str)`` for match dossiers."""
        rows: dict[str, tuple[str, str]] = {}
        eh = self.club_elo.get("home")
        ea = self.club_elo.get("away")
        if eh or ea:
            h_txt = f"{eh['elo']:.0f} (#{eh['rank']})" if eh and eh.get("elo") else "-"
            a_txt = f"{ea['elo']:.0f} (#{ea['rank']})" if ea and ea.get("elo") else "-"
            rows["ClubElo"] = (h_txt, a_txt)

        uh = self.understat_teams.get("home")
        ua = self.understat_teams.get("away")
        if uh or ua:
            rows["Understat xG / xGA"] = (
                f"{uh['xg_per_match']:.2f} / {uh['xga_per_match']:.2f}" if uh else "-",
                f"{ua['xg_per_match']:.2f} / {ua['xga_per_match']:.2f}" if ua else "-",
            )
            rows["Understat PPDA"] = (
                f"{uh['ppda']:.1f}" if uh and pd.notna(uh.get("ppda")) else "-",
                f"{ua['ppda']:.1f}" if ua and pd.notna(ua.get("ppda")) else "-",
            )
        return rows


# ---- Unified Client --------------------------------------------------------------------------


class SoccerDataClient:
    """High-level QuantFoot adapter over ``probberechts/soccerdata`` scrapers."""

    def __init__(
        self,
        data_dir: Path | None = None,
        proxy: str | list[str] | Callable[[], str] | None = None,
        no_cache: bool = False,
        no_store: bool = False,
        headless: bool = True,
        log_level: str = "WARNING",
        strict: bool = False,
    ) -> None:
        self.data_dir = default_soccerdata_dir(data_dir).resolve()
        self.proxy = proxy
        self.no_cache = no_cache
        self.no_store = no_store
        self.headless = headless
        self.log_level = log_level
        self.strict = strict

    def _sd(self) -> Any:
        return configure_soccerdata(data_dir=self.data_dir, log_level=self.log_level)

    def _source_dir(self, source: str) -> Path:
        path = self.data_dir / source
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_reader(
        self,
        source: str,
        *,
        leagues: str | Iterable[str] | None = None,
        seasons: str | int | Iterable[str | int] | None = None,
        **extra_kwargs: Any,
    ) -> Any:
        """Instantiate an upstream ``soccerdata`` scraper configured with QuantFoot defaults."""
        sd = self._sd()
        canonical_map = {name.lower(): name for name in _SOURCE_CATALOG}
        cls_name = canonical_map.get(source.strip().lower(), source)
        cls = getattr(sd, cls_name, None)
        if cls is None:
            raise ValueError(f"Unknown soccerdata source '{source}'. Valid: {sorted(_SOURCE_CATALOG)}")

        kwargs: dict[str, Any] = {
            "proxy": self.proxy,
            "no_cache": self.no_cache,
            "no_store": self.no_store,
            "data_dir": self._source_dir(cls_name),
        }
        if cls_name != "ClubElo":
            resolved_leagues = resolve_leagues(leagues)
            if resolved_leagues is not None:
                kwargs["leagues"] = resolved_leagues
        if cls_name not in ("ClubElo", "SoFIFA") and seasons is not None:
            kwargs["seasons"] = resolve_seasons(seasons)
        if cls_name in ("FBref", "SoFIFA", "WhoScored"):
            kwargs["headless"] = self.headless
        kwargs.update(extra_kwargs)
        return cls(**kwargs)

    def _safe_call(
        self,
        source: str,
        fn: Callable[[], pd.DataFrame],
        *,
        meta: dict[str, Any] | None = None,
        cleanup_html_cache: bool = False,
    ) -> SoccerDataResult:
        cache_dir = self._source_dir(source)
        try:
            df = fn()
            return SoccerDataResult(
                source=source,
                ok=True,
                data=df if isinstance(df, pd.DataFrame) else pd.DataFrame(),
                cache_dir=cache_dir,
                meta=meta or {},
            )
        except Exception as exc:
            removed = _purge_corrupt_json_cache(cache_dir) if cleanup_html_cache else []
            msg = f"{type(exc).__name__}: {exc}"
            if removed:
                msg += f" (HTML maintenance/error cache cleaned: {len(removed)} file(s))"
            if self.strict:
                raise
            return SoccerDataResult(
                source=source,
                ok=False,
                data=pd.DataFrame(),
                error=msg,
                cache_dir=cache_dir,
                meta=meta or {},
            )

    # ---- ClubElo -------------------------------------------------------------------------

    def club_elo(self, date: str | dt.datetime | None = None, team: str | None = None) -> SoccerDataResult:
        """Fetch ClubElo snapshot by date or full history for one club."""
        def _run() -> pd.DataFrame:
            reader = self.get_reader("ClubElo")
            df = reader.read_team_history(team) if team else reader.read_by_date(date)
            if not df.empty and "league" in df.columns:
                df = df.copy()
                df["division"] = df["league"].map(to_quantfoot_division)
            return df

        return self._safe_call("ClubElo", _run, meta={"date": str(date) if date else "today", "team": team})

    # ---- MatchHistory (Football-Data.co.uk) ----------------------------------------------

    def match_history(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        as_quantfoot: bool = True,
        known_teams: set[str] | None = None,
    ) -> SoccerDataResult:
        """Fetch Football-Data.co.uk games, optionally normalized to ``load_matches()`` schema."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("MatchHistory", leagues=resolved_leagues, seasons=resolved_seasons)
            raw = reader.read_games()
            return normalize_match_history_df(raw, known_teams=known_teams) if as_quantfoot else raw

        return self._safe_call(
            "MatchHistory",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "as_quantfoot": as_quantfoot},
        )

    # ---- Understat -----------------------------------------------------------------------

    def understat_team_xg(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        summarize: bool = True,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch Understat team match xG/NPxG/PPDA/deep data (or aggregated season summary)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Understat", leagues=resolved_leagues, seasons=resolved_seasons)
            raw = reader.read_team_match_stats(force_cache=force_cache)
            return summarize_understat_teams(raw) if summarize else raw

        return self._safe_call(
            "Understat",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "summarize": summarize},
            cleanup_html_cache=True,
        )

    def understat_player_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch Understat season-level player stats (goals, xG, assists, xA, shots, cards)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Understat", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_player_season_stats(force_cache=force_cache)

        return self._safe_call(
            "Understat",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
            cleanup_html_cache=True,
        )

    def understat_shots(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
    ) -> SoccerDataResult:
        """Fetch Understat shot-level xG events."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Understat", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_shot_events(match_id=match_id)

        return self._safe_call(
            "Understat",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
            cleanup_html_cache=True,
        )

    def understat_schedule(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        include_matches_without_data: bool = True,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch Understat season fixture schedule."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Understat", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_schedule(
                include_matches_without_data=include_matches_without_data,
                force_cache=force_cache,
            )

        return self._safe_call(
            "Understat",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
            cleanup_html_cache=True,
        )

    def understat_player_match_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
    ) -> SoccerDataResult:
        """Fetch Understat per-match player stats (xG, xA, shots, key passes)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Understat", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_player_match_stats(match_id=match_id)

        return self._safe_call(
            "Understat",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
            cleanup_html_cache=True,
        )

    # ---- ESPN ----------------------------------------------------------------------------

    def espn_schedule(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch season schedule via ``soccerdata.ESPN`` (works across Big-5 + T1/E1/N1/P1)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("ESPN", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_schedule(force_cache=force_cache)

        return self._safe_call(
            "ESPN",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "force_cache": force_cache},
        )

    def _espn_fallback_summary(
        self,
        reader: Any,
        df_sched: pd.DataFrame,
        match_id: int | list[int] | None,
        kind: str,
    ) -> pd.DataFrame:
        sched = df_sched.reset_index()
        if match_id is not None:
            ids = [match_id] if isinstance(match_id, int) else list(match_id)
            sched = sched[sched["game_id"].isin(ids)]
        if sched.empty:
            raise ValueError("No games with the given match_id found in ESPN schedule.")

        frames: list[pd.DataFrame] = []
        for _, m in sched.iterrows():
            url = f"http://site.api.espn.com/apis/site/v2/sports/soccer/{m['league_id']}/summary?event={m['game_id']}"
            filepath = reader.data_dir / f"Summary_{m['game_id']}.json"
            raw = reader.get(url, filepath)
            payload = json.load(raw)
            if kind == "matchsheet":
                part = parse_espn_summary_matchsheet(
                    payload, league=str(m["league"]), season=str(m["season"]), game=str(m["game"])
                )
            else:
                part = parse_espn_summary_lineup(
                    payload, league=str(m["league"]), season=str(m["season"]), game=str(m["game"])
                )
            if not part.empty:
                frames.append(part)
        return pd.concat(frames).sort_index() if frames else pd.DataFrame()

    def espn_matchsheet(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
        force_cache: bool = True,
    ) -> SoccerDataResult:
        """Fetch ESPN box-score matchsheets with automatic fallback for ESPN's ``boxscore.teams`` schema."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("ESPN", leagues=resolved_leagues, seasons=resolved_seasons)
            df_sched = reader.read_schedule(force_cache=force_cache)
            if force_cache:
                return self._espn_fallback_summary(reader, df_sched, match_id, kind="matchsheet")
            try:
                return reader.read_matchsheet(match_id=match_id)
            except KeyError:
                return self._espn_fallback_summary(reader, df_sched, match_id, kind="matchsheet")

        return self._safe_call(
            "ESPN",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    def espn_lineup(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
        force_cache: bool = True,
    ) -> SoccerDataResult:
        """Fetch ESPN player lineups & match stats with automatic fallback for newer summary JSON."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("ESPN", leagues=resolved_leagues, seasons=resolved_seasons)
            df_sched = reader.read_schedule(force_cache=force_cache)
            if force_cache:
                return self._espn_fallback_summary(reader, df_sched, match_id, kind="lineup")
            try:
                return reader.read_lineup(match_id=match_id)
            except KeyError:
                return self._espn_fallback_summary(reader, df_sched, match_id, kind="lineup")

        return self._safe_call(
            "ESPN",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    # ---- FBref / Sofascore / SoFIFA / WhoScored ------------------------------------------

    def fbref_team_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        stat_type: str = "standard",
        opponent_stats: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref team season statistics (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_team_season_stats(stat_type=stat_type, opponent_stats=opponent_stats)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "stat_type": stat_type},
        )

    def fbref_player_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        stat_type: str = "standard",
    ) -> SoccerDataResult:
        """Fetch FBref player season statistics (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_player_season_stats(stat_type=stat_type)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "stat_type": stat_type},
        )

    def fbref_schedule(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref season schedule (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_schedule(force_cache=force_cache)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
        )

    def fbref_team_match_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        stat_type: str = "schedule",
        opponent_stats: bool = False,
        team: str | list[str] | None = None,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref team match-by-match stats (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_team_match_stats(
                stat_type=stat_type,
                opponent_stats=opponent_stats,
                team=team,
                force_cache=force_cache,
            )

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "stat_type": stat_type, "team": team},
        )

    def fbref_player_match_stats(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        stat_type: str = "summary",
        match_id: str | list[str] | None = None,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref player match-level statistics (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_player_match_stats(stat_type=stat_type, match_id=match_id, force_cache=force_cache)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "stat_type": stat_type, "match_id": match_id},
        )

    def fbref_lineup(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: str | list[str] | None = None,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref match lineups (requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_lineup(match_id=match_id, force_cache=force_cache)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    def fbref_events(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: str | list[str] | None = None,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch FBref match events (goals, cards, subs; requires browser / SeleniumBase)."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("FBref", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_events(match_id=match_id, force_cache=force_cache)

        return self._safe_call(
            "FBref",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    def sofascore_table(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch Sofascore league table."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Sofascore", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_league_table(force_cache=force_cache)

        return self._safe_call(
            "Sofascore",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
        )

    def sofascore_schedule(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch Sofascore season schedule."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("Sofascore", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_schedule(force_cache=force_cache)

        return self._safe_call(
            "Sofascore",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
        )

    def sofifa_versions(
        self,
        leagues: str | Iterable[str] | None = None,
        *,
        max_age: int | dt.timedelta = 1,
    ) -> SoccerDataResult:
        """Fetch available SoFIFA FIFA/EA FC database versions."""
        resolved_leagues = resolve_leagues(leagues)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("SoFIFA", leagues=resolved_leagues)
            return reader.read_versions(max_age=max_age)

        return self._safe_call("SoFIFA", _run, meta={"leagues": resolved_leagues})

    def sofifa_team_ratings(
        self,
        leagues: str | Iterable[str],
        *,
        versions: str | int | list[int] = "latest",
    ) -> SoccerDataResult:
        """Fetch SoFIFA club ratings (overall, attack, midfield, defence)."""
        resolved_leagues = resolve_leagues(leagues)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("SoFIFA", leagues=resolved_leagues, versions=versions)
            return reader.read_team_ratings()

        return self._safe_call("SoFIFA", _run, meta={"leagues": resolved_leagues, "versions": versions})

    def sofifa_player_ratings(
        self,
        leagues: str | Iterable[str],
        *,
        versions: str | int | list[int] = "latest",
        team: str | list[str] | None = None,
        player: int | list[int] | None = None,
    ) -> SoccerDataResult:
        """Fetch SoFIFA player attribute ratings."""
        resolved_leagues = resolve_leagues(leagues)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("SoFIFA", leagues=resolved_leagues, versions=versions)
            return reader.read_player_ratings(team=team, player=player)

        return self._safe_call(
            "SoFIFA",
            _run,
            meta={"leagues": resolved_leagues, "versions": versions, "team": team, "player": player},
        )

    def whoscored_schedule(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch WhoScored fixture schedule."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("WhoScored", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_schedule(force_cache=force_cache)

        return self._safe_call(
            "WhoScored",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons},
        )

    def whoscored_missing_players(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
        force_cache: bool = False,
    ) -> SoccerDataResult:
        """Fetch WhoScored injury/suspension missing-player lists."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("WhoScored", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_missing_players(match_id=match_id, force_cache=force_cache)

        return self._safe_call(
            "WhoScored",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    def whoscored_events(
        self,
        leagues: str | Iterable[str],
        seasons: str | int | Iterable[str | int] | None = None,
        *,
        match_id: int | list[int] | None = None,
        force_cache: bool = False,
        output_fmt: str | None = "events",
    ) -> SoccerDataResult:
        """Fetch WhoScored Opta-style event streams."""
        resolved_leagues = resolve_leagues(leagues)
        resolved_seasons = resolve_seasons(seasons)

        def _run() -> pd.DataFrame:
            reader = self.get_reader("WhoScored", leagues=resolved_leagues, seasons=resolved_seasons)
            return reader.read_events(match_id=match_id, force_cache=force_cache, output_fmt=output_fmt)

        return self._safe_call(
            "WhoScored",
            _run,
            meta={"leagues": resolved_leagues, "seasons": resolved_seasons, "match_id": match_id},
        )

    # ---- High-level Fixture Enrichment ---------------------------------------------------

    def enrich_match(
        self,
        home: str,
        away: str,
        league: str,
        *,
        season: str | int | None = None,
        date: str | dt.datetime | None = None,
        sources: Iterable[str] = ("clubelo", "understat", "espn"),
        force_cache: bool = True,
    ) -> SoccerDataMatchContext:
        """Combine available soccerdata signals (ClubElo, Understat xG/players, ESPN fixture) for a matchup."""
        sd_league = to_soccerdata_league(league)
        div = to_quantfoot_division(sd_league)
        season_code = normalize_season(season)
        ctx = SoccerDataMatchContext(
            home=home,
            away=away,
            league=sd_league,
            division=div,
            season=season_code,
        )

        requested = [s.strip().lower() for s in sources]

        if "clubelo" in requested:
            elo_res = self.club_elo(date=date)
            if elo_res.ok and not elo_res.data.empty:
                h_elo = lookup_club_elo(elo_res.data, home)
                a_elo = lookup_club_elo(elo_res.data, away)
                if h_elo:
                    ctx.club_elo["home"] = h_elo
                if a_elo:
                    ctx.club_elo["away"] = a_elo
                if h_elo and a_elo and h_elo.get("elo") and a_elo.get("elo"):
                    ctx.club_elo["elo_diff"] = round(float(h_elo["elo"]) - float(a_elo["elo"]), 1)
                ctx.source_status["ClubElo"] = "ok"
            else:
                ctx.source_status["ClubElo"] = elo_res.error or "empty"

        understat_supported = sd_league in {
            "ENG-Premier League",
            "ESP-La Liga",
            "GER-Bundesliga",
            "ITA-Serie A",
            "FRA-Ligue 1",
        }
        if "understat" in requested:
            if not understat_supported:
                ctx.source_status["Understat"] = f"unsupported league ({sd_league})"
            else:
                u_team = self.understat_team_xg(sd_league, season_code, summarize=True, force_cache=force_cache)
                if u_team.ok and not u_team.data.empty:
                    teams_avail = u_team.data["team"].tolist()
                    for side_key, q_name in (("home", home), ("away", away)):
                        hit = _match_team_in_list(q_name, teams_avail)
                        if hit is not None:
                            row = u_team.data[u_team.data["team"] == hit].iloc[0].to_dict()
                            ctx.understat_teams[side_key] = {
                                k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v)
                                for k, v in row.items()
                            }
                    ctx.source_status["Understat"] = "ok"
                else:
                    ctx.source_status["Understat"] = u_team.error or "empty"

                u_players = self.understat_player_stats(sd_league, season_code, force_cache=force_cache)
                if u_players.ok and not u_players.data.empty:
                    for side_key, q_name, p_side in (("home", home, "Ev"), ("away", away, "Dep")):
                        profiles = understat_to_player_profiles(u_players.data, q_name, side=p_side, top_n=5)
                        if profiles:
                            ctx.understat_players[side_key] = [
                                {
                                    "name": p.name,
                                    "goal_share": p.goal_share,
                                    "assist_share": p.assist_share,
                                    "minutes": p.minutes,
                                    "shots_p90": p.shots_p90,
                                    "yellow_p90": p.yellow_p90,
                                }
                                for p in profiles
                            ]

        if "espn" in requested:
            e_sched = self.espn_schedule(sd_league, season_code, force_cache=force_cache)
            if e_sched.ok and not e_sched.data.empty:
                sdf = e_sched.data.reset_index()
                h_match = _match_team_in_list(home, sdf["home_team"].unique())
                a_match = _match_team_in_list(away, sdf["away_team"].unique())
                hit_rows = (
                    sdf[(sdf["home_team"] == h_match) & (sdf["away_team"] == a_match)]
                    if (h_match and a_match)
                    else pd.DataFrame()
                )
                if not hit_rows.empty:
                    r0 = hit_rows.iloc[0]
                    ctx.espn_fixture = {
                        "game": str(r0.get("game")),
                        "game_id": int(r0["game_id"]) if pd.notna(r0.get("game_id")) else None,
                        "date": str(r0.get("date")),
                        "home_team": str(r0.get("home_team")),
                        "away_team": str(r0.get("away_team")),
                    }
                ctx.source_status["ESPN"] = "ok"
            else:
                ctx.source_status["ESPN"] = e_sched.error or "empty"

        return ctx
