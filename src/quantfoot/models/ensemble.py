"""Probability calibration (Temperature & Dirichlet ODIR) and v4 Pyramid Super-Ensemble."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from scipy.optimize import minimize, minimize_scalar
from scipy.special import softmax
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from quantfoot.models.ordinal import OrderedLogit3Class


def fit_temperature_scaling(probs: np.ndarray, y_idx: np.ndarray) -> float:
    """Fit scalar temperature T minimizing multi-class log-loss on validation probabilities."""
    log_p = np.log(np.clip(probs, 1e-9, 1.0))

    def _obj(temp: float) -> float:
        p = softmax(log_p / temp, axis=1)
        return float(log_loss(y_idx, p, labels=[0, 1, 2]))

    res = minimize_scalar(_obj, bounds=(0.3, 4.0), method="bounded")
    return float(res.x)


def apply_temperature(probs: np.ndarray, temp: float) -> np.ndarray:
    """Apply temperature scaling to a probability matrix (N, K)."""
    return softmax(np.log(np.clip(probs, 1e-9, 1.0)) / temp, axis=1)


def fit_dirichlet_odir(
    probs: np.ndarray,
    y_idx: np.ndarray,
    l2_diag: float = 0.1,
    l2_bias: float = 0.05,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit Kull et al. (2019) Dirichlet calibration with ODIR off-diagonal/bias regularization."""
    log_p = np.log(np.clip(probs, 1e-9, 1.0))
    k = probs.shape[1]
    y_oh = np.zeros_like(probs, dtype=float)
    y_oh[np.arange(len(y_idx)), y_idx] = 1.0

    x0 = np.zeros(k * k + k, dtype=float)
    for i in range(k):
        x0[i * k + i] = 1.0

    off_diag_mask = np.ones((k, k), dtype=float) - np.eye(k)

    def _obj(params: np.ndarray) -> float:
        w = params[: k * k].reshape(k, k)
        b = params[k * k :]
        p = softmax(log_p @ w.T + b, axis=1)
        nll = -np.mean(np.sum(y_oh * np.log(np.clip(p, 1e-12, 1.0)), axis=1))
        reg = l2_diag * np.sum((w * off_diag_mask) ** 2) + l2_bias * np.sum(b**2)
        return float(nll + reg)

    res = minimize(_obj, x0, method="BFGS")
    return res.x[: k * k].reshape(k, k), res.x[k * k :]


