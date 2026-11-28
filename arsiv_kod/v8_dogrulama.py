"""Reproducible empirical benchmark suite for QuantFoot v8 upgrades.

Evaluates on real repository datasets (zero fabricated numbers):
  1. Devigging benchmark (multiplicative, power, shin, odds_ratio, goto, ensemble) on:
     - 7,300+ Pinnacle closing 1X2 matches (data/tipsaudit.csv)
     - 22-league Betfair Exchange closing 1X2 matches (data/global_odds/latest/season_2627/*.csv)
  2. Score-matrix pricing WITH vs WITHOUT Asian Handicap (ah_lines) across season_2627/*.csv
     (comparing log-loss & Brier on Hnd(-1) 1, Hnd(+1) 2, 1.5 Üst, 3.5 Üst, KG Var, Ev 1.5 Üst, Dep 1.5 Üst).
  3. Exponential NPxG/xG form rating walk-forward test against Betfair Exchange closing 1X2
     via log-opinion-pool weight optimization (optimal_log_pool_weight).
  4. Referee profile dispersion (card & goal z-scores across season_2627/*.csv).
  5. CLV statistical significance & Brier MCB/DSC decomposition on data/tipsaudit.csv.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation.clv_tracker import (
    brier_decomposition,
    corp_reliability_decomposition,
    evaluate_tipsaudit_csv,
    optimal_log_pool_weight,
)
from quantfoot.markets.consensus import benchmark_consensus_on_season_2627
from quantfoot.markets.devig import DevigMethod, devig, devig_batch
from quantfoot.markets.line_movement import backtest_sharp_soft_and_steam
from quantfoot.markets.lineup_xg import build_referee_profiles, compute_team_xg_profiles
from quantfoot.markets.tail_goals import (
    CLUB_REGIME,
    fit_tail_rates_from_markets,
    matrix_1x2,
    negative_binomial_score_matrix,
    rake_score_matrix_to_markets,
)
from quantfoot.settings import MARGIN_TILT
from quantfoot.strategy.kelly import adaptive_kelly_stake, kelly_fraction


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def load_season_2627_matches() -> list[dict[str, Any]]:
    folder = ROOT / "data" / "global_odds" / "latest" / "season_2627"
    rows: list[dict[str, Any]] = []
    if not folder.exists():
        return rows
    for path in sorted(folder.glob("*.csv")):
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            for r in csv.DictReader(fh):
                if _flt(r.get("FTHG")) is None or _flt(r.get("FTAG")) is None:
                    continue
                rows.append(r)
    return rows


def benchmark_season_devig(rows: list[dict[str, Any]]) -> dict[str, Any]:
    odds_list: list[list[float]] = []
    outcomes: list[int] = []
    res_map = {"H": 0, "D": 1, "A": 2}
    for r in rows:
        ftr = (r.get("FTR") or "").strip().upper()
        if ftr not in res_map:
            continue
        o = [_flt(r.get(c)) for c in ("BFECH", "BFECD", "BFECA")]
        if any(x is None or x <= 1.01 for x in o):
            o = [_flt(r.get(c)) for c in ("BFEH", "BFED", "BFEA")]
        if any(x is None or x <= 1.01 for x in o):
            continue
        odds_list.append([float(x) for x in o])  # type: ignore[arg-type]
        outcomes.append(res_map[ftr])

    arr = np.asarray(odds_list, dtype=float)
    y = np.asarray(outcomes, dtype=int)
    idx = np.arange(y.size)
    methods: tuple[DevigMethod, ...] = ("multiplicative", "power", "shin", "odds_ratio", "goto", "ensemble")
    out: dict[str, Any] = {"n_matches": int(y.size), "methods": {}}
    for m in methods:
        probs = devig_batch(arr, method=m)
        ll = float(-np.mean(np.log(np.clip(probs[idx, y], 1e-12, 1.0))))
        onehot = np.zeros_like(probs)
        onehot[idx, y] = 1.0
        brier = float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))
        dec = brier_decomposition((y == 0).astype(float), probs[:, 0], n_bins=10)
        corp = corp_reliability_decomposition((y == 0).astype(float), probs[:, 0])
        out["methods"][m] = {
            "log_loss": round(ll, 6),
            "brier_1x2": round(brier, 6),
            "home_ece": dec.ece,
            "home_mcb": dec.mcb,
            "home_dsc": dec.dsc,
            "corp_ece": corp.corp_ece,
            "corp_mcb": corp.mcb,
            "corp_dsc": corp.dsc,
        }
    return out


def benchmark_ah_raking(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare score-matrix derivative accuracy WITH vs WITHOUT sharp |AH|>=0.75 constraints."""
    nu, alpha, kappa = CLUB_REGIME
    targets = ("Hnd(-1) 1", "Hnd(+1) 2", "1.5 Üst", "3.5 Üst", "KG Var", "Ev 1.5 Üst", "Dep 1.5 Üst")
    base_ll: dict[str, list[float]] = {k: [] for k in targets}
    ah_ll: dict[str, list[float]] = {k: [] for k in targets}
    base_bs: dict[str, list[float]] = {k: [] for k in targets}
    ah_bs: dict[str, list[float]] = {k: [] for k in targets}

    n_used = 0
    for r in rows:
        ah_line = _flt(r.get("AHCh"))
        if ah_line is None:
            ah_line = _flt(r.get("AHh"))
        if ah_line is None or abs(ah_line) < 0.75 - 1e-9:
            continue
        x12 = [_flt(r.get(c)) for c in ("BFECH", "BFECD", "BFECA")]
        ou = [_flt(r.get(c)) for c in ("BFEC>2.5", "BFEC<2.5")]
        ah = [_flt(r.get(c)) for c in ("BFECAHH", "BFECAHA")]
        if any(x is None or x <= 1.01 for x in x12 + ou + ah):
            continue
        hg, ag = int(float(r["FTHG"])), int(float(r["FTAG"]))

        p1x2 = devig([float(x) for x in x12], method="power").probabilities  # type: ignore[arg-type]
        p_ov25 = float(devig([float(x) for x in ou], method="power").probabilities[0])  # type: ignore[arg-type]
        p_ah_h = float(devig([float(x) for x in ah], method="power").probabilities[0])  # type: ignore[arg-type]
        if not (0.02 < p_ov25 < 0.98 and 0.02 < p_ah_h < 0.98):
            continue

        _, _, fit_base = fit_tail_rates_from_markets(
            p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], seed_rates=(1.45, 1.15),
            alpha_nb=alpha, shared_kappa=kappa, com_nu=nu, fund_weight=0.0,
        )
        mat_base = rake_score_matrix_to_markets(fit_base, p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], margin_tilt=MARGIN_TILT)

        _, _, fit_ah = fit_tail_rates_from_markets(
            p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], ah_lines=[(ah_line, p_ah_h)], seed_rates=(1.45, 1.15),
            alpha_nb=alpha, shared_kappa=kappa, com_nu=nu, fund_weight=0.0,
        )
        mat_ah = rake_score_matrix_to_markets(
            fit_ah, p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], ah_lines=[(ah_line, p_ah_h)], margin_tilt=MARGIN_TILT
        )

        def _extract(mat: np.ndarray) -> dict[str, float]:
            nh, na = mat.shape
            hi, ai = np.indices((nh, na))
            return {
                "Hnd(-1) 1": float(mat[(hi - ai) >= 2].sum()),
                "Hnd(+1) 2": float(mat[(ai - hi) >= 2].sum()),
                "1.5 Üst": float(mat[(hi + ai) >= 2].sum()),
                "3.5 Üst": float(mat[(hi + ai) >= 4].sum()),
                "KG Var": float(mat[(hi >= 1) & (ai >= 1)].sum()),
                "Ev 1.5 Üst": float(mat[hi >= 2].sum()),
                "Dep 1.5 Üst": float(mat[ai >= 2].sum()),
            }

        actual = {
            "Hnd(-1) 1": 1.0 if (hg - ag) >= 2 else 0.0,
            "Hnd(+1) 2": 1.0 if (ag - hg) >= 2 else 0.0,
            "1.5 Üst": 1.0 if (hg + ag) >= 2 else 0.0,
            "3.5 Üst": 1.0 if (hg + ag) >= 4 else 0.0,
            "KG Var": 1.0 if (hg >= 1 and ag >= 1) else 0.0,
            "Ev 1.5 Üst": 1.0 if hg >= 2 else 0.0,
            "Dep 1.5 Üst": 1.0 if ag >= 2 else 0.0,
        }
        pb = _extract(mat_base)
        pa = _extract(mat_ah)
        for k in targets:
            y = actual[k]
            p0 = float(np.clip(pb[k], 1e-6, 1.0 - 1e-6))
            p1 = float(np.clip(pa[k], 1e-6, 1.0 - 1e-6))
            base_ll[k].append(-(y * math.log(p0) + (1.0 - y) * math.log(1.0 - p0)))
            ah_ll[k].append(-(y * math.log(p1) + (1.0 - y) * math.log(1.0 - p1)))
            base_bs[k].append((p0 - y) ** 2)
            ah_bs[k].append((p1 - y) ** 2)
        n_used += 1

    summary: dict[str, Any] = {"n_matches_with_abs_ah_ge_075": n_used, "markets": {}}
    for k in targets:
        b_ll = float(np.mean(base_ll[k])) if base_ll[k] else 0.0
        a_ll = float(np.mean(ah_ll[k])) if ah_ll[k] else 0.0
        b_bs = float(np.mean(base_bs[k])) if base_bs[k] else 0.0
        a_bs = float(np.mean(ah_bs[k])) if ah_bs[k] else 0.0
        summary["markets"][k] = {
            "base_log_loss": round(b_ll, 6),
            "ah_log_loss": round(a_ll, 6),
            "delta_log_loss": round(a_ll - b_ll, 6),
            "base_brier": round(b_bs, 6),
            "ah_brier": round(a_bs, 6),
            "delta_brier": round(a_bs - b_bs, 6),
        }
    return summary


