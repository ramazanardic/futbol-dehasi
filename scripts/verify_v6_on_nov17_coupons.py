"""Backtest QuantFoot-v6 on the exact Nov 17, 2026 fixtures from the user's 9 lost Nesine coupons."""

from __future__ import annotations

import sys
sys.path.insert(0, r"C:\Users\pc\.gemini\antigravity\scratch\quant-football-betting\src")

from quantfoot.markets import compute_omni_markets
from quantfoot.strategy import (
    MatchRiskContext,
    audit_match_risks,
    build_target_odds_coupon,
    select_best_valid_bet,
)


def check_hit(sel: str, ht_h: int, ht_a: int, ft_h: int, ft_a: int) -> bool:
    h2_h, h2_a = ft_h - ht_h, ft_a - ht_a
    tot = ft_h + ft_a
    ht_tot = ht_h + ht_a
    h2_tot = h2_h + h2_a
    kg = ft_h >= 1 and ft_a >= 1
    kg1 = ht_h >= 1 and ht_a >= 1
    kg2 = h2_h >= 1 and h2_a >= 1

    mapping = {
        "MS 1": ft_h > ft_a,
        "MS 0": ft_h == ft_a,
        "MS 2": ft_a > ft_h,
        "ÇŞ 10": ft_h >= ft_a,
        "ÇŞ 02": ft_a >= ft_h,
        "ÇŞ 12": ft_h != ft_a,
        "1.5 Üst": tot >= 2,
        "1.5 Alt": tot <= 1,
        "2.5 Üst": tot >= 3,
        "2.5 Alt": tot <= 2,
        "3.5 Üst": tot >= 4,
        "3.5 Alt": tot <= 3,
        "4.5 Üst": tot >= 5,
        "4.5 Alt": tot <= 4,
        "5.5 Üst": tot >= 6,
        "5.5 Alt": tot <= 5,
        "İY 0.5 Üst": ht_tot >= 1,
        "İY 1.5 Alt": ht_tot <= 1,
        "İY 1.5 Üst": ht_tot >= 2,
        "2Y 0.5 Üst": h2_tot >= 1,
        "2Y 1.5 Alt": h2_tot <= 1,
        "2Y 1.5 Üst": h2_tot >= 2,
        "İY 1": ht_h > ht_a,
        "İY 0": ht_h == ht_a,
        "İY 2": ht_a > ht_h,
        "KG Var": kg,
        "KG Yok": not kg,
        "1. Yarı KG Var": kg1,
        "2. Yarı KG Var": kg2,
        "En Az Bir Devre KG Var": kg1 or kg2,
        "1Y ve 2Y KG Var": kg1 and kg2,
        "0-1 Gol": tot <= 1,
        "2-3 Gol": 2 <= tot <= 3,
        "2-4 Gol": 2 <= tot <= 4,
        "3-5 Gol": 3 <= tot <= 5,
        "4-5 Gol": 4 <= tot <= 5,
        "+6 Gol": tot >= 6,
        "MS 1 & 1.5 Üst": (ft_h > ft_a) and tot >= 2,
        "MS 2 & 1.5 Üst": (ft_a > ft_h) and tot >= 2,
        "MS 1 & 2.5 Üst": (ft_h > ft_a) and tot >= 3,
        "MS 2 & 2.5 Üst": (ft_a > ft_h) and tot >= 3,
        "2.5 Alt & KG Yok": (tot <= 2) and (not kg),
        "2.5 Üst & KG Var": (tot >= 3) and kg,
    }
    return mapping.get(sel, False)


