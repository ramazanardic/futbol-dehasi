#!/usr/bin/env python3
"""21 Kas gece: notlanmış seçimlerin pazar bazında hata analizi (özel; yalnız toplamlar rapora girer)."""
from __future__ import annotations
import json, math, re, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

D = Path("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-21")
den = json.load(open(D / "denetim_gece_2026-11-21.json"))
deep = json.load(open(D / "derin_tahminler.json"))
glob = {m["code"]: m for m in json.load(open(D / "nesine_global.json"))["matches"]}

meta = {}
for m in deep:
    for f in m["families"]:
        for s in f["suitable"]:
            meta[(m["code"], s["name"])] = s

# steam: first vs last snapshot per (code, sel)
snap_first, snap_last = {}, {}
for line in open(D / "nesine_history.jsonl"):
    j = json.loads(line)
    for code, v in j["m"].items():
        for name, (o, p) in (v.get("s") or {}).items():
            k = (int(code), name)
            snap_first.setdefault(k, (j["ts"], p))
            snap_last[k] = (j["ts"], p)

rows = []
for r in den["rows"]:
    if r["kind"] != "final" or r["won"] is None:
        continue
    s = meta.get((r["code"], r["name"]), {})
    g = glob.get(r["code"], {})
    f1x2 = g.get("fair_1x2") or [snap_first.get((r["code"], n), (None, None))[1] for n in ("MS 1", "MS 0", "MS 2")]
    fav = max(f1x2) if all(isinstance(x, (int, float)) for x in f1x2) else None
    k = (r["code"], r["name"])
    steam = None
    if k in snap_first and snap_first[k][0] != snap_last[k][0]:
        steam = snap_last[k][1] - snap_first[k][1]
    rows.append(dict(r, direct=s.get("direct"), verdict=s.get("verdict"), fav=fav,
                     fav_side=(int(np.argmax(f1x2)) if fav else None),
                     mu_h=g.get("mu_home"), mu_a=g.get("mu_away"), steam=steam))
json.dump(rows, open("/tmp/hata_rows.json", "w"), ensure_ascii=False)
print("graded final rows", len(rows), "matches", len({r["code"] for r in rows}))


def stats(sub):
    p = np.array([x["p"] for x in sub], float); y = np.array([1.0 if x["won"] else 0.0 for x in sub])
    n = len(sub)
    if not n:
        return None
    pc = np.clip(p, 1e-4, 1 - 1e-4)
    ll = float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)))
    br = float(np.mean((p - y) ** 2))
    # binomial z of gap
    var = float(np.sum(p * (1 - p)))
    z = (y.sum() - p.sum()) / math.sqrt(var) if var > 0 else 0.0
    return dict(n=n, hit=round(float(y.mean()), 4), p=round(float(p.mean()), 4), gap=round(float(y.mean() - p.mean()), 4),
                brier=round(br, 4), ll=round(ll, 4), z=round(z, 2), odds=round(float(np.mean([x["odds"] for x in sub])), 2),
                roi=round(float(np.mean([(x["odds"] - 1) if x["won"] else -1 for x in sub])), 4),
                matches=len({x["code"] for x in sub}))


def table(key, sub=rows, minn=15, title=""):
    g = defaultdict(list)
    for x in sub:
        g[key(x)].append(x)
    out = {str(k): stats(v) for k, v in g.items() if len(v) >= minn}
    print(f"\n== {title} ==")
    for k, v in sorted(out.items(), key=lambda kv: kv[1]["z"]):
        print(f"{k[:34]:34s} n={v['n']:4d} hit={v['hit']:.3f} p={v['p']:.3f} gap={v['gap']:+.3f} z={v['z']:+.2f} br={v['brier']:.3f} roi={v['roi']:+.3f} o={v['odds']}")
    return out

def norm(name):
    return re.sub(r"\s+", " ", name.replace(",", "."))

