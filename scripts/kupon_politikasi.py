"""Kupon politika denetimi: oynamadan önce kuponun EV'sini, marj maliyetini, aynı maç maruziyetini ve
kesirli Kelly payını gösterir. Olasılıklar keskin/marjsız kaynaktan gelmelidir (Nesine değil).

    python scripts/kupon_politikasi.py --bacaklar kupon.csv --kasa 250       # sütunlar: match_id,selection,odds,prob[,prob_sd][,coupon]
    python scripts/kupon_politikasi.py --gecmis nesine_kupon_gecmisi.csv     # geçmiş kuponlarda çift maruziyet / bacak sayısı

``coupon`` sütunu varsa her kupon ayrı denetlenir ve aynı gün maruziyet defterine sırayla eklenir.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from quantfoot.strategy.accumulator_policy import ExposureBook, Leg, PolicyConfig, check_coupon  # noqa: E402


def audit_history(path: Path) -> str:
    g = pd.read_csv(path)
    per = g.groupby("coupon_id").size()
    c = g.groupby("match").coupon_id.nunique()
    dup = c[c > 1].sort_values(ascending=False)
    lines = [f"Kupon: {per.size}, bacak: {len(g)}, kupon başı bacak ortalama {per.mean():.1f} (en çok {per.max()})",
             f"Birden çok kupona giren maç: {len(dup)} / {len(c)}"]
    lines += [f"  {m}: {n} kupon" for m, n in dup.head(10).items()]
    over = int((per > PolicyConfig().max_legs).sum())
    lines.append(f"Politika tavanını ({PolicyConfig().max_legs} bacak) aşan kupon: {over}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bacaklar", type=Path)
    ap.add_argument("--gecmis", type=Path)
    ap.add_argument("--kasa", type=float, default=0.0)
    ap.add_argument("--max-mac", type=int, default=PolicyConfig().max_legs)
    ap.add_argument("--min-ev", type=float, default=PolicyConfig().min_coupon_ev)
    args = ap.parse_args()
    if args.gecmis:
        print(audit_history(args.gecmis))
        return
    if not args.bacaklar:
        ap.error("--bacaklar ya da --gecmis gerekli")
    df = pd.read_csv(args.bacaklar)
    cfg = PolicyConfig(max_legs=args.max_mac, min_coupon_ev=args.min_ev)
    book = ExposureBook(args.kasa or 1.0, cfg)
    groups = df.groupby("coupon", sort=False) if "coupon" in df.columns else [("kupon", df)]
    for name, part in groups:
        legs = [Leg(str(r.match_id), str(r.selection), float(r.odds), float(r.prob),
                    float(getattr(r, "prob_sd", 0.0) or 0.0)) for r in part.itertuples()]
        ev = check_coupon(legs, cfg)
        ok, stake, why = book.add(ev)
        print(f"== {name}: {ev.n_legs} bacak, oran {ev.odds:.2f}, tutma {ev.prob:.1%}, EV {ev.ev:+.1%}, "
              f"marj maliyeti {ev.margin_drag:.1%}")
        for leg in legs:
            print(f"   {leg.match_id} {leg.selection}: oran {leg.odds:.2f}, p {leg.prob:.1%}, EV {leg.ev:+.1%}")
        if ok:
            print(f"   KARAR: OYNANABİLİR — önerilen pay {stake:.2f} TL" if args.kasa else "   KARAR: OYNANABİLİR")
        else:
            print("   KARAR: OYNAMA")
            for w in why:
                print(f"   - {w}")


if __name__ == "__main__":
    main()
