"""'İki Yarıda KG Var' olasılığı: durumdan bağımsız 2. yarıda P = P(İY KG) × P(2Y KG); durum etkisinde sınırlar korunur."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from iki_yari_kg_arastirma import both_from_matrices  # noqa: E402
from quantfoot.markets import yuksek_oran_modeli as ym  # noqa: E402


def _gs(lam, mu, mult):
    lam, mu = np.array([lam]), np.array([mu])
    m1 = ym.dc_matrix(lam * 0.45, mu * 0.45, 0.0)
    ones = np.full((1, 3), mult)
    return m1, ym.game_state_model(m1, lam * 0.55, mu * 0.55, ones, ones, 0.0)


def test_independent_when_no_game_state_effect():
    m1, gs = _gs(1.6, 1.2, 1.0)
    both, kg1 = both_from_matrices(m1, gs)
    assert abs(both[0] - kg1[0] * gs["kg2"][0]) < 1e-9


def test_bounded_by_each_half():
    m1, gs = _gs(2.0, 1.5, 1.05)
    both, kg1 = both_from_matrices(m1, gs)
    assert 0 < both[0] < min(kg1[0], gs["kg2"][0])
    assert both[0] < 0.2          # iki yarıda KG nadir bir olay
