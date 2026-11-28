#!/usr/bin/env python3
"""İY/MS ve 2Y KG Var araştırması: profil, kalibrasyon, kupon simülasyonu, Nesine fiyat kıyası, model iyileştirme testleri.

Sızıntısız: olasılıklar `yuksek_oran_backtest` ileri-yürüyen hattından (aylık yalnız geçmiş kalibrasyonu); test 2024-07-01 sonrası.
Arşivde İY/MS ve 2Y KG oranı yok → ROI "sentetik Nesine oranı" iledir (bkz. quantfoot.evaluation.kupon_simulasyon).

    python scripts/iyms_2ykg_arastirma.py --cache /workspace/yo_cache/feat_240.pkl [--nesine tahminler/.../nesine_global.json] [--model-testleri]
Çıktı: reports/research/iyms_2ykg_arastirma_<tarih>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation import yuksek_oran_backtest as bt  # noqa: E402
from quantfoot.evaluation.kupon_simulasyon import payout_curve, simulate_coupons, wilson  # noqa: E402
from quantfoot.markets import yuksek_oran_modeli as ym  # noqa: E402

L = ["1/1", "1/X", "1/2", "X/1", "X/X", "X/2", "2/1", "2/X", "2/2"]
CFG = bt.ProbConfig(w_market=1.0, gamma_team=0.0, rho_iy=0.0, rho_2y=0.0, rho_ms=0.0)
TEST_FROM = "2024-07-01"


def load_oos(cache: str | None) -> tuple[pd.DataFrame, dict, dict]:
    if cache and Path(cache).exists():
        f = pd.read_pickle(cache)
    else:
        f = bt.add_market_lambdas(bt.build_features(bt.load_matches(), bt.FeatureConfig(half_life=240.0)))
    f = f[f.lam_p.notna() | f.lam_m.notna()].reset_index(drop=True)
    y = bt.outcomes(f)
    mh, ma, _ = bt.game_state_multipliers(f, CFG)
    raw = bt.raw_probs(f, CFG, "sonra", (mh, ma), ft_from_halves=True)
    cal, _ = bt.walk_forward_calibrate(f, raw, y, "2019-07-01")
    for c in range(9):
        f[f"h{c}"] = cal["htft"][:, c]
    f["kg2"], f["y_htft"], f["y_kg2"], f["ht_ok"] = cal["kg2"], y["htft"], y["kg2"], y["ht_ok"]
    f["ptot"] = f.lam_p + f.mu_p
    f["pfav"] = f[["p1", "p2"]].max(axis=1)
    return f, raw, y


def _band(df, pcol, ycol, edges):
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        s = (df[pcol] >= lo) & (df[pcol] < hi)
        n = int(s.sum())
        if n < 30:
            continue
        k = int(df.loc[s, ycol].sum())
        ga = wilson(k, n)
        rows.append({"bant": f"{lo:.2f}-{min(hi, 1):.2f}", "n": n, "tahmin": round(float(df.loc[s, pcol].mean()), 4),
                     "gercek": round(k / n, 4), "ga": [round(ga[0], 4), round(ga[1], 4)]})
    return rows


def analyses(f: pd.DataFrame, nesine: str | None) -> dict:
    ok = f.ht_ok & f.lam_m.notna() & f.lam_p.notna()
    T = f[ok & (f.MatchDate >= TEST_FROM)].copy().reset_index(drop=True)
    H = T[[f"h{c}" for c in range(9)]].to_numpy()
    T["top"], T["ptop"] = H.argmax(1), H.max(1)
    T["hit"] = (T.top == T.y_htft).astype(int)
    T["yes"], T["no"], T["pn"] = T.y_kg2, 1 - T.y_kg2, 1 - T.kg2
    out: dict = {"n_test": int(len(T)), "test_from": TEST_FROM}
    out["iyms_en_olasi_hucre_bant"] = _band(T, "ptop", "hit", [0, .2, .25, .3, .35, .4, .45, .5, .55, .6, 1.01])
    out["iyms_hucre_max_p"] = {L[c]: round(float(T[f"h{c}"].max()), 3) for c in range(9)}
    T["fb"] = pd.cut(T.pfav, [0, .45, .55, .65, .75, 1])
    out["iyms_favori_gucu_x_hucre"] = [
        {"favori_p": str(k[0]), "hucre": L[int(k[1])], "n": int(len(g)), "tahmin": round(float(g.ptop.mean()), 4),
         "gercek": round(float(g.hit.mean()), 4)} for k, g in T[T.top.isin([0, 8])].groupby(["fb", "top"], observed=True)]
    A = f[ok & (f.MatchDate >= "2021-07-01")].copy()
    A["sez"] = np.where(A.MatchDate.dt.month >= 7, A.MatchDate.dt.year, A.MatchDate.dt.year - 1)
    out["iyms_11_p45_sezon"] = [{"sezon": int(s), "n": int(len(g)), "tahmin": round(float(g.h0.mean()), 4),
                                 "gercek": round(float((g.y_htft == 0).mean()), 4)} for s, g in A[A.h0 >= .45].groupby("sez")]
    S = T[T.ptop >= .45]
    out["iyms_p45_lig"] = [{"lig": d, "n": int(len(g)), "tahmin": round(float(g.ptop.mean()), 3), "gercek": round(float(g.hit.mean()), 3)}
                           for d, g in S.groupby("Division") if len(g) >= 25]
    out["kg2var_bant"] = _band(T, "kg2", "yes", [0, .15, .2, .25, .3, .35, .4, 1])
    out["kg2yok_bant"] = _band(T, "pn", "no", [0, .6, .65, .7, .75, .8, .85, 1.01])
    out["kg2var_lig"] = [{"lig": d, "n": int(len(g)), "tahmin": round(float(g.kg2.mean()), 4), "gercek": round(float(g.yes.mean()), 4)}
                         for d, g in T.groupby("Division") if len(g) >= 300]
    T["tq"] = pd.qcut(T.ptot, 5)
    out["kg2var_toplam_gol_beşlik"] = [{"aralik": str(k), "n": int(len(g)), "tahmin": round(float(g.kg2.mean()), 4),
                                         "gercek": round(float(g.yes.mean()), 4)} for k, g in T.groupby("tq", observed=True)]
    # Nesine fiyat kıyası (bülten anlık görüntüsü)
    ratio_i = ratio_v = ratio_y = None
    if nesine and Path(nesine).exists():
        d = json.loads(Path(nesine).read_text(encoding="utf-8"))
        P = ym.load_params()
        rows, kg = [], []
        for m in d["matches"]:
            if not (m.get("mu_home") and m.get("mu_away")):
                continue
            o = ym.predict_markets(float(m["mu_home"]), float(m["mu_away"]), params=P)
            ss = {s["name"]: s["odds"] for s in m["offered_selections"]}
            for lab in ym.HTFT_LABELS:
                if f"İY/MS {lab}" in ss:
                    rows.append((m["code"], lab, o["İY/MS"][f"İY/MS {lab}"], ss[f"İY/MS {lab}"]))
            if "2Y KG Var" in ss and "2Y KG Yok" in ss:
                kg.append((m["code"], o["2Y KG"]["2Y KG Var"], ss["2Y KG Var"], ss["2Y KG Yok"]))
        R = pd.DataFrame(rows, columns=["kod", "hucre", "P", "oran"])
        R["ev"] = R.P * R.oran - 1
        R["imp"] = 1 / R.oran
        R["pb"] = pd.cut(R.P, [0, .03, .06, .1, .15, .2, .3, .4, .5, 1])
        gb = R.groupby("pb", observed=True).apply(lambda g: pd.Series({"n": len(g), "P": g.P.mean(), "oran": g.oran.mean(),
                                                                       "beklenen_getiri": g.ev.mean(), "carpan": (g.imp / g.P).mean()}))
        K = pd.DataFrame(kg, columns=["kod", "P", "oran_var", "oran_yok"])
        K["pn"] = 1 - K.P
        out["nesine_anlik"] = {
            "iyms_mac": int(R.kod.nunique()), "iyms_9hucre_toplam_1_oran": round(float(R.groupby("kod").imp.sum().mean()), 3),
            "iyms_p_kovasi": gb.round(4).reset_index(drop=True).assign(kova=[str(i) for i in gb.index]).to_dict("records"),
            "iyms_en_olasi_hucre_beklenen_getiri": round(float(R.loc[R.groupby("kod").P.idxmax()].ev.mean()), 3),
            "kg2_mac": int(len(K)), "kg2var_beklenen_getiri": round(float((K.P * K.oran_var - 1).mean()), 3),
            "kg2yok_beklenen_getiri": round(float((K.pn * K.oran_yok - 1).mean()), 3),
            "kg2yok_oran_medyan": round(float(K.oran_yok.median()), 2), "kg2yok_p75_ustu_oran_1_20_ustu": int(((K.pn >= .75) & (K.oran_yok >= 1.2)).sum()),
            "kg2yok_p75_ustu_mac": int((K.pn >= .75).sum()),
        }
        ratio_i = payout_curve(gb.P.to_numpy(), gb.carpan.to_numpy())
        ratio_v = float(((1 / K.oran_var) / K.P).mean())
        ratio_y = float(((1 / K.oran_yok) / K.pn).mean())
    # kupon simülasyonu
    if ratio_i is not None:
        sims: dict = {"iyms_tum": [], "iyms_yalniz_11": [], "iyms_yalniz_22": [], "kg2var": [], "kg2yok": []}
        for thr in (0, .35, .45, .5, .55):
            for k in range(1, 7):
                for nm, S in (("iyms_tum", T), ("iyms_yalniz_11", T[T.top == 0]), ("iyms_yalniz_22", T[T.top == 8])):
                    if nm != "iyms_tum" and thr == 0:
                        continue
                    r = simulate_coupons(S, "ptop", "hit", ratio_i, k, thr)
                    if r and r["n"] >= 20:
                        sims[nm].append(r)
        for thr in (0, .30, .33, .35):
            for k in range(1, 7):
                r = simulate_coupons(T, "kg2", "yes", lambda q: 1 / (np.asarray(q) * ratio_v), k, thr)
                if r and r["n"] >= 20:
                    sims["kg2var"].append(r)
        for thr in (0, .75, .78, .80, .82):
            for k in range(1, 7):
                r = simulate_coupons(T, "pn", "no", lambda q: 1 / (np.asarray(q) * ratio_y), k, thr)
                if r and r["n"] >= 20:
                    sims["kg2yok"].append(r)
        out["kupon_simulasyonu"] = sims
    cnt = {}
    for thr in (.45, .5, .55):
        c = T[T.ptop >= thr].groupby("MatchDate").size()
        cnt[str(thr)] = {"gun": int(T.MatchDate.nunique()), "en_az_1": int(len(c)), "en_az_3": int((c >= 3).sum()),
                         "en_az_5": int((c >= 5).sum()), "ort_bacak_gun": round(float(c.mean()), 2)}
    out["iyms_gunluk_bacak_sayisi"] = cnt
    return out


def model_tests(f: pd.DataFrame, raw: dict, y: dict) -> dict:
    """İki iyileştirme adayı: (1) İY/MS güçlü ev favorisi kovası, (2) 2Y KG lig ofseti. Ölçüt: OOS log-loss farkı %95 GA üst ucu < 0."""
    months = f.MatchDate.dt.to_period("M").to_numpy()
    ht_ok = y["ht_ok"]
    valid = np.isfinite(raw["htft"]).all(1)
    ph, pa = raw["htft"][:, [0, 3, 6]].sum(1), raw["htft"][:, [2, 5, 8]].sum(1)
    d = ph - pa
    both = (f.lam_m.notna() & f.lam_p.notna()).to_numpy()
    val = (f.MatchDate >= "2022-07-01").to_numpy() & (f.MatchDate < TEST_FROM).to_numpy() & both
    test = (f.MatchDate >= TEST_FROM).to_numpy() & both

    def wf(edges, prior=60.0):
        b = np.digitize(d, edges)
        out = raw["htft"].copy()
        for m in sorted(set(months)):
            if m < pd.Period("2019-07", "M"):
                continue
            cur, past = (months == m) & valid, (months < m) & valid & ht_ok
            if (months < m)[valid].sum() < 500:
                continue
            for k in range(len(edges) + 1):
                sel, c = past & (b == k), cur & (b == k)
                if c.any():
                    out[c] = ym.apply_cell_factors(raw["htft"][c], ym.cell_factors(raw["htft"][sel], y["htft"][sel], prior))
        return out

    def ll(p):
        return -np.log(np.clip(p[np.arange(len(p)), y["htft"]], 1e-9, 1))

    def cmp(l, base, mask):
        dd = (l - base)[mask & ht_ok]
        se = dd.std(ddof=1) / np.sqrt(len(dd))
        return {"n": int(len(dd)), "fark": round(float(dd.mean()), 5), "ga": [round(float(dd.mean() - 1.96 * se), 5), round(float(dd.mean() + 1.96 * se), 5)]}

    base = ll(wf([-.15, .15]))
    res: dict = {"iyms_kova": {}}
    for nm, e in {"ev-güçlü >0.45": [-.15, .15, .45], "ev-güçlü >0.35": [-.15, .15, .35], "ev .30/.50": [-.15, .15, .3, .5], "simetrik .45": [-.45, -.15, .15, .45]}.items():
        l = ll(wf(e))
        res["iyms_kova"][nm] = {"dogrulama": cmp(l, base, val), "test": cmp(l, base, test)}
    ok = (ht_ok & both & np.isfinite(f.kg2.to_numpy()))
    p, yy, div = f.kg2.to_numpy(), f.y_kg2.to_numpy(), f.Division.to_numpy()

    def lk(q):
        q = np.clip(q, 1e-6, 1 - 1e-6)
        return -(yy * np.log(q) + (1 - yy) * np.log(1 - q))

    b0 = lk(p)
    res["kg2_lig_ofset"] = {}
    for K in (100, 200, 400, 800):
        q = p.copy()
        for m in sorted(set(months[ok])):
            if m < pd.Period("2021-10", "M"):
                continue
            cur, past = ok & (months == m), ok & (months < m)
            for dv in np.unique(div[cur]):
                pm = past & (div == dv)
                if pm.any():
                    fac = (yy[pm].sum() + K * p[pm].mean()) / (p[pm].sum() + K * p[pm].mean())
                    c = cur & (div == dv)
                    q[c] = np.clip(p[c] * fac, 1e-4, 1 - 1e-4)
        l = lk(q)
        r = {}
        for nm, mk in (("dogrulama", val & ok), ("test", test & ok)):
            dd = (l - b0)[mk]
            se = dd.std(ddof=1) / np.sqrt(len(dd))
            r[nm] = {"n": int(len(dd)), "fark": round(float(dd.mean()), 5), "ga": [round(float(dd.mean() - 1.96 * se), 5), round(float(dd.mean() + 1.96 * se), 5)]}
        res["kg2_lig_ofset"][f"K={K}"] = r
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="")
    ap.add_argument("--nesine", default="")
    ap.add_argument("--model-testleri", action="store_true")
    ap.add_argument("--damga", default=str(pd.Timestamp.today().date()))
    a = ap.parse_args()
    f, raw, y = load_oos(a.cache or None)
    out = analyses(f, a.nesine or None)
    if a.model_testleri:
        out["model_testleri"] = model_tests(f, raw, y)
    dest = ROOT / "reports" / "research" / f"iyms_2ykg_arastirma_{a.damga}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("yazıldı:", dest)


if __name__ == "__main__":
    main()
