"""Birim testleri: Nesine 777/779 skor çevirisi, lig yarı kapsamı, yüksek oranlı 1X2, 1/2-2/1 ve 6 altın skor."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.data.nesine import load_market_definitions, parse_bulletin, translate  # noqa: E402
from quantfoot.data.oddsmath import parse_oddsmath_1x2_payload  # noqa: E402
from quantfoot.markets.extreme_goals import score_both_halves_btts_match  # noqa: E402
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402
from quantfoot.markets.high_odds_analyzer import (  # noqa: E402
    analyze_balanced_1x2,
    rank_golden_scores_with_ev,
    score_comeback_reversals,
)
from quantfoot.markets.league_halves import league_comeback_rates, league_first_half_share  # noqa: E402
from quantfoot.markets.market_diagnosis import rank_macro_coherent_scores  # noqa: E402


def test_nesine_mtid_777_and_779_score_translation_and_pricing():
    defs = load_market_definitions()
    assert translate(777, 1, 0.0, defs, outcome_name="1:0") == ("Skor 1-0", False)
    assert translate(777, 3, 0.0, defs, outcome_name="2:1") == ("Skor 2-1", False)
    assert translate(777, 29, 0.0, defs, outcome_name="Diğer") is None
    assert translate(779, 1, 0.0, defs, outcome_name="0:0") == ("İY Skor 0-0", False)
    assert translate(779, 4, 0.0, defs, outcome_name="1:0") == ("İY Skor 1-0", False)

    ts = int(dt.datetime(2026, 11, 27, 20, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    payload = {
        "sg": {
            "EA": [
                {
                    "C": 999,
                    "HN": "Ev",
                    "AN": "Dep",
                    "TYPE": 1,
                    "ESD": ts,
                    "LC": 1,
                    "MA": [
                        {"MTID": 777, "MS": 1, "SOV": 0.0, "OCA": [{"N": 1, "ON": "1:0", "O": 6.5}, {"N": 29, "ON": "Diğer", "O": 22.0}]},
                        {"MTID": 779, "MS": 1, "SOV": 0.0, "OCA": [{"N": 1, "ON": "0:0", "O": 2.4}]},
                    ],
                }
            ],
            "LA": [{"LID": 1, "N": "Test"}],
        }
    }
    ev = parse_bulletin(payload, defs=defs)[0]
    assert ev.odds_of("Skor 1-0") == 6.5
    assert ev.odds_of("İY Skor 0-0") == 2.4

    joint = np.ones((4, 4, 4, 4)) / 256.0
    assert goal_probability("Skor 1-0", joint) > 0
    assert goal_probability("İY Skor 0-0", joint) > 0


def test_league_halves_expanded_coverage_and_comeback_rates():
    for lg in ("Tayland Şampiyonası", "Suudi Arabistan 1. Lig", "İspanya Segunda RFEF", "Arjantin Primera Lig", "İngiltere Premier Lig"):
        assert league_first_half_share(lg) is not None, f"Eşleşmedi: {lg}"
    cb = league_comeback_rates("İngiltere Premier Lig")
    assert cb is not None
    assert 0.0 < cb["iyms_1/2"] < 0.10
    assert 0.0 < cb["iyms_2/1"] < 0.10
    assert 0.0 < cb["kg_iki_yari"] < 0.20


def test_oddsmath_computes_consensus_gap():
    payload = {
        "schema": ["1", "X", "2"],
        "data": {
            "BetInAsia": {"live": {"1": 2.20, "X": 3.30, "2": 3.40}, "first": {"1": 2.35, "X": 3.30, "2": 3.10}},
            "Marathonbet": {"live": {"1": 2.45, "X": 3.20, "2": 2.95}},
            "Bet365": {"live": {"1": 2.40, "X": 3.25, "2": 3.00}},
        },
    }
    res = parse_oddsmath_1x2_payload(payload)
    assert res["consensus_gap"] is not None and res["consensus_gap"] > 0.01
    assert res["steam_1x2"] is not None and res["steam_1x2"][0] > 0.01


def test_balanced_1x2_analyzer_signals_and_pas():
    # Düşük skorlu dengeli maç -> Beraberlik pozitif kaymalı; steam Ev'e gelirse Ev öne çıkmalı
    m_draw = {
        "code": 1001,
        "kickoff": "2026-11-27 20:00",
        "league": "İtalya Serie A",
        "home": "Takım A",
        "away": "Takım B",
        "status": "fiyatlandı",
        "price_tier": "keskin",
        "fair_1x2": [0.36, 0.31, 0.33],
        "nesine_ms": [2.25, 3.35, 2.55],
        "mu_home": 1.05,
        "mu_away": 1.00,
        "steam_1x2": [-0.03, 0.03, 0.0],
        "selections": [{"name": "2.5 Üst", "odds": 2.15, "fair_prob": 0.43}],
        "research": {"teams": {"home": {"table": {"rank": 4}}, "away": {"table": {"rank": 12}}}, "flags": []},
    }
    a = analyze_balanced_1x2(m_draw)
    assert a is not None
    assert a.trap_draw_alert is True
    assert a.post_probs[1] > a.market_probs[1]
    assert a.verdict == "MS 0"

    # Düşük güven maç her zaman PAS dönmeli
    m_low = {**m_draw, "status": "düşük güven — global fiyat yok, Nesine oranından (kupona alınmaz)", "price_tier": "dusuk_guven"}
    b = analyze_balanced_1x2(m_low)
    assert b is not None and b.verdict == "PAS (Yazı-Tura)"


def test_comeback_reversals_and_golden_scores_with_live_odds():
    m = {
        "code": 1002,
        "kickoff": "2026-11-27 21:00",
        "league": "İngiltere Premier Lig",
        "home": "Ev Açık",
        "away": "Dep Favori",
        "status": "fiyatlandı",
        "fair_1x2": [0.22, 0.25, 0.53],
        "mu_home": 1.25,
        "mu_away": 2.05,
        "selections": [
            {"name": "İY/MS 1/2", "odds": 24.0, "fair_prob": 0.045},
            {"name": "2.5 Üst", "odds": 1.55, "fair_prob": 0.68},
            {"name": "KG Var", "odds": 1.62, "fair_prob": 0.62},
            {"name": "Skor 1-2", "odds": 8.80, "fair_prob": 0.095},
            {"name": "Skor 0-2", "odds": 9.50, "fair_prob": 0.088},
            {"name": "Skor 1-1", "odds": 7.20, "fair_prob": 0.110},
            {"name": "Skor 0-1", "odds": 8.40, "fair_prob": 0.075},
            {"name": "Skor 2-1", "odds": 13.5, "fair_prob": 0.055},
            {"name": "Skor 2-0", "odds": 19.0, "fair_prob": 0.035},
            {"name": "Skor 0-0", "odds": 15.0, "fair_prob": 0.035},
            {"name": "Skor 2-2", "odds": 14.0, "fair_prob": 0.050},
            {"name": "Skor 1-3", "odds": 16.0, "fair_prob": 0.055},
        ],
    }
    cbs = score_comeback_reversals(m)
    assert any(c.selection == "İY/MS 1/2" for c in cbs)
    c12 = next(c for c in cbs if c.selection == "İY/MS 1/2")
    assert 0.01 < c12.p_calibrated <= 0.095
    assert c12.ev is not None and c12.insurance_leg is not None

    ft_dist = {"1-1": 0.115, "1-2": 0.112, "0-2": 0.095, "0-1": 0.080, "2-1": 0.060}
    ranked = rank_macro_coherent_scores(
        ft_dist, f1x2=m["fair_1x2"], p_o25=0.68, p_btts=0.62, mu_home=1.25, mu_away=2.05,
        market_score_odds={"1-2": 8.8, "0-2": 9.5, "1-1": 7.2, "0-1": 8.4, "2-1": 13.5, "2-0": 19.0, "0-0": 15.0, "2-2": 14.0, "1-3": 16.0},
    )
    assert ranked[0][0] == "1-2"
    gs = rank_golden_scores_with_ev(m, ft_dist, top_n=3)
    assert gs[0].score == "1-2" and gs[0].is_golden and gs[0].nesine_odds == 8.8


def test_both_halves_btts_integrates_league_rate():
    m = {
        "code": 1003,
        "kickoff": "2026-11-27 21:45",
        "league": "Almanya Bundesliga",
        "home": "A",
        "away": "B",
        "mu_home": 1.85,
        "mu_away": 1.60,
        "selections": [{"name": "İki Yarıda KG Var", "market": "İki Yarıda KG", "selection": "Evet/Evet", "odds": 10.50, "fair_prob": 0.12}],
    }
    cand = score_both_halves_btts_match(m)
    assert cand is not None
    assert cand.dna_score >= 70.0
    assert any("İki Yarıda KG Var tabanı" in r for r in cand.reasons)
