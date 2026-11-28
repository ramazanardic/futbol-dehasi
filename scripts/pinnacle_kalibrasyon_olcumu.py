#!/usr/bin/env python3
"""Üretim türev kalibrasyonu (market_calibration.json) Pinnacle fiyatlı girdilerde doğru mu? — 28 Kas post-mortem testi.

Canlı motor olasılıkları keskin referanstan (OddsMath/Pinnacle) türetir; arşiv Platt eğrileri ise ortalama büro
oranlarıyla (OddHome/Over25) fiyatlanmış arşivde kuruldu. Bu betik aynı üretim hattını Pinnacle KAPANIŞ 1X2 + 2.5
oranlarıyla fiyatlar (``QF_AILE_VARYANT=pinnacle bahis_aileleri_kalibrasyon.py onbellek``) ve her kalibre edilen seçim
için test sezonlarında (2021/22+) karşılaştırır:

* ham      : Pinnacle-fiyatlı üretim türevi (kalibrasyonsuz)
* uretim   : ham + mevcut market_calibration.json eğrisi (üretimde uygulanan) — bu eğri test sezonlarını da görmüştür
* wf       : yalnız ÖNCEKİ Pinnacle sezonlarıyla kurulan Platt (+lig sapması) — sızıntısız

    QF_AILE_VARYANT=pinnacle python scripts/bahis_aileleri_kalibrasyon.py onbellek
    python scripts/pinnacle_kalibrasyon_olcumu.py [--yaz]   # -> reports/research/pinnacle_kalibrasyon_olcumu.json

İkinci bölüm: eğrisi OLMAYAN türev seçimler için aynı sızıntısız kural (``bahis_aileleri_kalibrasyon._wf_one``: test
log-loss farkının %95 bootstrap GA üst ucu < 0) Pinnacle verisinde çalıştırılır. ``--yaz`` yalnız bu kuralı geçen ve
banko bölgesinde (0,65–0,80) kalibrasyonu kötüleştirmeyen YENİ seçimleri market_calibration.json'a ekler; mevcut
eğrilere dokunmaz.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("QF_AILE_VARYANT", "pinnacle")

import bahis_aileleri_kalibrasyon as BA  # noqa: E402
from quantfoot.markets.market_calibration import _complement_key, apply_platt_league, fit_platt_league  # noqa: E402

FIRST_TEST = 2021
OUT = ROOT / "reports" / "research" / "pinnacle_kalibrasyon_olcumu"


def banko(p: np.ndarray, y: np.ndarray, lo: float = 0.70, hi: float = 0.80) -> dict:
    """Banko bölgesi (her iki taraf: seçim ve tümleyeni) tahmin/gerçek."""
    out = {}
    for side, pp, yy in (("secim", p, y), ("tumleyen", 1 - p, 1 - y)):
        m = (pp >= lo) & (pp < hi)
        n = int(m.sum())
        if n >= 50:
            e, o = float(pp[m].mean()), float(yy[m].mean())
            out[side] = {"n": n, "tahmin": round(e, 4), "gercek": round(o, 4), "fark": round(o - e, 4),
                         "z": round((o - e) / np.sqrt(e * (1 - e) / n), 2)}
    return out


def wf_predict(p: np.ndarray, y: np.ndarray, div: np.ndarray, season: np.ndarray, league: bool) -> np.ndarray:
    out = np.full_like(p, np.nan)
    for s in sorted(np.unique(season[season >= FIRST_TEST])):
        tr, te = season < s, season == s
        if tr.sum() < 2000 or te.sum() == 0:
            continue
        g = fit_platt_league(p[tr], y[tr], div[tr], league_l2=200.0 if league else None)
        out[te] = np.clip(apply_platt_league(g, p[te], div[te] if league else None), 0.01, 0.99)
    return out


def banko_ok(raw: dict, cal: dict) -> bool:
    """Banko bölgesinde |fark| büyümüyor (iki taraf, 0,70–0,80)."""
    for side in ("secim", "tumleyen"):
        if side in cal and side in raw and abs(cal[side]["fark"]) > abs(raw[side]["fark"]) + 0.005:
            return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yaz", action="store_true", help="kuralı geçen YENİ seçimleri market_calibration.json'a ekle")
    args = ap.parse_args()
    z = BA._load("pinnacle")
    cal = json.loads(BA.CAL_FILE.read_text(encoding="utf-8"))["markets"]
    P, Y, sel, div, season = z["P"].astype(float), z["Y"].astype(float), list(z["sel"]), z["div"], z["season"]
    test = season >= FIRST_TEST
    rows = []
    for name, params in cal.items():
        if name not in sel or name in BA.DIRECT:
            continue
        k = sel.index(name)
        p, y = np.clip(P[:, k], 1e-4, 1 - 1e-4), Y[:, k]
        cur = np.clip(apply_platt_league(params, p, div), 0.01, 0.99)
        wf = np.full_like(p, np.nan)
        for s in sorted(np.unique(season[test])):
            tr, te = season < s, season == s
            if tr.sum() < 2000 or te.sum() == 0:
                continue
            g = fit_platt_league(p[tr], y[tr], div[tr], league_l2=200.0)
            wf[te] = np.clip(apply_platt_league(g, p[te], div[te]), 0.01, 0.99)
        m = test & np.isfinite(wf)
        l_raw, l_cur, l_wf = BA.ll_vec(p[m], y[m]), BA.ll_vec(cur[m], y[m]), BA.ll_vec(wf[m], y[m])
        d_cur, d_wf = l_cur - l_raw, l_wf - l_cur
        rows.append({
            "secim": name, "n_test": int(m.sum()), "gercek": round(float(y[m].mean()), 4),
            "ort_ham": round(float(p[m].mean()), 4), "ort_uretim": round(float(cur[m].mean()), 4),
            "ll_ham": round(float(l_raw.mean()), 5), "ll_uretim": round(float(l_cur.mean()), 5), "ll_wf": round(float(l_wf.mean()), 5),
            "uretim_eksi_ham": round(float(d_cur.mean()), 6), "ci_uretim_eksi_ham": [round(c, 6) for c in BA.boot_ci(d_cur)],
            "wf_eksi_uretim": round(float(d_wf.mean()), 6), "ci_wf_eksi_uretim": [round(c, 6) for c in BA.boot_ci(d_wf)],
            "ece_ham": round(BA.ece(p[m], y[m]), 4), "ece_uretim": round(BA.ece(cur[m], y[m]), 4), "ece_wf": round(BA.ece(wf[m], y[m]), 4),
            "banko_ham": banko(p[m], y[m]), "banko_uretim": banko(cur[m], y[m]), "banko_wf": banko(wf[m], y[m]),
        })
    df = pd.DataFrame(rows).sort_values("uretim_eksi_ham")

    # 2) eğrisi olmayan türev seçimler: aynı sızıntısız tutma kuralı, Pinnacle verisinde
    BA.FIRST_TEST = FIRST_TEST
    new_rows, added = [], {}
    for k, name in enumerate(sel):
        comp = _complement_key(name)
        if name in cal or name in BA.DIRECT or (comp and comp in cal):
            continue
        p, y = np.clip(P[:, k], 1e-4, 1 - 1e-4), Y[:, k]
        r = BA._wf_one((name, p, y, div, season))
        row = {kk: r[kk] for kk in ("secim", "aile", "n", "gercek", "ort_tahmin", "d_platt", "ci_platt", "d_platt_lig",
                                     "ci_platt_lig", "ece_ham", "ece_platt", "ece_platt_lig", "tutulan")}
        if r["tutulan"]:
            wf = wf_predict(p, y, div, season, r["tutulan"] == "platt_lig")
            m = test & np.isfinite(wf)
            row["banko_ham"], row["banko_wf"] = banko(p[m], y[m]), banko(wf[m], y[m])
            row["banko_iyi"] = banko_ok(row["banko_ham"], row["banko_wf"])
            if row["banko_iyi"]:
                curve = dict(r["egri"])
                curve.update({"direct_in_production": False, "aile": r["aile"], "kaynak": "pinnacle_kalibrasyon_olcumu.py",
                              "fiyat": "Pinnacle kapanış 1X2 + 2.5 (2019/20+)",
                              "oos_ll_fark": r["d_platt_lig" if r["tutulan"] == "platt_lig" else "d_platt"],
                              "oos_ci95": r["ci_platt_lig" if r["tutulan"] == "platt_lig" else "ci_platt"]})
                added[name] = curve
        new_rows.append(row)
    if args.yaz and added:
        full = json.loads(BA.CAL_FILE.read_text(encoding="utf-8"))
        for name, curve in added.items():
            full["markets"].setdefault(name, curve)
        BA.CAL_FILE.write_text(json.dumps(full, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("market_calibration.json'a eklenen:", ", ".join(added))
    OUT.with_suffix(".json").write_text(json.dumps({"n_mac": int(len(P)), "test_mac": int(test.sum()),
                                                     "ilk_test_sezonu": FIRST_TEST, "mevcut_egriler": rows,
                                                     "yeni_adaylar": new_rows, "eklenen": sorted(added)},
                                                    ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    cols = ["secim", "n_test", "gercek", "ort_ham", "ort_uretim", "ll_ham", "ll_uretim", "ll_wf", "uretim_eksi_ham",
            "ci_uretim_eksi_ham", "wf_eksi_uretim", "ci_wf_eksi_uretim", "ece_ham", "ece_uretim", "ece_wf"]
    pd.set_option("display.width", 250)
    print(df[cols].to_string(index=False))
    print("\nYeni adaylar (kural geçen):")
    for r in new_rows:
        if r["tutulan"]:
            print(r["secim"], r["tutulan"], r["d_platt"], r["ci_platt"], "banko_iyi=", r.get("banko_iyi"),
                  r.get("banko_ham"), r.get("banko_wf"))


if __name__ == "__main__":
    main()
