"""Goalscorer and player-prop markets (golcü, asist, şut, isabetli şut, pas, kart).

Goal-linked props are priced *conditionally on the team's goal count* from the joint goal
distribution: each team goal is credited to the player with probability ``q`` (binomial /
multinomial thinning).  This is exact under the common assumption that a team's goals are
allocated to its players independently of the score (Whitaker et al. 2017,
arXiv:1710.00001, model player event abilities as Poisson thinning of the team rate).
Player-level finishing differences persist even after controlling for chance quality
(Scholtes & Karakuş 2023, arXiv:2311.13707), so ``goal_share`` should come from the
player's own record (goals / team goals while on the pitch), ideally shrunk toward the
positional average.

``q`` accounts for playing time: the share of the team's expected goals that fall while
the player is on the pitch, using the goal-timing intensity (starters play minutes
[0, m], substitutes [90 - m, 90]).

Count props (shots, shots on target, passes) use a Negative Binomial with mean
``rate_per90 * minutes / 90 * team_factor``; there is no player data in this repository,
so the dispersion default (alpha = 0.15) is an assumption to be re-estimated from data.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

import numpy as np
from scipy.stats import nbinom

from quantfoot.markets.goal_timing import BIN_EDGES, GoalTimingModel


@dataclass(frozen=True)
class PlayerProfile:
    """Inputs for one player (rates are per 90 minutes; shares are of the team's goals)."""

    name: str
    team: str  # "Ev" or "Dep"
    goal_share: float = 0.0
    assist_share: float = 0.0
    minutes: float = 90.0
    starter: bool = True
    shots_p90: float = 0.0
    sot_p90: float = 0.0
    passes_p90: float = 0.0
    yellow_p90: float = 0.0
    dispersion: float = 0.15

    def __post_init__(self) -> None:
        if self.team not in ("Ev", "Dep"):
            raise ValueError("team must be 'Ev' or 'Dep'.")
        if not 0.0 <= self.goal_share + self.assist_share <= 1.0:
            raise ValueError("goal_share + assist_share must lie in [0, 1].")
        if not 0.0 < self.minutes <= 90.0:
            raise ValueError("minutes must lie in (0, 90].")


def team_goal_pmf(joint: np.ndarray, team: str) -> np.ndarray:
    """P(team scores k goals) from the joint J[h1, a1, h2, a2]."""
    j = np.asarray(joint, dtype=float)
    j = j / j.sum()
    g = j.shape[0]
    i1, j1, i2, j2 = np.indices(j.shape)
    goals = (i1 + i2) if team == "Ev" else (j1 + j2)
    return np.bincount(goals.ravel(), j.ravel(), minlength=2 * g - 1)


def on_pitch_fraction(player: PlayerProfile, timing: GoalTimingModel | None) -> float:
    """Share of the team's expected goals that occur while the player is on the pitch."""
    m = float(player.minutes)
    if m >= 90.0 or timing is None:
        return m / 90.0
    total = timing.cumulative_hazard(90.0, player.team)
    if total <= 0:
        return m / 90.0
    if player.starter:
        return timing.cumulative_hazard(m, player.team) / total
    return (total - timing.cumulative_hazard(90.0 - m, player.team)) / total


def _window_overlap(player: PlayerProfile) -> np.ndarray:
    """Fraction of each 15-minute bin during which the player is on the pitch."""
    lo, hi = (0.0, player.minutes) if player.starter else (90.0 - player.minutes, 90.0)
    out = np.zeros(6)
    for k in range(6):
        a, b = BIN_EDGES[k], BIN_EDGES[k + 1]
        out[k] = max(0.0, min(b, hi) - max(a, lo)) / (b - a)
    return out


def prob_at_least(pmf_team: np.ndarray, q: float, n: int) -> float:
    """P(player credited with >= n of the team's goals), thinning each goal with prob q."""
    total = 0.0
    for k, pk in enumerate(pmf_team):
        if k < n or pk <= 0:
            continue
        below = sum(comb(k, i) * q**i * (1.0 - q) ** (k - i) for i in range(n))
        total += pk * (1.0 - below)
    return float(total)


def _nb_over(mean: float, alpha: float, line: float) -> float:
    """P(X > line) for a mean-parameterised Negative Binomial (Poisson when alpha -> 0)."""
    if mean <= 0:
        return 0.0
    alpha = max(alpha, 1e-6)
    r = 1.0 / alpha
    p = r / (r + mean)
    return float(nbinom.sf(int(np.floor(line)), r, p))


def price_player_markets(
    joint: np.ndarray,
    players: list[PlayerProfile],
    timing: GoalTimingModel | None = None,
    team_factors: dict[str, float] | None = None,
    card_factor: float = 1.0,
    shot_lines: tuple[float, ...] = (0.5, 1.5, 2.5, 3.5),
    sot_lines: tuple[float, ...] = (0.5, 1.5, 2.5),
    pass_lines: tuple[float, ...] = (19.5, 29.5, 39.5, 49.5, 59.5),
) -> dict[str, dict[str, float]]:
    """Price golcü, asist and count props for each player.

    team_factors: optional multiplier per team ("Ev"/"Dep") applied to count-prop rates, e.g.
    this match's expected team shots divided by the team's season average.
    card_factor: this match's expected cards divided by the league average (from the card model).
    """
    timing = timing or GoalTimingModel.from_joint(joint)
    pmfs = {t: team_goal_pmf(joint, t) for t in ("Ev", "Dep")}
    factors = team_factors or {}
    out: dict[str, dict[str, float]] = {}
    for pl in players:
        pmf = pmfs[pl.team]
        on = on_pitch_fraction(pl, timing)
        q_goal = pl.goal_share * on
        q_assist = pl.assist_share * on
        overlap = _window_overlap(pl)
        first = float((timing.first_goal_team_bins(pl.team) * overlap).sum() * pl.goal_share)
        last = float((timing.last_goal_team_bins(pl.team) * overlap).sum() * pl.goal_share)
        mins = pl.minutes / 90.0
        f = factors.get(pl.team, 1.0)
        row = {
            "Gol Atar": prob_at_least(pmf, q_goal, 1),
            "2+ Gol": prob_at_least(pmf, q_goal, 2),
            "Hat-trick": prob_at_least(pmf, q_goal, 3),
            "İlk Golü Atar": first,
            "Son Golü Atar": last,
            "Asist Yapar": prob_at_least(pmf, q_assist, 1),
            "Gol veya Asist": prob_at_least(pmf, min(1.0, q_goal + q_assist), 1),
        }
        if pl.shots_p90 > 0:
            mu = pl.shots_p90 * mins * f
            row.update({f"Şut {ln} Üst": _nb_over(mu, pl.dispersion, ln) for ln in shot_lines})
        if pl.sot_p90 > 0:
            mu = pl.sot_p90 * mins * f
            row.update({f"İsabetli Şut {ln} Üst": _nb_over(mu, pl.dispersion, ln) for ln in sot_lines})
        if pl.passes_p90 > 0:
            mu = pl.passes_p90 * mins
            row.update({f"Pas {ln} Üst": _nb_over(mu, pl.dispersion, ln) for ln in pass_lines})
        if pl.yellow_p90 > 0:
            row["Kart Görür"] = float(1.0 - np.exp(-pl.yellow_p90 * mins * card_factor))
        out[pl.name] = row
    return out
