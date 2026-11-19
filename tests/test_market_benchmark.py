"""The pooling test must give weight ~1 to an informative model and ~0 to a useless one."""

import numpy as np
import pytest

from quantfoot.evaluation.market_benchmark import fair_clv, log_pool, mean_with_ci, pooling_test, raw_clv


def _simulate(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    logits = rng.normal(0, 1.0, size=(n, 3))
    truth = np.exp(logits) / np.exp(logits).sum(axis=1, keepdims=True)
    y = np.array([rng.choice(3, p=p) for p in truth])
    noisy = np.exp(logits + rng.normal(0, 1.0, size=(n, 3)))
    noisy /= noisy.sum(axis=1, keepdims=True)
    return truth, noisy, y


def test_pool_endpoints():
    a = np.array([[0.5, 0.3, 0.2]])
    b = np.array([[0.2, 0.3, 0.5]])
    assert log_pool(a, b, 0.0) == pytest.approx(a)
    assert log_pool(a, b, 1.0) == pytest.approx(b)
    assert log_pool(a, b, 0.5).sum() == pytest.approx(1.0)


def test_informative_model_gets_weight():
    truth, noisy, y = _simulate(3000)
    res = pooling_test(p_market=noisy, p_model=truth, y=y, n_boot=200)
    assert res.weight > 0.7 and res.ci_low > 0.5
    assert res.logloss_pool <= res.logloss_market


def test_useless_model_gets_no_weight():
    truth, noisy, y = _simulate(3000, seed=1)
    res = pooling_test(p_market=truth, p_model=noisy, y=y, n_boot=200)
    assert res.weight < 0.15 and res.ci_low == 0.0


def test_clv_definitions():
    assert raw_clv(2.10, 2.00) == pytest.approx(0.05)
    assert fair_clv(2.10, 0.50) == pytest.approx(0.05)
    m, lo, hi = mean_with_ci([0.01, 0.02, 0.03])
    assert m == pytest.approx(0.02) and lo <= m <= hi
    assert mean_with_ci([]) is None