def apply_dirichlet(probs: np.ndarray, w: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Apply Dirichlet calibration parameters (W, b) to raw probabilities."""
    return softmax(np.log(np.clip(probs, 1e-9, 1.0)) @ w.T + b, axis=1)


def _ranked_probability_score(probs: np.ndarray, y_idx: np.ndarray) -> float:
    """Internal RPS calculation to keep model calibration independent of evaluation package."""
    n, k = probs.shape
    y_oh = np.zeros((n, k), dtype=float)
    y_oh[np.arange(n), y_idx] = 1.0
    cum_p = np.cumsum(probs, axis=1)[:, :-1]
    cum_y = np.cumsum(y_oh, axis=1)[:, :-1]
    return float(np.mean(0.5 * np.sum((cum_p - cum_y) ** 2, axis=1)))


@dataclass
class _ScaledClassifier:
    """Pairs an optional StandardScaler with a probabilistic classifier supporting sample weights."""

    cols: tuple[str, ...]
    clf_factory: Callable[[], object]
    scale: bool = True
    supports_sample_weight: bool = True
    scaler: StandardScaler | None = None
    clf: object | None = None

    def _fit_instance(
        self,
        x_tr: np.ndarray,
        y_tr: np.ndarray,
        sample_weight: np.ndarray | None,
    ) -> object:
        clf = self.clf_factory()
        if sample_weight is not None and self.supports_sample_weight:
            clf.fit(x_tr, y_tr, sample_weight=sample_weight)
        else:
            clf.fit(x_tr, y_tr)
        return clf

    def fit_predict(
        self,
        train_df: pd.DataFrame,
        y_train: np.ndarray,
        val_df: pd.DataFrame,
        sample_weight: np.ndarray | None = None,
    ) -> np.ndarray:
        """Fit on train_df and return out-of-fold probabilities on val_df."""
        x_tr = train_df[list(self.cols)].to_numpy(dtype=float)
        x_va = val_df[list(self.cols)].to_numpy(dtype=float)
        scaler = StandardScaler().fit(x_tr) if self.scale else None
        if scaler is not None:
            x_tr = scaler.transform(x_tr)
            x_va = scaler.transform(x_va)
        clf = self._fit_instance(x_tr, y_train, sample_weight)
        return np.asarray(clf.predict_proba(x_va), dtype=float)

    def fit_full(
        self,
        df: pd.DataFrame,
        y: np.ndarray,
        sample_weight: np.ndarray | None = None,
    ) -> "_ScaledClassifier":
        """Fit scaler and classifier on the full calibration dataset."""
        x = df[list(self.cols)].to_numpy(dtype=float)
        self.scaler = StandardScaler().fit(x) if self.scale else None
        if self.scaler is not None:
            x = self.scaler.transform(x)
        self.clf = self._fit_instance(x, y, sample_weight)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities for rows in df."""
        if self.clf is None:
            raise RuntimeError("_ScaledClassifier must be fitted before predict().")
        x = df[list(self.cols)].to_numpy(dtype=float)
        if self.scaler is not None:
            x = self.scaler.transform(x)
        return np.asarray(self.clf.predict_proba(x), dtype=float)


class FundamentalEnsemble:
    """v4 Pyramid Super-Ensemble with L2-regularized OOF simplex weights, COVID/recency weighting & MLP+LGBM.

    Combines Time-Decayed Dixon-Coles (Goals + Hybrid xG), Laplace-Kalman State-Space Poisson,
    Dual-GAS Poisson, Tier-Aware Wheatcroft GAP (OrderedLogit + MultiLogit), Pyramid Elo/Glicko-2,
    Pi-Ratings, Regularized MLP, and LightGBM over causal SOS/game-state/halftime/box-score features.
    """

    GAP_COLS = ("gap_sot_diff", "gap_vol_diff", "gap_xg_diff", "elo_diff", "glicko_diff")
    GLICKO_COLS = ("glicko_diff", "glicko_exp_h", "glicko_uncert")
    PYRAMID_RATING_COLS = ("elo_diff", "glicko_diff", "glicko_uncert")
    PI_COLS = ("pi_diff_venue", "pi_diff_overall", "pi_exp_gd")
    ELO_COLS = ("elo_diff",)

    FEATURE_COLS = (
        "dcg_h",
        "dcg_d",
        "dcg_a",
        "dch_h",
        "dch_d",
        "dch_a",
        "kal_h",
        "kal_d",
        "kal_a",
        "kal_lam",
        "kal_mu",
        "kal_uncert",
        "gas_h",
        "gas_d",
        "gas_a",
        "gap_sot_diff",
        "gap_sot_sum",
        "gap_vol_diff",
        "gap_vol_sum",
        "gap_xg_diff",
        "gap_xg_sum",
        "glicko_diff",
        "glicko_uncert",
        "elo_diff",
        "pi_diff_venue",
        "pi_diff_overall",
        "pi_exp_gd",
        "sos_xg_diff",
        "gs_xg_diff",
        "xg_diff_10",
        "xg_luck_h",
        "xg_luck_a",
        "ht_gd_diff",
        "cards_diff",
        "sot_diff_10",
        "pts_diff_5",
        "rest_diff",
        "lg_avg_goals",
        "lg_home_rate",
        "is_covid",
    )

    SUBMODEL_NAMES = (
        "dc_goals",
        "dc_hybrid",
        "kalman",
        "gas_poisson",
        "gap_ordered",
        "gap_elo",
        "pyramid_rating",
        "pi",
        "mlp",
        "lgbm",
    )
    DEFAULT_WEIGHTS = (0.06, 0.08, 0.12, 0.05, 0.20, 0.16, 0.09, 0.05, 0.09, 0.10)

    def __init__(
        self,
        weights: tuple[float, ...] | None = None,
        simplex_l2: float = 0.012,
        recency_decay: float = 0.00025,
        covid_weight: float = 0.55,
    ) -> None:
        self._fixed_weights = weights
        self.simplex_l2 = simplex_l2
        self.recency_decay = recency_decay
        self.covid_weight = covid_weight
        self.weights_: np.ndarray = np.asarray(
            weights if weights is not None else self.DEFAULT_WEIGHTS,
            dtype=float,
        )
        self.weights_ /= np.sum(self.weights_)

        self._heads: dict[str, _ScaledClassifier] = {
            "elo": _ScaledClassifier(self.ELO_COLS, lambda: LogisticRegression(C=1.0, max_iter=500)),
            "glicko2": _ScaledClassifier(self.GLICKO_COLS, lambda: LogisticRegression(C=0.5, max_iter=500)),
            "pyramid_rating": _ScaledClassifier(self.PYRAMID_RATING_COLS, lambda: LogisticRegression(C=0.5, max_iter=500)),
            "pi": _ScaledClassifier(self.PI_COLS, lambda: LogisticRegression(C=1.0, max_iter=500)),
            "gap_elo": _ScaledClassifier(self.GAP_COLS, lambda: LogisticRegression(C=0.4, max_iter=500)),
            "gap_ordered": _ScaledClassifier(
                self.GAP_COLS, lambda: OrderedLogit3Class(l2_reg=2.0), supports_sample_weight=False
            ),
            "mlp": _ScaledClassifier(
                self.FEATURE_COLS,
                lambda: MLPClassifier(
                    hidden_layer_sizes=(24, 12),
                    alpha=2.5,
                    max_iter=400,
                    early_stopping=True,
                    n_iter_no_change=15,
                    validation_fraction=0.12,
                    random_state=42,
                ),
                supports_sample_weight=False,
            ),
            "lgbm": _ScaledClassifier(
                self.FEATURE_COLS,
                lambda: LGBMClassifier(
                    n_estimators=260,
                    learning_rate=0.02,
                    max_depth=3,
                    num_leaves=7,
                    min_child_samples=60,
                    subsample=0.8,
                    colsample_bytree=0.75,
                    reg_lambda=2.0,
                    random_state=42,
                    verbose=-1,
                ),
                scale=False,
            ),
        }
        self.temperature: float = 1.0
        self.is_fitted: bool = False

    def _compute_sample_weights(self, cal_df: pd.DataFrame) -> np.ndarray | None:
        if "MatchDate" not in cal_df.columns:
            return None
        max_ts = pd.to_datetime(cal_df["MatchDate"]).max()
        days_back = (max_ts - pd.to_datetime(cal_df["MatchDate"])).dt.days.clip(lower=0).to_numpy(dtype=float)
        sw = np.exp(-self.recency_decay * days_back)
        if "is_covid" in cal_df.columns:
            sw *= np.where(cal_df["is_covid"].to_numpy(dtype=float) > 0.5, self.covid_weight, 1.0)
        mean_sw = float(np.mean(sw))
        return sw / mean_sw if mean_sw > 0.0 else None

    def _optimize_simplex_weights(self, oof_list: list[np.ndarray], y_oof: np.ndarray) -> np.ndarray:
        """Optimize convex combination weights with L2 diversity regularization."""
        k = len(oof_list)

        def _obj(w: np.ndarray) -> float:
            blend = sum(w[i] * oof_list[i] for i in range(k))
            ll = float(log_loss(y_oof, np.clip(blend, 1e-12, 1.0), labels=[0, 1, 2]))
            rps = _ranked_probability_score(blend, y_oof)
            return 0.7 * ll + 0.3 * rps + self.simplex_l2 * float(np.sum(w * w))

        res = minimize(
            _obj,
            np.ones(k, dtype=float) / k,
            method="SLSQP",
            bounds=[(0.0, 1.0)] * k,
            constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        )
        w_opt = np.clip(res.x, 0.0, 1.0)
        return w_opt / np.sum(w_opt)

    def fit(self, cal_df: pd.DataFrame) -> "FundamentalEnsemble":
        """Fit sub-model heads, chronological 3-fold OOF simplex weights, and temperature calibration."""
        y = cal_df["y"].to_numpy(dtype=int)
        n = len(cal_df)
        sw = self._compute_sample_weights(cal_df)
        trained_keys = ("gap_ordered", "gap_elo", "pyramid_rating", "pi", "mlp", "lgbm")

        if n >= 400:
            splits = [int(n * 0.45), int(n * 0.65), int(n * 0.82), n]
            oof_preds = {name: np.zeros((n, 3), dtype=float) for name in trained_keys}
            for s_idx in range(len(splits) - 1):
                tr_end, va_end = splits[s_idx], splits[s_idx + 1]
                tr_df = cal_df.iloc[:tr_end]
                va_df = cal_df.iloc[tr_end:va_end]
                sw_tr = sw[:tr_end] if sw is not None else None
                for name in trained_keys:
                    oof_preds[name][tr_end:va_end] = self._heads[name].fit_predict(
                        tr_df, y[:tr_end], va_df, sample_weight=sw_tr
                    )

            sl = slice(splits[0], n)
            oof_list = [
                cal_df[["dcg_h", "dcg_d", "dcg_a"]].to_numpy(dtype=float)[sl],
                cal_df[["dch_h", "dch_d", "dch_a"]].to_numpy(dtype=float)[sl],
                cal_df[["kal_h", "kal_d", "kal_a"]].to_numpy(dtype=float)[sl],
                cal_df[["gas_h", "gas_d", "gas_a"]].to_numpy(dtype=float)[sl],
                *[oof_preds[name][sl] for name in trained_keys],
            ]
            y_oof = y[sl]
            if self._fixed_weights is None:
                self.weights_ = self._optimize_simplex_weights(oof_list, y_oof)
            oof_blend = sum(self.weights_[i] * oof_list[i] for i in range(len(oof_list)))
            oof_blend /= np.sum(oof_blend, axis=1, keepdims=True)
            self.temperature = fit_temperature_scaling(oof_blend, y_oof)

        for head in self._heads.values():
            head.fit_full(cal_df, y, sample_weight=sw)

        if n < 400:
            raw_base = self._raw_blend(cal_df)
            self.temperature = fit_temperature_scaling(raw_base, y)

        self.is_fitted = True
        return self

    def _submodel_outputs(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        outputs: dict[str, np.ndarray] = {
            "dc_goals": df[["dcg_h", "dcg_d", "dcg_a"]].to_numpy(dtype=float),
            "dc_hybrid": df[["dch_h", "dch_d", "dch_a"]].to_numpy(dtype=float),
            "kalman": df[["kal_h", "kal_d", "kal_a"]].to_numpy(dtype=float),
            "gas_poisson": df[["gas_h", "gas_d", "gas_a"]].to_numpy(dtype=float),
        }
        for name, head in self._heads.items():
            outputs[name] = head.predict(df)
        return outputs

    def _raw_blend_from_outputs(self, outputs: dict[str, np.ndarray]) -> np.ndarray:
        raw = sum(self.weights_[i] * outputs[name] for i, name in enumerate(self.SUBMODEL_NAMES))
        raw /= np.sum(raw, axis=1, keepdims=True)
        return raw

    def _raw_blend(self, df: pd.DataFrame) -> np.ndarray:
        return self._raw_blend_from_outputs(self._submodel_outputs(df))

    def predict_components(self, df: pd.DataFrame) -> dict[str, np.ndarray]:
        """Return calibrated ensemble probabilities, all v4 sub-model predictions, and epistemic std."""
        if not self.is_fitted:
            raise RuntimeError("FundamentalEnsemble must be fitted before predicting.")
        outputs = self._submodel_outputs(df)
        raw = self._raw_blend_from_outputs(outputs)
        calibrated = apply_temperature(raw, self.temperature)

        stack = np.stack([outputs[name] for name in self.SUBMODEL_NAMES], axis=0)
        epistemic_std = np.std(stack, axis=0)

        return {
            **outputs,
            "raw_ensemble": raw,
            "calibrated_ensemble": calibrated,
            "epistemic_std": epistemic_std,
        }

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Return calibrated (N, 3) probability matrix [P(H), P(D), P(A)]."""
        return self.predict_components(df)["calibrated_ensemble"]
