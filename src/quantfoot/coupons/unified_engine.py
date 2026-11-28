"""QuantFoot Unified Decision & Coupon Engine v2 (OOS-Validated + Closed-Loop Self-Learning).

Replaces fragmented, contradicting rule layers with one transparent, empirically verified
decision engine calibrated against BOTH:
- 2026 Out-of-Sample historical archive (`1,334` matches, `2026-03-08 -> 2026-11-16`), and
- Live settled Nesine slates (`614` matches via `oz_gelistirme_raporu.json`).

Core principles
---------------
1. **Double-Verified Gold Core Whitelist (Banko / Core):** Only markets proven positive or well
   calibrated on BOTH 2026 OOS archive AND live Nesine slates — removing 2-day overfit traps
   such as blind `MS 2` (`-6.61p` OOS), blind `İY 0.5 Üst` (`-2.85p` OOS), and toxic `Dep 1.5 Üst`
   (`%48.0`, `-36.1% ROI`).
2. **Sharp-Only Core + Symmetric Steam Shock Shield:**
   - Banko and Core coupons accept only sharp exchange/Pinnacle references (`SHARP_SOURCES`),
     zero women's/youth leagues, and a hard Nesine margin floor (`EV >= -0.145`).
   - Sharp steam shock `max(|steam|) >= 6.0p` (ANY direction) blocks BOTH `MS 1/2` (`%42.1`
     realized under `>=6p` steam) AND ALL `Alt`/`KG Yok` markets (`%56.7` realized).
3. **Closed-Loop Empirical-Bayes Self-Learning (`SelfLearningAdjustments`):**
   Reads strictly from the active AI's own `oz_gelistirme_raporu.json` to auto-block persistent
   toxic alarms (`n >= 25`, `shrunk_residual <= -0.020`) and apply conservative asymmetric
   probability shrinkage (`[-4.0p, +1.5p]`) without overfitting.
4. **Directional Transfermarkt Injury Engine:**
   - Missing top scorer blocks `KG Var`, `2Y KG Var`, `İki Yarıda KG Var`, and that team's goal/win
     bets, while boosting opponent clean-sheet / `İY Skor 0-0` / team-Under picks.
   - Missing #1 goalkeeper blocks all Unders / `KG Yok` / `İY Skor 0-0` and that team's win,
     while boosting the *opponent's* goal markets rather than fragile `MS 1/2`.
5. **Short Banko + Automatic Single-Leg Insurance + 5 Specialty Builders:**
   Includes integrated specialty builders for `İY Skor` (MTID 779), `Maç Skoru` (MTID 777),
   `İY/MS` (`1/2, 2/1, 0/1, 0/2, 1/0, 2/0`), `İki Yarıda KG Var` (MTID 801), and `2Y KG Var`
   (MTID 599) with full cross-coupon anti-contradiction checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from quantfoot.coupons.system_builder import SystemEvaluation, SystemLeg, evaluate_system
from quantfoot.strategy.coupon_builder import (
    _conflicting_selections,
    is_cup_competition,
    is_uncalibrated_competition,
)

SHARP_SOURCES: tuple[str, ...] = (
    "Pinnacle",
    "Smarkets",
    "Matchbook",
    "Betfair",
    "OddsMath (BetInAsia",
    "OddsMath (Borsa",
)

YOUTH_TOKENS: tuple[str, ...] = (
    "u17", "u18", "u19", "u20", "u21", "u23",
    "gençler", "gencler", "primavera", "gelişim", "gelisim", "academy",
)

# Empirically toxic markets across 2026 OOS archive + 614 settled live Nesine matches
BANNED_CORE_SELECTIONS: frozenset[str] = frozenset({
    "İY ÇŞ 12",
    "DEĞİL(Ev İki Yarıda Gol)",
    "Ev 2.5 Alt",
    "Dep 1.5 Üst",  # 12/25 (%48.0), -36.1% ROI live toxic alarm
    "MS 0",
    "İY 0",
    "ÇŞ 12",
    "Tek",
    "Çift",
    "İY Tek",
    "İY Çift",
})

BANNED_CORE_PREFIXES: tuple[str, ...] = (
    "Skor ",
    "İY Skor ",
    "İY/MS ",
    "İlk Gol",
    "Korner",
    "Kart",
    "Hnd(",
    "2Y 1",
    "2Y 0",
    "2Y 2",
    "İY 1",
    "İY 2",
    "DEĞİL(",
)

# Double-verified Gold Core markets (confirmed on BOTH 2026 OOS 1,334-match archive AND 614 live Nesine matches).
# Blind MS 2 (-6.61p OOS) and blind İY 0.5 Üst (-2.85p OOS) intentionally excluded from Banko Gold Core.
GOLD_CORE_SELECTIONS: frozenset[str] = frozenset({
    "Ev İY 0.5 Alt",
    "MS 1",
    "İY KG Yok & 2Y KG Yok",
    "1.5 Üst",
    "3.5 Alt",
    "Ev 1.5 Üst",
    "KG Yok",
    "Dep İY 0.5 Alt",
    "2Y KG Yok",
    "ÇŞ 1X",
    "Ev 1.5 Alt",
    "Ev En Az Bir Yarıyı Kazanır",
})

# Additional clean selections allowed ONLY in 20+ odds / extended value coupons (with strict xG, steam & injury guards)
EXTENDED_20X_SELECTIONS: frozenset[str] = GOLD_CORE_SELECTIONS | frozenset({
    "ÇŞ X2",
    "İY 0.5 Üst",
    "MS 2",
    "2.5 Üst",
    "3.5 Üst",
    "Dep 0.5 Üst",
    "Ev 0.5 Üst",
    "Dep 1.5 Alt",
    "Ev 0.5 Alt",
    "KG Var",
    "2.5 Üst & KG Var",
    "MS 1 & 1.5 Üst",
    "MS 2 & 1.5 Üst",
    "2-3 Gol",
})

ALLOWED_HTFT_REVERSALS: frozenset[str] = frozenset({
    "İY/MS 1/2",
    "İY/MS 2/1",
    "İY/MS 0/1",
    "İY/MS 0/2",
    "İY/MS 1/0",
    "İY/MS 2/0",
})

_UNDER_AND_NO_BTTS_MARKETS: frozenset[str] = frozenset({
    "3.5 Alt",
    "2.5 Alt",
    "1.5 Alt",
    "İY 1.5 Alt",
    "İY 0.5 Alt",
    "Ev 1.5 Alt",
    "Dep 1.5 Alt",
    "Ev İY 0.5 Alt",
    "Dep İY 0.5 Alt",
    "Ev 0.5 Alt",
    "Dep 0.5 Alt",
    "2Y KG Yok",
    "İY KG Yok & 2Y KG Yok",
    "KG Yok",
})

_STEAM_RE = re.compile(r"(Ev|Ber|Dep)\s*([+-]?\d+(?:\.\d+)?)p", re.I)
_SCORE_RE = re.compile(r"^(?:İY )?Skor (\d+)-(\d+)$")
_HTFT_RE = re.compile(r"^İY/MS ([012])/([012])$")


@dataclass(frozen=True)
class SelfLearningAdjustments:
    """Closed-loop Empirical-Bayes calibration loaded strictly from the active AI's report."""

    blocked_selections: frozenset[str] = frozenset()
    prob_deltas: dict[str, float] = field(default_factory=dict)
    source_path: str = ""
    settled_matches: int = 0
    generated_at: str = ""


def load_self_learning_adjustments(
    ai_dir_or_report: Path | str | None,
    *,
    min_block_n: int = 25,
    block_shrunk_threshold: float = -0.020,
    min_delta_n: int = 20,
    delta_scale: float = 0.5,
    max_penalty: float = -0.040,
    max_bonus: float = 0.015,
) -> SelfLearningAdjustments:
    """Load Empirical-Bayes toxic blocks and probability deltas from ``oz_gelistirme_raporu.json``.

    Accepts either the active AI directory (e.g. ``tahminler/antigravitytahmin``) or a direct
    path to ``oz_gelistirme_raporu.json``. Returns an empty object safely if the file does not
    exist or cannot be parsed.
    """
    if not ai_dir_or_report:
        return SelfLearningAdjustments()
    p = Path(ai_dir_or_report)
    report_path = p if p.is_file() else p / "oz_gelistirme_raporu.json"
    if not report_path.exists():
        return SelfLearningAdjustments()
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SelfLearningAdjustments()
    if not isinstance(data, dict):
        return SelfLearningAdjustments()

    blocked: set[str] = set()
    for item in data.get("toxic_alarms") or []:
        if not isinstance(item, dict):
            continue
        sel = str(item.get("selection") or "").strip()
        n = int(item.get("n") or 0)
        shrunk = float(item.get("shrunk_residual") or 0.0)
        if sel and n >= min_block_n and shrunk <= block_shrunk_threshold:
            blocked.add(sel)

    deltas: dict[str, float] = {}
    for sel, stats in (data.get("by_selection") or {}).items():
        if not isinstance(stats, dict):
            continue
        n = int(stats.get("n") or 0)
        if n < min_delta_n:
            continue
        shrunk = float(stats.get("shrunk_residual") or 0.0)
        adj = max(max_penalty, min(max_bonus, delta_scale * shrunk))
        if abs(adj) >= 0.001:
            deltas[str(sel).strip()] = round(adj, 4)

    return SelfLearningAdjustments(
        blocked_selections=frozenset(blocked),
        prob_deltas=deltas,
        source_path=str(report_path),
        settled_matches=int(data.get("settled_matches") or 0),
        generated_at=str(data.get("generated_at") or ""),
    )


