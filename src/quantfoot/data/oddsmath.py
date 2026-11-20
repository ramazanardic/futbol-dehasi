"""Live OddsMath sharp bookmaker odds, verified O/U totals, and opening-to-live steam feed.

OddsMath exposes clean JSON endpoints reachable directly from Turkey (no proxy, no key) carrying
live and opening prices from sharp brokers/exchanges (BetInAsia/Pinnacle, Matchbook, Betfair,
Smarkets, Marathonbet, etc.).

Verified ``cat_id`` schema (probed directly against live events):
- ``cat_id=0``: 1X2 (``schema == ["1", "X", "2"]``) — includes both ``first`` (open) and ``live``
  prices so opening-to-live sharp probability steam (``steam_1x2``) can be measured directly.
- ``cat_id=6``: Over/Under 2.5 (``schema == ["O", "U"]``, ``subcategory["Total"] == "2.5"``)
- ``cat_id=7``: Over/Under 1.5 (``schema == ["O", "U"]``, ``subcategory["Total"] == "1.5"``)
- ``cat_id=8``: Over/Under 3.5 (``schema == ["O", "U"]``, ``subcategory["Total"] == "3.5"``)

Note: ``cat_id=4`` is Draw No Bet (``Handicap: 0``), NOT BTTS. Every parser in this module
validates ``schema`` and ``subcategory`` explicitly so market misidentification is impossible.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import difflib
import re
from typing import Any, Iterable
import unicodedata

import requests
from requests.adapters import HTTPAdapter

from quantfoot.markets.devig import devig

ODDSMATH_BASE_URL = "https://www.oddsmath.com/api/v1"
ODDSMATH_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TSI_TZ = dt.timezone(dt.timedelta(hours=3))


def _pooled_session(pool_size: int = 20) -> requests.Session:
    sess = requests.Session()
    sess.headers.update(ODDSMATH_HEADERS)
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


#: Common club abbreviations / rebrands between Turkish Nesine bulletins and global feeds.
TEAM_ALIASES: dict[str, str] = {
    "tns": "the new saints",
    "ura": "uganda revenue authority",
    "agmk": "olmaliq",
    "fk agmk": "olmaliq",
    "admira wacker": "trenkwalder admira",
    "cd esc belen": "escorpiones",
    "esc belen": "escorpiones",
    "qpr": "queens park rangers",
    "psg": "paris saint germain",
    "pao": "panathinaikos",
}

ODDSMATH_CAT_1X2 = 0
ODDSMATH_CAT_OU_25 = 6
ODDSMATH_CAT_OU_15 = 7
ODDSMATH_CAT_OU_35 = 8

VERIFIED_OU_CATS: tuple[tuple[str, int], ...] = (
    ("2.5", ODDSMATH_CAT_OU_25),
    ("1.5", ODDSMATH_CAT_OU_15),
    ("3.5", ODDSMATH_CAT_OU_35),
)

#: Sharpest-first bookmaker priority used when selecting the reference price per market.
BOOK_PRIORITY: tuple[tuple[str, int], ...] = (
    ("BetInAsia", 0),
    ("Pinnacle", 0),
    ("Matchbook", 1),
    ("Betfair", 1),
    ("Smarkets", 1),
    ("Marathonbet", 2),
    ("1XBET", 3),
    ("Unibet", 3),
    ("Bet365", 4),
    ("WilliamHill", 4),
    ("Bwin", 5),
)

_STOP_RE = re.compile(
    r"\b(fc|cf|sc|ac|sk|fk|nk|cd|ca|club|de|da|the|utd|united|sv|vfb|tsg|rc|ud|ad|sd|sp|bk|"
    r"if|ik|afc|ssc|as|us|ss|uc|cs|cr|al|el|gnk|hnk|pfc|cska|bsc|tsv|sg|fsv|spvgg|rv|vv|vvv|"
    r"rkc|nac|az|psv|pec|ado|nec|kvc|kv|ksc|rsc|krc|ogc|osc|aj|sm|ea|stade|olympique|"
    r"sporting|real|atletico|deportivo)\b"
)


def _book_rank(name: str) -> tuple[int, str]:
    low = str(name).lower()
    for pat, rank in BOOK_PRIORITY:
        if pat.lower() in low:
            return rank, pat
    return 9, str(name)


def _norm_team(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\(k\)|\(kol\)|\(w\)|\(u\d+\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    raw_clean = " ".join(s.split())
    if raw_clean in TEAM_ALIASES:
        raw_clean = TEAM_ALIASES[raw_clean]
    s = _STOP_RE.sub(" ", raw_clean)
    cleaned = " ".join(s.split())
    return TEAM_ALIASES.get(cleaned, cleaned)


def _team_sim(a: str, b: str) -> float:
    na, nb = _norm_team(a), _norm_team(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    pref = 0.85 if (len(na) >= 5 and len(nb) >= 5 and na[:5] == nb[:5]) else 0.0
    sub = 0.82 if (min(len(na), len(nb)) >= 4 and (na in nb or nb in na)) else 0.0
    return max(ratio, jacc, pref, sub)


def is_women_match(league: str, home: str, away: str) -> bool:
    """Return True when league or team names indicate a women's football fixture."""
    txt = f"{league} {home} {away}".lower()
    return bool(re.search(r"kad[ıi]n|\(k\)|\(w\)|\bwomen\b|\bfemin|\bdamen|\bfrauen|\bladies\b|vrouwen", txt))


