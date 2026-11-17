"""Laplace-Extended Kalman Filter State-Space Poisson Goal/xG/SOT Model."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.special import gammaln

from quantfoot.models.pyramid import TIER_ATTACK_SHIFT


class KalmanPoissonModel:
    """Online Bayesian Kalman state-space model over latent team attack, defense, and covariance."""

    def __init__(
        self,
        mu0: float = 0.12,
        home_adv: float = 0.24,
        p0: float = 0.24,
        p_min: float = 0.025,
        p_max: float = 0.35,
        q_match: float = 0.0022,
        q_offseason: float = 0.06,
        offseason_days: int = 75,
        reversion: float = 0.93,
        k_mu0: float = 0.004,
        k_hfa: float = 0.004,
        xg_blend: float = 0.50,
        sot_weight: float = 0.12,
        rho: float = -0.09,
    ) -> None:
        self.default_mu0 = mu0
        self.default_hfa = home_adv
        self.p0 = p0
        self.p_min = p_min
        self.p_max = p_max
        self.q_match = q_match
        self.q_offseason = q_offseason
        self.offseason_days = offseason_days
        self.reversion = reversion
        self.k_mu0 = k_mu0
        self.k_hfa = k_hfa
        self.xg_blend = xg_blend
        self.sot_weight = sot_weight
        self.rho = rho

        self.att: dict[str, float] = {}
        self.defn: dict[str, float] = {}
        self.p_att: dict[str, float] = {}
        self.p_def: dict[str, float] = {}
        self.last_date: dict[str, pd.Timestamp] = {}
        self.last_div: dict[str, str] = {}
        self.div_mu0: dict[str, float] = {}
        self.div_hfa: dict[str, float] = {}

    def _env(self, div: str | None) -> tuple[float, float]:
        key = div or "_default"
        return (
            self.div_mu0.get(key, self.default_mu0),
            self.div_hfa.get(key, self.default_hfa),
        )

    def _match_env(self, home: str, away: str, div: str | None) -> tuple[float, float, float]:
        """Resolve (mu0, home_adv, tier_edge) using league baselines even for cross-league UCL ties."""
        if div is not None:
            mu0, base_hfa = self._env(div)
            return mu0, base_hfa, 0.0
        h_div = self.last_div.get(home)
        a_div = self.last_div.get(away)
        mu0_h = self.div_mu0.get(h_div, self.default_mu0) if h_div else self.default_mu0
        mu0_a = self.div_mu0.get(a_div, self.default_mu0) if a_div else self.default_mu0
        hfa_val = self.div_hfa.get(h_div, self.default_hfa) if h_div else self.default_hfa
        tier_edge = 0.0
        if h_div and a_div and h_div != a_div:
            tier_edge = 0.5 * (TIER_ATTACK_SHIFT.get(h_div, 0.0) - TIER_ATTACK_SHIFT.get(a_div, 0.0))
        return 0.5 * (mu0_h + mu0_a), hfa_val, tier_edge

    def _get_state(
        self,
        team: str,
        match_date: pd.Timestamp | None,
        div: str | None = None,
    ) -> tuple[float, float, float, float]:
        if team not in self.att:
            return -0.08, -0.05, self.p0, self.p0

        ah = self.att[team]
        dh = self.defn[team]
        pa = min(self.p_att[team] + self.q_match, self.p_max)
        pd_v = min(self.p_def[team] + self.q_match, self.p_max)

        if div is not None and team in self.last_div and self.last_div[team] != div:
            delta_t = TIER_ATTACK_SHIFT.get(self.last_div[team], 0.0) - TIER_ATTACK_SHIFT.get(div, 0.0)
            adj = 0.65 * delta_t - (0.05 if delta_t < 0.0 else 0.0)
            ah = float(np.clip(ah + adj, -1.5, 1.5))
            dh = float(np.clip(dh + adj, -1.5, 1.5))
            pa = min(pa + 0.10, self.p_max)
            pd_v = min(pd_v + 0.10, self.p_max)
        elif match_date is not None and team in self.last_date:
            if (match_date - self.last_date[team]).days >= self.offseason_days:
                ah *= self.reversion
                dh *= self.reversion
                pa = min(pa + self.q_offseason, self.p_max)
                pd_v = min(pd_v + self.q_offseason, self.p_max)

        return ah, dh, pa, pd_v

    def expected_goals(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
        neutral: bool = False,
    ) -> tuple[float, float]:
        """Return pre-match expected goals (lambda_home, mu_away)."""
        ah, dh, _, _ = self._get_state(home, match_date, div=div)
        aa, da, _, _ = self._get_state(away, match_date, div=div)
        mu0, base_hfa, tier_edge = self._match_env(home, away, div)
        hfa = 0.0 if neutral else base_hfa
        lam = math.exp(float(np.clip(mu0 + hfa + ah - da + tier_edge, -2.5, 2.0)))
        mu = math.exp(float(np.clip(mu0 + aa - dh - tier_edge, -2.5, 2.0)))
        return lam, mu

    def posterior_uncertainty(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
    ) -> float:
        """Return combined latent parameter standard deviation for the matchup."""
        _, _, pah, pdh = self._get_state(home, match_date, div=div)
        _, _, paa, pda = self._get_state(away, match_date, div=div)
        return float(math.sqrt(pah + pdh + paa + pda))

    def score_matrix(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
        neutral: bool = False,
        max_goals: int = 8,
    ) -> np.ndarray:
        """Compute normalized (M+1, M+1) Dixon-Coles-adjusted Kalman score matrix."""
        lam, mu = self.expected_goals(home, away, match_date=match_date, div=div, neutral=neutral)
        g = np.arange(max_goals + 1)
        px = np.exp(-lam + g * math.log(lam) - gammaln(g + 1))
        py = np.exp(-mu + g * math.log(mu) - gammaln(g + 1))
        mat = np.outer(px, py)
        mat[0, 0] *= max(1.0 - lam * mu * self.rho, 1e-6)
        mat[0, 1] *= max(1.0 + lam * self.rho, 1e-6)
        mat[1, 0] *= max(1.0 + mu * self.rho, 1e-6)
        mat[1, 1] *= max(1.0 - self.rho, 1e-6)
        mat /= np.sum(mat)
        return mat

    def predict_1x2(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
        neutral: bool = False,
    ) -> np.ndarray:
        """Return [P(H), P(D), P(A)] from the Kalman Poisson score matrix."""
        mat = self.score_matrix(home, away, match_date=match_date, div=div, neutral=neutral)
        return np.array(
            [
                float(np.sum(np.tril(mat, -1))),
                float(np.sum(np.diag(mat))),
                float(np.sum(np.triu(mat, 1))),
            ]
        )

    @staticmethod
    def _kalman_pair_step(
        att_i: float,
        def_j: float,
        p_att: float,
        p_def: float,
        y_obs: float,
        rate: float,
    ) -> tuple[float, float, float, float]:
        info = 0.55 * rate
        denom = 1.0 + (p_att + p_def) * info
        k_att = p_att / denom
        k_def = p_def / denom
        err = y_obs - rate
        new_att = float(np.clip(att_i + k_att * err, -1.5, 1.5))
        new_def = float(np.clip(def_j - k_def * err, -1.5, 1.5))
        new_pa = max((1.0 - k_att * info) * p_att, 0.025)
        new_pd = max((1.0 - k_def * info) * p_def, 0.025)
        return new_att, new_def, new_pa, new_pd

    def update(
        self,
        home: str,
        away: str,
        hg: float,
        ag: float,
        hxg: float | None = None,
        axg: float | None = None,
        hsot: float | None = None,
        asot: float | None = None,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
        neutral: bool = False,
        comp_weight: float = 1.0,
    ) -> None:
        """Update attack/defense means and posterior variances via Laplace-Kalman gain."""
        ah, dh, pah, pdh = self._get_state(home, match_date, div=div)
        aa, da, paa, pda = self._get_state(away, match_date, div=div)
        key = div or "_default"
        mu0, base_hfa = self._env(div)
        hfa = 0.0 if neutral else base_hfa

        lam = math.exp(float(np.clip(mu0 + hfa + ah - da, -2.5, 2.0)))
        mu = math.exp(float(np.clip(mu0 + aa - dh, -2.5, 2.0)))

        h_cap = min(hg, 4.5)
        a_cap = min(ag, 4.5)
        eff_h = (1.0 - self.xg_blend) * h_cap + self.xg_blend * hxg if hxg is not None else h_cap
        eff_a = (1.0 - self.xg_blend) * a_cap + self.xg_blend * axg if axg is not None else a_cap

        y_h = (1.0 - self.sot_weight) * eff_h + self.sot_weight * (hsot * 0.30) if hsot is not None else eff_h
        y_a = (1.0 - self.sot_weight) * eff_a + self.sot_weight * (asot * 0.30) if asot is not None else eff_a

        scale_w = float(np.clip(comp_weight, 0.25, 1.50))
        lam_obs = max(0.05, lam)
        mu_obs = max(0.05, mu)

        ah_n, da_n, pah_n, pda_n = self._kalman_pair_step(ah, da, pah * scale_w, pda * scale_w, y_h, lam_obs)
        aa_n, dh_n, paa_n, pdh_n = self._kalman_pair_step(aa, dh, paa * scale_w, pdh * scale_w, y_a, mu_obs)

        self.att[home], self.defn[home] = ah_n, dh_n
        self.att[away], self.defn[away] = aa_n, da_n
        self.p_att[home], self.p_def[home] = min(max(pah_n / scale_w, self.p_min), self.p_max), min(max(pdh_n / scale_w, self.p_min), self.p_max)
        self.p_att[away], self.p_def[away] = min(max(paa_n / scale_w, self.p_min), self.p_max), min(max(pda_n / scale_w, self.p_min), self.p_max)

        sh_g = float(np.clip((hg - lam) / math.sqrt(lam), -3.0, 3.0))
        sa_g = float(np.clip((ag - mu) / math.sqrt(mu), -3.0, 3.0))
        self.div_mu0[key] = float(np.clip(mu0 + self.k_mu0 * 0.5 * (sh_g + sa_g), -0.35, 0.55))
        if not neutral:
            self.div_hfa[key] = float(np.clip(base_hfa + self.k_hfa * (sh_g - sa_g), 0.05, 0.50))

        if match_date is not None:
            self.last_date[home] = match_date
            self.last_date[away] = match_date
        if div is not None:
            self.last_div[home] = div
            self.last_div[away] = div
