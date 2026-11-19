"""Fractional Kelly criterion, correlated portfolio optimization, and MacLean-Thorp-Ziemba risk metrics."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm


def kelly_fraction(
    prob: float,
    decimal_odds: float,
    multiplier: float = 0.25,
    max_stake: float = 0.03,
) -> float:
    """Compute capped fractional Kelly stake fraction for a single binary bet."""
    if decimal_odds <= 1.0 or prob <= 0.0:
        return 0.0
    b = decimal_odds - 1.0
    f_full = (prob * decimal_odds - 1.0) / b
    if f_full <= 0.0:
        return 0.0
    return float(min(multiplier * f_full, max_stake))


def baker_mchale_kelly_fraction(
    prob: float,
    decimal_odds: float,
    prob_std: float = 0.0,
    multiplier: float = 0.25,
    max_stake: float = 0.03,
) -> float:
    """Compute Baker & McHale (2013) parameter-uncertainty shrunken fractional Kelly stake."""
    if prob_std <= 0.0:
        return kelly_fraction(prob, decimal_odds, multiplier=multiplier, max_stake=max_stake)
    # Shrink the uncapped fractional stake first, then apply the cap.
    base = kelly_fraction(prob, decimal_odds, multiplier=multiplier, max_stake=float("inf"))
    if base <= 0.0:
        return 0.0
    edge = prob * decimal_odds - 1.0
    sigma_edge = decimal_odds * prob_std
    shrinkage = (edge * edge) / (edge * edge + sigma_edge * sigma_edge)
    return float(min(base * shrinkage, max_stake))


def maclean_doubling_before_halving(kelly_multiplier: float) -> dict[str, float]:
    """Return continuous-time capital growth and drawdown probabilities (MacLean, Thorp, Ziemba)."""
    if kelly_multiplier <= 0.0:
        raise ValueError("kelly_multiplier must be positive.")
    c = float(kelly_multiplier)
    rel_growth = c * (2.0 - c)
    if c >= 2.0:
        return {
            "kelly_multiplier": c,
            "relative_growth_rate": rel_growth,
            "prob_double_before_half": 0.0,
            "prob_ever_half_capital": 1.0,
        }
    a = (2.0 / c) - 1.0
    p_double = (2.0**a) / (2.0**a + 1.0)
    p_ever_half = 0.5**a
    return {
        "kelly_multiplier": c,
        "relative_growth_rate": float(rel_growth),
        "prob_double_before_half": float(p_double),
        "prob_ever_half_capital": float(p_ever_half),
    }


def _simulate_copula_returns(
    probs: np.ndarray,
    odds: np.ndarray,
    corr_matrix: np.ndarray,
    n_scenarios: int,
    seed: int,
) -> np.ndarray:
    """Simulate correlated binary bet net returns using a Gaussian copula with antithetic variates."""
    rng = np.random.default_rng(seed)
    n_bets = len(probs)
    half = max(n_scenarios // 2, 1)

    # Ensure PSD correlation matrix with small jitter if needed
    eig_min = float(np.min(np.linalg.eigvalsh(corr_matrix)))
    mat = corr_matrix.copy()
    if eig_min < 1e-6:
        mat += np.eye(n_bets) * (1e-6 - eig_min)

    z_half = rng.multivariate_normal(np.zeros(n_bets), mat, size=half)
    z = np.vstack([z_half, -z_half])
    thresholds = norm.ppf(np.clip(probs, 1e-6, 1.0 - 1e-6))
    wins = z <= thresholds[None, :]
    b = odds - 1.0
    return np.where(wins, b[None, :], -1.0)


def optimize_correlated_kelly(
    probs: np.ndarray | list[float],
    odds: np.ndarray | list[float],
    corr_matrix: np.ndarray | None = None,
    multiplier: float = 0.25,
    max_per_bet: float = 0.03,
    max_total: float = 0.15,
    n_scenarios: int = 8000,
    seed: int = 42,
) -> dict[str, object]:
    """Solve simultaneous fractional Kelly allocation across correlated bets."""
    p_arr = np.asarray(probs, dtype=float)
    o_arr = np.asarray(odds, dtype=float)
    n = len(p_arr)
    if n == 0:
        return {"fractions": np.array([]), "full_kelly": np.array([]), "expected_log_growth": 0.0}
    if o_arr.shape != p_arr.shape:
        raise ValueError("probs and odds must have identical shapes.")

    if corr_matrix is None:
        corr = np.eye(n, dtype=float)
    else:
        corr = np.asarray(corr_matrix, dtype=float)
        if corr.shape != (n, n):
            raise ValueError(f"corr_matrix must have shape ({n}, {n}).")

    # Zero out non-+EV bets before portfolio optimization
    ev = p_arr * o_arr - 1.0
    active = (ev > 0.0) & (o_arr > 1.0) & (p_arr > 0.0)
    if not np.any(active):
        zeros = np.zeros(n, dtype=float)
        return {"fractions": zeros, "full_kelly": zeros, "expected_log_growth": 0.0}

    idx = np.where(active)[0]
    p_sub = p_arr[idx]
    o_sub = o_arr[idx]
    corr_sub = corr[np.ix_(idx, idx)]

    returns = _simulate_copula_returns(p_sub, o_sub, corr_sub, n_scenarios=n_scenarios, seed=seed)
    m = len(idx)

    # Solve full Kelly portfolio with wealth >= 0.05 safety margin, then apply fractional multiplier.
    def _neg_log_growth(f: np.ndarray) -> float:
        wealth = 1.0 + returns @ f
        if np.any(wealth <= 1e-4):
            return 1e9 + float(np.sum(np.maximum(1e-4 - wealth, 0.0))) * 1e6
        return -float(np.mean(np.log(wealth)))

    bounds = [(0.0, 0.5) for _ in range(m)]
    constraints = ({"type": "ineq", "fun": lambda f: 0.95 - float(np.sum(f))},)
    init = np.minimum((p_sub * o_sub - 1.0) / (o_sub - 1.0), 0.15) / max(m, 1)

    res = minimize(_neg_log_growth, init, method="SLSQP", bounds=bounds, constraints=constraints, options={"ftol": 1e-9, "maxiter": 600})
    f_full_sub = np.clip(res.x, 0.0, 1.0)
    f_scaled_sub = np.minimum(multiplier * f_full_sub, max_per_bet)
    if float(np.sum(f_scaled_sub)) > max_total:
        f_scaled_sub *= max_total / float(np.sum(f_scaled_sub))

    full_kelly = np.zeros(n, dtype=float)
    fractions = np.zeros(n, dtype=float)
    full_kelly[idx] = f_full_sub
    fractions[idx] = f_scaled_sub

    wealth_final = 1.0 + returns @ f_scaled_sub
    growth = float(np.mean(np.log(np.maximum(wealth_final, 1e-9))))
    return {
        "fractions": fractions,
        "full_kelly": full_kelly,
        "expected_log_growth": growth,
    }
