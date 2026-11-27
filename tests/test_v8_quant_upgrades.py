"""Comprehensive unit and integration tests for QuantFoot v8 upgrades.

Covers:
  - Kaito Goto closed-form standard-error devigging & multi-method ensemble devigging
  - Exact zero-EV Asian Handicap payoff pricing (whole/half/quarter lines) & minimum-KL AH raking
  - Wiring ref['ah'] into scripts/nesine_global.py (price_event & consensus)
  - Sharp source connectors (The Odds API v4, football-data fixtures.csv, expanded API-Football /odds)
  - Quantitative T-60 lineup shock (bounded ±12%, anti-double-counting rule), exponential NPxG profiles,
    referee profiles, motivation risk assessment, and optional market_diagnosis.py context signals
  - CLV statistical significance, Murphy/Dimitriadis Brier MCB-DSC decomposition, log-opinion-pool
    weight test, and safe James-Stein family calibration proposal
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import nesine_global as ng  # noqa: E402
from quantfoot.data.api_football import parse_api_football_odds  # noqa: E402
from quantfoot.data.nesine import NesineEvent, NesineSelection  # noqa: E402
from quantfoot.data.sharp_sources import (  # noqa: E402
    filter_fresh_references,
    load_football_data_fixtures,
    parse_the_odds_api_events,
    reference_age_hours,
)
from quantfoot.evaluation.clv_ledger import (  # noqa: E402
    record_daily_picks,
    settle_ledger,
    summarize_clv_ledger,
    update_closing_lines,
)
from quantfoot.evaluation.clv_tracker import (  # noqa: E402
    brier_decomposition,
    clv_significance,
    compute_clv,
    corp_reliability_decomposition,
    optimal_log_pool_weight,
    pav_isotonic,
    propose_family_calibration_update,
)
from quantfoot.evaluation.self_improve import _build_diag_ctx  # noqa: E402
from quantfoot.markets import inplay  # noqa: E402
from quantfoot.markets.consensus import (  # noqa: E402
    BookmakerQuote,
    adaptive_kelly_from_consensus,
    check_synthetic_coherence,
    precision_weighted_consensus,
)
from quantfoot.markets.devig import devig, devig_batch  # noqa: E402
from quantfoot.markets.line_movement import (  # noqa: E402
    analyze_line_movement,
    backtest_sharp_soft_and_steam,
    sharp_soft_edge,
)
from quantfoot.markets.lineup_xg import (  # noqa: E402
    assess_motivation_risk,
    build_referee_profiles,
    compute_lineup_shock,
    compute_team_xg_profiles,
)
from quantfoot.markets.market_diagnosis import diagnose_selection  # noqa: E402
from quantfoot.markets.tail_goals import (  # noqa: E402
    fit_tail_rates_from_markets,
    matrix_1x2,
    matrix_ah_home_win_share,
    matrix_ah_outcomes,
    matrix_over_probability,
    negative_binomial_score_matrix,
    rake_score_matrix_to_markets,
)
from quantfoot.strategy.kelly import adaptive_kelly_stake  # noqa: E402


# --------------------------------------------------------------------------- 1. Goto & Ensemble Devigging
def test_goto_conversion_matches_published_reference_vector():
    """Exact verification against Kaito Goto's published [1.2, 3.4, 5.6] benchmark."""
    res = devig([1.2, 3.4, 5.6], method="goto")
    expected = np.array([0.7753528189788175, 0.17479473292721065, 0.04985244809397199])
    assert np.allclose(res.probabilities, expected, atol=1e-10)
    assert np.isclose(res.probabilities.sum(), 1.0, atol=1e-12)
    assert res.method == "goto"
    assert res.parameter is not None and res.parameter > 0.0


def test_goto_corrects_favorite_longshot_bias_and_handles_extreme_longshots():
    odds = [1.08, 12.0, 45.0]
    p_mult = devig(odds, method="multiplicative").probabilities
    p_goto = devig(odds, method="goto").probabilities
    p_ens = devig(odds, method="ensemble").probabilities
    # Goto shifts more vig onto longshots -> favorite higher, longshot lower than multiplicative.
    assert p_goto[0] > p_mult[0]
    assert p_goto[2] < p_mult[2]
    assert np.all(p_goto > 0.0) and np.isclose(p_goto.sum(), 1.0, atol=1e-12)
    assert np.all(p_ens > 0.0) and np.isclose(p_ens.sum(), 1.0, atol=1e-12)