def is_youth_or_reserve_match(league: str, home: str, away: str) -> bool:
    """Return True for explicit U17–U23 youth competitions/teams so youth never cross-matches senior sides."""
    txt = f"{league} {home} {away}".lower()
    return bool(re.search(r"\bu17\b|\bu18\b|\bu19\b|\bu20\b|\bu21\b|\bu23\b|gen[çc]ler|beloften|youth|primavera", txt))


# ---- Pure JSON parsers (100% testable offline) -----------------------------------------------


def parse_oddsmath_day_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse ``events-by-day.json`` response into UTC-stamped event dictionaries."""
    out: list[dict[str, Any]] = []
    for _lg_id, lg_data in (payload.get("data") or {}).items():
        if not isinstance(lg_data, dict):
            continue
        lg_name = str(lg_data.get("name", ""))
        for ev_id, ev in (lg_data.get("events") or {}).items():
            if not isinstance(ev, dict):
                continue
            t_str = str(ev.get("time", "")).strip()
            try:
                ko_local = dt.datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TSI_TZ)
            except ValueError:
                continue
            out.append(
                {
                    "id": str(ev_id),
                    "league": lg_name,
                    "home": str(ev.get("hometeam_name", "")),
                    "away": str(ev.get("awayteam_name", "")),
                    "kickoff": ko_local.astimezone(dt.timezone.utc),
                    "live": bool(ev.get("live")),
                }
            )
    return out


def parse_oddsmath_1x2_payload(payload: dict[str, Any], *, max_vig: float = 0.16) -> dict[str, Any]:
    """Parse OddsMath ``cat_id=0`` (1X2) payload with strict schema validation and steam computation."""
    res: dict[str, Any] = {
        "1x2": None,
        "book_1x2": None,
        "book_rank": 9,
        "vig_1x2": None,
        "books_count": 0,
        "steam_1x2": None,
    }
    if payload.get("schema") != ["1", "X", "2"]:
        return res
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return res

    cands: list[tuple[int, float, str, str, list[float], list[float] | None]] = []
    for bname, node in data.items():
        if not isinstance(node, dict):
            continue
        live = node.get("live") or {}
        try:
            vals = [float(live.get("1")), float(live.get("X")), float(live.get("2"))]
        except (TypeError, ValueError):
            continue
        if min(vals) <= 1.01:
            continue
        vig = sum(1.0 / v for v in vals) - 1.0
        if not (0.0 <= vig <= max_vig):
            continue
        rk, label = _book_rank(bname)
        first = node.get("first")
        fvals = None
        if isinstance(first, dict):
            try:
                fv = [float(first.get("1")), float(first.get("X")), float(first.get("2"))]
                if min(fv) > 1.01:
                    fvals = fv
            except (TypeError, ValueError):
                pass
        if fvals is None and isinstance(node.get("history"), list):
            # OddsMath history is ordered newest-first; earliest valid entry is the opening quote
            for entry in reversed(node["history"]):
                if not isinstance(entry, dict):
                    continue
                try:
                    fv = [float(entry.get("1")), float(entry.get("X")), float(entry.get("2"))]
                    if min(fv) > 1.01:
                        fvals = fv
                        break
                except (TypeError, ValueError):
                    continue
        cands.append((rk, vig, label, str(bname), vals, fvals))

    res["books_count"] = len(cands)
    if not cands:
        return res

    cands.sort(key=lambda x: (x[0], x[1]))
    rk, vig, _label, bname, vals, fvals = cands[0]
    res["1x2"] = vals
    res["book_1x2"] = bname
    res["book_rank"] = rk
    res["vig_1x2"] = round(vig, 4)
    if fvals:
        p0 = devig(fvals, method="power").probabilities
        p1 = devig(vals, method="power").probabilities
        res["steam_1x2"] = [round(float(p1[i] - p0[i]), 4) for i in range(3)]
    return res


def parse_oddsmath_ou_payload(
    payload: dict[str, Any],
    expected_total: str,
    *,
    max_vig: float = 0.14,
) -> dict[str, Any] | None:
    """Parse OddsMath O/U payload while strictly enforcing ``schema == ['O', 'U']`` and exact total line."""
    if payload.get("schema") != ["O", "U"]:
        return None
    subcat_total = str((payload.get("subcategory") or {}).get("Total", ""))
    if subcat_total != str(expected_total):
        return None
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return None

    cands: list[tuple[int, float, str, list[float]]] = []
    for bname, node in data.items():
        if not isinstance(node, dict):
            continue
        live = node.get("live") or {}
        try:
            vals = [float(live.get("O")), float(live.get("U"))]
        except (TypeError, ValueError):
            continue
        if min(vals) <= 1.01:
            continue
        vig = sum(1.0 / v for v in vals) - 1.0
        if not (0.0 <= vig <= max_vig):
            continue
        rk, _ = _book_rank(bname)
        cands.append((rk, vig, str(bname), vals))

    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]))
    rk, vig, bname, vals = cands[0]
    return {"book": bname, "book_rank": rk, "odds": vals, "vig": round(vig, 4)}


# ---- Live HTTP fetchers ----------------------------------------------------------------------


def fetch_oddsmath_day(day_str: str, *, timeout: int = 20) -> list[dict[str, Any]]:
    """Fetch all scheduled/live football events for ``YYYY-MM-DD`` (Europe/Istanbul) from OddsMath."""
    url = (
        f"{ODDSMATH_BASE_URL}/events-by-day.json"
        f"?language=en&country_code=TR&day={day_str}&timezone=Europe/Istanbul"
    )
    try:
        r = requests.get(url, headers=ODDSMATH_HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []
        return parse_oddsmath_day_payload(r.json())
    except (requests.RequestException, ValueError):
        return []


def fetch_oddsmath_event_odds(
    event_id: str,
    *,
    include_ou: bool = True,
    timeout: int = 12,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch verified 1X2 (+ opening-to-live steam) and O/U 1.5 / 2.5 / 3.5 odds for one OddsMath event."""
    out: dict[str, Any] = {
        "event_id": str(event_id),
        "1x2": None,
        "ou": {},
        "book_1x2": None,
        "book_rank": 9,
        "vig_1x2": None,
        "books_count": 0,
        "steam_1x2": None,
    }
    getter = session.get if session is not None else requests.get
    req_kw = {"timeout": timeout} if session is not None else {"headers": ODDSMATH_HEADERS, "timeout": timeout}

    url_1x2 = (
        f"{ODDSMATH_BASE_URL}/live-odds.json"
        f"?event_id={event_id}&cat_id={ODDSMATH_CAT_1X2}&include_exchanges=1&language=en&country_code=TR"
    )
    try:
        r = getter(url_1x2, **req_kw)
        if r.status_code == 200:
            parsed = parse_oddsmath_1x2_payload(r.json())
            out.update(parsed)
    except (requests.RequestException, ValueError):
        pass

    if include_ou:
        for line_str, cat_id in VERIFIED_OU_CATS:
            url_ou = (
                f"{ODDSMATH_BASE_URL}/live-odds.json"
                f"?event_id={event_id}&cat_id={cat_id}&include_exchanges=1&language=en&country_code=TR"
            )
            try:
                r = getter(url_ou, **req_kw)
                if r.status_code != 200:
                    continue
                ou_parsed = parse_oddsmath_ou_payload(r.json(), expected_total=line_str)
                if ou_parsed is not None:
                    out["ou"][line_str] = ou_parsed
            except (requests.RequestException, ValueError):
                continue

    return out


