import json, sys, math, re
import numpy as np
sys.path.insert(0, "/workspace/futbol-dehasi/src")
from quantfoot.strategy import banko_guard as bg
from quantfoot.markets import market_reliability as MR
rows = json.load(open("/tmp/hata_rows.json"))
snap = {}
for line in open("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-21/nesine_history.jsonl"):
    j = json.loads(line)
    for c, v in j["m"].items():
        for n, (o, p) in (v.get("s") or {}).items():
            snap.setdefault((int(c), n), (o, p))
def eff(x, sc):
    leg = bg.BankoLeg(x["code"], x["name"], x["odds"], x["p"], direct=x["direct"], league=x["league"], name=x["name"],
                      p_draw=snap.get((x["code"], "MS 0"), (None, None))[1], p_over25=snap.get((x["code"], "2.5 Üst"), (None, None))[1])
    return bg.effective_prob(leg, sc)
old = bg.ShrinkConfig(tail=False, untested_extra=0.0)
new = bg.ShrinkConfig()
y = np.array([1.0 if x["won"] else 0.0 for x in rows])
for lab, sc in (("ham", None), ("önceki (PR#5 büzme)", old), ("yeni", new)):
    p = np.array([x["p"] for x in rows]) if sc is None else np.array([eff(x, sc) for x in rows])
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    print(lab, "n", len(p), "ort P", p.mean().round(4), "gerçek", y.mean().round(4), "Brier", ((p - y) ** 2).mean().round(5), "LL", (-(y*np.log(pc)+(1-y)*np.log(1-pc))).mean().round(5))
    hi = p >= 0.65
    print("   P≥.65 n", hi.sum(), "hit", y[hi].mean().round(4), "P", p[hi].mean().round(4))
# changed rows
ch = [(x["name"], x["p"], eff(x, old), eff(x, new), x["won"]) for x in rows if abs(eff(x, old) - eff(x, new)) > 1e-6]
print("değişen seçim", len(ch))
from collections import defaultdict
g = defaultdict(list)
for n, p, a, b, w in ch: g[n].append((a, b, w))
for n, v in sorted(g.items(), key=lambda kv: -len(kv[1]))[:15]:
    print(f"  {n:30s} n={len(v):3d} önce={np.mean([a for a,b,w in v]):.3f} sonra={np.mean([b for a,b,w in v]):.3f} gerçek={np.mean([w for a,b,w in v]):.3f}")
# draw picks of today
print("\nbugünün MS 0 seçimleri:")
den = json.load(open("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-21/denetim_gece_2026-11-21.json"))
seen = set()
for x in den["rows"]:
    if re.search(r"MS 0|Maç Sonucu: 0|beraberlik", x["name"] + " " + x.get("label", "")) and x["name"].startswith("MS 0") and x["code"] not in seen:
        seen.add(x["code"])
        pd_, po = snap.get((x["code"], "MS 0"), (None, None)), snap.get((x["code"], "2.5 Üst"), (None, None))
        p1, p2 = snap.get((x["code"], "MS 1"), (None, None)), snap.get((x["code"], "MS 2"), (None, None))
        r = MR.draw_risk(pd_[1], po[1])
        ok = MR.draw_pick_ok(pd_[1], po[1], x["odds"])
        print(" ", x["match"], x["name"], "oran", x["odds"], "P", x["p"], "skor", x["ft"], "won", x["won"], "| fav oran", min(p1[0] or 99, p2[0] or 99), "ber oran", pd_[0], "P0", pd_[1], "P2.5Ü", po[1], "risk", None if r is None else round(r, 3), ok)
