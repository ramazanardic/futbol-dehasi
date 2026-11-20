"""Settlement must agree with pricing: every priced selection settles to exactly win or lose."""

import pytest

from quantfoot.evaluation.settlement import settle_selection
from quantfoot.markets.goal_markets import price_goal_markets
from quantfoot.markets.omni_markets import compute_omni_markets


@pytest.mark.parametrize(
    "sel,ht,ft,expected",
    [
        ("MS 1", (0, 0), (2, 1), True),
        ("İY/MS 0/1", (0, 0), (2, 1), True),
        ("İY/MS 2/1", (0, 1), (1, 1), False),
        ("2.5 Üst & KG Var", (1, 0), (2, 1), True),
        ("Ev İki Yarıda Gol", (1, 1), (2, 1), True),
        ("Ev İki Yarıda Gol", (2, 0), (2, 1), False),
        ("6+ Gol", (2, 2), (4, 2), True),
        ("İY 1.5 Üst", (1, 0), (3, 0), False),
        ("Dep Gol Yemeden Kazanır", (0, 0), (0, 2), True),
        ("Bilinmeyen Pazar", (0, 0), (0, 0), None),
    ],
)
def test_settle_examples(sel, ht, ft, expected):
    assert settle_selection(sel, ht, ft) is expected


def test_every_priced_market_settles():
    names = [n for fam in price_goal_markets(compute_omni_markets(1.5, 1.2).joint).values() for n in fam if "Diğer" not in n]
    for n in names:
        assert settle_selection(n, (1, 0), (2, 1)) in (True, False), n


def test_halftime_cannot_exceed_fulltime():
    with pytest.raises(ValueError):
        settle_selection("MS 1", (2, 0), (1, 0))


def test_first_goal_settles_when_the_scores_decide_it():
    from quantfoot.evaluation.settlement import settle_selection

    assert settle_selection("İlk Gol Ev", (1, 0), (2, 1)) is True  # only the home side scored before half time
    assert settle_selection("İlk Gol Dep", (0, 0), (0, 2)) is True
    assert settle_selection("İlk Gol Yok", (0, 0), (0, 0)) is True
    assert settle_selection("İlk Gol Ev", (1, 1), (1, 1)) is None  # both scored in the same half: order unknown
