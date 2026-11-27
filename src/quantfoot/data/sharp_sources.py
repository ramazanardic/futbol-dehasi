"""Unified sharp odds aggregation: The Odds API v4, football-data fixtures, and freshness merging.

All external connectors are strictly optional and activate only when their API key environment
variable is configured (e.g. ``THE_ODDS_API_KEY``). Every parser emits the exact reference
schema consumed by ``scripts/nesine_global.py`` so all 5 AIs share identical sharp coverage.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable

import requests

from quantfoot.markets.devig import devig

THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"

#: Sharp-first bookmaker priority inside The Odds API v4.
_ODDS_API_SHARP_ORDER: tuple[tuple[str, str, int], ...] = (
    ("pinnacle", "Pinnacle (TheOddsAPI)", 0),
    ("betfair_ex_eu", "Betfair (TheOddsAPI)", 1),
    ("betfair_ex_uk", "Betfair (TheOddsAPI)", 1),
    ("matchbook", "Matchbook (TheOddsAPI)", 1),
    ("smarkets", "Smarkets (TheOddsAPI)", 1),
    ("marathonbet", "OddsAPI (Marathonbet)", 3),
    ("betonlineag", "OddsAPI (BetOnline)", 3),
)

#: Popular soccer sport keys served by The Odds API v4.
DEFAULT_ODDS_API_SPORTS: tuple[str, ...] = (
    "soccer_epl",
    "soccer_efl_champ",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_turkey_super_league",
    "soccer_netherlands_eredivisie",
    "soccer_portugal_primeira_liga",
    "soccer_belgium_first_div",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_uefa_europa_conference_league",
)


def _book_meta(book_key: str) -> tuple[str, int] | None:
    low = str(book_key or "").lower()
    for key, label, rank in _ODDS_API_SHARP_ORDER:
        if low == key:
            return label, rank
    return None


def _clean_2way_odds(o1: float | None, o2: float | None, max_vig: float = 0.14) -> list[float] | None:
    if o1 is None or o2 is None:
        return None
    if o1 <= 1.01 or o2 <= 1.01:
        return None
    vig = (1.0 / o1) + (1.0 / o2) - 1.0
    if not (-0.02 <= vig <= max_vig):
        return None
    return [round(float(o1), 4), round(float(o2), 4)]


def parse_the_odds_api_events(
    events: Iterable[dict[str, Any]],
    *,
    fetched_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize The Odds API v4 soccer event payloads into ``nesine_global`` reference dicts.

    Extracts sharp 1X2 (``h2h``), Over/Under (``totals`` across 1.5/2.5/3.5/4.5), and
    Asian Handicap (``spreads``, home-team point line) from the highest-priority sharp book
    (Pinnacle > Betfair Exchange / Matchbook / Smarkets).
    """
    ts = fetched_utc or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    refs: list[dict[str, Any]] = []

    for ev in events:
        home = str(ev.get("home_team") or "").strip()
        away = str(ev.get("away_team") or "").strip()
        ko_raw = ev.get("commence_time")
        league = str(ev.get("sport_title") or ev.get("sport_key") or "").strip()
        if not (home and away and ko_raw):
            continue
        try:
            ko = dt.datetime.fromisoformat(str(ko_raw).replace("Z", "+00:00"))
        except ValueError:
            continue

        x12_cands: list[tuple[int, float, str, list[float], str]] = []
        ou_by_line: dict[float, list[tuple[int, float, list[float]]]] = {}
        ah_cands: list[tuple[int, float, float, list[float]]] = []

        for bk in ev.get("bookmakers") or []:
            meta = _book_meta(str(bk.get("key") or ""))
            if meta is None:
                continue
            src_lbl, rk = meta
            last_upd = str(bk.get("last_update") or ts)
            for mkt in bk.get("markets") or []:
                mkey = str(mkt.get("key") or "").lower()
                outcomes = mkt.get("outcomes") or []
                if mkey == "h2h":
                    mp = {str(o.get("name")): o.get("price") for o in outcomes}
                    try:
                        o1x2 = [float(mp[home]), float(mp["Draw"]), float(mp[away])]
                    except (KeyError, TypeError, ValueError):
                        continue
                    if min(o1x2) > 1.01:
                        vig = sum(1.0 / x for x in o1x2) - 1.0
                        if -0.02 <= vig <= 0.14:
                            x12_cands.append((rk, vig, src_lbl, o1x2, last_upd))
                elif mkey == "totals":
                    by_pt: dict[float, dict[str, float]] = {}
                    for o in outcomes:
                        pt = o.get("point")
                        nm = str(o.get("name") or "").lower()
                        pr = o.get("price")
                        if pt is None or pr is None or nm not in ("over", "under"):
                            continue
                        try:
                            by_pt.setdefault(float(pt), {})[nm] = float(pr)
                        except (TypeError, ValueError):
                            continue
                    for pt, sides in by_pt.items():
                        pair = _clean_2way_odds(sides.get("over"), sides.get("under"))
                        if pair and abs(pt % 1.0 - 0.5) < 1e-6:
                            vig = (1.0 / pair[0]) + (1.0 / pair[1]) - 1.0
                            ou_by_line.setdefault(pt, []).append((rk, vig, pair))
                elif mkey == "spreads":
                    home_pts: dict[float, float] = {}
                    away_pts: dict[float, float] = {}
                    for o in outcomes:
                        pt = o.get("point")
                        nm = str(o.get("name") or "")
                        pr = o.get("price")
                        if pt is None or pr is None:
                            continue
                        try:
                            fpt, fpr = float(pt), float(pr)
                        except (TypeError, ValueError):
                            continue
                        if nm == home:
                            home_pts[fpt] = fpr
                        elif nm == away:
                            away_pts[fpt] = fpr
                    for h_line, oh in home_pts.items():
                        oa = away_pts.get(-h_line)
                        pair = _clean_2way_odds(oh, oa)
                        if pair:
                            vig = (1.0 / pair[0]) + (1.0 / pair[1]) - 1.0
                            # Prefer balanced lines closest to even money (|oh - oa| small).
                            bal = abs(pair[0] - pair[1])
                            ah_cands.append((rk, bal, h_line, pair))

        if not x12_cands:
            continue
        x12_cands.sort(key=lambda x: (x[0], x[1]))
        _, _, src_lbl, x12, last_upd = x12_cands[0]

        ou_main = None
        direct_markets: dict[str, dict[str, float]] = {}
        for pt in sorted(ou_by_line):
            cands = sorted(ou_by_line[pt], key=lambda x: (x[0], x[1]))
            pair = cands[0][2]
            if abs(pt - 2.5) < 1e-6:
                ou_main = [2.5, pair]
            probs = devig(pair, method="power").probabilities
            direct_markets[f"Over/Under {pt:.1f}"] = {
                "OVER|Over": round(float(probs[0]), 5),
                "UNDER|Under": round(float(probs[1]), 5),
            }
        if ou_main is None and ou_by_line:
            best_pt = min(ou_by_line, key=lambda x: abs(x - 2.5))
            cands = sorted(ou_by_line[best_pt], key=lambda x: (x[0], x[1]))
            ou_main = [best_pt, cands[0][2]]

        ah_main = None
        if ah_cands:
            ah_cands.sort(key=lambda x: (x[0], x[1]))
            ah_main = [ah_cands[0][2], ah_cands[0][3]]

        refs.append(
            {
                "source": src_lbl,
                "league": league,
                "home": home,
                "away": away,
                "kickoff": ko,
                "kickoff_utc": ko.isoformat(),
                "x12": x12,
                "ou": ou_main,
                "ah": ah_main,
                "markets": direct_markets,
                "fetched_utc": ts,
                "book_updated_utc": last_upd,
            }
        )
    return refs


