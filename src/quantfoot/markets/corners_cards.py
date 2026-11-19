"""Corner and card markets with team ratings calibrated on `data/matches.csv`.

Empirical facts (2018/19+, 56,743 matches in 22 divisions, measured in this repository):

* Corners: home 5.35, away 4.47 per match. One team's corners are overdispersed
  (Var/Mean ~ 1.55) but the match total is close to Poisson (Var/Mean ~ 1.18), because home
  and away corners are **negatively** correlated (r = -0.24).  Corners are almost
  uncorrelated with goals (r = -0.01) and corner difference only weakly with goal difference
  (r = +0.05).
* Yellow cards: per team almost Poisson (Var/Mean ~ 0.96) with a positive match-level
  covariance (r = +0.21, a shared referee / match-intensity component).  Away teams receive
  more yellows (2.14 vs 1.90), in line with the referee-bias literature (Goumas 2014,
  doi:10.1080/17461391.2012.686062).  At least one red card in 17.5% of matches.
  Cards are almost uncorrelated with goals (r = -0.04) and with corners (r = -0.04).

Corner model: total T ~ Negative Binomial (Poisson if Var/Mean <= 1) and home corners
H | T ~ Beta-Binomial(T, s, rho).  With rho solved from the moment equations this
reproduces the team overdispersion *and* the negative home/away correlation (implied
r = -0.24 at league-average parameters).  Corner counts are batch-clustered, which is why a
compound / overdispersed model is needed (Yip et al. 2021, arXiv:2112.13001).

Card model: yellows follow a bivariate Poisson with common component lambda_3 = Cov(Y_h, Y_a);
reds are independent Poisson per team.  Card points use 10 per yellow and 25 per red.

Not in the data (assumptions, override when better data exist): the first-half share of
corners (default 0.47) and the settlement rule for a second yellow (counted as one red,
one yellow here, as in most bookmakers' "booking points").
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re

import numpy as np
from scipy.stats import betabinom, binom, nbinom, poisson

# division: (home_corners, away_corners, total_corner_var_mean, team_corner_var_mean,
#            home_yellow, away_yellow, yellow_covariance, home_red, away_red)
LEAGUE_BASELINES: dict[str, tuple[float, ...]] = {
    "B1": (5.482, 4.536, 1.137, 1.472, 1.776, 2.161, 0.228, 0.093, 0.1295),
    "D1": (5.332, 4.423, 1.151, 1.56, 1.787, 2.028, 0.368, 0.0619, 0.0859),
    "D2": (5.513, 4.646, 1.15, 1.439, 2.029, 2.279, 0.203, 0.08, 0.1115),
    "E0": (5.648, 4.696, 1.131, 1.67, 1.667, 1.883, 0.308, 0.0546, 0.0624),
    "E1": (5.578, 4.596, 1.126, 1.464, 1.617, 1.913, 0.231, 0.0491, 0.0686),
    "E2": (5.492, 4.728, 1.172, 1.492, 1.637, 1.888, 0.225, 0.0617, 0.0773),
    "E3": (5.351, 4.582, 1.138, 1.43, 1.587, 1.855, 0.225, 0.0646, 0.0885),
    "F1": (5.201, 4.318, 1.153, 1.523, 1.752, 1.998, 0.211, 0.1188, 0.1331),
    "F2": (4.916, 4.137, 1.174, 1.451, 1.786, 1.976, 0.249, 0.1102, 0.1389),
    "G1": (4.873, 3.754, 1.148, 1.625, 2.326, 2.823, 0.437, 0.1026, 0.1415),
    "I1": (5.311, 4.397, 1.248, 1.629, 2.046, 2.344, 0.278, 0.0961, 0.1078),
    "I2": (5.202, 4.512, 1.144, 1.439, 2.367, 2.605, 0.25, 0.1172, 0.1464),
    "N1": (5.643, 4.579, 1.172, 1.786, 1.343, 1.63, 0.259, 0.081, 0.0918),
    "P1": (5.38, 4.6, 1.201, 1.71, 2.486, 2.661, 0.596, 0.1358, 0.1572),
    "SC0": (5.606, 4.806, 1.2, 1.778, 1.652, 1.925, 0.187, 0.092, 0.105),
    "SC1": (5.596, 4.736, 1.244, 1.591, 1.673, 1.884, 0.282, 0.0703, 0.0755),
    "SC2": (5.141, 4.711, 1.199, 1.561, 1.628, 1.879, 0.28, 0.083, 0.0935),
    "SC3": (5.122, 4.543, 1.149, 1.424, 1.805, 1.963, 0.21, 0.0881, 0.1104),
    "SP1": (5.246, 4.147, 1.147, 1.527, 2.326, 2.486, 0.515, 0.1162, 0.1241),
    "SP2": (5.136, 4.076, 1.118, 1.434, 2.391, 2.597, 0.332, 0.1162, 0.1518),
    "T1": (5.243, 4.385, 1.14, 1.512, 2.202, 2.312, 0.516, 0.112, 0.1371),
}
GLOBAL_BASELINE: tuple[float, ...] = (5.349, 4.473, 1.18, 1.545, 1.897, 2.141, 0.40, 0.089, 0.110)
DEFAULT_HT_CORNER_SHARE = 0.47  # assumption: no half-time corner counts in the data


def league_baseline(division: str | None) -> tuple[float, ...]:
    """Per-division corner / card parameters (global average for unknown competitions)."""
    return LEAGUE_BASELINES.get((division or "").upper(), GLOBAL_BASELINE)


# --------------------------------------------------------------------------------------
# Corners
# --------------------------------------------------------------------------------------
def corner_joint_pmf(
    exp_home: float,
    exp_away: float,
    total_var_mean: float = 1.18,
    team_var_mean: float = 1.545,
    max_corners: int = 35,
) -> np.ndarray:
    """Joint pmf P(H = h, A = a) of home / away corners (negative-correlation model)."""
    mh, ma = max(exp_home, 0.05), max(exp_away, 0.05)
    m = mh + ma
    s = mh / m
    t = np.arange(max_corners + 1)
    if total_var_mean > 1.0 + 1e-6:
        r = m / (total_var_mean - 1.0)
        p_t = nbinom.pmf(t, r, r / (r + m))
    else:
        p_t = poisson.pmf(t, m)
    p_t = p_t / p_t.sum()
    var_t = float(np.sum(t**2 * p_t) - np.sum(t * p_t) ** 2)
    e_tt1 = float(np.sum(t * (t - 1) * p_t))
    target = team_var_mean * (mh + ma)  # Var(H) + Var(A)
    ss = s * (1.0 - s)
    rho = (target - 2.0 * m * ss - (s**2 + (1.0 - s) ** 2) * var_t) / max(2.0 * ss * e_tt1, 1e-12)
    rho = float(np.clip(rho, 1e-4, 0.5))
    a, b = s * (1.0 / rho - 1.0), (1.0 - s) * (1.0 / rho - 1.0)
    mat = np.zeros((max_corners + 1, max_corners + 1))
    for tot in t:
        h = np.arange(tot + 1)
        mat[h, tot - h] += p_t[tot] * betabinom.pmf(h, tot, a, b)
    return mat / mat.sum()


@dataclass(frozen=True)
class CornerDistribution:
    """Joint corner distribution with market pricing helpers."""

    pmf: np.ndarray
    ht_share: float = DEFAULT_HT_CORNER_SHARE

    @classmethod
    def from_expectations(cls, exp_home: float, exp_away: float, division: str | None = None, **kw) -> "CornerDistribution":
        base = league_baseline(division)
        return cls(corner_joint_pmf(exp_home, exp_away, base[2], base[3]), **kw)

    def _grid(self) -> tuple[np.ndarray, np.ndarray]:
        return np.indices(self.pmf.shape)

    def event_mask(self, name: str) -> np.ndarray:
        """Mask over (home, away) corners for full-match corner selections."""
        h, a = self._grid()
        s = name.strip()
        m = re.fullmatch(r"(?:(Ev|Dep) )?Korner (\d+\.5) (Üst|Alt)", s)
        if m:
            val = {"Ev": h, "Dep": a}.get(m.group(1), h + a)
            over = val > float(m.group(2))
            return over if m.group(3) == "Üst" else ~over
        m = re.fullmatch(r"Korner ([10X2])", s)
        if m:
            code = {"1": 1, "0": 0, "X": 0, "2": -1}[m.group(1)]
            return np.sign(h - a) == code
        m = re.fullmatch(r"Korner (Tek|Çift)", s)
        if m:
            odd = (h + a) % 2 == 1
            return odd if m.group(1) == "Tek" else ~odd
        m = re.fullmatch(r"Korner Hnd (Ev|Dep) ([+-]\d+\.5)", s)
        if m:
            diff = (h - a) if m.group(1) == "Ev" else (a - h)
            return diff + float(m.group(2)) > 0
        raise KeyError(f"Bilinmeyen korner seçimi: {name!r}")

    def prob(self, name: str) -> float:
        return float(self.pmf[self.event_mask(name)].sum())

    def expected(self) -> tuple[float, float]:
        h, a = self._grid()
        return float((h * self.pmf).sum()), float((a * self.pmf).sum())

    def markets(self) -> dict[str, dict[str, float]]:
        h, a = self._grid()
        tot_lines = [6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]
        team_lines = [2.5, 3.5, 4.5, 5.5, 6.5, 7.5]
        totals = {f"Korner {ln} {s}": self.prob(f"Korner {ln} {s}") for ln in tot_lines for s in ("Üst", "Alt")}
        team = {f"{t} Korner {ln} {s}": self.prob(f"{t} Korner {ln} {s}") for t in ("Ev", "Dep") for ln in team_lines for s in ("Üst", "Alt")}
        hnd = {f"Korner Hnd {t} {ln:+.1f}": self.prob(f"Korner Hnd {t} {ln:+.1f}") for t in ("Ev", "Dep") for ln in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5)}
        # First corner: with proportional corner intensities the first corner is home with prob s.
        e_h, e_a = self.expected()
        p_none = float(self.pmf[0, 0])
        first = {
            "İlk Korner Ev": (1.0 - p_none) * e_h / (e_h + e_a),
            "İlk Korner Dep": (1.0 - p_none) * e_a / (e_h + e_a),
            "İlk Korner Yok": p_none,
        }
        # First-half corners: binomial thinning of the match total with the first-half share.
        tot_pmf = np.bincount((h + a).ravel(), self.pmf.ravel())
        n_tot = np.arange(len(tot_pmf))
        ht = {}
        for ln in (2.5, 3.5, 4.5, 5.5, 6.5):
            p_over = float(np.sum(tot_pmf * binom.sf(int(ln), n_tot, self.ht_share)))
            ht[f"İY Korner {ln} Üst"] = p_over
            ht[f"İY Korner {ln} Alt"] = 1.0 - p_over
        return {
            "Toplam Korner": totals,
            "Takım Korner": team,
            "Korner Handikabı": hnd,
            "En Çok Korner": {f"Korner {c}": self.prob(f"Korner {c}") for c in "102"},
            "Korner Tek/Çift": {"Korner Tek": self.prob("Korner Tek"), "Korner Çift": self.prob("Korner Çift")},
            "İlk Korner": first,
            "İY Korner": ht,
        }


# --------------------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class CardDistribution:
    """Joint distribution of (home yellows, away yellows, home reds, away reds)."""

    pmf: np.ndarray  # shape (Y, Y, R, R)
    yellow_points: int = 10
    red_points: int = 25

    @classmethod
    def from_expectations(
        cls,
        exp_yellow_home: float,
        exp_yellow_away: float,
        exp_red_home: float = 0.089,
        exp_red_away: float = 0.110,
        yellow_cov: float = 0.40,
        max_yellow: int = 14,
        max_red: int = 3,
    ) -> "CardDistribution":
        yh, ya = max(exp_yellow_home, 0.05), max(exp_yellow_away, 0.05)
        lam3 = float(np.clip(yellow_cov, 0.0, 0.9 * min(yh, ya)))
        k = np.arange(max_yellow + 1)
        p1, p2, p3 = poisson.pmf(k, yh - lam3), poisson.pmf(k, ya - lam3), poisson.pmf(k, lam3)
        bp = np.zeros((max_yellow + 1, max_yellow + 1))
        for c, pc in enumerate(p3):  # Y_h = X1 + C, Y_a = X2 + C
            if pc < 1e-15:
                continue
            bp[c:, c:] += pc * np.outer(p1[: max_yellow + 1 - c], p2[: max_yellow + 1 - c])
        r = np.arange(max_red + 1)
        rh, ra = poisson.pmf(r, max(exp_red_home, 1e-4)), poisson.pmf(r, max(exp_red_away, 1e-4))
        pmf = bp[:, :, None, None] * rh[None, None, :, None] * ra[None, None, None, :]
        return cls(pmf=pmf / pmf.sum())

    @classmethod
    def for_division(cls, division: str | None, yellow_factor_home: float = 1.0, yellow_factor_away: float = 1.0) -> "CardDistribution":
        b = league_baseline(division)
        return cls.from_expectations(b[4] * yellow_factor_home, b[5] * yellow_factor_away, b[7] * yellow_factor_home, b[8] * yellow_factor_away, b[6])

    def _grid(self) -> tuple[np.ndarray, ...]:
        return np.indices(self.pmf.shape)

    def event_mask(self, name: str) -> np.ndarray:
        yh, ya, rh, ra = self._grid()
        s = name.strip()
        m = re.fullmatch(r"(?:(Ev|Dep) )?Kart (\d+\.5) (Üst|Alt)", s)
        if m:
            val = {"Ev": yh + rh, "Dep": ya + ra}.get(m.group(1), yh + ya + rh + ra)
            over = val > float(m.group(2))
            return over if m.group(3) == "Üst" else ~over
        m = re.fullmatch(r"Kart Puanı (\d+\.5) (Üst|Alt)", s)
        if m:
            pts = self.yellow_points * (yh + ya) + self.red_points * (rh + ra)
            over = pts > float(m.group(1))
            return over if m.group(2) == "Üst" else ~over
        m = re.fullmatch(r"(?:(Ev|Dep) )?Kırmızı Kart (Var|Yok)", s)
        if m:
            val = {"Ev": rh, "Dep": ra}.get(m.group(1), rh + ra)
            yes = val >= 1
            return yes if m.group(2) == "Var" else ~yes
        m = re.fullmatch(r"Kart ([10X2])", s)
        if m:
            code = {"1": 1, "0": 0, "X": 0, "2": -1}[m.group(1)]
            return np.sign((yh + rh) - (ya + ra)) == code
        raise KeyError(f"Bilinmeyen kart seçimi: {name!r}")

    def prob(self, name: str) -> float:
        return float(self.pmf[self.event_mask(name)].sum())

    def expected_total(self) -> float:
        yh, ya, rh, ra = self._grid()
        return float(((yh + ya + rh + ra) * self.pmf).sum())

    def markets(self) -> dict[str, dict[str, float]]:
        return {
            "Toplam Kart": {f"Kart {ln} {s}": self.prob(f"Kart {ln} {s}") for ln in (1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5) for s in ("Üst", "Alt")},
            "Takım Kart": {f"{t} Kart {ln} {s}": self.prob(f"{t} Kart {ln} {s}") for t in ("Ev", "Dep") for ln in (0.5, 1.5, 2.5, 3.5) for s in ("Üst", "Alt")},
            "Kart Puanı": {f"Kart Puanı {ln} {s}": self.prob(f"Kart Puanı {ln} {s}") for ln in (15.5, 25.5, 35.5, 45.5, 55.5, 65.5, 75.5) for s in ("Üst", "Alt")},
            "Kırmızı Kart": {n: self.prob(n) for n in ("Kırmızı Kart Var", "Kırmızı Kart Yok", "Ev Kırmızı Kart Var", "Dep Kırmızı Kart Var")},
            "En Çok Kart": {f"Kart {c}": self.prob(f"Kart {c}") for c in "102"},
        }


# --------------------------------------------------------------------------------------
# Team ratings for corners / cards
# --------------------------------------------------------------------------------------
@dataclass
class CornerCardRatings:
    """Exponentially weighted team ratios for corners won / conceded and yellows received / provoked.

    Expected home corners = league home mean x att[home] x def[away] (multiplicative, like
    the goal-based GAP / Maher structure).  Ratios start at 1.0 and are updated causally,
    so the class can be used walk-forward without look-ahead.
    """

    alpha: float = 0.02  # best overall of {0.01, 0.02, 0.03, 0.06, 0.10}, walk-forward 2023-07+ (scripts/evaluate_corner_card_models.py)
    corner_att: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1.0))
    corner_def: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1.0))
    yellow_rec: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1.0))
    yellow_prov: dict[str, float] = field(default_factory=lambda: defaultdict(lambda: 1.0))

    def expected(self, home: str, away: str, division: str | None) -> dict[str, float]:
        b = league_baseline(division)
        c_h = b[0] * self.corner_att[home] * self.corner_def[away]
        c_a = b[1] * self.corner_att[away] * self.corner_def[home]
        y_h = b[4] * self.yellow_rec[home] * self.yellow_prov[away]
        y_a = b[5] * self.yellow_rec[away] * self.yellow_prov[home]
        return {
            "corners_home": c_h, "corners_away": c_a,
            "yellow_home": y_h, "yellow_away": y_a,
            "red_home": b[7] * y_h / b[4], "red_away": b[8] * y_a / b[5],
        }

    def update(self, home: str, away: str, division: str | None, hc: float, ac: float, hy: float, ay: float) -> None:
        b = league_baseline(division)
        a = self.alpha
        # Observed ratio divided by the opponent's current effect isolates each team's own effect.
        if np.isfinite(hc) and np.isfinite(ac):
            self.corner_att[home] += a * (hc / (b[0] * self.corner_def[away]) - self.corner_att[home])
            self.corner_att[away] += a * (ac / (b[1] * self.corner_def[home]) - self.corner_att[away])
            self.corner_def[away] += a * (hc / (b[0] * self.corner_att[home]) - self.corner_def[away])
            self.corner_def[home] += a * (ac / (b[1] * self.corner_att[away]) - self.corner_def[home])
        if np.isfinite(hy) and np.isfinite(ay):
            self.yellow_rec[home] += a * (hy / (b[4] * self.yellow_prov[away]) - self.yellow_rec[home])
            self.yellow_rec[away] += a * (ay / (b[5] * self.yellow_prov[home]) - self.yellow_rec[away])
            self.yellow_prov[away] += a * (hy / (b[4] * self.yellow_rec[home]) - self.yellow_prov[away])
            self.yellow_prov[home] += a * (ay / (b[5] * self.yellow_rec[away]) - self.yellow_prov[home])
        for d in (self.corner_att, self.corner_def, self.yellow_rec, self.yellow_prov):
            for t in (home, away):
                d[t] = float(np.clip(d[t], 0.4, 2.5))
