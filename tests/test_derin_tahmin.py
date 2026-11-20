"""scripts/derin_tahmin.py and scripts/wiki_gecmis.py (deep-researched daily picks, Wikipedia season history)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_candidates_direct_only_and_thresholds():
    dt_ = _load("derin_tahmin")
    sel = lambda n, p, o, d=True: {"name": n, "market": "M", "selection": n, "fair_prob": p, "odds": o, "direct": d}  # noqa: E731
    m = {"selections": [sel("a", 0.70, 1.30), sel("b", 0.80, 1.15), sel("c", 0.75, 1.40, False), sel("d", 0.54, 1.80),
                        sel("e", 0.60, 1.50)]}
    assert [c["name"] for c in dt_.candidates(m, 5)] == ["a", "e"]   # odds < 1.20, model-derived and p < 55 % left out


def test_choose_skips_warned_legs():
    dt_ = _load("derin_tahmin")
    legs = [{"p": 0.7, "verdict": "⚠ geçmiş desteklemiyor"}, {"p": 0.6, "verdict": "geçmiş yetersiz"},
            {"p": 0.65, "verdict": "✓ geçmiş destekliyor"}]
    assert dt_.choose(legs)["p"] == 0.65
    assert dt_.choose([legs[0]]) is None


def test_results_matrix_and_crosstable():
    wg = _load("wiki_gecmis")
    en = "|name_ABC = [[Alpha FC]]\n|name_DEF = [[Delta United|Delta]]\n|match_ABC_DEF = 2–1\n|match_DEF_ABC = [[x|0–0]]\n|match_ABC_XYZ = \n"
    names, games = wg.results_matrix(en)
    assert names == {"ABC": "Alpha FC", "DEF": "Delta"}
    assert games == [("ABC", "DEF", 2, 1), ("DEF", "ABC", 0, 0)]
    de = ("=== Kreuztabelle ===\n{| class=\"wikitable\"\n|-\n! 2026/27\n! [[Datei:a.svg|22px|Alpha]]\n! [[Datei:b.svg|22px|Beta]]\n"
          "|-\n| style=\"text-align: left;\" | [[Alpha]]\n| class=\"h\" | || 3:1\n"
          "|-\n| style=\"text-align: left;\" | [[Beta]]\n| : || class=\"h\" |\n|}")
    names, games = wg.crosstable(de)
    assert names == {"0": "Alpha", "1": "Beta"} and games == [("0", "1", 3, 1)]   # unplayed ":" cells skipped


def test_match_team_alias_and_fuzzy():
    wg = _load("wiki_gecmis")
    names = {"A": "SK Rapid II", "B": "Austria Wien II", "C": "Auckland City", "D": "Lokomotiv Plovdiv"}
    assert wg.match_team("R. Wien (Amt)", names) == "A"      # alias beats the fuzzy match
    assert wg.match_team("Auckland", names) is None          # alias None: never guess
    assert wg.match_team("Loko Plovdiv", names) == "D"
    assert wg.match_team("Completely Different", names) is None


def test_wiki_leg_history_full_time_only():
    wg = _load("wiki_gecmis")
    names = {"H": "Home", "A": "Away", "X": "Other"}
    games = [("H", "X", 2, 0), ("H", "X", 0, 1), ("X", "A", 1, 1), ("X", "A", 3, 0), ("A", "X", 5, 5)]
    hg, ag = wg.team_games("H", names, games), wg.team_games("A", names, games)
    hist = wg.leg_history("2.5 Alt", hg, ag)     # home team's home games, away team's away games only
    assert (hist["home_n"], hist["away_n"]) == (2, 2) and hist["home_rate"] == 1.0 and hist["away_rate"] == 0.5
    assert wg.leg_history("İY 0.5 Üst", hg, ag)["mean"] is None   # no half-time scores on Wikipedia
    assert wg.verdict(0.7, hist) == "geçmiş yetersiz"        # fewer than 4 home / 4 away games