def fetch_the_odds_api_references(
    *,
    api_key: str | None = None,
    sports: Iterable[str] = DEFAULT_ODDS_API_SPORTS,
    cache_dir: Path | None = None,
    cache_ttl_h: float = 2.0,
    timeout: int = 15,
) -> list[dict[str, Any]]:
    """Fetch fresh sharp odds from The Odds API v4 when ``THE_ODDS_API_KEY`` is configured.

    Returns an empty list cleanly with zero network traffic when no key is configured.
    """
    key = (api_key or os.environ.get("THE_ODDS_API_KEY", "")).strip()
    if not key:
        return []

    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    all_refs: list[dict[str, Any]] = []
    for sport in sports:
        cached = Path(cache_dir) / f"the_odds_api_{sport}.json" if cache_dir is not None else None
        if cached is not None and cached.exists() and time.time() - cached.stat().st_mtime < cache_ttl_h * 3600:
            try:
                loaded = json.loads(cached.read_text(encoding="utf-8"))
                for r in loaded:
                    r["kickoff"] = dt.datetime.fromisoformat(str(r["kickoff_utc"]).replace("Z", "+00:00"))
                all_refs.extend(loaded)
                continue
            except (OSError, ValueError, KeyError, TypeError):
                pass
        try:
            resp = requests.get(
                f"{THE_ODDS_API_BASE}/sports/{sport}/odds",
                params={
                    "apiKey": key,
                    "regions": "eu,uk",
                    "markets": "h2h,totals,spreads",
                    "oddsFormat": "decimal",
                    "bookmakers": "pinnacle,betfair_ex_eu,betfair_ex_uk,matchbook,smarkets",
                },
                timeout=timeout,
            )
            if resp.status_code != 200:
                continue
            payload = resp.json()
        except (requests.RequestException, ValueError):
            continue
        parsed = parse_the_odds_api_events(payload if isinstance(payload, list) else [], fetched_utc=ts)
        if cached is not None:
            try:
                cached.parent.mkdir(parents=True, exist_ok=True)
                serializable = [{k: v for k, v in r.items() if k != "kickoff"} for r in parsed]
                cached.write_text(json.dumps(serializable, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        all_refs.extend(parsed)
    return all_refs


def _parse_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
        return v if v > 0.0 else None
    except (TypeError, ValueError):
        return None


def _parse_signed_float(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_fd_kickoff(date_s: str, time_s: str) -> dt.datetime | None:
    ds = (date_s or "").strip()
    ts = (time_s or "12:00").strip() or "12:00"
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(f"{ds} {ts}", fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def load_football_data_fixtures(
    csv_path: Path | str,
    *,
    fetched_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Parse ``football-data.co.uk`` ``fixtures.csv`` into sharp reference records.

    Prioritizes Pinnacle (``PSH/PSD/PSA``, ``P>2.5/P<2.5``, ``AHh/PAHH/PAHA``), then
    Betfair Exchange (``BFEH/BFED/BFEA``, ``BFE>2.5/BFE<2.5``, ``AHh/BFEAHH/BFEAHA``).
    """
    path = Path(csv_path)
    if not path.exists():
        return []
    ts = fetched_utc or dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc).isoformat(timespec="seconds")
    refs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            home = (row.get("HomeTeam") or "").strip()
            away = (row.get("AwayTeam") or "").strip()
            ko = _parse_fd_kickoff(row.get("Date") or "", row.get("Time") or "")
            if not (home and away and ko):
                continue
            league = (row.get("Div") or "").strip()

            p_x12 = [_parse_float(row.get(c)) for c in ("PSH", "PSD", "PSA")]
            bfe_x12 = [_parse_float(row.get(c)) for c in ("BFEH", "BFED", "BFEA")]
            if all(v is not None and v > 1.01 for v in p_x12):
                source = "Pinnacle (football-data)"
                x12 = [float(v) for v in p_x12]  # type: ignore[arg-type]
                ou_pair = _clean_2way_odds(_parse_float(row.get("P>2.5")), _parse_float(row.get("P<2.5")))
                ah_pair = _clean_2way_odds(_parse_float(row.get("PAHH")), _parse_float(row.get("PAHA")))
            elif all(v is not None and v > 1.01 for v in bfe_x12):
                source = "Betfair Borsası (football-data)"
                x12 = [float(v) for v in bfe_x12]  # type: ignore[arg-type]
                ou_pair = _clean_2way_odds(_parse_float(row.get("BFE>2.5")), _parse_float(row.get("BFE<2.5")))
                ah_pair = _clean_2way_odds(_parse_float(row.get("BFEAHH")), _parse_float(row.get("BFEAHA")))
            else:
                continue

            ah_line = _parse_signed_float(row.get("AHh"))
            ah = [ah_line, ah_pair] if (ah_line is not None and ah_pair is not None) else None
            ou = [2.5, ou_pair] if ou_pair is not None else None
            refs.append(
                {
                    "source": source,
                    "league": league,
                    "home": home,
                    "away": away,
                    "kickoff": ko,
                    "kickoff_utc": ko.isoformat(),
                    "x12": x12,
                    "ou": ou,
                    "ah": ah,
                    "fetched_utc": ts,
                }
            )
    return refs


def reference_age_hours(ref: dict[str, Any], now_utc: dt.datetime | None = None) -> float | None:
    """Return age of a reference snapshot in hours, or None if timestamp is missing."""
    raw = ref.get("fetched_utc") or ref.get("book_updated_utc")
    if not raw:
        return None
    try:
        ts = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 3600.0)


def filter_fresh_references(
    refs: Iterable[dict[str, Any]],
    *,
    max_age_hours: float = 3.0,
    now_utc: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    """Keep only references whose snapshot age is within ``max_age_hours``."""
    now = now_utc or dt.datetime.now(dt.timezone.utc)
    out: list[dict[str, Any]] = []
    for r in refs:
        age = reference_age_hours(r, now_utc=now)
        if age is None or age <= max_age_hours:
            out.append(r)
    return out
