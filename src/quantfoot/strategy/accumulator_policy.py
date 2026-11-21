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


# ====================================================================== kasa dağıtımı ve risk

def _eligible(ev_: CouponEvaluation, cfg: PolicyConfig) -> bool:
    """Sert kural: kupon EV ≥ eşik VE her bacak EV ≥ 0 (dolgu yok) VE politika nedenleri boş."""
    return (not ev_.reasons and ev_.ev >= cfg.min_coupon_ev and all(l.ev >= 0 for l in ev_.legs))


def round_stake(amount: float, step: float, min_stake: float) -> float:
    amt = math.floor(amount / step + 1e-9) * step
    return float(amt) if amt >= min_stake else 0.0


def allocate_budget(coupons: Sequence[CouponEvaluation], bankroll: float, cfg: PolicyConfig = PolicyConfig(),
                    fill_budget: bool = True) -> list[float]:
    """Günlük bütçeyi yalnız +EV kuponlara, kesirli Kelly ağırlığıyla dağıt.

    * ``fill_budget=True``: bütçe = kasa × ``max_daily_frac``; kuponlara Kelly ağırlığıyla orantılı dağıtılır
      (kullanıcı ayarı; tam Kelly'yi aşabilir — risk raporu bunu gösterir).
    * ``fill_budget=False``: her kupon yalnız kendi kesirli Kelly payını alır (klasik).
    Her kupon ≤ kasa × ``max_stake_frac``; paylar ``stake_step`` katına aşağı yuvarlanır, ``min_stake`` altı 0.
    +EV kupon yoksa hepsi 0.
    """
    n = len(coupons)
    weights = []
    for c in coupons:
        if not _eligible(c, cfg) or c.odds <= 1:
            weights.append(0.0)
            continue
        full = (c.prob * c.odds - 1.0) / (c.odds - 1.0)
        p_sd = c.prob * c.log_prob_sd
        se = c.odds * p_sd
        edge = c.prob * c.odds - 1.0
        shrink = edge * edge / (edge * edge + se * se) if se > 0 else 1.0
        weights.append(max(0.0, cfg.kelly_multiplier * full * shrink))
    if sum(weights) <= 0:
        return [0.0] * n
    cap = cfg.max_stake_frac * bankroll
    if not fill_budget:
        raw = [min(w * bankroll, cap) for w in weights]
    else:
        budget = cfg.max_daily_frac * bankroll
        raw = [0.0] * n
        active = [i for i in range(n) if weights[i] > 0]
        remaining = budget
        while active and remaining > 1e-9:
            wsum = sum(weights[i] for i in active)
            nxt = []
            spent = 0.0
            for i in active:
                add = remaining * weights[i] / wsum
                room = cap - raw[i]
                take = min(add, room)
                raw[i] += take
                spent += take
                if raw[i] < cap - 1e-9:
                    nxt.append(i)
            remaining -= spent
            if spent <= 1e-9:
                break
            active = nxt
    stakes = [round_stake(r, cfg.stake_step, cfg.min_stake) for r in raw]
    if fill_budget:  # yuvarlamadan kalan 5 TL'leri en yüksek Kelly ağırlıklı, tavanı dolmamış kuponlara ver
        left = cfg.max_daily_frac * bankroll - sum(stakes)
        order = sorted((i for i in range(n) if weights[i] > 0), key=lambda i: -weights[i])
        while left >= cfg.stake_step - 1e-9:
            j = next((i for i in order if stakes[i] + cfg.stake_step <= cap + 1e-9
                      and stakes[i] + cfg.stake_step >= cfg.min_stake), None)
            if j is None:
                break
            stakes[j] += cfg.stake_step
            left -= cfg.stake_step
            order = order[order.index(j) + 1:] + order[:order.index(j) + 1]  # sırayla dağıt
    total_cap = cfg.max_daily_frac * bankroll + 1e-9
    while sum(stakes) > total_cap:  # yuvarlama sonrası güvenlik
        j = max(range(n), key=lambda i: stakes[i])
        stakes[j] = round_stake(stakes[j] - cfg.stake_step, cfg.stake_step, cfg.min_stake)
    return stakes


