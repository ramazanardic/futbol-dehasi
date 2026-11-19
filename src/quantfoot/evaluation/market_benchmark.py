"""Does the model add information to the market? Pooling-weight test and closing-line value.

Pooling test (Pitcan 2026, arXiv:2608.11505): combine market and model probabilities in a
logarithmic opinion pool

    p_w  proportional to  p_market^(1 - w) * p_model^w ,   w in [0, 1]

and choose w by minimum mean log-loss on settled matches. w = 0 means the model carries no
information the (margin-free) market price has not already absorbed. A bootstrap over
matches gives a confidence interval; only an interval clearly above 0 is evidence of an edge.

Closing-line value (CLV): beating the closing price is a far less noisy indicator of skill
than realised profit (Kaunitz et al. 2017, arXiv:1710.02824).
    raw CLV  = taken_odds / closing_odds - 1
    fair CLV = taken_odds * p_close_fair - 1   (expected value at the margin-free closing price)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

GRID = np.round(np.linspace(0.0, 1.0, 101), 2)


def log_pool(p_market: np.ndarray, p_model: np.ndarray, w: float) -> np.ndarray:
    """Logarithmic opinion pool of two (n, k) probability arrays."""
    lm = np.log(np.clip(p_market, 1e-12, 1.0))
    lf = np.log(np.clip(p_model, 1e-12, 1.0))
    z = (1.0 - w) * lm + w * lf
    z -= z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _pool_losses(p_market: np.ndarray, p_model: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Per-match log-loss for every grid weight: shape (len(GRID), n)."""
    rows = np.arange(len(y))
    return np.stack([-np.log(np.clip(log_pool(p_market, p_model, w)[rows, y], 1e-12, 1.0)) for w in GRID])


@dataclass(frozen=True)
class PoolResult:
    n: int
    weight: float
    ci_low: float
    ci_high: float
    logloss_market: float
    logloss_model: float
    logloss_pool: float


def pooling_test(
    p_market: np.ndarray,
    p_model: np.ndarray,
    y: np.ndarray,
    n_boot: int = 1000,
    seed: int = 7,
) -> PoolResult:
    """Fit the pooling weight and a percentile bootstrap interval (resampling matches)."""
    p_market = np.asarray(p_market, dtype=float)
    p_model = np.asarray(p_model, dtype=float)
    y = np.asarray(y, dtype=int)
    if len(y) == 0:
        raise ValueError("Sonuçlanmış maç yok.")
    losses = _pool_losses(p_market, p_model, y)
    mean = losses.mean(axis=1)
    best = int(np.argmin(mean))
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        boots[b] = GRID[int(np.argmin(losses[:, idx].mean(axis=1)))]
    return PoolResult(
        n=len(y),
        weight=float(GRID[best]),
        ci_low=float(np.quantile(boots, 0.025)),
        ci_high=float(np.quantile(boots, 0.975)),
        logloss_market=float(mean[0]),
        logloss_model=float(mean[-1]),
        logloss_pool=float(mean[best]),
    )


def raw_clv(taken_odds: float, closing_odds: float) -> float:
    return float(taken_odds) / float(closing_odds) - 1.0


def fair_clv(taken_odds: float, p_close_fair: float) -> float:
    return float(taken_odds) * float(p_close_fair) - 1.0


def mean_with_ci(values: list[float], n_boot: int = 2000, seed: int = 11) -> tuple[float, float, float] | None:
    """Mean and 95% bootstrap interval of a list (None when empty)."""
    v = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if v.size == 0:
        return None
    rng = np.random.default_rng(seed)
    boots = rng.choice(v, size=(n_boot, v.size), replace=True).mean(axis=1)
    return float(v.mean()), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))
