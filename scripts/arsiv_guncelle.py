"""Bring the match archive data/matches.csv up to date from football-data.co.uk season files (user request, 21 Nov).

football-data.co.uk (free, attribution: www.football-data.co.uk) is not reachable from Turkey, so the season CSVs are
downloaded on GitHub's servers by scripts/fetch_global_odds.py into data/global_odds/latest/season_<yy><yy>/; this
script maps them to the archive's columns and appends the played matches the archive does not have yet (same
division, date and teams).

Ek ligler (28 Kas 2026): football-data.co.uk "new leagues" dosyaları (ARG, BRA, JPN, USA …) fetch_global_odds.py ile
data/global_odds/latest/new_leagues/ altına iner; kapanış ortalama/maks 1X2 oranlarıyla (AvgC*/MaxC*) arşive eklenir.
Arşivin eski ek lig satırlarında tarih bazen gün/ay ters okunmuş (12/08 → 12 Ara); çift kayıt olmasın diye eşleşmede
gün/ay ters tarih de denenir.

Form (Form3/5 Home/Away) yeni satırlar için arşivin kendi tanımıyla doldurulur: takımın aynı ligdeki son 3/5 maçından
topladığı puan (G=3, B=1, M=0; ev/deplasman ayrımı yok) — eski satırlarla %98/%94 birebir uyumlu. Elo sütunları boş
kalır (maç öncesi Club Elo geçmişi bu kaynakta yok); arşivi kullanan her betik bunları isteğe bağlı sayar.

    python scripts/arsiv_guncelle.py            # after git pull / fetch_global_odds.py --season-history
"""

from __future__ import annotations

import argparse
from collections import defaultdict
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
    return _numeric(out).dropna(subset=["MatchDate"])


# football-data ek lig dosya kodu -> arşiv Division kodu (fetch_global_odds.NEW_LEAGUES ile aynı)
NEW_LEAGUES = {"ARG": "ARG", "AUT": "AUT", "BRA": "BRA", "CHN": "CHN", "DNK": "DEN", "FIN": "FIN", "IRL": "IRL",
               "JPN": "JAP", "MEX": "MEX", "NOR": "NOR", "POL": "POL", "ROU": "ROM", "RUS": "RUS", "SWZ": "SUI",
               "SWE": "SWE", "USA": "USA"}
NEW_MAP = {"MatchTime": ["Time"], "HomeTeam": ["Home"], "AwayTeam": ["Away"], "FTHome": ["HG"], "FTAway": ["AG"],
           "FTResult": ["Res"], "OddHome": ["AvgCH", "PSCH", "B365CH"], "OddDraw": ["AvgCD", "PSCD", "B365CD"],
           "OddAway": ["AvgCA", "PSCA", "B365CA"], "MaxHome": ["MaxCH"], "MaxDraw": ["MaxCD"], "MaxAway": ["MaxCA"]}
FORM_COLS = ("Form3Home", "Form5Home", "Form3Away", "Form5Away")


