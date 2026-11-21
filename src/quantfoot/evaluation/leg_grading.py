"""Bacak notlama — Nesine tarzı seçim adlarını İY/MS skoruyla karara bağlar (21 Kasım denetiminden repoya taşındı).

``grade(leg, result)`` maç bittiğinde True/False/None, ``early_decide`` canlıda matematiksel olarak kesinleşmiş
bacaklar için. ``leg``: market / sel / name alanları (Nesine pazar adı, seçim, kısa ad). ``result``: state ('bitti',
'canlı', 'başlamadı', 'eşleşmedi'), ht/ft [ev, dep], score, minute. Sonuç uydurulmaz: belirlenemeyen None döner.

``fetch_result`` FotMob'dan sonucu çeker (API-Football kullanılmaz); ``market_family`` kalibrasyon defteri için aile.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

TSI = dt.timezone(dt.timedelta(hours=3))


def market_family(leg: dict) -> str:
    """Kalibrasyon ailesi (defter ve karışım ağırlıkları için kaba sınıflama)."""
    name = f"{leg.get('market') or ''} | {leg.get('sel') or ''} | {leg.get('name') or ''}"
    nm = leg.get("name") or ""
    if leg.get("live") or "Canlı" in name:
        return "canli"
    if nm == "KGKG" or "Evet/Evet" in name:
        return "kg_iki_yari"
    if nm.startswith("İYMS") or "İlk Yarı / Maç Sonucu" in name:
        return "iyms"
    if "&" in name or " ve " in (leg.get("sel") or ""):
        return "kombine"
    if "Handikap" in name:
        return "handikap"
    if re.search(r"İY|1\. Yarı|2Y|İlk Yarı", name):
        return "yari"
    if "Çifte" in name or nm.startswith("ÇŞ"):
        return "cifte_sans"
    if re.search(r"Maç Sonucu|^MS [102X]$", name) or re.fullmatch(r"MS [102X]", nm):
        return "ms"
    if "Karşılıklı" in name or nm.startswith("KG"):
        return "kg"
    if re.search(r"Ev |Deplasman|Dep |Ev Sahibi", name):
        return "takim_gol"
    if "Alt" in name or "Üst" in name:
        return "alt_ust"
    return "diger"


def _line(s):
    m = re.search(r'(\d+)[.,](5)', s); return float(f"{m.group(1)}.5") if m else None

def grade(p: dict, r: dict) -> bool | None:
    """True/False/None (None = belirlenemez/bekliyor). Kapanmış yarı marketleri canlıda karara bağlanabilir."""
    name = f"{p.get('market') or ''} | {p.get('sel') or ''} | {p.get('name') or ''}"
    ht, ft = r.get('ht'), r.get('ft')
    if r['state'] != 'bitti' or ft is None:
        return None
    if ht is None and re.search(r'İY|1\. Yarı|2Y|İlk Yarı|Evet/Evet|Dep İY', name):
        return None
    h, a = ft; h1, a1 = ht if ht else (None, None)
    h2, a2 = (h - h1, a - a1) if ht else (None, None)
    nm, mk, sel = p.get('name') or '', p.get('market') or '', str(p.get('sel') or '')
    def ou(goals, s):
        ln = _line(s); return (goals > ln) if 'Üst' in s else (goals < ln)
    def ms(x, hh, aa):
        return {'1': hh > aa, '2': aa > hh, '0': hh == aa, 'X': hh == aa}[x]
    if nm == 'KGKG': return h1 > 0 and a1 > 0 and h2 > 0 and a2 > 0
    if nm.startswith('İYMS'):
        a_, b_ = sel.split('/'); return ms(a_, h1, a1) and ms(b_, h, a)
    if '&' in sel or ' ve ' in sel or ('&' in mk):
        parts = re.split(r'\s*&\s*|\s+ve\s+', sel.replace('MS ', 'MS '))
        out = True
        for part in parts:
            part = part.strip()
            if part.startswith('MS'): out &= ms(part.split()[1], h, a)
            elif part.startswith('İY KG'): out &= ((h1 > 0 and a1 > 0) == ('Var' in part))
            elif part.startswith('İY'): out &= ms(part.split()[1], h1, a1)
            elif part.startswith('KG'): out &= ((h > 0 and a > 0) == ('Var' in part))
            elif 'Alt' in part or 'Üst' in part: out &= ou(h + a, part)
            else: return None
        return out
    if mk == 'Maç Sonucu' or mk == 'Canlı Maç Sonucu' or re.fullmatch(r'MS [102X]', nm):
        return ms((sel if sel in '102X' else nm.split()[-1]), h, a)
    if 'Çifte' in mk or nm.startswith('ÇŞ'):
        s = nm.replace('ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        return any(ms(c, h, a) for c in s)
    if 'Handikap' in mk:
        hc = int(re.search(r'\((-?\d+)\)', nm).group(1)); hh = h + hc
        return ms(nm.split()[-1], hh, a)
    if mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102]', nm): return ms(nm.split()[-1], h1, a1)
    if nm.startswith('2Y'): return ms(nm.split()[-1], h2, a2)
    if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'): return ou(a1, sel)
    if mk.startswith('1. Yarı') and ('Alt' in sel or 'Üst' in sel): return ou(h1 + a1, sel)
    if mk.startswith('Deplasman') or 'Ev Sahibi' in mk or mk.startswith('Canlı Ev') or nm.startswith(('Dep ', 'Ev ')):
        g = a if (mk.startswith('Deplasman') or nm.startswith('Dep')) else h
        return ou(g, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Karşılıklı' in mk: return (h > 0 and a > 0) == (sel in ('Var', 'Evet'))
    if 'Tek' in sel or 'Tek' in nm: return (h + a) % 2 == 1
    if 'Alt' in sel or 'Üst' in sel or 'Alt' in nm or 'Üst' in nm: return ou(h + a, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    return None

def early_decide(p: dict, r: dict) -> bool | None:
    """Canlı maçta zaten kesinleşmiş bacaklar (ör. Üst geçti, ya da İY bitmiş).
    Yalnız matematiksel olarak kesin sonuç döner; aksi halde None."""
    if r['state'] != 'canlı': return None
    sc = r.get('score')
    if not sc or sc[0] is None: return None
    h, a = sc; nm, sel = p.get('name') or '', str(p.get('sel') or '')
    mk = p.get('market') or ''
    ht = r.get('ht')
    # 1. yarı skoru: devre bittiyse HT, aksi halde (hâlâ ilk yarıdaysak) anlık skor
    h1 = a1 = None
    if ht:
        h1, a1 = ht
    elif r.get('minute') is not None and r['minute'] <= 45:
        h1, a1 = h, a

    def ou_decided(goals, s):
        ln = _line(s)
        if ln is None: return None
        if 'Üst' in s and goals > ln: return True
        if 'Alt' in s and goals > ln: return False
        return None  # çizgi aşılmadı; Alt ancak yarı/maç bitince kazanır

    def ou_final(goals, s):
        ln = _line(s)
        if ln is None: return None
        return (goals > ln) if 'Üst' in s else (goals < ln)

    if mk in ('2,5 Gol Alt/Üst', '3,5 Gol Alt/Üst') or re.fullmatch(r'\d\.5 (Alt|Üst)', nm):
        s = sel if ('Alt' in sel or 'Üst' in sel) else nm
        g = ou_decided(h + a, s)
        if g is not None: return g
    if ('3,5 Alt' in sel or '3.5 Alt' in nm or '3,5 Alt' in nm) and h + a > 3.5: return False
    if ('2,5 Alt' in sel or '2.5 Alt' in nm or '2,5 Alt' in nm) and h + a > 2.5: return False

    if (mk.startswith('Deplasman 0,5') or nm.startswith('Dep 0.5')) and 'Üst' in (sel + nm) and a > 0: return True
    if (mk.startswith('Ev Sahibi') or nm.startswith('Ev 0.5')) and 'Üst' in (sel + nm) and h > 0: return True
    if 'Karşılıklı' in mk and sel in ('Var', 'Evet') and h > 0 and a > 0: return True
    if 'KG Yok' in (sel + nm) and h > 0 and a > 0: return False
    if nm == 'KGKG' and ht and (ht[0] == 0 or ht[1] == 0): return False

    if ht and (mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102X]', nm)):
        x = nm.split()[-1]
        if x in '102X':
            return {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]
    if ht and nm.startswith('İYMS'):
        x = (sel.split('/')[0] if '/' in sel else '')
        if x in '102X' and not {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]:
            return False

    if h1 is not None:
        iy_s = sel if ('Alt' in sel or 'Üst' in sel) else nm
        if mk.startswith('1. Yarı 0,5') or nm.startswith('İY 0.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(h1 + a1, iy_s)
        if mk.startswith('1. Yarı 1,5') or '1. Yarı 1,5' in mk or nm.startswith('İY 1.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(h1 + a1, iy_s)
        if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'):
            g = ou_decided(a1, iy_s)
            if g is not None: return g
            if ht: return ou_final(a1, iy_s)
    return None


def fetch_result(leg: dict, fotmob: Any, fm_list: list[dict], overrides: dict | None = None,
                 cache: dict | None = None, window_h: float = 3.0) -> dict:
    """FotMob sonucu: maç listesinde kickoff ±window_h ve takım adı benzerliğiyle eşleştir, ayrıntıdan İY/MS al."""
    from quantfoot.data.fotmob import find_match, parse_details
    cache = {} if cache is None else cache
    code = leg.get("code")
    if code in cache:
        return cache[code]
    ko = None
    if leg.get("ko"):
        try:
            ko = dt.datetime.strptime(str(leg["ko"])[:16], "%Y-%m-%d %H:%M").replace(tzinfo=TSI)
        except ValueError:
            ko = None
    cand = fm_list
    if ko:
        cand = [m for m in fm_list if m.get("utc") and abs((dt.datetime.fromisoformat(m["utc"].replace("Z", "+00:00")) - ko).total_seconds()) <= window_h * 3600]
    ov = (overrides or {}).get(code) or (overrides or {}).get(str(code))
    mm = next((m for m in fm_list if m["id"] == ov), None) if ov else None
    home, away = leg.get("home"), leg.get("away")
    if (not home or not away) and leg.get("match") and " - " in leg["match"]:
        home, away = leg["match"].split(" - ", 1)
    mm = mm or find_match(cand, home or "", away or "", 0.6)
    r: dict = dict(fotmob_id=None, state="eşleşmedi")
    if mm:
        r.update(fotmob_id=mm["id"], fm_match=f"{mm['home']} - {mm['away']}",
                 state="bitti" if mm["finished"] else ("canlı" if mm["ongoing"] else "başlamadı"),
                 minute=mm.get("minute"), score=[mm["hg"], mm["ag"]])
        if mm["finished"] or mm["ongoing"]:
            d = fotmob.details(mm["id"], ttl_s=None if mm["finished"] else 300) or {}
            st = (d.get("header") or {}).get("status") or {}
            if mm["finished"] and st.get("ongoing") and not st.get("finished"):
                d = fotmob.details(mm["id"], ttl_s=0) or d
                st = (d.get("header") or {}).get("status") or {}
            ev = ((d.get("content") or {}).get("matchFacts") or {}).get("events", {}).get("events") or []
            ht = [e for e in ev if e.get("type") == "Half" and e.get("halfStrShort") == "HT"]
            ft = [e for e in ev if e.get("type") == "Half" and e.get("halfStrShort") == "FT"]
            pd = parse_details(d)
            r["ht"] = [ht[0]["homeScore"], ht[0]["awayScore"]] if ht else None
            if ft:
                r["ft"] = [ft[0]["homeScore"], ft[0]["awayScore"]]
            elif st.get("finished") and pd.get("score"):
                r["ft"] = pd.get("score")
            elif mm["finished"]:
                r["ft"] = [mm["hg"], mm["ag"]]
            else:
                r["ft"] = None
            r["reason"] = (st.get("reason") or {}).get("short")
            if st.get("finished") or mm["finished"]:
                r["state"], r["score"], r["minute"] = "bitti", r.get("ft") or r["score"], None
            elif st.get("ongoing") or mm["ongoing"]:
                r["state"], r["score"] = "canlı", pd.get("score") or r["score"]
    cache[code] = r
    return r


def decide(leg: dict, result: dict) -> bool | None:
    """Bitmiş maçta ``grade``, canlıda kesinleşmişse ``early_decide``."""
    g = grade(leg, result)
    return early_decide(leg, result) if g is None else g
