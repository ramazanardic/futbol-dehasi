"""Per-market, per-league probability calibration (walk-forward fitted on the archive).

Fitted by ``scripts/pazar_kalibrasyonu.py`` and stored in ``data/calibration/market_calibration.json``.
A market is only present in that file when its walk-forward (out-of-sample) log-loss improvement had a
95 % bootstrap interval entirely below zero — otherwise the coupon engine uses the raw fair price.

Model (Platt / logit-linear with shrunk league offsets)::

    logit p' = a + b·logit p (+ c·x) + Δa_lig + Δb_lig·logit p

League offsets are L2-penalised toward zero, so a league with little data stays at the global curve,
and a league missing from the archive (most Nesine leagues) uses the global curve only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "calibration" / "market_calibration.json"


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def fit_platt_league(
    p: np.ndarray,
    y: np.ndarray,
    league: np.ndarray,
    league_l2: float | None = 200.0,
    extra: np.ndarray | None = None,
) -> dict[str, Any]:
    """Fit logit p' = a + b·logit p (+ c·extra) + league offsets (L2 ``league_l2``; None = no league terms)."""
    from scipy.optimize import minimize

    x = _logit(p)
    y = np.asarray(y, dtype=float)
    lg = np.asarray(league).astype(str)
    names = sorted(set(lg)) if league_l2 is not None else []
    idx = np.array([names.index(v) for v in lg]) if names else np.zeros(len(lg), int)
    k = len(names)
    e = None if extra is None else np.nan_to_num(np.asarray(extra, dtype=float))
    n_g = 2 + (1 if e is not None else 0)

    def unpack(theta):
        a, b = theta[0], theta[1]
        c = theta[2] if e is not None else 0.0
        da = theta[n_g:n_g + k] if k else np.zeros(1)
        db = theta[n_g + k:n_g + 2 * k] if k else np.zeros(1)
        return a, b, c, da, db

    def f(theta):
        a, b, c, da, db = unpack(theta)
        z = a + b * x + (c * e if e is not None else 0.0)
        if k:
            z = z + da[idx] + db[idx] * x
        q = _sigmoid(z)
        q = np.clip(q, 1e-9, 1 - 1e-9)
        nll = -np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))
        r = q - y
        g = [r.sum(), (r * x).sum()]
        if e is not None:
            g.append((r * e).sum())
        grad = np.array(g, dtype=float)
        pen = 0.0
        if k:
            ga = np.bincount(idx, weights=r, minlength=k) + 2 * league_l2 * da
            gb = np.bincount(idx, weights=r * x, minlength=k) + 2 * league_l2 * db
            pen = league_l2 * (np.sum(da**2) + np.sum(db**2))
            grad = np.concatenate([grad, ga, gb])
        return nll + pen, grad

    theta0 = np.zeros(n_g + 2 * k)
    theta0[1] = 1.0
    res = minimize(f, theta0, jac=True, method="L-BFGS-B")
    a, b, c, da, db = unpack(res.x)
    out: dict[str, Any] = {"a": float(a), "b": float(b), "n": len(y)}
    if e is not None:
        out["c"] = float(c)
    if k:
        counts = np.bincount(idx, minlength=k)
        out["league"] = {nm: [float(da[i]), float(db[i]), int(counts[i])] for i, nm in enumerate(names)}
    return out


def apply_platt_league(params: dict[str, Any], p, league=None, extra=None) -> np.ndarray:
    """Vectorised application of :func:`fit_platt_league` parameters (unknown league = global curve)."""
    x = _logit(p)
    z = params["a"] + params["b"] * x
    if "c" in params and extra is not None:
        z = z + params["c"] * np.nan_to_num(np.asarray(extra, dtype=float))
    lg_par = params.get("league") or {}
    if lg_par and league is not None:
        lg = np.asarray(league).astype(str)
        da = np.array([lg_par.get(v, [0.0, 0.0])[0] for v in lg])
        db = np.array([lg_par.get(v, [0.0, 0.0])[1] for v in lg])
        z = z + da + db * x
    return _sigmoid(z)


def fit_isotonic(p: np.ndarray, y: np.ndarray, n_knots: int = 200) -> dict[str, list[float]]:
    from sklearn.isotonic import IsotonicRegression

    iso = IsotonicRegression(out_of_bounds="clip", y_min=1e-4, y_max=1 - 1e-4).fit(p, y)
    xs = np.quantile(p, np.linspace(0, 1, n_knots))
    return {"x": [float(v) for v in xs], "y": [float(v) for v in iso.predict(xs)]}