def _leg_matrix(coupons: Sequence[CouponEvaluation]) -> tuple[list[tuple[str, str]], np.ndarray, list[list[int]]]:
    """Ortak bacak indeksleri: aynı (maç, seçim) iki kuponda ise TEK rastgele değişken (korelasyon doğru)."""
    keys: list[tuple[str, str]] = []
    probs: list[float] = []
    idx: dict[tuple[str, str], int] = {}
    members: list[list[int]] = []
    for c in coupons:
        mem = []
        for l in c.legs:
            k = (l.match_id, l.selection)
            if k not in idx:
                idx[k] = len(keys)
                keys.append(k)
                probs.append(l.prob)
            mem.append(idx[k])
        members.append(mem)
    return keys, np.array(probs, float), members


def simulate_day(coupons: Sequence[CouponEvaluation], stakes: Sequence[float], n_sims: int = 20000,
                 prob_haircut: float = 0.0, seed: int = 7, leg_probs: np.ndarray | None = None) -> np.ndarray:
    """Bir günün net kâr/zarar dağılımı (TL). Ortak bacaklar tek değişkenle simüle edilir.
    Aynı maçın farklı seçimleri (ör. MS 1 ve MS X) ayrık olmalıdır; politika aynı maçı tek kupona sınırladığı için
    burada farklı kuponlardaki aynı maç-farklı seçim bağımsız sayılır (uyarı: yalnız politika dışı girdide)."""
    rng = np.random.default_rng(seed)
    _, p, members = _leg_matrix(coupons)
    if leg_probs is not None:
        p = leg_probs
    p = np.clip(p * (1.0 - prob_haircut), 0.0, 1.0)
    if len(p) == 0:
        return np.zeros(n_sims)
    hits = rng.random((n_sims, len(p))) < p
    pnl = np.zeros(n_sims)
    for c, s, mem in zip(coupons, stakes, members):
        if s <= 0:
            continue
        won = hits[:, mem].all(axis=1)
        pnl += np.where(won, s * (c.odds - 1.0), -s)
    return pnl


def risk_report(coupons: Sequence[CouponEvaluation], stakes: Sequence[float], bankroll: float, days: int = 30,
                n_sims: int = 4000, prob_haircut: float = 0.0, seed: int = 11) -> dict[str, float]:
    """Seçilen dağıtım her gün aynı KASA ORANLARIYLA tekrarlansa: bugünün dağılımı + ``days`` günlük patika.
    Olasılıklar modelinkiyse iyimser olabilir; ``prob_haircut`` ile stres testi yapılır."""
    total = float(sum(stakes))
    day = simulate_day(coupons, stakes, n_sims=20000, prob_haircut=prob_haircut, seed=seed)
    out = {"stake_total": total, "stake_frac": total / bankroll if bankroll else 0.0,
           "p_lose_all_today": float(np.mean(day <= -total + 1e-9)) if total > 0 else 0.0,
           "p_loss_today": float(np.mean(day < 0)), "exp_pnl_today": float(day.mean()),
           "p5_pnl_today": float(np.percentile(day, 5))}
    if total <= 0 or bankroll <= 0:
        out.update(median_end=bankroll, p_half=0.0, p_ruin=0.0, median_max_dd=0.0, log_growth=0.0)
        return out
    frac_day = simulate_day(coupons, stakes, n_sims=n_sims * days, prob_haircut=prob_haircut, seed=seed + 1) / bankroll
    r = frac_day.reshape(n_sims, days)
    with np.errstate(divide="ignore"):
        g = np.log(np.maximum(1.0 + r, 1e-12))
    path = np.exp(np.cumsum(g, axis=1))
    peak = np.maximum.accumulate(np.concatenate([np.ones((n_sims, 1)), path], axis=1), axis=1)[:, 1:]
    dd = 1.0 - path / peak
    min_frac = max(1e-9, (stakes and min(s for s in stakes if s > 0)) / bankroll)
    out.update(median_end=float(np.median(path[:, -1]) * bankroll), mean_end=float(path[:, -1].mean() * bankroll),
               p_half=float(np.mean(path.min(axis=1) < 0.5)),
               p_ruin=float(np.mean(path.min(axis=1) < min_frac)),
               median_max_dd=float(np.median(dd.max(axis=1))), log_growth=float(g.mean()))
    return out


# ====================================================================== hedef katlama

@dataclass
class TargetPlan:
    coupons: list[CouponEvaluation]
    stakes: list[float]
    p_reach: float
    p_lose_all: float
    exp_final: float
    markov_bound: float


