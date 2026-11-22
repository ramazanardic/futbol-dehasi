"""Post-mortem hardened risk filters, omni-market best-bet selector, and target-odds (10x/20x/30x) coupon optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence

from quantfoot.markets.omni_markets import OmniMarketBundle

MIN_ALLOWED_ODDS: float = 1.20

# Competitions the models were never trained or calibrated on (training data: men's leagues).
# Model probabilities there are unreliable, so no recommendation is produced by default.
_UNCALIBRATED_TOKENS: tuple[str, ...] = (
    "women", "wchampions", "eng.w.", "reina", "frauen", "féminine", "feminine",
    "femenina", "femminile", "nwsl", "w-league", "(k)", "kadın",
)


def is_uncalibrated_competition(league: str | None) -> bool:
    """Return True for competitions outside the models' calibration domain (e.g. women's football)."""
    if not league:
        return False
    low = league.lower()
    return any(tok in low for tok in _UNCALIBRATED_TOKENS)


_CUP_TOKENS: tuple[str, ...] = (
    "kupa", "cup", "pokal", "coupe", "copa", "taça", "taca", "coppa",
    "beker", "trophy", "shield", "playoff", "play-off", "eleme", "düşme turu", "dusme turu",
)

_MAIN_MARKET_SELECTIONS: frozenset[str] = frozenset({
    "MS 1", "MS 0", "MS 2",
    "ÇŞ 10", "ÇŞ 12", "ÇŞ 02",
    "1.5 Alt", "1.5 Üst",
    "2.5 Alt", "2.5 Üst",
    "3.5 Alt", "3.5 Üst",
    "KG Var", "KG Yok",
})


def is_cup_competition(league: str | None) -> bool:
    """Return True for knockout cups, playoffs, or relegation-playoff ties (rotation & 90' draw traps)."""
    if not league:
        return False
    low = league.replace("İ", "i").replace("I", "i").lower()
    return any(tok in low for tok in _CUP_TOKENS)


def is_main_market_selection(selection_name: str | None) -> bool:
    """Return True for core full-time main markets (1X2, Double Chance, O/U 1.5/2.5/3.5, BTTS)."""
    return bool(selection_name and selection_name.strip() in _MAIN_MARKET_SELECTIONS)


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
    # Nov 19 post-mortem hardening flags (backward-compatible defaults):
    is_knockout: bool = False               # Single-leg cup / playoff (90' extra-time & penalty draw trap)
    has_ou_market: bool = True              # False when only 1X2 exists without a live O/U total-goals anchor
    btts_market_prob: float | None = None   # Devigged 2-way market P(KG Var) for blowout phantom-+EV check
    btts_is_direct: bool = False            # True when KG Var/Yok comes from a direct sharp exchange quote


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
    mbs: int = 1
    prob_sigma: float = 0.0  # estimation uncertainty (0 for exact/unspecified; >=0.01 direct, >=0.025 model)

    @property
    def reliable_probability(self) -> float:
        """One-sided ~90% lower-bound probability (penalises noisier model derivatives vs direct exchange quotes)."""
        return max(0.001, self.probability - 1.28 * max(0.0, self.prob_sigma))


@dataclass(frozen=True)
class PortfolioCouponSpec:
    """Specification for one coupon inside a diversified multi-coupon portfolio."""

    title: str
    target_odds: float
    max_legs: int = 8
    min_leg_odds: float = MIN_ALLOWED_ODDS
    min_leg_ev: float | None = 0.0
    allowed_categories: tuple[str, ...] | None = None
    min_leg_prob: float | None = None


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
    reached_target: bool = True  # False when the pool could not reach target_odds within max_legs
    expected_value: float = 0.0  # joint_probability * achieved_odds - 1 (assumes independent legs)


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

    if tot >= 2.68 or max_mu >= 1.72 or (ctx.home_must_win and ctx.away_must_win):
        blocked["3.5 Alt"] = (
            f"Yüksek Tempo 3.5 Alt Tuzağı: Toplam xG={tot:.2f} / max xG={max_mu:.2f} "
            "(Örn: Troyes 3-1, Andorra 1-3, Galler-Portekiz 2-3 gibi geçiş maçlarında 3.5 Alt kırılgan)."
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

    # 6. BLOWOUT KG YOK UNIDENTIFIABILITY & PHANTOM +EV GUARD (Nov 19: Al Wasl 2-1, AL Ain 2-1, Gaddafi 2-2)
    # In lopsided blowouts, 1X2+O/U alone cannot pin mu_underdog accurately; when the market's own 2-way BTTS
    # prices KG Var >= 6% higher than the model, apparent +EV on KG Yok is model misspecification, not edge.
    p_btts_model = float(bundle.btts.get("KG Var", 0.5))
    if ctx.btts_market_prob is not None:
        p_btts_mkt = float(ctx.btts_market_prob)
        if p_btts_mkt - p_btts_model >= 0.06:
            reason_kgy = (
                f"Phantom +EV / KG Yok Yanılsaması: Piyasa 2-yönlü BTTS (%{p_btts_mkt*100:.1f}) "
                f"modelden (%{p_btts_model*100:.1f}) belirgin yüksek; dev favoride teselli/kontra golü riski "
                "(Örn: Al Wasl 2-1, AL Ain 2-1)."
            )
            for kgy_sel in ("KG Yok", "2.5 Alt & KG Yok", "MS 1 & KG Yok", "MS 2 & KG Yok"):
                blocked.setdefault(kgy_sel, reason_kgy)
        elif p_btts_model - p_btts_mkt >= 0.08:
            reason_kgv = (
                f"Piyasa KG Var Uyuşmazlığı: Piyasa 2-yönlü BTTS (%{p_btts_mkt*100:.1f}) "
                f"modelden (%{p_btts_model*100:.1f}) çok düşük."
            )
            for kgv_sel in ("KG Var", "2.5 Üst & KG Var"):
                blocked.setdefault(kgv_sel, reason_kgv)

    if tot >= 3.45 and p_fav >= 0.78 and min_mu >= 0.42:
        penalties["KG Yok"] = min(penalties.get("KG Yok", 1.0), 0.75)
        if ctx.btts_market_prob is not None and (1.0 - float(ctx.btts_market_prob)) < 0.56:
            blocked.setdefault(
                "KG Yok",
                f"Açık Maç Dev Favori KG Yok Tuzağı: Toplam xG={tot:.2f}, piyasa KG Yok olasılığı "
                f"düşük (%{(1.0 - float(ctx.btts_market_prob))*100:.1f}); Al Wasl / AL Ain 2-1 riski.",
            )

    # 7. SINGLE-LEG KNOCKOUT CUP / PLAYOFF 90' DRAW GUARD (Nov 19: Roltek Dob 1-1, Mokawloon 1-1, Queensland 1-1)
    if ctx.is_knockout:
        if p_fav < 0.72:
            ko_reason = (
                f"Tek Maçlı Kupa/Playoff 90' Beraberlik Tuzağı (p_fav=%{p_fav*100:.1f} < %72): "
                "Uzatma/penaltı motivasyonu MS bahislerini kırılganlaştırır (Örn: Roltek Dob 1-1, Mokawloon 1-1); "
                "Alt/Üst, KG veya ÇŞ tercih edilmeli."
            )
            for ko_sel in (
                "MS 1", "MS 2",
                "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst",
                "MS 1 & 2.5 Üst", "MS 2 & 2.5 Üst",
                "İY/MS 1/1", "İY/MS 2/2",
            ):
                blocked.setdefault(ko_sel, ko_reason)
        else:
            penalties["MS 1"] = min(penalties.get("MS 1", 1.0), 0.94)
            penalties["MS 2"] = min(penalties.get("MS 2", 1.0), 0.94)

    # 8. HIGH-DRAW DOUBLE-CHANCE 12 GUARD (Nov 19: ZED-Smouha, Malavan, Sao Paulo 0-0/1-1 trap)
    p_draw = float(bundle.ft_1x2["0"])
    if p_draw >= 0.275 or (ctx.is_knockout and p_draw >= 0.25):
        blocked.setdefault(
            "ÇŞ 12",
            f"Yüksek Beraberlik ÇŞ 12 Tuzağı (P(X)=%{p_draw*100:.1f}): Tek 0-0 / 1-1 skoru kuponu düşürür.",
        )

    # 9. MISSING GLOBAL O/U ANCHOR GATE (Nov 19: 6/13=%46.2 without O/U vs 8/12=%66.7 with O/U)
    if not ctx.has_ou_market:
        no_ou_reason = (
            "Küresel Alt/Üst (O/U) Piyasası Eksik: Yalnızca 1X2 + lig önselinden türetilen "
            "gol/KG tahminleri güvenilir değildir (Örn: Gaddafi 2-2, Farco 2-1, El Daklyeh 0-0)."
        )
        for no_ou_sel in (
            "KG Yok", "KG Var", "1.5 Üst", "2.5 Üst", "2.5 Alt", "3.5 Üst", "3.5 Alt",
            "2.5 Üst & KG Var", "2.5 Alt & KG Yok",
        ):
            blocked.setdefault(no_ou_sel, no_ou_reason)
        for side_sel in ("MS 1", "MS 2", "ÇŞ 10", "ÇŞ 02"):
            penalties[side_sel] = min(penalties.get(side_sel, 1.0), 0.85)

    # 10. UNDERDOG & SHOOTOUT COIN-FLIP DOUBLE-CHANCE (ÇŞ) GUARD
    # (Nov 19-20 post-mortem: Amiens 2-1 ÇŞ 02, Cundinamarca 0-2 ÇŞ 10, Orlando 1-3 ÇŞ 10, Vitoria 2-1 ÇŞ 02)
    # When the favorite's ÇŞ drops below 1.20, never leak onto the underdog's ÇŞ or onto a low-draw shootout coin-flip.
    p_home = float(bundle.ft_1x2["1"])
    p_away = float(bundle.ft_1x2["2"])
    p_dc10 = float(bundle.double_chance.get("10", p_home + p_draw))
    p_dc02 = float(bundle.double_chance.get("02", p_away + p_draw))
    if p_home - p_away >= 0.05 and p_dc02 < 0.68:
        blocked.setdefault(
            "ÇŞ 02",
            f"Favori Karşıtı ÇŞ 02 Tuzağı (Ev P=%{p_home*100:.1f} > Dep P=%{p_away*100:.1f}, P(02)=%{p_dc02*100:.1f}): "
            "Favorinin ÇŞ oranı <1.20 düştüğünde zayıf tarafın ÇŞ'sine kayılmaz (Örn: Amiens 2-1).",
        )
    if p_away - p_home >= 0.05 and p_dc10 < 0.68:
        blocked.setdefault(
            "ÇŞ 10",
            f"Favori Karşıtı ÇŞ 10 Tuzağı (Dep P=%{p_away*100:.1f} > Ev P=%{p_home*100:.1f}, P(10)=%{p_dc10*100:.1f}): "
            "Favorinin ÇŞ oranı <1.20 düştüğünde zayıf tarafın ÇŞ'sine kayılmaz (Örn: Cundinamarca 0-2).",
        )
    if tot >= 3.30 and abs(p_home - p_away) <= 0.12:
        shootout_dc_reason = (
            f"Yüksek Tempolu Dengeli Maç ÇŞ Tuzağı (xG={tot:.2f}, P(X)=%{p_draw*100:.1f}): "
            "Beraberlik olasılığı düşük gollü maçlarda taraf ÇŞ yerine Üst/KG tercih edilmeli (Örn: Orlando 1-3)."
        )
        blocked.setdefault("ÇŞ 10", shootout_dc_reason)
        blocked.setdefault("ÇŞ 02", shootout_dc_reason)
    elif abs(p_home - p_away) < 0.05:
        # True 50-50 coin-flip: penalize side ÇŞ so cleaner totals/BTTS rank ahead
        penalties["ÇŞ 10"] = min(penalties.get("ÇŞ 10", 1.0), 0.86)
        penalties["ÇŞ 02"] = min(penalties.get("ÇŞ 02", 1.0), 0.86)

    # 11. TIGHT-MATCH 1.5 ÜST & KNOCKOUT MARGINAL OVER GUARD
    # (Nov 19-20 post-mortem: ZED-Smouha 0-0 1.5 Üst, Sao Paulo 0-1 1.5 Üst, Dep. La Guaira 0-1 2.5 Üst)
    p_o15 = float(bundle.ft_ou.get("1.5 Üst", 0.0))
    p_o25 = float(bundle.ft_ou.get("2.5 Üst", 0.0))
    if tot < 2.25 or (tot < 2.50 and p_o15 < 0.72):
        blocked.setdefault(
            "1.5 Üst",
            f"Kısır Maç 1.5 Üst Tuzağı (xG={tot:.2f}, P(1.5 Üst)=%{p_o15*100:.1f}): "
            "0-0 / 1-0 / 0-1 riski %30+; savunma rejimine karşı 1.5 Üst yerine 2.5 Alt / KG Yok tercih edilmeli "
            "(Örn: ZED 0-0, Sao Paulo 0-1).",
        )
    if ctx.is_knockout and p_o25 < 0.60:
        blocked.setdefault(
            "2.5 Üst",
            f"Tek Maçlı Kupa Sınırda 2.5 Üst Tuzağı (P(2.5 Üst)=%{p_o25*100:.1f} < %60): "
            "Eleme maçında zayıf tarafın kapanma riski yüksek (Örn: Dep. La Guaira 0-1).",
        )

    # 12. FRAGILE MODERATE-FAVORITE 1X2 & MARGINAL 2.5-LINE PENALTY
    # (Nov 18-21 empirical audit across 330 matches: MS 1/2 at P<70% went 7/16=%43.8 on global & 18/33=%54.5 on local,
    # whereas KG Yok %87.5, 3.5 Alt (xG<2.68) %80.0, İY 0.5 Üst %76.5, KG Var %70.0, and 2.5 Üst (P>=62%) %68+ dominated.)
    if p_home < 0.64:
        penalties["MS 1"] = min(penalties.get("MS 1", 1.0), 0.80)
    elif p_home < 0.70:
        penalties["MS 1"] = min(penalties.get("MS 1", 1.0), 0.88)

    if p_away < 0.64:
        penalties["MS 2"] = min(penalties.get("MS 2", 1.0), 0.78)
    elif p_away < 0.70:
        penalties["MS 2"] = min(penalties.get("MS 2", 1.0), 0.86)

    p_u25 = float(bundle.ft_ou.get("2.5 Alt", 1.0 - p_o25))
    if p_o25 < 0.62:
        penalties["2.5 Üst"] = min(penalties.get("2.5 Üst", 1.0), 0.86)
    if p_u25 < 0.62:
        penalties["2.5 Alt"] = min(penalties.get("2.5 Alt", 1.0), 0.86)

    # 13. FIRST-HALF UNDER 1.5 (İY 1.5 ALT) HIGH-TEMPO LEAKAGE GUARD
    # (Nov 22 forensic audit: n=56 predicted %63.8 vs realized %55.4 = -8.4p overconfidence; 41 high-xG matches
    # leaked from blocked 3.5 Alt into İY 1.5 Alt and collapsed at %42.9-%58.5.)
    if tot >= 2.40 or bundle.exp_1h_total >= 1.05 or max_mu >= 1.50:
        blocked.setdefault(
            "İY 1.5 Alt",
            f"Yüksek Tempo İY 1.5 Alt Tuzağı (xG={tot:.2f}, 1Y xG={bundle.exp_1h_total:.2f}, max xG={max_mu:.2f}): "
            "3.5 Alt bloke olan maçlarda İY 1.5 Alt'a kaçılmamalı (Nov 22: -8.4 puan aşırı özgüven).",
        )

    # 14. UNVERIFIED MODEL-BTTS OVERCONFIDENCE GUARD
    # (Nov 22 forensic audit: direct=False Model KG Var >=67% went 4/10=%40.0 vs direct exchange %65.4;
    # balanced gap<0.50 Model KG Var went 25/48=%52.1.)
    if not ctx.btts_is_direct:
        if p_btts_model >= 0.67:
            penalties["KG Var"] = min(penalties.get("KG Var", 1.0), 0.82)
        elif p_btts_model >= 0.65 or gap < 0.50:
            penalties["KG Var"] = min(penalties.get("KG Var", 1.0), 0.88)

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
    min_prob: float = 0.57,
    specialty_mode: str | None = None,
    allow_uncalibrated: bool = False,
    mbs: int = 1,
    combo_min_prob: float = 0.46,
    require_prediction: bool = True,
    direct_selections: frozenset[str] | set[str] | None = None,
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
    allow_uncalibrated : bool
        By default competitions outside the calibration domain (see `is_uncalibrated_competition`,
        e.g. women's football) return no recommendations, because model probabilities there are unreliable.
    """
    if not allow_uncalibrated and is_uncalibrated_competition(league):
        return []
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

    high_eff_combos = frozenset({
        "2.5 Üst & KG Var", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst", "2.5 Alt & KG Yok", "2-3 Gol", "3-5 Gol",
    })

    for sel in candidate_keys:
        if sel not in all_probs:
            continue
        if sel in blocked:
            continue

        prob = float(all_probs[sel])
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

        if specialty_mode in ("ht_ft", "both_halves_btts", "6_plus_goals"):
            eff_min_prob = 0.18
        elif sel in high_eff_combos and off_odds >= 1.55 and not is_est:
            # Allow short-parlay high-efficiency live combos (>=1.55) down to combo_min_prob
            eff_min_prob = min(min_prob, float(combo_min_prob))
        else:
            eff_min_prob = min_prob
        if prob < eff_min_prob:
            continue

        # Also avoid ultra-heavy juice where estimated odds barely clear 1.20 unless live odds confirm >= 1.20
        fair = round(1.0 / max(prob, 1e-6), 2)
        ev = round(prob * off_odds - 1.0, 4)
        pen = penalties.get(sel, 1.0)
        if direct_selections is not None:
            is_direct = sel in direct_selections
            p_sigma = 0.010 if is_direct else (0.032 if ("İY" in sel or "2Y" in sel) else 0.025)
            eff_prob = max(0.001, prob - 1.28 * p_sigma)
        else:
            p_sigma = 0.0
            eff_prob = prob

        # Safety utility: prioritizes high reliable hit probability while rewarding healthy odds (>=1.22) and low margin loss
        ev_factor = max(0.65, min(1.18, 1.0 + 0.45 * ev))
        safety_score = round((eff_prob ** 1.35) * pen * ev_factor * (1.0 + 0.08 * math.log(max(off_odds, 1.20))), 4)

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
                mbs=max(1, int(mbs)),
                prob_sigma=p_sigma,
            )
        )

    recommendations.sort(key=lambda r: (r.safety_score, r.probability), reverse=True)
    if recommendations or not require_prediction:
        return recommendations

    # Universal Zero-PAS Step-Down Fallback:
    # When all primary candidates are filtered out by min_prob or risk blocks, step down to the highest-reliability
    # >= 1.20 option (preferring unblocked structural buffers first, then least-penalized high-probability buffers)
    # so every researched match receives an explicit prediction.
    fallback_keys = [
        "3.5 Alt", "4.5 Alt", "1.5 Üst", "İY 0.5 Üst", "İY 1.5 Alt", "2Y 0.5 Üst",
        "KG Yok", "KG Var", "ÇŞ 10", "ÇŞ 02", "2.5 Alt", "2.5 Üst", "2-4 Gol", "2-3 Gol", "MS 1", "MS 2",
    ]
    for allow_blk in (False, True):
        for sel in fallback_keys:
            if sel not in all_probs:
                continue
            is_blk = sel in blocked
            if is_blk and not allow_blk:
                continue
            prob = float(all_probs[sel])
            if prob < 0.48:
                continue
            cat = _categorize_selection(sel)
            if sel in odds_map and odds_map[sel] is not None:
                off_odds = float(odds_map[sel])
                is_est = False
            else:
                off_odds = _estimate_offered_odds(prob, cat)
                is_est = True
            if off_odds < floor - 1e-9:
                continue
            fair = round(1.0 / max(prob, 1e-6), 2)
            ev = round(prob * off_odds - 1.0, 4)
            pen = penalties.get(sel, 1.0) * (0.72 if is_blk else 1.0)
            ev_factor = max(0.65, min(1.18, 1.0 + 0.45 * ev))
            safety_score = round((prob ** 1.35) * pen * ev_factor * (1.0 + 0.08 * math.log(max(off_odds, 1.20))), 4)
            rationale = (
                f"Zorunlu Güvenli Kademe (0 PAS Modu) — Model Olasılığı %{prob*100:.1f} "
                f"(Adil {fair:.2f}, Oran {off_odds:.2f}) | xG: {bundle.mu_home:.2f}-{bundle.mu_away:.2f}"
            )
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
                    stepped_down_from="Zorunlu Güvenli Kademe (0 PAS Modu)",
                    blocked_traps=trap_list[:3],
                    group_id=ctx.group_id,
                    mbs=max(1, int(mbs)),
                )
            )
        if recommendations:
            break

    recommendations.sort(key=lambda r: (r.safety_score, r.probability), reverse=True)
    return recommendations


def _category_share_ok(legs: tuple[MarketRecommendation, ...], max_share: float | None) -> bool:
    if max_share is None or len(legs) < 3:
        return True
    counts: dict[str, int] = {}
    sel_counts: dict[str, int] = {}
    for leg in legs:
        counts[leg.category] = counts.get(leg.category, 0) + 1
        sel_counts[leg.selection] = sel_counts.get(leg.selection, 0) + 1
    if (max(counts.values()) / len(legs)) > float(max_share) + 1e-9:
        return False
    # Never let a single exact selection (e.g. İY 1.5 Alt) dominate > 50% on 4-leg or > 45% on 5+ leg coupons
    if len(legs) >= 4:
        sel_cap = min(float(max_share), 0.45 if len(legs) >= 5 else 0.50)
        if (max(sel_counts.values()) / len(legs)) > sel_cap + 1e-9:
            return False
    return True


def _conflicting_selections(selection: str) -> frozenset[str]:
    """Return selections on the same fixture that directly contradict or hedge against `selection`."""
    conflicts: dict[str, set[str]] = {
        "MS 1": {"MS 0", "MS 2", "ÇŞ 02", "MS 2 & 1.5 Üst", "MS 2 & 2.5 Üst", "MS 2 & KG Yok"},
        "MS 0": {"MS 1", "MS 2", "ÇŞ 12"},
        "MS 2": {"MS 0", "MS 1", "ÇŞ 10", "MS 1 & 1.5 Üst", "MS 1 & 2.5 Üst", "MS 1 & KG Yok"},
        "ÇŞ 10": {"MS 2", "ÇŞ 02", "MS 2 & 1.5 Üst", "MS 2 & 2.5 Üst"},
        "ÇŞ 02": {"MS 1", "ÇŞ 10", "MS 1 & 1.5 Üst", "MS 1 & 2.5 Üst"},
        "ÇŞ 12": {"MS 0"},
        "KG Var": {"KG Yok", "2.5 Alt & KG Yok", "MS 1 & KG Yok", "MS 2 & KG Yok", "1.5 Alt", "0-1 Gol"},
        "KG Yok": {"KG Var", "2.5 Üst & KG Var", "1. Yarı KG Var", "2. Yarı KG Var", "1Y ve 2Y KG Var"},
        "1.5 Üst": {"1.5 Alt", "0-1 Gol"},
        "1.5 Alt": {"1.5 Üst", "2.5 Üst", "3.5 Üst", "KG Var", "2.5 Üst & KG Var"},
        "2.5 Üst": {"2.5 Alt", "1.5 Alt", "3.5 Alt", "0-1 Gol", "2.5 Alt & KG Yok"},
        "2.5 Alt": {"2.5 Üst", "3.5 Üst", "4.5 Üst", "2.5 Üst & KG Var"},
        "3.5 Üst": {"3.5 Alt", "2.5 Alt", "1.5 Alt", "0-1 Gol", "2.5 Alt & KG Yok"},
        "3.5 Alt": {"3.5 Üst", "4.5 Üst", "5.5 Üst", "+6 Gol"},
        "2.5 Üst & KG Var": {"2.5 Alt", "KG Yok", "2.5 Alt & KG Yok", "1.5 Alt", "3.5 Alt"},
        "2.5 Alt & KG Yok": {"2.5 Üst", "3.5 Üst", "KG Var", "2.5 Üst & KG Var"},
    }
    return frozenset(conflicts.get(selection, ()))


def build_target_odds_coupon(
    candidates_by_match: Sequence[Sequence[MarketRecommendation] | MarketRecommendation],
    target_odds: float = 10.0,
    min_leg_odds: float = MIN_ALLOWED_ODDS,
    max_legs: int = 8,
    title: str | None = None,
    min_leg_ev: float | None = 0.0,
    forbidden_pairs: set[tuple[str, str]] | None = None,
    forbidden_matches: set[str] | None = None,
    allowed_categories: tuple[str, ...] | None = None,
    max_same_category_share: float | None = None,
    min_leg_prob: float | None = None,
) -> CouponPlan:
    """Build the highest-probability coupon whose combined odds reach `>= target_odds`.

    Only legs with model `ev >= min_leg_ev` are eligible (default: positive expected value).
    A parlay of independent legs is Kelly-optimal only when every leg is +EV on its own
    (Long 2026, arXiv:2603.26620); combining -EV legs compounds the bookmaker margin.
    Legs priced with estimated odds carry a built-in margin and are therefore excluded by
    default. Pass `min_leg_ev=None` to disable the filter.

    Uses beam search over match candidates (at most 1 pick per match and 1 pick per group_id
    when provided) to maximize `prod(leg.probability)` and `prod(leg.safety_score)` subject
    to `prod(leg.offered_odds) >= target_odds`, `leg.offered_odds >= min_leg_odds`, and MBS rules.
    """
    floor = max(MIN_ALLOWED_ODDS, float(min_leg_odds))
    forb_pairs = forbidden_pairs or set()
    forb_matches = forbidden_matches or set()
    allowed_cats = set(allowed_categories) if allowed_categories else None

    normalized_pool: list[list[MarketRecommendation]] = []
    all_traps: list[str] = []

    for item in candidates_by_match:
        opts = [item] if isinstance(item, MarketRecommendation) else list(item)
        valid_opts = [
            o for o in opts
            if o.offered_odds >= floor - 1e-9
            and (min_leg_ev is None or o.ev >= min_leg_ev - 1e-12)
            and (min_leg_prob is None or o.probability >= min_leg_prob - 1e-12)
            and o.match_id not in forb_matches
            and (o.match_id, o.selection) not in forb_pairs
            and (allowed_cats is None or o.category in allowed_cats)
        ]
        if valid_opts:
            valid_opts.sort(key=lambda r: (r.safety_score, r.probability), reverse=True)
            best_safe = valid_opts[0]
            chosen_opts = [best_safe]
            # Preserve up to 2 distinct alternative-category options so category/selection diversity stays feasible
            if max_same_category_share is not None:
                seen_cats = {best_safe.category}
                for r in valid_opts[1:]:
                    if r.category not in seen_cats:
                        chosen_opts.append(r)
                        seen_cats.add(r.category)
                        if len(seen_cats) >= 3:
                            break
            # Keep up to 3 Pareto options per match: safest, balanced mid-odds, and high-efficiency combo/odds
            higher_odds = [
                r for r in valid_opts[1:]
                if r not in chosen_opts and r.offered_odds >= best_safe.offered_odds + 0.06
            ]
            if higher_odds:
                higher_odds.sort(key=lambda r: (r.offered_odds * (r.probability ** 1.15), r.safety_score), reverse=True)
                chosen_opts.append(higher_odds[0])
                sharp_high = [
                    r for r in higher_odds[1:]
                    if r.offered_odds >= max(1.55, higher_odds[0].offered_odds + 0.12)
                ]
                if sharp_high:
                    sharp_high.sort(key=lambda r: (r.probability * r.offered_odds, r.probability), reverse=True)
                    chosen_opts.append(sharp_high[0])
            normalized_pool.append(chosen_opts)
            for t in valid_opts[0].blocked_traps:
                if t not in all_traps:
                    all_traps.append(t)

    # Sort matches by best probability-efficiency so high-target parlays see sharp high-odds legs too
    normalized_pool.sort(key=lambda opts: max(o.safety_score for o in opts), reverse=True)
    pool = normalized_pool[:28]

    # Beam state: (log_safety, log_prob, log_odds, legs_tuple, used_groups_frozenset)
    beam: list[tuple[float, float, float, tuple[MarketRecommendation, ...], frozenset[str]]] = [
        (0.0, 0.0, 0.0, (), frozenset())
    ]
    target_log_odds = math.log(max(1.20, float(target_odds)))
    best_completed: tuple[float, float, float, tuple[MarketRecommendation, ...]] | None = None
    saf_weight = 0.18 if target_odds >= 10.0 else 0.40

    for match_opts in pool:
        new_states = list(beam)
        for log_saf, log_p, log_o, legs, used_groups in beam:
            if len(legs) >= max_legs:
                continue
            for opt in match_opts:
                if opt.group_id and opt.group_id in used_groups:
                    continue
                nl_saf = log_saf + math.log(max(opt.safety_score, 1e-6))
                nl_p = log_p + math.log(max(opt.reliable_probability, 1e-6))
                nl_o = log_o + math.log(max(opt.offered_odds, 1.01))
                n_legs = legs + (opt,)
                n_groups = used_groups | ({opt.group_id} if opt.group_id else frozenset())

                mbs_ok = len(n_legs) >= max(l.mbs for l in n_legs)
                cat_ok = _category_share_ok(n_legs, max_same_category_share)

                if nl_o >= target_log_odds - 1e-9 and mbs_ok and cat_ok:
                    # Rank completed coupons primarily by exact joint hit probability (prevents long-parlay vig bloat)
                    cand_score = nl_p + saf_weight * nl_saf
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
            by_prob = sorted(bucket, key=lambda s: s[1] + 0.30 * s[0] + 0.30 * s[2], reverse=True)[:50]
            by_bal = sorted(bucket, key=lambda s: s[2] + 0.90 * s[1] + 0.25 * s[0], reverse=True)[:50]
            by_odds = sorted(bucket, key=lambda s: s[2] + 0.35 * s[1], reverse=True)[:50]
            seen_ids: set[int] = set()
            for st in by_prob + by_bal + by_odds:
                sid = id(st[3])
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    beam.append(st)

    if best_completed is not None:
        _, _, final_log_o, chosen_legs = best_completed
    elif beam:
        # Prefer MBS-valid partial states first
        valid_partials = [s for s in beam if s[3] and len(s[3]) >= max(l.mbs for l in s[3])]
        pick_from = valid_partials if valid_partials else beam
        best_partial = max(pick_from, key=lambda s: (s[2], s[1]))
        final_log_o, chosen_legs = best_partial[2], best_partial[3]
    else:
        chosen_legs = ()
        final_log_o = 0.0

    achieved = round(math.exp(final_log_o), 2) if chosen_legs else 0.0
    exact_joint_p = math.prod(l.probability for l in chosen_legs) if chosen_legs else 0.0
    joint_p = round(exact_joint_p, 4) if chosen_legs else 0.0
    avg_p = round(sum(l.probability for l in chosen_legs) / len(chosen_legs), 4) if chosen_legs else 0.0

    return CouponPlan(
        title=title or f"QuantFoot-v7 Hedef {target_odds:.0f}x Kupon",
        target_odds=target_odds,
        achieved_odds=achieved,
        joint_probability=joint_p,
        average_leg_probability=avg_p,
        legs=chosen_legs,
        eliminated_traps=tuple(all_traps[:8]),
        reached_target=best_completed is not None,
        expected_value=round(exact_joint_p * math.exp(final_log_o) - 1.0, 4) if chosen_legs else 0.0,
    )


def build_diversified_portfolio(
    candidates_by_match: Sequence[Sequence[MarketRecommendation] | MarketRecommendation],
    specs: Sequence[PortfolioCouponSpec],
    max_selection_reuse: int = 1,
    max_match_reuse: int = 2,
    max_same_category_share: float = 0.65,
    forbid_contradictions: bool = True,
) -> list[CouponPlan]:
    """Build a multi-coupon portfolio with strict exposure caps and anti-contradiction enforcement.

    By default (`max_selection_reuse=1`), no `(match_id, selection)` pair can repeat across
    coupons, no single match can appear in more than `max_match_reuse` coupons, and no later
    coupon can bet the opposite/contradictory side on an already-selected match (fixing Nov 19-20
    portfolio contradictions such as ÇŞ 10 vs ÇŞ 02 or KG Var vs KG Yok across coupons).
    """
    selection_counts: dict[tuple[str, str], int] = {}
    match_counts: dict[str, int] = {}
    contradicted_pairs: set[tuple[str, str]] = set()
    plans: list[CouponPlan] = []

    for spec in specs:
        forb_pairs = {pair for pair, cnt in selection_counts.items() if cnt >= max_selection_reuse}
        if forbid_contradictions:
            forb_pairs |= contradicted_pairs
        forb_matches = {mid for mid, cnt in match_counts.items() if cnt >= max_match_reuse}
        eff_cat_share = None if spec.allowed_categories else max_same_category_share

        plan = build_target_odds_coupon(
            candidates_by_match,
            target_odds=spec.target_odds,
            min_leg_odds=spec.min_leg_odds,
            max_legs=spec.max_legs,
            title=spec.title,
            min_leg_ev=spec.min_leg_ev,
            forbidden_pairs=forb_pairs,
            forbidden_matches=forb_matches,
            allowed_categories=spec.allowed_categories,
            max_same_category_share=eff_cat_share,
            min_leg_prob=spec.min_leg_prob,
        )
        plans.append(plan)
        for leg in plan.legs:
            pair = (leg.match_id, leg.selection)
            selection_counts[pair] = selection_counts.get(pair, 0) + 1
            match_counts[leg.match_id] = match_counts.get(leg.match_id, 0) + 1
            if forbid_contradictions:
                for opp in _conflicting_selections(leg.selection):
                    contradicted_pairs.add((leg.match_id, opp))

    return plans
