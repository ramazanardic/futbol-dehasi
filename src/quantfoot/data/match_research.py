"""Match research from ESPN's free keyless site API: form, rest, head-to-head, table, line-ups, absences.

Used next to the global price, never instead of it: the sharp price already contains public team news,
so the research is (1) context for the report and (2) a staleness guard — when a regular starter (above
all the goalkeeper or the top scorer) is missing from an announced line-up that was published after our
global price was fetched, the price may not include that news yet and the match is kept out of coupons.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
import re

import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
UA = {"User-Agent": "Mozilla/5.0 (QuantFoot research)"}
REGULAR_MIN_STARTS = 4  # started >= 4 of the last 5 league games -> regular starter


def _get(url: str, **params) -> dict | None:
    try:
        r = requests.get(url, params=params or None, headers=UA, timeout=15)
        return r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError):
        return None


def espn_events(date_str: str) -> list[dict]:
    """All soccer events ESPN lists for a YYYYMMDD date: id, league slug, home, away, kickoff (UTC)."""
    js = _get(f"{BASE}/all/scoreboard", dates=date_str) or {}
    out = []
    for e in js.get("events", []):
        comp = (e.get("competitions") or [{}])[0]
        teams = {c.get("homeAway"): c.get("team", {}).get("displayName") for c in comp.get("competitors", [])}
        try:
            ko = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if teams.get("home") and teams.get("away"):
            out.append({"id": e["id"], "home": teams["home"], "away": teams["away"], "kickoff": ko,
                        "uid": e.get("uid", "")})
    return out


@lru_cache(maxsize=4096)
def _summary(event_id: str) -> dict | None:
    return _get(f"{BASE}/all/summary", event=event_id)  # "all" resolves any competition


def _starters(summary: dict, team_id: str) -> list[dict]:
    for r in summary.get("rosters") or []:
        if str(r.get("team", {}).get("id")) == str(team_id):
            return [{"id": str(p["athlete"]["id"]), "name": p["athlete"].get("displayName"),
                     "pos": (p.get("position") or {}).get("abbreviation", "")}
                    for p in r.get("roster", []) if p.get("starter") and p.get("athlete")]
    return []


def research(event_id: str) -> dict | None:
    """Research record for one ESPN event, or None when ESPN has no summary for it."""
    s = _summary(event_id)
    if not s:
        return None
    header = (s.get("header") or {}).get("competitions", [{}])[0]
    kickoff = header.get("date")
    teams = {c.get("homeAway"): c.get("team", {}) for c in header.get("competitors", [])}
    out: dict = {"espn_event": event_id, "league_slug": ((s.get("header") or {}).get("league") or {}).get("slug"), "teams": {}}

    table = {}
    groups = (s.get("standings") or {}).get("groups") or []
    for g in groups:
        entries = (g.get("standings") or {}).get("entries") or []
        for e in entries:
            st = {x["name"]: x.get("value") for x in e.get("stats", []) if "name" in x}
            table[str(e.get("id"))] = {"rank": st.get("rank"), "points": st.get("points"), "played": st.get("gamesPlayed"),
                                       "size": len(entries)}

    leaders = {}
    for block in s.get("leaders") or []:
        tid = str(block.get("team", {}).get("id"))
        for cat in block.get("leaders", []):
            if cat.get("name") == "goalsLeaders" and cat.get("leaders"):
                a = cat["leaders"][0].get("athlete", {})
                leaders[tid] = {"id": str(a.get("id")), "name": a.get("displayName"), "value": cat["leaders"][0].get("displayValue")}

    for block in s.get("lastFiveGames") or []:
        tid = str(block.get("team", {}).get("id"))
        side = next((k for k, t in teams.items() if str(t.get("id")) == tid), None)
        if side is None:
            continue
        games = block.get("events", [])
        rec = {"name": block["team"].get("displayName"), "form": "".join(g.get("gameResult", "?") for g in games),
               "last5": [f"{g.get('gameResult')} {g.get('score')} {g.get('atVs')} {(g.get('opponent') or {}).get('displayName')}"
                         for g in games],
               "table": table.get(tid), "top_scorer": leaders.get(tid)}
        dates = sorted(g.get("gameDate") for g in games if g.get("gameDate"))
        if dates and kickoff:
            last = dt.datetime.fromisoformat(dates[-1].replace("Z", "+00:00"))
            rec["rest_days"] = round((dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00")) - last).total_seconds() / 86400, 1)
        # regular starters from the previous five games (same team id)
        counts: dict[str, dict] = {}
        for g in games:
            gs = _summary(str(g.get("id"))) if g.get("id") else None
            for p in _starters(gs, tid) if gs else []:
                c = counts.setdefault(p["id"], {**p, "starts": 0})
                c["starts"] += 1
        rec["regulars"] = [c for c in counts.values() if c["starts"] >= REGULAR_MIN_STARTS]
        today = _starters(s, tid)
        rec["lineup_announced"] = len(today) >= 11
        if rec["lineup_announced"]:
            ids = {p["id"] for p in today}
            rec["missing_regulars"] = [c for c in rec["regulars"] if c["id"] not in ids]
            ts = rec["top_scorer"]
            rec["top_scorer_missing"] = bool(ts and ts["id"] not in ids)
            rec["goalkeeper_changed"] = any(c["pos"] == "G" for c in rec["missing_regulars"])
        out["teams"][side] = rec

    series = (s.get("seasonseries") or [{}])[0] if s.get("seasonseries") else {}
    out["h2h"] = series.get("summary")
    out["news"] = [a.get("headline") for a in (s.get("news") or {}).get("articles", [])[:3]]
    return out


def motivation(rec: dict, league_slug: str | None) -> str | None:
    """Table-pressure label for domestic leagues (ESPN slugs like 'bra.1'); None for cups and league phases."""
    t = rec.get("table") or {}
    rank, size = t.get("rank"), t.get("size")
    if not rank or not size or size < 8 or not re.fullmatch(r"[a-z]{3}\.\d", league_slug or ""):
        return None
    band = max(2, round(size * 0.2))  # top / bottom fifth of the table
    zone = "zirve yarışı" if rank <= band else "küme hattı" if rank > size - band else "orta sıralar"
    return f"{int(rank)}./{size} ({zone}, {int(t.get('points') or 0)} puan)"


def staleness_flags(res: dict, price_time: dt.datetime | None) -> list[str]:
    """Reasons the global price may predate important team news (empty list = no concern)."""
    flags = []
    for side, rec in (res.get("teams") or {}).items():
        if not rec.get("lineup_announced"):
            continue
        who = "Ev" if side == "home" else "Dep"
        if rec.get("goalkeeper_changed"):
            flags.append(f"{who}: düzenli kaleci ilk 11'de yok")
        if rec.get("top_scorer_missing"):
            flags.append(f"{who}: gol kralı ({rec['top_scorer']['name']}) ilk 11'de yok")
        if len(rec.get("missing_regulars") or []) >= 3:
            flags.append(f"{who}: {len(rec['missing_regulars'])} düzenli oyuncu ilk 11'de yok")
    if flags and price_time is not None and dt.datetime.now(dt.timezone.utc) - price_time > dt.timedelta(minutes=75):
        flags.append("global fiyat ilk 11 açıklanmadan önce çekilmiş olabilir")
    return flags


# ---- Premier League availability (official Fantasy Premier League feed: free, keyless) ----------------
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
_FPL_STATUS = {"i": "sakat", "s": "cezalı", "d": "şüpheli", "u": "kadro dışı", "n": "oynayamaz"}


@lru_cache(maxsize=1)
def fpl_availability() -> dict[str, list[dict]]:
    """Team name -> unavailable/doubtful players, with a 'key' flag for regular starters (FPL starts share)."""
    js = _get(FPL_URL)
    if not js:
        return {}
    teams = {t["id"]: t["name"] for t in js.get("teams", [])}
    max_starts: dict[int, int] = {}
    for e in js.get("elements", []):
        max_starts[e["team"]] = max(max_starts.get(e["team"], 0), int(e.get("starts") or 0))
    out: dict[str, list[dict]] = {}
    for e in js.get("elements", []):
        if e.get("status") not in ("i", "s", "d", "n"):
            continue
        top = max_starts.get(e["team"]) or 1
        out.setdefault(teams[e["team"]], []).append({
            "name": e.get("web_name"), "status": _FPL_STATUS.get(e["status"], e["status"]),
            "chance": e.get("chance_of_playing_next_round"), "news": e.get("news"),
            "goals": e.get("goals_scored"), "key": int(e.get("starts") or 0) >= 0.6 * top})
    return out
