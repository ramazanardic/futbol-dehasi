"""Unit tests for Dixon-Coles gradients, Bivariate Poisson, causal ratings, and calibration."""

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

from quantfoot.models.bivariate_poisson import DiagonalBivariatePoisson
from quantfoot.models.dixon_coles import TimeDecayedDixonColes
from quantfoot.models.ensemble import (
    FundamentalEnsemble,
    apply_dirichlet,
    apply_temperature,
    fit_dirichlet_odir,
    fit_temperature_scaling,
)
from quantfoot.models.gap_ratings import WheatcroftGAPRatings
from quantfoot.models.gas_poisson import GASPoissonModel
from quantfoot.models.glicko2 import FootballGlicko2
from quantfoot.models.kalman import KalmanPoissonModel
from quantfoot.models.ordinal import OrderedLogit3Class
from quantfoot.models.ratings import CausalRatingEngine
from quantfoot.models.weibull_copula import frank_copula_score_matrix, weibull_count_pmf


def _synthetic_league(n_matches: int = 180, seed: int = 7):
    rng = np.random.default_rng(seed)
    teams = ["TeamA", "TeamB", "TeamC", "TeamD", "TeamE", "TeamF"]
    home = rng.choice(teams, size=n_matches)
    away = rng.choice(teams, size=n_matches)
    keep = home != away
    home, away = home[keep], away[keep]
    m = len(home)
    hg = rng.poisson(1.45, size=m)
    ag = rng.poisson(1.15, size=m)
    days = np.linspace(m * 2.0, 0.0, m)
    return home, away, hg, ag, days


def test_dixon_coles_analytical_gradient_and_prediction():
    home, away, hg, ag, days = _synthetic_league()
    dc = TimeDecayedDixonColes(xi=0.002, l2_reg=0.05)

    # Check gradient accuracy directly on internal NLL function
    teams = sorted(set(home).union(set(away)))
    tmap = {t: i for i, t in enumerate(teams)}
    h_idx = np.array([tmap[t] for t in home], dtype=np.int32)
    a_idx = np.array([tmap[t] for t in away], dtype=np.int32)
    w = np.exp(-dc.xi * days)
    w /= np.mean(w)
    m00 = (hg == 0) & (ag == 0)
    m01 = (hg == 0) & (ag == 1)
    m10 = (hg == 1) & (ag == 0)
    m11 = (hg == 1) & (ag == 1)
    x_probe = np.zeros(2 * len(teams) + 3)
    x_probe[2 * len(teams)] = 0.2
    x_probe[2 * len(teams) + 1] = -0.04
    x_probe[2 * len(teams) + 2] = 0.1

    err = check_grad(
        lambda x: dc._nll_and_grad(x, len(teams), h_idx, a_idx, hg.astype(float), ag.astype(float), w, m00, m01, m10, m11)[0],
        lambda x: dc._nll_and_grad(x, len(teams), h_idx, a_idx, hg.astype(float), ag.astype(float), w, m00, m01, m10, m11)[1],
        x_probe,
        epsilon=1e-7,
    )
    assert err < 1e-4

    dc.fit(home, away, hg, ag, days, home_xg=hg * 0.8 + 0.3, away_xg=ag * 0.8 + 0.3, xg_weight=0.5)
    mat = dc.score_matrix("TeamA", "TeamB")
    assert np.sum(mat) == pytest.approx(1.0, abs=1e-9)
    p1x2 = dc.predict_1x2("TeamA", "TeamB")
    assert np.sum(p1x2) == pytest.approx(1.0, abs=1e-9)


def test_diagonal_bivariate_poisson_normalization():
    home, away, hg, ag, days = _synthetic_league(140, seed=11)
    dibp = DiagonalBivariatePoisson(xi=0.002, l2_reg=0.1)
    dibp.fit(home, away, hg, ag, days)
    mat = dibp.score_matrix("TeamA", "TeamC")
    assert np.sum(mat) == pytest.approx(1.0, abs=1e-9)
    assert np.all(mat >= 0.0)


