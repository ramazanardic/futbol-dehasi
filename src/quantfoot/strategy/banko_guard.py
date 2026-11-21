"""Banko/garanti kupon koruması — 21 Kasım 2026 denetiminden çıkan kurallar.

Kullanıcı kuralı (t57u): varsayılan banko kupon; her bacak yüksek olasılıklı (P ≥ %65, oran ≈1.20–1.80),
tek bir yüksek oranlı riskli bacakla toplam şişirilmez. Denetimde görülen hatalar ve karşılık gelen kural:

* Kupon 1–6 (≈20–26 oran) 2.3–4.1 oranlı beraberlik/İY bacaklarıyla kuruldu, P(kupon) %2.5–3.5 → ``LOTTERY_P_WIN``.
* Pécs "Dep 0,5 Alt" Nesine bülteninde yoktu, kupon kurulamadı → ``offered`` zorunlu.
* 1.20–1.21'lik bacaklar oynarken 1.17/1.19'a düştü → seçim anında ``BANKO_SELECT_MIN_ODDS`` tamponu.
* Canlı bacaklar doğrulanmamış canlı modelin P'siyle seçildi (piyasadan +14 puan) → canlıda piyasa P'si zorunlu.
* Aynı maç birden çok kuponda (Linfield, Catanzaro, Elche B, Coleraine) → ``BANKO_MAX_COUPONS_PER_MATCH``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from quantfoot import settings as S


@dataclass(frozen=True)
class BankoLeg:
    match_id: str | int
    label: str
    odds: float
    p: float                       # kalibre/piyasaya büzülmüş olasılık
    offered: bool = True           # seçim Nesine bülteninde birebir var mı
    sharp_ref: bool = True         # keskin (marjsız) referans fiyatı var mı
    live: bool = False
    p_market: float | None = None  # canlı bacakta marjsız piyasa P'si
    red_flags: tuple[str, ...] = ()


@dataclass
class GuardConfig:
    min_prob: float = S.BANKO_MIN_PROB
    min_odds: float = S.MIN_LEG_ODDS
    select_min_odds: float = S.BANKO_SELECT_MIN_ODDS
    max_leg_odds: float = S.BANKO_MAX_LEG_ODDS
    max_coupons_per_match: int = S.BANKO_MAX_COUPONS_PER_MATCH
    lottery_p_win: float = S.LOTTERY_P_WIN
    require_sharp: bool = True


DEFAULT = GuardConfig()


@dataclass
class GuardResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_odds: float = 1.0
    p_win: float = 1.0


def check_leg(leg: BankoLeg, cfg: GuardConfig = DEFAULT, at_selection: bool = True) -> tuple[list[str], list[str]]:
    err: list[str] = []
    warn: list[str] = []
    if not leg.offered:
        err.append(f"{leg.label}: seçim Nesine bülteninde yok (türetilmiş fiyat)")
    if leg.odds < cfg.min_odds:
        err.append(f"{leg.label}: oran {leg.odds:.2f} < {cfg.min_odds:.2f}")
    elif at_selection and leg.odds < cfg.select_min_odds:
        warn.append(f"{leg.label}: oran {leg.odds:.2f} tabana çok yakın, oynarken {cfg.min_odds:.2f} altına düşebilir")
    if leg.odds > cfg.max_leg_odds:
        err.append(f"{leg.label}: oran {leg.odds:.2f} > {cfg.max_leg_odds:.2f} (banko değil)")
    p = leg.p
    if leg.live:
        if leg.p_market is None:
            err.append(f"{leg.label}: canlı bacakta piyasa olasılığı yok (model tek başına kullanılamaz)")
        else:
            p = min(p, leg.p_market + 0.05)   # canlıda piyasanın +5 puan üstüne güvenme
    if p < cfg.min_prob:
        err.append(f"{leg.label}: P {p:.2f} < {cfg.min_prob:.2f}")
    if cfg.require_sharp and not leg.sharp_ref and not leg.live:
        err.append(f"{leg.label}: keskin referans fiyatı yok")
    for f in leg.red_flags:
        err.append(f"{leg.label}: kırmızı bayrak — {f}")
    return err, warn


def check_coupon(legs: Sequence[BankoLeg], open_exposure: Mapping[str | int, int] | None = None,
                 cfg: GuardConfig = DEFAULT, at_selection: bool = True) -> GuardResult:
    """Banko modunda kupon denetimi. ``open_exposure``: maç → bu maçı içeren açık kupon sayısı."""
    res = GuardResult(ok=True)
    seen: set = set()
    for leg in legs:
        e, w = check_leg(leg, cfg, at_selection)
        res.errors += e
        res.warnings += w
        if leg.match_id in seen:
            res.errors.append(f"{leg.label}: aynı maçtan ikinci seçim (korelasyon)")
        seen.add(leg.match_id)
        n_open = (open_exposure or {}).get(leg.match_id, 0)
        if n_open + 1 > cfg.max_coupons_per_match:
            res.errors.append(f"{leg.label}: bu maç zaten {n_open} açık kuponda (en çok {cfg.max_coupons_per_match})")
    res.total_odds = math.prod(l.odds for l in legs) if legs else 1.0
    res.p_win = math.prod(l.p for l in legs) if legs else 1.0
    if legs and res.p_win < cfg.lottery_p_win:
        res.errors.append(f"P(kupon) %{100 * res.p_win:.1f} < %{100 * cfg.lottery_p_win:.0f}: piyango kuponu, banko değil")
    res.ok = not res.errors
    return res


def max_banko_total(n_legs: int, cfg: GuardConfig = DEFAULT, leg_margin: float = 0.12) -> float:
    """P ≥ min_prob bacaklarla ulaşılabilecek kaba en yüksek toplam oran (Nesine bacak başı pay ≈ %8–13)."""
    leg = min(cfg.max_leg_odds, 1.0 / (cfg.min_prob * (1.0 + leg_margin)))
    return leg ** n_legs
