"""21 Nov bet-family audit: math regressions found while pricing every Nesine market family."""

from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from quantfoot.data.nesine import load_market_definitions, translate
from quantfoot.markets.bet_builder import goal_order_share, price_bet_builder
from quantfoot.markets.devig import devig
from quantfoot.markets.goal_markets import GoalGrid, asian_handicap, asian_total, goal_probability
from quantfoot.markets.market_calibration import calibrate_market_probability
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.pricing import over_under_probability, settle_asian_handicap
from quantfoot.markets.tail_goals import (
    fit_tail_rates_from_markets,
    matrix_1x2,
    matrix_over_probability,
    negative_binomial_score_matrix,
    rake_score_matrix_to_markets,
)


def _ft(joint: np.ndarray) -> np.ndarray:
    g = joint.shape[0]
    ft = np.zeros((2 * g - 1, 2 * g - 1))
    for a in range(g):
        for b in range(g):
            ft[a: a + g, b: b + g] += joint[a, b]
    return ft


def test_over_under_whole_line_excludes_push():
    mat = negative_binomial_score_matrix(1.5, 1.1, alpha_nb=0.0, shared_kappa=0.0)
    tot = np.add.outer(np.arange(mat.shape[0]), np.arange(mat.shape[1]))
    p_over, p_under = over_under_probability(mat, 2.0)
    assert p_over == pytest.approx(mat[tot > 2].sum())
    assert p_under == pytest.approx(mat[tot < 2].sum())       # was 1 - P(over): the push counted as an under win
    assert p_over + p_under == pytest.approx(1.0 - mat[tot == 2].sum())
    o, u = over_under_probability(mat, 2.5)                     # half line: still complementary
    assert o + u == pytest.approx(1.0)


def test_omni_half_btts_reads_the_priced_joint():
    b = compute_omni_markets(1.6, 1.1, league="e0")
    j = b.joint
    assert b.btts["1. Yarı KG Var"] == pytest.approx(goal_probability("İY KG Var", j), abs=6e-5)
    assert b.btts["2. Yarı KG Var"] == pytest.approx(goal_probability("2Y KG Var", j), abs=6e-5)
    assert b.btts["1Y ve 2Y KG Var"] == pytest.approx(goal_probability("İki Yarıda KG Var", j), abs=6e-5)
    either = goal_probability("İY KG Var", j) + goal_probability("2Y KG Var", j) - goal_probability("İki Yarıda KG Var", j)
    assert b.btts["En Az Bir Devre KG Var"] == pytest.approx(either, abs=1e-4)


def _one_hot(h1: int, a1: int, h2: int, a2: int, g: int = 8) -> np.ndarray:
    j = np.zeros((g, g, g, g))
    j[h1, a1, h2, a2] = 1.0
    return j


def test_first_goal_follows_the_half_order():
    g = GoalGrid(_one_hot(0, 1, 2, 0))          # 1H 0-1, then 2H 2-0: the away side scored first
    assert goal_order_share(g, "İlk", "Ev")[g.p > 0][0] == 0.0
    assert goal_order_share(g, "İlk", "Dep")[g.p > 0][0] == 1.0
    assert goal_order_share(g, "Son", "Ev")[g.p > 0][0] == 1.0
    g2 = GoalGrid(_one_hot(1, 1, 0, 0))         # all goals in the 1H: last goal is a 1H goal (exchangeable, 1/2)
    assert goal_order_share(g2, "Son", "Ev")[g2.p > 0][0] == 0.5
    q = price_bet_builder(["İlk Gol Ev"], _one_hot(0, 1, 2, 0))
    assert q.probability == pytest.approx(0.0)  # full-time h/(h+a) gave 2/3


def test_first_goal_combination_on_a_real_joint_is_consistent():
    j = compute_omni_markets(1.5, 1.2, league="e0").joint
    p_first_home = price_bet_builder(["İlk Gol Ev"], j).probability
    p_first_away = price_bet_builder(["İlk Gol Dep"], j).probability
    assert p_first_home + p_first_away == pytest.approx(1.0 - goal_probability("Skor 0-0", j), abs=1e-9)
    # first goal home AND away leading at half-time needs a 1H with away goals ≥ 2 more often than not -> small
    both = price_bet_builder(["İlk Gol Ev", "İY 2"], j).probability
    assert both < 0.35 * goal_probability("İY 2", j)


