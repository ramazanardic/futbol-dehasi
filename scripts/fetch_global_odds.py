"""Fetch sharp global football prices on a server outside Turkey (GitHub Actions) and store them in the repo.

Runs in .github/workflows/global-odds.yml; the local morning job does `git pull` and
scripts/nesine_global.py reads data/global_odds/latest/references.json.

Sources (free, no key, no quota; both are blocked from Turkey, hence the remote runner):
  * football-data.co.uk fixtures files — Pinnacle 1X2 and O/U 2.5 prices for upcoming matches
    (fixtures.csv: main European leagues; new_league_fixtures.csv: ARG, BRA, JPN, MEX, USA ...).
  * Smarkets exchange public API v3 — live back/lay quotes; the bid/offer mid of an exchange is a
    low-margin estimate of the market probability.

Output (per run):
  data/global_odds/latest/references.json   normalised list used by nesine_global.py
  data/global_odds/latest/fetch_log.json     counts, errors and small raw samples for debugging
  data/global_odds/latest/*.csv               raw football-data files

Only `requests` and the standard library are used, so the job has no fragile dependencies.
"""

from __future__ import annotations

import logging

import csv
import datetime as dt
import io
import json
import math
import sys
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "global_odds" / "latest"
UA = {"User-Agent": "Mozilla/5.0 (QuantFoot research; contact via repository)"}
FD_FILES = {
    "fixtures.csv": "https://www.football-data.co.uk/fixtures.csv",
    "new_league_fixtures.csv": "https://www.football-data.co.uk/new_league_fixtures.csv",
}
SEASON_DIVISIONS: tuple[str, ...] = (
    "E0", "E1", "E2", "E3", "EC", "SP1", "SP2", "D1", "D2", "I1", "I2", "F1", "F2", "T1", "N1", "P1", "B1", "SC0", "SC1",
    "SC2", "SC3", "G1",
)
FD_SEASON_URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
SMARKETS = "https://api.smarkets.com/v3"
# Smarkets market types stored as direct references for derivative selections (KG, other O/U lines, halves...).
DIRECT_TYPES = {"OVER_UNDER", "BTTS", "DOUBLE_CHANCE", "ODD_EVEN", "SCORE_RANGE", "HALF_FULL", "HALF_TIME_WINNER_3_WAY",
                "SECOND_HALF_WINNER_3_WAY", "FIRST_HALF_OVER_UNDER", "SECOND_HALF_OVER_UNDER", "BTTS_FIRST_HALF",
                "BTTS_SECOND_HALF", "BTTS_BOTH_HALVES", "HIGHEST_SCORING_HALF", "FIRST_HALF_ODD_EVEN", "WINNER_AND_BTTS",
                "WINNER_AND_OVER", "BTTS_AND_OVER", "HALF_TIME_DOUBLE_CHANCE", "FIRST_HALF_WINNER_AND_BTTS",
                "CORNERS_OVER_UNDER", "FIRST_HALF_CORNERS_OVER_UNDER"}
MAX_SPREAD = 0.04  # widest acceptable bid/offer spread (4 percentage points) for an exchange reference

DEADLINE = time.monotonic() + 11 * 60  # hard time budget for the whole run (seconds)


def _say(msg: str) -> None:
    print(msg, flush=True)


def _time_left() -> float:
    return DEADLINE - time.monotonic()


LOG: dict = {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "errors": [], "counts": {}, "samples": {}}


def _get(url: str, **params) -> requests.Response:
    for attempt in range(3):
        if _time_left() < 5:
            raise TimeoutError("time budget exhausted")
        try:
            r = requests.get(url, params=params or None, headers=UA, timeout=(10, 20))
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            return r
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            LOG["errors"].append(f"retry {url}: {exc}")
            logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
            time.sleep(3)
    return r


def _f(row: dict, *names: str) -> float | None:
    for n in names:
        v = (row.get(n) or "").strip()
        try:
            x = float(v)
            if x > 1.0:
                return x
        except ValueError:
            continue
    return None


