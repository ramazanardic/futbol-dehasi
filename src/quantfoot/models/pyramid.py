"""Cross-division football pyramid constants and promotion/relegation regression helpers."""

from __future__ import annotations

import math

PYRAMID_DIVISIONS: tuple[str, ...] = (
    "E0", "E1", "E2", "E3", "EC",
    "SP1", "SP2",
    "D1", "D2",
    "I1", "I2",
    "F1", "F2",
    "T1", "N1", "P1",
)

# Structural division tier priors (pre-sample hierarchy offsets preventing naive feeder-league inflation).
TIER_ELO_CENTERS: dict[str, float] = {
    "E0": 1710.0,
    "E1": 1525.0,
    "E2": 1410.0,
    "E3": 1330.0,
    "EC": 1270.0,
    "SP1": 1685.0,
    "SP2": 1495.0,
    "D1": 1680.0,
    "D2": 1500.0,
    "I1": 1675.0,
    "I2": 1485.0,
    "F1": 1665.0,
    "F2": 1480.0,
    "P1": 1575.0,
    "N1": 1575.0,
    "T1": 1560.0,
}

TIER_ATTACK_SHIFT: dict[str, float] = {
    "E0": 0.22,
    "E1": -0.02,
    "E2": -0.18,
    "E3": -0.30,
    "EC": -0.40,
    "SP1": 0.18,
    "SP2": -0.05,
    "D1": 0.20,
    "D2": -0.04,
    "I1": 0.17,
    "I2": -0.06,
    "F1": 0.16,
    "F2": -0.06,
    "P1": 0.05,
    "N1": 0.08,
    "T1": 0.03,
}


def regress_elo_for_division(
    rating: float | None,
    last_div: str | None,
    new_div: str | None,
    fallback: float = 1500.0,
) -> float:
    """Apply promotion/relegation centroid shrinkage when a club enters or switches division."""
    if new_div is None:
        return fallback if rating is None else float(rating)
    new_c = TIER_ELO_CENTERS.get(new_div, 1500.0)
    if rating is None:
        return float(new_c - 40.0)
    if last_div is None or last_div == new_div:
        return float(rating)
    old_c = TIER_ELO_CENTERS.get(last_div, 1500.0)
    anchor = (new_c - 30.0) if new_c > old_c else (new_c + 20.0)
    return float(0.65 * rating + 0.35 * anchor)


def regress_glicko_for_division(
    mu: float | None,
    phi: float,
    last_div: str | None,
    new_div: str | None,
    scale: float = 173.7178,
) -> tuple[float, float]:
    """Adjust latent Glicko-2 mean and inflate RD when switching pyramid tier."""
    if new_div is None:
        return (0.0 if mu is None else float(mu)), float(phi)
    new_c = (TIER_ELO_CENTERS.get(new_div, 1500.0) - 1550.0) / scale
    if mu is None:
        return float(new_c - 0.20), float(120.0 / scale)
    if last_div is None or last_div == new_div:
        return float(mu), float(phi)
    old_c = (TIER_ELO_CENTERS.get(last_div, 1500.0) - 1550.0) / scale
    anchor = (new_c - 0.15) if new_c > old_c else (new_c + 0.10)
    mu_adj = 0.65 * mu + 0.35 * anchor
    phi_adj = min(math.sqrt(phi * phi + 0.15), 180.0 / scale)
    return float(mu_adj), float(phi_adj)
