"""Bütün AI çıktılarını topla ve Nesine sonuçlarıyla yeniden notla."""
import csv, json, re, glob
from ortak import *

ROWS, COUPONS = [], []
GR = ARS / "tahminler/grokbottahmin"
LOC = Path("/workspace/futbol-dehasi/tahminler/grokbottahmin/2026-11-22")


def surum(date):
    return "eski (≤22 Kas)" if date <= "2026-11-22" else "yeni (≥23 Kas)"


def lab_canon(pk):
    """degerlendirme etiketi -> kısa ad + aile."""
    m, _, s = pk.partition(":"); m = m.strip(); s = s.strip().replace(",", ".")
    if m.startswith("Maç Sonucu ve"): return "MS " + s, "Kombine"
    if m.startswith("Maç Sonucu"): return ("MS " + s), "Maç sonucu"
    if m.startswith("1. Yarı / 2. Yarı"): return "İY/2Y KG " + s, "Yarı KG"
    if m.startswith("2. Yarı Karşılıklı"): return "2Y KG " + s, "2Y KG"
    if m.startswith("1. Yarı Karşılıklı"): return "İY KG " + s, "Yarı KG"
    if m.startswith("1. Yarı Çifte"): return "İY ÇŞ " + s, "İY çifte şans"
    if m.startswith("1. Yarı Sonucu"): return "İY " + s, "İY sonucu"
    if m.startswith("1. Yarı Tek"): return "İY " + s, "Tek/Çift"
    if m.startswith("1. Yarı") and "Alt/Üst" in m: return "İY " + s, "İY Alt/Üst"
    if ("1.Y" in m) and (m.startswith("Ev") or m.startswith("Dep")): return s, "Takım İY gol"
    if "İki Yarıda" in m: return m + " " + s, "Takım gol"
    if "Yarıyı" in m: return m + " " + s, "Yarı özel"
    if "Hangi Yarıda" in m: return m + " " + s, "Yarı özel"
    if m.startswith(("Ev Sahibi", "Deplasman")): return ("Ev " if m.startswith("Ev") else "Dep ") + s, "Takım gol"
    if m.startswith("Karşılıklı"): return "KG " + s, "KG"
    if m.startswith("Çifte"): return "ÇŞ " + s, "Çifte şans"
    if m.startswith("İlk Gol"): return "İlk gol " + s, "İlk gol"
    if m.startswith("Handikap"): return s, "Handikap"
    if "Alt/Üst ve Karşılıklı" in m: return s, "Kombine"
    if "Alt/Üst" in m: return s, "Alt/Üst"
    return pk, "Diğer"


def rule_viol(fam, name, odds, p):
    v = []
    if fam in BANNED_USER or (fam == "2Y KG" and "Yok" not in name) or fam == "Tek/Çift":
        v.append("yasak_aile")
    if re.search(r"(^| )(MS|İY|2Y) (0|X)$", name): v.append("beraberlik")
    if odds is not None and odds < 1.20: v.append("oran<1.20")
    if odds is not None and odds > 1.80: v.append("oran>1.80")
    if p is not None and p < 0.65: v.append("P<0.65")
    if p is not None and 0.65 <= p < 0.70: v.append("P 0.65-0.70")
    return v


def add(ai, date, kind, match, name, fam, odds, p, won, code=None, self_won=None, src="", extra=None):
    r = dict(ai=ai, tarih=date, surum=surum(date), tur=kind, mac=match, secim=name, aile=fam,
             oran=odds, odds=odds, p=p, won=won, kod=code, oz_beyan=self_won, kaynak=src,
             ihlal=rule_viol(fam, name, odds, p))
    if extra: r.update(extra)
    ROWS.append(r); return r


def fnum(x):
    try:
        x = str(x).replace("%", "").strip()
        return float(x.replace(",", ".")) if x not in ("", "None", "nan") else None
    except Exception:
        return None


def coupon(ai, date, cid, legs, odds=None, stake=None, played=False, self_status=None, note=""):
    lw = [l["won"] for l in legs]
    if any(w is False for w in lw): st = "kaybetti"
    elif lw and all(w is True for w in lw): st = "kazandı"
    else: st = "belirsiz"
    if odds is None:
        odds = 1.0
        for l in legs: odds *= (l.get("odds") or 1.0)
        odds = round(odds, 2)
    COUPONS.append(dict(ai=ai, tarih=date, surum=surum(date), id=cid, bacak=len(legs), oran=odds, stake=stake,
                        oynandi=played, durum=st, oz_beyan=self_status,
                        tutan_bacak=sum(1 for w in lw if w is True), yatan_bacak=sum(1 for w in lw if w is False),
                        belirsiz_bacak=sum(1 for w in lw if w is None),
                        donus=(round(stake * odds, 2) if (st == "kazandı" and stake) else (0 if stake and st == "kaybetti" else None)),
                        ihlalli_bacak=sum(1 for l in legs if l.get("ihlal")), not_=note,
                        legs=[{k: l.get(k) for k in ("mac", "secim", "odds", "p", "won", "aile", "ihlal")} for l in legs]))


