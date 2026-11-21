"""Marj temizleme yöntemi karşılaştırması: repo (power) vs penaltyblog'un 7 yöntemi (MIT).

    python scripts/devig_karsilastirma.py     # → docs/research/devig_karsilastirma_2026_11_21.md

Uydurma parametre yok (yöntemler veri üzerinde eğitilmez), dolayısıyla her maç örneklem dışıdır.
Ölçü: 1X2 log-loss ve Brier; fark için maç bazlı eşleştirilmiş bootstrap %95 GA (power'a göre).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import penaltyblog as pb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.markets.devig import devig  # noqa: E402

METHODS = ["multiplicative", "additive", "power", "shin", "differential_margin_weighting", "odds_ratio", "logarithmic"]
RNG = np.random.default_rng(7)


def probs(odds: np.ndarray, method: str) -> np.ndarray:
    out = np.empty_like(odds)
    for i, o in enumerate(odds):
        if method == "power_repo":
            out[i] = devig(o, method="power").probabilities
        else:
            p = np.asarray(pb.implied.calculate_implied(list(o), method=method).probabilities, float)
            p = np.clip(p, 1e-6, None)
            out[i] = p / p.sum()
    return out


def evaluate(name: str, odds: np.ndarray, y: np.ndarray) -> dict:
    rows, ll = {}, {}
    for m in ["power_repo"] + METHODS:
        P = probs(odds, m)
        ll[m] = -np.log(np.clip(P[np.arange(len(y)), y], 1e-12, None))
        br = ((P - np.eye(3)[y]) ** 2).sum(1)
        rows[m] = {"logloss": float(ll[m].mean()), "brier": float(br.mean())}
    base = ll["power_repo"]
    for m in METHODS:
        d = ll[m] - base
        bs = [d[RNG.integers(0, len(d), len(d))].mean() for _ in range(1000)]
        rows[m]["d_vs_power"] = float(d.mean())
        rows[m]["ci"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    margin = float(np.median((1 / odds).sum(1) - 1))
    return {"name": name, "n": int(len(y)), "median_margin": margin, "rows": rows}


def main() -> None:
    res = []
    m = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False,
                    usecols=["MatchDate", "OddHome", "OddDraw", "OddAway", "FTResult"])
    m = m[m.MatchDate >= "2021-07-01"].dropna()
    o = m[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
    ok = (o > 1).all(1) & ((1 / o).sum(1) > 1.0)
    m, o = m[ok], o[ok]
    idx = RNG.choice(len(m), min(20000, len(m)), replace=False)
    y = m.FTResult.map({"H": 0, "D": 1, "A": 2}).to_numpy()[idx]
    res.append(evaluate("matches.csv ortalama piyasa oranı (2021-07+, 20.000 rastgele maç)", o[idx], y))
    t = pd.read_csv(ROOT / "data" / "tipsaudit.csv")
    t = t[t.result.isin(["1", "X", "2"])]
    yt = t.result.map({"1": 0, "X": 1, "2": 2}).to_numpy()
    for col, label in (("pin_close", "Pinnacle kapanış"), ("pin_open", "Pinnacle açılış")):
        oo = t[[f"{col}_home", f"{col}_draw", f"{col}_away"]].to_numpy(float)
        ok = np.isfinite(oo).all(1) & (oo > 1).all(1) & ((1 / oo).sum(1) > 1.0)
        res.append(evaluate(f"tipsaudit {label} (2026-06 – 2026-10)", oo[ok], yt[ok]))
    out = ROOT / "docs" / "research"
    (out / "devig_karsilastirma_2026_11_21.json").write_text(json.dumps(res, indent=1))
    md = ["# Marj temizleme yöntemi karşılaştırması (21 Kasım 2026)", "",
          "Repo varsayılanı `power` (markets/devig.py) ile penaltyblog 1.13 (MIT) yöntemleri. Fark = yöntem − power "
          "log-loss'u (negatif = daha iyi), eşleştirilmiş bootstrap %95 GA.", ""]
    for r in res:
        md += [f"## {r['name']} — {r['n']} maç, medyan marj {r['median_margin']:.1%}", "",
               "| Yöntem | Log-loss | Brier | Fark (power'a göre) | %95 GA |", "|---|---|---|---|---|"]
        md.append(f"| power (repo) | {r['rows']['power_repo']['logloss']:.5f} | {r['rows']['power_repo']['brier']:.5f} | — | — |")
        for k in METHODS:
            x = r["rows"][k]
            md.append(f"| {k} | {x['logloss']:.5f} | {x['brier']:.5f} | {x['d_vs_power']:+.5f} | {x['ci'][0]:+.5f} – {x['ci'][1]:+.5f} |")
        md.append("")
    (out / "devig_karsilastirma_2026_11_21.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
