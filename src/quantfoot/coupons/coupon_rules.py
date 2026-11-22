"""Kupon kuralları — 21 Kasım 2026 kupon post-mortem'undan.

Tahminler tek tek büyük ölçüde kalibreydi; kuponlar yatma nedeni bacak seçimiydi
(beraberlik, KG, ev/deplasman golü, düşük P'li yüksek oran, 5+ bacak çarpımı).

Bu modül banko kupon bacaklarını şu kurallarla süzgeçler:

* Aile listesi kalibrasyon dosyasından, tek günlük residualin büzülmesiyle
  (önsel n = 150). n < 40 aileler kabul edilmez. Pozitif residual P'ye eklenmez.
* Düzeltilmiş P = model P + min(0, büzülmüş aile/isim residuali) + min(0, büzülmüş
  bant residuali); taban ``MIN_CALIBRATED_P`` (%70).
* Aynı maçtan tek bacak; beraberlik bacağı yok (MS 0, İY X, İY/MS …/X …);
  Karşılıklı gol, İlk gol, ev/deplasman gol bacakları yasak.
* Bacak oranı ≥ 1.20 (Nesine tabanı); banko kurulumunda üst sınır 1.80.
* Hedef 5 bacak (gerekçeliyse 6). P(kupon) düzeltilmiş P'lerin çarpımıdır;
  5 bacak doldurulamazsa mevcut en iyi kupon dürüst olasılıkla döner.

Üretim yolu: ``scripts/nesine_kupon.py`` banko modunda havuzu bu süzgeçten geçirir
(eski ``filter_pools_for_mode`` 0.65 tabanı durur; bu kurallar daha sıkıdır).
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from quantfoot import settings as S
from quantfoot.markets.market_diagnosis import (
    MarketDiagnosis,
    canonical_name,
    classify_family,
    diagnose_selection,
)
from quantfoot.paths import REPO_ROOT

MIN_CALIBRATED_P = 0.70
DEFAULT_MIN_LEGS = 5
DEFAULT_MAX_LEGS = 6
DEFAULT_CALIBRATION_PATH = REPO_ROOT / "data/calibration/coupon_family_calibration.json"

BANNED_FAMILIES = frozenset({
    "Karşılıklı gol",
    "Ev sahibi golleri",
    "Deplasman golleri",
    "İlk gol",
    "Çifte şans",
    "Handikap",
})

# 2Y KG ailesi bugün yalnız "Yok" ile ölçüldü; "Var" aynı ailede olsa da yasak.
FAMILY_NAME_ALLOW = {
    "2Y karşılıklı gol": frozenset({"2Y KG Yok"}),
}

_DRAW_EXACT = frozenset({
    "MS 0", "MS X", "İY 0", "İY X", "2Y 0", "2Y X", "X", "0",
    "Skor 0-0", "İY Skor 0-0", "2Y Skor 0-0",
})


def is_draw_leg(name: str | None) -> bool:
    """MS 0 / İY X / İY/MS …/X / 0-0 skor — banko kuponunda yok."""
    n = canonical_name(name)
    inner = n
    if inner.startswith("DEĞİL(") and inner.endswith(")"):
        return False  # "DEĞİL(MS 0)" beraberlik değil
    if inner in _DRAW_EXACT:
        return True
    if re.search(r"\b(beraberlik|berabere)\b", inner, re.IGNORECASE):
        return True
    if inner.startswith("İY/MS"):
        rest = inner[len("İY/MS"):].strip()
        parts = [p for p in re.split(r"[/\s]+", rest) if p]
        if any(p in {"0", "X"} for p in parts):
            return True
    return False


def _combo_parts(name: str) -> list[str]:
    if "&" not in name and " ve " not in name:
        return [name]
    return [p.strip() for p in re.split(r"\s*&\s*|\s+ve\s+", name) if p.strip()]


def shrink_residual(residual: float, n: int, prior_n: int) -> float:
    """James–Stein / önsel büzme: residual · n/(n+prior_n). n=0 → 0."""
    if n <= 0 or prior_n < 0:
        return 0.0
    return float(residual) * (n / (n + prior_n))


def _clip_positive(delta: float) -> float:
    """Tek günlük şanslı residual P'yi şişirmesin."""
    return delta if delta < 0 else 0.0


