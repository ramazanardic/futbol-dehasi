"""Son-120-gün form havuzunun kapsamı ve 18–28 Kas denetim seçimlerine etkisi (zaman sızıntısız).

Her seçim için form YALNIZ seçim gününden önceki maçlardan okunur (recent_form.team_form asof). Önce = seçimin P'si;
sonra = 0.6·P + 0.4·öncül (öncül: form lambdaları + bağımsız yarı-Poisson, gfi_priors.selection_probability).

    python scripts/kaynak_etki_olcumu.py --havuz /workspace/fd_kaynak_2026-11-28
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
from quantfoot.data import recent_form as rf
from quantfoot.markets import gfi_priors as gp
from quantfoot.markets import league_halves as lh

W = lh.MODEL_WEIGHT
GOAL = gp.GOAL_FAMILY


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


def paired_bootstrap(df: pd.DataFrame, a: str, b: str, n: int = 2000, seed: int = 7) -> dict:
    """b - a log-loss farkı (negatif = b daha iyi) için eşleştirilmiş bootstrap %95 aralığı; maç kümesi (tarih+lig) yeniden örneklenir."""
    import numpy as np

    d = pd.Series([_ll(pb, w) - _ll(pa, w) for pa, pb, w in zip(df[a], df[b], df.won)], index=df.index)
    g = (df.tarih + "|" + df.lig).values
    keys = pd.unique(g)
    sums = {k: d[g == k].sum() for k in keys}
    cnt = {k: int((g == k).sum()) for k in keys}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        pick = rng.choice(len(keys), len(keys))
        out.append(sum(sums[keys[i]] for i in pick) / sum(cnt[keys[i]] for i in pick))
    return {"n": len(df), "fark": round(float(d.mean()), 4), "ci95": [round(float(np.percentile(out, 2.5)), 4), round(float(np.percentile(out, 97.5)), 4)]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--havuz", type=Path, default=Path("/workspace/fd_kaynak_2026-11-28"))
    ap.add_argument("--rows", type=Path, default=ROOT / "tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json")
    ap.add_argument("--sonuc", type=Path, default=Path("/workspace/fd_denetim_2026-11-28/sonuc"))
    ap.add_argument("--out", type=Path, default=ROOT / "reports/research/kaynak_etki_2026-11-28.json")
    a = ap.parse_args()
    pool = rf.load_pool({"espn": a.havuz / "espn_gunler", "openmatchday": a.havuz / "openmatchday", "nesine": a.havuz / "nesine"})
    predict, n_fit = rf.fit_shot_xg()
    n_xg = rf.attach_xg_proxy(pool, predict)
    idx = rf.build_index(pool)
    info = {}
    for f in sorted(glob.glob(str(a.sonuc / "unlive_*.json"))):
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["d"]:
            info[m["C"]] = m
    rows = [r for r in json.loads(a.rows.read_text(encoding="utf-8")) if r.get("kod") in info]
    cache: dict = {}
    cov: dict = {}
    out = []
    means_by_day: dict = {}
    for r in rows:
        m = info[r["kod"]]
        day = r["tarih"]
        means = means_by_day.setdefault(day, rf.pool_means(pool, day))
        kh, ka = rf.resolve_team(m["HT"], idx, cache), rf.resolve_team(m["AT"], idx, cache)
        fh = rf.team_form(kh, idx, day) if kh else None
        fa = rf.team_form(ka, idx, day) if ka else None
        key = (day, r["kod"])
        if key not in cov:
            both = bool(fh and fa)
            srcs = sorted(set((fh or {}).get("kaynaklar", [])) | set((fa or {}).get("kaynaklar", []))) if both else []
            cov[key] = {"lig": m["L"], "form_iki_takim": both, "kaynak": "+".join(srcs)}
        if r.get("won") is None or r.get("p") is None:
            continue
        lam = rf.lambdas(m["HT"], m["AT"], idx, day, means, cache)
        if lam is None:
            continue
        share = gp.first_half_share(m["L"])
        pr = gp.selection_probability(r["secim"], lam[0], lam[1], share)
        if pr is None:
            continue
        lx = rf.lambdas(m["HT"], m["AT"], idx, day, means, cache, use_xg=True)
        prx = gp.selection_probability(r["secim"], lx[0], lx[1], share)
        xg_n = min(rf.team_form(kh, idx, day)["n_xg"], rf.team_form(ka, idx, day)["n_xg"])
        out.append({"tarih": day, "lig": m["L"], "aile": r["aile"], "secim": r["secim"], "won": bool(r["won"]), "p": float(r["p"]),
                    "prior": pr, "prior_xg": prx, "xg_n": xg_n, "kaynak": "+".join(lam[2]["kaynak"]), "min_n": min(lam[2]["n_ev"], lam[2]["n_dep"])})
    ev = pd.DataFrame(out)
    ev["p_form"] = W * ev.p + (1 - W) * ev.prior
    ev["p_xg"] = W * ev.p + (1 - W) * ev.prior_xg
    ev["p_form08"] = 0.8 * ev.p + 0.2 * ev.prior
    gol = ev.secim.map(lambda s: bool(GOAL.match(s)))
    ev["p_form_gol"] = ev.p.where(~gol, ev.p_form)
    ev["p_xg_gol"] = ev.p.where(~gol, ev.p_xg)
    cv = pd.DataFrame(cov.values())
    res = {"toplam_mac": len(cv), "form_iki_takim_var": int(cv.form_iki_takim.sum()),
           "form_orani": round(float(cv.form_iki_takim.mean()), 3),
           "kaynak_dagilimi": cv[cv.form_iki_takim].kaynak.value_counts().to_dict(),
           "formsuz_ligler": cv[~cv.form_iki_takim].lig.value_counts().head(25).to_dict(),
           "xg_vekili_egitim_mac": n_fit, "xg_vekili_havuz_mac": n_xg, "toplam_secim": len(rows), "form_onculu_secim": len(ev)}
    for name, sub in (("hepsi", ev), ("gol_aileleri", ev[gol]), ("P>=0.70", ev[ev.p >= 0.70]),
                      ("min_n>=6", ev[ev.min_n >= 6]), ("yalniz_nesine_openmatchday", ev[~ev.kaynak.str.contains("espn")]),
                      ("xg_vekili_var(n>=3)", ev[ev.xg_n >= 3])):
        res[name] = {c: metrics(sub, c) for c in ("p", "p_form", "p_xg", "p_form08", "p_form_gol", "p_xg_gol")}
    res["bootstrap_gol_logloss_farki"] = paired_bootstrap(ev[gol], "p", "p_form")
    res["bootstrap_xg_gol_logloss_farki"] = paired_bootstrap(ev[gol & (ev.xg_n >= 3)], "p_form", "p_xg")
    res["bootstrap_p070_gol_logloss_farki"] = paired_bootstrap(ev[gol & (ev.p >= 0.70)], "p", "p_form")
    res["aile"] = {k: {c: metrics(g, c) for c in ("p", "p_form")} for k, g in ev.groupby("aile") if len(g) >= 20}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "aile"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
