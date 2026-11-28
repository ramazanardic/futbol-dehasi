#!/usr/bin/env python3
"""≥10 oran kuponu v2 — 3/4/5 maçlık TAM (exhaustive) arama. OYNANMAZ.

Havuz: her uygun maçın Nesine bültenindeki tüm seçimleri (kombine aileler dahil), P = keskin 1X2+A/Ü(+KG)'ye
oturtulmuş Dixon-Coles matrisi -> kalibrasyon (nesine_kupon.candidates ile aynı formül). Maç başına (oran, P)
Pareto cephesi tutulur (baskın seçim hiçbir optimal kuponda yer alamaz -> kayıpsız budama). Ardından tam DP
(log-oran kova 0.0005, kesin log-oran saklanır) + doğrulama için kısıtlı kaba kuvvet.
"""
import datetime as dt, itertools, json, math, pickle, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kupon_10x_sec as K
nk, ng, KM = K.nk, K.ng, K.KM

D = pickle.load(open("/tmp/k10v2.pkl", "rb"))
matches, live = D["matches"], D["live"]
now = dt.datetime.now(K.TSI)
cutoff = now + dt.timedelta(minutes=K.LEAD_MIN)
import os
LO, HI, PMIN = 1.25, 2.50, 0.40
DERIVED = os.environ.get("DERIVED", "open")
HAIRCUT = 0.015 if DERIVED == "open" else 0.0
GUARD_HI = KM.policy("risk").max_leg_odds
mcal = nk.load_market_calibration()
cal = nk.load_live_calibration() or None
offered = KM.bulletin_offered(live) if live else None

reasons, pools, bym = {}, [], {}
for m in matches:
    why = K.bad_match(m, now, cutoff)
    if not why and nk.is_cup_competition(m.get("league")):
        why = "kupa"
    if not why and not (m.get("reference") or "").startswith(nk.SHARP_SOURCES):
        why = "keskin referans yok"
    if why:
        reasons[why] = reasons.get(why, 0) + 1
        continue
    bym[int(m["code"])] = m
    steam = K.parse_steam((m.get("research") or {}).get("flags") or [])
    legs = []
    for s in m.get("selections") or []:
        name = s.get("name", "")
        o = s["odds"]
        if o < LO - 1e-9 or o > HI + 1e-9:
            continue
        p = nk.calibrated_probability(s["fair_prob"], bool(s.get("direct")), cal)
        p = nk.calibrate_market_probability(name, p, m.get("league"), mcal, direct=bool(s.get("direct")))
        if p < PMIN or s["ev"] > nk.MAX_PLAUSIBLE_EV:
            continue
        hard = nk.is_hard_market(name, o)
        if hard and p * o - 1 < nk.HARD_MARKET_MIN_EV:
            continue
        if s.get("direct") is False:
            if DERIVED == "strict" and p * o - 1 < nk.leg_min_ev(name, hard):
                continue
            p = max(0.0, p - HAIRCUT)  # model-türevi (matris) fiyat: güvenlik payı
            if p < PMIN or p * o - 1 < -0.12:
                continue
        if not s.get("direct") and name.startswith(("İY/MS", "2Y 0", "2Y 1", "2Y 2")):
            continue
        if K.steam_against(name, steam):
            continue
        if offered is not None:
            ok = offered(int(m["code"]), s.get("key"), name)
            if ok is False:
                continue
        legs.append({"code": int(m["code"]), "kickoff": m["kickoff"], "league": m["league"],
                     "match": f"{m['home']} - {m['away']}", "market": s["market"], "selection": s["selection"],
                     "name": name, "odds": o, "p": p, "p_raw": s["fair_prob"], "direct": bool(s.get("direct")),
                     "mbs": int(s.get("mbs") or 1), "reference": m["reference"].split(" (")[0] + " (" + m["reference"].split(" (")[1] if " (" in m["reference"] else m["reference"],
                     "key": s.get("key"), "ev": round(p * o - 1, 4), "context": nk.match_context(m)})
    # Pareto front on (odds, p): drop legs with both lower odds and lower P than another
    legs.sort(key=lambda x: (-x["odds"], -x["p"]))
    front, bp = [], -1
    for l in legs:
        if l["p"] > bp + 1e-12:
            front.append(l); bp = l["p"]
    if front:
        pools.append(front)

