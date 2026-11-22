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
    assert not dec_good.ok and any("ailesi yasak" in r for r in dec_good.reasons)

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
    assert not CR.leg_decision(good_no).ok

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
    assert not CR.leg_decision(dep25_alt).ok

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
    assert not CR.leg_decision(ev25_alt).ok

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
    assert not CR.leg_decision(dep05_ust).ok

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
    assert not CR.leg_decision(dep_iy_good).ok

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
    assert not CR.leg_decision(cs12).ok

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
    assert not CR.leg_decision(hnd1).ok

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
    assert not CR.leg_decision(fg_good).ok

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


def test_kupon_kontrol_does_not_crash_on_missing_day_dir(tmp_path, monkeypatch):
    import datetime as dt
    kc = _load_script("kupon_kontrol")
    monkeypatch.setattr(kc, "AREA", tmp_path)
    monkeypatch.setattr(kc, "DAILY", tmp_path)
    rows, clv = kc.check("2026-11-22", dt.datetime(2026, 11, 22, 13, 0, tzinfo=kc.TSI), live={})
    assert rows == [] and clv == {}
    assert not (tmp_path / "2026-11-22").exists()


def test_gunluk_tahmin_audit_keeps_banned_families_out_and_catches_traps(tmp_path, monkeypatch):
    import csv
    import json
    gt = _load_script("gunluk_tahmin")
    monkeypatch.setattr(gt, "ROOT", tmp_path)
    day = tmp_path / "tahminler" / "antigravitytahmin" / "2026-11-22"
    day.mkdir(parents=True)
    matches = [
        {"code": 1, "mu_home": 1.48, "mu_away": 1.32, "fair_1x2": [0.40, 0.27, 0.33], "reference": "Pinnacle",
         "league": "Almanya Bundesliga", "selections": [{"name": "KG Var", "direct": True, "fair_prob": 0.74}]},
        {"code": 2, "mu_home": 1.45, "mu_away": 0.90, "fair_1x2": [0.50, 0.27, 0.23], "reference": "Pinnacle",
         "league": "İspanya La Liga", "selections": [{"name": "Dep 2.5 Alt", "direct": False, "fair_prob": 0.75}]},
        {"code": 3, "mu_home": 1.15, "mu_away": 0.80, "fair_1x2": [0.46, 0.30, 0.24], "reference": "Pinnacle",
         "league": "İtalya Serie A", "selections": [{"name": "İY 1.5 Alt", "direct": True, "fair_prob": 0.78}]},
        {"code": 4, "mu_home": 1.65, "mu_away": 1.25, "fair_1x2": [0.48, 0.21, 0.31], "reference": "Pinnacle",
         "league": "İngiltere Premier Lig", "selections": [{"name": "ÇŞ 12", "direct": True, "fair_prob": 0.76}]},
        {"code": 5, "mu_home": 1.30, "mu_away": 1.00, "fair_1x2": [0.45, 0.28, 0.27], "reference": "Pinnacle",
         "league": "Fransa Ligue 1", "selections": [{"name": "3.5 Alt", "direct": True, "fair_prob": 0.75}]},
    ]
    (day / "nesine_global.json").write_text(json.dumps({"matches": matches}), encoding="utf-8")
    rows = [
        {"kupon": "kupon_2.5x_1200", "kupon_no": "1", "mac": f"M{i}", "nesine_kodu": str(i),
         "secim_adi": nm, "secim": nm, "nesine_oran": "1.30", "olasilik": "0.75", "kural_oncesi_olasilik": "0.75"}
        for i, nm in [(1, "KG Var"), (2, "Dep 2.5 Alt"), (3, "İY 1.5 Alt"), (4, "ÇŞ 12"), (5, "3.5 Alt")]
    ]
    with (day / "kuponlar.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    audit = gt.run_audit("2026-11-22", "antigravitytahmin")
    assert not audit["ok"]
    assert sum("ailesi yasak" in reason for reason in audit["coupons"][0]["ihlaller"]) == 3

    # As kaleci eksik 3.5 Alt tuzağı run_audit tarafından yakalanır
    matches[4]["research"] = {"tm_absences": {"home": {"gk1_out": True}}}
    (day / "nesine_global.json").write_text(json.dumps({"matches": matches}), encoding="utf-8")
    audit_bad = gt.run_audit("2026-11-22", "antigravitytahmin")
    assert not audit_bad["ok"]
    assert any("kaleci" in x for x in audit_bad["coupons"][0]["ihlaller"])


def test_dep_iy_05_ust_never_falls_into_fulltime_team_goals_branch():
    # 22 Kas kritik bug: "Dep İY 0.5 Üst" önceden endswith("0.5 Üst") ile tam-maç dalına düşüp
    # team_mu=1.40 iken rehabilite ediliyordu (sahada 9/24 = %37.5, -21.5p, kuponlarda 0/4!).
    ctx = {
        "name": "Dep İY 0.5 Üst",
        "p": 0.65,
        "odds": 1.55,
        "mu_home": 1.25,
        "mu_away": 1.45,
        "reference": "Pinnacle",
        "direct": False,
        "league": "İngiltere U21",
    }
    diag = diagnose_selection("Dep İY 0.5 Üst", 0.65, ctx, for_coupon=True)
    assert not diag.ok and not diag.rehabilitated
    assert diag.residual_adjustment <= -0.08
    assert not CR.leg_decision(ctx).ok


def test_parity_noise_and_strong_home_not_both_halves_traps_caught():
    # İY Çift: 22 Kas'ta 26/58 (%44.8 vs %56.4 = -11.6p) — parite gürültüsü reddedilir
    parity_ctx = {
        "name": "İY Çift",
        "p": 0.62,
        "odds": 1.40,
        "mu_home": 1.20,
        "mu_away": 1.10,
        "reference": "Pinnacle",
        "direct": False,
    }
    d_par = diagnose_selection("İY Çift", 0.62, parity_ctx, for_coupon=False)
    assert not d_par.ok and not d_par.rehabilitated

    # gunluk_analiz.best_pick de İY Çift'i eler
    ga = _load_script("gunluk_analiz")
    m = {
        "status": "fiyatlandı",
        "reference": "Pinnacle",
        "league": "Almanya Bundesliga",
        "mu_home": 1.30,
        "mu_away": 1.10,
        "fair_1x2": [0.45, 0.28, 0.27],
        "selections": [
            {"name": "İY Çift", "market": "1. Yarı Tek/Çift", "selection": "Çift", "fair_prob": 0.72, "odds": 1.40, "ev": 0.008, "direct": False},
            {"name": "3.5 Alt", "market": "3,5 Gol Alt/Üst", "selection": "Alt", "fair_prob": 0.66, "odds": 1.28, "ev": -0.15, "direct": True},
        ],
    }
    pick, _ = ga.best_pick(m)
    assert pick is not None and pick["name"] == "3.5 Alt"

    # DEĞİL(Ev İki Yarıda Gol): güçlü ev sahibinde (mu_h >= 1.75) tuzak yakalanır, düşük xG'de geçer
    strong_home = {
        "name": "DEĞİL(Ev İki Yarıda Gol)",
        "p": 0.74,
        "odds": 1.22,
        "mu_home": 1.95,
        "mu_away": 0.90,
        "reference": "Pinnacle",
        "direct": False,
    }
    assert not diagnose_selection("DEĞİL(Ev İki Yarıda Gol)", 0.74, strong_home, for_coupon=True).ok
    weak_home = {**strong_home, "mu_home": 1.15}
    assert diagnose_selection("DEĞİL(Ev İki Yarıda Gol)", 0.74, weak_home, for_coupon=True).ok


def test_dep_15_over_requires_direct_or_dominant_xg_and_cs1x_blocks_strong_away():
    # Türetilmiş Dep 1.5 Üst mu_a=2.02 iken reddedilir, direct=True veya mu_a>=2.15 iken geçer
    derived_weak = {
        "name": "Dep 1.5 Üst",
        "p": 0.72,
        "odds": 1.30,
        "mu_home": 1.10,
        "mu_away": 2.02,
        "reference": "Pinnacle",
        "direct": False,
        "league": "Belçika Pro Lig",
    }
    assert not diagnose_selection("Dep 1.5 Üst", 0.72, derived_weak, for_coupon=True).ok
    direct_ok = {**derived_weak, "direct": True}
    d_ok = diagnose_selection("Dep 1.5 Üst", 0.72, direct_ok, for_coupon=True)
    assert d_ok.ok and d_ok.rehabilitated

    # ÇŞ 1X güçlü deplasmana karşı reddedilir
    cs1x_bad = {
        "name": "ÇŞ 1X",
        "p": 0.72,
        "odds": 1.28,
        "mu_home": 1.35,
        "mu_away": 1.45,
        "p2": 0.40,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İtalya Serie A",
    }
    assert not diagnose_selection("ÇŞ 1X", 0.72, cs1x_bad, for_coupon=True).ok


def test_v3_ht_dc_12_trap_caught_and_calibration_pattern_applied():
    # 22 Kas 427 maç bulgusu: İY ÇŞ 12 48/99 (%48.5 vs %62.9 = -14.4p) gizli kupon katili
    normal_ctx = {
        "name": "İY ÇŞ 12",
        "p": 0.72,
        "odds": 1.48,
        "mu_home": 1.55,
        "mu_away": 1.20,
        "p_draw": 0.25,
        "reference": "Pinnacle",
        "direct": False,
        "league": "İngiltere Premier Lig",
    }
    diag = diagnose_selection("İY ÇŞ 12", 0.72, normal_ctx, for_coupon=True)
    assert not diag.ok and not diag.rehabilitated
    assert diag.residual_adjustment <= -0.075
    assert any("İY ÇŞ 12" in r for r in diag.reasons)
    assert not CR.leg_decision(normal_ctx).ok

    # Kalibrasyon tablosunda ^İY ÇŞ 12$ paterni genel ^İY ÇŞ paterninden önce eşleşir ve daha düşük P üretir
    p_12 = CR.calibrate_p(0.70, "İY ÇŞ 12")
    p_1x = CR.calibrate_p(0.70, "İY ÇŞ 1X")
    assert p_12 < p_1x - 0.04


def test_v3_strong_steam_shields_ms_and_unders():
    # MS 1: steam yokken geçer, >=6p sert steam varken reddedilir (22 Kas: %43.8 vs %68.6!)
    ms_clean = {
        "name": "MS 1",
        "p": 0.74,
        "odds": 1.35,
        "mu_home": 2.05,
        "mu_away": 0.72,
        "p_draw": 0.19,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İspanya La Liga",
        "flags": [],
    }
    d_clean = diagnose_selection("MS 1", 0.74, ms_clean, for_coupon=True)
    assert d_clean.ok

    ms_steam = {**ms_clean, "flags": ["keskin borsa steam +6.8p"]}
    d_steam = diagnose_selection("MS 1", 0.74, ms_steam, for_coupon=True)
    assert not d_steam.ok and d_steam.residual_adjustment <= -0.075
    assert not CR.leg_decision(ms_steam).ok

    # Virgüllü Türkçe ondalık bayrak da (+6,2p) yakalanır
    ms_comma = {**ms_clean, "flags": ["steam +6,2p"]}
    assert not diagnose_selection("MS 1", 0.74, ms_comma, for_coupon=True).ok

    # İY 1.5 Alt: düşük xG'de temizken geçer, >=5.5p sert steam'de reddedilir (Getafe İY 0-2 dersi)
    iy15_clean = {
        "name": "İY 1.5 Alt",
        "p": 0.75,
        "odds": 1.28,
        "mu_home": 1.15,
        "mu_away": 0.80,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İspanya La Liga",
        "flags": [],
    }
    assert CR.leg_decision(iy15_clean).ok
    iy15_steam = {**iy15_clean, "flags": ["keskin steam +5.8p"]}
    assert not diagnose_selection("İY 1.5 Alt", 0.75, iy15_steam, for_coupon=True).ok
    assert not CR.leg_decision(iy15_steam).ok

    # 3.5 Alt: >=6.5p sert steam'de reddedilir
    u35_steam = {
        "name": "3.5 Alt",
        "p": 0.76,
        "odds": 1.26,
        "mu_home": 1.20,
        "mu_away": 0.90,
        "reference": "Pinnacle",
        "direct": True,
        "steam_pp": 7.1,
    }
    assert not diagnose_selection("3.5 Alt", 0.76, u35_steam, for_coupon=True).ok


def test_v3_not_both_halves_tightened_and_both_halves_kg_yok_rehabilitated():
    # v3: DEĞİL(Ev İki Yarıda Gol) eşiği 1.75 -> 1.60'a daraltıldı (22 Kas: 17/33 = %51.5, -14.9p)
    mid_home = {
        "name": "DEĞİL(Ev İki Yarıda Gol)",
        "p": 0.74,
        "odds": 1.24,
        "mu_home": 1.65,
        "mu_away": 0.95,
        "reference": "Pinnacle",
        "direct": False,
    }
    assert not diagnose_selection("DEĞİL(Ev İki Yarıda Gol)", 0.74, mid_home, for_coupon=True).ok

    # v3: İY KG Yok & 2Y KG Yok düşük toplamlı keskin maçta rehabilite edilir (22 Kas: 19/26 = %73.1, +10.0p)
    kg_yok_ok = {
        "name": "İY KG Yok & 2Y KG Yok",
        "p": 0.74,
        "odds": 1.32,
        "mu_home": 1.25,
        "mu_away": 0.95,
        "reference": "Pinnacle",
        "direct": False,
        "league": "İtalya Serie A",
    }
    d_rehab = diagnose_selection("İY KG Yok & 2Y KG Yok", 0.74, kg_yok_ok, for_coupon=True)
    assert d_rehab.ok and d_rehab.rehabilitated

    # Yüksek toplamlı maçta veya kaleci eksikken reddedilir
    assert not diagnose_selection("İY KG Yok & 2Y KG Yok", 0.74, {**kg_yok_ok, "mu_home": 1.90, "mu_away": 1.30}, for_coupon=True).ok
    assert not diagnose_selection("İY KG Yok & 2Y KG Yok", 0.74, {**kg_yok_ok, "away_gk1_out": True}, for_coupon=True).ok



