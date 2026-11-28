"""GFI öncüllerinin 18–28 Kas denetim seçimlerine etkisi (zaman sızıntısız).

Her seçim günü için GFI tabloları YALNIZ o günden önceki maçlardan yeniden kurulur (scripts/gfi_turet.py fonksiyonları,
asof). Önce = seçimin kendi P'si; sonra = 0.6·P + 0.4·GFI öncülü (league_halves.MODEL_WEIGHT). Ölçüler: log-loss,
Brier, kalibrasyon. Sonucu belirsiz (won=None) ya da P'si olmayan satırlar dışarıda.

    python scripts/gfi_etki_olcumu.py --dir /workspace/gfi_import \
        --rows tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json --sonuc /workspace/fd_denetim_2026-11-28/sonuc
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import gfi_turet as gt

from quantfoot.markets import gfi_priors as gp
from quantfoot.markets import league_halves as lh

W = lh.MODEL_WEIGHT


def _ll(p: float, y: bool) -> float:
    p = min(max(p, 1e-3), 1 - 1e-3)
    return -math.log(p if y else 1 - p)


def metrics(df: pd.DataFrame, col: str) -> dict:
    if df.empty:
        return {"n": 0}
    y = df.won.astype(float)
    return {"n": len(df), "logloss": round(sum(_ll(p, w) for p, w in zip(df[col], df.won)) / len(df), 4),
            "brier": round(float(((df[col] - y) ** 2).mean()), 4), "ort_p": round(float(df[col].mean()), 3),
            "isabet": round(float(y.mean()), 3)}


def calib(df: pd.DataFrame, col: str) -> list[dict]:
    out = []
    for lo, hi in ((0, 0.6), (0.6, 0.65), (0.65, 0.7), (0.7, 0.75), (0.75, 0.8), (0.8, 1.01)):
        x = df[(df[col] >= lo) & (df[col] < hi)]
        if len(x):
            out.append({"kova": f"{lo:.2f}-{min(hi, 1):.2f}", "n": len(x), "ort_p": round(float(x[col].mean()), 3),
                        "gercek": round(float(x.won.mean()), 3)})
    return out


def _s(d: dict) -> dict:
    return {k: ("" if pd.isna(v) else str(v)) for k, v in d.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", type=Path, default=gt.DEFAULT_DIR)
    ap.add_argument("--rows", type=Path, default=ROOT / "tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json")
    ap.add_argument("--sonuc", type=Path, default=Path("/workspace/fd_denetim_2026-11-28/sonuc"))
    ap.add_argument("--out", type=Path, default=ROOT / "reports/research/gfi_etki_2026-11-28.json")
    args = ap.parse_args()
    info = {}
    for f in sorted(glob.glob(str(args.sonuc / "unlive_*.json"))):
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["d"]:
            info[m["C"]] = m
    rows = [r for r in json.loads(args.rows.read_text(encoding="utf-8"))
            if r.get("won") is not None and r.get("p") is not None and r.get("kod") in info]
    df, wg, _ = gt.load(args.dir)
    wm = pd.read_csv(args.dir / "wi_matches.csv.gz")
    import datalake_lig as dl

    dl_rows = dl.table()
    out = []
    for day in sorted({r["tarih"] for r in rows}):
        table = {r["lig"]: _s(r) for r in gt.league_table(df, day).to_dict("records")}
        forms: dict = {}
        for r in gt.team_form(df, day).to_dict("records"):
            forms.setdefault(r["lig"], []).append(_s(r))
        minutes = {r["lig"]: _s(r) for r in gt.minute_table(wm, wg, day).to_dict("records")}
        for r in (x for x in rows if x["tarih"] == day):
            m = info[r["kod"]]
            lig, home, away = m["L"], m["HT"], m["AT"]
            pl = gp.prior_probability(r["secim"], lig, home, away, asof=day, use_form=False, table=table, minutes=minutes)
            if pl is None:
                continue
            pf = gp.prior_probability(r["secim"], lig, home, away, asof=day, use_form=True, table=table, forms=forms,
                                      minutes=minutes)
            covered = bool(lh._rows(lig)) or bool(dl.league_rates(lig, dl_rows))
            out.append({"tarih": day, "lig": lig, "secim": r["secim"], "aile": r["aile"], "won": bool(r["won"]),
                        "p": float(r["p"]), "prior_lig": pl[0], "prior_form": pf[0] if pf else pl[0],
                        "form_var": bool(pf and "formu" in pf[1]), "yeni_lig": not covered})
    ev = pd.DataFrame(out)
    ev["p_lig"] = W * ev.p + (1 - W) * ev.prior_lig
    ev["p_form"] = W * ev.p + (1 - W) * ev.prior_form
    # yalnız gol-toplamı aileleri (Alt/Üst, İY Alt/Üst, KG); diğerleri değişmez. Aynı veride seçildi -> örneklem içi
    gol = ev.aile.isin(["Alt/Üst", "İY Alt/Üst", "KG"])
    ev["p_lig_gol"] = ev.p.where(~gol, ev.p_lig)
    ev["p_lig_w08"] = 0.8 * ev.p + 0.2 * ev.prior_lig
    res = {"toplam_secim": len(rows), "gfi_onculu": len(ev), "yeni_lig_ligleri": sorted(set(ev[ev.yeni_lig].lig))}
    for name, sub in (("hepsi", ev), ("yeni_lig", ev[ev.yeni_lig]), ("kapsanan_lig", ev[~ev.yeni_lig]),
                      ("form_var", ev[ev.form_var]), ("P>=0.70", ev[ev.p >= 0.70])):
        res[name] = {c: metrics(sub, c) for c in ("p", "p_lig", "p_form", "p_lig_gol", "p_lig_w08")}
    res["aile"] = {a: {c: metrics(g, c) for c in ("p", "p_lig")} for a, g in ev.groupby("aile") if len(g) >= 20}
    res["gol_aileleri_yeni_lig"] = {c: metrics(ev[gol & ev.yeni_lig], c) for c in ("p", "p_lig")}
    res["kalibrasyon"] = {c: calib(ev, c) for c in ("p", "p_lig")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {c: (v[c]["logloss"], v[c]["brier"]) for c in v} for k, v in res.items()
                      if k in ("hepsi", "yeni_lig", "kapsanan_lig", "form_var", "P>=0.70", "gol_aileleri_yeni_lig")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
