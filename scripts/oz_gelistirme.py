"""Aktif yapay zekânın kendi bitmiş günlerini denetleyip öz-geliştirme raporu üretir.

    QUANTFOOT_AI=antigravitytahmin python scripts/oz_gelistirme.py
    QUANTFOOT_AI=antigravitytahmin python scripts/oz_gelistirme.py --tarih 2026-11-22

Yalnız aktif ``QUANTFOOT_AI`` klasörünü okur ve çıktıyı yine kendi klasörüne
(``tahminler/<QUANTFOOT_AI>/oz_gelistirme_raporu.md`` ve ``.json``) yazar.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation.self_improve import (  # noqa: E402
    DEFAULT_MIN_N,
    DEFAULT_MIN_ODDS,
    DEFAULT_MIN_P,
    DEFAULT_PRIOR_N,
    write_self_audit,
)
from quantfoot.paths import ai_area  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Kendi AI tahmin klasörü için çok günlük öz-geliştirme denetçisi")
    ap.add_argument("--tarih", nargs="*", help="Belirli YYYY-MM-DD tarih(ler)i (boşsa tüm bitmiş günler)")
    ap.add_argument("--min-p", type=float, default=DEFAULT_MIN_P)
    ap.add_argument("--min-oran", type=float, default=DEFAULT_MIN_ODDS)
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    ap.add_argument("--prior-n", type=float, default=DEFAULT_PRIOR_N)
    ap.add_argument(
        "--sinyal-kalibrasyon",
        action="store_true",
        help="2026/27 verisinde sinyal katmanı Brier/LogLoss katkısını ölçüp Empirical-Bayes ağırlıklarını güncelle",
    )
    args = ap.parse_args()

    area = ai_area(ROOT)
    report, md_path, json_path = write_self_audit(
        area,
        dates=args.tarih or None,
        min_p=args.min_p,
        min_odds=args.min_oran,
        min_n=args.min_n,
        prior_n=args.prior_n,
    )
    ov = report["overall_coupon_zone"]
    mp = report["main_picks"]
    print(
        f"[{report['ai']}] {len(report['dates'])} gün / {report['settled_matches']} maç denetlendi | "
        f"Kupon bölgesi: {ov['hits']}/{ov['n']} (%{100*ov['hit_rate']:.1f}, artık {100*ov['raw_residual']:+.1f}p) | "
        f"Ana tahminler: {mp['hits']}/{mp['n']} (%{100*mp['hit_rate']:.1f}) | "
        f"Altın: {len(report['golden_pools'])}, Alarm: {len(report['toxic_alarms'])}"
    )
    print(f"Rapor: {md_path}")
    print(f"JSON : {json_path}")

    if args.sinyal_kalibrasyon:
        from quantfoot.evaluation.signal_attribution import (
            render_attribution_markdown,
            run_causal_signal_attribution,
            save_signal_weights,
        )

        attr = run_causal_signal_attribution()
        w_path = save_signal_weights(attr)
        attr_md = area / "sinyal_kalibrasyon.md"
        attr_md.write_text(render_attribution_markdown(attr), encoding="utf-8")
        print(
            f"[sinyal-kalibrasyon] {attr.evaluated_matches} maç | Brier: {attr.overall_market_brier:.5f} -> "
            f"{attr.overall_model_brier:.5f} ({attr.overall_brier_gain:+.5f}) -> {w_path}"
        )


if __name__ == "__main__":
    main()
