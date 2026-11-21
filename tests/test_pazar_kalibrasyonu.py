"""Market calibration (Platt + league offsets), coupon post-mortem helpers and hard-market coupon rule (22 Nov)."""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ market_calibration
def test_platt_recovers_known_miscalibration_and_league_offset():
    from quantfoot.markets.market_calibration import (
        apply_platt_league,
        fit_platt_league,
    )

    rng = np.random.default_rng(0)
    n = 60000
    p = rng.uniform(0.2, 0.8, n)
    lg = np.where(rng.random(n) < 0.5, "A", "B")
    z = np.log(p / (1 - p))
    true = 1 / (1 + np.exp(-(0.1 + 0.8 * z + np.where(lg == "B", 0.3, 0.0))))   # overconfident + league B scores more
    y = (rng.random(n) < true).astype(float)
    par = fit_platt_league(p, y, lg, league_l2=1.0)
    q = apply_platt_league(par, p, lg)
    assert np.mean(np.abs(q - true)) < 0.02
    assert par["league"]["B"][0] - par["league"]["A"][0] > 0.2
    g = fit_platt_league(p, y, lg, league_l2=None)
    assert "league" not in g and 0.7 < g["b"] < 0.9
    # unknown league -> global curve only
    assert abs(apply_platt_league(par, [0.5], ["ZZ"])[0] - 1 / (1 + math.exp(-par["a"]))) < 1e-12


def test_identity_calibrator_and_heavy_shrinkage():
    from quantfoot.markets.market_calibration import (
        apply_platt_league,
        fit_platt_league,
    )

    rng = np.random.default_rng(1)
    p = rng.uniform(0.1, 0.9, 40000)
    y = (rng.random(len(p)) < p).astype(float)
    lg = np.array(["X"] * 39990 + ["tiny"] * 10)
    par = fit_platt_league(p, y, lg, league_l2=200.0)
    assert abs(par["a"]) < 0.05 and abs(par["b"] - 1) < 0.05
    assert abs(par["league"]["tiny"][0]) < 0.05                          # 10 matches cannot move a league curve
    assert np.max(np.abs(apply_platt_league(par, p[:100], lg[:100]) - p[:100])) < 0.03


def test_calibrate_market_probability_complements_and_gates():
    from quantfoot.markets.market_calibration import (
        calibrate_market_probability,
        nesine_league_to_division,
    )

    cal = {"markets": {"2.5 Üst": {"a": 0.2, "b": 1.0}}}
    up = calibrate_market_probability("2.5 Üst", 0.5, "İngiltere Premier Lig", cal)
    assert abs(up - 1 / (1 + math.exp(-0.2))) < 1e-9
    assert abs(calibrate_market_probability("2.5 Alt", 0.5, None, cal) - (1 - up)) < 1e-9   # Alt = complement
    assert calibrate_market_probability("KG Var", 0.55, None, cal) == 0.55                 # no kept calibrator
    assert calibrate_market_probability("2.5 Üst", 0.5, None, None) == 0.5
    assert nesine_league_to_division("İngiltere 1. Lig") == "E2" and nesine_league_to_division("İspanya 2. Lig") == "SP2"
    assert nesine_league_to_division("Almanya Bundesliga 2") == "D2" and nesine_league_to_division("Almanya Bundesliga") == "D1"
    assert nesine_league_to_division("Almanya Bundesliga Günlük Bahisler") is None
    assert nesine_league_to_division("İngiltere Ulusal Lig, Güney") is None


def test_shipped_market_calibration_file_is_consistent():
    """Every shipped curve must come with its walk-forward evidence (report json) — no unverified curve in production."""
    import json

    root = Path(__file__).resolve().parents[1]
    cal_path = root / "data" / "calibration" / "market_calibration.json"
    if not cal_path.exists():
        return
    cal = json.loads(cal_path.read_text(encoding="utf-8"))
    rep = json.loads((root / "reports" / "research" / "pazar_kalibrasyonu.json").read_text(encoding="utf-8"))
    kept = {k for k, v in rep["kalibrasyon_tutuldu"].items() if v}
    fam = root / "reports" / "research" / "bahis_aileleri_kalibrasyon.json"  # 21 Nov bet-family audit (all families)
    if fam.exists():
        kept |= {r["secim"] for r in json.loads(fam.read_text(encoding="utf-8"))["secimler"] if r.get("tutulan")}
    assert set(cal["markets"]) <= kept
    for name, par in cal["markets"].items():
        assert {"a", "b"} <= set(par) and math.isfinite(par["a"]) and 0.5 < par["b"] < 1.5, name


