import json, collections, csv
from ortak import summ, pband, oband, OUT, ARS
R = json.load(open(OUT / "rows.json")); C = json.load(open(OUT / "coupons.json"))
for r in R: r["odds"] = r.get("oran")

def grp(rows, key):
    d = collections.defaultdict(list)
    for r in rows: d[key(r)].append(r)
    return {k: summ(v) for k, v in sorted(d.items(), key=lambda kv: str(kv[0]))}

SEL_KINDS = {"ana_secim", "ana_secim_csv", "sohbet_secim", "havuz_en_iyi"}
out = {"uretim": "2026-11-28 TSİ", "kaynak_notu": "Skorlar Nesine GetUnliveMatches (18–28 Kas, İY+90'); bulunamayan = belirsiz."}
sel = [r for r in R if r["tur"] in SEL_KINDS]
leg = [r for r in R if r["tur"] in ("kupon_bacak", "oynanan_bacak")]
out["secim_ai_gun"] = grp(sel, lambda r: f'{r["ai"]} | {r["tarih"]} | {r["tur"]}')
out["secim_ai_surum"] = grp(sel, lambda r: f'{r["ai"]} | {r["surum"]}')
out["secim_surum"] = grp(sel, lambda r: r["surum"])
out["p_bandi_surum"] = grp(sel + leg, lambda r: f'{r["surum"]} | {pband(r.get("p"))}')
out["p_bandi_ai"] = grp(sel, lambda r: f'{r["ai"]} | {pband(r.get("p"))}')
out["aile_surum"] = grp(sel + leg, lambda r: f'{r["surum"]} | {r["aile"]}')
out["aile_ai"] = grp(sel, lambda r: f'{r["ai"]} | {r["aile"]}')
out["oran_bandi_surum"] = grp(sel + leg, lambda r: f'{r["surum"]} | {oband(r.get("oran"))}')
out["kupon_bacak_ai_surum"] = grp(leg, lambda r: f'{r["ai"]} | {r["surum"]}')
out["kupon_bacak_kural"] = grp(leg, lambda r: f'{r["surum"]} | {"kurala uygun" if not [x for x in r["ihlal"] if x != "P 0.65-0.70"] else "kural dışı"}')
viol = collections.defaultdict(list)
for r in sel + leg:
    for v in (r["ihlal"] or ["temiz"]):
        viol[f'{r["surum"]} | {v}'].append(r)
out["ihlal_turu"] = {k: summ(v) for k, v in sorted(viol.items())}
# kupon özetleri
def csumm(cs):
    st = collections.Counter(c["durum"] for c in cs)
    lw = sum(c["tutan_bacak"] for c in cs); ll = sum(c["yatan_bacak"] for c in cs)
    stake = sum(c["stake"] or 0 for c in cs if c["oynandi"]); ret = sum(c["donus"] or 0 for c in cs if c["oynandi"])
    return {"kupon": len(cs), "kazandı": st["kazandı"], "kaybetti": st["kaybetti"], "belirsiz": st["belirsiz"],
            "bacak_tuttu": lw, "bacak_yattı": ll, "bacak_isabet": round(lw / (lw + ll), 4) if lw + ll else None,
            "ort_bacak": round(sum(c["bacak"] for c in cs) / len(cs), 2) if cs else None,
            "ort_oran": round(sum(c["oran"] or 0 for c in cs) / len(cs), 2) if cs else None,
            "oynanan": sum(1 for c in cs if c["oynandi"]), "yatirilan_tl": stake, "donen_tl": ret}
def cgrp(cs, key):
    d = collections.defaultdict(list)
    for c in cs: d[key(c)].append(c)
    return {k: csumm(v) for k, v in sorted(d.items())}
