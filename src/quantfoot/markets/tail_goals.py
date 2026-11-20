"""Overdispersed bivariate tail-goal pricing for high-total (5.5+ / 6+ goals) research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln, roots_genlaguerre

# Regime parameters: (token, (com_nu, alpha_nb, shared_kappa))
# Club leagues follow empirical 34,463-match holdout COM-Poisson underdispersion (nu=1.10);
# International / youth / friendly mismatches retain Gamma-Poisson overdispersion
# calibrated against 49,940 international matches (Var/Mean ~ 1.22-1.29).
_DEFAULT_LEAGUE_REGIMES: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("fifa.world.u17", (1.00, 0.12, 0.09)),
    ("uefa.euro.u19", (1.00, 0.12, 0.09)),
    ("uefa.euro.u17", (1.00, 0.12, 0.09)),
    ("uefa.euro_u21", (1.00, 0.10, 0.08)),
    ("fifa.friendly_u21", (1.00, 0.11, 0.08)),
    ("u21", (1.00, 0.11, 0.08)),
    ("u19", (1.00, 0.12, 0.09)),
    ("u17", (1.00, 0.12, 0.09)),
    ("wchampions", (1.00, 0.04, 0.03)),
    ("reina", (1.00, 0.06, 0.04)),
    ("eng.w.", (1.00, 0.04, 0.03)),
    ("women", (1.00, 0.05, 0.03)),
    ("concacaf", (1.00, 0.08, 0.07)),
    ("fifa.friendly", (1.00, 0.09, 0.07)),
    ("copa_del_rey", (1.00, 0.08, 0.06)),
    ("uefa.nations", (1.00, 0.06, 0.05)),
    ("caf.", (1.00, 0.07, 0.06)),
    ("bra.1", (1.10, 0.00, 0.00)),
    ("tur.3", (1.10, 0.00, 0.00)),
    ("eng.trophy", (1.05, 0.00, 0.02)),
    ("isthmian", (1.06, 0.00, 0.02)),
    ("nonleague", (1.06, 0.00, 0.02)),
    ("nifl", (1.05, 0.00, 0.02)),
    ("per.1", (1.10, 0.00, 0.00)),
    ("bol.", (1.08, 0.00, 0.01)),
    ("col.", (1.10, 0.00, 0.00)),
    ("ind.2", (1.08, 0.00, 0.01)),
    # Open-tempo Gulf, Oceania, MLS, ASEAN & domestic cup regimes (Nov 19 post-mortem)
    ("uae.", (1.00, 0.06, 0.05)),
    ("qat.", (1.00, 0.05, 0.04)),
    ("aus.", (1.00, 0.06, 0.05)),
    ("usa.", (1.00, 0.03, 0.02)),
    ("afc.cup", (1.00, 0.06, 0.04)),
    ("svk.cup", (1.00, 0.07, 0.05)),
    ("svn.cup", (1.00, 0.06, 0.05)),
    ("jor.cup", (1.00, 0.07, 0.05)),
    # Tight defensive club regimes
    ("egy.", (1.10, 0.00, 0.00)),
    ("alg.", (1.10, 0.00, 0.00)),
    ("irn.", (1.10, 0.00, 0.00)),
    ("zam.", (1.10, 0.00, 0.00)),
)
# Club regime re-calibrated on market-anchored FT derivative markets (calibration 2019-22, test 2022+,
# 6,000 matches): nu=1.0 / rho=-0.03 beat the earlier nu=1.10 / rho=-0.07 on every market line
# (total log-loss 4.611 -> 4.554; KG Var mean 48.1% -> 51.3% vs 52.8% observed).
# See reports/research/regime_calibration.md.
CLUB_REGIME: tuple[float, float, float] = (1.00, 0.00, 0.00)
DEFAULT_RHO: float = -0.03
_CLUB_CODES: frozenset[str] = frozenset(
    {"e0", "e1", "e2", "e3", "ec", "sp1", "sp2", "d1", "d2", "i1", "i2", "f1", "f2", "t1", "n1", "p1", "b1", "sc0", "sc1", "sc2", "sc3"}
)


@dataclass(frozen=True)
class TailGoalSummary:
    """Summary probabilities for extreme total-goal events derived from a score matrix."""

    expected_total: float
    variance_total: float
    expected_home: float
    expected_away: float
    p_home: float
    p_draw: float
    p_away: float
    p_btts: float
    p_4plus: float
    p_5plus: float
    p_6plus: float
    p_7plus: float
    fair_odds_6plus: float
    top_6plus_scorelines: tuple[tuple[str, float], ...]


def league_tail_regime(league_slug: str | None) -> tuple[float, float, float]:
    """Return calibrated (com_nu, alpha_nb, shared_kappa) for a competition regime."""
    if not league_slug:
        return (1.05, 0.00, 0.02)
    slug = league_slug.lower()
    if slug in _CLUB_CODES:
        return CLUB_REGIME
    for token, params in _DEFAULT_LEAGUE_REGIMES:
        if token in slug:
            return params
    return CLUB_REGIME


def league_tail_params(league_slug: str | None) -> tuple[float, float]:
    """Return calibrated (alpha_nb, shared_kappa) dispersion parameters for a competition."""
    _, alpha_nb, shared_kappa = league_tail_regime(league_slug)
    return (alpha_nb, shared_kappa)


def com_poisson_pmf(mu: float, nu: float = 1.0, max_goals: int = 14) -> np.ndarray:
    """Mean-calibrated Conway-Maxwell-Poisson PMF over 0..max_goals (nu>1 underdispersed)."""
    goals = np.arange(max_goals + 1, dtype=float)
    if mu <= 0.0:
        out = np.zeros_like(goals)
        out[0] = 1.0
        return out
    if abs(nu - 1.0) < 1e-6:
        return _poisson_pmf(mu, goals)

    fact = gammaln(goals + 1.0)
    target = float(min(mu, max_goals - 0.1))
    lo, hi = -8.0, 6.0
    # 60 halvings of [-8, 6] reach float precision; 24 left the pmf piecewise-constant at ~1e-6,
    # which gave finite-difference optimisers a zero gradient (fits silently stayed at their start).
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lp = goals * mid - nu * fact
        lp -= lp.max()
        p = np.exp(lp)
        p /= p.sum()
        if float(np.sum(goals * p)) < target:
            lo = mid
        else:
            hi = mid
    mid = 0.5 * (lo + hi)
    lp = goals * mid - nu * fact
    lp -= lp.max()
    p = np.exp(lp)
    return p / p.sum()


def _poisson_pmf(lam: float, goals: np.ndarray) -> np.ndarray:
    """Evaluate numerically stable Poisson PMF over an integer goal grid."""
    if lam <= 0.0:
        out = np.zeros_like(goals, dtype=float)
        out[0] = 1.0
        return out
    log_p = goals * np.log(lam) - lam - gammaln(goals + 1.0)
    return np.exp(log_p)


def _neg_binom_pmf(mu: float, alpha: float, goals: np.ndarray) -> np.ndarray:
    """Evaluate mean-parameterized Negative Binomial PMF (Var = mu + alpha * mu^2)."""
    if mu <= 0.0:
        out = np.zeros_like(goals, dtype=float)
        out[0] = 1.0
        return out
    if alpha <= 1e-8:
        return _poisson_pmf(mu, goals)

    r = 1.0 / alpha
    log_p = (
        gammaln(goals + r)
        - gammaln(r)
        - gammaln(goals + 1.0)
        + r * np.log(r / (r + mu))
        + goals * np.log(mu / (r + mu))
    )
    return np.exp(log_p)


def _apply_dixon_coles_low_scores(
    matrix: np.ndarray, mu_h: float, mu_a: float, rho: float
) -> np.ndarray:
    """Apply safe Dixon-Coles low-score dependence on (0,0), (1,0), (0,1), (1,1)."""
    if abs(rho) < 1e-9 or matrix.shape[0] < 2 or matrix.shape[1] < 2:
        return matrix
    # Keep multiplier safely positive even at extreme blowout rates.
    lam_prod = max(mu_h * mu_a, 1e-6)
    safe_rho = float(np.clip(rho, -0.95 / max(1.0, lam_prod), 0.95))
    adjusted = matrix.copy()
    adjusted[0, 0] *= max(0.05, 1.0 - lam_prod * safe_rho)
    adjusted[1, 0] *= max(0.05, 1.0 + mu_a * safe_rho)
    adjusted[0, 1] *= max(0.05, 1.0 + mu_h * safe_rho)
    adjusted[1, 1] *= max(0.05, 1.0 - safe_rho)
    total = float(adjusted.sum())
    return adjusted / total if total > 0.0 else matrix


def _marginal_pmf(mu: float, alpha_nb: float, com_nu: float, goals: np.ndarray) -> np.ndarray:
    """Evaluate marginal count PMF selecting Negative Binomial, COM-Poisson, or Poisson."""
    if alpha_nb > 1e-8:
        return _neg_binom_pmf(mu, alpha_nb, goals)
    if abs(com_nu - 1.0) > 1e-6:
        return com_poisson_pmf(mu, nu=com_nu, max_goals=int(goals[-1]))
    return _poisson_pmf(mu, goals)


def negative_binomial_score_matrix(
    mu_h: float,
    mu_a: float,
    alpha_nb: float = 0.10,
    rho: float = DEFAULT_RHO,
    shared_kappa: float = 0.10,
    max_goals: int = 14,
    com_nu: float = 1.0,
) -> np.ndarray:
    """Build a (max_goals+1)x(max_goals+1) regime-calibrated bivariate goal score matrix.

    Combines team-level dispersion (Negative Binomial ``alpha_nb`` or COM-Poisson
    ``com_nu``) with a shared match-tempo Gamma factor (``shared_kappa``) integrated
    via generalized Gauss-Laguerre quadrature, plus Dixon-Coles low-score ``rho``.
    """
    mu_h = float(max(mu_h, 1e-4))
    mu_a = float(max(mu_a, 1e-4))
    goals = np.arange(max_goals + 1, dtype=float)

    if shared_kappa <= 1e-6:
        mat = np.outer(
            _marginal_pmf(mu_h, alpha_nb, com_nu, goals),
            _marginal_pmf(mu_a, alpha_nb, com_nu, goals),
        )
    else:
        shape_k = 1.0 / float(shared_kappa)
        nodes, weights = roots_genlaguerre(16, shape_k - 1.0)
        norm_weights = weights / np.exp(gammaln(shape_k))
        scale_factors = nodes / shape_k
        mat = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
        for s_val, w_val in zip(scale_factors, norm_weights):
            pmf_h = _marginal_pmf(mu_h * float(s_val), alpha_nb, com_nu, goals)
            pmf_a = _marginal_pmf(mu_a * float(s_val), alpha_nb, com_nu, goals)
            mat += float(w_val) * np.outer(pmf_h, pmf_a)

    total = float(mat.sum())
    if total > 0.0:
        mat /= total
    # Taper Dixon-Coles low-score (0-0 / 1-1) adjustment smoothly on high-total shootouts (tot > 2.8)
    # so 3.5-4.5 xG matches do not artificially elevate 1-1 / 0-0 above true shootout scorelines.
    tot_mu = mu_h + mu_a
    eff_rho = float(rho * np.exp(-max(0.0, tot_mu - 2.8) / 1.2))
    return _apply_dixon_coles_low_scores(mat, mu_h, mu_a, eff_rho)


regime_score_matrix = negative_binomial_score_matrix


def matrix_over_probability(score_matrix: np.ndarray, line: float) -> float:
    """Compute push-excluded Over probability for an arbitrary O/U goal line."""
    n_h, n_a = score_matrix.shape
    h_idx, a_idx = np.indices((n_h, n_a))
    tot = h_idx + a_idx

    frac = round(line % 1.0, 2)
    if np.isclose(frac, 0.25) or np.isclose(frac, 0.75):
        sub1 = matrix_over_probability(score_matrix, line - 0.25)
        sub2 = matrix_over_probability(score_matrix, line + 0.25)
        return 0.5 * (sub1 + sub2)

    p_over = float(score_matrix[tot > line + 1e-9].sum())
    p_push = float(score_matrix[np.isclose(tot, line)].sum()) if np.isclose(frac, 0.0) else 0.0
    denom = max(1.0 - p_push, 1e-12)
    return float(np.clip(p_over / denom, 0.0, 1.0))


def matrix_ah_home_win_share(score_matrix: np.ndarray, ah_line: float) -> float:
    """Compute push-excluded home-cover share on Asian Handicap line ``ah_line``."""
    n_h, n_a = score_matrix.shape
    h_idx, a_idx = np.indices((n_h, n_a))
    margin = (h_idx - a_idx) + ah_line

    frac = abs(ah_line) % 1.0
    if np.isclose(frac, 0.25) or np.isclose(frac, 0.75):
        s1 = matrix_ah_home_win_share(score_matrix, ah_line - 0.25)
        s2 = matrix_ah_home_win_share(score_matrix, ah_line + 0.25)
        return 0.5 * (s1 + s2)

    p_win = float(score_matrix[margin > 1e-9].sum())
    p_loss = float(score_matrix[margin < -1e-9].sum())
    denom = max(p_win + p_loss, 1e-12)
    return float(np.clip(p_win / denom, 0.0, 1.0))


def matrix_1x2(score_matrix: np.ndarray) -> np.ndarray:
    """Return (P(H), P(D), P(A)) directly from an arbitrary score matrix."""
    p_draw = float(np.trace(score_matrix))
    # Row index h > col index a (home wins) lies in the lower triangle.
    p_home = float(np.tril(score_matrix, k=-1).sum())
    p_away = float(np.triu(score_matrix, k=1).sum())
    probs = np.array([p_home, p_draw, p_away], dtype=float)
    s = float(probs.sum())
    return probs / s if s > 0.0 else np.array([1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0])


def fit_tail_rates_from_markets(
    p_1x2: Sequence[float] | None = None,
    ou_line: float | None = None,
    p_over: float | None = None,
    ah_line: float | None = None,
    p_ah_home: float | None = None,
    p_btts: float | None = None,
    ou_lines: Iterable[tuple[float, float]] | None = None,
    seed_rates: tuple[float, float] = (1.4, 1.1),
    alpha_nb: float = 0.10,
    rho: float = DEFAULT_RHO,
    shared_kappa: float = 0.10,
    max_goals: int = 14,
    fund_weight: float = 0.15,
    com_nu: float = 1.0,
) -> tuple[float, float, np.ndarray]:
    """Fit overdispersed scoring rates (mu_h, mu_a) jointly against live markets and seed prior."""
    seed_h = float(np.clip(seed_rates[0], 0.08, 7.5))
    seed_a = float(np.clip(seed_rates[1], 0.08, 7.5))

    ou_constraints: list[tuple[float, float]] = []
    if ou_lines is not None:
        for line, prob in ou_lines:
            if line is not None and prob is not None and 0.01 < float(prob) < 0.99:
                ou_constraints.append((float(line), float(prob)))
    if ou_line is not None and p_over is not None and 0.01 < float(p_over) < 0.99:
        pair = (float(ou_line), float(p_over))
        if pair not in ou_constraints:
            ou_constraints.append(pair)

    p1x2_arr: np.ndarray | None = None
    if p_1x2 is not None and len(p_1x2) == 3:
        raw = np.clip(np.asarray(p_1x2, dtype=float), 1e-4, 1.0)
        p1x2_arr = raw / raw.sum()

    has_ou_or_ah = bool(ou_constraints) or (ah_line is not None and p_ah_home is not None)
    # Keep total-goal regularization lighter when O/U lines already anchor the total,
    # stronger when only 1X2 is priced without a total market.
    prior_w = float(fund_weight) * (0.45 if has_ou_or_ah else 1.25)

    def _loss(theta: np.ndarray) -> float:
        mu_h = float(np.exp(theta[0]))
        mu_a = float(np.exp(theta[1]))
        mat = negative_binomial_score_matrix(
            mu_h,
            mu_a,
            alpha_nb=alpha_nb,
            rho=rho,
            shared_kappa=shared_kappa,
            max_goals=max_goals,
            com_nu=com_nu,
        )
        loss_val = 0.0

        if p1x2_arr is not None:
            m_1x2 = np.clip(matrix_1x2(mat), 1e-6, 1.0)
            loss_val += 3.5 * float(np.sum(p1x2_arr * np.log(p1x2_arr / m_1x2)))

        for line, target_over in ou_constraints:
            m_over = float(np.clip(matrix_over_probability(mat, line), 1e-6, 1.0 - 1e-6))
            t_ov = float(np.clip(target_over, 1e-6, 1.0 - 1e-6))
            kl = t_ov * np.log(t_ov / m_over) + (1.0 - t_ov) * np.log((1.0 - t_ov) / (1.0 - m_over))
            loss_val += 5.0 * float(kl)

        if ah_line is not None and p_ah_home is not None:
            m_ah = float(np.clip(matrix_ah_home_win_share(mat, float(ah_line)), 1e-6, 1.0 - 1e-6))
            t_ah = float(np.clip(float(p_ah_home), 1e-6, 1.0 - 1e-6))
            kl_ah = t_ah * np.log(t_ah / m_ah) + (1.0 - t_ah) * np.log((1.0 - t_ah) / (1.0 - m_ah))
            loss_val += 4.5 * float(kl_ah)

        if p_btts is not None:
            m_btts = float(np.clip(mat[1:, 1:].sum(), 1e-6, 1.0 - 1e-6))
            t_btts = float(np.clip(float(p_btts), 1e-6, 1.0 - 1e-6))
            kl_b = t_btts * np.log(t_btts / m_btts) + (1.0 - t_btts) * np.log(
                (1.0 - t_btts) / (1.0 - m_btts)
            )
            # In lopsided blowouts (max 1X2 >= 0.72), 1X2+O/U cannot uniquely separate
            # underdog scoring rate; weight BTTS more strongly so mu_underdog stays anchored.
            btts_w = 4.5 if (p1x2_arr is not None and float(np.max(p1x2_arr)) >= 0.72) else 2.5
            loss_val += btts_w * float(kl_b)

        # Log-space regularization toward domain-calibrated seed rates.
        loss_val += prior_w * (
            (theta[0] - np.log(seed_h)) ** 2 + (theta[1] - np.log(seed_a)) ** 2
        )
        return loss_val

    if p1x2_arr is None and not ou_constraints and ah_line is None and p_btts is None:
        mat = negative_binomial_score_matrix(
            seed_h,
            seed_a,
            alpha_nb=alpha_nb,
            rho=rho,
            shared_kappa=shared_kappa,
            max_goals=max_goals,
            com_nu=com_nu,
        )
        return seed_h, seed_a, mat

    # Smart initialization if a main O/U line and 1X2 exist.
    init_h, init_a = seed_h, seed_a
    if ou_constraints and not has_ou_or_ah:
        pass
    elif ou_constraints and p1x2_arr is not None:
        highest_line, highest_over = max(ou_constraints, key=lambda x: x[0])
        approx_tot = max(0.8, highest_line + (highest_over - 0.5) * 1.4)
        home_share = float(np.clip(p1x2_arr[0] + 0.5 * p1x2_arr[1], 0.08, 0.92))
        init_h = max(0.10, approx_tot * home_share)
        init_a = max(0.10, approx_tot * (1.0 - home_share))

    x0 = np.log([init_h, init_a])
    bounds = [(np.log(0.05), np.log(9.5)), (np.log(0.05), np.log(9.5))]
    res = minimize(_loss, x0=x0, method="L-BFGS-B", bounds=bounds, options={"eps": 1e-6})
    mu_h = float(np.exp(res.x[0]))
    mu_a = float(np.exp(res.x[1]))
    final_mat = negative_binomial_score_matrix(
        mu_h,
        mu_a,
        alpha_nb=alpha_nb,
        rho=rho,
        shared_kappa=shared_kappa,
        max_goals=max_goals,
        com_nu=com_nu,
    )
    return mu_h, mu_a, final_mat


def summarize_tail_goals(score_matrix: np.ndarray, top_k: int = 5) -> TailGoalSummary:
    """Extract total-goal moments and exact extreme tail probabilities (>=4, >=5, >=6, >=7)."""
    n_h, n_a = score_matrix.shape
    h_idx, a_idx = np.indices((n_h, n_a))
    tot = h_idx + a_idx

    e_home = float(np.sum(h_idx * score_matrix))
    e_away = float(np.sum(a_idx * score_matrix))
    e_tot = float(np.sum(tot * score_matrix))
    e_tot2 = float(np.sum((tot**2) * score_matrix))
    var_tot = max(0.0, e_tot2 - e_tot**2)

    p1x2 = matrix_1x2(score_matrix)
    p_btts = float(score_matrix[1:, 1:].sum()) if n_h > 1 and n_a > 1 else 0.0

    p_4plus = float(score_matrix[tot >= 4].sum())
    p_5plus = float(score_matrix[tot >= 5].sum())
    p_6plus = float(score_matrix[tot >= 6].sum())
    p_7plus = float(score_matrix[tot >= 7].sum())
    fair_odds_6plus = 1.0 / p_6plus if p_6plus > 1e-6 else float("inf")

    mask = tot >= 6
    cand_coords = np.argwhere(mask)
    ranked = sorted(
        ((f"{int(h)}-{int(a)}", float(score_matrix[h, a])) for h, a in cand_coords),
        key=lambda item: item[1],
        reverse=True,
    )

    return TailGoalSummary(
        expected_total=e_tot,
        variance_total=var_tot,
        expected_home=e_home,
        expected_away=e_away,
        p_home=float(p1x2[0]),
        p_draw=float(p1x2[1]),
        p_away=float(p1x2[2]),
        p_btts=p_btts,
        p_4plus=p_4plus,
        p_5plus=p_5plus,
        p_6plus=p_6plus,
        p_7plus=p_7plus,
        fair_odds_6plus=fair_odds_6plus,
        top_6plus_scorelines=tuple(ranked[:top_k]),
    )
