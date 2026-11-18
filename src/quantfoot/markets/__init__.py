"""Market devigging, Asian handicap pricing, Skellam, overdispersed tail goals, and Omni-Market engine."""

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
from quantfoot.markets.tail_goals import (
    TailGoalSummary,
    com_poisson_pmf,
    fit_tail_rates_from_markets,
    league_tail_params,
    league_tail_regime,
    matrix_1x2,
    matrix_ah_home_win_share,
    matrix_over_probability,
    negative_binomial_score_matrix,
    regime_score_matrix,
    summarize_tail_goals,
)

__all__ = [
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
    "matrix_over_probability",
    "negative_binomial_score_matrix",
    "price_all_markets",
    "regime_score_matrix",
    "settle_asian_handicap",
    "skellam_probabilities",
    "summarize_tail_goals",
]
