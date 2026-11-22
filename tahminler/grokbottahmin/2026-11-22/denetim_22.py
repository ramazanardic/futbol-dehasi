#!/usr/bin/env python3
"""Denetim 2026-11-22 (sabah): 21→22 gece + 07:00–09:00 tahminleri ve oynanan kuponlar.

Kaynak: Nesine GetUnliveMatches (İY + 90'), FotMob herkese açık JSON (yalnız Nesine'de bitmemişler
için; canlı maçlar 'bekliyor' sayılır, nota girmez). Skor uydurulmaz: bulunamayan = bilinmiyor.
Çalıştır: .venv/bin/python tahminler/grokbottahmin/2026-11-22/denetim_22.py
"""
from __future__ import annotations

import ast
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path("/workspace/futbol-dehasi")
G = ROOT / "tahminler/grokbottahmin"
D = G / "2026-11-22"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(G / "2026-11-21"))
import denetim_gece as dg  # noqa: E402
from quantfoot.data.match_dossier import team_match_score  # noqa: E402

TSI = dg.TSI
NOW = dt.datetime.now(TSI)

nes = dg.fetch_nesine()
# 22 Kasım CSV'sindeki "00:00–04:10" satırları aslında 23 Kasım gecesi (Nesine MD) — onları da tanı
_j23 = dg.get_json("https://ls.nesine.com/api/v2/LiveScore/GetUnliveMatches", {"sportType": 1, "date": "2026-11-23"})
REAL_KO: dict[int, str] = {}
for _day in ("2026-11-21", "2026-11-22"):
    for _m in (json.loads((dg.CACHE / f"unlive_{_day}.json").read_text()).get("d") or []):
        REAL_KO[int(_m["C"])] = (_m.get("MD") or "")[:16].replace("T", " ")
for _m in _j23.get("d") or []:
    _c = int(_m["C"])
    REAL_KO[_c] = (_m.get("MD") or "")[:16].replace("T", " ")
    if _c not in nes:
        nes[_c] = {"st": _m.get("ST"), "home": _m.get("HTTR"), "away": _m.get("ATTR"), "state": "başlamadı", "src": "nesine-23"}
fm = dg.fetch_fotmob_list()
FM_ALIAS = {"T. Vortis - S. Bellmare": "Tokushima Vortis - Shonan Bellmare", "R. Yamaguchi - MIO Biwako Shiga": "Renofa Yamaguchi - Reilac Shiga"}
# API-Football (tek istek, /fixtures?date=2026-11-22) — yalnız Nesine/FotMob'da bulunmayan bitmiş maçlar için
APIF = {}
_ap = Path("/tmp/den22/apif_20261122.json")
if _ap.exists():
    for _f in json.loads(_ap.read_text()).get("response") or []:
        APIF[(_f["teams"]["home"]["name"], _f["teams"]["away"]["name"])] = _f


def nes_find(match: str, min_score=0.72):
    h, a = dg.split_teams(match)
    best, bs = None, 0.0
    for code, r in nes.items():
        s = min(team_match_score(h, r.get("home") or ""), team_match_score(a, r.get("away") or ""))
        if s > bs:
            best, bs = code, s
    return (best, bs) if bs >= min_score else (None, bs)


_cache: dict = {}


def resolve(code, match):
    key = (code, match)
    if key in _cache:
        return _cache[key]
    rec = dict(nes.get(int(code)) or {}) if code else {}
    if rec.get("state") in ("final", "void"):
        _cache[key] = rec
        return rec
    if rec.get("src") == "nesine-23":
        _cache[key] = rec
        return rec
    h, a = dg.split_teams(FM_ALIAS.get(match, match))
    f, sc = dg.fm_find(fm, h, a)
    if not f and APIF:
        best, bs = None, 0.0
        for (ah, aa), fx in APIF.items():
            s_ = min(team_match_score(h, ah), team_match_score(a, aa))
            if s_ > bs:
                best, bs = fx, s_
        if best and bs >= 0.6:
            st = best["fixture"]["status"]["short"]
            sco = best["score"]
            if st in ("FT", "AET", "PEN") and sco["fulltime"]["home"] is not None:
                rec.update(state="final", ft=[sco["fulltime"]["home"], sco["fulltime"]["away"]],
                           ht=[sco["halftime"]["home"], sco["halftime"]["away"]], src="api-football",
                           apif_match=f"{best['teams']['home']['name']} - {best['teams']['away']['name']}")
            elif st in ("1H", "HT", "2H", "ET", "BT", "P", "LIVE"):
                rec.update(state="canlı", live=[best["goals"]["home"], best["goals"]["away"]],
                           minute=best["fixture"]["status"]["elapsed"], src="api-football")
            elif st in ("PST", "CANC", "ABD", "AWD", "WO"):
                rec.update(state="void", why=st, src="api-football")
            _cache[key] = rec
            return rec
    if not f:
        rec.setdefault("state", "bilinmiyor")
        rec["why"] = "Nesine'de bitmiş kayıt yok, FotMob/API-Football eşleşmesi yok"
    elif f["canc"] or f["reason"] in ("PP", "Ab"):
        rec.update(state="void", why=f["reason"] or "iptal", src="fotmob")
    elif f["fin"]:
        rec.update(state="final", ft=[f["hg"], f["ag"]], src="fotmob", fm_id=f["id"])
        ht = dg.fm_ht(f["id"])
        if ht is not None:
            rec["ht"] = ht
    elif f["live"]:
        rec.update(state="canlı", live=[f["hg"], f["ag"]], minute=f["minute"], src="fotmob-canlı", fm_id=f["id"])
    else:
        rec.update(state=rec.get("state") or "başlamadı", src="fotmob")
    _cache[key] = rec
    return rec


