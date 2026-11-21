"""Kupon modları — her kupon kurma yolunun ortak kapısı (21 Kasım 2026 denetimi, kullanıcı kuralı t69u/t70u/t73u).

* ``banko`` (VARSAYILAN): her bacak kalibre P ≥ %65, Nesine oranı 1.20–1.80 (kurarken ≥ 1.25 tercih, 1.22 altı uyarı),
  keskin referans zorunlu, kupon 5 maç (gerekçeliyse 6), 1–2 maçlık düşük oranlı kupon yok, P(kupon) < %5 ise ret.
* ``risk``: YALNIZ kullanıcı banko ile ulaşılamayan bir hedefi açıkça isterse (ör. "300 TL'den en az 2.000 TL").
  Bacak oranı ≤ 2.10, keskin referans zorunlu, 3–6 maç; P(kupon) ne kadar düşükse dürüstçe yazılır (ret değil).

Ek kontroller (her iki modda):
* seçim Nesine bülteninde birebir açık olmalı (``offered``) — Pécs "Dep 0,5 Alt" bültende yoktu;
* aynı maç en çok ``BANKO_MAX_COUPONS_PER_MATCH`` açık kuponda — oynanan kuponlar ``oynanan_kuponlar.json``
  kaydından okunur (``scripts/sonuc_defteri.py kaydet``).
"""

from __future__ import annotations

import datetime as dt
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from quantfoot import settings as S
from quantfoot.strategy.banko_guard import BankoLeg, GuardConfig, GuardResult, check_coupon

MODES = ("banko", "risk")
DEFAULT_MODE = "banko"
REGISTRY_NAME = "oynanan_kuponlar.json"
OPEN_STATES = ("açık", "acik", "bekliyor", None, "")


@dataclass(frozen=True)
class ModePolicy:
    name: str
    min_prob: float
    prefer_min_odds: float   # kurulum anında aday tabanı (oran kayması tamponu)
    max_leg_odds: float
    min_legs: int
    max_legs: int
    sharp_only: bool
    guard: GuardConfig


def policy(mode: str = DEFAULT_MODE) -> ModePolicy:
    if mode not in MODES:
        raise ValueError(f"bilinmeyen kupon modu {mode!r} (geçerli: {', '.join(MODES)})")
    if mode == "banko":
        g = GuardConfig(min_prob=S.BANKO_MIN_PROB, max_leg_odds=S.BANKO_MAX_LEG_ODDS, min_legs=S.BANKO_MIN_LEGS,
                        max_legs=S.BANKO_MAX_LEGS, lottery_is_error=True, name="banko")
        return ModePolicy("banko", S.BANKO_MIN_PROB, S.BANKO_PREFER_MIN_ODDS, S.BANKO_MAX_LEG_ODDS,
                          S.BANKO_MIN_LEGS, S.BANKO_MAX_LEGS, True, g)
    g = GuardConfig(min_prob=S.RISK_MIN_PROB, max_leg_odds=S.RISK_MAX_LEG_ODDS, min_legs=S.RISK_MIN_LEGS,
                    max_legs=S.RISK_MAX_LEGS, lottery_is_error=False, name="risk")
    return ModePolicy("risk", S.RISK_MIN_PROB, S.BANKO_PREFER_MIN_ODDS, S.RISK_MAX_LEG_ODDS,
                      S.RISK_MIN_LEGS, S.RISK_MAX_LEGS, True, g)


# ---------------------------------------------------------------- bacak dönüştürme (dict / dataclass)

def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for n in names:
        v = obj.get(n) if isinstance(obj, Mapping) else getattr(obj, n, None)
        if v is not None:
            return v
    return default


Offered = Callable[..., bool | None]


