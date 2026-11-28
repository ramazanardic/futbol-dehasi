#!/usr/bin/env python3
"""'İki Yarıda KG Var' (iki yarıda da karşılıklı gol): model P, güvenilirlik, profil, kupon simülasyonu.

Nesine: '1. Yarı / 2. Yarı Karşılıklı Gol' pazarının 'İki Yarıda KG Var' seçimi. P = Σ_{İY skoru, iki takım da attı} P(İY skoru) · P(2Y KG | devre durumu),
`yuksek_oran_modeli.game_state_model` içinden (2Y KG ile aynı hat). Test 2024-07-01 sonrası, sızıntısız.

    python scripts/iki_yari_kg_arastirma.py --cache <feat_240.pkl> [--nesine .../nesine_global.json] [--damga 2026-11-28]
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
sys.path.insert(0, str(ROOT / "scripts"))

from iyms_2ykg_arastirma import CFG, TEST_FROM, _band, load_oos  # noqa: E402
from quantfoot.evaluation import yuksek_oran_backtest as bt  # noqa: E402
from quantfoot.evaluation.kupon_simulasyon import simulate_coupons  # noqa: E402
from quantfoot.markets import yuksek_oran_modeli as ym  # noqa: E402


def both_halves_prob(f: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(P iki yarıda KG, P İY KG) ham; aynı hat: harman λ + lig payı + devre durum çarpanları."""
    mh, ma, _ = bt.game_state_multipliers(f, CFG)
    lam, mu = bt.blended_lambdas(f, CFG)
    lam, mu = np.nan_to_num(lam, nan=1.4), np.nan_to_num(mu, nan=1.1)
    sh, sa = bt.half_shares(f, CFG)
    m1 = ym.dc_matrix(lam * sh, mu * sa, CFG.rho_iy)
    gs = ym.game_state_model(m1, lam * (1 - sh), mu * (1 - sa), mh, ma, CFG.rho_2y)
    return both_from_matrices(m1, gs)


def both_from_matrices(m1: np.ndarray, gs: dict) -> tuple[np.ndarray, np.ndarray]:
    """P(İY'de ve 2Y'de iki takım da atar) = Σ_durum P(İY KG ∧ durum) · P(2Y KG | durum)."""
    n = m1.shape[1] - 1
    masks = ym.half_state_masks(n)
    kg1 = np.zeros_like(m1)
    kg1[:, 1:, 1:] = 1.0
    both = np.zeros(m1.shape[0])
    for s in range(3):
        both += (m1 * masks[s][None] * kg1).sum(axis=(1, 2)) * ym.btts_from_matrix(gs["m2s"][s])
    return both, (m1 * kg1).sum(axis=(1, 2))