def test_causal_rating_engine_zero_leakage():
    eng = CausalRatingEngine()
    d1 = pd.Timestamp("2025-09-01")
    d2 = pd.Timestamp("2025-09-08")

    f_before = eng.pre_match_features("TeamA", "TeamB", d1)
    assert f_before["elo_home"] == pytest.approx(1500.0)
    assert f_before["min_games"] == pytest.approx(0.0)

    eng.update("TeamA", "TeamB", 3.0, 0.0, 2.4, 0.6, 8.0, 2.0, 18.0, 7.0, d1)
    f_after = eng.pre_match_features("TeamA", "TeamB", d2)
    assert f_after["elo_home"] > 1500.0
    assert f_after["elo_away"] < 1500.0
    assert f_after["pi_diff_venue"] > 0.0
    assert f_after["min_games"] == pytest.approx(1.0)


def test_temperature_and_dirichlet_calibration():
    rng = np.random.default_rng(123)
    raw = rng.dirichlet([2.0, 1.5, 1.5], size=400)
    y = np.array([rng.choice(3, p=row) for row in raw])

    temp = fit_temperature_scaling(raw, y)
    p_temp = apply_temperature(raw, temp)
    assert np.allclose(p_temp.sum(axis=1), 1.0)

    w, b = fit_dirichlet_odir(raw, y)
    p_dir = apply_dirichlet(raw, w, b)
    assert np.allclose(p_dir.sum(axis=1), 1.0)


def test_gas_poisson_and_gap_and_weibull_copula():
    gas = GASPoissonModel(home_adv=0.25, offseason_days=30, offseason_reversion=0.5)
    lam_home, _ = gas.expected_goals("A", "B", neutral=False)
    lam_neut, _ = gas.expected_goals("A", "B", neutral=True)
    assert lam_home > lam_neut

    gas.update("A", "B", 3.0, 0.0, match_date=pd.Timestamp("2026-01-01"))
    assert gas.att["A"] > 0.0
    assert gas.defn["B"] < 0.0
    prev_att = gas.att["A"]
    gas.update("A", "B", 1.0, 1.0, match_date=pd.Timestamp("2026-04-01"))
    assert abs(gas.att["A"]) < prev_att  # off-season reversion ran

    gap = WheatcroftGAPRatings(lam=0.1, phi1=0.7, phi2=0.7, base_stat=10.0)
    gap.update("A", "B", 9.0, 2.0)
    exp_a, exp_b = gap.expected_stats("A", "B")
    assert exp_a > exp_b

    from scipy.stats import poisson

    p_wc = weibull_count_pmf(1.65, shape_c=1.0, max_n=8)
    p_po = poisson.pmf(np.arange(9), 1.65)
    p_po /= np.sum(p_po)
    assert np.max(np.abs(p_wc - p_po)) < 1e-12

    mat = frank_copula_score_matrix(weibull_count_pmf(1.5, 1.08), weibull_count_pmf(1.2, 1.08), theta=-0.2)
    assert mat.shape == (9, 9)
    assert np.sum(mat) == pytest.approx(1.0, abs=1e-9)


def test_football_glicko2_uncertainty_and_offseason():
    gl = FootballGlicko2(home_adv=0.35, base_rd=110.0, offseason_days=75, offseason_reversion=0.94)
    d1 = pd.Timestamp("2025-09-01")
    r0, rd0 = gl.get_rating("TeamA", d1)
    assert r0 == pytest.approx(1500.0)
    assert rd0 == pytest.approx(110.0)

    f_home = gl.pre_match_features("TeamA", "TeamB", d1, neutral=False)
    f_neut = gl.pre_match_features("TeamA", "TeamB", d1, neutral=True)
    assert f_home["glicko_diff"] > f_neut["glicko_diff"]
    assert f_home["glicko_exp_h"] > 0.5

    gl.update("TeamA", "TeamB", 3.0, 0.0, d1)
    r_after, rd_after = gl.get_rating("TeamA", pd.Timestamp("2025-09-08"))
    rb_after, _ = gl.get_rating("TeamB", pd.Timestamp("2025-09-08"))
    assert r_after > 1500.0
    assert rb_after < 1500.0
    assert rd_after < 110.0

    # Long off-season gap (>= 75 days) inflates RD and mean-reverts mu toward 1500
    r_off, rd_off = gl.get_rating("TeamA", pd.Timestamp("2026-01-15"))
    assert rd_off > rd_after
    assert abs(r_off - 1500.0) < abs(r_after - 1500.0)


