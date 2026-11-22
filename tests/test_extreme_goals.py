"""Unit tests for extreme-goal (6+ Gol & İki Yarıda KG Var) module and simulation calibration repairs."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from quantfoot.markets.extreme_goals import (
    both_halves_btts_probability,
    scan_extreme_goals,
    score_6plus_match,
    score_both_halves_btts_match,
    tail_6plus_probability,
)
from quantfoot.markets.goal_markets import goal_probability

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tail_and_both_halves_probabilities_are_monotone_and_bounded():
    p6_low = tail_6plus_probability(1.1, 0.9, "İngiltere Premier Lig")
    p6_high = tail_6plus_probability(2.2, 1.8, "İngiltere Premier Lig")
    assert 0.0 < p6_low < p6_high < 0.8

    pk_lopsided = both_halves_btts_probability(2.8, 0.4, "Almanya Bundesliga")
    pk_balanced = both_halves_btts_probability(1.7, 1.6, "Almanya Bundesliga")
    assert 0.0 < pk_lopsided < pk_balanced < 0.5


def test_score_6plus_archetypes_and_safe_ladder():
    shootout = {
        "code": 1001,
        "kickoff": "2026-11-23 19:00",
        "league": "Hollanda Eredivisie",
        "home": "S. Rotterdam",
        "away": "AZ Alkmaar",
        "status": "fiyatlandı",
        "mu_home": 1.35,
        "mu_away": 2.15,
        "selections": [
            {"name": "6+ Gol", "market": "Toplam Gol Aralığı", "selection": "6+ Gol", "odds": 6.20, "fair_prob": 0.14},
            {"name": "2.5 Üst", "market": "2,5 Gol Alt/Üst", "selection": "2,5 Üst", "odds": 1.30, "fair_prob": 0.72},
            {"name": "İY 0.5 Üst", "market": "1. Yarı 0,5 Gol Alt/Üst", "selection": "0,5 Üst", "odds": 1.22, "fair_prob": 0.76},
        ],
    }
    blowout = {
        "code": 1002,
        "kickoff": "2026-11-23 20:00",
        "league": "Belçika 2. Lig",
        "home": "Beerschot",
        "away": "Genk U23",
        "status": "fiyatlandı",
        "mu_home": 2.85,
        "mu_away": 1.05,
        "selections": [
            {"name": "6+ Gol", "market": "Toplam Gol Aralığı", "selection": "6+ Gol", "odds": 4.90, "fair_prob": 0.18},
        ],
    }
    dull = {
        "code": 1003,
        "kickoff": "2026-11-23 21:00",
        "league": "İtalya Serie B",
        "home": "Catania",
        "away": "Bari",
        "status": "fiyatlandı",
        "mu_home": 1.05,
        "mu_away": 0.85,
        "selections": [
            {"name": "6+ Gol", "market": "Toplam Gol Aralığı", "selection": "6+ Gol", "odds": 18.0, "fair_prob": 0.02},
        ],
    }

    c_sh = score_6plus_match(shootout)
    c_bl = score_6plus_match(blowout)
    c_du = score_6plus_match(dull)
    assert c_sh is not None and c_sh.archetype == "düello" and c_sh.dna_score >= 60.0
    assert c_bl is not None and c_bl.archetype == "yıkım" and c_bl.dna_score >= 60.0
    assert c_du is not None and c_du.archetype == "zayıf" and c_du.dna_score < c_sh.dna_score
    assert len(c_sh.safe_ladder) >= 2 and c_sh.safe_ladder[0].fair_prob >= 0.70

    # 1. kaleci eksikliği DNA skorunu yükseltir, iki golcü eksikliği düşürür
    gk_out = {**shootout, "research": {"tm_absences": {"away": {"gk1_out": True}}}}
    sc_out = {**shootout, "research": {"tm_absences": {"home": {"top_scorer_out": True}, "away": {"top_scorer_out": True}}}}
    assert score_6plus_match(gk_out).dna_score > c_sh.dna_score
    assert score_6plus_match(sc_out).dna_score < c_sh.dna_score


def test_score_both_halves_btts_rewards_symmetry_and_penalizes_lopsided_or_slow_1h():
    balanced = {
        "code": 2001,
        "kickoff": "2026-11-23 18:15",
        "league": "İspanya La Liga",
        "home": "Santander",
        "away": "R. Sociedad",
        "status": "fiyatlandı",
        "mu_home": 1.56,
        "mu_away": 2.02,
        "selections": [
            {"name": "İki Yarıda KG Var", "market": "1Y/2Y KG", "selection": "Evet/Evet", "odds": 7.50, "fair_prob": 0.12},
            {"name": "2.5 Üst", "market": "2,5 Gol Alt/Üst", "selection": "2,5 Üst", "odds": 1.24, "fair_prob": 0.72},
        ],
    }
    lopsided = {
        **balanced,
        "code": 2002,
        "mu_home": 2.95,
        "mu_away": 0.65,
    }
    slow_hist = {
        "teams": {
            "home": {"score1H": 0.20, "concede1H": 0.25},
            "away": {"score1H": 0.22, "concede1H": 0.25},
        }
    }
    fast_hist = {
        "teams": {
            "home": {"score1H": 0.65, "concede1H": 0.60},
            "away": {"score1H": 0.58, "concede1H": 0.55},
        }
    }
    c_bal_fast = score_both_halves_btts_match(balanced, fast_hist)
    c_bal_slow = score_both_halves_btts_match(balanced, slow_hist)
    c_lop = score_both_halves_btts_match(lopsided, fast_hist)
    assert c_bal_fast.archetype == "dengeli_tempo"
    assert c_bal_fast.dna_score > c_bal_slow.dna_score + 10.0
    assert c_bal_fast.dna_score > c_lop.dna_score + 20.0

    scanned = scan_extreme_goals([balanced, lopsided], {2001: fast_hist, 2002: fast_hist}, only_offered=True, min_dna_both_btts=50.0)
    assert scanned["both_halves_btts"][0].code == 2001


def test_simulasyon_home_adv_gamma_tempo_and_min_side_guard():
    sim = _load_script("simulasyon")
    # home_adv=True ev sahibine avantaj verir (eşit gf/ga'da bile mh > ma)
    row = {"teams": {"home": {"gf": 1.5, "ga": 1.5, "n": 10}, "away": {"gf": 1.5, "ga": 1.5, "n": 10}}}
    mh_adv, ma_adv, _ = sim.rates(row, {}, None, home_adv=True)
    assert mh_adv > ma_adv

    # kappa > 0 ve away_share_delta < 0: deplasman 1Y gol olasılığı saf simetrik Poisson'dan düşük, 6+ Gol kuyruğu kalın
    j_plain, _ = sim.simulate(1.8, 1.8, 30000, seed=42, share=0.44, kappa=0.0, away_share_delta=0.0)
    j_cal, _ = sim.simulate(1.8, 1.8, 30000, seed=42, share=0.44, kappa=0.06, away_share_delta=-0.025)
    assert goal_probability("Dep İY 0.5 Üst", j_cal) < goal_probability("Dep İY 0.5 Üst", j_plain)
    assert goal_probability("6+ Gol", j_cal) > goal_probability("6+ Gol", j_plain)

    # min_side < 0.45 iken tek taraf maskelemesi üçlü onayı engeller
    v_masked, _ = sim.judge(0.65, 0.66, 0.68, min_side=0.35)
    assert v_masked != "üçlü onay"
    v_ok, _ = sim.judge(0.65, 0.66, 0.68, min_side=0.60)
    assert v_ok == "üçlü onay"
