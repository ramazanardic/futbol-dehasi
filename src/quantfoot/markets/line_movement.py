"""Sharp line-movement (steam) intelligence and sharp-vs-soft bookmaker lag arbitrage engine.

Implements Roadmap items P1-4 (Kaunitz et al. 2017 sharp-soft price discrepancy) and P1-8
(opening-to-closing probability & log-odds velocity analysis):
  - ``analyze_line_movement``: computes opening-to-live probability shift, log-odds velocity,
    directional alignment (``aligned`` / ``against`` / ``neutral``), and volatility flags.
  - ``sharp_soft_edge``: evaluates soft-book price lag against devigged sharp fair probabilities
    with overround-aware plausibility bounds.
  - ``backtest_sharp_soft_and_steam``: reproducible out-of-sample empirical audit on
    ``data/tipsaudit.csv`` measuring ROI, CLV, hit rate, and t-statistics across EV tiers
    and steam-alignment buckets.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.stats import t as student_t

from quantfoot.markets.devig import DevigMethod, devig, devig_batch


@dataclass(frozen=True)
class LineMovementSignal:
    """Quantitative summary of sharp opening-to-live line movement for a specific selection."""

    p_open: float
    p_live: float
    delta_p: float
    delta_logit: float
    max_market_move: float
    direction: str  # "aligned" | "against" | "neutral"
    strong_steam: bool
    chaotic_market: bool


@dataclass(frozen=True)
class SharpSoftEdge:
    """Soft-book mispricing edge measured against a devigged sharp reference price."""

    p_sharp: float
    soft_odds: float
    fair_odds: float
    ev: float
    kelly_quarter: float
    is_plausible_edge: bool


def _logit(p: float) -> float:
    pc = float(np.clip(p, 1e-6, 1.0 - 1e-6))
    return math.log(pc / (1.0 - pc))


def analyze_line_movement(
    open_odds: Sequence[float],
    live_odds: Sequence[float],
    outcome_idx: int,
    *,
    method: DevigMethod = "power",
    align_threshold_pp: float = 0.02,
    strong_threshold_pp: float = 0.05,
) -> LineMovementSignal:
    """Compare opening vs live sharp odds to quantify steam velocity and directional alignment."""
    p_open_vec = devig(list(open_odds), method=method).probabilities
    p_live_vec = devig(list(live_odds), method=method).probabilities
    if not (0 <= outcome_idx < len(p_open_vec)) or len(p_open_vec) != len(p_live_vec):
        raise ValueError("Invalid outcome_idx or mismatched open/live odds lengths.")

    po = float(p_open_vec[outcome_idx])
    pl = float(p_live_vec[outcome_idx])
    dp = pl - po
    dl = _logit(pl) - _logit(po)
    max_move = float(np.max(np.abs(p_live_vec - p_open_vec)))

    if dp >= align_threshold_pp:
        direction = "aligned"
    elif dp <= -align_threshold_pp:
        direction = "against"
    else:
        direction = "neutral"

    return LineMovementSignal(
        p_open=round(po, 5),
        p_live=round(pl, 5),
        delta_p=round(dp, 5),
        delta_logit=round(dl, 5),
        max_market_move=round(max_move, 5),
        direction=direction,
        strong_steam=abs(dp) >= strong_threshold_pp,
        chaotic_market=max_move >= 0.06,
    )


def sharp_soft_edge(
    sharp_odds: Sequence[float],
    soft_odds: float,
    outcome_idx: int,
    *,
    method: DevigMethod = "power",
    min_ev: float = 0.02,
    max_plausible_ev: float = 0.25,
) -> SharpSoftEdge:
    """Measure soft-book EV and quarter-Kelly fraction against a devigged sharp price."""
    probs = devig(list(sharp_odds), method=method).probabilities
    p_s = float(probs[outcome_idx])
    so = float(soft_odds)
    if so <= 1.0:
        raise ValueError(f"soft_odds must exceed 1.0, got {so}")
    ev = p_s * so - 1.0
    b = so - 1.0
    f_q = max(0.0, 0.25 * ev / b) if ev > 0.0 else 0.0
    return SharpSoftEdge(
        p_sharp=round(p_s, 5),
        soft_odds=round(so, 4),
        fair_odds=round(1.0 / max(p_s, 1e-9), 4),
        ev=round(ev, 5),
        kelly_quarter=round(min(f_q, 0.03), 5),
        is_plausible_edge=bool(min_ev <= ev <= max_plausible_ev),
    )


def _summarize_bets(profits: list[float], clvs: list[float], hits: list[int]) -> dict[str, Any]:
    n = len(profits)
    if n == 0:
        return {"n": 0, "roi": 0.0, "hit_rate": 0.0, "mean_clv": 0.0, "t_stat": 0.0, "p_value_one_sided": 1.0}
    arr = np.asarray(profits, dtype=float)
    roi = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    t_val = (roi / (std / math.sqrt(n))) if (n > 1 and std > 1e-12) else 0.0
    p_one = float(student_t.sf(t_val, df=n - 1)) if n > 1 else 0.5
    return {
        "n": n,
        "roi": round(roi, 5),
        "hit_rate": round(float(np.mean(hits)), 5),
        "mean_clv": round(float(np.mean(clvs)), 5),
        "t_stat": round(t_val, 3),
        "p_value_one_sided": round(p_one, 5),
    }


def backtest_sharp_soft_and_steam(
    tipsaudit_csv: Path | str,
    *,
    method: DevigMethod = "power",
    ev_thresholds: Sequence[float] = (0.01, 0.02, 0.03, 0.05),
    max_plausible_ev: float = 0.25,
) -> dict[str, Any]:
    """Empirical backtest of sharp-vs-soft pricing lag and steam direction on ``data/tipsaudit.csv``.

    For every match, compares opening devigged Pinnacle probabilities against ``best_soft_*``
    odds (1X2 sides) and evaluates both overall sharp-soft EV tiers and breakdown by
    subsequent Pinnacle opening-to-closing steam direction.
    """
    path = Path(tipsaudit_csv)
    if not path.exists():
        raise FileNotFoundError(f"tipsaudit CSV not found: {path}")

    open_rows: list[list[float]] = []
    close_rows: list[list[float]] = []
    soft_rows: list[list[float]] = []
    outcomes: list[int] = []
    res_map = {"1": 0, "X": 1, "2": 2}

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            res = (row.get("result") or "").strip().upper()
            if res not in res_map or (row.get("void_reason") or "").strip():
                continue
            try:
                oo = [float(row["pin_open_home"]), float(row["pin_open_draw"]), float(row["pin_open_away"])]
                co = [float(row["pin_close_home"]), float(row["pin_close_draw"]), float(row["pin_close_away"])]
                so = [float(row["best_soft_home"]), float(row["best_soft_draw"]), float(row["best_soft_away"])]
            except (KeyError, TypeError, ValueError):
                continue
            if min(oo) <= 1.01 or min(co) <= 1.01 or min(so) <= 1.01:
                continue
            open_rows.append(oo)
            close_rows.append(co)
            soft_rows.append(so)
            outcomes.append(res_map[res])

    p_open = devig_batch(np.asarray(open_rows, dtype=float), method=method)
    p_close = devig_batch(np.asarray(close_rows, dtype=float), method=method)
    soft_arr = np.asarray(soft_rows, dtype=float)
    y_arr = np.asarray(outcomes, dtype=int)

    ev_mat = p_open * soft_arr - 1.0
    clv_mat = p_close * soft_arr - 1.0
    dp_mat = p_close - p_open

    tier_results: dict[str, dict[str, Any]] = {}
    for thr in ev_thresholds:
        profits: list[float] = []
        clvs: list[float] = []
        hits: list[int] = []
        for i in range(len(y_arr)):
            # At most one best +EV 1X2 side per match to prevent intra-match correlation.
            k = int(np.argmax(ev_mat[i]))
            ev = float(ev_mat[i, k])
            if thr <= ev <= max_plausible_ev:
                won = int(y_arr[i] == k)
                profits.append((float(soft_arr[i, k]) - 1.0) if won else -1.0)
                clvs.append(float(clv_mat[i, k]))
                hits.append(won)
        tier_results[f"ev>={int(round(thr * 100))}%"] = _summarize_bets(profits, clvs, hits)

    # Steam direction diagnostic on opening soft-edge candidates (EV >= 2%):
    steam_buckets: dict[str, tuple[list[float], list[float], list[int]]] = {
        "steam_aligned (>=+2pp)": ([], [], []),
        "steam_neutral (-2pp..+2pp)": ([], [], []),
        "steam_against (<=-2pp)": ([], [], []),
    }
    for i in range(len(y_arr)):
        k = int(np.argmax(ev_mat[i]))
        ev = float(ev_mat[i, k])
        if not (0.02 <= ev <= max_plausible_ev):
            continue
        dp = float(dp_mat[i, k])
        won = int(y_arr[i] == k)
        prof = (float(soft_arr[i, k]) - 1.0) if won else -1.0
        clv = float(clv_mat[i, k])
        if dp >= 0.02:
            bkey = "steam_aligned (>=+2pp)"
        elif dp <= -0.02:
            bkey = "steam_against (<=-2pp)"
        else:
            bkey = "steam_neutral (-2pp..+2pp)"
        steam_buckets[bkey][0].append(prof)
        steam_buckets[bkey][1].append(clv)
        steam_buckets[bkey][2].append(won)

    return {
        "n_matches": int(len(y_arr)),
        "devig_method": method,
        "sharp_soft_ev_tiers": tier_results,
        "steam_direction_on_ev2pct": {k: _summarize_bets(*v) for k, v in steam_buckets.items()},
    }
