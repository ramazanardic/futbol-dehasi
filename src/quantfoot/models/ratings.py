"""Strictly causal match-by-match Elo, Pi-Ratings (Constantinou & Fenton), and rolling stats."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from quantfoot.models.pyramid import TIER_ELO_CENTERS, regress_elo_for_division


class CausalRatingEngine:
    """Maintains pre-match causal Elo, Pi-ratings, SOS/game-state xG, and rolling box-score form."""

    def __init__(
        self,
        elo_k: float = 22.0,
        elo_hfa: float = 55.0,
        pi_lam: float = 0.04,
        pi_gamma: float = 0.68,
        pi_c: float = 3.0,
        offseason_days: int = 75,
        reversion_factor: float = 0.92,
    ) -> None:
        self.elo_k = elo_k
        self.elo_hfa = elo_hfa
        self.pi_lam = pi_lam
        self.pi_gamma = pi_gamma
        self.pi_c = pi_c
        self.offseason_days = offseason_days
        self.reversion_factor = reversion_factor

        self.elo: dict[str, float] = {}
        self.pi_h: dict[str, float] = {}
        self.pi_a: dict[str, float] = {}
        self.hist: dict[str, list[dict]] = {}
        self.last_div: dict[str, str] = {}

    def _apply_offseason_reversion(self, team: str, match_date: pd.Timestamp, div: str | None = None) -> None:
        recs = self.hist.get(team)
        if not recs:
            return
        gap = (match_date - recs[-1]["date"]).days
        if gap >= self.offseason_days:
            center = TIER_ELO_CENTERS.get(div, 1500.0) if div is not None else 1500.0
            self.elo[team] = center + self.reversion_factor * (self.get_elo(team, div=div) - center)
            ph, pa = self.get_pi(team)
            self.pi_h[team] = self.reversion_factor * ph
            self.pi_a[team] = self.reversion_factor * pa

    def get_elo(self, team: str, div: str | None = None) -> float:
        raw = self.elo.get(team)
        return regress_elo_for_division(raw, self.last_div.get(team), div, fallback=1500.0)

    def get_pi(self, team: str) -> tuple[float, float]:
        return self.pi_h.get(team, 0.0), self.pi_a.get(team, 0.0)

    def _pi_expected_gd(self, rating: float) -> float:
        sign = 1.0 if rating >= 0.0 else -1.0
        return sign * (10.0 ** (abs(rating) / self.pi_c) - 1.0)

    def team_rolling(self, team: str, window: int = 10) -> dict[str, float | pd.Timestamp]:
        """Compute exponentially recency-weighted causal statistics over last `window` matches."""
        records = self.hist.get(team, [])
        if not records:
            return {
                "n": 0,
                "gf": 1.35,
                "ga": 1.35,
                "xgf": 1.35,
                "xga": 1.35,
                "sot_f": 4.2,
                "sot_a": 4.2,
                "shots_f": 12.0,
                "shots_a": 12.0,
                "pts": 1.35,
                "sos": 0.0,
                "gs_xg": 0.0,
                "ht_gd": 0.0,
                "cards": 2.0,
            }

        sub = records[-window:]
        w = np.exp(np.linspace(-0.8, 0.0, len(sub)))
        w /= np.sum(w)

        def _wavg(key: str, default: float = 0.0) -> float:
            return float(np.sum(np.array([x.get(key, default) for x in sub], dtype=float) * w))

        return {
            "n": len(records),
            "gf": _wavg("gf", 1.35),
            "ga": _wavg("ga", 1.35),
            "xgf": _wavg("xgf", 1.35),
            "xga": _wavg("xga", 1.35),
            "sot_f": _wavg("sot_f", 4.2),
            "sot_a": _wavg("sot_a", 4.2),
            "shots_f": _wavg("shots_f", 12.0),
            "shots_a": _wavg("shots_a", 12.0),
            "pts": _wavg("pts", 1.35),
            "sos": _wavg("sos", 0.0),
            "gs_xg": _wavg("gs_xg", 0.0),
            "ht_gd": _wavg("ht_gd", 0.0),
            "cards": _wavg("cards", 2.0),
            "last_date": sub[-1]["date"],
        }

    def pre_match_features(
        self,
        home: str,
        away: str,
        match_date: pd.Timestamp,
        neutral: bool = False,
        div: str | None = None,
    ) -> dict[str, float]:
        """Extract strictly pre-match causal ratings and form differentials."""
        e_h = self.get_elo(home, div=div)
        e_a = self.get_elo(away, div=div)
        pi_hh, pi_ha = self.get_pi(home)
        pi_ah, pi_aa = self.get_pi(away)

        rh = self.team_rolling(home, 10)
        ra = self.team_rolling(away, 10)
        rh5 = self.team_rolling(home, 5)
        ra5 = self.team_rolling(away, 5)

        rest_h = min((match_date - rh["last_date"]).days, 21) if "last_date" in rh else 7
        rest_a = min((match_date - ra["last_date"]).days, 21) if "last_date" in ra else 7

        hfa = 0.0 if neutral else self.elo_hfa
        elo_diff = (e_h + hfa) - e_a
        elo_exp_h = 1.0 / (1.0 + 10.0 ** (-elo_diff / 400.0))
        pi_exp_gd = self._pi_expected_gd(pi_hh) - self._pi_expected_gd(pi_aa)

        return {
            "elo_home": e_h,
            "elo_away": e_a,
            "elo_diff": elo_diff,
            "elo_exp_h": elo_exp_h,
            "pi_diff_venue": pi_hh - pi_aa,
            "pi_diff_overall": 0.5 * (pi_hh + pi_ha) - 0.5 * (pi_ah + pi_aa),
            "pi_exp_gd": pi_exp_gd,
            "xg_diff_10": (float(rh["xgf"]) - float(rh["xga"])) - (float(ra["xgf"]) - float(ra["xga"])),
            "xg_sum_10": 0.5 * (float(rh["xgf"]) + float(ra["xga"]) + float(ra["xgf"]) + float(rh["xga"])),
            "g_diff_10": (float(rh["gf"]) - float(rh["ga"])) - (float(ra["gf"]) - float(ra["ga"])),
            "xg_luck_h": float(rh["gf"]) - float(rh["xgf"]),
            "xg_luck_a": float(ra["gf"]) - float(ra["xgf"]),
            "sos_xg_diff": float(rh["sos"]) - float(ra["sos"]),
            "gs_xg_diff": float(rh["gs_xg"]) - float(ra["gs_xg"]),
            "ht_gd_diff": float(rh["ht_gd"]) - float(ra["ht_gd"]),
            "cards_diff": float(rh["cards"]) - float(ra["cards"]),
            "sot_diff_10": (float(rh["sot_f"]) - float(rh["sot_a"])) - (float(ra["sot_f"]) - float(ra["sot_a"])),
            "pts_diff_5": float(rh5["pts"]) - float(ra5["pts"]),
            "rest_diff": float(rest_h - rest_a),
            "min_games": float(min(int(rh["n"]), int(ra["n"]))),
        }

    def update(
        self,
        home: str,
        away: str,
        hg: float,
        ag: float,
        hxg: float,
        axg: float,
        hsot: float,
        asot: float,
        hsh: float,
        ash: float,
        match_date: pd.Timestamp,
        neutral: bool = False,
        div: str | None = None,
        ht_gd: float = 0.0,
        cards_h: float = 2.0,
        cards_a: float = 2.0,
    ) -> None:
        """Update Elo, Pi-Ratings, SOS/game-state xG, and team history AFTER a match completes."""
        self._apply_offseason_reversion(home, match_date, div=div)
        self._apply_offseason_reversion(away, match_date, div=div)

        e_h = self.get_elo(home, div=div)
        e_a = self.get_elo(away, div=div)
        hfa = 0.0 if neutral else self.elo_hfa
        exp_h = 1.0 / (1.0 + 10.0 ** (-((e_h + hfa) - e_a) / 400.0))
        actual_h = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        gd = abs(hg - ag)
        mult = math.log1p(gd) * (2.2 / ((abs(e_h - e_a) * 0.001) + 2.2)) if gd > 0 else 1.0
        delta = self.elo_k * max(mult, 0.8) * (actual_h - exp_h)
        self.elo[home] = e_h + delta
        self.elo[away] = e_a - delta

        pi_hh, pi_ha = self.get_pi(home)
        pi_ah, pi_aa = self.get_pi(away)
        pred_gd = self._pi_expected_gd(pi_hh) - self._pi_expected_gd(pi_aa)
        err = (0.65 * (hg - ag) + 0.35 * (hxg - axg)) - pred_gd
        psi = self.pi_c * math.log10(1.0 + abs(err))
        upd = psi if err >= 0.0 else -psi

        self.pi_h[home] = pi_hh + self.pi_lam * upd
        self.pi_a[home] = pi_ha + self.pi_lam * self.pi_gamma * upd
        self.pi_a[away] = pi_aa - self.pi_lam * upd
        self.pi_h[away] = pi_ah - self.pi_lam * self.pi_gamma * upd

        ra_pre = self.team_rolling(away, 10)
        rh_pre = self.team_rolling(home, 10)
        sos_h = (hxg - float(ra_pre["xga"])) - (axg - float(ra_pre["xgf"]))
        sos_a = (axg - float(rh_pre["xga"])) - (hxg - float(rh_pre["xgf"]))
        gs_w = 0.72 if abs(ht_gd) >= 2.0 else 1.0
        gs_hxg = hxg * (0.90 if ht_gd <= -2.0 else (1.06 if ht_gd >= 2.0 else 1.0))
        gs_axg = axg * (0.90 if ht_gd >= 2.0 else (1.06 if ht_gd <= -2.0 else 1.0))

        pts_h = 3.0 if hg > ag else (1.0 if hg == ag else 0.0)
        pts_a = 3.0 if ag > hg else (1.0 if hg == ag else 0.0)
        self.hist.setdefault(home, []).append(
            {
                "date": match_date,
                "gf": float(hg),
                "ga": float(ag),
                "xgf": float(hxg),
                "xga": float(axg),
                "sot_f": float(hsot),
                "sot_a": float(asot),
                "shots_f": float(hsh),
                "shots_a": float(ash),
                "pts": pts_h,
                "sos": float(sos_h),
                "gs_xg": float((gs_hxg - gs_axg) * gs_w),
                "ht_gd": float(ht_gd),
                "cards": float(cards_h),
            }
        )
        self.hist.setdefault(away, []).append(
            {
                "date": match_date,
                "gf": float(ag),
                "ga": float(hg),
                "xgf": float(axg),
                "xga": float(hxg),
                "sot_f": float(asot),
                "sot_a": float(hsot),
                "shots_f": float(ash),
                "shots_a": float(hsh),
                "pts": pts_a,
                "sos": float(sos_a),
                "gs_xg": float((gs_axg - gs_hxg) * gs_w),
                "ht_gd": float(-ht_gd),
                "cards": float(cards_a),
            }
        )
        if div is not None:
            self.last_div[home] = div
            self.last_div[away] = div
