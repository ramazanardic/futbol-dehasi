"""Pazar kök-neden teşhis ve rehabilitasyon testleri (market_diagnosis + coupon_rules + derin_arastirma)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from quantfoot.coupons import coupon_rules as CR
from quantfoot.markets.market_diagnosis import diagnose_selection

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_btts_rehabilitated_in_balanced_match_and_blocked_in_lopsided_match():
    # Dengeli çift taraflı hücum maçı (min(mu) >= 1.10, doğrudan keskin fiyat): KG Var rehabilite edilir
    good_ctx = {
        "name": "KG Var",
        "p": 0.74,
        "odds": 1.52,
        "mu_home": 1.48,
        "mu_away": 1.32,
        "reference": "Pinnacle",
        "direct": True,
        "league": "Almanya Bundesliga",
    }
    diag_good = diagnose_selection("KG Var", 0.74, good_ctx, for_coupon=True)
    assert diag_good.ok and diag_good.rehabilitated
    dec_good = CR.leg_decision(good_ctx)
    assert dec_good.ok, dec_good.reasons

    # Tek taraflı maç (min(mu) < 0.90): KG Var tuzağı yakalanır ve reddedilir
    bad_ctx = {
        **good_ctx,
        "mu_home": 2.15,
        "mu_away": 0.65,
    }
    diag_bad = diagnose_selection("KG Var", 0.74, bad_ctx, for_coupon=True)
    assert not diag_bad.ok and not diag_bad.rehabilitated
    assert any("tek taraflı" in r for r in diag_bad.reasons)
    dec_bad = CR.leg_decision(bad_ctx)
    assert not dec_bad.ok


def test_btts_no_rehabilitated_in_low_total_sharp_and_blocked_in_blowout_or_gk_out():
    good_no = {
        "name": "KG Yok",
        "p": 0.74,
        "odds": 1.48,
        "mu_home": 1.50,
        "mu_away": 0.62,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İtalya Serie A",
    }
    diag = diagnose_selection("KG Yok", 0.74, good_no, for_coupon=True)
    assert diag.ok and diag.rehabilitated
    assert CR.leg_decision(good_no).ok

    # Yüksek toplamlı fark maçında teselli golü tuzağı (Vihren 6-1 / GS 2-1 tipi)
    blowout_no = {**good_no, "mu_home": 2.40, "mu_away": 0.70}
    diag_blowout = diagnose_selection("KG Yok", 0.74, blowout_no, for_coupon=True)
    assert not diag_blowout.ok
    assert any("teselli golü" in r for r in diag_blowout.reasons)

    # As kaleci eksikken KG Yok reddedilir
    gk_out_no = {**good_no, "home_gk1_out": True}
    assert not diagnose_selection("KG Yok", 0.74, gk_out_no, for_coupon=True).ok


def test_team_goals_rehabilitate_strong_slices_and_catch_first_half_low_block_trap():
    # Dep 2.5 Alt (%75 isabet, +11.2p), Ev 2.5 Alt (%75 isabet, +11.3p), Dep 0.5 Üst (%70.2 isabet) rehabilite edilir
    dep25_alt = {
        "name": "Dep 2.5 Alt",
        "p": 0.74,
        "odds": 1.32,
        "mu_home": 1.45,
        "mu_away": 0.90,
        "reference": "Pinnacle",
        "direct": False,
        "league": "İspanya La Liga",
    }
    assert CR.leg_decision(dep25_alt).ok

    ev25_alt = {
        "name": "Ev 2.5 Alt",
        "p": 0.74,
        "odds": 1.36,
        "mu_home": 1.28,
        "mu_away": 1.05,
        "reference": "Pinnacle",
        "direct": False,
        "league": "İspanya La Liga",
    }
    assert CR.leg_decision(ev25_alt).ok

    dep05_ust = {
        "name": "Dep 0.5 Üst",
        "p": 0.74,
        "odds": 1.38,
        "mu_home": 1.20,
        "mu_away": 1.42,
        "reference": "Pinnacle",
        "direct": True,
        "league": "Almanya Bundesliga",
    }
    assert CR.leg_decision(dep05_ust).ok

    # Ev İY 0.5 Üst: ilk yarı düşük blok tuzağı (%43.3 isabet, -17.2p) yakalanır
    ev_iy_trap = {
        "name": "Ev İY 0.5 Üst",
        "p": 0.75,
        "odds": 1.45,
        "mu_home": 1.65,
        "mu_away": 0.95,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İngiltere Premier Lig",
    }
    diag_trap = diagnose_selection("Ev İY 0.5 Üst", 0.75, ev_iy_trap, for_coupon=True)
    assert not diag_trap.ok
    assert not CR.leg_decision(ev_iy_trap).ok

    # Dep İY 0.5 Alt: mu_away < 0.90 ve yetişkin keskin ligde (%68.6 isabet) rehabilite edilir,
    # dengeli veya U19 gençlik maçında reddedilir
    dep_iy_good = {
        "name": "Dep İY 0.5 Alt",
        "p": 0.74,
        "odds": 1.35,
        "mu_home": 1.55,
        "mu_away": 0.72,
        "reference": "Pinnacle",
        "direct": False,
        "league": "Fransa Ligue 1",
    }
    assert CR.leg_decision(dep_iy_good).ok

    dep_iy_youth = {**dep_iy_good, "league": "Almanya U19 Gençlik Ligi"}
    assert not CR.leg_decision(dep_iy_youth).ok


def test_hidden_traps_inside_allowed_families_are_caught():
    # İY 1.5 Alt: iki takımın da gol beklentisi yüksek (min_mu >= 1.05) ve Tier-1 dışı ligde (%44.0 isabet, -23p)
    iy15_trap = {
        "name": "İY 1.5 Alt",
        "p": 0.73,
        "odds": 1.42,
        "mu_home": 1.35,
        "mu_away": 1.22,
        "reference": "Pinnacle",
        "direct": False,
        "league": "Hollanda 1. Lig",
    }
    dec_trap = CR.leg_decision(iy15_trap)
    assert not dec_trap.ok
    assert any("İY 1.5 Alt tuzağı" in r for r in dec_trap.reasons)

    # İY 1.5 Alt: düşük tempolu maçta geçer
    iy15_good = {**iy15_trap, "mu_home": 1.15, "mu_away": 0.78}
    assert CR.leg_decision(iy15_good).ok

    # Yarı özel ailesi içindeki gizli tuzak: Ev En Az Bir Yarıyı Kazanır (%48.1, -14.3p) reddedilir
    yari_trap = {
        "name": "Ev En Az Bir Yarıyı Kazanır",
        "p": 0.75,
        "odds": 1.35,
        "mu_home": 1.55,
        "mu_away": 1.05,
        "reference": "Pinnacle",
        "direct": False,
    }
    assert not CR.leg_decision(yari_trap).ok

    # 3.5 Alt: as kaleci eksikken reddedilir
    alt35_gk_out = {
        "name": "3.5 Alt",
        "p": 0.75,
        "odds": 1.32,
        "mu_home": 1.40,
        "mu_away": 1.10,
        "reference": "Pinnacle",
        "home_gk1_out": True,
    }
    dec_gk = CR.leg_decision(alt35_gk_out)
    assert not dec_gk.ok
    assert any("kaleci" in r for r in dec_gk.reasons)


def test_double_chance_handicap_and_first_goal_rehabilitation():
    # ÇŞ 12 (%76.5 isabet @ P>=65% & sharp) düşük beraberlik olasılıklı maçta rehabilite edilir
    cs12 = {
        "name": "ÇŞ 12",
        "p": 0.74,
        "odds": 1.28,
        "mu_home": 1.65,
        "mu_away": 1.25,
        "p_draw": 0.21,
        "reference": "Pinnacle",
        "direct": True,
    }
    assert CR.leg_decision(cs12).ok

    # Hnd(+1) 1 (%75.0 isabet @ P>=65% & sharp) rehabilite edilir
    hnd1 = {
        "name": "Hnd(+1) 1",
        "p": 0.74,
        "odds": 1.34,
        "mu_home": 1.45,
        "mu_away": 1.05,
        "p2": 0.24,
        "reference": "Pinnacle",
        "direct": True,
    }
    assert CR.leg_decision(hnd1).ok

    # İlk Gol Ev: belirgin hücum asimetrisinde (%70.0 isabet) rehabilite edilir, dengeli maçta (%44.0) reddedilir
    fg_good = {
        "name": "İlk Gol Ev",
        "p": 0.74,
        "odds": 1.42,
        "mu_home": 1.95,
        "mu_away": 0.72,
        "p_draw": 0.20,
        "reference": "Pinnacle",
        "direct": True,
    }
    assert CR.leg_decision(fg_good).ok

    fg_balanced = {**fg_good, "mu_home": 1.35, "mu_away": 1.25, "p_draw": 0.27}
    assert not CR.leg_decision(fg_balanced).ok


def test_single_side_history_masking_caught_in_derin_arastirma():
    dr = _load_script("derin_arastirma")
    # Ev sahibi %90 (10 maç), deplasman %40 (10 maç) -> ortalama %65 olsa da tek taraf çöküşü yakalanır!
    hist = {"home_rate": 0.90, "home_n": 10, "away_rate": 0.40, "away_n": 10, "min_side": 0.40, "mean": 0.65}
    v = dr.verdict(0.65, hist)
    assert v.startswith("⚠"), f"Tek taraf çöküşü yakalanmalıydı, dönen: {v}"

    # İki taraf da dengeli (%68 ve %64) -> ✓ geçmiş destekliyor
    hist_ok = {"home_rate": 0.68, "home_n": 10, "away_rate": 0.64, "away_n": 10, "min_side": 0.64, "mean": 0.66}
    assert dr.verdict(0.65, hist_ok).startswith("✓")


def test_gunluk_analiz_best_pick_avoids_diagnosed_trap():
    ga = _load_script("gunluk_analiz")
    match = {
        "status": "fiyatlandı",
        "reference": "Pinnacle",
        "league": "İngiltere Premier Lig",
        "mu_home": 1.55,
        "mu_away": 0.95,
        "fair_1x2": [0.52, 0.26, 0.22],
        "selections": [
            {"name": "Ev İY 0.5 Üst", "market": "Ev Sahibi İY Gol", "selection": "0,5 Üst", "fair_prob": 0.72, "odds": 1.55, "ev": 0.116, "direct": True},
            {"name": "3.5 Alt", "market": "Alt/Üst 3,5", "selection": "Alt", "fair_prob": 0.69, "odds": 1.42, "ev": -0.02, "direct": True},
        ],
    }
    pick, _ = ga.best_pick(match)
    assert pick is not None
    assert pick["name"] == "3.5 Alt"