def benchmark_xg_walkforward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Strict chronological walk-forward test: exponential NPxG/xG model vs Betfair Exchange 1X2."""
    xg_rows: list[tuple[dt.date, dict[str, Any]]] = []
    res_map = {"H": 0, "D": 1, "A": 2}
    for r in rows:
        if _flt(r.get("HxG")) is None or _flt(r.get("AxG")) is None:
            continue
        ftr = (r.get("FTR") or "").strip().upper()
        if ftr not in res_map:
            continue
        o = [_flt(r.get(c)) for c in ("BFECH", "BFECD", "BFECA")]
        if any(x is None or x <= 1.01 for x in o):
            continue
        ds = (r.get("Date") or "").strip()
        d = None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(ds[:10], fmt).date()
                break
            except ValueError:
                continue
        if d is not None:
            xg_rows.append((d, r))

    xg_rows.sort(key=lambda x: x[0])
    if len(xg_rows) < 60:
        return {"n_eval": 0}

    # Evaluate on the second half of matches strictly using prior-date xG history (zero lookahead).
    split = len(xg_rows) // 2
    model_ps: list[np.ndarray] = []
    mkt_ps: list[np.ndarray] = []
    ys: list[int] = []
    by_date_history: list[dict[str, Any]] = [r for _, r in xg_rows[:split]]
    cached_date: dt.date | None = None
    profiles: dict[str, Any] = {}

    for d, r in xg_rows[split:]:
        if d != cached_date:
            profiles = compute_team_xg_profiles(by_date_history, as_of=d - dt.timedelta(days=1), half_life_days=90.0, shrink_games=6.0)
            cached_date = d
        hp = profiles.get(r["HomeTeam"].strip())
        ap = profiles.get(r["AwayTeam"].strip())
        if hp and ap and hp.matches >= 3 and ap.matches >= 3:
            mu_h = float(np.clip(1.42 * hp.attack_index * ap.defense_index, 0.25, 4.5))
            mu_a = float(np.clip(1.12 * ap.attack_index * hp.defense_index, 0.20, 4.0))
            mat = negative_binomial_score_matrix(mu_h, mu_a, alpha_nb=0.0, shared_kappa=0.0, com_nu=1.0)
            pm = matrix_1x2(mat)
            pk = devig([float(r["BFECH"]), float(r["BFECD"]), float(r["BFECA"])], method="power").probabilities
            model_ps.append(pm)
            mkt_ps.append(pk)
            ys.append(res_map[r["FTR"].strip().upper()])
        by_date_history.append(r)

    if not ys:
        return {"n_eval": 0}
    pool = optimal_log_pool_weight(np.vstack(model_ps), np.vstack(mkt_ps), np.asarray(ys, dtype=int))
    return pool.__dict__


def benchmark_adaptive_kelly_monte_carlo(
    n_paths: int = 400,
    n_bets: int = 250,
    true_edge: float = 0.025,
    est_noise_std: float = 0.025,
    seed: int = 2026,
) -> dict[str, Any]:
    """Deterministic Monte Carlo comparison: fixed quarter-Kelly vs drawdown-throttled adaptive Kelly."""
    rng = np.random.default_rng(seed)
    fixed_max_dd: list[float] = []
    adapt_max_dd: list[float] = []
    fixed_end: list[float] = []
    adapt_end: list[float] = []
    fixed_dd25_breach = 0
    adapt_dd25_breach = 0

    for _ in range(n_paths):
        p_true = rng.uniform(0.40, 0.72, size=n_bets)
        odds = (1.0 + true_edge) / p_true
        p_est = np.clip(p_true + rng.normal(0.0, est_noise_std, size=n_bets), 0.05, 0.95)
        wins = rng.random(size=n_bets) < p_true

        bf = 1000.0
        pf = 1000.0
        mdd_f = 0.0

        ba = 1000.0
        pa = 1000.0
        mdd_a = 0.0

        for i in range(n_bets):
            o = float(odds[i])
            pe = float(p_est[i])
            won = bool(wins[i])

            ff = kelly_fraction(pe, o, multiplier=0.25, max_stake=0.03)
            bf += (bf * ff * (o - 1.0)) if won else (-bf * ff)
            pf = max(pf, bf)
            mdd_f = max(mdd_f, (pf - bf) / pf)

            # Adaptive Baker-McHale + drawdown throttle (resets daily/weekly PnL every 5 / 25 bets)
            res = adaptive_kelly_stake(
                pe,
                o,
                bankroll=ba,
                peak_bankroll=pa,
                prob_std=est_noise_std,
                base_multiplier=0.25,
                max_per_bet=0.03,
                drawdown_halt=0.25,
            )
            fa = float(res["stake_fraction"])
            ba += (ba * fa * (o - 1.0)) if won else (-ba * fa)
            pa = max(pa, ba)
            mdd_a = max(mdd_a, (pa - ba) / pa)

        fixed_max_dd.append(mdd_f)
        adapt_max_dd.append(mdd_a)
        fixed_end.append(bf)
        adapt_end.append(ba)
        if mdd_f >= 0.25:
            fixed_dd25_breach += 1
        if mdd_a >= 0.25:
            adapt_dd25_breach += 1

    return {
        "n_paths": n_paths,
        "n_bets_per_path": n_bets,
        "true_edge": true_edge,
        "est_noise_std": est_noise_std,
        "fixed_quarter_kelly": {
            "median_max_dd": round(float(np.median(fixed_max_dd)), 4),
            "p95_max_dd": round(float(np.quantile(fixed_max_dd, 0.95)), 4),
            "dd_ge_25pct_rate": round(fixed_dd25_breach / n_paths, 4),
            "p05_terminal_bankroll": round(float(np.quantile(fixed_end, 0.05)), 2),
            "median_terminal_bankroll": round(float(np.median(fixed_end)), 2),
        },
        "adaptive_kelly": {
            "median_max_dd": round(float(np.median(adapt_max_dd)), 4),
            "p95_max_dd": round(float(np.quantile(adapt_max_dd, 0.95)), 4),
            "dd_ge_25pct_rate": round(adapt_dd25_breach / n_paths, 4),
            "p05_terminal_bankroll": round(float(np.quantile(adapt_end, 0.05)), 2),
            "median_terminal_bankroll": round(float(np.median(adapt_end)), 2),
        },
    }


def main() -> int:
    ta_path = ROOT / "data" / "tipsaudit.csv"
    ta = evaluate_tipsaudit_csv(ta_path)
    ta_steam = backtest_sharp_soft_and_steam(ta_path)
    season_rows = load_season_2627_matches()
    season_devig = benchmark_season_devig(season_rows)
    ah_bench = benchmark_ah_raking(season_rows)
    xg_wf = benchmark_xg_walkforward(season_rows)
    refs = build_referee_profiles(season_rows, min_matches=5)
    top_card_refs = sorted(refs.values(), key=lambda x: x.card_zscore, reverse=True)[:5]
    kelly_mc = benchmark_adaptive_kelly_monte_carlo()
    cons_bench = benchmark_consensus_on_season_2627(ROOT / "data" / "global_odds" / "latest" / "season_2627")

    payload = {
        "tipsaudit": {
            "n_matches": ta["n_matches"],
            "devig_benchmark": ta["devig_benchmark"],
            "clv_report": ta["clv_report"].__dict__,
            "open_vs_close_pool": ta["open_vs_close_pool"].__dict__,
            "prediction_hit_rate": ta["prediction_hit_rate"],
        },
        "tipsaudit_sharp_soft_steam": ta_steam,
        "season_2627_devig": season_devig,
        "season_2627_consensus": cons_bench,
        "season_2627_ah_raking": ah_bench,
        "season_2627_xg_walkforward": xg_wf,
        "season_2627_referees": {
            "n_referees_ge5": len(refs),
            "top_card_zscore": [r.__dict__ for r in top_card_refs],
        },
        "adaptive_kelly_monte_carlo": kelly_mc,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