out["kupon_ai_gun"] = cgrp(C, lambda c: f'{c["ai"]} | {c["tarih"]}')
out["kupon_ai_surum"] = cgrp(C, lambda c: f'{c["ai"]} | {c["surum"]}')
out["kupon_surum"] = cgrp(C, lambda c: c["surum"])
out["kupon_bacak_sayisi"] = cgrp(C, lambda c: f'{c["surum"]} | {min(c["bacak"], 8)}{"+" if c["bacak"]>=8 else ""} bacak')
out["kupon_oran_bandi"] = cgrp(C, lambda c: f'{c["surum"]} | ' + ("<3" if (c["oran"] or 0) < 3 else "3-6" if c["oran"] < 6 else "6-15" if c["oran"] < 15 else "15+"))
out["kupon_ihlalli"] = cgrp([c for c in C if c["ihlalli_bacak"] is not None], lambda c: f'{c["surum"]} | {"kural dışı bacak var" if c["ihlalli_bacak"] else "tüm bacaklar kurala uygun"}')
# Gemini öz-beyan doğruluğu
g = [r for r in R if r["ai"] == "geminitahmin" and r["oz_beyan"] is not None and r["won"] is not None]
out["gemini_oz_beyan"] = {"karsilastirilan": len(g), "uyusmayan": sum(1 for r in g if r["oz_beyan"] != r["won"]),
    "oz_beyan_isabet": round(sum(r["oz_beyan"] for r in g) / len(g), 4) if g else None,
    "nesine_isabet": round(sum(r["won"] for r in g) / len(g), 4) if g else None,
    "ornekler": [{k: r[k] for k in ("tarih", "mac", "secim", "oz_beyan", "won", "kod")} for r in g if r["oz_beyan"] != r["won"]][:20]}
gc = [c for c in C if c["ai"] == "geminitahmin" and c["oz_beyan"]]
out["gemini_kupon_oz_beyan"] = [{k: c[k] for k in ("tarih", "id", "oz_beyan", "durum", "tutan_bacak", "yatan_bacak", "belirsiz_bacak", "stake")} for c in gc]
# Gerçek para defteri (Nesine hesabından çekilmiş, repoda)
def num(s):
    s = (s or "").replace("TL", "").strip()
    return float(s.replace(".", "").replace(",", ".")) if s else 0.0
L = list(csv.DictReader(open(ARS / "tahminler/grokbottahmin/nesine_kupon_liste.csv", encoding="utf-8-sig")))
G = list(csv.DictReader(open(ARS / "tahminler/grokbottahmin/nesine_kupon_gecmisi.csv", encoding="utf-8-sig")))
gid = {}
for r in G: gid.setdefault(r["coupon_id"], r)
out["gercek_para"] = {
    "liste_20Eki_10Kas": {"kupon": len(L), "kazanan": sum(r["status"] == "Kazandı" for r in L),
                          "yatirilan": sum(num(r["stake_TL"]) for r in L), "donen": sum(num(r["win_TL"]) for r in L)},
    "gecmis_13_21Kas": {"kupon": len(gid), "kazanan": sum(r["status"] == "Kazandı" for r in gid.values()),
                        "acik": sum(r["status"] == "Devam" for r in gid.values()),
                        "yatirilan": sum(num(r["stake_TL"]) for r in gid.values()), "donen": sum(num(r["win_TL"]) for r in gid.values())},
}
out["kupon_listesi"] = C
json.dump(out, open(OUT / "rapor.json", "w"), ensure_ascii=False, indent=1, default=str)
for k in ("secim_ai_surum", "secim_surum", "kupon_ai_surum", "kupon_surum", "kupon_bacak_sayisi", "kupon_oran_bandi", "kupon_ihlalli",
          "kupon_bacak_kural", "ihlal_turu", "p_bandi_surum", "oran_bandi_surum", "aile_surum", "gemini_oz_beyan", "gercek_para"):
    print("==", k)
    v = out[k]
    if isinstance(v, dict) and all(isinstance(x, dict) for x in v.values()):
        for kk, vv in v.items(): print("  ", kk, {a: b for a, b in vv.items() if a in ("n","notlanan","tuttu","isabet","ort_p","ort_oran","roi","kupon","kazandı","kaybetti","belirsiz","bacak_isabet","ort_bacak","oynanan","yatirilan_tl","donen_tl","yatirilan","donen","kazanan","acik")})
    else: print(json.dumps(v, ensure_ascii=False)[:1500])
