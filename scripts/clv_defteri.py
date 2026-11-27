"""Per-AI Nesine Opening-vs-Closing CLV Ledger CLI (strictly isolated to QUANTFOOT_AI).

Usage:
    QUANTFOOT_AI=<klasörün> python scripts/clv_defteri.py --kaydet --tarih 2026-11-26
    QUANTFOOT_AI=<klasörün> python scripts/clv_defteri.py --kapanis-guncelle --tarih 2026-11-26
    QUANTFOOT_AI=<klasörün> python scripts/clv_defteri.py --ozet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation.clv_ledger import (
    record_daily_picks,
    summarize_clv_ledger,
    update_closing_lines,
)
from quantfoot.paths import ai_area, ai_name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Nesine açılış/kapanış CLV defteri (yalnız QUANTFOOT_AI)")
    ap.add_argument("--tarih", default="", help="Gün klasörü (YYYY-AA-GG)")
    ap.add_argument("--kaydet", action="store_true", help="Günlük tahmin ve kuponları CLV defterine kaydet")
    ap.add_argument("--kapanis-guncelle", action="store_true", help="Günün nesine_global.json kapanış olasılıklarıyla CLV güncelle")
    ap.add_argument("--ozet", action="store_true", help="CLV anlamlılık, CORP ve steam özeti yazdır")
    ap.add_argument("--json", action="store_true", help="JSON çıktısı ver")
    args = ap.parse_args(argv)

    active = ai_name()
    root = ai_area()
    lpath = root / "clv_defteri.jsonl"
    out: dict = {"ai": active}

    if args.kaydet:
        if not args.tarih:
            raise SystemExit("--kaydet için --tarih YYYY-AA-GG gereklidir.")
        out["record"] = record_daily_picks(root, args.tarih, ledger_path=lpath)

    if args.kapanis_guncelle:
        if not args.tarih:
            raise SystemExit("--kapanis-guncelle için --tarih YYYY-AA-GG gereklidir.")
        ng_path = root / args.tarih / "nesine_global.json"
        if not ng_path.exists():
            raise SystemExit(f"Kapanış anlık görüntüsü bulunamadı: {ng_path}")
        payload = json.loads(ng_path.read_text(encoding="utf-8"))
        out["closing"] = update_closing_lines(lpath, payload, date_filter=args.tarih)

    if args.ozet or (not args.kaydet and not args.kapanis_guncelle):
        out["summary"] = summarize_clv_ledger(lpath)

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if "record" in out:
        r = out["record"]
        print(f"[{active}] CLV defterine +{r['added']} yeni kayıt eklendi (toplam: {r['total_entries']}).")
    if "closing" in out:
        c = out["closing"]
        print(f"[{active}] Kapanış CLV güncellendi: {c['updated_closing']} kayıt.")
    if "summary" in out:
        s = out["summary"]
        clv = s["clv_report"]
        print(f"=== {active} CLV Defteri Özeti (kayıt={s['total_entries']}, CLV={s['n_with_closing_clv']}, bitmiş={s['n_settled']}) ===")
        if clv["n"] > 0:
            print(
                f"  CLV: ort={clv['mean_clv']*100:+.2f}%, medyan={clv['median_clv']*100:+.2f}%, "
                f"t={clv['t_stat']:.2f}, p={clv['p_value_one_sided']:.4f}"
            )
        if s["corp_calibration"]:
            cc = s["corp_calibration"]
            print(
                f"  CORP Kalibrasyon: Brier={cc['brier']:.5f}, MCB={cc['mcb']:.5f}, "
                f"DSC={cc['dsc']:.5f}, CORP_ECE={cc['corp_ece']:.5f}, ROI={s['flat_roi']*100:+.2f}%"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
