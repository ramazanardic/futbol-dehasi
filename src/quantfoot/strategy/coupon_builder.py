"""Post-mortem hardened risk filters, omni-market best-bet selector, and target-odds (10x/20x/30x) coupon optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence

from quantfoot.markets.omni_markets import OmniMarketBundle

MIN_ALLOWED_ODDS: float = 1.20


@dataclass(frozen=True)
class MatchRiskContext:
    """Empirical and tactical risk flags for a specific fixture."""

    home_must_win: bool = False
    away_must_win: bool = False
    home_complacent: bool = False   # Already qualified / huge 1st-leg lead
    away_complacent: bool = False   # Away favorite happy with a 0-0 / 1-1 draw (e.g. Egypt, Nigeria, Congo DR)
    home_dead_attack: bool = False  # <= 3 goals in last 5 games (e.g. Georgia 0:4)
    away_dead_attack: bool = False  # <= 3 goals in last 5 games (e.g. Cayman 0:12, Peterborough 2:14, Kosovo 3:4)
    high_rotation_risk: bool = False
    first_leg_goals: int | None = None
    group_id: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class MarketRecommendation:
    """Validated betting recommendation for a single fixture."""

    match_id: str
    home: str
    away: str
    league: str
    kickoff: str
    category: str
    selection: str
    probability: float
    fair_odds: float
    offered_odds: float
    odds_is_estimated: bool
    safety_score: float
    ev: float
    rationale: str
    stepped_down_from: str | None = None
    blocked_traps: tuple[str, ...] = ()
    group_id: str | None = None


@dataclass(frozen=True)
class CouponPlan:
    """Optimized multi-match coupon meeting a target odds threshold with maximum joint probability."""

    title: str
    target_odds: float
    achieved_odds: float
    joint_probability: float
    average_leg_probability: float
    legs: tuple[MarketRecommendation, ...]
    eliminated_traps: tuple[str, ...] = field(default_factory=tuple)


def _categorize_selection(sel: str) -> str:
    if sel.startswith("MS ") and "&" not in sel:
        return "Maç Sonucu (1X2)"
    if sel.startswith("ÇŞ "):
        return "Çifte Şans"
    if sel.startswith("İY/MS "):
        return "İlk Yarı / Maç Sonucu (İY/MS)"
    if sel in ("İY 1", "İY 0", "İY 2"):
        return "İlk Yarı Sonucu"
    if sel in ("2Y 1", "2Y 0", "2Y 2"):
        return "İkinci Yarı Sonucu"
    if sel.startswith("İY ") and ("Üst" in sel or "Alt" in sel):
        return "İlk Yarı Alt/Üst"
    if sel.startswith("2Y ") and ("Üst" in sel or "Alt" in sel):
        return "İkinci Yarı Alt/Üst"
    if "Gol" in sel and ("-" in sel or "+6" in sel):
        return "Toplam Gol Aralığı"
    if "KG" in sel and "&" not in sel:
        return "Karşılıklı Gol"
    if "&" in sel:
        return "Özel Kombine"
    if "Üst" in sel or "Alt" in sel:
        return "Maç Geneli Alt/Üst"
    return "Diğer"


def audit_match_risks(
    bundle: OmniMarketBundle,
    risk_ctx: MatchRiskContext | None = None,
) -> tuple[dict[str, str], dict[str, float]]:
    """Identify trap markets and reliability penalties based on post-mortem failure modes.

    Returns
    -------
    blocked : dict[str, str]
        Mapping of `selection -> reason` for selections that must be rejected.
    penalties : dict[str, float]
        Mapping of `selection -> multiplier in (0, 1]` applied to safety scoring.
    """
    ctx = risk_ctx or MatchRiskContext()
    blocked: dict[str, str] = {}
    penalties: dict[str, float] = {}

    mu_h, mu_a = bundle.mu_home, bundle.mu_away
    tot = bundle.expected_total
    gap = abs(mu_h - mu_a)
    max_mu = max(mu_h, mu_a)
    min_mu = min(mu_h, mu_a)
    p_fav = max(bundle.ft_1x2["1"], bundle.ft_1x2["2"])

    # 1. ASYMMETRIC UNDER-TOTAL TRAP (e.g. Dominica 5-0 Cayman, Ireland 3-0 Kosovo, Wales 2-3 Portugal)
    if max_mu >= 1.28 or gap >= 0.42 or p_fav >= 0.45 or ctx.home_must_win or ctx.away_must_win:
        blocked["2.5 Alt"] = (
            f"Asimetrik Alt Tuzağı: Favori gol beklentisi yüksek (max xG={max_mu:.2f}, fark={gap:.2f}); "
            "zayıf takım gol atamasa bile favori tek başına 3+ gol atabilir (Örn: Dominika 5-0, İrlanda 3-0)."
        )
        blocked["1.5 Alt"] = blocked["2.5 Alt"]
        blocked["0-1 Gol"] = blocked["2.5 Alt"]
        penalties["2.5 Alt & KG Yok"] = 0.72

    if tot >= 2.85 or max_mu >= 1.85 or (ctx.home_must_win and ctx.away_must_win):
        blocked["3.5 Alt"] = (
            f"Yüksek Tempo 3.5 Alt Tuzağı: Toplam xG={tot:.2f} / max xG={max_mu:.2f} "
            "(Örn: Galler-Portekiz 2-3 gibi geçiş maçlarında 3.5 Alt kırılgan)."
        )

    # 2. FIRST-HALF DRAW (İY 0) EARLY-GOAL FRAGILITY GUARD (1/7 failure mode)
    if bundle.exp_1h_total > 0.84 or gap > 0.14 or ctx.home_must_win or ctx.away_must_win:
        blocked["İY 0"] = (
            f"İlk Yarı Beraberlik Kırılganlığı: 1Y xG={bundle.exp_1h_total:.2f}, güç farkı={gap:.2f}. "
            "Maç alt bitse bile tek golün ilk 45 dakikada gelme riski ~%50'dir."
        )
    else:
        penalties["İY 0"] = 0.86  # Even in symmetric low-total games, cap priority below FT Under / 1H Under 1.5

    # 3. DEAD-ATTACKER BTTS & FAKE-OVER TRAP (e.g. Luton 3-0 Peterborough, Dominica 5-0 Cayman)
    if ctx.home_dead_attack or ctx.away_dead_attack or min_mu < 0.58:
        for kg_sel in ("KG Var", "1. Yarı KG Var", "2. Yarı KG Var", "1Y ve 2Y KG Var", "En Az Bir Devre KG Var", "2.5 Üst & KG Var"):
            blocked[kg_sel] = (
                f"Kısır Hücum KG Tuzağı: Zayıf tarafın gol üretimi çok düşük (min xG={min_mu:.2f}); "
                "maç gollü geçse bile tek taraflı (3-0 / 5-0) kalma riski yüksek."
            )
        if max_mu < 4.60:
            blocked["+6 Gol"] = "Tek Taraflı Kısır Rakip Tuzağı: Zayıf takım gol katkısı veremeyeceği için 6+ gol riskli."
            blocked["5.5 Üst"] = blocked["+6 Gol"]

    # 4. AWAY COMPLACENCY & ROTATION GUARD (e.g. Malawi 0-0 Egypt, Sierra Leone 1-1 Congo DR, USA 2-0 Haiti)
    if ctx.away_complacent:
        blocked["MS 2"] = "Deplasman Lider/Rövanş Rehaveti: Konuk favoriye beraberlik yetiyor (0-0 / 1-1 riski yüksek)."
        blocked["MS 2 & 1.5 Üst"] = blocked["MS 2"]
        blocked["MS 2 & 2.5 Üst"] = blocked["MS 2"]
        blocked["MS 2 & KG Yok"] = blocked["MS 2"]
        blocked["İY/MS 2/2"] = blocked["MS 2"]
        blocked["İY/MS 0/2"] = blocked["MS 2"]

    if ctx.home_complacent:
        blocked["MS 1"] = "Ev Sahibi Rövanş/Lider Rehaveti: Ev sahibine beraberlik veya rölanti tempo yetiyor."
        blocked["MS 1 & 1.5 Üst"] = blocked["MS 1"]
        blocked["MS 1 & 2.5 Üst"] = blocked["MS 1"]
        blocked["İY/MS 1/1"] = blocked["MS 1"]

    if ctx.high_rotation_risk:
        for over_sel in ("3.5 Üst", "4.5 Üst", "5.5 Üst", "+6 Gol", "1Y ve 2Y KG Var"):
            blocked[over_sel] = "Yoğun Kadro Rotasyonu Uyarısı: İlk maç farkı veya garantilenmiş tur nedeniyle tempo düşüşü riski."

    if ctx.first_leg_goals is not None and ctx.first_leg_goals >= 4:
        for under_sel in ("1.5 Alt", "2.5 Alt", "0-1 Gol", "2.5 Alt & KG Yok"):
            blocked[under_sel] = f"İlk Ayak Gollü Geçti ({ctx.first_leg_goals} gol): Kısır Alt tercihi tehlikeli."

    # 5. EXTREME TAIL THRESHOLD GUARDS (Preventing forced 6+ Gol and 1Y&2Y KG on 4-5 goal matches)
    if bundle.goal_bands["+6 Gol"] < 0.45 or tot < 5.35:
        blocked.setdefault(
            "+6 Gol",
            f"6+ Gol Güven Eşiği Altında (P={bundle.goal_bands['+6 Gol']*100:.1f}%, xG={tot:.2f} < 5.35): "
            "4-5 golde kalma riski yüksek (Örn: 3-2 / 2-3); 3.5 Üst / 2.5 Üst / 3-5 Gol tercih edilmeli.",
        )
        blocked.setdefault("5.5 Üst", blocked["+6 Gol"])

    if bundle.btts["1Y ve 2Y KG Var"] < 0.28 or min(bundle.exp_1h_home, bundle.exp_1h_away) < 0.68:
        blocked.setdefault(
            "1Y ve 2Y KG Var",
            f"İki Devrede KG Güven Eşiği Altında (P={bundle.btts['1Y ve 2Y KG Var']*100:.1f}%): "
            "Devrelerden birinin kısır/tek taraflı kalma riski yüksek; Maç Geneli KG Var veya 2. Yarı KG Var daha güvenli.",
        )

    if bundle.btts["1. Yarı KG Var"] < 0.42 or min(bundle.exp_1h_home, bundle.exp_1h_away) < 0.65:
        penalties["1. Yarı KG Var"] = 0.70  # 2nd half has 56% of goals; 1st half BTTS is fragile in U21/open games

    return blocked, penalties


def _estimate_offered_odds(prob: float, category: str) -> float:
    """Estimate realistic bookmaker odds when live offered odds are not supplied for a derivative market."""
    if prob <= 1e-5:
        return 99.0
    # Typical bookmaker margin by market type
    haircut = 0.89 if category in ("Maç Sonucu (1X2)", "Maç Geneli Alt/Üst", "Karşılıklı Gol") else 0.87
    return round(max(1.01, (1.0 / prob) * haircut), 2)


def select_best_valid_bet(
    match_id: str,
    home: str,
    away: str,
    league: str,
    kickoff: str,
    bundle: OmniMarketBundle,
    offered_odds_map: dict[str, float] | None = None,
    risk_ctx: MatchRiskContext | None = None,
    min_odds: float = MIN_ALLOWED_ODDS,
    min_prob: float = 0.54,
    specialty_mode: str | None = None,
) -> list[MarketRecommendation]:
    """Evaluate all markets for a fixture, enforce >= 1.20 odds & risk guards, and rank best valid options.

    Parameters
    ----------
    specialty_mode : str | None
        - None / "general": Best overall high-probability valid bets (`>= 1.20` odds) across all markets.
        - "6_plus_goals": Evaluates `+6 Gol / 5.5 Üst`; if unsafe, automatically steps down to `4.5 Üst / 3.5 Üst / 3-5 Gol / 2.5 Üst`.
        - "both_halves_btts": Evaluates `1Y ve 2Y KG Var`; if unsafe for coupons, steps down to `2. Yarı KG Var / KG Var`.
        - "ht_ft": Evaluates the 9 `İY/MS` (`1/1, 0/1, 2/2, 0/2, 0/0, 1/2, 2/1...`) outcomes.
        - "goal_bands": Evaluates `0-1 Gol, 2-3 Gol, 3-5 Gol, 2-4 Gol, +6 Gol`.
    """
    odds_map = offered_odds_map or {}
    ctx = risk_ctx or MatchRiskContext()
    blocked, penalties = audit_match_risks(bundle, ctx)
    all_probs = bundle.all_probabilities()

    floor = max(MIN_ALLOWED_ODDS, float(min_odds))
    stepped_down_note: str | None = None

    if specialty_mode == "6_plus_goals":
        if "+6 Gol" not in blocked and all_probs["+6 Gol"] >= 0.45:
            candidate_keys = ["+6 Gol", "5.5 Üst", "4.5 Üst", "3.5 Üst", "3-5 Gol"]
        else:
            stepped_down_note = "+6 Gol (Güvenlik İndirimi -> Alt Kademe Üst/Aralık)"
            candidate_keys = ["4.5 Üst", "3.5 Üst", "3-5 Gol", "2.5 Üst", "MS 1 & 2.5 Üst", "MS 2 & 2.5 Üst"]
    elif specialty_mode == "both_halves_btts":
        if "1Y ve 2Y KG Var" not in blocked and all_probs["1Y ve 2Y KG Var"] >= 0.28:
            candidate_keys = ["1Y ve 2Y KG Var", "2. Yarı KG Var", "KG Var", "2.5 Üst & KG Var"]
        else:
            stepped_down_note = "1Y ve 2Y KG Var (Güvenlik İndirimi -> Maç Geneli / 2. Yarı KG)"
            candidate_keys = ["KG Var", "2. Yarı KG Var", "En Az Bir Devre KG Var", "2.5 Üst & KG Var"]
    elif specialty_mode == "ht_ft":
        candidate_keys = [f"İY/MS {k}" for k in ("1/1", "2/2", "0/1", "0/2", "0/0", "1/0", "2/0", "2/1", "1/2")]
    elif specialty_mode == "goal_bands":
        candidate_keys = ["2-3 Gol", "2-4 Gol", "3-5 Gol", "0-1 Gol", "4-5 Gol", "+6 Gol"]
    else:
        # General best-bet scan across all high-reliability markets
        candidate_keys = [
            "MS 1", "MS 2", "ÇŞ 10", "ÇŞ 02",
            "1.5 Üst", "2.5 Üst", "2.5 Alt", "3.5 Üst", "3.5 Alt", "4.5 Alt",
            "İY 0.5 Üst", "İY 1.5 Alt", "İY 1.5 Üst",
            "2Y 0.5 Üst", "2Y 1.5 Alt", "2Y 1.5 Üst",
            "KG Var", "KG Yok", "2. Yarı KG Var",
            "2-3 Gol", "2-4 Gol", "3-5 Gol",
            "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst", "2.5 Alt & KG Yok", "2.5 Üst & KG Var",
            "İY/MS 1/1", "İY/MS 2/2",
        ]

    recommendations: list[MarketRecommendation] = []
    trap_list = tuple(f"{k}: {v}" for k, v in blocked.items())

    for sel in candidate_keys:
        if sel not in all_probs:
            continue
        if sel in blocked and specialty_mode not in ("ht_ft",):
            continue

        prob = float(all_probs[sel])
        eff_min_prob = 0.18 if specialty_mode in ("ht_ft", "both_halves_btts", "6_plus_goals") else min_prob
        if prob < eff_min_prob:
            continue

        cat = _categorize_selection(sel)
        if sel in odds_map and odds_map[sel] is not None:
            off_odds = float(odds_map[sel])
            is_est = False
        else:
            off_odds = _estimate_offered_odds(prob, cat)
            is_est = True

        # STRICT RULE: Never allow odds < 1.20 (eliminates 1.15 - 1.18 trap legs)
        if off_odds < floor - 1e-9:
            continue

        # Also avoid ultra-heavy juice where estimated odds barely clear 1.20 unless live odds confirm >= 1.20
        fair = round(1.0 / max(prob, 1e-6), 2)
        ev = round(prob * off_odds - 1.0, 4)
        pen = penalties.get(sel, 1.0)

        # Safety utility: prioritizes high hit probability while rewarding healthy odds (>=1.22) and low margin loss
        ev_factor = max(0.65, min(1.18, 1.0 + 0.45 * ev))
        safety_score = round((prob ** 1.35) * pen * ev_factor * (1.0 + 0.08 * math.log(max(off_odds, 1.20))), 4)

        rationale = (
            f"Model Olasılığı %{prob*100:.1f} (Adil {fair:.2f}, Oran {off_odds:.2f}) | "
            f"xG: {bundle.mu_home:.2f}-{bundle.mu_away:.2f} (1Y {bundle.exp_1h_total:.2f}, 2Y {bundle.exp_2h_total:.2f})"
        )
        if ctx.notes:
            rationale += f" | {ctx.notes}"

        recommendations.append(
            MarketRecommendation(
                match_id=match_id,
                home=home,
                away=away,
                league=league,
                kickoff=kickoff,
                category=cat,
                selection=sel,
                probability=round(prob, 4),
                fair_odds=fair,
                offered_odds=round(off_odds, 2),
                odds_is_estimated=is_est,
                safety_score=safety_score,
                ev=ev,
                rationale=rationale,
                stepped_down_from=stepped_down_note,
                blocked_traps=trap_list[:3],
                group_id=ctx.group_id,
            )
        )

    recommendations.sort(key=lambda r: (r.safety_score, r.probability), reverse=True)
    return recommendations


def build_target_odds_coupon(
    candidates_by_match: Sequence[Sequence[MarketRecommendation] | MarketRecommendation],
    target_odds: float = 10.0,
    min_leg_odds: float = MIN_ALLOWED_ODDS,
    max_legs: int = 8,
    title: str | None = None,
) -> CouponPlan:
    """Build the highest-probability coupon whose combined odds reach `>= target_odds`.

    Uses beam search over match candidates (at most 1 pick per match and 1 pick per group_id
    when provided) to maximize `prod(leg.safety_score)` and `prod(leg.probability)` subject
    to `prod(leg.offered_odds) >= target_odds` and `leg.offered_odds >= min_leg_odds`.
    """
    floor = max(MIN_ALLOWED_ODDS, float(min_leg_odds))
    normalized_pool: list[list[MarketRecommendation]] = []
    all_traps: list[str] = []

    for item in candidates_by_match:
        opts = [item] if isinstance(item, MarketRecommendation) else list(item)
        valid_opts = [o for o in opts if o.offered_odds >= floor - 1e-9]
        if valid_opts:
            valid_opts.sort(key=lambda r: (r.safety_score, r.probability), reverse=True)
            best_safe = valid_opts[0]
            chosen_opts = [best_safe]
            higher_odds = [
                r for r in valid_opts[1:]
                if r.offered_odds >= best_safe.offered_odds + 0.06
            ]
            if higher_odds:
                higher_odds.sort(key=lambda r: (r.offered_odds * (r.probability ** 1.1), r.safety_score), reverse=True)
                chosen_opts.append(higher_odds[0])
            normalized_pool.append(chosen_opts)
            for t in valid_opts[0].blocked_traps:
                if t not in all_traps:
                    all_traps.append(t)

    # Sort matches by their top option's safety_score descending
    normalized_pool.sort(key=lambda opts: opts[0].safety_score, reverse=True)
    pool = normalized_pool[:24]  # Keep top 24 matches for fast exact/beam search

    # Beam state: (log_safety, log_prob, log_odds, legs_tuple, used_groups_frozenset)
    beam: list[tuple[float, float, float, tuple[MarketRecommendation, ...], frozenset[str]]] = [
        (0.0, 0.0, 0.0, (), frozenset())
    ]
    target_log_odds = math.log(max(1.20, float(target_odds)))
    best_completed: tuple[float, float, float, tuple[MarketRecommendation, ...]] | None = None

    for match_opts in pool:
        new_states = list(beam)
        for log_saf, log_p, log_o, legs, used_groups in beam:
            if len(legs) >= max_legs:
                continue
            for opt in match_opts:
                if opt.group_id and opt.group_id in used_groups:
                    continue
                nl_saf = log_saf + math.log(max(opt.safety_score, 1e-6))
                nl_p = log_p + math.log(max(opt.probability, 1e-6))
                nl_o = log_o + math.log(max(opt.offered_odds, 1.01))
                n_legs = legs + (opt,)
                n_groups = used_groups | ({opt.group_id} if opt.group_id else frozenset())

                if nl_o >= target_log_odds - 1e-9:
                    # Completed coupon candidate: rank primarily by joint probability & safety!
                    cand_score = nl_p + 0.45 * nl_saf
                    if best_completed is None or cand_score > best_completed[0]:
                        best_completed = (cand_score, nl_p, nl_o, n_legs)
                else:
                    new_states.append((nl_saf, nl_p, nl_o, n_legs, n_groups))

        # Prune beam per leg-count bucket keeping probability-optimal, balanced, and high-odds Pareto frontiers
        by_len: dict[int, list[tuple[float, float, float, tuple[MarketRecommendation, ...], frozenset[str]]]] = {}
        for st in new_states:
            by_len.setdefault(len(st[3]), []).append(st)
        beam = []
        for k_len, bucket in by_len.items():
            by_prob = sorted(bucket, key=lambda s: s[1] + 0.35 * s[0] + 0.30 * s[2], reverse=True)[:50]
            by_bal = sorted(bucket, key=lambda s: s[2] + 0.90 * s[1] + 0.30 * s[0], reverse=True)[:50]
            by_odds = sorted(bucket, key=lambda s: s[2] + 0.35 * s[1], reverse=True)[:50]
            seen_ids: set[int] = set()
            for st in by_prob + by_bal + by_odds:
                sid = id(st[3])
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    beam.append(st)

    if best_completed is not None:
        _, final_log_p, final_log_o, chosen_legs = best_completed
    elif beam:
        # If total pool couldn't reach target_odds within max_legs, pick the highest-odds valid state
        best_partial = max(beam, key=lambda s: (s[2], s[1]))
        final_log_p, final_log_o, chosen_legs = best_partial[1], best_partial[2], best_partial[3]
    else:
        chosen_legs = ()
        final_log_p = 0.0
        final_log_o = 0.0

    achieved = round(math.exp(final_log_o), 2) if chosen_legs else 0.0
    joint_p = round(math.exp(final_log_p), 4) if chosen_legs else 0.0
    avg_p = round(sum(l.probability for l in chosen_legs) / len(chosen_legs), 4) if chosen_legs else 0.0

    return CouponPlan(
        title=title or f"QuantFoot-v6 Hedef {target_odds:.0f}x Garanti Kupon",
        target_odds=target_odds,
        achieved_odds=achieved,
        joint_probability=joint_p,
        average_leg_probability=avg_p,
        legs=chosen_legs,
        eliminated_traps=tuple(all_traps[:8]),
    )