def bulletin_offered(bulletin: Mapping[Any, Mapping[str, float]] | None) -> Offered:
    """Nesine bülten okuması ({kod: {seçim anahtarı: oran}}) → (kod, anahtar) açık mı? Bülten yoksa None (bilinmiyor)."""
    if bulletin is None:
        return lambda code, key: None
    norm = {str(k): v for k, v in bulletin.items()}

    def f(code: Any, key: Any, name: str | None = None) -> bool | None:
        sel = norm.get(str(code))
        if sel is None:
            return False          # maç bültende yok (başlamış / kaldırılmış)
        if key is None:
            if not name or not any(str(k).startswith("name:") for k in sel):
                return None       # seçim anahtarı ya da adı yok: bilinmiyor
            key = f"name:{name}"
        o = sel.get(key)
        return bool(o and float(o) > 1.01)
    return f


def bulletin_book(events: Iterable[Any], key_fn: Callable[[Any], str] | None = None) -> dict[str, dict[str, float]]:
    """``parse_bulletin`` olayları → {kod: {"name:<kısa ad>": oran, [anahtar]: oran}} (bültende olmayan seçim reddi için)."""
    out: dict[str, dict[str, float]] = {}
    for e in events:
        book = out.setdefault(str(e.code), {})
        for s in e.selections:
            book[f"name:{s.name}"] = min(book.get(f"name:{s.name}", s.odds), s.odds)
            if key_fn is not None:
                book[key_fn(s)] = s.odds
    return out


def to_leg(obj: Any, offered: Offered | None = None) -> BankoLeg:
    """Kupon kurucularının bacak sözlüğü (nesine_kupon, banko seçiciler, defter) ya da MarketRecommendation/Leg nesnesi."""
    code = _get(obj, "code", "match_id", "event_id", default="?")
    name = _get(obj, "name", "selection", "sel", default="")
    match = _get(obj, "match", default=None)
    if match is None and _get(obj, "home") is not None:
        match = f"{_get(obj, 'home')} - {_get(obj, 'away')}"
    label = f"{match or code} {name}".strip()
    odds = float(_get(obj, "odds", "offered_odds", "nesine_odds", default=0.0))
    p = float(_get(obj, "p", "probability", "prob", "fair_prob", "P", default=0.0))
    p_sharp, p_model = _get(obj, "p_sharp", default=None), _get(obj, "p_model", "model_p", default=None)
    if p_sharp is not None and p_model is not None and not _get(obj, "live", default=False):
        # model ile keskin fiyat ayrı verilmişse aile ağırlığıyla karıştır (çoğu ailede w = 0 → piyasa) ve
        # bacağın kendi P'sinden iyimser olanını değil, düşüğünü kullan
        from quantfoot.markets.blend import blend_probability, family_of
        pb = blend_probability(family_of(str(name)), float(p_model), float(p_sharp))
        if pb is not None:
            p = min(p, pb) if p > 0 else pb
    ref = str(_get(obj, "reference", default="") or "")
    tier = _get(obj, "tier", default=None)
    sharp = _get(obj, "sharp_ref", default=None)
    if sharp is None:
        # nesine_kupon: tier "keskin"/"orta"; diğer kaynaklar: "[orta]" etiketi ya da ESPN/model referansı keskin değil
        sharp = (tier == "keskin") if tier is not None else not (ref.endswith("[orta]") or ref.upper().startswith(("ESPN", "MODEL")))
    off = _get(obj, "offered", default=None)
    if offered is not None:
        o2 = offered(code, _get(obj, "key", default=None), str(name) if name else None)
        if o2 is not None:
            off = o2
    flags = tuple(_get(obj, "red_flags", default=()) or ())
    if _get(obj, "odds_is_estimated", default=False):
        off = False
    return BankoLeg(match_id=str(code), label=label, odds=odds, p=p, offered=True if off is None else bool(off),
                    sharp_ref=bool(sharp), live=bool(_get(obj, "live", default=False)),
                    p_market=_get(obj, "p_market", "market_prob", default=None), red_flags=flags)


