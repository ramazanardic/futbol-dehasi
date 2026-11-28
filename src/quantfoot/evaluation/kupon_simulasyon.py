"""Yüksek oranlı pazarlar (İY/MS, 2Y KG) için geçmiş kupon simülasyonu yardımcıları.

Arşivde İY/MS ve 2Y KG oranı yoktur; bu yüzden ROI "sentetik Nesine oranı" ile hesaplanır:
oran = 1 / (P × ödeme_çarpanı(P)); çarpan, Nesine bülteninden ölçülen (1/oran)/P değerinin P kovasındaki ortalamasıdır.
Kupon tutma oranı ise gerçek sonuçlardır; yalnız ROI sentetik fiyata bağlıdır.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """İkili oran için Wilson %95 güven aralığı."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(c - h), float(c + h))


def payout_curve(p: np.ndarray, imp_over_p: np.ndarray):
    """P kovası ortalamasına göre (1/oran)/P çarpanı eğrisi; sentetik oran üreten fonksiyon döner."""
    order = np.argsort(p)
    px, rx = np.asarray(p, float)[order], np.asarray(imp_over_p, float)[order]
    return lambda q: 1.0 / (np.asarray(q, float) * np.interp(q, px, rx))


def simulate_coupons(df: pd.DataFrame, pcol: str, hitcol: str, odds_fn, k: int, thr: float,
                     date_col: str = "MatchDate") -> dict | None:
    """Her gün P'si ≥ thr olan bacakları P'ye göre sırala, k'lı ayrık kuponlara böl (maç başı tek bacak).

    Dönen: kupon sayısı, çarpım tahmini, gerçek tutma, ortalama oran, sentetik ROI ve standart hatası.
    """
    rows = []
    for _, g in df.groupby(date_col):
        g = g[g[pcol] >= thr].sort_values(pcol, ascending=False)
        for i in range(0, len(g) - k + 1, k):
            c = g.iloc[i:i + k]
            p = c[pcol].to_numpy(float)
            rows.append((float(np.prod(p)), int(c[hitcol].astype(bool).all()), float(np.prod(odds_fn(p)))))
    if not rows:
        return None
    c = pd.DataFrame(rows, columns=["pp", "hit", "odds"])
    roi = c.hit * c.odds - 1
    n, hits = len(c), int(c.hit.sum())
    lo, hi = wilson(hits, n)
    return {"k": k, "thr": thr, "n": n, "tahmin": round(float(c.pp.mean()), 4), "gercek": round(hits / n, 4),
            "gercek_ga": [round(lo, 4), round(hi, 4)], "ort_oran": round(float(c.odds.mean()), 2),
            "roi": round(float(roi.mean()), 3), "roi_se": round(float(roi.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan"), 3)}
