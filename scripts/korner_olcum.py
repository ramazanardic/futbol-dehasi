#!/usr/bin/env python3
"""Toplam korner Alt/Üst ileri-yürüyen kalibrasyon ölçümü ve kalibrasyon dosyası (banko ailesi).

    python scripts/korner_olcum.py --cache /workspace/yo_cache      # özellik önbelleği (repo dışı) varsa kullanır

Çıktılar: data/calibration/korner_kalibrasyon.json, reports/research/korner_banko_<tarih>.{md,json}
Ölçüt: (çizgi, yön) için P ≥ 0,70 diliminde, doğrulama (2022-07..2024-07) ve test (2024-07+) dönemlerinin İKİSİNDE
n ≥ 300 maç ve gerçekleşme ≥ tahmin − 5 puan. Hiçbiri geçmezse ``etkin`` = false (korner banko kuponuna girmez).
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

from quantfoot.evaluation import korner_backtest as kb  # noqa: E402
from quantfoot.evaluation import yuksek_oran_backtest as bt  # noqa: E402


def _features(cache: str, half_life: float = 240.0) -> pd.DataFrame:
    p = Path(cache) / f"feat_{int(half_life)}.pkl" if cache else None
    if p and p.exists():
        return pd.read_pickle(p)
    df = bt.load_matches()
    f = bt.build_features(df, bt.FeatureConfig(half_life=half_life))
    if p:
        p.parent.mkdir(parents=True, exist_ok=True)
        f.to_pickle(p)
    return f


def _md(res: dict, good: list[str], why: dict[str, str], info: dict, etkin: bool, last: str) -> str:
    L = [f"# Toplam korner Alt/Üst — ileri-yürüyen kalibrasyon ({date.today()})", "",
         f"- Veri: data/matches.csv, son maç {last}. Korner oranı arşivde yok → yalnız kalibrasyon ölçüldü, ROI ölçülmedi.",
         f"- Son katsayılar: toplam ≈ {info['katsayi'][0]} + {info['katsayi'][1]}·beklenti, Var/Ort {info['var_ort']} (n={info['n_egitim']}).",
         f"- Ölçüt: P ≥ 0,70 diliminde iki dönemde n ≥ {kb.MIN_SLICE_N} maç ve gerçek ≥ tahmin − 5 puan.",
         f"- Sonuç: **{'ETKİN' if etkin else 'KAPALI'}**; geçerli seçimler: {', '.join(good) or 'yok'}.", "",
         "## Havuz (tüm çizgiler, P ≥ 0,70)", "", "| Dönem | n | tahmin | gerçek | fark |", "|---|---|---|---|---|"]
    for per, d in res["havuz"].items():
        s = d["tum_P>=0.70"]
        L.append(f"| {per} | {s['n']} | {s['tahmin']} | {s['gercek']} | {s['fark']:+.4f} |")
    L += ["", "## P bantları (havuz)", "", "| Dönem | Bant | n | tahmin | gerçek | fark |", "|---|---|---|---|---|---|"]
    for per, d in res["bantlar"].items():
        for band, s in d.items():
            if s["n"]:
                L.append(f"| {per} | {band} | {s['n']} | {s['tahmin']} | {s['gercek']} | {s['fark']:+.4f} |")
    L += ["", "## Seçim bazında (P ≥ 0,70)", "",
          "| Seçim | Dönem | n | tahmin | gerçek | fark | z | karar |", "|---|---|---|---|---|---|---|---|"]
    for name, per in res["secimler"].items():
        for pname, s in per.items():
            if s["n"]:
                L.append(f"| {name} | {pname} | {s['n']} | {s['tahmin']} | {s['gercek']} | {s['fark']:+.4f} | {s['z']} | "
                         f"{'geçerli' if name in good else 'elendi'} |")
    if why:
        L += ["", "## Elenenler ve gerekçe", ""] + [f"- {k}: {v}" for k, v in why.items() if any(s.get('n') for s in res['secimler'][k].values())]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default="", help="özellik önbellek klasörü (repo dışı)")
    ap.add_argument("--cal-from", default="2019-07-01")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    f = _features(args.cache)
    adj, vm, info = kb.walk_forward_totals(f, args.cal_from)
    res = kb.evaluate(f, adj, vm)
    good, why = kb.validated(res)
    etkin = bool(good)
    last = str(f.MatchDate.max().date())
    params = {"surum": 1, "uretim": str(date.today()), "son_mac": last, "etkin": etkin, "gecerli": good,
              "katsayi": info["katsayi"], "var_ort": info["var_ort"], "n_egitim": info["n_egitim"],
              "olcut": {"dilim_P": kb.SLICE_P, "min_n": kb.MIN_SLICE_N, "azami_eksik": kb.MAX_SHORTFALL,
                        "donemler": [list(p) for p in kb.PERIODS]},
              "elenen": why}
    print(json.dumps({k: params[k] for k in ("etkin", "gecerli", "katsayi", "var_ort")}, ensure_ascii=False))
    for per, d in res["havuz"].items():
        print(per, d)
    if args.no_write:
        return
    (ROOT / "data/calibration/korner_kalibrasyon.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    out = ROOT / "reports/research"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"korner_banko_{date.today()}.md").write_text(_md(res, good, why, info, etkin, last), encoding="utf-8")
    (out / f"korner_banko_{date.today()}.json").write_text(
        json.dumps({"parametreler": params, "olcum": res}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
