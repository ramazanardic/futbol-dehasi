"""Toplam korner Alt/Üst banko ailesi (t179u): model, takım eşleme, Nesine fiyatlama ve kupon havuzu."""

from __future__ import annotations

import datetime as dt
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from quantfoot.evaluation import korner_backtest as kb
from quantfoot.markets import korner_banko as K

ROOT = Path(__file__).resolve().parents[1]
PARAMS = {"etkin": True, "gecerli": ["Korner 8.5 Üst", "Korner 11.5 Alt", "Korner 12.5 Alt"],
          "katsayi": [4.0, 0.6], "var_ort": 1.15}


def test_nb_over_wider_than_poisson():
    p_pois = K.nb_over(np.array([10.0]), 1.0, 13.5)[0]
    p_nb = K.nb_over(np.array([10.0]), 1.5, 13.5)[0]
    assert p_nb > p_pois > 0


def test_parse_selection_only_total_corner_half_lines():
    assert K.parse_selection("Korner 9.5 Üst") == (9.5, "Üst")
    assert K.parse_selection("Korner 12.5 Alt") == (12.5, "Alt")
    for bad in ("İY Korner 4.5 Üst", "Korner 9 Üst", "Kart 3.5 Üst", "DEĞİL(Korner 9.5 Üst)", "2.5 Üst", ""):
        assert K.parse_selection(bad) is None, bad


def test_valid_selections_empty_when_file_missing_or_not_enabled(tmp_path):
    assert K.valid_selections({}) == frozenset()
    assert K.valid_selections({"etkin": False, "gecerli": ["Korner 8.5 Üst"]}) == frozenset()
    assert K.load_params(tmp_path / "yok.json") == {}
    assert K.valid_selections(PARAMS) == frozenset(PARAMS["gecerli"])


def test_repo_calibration_file_is_consistent():
    p = K.load_params()
    assert p, "data/calibration/korner_kalibrasyon.json yok: scripts/korner_olcum.py çalıştır"
    assert p["olcut"]["azami_eksik"] == pytest.approx(0.05)
    if p["etkin"]:
        assert p["gecerli"]
        for n in p["gecerli"]:
            assert K.parse_selection(n) is not None
    else:
        assert not K.valid_selections(p)


