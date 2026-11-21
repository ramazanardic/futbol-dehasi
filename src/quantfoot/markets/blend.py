"""Model ↔ keskin piyasa karışımı — aile başına öğrenilmiş ağırlık (``scripts/karisim_kalibrasyonu.py``).

logit P = a + b·[(1−w)·logit(piyasa) + w·logit(model)]. Ağırlıklar ``data/calibration/blend_weights.json``'dan okunur;
bir aile için walk-forward kanıtı yoksa (ya da dosya yoksa) w = 0, a = 0, b = 1: olasılık marjsız keskin piyasadır.
21 Kasım 2026 arşiv testi (≈84 bin test maçı): MS 1/X/2, 2.5 ve 3.5 Üst'te model piyasaya bilgi katmadı (w = 0);
KG Var'da yalnız küçük bir Platt düzeltmesi (w ≈ 0.01) tutuldu.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

WEIGHTS_FILE = Path(__file__).resolve().parents[3] / "data" / "calibration" / "blend_weights.json"
EPS = 1e-6


def family_of(name: str) -> str | None:
    """Seçim adı → karışım ailesi (yalnız arşivde sınanan aileler; diğerleri None → saf piyasa)."""
    n = (name or "").strip()
    if n in ("MS 1",):
        return "ms1"
    if n in ("MS 0", "MS X"):
        return "msx"
    if n == "MS 2":
        return "ms2"
    if re.fullmatch(r"2[.,]5 Üst", n):
        return "ust25"
    if re.fullmatch(r"3[.,]5 Üst", n):
        return "ust35"
    if n == "KG Var":
        return "kg_var"
    return None


@lru_cache(maxsize=4)
def load_weights(path: str | None = None) -> dict:
    f = Path(path) if path else WEIGHTS_FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("families") or {}
    except (OSError, ValueError):
        return {}


def _logit(p: float) -> float:
    p = min(max(p, EPS), 1 - EPS)
    return math.log(p / (1 - p))


def blend_probability(family: str | None, p_model: float | None, p_market: float | None,
                      weights: dict | None = None) -> float | None:
    """Karışık olasılık. Piyasa yoksa model AYNEN dönmez — None döner (kupon için keskin referans zorunlu)."""
    if p_market is None:
        return None
    w_all = load_weights() if weights is None else weights
    e = w_all.get(family or "", {}) if family else {}
    w, a, b = float(e.get("w", 0.0)), float(e.get("a", 0.0)), float(e.get("b", 1.0))
    if p_model is None:
        w = 0.0
    z = a + b * ((1 - w) * _logit(p_market) + w * (_logit(p_model) if p_model is not None else 0.0))
    return 1 / (1 + math.exp(-z))


def model_weight(family: str | None, weights: dict | None = None) -> float:
    w_all = load_weights() if weights is None else weights
    return float((w_all.get(family or "", {}) or {}).get("w", 0.0))
