"""Kupon simülasyonu yardımcıları: Wilson aralığı, sentetik oran eğrisi, ayrık kupon bölme."""

from __future__ import annotations

import numpy as np
import pandas as pd

from quantfoot.evaluation.kupon_simulasyon import payout_curve, simulate_coupons, wilson


def test_wilson_contains_rate_and_is_ordered():
    lo, hi = wilson(30, 100)
    assert lo < 0.30 < hi
    assert 0 <= lo < hi <= 1
    assert np.isnan(wilson(0, 0)[0])


def test_payout_curve_gives_below_fair_odds():
    fn = payout_curve(np.array([0.1, 0.3, 0.6]), np.array([1.4, 1.25, 1.27]))
    o = fn(np.array([0.3]))[0]
    assert abs(o - 1 / (0.3 * 1.25)) < 1e-9
    assert o < 1 / 0.3


def test_simulate_coupons_disjoint_chunks_and_threshold():
    d = pd.Timestamp("2025-01-01")
    df = pd.DataFrame({"MatchDate": [d] * 5, "p": [0.9, 0.8, 0.7, 0.6, 0.2], "hit": [1, 1, 0, 1, 1]})
    fn = lambda q: 1 / np.asarray(q, float)  # noqa: E731  (adil oran)
    r = simulate_coupons(df, "p", "hit", fn, k=2, thr=0.5)
    assert r["n"] == 2                      # 0.9+0.8 ve 0.7+0.6; 0.2 eşik altı
    assert r["gercek"] == 0.5               # ilk kupon tuttu, ikincisi yattı
    assert abs(r["tahmin"] - (0.72 + 0.42) / 2) < 1e-9
    assert simulate_coupons(df, "p", "hit", fn, k=2, thr=0.95) is None
