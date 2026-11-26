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
    nm = (p.get('name') or '').strip()
    mk = (p.get('market') or '').strip()
    sel = str(p.get('sel') or '').strip()
    if nm.startswith('DEĞİL(') and nm.endswith(')'):
        inner = grade({**p, 'name': nm[6:-1].strip()}, r)
        return None if inner is None else (not inner)
    name = f"{mk} | {sel} | {nm}"
    ht, ft = r.get('ht'), r.get('ft')
    if r['state'] != 'bitti' or ft is None:
        return None
    if ht is None and re.search(r'İY|1\. Yarı|2Y|2\. Yarı|İlk Yarı|İkinci Yarı|Evet/Evet|Dep İY|Ev İY', name):
        return None
    h, a = ft; h1, a1 = ht if ht else (None, None)
    h2, a2 = (h - h1, a - a1) if ht else (None, None)

    def ou(goals, s):
        ln = _line(s)
        if ln is None:
            return None
        if 'Üst' in s:
            return goals > ln
        if 'Alt' in s:
            return goals < ln
        return None

    def ms(x, hh, aa):
        return {'1': hh > aa, '2': aa > hh, '0': hh == aa, 'X': hh == aa}.get(x)

    def dc(code_str, hh, aa):
        chars = [c for c in code_str if c in '102X']
        if not chars:
            return None
        return any(ms(c, hh, aa) for c in chars)

    def btts(hh, aa, s_text):
        if 'Yok' in s_text or 'Hayır' in s_text:
            return not (hh > 0 and aa > 0)
        if 'Var' in s_text or 'Evet' in s_text:
            return hh > 0 and aa > 0
        return None

    if nm == 'KGKG':
        return h1 > 0 and a1 > 0 and h2 > 0 and a2 > 0
    if nm.startswith('İYMS') or nm.startswith('İY/MS'):
        code_src = sel if '/' in sel else nm.split()[-1]
        if '/' not in code_src:
            return None
        a_, b_ = code_src.split('/', 1)
        r1, r2 = ms(a_.strip(), h1, a1), ms(b_.strip(), h, a)
        return None if (r1 is None or r2 is None) else (r1 and r2)
    if '&' in sel or ' ve ' in sel or '&' in mk or '&' in nm:
        combo_src = sel if ('&' in sel or ' ve ' in sel) else nm
        parts = re.split(r'\s*&\s*|\s+ve\s+', combo_src.replace('MS ', 'MS '))
        out = True
        for part in parts:
            part = part.strip()
            if part.startswith('MS '):
                v = ms(part.split()[1], h, a)
            elif part.startswith('İY KG'):
                v = btts(h1, a1, part)
            elif part.startswith('2Y KG'):
                v = btts(h2, a2, part)
            elif part.startswith('İY '):
                v = ms(part.split()[1], h1, a1)
            elif part.startswith('2Y '):
                v = ms(part.split()[1], h2, a2)
            elif part.startswith('KG'):
                v = btts(h, a, part)
            elif 'Alt' in part or 'Üst' in part:
                v = ou(h + a, part)
            else:
                return None
            if v is None:
                return None
            out &= v
        return out

    # Half-scoped Double Chance BEFORE full-time Double Chance
    if nm.startswith('İY ÇŞ') or ('1. Yarı' in mk and 'Çifte' in mk):
        s = nm.replace('İY ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        return dc(s, h1, a1)
    if nm.startswith('2Y ÇŞ') or ('2. Yarı' in mk and 'Çifte' in mk):
        s = nm.replace('2Y ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        return dc(s, h2, a2)

    # Half-scoped BTTS BEFORE full-time BTTS and 2Y result
    if nm.startswith('İY KG') or ('1. Yarı' in mk and 'Karşılıklı' in mk):
        return btts(h1, a1, f"{sel} {nm}")
    if nm.startswith('2Y KG') or ('2. Yarı' in mk and 'Karşılıklı' in mk):
        return btts(h2, a2, f"{sel} {nm}")

    # Half-scoped Odd/Even (Tek/Çift) BEFORE FT parity or 2Y result
    if any(tok in (sel, nm) or tok in f" {sel} {nm} " for tok in ('Tek', 'Çift')):
        is_odd = 'Tek' in (sel + ' ' + nm) and 'Çift' not in sel
        if 'Çift' in sel or (not sel and 'Çift' in nm) or nm.endswith('Çift'):
            is_odd = False
        if '1. Yarı' in mk or nm.startswith('İY '):
            return ((h1 + a1) % 2 == 1) if is_odd else ((h1 + a1) % 2 == 0)
        if '2. Yarı' in mk or nm.startswith('2Y '):
            return ((h2 + a2) % 2 == 1) if is_odd else ((h2 + a2) % 2 == 0)
        return ((h + a) % 2 == 1) if is_odd else ((h + a) % 2 == 0)

    # Half-scoped team goals BEFORE general half totals or FT team goals
    if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'):
        return ou(a1, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Ev Sahibi 1. Yarı' in mk or nm.startswith('Ev İY'):
        return ou(h1, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Deplasman 2. Yarı' in mk or nm.startswith('Dep 2Y'):
        return ou(a2, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Ev Sahibi 2. Yarı' in mk or nm.startswith('Ev 2Y'):
        return ou(h2, sel if ('Alt' in sel or 'Üst' in sel) else nm)

    # Half-scoped total goals BEFORE 1Y/2Y match result
    if (mk.startswith('1. Yarı') or nm.startswith('İY ')) and ('Alt' in sel or 'Üst' in sel or 'Alt' in nm or 'Üst' in nm):
        return ou(h1 + a1, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if (mk.startswith('2. Yarı') or nm.startswith('2Y ')) and ('Alt' in sel or 'Üst' in sel or 'Alt' in nm or 'Üst' in nm):
        return ou(h2 + a2, sel if ('Alt' in sel or 'Üst' in sel) else nm)

    if mk == 'Maç Sonucu' or mk == 'Canlı Maç Sonucu' or re.fullmatch(r'MS [102X]', nm):
        tok = sel if sel in ('1', '0', '2', 'X') else nm.split()[-1]
        return ms(tok, h, a)
    if 'Çifte' in mk or nm.startswith('ÇŞ'):
        s = nm.replace('ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        return dc(s, h, a)
    if 'Handikap' in mk or nm.startswith('Hnd('):
        m_hc = re.search(r'\((-?\d+)\)', nm)
        if not m_hc:
            return None
        hc = int(m_hc.group(1)); hh = h + hc
        return ms(nm.split()[-1], hh, a)
    if mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102X]', nm):
        tok = sel if sel in ('1', '0', '2', 'X') else nm.split()[-1]
        return ms(tok, h1, a1)
    if mk.startswith('2. Yarı Sonucu') or re.fullmatch(r'2Y [102X]', nm):
        tok = sel if sel in ('1', '0', '2', 'X') else nm.split()[-1]
        return ms(tok, h2, a2)
    if mk.startswith('Deplasman') or 'Ev Sahibi' in mk or mk.startswith('Canlı Ev') or nm.startswith(('Dep ', 'Ev ')):
        g = a if (mk.startswith('Deplasman') or nm.startswith('Dep')) else h
        return ou(g, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    if 'Karşılıklı' in mk or nm.startswith('KG'):
        return btts(h, a, f"{sel} {nm}")
    if 'Alt' in sel or 'Üst' in sel or 'Alt' in nm or 'Üst' in nm:
        return ou(h + a, sel if ('Alt' in sel or 'Üst' in sel) else nm)
    return None


def early_decide(p: dict, r: dict) -> bool | None:
    """Canlı maçta zaten kesinleşmiş bacaklar (ör. Üst geçti, ya da İY bitmiş).
    Yalnız matematiksel olarak kesin sonuç döner; aksi halde None."""
    if r['state'] != 'canlı':
        return None
    nm = (p.get('name') or '').strip()
    if nm.startswith('DEĞİL(') and nm.endswith(')'):
        inner = early_decide({**p, 'name': nm[6:-1].strip()}, r)
        return None if inner is None else (not inner)
    sc = r.get('score')
    if not sc or sc[0] is None:
        return None
    h, a = sc
    sel = str(p.get('sel') or '').strip()
    mk = (p.get('market') or '').strip()
    ht = r.get('ht')
    # 1. yarı skoru: devre bittiyse HT, aksi halde (hâlâ ilk yarıdaysak) anlık skor
    h1 = a1 = None
    if ht:
        h1, a1 = ht
    elif r.get('minute') is not None and r['minute'] <= 45:
        h1, a1 = h, a

    def ou_decided(goals, s):
        ln = _line(s)
        if ln is None:
            return None
        if 'Üst' in s and goals > ln:
            return True
        if 'Alt' in s and goals > ln:
            return False
        return None  # çizgi aşılmadı; Alt ancak yarı/maç bitince kazanır

    def ou_final(goals, s):
        ln = _line(s)
        if ln is None:
            return None
        return (goals > ln) if 'Üst' in s else (goals < ln)

    is_half_market = bool(re.search(r'İY|1\. Yarı|2Y|2\. Yarı|İlk Yarı|İkinci Yarı', f"{mk} {nm}"))

    if not is_half_market:
        if mk in ('1,5 Gol Alt/Üst', '2,5 Gol Alt/Üst', '3,5 Gol Alt/Üst', '4,5 Gol Alt/Üst') or re.fullmatch(r'\d\.5 (Alt|Üst)', nm):
            s = sel if ('Alt' in sel or 'Üst' in sel) else nm
            g = ou_decided(h + a, s)
            if g is not None:
                return g
        if ('3,5 Alt' in sel or '3.5 Alt' in nm or '3,5 Alt' in nm) and h + a > 3.5:
            return False
        if ('2,5 Alt' in sel or '2.5 Alt' in nm or '2,5 Alt' in nm) and h + a > 2.5:
            return False

        # Team full-time totals: always parse exact line (never assume 0.5 for Ev Sahibi 1,5 Üst!)
        if mk.startswith('Deplasman') or nm.startswith('Dep '):
            s = sel if ('Alt' in sel or 'Üst' in sel) else nm
            g = ou_decided(a, s)
            if g is not None:
                return g
        if mk.startswith('Ev Sahibi') or mk.startswith('Canlı Ev') or nm.startswith('Ev '):
            s = sel if ('Alt' in sel or 'Üst' in sel) else nm
            g = ou_decided(h, s)
            if g is not None:
                return g

        if ('Karşılıklı' in mk or nm.startswith('KG')) and ('Var' in (sel + nm) or 'Evet' in sel) and h > 0 and a > 0:
            return True
        if ('Karşılıklı' in mk or nm.startswith('KG')) and ('Yok' in (sel + nm) or 'Hayır' in sel) and h > 0 and a > 0:
            return False

    if nm == 'KGKG' and ht and (ht[0] == 0 or ht[1] == 0):
        return False

    if ht and (mk.startswith('1. Yarı Sonucu') or re.fullmatch(r'İY [102X]', nm)):
        x = sel if sel in ('1', '0', '2', 'X') else nm.split()[-1]
        if x in ('1', '0', '2', 'X'):
            return {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]
    if ht and (nm.startswith('İY ÇŞ') or ('1. Yarı' in mk and 'Çifte' in mk)):
        s = nm.replace('İY ÇŞ', '').strip().replace('-', '') or sel.replace('-', '')
        chars = [c for c in s if c in '102X']
        if chars:
            return any({'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[c] for c in chars)
    if ht and (nm.startswith('İYMS') or nm.startswith('İY/MS')):
        x = (sel.split('/')[0].strip() if '/' in sel else '')
        if x in ('1', '0', '2', 'X') and not {'1': ht[0] > ht[1], '2': ht[1] > ht[0], '0': ht[0] == ht[1], 'X': ht[0] == ht[1]}[x]:
            return False

    if h1 is not None:
        iy_s = sel if ('Alt' in sel or 'Üst' in sel) else nm
        if mk.startswith('1. Yarı 0,5') or nm.startswith('İY 0.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None:
                return g
            if ht:
                return ou_final(h1 + a1, iy_s)
        if mk.startswith('1. Yarı 1,5') or '1. Yarı 1,5' in mk or nm.startswith('İY 1.5'):
            g = ou_decided(h1 + a1, iy_s)
            if g is not None:
                return g
            if ht:
                return ou_final(h1 + a1, iy_s)
        if 'Deplasman 1. Yarı' in mk or nm.startswith('Dep İY'):
            g = ou_decided(a1, iy_s)
            if g is not None:
                return g
            if ht:
                return ou_final(a1, iy_s)
        if 'Ev Sahibi 1. Yarı' in mk or nm.startswith('Ev İY'):
            g = ou_decided(h1, iy_s)
            if g is not None:
                return g
            if ht:
                return ou_final(h1, iy_s)
        if nm.startswith('İY KG') or ('1. Yarı' in mk and 'Karşılıklı' in mk):
            if ('Var' in (sel + nm) or 'Evet' in sel) and h1 > 0 and a1 > 0:
                return True
            if ('Yok' in (sel + nm) or 'Hayır' in sel) and h1 > 0 and a1 > 0:
                return False
            if ht:
                both = h1 > 0 and a1 > 0
                return both if ('Var' in (sel + nm) or 'Evet' in sel) else (not both)
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
