"""Bet-family classification of engine / Nesine selection names and the per-family value rules.

One canonical family per selection (21 Nov bet-family audit, docs/research/bahis_aileleri_2026_11_21.md). The rules
themselves (minimum calibrated EV and extra uncertainty per family) live in ``quantfoot.settings`` so every coupon
path reads the same numbers; this module only maps a selection name to its family and combines the family floor with
the PR #3 hard-market floor (the stricter one wins).
"""

from __future__ import annotations

import re

_HALF_SPECIAL = ("En Çok Gol", "Her İki Yarıyı Kazanır", "En Az Bir Yarıyı Kazanır", "İki Yarıda Gol")


def bet_family(name: str) -> str:
    """Canonical bet family of a selection name (``DEĞİL(x)`` = family of x)."""
    n = (name or "").strip()
    if n.startswith("DEĞİL(") and n.endswith(")"):
        n = n[6:-1].strip()
    if not n:
        return "Diğer"
    if "Korner" in n:
        return "Korner"
    if "Kart" in n:
        return "Kart"
    if n.startswith(("İlk Gol", "Son Gol")):
        return "İlk Gol"
    if n.startswith("İY/MS"):
        return "İY/MS"
    if "&" in n:
        parts = [p.strip() for p in n.split("&")]
        if all(re.fullmatch(r"(?:İY |2Y )?Skor \d+-\d+", p) for p in parts):
            return "Doğru Skor"  # Nesine 'İlk Yarı / Maç Skoru'
        if all(re.fullmatch(r"(?:İY|2Y) KG (?:Var|Yok)", p) for p in parts):
            return "Yarı KG"     # Nesine '1. Yarı / 2. Yarı Karşılıklı Gol'
        if all(re.fullmatch(r"(?:İY|2Y) \d+\.5 (?:Alt|Üst)", p) for p in parts):
            return "İY Alt/Üst"  # 'Her iki yarıda da x Alt/Üst'
        return "Kombine"
    if n.startswith("MS "):
        return "Maç Sonucu"
    if n.startswith("ÇŞ "):
        return "Çifte Şans"
    if n.startswith("Hnd("):
        return "Handikap"
    if n.startswith("Fark "):
        return "Fark"
    if re.fullmatch(r"(?:İY |2Y )?Skor \d+-\d+|(?:İY )?Skor Diğer", n):
        return "Doğru Skor"
    if n == "İki Yarıda KG Var" or re.fullmatch(r"(?:İY|2Y) KG (?:Var|Yok)", n):
        return "Yarı KG"
    if re.fullmatch(r"KG (?:Var|Yok)", n):
        return "Karşılıklı Gol"
    if any(t in n for t in _HALF_SPECIAL):
        return "Yarı Özel"
    if n.startswith(("Ev ", "Dep ")):
        return "Takım Golleri"
    if re.fullmatch(r"(?:İY |2Y )?(?:Tek|Çift)", n):
        return "Tek/Çift"
    if re.fullmatch(r"İY (?:ÇŞ )?[10X2x]{1,2}", n):
        return "İY Sonucu"
    if re.fullmatch(r"2Y [10X2x]", n):
        return "2Y Sonucu"
    if re.fullmatch(r"İY \d+\.5 (?:Alt|Üst)", n):
        return "İY Alt/Üst"
    if re.fullmatch(r"2Y \d+\.5 (?:Alt|Üst)", n):
        return "2Y Alt/Üst"
    if re.fullmatch(r"\d+\.5 (?:Alt|Üst)", n):
        return "Alt/Üst"
    if re.fullmatch(r"\d+-\d+ Gol|\+?\d+\+? Gol", n):
        return "Toplam Gol Aralığı"
    return "Diğer"


def family_rule(name: str) -> tuple[float, float]:
    """(minimum calibrated EV, extra σ) for a selection from ``settings.FAMILY_VALUE_RULES``."""
    from quantfoot.settings import FAMILY_VALUE_RULES

    return FAMILY_VALUE_RULES.get(bet_family(name), FAMILY_VALUE_RULES["Diğer"])


def leg_min_ev(name: str, hard: bool = False) -> float:
    """EV a coupon leg needs (calibrated p × Nesine odds − 1): the stricter of its family floor and, for a hard market
    (PR #3: Üst 2.5/3.5, KG Var, weak-favourite MS 1, İY/MS, exact score), ``HARD_MARKET_MIN_EV``."""
    from quantfoot.settings import HARD_MARKET_MIN_EV

    floor, _ = family_rule(name)
    return max(floor, HARD_MARKET_MIN_EV) if hard else floor
