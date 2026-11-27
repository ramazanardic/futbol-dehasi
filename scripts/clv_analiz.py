"""CLV (Closing Line Value), devigging benchmark, and Brier MCB/DSC calibration audit CLI.

Usage:
    python scripts/clv_analiz.py --tipsaudit
    QUANTFOOT_AI=<klasörün> python scripts/clv_analiz.py --kendi-kalibrasyon
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation.clv_tracker import (
    evaluate_tipsaudit_csv,
    propose_family_calibration_update,
)
from quantfoot.markets.line_movement import backtest_sharp_soft_and_steam
from quantfoot.paths import ai_name


def _load_shared_degerlendirme_rows(ai: str) -> list[dict]:
    """Read ONLY the active AI's settled picks from shared degerlendirme/*.json files."""
    deg_dir = ROOT / "degerlendirme"
    rows: list[dict] = []
    if not deg_dir.exists():
        return rows
    for path in sorted(deg_dir.glob("20*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ai_block = (payload.get("ais") or {}).get(ai) or {}
        for rec in ai_block.get("rows") or ai_block.get("picks") or []:
            if isinstance(rec, dict):
                rows.append(rec)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CLV significance, CORP reliability & sharp-soft steam audit")
    ap.add_argument("--tipsaudit", action="store_true", help="Benchmark devigging + CLV + CORP on data/tipsaudit.csv")
    ap.add_argument("--steam", action="store_true", help="Run sharp-vs-soft EV tier & steam-direction backtest on data/tipsaudit.csv")
    ap.add_argument("--kendi-kalibrasyon", action="store_true", help="Generate safe calibration proposal for QUANTFOOT_AI")
    ap.add_argument("--json", action="store_true", help="Emit JSON output")
    args = ap.parse_args(argv)

    run_tips = args.tipsaudit or (not args.kendi_kalibrasyon and not args.steam)
    out: dict = {}

    ta_path = ROOT / "data" / "tipsaudit.csv"
    if run_tips and ta_path.exists():
        res = evaluate_tipsaudit_csv(ta_path)
        out["tipsaudit"] = {
            "n_matches": res["n_matches"],
            "devig_benchmark": res["devig_benchmark"],
            "clv_report": res["clv_report"].__dict__,
            "open_vs_close_pool": res["open_vs_close_pool"].__dict__,
            "prediction_hit_rate": res["prediction_hit_rate"],
        }

    if args.steam and ta_path.exists():
        out["sharp_soft_steam"] = backtest_sharp_soft_and_steam(ta_path)

    if args.kendi_kalibrasyon:
        active_ai = ai_name()
        cal_path = ROOT / "data" / "calibration" / "coupon_family_calibration.json"
        cur_cal = json.loads(cal_path.read_text(encoding="utf-8")) if cal_path.exists() else {}
        settled = _load_shared_degerlendirme_rows(active_ai)
        out["calibration_proposal"] = {
            "ai": active_ai,
            **propose_family_calibration_update(settled, cur_cal),
        }

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if "tipsaudit" in out:
        tb = out["tipsaudit"]
        print(f"=== tipsaudit.csv Devig, CORP & CLV Denetimi (n={tb['n_matches']}) ===")
        for method, stats in tb["devig_benchmark"].items():
            print(
                f"  {method:15s} | log_loss={stats['log_loss']:.6f} | brier_1x2={stats['brier_1x2']:.6f} "
                f"| CORP_ECE={stats['corp_ece']:.5f} (MCB={stats['corp_mcb']:.6f}, DSC={stats['corp_dsc']:.6f})"
            )
        clv = tb["clv_report"]
        print(
            f"  CLV (n={clv['n']}): mean={clv['mean_clv']*100:+.2f}%, median={clv['median_clv']*100:+.2f}%, "
            f"pos={clv['positive_rate']*100:.1f}%, t={clv['t_stat']:.2f}, p={clv['p_value_one_sided']:.4f}, "
            f"95% CI=[{clv['ci_95_low']*100:+.2f}%, {clv['ci_95_high']*100:+.2f}%]"
        )
    if "sharp_soft_steam" in out:
        ss = out["sharp_soft_steam"]
        print(f"\n=== Sharp-vs-Soft EV & Steam Yönü Backtesti (n={ss['n_matches']}, devig={ss['devig_method']}) ===")
        for tier, st in ss["sharp_soft_ev_tiers"].items():
            print(
                f"  {tier:10s} | n={st['n']:4d} | ROI={st['roi']*100:+6.2f}% | hit={st['hit_rate']*100:5.1f}% "
                f"| CLV={st['mean_clv']*100:+6.2f}% | t={st['t_stat']:+5.2f} (p={st['p_value_one_sided']:.4f})"
            )
        print("  --- EV >= %2 adaylarında açılış→kapanış steam yönü kırılımı ---")
        for bkt, st in ss["steam_direction_on_ev2pct"].items():
            print(
                f"  {bkt:28s} | n={st['n']:4d} | ROI={st['roi']*100:+6.2f}% | hit={st['hit_rate']*100:5.1f}% "
                f"| CLV={st['mean_clv']*100:+6.2f}% | t={st['t_stat']:+5.2f}"
            )
    if "calibration_proposal" in out:
        cp = out["calibration_proposal"]
        print(f"\n=== Güvenli Kalibrasyon Önerisi ({cp['ai']}, n={cp['n_total']}) ===")
        for fam, st in cp["families"].items():
            tag = "UYGUN" if st["eligible"] else "YETERSIZ_N"
            print(
                f"  [{tag:10s}] {fam:24s} n={st['n']:4d} pred={st['mean_pred']:.3f} hit={st['hit_rate']:.3f} "
                f"eski={st['previous_adjustment']:+.4f} -> öneri={st['proposed_adjustment']:+.4f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
