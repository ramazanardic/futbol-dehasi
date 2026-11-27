"""League half-time base rates from the user's GLOBAL FOOTBALL INTELLIGENCE archive (user request, 26 Nov).

That project keeps openfootball/football.json (CC0 public domain) for 40+ leagues and several seasons in
state/gfi.sqlite3. This script only reads it (SQLite read-only mode) and writes, per league file code (en.1, tr.1 …):

    n, İY 1/0/2, 2Y 1/0/2, the nine İY/MS and nine İY/2Y combos, İY 0-0, goal in both halves, both-halves BTTS

to data/lig_yari_oranlari.csv. These are league priors for half bets, not team ratings.

    python scripts/gfi_yari_oranlari.py [--db PATH]
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path.home() / "Desktop" / "GLOBAL FOOTBALL INTELLIGENCE" / "state" / "gfi.sqlite3"
OUT = ROOT / "data" / "lig_yari_oranlari.csv"
RES = ("1", "0", "2")


def res(h: int, a: int) -> str:
    return "1" if h > a else "2" if h < a else "0"


def halves(payload: dict, hg: int, ag: int) -> tuple[int, int, int, int] | None:
    """(İY ev, İY dep, 2Y ev, 2Y dep) or None when the half score is missing or contradicts the full time."""
    score = payload.get("score")
    ht = score.get("ht") if isinstance(score, dict) else None
    if not isinstance(ht, list) or len(ht) != 2 or any(type(x) is not int or x < 0 for x in ht):
        return None
    if ht[0] > hg or ht[1] > ag:
        return None
    return ht[0], ht[1], hg - ht[0], ag - ht[1]


def league_rates(rows) -> dict[str, dict[str, float]]:
    """rows: (league code, home goals, away goals, payload dict) -> rates per league."""
    c: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for code, hg, ag, payload in rows:
        v = halves(payload, hg, ag)
        if v is None:
            continue
        h1, a1, h2, a2 = v
        k = c[code]
        r1, r2, rf = res(h1, a1), res(h2, a2), res(hg, ag)
        k["n"] += 1
        k["g1"] += h1 + a1
        k["g"] += hg + ag
        k["iy" + r1] += 1
        k["2y" + r2] += 1
        k[f"iyms_{r1}/{rf}"] += 1
        k[f"iy2y_{r1}/{r2}"] += 1
        k["iy00"] += (h1 + a1 == 0)
        k["gol_iki_yari"] += (h1 + a1 > 0 and h2 + a2 > 0)
        k["kg_iki_yari"] += (min(h1, a1) > 0 and min(h2, a2) > 0)
    cols = ([f"iy{r}" for r in RES] + [f"2y{r}" for r in RES] + [f"iyms_{x}/{y}" for x in RES for y in RES]
            + [f"iy2y_{x}/{y}" for x in RES for y in RES] + ["iy00", "gol_iki_yari", "kg_iki_yari"])
    return {code: {"n": k["n"], "gol": round(k["g"] / k["n"], 4),
                   "iy_gol_payi": round(k["g1"] / k["g"], 4) if k["g"] else "",
                   **{col: round(k[col] / k["n"], 4) for col in cols}} for code, k in c.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    db = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    q = """SELECT s.path, o.home_goals, o.away_goals, o.payload FROM latest_matches o
           JOIN snapshots s ON s.checksum = o.checksum
           WHERE o.home_goals IS NOT NULL AND o.away_goals IS NOT NULL AND s.path LIKE '%.json'"""
    rows = ((path.rsplit("/", 1)[-1][:-5], hg, ag, json.loads(p)) for path, hg, ag, p in db.execute(q))
    rates = league_rates(rows)
    db.close()
    fields = ["lig"] + list(next(iter(rates.values())).keys())
    with OUT.open("w", newline="", encoding="utf-8") as f:
        f.write("# openfootball/football.json (CC0), GLOBAL FOOTBALL INTELLIGENCE arşivinden; yarı taban oranları\n")
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for code in sorted(rates):
            w.writerow({"lig": code, **rates[code]})
    total = sum(r["n"] for r in rates.values())
    print(f"{len(rates)} lig, {total} maç -> {OUT}")


if __name__ == "__main__":
    main()
