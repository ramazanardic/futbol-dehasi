"""Comprehensive tests for the 6-segment deep match simulator, 21-family scanner, player props, in-play engine, and signal attribution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.evaluation.signal_attribution import (
    BASELINE_SIGNAL_WEIGHTS,
    SignalPerformance,
    recommend_signal_weights,
    render_attribution_markdown,
    run_causal_signal_attribution,
)
from quantfoot.markets.inplay_engine import (
    InPlayState,
    elapsed_goal_fraction,
    from_fotmob_details,
    reprice_inplay,
)
from quantfoot.markets.match_simulator import (
    MatchSimConfig,
    evaluate_21_families,
    precision_fuse_probabilities,
    render_21_families_markdown,
    simulate_deep_match,
)
from quantfoot.markets.player_props import (
    assess_match_props_and_context,
    predict_team_card_risks,
    predict_team_goalscorers,
    render_player_props_markdown,
)


def test_deep_6_segment_simulator_conserves_means_and_models_1h_2h():
    cfg = MatchSimConfig(
        mu_home=2.15,
        mu_away=1.25,
        home_1h_share=0.50,
        away_1h_share=0.42,
        kappa=0.03,
        home_red_prob=0.08,
        away_red_prob=0.10,
        game_state=True,
    )
    res = simulate_deep_match(cfg, n=15000, seed=1903)
    d = res.diagnostics
    # Expected total goals closely conserved (~3.40)
    assert 3.20 <= d["avg_goals_ft"] <= 3.60
    # High-scoring fast-1H match -> İY 1.5 Üst, Ev 1.5 Üst, MS 1 & 1.5 Üst all substantial
    assert d["p_ht_over15"] >= 0.42
    assert d["p_home_over15"] >= 0.60
    assert d["p_ms1_and_o15"] >= 0.47
    assert 0.10 <= d["red_card_match_prob"] <= 0.25
    assert abs(sum(res.first_goal.values()) - 1.0) < 0.01
    assert len(res.segment_goal_means) == 6
    # Late 75-90+' segment produces more goals than opening 0-15'
    open_g = sum(res.segment_goal_means["0-15'"])
    late_g = sum(res.segment_goal_means["75-90+'"])
    assert late_g > open_g


def test_evaluate_21_families_high_scoring_match_surfaces_iy15_ev15_and_ms1_o15():
    cfg = MatchSimConfig(mu_home=2.25, mu_away=1.25, home_1h_share=0.50, away_1h_share=0.45)
    sim = simulate_deep_match(cfg, n=12000, seed=7)
    match = {
        "home": "Beşiktaş",
        "away": "Antalyaspor",
        "league": "Türkiye Süper Lig",
        "mu_home": 2.25,
        "mu_away": 1.25,
        "selections": [
            {"name": "MS 1", "odds": 1.55, "fair_prob": 0.62, "direct": True},
            {"name": "MS 1 & 1.5 Üst", "odds": 1.82, "fair_prob": 0.56},
            {"name": "İY 1.5 Üst", "odds": 2.25, "fair_prob": 0.46},
            {"name": "Ev 1.5 Üst", "odds": 1.58, "fair_prob": 0.65},
            {"name": "2.5 Üst", "odds": 1.55, "fair_prob": 0.66, "direct": True},
            {"name": "KG Var", "odds": 1.65, "fair_prob": 0.60, "direct": True},
        ],
    }
    rep = evaluate_21_families(match, sim)
    assert rep.families_covered >= 15
    assert rep.match_character == "bol_gollu_hizli_1y"
    smart_names = {x.name for x in rep.smart_attacking_picks}
    assert any(k in smart_names for k in ("Ev 1.5 Üst", "MS 1 & 1.5 Üst", "İY 1.5 Üst"))
    md = "\n".join(render_21_families_markdown(rep, sim))
    assert "İY 1.5 Üst" in md and "Ev 1.5 Üst" in md and "MS 1 & 1.5 Üst" in md


def test_precision_fuse_penalizes_disagreement_and_rewards_consensus():
    p_agree, sd_agree, sc_agree = precision_fuse_probabilities(0.70, 0.71, 0.69, 0.72, direct_market=True)
    p_dis, sd_dis, sc_dis = precision_fuse_probabilities(0.75, 0.45, 0.48, 0.40, direct_market=False)
    assert sd_agree < 0.02
    assert sc_agree >= 90.0
    assert sd_dis > 0.10
    assert sc_dis < 50.0
    assert p_dis < 0.62  # shrunk conservatively when independent models disagree


def test_player_props_goalscorers_cards_and_travel_hangover():
    team_rec = {
        "rest_days": 3.0,
        "last5": ["W 2-1 vs Bayern"],
        "news_flags": ["Champions League clash drains squad ahead of league game"],
        "season": {"goals_for": 28},
        "missing_regulars": [{"name": "Injured Star", "pos": "F"}],
        "profile": {
            "top_scorers": [
                {"name": "Osimhen", "pos": "F", "goals": 11, "assists": 3, "apps": 12, "shots": 42},
                {"name": "Injured Star", "pos": "F", "goals": 8, "assists": 1, "apps": 10, "shots": 25},
                {"name": "Mertens", "pos": "M", "goals": 5, "assists": 7, "apps": 12, "shots": 20},
            ],
            "cards": [
                {"name": "Torreira", "pos": "M", "yellow": 6, "red": 1, "apps": 12},
            ],
        },
        "recent_player_form": {
            "matches": 5,
            "hot_players": [{"name": "Osimhen", "pos": "F", "goals": 4, "assists": 1, "sot": 10}],
        },
    }
    scorers = predict_team_goalscorers("Galatasaray", 1.85, team_rec)
    names = [s.name for s in scorers]
    assert "Osimhen" in names
    assert "Injured Star" not in names  # absent player excluded!
    assert 0.30 <= scorers[0].prob_anytime_goal <= 0.75

    cards_normal = predict_team_card_risks("Galatasaray", team_rec, referee_card_zscore=0.0, derby_card_boost=1.0)
    cards_derby = predict_team_card_risks("Galatasaray", team_rec, referee_card_zscore=1.8, derby_card_boost=1.25)
    assert cards_derby[0].prob_card > cards_normal[0].prob_card

    rec = {
        "home": "Beşiktaş",
        "away": "Trabzonspor",
        "league": "Türkiye Süper Lig",
        "mu_home": 1.65,
        "mu_away": 1.15,
        "research": {"teams": {"home": team_rec, "away": {}}},
    }
    ctx = assess_match_props_and_context(rec)
    assert ctx["travel_distance_km"] is not None and 800.0 <= ctx["travel_distance_km"] <= 1000.0
    assert ctx["hangover_side"] == "home"
    md = "\n".join(render_player_props_markdown(ctx, "Beşiktaş", "Trabzonspor"))
    assert "Osimhen" in md and "Torreira" in md


def test_inplay_engine_red_card_and_live_comeback_detection():
    # Monotonic elapsed goal fraction
    assert 0.0 == elapsed_goal_fraction(0.0)
    assert 0.40 <= elapsed_goal_fraction(45.0) <= 0.48
    assert 1.0 == elapsed_goal_fraction(95.0)

    # Trailing 0-1 at 48' with strong live xG dominance + opponent red card -> massive comeback swing
    base_state = InPlayState(
        minute=48.0, score_home=0, score_away=1, pre_mu_home=1.70, pre_mu_away=1.10,
        live_xg_home=1.45, live_xg_away=0.35, home="Beşiktaş", away="Galatasaray",
    )
    red_state = InPlayState(
        minute=48.0, score_home=0, score_away=1, pre_mu_home=1.70, pre_mu_away=1.10,
        red_home=0, red_away=1, live_xg_home=1.45, live_xg_away=0.35, home="Beşiktaş", away="Galatasaray",
    )
    p_base = reprice_inplay(base_state)
    p_red = reprice_inplay(red_state)
    assert p_red.live_1x2["MS 1"] > p_base.live_1x2["MS 1"] + 0.08
    assert p_red.rem_mu_home > p_base.rem_mu_home
    assert p_red.rem_mu_away < p_base.rem_mu_away
    assert p_red.comeback_alert is not None
    assert abs(sum(p_red.live_1x2.values()) - 1.0) < 0.005

    # FotMob live details adapter
    fm_state = from_fotmob_details(
        {"score": [1, 1], "red": [0, 1], "stats": {"home": {"xg": 1.3, "sot": 5}, "away": {"xg": 0.7, "sot": 2}}},
        minute=62.0, pre_mu_home=1.5, pre_mu_away=1.2,
    )
    assert fm_state.red_away == 1 and fm_state.live_xg_home == 1.3


def test_signal_attribution_causal_and_weight_shrinkage():
    # Synthetic weight recommendation test: good signal boosted, noisy signal damped
    sigs = [
        SignalPerformance("xg_structural", 60, 0.650, 0.640, 0.010, 1.07, 1.05, 0.02, 0.48, "KATMA DEĞER"),
        SignalPerformance("finishing_luck", 60, 0.640, 0.652, -0.012, 1.06, 1.08, -0.02, 0.40, "GÜRÜLTÜ — DARALT"),
    ]
    w = recommend_signal_weights(sigs)
    assert w["xg_weight_cap"] > BASELINE_SIGNAL_WEIGHTS["xg_weight_cap"]
    assert w["luck_cap"] < BASELINE_SIGNAL_WEIGHTS["luck_cap"]

    # Live causal attribution on T1 + E0 2026/27 data
    rep = run_causal_signal_attribution(divisions=("T1", "E0"), min_prior_matches=35)
    if rep.evaluated_matches == 0:
        pytest.skip("No 2026/27 CSV rows found")
    assert rep.evaluated_matches >= 20
    assert rep.overall_model_brier > 0
    md = render_attribution_markdown(rep)
    assert "Otomatik Sinyal Katkı Ölçümü" in md


def test_simulasyon_deep_flag_and_mac_dosyasi_combo_families():
    import mac_dosyasi
    import simulasyon

    joint, top = simulasyon.simulate(1.8, 1.2, 4000, seed=99, deep=True)
    assert joint.shape == (9, 9, 9, 9)
    assert abs(float(joint.sum()) - 1.0) < 1e-6
    assert len(top) >= 3

    fams = mac_dosyasi.families("Beşiktaş", "Galatasaray")
    all_names = {sel_name for _, outs in fams for _, sel_name in outs}
    assert "MS 1 & 1.5 Üst" in all_names
    assert "MS 2 & 1.5 Üst" in all_names
    assert "İY 1.5 Üst" in all_names
    assert "Ev 1.5 Üst" in all_names
    assert "ÇŞ 1X & 1.5 Üst" in all_names