# ---- Matching & nesine_global reference bridge -----------------------------------------------


def match_event_to_oddsmath(
    home: str,
    away: str,
    kickoff_utc: dt.datetime,
    candidates: Iterable[dict[str, Any]],
    *,
    league: str = "",
    max_hours: float = 3.0,
    threshold: float = 0.62,
) -> tuple[dict[str, Any] | None, float]:
    """Match a fixture to its OddsMath event while strictly separating women/men and youth/senior teams."""
    ko = kickoff_utc.astimezone(dt.timezone.utc) if kickoff_utc.tzinfo else kickoff_utc.replace(tzinfo=dt.timezone.utc)
    w_flag = is_women_match(league, home, away)
    y_flag = is_youth_or_reserve_match(league, home, away)
    best, best_sc = None, 0.0
    for c in candidates:
        c_ko = c.get("kickoff")
        if not isinstance(c_ko, dt.datetime):
            continue
        dt_sec = abs((c_ko - ko).total_seconds())
        if dt_sec > max_hours * 3600:
            continue
        if is_women_match(c.get("league", ""), c.get("home", ""), c.get("away", "")) != w_flag:
            continue
        if is_youth_or_reserve_match(c.get("league", ""), c.get("home", ""), c.get("away", "")) != y_flag:
            continue
        sh = _team_sim(home, c.get("home", ""))
        sa = _team_sim(away, c.get("away", ""))
        sc = (sh + sa) / 2.0
        if min(sh, sa) < 0.42:
            # Same-kickoff exact-anchor fallback: one team matches nearly verbatim while the opponent
            # uses a sponsor/local/rebranded name (downstream _consistent still checks 1X2 odds alignment).
            if dt_sec <= 900 and max(sh, sa) >= 0.90 and min(sh, sa) >= 0.15:
                sc = max(sc, threshold)
            else:
                continue
        if sc > best_sc:
            best_sc, best = sc, c
    return (best, best_sc) if best_sc >= threshold else (None, best_sc)