def apply_isotonic(params: dict[str, list[float]], p) -> np.ndarray:
    return np.interp(np.asarray(p, dtype=float), params["x"], params["y"])


# ------------------------------------------------------------------------------------------ production
# Nesine (Turkish) league name -> football-data division code used by the archive. EXACT names (Nesine's
# "1. Lig" means a different tier per country: England 1. Lig = League One, Spain 2. Lig = Segunda).
NESINE_TO_DIVISION: dict[str, str] = {
    "ingiltere premier lig": "E0", "ingiltere championship": "E1", "ingiltere 1. lig": "E2", "ingiltere 2. lig": "E3",
    "ingiltere ulusal lig": "EC", "almanya bundesliga": "D1", "almanya bundesliga 2": "D2",
    "ispanya la liga": "SP1", "ispanya 2. lig": "SP2", "ispanya la liga 2": "SP2", "italya serie a": "I1", "italya serie b": "I2",
    "fransa ligue 1": "F1", "fransa ligue 2": "F2", "turkiye super ligi": "T1", "turkiye super lig": "T1",
    "hollanda eredivisie": "N1", "portekiz premier lig": "P1", "portekiz liga portugal": "P1", "portekiz super lig": "P1",
    "belcika pro lig": "B1", "belcika 1. lig a": "B1", "iskocya premiership": "SC0", "iskocya championship": "SC1",
    "iskocya 1. lig": "SC2", "iskocya 2. lig": "SC3", "yunanistan super lig": "G1",
}


def _ascii(s: str) -> str:
    tr = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    return " ".join(s.translate(tr).lower().split())


def nesine_league_to_division(league: str | None) -> str | None:
    """Exact-name mapping; None for leagues the archive does not cover (→ global curve only)."""
    if not league:
        return None
    return NESINE_TO_DIVISION.get(_ascii(league))


_CACHE: dict[str, Any] = {}


def load_market_calibration(path: Path | str | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else DEFAULT_PATH
    key = str(p)
    if key not in _CACHE:
        try:
            _CACHE[key] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _CACHE[key] = None
    return _CACHE[key]


_COMPLEMENT = {"2.5 Alt": "2.5 Üst", "3.5 Alt": "3.5 Üst", "KG Yok": "KG Var"}


def _complement_key(name: str) -> str | None:
    """Binary complement of a selection whose curve is stored on the other side (Alt↔Üst, Yok↔Var, Çift↔Tek).

    21 Nov: only three fixed pairs were mapped, so e.g. a stored '4.5 Üst' curve left '4.5 Alt' raw and the two sides of
    one market no longer summed to 1. Combinations ('A & B') have no single-selection complement."""
    if name in _COMPLEMENT:
        return _COMPLEMENT[name]
    if "&" in name:
        return None
    for a, b in ((" Alt", " Üst"), (" Yok", " Var"), ("Çift", "Tek")):
        if name.endswith(a.strip()) and name[: len(name) - len(a.strip())] + b.strip() != name:
            return name[: len(name) - len(a.strip())] + b.strip()
    return None


def calibrate_market_probability(
    name: str,
    p: float,
    league: str | None = None,
    calibration: dict[str, Any] | None = None,
    home_odds: float | None = None,
    direct: bool = False,
) -> float:
    """Calibrated probability of one selection; identity when the market has no kept calibrator.

    Curves were fitted on the engine's DERIVED probabilities (market-anchored goal model). A selection the global
    source quotes directly (``direct=True``) is not recalibrated unless the curve says ``apply_to_direct``."""
    if calibration is None or not math.isfinite(p):
        return p
    markets = calibration.get("markets") or {}
    if name.startswith("DEĞİL(") and name.endswith(")"):  # Nesine outcome = complement of the engine event
        inner = calibrate_market_probability(name[6:-1], 1.0 - p, league, calibration, home_odds, direct)
        return 1.0 - inner
    flip = False
    key = name
    if key not in markets:
        comp = _complement_key(name)
        if comp and comp in markets:
            key, flip = comp, True
    params = markets.get(key)
    if not params:
        return p
    if direct and not params.get("apply_to_direct", params.get("direct_in_production", False)):
        return p
    rng = params.get("only_home_odds_range")
    if rng and (home_odds is None or not (rng[0] <= home_odds <= rng[1])):
        return p
    q = 1.0 - p if flip else p
    q_cal = float(apply_platt_league(params, [q], [nesine_league_to_division(league) or "__global__"])[0])
    q_cal = min(0.99, max(0.01, q_cal))
    return 1.0 - q_cal if flip else q_cal
