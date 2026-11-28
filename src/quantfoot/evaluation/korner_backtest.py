"""Toplam korner Alt/Üst için sızıntısız ileri-yürüyen test (banko ailesi; t179u).

Girdi: ``yuksek_oran_backtest.build_features`` çıktısı (haftalık, yalnız geçmişten Maher korner beklentisi ``ch_m``/``ca_m``).
Her ay: toplam korner ~ a + b·beklenti doğrusal düzeltmesi YALNIZ o aydan önceki satırlarla uydurulur; dağılım negatif
binom (Var/Ort oranı geçmiş artıklardan). Sonra her (çizgi, yön) için P ≥ 0,70 diliminde tahmin vs gerçekleşme ölçülür.

Korner oranı arşivde yok: kalibrasyon ölçülür, kâr ölçülemez.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from quantfoot.markets.korner_banko import LINES, nb_over, selection_name

MIN_SLICE_N = 300          # (çizgi, yön) için dönem başına en az bağımsız maç
MAX_SHORTFALL = 0.05       # gerçekleşme < tahmin − 5 puan ise kötü kalibrasyon
SLICE_P = 0.70
PERIODS = (("doğrulama", "2022-07-01", "2024-07-01"), ("test", "2024-07-01", None))


def corner_outcomes(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    ch, ca = df.HomeCorners.to_numpy(float), df.AwayCorners.to_numpy(float)
    return np.isfinite(ch) & np.isfinite(ca), ch + ca


def walk_forward_totals(df: pd.DataFrame, cal_from: str = "2019-07-01") -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """(düzeltilmiş toplam beklenti, Var/Ort, son katsayılar). Her ayın tahmini yalnız önceki aylarla uydurulur."""
    ok, tot = corner_outcomes(df)
    e = df.ch_m.to_numpy() + df.ca_m.to_numpy()
    ok = ok & np.isfinite(e)
    months = df.MatchDate.dt.to_period("M").to_numpy()
    adj = np.full(len(df), np.nan)
    vm = np.full(len(df), np.nan)
    coef: list[float] = []
    v_last = np.nan
    n_last = 0
    first = pd.Period(cal_from, "M")
    for m in sorted(set(months)):
        if m < first:
            continue
        cur = (months == m) & ok
        past = (months < m) & ok
        if past.sum() < 1000 or not cur.any():
            continue
        X = np.c_[np.ones(past.sum()), e[past]]
        beta = np.linalg.lstsq(X, tot[past], rcond=None)[0]
        fit = X @ beta
        v_last = float(np.mean((tot[past] - fit) ** 2) / np.mean(fit))
        adj[cur] = np.clip(beta[0] + beta[1] * e[cur], 3.0, 20.0)
        vm[cur] = v_last
        coef = beta.round(4).tolist()
        n_last = int(past.sum())
    return adj, vm, {"katsayi": coef, "var_ort": round(v_last, 4), "n_egitim": n_last}


def slice_stats(p: np.ndarray, y: np.ndarray, lo: float = SLICE_P, hi: float = 1.01) -> dict[str, Any]:
    s = (p >= lo) & (p < hi)
    n = int(s.sum())
    if n == 0:
        return {"n": 0}
    pred, real = float(p[s].mean()), float(y[s].mean())
    se = float(np.sqrt(max(pred * (1 - pred), 1e-9) / n))
    return {"n": n, "tahmin": round(pred, 4), "gercek": round(real, 4), "fark": round(real - pred, 4),
            "z": round((real - pred) / se, 2)}


def evaluate(df: pd.DataFrame, adj: np.ndarray, vm: np.ndarray) -> dict[str, Any]:
    """Her (çizgi, yön) ve dönem için P ≥ 0,70 dilimi; ayrıca havuz ve P bantları."""
    ok, tot = corner_outcomes(df)
    ok = ok & np.isfinite(adj)
    dates = df.MatchDate.to_numpy()
    out: dict[str, Any] = {"secimler": {}, "havuz": {}, "bantlar": {}}
    for per, a, b in PERIODS:
        msk = ok & (dates >= np.datetime64(a))
        if b:
            msk &= dates < np.datetime64(b)
        pooled_p, pooled_y = [], []
        for ln in LINES:
            po = nb_over(np.nan_to_num(adj[msk], nan=10.0), np.nan_to_num(vm[msk], nan=1.15), ln)
            yo = (tot[msk] > ln).astype(float)
            for side, p, yy in (("Üst", po, yo), ("Alt", 1 - po, 1 - yo)):
                st = slice_stats(p, yy)
                out["secimler"].setdefault(selection_name(ln, side), {})[per] = st
                pooled_p.append(p)
                pooled_y.append(yy)
        P, Y = np.concatenate(pooled_p), np.concatenate(pooled_y)
        out["havuz"][per] = {"tum_P>=0.70": slice_stats(P, Y)}
        out["bantlar"][per] = {f"{lo:.2f}-{min(hi, 1):.2f}": slice_stats(P, Y, lo, hi)
                               for lo, hi in ((0.70, 0.75), (0.75, 0.80), (0.80, 0.90), (0.90, 1.01))}
    return out


def validated(result: dict[str, Any], min_n: int = MIN_SLICE_N, max_shortfall: float = MAX_SHORTFALL) -> tuple[list[str], dict[str, str]]:
    """Geçerli seçimler: HER İKİ dönemde P ≥ 0,70 diliminde n ≥ min_n ve gerçekleşme ≥ tahmin − max_shortfall.
    İkinci dönüş değeri elenenlerin gerekçesi."""
    good: list[str] = []
    why: dict[str, str] = {}
    for name, per in result["secimler"].items():
        reasons = []
        for pname, st in per.items():
            if st.get("n", 0) < min_n:
                reasons.append(f"{pname}: P≥0,70 diliminde yalnız {st.get('n', 0)} maç")
            elif st["fark"] < -max_shortfall:
                reasons.append(f"{pname}: gerçek {st['gercek']:.3f} < tahmin {st['tahmin']:.3f} − 5 puan")
        if reasons:
            why[name] = "; ".join(reasons)
        else:
            good.append(name)
    return good, why
