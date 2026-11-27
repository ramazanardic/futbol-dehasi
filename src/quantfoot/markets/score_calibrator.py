"""Multinomial Skor Kalibrasyonu & Akıllı Çoklu-Skor Örtme (Score Dutching).

1. `score_calibration.json`: 6 makro rejim x skor sınıfı için tarihsel (2018-2023)
   Empirical Bayes düzeltme çarpanları. Ham dağılımı tarihsel gerçekleşmeye yaklaştırır.
2. `optimize_score_dutching`: Canlı Nesine MTID 777 skor oranlarıyla aynı maçta en yüksek
   EV veya kapsama olasılığını veren 2 ya da 3 skorluk küme için optimal tutar dağılımı hesaplar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
import itertools
import json
import math
from pathlib import Path
from typing import Any

from quantfoot.paths import REPO_ROOT

CALIBRATION_PATH = REPO_ROOT / "data" / "calibration" / "score_calibration.json"


def classify_score_regime(
    p1: float,
    px: float,
    p2: float,
    p_over25: float | None = None,
) -> str:
    """Maçı 6 makro skor rejiminden birine ayır."""
    is_open = (p_over25 is not None and p_over25 >= 0.51)
    if p1 - p2 >= 0.14 and p1 >= 0.44:
        return "strong_home_open" if is_open else "strong_home_low"
    if p2 - p1 >= 0.12 and p2 >= 0.42:
        return "strong_away_open" if is_open else "strong_away_low"
    return "balanced_open" if is_open else "balanced_low"


@lru_cache(maxsize=1)
def load_score_calibration(path: Path | None = None) -> dict[str, Any]:
    p = path or CALIBRATION_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def calibrate_score_distribution(
    ft_dist: Mapping[str, float] | None,
    f1x2: Sequence[float] | None = None,
    p_over25: float | None = None,
    table: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Ham skor dağılımını rejim bazlı Empirical Bayes çarpanlarıyla kalibre et."""
    if not ft_dist:
        return {}
    cal = table if table is not None else load_score_calibration()
    p1 = float(f1x2[0]) if f1x2 and len(f1x2) == 3 and f1x2[0] is not None else 0.34
    px = float(f1x2[1]) if f1x2 and len(f1x2) == 3 and f1x2[1] is not None else 0.32
    p2 = float(f1x2[2]) if f1x2 and len(f1x2) == 3 and f1x2[2] is not None else 0.34
    regime = classify_score_regime(p1, px, p2, p_over25)
    mult_map = ((cal.get("regimes") or {}).get(regime) or {}).get("multipliers") or {}

    out: dict[str, float] = {}
    tot = 0.0
    for sc, p in ft_dist.items():
        norm_sc = str(sc).replace(":", "-").strip()
        val = max(0.0, float(p)) * float(mult_map.get(norm_sc, 1.0))
        out[norm_sc] = val
        tot += val
    if tot <= 0:
        return {str(k).replace(":", "-").strip(): float(v) for k, v in ft_dist.items()}
    return {k: round(v / tot, 6) for k, v in out.items()}


@dataclass(frozen=True)
class ScoreDutchingPlan:
    scores: tuple[str, ...]
    odds: tuple[float, ...]
    probs: tuple[float, ...]
    stake_weights: tuple[float, ...]
    stake_tl: tuple[float, ...]
    effective_odds: float
    cover_prob: float
    ev: float
    expected_payout_if_hit: float


def optimize_score_dutching(
    calibrated_probs: Mapping[str, float],
    market_score_odds: Mapping[str, float],
    *,
    sizes: Sequence[int] = (2, 3),
    min_cover_prob: float = 0.16,
    min_eff_odds: float = 2.30,
    budget_tl: float = 100.0,
    pool_top_n: int = 10,
) -> list[ScoreDutchingPlan]:
    """Canlı skor oranlarıyla aynı maçta 2 veya 3 skoru eşit-kazançlı örten Dutching planları kur."""
    cands: list[tuple[str, float, float]] = []
    for sc, p in calibrated_probs.items():
        norm = str(sc).replace(":", "-").strip()
        od = market_score_odds.get(norm)
        if od is None or od <= 1.05 or p <= 0.005:
            continue
        cands.append((norm, float(p), float(od)))
    if len(cands) < 2:
        return []
    cands.sort(key=lambda x: (-x[1], -x[1] * x[2]))
    pool = cands[:pool_top_n]

    plans: list[ScoreDutchingPlan] = []
    for k in sizes:
        if k > len(pool):
            continue
        for comb in itertools.combinations(pool, int(k)):
            inv_sum = sum(1.0 / item[2] for item in comb)
            if inv_sum <= 0 or inv_sum >= 1.0:
                continue
            eff_odds = 1.0 / inv_sum
            if eff_odds < min_eff_odds:
                continue
            cover_prob = sum(item[1] for item in comb)
            if cover_prob < min_cover_prob:
                continue
            ev = cover_prob * eff_odds - 1.0
            weights = tuple(round((1.0 / item[2]) / inv_sum, 4) for item in comb)
            stakes = tuple(round(budget_tl * w, 2) for w in weights)
            plans.append(
                ScoreDutchingPlan(
                    scores=tuple(item[0] for item in comb),
                    odds=tuple(round(item[2], 2) for item in comb),
                    probs=tuple(round(item[1], 4) for item in comb),
                    stake_weights=weights,
                    stake_tl=stakes,
                    effective_odds=round(eff_odds, 2),
                    cover_prob=round(cover_prob, 4),
                    ev=round(ev, 4),
                    expected_payout_if_hit=round(budget_tl * eff_odds, 2),
                )
            )
    plans.sort(key=lambda pl: (-pl.ev, -pl.cover_prob, -pl.effective_odds))
    return plans