def test_devig_batch_goto_matches_single_calls():
    mat = np.array([[1.2, 3.4, 5.6], [2.1, 3.3, 3.6], [1.05, 14.0, 55.0], [2.0, 2.0, 99.0]])
    batch = devig_batch(mat, method="goto")
    singles = np.vstack([devig(row, method="goto").probabilities for row in mat])
    assert np.allclose(batch, singles, atol=1e-11)


# --------------------------------------------------------------------------- 2. Exact AH Payoff & Raking
def test_matrix_ah_quarter_line_exact_zero_ev():
    """Verify exact zero-EV decimal pricing on -0.25 and -0.75 quarter lines."""
    mat = negative_binomial_score_matrix(1.6, 1.1, alpha_nb=0.0, shared_kappa=0.0, com_nu=1.0)
    out = matrix_ah_outcomes(mat, -0.25)
    assert np.isclose(out["win"] + out["half_win"] + out["push"] + out["half_loss"] + out["loss"], 1.0, atol=1e-12)
    assert out["push"] == 0.0
    assert out["half_win"] == 0.0
    assert out["half_loss"] > 0.0  # draws are half-losses on -0.25

    fair_p = out["fair_home_share"]
    fair_odds = 1.0 / fair_p
    ev = out["win"] * (fair_odds - 1.0) - 0.5 * out["half_loss"] - 1.0 * out["loss"]
    assert ev == pytest.approx(0.0, abs=1e-11)

    out75 = matrix_ah_outcomes(mat, -0.75)
    assert out75["half_win"] > 0.0  # 1-goal home wins are half-wins on -0.75
    fair_odds75 = 1.0 / out75["fair_home_share"]
    ev75 = out75["win"] * (fair_odds75 - 1.0) + 0.5 * out75["half_win"] * (fair_odds75 - 1.0) - out75["loss"]
    assert ev75 == pytest.approx(0.0, abs=1e-11)


def test_rake_score_matrix_hits_1x2_ou_and_ah_simultaneously():
    """Minimum-KL raking must satisfy 1X2, O/U 2.5, AND AH (-1.25 / -1.5) targets simultaneously."""
    p1x2 = [0.68, 0.19, 0.13]
    p_ov25 = 0.62
    target_ah = 0.44  # AH -1.25 home fair share
    _, _, fit_mat = fit_tail_rates_from_markets(
        p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], ah_lines=[(-1.25, target_ah)],
        alpha_nb=0.0, shared_kappa=0.0, com_nu=1.0, fund_weight=0.0,
    )
    raked = rake_score_matrix_to_markets(
        fit_mat, p_1x2=p1x2, ou_lines=[(2.5, p_ov25)], ah_lines=[(-1.25, target_ah)],
    )
    assert np.isclose(raked.sum(), 1.0, atol=1e-10)
    assert np.allclose(matrix_1x2(raked), p1x2, atol=1e-5)
    assert matrix_over_probability(raked, 2.5) == pytest.approx(p_ov25, abs=1e-5)
    assert matrix_ah_home_win_share(raked, -1.25) == pytest.approx(target_ah, abs=1e-5)


def test_nesine_global_price_event_uses_sharp_ah_constraint():
    """Passing a sharper AH -1.5 quote must shift Hnd(-1) 1 probability accordingly in price_event."""
    ko = dt.datetime(2026, 11, 26, 18, 0, tzinfo=dt.timezone.utc)
    sels = [
        NesineSelection(1, "Maç Sonucu", "1", "MS 1", 1.35, mbs=1),
        NesineSelection(1, "Maç Sonucu", "0", "MS 0", 4.80, mbs=1),
        NesineSelection(1, "Maç Sonucu", "2", "MS 2", 8.50, mbs=1),
        NesineSelection(2, "2,5 Alt/Üst", "Üst", "2.5 Üst", 1.65, mbs=1),
        NesineSelection(2, "2,5 Alt/Üst", "Alt", "2.5 Alt", 2.15, mbs=1),
        NesineSelection(3, "Handikaplı Maç Sonucu (-1)", "1", "Hnd(-1) 1", 1.95, mbs=1),
    ]
    ev = NesineEvent(code=999001, kickoff=ko, league_code=1, home="Arsenal", away="Coventry", selections=sels)
    ref_no_ah = {"source": "Pinnacle (football-data)", "x12": [1.35, 5.2, 9.0], "ou": [2.5, [1.65, 2.35]]}
    ref_strong_ah = {**ref_no_ah, "ah": [-1.5, [1.75, 2.25]]}  # market expects high 2+ margin probability
    ref_weak_ah = {**ref_no_ah, "ah": [-1.5, [2.45, 1.62]]}  # market expects low 2+ margin probability

    p_strong = next(s["fair_prob"] for s in ng.price_event(ev, ref_strong_ah, "İngiltere Premier Lig")["selections"] if s["name"] == "Hnd(-1) 1")
    p_weak = next(s["fair_prob"] for s in ng.price_event(ev, ref_weak_ah, "İngiltere Premier Lig")["selections"] if s["name"] == "Hnd(-1) 1")
    assert p_strong > p_weak + 0.10


