"""Coherence tests for the full market book (20 families) and the Bet Builder."""

import numpy as np
import pytest

from quantfoot.markets.bet_builder import price_bet_builder
from quantfoot.markets.corners_cards import CardDistribution, CornerCardRatings, CornerDistribution
from quantfoot.markets.goal_markets import (
    asian_handicap,
    asian_total,
    draw_no_bet,
    goal_probability,
    price_asian_markets,
    price_goal_markets,
)
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets.market_book import build_market_book
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.player_markets import PlayerProfile, price_player_markets, team_goal_pmf

CASES = [(1.6, 1.1, "e0"), (2.6, 0.6, "fifa.friendly"), (0.9, 1.4, None), (3.1, 0.4, "u21")]


@pytest.fixture(scope="module", params=CASES, ids=lambda c: f"{c[0]}-{c[1]}-{c[2]}")
def bundle(request):
    return compute_omni_markets(*request.param[:2], league=request.param[2])


@pytest.fixture(scope="module")
def goals(bundle):
    return price_goal_markets(bundle.joint)


def test_joint_matches_published_margins(bundle):
    j = bundle.joint
    i1, j1, i2, j2 = np.indices(j.shape)
    p_home = float(j[(i1 + i2) > (j1 + j2)].sum())
    assert p_home == pytest.approx(bundle.ft_1x2["1"], abs=1e-3)
    assert float(j[i1 > j1].sum()) == pytest.approx(bundle.ht_1x2["İY 1"], abs=1e-3)
    assert bundle.exp_1h_total + bundle.exp_2h_total == pytest.approx(bundle.expected_total, abs=2e-3)


def test_partitions_sum_to_one(goals):
    for fam in ("Maç Sonucu", "Doğru Skor", "İY/MS", "En Çok Gol Olan Yarı"):
        assert sum(goals[fam].values()) == pytest.approx(1.0, abs=1e-9)
    ht_scores = {k: v for k, v in goals["İlk Yarı"].items() if k.startswith("İY Skor")}
    assert sum(ht_scores.values()) == pytest.approx(1.0, abs=1e-9)
    assert goals["Tek/Çift"]["Tek"] + goals["Tek/Çift"]["Çift"] == pytest.approx(1.0)
    for h in (-3, -2, -1, 1, 2, 3):
        trio = [goals["Avrupa Handikabı"][f"Hnd({h:+d}) {r}"] for r in "102"]
        assert sum(trio) == pytest.approx(1.0)


def test_cross_market_identities(bundle, goals):
    j = bundle.joint
    ms = goals["Maç Sonucu"]
    # European handicap -1 home win = home wins by 2+ = Asian -1.5 home win.
    assert goals["Avrupa Handikabı"]["Hnd(-1) 1"] == pytest.approx(asian_handicap(j, -1.5, "Ev").win)
    # Draw-no-bet = Asian 0; fair odds = (1 - P(draw)) / P(home win).
    dnb = draw_no_bet(j, "Ev")
    assert dnb.push == pytest.approx(ms["MS 0"])
    assert dnb.fair_odds == pytest.approx((1 - ms["MS 0"]) / ms["MS 1"])
    assert asian_total(j, 2.5, "Üst").win == pytest.approx(goals["Alt/Üst"]["2.5 Üst"])
    tg = goals["Takım Golleri"]
    assert tg["Ev Gol Yemeden Kazanır"] == pytest.approx(goal_probability("MS 1 & Dep 0.5 Alt", j))
    assert tg["Ev Gol Atar"] == pytest.approx(tg["Ev 0.5 Üst"])
    assert goals["Toplam Gol Aralığı"]["6+ Gol"] == pytest.approx(goals["Alt/Üst"]["5.5 Üst"])


def test_combos_bounded_by_legs(goals):
    flat = {k: v for fam in goals.values() for k, v in fam.items()}
    for name, p in goals["Kombine"].items():
        for leg in name.split(" & "):
            assert p <= flat[leg] + 1e-12, name


@pytest.mark.parametrize("q", range(-12, 13))
def test_asian_fair_odds_have_zero_ev(bundle, q):
    for side in ("Ev", "Dep"):
        o = asian_handicap(bundle.joint, q / 4, side)
        if np.isfinite(o.fair_odds):
            assert o.ev(o.fair_odds) == pytest.approx(0.0, abs=1e-9)
    t = asian_total(bundle.joint, 2.5 + q / 8, "Üst") if q % 2 == 0 else None
    if t is not None and np.isfinite(t.fair_odds):
        assert t.ev(t.fair_odds) == pytest.approx(0.0, abs=1e-9)


def test_goal_timing_coherent(bundle, goals):
    t = GoalTimingModel.from_joint(bundle.joint)
    mk = t.markets()
    assert t.p_no_goal == pytest.approx(goals["Doğru Skor"]["Skor 0-0"])
    assert sum(mk["İlk Golü Atan Takım"].values()) == pytest.approx(1.0)
    assert sum(mk["İlk Gol Dakikası"].values()) == pytest.approx(1.0)
    assert sum(mk["Son Gol Dakikası"].values()) == pytest.approx(1.0)
    # No goal in the first half agrees with the İY 0.5 Alt market.
    assert 1 - t.p_goal_between(0, 45) == pytest.approx(goals["İlk Yarı"]["İY 0.5 Alt"], abs=1e-9)


