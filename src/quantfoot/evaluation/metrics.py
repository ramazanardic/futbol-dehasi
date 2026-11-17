"""Strictly proper scoring rules, calibration diagnostics, and betting risk-return metrics."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm
from sklearn.metrics import log_loss

from quantfoot.strategy.kelly import kelly_fraction


def multiclass_log_loss(probs: np.ndarray, y_idx: np.ndarray) -> float:
    """Compute multi-class cross-entropy log-loss."""
    labels = list(range(probs.shape[1]))
    return float(log_loss(y_idx, probs, labels=labels))


def ranked_probability_score(probs: np.ndarray, y_idx: np.ndarray) -> float:
    """Compute Ranked Probability Score (Constantinou & Fenton, 2012) for ordinal outcomes."""
    n, k = probs.shape
    y_oh = np.zeros((n, k), dtype=float)
    y_oh[np.arange(n), y_idx] = 1.0
    cum_p = np.cumsum(probs, axis=1)[:, :-1]
    cum_y = np.cumsum(y_oh, axis=1)[:, :-1]
    return float(np.mean(0.5 * np.sum((cum_p - cum_y) ** 2, axis=1)))


def multiclass_brier(probs: np.ndarray, y_idx: np.ndarray) -> float:
    """Compute multi-class Brier score."""
    n, k = probs.shape
    y_oh = np.zeros((n, k), dtype=float)
    y_oh[np.arange(n), y_idx] = 1.0
    return float(np.mean(np.sum((probs - y_oh) ** 2, axis=1)))


def classwise_ece(probs: np.ndarray, y_idx: np.ndarray, n_bins: int = 10) -> float:
    """Compute mean classwise Expected Calibration Error (ECE)."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece_total = 0.0
    for c in range(probs.shape[1]):
        p_c = probs[:, c]
        y_c = (y_idx == c).astype(float)
        ece_c = 0.0
        for b in range(n_bins):
            if b == n_bins - 1:
                mask = (p_c >= bins[b]) & (p_c <= bins[b + 1])
            else:
                mask = (p_c >= bins[b]) & (p_c < bins[b + 1])
            if np.any(mask):
                ece_c += (float(np.sum(mask)) / len(p_c)) * abs(float(np.mean(y_c[mask])) - float(np.mean(p_c[mask])))
        ece_total += ece_c
    return float(ece_total / probs.shape[1])


def betting_metrics(returns: np.ndarray, odds_taken: np.ndarray | None = None) -> dict[str, float]:
    """Compute ROI, hit rate, t-statistic, one-sided p-value, and per-bet Sharpe."""
    n = len(returns)
    if n == 0:
        return {"bets": 0, "win_rate": 0.0, "avg_odds": 0.0, "roi": 0.0, "t_stat": 0.0, "p_value": 1.0, "sharpe_per_bet": 0.0}

    roi = float(np.mean(returns))
    std = float(np.std(returns, ddof=1)) if n > 1 else 0.0
    t_stat = (roi / (std / math.sqrt(n))) if std > 1e-12 else 0.0
    p_val = float(1.0 - norm.cdf(t_stat)) if std > 1e-12 else 1.0
    sharpe = (roi / std) if std > 1e-12 else 0.0
    avg_odd = float(np.mean(odds_taken)) if odds_taken is not None and len(odds_taken) == n else 0.0

    return {
        "bets": int(n),
        "win_rate": float(np.mean(returns > 0.0)),
        "avg_odds": avg_odd,
        "roi": roi,
        "t_stat": float(t_stat),
        "p_value": p_val,
        "sharpe_per_bet": float(sharpe),
    }


def simulate_kelly_equity(
    probs: np.ndarray,
    odds: np.ndarray,
    won: np.ndarray,
    initial_bankroll: float = 1000.0,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
) -> dict[str, object]:
    """Simulate chronological fractional Kelly bankroll trajectory and max drawdown."""
    bank = float(initial_bankroll)
    peak = bank
    max_dd = 0.0
    curve = [bank]

    for p, o, w in zip(probs, odds, won):
        f = kelly_fraction(float(p), float(o), multiplier=kelly_mult, max_stake=max_stake)
        if f <= 0.0:
            continue
        stake = bank * f
        bank += stake * (float(o) - 1.0) if bool(w) else -stake
        peak = max(peak, bank)
        dd = (peak - bank) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        curve.append(bank)

    return {
        "initial_bankroll": initial_bankroll,
        "final_bankroll": float(bank),
        "total_return_pct": float((bank / initial_bankroll - 1.0) * 100.0),
        "max_drawdown_pct": float(max_dd * 100.0),
        "curve": np.asarray(curve, dtype=float),
    }
