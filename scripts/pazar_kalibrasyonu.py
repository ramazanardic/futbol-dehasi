"""Pazar kalibrasyonu: 2.5 Üst, 3.5 Üst, KG Var ve zayıf favori MS 1 — arşivde walk-forward (sızıntısız).

    python scripts/pazar_kalibrasyonu.py onbellek          # üretim fiyatlama hattıyla arşivi fiyatla (≈3 dk, 8 çekirdek)
    python scripts/pazar_kalibrasyonu.py analiz            # güvenilirlik, Brier, log-loss, walk-forward kalibrasyon, ROI
    python scripts/pazar_kalibrasyonu.py analiz --yaz      # + data/calibration/market_calibration.json (yalnız OOS kazanç varsa)

Fiyatlama = kupon motorunun kullandığı hat (scripts/nesine_global.price_event): marjsız (power) 1X2 + 2.5 Alt/Üst,
gol oranları fund_weight=0 ile piyasaya uydurulur, türev pazarlar (3.5 Üst, KG Var) ortak gol tensöründen gelir.
Arşiv oranları data/matches.csv (Bet365 tipi tek büro, kapanış/açılış ayrımı veri setinde yok). Max oranlar
"piyasadaki en iyi fiyat" yerine geçer: Nesine ↔ global adil fiyat seçiminin arşivdeki vekilidir (iyimser).

Walk-forward: her test sezonu (Temmuz–Haziran) için kalibratör yalnız ÖNCEKİ sezonlarla kurulur.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CACHE = ROOT / "reports" / "research" / "backtest_cache_pazar_kalibrasyonu.csv.gz"  # .gitignore: backtest_cache*
OUT_MD = ROOT / "reports" / "research" / "pazar_kalibrasyonu.md"
OUT_JSON = ROOT / "reports" / "research" / "pazar_kalibrasyonu.json"
CAL_FILE = ROOT / "data" / "calibration" / "market_calibration.json"
START = "2010-07-01"


def _season(d: pd.Timestamp) -> int:
    return d.year if d.month >= 7 else d.year - 1


def _price(task: tuple) -> list[float] | None:
    from quantfoot.markets import tail_goals
    from quantfoot.markets.devig import devig
    from quantfoot.markets.goal_markets import goal_probability
    from quantfoot.markets.omni_markets import compute_omni_markets

    div, oh, od, oa, ov, un = task
    try:
        p1x2 = devig([oh, od, oa], method="power").probabilities
        p_ov = float(devig([ov, un], method="power").probabilities[0])
        nu, alpha, kappa = tail_goals.league_tail_regime(div.lower())
        out = [float(p1x2[0]), float(p1x2[1]), float(p1x2[2]), p_ov]
        for taper in (True, False):
            tail_goals.HIGH_TOTAL_RHO_TAPER = taper
            mu_h, mu_a, _ = tail_goals.fit_tail_rates_from_markets(
                p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15), alpha_nb=alpha, shared_kappa=kappa,
                com_nu=nu, fund_weight=0.0)
            joint = compute_omni_markets(mu_h, mu_a, league=div.lower()).joint
            out += [mu_h, mu_a] + [goal_probability(m, joint) for m in ("3.5 Üst", "KG Var", "2.5 Üst", "Skor 0-0", "Skor 1-1")]
        tail_goals.HIGH_TOTAL_RHO_TAPER = True
        return out
    except Exception:
        return None


PRICE_COLS = ["p_h", "p_d", "p_a", "p_o25",
              "mu_h", "mu_a", "p_o35", "p_btts", "p_o25_fit", "p_00", "p_11",
              "mu_h_nt", "mu_a_nt", "p_o35_nt", "p_btts_nt", "p_o25_fit_nt", "p_00_nt", "p_11_nt"]


def cmd_cache(args: argparse.Namespace) -> None:
    cols = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "OddHome", "OddDraw", "OddAway", "Over25", "Under25",
            "MaxHome", "MaxDraw", "MaxAway", "MaxOver25", "MaxUnder25", "FTHome", "FTAway"]
    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"], usecols=cols)
    df = df.dropna(subset=cols[:9] + ["FTHome", "FTAway"])
    df = df[(df[["OddHome", "OddDraw", "OddAway", "Over25", "Under25"]] > 1.0).all(axis=1) & (df.MatchDate >= START)]
    df = df.sort_values(["MatchDate", "Division", "HomeTeam"]).reset_index(drop=True)
    if args.limit:
        df = df.iloc[: args.limit]
    tasks = list(df[["Division", "OddHome", "OddDraw", "OddAway", "Over25", "Under25"]].itertuples(index=False, name=None))
    with ProcessPoolExecutor() as pool:
        preds = list(pool.map(_price, tasks, chunksize=400))
    keep = [i for i, p in enumerate(preds) if p is not None]
    out = df.iloc[keep].copy()
    out[PRICE_COLS] = np.array([preds[i] for i in keep])
    out.to_csv(CACHE, index=False, compression="gzip")
    print(f"{len(out)} / {len(df)} maç fiyatlandı -> {CACHE}")


# ---------------------------------------------------------------------------------------- metrics
def logloss(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[b == k].mean() - y[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def reliability(p: np.ndarray, y: np.ndarray, edges=(0, .2, .3, .4, .5, .55, .6, .65, .7, .8, 1.0001)) -> list[dict]:
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() >= 30:
            rows.append({"bant": f"{lo:.2f}–{min(hi, 1):.2f}", "n": int(m.sum()), "tahmin": round(float(p[m].mean()), 4),
                         "gercek": round(float(y[m].mean()), 4)})
    return rows


def boot_ci(a: np.ndarray, n: int = 400, seed: int = 7) -> tuple[float, float]:
    """95 % bootstrap CI of the mean of per-match log-loss differences."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    means = a[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _ll_vec(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