def _f_signed(row: dict, *names: str) -> float | None:
    """Parse a signed float such as an Asian Handicap line (e.g. -0.75, 0.0, +0.5)."""
    for n in names:
        v = (row.get(n) or "").strip()
        if not v:
            continue
        try:
            return float(v)
        except ValueError:
            continue
    return None


def current_season_code(today: dt.date | None = None) -> str:
    """Return European split-year football-data.co.uk season code (e.g. '2627' for Nov 2026)."""
    ref = today or dt.datetime.now(dt.timezone.utc).date()
    start_year = ref.year if ref.month >= 7 else ref.year - 1
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def _fd_kickoff(date_s: str, time_s: str) -> str | None:
    """football-data dates are dd/mm/yyyy (or yy) in UK local time; times may be empty."""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            naive = dt.datetime.strptime(f"{date_s.strip()} {(time_s or '15:00').strip()}", fmt)
            # UK time: GMT in winter, BST (UTC+1) from last Sunday of March to last Sunday of October.
            year = naive.year
            bst_start = max(dt.datetime(year, 3, d) for d in range(25, 32) if dt.datetime(year, 3, d).weekday() == 6)
            bst_end = max(dt.datetime(year, 10, d) for d in range(25, 32) if dt.datetime(year, 10, d).weekday() == 6)
            offset = 1 if bst_start <= naive < bst_end else 0
            return (naive - dt.timedelta(hours=offset)).replace(tzinfo=dt.timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _log_pool_consensus_x12(books: dict[str, list[float]]) -> tuple[list[float], float]:
    """Pure-stdlib precision-weighted log-opinion-pool consensus (prior / sqrt(overround)) across sharp books."""
    priors = {"PS": 1.35, "P": 1.35, "BFE": 1.40, "B365": 0.85, "BV": 0.85, "Avg": 0.90}
    valid: list[tuple[list[float], float]] = []
    for key, odds in books.items():
        if len(odds) != 3 or any(o <= 1.01 for o in odds):
            continue
        inv = [1.0 / o for o in odds]
        s = sum(inv)
        ov = max(0.0, s - 1.0)
        # Power-method exponent k so sum(inv_i^k) == 1 via fast bisection
        lo, hi = 0.5, 2.0
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            if sum(v ** mid for v in inv) > 1.0:
                lo = mid
            else:
                hi = mid
        k = 0.5 * (lo + hi)
        probs = [v ** k for v in inv]
        ps = sum(probs)
        probs = [p / ps for p in probs]
        prec = priors.get(key, 0.75) / math.sqrt(max(ov, 0.015))
        valid.append((probs, prec))
    if not valid:
        raise ValueError("no valid books")
    tot_w = sum(w for _, w in valid)
    log_p = [sum((w / tot_w) * math.log(max(p[i], 1e-9)) for p, w in valid) for i in range(3)]
    m = max(log_p)
    ex = [math.exp(x - m) for x in log_p]
    z = sum(ex)
    cons = [x / z for x in ex]
    max_gap = max(abs(p[i] - cons[i]) for p, _ in valid for i in range(3)) if len(valid) > 1 else 0.0
    return [round(1.0 / max(c, 1e-6), 4) for c in cons], round(max_gap, 4)


def football_data() -> list[dict]:
    refs = []
    for name, url in FD_FILES.items():
        try:
            r = _get(url)
            r.raise_for_status()
        except Exception as exc:
            LOG["errors"].append(f"football-data {name}: {exc}")
            logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
            continue
        text = r.content.decode("utf-8-sig", errors="replace")
        (OUT / name).write_text(text, encoding="utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        LOG["counts"][name] = len(rows)
        LOG["samples"][name] = {"columns": list(rows[0].keys()) if rows else [], "first": rows[0] if rows else None}
        for row in rows:
            home = row.get("HomeTeam") or row.get("Home")
            away = row.get("AwayTeam") or row.get("Away")
            ko = _fd_kickoff(row.get("Date", ""), row.get("Time", ""))
            # Collect all available sharp & tier-1 books for precision-weighted consensus + dispersion.
            books_x12: dict[str, list[float]] = {}
            for prefix in ("PS", "P", "BFE", "B365", "BV", "Avg"):
                cand = [_f(row, f"{prefix}H"), _f(row, f"{prefix}D"), _f(row, f"{prefix}A")]
                if None not in cand:
                    if prefix == "P" and "PS" in books_x12:
                        continue
                    books_x12[prefix] = cand
            # Sharpest anchor required: Pinnacle (PS*/P*) or Betfair Exchange (BFE*).
            x12, source, gap = None, None, None
            for prefix, label in (("PS", "Pinnacle (football-data)"), ("P", "Pinnacle (football-data)"),
                                  ("BFE", "Betfair Borsası (football-data)")):
                if prefix in books_x12:
                    x12, source = books_x12[prefix], label
                    break
            if x12 is None:
                continue
            if len(books_x12) >= 2:
                cons_x12, cand_gap = _log_pool_consensus_x12(books_x12)
                if cand_gap <= 0.06:
                    x12, gap = cons_x12, cand_gap
            ou = None
            for prefix in ("P", "BFE"):
                over, under = _f(row, f"{prefix}>2.5"), _f(row, f"{prefix}<2.5")
                if over and under:
                    ou = [2.5, [over, under]]
                    break
            ah = None
            ah_line = _f_signed(row, "AHh", "BbAHh")
            if ah_line is not None:
                for prefix in ("PAH", "BFEAH"):
                    ah_h, ah_a = _f(row, f"{prefix}H"), _f(row, f"{prefix}A")
                    if ah_h and ah_a:
                        ah = [ah_line, [ah_h, ah_a]]
                        break
            if home and away and ko:
                rec = {"source": source, "league": row.get("Div") or f"{row.get('Country', '')} {row.get('League', '')}".strip(),
                       "home": home, "away": away, "kickoff_utc": ko, "x12": x12, "ou": ou, "ah": ah}
                if len(books_x12) >= 2:
                    rec["n_books"] = len(books_x12)
                    rec["consensus_gap"] = gap
                    rec["books_x12"] = books_x12
                refs.append(rec)
    return refs


def fetch_season_history(
    season: str | None = None,
    divisions: tuple[str, ...] = SEASON_DIVISIONS,
    out_dir: Path | None = None,
) -> int:
    """Download current-season football-data.co.uk match-history CSVs (shots, corners, cards, Pinnacle close)."""
    season_code = season or current_season_code()
    dest = (out_dir or OUT) / f"season_{season_code}"
    dest.mkdir(parents=True, exist_ok=True)
    saved_files = 0
    total_rows = 0
    for div in divisions:
        if _time_left() < 60:
            LOG["errors"].append(f"season_history {season_code}: time budget reached at {div}")
            break
        url = FD_SEASON_URL.format(season=season_code, div=div)
        try:
            r = _get(url)
            if r.status_code != 200:
                LOG["errors"].append(f"season_history {season_code}/{div}: HTTP {r.status_code}")
                continue
        except Exception as exc:
            LOG["errors"].append(f"season_history {season_code}/{div}: {exc}")
            logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
            continue
        text = r.content.decode("utf-8-sig", errors="replace")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if "Date" not in first_line or "HomeTeam" not in first_line:
            LOG["errors"].append(f"season_history {season_code}/{div}: unexpected header")
            continue
        (dest / f"{div}.csv").write_text(text, encoding="utf-8")
        rows = max(0, len(text.splitlines()) - 1)
        saved_files += 1
        total_rows += rows
    LOG["counts"][f"season_{season_code}_files"] = saved_files
    LOG["counts"][f"season_{season_code}_rows"] = total_rows
    _say(f"football-data season {season_code}: {saved_files}/{len(divisions)} divisions ({total_rows} matches)")
    return saved_files


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def smarkets(days: int = 7, max_events: int = 3000, window_hours: float | None = None, direct_hours: float = 36.0) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + (dt.timedelta(hours=window_hours) if window_hours else dt.timedelta(days=days))
    # Query in 6-hour windows: a single sorted query stops at ~600 events, which silently dropped every
    # match after Saturday afternoon. Each window is paginated and events are de-duplicated by id.
    events, seen_ids = [], set()
    start = now
    while start < horizon and len(events) < max_events and _time_left() > 120:
        end = min(start + dt.timedelta(hours=6), horizon)
        url = f"{SMARKETS}/events/"
        params = {"type": "football_match", "state": "upcoming", "limit": 300, "sort": "start_datetime,id",
                  "start_datetime_min": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "start_datetime_max": end.strftime("%Y-%m-%dT%H:%M:%SZ")}
        seen_pages: set[str] = set()
        for _ in range(6):  # pagination within the window (bounded)
            r = _get(url, **params) if params else _get(url)
            if r.status_code != 200:
                LOG["errors"].append(f"smarkets events HTTP {r.status_code}: {r.text[:200]}")
                break
            js = r.json()
            for e in js.get("events", []):
                if e["id"] not in seen_ids:
                    seen_ids.add(e["id"])
                    events.append(e)
            nxt = (js.get("pagination") or {}).get("next_page")
            if not nxt or nxt in seen_pages:
                break
            seen_pages.add(nxt)
            url, params = f"{SMARKETS}/events/{nxt}", None
        start = end
    _say(f"smarkets events (6 h windows): {len(events)}")
    LOG["counts"]["smarkets_events"] = len(events)
    if events:
        LOG["samples"]["smarkets_event"] = events[0]
    events = events[:max_events]
    _say(f"smarkets events: {len(events)}")
    by_event = {str(e["id"]): e for e in events}

    markets = []
    for ids in _chunks(list(by_event), 50):
        if _time_left() < 60:
            LOG["errors"].append("smarkets: time budget reached while fetching markets")
            break
        r = _get(f"{SMARKETS}/events/{','.join(ids)}/markets/")
        if r.status_code == 200:
            markets += r.json().get("markets", [])
        else:
            LOG["errors"].append(f"smarkets markets HTTP {r.status_code}")
    LOG["counts"]["smarkets_markets"] = len(markets)
    if markets:
        LOG["samples"]["smarkets_market"] = markets[0]

    names: dict[str, int] = {}
    for m in markets:
        key = f"{(m.get('market_type') or {}).get('name')} | {m.get('name')}"
        names[key] = names.get(key, 0) + 1
    LOG["samples"]["smarkets_market_names"] = dict(sorted(names.items(), key=lambda kv: -kv[1])[:60])

    def _kind(m: dict) -> str | None:
        # Full-time markets only: half-time markets share the same market_type, so match on the name.
        name = (m.get("name") or "").strip().lower()
        mtype = str((m.get("market_type") or {}).get("name", "")).upper()
        if mtype == "WINNER_3_WAY" and name in ("full-time result", "full time result", "match odds"):
            return "1x2"
        if name in ("over/under 2.5", "over/under 2.5 goals", "total goals over/under 2.5") and "half" not in name:
            return "ou25"
        if mtype in DIRECT_TYPES and _soon(m):
            return "direct"
        return None

    direct_until = now + dt.timedelta(hours=direct_hours)

    def _soon(m: dict) -> bool:
        # derivative markets only for matches within direct_hours (time budget); the light run refreshes them pre-kick-off
        ev = by_event.get(str(m.get("event_id")))
        try:
            return dt.datetime.fromisoformat(ev["start_datetime"].replace("Z", "+00:00")) <= direct_until
        except (TypeError, KeyError, ValueError):
            return False

    wanted = {str(m["id"]): (m, _kind(m)) for m in markets if _kind(m)}
    contracts, quotes = [], {}
    _say(f"smarkets markets: {len(markets)}, wanted: {len(wanted)}")
    # 1X2 and O/U 2.5 first, so a time-budget cut only ever loses the optional direct derivative markets.
    def _order(k: str) -> tuple:
        m, kind = wanted[k]
        ev = by_event.get(str(m.get("event_id"))) or {}
        return (kind == "direct", ev.get("start_datetime") or "")

    for ids in _chunks(sorted(wanted, key=_order), 50):
        if _time_left() < 30:
            LOG["errors"].append("smarkets: time budget reached while fetching quotes")
            break
        rc = _get(f"{SMARKETS}/markets/{','.join(ids)}/contracts/")
        if rc.status_code == 200:
            contracts += rc.json().get("contracts", [])
        rq = _get(f"{SMARKETS}/markets/{','.join(ids)}/quotes/")
        if rq.status_code == 200:
            quotes.update(rq.json())
    LOG["counts"]["smarkets_contracts"] = len(contracts)
    if contracts:
        LOG["samples"]["smarkets_contract"] = contracts[0]
    if quotes:
        k = next(iter(quotes))
        LOG["samples"]["smarkets_quote"] = {k: quotes[k]}

    def _mid_and_spread(cid: str) -> tuple[float, float] | None:
        """Bid/offer mid probability and spread (both in probability units, prices are basis points)."""
        q = quotes.get(str(cid)) or {}
        bids = [b["price"] for b in q.get("bids", []) if b.get("price")]
        offers = [o["price"] for o in q.get("offers", []) if o.get("price")]
        if bids and offers:
            hi_bid, lo_offer = max(bids) / 10000.0, min(offers) / 10000.0
            return (hi_bid + lo_offer) / 2, lo_offer - hi_bid
        return None

    per_market: dict[str, dict[str, float]] = {}
    labelled: dict[str, dict[str, float]] = {}  # direct markets: "CONTRACT_TYPE|contract name" -> mid
    spreads: dict[str, float] = {}
    n_contracts: dict[str, int] = {}
    for c in contracts:
        mkt = str(c["market_id"])
        n_contracts[mkt] = n_contracts.get(mkt, 0) + 1
        ms = _mid_and_spread(c["id"])
        if ms is None:
            continue
        ctype = str((c.get("contract_type") or {}).get("name", "") or c.get("name", "")).upper()
        per_market.setdefault(mkt, {})[ctype] = ms[0]
        labelled.setdefault(mkt, {})[f"{ctype}|{c.get('name', '')}"] = ms[0]
        spreads[mkt] = max(spreads.get(mkt, 0.0), ms[1])
    # Liquidity guard: a thin exchange book has a wide bid/offer spread and its mid is not a price.
    illiquid = {mid for mid, sp in spreads.items() if sp > MAX_SPREAD}
    LOG["counts"]["smarkets_markets_illiquid"] = len(illiquid)

    refs: dict[str, dict] = {}
    for mid_id, probs in per_market.items():
        if mid_id in illiquid:
            continue
        m, kind = wanted[mid_id]
        ev = by_event.get(str(m["event_id"]))
        if not ev:
            continue
        name = ev.get("name", "")
        if " vs " not in name:
            continue
        home, away = name.split(" vs ", 1)
        rec = refs.setdefault(str(ev["id"]), {"source": "Smarkets (borsa)", "league": ev.get("parent_id"), "home": home.strip(),
                                              "away": away.strip(), "kickoff_utc": ev.get("start_datetime"), "x12": None, "ou": None,
                                              "fetched_utc": now.isoformat(timespec="seconds")})
        if kind == "1x2" and {"HOME", "DRAW", "AWAY"} <= set(probs):
            p = [probs["HOME"], probs["DRAW"], probs["AWAY"]]
            s = sum(p)
            rec["x12"] = [round(s / x, 4) for x in p]  # margin-free odds from the exchange mid
            rec["x12_spread"] = round(spreads[mid_id], 4)
        if kind == "ou25" and {"OVER", "UNDER"} <= set(probs):
            p = [probs["OVER"], probs["UNDER"]]
            s = sum(p)
            rec["ou"] = [2.5, [round(s / x, 4) for x in p]]
            rec["ou_spread"] = round(spreads[mid_id], 4)
        if kind == "direct" and len(labelled.get(mid_id, {})) == n_contracts.get(mid_id):  # every outcome quoted
            lab = labelled[mid_id]
            s = sum(lab.values())
            if 0.9 < s < 1.1:  # exchange mids of a complete book sum to ~1
                rec.setdefault("markets", {})[m.get("name", "")] = {k: round(v / s, 4) for k, v in lab.items()}
    out = [r for r in refs.values() if r["x12"]]
    LOG["counts"]["smarkets_references"] = len(out)
    return out


MATCHBOOK = "https://api.matchbook.com/edge/rest/events"


def matchbook(window_hours: float = 7 * 24.0) -> list[dict]:
    """Matchbook exchange (public price feed, no account): margin-free 1X2 and O/U 2.5 from back/lay mids."""
    now = dt.datetime.now(dt.timezone.utc)
    horizon = now + dt.timedelta(hours=window_hours)
    events, offset = [], 0
    while offset < 1000 and _time_left() > 60:
        r = _get(MATCHBOOK, **{"sport-ids": 15, "per-page": 100, "offset": offset, "include-prices": "true", "price-depth": 1,
                               "exchange-type": "back-lay", "odds-type": "DECIMAL", "states": "open"})
        if r.status_code != 200:
            LOG["errors"].append(f"matchbook HTTP {r.status_code}")
            break
        js = r.json()
        batch = js.get("events", [])
        events += batch
        offset += len(batch)
        if not batch or offset >= js.get("total", 0):
            break
    LOG["counts"]["matchbook_events"] = len(events)
    if events and events[0].get("markets"):
        LOG["samples"]["matchbook_market"] = events[0]["markets"][0]
    names: dict[str, int] = {}

    def _mid(runner: dict) -> tuple[float, float] | None:
        backs = [p["decimal-odds"] for p in runner.get("prices", []) if p.get("side") == "back" and p.get("decimal-odds")]
        lays = [p["decimal-odds"] for p in runner.get("prices", []) if p.get("side") == "lay" and p.get("decimal-odds")]
        if not backs or not lays:
            return None
        pb, pl = 1 / max(backs), 1 / min(lays)  # back = lower probability bound, lay = upper
        return (pb + pl) / 2, pl - pb

    out = []
    for ev in events:
        try:
            ko = dt.datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if ko > horizon or " vs " not in ev.get("name", ""):
            continue
        home, away = (x.strip() for x in ev["name"].split(" vs ", 1))
        rec = {"source": "Matchbook (borsa)", "home": home, "away": away, "kickoff_utc": ev["start"], "x12": None, "ou": None,
               "fetched_utc": now.isoformat(timespec="seconds")}
        for m in ev.get("markets", []):
            key = f"{m.get('market-type')} | {m.get('name')}"
            names[key] = names.get(key, 0) + 1
            runners = [x for x in m.get("runners", []) if not x.get("withdrawn")]
            mids = [_mid(x) for x in runners]
            if not runners or any(x is None for x in mids) or max(x[1] for x in mids) > MAX_SPREAD:
                continue  # incomplete or illiquid book
            total = sum(x[0] for x in mids)
            if m.get("market-type") == "one_x_two" and len(runners) == 3:
                by = {x["name"].strip(): mid[0] for x, mid in zip(runners, mids)}
                draw = next((v for k, v in by.items() if k.lower() == "draw"), None)
                ph, pa = by.get(home), by.get(away)
                if None not in (draw, ph, pa):
                    rec["x12"] = [round(total / x, 4) for x in (ph, draw, pa)]
                    rec["x12_spread"] = round(max(x[1] for x in mids), 4)
            # Full-time match total only: "1st Half Total" and team totals share market-type "total".
            if (m.get("market-type") == "total" and (m.get("name") or "").strip().lower() == "total"
                    and abs(float(m.get("handicap") or 0) - 2.5) < 1e-9 and len(runners) == 2):
                over = next((mid[0] for x, mid in zip(runners, mids) if "over" in x["name"].lower()), None)
                under = next((mid[0] for x, mid in zip(runners, mids) if "under" in x["name"].lower()), None)
                if over and under:
                    rec["ou"] = [2.5, [round(total / over, 4), round(total / under, 4)]]
                    rec["ou_spread"] = round(max(x[1] for x in mids), 4)
        if rec["x12"]:
            out.append(rec)
    LOG["samples"]["matchbook_market_names"] = dict(sorted(names.items(), key=lambda kv: -kv[1])[:30])
    LOG["counts"]["matchbook_references"] = len(out)
    return out


def _write(refs: list[dict], full_utc: str | None = None) -> None:
    """full_utc: time of the last FULL fetch (a light run keeps the previous one, so the PC still sees how old
    the prices outside the light window are)."""
    LOG["counts"]["references_total"] = len(refs)
    LOG["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (OUT / "references.json").write_text(json.dumps({"generated_utc": LOG["finished_utc"],
                                                     "full_utc": full_utc or LOG["finished_utc"], "references": refs},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "fetch_log.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    _say(json.dumps(LOG["counts"]) + f" errors: {len(LOG['errors'])}")


def _key(r: dict) -> tuple:
    return (r.get("source"), r.get("home"), r.get("away"), r.get("kickoff_utc"))


def light(window_hours: float) -> None:
    """Pre-kick-off refresh: re-fetch Smarkets (all stored markets) only for matches starting within the window
    and merge them into the last full snapshot, so line-up news is priced in without a full 5-minute run."""
    old, full_utc = [], None
    if (OUT / "references.json").exists():
        prev = json.loads((OUT / "references.json").read_text(encoding="utf-8"))
        old, full_utc = prev.get("references", []), prev.get("full_utc") or prev.get("generated_utc")
    LOG["mode"] = f"light ({window_hours:g} h)"
    try:
        fresh = smarkets(window_hours=window_hours)
    except Exception as exc:
        LOG["errors"].append(f"light smarkets: {type(exc).__name__}: {exc}")
        logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
        fresh = []
    try:
        fresh += matchbook(window_hours=window_hours)
    except Exception as exc:
        LOG["errors"].append(f"light matchbook: {type(exc).__name__}: {exc}")
        logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
    keys = {_key(r) for r in fresh}
    _write([r for r in old if _key(r) not in keys] + fresh, full_utc=full_utc)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 2 and sys.argv[1] == "--light":
        light(float(sys.argv[2]))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--season-history":
        season = sys.argv[2] if len(sys.argv) > 2 else None
        fetch_season_history(season=season)
        return
    refs: list[dict] = []
    # Pinnacle (football-data) first: small, fast, most reliable. Saved before the exchange fetch.
    for fn in (football_data, matchbook, smarkets):  # Smarkets last: it is the one trimmed by the time budget
        _say(f"--- {fn.__name__} (time left {_time_left():.0f}s)")
        try:
            refs += fn()
        except Exception as exc:  # keep the other source if one fails
            LOG["errors"].append(f"{fn.__name__}: {type(exc).__name__}: {exc}")
            logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
            _say(f"{fn.__name__} failed: {type(exc).__name__}: {exc}")
        _write(refs)
        if fn is football_data:
            _say(f"--- fetch_season_history (time left {_time_left():.0f}s)")
            try:
                fetch_season_history()
            except Exception as exc:
                LOG["errors"].append(f"fetch_season_history: {type(exc).__name__}: {exc}")
                logging.getLogger(__name__).warning("%s", LOG["errors"][-1], exc_info=True)
                _say(f"fetch_season_history failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
