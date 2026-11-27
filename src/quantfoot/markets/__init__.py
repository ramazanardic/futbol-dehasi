"""Market devigging, Asian handicap pricing, Skellam, overdispersed tail goals, and Omni-Market engine."""

from quantfoot.markets.bet_builder import BetBuilderQuote, price_bet_builder
from quantfoot.markets.corners_cards import CardDistribution, CornerCardRatings, CornerDistribution, league_baseline
from quantfoot.markets.goal_markets import Outcome, asian_handicap, asian_total, draw_no_bet, goal_probability, price_asian_markets, price_goal_markets
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets.market_book import build_market_book
from quantfoot.markets.player_markets import PlayerProfile, price_player_markets
from quantfoot.markets.devig import DevigResult, book_overround, devig, devig_batch
from quantfoot.markets.halves_btts import (
    HalvesBttsSummary,
    compute_halves_btts,
    half_model_params,
    half_timing_profile,
)
from quantfoot.markets.omni_markets import (
    HTFT_OUTCOMES,
    OmniMarketBundle,
    compute_omni_markets,
)
from quantfoot.markets.pricing import (
    expected_ah_ev,
    invert_ah_ou_1x2,
    price_all_markets,
    settle_asian_handicap,
    skellam_probabilities,
)
from quantfoot.markets.consensus import (
    BookmakerQuote,
    SharpConsensus,
    SyntheticCoherenceReport,
    adaptive_kelly_from_consensus,
    benchmark_consensus_on_season_2627,
    check_synthetic_coherence,
    precision_weighted_consensus,
)
from quantfoot.markets.line_movement import (
    LineMovementSignal,
    SharpSoftEdge,
    analyze_line_movement,
    backtest_sharp_soft_and_steam,
    sharp_soft_edge,
)
from quantfoot.markets.tail_goals import (
    TailGoalSummary,
    com_poisson_pmf,
    fit_tail_rates_from_markets,
    league_tail_params,
    league_tail_regime,
    matrix_1x2,
    matrix_ah_home_win_share,
    matrix_ah_outcomes,
    matrix_over_probability,
    negative_binomial_score_matrix,
    regime_score_matrix,
    summarize_tail_goals,
)

__all__ = [
    "BetBuilderQuote",
    "BookmakerQuote",
    "CardDistribution",
    "CornerCardRatings",
    "CornerDistribution",
    "GoalTimingModel",
    "LineMovementSignal",
    "Outcome",
    "PlayerProfile",
    "SharpConsensus",
    "SharpSoftEdge",
    "SyntheticCoherenceReport",
    "adaptive_kelly_from_consensus",
    "analyze_line_movement",
    "asian_handicap",
    "asian_total",
    "backtest_sharp_soft_and_steam",
    "benchmark_consensus_on_season_2627",
    "build_market_book",
    "check_synthetic_coherence",
    "draw_no_bet",
    "goal_probability",
    "league_baseline",
    "precision_weighted_consensus",
    "price_asian_markets",
    "price_bet_builder",
    "price_goal_markets",
    "price_player_markets",
    "DevigResult",
    "HTFT_OUTCOMES",
    "HalvesBttsSummary",
    "OmniMarketBundle",
    "TailGoalSummary",
    "book_overround",
    "com_poisson_pmf",
    "compute_halves_btts",
    "compute_omni_markets",
    "devig",
    "devig_batch",
    "expected_ah_ev",
    "fit_tail_rates_from_markets",
    "half_model_params",
    "half_timing_profile",
    "invert_ah_ou_1x2",
    "league_tail_params",
    "league_tail_regime",
    "matrix_1x2",
    "matrix_ah_home_win_share",
    "matrix_ah_outcomes",
    "matrix_over_probability",
    "negative_binomial_score_matrix",
    "price_all_markets",
    "regime_score_matrix",
    "settle_asian_handicap",
    "sharp_soft_edge",
    "skellam_probabilities",
    "summarize_tail_goals",
]
