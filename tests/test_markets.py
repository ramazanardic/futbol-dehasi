"""Unit tests for devigging solvers, Skellam distribution, and Asian Handicap pricing."""

import numpy as np
import pytest

from quantfoot.data.live_espn import american_to_decimal, normalize_club_team, normalize_international_team
from quantfoot.markets.devig import book_overround, devig, devig_batch
from quantfoot.markets.pricing import (
    expected_ah_ev,
    fair_ah_odds,
    invert_ah_ou_1x2,
    over_under_probability,
    price_all_markets,
    settle_asian_handicap,
    skellam_probabilities,
)


def test_devig_all_methods_sum_to_one_and_preserve_order():
    odds = [1.80, 3.60, 4.80]
    assert book_overround(odds) == pytest.approx(sum(1.0 / o for o in odds) - 1.0)
    for method in ("multiplicative", "power", "odds_ratio", "shin"):
        res = devig(odds, method=method)
        assert np.sum(res.probabilities) == pytest.approx(1.0, abs=1e-8)
        assert res.probabilities[0] > res.probabilities[1] > res.probabilities[2]
        if method in ("power", "shin", "odds_ratio"):
            # Favorite receives higher fair probability than naive multiplicative (FLB adjustment)
            mult = devig(odds, method="multiplicative").probabilities
            assert res.probabilities[0] > mult[0]


def test_devig_batch_and_zero_vig():
    odds_mat = np.array([[2.05, 2.05], [1.50, 4.20]])
    probs = devig_batch(odds_mat, method="power")
    assert probs.shape == (2, 2)
    assert np.allclose(probs.sum(axis=1), 1.0)


def test_skellam_matches_independent_poisson_matrix():
    mu_h, mu_a = 1.65, 1.15
    skel = skellam_probabilities(mu_h, mu_a, min_diff=-8, max_diff=8)
    assert sum(skel.values()) == pytest.approx(1.0, abs=1e-4)

    # Independent Poisson matrix sum of diagonals should match Skellam
    g = np.arange(15)
    from scipy.stats import poisson

    mat = np.outer(poisson.pmf(g, mu_h), poisson.pmf(g, mu_a))
    p_draw_mat = float(np.sum(np.diag(mat)))
    assert skel[0] == pytest.approx(p_draw_mat, abs=1e-5)


def test_asian_handicap_quarter_lines_and_fair_ev_zero():
    # Home -0.25 at odds 2.00
    assert settle_asian_handicap(1, -0.25, 2.0, is_home=True) == pytest.approx(1.0)
    assert settle_asian_handicap(0, -0.25, 2.0, is_home=True) == pytest.approx(-0.5)
    assert settle_asian_handicap(-1, -0.25, 2.0, is_home=True) == pytest.approx(-1.0)

    # Home -0.75 at odds 2.00
    assert settle_asian_handicap(2, -0.75, 2.0, is_home=True) == pytest.approx(1.0)
    assert settle_asian_handicap(1, -0.75, 2.0, is_home=True) == pytest.approx(0.5)
    assert settle_asian_handicap(0, -0.75, 2.0, is_home=True) == pytest.approx(-1.0)

    # Fair AH odds should produce exact 0.0 EV against the generating score matrix
    g = np.arange(9)
    from scipy.stats import poisson

    mat = np.outer(poisson.pmf(g, 1.5), poisson.pmf(g, 1.2))
    mat /= np.sum(mat)
    for line in (-1.25, -0.75, -0.25, 0.0, 0.25, 0.75):
        o_fair_h = fair_ah_odds(mat, line, is_home=True)
        assert expected_ah_ev(mat, line, o_fair_h, is_home=True) == pytest.approx(0.0, abs=1e-9)

    priced = price_all_markets(mat)
    assert sum(priced["1x2"].values()) == pytest.approx(1.0, abs=1e-9)
    assert priced["over_under"]["over_2.5"] + priced["over_under"]["under_2.5"] == pytest.approx(1.0)
    po, pu = over_under_probability(mat, 3.5)
    assert po + pu == pytest.approx(1.0, abs=1e-9)


