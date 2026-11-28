#!/usr/bin/env python3
"""Yüksek oran katmanı için aday ek pazarların ileri-yürüyen değerlendirmesi (rapor; katmana pazar eklemez).

    python scripts/yuksek_oran_yeni_pazar.py --cache /workspace/yo_cache

Çıktı: reports/research/yuksek_oran_yeni_pazar_<tarih>.{md,json}. Ölçüt ve gerekçe:
src/quantfoot/evaluation/yuksek_oran_yeni_pazar.py. Hiperparametreler data/calibration/yuksek_oran_kalibrasyon.json'dan.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation import yuksek_oran_backtest as bt  # noqa: E402
from quantfoot.evaluation import yuksek_oran_yeni_pazar as yn  # noqa: E402


def _features(cache: str, half_life: float) -> pd.DataFrame:
    p = Path(cache) / f"feat_{int(half_life)}.pkl" if cache else None
    if p and p.exists():
        return pd.read_pickle(p)
    f = bt.add_market_lambdas(bt.build_features(bt.load_matches(), bt.FeatureConfig(half_life=half_life)))
    if p:
        p.parent.mkdir(parents=True, exist_ok=True)
        f.to_pickle(p)
    return f


def _md(res: dict, keep: list[str], why: dict[str, str], last: str) -> str:
    L = [f"# Yüksek oran katmanı: aday ek pazarlar — ileri-yürüyen değerlendirme ({date.today()})", "",
         f"- Veri: data/matches.csv, son maç {last}. Pazar oranı arşivde yok → olasılık kalitesi (log-loss, ECE) ölçüldü, ROI ölçülmedi.",
         "- **piyasa türevi** = 1X2 + 2.5 Alt/Üst'ten ters çevrilmiş λ,μ; sabit %44,4 İY payı; bağımsız yarılar. **sonra** = mevcut yeni model "
         "(harman λ, lig İY payı, devre-arası durum çarpanı, aylık geçmişle kalibrasyon). **sonra_ham** = kalibrasyonsuz.",
         f"- Karar: doğrulamada t ≤ {yn.VAL_T:g}, testte t ≤ {yn.TEST_T:g} (log-loss farkı < 0) ve test ECE'si kıyastan kötü değil.",
         f"- **Eklenen:** {', '.join(keep) if keep else 'yok'}.",
         "- Nesine'nin sunmadığı pazar (2. yarı skoru) değerlendirilmedi. İY/MS'nin dokuz hücresi zaten katmanda.", "",
         "| Pazar | Dönem | n | log-loss piyasa | sonra_ham | sonra | sonra−piyasa (t) | ham−piyasa (t) | ECE piyasa → sonra |",
         "|---|---|---|---|---|---|---|---|---|"]
    for key, per in res.items():
        for pn, r in per.items():
            ll, d, h, e = r["logloss"], r["sonra_vs_piyasa"], r["ham_vs_piyasa"], r["ece"]
            L.append(f"| {yn.MARKETS[key]} | {pn} | {r['n']} | {ll['piyasa']:.4f} | {ll['sonra_ham']:.4f} | {ll['sonra']:.4f} | "
                     f"{d['fark']:+.5f} ({d['t']}) | {h['fark']:+.5f} ({h['t']}) | {e['piyasa']:.5f} → {e['sonra']:.5f} |")
    L += ["", "## Elenme gerekçeleri", ""] + [f"- {yn.MARKETS[k]}: {v}" for k, v in why.items()]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default="")
    ap.add_argument("--cal-from", default="2021-09-01")
    args = ap.parse_args()
    hp = json.loads((ROOT / "data/calibration/yuksek_oran_kalibrasyon.json").read_text(encoding="utf-8"))["hiperparametre"]
    cfg = bt.ProbConfig(w_market=hp["w_market"], gamma_team=hp["gamma_team"], rho_iy=hp["rho_iy"], rho_2y=hp["rho_2y"], rho_ms=0.0)
    f = _features(args.cache, hp["half_life"])
    f = f[(f.lam_p.notna() | f.lam_m.notna()) & (f.MatchDate >= "2021-07-01")].reset_index(drop=True)
    y = yn.outcomes_extra(f)
    mh, ma, _ = bt.game_state_multipliers(f, cfg)
    pm = yn.model_markets(f, cfg, "piyasa")
    ham = yn.model_markets(f, cfg, "sonra", (mh, ma))
    son, _ = yn.walk_forward_calibrate_extra(f, ham, y, args.cal_from)
    res = yn.compare(f, y, pm, son, ham)
    keep, why = yn.decide(res)
    last = str(f.MatchDate.max().date())
    out = ROOT / "reports" / "research"
    stamp = str(date.today())
    (out / f"yuksek_oran_yeni_pazar_{stamp}.json").write_text(
        json.dumps({"tarih": stamp, "son_mac": last, "eklenen": keep, "elenen": why, "sonuc": res}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    (out / f"yuksek_oran_yeni_pazar_{stamp}.md").write_text(_md(res, keep, why, last), encoding="utf-8")
    print("eklenen:", keep or "yok")
    for k, v in why.items():
        print(f"  elendi {k}: {v}")


if __name__ == "__main__":
    main()