# 1) degerlendirme ana tercihleri (Nesine kodu ile; won = ortak karne + yeniden notlama denemesi)
for f in sorted(glob.glob(str(ARS / "degerlendirme/2026-11-*.json"))):
    d = json.load(open(f)); date = d["date"]
    for code, m in d["matches"].items():
        for ai, pk in m["picks"].items():
            if ai == "grokbottahmin":
                continue  # grokbot kendi denetim dosyalarından alınır (daha geniş)
            name, fam = lab_canon(pk["pick"])
            rec = NES.get(int(code))
            add(ai, date, "ana_secim", m["match"], name, fam, pk.get("odds"), pk.get("p"), pk.get("won"),
                code=int(code), src="degerlendirme+Nesine")
    for ai, a in d["ais"].items():
        if ai == "grokbottahmin":
            continue
        for c in a.get("coupons") or []:
            n = c.get("legs") or 0; lw = c.get("legs_won") or 0
            legs = [{"won": True}] * lw + [{"won": False}] * (n - lw) if c.get("won") is not None else [{"won": None}] * n
            COUPONS.append(dict(ai=ai, tarih=date, surum=surum(date), id=c["coupon"], bacak=n, oran=c.get("odds"),
                                stake=None, oynandi=False, durum=("kazandı" if c.get("won") else "kaybetti") if c.get("won") is not None else "belirsiz",
                                oz_beyan=None, tutan_bacak=lw, yatan_bacak=n - lw if c.get("won") is not None else 0,
                                belirsiz_bacak=0, donus=None, ihlalli_bacak=None, not_="ortak karneden (degerlendirme)",
                                legs=[{"secim": x} for x in c.get("lost_legs") or []]))


# 2) Gemini CSV'leri (kendi şeması; ortak karne 'incompatible' sayıp hiç notlamadı)
MANUAL = {"Southern District - BC Rangers": 3313898, "Ferencvaros - Gyori ETO": 3313417,
          "Norwich City - Queens Park Rangers": 3322092, "Arsenal - Borussia Dortmund": 3322088,
          "Bolton Wanderers - West Bromwich Albion": 3324126, "Brighton & Hove Albion - Universitatea Craiova": 3326577,
          "Kauno Žalgiris - Riga FC": 3326547, "KAA Gent - Crvena Zvezda": 3326651,
          "Inter Club d'Escaldes - FC København": 3326548, "Beşiktaş JK - Hapoel Be'er Sheva": 3326581,
          "Olympique de Marseille - Levski Sofia": 3326632, "Olympiacos Piraeus - AC Milan": 3326567,
          "Sunderland AFC - Jagiellonia Białystok": 3326621, "PKR Svay Rieng - FC Machida Zelvia": 3326316,
          "Dinamo Bucuresti - Petrolul Ploiesti": 3314719, "Lokomotiv Moscow - FC Rostov": 3321900,
          "Dinamo Makhachkala - Baltika Kaliningrad": 3321944, "Heart of Midlothian - AS Monaco": 3326536,
          "Dinamo Zagreb - Bayer 04 Leverkusen": 3326628, "Al-Faisaly Harmah - Al-Diriyah": 3389697}


def gem_match(date, mac=None, home=None, away=None):
    key = mac or f"{home} - {away}"
    if key in MANUAL:
        return NES[MANUAL[key]], 1.0
    if mac:
        home, away = split2(mac)
    r, s = find(home, away, days_around(date))
    return r, s


def split2(mac):
    p = re.split(r"\s+-\s+", mac, maxsplit=1)
    return (p[0], p[1]) if len(p) == 2 else (mac, "")


def selfw(x):
    x = (x or "").upper()
    if "DOĞRU" in x or "TUTTU" in x or "KAZANDI" in x: return True
    if "YANLIŞ" in x or "KAYBETT" in x or "YATTI" in x: return False
    return None


