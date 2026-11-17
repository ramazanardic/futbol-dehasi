"""Proper scoring rules, walk-forward backtesting, and visual reporting."""

from quantfoot.evaluation.backtest import run_pinnacle_soft_backtest, run_walk_forward_backtest
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
    "betting_metrics",
    "classwise_ece",
    "generate_backtest_charts",
    "multiclass_brier",
    "multiclass_log_loss",
    "ranked_probability_score",
    "run_pinnacle_soft_backtest",
    "run_walk_forward_backtest",
    "simulate_kelly_equity",
]
