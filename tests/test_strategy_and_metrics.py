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
            # MS 1 / 2-4 Gol priced above fair (+EV); 1.5 Üst at 1.30 is -EV and must be filtered out.
            offered_odds_map={"MS 1": 1.72, "1.5 Üst": 1.30, "2-4 Gol": 1.85},
            risk_ctx=MatchRiskContext(group_id=f"G_{idx}"),
        )
        match_pool.append(r_list)

    for target in (10.0, 20.0, 30.0):
        plan = build_target_odds_coupon(match_pool, target_odds=target, max_legs=10)
        assert plan.achieved_odds >= target
        assert len(plan.legs) >= 1
        assert all(leg.offered_odds >= 1.20 for leg in plan.legs)
        assert all(leg.ev > 0.0 for leg in plan.legs)
        assert plan.reached_target and plan.expected_value > 0.0



def test_baker_mchale_shrinks_before_capping():
    from quantfoot.strategy.kelly import baker_mchale_kelly_fraction

    # Uncapped quarter-Kelly 0.0833 shrunk by ~0.94 is still above the 3% cap.
    assert baker_mchale_kelly_fraction(0.6, 2.5, prob_std=0.05) == pytest.approx(0.03)
    # Below the cap the shrinkage still applies.
    small = baker_mchale_kelly_fraction(0.52, 2.0, prob_std=0.05, max_stake=1.0)
    assert 0.0 < small < 0.25 * (0.52 * 2.0 - 1.0) / 1.0


def test_ht_ft_mode_respects_complacency_blocks():
    from quantfoot.markets.omni_markets import compute_omni_markets
    from quantfoot.strategy.coupon_builder import MatchRiskContext, select_best_valid_bet

    bundle = compute_omni_markets(0.8, 2.0, league="e0")
    recs = select_best_valid_bet(
        "m1", "H", "A", "e0", "", bundle,
        risk_ctx=MatchRiskContext(away_complacent=True),
        specialty_mode="ht_ft",
    )
    sels = {r.selection for r in recs}
    assert "İY/MS 2/2" not in sels and "İY/MS 0/2" not in sels


def test_coupon_builder_rejects_negative_ev_legs():
    from quantfoot.markets.omni_markets import compute_omni_markets
    from quantfoot.strategy.coupon_builder import build_target_odds_coupon, select_best_valid_bet

    pool = []
    for idx in range(6):
        b = compute_omni_markets(1.8, 0.7, league="e0")
        # Bookmaker-like odds below fair value: every leg is -EV.
        pool.append(select_best_valid_bet(f"M{idx}", "H", "A", "e0", "", b, offered_odds_map={"MS 1": 1.45, "1.5 Üst": 1.28}))
    assert all(r.ev < 0 for recs in pool for r in recs)
    plan = build_target_odds_coupon(pool, target_odds=10.0)
    assert plan.legs == () and plan.reached_target is False
    # The old behaviour is still available explicitly.
    assert build_target_odds_coupon(pool, target_odds=10.0, min_leg_ev=None).legs


def test_uncalibrated_competitions_get_no_recommendations():
    from quantfoot.markets.omni_markets import compute_omni_markets
    from quantfoot.strategy.coupon_builder import is_uncalibrated_competition, select_best_valid_bet

    for name in ("UEFA Women's Champions League", "uefa.wchampions", "Spanish Copa de la Reina", "Chelsea (K) - PSG (K)"):
        assert is_uncalibrated_competition(name)
    for name in ("UEFA Champions League", "E0", "Brazilian Serie A", None):
        assert not is_uncalibrated_competition(name)

    b = compute_omni_markets(2.7, 0.7, league="uefa.wchampions")
    assert select_best_valid_bet("m", "Chelsea", "PSG", "UEFA Women's Champions League", "", b) == []
    assert select_best_valid_bet("m", "Chelsea", "PSG", "UEFA Women's Champions League", "", b, allow_uncalibrated=True)


def test_v7_blowout_kg_yok_phantom_ev_and_btts_joint_fit():
    from quantfoot.markets import compute_omni_markets, devig, fit_tail_rates_from_markets, league_tail_regime
    from quantfoot.strategy import MatchRiskContext, audit_match_risks

    # Replay Nov 19 AL Ain - AL Dhafra (1.09 fav, O/U 3.5=[1.82,1.85], 2-way BTTS=[1.69,1.56] -> P(BTTS)=47.9%)
    p1x2 = devig([1.09, 7.30, 14.70], method="power").probabilities
    p25 = float(devig([1.30, 2.97], method="power").probabilities[0])
    p35 = float(devig([1.82, 1.85], method="power").probabilities[0])
    p_btts_mkt = float(devig([1.69, 1.56], method="power").probabilities[0])
    com_nu, alpha_nb, kappa = league_tail_regime("uae.1")

    # 1. Without BTTS anchor, 1X2+O/U underestimates underdog rate -> audit_match_risks Layer 6 blocks phantom KG Yok!
    mh_raw, ma_raw, _ = fit_tail_rates_from_markets(
        p_1x2=p1x2, ou_lines=[(2.5, p25), (3.5, p35)],
        seed_rates=(2.9, 0.4), alpha_nb=alpha_nb, shared_kappa=kappa, com_nu=com_nu, fund_weight=0.04,
    )
    b_raw = compute_omni_markets(mh_raw, ma_raw, league="uae.1")
    blocked, _ = audit_match_risks(b_raw, MatchRiskContext(btts_market_prob=p_btts_mkt))
    assert "KG Yok" in blocked

    # 2. With p_btts supplied, joint fit raises underdog rate so model BTTS aligns near market!
    mh_fit, ma_fit, _ = fit_tail_rates_from_markets(
        p_1x2=p1x2, ou_lines=[(2.5, p25), (3.5, p35)], p_btts=p_btts_mkt,
        seed_rates=(2.9, 0.4), alpha_nb=alpha_nb, shared_kappa=kappa, com_nu=com_nu, fund_weight=0.04,
    )
    assert ma_fit > ma_raw + 0.08
    b_fit = compute_omni_markets(mh_fit, ma_fit, league="uae.1")
    assert abs(b_fit.btts["KG Var"] - p_btts_mkt) < 0.06


