"""Günlük Yüksek Oran Uzman Analizi: Denk Maç (1X2), İY/MS 1/2 & 2/1, İki Yarıda KG Var, Doğru Skor & Bayat Oran.

    QUANTFOOT_AI=geminitahmin python scripts/yuksek_oran_analiz.py --tarih 2026-11-26

Girdiler: tahminler/<QUANTFOOT_AI>/<tarih>/nesine_global.json (+ varsa derin_tahminler.json, takip_kayit.json).
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
from quantfoot.markets.high_odds_engine import scan_high_odds_day  # noqa: E402


def _render_close_matches(items: list) -> list[str]:
    lines = [f"## 1. Denk & Yüksek Oranlı 1X2 Maç Çözücü ({len(items)} maç)", ""]
    if not items:
        lines += ["_Dengeli/yüksek oranlı 1X2 adayı bulunamadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Nesine 1/0/2 | Piyasa → Model (%) | En İyi Tercih | EV | Güven | Beraberlik Rejimi | Çifte Şans Alternatifi | Karar / Gerekçe |",
        "|---|---|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for c in items:
        o = c.nesine_odds_1x2
        odds_s = f"{o['MS 1'] or '-'} / {o['MS 0'] or '-'} / {o['MS 2'] or '-'}"
        mp = c.market_1x2
        md = c.model_1x2
        prob_s = (
            f"{100*mp['MS 1']:.0f}/{100*mp['MS 0']:.0f}/{100*mp['MS 2']:.0f} → "
            f"**{100*md['MS 1']:.0f}/{100*md['MS 0']:.0f}/{100*md['MS 2']:.0f}**"
        )
        ev_s = f"%{100*c.best_ev:+.1f}" if c.best_ev is not None else "-"
        best_s = f"**{c.best_outcome}** @{c.best_odds:.2f}" if c.best_odds else f"**{c.best_outcome}**"
        safe_s = (
            f"{c.safe_alternative} @{c.safe_alternative_odds:.2f} (%{100*(c.safe_alternative_prob or 0):.0f})"
            if c.safe_alternative and c.safe_alternative_odds
            else (f"{c.safe_alternative} (%{100*(c.safe_alternative_prob or 0):.0f})" if c.safe_alternative else "-")
        )
        note = "; ".join(c.reasons[:2])
        if c.warnings:
            note = (note + " | ⚠ " + "; ".join(c.warnings[:1])).strip(" |")
        lines.append(
            f"| {c.kickoff[-5:]} | {c.league} | {c.match} | {odds_s} | {prob_s} | {best_s} | "
            f"{ev_s} | **{c.conviction_score:.0f}** | {c.draw_regime_score:.0f}/100 | {safe_s} | **{c.verdict}** — {note or '-'} |"
        )
    lines.append("")
    return lines


def _render_comebacks(items: list) -> list[str]:
    lines = [f"## 2. İY/MS Geri Dönüş Adayları — 1/2 ve 2/1 ({len(items)} aday)", ""]
    if not items:
        lines += ["_Bu eşikte İY/MS 1/2 veya 2/1 geri dönüş adayı bulunamadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Tercih | Arketip | xG | 1Y Payı (Ev/Dep) | DNA | Model P (Adil) | Nesine Oran | EV | Güvenli Sigorta | Neden |",
        "|---|---|---|---|---|---|---|---:|---|---:|---:|---|---|",
    ]
    for c in items:
        ev_s = f"%{100*c.ev:+.1f}" if c.ev is not None else "-"
        odds_s = f"{c.nesine_odds:.2f}" if c.nesine_odds is not None else "-"
        lad = ", ".join(f"{lg.name} @{lg.odds:.2f}" for lg in c.safe_ladder[:2]) or "-"
        note = "; ".join(c.reasons[:2]) or "-"
        lines.append(
            f"| {c.kickoff[-5:]} | {c.league} | {c.match} | **{c.kind}** | {c.archetype} | "
            f"{c.mu_home:.2f}-{c.mu_away:.2f} | %{100*c.home_1h_share:.0f}/%{100*c.away_1h_share:.0f} | "
            f"**{c.dna_score:.1f}** | %{100*c.p_comeback:.1f} (@{c.fair_odds:.1f}) | {odds_s} | {ev_s} | {lad} | {note} |"
        )
    lines.append("")
    return lines


def _render_both_btts(items: list) -> list[str]:
    lines = [f"## 3. İki Yarıda KG Var Adayları ({len(items)} aday)", ""]
    if not items:
        lines += ["_Bu eşikte İki Yarıda KG Var adayı bulunamadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Arketip | xG (Ev-Dep) | DNA | Kuyruk P | Nesine Oran | EV | Güvenli Merdiven | Neden |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for c in items:
        ev_s = f"%{100*c.ev:+.1f}" if c.ev is not None else "-"
        odds_s = f"{c.nesine_odds:.2f}" if c.nesine_odds is not None else "-"
        lad = ", ".join(f"{lg.name} @{lg.odds:.2f}" for lg in c.safe_ladder[:2]) or "-"
        note = "; ".join(c.reasons[:2]) or "-"
        lines.append(
            f"| {c.kickoff[-5:]} | {c.league} | {c.match} | {c.archetype} | {c.mu_home:.2f}-{c.mu_away:.2f} | "
            f"**{c.dna_score:.1f}** | %{100*c.p_tail:.1f} | {odds_s} | {ev_s} | {lad} | {note} |"
        )
    lines.append("")
    return lines


def _render_exact_scores(items: list) -> list[str]:
    lines = [f"## 4. Doğru Skor & Değer Skorları ({len(items)} maç)", ""]
    if not items:
        lines += ["_Skor adayı bulunamadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Skor Rejimi | En Olası 3 Uyumlu Skor | +EV Değer Skorları | Geri Dönüş Skorları |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in items:
        top3 = ", ".join(
            f"**{x.score}** (%{100*x.prob:.1f}" + (f" @{x.nesine_odds:.1f}" if x.nesine_odds else "") + ")"
            for x in e.top_coherent[:3]
        )
        val3 = ", ".join(
            f"**{x.score}** @{x.nesine_odds:.1f} (EV %{100*(x.ev or 0):+.0f})"
            for x in e.value_scores[:3]
        ) or "-"
        cb3 = ", ".join(f"{x.score} (%{100*x.prob:.1f})" for x in e.comeback_scores[:3]) or "-"
        lines.append(f"| {e.kickoff[-5:]} | {e.league} | {e.match} | {e.cluster} | {top3} | {val3} | {cb3} |")
    lines.append("")
    return lines


def _render_stale_edges(items: list) -> list[str]:
    lines = [f"## 5. Nesine Bayat Oran & Düşük Marj Fırsatları ({len(items)} seçim)", ""]
    if not items:
        lines += ["_Bayat oran / düşük marj anomalisi saptanmadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Seçim | Tür | Nesine | Adil P | EV | Keskin Steam | Not |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for a in items:
        st = f"{a.dir_steam_pp:+.1f}p" if a.dir_steam_pp is not None else "-"
        lines.append(
            f"| {a.kickoff[-5:]} | {a.league} | {a.match} | **{a.selection_name}** | {a.kind} | "
            f"{a.nesine_odds:.2f} | %{100*a.fair_prob:.1f} | **%{100*a.ev:+.1f}** | {st} | {a.note} |"
        )
    lines.append("")
    return lines


def run(date: str, *, only_offered: bool = True, top_n: int = 10, min_dna: float = 52.0) -> dict:
    day_dir = DAILY / date
    ng = json.loads((day_dir / "nesine_global.json").read_text(encoding="utf-8"))
    dr_path = day_dir / "derin_tahminler.json"
    res_map: dict[int, dict] = {}
    if dr_path.exists():
        for row in json.loads(dr_path.read_text(encoding="utf-8")):
            if str(row.get("code", "")).isdigit():
                res_map[int(row["code"])] = dict(row)

    ft_dist_map: dict[int, dict] = {}
    pred_path = day_dir / PREDICTIONS_FILE
    if pred_path.exists():
        try:
            store = json.loads(pred_path.read_text(encoding="utf-8"))
            for k, v in store.items():
                if str(k).isdigit() and (v.get("dist") or {}).get("ft"):
                    ft_dist_map[int(k)] = v["dist"]["ft"]
        except (OSError, json.JSONDecodeError):
            pass

    now = dt.datetime.now(TSI)
    upcoming = [m for m in ng.get("matches", []) if dt.datetime.fromisoformat(m["kickoff_iso"]) > now]
    scanned = scan_high_odds_day(
        upcoming,
        res_map,
        ft_dist_by_code=ft_dist_map,
        only_offered=only_offered,
        min_comeback_dna=min_dna,
        min_btts_dna=max(min_dna, 55.0),
        top_n=top_n,
    )

    sys_lines: list[str] = []
    for best in scanned["systems_100tl"][:2]:
        sz_s = ",".join(str(x) for x in best.sizes)
        min_k = min(best.sizes)
        p_min = best.p_at_least.get(min_k, 0.0)
        lo_m, hi_m = best.hit_table.get(min_k, (0.0, 0.0))
        sys_lines.append(
            f"- **Yüksek Oran Sistem ({best.n_legs} maç, Sistem {sz_s}):** {best.n_cols} kolon × "
            f"{best.stake_per_col:.0f} TL = **{best.total_cost:.0f} TL** | Tavan: **{best.max_payout:,.0f} TL** "
            f"| {min_k}+ isabet: %{100*p_min:.1f} ({lo_m:.0f}–{hi_m:.0f} TL) | P(Kâr): %{100*best.p_profit:.1f}"
        )

    md = [
        f"# {date} — Yüksek Oran, Denk Maç, İY/MS (1/2 & 2/1), İki Yarıda KG ve Doğru Skor Analizi ({now:%H:%M} TSİ)",
        "",
        "Canlı 2026/27 xG, takım yarı-payı asimetrisi, Asya Handikapı, keskin steam ve makro-uyumlu skor "
        "dağılımıyla üretilmiştir. (Öneridir; kullanıcı onayı olmadan bahis oynanmaz.)",
        "",
        *_render_close_matches(scanned["close_matches"]),
        *_render_comebacks(scanned["comebacks"]),
        *_render_both_btts(scanned["both_halves_btts"]),
        *_render_exact_scores(scanned["exact_scores"]),
        *_render_stale_edges(scanned["stale_edges"]),
    ]
    if sys_lines:
        md += ["## 6. 100 TL MBS-Uyumlu Yüksek Oran Sistem Kuponu Özeti", "", *sys_lines, ""]

    payload = {
        "date": date,
        "generated_at": now.isoformat(timespec="minutes"),
        "only_offered": only_offered,
        "min_dna": min_dna,
        "close_matches": [x.to_dict() for x in scanned["close_matches"]],
        "comebacks": [x.to_dict() for x in scanned["comebacks"]],
        "both_halves_btts": [asdict(x) for x in scanned["both_halves_btts"]],
        "exact_scores": [x.to_dict() for x in scanned["exact_scores"]],
        "stale_edges": [x.to_dict() for x in scanned["stale_edges"]],
        "systems_100tl": [asdict(x) for x in scanned["systems_100tl"]],
    }
    (day_dir / "yuksek_oran_analiz.md").write_text("\n".join(md), encoding="utf-8")
    (day_dir / "yuksek_oran_analiz.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Günlük yüksek oran, denk maç, İY/MS 1/2-2/1 ve doğru skor analiz aracı")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-dna", type=float, default=52.0)
    ap.add_argument("--tumu", action="store_true", help="Nesine'de oranı açık olmayan maçları da dahil et")
    args = ap.parse_args()
    out = run(args.tarih, only_offered=not args.tumu, top_n=args.top, min_dna=args.min_dna)
    print(
        f"{args.tarih}: {len(out['close_matches'])} denk maç, {len(out['comebacks'])} İY/MS geri dönüş, "
        f"{len(out['both_halves_btts'])} İki Yarıda KG, {len(out['exact_scores'])} doğru skor -> "
        f"{DAILY / args.tarih / 'yuksek_oran_analiz.md'}"
    )


if __name__ == "__main__":
    main()