# --------------------------------------------------------------------------- 3. Sharp Sources & Expanded API-Football
def test_parse_the_odds_api_events_extracts_1x2_totals_and_ah():
    payload = [
        {
            "sport_key": "soccer_epl",
            "sport_title": "EPL",
            "commence_time": "2026-11-26T20:00:00Z",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "last_update": "2026-11-26T17:30:00Z",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Arsenal", "price": 1.80},
                                {"name": "Draw", "price": 3.80},
                                {"name": "Chelsea", "price": 4.50},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "point": 2.5, "price": 1.85},
                                {"name": "Under", "point": 2.5, "price": 2.05},
                                {"name": "Over", "point": 3.5, "price": 2.95},
                                {"name": "Under", "point": 3.5, "price": 1.44},
                            ],
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Arsenal", "point": -0.75, "price": 2.02},
                                {"name": "Chelsea", "point": 0.75, "price": 1.90},
                            ],
                        },
                    ],
                }
            ],
        }
    ]
    refs = parse_the_odds_api_events(payload, fetched_utc="2026-11-26T17:45:00+00:00")
    assert len(refs) == 1
    r = refs[0]
    assert r["source"] == "Pinnacle (TheOddsAPI)"
    assert r["x12"] == [1.8, 3.8, 4.5]
    assert r["ou"] == [2.5, [1.85, 2.05]]
    assert r["ah"] == [-0.75, [2.02, 1.9]]
    assert "Over/Under 3.5" in r["markets"]

    now = dt.datetime(2026, 11, 26, 19, 0, tzinfo=dt.timezone.utc)
    assert reference_age_hours(r, now_utc=now) == pytest.approx(1.25, abs=1e-4)
    assert len(filter_fresh_references(refs, max_age_hours=3.0, now_utc=now)) == 1
    assert len(filter_fresh_references(refs, max_age_hours=1.0, now_utc=now)) == 0


def test_load_football_data_fixtures_parses_real_file():
    fx_path = ROOT / "data" / "global_odds" / "latest" / "fixtures.csv"
    if not fx_path.exists():
        pytest.skip("fixtures.csv not present")
    refs = load_football_data_fixtures(fx_path)
    assert len(refs) > 0
    assert all(len(r["x12"]) == 3 for r in refs)
    assert all(r["source"] in ("Pinnacle (football-data)", "Betfair Borsası (football-data)") for r in refs)


def test_parse_api_football_odds_extracts_derivatives_and_ah():
    fx_by_id = {
        77: {
            "fixture": {"id": 77, "date": "2026-11-26T19:00:00+00:00"},
            "league": {"country": "Turkey", "name": "Super Lig"},
            "teams": {"home": {"name": "Galatasaray"}, "away": {"name": "Trabzonspor"}},
        }
    }
    odds_items = [
        {
            "fixture": {"id": 77},
            "bookmakers": [
                {
                    "name": "Pinnacle",
                    "bets": [
                        {
                            "name": "Match Winner",
                            "values": [
                                {"value": "Home", "odd": "1.60"},
                                {"value": "Draw", "odd": "4.20"},
                                {"value": "Away", "odd": "5.20"},
                            ],
                        },
                        {
                            "name": "Goals Over/Under",
                            "values": [
                                {"value": "Over 2.5", "odd": "1.62"},
                                {"value": "Under 2.5", "odd": "2.35"},
                                {"value": "Over 3.5", "odd": "2.55"},
                                {"value": "Under 3.5", "odd": "1.55"},
                            ],
                        },
                        {
                            "name": "Both Teams Score",
                            "values": [{"value": "Yes", "odd": "1.70"}, {"value": "No", "odd": "2.20"}],
                        },
                        {
                            "name": "Asian Handicap",
                            "values": [
                                {"value": "Home -1.0", "odd": "2.04"},
                                {"value": "Away +1.0", "odd": "1.88"},
                            ],
                        },
                        {
                            "name": "Goals Over/Under First Half",
                            "values": [
                                {"value": "Over 0.5", "odd": "1.30"},
                                {"value": "Under 0.5", "odd": "3.60"},
                            ],
                        },
                    ],
                }
            ],
        }
    ]
    refs = parse_api_football_odds(fx_by_id, odds_items, fetched_utc="2026-11-26T16:00:00+00:00")
    assert len(refs) == 1
    r = refs[0]
    assert r["source"] == "Pinnacle (API-Football)"
    assert r["ah"] == [-1.0, [2.04, 1.88]]
    direct = ng.direct_probabilities(r)
    assert "KG Var" in direct and "3.5 Üst" in direct and "İY 0.5 Üst" in direct


