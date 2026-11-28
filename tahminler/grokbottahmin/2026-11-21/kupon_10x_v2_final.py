#!/usr/bin/env python3
"""v2 aşama 3: ek güvenlik elemesi + 3/4/5 maç tam sayım + canlı oran kontrolü + risk guard -> kupon_10x_v2.json/.md. OYNANMAZ."""
import datetime as dt, heapq, itertools, json, math, pickle, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kupon_10x_sec as K
nk, KM = K.nk, K.KM
R = pickle.load(open("/tmp/k10v2_res_open.pkl", "rb"))
D = pickle.load(open("/tmp/k10v2.pkl", "rb"))
bym = {int(m["code"]): m for m in D["matches"]}
now = dt.datetime.now(K.TSI)
cutoff = now + dt.timedelta(minutes=K.LEAD_MIN)
GH, PM, BUF = KM.policy("risk").max_leg_odds, KM.policy("risk").min_prob, 10.20
EXTRA = {}
def extra_block(code):
    m = bym[code]; lg = m.get("league") or ""
    if "PO" in lg or "Play" in lg or "Liguilla" in lg:
        return "play-off / eleme"
    r = m.get("research") or {}
    if not r.get("teams") and not lg.startswith(("Brezilya Serie A", "İngiltere", "İspanya La Liga", "İtalya Serie A", "Almanya", "Fransa Ligue 1")):
        return "alt lig + takım araştırması yok"
    if dt.datetime.fromisoformat(m["kickoff_iso"]) < cutoff:
        return "kickoff < 25 dk (yeniden kontrol)"
    return None
pools = []
for pl in R["pools"]:
    code = int(pl[0]["code"])
    why = extra_block(code)
    if why:
        EXTRA[f"{pl[0]['match']}"] = why; continue
    pools.append(pl)
LT = math.log(10.0)
def enum(n, cap, pmin, top=15, tmin=10.0):
    P = [[l for l in pl if l["odds"] <= cap + 1e-9 and l["p"] >= pmin] for pl in pools]
    P = [p for p in P if p]
    mx = [math.log(max(l["odds"] for l in p)) for p in P]
    h = []; lt = math.log(tmin)
    for combo in itertools.combinations(range(len(P)), n):
        if sum(mx[i] for i in combo) < lt: continue
        for legs in itertools.product(*[P[i] for i in combo]):
            lo = sum(math.log(l["odds"]) for l in legs)
            if lo < lt - 1e-12: continue
            if max(l["mbs"] for l in legs) > n: continue
            lp = sum(math.log(l["p"]) for l in legs)
            it = (lp, lo, id(legs), legs)
            if len(h) < top: heapq.heappush(h, it)
            elif lp > h[0][0]: heapq.heapreplace(h, it)
    return [summ(x[3]) for x in sorted(h, reverse=True)]
def summ(legs):
    legs = sorted(legs, key=lambda x: x["kickoff"])
    o = math.prod(l["odds"] for l in legs); p = math.prod(l["p"] for l in legs)
    return {"n": len(legs), "odds": round(o, 2), "p": round(p, 5), "ev": round(p * o - 1, 4), "earliest": legs[0]["kickoff"], "legs": legs}
out = {}
for n in (3, 4, 5):
    out[f"guard_{n}"] = enum(n, GH, PM)
    out[f"wide_{n}"] = enum(n, 2.50, 0.40, top=3)
curve = {}
for n in (3, 4, 5):
    for T in (10.0, 11.0, 12.0):
        r = enum(n, GH, PM, top=1, tmin=T)
        curve[f"{n}|{T}"] = r[0] if r else None
