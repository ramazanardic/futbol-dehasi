"""Kombine (accumulator) politika motoru: kupon EV'si, marj bileşikleşmesi, bacak korelasyonu,
aynı maça çift maruziyet yasağı ve kesirli Kelly ile kupon başı pay.

Neden: bir kombinenin beklenen getirisi bacakların (1 + EV_i) çarpımıdır. Her bacakta büro marjı
varsa (EV_i < 0) kayıp maç sayısıyla **bileşik** büyür: 7 bacak × %-6 ≈ %-35. Pozitif EV'li tek
bacak, negatif EV'li dolgu bacaklarla birleşince değerini kaybeder. Bu modül:

* her bacağın EV'sini keskin (marjsız) olasılıkla ölçer,
* kuponu yalnız EV'yi artıran bacaklarla, en çok ``max_legs`` maçla kurar,
* aynı maçtaki iki bacağı (bağımsız sayılamaz) ortak olasılık verilmedikçe reddeder,
* aynı maçın gün içinde birden çok kupona girmesini (korelasyonlu maruziyet) engeller,
* olasılık belirsizliğini (Baker & McHale 2013) hesaba katan kesirli Kelly payı önerir.

Saf fonksiyonlar; ağ erişimi yok. Olasılıkları değiştirmez, yalnız kupon kararını ve payı verir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import math
from typing import Iterable, Sequence

import numpy as np

from quantfoot import settings as S


@dataclass(frozen=True)
class Leg:
    """Tek bacak. ``prob`` keskin/marjsız tutma olasılığı, ``odds`` oynanacak büronun (Nesine) oranı."""

    match_id: str
    selection: str
    odds: float
    prob: float
    prob_sd: float = 0.0  # olasılık tahmininin standart sapması (bilinmiyorsa 0)
    family: str = ""

    @property
    def ev(self) -> float:
        return self.prob * self.odds - 1.0

    @property
    def implied(self) -> float:
        return 1.0 / self.odds if self.odds > 0 else float("nan")


@dataclass(frozen=True)
class PolicyConfig:
    min_leg_ev: float = 0.0          # her bacak en az bu EV'de olmalı (dolgu bacak yok)
    min_coupon_ev: float = S.MIN_COUPON_EV  # kupon EV eşiği
    max_legs: int = 4                # EV'ye göre en çok bacak (marj bileşikleşmesi)
    min_leg_odds: float = 1.20
    max_coupon_odds: float = 60.0
    max_matches_per_day_exposure: int = 1  # bir maç gün içinde en çok kaç kupona girebilir
    kelly_multiplier: float = S.KELLY_MULTIPLIER
    max_stake_frac: float = S.STAKE_COUPON_FRAC   # kupon başı kasa payı tavanı (kullanıcı ayarı)
    max_daily_frac: float = S.STAKE_DAILY_FRAC    # gün toplam kasa payı tavanı (kullanıcı ayarı)
    stake_step: float = S.STAKE_STEP_TL
    min_stake: float = S.MIN_STAKE_TL
    max_plausible_leg_ev: float = 0.25  # bunun üstü referans hatası şüphesi


@dataclass
class CouponEvaluation:
    legs: tuple[Leg, ...]
    prob: float
    odds: float
    ev: float
    independent_ev: float
    margin_drag: float               # marjın kupona maliyeti: 1 - Π min(1, 1+EV_i)
    log_prob_sd: float
    reasons: list[str] = field(default_factory=list)

    @property
    def n_legs(self) -> int:
        return len(self.legs)


def coupon_probability(legs: Sequence[Leg], joint_probs: dict[str, float] | None = None) -> float:
    """Birleşik tutma olasılığı. Farklı maçlar bağımsız kabul edilir (kanıt: maçlar arası korelasyon
    ihmal edilebilir). Aynı maçtaki bacaklar için ``joint_probs[match_id]`` (skor dağılımından ortak
    olasılık) verilmelidir; verilmezse ValueError."""
    by_match: dict[str, list[Leg]] = {}
    for leg in legs:
        by_match.setdefault(leg.match_id, []).append(leg)
    p = 1.0
    for mid, group in by_match.items():
        if len(group) == 1:
            p *= group[0].prob
        else:
            if not joint_probs or mid not in joint_probs:
                raise ValueError(f"aynı maçta {len(group)} bacak ({mid}): ortak olasılık verilmeden fiyatlanamaz")
            p *= joint_probs[mid]
    return p


def evaluate_coupon(legs: Sequence[Leg], joint_probs: dict[str, float] | None = None) -> CouponEvaluation:
    legs = tuple(legs)
    odds = math.prod(leg.odds for leg in legs) if legs else 1.0
    prob = coupon_probability(legs, joint_probs)
    indep = math.prod(leg.prob for leg in legs) if legs else 1.0
    drag = 1.0 - math.prod(min(1.0, 1.0 + leg.ev) for leg in legs)
    # delta yöntemi: Var(log P) ≈ Σ (sd_i / p_i)^2
    lsd = math.sqrt(sum((leg.prob_sd / leg.prob) ** 2 for leg in legs if leg.prob > 0))
    return CouponEvaluation(legs, prob, odds, prob * odds - 1.0, indep * odds - 1.0, drag, lsd)


def margin_compounding_table(leg_ev: float, max_legs: int = 10) -> list[tuple[int, float]]:
    """Her bacak aynı EV'deyse k bacaklı kupon EV'si: (1+ev)^k - 1."""
    return [(k, (1.0 + leg_ev) ** k - 1.0) for k in range(1, max_legs + 1)]


def coupon_kelly_fraction(ev_: CouponEvaluation, cfg: PolicyConfig = PolicyConfig()) -> float:
    """Kupon tek bir ikili bahis gibi: f* = (P·O − 1)/(O − 1); Baker-McHale küçültmesi ve tavan."""
    o, p = ev_.odds, ev_.prob
    if o <= 1.0 or p <= 0.0:
        return 0.0
    edge = p * o - 1.0
    if edge <= 0.0:
        return 0.0
    full = edge / (o - 1.0)
    p_sd = p * ev_.log_prob_sd
    sigma_edge = o * p_sd
    shrink = edge * edge / (edge * edge + sigma_edge * sigma_edge) if sigma_edge > 0 else 1.0
    return float(min(cfg.kelly_multiplier * full * shrink, cfg.max_stake_frac))


def check_coupon(legs: Sequence[Leg], cfg: PolicyConfig = PolicyConfig(),
                 joint_probs: dict[str, float] | None = None) -> CouponEvaluation:
    """Kuralları uygula, nedenleri doldur. ``reasons`` boşsa kupon politikayı geçer."""
    reasons: list[str] = []
    seen: dict[str, int] = {}
    for leg in legs:
        seen[leg.match_id] = seen.get(leg.match_id, 0) + 1
    dup = [m for m, c in seen.items() if c > 1]
    if dup and not (joint_probs and all(m in joint_probs for m in dup)):
        reasons.append(f"aynı maçta birden çok bacak (bağımsız değil): {', '.join(dup)}")
        # yalnız raporlamak için saf çarpım (yanlış/iyimser olabilir); kupon zaten reddedilir
        naive = {m: math.prod(l.prob for l in legs if l.match_id == m) for m in dup}
        ev_ = evaluate_coupon(legs, {**(joint_probs or {}), **naive})
    else:
        ev_ = evaluate_coupon(legs, joint_probs)
    if len(legs) > cfg.max_legs:
        reasons.append(f"{len(legs)} bacak > en çok {cfg.max_legs} (her ek bacak marjı yeniden ekler)")
    for leg in legs:
        if leg.odds < cfg.min_leg_odds:
            reasons.append(f"{leg.match_id} {leg.selection}: oran {leg.odds:.2f} < {cfg.min_leg_odds:.2f}")
        if leg.ev < cfg.min_leg_ev:
            reasons.append(f"{leg.match_id} {leg.selection}: bacak EV {leg.ev:+.1%} < {cfg.min_leg_ev:+.1%} (dolgu bacak)")
        if leg.ev > cfg.max_plausible_leg_ev:
            reasons.append(f"{leg.match_id} {leg.selection}: EV {leg.ev:+.1%} inanılmaz yüksek (referans hatası?)")
    if ev_.odds > cfg.max_coupon_odds:
        reasons.append(f"kupon oranı {ev_.odds:.1f} > {cfg.max_coupon_odds:g}")
    if ev_.ev < cfg.min_coupon_ev:
        reasons.append(f"kupon EV {ev_.ev:+.1%} < {cfg.min_coupon_ev:+.1%}")
    ev_.reasons = reasons
    return ev_


def build_ev_coupon(candidates: Iterable[Leg], cfg: PolicyConfig = PolicyConfig(),
                    exclude_matches: Iterable[str] = ()) -> CouponEvaluation | None:
    """Adaylardan EV'yi en çok artıran kuponu açgözlü kur: maç başına en iyi EV'li tek bacak,
    EV'ye göre sırala, kupon EV'si artmaya devam ettiği sürece ve ``max_legs``'e kadar ekle.
    (1+EV) çarpımsal olduğu için EV_i > 0 olan her bacak kupon EV'sini artırır; EV_i ≤ 0 asla eklenmez.
    """
    excl = set(exclude_matches)
    best: dict[str, Leg] = {}
    for leg in candidates:
        if leg.match_id in excl or leg.odds < cfg.min_leg_odds:
            continue
        if not (cfg.min_leg_ev <= leg.ev <= cfg.max_plausible_leg_ev) or leg.ev <= 0:
            continue
        cur = best.get(leg.match_id)
        if cur is None or leg.ev > cur.ev:
            best[leg.match_id] = leg
    chosen: list[Leg] = []
    for leg in sorted(best.values(), key=lambda l: (-l.ev, l.match_id)):
        if len(chosen) >= cfg.max_legs:
            break
        if math.prod(l.odds for l in chosen) * leg.odds > cfg.max_coupon_odds:
            continue
        chosen.append(leg)
    if not chosen:
        return None
    out = check_coupon(chosen, cfg)
    return out if not out.reasons else None


class ExposureBook:
    """Gün içi maruziyet defteri: aynı maçın birden çok kupona girmesini ve gün toplam payını sınırlar."""

    def __init__(self, bankroll: float, cfg: PolicyConfig = PolicyConfig()) -> None:
        self.bankroll = float(bankroll)
        self.cfg = cfg
        self.match_count: dict[str, int] = {}
        self.staked = 0.0
        self.coupons: list[tuple[CouponEvaluation, float]] = []

    def conflicts(self, legs: Sequence[Leg]) -> list[str]:
        return sorted({l.match_id for l in legs
                       if self.match_count.get(l.match_id, 0) >= self.cfg.max_matches_per_day_exposure})

    def blocked_matches(self) -> set[str]:
        return {m for m, c in self.match_count.items() if c >= self.cfg.max_matches_per_day_exposure}

    def stake_for(self, ev_: CouponEvaluation) -> float:
        frac = coupon_kelly_fraction(ev_, self.cfg)
        room = max(0.0, self.cfg.max_daily_frac * self.bankroll - self.staked)
        return round(min(frac * self.bankroll, room), 2)

    def add(self, ev_: CouponEvaluation) -> tuple[bool, float, list[str]]:
        """Kuponu deftere eklemeyi dene → (kabul, önerilen pay TL, nedenler)."""
        reasons = list(ev_.reasons)
        c = self.conflicts(ev_.legs)
        if c:
            reasons.append("aynı maç başka kuponda (korelasyonlu maruziyet): " + ", ".join(c))
        stake = self.stake_for(ev_) if not reasons else 0.0
        if not reasons and stake <= 0:
            reasons.append("Kelly payı 0 (EV yok ya da günlük tavan doldu)")
        if reasons:
            return False, 0.0, reasons
        for leg in ev_.legs:
            self.match_count[leg.match_id] = self.match_count.get(leg.match_id, 0) + 1
        self.staked += stake
        self.coupons.append((ev_, stake))
        return True, stake, []


def build_daily_portfolio(candidates: Sequence[Leg], bankroll: float, n_coupons: int = 3,
                          cfg: PolicyConfig = PolicyConfig()) -> list[tuple[CouponEvaluation, float]]:
    """Aynı maçı tekrar kullanmadan en çok ``n_coupons`` EV-pozitif kupon kur ve payla."""
    book = ExposureBook(bankroll, cfg)
    for _ in range(n_coupons):
        cp = build_ev_coupon(candidates, cfg, exclude_matches=book.blocked_matches())
        if cp is None:
            break
        ok, _, _ = book.add(cp)
        if not ok:
            break
    return book.coupons
