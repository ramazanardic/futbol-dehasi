"""Canlı (in-play) gol modeli: kalan süredeki gol yoğunluğu → maç sonu pazarlarının adil olasılığı.

Model (her parametre açıkça varsayımdır, ileri-yürüyen testle doğrulanmadı):
* Maç öncesi gol beklentileri (λ_ev, λ_dep) maç öncesi fiyattan (1X2 + 2,5 Alt/Üst) Poisson ile uydurulur.
* Gol yoğunluğu maç boyunca artar (Dixon & Robinson 1998): r(t) ∝ 1 + k·t/90, k = 0.4. Kalan pay
  F(t) = ∫_t^T r / ∫_0^T r, T = 90 + uzatma (varsayılan 4 dk).
* Kırmızı kart: eksik takımın yoğunluğu × 0.75, rakibin × 1.20 (kart başına) — varsayım.
* Skor durumu: geride olan takım × 1.10, önde olan × 0.95 (son 30 dk'da) — varsayım.
* Baskı (xG vekili): isabetli şut × 0.30 + isabetsiz şut × 0.04 (+ korner × 0.02). Gözlenen vekilin, maç
  öncesi beklentinin geçen süreye düşen payına oranı, beklenen değere eşit ağırlıklı bir önselle büzülür
  ve [0.75, 1.35] aralığına kırpılır.
Canlı keskin referans varsa (API-Football canlı oranları) kalan yoğunluklar doğrudan ona uydurulur.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

INTENSITY_SLOPE = 0.4
RED_SELF, RED_OPP = 0.75, 1.20
TRAIL_BOOST, LEAD_DAMP = 1.10, 0.95
MAX_GOALS = 12


@dataclass
class LiveState:
    minute: float
    home_goals: int = 0
    away_goals: int = 0
    home_red: int = 0
    away_red: int = 0
    stoppage: float = 4.0
    stats: dict[str, dict[str, float]] = field(default_factory=dict)  # {"home": {"sot":..,"shots":..,"corners":..}, "away": ...}


def remaining_share(minute: float, stoppage: float = 4.0, k: float = INTENSITY_SLOPE) -> float:
    T = 90.0 + stoppage
    t = min(max(minute, 0.0), T)

    def cum(x: float) -> float:
        return x + k * x * x / 180.0

    return max(0.0, (cum(T) - cum(t)) / cum(T))


DEFAULT_INPLAY_RHO = -0.08


def _grid(lh: float, la: float, rho: float = DEFAULT_INPLAY_RHO) -> np.ndarray:
    lh_safe = max(float(lh), 1e-9)
    la_safe = max(float(la), 1e-9)
    g = np.arange(MAX_GOALS + 1)
    G = np.outer(poisson.pmf(g, lh_safe), poisson.pmf(g, la_safe))
    # Dixon-Coles low-score correlation scaled smoothly by remaining goal mass
    if rho != 0.0 and (lh_safe + la_safe) > 0.05:
        rho_eff = float(rho) * min(1.0, (lh_safe + la_safe) / 2.5)
        tau00 = max(0.05, 1.0 - lh_safe * la_safe * rho_eff)
        tau10 = max(0.05, 1.0 + la_safe * rho_eff)
        tau01 = max(0.05, 1.0 + lh_safe * rho_eff)
        tau11 = max(0.05, 1.0 - rho_eff)
        G[0, 0] *= tau00
        G[1, 0] *= tau10
        G[0, 1] *= tau01
        G[1, 1] *= tau11
        tot = float(G.sum())
        if tot > 0.0:
            G /= tot
    return G


def final_probabilities(lh_rem: float, la_rem: float, hg: int = 0, ag: int = 0,
                        lines: tuple[float, ...] = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)) -> dict[str, float]:
    """Kalan gol yoğunluklarından maç SONU pazarları (mevcut skor dahil)."""
    G = _grid(lh_rem, la_rem)
    g = np.arange(MAX_GOALS + 1)
    H = hg + g[:, None]
    A = ag + g[None, :]
    tot = H + A
    p1 = float(G[H > A].sum())
    px = float(G[H == A].sum())
    p2 = float(G[H < A].sum())
    out = {
        "MS 1": p1,
        "MS X": px,
        "MS 2": p2,
        "ÇŞ 1X": p1 + px,
        "ÇŞ 12": p1 + p2,
        "ÇŞ X2": px + p2,
        "KG Var": float(G[(H > 0) & (A > 0)].sum()),
    }
    out["KG Yok"] = 1.0 - out["KG Var"]
    for ln in lines:
        o = float(G[tot > ln].sum())
        out[f"{ln} Üst"], out[f"{ln} Alt"] = o, 1.0 - o
    return out


def fit_lambdas(targets: dict[str, float], hg: int = 0, ag: int = 0, x0: tuple[float, float] = (1.4, 1.1)) -> tuple[float, float]:
    """Hedef olasılıklara (ör. {"MS 1":..,"MS X":..,"2.5 Üst":..}) en yakın (λ_ev, λ_dep)."""
    keys = [k for k in targets if targets[k] is not None]
    if not keys:
        raise ValueError("hedef olasılık yok")

    def loss(x: np.ndarray) -> float:
        xc = np.clip(x, -6.0, 2.5)
        lh, la = np.exp(xc)
        p = final_probabilities(lh, la, hg, ag)
        return sum((p.get(k, 0.0) - targets[k]) ** 2 for k in keys)

    res = minimize(loss, np.log(np.maximum(x0, 0.05)), method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-9, "maxiter": 400})
    lh, la = np.exp(np.clip(res.x, -6.0, 2.5))
    return float(lh), float(la)


def xg_proxy(st: dict[str, float] | None) -> float | None:
    if not st:
        return None
    if st.get("xg") is not None:   # gerçek canlı xG (FotMob) varsa onu kullan
        return float(st["xg"])
    sot, shots = st.get("sot"), st.get("shots")
    if sot is None and shots is None:
        return None
    sot = float(sot or 0.0)
    off = max(0.0, float(shots or 0.0) - sot)
    return 0.30 * sot + 0.04 * off + 0.02 * float(st.get("corners") or 0.0)


def pressure_multiplier(observed: float | None, expected_so_far: float) -> float:
    if observed is None or expected_so_far <= 0:
        return 1.0
    m = (observed + expected_so_far) / (2.0 * expected_so_far)  # eşit ağırlıklı önsel
    return float(min(1.35, max(0.75, m)))


def remaining_lambdas(lh: float, la: float, s: LiveState) -> tuple[float, float, list[str]]:
    """Maç öncesi λ'lardan kalan süre yoğunlukları + uygulanan ayarların açıklaması."""
    share = remaining_share(s.minute, s.stoppage)
    rh, ra = lh * share, la * share
    notes = [f"kalan pay {share:.2f}"]
    dr = s.home_red - s.away_red
    if dr:
        fh = (RED_SELF if dr > 0 else RED_OPP) ** abs(dr)
        fa = (RED_OPP if dr > 0 else RED_SELF) ** abs(dr)
        rh, ra = rh * fh, ra * fa
        notes.append(f"kırmızı kart farkı {dr:+d}")
    if s.minute >= 60 and s.home_goals != s.away_goals:
        if s.home_goals < s.away_goals:
            rh, ra = rh * TRAIL_BOOST, ra * LEAD_DAMP
        else:
            rh, ra = rh * LEAD_DAMP, ra * TRAIL_BOOST
        notes.append("skor durumu")
    played = 1.0 - share
    for side, lam in (("home", lh), ("away", la)):
        m = pressure_multiplier(xg_proxy(s.stats.get(side)), lam * played)
        if abs(m - 1.0) > 1e-9:
            if side == "home":
                rh *= m
            else:
                ra *= m
            notes.append(f"baskı {'ev' if side == 'home' else 'dep'} ×{m:.2f}")
    return rh, ra, notes


def devig_power(odds: list[float]) -> list[float] | None:
    if not odds or any(o is None or o <= 1.0 for o in odds):
        return None
    inv = np.array([1.0 / o for o in odds])
    if inv.sum() <= 1.0:
        return list(inv / inv.sum())
    lo, hi = 1.0, 10.0
    for _ in range(80):
        k = (lo + hi) / 2
        if (inv ** k).sum() > 1.0:
            lo = k
        else:
            hi = k
    p = inv ** ((lo + hi) / 2)
    return list(p / p.sum())


def kelly_stake(prob: float, odds: float, bankroll: float, multiplier: float = 0.25, cap_frac: float = 0.2,
                step: float = 5.0, min_stake: float = 5.0) -> float:
    if bankroll <= 0 or odds <= 1.0:
        return 0.0
    f = (prob * odds - 1.0) / (odds - 1.0)
    if f <= 0:
        return 0.0
    amt = min(multiplier * f, cap_frac) * bankroll
    amt = math.floor(amt / step) * step
    return float(amt) if amt >= min_stake else 0.0
