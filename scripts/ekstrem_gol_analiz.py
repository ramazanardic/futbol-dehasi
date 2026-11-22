"""Günlük 6+ Gol / 5,5 Üst ve İki Yarıda KG Var uzman taraması (kendi AI klasörü içinde).

    QUANTFOOT_AI=antigravitytahmin python scripts/ekstrem_gol_analiz.py --tarih 2026-11-23

Girdiler: tahminler/<QUANTFOOT_AI>/<tarih>/nesine_global.json (+ varsa derin_tahminler.json).
Çıktılar: tahminler/<QUANTFOOT_AI>/<tarih>/ekstrem_gol_analiz.md / .json
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

from nesine_global import DAILY, TSI  # noqa: E402
from quantfoot.markets.extreme_goals import ExtremeGoalCandidate, scan_extreme_goals  # noqa: E402


def _render_section(title: str, items: list[ExtremeGoalCandidate]) -> list[str]:
    lines = [f"## {title} ({len(items)} aday)", ""]
    if not items:
        lines += ["_Bu eşikte Nesine'de açık aday bulunamadı._", ""]
        return lines
    lines += [
        "| Saat | Lig | Maç | Arketip | xG (Ev-Dep) | DNA | Kuyruk P | Nesine Oran | EV | Güvenli Merdiven (%64+) | Neden / Uyarı |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|---|",
    ]
    for c in items:
        ev_s = f"%{100 * c.ev:+.1f}" if c.ev is not None else "-"
        odds_s = f"{c.nesine_odds:.2f}" if c.nesine_odds is not None else "-"
        lad = ", ".join(f"{lg.name} @{lg.odds:.2f} (%{100*lg.fair_prob:.0f})" for lg in c.safe_ladder) or "-"
        notes = "; ".join(c.reasons[:2])
        if c.warnings:
            notes = (notes + " | ⚠ " + "; ".join(c.warnings[:1])).strip(" |")
        lines.append(
            f"| {c.kickoff[-5:]} | {c.league} | {c.match} | {c.archetype} | {c.mu_home:.2f}-{c.mu_away:.2f} | "
            f"**{c.dna_score:.1f}** | %{100*c.p_tail:.1f} | {odds_s} | {ev_s} | {lad} | {notes or '-'} |"
        )
    lines.append("")
    return lines


def run(date: str, *, only_offered: bool = True, top_n: int = 10, min_dna: float = 55.0) -> dict:
    day_dir = DAILY / date
    ng = json.loads((day_dir / "nesine_global.json").read_text(encoding="utf-8"))
    dr_path = day_dir / "derin_tahminler.json"
    res_map: dict[int, dict] = {}
    if dr_path.exists():
        for row in json.loads(dr_path.read_text(encoding="utf-8")):
            if str(row.get("code", "")).isdigit():
                res_map[int(row["code"])] = row
    now = dt.datetime.now(TSI)
    upcoming = [m for m in ng.get("matches", []) if dt.datetime.fromisoformat(m["kickoff_iso"]) > now]
    scanned = scan_extreme_goals(
        upcoming,
        res_map,
        only_offered=only_offered,
        min_dna_6plus=min_dna,
        min_dna_both_btts=min_dna,
        top_n=top_n,
    )
    md = [
        f"# {date} — 6+ Gol ve İki Yarıda KG Var Uzman Analizi ({now:%H:%M} TSİ)",
        "",
        "İki katmanlı çıktı: (1) Yüksek oranlı **6+ Gol / 5,5 Üst** ve **İki Yarıda KG Var** değer adayları "
        "(hedef: %18–30 isabetle pozitif ROI), (2) Aynı yüksek-DNA maçların **%64–70+ güvenli gol merdiveni**.",
        "",
        *_render_section("6+ Gol / 5,5 Üst Adayları", scanned["6plus"]),
        *_render_section("İki Yarıda KG Var Adayları", scanned["both_halves_btts"]),
    ]
    payload = {
        "date": date,
        "generated_at": now.isoformat(timespec="minutes"),
        "only_offered": only_offered,
        "min_dna": min_dna,
        "6plus": [asdict(x) for x in scanned["6plus"]],
        "both_halves_btts": [asdict(x) for x in scanned["both_halves_btts"]],
    }
    (day_dir / "ekstrem_gol_analiz.md").write_text("\n".join(md), encoding="utf-8")
    (day_dir / "ekstrem_gol_analiz.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Günlük 6+ Gol ve İki Yarıda KG Var uzman tarayıcı")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--min-dna", type=float, default=55.0)
    ap.add_argument("--tumu", action="store_true", help="Nesine'de oranı açık olmayan maçları da listele")
    args = ap.parse_args()
    out = run(args.tarih, only_offered=not args.tumu, top_n=args.top, min_dna=args.min_dna)
    print(f"{args.tarih}: {len(out['6plus'])} adet 6+ Gol, {len(out['both_halves_btts'])} adet İki Yarıda KG Var adayı -> {DAILY / args.tarih / 'ekstrem_gol_analiz.md'}")


if __name__ == "__main__":
    main()