@dataclass(frozen=True)
class Calibration:
    """Aile / bant / isim-kalıbı residual tablosu (dosyadan veya testten)."""

    prior_n: int = 150
    min_family_n: int = 40
    max_negative_residual: float = -0.01
    headline_min_n: int = 30
    headline_max_negative_residual: float = -0.02
    families: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    bands: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    name_patterns: Sequence[Mapping[str, Any]] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "Calibration":
        return cls(
            prior_n=int(raw.get("prior_n", 150)),
            min_family_n=int(raw.get("min_family_n", 40)),
            max_negative_residual=float(raw.get("max_negative_residual", -0.01)),
            headline_min_n=int(raw.get("headline_min_n", 30)),
            headline_max_negative_residual=float(raw.get("headline_max_negative_residual", -0.02)),
            families=dict(raw.get("families") or {}),
            bands=tuple(raw.get("bands") or ()),
            name_patterns=tuple(raw.get("name_patterns") or ()),
        )


@lru_cache(maxsize=4)
def load_calibration(path: str | Path | None = None) -> Calibration:
    p = Path(path) if path is not None else DEFAULT_CALIBRATION_PATH
    return Calibration.from_dict(json.loads(p.read_text(encoding="utf-8")))


def default_calibration() -> Calibration:
    return load_calibration()


def family_shrunk_residual(family: str, cal: Calibration) -> float | None:
    """Aile residuali büzülmüş; aile yoksa None."""
    rec = cal.families.get(family)
    if not rec:
        return None
    return shrink_residual(float(rec.get("residual") or 0.0), int(rec.get("n") or 0), cal.prior_n)


def family_allowed(family: str, cal: Calibration | None = None) -> bool:
    """Sert yasak listesi + büzülmüş residual / örnek sayısı süzgeci."""
    cal = cal or default_calibration()
    if family in BANNED_FAMILIES:
        return False
    rec = cal.families.get(family)
    if not rec:
        return False
    n = int(rec.get("n") or 0)
    if n < cal.min_family_n:
        return False
    shrunk = shrink_residual(float(rec.get("residual") or 0.0), n, cal.prior_n)
    if shrunk < cal.max_negative_residual:
        return False
    hl = rec.get("headline") or {}
    hn = int(hl.get("n") or 0)
    if hn >= cal.headline_min_n:
        hres = hl.get("residual")
        if hres is not None:
            h_shrunk = shrink_residual(float(hres), hn, cal.prior_n)
            if h_shrunk < cal.headline_max_negative_residual:
                return False
    return True


def _name_pattern_residual(name: str, cal: Calibration) -> tuple[float, int] | None:
    for pat in cal.name_patterns:
        try:
            if re.search(str(pat["pattern"]), name):
                return float(pat.get("residual") or 0.0), int(pat.get("n") or 0)
        except re.error:
            continue
    return None


def _band_residual(p: float, cal: Calibration) -> tuple[float, int]:
    for b in cal.bands:
        lo, hi = float(b["lo"]), float(b["hi"])
        if lo <= p < hi:
            return float(b.get("residual") or 0.0), int(b.get("n") or 0)
    return 0.0, 0


def calibrate_p(p: float, name: str | None, cal: Calibration | None = None,
                family: str | None = None) -> float:
    """Model P + (yalnız negatif) büzülmüş aile/isim ve bant düzeltmesi, [0, 1] aralığında."""
    cal = cal or default_calibration()
    n = canonical_name(name)
    fam = family or classify_family(n)
    name_hit = _name_pattern_residual(n, cal)
    if name_hit is not None:
        raw, nn = name_hit
        fam_delta = _clip_positive(shrink_residual(raw, nn, cal.prior_n))
    else:
        rec = cal.families.get(fam)
        if rec:
            fam_delta = _clip_positive(shrink_residual(float(rec.get("residual") or 0.0),
                                                       int(rec.get("n") or 0), cal.prior_n))
        else:
            fam_delta = 0.0
    b_raw, b_n = _band_residual(float(p), cal)
    band_delta = _clip_positive(shrink_residual(b_raw, b_n, cal.prior_n))
    return min(1.0, max(0.0, float(p) + fam_delta + band_delta))


@dataclass(frozen=True)
class RuleDecision:
    ok: bool
    reasons: tuple[str, ...]
    family: str
    name: str
    p_cal: float | None
    odds: float | None


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for n in names:
        v = obj.get(n) if isinstance(obj, Mapping) else getattr(obj, n, None)
        if v is not None:
            return v
    return default


_DIAG_CTX_KEYS = (
    "mu_home",
    "mu_away",
    "home_gk1_out",
    "away_gk1_out",
    "home_top_scorer_out",
    "away_top_scorer_out",
    "home_rate",
    "away_rate",
    "min_side_rate",
    "flags",
    "steam_pp",
    "sharp_steam_pp",
)


def _has_diagnosis_context(obj: Any) -> bool:
    for k in _DIAG_CTX_KEYS:
        if _get(obj, k, default=None) is not None:
            return True
    return False


