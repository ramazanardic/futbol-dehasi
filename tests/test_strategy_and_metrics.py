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


def test_quantfoot_v6_risk_guards_step_down_and_target_odds_coupon():
    from quantfoot.markets import compute_omni_markets
    from quantfoot.strategy import (
        MIN_ALLOWED_ODDS,
        MatchRiskContext,
        audit_match_risks,
        build_target_odds_coupon,
        select_best_valid_bet,
    )

    # 1. Asymmetric Under-Total Trap (e.g. Ireland - Kosovo / Dominica - Cayman)
    b_ire = compute_omni_markets(1.62, 0.52, league="uefa.nations")
    ctx_ire = MatchRiskContext(home_must_win=True, away_dead_attack=True)
    blocked_ire, _ = audit_match_risks(b_ire, ctx_ire)
    assert "2.5 Alt" in blocked_ire
    assert "İY 0" in blocked_ire
    assert "KG Var" in blocked_ire

    recs_ire = select_best_valid_bet(
        "IRE_KOS", "İrlanda", "Kosova", "UNL", "22:45", b_ire,
        offered_odds_map={"2.5 Alt": 1.39, "MS 1": 1.62, "KG Yok": 1.58, "MS 1 & 1.5 Üst": 1.95},
        risk_ctx=ctx_ire,
    )
    assert all(r.selection != "2.5 Alt" for r in recs_ire)
    assert all(r.offered_odds >= MIN_ALLOWED_ODDS for r in recs_ire)
    assert recs_ire[0].selection in ("KG Yok", "MS 1", "MS 1 & 1.5 Üst", "ÇŞ 10")

    # 2. Sub-1.20 Odds Rejection & Away Complacency (Sierra Leone - Congo DR @ 1.18)
    b_cod = compute_omni_markets(0.65, 1.75, league="caf.nations.qual")
    ctx_cod = MatchRiskContext(away_complacent=True)
    recs_cod = select_best_valid_bet(
        "SLE_COD", "Sierra Leone", "Kongo DC", "AFCON", "19:00", b_cod,
        offered_odds_map={"MS 2": 1.18, "2.5 Alt": 1.52, "İY 1.5 Alt": 1.32},
        risk_ctx=ctx_cod,
    )
    assert all(r.selection != "MS 2" for r in recs_cod)
    assert all(r.offered_odds >= 1.20 for r in recs_cod)

    # 3. Adaptive Step-Down on Extreme Markets (+6 Gol -> 3.5 Üst / 2.5 Üst / 3-5 Gol)
    b_den = compute_omni_markets(1.95, 1.85, league="uefa.nations")
    recs_den_6 = select_best_valid_bet(
        "DEN_NOR", "Danimarka", "Norveç", "UNL", "22:45", b_den,
        offered_odds_map={"+6 Gol": 5.01, "3.5 Üst": 2.15, "2.5 Üst": 1.48, "3-5 Gol": 1.85},
        specialty_mode="6_plus_goals",
    )
    assert all(r.selection != "+6 Gol" for r in recs_den_6)
    assert recs_den_6[0].stepped_down_from is not None
    assert recs_den_6[0].selection in ("2.5 Üst", "3-5 Gol", "3.5 Üst", "4.5 Üst")

    # 4. Target-Odds (10x / 20x / 30x) Guarantee Coupon Builder
    match_pool = []
    for idx in range(10):
        bm = compute_omni_markets(1.75 + 0.05 * (idx % 3), 0.70, league="uefa.nations")
        r_list = select_best_valid_bet(
            f"M_{idx}", f"Home_{idx}", f"Away_{idx}", "UNL", "22:45", bm,
            offered_odds_map={"MS 1": 1.52, "1.5 Üst": 1.30, "2-4 Gol": 1.46},
            risk_ctx=MatchRiskContext(group_id=f"G_{idx}"),
        )
        match_pool.append(r_list)

    for target in (10.0, 20.0, 30.0):
        plan = build_target_odds_coupon(match_pool, target_odds=target, max_legs=10)
        assert plan.achieved_odds >= target
        assert len(plan.legs) >= 1
        assert all(leg.offered_odds >= 1.20 for leg in plan.legs)