@pytest.mark.parametrize("line", [-2.0, -1.75, -1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25])
def test_asian_handicap_outcome_matches_per_score_settlement(line):
    j = compute_omni_markets(1.7, 1.0, league="e0").joint
    ft = _ft(j / j.sum())
    for side, sign in (("Ev", 1), ("Dep", -1)):
        o = asian_handicap(j, line, side)  # `line` is the handicap of `side` itself
        brute = sum(ft[h, a] * settle_asian_handicap(sign * (h - a), line, 1.9, is_home=True)
                    for h in range(ft.shape[0]) for a in range(ft.shape[1]))
        assert o.ev(1.9) == pytest.approx(brute, abs=1e-9), side
        # pricing.settle_asian_handicap's away convention (line = HOME handicap) must agree with goal_markets
        brute_away = sum(ft[h, a] * settle_asian_handicap(h - a, -line, 1.9, is_home=False)
                         for h in range(ft.shape[0]) for a in range(ft.shape[1]))
        if side == "Dep":
            assert o.ev(1.9) == pytest.approx(brute_away, abs=1e-9)


@pytest.mark.parametrize("line", [1.75, 2.0, 2.25, 2.5, 2.75, 3.0])
def test_asian_total_over_under_are_mirror_images(line):
    j = compute_omni_markets(1.4, 1.2, league="e0").joint
    ft = _ft(j / j.sum())
    tot = np.add.outer(np.arange(ft.shape[0]), np.arange(ft.shape[1]))
    over, under = asian_total(j, line, "Üst"), asian_total(j, line, "Alt")
    assert over.win == pytest.approx(under.lose, abs=1e-12)
    assert over.half_win == pytest.approx(under.half_lose, abs=1e-12)
    assert over.push == pytest.approx(under.push, abs=1e-12)
    if line % 1 == 0:
        assert over.push == pytest.approx(ft[tot == line].sum(), abs=1e-12)
    if line % 1 == 0.25:  # 2.25 over: total 2 loses half
        assert over.half_lose == pytest.approx(ft[tot == int(line)].sum(), abs=1e-12)


def test_raking_reproduces_the_quotes_exactly():
    p1x2 = devig([2.10, 3.40, 3.60]).probabilities
    p_ov = float(devig([1.90, 1.95]).probabilities[0])
    _, _, mat = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15), alpha_nb=0.0,
                                            shared_kappa=0.0, com_nu=1.0, fund_weight=0.0)
    assert abs(matrix_1x2(mat)[1] - p1x2[1]) > 0.005        # the 2-parameter fit misses the draw
    r = rake_score_matrix_to_markets(mat, p_1x2=p1x2, ou_lines=[(2.5, p_ov), (3.0, 0.3)], p_btts=0.52)
    assert matrix_1x2(r) == pytest.approx(p1x2, abs=1e-8)
    assert matrix_over_probability(r, 2.5) == pytest.approx(p_ov, abs=1e-8)
    assert float(r[1:, 1:].sum()) == pytest.approx(0.52, abs=1e-6)
    assert r.sum() == pytest.approx(1.0)
    r2 = rake_score_matrix_to_markets(mat, p_1x2=p1x2, ou_lines=[(2.5, p_ov)])
    assert r2[1, 1] > mat[1, 1] and r2[2, 2] > mat[2, 2]       # the missing draw mass lands on the diagonal
    # already consistent -> unchanged
    same = rake_score_matrix_to_markets(r, p_1x2=matrix_1x2(r), ou_lines=[(2.5, matrix_over_probability(r, 2.5))])
    assert np.allclose(same, r, atol=1e-9)


