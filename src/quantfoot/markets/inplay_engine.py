"""Canlı (Maç İçi / In-Play) Dakika-Dakika Yeniden Fiyatlama, Kırmızı Kart ve Geri Dönüş Motoru.

Maç oynanırken anlık skor, dakika, kırmızı kart sayısı ve canlı xG/isabetli şut verisine göre:
1. **Homojen Olmayan Dakika Yoğunluk Eğrisi:** 40–45+' ve 75–90+' uzatma/yorgunluk gol artışlarını tam yansıtır.
2. **Kırmızı Kart Şoku:** Kırmızı kart gören takımın kalan hücum hızı ×0.72, rakibin hücum hızı ×1.34 olur.
3. **Skor-Durumu (Game-State) Dinamiği:** 1 gol geride olan takım baskıyı artırır (+%14 hücum, +%15 rakip kontra).
4. **Empirical-Bayes Canlı xG/Şut Füzyonu:** Maç öncesi keskin prior'ı, geçen dakikanın canlı xG/SOT temposuyla
   ölçekli biçimde harmanlar (erken 10 dakikalık gürültüye kapılmaz, 60. dakikada baskıyı gerçekçi yakalar).
5. **Canlı Fırsat & Geri Dönüş Tarayıcısı:** Canlı 1X2, Sonraki Gol, Canlı Alt/Üst (0.5..5.5), Canlı KG Var,
   En Olası Maç Sonu Skorları ve "0-1 geride ama canlı xG baskın — canlı geri dönüş" fırsatını üretir.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np

from quantfoot.markets.tail_goals import DEFAULT_RHO, league_tail_regime, regime_score_matrix

# Cumulative goal fraction by minute checkpoints (empirical club football: 1H ~43.8%, 2H ~56.2%, surge at 75-90+)
_CUM_CHECKPOINTS: tuple[tuple[float, float], ...] = (
    (0.0, 0.000),
    (15.0, 0.128),
    (30.0, 0.273),
    (45.0, 0.438),
    (60.0, 0.606),
    (75.0, 0.780),
    (90.0, 0.960),
    (95.0, 1.000),
)

RED_OWN_ATTACK_MULT = 0.72
RED_OPP_ATTACK_MULT = 1.34


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def elapsed_goal_fraction(minute: float, *, first_half_share: float = 0.438) -> float:
    """Cumulative fraction of total match goals expected to have occurred by ``minute`` (0..95)."""
    m = _clip(float(minute), 0.0, 95.0)
    s1 = _clip(float(first_half_share), 0.30, 0.58)
    s2 = 1.0 - s1

    # Rescale 1H [0..45] and 2H [45..95] checkpoints to match team's specific 1H share
    scaled: list[tuple[float, float]] = []
    for t, f in _CUM_CHECKPOINTS:
        if t <= 45.0:
            scaled.append((t, (f / 0.438) * s1))
        else:
            scaled.append((t, s1 + ((f - 0.438) / 0.562) * s2))

    for i in range(len(scaled) - 1):
        t0, f0 = scaled[i]
        t1, f1 = scaled[i + 1]
        if t0 <= m <= t1:
            alpha = (m - t0) / max(t1 - t0, 1e-6)
            return float(_clip(f0 + alpha * (f1 - f0), 0.0, 1.0))
    return 1.0


@dataclass(frozen=True)
class InPlayState:
    """Snapshot of a live football match at a given minute."""

    minute: float
    score_home: int
    score_away: int
    pre_mu_home: float
    pre_mu_away: float
    red_home: int = 0
    red_away: int = 0
    live_xg_home: float | None = None
    live_xg_away: float | None = None
    live_sot_home: int | None = None
    live_sot_away: int | None = None
    home_1h_share: float = 0.440
    away_1h_share: float = 0.425
    league: str = ""
    home: str = "Ev"
    away: str = "Dep"


@dataclass(frozen=True)
class InPlayPricing:
    """Minute-by-minute repriced live probabilities, remaining xG, and tactical signals."""

    minute: float
    score: str
    rem_mu_home: float
    rem_mu_away: float
    live_1x2: dict[str, float]
    next_goal: dict[str, float]
    live_ou: dict[str, float]
    live_btts: dict[str, float]
    top_final_scores: dict[str, float]
    comeback_alert: str | None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reprice_inplay(state: InPlayState) -> InPlayPricing:
    """Compute exact live remaining-time probabilities given score, minute, red cards, and live xG/SOT."""
    m = _clip(state.minute, 0.0, 95.0)
    sh, sa = max(0, int(state.score_home)), max(0, int(state.score_away))
    rh, ra = max(0, min(3, int(state.red_home))), max(0, min(3, int(state.red_away)))

    # Remaining goal fractions for home & away
    el_h = elapsed_goal_fraction(m, first_half_share=state.home_1h_share)
    el_a = elapsed_goal_fraction(m, first_half_share=state.away_1h_share)
    rem_frac_h = max(0.0, 1.0 - el_h)
    rem_frac_a = max(0.0, 1.0 - el_a)

    # Live tempo update from live xG (or SOT proxy) with Empirical-Bayes elapsed-time weight
    eff_mu_h = max(0.15, float(state.pre_mu_home))
    eff_mu_a = max(0.15, float(state.pre_mu_away))
    notes: list[str] = []

    live_h = _flt(state.live_xg_home)
    live_a = _flt(state.live_xg_away)
    if live_h is None and state.live_sot_home is not None:
        live_h = 0.30 * max(0, int(state.live_sot_home))
    if live_a is None and state.live_sot_away is not None:
        live_a = 0.30 * max(0, int(state.live_sot_away))

    if m >= 12.0 and live_h is not None and live_a is not None:
        # Pace-implied full-match xG, capped against early small-sample spikes
        pace_h = _clip(live_h / max(el_h, 0.14), 0.20, 4.50)
        pace_a = _clip(live_a / max(el_a, 0.14), 0.20, 4.50)
        w_live = _clip((m / 90.0) * 0.48, 0.06, 0.45)
        eff_mu_h = (1.0 - w_live) * eff_mu_h + w_live * pace_h
        eff_mu_a = (1.0 - w_live) * eff_mu_a + w_live * pace_a
        notes.append(f"Canlı tempo harmanı (ağırlık %{100*w_live:.0f}): canlı xG {live_h:.2f}-{live_a:.2f}")

    rem_h = eff_mu_h * rem_frac_h
    rem_a = eff_mu_a * rem_frac_a

    # Score-state urgency (trailing team pushes harder in remaining minutes)
    diff = sh - sa
    if m >= 20.0 and rem_frac_h > 0.02:
        if diff == 1:
            rem_a *= 1.14
            rem_h *= 1.04
            notes.append("Skor durumu: deplasman 1 farkla geride — baskı ve kontra alanı yüksek")
        elif diff == -1:
            rem_h *= 1.15
            rem_a *= 1.04
            notes.append("Skor durumu: ev sahibi 1 farkla geride — baskı ve kontra alanı yüksek")
        elif abs(diff) >= 2 and m >= 65.0:
            rem_h *= 0.94
            rem_a *= 0.94
            notes.append("2+ fark ve geç dakika — tempo kontrollü")

    # Red-card impact on remaining scoring rates
    if rh > 0 or ra > 0:
        rem_h *= (RED_OWN_ATTACK_MULT ** min(rh, 2)) * (RED_OPP_ATTACK_MULT ** min(ra, 2))
        rem_a *= (RED_OWN_ATTACK_MULT ** min(ra, 2)) * (RED_OPP_ATTACK_MULT ** min(rh, 2))
        notes.append(f"Kırmızı kart etkisi (Ev {rh}K / Dep {ra}K): kalan xG {rem_h:.2f}–{rem_a:.2f}")

    # Build remaining-goals score matrix (or degenerate point mass at minute >= 95)
    if rem_h + rem_a <= 1e-5:
        mat = np.zeros((1, 1), dtype=float)
        mat[0, 0] = 1.0
    else:
        nu, alpha, kappa = league_tail_regime(state.league or "e0")
        mat = regime_score_matrix(
            max(1e-4, rem_h),
            max(1e-4, rem_a),
            alpha_nb=alpha,
            rho=DEFAULT_RHO * min(1.0, (rem_h + rem_a) / 2.2),
            shared_kappa=kappa,
            com_nu=nu,
            max_goals=8,
        )

    p1 = px = p2 = 0.0
    btts_yes = 0.0
    ou_over: dict[float, float] = {ln: 0.0 for ln in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)}
    score_probs: dict[str, float] = {}

    gh_max, ga_max = mat.shape
    for dh in range(gh_max):
        for da in range(ga_max):
            p = float(mat[dh, da])
            if p <= 0:
                continue
            fh, fa = sh + dh, sa + da
            if fh > fa:
                p1 += p
            elif fh == fa:
                px += p
            else:
                p2 += p
            if fh >= 1 and fa >= 1:
                btts_yes += p
            tot = fh + fa
            for ln in ou_over:
                if tot > ln:
                    ou_over[ln] += p
            sk = f"{fh}-{fa}"
            score_probs[sk] = score_probs.get(sk, 0.0) + p

    # Next Goal probabilities from competing Poisson processes over remaining time
    p_no_more = float(mat[0, 0])
    p_some_more = max(0.0, 1.0 - p_no_more)
    tot_rem = rem_h + rem_a
    if tot_rem > 1e-6:
        p_next_h = p_some_more * (rem_h / tot_rem)
        p_next_a = p_some_more * (rem_a / tot_rem)
    else:
        p_next_h = p_next_a = 0.0

    # Live Comeback Opportunity Detector
    comeback_alert: str | None = None
    if diff == -1 and m <= 70.0 and p1 >= 0.24 and rem_h >= rem_a + 0.25:
        comeback_alert = (
            f"🔥 Canlı Ev Geri Dönüş Fırsatı ({state.home} {sh}-{sa} geride, dk {m:.0f}'): "
            f"kalan xG {rem_h:.2f} vs {rem_a:.2f} -> Canlı MS 1 %{100*p1:.1f} (ÇŞ 1X %{100*(p1+px):.1f})"
        )
    elif diff == 1 and m <= 70.0 and p2 >= 0.24 and rem_a >= rem_h + 0.25:
        comeback_alert = (
            f"🔥 Canlı Deplasman Geri Dönüş Fırsatı ({state.away} {sh}-{sa} geride, dk {m:.0f}'): "
            f"kalan xG {rem_a:.2f} vs {rem_h:.2f} -> Canlı MS 2 %{100*p2:.1f} (ÇŞ X2 %{100*(p2+px):.1f})"
        )

    live_ou: dict[str, float] = {}
    for ln, pv in ou_over.items():
        live_ou[f"{ln:.1f} Üst"] = round(pv, 4)
        live_ou[f"{ln:.1f} Alt"] = round(max(0.0, 1.0 - pv), 4)

    top_scores = {k: round(v, 4) for k, v in sorted(score_probs.items(), key=lambda kv: -kv[1])[:6]}

    return InPlayPricing(
        minute=round(m, 1),
        score=f"{sh}-{sa}",
        rem_mu_home=round(rem_h, 3),
        rem_mu_away=round(rem_a, 3),
        live_1x2={"MS 1": round(p1, 4), "MS 0": round(px, 4), "MS 2": round(p2, 4)},
        next_goal={
            "Sonraki Gol Ev": round(p_next_h, 4),
            "Sonraki Gol Dep": round(p_next_a, 4),
            "Gol Olmaz": round(p_no_more, 4),
        },
        live_ou=live_ou,
        live_btts={"KG Var": round(btts_yes, 4), "KG Yok": round(max(0.0, 1.0 - btts_yes), 4)},
        top_final_scores=top_scores,
        comeback_alert=comeback_alert,
        notes=tuple(notes),
    )


def from_fotmob_details(
    details: Mapping[str, Any],
    *,
    minute: float,
    pre_mu_home: float,
    pre_mu_away: float,
    home: str = "Ev",
    away: str = "Dep",
    league: str = "",
) -> InPlayState:
    """Adapter converting ``quantfoot.data.fotmob.parse_details`` output into ``InPlayState``."""
    score = details.get("score") or [0, 0]
    reds = details.get("red") or [0, 0]
    stats = details.get("stats") or {}
    hs = stats.get("home") or {}
    as_ = stats.get("away") or {}
    return InPlayState(
        minute=float(minute),
        score_home=int(score[0] or 0),
        score_away=int(score[1] or 0),
        pre_mu_home=float(pre_mu_home),
        pre_mu_away=float(pre_mu_away),
        red_home=int(reds[0] or 0),
        red_away=int(reds[1] or 0),
        live_xg_home=_flt(hs.get("xg")),
        live_xg_away=_flt(as_.get("xg")),
        live_sot_home=int(hs["sot"]) if hs.get("sot") is not None else None,
        live_sot_away=int(as_["sot"]) if as_.get("sot") is not None else None,
        league=league,
        home=home,
        away=away,
    )
