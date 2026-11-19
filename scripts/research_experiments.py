"""Research experiments: does anything in this repository carry information the market has not priced?

    python scripts/research_experiments.py cache        # run the walk-forward backtest once, cache predictions
    python scripts/research_experiments.py pool         # pooling test of every model vs the Bet365 price
    python scripts/research_experiments.py rest         # do rest days add information beyond the market?
    python scripts/research_experiments.py sharp-soft   # Pinnacle-open vs best-soft-book strategy (tipsaudit.csv)

Results are written to reports/research/.  All tests are out-of-sample: model predictions come
from the expanding walk-forward backtest (refit only on data before each season), and
regression-based tests use a chronological train / test split.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from quantfoot.evaluation.market_benchmark import mean_with_ci, pooling_test
from quantfoot.markets.devig import devig_batch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "research"
CACHE = OUT / "backtest_cache.npz"
CACHE_META = OUT / "backtest_cache_meta.parquet"


def _save(name: str, payload: dict, md: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


# ----------------------------------------------------------------------------------------------
def cmd_cache(_: argparse.Namespace) -> None:
    from quantfoot.evaluation.backtest import run_walk_forward_backtest

    res = run_walk_forward_backtest()
    OUT.mkdir(parents=True, exist_ok=True)
    comps = {f"comp_{k}": np.asarray(v, dtype=float) for k, v in res["components"].items() if np.ndim(v) == 2}
    np.savez_compressed(CACHE, y=res["y_test"], p_b365=res["p_b365_devig"], **comps)
    cols = [c for c in ("MatchDate", "Division", "HomeTeam", "AwayTeam", "OddHome", "OddDraw", "OddAway",
                        "MaxHome", "MaxDraw", "MaxAway", "FTHome", "FTAway") if c in res["test_df"].columns]
    res["test_df"][cols].to_parquet(CACHE_META)
    print(f"önbellek: {CACHE.relative_to(ROOT)} ({len(res['y_test'])} test maçı, {len(comps)} model)")


def cmd_pool(_: argparse.Namespace) -> None:
    data = np.load(CACHE)
    y, p_mkt = data["y"], data["p_b365"]
    meta = pd.read_parquet(CACHE_META)
    rows = []
    for key in sorted(k for k in data.files if k.startswith("comp_")):
        res = pooling_test(p_mkt, data[key], y, n_boot=300)
        rows.append({"model": key[5:], **res.__dict__})
    rows.sort(key=lambda r: -r["weight"])
    # Per-season check for the calibrated ensemble (stability of the weight).
    seasons = []
    if "comp_calibrated_ensemble" in data.files:
        season = pd.to_datetime(meta["MatchDate"]).apply(lambda d: d.year if d.month >= 7 else d.year - 1).to_numpy()
        for s in np.unique(season):
            m = season == s
            r = pooling_test(p_mkt[m], data["comp_calibrated_ensemble"][m], y[m], n_boot=300)
            seasons.append({"season": f"{s}/{s + 1 - 2000:02d}", **r.__dict__})
    md = ["# Model piyasaya bilgi katıyor mu? (ileri-yürüyen backtest, Bet365 marjsız fiyatına karşı)", "",
          f"Test: {len(y)} maç, {meta['MatchDate'].min()[:10] if isinstance(meta['MatchDate'].min(), str) else str(meta['MatchDate'].min())[:10]} – "
          f"{str(meta['MatchDate'].max())[:10]}. Havuz: p ∝ p_piyasa^(1−w) · p_model^w; w=0 → model bilgi katmıyor.", "",
          "| Model | w | %95 GA | log-loss piyasa | log-loss model | log-loss havuz |", "|---|---|---|---|---|---|"]
    md += [f"| {r['model']} | {r['weight']:.2f} | {r['ci_low']:.2f} – {r['ci_high']:.2f} | {r['logloss_market']:.5f} | "
           f"{r['logloss_model']:.5f} | {r['logloss_pool']:.5f} |" for r in rows]
    if seasons:
        md += ["", "## Kalibre topluluk modeli: sezon sezon", "", "| Sezon | n | w | %95 GA | kazanç (log-loss) |", "|---|---|---|---|---|"]
        md += [f"| {s['season']} | {s['n']} | {s['weight']:.2f} | {s['ci_low']:.2f} – {s['ci_high']:.2f} | "
               f"{s['logloss_market'] - s['logloss_pool']:+.5f} |" for s in seasons]
    _save("pooling_test", {"models": rows, "seasons": seasons}, md)


# ----------------------------------------------------------------------------------------------
def _rest_days(df: pd.DataFrame) -> pd.DataFrame:
    """Days since each team's previous match in the data set (league matches only)."""
    long = pd.concat([
        df[["MatchDate", "HomeTeam"]].rename(columns={"HomeTeam": "team"}).assign(idx=df.index, side="h"),
        df[["MatchDate", "AwayTeam"]].rename(columns={"AwayTeam": "team"}).assign(idx=df.index, side="a"),
    ]).sort_values(["team", "MatchDate"])
    long["rest"] = long.groupby("team")["MatchDate"].diff().dt.days
    wide = long.pivot_table(index="idx", columns="side", values="rest")
    return wide.rename(columns={"h": "rest_h", "a": "rest_a"})


