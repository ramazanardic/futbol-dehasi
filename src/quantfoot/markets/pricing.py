"""Unified bivariate score-matrix pricing, Skellam goal-difference distribution, and AH settlement."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln, ive


_GRID_8 = np.arange(9, dtype=float)
_FACT_8 = gammaln(_GRID_8 + 1.0)
_HG_8, _AG_8 = np.meshgrid(np.arange(9), np.arange(9), indexing="ij")
_OVER25_MASK = (_HG_8 + _AG_8) > 2
_GD_8 = _HG_8 - _AG_8


def skellam_probabilities(
    mu_home: float,
    mu_away: float,
    min_diff: int = -8,
    max_diff: int = 8,
) -> dict[int, float]:
    """Compute exact Skellam PMF P(X - Y = d) via exponentially scaled Bessel functions."""
    if mu_home <= 0.0 or mu_away <= 0.0:
        raise ValueError("Poisson rates mu_home and mu_away must be positive.")

    z = 2.0 * math.sqrt(mu_home * mu_away)
    log_ratio = 0.5 * math.log(mu_home / mu_away)
    prefactor = math.exp(-(mu_home + mu_away) + z)

    probs: dict[int, float] = {}
    for d in range(min_diff, max_diff + 1):
        # ive(v, z) = exp(-|z|) * I_v(z) prevents numerical overflow for large rates.
        probs[d] = float(prefactor * math.exp(d * log_ratio) * ive(abs(d), z))
    return probs


def _sub_lines(line: float) -> list[float]:
    """Split quarter-ball Asian Handicap lines (.25/.75) into two adjacent half/whole lines."""
    exact_quarter = round(line * 4.0) / 4.0
    rem = round((exact_quarter * 4.0) % 2)
    if rem != 0:
        return [exact_quarter - 0.25, exact_quarter + 0.25]
    return [exact_quarter]


def settle_asian_handicap(goal_diff: float, line: float, odds: float, is_home: bool = True) -> float:
    """Return exact net profit per 1.0 unit staked for an Asian Handicap bet."""
    lines = _sub_lines(line)
    net_profit = 0.0
    weight = 1.0 / len(lines)
    for sub_line in lines:
        margin = (goal_diff + sub_line) if is_home else (-goal_diff - sub_line)
        if margin > 1e-6:
            net_profit += weight * (odds - 1.0)
        elif margin < -1e-6:
            net_profit -= weight
    return float(net_profit)


def expected_ah_ev(score_matrix: np.ndarray, line: float, odds: float, is_home: bool = True) -> float:
    """Compute exact Expected Value of an Asian Handicap line from a joint score matrix."""
    n_h, n_a = score_matrix.shape
    gi, gj = np.meshgrid(np.arange(n_h), np.arange(n_a), indexing="ij")
    gd = (gi - gj).ravel()
    probs = score_matrix.ravel()
    lines = _sub_lines(line)
    ev = 0.0
    for sub_line in lines:
        margin = (gd + sub_line) if is_home else (-gd - sub_line)
        win_p = float(np.sum(probs[margin > 1e-6]))
        loss_p = float(np.sum(probs[margin < -1e-6]))
        ev += (win_p * (odds - 1.0) - loss_p) / len(lines)
    return float(ev)


def fair_ah_odds(score_matrix: np.ndarray, line: float, is_home: bool = True) -> float:
    """Compute exact zero-margin fair decimal odds for an Asian Handicap line."""
    n_h, n_a = score_matrix.shape
    gi, gj = np.meshgrid(np.arange(n_h), np.arange(n_a), indexing="ij")
    gd = (gi - gj).ravel()
    probs = score_matrix.ravel()
    lines = _sub_lines(line)

    win_eff = 0.0
    loss_eff = 0.0
    for sub_line in lines:
        margin = (gd + sub_line) if is_home else (-gd - sub_line)
        win_eff += float(np.sum(probs[margin > 1e-6])) / len(lines)
        loss_eff += float(np.sum(probs[margin < -1e-6])) / len(lines)

    if win_eff <= 1e-9:
        return float("inf")
    return float(1.0 + loss_eff / win_eff)


def over_under_probability(score_matrix: np.ndarray, line: float) -> tuple[float, float]:
    """Return (P(total > line), P(total < line)) from a normalized score matrix.

    For a whole-goal line (2.0, 3.0) the push mass P(total == line) belongs to neither side, so the two
    probabilities sum to 1 - P(push). (Before 21 Nov the under side was 1 - P(over), i.e. it silently counted
    the push as an under win: +25 pp at line 2.0 for a 1.5 / 1.1 match.)"""
    mat = np.asarray(score_matrix, dtype=float)
    mat = mat / np.sum(mat)
    n_h, n_a = mat.shape
    gi, gj = np.meshgrid(np.arange(n_h), np.arange(n_a), indexing="ij")
    tot = gi + gj
    p_over = float(np.sum(mat[tot > line + 1e-9]))
    p_under = float(np.sum(mat[tot < line - 1e-9]))
    return p_over, p_under


def price_all_markets(score_matrix: np.ndarray, top_scores: int = 5) -> dict[str, object]:
    """Derive coherent fair probabilities across 1X2, DC, O/U, BTTS, AH, and exact scores."""
    mat = np.asarray(score_matrix, dtype=float)
    mat = mat / np.sum(mat)
    n_h, n_a = mat.shape
    gi, gj = np.meshgrid(np.arange(n_h), np.arange(n_a), indexing="ij")
    totals = gi + gj

    p_h = float(np.sum(np.tril(mat, -1)))
    p_d = float(np.sum(np.diag(mat)))
    p_a = float(np.sum(np.triu(mat, 1)))

    over_under = {}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        p_over = float(np.sum(mat[totals > line]))
        over_under[f"over_{line}"] = p_over
        over_under[f"under_{line}"] = 1.0 - p_over

    p_btts_yes = float(np.sum(mat[(gi >= 1) & (gj >= 1)]))

    ah_fair_odds = {}
    for line in (-1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5):
        ah_fair_odds[f"home_{line:+.2f}"] = fair_ah_odds(mat, line, is_home=True)
        ah_fair_odds[f"away_{-line:+.2f}"] = fair_ah_odds(mat, line, is_home=False)

    flat_idx = np.argsort(mat.ravel())[::-1][:top_scores]
    exact_scores = []
    for idx in flat_idx:
        i, j = divmod(int(idx), n_a)
        exact_scores.append({"score": f"{i}-{j}", "prob": float(mat[i, j]), "fair_odds": float(1.0 / max(mat[i, j], 1e-9))})

    return {
        "1x2": {"H": p_h, "D": p_d, "A": p_a},
        "double_chance": {"1X": p_h + p_d, "X2": p_d + p_a, "12": p_h + p_a},
        "over_under": over_under,
        "btts": {"yes": p_btts_yes, "no": 1.0 - p_btts_yes},
        "asian_handicap_fair_odds": ah_fair_odds,
        "top_exact_scores": exact_scores,
        "expected_home_goals": float(np.sum(gi * mat)),
        "expected_away_goals": float(np.sum(gj * mat)),
    }


def invert_ah_ou_1x2(
    ah_line: float,
    p_ah_home_share: float,
    p_over25: float,
    rho: float = -0.09,
) -> tuple[float, float, np.ndarray]:
    """Invert low-vig Asian Handicap + O/U 2.5 market shares into (lambda, mu, Fair 1X2 [H, D, A])."""
    lines = _sub_lines(ah_line)
    w = 1.0 / len(lines)
    win_masks = [(_GD_8 + ln) > 1e-6 for ln in lines]
    loss_masks = [(_GD_8 + ln) < -1e-6 for ln in lines]

    def _loss(x: np.ndarray) -> float:
        lam = math.exp(float(np.clip(x[0], -1.8, 1.5)))
        mu = math.exp(float(np.clip(x[1], -1.8, 1.5)))
        px = np.exp(-lam + _GRID_8 * math.log(lam) - _FACT_8)
        py = np.exp(-mu + _GRID_8 * math.log(mu) - _FACT_8)
        mat = np.outer(px, py)
        mat[0, 0] *= max(1.0 - lam * mu * rho, 1e-6)
        mat[0, 1] *= max(1.0 + lam * rho, 1e-6)
        mat[1, 0] *= max(1.0 + mu * rho, 1e-6)
        mat[1, 1] *= max(1.0 - rho, 1e-6)
        mat /= np.sum(mat)

        p_o = float(np.sum(mat[_OVER25_MASK]))
        w_sum = sum(w * float(np.sum(mat[m])) for m in win_masks)
        l_sum = sum(w * float(np.sum(mat[m])) for m in loss_masks)
        ah_share = w_sum / max(w_sum + l_sum, 1e-9)
        return (ah_share - p_ah_home_share) ** 2 + (p_o - p_over25) ** 2

    tot_seed = float(np.clip(2.55 + 2.2 * (p_over25 - 0.5), 1.4, 4.2))
    diff_seed = float(np.clip(1.6 * (p_ah_home_share - 0.5) - ah_line, -2.0, 2.0))
    lam_0 = max(0.35, 0.5 * (tot_seed + diff_seed))
    mu_0 = max(0.35, 0.5 * (tot_seed - diff_seed))
    res = minimize(
        _loss,
        np.array([math.log(lam_0), math.log(mu_0)]),
        method="Nelder-Mead",
        options={"xatol": 2e-3, "fatol": 1e-6, "maxiter": 45},
    )
    lam = math.exp(float(np.clip(res.x[0], -1.8, 1.5)))
    mu = math.exp(float(np.clip(res.x[1], -1.8, 1.5)))
    px = np.exp(-lam + _GRID_8 * math.log(lam) - _FACT_8)
    py = np.exp(-mu + _GRID_8 * math.log(mu) - _FACT_8)
    mat = np.outer(px, py)
    mat[0, 0] *= max(1.0 - lam * mu * rho, 1e-6)
    mat[0, 1] *= max(1.0 + lam * rho, 1e-6)
    mat[1, 0] *= max(1.0 + mu * rho, 1e-6)
    mat[1, 1] *= max(1.0 - rho, 1e-6)
    mat /= np.sum(mat)
    p1x2 = np.array([float(np.sum(np.tril(mat, -1))), float(np.sum(np.diag(mat))), float(np.sum(np.triu(mat, 1)))])
    return lam, mu, p1x2 / np.sum(p1x2)
