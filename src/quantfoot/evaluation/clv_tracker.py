"""Closing Line Value (CLV) significance, Brier MCB/DSC calibration decomposition, and safe auto-calibration.

Implements the evaluation pillars recommended by Kaunitz et al. (2017) and Dimitriadis et al. (2023):
  1. **Closing Line Value (CLV):** Measures edge against sharp closing fair probabilities with
     Student-t p-values, deterministic bootstrap 95% CIs, and statistical power sample sizes.
  2. **Murphy / Dimitriadis Brier Decomposition:** Exact ``Brier = MCB - DSC + UNC`` decomposition
     plus Expected Calibration Error (ECE) separating miscalibration from discrimination skill.
  3. **Log-Opinion-Pool Test:** Optimizes ``w in [0, 1]`` for ``P_pool ∝ P_model^w * P_market^(1-w)``
     to test empirically whether any model adds genuine information beyond sharp closing prices.
  4. **Safe Walk-Forward Family Calibration Proposal:** James-Stein shrunk negative-only residual
     updates (``prior_n=150``, ``min_n=40``) that never blindly overwrite production files.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import t as student_t

from quantfoot.evaluation.auto_learn import market_family
from quantfoot.markets.devig import DevigMethod, devig_batch


@dataclass(frozen=True)
class CLVReport:
    """Statistical significance summary of Closing Line Value observations."""

    n: int
    mean_clv: float
    median_clv: float
    std_clv: float
    positive_rate: float
    t_stat: float
    p_value_one_sided: float
    ci_95_low: float
    ci_95_high: float
    min_n_for_95pct_power: int | None


@dataclass(frozen=True)
class BrierDecomposition:
    """Exact Murphy / Dimitriadis Brier score decomposition: brier = mcb - dsc + unc."""

    n: int
    brier: float
    ece: float
    mcb: float
    dsc: float
    unc: float
    mean_pred: float
    mean_obs: float


@dataclass(frozen=True)
class CORPDecomposition:
    """Bin-free CORP (Pool-Adjacent-Violators isotonic) reliability & Brier decomposition (Dimitriadis et al. 2021/2023).

    Satisfies the exact algebraic identity ``brier == mcb - dsc + unc`` with zero binning
    hyperparameters, using isotonic conditional event probabilities (CEP).
    """

    n: int
    brier: float
    corp_ece: float
    mcb: float
    dsc: float
    unc: float
    n_isotonic_levels: int
    mean_pred: float
    mean_obs: float


@dataclass(frozen=True)
class LogPoolTestResult:
    """Optimal log-opinion-pool weight ``w`` of a candidate model against sharp closing probabilities."""

    n: int
    optimal_weight: float
    market_log_loss: float
    model_log_loss: float
    pool_log_loss: float
    log_loss_gain: float


def compute_clv(
    odds_taken: float,
    closing_fair_prob: float | None = None,
    *,
    closing_odds: float | None = None,
) -> float:
    """Compute percentage Closing Line Value (CLV).

    When ``closing_fair_prob`` (devigged sharp closing probability) is supplied, returns
    ``odds_taken * closing_fair_prob - 1.0`` (true expected value vs closing market).
    Otherwise falls back to raw price ratio ``odds_taken / closing_odds - 1.0``.
    """
    ot = float(odds_taken)
    if ot <= 1.0:
        raise ValueError(f"odds_taken must exceed 1.0, got {ot}")
    if closing_fair_prob is not None:
        p_close = float(closing_fair_prob)
        if not 0.0 < p_close < 1.0:
            raise ValueError(f"closing_fair_prob must lie in (0, 1), got {p_close}")
        return ot * p_close - 1.0
    if closing_odds is not None:
        oc = float(closing_odds)
        if oc <= 1.0:
            raise ValueError(f"closing_odds must exceed 1.0, got {oc}")
        return (ot / oc) - 1.0
    raise ValueError("Either closing_fair_prob or closing_odds must be provided.")


def clv_significance(
    clv_values: Sequence[float],
    *,
    n_bootstrap: int = 2000,
    seed: int = 42,
) -> CLVReport:
    """Evaluate statistical significance of observed CLV values with Student-t & bootstrap CI."""
    arr = np.asarray([float(x) for x in clv_values if x is not None and math.isfinite(float(x))], dtype=float)
    n = int(arr.size)
    if n == 0:
        return CLVReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, None)

    mean_v = float(np.mean(arr))
    med_v = float(np.median(arr))
    std_v = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    pos_rate = float(np.mean(arr > 0.0))

    if n > 1 and std_v > 1e-12:
        t_stat = mean_v / (std_v / math.sqrt(n))
        p_one = float(student_t.sf(t_stat, df=n - 1))
    else:
        t_stat = 0.0
        p_one = 0.5 if mean_v == 0.0 else (0.0 if mean_v > 0.0 else 1.0)

    if n > 1 and n_bootstrap > 0:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, n, size=(int(n_bootstrap), n))
        boot_means = np.mean(arr[idx], axis=1)
        ci_lo = float(np.quantile(boot_means, 0.025))
        ci_hi = float(np.quantile(boot_means, 0.975))
    else:
        ci_lo, ci_hi = mean_v, mean_v

    # One-sided alpha=0.05, power=0.95 => (z_0.95 + z_0.95)^2 = (1.6449 + 1.6449)^2 ≈ 10.822
    if mean_v > 1e-6 and std_v > 1e-12:
        min_n = int(math.ceil(10.822 * ((std_v / mean_v) ** 2)))
    else:
        min_n = None

    return CLVReport(
        n=n,
        mean_clv=round(mean_v, 6),
        median_clv=round(med_v, 6),
        std_clv=round(std_v, 6),
        positive_rate=round(pos_rate, 5),
        t_stat=round(t_stat, 4),
        p_value_one_sided=round(p_one, 6),
        ci_95_low=round(ci_lo, 6),
        ci_95_high=round(ci_hi, 6),
        min_n_for_95pct_power=min_n,
    )


def brier_decomposition(
    y_true: Sequence[float],
    y_prob: Sequence[float],
    *,
    n_bins: int = 10,
) -> BrierDecomposition:
    """Compute exact Murphy / Dimitriadis Brier decomposition (MCB - DSC + UNC) and ECE."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    if yt.shape != yp.shape or yt.ndim != 1 or yt.size == 0:
        raise ValueError("y_true and y_prob must be non-empty 1D arrays of equal length.")

    n = int(yt.size)
    brier = float(np.mean((yp - yt) ** 2))
    base_rate = float(np.mean(yt))
    unc = base_rate * (1.0 - base_rate)

    # Quantile-free equal-width probability bins (standard reliability diagram decomposition).
    edges = np.linspace(0.0, 1.0, max(2, int(n_bins)) + 1)
    mcb = 0.0
    dsc = 0.0
    ece = 0.0
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if i == len(edges) - 2:
            mask = (yp >= lo) & (yp <= hi)
        else:
            mask = (yp >= lo) & (yp < hi)
        cnt = int(np.sum(mask))
        if cnt == 0:
            continue
        w = cnt / n
        p_bar = float(np.mean(yp[mask]))
        o_bar = float(np.mean(yt[mask]))
        mcb += w * ((p_bar - o_bar) ** 2)
        dsc += w * ((o_bar - base_rate) ** 2)
        ece += w * abs(p_bar - o_bar)

    return BrierDecomposition(
        n=n,
        brier=round(brier, 6),
        ece=round(ece, 6),
        mcb=round(mcb, 6),
        dsc=round(dsc, 6),
        unc=round(unc, 6),
        mean_pred=round(float(np.mean(yp)), 5),
        mean_obs=round(base_rate, 5),
    )


