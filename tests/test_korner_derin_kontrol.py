"""Korner bacakları derin kontrolde takımın GERÇEK korner geçmişiyle sınanır (28 Kas); veri yoksa elenir.
Ayrıca openfootball liste-skor koruması."""

from __future__ import annotations

import datetime as dt
import importlib
import sys
from pathlib import Path

import pandas as pd

from quantfoot.markets import korner_banko as K

ROOT = Path(__file__).resolve().parents[1]
PARAMS = {"etkin": True, "gecerli": ["Korner 8.5 Üst", "Korner 11.5 Alt"], "katsayi": [4.0, 0.6], "var_ort": 1.15}
ASOF = "2026-11-28"


def _games(corners_a: list[int], corners_b: list[int], n_filler: int = 200):
    """A ve B takımları aynı ligde; A'nın maçlarında toplam korner corners_a, B'ninkinde corners_b."""
    rows, d0 = [], pd.Timestamp("2026-08-01")
    for i, c in enumerate(corners_a):
        rows.append(("E0", d0 + pd.Timedelta(days=3 * i), "Alpha", f"Fill{i % 10}", c // 2, c - c // 2))
    for i, c in enumerate(corners_b):
        rows.append(("E0", d0 + pd.Timedelta(days=3 * i + 1), f"Fill{i % 10}", "Beta", c // 2, c - c // 2))
    for i in range(n_filler):
        rows.append(("E0", pd.Timestamp("2025-09-01") + pd.Timedelta(days=i), f"Fill{i % 10}", f"Fill{(i + 3) % 10}", 5, 5))
    return pd.DataFrame(rows, columns=["Division", "MatchDate", "HomeTeam", "AwayTeam", "HomeCorners", "AwayCorners"])


def _model(df):
    return K.CornerBankoModel.from_matches(df, ASOF, dict(PARAMS))


def test_team_corner_totals_uses_real_totals_and_only_past_games():
    df = _games([12, 8, 10], [9, 9, 9])
    assert K.team_corner_totals(df, "Alpha", "E0", ASOF) == [12.0, 8.0, 10.0]
    assert K.team_corner_totals(df, "Alpha", "E0", "2026-08-02") == [12.0]
    assert K.team_corner_totals(df, "Alpha", "T1", ASOF) == []  # başka lig


def test_leg_history_rates_follow_real_corner_totals():
    df = _games([8, 9, 10, 9, 8, 9, 10, 8], [9, 8, 9, 10, 9, 8, 9, 10])
    h = K.leg_history(_model(df), df, "Alpha", "Beta", "Korner 11.5 Alt", ASOF)
    assert h["home_n"] == 8 and h["away_n"] == 8
    assert h["home_rate"] == 1.0 and h["away_rate"] == 1.0 and h["mean"] == 1.0
    h = K.leg_history(_model(df), df, "Alpha", "Beta", "Korner 8.5 Üst", ASOF)
    assert 0.0 < h["home_rate"] < 1.0
    assert abs(h["home_rate"] - 5 / 8) < 1e-9


def test_leg_history_none_when_unresolved_or_not_a_corner_leg():
    df = _games([8] * 8, [8] * 8)
    m = _model(df)
    assert K.leg_history(m, df, "Alpha", "Yok Takım", "Korner 11.5 Alt", ASOF) is None
    assert K.leg_history(m, df, "Alpha", "Beta", "2,5 Alt", ASOF) is None
    assert K.leg_history(m, df, "Alpha", "Beta", "İY Korner 4.5 Üst", ASOF) is None


def _kupon_kur():
    sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module("kupon_kur")


def _install(kk, df):
    kk._CORNER_STATE.clear()
    kk._CORNER_STATE.update({"model": _model(df), "df": df})


def _row():
    return {"legs": [{"verdict": "geçmiş yetersiz"}]}


def _match():
    return {"home": "Alpha", "away": "Beta", "kickoff_iso": f"{ASOF}T18:00:00+03:00"}


def _leg(name="Korner 11.5 Alt", p=0.72):
    return {"name": name, "p": p, "market": "Korner Alt/Üst", "selection": name}


def test_corner_leg_supported_by_real_history_is_not_dropped():
    kk = _kupon_kur()
    _install(kk, _games([8, 9, 10, 9, 8, 9, 10, 8], [9, 8, 9, 10, 9, 8, 9, 10]))
    row = _row()
    assert kk.corner_research(row, _match(), _leg()) is True
    assert row["legs"][0]["verdict"].startswith("✓")


def test_corner_leg_contradicted_by_history_is_rejected():
    kk = _kupon_kur()
    _install(kk, _games([14, 15, 13, 14, 16, 13, 14, 15], [13, 14, 15, 13, 14, 16, 14, 13]))
    row = _row()
    kk.corner_research(row, _match(), _leg(p=0.72))
    assert row["legs"][0]["verdict"].startswith("⚠")


def test_corner_leg_without_enough_corner_data_is_dropped():
    kk = _kupon_kur()
    _install(kk, _games([8, 9, 10], [9, 8, 9]))  # takım başına 3 maç < 6
    row = _row()
    kk.corner_research(row, _match(), _leg())
    assert row["legs"][0]["verdict"] == "geçmiş yetersiz"


def test_corner_leg_with_unresolved_team_is_dropped():
    kk = _kupon_kur()
    _install(kk, _games([8] * 8, [8] * 8))
    row = _row()
    m = dict(_match(), away="Hiç Yok FC")
    kk.corner_research(row, m, _leg())
    assert row["legs"][0]["verdict"] == "geçmiş yetersiz"


def test_non_corner_leg_is_left_to_goal_history():
    kk = _kupon_kur()
    _install(kk, _games([8] * 8, [8] * 8))
    row = _row()
    assert kk.corner_research(row, _match(), _leg(name="2,5 Alt")) is False
    assert row["legs"][0]["verdict"] == "geçmiş yetersiz"


def test_openfootball_played_ignores_list_scores():
    sys.path.insert(0, str(ROOT / "scripts"))
    of = importlib.import_module("openfootball_gecmis")
    games = [
        {"date": "2026-11-01", "score": [1, 0]},                                   # liste: atlanır, çökmez
        {"date": "2026-11-02", "score": {"ft": [2, 1], "ht": [1, 0]}},
        {"date": "2026-11-03", "score": None},
        {"date": "2026-12-05", "score": {"ft": [0, 0], "ht": [0, 0]}},            # gelecek
    ]
    out = of.played(games, dt.date(2026, 11, 28))
    assert [g["date"] for g in out] == ["2026-11-02"]
