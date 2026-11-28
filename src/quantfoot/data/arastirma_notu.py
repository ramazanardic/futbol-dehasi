"""Kupon öncesi maç araştırma notu: şema, saklama, doğrulama ve bacak kararı (t190u).

Dosya: ``tahminler/<QUANTFOOT_AI>/arastirma/<YYYY-AA-GG>/<kod>_<ev>_<dep>.json``.

Otomatik toplanan alanlar (ücretsiz, herkese açık kaynaklar: ``web_research``) doldurulur; toplanamayanlar ``null`` / boş
liste kalır ve ``bos_alanlar`` listesinde görünür. Yapay zekâ (WebSearch) kalanları ``scripts/mac_web_arastirma.py --not-yaz``
ile doldurur. Her bacak için ``bacak_kararlari``: ``onay`` / ``uyari`` / ``veto`` (+ gerekçe; uyarı ve veto için zorunlu).

KURAL (KURALLAR.md ile uyumlu): not bir bacağın olasılığını ASLA yükseltmez ve bir bacağı eşiğin üstüne taşımaz; yalnız
eleyebilir (``veto``) ya da işaretleyebilir (``uyari``). ``onay`` hiçbir eşiği gevşetmez.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from quantfoot.paths import ai_area

SCHEMA_VERSION = 1
DECISIONS = ("onay", "uyari", "veto")
ALL_LEGS = "*"
ROTATION_RISK = ("dusuk", "orta", "yuksek")
SQUAD_STATUS = ("aciklandi", "tahmini")
MOTIVATION = ("sampiyonluk", "avrupa", "dusme", "kupa", "onemsiz", "normal")
SIDES = ("ev", "dep")
TSI = dt.timezone(dt.timedelta(hours=3))


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "x"


def default_root() -> Path:
    """tahminler/<QUANTFOOT_AI>/arastirma (grokbottahmin için tahminler/grokbottahmin/arastirma); her AI kendi klasörüne yazar."""
    return ai_area() / "arastirma"


def day_dir(day: str, root: Path | None = None) -> Path:
    return (root or default_root()) / day


def note_filename(code: Any, home: str, away: str) -> str:
    return f"{code}_{slug(home)}_{slug(away)}.json"


def note_path(day: str, code: Any, home: str, away: str, root: Path | None = None) -> Path:
    return day_dir(day, root) / note_filename(code, home, away)


def find_note_path(day: str, code: Any, root: Path | None = None) -> Path | None:
    """Nesine koduna göre dosya (ad takım adından türetildiği için kod ön eki aranır)."""
    d = day_dir(day, root)
    hits = sorted(d.glob(f"{code}_*.json")) if d.exists() else []
    return hits[0] if hits else None


def _now() -> str:
    return dt.datetime.now(TSI).isoformat(timespec="seconds")


def _team_template(name: str) -> dict[str, Any]:
    return {
        "ad": name,
        "kesin_eksik": [],     # [{"oyuncu", "rol", "onem" (1-3), "kaynak"}]
        "supheli": [],         # aynı biçim
        "muhtemel_11": {"durum": None, "kaynak": None, "oyuncular": []},   # durum: aciklandi | tahmini
        "rotasyon": {"risk": None, "avrupa_maci": None, "dinlenme_gun": None, "gerekce": None},
        "motivasyon": {"durum": None, "aciklama": None},
        "hoca_degisikligi": {"var": None, "aciklama": None, "kaynak": None},
    }


def empty_note(day: str, code: Any, home: str, away: str, kickoff: str | None, league: str | None) -> dict[str, Any]:
    return {
        "surum": SCHEMA_VERSION,
        "tarih": day,
        "mac": {"kod": code, "ev": home, "dep": away, "saat": kickoff, "lig": league},
        "takimlar": {"ev": _team_template(home), "dep": _team_template(away)},
        "hava_zemin": {"hava": None, "zemin": None, "kaynak": None},
        "hakem": {"ad": None, "not": None, "kaynak": None},
        "haber_ozeti": None,
        "kaynaklar": [],       # [{"url", "baslik", "tarih", "not"}]
        "bacak_kararlari": [],  # [{"secim", "karar", "gerekce", "kaynak"}]
        "olusturma": _now(),
        "guncelleme": _now(),
    }


# ---------------------------------------------------------------- otomatik doldurma (web_research / nesine_global kaydı)
def _player_rows(rows: list[dict] | None) -> list[dict[str, Any]]:
    out = []
    for r in rows or []:
        imp = str(r.get("importance") or "")
        onem = 3 if ("GK1" in imp or "TOP_SCORER" in imp) else (2 if "CORE" in imp else 1)
        out.append({"oyuncu": r.get("name"), "rol": r.get("pos") or imp or None, "onem": onem,
                    "kaynak": r.get("source") or "web-arastirma", "neden": r.get("reason")})
    return out


def _coach_text(c: Any) -> str:
    if isinstance(c, dict):
        return ", ".join(f"{k}: {v}" for k, v in c.items() if k != "kaynak" and v not in (None, ""))
    return str(c)


def from_match(m: dict, day: str) -> dict[str, Any]:
    """``nesine_global`` maç kaydı (+ ``research`` / ``research["web"]``) -> not. Bilinmeyen alan boş kalır."""
    note = empty_note(day, m.get("code"), m.get("home", ""), m.get("away", ""), m.get("kickoff_iso") or m.get("kickoff"),
                      m.get("league"))
    res = m.get("research") or {}
    web = res.get("web") or {}
    wteams = web.get("takimlar") or {}
    for side, key in (("home", "ev"), ("away", "dep")):
        t = note["takimlar"][key]
        wt = wteams.get(side) or {}
        ab = wt.get("sakat_cezali")
        if isinstance(ab, dict):
            t["kesin_eksik"] = _player_rows([x for x in ab.get("injuries", []) if x.get("state", "out") == "out"]) + \
                _player_rows(ab.get("suspensions"))
            t["supheli"] = _player_rows([x for x in ab.get("injuries", []) if x.get("state") == "doubt"])
            seen = set()
            t["kesin_eksik"] = [x for x in t["kesin_eksik"] if not (x["oyuncu"] in seen or seen.add(x["oyuncu"]))]
            if ab.get("lineup_confirmed"):
                t["muhtemel_11"] = {"durum": "aciklandi", "kaynak": ab.get("source"), "oyuncular": []}
        rt = (res.get("teams") or {}).get(side) or {}
        if rt.get("rest_days") is not None:
            t["rotasyon"]["dinlenme_gun"] = rt["rest_days"]
        mot = (res.get("motivation") or {}).get(side)
        if mot:
            t["motivasyon"]["aciklama"] = str(mot)
        hd = wt.get("hoca_degisikligi")
        if isinstance(hd, list) and hd:
            t["hoca_degisikligi"] = {"var": True, "aciklama": "; ".join(_coach_text(c) for c in hd)[:400],
                                     "kaynak": hd[0].get("kaynak") if isinstance(hd[0], dict) else None}
        elif isinstance(hd, str) and hd.startswith("son 90"):
            t["hoca_degisikligi"] = {"var": False, "aciklama": hd, "kaynak": "Wikipedia"}
    w = res.get("weather")
    if isinstance(w, dict):
        note["hava_zemin"]["hava"] = {k: w.get(k) for k in ("temp_c", "rain_mm", "wind_kmh", "snow_cm", "severe", "flag") if k in w}
        note["hava_zemin"]["kaynak"] = "open-meteo (nesine_global weather)"
    if res.get("referee"):
        note["hakem"] = {"ad": res["referee"], "not": None, "kaynak": "ESPN"}
    news = web.get("haber")
    if isinstance(news, list):
        heads = [(n.get("baslik") or str(n)) if isinstance(n, dict) else str(n) for n in news[:6]]
        note["haber_ozeti"] = " | ".join(h for h in heads if h)[:600] or None
    seen_u = set()
    for k in web.get("kaynaklar") or []:
        u = k.get("url")
        if u and k.get("ok") and u not in seen_u:
            seen_u.add(u)
            note["kaynaklar"].append({"url": u, "baslik": k.get("kaynak"), "tarih": k.get("zaman"), "not": "otomatik toplama"})
    return note


# ---------------------------------------------------------------- doğrulama
def validate(note: dict[str, Any]) -> list[str]:
    """Şema ihlalleri (boş liste = geçerli). Karar kuralları burada kilitlenir."""
    errs: list[str] = []
    if not isinstance(note, dict):
        return ["not bir nesne olmalı"]
    mac = note.get("mac") or {}
    if mac.get("kod") in (None, ""):
        errs.append("mac.kod yok")
    for side in SIDES:
        t = (note.get("takimlar") or {}).get(side)
        if not isinstance(t, dict):
            errs.append(f"takimlar.{side} yok")
            continue
        for fld in ("kesin_eksik", "supheli"):
            for i, p in enumerate(t.get(fld) or []):
                if not p.get("oyuncu"):
                    errs.append(f"{side}.{fld}[{i}].oyuncu yok")
                if p.get("onem") not in (1, 2, 3):
                    errs.append(f"{side}.{fld}[{i}].onem 1-3 olmalı")
        rot = (t.get("rotasyon") or {}).get("risk")
        if rot is not None and rot not in ROTATION_RISK:
            errs.append(f"{side}.rotasyon.risk {ROTATION_RISK} olmalı")
        mot = (t.get("motivasyon") or {}).get("durum")
        if mot is not None and mot not in MOTIVATION:
            errs.append(f"{side}.motivasyon.durum {MOTIVATION} olmalı")
        st = (t.get("muhtemel_11") or {}).get("durum")
        if st is not None and st not in SQUAD_STATUS:
            errs.append(f"{side}.muhtemel_11.durum {SQUAD_STATUS} olmalı")
    for i, d in enumerate(note.get("bacak_kararlari") or []):
        if d.get("karar") not in DECISIONS:
            errs.append(f"bacak_kararlari[{i}].karar {DECISIONS} olmalı")
        if not str(d.get("secim") or "").strip():
            errs.append(f"bacak_kararlari[{i}].secim yok")
        if d.get("karar") in ("uyari", "veto") and not str(d.get("gerekce") or "").strip():
            errs.append(f"bacak_kararlari[{i}]: {d.get('karar')} için gerekçe zorunlu")
        if any(k in d for k in ("p", "olasilik", "p_yeni", "oran")):
            errs.append(f"bacak_kararlari[{i}]: not olasılık/oran taşıyamaz")
    for i, s in enumerate(note.get("kaynaklar") or []):
        if not str(s.get("url") or "").startswith(("http://", "https://")):
            errs.append(f"kaynaklar[{i}].url geçersiz")
    return errs


def empty_fields(note: dict[str, Any]) -> list[str]:
    """Hâlâ boş (otomatik toplanamamış) alanlar: yapay zekânın doldurması gerekenler."""
    out: list[str] = []
    for side in SIDES:
        t = note["takimlar"][side]
        if not t["kesin_eksik"] and not t["supheli"]:
            out.append(f"{side}.eksikler")
        if t["muhtemel_11"].get("durum") is None:
            out.append(f"{side}.muhtemel_11")
        r = t["rotasyon"]
        if r.get("risk") is None:
            out.append(f"{side}.rotasyon")
        if t["motivasyon"].get("durum") is None:
            out.append(f"{side}.motivasyon")
        if t["hoca_degisikligi"].get("var") is None:
            out.append(f"{side}.hoca_degisikligi")
    if not (note["hava_zemin"].get("hava") or note["hava_zemin"].get("zemin")):
        out.append("hava_zemin")
    elif note["hava_zemin"].get("zemin") is None:
        out.append("zemin")
    if not note["hakem"].get("ad"):
        out.append("hakem")
    if not note.get("haber_ozeti"):
        out.append("haber_ozeti")
    if not note.get("kaynaklar"):
        out.append("kaynaklar")
    if not note.get("bacak_kararlari"):
        out.append("bacak_kararlari")
    return out


# ---------------------------------------------------------------- birleştirme / saklama
def _merge(dst: Any, patch: Any) -> Any:
    if isinstance(dst, dict) and isinstance(patch, dict):
        out = dict(dst)
        for k, v in patch.items():
            out[k] = _merge(dst.get(k), v) if k in dst else copy.deepcopy(v)
        return out
    return copy.deepcopy(patch)


def merge_patch(note: dict[str, Any], patch: dict[str, Any], who: str = "yapay_zeka") -> dict[str, Any]:
    """Yama ile birleştirir: sözlükler alan alan; ``kesin_eksik`` / ``supheli`` / ``kaynaklar`` listeleri değiştirilir;
    ``bacak_kararlari`` secim bazında güncellenir (yenisi eskinin yerine). Kimlik alanları (mac.kod/ev/dep) değişmez."""
    patch = copy.deepcopy(patch)
    patch.pop("surum", None)
    decisions = patch.pop("bacak_kararlari", None)
    mac = patch.pop("mac", None) or {}
    out = _merge(note, patch)
    for k in ("saat", "lig"):
        if mac.get(k):
            out["mac"][k] = mac[k]
    if decisions is not None:
        cur = {d["secim"]: d for d in out.get("bacak_kararlari") or []}
        for d in decisions:
            d = {**d, "kaynak": d.get("kaynak") or who, "zaman": _now()}
            cur[normalize_selection(d.get("secim"))] = {**d, "secim": normalize_selection(d.get("secim"))}
        out["bacak_kararlari"] = list(cur.values())
    for side in SIDES:
        for fld in ("kesin_eksik", "supheli"):
            for p in out["takimlar"][side].get(fld) or []:
                p.setdefault("kaynak", who)
    for s in out.get("kaynaklar") or []:
        s.setdefault("not", None)
    out["guncelleme"] = _now()
    out["dolduran"] = sorted(set((note.get("dolduran") or []) + [who]))
    return out


def normalize_selection(name: Any) -> str:
    n = str(name or "").strip()
    if n == ALL_LEGS:
        return n
    from quantfoot.markets.market_diagnosis import canonical_name

    return canonical_name(n)


def save(note: dict[str, Any], day: str, root: Path | None = None) -> Path:
    errs = validate(note)
    if errs:
        raise ValueError("; ".join(errs))
    note["bos_alanlar"] = empty_fields(note)
    m = note["mac"]
    p = note_path(day, m["kod"], m["ev"], m["dep"], root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(note, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def load_day(day: str, root: Path | None = None) -> dict[str, dict[str, Any]]:
    """{nesine kodu (str): not} — yalnız okunabilen dosyalar."""
    d = day_dir(day, root)
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(d.glob("*.json")) if d.exists() else []:
        n = load(p)
        if n and (n.get("mac") or {}).get("kod") not in (None, ""):
            out[str(n["mac"]["kod"])] = n
    return out


# ---------------------------------------------------------------- bacak kararı
def leg_verdict(note: dict[str, Any] | None, leg_name: str) -> dict[str, Any]:
    """Bir bacak için not kararı: ``{"durum": "onay"|"uyari"|"veto"|"karar_yok"|"not_yok", "gerekce": str|None}``.

    Öncelik: veto > uyari > onay (kesin ad ya da ``*``). Not yoksa ``not_yok``; not var ama bu bacak için karar yoksa
    ``karar_yok`` (davranış değişmez). Bu fonksiyon olasılığa/orana dokunmaz."""
    if not note:
        return {"durum": "not_yok", "gerekce": None}
    name = normalize_selection(leg_name)
    hits = [d for d in note.get("bacak_kararlari") or []
            if d.get("karar") in DECISIONS and normalize_selection(d.get("secim")) in (name, ALL_LEGS)]
    for level in ("veto", "uyari", "onay"):
        for d in hits:
            if d["karar"] == level:
                return {"durum": level, "gerekce": d.get("gerekce") or None}
    return {"durum": "karar_yok", "gerekce": None}


# ---------------------------------------------------------------- yeniden toplama (yapay zekâ girdisi korunur)
def _prune(x: Any) -> Any:
    if isinstance(x, dict):
        d = {k: _prune(v) for k, v in x.items()}
        return {k: v for k, v in d.items() if v not in (None, "", [], {})}
    return x


def refresh(auto: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    """Yeni otomatik toplama ``auto``; daha önce dolu (AI'nin yazdığı) alanlar ``existing``'den korunur, boşlar yenilenir."""
    if not existing:
        return auto
    keep = _prune(existing)
    keep.pop("bos_alanlar", None)
    out = _merge(auto, keep)
    out["olusturma"] = existing.get("olusturma") or auto["olusturma"]
    out["guncelleme"] = _now()
    return out
