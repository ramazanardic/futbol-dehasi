"""Generate 5 mathematically disjoint Nesine coupons (each >= 20.00 total odds) from Global Sharp analysis."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from scripts.analyze_nov19_nesine_global import (  # noqa: E402
    MATCH_DATA,
    _build_verified_coupon,
    _pick_leg,
    analyze_match,
)


def build_20x_disjoint_coupons() -> list[dict]:
    """Construct 5 completely disjoint >= 20.00x coupons with zero repeated (match, selection) pairs."""
    results = [analyze_match(m) for m in MATCH_DATA]
    by_idx = {r["idx"]: r for r in results}

    specs = [
        (
            "2026_11_19_20X_SET_1_CORE_VALUE",
            "KUPON 1 — Küresel Değer & Sıfır Vergi 20x+ Ana Kombinesi",
            "Kademe 1 (En Düşük Nesine Vergili Global 1X2+O/U Lig Karması — 0 Kupa Maçı)",
            "5-Kupon Bütçesinin %30'u",
            "Düz 9'lu veya Sistem 7-8/9 (Tüm ayaklar tam Global 1X2+O/U verili lig maçları; Ort. Global P=%63.8)",
            [
                (15, "KG Yok", "Al Wasl 1.09 favori (xG 3.48-0.54, EV -%1.4).", "Karşılıksız Gol"),
                (28, "KG Yok", "AL Ain 1.09 favori (xG 3.25-0.45, sıfır vergi EV +%0.5).", "Karşılıksız Gol"),
                (7, "2.5 Üst", "Cong An - Johor tempolu grup maçı (Flashscore 1.50 Over).", "Alt/Üst"),
                (4, "KG Var", "Preah Khan - Port dengeli açık maç (xG 1.51-1.43).", "Karşılıklı Gol"),
                (16, "KG Yok", "İran Pro Ligi düşük gol beklentisi (xG 0.80-0.77 -> %68.8).", "Karşılıksız Gol"),
                (25, "MS 2", "Fratria Varna deplasman üstünlüğü (Flashscore 1.72).", "Maç Sonucu (1X2)"),
                (38, "2.5 Üst", "Paris (K) 9-6 L5 vs HB Koege (K) 7-12 L5 (P=%65.0).", "Alt/Üst"),
                (45, "MS 1", "Penarol iç saha lig dominasyonu (Flashscore 1.39 -> %68.8).", "Maç Sonucu (1X2)"),
                (52, "3.5 Alt", "Vasco - Internacional (Pinnacle + Flashscore 3.5 Alt %69.9).", "Alt/Üst"),
            ],
        ),
        (
            "2026_11_19_20X_SET_2_GOALS_BTTS",
            "KUPON 2 — Saf Gol & KG Yağmuru 20x+ Kuponu (Sıfır MS Taraf Riski)",
            "Kademe 2 (Yalnızca Alt/Üst & KG Seçenekleri — Yüksek Tempo Maçları)",
            "5-Kupon Bütçesinin %25'i",
            "Düz 10'lu veya Sistem 8-9/10 (Sıfır MS taraf riski; tüm maçlarda Global gol/KG olasılığı >= %54.1)",
            [
                (1, "3.5 Üst", "Preston Lions - South Hobart (xG 3.32-0.76, Top 4.08).", "Alt/Üst"),
                (2, "KG Var", "Queensland L. - Woll. Wolves (xG 2.34-1.26 -> %66.4).", "Karşılıklı Gol"),
                (5, "KG Yok", "Persib Bandung 1.07 favori (xG 3.39-0.48 -> %62.6).", "Karşılıksız Gol"),
                (4, "2.5 Üst", "Preah Khan - Port (xG 2.95 — K1'deki KG Var yerine 2.5 Üst).", "Alt/Üst"),
                (7, "KG Var", "Cong An - Johor (xG 1.15-2.07 — K1'deki 2.5 Üst yerine KG Var).", "Karşılıklı Gol"),
                (30, "KG Var", "Katar Ligi Al Ahli Doha - Al Shamal (xG 1.55-1.95 -> %69.4).", "Karşılıklı Gol"),
                (40, "2.5 Üst", "Fredericia - Hilleroed (Flashscore 1.38 Over -> %68.2).", "Alt/Üst"),
                (48, "2.5 Üst", "Arsenal (K) - OL Lyonnes (K) (Pinnacle/Flashscore xG 3.39).", "Alt/Üst"),
                (50, "2.5 Üst", "Benfica (K) L5 6-9 vs Roma (K) L5 8-10 (%63.5).", "Alt/Üst"),
                (57, "3.5 Üst", "Orlando City (9-9 L5) - Cincinnati (7-5 L5) MLS Playoff xG 3.87.", "Alt/Üst"),
            ],
        ),
        (
            "2026_11_19_20X_SET_3_SIDES_LEAGUES",
            "KUPON 3 — Favori Taraf Baskısı & Dengeli Ligler 20x+ Kuponu (0 Kupa Maçı)",
            "Kademe 3 (Küresel MS Favorileri + Düşük Riskli Lig Tamamlayıcıları)",
            "5-Kupon Bütçesinin %20'si",
            "Düz 10'lu veya Sistem 8/10 (0 Kupa maçı; her ayakta Global P >= %53.7, Ort. %62.5)",
            [
                (2, "MS 1", "Queensland Lions iç saha (xG 2.34-1.26 -> %60.8).", "Maç Sonucu (1X2)"),
                (7, "MS 2", "Johor Darul kalite farkı (xG 1.15-2.07 -> %58.0).", "Maç Sonucu (1X2)"),
                (34, "MS 1", "MC Alger iç saha (Flashscore 1.37 -> %69.8).", "Maç Sonucu (1X2)"),
                (38, "MS 1", "Paris FC (K) iç saha (Pinnacle 1.67, HB Koege L5 12 GA).", "Maç Sonucu (1X2)"),
                (43, "2.5 Alt", "JS Kabylie - USM Alger Cezayir savunması (xG 2.03 -> %66.5).", "Alt/Üst"),
                (44, "MS 2", "Torque deplasman gücü (Flashscore 1.41 -> %67.8).", "Maç Sonucu (1X2)"),
                (46, "MS 2", "D. Maldonado deplasman değeri (Flashscore 1.75 -> %53.7).", "Maç Sonucu (1X2)"),
                (52, "MS 1", "Vasco da Gama iç saha (Pinnacle 1.69, L5 3G-0B-2M -> %57.6).", "Maç Sonucu (1X2)"),
                (53, "MS 1", "U. Magdalena iç saha (Flashscore 1.51 -> %63.0).", "Maç Sonucu (1X2)"),
                (56, "1.5 Üst", "Sao Paulo - Fluminense en az 2 gol (%72.1).", "Alt/Üst"),
            ],
        ),
        (
            "2026_11_19_20X_SET_4_LOCK_DEFENSE_CUPS",
            "KUPON 4 — Savunma Kilidi (KG Yok / Alt) & 90' Kupa Favorileri 20x+ Kuponu",
            "Kademe 4 (Düşük Skorlu & Kupa Favori Eşleşmeleri — Farklı Tercihler)",
            "5-Kupon Bütçesinin %15'i",
            "Düz 10'lu veya Sistem 7-8/10 (Kupa maçları 90 dk risk notlu; Bayern L5 9 GA uyarılı; Ort. Global P=%62.7)",
            [
                (13, "MS 2", "NK Celje Slovenya Kupası 90' kalite farkı (Flashscore 1.32 -> %72.8).", "Maç Sonucu (1X2)"),
                (14, "MS 2", "NK Bistrica Slovenya Kupası 90' deplasman (Flashscore 1.65 -> %57.2).", "Maç Sonucu (1X2)"),
                (26, "MS 1", "Al Mokawloon Mısır Kupası 90' iç saha (Flashscore 1.62 -> %58.3).", "Maç Sonucu (1X2)"),
                (27, "MS 1", "Al Masry Mısır Kupası 90' iç saha (Flashscore 1.71 -> %55.0).", "Maç Sonucu (1X2)"),
                (33, "KG Yok", "MB Rouisset - CR Belouizdad Cezayir düşük xG 1.92 (%64.5).", "Karşılıksız Gol"),
                (34, "KG Yok", "MC Alger - Akbou (xG 1.86-0.49 — K3'teki MS 1 yerine KG Yok %66.1).", "Karşılıksız Gol"),
                (37, "KG Yok", "Austria Wien (K) - B. Münih (K) (EV +%0.5, P=%71.3; Bayern L5 9 GA notlu).", "Karşılıksız Gol"),
                (43, "KG Yok", "JS Kabylie - USM Alger (K3'teki 2.5 Alt yerine KG Yok %58.9).", "Karşılıksız Gol"),
                (45, "KG Yok", "Penarol - Cerro Largo (xG 1.95-0.62 — K1'deki MS 1 yerine KG Yok %59.2).", "Karşılıksız Gol"),
                (59, "2.5 Alt", "Cundinamarca - Deportes Quindio Kolombiya B (xG 2.12 -> %64.2).", "Alt/Üst"),
            ],
        ),
        (
            "2026_11_19_20X_SET_5_BTTS_ALT_VARIETY",
            "KUPON 5 — Çapraz KG Var & Üst/Alt Alternatif 20x+ Kuponu",
            "Kademe 5 (Yüksek Gol / Karşılıklı Gol Uyumlu Çapraz Çeşitleme)",
            "5-Kupon Bütçesinin %10'u",
            "Düz 10'lu veya Sistem 7-8/10 (Önceki 4 kuponla 0 ortak tercih; tüm ayaklar tam Global 1X2+O/U doğrulamalı)",
            [
                (15, "3.5 Üst", "Al Wasl - Hatta SC (xG 4.01, Flashscore 1.64 Over 3.5 -> %56.8).", "Alt/Üst"),
                (27, "1.5 Üst", "Al Masry - Asyut Petroleum Mısır Kupası (%65.2).", "Alt/Üst"),
                (30, "2.5 Üst", "Al Ahli Doha - Al Shamal (xG 3.50 — K2'deki KG Var yerine 2.5 Üst).", "Alt/Üst"),
                (36, "KG Var", "Sveikata - Hegelmann Litauen B playoff açık oyun (%65.1).", "Karşılıklı Gol"),
                (38, "KG Var", "Paris (K) - HB Koege (K) (xG 2.37-1.29 -> %60.1).", "Karşılıklı Gol"),
                (40, "KG Var", "Fredericia - Hilleroed (xG 2.65-0.89 -> %56.1).", "Karşılıklı Gol"),
                (47, "KG Var", "Amiens - Caen Fransa Ulusal dengeli gol beklentisi (xG 2.62).", "Karşılıklı Gol"),
                (50, "KG Var", "Benfica (K) - Roma (K) (her iki takım L5'te gol atıp yiyor -> %62.5).", "Karşılıklı Gol"),
                (52, "KG Var", "Vasco (8-7 L5) - Internacional (6-5 L5) (%54.0).", "Karşılıklı Gol"),
                (54, "2.5 Alt", "Independiente Yumbo - Envigado Kolombiya B (xG 2.15 -> %63.7).", "Alt/Üst"),
            ],
        ),
    ]

    coupons: list[dict] = []
    seen_pairs: set[tuple[int, str]] = set()

    for cid, title, tier, stake_pct, sys_note, raw_legs in specs:
        picked = []
        seen_in_coupon: set[int] = set()
        for idx, sel, note, cat in raw_legs:
            if idx in seen_in_coupon:
                raise ValueError(f"Duplicate match #{idx} inside coupon {cid}")
            seen_in_coupon.add(idx)
            pair = (idx, sel)
            if pair in seen_pairs:
                raise ValueError(f"REPEATED SELECTION ACROSS COUPONS: match #{idx} selection {sel!r}")
            seen_pairs.add(pair)
            picked.append(_pick_leg(by_idx, idx, sel, note, cat))

        c = _build_verified_coupon(
            coupon_id=cid,
            title=title,
            tier=tier,
            stake_pct=stake_pct,
            system_note=sys_note,
            legs=picked,
        )
        if c["total_odds"] < 20.00:
            raise ValueError(f"Coupon {cid} odds {c['total_odds']} < 20.00 minimum requirement!")
        coupons.append(c)

    if len(coupons) < 4:
        raise ValueError(f"Must build at least 4 coupons, got {len(coupons)}")
    return coupons


def main() -> None:
    coupons = build_20x_disjoint_coupons()
    total_legs = sum(c["leg_count"] for c in coupons)

    md_lines = [
        "# 19 Kasım 2026 — Minimum 20 Oranlı & Sıfır Tekrarlı 5'li Özel Nesine Kupon Portföyü",
        "",
        "**Kayıt Zamanı:** 2026-11-19 07:30 TSİ (Tüm maçlar başlamadan önce)  ",
        "**Global Benchmark:** Tier-1 Pinnacle + Tier-2 Flashscore Global (`bookmakerId=417`) + Sofascore / ESPN L5  ",
        f"**Sert Kurallar:** En az 4 kupon (**{len(coupons)} kupon**), her kupon **>= 20.00 oran**, tekil maç oranları **>= 1.20**, tüm MBS kuralları geçerli, ve **{total_legs} toplam ayağın tamamında 0 adet tekrarlanan `(Maç, Tercih)` ikilisi!**",
        "",
        "> *Kullanıcı kuralı gereği bir kuponda bir maça verilen tercih (`örneğin MS 1` veya `KG Yok`) diğer hiçbir kuponda tekrar edilmemiştir. Aynı maç birden fazla kuponda yer aldığında ise skor senaryosuyla uyumlu farklı bir market (`2.5 Üst`, `KG Var`, `1.5 Üst` veya `KG Yok`) seçilmiştir.*",
        "",
        "---",
        "",
    ]

    for c in coupons:
        md_lines.extend([
            f"## {c['title']}",
            f"- **Kademe:** {c['tier']} | **Bütçe Payı:** {c['recommended_stake_pct']}",
            f"- **Toplam Nesine Oranı:** **`{c['total_odds']:.2f}x`** | **Maç Sayısı:** {c['leg_count']} (Maks MBS: {c['max_mbs']}) | **Ort. Global Olasılık:** **`%{c['average_leg_probability']*100:.1f}`** | **Birleşik Olasılık:** `%{c['joint_probability']*100:.2f}` | **Ort. EV:** `{c['average_nesine_ev']*100:+.1f}%`",
            f"- **Strateji:** {c['system_note']}",
            "",
            "| # | Saat | Maç | Lig | MBS | Tercih | Nesine | Global Adil | Global % | EV | Not & xG |",
            "| :---: | :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ])
        for l in c["legs"]:
            md_lines.append(
                f"| {l['idx']} | {l['ko_tsi']} | {l['home']} - {l['away']} | {l['league']} | {l['mbs']} | "
                f"**{l['selection']}** | **{l['odds']:.2f}** | {l['fair_odds']:.2f} | %{l['prob']*100:.1f} | {l['nesine_ev']*100:+.1f}% | {l['note']} (`{l['xg_summary']}`) |"
            )
        md_lines.append("")

    md_text = "\n".join(md_lines)
    ledger_md = REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_19_20x_set.md"
    ledger_md.write_text(md_text, encoding="utf-8")

    ledger_json = REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_19_20x_set.json"
    ledger_json.write_text(
        json.dumps(
            {
                "date": "2026-11-19",
                "engine_version": "QuantFoot-v6.1 (Global Benchmark — Disjoint 20x+ Set)",
                "constraints": {
                    "min_coupons": 4,
                    "actual_coupons": len(coupons),
                    "min_coupon_odds": 20.0,
                    "min_leg_odds": 1.2,
                    "zero_duplicate_match_selection": True,
                    "total_unique_legs": total_legs,
                },
                "coupons": coupons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    artifact_md = Path(
        r"C:\Users\pc\.gemini\antigravity\brain\fd718395-2b56-447a-8788-984e92dfbffb\nov19_20x_disjoint_coupons_2026_11_19.md"
    )
    artifact_md.write_text(md_text, encoding="utf-8")

    index_path = REPO_ROOT / "reports" / "ledger" / "INDEX.md"
    if index_path.exists():
        idx_lines = [ln for ln in index_path.read_text(encoding="utf-8").splitlines() if "Disjoint 20x+ Set" not in ln]
        idx_lines.append(
            "| **2026-11-19 (20x+ Set)** | `QuantFoot-v6.1 (Disjoint 20x+ Set)` | 33 Benzersiz Maç | "
            "[coupons_2026_11_19_20x_set.md](coupons_2026_11_19_20x_set.md) / [coupons_2026_11_19_20x_set.json](coupons_2026_11_19_20x_set.json) | "
            "`5 Kupon (>=20x, 0 Tekrar, 49 Ayak) - BEKLİYOR` |"
        )
        index_path.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")

    print(f"VERIFIED: Built {len(coupons)} completely disjoint coupons ({total_legs} unique (match, selection) pairs, 0 duplicates).")
    for c in coupons:
        print(
            f"- {c['title']} => {c['total_odds']:.2f}x | {c['leg_count']} maç (MBS<={c['max_mbs']}) | "
            f"Ort P=%{c['average_leg_probability']*100:.1f} | Birleşik P=%{c['joint_probability']*100:.2f} | Ort EV={c['average_nesine_ev']*100:+.1f}%"
        )


if __name__ == "__main__":
    main()