def grade(name, rec):
    if rec.get("state") != "final":
        return None
    w, _, _ = dg.grade(name, rec)
    return w


def fam_of(name: str) -> str:
    n = name
    if n.startswith("DEĞİL(") and ("Yarıda" in n or "Yarıyı" in n):
        return "Yarı özel"
    if "2Y KG" in n:
        return "2Y karşılıklı gol"
    if n.startswith("İY KG") or "İY KG" in n:
        return "Yarı KG kombine"
    if n.startswith(("Ev İY", "Dep İY")):
        return "Takım İY gol"
    if n.startswith("İY"):
        return "İlk yarı"
    if n.startswith(("Ev ", "Dep ")):
        return "Takım gol"
    if n.startswith("ÇŞ"):
        return "Çifte şans"
    if n.startswith("MS") and "&" in n:
        return "Kombine"
    if n.startswith("MS"):
        return "Maç sonucu"
    if n.startswith("KG"):
        return "Karşılıklı gol"
    if "Alt" in n or "Üst" in n:
        return "Alt/Üst"
    return "Diğer"


def row_out(code, match, ko, league, name, p, odds, family, src_set, headline=True):
    rec = resolve(code, match)
    w = grade(name, rec)
    return {
        "set": src_set, "code": int(code) if code else None, "match": match, "kickoff": ko, "league": league,
        "name": name, "family": family, "p": p, "odds": odds, "headline": headline,
        "state": rec.get("state"), "ht": rec.get("ht"), "ft": rec.get("ft"), "live": rec.get("live"),
        "minute": rec.get("minute"), "src": rec.get("src"), "won": w,
        "real_kickoff": REAL_KO.get(int(code)) if code else None,
    }


# ---- A) 22 Kasım ana seçimler (mac_tahminleri.csv), başlamış olanlar
def started(code, ko_label):
    ko = REAL_KO.get(int(code)) or ko_label
    return dt.datetime.strptime(ko, "%Y-%m-%d %H:%M").replace(tzinfo=TSI) <= NOW


moved_23 = []  # CSV'de "2026-11-22 00:00–04:10" yazan ama Nesine'de 23 Kasım olan maçlar
rows_a = []
for r in csv.DictReader(open(D / "mac_tahminleri.csv", encoding="utf-8-sig")):
    if not r["secim_adi"]:
        continue
    ko = f"{r['tarih']} {r['saat']}"
    rk = REAL_KO.get(int(r["nesine_kodu"]))
    if rk and rk[:10] != ko[:10]:
        moved_23.append({"code": int(r["nesine_kodu"]), "match": r["mac"], "csv_kickoff": ko, "nesine_kickoff": rk,
                         "name": r["secim_adi"]})
    if not started(r["nesine_kodu"], ko):
        continue
    rows_a.append(row_out(r["nesine_kodu"], r["mac"], ko, r["lig"], r["secim_adi"], float(r["olasilik"]),
                          float(r["nesine_oran"] or 0) or None, fam_of(r["secim_adi"]), "22K-ana"))

