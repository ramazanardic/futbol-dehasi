"""Optional API-Football v3 connector (1,100+ leagues: exotic odds + fixtures).

Activates automatically when ``API_FOOTBALL_KEY`` is present in the environment (or GitHub
Actions Secrets). When unset, every function cleanly returns an empty list with zero errors
so the rest of the pipeline runs unaffected.

Free tier: 100 requests/day at https://www.api-football.com/ — querying by date
(``/fixtures?date=YYYY-MM-DD`` + paginated ``/odds?date=YYYY-MM-DD``) covers an entire day's
global football slate including Rwanda, Iraq, Bahrain 2nd Div, Saudi 2nd Div, Nicaragua, U21.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable

import requests

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"

#: Preferred bookmaker ordering inside API-Football's bookmaker payload.
_BOOK_PRIORITY: tuple[tuple[str, int], ...] = (
    ("Pinnacle", 0),
    ("Betfair", 1),
    ("Marathonbet", 2),
    ("1xBet", 3),
    ("Bet365", 4),
    ("Unibet", 5),
    ("Bwin", 6),
)


def _book_rank(name: str) -> int:
    low = str(name).lower()
    for pat, rk in _BOOK_PRIORITY:
        if pat.lower() in low:
            return rk
    return 9


def parse_api_football_odds(
    fixtures_by_id: dict[int, dict[str, Any]],
    odds_items: Iterable[dict[str, Any]],
    *,
    fetched_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Normalize API-Football ``/fixtures`` + ``/odds`` JSON into ``nesine_global.py`` references."""
    ts = fetched_utc or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    refs: list[dict[str, Any]] = []

    for item in odds_items:
        fx_id = (item.get("fixture") or {}).get("id")
        fx = fixtures_by_id.get(fx_id)
        if not fx:
            continue
        teams = fx.get("teams") or {}
        home = (teams.get("home") or {}).get("name")
        away = (teams.get("away") or {}).get("name")
        ko_raw = (fx.get("fixture") or {}).get("date")
        lg_name = f"{(fx.get('league') or {}).get('country', '')} {(fx.get('league') or {}).get('name', '')}".strip()
        if not (home and away and ko_raw):
            continue
        try:
            ko = dt.datetime.fromisoformat(str(ko_raw).replace("Z", "+00:00"))
        except ValueError:
            continue

        x12_cands: list[tuple[int, float, str, list[float]]] = []
        ou_cands: list[tuple[int, float, list[float]]] = []

        for bk in item.get("bookmakers") or []:
            bname = str(bk.get("name") or "")
            rk = _book_rank(bname)
            for bet in bk.get("bets") or []:
                bet_name = str(bet.get("name") or "").lower()
                vals = bet.get("values") or []
                if bet_name in ("match winner", "1x2"):
                    mp = {str(v.get("value")): v.get("odd") for v in vals}
                    try:
                        o1x2 = [float(mp["Home"]), float(mp["Draw"]), float(mp["Away"])]
                    except (KeyError, TypeError, ValueError):
                        continue
                    if min(o1x2) > 1.01:
                        vig = sum(1.0 / x for x in o1x2) - 1.0
                        if 0.0 <= vig <= 0.16:
                            x12_cands.append((rk, vig, bname, o1x2))
                elif bet_name in ("goals over/under", "over/under"):
                    mp = {str(v.get("value")): v.get("odd") for v in vals}
                    try:
                        o_ou = [float(mp["Over 2.5"]), float(mp["Under 2.5"])]
                    except (KeyError, TypeError, ValueError):
                        continue
                    if min(o_ou) > 1.01:
                        vig = sum(1.0 / x for x in o_ou) - 1.0
                        if 0.0 <= vig <= 0.14:
                            ou_cands.append((rk, vig, o_ou))

        if not x12_cands:
            continue
        x12_cands.sort(key=lambda x: (x[0], x[1]))
        rk, vig, bname, x12 = x12_cands[0]
        ou = None
        if ou_cands:
            ou_cands.sort(key=lambda x: (x[0], x[1]))
            ou = [2.5, ou_cands[0][2]]

        if rk == 0:
            src_lbl = "Pinnacle (API-Football)"
        elif rk == 1:
            src_lbl = "Betfair (API-Football)"
        else:
            src_lbl = f"API-Football ({bname})"

        refs.append(
            {
                "source": src_lbl,
                "league": lg_name,
                "home": home,
                "away": away,
                "kickoff": ko,
                "kickoff_utc": ko.isoformat(),
                "x12": x12,
                "ou": ou,
                "fetched_utc": ts,
            }
        )
    return refs


