"""Same-game combinations (Bet Builder / Kombine) priced from one coherent model.

Bookmakers price same-game combos from a joint model, not by multiplying leg prices,
because legs within one match are correlated (e.g. "MS 1" and "2.5 Üst" for a strong
favourite).  Following Rana et al. (2026, "ParlayMarket", arXiv:2603.22596), every combo
price here is a marginal of a single joint distribution:

* Goal legs (any name accepted by `goal_markets.goal_event_mask`) are an exact AND over the
  joint goal tensor J[h1, a1, h2, a2].
* "İlk Gol Ev/Dep" and "Son Gol Ev/Dep" use P(team scores first | final score h-a) = h / (h + a),
  exact when both teams' goal intensities share the same time profile.
* Scorer legs ("<oyuncu>: Gol Atar", "...: 2+ Gol", "...: Hat-trick", "...: İlk Golü Atar")
  are priced conditionally on the team's goal count in each joint state by multinomial
  allocation of the team's goals, so "MS 1 & Kane: Gol Atar" is coherent.
* Assist legs are thinned conditionally on team goals, independently of the scorer legs
  (approximation).  Shots / passes / player-card legs are treated as independent of goals.
* Corner legs and card legs are each exact ANDs inside their own joint distributions and
  independent of goals and of each other: in `data/matches.csv` (2018+) corr(total corners,
  goals) = -0.01, corr(total yellows, goals) = -0.04 and corr(corners, yellows) = -0.04.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product as iproduct
from math import factorial
import re

import numpy as np

from quantfoot.markets.corners_cards import CardDistribution, CornerDistribution
from quantfoot.markets.goal_markets import GoalGrid, goal_event_mask, goal_probability
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets.player_markets import PlayerProfile, on_pitch_fraction, price_player_markets

_SCORER_MIN = {"Gol Atar": 1, "2+ Gol": 2, "Hat-trick": 3}


@dataclass(frozen=True)
class BetBuilderQuote:
    """Fair price of a same-game combination."""

    selections: tuple[str, ...]
    probability: float
    fair_odds: float
    independent_product: float  # what naive multiplication of the legs would give
    correlation_ratio: float    # probability / independent_product (>1: legs reinforce each other)
    offered_odds: float | None = None
    ev: float | None = None


def _multinomial_condition(k: int, conds: list[tuple[float, int]]) -> float:
    """P(each listed player i scores >= n_i of k team goals), goals allocated with probs q_i."""
    if not conds:
        return 1.0
    qs = [q for q, _ in conds]
    rest = max(0.0, 1.0 - sum(qs))
    need = [n for _, n in conds]
    if sum(need) > k:
        return 0.0
    total = 0.0
    for alloc in iproduct(*[range(n, k + 1) for n in need]):
        used = sum(alloc)
        if used > k:
            continue
        coef = factorial(k) / (np.prod([factorial(x) for x in alloc]) * factorial(k - used))
        total += coef * np.prod([q**x for q, x in zip(qs, alloc)]) * rest ** (k - used)
    return float(total)


def goal_order_share(g: GoalGrid, which: str, team: str) -> np.ndarray:
    """P(`team` scores the match's first ('İlk') / last ('Son') goal | joint state), goals exchangeable WITHIN a half.

    The first goal is in the first half whenever the first half had one (the last goal in the second half whenever
    it had one). Until 21 Nov the share was taken from full-time totals (h / (h + a)), which is wrong for
    same-match combinations: 1H 0-1 then 2H 2-0 gave 'İlk Gol Ev' weight 2/3 although the away side scored first."""
    own1, own2 = (g.h1, g.h2) if team == "Ev" else (g.a1, g.a2)
    t1, t2 = (g.h1 + g.a1).astype(float), (g.h2 + g.a2).astype(float)
    s1 = np.divide(own1, t1, out=np.zeros_like(t1), where=t1 > 0)
    s2 = np.divide(own2, t2, out=np.zeros_like(t2), where=t2 > 0)
    if which == "İlk":
        return np.where(t1 > 0, s1, s2)
    return np.where(t2 > 0, s2, s1)


def price_bet_builder(
    selections: list[str],
    joint: np.ndarray,
    players: dict[str, PlayerProfile] | None = None,
    corners: CornerDistribution | None = None,
    cards: CardDistribution | None = None,
    timing: GoalTimingModel | None = None,
    offered_odds: float | None = None,
) -> BetBuilderQuote:
    """Price an AND-combination of selections from one match."""
    if not selections:
        raise ValueError("En az bir seçim gerekli.")
    players = players or {}
    timing = timing or GoalTimingModel.from_joint(joint)
    g = GoalGrid(joint)
    weight = g.p.copy()
    singles: list[float] = []
    corner_legs: list[str] = []
    card_legs: list[str] = []
    indep_factor = 1.0
    scorer_conds: dict[str, list[tuple[float, int]]] = {"Ev": [], "Dep": []}
    assist_q: dict[str, list[float]] = {"Ev": [], "Dep": []}
    player_book: dict[str, dict[str, float]] | None = None

    for raw in selections:
        sel = raw.strip()
        m = re.fullmatch(r"(.+?): (.+)", sel)
        if m:
            name, prop = m.group(1).strip(), m.group(2).strip()
            if name not in players:
                raise KeyError(f"Oyuncu profili yok: {name!r}")
            pl = players[name]
            if player_book is None:
                player_book = price_player_markets(joint, list(players.values()), timing)
            if prop not in player_book[name]:
                raise KeyError(f"Bilinmeyen oyuncu pazarı: {prop!r}")
            singles.append(player_book[name][prop])
            q = pl.goal_share * on_pitch_fraction(pl, timing)
            if prop in _SCORER_MIN:
                scorer_conds[pl.team].append((q, _SCORER_MIN[prop]))
            elif prop == "İlk Golü Atar":
                weight = weight * goal_order_share(g, "İlk", pl.team) * pl.goal_share
            elif prop == "Son Golü Atar":
                weight = weight * goal_order_share(g, "Son", pl.team) * pl.goal_share
            elif prop == "Asist Yapar":
                assist_q[pl.team].append(pl.assist_share * on_pitch_fraction(pl, timing))
            else:  # shots / passes / player cards / goal-or-assist: independent of the score
                indep_factor *= player_book[name][prop]
            continue
        m = re.fullmatch(r"(İlk|Son) Gol (Ev|Dep)", sel)
        if m:
            weight = weight * goal_order_share(g, m.group(1), m.group(2))
            singles.append(float(timing.markets()[f"{m.group(1)} Golü Atan Takım"][sel]))
            continue
        if "Korner" in sel:
            if corners is None:
                raise ValueError("Korner seçimi için CornerDistribution gerekli.")
            corner_legs.append(sel)
            singles.append(corners.prob(sel))
            continue
        if "Kart" in sel:
            if cards is None:
                raise ValueError("Kart seçimi için CardDistribution gerekli.")
            card_legs.append(sel)
            singles.append(cards.prob(sel))
            continue
        weight = weight * goal_event_mask(sel, g)
        singles.append(goal_probability(sel, joint))

    # Scorer / assist conditions depend on the team's goal count in each joint state.
    for team, goals in (("Ev", g.fh), ("Dep", g.fa)):
        if scorer_conds[team] or assist_q[team]:
            kmax = int(goals.max())
            table = np.ones(kmax + 1)
            for k in range(kmax + 1):
                table[k] = _multinomial_condition(k, scorer_conds[team])
                for qa in assist_q[team]:
                    table[k] *= 1.0 - (1.0 - qa) ** k
            weight = weight * table[goals]

    prob = float(weight.sum()) * indep_factor
    if corner_legs:
        mask = np.ones_like(corners.pmf, dtype=bool)
        for leg in corner_legs:
            mask &= corners.event_mask(leg)
        prob *= float(corners.pmf[mask].sum())
    if card_legs:
        mask = np.ones_like(cards.pmf, dtype=bool)
        for leg in card_legs:
            mask &= cards.event_mask(leg)
        prob *= float(cards.pmf[mask].sum())

    indep = float(np.prod(singles))
    return BetBuilderQuote(
        selections=tuple(selections),
        probability=prob,
        fair_odds=float("inf") if prob <= 1e-12 else 1.0 / prob,
        independent_product=indep,
        correlation_ratio=prob / indep if indep > 0 else float("nan"),
        offered_odds=offered_odds,
        ev=None if offered_odds is None else prob * offered_odds - 1.0,
    )
