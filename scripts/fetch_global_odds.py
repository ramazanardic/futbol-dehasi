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

import csv
import datetime as dt
import io
import json
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
SMARKETS = "https://api.smarkets.com/v3"

DEADLINE = time.monotonic() + 8 * 60  # hard time budget for the whole run (seconds)


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


def football_data() -> list[dict]:
    refs = []
    for name, url in FD_FILES.items():
        try:
            r = _get(url)
            r.raise_for_status()
        except Exception as exc:
            LOG["errors"].append(f"football-data {name}: {exc}")
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
            # Pinnacle columns: PSH/PSD/PSA (main files) or PH/PD/PA (extra leagues).
            x12 = [_f(row, "PSH", "PH"), _f(row, "PSD", "PD"), _f(row, "PSA", "PA")]
            source = "Pinnacle (football-data)"
            if None in x12:
                continue
            ou = None
            over, under = _f(row, "P>2.5", "PC>2.5"), _f(row, "P<2.5", "PC<2.5")
            if over and under:
                ou = [2.5, [over, under]]
            if home and away and ko:
                refs.append({"source": source, "league": row.get("Div") or f"{row.get('Country', '')} {row.get('League', '')}".strip(),
                             "home": home, "away": away, "kickoff_utc": ko, "x12": x12, "ou": ou})
    return refs


def _chunks(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def smarkets(days: int = 2, max_events: int = 600) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    events, url = [], f"{SMARKETS}/events/"
    params = {"type": "football_match", "state": "upcoming", "limit": 300, "sort": "start_datetime,id",
              "start_datetime_max": (now + dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    seen_pages: set[str] = set()
    for _ in range(10):  # pagination (bounded)
        r = _get(url, **params) if params else _get(url)
        _say(f"smarkets events page: HTTP {r.status_code}")
        if r.status_code != 200:
            LOG["errors"].append(f"smarkets events HTTP {r.status_code}: {r.text[:200]}")
            break
        js = r.json()
        events += js.get("events", [])
        nxt = (js.get("pagination") or {}).get("next_page")
        if not nxt or nxt in seen_pages or len(events) >= max_events:
            break
        seen_pages.add(nxt)
        url, params = f"{SMARKETS}/events/{nxt}", None
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

    def _kind(m: dict) -> str | None:
        name = (m.get("name") or "").lower()
        mtype = str((m.get("market_type") or {}).get("name", "")).upper()
        if "WINNER_3_WAY" in mtype or name in ("full-time result", "match odds", "full time result"):
            return "1x2"
        if "2.5" in name and ("over" in name or "under" in name or "goals" in name):
            return "ou25"
        return None

    wanted = {str(m["id"]): (m, _kind(m)) for m in markets if _kind(m)}
    contracts, quotes = [], {}
    _say(f"smarkets markets: {len(markets)}, wanted: {len(wanted)}")
    for ids in _chunks(list(wanted), 50):
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

    def _mid_prob(cid: str) -> float | None:
        q = quotes.get(str(cid)) or {}
        bids = [b["price"] for b in q.get("bids", []) if b.get("price")]
        offers = [o["price"] for o in q.get("offers", []) if o.get("price")]
        if bids and offers:
            return (max(bids) + min(offers)) / 2 / 10000.0
        return None

    per_market: dict[str, dict[str, float]] = {}
    for c in contracts:
        mid = _mid_prob(c["id"])
        if mid is None:
            continue
        ctype = str((c.get("contract_type") or {}).get("name", "") or c.get("name", "")).upper()
        per_market.setdefault(str(c["market_id"]), {})[ctype] = mid

    refs: dict[str, dict] = {}
    for mid_id, probs in per_market.items():
        m, kind = wanted[mid_id]
        ev = by_event.get(str(m["event_id"]))
        if not ev:
            continue
        name = ev.get("name", "")
        if " vs " not in name:
            continue
        home, away = name.split(" vs ", 1)
        rec = refs.setdefault(str(ev["id"]), {"source": "Smarkets (borsa)", "league": ev.get("parent_id"), "home": home.strip(),
                                              "away": away.strip(), "kickoff_utc": ev.get("start_datetime"), "x12": None, "ou": None})
        if kind == "1x2" and {"HOME", "DRAW", "AWAY"} <= set(probs):
            p = [probs["HOME"], probs["DRAW"], probs["AWAY"]]
            s = sum(p)
            rec["x12"] = [round(s / x, 4) for x in p]  # margin-free odds from the exchange mid
        if kind == "ou25" and {"OVER", "UNDER"} <= set(probs):
            p = [probs["OVER"], probs["UNDER"]]
            s = sum(p)
            rec["ou"] = [2.5, [round(s / x, 4) for x in p]]
    out = [r for r in refs.values() if r["x12"]]
    LOG["counts"]["smarkets_references"] = len(out)
    return out


def _write(refs: list[dict]) -> None:
    LOG["counts"]["references_total"] = len(refs)
    LOG["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    (OUT / "references.json").write_text(json.dumps({"generated_utc": LOG["finished_utc"], "references": refs},
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "fetch_log.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    _say(json.dumps(LOG["counts"]) + f" errors: {len(LOG['errors'])}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    refs: list[dict] = []
    # Pinnacle (football-data) first: small, fast, most reliable. Saved before the exchange fetch.
    for fn in (football_data, smarkets):
        _say(f"--- {fn.__name__} (time left {_time_left():.0f}s)")
        try:
            refs += fn()
        except Exception as exc:  # keep the other source if one fails
            LOG["errors"].append(f"{fn.__name__}: {type(exc).__name__}: {exc}")
            _say(f"{fn.__name__} failed: {type(exc).__name__}: {exc}")
        _write(refs)


if __name__ == "__main__":
    main()