cands = [c for n in (3, 4, 5) for c in out[f"guard_{n}"]]
best_raw = max(cands, key=lambda c: c["p"])
buffered = [c for c in cands if c["odds"] >= BUF]
chosen = max(buffered, key=lambda c: (c["p"], sum(l["direct"] for l in c["legs"])))
# canlı Nesine kontrolü + risk guard
live2, flick2 = nk.read_bulletin_odds()
coupon = {"legs": json.loads(json.dumps(chosen["legs"], default=str)), "nesine_odds": chosen["odds"], "probability": chosen["p"]}
notes = nk.recheck_odds([coupon], live2, flick2)
exposure = KM.open_exposure(K.ai_area())
kept, gnotes = nk.apply_mode_guard([coupon], "risk", live2 or None, exposure)
for leg in coupon["legs"]:
    m = bym[int(leg["code"])]
    leg["mu_home"], leg["mu_away"], leg["fair_1x2"] = m.get("mu_home"), m.get("mu_away"), m.get("fair_1x2")
    leg["kickoff_iso"], leg["ref_fetched_utc"] = m.get("kickoff_iso"), m.get("ref_fetched_utc")
    leg["flags"] = (m.get("research") or {}).get("flags")
    leg["fair_odds"] = round(1 / leg["p"], 2)
coupon["probability"] = round(math.prod(l["p"] for l in coupon["legs"]), 5)
coupon["ev"] = round(coupon["probability"] * coupon["nesine_odds"] - 1, 4)
def slim(c):
    if not c: return None
    return {**{k: c[k] for k in ("n", "odds", "p", "ev", "earliest")},
            "legs": [{k: l.get(k) for k in ("code", "kickoff", "league", "match", "market", "selection", "name", "odds", "p", "p_raw", "direct", "ev")} for l in c["legs"]]}
payload = {"ok": True, "placed": False, "mode": "risk", "created": dt.datetime.now(K.TSI).isoformat(timespec="seconds"),
           "data_snapshot": D["now"].isoformat(timespec="seconds"), "target_min": 10.0, "build_buffer_min": BUF,
           "method": "Tam sayım: uygun maçlardaki tüm Nesine seçimleri (Pareto cephesi, kayıpsız budama), 3/4/5 maçın her kombinasyonu; P=keskin 1X2+A/Ü(+KG)'ye oturtulmuş DC matrisi + kalibrasyon; matris türevi seçimlerde -1,5 puan güvenlik payı; maç içi korelasyon tek seçim/maç.",
           "nesine_odds": coupon["nesine_odds"], "probability": coupon["probability"], "ev": coupon["ev"],
           "n_legs": len(coupon["legs"]), "earliest_kickoff": coupon["legs"][0]["kickoff"], "one_in": round(1 / coupon["probability"], 1),
           "guard": coupon.get("guard"), "guard_notes": gnotes, "recheck_notes": notes, "legs": coupon["legs"],
           "best_raw_any_buffer": slim(best_raw),
           "best_3_guard": slim(out["guard_3"][0] if out["guard_3"] else None), "best_4_guard": slim(out["guard_4"][0] if out["guard_4"] else None),
           "best_5_guard": slim(out["guard_5"][0] if out["guard_5"] else None),
           "best_3_wide_2_50": slim(out["wide_3"][0] if out["wide_3"] else None),
           "top_4": [slim(c) for c in out["guard_4"][:8]], "top_5": [slim(c) for c in out["guard_5"][:5]],
           "curve": {k: slim(v) for k, v in curve.items()},
           "excluded_extra": EXTRA, "pool_filters": R["reasons"],
           "exclude_open_codes": sorted(K.EXCLUDE_OPEN), "pool_matches": len(pools), "pool_selections": sum(map(len, pools))}
(HERE / "kupon_10x_v2.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps({k: payload[k] for k in ("nesine_odds", "probability", "ev", "earliest_kickoff", "guard", "guard_notes", "recheck_notes", "excluded_extra", "pool_matches", "pool_selections")}, ensure_ascii=False, indent=1, default=str))
for l in coupon["legs"]:
    print(l["kickoff"], l["match"], l["league"], l["name"], l["odds"], round(l["p"], 3), "D" if l["direct"] else "M", l["fair_odds"], l["flags"], l["mu_home"], l["mu_away"])
for k in ("best_raw_any_buffer", "best_3_guard", "best_4_guard", "best_5_guard", "best_3_wide_2_50"):
    c = payload[k]
    print("==", k, c and (c["odds"], c["p"], c["ev"], [(l["match"], l["name"], l["odds"], round(l["p"], 3)) for l in c["legs"]]))
for k, c in payload["curve"].items():
    print("curve", k, c and (c["odds"], c["p"]))
