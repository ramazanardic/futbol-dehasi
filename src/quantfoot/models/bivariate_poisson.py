"""Diagonal-Inflated Bivariate Poisson model (Karlis & Ntzoufras, 2003)."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp


def _bivariate_poisson_log_pmf(
    x: np.ndarray,
    y: np.ndarray,
    lam1: np.ndarray,
    lam2: np.ndarray,
    lam3: np.ndarray,
) -> np.ndarray:
    """Evaluate log P(X=x, Y=y) for Bivariate Poisson(lam1, lam2, lam3) safely."""
    max_k = int(np.max(np.minimum(x, y))) if len(x) else 0
    k_vals = np.arange(max_k + 1, dtype=np.float64)[None, :]  # (1, K)
    min_xy = np.minimum(x, y)[:, None]  # (N, 1)
    valid = k_vals <= min_xy

    x_col = x[:, None]
    y_col = y[:, None]
    safe_l1 = np.maximum(lam1[:, None], 1e-9)
    safe_l2 = np.maximum(lam2[:, None], 1e-9)
    safe_l3 = np.maximum(lam3[:, None], 1e-12)

    terms = (
        (x_col - k_vals) * np.log(safe_l1)
        - gammaln(np.maximum(x_col - k_vals + 1.0, 1.0))
        + (y_col - k_vals) * np.log(safe_l2)
        - gammaln(np.maximum(y_col - k_vals + 1.0, 1.0))
        + k_vals * np.log(safe_l3)
        - gammaln(k_vals + 1.0)
    )
    terms = np.where(valid, terms, -np.inf)
    return -(lam1 + lam2 + lam3) + logsumexp(terms, axis=1)


class DiagonalBivariatePoisson:
    """Karlis & Ntzoufras (2003) Bivariate Poisson with geometric diagonal inflation."""

    def __init__(self, xi: float = 0.0020, l2_reg: float = 0.08, max_goals: int = 8) -> None:
        self.xi = xi
        self.l2_reg = l2_reg
        self.max_goals = max_goals

        self.teams: list[str] = []
        self.team_to_idx: dict[str, int] = {}
        self.attack: np.ndarray = np.array([])
        self.defense: np.ndarray = np.array([])
        self.home_adv: float = 0.25
        self.intercept: float = 0.0
        self.lambda3: float = 0.06
        self.diag_weight: float = 0.02
        self.diag_theta: float = 0.45
        self.is_fitted: bool = False

    def fit(
        self,
        home_teams: Iterable[str],
        away_teams: Iterable[str],
        home_goals: Iterable[float],
        away_goals: Iterable[float],
        days_ago: Iterable[float],
    ) -> "DiagonalBivariatePoisson":
        """Fit BVP team strengths, shared covariance lambda3, and diagonal inflation."""
        h_list = list(home_teams)
        a_list = list(away_teams)
        teams = sorted(set(h_list).union(set(a_list)))
        self.teams = teams
        self.team_to_idx = {t: i for i, t in enumerate(teams)}
        n_teams = len(teams)

        h_idx = np.array([self.team_to_idx[t] for t in h_list], dtype=np.int32)
        a_idx = np.array([self.team_to_idx[t] for t in a_list], dtype=np.int32)
        hg = np.rint(np.asarray(list(home_goals), dtype=np.float64)).astype(np.int32)
        ag = np.rint(np.asarray(list(away_goals), dtype=np.float64)).astype(np.int32)
        w = np.exp(-self.xi * np.asarray(list(days_ago), dtype=np.float64))
        w /= np.mean(w)

        is_diag = hg == ag
        x0 = np.zeros(2 * n_teams + 5, dtype=np.float64)
        x0[2 * n_teams] = 0.25
        x0[2 * n_teams + 1] = math.log(max(float(np.mean(ag)), 0.4))
        x0[2 * n_teams + 2] = -2.8  # log(lambda3) ~ 0.06
        x0[2 * n_teams + 3] = -3.5  # logit(diag_weight) ~ 0.03
        x0[2 * n_teams + 4] = 0.0   # logit(diag_theta) ~ 0.50

        def _loss(params: np.ndarray) -> float:
            att = params[:n_teams]
            defn = params[n_teams : 2 * n_teams]
            att_c = att - np.mean(att)
            defn_c = defn - np.mean(defn)
            h_adv = params[2 * n_teams]
            mu0 = params[2 * n_teams + 1]
            lam3 = math.exp(float(np.clip(params[2 * n_teams + 2], -6.0, -0.7)))
            w_diag = 1.0 / (1.0 + math.exp(-float(np.clip(params[2 * n_teams + 3], -7.0, -1.0))))
            theta = 1.0 / (1.0 + math.exp(-float(np.clip(params[2 * n_teams + 4], -3.0, 3.0))))

            lam1 = np.exp(np.clip(mu0 + att_c[h_idx] - defn_c[a_idx] + h_adv, -4.0, 2.5))
            lam2 = np.exp(np.clip(mu0 + att_c[a_idx] - defn_c[h_idx], -4.0, 2.5))
            lam3_arr = np.full_like(lam1, lam3)

            bp_prob = np.exp(_bivariate_poisson_log_pmf(hg, ag, lam1, lam2, lam3_arr))
            # Geometric distribution on diagonal d = 0, 1, 2, ...
            diag_pmf = np.where(is_diag, theta * ((1.0 - theta) ** hg), 0.0)
            mix_prob = np.maximum((1.0 - w_diag) * bp_prob + w_diag * diag_pmf, 1e-12)

            reg = 0.5 * self.l2_reg * (np.sum(att**2) + np.sum(defn**2)) + 10.0 * (
                np.mean(att) ** 2 + np.mean(defn) ** 2
            )
            return float(-np.sum(w * np.log(mix_prob)) + reg)

        bounds = (
            [(-2.5, 2.5)] * (2 * n_teams)
            + [(-0.5, 1.5), (-1.5, 1.5), (-6.0, -0.7), (-7.0, -1.0), (-3.0, 3.0)]
        )
        res = minimize(_loss, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 180})
        p = res.x
        self.attack = p[:n_teams] - np.mean(p[:n_teams])
        self.defense = p[n_teams : 2 * n_teams] - np.mean(p[n_teams : 2 * n_teams])
        self.home_adv = float(p[2 * n_teams])
        self.intercept = float(p[2 * n_teams + 1])
        self.lambda3 = math.exp(float(p[2 * n_teams + 2]))
        self.diag_weight = 1.0 / (1.0 + math.exp(-float(p[2 * n_teams + 3])))
        self.diag_theta = 1.0 / (1.0 + math.exp(-float(p[2 * n_teams + 4])))
        self.is_fitted = True
        return self

    def score_matrix(self, home_team: str, away_team: str) -> np.ndarray:
        """Compute normalized (M+1, M+1) DIBP joint probability matrix."""
        if not self.is_fitted:
            raise RuntimeError("DiagonalBivariatePoisson must be fitted before predicting.")

        ha = float(self.attack[self.team_to_idx[home_team]]) if home_team in self.team_to_idx else 0.0
        hd = float(self.defense[self.team_to_idx[home_team]]) if home_team in self.team_to_idx else 0.0
        aa = float(self.attack[self.team_to_idx[away_team]]) if away_team in self.team_to_idx else 0.0
        ad = float(self.defense[self.team_to_idx[away_team]]) if away_team in self.team_to_idx else 0.0

        lam1 = math.exp(float(np.clip(self.intercept + ha - ad + self.home_adv, -3.0, 2.5)))
        lam2 = math.exp(float(np.clip(self.intercept + aa - hd, -3.0, 2.5)))
        lam3 = self.lambda3

        m = self.max_goals + 1
        gi, gj = np.meshgrid(np.arange(m), np.arange(m), indexing="ij")
        x_flat = gi.ravel()
        y_flat = gj.ravel()
        n = len(x_flat)

        bp_flat = np.exp(
            _bivariate_poisson_log_pmf(
                x_flat,
                y_flat,
                np.full(n, lam1),
                np.full(n, lam2),
                np.full(n, lam3),
            )
        )
        mat = (1.0 - self.diag_weight) * bp_flat.reshape(m, m)
        for d in range(m):
            mat[d, d] += self.diag_weight * self.diag_theta * ((1.0 - self.diag_theta) ** d)
        mat /= np.sum(mat)
        return mat

    def predict_1x2(self, home_team: str, away_team: str) -> np.ndarray:
        """Return [P(H), P(D), P(A)] derived from the DIBP score matrix."""
        mat = self.score_matrix(home_team, away_team)
        return np.array(
            [
                float(np.sum(np.tril(mat, -1))),
                float(np.sum(np.diag(mat))),
                float(np.sum(np.triu(mat, 1))),
            ]
        )
