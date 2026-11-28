"""Price every Nesine selection of the day against a GLOBAL reference price, never against Nesine itself.

    python scripts/nesine_global.py --date 2026-11-19            # writes tahminler/<QUANTFOOT_AI>/<date>/nesine_global.{json,md}
    python scripts/nesine_global.py --date 2026-11-19 --min-ev 0.0

Reference price, best available per match (all free, no key, no quota):
  1. Pinnacle — from football-data.co.uk fixture files
  2. Smarkets exchange — bid/offer mid
     (1 and 2 are not reachable from Turkey; GitHub Actions fetches them abroad into
      data/global_odds/latest/references.json, see .github/workflows/global-odds.yml)
  3. ESPN odds feed (DraftKings) — fetched locally, weakest reference.
Matches without any reference are listed but NOT priced (fair prices are never derived from
Nesine's own odds).

From the reference 1X2 (+ O/U when quoted) the margin is removed (power method), goal rates are
fitted with no model prior (fund_weight = 0) and every Nesine market — İY/MS, KG, gol aralığı,
handikap, kombineler … — is priced from the coherent joint goal distribution (docs/markets.md;
derivative calibration in docs/research/experiments_2026_11.md). EV = fair probability × Nesine odds − 1.

Research context (reports/research/): fundamental models add no information to sharp prices;
the documented edge is a soft book offering more than the sharp fair price.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import difflib
import json
from pathlib import Path
import re
import unicodedata

from quantfoot.paths import LazyAiArea, LazyAiName
from quantfoot.settings import MAX_PLAUSIBLE_EV as SETTINGS_MAX_PLAUSIBLE_EV
from quantfoot.settings import MAX_PRICE_AGE_H, REFERENCE_LOAD_AGE_H
from quantfoot.settings import MARGIN_TILT
from quantfoot.data import fotmob
from quantfoot.data.absences import fetch_matchday_absences, format_tm_absence_brief
from quantfoot.data import web_research
from quantfoot.data.api_football import fetch_api_football_references
from quantfoot.data.api_budget import DEFAULT_DIR as API_BUDGET_DIR, default_budget
from quantfoot.data.live_espn import fetch_espn_slate
from quantfoot.data.match_dossier import CachedHttp
from quantfoot.data.match_research import espn_events, fpl_availability, motivation, research, staleness_flags
from quantfoot.data.nesine import TSI, betting_day, fetch_bulletin, league_names, market_overrounds, parse_bulletin
from quantfoot.data.oddsmath import (
    TEAM_ALIASES,
    fetch_oddsmath_references,
    is_women_match,
    is_youth_or_reserve_match,
)
from quantfoot.data.oddspapi import fetch_oddspapi_references
from quantfoot.data.sharp_sources import fetch_the_odds_api_references
from quantfoot.data.weather import fetch_matchday_weather
from quantfoot.markets.club_half_dna import club_omni_adjustments
from quantfoot.markets.consensus import BookmakerQuote, check_synthetic_coherence, precision_weighted_consensus
from quantfoot.markets.devig import devig
from quantfoot.markets.goal_markets import goal_probability
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets import form_priors, gfi_priors
from quantfoot.markets.league_halves import blend_with_league, league_first_half_share
from quantfoot.markets.match_intelligence import build_half_split_view, enrich_match_record
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.tail_goals import fit_tail_rates_from_markets, league_tail_regime, rake_score_matrix_to_markets
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition

ROOT = Path(__file__).resolve().parents[1]
# Every AI writes its predictions only into its own folder (user rule, 20 Nov): tahminler/<ai>/<date>/.
# QUANTFOOT_AI is required (quantfoot.paths). Days up to 19 Nov live in the old shared reports/daily.
AI_NAME = LazyAiName()
DAILY = LazyAiArea()
LEGACY_DAILY = ROOT / "reports" / "daily"
_STOP = r"\b(fc|cf|sc|ac|sk|fk|nk|cd|ca|club|de|da|the|utd|united|k|w|women|kadinlar|u\d+|bk|if|ik|afc|scc|sp|ba)\b"


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(k\)|\(kol\)", " ", s)
    raw = re.sub(r"[^a-z0-9]+", " ", s).strip()
    if raw in TEAM_ALIASES:
        raw = TEAM_ALIASES[raw]
    s = re.sub(_STOP, " ", raw)
    cleaned = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return TEAM_ALIASES.get(cleaned, cleaned)


def _sim(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    pref = 1.0 if (na[:5] == nb[:5] and len(na) >= 5) else 0.0
    return max(ratio, jacc, 0.85 * pref)


def _match(
    event,
    candidates: list[dict],
    max_hours: float = 3.0,
    threshold: float = 0.62,
    league: str = "",
) -> tuple[dict | None, float]:
    best, score = None, 0.0
    ev_w = is_women_match(league, event.home, event.away)
    ev_y = is_youth_or_reserve_match(league, event.home, event.away)
    for c in candidates:
        dt_sec = abs((c["kickoff"] - event.kickoff).total_seconds())
        if dt_sec > max_hours * 3600:
            continue
        if is_women_match(c.get("league", ""), c["home"], c["away"]) != ev_w:
            continue
        if is_youth_or_reserve_match(c.get("league", ""), c["home"], c["away"]) != ev_y:
            continue
        sh, sa = _sim(event.home, c["home"]), _sim(event.away, c["away"])
        s = (sh + sa) / 2
        if s < threshold and dt_sec <= 900 and max(sh, sa) >= 0.85 and min(sh, sa) >= 0.20:
            # same kick-off and one team clearly the same, the other only renamed (e.g. 'R. Wien (Amt)' = 'SK Rapid II',
            # 'Admira Wacker' = 'Trenkwalder Admira', 'TNS' = 'The New Saints'); analyze_day still checks _consistent
            s = threshold
        if s > score:
            best, score = c, s
    return (best, score) if score >= threshold else (None, score)


# ---- reference sources ------------------------------------------------------------------
MAX_PLAUSIBLE_EV = SETTINGS_MAX_PLAUSIBLE_EV
SOURCE_RANK = {
    "Pinnacle (football-data)": 0,
    "Smarkets (borsa)": 1,
    "Matchbook (borsa)": 1,
    "Betfair Borsası (football-data)": 2,
    "OddsMath (BetInAsia/Pinnacle)": 2,
    "OddsMath (Borsa)": 2,
    "ESPN (DraftKings/ESPN BET)": 4,
}
EXCHANGES = ("Smarkets (borsa)", "Matchbook (borsa)")
SHARP_SOURCE_PREFIXES = (
    "Pinnacle",
    "Smarkets",
    "Matchbook",
    "Betfair",
    "OddsMath (BetInAsia",
    "OddsMath (Borsa",
)


def is_sharp_source(source: str | None) -> bool:
    """True for low-margin sharp bookmakers/exchanges eligible for coupon building."""
    return bool(source and source.startswith(SHARP_SOURCE_PREFIXES))


def is_synthetic_special(league: str, home: str) -> bool:
    """True for non-match weekly aggregate specials (e.g. 'Bundesliga - 10. Hafta (9 Maç)')."""
    low_l = str(league).lower()
    low_h = str(home).lower()
    return "haftalık bahisler" in low_l or "gol atılır" in low_h or bool(re.search(r"\(\d+\s*maç\)", low_h))


def classify_price_tier(status: str, reference: str | None = None) -> str:
    """Transparent 3-tier global price confidence tag: 'keskin', 'global_buro', 'dusuk_guven', 'ozel_bahis', 'fiyatsiz'."""
    if status == "fiyatlandı":
        return "keskin" if is_sharp_source(reference) else "global_buro"
    if status == NESINE_ONLY_STATUS:
        return "dusuk_guven"
    if "özel bahis" in status:
        return "ozel_bahis"
    return "fiyatsiz"


def _source_rank(source: str) -> int:
    if source in SOURCE_RANK:
        return SOURCE_RANK[source]
    if source.startswith(("Pinnacle (", "Betfair (", "Matchbook (")):
        return 2
    if source.startswith(("OddsMath (", "OddsPapi (", "API-Football (")):
        return 3  # soft/mid-tier global books (Marathonbet/1XBET/Bet365/API-Football): above ESPN, below sharp exchanges
    return 9


MAX_CONSENSUS_GAP = 0.08  # two sharp exchanges disagreeing by > 8 pts on one outcome = one of them is wrong


def _gap(x: list[float], y: list[float]) -> float:
    return max(abs(u - v) for u, v in zip(devig(x, method="power").probabilities, devig(y, method="power").probabilities))


def consensus(a: dict, b: dict) -> dict | None:
    """Average the margin-free probabilities of two independent exchanges (1X2, and O/U on the same line)."""
    def _avg(x: list[float], y: list[float]) -> list[float]:
        px = devig(x, method="power").probabilities
        py = devig(y, method="power").probabilities
        return [round(2 / (u + v), 4) for u, v in zip(px, py)]

    if _gap(a["x12"], b["x12"]) > MAX_CONSENSUS_GAP:
        return None  # exchanges contradict each other: do not price this match
    out = dict(a, source=" + ".join(sorted({a["source"].split(" ")[0], b["source"].split(" ")[0]})) + " (borsa)")
    out["x12"] = _avg(a["x12"], b["x12"])
    if a.get("ou") and b.get("ou") and a["ou"][0] == b["ou"][0]:
        # contradictory totals -> use neither (fit on 1X2 only) rather than a possibly wrong line
        out["ou"] = [a["ou"][0], _avg(a["ou"][1], b["ou"][1])] if _gap(a["ou"][1], b["ou"][1]) <= MAX_CONSENSUS_GAP else None
    else:
        out["ou"] = a.get("ou") or b.get("ou")
    if a.get("ah") and b.get("ah") and a["ah"][0] == b["ah"][0]:
        out["ah"] = [a["ah"][0], _avg(a["ah"][1], b["ah"][1])] if _gap(a["ah"][1], b["ah"][1]) <= MAX_CONSENSUS_GAP else None
    else:
        out["ah"] = a.get("ah") or b.get("ah")
    out["markets"] = _merge_direct_markets(a.get("markets"), b.get("markets"))
    out["fetched_utc"] = min(filter(None, [a.get("fetched_utc"), b.get("fetched_utc")]), default=None)
    out["consensus_gap"] = round(_gap(a["x12"], b["x12"]), 4)
    try:
        sc = precision_weighted_consensus([
            BookmakerQuote(bookmaker=a.get("source", "book_a"), odds=tuple(float(x) for x in a["x12"])),
            BookmakerQuote(bookmaker=b.get("source", "book_b"), odds=tuple(float(x) for x in b["x12"])),
        ], method="goto")
        out["consensus_dispersion"] = {
            "max_prob_std": round(max(sc.prob_std), 5),
            "max_kl_divergence": sc.max_kl_divergence,
            "n_books": sc.n_books,
        }
    except ValueError:
        pass
    return out


def _sharp_source_label(refs: list[dict]) -> str:
    """Format a combined sharp source name guaranteed to preserve is_sharp_source() prefix matching."""
    priority = {"Pinnacle": 0, "Smarkets": 1, "Matchbook": 2, "Betfair": 3}
    tokens = sorted(
        {r["source"].split(" ")[0] for r in refs},
        key=lambda t: (priority.get(t, 9), t),
    )
    suffix = " (borsa)" if all(r.get("source") in EXCHANGES for r in refs) else " (keskin konsensüs)"
    return " + ".join(tokens) + suffix


def consensus_multi(refs: list[dict]) -> dict | None:
    """Precision-weighted log-opinion-pool consensus across 2+ sharp references (rejecting contradictions)."""
    if not refs:
        return None
    if len(refs) == 1:
        return refs[0]
    if len(refs) == 2 and all(r.get("source") in EXCHANGES for r in refs):
        return consensus(refs[0], refs[1])
    base = refs[0]
    agreeing = [base]
    max_gap = 0.0
    for other in refs[1:]:
        g = _gap(base["x12"], other["x12"])
        if g > MAX_CONSENSUS_GAP:
            return None
        max_gap = max(max_gap, g)
        agreeing.append(other)
    quotes = [
        BookmakerQuote(bookmaker=r.get("source", f"book_{i}"), odds=tuple(float(x) for x in r["x12"]))
        for i, r in enumerate(agreeing)
    ]
    sc = precision_weighted_consensus(quotes, method="goto")
    out = dict(base)
    out["source"] = _sharp_source_label(agreeing)
    out["x12"] = [round(1.0 / max(p, 1e-6), 4) for p in sc.probabilities]
    # Merge O/U and AH on matching lines via log-pool consensus
    ou_line = next((r["ou"][0] for r in agreeing if r.get("ou")), None)
    if ou_line is not None:
        ou_quotes = [
            BookmakerQuote(bookmaker=r.get("source", f"ou_{i}"), odds=tuple(float(x) for x in r["ou"][1]))
            for i, r in enumerate(agreeing)
            if r.get("ou") and r["ou"][0] == ou_line
        ]
        if len(ou_quotes) >= 2:
            ou_gaps = [_gap(list(ou_quotes[0].odds), list(q.odds)) for q in ou_quotes[1:]]
            if max(ou_gaps) <= MAX_CONSENSUS_GAP:
                sc_ou = precision_weighted_consensus(ou_quotes, method="goto")
                out["ou"] = [ou_line, [round(1.0 / max(p, 1e-6), 4) for p in sc_ou.probabilities]]
            else:
                out["ou"] = None
        elif ou_quotes:
            out["ou"] = [ou_line, list(ou_quotes[0].odds)]
    ah_line = next((r["ah"][0] for r in agreeing if r.get("ah")), None)
    if ah_line is not None:
        ah_quotes = [
            BookmakerQuote(bookmaker=r.get("source", f"ah_{i}"), odds=tuple(float(x) for x in r["ah"][1]))
            for i, r in enumerate(agreeing)
            if r.get("ah") and r["ah"][0] == ah_line
        ]
        if len(ah_quotes) >= 2:
            ah_gaps = [_gap(list(ah_quotes[0].odds), list(q.odds)) for q in ah_quotes[1:]]
            if max(ah_gaps) <= MAX_CONSENSUS_GAP:
                sc_ah = precision_weighted_consensus(ah_quotes, method="goto")
                out["ah"] = [ah_line, [round(1.0 / max(p, 1e-6), 4) for p in sc_ah.probabilities]]
            else:
                out["ah"] = None
        elif ah_quotes:
            out["ah"] = [ah_line, list(ah_quotes[0].odds)]
    merged_mkts: dict = {}
    for r in agreeing:
        merged_mkts = _merge_direct_markets(merged_mkts, r.get("markets"))
    out["markets"] = merged_mkts
    out["fetched_utc"] = min(filter(None, [r.get("fetched_utc") for r in agreeing]), default=None)
    out["consensus_gap"] = round(max_gap, 4)
    out["consensus_dispersion"] = {
        "max_prob_std": round(max(sc.prob_std), 5),
        "max_kl_divergence": sc.max_kl_divergence,
        "n_books": sc.n_books,
    }
    return out


def fuse_sharp_references(event, primary_ref: dict, mine: list[dict], league: str = "") -> tuple[dict | None, bool]:
    """Fuse all agreeing sharp sources (Pinnacle, Smarkets, Matchbook, Betfair, sharp OddsMath) into one consensus.

    Preserves direct exchange derivative markets (BTTS, 1H/2H, O/U lines, corners) even when Pinnacle wins rank 0.
    Returns ``(fused_ref, contradiction)``.
    """
    if not is_sharp_source(primary_ref.get("source")):
        return primary_ref, False
    seen_sources = {primary_ref["source"]}
    sharp_group = [primary_ref]
    # First check direct peer exchanges so exchange-vs-exchange contradictions (>8pp) remain strictly blocked.
    if primary_ref["source"] in EXCHANGES:
        for cand_src in sorted(set(EXCHANGES) - seen_sources):
            other, _ = _match(event, [r for r in mine if r["source"] == cand_src], league=league)
            if other is not None:
                if _gap(primary_ref["x12"], other["x12"]) > MAX_CONSENSUS_GAP:
                    return None, True
                sharp_group.append(other)
                seen_sources.add(cand_src)
    # Then fuse all remaining agreeing sharp sources (e.g. Pinnacle + Smarkets + Matchbook + Betfair + BetInAsia).
    other_sharp_sources = sorted(
        {r["source"] for r in mine if is_sharp_source(r.get("source")) and r["source"] not in seen_sources},
        key=lambda s: (_source_rank(s), s),
    )
    for cand_src in other_sharp_sources:
        other, _ = _match(event, [r for r in mine if r["source"] == cand_src], league=league)
        if other is not None and _gap(primary_ref["x12"], other["x12"]) <= MAX_CONSENSUS_GAP:
            sharp_group.append(other)
            seen_sources.add(cand_src)
    if len(sharp_group) >= 2:
        fused = consensus_multi(sharp_group)
        return fused, fused is None
    return primary_ref, False


def _merge_direct_markets(ma: dict | None, mb: dict | None) -> dict:
    """Merge direct exchange market probability dicts; average agreeing overlaps and drop contradicting ones."""
    if not ma:
        return dict(mb or {})
    if not mb:
        return dict(ma)
    merged: dict[str, dict[str, float]] = {}
    for mkt in set(ma) | set(mb):
        ca, cb = ma.get(mkt), mb.get(mkt)
        if not ca:
            merged[mkt] = dict(cb)
        elif not cb:
            merged[mkt] = dict(ca)
        else:
            out_c: dict[str, float] = {}
            for k in set(ca) | set(cb):
                if k in ca and k in cb:
                    pa, pb = float(ca[k]), float(cb[k])
                    if abs(pa - pb) <= MAX_CONSENSUS_GAP:
                        out_c[k] = round(0.5 * (pa + pb), 5)
                elif k in ca:
                    out_c[k] = float(ca[k])
                else:
                    out_c[k] = float(cb[k])
            if out_c:
                merged[mkt] = out_c
    return merged
GLOBAL_FILE = ROOT / "data" / "global_odds" / "latest" / "references.json"


def global_references(max_age_hours: float = REFERENCE_LOAD_AGE_H) -> tuple[list[dict], str | None]:
    """Sharp references fetched abroad by GitHub Actions (empty if missing or older than max_age_hours).

    Analysis may call this with a large cap to still render a report. Betting paths must refuse
    references older than MAX_PRICE_AGE_H hours.
    """
    if not GLOBAL_FILE.exists():
        return [], None
    data = json.loads(GLOBAL_FILE.read_text(encoding="utf-8"))
    generated = data.get("generated_utc")
    if generated:
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)
        if age.total_seconds() > max_age_hours * 3600:
            return [], generated
    refs = []
    for r in data.get("references", []):
        try:
            refs.append({**r, "kickoff": dt.datetime.fromisoformat(r["kickoff_utc"].replace("Z", "+00:00"))})
        except (KeyError, TypeError, ValueError):
            continue
    return refs, generated


def espn_references(dates: list[str]) -> list[dict]:
    refs = []
    for d in dates:
        for f in fetch_espn_slate(d.replace("-", "")):
            if not f.cur_1x2:
                continue
            refs.append({
                "source": "ESPN (DraftKings/ESPN BET)",
                "home": f.home_team, "away": f.away_team,
                "kickoff": dt.datetime.fromisoformat(f.date_utc.replace("Z", "+00:00")),
                "x12": list(f.cur_1x2),
                "ou": (float(f.ou_line), list(f.ou_odds)) if f.ou_line is not None and f.ou_odds and float(f.ou_line) % 1 == 0.5 else None,
            })
    return refs


# ---- pricing ----------------------------------------------------------------------------
def selection_key(s) -> str:
    """Stable identity of a Nesine selection within its event (for re-checking odds later)."""
    return f"{s.market_id}|{s.name}|{int(bool(s.negate))}"


_SIDE = {"HOME": "1", "DRAW": "0", "AWAY": "2"}
_KG = {"YES": "KG Var", "NO": "KG Yok"}
_OU = {"OVER": "Üst", "UNDER": "Alt"}


def _line(market: str) -> str | None:
    m = re.search(r"(\d+\.5)", market)
    return f"{float(m.group(1)):.1f}" if m else None


def _direct_name(market: str, label: str) -> str | None:
    """Smarkets market name + "CONTRACT_TYPE|contract name" -> canonical selection name (goal_markets syntax)."""
    ctype, _, cname = label.partition("|")
    parts = ctype.split("_")
    mk, line = market.lower(), _line(market)
    if mk.startswith("first half over/under") and "corner" in mk and line and ctype in _OU:
        return f"İY Korner {line} {_OU[ctype]}"
    if mk.startswith("over/under") and "corner" in mk and line and ctype in _OU:
        return f"Korner {line} {_OU[ctype]}"
    if mk.startswith("over/under") and line and ctype in _OU:
        return f"{line} {_OU[ctype]}"
    if mk.startswith("first half over/under") and line and ctype in _OU:
        return f"İY {line} {_OU[ctype]}"
    if mk.startswith("second half over/under") and line and ctype in _OU:
        return f"2Y {line} {_OU[ctype]}"
    if mk == "both teams to score" and ctype in _KG:
        return _KG[ctype]
    if mk == "both teams to score in first half" and ctype in _KG:
        return f"İY {_KG[ctype]}"
    if mk == "both teams to score in second half" and ctype in _KG:
        return f"2Y {_KG[ctype]}"
    if mk == "both teams to score in first half / second half" and ctype == "YES_YES":
        return "İki Yarıda KG Var"
    if mk.startswith("both teams to score and over/under") and line and len(parts) == 2 and parts[0] in _KG and parts[1] in _OU:
        return f"{line} {_OU[parts[1]]} & {_KG[parts[0]]}"
    if mk == "half-time result" and ctype in _SIDE:
        return f"İY {_SIDE[ctype]}"
    if mk == "second half result" and ctype in _SIDE:
        return f"2Y {_SIDE[ctype]}"
    if mk == "half-time/full-time" and len(parts) == 2 and all(x in _SIDE for x in parts):
        return f"İY/MS {_SIDE[parts[0]]}/{_SIDE[parts[1]]}"
    if mk == "odd or even score" and ctype in ("ODD", "EVEN"):
        return "Tek" if ctype == "ODD" else "Çift"
    if mk == "first half odd or even score" and ctype in ("ODD", "EVEN"):
        return "İY Tek" if ctype == "ODD" else "İY Çift"
    if mk == "goal range" and cname.replace(" ", "") in ("0-1", "2-3"):  # Nesine bands 4-5 / 6+ differ from 4-6 / 7+
        return f"{cname.replace(' ', '')} Gol"
    if mk == "winner and both teams to score" and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _KG:
        return f"MS {_SIDE[parts[0]]} & {_KG[parts[1]]}"
    if mk.startswith("winner and over/under") and line and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _OU:
        return f"MS {_SIDE[parts[0]]} & {line} {_OU[parts[1]]}"
    if mk == "first half winner and both teams to score" and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _KG:
        return f"İY {_SIDE[parts[0]]} & İY {_KG[parts[1]]}"
    return None


def direct_probabilities(ref: dict) -> dict[str, float]:
    """Margin-free probabilities quoted directly by the global source for individual selections."""
    out: dict[str, float] = {}
    for market, contracts in (ref.get("markets") or {}).items():
        for label, p in contracts.items():
            name = _direct_name(market, label)
            if name:
                out[name] = float(p)
    return out


PRICED: dict[int, dict] = {}  # Nesine code -> goal distribution + direct quotes of the last analysis (match dossiers)


def _nesine_league_regime_key(league: str) -> str:
    """Map a Turkish Nesine league name to a calibrated tail_goals regime token."""
    s = league.replace("İ", "i").replace("I", "i").lower()
    if is_uncalibrated_competition(league):
        return "wchampions" if ("şamp" in s or "champions" in s) else "women"
    if "u17" in s:
        return "u17"
    if "u19" in s:
        return "u19"
    if "u21" in s:
        return "u21"
    if "bae" in s or "arap körfez" in s:
        return "uae.1"
    if "katar" in s:
        return "qat.1"
    if "avustralya" in s:
        return "aus.1"
    if "abd" in s or "major lig" in s:
        return "usa.1"
    if "asean" in s:
        return "afc.cup"
    if "mısır" in s:
        return "egy.1"
    if "cezayir" in s:
        return "alg.1"
    if "iran" in s:
        return "irn.1"
    if "zambiya" in s:
        return "zam.1"
    if "brezilya" in s:
        return "bra.1"
    if "kolombiya" in s:
        return "col.2"
    return "e0"  # empirically optimal CLUB_REGIME (nu=1.0, alpha=0.0, kappa=0.0)


def shrink_local_probability(prob: float, weight: float = 0.78) -> float:
    """Pull local Nesine-only devig probabilities gently toward 0.50 (fixes Nov 22 -9.8pt local overconfidence)."""
    return float(max(0.01, min(0.99, 0.5 + weight * (float(prob) - 0.5))))


def _korner_model_probability(event, name: str) -> float | None:
    """Total-corner Alt/Üst probability from the walk-forward corner model; None when the selection is not a validated
    banko corner line, the teams are not in the corner archive (same league), or the flag/calibration is off."""
    from quantfoot.markets import korner_banko

    if not korner_banko.banko_name_allowed(name):
        return None
    model = korner_banko.default_model()
    if model is None:
        return None
    return model.probability(getattr(event, "home", ""), getattr(event, "away", ""), name)


def price_event(
    event,
    ref: dict,
    league: str,
    *,
    half_shifts: tuple[float, float] = (0.0, 0.0),
) -> dict:
    is_local_fallback = str(ref.get("source", "")).startswith("Nesine")
    p1x2 = devig(ref["x12"], method="power").probabilities
    quoted = direct_probabilities(ref)

    ou_line, p_over = None, None
    ou_lines_map: dict[float, float] = {}
    if ref.get("ou"):
        ou_line = float(ref["ou"][0])
        p_over = float(devig(ref["ou"][1], method="power").probabilities[0])
        ou_lines_map[ou_line] = p_over
    for line_val in (1.5, 2.5, 3.5, 4.5):
        over_key = f"{line_val:.1f} Üst"
        under_key = f"{line_val:.1f} Alt"
        if over_key in quoted and line_val not in ou_lines_map:
            ou_lines_map[line_val] = float(quoted[over_key])
        elif under_key in quoted and line_val not in ou_lines_map:
            ou_lines_map[line_val] = max(0.0, min(1.0, 1.0 - float(quoted[under_key])))
    ou_lines = sorted(ou_lines_map.items())
    p_btts_direct = quoted.get("KG Var")
    if p_btts_direct is None and "KG Yok" in quoted:
        p_btts_direct = max(0.0, min(1.0, 1.0 - float(quoted["KG Yok"])))

    ah_line, p_ah_home = None, None
    ah_lines: list[tuple[float, float]] = []
    if ref.get("ah") and isinstance(ref["ah"], (list, tuple)) and len(ref["ah"]) == 2:
        try:
            raw_ah_line = float(ref["ah"][0])
            raw_ah_odds = [float(x) for x in ref["ah"][1]]
            if len(raw_ah_odds) == 2 and min(raw_ah_odds) > 1.01:
                ah_line = raw_ah_line
                p_ah_home = float(devig(raw_ah_odds, method="power").probabilities[0])
                if 0.01 < p_ah_home < 0.99:
                    ah_lines.append((ah_line, p_ah_home))
        except (TypeError, ValueError):
            ah_line, p_ah_home = None, None

    regime_key = _nesine_league_regime_key(league)
    nu, alpha, kappa = league_tail_regime(regime_key)
    mu_h, mu_a, fit_mat = fit_tail_rates_from_markets(
        p_1x2=p1x2,
        ou_lines=ou_lines or None,
        ah_lines=ah_lines or None,
        p_btts=p_btts_direct,
        seed_rates=(1.45, 1.15),
        alpha_nb=alpha,
        shared_kappa=kappa,
        com_nu=nu,
        fund_weight=0.0,
    )
    # Two goal rates cannot reproduce 1X2 + O/U (+ AH / KG) at once; rake the score matrix onto the quotes so every
    # derived market agrees with them (21 Nov audit: the unraked joint under-priced draws by 0.8 pp; v8 adds |AH|>=0.75
    # goal-margin raking so Hnd(-1/+1) and multi-goal margins reflect sharp Asian Handicap quotes directly).
    ft_mat = rake_score_matrix_to_markets(fit_mat, p_1x2=p1x2, ou_lines=ou_lines, p_btts=p_btts_direct,
                                          ah_lines=ah_lines or None, margin_tilt=MARGIN_TILT)
    # League's own first-half goal share (data/lig_yari_oranlari.csv) + 1Y urgency shifts: this season's team half
    # split (build_half_split_view) when it has evidence, else the club's long-run 1Y/2Y DNA. Never both, so the same
    # tendency is not counted twice. Club DNA comeback multipliers always apply.
    dna_h, dna_a, club_mults = club_omni_adjustments(getattr(event, "home", None), getattr(event, "away", None))
    season = (float(half_shifts[0]), float(half_shifts[1]))
    h_shift, a_shift = season if any(abs(x) > 1e-9 for x in season) else (dna_h, dna_a)
    joint = compute_omni_markets(mu_h, mu_a, league=regime_key, ft_matrix=ft_mat,
                                 first_half_share=league_first_half_share(league),
                                 home_1h_urgency_shift=h_shift, away_1h_urgency_shift=a_shift,
                                 state_mults=club_mults).joint
    timing = GoalTimingModel.from_joint(joint).markets()["İlk Golü Atan Takım"]

    exact_direct: dict[str, float] = {
        "MS 1": float(p1x2[0]),
        "MS 0": float(p1x2[1]),
        "MS X": float(p1x2[1]),
        "MS 2": float(p1x2[2]),
        "ÇŞ 10": float(p1x2[0] + p1x2[1]),
        "ÇŞ 1X": float(p1x2[0] + p1x2[1]),
        "ÇŞ 12": float(p1x2[0] + p1x2[2]),
        "ÇŞ 02": float(p1x2[1] + p1x2[2]),
        "ÇŞ X2": float(p1x2[1] + p1x2[2]),
    }
    if ou_line is not None and p_over is not None:
        exact_direct[f"{ou_line:.1f} Üst"] = p_over
        exact_direct[f"{ou_line:.1f} Alt"] = 1.0 - p_over

    inputs = {"MS 1", "MS 0", "MS X", "MS 2", "ÇŞ 10", "ÇŞ 1X", "ÇŞ 12", "ÇŞ 02", "ÇŞ X2"} | (
        {f"{ou_line:.1f} Üst", f"{ou_line:.1f} Alt"} if ou_line is not None else set()
    )
    PRICED[event.code] = {"joint": joint, "timing": timing, "quoted": quoted, "inputs": inputs}
    derivatives_ok = not is_uncalibrated_competition(league)
    # Without any quoted total the goal level is extrapolated from 1X2 alone (it overshoots for big favourites):
    # then only pure result markets are priced from the model.
    totals_known = bool(ou_lines) or any("Üst" in k or "Alt" in k for k in quoted)
    rows = []
    for s in event.selections:
        direct = s.name in exact_direct or s.name in quoted
        if not direct and not derivatives_ok:
            continue  # derivative distribution not calibrated for this competition
        if not direct and not totals_known and not (s.name.startswith(("MS ", "ÇŞ ")) and "&" not in s.name):
            continue  # goal-count market with no global total to anchor it
        corner_model = False
        if "Korner" in s.name and s.name not in quoted:
            # Corners are never extrapolated from the goal grid. Total-corner Alt/Üst may be priced by the validated
            # walk-forward corner model (markets/korner_banko.py, banko family); anything else stays unpriced.
            p = None if s.negate else _korner_model_probability(event, s.name)
            if p is None:
                continue
            corner_model = True
        elif s.name in quoted:
            p = quoted[s.name]
        elif s.name in exact_direct:
            p = exact_direct[s.name]
        elif s.name.startswith("İlk Gol"):
            p = timing.get(s.name)
        else:
            try:
                p = blend_with_league(s.name, goal_probability(s.name, joint), league)
                # GFI ince-lig öncülü (settings.GFI_PRIORS_ENABLED, varsayılan kapalı; kapalıyken p değişmez)
                p = gfi_priors.blend(s.name, p, league, getattr(event, "home", ""), getattr(event, "away", ""))
                # Son-120-gün form öncülü (settings.RECENT_FORM_ENABLED, varsayılan kapalı; kapalıyken p değişmez)
                p = form_priors.blend(s.name, p, league, getattr(event, "home", ""), getattr(event, "away", ""),
                                      getattr(event, "kickoff", None))
            except KeyError:
                continue  # keep the offer in the inventory even when the model cannot price it
        if p is None:
            continue
        if s.negate:
            p = 1.0 - p
        if is_local_fallback and p > 0.50 and not corner_model:
            p = shrink_local_probability(p, weight=0.78)
        # Nesine templates ("{{handicap}} Gol Alt/Üst" / "{{SOV}} Üst"): show the resolved name instead.
        market = s.market_title.replace("{{handicap}} ", "").replace(" ({{handicap}})", "")
        label = s.name if "{{" in s.label or "{{" in s.market_title else s.label
        rows.append({"key": selection_key(s), "market": market, "selection": label, "name": s.name if not s.negate else f"DEĞİL({s.name})",
                     "odds": s.odds, "fair_prob": round(p, 5), "fair_odds": round(1 / p, 3) if p > 1e-9 else None,
                     "ev": round(p * s.odds - 1.0, 4), "mbs": s.mbs, "direct": direct,
                     **({"korner_modeli": True} if corner_model else {})})
    rows.sort(key=lambda r: r["ev"], reverse=True)
    nesine_ms = [event.odds_of(f"MS {c}") for c in "102"]
    margin = sum(1 / o for o in nesine_ms) - 1 if all(nesine_ms) else None
    synthetic_coherence = None
    if all(nesine_ms):
        dc_map = {
            lbl: val
            for lbl, src_lbl in (("ÇŞ 1X", "ÇŞ 10"), ("ÇŞ 12", "ÇŞ 12"), ("ÇŞ X2", "ÇŞ 02"))
            if (val := (event.odds_of(src_lbl) or event.odds_of(lbl)))
        }
        if dc_map:
            try:
                coh = check_synthetic_coherence(nesine_ms, double_chance=dc_map)
                synthetic_coherence = {
                    "synthetic_dc_odds": coh.synthetic_dc_odds,
                    "cheapest_equivalents": coh.cheapest_equivalents,
                }
            except (ValueError, ZeroDivisionError):
                synthetic_coherence = None
    return {"mu_home": round(float(mu_h), 3), "mu_away": round(float(mu_a), 3), "reference": ref["source"],
            "ref_fetched_utc": ref.get("fetched_utc"), "consensus_gap": ref.get("consensus_gap"),
            "consensus_dispersion": ref.get("consensus_dispersion"),
            "synthetic_coherence": synthetic_coherence,
            "ref_1x2": ref["x12"], "ref_ou": ref.get("ou"), "ref_ah": ref.get("ah"),
            "steam_1x2": ref.get("steam_1x2"), "fair_1x2": [round(float(x), 4) for x in p1x2],
            "nesine_ms_margin": None if margin is None else round(margin, 4), "derivatives_priced": derivatives_ok, "selections": rows}


MAX_PAIRING_GAP = 0.15  # Nesine's own 1X2, devigged, vs the reference: a bigger gap means a wrong pairing


def _consistent(event, ref: dict) -> bool:
    """Sanity check of a name/time pairing: Nesine's 1X2 must tell roughly the same story as the reference."""
    nes = [event.odds_of(f"MS {c}") for c in "102"]
    if not all(nes) or not ref.get("x12"):
        return True  # nothing to compare
    pn = devig(nes, method="power").probabilities
    pr = devig(ref["x12"], method="power").probabilities
    return max(abs(a - b) for a, b in zip(pn, pr)) <= MAX_PAIRING_GAP


