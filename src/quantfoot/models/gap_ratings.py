"""Edward Wheatcroft (2020) Generalised Attacking Performance (GAP) Ratings."""

from __future__ import annotations

from quantfoot.models.pyramid import TIER_ATTACK_SHIFT


class WheatcroftGAPRatings:
    """Maintains four causal attacking/defensive ratings per team using high-frequency match stats."""

    def __init__(
        self,
        lam: float = 0.06,
        phi1: float = 0.70,
        phi2: float = 0.70,
        base_stat: float = 9.0,
    ) -> None:
        self.lam = lam
        self.phi1 = phi1
        self.phi2 = phi2
        self.base_stat = base_stat

        self.home_att: dict[str, float] = {}
        self.home_def: dict[str, float] = {}
        self.away_att: dict[str, float] = {}
        self.away_def: dict[str, float] = {}
        self.last_div: dict[str, str] = {}

    def _half(self) -> float:
        return 0.5 * self.base_stat

    def _adjusted_stats(self, team: str, div: str | None) -> tuple[float, float, float, float]:
        h0 = self._half()
        ha = self.home_att.get(team, h0)
        aa = self.away_att.get(team, h0)
        hd = self.home_def.get(team, h0)
        ad = self.away_def.get(team, h0)
        if div is not None and team in self.last_div and self.last_div[team] != div:
            old_t = TIER_ATTACK_SHIFT.get(self.last_div[team], 0.0)
            new_t = TIER_ATTACK_SHIFT.get(div, 0.0)
            shift = 0.20 * (old_t - new_t) * self.base_stat
            ha = 0.65 * ha + 0.35 * h0
            aa = 0.65 * aa + 0.35 * h0
            hd = 0.65 * hd + 0.35 * h0
            ad = 0.65 * ad + 0.35 * h0
            if new_t > old_t:
                ha = max(ha + shift, 0.2 * h0)
                aa = max(aa + shift, 0.2 * h0)
        return ha, aa, hd, ad

    def expected_stats(self, home: str, away: str, div: str | None = None) -> tuple[float, float]:
        """Predict pre-match attacking volume for (home, away), with optional tier adjustment."""
        ha_h, _, hd_home, _ = self._adjusted_stats(home, div)
        _, aa_a, _, ad_a = self._adjusted_stats(away, div)
        exp_h = max(ha_h + ad_a, 0.5)
        exp_a = max(aa_a + hd_home, 0.5)
        return float(exp_h), float(exp_a)

    def update(self, home: str, away: str, stat_home: float, stat_away: float, div: str | None = None) -> None:
        """Update home and away GAP attack/defense ratings with cross-venue spillover."""
        exp_h, exp_a = self.expected_stats(home, away, div=div)
        err_h = stat_home - exp_h
        err_a = stat_away - exp_a

        ha_h, aa_h, hd_h, ad_h = self._adjusted_stats(home, div)
        ha_a, aa_a, hd_a, ad_a = self._adjusted_stats(away, div)

        self.home_att[home] = max(0.0, ha_h + self.lam * self.phi1 * err_h)
        self.away_att[home] = max(0.0, aa_h + self.lam * (1.0 - self.phi1) * err_h)
        self.away_def[away] = max(0.0, ad_a + self.lam * self.phi2 * err_h)
        self.home_def[away] = max(0.0, hd_a + self.lam * (1.0 - self.phi2) * err_h)

        self.away_att[away] = max(0.0, aa_a + self.lam * self.phi1 * err_a)
        self.home_att[away] = max(0.0, ha_a + self.lam * (1.0 - self.phi1) * err_a)
        self.home_def[home] = max(0.0, hd_h + self.lam * self.phi2 * err_a)
        self.away_def[home] = max(0.0, ad_h + self.lam * (1.0 - self.phi2) * err_a)
        if div is not None:
            self.last_div[home] = div
            self.last_div[away] = div