# ---------------------------------------------------------------------------------------- features
def add_outcomes_and_features(df: pd.DataFrame, half_life: float = 8.0) -> pd.DataFrame:
    """Outcomes + causal (pre-match only) team form residual features and a simple EWMA Poisson stats model."""
    df = df.sort_values(["MatchDate", "Division", "HomeTeam"]).reset_index(drop=True)
    h, a = df.FTHome.to_numpy(int), df.FTAway.to_numpy(int)
    df["y_o25"] = (h + a > 2.5).astype(float)
    df["y_o35"] = (h + a > 3.5).astype(float)
    df["y_btts"] = ((h > 0) & (a > 0)).astype(float)
    df["y_h"] = (h > a).astype(float)
    df["season"] = df.MatchDate.map(_season)
    w = 0.5 ** (1.0 / half_life)
    # form residual: EWMA over a team's matches of (actual total goals - market expected total), and BTTS residual
    res_g: dict[tuple, float] = {}
    res_b: dict[tuple, float] = {}
    n_g: dict[tuple, int] = {}
    # stats model: EWMA attack (goals scored) / defence (conceded) per team, league means
    att: dict[tuple, float] = {}
    dfn: dict[tuple, float] = {}
    lg: dict[str, list[float]] = {}
    f_goal, f_btts, s_lh, s_la, n_min = [], [], [], [], []
    for r in df[["Division", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "mu_h_nt", "mu_a_nt", "p_btts_nt", "MatchDate"]].itertuples(index=False):
        div = r.Division
        kh, ka = (div, r.HomeTeam), (div, r.AwayTeam)
        f_goal.append(0.5 * (res_g.get(kh, 0.0) + res_g.get(ka, 0.0)))
        f_btts.append(0.5 * (res_b.get(kh, 0.0) + res_b.get(ka, 0.0)))
        n_min.append(min(n_g.get(kh, 0), n_g.get(ka, 0)))
        L = lg.setdefault(div, [1.45, 1.15])
        ah, dh = att.get(kh, 1.3), dfn.get(kh, 1.3)
        aa, da = att.get(ka, 1.3), dfn.get(ka, 1.3)
        base = 0.5 * (L[0] + L[1])
        s_lh.append(L[0] * (ah / base) * (da / base))
        s_la.append(L[1] * (aa / base) * (dh / base))
        # update after the match (causal)
        tot_res = (r.FTHome + r.FTAway) - (r.mu_h_nt + r.mu_a_nt)
        b_res = float(r.FTHome > 0 and r.FTAway > 0) - r.p_btts_nt
        for k in (kh, ka):
            res_g[k] = w * res_g.get(k, 0.0) + (1 - w) * tot_res
            res_b[k] = w * res_b.get(k, 0.0) + (1 - w) * b_res
            n_g[k] = n_g.get(k, 0) + 1
        att[kh] = w * ah + (1 - w) * r.FTHome
        dfn[kh] = w * dh + (1 - w) * r.FTAway
        att[ka] = w * aa + (1 - w) * r.FTAway
        dfn[ka] = w * da + (1 - w) * r.FTHome
        L[0] = 0.995 * L[0] + 0.005 * r.FTHome
        L[1] = 0.995 * L[1] + 0.005 * r.FTAway
    df["f_goal"], df["f_btts"], df["n_min"] = f_goal, f_btts, n_min
    df["s_lh"], df["s_la"] = s_lh, s_la
    # stats-model probabilities from independent Poisson
    from scipy.stats import poisson

    g = np.arange(11)
    ph = poisson.pmf(g[None, :], np.asarray(s_lh)[:, None])
    pa = poisson.pmf(g[None, :], np.asarray(s_la)[:, None])
    joint = ph[:, :, None] * pa[:, None, :]
    tot = g[:, None] + g[None, :]
    df["s_o25"] = joint[:, tot > 2.5].sum(axis=1)
    df["s_o35"] = joint[:, tot > 3.5].sum(axis=1)
    df["s_btts"] = joint[:, 1:, 1:].sum(axis=(1, 2))
    df["s_h"] = joint[:, g[:, None] > g[None, :]].sum(axis=1)
    return df


