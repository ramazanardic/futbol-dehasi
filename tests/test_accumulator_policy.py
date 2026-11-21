import math
import numpy as np

import pytest

from quantfoot.strategy.accumulator_policy import (
    ExposureBook,
    Leg,
    PolicyConfig,
    build_daily_portfolio,
    build_ev_coupon,
    check_coupon,
    coupon_kelly_fraction,
    coupon_probability,
    evaluate_coupon,
    margin_compounding_table,
)


def test_margin_compounds_multiplicatively():
    table = dict(margin_compounding_table(-0.06, 7))
    assert table[1] == pytest.approx(-0.06)
    assert table[7] == pytest.approx(0.94 ** 7 - 1)
    assert table[7] < -0.35


def test_evaluate_coupon_product_and_drag():
    legs = [Leg("a", "1", 2.0, 0.55), Leg("b", "2", 1.5, 0.6)]
    ev = evaluate_coupon(legs)
    assert ev.odds == pytest.approx(3.0)
    assert ev.prob == pytest.approx(0.33)
    assert ev.ev == pytest.approx(0.33 * 3 - 1)
    # leg b has EV -10% → drag 10 %
    assert ev.margin_drag == pytest.approx(0.10)


def test_same_match_legs_need_joint_probability():
    legs = [Leg("a", "MS 1", 2.0, 0.5), Leg("a", "2.5 Üst", 1.9, 0.55)]
    with pytest.raises(ValueError):
        coupon_probability(legs)
    assert coupon_probability(legs, {"a": 0.35}) == pytest.approx(0.35)
    res = check_coupon(legs, PolicyConfig(min_coupon_ev=-1, min_leg_ev=-1))
    assert any("aynı maçta" in r for r in res.reasons)


def test_check_rejects_filler_and_long_coupons():
    legs = [Leg(str(i), "1", 1.3, 0.75) for i in range(6)] + [Leg("x", "1", 1.12, 0.85)]
    res = check_coupon(legs, PolicyConfig())
    joined = " | ".join(res.reasons)
    assert "bacak >" in joined and "dolgu" in joined and "1.12" in joined and "kupon EV" in joined


def test_build_ev_coupon_only_positive_ev_and_capped():
    cands = [Leg(f"m{i}", "1", 2.0, 0.52 + 0.01 * i) for i in range(8)]  # all +EV
    cands += [Leg("neg", "1", 1.8, 0.5)]  # EV -10 %
    cands += [Leg("m7", "2", 3.0, 0.40)]  # same match, higher EV → chosen for m7
    cp = build_ev_coupon(cands, PolicyConfig(max_legs=3, max_coupon_odds=100))
    assert cp is not None and cp.n_legs == 3
    ids = [l.match_id for l in cp.legs]
    assert "neg" not in ids and len(set(ids)) == 3
    assert any(l.match_id == "m7" and l.selection == "2" for l in cp.legs)
    assert all(l.ev > 0 for l in cp.legs)


def test_no_coupon_when_nothing_has_value():
    assert build_ev_coupon([Leg("a", "1", 1.5, 0.6), Leg("b", "1", 1.4, 0.7)]) is None


def test_kelly_shrinks_with_uncertainty_and_caps():
    cfg = PolicyConfig(kelly_multiplier=0.25, max_stake_frac=1.0)
    sure = evaluate_coupon([Leg("a", "1", 2.2, 0.55)])
    unsure = evaluate_coupon([Leg("a", "1", 2.2, 0.55, prob_sd=0.08)])
    f1, f2 = coupon_kelly_fraction(sure, cfg), coupon_kelly_fraction(unsure, cfg)
    assert f1 == pytest.approx(0.25 * (0.55 * 2.2 - 1) / 1.2)
    assert 0 < f2 < f1
    assert coupon_kelly_fraction(sure, PolicyConfig(max_stake_frac=0.01)) == pytest.approx(0.01)
    assert coupon_kelly_fraction(evaluate_coupon([Leg("a", "1", 1.5, 0.6)]), cfg) == 0.0


def test_exposure_book_blocks_same_match_and_daily_cap():
    cfg = PolicyConfig(min_coupon_ev=0.0, max_stake_frac=0.05, max_daily_frac=0.06, max_legs=4)
    book = ExposureBook(1000, cfg)
    c1 = check_coupon([Leg("a", "1", 2.2, 0.55), Leg("b", "1", 2.0, 0.55)], cfg)
    ok, stake, _ = book.add(c1)
    assert ok and 0 < stake <= 50
    c2 = check_coupon([Leg("a", "2", 4.0, 0.3), Leg("c", "1", 2.0, 0.56)], cfg)
    ok2, _, why = book.add(c2)
    assert not ok2 and any("aynı maç" in w for w in why)
    c3 = check_coupon([Leg("d", "1", 2.5, 0.5), Leg("e", "1", 2.0, 0.6)], cfg)
    ok3, stake3, _ = book.add(c3)
    assert ok3 and stake + stake3 <= 60 + 1e-9


