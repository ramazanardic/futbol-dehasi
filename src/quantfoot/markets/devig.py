"""Bookmaker overround removal (devigging) solvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.optimize import brentq

DevigMethod = Literal["power", "shin", "odds_ratio", "multiplicative", "goto", "ensemble"]


@dataclass(frozen=True)
class DevigResult:
    """Fair probabilities and market overround extracted from decimal odds."""

    probabilities: np.ndarray
    overround: float
    method: str
    parameter: float | None = None


def book_overround(odds: np.ndarray | list[float]) -> float:
    """Compute bookmaker overround (vig), e.g. 0.05 for a 105% book."""
    arr = np.asarray(odds, dtype=float)
    return float(np.sum(1.0 / arr) - 1.0)


def _solve_power(inv: np.ndarray) -> tuple[np.ndarray, float]:
    fn = lambda exp_k: float(np.sum(inv**exp_k) - 1.0)  # noqa: E731
    upper = 4.0
    while fn(upper) > 0.0 and upper < 1024.0:
        upper *= 2.0
    k = brentq(fn, 0.25, upper, xtol=1e-10)
    probs = inv**k
    return probs / np.sum(probs), float(k)


def _solve_odds_ratio(inv: np.ndarray) -> tuple[np.ndarray, float]:
    fn = lambda ratio: float(np.sum(inv / (ratio + (1.0 - ratio) * inv)) - 1.0)  # noqa: E731
    upper = 25.0
    while fn(upper) > 0.0 and upper < 1e6:
        upper *= 4.0
    lower = 0.05
    if fn(lower) <= 0.0:
        return inv / float(np.sum(inv)), 1.0
    c = brentq(fn, lower, upper, xtol=1e-10)
    probs = inv / (c + (1.0 - c) * inv)
    return probs / np.sum(probs), float(c)


def _solve_shin(inv: np.ndarray) -> tuple[np.ndarray, float]:
    s = float(np.sum(inv))

    def _shin_probs(z: float) -> np.ndarray:
        inner = np.maximum(z * z + 4.0 * (1.0 - z) * (inv * inv) / s, 0.0)
        return (np.sqrt(inner) - z) / (2.0 * (1.0 - z))

    fn = lambda z: float(np.sum(_shin_probs(z)) - 1.0)  # noqa: E731
    lo = 0.0
    if fn(lo) <= 0.0:
        return inv / s, 0.0
    hi = 0.75
    while fn(hi) > 0.0 and hi < 0.99999:
        hi = 1.0 - 0.25 * (1.0 - hi)
    if fn(hi) > 0.0:
        probs = np.clip(_shin_probs(hi), 1e-12, None)
        return probs / np.sum(probs), float(hi)
    z_opt = brentq(fn, lo, hi, xtol=1e-10)
    probs = np.clip(_shin_probs(z_opt), 1e-12, None)
    return probs / np.sum(probs), float(z_opt)


def _solve_goto(inv: np.ndarray) -> tuple[np.ndarray, float]:
    """Closed-form Kaito Goto standard-error conversion for favorite-longshot bias.

    Shifts each naive inverse probability ``p_i = 1 / O_i`` by a uniform number of
    standard-error units ``se_i = sqrt((p_i - p_i^2) / p_i) = sqrt(1 - p_i)`` so
    ``sum(p_i - step * se_i) = 1``. Longshots carry larger relative standard error
    and therefore absorb proportionally more bookmaker margin than heavy favorites.
    When an extreme longshot would be pushed non-positive, the step is iteratively
    projected onto the positive simplex while preserving monotonicity.
    """
    p = np.asarray(inv, dtype=float)
    se = np.sqrt(np.maximum(1.0 - p, 1e-15))
    overround = float(np.sum(p) - 1.0)
    se_sum = float(np.sum(se))
    if se_sum <= 1e-15:
        return p / float(np.sum(p)), 0.0

    step = overround / se_sum
    probs = p - step * se
    eps = 1e-9

    if np.all(probs > eps):
        return probs / float(np.sum(probs)), float(step)

    # Boundary-safe active-set projection when extreme longshots would hit <= 0.
    active = np.ones_like(p, dtype=bool)
    out = np.full_like(p, eps)
    eff_step = step
    for _ in range(len(p)):
        if not np.any(active):
            break
        rem_target = 1.0 - float(np.sum(out[~active]))
        rem_excess = float(np.sum(p[active])) - rem_target
        rem_se = float(np.sum(se[active]))
        if rem_se <= 1e-15:
            out[active] = p[active] / float(np.sum(p[active])) * rem_target
            break
        eff_step = rem_excess / rem_se
        cand = p[active] - eff_step * se[active]
        bad = cand <= eps
        if not np.any(bad):
            out[active] = cand
            break
        active_idx = np.flatnonzero(active)
        out[active_idx[bad]] = eps
        active[active_idx[bad]] = False
    out = np.clip(out, eps, None)
    return out / float(np.sum(out)), float(eff_step)


def _solve_ensemble(inv: np.ndarray) -> tuple[np.ndarray, float]:
    """Equal-weight ensemble of Power, Shin, and Goto devigging solvers."""
    p_pow, _ = _solve_power(inv)
    p_shin, _ = _solve_shin(inv)
    p_goto, step = _solve_goto(inv)
    probs = (p_pow + p_shin + p_goto) / 3.0
    return probs / float(np.sum(probs)), float(step)


def devig(odds: np.ndarray | list[float], method: DevigMethod = "power") -> DevigResult:
    """Strip bookmaker margin from decimal odds using the requested method."""
    arr = np.asarray(odds, dtype=float)
    if np.any(arr <= 1.0):
        raise ValueError(f"All decimal odds must exceed 1.0, got {arr}.")

    inv = 1.0 / arr
    s = float(np.sum(inv))
    overround = s - 1.0

    # When odds already offer zero or negative vig, proportional scaling preserves order cleanly.
    if method == "multiplicative" or s <= 1.0 + 1e-12:
        return DevigResult(probabilities=inv / s, overround=overround, method=method, parameter=None)

    solvers = {
        "power": _solve_power,
        "odds_ratio": _solve_odds_ratio,
        "shin": _solve_shin,
        "goto": _solve_goto,
        "ensemble": _solve_ensemble,
    }
    if method not in solvers:
        raise ValueError(f"Unknown devigging method: {method}")

    probs, param = solvers[method](inv)
    return DevigResult(probabilities=probs, overround=overround, method=method, parameter=param)


def devig_batch(odds_matrix: np.ndarray, method: DevigMethod = "power") -> np.ndarray:
    """Vectorized/batch margin removal across an (N, K) matrix of decimal odds."""
    arr = np.asarray(odds_matrix, dtype=float)
    if arr.ndim != 2:
        raise ValueError("odds_matrix must be 2D of shape (N, K).")
    if np.any(arr <= 1.0):
        raise ValueError("All decimal odds must exceed 1.0.")
    if method == "multiplicative":
        inv = 1.0 / arr
        return inv / np.sum(inv, axis=1, keepdims=True)
    if method == "goto":
        inv = 1.0 / arr
        s = np.sum(inv, axis=1, keepdims=True)
        se = np.sqrt(np.maximum(1.0 - inv, 1e-15))
        step = np.maximum(s - 1.0, 0.0) / np.maximum(np.sum(se, axis=1, keepdims=True), 1e-15)
        probs = inv - step * se
        # Fast path when all rows have positive vig and strictly positive probabilities.
        clean = (s[:, 0] > 1.0 + 1e-12) & np.all(probs > 1e-9, axis=1)
        if np.all(clean):
            return probs / np.sum(probs, axis=1, keepdims=True)
        out = np.empty_like(probs)
        out[clean] = probs[clean] / np.sum(probs[clean], axis=1, keepdims=True)
        for idx in np.flatnonzero(~clean):
            out[idx] = devig(arr[idx], method="goto").probabilities
        return out
    return np.vstack([devig(row, method=method).probabilities for row in arr])
