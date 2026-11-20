"""Club Elo as one more independent view of 1X2 bets (user request, 21 Nov).

* Ratings: api.clubelo.com (free, Europe's top ~2 divisions, daily) is not reachable from Turkey, so the global-odds
  workflow saves today's table to data/global_odds/latest/clubelo.csv (``fetch`` below, run on GitHub's servers).
* Elo difference -> probability: measured, not assumed — on the archive data/matches.csv (pre-match HomeElo /
  AwayElo and results of ~240k matches) the home-win / draw / away-win frequencies are tabulated per 25-point bin of
  (home Elo - away Elo) and smoothed; ``python scripts/elo_gorus.py --kalibre`` writes data/calibration/elo_1x2.json.
* View: MS 1 / MS 0 / MS 2, ÇŞ 1X / 12 / X2 probability of a Nesine match whose two clubs are in today's table.

    python scripts/elo_gorus.py --kalibre      # rebuild the Elo -> 1X2 table from the archive
    python scripts/elo_gorus.py --cek          # (cloud) save today's Club Elo table
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RATINGS = ROOT / "data" / "global_odds" / "latest" / "clubelo.csv"
TABLE = ROOT / "data" / "calibration" / "elo_1x2.json"
ARCHIVE = ROOT / "data" / "matches.csv"
BIN = 25
CLIP = 600
MIN_BIN = 200


def fetch(day: dt.date | None = None, out: Path = RATINGS) -> int:
    import requests
    import time
    day = day or dt.date.today()
    r = None
    for back in (0, 1, 2):  # the API answered 502 on 20 Nov: retry, then fall back to the previous days' table
        for wait in (0, 20):
            time.sleep(wait)
            try:
                r = requests.get(f"http://api.clubelo.com/{(day - dt.timedelta(days=back)).isoformat()}", timeout=60)
            except requests.RequestException:
                continue
            if r.status_code == 200 and r.text.startswith("Rank,Club"):
                break
        if r is not None and r.status_code == 200 and r.text.startswith("Rank,Club"):
            break
    if r is None or r.status_code != 200 or not r.text.startswith("Rank,Club"):
        raise RuntimeError(f"Club Elo unavailable (HTTP {getattr(r, 'status_code', '-')})")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(r.text, encoding="utf-8")
    return max(0, len(r.text.splitlines()) - 1)


def calibrate(archive: Path = ARCHIVE, out: Path = TABLE) -> dict:
    import pandas as pd
    d = pd.read_csv(archive, low_memory=False, usecols=["HomeElo", "AwayElo", "FTResult"]).dropna()
    d = d[d["FTResult"].isin(["H", "D", "A"])]
    diff = (d["HomeElo"] - d["AwayElo"]).clip(-CLIP, CLIP)
    b = (diff / BIN).round().astype(int) * BIN
    rows = {}
    for k, g in d.groupby(b):
        if len(g) >= MIN_BIN:
            rows[int(k)] = [float((g["FTResult"] == x).mean()) for x in ("H", "D", "A")] + [int(len(g))]
    table = {"bin": BIN, "n": int(len(d)), "rows": {str(k): v for k, v in sorted(rows.items())}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(table, indent=1), encoding="utf-8")
    return table


@lru_cache(maxsize=1)
def _table() -> tuple[np.ndarray, np.ndarray] | None:
    if not TABLE.exists():
        return None
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    ks = sorted(int(k) for k in t["rows"])
    return np.array(ks, dtype=float), np.array([t["rows"][str(k)][:3] for k in ks])


def probs_1x2(diff: float) -> tuple[float, float, float] | None:
    """(home, draw, away) for a pre-match Elo difference, interpolated on the measured table."""
    t = _table()
    if t is None:
        return None
    ks, p = t
    x = float(np.clip(diff, ks[0], ks[-1]))
    v = [float(np.interp(x, ks, p[:, i])) for i in range(3)]
    s = sum(v)
    return v[0] / s, v[1] / s, v[2] / s


@lru_cache(maxsize=1)
def ratings() -> dict[str, float]:
    if not RATINGS.exists():
        return {}
    with RATINGS.open(encoding="utf-8") as fh:
        return {r["Club"]: float(r["Elo"]) for r in csv.DictReader(fh) if r.get("Elo")}


def match_view(m: dict) -> dict | None:
    """{name: probability} for the 1X2 / double-chance bets of a Nesine match, or None (club not rated)."""
    import wiki_gecmis as wg  # lazy: the cloud fetch needs only requests
    rt = ratings()
    if not rt:
        return None
    names = {k: k for k in rt}
    h, a = wg.match_team(m["home"], names), wg.match_team(m["away"], names)
    if not h or not a or h == a:
        return None
    p = probs_1x2(rt[h] - rt[a])
    if p is None:
        return None
    p1, px, p2 = p
    return {"MS 1": p1, "MS 0": px, "MS 2": p2, "ÇŞ 1X": p1 + px, "ÇŞ 12": p1 + p2, "ÇŞ X2": px + p2,
            "_clubs": f"{h} {rt[h]:.0f} – {a} {rt[a]:.0f}"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kalibre", action="store_true")
    ap.add_argument("--cek", action="store_true")
    args = ap.parse_args()
    if args.kalibre:
        t = calibrate()
        print(f"Elo -> 1X2 tablosu: {t['n']} maç, {len(t['rows'])} aralık -> {TABLE}")
    if args.cek:
        print(f"Club Elo: {fetch()} kulüp -> {RATINGS}")


if __name__ == "__main__":
    main()