def cmd_rest(args: argparse.Namespace) -> None:
    from sklearn.linear_model import LogisticRegression

    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"],
                     usecols=["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "OddHome", "OddDraw", "OddAway"])
    df = df[(df.MatchDate >= "2012-07-01")].dropna().reset_index(drop=True)
    df = df[(df[["OddHome", "OddDraw", "OddAway"]] > 1.0).all(axis=1)].reset_index(drop=True)
    df = df.join(_rest_days(df))
    df = df.dropna(subset=["rest_h", "rest_a"])
    df = df[(df.rest_h <= 30) & (df.rest_a <= 30)].reset_index(drop=True)  # drop season breaks
    p_mkt = devig_batch(df[["OddHome", "OddDraw", "OddAway"]].to_numpy(float), method="power")
    y = np.where(df.FTHome > df.FTAway, 0, np.where(df.FTHome == df.FTAway, 1, 2))
    logit = np.log(np.clip(p_mkt, 1e-9, 1))
    short_h = (df.rest_h <= 3).astype(float).to_numpy()
    short_a = (df.rest_a <= 3).astype(float).to_numpy()
    diff = np.clip(df.rest_h - df.rest_a, -10, 10).to_numpy(float)
    X_base = logit
    X_rest = np.column_stack([logit, short_h, short_a, diff / 10.0])
    train = (df.MatchDate < args.test_from).to_numpy()
    test = ~train

    def _fit_ll(X: np.ndarray) -> tuple[float, LogisticRegression]:
        clf = LogisticRegression(max_iter=2000, C=1e4).fit(X[train], y[train])
        p = clf.predict_proba(X[test])
        return float(-np.mean(np.log(np.clip(p[np.arange(test.sum()), y[test]], 1e-12, 1)))), clf

    ll_mkt = float(-np.mean(np.log(np.clip(p_mkt[test][np.arange(test.sum()), y[test]], 1e-12, 1))))
    ll_base, _ = _fit_ll(X_base)
    ll_rest, clf = _fit_ll(X_rest)
    # Bootstrap the per-match log-loss difference (rest model vs recalibrated market).
    p_b = LogisticRegression(max_iter=2000, C=1e4).fit(X_base[train], y[train]).predict_proba(X_base[test])
    p_r = clf.predict_proba(X_rest[test])
    rows = np.arange(test.sum())
    d = np.log(np.clip(p_r[rows, y[test]], 1e-12, 1)) - np.log(np.clip(p_b[rows, y[test]], 1e-12, 1))
    gain = mean_with_ci(list(d))
    # Raw effect sizes in the test period, conditional on the market: actual minus market home-win rate.
    t = df[test].assign(p_home=p_mkt[test][:, 0], home_win=(y[test] == 0).astype(float))
    groups = {
        "ev kısa dinlenme (≤3 gün), dep ≥5": t[(t.rest_h <= 3) & (t.rest_a >= 5)],
        "dep kısa dinlenme (≤3 gün), ev ≥5": t[(t.rest_a <= 3) & (t.rest_h >= 5)],
        "ikisi de ≥5 gün": t[(t.rest_h >= 5) & (t.rest_a >= 5)],
    }
    eff = {k: {"n": len(g), "gerçek_ev_galibiyeti": float(g.home_win.mean()), "piyasa_ev_olasılığı": float(g.p_home.mean())}
           for k, g in groups.items() if len(g)}
    md = ["# Dinlenme günü piyasanın ötesinde bilgi taşıyor mu?", "",
          f"Veri: lig maçları {df.MatchDate.min():%Y-%m} – {df.MatchDate.max():%Y-%m}; eğitim < {args.test_from}, test ≥ {args.test_from} "
          f"({int(test.sum())} maç). Dinlenme = aynı veri setindeki önceki maçtan bu yana gün (kupa / Avrupa maçları veri setinde yok, "
          "bu yüzden kısa dinlenme eksik ölçülür).", "",
          f"- Test log-loss — marjsız piyasa: {ll_mkt:.5f} | yeniden kalibre piyasa: {ll_base:.5f} | piyasa + dinlenme: {ll_rest:.5f}",
          f"- Maç başı log-olabilirlik kazancı (dinlenme modeli − kalibre piyasa): {gain[0]:+.6f} (%95 GA {gain[1]:+.6f} – {gain[2]:+.6f})",
          "", "| Grup (test) | n | Gerçek ev galibiyeti | Piyasanın ev olasılığı |", "|---|---|---|---|"]
    md += [f"| {k} | {v['n']} | %{v['gerçek_ev_galibiyeti'] * 100:.1f} | %{v['piyasa_ev_olasılığı'] * 100:.1f} |" for k, v in eff.items()]
    md += ["", "Yorum: güven aralığı sıfırı içeriyorsa dinlenme günü, piyasanın zaten fiyatladığı bilginin ötesinde bir şey katmıyor."]
    _save("rest_days", {"ll_market": ll_mkt, "ll_recal": ll_base, "ll_rest": ll_rest, "gain": gain, "groups": eff,
                        "n_test": int(test.sum()), "coef": clf.coef_.tolist()}, md)


# ----------------------------------------------------------------------------------------------
def cmd_sharp_soft(args: argparse.Namespace) -> None:
    df = pd.read_csv(ROOT / "data" / "tipsaudit.csv", parse_dates=["kickoff_utc"])
    df = df[df["result"].isin(["1", "X", "2"])].copy()
    sides = [("home", "1", 0), ("draw", "X", 1), ("away", "2", 2)]
    pin_open = df[[f"pin_open_{s}" for s, _, _ in sides]].to_numpy(float)
    pin_close = df[[f"pin_close_{s}" for s, _, _ in sides]].to_numpy(float)
    soft = df[[f"best_soft_{s}" for s, _, _ in sides]].to_numpy(float)
    ok = np.isfinite(pin_open).all(1) & np.isfinite(pin_close).all(1) & np.isfinite(soft).all(1) & (pin_open > 1).all(1)
    df, pin_open, pin_close, soft = df[ok], pin_open[ok], pin_close[ok], soft[ok]
    y = df["result"].map({"1": 0, "X": 1, "2": 2}).to_numpy()
    p_open = devig_batch(pin_open, method="power")
    p_close = devig_batch(pin_close, method="power")
    rows_out = []
    for thr in (0.0, 0.01, 0.025, 0.05):
        for max_odds in (3.5, 6.0):
            bets = []
            for i in range(len(df)):
                for k in range(3):
                    ev = p_open[i, k] * soft[i, k] - 1.0
                    if ev >= thr and soft[i, k] <= max_odds:
                        bets.append((soft[i, k] - 1.0 if y[i] == k else -1.0, p_close[i, k] * soft[i, k] - 1.0))
            if not bets:
                continue
            pl = [b[0] for b in bets]
            clv = [b[1] for b in bets]
            roi = mean_with_ci(pl)
            c = mean_with_ci(clv)
            rows_out.append({"min_ev": thr, "max_odds": max_odds, "n": len(bets), "roi": roi, "fair_clv": c})
    # Reference: is the Pinnacle close better than the open (it should be)?
    r = np.arange(len(y))
    ll_open = float(-np.mean(np.log(p_open[r, y])))
    ll_close = float(-np.mean(np.log(p_close[r, y])))
    md = ["# Keskin–yumuşak oran farkı: Pinnacle açılış fiyatına göre en iyi yumuşak büro", "",
          f"Veri: `tipsaudit.csv`, {len(df)} maç ({df.kickoff_utc.min():%Y-%m-%d} – {df.kickoff_utc.max():%Y-%m-%d}). "
          f"Pinnacle log-loss: açılış {ll_open:.5f}, kapanış {ll_close:.5f}.", "",
          "Kural: marjsız Pinnacle açılış olasılığı × en iyi yumuşak oran − 1 ≥ eşik ise bahis. "
          "Adil CLV = Pinnacle kapanış marjsız olasılığı × alınan oran − 1.", "",
          "| EV eşiği | Maks. oran | Bahis | ROI (%95 GA) | Adil CLV (%95 GA) |", "|---|---|---|---|---|"]
    for row in rows_out:
        roi, c = row["roi"], row["fair_clv"]
        md.append(f"| {row['min_ev']:.1%} | {row['max_odds']:.1f} | {row['n']} | {roi[0]:+.2%} ({roi[1]:+.2%} – {roi[2]:+.2%}) | "
                  f"{c[0]:+.2%} ({c[1]:+.2%} – {c[2]:+.2%}) |")
    md += ["", "Not: en iyi yumuşak oran birden çok büronun en iyisidir; tek bir büroda (ör. Nesine) bu oranlar bulunmayabilir. "
           "Kazanan hesapların kısıtlanması riski vardır (Kaunitz ve ark. 2017)."]
    _save("sharp_soft", {"rows": rows_out, "ll_open": ll_open, "ll_close": ll_close, "n_matches": int(len(df))}, md)




# ----------------------------------------------------------------------------------------------
DERIV_MARKETS = ("KG Var", "1.5 Üst", "3.5 Üst", "İY 0.5 Üst", "İY 1.5 Üst", "İY 1", "İY 0", "İY 2",
                 "Ev 0.5 Üst", "Dep 0.5 Üst", "İY/MS 1/1", "İY/MS 0/0", "İY/MS 2/2", "İY/MS 0/1",
                 "Skor 0-0", "Skor 1-1", "Skor 1-0", "Tek", "En Çok Gol 2Y")


def _price_row(row: tuple) -> list[float] | None:
    from quantfoot.markets.goal_markets import goal_probability
    from quantfoot.markets.omni_markets import compute_omni_markets
    from quantfoot.markets.tail_goals import fit_tail_rates_from_markets, league_tail_regime
    from quantfoot.markets.devig import devig

    div, oh, od, oa, ov, un = row
    try:
        p1x2 = devig([oh, od, oa], method="power").probabilities
        p_ov = float(devig([ov, un], method="power").probabilities[0])
        nu, alpha, kappa = league_tail_regime(div.lower())
        mu_h, mu_a, _ = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15),
                                                    alpha_nb=alpha, shared_kappa=kappa, com_nu=nu, fund_weight=0.0)
        joint = compute_omni_markets(mu_h, mu_a, league=div.lower()).joint
        return [goal_probability(m, joint) for m in DERIV_MARKETS]
    except Exception:
        return None


