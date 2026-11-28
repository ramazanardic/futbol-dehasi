#!/usr/bin/env python3
"""Denetim 2026-11-22 gün içi (≈17:15 TSİ): sohbette verilen seçimler + analiz_1000_1400 / analiz_gun havuzu.

Skor: Nesine GetUnliveMatches (İY+90'), yoksa FotMob herkese açık JSON (İY matchDetails'ten).
Skor uydurulmaz: bulunamayan = 'belirsiz'; başlamamış/canlı = 'bekliyor'.
Çalıştır: .venv/bin/python tahminler/grokbottahmin/2026-11-22/denetim_gun.py
"""
from __future__ import annotations

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

TSI = dg.TSI
NOW = dt.datetime.now(TSI)
OUT = sys.argv[1] if len(sys.argv) > 1 else "1715"

nes = dg.fetch_nesine()
_j23 = dg.get_json("https://ls.nesine.com/api/v2/LiveScore/GetUnliveMatches", {"sportType": 1, "date": "2026-11-23"})
for _m in _j23.get("d") or []:
    _c = int(_m["C"])
    nes.setdefault(_c, {"st": _m.get("ST"), "home": _m.get("HTTR"), "away": _m.get("ATTR"), "state": "başlamadı", "src": "nesine-23"})
fm = dg.fetch_fotmob_list()

A = json.load(open(D / "analiz_1000_1400.json"))
GN = json.load(open(D / "analiz_gun_2026-11-22.json"))
MAC: dict[str, dict] = {}
for m in A["maclar"]:
    MAC[str(m["kod"])] = dict(m, tarih=m.get("tarih") or "2026-11-22", _src="analiz_1000_1400")
for m in GN["maclar"]:
    MAC.setdefault(str(m["kod"]), dict(m, _src="analiz_gun"))

# FotMob adı farklı olanlar (Maxline Rogachev = FotMob'da "ML Vitebsk", aynı kulüp, Slavia Mozyr maçı 17:00 TSİ)
FM_ALIAS = {"E. Cottbus - Hertha Berlin": "Energie Cottbus - Hertha BSC", "M. Rogachev - Slavia Mozyr": "ML Vitebsk - Slavia Mozyr"}
_cache: dict = {}


def resolve(code: str) -> dict:
    if code in _cache:
        return _cache[code]
    m = MAC[code]
    rec = dict(nes.get(int(code)) or {})
    ko = dt.datetime.strptime(f"{m['tarih']} {m['saat']}", "%Y-%m-%d %H:%M").replace(tzinfo=TSI)
    if rec.get("state") in ("final", "void"):
        pass
    elif ko > NOW:
        rec["state"] = "başlamadı"
    else:
        h, a = dg.split_teams(FM_ALIAS.get(m["mac"], m["mac"]))
        f, _ = dg.fm_find(fm, h, a)
        if not f:
            rec["state"] = "belirsiz" if ko + dt.timedelta(hours=2, minutes=15) < NOW else "canlı?"
            rec["why"] = "Nesine'de bitmiş kayıt yok, FotMob eşleşmesi yok"
        elif f["canc"] or f["reason"] in ("PP", "Ab"):
            rec.update(state="void", why=f["reason"] or "iptal", src="fotmob")
        elif f["fin"]:
            rec.update(state="final", ft=[f["hg"], f["ag"]], src="fotmob", fm_id=f["id"])
            ht = dg.fm_ht(f["id"])
            if ht is not None:
                rec["ht"] = ht
        elif f["live"]:
            rec.update(state="canlı", live=[f["hg"], f["ag"]], minute=f["minute"], src="fotmob-canlı", fm_id=f["id"])
            if (f["minute"] or 0) >= 46:  # devre arası geçtiyse İY skoru kesin
                ht = dg.fm_ht(f["id"])
                if ht is not None:
                    rec["ht"] = ht
        else:
            rec.update(state="canlı?" if ko + dt.timedelta(hours=2, minutes=15) > NOW else "belirsiz", src="fotmob")
    rec["ko"] = f"{m['tarih']} {m['saat']}"
    _cache[code] = rec
    return rec


