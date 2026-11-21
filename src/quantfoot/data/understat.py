"""Understat gerçek xG — sayfadaki gömülü ``JSON.parse('...')`` bloklarını çözer (resmî API yok).

21 Kasım 2026 durumu: understat.com bu bilgisayardan "We will come back soon" bakım sayfası döndürüyor;
ayrıştırıcı hazır, site dönünce kendiliğinden çalışır. Bot koruması aşılmaz; düz GET + önbellek.
Ligler: EPL, La_liga, Bundesliga, Serie_A, Ligue_1, RFPL.
"""

from __future__ import annotations

import codecs
import json
import re
from typing import Any

from quantfoot.data.match_dossier import CachedHttp, team_match_score

BASE = "https://understat.com"
UA = {"User-Agent": "QuantFoot-GrokBot/1.0 (kisisel futbol arastirmasi)"}
LEAGUES = {39: "EPL", 140: "La_liga", 78: "Bundesliga", 135: "Serie_A", 61: "Ligue_1", 235: "RFPL"}
_BLOB = re.compile(r"var\s+(\w+)\s*=\s*JSON\.parse\('((?:[^'\\]|\\.)*)'\)")


def extract_json_blobs(html: str) -> dict[str, Any]:
    """``var teamsData = JSON.parse('\\x7B...')`` → {"teamsData": {...}}."""
    out: dict[str, Any] = {}
    for name, raw in _BLOB.findall(html or ""):
        try:
            text = codecs.decode(raw, "unicode_escape")
            out[name] = json.loads(text)
        except (ValueError, UnicodeDecodeError):
            continue
    return out


def team_xg_form(teams_data: dict, team: str, last_n: int = 6) -> dict[str, Any] | None:
    """teamsData'dan takımın son ``last_n`` maç xG / xGA ortalaması (gerçek şut bazlı xG)."""
    best, score = None, 0.0
    for t in (teams_data or {}).values():
        s = team_match_score(team, t.get("title", ""))
        if s > score:
            best, score = t, s
    if not best or score < 0.72:
        return None
    hist = best.get("history") or []
    recent = hist[-last_n:]
    if not recent:
        return None
    xg = [float(h.get("xG", 0)) for h in recent]
    xga = [float(h.get("xGA", 0)) for h in recent]
    goals = [float(h.get("scored", 0)) for h in recent]
    conc = [float(h.get("missed", 0)) for h in recent]
    n = len(recent)
    return {"team": best.get("title"), "n": n, "xg": round(sum(xg) / n, 2), "xga": round(sum(xga) / n, 2),
            "goals": round(sum(goals) / n, 2), "conceded": round(sum(conc) / n, 2),
            "flag": ("şansın üstünde gol atıyor (gerileme beklenir)" if sum(goals) - sum(xg) > 0.5 * n else
                     "şansın altında gol atıyor (yükseliş beklenir)" if sum(xg) - sum(goals) > 0.5 * n else None)}


def league_teams(http: CachedHttp, league_id: int, season_start_year: int) -> tuple[dict | None, str]:
    code = LEAGUES.get(league_id)
    if not code:
        return None, "lig Understat'ta yok"
    html = http.get(f"{BASE}/league/{code}/{season_start_year}", None, UA, ttl_s=12 * 3600)
    if not isinstance(html, str):
        return None, "erişilemedi"
    blobs = extract_json_blobs(html)
    if "teamsData" not in blobs:
        return None, "sayfada veri yok (bakım sayfası olabilir)"
    return blobs["teamsData"], "tamam"