def test_ordered_logit_3class_probabilities_and_monotonicity():
    rng = np.random.default_rng(99)
    x = rng.normal(size=(400, 2))
    latent = 1.4 * x[:, 0] - 0.8 * x[:, 1]
    y = np.where(latent > 0.6, 0, np.where(latent < -0.6, 2, 1))

    clf = OrderedLogit3Class(l2_reg=1.0).fit(x, y)
    assert clf.c1 < clf.c2
    probs = clf.predict_proba(x)
    assert probs.shape == (400, 3)
    assert np.allclose(probs.sum(axis=1), 1.0)
    assert np.all(probs > 0.0)

    probe = np.array([[-2.0, 0.0], [2.0, 0.0]])
    p_probe = clf.predict_proba(probe)
    assert p_probe[1, 0] > p_probe[0, 0]  # higher x[0] -> higher Home win prob


def test_dual_gas_xg_blend_and_dynamic_hfa():
    gas_goal = GASPoissonModel(xg_blend=0.0, k_hfa=0.02)
    gas_dual = GASPoissonModel(xg_blend=0.45, k_hfa=0.02)
    init_hfa = gas_dual.home_adv
    d1 = pd.Timestamp("2026-02-01")

    # Equal goals (1-1) but high home xG (2.6 vs 0.5) should shift dual attack higher
    gas_goal.update("A", "B", 1.0, 1.0, hxg=2.6, axg=0.5, match_date=d1)
    gas_dual.update("A", "B", 1.0, 1.0, hxg=2.6, axg=0.5, match_date=d1)
    assert gas_dual.att["A"] > gas_goal.att["A"]

    # Non-neutral update shifts home_adv; neutral leaves it unchanged
    gas_dual.update("A", "B", 4.0, 0.0, hxg=3.2, axg=0.4, neutral=False, match_date=d1)
    assert gas_dual.home_adv > init_hfa
    hfa_snapshot = gas_dual.home_adv
    gas_dual.update("A", "B", 0.0, 4.0, hxg=0.4, axg=3.2, neutral=True, match_date=d1)
    assert gas_dual.home_adv == pytest.approx(hfa_snapshot)


def test_kalman_poisson_covariance_and_pyramid_promotion():
    km = KalmanPoissonModel()
    d0 = pd.Timestamp("2025-08-10")
    u0 = km.posterior_uncertainty("Burnley", "Everton", match_date=d0, div="E0")
    km.update("Burnley", "Leeds", 2.0, 0.0, hxg=1.8, axg=0.5, hsot=6.0, asot=2.0, match_date=d0, div="E1")
    u1 = km.posterior_uncertainty("Burnley", "Everton", match_date=pd.Timestamp("2025-08-17"), div="E1")
    assert u1 < u0

    # Promotion E1 -> E0 should inflate uncertainty and attenuate attack relative to staying in E1
    lam_e1, _ = km.expected_goals("Burnley", "Everton", match_date=pd.Timestamp("2025-08-17"), div="E1")
    lam_e0, _ = km.expected_goals("Burnley", "Everton", match_date=pd.Timestamp("2025-08-17"), div="E0")
    u_promo = km.posterior_uncertainty("Burnley", "Everton", match_date=pd.Timestamp("2025-08-17"), div="E0")
    assert lam_e0 < lam_e1
    assert u_promo > u1

    mat = km.score_matrix("Burnley", "Everton", match_date=pd.Timestamp("2025-08-17"), div="E0")
    assert np.sum(mat) == pytest.approx(1.0, abs=1e-9)


def test_tier_aware_gap_and_elo_promotion_regression():
    gap = WheatcroftGAPRatings(lam=0.10, base_stat=10.0)
    gap.update("TeamUp", "Other", 12.0, 1.0, div="E1")
    e_e1, _ = gap.expected_stats("TeamUp", "Other", div="E1")
    e_e0, _ = gap.expected_stats("TeamUp", "Other", div="E0")
    # Promoted team expects lower attacking volume in the stronger E0 tier than staying in E1
    assert e_e0 < e_e1

    eng = CausalRatingEngine()
    d1 = pd.Timestamp("2025-05-01")
    eng.update("TeamUp", "Other", 3.0, 0.0, 2.5, 0.5, 7.0, 2.0, 16.0, 6.0, d1, div="E1")
    elo_e1 = eng.get_elo("TeamUp", div="E1")
    elo_e0 = eng.get_elo("TeamUp", div="E0")
    # Promoted team shrinks partway toward E0 anchor rather than freezing flat E1 value
    assert elo_e0 != pytest.approx(elo_e1)
    assert elo_e0 > 1525.0


