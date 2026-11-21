"""Ortak sistemin TEK giriş komutu: bir günün tahminlerini ve banko kuponunu her yapay zekâ için aynı hatla üretir.

    QUANTFOOT_AI=claudetahmin python scripts/gunluk_tahmin.py --tarih 2026-11-22
    python scripts/gunluk_tahmin.py --ai geminitahmin --tarih 2026-11-22 --hedef 2.5
    python scripts/gunluk_tahmin.py --ai grokbottahmin --kuru           # yalnız adımları yazdır, çalıştırma
    python scripts/gunluk_tahmin.py --ai chatgbttahmin --yalniz denetim # yalnız kuponlar.csv kural denetimi

Bağlayıcı belge: docs/ORTAK_SISTEM.md. Adımlar (sırayla, mevcut betikler yeniden kullanılır):

  1. bulten   scripts/nesine_global.py --date D        Nesine bülteni + keskin referanslar (Pinnacle/Smarkets/OddsMath),
                                                       marjsız adil fiyatlar, piyasa kalibrasyonu
  2. tahmin   scripts/ai_tahmin.py --tarih D           mac_tahminleri.csv (ortak biçim, başlamış maç satırı dondurulur)
  3. derin    scripts/derin_tahmin.py --tarih D        her maç için takım geçmişiyle sınanmış ana tercih
  4. kupon    scripts/kupon_kur.py --hedef H --mod banko   nesine_kupon.py + coupon_rules (P_düz ≥ %70, aile beyaz
                                                       listesi, beraberlik/KG/gol yasağı) + bacak bacak derin araştırma;
                                                       kuponlar.csv'yi yazar
  5. denetim  kuponlar.csv bu dosyadaki ``audit_coupons`` ile ortak kurallara göre denetlenir -> kupon_denetim.md

Çıktılar yalnız tahminler/<QUANTFOOT_AI>/<tarih>/ altına yazılır; başka bir yapay zekânın klasörü okunmaz.
Bahis OYNANMAZ: kupon yalnız öneridir, kullanıcı onayı olmadan Nesine'de kupon yapılmaz.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.coupons.coupon_rules import DEFAULT_MAX_LEGS, DEFAULT_MIN_LEGS, leg_decision  # noqa: E402
from quantfoot.paths import VALID_AIS, QuantfootAIError, ai_name  # noqa: E402

TSI = dt.timezone(dt.timedelta(hours=3))
STEPS = ("bulten", "tahmin", "derin", "kupon", "denetim")
DEFAULT_TARGET = 2.5  # banko: 5 bacak × ~1,21–1,25 ≈ 2,6–3,0; daha yüksek hedef banko kurallarıyla genelde kurulamaz


def step_commands(date: str, targets: list[float], py: str = sys.executable) -> dict[str, list[list[str]]]:
    """Each step's subprocess command lines (the denetim step runs in-process)."""
    s = str(ROOT / "scripts")
    return {
        "bulten": [[py, f"{s}/nesine_global.py", "--date", date]],
        "tahmin": [[py, f"{s}/ai_tahmin.py", "--tarih", date]],
        "derin": [[py, f"{s}/derin_tahmin.py", "--tarih", date]],
        "kupon": [[py, f"{s}/kupon_kur.py", "--hedef", f"{t:g}", "--tarih", date, "--mod", "banko"] for t in targets],
        "denetim": [],
    }


def _f(x) -> float | None:
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def audit_coupons(rows: list[dict]) -> dict:
    """Ortak kupon kurallarını kuponlar.csv satırlarına uygula (docs/ORTAK_SISTEM.md §3).

    Kurallar: her bacak coupon_rules.leg_decision'dan geçer (düzeltilmiş P ≥ %70, oran ≥ 1,20 ve ≤ 1,80, izinli aile,
    beraberlik/KG/ilk gol/takım golü yok); kupon 5–6 bacak; aynı maçtan tek bacak; aynı tercih iki kuponda yok.
    Dönen sözlük: ``coupons`` (kupon başına bacak sayısı, toplam oran, tutma olasılığı, ihlaller) ve ``ok``.
    """
    coupons: dict[str, list[dict]] = {}
    for r in rows:
        coupons.setdefault(f"{r.get('kupon', '')}#{r.get('kupon_no', '')}", []).append(r)
    seen_legs: dict[tuple[str, str], str] = {}
    out = []
    for cid, legs in coupons.items():
        issues: list[str] = []
        n = len(legs)
        if not DEFAULT_MIN_LEGS <= n <= DEFAULT_MAX_LEGS:
            issues.append(f"{n} bacak (kural: {DEFAULT_MIN_LEGS}–{DEFAULT_MAX_LEGS})")
        codes = [str(leg.get("nesine_kodu") or leg.get("mac")) for leg in legs]
        if len(set(codes)) < len(codes):
            issues.append("aynı maçtan birden çok bacak")
        p_total, odds_total = 1.0, 1.0
        for leg in legs:
            name = (leg.get("secim_adi") or leg.get("secim") or "").strip()
            dec = leg_decision({"name": name, "odds": _f(leg.get("nesine_oran")), "p": _f(leg.get("olasilik"))})
            if not dec.ok:
                issues.append(f"{leg.get('mac')} — {name}: " + "; ".join(dec.reasons))
            p_total *= dec.p_cal if dec.p_cal is not None else 0.0
            odds_total *= _f(leg.get("nesine_oran")) or 1.0
            key = (str(leg.get("nesine_kodu") or leg.get("mac")), name)
            if key in seen_legs and seen_legs[key] != cid:
                issues.append(f"{leg.get('mac')} — {name}: aynı tercih {seen_legs[key]} kuponunda da var")
            seen_legs.setdefault(key, cid)
        out.append({"kupon": cid, "bacak": n, "toplam_oran": round(odds_total, 2),
                    "tutma_olasiligi": round(p_total, 4), "ihlaller": issues})
    return {"coupons": out, "ok": all(not c["ihlaller"] for c in out)}