def _league(n_weeks: int = 120, div: str = "X1", teams: tuple[str, ...] = ("Alpha", "Beta", "Gamma", "Delta", "Eps", "Zeta"),
            seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    start = pd.Timestamp("2024-01-06")
    for w in range(n_weeks):
        order = rng.permutation(teams)
        for k in range(0, len(teams), 2):
            rows.append({"Division": div, "MatchDate": start + pd.Timedelta(days=7 * w), "HomeTeam": order[k],
                         "AwayTeam": order[k + 1], "HomeCorners": float(rng.poisson(5.5)), "AwayCorners": float(rng.poisson(4.5))})
    return pd.DataFrame(rows)


def _model() -> K.CornerBankoModel:
    df = pd.concat([_league(), _league(div="Y1", teams=("Red FC", "Blue United", "Green Town", "Gold City"), seed=2)])
    return K.CornerBankoModel.from_matches(df, "2026-06-01", dict(PARAMS))


def test_model_resolves_same_league_only_and_prices_valid_lines(monkeypatch):
    m = _model()
    assert m.resolve("Alpha", "Beta")[0] == "X1"
    assert m.resolve("Red", "Blue United")[0] == "Y1"            # yakın ad eşleşir
    assert m.resolve("Alpha", "Red FC") is None                   # farklı ligler: bacak yok
    assert m.resolve("Alpha", "Nobody Rovers") is None
    assert m.resolve("Alpha", "Alpha") is None
    p_over = m.probability("Alpha", "Beta", "Korner 8.5 Üst")
    assert 0.5 < p_over < 1
    assert m.probability("Alpha", "Beta", "Korner 12.5 Alt") > 0.7
    assert m.probability("Alpha", "Beta", "Korner 9.5 Üst") is None      # doğrulanmamış çizgi
    assert m.probability("Alpha", "Beta", "İY Korner 4.5 Üst") is None
    assert m.probability("Alpha", "Red FC", "Korner 8.5 Üst") is None


def test_model_uses_only_matches_before_asof():
    df = _league()
    late = df.MatchDate > pd.Timestamp("2025-01-01")
    df2 = df.copy()
    df2.loc[late, "HomeCorners"] = 40.0  # gelecek bozulur
    a = K.CornerBankoModel.from_matches(df, "2025-01-01", dict(PARAMS))
    b = K.CornerBankoModel.from_matches(df2, "2025-01-01", dict(PARAMS))
    assert a.expected_total("Alpha", "Beta") == b.expected_total("Alpha", "Beta")


def test_flag_off_blocks_pricing(monkeypatch):
    monkeypatch.setattr(K, "load_params", lambda path=None: dict(PARAMS))
    monkeypatch.setenv("QF_KORNER_BANKO", "0")
    assert not K.banko_enabled() and not K.banko_name_allowed("Korner 8.5 Üst")
    monkeypatch.setenv("QF_KORNER_BANKO", "1")
    assert K.banko_enabled() and K.banko_name_allowed("Korner 8.5 Üst") and not K.banko_name_allowed("Korner 9.5 Üst")


def test_walk_forward_totals_use_only_past_months():
    rng = np.random.default_rng(5)
    n = 4000
    dates = pd.Timestamp("2020-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 900, n)), unit="D")
    e = rng.uniform(8, 12, n)
    tot = rng.poisson(0.6 * e + 4.0).astype(float)
    df = pd.DataFrame({"MatchDate": dates, "ch_m": e * 0.55, "ca_m": e * 0.45, "HomeCorners": tot * 0.55, "AwayCorners": tot * 0.45})
    a1, v1, _ = kb.walk_forward_totals(df, "2020-03-01")
    df2 = df.copy()
    last = df2.MatchDate.dt.to_period("M") == df2.MatchDate.dt.to_period("M").max()
    df2.loc[last, ["HomeCorners", "AwayCorners"]] = 50.0
    a2, v2, _ = kb.walk_forward_totals(df2, "2020-03-01")
    assert np.allclose(a1, a2, equal_nan=True) and np.allclose(v1, v2, equal_nan=True)


def test_validated_requires_both_periods_and_sample_size():
    ok = {"n": 500, "tahmin": 0.75, "gercek": 0.74, "fark": -0.01, "z": 0.5}
    bad = {"n": 500, "tahmin": 0.75, "gercek": 0.60, "fark": -0.15, "z": -3.0}
    tiny = {"n": 20, "tahmin": 0.75, "gercek": 0.95, "fark": 0.20, "z": 2.0}
    res = {"secimler": {"A": {"doğrulama": ok, "test": ok}, "B": {"doğrulama": ok, "test": bad},
                        "C": {"doğrulama": tiny, "test": ok}}}
    good, why = kb.validated(res)
    assert good == ["A"] and set(why) == {"B", "C"}


def test_nesine_global_prices_corner_only_when_model_available(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    ng = importlib.import_module("nesine_global")
    monkeypatch.setattr(K, "load_params", lambda path=None: dict(PARAMS))
    monkeypatch.setenv("QF_KORNER_BANKO", "1")
    event = SimpleNamespace(home="Alpha", away="Beta")
    monkeypatch.setattr(K, "default_model", lambda: _model())
    assert 0.5 < ng._korner_model_probability(event, "Korner 8.5 Üst") < 1
    assert ng._korner_model_probability(event, "Korner 9.5 Üst") is None
    assert ng._korner_model_probability(SimpleNamespace(home="Alpha", away="Nobody"), "Korner 8.5 Üst") is None
    monkeypatch.setattr(K, "default_model", lambda: None)
    assert ng._korner_model_probability(event, "Korner 8.5 Üst") is None


def test_corner_leg_passes_direct_only_candidates(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    kupon = importlib.import_module("nesine_kupon")
    monkeypatch.setattr(K, "load_params", lambda path=None: dict(PARAMS))
    monkeypatch.setenv("QF_KORNER_BANKO", "1")
    now = dt.datetime(2026, 11, 28, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    sels = [
        {"market": "Korner", "selection": "8,5 Üst", "name": "Korner 8.5 Üst", "odds": 1.35, "fair_prob": 0.76, "ev": 0.026,
         "mbs": 1, "direct": False, "korner_modeli": True},
        {"market": "Alt/Üst", "selection": "Üst", "name": "1.5 Üst", "odds": 1.30, "fair_prob": 0.80, "ev": 0.04, "mbs": 1,
         "direct": False},   # model türevi gol bacağı direct_only'de elenir
    ]
    m = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-28T20:00:00+03:00",
         "kickoff": "2026-11-28 20:00", "code": 1, "league": "L", "home": "Alpha", "away": "Beta", "selections": sels}
    kw = {"min_odds": 1.2, "min_prob": 0.5, "allow_espn": False, "market_calibration": None, "direct_only": True}
    names = {x["name"] for pool in kupon.candidates([m], now, mode="banko", **kw) for x in pool}
    assert names == {"Korner 8.5 Üst"}
    leg = next(x for pool in kupon.candidates([m], now, mode="banko", **kw) for x in pool)
    assert leg["korner_modeli"] is True and leg["direct"] is False
    assert "korner modeli" in kupon.leg_reason({**leg, "reference": "x"})
