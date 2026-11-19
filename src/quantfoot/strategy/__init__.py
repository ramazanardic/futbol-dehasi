"""Value detection, correlated Kelly portfolio optimization, CLV filters, and QuantFoot-v6 coupon builder."""

from quantfoot.strategy.clv_filter import CLVPreservationFilter
from quantfoot.strategy.coupon_builder import (
    MIN_ALLOWED_ODDS,
    CouponPlan,
    MarketRecommendation,
    MatchRiskContext,
    audit_match_risks,
    build_target_odds_coupon,
    is_uncalibrated_competition,
    select_best_valid_bet,
)
from quantfoot.strategy.kelly import (
    baker_mchale_kelly_fraction,
    kelly_fraction,
    maclean_doubling_before_halving,
    optimize_correlated_kelly,
)
from quantfoot.strategy.value import (
    BetOpportunity,
    bayesian_log_odds_blend,
    evaluate_1x2_value,
    evaluate_halves_btts_value,
    evaluate_multimarket_value,
)

__all__ = [
    "BetOpportunity",
    "CLVPreservationFilter",
    "CouponPlan",
    "MIN_ALLOWED_ODDS",
    "MarketRecommendation",
    "MatchRiskContext",
    "audit_match_risks",
    "baker_mchale_kelly_fraction",
    "bayesian_log_odds_blend",
    "build_target_odds_coupon",
    "evaluate_1x2_value",
    "evaluate_halves_btts_value",
    "evaluate_multimarket_value",
    "is_uncalibrated_competition",
    "kelly_fraction",
    "maclean_doubling_before_halving",
    "optimize_correlated_kelly",
    "select_best_valid_bet",
]