def guard_legs(legs: Iterable[Any], mode: str = DEFAULT_MODE, *, open_exposure: Mapping[Any, int] | None = None,
               offered: Offered | None = None, at_selection: bool = True) -> GuardResult:
    pol = policy(mode)
    bl = [to_leg(x, offered) for x in legs]
    exp = {str(k): v for k, v in (open_exposure or {}).items()}
    return check_coupon(bl, exp, pol.guard, at_selection=at_selection)


def honest_line(res: GuardResult, stake: float | None = None) -> str:
    """Kullanıcıya her kuponla birlikte yazılacak dürüst özet."""
    p = res.p_win
    one_in = (1.0 / p) if p > 0 else math.inf
    s = f"toplam oran {res.total_odds:.2f}, tutma ihtimali %{100 * p:.1f} (yaklaşık {one_in:.0f}'de 1)"
    if stake:
        s += f"; {stake:.0f} TL → kazanç {stake * res.total_odds:.2f} TL, beklenen değer {stake * (p * res.total_odds - 1):+.0f} TL"
    return s


def target_reachable(target: float, mode: str = DEFAULT_MODE, leg_margin: float = 0.12) -> bool:
    """Bu mod bu hedef orana kaba olarak ulaşabilir mi (her bacak min_prob'da, Nesine payı ≈ %12)."""
    pol = policy(mode)
    leg = min(pol.max_leg_odds, 1.0 / (pol.min_prob * (1.0 + leg_margin)))
    return leg ** pol.max_legs >= target - 1e-9


# ---------------------------------------------------------------- oynanan kupon kaydı ve açık maruziyet

def registry_path(area: Path) -> Path:
    return Path(area) / REGISTRY_NAME


def load_placed(area: Path) -> list[dict]:
    f = registry_path(area)
    try:
        return list(json.loads(f.read_text(encoding="utf-8")).get("coupons") or [])
    except (OSError, ValueError):
        return []


def save_placed(area: Path, coupons: Sequence[dict]) -> Path:
    f = registry_path(area)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"coupons": list(coupons)}, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


def register_placed(area: Path, coupon: dict) -> dict:
    """Oynanan kuponu kayda ekle (aynı id varsa günceller). Zorunlu: id, stake, legs[code, odds, p, name]."""
    for k in ("id", "stake", "legs"):
        if k not in coupon:
            raise ValueError(f"kupon kaydında '{k}' yok")
    rows = [c for c in load_placed(area) if c.get("id") != coupon["id"]]
    c = {"status": "açık", **coupon}
    c.setdefault("odds", round(math.prod(float(x["odds"]) for x in c["legs"]), 2))
    rows.append(c)
    save_placed(area, rows)
    return c


def open_exposure(area: Path | None = None, coupons: Sequence[dict] | None = None,
                  now: dt.datetime | None = None, horizon_h: float = 2.5) -> dict[str, int]:
    """Maç kodu → bu maçı içeren AÇIK (sonuçlanmamış) oynanmış kupon sayısı. Maçı çoktan bitmiş bacaklar sayılmaz."""
    rows = coupons if coupons is not None else (load_placed(area) if area is not None else [])
    now = now or dt.datetime.now(S.TSI)
    out: dict[str, int] = {}
    for c in rows:
        if c.get("status") not in OPEN_STATES:
            continue
        for leg in c.get("legs") or []:
            if leg.get("won") is not None:
                continue
            ko = leg.get("ko") or leg.get("kickoff")
            if ko:
                try:
                    t = dt.datetime.strptime(str(ko)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=S.TSI)
                    if t + dt.timedelta(hours=horizon_h) < now:
                        continue
                except ValueError:
                    pass
            k = str(leg.get("code"))
            out[k] = out.get(k, 0) + 1
    return out


def with_mode(cfg: GuardConfig, **kw: Any) -> GuardConfig:
    return replace(cfg, **kw)