def _owners(events: list, refs: list[dict], leagues: dict | None = None) -> dict[int, object]:
    """Each reference belongs to the one Nesine event it resembles most (no reference priced twice)."""
    best: dict[int, tuple[float, object]] = {}
    for e in events:
        lg = (leagues or {}).get(getattr(e, "league_code", None), "")
        ev_w = is_women_match(lg, e.home, e.away)
        ev_y = is_youth_or_reserve_match(lg, e.home, e.away)
        for r in refs:
            if abs((r["kickoff"] - e.kickoff).total_seconds()) > 3 * 3600:
                continue
            if is_women_match(r.get("league", ""), r["home"], r["away"]) != ev_w:
                continue
            if is_youth_or_reserve_match(r.get("league", ""), r["home"], r["away"]) != ev_y:
                continue
            sc = (_sim(e.home, r["home"]) + _sim(e.away, r["away"])) / 2
            if sc > best.get(id(r), (0.0, None))[0]:
                best[id(r)] = (sc, e.code)
    return {k: v[1] for k, v in best.items()}


def _absent(r: dict, side: str) -> str:
    """Key absences for the report (Premier League official list); '-' when unknown."""
    a = (r.get("absences") or {}).get(side)
    if not a:
        return "-"
    key = []
    for p in a["players"]:
        if p["key"]:
            chance = f" %{p['chance']}" if p["chance"] not in (None, 0) else ""
            key.append(f"{p['name']} ({p['status']}{chance})")
    return ", ".join(key) or "kilit eksik yok"


