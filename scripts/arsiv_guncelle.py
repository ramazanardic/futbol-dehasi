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
       "HandiAway": ["AvgAHA", "B365AHA"],
       # Pinnacle (28 Kas 2026; eski satırlar scripts/pinnacle_doldur.py ile geriye dolduruldu)
       "PSHome": ["PSH"], "PSDraw": ["PSD"], "PSAway": ["PSA"], "PSCHome": ["PSCH"], "PSCDraw": ["PSCD"],
       "PSCAway": ["PSCA"], "PSOver25": ["P>2.5"], "PSUnder25": ["P<2.5"], "PSCOver25": ["PC>2.5"],
       "PSCUnder25": ["PC<2.5"]}


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
           "OddAway": ["AvgCA", "PSCA", "B365CA"], "MaxHome": ["MaxCH"], "MaxDraw": ["MaxCD"], "MaxAway": ["MaxCA"],
           "PSCHome": ["PSCH"], "PSCDraw": ["PSCD"], "PSCAway": ["PSCA"]}
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
                "MaxUnder25", "HandiSize", "HandiHome", "HandiAway", "PSHome", "PSDraw", "PSAway", "PSCHome", "PSCDraw",
                "PSCAway", "PSOver25", "PSUnder25", "PSCOver25", "PSCUnder25")


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


# ESPN skor doldurma (28 Kas 2026): football-data bazı ligleri haftalarca güncellemiyor (P1 08 Kas'ta, RUS 02 Ağu'da
# kaldı). Bu ligler için data/arsiv/maclar.csv.gz'deki ESPN skorları (scripts/espn_lig_tara.py) football-data'nın son
# gününden SONRASI için eklenir: yalnız tarih, takımlar, tam skor; oran / İY / şut boş kalır, Source="espn".
# Aynı maç sonradan football-data'da çıkarsa (±1 gün, aynı takımlar) ESPN satırı silinip football-data satırı yazılır.
ARSIV_MACLAR = ROOT / "data" / "arsiv" / "maclar.csv.gz"
ESPN_ALIAS = {
    "P1": {"Braga": "Sp Braga", "C.D. Nacional": "Nacional", "FC Famalicao": "Famalicao", "FC Porto": "Porto",
           "Sporting CP": "Sp Lisbon", "Vitória de Guimaraes": "Guimaraes", "Vitoria de Guimaraes": "Guimaraes",
           "Académico de Viseu": "Academico Viseu", "Academico de Viseu": "Academico Viseu"},
    "RUS": {"Akron Tolyatti": "Akron Togliatti", "Dinamo Moscow": "Dynamo Moscow", "FC Baltika Kaliningrad": "Baltika",
            "Gazovik Orenburg": "Orenburg", "Krylia Sovetov": "Krylya Sovetov", "Nizhny Novgorod": "Pari NN",
            "Rostov": "FK Rostov", "Zenit St Petersburg": "Zenit"},
}
ESPN_FILL = {"P1": "espn/por.1", "RUS": "espn/rus.1"}


def _source(df: pd.DataFrame) -> pd.Series:
    return df["Source"].astype("string").fillna("").astype(str) if "Source" in df.columns else pd.Series("", index=df.index)


def espn_fill(base: pd.DataFrame, columns: list[str], maclar: Path = ARSIV_MACLAR) -> pd.DataFrame:
    """football-data'nın son gününden sonraki ESPN skorları (yalnız eşlenen takımlar) arşiv düzeninde."""
    if "Source" not in columns or not maclar.exists():
        return pd.DataFrame(columns=columns)
    a = pd.read_csv(maclar, low_memory=False, usecols=["tarih", "yarisma", "ev", "dep", "hg", "ag", "durum"])
    a = a[a.yarisma.isin(set(ESPN_FILL.values())) & a.durum.isin(["FT", "AET", "PEN"])].dropna(subset=["hg", "ag"])
    fd = base[_source(base) == ""]
    out = []
    for div, comp in ESPN_FILL.items():
        mine = fd[fd["Division"] == div]
        if mine.empty:
            continue
        last = str(mine["MatchDate"].max())
        recent = mine[mine["MatchDate"] >= f"{int(last[:4]) - 1}{last[4:]}"]
        known = set(recent["HomeTeam"].astype(str)) | set(recent["AwayTeam"].astype(str))
        alias = ESPN_ALIAS.get(div, {})
        x = a[(a.yarisma == comp) & (a.tarih.astype(str) > last)]
        for t, ev, dep, hg, ag in zip(x.tarih, x.ev, x.dep, x.hg, x.ag):
            h, w = alias.get(ev, ev), alias.get(dep, dep)
            if h not in known or w not in known:
                continue  # eşlenemeyen takım: satır yazılmaz (uydurma eşleşme yok)
            hg, ag = int(hg), int(ag)
            out.append({"Division": div, "MatchDate": str(t), "HomeTeam": h, "AwayTeam": w, "FTHome": hg, "FTAway": ag,
                        "FTResult": "H" if hg > ag else "A" if hg < ag else "D", "Source": "espn"})
    return pd.DataFrame(out, columns=columns) if out else pd.DataFrame(columns=columns)


