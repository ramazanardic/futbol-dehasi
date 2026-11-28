"""21 Kasım hata analizi — günlük hataların arşivde (2011/12+, ~116k maç; test 2016/17+) kalıcı mı gürültü mü olduğunu sınar.

    python scripts/bahis_aileleri_kalibrasyon.py onbellek     # önce arşiv önbelleği (üretim hattı)
    python arsiv_kod/hata_analizi_21kasim.py [--yaz]

A) Yüksek-P kuyruk kalibrasyonu (seçimlerin oynandığı bölge, P .55–.90): her seçim/karşı taraf için mevcut üretim
   kalibrasyonundan (market_calibration.json Platt, yalnız türetilmiş) SONRA kalan sapma. Eğitim 2011–2020 sezonları,
   test 2021+; logit kayması δ yalnız test log-loss farkının %95 (maç-bootstrap) GA üst ucu < 0 ise tutulur.
B) Beraberlik profili: oran bantlarına göre gerçek beraberlik (MS + İY, 0-0/1-1/2-2) vs marjsız piyasa P'si, ortalama
   ve en iyi oranla beraberlik ROI; beraberlik düzeltmesi (logit p0 + düşük toplam + lig beraberlik eğilimi) walk-forward.

--yaz: data/calibration/market_tail_calibration.json ve reports/research/hata_analizi_21kasim.json yazar.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.markets.market_calibration import apply_platt_league, load_market_calibration  # noqa: E402

CACHE = ROOT / "reports" / "research" / "backtest_cache_bahis_aileleri.npz"
OUT_CAL = ROOT / "data" / "calibration" / "market_tail_calibration.json"
OUT_JSON = ROOT / "reports" / "research" / "hata_analizi_21kasim.json"
DIRECT = {"MS 1", "MS 0", "MS 2", "ÇŞ 1X", "ÇŞ 12", "ÇŞ X2", "2.5 Üst"}
LOW_DIV = {"E2", "E3", "EC", "SC1", "SC2", "SC3", "I2", "SP2", "F2", "D2"}
LO, HI = 0.55, 0.90
TRAIN_END = 2020  # sezon başlangıç yılı ≤ 2020 eğitim
SKIP_PREFIX = ("Skor", "İY Skor", "İY/MS", "Fark", "6+", "4-5")  # uzun oranlı; banko bölgesine girmez


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _sig(z):
    return 1 / (1 + np.exp(-z))


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot_ci(d, n_boot=600, seed=7):
    rng = np.random.default_rng(seed)
    n = len(d)
    m = np.array([d[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def fit_offset(x, y, iters=30):
    """logit kayması δ: Σ (σ(x+δ) − y) = 0 (Newton)."""
    d = 0.0
    for _ in range(iters):
        q = _sig(x + d)
        g, h = (q - y).sum(), (q * (1 - q)).sum()
        if h <= 0:
            break
        d -= g / h
    return float(np.clip(d, -1.0, 1.0))


def load():
    z = np.load(CACHE, allow_pickle=False)
    date = z["date"]
    season = np.array([int(d[:4]) - (1 if int(d[5:7]) < 7 else 0) for d in date])
    month = np.array([int(d[5:7]) for d in date])
    return dict(P=z["P"].astype(float), Y=z["Y"].astype(float), sel=[str(s) for s in z["sel"]], div=z["div"].astype(str),
                season=season, month=month, odds=z["odds"], goals=z["goals"])


def production_p(A, s):
    """Seçimin üretimdeki P'si: türetilmişse market_calibration Platt'ı (lig sapmalı) uygulanmış."""
    i = A["sel"].index(s)
    p = A["P"][:, i]
    cal = (load_market_calibration() or {}).get("markets") or {}
    if s in cal and s not in DIRECT:
        p = apply_platt_league(cal[s], p, A["div"])
    return p, A["Y"][:, i]


# ------------------------------------------------------------------------------------------ A) kuyruk
def tail_study(A):
    tr, te = A["season"] <= TRAIN_END, A["season"] > TRAIN_END
    rows, seen = [], set()
    for s in A["sel"]:
        if s.startswith(SKIP_PREFIX):
            continue
        p0, y0 = production_p(A, s)
        for side in (False, True):
            name = s if not side else _complement_name(s)
            if name is None or name in seen:
                continue
            seen.add(name)
            p, y = (1 - p0, 1 - y0) if side else (p0, y0)
            band = (p >= LO) & (p < HI)
            mtr, mte = tr & band, te & band
            if mtr.sum() < 400 or mte.sum() < 300:
                continue
            x = _logit(p)
            d = fit_offset(x[mtr], y[mtr])
            q = _sig(x + d)
            dll = ll(q[mte], y[mte]) - ll(p[mte], y[mte])
            lo, hi = boot_ci(dll)
            seasons = sorted(set(A["season"][mte]))
            gaps = [float(y[mte & (A["season"] == k)].mean() - p[mte & (A["season"] == k)].mean()) for k in seasons]
            rows.append(dict(
                secim=name, direct=s in DIRECT, n_train=int(mtr.sum()), n_test=int(mte.sum()),
                p_test=round(float(p[mte].mean()), 4), hit_test=round(float(y[mte].mean()), 4),
                gap_test=round(float(y[mte].mean() - p[mte].mean()), 4), gap_train=round(float(y[mtr].mean() - p[mtr].mean()), 4),
                brier_test=round(float(((p[mte] - y[mte]) ** 2).mean()), 5),
                brier_test_adj=round(float(((q[mte] - y[mte]) ** 2).mean()), 5),
                delta=round(d, 4), dll=round(float(dll.mean()), 6), ci=[round(lo, 6), round(hi, 6)],
                kept=bool(hi < 0 and abs(d) >= 0.01), test_seasons_same_sign=f"{sum(np.sign(g) == np.sign(d) for g in gaps)}/{len(gaps)}"))
    return rows


def _complement_name(s):
    if "&" in s:
        return None
    for a, b in (("Üst", "Alt"), ("Var", "Yok"), ("Tek", "Çift")):
        if s.endswith(a):
            return s[: -len(a)] + b
    if s.startswith(("Ev ", "Dep ")) and ("Yarı" in s or "Kazanır" in s or "En Çok" in s):
        return f"DEĞİL({s})"
    comp = {"MS 1": "ÇŞ X2", "MS 2": "ÇŞ 1X", "MS 0": "ÇŞ 12", "İY 0": "İY ÇŞ 12", "İY 1": "İY ÇŞ X2", "İY 2": "İY ÇŞ 1X",
            }
    return comp.get(s)


# ------------------------------------------------------------------------------------------ B) beraberlik
def _bucket_table(A, mask, key_fn, labels):
    P, Y, g, o = A["P"], A["Y"], A["goals"], A["odds"]
    i0 = A["sel"].index("MS 0")
    p0, y0 = P[:, i0], Y[:, i0]
    ht_d = (g[:, 0] == g[:, 1]).astype(float)
    ft = g[:, 2:4]
    keys = key_fn()
    out = []
    for k in labels:
        m = mask & (keys == k)
        n = int(m.sum())
        if n < 200:
            continue
        avg_o, max_o = o[m, 1], o[m, 6]
        roi_avg = float(np.mean(np.where(y0[m] > 0, avg_o - 1, -1)))
        roi_max = float(np.mean(np.where(y0[m] > 0, np.nan_to_num(max_o, nan=1.0) - 1, -1)))
        gaps = []
        for s in sorted(set(A["season"][m])):
            mm = m & (A["season"] == s)
            if mm.sum() >= 50:
                gaps.append(y0[mm].mean() - p0[mm].mean())
        se = float(np.std(gaps, ddof=1) / np.sqrt(len(gaps))) if len(gaps) > 2 else float("nan")
        out.append(dict(kova=k, n=n, beraberlik=round(float(y0[m].mean()), 4), piyasa_p=round(float(p0[m].mean()), 4),
                        fark=round(float(y0[m].mean() - p0[m].mean()), 4), se=round(se, 4),
                        iy_beraberlik=round(float(ht_d[m].mean()), 4),
                        s00=round(float(((ft[m, 0] == 0) & (ft[m, 1] == 0)).mean()), 4),
                        s11=round(float(((ft[m, 0] == 1) & (ft[m, 1] == 1)).mean()), 4),
                        s22=round(float(((ft[m, 0] == 2) & (ft[m, 1] == 2)).mean()), 4),
                        ort_oran=round(float(np.mean(avg_o)), 3), roi_ort=round(roi_avg, 4), roi_max=round(roi_max, 4)))
    return out


def _band(v, edges, names):
    out = np.full(len(v), names[-1], dtype=object)
    for e, nme in zip(edges[::-1], names[::-1][1:]):
        pass
    idx = np.searchsorted(np.asarray(edges), v, side="right")
    return np.array([names[min(i, len(names) - 1)] for i in idx], dtype=object)


def league_draw_prior(A):
    """Her maç için ligin ÖNCEKİ sezon(lar)daki beraberlik oranı − genel (sızıntısız, son 3 sezon)."""
    i0 = A["sel"].index("MS 0")
    y0 = A["Y"][:, i0]
    out = np.zeros(len(y0))
    for d in set(A["div"]):
        md = A["div"] == d
        for s in set(A["season"][md]):
            prev = md & (A["season"] < s) & (A["season"] >= s - 3)
            if prev.sum() >= 200:
                out[md & (A["season"] == s)] = y0[prev].mean()
            else:
                out[md & (A["season"] == s)] = np.nan
    return out


def draw_study(A):
    P, o = A["P"], A["odds"]
    i1, i0, i2, io = (A["sel"].index(s) for s in ("MS 1", "MS 0", "MS 2", "2.5 Üst"))
    p1, p0, p2, po = P[:, i1], P[:, i0], P[:, i2], P[:, io]
    fav_odds = np.minimum(o[:, 0], o[:, 2])
    test = A["season"] >= 2016
    T = {}
    T["favori_oran"] = _bucket_table(A, test, lambda: _band(fav_odds, [1.30, 1.50, 1.80, 2.10], ["1.10-1.30", "1.30-1.50", "1.50-1.80", "1.80-2.10", "2.10+ (dengeli)"]),
                                     ["1.10-1.30", "1.30-1.50", "1.50-1.80", "1.80-2.10", "2.10+ (dengeli)"])
    T["ev_dep_farki"] = _bucket_table(A, test, lambda: _band(np.abs(p1 - p2), [0.10, 0.20, 0.35, 0.50], ["<.10", ".10-.20", ".20-.35", ".35-.50", "≥.50"]),
                                      ["<.10", ".10-.20", ".20-.35", ".35-.50", "≥.50"])
    T["beraberlik_orani"] = _bucket_table(A, test, lambda: _band(o[:, 1], [3.00, 3.30, 3.60, 4.00], ["<3.00", "3.00-3.30", "3.30-3.60", "3.60-4.00", "4.00+"]),
                                          ["<3.00", "3.00-3.30", "3.30-3.60", "3.60-4.00", "4.00+"])
    T["ust25_p"] = _bucket_table(A, test, lambda: _band(po, [0.40, 0.45, 0.50, 0.55, 0.60], ["<.40", ".40-.45", ".45-.50", ".50-.55", ".55-.60", "≥.60"]),
                                 ["<.40", ".40-.45", ".45-.50", ".50-.55", ".55-.60", "≥.60"])
    T["lig_kademe"] = _bucket_table(A, test, lambda: np.where(np.isin(A["div"], list(LOW_DIV)), "alt/ikinci lig", "üst lig"),
                                    ["üst lig", "alt/ikinci lig"])
    prior = league_draw_prior(A)
    T["lig_beraberlik_egilimi"] = _bucket_table(A, test & np.isfinite(prior), lambda: _band(np.nan_to_num(prior, nan=0.26), [0.24, 0.26, 0.28], ["<%24", "%24-26", "%26-28", "≥%28"]),
                                                ["<%24", "%24-26", "%26-28", "≥%28"])
    phase = np.where(np.isin(A["month"], [7, 8, 9, 10]), "sezon başı (Tem-Eki)",
                     np.where(np.isin(A["month"], [11, 12, 1, 2]), "sezon ortası (Kas-Şub)", "sezon sonu (Mar-Haz)"))
    T["sezon_evresi"] = _bucket_table(A, test, lambda: phase, ["sezon başı (Tem-Eki)", "sezon ortası (Kas-Şub)", "sezon sonu (Mar-Haz)"])
    combo = (po < 0.45) & (p0 >= 0.28)
    T["birlesik_bolge"] = _bucket_table(A, test, lambda: np.where(combo, "2.5Ü<.45 & piyasa beraberlik ≥.28", "diğer"),
                                        ["2.5Ü<.45 & piyasa beraberlik ≥.28", "diğer"])
    T["lig"] = _bucket_table(A, test, lambda: A["div"], sorted(set(A["div"])))
    return T, prior


LOW_TOTAL = 0.45  # P(2.5 Üst) bunun altı = düşük toplam beklentisi


def fit_draw_adjust(A, prior=None):
    """logit p0' = logit p0 + a + c·1[P(2.5Ü) < .45]; eğitim ≤2020, test 2021+ (maç-bootstrap GA). Daha zengin model
    (eğim + sürekli düşük-toplam + lig eğilimi) testte GA'yı geçemedi → basit iki parametreli düzeltme."""
    from scipy.optimize import minimize

    i0, io = A["sel"].index("MS 0"), A["sel"].index("2.5 Üst")
    p0, po, y = A["P"][:, i0], A["P"][:, io], A["Y"][:, i0]
    x, z = _logit(p0), (po < LOW_TOTAL).astype(float)
    tr, te = (A["season"] >= 2012) & (A["season"] <= TRAIN_END), A["season"] > TRAIN_END
    t = minimize(lambda t: ll(_sig(x[tr] + t[0] + t[1] * z[tr]), y[tr]).sum(), np.zeros(2), method="L-BFGS-B").x
    q = _sig(x + t[0] + t[1] * z)
    d = ll(q[te], y[te]) - ll(p0[te], y[te])
    lo, hi = boot_ci(d)
    low = te & (z > 0)
    br0, br1 = float(((p0[te] - y[te]) ** 2).mean()), float(((q[te] - y[te]) ** 2).mean())
    res = dict(a=float(t[0]), c_low_total=float(t[1]), low_total_below=LOW_TOTAL, n_train=int(tr.sum()), n_test=int(te.sum()),
               dll_test=float(d.mean()), ci=[lo, hi], kept=bool(hi < 0), brier_test=[br0, br1],
               test_low_total=dict(n=int(low.sum()), real=float(y[low].mean()), p_market=float(p0[low].mean()), p_adj=float(q[low].mean())),
               test_all=dict(real=float(y[te].mean()), p_market=float(p0[te].mean()), p_adj=float(q[te].mean())))
    i1, i2 = A["sel"].index("MS 1"), A["sel"].index("MS 2")
    fav_home = A["P"][:, i1] >= A["P"][:, i2]
    pf = np.where(fav_home, A["P"][:, i1], A["P"][:, i2])
    yf = np.where(fav_home, A["Y"][:, i1], A["Y"][:, i2])
    for lab, m in (("fav_win_low_total_test", te & (z > 0) & (pf >= 0.55)), ("fav_win_banko_band_test", te & (pf >= 0.55) & (pf < 0.80))):
        res[lab] = dict(n=int(m.sum()), p=float(pf[m].mean()), real=float(yf[m].mean()))
    return res, q

