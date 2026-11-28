#!/usr/bin/env python3
"""Banko P ≥ 0,70 bandı hâlâ tutuyor mu? Son sonuçlarla kalibrasyon kontrolü (kural onarımı, 28 Kas 2026).

İki bağımsız kanıt:

A. **Pazar (arşiv):** data/matches.csv kapanış 1X2 ve 2,5 Alt/Üst oranlarından marjı orantılı atılmış P. Her bantta
   ortalama P ile gerçekleşen isabet karşılaştırılır. Varsayılan pencere: bu sezon (2026-07-01 →); kıyas: 2021-07-01 →.
B. **Yapay zekâ bacakları:** sürüm denetimindeki (tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json)
   sonucu Nesine'den doğrulanmış seçimler; P bandına ve kurala uygunluğa göre isabet.

    python scripts/banko_bant_kontrol.py [--json reports/research/banko_bant_kontrol.json]

Bu bir rapor betiğidir; kupon kurallarını değiştirmez.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "matches.csv"
AI_ROWS = ROOT / "tahminler" / "grokbottahmin" / "2026-11-28" / "surum_denetimi" / "rows.json"
BANDS = ((0.60, 0.65), (0.65, 0.70), (0.70, 0.75), (0.75, 0.80), (0.80, 0.85), (0.85, 1.01))


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 4), round(c + h, 4))


def _band_table(p: pd.Series, won: pd.Series) -> list[dict]:
    out = []
    for lo, hi in BANDS:
        m = (p >= lo) & (p < hi)
        n = int(m.sum())
        k = int(won[m].sum())
        out.append({"bant": f"{lo:.2f}-{min(hi, 1.0):.2f}", "n": n, "ort_p": round(float(p[m].mean()), 4) if n else None,
                    "isabet": round(k / n, 4) if n else None, "ci95": _wilson(k, n),
                    "fark": round(k / n - float(p[m].mean()), 4) if n else None})
    m = p >= 0.70
    n = int(m.sum())
    k = int(won[m].sum())
    out.append({"bant": "≥0.70 (toplam)", "n": n, "ort_p": round(float(p[m].mean()), 4) if n else None,
                "isabet": round(k / n, 4) if n else None, "ci95": _wilson(k, n),
                "fark": round(k / n - float(p[m].mean()), 4) if n else None})
    return out


def market_check(archive: Path = ARCHIVE, since: str = "2026-07-01") -> dict:
    d = pd.read_csv(archive, low_memory=False,
                    usecols=["Division", "MatchDate", "FTHome", "FTAway", "OddHome", "OddDraw", "OddAway", "Over25", "Under25"])
    d = d[d["MatchDate"].astype(str) >= since].dropna(subset=["FTHome", "FTAway"])
    res: dict = {"pencere": since, "mac": len(d)}
    x = d.dropna(subset=["OddHome", "OddDraw", "OddAway"])
    x = x[(x[["OddHome", "OddDraw", "OddAway"]] > 1.0).all(axis=1)]
    inv = 1 / x[["OddHome", "OddDraw", "OddAway"]]
    pr = inv.div(inv.sum(axis=1), axis=0)
    p = pd.concat([pr["OddHome"], pr["OddAway"]], ignore_index=True)
    won = pd.concat([(x["FTHome"] > x["FTAway"]), (x["FTAway"] > x["FTHome"])], ignore_index=True).astype(int)
    res["ms_1_2"] = _band_table(p, won)
    y = d.dropna(subset=["Over25", "Under25"])
    y = y[(y[["Over25", "Under25"]] > 1.0).all(axis=1)]
    inv = 1 / y[["Over25", "Under25"]]
    pr = inv.div(inv.sum(axis=1), axis=0)
    tot = y["FTHome"] + y["FTAway"]
    p = pd.concat([pr["Over25"], pr["Under25"]], ignore_index=True)
    won = pd.concat([(tot > 2.5), (tot < 2.5)], ignore_index=True).astype(int)
    res["alt_ust_25"] = _band_table(p, won)
    return res


def ai_check(rows_path: Path = AI_ROWS) -> dict | None:
    if not rows_path.exists():
        return None
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    df = pd.DataFrame(rows)
    df = df[df["p"].notna() & df["won"].notna()].copy()
    df["p"] = df["p"].astype(float)
    df["won"] = df["won"].astype(bool).astype(int)
    hard = ("yasak_aile", "beraberlik", "oran>", "oran<")  # denetim etiketleri (P bandı ihlalleri hariç)
    df["kurala_uygun"] = df["ihlal"].apply(lambda v: not any(str(x).startswith(hard) for x in (v or [])))
    out = {"secim": len(df), "hepsi": _band_table(df["p"], df["won"])}
    k = df[df["kurala_uygun"]]
    out["kurala_uygun_aile_oran"] = _band_table(k["p"], k["won"])
    out["yeni_surum"] = _band_table(df[df["surum"].astype(str).str.startswith("yeni")]["p"],
                                    df[df["surum"].astype(str).str.startswith("yeni")]["won"])
    return out


def to_md(rep: dict) -> str:
    def tbl(rows: list[dict]) -> list[str]:
        lines = ["| Bant | n | Ort. P | İsabet | %95 GA | Fark |", "|---|---|---|---|---|---|"]
        for r in rows:
            if not r["n"]:
                continue
            lines.append(f"| {r['bant']} | {r['n']} | {r['ort_p']:.3f} | {r['isabet']:.3f} | {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f} | {r['fark']:+.3f} |")
        return lines
    L = ["# Banko P ≥ 0,70 bant kontrolü", ""]
    for m in rep["pazar"].values():
        L += [f"## A. Pazar — {m['pencere']} → ({m['mac']} maç)", "", "### MS 1 / MS 2 (marjsız kapanış P)", *tbl(m["ms_1_2"]),
              "", "### 2,5 Alt / Üst", *tbl(m["alt_ust_25"]), ""]
    if rep.get("ai"):
        a = rep["ai"]
        L += [f"## B. Yapay zekâ seçimleri ({a['secim']} sonuçlu seçim, 18–28 Kas)", "", "### Hepsi", *tbl(a["hepsi"]), "",
              "### Yasak aile/oran ihlali olmayanlar", *tbl(a["kurala_uygun_aile_oran"]), "",
              "### Yeni sürüm (≥23 Kas)", *tbl(a["yeni_surum"]), ""]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json")
    ap.add_argument("--md")
    a = ap.parse_args()
    rep = {"pazar": {"bu_sezon": market_check(since="2026-07-01"), "son_5_sezon": market_check(since="2021-07-01")},
           "ai": ai_check()}
    md = to_md(rep)
    print(md)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