def IY_ONLY(name: str) -> bool:
    return name.startswith("İY ") and "&" not in name and "2Y" not in name


def grade(name: str, rec: dict):
    """-> (won, durum)"""
    st = rec.get("state")
    if st == "void":
        return None, "iptal/ertelendi"
    if st == "canlı" and rec.get("ht") and IY_ONLY(name):
        w, _, _ = dg.grade(name, dict(rec, state="final", ft=rec["ht"]))
        if w is not None:
            return w, ("tuttu" if w else "yattı") + " (İY kesin, maç sürüyor)"
    if st in ("başlamadı", "canlı", "canlı?"):
        return None, "bekliyor"
    if st != "final":
        return None, "belirsiz"
    w, _, why = dg.grade(name, rec)
    if w is None:
        return None, "belirsiz"  # örn. İY skoru yok
    return w, "tuttu" if w else "yattı"


def find_code(key: str) -> str:
    hits = [c for c, m in MAC.items() if key.lower() in m["mac"].lower()]
    if len(hits) != 1:
        raise SystemExit(f"eşleşme {key!r}: {[MAC[c]['mac'] for c in hits]}")
    return hits[0]


def cand(code, name):
    for u in MAC[code].get("uygun_adaylar") or []:
        if u.get("name") == name:
            return u
    return None


def p_ms(code, name):
    pr = MAC[code].get("olasilik_1x2") or [None] * 3
    return {"MS 1": pr[0], "MS 2": pr[2]}.get(name)


def row(group, key, name, odds=None, note=None):
    code = find_code(key)
    m = MAC[code]
    rec = resolve(code)
    w, durum = grade(name, rec)
    u = cand(code, name)
    p = (u or {}).get("p_cal") or p_ms(code, name)
    if odds is None:
        odds = (u or {}).get("odds")
        if odds is None and name in ("MS 1", "MS 2"):
            odds = (m.get("nesine_ms") or [None] * 3)[0 if name == "MS 1" else 2]
    return {"grup": group, "kod": int(code), "ko": rec["ko"], "mac": m["mac"], "lig": m.get("lig"), "secim": name,
            "aile": (u or {}).get("family") or ("Maç sonucu" if name.startswith("MS") else None),
            "oran": odds, "p": round(p, 4) if p is not None else None, "durum": durum, "won": w,
            "iy": rec.get("ht"), "ms": rec.get("ft"), "canli": rec.get("live"), "dk": rec.get("minute"),
            "kaynak": rec.get("src"), "not": note}