res = {"overall": stats(rows), "headline": stats([x for x in rows if x["headline"]])}
res["by_name"] = table(lambda x: norm(x["name"]), title="seçim", minn=20)
res["by_family"] = table(lambda x: x["family"], title="aile", minn=10)
res["by_direct"] = table(lambda x: x["direct"], title="doğrudan", minn=10)
res["by_tier"] = table(lambda x: x["tier"], title="kademe", minn=10)
def oband(o): return "1.20-1.30" if o < 1.30 else "1.30-1.45" if o < 1.45 else "1.45-1.65" if o < 1.65 else "1.65+"
res["by_odds"] = table(lambda x: oband(x["odds"]), title="oran bandı", minn=10)
def pband(p): return "<.60" if p < .6 else ".60-.65" if p < .65 else ".65-.70" if p < .70 else ".70-.75" if p < .75 else ".75+"
res["by_pband"] = table(lambda x: pband(x["p"]), title="P bandı", minn=10)
def fav(x):
    f = x["fav"]
    return "?" if f is None else "güçlü fav ≥.60" if f >= .6 else "fav .45-.60" if f >= .45 else "dengeli <.45"
res["by_fav"] = table(fav, title="favori gücü", minn=10)
def ko(x):
    h = int(x["kickoff"][11:13]); return "<15" if h < 15 else "15-18" if h < 18 else "18+"
res["by_kickoff"] = table(ko, title="başlama", minn=10)
def st(x):
    s = x["steam"]
    return "yok" if s is None else "aleyhte ≤-.02" if s <= -0.02 else "lehte ≥.02" if s >= 0.02 else "sabit"
res["by_steam"] = table(st, title="steam (seçimin kendi keskin P'si)", minn=5)
res["by_verdict"] = table(lambda x: x["verdict"], title="geçmiş kararı", minn=10)
res["name_x_direct"] = table(lambda x: (norm(x["name"]), x["direct"]), title="seçim×doğrudan", minn=20)
res["family_x_tier"] = table(lambda x: (x["family"], x["tier"][:1]), title="aile×kademe", minn=25)
# goals level diagnostics
ft = {}; 
for x in rows: ft[x["code"]] = (x["ft"], x["ht"], x["mu_h"], x["mu_a"], x["tier"])
arr = [(v[0][0], v[0][1], v[1][0] if v[1] else None, v[1][1] if v[1] else None, 0, 0) for v in ft.values() if v[0]]
a = np.array([[t[0], t[1], t[4], t[5]] for t in arr], float)
print("\nmaç n", len(a), "gerçek ev/dep gol", a[:, 0].mean().round(3), a[:, 1].mean().round(3))
htv = np.array([[t[2], t[3], t[0], t[1]] for t in arr if t[2] is not None], float)
print("İY gol payı", (htv[:, :2].sum() / htv[:, 2:].sum()).round(3), "n", len(htv))
draw = np.mean([v[0][0] == v[0][1] for c, v in ft.items() if (c, "MS 0") in snap_first]); pdraw = np.mean([snap_first[(c, "MS 0")][1] for c in ft if (c, "MS 0") in snap_first])
o25 = [(sum(v[0]) > 2.5, snap_first[(c, "2.5 Üst")][1]) for c, v in ft.items() if (c, "2.5 Üst") in snap_first]
print("2.5Ü keskin: n", len(o25), "gerçek", round(np.mean([a for a, b in o25]), 3), "keskin P", round(np.mean([b for a, b in o25]), 3))
hw = [(v[0][0] > v[0][1], snap_first[(c, "MS 1")][1]) for c, v in ft.items() if (c, "MS 1") in snap_first]
print("MS1 keskin: n", len(hw), "gerçek", round(np.mean([a for a, b in hw]), 3), "keskin P", round(np.mean([b for a, b in hw]), 3))
print("beraberlik oranı", round(draw, 3), "model ort", round(pdraw, 3))
res["goals"] = dict(n=len(a), home=float(a[:, 0].mean()), away=float(a[:, 1].mean()), o25_n=len(o25), o25_real=float(np.mean([a for a, b in o25])), o25_p=float(np.mean([b for a, b in o25])),
                    ht_share=float(htv[:, :2].sum() / htv[:, 2:].sum()), draw=float(draw), p_draw=float(pdraw), n_draw=sum((c, "MS 0") in snap_first for c in ft))
json.dump(res, open(D / "hata_analizi_21kasim.json", "w"), ensure_ascii=False, indent=1)