# --------------------------------------------------------------------------- 4. Lineup Shock, NPxG, Referee & Motivation
def test_lineup_shock_anti_double_counting_and_bounds():
    # When news is ALREADY priced in (news_fresher_than_odds=False), mu must stay untouched.
    priced_in = compute_lineup_shock(
        1.80, 1.10, home_gk1_out=True, home_top_scorer_out=True, news_fresher_than_odds=False
    )
    assert priced_in.applied is False
    assert priced_in.mu_home_adj == 1.80
    assert priced_in.mu_away_adj == 1.10
    assert len(priced_in.flags) == 2

    # When T-60 news breaks AFTER sharp snapshot, bounded shift applies cleanly.
    fresh = compute_lineup_shock(
        1.80, 1.10,
        home_gk1_out=True,
        home_top_scorer_out=True,
        home_scorer_goal_share=0.30,
        home_other_starters_out=4,
        news_fresher_than_odds=True,
        max_shift=0.12,
    )
    assert fresh.applied is True
    assert 0.88 <= fresh.home_multiplier <= 1.12
    assert 0.88 <= fresh.away_multiplier <= 1.12
    assert fresh.mu_home_adj < 1.80
    assert fresh.mu_away_adj > 1.10


def test_xg_profiles_referees_motivation_and_diagnosis_signals():
    matches = [
        {"Date": "2026-10-01", "HomeTeam": "Alpha", "AwayTeam": "Beta", "HxG": 2.4, "AxG": 0.7, "FTHG": 3, "FTAG": 0, "Referee": "RefStrict", "HF": 14, "AF": 16, "HY": 4, "AY": 5, "HR": 0, "AR": 1},
        {"Date": "2026-10-15", "HomeTeam": "Beta", "AwayTeam": "Alpha", "HxG": 0.8, "AxG": 2.1, "FTHG": 1, "FTAG": 2, "Referee": "RefStrict", "HF": 15, "AF": 13, "HY": 4, "AY": 4, "HR": 1, "AR": 0},
        {"Date": "2026-11-01", "HomeTeam": "Alpha", "AwayTeam": "Beta", "HxG": 2.2, "AxG": 0.9, "FTHG": 2, "FTAG": 1, "Referee": "RefCalm", "HF": 8, "AF": 9, "HY": 1, "AY": 1, "HR": 0, "AR": 0},
        {"Date": "2026-11-10", "HomeTeam": "Beta", "AwayTeam": "Alpha", "HxG": 0.9, "AxG": 2.0, "FTHG": 0, "FTAG": 2, "Referee": "RefCalm", "HF": 7, "AF": 8, "HY": 1, "AY": 2, "HR": 0, "AR": 0},
    ]
    profs = compute_team_xg_profiles(matches, half_life_days=60.0, shrink_games=4.0)
    assert profs["Alpha"].attack_index > profs["Beta"].attack_index
    assert profs["Alpha"].defense_index < profs["Beta"].defense_index

    refs = build_referee_profiles(matches, min_matches=2)
    assert refs["RefStrict"].cards_per_match > refs["RefCalm"].cards_per_match
    assert refs["RefStrict"].card_zscore > 0.0

    mot = assess_motivation_risk("Orta sıra — hedefsiz", "Garantiledi (hedefsiz)")
    assert mot.dead_rubber is True and mot.regime == "dead_rubber"

    # Optional context signals trigger only when explicitly passed to diagnose_selection.
    base_ctx = {"mu_home": 1.1, "mu_away": 0.9, "sharp": True, "league": "İngiltere Premier Lig"}
    assert diagnose_selection("3.5 Alt", 0.78, base_ctx, for_coupon=True).ok is True
    assert diagnose_selection("3.5 Alt", 0.78, {**base_ctx, "dead_rubber": True}, for_coupon=True).ok is False
    assert diagnose_selection("3.5 Alt", 0.78, {**base_ctx, "referee_card_zscore": 2.4}, for_coupon=True).ok is False