def leg_decision(obj: Any, cal: Calibration | None = None, *,
                 min_p: float = MIN_CALIBRATED_P,
                 min_odds: float = S.MIN_LEG_ODDS,
                 max_odds: float | None = S.BANKO_MAX_LEG_ODDS) -> RuleDecision:
    """Tek bacak kural ve teşhis/rehabilitasyon süzgecinden geçer mi?"""
    cal = cal or default_calibration()
    raw_name = _get(obj, "name", "sel", "selection", default="") or ""
    name = canonical_name(raw_name)
    # kısa ad boşsa pazar+seçimden dene
    if not name:
        name = canonical_name(_get(obj, "sel", "selection", default="") or "")
    family = classify_family(name)
    odds_v = _get(obj, "odds", default=None)
    try:
        odds = float(odds_v) if odds_v is not None else None
    except (TypeError, ValueError):
        odds = None
    p_v = _get(obj, "p", "p_cal", "probability", default=None)
    try:
        p = float(p_v) if p_v is not None else None
    except (TypeError, ValueError):
        p = None

    if p is not None and not (math.isfinite(p) and 0 <= p <= 1):
        p = None
    if odds is not None and not math.isfinite(odds):
        odds = None

    diag: MarketDiagnosis | None = None
    if name and _has_diagnosis_context(obj):
        diag = diagnose_selection(name, p if p is not None else 0.0, obj, for_coupon=True)
    explicit_rehab = _get(obj, "rehabilitated", default=None)
    is_rehabilitated = (
        (explicit_rehab is True and (diag is None or diag.ok))
        or (explicit_rehab is None and diag is not None and diag.ok and diag.rehabilitated)
    )

    if p is not None:
        if is_rehabilitated:
            # Rehabilite edilmiş alt-dilim negatif aile/isim sapmasından arındırılmıştır;
            # yalnız bant düzeltmesi ve varsa negatif teşhis düzeltmesi uygulanır.
            b_raw, b_n = _band_residual(float(p), cal)
            band_delta = _clip_positive(shrink_residual(b_raw, b_n, cal.prior_n))
            diag_delta = min(0.0, float(diag.residual_adjustment)) if diag is not None else 0.0
            p_cal = min(1.0, max(0.0, float(p) + band_delta + diag_delta))
        else:
            base_cal = calibrate_p(p, name, cal, family)
            diag_delta = min(0.0, float(diag.residual_adjustment)) if diag is not None else 0.0
            p_cal = min(1.0, max(0.0, base_cal + diag_delta))
    else:
        p_cal = None

    reasons: list[str] = []
    if not name:
        reasons.append("seçim adı yok")
    if is_draw_leg(name):
        reasons.append("beraberlik bacağı yasak")
    if family in BANNED_FAMILIES:
        reasons.append(f"{family} ailesi yasak")
    elif not is_rehabilitated and not family_allowed(family, cal):
        reasons.append(f"{family} ailesi kupon beyaz listesinde değil")
    allowed_names = FAMILY_NAME_ALLOW.get(family)
    if allowed_names is not None and name not in allowed_names:
        reasons.append(f"{family} ailesinde yalnız {', '.join(sorted(allowed_names))} kabul")
    if diag is not None and not diag.ok:
        for r in diag.reasons:
            reasons.append(r)
    for part in _combo_parts(name):
        if part == name and "&" not in name and " ve " not in name:
            continue
        pf = classify_family(part)
        if is_draw_leg(part):
            reasons.append(f"kombine parça beraberlik: {part}")
        if pf in BANNED_FAMILIES:
            reasons.append(f"kombine parça yasak aile ({pf}): {part}")
    if odds is None:
        reasons.append("oran yok")
    else:
        if odds + 1e-12 < min_odds:
            reasons.append(f"oran {odds:.2f} < {min_odds:.2f}")
        if max_odds is not None and odds > max_odds + 1e-12:
            reasons.append(f"oran {odds:.2f} > {max_odds:.2f}")
    if p_cal is None:
        reasons.append("olasılık yok")
    elif p_cal + 1e-12 < min_p:
        reasons.append(f"düzeltilmiş P %{100 * p_cal:.1f} < %{100 * min_p:.0f}")
    # unique reasons, keep order
    seen: set[str] = set()
    uniq = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return RuleDecision(not uniq, tuple(uniq), family, name, p_cal, odds)


def filter_legs(legs: Iterable[Any], cal: Calibration | None = None, **kw: Any) -> list[Any]:
    """Kuralı geçen bacakları (orijinal nesneler, giriş sırası) döndür."""
    return [leg for leg in legs if leg_decision(leg, cal, **kw).ok]


