"""Goal-timing markets (İlk gol, son gol, gol dakikası aralığı) from a non-homogeneous Poisson model.

Model
-----
Each team scores as a non-homogeneous Poisson process whose intensity is piecewise
constant over six 15-minute bins (stoppage time folded into 31-45 and 76-90):

* Half-level totals are calibrated to the joint goal distribution: the hazard of a half is
  ``-log P(no goal in that half)`` and is split between the teams in proportion to their
  expected goals in that half.  Hence "no goal in the 1st half" agrees exactly with the
  joint, and the 1H/2H goal split follows the league's calibrated first-half share.
* Within a half, the hazard is spread with `DEFAULT_BIN_SHARES`.  Goal intensity rises as a
  match progresses and the opening minutes of each half are quietest (Ayana et al. 2025,
  arXiv:2501.18606); the last 15 minutes carry the largest share (22.7% of World Cup goals
  1966-2018, Mićović et al. 2023, doi:10.3389/fpsyg.2023.954876).  The default profile is a
  literature prior — override it with shares estimated from minute-level data when available.
* Probabilities that condition on "at least one goal" are rescaled so that
  P(no goal in the match) equals the joint's P(0-0).

Limitations: the Poisson timing model ignores bursty same-team clustering after a goal
(Ayana et al. 2025) and score-dependent intensity (Heuer & Rubner 2012; Maia et al. 2023).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BIN_LABELS: tuple[str, ...] = ("1-15", "16-30", "31-45", "46-60", "61-75", "76-90")
BIN_EDGES: tuple[float, ...] = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
# Share of a match's goals per bin (sums to 1); rescaled per half to the calibrated 1H share.
DEFAULT_BIN_SHARES: tuple[float, ...] = (0.125, 0.145, 0.170, 0.165, 0.180, 0.215)


@dataclass(frozen=True)
class GoalTimingModel:
    """Per-bin expected goals for each team plus the joint's P(no goal)."""

    home_hazard: np.ndarray  # expected home goals per bin
    away_hazard: np.ndarray
    p_no_goal: float

    @classmethod
    def from_joint(cls, joint: np.ndarray, bin_shares: tuple[float, ...] = DEFAULT_BIN_SHARES) -> "GoalTimingModel":
        j = np.asarray(joint, dtype=float)
        j = j / j.sum()
        g = j.shape[0]
        ar = np.arange(g)
        m1 = j.sum(axis=(2, 3))  # 1H score
        m2 = j.sum(axis=(0, 1))  # 2H score
        shares = np.asarray(bin_shares, dtype=float)
        if shares.shape != (6,) or np.any(shares <= 0):
            raise ValueError("bin_shares must contain six positive values.")
        home, away = np.zeros(6), np.zeros(6)
        for half, mat, sl in ((0, m1, slice(0, 3)), (1, m2, slice(3, 6))):
            e_h = float((ar[:, None] * mat).sum())
            e_a = float((ar[None, :] * mat).sum())
            lam = -np.log(max(float(mat[0, 0]), 1e-12))  # hazard of "any goal" in this half
            w = shares[sl] / shares[sl].sum()
            frac_h = e_h / max(e_h + e_a, 1e-12)
            home[sl] = lam * frac_h * w
            away[sl] = lam * (1.0 - frac_h) * w
        p00 = float(j[0, 0, 0, 0])  # no goal in either half
        return cls(home_hazard=home, away_hazard=away, p_no_goal=p00)

    # ---- helpers -------------------------------------------------------------------------
    @property
    def total_hazard(self) -> np.ndarray:
        return self.home_hazard + self.away_hazard

    def _first_goal_bins(self) -> np.ndarray:
        """P(first goal falls in bin k), rescaled so the goal-part sums to 1 - P(0-0)."""
        lam = self.total_hazard
        before = np.concatenate([[0.0], np.cumsum(lam)[:-1]])
        raw = np.exp(-before) * (1.0 - np.exp(-lam))
        return raw * (1.0 - self.p_no_goal) / max(raw.sum(), 1e-12)

    def _last_goal_bins(self) -> np.ndarray:
        lam = self.total_hazard
        after = np.concatenate([np.cumsum(lam[::-1])[::-1][1:], [0.0]])
        raw = (1.0 - np.exp(-lam)) * np.exp(-after)
        return raw * (1.0 - self.p_no_goal) / max(raw.sum(), 1e-12)

    def cumulative_hazard(self, t: float, team: str | None = None) -> float:
        """Expected goals in minutes [0, t] (team 'Ev', 'Dep' or None for both)."""
        lam = {"Ev": self.home_hazard, "Dep": self.away_hazard}.get(team, self.total_hazard)
        out = 0.0
        for k in range(6):
            lo, hi = BIN_EDGES[k], BIN_EDGES[k + 1]
            if t <= lo:
                break
            out += lam[k] * (min(t, hi) - lo) / (hi - lo)
        return out

    def p_goal_between(self, t0: float, t1: float, team: str | None = None) -> float:
        """P(at least one goal between minute t0 and t1), stoppage folded into minute 45 / 90."""
        return float(1.0 - np.exp(-(self.cumulative_hazard(t1, team) - self.cumulative_hazard(t0, team))))

    def first_goal_team_bins(self, team: str) -> np.ndarray:
        """P(`team` scores the match's first goal and it falls in bin k)."""
        share = np.divide(
            self.home_hazard if team == "Ev" else self.away_hazard,
            self.total_hazard, out=np.zeros(6), where=self.total_hazard > 0,
        )
        return self._first_goal_bins() * share

    def last_goal_team_bins(self, team: str) -> np.ndarray:
        share = np.divide(
            self.home_hazard if team == "Ev" else self.away_hazard,
            self.total_hazard, out=np.zeros(6), where=self.total_hazard > 0,
        )
        return self._last_goal_bins() * share

    # ---- markets -------------------------------------------------------------------------
    def markets(self) -> dict[str, dict[str, float]]:
        first = self._first_goal_bins()
        last = self._last_goal_bins()
        first_team = {
            "İlk Gol Ev": float(self.first_goal_team_bins("Ev").sum()),
            "İlk Gol Dep": float(self.first_goal_team_bins("Dep").sum()),
            "İlk Gol Yok": self.p_no_goal,
        }
        last_team = {
            "Son Gol Ev": float(self.last_goal_team_bins("Ev").sum()),
            "Son Gol Dep": float(self.last_goal_team_bins("Dep").sum()),
            "Son Gol Yok": self.p_no_goal,
        }
        first_time = {f"İlk Gol {lbl}": float(p) for lbl, p in zip(BIN_LABELS, first)}
        first_time["İlk Gol Yok"] = self.p_no_goal
        last_time = {f"Son Gol {lbl}": float(p) for lbl, p in zip(BIN_LABELS, last)}
        last_time["Son Gol Yok"] = self.p_no_goal
        intervals = {
            f"{lbl} Arası Gol Var": self.p_goal_between(BIN_EDGES[k], BIN_EDGES[k + 1])
            for k, lbl in enumerate(BIN_LABELS)
        }
        intervals["İlk 10 Dakikada Gol Var"] = self.p_goal_between(0.0, 10.0)
        intervals["Son 10 Dakikada Gol Var"] = self.p_goal_between(80.0, 90.0)
        first_median = None
        cdf = np.cumsum(first) / max(1.0 - self.p_no_goal, 1e-12)
        for lbl, c in zip(BIN_LABELS, cdf):
            if c >= 0.5:
                first_median = lbl
                break
        return {
            "İlk Golü Atan Takım": first_team,
            "Son Golü Atan Takım": last_team,
            "İlk Gol Dakikası": first_time,
            "Son Gol Dakikası": last_time,
            "Gol Dakikası Aralığı": intervals,
            "Özet": {"İlk Gol Medyan Aralığı": first_median or BIN_LABELS[-1]},  # type: ignore[dict-item]
        }
