"""Ortak yardımcılar: Nesine sonuç dizini, isim eşleme, notlama, aile ve P bandı."""
import json, re, sys, glob
from pathlib import Path
sys.path.insert(0, "/workspace/fd_base_8ff235c/src")
from quantfoot.evaluation.settlement import settle_selection
from quantfoot.data.match_dossier import team_match_score

OUT = Path("/workspace/fd_denetim_2026-11-28")
ARS = OUT / "arsiv"
FIN = {"MS", "UZT", "PEN"}
NEED_HT = re.compile(r"İY|2Y|Yarı|İlk Gol|En Çok Gol")

NES = {}   # code -> rec
BYDAY = {}  # date -> [rec]
for f in sorted(glob.glob(str(OUT / "sonuc/unlive_*.json"))):
    day = f.split("unlive_")[1][:10]
    for m in json.load(open(f)).get("d") or []:
        try:
            code = int(m["C"])
        except Exception:
            continue
        sc = {e.get("T"): (int(e.get("H", 0)), int(e.get("A", 0))) for e in m.get("ES") or []}
        rec = {"code": code, "day": day, "md": (m.get("MD") or "")[:16], "home": m.get("HTTR") or m.get("HT") or "",
               "away": m.get("ATTR") or m.get("AT") or "", "league": m.get("L"), "st": m.get("ST")}
        if m.get("ST") in FIN and 2 in sc and (3 in sc or 1 in sc):
            rec.update(state="final", ht=list(sc[2]), ft=list(sc.get(3, sc.get(1))))
        elif m.get("ST") in ("Ert.", "Ksl."):
            rec.update(state="void")
        else:
            rec.update(state="acik")
        NES[code] = rec
        BYDAY.setdefault(day, []).append(rec)

ALIAS = {"inter milan": "inter", "fc barcelona": "barcelona", "atlético madrid": "atl. madrid",
         "atletico madrid": "atl. madrid", "manchester city": "man. city", "manchester united": "man. united"}


def _n(s):
    s = (s or "").strip()
    return ALIAS.get(s.lower(), s)


def find(home, away, days, min_score=0.70):
    best, bs = None, 0.0
    for d in days:
        for r in BYDAY.get(d, []):
            s = min(team_match_score(_n(home), r["home"]), team_match_score(_n(away), r["away"]))
            if s > bs:
                best, bs = r, s
    return (best, round(bs, 3)) if bs >= min_score else (None, round(bs, 3))


def days_around(date):
    import datetime as dt
    d = dt.date.fromisoformat(date)
    return [str(d), str(d + dt.timedelta(days=1)), str(d - dt.timedelta(days=1))]


def canon(name):
    n = (name or "").strip().replace(",", ".")
    n = re.sub(r"\s+", " ", n)
    if not n.startswith(("DEĞİL(", "Hnd(")):
        n = re.sub(r"\s*\((?!\d+:\d+\)).*?\)\s*$", "", n).strip()
    n = n.replace("Her İki Yarıda KG Var", "İki Yarıda KG Var")
    n = re.sub(r"ÇŞ X-2", "ÇŞ X2", n); n = re.sub(r"ÇŞ 1-X", "ÇŞ 1X", n); n = re.sub(r"ÇŞ 1-2", "ÇŞ 12", n)
    n = re.sub(r"^TG (\d)-(\d)( Gol)?$", r"\1-\2 Gol", n)
    n = re.sub(r"^Kesin Skor: ?", "Skor ", n)
    if n in ("1", "2"):
        n = "MS " + n
    n = n.replace("İY ÇŞ", "İY ÇŞ").replace("Dep. ", "Dep ").replace("Ev. ", "Ev ")
    return n


def grade(name, rec):
    """True/False/None ; None = belirsiz (sonuç yok, iptal, ya da seçim notlanamadı)."""
    if not rec or rec.get("state") != "final":
        return None
    n = canon(name)
    ht, ft = rec.get("ht"), rec.get("ft")
    try:
        return settle_selection(n, tuple(ht), tuple(ft))
    except Exception:
        return None