def cmd_derivative(args: argparse.Namespace) -> None:
    """Calibration of derivative markets priced from the Bet365 1X2 + O/U 2.5 anchor."""
    from concurrent.futures import ProcessPoolExecutor

    from quantfoot.evaluation.settlement import settle_selection

    cols = ["Division", "MatchDate", "OddHome", "OddDraw", "OddAway", "Over25", "Under25", "HTHome", "HTAway", "FTHome", "FTAway"]
    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"], usecols=cols).dropna()
    df = df[(df[["OddHome", "OddDraw", "OddAway", "Over25", "Under25"]] > 1.0).all(axis=1)]
    base = df[(df.MatchDate >= "2016-07-01") & (df.MatchDate < args.test_from)]
    test = df[df.MatchDate >= args.test_from].sample(n=min(args.n, (df.MatchDate >= args.test_from).sum()), random_state=3)
    rows = list(test[["Division", "OddHome", "OddDraw", "OddAway", "Over25", "Under25"]].itertuples(index=False, name=None))
    with ProcessPoolExecutor() as pool:
        preds = list(pool.map(_price_row, rows, chunksize=200))
    keep = [i for i, p in enumerate(preds) if p is not None]
    P = np.array([preds[i] for i in keep])
    t = test.iloc[keep]

    def _outcomes(frame: pd.DataFrame) -> np.ndarray:
        return np.array([[settle_selection(m, (int(r.HTHome), int(r.HTAway)), (int(r.FTHome), int(r.FTAway))) for m in DERIV_MARKETS]
                         for r in frame.itertuples(index=False)], dtype=float)

    Y = _outcomes(t)
    base_rate = _outcomes(base.sample(n=min(20000, len(base)), random_state=5)).mean(axis=0)
    md = ["# Türev pazarların kalibrasyonu (Bet365 1X2 + 2.5 Alt/Üst'e sabitlenmiş motor)", "",
          f"Test: {len(t)} rastgele maç, {args.test_from} sonrası, 22 lig. Her maçta gol beklentisi Bet365 marjsız 1X2 ve 2.5 "
          "Alt/Üst olasılığına uydurulur (fund_weight=0), sonra ortak gol tensöründen türev olasılıklar hesaplanır.", "",
          "Ölçütler: ECE = 10 kovalı beklenen kalibrasyon hatası; log-loss, 2016–test öncesi sabit taban oranıyla karşılaştırılır.", "",
          "| Pazar | Ort. tahmin | Gerçekleşen | ECE | Log-loss motor | Log-loss taban oran | Kazanç |", "|---|---|---|---|---|---|---|"]
    out = []
    for j, m in enumerate(DERIV_MARKETS):
        p = np.clip(P[:, j], 1e-6, 1 - 1e-6)
        y = Y[:, j]
        bins = np.minimum((p * 10).astype(int), 9)
        ece = float(sum(abs(p[bins == b].mean() - y[bins == b].mean()) * (bins == b).mean() for b in range(10) if (bins == b).any()))
        ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        b0 = float(np.clip(base_rate[j], 1e-6, 1 - 1e-6))
        ll0 = float(-np.mean(y * np.log(b0) + (1 - y) * np.log(1 - b0)))
        out.append({"market": m, "mean_pred": float(p.mean()), "observed": float(y.mean()), "ece": ece, "ll": ll, "ll_base": ll0})
        md.append(f"| {m} | %{p.mean() * 100:.1f} | %{y.mean() * 100:.1f} | {ece:.4f} | {ll:.5f} | {ll0:.5f} | {ll0 - ll:+.5f} |")
    md += ["", "Yorum: ECE küçük ve ortalama tahmin ≈ gerçekleşen ise motor, keskin bir 1X2 + Alt/Üst fiyatından türev pazarlar için "
           "güvenilir adil fiyat üretir; yumuşak büronun türev oranları bu adil fiyatlarla karşılaştırılabilir."]
    _save("derivative_calibration", {"n": len(t), "markets": out}, md)




