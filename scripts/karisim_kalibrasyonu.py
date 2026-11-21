"""Model ↔ keskin piyasa karışım ağırlığı (aile aile), walk-forward, arşivde (data/matches.csv + pazar önbelleği).

    python scripts/karisim_kalibrasyonu.py            # rapor + data/calibration/blend_weights.json

Soru: kupon olasılığı P = karışım(model, piyasa) olsun; modelin ağırlığı w her pazar ailesinde ne olmalı?

* Piyasa P'si: ``reports/research/backtest_cache_pazar_kalibrasyonu.csv.gz`` (kupon hattıyla marjsız 1X2 + 2.5 A/Ü →
  gol tensörü: MS 1/X/2, 2.5 Üst, 3.5 Üst, KG Var). Arşiv oranı ortalama büro (Bet365 tipi), Pinnacle kapanışı değil.
* Model P'si (piyasa görmeyen): sonuçlardan kronolojik Elo (1X2, sıralı lojit) + takım hücum/savunma gol oranları
  (Poisson → 2.5/3.5 Üst, KG). Her maç yalnız ÖNCEKİ maçlarla.
* Karışım: logit P = a + b·[(1−w)·logit(piyasa) + w·logit(model)] (w ∈ [0, 1], Platt a, b). Her test sezonu
  (Temmuz–Haziran, 2016+) için yalnız önceki sezonlarla kurulur (sızıntı yok).
* Karar: bir ailede w yalnız test log-loss farkının (karışım − ham piyasa) %95 bootstrap güven aralığının ÜST ucu < 0
  ise tutulur; aksi halde w = 0 (piyasaya yaslan). Ayrıca saf Platt (w = 0) da aynı kuralla sınanır.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "reports" / "research" / "backtest_cache_pazar_kalibrasyonu.csv.gz"
MATCHES = ROOT / "data" / "matches.csv"
OUT_JSON = ROOT / "data" / "calibration" / "blend_weights.json"
OUT_MD = ROOT / "reports" / "research" / "karisim_kalibrasyonu.md"
FIRST_TEST = 2016
EPS = 1e-6
FAMILIES = {  # aile → (piyasa sütunu, model sütunu, hedef)
    "ms1": ("p_h", "m_h", "y_h"),
    "msx": ("p_d", "m_d", "y_d"),
    "ms2": ("p_a", "m_a", "y_a"),
    "ust25": ("p_o25", "m_o25", "y_o25"),
    "ust35": ("p_o35", "m_o35", "y_o35"),
    "kg_var": ("p_btts", "m_btts", "y_btts"),
}
BANDS = (0.0, 0.2, 0.3, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9, 1.0)


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def season(date: pd.Series) -> pd.Series:
    d = pd.to_datetime(date)
    return np.where(d.dt.month >= 7, d.dt.year + 1, d.dt.year)   # 2016 = 2015/16


# ------------------------------------------------------------------------------- piyasa görmeyen model

def model_features(m: pd.DataFrame) -> pd.DataFrame:
    """Kronolojik Elo + üstel ağırlıklı takım gol oranları; her satır yalnız önceki maçlardan."""
    m = m.sort_values(["MatchDate"], kind="stable").reset_index(drop=True)
    elo: dict = defaultdict(lambda: 1500.0)
    gf: dict = defaultdict(lambda: None)   # takım → [hücum (atılan ort.), savunma (yenen ort.), n]
    lg: dict = defaultdict(lambda: [1.45, 1.15])   # lig → [ev ort., dep ort.]
    K, HFA, A = 20.0, 60.0, 0.06
    out = np.full((len(m), 4), np.nan)
    hs, as_ = m["FTHome"].to_numpy(), m["FTAway"].to_numpy()
    for i, (div, h, a) in enumerate(zip(m["Division"], m["HomeTeam"], m["AwayTeam"])):
        kh, ka = (div, h), (div, a)
        out[i, 0] = elo[kh] - elo[ka] + HFA
        th, ta, L = gf[kh], gf[ka], lg[div]
        if th and ta and th[2] >= 6 and ta[2] >= 6:
            out[i, 1] = L[0] * (th[0] / ((L[0] + L[1]) / 2)) * (ta[1] / ((L[0] + L[1]) / 2))
            out[i, 2] = L[1] * (ta[0] / ((L[0] + L[1]) / 2)) * (th[1] / ((L[0] + L[1]) / 2))
        out[i, 3] = 0 if not (th and ta) else min(th[2], ta[2])
        x, y = hs[i], as_[i]
        if np.isnan(x) or np.isnan(y):
            continue
        e = 1 / (1 + 10 ** (-(out[i, 0]) / 400))
        s = 1.0 if x > y else 0.5 if x == y else 0.0
        mult = math.log(abs(x - y) + 1) + 1 if x != y else 1.0
        elo[kh] += K * mult * (s - e)
        elo[ka] -= K * mult * (s - e)
        for key, f, ag in ((kh, x, y), (ka, y, x)):
            t = gf[key]
            gf[key] = [f, ag, 1] if t is None else [(1 - A) * t[0] + A * f, (1 - A) * t[1] + A * ag, t[2] + 1]
        L[0], L[1] = 0.995 * L[0] + 0.005 * x, 0.995 * L[1] + 0.005 * y
    m["elo_d"], m["mu_h_m"], m["mu_a_m"], m["n_hist"] = out[:, 0], out[:, 1], out[:, 2], out[:, 3]
    return m


def goal_probs(mu_h: np.ndarray, mu_a: np.ndarray) -> dict[str, np.ndarray]:
    g = np.arange(11)
    ph = poisson.pmf(g[None, :], mu_h[:, None])
    pa = poisson.pmf(g[None, :], mu_a[:, None])
    joint = ph[:, :, None] * pa[:, None, :]
    tot = g[:, None] + g[None, :]
    return {"m_o25": (joint * (tot >= 3)).sum((1, 2)), "m_o35": (joint * (tot >= 4)).sum((1, 2)),
            "m_btts": (1 - ph[:, 0]) * (1 - pa[:, 0])}


def fit_ordinal(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Sıralı lojit (A < D < H) elo farkıyla: P(sonuç ≤ k) = σ(c_k − βx)."""
    def nll(th):
        b, c1, c2 = th[0], th[1], th[1] + math.exp(th[2])
        pa_ = 1 / (1 + np.exp(-(c1 - b * x)))
        pad = 1 / (1 + np.exp(-(c2 - b * x)))
        p = np.where(y == 0, pa_, np.where(y == 1, pad - pa_, 1 - pad))
        return -np.log(np.clip(p, EPS, 1)).sum()
    return minimize(nll, [0.004, -0.6, math.log(1.1)], method="Nelder-Mead", options={"maxiter": 2000}).x