def load_user_absences(folder: Path = ROOT / "reports") -> tuple[dict[int, dict], str | None]:
    """Injury / suspension file the user supplies (reports/haftalik_sakatlik_ceza_*.json, newest wins),
    keyed by Nesine event code. The system never fetches this data itself; it only reads the user's file."""
    files = sorted(folder.glob("haftalik_sakatlik_ceza_*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        return {}, None
    try:
        data = json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, None
    out = {int(m["code"]): m["absences"] for m in data.get("matches", [])
           if (m.get("absences") or {}).get("covered") and m.get("code") is not None}
    label = f"{files[-1].name} ({data.get('generated_tsi', '?')[:16].replace('T', ' ')})"
    try:
        age_h = (dt.datetime.now(TSI) - dt.datetime.fromisoformat(data["generated_tsi"])).total_seconds() / 3600
        if age_h > 24:
            label += f" — ⚠ {age_h / 24:.1f} gün önce üretildi, sakatlık/ceza bilgisi eskimiş olabilir"
    except (KeyError, ValueError, TypeError):
        pass
    return out, label


NESINE_ONLY_STATUS = "düşük güven — global fiyat yok, Nesine oranından (kupona alınmaz)"


def nesine_fallback_reference(event) -> dict | None:
    """Last-resort reference for matches no global source prices: Nesine's own 1X2 (+ O/U 2.5).
    The margin is removed later by the same devig as for global prices; the result is low-confidence."""
    x12 = [event.odds_of(f"MS {c}") for c in "102"]
    if not all(x12):
        return None
    ou = [event.odds_of("2.5 Üst"), event.odds_of("2.5 Alt")]
    return {"source": "Nesine (yerel, düşük güven)", "x12": x12, "ou": [2.5, ou] if all(ou) else None}


def attach_research(out: list[dict], events: list, day: dt.date, sharp_generated: str | None,
                    *, all_upcoming: bool = False) -> None:
    """Add ESPN research (form, table, rest, line-ups, absences) to priced matches; flag stale prices."""
    pool = []
    for d in (day - dt.timedelta(days=1), day, day + dt.timedelta(days=1)):
        pool += [{**x, "source": "ESPN"} for x in espn_events(d.strftime("%Y%m%d"))]
    by_code = {e.code: e for e in events}
    jobs = {}
    now = dt.datetime.now(TSI)
    for rec in out:
        event = by_code[rec["code"]]
        priced = rec.get("status") in ("fiyatlandı", NESINE_ONLY_STATUS)
        extra = all_upcoming and rec.get("price_tier") != "ozel_bahis" and event.kickoff > now
        if not (priced or extra):
            continue
        hit, _ = _match(event, pool)
        if hit:
            jobs[rec["code"]] = hit["id"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(zip(jobs, ex.map(research, jobs.values())))
    gen = dt.datetime.fromisoformat(sharp_generated) if sharp_generated else None
    for rec in out:
        res = results.get(rec["code"])
        if not res:
            continue
        if rec.get("ref_fetched_utc"):
            price_time = dt.datetime.fromisoformat(rec["ref_fetched_utc"])
        else:  # ESPN references are fetched live, now
            price_time = None if str(rec.get("reference") or "").startswith("ESPN") else gen
        flags = staleness_flags(res, price_time)
        res["motivation"] = {side: motivation(t, res.get("league_slug")) for side, t in res["teams"].items()}
        from quantfoot.markets.lineup_xg import assess_motivation_risk
        mot_risk = assess_motivation_risk(res["motivation"].get("home"), res["motivation"].get("away"))
        res["motivation_regime"] = {
            "regime": mot_risk.regime,
            "dead_rubber": mot_risk.dead_rubber,
            "one_sided": mot_risk.one_sided,
            "high_stakes_tight": mot_risk.high_stakes_tight,
        }
        for mf in mot_risk.flags:
            if mf not in flags:
                flags.append(mf)
        res["flags"] = flags
        rec["research"] = res
        # Important absence in a line-up published after our price was fetched -> keep out of coupons.
        rec["research_block"] = bool(flags) and flags[-1].startswith("global fiyat")
    # User-supplied injury / suspension file, matched on the Nesine event code.
    user_abs, user_src = load_user_absences()
    for rec in out:
        a = user_abs.get(int(rec["code"]))
        if a:
            res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
            res["user_absences"] = {"source": user_src, **a}
    # Premier League: official injury / suspension list (already priced by the market; shown as context).
    fpl = None
    for rec in out:
        if rec.get("status") != "fiyatlandı" or rec.get("league") != "İngiltere Premier Lig":
            continue
        fpl = fpl if fpl is not None else fpl_availability()
        absences = {}
        for side, name in (("home", rec["home"]), ("away", rec["away"])):
            team = max(fpl, key=lambda t: _sim(name, t), default=None)
            if team and _sim(name, team) >= 0.6:
                absences[side] = {"team": team, "players": fpl[team]}
        if absences:
            rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})["absences"] = absences

    # FotMob (gerçek xG / şut / hakem / son dakika onaylı ilk 11): ESPN eksik veya maç <= 2 saat ise önbellekli zenginleştir.
    if fotmob.enabled():
        try:
            fm = fotmob.FotMob(CachedHttp(ROOT / "data" / "cache" / "fotmob"), delay_s=0.45)
            fm_day = fm.matches_on(day, ttl_s=1800)
            fm_list = fotmob.parse_matches(fm_day) if fm_day else []
            if fm_list:
                fetched_fm = 0
                for rec in out:
                    if fetched_fm >= 45 or rec.get("price_tier") == "ozel_bahis":
                        continue
                    event = by_code.get(rec["code"])
                    if not event:
                        continue
                    has_espn = bool((rec.get("research") or {}).get("teams"))
                    mins_to_ko = (event.kickoff - now).total_seconds() / 60.0
                    near_kickoff = -10.0 <= mins_to_ko <= 120.0
                    if has_espn and not near_kickoff:
                        continue
                    hit = fotmob.find_match(fm_list, rec["home"], rec["away"], min_score=0.72)
                    if not hit or not hit.get("id"):
                        continue
                    raw_det = fm.details(hit["id"], ttl_s=900 if near_kickoff else 3600)
                    if not raw_det:
                        continue
                    fetched_fm += 1
                    parsed = fotmob.parse_details(raw_det)
                    res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
                    res["fotmob"] = parsed
                    if parsed.get("lineup_type") == "official":
                        for side in ("home", "away"):
                            lu_side = parsed.get(f"{side}_lineup") or {}
                            if lu_side.get("starters"):
                                t_side = res["teams"].setdefault(side, {"name": rec[side]})
                                t_side["lineup_announced"] = True
                                if lu_side.get("unavailable"):
                                    t_side.setdefault("fotmob_unavailable", lu_side["unavailable"])
                        tag = "FotMob: resmi ilk 11 açıklandı"
                        if tag not in res["flags"]:
                            res["flags"].append(tag)
        except Exception:
            pass  # FotMob erişilemez / zaman aşımı olursa ana bülteni bozma


def _steam_flag(steam_1x2: list[float] | None, threshold: float = 0.05) -> str | None:
    """Format a sharp opening-to-live probability move warning when |Δp| >= threshold."""
    if not steam_1x2 or len(steam_1x2) != 3:
        return None
    if max(abs(float(x)) for x in steam_1x2) < threshold:
        return None
    labels = ("Ev", "Ber", "Dep")
    parts = [f"{lbl} {val * 100:+.1f}p" for lbl, val in zip(labels, steam_1x2) if abs(val) >= 0.03]
    return ("⚡ Sharp steam: " + ", ".join(parts)) if parts else None


def analyze_day(
    day: dt.date,
    verbose: bool = True,
    with_research: bool = True,
    *,
    use_oddsmath: bool = True,
    use_tm: bool = False,
    use_weather: bool = True,
    all_upcoming_research: bool = False,
) -> tuple[list[dict], dict, list]:
    """Fetch the live Nesine bulletin and price every match of `day` against the best global reference.

    Returns (match records, raw bulletin payload, parsed events). Used by main() and nesine_kupon.py.
    """
    nxt = day + dt.timedelta(days=1)
    payload = fetch_bulletin()
    leagues = league_names(payload)
    # Betting day = 07:00–07:00 TSİ, so consecutive days never share a match.
    date = day.isoformat()
    events = [e for e in parse_bulletin(payload) if betting_day(e.kickoff) == date]
    real_events = [e for e in events if not is_synthetic_special(leagues.get(e.league_code, ""), e.home)]
    sharp, generated = global_references()
    espn = espn_references([day.isoformat(), nxt.isoformat()])
    om_refs = (
        fetch_oddsmath_references(real_events, [day.isoformat(), nxt.isoformat()], league_lookup=leagues)
        if use_oddsmath
        else []
    )
    op_refs = fetch_oddspapi_references([day.isoformat(), nxt.isoformat()])
    toa_refs = fetch_the_odds_api_references(cache_dir=ROOT / "data" / "cache" / "the_odds_api")
    af_refs = fetch_api_football_references([day.isoformat(), nxt.isoformat()], budget=default_budget(),
                                            cache_dir=API_BUDGET_DIR)  # kota: data/cache/api_football/butce_<gün>.json
    if verbose:
        n_spec = len(events) - len(real_events)
        spec_s = f" (+{n_spec} özel bahis)" if n_spec else ""
        print(f"Nesine {day}: {len(real_events)} futbol maçı{spec_s}")
        print(f"Global (Pinnacle/Smarkets/Betfair): {len(sharp)} referans (oluşturulma {generated or 'yok'})")
        if generated:
            try:
                ref_age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)).total_seconds() / 3600.0
                if ref_age > 24.0:
                    print(f"⚠ data/global_odds/latest/references.json {ref_age:.1f} saat eski — GitHub Actions global-odds tazelenmesi önerilir")
            except ValueError:
                pass
        if use_oddsmath:
            print(f"OddsMath (BetInAsia/sharp + global büro + steam): {len(om_refs)} maçta canlı oran bulundu")
        if op_refs:
            print(f"OddsPapi (API): {len(op_refs)} maçta oran bulundu")
        if toa_refs:
            print(f"The Odds API (Pinnacle/Betfair/Matchbook): {len(toa_refs)} maçta canlı keskin oran bulundu")
        if af_refs:
            print(f"API-Football (1100+ lig): {len(af_refs)} maçta oran bulundu")
        print(f"ESPN: {len(espn)} maçta oran bulundu")
    refs = sharp + toa_refs + op_refs + om_refs + af_refs + espn
    owner = _owners(real_events, refs, leagues=leagues)
    out = []
    for e in sorted(events, key=lambda x: x.kickoff):
        league = leagues.get(e.league_code, str(e.league_code))
        rec = {"code": e.code, "kickoff": e.kickoff.strftime("%Y-%m-%d %H:%M"), "kickoff_iso": e.kickoff.isoformat(),
               "league": league, "home": e.home, "away": e.away,
               "nesine_ms": [e.odds_of(f"MS {c}") for c in "102"], "n_nesine_selections": len(e.selections)}
        rec["offered_selections"] = [
            {"key": selection_key(s), "name": s.name if not s.negate else f"DEĞİL({s.name})",
             "market": s.market_title, "selection": s.label, "odds": s.odds}
            for s in e.selections
        ]
        rec["untranslated_selections"] = e.untranslated
        if is_synthetic_special(league, e.home):
            rec["status"] = "özel bahis (maç değil) — fiyatlanmadı"
            rec["price_tier"] = "ozel_bahis"
            out.append(rec)
            continue
        ref, score = None, 0.0
        mine = [r for r in refs if owner.get(id(r)) == e.code and _consistent(e, r)]
        all_ranks = sorted({_source_rank(r["source"]) for r in mine})
        for rank in all_ranks:  # best source first
            pool = [r for r in mine if _source_rank(r["source"]) == rank]
            ref, score = _match(e, pool, league=league) if pool else (None, 0.0)
            if ref is not None:
                break
        contradiction = False
        if ref is not None and is_sharp_source(ref["source"]):
            ref, contradiction = fuse_sharp_references(e, ref, mine, league=league)
        # Carry OddsMath live steam_1x2 even when GitHub Pinnacle/Smarkets won source priority
        if ref is not None and not ref.get("steam_1x2") and om_refs:
            om_mine = [r for r in mine if r["source"].startswith("OddsMath (")]
            om_hit, _ = _match(e, om_mine, league=league) if om_mine else (None, 0.0)
            if om_hit and om_hit.get("steam_1x2"):
                ref = {**ref, "steam_1x2": om_hit["steam_1x2"]}
        hv = build_half_split_view(league, e.home, e.away, as_of=day)
        h_shifts = (hv.home_1h_urgency_shift, hv.away_1h_urgency_shift) if hv is not None else (0.0, 0.0)
        if ref is None:
            rec["status"] = ("borsalar birbiriyle çelişiyor (> 8 puan) — fiyatlanmadı" if contradiction
                             else "global referans bulunamadı — fiyatlanmadı")
            local = nesine_fallback_reference(e)
            if local is not None and not contradiction:
                # Display-only estimate from Nesine's own margin-free odds: never used in coupons
                # (candidates() accepts only status 'fiyatlandı').
                rec.update(**price_event(e, local, league, half_shifts=h_shifts))
                rec["status"] = NESINE_ONLY_STATUS
            rec["price_tier"] = classify_price_tier(rec["status"], rec.get("reference"))
        else:
            rec.update(match_score=round(score, 2), ref_match=f"{ref['home']} - {ref['away']}", **price_event(e, ref, league, half_shifts=h_shifts))
            rec["status"] = "fiyatlandı"
            rec["price_tier"] = classify_price_tier(rec["status"], rec.get("reference"))
        out.append(rec)
    if with_research:
        if all_upcoming_research:
            attach_research(out, events, day, generated, all_upcoming=True)
        else:
            attach_research(out, events, day, generated)
    if use_tm:
        tm_map = fetch_matchday_absences([m for m in out if m.get("price_tier") != "ozel_bahis"])
        if not tm_map:
            # Preserve same-day Transfermarkt data already captured earlier (e.g. when a cloud datacenter IP gets throttled)
            prev_path = DAILY / day.isoformat() / "nesine_global.json"
            if prev_path.exists():
                try:
                    prev_data = json.loads(prev_path.read_text(encoding="utf-8"))
                    for pm in prev_data.get("matches") or []:
                        ptm = (pm.get("research") or {}).get("tm_absences")
                        if ptm and pm.get("code") is not None:
                            tm_map[int(pm["code"])] = ptm
                except (OSError, json.JSONDecodeError, ValueError):
                    pass
        if verbose:
            print(f"Transfermarkt (2026/27 sakat/cezalı + puan durumu): {len(tm_map)}/{len(real_events)} maç eşleşti")
        for rec in out:
            tm_rec = tm_map.get(rec["code"]) or tm_map.get(int(rec["code"]))
            if tm_rec:
                res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
                res["tm_absences"] = tm_rec
                for al in tm_rec.get("alerts") or []:
                    tag = f"TM: {al}"
                    if tag not in res["flags"]:
                        res["flags"].append(tag)
    if web_research.enabled():
        # Maç başına web-araştırma (yalnız kupona aday maçlar): form, puan durumu, xG, sakat/ilk 11, hoca değişikliği.
        # Bilgi kaydı (research["web"]); olasılığa dokunmaz. Hata/zaman aşımı ana bülteni bozmaz.
        try:
            ws = web_research.attach(out, day, budget_s=240.0)
            if verbose:
                print(f"Web-araştırma: {ws.get('islenen', 0)}/{ws.get('aday', 0)} aday maç, "
                      f"{ws.get('sure_sn')} sn (maç başı {ws.get('mac_basi_sn')} sn)")
        except Exception as e:  # noqa: BLE001
            print(f"Web-araştırma atlandı: {type(e).__name__}")
    for rec in out:
        sf = _steam_flag(rec.get("steam_1x2"))
        if sf:
            res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
            if sf not in res["flags"]:
                res["flags"].append(sf)
    if use_weather:
        weather_map = fetch_matchday_weather([m for m in out if m.get("price_tier") != "ozel_bahis"])
        for rec in out:
            w = weather_map.get(rec["code"])
            if w:
                res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
                res["weather"] = w
                if w.get("flag") and w["flag"] not in res["flags"]:
                    res["flags"].append(w["flag"])
    for rec in out:
        if rec.get("price_tier") != "ozel_bahis":
            enrich_match_record(rec, as_of=day)
    return out, payload, events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=betting_day())
    ap.add_argument("--min-ev", type=float, default=0.0)
    ap.add_argument("--haftalik", action="store_true",
                    help="Yalnız kullanıcı isterse: haftalık tahmin raporu (tahminler/<ai>/hafta/); --hafta 7 ile birlikte")
    ap.add_argument("--hafta", type=int, default=1, help="Kaç gün analiz edilsin (ör. 7: bugünden itibaren bütün hafta)")
    ap.add_argument("--oddsmath", action="store_true", help="OddsMath referanslarını açıkça etkinleştir (varsayılan açık)")
    ap.add_argument("--no-oddsmath", action="store_true", help="OddsMath canlı referans/steam çekimini kapat")
    ap.add_argument("--tm", action="store_true", help="Transfermarkt 2026/27 sakat/cezalı çekimini aç (varsayılan: kapalı, kullanım koşulları)")
    ap.add_argument("--no-tm", action="store_true", help="Transfermarkt çekimini kapat (varsayılan davranış; açıkça geçmek için yeterlidir)")
    ap.add_argument("--tum-istatistikler", action="store_true", help="Fiyatlanmamış başlamamış maçlarda da takım verisi ara")
    ap.add_argument("--no-weather", action="store_true", help="Open-Meteo maç saati şiddetli hava kontrolünü kapat")
    args = ap.parse_args()
    start = dt.date.fromisoformat(args.date)
    week = []
    for k in range(args.hafta):
        day = (start + dt.timedelta(days=k)).isoformat()
        # Multi-day scans run OddsMath for today/tomorrow and TM/weather for today unless explicitly forced, keeping hourly runs fast.
        run_om = (not args.no_oddsmath) and (args.oddsmath or args.hafta == 1 or k <= 1)
        run_tm = bool(args.tm) and not args.no_tm
        run_wx = (not args.no_weather) and (args.hafta == 1 or k == 0)
        out, payload, events = analyze_day(
            dt.date.fromisoformat(day),
            verbose=args.hafta == 1,
            use_oddsmath=run_om,
            use_tm=run_tm,
            use_weather=run_wx,
            **({"all_upcoming_research": True} if args.tum_istatistikler else {}),
        )
        write_report(day, out, payload, events, args.min_ev)
        week.append((day, out))
    if args.haftalik:  # weekly prediction only on request (user, 20 Nov: "ben istersem yaparsın")
        write_week(start, week, args.min_ev)