CHAT = [
    ("Sabah seçimleri (banko/yüksek kupon bacakları)", [("Araz", "MS 2"), ("Zizkov", "2Y KG Yok"), ("Erzurum", "İY 1.5 Alt"),
                                   ("Erzurum", "İY 0.5 Üst"), ("Batman", "3.5 Alt"), ("Getafe B", "İY 0.5 Üst"),
                                   ("Pena Deportiva", "İY 0.5 Üst")]),
    ("Gündüz seçimleri", [("Beveren", "3.5 Alt"), ("Esenler", "3.5 Alt"), ("Twente - Willem", "İY 2.5 Alt"),
                          ("UD Ourense - Racing", "İY 1.5 Alt"), ("Cottbus", "4.5 Alt"), ("Horsens", "İY 0.5 Üst"),
                          ("Kasımpaşa", "İY 0.5 Üst"), ("Altach", "İY 0.5 Üst")]),
    ("Dengeli 1X2 – model eğilimi", [("Pena Deportiva", "MS 2"), ("D. Moskova - Krasnodar", "MS 1"),
                                     ("Getafe B", "MS 1"), ("Ramnicu", "MS 2"), ("Erzurum", "MS 2"),
                                     ("Mallorca B", "MS 2")]),
    ("15:56 en banko listesi", [("Marsilya", "DEĞİL(Dep En Az Bir Yarıyı Kazanır)"), ("Avellino", "İY ÇŞ X2"),
                                ("S. Rotterdam", "Dep En Az Bir Yarıyı Kazanır"), ("Trabzonspor - Eyüp", "4.5 Alt"),
                                ("Cacereno", "3.5 Alt"), ("Nashville", "DEĞİL(Dep En Az Bir Yarıyı Kazanır)"),
                                ("River Plate - Lanus", "DEĞİL(Dep En Az Bir Yarıyı Kazanır)"),
                                ("Fluminense", "Ev En Az Bir Yarıyı Kazanır"),
                                ("Kortrijk", "MS 2"), ("Lorient", "1.5 Üst"), ("Nordsjælland", "İY 0.5 Üst"),
                                ("Celta Vigo B", "İY 0.5 Üst"), ("Girona - Eibar", "3.5 Alt"),
                                ("Getafe - Atl", "İY 1.5 Alt"), ("Bragantino", "İY ÇŞ X2"), ("Whitecaps", "4.5 Alt")]),
    ("10'lu 1/2 kuponu (ilk, 1.20 altı bacaklı)", [("D. Zagreb", "MS 1", 1.06), ("Rogachev", "MS 1", 1.10),
                                                   ("Paris - Angers", "MS 1", 1.16), ("Farense", "MS 1", 1.08),
                                                   ("Beerschot", "MS 1", 1.16), ("Kortrijk", "MS 2", 1.21),
                                                   ("Panathinaikos", "MS 1", 1.06), ("Rijeka", "MS 1", 1.18),
                                                   ("PAOK", "MS 1", 1.18), ("Strongest", "MS 1", 1.15)]),
    ("10'lu 1/2 kuponu (düzeltilmiş, ≥1.20)", [("Maribor", "MS 1", 1.26), ("Hull City - Brighton", "MS 2", 1.28),
                                              ("Kortrijk", "MS 2", 1.21), ("Celje", "MS 1", 1.20),
                                              ("Sarajevo", "MS 1", 1.21), ("Dunajska", "MS 1", 1.23),
                                              ("Anderlecht", "MS 1", 1.30), ("Rosario", "MS 1", 1.23),
                                              ("Marsilya", "MS 1", 1.29), ("S. Cristal", "MS 1", 1.22)]),
]
chat_rows = []
for g, items in CHAT:
    for it in items:
        chat_rows.append(row(g, it[0], it[1], it[2] if len(it) > 2 else None))


def coupon_status(rs):
    ws = [r["won"] for r in rs]
    if any(w is False for w in ws):
        return "KAYBETTİ"
    if all(w is True for w in ws):
        return "KAZANDI"
    return "BEKLİYOR"


coupons = {}
for g, _ in CHAT:
    if g.startswith("10'lu"):
        rs = [r for r in chat_rows if r["grup"] == g]
        coupons[g] = {"durum": coupon_status(rs), "tuttu": sum(r["won"] is True for r in rs),
                      "yattı": sum(r["won"] is False for r in rs), "bekleyen": sum(r["won"] is None for r in rs)}
for nm, legs in (("A banko (5)", A["kupon_banko"]), ("A yüksek (6)", A["kupon_yuksek"]),
                 ("Gün kupon_a", GN["kupon_a"]), ("Gün kupon_b", GN["kupon_b"]), ("Gün kupon_c", GN["kupon_c"])):
    rs = [row("kupon", b["mac"], b["kisa"]) if True else None for b in legs["bacaklar"]]
    coupons[nm] = {"oran": legs.get("toplam_oran"), "p_model": legs.get("tutma_olasiligi"), "durum": coupon_status(rs),
                   "bacaklar": [{k: r[k] for k in ("ko", "mac", "secim", "oran", "p", "durum", "iy", "ms", "canli", "dk")} for r in rs]}

