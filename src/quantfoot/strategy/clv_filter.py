"""Causal Closing Line Value (CLV) Preservation Filter for soft-book alpha selection."""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier


class CLVPreservationFilter:
    """Predicts whether an opening soft-book edge preserves positive CLV until market close."""

    FEATURE_COLS = (
        "best_ev",
        "odd_sel",
        "p_sel",
        "vig_open",
        "is_draw",
        "is_away",
        "books_n",
        "margin_avg",
        "margin_min",
        "pin_vs_soft_gap",
    )

    def __init__(self, min_train_ev: float = 0.015) -> None:
        self.min_train_ev = min_train_ev
        self._clf = LGBMClassifier(
            n_estimators=100,
            learning_rate=0.03,
            max_depth=3,
            num_leaves=6,
            min_child_samples=40,
            random_state=42,
            verbose=-1,
        )
        self.is_fitted = False

    def fit(self, features_df: pd.DataFrame, clv_positive: np.ndarray) -> "CLVPreservationFilter":
        """Fit classifier strictly on historical bets meeting minimum opening EV."""
        mask = features_df["best_ev"].to_numpy(dtype=float) >= self.min_train_ev
        x_tr = features_df.loc[mask, list(self.FEATURE_COLS)].to_numpy(dtype=float)
        y_tr = np.asarray(clv_positive[mask], dtype=int)
        if len(x_tr) < 50 or len(np.unique(y_tr)) < 2:
            raise ValueError("Insufficient historical EV samples to fit CLVPreservationFilter.")
        self._clf.fit(x_tr, y_tr)
        self.is_fitted = True
        return self

    def predict_hold_proba(self, features_df: pd.DataFrame) -> np.ndarray:
        """Return P(realized CLV > 0) based solely on market-open microstructure."""
        if not self.is_fitted:
            raise RuntimeError("CLVPreservationFilter must be fitted before predicting.")
        x = features_df[list(self.FEATURE_COLS)].to_numpy(dtype=float)
        return np.asarray(self._clf.predict_proba(x)[:, 1], dtype=float)