def test_american_odds_and_team_aliases():
    assert american_to_decimal("+150") == pytest.approx(2.5)
    assert american_to_decimal("-200") == pytest.approx(1.5)
    assert american_to_decimal("EVEN") == pytest.approx(2.0)
    assert american_to_decimal("OFF") is None
    assert normalize_international_team("Türkiye") == "Turkey"
    assert normalize_international_team("Bosnia-Herzegovina") == "Bosnia and Herzegovina"
    known = {"Man United", "Fenerbahce", "Ath Madrid", "Galatasaray"}
    assert normalize_club_team("Manchester United", known) == "Man United"
    assert normalize_club_team("Fenerbahçe", known) == "Fenerbahce"
    assert normalize_club_team("Atlético Madrid", known) == "Ath Madrid"


def test_cross_market_ah_ou_inversion():
    lam, mu, p1x2 = invert_ah_ou_1x2(ah_line=-0.5, p_ah_home_share=0.58, p_over25=0.55)
    assert lam > mu
    assert np.sum(p1x2) == pytest.approx(1.0, abs=1e-9)
    assert p1x2[0] == pytest.approx(0.58, abs=0.02)


def test_negative_binomial_tail_matrix_thickens_6plus_tail():
    from quantfoot.markets import negative_binomial_score_matrix, summarize_tail_goals

    poisson_mat = negative_binomial_score_matrix(
        2.6, 1.3, alpha_nb=0.0, rho=0.0, shared_kappa=0.0, max_goals=14
    )
    nb_mat = negative_binomial_score_matrix(
        2.6, 1.3, alpha_nb=0.14, rho=-0.07, shared_kappa=0.12, max_goals=14
    )
    assert poisson_mat.shape == (15, 15)
    assert nb_mat.shape == (15, 15)
    assert np.sum(nb_mat) == pytest.approx(1.0, abs=1e-9)
    assert np.all(nb_mat >= 0.0)

    sum_pois = summarize_tail_goals(poisson_mat)
    sum_nb = summarize_tail_goals(nb_mat)
    assert sum_nb.variance_total > sum_pois.variance_total
    assert sum_nb.p_6plus > sum_pois.p_6plus
    assert sum_nb.p_4plus >= sum_nb.p_5plus >= sum_nb.p_6plus >= sum_nb.p_7plus
    assert sum_nb.fair_odds_6plus == pytest.approx(1.0 / sum_nb.p_6plus, rel=1e-6)
    for score_str, _ in sum_nb.top_6plus_scorelines:
        h, a = (int(x) for x in score_str.split("-"))
        assert h + a >= 6


def test_fit_tail_rates_from_markets_matches_blowout_quotes():
    from quantfoot.markets import (
        fit_tail_rates_from_markets,
        league_tail_params,
        matrix_ah_home_win_share,
        matrix_over_probability,
        summarize_tail_goals,
    )

    alpha_u17, kappa_u17 = league_tail_params("fifa.world.u17")
    alpha_club, kappa_club = league_tail_params("bra.1")
    assert alpha_u17 > alpha_club
    assert kappa_u17 > kappa_club

    mu_h, mu_a, mat = fit_tail_rates_from_markets(
        p_1x2=[0.88, 0.08, 0.04],
        ou_line=4.5,
        p_over=0.44,
        ah_line=-2.5,
        p_ah_home=0.60,
        seed_rates=(2.1, 0.7),
        alpha_nb=0.13,
        shared_kappa=0.11,
        fund_weight=0.10,
    )
    assert mu_h > mu_a * 2.5
    assert matrix_over_probability(mat, 4.5) == pytest.approx(0.44, abs=0.05)
    assert matrix_ah_home_win_share(mat, -2.5) == pytest.approx(0.60, abs=0.06)
    summary = summarize_tail_goals(mat)
    assert summary.p_home > 0.80
    assert 0.15 < summary.p_6plus < 0.45


