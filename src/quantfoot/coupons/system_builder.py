"""Sistem kuponu optimizeri (tek-bacak sigortası + yüksek oranlı sistemler) ve çapraz kupon portföy koruması.

22 Kasım 2026 denetiminden doğdu:
  * K1 bacakları %69,6, K2 bacakları %67,9 tutmasına rağmen 6 kombine kupon YALNIZCA TEK BACAKTAN yattı.
  * Aynı tek bacak (Getafe–Atl Madrid İY 1.5 Alt) 3 kupona birden girdiği için tek sürprizle 3 kuponu birden gömdü.

Bu modül:
  1. ``evaluate_system``: Her sistem kuponu için kesin Poisson-Binomial P(≥k), her tutan maç sayısında
     min/max TL ödeme aralığı, kesin kâra geçme olasılığı (P(kazanç > maliyet)), beklenen dönüş ve MBS doğrulaması.
  2. ``optimize_system``: Verilen bütçe (ör. 50/100/250 TL) ve mod ("banko_sigorta" veya "yuksek_oran") için
     MBS uyumlu en verimli sistem kombinasyonlarını üretir.
  3. ``PortfolioExposureGuard``: Aynı gün kurulan kuponlar arasında aynı maçın/tercihin birden çok kuponu aynı
     anda yakmasını engelleyen çapraz korelasyon bekçisi.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import itertools
import math


@dataclass(frozen=True)
class SystemLeg:
    match_id: str
    match: str
    name: str
    odds: float
    p: float
    mbs: int = 1
    kickoff: str | None = None
    league: str | None = None
    consensus_dispersion: float = 0.0


@dataclass(frozen=True)
class SystemEvaluation:
    n_legs: int
    sizes: tuple[int, ...]
    n_cols: int
    stake_per_col: float
    total_cost: float
    max_payout: float
    effective_max_odds: float
    expected_return: float
    roi: float
    p_profit: float
    p_at_least: dict[int, float]
    hit_table: dict[int, tuple[float, float]]
    mbs_ok: bool
    mbs_required: int
    legs: tuple[SystemLeg, ...] = ()


def poisson_binomial_tail(probs: Sequence[float]) -> dict[int, float]:
    """Kesin Poisson-Binomial dağılımıyla P(tutan >= k), k = 0..n."""
    n = len(probs)
    dp = [1.0] + [0.0] * n
    for p in probs:
        p = min(1.0, max(0.0, float(p)))
        ndp = [0.0] * (n + 1)
        for j in range(n + 1):
            ndp[j] += dp[j] * (1.0 - p)
            if j + 1 <= n:
                ndp[j + 1] += dp[j] * p
        dp = ndp
    out: dict[int, float] = {}
    running = 0.0
    for k in range(n, -1, -1):
        running += dp[k]
        out[k] = round(min(1.0, running), 8)
    return out


def evaluate_system(
    legs: Sequence[SystemLeg],
    sizes: Sequence[int],
    stake_per_col: float = 1.0,
) -> SystemEvaluation:
    """Bir sistem kuponunu tüm alt-kümeler ve kesin olasılıklarla değerlendir."""
    if not legs:
        raise ValueError("Sistem kuponu için en az 1 bacak gerekir.")
    clean_sizes = tuple(sorted({int(k) for k in sizes if 1 <= int(k) <= len(legs)}))
    if not clean_sizes:
        raise ValueError("Geçerli sistem boyutu yok.")
    if stake_per_col <= 0:
        raise ValueError("Kolon tutarı pozitif olmalı.")

    n = len(legs)
    mbs_req = max(int(lg.mbs or 1) for lg in legs)
    mbs_ok = min(clean_sizes) >= mbs_req

    n_cols = sum(math.comb(n, k) for k in clean_sizes)
    total_cost = round(n_cols * stake_per_col, 2)
    odds = [float(lg.odds) for lg in legs]
    probs = [min(1.0, max(0.0, float(lg.p))) for lg in legs]

    p_tail = poisson_binomial_tail(probs)

    # Her alt-küme boyutu m için min/max ödeme + n <= 12 için kesin p_profit hesabı
    hit_table: dict[int, tuple[float, float]] = {}
    p_profit = 0.0
    for m in range(min(clean_sizes), n + 1):
        lo = float("inf")
        hi = 0.0
        for sub in itertools.combinations(range(n), m):
            sub_pay = 0.0
            for k in clean_sizes:
                if k <= m:
                    for comb in itertools.combinations(sub, k):
                        sub_pay += math.prod(odds[i] for i in comb) * stake_per_col
            if sub_pay < lo:
                lo = sub_pay
            if sub_pay > hi:
                hi = sub_pay
            if n <= 12 and sub_pay > total_cost + 1e-9:
                sub_set = set(sub)
                p_sub = math.prod(probs[i] if i in sub_set else (1.0 - probs[i]) for i in range(n))
                p_profit += p_sub
        hit_table[m] = (round(lo, 2), round(hi, 2))

    # Eğer n > 12 ise p_profit alt sınırı: min ödeme > maliyet olan ilk m'nin kuyruk olasılığı
    if n > 12:
        for m in range(min(clean_sizes), n + 1):
            if hit_table[m][0] > total_cost + 1e-9:
                p_profit = p_tail[m]
                break

    exp_ret = 0.0
    for k in clean_sizes:
        for comb in itertools.combinations(range(n), k):
            exp_ret += math.prod(probs[i] * odds[i] for i in comb) * stake_per_col

    max_payout = hit_table[n][1]
    return SystemEvaluation(
        n_legs=n,
        sizes=clean_sizes,
        n_cols=n_cols,
        stake_per_col=round(stake_per_col, 2),
        total_cost=total_cost,
        max_payout=round(max_payout, 2),
        effective_max_odds=round(max_payout / total_cost, 2) if total_cost > 0 else 0.0,
        expected_return=round(exp_ret, 2),
        roi=round((exp_ret - total_cost) / total_cost, 4) if total_cost > 0 else 0.0,
        p_profit=round(min(1.0, p_profit), 6),
        p_at_least=p_tail,
        hit_table=hit_table,
        mbs_ok=mbs_ok,
        mbs_required=mbs_req,
        legs=tuple(legs),
    )


def optimize_system(
    legs: Sequence[SystemLeg],
    budget_tl: float,
    *,
    mode: str = "banko_sigorta",
    min_col_stake: float = 1.0,
    top_n: int = 3,
) -> list[SystemEvaluation]:
    """Verilen bütçeye ve moda göre MBS uyumlu en iyi sistem kuponu adaylarını döndürür.

    * ``banko_sigorta``: Tek-bacak (n-1, n) veya çift-bacak (n-2, n-1, n) sigortalı yapılar;
      kâra geçme olasılığı + beklenen dönüş sıralı.
    * ``yuksek_oran``: 2/1–1/2, 6+ Gol, İki Yarıda KG gibi yüksek oranlı maçlar için
      en yüksek P(≥min_k) + yüksek tavan oran + bütçeyi verimli kullanan yapılar.
    """
    n = len(legs)
    if n < 2 or budget_tl < min_col_stake:
        return []
    mbs_req = max(int(lg.mbs or 1) for lg in legs)
    min_k = max(2, mbs_req)
    if min_k > n:
        return []

    candidate_sizes: list[tuple[int, ...]] = []
    if mode == "banko_sigorta":
        # Tek-bacak ve çift-bacak sigortaları
        if n - 1 >= min_k:
            candidate_sizes.append((n - 1, n))
        if n - 2 >= min_k:
            candidate_sizes.append((n - 2, n - 1, n))
        candidate_sizes.append((n,))
        if min_k <= n - 1:
            candidate_sizes.append((n - 1,))
    else:
        # Yüksek oranlı sistemler: ikili + üçlü çekirdek + tavan kombinasyonları
        for sz in (
            (min_k,),
            (min_k, min_k + 1),
            (min_k, min_k + 1, n),
            (min_k, min_k + 1, min_k + 2),
            (min_k, min_k + 1, n - 1, n),
            (min_k, min_k + 1, min_k + 2, n),
            (min_k, min_k + 1, min_k + 2, n - 1, n),
            tuple(range(min_k, n + 1)),
        ):
            clean = tuple(sorted({k for k in sz if min_k <= k <= n}))
            if clean and clean not in candidate_sizes:
                candidate_sizes.append(clean)

    evals: list[SystemEvaluation] = []
    seen: set[tuple[tuple[int, ...], int]] = set()
    for sz in candidate_sizes:
        n_cols = sum(math.comb(n, k) for k in sz)
        max_mult = int(budget_tl // (n_cols * min_col_stake))
        if max_mult < 1:
            continue
        stake = max_mult * min_col_stake
        key = (sz, int(round(stake * 100)))
        if key in seen:
            continue
        seen.add(key)
        ev = evaluate_system(legs, sz, stake_per_col=stake)
        if ev.mbs_ok and ev.total_cost <= budget_tl + 1e-9:
            evals.append(ev)

    if mode == "banko_sigorta":
        evals.sort(key=lambda e: (e.p_profit, e.expected_return, -len(e.sizes)), reverse=True)
    else:
        evals.sort(key=lambda e: (e.p_profit, e.total_cost / budget_tl, math.log10(max(1.0, e.effective_max_odds))), reverse=True)
    return evals[:top_n]


@dataclass
class PortfolioAudit:
    ok: bool
    n_coupons: int
    duplicate_selections: list[str] = field(default_factory=list)
    overexposed_matches: list[str] = field(default_factory=list)
    concentration_score: float = 0.0  # 0 = tam bağımsız, 100 = tüm kuponlar aynı maça bağlı


class PortfolioExposureGuard:
    """Birden çok kuponda aynı maçın / aynı bacağın ortak çöküş (correlation wipeout) riskini engeller.

    22 Kas dersi: Getafe–Atl Madrid İY 1.5 Alt aynı anda 3 kuponda yer aldığı için tek sürprizle
    #1, #32 ve #33'ün üçünü birden yatırdı.
    """

    def __init__(self, *, max_coupons_per_match: int = 1, max_coupons_per_selection: int = 1) -> None:
        self.max_coupons_per_match = max(1, int(max_coupons_per_match))
        self.max_coupons_per_selection = max(1, int(max_coupons_per_selection))
        self._match_coupons: dict[str, list[str]] = {}
        self._sel_coupons: dict[tuple[str, str], list[str]] = {}
        self._coupon_ids: list[str] = []

    def can_add_leg(self, coupon_id: str, match_id: str, selection_name: str) -> tuple[bool, str]:
        mid = str(match_id)
        skey = (mid, selection_name.strip())
        cur_s = [c for c in self._sel_coupons.get(skey, []) if c != coupon_id]
        if len(cur_s) >= self.max_coupons_per_selection:
            return False, f"aynı tercih ({mid}|{selection_name}) zaten {cur_s[0]} kuponunda var"
        cur_m = [c for c in self._match_coupons.get(mid, []) if c != coupon_id]
        if len(cur_m) >= self.max_coupons_per_match:
            return False, f"aynı maç ({mid}) zaten {len(cur_m)} kuponda (sınır {self.max_coupons_per_match})"
        return True, ""

    def register_coupon(self, coupon_id: str, legs: Sequence[SystemLeg]) -> list[str]:
        """Kuponu kaydet ve varsa çapraz korelasyon ihlallerini döndür."""
        issues: list[str] = []
        if coupon_id not in self._coupon_ids:
            self._coupon_ids.append(coupon_id)
        for lg in legs:
            ok, why = self.can_add_leg(coupon_id, lg.match_id, lg.name)
            if not ok:
                issues.append(f"{coupon_id} · {lg.match} ({lg.name}): {why}")
            self._match_coupons.setdefault(str(lg.match_id), []).append(coupon_id)
            self._sel_coupons.setdefault((str(lg.match_id), lg.name.strip()), []).append(coupon_id)
        return issues

    def audit(self) -> PortfolioAudit:
        dup_sels = [
            f"{mid}|{nm} -> {', '.join(cids)}"
            for (mid, nm), cids in self._sel_coupons.items()
            if len(set(cids)) > self.max_coupons_per_selection
        ]
        over_m = [
            f"{mid} -> {len(set(cids))} kupon ({', '.join(sorted(set(cids)))})"
            for mid, cids in self._match_coupons.items()
            if len(set(cids)) > self.max_coupons_per_match
        ]
        n_c = max(1, len(self._coupon_ids))
        max_overlap = max((len(set(cids)) for cids in self._match_coupons.values()), default=0)
        conc = round(100.0 * max(0, max_overlap - 1) / max(1, n_c - 1), 1) if n_c > 1 else 0.0
        return PortfolioAudit(
            ok=not dup_sels and not over_m,
            n_coupons=len(self._coupon_ids),
            duplicate_selections=dup_sels,
            overexposed_matches=over_m,
            concentration_score=conc,
        )


@dataclass(frozen=True)
class CapitalShieldTicket:
    ticket_no: int
    legs: tuple[SystemLeg, ...]
    total_odds: float
    p_win: float
    ev: float
    stake_tl: float
    potential_payout_tl: float


@dataclass(frozen=True)
class CapitalShieldPlan:
    bankroll_tl: float
    total_staked_tl: float
    daily_risk_pct: float
    tickets: tuple[CapitalShieldTicket, ...]
    skipped_low_ev: int
    notes: tuple[str, ...] = ()


def build_capital_shield_plan(
    candidates: Sequence[SystemLeg],
    *,
    bankroll_tl: float = 1000.0,
    max_tickets: int = 3,
    legs_per_ticket: int = 3,
    min_ev: float = -0.10,
    min_p: float = 0.60,
    max_stake_frac: float = 0.03,
    max_daily_frac: float = 0.10,
    step_tl: float = 10.0,
    drawdown_pct: float = 0.0,
    max_drawdown_stop: float = 0.25,
) -> CapitalShieldPlan:
    """Kasa koruma planı: yüksek Nesine marjlı 5–6'lı kombine yerine düşük-bacaklı (2–3 maç) ve EV tabanlı kuponlar.

    22 Kasım 2026 (428 maç / 1.838 seçim) bulgusu:
      * EV < -%14 bacaklar 1u ROI -%17,3 (5'li kombinede -%61 beklenen kayıp!).
      * EV >= -%10 bacaklar 17/20 (%85,0 isabet, +%20,8 1u ROI).
      * Kasa başına kupon tavanı %3 ve günlük toplam risk tavanı %10 ile tek kötü günde sermaye erimesi engellenir.
      * PortfolioExposureGuard ile hiçbir maç iki kupona birden girmez (sıfır çapraz çöküş).
      * Drawdown (sermaye düşüşü) %25+ olduğunda devre kesici otomatik PAS geçer; ara düşüşlerde ve
        keskin büro dağılımı (consensus_dispersion) yüksek bacaklarda tutar otomatik kısılır.
    """
    if bankroll_tl <= 0 or legs_per_ticket < 1 or max_tickets < 1:
        return CapitalShieldPlan(bankroll_tl, 0.0, 0.0, (), 0, ("Geçersiz bütçe veya kupon parametresi.",))

    dd = max(0.0, float(drawdown_pct))
    if dd >= max_drawdown_stop:
        return CapitalShieldPlan(
            round(bankroll_tl, 2), 0.0, 0.0, (), 0,
            (f"Devre kesici aktif (drawdown %{100*dd:.1f} ≥ %{100*max_drawdown_stop:.0f}) — BUGÜN PAS (kasa korundu).",),
        )

    # Maç başına en yüksek EV'li (eşitlikte en yüksek P) bacağı seç, EV tabanı ve MBS sınırını uygula
    best_by_match: dict[str, SystemLeg] = {}
    skipped_low_ev = 0
    for lg in candidates:
        ev = lg.p * lg.odds - 1.0
        if lg.p < min_p or lg.odds < 1.20 or int(lg.mbs or 1) > legs_per_ticket:
            continue
        if ev < min_ev - 1e-9:
            skipped_low_ev += 1
            continue
        prev = best_by_match.get(lg.match_id)
        if prev is None or (ev, lg.p) > (prev.p * prev.odds - 1.0, prev.p):
            best_by_match[lg.match_id] = lg

    ranked = sorted(best_by_match.values(), key=lambda x: (-(x.p * x.odds - 1.0), -x.p, x.match_id))
    guard = PortfolioExposureGuard(max_coupons_per_match=1, max_coupons_per_selection=1)

    dd_scale = max(0.25, 1.0 - dd / max(max_drawdown_stop + 0.05, 0.30)) if dd > 0.0 else 1.0
    max_daily_tl = bankroll_tl * max_daily_frac * dd_scale
    raw_per_ticket = min(bankroll_tl * max_stake_frac * dd_scale, max_daily_tl / max_tickets)
    base_stake_tl = max(step_tl, math.floor(raw_per_ticket / step_tl) * step_tl) if raw_per_ticket >= step_tl else round(raw_per_ticket, 2)

    tickets: list[CapitalShieldTicket] = []
    total_staked = 0.0
    throttled_dispersion = 0
    idx = 0
    for tno in range(1, max_tickets + 1):
        if idx + legs_per_ticket > len(ranked):
            break
        batch = tuple(ranked[idx : idx + legs_per_ticket])
        idx += legs_per_ticket
        cid = f"kasa_koruma_{tno}"
        if guard.register_coupon(cid, batch):
            continue
        max_disp = max((float(getattr(x, "consensus_dispersion", 0.0) or 0.0) for x in batch), default=0.0)
        ticket_raw = base_stake_tl
        if max_disp > 0.035:
            ticket_raw = base_stake_tl * 0.70
            throttled_dispersion += 1
        stake_tl = max(step_tl, math.floor(ticket_raw / step_tl) * step_tl) if ticket_raw >= step_tl else round(ticket_raw, 2)
        if total_staked + stake_tl > max_daily_tl + 1e-9:
            break
        tot_odds = round(math.prod(x.odds for x in batch), 2)
        p_win = round(math.prod(x.p for x in batch), 4)
        ev = round(p_win * tot_odds - 1.0, 4)
        tickets.append(CapitalShieldTicket(
            ticket_no=tno,
            legs=batch,
            total_odds=tot_odds,
            p_win=p_win,
            ev=ev,
            stake_tl=round(stake_tl, 2),
            potential_payout_tl=round(stake_tl * tot_odds, 2),
        ))
        total_staked += stake_tl

    notes: list[str] = []
    if dd > 0.0:
        notes.append(f"Drawdown freni aktif (%{100*dd:.1f} düşüş → tutar çarpanı {dd_scale:.2f}x).")
    if throttled_dispersion:
        notes.append(f"{throttled_dispersion} kuponda yüksek keskin büro dağılımı nedeniyle tutar %30 kısıldı.")
    if not tickets:
        notes.append(f"EV ≥ %{100*min_ev:+.0f} ve P ≥ %{100*min_p:.0f} kasa koruma eşiğini geçen yeterli maç yok — BUGÜN PAS (kasa korundu).")
    if skipped_low_ev:
        notes.append(f"{skipped_low_ev} yüksek Nesine marjlı bacak (EV < %{100*min_ev:+.0f}) kasa koruma kalkanıyla elendi.")
    return CapitalShieldPlan(
        bankroll_tl=round(bankroll_tl, 2),
        total_staked_tl=round(total_staked, 2),
        daily_risk_pct=round(100.0 * total_staked / bankroll_tl, 2) if bankroll_tl > 0 else 0.0,
        tickets=tuple(tickets),
        skipped_low_ev=skipped_low_ev,
        notes=tuple(notes),
    )