def write_week(start: dt.date, week: list[tuple[str, list[dict]]], min_ev: float) -> None:
    """Weekly prediction report, ONLY when the user asks (--haftalik): coverage per day and every plausible
    value selection of the week, written to the AI's own private folder (tahminler/<ai>/hafta/)."""
    lines = [f"# Nesine haftalık analiz ({start} – {week[-1][0]})", "",
             "| Gün | Nesine maçı | Global fiyatlı | Düşük güven (Nesine) | Doğrudan borsa seçimi | Araştırma | Uyarılı |",
             "|---|---|---|---|---|---|---|"]
    value = []
    for day, out in week:
        priced = [m for m in out if m["status"] == "fiyatlandı"]
        direct = sum(1 for m in priced for s in m["selections"] if s.get("direct"))
        local = sum(1 for m in out if m["status"] == NESINE_ONLY_STATUS)
        lines.append(f"| {day} | {len(out)} | {len(priced)} | {local} | {direct} | {sum(1 for m in out if m.get('research'))} | "
                     f"{sum(1 for m in out if (m.get('research') or {}).get('flags'))} |")
        value += [(m, s) for m in priced for s in m["selections"] if min_ev <= s["ev"] <= MAX_PLAUSIBLE_EV]
    value.sort(key=lambda x: x[1]["ev"], reverse=True)
    lines += ["", "## Haftanın değerli seçimleri (Nesine oranı > global adil oran)", "",
              "| Gün saat | Maç | Pazar | Seçim | Nesine | Global olasılık | EV | Fiyat | Referans |", "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {m['kickoff']} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
              f"%{s['fair_prob'] * 100:.1f} | {s['ev']:+.1%} | {'doğrudan' if s.get('direct') else 'model'} | "
              f"{m['reference'].split(' (')[0]} |" for m, s in value[:100]] or ["_Yok._"]
    path = DAILY / "hafta" / f"{start}_nesine_hafta.md"  # the AI's own folder (user rule, 20 Nov)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {path}")