# --------------------------------------------------------------------------- 5. CLV, Brier MCB/DSC, Pool Weight & Calibration
def test_clv_brier_decomposition_pool_weight_and_calibration_proposal():
    assert compute_clv(2.10, closing_fair_prob=0.50) == pytest.approx(0.05, abs=1e-9)
    assert compute_clv(2.10, closing_odds=2.00) == pytest.approx(0.05, abs=1e-9)

    clv_rep = clv_significance([0.03, 0.04, 0.02, 0.05, 0.01, 0.06, 0.025, 0.035] * 10)
    assert clv_rep.mean_clv > 0.03
    assert clv_rep.p_value_one_sided < 0.001
    assert clv_rep.ci_95_low > 0.0

    # Exact Brier identity check on constant-within-bin predictions: brier == mcb - dsc + unc
    y_true = np.array([1, 1, 1, 0, 0, 0, 1, 0, 1, 0], dtype=float)
    y_prob = np.array([0.85, 0.85, 0.85, 0.85, 0.15, 0.15, 0.15, 0.15, 0.55, 0.55], dtype=float)
    dec = brier_decomposition(y_true, y_prob, n_bins=10)
    assert dec.brier == pytest.approx(dec.mcb - dec.dsc + dec.unc, abs=1e-5)
    assert dec.ece >= 0.0

    # Log-opinion-pool weight test: an informative model gets w > 0, a noisy model gets w ≈ 0.
    rng = np.random.default_rng(7)
    n = 300
    true_p = np.column_stack([0.55 * np.ones(n), 0.25 * np.ones(n), 0.20 * np.ones(n)])
    outcomes = np.array([rng.choice(3, p=row) for row in true_p])
    noisy_model = np.column_stack([0.34 * np.ones(n), 0.33 * np.ones(n), 0.33 * np.ones(n)])
    pool_res = optimal_log_pool_weight(noisy_model, true_p, outcomes)
    assert pool_res.optimal_weight < 0.15

    # Safe calibration proposal: negative-only shrinkage & min_n guard.
    settled = (
        [{"secim_adi": "İY 0.5 Üst", "olasilik": 0.78, "tuttu": i < 30} for i in range(50)]  # hit 60% vs 78% -> negative adj
        + [{"secim_adi": "3.5 Alt", "olasilik": 0.72, "tuttu": i < 45} for i in range(50)]  # hit 90% vs 72% -> capped at 0.0
        + [{"secim_adi": "MS 1", "olasilik": 0.75, "tuttu": False} for _ in range(10)]  # n=10 < min_n -> not eligible
    )
    prop = propose_family_calibration_update(settled, prior_n=150.0, min_n=40)
    assert prop["families"]["İlk yarı"]["eligible"] is True
    assert prop["families"]["İlk yarı"]["proposed_adjustment"] < 0.0
    assert prop["families"]["Alt/Üst"]["proposed_adjustment"] == 0.0
    assert prop["families"]["Maç sonucu"]["eligible"] is False
    assert prop["families"]["Maç sonucu"]["proposed_adjustment"] == 0.0


# --------------------------------------------------------------------------- 6. CORP Isotonic Reliability (PAVA)
def test_pav_isotonic_and_corp_exact_brier_identity():
    """Verify O(n) PAVA monotonicity and exact bin-free CORP identity: brier == mcb - dsc + unc."""
    raw = np.array([0.8, 0.2, 0.6, 0.4, 0.9, 0.7])
    iso = pav_isotonic(raw)
    assert np.all(np.diff(iso) >= -1e-12)
    assert np.isclose(np.mean(iso), np.mean(raw), atol=1e-12)

    # Exact identity must hold on arbitrary continuous predictions (with and without ties).
    rng = np.random.default_rng(123)
    probs = np.concatenate([rng.uniform(0.05, 0.95, size=240), np.full(10, 0.50)])
    outcomes = (rng.random(size=probs.size) < np.clip(probs - 0.06, 0.02, 0.98)).astype(float)
    corp = corp_reliability_decomposition(outcomes, probs)
    assert corp.n == 250
    assert corp.brier == pytest.approx(corp.mcb - corp.dsc + corp.unc, abs=1e-5)
    assert corp.mcb >= 0.0 and corp.dsc >= 0.0 and corp.corp_ece >= 0.0
    assert corp.n_isotonic_levels >= 1

    # Perfectly calibrated predictions yield MCB == 0 and CORP_ECE == 0.
    p_perf = np.array([0.25] * 40 + [0.75] * 40)
    y_perf = np.array([1.0] * 10 + [0.0] * 30 + [1.0] * 30 + [0.0] * 10)
    corp_perf = corp_reliability_decomposition(y_perf, p_perf)
    assert corp_perf.mcb == pytest.approx(0.0, abs=1e-6)
    assert corp_perf.corp_ece == pytest.approx(0.0, abs=1e-6)
    assert corp_perf.brier == pytest.approx(corp_perf.unc - corp_perf.dsc, abs=1e-5)


