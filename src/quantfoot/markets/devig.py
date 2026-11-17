"""Bookmaker overround removal (devigging) solvers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.optimize import brentq

DevigMethod = Literal["power", "shin", "odds_ratio", "multiplicative"]


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
    k = brentq(lambda exp_k: float(np.sum(inv**exp_k) - 1.0), 0.25, 4.0, xtol=1e-10)
    probs = inv**k
    return probs / np.sum(probs), float(k)


def _solve_odds_ratio(inv: np.ndarray) -> tuple[np.ndarray, float]:
    c = brentq(
        lambda ratio: float(np.sum(inv / (ratio + (1.0 - ratio) * inv)) - 1.0),
        0.05,
        25.0,
        xtol=1e-10,
    )
    probs = inv / (c + (1.0 - c) * inv)
    return probs / np.sum(probs), float(c)


def _solve_shin(inv: np.ndarray) -> tuple[np.ndarray, float]:
    s = float(np.sum(inv))

    def _shin_probs(z: float) -> np.ndarray:
        inner = np.maximum(z * z + 4.0 * (1.0 - z) * (inv * inv) / s, 0.0)
        return (np.sqrt(inner) - z) / (2.0 * (1.0 - z))

    z_opt = brentq(lambda z: float(np.sum(_shin_probs(z)) - 1.0), 1e-12, 0.75, xtol=1e-10)
    probs = np.clip(_shin_probs(z_opt), 1e-12, None)
    return probs / np.sum(probs), float(z_opt)


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
    if method == "multiplicative":
        inv = 1.0 / arr
        return inv / np.sum(inv, axis=1, keepdims=True)
    return np.vstack([devig(row, method=method).probabilities for row in arr])
