"""Sistem kuponu optimizeri (system_builder) ve çapraz portföy koruma (PortfolioExposureGuard) testleri."""

from __future__ import annotations

import math
import pytest

from quantfoot.coupons.system_builder import (
    PortfolioExposureGuard,
    SystemLeg,
    evaluate_system,
    optimize_system,
    poisson_binomial_tail,
)


def _sample_banko_legs(n: int = 5) -> list[SystemLeg]:
    return [
        SystemLeg(match_id=str(100 + i), match=f"Ev{i} - Dep{i}", name="3.5 Alt", odds=1.32 + 0.02 * i, p=0.74, mbs=1)
        for i in range(n)
    ]


def _sample_high_odds_legs(n: int = 6, mbs: int = 2) -> list[SystemLeg]:
    return [
        SystemLeg(match_id=str(200 + i), match=f"Sürpriz{i} - Rakip{i}", name="İY/MS 2/1", odds=18.0 + i * 2.0, p=0.055, mbs=mbs)
        for i in range(n)
    ]


def test_poisson_binomial_tail_matches_exact_manual_distribution():
    probs = [0.8, 0.6, 0.5]
    tail = poisson_binomial_tail(probs)
    p3 = 0.8 * 0.6 * 0.5
    p2_only = 0.8 * 0.6 * 0.5 + 0.8 * 0.4 * 0.5 + 0.2 * 0.6 * 0.5
    assert tail[0] == pytest.approx(1.0)
    assert tail[3] == pytest.approx(p3, abs=1e-6)
    assert tail[2] == pytest.approx(p3 + p2_only, abs=1e-6)
    assert tail[1] >= tail[2] >= tail[3]


def test_evaluate_system_computes_exact_payouts_mbs_and_p_profit():
    legs = [
        SystemLeg("1", "A - B", "İY/MS 2/1", odds=20.0, p=0.06, mbs=2),
        SystemLeg("2", "C - D", "İY/MS 1/2", odds=25.0, p=0.05, mbs=2),
        SystemLeg("3", "E - F", "İY/MS 2/1", odds=30.0, p=0.04, mbs=2),
    ]
    # Sistem 2,3 -> C(3,2)+C(3,3) = 4 kolon × 25 TL = 100 TL
    ev = evaluate_system(legs, sizes=(2, 3), stake_per_col=25.0)
    assert ev.n_cols == 4
    assert ev.total_cost == 100.0
    assert ev.mbs_ok and ev.mbs_required == 2
    # 2 maç tutarsa en az 20*25*25 = 12_500 TL (>100 TL), yani P(kâr) = P(>=2)
    assert ev.hit_table[2][0] == pytest.approx(20.0 * 25.0 * 25.0)
    assert ev.hit_table[2][1] == pytest.approx(25.0 * 30.0 * 25.0)
    expected_max = (20 * 25 + 20 * 30 + 25 * 30 + 20 * 25 * 30) * 25.0
    assert ev.max_payout == pytest.approx(expected_max)
    assert ev.p_profit == pytest.approx(ev.p_at_least[2], abs=1e-5)

    # MBS ihlali: MBS=2 maçlara size=(1, 2) verilirse mbs_ok=False
    ev_bad = evaluate_system(legs, sizes=(1, 2), stake_per_col=10.0)
    assert not ev_bad.mbs_ok


def test_optimize_system_banko_sigorta_and_yuksek_oran_budget_and_mbs():
    banko_legs = _sample_banko_legs(5)
    # 5 maç banko sigorta: 4/5+5/5 = 6 kolon, 120 TL bütçede 20 TL/kolon sığar
    opts_b = optimize_system(banko_legs, budget_tl=120.0, mode="banko_sigorta", top_n=3)
    assert opts_b
    assert all(e.total_cost <= 120.0 and e.mbs_ok for e in opts_b)
    # Tek-bacak sigortalı sistem (4,5) düz 5'liden daha yüksek P(>=4) taşır
    sig = next((e for e in opts_b if e.sizes == (4, 5)), None)
    assert sig is not None and sig.n_cols == 6
    assert sig.p_at_least[4] > sig.p_at_least[5] + 0.30

    # Yüksek oran 6 maç 100 TL bütçe, MBS=3 zorlaması
    hi_legs = _sample_high_odds_legs(6, mbs=3)
    opts_h = optimize_system(hi_legs, budget_tl=100.0, mode="yuksek_oran", top_n=3)
    assert opts_h
    for e in opts_h:
        assert e.mbs_ok and min(e.sizes) >= 3
        assert e.total_cost <= 100.0
        assert e.n_cols == sum(math.comb(6, k) for k in e.sizes)


def test_portfolio_exposure_guard_detects_duplicate_selection_and_match_wipeout():
    guard = PortfolioExposureGuard(max_coupons_per_match=1, max_coupons_per_selection=1)
    c1 = [
        SystemLeg("33001", "Getafe - Atl Madrid", "İY 1.5 Alt", 1.24, 0.76),
        SystemLeg("33002", "Betis - Girona", "3.5 Alt", 1.30, 0.74),
    ]
    c2 = [
        SystemLeg("33001", "Getafe - Atl Madrid", "İY 1.5 Alt", 1.24, 0.76),  # aynı tercih!
        SystemLeg("33003", "Lille - Paris FC", "1.5 Üst", 1.22, 0.78),
    ]
    c3 = [
        SystemLeg("33002", "Betis - Girona", "2.5 Alt", 1.65, 0.62),  # aynı maç farklı tercih!
        SystemLeg("33004", "Inter - Milan", "KG Var", 1.55, 0.66),
    ]
    assert guard.register_coupon("K1", c1) == []
    issues2 = guard.register_coupon("K2", c2)
    issues3 = guard.register_coupon("K3", c3)
    assert len(issues2) == 1 and "aynı tercih" in issues2[0]
    assert len(issues3) == 1 and "aynı maç" in issues3[0]

    audit = guard.audit()
    assert not audit.ok
    assert audit.n_coupons == 3
    assert len(audit.duplicate_selections) == 1
    assert len(audit.overexposed_matches) == 2
    assert audit.concentration_score > 0.0