def test_v7_knockout_90min_draw_missing_ou_and_high_draw_cs12_guards():
    from quantfoot.markets import compute_omni_markets
    from quantfoot.strategy import MatchRiskContext, audit_match_risks

    # Knockout medium favorite (Roltek Dob 1-1 Bistrica, p_fav ~ 57%) -> MS blocked, goals/BTTS allowed
    b_ko = compute_omni_markets(1.04, 1.92, league="svn.cup")
    blocked_ko, _ = audit_match_risks(b_ko, MatchRiskContext(is_knockout=True))
    assert "MS 2" in blocked_ko
    assert "MS 2 & 1.5 Üst" in blocked_ko
    assert "KG Var" not in blocked_ko

    # Knockout mega-favorite (Beltinci 1-3 NK Celje, p_fav ~ 73%) -> MS allowed with slight penalty
    b_mega = compute_omni_markets(0.80, 2.55, league="svn.cup")
    blocked_mega, pen_mega = audit_match_risks(b_mega, MatchRiskContext(is_knockout=True))
    assert "MS 2" not in blocked_mega
    assert pen_mega["MS 2"] < 1.0

    # High draw probability -> ÇŞ 12 blocked
    b_draw = compute_omni_markets(1.05, 0.95, league="egy.cup")
    blocked_draw, _ = audit_match_risks(b_draw, MatchRiskContext(is_knockout=True))
    assert "ÇŞ 12" in blocked_draw

    # Missing global O/U anchor (Gaddafi 2-2, Farco 2-1) -> KG/goals blocked
    b_no_ou = compute_omni_markets(2.30, 0.30, league="uga.1")
    blocked_no_ou, _ = audit_match_risks(b_no_ou, MatchRiskContext(has_ou_market=False))
    assert "KG Yok" in blocked_no_ou
    assert "1.5 Üst" in blocked_no_ou


def test_v7_diversified_portfolio_enforces_zero_repeats_exposure_cap_and_mbs():
    from quantfoot.markets import compute_omni_markets
    from quantfoot.strategy import (
        MatchRiskContext,
        PortfolioCouponSpec,
        build_diversified_portfolio,
        select_best_valid_bet,
    )

    pool = []
    for idx in range(14):
        b = compute_omni_markets(1.85 + 0.04 * (idx % 4), 0.75 + 0.05 * (idx % 3), league="e0")
        recs = select_best_valid_bet(
            f"M_{idx}", f"Home_{idx}", f"Away_{idx}", "E0", "20:00", b,
            offered_odds_map={
                "MS 1": 1.65,
                "1.5 Üst": 1.32,
                "2.5 Üst": 2.05,
                "MS 1 & 1.5 Üst": 2.15,
                "2-4 Gol": 1.75,
            },
            risk_ctx=MatchRiskContext(group_id=f"G_{idx}"),
            mbs=3 if idx % 2 == 0 else 1,
        )
        pool.append(recs)

    specs = [
        PortfolioCouponSpec(title="C1", target_odds=10.0, max_legs=6, min_leg_ev=None),
        PortfolioCouponSpec(title="C2", target_odds=10.0, max_legs=6, min_leg_ev=None),
        PortfolioCouponSpec(title="C3", target_odds=10.0, max_legs=6, min_leg_ev=None),
    ]
    plans = build_diversified_portfolio(pool, specs, max_selection_reuse=1, max_match_reuse=2)
    assert len(plans) == 3

    seen_pairs: set[tuple[str, str]] = set()
    match_hits: dict[str, int] = {}
    for p in plans:
        assert p.reached_target and p.achieved_odds >= 10.0
        assert len(p.legs) >= max(l.mbs for l in p.legs)
        for l in p.legs:
            pair = (l.match_id, l.selection)
            assert pair not in seen_pairs
            seen_pairs.add(pair)
            match_hits[l.match_id] = match_hits.get(l.match_id, 0) + 1
    assert max(match_hits.values()) <= 2


