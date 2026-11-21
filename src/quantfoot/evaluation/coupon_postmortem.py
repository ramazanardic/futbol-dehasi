"""Pure helpers for the Nesine coupon post-mortem (no IO, unit-tested).

Nesine's coupon history gives, per leg, the market title and the selection text
("Toplam Gol" / "2,5 Üst").  ``canonical_leg`` turns that into the engine's selection
name (``2.5 Üst``) and a market family used for the hit-rate tables.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

_LINE = re.compile(r"^(\d+),(\d) (Üst|Alt)$")


@dataclass(frozen=True)
class CanonLeg:
    name: str | None      # engine selection name (goal_probability / nesine_global), None = not priceable
    family: str           # market family for the tables
    hard: bool            # one of the user's "most losing" market families (t9u)


def _line(sel: str) -> tuple[str, str] | None:
    m = _LINE.match(sel.strip())
    return (f"{m.group(1)}.{m.group(2)}", m.group(3)) if m else None


def canonical_leg(market: str | None, selection: str | None, odds: float | None = None) -> CanonLeg:
    """Map Nesine coupon-history (market, selection) to an engine name and a family."""
    mk = (market or "").strip()
    sel = (selection or "").strip()
    if not mk and not sel:
        if odds is not None and odds >= 4.0:
            return CanonLeg(None, "Bilinmiyor (oran ≥ 4, uzun atış)", True)
        return CanonLeg(None, "Bilinmiyor", False)
    if mk == "Maç Sonucu":
        side = {"1": "1", "X": "0", "0": "0", "2": "2"}.get(sel)
        if side is None:
            return CanonLeg(None, "MS (seçim metni yok)", False)
        if side == "1" and odds is not None and 1.70 <= odds <= 2.30:
            return CanonLeg("MS 1", "MS 1 zayıf favori (1.70–2.30)", True)
        return CanonLeg(f"MS {side}", f"MS {side}", False)
    if mk == "Toplam Gol":
        ln = _line(sel)
        if ln:
            hard = ln[1] == "Üst" and ln[0] in ("2.5", "3.5")
            return CanonLeg(f"{ln[0]} {ln[1]}", f"Toplam Gol {ln[0]} {ln[1]}", hard)
    if mk == "Karşılıklı Gol" and sel in ("Var", "Yok"):
        return CanonLeg(f"KG {sel}", f"KG {sel}", sel == "Var")
    if mk == "1.Y Gol":
        ln = _line(sel)
        if ln:
            return CanonLeg(f"İY {ln[0]} {ln[1]}", f"İY Gol {ln[1]}", False)
    if mk == "İlk Yarı/Maç Sonucu":
        m = re.fullmatch(r"([12X])/([12X])", sel)
        if m:
            a, b = (x.replace("X", "0") for x in m.groups())
            return CanonLeg(f"İY/MS {a}/{b}", "İY/MS", True)
    if mk == "Çifte Şans":
        dc = {"1-X": "10", "X-2": "02", "1-2": "12"}.get(sel)
        if dc:
            return CanonLeg(f"ÇŞ {dc}", "Çifte Şans", False)
    if mk in ("Ev. Gol", "Dep. Gol"):
        ln = _line(sel)
        if ln:
            side = "Ev" if mk.startswith("Ev") else "Dep"
            return CanonLeg(f"{side} {ln[0]} {ln[1]}", "Takım golü", False)
    if mk in ("Ev. 1.Yarı Gol", "Dep. 1.Yarı Gol"):
        ln = _line(sel)
        if ln:
            side = "Ev" if mk.startswith("Ev") else "Dep"
            return CanonLeg(f"{side} İY {ln[0]} {ln[1]}", "Takım golü", False)
    if mk in ("Ev. İki Yarı da Gol", "Dep. İki Yarı da Gol") and sel == "Atar":
        side = "Ev" if mk.startswith("Ev") else "Dep"
        return CanonLeg(f"{side} İki Yarıda Gol", "Takım golü", False)
    if mk == "2,5 Alt/Üst ve KG":
        m = re.fullmatch(r"(Üst|Alt)&(Var|Yok)", sel)
        if m:
            return CanonLeg(f"2.5 {m.group(1)} & KG {m.group(2)}", "Kombine (MS/Gol/KG)", False)
    m = re.fullmatch(r"MS&Toplam Gol\((\d),(\d)\)", mk)
    if m:
        mm = re.fullmatch(r"([12X]) & (Üst|Alt)", sel)
        if mm:
            side = mm.group(1).replace("X", "0")
            return CanonLeg(f"MS {side} & {m.group(1)}.{m.group(2)} {mm.group(2)}", "Kombine (MS/Gol/KG)", False)
    m = re.fullmatch(r"Hnd\. MS \((\d):(\d)\)", mk)
    if m and sel in ("1", "X", "2"):
        hcp = int(m.group(1)) - int(m.group(2))
        return CanonLeg(f"Hnd({hcp:+d}) {sel.replace('X', '0')}", "Handikap", False)
    if "Korner" in mk:
        return CanonLeg(None, "Korner", False)
    if mk.startswith("Skor") or "Skor" in mk:
        return CanonLeg(None, "Kesin skor", True)
    return CanonLeg(None, f"Diğer ({mk})", False)


def odds_band(odds: float) -> str:
    for hi, lbl in ((1.20, "<1.20"), (1.40, "1.20–1.39"), (1.70, "1.40–1.69"), (2.30, "1.70–2.29"), (4.0, "2.30–3.99")):
        if odds < hi:
            return lbl
    return "≥4.00"


def legs_bucket(n: int) -> str:
    if n <= 2:
        return "1–2"
    if n <= 4:
        return "3–4"
    if n <= 6:
        return "5–6"
    if n <= 8:
        return "7–8"
    return "9+"


def parse_tl(text) -> float:
    """'1.010,09 TL' / '5,72' / 1.5 -> float (Turkish thousands '.' and decimal ',')."""
    if text is None:
        return 0.0
    if isinstance(text, (int, float)):
        return 0.0 if (isinstance(text, float) and math.isnan(text)) else float(text)
    s = str(text).replace("TL", "").strip()
    if not s or s.lower() == "nan":
        return 0.0
    return float(s.replace(".", "").replace(",", "."))


def implied_prob(odds: float, overround: float) -> float:
    """Rough margin-free probability of one selection: (1/odds)/(1+overround) (proportional devig)."""
    return (1.0 / odds) / (1.0 + max(0.0, overround))


def binom_two_sided_p(k: int, n: int, p: float) -> float:
    """Exact two-sided binomial p-value (sum of outcomes no more likely than k)."""
    if n == 0:
        return 1.0
    pmf = [math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(n + 1)]
    pk = pmf[k]
    return float(min(1.0, sum(x for x in pmf if x <= pk * (1 + 1e-9))))