print("eleme:", reasons, "| uygun maç:", len(pools), "| cephe seçim:", sum(map(len, pools)))

RES = 0.0005
LCAP = math.log(30.0)

def dp(pools, max_odds_leg=HI):
    """state (n, maxmbs, bucket) -> (sumlogp, exact_logodds, legs). Exact up to RES merging."""
    st = {(0, 1, 0): (0.0, 0.0, ())}
    for pool in pools:
        new = dict(st)
        for (n, mb, _), (lp, lo, legs) in st.items():
            if n >= 5:
                continue
            for l in pool:
                if l["odds"] > max_odds_leg + 1e-9:
                    continue
                nlo = min(lo + math.log(l["odds"]), LCAP)
                key = (n + 1, max(mb, l["mbs"]), int(nlo / RES))
                v = lp + math.log(l["p"])
                old = new.get(key)
                if old is None or v > old[0] + 1e-12:
                    new[key] = (v, nlo, legs + (l,))
        st = new
    return st

def best_from(st, n, T):
    best = None
    for (k, mb, b), (lp, lo, legs) in st.items():
        if k == n and k >= mb and lo >= math.log(T) - 1e-12:
            if best is None or lp > best[0]:
                best = (lp, legs)
    return best

def summ(legs):
    legs = sorted(legs, key=lambda x: x["kickoff"])
    o = math.prod(l["odds"] for l in legs); p = math.prod(l["p"] for l in legs)
    return {"n": len(legs), "odds": round(o, 2), "p": p, "ev": p * o - 1, "earliest": legs[0]["kickoff"], "legs": legs}

curve = {}
for cap_lbl, cap in (("guard_2.10", GUARD_HI), ("max_2.50", HI)):
    st = dp(pools, cap)
    for n in (3, 4, 5):
        for T in (10.0, 11.0, 12.0):
            b = best_from(st, n, T)
            curve[f"{cap_lbl}|{n}|{T}"] = summ(b[1]) if b else None

# Verification: brute force over top-K per match by efficiency on top-M matches (5-leg) for the ≥10 / guard case
def eff(l):
    return math.log(l["p"]) / math.log(l["odds"])
small = []
for pool in pools:
    c = [l for l in pool if l["odds"] <= GUARD_HI + 1e-9]
    c.sort(key=eff, reverse=True)
    if c:
        small.append(c[:3])
small.sort(key=lambda pl: -max(eff(l) for l in pl))
bf = {}
for n, M in ((3, len(small)), (4, min(len(small), 45)), (5, min(len(small), 24))):
    best = None
    for combo in itertools.combinations(small[:M], n):
        for legs in itertools.product(*combo):
            lo = sum(math.log(l["odds"]) for l in legs)
            if lo < math.log(10.0) - 1e-12 or max(l["mbs"] for l in legs) > n:
                continue
            lp = sum(math.log(l["p"]) for l in legs)
            if best is None or lp > best[0]:
                best = (lp, legs)
    bf[n] = summ(best[1]) if best else None

pickle.dump({"pools": pools, "curve": curve, "bf": bf, "reasons": reasons, "now": now, "data_now": D["now"]},
            open(f"/tmp/k10v2_res_{DERIVED}.pkl", "wb"))
for k, v in curve.items():
    if v:
        print(k, v["odds"], f"P={v['p']*100:.2f}%", f"EV={v['ev']:+.0%}", " | ".join(f"{l['kickoff'][11:]} {l['match']} [{l['name']}] {l['odds']} {l['p']*100:.0f}%" for l in v["legs"]))
    else:
        print(k, None)
print("--- kaba kuvvet doğrulama (guard 2.10, ≥10):")
for n, v in bf.items():
    if v:
        print(n, v["odds"], f"P={v['p']*100:.2f}%", " | ".join(f"{l['match']} [{l['name']}] {l['odds']}" for l in v["legs"]))
