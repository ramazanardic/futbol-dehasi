"""Correlated Gamma-Poisson half-split pricing for 1H BTTS, 2H BTTS, and Both-Halves BTTS."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln, roots_genlaguerre

_HALF_MODEL_PROFILES: tuple[tuple[str, tuple[float, float, float, float, float]], ...] = (
    # (token, (first_half_share, match_kappa, half_alpha, fgm_1h, fgm_2h))
    # Club baselines calibrated on 184,276 historical HT+FT matches (emp_a1=0.4403)
    # and verified out-of-sample on 34,463 matches (kappa=0.025, fgm_1h=0.08).
    ("eng.u21", (0.452, 0.055, 0.00, 0.10, 0.02)),
    ("gelisim", (0.452, 0.055, 0.00, 0.10, 0.02)),
    ("u21", (0.450, 0.055, 0.00, 0.10, 0.02)),
    ("isthmian", (0.446, 0.045, 0.00, 0.09, 0.01)),
    ("nonleague", (0.445, 0.045, 0.00, 0.09, 0.01)),
    ("nifl", (0.445, 0.045, 0.00, 0.09, 0.01)),
    ("uefa.euro.u19", (0.445, 0.055, 0.00, 0.09, 0.02)),
    ("uefa.euro.u17", (0.445, 0.055, 0.00, 0.09, 0.02)),
    ("fifa.world.u17", (0.440, 0.055, 0.00, 0.09, 0.02)),
    ("wchampions", (0.440, 0.050, 0.00, 0.09, 0.01)),
    ("eng.w.", (0.442, 0.050, 0.00, 0.09, 0.01)),
    ("reina", (0.438, 0.045, 0.00, 0.08, 0.01)),
    ("eng.trophy", (0.440, 0.040, 0.00, 0.08, 0.00)),
    ("copa_del_rey", (0.435, 0.040, 0.00, 0.08, 0.00)),
    ("bra.1", (0.418, 0.030, 0.00, 0.08, 0.00)),
    ("per.1", (0.422, 0.030, 0.00, 0.08, 0.00)),
    ("bol.", (0.428, 0.035, 0.00, 0.08, 0.00)),
    ("col.", (0.420, 0.030, 0.00, 0.08, 0.00)),
    ("concacaf", (0.430, 0.045, 0.00, 0.09, 0.01)),
    ("tur.3", (0.432, 0.035, 0.00, 0.08, 0.00)),
    ("uefa.nations", (0.432, 0.035, 0.00, 0.08, 0.00)),
    ("fifa.friendly", (0.430, 0.045, 0.00, 0.08, 0.01)),
    ("caf.", (0.415, 0.035, 0.00, 0.08, 0.00)),
    # Exact historical football-data divisions (184,276 matches):
    ("e0", (0.444, 0.025, 0.00, 0.08, 0.00)),
    ("e1", (0.439, 0.025, 0.00, 0.08, 0.00)),
    ("e2", (0.444, 0.025, 0.00, 0.08, 0.00)),
    ("e3", (0.441, 0.025, 0.00, 0.08, 0.00)),
    ("ec", (0.443, 0.025, 0.00, 0.08, 0.00)),
    ("d1", (0.442, 0.025, 0.00, 0.08, 0.00)),
    ("d2", (0.435, 0.025, 0.00, 0.08, 0.00)),
    ("n1", (0.433, 0.025, 0.00, 0.08, 0.00)),
    ("t1", (0.434, 0.025, 0.00, 0.08, 0.00)),
    ("sp1", (0.443, 0.025, 0.00, 0.08, 0.00)),
    ("i1", (0.438, 0.025, 0.00, 0.08, 0.00)),
    ("i2", (0.451, 0.025, 0.00, 0.08, 0.00)),
    ("f1", (0.440, 0.025, 0.00, 0.08, 0.00)),
    ("p1", (0.445, 0.025, 0.00, 0.08, 0.00)),
)


@dataclass(frozen=True)
class HalvesBttsSummary:
    """Consistent joint probabilities for 1H, 2H, Both-Halves, and Full-Time BTTS."""

    mu_home: float
    mu_away: float
    expected_total: float
    attack_symmetry: float
    first_half_share: float
    p_1h_kg: float
    p_2h_kg: float
    p_both_halves_kg: float
    p_either_half_kg: float
    p_ft_kg: float
    p_2h_kg_given_1h_kg: float
    fair_odds_1h_kg: float
    fair_odds_2h_kg: float
    fair_odds_both_halves: float
    fair_odds_ft_kg: float


def half_model_params(league_slug: str | None) -> tuple[float, float, float, float, float]:
    """Return empirically calibrated (first_half_share, match_kappa, half_alpha, fgm_1h, fgm_2h)."""
    if not league_slug:
        return (0.440, 0.025, 0.00, 0.08, 0.00)
    low = league_slug.lower()
    for token, profile in _HALF_MODEL_PROFILES:
        if token in low:
            return profile
    return (0.440, 0.025, 0.00, 0.08, 0.00)


def half_timing_profile(league_slug: str | None) -> tuple[float, float, float]:
    """Return (first_half_share, match_kappa, half_alpha) for a competition."""
    a1, kappa, h_alpha, _, _ = half_model_params(league_slug)
    return (a1, kappa, h_alpha)


def _prob_zero_nb(mu: float, alpha: float) -> float:
    """Exact P(X = 0) under mean-parameterized Negative Binomial (or Poisson when alpha <= 0)."""
    if mu <= 0.0:
        return 1.0
    if alpha <= 1e-8:
        return float(np.exp(-mu))
    inv_a = 1.0 / alpha
    return float(np.exp(-inv_a * np.log1p(alpha * mu)))


def compute_halves_btts(
    mu_home: float,
    mu_away: float,
    first_half_share: float = 0.440,
    match_kappa: float = 0.025,
    half_alpha: float = 0.00,
    btts_persistence: float = 1.0,
    fgm_1h: float = 0.08,
    fgm_2h: float = 0.00,
) -> HalvesBttsSummary:
    """Compute correlated Both-Halves BTTS and derivative half-KG probabilities.

    Uses 16-point generalized Gauss-Laguerre quadrature over a shared Gamma
    match-tempo factor ``G_match ~ Gamma(1/match_kappa, match_kappa)`` combined
    with FGM within-half Home-Away co-scoring dependence (``fgm_1h``, ``fgm_2h``)
    and optional per-half Negative Binomial dispersion ``half_alpha``.
    """
    mu_h = float(max(mu_home, 1e-4))
    mu_a = float(max(mu_away, 1e-4))
    a1 = float(np.clip(first_half_share, 0.30, 0.55))
    a2 = 1.0 - a1
    persist = float(np.clip(btts_persistence, 0.85, 1.15))
    f1 = float(np.clip(fgm_1h, -1.0, 1.0))
    f2 = float(np.clip(fgm_2h, -1.0, 1.0))

    if match_kappa <= 1e-6:
        nodes_scale = np.array([1.0], dtype=float)
        weights_norm = np.array([1.0], dtype=float)
    else:
        shape_k = 1.0 / float(match_kappa)
        nodes, weights = roots_genlaguerre(16, shape_k - 1.0)
        nodes_scale = nodes / shape_k
        weights_norm = weights / np.exp(gammaln(shape_k))

    p_1h = 0.0
    p_2h = 0.0
    p_both = 0.0
    p_ft = 0.0

    for s_val, w_val in zip(nodes_scale, weights_norm):
        s = float(s_val)
        w = float(w_val)

        p0_1h_h = _prob_zero_nb(a1 * mu_h * s, half_alpha)
        p0_1h_a = _prob_zero_nb(a1 * mu_a * s, half_alpha)
        p0_2h_h = _prob_zero_nb(a2 * mu_h * s, half_alpha)
        p0_2h_a = _prob_zero_nb(a2 * mu_a * s, half_alpha)

        ph1, pa1 = 1.0 - p0_1h_h, 1.0 - p0_1h_a
        ph2, pa2 = 1.0 - p0_2h_h, 1.0 - p0_2h_a
        d1 = f1 * ph1 * pa1 * p0_1h_h * p0_1h_a
        d2 = f2 * ph2 * pa2 * p0_2h_h * p0_2h_a

        q1 = float(np.clip(ph1 * pa1 + d1, 0.0, min(ph1, pa1)))
        q2 = float(np.clip(ph2 * pa2 + d2, 0.0, min(ph2, pa2)))
        q2_cond = min(1.0, q2 * persist)
        p00_ft = (p0_1h_h * p0_1h_a + d1) * (p0_2h_h * p0_2h_a + d2)
        q_ft = float(np.clip(1.0 - p0_1h_h * p0_2h_h - p0_1h_a * p0_2h_a + p00_ft, max(q1, q2), 1.0))

        p_1h += w * q1
        p_2h += w * q2
        p_both += w * min(q_ft, q1 * q2_cond)
        p_ft += w * q_ft

    p_1h = float(np.clip(p_1h, 0.0, 1.0))
    p_2h = float(np.clip(p_2h, 0.0, 1.0))
    p_both = float(np.clip(p_both, 0.0, min(p_1h, p_2h)))
    p_either = float(np.clip(p_1h + p_2h - p_both, max(p_1h, p_2h), p_ft))
    p_ft = float(np.clip(p_ft, p_either, 1.0))

    sym = float(min(mu_h, mu_a) / max(mu_h, mu_a))
    p_cond = float(p_both / p_1h) if p_1h > 1e-8 else 0.0

    def _fair(p: float) -> float:
        return 1.0 / p if p > 1e-6 else float("inf")

    return HalvesBttsSummary(
        mu_home=mu_h,
        mu_away=mu_a,
        expected_total=mu_h + mu_a,
        attack_symmetry=sym,
        first_half_share=a1,
        p_1h_kg=p_1h,
        p_2h_kg=p_2h,
        p_both_halves_kg=p_both,
        p_either_half_kg=p_either,
        p_ft_kg=p_ft,
        p_2h_kg_given_1h_kg=p_cond,
        fair_odds_1h_kg=_fair(p_1h),
        fair_odds_2h_kg=_fair(p_2h),
        fair_odds_both_halves=_fair(p_both),
        fair_odds_ft_kg=_fair(p_ft),
    )
