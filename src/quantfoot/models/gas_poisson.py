"""Koopman & Lit (2015, 2019) Dual-Signal Score-Driven (GAS) Poisson State-Space Goal Model."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.special import gammaln


class GASPoissonModel:
    """Score-driven Poisson model with optional xG dual-signal updates and dynamic home advantage."""

    def __init__(
        self,
        mu0: float = 0.12,
        home_adv: float = 0.25,
        persist: float = 0.994,
        k_att: float = 0.055,
        k_def: float = 0.055,
        k_mu0: float = 0.004,
        k_hfa: float = 0.003,
        xg_blend: float = 0.45,
        rho: float = -0.08,
        fisher_power: float = 0.5,
        offseason_days: int = 75,
        offseason_reversion: float = 0.92,
    ) -> None:
        self.mu0 = mu0
        self.home_adv = home_adv
        self.persist = persist
        self.k_att = k_att
        self.k_def = k_def
        self.k_mu0 = k_mu0
        self.k_hfa = k_hfa
        self.xg_blend = xg_blend
        self.rho = rho
        self.fisher_power = fisher_power
        self.offseason_days = offseason_days
        self.offseason_reversion = offseason_reversion

        self.att: dict[str, float] = {}
        self.defn: dict[str, float] = {}
        self.last_date: dict[str, pd.Timestamp] = {}

    def _apply_offseason_reversion(self, team: str, match_date: pd.Timestamp | None) -> None:
        """Apply Baio-Blangiardo seasonal mean reversion after long summer/tournament breaks."""
        if match_date is None or team not in self.last_date:
            return
        gap = (match_date - self.last_date[team]).days
        if gap >= self.offseason_days:
            self.att[team] = self.att.get(team, 0.0) * self.offseason_reversion
            self.defn[team] = self.defn.get(team, 0.0) * self.offseason_reversion

    def expected_goals(self, home: str, away: str, neutral: bool = False) -> tuple[float, float]:
        """Return pre-match expected goals (lambda_home, mu_away)."""
        ah = self.att.get(home, 0.0)
        dh = self.defn.get(home, 0.0)
        aa = self.att.get(away, 0.0)
        da = self.defn.get(away, 0.0)
        hfa = 0.0 if neutral else self.home_adv
        lam = math.exp(float(np.clip(self.mu0 + hfa + ah - da, -2.5, 2.0)))
        mu = math.exp(float(np.clip(self.mu0 + aa - dh, -2.5, 2.0)))
        return lam, mu

    def score_matrix(self, home: str, away: str, neutral: bool = False, max_goals: int = 8) -> np.ndarray:
        """Compute normalized (M+1, M+1) Dixon-Coles-adjusted score matrix."""
        lam, mu = self.expected_goals(home, away, neutral=neutral)
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

    def predict_1x2(self, home: str, away: str, neutral: bool = False) -> np.ndarray:
        """Return [P(H), P(D), P(A)] from the GAS score matrix."""
        mat = self.score_matrix(home, away, neutral=neutral)
        return np.array(
            [
                float(np.sum(np.tril(mat, -1))),
                float(np.sum(np.diag(mat))),
                float(np.sum(np.triu(mat, 1))),
            ]
        )

    def update(
        self,
        home: str,
        away: str,
        hg: float,
        ag: float,
        hxg: float | None = None,
        axg: float | None = None,
        neutral: bool = False,
        match_date: pd.Timestamp | None = None,
        comp_weight: float = 1.0,
    ) -> None:
        """Update attack, defense, league goal baseline, and dynamic home advantage."""
        self._apply_offseason_reversion(home, match_date)
        self._apply_offseason_reversion(away, match_date)

        lam, mu = self.expected_goals(home, away, neutral=neutral)
        eff_h = ((1.0 - self.xg_blend) * hg + self.xg_blend * hxg) if hxg is not None else hg
        eff_a = ((1.0 - self.xg_blend) * ag + self.xg_blend * axg) if axg is not None else ag

        sh = float(np.clip((eff_h - lam) / (lam**self.fisher_power), -3.0, 3.0)) * comp_weight
        sa = float(np.clip((eff_a - mu) / (mu**self.fisher_power), -3.0, 3.0)) * comp_weight

        ah = self.att.get(home, 0.0)
        dh = self.defn.get(home, 0.0)
        aa = self.att.get(away, 0.0)
        da = self.defn.get(away, 0.0)

        self.att[home] = self.persist * ah + self.k_att * sh
        self.defn[away] = self.persist * da - self.k_def * sh
        self.att[away] = self.persist * aa + self.k_att * sa
        self.defn[home] = self.persist * dh - self.k_def * sa

        # Dynamic league scoring rate & dynamic home advantage driven strictly by goal residuals
        sh_g = float(np.clip((hg - lam) / (lam**self.fisher_power), -3.0, 3.0)) * comp_weight
        sa_g = float(np.clip((ag - mu) / (mu**self.fisher_power), -3.0, 3.0)) * comp_weight
        if self.k_mu0 > 0.0:
            self.mu0 = float(np.clip(self.mu0 + self.k_mu0 * 0.5 * (sh_g + sa_g), -0.35, 0.55))
        if self.k_hfa > 0.0 and not neutral:
            self.home_adv = float(np.clip(self.home_adv + self.k_hfa * (sh_g - sa_g), 0.05, 0.50))

        if match_date is not None:
            self.last_date[home] = match_date
            self.last_date[away] = match_date