def _near_keys(df: pd.DataFrame) -> pd.Series:
    """±1 gün toleranslı eşleşme için (lig, ev, dep, gün sayısı)."""
    d = pd.to_datetime(df["MatchDate"], errors="coerce")
    return df["Division"].astype(str) + "|" + df["HomeTeam"].astype(str) + "|" + df["AwayTeam"].astype(str), d


def _drop_lines(archive: Path, drop: set[int]) -> None:
    """Veri satırı indekslerini (0 tabanlı) metin düzeyinde siler; diğer satırlar bayt bayt aynı kalır."""
    lines = archive.read_text(encoding="utf-8").split("\n")
    keep = [lines[0]] + [ln for i, ln in enumerate(lines[1:]) if i not in drop]
    archive.write_text("\n".join(keep), encoding="utf-8")


def update(archive: Path = ARCHIVE, seasons: Path = SEASONS, *, fill_form_cols: bool = True,
           maclar: Path = ARSIV_MACLAR) -> int:
    base = pd.read_csv(archive, low_memory=False)
    src = _source(base)
    is_espn = src == "espn"
    seen = set(key(base[~is_espn]))
    ext = base[base["Division"].isin(set(NEW_LEAGUES.values())) & ~is_espn]
    if len(ext):  # eski ek lig satırlarında gün/ay ters okunmuş tarihler
        seen |= set(ext["Division"].astype(str) + "|" + _swap_day_month(ext["MatchDate"]) + "|" +
                    ext["HomeTeam"].astype(str) + "|" + ext["AwayTeam"].astype(str))
    espn_rows = base[is_espn]
    ek, ed = _near_keys(espn_rows)
    espn_by_pair: dict[str, list[tuple[int, pd.Timestamp]]] = defaultdict(list)
    for i, k, d in zip(espn_rows.index, ek, ed):
        espn_by_pair[k].append((i, d))
    replaced: set[int] = set()

    def _take(rows: pd.DataFrame) -> pd.DataFrame:
        rows = rows[~key(rows).isin(seen)]
        rows = rows[~key(rows).duplicated()]
        seen.update(key(rows))
        rk, rd = _near_keys(rows)
        for k, d in zip(rk, rd):
            for i, d0 in espn_by_pair.get(k, []):
                if pd.notna(d) and pd.notna(d0) and abs((d - d0).days) <= 1:
                    replaced.add(i)
        return rows

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
        new.append(_take(convert_new_league(fd, div, list(base.columns))))
    for f in sorted(seasons.glob("season_*/*.csv")):
        try:
            fd = pd.read_csv(f, encoding="utf-8", on_bad_lines="skip")
        except (OSError, ValueError, pd.errors.ParserError):
            continue
        if not {"Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= set(fd.columns):
            continue
        new.append(_take(convert(fd, list(base.columns))))
    # ESPN: football-data'da olmayan, mevcut ESPN satırı da olmayan maçlar
    kept_base = base.drop(index=list(replaced))
    es = espn_fill(kept_base, list(base.columns), maclar)
    if len(es):
        fd_pairs = defaultdict(list)
        for x in [kept_base[_source(kept_base) == ""], *[y for y in new if len(y)]]:
            xk, xd = _near_keys(x)
            for k, d in zip(xk, xd):
                fd_pairs[k].append(d)
        have_espn = set(key(kept_base[_source(kept_base) == "espn"]))
        sk, sd = _near_keys(es)
        ok = [key(es).iloc[j] not in have_espn and not any(pd.notna(d0) and abs((d - d0).days) <= 1 for d0 in fd_pairs.get(k, []))
              for j, (k, d) in enumerate(zip(sk, sd))]
        new.append(es[ok])
    new = [x for x in new if len(x)]
    add = pd.concat(new, ignore_index=True) if new else pd.DataFrame(columns=base.columns)
    if replaced:
        _drop_lines(archive, {base.index.get_loc(i) for i in replaced})
    if len(add):  # appended at the end, the existing rows stay byte for byte as they are
        add = add.sort_values(["MatchDate", "Division"], kind="stable").reset_index(drop=True)
        if fill_form_cols:
            add = fill_form(kept_base, add)
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
