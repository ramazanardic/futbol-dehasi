"""Run the QuantFoot Empirical-Bayes self-learning and live calibration pass.

    python scripts/auto_learn.py

Reads all settled days in ``reports/daily/*/takip_kayit.json`` + ``takip_sonuc.json`` and writes:
  - ``data/calibration/live_calibration.json`` (loaded automatically by ``scripts/nesine_kupon.py``)
  - ``reports/takip/ogrenme_raporu.md`` (daily self-audit & calibration summary)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from quantfoot.evaluation.auto_learn import run_auto_learn
from quantfoot.paths import ai_area

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--daily-dir", type=Path, default=None,
                    help="Varsayılan: tahminler/<QUANTFOOT_AI>/ (QUANTFOOT_AI zorunlu)")
    ap.add_argument("--calibration-out", type=Path, default=ROOT / "data" / "calibration" / "live_calibration.json")
    ap.add_argument("--report-out", type=Path, default=None)
    args = ap.parse_args()

    daily_dir = args.daily_dir or ai_area(ROOT)
    snap = run_auto_learn(
        root=ROOT,
        daily_dir=daily_dir,
        calibration_path=args.calibration_out,
        report_path=args.report_out,
    )
    ov = snap["overall"]
    adj = snap["adjustments"]
    print(
        f"Öz-öğrenme tamamlandı: {len(snap['days'])} gün, {snap['total_matches_settled']} maç, "
        f"{ov['n']} seçim (Brier={ov['brier']}) | "
        f"aktif Δσ: kaynak={len(adj['source_sigma_delta'])}, pazar={len(adj['family_sigma_delta'])}, "
        f"uyarı={len(adj['auto_blocked_families'])}"
    )
    print(f"-> {args.calibration_out}")
    print(f"-> {args.report_out or daily_dir / 'takip' / 'ogrenme_raporu.md'}")


if __name__ == "__main__":
    main()