def test_daily_portfolio_never_reuses_match():
    cands = [Leg(f"m{i}", "1", 2.1, 0.53) for i in range(10)]
    coupons = build_daily_portfolio(cands, 1000, n_coupons=3, cfg=PolicyConfig(max_legs=3, max_coupon_odds=100))
    used = [l.match_id for cp, _ in coupons for l in cp.legs]
    assert len(coupons) == 3 and len(used) == len(set(used))
    assert all(math.isfinite(s) and s > 0 for _, s in coupons)


# ---------------------------------------------------------------- kasa dağıtımı / risk / hedef katlama
from quantfoot.strategy.accumulator_policy import (  # noqa: E402
    allocate_budget,
    plan_metrics,
    risk_report,
    round_stake,
    search_target_plan,
    simulate_day,
)


def _coupons(cfg):
    return [check_coupon([Leg("a", "1", 2.2, 0.52), Leg("b", "1", 2.0, 0.55)], cfg),
            check_coupon([Leg("c", "1", 3.0, 0.37)], cfg),
            check_coupon([Leg("d", "1", 1.8, 0.60), Leg("e", "2", 2.6, 0.41)], cfg)]


def test_round_stake_nesine_friendly():
    assert round_stake(49.9, 5, 5) == 45 and round_stake(4.9, 5, 5) == 0 and round_stake(50, 5, 5) == 50


def test_allocate_fills_daily_budget_with_caps():
    cfg = PolicyConfig(max_daily_frac=1.0, max_stake_frac=0.2, min_coupon_ev=0.0)
    cps = _coupons(cfg)
    st = allocate_budget(cps, 250, cfg)
    assert all(s % 5 == 0 and s <= 50 for s in st)
    assert sum(st) <= 250 and sum(st) == 150  # 3 kupon × 50 TL tavan
    cfg5 = PolicyConfig(max_daily_frac=1.0, max_stake_frac=0.2, min_coupon_ev=0.0)
    five = [check_coupon([Leg(f"m{i}", "1", 2.1, 0.52)], cfg5) for i in range(6)]
    assert sum(allocate_budget(five, 250, cfg5)) == 250  # 5 × 50 TL'ye kadar doldurur


def test_allocate_zero_when_no_positive_ev_and_respects_daily_cap():
    cfg = PolicyConfig(max_daily_frac=0.4, max_stake_frac=0.2, min_coupon_ev=0.0)
    bad = [check_coupon([Leg("a", "1", 1.8, 0.5)], cfg)]
    assert allocate_budget(bad, 250, cfg) == [0.0]
    st = allocate_budget(_coupons(cfg), 250, cfg)
    assert sum(st) <= 100


def test_allocate_kelly_mode_is_smaller():
    cfg = PolicyConfig(max_daily_frac=1.0, max_stake_frac=0.2, min_coupon_ev=0.0)
    cps = _coupons(cfg)
    assert sum(allocate_budget(cps, 10000, cfg, fill_budget=False)) < sum(allocate_budget(cps, 10000, cfg))


def test_simulation_handles_shared_legs():
    cfg = PolicyConfig(min_coupon_ev=-1.0, min_leg_ev=-1.0)
    shared = Leg("a", "1", 2.0, 0.5)
    c1 = check_coupon([shared], cfg)
    c2 = check_coupon([shared], cfg)
    pnl = simulate_day([c1, c2], [10, 10], n_sims=20000)
    # aynı bacak → iki kupon birlikte kazanır ya da birlikte kaybeder: yalnız +20 / -20
    assert set(np.unique(pnl)) <= {-20.0, 20.0}


def test_risk_report_flags_overbetting():
    cfg = PolicyConfig(max_daily_frac=1.0, max_stake_frac=1.0, min_coupon_ev=0.0)
    c = check_coupon([Leg("a", "1", 2.1, 0.5)], cfg)
    heavy = risk_report([c], [200], 250, days=20, n_sims=2000)
    light = risk_report([c], [5], 250, days=20, n_sims=2000)
    assert heavy["log_growth"] < 0 < light["log_growth"]
    assert heavy["p_ruin"] > light["p_ruin"]
    assert 0 <= heavy["p_lose_all_today"] <= 1


def test_target_plan_respects_rules_and_markov_bound():
    legs = [Leg(f"m{i}", "1", o, p) for i, (o, p) in enumerate(
        [(2.1, .5), (1.9, .55), (3.2, .33), (2.5, .42), (1.7, .62), (4.0, .27), (1.6, .55)])]  # m6 EV<0
    cfg = PolicyConfig(max_coupon_odds=500)
    plan = search_target_plan(legs, 250, 10, reserve=100, cfg=cfg, n_plans=400, n_sims=3000)
    assert plan is not None
    assert all(l.ev >= 0 for c in plan.coupons for l in c.legs)
    assert all(l.match_id != "m6" for c in plan.coupons for l in c.legs)
    assert sum(plan.stakes) <= 150 and all(s % 5 == 0 and s > 0 for s in plan.stakes)
    assert 0 < plan.p_reach <= plan.markov_bound + 0.01
    assert plan.p_reach > 0.03
    kelly = plan_metrics([], [], 250, 2500)
    assert kelly.p_reach == 0 and kelly.exp_final == 250


def test_target_plan_none_without_value():
    assert search_target_plan([Leg("a", "1", 1.5, 0.6)], 250, 10) is None