@dataclass(frozen=True)
class InjuryProfile:
    """Unified directional squad-absence flags extracted from TM, user files, FPL, and ESPN."""

    home_gk1_out: bool = False
    away_gk1_out: bool = False
    home_top_scorer_out: bool = False
    away_top_scorer_out: bool = False
    home_def_crisis: bool = False
    away_def_crisis: bool = False
    home_att_crisis: bool = False
    away_att_crisis: bool = False


@dataclass(frozen=True)
class UnifiedLeg:
    """Single validated coupon candidate leg produced by the unified decision engine."""

    code: int
    kickoff: str
    kickoff_iso: str
    league: str
    match: str
    market: str
    selection: str
    name: str
    key: str
    odds: float
    prob: float
    prob_effective: float
    ev: float
    mbs: int
    direct: bool
    is_sharp: bool
    reference: str
    mu_home: float
    mu_away: float
    tier: str
    injury_boost: float = 0.0
    reasons: tuple[str, ...] = ()

    def to_system_leg(self) -> SystemLeg:
        return SystemLeg(
            match_id=str(self.code),
            match=self.match,
            name=self.name,
            odds=self.odds,
            p=self.prob,
            mbs=self.mbs,
            kickoff=self.kickoff,
            league=self.league,
        )


@dataclass(frozen=True)
class UnifiedCoupon:
    """Optimized coupon with honest joint probability and optional single-leg insurance breakdown."""

    coupon_id: str
    title: str
    mode: str
    legs: tuple[UnifiedLeg, ...]
    total_odds: float
    joint_prob: float
    expected_value: float
    max_mbs: int
    insurance: SystemEvaluation | None = None
    note: str = ""


def is_youth_competition(league: str | None) -> bool:
    """Return True for U17/U19/U20/U21/U23 youth competitions (higher score variance)."""
    if not league:
        return False
    low = league.replace("İ", "i").replace("I", "i").lower()
    return any(tok in low for tok in YOUTH_TOKENS)


def extract_injury_profile(match: dict[str, Any]) -> InjuryProfile:
    """Extract directional GK1 / top-scorer / defensive / attacking crisis flags from match research."""
    res = match.get("research") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    fpl = res.get("absences") or {}
    teams = res.get("teams") or {}

    def _side(side: str) -> tuple[bool, bool, bool, bool]:
        tm_s = tm.get(side) or {}
        ua_s = ua.get(side) or {}
        fpl_s = fpl.get(side) or {}
        espn_s = teams.get(side) or {}
        gk1 = bool(tm_s.get("gk1_out") or ua_s.get("gk_out"))
        sc1 = bool(tm_s.get("top_scorer_out"))
        def_c = int(tm_s.get("def_core_out") or 0) >= 2
        att_c = int(tm_s.get("att_core_out") or 0) >= 2
        for p in fpl_s.get("players") or []:
            if p.get("key") and p.get("chance") == 0:
                pos = str(p.get("position") or p.get("pos") or "").lower()
                if any(k in pos for k in ("gk", "goalkeeper", "kaleci")):
                    gk1 = True
                elif any(k in pos for k in ("fwd", "forward", "forvet")):
                    sc1 = True
        for item in espn_s.get("likely_absent") or []:
            rsn = str(item.get("reason") or "").lower()
            if "kaleci" in rsn or "goalkeeper" in rsn:
                gk1 = True
        return gk1, sc1, def_c, att_c

    h_gk, h_sc, h_def, h_att = _side("home")
    a_gk, a_sc, a_def, a_att = _side("away")
    return InjuryProfile(
        home_gk1_out=h_gk,
        away_gk1_out=a_gk,
        home_top_scorer_out=h_sc,
        away_top_scorer_out=a_sc,
        home_def_crisis=h_def,
        away_def_crisis=a_def,
        home_att_crisis=h_att,
        away_att_crisis=a_att,
    )


def parse_steam_deltas(match: dict[str, Any]) -> tuple[float, float, float]:
    """Return ``(home_pp, draw_pp, away_pp)`` sharp opening-to-live probability steam in percentage points."""
    st = match.get("steam_1x2")
    if isinstance(st, (list, tuple)) and len(st) == 3:
        return (float(st[0]) * 100.0, float(st[1]) * 100.0, float(st[2]) * 100.0)
    h, d, a = 0.0, 0.0, 0.0
    for fl in (match.get("research") or {}).get("flags") or []:
        for lbl, val in _STEAM_RE.findall(str(fl)):
            fval = float(val)
            key = lbl.lower()
            if key == "ev":
                h = fval
            elif key == "ber":
                d = fval
            elif key == "dep":
                a = fval
    return (h, d, a)