def ordinal_probs(th: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    b, c1, c2 = th[0], th[1], th[1] + math.exp(th[2])
    pa_ = 1 / (1 + np.exp(-(c1 - b * x)))
    pad = 1 / (1 + np.exp(-(c2 - b * x)))
    return 1 - pad, pad - pa_, pa_


# ------------------------------------------------------------------------------- karışım ve metrikler

def _sig(t: float) -> float:
    return 1 / (1 + math.exp(-min(max(float(t), -30.0), 30.0)))


def fit_blend(lm: np.ndarray, lmod: np.ndarray, y: np.ndarray, free_w: bool = True) -> tuple[float, float, float]:
    """(w, a, b): logit P = a + b·((1−w)·lm + w·lmod). free_w=False → w = 0 (saf Platt)."""
    def nll(th):
        w = _sig(th[2]) if free_w else 0.0
        z = th[0] + th[1] * ((1 - w) * lm + w * lmod)
        return np.sum(np.logaddexp(0, z) - y * z)
    r = minimize(nll, [0.0, 1.0, -3.0 if free_w else 0.0], method="Nelder-Mead", options={"maxiter": 3000, "xatol": 1e-6, "fatol": 1e-6})
    w = _sig(r.x[2]) if free_w else 0.0
    return w, float(r.x[0]), float(r.x[1])


def apply_blend(lm, lmod, w, a, b):
    return 1 / (1 + np.exp(-(a + b * ((1 - w) * lm + w * lmod))))


def metrics(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.clip(p, EPS, 1 - EPS)
    ll = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    idx = np.digitize(p, BANDS[1:-1])
    ece = sum(abs(p[idx == k].mean() - y[idx == k].mean()) * (idx == k).sum() for k in np.unique(idx)) / len(p)
    return {"n": int(len(p)), "mean_p": float(p.mean()), "hit": float(y.mean()), "logloss": float(ll.mean()),
            "brier": float(((p - y) ** 2).mean()), "ece": float(ece)}


def boot_ci(d: np.ndarray, n_boot: int = 1000, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n_boot)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def buckets(p: np.ndarray, y: np.ndarray) -> list[tuple[str, int, float, float]]:
    idx = np.digitize(p, BANDS[1:-1])
    rows = []
    for k in range(len(BANDS) - 1):
        sel = idx == k
        if sel.sum() >= 30:
            rows.append((f"{BANDS[k]:.2f}–{BANDS[k + 1]:.2f}", int(sel.sum()), float(p[sel].mean()), float(y[sel].mean())))
    return rows


def build_frame() -> pd.DataFrame:
    c = pd.read_csv(CACHE)
    m = pd.read_csv(MATCHES, usecols=["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway"])
    m = model_features(m.dropna(subset=["FTHome", "FTAway"]))
    df = c.merge(m[["Division", "MatchDate", "HomeTeam", "AwayTeam", "elo_d", "mu_h_m", "mu_a_m", "n_hist"]],
                 on=["Division", "MatchDate", "HomeTeam", "AwayTeam"], how="inner")
    df = df.dropna(subset=["p_h", "p_d", "p_a", "p_o25", "p_o35", "p_btts", "mu_h_m", "mu_a_m"])
    df["season"] = season(df["MatchDate"])
    hg, ag = df["FTHome"].to_numpy(), df["FTAway"].to_numpy()
    df["y_h"], df["y_d"], df["y_a"] = (hg > ag) * 1.0, (hg == ag) * 1.0, (hg < ag) * 1.0
    df["y_o25"], df["y_o35"], df["y_btts"] = (hg + ag >= 3) * 1.0, (hg + ag >= 4) * 1.0, ((hg > 0) & (ag > 0)) * 1.0
    df["y_ord"] = np.where(hg > ag, 2, np.where(hg == ag, 1, 0))
    gp = goal_probs(np.clip(df["mu_h_m"].to_numpy(), 0.2, 5), np.clip(df["mu_a_m"].to_numpy(), 0.2, 5))
    for k, v in gp.items():
        df[k] = v
    return df.reset_index(drop=True)


def main() -> None:
    df = build_frame()
    seasons = sorted(s for s in df["season"].unique() if s >= FIRST_TEST)
    # 1X2 modeli: her test sezonu için önceki sezonlarla sıralı lojit
    df["m_h"] = df["m_d"] = df["m_a"] = np.nan
    for s in seasons:
        tr, te = df["season"] < s, df["season"] == s
        th = fit_ordinal(df.loc[tr, "elo_d"].to_numpy(), df.loc[tr, "y_ord"].to_numpy())
        ph, pd_, pa = ordinal_probs(th, df.loc[te, "elo_d"].to_numpy())
        df.loc[te, "m_h"], df.loc[te, "m_d"], df.loc[te, "m_a"] = ph, pd_, pa
    first_tr = df["season"] < FIRST_TEST
    th0 = fit_ordinal(df.loc[first_tr, "elo_d"].to_numpy(), df.loc[first_tr, "y_ord"].to_numpy())
    df.loc[first_tr, "m_h"], df.loc[first_tr, "m_d"], df.loc[first_tr, "m_a"] = ordinal_probs(th0, df.loc[first_tr, "elo_d"].to_numpy())

    result: dict = {"method": __doc__.split("\n")[0], "n_matches": int(len(df)),
                    "span": [str(df["MatchDate"].min()), str(df["MatchDate"].max())], "first_test_season": FIRST_TEST,
                    "families": {}}
    md = ["# Model ↔ piyasa karışım kalibrasyonu (walk-forward)", "",
          f"Veri: {len(df)} maç ({df['MatchDate'].min()} – {df['MatchDate'].max()}), test sezonları {FIRST_TEST}+ "
          "(her sezon yalnız önceki sezonlarla kuruldu). Piyasa = arşivdeki ortalama büro oranından marjsız kupon hattı; "
          "model = piyasa görmeyen Elo + takım gol oranları.", ""]
    md += ["| Aile | n (test) | LL piyasa | LL model | LL Platt | LL karışım | Brier piyasa | Brier karışım | ECE piyasa | ECE karışım | w (son) | Karar |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    bucket_md = []
    for fam, (pc, mc, yc) in FAMILIES.items():
        p_raw, p_mod, p_pl, p_bl, ys, ws = [], [], [], [], [], []
        for s in seasons:
            tr, te = df["season"] < s, df["season"] == s
            lm_tr, lmod_tr, y_tr = logit(df.loc[tr, pc].to_numpy()), logit(df.loc[tr, mc].to_numpy()), df.loc[tr, yc].to_numpy()
            w, a, b = fit_blend(lm_tr, lmod_tr, y_tr, True)
            _, a0, b0 = fit_blend(lm_tr, lmod_tr, y_tr, False)
            _, am, bm = fit_blend(lmod_tr, lm_tr, y_tr, False)   # model tek başına (Platt'lı)
            lm, lmod, y = logit(df.loc[te, pc].to_numpy()), logit(df.loc[te, mc].to_numpy()), df.loc[te, yc].to_numpy()
            p_raw.append(df.loc[te, pc].to_numpy())
            p_bl.append(apply_blend(lm, lmod, w, a, b))
            p_pl.append(apply_blend(lm, lmod, 0.0, a0, b0))
            p_mod.append(apply_blend(lmod, lm, 0.0, am, bm))
            ys.append(y)
            ws.append(w)
        p_raw, p_mod, p_pl, p_bl, y = map(np.concatenate, (p_raw, p_mod, p_pl, p_bl, ys))
        M = {k: metrics(v, y) for k, v in (("piyasa", p_raw), ("model", p_mod), ("platt", p_pl), ("karisim", p_bl))}

        def ll_vec(p):
            p = np.clip(p, EPS, 1 - EPS)
            return -(y * np.log(p) + (1 - y) * np.log(1 - p))
        d_bl = ll_vec(p_bl) - ll_vec(p_raw)
        d_pl = ll_vec(p_pl) - ll_vec(p_raw)
        ci_bl, ci_pl = boot_ci(d_bl), boot_ci(d_pl)
        all_tr = df["season"] <= max(seasons)
        w_f, a_f, b_f = fit_blend(logit(df.loc[all_tr, pc].to_numpy()), logit(df.loc[all_tr, mc].to_numpy()), df.loc[all_tr, yc].to_numpy(), True)
        _, a_p, b_p = fit_blend(logit(df.loc[all_tr, pc].to_numpy()), logit(df.loc[all_tr, mc].to_numpy()), df.loc[all_tr, yc].to_numpy(), False)
        keep_blend = ci_bl[1] < 0 and ci_bl[1] < ci_pl[1]
        keep_platt = (not keep_blend) and ci_pl[1] < 0
        decision = "karışım" if keep_blend else ("yalnız Platt (w=0)" if keep_platt else "ham piyasa (w=0)")
        entry = {"w": round(w_f, 4) if keep_blend else 0.0, "a": round(a_f if keep_blend else (a_p if keep_platt else 0.0), 5),
                 "b": round(b_f if keep_blend else (b_p if keep_platt else 1.0), 5), "decision": decision,
                 "w_fitted": round(w_f, 4), "w_by_season": [round(x, 4) for x in ws],
                 "test": M, "dll_blend_vs_market": float(d_bl.mean()), "ci95_blend": ci_bl,
                 "dll_platt_vs_market": float(d_pl.mean()), "ci95_platt": ci_pl}
        result["families"][fam] = entry
        md.append(f"| {fam} | {M['piyasa']['n']} | {M['piyasa']['logloss']:.5f} | {M['model']['logloss']:.5f} | {M['platt']['logloss']:.5f} | "
                  f"{M['karisim']['logloss']:.5f} | {M['piyasa']['brier']:.5f} | {M['karisim']['brier']:.5f} | {M['piyasa']['ece']:.4f} | "
                  f"{M['karisim']['ece']:.4f} | {w_f:.3f} | {decision} |")
        bucket_md += [f"### {fam}", "", "| Bant | n | Piyasa tahmini | Gerçekleşen | Karışım tahmini | Gerçekleşen |", "|---|---|---|---|---|---|"]
        b1, b2 = {r[0]: r for r in buckets(p_raw, y)}, {r[0]: r for r in buckets(p_bl, y)}
        for k in sorted(set(b1) | set(b2)):
            r1, r2 = b1.get(k), b2.get(k)
            bucket_md.append(f"| {k} | {(r1 or r2)[1]} | " + (f"%{100 * r1[2]:.1f} | %{100 * r1[3]:.1f}" if r1 else "- | -") + " | "
                             + (f"%{100 * r2[2]:.1f} | %{100 * r2[3]:.1f}" if r2 else "- | -") + " |")
        bucket_md.append("")
        print(f"{fam:7} LL piyasa {M['piyasa']['logloss']:.5f} model {M['model']['logloss']:.5f} platt {M['platt']['logloss']:.5f} "
              f"karışım {M['karisim']['logloss']:.5f} w={w_f:.3f} CI{tuple(round(x, 6) for x in ci_bl)} → {decision}")
    md += ["", "Karar kuralı: karışım yalnız test log-loss farkının %95 güven aralığı tamamen sıfırın altındaysa tutulur; "
           "aksi halde w = 0 — olasılık keskin/marjsız piyasadan gelir.", "",
           "Sınır: arşiv oranı ortalama büro (Bet365 tipi), Pinnacle kapanışı değil; gerçek keskin fiyata karşı modelin "
           "katkısı bundan da küçük olmalı. Canlı model için arşiv yok (21 Kasım'da yalnız 3 canlı bacak) — canlı karışım "
           "w = 0.5 tavanında kalır, banko koruması canlı P'yi piyasanın en çok +5 puan üstünde sınırlar.", "",
           "## Güvenilirlik bantları (test sezonları)", ""] + bucket_md
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"-> {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
