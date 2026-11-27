"""Quantitative T-60 lineup shock, exponential NPxG form rating, referee, and motivation signals.

Designed to work alongside sharp closing prices without double-counting public news:
  - When news is already priced into the sharp snapshot (``news_fresher_than_odds=False``),
    ``compute_lineup_shock`` preserves the sharp ``(mu_home, mu_away)`` intact and surfaces
    diagnostic risk flags + theoretical sensitivity only.
  - When a confirmed T-60 lineup or late injury breaks AFTER the sharp snapshot
    (``news_fresher_than_odds=True``), ``compute_lineup_shock`` applies a bounded,
    regularized ``±12%`` multiplier to ``(mu_home, mu_away)``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import datetime as dt
import math
from typing import Any, Iterable, Mapping

import numpy as np


@dataclass(frozen=True)
class TeamXGProfile:
    """Exponentially-weighted team xG / NPxG attack & defense profile with league-mean shrinkage."""

    team: str
    matches: int
    effective_weight: float
    xg_for: float
    xg_against: float
    goals_for: float
    goals_against: float
    finishing_overperformance: float
    defensive_overperformance: float
    attack_index: float
    defense_index: float


@dataclass(frozen=True)
class LineupShock:
    """Bounded expected-goal adjustment from confirmed goalkeeper / top-scorer / starter absences."""

    mu_home_base: float
    mu_away_base: float
    mu_home_adj: float
    mu_away_adj: float
    home_multiplier: float
    away_multiplier: float
    theoretical_home_mult: float
    theoretical_away_mult: float
    applied: bool
    pre_market_window: bool
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RefereeProfile:
    """Empirical referee profile (goals, fouls, cards, red rate, and card/tempo z-scores)."""

    referee: str
    matches: int
    goals_per_match: float
    fouls_per_match: float
    yellows_per_match: float
    reds_per_match: float
    cards_per_match: float
    card_zscore: float
    goals_zscore: float


@dataclass(frozen=True)
class MotivationAssessment:
    """Structured motivation risk classification for matchday diagnostics."""

    regime: str
    dead_rubber: bool
    one_sided: bool
    high_stakes_tight: bool
    flags: tuple[str, ...] = ()


def _parse_date(val: Any) -> dt.date | None:
    if val is None or val == "":
        return None
    if isinstance(val, dt.datetime):
        return val.date()
    if isinstance(val, dt.date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def compute_team_xg_profiles(
    matches: Iterable[Mapping[str, Any]],
    *,
    as_of: dt.date | None = None,
    half_life_days: float = 90.0,
    shrink_games: float = 6.0,
) -> dict[str, TeamXGProfile]:
    """Compute exponentially-weighted team xG/NPxG profiles from historical match records.

    Accepts dicts with either football-data CSV columns (``HomeTeam``, ``AwayTeam``, ``Date``,
    ``HxG``, ``AxG``, ``FTHG``, ``FTAG``) or canonical snake_case keys (``home``, ``away``,
    ``date``, ``home_xg``, ``away_xg``, ``home_goals``, ``away_goals``).
    """
    parsed: list[tuple[dt.date | None, str, str, float, float, float, float]] = []
    for row in matches:
        home = str(row.get("HomeTeam") or row.get("home") or "").strip()
        away = str(row.get("AwayTeam") or row.get("away") or "").strip()
        hxg = _flt(row.get("HxG") if "HxG" in row else row.get("home_xg"))
        axg = _flt(row.get("AxG") if "AxG" in row else row.get("away_xg"))
        hg = _flt(row.get("FTHG") if "FTHG" in row else row.get("home_goals"))
        ag = _flt(row.get("FTAG") if "FTAG" in row else row.get("away_goals"))
        if not (home and away) or hxg is None or axg is None:
            continue
        d = _parse_date(row.get("Date") if "Date" in row else row.get("date"))
        if as_of is not None and d is not None and d > as_of:
            continue
        parsed.append((d, home, away, hxg, axg, hg if hg is not None else hxg, ag if ag is not None else axg))

    if not parsed:
        return {}

    ref_date = as_of or max((p[0] for p in parsed if p[0] is not None), default=None)
    decay = math.log(2.0) / max(float(half_life_days), 1.0)

    # League-wide mean xG per team per match for empirical-Bayes shrinkage.
    all_xg = [x for _, _, _, hxg, axg, _, _ in parsed for x in (hxg, axg)]
    lg_mean = float(np.mean(all_xg)) if all_xg else 1.35

    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # [n, w, xgf, xga, gf, ga]
    for d, home, away, hxg, axg, hg, ag in parsed:
        if ref_date is not None and d is not None:
            age_days = max(0.0, float((ref_date - d).days))
            w = math.exp(-decay * age_days)
        else:
            w = 1.0
        for team, xgf, xga, gf, ga in ((home, hxg, axg, hg, ag), (away, axg, hxg, ag, hg)):
            st = acc[team]
            st[0] += 1.0
            st[1] += w
            st[2] += w * xgf
            st[3] += w * xga
            st[4] += w * gf
            st[5] += w * ga

    prior_w = max(float(shrink_games), 0.0)
    profiles: dict[str, TeamXGProfile] = {}
    for team, (n, w_sum, s_xgf, s_xga, s_gf, s_ga) in acc.items():
        denom = max(w_sum + prior_w, 1e-9)
        xgf_shrunk = (s_xgf + prior_w * lg_mean) / denom
        xga_shrunk = (s_xga + prior_w * lg_mean) / denom
        raw_denom = max(w_sum, 1e-9)
        gf_avg = s_gf / raw_denom
        ga_avg = s_ga / raw_denom
        xgf_raw = s_xgf / raw_denom
        xga_raw = s_xga / raw_denom
        profiles[team] = TeamXGProfile(
            team=team,
            matches=int(n),
            effective_weight=round(w_sum, 3),
            xg_for=round(xgf_shrunk, 4),
            xg_against=round(xga_shrunk, 4),
            goals_for=round(gf_avg, 4),
            goals_against=round(ga_avg, 4),
            finishing_overperformance=round(gf_avg - xgf_raw, 4),
            defensive_overperformance=round(xga_raw - ga_avg, 4),
            attack_index=round(xgf_shrunk / max(lg_mean, 1e-6), 4),
            defense_index=round(xga_shrunk / max(lg_mean, 1e-6), 4),
        )
    return profiles


def compute_lineup_shock(
    mu_home: float,
    mu_away: float,
    *,
    home_gk1_out: bool = False,
    away_gk1_out: bool = False,
    home_top_scorer_out: bool = False,
    away_top_scorer_out: bool = False,
    home_scorer_goal_share: float | None = None,
    away_scorer_goal_share: float | None = None,
    home_other_starters_out: int = 0,
    away_other_starters_out: int = 0,
    news_fresher_than_odds: bool = False,
    max_shift: float = 0.12,
) -> LineupShock:
    """Quantify bounded expected-goal shifts from confirmed lineup absences.

    - Missing #1 goalkeeper increases opponent expected goals by ``+6.0%``.
    - Missing top scorer reduces own expected goals by ``clip(0.35 * goal_share, 4%, 10%)``
      (default ``-7.0%`` when ``goal_share`` is unavailable).
    - Each additional confirmed regular starter out (beyond GK / top scorer) reduces own attack
      by ``-2.0%`` and raises opponent attack by ``+1.5%``.
    - Total multiplier per side is strictly clamped to ``[1 - max_shift, 1 + max_shift]``
      (default ``[0.88, 1.12]``).
    - **Anti-double-counting rule:** Adjustments are applied to ``(mu_home_adj, mu_away_adj)``
      ONLY when ``news_fresher_than_odds=True`` (i.e. T-60 lineup or late injury broke after the
      sharp price snapshot). Otherwise sharp rates are preserved and flags are surfaced for risk
      filtering.
    """
    mh = max(0.05, float(mu_home))
    ma = max(0.05, float(mu_away))
    cap = float(np.clip(max_shift, 0.02, 0.25))

    def _scorer_drop(share: float | None) -> float:
        if share is None:
            return 0.07
        return float(np.clip(0.35 * float(share), 0.04, 0.10))

    h_mult = 1.0
    a_mult = 1.0
    flags: list[str] = []

    if home_gk1_out:
        a_mult *= 1.06
        flags.append("ev 1. kaleci eksik (rakip xG +6%)")
    if away_gk1_out:
        h_mult *= 1.06
        flags.append("dep 1. kaleci eksik (rakip xG +6%)")

    if home_top_scorer_out:
        drop = _scorer_drop(home_scorer_goal_share)
        h_mult *= 1.0 - drop
        flags.append(f"ev 1. golcü eksik (ev xG -{drop * 100:.1f}%)")
    if away_top_scorer_out:
        drop = _scorer_drop(away_scorer_goal_share)
        a_mult *= 1.0 - drop
        flags.append(f"dep 1. golcü eksik (dep xG -{drop * 100:.1f}%)")

    h_extra = max(0, int(home_other_starters_out))
    a_extra = max(0, int(away_other_starters_out))
    if h_extra > 0:
        h_mult *= max(0.90, 1.0 - 0.02 * h_extra)
        a_mult *= min(1.10, 1.0 + 0.015 * h_extra)
        flags.append(f"ev {h_extra} ek as oyuncu eksik")
    if a_extra > 0:
        a_mult *= max(0.90, 1.0 - 0.02 * a_extra)
        h_mult *= min(1.10, 1.0 + 0.015 * a_extra)
        flags.append(f"dep {a_extra} ek as oyuncu eksik")

    theo_h = float(np.clip(h_mult, 1.0 - cap, 1.0 + cap))
    theo_a = float(np.clip(a_mult, 1.0 - cap, 1.0 + cap))

    if news_fresher_than_odds:
        eff_h, eff_a = theo_h, theo_a
        applied = bool(flags)
    else:
        eff_h, eff_a = 1.0, 1.0
        applied = False

    return LineupShock(
        mu_home_base=round(mh, 4),
        mu_away_base=round(ma, 4),
        mu_home_adj=round(mh * eff_h, 4),
        mu_away_adj=round(ma * eff_a, 4),
        home_multiplier=round(eff_h, 4),
        away_multiplier=round(eff_a, 4),
        theoretical_home_mult=round(theo_h, 4),
        theoretical_away_mult=round(theo_a, 4),
        applied=applied,
        pre_market_window=bool(news_fresher_than_odds),
        flags=tuple(flags),
    )


def build_referee_profiles(
    matches: Iterable[Mapping[str, Any]],
    *,
    min_matches: int = 5,
) -> dict[str, RefereeProfile]:
    """Build per-referee goal, foul, yellow, and red card profiles across any league dataset."""
    acc: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    for row in matches:
        ref = str(row.get("Referee") or row.get("referee") or "").strip()
        if not ref:
            continue
        hg = _flt(row.get("FTHG") if "FTHG" in row else row.get("home_goals"))
        ag = _flt(row.get("FTAG") if "FTAG" in row else row.get("away_goals"))
        if hg is None or ag is None:
            continue
        hf = _flt(row.get("HF") if "HF" in row else row.get("home_fouls")) or 0.0
        af = _flt(row.get("AF") if "AF" in row else row.get("away_fouls")) or 0.0
        hy = _flt(row.get("HY") if "HY" in row else row.get("home_yellows")) or 0.0
        ay = _flt(row.get("AY") if "AY" in row else row.get("away_yellows")) or 0.0
        hr = _flt(row.get("HR") if "HR" in row else row.get("home_reds")) or 0.0
        ar = _flt(row.get("AR") if "AR" in row else row.get("away_reds")) or 0.0
        acc[ref].append((hg + ag, hf + af, hy + ay, hr + ar))

    eligible = {ref: rows for ref, rows in acc.items() if len(rows) >= max(1, int(min_matches))}
    if not eligible:
        return {}

    all_goals = [g for rows in eligible.values() for g, _, _, _ in rows]
    all_cards = [y + r for rows in eligible.values() for _, _, y, r in rows]
    g_mean, g_std = float(np.mean(all_goals)), max(float(np.std(all_goals)), 1e-6)
    c_mean, c_std = float(np.mean(all_cards)), max(float(np.std(all_cards)), 1e-6)

    out: dict[str, RefereeProfile] = {}
    for ref, rows in eligible.items():
        n = len(rows)
        g_avg = float(np.mean([x[0] for x in rows]))
        f_avg = float(np.mean([x[1] for x in rows]))
        y_avg = float(np.mean([x[2] for x in rows]))
        r_avg = float(np.mean([x[3] for x in rows]))
        c_avg = y_avg + r_avg
        # Standard error of the referee mean for shrinkage-aware z-score.
        se_c = c_std / math.sqrt(n)
        se_g = g_std / math.sqrt(n)
        out[ref] = RefereeProfile(
            referee=ref,
            matches=n,
            goals_per_match=round(g_avg, 3),
            fouls_per_match=round(f_avg, 3),
            yellows_per_match=round(y_avg, 3),
            reds_per_match=round(r_avg, 3),
            cards_per_match=round(c_avg, 3),
            card_zscore=round((c_avg - c_mean) / max(se_c, 1e-6), 3),
            goals_zscore=round((g_avg - g_mean) / max(se_g, 1e-6), 3),
        )
    return out


_HIGH_STAKES_TOKENS = ("şampiyon", "title", "küme", "relegation", "avrupa", "europe", "play-off", "playoff", "final")
_LOW_STAKES_TOKENS = ("hedefsiz", "dead rubber", "orta sıra", "mid-table", "garantiledi", "secured", "elendi", "eliminated")


def assess_motivation_risk(
    home_motivation: str | None,
    away_motivation: str | None,
) -> MotivationAssessment:
    """Classify matchday motivation regime from Turkish/English table-context strings."""
    h_low = str(home_motivation or "").lower()
    a_low = str(away_motivation or "").lower()

    h_high = any(tok in h_low for tok in _HIGH_STAKES_TOKENS)
    a_high = any(tok in a_low for tok in _HIGH_STAKES_TOKENS)
    h_dead = any(tok in h_low for tok in _LOW_STAKES_TOKENS)
    a_dead = any(tok in a_low for tok in _LOW_STAKES_TOKENS)

    flags: list[str] = []
    if h_dead and a_dead:
        flags.append("iki takım da hedefsiz (dead rubber — rotasyon/tempo oynaklığı)")
        return MotivationAssessment("dead_rubber", True, False, False, tuple(flags))
    if (h_high and a_dead) or (a_high and h_dead):
        side = "ev" if h_high else "dep"
        flags.append(f"tek taraflı motivasyon ({side} hedef maçı, rakip hedefsiz)")
        return MotivationAssessment("one_sided", False, True, False, tuple(flags))
    if h_high and a_high:
        flags.append("yüksek baskılı iki taraflı hedef maçı (sıkı tempo / beraberlik riski)")
        return MotivationAssessment("high_stakes_tight", False, False, True, tuple(flags))
    return MotivationAssessment("normal", False, False, False, ())