# ---- ek kuponlar: 4'lü öneri, gece_kupon_0709 A/B/C, oynanan kuponlar (22 Kas bacaklı)
def reg(code, ko, mac):
    code = str(code)
    if code not in MAC:
        if "." in ko[:6]:  # "22.11 08:00"
            dd, mm = ko[:5].split(".")
            tarih, saat = f"2026-{mm}-{dd}", ko[6:11]
        else:
            tarih, saat = ko[:10], ko[11:16]
        MAC[code] = {"kod": code, "tarih": tarih, "saat": saat, "mac": mac, "uygun_adaylar": [], "_src": "kupon"}
    return code


def row_code(group, code, ko, mac, name, odds, p=None):
    code = reg(code, ko, mac)
    rec = resolve(code)
    w, durum = grade(name, rec)
    return {"grup": group, "kod": int(code), "ko": rec["ko"], "mac": MAC[code]["mac"], "secim": name, "oran": odds, "p": p,
            "durum": durum, "won": w, "iy": rec.get("ht"), "ms": rec.get("ft"), "canli": rec.get("live"),
            "dk": rec.get("minute"), "kaynak": rec.get("src")}


def pack(rs, oran=None, p_model=None, extra=None):
    d = {"oran": oran, "p_model": p_model, "durum": coupon_status(rs),
         "bacaklar": [{k: r[k] for k in ("ko", "mac", "secim", "oran", "p", "durum", "iy", "ms", "canli", "dk")} for r in rs]}
    d.update(extra or {})
    return d


_q = [r for r in chat_rows if r["grup"].startswith("10'lu 1/2 kuponu (düzeltilmiş")][:4]
coupons["4'lü öneri (Maribor, Brighton, USG, Celje)"] = pack(_q, round(1.26 * 1.28 * 1.21 * 1.20, 2))
for k in ("10'lu 1/2 kuponu (ilk, 1.20 altı bacaklı)", "10'lu 1/2 kuponu (düzeltilmiş, ≥1.20)"):
    rs = [r for r in chat_rows if r["grup"] == k]
    o_ = 1.0
    for r in rs:
        o_ *= r["oran"]
    coupons[k] = pack(rs, round(o_, 2))
_c0709 = json.load(open(D / "gece_kupon_0709.json"))["coupons"]
for cid in ("A", "B", "C"):
    c = _c0709[cid]
    rs = [row_code("0709", l["code"], l["kickoff_tsi"], l["match"], l.get("rule_name") or l["pick"], l["nesine_odds"], l.get("p_cal"))
          for l in c["legs"]]
    coupons[f"gece_kupon_0709 {cid} — {c['title']}"] = pack(rs, c.get("total_odds"), c.get("p_win"))
_log = json.load(open(G / "oynanan_kuponlar.json"))
_old = {c["id"]: c for c in json.load(open(D / "denetim_2026-11-22_raw.json"))["coupons"]}
OYNANAN = {}
for cid, key in (("MS10", "MS10"), ("K2000", "K2000"), ("GECE-5.00", "GECE-5.00"), ("0709-C (20.30)", "0709-C (20.30)")):
    oc = _old[key]
    rs = [row_code("oynanan", l["code"], l["ko"], l["match"], l["name"], l["odds"], l.get("p")) for l in oc["legs"]]
    OYNANAN[cid] = pack(rs, oc["odds"], None, {"stake": oc["stake"], "placed": oc["placed"]})
    st = OYNANAN[cid]["durum"]
    OYNANAN[cid]["donen_tl"] = round(oc["stake"] * oc["odds"], 2) if st == "KAZANDI" else (0 if st == "KAYBETTİ" else None)