def test_raked_joint_keeps_ft_and_ht_margins():
    p1x2 = devig([1.55, 4.2, 6.0]).probabilities
    p_ov = float(devig([1.75, 2.10]).probabilities[0])
    mu_h, mu_a, mat = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15),
                                                  alpha_nb=0.0, shared_kappa=0.0, com_nu=1.0, fund_weight=0.0)
    r = rake_score_matrix_to_markets(mat, p_1x2=p1x2, ou_lines=[(2.5, p_ov)])
    j = compute_omni_markets(mu_h, mu_a, league="e0", ft_matrix=r).joint
    assert goal_probability("MS 0", j) == pytest.approx(p1x2[1], abs=2e-4)
    assert goal_probability("2.5 Üst", j) == pytest.approx(p_ov, abs=2e-4)


def test_nesine_handicap_sov_is_the_home_teams_head_start():
    defs = load_market_definitions()
    # 21 Nov bulletin: L. Zagreb (4.25) - Hajduk (1.41), MTID 268 SOV +1 -> '1' at 1.89 = home wins or draws
    assert translate(268, 1, 1.0, defs) == ("Hnd(+1) 1", False)
    assert translate(268, 3, -1.0, defs) == ("Hnd(-1) 2", False)
    j = compute_omni_markets(0.9, 1.7, league="e0").joint
    assert goal_probability("Hnd(+1) 1", j) == pytest.approx(goal_probability("ÇŞ 1X", j), abs=1e-12)


def test_market_calibration_complements_cover_every_binary_pair():
    curve = {"a": 0.2, "b": 1.0, "n": 1}
    cal = {"markets": {"4.5 Üst": curve, "İY KG Var": curve, "Tek": curve, "Ev İki Yarıda Gol": curve}}
    for pos, neg, p in (("4.5 Üst", "4.5 Alt", 0.2), ("İY KG Var", "İY KG Yok", 0.3), ("Tek", "Çift", 0.5)):
        up = calibrate_market_probability(pos, p, None, cal)
        assert up != p
        assert calibrate_market_probability(neg, 1 - p, None, cal) == pytest.approx(1 - up, abs=1e-12)
    # Nesine 'Atamaz' outcomes are priced as DEĞİL(event): calibrated as the complement of the event's curve
    up = calibrate_market_probability("Ev İki Yarıda Gol", 0.3, None, cal)
    assert calibrate_market_probability("DEĞİL(Ev İki Yarıda Gol)", 0.7, None, cal) == pytest.approx(1 - up, abs=1e-12)
    assert calibrate_market_probability("MS 1 & 2.5 Alt", 0.2, None, cal) == 0.2   # no curve, no complement


# --- bet-family classification and per-family value rules (21 Nov audit) -------------------------------------------

@pytest.mark.parametrize("name,fam", [
    ("MS 1", "Maç Sonucu"), ("ÇŞ 1X", "Çifte Şans"), ("2.5 Üst", "Alt/Üst"), ("KG Var", "Karşılıklı Gol"),
    ("İY 1", "İY Sonucu"), ("İY 1.5 Alt", "İY Alt/Üst"), ("2Y 0", "2Y Sonucu"), ("2Y 0.5 Üst", "2Y Alt/Üst"),
    ("İY/MS 1/1", "İY/MS"), ("Hnd(-1) 1", "Handikap"), ("Fark Ev 2", "Fark"), ("2-3 Gol", "Toplam Gol Aralığı"),
    ("6+ Gol", "Toplam Gol Aralığı"), ("Tek", "Tek/Çift"), ("İY Çift", "Tek/Çift"), ("Skor 1-1", "Doğru Skor"),
    ("İY Skor 0-0 & Skor 1-0", "Doğru Skor"), ("İY KG Var & 2Y KG Yok", "Yarı KG"), ("2Y KG Var", "Yarı KG"),
    ("İki Yarıda KG Var", "Yarı KG"), ("En Çok Gol İY", "Yarı Özel"), ("Ev Her İki Yarıyı Kazanır", "Yarı Özel"),
    ("Ev 1.5 Üst", "Takım Golleri"), ("İlk Gol Ev", "İlk Gol"), ("Son Gol Dep", "İlk Gol"),
    ("MS 1 & 2.5 Üst", "Kombine"), ("DEĞİL(KG Var)", "Karşılıklı Gol"), ("Korner 9.5 Üst", "Korner"),
    ("Kart 4.5 Üst", "Kart"), ("", "Diğer"),
])
def test_bet_family(name, fam):
    from quantfoot.markets.families import bet_family
    assert bet_family(name) == fam