# --------------------------------------------------------------------------- 7. Sharp-vs-Soft & Line Movement (Steam)
def test_line_movement_and_sharp_soft_edge(tmp_path: Path):
    # Home steamed sharply from 2.20 -> 1.85 (aligned, strong_steam, chaotic_market).
    sig = analyze_line_movement([2.20, 3.40, 3.50], [1.85, 3.60, 4.50], outcome_idx=0)
    assert sig.direction == "aligned"
    assert sig.delta_p > 0.06
    assert sig.delta_logit > 0.25
    assert sig.strong_steam is True
    assert sig.chaotic_market is True

    # Away moved against sharply.
    sig_away = analyze_line_movement([2.20, 3.40, 3.50], [1.85, 3.60, 4.50], outcome_idx=2)
    assert sig_away.direction == "against"
    assert sig_away.delta_p < -0.04

    # Sharp-vs-soft mispricing edge detection.
    edge = sharp_soft_edge([1.80, 3.80, 4.60], soft_odds=2.05, outcome_idx=0)
    assert edge.ev > 0.08
    assert edge.is_plausible_edge is True
    assert 0.0 < edge.kelly_quarter <= 0.03

    # End-to-end backtest_sharp_soft_and_steam on synthetic fixture CSV.
    csv_file = tmp_path / "mini_tipsaudit.csv"
    csv_file.write_text(
        "result,void_reason,pin_open_home,pin_open_draw,pin_open_away,"
        "pin_close_home,pin_close_draw,pin_close_away,"
        "best_soft_home,best_soft_draw,best_soft_away\n"
        "1,,2.00,3.50,4.00,1.80,3.80,4.80,2.15,3.40,3.80\n"
        "2,,2.00,3.50,4.00,2.25,3.40,3.30,2.15,3.40,3.80\n"
        "1,,1.95,3.55,4.10,1.94,3.56,4.12,2.08,3.40,3.90\n",
        encoding="utf-8",
    )
    bt = backtest_sharp_soft_and_steam(csv_file)
    assert bt["n_matches"] == 3
    assert bt["sharp_soft_ev_tiers"]["ev>=2%"]["n"] == 3
    assert bt["steam_direction_on_ev2pct"]["steam_aligned (>=+2pp)"]["n"] == 1
    assert bt["steam_direction_on_ev2pct"]["steam_against (<=-2pp)"]["n"] == 1
    assert bt["steam_direction_on_ev2pct"]["steam_neutral (-2pp..+2pp)"]["n"] == 1


# --------------------------------------------------------------------------- 8. Adaptive Drawdown Kelly & Live Context Wiring
def test_adaptive_kelly_stake_throttling_and_circuit_breakers():
    # Healthy bankroll at peak -> positive stake allowed.
    ok = adaptive_kelly_stake(0.60, 2.00, bankroll=1000.0, peak_bankroll=1000.0, prob_std=0.02)
    assert ok["allowed"] is True
    assert 0.0 < float(ok["stake_fraction"]) <= 0.03
    assert float(ok["effective_multiplier"]) == pytest.approx(0.25, abs=1e-5)

    # 12.5% drawdown (halfway to 25% halt) -> multiplier throttled by 50%.
    dd_mid = adaptive_kelly_stake(0.60, 2.00, bankroll=875.0, peak_bankroll=1000.0, prob_std=0.02)
    assert dd_mid["allowed"] is True
    assert float(dd_mid["effective_multiplier"]) == pytest.approx(0.125, abs=1e-4)
    assert float(dd_mid["stake_fraction"]) < float(ok["stake_fraction"])

    # Daily loss >= 5% -> hard circuit breaker halts betting.
    halt_day = adaptive_kelly_stake(0.60, 2.00, bankroll=1000.0, daily_pnl=-55.0)
    assert halt_day["allowed"] is False and float(halt_day["stake_fraction"]) == 0.0

    # Weekly loss >= 12% -> hard circuit breaker halts betting.
    halt_wk = adaptive_kelly_stake(0.60, 2.00, bankroll=1000.0, weekly_pnl=-125.0)
    assert halt_wk["allowed"] is False and float(halt_wk["stake_fraction"]) == 0.0

    # Drawdown >= 25% -> hard circuit breaker halts betting.
    halt_dd = adaptive_kelly_stake(0.60, 2.00, bankroll=740.0, peak_bankroll=1000.0)
    assert halt_dd["allowed"] is False and float(halt_dd["stake_fraction"]) == 0.0

    # Remaining daily exposure cap enforced cleanly.
    capped = adaptive_kelly_stake(0.65, 2.00, bankroll=1000.0, daily_exposure=0.095, max_daily_exposure=0.10)
    assert capped["allowed"] is True and float(capped["stake_fraction"]) <= 0.005 + 1e-9

    # Negative EV rejected cleanly.
    neg = adaptive_kelly_stake(0.45, 2.00, bankroll=1000.0)
    assert neg["allowed"] is False and float(neg["stake_fraction"]) == 0.0


