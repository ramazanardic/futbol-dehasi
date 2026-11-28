"""QuantFoot Unified Decision & Coupon Engine (Clean-Slate Single-Source-of-Truth).

Replaces fragmented, contradicting rule layers with one transparent, empirically verified
decision engine calibrated on live settled Nesine slates (612 settled global-priced matches
across 22 & 27 Nov 2026).

Core principles
---------------
1. **Gold Core Market Whitelist (Banko / Core):** Only markets empirically verified to hold or
   beat model calibration (`>= 70%` realized hit rate on sharp prices), with strict xG regime
   gates (`1.5 Üst` requires `tot_xg >= 2.60`, `2.5 Üst` requires `tot_xg >= 3.10`, `3.5 Alt`
   requires `tot_xg <= 2.40` & `max_mu <= 1.55`).
2. **Sharp-Only Core Discipline:** Banko and Core coupons accept only sharp exchange/Pinnacle
   references (`SHARP_SOURCES`), zero women's/youth variance leagues, and a hard Nesine margin
   floor (`EV >= -0.145`).
3. **Directional Transfermarkt Injury Engine:** Instead of blindly penalizing or flipping `MS 1`:
   - Missing team top scorer blocks `KG Var`, `2Y KG Var`, `İki Yarıda KG Var`, and that team's
     goal/win bets, while boosting opponent-clean-sheet / `İY Skor 0-0` / team-Under picks.
   - Missing team #1 goalkeeper blocks all Unders / `KG Yok` / `İY Skor 0-0` and that team's win,
     while boosting the *opponent's* goal markets (`Ev/Dep 1.5 Üst`, `2.5 Üst`, `İY 0.5 Üst`)
     rather than fragile `MS 1/2`.
4. **Short Banko + Exact DP + Automatic Single-Leg Insurance:**
   - Banko defaults to **3 legs** (not 5× 1.21) for genuinely high coupon hit rates.
   - Multi-leg coupons automatically compute `Sistem (n-1, n)` single-leg insurance payouts via
     `system_builder.evaluate_system`.
5. **Portfolio Anti-Contradiction & Anti-Concentration:** Enforces max 2 legs per exact selection
   and max 2 legs per league inside a coupon, plus zero duplicates / zero contradictions across
   all coupons in a portfolio.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import datetime as dt
import math
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

# Empirically toxic markets across 612 settled Nesine matches (realized -5p to -14p vs model)
BANNED_CORE_SELECTIONS: frozenset[str] = frozenset({
    "İY ÇŞ 12",
    "DEĞİL(Ev İki Yarıda Gol)",
    "Ev 2.5 Alt",
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

# Markets proven >= 70% realized hit rate AND top-tier ROI (-8.5% to +4.1% on Nesine) across 612 settled matches
GOLD_CORE_SELECTIONS: frozenset[str] = frozenset({
    "Ev En Az Bir Yarıyı Kazanır",
    "İY KG Yok & 2Y KG Yok",
    "Ev 1.5 Alt",
    "Ev 1.5 Üst",
    "MS 1",
    "MS 2",
    "Ev İY 0.5 Alt",
    "Dep İY 0.5 Alt",
    "İY 0.5 Üst",
    "ÇŞ 1X",
})

# Additional clean selections allowed ONLY in 20+ odds / extended value coupons (with strict xG & injury guards)
EXTENDED_20X_SELECTIONS: frozenset[str] = GOLD_CORE_SELECTIONS | frozenset({
    "1.5 Üst",
    "2.5 Üst",
    "3.5 Alt",
    "2Y KG Yok",
    "ÇŞ X2",
    "Dep 0.5 Üst",
    "Ev 0.5 Üst",
    "Dep 1.5 Alt",
    "Ev 0.5 Alt",
    "KG Var",
    "KG Yok",
    "3.5 Üst",
    "2.5 Üst & KG Var",
    "MS 1 & 1.5 Üst",
    "MS 2 & 1.5 Üst",
    "2-3 Gol",
})

_STEAM_RE = re.compile(r"(Ev|Ber|Dep)\s*([+-]?\d+(?:\.\d+)?)p", re.I)


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


def evaluate_directional_injury(name: str, inj: InjuryProfile) -> tuple[bool, float, str | None]:
    """Apply directional TM injury intelligence to a candidate selection.

    Returns ``(allowed, prob_boost, note)``:
    - ``allowed=False`` rejects selections directly contradicted by a missing GK1 or top scorer.
    - ``prob_boost`` (+0.012 to +0.018) rewards selections *aligned* with the missing player
      (e.g. opponent goals when GK1 is out, team Under / İY 0-0 when top scorer is out).
    """
    n = name.strip()
    is_any_under = (
        n in ("3.5 Alt", "2.5 Alt", "1.5 Alt", "İY 1.5 Alt", "İY 0.5 Alt", "2Y KG Yok", "İY KG Yok & 2Y KG Yok", "KG Yok", "İY Skor 0-0")
    )
    is_both_score = n in ("KG Var", "2.5 Üst & KG Var", "2Y KG Var", "İki Yarıda KG Var")

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
        if n in ("Dep 0.5 Üst", "Dep 1.5 Üst", "İY 0.5 Üst"):
            return True, 0.015, "TM: Ev 1. kaleci/savunma eksik (dep golü destekli)"

    if inj.away_gk1_out or inj.away_def_crisis:
        if is_any_under or n in ("MS 2", "MS 2 & 1.5 Üst", "Ev 1.5 Alt", "Ev İY 0.5 Alt", "Ev 0.5 Alt"):
            return False, 0.0, "Dep 1. kaleci/savunma krizi -> Alt / Dep galibiyeti yasak"
        # Deliberately do NOT boost MS 1 (lesson from O.H. Leuven 2-2) or 2.5 Üst (Bochum 2-0): boost HOME GOALS!
        if n in ("Ev 0.5 Üst", "Ev 1.5 Üst", "İY 0.5 Üst"):
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
    """Single clean regime check enforcing all empirically proven xG, draw, cup, and steam laws."""
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

    # Hard steam guards (Nov 22 + 27 evidence: sharp steam >= 5.5p against side collapses MS & Unders)
    if name in ("MS 1", "ÇŞ 1X", "MS 1 & 1.5 Üst") and h_st <= -5.5:
        return False, f"sert negatif steam Ev ({h_st:+.1f}p)"
    if name in ("MS 2", "ÇŞ X2", "MS 2 & 1.5 Üst") and a_st <= -5.5:
        return False, f"sert negatif steam Dep ({a_st:+.1f}p)"
    if name in ("3.5 Alt", "2.5 Alt", "2Y KG Yok", "İY KG Yok & 2Y KG Yok") and max_st >= 6.0:
        return False, f"sert piyasa hareketi ({max_st:.1f}p) Alt için riskli"

    # Knockout cup guards: never take fragile MS or tight Under in single-leg cups
    if is_cup:
        if name in ("MS 1", "MS 2", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst") and p < 0.72:
            return False, "kupa 90' beraberlik riski"
        if name in ("Ev 0.5 Alt", "2.5 Üst") and p < 0.65:
            return False, "kupa varyans riski"

    # Exact xG regime gates (proven on 612 settled matches!)
    if name == "1.5 Üst":
        if tot < 2.60 or p < 0.70:
            return False, f"1.5 Üst için düşük tempo (xG={tot:.2f} < 2.60)"
    elif name == "2.5 Üst":
        if tot < 3.10 or p < (0.65 if mode == "banko" else 0.59):
            return False, f"2.5 Üst için düşük tempo (xG={tot:.2f} < 3.10)"
    elif name == "3.5 Üst":
        if tot < 3.65 or p < 0.56:
            return False, f"3.5 Üst için xG yetersiz ({tot:.2f})"
    elif name == "3.5 Alt":
        if tot > 2.40 or max_mu > 1.55 or p < 0.68:
            return False, f"3.5 Alt için yüksek tempo (xG={tot:.2f}, max={max_mu:.2f})"
    elif name == "İY 0.5 Üst":
        if tot < 2.55 or p < 0.65:
            return False, f"İY 0.5 Üst için düşük tempo (xG={tot:.2f})"
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
    elif name == "Ev En Az Bir Yarıyı Kazanır":
        if (mu_h - mu_a) < 0.60 or p < 0.65:
            return False, "Ev yarı galibiyeti için güç farkı yetersiz"
    elif name == "MS 1":
        if p < (0.65 if mode in ("banko", "dengeli") else 0.59) or (p_draw is not None and p_draw >= 0.27):
            return False, "MS 1 için olasılık düşük veya beraberlik riski yüksek"
    elif name == "MS 2":
        if p < (0.67 if mode in ("banko", "dengeli") else 0.61) or (p_draw is not None and p_draw >= 0.26):
            return False, "MS 2 için olasılık düşük veya beraberlik riski yüksek"
    elif name == "ÇŞ 1X":
        if p < 0.66 or tot >= 3.30 or (p1 is not None and p2 is not None and p2 - p1 > 0.05):
            return False, "ÇŞ 1X için zayıf ev / yüksek tempo riski"
    elif name == "ÇŞ X2":
        if p < 0.63 or tot >= 3.30 or (p1 is not None and p2 is not None and p1 - p2 > 0.05):
            return False, "ÇŞ X2 için zayıf deplasman / yüksek tempo riski"
    elif name in ("KG Var", "2.5 Üst & KG Var"):
        if tot < 3.15 or min_mu < 1.20 or p < 0.58:
            return False, f"KG Var için yetersiz çift taraflı xG ({mu_h:.2f}-{mu_a:.2f})"
    elif name == "KG Yok":
        if min_mu > 0.78 or tot >= 3.40 or p < 0.62:
            return False, "KG Yok için açık maç riski"
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
) -> list[list[UnifiedLeg]]:
    """Build clean, non-dominated per-match candidate pools under the unified decision engine."""
    ev_floor = min_ev if min_ev is not None else (-0.145 if mode in ("banko", "dengeli") else -0.165)
    excl = exclude_codes or set()
    pools: list[list[UnifiedLeg]] = []

    for m in matches:
        if m.get("status") != "fiyatlandı" or m.get("price_tier") == "ozel_bahis":
            continue
        code = int(m["code"])
        if code in excl or m.get("research_block"):
            continue
        league = str(m.get("league") or "")
        if is_uncalibrated_competition(league):
            continue
        if not allow_youth and is_youth_competition(league):
            continue

        ref = str(m.get("reference") or "")
        is_sharp = ref.startswith(SHARP_SOURCES)
        if sharp_only and not is_sharp:
            continue

        ko_iso = str(m.get("kickoff_iso") or "")
        hours_to_ko: float | None = None
        if now is not None and ko_iso:
            ko_dt = dt.datetime.fromisoformat(ko_iso)
            mins = (ko_dt - now).total_seconds() / 60.0
            if mins < min_minutes_to_kickoff:
                continue
            hours_to_ko = mins / 60.0
            if max_hours_to_kickoff is not None and hours_to_ko > max_hours_to_kickoff:
                continue

        mu_h = float(m.get("mu_home") or 0.0)
        mu_a = float(m.get("mu_away") or 0.0)
        if mu_h <= 0.0 or mu_a <= 0.0:
            continue
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
            odds = float(s.get("odds") or 0.0)
            p = float(s.get("fair_prob") or 0.0)
            if not nm or odds < 1.20 or p < 0.56:
                continue
            ev = p * odds - 1.0
            if ev > 0.25 or ev < ev_floor:
                continue

            # Check conflicts against already chosen portfolio legs on the same match
            conflict = False
            for pl in prior_legs:
                if pl.code == code:
                    if pl.key == s.get("key") or pl.name == nm:
                        conflict = True
                        break
                    if nm in _conflicting_selections(pl.name) or pl.name in _conflicting_selections(nm):
                        conflict = True
                        break
            if conflict:
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
            # Slight empirical bonus for proven Gold Core markets in core ranking
            gold_bonus = 0.010 if nm in GOLD_CORE_SELECTIONS else 0.0
            p_eff = max(0.01, min(0.95, p - 1.28 * sigma + boost + gold_bonus))

            tier = "Tier-S" if (is_sharp and p >= 0.68 and p_eff >= 0.64) else (
                "Tier-A" if (is_sharp and p >= 0.63) else "Tier-B"
            )
            rsns = [f"P=%{p*100:.1f}", f"EV %{ev*100:+.1f}", f"xG {mu_h:.2f}-{mu_a:.2f}"]
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
                    key=str(s.get("key") or nm),
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


def build_clean_slate_portfolio(
    matches: Iterable[dict[str, Any]],
    *,
    now: dt.datetime | None = None,
    min_minutes_to_kickoff: int = 15,
    max_hours_to_kickoff: float | None = None,
    n_20x: int = 2,
) -> list[UnifiedCoupon]:
    """Build a complete, zero-overlap, zero-contradiction clean-slate portfolio:

    1. **U01 — 3'lü Kısa Banko (Gold Core, ~2.1–2.8x):** Highest win-probability 3-leg coupon.
    2. **U02 — 4'lü Dengeli + Tek-Bacak Sigorta (Gold Core, ~3.5–5.5x):** Zero overlap with U01.
    3. **U03..U0N — Bağımsız Minimum 20 Oran Kuponları (+ Tek-Bacak Sistem Sigortalı):** Zero overlap
       between 20x coupons, sharp-only first, directional TM injury guards enforced.
    """
    match_list = list(matches)
    built: list[UnifiedCoupon] = []
    used_banko_codes: set[int] = set()
    prior_legs: list[UnifiedLeg] = []

    # 1. Short 3-leg Gold Banko (target 2.0x -> 3 clean legs, ~40%+ realistic win probability!)
    p_banko = extract_clean_candidates(
        match_list, now=now, mode="banko",
        min_minutes_to_kickoff=min_minutes_to_kickoff,
        max_hours_to_kickoff=max_hours_to_kickoff,
        sharp_only=True, allow_youth=False,
    )
    u1 = optimize_unified_coupon(
        p_banko, coupon_id="U01",
        title="Altın Çekirdek — 3'lü Kısa Banko",
        mode="banko", target_odds=2.05, min_legs=3, max_legs=3,
        max_same_selection=2, max_same_league=2, include_insurance=False,
        note="Yalnız %72–80 isabetli Altın Çekirdek keskin pazarlar; 5'li @1.21 yerine 3'lü kısa banko.",
    )
    if u1 is None:
        u1 = optimize_unified_coupon(
            p_banko, coupon_id="U01",
            title="Altın Çekirdek — Kısa Banko",
            mode="banko", target_odds=1.90, min_legs=3, max_legs=4,
            max_same_selection=2, max_same_league=2, include_insurance=True,
            note="Yalnız Altın Çekirdek keskin pazarlar.",
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
                mode="yuksek_20x", target_odds=20.50, min_legs=5, max_legs=8,
                max_same_selection=2, max_same_league=2, include_insurance=True,
                note="Diğer 20x kuponlarla sıfır ortak maç, yönlü sakatlık korumalı.",
            )
        if u_hi is not None:
            built.append(u_hi)
            used_20x_codes |= {x.code for x in u_hi.legs}
            prior_legs.extend(u_hi.legs)

    return built
