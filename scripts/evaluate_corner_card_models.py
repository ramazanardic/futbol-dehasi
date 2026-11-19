"""Walk-forward check: do team corner / card ratings beat the league-average baseline?

Ratings are updated causally from 2018-07 onward; matches from --test-from are scored
before their own update (no look-ahead). Metric: binary log-loss per market line.

    python scripts/evaluate_corner_card_models.py [--test-from 2023-07-01]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from quantfoot.markets.corners_cards import CardDistribution, CornerCardRatings, CornerDistribution, league_baseline

ROOT = Path(__file__).resolve().parents[1]
CORNER_LINES = ["Korner 8.5 Üst", "Korner 9.5 Üst", "Korner 10.5 Üst", "Ev Korner 4.5 Üst", "Dep Korner 4.5 Üst", "Korner 1"]
CARD_LINES = ["Kart 3.5 Üst", "Kart 4.5 Üst", "Ev Kart 1.5 Üst", "Kırmızı Kart Var"]


def _outcome(name: str, hc: int, ac: int, hy: int, ay: int, hr: int, ar: int) -> bool:
    return {
        "Korner 8.5 Üst": hc + ac > 8.5, "Korner 9.5 Üst": hc + ac > 9.5, "Korner 10.5 Üst": hc + ac > 10.5,
        "Ev Korner 4.5 Üst": hc > 4.5, "Dep Korner 4.5 Üst": ac > 4.5, "Korner 1": hc > ac,
        "Kart 3.5 Üst": hy + ay + hr + ar > 3.5, "Kart 4.5 Üst": hy + ay + hr + ar > 4.5,
        "Ev Kart 1.5 Üst": hy + hr > 1.5, "Kırmızı Kart Var": hr + ar >= 1,
    }[name]


def _ll(p: float, y: bool) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -np.log(p if y else 1 - p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-from", default="2023-07-01")
    ap.add_argument("--alphas", default="0.03,0.06,0.10")
    args = ap.parse_args()

    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"])
    cols = ["HomeCorners", "AwayCorners", "HomeYellow", "AwayYellow", "HomeRed", "AwayRed"]
    df = df[df.MatchDate >= "2018-07-01"].dropna(subset=cols).sort_values("MatchDate").reset_index(drop=True)
    test_mask = df.MatchDate >= args.test_from
    print(f"maç: {len(df)} | test ({args.test_from}+): {int(test_mask.sum())}")

    base_cache: dict[str, tuple[CornerDistribution, CardDistribution]] = {}
    results: dict[str, dict[str, list[float]]] = {"lig ortalaması": {k: [] for k in CORNER_LINES + CARD_LINES}}
    alphas = [float(a) for a in args.alphas.split(",")]
    raters = {a: CornerCardRatings(alpha=a) for a in alphas}
    for a in alphas:
        results[f"rating α={a}"] = {k: [] for k in CORNER_LINES + CARD_LINES}

    for row in df.itertuples(index=False):
        hc, ac, hy, ay, hr, ar = (int(getattr(row, c)) for c in cols)
        div = row.Division
        if row.MatchDate >= pd.Timestamp(args.test_from):
            if div not in base_cache:
                b = league_baseline(div)
                base_cache[div] = (CornerDistribution.from_expectations(b[0], b[1], div), CardDistribution.for_division(div))
            bc, bk = base_cache[div]
            for name in CORNER_LINES:
                results["lig ortalaması"][name].append(_ll(bc.prob(name), _outcome(name, hc, ac, hy, ay, hr, ar)))
            for name in CARD_LINES:
                results["lig ortalaması"][name].append(_ll(bk.prob(name), _outcome(name, hc, ac, hy, ay, hr, ar)))
            for a, rt in raters.items():
                e = rt.expected(row.HomeTeam, row.AwayTeam, div)
                cdist = CornerDistribution.from_expectations(e["corners_home"], e["corners_away"], div)
                b = league_baseline(div)
                kdist = CardDistribution.from_expectations(e["yellow_home"], e["yellow_away"], e["red_home"], e["red_away"], b[6])
                for name in CORNER_LINES:
                    results[f"rating α={a}"][name].append(_ll(cdist.prob(name), _outcome(name, hc, ac, hy, ay, hr, ar)))
                for name in CARD_LINES:
                    results[f"rating α={a}"][name].append(_ll(kdist.prob(name), _outcome(name, hc, ac, hy, ay, hr, ar)))
        for rt in raters.values():
            rt.update(row.HomeTeam, row.AwayTeam, div, hc, ac, hy, ay)

    names = CORNER_LINES + CARD_LINES
    print("\nLog-loss (düşük = iyi)\n" + "model".ljust(18) + "".join(n[:16].rjust(18) for n in names))
    for model, res in results.items():
        print(model.ljust(18) + "".join(f"{np.mean(res[n]):18.5f}" for n in names))


if __name__ == "__main__":
    main()
