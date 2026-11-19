"""Cross-market coherence (property) tests for the pricing engines.

Every probability the engines publish must obey the laws of probability across markets:
complements sum to one, sub-events never exceed their parent event, marginals of joint
tables equal the direct markets, and zero-margin odds give zero expected value.
"""

import itertools

import numpy as np
import pytest

from quantfoot.markets.devig import devig
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.pricing import expected_ah_ev, fair_ah_odds, price_all_markets
from quantfoot.markets.tail_goals import regime_score_matrix
from quantfoot.strategy.kelly import baker_mchale_kelly_fraction, kelly_fraction

RATES = [0.4, 0.9, 1.4, 2.2, 3.2]
LEAGUES = [None, "e0", "fifa.friendly", "u21", "bra.1"]
CASES = [(h, a, lg) for (h, a), lg in itertools.product(itertools.product(RATES, RATES), LEAGUES)]
TOL = 2e-3  # bundle values are rounded to 4 decimals


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-{c[1]}-{c[2]}")
def bundle(request):
    mu_h, mu_a, league = request.param
    return compute_omni_markets(mu_h, mu_a, league=league)


def test_all_probabilities_are_valid(bundle):
    for key, p in bundle.all_probabilities().items():
        assert -1e-9 <= p <= 1.0 + 1e-9, key


def test_partitions_sum_to_one(bundle):
    for table in (bundle.ft_1x2, bundle.ht_1x2, bundle.h2_1x2, bundle.ht_ft):
        assert sum(table.values()) == pytest.approx(1.0, abs=TOL)


def test_over_under_complements_and_monotonicity(bundle):
    for prefix, table, lines in (("", bundle.ft_ou, (1.5, 2.5, 3.5, 4.5, 5.5)),
                                 ("İY ", bundle.ht_ou, (0.5, 1.5, 2.5)),
                                 ("2Y ", bundle.h2_ou, (0.5, 1.5, 2.5))):
        overs = [table[f"{prefix}{ln:.1f} Üst"] for ln in lines]
        for ln, ov in zip(lines, overs):
            assert ov + table[f"{prefix}{ln:.1f} Alt"] == pytest.approx(1.0, abs=TOL)
        assert all(a >= b - TOL for a, b in zip(overs, overs[1:]))


def test_goal_bands_match_over_under(bundle):
    gb, ou = bundle.goal_bands, bundle.ft_ou
    assert gb["0-1 Gol"] == pytest.approx(ou["1.5 Alt"], abs=TOL)
    assert gb["+6 Gol"] == pytest.approx(ou["5.5 Üst"], abs=TOL)
    assert gb["2-3 Gol"] == pytest.approx(ou["1.5 Üst"] - ou["3.5 Üst"], abs=TOL)
    assert gb["4-5 Gol"] == pytest.approx(ou["3.5 Üst"] - ou["5.5 Üst"], abs=TOL)


def test_double_chance_matches_1x2(bundle):
    p = bundle.ft_1x2
    assert bundle.double_chance["10"] == pytest.approx(p["1"] + p["0"], abs=TOL)
    assert bundle.double_chance["02"] == pytest.approx(p["0"] + p["2"], abs=TOL)


def test_htft_marginals_match_half_and_full_time(bundle):
    for code, key in (("1", "İY 1"), ("0", "İY 0"), ("2", "İY 2")):
        row = sum(v for k, v in bundle.ht_ft.items() if k.startswith(code + "/"))
        assert row == pytest.approx(bundle.ht_1x2[key], abs=TOL)
    for code in ("1", "0", "2"):
        col = sum(v for k, v in bundle.ht_ft.items() if k.endswith("/" + code))
        assert col == pytest.approx(bundle.ft_1x2[code], abs=TOL)


def test_combos_never_exceed_their_parts(bundle):
    c, p, ou, kg = bundle.combos, bundle.ft_1x2, bundle.ft_ou, bundle.btts
    assert c["MS 1 & 2.5 Üst"] <= min(p["1"], ou["2.5 Üst"]) + TOL
    assert c["MS 2 & 2.5 Üst"] <= min(p["2"], ou["2.5 Üst"]) + TOL
    assert c["MS 1 & KG Yok"] <= min(p["1"], kg["KG Yok"]) + TOL
    assert c["2.5 Üst & KG Var"] <= min(ou["2.5 Üst"], kg["KG Var"]) + TOL
    assert c["2.5 Alt & KG Yok"] <= min(ou["2.5 Alt"], kg["KG Yok"]) + TOL


