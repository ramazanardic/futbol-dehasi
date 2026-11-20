"""Optional OddsPapi REST connector (300+ bookmakers: Pinnacle, Singbet, SBOBet, Betfair, 1xBet).

Activates automatically when ``ODDSPAPI_KEY`` is present in the environment (or GitHub
Actions Secrets). Returns an empty list cleanly with zero errors when unset.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Iterable

import requests

ODDSPAPI_BASE = "https://api.oddspapi.io/v4"

_SHARP_BOOKS: tuple[tuple[str, int, str], ...] = (
    ("pinnacle", 0, "Pinnacle (OddsPapi)"),
    ("singbet", 0, "Pinnacle (OddsPapi/Singbet)"),
    ("sbobet", 1, "OddsPapi (SBOBet)"),
    ("betfair", 1, "Betfair (OddsPapi)"),
    ("matchbook", 1, "Matchbook (OddsPapi)"),
    ("cloudbet", 2, "OddsPapi (Cloudbet)"),
    ("1xbet", 3, "OddsPapi (1XBET)"),
)


def _book_meta(book_key: str) -> tuple[int, str]:
    low = str(book_key).lower()
    for pat, rk, lbl in _SHARP_BOOKS:
        if pat in low:
            return rk, lbl
    return 5, f"OddsPapi ({book_key})"


def parse_oddspapi_fixtures(
    fixtures: Iterable[dict[str, Any]],
    *,
    fetched_utc: str | None = None,
) -> list[dict[str, Any]]:
    """Convert OddsPapi fixture+bookmaker payloads into ``nesine_global.py`` reference dicts."""
    ts = fetched_utc or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    refs: list[dict[str, Any]] = []

    for fx in fixtures:
        if not isinstance(fx, dict):
            continue
        home = fx.get("participant1Name") or fx.get("home")
        away = fx.get("participant2Name") or fx.get("away")
        ko_raw = fx.get("startTime") or fx.get("commenceTime")
        lg = str(fx.get("tournamentName") or fx.get("league") or "")
        if not (home and away and ko_raw):
            continue
        try:
            ko = dt.datetime.fromisoformat(str(ko_raw).replace("Z", "+00:00"))
        except ValueError:
            continue

        books = fx.get("bookmakerOdds") or fx.get("odds") or {}
        if not isinstance(books, dict):
            continue

        x12_cands: list[tuple[int, float, str, list[float]]] = []
        ou_cands: list[tuple[int, float, list[float]]] = []

        for bkey, bdata in books.items():
            if not isinstance(bdata, dict):
                continue
            rk, lbl = _book_meta(bkey)
            markets = bdata.get("markets") or bdata
            m1x2 = markets.get("101") or markets.get("1x2") or markets.get("h2h") or {}
            if isinstance(m1x2, dict):
                outcomes = m1x2.get("outcomes") or m1x2
                try:
                    o1 = float((outcomes.get("101") or outcomes.get("1") or outcomes.get("home") or {}).get("price", 0))
                    ox = float((outcomes.get("102") or outcomes.get("X") or outcomes.get("draw") or {}).get("price", 0))
                    o2 = float((outcomes.get("103") or outcomes.get("2") or outcomes.get("away") or {}).get("price", 0))
                    if min(o1, ox, o2) > 1.01:
                        vig = (1 / o1 + 1 / ox + 1 / o2) - 1.0
                        if 0.0 <= vig <= 0.16:
                            x12_cands.append((rk, vig, lbl, [o1, ox, o2]))
                except (TypeError, ValueError, AttributeError):
                    pass

            mou = markets.get("104") or markets.get("ou25") or markets.get("totals_2.5") or {}
            if isinstance(mou, dict):
                outcomes = mou.get("outcomes") or mou
                try:
                    oo = float((outcomes.get("over") or outcomes.get("O") or {}).get("price", 0))
                    ou = float((outcomes.get("under") or outcomes.get("U") or {}).get("price", 0))
                    if min(oo, ou) > 1.01:
                        vig = (1 / oo + 1 / ou) - 1.0
                        if 0.0 <= vig <= 0.14:
                            ou_cands.append((rk, vig, [oo, ou]))
                except (TypeError, ValueError, AttributeError):
                    pass

        if not x12_cands:
            continue
        x12_cands.sort(key=lambda x: (x[0], x[1]))
        _rk, _vig, lbl, x12 = x12_cands[0]
        ou_val = None
        if ou_cands:
            ou_cands.sort(key=lambda x: (x[0], x[1]))
            ou_val = [2.5, ou_cands[0][2]]

        refs.append(
            {
                "source": lbl,
                "league": lg,
                "home": str(home),
                "away": str(away),
                "kickoff": ko,
                "kickoff_utc": ko.isoformat(),
                "x12": x12,
                "ou": ou_val,
                "fetched_utc": ts,
            }
        )
    return refs


def fetch_oddspapi_references(
    dates: Iterable[str],
    *,
    api_key: str | None = None,
    timeout: int = 20,
) -> list[dict[str, Any]]:
    """Fetch upcoming football odds from OddsPapi when ``ODDSPAPI_KEY`` is configured."""
    key = api_key or os.environ.get("ODDSPAPI_KEY", "").strip()
    if not key:
        return []

    date_list = sorted(set(dates))
    if not date_list:
        return []
    params = {
        "apiKey": key,
        "sportId": 10,  # Football / Soccer
        "from": f"{date_list[0]}T00:00:00Z",
        "to": f"{date_list[-1]}T23:59:59Z",
    }
    try:
        r = requests.get(f"{ODDSPAPI_BASE}/fixtures", params=params, timeout=timeout)
        if r.status_code != 200:
            return []
        payload = r.json()
    except (requests.RequestException, ValueError):
        return []

    items = payload if isinstance(payload, list) else (payload.get("fixtures") or payload.get("data") or [])
    return parse_oddspapi_fixtures(items)
