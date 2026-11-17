"""Unit tests for Kelly portfolio optimization, MacLean-Thorp-Ziemba risk, and RPS."""

import numpy as np
import pandas as pd
import pytest

from quantfoot.evaluation.metrics import ranked_probability_score
from quantfoot.strategy.clv_filter import CLVPreservationFilter
from quantfoot.strategy.kelly import (
    baker_mchale_kelly_fraction,
    kelly_fraction,
    maclean_doubling_before_halving,
    optimize_correlated_kelly,
)
from quantfoot.strategy.value import evaluate_1x2_value


def test_maclean_thorp_ziemba_exact_tradeoffs():
    full = maclean_doubling_before_halving(1.0)
    assert full["relative_growth_rate"] == pytest.approx(1.0)
    assert full["prob_double_before_half"] == pytest.approx(2.0 / 3.0)
    assert full["prob_ever_half_capital"] == pytest.approx(0.5)

    half = maclean_doubling_before_halving(0.5)
    assert half["relative_growth_rate"] == pytest.approx(0.75)
    assert half["prob_double_before_half"] == pytest.approx(8.0 / 9.0)
    assert half["prob_ever_half_capital"] == pytest.approx(0.125)

    quarter = maclean_doubling_before_halving(0.25)
    assert quarter["prob_double_before_half"] > 0.99


def test_correlated_kelly_reduces_stakes_under_positive_correlation():
    probs = [0.55, 0.55]
    odds = [2.10, 2.10]
    indep = optimize_correlated_kelly(probs, odds, corr_matrix=np.eye(2), multiplier=1.0, max_per_bet=0.5, max_total=0.9)
    corr = np.array([[1.0, 0.70], [0.70, 1.0]])
    dep = optimize_correlated_kelly(probs, odds, corr_matrix=corr, multiplier=1.0, max_per_bet=0.5, max_total=0.9)

    assert np.sum(dep["fractions"]) < np.sum(indep["fractions"])
    assert kelly_fraction(0.40, 2.00) == 0.0  # negative EV -> zero stake
    f0 = baker_mchale_kelly_fraction(0.55, 2.00, prob_std=0.0)
    f1 = baker_mchale_kelly_fraction(0.55, 2.00, prob_std=0.02)
    f2 = baker_mchale_kelly_fraction(0.55, 2.00, prob_std=0.06)
    assert f0 == pytest.approx(kelly_fraction(0.55, 2.00))
    assert f0 > f1 > f2 > 0.0


def test_rps_respects_ordinal_distance():
    # True outcome is Home Win (index 0). Forecast A places probability on Draw (1),
    # Forecast B places same probability on Away Win (2) -> Forecast A must score strictly better (lower RPS).
    y = np.array([0])
    p_close = np.array([[0.30, 0.60, 0.10]])
    p_far = np.array([[0.30, 0.10, 0.60]])
    assert ranked_probability_score(p_close, y) < ranked_probability_score(p_far, y)


def test_value_filter_enforces_longshot_odds_cap():
    # Even with positive EV at odds 6.00, default max_odds=3.50 blocks longshot bias traps
    opp = evaluate_1x2_value([0.20, 0.30, 0.50], [6.00, 3.30, 1.90], min_ev=0.05, max_odds=3.50)
    assert opp is None
    opp_ok = evaluate_1x2_value([0.55, 0.25, 0.20], [2.00, 3.80, 4.50], min_ev=0.05, max_odds=3.50)
    assert opp_ok is not None
    assert opp_ok.selection == "Home (1)"
    assert opp_ok.expected_value == pytest.approx(0.10)


def test_clv_preservation_filter_predicts_valid_probabilities():
    rng = np.random.default_rng(17)
    n = 300
    best_ev = rng.uniform(0.015, 0.12, size=n)
    books_n = rng.integers(5, 30, size=n).astype(float)
    df = pd.DataFrame({
        "best_ev": best_ev,
        "odd_sel": rng.uniform(1.4, 3.5, size=n),
        "p_sel": rng.uniform(0.3, 0.7, size=n),
        "vig_open": rng.uniform(0.02, 0.06, size=n),
        "is_draw": rng.integers(0, 2, size=n).astype(float),
        "is_away": rng.integers(0, 2, size=n).astype(float),
        "books_n": books_n,
        "margin_avg": rng.uniform(3.0, 6.0, size=n),
        "margin_min": rng.uniform(1.0, 3.5, size=n),
        "pin_vs_soft_gap": best_ev * 0.9,
    })
    y_clv = ((best_ev + 0.002 * books_n + rng.normal(scale=0.02, size=n)) > 0.06).astype(int)
    flt = CLVPreservationFilter(min_train_ev=0.015).fit(df, y_clv)
    p_hold = flt.predict_hold_proba(df.iloc[:25])
    assert p_hold.shape == (25,)
    assert np.all((p_hold >= 0.0) & (p_hold <= 1.0))


def test_multimarket_value_scans_btts_alt_ou_and_halves():
    from quantfoot.markets import regime_score_matrix
    from quantfoot.strategy import evaluate_halves_btts_value, evaluate_multimarket_value

    mat = regime_score_matrix(2.4, 2.2, alpha_nb=0.0, shared_kappa=0.04, com_nu=1.05, max_goals=14)
    opps = evaluate_multimarket_value(
        mat,
        offered_btts=[1.85, 2.20],
        offered_alt_ou=[(4.5, [2.40, 1.75])],
        min_ev=0.02,
        min_odds=1.20,
        max_odds=4.00,
    )
    assert any(o.market == "BTTS" and o.selection == "BTTS Yes" and o.expected_value > 0.02 for o in opps)
    assert any(o.market == "O/U 4.5" and o.selection == "Over 4.5" for o in opps)

    h_opps = evaluate_halves_btts_value(
        2.6,
        2.3,
        league_slug="eng.u21",
        offered_1h_btts=[2.80, 1.50],
        offered_both_halves=[5.50, 1.15],
        min_ev=0.02,
    )
    assert len(h_opps) >= 1
    assert all(o.expected_value >= 0.02 and o.kelly_stake > 0.0 for o in h_opps)
