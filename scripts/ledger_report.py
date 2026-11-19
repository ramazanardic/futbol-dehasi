"""Settle placed bets against real results and measure model calibration and profit.

Usage:
    python scripts/ledger_report.py --date 2026_11_18 [--offline]

Inputs:
    reports/ledger/placed_bets_<date>.csv          one row per coupon leg (real offered odds)
    reports/today_v6_predictions_<date>.json       model probabilities for that day
Outputs:
    reports/ledger/results_<date>.json             cached HT / 90-minute scores (ESPN)
    reports/ledger/placed_bets_report_<date>.md    settlement + calibration report

Scores are taken from ESPN period line scores: HT = 1st period, settlement score =
1st + 2nd period (90 minutes), so extra time / penalties never settle a bet.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from quantfoot.evaluation.settlement import fetch_espn_result, settle_selection

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports" / "ledger"


def model_prob(sel: str, pred: dict | None) -> float | None:
    """Look up the model probability for a selection in the day's prediction record."""
    if not pred:
        return None
    if sel.startswith("MS "):
        return pred["ft_1x2"].get(sel[3:])
    if sel.startswith("İY/MS "):
        return pred["ht_ft"].get(sel[6:])
    for group in ("ht_1x2", "ht_ou", "ft_ou", "goal_bands", "btts", "combos"):
        if sel in pred.get(group, {}):
            return pred[group][sel]
    return None


