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


def _squad(summary: dict, team_id: str) -> dict[str, dict]:
    """Matchday squad (starters + bench) of one team with per-match red cards: id -> record."""
    for r in summary.get("rosters") or []:
        if str(r.get("team", {}).get("id")) == str(team_id):
            out = {}
            for p in r.get("roster", []):
                if not p.get("athlete"):
                    continue
                st = {x.get("name"): x.get("value") for x in p.get("stats") or []}
                out[str(p["athlete"]["id"])] = {"name": p["athlete"].get("displayName"), "starter": bool(p.get("starter")),
                                                "pos": (p.get("position") or {}).get("abbreviation", ""),
                                                "red": int(st.get("redCards") or 0)}
            return out
    return {}


def likely_absentees(squads: list[dict[str, dict]]) -> list[dict]:
    """Infer injured / suspended players before the line-up is out, from the last matchday squads
    (oldest first): a player who started >= 3 of them but is not even on the bench in the latest one,
    or who was sent off in the latest one."""
    if len(squads) < 3:
        return []
    latest, previous = squads[-1], squads[-2]
    starts: dict[str, int] = {}
    info: dict[str, dict] = {}
    for sq in squads:
        for pid, p in sq.items():
            info[pid] = p
            starts[pid] = starts.get(pid, 0) + int(p["starter"])
    out = []
    for pid, n in starts.items():
        p = info[pid]
        if n >= 3 and pid not in latest:
            gone = 2 if pid not in previous else 1
            out.append({"name": p["name"], "pos": p["pos"], "reason": f"son {gone} maçta kadroda yok (muhtemel sakat/cezalı)",
                        "starts": n})
        elif pid in latest and latest[pid]["red"]:
            out.append({"name": p["name"], "pos": p["pos"], "reason": "son maçta kırmızı kart (cezalı olabilir)", "starts": n})
    single = [x for x in out if x["reason"].startswith("son 1 maçta")]
    if len(single) >= 4:  # several regulars out at once in one game = rotation (cup / fixture congestion), not injuries
        for x in single:
            x["reason"] = "son maçta kadroda yok (rotasyon olabilir)"
    return sorted(out, key=lambda x: -x["starts"])


def _player_stats(athlete: dict) -> dict:
    out = {}
    for cat in (athlete.get("statistics") or {}).get("splits", {}).get("categories", []):
        for st in cat.get("stats", []):
            out[st["name"]] = st.get("value") or 0.0
    return out


@lru_cache(maxsize=1024)
def team_profile(slug: str, team_id: str) -> dict | None:
    """Season player data for one team: top scorers, first-choice goalkeeper (save %), card counts."""
    js = _get(f"{BASE}/{slug}/teams/{team_id}/roster")
    if not js or not js.get("athletes"):
        return None
    players = []
    for a in js["athletes"]:
        st = _player_stats(a)
        players.append({"name": a.get("displayName"), "pos": (a.get("position") or {}).get("abbreviation", ""),
                        "apps": int(st.get("appearances", 0)), "goals": int(st.get("totalGoals", 0)),
                        "assists": int(st.get("goalAssists", 0)), "yellow": int(st.get("yellowCards", 0)),
                        "red": int(st.get("redCards", 0)), "saves": int(st.get("saves", 0)),
                        "conceded": int(st.get("goalsConceded", 0))})
    scorers = sorted((p for p in players if p["goals"] > 0), key=lambda p: (-p["goals"], -p["assists"]))[:3]
    assisters = sorted((p for p in players if p["assists"] > 0), key=lambda p: (-p["assists"], -p["goals"]))[:3]
    keepers = sorted((p for p in players if p["pos"] == "G" and p["apps"] > 0), key=lambda p: -p["apps"])
    gk = None
    if keepers:
        k = keepers[0]
        faced = k["saves"] + k["conceded"]
        gk = {"name": k["name"], "apps": k["apps"], "save_pct": round(k["saves"] / faced, 3) if faced else None,
              "conceded_per_game": round(k["conceded"] / k["apps"], 2) if k["apps"] else None}
    cards = sorted((p for p in players if p["yellow"] >= 4 or p["red"] > 0), key=lambda p: (-p["red"], -p["yellow"]))[:4]
    return {"top_scorers": scorers, "top_assists": assisters, "goalkeeper": gk, "cards": cards}


_NEWS_RE = re.compile(r"injur|ruled out|out for|sidelined|suspen|\bban\b|banned|doubt|fitness|hamstring|knee|ankle|"
                      r"groin|calf|thigh|surgery|absence|absent|miss(?:es|ing)? (?:the|next|out)|red card|sent off", re.I)


@lru_cache(maxsize=1024)
def team_news(slug: str, team_id: str) -> list[str]:
    """Latest ESPN team headlines that mention injuries, suspensions or absences."""
    js = _get(f"{BASE}/{slug}/news", team=team_id, limit=15) or {}
    out = []
    for a in js.get("articles", []):
        text = f"{a.get('headline', '')} {a.get('description', '')}"
        if _NEWS_RE.search(text):
            out.append(a.get("headline") or text[:120])
    return out[:4]