# ---- A2) 22 Kasım tüm uygun seçimler (derin_tahminler.json), başlamış maçlar
rows_a2 = []
for m in json.load(open(D / "derin_tahminler.json")):
    ko = m["kickoff"]
    if not started(m["code"], ko):
        continue
    fams = m["families"]
    fams = ast.literal_eval(fams) if isinstance(fams, str) else fams
    for f in fams or []:
        for s in f.get("suitable") or []:
            if (s.get("odds") or 0) >= 1.20 and s.get("name"):
                rows_a2.append(row_out(m["code"], m["match"], ko, m["league"], s["name"], s.get("p"), s.get("odds"),
                                       f["family"], "22K-tüm", headline=False))

# ---- B) 21 Kasım denetiminde notlanamamış satırlar (gece maçları vs.)
old = json.load(open(G / "2026-11-21/denetim_gece_2026-11-21.json"))
rows_b = []
for r in old["rows"]:
    if r.get("won") is not None:
        continue
    nr = row_out(r["code"], r["match"], r["kickoff"], r.get("league"), r["name"], r["p"], r.get("odds"),
                 r.get("family"), "21K-yeniden", headline=bool(r.get("headline")))
    nr["old_kind"] = r.get("kind")
    rows_b.append(nr)

# ---- C) kuponlar
def leg(code, ko, match, name, odds, p=None, family=None):
    if not code:
        code, _ = nes_find(match)
    rec = resolve(code, match)
    return {"code": code, "ko": ko, "match": match, "name": name, "odds": odds, "p": p,
            "family": family or fam_of(name), "state": rec.get("state"), "ht": rec.get("ht"), "ft": rec.get("ft"),
            "live": rec.get("live"), "minute": rec.get("minute"), "src": rec.get("src"), "won": grade(name, rec)}


def coupon(cid, title, stake, odds, played, placed, legs, p_win=None):
    won = [l["won"] for l in legs]
    if any(w is False for w in won):
        st = "KAYBETTİ"
    elif all(w is True for w in won):
        st = "KAZANDI"
    else:
        st = "BEKLİYOR"
    return {"id": cid, "title": title, "stake": stake, "odds": odds, "played": played, "placed": placed,
            "p_win_model": p_win, "status": st, "legs_won": won.count(True), "legs_lost": won.count(False),
            "legs_pending": sum(1 for w in won if w is None),
            "return_tl": round(stake * odds, 2) if (played and st == "KAZANDI") else (0 if played and st == "KAYBETTİ" else None),
            "legs": legs}


log = json.load(open(G / "oynanan_kuponlar.json"))
byid = {c.get("id"): c for c in log["coupons"] if c.get("id")}
coupons = []
for cid, placed in (("MS10", "2026-11-21 15:58"), ("K2000", "2026-11-21 18:00")):
    c = byid[cid]
    coupons.append(coupon(cid, c.get("mode"), c["stake"], c["odds"], True, placed,
                          [leg(l["code"], l["ko"], l["match"], l["name"], l["odds"], l.get("p")) for l in c["legs"]]))
b = [c for c in log["coupons"] if not c.get("id") and c.get("placed_at") == "2026-11-21 23:26"][0]
NAMES = {"İY 1,5 Alt": "İY 1.5 Alt", "2,5 Alt": "2.5 Alt", "İY 0,5 Üst": "İY 0.5 Üst", "MS 2": "MS 2", "2,5 Üst": "2.5 Üst",
         "MS 1": "MS 1"}
_pc5 = [x.get("pc") for x in json.load(open(D / "gece_kupon_7x.json"))["alt_5x"]["legs"]]
coupons.append(coupon("GECE-5.00", "gece_kupon_7x alternatif", 200, 5.0, True, "2026-11-21 23:26",
                      [leg(None, l["ko"], l["match"], NAMES[l["pick"]], l["odds"], _pc5[i] if i < len(_pc5) else None)
                       for i, l in enumerate(b["legs"])]))
k = log["kuponlar"][-1]
c0709 = json.load(open(D / "gece_kupon_0709.json"))["coupons"]
pmap = {l["code"]: l.get("p_cal") for l in c0709["C"]["legs"]}
coupons.append(coupon("0709-C (20.30)", "riskli 20 oran", k["stake"], k["total_odds"], True, k["placed"],
                      [leg(int(l[1]), l[0], l[2], l[3], l[4], pmap.get(l[1])) for l in k["legs"]], c0709["C"].get("p_win")))
g7 = json.load(open(D / "gece_kupon_7x.json"))
for key, cid, played in (("coupon_7x", "GECE-7.04", False),):
    c = g7[key]
    coupons.append(coupon(cid, "gece 7x (oynanmadı)", 0, c["total_odds"], played, None,
                          [leg(None, l["ko"], l["match"], NAMES.get(l["sel"], l["sel"]), l["odds"], l.get("pc")) for l in c["legs"]],
                          c.get("p")))