def selections_conflict(name_a: str, name_b: str) -> bool:
    """Return True if two selections on the same match are logically incompatible or duplicates."""
    a = name_a.strip()
    b = name_b.strip()
    if a == b:
        return True
    if b in _conflicting_selections(a) or a in _conflicting_selections(b):
        return True

    def _pair_check(x: str, y: str) -> bool:
        # Both-halves or 2nd-half BTTS vs No-BTTS / zero-goal bets
        if x in ("İki Yarıda KG Var", "2Y KG Var"):
            if y in ("KG Yok", "2Y KG Yok", "İY KG Yok & 2Y KG Yok", "Ev 0.5 Alt", "Dep 0.5 Alt"):
                return True
        if x == "İki Yarıda KG Var":
            if y in ("İY Skor 0-0", "İY 0.5 Alt", "Ev İY 0.5 Alt", "Dep İY 0.5 Alt"):
                return True
        # HT/FT outcome vs FT side or HT 0-0
        m_hf = _HTFT_RE.match(x)
        if m_hf:
            ht_r, ft_r = m_hf.group(1), m_hf.group(2)
            if ft_r == "1" and y in ("MS 2", "MS 0", "ÇŞ X2", "MS 2 & 1.5 Üst"):
                return True
            if ft_r == "2" and y in ("MS 1", "MS 0", "ÇŞ 1X", "MS 1 & 1.5 Üst"):
                return True
            if ft_r == "0" and y in ("MS 1", "MS 2", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst"):
                return True
            if ht_r in ("1", "2") and y == "İY Skor 0-0":
                return True
            if ht_r == "1" and y == "Ev İY 0.5 Alt":
                return True
            if ht_r == "2" and y == "Dep İY 0.5 Alt":
                return True
        # Exact HT or FT score conflicts
        m_sc = _SCORE_RE.match(x)
        if m_sc:
            gh, ga = int(m_sc.group(1)), int(m_sc.group(2))
            if x.startswith("İY Skor "):
                if gh == 0 and ga == 0 and y in ("İY 0.5 Üst", "İki Yarıda KG Var"):
                    return True
                if gh > 0 and y == "Ev İY 0.5 Alt":
                    return True
                if ga > 0 and y == "Dep İY 0.5 Alt":
                    return True
                if gh > 0 and ga > 0 and y == "İY KG Yok & 2Y KG Yok":
                    return True
            else:
                tot = gh + ga
                if (gh == 0 or ga == 0) and y in ("KG Var", "2.5 Üst & KG Var", "2Y KG Var", "İki Yarıda KG Var"):
                    return True
                if gh > 0 and ga > 0 and y == "KG Yok":
                    return True
                if gh <= ga and y in ("MS 1", "MS 1 & 1.5 Üst"):
                    return True
                if ga <= gh and y in ("MS 2", "MS 2 & 1.5 Üst"):
                    return True
                if gh < ga and y == "ÇŞ 1X":
                    return True
                if ga < gh and y == "ÇŞ X2":
                    return True
                if tot < 2 and y == "1.5 Üst":
                    return True
                if tot < 3 and y in ("2.5 Üst", "2.5 Üst & KG Var"):
                    return True
                if tot >= 4 and y == "3.5 Alt":
                    return True
                if gh >= 2 and y == "Ev 1.5 Alt":
                    return True
                if ga >= 2 and y == "Dep 1.5 Alt":
                    return True
                if gh < 2 and y == "Ev 1.5 Üst":
                    return True
        return False

    return _pair_check(a, b) or _pair_check(b, a)


def evaluate_directional_injury(name: str, inj: InjuryProfile) -> tuple[bool, float, str | None]:
    """Apply directional TM injury intelligence to a candidate selection (core & specialty).

    Returns ``(allowed, prob_boost, note)``:
    - ``allowed=False`` rejects selections directly contradicted by a missing GK1 or top scorer.
    - ``prob_boost`` (+0.015 to +0.018) rewards selections *aligned* with the missing player.
    """
    n = name.strip()
    is_any_under = n in _UNDER_AND_NO_BTTS_MARKETS or n == "İY Skor 0-0"
    is_both_score = n in ("KG Var", "2.5 Üst & KG Var", "2Y KG Var", "İki Yarıda KG Var")

    # Specialty score & HT/FT directional injury checks
    m_sc = _SCORE_RE.match(n)
    if m_sc:
        gh, ga = int(m_sc.group(1)), int(m_sc.group(2))
        is_ht = n.startswith("İY Skor ")
        if (inj.home_gk1_out or inj.home_def_crisis) and ga == 0:
            return False, 0.0, "Ev 1. kaleci/savunma krizi -> Ev gol yemez skoru yasak"
        if (inj.away_gk1_out or inj.away_def_crisis) and gh == 0:
            return False, 0.0, "Dep 1. kaleci/savunma krizi -> Dep gol yemez skoru yasak"
        if (inj.home_top_scorer_out or inj.home_att_crisis) and gh >= (1 if is_ht else 2):
            return False, 0.0, "Ev golcü/hücum eksiği -> Ev gollü skor yasak"
        if (inj.away_top_scorer_out or inj.away_att_crisis) and ga >= (1 if is_ht else 2):
            return False, 0.0, "Dep golcü/hücum eksiği -> Dep gollü skor yasak"
        if is_ht and gh == 0 and ga == 0 and (inj.home_top_scorer_out or inj.away_top_scorer_out):
            return True, 0.018, "TM: Golcü eksiği İY 0-0 destekliyor"
        return True, 0.0, None

    m_hf = _HTFT_RE.match(n)
    if m_hf:
        ft_r = m_hf.group(2)
        if ft_r == "1" and (inj.home_gk1_out or inj.home_def_crisis or inj.home_top_scorer_out or inj.home_att_crisis):
            return False, 0.0, "Ev kaleci/golcü eksiği -> */1 İY/MS yasak"
        if ft_r == "2" and (inj.away_gk1_out or inj.away_def_crisis or inj.away_top_scorer_out or inj.away_att_crisis):
            return False, 0.0, "Dep kaleci/golcü eksiği -> */2 İY/MS yasak"
        return True, 0.0, None

    # 1. Missing top scorer -> NEVER back that team to score or BTTS!
    if inj.home_top_scorer_out or inj.home_att_crisis:
        if is_both_score or n in ("MS 1", "MS 1 & 1.5 Üst", "Ev 0.5 Üst", "Ev 1.5 Üst", "Ev En Az Bir Yarıyı Kazanır"):
            return False, 0.0, "Ev golcü/hücum eksiği -> ev golü/KG Var yasak"
        if n in ("Ev 1.5 Alt", "Ev İY 0.5 Alt", "Ev 0.5 Alt", "İY Skor 0-0", "KG Yok", "3.5 Alt"):
            return True, 0.015, "TM: Ev golcü eksik (seçimi destekliyor)"

    if inj.away_top_scorer_out or inj.away_att_crisis:
        if is_both_score or n in ("MS 2", "MS 2 & 1.5 Üst", "Dep 0.5 Üst", "Dep 1.5 Üst"):
            return False, 0.0, "Dep golcü/hücum eksiği -> dep golü/KG Var yasak"
        if n in ("Dep 1.5 Alt", "Dep İY 0.5 Alt", "İY Skor 0-0", "KG Yok", "3.5 Alt"):
            return True, 0.015, "TM: Dep golcü eksik (seçimi destekliyor)"

    # 2. Missing #1 goalkeeper -> NEVER back Unders or that team's win; BOOST opponent goals instead!
    if inj.home_gk1_out or inj.home_def_crisis:
        if is_any_under or n in ("MS 1", "MS 1 & 1.5 Üst", "Dep 1.5 Alt", "Dep İY 0.5 Alt"):
            return False, 0.0, "Ev 1. kaleci/savunma krizi -> Alt / Ev galibiyeti yasak"
        if n in ("Dep 0.5 Üst", "İY 0.5 Üst", "2Y KG Var", "İki Yarıda KG Var"):
            return True, 0.015, "TM: Ev 1. kaleci/savunma eksik (gol yönü destekli)"

    if inj.away_gk1_out or inj.away_def_crisis:
        if is_any_under or n in ("MS 2", "MS 2 & 1.5 Üst", "Ev 1.5 Alt", "Ev İY 0.5 Alt", "Ev 0.5 Alt"):
            return False, 0.0, "Dep 1. kaleci/savunma krizi -> Alt / Dep galibiyeti yasak"
        # Deliberately do NOT boost MS 1 (O.H. Leuven 2-2 lesson) or 2.5 Üst (Bochum 2-0): boost HOME GOALS!
        if n in ("Ev 0.5 Üst", "Ev 1.5 Üst", "İY 0.5 Üst", "2Y KG Var", "İki Yarıda KG Var"):
            return True, 0.015, "TM: Dep 1. kaleci/savunma eksik (ev golü destekli)"

    return True, 0.0, None


def _selection_regime_ok(
    name: str,
    p: float,
    odds: float,
    mu_h: float,
    mu_a: float,
    p1: float | None,
    p_draw: float | None,
    p2: float | None,
    *,
    is_cup: bool,
    steam: tuple[float, float, float],
    mode: str,
) -> tuple[bool, str | None]:
    """Single clean regime check enforcing all OOS-validated xG, draw, cup, and symmetric steam laws."""
    tot = mu_h + mu_a
    max_mu = max(mu_h, mu_a)
    min_mu = min(mu_h, mu_a)
    h_st, _, a_st = steam
    max_st = max(abs(x) for x in steam)

    if name in BANNED_CORE_SELECTIONS or name.startswith(BANNED_CORE_PREFIXES):
        return False, "yasak/gürültülü pazar"

    allowed_set = GOLD_CORE_SELECTIONS if mode in ("banko", "dengeli") else EXTENDED_20X_SELECTIONS
    if name not in allowed_set:
        return False, f"{mode} beyaz listesi dışı"

    # Symmetric sharp steam shock shield (614 live matches: >=6p steam collapses MS 1/2 to %42.1 & Alt to %56.7!)
    if name in ("MS 1", "MS 2", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst") and max_st >= 6.0:
        return False, f"sert piyasa şoku ({max_st:.1f}p >= 6p) MS için yasak"
    if name in ("MS 1", "ÇŞ 1X", "MS 1 & 1.5 Üst") and h_st <= -5.5:
        return False, f"sert negatif steam Ev ({h_st:+.1f}p)"
    if name in ("MS 2", "ÇŞ X2", "MS 2 & 1.5 Üst") and a_st <= -5.5:
        return False, f"sert negatif steam Dep ({a_st:+.1f}p)"
    if name in _UNDER_AND_NO_BTTS_MARKETS and max_st >= 6.0:
        return False, f"sert piyasa şoku ({max_st:.1f}p >= 6p) Alt/KG Yok için yasak"

    # Knockout cup guards: never take fragile MS or tight Under in single-leg cups
    if is_cup:
        if name in ("MS 1", "MS 2", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst") and p < 0.72:
            return False, "kupa 90' beraberlik riski"
        if name in ("Ev 0.5 Alt", "2.5 Üst") and p < 0.65:
            return False, "kupa varyans riski"

    # Exact xG regime gates (double-verified on 2026 OOS 1,334-match archive + 614 live matches)
    if name == "1.5 Üst":
        if tot < 2.60 or p < (0.72 if mode in ("banko", "dengeli") else 0.70):
            return False, f"1.5 Üst için düşük tempo (xG={tot:.2f} < 2.60)"
    elif name == "2.5 Üst":
        if tot < 3.10 or p < 0.60:
            return False, f"2.5 Üst için düşük tempo (xG={tot:.2f} < 3.10)"
    elif name == "3.5 Üst":
        if tot < 3.65 or p < 0.56:
            return False, f"3.5 Üst için xG yetersiz ({tot:.2f})"
    elif name == "3.5 Alt":
        if tot > 2.40 or max_mu > 1.55 or p < 0.68:
            return False, f"3.5 Alt için yüksek tempo (xG={tot:.2f}, max={max_mu:.2f})"
    elif name == "İY 0.5 Üst":
        # 2026 OOS: blind İY 0.5 Üst was -2.85p overconfident -> only allow in 20x for ultra-high tempo!
        if tot < 2.95 or p < 0.70:
            return False, f"İY 0.5 Üst için aşırı tempo gerekli (xG={tot:.2f} < 2.95)"
    elif name == "İY KG Yok & 2Y KG Yok":
        if tot > 2.65 or p < 0.64:
            return False, f"İY&2Y KG Yok için yüksek tempo (xG={tot:.2f})"
    elif name == "2Y KG Yok":
        if tot > 2.85 or p < 0.66:
            return False, f"2Y KG Yok için yüksek tempo (xG={tot:.2f})"
    elif name == "Ev 1.5 Alt":
        if mu_h > 1.25 or p < 0.65:
            return False, f"Ev 1.5 Alt için yüksek Ev xG ({mu_h:.2f})"
    elif name == "Ev 1.5 Üst":
        if mu_h < 1.80 or p < (0.64 if mode == "banko" else 0.58):
            return False, f"Ev 1.5 Üst için düşük Ev xG ({mu_h:.2f})"
    elif name == "Ev İY 0.5 Alt":
        if mu_h > 1.10 or p < 0.66:
            return False, f"Ev İY 0.5 Alt için yüksek Ev xG ({mu_h:.2f})"
    elif name == "Dep İY 0.5 Alt":
        if mu_a > 1.05 or p < 0.66:
            return False, f"Dep İY 0.5 Alt için yüksek Dep xG ({mu_a:.2f})"
    elif name == "Dep 1.5 Alt":
        if mu_a > 1.20 or p < 0.65:
            return False, f"Dep 1.5 Alt için yüksek Dep xG ({mu_a:.2f})"
    elif name == "Ev 0.5 Alt":
        if mu_h > 0.65 or p < 0.57:
            return False, f"Ev 0.5 Alt için yüksek Ev xG ({mu_h:.2f})"
    elif name == "Dep 0.5 Üst":
        if mu_a < 1.15 or p < 0.64:
            return False, f"Dep 0.5 Üst için düşük Dep xG ({mu_a:.2f})"
    elif name == "Ev 0.5 Üst":
        if mu_h < 1.20 or p < 0.64:
            return False, f"Ev 0.5 Üst için düşük Ev xG ({mu_h:.2f})"
    elif name == "Ev En Az Bir Yarıyı Kazanır":
        if (mu_h - mu_a) < 0.60 or p < 0.65:
            return False, "Ev yarı galibiyeti için güç farkı yetersiz"
    elif name == "MS 1":
        if p < (0.65 if mode in ("banko", "dengeli") else 0.59) or (p_draw is not None and p_draw >= 0.27):
            return False, "MS 1 için olasılık düşük veya beraberlik riski yüksek"
    elif name == "MS 2":
        # 2026 OOS: MS 2 (P>=62%) collapsed -6.61p -> strictly heavy away favorites (P>=72%) only in 20x!
        if p < 0.72 or (p_draw is not None and p_draw >= 0.24):
            return False, "MS 2 için çok güçlü deplasman favorisi gerekli (P>=%72)"
    elif name == "MS 1 & 1.5 Üst":
        if p < 0.58 or (p_draw is not None and p_draw >= 0.25):
            return False, "MS 1 & 1.5 Üst için olasılık/beraberlik eşiği dışı"
    elif name == "MS 2 & 1.5 Üst":
        if p < 0.65 or (p_draw is not None and p_draw >= 0.24):
            return False, "MS 2 & 1.5 Üst için olasılık/beraberlik eşiği dışı"
    elif name == "ÇŞ 1X":
        if p < 0.66 or tot >= 3.30 or (p1 is not None and p2 is not None and p2 - p1 > 0.05):
            return False, "ÇŞ 1X için zayıf ev / yüksek tempo riski"
    elif name == "ÇŞ X2":
        if p < 0.63 or tot >= 3.30 or (p1 is not None and p2 is not None and p1 - p2 > 0.05):
            return False, "ÇŞ X2 için zayıf deplasman / yüksek tempo riski"
    elif name in ("KG Var", "2.5 Üst & KG Var"):
        if tot < 3.25 or min_mu < 1.25 or p < (0.60 if name == "KG Var" else 0.58):
            return False, f"KG Var için yetersiz çift taraflı xG ({mu_h:.2f}-{mu_a:.2f})"
    elif name == "KG Yok":
        if min_mu > 0.78 or tot > 3.10 or p < 0.63:
            return False, f"KG Yok için açık maç riski (xG={tot:.2f}, min={min_mu:.2f})"
    elif name == "2-3 Gol":
        if tot < 2.20 or tot > 2.90 or p < 0.56:
            return False, "2-3 Gol için xG bandı dışı"

    # Odds sanity bounds per mode
    if mode == "banko" and not (1.20 <= odds <= 1.75):
        return False, "banko oran aralığı dışı (1.20-1.75)"
    if mode == "dengeli" and not (1.22 <= odds <= 1.95):
        return False, "dengeli oran aralığı dışı (1.22-1.95)"
    if mode == "yuksek_20x" and not (1.25 <= odds <= 2.10):
        return False, "20x bacak oran aralığı dışı (1.25-2.10)"

    return True, None


def _match_is_eligible(
    m: dict[str, Any],
    *,
    now: dt.datetime | None,
    min_minutes_to_kickoff: int,
    max_hours_to_kickoff: float | None,
    sharp_only: bool,
    allow_youth: bool,
    exclude_codes: set[int],
) -> tuple[bool, bool, float | None]:
    """Check fixture-level eligibility and return ``(ok, is_sharp, hours_to_ko)``."""
    if m.get("status") != "fiyatlandı" or m.get("price_tier") == "ozel_bahis":
        return False, False, None
    code = int(m["code"])
    if code in exclude_codes or m.get("research_block"):
        return False, False, None
    league = str(m.get("league") or "")
    if is_uncalibrated_competition(league):
        return False, False, None
    if not allow_youth and is_youth_competition(league):
        return False, False, None

    ref = str(m.get("reference") or "")
    is_sharp = ref.startswith(SHARP_SOURCES)
    if sharp_only and not is_sharp:
        return False, is_sharp, None

    ko_iso = str(m.get("kickoff_iso") or "")
    hours_to_ko: float | None = None
    if now is not None and ko_iso:
        ko_dt = dt.datetime.fromisoformat(ko_iso)
        mins = (ko_dt - now).total_seconds() / 60.0
        if mins < min_minutes_to_kickoff:
            return False, is_sharp, None
        hours_to_ko = mins / 60.0
        if max_hours_to_kickoff is not None and hours_to_ko > max_hours_to_kickoff:
            return False, is_sharp, None

    mu_h = float(m.get("mu_home") or 0.0)
    mu_a = float(m.get("mu_away") or 0.0)
    if mu_h <= 0.0 or mu_a <= 0.0:
        return False, is_sharp, None
    return True, is_sharp, hours_to_ko


def _has_prior_conflict(code: int, key: str, name: str, prior_legs: Sequence[UnifiedLeg]) -> bool:
    for pl in prior_legs:
        if pl.code == code:
            if pl.key == key or selections_conflict(pl.name, name):
                return True
    return False


def extract_clean_candidates(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    mode: str = "banko",
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    sharp_only: bool = True,
    allow_youth: bool = False,
    min_ev: float | None = None,
    exclude_codes: set[int] | None = None,
    prior_legs: Sequence[UnifiedLeg] = (),
    self_learning: SelfLearningAdjustments | None = None,
) -> list[list[UnifiedLeg]]:
    """Build clean, non-dominated per-match candidate pools under the unified decision engine."""
    ev_floor = min_ev if min_ev is not None else (-0.145 if mode in ("banko", "dengeli") else -0.165)
    excl = exclude_codes or set()
    pools: list[list[UnifiedLeg]] = []

    for m in matches:
        ok_m, is_sharp, hours_to_ko = _match_is_eligible(
            m,
            now=now,
            min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff,
            sharp_only=sharp_only,
            allow_youth=allow_youth,
            exclude_codes=excl,
        )
        if not ok_m:
            continue

        code = int(m["code"])
        league = str(m.get("league") or "")
        ref = str(m.get("reference") or "")
        ko_iso = str(m.get("kickoff_iso") or "")
        mu_h = float(m.get("mu_home") or 0.0)
        mu_a = float(m.get("mu_away") or 0.0)
        f1x2 = m.get("fair_1x2") or []
        p1 = float(f1x2[0]) if len(f1x2) == 3 else None
        p_draw = float(f1x2[1]) if len(f1x2) == 3 else None
        p2 = float(f1x2[2]) if len(f1x2) == 3 else None

        inj = extract_injury_profile(m)
        steam = parse_steam_deltas(m)
        is_cup = is_cup_competition(league)

        match_legs: list[UnifiedLeg] = []
        for s in m.get("selections") or []:
            nm = str(s.get("name") or "").strip()
            s_key = str(s.get("key") or nm)
            odds = float(s.get("odds") or 0.0)
            p = float(s.get("fair_prob") or 0.0)
            if not nm or odds < 1.20 or p < 0.56:
                continue

            # Closed-loop self-learning auto-block for persistent toxic alarms
            if self_learning is not None and nm in self_learning.blocked_selections:
                continue

            ev = p * odds - 1.0
            if ev > 0.25 or ev < ev_floor:
                continue

            if _has_prior_conflict(code, s_key, nm, prior_legs):
                continue

            ok_reg, _ = _selection_regime_ok(
                nm, p, odds, mu_h, mu_a, p1, p_draw, p2,
                is_cup=is_cup, steam=steam, mode=mode,
            )
            if not ok_reg:
                continue

            ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
            if not ok_inj:
                continue

            # Clean transparent uncertainty penalty (direct vs model + lead-time + non-sharp)
            sigma = 0.010 if s.get("direct") else 0.020
            if not is_sharp:
                sigma += 0.025
            if hours_to_ko is not None:
                if hours_to_ko > 6.0:
                    sigma += 0.010
                elif hours_to_ko > 3.0:
                    sigma += 0.005
            gold_bonus = 0.010 if nm in GOLD_CORE_SELECTIONS else 0.0
            learn_delta = self_learning.prob_deltas.get(nm, 0.0) if self_learning is not None else 0.0
            p_eff = max(0.01, min(0.95, p - 1.28 * sigma + boost + gold_bonus + learn_delta))

            tier = "Tier-S" if (is_sharp and p >= 0.68 and p_eff >= 0.64) else (
                "Tier-A" if (is_sharp and p >= 0.63) else "Tier-B"
            )
            rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
            if abs(learn_delta) >= 0.005:
                rsns.append(f"Öğr {learn_delta*100:+.1f}p")
            if inj_note:
                rsns.append(inj_note)

            match_legs.append(
                UnifiedLeg(
                    code=code,
                    kickoff=str(m.get("kickoff") or ""),
                    kickoff_iso=ko_iso,
                    league=league,
                    match=f"{m.get('home', '')} - {m.get('away', '')}",
                    market=str(s.get("market") or ""),
                    selection=str(s.get("selection") or ""),
                    name=nm,
                    key=s_key,
                    odds=round(odds, 2),
                    prob=round(p, 4),
                    prob_effective=round(p_eff, 4),
                    ev=round(ev, 4),
                    mbs=int(s.get("mbs") or 1),
                    direct=bool(s.get("direct")),
                    is_sharp=is_sharp,
                    reference=ref.split(" (")[0],
                    mu_home=round(mu_h, 2),
                    mu_away=round(mu_a, 2),
                    tier=tier,
                    injury_boost=round(boost, 4),
                    reasons=tuple(rsns),
                )
            )

        if match_legs:
            # Pareto front (descending odds, strictly increasing p_effective)
            match_legs.sort(key=lambda x: (-x.odds, -x.prob_effective))
            front: list[UnifiedLeg] = []
            best_pe = -1.0
            for lg in match_legs:
                if lg.prob_effective > best_pe + 1e-9:
                    front.append(lg)
                    best_pe = lg.prob_effective
            pools.append(front)

    return pools


def optimize_unified_coupon(
    pools: Sequence[Sequence[UnifiedLeg]],
    *,
    coupon_id: str,
    title: str,
    mode: str,
    target_odds: float,
    min_legs: int = 3,
    max_legs: int = 5,
    max_same_selection: int = 2,
    max_same_league: int = 2,
    include_insurance: bool = True,
    insurance_budget_tl: float = 100.0,
    note: str = "",
) -> UnifiedCoupon | None:
    """Exact log-odds DP maximizing Σ log(prob_effective) subject to target odds, MBS, and diversity."""
    if not pools or target_odds <= 1.0:
        return None
    RES = 0.005
    log_t = math.log(target_odds)
    tb = math.ceil(log_t / RES)

    def _bucket(lo: float) -> int:
        return tb if lo >= log_t - 1e-12 else min(int(lo / RES), tb - 1)

    states: dict[tuple[int, int, int], tuple[float, float, tuple[UnifiedLeg, ...]]] = {
        (0, 1, 0): (0.0, 0.0, ())
    }
    for pool in pools:
        new = dict(states)
        for (n, mbs, _), (lp, lo, legs) in states.items():
            if n >= max_legs:
                continue
            for lg in pool:
                if sum(1 for x in legs if x.name == lg.name) >= max_same_selection:
                    continue
                if sum(1 for x in legs if x.league == lg.league) >= max_same_league:
                    continue
                nlo = lo + math.log(lg.odds)
                key = (n + 1, max(mbs, lg.mbs), _bucket(nlo))
                val = lp + math.log(lg.prob_effective)
                old = new.get(key)
                if old is None or val > old[0] + 1e-12 or (abs(val - old[0]) <= 1e-12 and nlo > old[1]):
                    new[key] = (val, nlo, legs + (lg,))
        states = new

    finals = [
        (lp, legs)
        for (n, mbs, b), (lp, lo, legs) in states.items()
        if b == tb and n >= max(mbs, min_legs, 1)
    ]
    if not finals:
        return None

    _, best_legs = max(finals, key=lambda x: (x[0], -len(x[1])))
    ordered = tuple(sorted(best_legs, key=lambda x: x.kickoff))
    tot_odds = math.prod(x.odds for x in ordered)
    tot_p = math.prod(x.prob for x in ordered)
    max_mbs = max(x.mbs for x in ordered)

    ins: SystemEvaluation | None = None
    if include_insurance and len(ordered) >= 4 and (len(ordered) - 1) >= max_mbs:
        sys_legs = [x.to_system_leg() for x in ordered]
        sizes = (len(ordered) - 1, len(ordered))
        n_cols = len(ordered) + 1
        stake = max(1.0, round(insurance_budget_tl / n_cols, 2))
        ins = evaluate_system(sys_legs, sizes, stake_per_col=stake)

    return UnifiedCoupon(
        coupon_id=coupon_id,
        title=title,
        mode=mode,
        legs=ordered,
        total_odds=round(tot_odds, 2),
        joint_prob=round(tot_p, 6),
        expected_value=round(tot_p * tot_odds - 1.0, 4),
        max_mbs=max_mbs,
        insurance=ins,
        note=note,
    )


def _select_top_specialty_legs(
    candidates: list[UnifiedLeg],
    *,
    n_legs: int,
    max_same_league: int = 2,
) -> tuple[UnifiedLeg, ...] | None:
    """Greedily pick top ``n_legs`` disjoint-match legs satisfying league diversity and MBS."""
    ordered = sorted(candidates, key=lambda x: (-x.prob_effective, -x.ev, -x.odds))
    chosen: list[UnifiedLeg] = []
    used_codes: set[int] = set()
    league_counts: dict[str, int] = {}
    for lg in ordered:
        if lg.code in used_codes:
            continue
        if lg.mbs > n_legs:
            continue
        if league_counts.get(lg.league, 0) >= max_same_league:
            continue
        chosen.append(lg)
        used_codes.add(lg.code)
        league_counts[lg.league] = league_counts.get(lg.league, 0) + 1
        if len(chosen) == n_legs:
            break
    if len(chosen) < n_legs:
        return None
    if max(x.mbs for x in chosen) > len(chosen):
        return None
    return tuple(sorted(chosen, key=lambda x: x.kickoff))


def _assemble_specialty_coupon(
    legs: tuple[UnifiedLeg, ...] | None,
    *,
    coupon_id: str,
    title: str,
    mode: str,
    note: str,
) -> UnifiedCoupon | None:
    if not legs:
        return None
    tot_odds = math.prod(x.odds for x in legs)
    tot_p = math.prod(x.prob for x in legs)
    return UnifiedCoupon(
        coupon_id=coupon_id,
        title=title,
        mode=mode,
        legs=legs,
        total_odds=round(tot_odds, 2),
        joint_prob=round(tot_p, 6),
        expected_value=round(tot_p * tot_odds - 1.0, 4),
        max_mbs=max(x.mbs for x in legs),
        insurance=None,
        note=note,
    )


def build_ht_score_coupon(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_legs: int = 3,
    coupon_id: str = "S01",
    prior_legs: Sequence[UnifiedLeg] = (),
    exclude_codes: set[int] | None = None,
) -> UnifiedCoupon | None:
    """Build First-Half Exact Score coupon (MTID 779) with directional GK1/scorer guards."""
    excl = exclude_codes or set()
    match_list = list(matches)
    for sharp_only in (True, False):
        cands: list[UnifiedLeg] = []
        for m in match_list:
            ok_m, is_sharp, _ = _match_is_eligible(
                m, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
                max_hours_to_kickoff=max_hours_to_kickoff, sharp_only=sharp_only,
                allow_youth=False, exclude_codes=excl,
            )
            if not ok_m:
                continue
            code = int(m["code"])
            league = str(m.get("league") or "")
            ref = str(m.get("reference") or "")
            mu_h, mu_a = float(m["mu_home"]), float(m["mu_away"])
            inj = extract_injury_profile(m)

            best_for_match: UnifiedLeg | None = None
            for s in m.get("selections") or []:
                nm = str(s.get("name") or "").strip()
                s_key = str(s.get("key") or nm)
                if not (s_key.startswith("779|") or (nm.startswith("İY Skor ") and " & " not in nm)):
                    continue
                odds = float(s.get("odds") or 0.0)
                p = float(s.get("fair_prob") or 0.0)
                if odds < 1.80 or p < 0.22:
                    continue
                ev = p * odds - 1.0
                if ev < -0.24 or ev > 0.30:
                    continue
                if _has_prior_conflict(code, s_key, nm, prior_legs):
                    continue
                ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
                if not ok_inj:
                    continue
                p_eff = max(0.01, min(0.85, p + boost + (0.012 if is_sharp else 0.0)))
                rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
                if inj_note:
                    rsns.append(inj_note)
                leg = UnifiedLeg(
                    code=code, kickoff=str(m.get("kickoff") or ""), kickoff_iso=str(m.get("kickoff_iso") or ""),
                    league=league, match=f"{m.get('home', '')} - {m.get('away', '')}",
                    market=str(s.get("market") or "1. Yarı Skoru"), selection=str(s.get("selection") or ""),
                    name=nm, key=s_key, odds=round(odds, 2), prob=round(p, 4),
                    prob_effective=round(p_eff, 4), ev=round(ev, 4), mbs=int(s.get("mbs") or 1),
                    direct=bool(s.get("direct")), is_sharp=is_sharp, reference=ref.split(" (")[0],
                    mu_home=round(mu_h, 2), mu_away=round(mu_a, 2), tier="Özel-İYSkor",
                    injury_boost=round(boost, 4), reasons=tuple(rsns),
                )
                if best_for_match is None or leg.prob_effective > best_for_match.prob_effective:
                    best_for_match = leg
            if best_for_match is not None:
                cands.append(best_for_match)

        legs = _select_top_specialty_legs(cands, n_legs=n_legs, max_same_league=2)
        if legs is not None:
            return _assemble_specialty_coupon(
                legs, coupon_id=coupon_id, title="Özel Kupon — İlk Yarı Skor (MTID 779)",
                mode="ozel_iy_skor",
                note="Kaleci eksiği olan maçlarda İY 0-0 engelli; golcü eksiği olan sıkı maçlar öncelikli.",
            )
    return None


def build_ft_score_coupon(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_legs: int = 2,
    coupon_id: str = "S02",
    yuksek_oran_data: dict[str, Any] | None = None,
    prior_legs: Sequence[UnifiedLeg] = (),
    exclude_codes: set[int] | None = None,
) -> UnifiedCoupon | None:
    """Build Full-Time Exact Score coupon (MTID 777), optionally boosted by golden_scores calibration."""
    excl = exclude_codes or set()
    golden_map: dict[tuple[int, str], float] = {}
    for entry in (yuksek_oran_data or {}).get("golden_scores") or []:
        c = int(entry.get("code") or 0)
        for ts in entry.get("top_scores") or []:
            if ts.get("is_golden") and ts.get("score"):
                golden_map[(c, f"Skor {ts['score']}")] = float(ts.get("p_model") or 0.0)

    match_list = list(matches)
    for sharp_only in (True, False):
        cands: list[UnifiedLeg] = []
        for m in match_list:
            ok_m, is_sharp, _ = _match_is_eligible(
                m, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
                max_hours_to_kickoff=max_hours_to_kickoff, sharp_only=sharp_only,
                allow_youth=False, exclude_codes=excl,
            )
            if not ok_m:
                continue
            code = int(m["code"])
            league = str(m.get("league") or "")
            ref = str(m.get("reference") or "")
            mu_h, mu_a = float(m["mu_home"]), float(m["mu_away"])
            inj = extract_injury_profile(m)

            best_for_match: UnifiedLeg | None = None
            for s in m.get("selections") or []:
                nm = str(s.get("name") or "").strip()
                s_key = str(s.get("key") or nm)
                if not (s_key.startswith("777|") or (nm.startswith("Skor ") and " & " not in nm)):
                    continue
                odds = float(s.get("odds") or 0.0)
                p = float(s.get("fair_prob") or 0.0)
                if odds < 4.50 or p < 0.09:
                    continue
                ev = p * odds - 1.0
                if ev < -0.25 or ev > 0.35:
                    continue
                if _has_prior_conflict(code, s_key, nm, prior_legs):
                    continue
                ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
                if not ok_inj:
                    continue
                is_golden = (code, nm) in golden_map
                g_boost = 0.012 if is_golden else 0.0
                p_eff = max(0.01, min(0.50, p + boost + g_boost + (0.008 if is_sharp else 0.0)))
                rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
                if is_golden:
                    rsns.append("Altın Skor kalibre")
                if inj_note:
                    rsns.append(inj_note)
                leg = UnifiedLeg(
                    code=code, kickoff=str(m.get("kickoff") or ""), kickoff_iso=str(m.get("kickoff_iso") or ""),
                    league=league, match=f"{m.get('home', '')} - {m.get('away', '')}",
                    market=str(s.get("market") or "Maç Skoru"), selection=str(s.get("selection") or ""),
                    name=nm, key=s_key, odds=round(odds, 2), prob=round(p, 4),
                    prob_effective=round(p_eff, 4), ev=round(ev, 4), mbs=int(s.get("mbs") or 1),
                    direct=bool(s.get("direct")), is_sharp=is_sharp, reference=ref.split(" (")[0],
                    mu_home=round(mu_h, 2), mu_away=round(mu_a, 2), tier="Özel-Skor",
                    injury_boost=round(boost, 4), reasons=tuple(rsns),
                )
                if best_for_match is None or leg.prob_effective > best_for_match.prob_effective:
                    best_for_match = leg
            if best_for_match is not None:
                cands.append(best_for_match)

        legs = _select_top_specialty_legs(cands, n_legs=n_legs, max_same_league=2)
        if legs is not None:
            return _assemble_specialty_coupon(
                legs, coupon_id=coupon_id, title="Özel Kupon — Maç Skoru (MTID 777)",
                mode="ozel_skor",
                note="En yüksek gerçek olasılıklı 2'li skor kombini (Altın Skor kalibrasyonu ve yönlü TM kalkanlı).",
            )
    return None


def build_htft_reversal_coupon(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_legs: int = 2,
    coupon_id: str = "S03",
    allowed_outcomes: frozenset[str] = ALLOWED_HTFT_REVERSALS,
    yuksek_oran_data: dict[str, Any] | None = None,
    prior_legs: Sequence[UnifiedLeg] = (),
    exclude_codes: set[int] | None = None,
) -> UnifiedCoupon | None:
    """Build HT/FT coupon restricted strictly to 1/2, 2/1, 0/1, 0/2, 1/0, 2/0 (MTID 5)."""
    excl = exclude_codes or set()
    rev_dna: dict[tuple[int, str], float] = {}
    for entry in (yuksek_oran_data or {}).get("htft_reversals") or []:
        c = int(entry.get("code") or 0)
        sel = str(entry.get("selection") or "").strip()
        if c and sel:
            rev_dna[(c, sel)] = float(entry.get("dna_score") or 0.0)

    match_list = list(matches)
    for sharp_only in (True, False):
        cands: list[UnifiedLeg] = []
        for m in match_list:
            ok_m, is_sharp, _ = _match_is_eligible(
                m, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
                max_hours_to_kickoff=max_hours_to_kickoff, sharp_only=sharp_only,
                allow_youth=False, exclude_codes=excl,
            )
            if not ok_m:
                continue
            code = int(m["code"])
            league = str(m.get("league") or "")
            ref = str(m.get("reference") or "")
            mu_h, mu_a = float(m["mu_home"]), float(m["mu_away"])
            inj = extract_injury_profile(m)

            best_for_match: UnifiedLeg | None = None
            for s in m.get("selections") or []:
                nm = str(s.get("name") or "").strip()
                s_key = str(s.get("key") or nm)
                if nm not in allowed_outcomes:
                    continue
                odds = float(s.get("odds") or 0.0)
                p = float(s.get("fair_prob") or 0.0)
                if odds < 3.00 or p < 0.03:
                    continue
                ev = p * odds - 1.0
                if ev < -0.24 or ev > 0.35:
                    continue
                if _has_prior_conflict(code, s_key, nm, prior_legs):
                    continue
                ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
                if not ok_inj:
                    continue
                dna = rev_dna.get((code, nm), 0.0)
                dna_boost = 0.015 if dna >= 75.0 else 0.0
                p_eff = max(0.01, min(0.55, p + boost + dna_boost + (0.010 if is_sharp else 0.0)))
                rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
                if dna >= 75.0:
                    rsns.append(f"Geri Dönüş DNA {dna:.0f}")
                if inj_note:
                    rsns.append(inj_note)
                leg = UnifiedLeg(
                    code=code, kickoff=str(m.get("kickoff") or ""), kickoff_iso=str(m.get("kickoff_iso") or ""),
                    league=league, match=f"{m.get('home', '')} - {m.get('away', '')}",
                    market=str(s.get("market") or "İlk Yarı/Maç Sonucu"), selection=str(s.get("selection") or ""),
                    name=nm, key=s_key, odds=round(odds, 2), prob=round(p, 4),
                    prob_effective=round(p_eff, 4), ev=round(ev, 4), mbs=int(s.get("mbs") or 1),
                    direct=bool(s.get("direct")), is_sharp=is_sharp, reference=ref.split(" (")[0],
                    mu_home=round(mu_h, 2), mu_away=round(mu_a, 2), tier="Özel-İYMS",
                    injury_boost=round(boost, 4), reasons=tuple(rsns),
                )
                if best_for_match is None or leg.prob_effective > best_for_match.prob_effective:
                    best_for_match = leg
            if best_for_match is not None:
                cands.append(best_for_match)

        legs = _select_top_specialty_legs(cands, n_legs=n_legs, max_same_league=2)
        if legs is not None:
            return _assemble_specialty_coupon(
                legs, coupon_id=coupon_id, title="Özel Kupon — İY/MS (1/2 · 2/1 · 0/1 · 0/2 · 1/0 · 2/0)",
                mode="ozel_iyms",
                note="Yalnız istenen 6 İY/MS senaryosu içinden en yüksek kalibre olasılıklı ve TM korumalı 2'li.",
            )
    return None


def build_both_halves_btts_coupon(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_legs: int = 2,
    coupon_id: str = "S04",
    ekstrem_gol_data: dict[str, Any] | None = None,
    prior_legs: Sequence[UnifiedLeg] = (),
    exclude_codes: set[int] | None = None,
) -> UnifiedCoupon | None:
    """Build Both-Halves BTTS coupon (MTID 801: İki Yarıda KG Var), blocking any top-scorer absence."""
    excl = exclude_codes or set()
    dna_map: dict[int, float] = {
        int(e["code"]): float(e.get("dna_score") or 0.0)
        for e in ((ekstrem_gol_data or {}).get("both_halves_btts") or [])
        if e.get("code")
    }
    match_list = list(matches)
    for sharp_only in (True, False):
        cands: list[UnifiedLeg] = []
        for m in match_list:
            ok_m, is_sharp, _ = _match_is_eligible(
                m, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
                max_hours_to_kickoff=max_hours_to_kickoff, sharp_only=sharp_only,
                allow_youth=False, exclude_codes=excl,
            )
            if not ok_m:
                continue
            code = int(m["code"])
            league = str(m.get("league") or "")
            ref = str(m.get("reference") or "")
            mu_h, mu_a = float(m["mu_home"]), float(m["mu_away"])
            if (mu_h + mu_a) < 2.95 or min(mu_h, mu_a) < 1.10:
                continue
            inj = extract_injury_profile(m)

            for s in m.get("selections") or []:
                nm = str(s.get("name") or "").strip()
                s_key = str(s.get("key") or nm)
                if nm != "İki Yarıda KG Var":
                    continue
                odds = float(s.get("odds") or 0.0)
                p = float(s.get("fair_prob") or 0.0)
                if odds < 4.00 or p < 0.05:
                    continue
                ev = p * odds - 1.0
                if ev < -0.28 or ev > 0.35:
                    continue
                if _has_prior_conflict(code, s_key, nm, prior_legs):
                    continue
                ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
                if not ok_inj:
                    continue
                dna = dna_map.get(code, 0.0)
                dna_boost = 0.015 if dna >= 65.0 else 0.0
                p_eff = max(0.01, min(0.45, p + boost + dna_boost + (0.008 if is_sharp else 0.0)))
                rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
                if dna >= 65.0:
                    rsns.append(f"Ekstrem DNA {dna:.0f}")
                if inj_note:
                    rsns.append(inj_note)
                cands.append(
                    UnifiedLeg(
                        code=code, kickoff=str(m.get("kickoff") or ""), kickoff_iso=str(m.get("kickoff_iso") or ""),
                        league=league, match=f"{m.get('home', '')} - {m.get('away', '')}",
                        market=str(s.get("market") or "1. Yarı / 2. Yarı Karşılıklı Gol"),
                        selection=str(s.get("selection") or "Evet/Evet"),
                        name=nm, key=s_key, odds=round(odds, 2), prob=round(p, 4),
                        prob_effective=round(p_eff, 4), ev=round(ev, 4), mbs=int(s.get("mbs") or 1),
                        direct=bool(s.get("direct")), is_sharp=is_sharp, reference=ref.split(" (")[0],
                        mu_home=round(mu_h, 2), mu_away=round(mu_a, 2), tier="Özel-2YarıKG",
                        injury_boost=round(boost, 4), reasons=tuple(rsns),
                    )
                )
        legs = _select_top_specialty_legs(cands, n_legs=n_legs, max_same_league=2)
        if legs is not None:
            return _assemble_specialty_coupon(
                legs, coupon_id=coupon_id, title="Özel Kupon — İki Yarıda KG Var (MTID 801)",
                mode="ozel_iki_yari_kg",
                note="En yüksek çift-yönlü xG + Ekstrem DNA eşleşmesi; golcü eksiği olan maçlar otomatik elenir.",
            )
    return None


def build_second_half_btts_coupon(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_legs: int = 3,
    coupon_id: str = "S05",
    prior_legs: Sequence[UnifiedLeg] = (),
    exclude_codes: set[int] | None = None,
) -> UnifiedCoupon | None:
    """Build 2nd-Half BTTS coupon (MTID 599: 2Y KG Var), blocking any top-scorer absence."""
    excl = exclude_codes or set()
    match_list = list(matches)
    for sharp_only in (True, False):
        cands: list[UnifiedLeg] = []
        for m in match_list:
            ok_m, is_sharp, _ = _match_is_eligible(
                m, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
                max_hours_to_kickoff=max_hours_to_kickoff, sharp_only=sharp_only,
                allow_youth=False, exclude_codes=excl,
            )
            if not ok_m:
                continue
            code = int(m["code"])
            league = str(m.get("league") or "")
            ref = str(m.get("reference") or "")
            mu_h, mu_a = float(m["mu_home"]), float(m["mu_away"])
            if (mu_h + mu_a) < 2.80 or min(mu_h, mu_a) < 1.05:
                continue
            inj = extract_injury_profile(m)

            for s in m.get("selections") or []:
                nm = str(s.get("name") or "").strip()
                s_key = str(s.get("key") or nm)
                if nm != "2Y KG Var":
                    continue
                odds = float(s.get("odds") or 0.0)
                p = float(s.get("fair_prob") or 0.0)
                if odds < 1.80 or p < 0.25:
                    continue
                ev = p * odds - 1.0
                if ev < -0.25 or ev > 0.30:
                    continue
                if _has_prior_conflict(code, s_key, nm, prior_legs):
                    continue
                ok_inj, boost, inj_note = evaluate_directional_injury(nm, inj)
                if not ok_inj:
                    continue
                p_eff = max(0.01, min(0.70, p + boost + (0.012 if is_sharp else 0.0)))
                rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
                if inj_note:
                    rsns.append(inj_note)
                cands.append(
                    UnifiedLeg(
                        code=code, kickoff=str(m.get("kickoff") or ""), kickoff_iso=str(m.get("kickoff_iso") or ""),
                        league=league, match=f"{m.get('home', '')} - {m.get('away', '')}",
                        market=str(s.get("market") or "2. Yarı Karşılıklı Gol"),
                        selection=str(s.get("selection") or "Var"),
                        name=nm, key=s_key, odds=round(odds, 2), prob=round(p, 4),
                        prob_effective=round(p_eff, 4), ev=round(ev, 4), mbs=int(s.get("mbs") or 1),
                        direct=bool(s.get("direct")), is_sharp=is_sharp, reference=ref.split(" (")[0],
                        mu_home=round(mu_h, 2), mu_away=round(mu_a, 2), tier="Özel-2YKG",
                        injury_boost=round(boost, 4), reasons=tuple(rsns),
                    )
                )
        legs = _select_top_specialty_legs(cands, n_legs=n_legs, max_same_league=2)
        if legs is not None:
            return _assemble_specialty_coupon(
                legs, coupon_id=coupon_id, title="Özel Kupon — 2. Yarı KG Var (MTID 599)",
                mode="ozel_2y_kg",
                note="Yüksek tempolu açık maçlar; golcü eksiği engelli, kaleci/savunma krizi pozitif destekli.",
            )
    return None


def build_specialty_suite(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    ekstrem_gol_data: dict[str, Any] | None = None,
    yuksek_oran_data: dict[str, Any] | None = None,
    prior_legs: Sequence[UnifiedLeg] = (),
) -> list[UnifiedCoupon]:
    """Build all 5 specialty coupons cleanly with zero cross-coupon conflicts."""
    match_list = list(matches)
    seen_legs = list(prior_legs)
    suite: list[UnifiedCoupon] = []

    builders = [
        lambda pl: build_ht_score_coupon(
            match_list, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff, prior_legs=pl,
        ),
        lambda pl: build_ft_score_coupon(
            match_list, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff, yuksek_oran_data=yuksek_oran_data, prior_legs=pl,
        ),
        lambda pl: build_htft_reversal_coupon(
            match_list, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff, yuksek_oran_data=yuksek_oran_data, prior_legs=pl,
        ),
        lambda pl: build_both_halves_btts_coupon(
            match_list, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff, ekstrem_gol_data=ekstrem_gol_data, prior_legs=pl,
        ),
        lambda pl: build_second_half_btts_coupon(
            match_list, now=now, min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff, prior_legs=pl,
        ),
    ]
    for fn in builders:
        c = fn(seen_legs)
        if c is not None:
            suite.append(c)
            seen_legs.extend(c.legs)
    return suite


def build_clean_slate_portfolio(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_20x: int = 2,
    self_learning: SelfLearningAdjustments | None = None,
    include_specialty: bool = False,
    ekstrem_gol_data: dict[str, Any] | None = None,
    yuksek_oran_data: dict[str, Any] | None = None,
) -> list[UnifiedCoupon]:
    """Build a complete, zero-overlap, zero-contradiction clean-slate portfolio:

    1. **U01 — 3'lü Kısa Banko (Gold Core, ~2.1–2.8x):** Highest win-probability 3-leg coupon.
    2. **U02 — 4'lü Dengeli + Tek-Bacak Sigorta (Gold Core, ~3.2–5.5x):** Zero overlap with U01.
    3. **U03..U0N — Bağımsız Minimum 20 Oran Kuponları (+ Tek-Bacak Sistem Sigortalı):** Zero overlap
       between 20x coupons, sharp-only first, directional TM injury & symmetric steam guards enforced.
    4. *(Optional, ``include_specialty=True``)* **S01..S05 — 5 Özel Kupon** (İY Skor, Maç Skoru,
       İY/MS 6'lı, İki Yarıda KG Var, 2Y KG Var) checked for zero contradictions against U01..U0N.
    """
    match_list = list(matches)
    built: list[UnifiedCoupon] = []
    used_banko_codes: set[int] = set()
    prior_legs: list[UnifiedLeg] = []

    # 1. Short 3-leg Gold Banko (target 2.05x -> 3 clean legs, ~40%+ realistic win probability!)
    p_banko = extract_clean_candidates(
        match_list, now=now, mode="banko",
        min_minutes_to_kickoff=min_minutes_to_kickoff,
        max_hours_to_kickoff=max_hours_to_kickoff,
        sharp_only=True, allow_youth=False,
        self_learning=self_learning,
    )
    u1 = optimize_unified_coupon(
        p_banko, coupon_id="U01",
        title="Altın Çekirdek — 3'lü Kısa Banko",
        mode="banko", target_odds=2.05, min_legs=3, max_legs=3,
        max_same_selection=2, max_same_league=2, include_insurance=False,
        note="2026 OOS + canlı çift-onaylı Altın Çekirdek keskin pazarlar; simetrik steam ve yönlü TM kalkanlı.",
    )
    if u1 is None:
        u1 = optimize_unified_coupon(
            p_banko, coupon_id="U01",
            title="Altın Çekirdek — Kısa Banko",
            mode="banko", target_odds=1.90, min_legs=3, max_legs=4,
            max_same_selection=2, max_same_league=2, include_insurance=True,
            note="2026 OOS + canlı çift-onaylı Altın Çekirdek keskin pazarlar.",
        )
    if u1 is not None:
        built.append(u1)
        used_banko_codes |= {x.code for x in u1.legs}
        prior_legs.extend(u1.legs)

    # 2. 4-leg Balanced Gold Core (disjoint from U01, with Sistem 3/4 + 4/4 insurance!)
    p_bal = extract_clean_candidates(
        match_list, now=now, mode="dengeli",
        min_minutes_to_kickoff=min_minutes_to_kickoff,
        max_hours_to_kickoff=max_hours_to_kickoff,
        sharp_only=True, allow_youth=False,
        exclude_codes=used_banko_codes,
        prior_legs=prior_legs,
        self_learning=self_learning,
    )
    u2 = optimize_unified_coupon(
        p_bal, coupon_id="U02",
        title="Altın Çekirdek — 4'lü Dengeli (+ Sistem 3/4 Sigortalı)",
        mode="dengeli", target_odds=3.20, min_legs=4, max_legs=4,
        max_same_selection=2, max_same_league=2, include_insurance=True,
        note="U01 ile sıfır ortak maç; tek maçtan yatmaya karşı Sistem 3,4 sigorta tablosu dahildir.",
    )
    if u2 is None:
        u2 = optimize_unified_coupon(
            p_bal, coupon_id="U02",
            title="Altın Çekirdek — 4'lü Dengeli (+ Sistem 3/4 Sigortalı)",
            mode="dengeli", target_odds=2.60, min_legs=4, max_legs=4,
            max_same_selection=2, max_same_league=2, include_insurance=True,
            note="U01 ile sıfır ortak maç; tek maçtan yatmaya karşı Sistem 3,4 sigorta tablosu dahildir.",
        )
    if u2 is not None:
        built.append(u2)
        used_banko_codes |= {x.code for x in u2.legs}
        prior_legs.extend(u2.legs)

    # 3. Independent Minimum 20.00+ Odds Coupons (disjoint from each other!)
    used_20x_codes: set[int] = set()
    for idx in range(1, n_20x + 1):
        cid = f"U{2 + idx:02d}"
        p_20 = extract_clean_candidates(
            match_list, now=now, mode="yuksek_20x",
            min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff,
            sharp_only=True, allow_youth=False,
            exclude_codes=used_20x_codes,
            prior_legs=prior_legs,
            self_learning=self_learning,
        )
        u_hi = optimize_unified_coupon(
            p_20, coupon_id=cid,
            title=f"Temiz Motor Minimum 20 Oran #{idx} (Keskin + Yönlü TM Kalkanlı)",
            mode="yuksek_20x", target_odds=20.80, min_legs=5, max_legs=7,
            max_same_selection=2, max_same_league=2, include_insurance=True,
            note="Diğer 20x kuponlarla sıfır ortak maç, yönlü sakatlık korumalı ve tek-bacak sistem sigortalı.",
        )
        if u_hi is None:
            u_hi = optimize_unified_coupon(
                p_20, coupon_id=cid,
                title=f"Temiz Motor Minimum 20 Oran #{idx} (Keskin 8'li)",
                mode="yuksek_20x", target_odds=20.20, min_legs=5, max_legs=8,
                max_same_selection=2, max_same_league=2, include_insurance=True,
                note="Diğer 20x kuponlarla sıfır ortak maç, yönlü sakatlık korumalı ve tek-bacak sigortalı.",
            )
        if u_hi is None:
            u_hi = optimize_unified_coupon(
                p_20, coupon_id=cid,
                title=f"Temiz Motor Minimum 20 Oran #{idx} (Keskin 9'lu)",
                mode="yuksek_20x", target_odds=20.10, min_legs=6, max_legs=9,
                max_same_selection=3, max_same_league=2, include_insurance=True,
                note="Diğer 20x kuponlarla sıfır ortak maç, yönlü sakatlık korumalı ve tek-bacak sigortalı.",
            )
        if u_hi is not None:
            built.append(u_hi)
            used_20x_codes |= {x.code for x in u_hi.legs}
            prior_legs.extend(u_hi.legs)

    # 4. Optional Specialty Suite (S01..S05) checked for zero contradictions against U01..U0N
    if include_specialty:
        suite = build_specialty_suite(
            match_list,
            now=now,
            min_minutes_to_kickoff=min_minutes_to_kickoff,
            max_hours_to_kickoff=max_hours_to_kickoff,
            ekstrem_gol_data=ekstrem_gol_data,
            yuksek_oran_data=yuksek_oran_data,
            prior_legs=prior_legs,
        )
        built.extend(suite)

    return built
