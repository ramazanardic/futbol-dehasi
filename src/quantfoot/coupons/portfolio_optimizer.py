"""Monte Carlo Korelasyonlu Portföy & Hedge (Sigorta) Dağıtım Optimizatörü.

Aynı lig / aynı saat dilimi maçları arasındaki gizli korelasyonu Gaussian copula ile modeller,
10.000 adımlık Monte Carlo simülasyonuyla sistem kuponlarının gerçek kâr olasılığını (`p_profit`),
sıfır dönüş (tam kayıp) olasılığını (`p_zero_return`) ve ödeme yüzdeliklerini (`p50/p90/p95`) ölçer.

Ardından bütçeyi "Yüksek Oranlı Sistem (1/2, 2/1, 2Y KG, Skor)" + "Aynı Maçların Güvenli Sigorta Bacağı"
arasında en iyi dağıtan dengeli Hedge planını bulur.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import itertools
import math

import numpy as np
from scipy.stats import norm

from quantfoot.coupons.system_builder import SystemLeg, evaluate_system


@dataclass(frozen=True)
class MonteCarloPortfolioReport:
    n_sims: int
    total_cost: float
    expected_return: float
    roi: float
    p_profit: float
    p_zero_return: float
    p50_payout: float
    p90_payout: float
    p95_payout: float
    max_payout: float
    correlation_used: float


@dataclass(frozen=True)
class HedgedAllocationPlan:
    total_budget_tl: float
    high_odds_budget_tl: float
    hedge_budget_tl: float
    high_odds_system: str
    hedge_description: str
    expected_return: float
    roi: float
    p_profit: float
    p_zero_return: float
    p90_payout: float
    max_payout: float


def _build_correlation_matrix(
    legs: Sequence[SystemLeg],
    same_league_rho: float,
    same_slot_rho: float,
) -> tuple[np.ndarray, float]:
    n = len(legs)
    corr = np.eye(n, dtype=float)
    max_rho = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            rho = 0.0
            if legs[i].league and legs[j].league and legs[i].league == legs[j].league:
                rho += same_league_rho
            if legs[i].kickoff and legs[j].kickoff and str(legs[i].kickoff)[:13] == str(legs[j].kickoff)[:13]:
                rho += same_slot_rho
            rho = min(0.35, rho)
            corr[i, j] = corr[j, i] = rho
            if rho > max_rho:
                max_rho = rho
    # PSD garanti: küçük özdeğerleri kırp
    eigvals, eigvecs = np.linalg.eigh(corr)
    if np.min(eigvals) < 1e-6:
        eigvals = np.maximum(eigvals, 1e-6)
        corr = (eigvecs * eigvals) @ eigvecs.T
        d = np.sqrt(np.diag(corr))
        corr = corr / np.outer(d, d)
    return corr, round(float(max_rho), 4)


def _simulate_outcomes(
    legs: Sequence[SystemLeg],
    n_sims: int,
    same_league_rho: float,
    same_slot_rho: float,
    seed: int,
) -> tuple[np.ndarray, float]:
    n = len(legs)
    probs = np.clip(np.array([float(lg.p) for lg in legs], dtype=float), 1e-4, 1.0 - 1e-4)
    thresh = norm.ppf(probs)
    corr, max_rho = _build_correlation_matrix(legs, same_league_rho, same_slot_rho)
    chol = np.linalg.cholesky(corr)
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((int(n_sims), n)) @ chol.T
    wins = z < thresh[None, :]
    return wins, max_rho


def _vector_system_payouts(
    wins: np.ndarray,
    odds: Sequence[float],
    sizes: Sequence[int],
    stake_per_col: float,
) -> np.ndarray:
    n = wins.shape[1]
    payouts = np.zeros(wins.shape[0], dtype=float)
    odds_arr = [float(o) for o in odds]
    for k in sizes:
        if not 1 <= int(k) <= n:
            continue
        for comb in itertools.combinations(range(n), int(k)):
            col_odds = math.prod(odds_arr[i] for i in comb)
            hit_mask = np.all(wins[:, list(comb)], axis=1)
            payouts += hit_mask * (col_odds * stake_per_col)
    return payouts


def simulate_correlated_system(
    legs: Sequence[SystemLeg],
    sizes: Sequence[int],
    stake_per_col: float = 1.0,
    *,
    n_sims: int = 10000,
    same_league_rho: float = 0.10,
    same_slot_rho: float = 0.05,
    seed: int = 42,
) -> MonteCarloPortfolioReport:
    """Bir sistem kuponunu korelasyonlu Monte Carlo ile simüle et."""
    if not legs:
        raise ValueError("Simülasyon için en az 1 bacak gerekir.")
    clean_sizes = tuple(sorted({int(k) for k in sizes if 1 <= int(k) <= len(legs)}))
    if not clean_sizes:
        raise ValueError("Geçerli sistem boyutu yok.")
    n_cols = sum(math.comb(len(legs), k) for k in clean_sizes)
    total_cost = round(n_cols * float(stake_per_col), 2)

    wins, max_rho = _simulate_outcomes(legs, n_sims, same_league_rho, same_slot_rho, seed)
    payouts = _vector_system_payouts(wins, [float(lg.odds) for lg in legs], clean_sizes, float(stake_per_col))

    exp_ret = float(np.mean(payouts))
    max_pay = float(math.prod(float(lg.odds) for lg in legs) * 0.0)
    # Teorik max ödeme
    max_pay = float(sum(math.prod(float(lg.odds) for lg in comb) * float(stake_per_col) for k in clean_sizes for comb in itertools.combinations(legs, k)))
    return MonteCarloPortfolioReport(
        n_sims=int(n_sims),
        total_cost=total_cost,
        expected_return=round(exp_ret, 2),
        roi=round(exp_ret / total_cost - 1.0, 4) if total_cost > 0 else 0.0,
        p_profit=round(float(np.mean(payouts > total_cost + 1e-9)), 4),
        p_zero_return=round(float(np.mean(payouts <= 1e-9)), 4),
        p50_payout=round(float(np.percentile(payouts, 50)), 2),
        p90_payout=round(float(np.percentile(payouts, 90)), 2),
        p95_payout=round(float(np.percentile(payouts, 95)), 2),
        max_payout=round(max_pay, 2),
        correlation_used=max_rho,
    )


def optimize_hedged_allocation(
    high_odds_legs: Sequence[SystemLeg],
    insurance_legs: Sequence[SystemLeg],
    total_budget_tl: float = 100.0,
    *,
    n_sims: int = 5000,
    seed: int = 42,
) -> HedgedAllocationPlan | None:
    """Bütçeyi yüksek oranlı sistem + güvenli sigorta kombinesi/sistemi arasında dağıt."""
    hi = list(high_odds_legs)[:6]
    ins = list(insurance_legs)[:4]
    if len(hi) < 3 or len(ins) < 2 or total_budget_tl < 30.0:
        return None

    mbs_hi = max(int(lg.mbs or 1) for lg in hi)
    hi_size = max(2, mbs_hi)
    n_cols_hi = math.comb(len(hi), hi_size)
    if n_cols_hi <= 0:
        return None

    # Ortak korelasyonlu simülasyon (aynı maç veya ligde örtüşme dahil)
    combined = hi + ins
    wins, _ = _simulate_outcomes(combined, n_sims, same_league_rho=0.10, same_slot_rho=0.05, seed=seed)
    wins_hi = wins[:, : len(hi)]
    wins_ins = wins[:, len(hi) :]
    ins_combo_win = np.all(wins_ins, axis=1)
    ins_combo_odds = math.prod(float(lg.odds) for lg in ins)

    best_plan: HedgedAllocationPlan | None = None
    best_score = -1e9

    for hi_share in (0.30, 0.45, 0.60):
        raw_hi_budget = total_budget_tl * hi_share
        stake_col = int(max(1, round(raw_hi_budget / n_cols_hi)))
        actual_hi_budget = round(float(n_cols_hi * stake_col), 2)
        if actual_hi_budget >= total_budget_tl - 10.0:
            continue
        actual_hedge_budget = round(float(total_budget_tl - actual_hi_budget), 2)

        pay_hi = _vector_system_payouts(wins_hi, [float(lg.odds) for lg in hi], (hi_size,), float(stake_col))
        pay_hedge = ins_combo_win.astype(float) * (ins_combo_odds * actual_hedge_budget)
        tot_pay = pay_hi + pay_hedge

        exp_ret = float(np.mean(tot_pay))
        roi = exp_ret / total_budget_tl - 1.0
        p_prof = float(np.mean(tot_pay > total_budget_tl + 1e-9))
        p_zero = float(np.mean(tot_pay <= 1e-9))
        p90 = float(np.percentile(tot_pay, 90))
        hi_max = float(sum(math.prod(float(lg.odds) for lg in c) * stake_col for c in itertools.combinations(hi, hi_size)))
        max_pay = hi_max + ins_combo_odds * actual_hedge_budget

        # Dengeli amaç fonksiyonu: kâr olasılığı + sıfır-kayıp düşüklüğü + ROI
        obj = 1.6 * p_prof - 0.8 * p_zero + 0.5 * roi
        if obj > best_score:
            best_score = obj
            ev_hi = evaluate_system(hi, (hi_size,), float(stake_col))
            best_plan = HedgedAllocationPlan(
                total_budget_tl=round(total_budget_tl, 2),
                high_odds_budget_tl=actual_hi_budget,
                hedge_budget_tl=actual_hedge_budget,
                high_odds_system=f"{len(hi)} maç Sistem {hi_size} ({ev_hi.n_cols} kol × {stake_col} TL)",
                hedge_description=f"{len(ins)}'li Güvenli Sigorta @{ins_combo_odds:.2f} ({actual_hedge_budget:.0f} TL)",
                expected_return=round(exp_ret, 2),
                roi=round(roi, 4),
                p_profit=round(p_prof, 4),
                p_zero_return=round(p_zero, 4),
                p90_payout=round(p90, 2),
                max_payout=round(max_pay, 2),
            )

    return best_plan
