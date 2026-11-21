"""Toplam gol kuyruğu (5+, 6+ gol) için piyasa uydurma yardımcıları — 21 Kasım 6+ gol araştırmasında kullanıldı.

Önceden geçici ``/tmp/g6/fit.py`` dosyasındaydı (kutu yeniden başlarsa kaybolur, testsizdi); şimdi repoda ve testli.

* ``devig2``: iki yollu kotasyondan power yöntemiyle marjsız ilk seçenek olasılığı.
* ``com_pmf`` / ``com_from_mean``: Conway–Maxwell–Poisson toplam gol dağılımı (kulüp ligleri ν≈1.10, az-dağılımlı;
  bkz. ``tail_goals.py`` 34.463 maçlık holdout).
* ``nb_pmf``: negatif binom (α=0 → Poisson) duyarlılık dağılımı.
* ``fit_market``: keskin 1.5/2.5/3.5 Alt/Üst kotasyonlarına (μ, ν) uydurur, P(6+) ve P(5+) verir.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln


def devig2(odds: tuple[float, float] | list[float]) -> float:
    """Power devig of a two-way quote; returns the fair probability of the first outcome."""
    a, b = float(odds[0]), float(odds[1])
    lo, hi = 0.5, 3.0
    k = 1.0
    for _ in range(60):
        k = (lo + hi) / 2
        s = (1 / a) ** k + (1 / b) ** k
        if s > 1:
            lo = k
        else:
            hi = k
    return (1 / a) ** k


def com_pmf(lam: float, nu: float, n: int = 20) -> np.ndarray:
    k = np.arange(n + 1)
    lp = k * math.log(lam) - nu * gammaln(k + 1)
    lp -= lp.max()
    p = np.exp(lp)
    return p / p.sum()


def com_from_mean(mu: float, nu: float, n: int = 20) -> np.ndarray:
    """COM-Poisson pmf whose mean is ``mu`` (bisection on λ)."""
    lo, hi = 1e-3, 60.0
    lam = math.sqrt(lo * hi)
    for _ in range(80):
        lam = math.sqrt(lo * hi)
        m = float((np.arange(n + 1) * com_pmf(lam, nu, n)).sum())
        if m < mu:
            lo = lam
        else:
            hi = lam
    return com_pmf(lam, nu, n)


def nb_pmf(mu: float, alpha: float, n: int = 20) -> np.ndarray:
    k = np.arange(n + 1)
    if alpha < 1e-6:
        lp = k * math.log(mu) - mu - gammaln(k + 1)
    else:
        r = 1 / alpha
        p = r / (r + mu)
        lp = gammaln(k + r) - gammaln(r) - gammaln(k + 1) + r * math.log(p) + k * math.log(1 - p)
    q = np.exp(lp)
    return q / q.sum()


def tail(p: np.ndarray, k: int) -> float:
    """P(T ≥ k)."""
    return float(p[k:].sum())


def market_targets(ou: dict, sharp: bool = True) -> dict[int, float]:
    """{'2.5': [over, under], ...} → {3: P(T≥3), ...}. Keskin büro: power devig; yumuşak büro: çarpımsal devig."""
    def f(o):
        return devig2(o) if sharp else (1 / o[0]) / ((1 / o[0]) + (1 / o[1]))
    return {int(float(line) + 0.5): f(o) for line, o in ou.items() if o and len(o) == 2 and min(o) > 1.0}


def fit_mean(targets: dict[int, float], pmf) -> tuple[float, float]:
    """μ that best reproduces the market tail targets under ``pmf(mu)``; returns (μ, rmse)."""
    r = minimize(lambda x: sum((tail(pmf(math.exp(x[0])), k) - v) ** 2 for k, v in targets.items()), [math.log(3)],
                 method="Nelder-Mead", options=dict(xatol=1e-5, fatol=1e-12))
    return math.exp(r.x[0]), math.sqrt(r.fun / max(1, len(targets)))


def fit_market(ou: dict) -> dict | None:
    """Free (μ, ν) COM-Poisson fit to sharp O/U quotes; ν clipped to [0.7, 1.4]."""
    tg = market_targets(ou, sharp=True)
    if not tg:
        return None

    def loss(x):
        p = com_from_mean(math.exp(x[0]), math.exp(x[1]))
        return sum((tail(p, k) - v) ** 2 for k, v in tg.items())
    best = None
    for nu0 in (0.8, 1.0, 1.2):
        r = minimize(loss, [math.log(3), math.log(nu0)], method="Nelder-Mead",
                     options=dict(xatol=1e-4, fatol=1e-9, maxiter=600))
        if best is None or r.fun < best.fun:
            best = r
    mu, nu = math.exp(best.x[0]), min(max(math.exp(best.x[1]), 0.7), 1.4)
    mu1, _ = fit_mean(tg, lambda m: com_from_mean(m, 1.0))
    return dict(targets=tg, mu=mu, nu=nu, rmse=math.sqrt(best.fun / len(tg)), mu_pois=mu1,
                p6_com=tail(com_from_mean(mu, nu), 6), p6_pois=tail(com_from_mean(mu1, 1.0), 6),
                p5_com=tail(com_from_mean(mu, nu), 5))