def _side_rows(r: dict, side: str) -> dict[str, str]:
    t = (r.get("teams") or {}).get(side) or {}
    tab, sea, prof = t.get("table") or {}, t.get("season") or {}, t.get("profile") or {}
    row: dict[str, str] = {"Takım": t.get("name") or "-", "Son 5 maç": " · ".join(t.get("last5") or []) or "-",
                           "Form": t.get("form") or "-", "Dinlenme (gün)": str(t.get("rest_days", "-"))}
    if tab.get("rank"):
        row["Puan durumu"] = (f"{int(tab['rank'])}./{tab['size']} · {int(tab.get('points') or 0)} p · "
                              f"{int(tab.get('wins') or 0)}G {int(tab.get('draws') or 0)}B {int(tab.get('losses') or 0)}M")
    if sea.get("goals_for") and sea.get("played"):
        n = float(sea["played"]) or 1.0
        row["Sezon gol (at / ye)"] = (f"{sea['goals_for']} / {sea['goals_against']} "
                                     f"({float(sea['goals_for']) / n:.2f} / {float(sea['goals_against']) / n:.2f} maç başı)")
    if prof.get("top_scorers"):
        row["Golcüler"] = ", ".join(f"{p['name']} {p['goals']}G {p['assists']}A" for p in prof["top_scorers"])
    if prof.get("top_assists"):
        row["Asist yapanlar"] = ", ".join(f"{p['name']} {p['assists']}A {p['goals']}G" for p in prof["top_assists"])
    gk = prof.get("goalkeeper")
    if gk:
        sp = f"%{gk['save_pct'] * 100:.0f} kurtarış" if gk.get("save_pct") is not None else "kurtarış verisi yok"
        row["Kaleci"] = f"{gk['name']} ({gk['apps']} maç, {sp}, maç başı {gk['conceded_per_game']} gol)"
    if prof.get("cards"):
        row["Kart riski"] = ", ".join(f"{p['name']} {p['yellow']}S" + (f" {p['red']}K" if p["red"] else "")
                                      for p in prof["cards"])
    for label, value in (t.get("team_stats") or {}).items():
        row[label] = value
    row["Eksikler"] = _absent(r, side)
    ua = (r.get("user_absences") or {}).get(side) or {}
    if ua.get("injuries"):
        row["Sakatlar (kullanıcı dosyası)"] = "; ".join(
            f"{p['player']} ({p.get('pos') or '?'}, {p.get('reason') or 'sakat'}" + (f", dönüş {p['until']}" if p.get("until") else "") + ")"
            for p in ua["injuries"][:8])
    if ua.get("cards"):
        row["Cezalılar (kullanıcı dosyası)"] = "; ".join(f"{p['player']} ({p.get('pos') or '?'}, {p.get('reason') or 'cezalı'})"
                                                        for p in ua["cards"][:6])
    if ua.get("gk_out"):
        row["Kaleci"] = (row.get("Kaleci", "") + " · ⚠ kullanıcı dosyası: kaleci eksik").strip(" ·")
    tm = (r.get("tm_absences") or {}).get(side) or {}
    if tm:
        if tm.get("rank") and "Puan durumu" not in row:
            row["Puan durumu (TM)"] = f"{tm['rank']}. · {tm.get('points', '-')} p ({tm.get('played', '-')} maç, av {tm.get('gd', '-')})"
        row["Transfermarkt (2026/27 eksikler)"] = format_tm_absence_brief(tm)
        if tm.get("top_scorers") and "Golcüler" not in row:
            row["Golcüler (TM)"] = ", ".join(f"{p['name']} {p['goals']}G {p['assists']}A" for p in tm["top_scorers"])
        if tm.get("gk1_out"):
            row["Kaleci"] = (row.get("Kaleci", "") + " · ⚠ TM: 1. kaleci eksik").strip(" ·")
    if t.get("news_flags"):
        row["Haber (sakatlık/ceza)"] = " · ".join(t["news_flags"])
    if t.get("likely_absent"):
        row["Muhtemel eksikler (son kadrolardan)"] = "; ".join(f"{p['name']}: {p['reason']}" for p in t["likely_absent"][:6])
    if t.get("lineup_announced"):
        miss = [p["name"] for p in t.get("missing_regulars") or []]
        row["İlk 11"] = "açıklandı" + (f"; düzenli oyunculardan yok: {', '.join(miss)}" if miss else "")
    rec_pf = t.get("recent_player_form") or {}
    if rec_pf.get("hot_players"):
        row["Son 5 maç formda oyuncular"] = ", ".join(
            f"{p['name']} ({p['goals']}G {p['assists']}A, {p['sot']} isabetli şut)"
            for p in rec_pf["hot_players"][:4]
        )
    if rec_pf.get("recent_gk"):
        rgk = rec_pf["recent_gk"]
        rsp = f"%{rgk['save_pct'] * 100:.0f} kurtarış" if rgk.get("save_pct") is not None else "kurtarış verisi yok"
        row["Son 5 maç kaleci formu"] = f"{rgk['name']} ({rgk['starts']} maç, {rsp}, {rgk['conceded_per_game']} gol/maç)"
    scout = r.get("squad_scouting") or {}
    s_side = scout.get(side) if isinstance(scout, dict) else None
    if isinstance(s_side, dict):
        row["Hat güçleri (0-100)"] = (
            f"Kaleci {s_side['goalkeeper']:.0f} · Defans {s_side['defense']:.0f} · "
            f"Orta Saha {s_side['midfield']:.0f} · Forvet {s_side['attack']:.0f} "
            f"(Genel {s_side['overall']:.0f}, stil: {s_side['tactical_style']})"
        )
    bx = (r.get("boxscore_profile") or {}).get(side) if isinstance(r.get("boxscore_profile"), dict) else None
    if isinstance(bx, dict) and bx.get("shots_for") is not None:
        row["2026/27 Maç İstatistiği"] = (
            f"Şut {bx['shots_for']:.1f}/{bx.get('shots_against', 0):.1f} · "
            f"İsabet {bx.get('sot_for', 0):.1f}/{bx.get('sot_against', 0):.1f} · "
            f"Korner {bx.get('corners_for', 0):.1f}/{bx.get('corners_against', 0):.1f} · "
            f"CS %{100 * (bx.get('clean_sheet_rate') or 0):.0f} · "
            f"Kaleci kurtarış ~%{100 * (bx.get('gk_save_rate') or 0.70):.0f}"
        )
    return row