# ---- havuz: P≥0.65 en iyi seçim (maç başına 1) ve tüm P≥0.65 uygun adaylar
pool_best, pool_all = [], []
for code, m in list(MAC.items()):
    if m["_src"] == "kupon":
        continue
    cs = [u for u in (m.get("uygun_adaylar") or []) if (u.get("p_cal") or 0) >= 0.65 and (u.get("odds") or 0) >= 1.20]
    if not cs:
        continue
    rec = resolve(code)
    for i, u in enumerate(sorted(cs, key=lambda u: -u["p_cal"])):
        w, durum = grade(u["name"], rec)
        r = {"kod": int(code), "ko": rec["ko"], "mac": m["mac"], "lig": m.get("lig"), "secim": u["name"],
             "aile": u.get("family"), "oran": u.get("odds"), "p": round(u["p_cal"], 4), "katman": m.get("fiyat_katmani"),
             "verdict": u.get("verdict"), "durum": durum, "won": w, "iy": rec.get("ht"), "ms": rec.get("ft"),
             "kaynak": rec.get("src"), "dosya": m["_src"]}
        pool_all.append(r)
        if i == 0:
            pool_best.append(r)


def summ(rs):
    g = [x for x in rs if x["won"] in (True, False)]
    n, w = len(g), sum(1 for x in g if x["won"])
    ps = [x["p"] for x in g if x.get("p") is not None]
    return {"n": n, "tuttu": w, "yattı": n - w, "bekleyen": sum(x["durum"] == "bekliyor" for x in rs),
            "belirsiz": sum(x["durum"] in ("belirsiz", "iptal/ertelendi") for x in rs),
            "isabet": round(w / n, 4) if n else None, "ort_p": round(sum(ps) / len(ps), 4) if ps else None,
            "fark": round(w / n - sum(ps) / len(ps), 4) if n and ps else None}


def by(rs, f):
    d = defaultdict(list)
    for x in rs:
        d[f(x)].append(x)
    return dict(sorted(((k, summ(v)) for k, v in d.items()), key=lambda kv: (-kv[1]["n"], str(kv[0]))))


def band(p):
    if p is None:
        return "?"
    for lo, hi, lab in ((0, .55, "<55"), (.55, .60, "55-60"), (.60, .65, "60-65"), (.65, .70, "65-70"), (.70, .75, "70-75"), (.75, 2, "75+")):
        if lo <= p < hi:
            return lab


uniq = {}
for r in chat_rows:
    uniq[(r["kod"], r["secim"])] = r
chat_uniq = list(uniq.values())
out = {
    "generated_at": NOW.strftime("%Y-%m-%d %H:%M TSİ"),
    "kaynaklar": ["Nesine GetUnliveMatches 21-23 Kas (İY+90')", "FotMob herkese açık JSON (Nesine'de bitmeyenler, İY matchDetails)"],
    "ozet": {"sohbet_tekil": summ(chat_uniq), "havuz_en_iyi_P65": summ(pool_best), "havuz_tum_P65": summ(pool_all)},
    "sohbet_grup": by(chat_rows, lambda x: x["grup"]),
    "sohbet_aile": by(chat_uniq, lambda x: x["aile"] or "?"),
    "havuz_en_iyi_aile": by(pool_best, lambda x: x["aile"] or "?"),
    "havuz_en_iyi_band": by(pool_best, lambda x: band(x["p"])),
    "havuz_tum_aile": by(pool_all, lambda x: x["aile"] or "?"),
    "havuz_tum_band": by(pool_all, lambda x: band(x["p"])),
    "havuz_en_iyi_secim": by(pool_best, lambda x: x["secim"]),
    "havuz_en_iyi_katman": by(pool_best, lambda x: x["katman"] or "?"),
    "kuponlar": coupons,
    "oynanan_kuponlar": OYNANAN,
    "sohbet_secimleri": chat_rows,
    "havuz_en_iyi": pool_best,
    "havuz_tum": pool_all,
}
dg.save_json(D / f"denetim_gun_{OUT}_raw.json", out)
print(json.dumps(out["ozet"], ensure_ascii=False))
for r in chat_rows:
    print(r["grup"][:12], r["ko"][11:], r["mac"], "|", r["secim"], r["oran"], r["p"], "|", r["iy"], r["ms"], r["canli"], r["durum"], r["kaynak"])
for k, v in coupons.items():
    print(k, v["durum"])