GD = ARS / "tahminler/geminitahmin"
unmatched = []
def gem_leg(date, mac, sel, odds, p, kind, selfr=None, home=None, away=None):
    r, s = gem_match(date, mac, home, away)
    name = canon(sel)
    w = grade(name, r) if r else None
    if not r: unmatched.append((date, mac or f"{home} - {away}", s))
    return add("geminitahmin", date, kind, mac or f"{home} - {away}", name, family(name), odds, p, w,
               code=r["code"] if r else None, self_won=selfr, src="Gemini CSV + Nesine")

# 20 Kas
for row in csv.DictReader(open(GD / "2026-11-20/mac_tahminleri.csv", encoding="utf-8-sig")):
    if row.get("ana_secim"):
        gem_leg("2026-11-20", row["mac"], row["ana_secim"], fnum(row["nesine_oran"]), fnum(row["olasilik"]), "ana_secim")
cp = {}
for row in csv.DictReader(open(GD / "2026-11-20/kuponlar.csv", encoding="utf-8-sig")):
    cp.setdefault(row["kupon"] + "#" + row["kupon_no"], []).append(row)
for cid, rs in cp.items():
    legs = [gem_leg("2026-11-20", r["mac"], r["secim"], fnum(r["nesine_oran"]), fnum(r["olasilik"]), "kupon_bacak") for r in rs]
    coupon("geminitahmin", "2026-11-20", cid, legs, odds=fnum(rs[0]["kupon_toplam_oran"]))
# 21 Kas
for row in csv.DictReader(open(GD / "2026-11-21/mac_tahminleri.csv", encoding="utf-8-sig")):
    p = fnum(row["kalibre_olasilik_pct"]); p = p / 100 if p and p > 1 else p
    gem_leg("2026-11-21", row["mac"], row["ana_tahmin"], fnum(row["oran"]), p, "ana_secim", selfw(row.get("durum")))
cp = {}
for row in csv.DictReader(open(GD / "2026-11-21/kuponlar.csv", encoding="utf-8-sig")):
    cp.setdefault(row["kupon_adi"], []).append(row)
for cid, rs in cp.items():
    legs = [gem_leg("2026-11-21", r["mac"], r["tercih"], fnum(r["nesine_oran"]), None, "kupon_bacak", selfw(r.get("ayak_durumu"))) for r in rs]
    coupon("geminitahmin", "2026-11-21", cid, legs, odds=fnum(rs[0]["toplam_oran"]), stake=fnum(rs[0]["bahis_tl"]),
           played=False, self_status=rs[0].get("durum"), note="bahis_tl CSV'de yazıyor; gerçekten oynandığı kanıtlanmadı")
# 24 / 25 Kas
for date in ("2026-11-24", "2026-11-25"):
    for row in csv.DictReader(open(GD / f"{date}/mac_tahminleri.csv", encoding="utf-8-sig")):
        gem_leg(date, None, row["ana_tercih"], fnum(row["tercih_orani"]), fnum(row["p_kalibre"]), "ana_secim",
                home=row["ev_sahibi"], away=row["deplasman"])
cp = {}
for row in csv.DictReader(open(GD / "2026-11-24/kuponlar.csv", encoding="utf-8-sig")):
    cp.setdefault(row["kupon_id"], []).append(row)
for cid, rs in cp.items():
    legs = [gem_leg("2026-11-24", r["mac"], r["tercih"], fnum(r["oran"]), fnum(r["p_kalibre"]), "kupon_bacak") for r in rs]
    coupon("geminitahmin", "2026-11-24", cid, legs, odds=fnum(rs[0]["kupon_toplam_oran"]))
LEGRE = re.compile(r"^\s*(\d{1,2}:\d{2})\s+(.+?):\s+(.+?)\s+\(([\d.,]+)\)\s*$")
for row in csv.DictReader(open(GD / "2026-11-25/kuponlar.csv", encoding="utf-8-sig")):
    legs = []
    for part in row["bacaklar_detay"].split("|"):
        m = LEGRE.match(part)
        if not m:
            legs.append({"won": None, "secim": part}); continue
        legs.append(gem_leg("2026-11-25", m.group(2), m.group(3), fnum(m.group(4)), None, "kupon_bacak"))
    coupon("geminitahmin", "2026-11-25", row["kupon_id"], legs, odds=fnum(row["toplam_oran"]))
# 26 Kas
for row in csv.DictReader(open(GD / "2026-11-26/mac_tahminleri.csv", encoding="utf-8-sig")):
    gem_leg("2026-11-26", row["mac"], row["ana_tercih"], fnum(row["ana_oran"]), None, "ana_secim", selfw(row.get("ana_sonuc")))