def _candidate_coupons(legs: Sequence[Leg], cfg: PolicyConfig, max_legs: int, top_n: int = 10) -> list[CouponEvaluation]:
    best: dict[str, Leg] = {}
    for l in legs:
        if l.ev < 0 or l.ev > cfg.max_plausible_leg_ev or l.odds < cfg.min_leg_odds:
            continue
        if l.match_id not in best or l.ev > best[l.match_id].ev:
            best[l.match_id] = l
    pool = sorted(best.values(), key=lambda l: -l.ev)[:top_n]
    out = []
    for k in range(1, min(max_legs, len(pool)) + 1):
        for combo in itertools.combinations(pool, k):
            c = check_coupon(combo, cfg)
            if _eligible(c, cfg):
                out.append(c)
    return out


def plan_metrics(coupons: Sequence[CouponEvaluation], stakes: Sequence[float], bankroll: float, target: float,
                 reserve: float = 0.0, n_sims: int = 20000, seed: int = 3, prob_haircut: float = 0.0) -> TargetPlan:
    keep = [(c, st) for c, st in zip(coupons, stakes) if st > 0]
    coupons, stakes = [c for c, _ in keep], [st for _, st in keep]
    pnl = simulate_day(coupons, stakes, n_sims=n_sims, seed=seed, prob_haircut=prob_haircut)
    final = bankroll + pnl
    total = float(sum(stakes))
    exp_final = float(final.mean())
    return TargetPlan(list(coupons), list(stakes), float(np.mean(final >= target - 1e-9)),
                      float(np.mean(pnl <= -total + 1e-9)) if total > 0 else 0.0, exp_final,
                      min(1.0, exp_final / target) if target > 0 else 1.0)


def search_target_plan(legs: Sequence[Leg], bankroll: float, target_multiple: float, reserve: float = 0.0,
                       cfg: PolicyConfig = PolicyConfig(), max_coupons: int = 5, max_legs: int | None = None,
                       n_plans: int = 1500, n_sims: int = 6000, seed: int = 5) -> TargetPlan | None:
    """P(gün sonu kasa ≥ hedef) en yüksek planı ara (rastgele + açgözlü arama, ortak rastgele sayılar).

    Kısıtlar: her bacak EV ≥ 0, her kupon politikayı geçer, paylar ``stake_step`` katı, toplam ≤ kasa − rezerv.
    Not (Markov eşitsizliği): P(kasa ≥ hedef) ≤ E[kasa] / hedef — EV küçükken 10 kat hedefin olasılığı ≈ 1/10'u aşamaz.
    """
    max_legs = max_legs or cfg.max_legs
    cands = _candidate_coupons(legs, cfg, max_legs)
    if not cands:
        return None
    target = bankroll * target_multiple
    budget = max(0.0, bankroll - reserve)
    step = cfg.stake_step
    units = int(budget // step)
    if units < 1:
        return None
    rng = np.random.default_rng(seed)
    need_odds = target / max(budget, step)
    # yüksek oranlı kuponlara öncelik (hedefe ulaşmak için gereken toplam oran)
    weights = np.array([min(c.odds, need_odds * 2) * (1 + c.ev) for c in cands], float)
    weights /= weights.sum()
    best: TargetPlan | None = None
    tried: set = set()
    for t in range(n_plans):
        m = int(rng.integers(1, min(max_coupons, len(cands)) + 1))
        pick = sorted(set(rng.choice(len(cands), m, replace=False, p=weights).tolist()))
        mode = t % 3
        if mode == 0:     # eşit
            split = [units // len(pick)] * len(pick)
        elif mode == 1:   # hepsi tek kupona (ilk)
            split = [units] + [0] * (len(pick) - 1)
        else:             # rastgele
            cuts = np.sort(rng.integers(0, units + 1, len(pick) - 1))
            split = np.diff(np.concatenate([[0], cuts, [units]])).tolist()
        stakes = [u * step for u in split]
        stakes = [s if s >= cfg.min_stake else 0.0 for s in stakes]
        key = (tuple(pick), tuple(stakes))
        if key in tried or sum(stakes) <= 0:
            continue
        tried.add(key)
        plan = plan_metrics([cands[i] for i in pick], stakes, bankroll, target, reserve, n_sims=n_sims, seed=seed)
        if best is None or (plan.p_reach, plan.exp_final) > (best.p_reach, best.exp_final):
            best = plan
    if best is not None:  # son ölçüm daha çok simülasyonla
        best = plan_metrics(best.coupons, best.stakes, bankroll, target, reserve, n_sims=40000, seed=seed + 99)
    return best