def test_fundamental_ensemble_v4_fit_and_predict():
    rng = np.random.default_rng(77)
    n = 450
    strength = rng.normal(size=n)
    p_raw = np.column_stack([
        np.clip(0.45 + 0.15 * strength, 0.1, 0.8),
        np.full(n, 0.26),
        np.clip(0.29 - 0.15 * strength, 0.1, 0.8),
    ])
    p_raw /= p_raw.sum(axis=1, keepdims=True)
    y = np.array([rng.choice(3, p=row) for row in p_raw], dtype=int)

    df = pd.DataFrame({
        "MatchDate": pd.date_range("2020-01-01", periods=n, freq="2D"),
        "y": y,
        "dcg_h": p_raw[:, 0], "dcg_d": p_raw[:, 1], "dcg_a": p_raw[:, 2],
        "dch_h": p_raw[:, 0], "dch_d": p_raw[:, 1], "dch_a": p_raw[:, 2],
        "kal_h": p_raw[:, 0], "kal_d": p_raw[:, 1], "kal_a": p_raw[:, 2],
        "kal_lam": np.clip(1.4 + 0.3 * strength, 0.3, 4.0),
        "kal_mu": np.clip(1.2 - 0.3 * strength, 0.3, 4.0),
        "kal_uncert": rng.uniform(0.3, 0.7, size=n),
        "gas_h": p_raw[:, 0], "gas_d": p_raw[:, 1], "gas_a": p_raw[:, 2],
        "gap_sot_diff": 2.0 * strength + rng.normal(scale=0.5, size=n),
        "gap_sot_sum": rng.uniform(6.0, 12.0, size=n),
        "gap_vol_diff": 3.0 * strength + rng.normal(scale=0.5, size=n),
        "gap_vol_sum": rng.uniform(18.0, 30.0, size=n),
        "gap_xg_diff": 0.6 * strength + rng.normal(scale=0.2, size=n),
        "gap_xg_sum": rng.uniform(1.8, 3.6, size=n),
        "glicko_diff": strength,
        "glicko_uncert": rng.uniform(0.3, 0.9, size=n),
        "glicko_exp_h": 1.0 / (1.0 + np.exp(-strength)),
        "elo_diff": 120.0 * strength,
        "pi_diff_venue": 0.4 * strength,
        "pi_diff_overall": 0.35 * strength,
        "pi_exp_gd": 0.6 * strength,
        "sos_xg_diff": 0.5 * strength,
        "gs_xg_diff": 0.5 * strength,
        "xg_diff_10": 0.5 * strength,
        "xg_luck_h": rng.normal(scale=0.3, size=n),
        "xg_luck_a": rng.normal(scale=0.3, size=n),
        "ht_gd_diff": rng.normal(scale=0.4, size=n),
        "cards_diff": rng.normal(scale=0.5, size=n),
        "sot_diff_10": 1.5 * strength,
        "pts_diff_5": 0.5 * strength,
        "rest_diff": rng.integers(-4, 5, size=n),
        "lg_avg_goals": np.full(n, 2.65),
        "lg_home_rate": np.full(n, 0.45),
        "is_covid": np.where(np.arange(n) < 100, 1.0, 0.0),
    })

    ens = FundamentalEnsemble().fit(df)
    assert np.sum(ens.weights_) == pytest.approx(1.0, abs=1e-9)
    assert len(ens.weights_) == 10

    comps = ens.predict_components(df.iloc[:40])
    for key in (
        "elo", "pi", "dc_goals", "dc_hybrid", "kalman", "gas_poisson",
        "gap_ordered", "gap_elo", "pyramid_rating", "glicko2", "mlp", "lgbm",
        "raw_ensemble", "calibrated_ensemble",
    ):
        assert comps[key].shape == (40, 3)
        assert np.allclose(comps[key].sum(axis=1), 1.0)
    assert comps["epistemic_std"].shape == (40, 3)
