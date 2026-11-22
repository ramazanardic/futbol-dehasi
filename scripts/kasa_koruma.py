"""Kasa koruma kupon planlayıcı (v4): ağır Nesine marjlı 5–6'lı kombine yerine 2–3 maçlık EV tabanlı kasa koruma kuponları.

    QUANTFOOT_AI=antigravitytahmin python scripts/kasa_koruma.py --tarih 2026-11-23 --kasa 1000

Girdi : tahminler/<QUANTFOOT_AI>/<tarih>/nesine_global.json
Çıktı : tahminler/<QUANTFOOT_AI>/<tarih>/kasa_koruma_plani.md / .json

ASLA bahis oynamaz, para yatırmaz/çekmez; yalnızca kasa disiplinli öneri üretir.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.coupons.system_builder import CapitalShieldPlan, SystemLeg, build_capital_shield_plan  # noqa: E402
from quantfoot.evaluation.self_improve import _build_diag_ctx  # noqa: E402
from quantfoot.markets.market_diagnosis import canonical_name, diagnose_selection  # noqa: E402
from quantfoot.paths import ai_area  # noqa: E402

TSI = dt.timezone(dt.timedelta(hours=3))


def run(
    date: str,
    *,
    bankroll_tl: float = 1000.0,
    max_tickets: int = 3,
    legs_per_ticket: int = 3,
    min_ev: float = -0.10,
    min_p: float = 0.60,
    only_upcoming: bool = True,
) -> tuple[CapitalShieldPlan, Path, Path]:
    day_dir = ai_area(ROOT) / date
    ng = json.loads((day_dir / "nesine_global.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(TSI)

    candidates: list[SystemLeg] = []
    for m in ng.get("matches") or []:
        if m.get("status") != "fiyatlandı":
            continue
        if only_upcoming:
            try:
                if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now + dt.timedelta(minutes=5):
                    continue
            except (KeyError, ValueError):
                continue
        if m.get("research_block"):
            continue
        for s in m.get("selections") or []:
            o = float(s.get("odds") or 0.0)
            p = float(s.get("fair_prob") or 0.0)
            if o < 1.20 or o > 1.80 or p < min_p:
                continue
            cname = canonical_name(s.get("name"))
            if not cname:
                continue
            diag = diagnose_selection(cname, p, _build_diag_ctx(m, s), for_coupon=True)
            if not diag.ok:
                continue
            candidates.append(
                SystemLeg(
                    match_id=str(m["code"]),
                    match=f"{m.get('home', '')} - {m.get('away', '')}",
                    name=cname,
                    odds=o,
                    p=p,
                    mbs=int(s.get("mbs") or m.get("mbs") or 1),
                    kickoff=str(m.get("kickoff") or ""),
                    league=str(m.get("league") or ""),
                )
            )

    plan = build_capital_shield_plan(
        candidates,
        bankroll_tl=bankroll_tl,
        max_tickets=max_tickets,
        legs_per_ticket=legs_per_ticket,
        min_ev=min_ev,
        min_p=min_p,
    )

    lines = [
        f"# {date} — Kasa Koruma Planı ({now:%H:%M} TSİ)",
        "",
        f"- **Kasa:** {plan.bankroll_tl:,.0f} TL · **Günlük toplam risk:** **{plan.total_staked_tl:,.0f} TL (%{plan.daily_risk_pct:.1f})** "
        f"(tavan %10, kupon başına tavan %3)",
        f"- **Filtreler:** v4 `market_diagnosis` temiz · `EV ≥ %{100*min_ev:+.1f}` · `P ≥ %{100*min_p:.0f}` · "
        f"{legs_per_ticket} maç/kupon · **sıfır ortak maç (çapraz çöküş kilidi)**",
        f"- **Elenen ağır Nesine marjlı bacak:** {plan.skipped_low_ev}",
        "",
    ]
    for n in plan.notes:
        lines.append(f"> {n}")
    if plan.notes:
        lines.append("")

    for t in plan.tickets:
        lines += [
            f"## Kupon #{t.ticket_no} — Oran **{t.total_odds:.2f}** · Tutar **{t.stake_tl:.0f} TL** · "
            f"Olası Ödeme **{t.potential_payout_tl:.2f} TL** · P **%{100*t.p_win:.1f}** · EV **%{100*t.ev:+.1f}**",
            "",
            "| Saat | Lig | Maç | Seçim | Oran | Global P | EV | MBS |",
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
        for lg in t.legs:
            ev = lg.p * lg.odds - 1.0
            lines.append(
                f"| {(lg.kickoff or '')[-5:]} | {lg.league or '-'} | {lg.match} | **{lg.name}** | "
                f"{lg.odds:.2f} | %{100*lg.p:.1f} | %{100*ev:+.1f} | {lg.mbs} |"
            )
        lines.append("")

    md_path = day_dir / "kasa_koruma_plani.md"
    json_path = day_dir / "kasa_koruma_plani.json"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(asdict(plan), ensure_ascii=False, indent=2), encoding="utf-8")
    return plan, md_path, json_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Kasa koruma 2–3 maçlık EV tabanlı kupon planlayıcı (v4)")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--kasa", type=float, default=1000.0, help="Toplam kasa (TL, varsayılan 1000)")
    ap.add_argument("--max-kupon", type=int, default=3)
    ap.add_argument("--bacak", type=int, default=3, help="Kupon başına bacak sayısı (varsayılan 3 — MBS uyumlu)")
    ap.add_argument("--min-ev", type=float, default=-0.10, help="Bacak başına en düşük EV (varsayılan -0.10)")
    ap.add_argument("--min-p", type=float, default=0.60, help="Bacak başına en düşük olasılık (varsayılan 0.60)")
    ap.add_argument("--tumu", action="store_true", help="Başlamış maçları da dahil et (geriye dönük inceleme için)")
    args = ap.parse_args()
    plan, md_path, _ = run(
        args.tarih,
        bankroll_tl=args.kasa,
        max_tickets=args.max_kupon,
        legs_per_ticket=args.bacak,
        min_ev=args.min_ev,
        min_p=args.min_p,
        only_upcoming=not args.tumu,
    )
    print(f"{args.tarih}: {len(plan.tickets)} kasa koruma kuponu ({plan.total_staked_tl:.0f} TL / %{plan.daily_risk_pct:.1f} risk) -> {md_path}")


if __name__ == "__main__":
    main()