def test_every_family_has_a_rule_and_hard_floor_wins():
    from quantfoot.markets.families import bet_family, leg_min_ev
    from quantfoot.settings import FAMILY_VALUE_RULES, HARD_MARKET_MIN_EV
    assert set(FAMILY_VALUE_RULES) >= {"Maç Sonucu", "Doğru Skor", "Korner", "Diğer"}
    for v in FAMILY_VALUE_RULES.values():
        assert 0.0 < v[0] <= 0.10 and 0.0 <= v[1] <= 0.02
    assert leg_min_ev("ÇŞ 1X", hard=True) == max(FAMILY_VALUE_RULES["Çifte Şans"][0], HARD_MARKET_MIN_EV)
    assert leg_min_ev("Skor 1-0", hard=True) == FAMILY_VALUE_RULES["Doğru Skor"][0]
    assert bet_family("Ne ki bu") == "Diğer"


@pytest.mark.parametrize("name,fam", [
    ("En Çok Gol İY", "Yarı özel"), ("Ev Her İki Yarıyı Kazanır", "Yarı özel"), ("Skor 1-0", "Doğru skor"),
    ("İY Skor 0-0", "Doğru skor"), ("Fark Ev 1", "Handikap"), ("İki Yarıda KG Var", "Yarı karşılıklı gol"),
    ("Son Gol Ev", "İlk gol"), ("Ev 1.5 Üst", "Ev sahibi golleri"), ("2-3 Gol", "Gol aralığı"), ("MS 1", "Maç sonucu"),
])
def test_auto_learn_market_family_fixed(name, fam):
    from quantfoot.evaluation.auto_learn import market_family
    assert market_family(name) == fam


def test_choose_applies_family_floor():
    import importlib
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    dt_ = importlib.import_module("derin_tahmin")
    legs = [{"name": "Skor 1-0", "verdict": "✓", "odds": 7.0, "p": 0.15},       # EV 0.05 < Doğru Skor floor
            {"name": "MS 1", "verdict": "✓", "odds": 2.0, "p": 0.52}]           # EV 0.04 >= MS floor
    assert dt_.choose(legs)["name"] == "MS 1"
    assert dt_.choose(legs, min_ev=0.0)["name"] == "Skor 1-0"


def test_candidates_family_floor_only_on_derived_legs():
    import datetime as dt
    import importlib
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    kupon = importlib.import_module("nesine_kupon")
    now = dt.datetime(2026, 11, 19, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    sels = [
        {"market": "ÇŞ", "selection": "1-X", "name": "ÇŞ 1X", "odds": 1.30, "fair_prob": 0.78, "ev": 0.014, "mbs": 1,
         "direct": True},  # direct, EV 1.4 % < Çifte Şans floor: direct legs keep the PR #3 rule
        {"market": "Gol Aralığı", "selection": "2-3 Gol", "name": "2-3 Gol", "odds": 1.85, "fair_prob": 0.56, "ev": 0.036,
         "mbs": 1, "direct": False},   # derived, EV 3.6 % < Toplam Gol Aralığı floor 4 %
        {"market": "Ev Alt/Üst", "selection": "Üst", "name": "Ev 0.5 Üst", "odds": 1.55, "fair_prob": 0.70, "ev": 0.085,
         "mbs": 1, "direct": False},   # derived, EV 8 % >= floor
    ]
    m = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-19T20:00:00+03:00",
         "kickoff": "2026-11-19 20:00", "code": 1, "league": "L", "home": "A", "away": "B", "selections": sels}
    kw = dict(min_odds=1.2, min_prob=0.5, allow_espn=False, market_calibration=None)
    names = {x["name"] for pool in kupon.candidates([m], now, **kw) for x in pool}
    assert "2-3 Gol" not in names and "ÇŞ 1X" in names
    names_off = {x["name"] for pool in kupon.candidates([m], now, family_ev=False, **kw) for x in pool}
    assert "2-3 Gol" in names_off