def run(f: pd.DataFrame, nesine: str | None) -> dict:
    both, kg1 = both_halves_prob(f)
    f = f.copy()
    f["b_raw"], f["kg1_raw"] = both, kg1
    hh, ha = f.HTHome.to_numpy(float), f.HTAway.to_numpy(float)
    ht_ok = np.isfinite(hh)
    y = ((hh > 0) & (ha > 0) & ((f.FTHome - hh) > 0) & ((f.FTAway - ha) > 0)).to_numpy().astype(int)
    f["y"] = y
    months = f.MatchDate.dt.to_period("M").to_numpy()
    valid = ht_ok & np.isfinite(both)
    cal = both.copy()
    for m in sorted(set(months)):
        if m < pd.Period("2019-07", "M"):
            continue
        cur, past = valid & (months == m), valid & (months < m)
        if past.sum() < 500:
            continue
        ab = ym.fit_logit_calibration(both[past], y[past])
        cal[cur] = ym.apply_logit(both[cur], ab)
    f["p"] = cal
    ok = f.ht_ok & f.lam_m.notna() & f.lam_p.notna()
    T = f[ok & (f.MatchDate >= TEST_FROM)].copy().reset_index(drop=True)
    T["ptot"], T["pmin"] = T.lam_p + T.mu_p, T[["lam_p", "mu_p"]].min(axis=1)
    out: dict = {"n_test": len(T), "gercek_oran": round(float(T.y.mean()), 4), "ort_p_kalibre": round(float(T.p.mean()), 4),
                 "ort_p_ham": round(float(T.b_raw.mean()), 4), "max_p": round(float(T.p.max()), 3),
                 "p_yuzdelikler": {str(q): round(float(T.p.quantile(q)), 3) for q in (.5, .9, .99)}}
    out["bant"] = _band(T, "p", "y", [0, .08, .10, .12, .14, .16, .18, .20, .25, 1])
    def ll(q):
        q = np.clip(q, 1e-6, 1 - 1e-6)
        return -(T.y * np.log(q) + (1 - T.y) * np.log(1 - q)).to_numpy()
    d = ll(T.p.to_numpy()) - ll(T.b_raw.to_numpy())
    se = d.std(ddof=1) / np.sqrt(len(d))
    out["kalibrasyon_vs_ham_ll"] = {"fark": round(float(d.mean()), 5), "ga": [round(float(d.mean() - 1.96 * se), 5), round(float(d.mean() + 1.96 * se), 5)]}
    ind = (T.kg1_raw * T.kg2).clip(1e-6, 1 - 1e-6)
    d2 = ll(T.p.to_numpy()) - ll(ind.to_numpy())
    out["model_vs_bagimsiz_carpim_ll"] = {"fark": round(float(d2.mean()), 5), "ga": [round(float(d2.mean() - 1.96 * d2.std(ddof=1) / np.sqrt(len(d2))), 5),
                                                                               round(float(d2.mean() + 1.96 * d2.std(ddof=1) / np.sqrt(len(d2))), 5)]}
    T["tq"] = pd.qcut(T.ptot, 5)
    out["toplam_gol_beslik"] = [{"aralik": str(k), "n": len(g), "tahmin": round(float(g.p.mean()), 4), "gercek": round(float(g.y.mean()), 4)} for k, g in T.groupby("tq", observed=True)]
    T["mq"] = pd.qcut(T.pmin, 4)
    out["iki_takim_atak_dortluk"] = [{"aralik": str(k), "n": len(g), "tahmin": round(float(g.p.mean()), 4), "gercek": round(float(g.y.mean()), 4)} for k, g in T.groupby("mq", observed=True)]
    T["fb"] = pd.cut(T.pfav, [0, .45, .55, .65, 1])
    out["favori_gucu"] = [{"aralik": str(k), "n": len(g), "tahmin": round(float(g.p.mean()), 4), "gercek": round(float(g.y.mean()), 4)} for k, g in T.groupby("fb", observed=True)]
    out["lig"] = sorted([{"lig": k, "n": len(g), "tahmin": round(float(g.p.mean()), 4), "gercek": round(float(g.y.mean()), 4)} for k, g in T.groupby("Division") if len(g) >= 300], key=lambda r: -r["gercek"])
    hi = T[T.p >= T.p.quantile(.9)]
    out["ust_desil"] = {"esik": round(float(T.p.quantile(.9)), 3), "n": len(hi), "tahmin": round(float(hi.p.mean()), 4), "gercek": round(float(hi.y.mean()), 4),
                        "lig_dagilim": hi.Division.value_counts().head(8).to_dict()}
    # Nesine fiyatı
    ratio = None
    if nesine and Path(nesine).exists():
        dd = json.loads(Path(nesine).read_text(encoding="utf-8"))
        P = ym.load_params()
        rows = []
        for m in dd["matches"]:
            ss = {s["name"]: s["odds"] for s in m["offered_selections"] if s["market"] == "1. Yarı / 2. Yarı Karşılıklı Gol"}
            if "İki Yarıda KG Var" in ss and m.get("mu_home") and m.get("mu_away"):
                ff = pd.DataFrame({"lam": [float(m["mu_home"])], "mu": [float(m["mu_away"])]})
                lam, mu = ff.lam.to_numpy(), ff.mu.to_numpy()
                share = P.get("lig_iy_payi", {}).get("_genel", ym.DEFAULT_FIRST_HALF_SHARE)
                m1 = ym.dc_matrix(lam * share, mu * share, 0.0)
                gsm = P.get("durum_carpani", {"ev": [1, 1, 1], "dep": [1, 1, 1]})
                gs = ym.game_state_model(m1, lam * (1 - share), mu * (1 - share), np.array([gsm["ev"]], float), np.array([gsm["dep"]], float), 0.0)
                n = m1.shape[1] - 1
                masks = ym.half_state_masks(n)
                k1 = np.zeros_like(m1)
                k1[:, 1:, 1:] = 1
                pr = sum((m1 * masks[s][None] * k1).sum() * ym.btts_from_matrix(gs["m2s"][s])[0] for s in range(3))
                pr = float(ym.apply_logit(np.array([pr]), (0.0, 1.0))[0])
                allp = sum(1 / v for v in ss.values())
                rows.append((m["code"], pr, ss["İki Yarıda KG Var"], allp))
        if rows:
            R = pd.DataFrame(rows, columns=["kod", "P", "oran", "toplam_1_oran"])
            R["ev"] = R.P * R.oran - 1
            ratio = float(((1 / R.oran) / R.P).mean())
            out["nesine_anlik"] = {"mac": len(R), "oran_medyan": round(float(R.oran.median()), 2), "oran_min": float(R.oran.min()), "oran_maks": float(R.oran.max()),
                                   "dort_secim_1_oran_toplam": round(float(R.toplam_1_oran.mean()), 3), "ort_p_ham": round(float(R.P.mean()), 4),
                                   "beklenen_getiri": round(float(R.ev.mean()), 3), "carpan": round(ratio, 3),
                                   "pozitif_ev_mac": int((R.ev > 0).sum()), "pozitif_ev_ort_p": round(float(R[R.ev > 0].P.mean()), 3) if (R.ev > 0).any() else None, "pozitif_ev_ort_oran": round(float(R[R.ev > 0].oran.mean()), 1) if (R.ev > 0).any() else None}
    if ratio is not None:
        out["kupon_simulasyonu"] = [r for thr in (0, .07, .08, .09) for k in (1, 2, 3, 4)
                                    if (r := simulate_coupons(T, "p", "y", lambda q: 1 / (np.asarray(q) * ratio), k, thr)) and r["n"] >= 20]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default="")
    ap.add_argument("--nesine", default="")
    ap.add_argument("--damga", default=str(pd.Timestamp.today().date()))
    a = ap.parse_args()
    f, _, _ = load_oos(a.cache or None)
    out = run(f, a.nesine or None)
    dest = ROOT / "reports" / "research" / f"iki_yari_kg_arastirma_{a.damga}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("yazıldı:", dest)


if __name__ == "__main__":
    main()