# ----------------------------------------------------------------------------------------------
FT_MARKETS = ("KG Var", "1.5 Üst", "3.5 Üst", "4.5 Üst", "Ev 0.5 Üst", "Dep 0.5 Üst", "Skor 0-0", "Skor 1-1", "Skor 1-0", "Skor 0-1")


def _ft_probs(task: tuple) -> list[float] | None:
    from quantfoot.markets.devig import devig
    from quantfoot.markets.tail_goals import fit_tail_rates_from_markets

    (oh, od, oa, ov, un), (nu, rho, kappa) = task
    try:
        p1x2 = devig([oh, od, oa], method="power").probabilities
        p_ov = float(devig([ov, un], method="power").probabilities[0])
        _, _, mat = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15), alpha_nb=0.0,
                                                rho=rho, shared_kappa=kappa, com_nu=nu, fund_weight=0.0)
    except Exception:
        return None
    mat = mat / mat.sum()
    h, a = np.indices(mat.shape)
    t = h + a
    return [float(mat[(h > 0) & (a > 0)].sum()), float(mat[t > 1.5].sum()), float(mat[t > 3.5].sum()), float(mat[t > 4.5].sum()),
            float(mat[h > 0].sum()), float(mat[a > 0].sum()), float(mat[0, 0]), float(mat[1, 1]), float(mat[1, 0]), float(mat[0, 1])]


