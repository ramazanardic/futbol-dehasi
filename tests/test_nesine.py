"""Nesine bulletin parsing and market translation (no network)."""

import datetime as dt

import numpy as np
import pytest

from quantfoot.data.nesine import load_market_definitions, market_overrounds, parse_bulletin, translate
from quantfoot.markets.goal_markets import goal_probability

DEFS = load_market_definitions()


@pytest.mark.parametrize(
    "mtid,outcome,sov,expected",
    [
        (1, 2, 0.0, ("MS 0", False)),
        (3, 3, 0.0, ("ÇŞ X2", False)),
        (5, 4, 0.0, ("İY/MS 0/1", False)),
        (12, 2, 2.5, ("2.5 Üst", False)),
        (14, 1, 1.5, ("İY 1.5 Alt", False)),
        (212, 2, 0.5, ("Ev 0.5 Üst", False)),
        (38, 1, 0.0, ("KG Var", False)),
        (43, 4, 0.0, ("6+ Gol", False)),
        (268, 1, -1.0, ("Hnd(-1) 1", False)),
        (414, 2, 0.0, ("MS 1 & KG Yok", False)),
        (343, 6, 0.0, ("MS 2 & 2.5 Üst", False)),
        (295, 2, 0.0, ("Ev İki Yarıda Gol", True)),
        (291, 2, 0.0, ("İlk Gol Yok", False)),
    ],
)
def test_translate_known_markets(mtid, outcome, sov, expected):
    assert translate(mtid, outcome, sov, DEFS) == expected


def test_every_translation_is_priceable():
    joint = np.ones((3, 3, 3, 3)) / 81
    for mtid, d in DEFS.items():
        for oc in d["outcomes"]:
            for sov in (0.0, 0.5, 1.5, 2.5, -1.0):
                tr = translate(mtid, oc, sov, DEFS)
                # corners are priced only from direct exchange quotes, never from the goal grid
                if tr and not tr[0].startswith("İlk Gol") and "Korner" not in tr[0]:
                    goal_probability(tr[0], joint)  # must not raise


def test_parse_minimal_payload():
    ts = int(dt.datetime(2026, 11, 19, 20, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
    payload = {"sg": {"EA": [{
        "C": 123, "HN": "Ev Takım", "AN": "Dep Takım", "TYPE": 1, "ESD": ts, "LC": 5,
        "MA": [{"MTID": 1, "MBS": 1, "SOV": 0.0, "OCA": [{"N": 1, "O": 2.0}, {"N": 2, "O": 3.2}, {"N": 3, "O": 3.6}]},
               {"MTID": 12, "MBS": 1, "SOV": 2.5, "OCA": [{"N": 1, "O": 1.8}, {"N": 2, "O": 1.9}]}],
    }], "LA": [{"LID": 5, "N": "Test Ligi"}]}}
    ev = parse_bulletin(payload)[0]
    assert ev.odds_of("MS 1") == 2.0 and ev.odds_of("2.5 Üst") == 1.9
    m = market_overrounds(payload)
    assert m["Maç Sonucu"]["margin"] == pytest.approx(1 / 2.0 + 1 / 3.2 + 1 / 3.6 - 1)