FIXTURES = [
    # (id, home, away, league, mu_h, mu_a, ht_h, ht_a, ft_h, ft_a, old_pick, old_odds, odds_map, ctx, mode)
    (
        "UNL_IRE_KOS", "İrlanda", "Kosova", "uefa.nations",
        1.62, 0.48, 1, 0, 3, 0,
        "2.5 Alt / İY 0", 1.39,
        {"2.5 Alt": 1.39, "İY 0": 1.80, "KG Yok": 1.52, "MS 1": 1.62, "MS 1 & 1.5 Üst": 1.95, "ÇŞ 10": 1.16},
        MatchRiskContext(home_must_win=True, away_dead_attack=True, group_id="UNL_IRE", notes="Kosova 5 maçta 3 gol; İrlanda mutlak kazanmalı"),
        None,
    ),
    (
        "CON_DOM_CAY", "Dominika", "Cayman Adaları", "concacaf.nations",
        2.35, 0.35, 2, 0, 5, 0,
        "2.5 Alt", 1.77,
        {"2.5 Alt": 1.77, "KG Yok": 1.48, "MS 1 & 1.5 Üst": 1.42, "2.5 Üst": 1.65, "MS 1": 1.24},
        MatchRiskContext(home_must_win=True, away_dead_attack=True, group_id="CON_DOM", notes="Cayman 4 maçta 0:12 averaj"),
        None,
    ),
    (
        "UNL_WAL_POR", "Galler", "Portekiz", "uefa.nations",
        0.95, 1.98, 1, 2, 2, 3,
        "3.5 Alt", 1.45,
        {"3.5 Alt": 1.45, "MS 2": 1.25, "1.5 Üst": 1.22, "2.5 Üst": 1.68, "MS 2 & 1.5 Üst": 1.48},
        MatchRiskContext(away_must_win=True, group_id="UNL_WAL", notes="Portekiz yüksek geçiş hücumu"),
        None,
    ),
    (
        "UNL_BIH_ROU", "Bosna Hersek", "Romanya", "uefa.nations",
        1.58, 1.22, 1, 0, 2, 1,
        "KG Var / MS 1", 1.42,
        {"KG Var": 1.42, "MS 1": 1.84, "1.5 Üst": 1.26, "2-4 Gol": 1.45},
        MatchRiskContext(home_must_win=True, group_id="UNL_BIH"),
        None,
    ),
    (
        "UNL_DEN_NOR", "Danimarka", "Norveç", "uefa.nations",
        1.92, 1.82, 2, 1, 2, 3,
        "+6 Gol (5.01) / 1Y&2Y KG (6.65)", 5.01,
        {"+6 Gol": 5.01, "1Y ve 2Y KG Var": 6.65, "KG Var": 1.25, "2.5 Üst": 1.22, "3.5 Üst": 2.10, "3-5 Gol": 1.82, "2.5 Üst & KG Var": 1.68},
        MatchRiskContext(home_must_win=True, away_must_win=True, group_id="UNL_DEN", notes="İskandinav derbisi 4-5 gol bandı"),
        "6_plus_goals",
    ),
    (
        "UNL_POL_SWE", "Polonya", "İsveç", "uefa.nations",
        1.32, 1.28, 0, 0, 1, 1,
        "KG Var / 1:1 Skor", 1.32,
        {"KG Var": 1.32, "2-4 Gol": 1.44, "1.5 Üst": 1.24},
        MatchRiskContext(group_id="UNL_POL"),
        None,
    ),
    (
        "UNL_HUN_NIR", "Macaristan", "Kuzey İrlanda", "uefa.nations",
        1.18, 0.72, 1, 0, 1, 1,
        "2.5 Alt (1.41) / İY 0 (1.85)", 1.41,
        {"2.5 Alt": 1.41, "İY 0": 1.85, "İY 1.5 Alt": 1.30, "3.5 Alt": 1.18},
        MatchRiskContext(group_id="UNL_HUN"),
        None,
    ),
    (
        "UNL_UKR_GEO", "Ukrayna", "Gürcistan", "uefa.nations",
        1.22, 0.55, 1, 0, 1, 0,
        "2.5 Alt (1.45) / İY 0 (1.85)", 1.45,
        {"2.5 Alt": 1.45, "İY 0": 1.85, "KG Yok": 1.54, "İY 1.5 Alt": 1.30, "2.5 Alt & KG Yok": 1.82},
        MatchRiskContext(away_dead_attack=True, group_id="UNL_UKR", notes="Gürcistan 5 maçta 0:4"),
        None,
    ),
    (
        "AFCON_SLE_COD", "Sierra Leone", "D. Kongo Cum.", "caf.nations.qual",
        0.68, 1.42, 0, 1, 1, 1,
        "MS 2 (1.18 - <1.20 TUZAK)", 1.18,
        {"MS 2": 1.18, "2.5 Alt": 1.50, "İY 1.5 Alt": 1.28, "2-3 Gol": 1.85},
        MatchRiskContext(away_complacent=True, group_id="AFCON_SLE", notes="Kongo DC lider, 1.18 oran + beraberlik rehaveti"),
        None,
    ),
    (
        "AFCON_MWI_EGY", "Malavi", "Mısır", "caf.nations.qual",
        0.48, 1.22, 0, 0, 0, 0,
        "MS 2 & KG Yok (1.33)", 1.33,
        {"MS 2 & KG Yok": 1.33, "MS 2": 1.25, "KG Yok": 1.42, "2.5 Alt": 1.48, "2.5 Alt & KG Yok": 1.72},
        MatchRiskContext(away_complacent=True, home_dead_attack=True, group_id="AFCON_MWI", notes="Mısır gruptan çıktı, deplasmanda 0-0 kilit"),
        None,
    ),
    (
        "AFCON_TZA_NGA", "Tanzanya", "Nijerya", "caf.nations.qual",
        0.52, 1.18, 0, 0, 0, 0,
        "2.5 Alt & KG Yok (1.70)", 1.70,
        {"2.5 Alt & KG Yok": 1.70, "2.5 Alt": 1.44, "KG Yok": 1.46},
        MatchRiskContext(away_complacent=True, home_dead_attack=True, group_id="AFCON_TZA"),
        None,
    ),
    (
        "AFCON_MTN_BFA", "Moritanya", "Burkina Faso", "caf.nations.qual",
        0.88, 1.55, 0, 2, 1, 3,
        "2.5 Alt (1.22) / İY 0 (1.62)", 1.22,
        {"2.5 Alt": 1.22, "İY 0": 1.62, "ÇŞ 02": 1.22, "1.5 Üst": 1.42, "2-4 Gol": 1.58},
        MatchRiskContext(away_must_win=True, group_id="AFCON_MTN", notes="Burkina Faso hücum gücü yüksek"),
        None,
    ),
    (
        "EFL_LUT_PET", "Luton Town", "Peterborough", "eng.trophy",
        2.15, 0.52, 2, 0, 3, 0,
        "+6 Gol (4.21)", 4.21,
        {"+6 Gol": 4.21, "MS 1": 1.55, "2.5 Üst": 1.48, "MS 1 & 1.5 Üst": 1.72, "3-5 Gol": 1.85},
        MatchRiskContext(away_dead_attack=True, group_id="EFL_LUT", notes="Peterborough son 5 maçta 2:14"),
        "6_plus_goals",
    ),
    (
        "CON_SKN_BON", "St. Kitts ve Nevis", "Bonaire", "concacaf.nations",
        2.25, 1.55, 1, 2, 3, 2,
        "+6 Gol (3.94) / 1Y&2Y KG (5.27)", 3.94,
        {"+6 Gol": 3.94, "1Y ve 2Y KG Var": 5.27, "2.5 Üst": 1.38, "3.5 Üst": 1.92, "3-5 Gol": 1.80, "KG Var": 1.46},
        MatchRiskContext(group_id="CON_SKN", notes="4-5 gol bandı (xG=3.80 < 5.35)"),
        "6_plus_goals",
    ),
    (
        "U21_SWF_HUL", "S. Wednesday U21", "Hull City U21", "eng.u21",
        1.85, 2.15, 0, 1, 2, 4,
        "1. Yarı KG Var (2.39) / 3.5 Üst (1.54)", 2.39,
        {"1. Yarı KG Var": 2.39, "3.5 Üst": 1.54, "2.5 Üst": 1.25, "KG Var": 1.32, "2. Yarı KG Var": 1.72},
        MatchRiskContext(group_id="U21_SWF", notes="U21 gollerinin %58'i 2. yarıda"),
        "both_halves_btts",
    ),
    (
        "U21_BAR_WIG", "Barnsley U21", "Wigan Ath U21", "eng.u21",
        1.90, 2.20, 0, 1, 2, 4,
        "1. Yarı KG Var (2.09) / 4.5 Üst (1.84)", 2.09,
        {"1. Yarı KG Var": 2.09, "4.5 Üst": 1.84, "3.5 Üst": 1.48, "KG Var": 1.30, "2. Yarı KG Var": 1.68},
        MatchRiskContext(group_id="U21_BAR", notes="U21 gollerinin %58'i 2. yarıda"),
        "both_halves_btts",
    ),
]


