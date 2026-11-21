"""Dataset fetching, caching, and hygiene for historical football matches and odds."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests

MATCHES_URL = "https://huggingface.co/datasets/xgabora/club-football-match-data/resolve/main/Matches.csv"
TIPSAUDIT_URL = "https://huggingface.co/datasets/tipsaudit/football-predictions-closing-odds-margins/resolve/main/tipsaudit-predictions.csv"

DEFAULT_LEAGUES = ["E0", "SP1", "D1", "I1", "F1", "T1", "E1", "N1", "P1"]

LEAGUE_NAMES = {
    "E0": "Premier League (ENG)",
    "E1": "Championship (ENG)",
    "SP1": "La Liga (ESP)",
    "D1": "Bundesliga (GER)",
    "I1": "Serie A (ITA)",
    "F1": "Ligue 1 (FRA)",
    "T1": "Süper Lig (TUR)",
    "N1": "Eredivisie (NED)",
    "P1": "Primeira Liga (POR)",
}

_RESULT_MAP = {"H": 0, "D": 1, "A": 2}
_TIPSAUDIT_RES_MAP = {"1": 0, "X": 1, "2": 2, "H": 0, "D": 1, "A": 2}


def default_data_dir() -> Path:
    """Return the project-local data cache directory."""
    return Path(__file__).resolve().parents[3] / "data"


def ensure_file(path: Path, url: str, refresh: bool = False, timeout: int = 60) -> Path:
    """Download a dataset file if missing or if refresh is requested."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if refresh or not path.exists():
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def normalize_quarter_handicap(series: pd.Series) -> pd.Series:
    """Recover exact quarter-ball handicap lines from 1-decimal rounded values (e.g. -0.3 -> -0.25)."""
    vals = pd.to_numeric(series, errors="coerce")
    return np.round(vals * 4.0) / 4.0


def load_season_history_overrides(
    data_dir: Path | None = None,
    leagues: Iterable[str] | None = None,
    min_date: str | None = None,
    known_teams: set[str] | None = None,
) -> pd.DataFrame:
    """Load current-season football-data.co.uk CSVs synced into ``data/global_odds/latest/season_*/*.csv``."""
    from quantfoot.data.soccerdata_bridge import merge_match_history, normalize_match_history_df

    target_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    base = target_dir / "global_odds" / "latest"
    if not base.exists():
        return pd.DataFrame()

    league_set = {str(x).upper() for x in leagues} if leagues is not None else None
    frames: list[pd.DataFrame] = []
    for season_dir in sorted(base.glob("season_*")):
        if not season_dir.is_dir():
            continue
        for csv_path in sorted(season_dir.glob("*.csv")):
            div_code = csv_path.stem.upper()
            if league_set is not None and div_code not in league_set:
                continue
            try:
                raw = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
            except Exception:
                logging.getLogger(__name__).warning("Sezon CSV okunamadı: %s", csv_path, exc_info=True)
                continue
            if raw.empty:
                continue
            if "Div" not in raw.columns:
                raw["Div"] = div_code
            try:
                norm = normalize_match_history_df(raw, known_teams=known_teams)
            except ValueError:
                continue
            if not norm.empty:
                frames.append(norm)

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for nxt in frames[1:]:
        merged = merge_match_history(merged, nxt)
    if league_set is not None:
        merged = merged[merged["Division"].isin(league_set)]
    if min_date is not None:
        merged = merged[merged["MatchDate"] >= pd.Timestamp(min_date)]
    return merged.reset_index(drop=True)


def load_matches(
    data_dir: Path | None = None,
    leagues: Iterable[str] | None = None,
    min_date: str | None = None,
    require_odds: bool = True,
    refresh: bool = False,
    include_season_history: bool = False,
) -> pd.DataFrame:
    """Load, clean, and chronologically sort historical club football matches.

    When ``include_season_history=True``, merges any current-season football-data.co.uk CSVs
    synced by GitHub Actions into ``data/global_odds/latest/season_*/*.csv`` (keeping the
    default ``False`` so historical walk-forward backtests stay 100% reproducible).
    """
    target_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    csv_path = ensure_file(target_dir / "matches.csv", MATCHES_URL, refresh=refresh)

    df = pd.read_csv(csv_path, low_memory=False)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    df = df.dropna(subset=["MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "FTResult"]).copy()

    if leagues is not None:
        league_set = set(leagues)
        df = df[df["Division"].isin(league_set)]

    if min_date is not None:
        df = df[df["MatchDate"] >= pd.Timestamp(min_date)]

    df["y"] = df["FTResult"].map(_RESULT_MAP)
    df = df.dropna(subset=["y"]).copy()
    df["y"] = df["y"].astype(int)

    if include_season_history:
        from quantfoot.data.soccerdata_bridge import merge_match_history

        known_teams = set(df["HomeTeam"]).union(set(df["AwayTeam"]))
        extra = load_season_history_overrides(
            data_dir=target_dir,
            leagues=leagues,
            min_date=min_date,
            known_teams=known_teams,
        )
        if not extra.empty:
            df = merge_match_history(df, extra)

    if require_odds:
        df = df.dropna(subset=["OddHome", "OddDraw", "OddAway"])
        valid_b365 = (df["OddHome"] > 1.01) & (df["OddDraw"] > 1.01) & (df["OddAway"] > 1.01)
        df = df[valid_b365].copy()

    if "HandiSize" in df.columns:
        df["HandiSizeExact"] = normalize_quarter_handicap(df["HandiSize"])

    sort_cols = ["MatchDate", "MatchTime"] if "MatchTime" in df.columns else ["MatchDate"]
    df = df.sort_values(sort_cols, na_position="first").reset_index(drop=True)
    return df


def load_tipsaudit(data_dir: Path | None = None, refresh: bool = False) -> pd.DataFrame:
    """Load and clean the 2026 Pinnacle opening/closing vs best soft bookmaker dataset."""
    target_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    csv_path = ensure_file(target_dir / "tipsaudit.csv", TIPSAUDIT_URL, refresh=refresh)

    df = pd.read_csv(csv_path)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], errors="coerce")
    df["y"] = df["result"].astype(str).map(_TIPSAUDIT_RES_MAP)

    required_odds = [
        "pin_open_home",
        "pin_open_draw",
        "pin_open_away",
        "pin_close_home",
        "pin_close_draw",
        "pin_close_away",
        "best_soft_home",
        "best_soft_draw",
        "best_soft_away",
    ]
    df = df.dropna(subset=["kickoff_utc", "y", *required_odds]).copy()
    df["y"] = df["y"].astype(int)

    valid = np.ones(len(df), dtype=bool)
    for col in required_odds:
        valid &= df[col].values > 1.01
    df = df[valid].sort_values("kickoff_utc").reset_index(drop=True)
    return df