def write_team_files(date: str, out: list[dict], d: Path) -> None:
    """Per-match dossier of both teams (ESPN + Premier League official availability + line-by-line squad scouting)."""
    md = [f"# {date} — Takım dosyaları", "",
          "Kaynak: ESPN (form, son maçlar, puan durumu, sezon golleri, golcüler, kaleci, kartlar, ilk 11), "
          "2026/27 xG & maç istatistikleri, hat bazlı kadro gücü (Kaleci/Defans/Orta Saha/Forvet), Premier Lig "
          "resmî sakat/cezalı listesi ve varsa sizin sağladığınız sakatlık/ceza dosyası.", ""]
    for m in out:
        r = m.get("research")
        if not r or not (r.get("teams") or r.get("user_absences") or r.get("absences") or r.get("tm_absences") or r.get("squad_scouting")):
            continue
        h, a = _side_rows(r, "home"), _side_rows(r, "away")
        h["Takım"] = h["Takım"] if h["Takım"] != "-" else m["home"]
        a["Takım"] = a["Takım"] if a["Takım"] != "-" else m["away"]
        alerts = (r.get("user_absences") or {}).get("alerts") or []
        if r.get("user_absences", {}).get("source") and "⚠" in r["user_absences"]["source"] and "⚠ dosya" not in md[3]:
            md.insert(3, f"> ⚠ dosya: {r['user_absences']['source']}")
        md += [f"## {m['kickoff'][11:]} · {m['home']} - {m['away']} ({m['league']})", "",
               f"Aralarında: {r.get('h2h') or '-'} · Uyarı: {'; '.join((r.get('flags') or []) + alerts) or '-'}", "",
               "| | Ev | Deplasman |", "|---|---|---|"]
        for key in dict.fromkeys(list(h) + list(a)):
            md.append(f"| {key} | {h.get(key, '-')} | {a.get(key, '-')} |")
        scout = r.get("squad_scouting")
        if isinstance(scout, dict) and (scout.get("key_edges") or scout.get("derby")):
            md.append("")
            if scout.get("derby"):
                md.append(f"- **Derbi bağlamı:** {scout['derby'].get('label')} (tempo endeksi {scout.get('tempo_index', 50):.0f}/100)")
            for ke in scout.get("key_edges") or []:
                md.append(f"- **Taktik üstünlük:** {ke}")
        md.append("")
    (d / "takim_dosyalari.md").write_text("\n".join(md) + "\n", encoding="utf-8")