# ------------------------------------------------------------------ coupon post-mortem helpers
def test_canonical_leg_mapping():
    from quantfoot.evaluation.coupon_postmortem import canonical_leg

    assert canonical_leg("Toplam Gol", "2,5 Üst", 1.5).name == "2.5 Üst" and canonical_leg("Toplam Gol", "2,5 Üst").hard
    assert canonical_leg("Toplam Gol", "3,5 Alt").hard is False
    assert canonical_leg("Maç Sonucu", "1", 1.95).family.startswith("MS 1 zayıf") and canonical_leg("Maç Sonucu", "1", 1.4).name == "MS 1"
    assert canonical_leg("İlk Yarı/Maç Sonucu", "2/X").name == "İY/MS 2/0"
    assert canonical_leg("Çifte Şans", "X-2").name == "ÇŞ 02" and canonical_leg("Karşılıklı Gol", "Var").name == "KG Var"
    assert canonical_leg("1.Y Gol", "0,5 Üst").name == "İY 0.5 Üst"
    assert canonical_leg("2,5 Alt/Üst ve KG", "Üst&Var").name == "2.5 Üst & KG Var"
    assert canonical_leg("MS&Toplam Gol(2,5)", "1 & Üst").name == "MS 1 & 2.5 Üst"
    assert canonical_leg("Hnd. MS (0:2)", "1").name == "Hnd(-2) 1"
    assert canonical_leg(None, None, 5.9).family.startswith("Bilinmiyor (oran") and canonical_leg(None, None, 1.5).name is None
    from quantfoot.markets.goal_markets import goal_probability
    from quantfoot.markets.omni_markets import compute_omni_markets
    joint = compute_omni_markets(1.4, 1.1, league="e0").joint
    for mk, sel in (("İlk Yarı/Maç Sonucu", "1/1"), ("Ev. Gol", "1,5 Üst"), ("Dep. 1.Yarı Gol", "0,5 Üst"),
                    ("Ev. İki Yarı da Gol", "Atar"), ("Hnd. MS (0:2)", "1"), ("MS&Toplam Gol(2,5)", "1 & Üst")):
        assert 0 < goal_probability(canonical_leg(mk, sel).name, joint) < 1     # every mapped name is priceable


def test_postmortem_number_helpers():
    from quantfoot.evaluation.coupon_postmortem import (
        binom_two_sided_p,
        implied_prob,
        legs_bucket,
        odds_band,
        parse_tl,
    )

    assert parse_tl("1.010,09 TL") == 1010.09 and parse_tl("5,72") == 5.72 and parse_tl(None) == 0.0 and parse_tl(float("nan")) == 0.0
    assert odds_band(1.19) == "<1.20" and odds_band(1.70) == "1.70–2.29" and odds_band(4.0) == "≥4.00"
    assert legs_bucket(2) == "1–2" and legs_bucket(7) == "7–8" and legs_bucket(12) == "9+"
    assert abs(implied_prob(2.0, 0.10) - 0.5 / 1.1) < 1e-12
    assert binom_two_sided_p(5, 10, 0.5) == 1.0 and binom_two_sided_p(0, 10, 0.5) < 0.01


def test_postmortem_live_and_refund_rules(tmp_path, monkeypatch):
    pm = _load("kupon_postmortem")
    csv_txt = ("coupon_id,placed,stake_TL,total_odds,win_TL,status,legs_count,match,league,market,selection,leg_odds,leg_result,time_state,score\n"
               "1,20 Kasım 2026 11:00,100,\"3,00\",,Kaybetti,2,A - B,,Toplam Gol,\"2,5 Üst\",1.5,lost,MS,1-0\n"
               "1,20 Kasım 2026 11:00,100,\"3,00\",,Kaybetti,2,C - D,,Maç Sonucu,1,2.0,won,MS,2-0\n"
               "4605462726493704,15 Kasım 2026 10:35,247,\"11,00\",\"5,76 TL\",Kazandı,2,E - F,,Maç Sonucu,1,1.00,void/unknown,MS,0-0\n"
               "4605462726493704,15 Kasım 2026 10:35,247,\"11,00\",\"5,76 TL\",Kazandı,2,G - H,,Maç Sonucu,1,11.0,lost,MS,0-1\n")
    (tmp_path / "nesine_kupon_gecmisi.csv").write_text(csv_txt, encoding="utf-8-sig")
    rows = pm.load_detail(tmp_path)
    assert rows[2]["leg_result"] == "void"                                    # 1.00 odds leg = void, not a win
    cs = {c["coupon_id"]: c for c in pm.coupons_from_detail(rows)}
    assert cs["4605462726493704"]["status"] == "Kısmi iade" and cs["1"]["lost_legs"] == 1
    assert pm.total_odds_band(4.0) == "3–5" and pm.total_odds_band(60) == "≥50"


