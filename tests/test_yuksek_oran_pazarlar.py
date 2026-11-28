"""Yüksek oranlı pazar katmanı (skor, İY skoru, İY/MS, 2Y KG): matematik, sızıntısızlık ve izolasyon."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantfoot.coupons.coupon_rules import hard_banned_reason
from quantfoot.evaluation import yuksek_oran_backtest as bt
from quantfoot.markets import yuksek_oran_modeli as ym

ROOT = Path(__file__).resolve().parents[1]


def test_dc_matrix_normalized_and_rho_zero_is_independent():
    m = ym.dc_matrix([1.4, 0.7], [1.1, 0.4], 0.0)
    assert np.allclose(m.sum(axis=(1, 2)), 1.0)
    p = ym.poisson_pmf(np.array([1.4]))[0]
    q = ym.poisson_pmf(np.array([1.1]))[0]
    indep = np.outer(p, q)
    assert np.allclose(m[0], indep / indep.sum())
    m_neg = ym.dc_matrix([1.4], [1.1], -0.1)
    assert m_neg[0, 0, 0] > m[0, 0, 0] and m_neg[0, 1, 1] > m[0, 1, 1]  # rho<0 düşük beraberlikleri şişirir


def test_htft_consistent_with_full_time_convolution():
    m1 = ym.dc_matrix([0.6, 1.0], [0.5, 0.3])
    m2 = ym.dc_matrix([0.8, 1.2], [0.6, 0.4])
    h = ym.htft_from_halves(m1, m2)
    ft = ym.convolve_halves(m1, m2)
    i, j = np.indices(ft.shape[1:])
    assert np.allclose(h.sum(axis=1), 1.0)
    assert np.allclose(h[:, [0, 3, 6]].sum(axis=1), (ft * (i > j)).sum(axis=(1, 2)), atol=1e-6)
    assert np.allclose(h[:, [0, 1, 2]].sum(axis=1), (m1 * (i > j)).sum(axis=(1, 2)), atol=1e-6)


def test_game_state_model_reduces_to_independent_and_raises_comebacks():
    m1 = ym.dc_matrix([0.6], [0.5])
    l2, u2 = np.array([0.8]), np.array([0.6])
    one = np.ones((1, 3))
    g = ym.game_state_model(m1, l2, u2, one, one)
    assert np.allclose(g["htft"], ym.htft_from_halves(m1, ym.dc_matrix(l2, u2)))
    assert np.allclose(g["ft_matrix"], ym.convolve_halves(m1, ym.dc_matrix(l2, u2)))
    # geride kapatan daha çok atarsa geri dönüşler (1/2, 2/1) artar
    mh, ma = np.array([[0.95, 1.0, 1.10]]), np.array([[1.10, 1.0, 0.95]])
    g2 = ym.game_state_model(m1, l2, u2, mh, ma)
    lab = list(ym.HTFT_LABELS)
    assert g2["htft"][0, lab.index("1/2")] > g["htft"][0, lab.index("1/2")]
    assert g2["htft"][0, lab.index("2/1")] > g["htft"][0, lab.index("2/1")]
    assert np.isclose(g2["htft"].sum(), 1.0) and np.isclose(g2["ft_matrix"].sum(), 1.0)


def test_cell_factors_move_toward_observed_frequency():
    rng = np.random.default_rng(0)
    pred = np.tile([0.5, 0.3, 0.2], (5000, 1))
    y = rng.choice(3, size=5000, p=[0.4, 0.3, 0.3])
    f = ym.cell_factors(pred, y, prior=60)
    adj = ym.apply_cell_factors(pred, f)
    assert np.allclose(adj.sum(axis=1), 1.0)
    assert abs(adj[0, 0] - 0.4) < 0.02 and abs(adj[0, 2] - 0.3) < 0.02


def test_logit_calibration_identity_on_calibrated_data():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.1, 0.6, 20000)
    y = (rng.uniform(size=p.size) < p).astype(float)
    a, b = ym.fit_logit_calibration(p, y)
    assert abs(a) < 0.1 and abs(b - 1) < 0.1


def test_market_inverter_round_trip():
    inv = ym.MarketInverter()
    m = ym.dc_matrix([1.6], [1.0], -0.05, n=12)
    i, j = np.indices(m.shape[1:])
    p1, p2 = (m * (i > j)).sum(), (m * (i < j)).sum()
    po = (m * (i + j > 2.5)).sum()
    lam, mu = inv.invert(np.array([p1]), np.array([p2]), np.array([po]))
    assert abs(lam[0] - 1.6) < 0.05 and abs(mu[0] - 1.0) < 0.05
    lam2, mu2 = inv.invert(np.array([p1]), np.array([p2]), np.array([np.nan]))
    assert np.isfinite(lam2[0]) and np.isfinite(mu2[0])


def test_fit_maher_ranks_teams():
    rng = np.random.default_rng(2)
    teams = ["A", "B", "C", "D"]
    strength = {"A": 1.6, "B": 1.0, "C": 1.0, "D": 0.6}
    H, A, gh, ga = [], [], [], []
    for _ in range(150):
        for h in teams:
            for a in teams:
                if h != a:
                    H.append(h)
                    A.append(a)
                    gh.append(rng.poisson(1.4 * strength[h] / strength[a] ** 0.5))
                    ga.append(rng.poisson(1.1 * strength[a] / strength[h] ** 0.5))
    fit = ym.fit_maher(np.array(H), np.array(A), np.array(gh, float), np.array(ga, float), np.ones(len(H)))
    assert fit.att["A"] > fit.att["B"] > fit.att["D"]
    assert fit.expect("A", "D")[0] > fit.expect("D", "A")[0]


def _synthetic(n_weeks: int = 140) -> pd.DataFrame:
    rng = np.random.default_rng(3)
    teams = [f"T{i}" for i in range(12)]
    rows = []
    start = pd.Timestamp("2021-01-04")
    for w in range(n_weeks):
        order = rng.permutation(teams)
        for k in range(0, 12, 2):
            fh, fa = rng.poisson(1.4), rng.poisson(1.1)
            hh, ha = rng.binomial(fh, 0.45), rng.binomial(fa, 0.45)
            rows.append({"Division": "X1", "MatchDate": start + pd.Timedelta(days=7 * w + 5), "HomeTeam": order[k],
                         "AwayTeam": order[k + 1], "FTHome": fh, "FTAway": fa, "HTHome": hh, "HTAway": ha,
                         "HomeCorners": rng.poisson(5.3), "AwayCorners": rng.poisson(4.5),
                         "p1": 0.45, "px": 0.27, "p2": 0.28, "po": 0.5})
    return pd.DataFrame(rows)


def test_build_features_has_no_lookahead():
    df = _synthetic()
    cfg = bt.FeatureConfig(start="2022-06-01")
    f1 = bt.build_features(df, cfg)
    cut = pd.Timestamp("2022-10-01")
    df2 = df.copy()
    later = df2.MatchDate >= cut
    df2.loc[later, "FTHome"] = 9  # geleceği boz
    df2.loc[later, "HomeCorners"] = 30
    f2 = bt.build_features(df2, cfg)
    early = (f1.MatchDate < cut).to_numpy()
    cols = ["lam_m", "mu_m", "s_h", "s_a", "s_lig", "ch_m", "ca_m"]
    assert f1.loc[early, cols].notna().any().all()
    pd.testing.assert_frame_equal(f1.loc[early, cols], f2.loc[early, cols])


def test_walk_forward_calibration_uses_only_past_months():
    df = _synthetic()
    df["lam_m"], df["mu_m"], df["lam_p"], df["mu_p"] = 1.4, 1.1, 1.4, 1.1
    df["s_lig"] = df["s_h"] = df["s_a"] = 0.45
    y = bt.outcomes(df)
    raw = bt.raw_probs(df, bt.ProbConfig(), "sonra")
    cal1, _ = bt.walk_forward_calibrate(df, {k: v.copy() for k, v in raw.items()}, y, "2021-06-01", prior=60)
    y2 = {k: v.copy() for k, v in y.items()}
    last_m = df.MatchDate.dt.to_period("M") == df.MatchDate.dt.to_period("M").max()
    y2["htft"][last_m.to_numpy()] = 2  # son ayın sonuçlarını değiştir
    y2["ft"][last_m.to_numpy()] = 0
    cal2, _ = bt.walk_forward_calibrate(df, {k: v.copy() for k, v in raw.items()}, y2, "2021-06-01", prior=60)
    assert np.allclose(cal1["htft"], cal2["htft"]) and np.allclose(cal1["ft"], cal2["ft"])


def test_predict_markets_probabilities_sum_to_one():
    params = ym.load_params()
    out = ym.predict_markets(1.5, 1.1, division="E0", params=params)
    assert set(out) >= {"İY/MS", "Skor", "İY Skor", "2Y KG"}
    assert "Korner" not in out  # korner banko ailesine taşındı (markets/korner_banko.py)
    assert sum(out["İY/MS"].values()) == pytest.approx(1.0, abs=1e-3)
    assert sum(out["Skor"].values()) == pytest.approx(1.0, abs=1e-3)
    assert sum(out["İY Skor"].values()) == pytest.approx(1.0, abs=1e-3)
    # ev favorisinde 1/1 > 2/2 ve geri dönüş 2/1 > 0
    assert out["İY/MS"]["İY/MS 1/1"] > out["İY/MS"]["İY/MS 2/2"] > 0
    assert out["İY/MS"]["İY/MS 2/1"] > 0


@pytest.mark.parametrize("name", ["İY/MS 2/1", "İY/MS 1/2", "İY/MS 0/0", "Skor 2-1", "İY Skor 1-0", "2Y KG Var",
                                  "Skor 0-0"])
def test_high_odds_selections_stay_banned_from_banko(name):
    assert hard_banned_reason(name), f"{name} banko kuponda yasak kalmalı"


def test_layer_not_wired_into_daily_pipeline():
    pattern = re.compile(r"yuksek_oran_(pazarlar|modeli|backtest)")
    for rel in ("scripts/gunluk_analiz.py", "scripts/nesine_kupon.py", "scripts/kupon_kur.py", "scripts/kasa_koruma.py"):
        p = ROOT / rel
        if p.exists():
            assert not pattern.search(p.read_text(encoding="utf-8")), f"{rel} yüksek oran katmanını otomatik çağırmamalı"


def test_extra_markets_are_coherent_with_half_model():
    from scipy.stats import poisson

    lam, mu, sh = np.array([1.5]), np.array([1.1]), 0.45
    m1 = ym.dc_matrix(lam * sh, mu * sh, 0.0)
    ones = np.ones((1, 3))
    gs = ym.game_state_model(m1, lam * (1 - sh), mu * (1 - sh), ones, ones, 0.0)
    ex = ym.extra_markets(m1, gs)
    for k, v in ex.items():
        if v.ndim == 2:
            assert v.sum(axis=1)[0] == pytest.approx(1.0, abs=1e-6), k
        assert (v >= -1e-12).all(), k
    # durum çarpanı 1 ve rho 0: toplam gol Poisson(λ+μ); yarılar bağımsız Poisson
    assert ex["gol_araligi"][0, 0] == pytest.approx(poisson.cdf(1, 2.6), abs=2e-3)
    assert ex["iy_gol"][0, 0] == pytest.approx(poisson.pmf(0, (lam + mu)[0] * sh), abs=1e-4)
    assert ex["2y_gol"][0, 0] == pytest.approx(poisson.pmf(0, (lam + mu)[0] * (1 - sh)), abs=1e-4)
    p2 = poisson.sf(1, (lam + mu)[0] * sh) * poisson.sf(1, (lam + mu)[0] * (1 - sh))
    assert ex["iki_yari_15_ust"][0] == pytest.approx(p2, abs=1e-4)
    # İY skoru marjinali: İY 0-0 hücrelerinin toplamı = m1[0,0]
    k = len(ym.HT_FT_SCORE_FT)
    assert ex["iy_ms_skor"][0, :k].sum() == pytest.approx(m1[0, 0, 0], abs=2e-3)
    # İY/2Y KG: dört hücre toplamı 1
    assert ex["iy_2y_kg"][0].sum() == pytest.approx(1.0, abs=1e-9)


def test_new_market_decision_requires_both_periods_and_ece():
    from quantfoot.evaluation import yuksek_oran_yeni_pazar as yn

    def blk(fark, t, ece_s=0.001, ece_p=0.002):
        return {"sonra_vs_piyasa": {"fark": fark, "t": t}, "ece": {"sonra": ece_s, "piyasa": ece_p}}

    res = {"gol_araligi": {"doğrulama": blk(-0.001, -2.5), "test": blk(-0.001, -3.5)},          # geçer
           "iy_gol": {"doğrulama": blk(-0.001, -2.5), "test": blk(-0.0005, -2.0)},              # test zayıf
           "2y_gol": {"doğrulama": blk(0.0004, 1.0), "test": blk(-0.001, -4.0)},                # doğrulama kötü
           "2y_sonucu": {"doğrulama": blk(-0.001, -2.5), "test": blk(-0.001, -3.5, 0.004, 0.002)}}  # ECE kötü
    keep, why = yn.decide(res)
    assert keep == ["gol_araligi"] and set(why) == {"iy_gol", "2y_gol", "2y_sonucu"}