def test_btts_hierarchy(bundle):
    kg = bundle.btts
    both, either = kg["1Y ve 2Y KG Var"], kg["En Az Bir Devre KG Var"]
    assert both <= min(kg["1. Yarı KG Var"], kg["2. Yarı KG Var"]) + TOL
    assert max(kg["1. Yarı KG Var"], kg["2. Yarı KG Var"]) <= either + TOL
    # BTTS inside one half implies BTTS over the full match.
    assert either <= kg["KG Var"] + 0.02


def test_half_expectations_add_up_to_full_time(bundle):
    assert bundle.exp_1h_total + bundle.exp_2h_total == pytest.approx(bundle.expected_total, rel=0.02)


@pytest.mark.parametrize("odds", [[1.80, 3.60, 4.80], [1.15, 7.5, 15.0], [2.9, 3.1, 2.6], [1.50, 2.62]])
@pytest.mark.parametrize("method", ["power", "shin", "odds_ratio", "multiplicative"])
def test_devig_is_a_proper_distribution(odds, method):
    p = devig(odds, method=method).probabilities
    assert p.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.all(p > 0)
    assert list(np.argsort(p)) == list(np.argsort(-np.asarray(odds)))
    # Removing margin can only raise fair odds above the offered ones.
    assert np.all(1.0 / p >= np.asarray(odds) - 1e-9)


@pytest.mark.parametrize("line", [-1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.75, 1.0])
@pytest.mark.parametrize("home", [True, False])
def test_fair_ah_odds_have_zero_ev(line, home):
    mat = regime_score_matrix(1.7, 1.1, alpha_nb=0.0, rho=-0.07, shared_kappa=0.0, com_nu=1.0)
    fair = fair_ah_odds(mat, line, is_home=home)
    assert expected_ah_ev(mat, line, fair, is_home=home) == pytest.approx(0.0, abs=1e-9)


def test_price_all_markets_coherent():
    mat = regime_score_matrix(1.6, 1.2, alpha_nb=0.0, rho=-0.07, shared_kappa=0.0, com_nu=1.0)
    pm = price_all_markets(mat)
    assert sum(pm["1x2"].values()) == pytest.approx(1.0)
    ou = pm["over_under"]
    assert all(ou[f"over_{a}"] >= ou[f"over_{b}"] for a, b in ((0.5, 1.5), (1.5, 2.5), (2.5, 3.5), (3.5, 4.5)))


def test_kelly_properties():
    assert kelly_fraction(0.45, 2.0) == 0.0  # negative EV -> no stake
    stakes = [kelly_fraction(p, 2.2, max_stake=1.0) for p in (0.47, 0.50, 0.55, 0.60)]
    assert stakes == sorted(stakes)
    # Parameter uncertainty can only shrink the stake.
    for p in (0.5, 0.55, 0.62):
        assert baker_mchale_kelly_fraction(p, 2.1, prob_std=0.06, max_stake=1.0) <= kelly_fraction(p, 2.1, max_stake=1.0)


def test_dixon_coles_low_score_convention():
    from quantfoot.markets.tail_goals import _apply_dixon_coles_low_scores

    mu_h, mu_a, rho = 2.0, 0.5, -0.1
    base = np.outer(np.exp(-mu_h) * mu_h ** np.arange(4) / [1, 1, 2, 6], np.exp(-mu_a) * mu_a ** np.arange(4) / [1, 1, 2, 6])
    adj = _apply_dixon_coles_low_scores(base / base.sum(), mu_h, mu_a, rho) * base.sum()
    ratio = adj / base
    # tau(1,0) = 1 + mu_away*rho and tau(0,1) = 1 + mu_home*rho (Dixon & Coles 1997), up to normalisation.
    assert ratio[1, 0] / ratio[2, 2] == pytest.approx(1 + mu_a * rho)
    assert ratio[0, 1] / ratio[2, 2] == pytest.approx(1 + mu_h * rho)


def test_division_codes_match_exactly():
    from quantfoot.markets.halves_btts import half_model_params

    assert half_model_params("e0") == half_model_params("E0")
    # Ecuador's slug contains "ec" but must not get the English Conference (EC) profile.
    assert half_model_params("ecu.1") == half_model_params(None)
    assert half_model_params("eng.u21.cup")[0] == pytest.approx(0.452)


def test_coupon_flags_unreachable_target():
    from quantfoot.strategy.coupon_builder import build_target_odds_coupon, select_best_valid_bet

    recs = select_best_valid_bet("m1", "H", "A", "e0", "", compute_omni_markets(1.5, 1.1, league="e0"))
    plan = build_target_odds_coupon([recs], target_odds=50.0)
    assert plan.reached_target is False
    assert plan.achieved_odds < 50.0
