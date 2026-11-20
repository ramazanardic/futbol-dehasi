"""Season results with half-time scores from openfootball/football.json (CC0 public domain; user request, 21 Nov).

https://github.com/openfootball/football.json serves one JSON per league and season, e.g. 2026-27/en.1.json, with
date, teams and {"ht": [h, a], "ft": [h, a]} for every played match. It covers the top divisions of England (1 and 2),
Germany, Spain, France, Italy, the Netherlands and Portugal. Files are read from raw.githubusercontent.com and cached
6 h in data/cache/openfootball.

Because the half scores are there, a team's games come out in scripts/derin_arastirma.py's form and every bet — half
bets too — is settled with its own leg test (last 15 games, home team at home / away team away kept as in ESPN).

    python scripts/openfootball_gecmis.py --tarih 2026-11-20    # fill derin_tahminler.json where history is missing
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402
import wiki_gecmis as wg  # noqa: E402

RAW = "https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json"
CACHE = dr.ROOT / "data" / "cache" / "openfootball"
TTL_H = 6.0
# Nesine league name (exact, spaces stripped) -> openfootball league file
LEAGUES = {"İngiltere Premier Lig": "en.1", "İngiltere Championship": "en.2", "Almanya Bundesliga": "de.1",
           "İspanya La Liga": "es.1", "Fransa Ligue 1": "fr.1", "İtalya Serie A": "it.1", "Hollanda Eredivisie": "nl.1",
           "Portekiz Süper Lig": "pt.1", "Portekiz Premier Lig": "pt.1"}


def season_of(day: dt.date) -> str:
    """'2026-27' for a date in the 2026/27 European season (July-June)."""
    y = day.year if day.month >= 7 else day.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def league_file(league: str, day: dt.date) -> list[dict]:
    code = LEAGUES.get((league or "").strip())
    if not code:
        return []
    season = season_of(day)
    f = CACHE / f"{season}_{code}.json"
    if f.exists() and time.time() - f.stat().st_mtime < TTL_H * 3600:
        return json.loads(f.read_text(encoding="utf-8"))
    try:
        r = requests.get(RAW.format(season=season, code=code), timeout=30)
        data = r.json().get("matches", []) if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        data = []
    if data:
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data), encoding="utf-8")
    return data


def played(matches: list[dict], before: dt.date) -> list[dict]:
    out = []
    for x in matches:
        sc = x.get("score") or {}
        if sc.get("ft") and sc.get("ht") and x.get("date") and dt.date.fromisoformat(x["date"]) < before:
            out.append(x)
    return sorted(out, key=lambda x: x["date"])


def team_games(team: str, matches: list[dict], n: int = dr.N_RECENT) -> list[dict]:
    """A team's last n played games in derin_arastirma's oriented form (half scores included)."""
    games = []
    for x in matches:
        if team not in (x["team1"], x["team2"]):
            continue
        side = "home" if x["team1"] == team else "away"
        i, j = (0, 1) if side == "home" else (1, 0)
        ht, ft = x["score"]["ht"], x["score"]["ft"]
        games.append({"event": f"{x['date']}_{x['team1']}", "date": x["date"], "side": side,
                      "opp": x["team2"] if side == "home" else x["team1"],
                      "opp_id": x["team2"] if side == "home" else x["team1"],
                      "for": (ht[i], ft[i] - ht[i]), "against": (ht[j], ft[j] - ht[j])})
    return games[-n:]


def research(row: dict, m: dict) -> bool:
    """Fill a research row from openfootball; True when both teams were found."""
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    games = played(league_file(m["league"], kick.date()), kick.date())
    if not games:
        return False
    names = {t: t for x in games for t in (x["team1"], x["team2"])}
    home, away = wg.match_team(m["home"], names), wg.match_team(m["away"], names)
    if not home or not away or home == away:
        return False
    hg, ag = team_games(home, games), team_games(away, games)
    row["openfootball"] = {"home": home, "away": away}
    row["games"], row["games_ft_only"] = {"home": hg, "away": ag}, False
    row.setdefault("teams", {}).setdefault("home", {}).update(dr.profile(hg))
    row["teams"].setdefault("away", {}).update(dr.profile(ag))
    row["h2h"] = [f"{g['date']}: {m['home']} {sum(g['for'])}-{sum(g['against'])} (İY {g['for'][0]}-{g['against'][0]})"
                  for g in hg if g["opp"] == away]
    for leg in row.get("legs") or []:
        hist = dr.leg_history(leg["name"], hg, ag)
        leg.update(hist)
        leg["verdict"] = dr.verdict(leg.get("p"), hist)
    return True


def main() -> None:
    import derin_tahmin as dtah
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    args = ap.parse_args()
    out = dr.AREA / args.tarih
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    found = 0
    for r in rows:
        m = ms.get(str(r["code"]))
        if not m or r.get("espn") or not r.get("legs"):
            continue
        if any(not x["verdict"].startswith("geçmiş yetersiz") for x in r["legs"]):
            continue  # already tested on another source
        if research(r, m):
            found += 1
            r["pick"], r["dropped"] = dtah.choose(r["legs"]), [x for x in r["legs"] if x["verdict"].startswith("⚠")]
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"openfootball: {found} maçta takım geçmişi bulundu; tablo {dtah.update_table(args.tarih, rows)} satır")


if __name__ == "__main__":
    main()