def test_self_improve_build_diag_ctx_propagates_motivation_and_referee():
    """Verify _build_diag_ctx (shared by self_improve & kasa_koruma) wires dead_rubber and referee_card_zscore."""
    match_dead = {
        "mu_home": 1.1,
        "mu_away": 0.9,
        "league": "İngiltere Premier Lig",
        "reference": {"source": "Pinnacle"},
        "research": {
            "motivation": {"home": "Orta sıra — hedefsiz", "away": "Garantiledi (hedefsiz)"},
            "referee_profile": {"card_zscore": 2.35},
        },
    }
    ctx = _build_diag_ctx(match_dead, {"direct": True})
    assert ctx["dead_rubber"] is True
    assert ctx["referee_card_zscore"] == pytest.approx(2.35, abs=1e-6)
    diag = diagnose_selection("3.5 Alt", 0.78, ctx, for_coupon=True)
    assert diag.ok is False


# --------------------------------------------------------------------------- 9. Multi-Book Consensus, Dispersion Kelly & Synthetic Coherence
def test_precision_weighted_consensus_dispersion_and_synthetic_coherence():
    quotes = [
        BookmakerQuote("betfair_exchange", (1.92, 3.65, 4.40)),  # ~1.5% vig -> highest weight
        BookmakerQuote("pinnacle", (1.89, 3.60, 4.30)),          # ~2.5% vig -> second weight
        BookmakerQuote("bet365", (1.85, 3.50, 4.10)),            # ~6.5% vig -> lowest weight
    ]
    cons = precision_weighted_consensus(quotes, method="goto")
    assert cons.n_books == 3
    assert sum(cons.probabilities) == pytest.approx(1.0, abs=1e-5)
    assert cons.weights["betfair_exchange"] > cons.weights["pinnacle"] > cons.weights["bet365"]
    assert cons.max_kl_divergence < 0.005

    # Consensus-to-Adaptive-Kelly bridge allows plausible +EV soft price and rejects extreme disagreement.
    stake_ok = adaptive_kelly_from_consensus(cons, outcome_idx=0, soft_odds=2.12, bankroll=1000.0)
    assert stake_ok["allowed"] is True and float(stake_ok["stake_fraction"]) > 0.0

    # High disagreement between sharp books must trigger KL safeguard.
    disagree = precision_weighted_consensus([
        BookmakerQuote("pinnacle", (1.60, 4.00, 6.00)),
        BookmakerQuote("betfair_exchange", (2.30, 3.30, 3.20)),
    ])
    stake_block = adaptive_kelly_from_consensus(disagree, outcome_idx=0, soft_odds=2.40, bankroll=1000.0)
    assert stake_block["allowed"] is False and float(stake_block["stake_fraction"]) == 0.0

    # Synthetic coherence detects when Dutching 1X2 beats an overpriced soft Double Chance quote.
    # 1/(1/2.10 + 1/3.40) = 1.2982 > offered 1.22 -> prefer_synthetic True!
    coh = check_synthetic_coherence(
        [2.10, 3.40, 3.60],
        double_chance={"ÇŞ 1X": 1.22},
        dnb={"DNB 1": 1.40},
    )
    dc_item = next(x for x in coh.cheapest_equivalents if x["market"] == "ÇŞ 1X")
    assert dc_item["prefer_synthetic"] is True
    assert dc_item["synthetic_dutch_odds"] > 1.29


