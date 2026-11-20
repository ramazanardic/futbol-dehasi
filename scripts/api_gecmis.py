"""Team history from API-Football for matches ESPN does not cover (user request, 20 Nov: research every match).

The key is read from the environment or from the repo's .env (API_FOOTBALL_KEY; .env is git-ignored, never commit
it). Free plan: 100 requests a day, so the calls are few and cached in data/cache/api_football:

* /fixtures?date=<day>            one call per day -> fixture and team ids (matched on kick-off ±20 min + names)
* /fixtures?team=<id>&last=15     one call per team (cached 12 h) -> last 15 results WITH half-time scores

The games come out in scripts/derin_arastirma.py's form, so its leg test and verdicts apply unchanged.

    python scripts/api_gecmis.py --tarih 2026-11-20     # fill the day's derin_tahminler.json where history is missing
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

BASE = "https://v3.football.api-sports.io"
CACHE = dr.ROOT / "data" / "cache" / "api_football"
TEAM_TTL_H = 12.0
DAY_TTL_H = 3.0
N_RECENT = 15


def api_key() -> str:
    key = os.environ.get("API_FOOTBALL_KEY", "").strip()
    env = dr.ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("API_FOOTBALL_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


class ApiError(RuntimeError):
    """The API refused the call (suspended account, daily limit, bad key)."""


def get(path: str, ttl_h: float, **params) -> list[dict]:
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists() and time.time() - f.stat().st_mtime < ttl_h * 3600:
        return json.loads(f.read_text(encoding="utf-8"))
    k = api_key()
    if not k:
        raise ApiError("API_FOOTBALL_KEY yok")
    try:
        j = requests.get(f"{BASE}/{path}", params=params, headers={"x-apisports-key": k}, timeout=30).json()
    except (requests.RequestException, ValueError) as e:
        raise ApiError(f"bağlantı: {type(e).__name__}") from e
    if j.get("errors"):
        raise ApiError(str(j["errors"]))
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j.get("response") or []), encoding="utf-8")
    return j.get("response") or []


def _sim(a: str, b: str) -> float:
    n = lambda s: " ".join(t for t in s.lower().replace(".", " ").replace("-", " ").split() if len(t) > 2)  # noqa: E731
    return difflib.SequenceMatcher(None, n(a), n(b)).ratio()


def find_fixture(m: dict, fixtures: list[dict]) -> dict | None:
    """The day's fixture of a Nesine match: kick-off within 20 minutes and both team names alike."""
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    best, score = None, 0.0
    for fx in fixtures:
        try:
            t = dt.datetime.fromisoformat(fx["fixture"]["date"])
        except (KeyError, ValueError):
            continue
        if abs((t - kick).total_seconds()) > 1200:
            continue
        sc = _sim(m["home"], fx["teams"]["home"]["name"]) + _sim(m["away"], fx["teams"]["away"]["name"])
        if sc > score:
            best, score = fx, sc
    return best if score >= 1.0 else None


def team_games(team_id: int, before: dt.datetime) -> list[dict]:
    """Last finished games of a team before ``before``, oriented to it, with half scores (derin_arastirma form)."""
    games = []
    for fx in sorted(get("fixtures", TEAM_TTL_H, team=team_id, last=N_RECENT), key=lambda x: x["fixture"]["date"]):
        if (fx["fixture"].get("status") or {}).get("short") not in ("FT", "AET", "PEN"):
            continue
        if dt.datetime.fromisoformat(fx["fixture"]["date"]) >= before:
            continue
        ht, ft = fx["score"].get("halftime") or {}, fx["score"].get("fulltime") or {}
        if None in (ht.get("home"), ht.get("away"), ft.get("home"), ft.get("away")):
            continue
        side = "home" if fx["teams"]["home"]["id"] == team_id else "away"
        opp = "away" if side == "home" else "home"
        games.append({"event": fx["fixture"]["id"], "date": fx["fixture"]["date"][:10], "side": side,
                      "opp": fx["teams"][opp]["name"], "opp_id": fx["teams"][opp]["id"],
                      "for": (ht[side], ft[side] - ht[side]), "against": (ht[opp], ft[opp] - ht[opp])})
    return games


def research(row: dict, m: dict, fixtures: list[dict]) -> bool:
    """Fill a research row (derin_arastirma form) from API-Football; True when both teams' games were found."""
    fx = find_fixture(m, fixtures)
    if not fx:
        return False
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    hg, ag = team_games(fx["teams"]["home"]["id"], kick), team_games(fx["teams"]["away"]["id"], kick)
    if not hg or not ag:
        return False
    row["api_football"] = {"fixture": fx["fixture"]["id"], "league": (fx.get("league") or {}).get("name")}
    row.setdefault("teams", {}).setdefault("home", {}).update(dr.profile(hg))
    row["teams"].setdefault("away", {}).update(dr.profile(ag))
    away_id = fx["teams"]["away"]["id"]
    row["h2h"] = [f"{g['date']}: {m['home']} {sum(g['for'])}-{sum(g['against'])} (İY {g['for'][0]}-{g['against'][0]})"
                  for g in hg if g["opp_id"] == away_id]
    for leg in row.get("legs") or []:
        hist = dr.leg_history(leg["name"], hg, ag)
        leg.update(hist)
        leg["verdict"] = dr.verdict(leg.get("p"), hist)
    return True


def day_fixtures(date: str) -> list[dict]:
    return get("fixtures", DAY_TTL_H, date=date, timezone="Europe/Istanbul")


def main() -> None:
    import derin_tahmin as dtah
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    args = ap.parse_args()
    out = dr.AREA / args.tarih
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    try:
        fixtures = day_fixtures(args.tarih)
    except ApiError as e:
        print(f"API-Football kullanılamıyor: {e}")
        return
    found = 0
    for r in rows:
        if r.get("espn") or not r.get("legs"):
            continue
        if any(not x["verdict"].startswith("geçmiş yetersiz") for x in r["legs"]):
            continue  # already tested on another source
        try:
            ok = research(r, ms[str(r["code"])], fixtures)
        except ApiError as e:
            print(f"API-Football durdu: {e}")
            break
        if ok:
            found += 1
            r["pick"], r["dropped"] = dtah.choose(r["legs"]), [x for x in r["legs"] if x["verdict"].startswith("⚠")]
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(dtah.to_markdown(args.tarih, rows), encoding="utf-8")
    print(f"API-Football: {found} maçta takım geçmişi bulundu; tablo {dtah.update_table(args.tarih, rows)} satır")


if __name__ == "__main__":
    main()