def _ft_outcomes(frame: pd.DataFrame) -> np.ndarray:
    h, a = frame.FTHome.to_numpy(int), frame.FTAway.to_numpy(int)
    t = h + a
    return np.column_stack([(h > 0) & (a > 0), t > 1.5, t > 3.5, t > 4.5, h > 0, a > 0,
                            (h == 0) & (a == 0), (h == 1) & (a == 1), (h == 1) & (a == 0), (h == 0) & (a == 1)]).astype(float)


def _ll_table(P: np.ndarray, Y: np.ndarray) -> np.ndarray:
    P = np.clip(P, 1e-6, 1 - 1e-6)
    return -(Y * np.log(P) + (1 - Y) * np.log(1 - P)).mean(axis=0)


def cmd_calibrate_regime(args: argparse.Namespace) -> None:
    """Grid-search (COM-Poisson nu, Dixon-Coles rho, shared tempo kappa) on market-anchored FT derivative markets."""
    from concurrent.futures import ProcessPoolExecutor
    from itertools import product

    cols = ["Division", "MatchDate", "OddHome", "OddDraw", "OddAway", "Over25", "Under25", "FTHome", "FTAway"]
    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"], usecols=cols).dropna()
    df = df[(df[["OddHome", "OddDraw", "OddAway", "Over25", "Under25"]] > 1.0).all(axis=1)]
    cal = df[(df.MatchDate >= "2019-07-01") & (df.MatchDate < args.test_from)].sample(n=args.n_cal, random_state=11)
    test = df[df.MatchDate >= args.test_from].sample(n=args.n_test, random_state=12)
    odds_cols = ["OddHome", "OddDraw", "OddAway", "Over25", "Under25"]
    grid = list(product((0.95, 1.0, 1.05, 1.10), (-0.07, -0.03, 0.0, 0.03), (0.0, 0.05, 0.10)))

    def _eval(frame: pd.DataFrame, params: tuple) -> tuple[np.ndarray, np.ndarray]:
        tasks = [(tuple(r), params) for r in frame[odds_cols].itertuples(index=False, name=None)]
        with ProcessPoolExecutor() as pool:
            preds = list(pool.map(_ft_probs, tasks, chunksize=100))
        keep = [i for i, p in enumerate(preds) if p is not None]
        return np.array([preds[i] for i in keep]), _ft_outcomes(frame.iloc[keep])

    scores = []
    for params in grid:
        P, Y = _eval(cal, params)
        ll = _ll_table(P, Y)
        scores.append((float(ll.sum()), params, ll))
        print(f"nu={params[0]:.2f} rho={params[1]:+.2f} kappa={params[2]:.2f}: toplam log-loss {ll.sum():.5f}")
    scores.sort(key=lambda x: x[0])
    best = scores[0][1]
    current = (1.10, -0.07, 0.0)
    P_cur, Y_t = _eval(test, current)
    P_best, Y_b = _eval(test, best)
    ll_cur, ll_best = _ll_table(P_cur, Y_t), _ll_table(P_best, Y_b)
    md = ["# Gol dağılımı rejiminin yeniden kalibrasyonu (piyasaya sabitlenmiş maç sonu türev pazarlar)", "",
          f"Kalibrasyon: {args.n_cal} maç (2019-07 – {args.test_from}); test: {args.n_test} maç ({args.test_from}+). "
          "Her maçta gol beklentisi Bet365 marjsız 1X2 + 2.5 Alt/Üst'e uydurulur; parametreler yalnızca kalibrasyon döneminde seçilir.", "",
          f"- Mevcut kulüp rejimi: ν={current[0]}, ρ={current[1]}, κ={current[2]}",
          f"- Kalibrasyonda en iyi: **ν={best[0]}, ρ={best[1]}, κ={best[2]}**", "",
          "| Pazar | Gerçekleşen (test) | Mevcut tahmin | Yeni tahmin | Log-loss mevcut | Log-loss yeni |", "|---|---|---|---|---|---|"]
    for j, m in enumerate(FT_MARKETS):
        md.append(f"| {m} | %{Y_t[:, j].mean() * 100:.1f} | %{P_cur[:, j].mean() * 100:.1f} | %{P_best[:, j].mean() * 100:.1f} | "
                  f"{ll_cur[j]:.5f} | {ll_best[j]:.5f} |")
    md += ["", f"Toplam test log-loss: mevcut {ll_cur.sum():.5f} → yeni {ll_best.sum():.5f} ({ll_best.sum() - ll_cur.sum():+.5f}).", "",
           "## Kalibrasyon ızgarası (ilk 10)", "", "| ν | ρ | κ | toplam log-loss |", "|---|---|---|---|"]
    md += [f"| {p[0]} | {p[1]:+.2f} | {p[2]} | {s:.5f} |" for s, p, _ in scores[:10]]
    _save("regime_calibration", {"best": best, "current": current, "test_ll_current": ll_cur.tolist(), "test_ll_best": ll_best.tolist(),
                                 "grid": [(s, p) for s, p, _ in scores]}, md)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cache").set_defaults(func=cmd_cache)
    sub.add_parser("pool").set_defaults(func=cmd_pool)
    p = sub.add_parser("rest")
    p.add_argument("--test-from", default="2021-07-01")
    p.set_defaults(func=cmd_rest)
    sub.add_parser("sharp-soft").set_defaults(func=cmd_sharp_soft)
    p = sub.add_parser("derivative")
    p.add_argument("--test-from", default="2022-07-01")
    p.add_argument("--n", type=int, default=12000)
    p.set_defaults(func=cmd_derivative)
    p = sub.add_parser("calibrate-regime")
    p.add_argument("--test-from", default="2022-07-01")
    p.add_argument("--n-cal", type=int, default=2500)
    p.add_argument("--n-test", type=int, default=6000)
    p.set_defaults(func=cmd_calibrate_regime)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
