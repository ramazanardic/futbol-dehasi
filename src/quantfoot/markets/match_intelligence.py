"""Unified pre-match football intelligence engine (xG form, finishing luck, referee z-scores, T-60 lineup shock, fatigue).

Reads live 2026/27 box-score & xG archives (``data/global_odds/latest/season_2627/*.csv``) strictly causally
(``date < as_of``) and synthesizes four independent, empirically grounded layers alongside sharp prices:

1. **Exponential NPxG/xG Attack & Defense Profiles + Finishing Luck Regression:**
   Detects unsustainable finishing bubbles (``GF - xGF >= +0.45/match``) or goalkeeper overperformance
   (``xGA - GA >= +0.45/match``) and computes market-independent xG-implied expected goals ``(xg_mu_h, xg_mu_a)``.
2. **Referee Card & Tempo Z-Scores:**
   Normalizes referee names across ESPN/FotMob/football-data (e.g. ``"Michael Oliver"`` ↔ ``"M Oliver"``)
   to surface high-card / high-volatility officials directly to ``market_diagnosis``.
3. **T-60 Confirmed Lineup Shock (Anti-Double-Counting):**
   Synthesizes ESPN announced lineups, Transfermarkt, FPL, and user absence files into ``LineupShock``,
   applying bounded ``±12%`` rate shifts ONLY when confirmed news breaks after the sharp snapshot.
4. **Rest-Day Asymmetry & Severe Weather Risk Diagnostics:**
   Flags acute fixture fatigue (``rest <= 3.0d`` vs opponent ``>= 6.0d``) and weather-dampened scoring totals.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import datetime as dt
import difflib
from functools import lru_cache
import math
from pathlib import Path
import re
from typing import Any, Mapping
import unicodedata

from quantfoot.markets.lineup_xg import (
    LineupShock,
    RefereeProfile,
    TeamXGProfile,
    build_referee_profiles,
    compute_lineup_shock,
    compute_team_xg_profiles,
)
from quantfoot.markets.market_calibration import nesine_league_to_division
from quantfoot.paths import REPO_ROOT

SEASON_DATA_DIR = REPO_ROOT / "data" / "global_odds" / "latest" / "season_2627"

# Empirical club-football constants (calibrated on 22 European leagues)
DEFAULT_HOME_XG_MULT = 1.11
DEFAULT_AWAY_XG_MULT = 0.89
LUCK_BUBBLE_THRESHOLD = 0.45   # goals/match over/under xG across >= 5 games
MIN_LUCK_MATCHES = 5
FATIGUE_SHORT_REST_DAYS = 3.0
FATIGUE_FRESH_OPP_DAYS = 6.0
FATIGUE_MIN_GAP_DAYS = 2.5
WEATHER_GOAL_DAMPEN_MAX = 0.12

_TEAM_STOP = re.compile(
    r"\b(fc|cf|sc|ac|afc|sk|fk|nk|cd|ca|ud|sv|bk|if|ik|club|de|da|the|calcio|athletic|sporting)\b"
)
_TEAM_SYNONYMS: dict[str, str] = {
    "man utd": "manchester united",
    "man united": "manchester united",
    "man city": "manchester city",
    "nott m forest": "nottingham forest",
    "nottm forest": "nottingham forest",
    "spurs": "tottenham",
    "wolves": "wolverhampton",
    "ath madrid": "atletico madrid",
    "ath bilbao": "athletic bilbao",
    "ein frankfurt": "eintracht frankfurt",
    "m gladbach": "borussia monchengladbach",
    "monchengladbach": "borussia monchengladbach",
    "bayern munich": "bayern munchen",
    "inter milan": "inter",
    "ac milan": "milan",
    "psg": "paris saint germain",
    "paris sg": "paris saint germain",
    "st etienne": "saint etienne",
    "az alkmaar": "az",
    "psv eindhoven": "psv",
    "fenerbahce": "fenerbahce",
    "galatasaray": "galatasaray",
    "besiktas": "besiktas",
    "trabzonspor": "trabzonspor",
    "basaksehir": "istanbul basaksehir",
    "west brom": "west bromwich",
    "sheff utd": "sheffield united",
    "sheff wed": "sheffield wednesday",
    "qpr": "queens park rangers",
}


def _ascii_norm(text: str) -> str:
    tr = str.maketrans("İIıŞşĞğÜüÖöÇç", "iiissgguuoocc")
    s = unicodedata.normalize("NFKD", (text or "").translate(tr)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def _norm_team(name: str) -> str:
    raw = _ascii_norm(name)
    if raw in _TEAM_SYNONYMS:
        raw = _TEAM_SYNONYMS[raw]
    cleaned = re.sub(_TEAM_STOP, " ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _TEAM_SYNONYMS.get(cleaned, cleaned)


def _match_team_name(query: str, candidates: Mapping[str, Any], min_sim: float = 0.68) -> str | None:
    """Fuzzy-match a Nesine/ESPN team name against football-data season CSV team keys."""
    nq = _norm_team(query)
    if not nq:
        return None
    best_k: str | None = None
    best_s = 0.0
    qt = set(nq.split())
    for k in candidates:
        nk = _norm_team(k)
        if not nk:
            continue
        if nk == nq:
            return k
        if (len(nq) >= 4 and nq in nk) or (len(nk) >= 4 and nk in nq):
            score = 0.92
        else:
            ratio = difflib.SequenceMatcher(None, nq, nk).ratio()
            kt = set(nk.split())
            jacc = len(qt & kt) / max(1, len(qt | kt))
            score = max(ratio, jacc)
        if score > best_s:
            best_s = score
            best_k = k
    return best_k if best_s >= min_sim else None


def _parse_csv_date(raw: str | None) -> dt.date | None:
    s = (raw or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y"):
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


def _boxscore_xg_fallback(row: Mapping[str, Any]) -> tuple[float | None, float | None]:
    """Simple empirical shot-quality xG proxy when a CSV division lacks HxG/AxG (e.g. EC, SC1..3)."""
    hs, as_ = _flt(row.get("HS")), _flt(row.get("AS"))
    hst, ast = _flt(row.get("HST")), _flt(row.get("AST"))
    hc, ac = _flt(row.get("HC")) or 0.0, _flt(row.get("AC")) or 0.0
    if hs is None or as_ is None or hst is None or ast is None:
        return None, None
    h_off = max(0.0, hs - hst)
    a_off = max(0.0, as_ - ast)
    # Calibrated linear shot-quality proxy (~0.24/SOT + 0.045/off-target + 0.025/corner)
    hxg = max(0.10, min(5.5, 0.12 + 0.24 * hst + 0.045 * h_off + 0.025 * hc))
    axg = max(0.10, min(5.5, 0.08 + 0.24 * ast + 0.045 * a_off + 0.025 * ac))
    return round(hxg, 3), round(axg, 3)


@lru_cache(maxsize=64)
def load_division_rows(division: str, data_dir: str = str(SEASON_DATA_DIR)) -> tuple[dict[str, Any], ...]:
    """Load and cache all played rows from a football-data 2026/27 division CSV."""
    path = Path(data_dir) / f"{division}.csv"
    if not path.exists():
        return ()
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for raw in csv.DictReader(fh):
            if not raw.get("HomeTeam") or not raw.get("AwayTeam"):
                continue
            if _flt(raw.get("FTHG")) is None or _flt(raw.get("FTAG")) is None:
                continue
            rec = dict(raw)
            if _flt(rec.get("HxG")) is None or _flt(rec.get("AxG")) is None:
                hxg, axg = _boxscore_xg_fallback(rec)
                if hxg is not None and axg is not None:
                    rec["HxG"] = hxg
                    rec["AxG"] = axg
                    rec["_xg_source"] = "boxscore_proxy"
            else:
                rec["_xg_source"] = "csv_xg"
            rows.append(rec)
    return tuple(rows)


@lru_cache(maxsize=8)
def load_all_referee_profiles(
    data_dir: str = str(SEASON_DATA_DIR),
    min_matches: int = 4,
) -> dict[str, RefereeProfile]:
    """Aggregate live 2026/27 referee profiles across every division CSV containing Referee data."""
    root = Path(data_dir)
    if not root.exists():
        return {}
    all_rows: list[dict[str, Any]] = []
    for p in sorted(root.glob("*.csv")):
        all_rows.extend(load_division_rows(p.stem, data_dir=data_dir))
    return build_referee_profiles(all_rows, min_matches=min_matches)


def _referee_key(name: str) -> tuple[str, str]:
    """Convert 'Michael Oliver' or 'M Oliver' or 'M. Oliver' -> (first_initial, surname)."""
    norm = _ascii_norm(name)
    parts = norm.split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    return (parts[0][0], parts[-1])


def lookup_referee_profile(
    referee_name: str | None,
    *,
    data_dir: str = str(SEASON_DATA_DIR),
    min_matches: int = 4,
) -> RefereeProfile | None:
    """Match an ESPN/FotMob full referee name against football-data abbreviated referee profiles."""
    if not referee_name or not str(referee_name).strip():
        return None
    profiles = load_all_referee_profiles(data_dir=data_dir, min_matches=min_matches)
    if not profiles:
        return None
    q_norm = _ascii_norm(referee_name)
    q_init, q_last = _referee_key(referee_name)
    if not q_last:
        return None

    # 1. Exact normalized match
    for name, prof in profiles.items():
        if _ascii_norm(name) == q_norm:
            return prof

    # 2. Exact surname + matching first initial (e.g. "Michael Oliver" <-> "M Oliver")
    surname_hits: list[RefereeProfile] = []
    for name, prof in profiles.items():
        p_init, p_last = _referee_key(name)
        if p_last == q_last:
            if not q_init or not p_init or q_init == p_init:
                return prof
            surname_hits.append(prof)
    if len(surname_hits) == 1 and not q_init:
        return surname_hits[0]
    return None


@dataclass(frozen=True)
class XGMatchView:
    """Independent xG-based match projection and finishing-luck diagnostics."""

    division: str
    home_team: str
    away_team: str
    xg_mu_home: float
    xg_mu_away: float
    league_avg_xg: float
    home_profile: TeamXGProfile
    away_profile: TeamXGProfile
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "division": self.division,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "xg_mu_home": self.xg_mu_home,
            "xg_mu_away": self.xg_mu_away,
            "league_avg_xg": self.league_avg_xg,
            "home": {
                "matches": self.home_profile.matches,
                "xg_for": self.home_profile.xg_for,
                "xg_against": self.home_profile.xg_against,
                "goals_for": self.home_profile.goals_for,
                "goals_against": self.home_profile.goals_against,
                "finishing_luck": self.home_profile.finishing_overperformance,
                "defensive_luck": self.home_profile.defensive_overperformance,
                "attack_index": self.home_profile.attack_index,
                "defense_index": self.home_profile.defense_index,
            },
            "away": {
                "matches": self.away_profile.matches,
                "xg_for": self.away_profile.xg_for,
                "xg_against": self.away_profile.xg_against,
                "goals_for": self.away_profile.goals_for,
                "goals_against": self.away_profile.goals_against,
                "finishing_luck": self.away_profile.finishing_overperformance,
                "defensive_luck": self.away_profile.defensive_overperformance,
                "attack_index": self.away_profile.attack_index,
                "defense_index": self.away_profile.defense_index,
            },
            "flags": list(self.flags),
        }


def build_xg_match_view(
    league: str,
    home: str,
    away: str,
    *,
    as_of: dt.date | None = None,
    half_life_days: float = 65.0,
    shrink_games: float = 5.0,
    min_team_matches: int = 3,
    data_dir: str = str(SEASON_DATA_DIR),
) -> XGMatchView | None:
    """Compute strictly causal xG attack/defense profiles, finishing-luck flags, and independent xG rates."""
    div = nesine_league_to_division(league)
    if not div:
        return None
    rows = load_division_rows(div, data_dir=data_dir)
    if not rows:
        return None
    if as_of is not None:
        rows = tuple(r for r in rows if (_parse_csv_date(r.get("Date")) or as_of) < as_of)
    if len(rows) < 12:
        return None

    profiles = compute_team_xg_profiles(
        rows,
        as_of=as_of,
        half_life_days=half_life_days,
        shrink_games=shrink_games,
    )
    hk = _match_team_name(home, profiles)
    ak = _match_team_name(away, profiles)
    if not hk or not ak or hk == ak:
        return None
    hp, ap = profiles[hk], profiles[ak]
    if min(hp.matches, ap.matches) < min_team_matches:
        return None

    # League-average xG per team per match + empirical home/away xG split from the division itself
    h_xgs = [_flt(r.get("HxG")) for r in rows]
    a_xgs = [_flt(r.get("AxG")) for r in rows]
    h_xgs = [x for x in h_xgs if x is not None]
    a_xgs = [x for x in a_xgs if x is not None]
    if not h_xgs or not a_xgs:
        return None
    mean_h = sum(h_xgs) / len(h_xgs)
    mean_a = sum(a_xgs) / len(a_xgs)
    lg_avg = 0.5 * (mean_h + mean_a)

    # Empirical-Bayes shrunk home/away venue multipliers so small early-season samples stay stable
    prior_n = 30.0
    n_m = float(len(h_xgs))
    home_mult = ((mean_h / max(lg_avg, 1e-6)) * n_m + DEFAULT_HOME_XG_MULT * prior_n) / (n_m + prior_n)
    away_mult = ((mean_a / max(lg_avg, 1e-6)) * n_m + DEFAULT_AWAY_XG_MULT * prior_n) / (n_m + prior_n)

    xg_mu_h = max(0.25, min(4.2, lg_avg * hp.attack_index * ap.defense_index * home_mult))
    xg_mu_a = max(0.25, min(4.2, lg_avg * ap.attack_index * hp.defense_index * away_mult))

    flags: list[str] = []
    for lbl, prof in (("Ev", hp), ("Dep", ap)):
        if prof.matches >= MIN_LUCK_MATCHES:
            if prof.finishing_overperformance >= LUCK_BUBBLE_THRESHOLD:
                flags.append(
                    f"xG şişkinliği ({lbl}): gol/maç {prof.goals_for:.2f} vs xG {prof.xg_for:.2f} "
                    f"(+{prof.finishing_overperformance:.2f} bitiricilik şansı — gerileme riski)"
                )
            elif prof.finishing_overperformance <= -LUCK_BUBBLE_THRESHOLD:
                flags.append(
                    f"xG şanssızlığı ({lbl}): gol/maç {prof.goals_for:.2f} vs xG {prof.xg_for:.2f} "
                    f"({prof.finishing_overperformance:+.2f} — pozitif tepki potansiyeli)"
                )
            if prof.defensive_overperformance >= LUCK_BUBBLE_THRESHOLD:
                flags.append(
                    f"Savunma şansı ({lbl}): yenen {prof.goals_against:.2f} vs xGA {prof.xg_against:.2f} "
                    f"(+{prof.defensive_overperformance:.2f} — kaleci/şans gerileme riski)"
                )

    return XGMatchView(
        division=div,
        home_team=hk,
        away_team=ak,
        xg_mu_home=round(xg_mu_h, 3),
        xg_mu_away=round(xg_mu_a, 3),
        league_avg_xg=round(lg_avg, 3),
        home_profile=hp,
        away_profile=ap,
        flags=tuple(flags),
    )


def assess_fatigue_asymmetry(
    home_rest_days: float | None,
    away_rest_days: float | None,
) -> dict[str, Any]:
    """Detect acute rest-day / fixture-congestion asymmetry between home and away sides."""
    h_r = _flt(home_rest_days)
    a_r = _flt(away_rest_days)
    if h_r is None or a_r is None:
        return {"rest_diff": None, "fatigued_side": None, "home_mult": 1.0, "away_mult": 1.0, "flag": None}
    diff = round(h_r - a_r, 1)
    if h_r <= FATIGUE_SHORT_REST_DAYS and a_r >= FATIGUE_FRESH_OPP_DAYS and (a_r - h_r) >= FATIGUE_MIN_GAP_DAYS:
        return {
            "rest_diff": diff,
            "fatigued_side": "home",
            "home_mult": 0.96,
            "away_mult": 1.03,
            "flag": f"Yorgunluk asimetrisi: Ev {h_r:.1f}g vs Dep {a_r:.1f}g dinlenme",
        }
    if a_r <= FATIGUE_SHORT_REST_DAYS and h_r >= FATIGUE_FRESH_OPP_DAYS and (h_r - a_r) >= FATIGUE_MIN_GAP_DAYS:
        return {
            "rest_diff": diff,
            "fatigued_side": "away",
            "home_mult": 1.03,
            "away_mult": 0.96,
            "flag": f"Yorgunluk asimetrisi: Dep {a_r:.1f}g vs Ev {h_r:.1f}g dinlenme",
        }
    return {"rest_diff": diff, "fatigued_side": None, "home_mult": 1.0, "away_mult": 1.0, "flag": None}


def weather_goal_multiplier(weather: Mapping[str, Any] | None) -> float:
    """Bounded scoring-rate dampener for severe kick-off precipitation, snow, or high wind."""
    if not isinstance(weather, Mapping) or not weather.get("severe"):
        return 1.0
    rain = _flt(weather.get("rain_mm")) or 0.0
    wind = _flt(weather.get("wind_kmh")) or 0.0
    snow = _flt(weather.get("snow_cm")) or 0.0
    drop = 0.0
    if rain >= 4.0:
        drop += min(0.06, 0.03 + 0.005 * max(0.0, rain - 4.0))
    if snow >= 1.0:
        drop += min(0.08, 0.05 + 0.01 * max(0.0, snow - 1.0))
    if wind >= 38.0:
        drop += min(0.06, 0.03 + 0.002 * max(0.0, wind - 38.0))
    return round(max(1.0 - WEATHER_GOAL_DAMPEN_MAX, 1.0 - drop), 4)


def evaluate_match_lineup_shock(
    mu_home: float | None,
    mu_away: float | None,
    research: Mapping[str, Any] | None,
    *,
    research_block: bool = False,
) -> LineupShock | None:
    """Synthesize confirmed absences across ESPN / TM / FPL / user files into a bounded LineupShock."""
    if mu_home is None or mu_away is None or not isinstance(research, Mapping):
        return None
    teams = research.get("teams") or {}
    tm = research.get("tm_absences") or {}
    ua = research.get("user_absences") or {}
    flags = research.get("flags") or []

    def _side_counts(side: str) -> tuple[bool, bool, int]:
        t = teams.get(side) or {}
        tm_s = tm.get(side) or {}
        ua_s = ua.get(side) or {}
        gk_out = bool(t.get("goalkeeper_changed") or tm_s.get("gk1_out") or ua_s.get("gk_out"))
        ts_out = bool(t.get("top_scorer_missing") or tm_s.get("top_scorer_out"))
        missing_regs = t.get("missing_regulars") or []
        extra = max(0, len(missing_regs) - int(bool(t.get("goalkeeper_changed"))) - int(bool(t.get("top_scorer_missing"))))
        if extra == 0 and tm_s.get("critical_absences"):
            extra = max(0, len(tm_s["critical_absences"]) - int(bool(tm_s.get("gk1_out"))) - int(bool(tm_s.get("top_scorer_out"))))
        return gk_out, ts_out, extra

    h_gk, h_ts, h_ex = _side_counts("home")
    a_gk, a_ts, a_ex = _side_counts("away")
    if not (h_gk or h_ts or h_ex or a_gk or a_ts or a_ex):
        return None

    news_fresher = bool(research_block) or any("global fiyat ilk 11" in str(f).lower() for f in flags)
    return compute_lineup_shock(
        float(mu_home),
        float(mu_away),
        home_gk1_out=h_gk,
        away_gk1_out=a_gk,
        home_top_scorer_out=h_ts,
        away_top_scorer_out=a_ts,
        home_other_starters_out=h_ex,
        away_other_starters_out=a_ex,
        news_fresher_than_odds=news_fresher,
    )


@dataclass(frozen=True)
class TeamHalfProfile:
    """Strictly causal team 1H/2H scoring, conceding, comeback, and draw profile."""

    team: str
    matches: int
    h1_gf: float
    h2_gf: float
    h1_ga: float
    h2_ga: float
    h1_attack_share: float
    h1_concede_share: float
    ht_leads: int
    leads_blown: int
    leads_lost: int
    lead_blown_rate: float
    lead_lost_rate: float
    ht_trails: int
    comebacks_pts: int
    comebacks_won: int
    comeback_pts_rate: float
    comeback_win_rate: float
    btts_1h_rate: float
    btts_2h_rate: float
    both_halves_btts_rate: float
    draw_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "team": self.team,
            "matches": self.matches,
            "h1_gf": self.h1_gf,
            "h2_gf": self.h2_gf,
            "h1_ga": self.h1_ga,
            "h2_ga": self.h2_ga,
            "h1_attack_share": self.h1_attack_share,
            "h1_concede_share": self.h1_concede_share,
            "ht_leads": self.ht_leads,
            "leads_blown": self.leads_blown,
            "leads_lost": self.leads_lost,
            "lead_blown_rate": self.lead_blown_rate,
            "lead_lost_rate": self.lead_lost_rate,
            "ht_trails": self.ht_trails,
            "comebacks_pts": self.comebacks_pts,
            "comebacks_won": self.comebacks_won,
            "comeback_pts_rate": self.comeback_pts_rate,
            "comeback_win_rate": self.comeback_win_rate,
            "btts_1h_rate": self.btts_1h_rate,
            "btts_2h_rate": self.btts_2h_rate,
            "both_halves_btts_rate": self.both_halves_btts_rate,
            "draw_rate": self.draw_rate,
        }


@dataclass(frozen=True)
class HalfSplitMatchView:
    """Match-level asymmetric 1H/2H scoring split & comeback profile for omni_markets and high-odds models."""

    division: str
    home_team: str
    away_team: str
    league_1h_share: float
    home_eff_1h_share: float
    away_eff_1h_share: float
    home_1h_urgency_shift: float
    away_1h_urgency_shift: float
    home_profile: TeamHalfProfile
    away_profile: TeamHalfProfile
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "division": self.division,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "league_1h_share": self.league_1h_share,
            "home_eff_1h_share": self.home_eff_1h_share,
            "away_eff_1h_share": self.away_eff_1h_share,
            "home_1h_urgency_shift": self.home_1h_urgency_shift,
            "away_1h_urgency_shift": self.away_1h_urgency_shift,
            "home": self.home_profile.to_dict(),
            "away": self.away_profile.to_dict(),
            "flags": list(self.flags),
        }


def compute_team_half_profiles(
    rows: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    as_of: dt.date | None = None,
    half_life_days: float = 65.0,
    shrink_goals: float = 10.0,
    shrink_events: float = 5.0,
) -> tuple[dict[str, TeamHalfProfile], float]:
    """Compute strictly causal EWMA 1H/2H scoring, comeback, both-halves BTTS, and draw profiles."""
    if not rows:
        return {}, 0.438

    parsed: list[tuple[dt.date | None, str, str, int, int, int, int]] = []
    max_date: dt.date | None = None
    tot_h1 = 0
    tot_ft = 0
    for r in rows:
        h = str(r.get("HomeTeam") or "").strip()
        a = str(r.get("AwayTeam") or "").strip()
        fthg = _flt(r.get("FTHG"))
        ftag = _flt(r.get("FTAG"))
        hthg = _flt(r.get("HTHG"))
        htag = _flt(r.get("HTAG"))
        if not h or not a or fthg is None or ftag is None or hthg is None or htag is None:
            continue
        hg, ag, h1, a1 = int(fthg), int(ftag), int(hthg), int(htag)
        if h1 > hg or a1 > ag or h1 < 0 or a1 < 0:
            continue
        d = _parse_csv_date(r.get("Date"))
        if as_of is not None and d is not None and d >= as_of:
            continue
        if d is not None and (max_date is None or d > max_date):
            max_date = d
        parsed.append((d, h, a, h1, a1, hg - h1, ag - a1))
        tot_h1 += h1 + a1
        tot_ft += hg + ag

    if not parsed:
        return {}, 0.438

    ref_date = as_of or max_date
    lg_1h_share = (tot_h1 / tot_ft) if tot_ft >= 20 else 0.438
    lg_1h_share = max(0.36, min(0.50, lg_1h_share))

    acc: dict[str, dict[str, float]] = {}

    def _slot(team: str) -> dict[str, float]:
        return acc.setdefault(
            team,
            {
                "n": 0.0, "w": 0.0,
                "h1_gf": 0.0, "h2_gf": 0.0, "h1_ga": 0.0, "h2_ga": 0.0,
                "ht_leads": 0.0, "leads_blown": 0.0, "leads_lost": 0.0,
                "ht_trails": 0.0, "cb_pts": 0.0, "cb_won": 0.0,
                "btts1": 0.0, "btts2": 0.0, "bh_btts": 0.0, "draws": 0.0,
            },
        )

    for d, h, a, h1, a1, h2, a2 in parsed:
        if ref_date is not None and d is not None:
            age = max(0.0, float((ref_date - d).days))
            w = math.pow(0.5, age / max(half_life_days, 1.0))
        else:
            w = 1.0
        ft_h, ft_a = h1 + h2, a1 + a2
        b1 = 1.0 if (h1 >= 1 and a1 >= 1) else 0.0
        b2 = 1.0 if (h2 >= 1 and a2 >= 1) else 0.0
        bh = 1.0 if (b1 > 0 and b2 > 0) else 0.0
        dr = 1.0 if ft_h == ft_a else 0.0

        for team, gf1, gf2, ga1, ga2, ftf, fta in (
            (h, h1, h2, a1, a2, ft_h, ft_a),
            (a, a1, a2, h1, h2, ft_a, ft_h),
        ):
            st = _slot(team)
            st["n"] += 1.0
            st["w"] += w
            st["h1_gf"] += w * gf1
            st["h2_gf"] += w * gf2
            st["h1_ga"] += w * ga1
            st["h2_ga"] += w * ga2
            st["btts1"] += w * b1
            st["btts2"] += w * b2
            st["bh_btts"] += w * bh
            st["draws"] += w * dr
            if gf1 > ga1:
                st["ht_leads"] += 1.0
                if ftf <= fta:
                    st["leads_blown"] += 1.0
                if ftf < fta:
                    st["leads_lost"] += 1.0
            elif gf1 < ga1:
                st["ht_trails"] += 1.0
                if ftf >= fta:
                    st["cb_pts"] += 1.0
                if ftf > fta:
                    st["cb_won"] += 1.0

    # Baseline priors calibrated on European leagues
    prior_lead_blown = 0.22
    prior_lead_lost = 0.075
    prior_cb_pts = 0.22
    prior_cb_won = 0.075

    profiles: dict[str, TeamHalfProfile] = {}
    for team, st in acc.items():
        w = max(st["w"], 1e-6)
        tot_gf = st["h1_gf"] + st["h2_gf"]
        tot_ga = st["h1_ga"] + st["h2_ga"]
        h1_att_share = (st["h1_gf"] + shrink_goals * lg_1h_share) / (tot_gf + shrink_goals)
        h1_con_share = (st["h1_ga"] + shrink_goals * lg_1h_share) / (tot_ga + shrink_goals)
        h1_att_share = max(0.28, min(0.60, h1_att_share))
        h1_con_share = max(0.28, min(0.60, h1_con_share))

        hl = st["ht_leads"]
        ht = st["ht_trails"]
        lead_blown_rate = (st["leads_blown"] + shrink_events * prior_lead_blown) / (hl + shrink_events)
        lead_lost_rate = (st["leads_lost"] + shrink_events * prior_lead_lost) / (hl + shrink_events)
        cb_pts_rate = (st["cb_pts"] + shrink_events * prior_cb_pts) / (ht + shrink_events)
        cb_win_rate = (st["cb_won"] + shrink_events * prior_cb_won) / (ht + shrink_events)

        profiles[team] = TeamHalfProfile(
            team=team,
            matches=int(st["n"]),
            h1_gf=round(st["h1_gf"] / w, 3),
            h2_gf=round(st["h2_gf"] / w, 3),
            h1_ga=round(st["h1_ga"] / w, 3),
            h2_ga=round(st["h2_ga"] / w, 3),
            h1_attack_share=round(h1_att_share, 4),
            h1_concede_share=round(h1_con_share, 4),
            ht_leads=int(hl),
            leads_blown=int(st["leads_blown"]),
            leads_lost=int(st["leads_lost"]),
            lead_blown_rate=round(lead_blown_rate, 4),
            lead_lost_rate=round(lead_lost_rate, 4),
            ht_trails=int(ht),
            comebacks_pts=int(st["cb_pts"]),
            comebacks_won=int(st["cb_won"]),
            comeback_pts_rate=round(cb_pts_rate, 4),
            comeback_win_rate=round(cb_win_rate, 4),
            btts_1h_rate=round(st["btts1"] / w, 4),
            btts_2h_rate=round(st["btts2"] / w, 4),
            both_halves_btts_rate=round(st["bh_btts"] / w, 4),
            draw_rate=round(st["draws"] / w, 4),
        )
    return profiles, round(lg_1h_share, 4)


def build_half_split_view(
    league: str,
    home: str,
    away: str,
    *,
    as_of: dt.date | None = None,
    min_team_matches: int = 4,
    data_dir: str = str(SEASON_DATA_DIR),
) -> HalfSplitMatchView | None:
    """Build match-specific 1H/2H scoring urgency shifts and comeback profiles from live 2026/27 HT+FT data."""
    div = nesine_league_to_division(league)
    if not div:
        return None
    rows = load_division_rows(div, data_dir=data_dir)
    if not rows:
        return None
    profiles, lg_1h = compute_team_half_profiles(rows, as_of=as_of)
    hk = _match_team_name(home, profiles)
    ak = _match_team_name(away, profiles)
    if not hk or not ak or hk == ak:
        return None
    hp, ap = profiles[hk], profiles[ak]
    if min(hp.matches, ap.matches) < min_team_matches:
        return None

    # Effective 1H goal share for each side combines attacker's 1H tendency (60%) + opponent's 1H concede tendency (40%)
    home_eff = 0.60 * hp.h1_attack_share + 0.40 * ap.h1_concede_share
    away_eff = 0.60 * ap.h1_attack_share + 0.40 * hp.h1_concede_share
    # Empirical-Bayes damping by sample size (full weight reached around 12 matches)
    sample_w = min(1.0, min(hp.matches, ap.matches) / 12.0)
    h_shift = max(-0.08, min(0.08, (home_eff - lg_1h) * sample_w))
    a_shift = max(-0.08, min(0.08, (away_eff - lg_1h) * sample_w))
    home_eff_clamped = max(0.30, min(0.58, lg_1h + h_shift))
    away_eff_clamped = max(0.30, min(0.58, lg_1h + a_shift))

    flags: list[str] = []
    if h_shift >= 0.035 and a_shift <= -0.025:
        flags.append(
            f"1/2 geri dönüş profili: Ev hızlı başlar (1Y %{100*home_eff_clamped:.0f}), "
            f"Dep 2. yarı açılır (2Y %{100*(1-away_eff_clamped):.0f})"
        )
    elif a_shift >= 0.035 and h_shift <= -0.025:
        flags.append(
            f"2/1 geri dönüş profili: Dep hızlı başlar (1Y %{100*away_eff_clamped:.0f}), "
            f"Ev 2. yarı açılır (2Y %{100*(1-home_eff_clamped):.0f})"
        )
    if hp.both_halves_btts_rate >= 0.14 and ap.both_halves_btts_rate >= 0.14:
        flags.append(
            f"İki yarıda KG temposu yüksek (Ev %{100*hp.both_halves_btts_rate:.0f} / "
            f"Dep %{100*ap.both_halves_btts_rate:.0f})"
        )

    return HalfSplitMatchView(
        division=div,
        home_team=hk,
        away_team=ak,
        league_1h_share=lg_1h,
        home_eff_1h_share=round(home_eff_clamped, 4),
        away_eff_1h_share=round(away_eff_clamped, 4),
        home_1h_urgency_shift=round(h_shift, 4),
        away_1h_urgency_shift=round(a_shift, 4),
        home_profile=hp,
        away_profile=ap,
        flags=tuple(flags),
    )


def build_boxscore_match_view(
    league: str,
    home: str,
    away: str,
    *,
    as_of: dt.date | None = None,
    half_life_days: float = 65.0,
    min_team_matches: int = 3,
    data_dir: str = str(SEASON_DATA_DIR),
) -> dict[str, Any] | None:
    """Strictly causal 2026/27 boxscore tactical & GK profile (shots, SOT, save-rate proxy, CS, corners, fouls, cards)."""
    div = nesine_league_to_division(league)
    if not div:
        return None
    rows = load_division_rows(div, data_dir=data_dir)
    if not rows:
        return None

    parsed: list[tuple[dt.date | None, dict[str, Any]]] = []
    max_date: dt.date | None = None
    for r in rows:
        d = _parse_csv_date(r.get("Date"))
        if as_of is not None and d is not None and d >= as_of:
            continue
        if d is not None and (max_date is None or d > max_date):
            max_date = d
        parsed.append((d, r))
    if len(parsed) < 12:
        return None

    ref_date = as_of or max_date
    acc: dict[str, dict[str, Any]] = {}

    def _slot(team: str) -> dict[str, Any]:
        return acc.setdefault(
            team,
            {
                "n": 0, "w": 0.0, "w_shots": 0.0, "w_sot": 0.0, "w_cor": 0.0, "w_foul": 0.0, "w_card": 0.0,
                "gf": 0.0, "ga": 0.0, "cs": 0.0,
                "sf": 0.0, "sa": 0.0, "sotf": 0.0, "sota": 0.0,
                "cf": 0.0, "ca": 0.0, "ff": 0.0, "cards": 0.0, "reds": 0.0,
                "recent_pts": [],
            },
        )

    for d, r in parsed:
        h = str(r.get("HomeTeam") or "").strip()
        a = str(r.get("AwayTeam") or "").strip()
        hg, ag = _flt(r.get("FTHG")), _flt(r.get("FTAG"))
        if not h or not a or hg is None or ag is None:
            continue
        if ref_date is not None and d is not None:
            age = max(0.0, float((ref_date - d).days))
            w = math.pow(0.5, age / max(half_life_days, 1.0))
        else:
            w = 1.0

        hs, as_ = _flt(r.get("HS")), _flt(r.get("AS"))
        hst, ast = _flt(r.get("HST")), _flt(r.get("AST"))
        hc, ac = _flt(r.get("HC")), _flt(r.get("AC"))
        hf, af = _flt(r.get("HF")), _flt(r.get("AF"))
        hy, ay = _flt(r.get("HY")), _flt(r.get("AY"))
        hr, ar = _flt(r.get("HR")), _flt(r.get("AR"))

        for team, gf, ga, sf, sa, sotf, sota, cf, ca, ff, y, red in (
            (h, hg, ag, hs, as_, hst, ast, hc, ac, hf, hy, hr),
            (a, ag, hg, as_, hs, ast, hst, ac, hc, af, ay, ar),
        ):
            st = _slot(team)
            st["n"] += 1
            st["w"] += w
            st["gf"] += w * gf
            st["ga"] += w * ga
            st["cs"] += w * (1.0 if ga == 0 else 0.0)
            pts = 3.0 if gf > ga else (1.0 if gf == ga else 0.0)
            st["recent_pts"].append((d or dt.date.min, pts))
            if sf is not None and sa is not None:
                st["w_shots"] += w
                st["sf"] += w * sf
                st["sa"] += w * sa
            if sotf is not None and sota is not None:
                st["w_sot"] += w
                st["sotf"] += w * sotf
                st["sota"] += w * sota
            if cf is not None and ca is not None:
                st["w_cor"] += w
                st["cf"] += w * cf
                st["ca"] += w * ca
            if ff is not None:
                st["w_foul"] += w
                st["ff"] += w * ff
            if y is not None:
                st["w_card"] += w
                st["cards"] += w * (y + 2.0 * (red or 0.0))
                st["reds"] += red or 0.0

    hk = _match_team_name(home, acc)
    ak = _match_team_name(away, acc)
    if not hk or not ak or hk == ak:
        return None
    if min(acc[hk]["n"], acc[ak]["n"]) < min_team_matches:
        return None

    def _summarize(team_key: str) -> dict[str, Any]:
        st = acc[team_key]
        w = max(st["w"], 1e-6)
        gf_pg = st["gf"] / w
        ga_pg = st["ga"] / w
        out_s: dict[str, Any] = {
            "team": team_key,
            "matches": st["n"],
            "goals_for": round(gf_pg, 3),
            "goals_against": round(ga_pg, 3),
            "clean_sheet_rate": round(st["cs"] / w, 3),
        }
        if st["w_shots"] > 0:
            sf_pg = st["sf"] / st["w_shots"]
            sa_pg = st["sa"] / st["w_shots"]
            out_s["shots_for"] = round(sf_pg, 2)
            out_s["shots_against"] = round(sa_pg, 2)
            out_s["shot_share"] = round(sf_pg / max(sf_pg + sa_pg, 1e-6), 4)
        if st["w_sot"] > 0:
            sotf_pg = st["sotf"] / st["w_sot"]
            sota_pg = st["sota"] / st["w_sot"]
            out_s["sot_for"] = round(sotf_pg, 2)
            out_s["sot_against"] = round(sota_pg, 2)
            out_s["sot_conversion"] = round(min(0.65, gf_pg / max(sotf_pg, 0.5)), 3)
            # Empirical-Bayes shrunk GK save-rate proxy: (SOT_against - GA) / SOT_against
            raw_save = max(0.35, min(0.92, 1.0 - ga_pg / max(sota_pg, 0.8)))
            sw = min(1.0, st["n"] / 10.0)
            out_s["gk_save_rate"] = round(sw * raw_save + (1.0 - sw) * 0.70, 3)
        if st["w_cor"] > 0:
            cf_pg = st["cf"] / st["w_cor"]
            ca_pg = st["ca"] / st["w_cor"]
            out_s["corners_for"] = round(cf_pg, 2)
            out_s["corners_against"] = round(ca_pg, 2)
            out_s["corner_share"] = round(cf_pg / max(cf_pg + ca_pg, 1e-6), 4)
        if st["w_foul"] > 0:
            out_s["fouls_for"] = round(st["ff"] / st["w_foul"], 2)
        if st["w_card"] > 0:
            out_s["cards_for"] = round(st["cards"] / st["w_card"], 2)
            out_s["reds_total"] = int(st["reds"])
        rec5 = [p for _, p in sorted(st["recent_pts"], key=lambda x: x[0])[-5:]]
        if rec5:
            out_s["recent5_ppg"] = round(sum(rec5) / len(rec5), 2)
        return out_s

    return {
        "division": div,
        "home": _summarize(hk),
        "away": _summarize(ak),
    }


def enrich_match_record(
    rec: dict[str, Any],
    *,
    as_of: dt.date | None = None,
    data_dir: str = str(SEASON_DATA_DIR),
) -> dict[str, Any]:
    """Attach live 2026/27 xG view, half-split, boxscore tactical profile, referee, fatigue, T-60 shock, and squad scouting."""
    res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
    flags: list[str] = res.setdefault("flags", [])

    # 1. Resolve match date strictly causally (only past matches < kickoff date)
    match_date = as_of
    if match_date is None and rec.get("kickoff_iso"):
        try:
            match_date = dt.datetime.fromisoformat(str(rec["kickoff_iso"])).date()
        except ValueError:
            match_date = None

    # 2. Live 2026/27 xG & finishing-luck regression intelligence
    xg_view = build_xg_match_view(
        str(rec.get("league") or ""),
        str(rec.get("home") or ""),
        str(rec.get("away") or ""),
        as_of=match_date,
        data_dir=data_dir,
    )
    if xg_view is not None:
        res["xg_intelligence"] = xg_view.to_dict()
        for f in xg_view.flags:
            if f not in flags:
                flags.append(f)

    # 2b. Live 2026/27 team 1H/2H scoring splits, comeback, and both-halves BTTS profiles
    half_view = build_half_split_view(
        str(rec.get("league") or ""),
        str(rec.get("home") or ""),
        str(rec.get("away") or ""),
        as_of=match_date,
        data_dir=data_dir,
    )
    if half_view is not None:
        res["half_split"] = half_view.to_dict()
        for f in half_view.flags:
            if f not in flags:
                flags.append(f)

    # 2c. Live 2026/27 boxscore tactical & goalkeeper profile (shots, SOT, GK save-rate, corners, fouls, cards)
    box_view = build_boxscore_match_view(
        str(rec.get("league") or ""),
        str(rec.get("home") or ""),
        str(rec.get("away") or ""),
        as_of=match_date,
        data_dir=data_dir,
    )
    if box_view is not None:
        res["boxscore_profile"] = box_view

    # 3. Referee card & goal tempo profile
    ref_name = res.get("referee")
    if ref_name and not res.get("referee_profile"):
        ref_prof = lookup_referee_profile(str(ref_name), data_dir=data_dir)
        if ref_prof is not None:
            res["referee_profile"] = {
                "referee": ref_prof.referee,
                "matches": ref_prof.matches,
                "goals_per_match": ref_prof.goals_per_match,
                "fouls_per_match": ref_prof.fouls_per_match,
                "yellows_per_match": ref_prof.yellows_per_match,
                "reds_per_match": ref_prof.reds_per_match,
                "cards_per_match": ref_prof.cards_per_match,
                "card_zscore": ref_prof.card_zscore,
                "goals_zscore": ref_prof.goals_zscore,
            }
            if ref_prof.card_zscore >= 1.5:
                tag = f"Sert hakem ({ref_prof.referee}): {ref_prof.cards_per_match:.1f} kart/maç (z={ref_prof.card_zscore:+.1f})"
                if tag not in flags:
                    flags.append(tag)

    # 4. Rest-day / fixture fatigue asymmetry
    teams = res.get("teams") or {}
    fat = assess_fatigue_asymmetry(
        (teams.get("home") or {}).get("rest_days"),
        (teams.get("away") or {}).get("rest_days"),
    )
    if fat["rest_diff"] is not None:
        res["fatigue"] = fat
        if fat["flag"] and fat["flag"] not in flags:
            flags.append(fat["flag"])

    # 5. T-60 lineup shock & sensitivity (strictly respects anti-double-counting)
    shock = evaluate_match_lineup_shock(
        rec.get("mu_home"),
        rec.get("mu_away"),
        res,
        research_block=bool(rec.get("research_block")),
    )
    if shock is not None:
        res["lineup_shock"] = {
            "mu_home_base": shock.mu_home_base,
            "mu_away_base": shock.mu_away_base,
            "mu_home_adj": shock.mu_home_adj,
            "mu_away_adj": shock.mu_away_adj,
            "home_multiplier": shock.home_multiplier,
            "away_multiplier": shock.away_multiplier,
            "theoretical_home_mult": shock.theoretical_home_mult,
            "theoretical_away_mult": shock.theoretical_away_mult,
            "applied": shock.applied,
            "pre_market_window": shock.pre_market_window,
            "flags": list(shock.flags),
        }

    # 6. Deep Line-by-Line Squad & Tactical Matchup Scouting (Kaleci / Defans / Orta Saha / Forvet + Derbi)
    from quantfoot.markets.squad_scouting import build_match_scouting_report

    scouting = build_match_scouting_report(rec)
    if scouting is not None and (scouting.confidence > 0.0 or scouting.derby is not None):
        res["squad_scouting"] = scouting.to_dict()
        for rf in scouting.risk_flags:
            if rf not in flags:
                flags.append(rf)

    # 7. Player Anytime Goalscorer / Card Props & European Cup / Travel Context
    from quantfoot.markets.player_props import assess_match_props_and_context

    props_ctx = assess_match_props_and_context(rec)
    if (
        props_ctx["home_goalscorers"]
        or props_ctx["away_goalscorers"]
        or props_ctx["home_card_risks"]
        or props_ctx["away_card_risks"]
        or props_ctx["context_flags"]
        or props_ctx["travel_distance_km"] is not None
    ):
        res["player_props"] = props_ctx
        for cf in props_ctx["context_flags"]:
            if cf not in flags:
                flags.append(cf)

    return rec