# Derived markets use the NO-taper columns: the 141e724 taper is off in production (see test_taper / tail_goals).
MARKETS = {  # key: (prob column, outcome column, engine selection name, direct-in-production?)
    "2.5 Üst": ("p_o25", "y_o25", "2.5 Üst", True),
    "3.5 Üst": ("p_o35_nt", "y_o35", "3.5 Üst", False),
    "KG Var": ("p_btts_nt", "y_btts", "KG Var", False),
    "MS 1": ("p_h", "y_h", "MS 1", True),
}
WEAK_FAV = (1.70, 2.30)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def run_walk_forward(df: pd.DataFrame, first_test: int = 2016) -> dict:
    from quantfoot.markets.market_calibration import (
        apply_isotonic,
        apply_platt_league,
        fit_isotonic,
        fit_platt_league,
    )

    seasons = sorted(s for s in df.season.unique() if s >= first_test)
    res: dict = {}
    for mk, (pc, yc, _name, _direct) in MARKETS.items():
        preds = {k: [] for k in ("raw", "platt_global", "platt_lig", "isotonic", "platt_lig_form", "stats")}
        ys, divs, odds_home, rows_idx = [], [], [], []
        for s in seasons:
            tr = df[df.season < s]
            te = df[df.season == s]
            if len(te) == 0:
                continue
            pg = fit_platt_league(tr[pc].to_numpy(), tr[yc].to_numpy(), tr.Division.to_numpy(), league_l2=None)
            pl = fit_platt_league(tr[pc].to_numpy(), tr[yc].to_numpy(), tr.Division.to_numpy(), league_l2=200.0)
            iso = fit_isotonic(tr[pc].to_numpy(), tr[yc].to_numpy())
            fcol = "f_btts" if mk == "KG Var" else "f_goal"
            plf = fit_platt_league(tr[pc].to_numpy(), tr[yc].to_numpy(), tr.Division.to_numpy(), league_l2=200.0,
                                   extra=tr[fcol].to_numpy())
            preds["raw"].append(te[pc].to_numpy())
            preds["platt_global"].append(apply_platt_league(pg, te[pc].to_numpy(), te.Division.to_numpy()))
            preds["platt_lig"].append(apply_platt_league(pl, te[pc].to_numpy(), te.Division.to_numpy()))
            preds["isotonic"].append(apply_isotonic(iso, te[pc].to_numpy()))
            preds["platt_lig_form"].append(apply_platt_league(plf, te[pc].to_numpy(), te.Division.to_numpy(), extra=te[fcol].to_numpy()))
            preds["stats"].append(te[{"2.5 Üst": "s_o25", "3.5 Üst": "s_o35", "KG Var": "s_btts", "MS 1": "s_h"}[mk]].to_numpy())
            ys.append(te[yc].to_numpy())
            divs.append(te.Division.to_numpy())
            odds_home.append(te.OddHome.to_numpy())
            rows_idx.append(te.index.to_numpy())
        P = {k: np.concatenate(v) for k, v in preds.items()}
        Y, D, OH, IDX = np.concatenate(ys), np.concatenate(divs), np.concatenate(odds_home), np.concatenate(rows_idx)
        subsets = {"tümü": np.ones(len(Y), bool)}
        if mk == "MS 1":
            subsets["zayıf favori (ev oranı 1.70–2.30)"] = (OH >= WEAK_FAV[0]) & (OH <= WEAK_FAV[1])
        out_m = {"n_test": len(Y), "test_sezonlari": [int(s) for s in seasons], "subsets": {}}
        for sname, m in subsets.items():
            tab = {}
            for k, p in P.items():
                tab[k] = {"logloss": round(logloss(p[m], Y[m]), 5), "brier": round(brier(p[m], Y[m]), 5),
                          "ece": round(ece(p[m], Y[m]), 4), "ort_tahmin": round(float(p[m].mean()), 4)}
            d = _ll_vec(P["platt_lig"][m], Y[m]) - _ll_vec(P["raw"][m], Y[m])
            d2 = _ll_vec(P["platt_lig_form"][m], Y[m]) - _ll_vec(P["platt_lig"][m], Y[m])
            d3 = _ll_vec(P["platt_global"][m], Y[m]) - _ll_vec(P["raw"][m], Y[m])
            out_m["subsets"][sname] = {
                "n": int(m.sum()), "gercek": round(float(Y[m].mean()), 4), "yontemler": tab,
                "ll_fark_platt_lig_eksi_ham": round(float(d.mean()), 6), "ci95_platt_lig_eksi_ham": [round(x, 6) for x in boot_ci(d)],
                "ll_fark_platt_global_eksi_ham": round(float(d3.mean()), 6), "ci95_platt_global_eksi_ham": [round(x, 6) for x in boot_ci(d3)],
                "ll_fark_form_eksi_platt_lig": round(float(d2.mean()), 6), "ci95_form_eksi_platt_lig": [round(x, 6) for x in boot_ci(d2)],
                "guvenilirlik_ham": reliability(P["raw"][m], Y[m]),
                "guvenilirlik_platt_lig": reliability(P["platt_lig"][m], Y[m]),
            }
        # per league (all rows)
        per_lg = []
        for div in sorted(set(D)):
            m = D == div
            per_lg.append({"lig": div, "n": int(m.sum()), "gercek": round(float(Y[m].mean()), 4),
                           "ham_ort": round(float(P["raw"][m].mean()), 4),
                           "ll_ham": round(logloss(P["raw"][m], Y[m]), 5), "ll_platt_lig": round(logloss(P["platt_lig"][m], Y[m]), 5),
                           "ll_platt_global": round(logloss(P["platt_global"][m], Y[m]), 5),
                           "brier_ham": round(brier(P["raw"][m], Y[m]), 5), "brier_platt_lig": round(brier(P["platt_lig"][m], Y[m]), 5)})
        out_m["ligler"] = per_lg
        res[mk] = out_m
        res[mk]["_P"] = P
        res[mk]["_Y"] = Y
        res[mk]["_IDX"] = IDX
    return res


