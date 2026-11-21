"""Shared operational thresholds and paths for QuantFoot daily / Nesine flows.

Backtest research defaults (e.g. min_ev=0.015 in walk-forward studies) stay in
evaluation.backtest so historical numbers are not silently rewritten.
"""

from __future__ import annotations

import datetime as dt

# Europe/Istanbul has been permanently UTC+3 since 2016 (no DST).
TSI = dt.timezone(dt.timedelta(hours=3))

# Official Nesine coupon rules (tahminler/README.md, 20 Nov 2026).
MIN_LEG_ODDS = 1.20
MAX_LEGS = 7
MAX_LEGS_HIGH = 8
HIGH_TARGET = 20.0
STANDARD_COUPON_TARGETS: tuple[float, ...] = (5.0, 10.0, 20.0, 30.0, 50.0)
MIN_LEG_PROB_OPTIMUM = 0.55
MIN_LEG_PROB_SAFE = 0.60

# ESPN/model-only daily.py coupon scanner (NOT the official Nesine coupon).
# These legs are fitted to the same book's odds; they are not a betting edge.
MODEL_ONLY_MIN_EV = 0.02
MODEL_ONLY_TARGETS: tuple[float, ...] = (3.0, 5.0, 10.0)
MODEL_ONLY_MAX_LEGS = 4

# Global reference age. Analysis may still *price* older snapshots (clearly marked).
# Anything betting-related (coupons, official picks) must not use prices older than this.
MAX_PRICE_AGE_H = 3.0
# How old a references.json snapshot may be before global_references() drops it
# entirely (analysis can pass a larger cap to still render a report).
REFERENCE_LOAD_AGE_H = 30.0

# Selections with EV above this are listed as "reference error suspected", never as tips.
MAX_PLAUSIBLE_EV = 0.25

# Main pick of a match (derin_tahmin.choose / simulasyon.update_picks): value, not just probability.
# A pick needs calibrated EV = p × Nesine odds − 1 ≥ this; evidence verdicts only FILTER (⚠ / not triple-confirmed).
PICK_MIN_EV = 0.02

# "Hard" markets the user lost most on (21 Nov post-mortem: Üst 2.5/3.5, KG Var, weak-favourite MS 1, İY/MS).
# Not banned: they enter a coupon only with a larger margin over the calibrated global fair price.
HARD_MARKET_MIN_EV = 0.03
HARD_MARKET_SIGMA_ADD = 0.010