def fetch_api_football_references(
    dates: Iterable[str],
    *,
    api_key: str | None = None,
    max_odds_pages: int = 8,
    timeout: int = 20,
    budget: Any = None,
    cache_dir: Path | None = None,
    cache_ttl_h: float = 3.0,
) -> list[dict[str, Any]]:
    """Fetch global odds across 1,100+ leagues from API-Football when ``API_FOOTBALL_KEY`` is configured.

    ``budget`` (``quantfoot.data.api_budget.ApiBudget``): every HTTP request spends one unit first; when the day's cap
    is reached the remaining requests are skipped. ``cache_dir``: one day's parsed references are kept for
    ``cache_ttl_h`` hours so repeated pipeline runs (ai_tahmin, nesine_kupon rounds) do not re-spend the quota.
    """
    key = api_key or os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        return []

    headers = {"x-apisports-key": key}
    all_refs: list[dict[str, Any]] = []
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def _spend(what: str) -> bool:
        return budget is None or budget.spend(1, what)

    for day_str in dates:
        cached = Path(cache_dir) / f"odds_refs_{day_str}.json" if cache_dir is not None else None
        if cached is not None and cached.exists() and time.time() - cached.stat().st_mtime < cache_ttl_h * 3600:
            try:
                loaded = json.loads(cached.read_text(encoding="utf-8"))
                for r in loaded:
                    r["kickoff"] = dt.datetime.fromisoformat(str(r["kickoff_utc"]).replace("Z", "+00:00"))
                all_refs.extend(loaded)
                continue
            except (ValueError, KeyError, TypeError, AttributeError):
                pass  # unreadable cache: fetch the day again
        day_refs: list[dict[str, Any]] = []
        if not _spend(f"fixtures {day_str}"):
            continue
        try:
            rf = requests.get(f"{API_FOOTBALL_BASE}/fixtures", params={"date": day_str}, headers=headers, timeout=timeout)
            if rf.status_code != 200:
                continue
            fx_list = (rf.json() or {}).get("response") or []
        except (requests.RequestException, ValueError):
            continue

        fx_by_id = {
            int(f["fixture"]["id"]): f
            for f in fx_list
            if isinstance(f, dict) and (f.get("fixture") or {}).get("id") is not None
        }
        if not fx_by_id:
            if cached is not None:  # e.g. a date the free plan does not serve: do not ask again within the TTL
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text("[]", encoding="utf-8")
            continue

        odds_items: list[dict[str, Any]] = []
        for page in range(1, max_odds_pages + 1):
            if not _spend(f"odds {day_str} p{page}"):
                break
            try:
                ro = requests.get(
                    f"{API_FOOTBALL_BASE}/odds",
                    params={"date": day_str, "page": page},
                    headers=headers,
                    timeout=timeout,
                )
                if ro.status_code != 200:
                    break
                js = ro.json() or {}
            except (requests.RequestException, ValueError):
                break
            odds_items.extend(js.get("response") or [])
            paging = js.get("paging") or {}
            if int(paging.get("current") or page) >= int(paging.get("total") or 1):
                break

        day_refs = parse_api_football_odds(fx_by_id, odds_items, fetched_utc=ts)
        all_refs.extend(day_refs)
        if cached is not None and odds_items:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(day_refs, ensure_ascii=False, default=str), encoding="utf-8")

    return all_refs
