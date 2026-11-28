#!/usr/bin/env python3
"""Ortak AI çıktı doğrulayıcısı — her AI (Gemini dahil) aynı şemaya ve Ramazan'ın kurallarına uymak zorunda.

Kural onarımı (28 Kas 2026). Denetimde Gemini'nin kendi yazdığı sonuçlar 112 tercihin 17'sinde Nesine ile çelişti ve
kural dışı bacaklar (%48 isabet) kuralına uyanların (%68) çok altında kaldı. Bu betik bir gün klasörünü
(``tahminler/<ai>/<tarih>/``) okur ve şunları denetler:

1. **Ortak şema:** ``kuponlar.csv`` ve ``mac_tahminleri.csv`` ``scripts/ai_tahmin.py`` sütunlarını taşır.
2. **Kendi sonucunu yazma yasak:** sonuç/skor sütunu (``bacak_sonucu``, ``kupon_sonucu``, ``ana_sonuc``, ``ms_skoru`` ...)
   ya da KAZANDI/KAYBETTİ/TUTTU/YATTI hücresi olamaz. Sonuçlar yalnız ortak sonuç defterinden (Nesine) gelir;
   bilinmeyen sonuç "belirsiz"dir, uydurulmaz.
3. **Kupon kuralları (KURALLAR.md):** bacak P ≥ 0,70 · oran 1,20–1,80 · maç başına tek bacak · 2–5 bacak (en çok 6) ·
   toplam oran < 20 · yasak: beraberlik, maç geneli KG/BTTS ve 2Y KG Var (2Y KG Yok izinli), ilk gol, takım golü (iki yarıda gol atar/atamaz dahil), İY/MS,
   İY/2Y, skor, çifte şans, handikap.

Kullanım::

    python scripts/ai_cikti_dogrula.py --ai geminitahmin --tarih 2026-11-28
    python scripts/ai_cikti_dogrula.py --klasor tahminler/geminitahmin/2026-11-28 --json

Çıkış kodu: 0 = temiz, 1 = ihlal var (o çıktı kullanıcıya önerilmez), 2 = klasör/dosya yok.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot import settings as S
from quantfoot.coupons.coupon_rules import (
    BANNED_FAMILIES,
    DEFAULT_MIN_LEGS,
    HARD_MAX_LEGS,
    canonical_name,
    classify_family,
    hard_banned_reason,
    is_draw_leg,
)

# scripts/ai_tahmin.py ile birebir aynı olmalı (tests/test_ai_cikti_dogrula.py denetler)
MATCH_COLS = ["tarih", "saat", "lig", "mac", "nesine_kodu", "olasilik_1", "olasilik_X", "olasilik_2",
              "beklenen_gol_ev", "beklenen_gol_dep", "en_olasi_skor", "ana_secim_pazar", "ana_secim",
              "nesine_oran", "olasilik", "fiyat_kaynagi", "guven", "not", "secim_adi", "en_yuksek_5_olasilik"]
COUPON_COLS = ["tarih", "kupon_turu", "kupon", "kupon_no", "kupon_toplam_oran", "kupon_tutma_olasiligi", "saat", "mac",
               "nesine_kodu", "pazar", "secim", "nesine_oran", "olasilik", "secim_adi", "kural_oncesi_olasilik"]

MIN_LEG_P = 0.70
MIN_ODDS = S.MIN_LEG_ODDS
MAX_ODDS = S.BANKO_MAX_LEG_ODDS
MAX_TOTAL_ODDS = S.BANKO_MAX_TOTAL_ODDS

RESULT_COL = re.compile(r"sonuc|sonuç|skoru|kazand|kaybett|durum|degerlendirme|değerlendirme|result|outcome", re.IGNORECASE)
RESULT_CELL = re.compile(r"\b(KAZANDI|KAYBETT[İI]|TUTTU|YATTI|WON|LOST|İADE)\b", re.IGNORECASE)


def _p(x) -> float | None:
    """Olasılık: 0.74, "0,74" ya da "%74" / "74" kabul edilir."""
    if x is None:
        return None
    s = str(x).strip().replace("%", "").replace(",", ".")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return v / 100.0 if v > 1.0 else v


def _odds(x) -> float | None:
    if x is None or not str(x).strip():
        return None
    try:
        return float(str(x).strip().replace(",", "."))
    except ValueError:
        return None


def leg_rule_issues(name: str, odds: float | None, p: float | None) -> list[str]:
    """Tek bacağın Ramazan kurallarına aykırılıkları (boş liste = uygun)."""
    issues: list[str] = []
    raw = (name or "").strip()
    if not raw:
        return ["seçim adı yok"]
    parts = [x.strip() for x in re.split(r"\s*&\s*|\s+ve\s+", raw) if x.strip()] or [raw]
    for part in parts:
        n = canonical_name(part) or part
        if is_draw_leg(n):
            issues.append(f"beraberlik yasak: {part}")
        hard = hard_banned_reason(n)
        if hard:
            issues.append(f"{hard}: {part}")
        fam = classify_family(n)
        if fam in BANNED_FAMILIES:
            issues.append(f"{fam} ailesi yasak: {part}")
        if re.search(r"çifte\s*şans|^çş\b|^ÇŞ\b|handikap|^h\s*\d", part, re.IGNORECASE):
            issues.append(f"çifte şans/handikap yasak: {part}")
    if odds is None:
        issues.append("oran yok")
    elif not (MIN_ODDS - 1e-9 <= odds <= MAX_ODDS + 1e-9):
        issues.append(f"oran {odds:.2f} (kural {MIN_ODDS:.2f}–{MAX_ODDS:.2f})")
    if p is None:
        issues.append("olasılık yok (P yazılmadan bacak önerilmez)")
    elif p < MIN_LEG_P - 1e-9:
        issues.append(f"P %{100 * p:.1f} < %70")
    return list(dict.fromkeys(issues))


def check_schema(fieldnames: Iterable[str] | None, required: list[str], label: str) -> list[str]:
    fields = list(fieldnames or [])
    out: list[str] = []
    missing = [c for c in required if c not in fields]
    if missing:
        out.append(f"{label}: ortak şemada olan sütun eksik: {', '.join(missing)}")
    res_cols = [c for c in fields if RESULT_COL.search(c or "")]
    if res_cols:
        out.append(f"{label}: kendi sonucunu yazma yasak — sonuç/skor sütunu var: {', '.join(res_cols)}")
    return out


def check_result_cells(rows: list[Mapping[str, str]], label: str) -> list[str]:
    hits = 0
    for r in rows:
        for v in r.values():
            if isinstance(v, str) and RESULT_CELL.search(v):
                hits += 1
    return [f"{label}: kendi sonucunu yazma yasak — {hits} hücrede KAZANDI/KAYBETTİ benzeri sonuç var"] if hits else []


def audit_coupon_rows(rows: list[Mapping[str, str]]) -> list[dict]:
    coupons: dict[str, list[Mapping[str, str]]] = {}
    for r in rows:
        cid = f"{r.get('kupon') or r.get('kupon_id') or ''}#{r.get('kupon_no') or ''}"
        coupons.setdefault(cid, []).append(r)
    out = []
    for cid, legs in coupons.items():
        issues: list[str] = []
        n = len(legs)
        if not DEFAULT_MIN_LEGS <= n <= HARD_MAX_LEGS:
            issues.append(f"{n} bacak (kural {DEFAULT_MIN_LEGS}–5, en çok {HARD_MAX_LEGS})")
        matches = [str(x.get("nesine_kodu") or x.get("mac_no") or x.get("mac") or "") for x in legs]
        if len(set(matches)) < len(matches):
            issues.append("aynı maçtan birden çok bacak")
        total = 1.0
        p_total = 1.0
        for leg in legs:
            name = (leg.get("secim_adi") or leg.get("secim") or leg.get("tercih") or "").strip()
            odds = _odds(leg.get("nesine_oran") or leg.get("oran"))
            p = _p(leg.get("olasilik") or leg.get("kural_oncesi_olasilik"))
            for x in leg_rule_issues(name, odds, p):
                issues.append(f"{leg.get('mac', '?')} — {name}: {x}")
            total *= odds or 1.0
            p_total *= p if p is not None else 0.0
        if total >= MAX_TOTAL_ODDS - 1e-9:
            issues.append(f"toplam oran {total:.2f} ≥ {MAX_TOTAL_ODDS:g} (20+ oranlı kupon yok)")
        out.append({"kupon": cid, "bacak": n, "toplam_oran": round(total, 2),
                    "tutma_olasiligi": round(p_total, 4), "ihlaller": issues})
    return out


def _read(path: Path) -> tuple[list[str] | None, list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def validate_dir(day: Path) -> dict:
    errors: list[str] = []
    coupons: list[dict] = []
    kp, mp = day / "kuponlar.csv", day / "mac_tahminleri.csv"
    if not kp.exists() and not mp.exists():
        return {"klasor": str(day), "ok": False, "hatalar": ["kuponlar.csv / mac_tahminleri.csv yok"], "kuponlar": [],
                "eksik": True}
    if mp.exists():
        f, rows = _read(mp)
        errors += check_schema(f, MATCH_COLS, "mac_tahminleri.csv") + check_result_cells(rows, "mac_tahminleri.csv")
    if kp.exists():
        f, rows = _read(kp)
        errors += check_schema(f, COUPON_COLS, "kuponlar.csv") + check_result_cells(rows, "kuponlar.csv")
        coupons = audit_coupon_rows(rows)
    ok = not errors and all(not c["ihlaller"] for c in coupons)
    return {"klasor": str(day), "ok": ok, "hatalar": errors, "kuponlar": coupons, "eksik": False}


def to_markdown(rep: dict) -> str:
    lines = [f"# AI çıktı doğrulaması — {rep['klasor']}", "", "Kurallar: KURALLAR.md. Durum: "
             + ("**TEMİZ**" if rep["ok"] else "**İHLAL VAR — önerilmez**"), ""]
    lines += [f"- ⚠ {e}" for e in rep["hatalar"]]
    for c in rep["kuponlar"]:
        lines.append(f"## {c['kupon']} — {'UYGUN' if not c['ihlaller'] else 'KURAL DIŞI'}")
        lines.append(f"- {c['bacak']} bacak, toplam oran {c['toplam_oran']:.2f}, tutma olasılığı %{100 * c['tutma_olasiligi']:.1f}")
        lines += [f"- ⚠ {x}" for x in c["ihlaller"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ai")
    ap.add_argument("--tarih")
    ap.add_argument("--klasor")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.klasor:
        day = Path(a.klasor)
    elif a.ai and a.tarih:
        day = ROOT / "tahminler" / a.ai / a.tarih
    else:
        ap.error("--klasor ya da --ai ve --tarih gerekli")
    if not day.is_dir():
        print(f"Klasör yok: {day}")
        return 2
    rep = validate_dir(day)
    print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else to_markdown(rep))
    if rep.get("eksik"):
        return 2
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
