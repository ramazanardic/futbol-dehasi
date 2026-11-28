"""5 ileri algoritma için birim testleri: ClubHalfDNA, BalancedResidual, SharpLag, ScoreCalibrator/Dutching, MonteCarloPortfolio."""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.coupons.system_builder import SystemLeg  # noqa: E402
from quantfoot.markets.club_half_dna import (  # noqa: E402
    ClubHalfDNA,
    club_omni_adjustments,
    load_club_half_dna,
    lookup_club_dna,
)
from quantfoot.markets.score_calibrator import (  # noqa: E402
    calibrate_score_distribution,
    classify_score_regime,
    optimize_score_dutching,
)
from quantfoot.models.balanced_residual import load_balanced_residual, predict_balanced_residual  # noqa: E402


def test_club_half_dna_load_lookup_and_omni_adjustments():
    tbl = load_club_half_dna()
    assert len(tbl) >= 100
    hm, aw, mults = club_omni_adjustments("Arsenal", "Chelsea")
    assert -0.045 <= hm <= 0.045
    assert -0.045 <= aw <= 0.045
    assert mults is not None
    assert set(mults) == {"00", "tied_g", "h_plus1", "a_plus1", "h_plus2", "a_plus2"}
    for lo, hi in mults.values():
        assert 0.85 <= lo <= 1.25 and 0.85 <= hi <= 1.25

    fake = {"test club": ClubHalfDNA("Test Club", n_eff=25.0, first_half_share=0.49, lead_hold_vuln=0.55, comeback_rate=0.45)}
    assert lookup_club_dna("FC Test Club", fake) is not None


def test_balanced_residual_model_load_and_probabilities():
    booster, alpha = load_balanced_residual()
    assert booster is not None and alpha > 0.0
    p = predict_balanced_residual((0.36, 0.31, 0.33), p_over25=0.46, elo_diff=None, form5_diff=2.0)
    assert len(p) == 3
    assert abs(sum(p) - 1.0) < 1e-4
    assert all(0.01 < x < 0.98 for x in p)


def test_score_calibrator_and_dutching_optimizer():
    assert classify_score_regime(0.60, 0.22, 0.18, 0.60) == "strong_home_open"
    assert classify_score_regime(0.35, 0.32, 0.33, 0.42) == "balanced_low"
    raw = {"1-0": 0.12, "2-0": 0.10, "2-1": 0.11, "1-1": 0.14, "0-0": 0.09, "0-1": 0.07}
    cal = calibrate_score_distribution(raw, (0.48, 0.28, 0.24), p_over25=0.49)
    assert abs(sum(cal.values()) - 1.0) < 1e-4

    odds = {"1-0": 6.50, "2-0": 8.00, "2-1": 7.50, "1-1": 6.20, "0-0": 9.00, "0-1": 10.50}
    plans = optimize_score_dutching(cal, odds, sizes=(2, 3), budget_tl=100.0)
    assert len(plans) >= 1
    top = plans[0]
    assert abs(sum(top.stake_weights) - 1.0) < 1e-3
    assert abs(sum(top.stake_tl) - 100.0) < 0.1
    exp_eff = 1.0 / sum(1.0 / o for o in top.odds)
    assert abs(top.effective_odds - round(exp_eff, 2)) <= 0.02
