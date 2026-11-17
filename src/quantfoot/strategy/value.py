"""Value bet identification across sharp-reference and multi-market fundamental modes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import softmax

from quantfoot.markets.devig import DevigMethod, devig
from quantfoot.markets.halves_btts import compute_halves_btts, half_model_params
from quantfoot.markets.pricing import expected_ah_ev, price_all_markets
from quantfoot.markets.tail_goals import matrix_over_probability
from quantfoot.strategy.kelly import baker_mchale_kelly_fraction, kelly_fraction


@dataclass(frozen=True)
class BetOpportunity:
    """Structured recommendation for a positive expected-value betting opportunity."""

    market: str
    selection: str
    model_prob: float
    fair_odds: float
    offered_odds: float
    expected_value: float
    kelly_stake: float


def bayesian_log_odds_blend(
    p_market: np.ndarray,
    p_fundamental: np.ndarray,
    fundamental_weight: float = 0.0,
) -> np.ndarray:
    """Combine market prior and fundamental model in log-odds space."""
    w = float(np.clip(fundamental_weight, 0.0, 1.0))
    log_m = np.log(np.clip(p_market, 1e-7, 1.0))
    log_f = np.log(np.clip(p_fundamental, 1e-7, 1.0))
    return softmax((1.0 - w) * log_m + w * log_f, axis=-1)


def evaluate_1x2_value(
    fair_probs: np.ndarray | list[float],
    offered_odds: np.ndarray | list[float],
    min_ev: float = 0.015,
    min_odds: float = 1.25,
    max_odds: float = 3.50,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
) -> BetOpportunity | None:
    """Pick the single highest-+EV 1X2 side passing odds bounds (avoiding longshot bias)."""
    probs = np.asarray(fair_probs, dtype=float)
    odds = np.asarray(offered_odds, dtype=float)
    labels = ("Home (1)", "Draw (X)", "Away (2)")

    best: BetOpportunity | None = None
    for idx in range(3):
        o = float(odds[idx])
        p = float(probs[idx])
        if o < min_odds or o > max_odds or o <= 1.0:
            continue
        ev = p * o - 1.0
        if ev < min_ev:
            continue
        stake = kelly_fraction(p, o, multiplier=kelly_mult, max_stake=max_stake)
        if best is None or ev > best.expected_value:
            best = BetOpportunity(
                market="1X2",
                selection=labels[idx],
                model_prob=p,
                fair_odds=1.0 / max(p, 1e-9),
                offered_odds=o,
                expected_value=float(ev),
                kelly_stake=stake,
            )
    return best


def _append_binary_opportunities(
    opps: list[BetOpportunity],
    market: str,
    sides: tuple[tuple[str, float, float], ...],
    min_ev: float,
    min_odds: float,
    max_odds: float,
    kelly_mult: float,
    max_stake: float,
    prob_std: float = 0.0,
) -> None:
    """Append qualifying +EV binary market legs using shared EV & Kelly sizing."""
    for sel, p_val, o_val in sides:
        o = float(o_val)
        p = float(p_val)
        if not (min_odds <= o <= max_odds) or o <= 1.0:
            continue
        ev = p * o - 1.0
        if ev < min_ev:
            continue
        stake = (
            baker_mchale_kelly_fraction(p, o, prob_std=prob_std, multiplier=kelly_mult, max_stake=max_stake)
            if prob_std > 0.0
            else kelly_fraction(p, o, multiplier=kelly_mult, max_stake=max_stake)
        )
        opps.append(
            BetOpportunity(
                market=market,
                selection=sel,
                model_prob=p,
                fair_odds=1.0 / max(p, 1e-9),
                offered_odds=o,
                expected_value=float(ev),
                kelly_stake=stake,
            )
        )


def evaluate_multimarket_value(
    score_matrix: np.ndarray,
    offered_1x2: list[float] | None = None,
    sharp_1x2: list[float] | None = None,
    offered_ou25: list[float] | None = None,
    offered_ah: tuple[float, float, float] | None = None,
    offered_btts: list[float] | None = None,
    offered_alt_ou: list[tuple[float, list[float]]] | None = None,
    devig_method: DevigMethod = "power",
    min_ev: float = 0.02,
    min_odds: float = 1.25,
    max_odds: float = 3.50,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
    fundamental_1x2_override: np.ndarray | None = None,
) -> list[BetOpportunity]:
    """Scan 1X2, O/U 2.5, Alt O/U, BTTS, and Asian Handicap for +EV opportunities."""
    priced = price_all_markets(score_matrix)
    opps: list[BetOpportunity] = []

    if offered_1x2 is not None and len(offered_1x2) == 3:
        if sharp_1x2 is not None and len(sharp_1x2) == 3:
            p_ref = devig(sharp_1x2, method=devig_method).probabilities
        elif fundamental_1x2_override is not None:
            p_ref = np.asarray(fundamental_1x2_override, dtype=float)
        else:
            p1 = priced["1x2"]
            p_ref = np.array([p1["H"], p1["D"], p1["A"]], dtype=float)
        opp_1x2 = evaluate_1x2_value(
            p_ref,
            offered_1x2,
            min_ev=min_ev,
            min_odds=min_odds,
            max_odds=max_odds,
            kelly_mult=kelly_mult,
            max_stake=max_stake,
        )
        if opp_1x2 is not None:
            opps.append(opp_1x2)

    if offered_ou25 is not None and len(offered_ou25) == 2:
        _append_binary_opportunities(
            opps,
            market="O/U 2.5",
            sides=(
                ("Over 2.5", float(priced["over_under"]["over_2.5"]), float(offered_ou25[0])),
                ("Under 2.5", float(priced["over_under"]["under_2.5"]), float(offered_ou25[1])),
            ),
            min_ev=min_ev,
            min_odds=min_odds,
            max_odds=max_odds,
            kelly_mult=kelly_mult,
            max_stake=max_stake,
        )

    if offered_alt_ou is not None:
        for line, pair in offered_alt_ou:
            if len(pair) != 2:
                continue
            p_over = matrix_over_probability(score_matrix, float(line))
            _append_binary_opportunities(
                opps,
                market=f"O/U {float(line):.1f}",
                sides=(
                    (f"Over {float(line):.1f}", p_over, float(pair[0])),
                    (f"Under {float(line):.1f}", 1.0 - p_over, float(pair[1])),
                ),
                min_ev=min_ev,
                min_odds=min_odds,
                max_odds=max_odds,
                kelly_mult=kelly_mult,
                max_stake=max_stake,
            )

    if offered_btts is not None and len(offered_btts) == 2:
        btts_p = priced["btts"]
        _append_binary_opportunities(
            opps,
            market="BTTS",
            sides=(
                ("BTTS Yes", float(btts_p["yes"]), float(offered_btts[0])),
                ("BTTS No", float(btts_p["no"]), float(offered_btts[1])),
            ),
            min_ev=min_ev,
            min_odds=min_odds,
            max_odds=max_odds,
            kelly_mult=kelly_mult,
            max_stake=max_stake,
        )

    if offered_ah is not None and len(offered_ah) == 3:
        line, o_home, o_away = float(offered_ah[0]), float(offered_ah[1]), float(offered_ah[2])
        for is_home, label, o_val in (
            (True, f"Home AH ({line:+.2f})", o_home),
            (False, f"Away AH ({-line:+.2f})", o_away),
        ):
            if min_odds <= o_val <= max_odds:
                ev = expected_ah_ev(score_matrix, line, o_val, is_home=is_home)
                if ev >= min_ev:
                    # Effective binary win probability for approximate Kelly sizing
                    p_eff = (ev + 1.0) / o_val
                    opps.append(
                        BetOpportunity(
                            market="Asian Handicap",
                            selection=label,
                            model_prob=float(p_eff),
                            fair_odds=float(1.0 / max(p_eff, 1e-9)),
                            offered_odds=o_val,
                            expected_value=float(ev),
                            kelly_stake=kelly_fraction(p_eff, o_val, multiplier=kelly_mult, max_stake=max_stake),
                        )
                    )

    opps.sort(key=lambda x: x.expected_value, reverse=True)
    return opps


def evaluate_halves_btts_value(
    mu_home: float,
    mu_away: float,
    league_slug: str | None = None,
    offered_1h_btts: list[float] | None = None,
    offered_2h_btts: list[float] | None = None,
    offered_both_halves: list[float] | None = None,
    min_ev: float = 0.02,
    min_odds: float = 1.25,
    max_odds: float = 15.0,
    kelly_mult: float = 0.25,
    max_stake: float = 0.02,
    prob_std: float = 0.015,
) -> list[BetOpportunity]:
    """Identify +EV opportunities across 1H BTTS, 2H BTTS, and Both-Halves BTTS."""
    a1, kappa, h_alpha, fgm1, fgm2 = half_model_params(league_slug)
    hb = compute_halves_btts(
        mu_home,
        mu_away,
        first_half_share=a1,
        match_kappa=kappa,
        half_alpha=h_alpha,
        fgm_1h=fgm1,
        fgm_2h=fgm2,
    )
    opps: list[BetOpportunity] = []
    specs = (
        ("1H BTTS", "1H BTTS Yes", "1H BTTS No", hb.p_1h_kg, offered_1h_btts),
        ("2H BTTS", "2H BTTS Yes", "2H BTTS No", hb.p_2h_kg, offered_2h_btts),
        ("Both-Halves BTTS", "Both Halves Yes", "Both Halves No", hb.p_both_halves_kg, offered_both_halves),
    )
    for mkt, y_lbl, n_lbl, p_yes, pair in specs:
        if pair is not None and len(pair) == 2:
            _append_binary_opportunities(
                opps,
                market=mkt,
                sides=((y_lbl, p_yes, float(pair[0])), (n_lbl, 1.0 - p_yes, float(pair[1]))),
                min_ev=min_ev,
                min_odds=min_odds,
                max_odds=max_odds,
                kelly_mult=kelly_mult,
                max_stake=max_stake,
                prob_std=prob_std,
            )
    opps.sort(key=lambda x: x.expected_value, reverse=True)
    return opps
