"""Yüksek Oran, Denk Maç (1X2), İY/MS Geri Dönüş (1/2 & 2/1), Doğru Skor ve Bayat Oran Uzman Motoru.

Bu modül, standart banko/favori bahislerinin dışında kalan en zor 4 futbol pazarında
ölçülebilir, kalibre ve zamansal sızıntısız üstünlük üretmek için tasarlanmıştır:

1. **Denk Maç / Yüksek Oran 1X2 Çözücü (ör. 2.20 / 3.30 / 2.55):**
   Keskin devig 1X2 + Asya Handikapı çapası + canlı 2026/27 EWMA xG yapısal 1X2 +
   bitiricilik/savunma şans gerilemesi + yönlü keskin steam + yorgunluk/ilk-11 şoku +
   Gerçek Beraberlik Rejimi (Draw-Regime) tespitiyle hangi sonucun gerçek değer taşıdığını ölçer.
2. **İY/MS Geri Dönüş Motoru (`İY/MS 1/2` ve `İY/MS 2/1`):**
   Takıma özel 1. yarı / 2. yarı gol ve yeme payı asimetrisini (hızlı başlayıp 2Y düşen vs
   yavaş başlayıp 2Y açılan profil) + 2. yarı oyun-durumu dinamiğini + ampirik geri dönüş /
   skor koruyamama geçmişini birleştirerek 9'lu İY/MS dağılımı ve 0–100 DNA skoru üretir.
3. **Doğru Skor (Exact Score) Zekâsı:**
   Takıma özel yarı-paylı dağılım + 6-Altın-Skor makro uyumu + Nesine skor oranlarıyla
   en olası 3 uyumlu skor, en yüksek +EV değer skorları ve geri dönüş skorlarını çıkarır.
4. **Nesine Bayat Oran & Düşük Marj Tarayıcısı + Otomatik Lig/Pazar Kara Listesi:**
   Keskin borsanın sert düştüğü hâlde Nesine'nin geç tepki verdiği pozitif EV fırsatlarını
   ve kronik eksi yazan lig-pazar çiftlerini otomatik işaretler.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
import math
import re
from typing import Any

import numpy as np

from quantfoot.coupons.system_builder import SystemEvaluation, SystemLeg, optimize_system
from quantfoot.markets.devig import devig
from quantfoot.markets.extreme_goals import (
    ExtremeGoalCandidate,
    SafeLadderLeg,
    score_both_halves_btts_match,
)
from quantfoot.markets.families import bet_family
from quantfoot.markets.league_halves import league_first_half_share
from quantfoot.markets.market_diagnosis import (
    parse_directional_steam,
    rank_macro_coherent_scores,
)
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.pricing import invert_ah_ou_1x2
from quantfoot.markets.tail_goals import DEFAULT_RHO, league_tail_regime, regime_score_matrix

_SCORE_SEL_RE = re.compile(r"^(?:Skor|Maç Skoru)\s*(\d+)\s*[-:]\s*(\d+)$", re.IGNORECASE)


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _norm_simplex(probs: Sequence[float]) -> tuple[float, float, float]:
    vals = [max(0.01, float(x)) for x in probs[:3]]
    tot = sum(vals)
    if tot <= 0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (vals[0] / tot, vals[1] / tot, vals[2] / tot)


def _dixon_coles_1x2(mu_h: float, mu_a: float, league: str | None = None) -> tuple[float, float, float]:
    nu, alpha, kappa = league_tail_regime(league)
    mat = regime_score_matrix(
        max(0.15, float(mu_h)),
        max(0.15, float(mu_a)),
        alpha_nb=alpha,
        rho=DEFAULT_RHO,
        shared_kappa=kappa,
        com_nu=nu,
        max_goals=10,
    )
    p1 = float(np.sum(np.tril(mat, -1)))
    px = float(np.sum(np.diag(mat)))
    p2 = float(np.sum(np.triu(mat, 1)))
    return _norm_simplex((p1, px, p2))


def _selection_map(match: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(s.get("name")): s for s in (match.get("selections") or []) if s.get("name")}


def _extract_market_1x2(match: Mapping[str, Any]) -> tuple[float, float, float] | None:
    f1x2 = match.get("fair_1x2")
    if isinstance(f1x2, (list, tuple)) and len(f1x2) == 3:
        vals = [_flt(x) for x in f1x2]
        if all(v is not None and v > 0 for v in vals):
            return _norm_simplex(vals)  # type: ignore[arg-type]
    sels = _selection_map(match)
    p1 = _flt((sels.get("MS 1") or {}).get("fair_prob"))
    px = _flt((sels.get("MS 0") or sels.get("MS X") or {}).get("fair_prob"))
    p2 = _flt((sels.get("MS 2") or {}).get("fair_prob"))
    if p1 and px and p2:
        return _norm_simplex((p1, px, p2))
    o1 = _flt((sels.get("MS 1") or {}).get("odds"))
    ox = _flt((sels.get("MS 0") or sels.get("MS X") or {}).get("odds"))
    o2 = _flt((sels.get("MS 2") or {}).get("odds"))
    if o1 and ox and o2 and min(o1, ox, o2) > 1.01:
        p = devig([o1, ox, o2], method="power").probabilities
        return _norm_simplex(p)
    return None


def _extract_nesine_1x2_odds(match: Mapping[str, Any]) -> dict[str, float | None]:
    sels = _selection_map(match)
    o1 = _flt((sels.get("MS 1") or {}).get("odds"))
    ox = _flt((sels.get("MS 0") or sels.get("MS X") or {}).get("odds"))
    o2 = _flt((sels.get("MS 2") or {}).get("odds"))
    return {"MS 1": o1, "MS 0": ox, "MS 2": o2}


def _extract_team_half_shifts(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
) -> tuple[float, float, dict[str, Any]]:
    """Extract bounded team-specific 1H urgency shifts from 2026/27 half_split or ESPN half history."""
    res = match.get("research") or {}
    hs = res.get("half_split")
    if isinstance(hs, Mapping):
        h_sh = _flt(hs.get("home_1h_urgency_shift"))
        a_sh = _flt(hs.get("away_1h_urgency_shift"))
        if h_sh is not None and a_sh is not None:
            return _clip(h_sh, -0.08, 0.08), _clip(a_sh, -0.08, 0.08), dict(hs)

    # Fallback: derive shrunk 1H shifts from ESPN recent match half-by-half goals if present
    games = (research_row or {}).get("games") or {}
    if not games:
        return 0.0, 0.0, {}

    lg_share = league_first_half_share(str(match.get("league") or "")) or 0.440
    side_stats: dict[str, dict[str, float]] = {}
    for side in ("home", "away"):
        glist = games.get(side) or []
        gf1 = gf2 = ga1 = ga2 = leads = blown = lost = trails = cb_win = cb_pts = bh = n = 0
        for g in glist:
            gf = g.get("for") or (None, None)
            ga = g.get("against") or (None, None)
            if gf[0] is None or gf[1] is None or ga[0] is None or ga[1] is None:
                continue
            f1, f2, a1, a2 = int(gf[0]), int(gf[1]), int(ga[0]), int(ga[1])
            gf1 += f1
            gf2 += f2
            ga1 += a1
            ga2 += a2
            n += 1
            if f1 >= 1 and a1 >= 1 and f2 >= 1 and a2 >= 1:
                bh += 1
            if f1 > a1:
                leads += 1
                if (f1 + f2) <= (a1 + a2):
                    blown += 1
                if (f1 + f2) < (a1 + a2):
                    lost += 1
            elif f1 < a1:
                trails += 1
                if (f1 + f2) >= (a1 + a2):
                    cb_pts += 1
                if (f1 + f2) > (a1 + a2):
                    cb_win += 1
        if n >= 4:
            att_1h = (gf1 + 10.0 * lg_share) / (gf1 + gf2 + 10.0)
            con_1h = (ga1 + 10.0 * lg_share) / (ga1 + ga2 + 10.0)
            side_stats[side] = {
                "matches": float(n),
                "h1_attack_share": _clip(att_1h, 0.28, 0.60),
                "h1_concede_share": _clip(con_1h, 0.28, 0.60),
                "ht_leads": float(leads),
                "leads_blown": float(blown),
                "leads_lost": float(lost),
                "lead_blown_rate": (blown + 5.0 * 0.22) / (leads + 5.0),
                "lead_lost_rate": (lost + 5.0 * 0.075) / (leads + 5.0),
                "ht_trails": float(trails),
                "comebacks_won": float(cb_win),
                "comebacks_pts": float(cb_pts),
                "comeback_win_rate": (cb_win + 5.0 * 0.075) / (trails + 5.0),
                "comeback_pts_rate": (cb_pts + 5.0 * 0.22) / (trails + 5.0),
                "both_halves_btts_rate": bh / n,
            }

    if "home" in side_stats and "away" in side_stats:
        hp, ap = side_stats["home"], side_stats["away"]
        h_eff = 0.60 * hp["h1_attack_share"] + 0.40 * ap["h1_concede_share"]
        a_eff = 0.60 * ap["h1_attack_share"] + 0.40 * hp["h1_concede_share"]
        sw = min(1.0, min(hp["matches"], ap["matches"]) / 12.0)
        h_sh = _clip((h_eff - lg_share) * sw, -0.08, 0.08)
        a_sh = _clip((a_eff - lg_share) * sw, -0.08, 0.08)
        return h_sh, a_sh, {
            "league_1h_share": lg_share,
            "home_eff_1h_share": round(lg_share + h_sh, 4),
            "away_eff_1h_share": round(lg_share + a_sh, 4),
            "home_1h_urgency_shift": round(h_sh, 4),
            "away_1h_urgency_shift": round(a_sh, 4),
            "home": hp,
            "away": ap,
        }
    return 0.0, 0.0, {}


# --------------------------------------------------------------------------- #
# 1. Denk Maç / Yüksek Oran 1X2 Çözücü (ör. 2.20 / 3.30 / 2.55)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CloseMatchAnalysis:
    """Dengeli / yüksek oranlı (2.20 / 3.30 / 2.55 gibi) 1X2 maçların çok katmanlı çözümü."""

    code: int
    kickoff: str
    league: str
    match: str
    is_close_match: bool
    market_1x2: dict[str, float]
    model_1x2: dict[str, float]
    edge_1x2: dict[str, float]
    nesine_odds_1x2: dict[str, float | None]
    ev_1x2: dict[str, float | None]
    best_outcome: str
    best_prob: float
    best_odds: float | None
    best_ev: float | None
    safe_alternative: str | None
    safe_alternative_prob: float | None
    safe_alternative_odds: float | None
    verdict: str  # "GÜÇLÜ DEĞER" | "DEĞER" | "DENGELİ — ÇİFTE ŞANS" | "PAS — GERÇEK YAZI-TURA"
    conviction_score: float  # 0..100
    draw_regime_score: float  # 0..100
    stale_nesine_edge: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_close_match(
    match: Mapping[str, Any],
    *,
    xg_weight_cap: float = 0.16,
    ah_weight: float = 0.15,
    luck_cap: float = 0.022,
    steam_weight: float = 0.30,
    min_close_odds: float = 1.80,
) -> CloseMatchAnalysis | None:
    """Resolve balanced / high-odds 1X2 matches (e.g. 2.20 / 3.30 / 2.55) using 6 independent evidence layers."""
    mkt_tuple = _extract_market_1x2(match)
    if mkt_tuple is None:
        return None
    p1_m, px_m, p2_m = mkt_tuple
    odds_map = _extract_nesine_1x2_odds(match)
    o1, ox, o2 = odds_map["MS 1"], odds_map["MS 0"], odds_map["MS 2"]
    lg = str(match.get("league") or "")
    res = match.get("research") or {}

    both_high_odds = o1 is not None and o2 is not None and min(o1, o2) >= min_close_odds
    is_close = max(p1_m, p2_m) <= 0.54 or both_high_odds

    p1, px, p2 = p1_m, px_m, p2_m
    reasons: list[str] = []
    warnings: list[str] = []
    evidence_hits = 0

    # Layer 1: Low-vig Asian Handicap + O/U 2.5 anchor (sharpest market on earth for coin-flip matches)
    ah_raw = match.get("ref_ah") or match.get("ah")
    sels = _selection_map(match)
    p_o25 = _flt((sels.get("2.5 Üst") or {}).get("fair_prob"))
    if isinstance(ah_raw, (list, tuple)) and len(ah_raw) == 2 and p_o25 is not None:
        ah_line = _flt(ah_raw[0])
        ah_odds = ah_raw[1]
        if ah_line is not None and isinstance(ah_odds, (list, tuple)) and len(ah_odds) == 2:
            ah_h, ah_a = _flt(ah_odds[0]), _flt(ah_odds[1])
            if ah_h and ah_a and min(ah_h, ah_a) > 1.01:
                try:
                    p_ah_h = float(devig([ah_h, ah_a], method="power").probabilities[0])
                    _, _, p_ah_1x2 = invert_ah_ou_1x2(ah_line, p_ah_h, p_o25)
                    w_ah = _clip(ah_weight, 0.0, 0.25)
                    p1 = (1.0 - w_ah) * p1 + w_ah * float(p_ah_1x2[0])
                    px = (1.0 - w_ah) * px + w_ah * float(p_ah_1x2[1])
                    p2 = (1.0 - w_ah) * p2 + w_ah * float(p_ah_1x2[2])
                    p1, px, p2 = _norm_simplex((p1, px, p2))
                    reasons.append(f"Asya Handikap ({ah_line:+.2f}) çapası işlendi")
                    evidence_hits += 1
                except Exception:  # noqa: BLE001
                    pass

    # Layer 2: Live 2026/27 EWMA NPxG/xG structural edge (market-independent!)
    xg_info = res.get("xg_intelligence")
    if isinstance(xg_info, Mapping):
        xmh = _flt(xg_info.get("xg_mu_home"))
        xma = _flt(xg_info.get("xg_mu_away"))
        hp = xg_info.get("home") or {}
        ap = xg_info.get("away") or {}
        min_n = min(int(hp.get("matches") or 0), int(ap.get("matches") or 0))
        if xmh is not None and xma is not None and min_n >= 3:
            xg_1, xg_x, xg_2 = _dixon_coles_1x2(xmh, xma, lg)
            w_xg = xg_weight_cap * min(1.0, min_n / 12.0)
            p1 = (1.0 - w_xg) * p1 + w_xg * xg_1
            px = (1.0 - w_xg) * px + w_xg * xg_x
            p2 = (1.0 - w_xg) * p2 + w_xg * xg_2
            p1, px, p2 = _norm_simplex((p1, px, p2))
            xg_gap = xmh - xma
            if abs(xg_gap) >= 0.32:
                leader = "Ev" if xg_gap > 0 else "Dep"
                reasons.append(f"2026/27 xG yapısal üstünlüğü ({leader}: {xmh:.2f}–{xma:.2f} xG)")
                evidence_hits += 1

            # Layer 3: Finishing-luck & defensive-luck regression (bubble fade / unlucky bounce)
            if min_n >= 5:
                h_luck = (_flt(hp.get("finishing_luck")) or 0.0) + (_flt(hp.get("defensive_luck")) or 0.0)
                a_luck = (_flt(ap.get("finishing_luck")) or 0.0) + (_flt(ap.get("defensive_luck")) or 0.0)
                luck_diff = h_luck - a_luck  # positive => Home overperforming xG vs Away
                if abs(luck_diff) >= 0.45:
                    shift = _clip(-0.020 * luck_diff, -luck_cap, luck_cap)
                    p1 += shift
                    p2 -= shift
                    p1, px, p2 = _norm_simplex((p1, px, p2))
                    unlucky = "Dep" if luck_diff > 0 else "Ev"
                    lucky = "Ev" if luck_diff > 0 else "Dep"
                    reasons.append(f"xG şans gerilemesi: {lucky} şişkin, {unlucky} lehine düzeltme ({luck_diff:+.2f})")
                    evidence_hits += 1

    # Layer 4: Directional Sharp Steam & Adverse Selection
    steam = match.get("steam_1x2")
    steam_vals = [0.0, 0.0, 0.0]
    if isinstance(steam, (list, tuple)) and len(steam) == 3:
        parsed_s = [_flt(x) for x in steam]
        if all(x is not None for x in parsed_s):
            steam_vals = [float(x) for x in parsed_s]  # type: ignore[arg-type]
            # Bounded directional shift from sharp opening -> current closing move
            d1 = _clip(steam_weight * steam_vals[0], -0.032, 0.032)
            dx = _clip(steam_weight * steam_vals[1], -0.025, 0.025)
            d2 = _clip(steam_weight * steam_vals[2], -0.032, 0.032)
            p1, px, p2 = _norm_simplex((p1 + d1, px + dx, p2 + d2))
            max_i = max(range(3), key=lambda i: steam_vals[i])
            labels = ("MS 1", "MS 0", "MS 2")
            if steam_vals[max_i] >= 0.025:
                reasons.append(f"Keskin piyasa akışı {labels[max_i]} yönünde ({100*steam_vals[max_i]:+.1f}p)")
                evidence_hits += 1
            for i, lbl in enumerate(labels):
                if steam_vals[i] <= -0.035:
                    warnings.append(f"{lbl} ters keskin steam altında ({100*steam_vals[i]:+.1f}p)")

    # Layer 5: Fatigue asymmetry + Fresh T-60 Lineup Shock (strictly anti-double-counted!)
    fat = res.get("fatigue") or {}
    if isinstance(fat, Mapping) and fat.get("fatigued_side") in ("home", "away"):
        shift = -0.018 if fat["fatigued_side"] == "home" else 0.018
        p1, px, p2 = _norm_simplex((p1 + shift, px, p2 - shift))
        reasons.append(str(fat.get("flag") or f"Yorgunluk asimetrisi ({fat['fatigued_side']})"))
        evidence_hits += 1

    shock = res.get("lineup_shock") or {}
    if isinstance(shock, Mapping) and shock.get("applied"):
        smh = _flt(shock.get("mu_home_adj"))
        sma = _flt(shock.get("mu_away_adj"))
        bmh = _flt(shock.get("mu_home_base"))
        bma = _flt(shock.get("mu_away_base"))
        if smh and sma and bmh and bma:
            s1, sx, s2 = _dixon_coles_1x2(smh, sma, lg)
            b1, bx, b2 = _dixon_coles_1x2(bmh, bma, lg)
            p1, px, p2 = _norm_simplex((p1 + (s1 - b1), px + (sx - bx), p2 + (s2 - b2)))
            reasons.append("İlk 11 şoku piyasadan taze — 1X2 olasılıkları güncellendi")
            evidence_hits += 1

    # Layer 5b: Deep Squad Line-by-Line Unit Matchup & Derby Intelligence (bounded ±2.0pp)
    scout = res.get("squad_scouting") or {}
    if isinstance(scout, Mapping) and float(scout.get("confidence") or 0.0) >= 0.35:
        s_edge = scout.get("scouting_edge_1x2") or {}
        sd1 = _flt(s_edge.get("MS 1")) or 0.0
        sdx = _flt(s_edge.get("MS 0")) or 0.0
        sd2 = _flt(s_edge.get("MS 2")) or 0.0
        if abs(sd1) + abs(sdx) + abs(sd2) >= 0.004:
            # Keep scouting strictly bounded so sharp consensus remains the anchor
            p1, px, p2 = _norm_simplex((
                p1 + _clip(sd1, -0.018, 0.018),
                px + _clip(sdx, -0.014, 0.014),
                p2 + _clip(sd2, -0.018, 0.018),
            ))
            key_edges = scout.get("key_edges") or []
            if key_edges:
                reasons.append(f"Hat eşleşmesi: {key_edges[0]}")
            evidence_hits += 1

    # Layer 6: Draw-Regime Detector (measures when 3.30 MS 0 is genuinely live!)
    mu_h = _flt(match.get("mu_home"))
    mu_a = _flt(match.get("mu_away"))
    mu_tot = (mu_h + mu_a) if (mu_h is not None and mu_a is not None) else 2.55
    mu_gap = abs(mu_h - mu_a) if (mu_h is not None and mu_a is not None) else abs(p1_m - p2_m) * 2.5
    gap_12 = abs(p1 - p2)
    hs = res.get("half_split") or {}
    h_dr = _flt(((hs.get("home") or {}) if isinstance(hs, Mapping) else {}).get("draw_rate"))
    a_dr = _flt(((hs.get("away") or {}) if isinstance(hs, Mapping) else {}).get("draw_rate"))
    avg_dr = 0.5 * (h_dr + a_dr) if (h_dr is not None and a_dr is not None) else None

    draw_score = 0.0
    if gap_12 <= 0.05:
        draw_score += 30.0
    elif gap_12 <= 0.10:
        draw_score += 20.0
    elif gap_12 <= 0.16:
        draw_score += 10.0

    if mu_tot <= 2.15:
        draw_score += 28.0
    elif mu_tot <= 2.45:
        draw_score += 18.0
    elif mu_tot <= 2.75:
        draw_score += 8.0
    else:
        draw_score -= 8.0

    if px_m >= 0.30:
        draw_score += 20.0
    elif px_m >= 0.275:
        draw_score += 12.0
    elif px_m >= 0.25:
        draw_score += 5.0

    if mu_gap <= 0.25:
        draw_score += 10.0
    if avg_dr is not None and avg_dr >= 0.32:
        draw_score += 12.0
    if bool((res.get("weather") or {}).get("severe")):
        draw_score += 8.0
        reasons.append("Şiddetli hava temposu düşürüyor (beraberlik/alt lehine)")
    if isinstance(scout, Mapping) and isinstance(scout.get("derby"), Mapping):
        derby_info = scout["derby"]
        draw_score += 8.0 if derby_info.get("tier") == "mega_derbi" else 5.0
        reasons.append(f"Derbi bağlamı ({derby_info.get('label', 'Derbi')}): sıkı skor ve yüksek mücadele")
    if steam_vals[1] >= 0.02:
        draw_score += 8.0
    draw_score = round(_clip(draw_score, 0.0, 100.0), 1)

    if draw_score >= 68.0:
        bump = _clip((draw_score - 65.0) * 0.0005, 0.0, 0.015)
        p1, px, p2 = _norm_simplex((p1 - 0.5 * bump, px + bump, p2 - 0.5 * bump))
        reasons.append(f"Gerçek beraberlik rejimi güçlü (skor {draw_score:.0f}/100, toplam xG {mu_tot:.2f})")

    # Consensus dispersion risk warning
    cons_disp = match.get("consensus_dispersion") or {}
    cons_kl = _flt(cons_disp.get("max_kl_divergence")) if isinstance(cons_disp, Mapping) else None
    if cons_kl is not None and cons_kl > 0.018:
        warnings.append(f"Borsalar arası yüksek uyumsuzluk (KL={cons_kl:.4f})")

    model_map = {"MS 1": round(p1, 5), "MS 0": round(px, 5), "MS 2": round(p2, 5)}
    market_map = {"MS 1": round(p1_m, 5), "MS 0": round(px_m, 5), "MS 2": round(p2_m, 5)}
    edge_map = {k: round(model_map[k] - market_map[k], 5) for k in ("MS 1", "MS 0", "MS 2")}
    ev_map = {
        k: (round(model_map[k] * float(odds_map[k]) - 1.0, 4) if odds_map[k] is not None else None)
        for k in ("MS 1", "MS 0", "MS 2")
    }

    # Check stale Nesine edge (sharp steamed favorably >= +2.5pp AND Nesine still gives EV >= +2%)
    stale_edge = False
    for idx, k in enumerate(("MS 1", "MS 0", "MS 2")):
        if steam_vals[idx] >= 0.025 and (ev_map[k] or -1.0) >= 0.02:
            stale_edge = True
            reasons.append(f"Nesine bayat oran fırsatı: {k} @{odds_map[k]:.2f} (EV %{100*(ev_map[k] or 0):+.1f})")

    # Pick best outcome: avoid picking a side fighting severe adverse sharp steam (<= -4pp) if alternative exists
    steam_by_k = {"MS 1": steam_vals[0], "MS 0": steam_vals[1], "MS 2": steam_vals[2]}
    candidates_k = [k for k in ("MS 1", "MS 0", "MS 2") if steam_by_k[k] > -0.04] or ["MS 1", "MS 0", "MS 2"]

    if any(ev_map[k] is not None for k in candidates_k):
        # Balance EV + edge over market so extreme longshots don't dominate purely on noise
        best_k = max(
            candidates_k,
            key=lambda k: (
                (ev_map[k] if ev_map[k] is not None else -9.0) + 0.45 * edge_map[k],
                model_map[k],
            ),
        )
    else:
        best_k = max(candidates_k, key=lambda k: (edge_map[k], model_map[k]))

    best_p = model_map[best_k]
    best_odds = odds_map[best_k]
    best_ev = ev_map[best_k]
    best_edge = edge_map[best_k]

    # Safe Double Chance alternative aligned with our directional lean
    if p1 >= p2:
        safe_alt = "ÇŞ 10" if "ÇŞ 10" in sels else "ÇŞ 1X"
        safe_p = round(p1 + px, 5)
    else:
        safe_alt = "ÇŞ 02" if "ÇŞ 02" in sels else "ÇŞ X2"
        safe_p = round(p2 + px, 5)
    safe_odds = _flt((sels.get(safe_alt) or sels.get("ÇŞ 1X" if p1 >= p2 else "ÇŞ X2") or {}).get("odds"))

    # Conviction score (0..100)
    conv = 25.0
    conv += _clip(best_edge * 650.0, -15.0, 30.0)
    if best_ev is not None:
        conv += _clip(best_ev * 180.0, -18.0, 24.0)
    conv += min(18.0, evidence_hits * 6.0)
    if stale_edge:
        conv += 10.0
    if best_k == "MS 0" and draw_score >= 65.0:
        conv += 8.0
    relevant_warnings = [
        w for w in warnings
        if best_k in w or not any(other in w for other in ("MS 1", "MS 0", "MS 2"))
    ]
    if relevant_warnings:
        conv -= min(18.0, len(relevant_warnings) * 8.0)
    conv = round(_clip(conv, 0.0, 100.0), 1)

    if (best_ev is not None and best_ev >= 0.05 and conv >= 68.0) or (stale_edge and (best_ev or 0.0) >= 0.03):
        verdict = "GÜÇLÜ DEĞER"
    elif (best_ev is not None and best_ev >= 0.015 and conv >= 54.0) or (best_ev is None and best_edge >= 0.025 and conv >= 58.0):
        verdict = "DEĞER"
    elif safe_p >= 0.68 and conv >= 45.0:
        verdict = "DENGELİ — ÇİFTE ŞANS"
    else:
        verdict = "PAS — GERÇEK YAZI-TURA"

    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    return CloseMatchAnalysis(
        code=int(match.get("code") or 0),
        kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
        league=lg,
        match=mname,
        is_close_match=is_close,
        market_1x2=market_map,
        model_1x2=model_map,
        edge_1x2=edge_map,
        nesine_odds_1x2=odds_map,
        ev_1x2=ev_map,
        best_outcome=best_k,
        best_prob=best_p,
        best_odds=best_odds,
        best_ev=best_ev,
        safe_alternative=safe_alt,
        safe_alternative_prob=safe_p,
        safe_alternative_odds=safe_odds,
        verdict=verdict,
        conviction_score=conv,
        draw_regime_score=draw_score,
        stale_nesine_edge=stale_edge,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


# --------------------------------------------------------------------------- #
# 2. İY/MS Geri Dönüş Motoru (1/2 ve 2/1 — İlk Yarı Ev/Dep -> Maç Sonu Dep/Ev)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ComebackCandidate:
    """İY/MS 1/2 veya İY/MS 2/1 geri dönüş adayı — asimetrik yarı-payı + oyun-durumu modeli."""

    code: int
    kickoff: str
    league: str
    match: str
    kind: str  # "İY/MS 1/2" | "İY/MS 2/1"
    archetype: str  # "hizli_basla_yavasla" | "yavas_basla_don" | "acik_duello" | "zayif"
    mu_home: float
    mu_away: float
    home_1h_share: float
    away_1h_share: float
    dna_score: float  # 0..100
    p_comeback: float
    fair_odds: float
    p_market: float | None
    nesine_odds: float | None
    ev: float | None
    p_ht_lead_alt: float  # P(leader leads HT)
    p_ft_win_alt: float   # P(winner wins FT)
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    safe_ladder: tuple[SafeLadderLeg, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_comeback_ladder(match: Mapping[str, Any], kind: str) -> tuple[SafeLadderLeg, ...]:
    sels = _selection_map(match)
    wanted = (
        ("KG Var", "2.5 Üst", "2Y 0.5 Üst", "ÇŞ 02", "ÇŞ X2")
        if kind == "İY/MS 1/2"
        else ("KG Var", "2.5 Üst", "2Y 0.5 Üst", "ÇŞ 10", "ÇŞ 1X")
    )
    out: list[SafeLadderLeg] = []
    for nm in wanted:
        s = sels.get(nm)
        if not s:
            continue
        odds = _flt(s.get("odds")) or 0.0
        p = _flt(s.get("fair_prob")) or 0.0
        if odds >= 1.20 and p >= 0.52:
            out.append(SafeLadderLeg(nm, str(s.get("market") or ""), str(s.get("selection") or ""), odds, p))
    out.sort(key=lambda x: (-x.fair_prob, x.odds))
    return tuple(out[:3])


def score_comeback_htft(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
) -> list[ComebackCandidate]:
    """Evaluate BOTH 'İY/MS 1/2' (Home HT -> Away FT) and 'İY/MS 2/1' (Away HT -> Home FT)."""
    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    if mh is None or ma is None or (mh + ma) <= 0.3:
        return []
    lg = str(match.get("league") or "")
    sels = _selection_map(match)
    res = match.get("research") or {}

    h_shift, a_shift, hs = _extract_team_half_shifts(match, research_row)
    lg_a1 = league_first_half_share(lg) or 0.440
    h_a1 = _clip(lg_a1 + 0.0023 + h_shift, 0.28, 0.58)
    a_a1 = _clip(lg_a1 - 0.0023 + a_shift, 0.28, 0.58)

    bundle = compute_omni_markets(
        mh,
        ma,
        league=lg,
        first_half_share=lg_a1,
        home_1h_urgency_shift=h_shift,
        away_1h_urgency_shift=a_shift,
    )

    hp = hs.get("home") if isinstance(hs.get("home"), Mapping) else {}
    ap = hs.get("away") if isinstance(hs.get("away"), Mapping) else {}
    mtot = mh + ma
    mmin = min(mh, ma)
    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")

    results: list[ComebackCandidate] = []
    for kind, key, leader_side, winner_side in (
        ("İY/MS 1/2", "1/2", "home", "away"),
        ("İY/MS 2/1", "2/1", "away", "home"),
    ):
        base_p = float(bundle.ht_ft.get(key, 0.0))
        lead_p = hp if leader_side == "home" else ap
        win_p = ap if winner_side == "away" else hp
        lead_shift = h_shift if leader_side == "home" else a_shift
        win_shift = a_shift if winner_side == "away" else h_shift
        mu_lead = mh if leader_side == "home" else ma
        mu_win = ma if winner_side == "away" else mh
        p_ht_lead = float(bundle.ht_1x2.get("İY 1" if leader_side == "home" else "İY 2", 0.0))
        p_ft_win = float(bundle.ft_1x2.get("2" if winner_side == "away" else "1", 0.0))

        # Empirical comeback / blown-lead Bayesian lift (strictly bounded [0.85, 1.28])
        emp_mult = 1.0
        blown_rate = _flt(lead_p.get("lead_blown_rate"))
        lost_rate = _flt(lead_p.get("lead_lost_rate"))
        cb_win_rate = _flt(win_p.get("comeback_win_rate"))
        cb_pts_rate = _flt(win_p.get("comeback_pts_rate"))
        if blown_rate is not None and cb_win_rate is not None:
            # Relative to league priors (0.22 blown, 0.075 lost, 0.075 cb_win)
            r_blown = _clip(blown_rate / 0.22, 0.70, 1.45)
            r_cb = _clip(cb_win_rate / 0.075, 0.70, 1.50)
            emp_mult = _clip((r_blown ** 0.35) * (r_cb ** 0.35), 0.85, 1.28)
            if lost_rate is not None and lost_rate >= 0.14:
                emp_mult = _clip(emp_mult * 1.06, 0.85, 1.30)

        p_cb = _clip(base_p * emp_mult, 0.002, 0.22)
        fair_odds = round(1.0 / p_cb, 2)
        sel = sels.get(kind)
        p_mkt = _flt(sel.get("fair_prob")) if sel else None
        odds = _flt(sel.get("odds")) if sel else None
        ev = (p_cb * odds - 1.0) if odds is not None else None

        reasons: list[str] = []
        warnings: list[str] = []
        score = 0.0

        # 1. Empirical Comeback Sweet-Spot: winner_p * min_mu (n=3,020 2026/27: beats base rate;
        # extreme 80% favorites rarely trail at HT, while weak <28% underdogs rarely overturn FT!) (0..26 pts)
        sweet_spot = p_ft_win * mmin
        if sweet_spot >= 0.60 and 0.38 <= p_ft_win <= 0.72:
            score += 26.0
            reasons.append(f"ideal geri dönüş dengesi (kazanan MS P %{100*p_ft_win:.0f}, rakip xG {mu_lead:.2f})")
        elif sweet_spot >= 0.45 and p_ft_win >= 0.32:
            score += 19.0
            reasons.append(f"uygun geri dönüş dengesi (MS P %{100*p_ft_win:.0f}, en düşük xG {mmin:.2f})")
        elif sweet_spot >= 0.34:
            score += 11.0
        else:
            score -= 8.0
            warnings.append(
                f"dengesiz geri dönüş profili (MS P %{100*p_ft_win:.0f}, en düşük xG {mmin:.2f})"
            )

        # 2. Required scoring tempo & two-way 1H/2H threat (1/2 & 2/1 need >= 3 goals with BOTH scoring) (0..22 pts)
        if mtot >= 3.05 and mmin >= 1.10:
            score += 22.0
            reasons.append(f"yüksek çift-taraflı gol temposu ({mh:.2f}–{ma:.2f} xG)")
        elif mtot >= 2.75 and mmin >= 0.95:
            score += 16.0
            reasons.append(f"uygun 3+ gol zemini ({mtot:.2f} xG, en zayıf {mmin:.2f})")
        elif mtot >= 2.45 and mmin >= 0.80:
            score += 9.0
        else:
            score += max(0.0, (mtot - 1.8) * 6.0)
            warnings.append(f"düşük gol temposu ({mtot:.2f} xG — 1/2 veya 2/1 için en az 3 gol gerekir)")

        # 3. Asymmetric 1H/2H team profile contrast (fast starter vs 2nd-half closer) (0..20 pts)
        split_contrast = lead_shift - win_shift  # positive => leader starts fast, winner finishes strong!
        if split_contrast >= 0.060:
            archetype = "hizli_basla_yavasla"
            score += 20.0
            reasons.append(
                f"güçlü yarı asimetrisi: 1Y lider hızlı başlar ({100*(lg_a1+lead_shift):.0f}%), "
                f"kazanan 2Y açılır (2Y %{100*(1-(lg_a1+win_shift)):.0f})"
            )
        elif split_contrast >= 0.025:
            archetype = "yavas_basla_don"
            score += 13.0
            reasons.append(f"yarı-payı uyumu (+{100*split_contrast:.1f}p 1Y/2Y zıtlığı)")
        elif p_ft_win >= 0.50 and mtot >= 2.85 and mu_lead >= 0.85:
            archetype = "favori_geri_donus"
            score += 11.0
            reasons.append("yüksek tempolu favori geri dönüş arketipi")
        elif mtot >= 3.00 and mmin >= 1.10 and mu_win >= 1.35:
            archetype = "acik_duello"
            score += 10.0
            reasons.append("açık gollü düello (yüksek skor çevirme alanı)")
        else:
            archetype = "zayif"
            if split_contrast <= -0.03:
                score -= 8.0
                warnings.append("ters yarı profili (1Y adayı yavaş başlıyor)")

        # 3b. Squad unit-matchup boost for comeback winner (strong Attack vs opposing Defense+GK)
        scout = res.get("squad_scouting") or {}
        if isinstance(scout, Mapping) and float(scout.get("confidence") or 0.0) >= 0.35:
            win_att_edge = _flt(
                scout.get("away_attack_vs_home_def_gk" if winner_side == "away" else "home_attack_vs_away_def_gk")
            )
            if win_att_edge is not None and win_att_edge >= 8.0:
                score += min(6.0, (win_att_edge - 6.0) * 0.4)
                reasons.append(f"kazanan hücum hattı rakip savunma+kaleciye üstün (+{win_att_edge:.1f})")

        # 4. Calibrated comeback probability magnitude (0..22 pts)
        if p_cb >= 0.045:
            score += 22.0
            reasons.append(f"yüksek model geri dönüş olasılığı (%{100*p_cb:.1f}, adil @{fair_odds:.1f})")
        elif p_cb >= 0.036:
            score += 17.0
        elif p_cb >= 0.028:
            score += 11.0
        else:
            score += 3.0

        # 5. Empirical comeback & lead-blown track record (0..10 pts)
        if emp_mult >= 1.12:
            score += 10.0
            reasons.append(
                f"geçmiş geri dönüş verisi destekli (önde koruyamama %{100*(blown_rate or 0):.0f}, "
                f"geriden puan %{100*(cb_pts_rate or 0):.0f})"
            )
        elif emp_mult >= 1.04:
            score += 6.0
        elif emp_mult <= 0.90:
            score -= 6.0
            warnings.append("geçmişte öne geçince skor koruma oranı yüksek")

        # 5. Directional sharp steam toward FT winner & positive EV (0..12 pts)
        win_ms_name = "MS 2" if winner_side == "away" else "MS 1"
        dir_steam = parse_directional_steam(match, win_ms_name)
        if dir_steam is not None:
            if dir_steam >= 0.025:
                score += 6.0
                reasons.append(f"keskin piyasa {win_ms_name} lehine akıyor ({100*dir_steam:+.1f}p)")
            elif dir_steam <= -0.04:
                score -= 10.0
                warnings.append(f"keskin piyasa {win_ms_name} aleyhine hareket etti ({100*dir_steam:+.1f}p)")

        if ev is not None and ev >= 0.08:
            score += min(10.0, ev * 20.0)
            reasons.append(f"pozitif geri dönüş EV ({100*ev:+.1f}%)")
        elif ev is not None and ev < -0.25:
            score -= 8.0
            warnings.append(f"Nesine oranı düşük (EV {100*ev:+.1f}%)")

        # Severe weather kills 3+ goal comeback scenarios
        if bool((res.get("weather") or {}).get("severe")):
            score -= 10.0
            warnings.append("şiddetli hava koşulları geri dönüş gol sayısını kısıtlar")

        score = round(_clip(score, 0.0, 100.0), 1)
        results.append(
            ComebackCandidate(
                code=int(match.get("code") or 0),
                kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
                league=lg,
                match=mname,
                kind=kind,
                archetype=archetype,
                mu_home=round(mh, 3),
                mu_away=round(ma, 3),
                home_1h_share=round(h_a1, 4),
                away_1h_share=round(a_a1, 4),
                dna_score=score,
                p_comeback=round(p_cb, 5),
                fair_odds=fair_odds,
                p_market=round(p_mkt, 5) if p_mkt is not None else None,
                nesine_odds=odds,
                ev=round(ev, 4) if ev is not None else None,
                p_ht_lead_alt=round(p_ht_lead, 4),
                p_ft_win_alt=round(p_ft_win, 4),
                reasons=tuple(reasons),
                warnings=tuple(warnings),
                safe_ladder=_safe_comeback_ladder(match, kind),
                extra={
                    "mbs": int(match.get("mbs") or 1),
                    "split_contrast": round(split_contrast, 4),
                    "emp_mult": round(emp_mult, 3),
                    "mu_lead": round(mu_lead, 3),
                    "mu_win": round(mu_win, 3),
                },
            )
        )

    results.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0), -x.p_comeback))
    return results


# --------------------------------------------------------------------------- #
# 3. Doğru Skor (Exact Score) Zekâsı
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ExactScorePick:
    score: str
    prob: float
    fair_odds: float
    nesine_odds: float | None = None
    ev: float | None = None


@dataclass(frozen=True)
class ExactScoreAnalysis:
    code: int
    kickoff: str
    league: str
    match: str
    cluster: str
    top_coherent: tuple[ExactScorePick, ...]
    value_scores: tuple[ExactScorePick, ...]
    comeback_scores: tuple[ExactScorePick, ...]
    entropy: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_nesine_score_odds(match: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for s in match.get("selections") or []:
        name = str(s.get("name") or "").strip()
        m = _SCORE_SEL_RE.match(name)
        if not m:
            continue
        odds = _flt(s.get("odds"))
        if odds is not None and odds > 1.05:
            out[f"{int(m.group(1))}-{int(m.group(2))}"] = odds
    return out


def analyze_exact_scores(
    match: Mapping[str, Any],
    *,
    ft_dist: Mapping[str, float] | None = None,
    research_row: Mapping[str, Any] | None = None,
) -> ExactScoreAnalysis | None:
    """Produce macro-coherent top-3 exact scores, positive-EV value scores, and comeback-aligned scores."""
    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    if mh is None or ma is None or (mh + ma) <= 0.2:
        return None
    lg = str(match.get("league") or "")
    sels = _selection_map(match)
    f1x2 = _extract_market_1x2(match)
    p_o25 = _flt((sels.get("2.5 Üst") or {}).get("fair_prob"))
    p_btts = _flt((sels.get("KG Var") or {}).get("fair_prob"))
    h_shift, a_shift, _ = _extract_team_half_shifts(match, research_row)

    bundle = compute_omni_markets(
        mh,
        ma,
        league=lg,
        first_half_share=league_first_half_share(lg),
        home_1h_urgency_shift=h_shift,
        away_1h_urgency_shift=a_shift,
    )
    if ft_dist:
        dist_map = {str(k): float(v) for k, v in ft_dist.items() if float(v) > 0}
    else:
        joint = bundle.joint
        assert joint is not None
        g = joint.shape[0]
        ft_mat = np.zeros((2 * g - 1, 2 * g - 1), dtype=float)
        for h1 in range(g):
            for a1 in range(g):
                for h2 in range(g):
                    for a2 in range(g):
                        ft_mat[h1 + h2, a1 + a2] += joint[h1, a1, h2, a2]
        ft_mat /= max(float(ft_mat.sum()), 1e-12)
        dist_map = {
            f"{i}-{j}": float(ft_mat[i, j])
            for i in range(min(8, ft_mat.shape[0]))
            for j in range(min(8, ft_mat.shape[1]))
            if ft_mat[i, j] >= 1e-4
        }

    ranked = rank_macro_coherent_scores(
        dist_map,
        f1x2=f1x2,
        p_o25=p_o25,
        p_btts=p_btts,
        mu_home=mh,
        mu_away=ma,
    )
    if not ranked:
        return None

    score_odds = _extract_nesine_score_odds(match)

    def _make_pick(sc: str, p: float) -> ExactScorePick:
        p_c = max(1e-5, float(p))
        no = score_odds.get(sc)
        ev = round(p_c * no - 1.0, 4) if no is not None else None
        return ExactScorePick(score=sc, prob=round(p_c, 5), fair_odds=round(1.0 / p_c, 2), nesine_odds=no, ev=ev)

    top_coherent = tuple(_make_pick(sc, p) for sc, p in ranked[:3])

    # Value exact scores against actual Nesine exact-score prices (prob >= 2%, odds >= 4.5)
    val_cands = [
        _make_pick(sc, p)
        for sc, p in dist_map.items()
        if sc in score_odds and score_odds[sc] >= 4.5 and p >= 0.020
    ]
    val_cands = [x for x in val_cands if x.ev is not None and x.ev >= 0.02]
    val_cands.sort(key=lambda x: (-(x.ev or -9.0), -x.prob))
    value_scores = tuple(val_cands[:3])

    # Comeback-compatible scores (1-2, 2-1, 2-3, 3-2, 1-3, 3-1)
    cb_keys = ("2-1", "1-2", "3-1", "1-3", "3-2", "2-3")
    cb_picks = [_make_pick(sc, dist_map[sc]) for sc in cb_keys if sc in dist_map]
    cb_picks.sort(key=lambda x: -x.prob)
    comeback_scores = tuple(cb_picks[:3])

    # Score regime label
    mtot = mh + ma
    mmin = min(mh, ma)
    p1 = f1x2[0] if f1x2 else 0.34
    px = f1x2[1] if f1x2 else 0.32
    p2 = f1x2[2] if f1x2 else 0.34
    if abs(p1 - p2) <= 0.08 and px >= 0.275 and mtot <= 2.45:
        cluster = "Gerçek Beraberlik (0-0 / 1-1)"
    elif mtot >= 3.15 and mmin >= 1.15:
        cluster = "Açık Gollü Düello (2-1 / 2-2 / 3-2)"
    elif mmin >= 0.98 and mtot >= 2.55:
        cluster = "KG+Üst Galibiyet (2-1 / 1-2)"
    else:
        cluster = "Favori Temiz Galibiyet (1-0 / 2-0)"

    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    return ExactScoreAnalysis(
        code=int(match.get("code") or 0),
        kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
        league=lg,
        match=mname,
        cluster=cluster,
        top_coherent=top_coherent,
        value_scores=value_scores,
        comeback_scores=comeback_scores,
        entropy=round(float(bundle.score_entropy), 4),
    )


# --------------------------------------------------------------------------- #
# 4. Nesine Bayat Oran / Düşük Marj Tarayıcısı & Otomatik Lig/Pazar Kara Liste
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StaleOddsAnomaly:
    code: int
    kickoff: str
    league: str
    match: str
    selection_name: str
    nesine_odds: float
    fair_prob: float
    ev: float
    dir_steam_pp: float | None
    nesine_1x2_margin: float | None
    kind: str  # "bayat_oran" | "dusuk_marj"
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def scan_nesine_value_anomalies(
    matches: Sequence[Mapping[str, Any]],
    *,
    min_ev: float = 0.02,
    min_steam_pp: float = 2.5,
    low_margin_threshold: float = 0.095,
    top_n: int = 15,
) -> list[StaleOddsAnomaly]:
    """Scan daily matches for stale Nesine odds lagging sharp steam or unusually low-margin +EV lines."""
    found: list[StaleOddsAnomaly] = []
    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        mname = str(m.get("match") or f"{m.get('home', '')} - {m.get('away', '')}")
        margin = _flt(m.get("nesine_ms_margin") if m.get("nesine_ms_margin") is not None else m.get("nesine_1x2_margin"))
        for s in m.get("selections") or []:
            if not s.get("direct"):
                continue
            name = str(s.get("name") or "")
            odds = _flt(s.get("odds"))
            p = _flt(s.get("fair_prob"))
            if odds is None or p is None or odds < 1.20 or p < 0.15:
                continue
            ev = p * odds - 1.0
            if ev < min_ev:
                continue
            d_steam = parse_directional_steam(m, name)
            d_pp = round(100.0 * d_steam, 2) if d_steam is not None else None
            if d_pp is not None and d_pp >= min_steam_pp:
                found.append(
                    StaleOddsAnomaly(
                        code=int(m.get("code") or 0),
                        kickoff=str(m.get("kickoff") or (m.get("kickoff_iso") or "")[:16]),
                        league=str(m.get("league") or ""),
                        match=mname,
                        selection_name=name,
                        nesine_odds=round(odds, 2),
                        fair_prob=round(p, 4),
                        ev=round(ev, 4),
                        dir_steam_pp=d_pp,
                        nesine_1x2_margin=round(margin, 4) if margin is not None else None,
                        kind="bayat_oran",
                        note=f"Keskin piyasa {d_pp:+.1f}p düştü, Nesine @{odds:.2f} hâlâ +%{100*ev:.1f} EV",
                    )
                )
            elif margin is not None and margin <= low_margin_threshold and ev >= max(min_ev, 0.03):
                found.append(
                    StaleOddsAnomaly(
                        code=int(m.get("code") or 0),
                        kickoff=str(m.get("kickoff") or (m.get("kickoff_iso") or "")[:16]),
                        league=str(m.get("league") or ""),
                        match=mname,
                        selection_name=name,
                        nesine_odds=round(odds, 2),
                        fair_prob=round(p, 4),
                        ev=round(ev, 4),
                        dir_steam_pp=d_pp,
                        nesine_1x2_margin=round(margin, 4),
                        kind="dusuk_marj",
                        note=f"Düşük Nesine marjı (%{100*margin:.1f}) + pozitif EV (+%{100*ev:.1f})",
                    )
                )
    found.sort(key=lambda x: (0 if x.kind == "bayat_oran" else 1, -x.ev, -(x.dir_steam_pp or 0.0)))
    return found[:top_n]


def build_league_market_blacklist(
    settled_rows: Sequence[Mapping[str, Any]],
    *,
    min_samples: int = 15,
    max_bias: float = -0.08,
    max_roi: float = -0.15,
) -> list[dict[str, Any]]:
    """Auto-detect chronically negative (league, family) pairs from settled historical picks."""
    buckets: dict[tuple[str, str], dict[str, float]] = {}
    for r in settled_rows:
        lg = str(r.get("league") or r.get("lig") or "").strip()
        sel = str(r.get("selection") or r.get("secim_adi") or r.get("name") or "").strip()
        fam = str(r.get("family") or (bet_family(sel) if sel else "")).strip()
        p = _flt(r.get("p") if r.get("p") is not None else r.get("olasilik"))
        odds = _flt(r.get("odds") if r.get("odds") is not None else r.get("nesine_oran"))
        won_raw = r.get("won")
        if won_raw is None:
            res_s = str(r.get("sonuc") or "").strip().lower()
            if res_s in ("tuttu", "win", "1", "true"):
                won = 1.0
            elif res_s in ("yatti", "yattı", "loss", "0", "false"):
                won = 0.0
            else:
                continue
        else:
            won = 1.0 if bool(won_raw) else 0.0
        if not lg or not fam or p is None or odds is None or odds <= 1.0:
            continue
        st = buckets.setdefault((lg, fam), {"n": 0.0, "wins": 0.0, "p_sum": 0.0, "ret": 0.0})
        st["n"] += 1.0
        st["wins"] += won
        st["p_sum"] += p
        st["ret"] += (odds - 1.0) if won > 0.5 else -1.0

    blocked: list[dict[str, Any]] = []
    for (lg, fam), st in buckets.items():
        n = int(st["n"])
        if n < min_samples:
            continue
        hit = st["wins"] / n
        pred = st["p_sum"] / n
        bias = hit - pred
        roi = st["ret"] / n
        if bias <= max_bias and roi <= max_roi:
            blocked.append(
                {
                    "league": lg,
                    "family": fam,
                    "n": n,
                    "hit_rate": round(hit, 4),
                    "pred_rate": round(pred, 4),
                    "bias": round(bias, 4),
                    "roi": round(roi, 4),
                }
            )
    blocked.sort(key=lambda x: (x["roi"], x["bias"]))
    return blocked


# --------------------------------------------------------------------------- #
# 5. Birleşik Günlük Yüksek Oran Tarayıcı & 100 TL Sistem Kuponu
# --------------------------------------------------------------------------- #


def build_high_odds_system(
    comebacks: Sequence[ComebackCandidate],
    both_btts: Sequence[ExtremeGoalCandidate],
    close_matches: Sequence[CloseMatchAnalysis],
    *,
    budget_tl: float = 100.0,
    max_legs: int = 5,
    top_n: int = 2,
) -> list[SystemEvaluation]:
    """Build MBS-compliant 100 TL high-odds system coupons from top comeback / BTTS-both-halves / close-match picks."""
    legs: list[SystemLeg] = []
    seen: set[int] = set()

    for c in comebacks:
        if c.code in seen or c.nesine_odds is None or c.nesine_odds < 4.0:
            continue
        seen.add(c.code)
        legs.append(SystemLeg(str(c.code), c.match, c.kind, float(c.nesine_odds), float(c.p_comeback),
                              mbs=int(c.extra.get("mbs") or 1), kickoff=c.kickoff, league=c.league))
        if len(legs) >= max_legs:
            break

    for b in both_btts:
        if len(legs) >= max_legs:
            break
        if b.code in seen or b.nesine_odds is None or b.nesine_odds < 3.0:
            continue
        seen.add(b.code)
        legs.append(SystemLeg(str(b.code), b.match, b.kind, float(b.nesine_odds), float(b.p_tail),
                              mbs=int(b.extra.get("mbs") or 1), kickoff=b.kickoff, league=b.league))

    for cm in close_matches:
        if len(legs) >= max_legs:
            break
        if cm.code in seen or cm.best_odds is None or cm.best_odds < 1.85:
            continue
        if cm.verdict not in ("GÜÇLÜ DEĞER", "DEĞER"):
            continue
        seen.add(cm.code)
        legs.append(SystemLeg(str(cm.code), cm.match, cm.best_outcome, float(cm.best_odds), float(cm.best_prob),
                              mbs=1, kickoff=cm.kickoff, league=cm.league))

    if len(legs) < 2:
        return []
    return optimize_system(legs, budget_tl, mode="yuksek_oran", top_n=top_n)


def scan_high_odds_day(
    matches: Sequence[Mapping[str, Any]],
    research_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    *,
    ft_dist_by_code: Mapping[int, Mapping[str, float]] | None = None,
    only_offered: bool = True,
    min_comeback_dna: float = 52.0,
    min_btts_dna: float = 55.0,
    top_n: int = 10,
) -> dict[str, Any]:
    """Run all 4 high-odds intelligence modules across a day's priced matches."""
    res_map = research_by_code or {}
    dist_map = ft_dist_by_code or {}
    close_list: list[CloseMatchAnalysis] = []
    comeback_list: list[ComebackCandidate] = []
    both_btts_list: list[ExtremeGoalCandidate] = []
    exact_list: list[ExactScoreAnalysis] = []

    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        code = int(m.get("code") or 0)
        row = res_map.get(code)

        cm = analyze_close_match(m)
        if cm and cm.is_close_match:
            close_list.append(cm)

        for cb in score_comeback_htft(m, row):
            if cb.dna_score >= min_comeback_dna and (not only_offered or cb.nesine_odds is not None):
                comeback_list.append(cb)

        bb = score_both_halves_btts_match(m, row)
        if bb and bb.dna_score >= min_btts_dna and (not only_offered or bb.nesine_odds is not None):
            both_btts_list.append(bb)

        es = analyze_exact_scores(m, ft_dist=dist_map.get(code), research_row=row)
        if es is not None:
            exact_list.append(es)

    verdict_rank = {"GÜÇLÜ DEĞER": 0, "DEĞER": 1, "DENGELİ — ÇİFTE ŞANS": 2, "PAS — GERÇEK YAZI-TURA": 3}
    close_list.sort(
        key=lambda x: (
            verdict_rank.get(x.verdict, 9),
            -x.conviction_score,
            -(x.best_ev if x.best_ev is not None else -9.0),
        )
    )
    comeback_list.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0), -x.p_comeback))
    both_btts_list.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0), -x.p_tail))
    exact_list.sort(
        key=lambda x: (
            -(x.value_scores[0].ev if x.value_scores and x.value_scores[0].ev is not None else -1.0),
            -(x.top_coherent[0].prob if x.top_coherent else 0.0),
        )
    )
    stale = scan_nesine_value_anomalies(matches, top_n=top_n)
    systems = build_high_odds_system(comeback_list[:top_n], both_btts_list[:top_n], close_list[:top_n])

    return {
        "close_matches": close_list[:top_n],
        "comebacks": comeback_list[:top_n],
        "both_halves_btts": both_btts_list[:top_n],
        "exact_scores": exact_list[:top_n],
        "stale_edges": stale,
        "systems_100tl": systems,
    }