def test_v71_underdog_dc_tight_o15_knockout_over_and_shootout_scores():
    from quantfoot.markets import compute_omni_markets
    from quantfoot.strategy import MatchRiskContext, audit_match_risks

    # 1. Layer 10: Underdog Double Chance blocked when favorite clearly leads (Amiens 2-1, Cundinamarca 0-2)
    b_amiens = compute_omni_markets(1.50, 1.16, league="fra.3")
    blocked_a, _ = audit_match_risks(b_amiens, MatchRiskContext())
    assert "ÇŞ 02" in blocked_a

    b_cund = compute_omni_markets(0.92, 1.03, league="col.2")
    blocked_c, _ = audit_match_risks(b_cund, MatchRiskContext())
    assert "ÇŞ 10" in blocked_c

    # 2. Layer 10: High-tempo shootout coin-flip blocks side ÇŞ (Orlando 1-3 Cincinnati)
    b_orl = compute_omni_markets(2.08, 2.02, league="usa.1")
    blocked_o, _ = audit_match_risks(b_orl, MatchRiskContext(is_knockout=True))
    assert "ÇŞ 10" in blocked_o and "ÇŞ 02" in blocked_o
    assert "3.5 Üst" not in blocked_o

    # 3. Layer 11: Tight-match 1.5 Üst blocked (ZED 0-0, Sao Paulo 0-1) + knockout marginal 2.5 Üst blocked
    b_zed = compute_omni_markets(1.15, 0.88, league="egy.cup")
    blocked_z, _ = audit_match_risks(b_zed, MatchRiskContext(is_knockout=True))
    assert "1.5 Üst" in blocked_z
    assert "KG Yok" not in blocked_z

    b_sp = compute_omni_markets(1.26, 1.15, league="bra.1")
    blocked_sp, _ = audit_match_risks(b_sp, MatchRiskContext())
    assert "1.5 Üst" in blocked_sp

    b_lag = compute_omni_markets(2.20, 0.73, league="ven.cup")
    blocked_lag, _ = audit_match_risks(b_lag, MatchRiskContext(is_knockout=True))
    assert "2.5 Üst" in blocked_lag

    # 4. Exact-score mode calibration: Arsenal-Lyon (1.47, 2.46) must not collapse #1 score to 1-1 or 0-1
    b_ars = compute_omni_markets(1.47, 2.46, league="uefa.wchampions")
    top3_ars = [s["score"] for s in b_ars.top_ft_scores[:3]]
    assert top3_ars[0] == "1-2"
    assert "0-1" not in top3_ars


def test_v71_portfolio_forbids_contradictions_and_enforces_min_leg_prob():
    from quantfoot.strategy import MarketRecommendation, PortfolioCouponSpec, build_diversified_portfolio

    def _rec(mid: str, sel: str, cat: str, prob: float, odds: float) -> MarketRecommendation:
        return MarketRecommendation(
            match_id=mid, home=f"H_{mid}", away=f"A_{mid}", league="E0", kickoff="20:00",
            category=cat, selection=sel, probability=prob, fair_odds=round(1.0 / prob, 2),
            offered_odds=odds, odds_is_estimated=False, safety_score=prob, ev=prob * odds - 1.0,
            rationale="test", group_id=mid, mbs=1,
        )

    pool = [
        [_rec("M1", "ÇŞ 10", "Çifte Şans", 0.66, 1.35), _rec("M1", "ÇŞ 02", "Çifte Şans", 0.65, 1.36)],
        [_rec("M2", "2.5 Üst", "Maç Geneli Alt/Üst", 0.68, 1.35), _rec("M2", "2.5 Alt", "Maç Geneli Alt/Üst", 0.60, 1.45)],
        [_rec("M3", "KG Var", "Karşılıklı Gol", 0.67, 1.35), _rec("M3", "KG Yok", "Karşılıklı Gol", 0.61, 1.42)],
        [_rec("M4", "MS 1", "Maç Sonucu (1X2)", 0.65, 1.38), _rec("M4", "2.5 Üst", "Maç Geneli Alt/Üst", 0.55, 1.60)],
    ]
    specs = [
        PortfolioCouponSpec(title="C1", target_odds=1.80, max_legs=2, min_leg_ev=None, min_leg_prob=0.64),
        PortfolioCouponSpec(title="C2", target_odds=1.80, max_legs=2, min_leg_ev=None, min_leg_prob=0.60),
    ]
    plans = build_diversified_portfolio(pool, specs, max_selection_reuse=1, max_match_reuse=2, forbid_contradictions=True)
    c1_map = {l.match_id: l.selection for l in plans[0].legs}
    c2_map = {l.match_id: l.selection for l in plans[1].legs}
    assert all(l.probability >= 0.64 for l in plans[0].legs)
    assert not (c1_map.get("M1") == "ÇŞ 10" and c2_map.get("M1") == "ÇŞ 02")
    assert not (c1_map.get("M2") == "2.5 Üst" and c2_map.get("M2") == "2.5 Alt")
    assert not (c1_map.get("M3") == "KG Var" and c2_map.get("M3") == "KG Yok")