def _source_label(book_name: str | None, book_rank: int) -> str:
    if book_rank == 0:
        return "OddsMath (BetInAsia/Pinnacle)"
    if book_rank == 1:
        return "OddsMath (Borsa)"
    return f"OddsMath ({book_name or 'diğer'})"


def oddsmath_to_reference(
    event: dict[str, Any],
    odds: dict[str, Any],
    *,
    fetched_utc: str | None = None,
) -> dict[str, Any] | None:
    """Convert an OddsMath event + live odds dict into a ``nesine_global.py``-compatible reference."""
    if not odds.get("1x2"):
        return None
    ts = fetched_utc or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    ou_map = odds.get("ou") or {}

    primary_ou = None
    for line_str in ("2.5", "1.5", "3.5"):
        if line_str in ou_map:
            primary_ou = [float(line_str), list(ou_map[line_str]["odds"])]
            break

    # Populate direct devigged O/U markets in exact nesine_global.direct_probabilities format
    direct_markets: dict[str, dict[str, float]] = {}
    for line_str, node in ou_map.items():
        p_ou = devig(node["odds"], method="power").probabilities
        direct_markets[f"Over/under {line_str}"] = {
            f"OVER|Over {line_str} goals": round(float(p_ou[0]), 5),
            f"UNDER|Under {line_str} goals": round(float(p_ou[1]), 5),
        }

    return {
        "source": _source_label(odds.get("book_1x2"), int(odds.get("book_rank", 9))),
        "league": event.get("league", ""),
        "home": event.get("home", ""),
        "away": event.get("away", ""),
        "kickoff": event["kickoff"],
        "kickoff_utc": event["kickoff"].isoformat(),
        "x12": list(odds["1x2"]),
        "ou": primary_ou,
        "markets": direct_markets,
        "book_1x2": odds.get("book_1x2"),
        "vig_1x2": odds.get("vig_1x2"),
        "books_count": odds.get("books_count", 0),
        "steam_1x2": odds.get("steam_1x2"),
        "fetched_utc": ts,
    }


def fetch_oddsmath_references(
    events: Iterable[Any],
    dates: Iterable[str],
    *,
    include_ou: bool = True,
    max_workers: int = 16,
    league_lookup: dict[Any, str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch live OddsMath sharp references matching a list of Nesine/fixture events."""
    pool: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for d in dates:
        for ev in fetch_oddsmath_day(d):
            if ev["id"] not in seen_ids:
                seen_ids.add(ev["id"])
                pool.append(ev)
    if not pool:
        return []

    matched_events: dict[str, dict[str, Any]] = {}
    for e in events:
        if isinstance(e, dict):
            home, away = e.get("home", ""), e.get("away", "")
            ko = e.get("kickoff")
            if isinstance(ko, str):
                ko = dt.datetime.fromisoformat(ko)
            lg = e.get("league", "")
        else:
            home, away, ko = e.home, e.away, e.kickoff
            lg = (league_lookup or {}).get(getattr(e, "league_code", None), "")
        if not isinstance(ko, dt.datetime):
            continue
        hit, _ = match_event_to_oddsmath(home, away, ko, pool, league=lg)
        if hit is not None:
            matched_events[hit["id"]] = hit

    if not matched_events:
        return []

    fetched_ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    odds_by_id: dict[str, dict[str, Any]] = {}
    sess = _pooled_session(pool_size=max(max_workers + 4, 20))
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {
                ex.submit(fetch_oddsmath_event_odds, eid, include_ou=include_ou, session=sess): eid
                for eid in matched_events
            }
            for fut, eid in futs.items():
                odds_by_id[eid] = fut.result()
    finally:
        sess.close()

    refs: list[dict[str, Any]] = []
    for eid, ev in matched_events.items():
        ref = oddsmath_to_reference(ev, odds_by_id[eid], fetched_utc=fetched_ts)
        if ref is not None:
            refs.append(ref)
    return refs