def roi_backtest(df: pd.DataFrame, wf: dict) -> dict:
    """Flat 1-unit bets at the BEST archive price (Max) when calibrated EV ≥ threshold. Optimistic proxy."""
    out = {}
    for mk, ocol in (("2.5 Üst", "MaxOver25"), ("MS 1", "MaxHome")):
        P, Y, IDX = wf[mk]["_P"], wf[mk]["_Y"], wf[mk]["_IDX"]
        odds = df.loc[IDX, ocol].to_numpy(float)
        oh = df.loc[IDX, "OddHome"].to_numpy(float)
        ok = np.isfinite(odds) & (odds > 1.0)
        rows = []
        for sub, m0 in (("tümü", ok), ("zayıf favori", ok & (oh >= WEAK_FAV[0]) & (oh <= WEAK_FAV[1]))):
            if mk != "MS 1" and sub != "tümü":
                continue
            for meth in ("raw", "platt_global", "platt_lig", "platt_lig_form"):
                for thr in (0.0, 0.02, 0.04, 0.06):
                    ev = P[meth] * odds - 1
                    m = m0 & (ev >= thr)
                    n = int(m.sum())
                    if n == 0:
                        continue
                    ret = np.where(Y[m] == 1, odds[m] - 1, -1.0)
                    lo, hi = boot_ci(ret, n=300)
                    rows.append({"alt_kume": sub, "yontem": meth, "esik": thr, "bahis": n, "roi": round(float(ret.mean()), 4),
                                 "ci95": [round(lo, 4), round(hi, 4)]})
        out[mk] = rows
    return out


