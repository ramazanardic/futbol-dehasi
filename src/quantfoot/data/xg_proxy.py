"""Causal box-score Expected Goals (xG) estimator trained strictly on past matches."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import PoissonRegressor


class BoxScoreXGModel:
    """Estimates team match expected goals (xG-proxy) from shot, corner, and card box scores."""

    _REQ_COLS = (
        "HomeShots",
        "AwayShots",
        "HomeTarget",
        "AwayTarget",
        "HomeCorners",
        "AwayCorners",
        "HomeRed",
        "AwayRed",
    )

    def __init__(self, alpha: float = 1.0, min_xg: float = 0.10, max_xg: float = 5.50) -> None:
        self.alpha = alpha
        self.min_xg = min_xg
        self.max_xg = max_xg
        self._reg = PoissonRegressor(alpha=alpha, max_iter=500)
        self.is_fitted = False

    @staticmethod
    def _build_team_matrix(df: pd.DataFrame) -> np.ndarray:
        h_off = (df["HomeShots"].values - df["HomeTarget"].values).clip(min=0.0)
        a_off = (df["AwayShots"].values - df["AwayTarget"].values).clip(min=0.0)
        x_home = np.column_stack(
            [
                df["HomeTarget"].values,
                h_off,
                df["HomeCorners"].values,
                df["AwayRed"].values,
                np.ones(len(df)),
            ]
        )
        x_away = np.column_stack(
            [
                df["AwayTarget"].values,
                a_off,
                df["AwayCorners"].values,
                df["HomeRed"].values,
                np.zeros(len(df)),
            ]
        )
        return np.vstack([x_home, x_away])

    def fit(self, df: pd.DataFrame, max_date: str | pd.Timestamp | None = None) -> "BoxScoreXGModel":
        """Fit Poisson GLM strictly on matches prior to max_date to prevent look-ahead leakage."""
        sub = df
        if max_date is not None:
            sub = sub[sub["MatchDate"] < pd.Timestamp(max_date)]
        sub = sub.dropna(subset=[*self._REQ_COLS, "FTHome", "FTAway"])
        if len(sub) < 50:
            raise ValueError(f"Insufficient box-score matches ({len(sub)}) to fit xG proxy.")

        x = self._build_team_matrix(sub)
        y = np.concatenate([sub["FTHome"].values, sub["FTAway"].values])
        self._reg.fit(x, y)
        self.is_fitted = True
        return self

    def transform(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Return (home_xg_proxy, away_xg_proxy) arrays, falling back to goals where shots are missing."""
        if not self.is_fitted:
            raise RuntimeError("BoxScoreXGModel must be fitted before transform().")

        h_out = df["FTHome"].to_numpy(dtype=float, copy=True)
        a_out = df["FTAway"].to_numpy(dtype=float, copy=True)
        has_stats = df[list(self._REQ_COLS)].notna().all(axis=1).to_numpy()

        if np.any(has_stats):
            sub = df.loc[has_stats]
            n = len(sub)
            x = self._build_team_matrix(sub)
            preds = np.clip(self._reg.predict(x), self.min_xg, self.max_xg)
            h_out[has_stats] = preds[:n]
            a_out[has_stats] = preds[n:]

        return h_out, a_out