# ------------------------------------------------------------------ hard-market coupon rule
def _match(sel_name, odds, p, league="İngiltere Premier Lig"):
    import datetime as dt
    ko = (dt.datetime.now(dt.timezone(dt.timedelta(hours=3))) + dt.timedelta(hours=5)).isoformat()
    return {"status": "fiyatlandı", "reference": "Matchbook + Smarkets (borsa)", "research": {}, "league": league, "code": 1,
            "kickoff": ko[:16].replace("T", " "), "kickoff_iso": ko, "home": "A", "away": "B", "ref_fetched_utc": None,
            "selections": [{"name": sel_name, "market": "M", "selection": sel_name, "odds": odds, "fair_prob": p,
                            "ev": round(p * odds - 1, 4), "mbs": 1, "direct": True, "key": "k"}]}


def test_hard_markets_need_a_real_margin_but_are_not_banned():
    import datetime as dt
    nk = _load("nesine_kupon")
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=3)))
    assert nk.is_hard_market("2.5 Üst", 1.6) and nk.is_hard_market("KG Var", 1.7) and nk.is_hard_market("MS 1", 1.95)
    assert not nk.is_hard_market("MS 1", 1.45) and not nk.is_hard_market("2.5 Alt", 1.8) and nk.is_hard_market("İY/MS 1/1", 3.0)
    kw = dict(now=now, min_odds=1.2, min_prob=0.55, allow_espn=False, calibration={}, market_calibration=None)
    thin = nk.candidates([_match("2.5 Üst", 1.70, 0.60)], **kw)            # EV +0.02 < +0.03 -> not taken
    fat = nk.candidates([_match("2.5 Üst", 1.75, 0.60)], **kw)             # EV +0.05 -> taken, with wider sigma
    plain = nk.candidates([_match("2.5 Alt", 1.70, 0.60)], **kw)           # not a hard market: unchanged rule
    assert thin == [] and len(fat) == 1 and fat[0][0]["hard"] and len(plain) == 1 and not plain[0][0]["hard"]
    assert fat[0][0]["sigma"] > plain[0][0]["sigma"]


def test_market_calibration_skips_direct_quotes_and_live_cal_is_gated(tmp_path):
    import json

    from quantfoot.evaluation.auto_learn import load_live_calibration
    from quantfoot.markets.market_calibration import calibrate_market_probability

    cal = {"markets": {"KG Var": {"a": 0.07, "b": 0.88, "direct_in_production": False}}}
    assert calibrate_market_probability("KG Var", 0.45, None, cal, direct=True) == 0.45      # exchange quote: untouched
    assert calibrate_market_probability("KG Var", 0.45, None, cal) > 0.45                   # derived: BTTS was under-predicted
    assert calibrate_market_probability("KG Yok", 0.55, None, cal) < 0.55
    p = tmp_path / "live.json"
    p.write_text(json.dumps({"total_matches_settled": 60, "adjustments": {"prob_shift": {"model|0.5-0.6": -0.02},
                                                                           "source_sigma_delta": {"X": 0.01}}}), encoding="utf-8")
    small = load_live_calibration(p)
    assert small["adjustments"]["prob_shift"] == {} and small["adjustments"]["source_sigma_delta"] == {}
    assert "neutralized_reason" in small
    assert load_live_calibration(p, min_matches=50)["adjustments"]["prob_shift"] == {"model|0.5-0.6": -0.02}


def test_taper_off_and_untested_regimes_reverted():
    from quantfoot.markets import tail_goals

    assert tail_goals.HIGH_TOTAL_RHO_TAPER is False and tail_goals.BTTS_FIT_WEIGHT == 2.0
    assert tail_goals.league_tail_regime("uae.1") == tail_goals.CLUB_REGIME
    assert tail_goals.league_tail_regime("egy.1") == tail_goals.CLUB_REGIME