def test_live_calibration(wf: dict) -> dict:
    """Apply data/calibration/live_calibration.json prob_shift (learned on ~60 matches) to archive OOS probabilities."""
    from quantfoot.evaluation.auto_learn import _prob_band

    path = ROOT / "data" / "calibration" / "live_calibration.json"
    cal = json.load(open(path, encoding="utf-8"))
    shifts = (cal.get("adjustments") or {}).get("prob_shift") or {}
    out = {"kaynak_mac": cal.get("total_matches_settled"), "prob_shift": shifts, "pazarlar": {}}
    for mk, (_pc, _yc, _name, direct) in MARKETS.items():
        p, y = wf[mk]["_P"]["raw"], wf[mk]["_Y"]
        kind = "doğrudan" if direct else "model"
        adj = np.array([min(0.99, max(0.01, x + float(shifts.get(f"{kind}|{_prob_band(x)}", 0.0)))) if _prob_band(x) else x for x in p])
        m = adj != p
        d = _ll_vec(adj, y) - _ll_vec(p, y)
        out["pazarlar"][mk] = {"tur": kind, "etkilenen": int(m.sum()), "ll_ham": round(logloss(p, y), 6),
                               "ll_kaydirmali": round(logloss(adj, y), 6), "fark": round(float(d.mean()), 7),
                               "ci95": [round(x, 7) for x in boot_ci(d)],
                               "etkilenen_ll_fark": round(float(d[m].mean()), 6) if m.any() else None}
    return out


def test_taper(df: pd.DataFrame) -> dict:
    """141e724 high-total Dixon-Coles taper vs no taper, all test-era matches (no fitting involved: pure OOS)."""
    t = df[df.season >= 2016]
    hi = (t.mu_h_nt + t.mu_a_nt) > 2.8
    out = {}
    for lbl, m in (("tümü", np.ones(len(t), bool)), ("toplam gol beklentisi > 2.8", hi.to_numpy())):
        rows = {}
        for mk, (a, b, ycol) in {"3.5 Üst": ("p_o35", "p_o35_nt", "y_o35"), "KG Var": ("p_btts", "p_btts_nt", "y_btts"),
                                 "Skor 0-0": ("p_00", "p_00_nt", None), "Skor 1-1": ("p_11", "p_11_nt", None)}.items():
            if ycol is None:
                hg, ag = t.FTHome.to_numpy(int), t.FTAway.to_numpy(int)
                y = ((hg == 0) & (ag == 0)) if mk == "Skor 0-0" else ((hg == 1) & (ag == 1))
                y = y.astype(float)
            else:
                y = t[ycol].to_numpy()
            pa, pb = t[a].to_numpy(), t[b].to_numpy()
            d = _ll_vec(pa[m], y[m]) - _ll_vec(pb[m], y[m])
            rows[mk] = {"n": int(m.sum()), "gercek": round(float(y[m].mean()), 4), "taperli": round(float(pa[m].mean()), 4),
                        "tapersiz": round(float(pb[m].mean()), 4), "ll_taperli": round(logloss(pa[m], y[m]), 6),
                        "ll_tapersiz": round(logloss(pb[m], y[m]), 6), "fark": round(float(d.mean()), 7),
                        "ci95": [round(x, 7) for x in boot_ci(d)]}
        out[lbl] = rows
    return out