# --------------------------------------------------------------------------- 10. In-Play Hawkes Momentum, 2-Goal Deficit & Next-Goal Pricing
def test_inplay_hawkes_momentum_two_goal_deficit_and_next_goal():
    base = inplay.LiveState(minute=65, home_goals=0, away_goals=0)
    rh0, ra0, _ = inplay.remaining_lambdas(1.5, 1.2, base)

    # 2-goal deficit triggers stronger Maia urgency boost than 1-goal deficit.
    trail1 = inplay.LiveState(minute=65, home_goals=0, away_goals=1)
    trail2 = inplay.LiveState(minute=65, home_goals=0, away_goals=2)
    rh1, ra1, _ = inplay.remaining_lambdas(1.5, 1.2, trail1)
    rh2, ra2, _ = inplay.remaining_lambdas(1.5, 1.2, trail2)
    assert rh2 > rh1 > rh0
    assert ra2 < ra1 < ra0

    # Recent goal triggers Hawkes self-excitation burst that decays over time.
    recent = inplay.LiveState(minute=65, home_goals=1, away_goals=1, last_goal_minute=63, last_goal_side="home")
    old = inplay.LiveState(minute=65, home_goals=1, away_goals=1, last_goal_minute=30, last_goal_side="home")
    rh_rec, ra_rec, notes_rec = inplay.remaining_lambdas(1.5, 1.2, recent)
    rh_old, ra_old, _ = inplay.remaining_lambdas(1.5, 1.2, old)
    assert rh_rec > rh_old and ra_rec > ra_old
    assert any("Hawkes" in n for n in notes_rec)

    # Exact next-goal probabilities sum to 1.0 and preserve team hazard ordering.
    ngp = inplay.next_goal_probabilities(0.70, 0.35)
    assert sum(ngp.values()) == pytest.approx(1.0, abs=1e-12)
    assert ngp["Sıradaki Gol Ev"] > ngp["Sıradaki Gol Dep"] > 0.0
    assert 0.0 < ngp["Sıradaki Gol Yok"] < 1.0


# --------------------------------------------------------------------------- 11. Per-AI Nesine CLV Ledger Lifecycle
def test_clv_ledger_record_close_settle_and_summarize(tmp_path: Path):
    ai_dir = tmp_path / "geminitahmin"
    day_dir = ai_dir / "2026-11-26"
    day_dir.mkdir(parents=True)

    (day_dir / "mac_tahminleri.csv").write_text(
        "tarih,saat,lig,mac,nesine_kodu,ana_secim_pazar,ana_secim,nesine_oran,olasilik,secim_adi\n"
        "2026-11-26,20:00,EPL,Arsenal - Chelsea,1001,Maç Sonucu,MS 1,1.95,0.56,MS 1\n"
        "2026-11-26,20:00,EPL,Liverpool - Spurs,1002,Alt/Üst,2.5 Üst,1.75,0.62,2.5 Üst\n",
        encoding="utf-8",
    )
    open_ng = {
        "matches": [
            {"code": 1001, "reference": {"source": "Pinnacle"}, "selections": [{"name": "MS 1", "fair_prob": 0.56, "odds": 1.95, "direct": True}]},
            {"code": 1002, "reference": {"source": "Pinnacle"}, "selections": [{"name": "2.5 Üst", "fair_prob": 0.62, "odds": 1.75, "direct": True}]},
        ]
    }
    (day_dir / "nesine_global.json").write_text(__import__("json").dumps(open_ng), encoding="utf-8")

    lpath = ai_dir / "clv_defteri.jsonl"
    rec = record_daily_picks(ai_dir, "2026-11-26", ledger_path=lpath)
    assert rec["added"] == 2

    # Closing snapshot: Arsenal steamed UP (0.56 -> 0.60 -> positive CLV & steam aligned),
    # Liverpool steamed DOWN (0.62 -> 0.55 -> negative CLV & steam against).
    close_ng = {
        "matches": [
            {"code": 1001, "selections": [{"name": "MS 1", "fair_prob": 0.60}]},
            {"code": 1002, "selections": [{"name": "2.5 Üst", "fair_prob": 0.55}]},
        ]
    }
    upd = update_closing_lines(lpath, close_ng, date_filter="2026-11-26")
    assert upd["updated_closing"] == 2

    stl = settle_ledger(
        lpath,
        {
            1001: {"completed": True, "ht": (1, 0), "ft90": (2, 0)},
            1002: {"completed": True, "ht": (0, 0), "ft90": (1, 0)},
        },
    )
    assert stl["settled"] == 2

    summ = summarize_clv_ledger(lpath)
    assert summ["n_with_closing_clv"] == 2
    assert summ["n_settled"] == 2
    assert summ["clv_report"]["mean_clv"] > 0.05  # (+0.17 and -0.0375) / 2
    assert "steam_aligned (>=+2pp)" in summ["by_steam_direction"]
    assert "steam_against (<=-2pp)" in summ["by_steam_direction"]
    assert summ["corp_calibration"]["brier"] >= 0.0
