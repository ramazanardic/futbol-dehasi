"""Proper scoring rules, walk-forward backtesting, and visual reporting."""

from quantfoot.evaluation.backtest import run_pinnacle_soft_backtest, run_walk_forward_backtest
from quantfoot.evaluation.clv_ledger import (
    record_daily_picks,
    settle_ledger,
    summarize_clv_ledger,
    update_closing_lines,
)
from quantfoot.evaluation.clv_tracker import (
    BrierDecomposition,
    CLVReport,
    CORPDecomposition,
    LogPoolTestResult,
    brier_decomposition,
    clv_significance,
    compute_clv,
    corp_reliability_decomposition,
    optimal_log_pool_weight,
    pav_isotonic,
    propose_family_calibration_update,
)
from quantfoot.evaluation.metrics import (
    betting_metrics,
    classwise_ece,
    multiclass_brier,
    multiclass_log_loss,
    ranked_probability_score,
    simulate_kelly_equity,
)
from quantfoot.evaluation.reporting import generate_backtest_charts

__all__ = [
    "BrierDecomposition",
    "CLVReport",
    "CORPDecomposition",
    "LogPoolTestResult",
    "betting_metrics",
    "brier_decomposition",
    "classwise_ece",
    "clv_significance",
    "compute_clv",
    "corp_reliability_decomposition",
    "generate_backtest_charts",
    "multiclass_brier",
    "multiclass_log_loss",
    "optimal_log_pool_weight",
    "pav_isotonic",
    "propose_family_calibration_update",
    "ranked_probability_score",
    "record_daily_picks",
    "run_pinnacle_soft_backtest",
    "run_walk_forward_backtest",
    "settle_ledger",
    "simulate_kelly_equity",
    "summarize_clv_ledger",
    "update_closing_lines",
]