@dataclass(frozen=True)
class RuleLeg:
    match_id: str
    match: str
    name: str
    family: str
    odds: float
    p: float
    p_cal: float
    kickoff: str | None = None
    market: str | None = None
    league: str | None = None
    source: Any = None


@dataclass(frozen=True)
class RuleCoupon:
    legs: tuple[RuleLeg, ...]
    total_odds: float
    p_win: float
    short: bool
    notes: tuple[str, ...]
    rejected: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_legs": len(self.legs),
            "total_odds": round(self.total_odds, 4),
            "p_win": self.p_win,
            "p_win_pct": round(100 * self.p_win, 2),
            "short": self.short,
            "notes": list(self.notes),
            "rejected": self.rejected,
            "legs": [
                {
                    "code": L.match_id,
                    "match": L.match,
                    "kickoff": L.kickoff,
                    "league": L.league,
                    "market": L.market,
                    "name": L.name,
                    "family": L.family,
                    "odds": L.odds,
                    "p": L.p,
                    "p_cal": round(L.p_cal, 4),
                }
                for L in self.legs
            ],
        }


def _to_rule_leg(obj: Any, dec: RuleDecision) -> RuleLeg:
    code = _get(obj, "code", "match_id", "event_id", default="?")
    match = _get(obj, "match", default=None)
    if match is None and _get(obj, "home") is not None:
        match = f"{_get(obj, 'home')} - {_get(obj, 'away')}"
    p = float(_get(obj, "p", "p_cal", "probability"))
    return RuleLeg(
        match_id=str(code),
        match=str(match or code),
        name=dec.name,
        family=dec.family,
        odds=float(dec.odds or 0.0),
        p=p,
        p_cal=float(dec.p_cal or 0.0),
        kickoff=_get(obj, "ko", "kickoff", "kickoff_tsi", default=None),
        market=_get(obj, "market", default=None),
        league=_get(obj, "league", "lg", default=None),
        source=obj,
    )


def build_rules_coupon(
    candidates: Iterable[Any],
    cal: Calibration | None = None,
    *,
    min_p: float = MIN_CALIBRATED_P,
    min_odds: float = S.MIN_LEG_ODDS,
    max_odds: float | None = S.BANKO_MAX_LEG_ODDS,
    min_legs: int = DEFAULT_MIN_LEGS,
    max_legs: int = DEFAULT_MAX_LEGS,
    prefer_n: int = DEFAULT_MIN_LEGS,
) -> RuleCoupon:
    """Adaylardan kurala uygun banko kupon kur (aynı maçtan en yüksek p_cal, sonra en yüksek p_cal sıralı).

    ``prefer_n`` varsayılan 5: 6. bacak ürün P'yi düşürür, yalnız aday havuzu 5'i dolduramıyorsa
    veya çağıran açıkça 6 isterse 6'ya çıkılır (``prefer_n=6``). 5 bacak yoksa kısa kupon + not.
    """
    cal = cal or default_calibration()
    notes: list[str] = []
    rejected = 0
    best: dict[str, RuleLeg] = {}
    for obj in candidates:
        dec = leg_decision(obj, cal, min_p=min_p, min_odds=min_odds, max_odds=max_odds)
        if not dec.ok:
            rejected += 1
            continue
        leg = _to_rule_leg(obj, dec)
        prev = best.get(leg.match_id)
        if prev is None or leg.p_cal > prev.p_cal + 1e-12 or (
            abs(leg.p_cal - prev.p_cal) <= 1e-12 and leg.odds < prev.odds
        ):
            best[leg.match_id] = leg
    ranked = sorted(best.values(), key=lambda L: (-L.p_cal, L.odds, L.match_id))
    n_take = prefer_n if len(ranked) >= prefer_n else min(max_legs, len(ranked))
    if n_take > max_legs:
        n_take = max_legs
    chosen = tuple(ranked[:n_take])
    short = len(chosen) < min_legs
    if short:
        notes.append(
            f"Kural süzgecinden yalnızca {len(chosen)} bacak geçti (hedef {min_legs}–{max_legs}); "
            "kısa kupon, dürüst olasılık aşağıda."
        )
    if rejected:
        notes.append(f"{rejected} aday kural süzgecinden elendi.")
    total_odds = math.prod(L.odds for L in chosen) if chosen else 1.0
    p_win = math.prod(L.p_cal for L in chosen) if chosen else 0.0
    if not chosen:
        notes.append("Uygun bacak yok.")
        p_win = 0.0
        total_odds = 1.0
    return RuleCoupon(chosen, float(total_odds), float(p_win), short, tuple(notes), rejected)