def main() -> None:
    print("=" * 95)
    print("QUANTFOOT-v6 POST-MORTEM DOĞRULAMA: 17 KASIM 2026 KAYBEDEN KUPON TUZAKLARI VS YENİ ALGORİTMA")
    print("=" * 95)

    all_recs = []
    hits = 0
    total = 0

    for mid, h, a, lg, mh, ma, hth, hta, fth, fta, old_p, old_o, omap, ctx, mode in FIXTURES:
        b = compute_omni_markets(mh, ma, league=lg)
        blocked, _ = audit_match_risks(b, ctx)
        recs = select_best_valid_bet(mid, h, a, lg, "17.11", b, offered_odds_map=omap, risk_ctx=ctx, specialty_mode=mode)
        top = recs[0]
        won = check_hit(top.selection, hth, hta, fth, fta)
        hits += int(won)
        total += 1
        all_recs.append(recs)

        status = "KAZANDI (WIN)" if won else "KAYBETTİ"
        step_str = f" [Kademe İndirimi: {top.stepped_down_from}]" if top.stepped_down_from else ""
        print(
            f"- {h} {fth}-{fta} (İY {hth}-{hta}) {a} | Eski: {old_p} -> "
            f"v6 En Geçerli Tahmin: {top.selection} @ {top.offered_odds:.2f} "
            f"(P=%{top.probability*100:.1f}) -> {status}{step_str}"
        )

    print("-" * 95)
    print(f"TOPLAM EN GEÇERLİ TAHMİN İSABETİ: {hits} / {total} (%{hits/total*100:.1f})")
    print("-" * 95)

    for target in (10.0, 20.0, 30.0):
        plan = build_target_odds_coupon(all_recs, target_odds=target, max_legs=8)
        leg_hits = [
            check_hit(
                leg.selection,
                next(x[6] for x in FIXTURES if x[0] == leg.match_id),
                next(x[7] for x in FIXTURES if x[0] == leg.match_id),
                next(x[8] for x in FIXTURES if x[0] == leg.match_id),
                next(x[9] for x in FIXTURES if x[0] == leg.match_id),
            )
            for leg in plan.legs
        ]
        all_won = all(leg_hits)
        print(
            f"\n[{plan.title}] Toplam Oran: {plan.achieved_odds:.2f} | "
            f"Ayak Sayısı: {len(plan.legs)} | Birleşik Model Olasılığı: %{plan.joint_probability*100:.1f} | "
            f"Gerçekleşen: {'KUPON TUTTU (' + str(sum(leg_hits)) + '/' + str(len(leg_hits)) + ')' if all_won else str(sum(leg_hits)) + '/' + str(len(leg_hits))}"
        )
        for leg, lw in zip(plan.legs, leg_hits):
            print(f"   * {leg.home} - {leg.away}: {leg.selection} @ {leg.offered_odds:.2f} (P=%{leg.probability*100:.1f}) -> {'TUTTU' if lw else 'YATTI'}")


if __name__ == "__main__":
    main()