def pav_isotonic(y_sorted: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Exact O(n) Pool-Adjacent-Violators Algorithm (PAVA) for non-decreasing isotonic regression."""
    y = np.asarray(y_sorted, dtype=float)
    w = np.ones_like(y, dtype=float) if weights is None else np.asarray(weights, dtype=float)
    n = int(y.size)
    if n == 0:
        return np.array([], dtype=float)

    # Stack of merged blocks: [sum_wy, sum_w, count]
    blocks: list[list[float]] = []
    for yi, wi in zip(y, w):
        blocks.append([float(yi * wi), float(wi), 1.0])
        while len(blocks) >= 2:
            prev_mean = blocks[-2][0] / blocks[-2][1]
            curr_mean = blocks[-1][0] / blocks[-1][1]
            if prev_mean <= curr_mean:
                break
            b_last = blocks.pop()
            blocks[-1][0] += b_last[0]
            blocks[-1][1] += b_last[1]
            blocks[-1][2] += b_last[2]

    out = np.empty(n, dtype=float)
    pos = 0
    for sum_wy, sum_w, cnt in blocks:
        c = int(cnt)
        out[pos : pos + c] = sum_wy / sum_w
        pos += c
    return out


def corp_reliability_decomposition(
    y_true: Sequence[float],
    y_prob: Sequence[float],
) -> CORPDecomposition:
    """Exact tuning-parameter-free CORP isotonic Brier decomposition (Dimitriadis, Gneiting & Jordan 2021).

    Computes isotonic recalibrated Conditional Event Probabilities ``cep = PAVA(y | p)`` and
    uses the exact proper-score CORP decomposition:
      - ``S   = mean((p - y)^2)`` (forecast Brier score)
      - ``S_c = mean((cep - y)^2)`` (isotonic-recalibrated Brier score; ``S_c <= S`` and ``S_c <= UNC``)
      - ``MCB = max(0, S - S_c)`` (miscalibration; 0 iff ``p`` is already isotonic-calibrated)
      - ``DSC = max(0, UNC - S_c) = mean((cep - y_bar)^2)`` (discrimination; higher is sharper)
      - ``UNC = y_bar * (1 - y_bar)`` (base-rate uncertainty)
      - ``Brier == MCB - DSC + UNC`` holds identically to machine precision with zero binning parameters.
    """
    yt = np.asarray(y_true, dtype=float)
    yp = np.clip(np.asarray(y_prob, dtype=float), 0.0, 1.0)
    if yt.shape != yp.shape or yt.ndim != 1 or yt.size == 0:
        raise ValueError("y_true and y_prob must be non-empty 1D arrays of equal length.")

    order = np.argsort(yp, kind="mergesort")
    p_s = yp[order]
    y_s = yt[order]

    # Collapse exact ties in predicted probabilities before PAVA so tied predictions share one CEP.
    _, inv_idx, counts = np.unique(p_s, return_inverse=True, return_counts=True)
    y_sums = np.bincount(inv_idx, weights=y_s)
    y_means = y_sums / counts
    cep_uniq = pav_isotonic(y_means, weights=counts.astype(float))
    cep = cep_uniq[inv_idx]

    n = int(yt.size)
    y_bar = float(np.mean(y_s))
    brier = float(np.mean((p_s - y_s) ** 2))
    brier_cal = float(np.mean((cep - y_s) ** 2))
    unc = y_bar * (1.0 - y_bar)
    mcb = max(0.0, brier - brier_cal)
    dsc = max(0.0, unc - brier_cal)
    corp_ece = float(np.mean(np.abs(p_s - cep)))
    n_levels = int(np.unique(np.round(cep, 10)).size)

    return CORPDecomposition(
        n=n,
        brier=round(brier, 6),
        corp_ece=round(corp_ece, 6),
        mcb=round(mcb, 6),
        dsc=round(dsc, 6),
        unc=round(unc, 6),
        n_isotonic_levels=n_levels,
        mean_pred=round(float(np.mean(p_s)), 5),
        mean_obs=round(y_bar, 5),
    )


def optimal_log_pool_weight(
    model_probs: np.ndarray,
    market_probs: np.ndarray,
    outcomes: np.ndarray,
) -> LogPoolTestResult:
    """Find optimal weight ``w in [0, 1]`` for log-opinion pool ``P_pool ∝ P_model^w * P_mkt^(1-w)``.

    ``model_probs`` and ``market_probs`` have shape ``(N, K)``; ``outcomes`` is an integer array
    of shape ``(N,)`` with class indices in ``0..K-1``.
    """
    pm = np.clip(np.asarray(model_probs, dtype=float), 1e-6, 1.0)
    pk = np.clip(np.asarray(market_probs, dtype=float), 1e-6, 1.0)
    pm = pm / np.sum(pm, axis=1, keepdims=True)
    pk = pk / np.sum(pk, axis=1, keepdims=True)
    y = np.asarray(outcomes, dtype=int)
    n = int(y.size)
    if pm.shape != pk.shape or pm.ndim != 2 or pm.shape[0] != n or n == 0:
        raise ValueError("Shapes of model_probs, market_probs, and outcomes are incompatible.")

    idx = np.arange(n)
    log_pm = np.log(pm)
    log_pk = np.log(pk)

    def _nll(w: float) -> float:
        logits = w * log_pm + (1.0 - w) * log_pk
        logits -= np.max(logits, axis=1, keepdims=True)
        ex = np.exp(logits)
        probs = ex / np.sum(ex, axis=1, keepdims=True)
        return float(-np.mean(np.log(np.clip(probs[idx, y], 1e-12, 1.0))))

    mkt_ll = _nll(0.0)
    mod_ll = _nll(1.0)
    res = minimize_scalar(_nll, bounds=(0.0, 1.0), method="bounded", options={"xatol": 1e-6})
    w_opt = float(res.x)
    pool_ll = float(res.fun)
    if mkt_ll <= pool_ll:
        w_opt = 0.0
        pool_ll = mkt_ll

    return LogPoolTestResult(
        n=n,
        optimal_weight=round(w_opt, 4),
        market_log_loss=round(mkt_ll, 6),
        model_log_loss=round(mod_ll, 6),
        pool_log_loss=round(pool_ll, 6),
        log_loss_gain=round(mkt_ll - pool_ll, 6),
    )


def propose_family_calibration_update(
    settled_rows: Iterable[Mapping[str, Any]],
    current_calibration: Mapping[str, Any] | None = None,
    *,
    prior_n: float = 150.0,
    min_n: int = 40,
    max_negative_shift: float = -0.15,
) -> dict[str, Any]:
    """Generate a safe James-Stein shrunk calibration proposal per market family.

    Never inflates probabilities (positive residuals are capped at ``0.0``) and skips
    families with fewer than ``min_n`` settled observations so single-day noise cannot
    corrupt production calibration files.
    """
    by_fam: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row in settled_rows:
        name = row.get("secim_adi") or row.get("name") or row.get("selection")
        fam = row.get("family") or market_family(str(name or ""))
        p_raw = row.get("olasilik") if "olasilik" in row else row.get("p")
        won_raw = row.get("tuttu") if "tuttu" in row else row.get("won")
        if p_raw is None or won_raw is None:
            continue
        try:
            p = float(p_raw)
            w = 1.0 if (won_raw in (True, 1, "1", "true", "True", "W")) else 0.0
        except (TypeError, ValueError):
            continue
        if 0.0 < p < 1.0:
            by_fam[str(fam)].append((p, w))

    existing_fams = dict((current_calibration or {}).get("families") or {})
    proposals: dict[str, dict[str, Any]] = {}
    for fam, pairs in sorted(by_fam.items()):
        n = len(pairs)
        ps = np.array([x[0] for x in pairs], dtype=float)
        ws = np.array([x[1] for x in pairs], dtype=float)
        mean_p = float(np.mean(ps))
        hit_rate = float(np.mean(ws))
        raw_resid = hit_rate - mean_p
        shrunk_resid = raw_resid * (n / (n + float(prior_n)))
        # Asymmetric safety rule: never add positive bias, only penalize systematic overconfidence.
        proposed_adj = max(float(max_negative_shift), min(0.0, shrunk_resid)) if n >= min_n else 0.0
        prev_adj = float((existing_fams.get(fam) or {}).get("residual_adjustment", 0.0))
        proposals[fam] = {
            "n": n,
            "eligible": n >= min_n,
            "mean_pred": round(mean_p, 4),
            "hit_rate": round(hit_rate, 4),
            "raw_residual": round(raw_resid, 4),
            "shrunk_residual": round(shrunk_resid, 4),
            "previous_adjustment": round(prev_adj, 4),
            "proposed_adjustment": round(proposed_adj, 4),
            "delta": round(proposed_adj - prev_adj, 4),
        }
    return {
        "prior_n": float(prior_n),
        "min_n": int(min_n),
        "n_total": sum(len(v) for v in by_fam.values()),
        "families": proposals,
    }


def evaluate_tipsaudit_csv(
    csv_path: Path | str,
    *,
    methods: Sequence[DevigMethod] = ("multiplicative", "power", "shin", "odds_ratio", "goto", "ensemble"),
) -> dict[str, Any]:
    """Benchmark devigging methods, CLV significance, and Brier MCB/DSC on ``data/tipsaudit.csv``."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"tipsaudit file not found: {path}")

    close_odds: list[list[float]] = []
    open_odds: list[list[float]] = []
    outcomes: list[int] = []
    clvs: list[float] = []
    won_flags: list[int] = []
    res_map = {"1": 0, "X": 1, "2": 2}

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            res = (row.get("result") or "").strip().upper()
            if res not in res_map or (row.get("void_reason") or "").strip():
                continue
            try:
                co = [float(row["pin_close_home"]), float(row["pin_close_draw"]), float(row["pin_close_away"])]
                oo = [float(row["pin_open_home"]), float(row["pin_open_draw"]), float(row["pin_open_away"])]
            except (KeyError, TypeError, ValueError):
                continue
            if min(co) <= 1.01 or min(oo) <= 1.01:
                continue
            close_odds.append(co)
            open_odds.append(oo)
            outcomes.append(res_map[res])

            clv_raw = row.get("prediction_clv_pct")
            if clv_raw not in (None, ""):
                try:
                    clvs.append(float(clv_raw) / 100.0)
                    won_flags.append(int(row.get("prediction_won") or 0))
                except ValueError:
                    pass

    close_arr = np.asarray(close_odds, dtype=float)
    open_arr = np.asarray(open_odds, dtype=float)
    y_arr = np.asarray(outcomes, dtype=int)
    n = int(y_arr.size)
    idx = np.arange(n)

    devig_bench: dict[str, dict[str, float]] = {}
    for m in methods:
        probs = devig_batch(close_arr, method=m)
        ll = float(-np.mean(np.log(np.clip(probs[idx, y_arr], 1e-12, 1.0))))
        onehot = np.zeros_like(probs)
        onehot[idx, y_arr] = 1.0
        brier_multi = float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))
        home_dec = brier_decomposition((y_arr == 0).astype(float), probs[:, 0], n_bins=10)
        home_corp = corp_reliability_decomposition((y_arr == 0).astype(float), probs[:, 0])
        devig_bench[m] = {
            "log_loss": round(ll, 6),
            "brier_1x2": round(brier_multi, 6),
            "home_ece": home_dec.ece,
            "home_mcb": home_dec.mcb,
            "home_dsc": home_dec.dsc,
            "corp_ece": home_corp.corp_ece,
            "corp_mcb": home_corp.mcb,
            "corp_dsc": home_corp.dsc,
        }

    # Test whether opening Pinnacle adds anything to closing Pinnacle (sanity check: w ≈ 0).
    p_open = devig_batch(open_arr, method="power")
    p_close = devig_batch(close_arr, method="power")
    open_vs_close = optimal_log_pool_weight(p_open, p_close, y_arr)

    return {
        "n_matches": n,
        "devig_benchmark": devig_bench,
        "clv_report": clv_significance(clvs),
        "open_vs_close_pool": open_vs_close,
        "prediction_hit_rate": round(float(np.mean(won_flags)), 5) if won_flags else None,
    }
