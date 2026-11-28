"""Tek parça temiz karar ve kupon üreticisi (QuantFoot Unified Engine).

Kullanım:
    QUANTFOOT_AI=antigravitytahmin python scripts/temiz_kupon.py --tarih 2026-11-28
    QUANTFOOT_AI=antigravitytahmin python scripts/temiz_kupon.py --tarih 2026-11-28 --pencere-saat 3 --adet-20x 3
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nesine_global import DAILY, TSI, analyze_day  # noqa: E402
import nesine_kupon as nk  # noqa: E402
from quantfoot.coupons.unified_engine import (  # noqa: E402
    UnifiedCoupon,
    build_clean_slate_portfolio,
)


def render_portfolio_markdown(date: str, coupons: list[UnifiedCoupon], now: dt.datetime) -> str:
    lines = [
        f"# {date} — Tek Parça Temiz Karar Motoru Kuponları ({now:%H:%M} TSİ)",
        "",
        "Yalnız keskin global referanslar, kanıtlanmış Altın Çekirdek pazarlar (`%72–80` bandı), "
        "yönlü Transfermarkt kaleci/golcü motoru ve 4+ maçlı kuponlarda otomatik tek-bacak sistem sigortası.",
        "",
        "| Kupon | Tür | Maç (MBS) | Toplam Oran | Kalibre Olasılık | Tek-Bacak Sigorta (Sistem n-1, n) |",
        "|---|---|---:|---:|---:|---|",
    ]
    for c in coupons:
        ins_s = "-"
        if c.insurance is not None:
            k_min = min(c.insurance.sizes)
            p_k = c.insurance.p_at_least.get(k_min, 0.0)
            lo_pay, hi_pay = c.insurance.hit_table.get(k_min, (0.0, 0.0))
            ins_s = f"Sistem {','.join(str(x) for x in c.insurance.sizes)}: ≥{k_min} isabet **%{p_k*100:.1f}** ({lo_pay:.0f}–{hi_pay:.0f} TL / 100 TL)"
        lines.append(
            f"| **{c.coupon_id}** | {c.title} | {len(c.legs)} (MBS {c.max_mbs}) | **{c.total_odds:.2f}x** | **%{c.joint_prob*100:.1f}** | {ins_s} |"
        )
    lines.append("")
    for c in coupons:
        lines += [
            f"## {c.coupon_id} — {c.title}",
            "",
            f"**Toplam Oran:** `{c.total_odds:.2f}x` · **Kalibre Tutma Olasılığı:** `%{c.joint_prob*100:.2f}` · **MBS:** `{c.max_mbs}`",
            "",
            f"> {c.note}",
            "",
            "| Saat | Lig | Maç | Seçim | Oran | Olasılık | MBS | Gerekçe |",
            "|---|---|---|---|---:|---:|---:|---|",
        ]
        for lg in c.legs:
            lines.append(
                f"| {lg.kickoff[11:]} | {lg.league} | **{lg.match}** | **{lg.name}** | {lg.odds:.2f} | "
                f"%{lg.prob*100:.1f} | {lg.mbs} | {'; '.join(lg.reasons)} |"
            )
        if c.insurance is not None:
            k_min = min(c.insurance.sizes)
            lines += [
                "",
                f"- **100 TL Tek-Bacak Sigorta (`Sistem {','.join(str(x) for x in c.insurance.sizes)}`):** "
                f"{c.insurance.n_cols} kolon × {c.insurance.stake_per_col:.1f} TL = `{c.insurance.total_cost:.0f} TL` · "
                f"{k_min}+ isabet: **%{c.insurance.p_at_least.get(k_min, 0.0)*100:.1f}** · "
                f"P(Kâr): **%{c.insurance.p_profit*100:.1f}** · Tavan: **{c.insurance.max_payout:,.0f} TL**",
            ]
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> Path | None:
    ap = argparse.ArgumentParser(description="Tek parça temiz karar ve kupon üreticisi")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--hazir-bulten", action="store_true", help="Var olan nesine_global.json dosyasını kullan")
    ap.add_argument("--canli-oran-yok", action="store_true", help="Canlı çift-okuma oran teyidini atla (çevrimdışı test)")
    ap.add_argument("--pencere-saat", type=float, default=None, help="Yalnızca en çok N saat içinde başlayacak maçlar")
    ap.add_argument("--adet-20x", type=int, default=2, help="Kaç adet bağımsız 20+ oran kuponu üretilsin")
    args = ap.parse_args(argv)

    day_dir = DAILY / args.tarih
    ng_path = day_dir / "nesine_global.json"
    if args.hazir_bulten and ng_path.exists():
        matches = json.loads(ng_path.read_text(encoding="utf-8")).get("matches", [])
    else:
        matches, _, _ = analyze_day(dt.date.fromisoformat(args.tarih), verbose=True, use_tm=True)

    if not args.canli_oran_yok:
        live, _ = nk.read_bulletin_odds(reads=2, gap_s=2.0)
        nk.apply_live_odds(matches, live)

    now = dt.datetime.now(TSI)
    coupons = build_clean_slate_portfolio(
        matches,
        now=now,
        min_minutes_to_kickoff=20,
        max_hours_to_kickoff=args.pencere_saat,
        n_20x=args.adet_20x,
    )
    if not coupons:
        print("Temiz kuralları geçen kupon kurulamadı.")
        return None

    day_dir.mkdir(parents=True, exist_ok=True)
    md_path = day_dir / f"temiz_kuponlar_{now:%H%M}.md"
    md_text = render_portfolio_markdown(args.tarih, coupons, now)
    md_path.write_text(md_text, encoding="utf-8")

    csv_rows = []
    for idx, c in enumerate(coupons, 1):
        for lg in c.legs:
            csv_rows.append({
                "tarih": args.tarih,
                "kupon_turu": c.mode,
                "kupon": c.coupon_id,
                "kupon_no": str(idx),
                "kupon_toplam_oran": f"{c.total_odds:.2f}",
                "kupon_tutma_olasiligi": f"{c.joint_prob:.6f}",
                "saat": lg.kickoff[11:],
                "mac": lg.match,
                "nesine_kodu": str(lg.code),
                "pazar": lg.market,
                "secim": lg.selection,
                "nesine_oran": f"{lg.odds:.2f}",
                "olasilik": f"{lg.prob:.4f}",
                "secim_adi": lg.name,
            })
    csv_path = day_dir / "kuponlar.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(csv_rows[0]))
        w.writeheader()
        w.writerows(csv_rows)

    print(md_text)
    print(f"-> {md_path} & {csv_path}")
    return md_path


if __name__ == "__main__":
    main()
