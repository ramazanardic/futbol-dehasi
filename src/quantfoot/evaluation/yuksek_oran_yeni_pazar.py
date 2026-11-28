"""Yüksek oran katmanına aday ek pazarların sızıntısız ileri-yürüyen değerlendirmesi (t179u).

Adaylar (Nesine'de sunulan): toplam gol aralığı, İY gol sayısı, 2Y gol sayısı, en çok gol olacak yarı, her iki yarıda
1,5 üst, 2Y sonucu, İY/2Y KG, İY skoru × maç skoru. Mevcut yarı modelinden türetilir (``ym.extra_markets``).

Kıyas ("piyasa türevi"): 1X2 + 2.5 Alt/Üst oranlarından ters çevrilmiş λ,μ; sabit %44,4 İY payı; yarılar bağımsız Poisson;
durum çarpanı ve kalibrasyon yok. Bu pazarların gerçek piyasa fiyatı arşivde yok; bu en iyi türev kıyastır.
Yeni model ("sonra"): harman λ, lig İY payı, devre-arası durum çarpanı (aylık, geçmişten) + aylık yalnız geçmişle
kalibrasyon (çok sınıflı hücre çarpanı / ikili logit).

Karar: bir pazar ancak hem doğrulama (2022-07..2024-07) hem test (2024-07+) döneminde log-loss'u kıyastan düşükse
(doğrulamada t ≤ −2, testte t ≤ −3; sekiz pazar denendiği için eşik katı) ve test ECE'si kıyastan kötü değilse eklenir.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quantfoot.evaluation import yuksek_oran_backtest as bt
from quantfoot.markets import yuksek_oran_modeli as ym

MARKETS = {
    "gol_araligi": "Toplam gol aralığı (0-1 / 2-3 / 4-5 / 6+)",
    "iy_gol": "İY gol sayısı (0 / 1 / 2+)",
    "2y_gol": "2Y gol sayısı (0 / 1 / 2+)",
    "en_cok_gol_yari": "En çok gol olacak yarı (1Y / Eşit / 2Y)",
    "iki_yari_15_ust": "Her iki yarıda da 1,5 üst",
    "2y_sonucu": "2. yarı sonucu (1 / X / 2)",
    "iy_2y_kg": "İY / 2Y karşılıklı gol",
    "iy_ms_skor": "İlk yarı skoru / maç skoru",
}
PERIODS = (("doğrulama", "2022-07-01", "2024-07-01"), ("test", "2024-07-01", None))
VAL_T, TEST_T = -2.0, -3.0


def outcomes_extra(df: pd.DataFrame) -> dict[str, np.ndarray]:
    fh, fa = df.FTHome.to_numpy(float), df.FTAway.to_numpy(float)
    hh, ha = df.HTHome.to_numpy(float), df.HTAway.to_numpy(float)
    ok = np.isfinite(hh) & np.isfinite(ha)
    hh0, ha0 = np.nan_to_num(hh).astype(int), np.nan_to_num(ha).astype(int)
    fhi, fai = fh.astype(int), fa.astype(int)
    t1 = hh0 + ha0
    t2 = (fhi + fai) - t1
    tot = fhi + fai
    d2 = (fhi - hh0) - (fai - ha0)
    b1 = (hh0 > 0) & (ha0 > 0)
    b2 = ((fhi - hh0) > 0) & ((fai - ha0) > 0)
    cls = np.full(len(df), len(ym.HT_FT_SCORE_HT) * len(ym.HT_FT_SCORE_FT))
    for hi, (a, b) in enumerate(ym.HT_FT_SCORE_HT):
        for fi, (c, d) in enumerate(ym.HT_FT_SCORE_FT):
            cls[(hh0 == a) & (ha0 == b) & (fhi == c) & (fai == d)] = hi * len(ym.HT_FT_SCORE_FT) + fi
    return {
        "ok": ok,
        "gol_araligi": np.where(tot <= 1, 0, np.where(tot <= 3, 1, np.where(tot <= 5, 2, 3))),
        "iy_gol": np.minimum(t1, 2),
        "2y_gol": np.minimum(np.maximum(t2, 0), 2),
        "en_cok_gol_yari": np.where(t1 > t2, 0, np.where(t1 == t2, 1, 2)),
        "iki_yari_15_ust": ((t1 >= 2) & (t2 >= 2)).astype(int),
        "2y_sonucu": np.where(d2 > 0, 0, np.where(d2 == 0, 1, 2)),
        "iy_2y_kg": np.where(b1 & b2, 0, np.where(b1 & ~b2, 1, np.where(~b1 & b2, 2, 3))),
        "iy_ms_skor": cls,
    }


def model_markets(df: pd.DataFrame, cfg: bt.ProbConfig, variant: str,
                  mult: tuple[np.ndarray, np.ndarray] | None = None, chunk: int = 20000) -> dict[str, np.ndarray]:
    """variant: 'piyasa' (kıyas) ya da 'sonra' (yeni model, kalibrasyonsuz)."""
    n = len(df)
    if variant == "piyasa":
        lam, mu = df.lam_p.to_numpy(), df.mu_p.to_numpy()
        sh = sa = np.full(n, bt.OLD_SHARE)
        r1 = r2 = 0.0
    else:
        lam, mu = bt.blended_lambdas(df, cfg)
        sh, sa = bt.half_shares(df, cfg)
        r1, r2 = cfg.rho_iy, cfg.rho_2y
    lam, mu = np.nan_to_num(lam, nan=1.4), np.nan_to_num(mu, nan=1.1)
    mh, ma = mult if (mult is not None and variant == "sonra") else (np.ones((n, 3)), np.ones((n, 3)))
    parts: dict[str, list[np.ndarray]] = {}
    for a in range(0, n, chunk):
        b = min(a + chunk, n)
        m1 = ym.dc_matrix(lam[a:b] * sh[a:b], mu[a:b] * sa[a:b], r1)
        gs = ym.game_state_model(m1, lam[a:b] * (1 - sh[a:b]), mu[a:b] * (1 - sa[a:b]), mh[a:b], ma[a:b], r2)
        for k, v in ym.extra_markets(m1, gs).items():
            parts.setdefault(k, []).append(v)
    return {k: np.concatenate(v) for k, v in parts.items()}


def walk_forward_calibrate_extra(df: pd.DataFrame, raw: dict[str, np.ndarray], y: dict[str, np.ndarray], cal_from: str,
                                 prior: float = 60.0) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    months = df.MatchDate.dt.to_period("M").to_numpy()
    ok = y["ok"] & np.isfinite(df.lam_m.to_numpy()) | y["ok"] & np.isfinite(df.lam_p.to_numpy())
    out = {k: v.copy() for k, v in raw.items()}
    final: dict[str, Any] = {}
    first = pd.Period(cal_from, "M")
    for m in sorted(set(months)):
        if m < first:
            continue
        cur = (months == m) & ok
        past = (months < m) & ok
        if past.sum() < 500 or not cur.any():
            continue
        for k, p in raw.items():
            if p.ndim == 2:
                f = ym.cell_factors(p[past], y[k][past], prior)
                out[k][cur] = ym.apply_cell_factors(p[cur], f)
                final[k] = f.round(4).tolist()
            else:
                ab = ym.fit_logit_calibration(p[past], y[k][past].astype(float))
                out[k][cur] = ym.apply_logit(p[cur], ab)
                final[k] = [round(ab[0], 4), round(ab[1], 4)]
    final["son_ay"] = str(max(months))
    return out, final


def _ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    return bt.per_row_ll(p, y)


def compare(df: pd.DataFrame, y: dict[str, np.ndarray], pm: dict[str, np.ndarray], son: dict[str, np.ndarray],
            ham: dict[str, np.ndarray]) -> dict[str, Any]:
    dates = df.MatchDate.to_numpy()
    base_ok = y["ok"] & np.isfinite(df.lam_m.to_numpy()) & np.isfinite(df.lam_p.to_numpy())
    res: dict[str, Any] = {}
    for key in MARKETS:
        res[key] = {}
        for per, a, b in PERIODS:
            msk = base_ok & (dates >= np.datetime64(a))
            if b:
                msk &= dates < np.datetime64(b)
            yy = y[key][msk]
            lp, ls, lh = _ll(pm[key][msk], yy), _ll(son[key][msk], yy), _ll(ham[key][msk], yy)
            res[key][per] = {
                "n": int(msk.sum()),
                "logloss": {"piyasa": round(float(lp.mean()), 5), "sonra_ham": round(float(lh.mean()), 5),
                            "sonra": round(float(ls.mean()), 5)},
                "sonra_vs_piyasa": bt.paired_delta(lp, ls),
                "ham_vs_piyasa": bt.paired_delta(lp, lh),
                "ece": {"piyasa": bt.ece(pm[key][msk], yy), "sonra": bt.ece(son[key][msk], yy)},
                "kalibrasyon_sonra": bt.calibration_table(son[key][msk], yy),
            }
    return res


def decide(res: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    keep: list[str] = []
    why: dict[str, str] = {}
    for key, per in res.items():
        v, t = per["doğrulama"], per["test"]
        reasons = []
        for name, r, thr in (("doğrulama", v, VAL_T), ("test", t, TEST_T)):
            d = r["sonra_vs_piyasa"]
            if not (d["fark"] < 0 and d["t"] <= thr):
                reasons.append(f"{name}: log-loss farkı {d['fark']:+.5f} (t={d['t']}), eşik t ≤ {thr}")
        if t["ece"]["sonra"] > t["ece"]["piyasa"] + 1e-9:
            reasons.append(f"test ECE kötü: {t['ece']['sonra']} > {t['ece']['piyasa']}")
        if reasons:
            why[key] = "; ".join(reasons)
        else:
            keep.append(key)
    return keep, why