c = g7["alt_5x"]
coupons.append(coupon("GECE-5.04 (plan)", "plan hali; oynanan GECE-5.00", 0, c["total_odds"], False, None,
                      [leg(None, l["ko"], l["match"], NAMES.get(l["sel"], l["sel"]), l["odds"], l.get("pc")) for l in c["legs"]],
                      c.get("p")))
for cid in ("A", "B"):
    c = c0709[cid]
    coupons.append(coupon(f"0709-{cid}", c["title"], 0, c["total_odds"], False, None,
                          [leg(int(l["code"]), l["kickoff_tsi"], l["match"], l["rule_name"], l["nesine_odds"], l.get("p_cal"), l.get("family"))
                           for l in c["legs"]], c.get("p_win")))

# ---- özetler
def summ(rs):
    g = [x for x in rs if x["won"] in (True, False)]
    n, w = len(g), sum(1 for x in g if x["won"])
    ps = [x["p"] for x in g if x.get("p") is not None]
    return {"n": n, "won": w, "lost": n - w, "pending_or_unknown": len(rs) - n,
            "hit": round(w / n, 4) if n else None,
            "avg_p": round(sum(ps) / len(ps), 4) if ps else None,
            "gap": round(w / n - sum(ps) / len(ps), 4) if n and ps else None}


EDGES = ((0, .55, "<55"), (.55, .60, "55-60"), (.60, .65, "60-65"), (.65, .70, "65-70"), (.70, .75, "70-75"), (.75, 2, "75+"))


def bins(rs):
    return {lab: summ([x for x in rs if x.get("p") is not None and lo <= x["p"] < hi]) for lo, hi, lab in EDGES}


def by(rs, key):
    d = defaultdict(list)
    for x in rs:
        d[x.get(key) or "?"].append(x)
    return dict(sorted(((k, summ(v)) for k, v in d.items()), key=lambda kv: -kv[1]["n"]))


# headline havuzu: 22K ana + 21K yeniden notlanan headline (kod+seçim tekil; 22K öncelikli)
seen = {(x["code"], x["name"]) for x in rows_a}
head = rows_a + [x for x in rows_b if x["headline"] and (x["code"], x["name"]) not in seen]
allp = rows_a2 + [x for x in rows_b if (x["code"], x["name"]) not in {(y["code"], y["name"]) for y in rows_a2}]
legs_all = [l for c in coupons for l in c["legs"]]
legs_played = [l for c in coupons if c["played"] for l in c["legs"]]
uniq = {}
for l in legs_all:
    uniq[(l["code"], l["name"])] = l
legs_uniq = list(uniq.values())

out = {
    "generated_at": NOW.strftime("%Y-%m-%d %H:%M TSİ"),
    "sources": ["Nesine GetUnliveMatches 21-22 Kas (İY+90')", "FotMob herkese açık JSON (Nesine'de bitmeyenler; canlılar notlanmadı)", "API-Football /fixtures?date=2026-11-22 (maç sonrası tek istek, bütçe sayacıyla)"],
    "summary": {
        "22K_ana_secim": summ(rows_a),
        "21K_yeniden_headline": summ([x for x in rows_b if x["headline"]]),
        "headline_havuz": summ(head),
        "tum_uygun_havuz": summ(allp),
        "kupon_bacak_tekil": summ(legs_uniq),
        "kupon_bacak_oynanan": summ(legs_played),
    },
    "calibration_headline": bins(head),
    "calibration_tum_uygun": bins(allp),
    "calibration_kupon_bacak": bins(legs_uniq),
    "family_headline": by(head, "family"),
    "family_tum_uygun": by(allp, "family"),
    "family_kupon_bacak": by(legs_uniq, "family"),
    "csv_tarih_hatasi_23K": moved_23,
    "coupons": coupons,
    "rows_22K_ana": rows_a,
    "rows_21K_yeniden": rows_b,
    "rows_22K_tum": rows_a2,
}
dg.save_json(D / "denetim_2026-11-22_raw.json", out)
print(json.dumps(out["summary"], ensure_ascii=False, indent=1))
for c in coupons:
    print(c["id"], c["status"], c["odds"], c["stake"])
    for l in c["legs"]:
        print("   ", l["ko"], l["match"], "|", l["name"], l["odds"], "| İY", l["ht"], "MS", l["ft"], "canlı", l["live"], l["minute"], l["state"], "->", l["won"])
