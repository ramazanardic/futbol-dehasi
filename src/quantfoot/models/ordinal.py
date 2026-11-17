"""Proportional-odds Ordered Logistic Regression for ordinal football outcomes (H < D < A)."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit


class OrderedLogit3Class:
    """Cumulative-link ordinal logit preserving Home < Draw < Away ordering."""

    def __init__(self, l2_reg: float = 2.0) -> None:
        self.l2_reg = l2_reg
        self.weights: np.ndarray = np.array([])
        self.c1: float = -0.3
        self.c2: float = 0.8
        self.is_fitted: bool = False

    def fit(self, x: np.ndarray, y: np.ndarray) -> "OrderedLogit3Class":
        """Fit shared latent linear predictor and ordered cutpoints via BFGS."""
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=int)
        n, d = x_arr.shape
        x0 = np.zeros(d + 2, dtype=float)
        x0[-2], x0[-1] = -0.3, 0.8

        def _obj(params: np.ndarray) -> float:
            w = params[:d]
            c1 = params[d]
            c2 = c1 + math.exp(float(np.clip(params[d + 1], -5.0, 5.0)))
            eta = x_arr @ w
            s1 = expit(c1 - eta)
            s2 = expit(c2 - eta)
            p_h = np.clip(s1, 1e-9, 1.0)
            p_d = np.clip(s2 - s1, 1e-9, 1.0)
            p_a = np.clip(1.0 - s2, 1e-9, 1.0)
            probs = np.column_stack([p_h, p_d, p_a])
            nll = -np.mean(np.log(probs[np.arange(n), y_arr]))
            return float(nll + 0.5 * self.l2_reg * np.sum(w * w) / max(n, 1))

        res = minimize(_obj, x0, method="BFGS")
        self.weights = res.x[:d]
        self.c1 = float(res.x[d])
        self.c2 = self.c1 + math.exp(float(np.clip(res.x[d + 1], -5.0, 5.0)))
        self.is_fitted = True
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        """Return (N, 3) calibrated ordinal probabilities [P(H), P(D), P(A)]."""
        if not self.is_fitted:
            raise RuntimeError("OrderedLogit3Class must be fitted before predicting.")
        eta = np.asarray(x, dtype=float) @ self.weights
        s1 = expit(self.c1 - eta)
        s2 = expit(self.c2 - eta)
        probs = np.column_stack(
            [
                np.clip(s1, 1e-7, 1.0),
                np.clip(s2 - s1, 1e-7, 1.0),
                np.clip(1.0 - s2, 1e-7, 1.0),
            ]
        )
        return probs / np.sum(probs, axis=1, keepdims=True)