def test_player_props_consistent(bundle):
    j = bundle.joint
    p_team = 1 - team_goal_pmf(j, "Ev")[0]
    solo = PlayerProfile("Tek", "Ev", goal_share=1.0, minutes=90)
    pm = price_player_markets(j, [solo])["Tek"]
    assert pm["Gol Atar"] == pytest.approx(p_team)
    split = [PlayerProfile(f"P{i}", "Ev", goal_share=0.25) for i in range(4)]
    firsts = price_player_markets(j, split)
    timing = GoalTimingModel.from_joint(j)
    assert sum(r["İlk Golü Atar"] for r in firsts.values()) == pytest.approx(timing.markets()["İlk Golü Atan Takım"]["İlk Gol Ev"])
    sub = price_player_markets(j, [PlayerProfile("Yedek", "Ev", goal_share=0.3, minutes=30, starter=False)])["Yedek"]
    assert 0 < sub["Gol Atar"] < pm["Gol Atar"]
    assert sub["2+ Gol"] <= sub["Gol Atar"]


def test_corner_model_matches_inputs_and_negative_correlation():
    c = CornerDistribution.from_expectations(6.0, 4.0, "E0")
    eh, ea = c.expected()
    assert (eh, ea) == pytest.approx((6.0, 4.0), abs=0.01)
    h, a = np.indices(c.pmf.shape)
    cov = float((h * a * c.pmf).sum() - eh * ea)
    assert cov < 0
    mk = c.markets()
    for ln in (8.5, 9.5, 10.5):
        assert mk["Toplam Korner"][f"Korner {ln} Üst"] + mk["Toplam Korner"][f"Korner {ln} Alt"] == pytest.approx(1.0)
    assert sum(mk["En Çok Korner"].values()) == pytest.approx(1.0)
    assert sum(mk["İlk Korner"].values()) == pytest.approx(1.0)


def test_card_model_markets():
    k = CardDistribution.for_division("T1")
    mk = k.markets()
    assert mk["Kırmızı Kart"]["Kırmızı Kart Var"] + mk["Kırmızı Kart"]["Kırmızı Kart Yok"] == pytest.approx(1.0)
    assert sum(mk["En Çok Kart"].values()) == pytest.approx(1.0)
    pts = [mk["Kart Puanı"][f"Kart Puanı {ln} Üst"] for ln in (15.5, 25.5, 35.5, 45.5)]
    assert pts == sorted(pts, reverse=True)


def test_bet_builder_agrees_with_single_markets(bundle, goals):
    j = bundle.joint
    q = price_bet_builder(["MS 1", "2.5 Üst"], j)
    assert q.probability == pytest.approx(goals["Kombine"]["MS 1 & 2.5 Üst"])
    assert price_bet_builder(["KG Var"], j).probability == pytest.approx(goals["Karşılıklı Gol"]["KG Var"])
    pl = {"A": PlayerProfile("A", "Ev", goal_share=0.35, minutes=80)}
    single = price_bet_builder(["A: Gol Atar"], j, players=pl).probability
    assert single == pytest.approx(price_player_markets(j, list(pl.values()))["A"]["Gol Atar"])
    # A home scorer is positively correlated with a home win, negatively with an away win.
    assert price_bet_builder(["MS 1", "A: Gol Atar"], j, players=pl).correlation_ratio > 1
    assert price_bet_builder(["MS 2", "A: Gol Atar"], j, players=pl).correlation_ratio < 1
    c = CornerDistribution.from_expectations(5.5, 4.5)
    cross = price_bet_builder(["MS 1", "Korner 9.5 Üst"], j, corners=c)
    assert cross.probability == pytest.approx(goals["Maç Sonucu"]["MS 1"] * c.prob("Korner 9.5 Üst"))
    with pytest.raises(KeyError):
        price_bet_builder(["Uydurma Pazar"], j)


def test_market_book_has_all_families():
    book = build_market_book(1.7, 1.0, league="eng.1", division="E0",
                             players=[PlayerProfile("A", "Ev", goal_share=0.3, shots_p90=3.0, yellow_p90=0.15)])
    numbered = {k.split(".")[0] for k in book if k[0].isdigit()}
    assert {str(i) for i in range(1, 21)} <= numbered
    assert set(price_asian_markets(book["_modeller"]["joint"])) == {"Asya Handikabı", "Asya Alt/Üst", "Beraberlikte İade"}


def test_corner_card_ratings_learn_team_effects():
    r = CornerCardRatings()
    for _ in range(60):
        r.update("Güçlü", "Zayıf", "E0", hc=9, ac=2, hy=1, ay=3)
    e = r.expected("Güçlü", "Zayıf", "E0")
    assert e["corners_home"] > 7 and e["corners_away"] < 3.5
    assert e["yellow_away"] > e["yellow_home"]
