import math

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