def test_pick_rule(df: pd.DataFrame, min_ev: float = 0.02) -> dict:
    """Main-pick rule on the archive (2016+): old = most probable selection (p ≥ 55 %, odds ≥ 1.20) vs new = highest
    EV (EV ≥ min_ev, same floors). Candidates: MS 1/0/2 and 2.5 Üst/Alt with the fair (devigged) probability;
    priced at the best archive odds (Max, optimistic) and at the single-book odds (margin like a normal bookmaker)."""
    t = df[df.season >= 2016].dropna(subset=["MaxHome", "MaxDraw", "MaxAway", "MaxOver25", "MaxUnder25"])
    P = np.column_stack([t.p_h, t.p_d, t.p_a, t.p_o25, 1 - t.p_o25])
    hg, ag = t.FTHome.to_numpy(int), t.FTAway.to_numpy(int)
    Y = np.column_stack([hg > ag, hg == ag, hg < ag, hg + ag > 2.5, hg + ag < 2.5]).astype(float)
    out = {}
    for lbl, cols in (("en iyi fiyat (Max)", ["MaxHome", "MaxDraw", "MaxAway", "MaxOver25", "MaxUnder25"]),
                      ("tek büro fiyatı", ["OddHome", "OddDraw", "OddAway", "Over25", "Under25"])):
        O = t[cols].to_numpy(float)
        ok = (O >= 1.20) & (P >= 0.55)
        res = {}
        for rule in ("olasilik", "ev"):
            if rule == "olasilik":
                score = np.where(ok, P, -np.inf)
            else:
                ev = P * O - 1
                score = np.where(ok & (ev >= min_ev), ev, -np.inf)
            j = np.argmax(score, axis=1)
            has = np.isfinite(score[np.arange(len(t)), j])
            o = O[np.arange(len(t)), j][has]
            y = Y[np.arange(len(t)), j][has]
            ret = np.where(y == 1, o - 1, -1.0)
            lo, hi = boot_ci(ret, n=300) if len(ret) else (float("nan"), float("nan"))
            res[rule] = {"secim": int(has.sum()), "isabet": round(float(y.mean()), 4) if len(y) else None,
                         "ort_oran": round(float(o.mean()), 3) if len(o) else None,
                         "roi": round(float(ret.mean()), 4) if len(ret) else None, "ci95": [round(lo, 4), round(hi, 4)]}
        out[lbl] = res
    return {"min_ev": min_ev, "n_mac": len(t), "sonuc": out}


def build_production_calibration(df: pd.DataFrame, wf: dict, keep: dict) -> dict:
    """Fit the kept calibrators on ALL archive seasons (for live use on future matches)."""
    from quantfoot.markets.market_calibration import fit_platt_league

    cal = {"version": 1, "fitted_on": f"data/matches.csv {df.MatchDate.min().date()} – {df.MatchDate.max().date()}", "n": len(df),
           "applies_to": "türetilmiş (doğrudan kote edilmeyen) seçimler; bkz. reports/research/pazar_kalibrasyonu.md",
           "method": "Platt (logit-lineer) + lig sapması (L2 daraltma), walk-forward doğrulandı",
           "markets": {}}
    for mk, (pc, yc, name, direct) in MARKETS.items():
        if not keep.get(mk):
            continue
        p = fit_platt_league(df[pc].to_numpy(), df[yc].to_numpy(), df.Division.to_numpy(), league_l2=200.0)
        p["direct_in_production"] = direct
        if mk == "MS 1":
            p["only_home_odds_range"] = None
        cal["markets"][name] = p
    return cal