CORE = "https://sports.core.api.espn.com/v2/sports/soccer/leagues"
TEAM_STATS = {  # ESPN name -> (Turkish label, per game?)
    "possessionPct": ("Topla oynama", False), "totalShots": ("Şut", True), "shotsOnTarget": ("İsabetli şut", True),
    "avgExpectedGoals": ("xG (beklenen gol)", False), "avgExpectedGoalsConceded": ("xGA (beklenen yenen gol)", False),
    "avgGoals": ("Gol", False), "avgGoalsConceded": ("Yenen gol", False), "bigChanceCreated": ("Net pozisyon", True),
    "wonCorners": ("Korner", True), "cleanSheet": ("Gol yemeden biten maç", False), "shotsFaced": ("Rakip şutu", True),
    "yellowCards": ("Sarı kart", True), "redCards": ("Kırmızı kart", False), "foulsCommitted": ("Faul", True),
    "passPct": ("Pas isabeti", False), "tacklePct": ("Top kapma başarısı", False), "homeGoals": ("İç sahada gol", False),
    "awayGoals": ("Deplasmanda gol", False),
}


@lru_cache(maxsize=1024)
def team_stats(slug: str, year: int, team_id: str) -> dict[str, str]:
    """Season team statistics (possession, shots, xG/xGA, big chances, corners, clean sheets, cards...)."""
    js = _get(f"{CORE}/{slug}/seasons/{year}/types/1/teams/{team_id}/statistics")
    stats: dict[str, float] = {}
    for cat in ((js or {}).get("splits") or {}).get("categories", []):
        for st in cat.get("stats", []):
            stats[st["name"]] = st.get("value")
    games = stats.get("appearances") or 0
    out = {}
    for key, (label, per_game) in TEAM_STATS.items():
        v = stats.get(key)
        if v is None:
            continue
        if per_game and games:
            out[label] = f"{v / games:.1f} / maç"
        elif key.endswith("Pct"):  # ESPN mixes 0-1 fractions and 0-100 percentages
            out[label] = f"%{v * 100:.0f}" if v <= 1 else f"%{v:.1f}"
        else:
            out[label] = f"{v:.2f}" if isinstance(v, float) and not float(v).is_integer() else f"{int(v)}"
    return out


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
                                       "wins": st.get("wins"), "draws": st.get("ties"), "losses": st.get("losses"),
                                       "goal_diff": st.get("pointDifferential"), "size": len(entries)}

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
        squads = []
        for g in sorted(games, key=lambda x: x.get("gameDate") or ""):  # oldest first
            gs = _summary(str(g.get("id"))) if g.get("id") else None
            for p in _starters(gs, tid) if gs else []:
                c = counts.setdefault(p["id"], {**p, "starts": 0})
                c["starts"] += 1
            if gs:
                sq = _squad(gs, tid)
                if sq:
                    squads.append(sq)
        rec["likely_absent"] = likely_absentees(squads)
        rec["regulars"] = [c for c in counts.values() if c["starts"] >= REGULAR_MIN_STARTS]
        today = _starters(s, tid)
        rec["lineup_announced"] = len(today) >= 11
        if rec["lineup_announced"]:
            ids = {p["id"] for p in today}
            rec["missing_regulars"] = [c for c in rec["regulars"] if c["id"] not in ids]
            ts = rec["top_scorer"]
            rec["top_scorer_missing"] = bool(ts and ts["id"] not in ids)
            rec["goalkeeper_changed"] = any(c["pos"] == "G" for c in rec["missing_regulars"])
        season = {}
        for bt in (s.get("boxscore") or {}).get("teams", []):
            if str((bt.get("team") or {}).get("id")) == tid:
                season = {x["name"]: x.get("displayValue") for x in bt.get("statistics", [])}
        played = (rec.get("table") or {}).get("played")
        rec["season"] = {"goals_for": season.get("totalGoals"), "goals_against": season.get("goalsConceded"),
                         "goal_diff": season.get("goalDifference"), "played": played}
        if out["league_slug"]:
            rec["profile"] = team_profile(out["league_slug"], tid)
            rec["news_flags"] = team_news(out["league_slug"], tid)
            year = ((s.get("header") or {}).get("season") or {}).get("year")
            if year:
                rec["team_stats"] = team_stats(out["league_slug"], int(year), tid)
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


def enrich_with_soccerdata(
    res: dict,
    *,
    league: str | None = None,
    season: str | int | None = None,
    sources: tuple[str, ...] = ("clubelo", "understat", "espn"),
    client=None,
) -> dict:
    """Attach optional ``probberechts/soccerdata`` context (ClubElo, Understat xG, ESPN) to a research dict."""
    from quantfoot.data.soccerdata_bridge import SoccerDataClient

    teams = res.get("teams") or {}
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    league_ref = league or res.get("league_slug")
    if not home or not away or not league_ref:
        return res

    sd_client = client if client is not None else SoccerDataClient()
    ctx = sd_client.enrich_match(home, away, league_ref, season=season, sources=sources)
    enriched = dict(res)
    enriched["soccerdata"] = ctx.to_dict()
    return enriched
