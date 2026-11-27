"""Dengeli / yüksek oranlı 1X2 maçları için piyasa-artık (Market-Residual) LightGBM modeli.

Sıfırdan maç sonucu tahmin etmek yerine piyasanın marjsız log-odds'unu `init_score` olarak
alır ve yalnızca piyasanın sistematik yanıldığı artık farkı (residual) öğrenir.
Doğrulama diliminde Brier skorunu iyileştiren `alpha` harman katsayısı ile güvenli tahmine geçer.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantfoot.paths import REPO_ROOT

MODEL_PATH = REPO_ROOT / "data" / "calibration" / "balanced_residual_lgbm.txt"
META_PATH = REPO_ROOT / "data" / "calibration" / "balanced_residual_meta.json"

FEATURE_NAMES: tuple[str, ...] = (
    "p_mkt_h",
    "p_mkt_d",
    "p_mkt_a",
    "p_gap_12",
    "abs_gap",
    "p_over25",
    "handi_size",
    "elo_diff",
    "form5_diff",
    "club_h_1h",
    "club_a_1h",
    "club_cb_diff",
)


def _softmax(logits: np.ndarray) -> np.ndarray:
    z = logits - np.max(logits, axis=-1, keepdims=True)
    e = np.exp(z)
    return e / np.sum(e, axis=-1, keepdims=True)


def build_residual_features(
    p_mkt: Sequence[float],
    *,
    p_over25: float | None = None,
    handi_size: float | None = None,
    elo_diff: float | None = None,
    form5_diff: float | None = None,
    club_h_1h: float | None = None,
    club_a_1h: float | None = None,
    club_cb_diff: float | None = None,
) -> np.ndarray:
    ph = float(np.clip(p_mkt[0], 0.02, 0.96))
    pd_ = float(np.clip(p_mkt[1], 0.02, 0.96))
    pa = float(np.clip(p_mkt[2], 0.02, 0.96))
    s = ph + pd_ + pa
    ph, pd_, pa = ph / s, pd_ / s, pa / s
    nan = float("nan")
    return np.array(
        [[
            ph,
            pd_,
            pa,
            ph - pa,
            abs(ph - pa),
            float(p_over25) if p_over25 is not None else nan,
            float(handi_size) if handi_size is not None else nan,
            float(elo_diff) if elo_diff is not None else nan,
            float(form5_diff) if form5_diff is not None else nan,
            float(club_h_1h) if club_h_1h is not None else nan,
            float(club_a_1h) if club_a_1h is not None else nan,
            float(club_cb_diff) if club_cb_diff is not None else nan,
        ]],
        dtype=float,
    )


def fit_balanced_residual(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    *,
    model_path: Path | None = None,
    meta_path: Path | None = None,
) -> dict[str, Any]:
    """2018-2022 eğitim + 2023 doğrulama üzerinde piyasa-artık LightGBM modelini eğit ve kaydet."""
    import lightgbm as lgb

    mp = model_path or MODEL_PATH
    mtp = meta_path or META_PATH
    mp.parent.mkdir(parents=True, exist_ok=True)

    feat_cols = list(FEATURE_NAMES)
    x_tr = train_df[feat_cols].to_numpy(dtype=float)
    y_tr = train_df["target"].to_numpy(dtype=int)
    p_tr = np.clip(train_df[["p_mkt_h", "p_mkt_d", "p_mkt_a"]].to_numpy(dtype=float), 0.02, 0.96)
    p_tr = p_tr / p_tr.sum(axis=1, keepdims=True)
    init_tr = np.log(p_tr).ravel(order="C")

    x_va = val_df[feat_cols].to_numpy(dtype=float)
    y_va = val_df["target"].to_numpy(dtype=int)
    p_va = np.clip(val_df[["p_mkt_h", "p_mkt_d", "p_mkt_a"]].to_numpy(dtype=float), 0.02, 0.96)
    p_va = p_va / p_va.sum(axis=1, keepdims=True)
    log_p_va = np.log(p_va)
    init_va = log_p_va.ravel(order="C")

    dtrain = lgb.Dataset(x_tr, label=y_tr, init_score=init_tr, feature_name=feat_cols, free_raw_data=False)
    dval = lgb.Dataset(x_va, label=y_va, init_score=init_va, feature_name=feat_cols, reference=dtrain, free_raw_data=False)

    params = {
        "objective": "multiclass",
        "num_class": 3,
        "metric": "multi_logloss",
        "learning_rate": 0.02,
        "max_depth": 3,
        "num_leaves": 6,
        "min_data_in_leaf": 150,
        "lambda_l2": 20.0,
        "lambda_l1": 2.0,
        "feature_fraction": 0.80,
        "bagging_fraction": 0.80,
        "bagging_freq": 1,
        "seed": 42,
        "verbose": -1,
    }
    booster = lgb.train(
        params,
        dtrain,
        num_boost_round=180,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)],
    )

    # raw_score=True -> init_score hariç yalnızca residual margin (N x 3)
    raw_va = booster.predict(x_va, raw_score=True)
    y_onehot = np.eye(3, dtype=float)[y_va]
    base_brier = float(np.mean(np.sum((p_va - y_onehot) ** 2, axis=1)))
    best_alpha = 0.0
    best_brier = base_brier
    for a in np.linspace(0.0, 0.50, 11):
        p_cand = _softmax(log_p_va + float(a) * raw_va)
        br = float(np.mean(np.sum((p_cand - y_onehot) ** 2, axis=1)))
        if br < best_brier - 1e-7:
            best_brier = br
            best_alpha = round(float(a), 3)

    booster.save_model(str(mp))
    meta = {
        "feature_names": feat_cols,
        "best_alpha": best_alpha,
        "val_base_brier": round(base_brier, 6),
        "val_best_brier": round(best_brier, 6),
        "best_iteration": int(booster.best_iteration or booster.current_iteration()),
        "n_train": int(len(train_df)),
        "n_val": int(len(val_df)),
    }
    mtp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    load_balanced_residual.cache_clear()
    return meta


@lru_cache(maxsize=1)
def load_balanced_residual(
    model_path: Path | None = None,
    meta_path: Path | None = None,
) -> tuple[Any, float]:
    """Kayıtlı LightGBM residual modelini ve doğrulama harman katsayısını yükle."""
    mp = model_path or MODEL_PATH
    mtp = meta_path or META_PATH
    if not mp.exists() or not mtp.exists():
        return None, 0.0
    try:
        import lightgbm as lgb

        meta = json.loads(mtp.read_text(encoding="utf-8"))
        alpha = float(meta.get("best_alpha", 0.0))
        if alpha <= 0.0:
            return None, 0.0
        booster = lgb.Booster(model_file=str(mp))
        return booster, alpha
    except Exception:
        return None, 0.0


def predict_balanced_residual(
    p_mkt: Sequence[float],
    *,
    p_over25: float | None = None,
    handi_size: float | None = None,
    elo_diff: float | None = None,
    form5_diff: float | None = None,
    club_h_1h: float | None = None,
    club_a_1h: float | None = None,
    club_cb_diff: float | None = None,
) -> tuple[float, float, float]:
    """Piyasa 1X2 olasılığını eğitimli LightGBM residual modeliyle ince ayarla (model yoksa p_mkt döner)."""
    ph = float(np.clip(p_mkt[0], 0.02, 0.96))
    pd_ = float(np.clip(p_mkt[1], 0.02, 0.96))
    pa = float(np.clip(p_mkt[2], 0.02, 0.96))
    s = ph + pd_ + pa
    base = (ph / s, pd_ / s, pa / s)

    booster, alpha = load_balanced_residual()
    if booster is None or alpha <= 0.0:
        return base

    x = build_residual_features(
        base,
        p_over25=p_over25,
        handi_size=handi_size,
        elo_diff=elo_diff,
        form5_diff=form5_diff,
        club_h_1h=club_h_1h,
        club_a_1h=club_a_1h,
        club_cb_diff=club_cb_diff,
    )
    raw = np.asarray(booster.predict(x, raw_score=True), dtype=float).reshape(1, 3)
    # Aşırı sapmayı koru
    raw = np.clip(raw, -0.40, 0.40)
    log_p = np.log(np.array([base], dtype=float))
    p_out = _softmax(log_p + alpha * raw)[0]
    return (round(float(p_out[0]), 5), round(float(p_out[1]), 5), round(float(p_out[2]), 5))
