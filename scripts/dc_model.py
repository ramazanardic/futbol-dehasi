"""Independent goal model per league with penaltyblog's Dixon-Coles (MIT-style open source, pip install penaltyblog;
user request, 21 Nov): a fourth view next to market, simulation and team history.

The model is fitted on the league's own played games of this season — openfootball (with dates, so recent games weigh
more: Dixon-Coles time decay xi=0.0065/day) or the Wikipedia season table (equal weights) — and predicts the score
matrix of the match. Half scores are split from the full-time goals with the 44 % first-half share, so every
goal-based bet name of the system (scripts/derin_arastirma.py grammar) can be priced on it.

It needs at least 40 played league games and 4 games of each team; otherwise there is no fourth view for the match.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from math import comb
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402
import openfootball_gecmis as of  # noqa: E402
import wiki_gecmis as wg  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402

MIN_GAMES, MIN_TEAM = 40, 4
XI = 0.0065
HT_SHARE = 0.44
G = 9


def league_results(league: str, day: dt.date) -> tuple[list[tuple], str]:
    """[(date | None, home, away, home goals, away goals)] of the league's played games, and the source name."""
    games = of.played(of.league_file(league, day), day)
    if games:
        return [(dt.date.fromisoformat(x["date"]), x["team1"], x["team2"], x["score"]["ft"][0], x["score"]["ft"][1])
                for x in games], "openfootball"
    s = wg.season_for(league)
    if s:
        _, names, rows = s
        return [(None, names.get(h, h), names.get(a, a), gh, ga) for h, a, gh, ga in rows], "Wikipedia"
    return [], ""


@lru_cache(maxsize=64)
def _fit(league: str, day: dt.date):
    import penaltyblog as pb
    rows, src = league_results(league, day)
    if len(rows) < MIN_GAMES:
        return None, src, {}
    w = [np.exp(-XI * (day - d).days) if d else 1.0 for d, *_ in rows]
    model = pb.models.DixonColesGoalModel([r[3] for r in rows], [r[4] for r in rows], [r[1] for r in rows],
                                          [r[2] for r in rows], weights=w)
    model.fit()
    counts: dict[str, int] = {}
    for _, h, a, *_ in rows:
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    return model, src, counts


def half_joint(ft: np.ndarray) -> np.ndarray:
    """(h1, a1, h2, a2) distribution from a full-time score matrix, first-half goals ~ Binomial(goals, HT_SHARE)."""
    joint = np.zeros((G, G, G, G))
    n = min(ft.shape[0], 2 * G - 1)
    for h in range(n):
        for a in range(n):
            p = ft[h, a]
            if p <= 0:
                continue
            for h1 in range(max(0, h - G + 1), min(h, G - 1) + 1):
                ph = comb(h, h1) * HT_SHARE ** h1 * (1 - HT_SHARE) ** (h - h1)
                for a1 in range(max(0, a - G + 1), min(a, G - 1) + 1):
                    pa = comb(a, a1) * HT_SHARE ** a1 * (1 - HT_SHARE) ** (a - a1)
                    joint[h1, a1, h - h1, a - a1] += p * ph * pa
    return joint / joint.sum()


def match_view(m: dict) -> tuple[np.ndarray, dict] | None:
    """(joint distribution, info) of a Nesine match from the league model, or None when it cannot be fitted."""
    day = dt.datetime.fromisoformat(m["kickoff_iso"]).date()
    try:
        model, src, counts = _fit(m["league"].strip(), day)
    except Exception:  # noqa: BLE001 — a league that fails to converge only loses its fourth view
        return None
    if model is None:
        return None
    names = {t: t for t in counts}
    home, away = wg.match_team(m["home"], names), wg.match_team(m["away"], names)
    if not home or not away or home == away or min(counts[home], counts[away]) < MIN_TEAM:
        return None
    try:
        p = model.predict(home, away)
    except ValueError:  # a poorly identified fit (small league sample) gives an invalid score matrix: no view
        return None
    joint = half_joint(np.asarray(p.goal_matrix, dtype=float))
    return joint, {"source": src, "home": home, "away": away,
                   "xg": [round(float(p.home_goal_expectation), 2), round(float(p.away_goal_expectation), 2)]}


def bet_probability(name: str, joint: np.ndarray) -> float | None:
    try:
        return float(goal_probability(name, joint))
    except (KeyError, ValueError):
        return None
