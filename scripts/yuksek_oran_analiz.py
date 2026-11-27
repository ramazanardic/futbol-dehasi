"""Günlük yüksek oranlı 1X2, 1/2 & 2/1 geri dönüş, Sharp-Lag, Skor Dutching ve Monte Carlo Portföy raporu.

    QUANTFOOT_AI=antigravitytahmin python scripts/yuksek_oran_analiz.py --tarih 2026-11-27

Girdiler: tahminler/<QUANTFOOT_AI>/<tarih>/nesine_global.json (+ varsa derin_tahminler.json,
takip_kayit.json, simulasyon.json, nesine_history.jsonl, ekstrem_gol_analiz.json).
Çıktılar: tahminler/<QUANTFOOT_AI>/<tarih>/yuksek_oran_analiz.md / .json
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

from nesine_global import DAILY, PREDICTIONS_FILE, TSI  # noqa: E402
from quantfoot.coupons.portfolio_optimizer import (  # noqa: E402
    optimize_hedged_allocation,
    simulate_correlated_system,
)
from quantfoot.coupons.system_builder import SystemLeg  # noqa: E402
from quantfoot.markets.high_odds_analyzer import (  # noqa: E402
    Balanced1X2Analysis,
    ComebackCandidate,
    scan_high_odds_opportunities,
)
from quantfoot.markets.sharp_lag import load_history_jsonl, scan_sharp_lag  # noqa: E402


def _fmt_ev(ev: float | None) -> str:
    return f"%{100 * ev:+.1f}" if ev is not None else "-"


def _fmt_ms_probs(p: tuple[float, float, float]) -> str:
    return f"%{100*p[0]:.0f} / %{100*p[1]:.0f} / %{100*p[2]:.0f}"


def _fmt_ms_odds(o: tuple[float | None, float | None, float | None]) -> str:
    return " / ".join(f"{x:.2f}" if x is not None else "-" for x in o)


def run(date: str, *, include_started: bool = False, top_n: int = 20) -> dict:
    day_dir = DAILY / date
    ng = json.loads((day_dir / "nesine_global.json").read_text(encoding="utf-8"))

    res_map: dict[int, dict] = {}
    dr_path = day_dir / "derin_tahminler.json"
    if dr_path.exists():
        for row in json.loads(dr_path.read_text(encoding="utf-8")):
            if str(row.get("code", "")).isdigit():
                res_map[int(row["code"])] = dict(row)

    sim_map: dict[int, list[float]] = {}
    sim_path = day_dir / "simulasyon.json"
    if sim_path.exists():
        for srow in json.loads(sim_path.read_text(encoding="utf-8")):
            if str(srow.get("code", "")).isdigit() and srow.get("xg"):
                sim_map[int(srow["code"])] = list(srow["xg"])

    dist_map: dict[int, dict] = {}
    tk_path = day_dir / PREDICTIONS_FILE
    if tk_path.exists():
        tk = json.loads(tk_path.read_text(encoding="utf-8"))
        for code_s, rec in tk.items():
            if str(code_s).isdigit() and rec.get("dist"):
                dist_map[int(code_s)] = dict(rec["dist"])

    now = dt.datetime.now(TSI)
    matches = ng.get("matches", [])
    if not include_started:
        matches = [m for m in matches if dt.datetime.fromisoformat(m["kickoff_iso"]) > now]

    hist_rows = load_history_jsonl(day_dir / "nesine_history.jsonl")
    sharp_lags = scan_sharp_lag(matches, hist_rows, now=now)[:top_n]

    scanned = scan_high_odds_opportunities(matches, res_map, dist_map, sim_map)
    bal_all: list[Balanced1X2Analysis] = scanned["balanced_1x2"]
    bal_actionable = [x for x in bal_all if x.verdict != "PAS (Yazı-Tura)"][:top_n]
    bal_pas = [x for x in bal_all if x.verdict == "PAS (Yazı-Tura)"][:10]
    htft_rev: list[ComebackCandidate] = scanned["htft_reversals"][:top_n]
    half_rev: list[ComebackCandidate] = scanned["half_reversals"][:top_n]
    golden: list[dict] = scanned["golden_scores"][:top_n]

    # Monte Carlo Portföy & Hedge optimizasyonu (günün en iyi 1/2-2/1 veya 2Y KG + güvenli sigorta bacakları)
    by_code = {int(m["code"]): m for m in matches}
    hi_legs: list[SystemLeg] = []
    ins_legs: list[SystemLeg] = []
    seen_ins: set[str] = set()
    for c in htft_rev:
        if c.nesine_odds is None or c.nesine_odds < 2.0 or len(hi_legs) >= 5:
            continue
        m_obj = by_code.get(c.code) or {}
        hi_legs.append(SystemLeg(
            match_id=str(c.code), match=c.match, name=c.selection,
            odds=float(c.nesine_odds), p=float(c.p_calibrated),
            mbs=int(m_obj.get("mbs") or 1), kickoff=c.kickoff, league=c.league,
        ))
        if c.insurance_leg and str(c.code) not in seen_ins and len(ins_legs) < 3:
            for sel in m_obj.get("selections") or []:
                if sel.get("name") in ("1.5 Üst", "2.5 Üst", "KG Var", "2Y 0.5 Üst") and float(sel.get("odds") or 0) >= 1.20 and float(sel.get("fair_prob") or 0) >= 0.65:
                    ins_legs.append(SystemLeg(
                        match_id=str(c.code), match=c.match, name=str(sel["name"]),
                        odds=float(sel["odds"]), p=float(sel["fair_prob"]),
                        mbs=1, kickoff=c.kickoff, league=c.league,
                    ))
                    seen_ins.add(str(c.code))
                    break

    mc_report = simulate_correlated_system(hi_legs, (2,), stake_per_col=5.0, n_sims=10000) if len(hi_legs) >= 3 else None
    hedge_100 = optimize_hedged_allocation(hi_legs, ins_legs, total_budget_tl=100.0) if (len(hi_legs) >= 3 and len(ins_legs) >= 2) else None
    hedge_250 = optimize_hedged_allocation(hi_legs, ins_legs, total_budget_tl=250.0) if (len(hi_legs) >= 3 and len(ins_legs) >= 2) else None

    md: list[str] = [
        f"# {date} — Yüksek Oranlı 1X2, 1/2 & 2/1, Sharp-Lag, Skor Dutching ve Portföy ({now:%H:%M} TSİ)",
        "",
        "Bu rapor 5 ileri algoritmayı tek akışta toplar: (1) **LightGBM Residual + Çoklu Sinyal** dengeli 1X2, "
        "(2) **488 Kulüp 1Y/2Y DNA** ile `1/2` & `2/1` geri dönüşler, (3) **Sharp-Lag** gecikmiş Nesine oranları, "
        "(4) **Multinomial Kalibreli 6 Altın Skor + 2/3-Skor Dutching**, (5) **Monte Carlo Korelasyonlu Portföy & Hedge**.",
        "",
        f"## 0. Sharp-Lag / Gecikmeli Nesine Oranı Sinyalleri ({len(sharp_lags)} sinyal)",
        "",
    ]

    if sharp_lags:
        md += [
            "| Saat | Maç | Seçim | Tip | Nesine | Adil P | EV | Steam | Aciliyet | Neden |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for sl in sharp_lags:
            md.append(
                f"| {sl.kickoff[-5:]} | {sl.match} | **{sl.selection}** | `{sl.source_kind}` | "
                f"{sl.nesine_odds:.2f} | %{100*sl.fair_prob:.1f} | {_fmt_ev(sl.ev)} | {sl.steam_pp:+.1f}p | "
                f"**{sl.urgency_score:.0f}** | {sl.reason} |"
            )
    else:
        md.append("_Şu an eşik üstünde gecikmiş Nesine/steam hız sinyali yok (saatlik çalıştırmalarda tarihçe biriktikçe dolar)._")
    md.append("")

    md += [f"## 1. Dengeli / Yüksek Oranlı 1X2 Analizi ({len(bal_actionable)} net karar / {len(bal_all)} dengeli maç)", ""]
    if bal_actionable:
        md += [
            "| Saat | Lig | Maç | Nesine 1/X/2 | Piyasa P | Çoklu-Sinyal P | Karar | Oran | EV | Güven | Sinyaller / Uyarılar |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---|",
        ]
        for b in bal_actionable:
            note = "; ".join(list(b.signals) + list(b.warnings)) or "-"
            odds_s = f"{b.best_odds:.2f}" if b.best_odds is not None else "-"
            md.append(
                f"| {b.kickoff[-5:]} | {b.league} | {b.match} | {_fmt_ms_odds(b.nesine_ms)} | "
                f"{_fmt_ms_probs(b.market_probs)} | {_fmt_ms_probs(b.post_probs)} | "
                f"**{b.verdict}** | {odds_s} | {_fmt_ev(b.best_ev)} | **{b.confidence_score:.0f}** | {note} |"
            )
    else:
        md.append("_Bu bültende çoklu-sinyal eşiklerini aşan net dengeli 1X2 ayrışması bulunamadı._")
    md.append("")

    if bal_pas:
        md += ["### Yazı-Tura / Tuzak (PAS Verilen Dengeli Maçlar — İlk 10)", ""]
        md += [
            "| Saat | Maç | Nesine 1/X/2 | Çoklu-Sinyal P | En Yakın | Güven | Neden PAS? |",
            "|---|---|---|---|---|---:|---|",
        ]
        for b in bal_pas:
            why = "; ".join(list(b.warnings) + list(b.signals)) or "sinyal ayrışması zayıf / marj yüksek"
            md.append(
                f"| {b.kickoff[-5:]} | {b.match} | {_fmt_ms_odds(b.nesine_ms)} | {_fmt_ms_probs(b.post_probs)} | "
                f"{b.best_side} ({_fmt_ev(b.best_ev)}) | {b.confidence_score:.0f} | {why} |"
            )
        md.append("")

    md += [f"## 2. 1/2 ve 2/1 Tam Geri Dönüş (`İY/MS 1/2`, `İY/MS 2/1` — {len(htft_rev)} aday)", ""]
    if htft_rev:
        md += [
            "| Saat | Lig | Maç | Seçim | Arketip | DNA | Kalibre P | Nesine | EV | Güvenli Sigorta | Gerekçe |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
        ]
        for c in htft_rev:
            od_s = f"{c.nesine_odds:.2f}" if c.nesine_odds is not None else "-"
            why = "; ".join(list(c.reasons) + [f"⚠ {w}" for w in c.warnings]) or "-"
            md.append(
                f"| {c.kickoff[-5:]} | {c.league} | {c.match} | **{c.selection}** | {c.archetype} | "
                f"**{c.dna_score:.1f}** | %{100*c.p_calibrated:.2f} | {od_s} | {_fmt_ev(c.ev)} | {c.insurance_leg or '-'} | {why} |"
            )
    else:
        md.append("_Uygun İY/MS 1/2 veya 2/1 geri dönüş adayı bulunamadı._")
    md.append("")

    md += [f"## 3. Devre Dönüş Adayları (`İY 1 & 2Y 2`, `İY 2 & 2Y 1` — {len(half_rev)} aday)", ""]
    if half_rev:
        md += [
            "| Saat | Lig | Maç | Seçim | Arketip | DNA | Kalibre P | Nesine | EV | Güvenli Sigorta | Gerekçe |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
        ]
        for c in half_rev:
            od_s = f"{c.nesine_odds:.2f}" if c.nesine_odds is not None else "-"
            why = "; ".join(list(c.reasons) + [f"⚠ {w}" for w in c.warnings]) or "-"
            md.append(
                f"| {c.kickoff[-5:]} | {c.league} | {c.match} | **{c.selection}** | {c.archetype} | "
                f"**{c.dna_score:.1f}** | %{100*c.p_calibrated:.1f} | {od_s} | {_fmt_ev(c.ev)} | {c.insurance_leg or '-'} | {why} |"
            )
    else:
        md.append("_Uygun devre dönüşü adayı bulunamadı._")
    md.append("")

    md += [f"## 4. Kalibreli 6 Altın Skor + Canlı Skor EV + 2/3-Skor Dutching ({len(golden)} maç)", ""]
    if golden:
        md += [
            "| Saat | Lig | Maç | #1 Skor | #2 Skor | #3 Skor | En Yüksek EV | En İyi 2/3-Skor Dutching |",
            "|---|---|---|---|---|---|---:|---|",
        ]
        for g in golden:
            slots = []
            for s in g["top_scores"]:
                od = f"@{s.nesine_odds:.2f}" if s.nesine_odds is not None else ""
                ev_t = f" ({100*s.ev:+.0f}%)" if s.ev is not None else ""
                tag = "★" if s.is_golden else ""
                slots.append(f"{tag}**{s.score}** %{100*s.p_model:.1f} {od}{ev_t}".strip())
            while len(slots) < 3:
                slots.append("-")
            dp = g.get("dutching")
            if dp is not None:
                d_s = f"{'/'.join(dp.scores)} @{dp.effective_odds:.2f} (Kapsam %{100*dp.cover_prob:.1f}, EV {100*dp.ev:+.1f}%)"
            else:
                d_s = "-"
            md.append(
                f"| {g['kickoff'][-5:]} | {g['league']} | {g['match']} | {slots[0]} | {slots[1]} | {slots[2]} | {_fmt_ev(g['best_ev'])} | {d_s} |"
            )
    else:
        md.append("_Skor dağılımı bulunan maç yok (önce nesine_global.py çalışmalı)._")

    md += ["", "## 5. Monte Carlo Korelasyonlu Portföy & Hedge Dağıtım Planı", ""]
    if mc_report is not None:
        md.append(
            f"- **1/2 & 2/1 Sistem 2 ({len(hi_legs)} maç, 10.000 Monte Carlo, max korelasyon ρ={mc_report.correlation_used:.2f}):** "
            f"Maliyet **{mc_report.total_cost:.0f} TL** · Beklenen Dönüş **{mc_report.expected_return:.1f} TL** "
            f"(ROI **{100*mc_report.roi:+.1f}%**) · P(Kâr) **%{100*mc_report.p_profit:.1f}** · "
            f"Tam Kayıp P **%{100*mc_report.p_zero_return:.1f}** · P90 Ödeme **{mc_report.p90_payout:,.0f} TL**"
        )
    if hedge_100 is not None:
        md.append(
            f"- **100 TL Hedge Planı:** {hedge_100.high_odds_system} (**{hedge_100.high_odds_budget_tl:.0f} TL**) + "
            f"{hedge_100.hedge_description} → P(Kâr) **%{100*hedge_100.p_profit:.1f}**, "
            f"Tam Kayıp **%{100*hedge_100.p_zero_return:.1f}**, Beklenen Dönüş **{hedge_100.expected_return:.1f} TL** "
            f"(P90 **{hedge_100.p90_payout:,.0f} TL**, Tavan **{hedge_100.max_payout:,.0f} TL**)"
        )
    if hedge_250 is not None:
        md.append(
            f"- **250 TL Hedge Planı:** {hedge_250.high_odds_system} (**{hedge_250.high_odds_budget_tl:.0f} TL**) + "
            f"{hedge_250.hedge_description} → P(Kâr) **%{100*hedge_250.p_profit:.1f}**, "
            f"Tam Kayıp **%{100*hedge_250.p_zero_return:.1f}**, Beklenen Dönüş **{hedge_250.expected_return:.1f} TL** "
            f"(P90 **{hedge_250.p90_payout:,.0f} TL**, Tavan **{hedge_250.max_payout:,.0f} TL**)"
        )
    if mc_report is None:
        md.append("_Bugün canlı Nesine oranlı en az 3 adet 1/2-2/1 adayı çıkmadığı için Monte Carlo sistem kurulamadı._")
    md += [
        "- Kullanıcı onayı olmadan kupon oynanmaz; değer görülmeyen dengeli 1X2 maçlarda **PAS** en kârlı karardır.",
        "",
    ]

    payload = {
        "date": date,
        "generated_at": now.isoformat(timespec="minutes"),
        "sharp_lags": [asdict(x) for x in sharp_lags],
        "balanced_1x2_actionable": [asdict(x) for x in bal_actionable],
        "balanced_1x2_pas": [asdict(x) for x in bal_pas],
        "htft_reversals": [asdict(x) for x in htft_rev],
        "half_reversals": [asdict(x) for x in half_rev],
        "golden_scores": [
            {
                "code": g["code"],
                "kickoff": g["kickoff"],
                "league": g["league"],
                "match": g["match"],
                "best_ev": g["best_ev"],
                "top_scores": [asdict(s) for s in g["top_scores"]],
                "dutching": asdict(g["dutching"]) if g.get("dutching") is not None else None,
            }
            for g in golden
        ],
        "monte_carlo_portfolio": asdict(mc_report) if mc_report is not None else None,
        "hedge_100": asdict(hedge_100) if hedge_100 is not None else None,
        "hedge_250": asdict(hedge_250) if hedge_250 is not None else None,
    }
    (day_dir / "yuksek_oran_analiz.md").write_text("\n".join(md), encoding="utf-8")
    (day_dir / "yuksek_oran_analiz.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Günlük yüksek oranlı 1X2, 1/2 & 2/1, Sharp-Lag ve Skor Dutching analizi")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--tumu", action="store_true", help="Başlamış maçları da dahil et")
    args = ap.parse_args()
    out = run(args.tarih, include_started=args.tumu, top_n=args.top)
    print(
        f"{args.tarih}: {len(out['sharp_lags'])} sharp-lag, {len(out['balanced_1x2_actionable'])} dengeli 1X2, "
        f"{len(out['htft_reversals'])} 1/2-2/1, {len(out['golden_scores'])} skor -> "
        f"{DAILY / args.tarih / 'yuksek_oran_analiz.md'}"
    )


if __name__ == "__main__":
    main()