HISTORY_FILE = "nesine_history.jsonl"
MIN_MOVE = 0.03  # exchange probability move (3 pts) that Nesine's unchanged price has not followed


def _history(d: Path) -> list[dict]:
    path = d / HISTORY_FILE
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def lagging_selections(history: list[dict], out: list[dict], hours: float = 8.0) -> list[tuple[dict, dict, float, str]]:
    """Directly quoted selections whose exchange probability rose >= MIN_MOVE since an earlier run while
    Nesine still pays the same odds: the bookmaker has not (yet) followed the market move."""
    now = dt.datetime.now(TSI)
    hits = []
    for m in out:
        if m.get("status") != "fiyatlandı":
            continue
        for s in m["selections"]:
            if not s.get("direct"):
                continue
            best = None
            for snap in history:
                ts = dt.datetime.fromisoformat(snap["ts"])
                if now - ts > dt.timedelta(hours=hours):
                    continue
                rec = (snap.get("m") or {}).get(str(m["code"]))
                if not rec or rec.get("ref_t") == m.get("ref_fetched_utc"):
                    continue  # same exchange snapshot: nothing moved
                then = (rec.get("s") or {}).get(s["name"])
                if not then or abs(then[0] - s["odds"]) > 1e-9:
                    continue  # Nesine changed its price meanwhile
                move = s["fair_prob"] - then[1]
                if move >= MIN_MOVE and (best is None or move > best[0]):
                    best = (move, then[1], snap["ts"])
            if best:
                hits.append((m, s, best[1], best[2]))
    hits.sort(key=lambda x: x[1]["fair_prob"] - x[2], reverse=True)
    return hits


def record_history(d: Path, out: list[dict]) -> None:
    """Append this run's directly quoted prices (Nesine odds + exchange probability) for move detection."""
    snap = {"ts": dt.datetime.now(TSI).isoformat(timespec="seconds"), "m": {}}
    for m in out:
        if m.get("status") != "fiyatlandı":
            continue
        sel = {s["name"]: [s["odds"], s["fair_prob"]] for s in m["selections"] if s.get("direct")}
        if sel:
            snap["m"][str(m["code"])] = {"ref_t": m.get("ref_fetched_utc"), "s": sel}
    with (d / HISTORY_FILE).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snap, ensure_ascii=False) + "\n")


PREDICTIONS_FILE = "takip_kayit.json"


def score_distributions(joint, top: int = 25) -> dict:
    """Full-time score, half-time score and HT/FT result distributions of a goal grid joint[h1, a1, h2, a2]
    (recorded so score and HT/FT predictions can be scored the next day, even when Nesine offers no such market)."""
    import numpy as np
    j = np.asarray(joint, dtype=float)
    j = j / j.sum()
    g = j.shape[0]
    ft: dict[str, float] = {}
    ht: dict[str, float] = {}
    htft: dict[str, float] = {}
    sign = lambda h, a: "1" if h > a else ("0" if h == a else "2")  # noqa: E731
    for h1 in range(g):
        for a1 in range(g):
            for h2 in range(g):
                for a2 in range(g):
                    p = float(j[h1, a1, h2, a2])
                    if p <= 0:
                        continue
                    k = f"{h1 + h2}-{a1 + a2}"
                    ft[k] = ft.get(k, 0.0) + p
                    ht[f"{h1}-{a1}"] = ht.get(f"{h1}-{a1}", 0.0) + p
                    hk = f"{sign(h1, a1)}/{sign(h1 + h2, a1 + a2)}"
                    htft[hk] = htft.get(hk, 0.0) + p
    best = lambda d, n: {k: round(v, 5) for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]}  # noqa: E731
    return {"ft": best(ft, top), "ht": best(ht, 12), "htft": best(htft, 9)}