def convert_new_league(fd: pd.DataFrame, division: str, columns: list[str]) -> pd.DataFrame:
    """football-data "new league" satırları (oynanmış) arşiv düzeninde."""
    fd = fd.dropna(subset=["HG", "AG"])
    out = pd.DataFrame(index=fd.index, columns=columns)
    out["Division"] = division
    out["MatchDate"] = pd.to_datetime(fd["Date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    for col, src in NEW_MAP.items():
        have = next((s for s in src if s in fd.columns and fd[s].notna().any()), None)
        if have and col in out.columns:
            out[col] = fd[have]
    for c in ("HomeTeam", "AwayTeam"):
        out[c] = out[c].astype(str).str.strip()
    return _numeric(out).dropna(subset=["MatchDate"])


NUMERIC_COLS = ("FTHome", "FTAway", "HTHome", "HTAway", "HomeShots", "AwayShots", "HomeTarget", "AwayTarget",
                "HomeFouls", "AwayFouls", "HomeCorners", "AwayCorners", "HomeYellow", "AwayYellow", "HomeRed", "AwayRed",
                "OddHome", "OddDraw", "OddAway", "MaxHome", "MaxDraw", "MaxAway", "Over25", "Under25", "MaxOver25",
                "MaxUnder25", "HandiSize", "HandiHome", "HandiAway")


def _numeric(out: pd.DataFrame) -> pd.DataFrame:
    """Kaynak dosyadaki bozuk hücreler (ör. oran yerine 'x') boş bırakılır; sayısal sütunlara metin girmez."""
    for c in NUMERIC_COLS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _swap_day_month(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates, format="%Y-%m-%d", errors="coerce")
    ok = d.notna() & (d.dt.day <= 12)
    out = dates.astype(str).copy()
    out[ok] = d[ok].dt.year.astype(str) + "-" + d[ok].dt.day.map("{:02d}".format) + "-" + d[ok].dt.month.map("{:02d}".format)
    return out


def fill_form(base: pd.DataFrame, add: pd.DataFrame) -> pd.DataFrame:
    """Yeni satırların form sütunları: aynı ligde son 3/5 maç puanı (arşiv geçmişi + yeni satırlar, tarih sırasıyla)."""
    if not len(add) or not all(c in add.columns for c in FORM_COLS):
        return add
    add = add.copy()
    hist = pd.concat([base[["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "FTHome", "FTAway"]].assign(_new=-1),
                      add[["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "FTHome", "FTAway"]]
                      .assign(_new=range(len(add)))], ignore_index=True)
    hist["_t"] = hist["MatchTime"].astype(str)
    hist = hist.sort_values(["MatchDate", "_t"], kind="stable")
    pts: dict[tuple[str, str], list[int]] = defaultdict(list)
    vals = {c: [None] * len(add) for c in FORM_COLS}
    for div, h, a, fh, fa, new in zip(hist["Division"].astype(str), hist["HomeTeam"].astype(str),
                                      hist["AwayTeam"].astype(str), pd.to_numeric(hist["FTHome"], errors="coerce"),
                                      pd.to_numeric(hist["FTAway"], errors="coerce"), hist["_new"]):
        if new >= 0:
            ph, pa = pts[(div, h)], pts[(div, a)]
            vals["Form3Home"][new] = float(sum(ph[-3:]))
            vals["Form5Home"][new] = float(sum(ph[-5:]))
            vals["Form3Away"][new] = float(sum(pa[-3:]))
            vals["Form5Away"][new] = float(sum(pa[-5:]))
        if pd.isna(fh) or pd.isna(fa):
            continue
        p_h, p_a = (3, 0) if fh > fa else (0, 3) if fh < fa else (1, 1)
        pts[(div, h)].append(p_h)
        pts[(div, a)].append(p_a)
    for c in FORM_COLS:
        add[c] = vals[c]
    return add


def key(df: pd.DataFrame) -> pd.Series:
    return df["Division"].astype(str) + "|" + df["MatchDate"].astype(str) + "|" + df["HomeTeam"].astype(str) + "|" + \
        df["AwayTeam"].astype(str)


def update(archive: Path = ARCHIVE, seasons: Path = SEASONS, *, fill_form_cols: bool = True) -> int:
    base = pd.read_csv(archive, low_memory=False)
    seen = set(key(base))
    ext = base[base["Division"].isin(set(NEW_LEAGUES.values()))]
    if len(ext):  # eski ek lig satırlarında gün/ay ters okunmuş tarihler
        seen |= set(ext["Division"].astype(str) + "|" + _swap_day_month(ext["MatchDate"]) + "|" +
                    ext["HomeTeam"].astype(str) + "|" + ext["AwayTeam"].astype(str))
    new = []
    for f in sorted((seasons / "new_leagues").glob("*.csv")):
        div = NEW_LEAGUES.get(f.stem)
        if not div:
            continue
        try:
            fd = pd.read_csv(f, encoding="utf-8", on_bad_lines="skip")
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if not {"Date", "Home", "Away", "HG", "AG"} <= set(fd.columns):
            continue
        rows = convert_new_league(fd, div, list(base.columns))
        rows = rows[~key(rows).isin(seen)]
        seen |= set(key(rows))
        new.append(rows)
    for f in sorted(seasons.glob("season_*/*.csv")):
        try:
            fd = pd.read_csv(f, encoding="utf-8", on_bad_lines="skip")
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if not {"Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= set(fd.columns):
            continue
        rows = convert(fd, list(base.columns))
        rows = rows[~key(rows).isin(seen)]
        seen |= set(key(rows))
        new.append(rows)
    new = [x for x in new if len(x)]
    add = pd.concat(new, ignore_index=True) if new else pd.DataFrame(columns=base.columns)
    if len(add):  # appended at the end, the existing rows stay byte for byte as they are
        add = add.sort_values(["MatchDate", "Division"], kind="stable").reset_index(drop=True)
        if fill_form_cols:
            add = fill_form(base, add)
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