# ------------------------------------------------------------------------------------------ C) yüksek oranlı pazarlar
HIGH_ODDS = [f"İY/MS {a}/{b}" for a in "102" for b in "102"] + ["İY 1", "İY 0", "İY 2", "2Y 1", "2Y 0", "2Y 2",
                                                                   "İki Yarıda KG Var", "Skor 2-1", "Skor 1-2", "Skor 3-1", "Skor 1-3", "Skor 2-2"]
# Nesine ödeme oranı (oran × marjsız P medyanı, 21 Kas 2026 bülteni, 52–119 maç): İY/MS ≈ .71–.77, İY/2Y sonucu ≈ .80–.84
NESINE_PAYOUT = {"İY/MS": 0.75, "İY": 0.82, "2Y": 0.82, "İki Yarıda KG Var": 0.85, "Skor": 0.60}


def _payout(name):
    for k, v in NESINE_PAYOUT.items():
        if name.startswith(k):
            return v
    return 0.75


def _diff_band(d):
    return np.select([d <= -0.30, d <= -0.10, d < 0.10, d < 0.30], ["dep güçlü fav", "dep hafif fav", "dengeli", "ev hafif fav"], "ev güçlü fav")


def _tot_band(po):
    return np.select([po < 0.45, po < 0.55], ["düşük toplam (2.5Ü<.45)", "orta (.45–.55)"], "yüksek toplam (≥.55)")