def record_predictions(d: Path, out: list[dict]) -> None:
    """Keep the last pre-kick-off prediction of every priced match (for settlement and hit-rate tracking).
    Matches that already started keep the record written before kick-off."""
    path = d / PREDICTIONS_FILE
    try:
        store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except json.JSONDecodeError:
        store = {}
    now = dt.datetime.now(TSI)
    for m in out:
        if m.get("status") not in ("fiyatlandı", NESINE_ONLY_STATUS) or dt.datetime.fromisoformat(m["kickoff_iso"]) <= now:
            continue
        store[str(m["code"])] = {
            "home": m["home"], "away": m["away"], "league": m["league"], "kickoff_iso": m["kickoff_iso"],
            "reference": m["reference"], "espn_event": (m.get("research") or {}).get("espn_event"),
            "recorded": now.isoformat(timespec="seconds"),
            "s": {s["name"]: [round(s["fair_prob"], 4), s["odds"], int(bool(s.get("direct")))] for s in m["selections"]},
        }
        if m["code"] in PRICED:
            store[str(m["code"])]["dist"] = score_distributions(PRICED[m["code"]]["joint"])
    path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")


def write_report(date: str, out: list[dict], payload: dict, events: list, min_ev: float) -> None:
    from bahis_aileleri import format_top_five, top_five
    from quantfoot.evaluation.auto_learn import load_live_calibration

    calibration = load_live_calibration() or {}
    for match in out:
        match["en_yuksek_5"] = top_five(match, calibration)
    priced = sum(1 for m in out if m["status"] == "fiyatlandı")
    d = DAILY / date
    d.mkdir(parents=True, exist_ok=True)
    lagging = lagging_selections(_history(d), out)
    record_history(d, out)
    record_predictions(d, out)
    _, generated = global_references(max_age_hours=1e9)
    ref_age_h = None
    if generated:
        ref_age_h = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)).total_seconds() / 3600
        for m in out:
            m["ref_age_hours"] = round(ref_age_h, 2)
            m["betting_ok"] = ref_age_h <= MAX_PRICE_AGE_H
    (d / "nesine_global.json").write_text(json.dumps({"date": date, "generated_at": dt.datetime.now(TSI).isoformat(timespec="seconds"),
                                                      "ref_age_hours": None if ref_age_h is None else round(ref_age_h, 2),
                                                      "max_price_age_hours": MAX_PRICE_AGE_H,
                                                      "nesine_margins": market_overrounds(payload, {e.code for e in events}),
                                                      "matches": out}, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    age = ""
    if generated:
        mins = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)).total_seconds() / 60
        stale = mins > MAX_PRICE_AGE_H * 60
        age = (f"**Global veri {mins:.0f} dakika önce çekildi**"
               + (" — ESKİ (>" + f"{MAX_PRICE_AGE_H:g} saat); analiz fiyatlar, kupon/bahis kullanmaz." if stale else ".")
               + " (yurt dışı sunucu: istek üzerine global-odds iş akışı)")
    priced_sharp = sum(1 for m in out if classify_price_tier(m["status"], m.get("reference")) == "keskin")
    priced_book = sum(1 for m in out if classify_price_tier(m["status"], m.get("reference")) == "global_buro")
    real_total = sum(1 for m in out if classify_price_tier(m["status"], m.get("reference")) != "ozel_bahis")
    researched_n = sum(
        1 for m in out
        if (m.get("research") or {}).get("teams") or (m.get("research") or {}).get("tm_absences")
    )
    md = [f"# {date} — Nesine bülteni, global referans fiyatına göre", "", age, "",
          f"Referans önceliği: Pinnacle → Smarkets / Matchbook (ikisi varsa ortalaması) → Betfair / OddsMath (BetInAsia-Pinnacle) "
          f"→ Global Büro (OddsMath Marathonbet/1XBET) → ESPN. "
          f"**{real_total}** gerçek maçın **{priced_sharp + priced_book}**'i global fiyatlı "
          f"(**{priced_sharp}** keskin borsa/Pinnacle + **{priced_book}** global büro orta güven); "
          f"**{researched_n}** maçta canlı araştırma (ESPN / Transfermarkt) var.", "",
          "> EV = global adil olasılık × Nesine oranı − 1. Türev pazarlar (İY/MS, KG, aralık, kombine…) referans 1X2 + Alt/Üst'ten "
          "kalibre edilmiş ortak gol dağılımıyla hesaplanır. DraftKings keskin bir büro değildir: küçük artı EV'ler gürültü olabilir.", ""]
    value = [(m, s) for m in out if m["status"] == "fiyatlandı" for s in m["selections"] if s["ev"] >= min_ev]
    value.sort(key=lambda x: x[1]["ev"], reverse=True)
    # In a liquid market an edge above +25% against a sharp price is almost always a data error
    # (thin reference, wrong match, model extrapolation) -> listed separately, never as a pick.
    plausible = [(m, s) for m, s in value if s["ev"] <= MAX_PLAUSIBLE_EV]
    suspicious = [(m, s) for m, s in value if s["ev"] > MAX_PLAUSIBLE_EV]

    def _rows(items: list) -> list[str]:
        rows = ["| Saat | Maç | Pazar | Seçim | Nesine | Adil oran | EV | MBS | Referans |", "|---|---|---|---|---|---|---|---|---|"]
        for m, s in items[:60]:
            rows.append(f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
                        f"{s['fair_odds']:.2f} | {s['ev']:+.1%} | {s['mbs']} | {m['reference'].split(' ')[0]} |")
        return rows

    md += ["## Borsa hareket etti, Nesine oranını güncellemedi", "",
           "Borsada olasılığı son 8 saatte en az 3 puan artan, Nesine'nin ise aynı oranı vermeye devam ettiği seçimler "
           "(haber / kadro sonrası geç kalan oran). Doğrudan borsa fiyatlı seçimler.", ""]
    if lagging:
        md += ["| Saat | Maç | Pazar | Seçim | Nesine (değişmedi) | Borsa olasılığı önce → şimdi | Şimdiki EV | İlk görülme |",
               "|---|---|---|---|---|---|---|---|"]
        md += [f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
               f"%{p0 * 100:.1f} → %{s['fair_prob'] * 100:.1f} | {s['ev']:+.1%} | {ts[11:16]} |" for m, s, p0, ts in lagging[:40]]
    else:
        md.append("_Şu an yok (ilk çalıştırmalarda geçmiş birikene kadar boş kalır)._")
    md += ["", "## Nesine'nin global adil fiyatın üstünde verdiği seçimler", ""]
    md += _rows(plausible) if plausible else ["_Bugün Nesine'nin global adil fiyatın üstünde verdiği seçim yok._"]
    if suspicious:
        md += ["", f"## Referans hatası şüphesi (EV > {MAX_PLAUSIBLE_EV:+.0%}) — bahis önerisi değildir", "",
               "Likit bir piyasada keskin fiyata karşı bu büyüklükte fark neredeyse her zaman veri hatasıdır "
               "(ince borsa fiyatı, yanlış eşleşen maç ya da uç favorilerde model dışı bölge).", ""]
        md += _rows(suspicious)
    md += ["", "## Fiyatlanan maçlar", "", "| Saat | Lig | Maç | Nesine 1/X/2 | Global adil 1/X/2 | Referans | En iyi EV | En yüksek 5 aile olasılığı |",
           "|---|---|---|---|---|---|---|---|"]
    for m in out:
        if m["status"] != "fiyatlandı":
            continue
        fair = "/".join(f"{1 / p:.2f}" for p in m["fair_1x2"])
        nes = "/".join(f"{o:.2f}" if o else "-" for o in m["nesine_ms"])
        best = m["selections"][0] if m["selections"] else None
        best_s = f"{best['market']}: {best['selection']} {best['ev']:+.1%}" if best else "-"
        md.append(f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | {nes} | {fair} | {m['reference'].split(' ')[0]} | {best_s} | {format_top_five(m['en_yuksek_5'])} |")
    md += ["", "## Maç araştırması (ESPN: form, puan durumu, dinlenme, ilk 11)", "",
           "Olasılık global fiyattan gelir; bu bölüm bağlam ve güvenlik kontrolüdür. Önemli bir eksik, global fiyat "
           "çekildikten sonra açıklanan ilk 11'de görülürse maç kupona alınmaz.", "",
           "| Saat | Maç | Form (ev / dep) | Puan durumu (ev / dep) | Dinlenme (gün) | Aralarında | İlk 11 | Eksikler (ev / dep) | Uyarı |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m in out:
        r = m.get("research")
        if not r:
            continue
        h, a = r["teams"].get("home", {}), r["teams"].get("away", {})
        mot = r.get("motivation", {})
        lineup = "açıklandı" if h.get("lineup_announced") or a.get("lineup_announced") else "henüz yok"
        md.append(f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {h.get('form', '-')} / {a.get('form', '-')} | "
                  f"{mot.get('home') or '-'} / {mot.get('away') or '-'} | {h.get('rest_days', '-')} / {a.get('rest_days', '-')} | "
                  f"{r.get('h2h') or '-'} | {lineup} | {_absent(r, 'home')} / {_absent(r, 'away')} | "
                  f"{'; '.join(r.get('flags') or []) or '-'} |")
    md += ["", "## Global fiyatı bulunamayan maçlar (fiyatlanmadı)", ""]
    md += [f"- {m['kickoff'][11:]} {m['league']}: {m['home']} - {m['away']}"
           + (f" — düşük güven tahmini (Nesine): 1/X/2 %{m['fair_1x2'][0] * 100:.0f} / %{m['fair_1x2'][1] * 100:.0f} / %{m['fair_1x2'][2] * 100:.0f}"
              if m["status"] == NESINE_ONLY_STATUS else " — fiyatlanmadı")
           for m in out if m["status"] != "fiyatlandı"]
    (d / "nesine_global.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    write_team_files(date, out, d)
    print(f"{priced}/{len(events)} maç fiyatlandı; {len(value)} seçim EV ≥ {min_ev:+.1%}. -> {d}/nesine_global.md")


if __name__ == "__main__":
    main()
