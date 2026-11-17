"""QuantFoot: Quantitative Football Prediction & Value Betting Engine."""

from quantfoot.markets.devig import devig, devig_batch
from quantfoot.markets.pricing import (
    expected_ah_ev,
    price_all_markets,
    settle_asian_handicap,
    skellam_probabilities,
)
from quantfoot.models.bivariate_poisson import DiagonalBivariatePoisson
from quantfoot.models.dixon_coles import TimeDecayedDixonColes
from quantfoot.models.ratings import CausalRatingEngine
from quantfoot.strategy.kelly import (
    kelly_fraction,
    maclean_doubling_before_halving,
    optimize_correlated_kelly,
)

__all__ = [
    "CausalRatingEngine",
    "DiagonalBivariatePoisson",
    "TimeDecayedDixonColes",
    "devig",
    "devig_batch",
    "expected_ah_ev",
    "kelly_fraction",
    "maclean_doubling_before_halving",
    "optimize_correlated_kelly",
    "price_all_markets",
    "settle_asian_handicap",
    "skellam_probabilities",
]
