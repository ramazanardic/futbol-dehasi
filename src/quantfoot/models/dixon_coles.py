"""Vectorized Time-Decayed Dixon-Coles (1997) model with optional xG-blended likelihood."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


class TimeDecayedDixonColes:
    """Dixon-Coles Poisson goal model with analytical gradients, time decay, and xG blending."""

    def __init__(
        self,
        xi: float = 0.0020,
        l2_reg: float = 0.05,
        max_goals: int = 8,
    ) -> None:
        self.xi = xi
        self.l2_reg = l2_reg
        self.max_goals = max_goals

        self.teams: list[str] = []
        self.team_to_idx: dict[str, int] = {}
        self.attack: np.ndarray = np.array([])
        self.defense: np.ndarray = np.array([])
        self.home_adv: float = 0.25
        self.rho: float = -0.05
        self.intercept: float = 0.0
        self.is_fitted: bool = False

    def fit(
        self,
        home_teams: Iterable[str],
        away_teams: Iterable[str],
        home_goals: Iterable[float],
        away_goals: Iterable[float],
        days_ago: Iterable[float],
        home_xg: Iterable[float] | None = None,
        away_xg: Iterable[float] | None = None,
        xg_weight: float = 0.0,
        neutral_venue: Iterable[bool | float] | None = None,
        sample_weights: Iterable[float] | None = None,
        goal_cap: float | None = None,
    ) -> "TimeDecayedDixonColes":
        """Fit attack, defense, home advantage, and low-score correlation rho via L-BFGS-B."""
        h_list = list(home_teams)
        a_list = list(away_teams)
        teams = sorted(set(h_list).union(set(a_list)))
        self.teams = teams
        self.team_to_idx = {t: i for i, t in enumerate(teams)}
        n_teams = len(teams)

        h_idx = np.array([self.team_to_idx[t] for t in h_list], dtype=np.int32)
        a_idx = np.array([self.team_to_idx[t] for t in a_list], dtype=np.int32)
        hg = np.asarray(list(home_goals), dtype=np.float64)
        ag = np.asarray(list(away_goals), dtype=np.float64)
        if goal_cap is not None:
            hg = np.minimum(hg, goal_cap)
            ag = np.minimum(ag, goal_cap)

        if xg_weight > 0.0 and home_xg is not None and away_xg is not None:
            hxg = np.asarray(list(home_xg), dtype=np.float64)
            axg = np.asarray(list(away_xg), dtype=np.float64)
            hg_eff = (1.0 - xg_weight) * hg + xg_weight * hxg
            ag_eff = (1.0 - xg_weight) * ag + xg_weight * axg
        else:
            hg_eff = hg
            ag_eff = ag

        weights = np.exp(-self.xi * np.asarray(list(days_ago), dtype=np.float64))
        if sample_weights is not None:
            weights = weights * np.asarray(list(sample_weights), dtype=np.float64)
        weights = weights / np.mean(weights)

        if neutral_venue is not None:
            is_home = 1.0 - np.asarray(list(neutral_venue), dtype=np.float64)
        else:
            is_home = np.ones_like(hg_eff)

        hg_int = np.rint(hg).astype(np.int32)
        ag_int = np.rint(ag).astype(np.int32)
        m00 = (hg_int == 0) & (ag_int == 0)
        m01 = (hg_int == 0) & (ag_int == 1)
        m10 = (hg_int == 1) & (ag_int == 0)
        m11 = (hg_int == 1) & (ag_int == 1)

        x0 = np.zeros(2 * n_teams + 3, dtype=np.float64)
        x0[2 * n_teams] = 0.25
        x0[2 * n_teams + 1] = -0.05
        x0[2 * n_teams + 2] = math.log(max(float(np.mean(ag_eff)), 0.4))

        def _objective(params: np.ndarray) -> tuple[float, np.ndarray]:
            return self._nll_and_grad(
                params, n_teams, h_idx, a_idx, hg_eff, ag_eff, weights, m00, m01, m10, m11, is_home
            )

        bounds = [(-2.5, 2.5)] * (2 * n_teams) + [(-0.5, 1.5), (-0.25, 0.25), (-1.5, 1.5)]
        res = minimize(_objective, x0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": 250})

        p = res.x
        self.attack = p[:n_teams] - np.mean(p[:n_teams])
        self.defense = p[n_teams : 2 * n_teams] - np.mean(p[n_teams : 2 * n_teams])
        self.home_adv = float(p[2 * n_teams])
        self.rho = float(p[2 * n_teams + 1])
        self.intercept = float(p[2 * n_teams + 2])
        self.is_fitted = True
        return self

    def _nll_and_grad(
        self,
        params: np.ndarray,
        n_teams: int,
        h_idx: np.ndarray,
        a_idx: np.ndarray,
        hg_eff: np.ndarray,
        ag_eff: np.ndarray,
        w: np.ndarray,
        m00: np.ndarray,
        m01: np.ndarray,
        m10: np.ndarray,
        m11: np.ndarray,
        is_home: np.ndarray | None = None,
    ) -> tuple[float, np.ndarray]:
        att = params[:n_teams]
        defn = params[n_teams : 2 * n_teams]
        att_c = att - np.mean(att)
        defn_c = defn - np.mean(defn)
        h_adv = params[2 * n_teams]
        rho = params[2 * n_teams + 1]
        mu0 = params[2 * n_teams + 2]
        home_ind = 1.0 if is_home is None else is_home

        eta_h = np.clip(mu0 + att_c[h_idx] - defn_c[a_idx] + h_adv * home_ind, -4.0, 3.0)
        eta_a = np.clip(mu0 + att_c[a_idx] - defn_c[h_idx], -4.0, 3.0)
        lam = np.exp(eta_h)
        mu = np.exp(eta_a)

        tau = np.ones_like(lam)
        tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
        tau[m01] = 1.0 + lam[m01] * rho
        tau[m10] = 1.0 + mu[m10] * rho
        tau[m11] = 1.0 - rho
        if np.any(tau <= 1e-6):
            return 1e9, np.zeros_like(params)

        ll = w * (hg_eff * eta_h - lam + ag_eff * eta_a - mu + np.log(tau))
        reg = 0.5 * self.l2_reg * (np.sum(att**2) + np.sum(defn**2)) + 10.0 * (
            np.mean(att) ** 2 + np.mean(defn) ** 2
        )
        nll = -np.sum(ll) + reg

        d_nll_d_eta_h = w * (lam - hg_eff)
        d_nll_d_eta_a = w * (mu - ag_eff)

        d_tau_lam = np.zeros_like(lam)
        d_tau_mu = np.zeros_like(mu)
        d_tau_rho = np.zeros_like(lam)

        d_tau_lam[m00] = -mu[m00] * rho / tau[m00]
        d_tau_mu[m00] = -lam[m00] * rho / tau[m00]
        d_tau_rho[m00] = -lam[m00] * mu[m00] / tau[m00]

        d_tau_lam[m01] = rho / tau[m01]
        d_tau_rho[m01] = lam[m01] / tau[m01]

        d_tau_mu[m10] = rho / tau[m10]
        d_tau_rho[m10] = mu[m10] / tau[m10]

        d_tau_rho[m11] = -1.0 / tau[m11]

        d_nll_d_eta_h -= w * d_tau_lam * lam
        d_nll_d_eta_a -= w * d_tau_mu * mu

        g_att_c = np.bincount(h_idx, weights=d_nll_d_eta_h, minlength=n_teams) + np.bincount(
            a_idx, weights=d_nll_d_eta_a, minlength=n_teams
        )
        g_def_c = -np.bincount(a_idx, weights=d_nll_d_eta_h, minlength=n_teams) - np.bincount(
            h_idx, weights=d_nll_d_eta_a, minlength=n_teams
        )

        g_att = g_att_c - np.mean(g_att_c) + self.l2_reg * att + 20.0 * np.mean(att) / n_teams
        g_def = g_def_c - np.mean(g_def_c) + self.l2_reg * defn + 20.0 * np.mean(defn) / n_teams
        g_hadv = np.sum(d_nll_d_eta_h * home_ind)
        g_rho = -np.sum(w * d_tau_rho)
        g_mu0 = np.sum(d_nll_d_eta_h + d_nll_d_eta_a)

        return float(nll), np.concatenate([g_att, g_def, [g_hadv, g_rho, g_mu0]])

    def expected_goals(self, home_team: str, away_team: str, neutral: bool = False) -> tuple[float, float]:
        """Return (lambda_home, mu_away) expected scoring rates."""
        if not self.is_fitted:
            raise RuntimeError("TimeDecayedDixonColes must be fitted before predicting.")
        ha = float(self.attack[self.team_to_idx[home_team]]) if home_team in self.team_to_idx else 0.0
        hd = float(self.defense[self.team_to_idx[home_team]]) if home_team in self.team_to_idx else 0.0
        aa = float(self.attack[self.team_to_idx[away_team]]) if away_team in self.team_to_idx else 0.0
        ad = float(self.defense[self.team_to_idx[away_team]]) if away_team in self.team_to_idx else 0.0
        hfa = 0.0 if neutral else self.home_adv
        lam = math.exp(float(np.clip(self.intercept + ha - ad + hfa, -3.0, 2.5)))
        mu = math.exp(float(np.clip(self.intercept + aa - hd, -3.0, 2.5)))
        return lam, mu

    def score_matrix(self, home_team: str, away_team: str, neutral: bool = False) -> np.ndarray:
        """Compute normalized (M+1, M+1) joint probability matrix P(X=i, Y=j)."""
        lam, mu = self.expected_goals(home_team, away_team, neutral=neutral)
        g = np.arange(self.max_goals + 1)
        px = np.exp(-lam + g * math.log(lam) - gammaln(g + 1))
        py = np.exp(-mu + g * math.log(mu) - gammaln(g + 1))
        mat = np.outer(px, py)
        mat[0, 0] *= max(1.0 - lam * mu * self.rho, 1e-6)
        mat[0, 1] *= max(1.0 + lam * self.rho, 1e-6)
        mat[1, 0] *= max(1.0 + mu * self.rho, 1e-6)
        mat[1, 1] *= max(1.0 - self.rho, 1e-6)
        mat /= np.sum(mat)
        return mat

    def predict_1x2(self, home_team: str, away_team: str, neutral: bool = False) -> np.ndarray:
        """Return [P(H), P(D), P(A)] derived from the Dixon-Coles score matrix."""
        mat = self.score_matrix(home_team, away_team, neutral=neutral)
        return np.array(
            [
                float(np.sum(np.tril(mat, -1))),
                float(np.sum(np.diag(mat))),
                float(np.sum(np.triu(mat, 1))),
            ]
        )

    def team_ratings_table(self) -> list[dict[str, float | str]]:
        """Return team attack and defense strength parameters sorted by net rating."""
        if not self.is_fitted:
            return []
        rows = [
            {
                "team": t,
                "attack": float(self.attack[i]),
                "defense": float(self.defense[i]),
                "net_strength": float(self.attack[i] + self.defense[i]),
            }
            for i, t in enumerate(self.teams)
        ]
        rows.sort(key=lambda r: r["net_strength"], reverse=True)
        return rows
