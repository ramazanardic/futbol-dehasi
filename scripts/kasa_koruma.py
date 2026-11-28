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
sys.path.insert(0, str(ROOT / "scripts"))

from nesine_global import is_sharp_source  # noqa: E402
from quantfoot import settings as S  # noqa: E402
from quantfoot.coupons.coupon_rules import BANNED_FAMILIES, calibrate_p, hard_banned_reason, is_draw_leg  # noqa: E402
from quantfoot.coupons.system_builder import CapitalShieldPlan, SystemLeg, build_capital_shield_plan  # noqa: E402
from quantfoot.evaluation.self_improve import _build_diag_ctx  # noqa: E402
from quantfoot.markets.market_calibration import calibrate_market_probability, load_market_calibration  # noqa: E402
from quantfoot.markets.market_diagnosis import canonical_name, classify_family, diagnose_selection  # noqa: E402
from quantfoot.markets.market_reliability import (  # noqa: E402
    is_match_result_side,
    ms_prob_after_draw_risk,
    tail_adjust,
)
from quantfoot.paths import ai_area  # noqa: E402
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition  # noqa: E402

TSI = dt.timezone(dt.timedelta(hours=3))


def _price_is_stale(ref_fetched_utc: str | None, now: dt.datetime, max_age_h: float) -> bool:
    if not ref_fetched_utc or max_age_h <= 0:
        return False
    try:
        fetched = dt.datetime.fromisoformat(str(ref_fetched_utc).replace("Z", "+00:00"))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=dt.timezone.utc)
        age_h = (now.astimezone(dt.timezone.utc) - fetched.astimezone(dt.timezone.utc)).total_seconds() / 3600.0
        return age_h > max_age_h
    except ValueError:
        return False


def run(
    date: str,
    *,
    bankroll_tl: float = 1000.0,
    max_tickets: int = 3,
    legs_per_ticket: int = 3,
    min_ev: float = -0.10,
    min_p: float = 0.70,
    only_upcoming: bool = True,
    max_price_age_h: float = S.MAX_PRICE_AGE_H,
    drawdown_pct: float = 0.0,
) -> tuple[CapitalShieldPlan, Path, Path]:
    day_dir = ai_area(ROOT) / date
    ng = json.loads((day_dir / "nesine_global.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(TSI)
    calibration = load_market_calibration()

    candidates: list[SystemLeg] = []
    for m in ng.get("matches") or []:
        if m.get("status") != "fiyatlandı":
            continue
        if is_uncalibrated_competition(m.get("league")):
            continue
        ref = m.get("reference")
        if ref and not is_sharp_source(ref) and m.get("price_tier") != "keskin":
            continue
        if only_upcoming:
            try:
                if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now + dt.timedelta(minutes=5):
                    continue
            except (KeyError, ValueError):
                continue
            if _price_is_stale(m.get("ref_fetched_utc"), now, max_price_age_h):
                continue
        if m.get("research_block"):
            continue
        p_over25 = next((float(x["fair_prob"]) for x in m.get("selections") or [] if x.get("name") == "2.5 Üst"), None)
        f1x2 = m.get("fair_1x2")
        p_draw = float(f1x2[1]) if isinstance(f1x2, (list, tuple)) and len(f1x2) == 3 and f1x2[1] is not None else None
        for s in m.get("selections") or []:
            o = float(s.get("odds") or 0.0)
            raw_p = float(s.get("fair_prob") or 0.0)
            if o < S.MIN_LEG_ODDS or o > S.BANKO_MAX_LEG_ODDS or raw_p <= 0.0:
                continue
            cname = canonical_name(s.get("name"))
            if not cname or is_draw_leg(cname):
                continue
            if classify_family(cname) in BANNED_FAMILIES or hard_banned_reason(cname):
                continue
            direct = bool(s.get("direct"))
            p = calibrate_market_probability(cname, raw_p, m.get("league"), calibration, direct=direct)
            p = tail_adjust(cname, p)
            if is_match_result_side(cname) and p_draw is not None:
                p = ms_prob_after_draw_risk(p, p_draw, p_over25)
            diag = diagnose_selection(cname, p, _build_diag_ctx(m, s), for_coupon=True)
            if not diag.ok:
                continue
            if not diag.rehabilitated:
                p = min(p, calibrate_p(p, cname))
            if diag.residual_adjustment < 0:
                p = min(1.0, max(0.0, p + float(diag.residual_adjustment)))
            ev = p * o - 1.0
            if p < min_p or ev > S.MAX_PLAUSIBLE_EV:
                continue
            cons_disp = m.get("consensus_dispersion") or {}
            disp_std = float(cons_disp.get("max_prob_std") or 0.0) if isinstance(cons_disp, dict) else 0.0
            candidates.append(
                SystemLeg(
                    match_id=str(m["code"]),
                    match=f"{m.get('home', '')} - {m.get('away', '')}",
                    name=cname,
                    odds=o,
                    p=round(p, 5),
                    mbs=int(s.get("mbs") or m.get("mbs") or 1),
                    kickoff=str(m.get("kickoff") or ""),
                    league=str(m.get("league") or ""),
                    consensus_dispersion=disp_std,
                )
            )

    plan = build_capital_shield_plan(
        candidates,
        bankroll_tl=bankroll_tl,
        max_tickets=max_tickets,
        legs_per_ticket=legs_per_ticket,
        min_ev=min_ev,
        min_p=min_p,
        drawdown_pct=drawdown_pct,
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
    ap.add_argument("--min-p", type=float, default=0.70, help="Bacak başına en düşük olasılık (varsayılan 0.70, Ramazan kuralı)")
    ap.add_argument("--drawdown", type=float, default=0.0, help="Mevcut kasa düşüş oranı (ör. 0.12 = %12; >=0.25 devre kesici)")
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
        drawdown_pct=args.drawdown,
    )
    print(f"{args.tarih}: {len(plan.tickets)} kasa koruma kuponu ({plan.total_staked_tl:.0f} TL / %{plan.daily_risk_pct:.1f} risk) -> {md_path}")


if __name__ == "__main__":
    main()