def test_halves_btts_coherence_symmetry_and_tempo_correlation():
    from quantfoot.markets import compute_halves_btts, half_timing_profile

    a1_u21, k_u21, ha_u21 = half_timing_profile("eng.u21")
    a1_bra, k_bra, _ = half_timing_profile("bra.1")
    assert a1_u21 > a1_bra
    assert k_u21 > k_bra

    sym_open = compute_halves_btts(
        2.2, 2.1, first_half_share=a1_u21, match_kappa=k_u21, half_alpha=ha_u21
    )
    asym_blowout = compute_halves_btts(
        3.9, 0.4, first_half_share=a1_u21, match_kappa=k_u21, half_alpha=ha_u21
    )
    assert 0.0 < sym_open.p_both_halves_kg <= min(sym_open.p_1h_kg, sym_open.p_2h_kg)
    assert max(sym_open.p_1h_kg, sym_open.p_2h_kg) <= sym_open.p_either_half_kg <= sym_open.p_ft_kg < 1.0
    assert sym_open.p_2h_kg > sym_open.p_1h_kg
    assert sym_open.fair_odds_both_halves == pytest.approx(1.0 / sym_open.p_both_halves_kg, rel=1e-6)
    # Same expected total (4.3), symmetric shootout dominates lopsided mismatch
    assert sym_open.p_both_halves_kg > asym_blowout.p_both_halves_kg * 3.0

    # Shared tempo variance induces positive correlation across halves: P(2H | 1H) > P(2H)
    indep = compute_halves_btts(2.2, 2.1, first_half_share=a1_u21, match_kappa=0.0, half_alpha=ha_u21)
    assert sym_open.p_2h_kg_given_1h_kg > indep.p_2h_kg_given_1h_kg
    assert sym_open.p_both_halves_kg > indep.p_both_halves_kg


def test_com_poisson_and_regime_calibration():
    from quantfoot.markets import com_poisson_pmf, league_tail_regime, regime_score_matrix

    g = np.arange(15, dtype=float)
    pmf_cmp = com_poisson_pmf(2.0, nu=1.10, max_goals=14)
    pmf_poi = com_poisson_pmf(2.0, nu=1.00, max_goals=14)
    assert np.sum(pmf_cmp) == pytest.approx(1.0, abs=1e-9)
    mean_cmp = float(np.sum(g * pmf_cmp))
    var_cmp = float(np.sum((g - mean_cmp) ** 2 * pmf_cmp))
    var_poi = float(np.sum((g - float(np.sum(g * pmf_poi))) ** 2 * pmf_poi))
    assert mean_cmp == pytest.approx(2.0, abs=2e-3)
    assert var_cmp < var_poi

    club_reg = league_tail_regime("bra.1")
    intl_reg = league_tail_regime("fifa.friendly")
    assert club_reg == (1.10, 0.0, 0.0)
    assert intl_reg[0] == 1.00 and intl_reg[1] > 0.0

    mat_club = regime_score_matrix(1.6, 1.3, alpha_nb=0.0, shared_kappa=0.0, com_nu=1.10, max_goals=14)
    assert mat_club.shape == (15, 15)
    assert np.sum(mat_club) == pytest.approx(1.0, abs=1e-9)


def test_halves_btts_fgm_copula_preserves_coherence():
    from quantfoot.markets import compute_halves_btts, half_model_params

    e0_params = half_model_params("e0")
    assert e0_params[0] == pytest.approx(0.444)
    base = compute_halves_btts(1.6, 1.4, first_half_share=e0_params[0], match_kappa=e0_params[1], half_alpha=0.0, fgm_1h=0.0, fgm_2h=0.0)
    fgm = compute_halves_btts(1.6, 1.4, first_half_share=e0_params[0], match_kappa=e0_params[1], half_alpha=0.0, fgm_1h=0.12, fgm_2h=0.0)
    assert fgm.p_1h_kg > base.p_1h_kg
    assert 0.0 < fgm.p_both_halves_kg <= min(fgm.p_1h_kg, fgm.p_2h_kg) <= fgm.p_either_half_kg <= fgm.p_ft_kg < 1.0