def fetch_scores(event_ids: set[str], preds: dict[str, dict], cache: dict) -> dict:
    """Fill the cache with finished matches' HT and 90-minute scores from ESPN."""
    for eid in sorted(event_ids):
        if cache.get(eid, {}).get("completed"):
            continue
        cache[eid] = fetch_espn_result(eid, (preds.get(eid) or {}).get("slug"))
    return cache


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026_11_18")
    ap.add_argument("--offline", action="store_true", help="use cached scores only")
    args = ap.parse_args()

    bets_path = LEDGER / f"placed_bets_{args.date}.csv"
    pred_path = ROOT / "reports" / f"today_v6_predictions_{args.date}.json"
    cache_path = LEDGER / f"results_{args.date}.json"

    with bets_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    preds = {}
    if pred_path.exists():
        preds = {str(m["event_id"]): m for m in json.loads(pred_path.read_text(encoding="utf-8"))["matches"]}
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    if not args.offline:
        cache = fetch_scores({r["event_id"] for r in rows if r["event_id"]}, preds, cache)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    legs = []
    for r in rows:
        res = cache.get(r["event_id"], {})
        sel = r["selection"]
        odds = float(r["odds"]) if r["odds"] else None
        won = settle_selection(sel, tuple(res["ht"]), tuple(res["ft90"])) if res.get("completed") and sel != "?" else None
        p = model_prob(sel, preds.get(r["event_id"]))
        score = f"{res['ft90'][0]}-{res['ft90'][1]} (İY {res['ht'][0]}-{res['ht'][1]})" if res.get("completed") else (res.get("status") or "-")
        legs.append({**r, "odds_f": odds, "won": won, "p": p, "score": score,
                     "ev": (p * odds - 1.0) if (p is not None and odds) else None})

    # ---- Coupon settlement ----
    coupons: dict[str, list[dict]] = defaultdict(list)
    for lg in legs:
        coupons[lg["coupon_id"]].append(lg)

    lines = [f"# Oynanan Bahisler Defteri — {args.date.replace('_', '-')}", "",
             "Skorlar ESPN'den: İY = 1. devre, uzlaşma skoru = 90 dakika (uzatma/penaltı hariç).",
             "EV = model olasılığı × verilen oran − 1. Kupon olasılığı bacakların bağımsız olduğunu varsayar.", "",
             "## Kuponlar", "",
             "| Kupon | Saat | Yatırım | Oran | Bacak (görünen) | Durum | Getiri | Model P(kupon) | Model EV |",
             "|---|---|---|---|---|---|---|---|---|"]
    tot_stake = tot_return = 0.0
    settled_stake = 0.0
    for cid, cl in sorted(coupons.items(), key=lambda kv: kv[1][0]["placed_at"]):
        head = cl[0]
        stake = float(head["stake_tl"]) if head["stake_tl"] else None
        odds = float(head["total_odds"]) if head["total_odds"] else None
        n_total = int(head["n_legs"]) if head["n_legs"] else None
        if any(lg["won"] is False for lg in cl):
            status, ret = "KAYBETTİ", 0.0
        elif n_total == len(cl) and all(lg["won"] is True for lg in cl):
            status, ret = "KAZANDI", (stake or 0.0) * (odds or 0.0)
        else:
            status, ret = "BEKLİYOR / EKSİK", None
        ps = [lg["p"] for lg in cl]
        joint = math.prod(ps) if ps and all(p is not None for p in ps) and n_total == len(cl) else None
        c_ev = f"{joint * odds - 1:+.0%}" if joint is not None and odds else "-"
        if stake is not None:
            tot_stake += stake
            if ret is not None:
                settled_stake += stake
                tot_return += ret
        lines.append(
            f"| {cid} | {head['placed_at']} | {head['stake_tl'] or '?'} | {head['total_odds'] or '?'} | "
            f"{len(cl)}/{head['n_legs'] or '?'} | {status} | {'-' if ret is None else f'{ret:.2f}'} | "
            f"{'-' if joint is None else f'{joint:.2%}'} | {c_ev} |"
        )
    pl = tot_return - settled_stake
    lines += ["", f"**Toplam yatırım (başlığı görünen kuponlar):** {tot_stake:.2f} TL  ",
              f"**Sonuçlanan kuponlar:** yatırım {settled_stake:.2f} TL, getiri {tot_return:.2f} TL, kâr/zarar **{pl:+.2f} TL**", ""]

    # ---- Leg-level calibration (unique match+selection+odds) ----
    uniq = {}
    for lg in legs:
        if lg["won"] is None or lg["p"] is None or not lg["odds_f"]:
            continue
        uniq[(lg["event_id"], lg["selection"], lg["odds_f"])] = lg
    u = list(uniq.values())
    lines += ["## Bacaklar (tekil bahis olarak)", "",
              "| Maç | Seçim | Oran | Model P | Model EV | Skor | Sonuç |", "|---|---|---|---|---|---|---|"]
    shown: set[tuple] = set()
    for lg in sorted(legs, key=lambda x: (x["match"], x["selection"])):
        key = (lg["event_id"], lg["selection"], lg["odds_f"])
        if key in shown:
            continue
        shown.add(key)
        res = "✓" if lg["won"] else ("✗" if lg["won"] is False else "?")
        p = "-" if lg["p"] is None else f"{lg['p']:.1%}"
        ev = "-" if lg["ev"] is None else f"{lg['ev']:+.1%}"
        lines.append(f"| {lg['match']} | {lg['selection']} | {lg['odds'] or '?'} | {p} | {ev} | {lg['score']} | {res} |")

    if u:
        n = len(u)
        hits = sum(1 for lg in u if lg["won"])
        mean_p = sum(lg["p"] for lg in u) / n
        brier = sum((lg["p"] - (1.0 if lg["won"] else 0.0)) ** 2 for lg in u) / n
        imp = sum(1.0 / lg["odds_f"] for lg in u) / n
        brier_mkt = sum((1.0 / lg["odds_f"] - (1.0 if lg["won"] else 0.0)) ** 2 for lg in u) / n
        flat = sum((lg["odds_f"] - 1.0) if lg["won"] else -1.0 for lg in u) / n
        mean_ev = sum(lg["ev"] for lg in u) / n
        lines += ["", "## Özet (sonuçlanan, tekil bacaklar)", "",
                  f"- Bacak sayısı: **{n}**, tutan: **{hits}** (%{hits / n * 100:.1f})",
                  f"- Ortalama model olasılığı: %{mean_p * 100:.1f} | Oranın ima ettiği: %{imp * 100:.1f}",
                  f"- Brier skoru — model: **{brier:.4f}**, oran (marjlı): {brier_mkt:.4f} (düşük olan daha iyi)",
                  f"- Modelin öngördüğü ortalama EV: {mean_ev:+.1%} | Gerçekleşen tekil (flat) ROI: **{flat:+.1%}**",
                  "", "_Tek günlük örneklem istatistiksel olarak anlamsızdır; değerlendirme için birkaç hafta veri gerekir._"]

    out = LEDGER / f"placed_bets_report_{args.date}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    pending = sorted({lg["match"] for lg in legs if lg["won"] is None and lg["selection"] != "?"})
    print(f"Rapor: {out.relative_to(ROOT)}")
    print(f"Sonuçlanan kuponlarda kâr/zarar: {pl:+.2f} TL (yatırım {settled_stake:.2f} TL)")
    if pending:
        print("Bekleyen maçlar:", ", ".join(pending))


if __name__ == "__main__":
    main()