def family(name):
    n = canon(name)
    if n.startswith("İY/MS"): return "İY/MS"
    if "Skor" in n: return "Skor"
    if "&" in n: return "Kombine"
    if n.startswith("DEĞİL(") or "Yarıyı" in n or "Yarıda" in n:
        return "Yarı özel" if "KG" not in n else "Yarı KG"
    if "2Y KG" in n: return "2Y KG"
    if "İY KG" in n: return "Yarı KG"
    if n.startswith(("Ev İY", "Dep İY")): return "Takım İY gol"
    if n.startswith(("Ev ", "Dep ")): return "Takım gol"
    if n.startswith("İY ÇŞ"): return "İY çifte şans"
    if re.match(r"İY [012X]$", n): return "İY sonucu"
    if n.startswith("İY") and ("Alt" in n or "Üst" in n): return "İY Alt/Üst"
    if n.startswith("2Y"): return "2. yarı"
    if n.startswith("ÇŞ"): return "Çifte şans"
    if n.startswith("MS"): return "Maç sonucu"
    if n.startswith("KG"): return "KG"
    if "Gol" in n and "-" in n: return "Gol aralığı"
    if "Alt" in n or "Üst" in n: return "Alt/Üst"
    if n.startswith(("İlk Gol", "İlk gol")): return "İlk gol"
    if n.startswith("Hnd"): return "Handikap"
    return "Diğer"


BANNED_USER = {"KG", "Takım gol", "Takım İY gol", "İlk gol", "Skor", "İY/MS", "Yarı KG"}


def violates_user_rules(name, odds, p):
    """Ramazan'ın 22 Kas kuralları: P≥0.65 (hedef 0.70), oran 1.20–1.80, beraberlik/KG/ilk gol/takım gol yok."""
    n = canon(name); v = []
    fam = family(n)
    if fam in BANNED_USER or (fam == "2Y KG" and n != "2Y KG Yok"):
        v.append("yasak_aile")
    if re.search(r"(^| )(MS|İY|2Y) (0|X)$", n) or n.endswith("/X") or "Skor 0-0" in n:
        v.append("beraberlik")
    if "&" in n and "KG" in n:
        v.append("yasak_aile")
    if odds is not None:
        if odds < 1.20: v.append("oran<1.20")
        if odds > 1.80: v.append("oran>1.80")
    if p is not None and p < 0.65:
        v.append("P<0.65")
    return sorted(set(v))


def pband(p):
    if p is None: return "P yok"
    for lo, hi in ((0, .5), (.5, .55), (.55, .6), (.6, .65), (.65, .7), (.7, .75), (.75, .8), (.8, 1.01)):
        if lo <= p < hi:
            return f"{int(lo*100)}-{int(hi*100) if hi<1 else 100}"


def oband(o):
    if o is None: return "oran yok"
    for lo, hi in ((1.0, 1.2), (1.2, 1.4), (1.4, 1.6), (1.6, 1.8), (1.8, 2.2), (2.2, 3.0), (3.0, 1e9)):
        if lo <= o < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi < 1e8 else "3.00+"


def summ(rows):
    g = [r for r in rows if r.get("won") is not None]
    w = sum(1 for r in g if r["won"])
    ps = [r["p"] for r in g if r.get("p") is not None]
    flat = [((r["odds"] - 1) if r["won"] else -1) for r in g if r.get("odds")]
    return {"n": len(rows), "notlanan": len(g), "tuttu": w, "belirsiz": len(rows) - len(g),
            "isabet": round(w / len(g), 4) if g else None,
            "ort_p": round(sum(ps) / len(ps), 4) if ps else None,
            "ort_oran": round(sum(r["odds"] for r in g if r.get("odds")) / max(1, sum(1 for r in g if r.get("odds"))), 3) if g else None,
            "birim_getiri": round(sum(flat), 2) if flat else None,
            "roi": round(sum(flat) / len(flat), 4) if flat else None}
