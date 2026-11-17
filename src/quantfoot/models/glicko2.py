"""Adaptive Glicko-2 rating system for association football with off-season RD inflation."""

from __future__ import annotations

import math

import pandas as pd

from quantfoot.models.pyramid import TIER_ELO_CENTERS, regress_glicko_for_division


class FootballGlicko2:
    """Tracks team strength (mu), rating uncertainty (phi / RD), and volatility (sigma)."""

    SCALE = 173.7178

    def __init__(
        self,
        home_adv: float = 0.35,
        base_rd: float = 110.0,
        offseason_days: int = 75,
        offseason_reversion: float = 0.94,
    ) -> None:
        self.home_adv = home_adv
        self.base_rd = base_rd
        self.offseason_days = offseason_days
        self.offseason_reversion = offseason_reversion

        self.mu: dict[str, float] = {}
        self.phi: dict[str, float] = {}
        self.sigma: dict[str, float] = {}
        self.last_date: dict[str, pd.Timestamp] = {}
        self.last_div: dict[str, str] = {}

    def _get_state(
        self,
        team: str,
        match_date: pd.Timestamp | None,
        div: str | None = None,
    ) -> tuple[float, float, float]:
        raw_mu = self.mu.get(team)
        phi = self.phi.get(team, self.base_rd / self.SCALE)
        sig = self.sigma.get(team, 0.06)

        if div is not None:
            mu, phi = regress_glicko_for_division(raw_mu, phi, self.last_div.get(team), div, scale=self.SCALE)
        else:
            mu = 0.0 if raw_mu is None else raw_mu

        if match_date is not None and team in self.last_date:
            if (match_date - self.last_date[team]).days >= self.offseason_days:
                phi = min(math.sqrt(phi * phi + 0.14), 180.0 / self.SCALE)
                if div is not None:
                    center = (TIER_ELO_CENTERS.get(div, 1500.0) - 1550.0) / self.SCALE
                    mu = center + self.offseason_reversion * (mu - center)
                else:
                    mu = mu * self.offseason_reversion
        return mu, phi, sig

    @staticmethod
    def _g(phi: float) -> float:
        return 1.0 / math.sqrt(1.0 + 3.0 * (phi * phi) / (math.pi * math.pi))

    def get_rating(
        self,
        team: str,
        match_date: pd.Timestamp | None = None,
        div: str | None = None,
    ) -> tuple[float, float]:
        """Return (Elo-equivalent rating centered at 1500, RD in Elo units)."""
        mu, phi, _ = self._get_state(team, match_date, div=div)
        center = 1550.0 if div is not None else 1500.0
        return center + mu * self.SCALE, phi * self.SCALE

    def pre_match_features(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp | None = None,
        neutral: bool = False,
        div: str | None = None,
    ) -> dict[str, float]:
        """Extract uncertainty-aware pre-match Glicko-2 features."""
        mh, ph, _ = self._get_state(home, match_date, div=div)
        ma, pa, _ = self._get_state(away, match_date, div=div)
        hfa = 0.0 if neutral else self.home_adv
        diff = (mh + hfa) - ma
        comb_phi = math.sqrt(ph * ph + pa * pa)
        exp_h = 1.0 / (1.0 + math.exp(-self._g(comb_phi) * diff))
        return {
            "glicko_diff": float(diff),
            "glicko_uncert": float(comb_phi),
            "glicko_exp_h": float(exp_h),
        }

    def update(
        self,
        home: str,
        away: str,
        hg: float,
        ag: float,
        match_date: pd.Timestamp,
        neutral: bool = False,
        div: str | None = None,
    ) -> None:
        """Update rating, deviation, and volatility after a match with margin-scaled score."""
        mh, ph, sh = self._get_state(home, match_date, div=div)
        ma, pa, sa = self._get_state(away, match_date, div=div)
        hfa = 0.0 if neutral else self.home_adv

        gd = hg - ag
        if gd > 0:
            score_h = min(0.68 + 0.12 * math.log1p(gd), 1.0)
        elif gd < 0:
            score_h = max(0.32 - 0.12 * math.log1p(-gd), 0.0)
        else:
            score_h = 0.50
        score_a = 1.0 - score_h

        def _step(mu_i: float, phi_i: float, sig_i: float, mu_j: float, phi_j: float, s_i: float, offset: float) -> tuple[float, float, float]:
            g_j = self._g(phi_j)
            e_val = 1.0 / (1.0 + math.exp(-g_j * ((mu_i + offset) - mu_j)))
            v = 1.0 / max(g_j * g_j * e_val * (1.0 - e_val), 1e-6)
            delta = v * g_j * (s_i - e_val)
            phi_star = math.sqrt(phi_i * phi_i + sig_i * sig_i)
            new_phi = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
            new_mu = mu_i + new_phi * new_phi * g_j * (s_i - e_val)
            new_sig = min(max(0.95 * sig_i + 0.05 * min(abs(delta) * 0.04, 0.12), 0.03), 0.12)
            return new_mu, new_phi, new_sig

        self.mu[home], self.phi[home], self.sigma[home] = _step(mh, ph, sh, ma, pa, score_h, hfa)
        self.mu[away], self.phi[away], self.sigma[away] = _step(ma, pa, sa, mh, ph, score_a, -hfa)
        self.last_date[home] = match_date
        self.last_date[away] = match_date
        if div is not None:
            self.last_div[home] = div
            self.last_div[away] = div