cp = {}
for row in csv.DictReader(open(GD / "2026-11-26/kuponlar.csv", encoding="utf-8-sig")):
    cp.setdefault(row["kupon_id"], []).append(row)
for cid, rs in cp.items():
    legs = [gem_leg("2026-11-26", r["mac"], r["tercih"], fnum(r["oran"]), None, "kupon_bacak", selfw(r.get("bacak_sonucu"))) for r in rs]
    coupon("geminitahmin", "2026-11-26", cid, legs, odds=fnum(rs[0]["kupon_toplam_oran"]), self_status=rs[0].get("kupon_sonucu"))


# 3) Grokbot (benim) — 21 Kas CSV ana seçimleri, 22 Kas sohbet + havuz en iyi (denetim_gun_2100), oynanan kuponlar
def gb_leg(date, code, mac, name, odds, p, kind, extra=None):
    rec = NES.get(int(code)) if code else None
    if rec is None and mac:
        rec, _ = find(*split2(mac), days_around(date))
    n = canon(name)
    return add("grokbottahmin", date, kind, mac, n, family(n), odds, p, grade(n, rec), code=code, src="grokbot + Nesine", extra=extra)

for date in ("2026-11-21", "2026-11-22"):
    for row in csv.DictReader(open(GR / f"{date}/mac_tahminleri.csv", encoding="utf-8-sig")):
        nm = row.get("secim_adi") or row.get("ana_secim")
        if not nm: continue
        gb_leg(row["saat"] and date, fnum(row["nesine_kodu"]) and int(fnum(row["nesine_kodu"])), row["mac"], nm,
               fnum(row["nesine_oran"]), fnum(row["olasilik"]), "ana_secim_csv")
d = json.load(open(LOC / "denetim_gun_2100.json"))
seen = set()
for r in d["sohbet_secimleri"]:
    gb_leg("2026-11-22", r["kod"], r["mac"], r["secim"], r.get("oran"), r.get("p"), "sohbet_secim", {"grup": r.get("grup")})
for r in d["havuz_en_iyi"]:
    gb_leg("2026-11-22", r["kod"], r["mac"], r["secim"], r.get("oran"), r.get("p"), "havuz_en_iyi", {"katman": r.get("katman")})
for cname, c in d["kuponlar"].items():
    legs = []
    for b in c.get("bacaklar") or []:
        legs.append(gb_leg("2026-11-22", b.get("kod"), b.get("mac"), b.get("secim"), b.get("oran"), b.get("p"), "kupon_bacak"))
    if legs:
        coupon("grokbottahmin", "2026-11-22", cname, legs, odds=c.get("oran"), self_status=c.get("durum"))
ok = json.load(open("/workspace/futbol-dehasi/tahminler/grokbottahmin/oynanan_kuponlar.json"))
for i, c in enumerate(ok["coupons"]):
    legs = []
    for b in c["legs"]:
        if isinstance(b, dict):
            legs.append(gb_leg((b.get("ko") or "2026-11-21")[:10], b.get("code"), b.get("match"), b.get("name") or b.get("sel") or b.get("pick"), b.get("odds"), b.get("p"), "oynanan_bacak"))
        else:
            legs.append(gb_leg("2026-11-21", b[1], b[2], b[3], b[4], None, "oynanan_bacak"))
    coupon("grokbottahmin", "2026-11-21", c.get("id") or f"GECE-5.00", legs, odds=c.get("odds") or c.get("total_odds"),
           stake=c.get("stake"), played=True, self_status=c.get("status"), note=c.get("note") or c.get("mode") or "")
for c in ok["kuponlar"]:
    legs = [gb_leg("2026-11-22", b[1], b[2], b[3], b[4], None, "oynanan_bacak") for b in c["legs"]]
    coupon("grokbottahmin", "2026-11-22", "0709-C (20.30)", legs, odds=c["total_odds"], stake=c["stake"], played=True,
           self_status=c.get("status"), note=c.get("type"))

json.dump(ROWS, open(OUT / "rows.json", "w"), ensure_ascii=False, indent=0, default=str)
json.dump(COUPONS, open(OUT / "coupons.json", "w"), ensure_ascii=False, indent=0, default=str)
json.dump(unmatched, open(OUT / "eslesmeyen_gemini.json", "w"), ensure_ascii=False, indent=0)
print(len(ROWS), len(COUPONS), "eşleşmeyen gemini:", len(unmatched))