def htft_study(A):
    """Her yüksek oranlı çıktı: üretim P'sinin (Platt'lı) kalibrasyonu, güvenilirlik (5 eşit kütleli kova), Brier/LL,
    oran profiline göre görülme/P oranı ve Nesine ödemesiyle tahmini ROI; walk-forward ek kalibrasyon (eğim + fark +
    toplam özellikleri) yalnız 2021+ test LL GA üst ucu < 0 ise tutulur."""
    from scipy.optimize import minimize

    i1, i2, io = (A["sel"].index(s) for s in ("MS 1", "MS 2", "2.5 Üst"))
    diff, po = A["P"][:, i1] - A["P"][:, i2], A["P"][:, io]
    test = A["season"] >= 2016
    tr, te = (A["season"] >= 2012) & (A["season"] <= TRAIN_END), A["season"] > TRAIN_END
    db, tb = _diff_band(diff), _tot_band(po)
    out, fits = {}, {}
    for name in HIGH_ODDS:
        if name not in A["sel"]:
            continue
        p, y = production_p(A, name)
        m = test
        q = np.clip(p[m], 1e-6, 1 - 1e-6)
        order = np.argsort(q)
        rel = []
        for part in np.array_split(order, 5):
            rel.append([round(float(q[part].mean()), 4), round(float(y[m][part].mean()), 4), int(len(part))])
        pay = _payout(name)
        prof = []
        for b1 in ("ev güçlü fav", "ev hafif fav", "dengeli", "dep hafif fav", "dep güçlü fav"):
            for b2 in ("düşük toplam (2.5Ü<.45)", "orta (.45–.55)", "yüksek toplam (≥.55)"):
                mm = m & (db == b1) & (tb == b2)
                if mm.sum() < 300:
                    continue
                roi = float(np.mean(y[mm] * pay / np.clip(p[mm], 1e-3, 1)) - 1)
                prof.append(dict(fark=b1, toplam=b2, n=int(mm.sum()), p=round(float(p[mm].mean()), 4), gercek=round(float(y[mm].mean()), 4),
                                 oran_gercek_p=round(float(y[mm].mean() / max(p[mm].mean(), 1e-6)), 3), nesine_roi_tahmini=round(roi, 4)))
        # walk-forward ek kalibrasyon
        x = np.column_stack([_logit(p), diff, po - 0.5])
        f = lambda t, mm: ll(_sig(t[0] + t[1] * x[mm, 0] + t[2] * x[mm, 1] + t[3] * x[mm, 2]), y[mm]).sum()
        t = minimize(lambda t: f(t, tr), np.array([0.0, 1.0, 0.0, 0.0]), method="L-BFGS-B").x
        qq = _sig(t[0] + t[1] * x[:, 0] + t[2] * x[:, 1] + t[3] * x[:, 2])
        dl = ll(qq[te], y[te]) - ll(p[te], y[te])
        lo, hi = boot_ci(dl)
        kept = bool(hi < 0)
        fits[name] = dict(a=float(t[0]), b=float(t[1]), c_diff=float(t[2]), d_total=float(t[3]), kept=kept,
                          dll=float(dl.mean()), ci=[lo, hi], brier_test=[float(((p[te] - y[te]) ** 2).mean()), float(((qq[te] - y[te]) ** 2).mean())],
                          test_p=[float(p[te].mean()), float(qq[te].mean())], test_real=float(y[te].mean()))
        out[name] = dict(n=int(m.sum()), p=round(float(p[m].mean()), 4), gercek=round(float(y[m].mean()), 4),
                         fark=round(float(y[m].mean() - p[m].mean()), 4), brier=round(float(((p[m] - y[m]) ** 2).mean()), 5),
                         logloss=round(float(ll(p[m], y[m]).mean()), 5), guvenilirlik=rel, profil=prof,
                         nesine_odeme=pay, ek_kalibrasyon=fits[name])
    # geri dönüş (comeback): İY önde olan takım maçı kaybeder
    g = A["goals"]
    for side, lead, lose in (("ev", "İY 1", "İY/MS 1/2"), ("dep", "İY 2", "İY/MS 2/1")):
        pl, _ = production_p(A, lead)
        pc, _ = production_p(A, lose)
        ht_lead = (g[:, 0] > g[:, 1]) if side == "ev" else (g[:, 1] > g[:, 0])
        ft_lose = (g[:, 2] < g[:, 3]) if side == "ev" else (g[:, 3] < g[:, 2])
        mm = test & ht_lead
        out[f"geri_donus_{side}"] = dict(n_ht_onde=int(mm.sum()), model_kosullu=round(float((pc[test] / np.clip(pl[test], 1e-4, 1)).mean()), 4),
                                        model_kosullu_agirlikli=round(float(pc[test].sum() / pl[test].sum()), 4),
                                        gercek=round(float(ft_lose[mm].mean()), 4))
    # İY gol payı (lig bazında): gerçek İY gol / toplam gol ve İY 0.5 Üst model farkı
    lg = {}
    iy05, y05 = production_p(A, "İY 0.5 Üst")
    for d in sorted(set(A["div"])):
        mm = test & (A["div"] == d)
        tot = g[mm, 2].sum() + g[mm, 3].sum()
        lg[d] = dict(n=int(mm.sum()), iy_gol_payi=round(float((g[mm, 0].sum() + g[mm, 1].sum()) / max(tot, 1)), 4),
                     iy05_p=round(float(iy05[mm].mean()), 4), iy05_gercek=round(float(y05[mm].mean()), 4))
    out["lig_iy_gol_payi"] = lg
    return out, fits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaz", action="store_true")
    a = ap.parse_args()
    A = load()
    tail = tail_study(A)
    tables, prior = draw_study(A)
    adj, _ = fit_draw_adjust(A, prior)
    htft, htft_fits = htft_study(A)
    for k, v in htft.items():
        if k.startswith("geri") :
            print(k, v)
        elif k != "lig_iy_gol_payi":
            e = v["ek_kalibrasyon"]
            print(f"{k:18s} n={v['n']} p={v['p']:.4f} gerçek={v['gercek']:.4f} fark={v['fark']:+.4f} brier={v['brier']} ek_kal tutuldu={e['kept']} dLL={e['dll']:+.6f} GA={[round(c, 6) for c in e['ci']]} güv={v['guvenilirlik']}")
    league_prior_latest = {}
    i0 = A["sel"].index("MS 0")
    last = A["season"].max()
    for d in sorted(set(A["div"])):
        m = (A["div"] == d) & (A["season"] >= last - 3)
        league_prior_latest[d] = round(float(A["Y"][m, i0].mean()), 4)
    kept = {r["secim"]: {"delta": r["delta"], "lo": LO, "hi": HI, "n_test": r["n_test"], "dll": r["dll"], "ci": r["ci"],
                         "gap_test": r["gap_test"], "direct": r["direct"]} for r in tail if r["kept"]}
    rel = {r["secim"]: {"gap_test": r["gap_test"], "ci_ok": r["kept"], "n_test": r["n_test"]} for r in tail}
    for r in sorted(tail, key=lambda r: r["dll"])[:25]:
        print(f"{r['secim']:28s} n={r['n_test']:6d} p={r['p_test']:.3f} hit={r['hit_test']:.3f} gap={r['gap_test']:+.4f} δ={r['delta']:+.3f} dLL={r['dll']:+.6f} CI={r['ci']} kept={r['kept']} {r['test_seasons_same_sign']}")
    print("tutulan kuyruk düzeltmesi:", len(kept), "/", len(tail))
    print("beraberlik düzeltmesi:", json.dumps(adj, ensure_ascii=False))
    for k, v in tables.items():
        print("\n==", k)
        for r in v:
            print("  ", r)
    if a.yaz:
        OUT_CAL.write_text(json.dumps({
            "version": 1, "fitted_on": "data/matches.csv 2011/12–2020/21 eğitim, 2021/22+ test (üretim hattı + market_calibration)",
            "applies_to": "P .55–.90 bölgesi (banko/kupon bacakları); δ logit kayması, yalnız test LL GA üst ucu < 0 olanlar",
            "tail": kept, "draw_adjust": {k: adj[k] for k in ("a", "c_low_total", "low_total_below", "kept", "dll_test", "ci")},
            "league_draw_rate": league_prior_latest, "reliability": rel,
            "htft": {k: {kk: v[kk] for kk in ("a", "b", "c_diff", "d_total", "dll", "ci")} for k, v in htft_fits.items() if v["kept"]},
            "nesine_payout": NESINE_PAYOUT}, ensure_ascii=False, indent=1), encoding="utf-8")
        OUT_JSON.write_text(json.dumps({"kuyruk": tail, "beraberlik_tablolari": tables, "beraberlik_duzeltmesi": adj,
                                        "lig_beraberlik_orani_son4": league_prior_latest,
                                        "yuksek_oranli": htft}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("yazıldı:", OUT_CAL, OUT_JSON)


if __name__ == "__main__":
    main()