def audit_markdown(date: str, ai: str, audit: dict) -> str:
    lines = [f"# Kupon kural denetimi — {ai} — {date}", "",
             "Kurallar: docs/ORTAK_SISTEM.md §3. Tutma olasılığı = düzeltilmiş bacak P'lerinin çarpımı.", ""]
    if not audit["coupons"]:
        lines.append("Kupon yok (kurallara uyan kupon kurulamadı — bu dürüst sonuçtur, kural gevşetilmez).")
    for c in audit["coupons"]:
        durum = "UYGUN" if not c["ihlaller"] else "KURAL DIŞI — oynanmaz"
        lines.append(f"## {c['kupon']} — {durum}")
        lines.append(f"- {c['bacak']} bacak, toplam oran {c['toplam_oran']:.2f}, tutma olasılığı "
                     f"%{100 * c['tutma_olasiligi']:.1f} (≈ {('1/' + str(round(1 / c['tutma_olasiligi']))) if c['tutma_olasiligi'] > 0 else '—'})")
        lines += [f"- ⚠ {x}" for x in c["ihlaller"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def run_audit(date: str, ai: str) -> dict:
    day = ROOT / "tahminler" / ai / date
    path = day / "kuponlar.csv"
    rows = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    audit = audit_coupons(rows)
    day.mkdir(parents=True, exist_ok=True)
    (day / "kupon_denetim.md").write_text(audit_markdown(date, ai, audit), encoding="utf-8")
    for c in audit["coupons"]:
        print(f"  {c['kupon']}: {c['bacak']} bacak, oran {c['toplam_oran']:.2f}, P %{100 * c['tutma_olasiligi']:.1f}"
              + ("" if not c["ihlaller"] else f" — {len(c['ihlaller'])} ihlal"))
    return audit


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--ai", choices=sorted(VALID_AIS), help="QUANTFOOT_AI (verilmezse ortamdaki değer)")
    ap.add_argument("--hedef", type=float, nargs="*", default=[DEFAULT_TARGET],
                    help="Banko kupon hedef toplam oranları (varsayılan 2,5; boş verilirse kupon kurulmaz)")
    ap.add_argument("--yalniz", nargs="*", choices=STEPS, help="Yalnız bu adımlar (varsayılan: hepsi)")
    ap.add_argument("--atla", nargs="*", choices=STEPS, default=[], help="Bu adımları atla")
    ap.add_argument("--kuru", action="store_true", help="Komutları yazdır, çalıştırma")
    args = ap.parse_args(argv)
    if args.ai:
        os.environ["QUANTFOOT_AI"] = args.ai
    try:
        ai = ai_name()
    except QuantfootAIError as e:
        print(e, file=sys.stderr)
        return 2
    dt.date.fromisoformat(args.tarih)
    steps = [s for s in (args.yalniz or STEPS) if s not in args.atla]
    cmds = step_commands(args.tarih, list(args.hedef))
    print(f"Ortak sistem — {ai} — {args.tarih}: {', '.join(steps)}")
    for step in steps:
        for cmd in cmds[step]:
            print(f"[{step}] {' '.join(cmd)}")
            if args.kuru:
                continue
            r = subprocess.run(cmd, cwd=ROOT, env=os.environ.copy())
            if r.returncode != 0:
                print(f"[{step}] çıkış kodu {r.returncode}", file=sys.stderr)
                if step in ("bulten", "tahmin"):
                    return r.returncode  # bülten/tahmin olmadan sonraki adımlar anlamsız
        if step == "denetim" and not args.kuru:
            audit = run_audit(args.tarih, ai)
            if not audit["ok"]:
                print("Kural dışı kupon var: kupon_denetim.md — bu kupon önerilmez/oynanmaz.", file=sys.stderr)
                return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
