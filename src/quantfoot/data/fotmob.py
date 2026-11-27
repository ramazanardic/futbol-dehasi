"""FotMob (resmî olmayan, herkese açık JSON) — kullanıcı onayı 21 Kasım (t27u).

Kurallar: yalnız analiz edilen maçlar için; agresif önbellek; istekler arası nazik bekleme; kimliğini açıkça
belirten ortak User-Agent; bot korumasını aşma girişimi yok. Bayrak: ``QUANTFOOT_FOTMOB`` (tüm geçerli
``QUANTFOOT_AI`` klasörleri için varsayılan eşit olarak açık; ``0`` ile kapatılabilir).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import time
from typing import Any

from quantfoot.data.match_dossier import CachedHttp, team_match_score
from quantfoot.paths import VALID_AIS

BASE = "https://www.fotmob.com/api/data"
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)", "Accept": "application/json"}


def enabled(environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    raw = env.get("QUANTFOOT_FOTMOB")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "evet", "on", "yes")
    return env.get("QUANTFOOT_AI", "").strip() in VALID_AIS


class FotMob:
    def __init__(self, http: CachedHttp, delay_s: float = 1.0) -> None:
        self.http = http
        self.delay_s = delay_s
        self._last = 0.0

    def _polite(self) -> None:
        wait = self.delay_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def matches_on(self, day: dt.date, ttl_s: float = 1800) -> dict | None:
        body = self.http.get(f"{BASE}/matches", {"date": day.strftime("%Y%m%d")}, UA, ttl_s, self._polite)
        return body if isinstance(body, dict) else None

    def details(self, match_id: int | str, ttl_s: float = 1800) -> dict | None:
        body = self.http.get(f"{BASE}/matchDetails", {"matchId": str(match_id)}, UA, ttl_s, self._polite)
        return body if isinstance(body, dict) else None


def _num(x: Any) -> float | None:
    if x is None:
        return None
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(x))
    return float(m.group(1)) if m else None


def parse_minute(live_time: dict | None) -> float | None:
    if not live_time:
        return None
    long_ = str(live_time.get("long") or "")
    m = re.match(r"(\d+):(\d+)", long_)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60.0
    s = re.sub(r"[^\d+]", "", str(live_time.get("short") or ""))
    if s.upper() == "" and "HT" in str(live_time.get("short", "")).upper():
        return 45.0
    try:
        return float(s.split("+")[0]) if s else None
    except ValueError:
        return None


def parse_matches(payload: dict, live_only: bool = False) -> list[dict]:
    out = []
    for lg in (payload or {}).get("leagues") or []:
        for m in lg.get("matches") or []:
            st = m.get("status") or {}
            if live_only and not st.get("ongoing"):
                continue
            out.append({"id": m.get("id"), "league": lg.get("name"), "home": (m.get("home") or {}).get("name"),
                        "away": (m.get("away") or {}).get("name"), "hg": (m.get("home") or {}).get("score"),
                        "ag": (m.get("away") or {}).get("score"), "ongoing": bool(st.get("ongoing")),
                        "finished": bool(st.get("finished")), "minute": parse_minute(st.get("liveTime")),
                        "utc": st.get("utcTime")})
    return out


def find_match(matches: list[dict], home: str, away: str, min_score: float = 0.72) -> dict | None:
    best, score = None, 0.0
    for m in matches:
        s = min(team_match_score(home, m["home"] or ""), team_match_score(away, m["away"] or ""))
        if s > score:
            best, score = m, s
    return best if score >= min_score else None


_STAT_KEYS = {"expected_goals": "xg", "total_shots": "shots", "ShotsOnTarget": "sot", "corners": "corners",
              "BallPossesion": "possession", "big_chance": "big_chances", "red_cards": "red"}


def parse_details(payload: dict) -> dict[str, Any]:
    c = (payload or {}).get("content") or {}
    header = (payload or {}).get("header") or {}
    st = header.get("status") or {}
    out: dict[str, Any] = {"red": [st.get("numberOfHomeRedCards") or 0, st.get("numberOfAwayRedCards") or 0],
                           "stats": {"home": {}, "away": {}}}
    teams = header.get("teams") or []
    if len(teams) == 2:
        out["score"] = [teams[0].get("score"), teams[1].get("score")]
    periods = ((c.get("stats") or {}).get("Periods") or {}).get("All") or {}
    for grp in periods.get("stats") or []:
        for s in grp.get("stats") or []:
            k = _STAT_KEYS.get(s.get("key"))
            vals = s.get("stats") or []
            if k and len(vals) == 2 and vals[0] is not None and k not in out["stats"]["home"]:
                out["stats"]["home"][k], out["stats"]["away"][k] = _num(vals[0]), _num(vals[1])
    info = ((c.get("matchFacts") or {}).get("infoBox")) or {}
    if info.get("Referee"):
        out["referee"] = info["Referee"].get("text")
    if info.get("Stadium"):
        sd = info["Stadium"]
        out["stadium"] = {"name": sd.get("name"), "city": sd.get("city"), "lat": sd.get("lat"), "lon": sd.get("long")}
    lu = c.get("lineup") or {}
    if lu:
        out["lineup_type"] = lu.get("lineupType")
        for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
            t = lu.get(key) or {}
            starter_details = []
            for p in t.get("starters") or []:
                perf = p.get("performance") or {}
                rating = _num(perf.get("rating") if isinstance(perf, dict) else p.get("rating"))
                starter_details.append({
                    "name": p.get("name"),
                    "position_id": p.get("positionId"),
                    "usual_pos": p.get("usualPlayingPositionId"),
                    "rating": rating,
                })
            out[f"{side}_lineup"] = {
                "formation": t.get("formation"),
                "rating": _num(t.get("rating")),
                "starters": [p.get("name") for p in t.get("starters") or []],
                "starter_details": starter_details,
                "unavailable": [
                    {
                        "name": p.get("name"),
                        "reason": ((p.get("unavailability") or {}).get("type")),
                        "expected_return": ((p.get("unavailability") or {}).get("expectedReturn")),
                    }
                    for p in t.get("unavailable") or []
                ],
            }
    if c.get("weather"):
        w = c["weather"]
        out["weather"] = {"temp_c": w.get("temperature"), "wind": w.get("windSpeed"), "precip": w.get("precipitation"),
                          "desc": w.get("description")}
    return out
