"""Boshnakov, Kharrat & McHale (2017) Bivariate Weibull Count + Frank Copula Model."""

from __future__ import annotations

import math

import numpy as np
from scipy.special import gammaln


def weibull_alpha_table(shape_c: float, max_n: int = 8, jmax: int = 26) -> np.ndarray:
    """Precompute McShane et al. (2008) lower-triangular series coefficients alpha[n, j]."""
    ratios = np.array([math.exp(gammaln(shape_c * k + 1.0) - gammaln(k + 1.0)) for k in range(jmax + 1)])
    alpha = np.zeros((max_n + 1, jmax + 1), dtype=np.float64)
    alpha[0, :] = ratios
    for n in range(1, max_n + 1):
        for j in range(n, jmax + 1):
            m_idx = np.arange(n - 1, j)
            alpha[n, j] = float(np.sum(alpha[n - 1, m_idx] * ratios[j - m_idx]))
    return alpha


def weibull_count_pmf(
    lam: float,
    shape_c: float = 1.05,
    max_n: int = 8,
    jmax: int = 26,
    alpha_table: np.ndarray | None = None,
) -> np.ndarray:
    """Compute Weibull count PMF P(N=0..max_n); collapses exactly to Poisson(lam) at c=1.0."""
    if alpha_table is None:
        alpha_table = weibull_alpha_table(shape_c, max_n=max_n, jmax=jmax)

    log_lam = math.log(max(lam, 1e-12))
    gamma_den = np.array([gammaln(shape_c * j + 1.0) for j in range(jmax + 1)])
    probs = np.zeros(max_n + 1, dtype=np.float64)

    for n in range(max_n + 1):
        j_vals = np.arange(n, jmax + 1)
        signs = np.where((j_vals - n) % 2 == 1, -1.0, 1.0)
        a_slice = np.maximum(alpha_table[n, n : jmax + 1], 1e-300)
        log_terms = np.minimum(j_vals * log_lam + np.log(a_slice) - gamma_den[n : jmax + 1], 45.0)
        probs[n] = max(float(np.sum(signs * np.exp(log_terms))), 0.0)

    total = float(np.sum(probs))
    return probs / total if total > 0.0 else np.eye(1, max_n + 1)[0]


def frank_copula_score_matrix(px: np.ndarray, py: np.ndarray, theta: float = 0.35) -> np.ndarray:
    """Couple two marginal count PMFs into a joint (M+1, M+1) matrix via Frank copula."""
    if abs(theta) < 1e-5:
        mat = np.outer(px, py)
        return mat / np.sum(mat)

    fx = np.clip(np.cumsum(px), 0.0, 1.0)
    fy = np.clip(np.cumsum(py), 0.0, 1.0)
    fx_prev = np.concatenate([[0.0], fx[:-1]])
    fy_prev = np.concatenate([[0.0], fy[:-1]])
    den = math.expm1(-theta)

    def _cop(u: np.ndarray, v: np.ndarray) -> np.ndarray:
        return -(1.0 / theta) * np.log1p((np.expm1(-theta * u)[:, None] * np.expm1(-theta * v)[None, :]) / den)

    mat = _cop(fx, fy) - _cop(fx_prev, fy) - _cop(fx, fy_prev) + _cop(fx_prev, fy_prev)
    mat = np.maximum(mat, 0.0)
    total = float(np.sum(mat))
    return mat / total if total > 0.0 else np.outer(px, py)
