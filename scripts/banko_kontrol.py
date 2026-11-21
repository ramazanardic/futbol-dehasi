"""Herhangi bir kupon dosyasını kupon modu kurallarından geçir (elle / özel betikle kurulan kuponlar için).

    python scripts/banko_kontrol.py tahminler/<ai>/<gün>/kupon_aksam_5.json            # banko (varsayılan)
    python scripts/banko_kontrol.py ... --mod risk --tutar 300                          # risk: dürüst ihtimal
    python scripts/banko_kontrol.py ... --bulten                                        # Nesine bülteninde var mı

Çıkış kodu 0 = kurallara uyuyor, 1 = uymuyor (kupon verilmez/oynanmaz). Açık maç maruziyeti
``oynanan_kuponlar.json`` kaydından okunur (scripts/sonuc_defteri.py kaydet).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.strategy import kupon_modu as KM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dosya", type=Path)
    ap.add_argument("--kupon-no", type=int, default=1)
    ap.add_argument("--mod", choices=KM.MODES, default=KM.DEFAULT_MODE)
    ap.add_argument("--tutar", type=float, default=None)
    ap.add_argument("--bulten", action="store_true", help="Nesine bültenini çekip her seçimin açık olduğunu doğrula")
    ap.add_argument("--maruziyetsiz", action="store_true", help="oynanan kupon kaydını okuma")
    args = ap.parse_args(argv)
    from sonuc_defteri import legs_from_file
    legs = legs_from_file(args.dosya, args.kupon_no - 1)
    offered = None
    if args.bulten:
        from quantfoot.data.nesine import fetch_bulletin, parse_bulletin
        offered = KM.bulletin_offered(KM.bulletin_book(parse_bulletin(fetch_bulletin())))
    exposure = {}
    if not args.maruziyetsiz:
        try:
            from quantfoot.paths import ai_area
            exposure = KM.open_exposure(ai_area())
        except Exception:  # noqa: BLE001 - QUANTFOOT_AI yoksa maruziyet atlanır
            exposure = {}
    res = KM.guard_legs(legs, args.mod, open_exposure=exposure, offered=offered)
    print(f"{args.dosya.name}: {len(legs)} maç — {KM.honest_line(res, args.tutar)}")
    for w in res.warnings:
        print(f"  uyarı: {w}")
    if res.ok:
        print(f"  {args.mod.upper()} KONTROLÜ GEÇTİ")
        return 0
    print(f"  {args.mod.upper()} KONTROLÜNDEN GEÇMEDİ:")
    for e in res.errors:
        print(f"  - {e}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