def cmd_analyze(args: argparse.Namespace) -> None:
    df = pd.read_csv(CACHE, parse_dates=["MatchDate"])
    df = add_outcomes_and_features(df)
    wf = run_walk_forward(df)
    roi = roi_backtest(df, wf)
    live = test_live_calibration(wf)
    taper = test_taper(df)
    pick = test_pick_rule(df)
    keep = {}
    for mk, r in wf.items():
        s = r["subsets"]["tümü"]
        ci = s["ci95_platt_lig_eksi_ham"]
        keep[mk] = bool(ci[1] < 0)  # keep only if log-loss improvement's whole 95 % CI is below zero
    payload = {"n_mac": len(df), "donem": [str(df.MatchDate.min().date()), str(df.MatchDate.max().date())],
               "walk_forward": {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in wf.items()},
               "roi": roi, "live_calibration_testi": live, "rho_taper_testi": taper, "secim_kurali_testi": pick,
               "kalibrasyon_tutuldu": keep}
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.yaz:
        cal = build_production_calibration(df, wf, keep)
        CAL_FILE.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"yazıldı: {CAL_FILE} pazarlar={list(cal['markets'])}")
    write_md(payload)
    print(json.dumps({"keep": keep, "n": len(df)}, ensure_ascii=False))


def write_md(pl: dict) -> None:
    L = ["# Pazar kalibrasyonu — 2.5 Üst, 3.5 Üst, KG Var, MS 1 (zayıf favori dahil)", "",
         f"Veri: `data/matches.csv`, {pl['n_mac']} maç ({pl['donem'][0]} – {pl['donem'][1]}), 22 lig. Fiyatlama: kupon motorunun "
         "hattı (marjsız 1X2 + 2.5 A/Ü → gol tensörü). Walk-forward: her test sezonunda kalibratör yalnız önceki sezonlarla kurulur. "
         "Arşiv oranları tek büro (Bet365 tipi) — kapanış olduğu garanti değil; 3.5 Üst ve KG Var için arşivde piyasa oranı yok.", ""]
    for mk, r in pl["walk_forward"].items():
        L += [f"## {mk}", ""]
        for sname, s in r["subsets"].items():
            L += [f"### {sname} — n={s['n']}, gerçekleşen %{s['gercek'] * 100:.1f}", "",
                  "| Yöntem | Ort. tahmin | Log-loss | Brier | ECE |", "|---|---|---|---|---|"]
            for k, t in s["yontemler"].items():
                L.append(f"| {k} | %{t['ort_tahmin'] * 100:.1f} | {t['logloss']:.5f} | {t['brier']:.5f} | {t['ece']:.4f} |")
            L += ["", f"- Platt+lig − ham log-loss: {s['ll_fark_platt_lig_eksi_ham']:+.6f} (95% GA {s['ci95_platt_lig_eksi_ham']})",
                  f"- Platt global − ham: {s['ll_fark_platt_global_eksi_ham']:+.6f} (95% GA {s['ci95_platt_global_eksi_ham']})",
                  f"- Form özelliği − Platt+lig: {s['ll_fark_form_eksi_platt_lig']:+.6f} (95% GA {s['ci95_form_eksi_platt_lig']})", "",
                  "| Bant | n | Ham tahmin | Gerçek | Platt+lig tahmin | Gerçek |", "|---|---|---|---|---|---|"]
            cal = {x["bant"]: x for x in s["guvenilirlik_platt_lig"]}
            for x in s["guvenilirlik_ham"]:
                c = cal.get(x["bant"], {})
                L.append(f"| {x['bant']} | {x['n']} | %{x['tahmin'] * 100:.1f} | %{x['gercek'] * 100:.1f} | "
                         f"{'%' + format(c['tahmin'] * 100, '.1f') if c else '-'} | {'%' + format(c['gercek'] * 100, '.1f') if c else '-'} |")
            L.append("")
        L += ["| Lig | n | Gerçek | Ham ort. | LL ham | LL Platt+lig | LL Platt global |", "|---|---|---|---|---|---|---|"]
        for x in r["ligler"]:
            L.append(f"| {x['lig']} | {x['n']} | %{x['gercek'] * 100:.1f} | %{x['ham_ort'] * 100:.1f} | {x['ll_ham']:.5f} | "
                     f"{x['ll_platt_lig']:.5f} | {x['ll_platt_global']:.5f} |")
        L.append("")
    L += ["## ROI vekili (arşivdeki en iyi fiyat = Max, EV ≥ eşik)", "",
          "| Pazar | Alt küme | Yöntem | Eşik | Bahis | ROI | 95% GA |", "|---|---|---|---|---|---|---|"]
    for mk, rows in pl["roi"].items():
        for x in rows:
            L.append(f"| {mk} | {x['alt_kume']} | {x['yontem']} | {x['esik']:+.2f} | {x['bahis']} | {x['roi'] * 100:+.2f}% | "
                     f"{x['ci95'][0] * 100:+.1f}% – {x['ci95'][1] * 100:+.1f}% |")
    lv = pl["live_calibration_testi"]
    L += ["", f"## live_calibration.json prob_shift testi ({lv['kaynak_mac']} maçtan öğrenilmiş)", "",
          "| Pazar | Tür | Etkilenen | LL ham | LL kaydırmalı | Fark | 95% GA |", "|---|---|---|---|---|---|---|"]
    for mk, x in lv["pazarlar"].items():
        L.append(f"| {mk} | {x['tur']} | {x['etkilenen']} | {x['ll_ham']:.6f} | {x['ll_kaydirmali']:.6f} | {x['fark']:+.7f} | {x['ci95']} |")
    L += ["", "## 141e724 yüksek-toplam Dixon–Coles taper testi (2016+ maçları)", ""]
    for lbl, rows in pl["rho_taper_testi"].items():
        L += [f"### {lbl}", "", "| Pazar | n | Gerçek | Taperlı | Tapersız | LL taperlı | LL tapersız | Fark | 95% GA |", "|---|---|---|---|---|---|---|---|---|"]
        for mk, x in rows.items():
            L.append(f"| {mk} | {x['n']} | %{x['gercek'] * 100:.2f} | %{x['taperli'] * 100:.2f} | %{x['tapersiz'] * 100:.2f} | "
                     f"{x['ll_taperli']:.6f} | {x['ll_tapersiz']:.6f} | {x['fark']:+.7f} | {x['ci95']} |")
        L.append("")
    pk = pl["secim_kurali_testi"]
    L += [f"## Ana tercih kuralı: en olası seçim vs en yüksek EV (EV ≥ {pk['min_ev']:+.2f}), {pk['n_mac']} maç (2016+)", "",
          "| Fiyat | Kural | Seçim | İsabet | Ort. oran | ROI | 95% GA |", "|---|---|---|---|---|---|---|"]
    for lbl, res in pk["sonuc"].items():
        for rule, x in res.items():
            if x["roi"] is None:
                continue
            L.append(f"| {lbl} | {rule} | {x['secim']} | %{x['isabet'] * 100:.1f} | {x['ort_oran']:.2f} | {x['roi'] * 100:+.2f}% | "
                     f"{x['ci95'][0] * 100:+.1f}% – {x['ci95'][1] * 100:+.1f}% |")
    L += ["", f"Tutulan kalibratörler (95% GA tamamen sıfırın altında): {pl['kalibrasyon_tutuldu']}", ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("onbellek")
    c.add_argument("--limit", type=int, default=0)
    c.set_defaults(func=cmd_cache)
    a = sub.add_parser("analiz")
    a.add_argument("--yaz", action="store_true")
    a.set_defaults(func=cmd_analyze)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
