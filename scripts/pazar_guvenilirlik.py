"""Pazar güvenilirliği: her seçimin (iki yönüyle) kupon bölgesindeki (P %55–85) arşiv kalibrasyon artığı.

    python scripts/bahis_aileleri_kalibrasyon.py onbellek --isci 6   # önce arşivi üretim hattıyla fiyatla (önbellek)
    python scripts/pazar_guvenilirlik.py [--yaz]                      # analiz; --yaz → data/calibration/market_reliability.json

21 Kas gece hata analizi (reports/research/hata_analizi_21kasim.md): canlı günlerde pazar bazında sapmalar günden güne
tutarsız (iki gün arası korelasyon ≈ 0, Empirical-Bayes τ = 0) → canlı tek günden pazar düzeltmesi YOK. Kalıcı olup
olmadığı yalnız arşivde (115k maç, 22 lig) sınanır:

* P = üretim hattı türev olasılığı + üretimdeki arşiv Platt eğrisi (``market_calibration``; doğrudan fiyatlı 1X2/ÇŞ/2.5'e
  uygulanmaz) — yani düzeltme bu ikisinden SONRA kalan artıktır.
* Bölge: P ∈ [0.55, 0.85) — banko/risk bacaklarının yaşadığı yer. Uydurma sezonları 2016/17–2020/21, dokunulmamış test
  2021/22+. Artık "teyitli" sayılırsa (n ≥ 500, |artık| ≥ 2·sezonlar-arası SE, sezonların ≥ %75'inde aynı işaret)
  dosyaya yazılır; üretim değeri tüm test sezonlarından (2016/17+) kestirilir, sezonlar-arası SE kadar sıfıra büzülür.
* Arşivde sınanamayan pazarlar (İlk Gol, korner, kart, oyuncu …) ``untested`` — seçicide sıralama cezası alır.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.markets.market_calibration import apply_platt_league, load_market_calibration  # noqa: E402

OUT = ROOT / "data" / "calibration" / "market_reliability.json"
REPORT = ROOT / "reports" / "research" / "pazar_guvenilirlik.json"
LO, HI = 0.55, 0.85
FIT_SEASONS = range(2016, 2021)   # 2016/17 – 2020/21
TEST_FROM = 2021                  # 2021/22+ dokunulmamış
DIRECT = {"MS 1", "MS 0", "MS 2", "ÇŞ 1X", "ÇŞ 12", "ÇŞ X2", "2.5 Üst"}


def complement_name(s: str, all_sel: set[str]) -> str:
    for a, b in (("Üst", "Alt"), ("Var", "Yok"), ("Tek", "Çift")):
        if s.endswith(a):
            return s[: -len(a)] + b
    special = {"İY 0": "İY ÇŞ 12", "MS 0": "ÇŞ 12", "MS 1": "ÇŞ X2", "MS 2": "ÇŞ 1X"}
    c = special.get(s)
    if c and c not in all_sel:
        return c
    return f"DEĞİL({s})"


def stats(p: np.ndarray, y: np.ndarray, season: np.ndarray, seasons) -> dict:
    gaps, ns = [], []
    for s in seasons:
        m = season == s
        if m.sum() >= 30:
            gaps.append(float(y[m].mean() - p[m].mean()))
            ns.append(int(m.sum()))
    n = len(p)
    gap = float(y.mean() - p.mean()) if n else 0.0
    se = float(np.std(gaps, ddof=1) / np.sqrt(len(gaps))) if len(gaps) > 2 else float("nan")
    same = sum(np.sign(g) == np.sign(gap) for g in gaps) / len(gaps) if gaps else 0.0
    return {"n": n, "p": round(float(p.mean()), 4) if n else None, "hit": round(float(y.mean()), 4) if n else None,
            "gap": round(gap, 4), "se": round(se, 4) if np.isfinite(se) else None, "same_sign": round(float(same), 2),
            "n_seasons": len(gaps)}


def confirmed(st: dict, min_n: int = 500, z: float = 2.0, same: float = 0.75) -> bool:
    return bool(st["n"] >= min_n and st["se"] and abs(st["gap"]) >= z * st["se"] and st["same_sign"] >= same)


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaz", action="store_true", help="data/calibration/market_reliability.json yaz")
    args = ap.parse_args()
    import bahis_aileleri_kalibrasyon as BA

    z = BA._load("")
    P, Y, sel, div, season = z["P"].astype(float), z["Y"].astype(float), list(z["sel"]), z["div"], z["season"]
    cal = (load_market_calibration() or {}).get("markets") or {}
    all_sel = set(sel)
    rows, markets = [], {}
    agg = {"fit": [], "test_raw": [], "test_cor": []}
    fam_test: dict[str, list] = {}
    for i, s in enumerate(sel):
        p = P[:, i]
        if s in cal and s not in DIRECT:
            p = apply_platt_league(cal[s], p, list(div))
        for name, q, y in ((s, p, Y[:, i]), (complement_name(s, all_sel), 1 - p, 1 - Y[:, i])):
            if name in markets:
                continue
            reg = (q >= LO) & (q < HI) & (season >= 2016)
            if reg.sum() < 100:
                markets[name] = {"family": BA.FAMILY_OF.get(s, "?"), "tested": True, "n_region": int(reg.sum()), "correction": 0.0,
                                 "confirmed": False, "note": "bölgede yetersiz örnek"}
                continue
            fit = reg & np.isin(season, list(FIT_SEASONS))
            test = reg & (season >= TEST_FROM)
            st_fit = stats(q[fit], y[fit], season[fit], FIT_SEASONS)
            st_all = stats(q[reg], y[reg], season[reg], range(2016, 2027))
            ok_fit = confirmed(st_fit)
            corr_fit = st_fit["gap"] if ok_fit else 0.0
            qt, yt = q[test], y[test]
            r = {"name": name, "family": BA.FAMILY_OF.get(s, "?"), "fit": st_fit, "all": st_all, "confirmed_on_fit": ok_fit,
                 "test": {"n": int(test.sum()), "gap": round(float(yt.mean() - qt.mean()), 4) if test.any() else None,
                          "ll_raw": round(ll(qt, yt), 6) if test.any() else None,
                          "ll_cor": round(ll(np.clip(qt + corr_fit, 0.01, 0.99), yt), 6) if test.any() else None,
                          "brier_raw": round(float(np.mean((qt - yt) ** 2)), 6) if test.any() else None,
                          "brier_cor": round(float(np.mean((np.clip(qt + corr_fit, 0.01, 0.99) - yt) ** 2)), 6) if test.any() else None}}
            rows.append(r)
            if test.any():
                fam_test.setdefault(r["family"], []).append((qt, yt, corr_fit))
            ok_all = confirmed(st_all)
            # üretim: tüm sezonlardan, SE kadar sıfıra büzülmüş (aşırı uydurma payı)
            corr = 0.0
            if ok_all and ok_fit:
                corr = float(np.sign(st_all["gap"]) * max(0.0, abs(st_all["gap"]) - st_all["se"]))
            markets[name] = {"family": r["family"], "tested": True, "n_region": st_all["n"], "gap": st_all["gap"], "se": st_all["se"],
                             "same_sign": st_all["same_sign"], "confirmed": bool(ok_all and ok_fit), "correction": round(corr, 4)}
    fam_summary = {}
    for f, parts in fam_test.items():
        q = np.concatenate([a for a, _, _ in parts]); y = np.concatenate([b for _, b, _ in parts])
        qc = np.concatenate([np.clip(a + c, 0.01, 0.99) for a, _, c in parts])
        fam_summary[f] = {"n": int(len(q)), "gap_raw": round(float(y.mean() - q.mean()), 4), "gap_cor": round(float(y.mean() - qc.mean()), 4),
                          "ll_raw": round(ll(q, y), 6), "ll_cor": round(ll(qc, y), 6),
                          "brier_raw": round(float(np.mean((q - y) ** 2)), 6), "brier_cor": round(float(np.mean((qc - y) ** 2)), 6)}
    conf = [r for r in rows if r["confirmed_on_fit"]]
    print(f"{len(rows)} seçim yönü bölgede; uydurma sezonlarında teyitli: {len(conf)}")
    for r in sorted(conf, key=lambda r: r["fit"]["gap"]):
        t = r["test"]
        print(f"  {r['name']:32s} fit gap {r['fit']['gap']:+.4f}±{r['fit']['se']:.4f} ({r['fit']['same_sign']:.0%}) | "
              f"test n={t['n']} gap {t['gap']:+.4f} LL {t['ll_raw']:.5f}→{t['ll_cor']:.5f}")
    print("aile (test 2021/22+, bölge):")
    for f, v in sorted(fam_summary.items()):
        print(f"  {f:22s} n={v['n']:7d} artık {v['gap_raw']:+.4f}→{v['gap_cor']:+.4f} LL {v['ll_raw']:.5f}→{v['ll_cor']:.5f} "
              f"Brier {v['brier_raw']:.5f}→{v['brier_cor']:.5f}")
    report = {"region": [LO, HI], "fit_seasons": "2016/17–2020/21", "test_from": "2021/22", "rows": rows, "family_test": fam_summary}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    if args.yaz:
        out = {"version": 1, "built_by": "scripts/pazar_guvenilirlik.py",
               "doc": "reports/research/hata_analizi_21kasim.md",
               "applies_to": "türetilmiş seçimler, arşiv kalibrasyon alanındaki ligler; P ∈ [0.55, 0.85)",
               "region": [LO, HI], "markets": dict(sorted(markets.items()))}
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print("yazıldı:", OUT)


if __name__ == "__main__":
    main()
