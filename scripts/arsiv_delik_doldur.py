"""data/matches.csv'deki sezon deliklerini football-data.co.uk sezon dosyalarından kapatır (28 Kas 2026, veri kapsam Faz 2).

Girdi: indirilmiş ``mmz_<sezon>_<div>.csv`` dosyaları (football-data.co.uk/mmz4281/<sezon>/<div>.csv; ücretsiz araştırma
verisi, atıf: www.football-data.co.uk). Arşivde OLMAYAN maç = aynı lig, ±1 gün, harf/rakam dışı atılmış takım adları
eşleşmiyor VE aynı gün aynı skorlu maç yok. Bunlar arsiv_guncelle.convert ile arşiv düzenine çevrilip sona eklenir
(eski satırlar bayt bayt aynı); form arşivin kendi tanımıyla doldurulur, Elo boş kalır. 28 Kas tespiti: G1 2011/12,
2022/23, 2023/24 tamamen; G1 2024/25 77, EC 2024/25 372, SC0–SC3 / T1 2024/25 sezon sonu maçları eksikti.

    python scripts/arsiv_delik_doldur.py --ham /workspace/fd_hist
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import arsiv_guncelle as ag
import pinnacle_doldur as pdl


def missing_rows(base: pd.DataFrame, files: list[Path]) -> pd.DataFrame:
    d = pd.to_datetime(base["MatchDate"], errors="coerce")
    keys, scores = set(), set()
    for div, day, h, a, fh, fa in zip(base["Division"], d, base["HomeTeam"], base["AwayTeam"], base["FTHome"], base["FTAway"]):
        if pd.isna(day):
            continue
        for k in (-1, 0, 1):
            keys.add((div, (day + pd.Timedelta(days=k)).strftime("%Y-%m-%d"), pdl.norm(h), pdl.norm(a)))
        if pd.notna(fh) and pd.notna(fa):
            scores.add((div, day.strftime("%Y-%m-%d"), int(fh), int(fa)))
    out = []
    for f in files:
        text = f.read_bytes().decode("utf-8-sig", errors="replace")
        try:
            fd = pd.read_csv(io.StringIO(text), on_bad_lines="skip")
        except (ValueError, pd.errors.ParserError):
            continue
        if not {"Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"} <= set(fd.columns):
            continue
        fd = fd.dropna(subset=["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
        fd["Date"] = fd["Date"].astype(str).map(lambda s: pdl._date(s) or "")
        fd = fd[fd["Date"] != ""]
        miss = [not ((dv, dt_, pdl.norm(h), pdl.norm(a)) in keys or (dv, dt_, int(fh), int(fa)) in scores)
                for dv, dt_, h, a, fh, fa in zip(fd["Div"], fd["Date"], fd["HomeTeam"], fd["AwayTeam"], fd["FTHG"], fd["FTAG"])]
        fd = fd[miss]
        if len(fd):
            fd = fd.assign(Date=pd.to_datetime(fd["Date"]).dt.strftime("%d/%m/%Y"))
            out.append(ag.convert(fd, list(base.columns)))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=base.columns)


def run(archive: Path, files: list[Path]) -> dict:
    base = pd.read_csv(archive, low_memory=False)
    add = missing_rows(base, files)
    if len(add):
        add = add.sort_values(["MatchDate", "Division"], kind="stable").reset_index(drop=True)
        add = ag.fill_form(base, add)
        with archive.open("a", encoding="utf-8", newline="") as fh:
            add.to_csv(fh, index=False, header=False, lineterminator="\n")
    return {"eklenen": len(add), **({"lig_sezon": add.groupby(["Division", add["MatchDate"].str[:4]]).size()
                                     .to_dict().items()} if len(add) else {})}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ham", type=Path, required=True)
    ap.add_argument("--arsiv", type=Path, default=ag.ARCHIVE)
    a = ap.parse_args()
    print(run(a.arsiv, sorted(a.ham.glob("mmz_*.csv"))))


if __name__ == "__main__":
    main()
