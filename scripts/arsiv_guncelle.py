"""Bring the match archive data/matches.csv up to date from football-data.co.uk season files (user request, 21 Nov).

football-data.co.uk (free, attribution: www.football-data.co.uk) is not reachable from Turkey, so the season CSVs are
downloaded on GitHub's servers by scripts/fetch_global_odds.py into data/global_odds/latest/season_<yy><yy>/; this
script maps them to the archive's columns and appends the played matches the archive does not have yet (same
division, date and teams). Elo and form columns stay empty for the new rows (they come from the archive's own
source); every user of the archive already treats them as optional.

    python scripts/arsiv_guncelle.py            # after git pull
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "matches.csv"
SEASONS = ROOT / "data" / "global_odds" / "latest"
# archive column <- football-data column(s), first one present wins
MAP = {"Division": ["Div"], "MatchTime": ["Time"], "HomeTeam": ["HomeTeam"], "AwayTeam": ["AwayTeam"],
       "FTHome": ["FTHG"], "FTAway": ["FTAG"], "FTResult": ["FTR"], "HTHome": ["HTHG"], "HTAway": ["HTAG"],
       "HTResult": ["HTR"], "HomeShots": ["HS"], "AwayShots": ["AS"], "HomeTarget": ["HST"], "AwayTarget": ["AST"],
       "HomeFouls": ["HF"], "AwayFouls": ["AF"], "HomeCorners": ["HC"], "AwayCorners": ["AC"], "HomeYellow": ["HY"],
       "AwayYellow": ["AY"], "HomeRed": ["HR"], "AwayRed": ["AR"], "OddHome": ["AvgH", "B365H"],
       "OddDraw": ["AvgD", "B365D"], "OddAway": ["AvgA", "B365A"], "MaxHome": ["MaxH"], "MaxDraw": ["MaxD"],
       "MaxAway": ["MaxA"], "Over25": ["Avg>2.5", "B365>2.5"], "Under25": ["Avg<2.5", "B365<2.5"],
       "MaxOver25": ["Max>2.5"], "MaxUnder25": ["Max<2.5"], "HandiSize": ["AHh"], "HandiHome": ["AvgAHH", "B365AHH"],
       "HandiAway": ["AvgAHA", "B365AHA"]}


def convert(fd: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """football-data rows (played only) in the archive's column layout."""
    fd = fd.dropna(subset=["FTHG", "FTAG"])
    out = pd.DataFrame(index=fd.index, columns=columns)
    out["MatchDate"] = pd.to_datetime(fd["Date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    for col, src in MAP.items():
        have = next((s for s in src if s in fd.columns), None)
        if have and col in out.columns:
            out[col] = fd[have]
    return out.dropna(subset=["MatchDate"])


def key(df: pd.DataFrame) -> pd.Series:
    return df["Division"].astype(str) + "|" + df["MatchDate"].astype(str) + "|" + df["HomeTeam"].astype(str) + "|" + \
        df["AwayTeam"].astype(str)


def update(archive: Path = ARCHIVE, seasons: Path = SEASONS) -> int:
    base = pd.read_csv(archive, low_memory=False)
    seen = set(key(base))
    new = []
    for f in sorted(seasons.glob("season_*/*.csv")):
        try:
            fd = pd.read_csv(f, encoding="utf-8", on_bad_lines="skip")
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if not {"Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= set(fd.columns):
            continue
        rows = convert(fd, list(base.columns))
        new.append(rows[~key(rows).isin(seen)])
    add = pd.concat(new, ignore_index=True) if new else pd.DataFrame(columns=base.columns)
    if len(add):  # appended at the end, the existing rows stay byte for byte as they are
        add = add.sort_values(["MatchDate", "Division"], kind="stable")
        with archive.open("a", encoding="utf-8", newline="") as fh:
            add.to_csv(fh, index=False, header=False, lineterminator="\n")
    return len(add)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args()
    n = update()
    print(f"arşiv: {n} yeni maç eklendi -> {ARCHIVE}")


if __name__ == "__main__":
    main()
