"""Team history from OpenLigaDB (api.openligadb.de) — German leagues incl. Regionalliga Nordost and the women's
Bundesliga, every finished match with its half-time score (user decision, 21 Nov).

Keyless, ODbL (attribution required: "Daten: OpenLigaDB, ODbL"). The provider asks for at most one query per league
per 30–60 s during live matches; one request returns a whole league season, cached 6 h in data/cache/openligadb.

    python scripts/openligadb_gecmis.py --tarih 2026-11-20   # fill the day's derin_tahminler.json where history is missing

Data: OpenLigaDB (https://www.openligadb.de), Open Database License.
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

BASE = "https://api.openligadb.de/getmatchdata/{league}/{season}"
CACHE = dr.ROOT / "data" / "cache" / "openligadb"
TTL_H = 6.0
N_RECENT = 15
# Nesine league name prefix -> OpenLigaDB shortcut (longest prefix wins)
LEAGUES = {"Almanya Bundesliga 2": "bl2", "Almanya Bundesliga": "bl1", "Almanya 3. Lig": "bl3",
           "Almanya Böl. Lig, Kuzey Doğu": "rlno", "Almanya Kadınlar Bundesliga 2": "ffb2",
           "Almanya Kadınlar Bundesliga": "ffb1", "Almanya Kadınlar 2. Bundesliga": "ffb2"}


def league_for(league: str) -> str | None:
    hits = [k for k in LEAGUES if league.startswith(k)]
    return LEAGUES[max(hits, key=len)] if hits else None


def season_of(day: dt.date) -> int:
    return day.year if day.month >= 7 else day.year - 1


def matches(league: str, season: int) -> list[dict]:
    f = CACHE / f"{league}_{season}.json"
    if not (f.exists() and time.time() - f.stat().st_mtime < TTL_H * 3600):
        try:
            r = requests.get(BASE.format(league=league, season=season), timeout=60)
            if r.status_code == 200 and r.text.startswith("["):
                CACHE.mkdir(parents=True, exist_ok=True)
                f.write_text(r.text, encoding="utf-8")
        except requests.RequestException:
            pass
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def _result(m: dict, type_id: int) -> tuple[int, int] | None:
    r = next((x for x in m.get("matchResults") or [] if x.get("resultTypeID") == type_id), None)
    return (int(r["pointsTeam1"]), int(r["pointsTeam2"])) if r else None


def team_games(team: str, rows: list[dict], before: dt.datetime) -> list[dict]:
    out = []
    for m in sorted(rows, key=lambda x: x.get("matchDateTimeUTC") or ""):
        h, a = m["team1"]["teamName"], m["team2"]["teamName"]
        if team not in (h, a) or not m.get("matchIsFinished"):
            continue
        t = dt.datetime.fromisoformat(m["matchDateTimeUTC"].replace("Z", "+00:00"))
        ht, ft = _result(m, 1), _result(m, 2)
        if t >= before or not ht or not ft or ht[0] > ft[0] or ht[1] > ft[1]:
            continue
        side = "home" if h == team else "away"
        i, j = (0, 1) if side == "home" else (1, 0)
        out.append({"event": m["matchID"], "date": m["matchDateTimeUTC"][:10], "side": side, "opp": a if side == "home" else h,
                    "opp_id": a if side == "home" else h, "for": (ht[i], ft[i] - ht[i]), "against": (ht[j], ft[j] - ht[j])})
    return out[-N_RECENT:]


def research(row: dict, m: dict) -> bool:
    """Fill a research row (no ESPN history) from OpenLigaDB; True when both teams were found."""
    lg = league_for(row.get("league") or m.get("league") or "")
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    rows = matches(lg, season_of(kick.date())) if lg else []
    if not rows:
        return False
    names = {t: t for x in rows for t in (x["team1"]["teamName"], x["team2"]["teamName"])}
    clean = lambda s: s.replace("(K)", "").replace("(Amt)", " II").strip()  # noqa: E731 — Nesine women / reserve marks
    hc, ac = wg.match_team(clean(m["home"]), names), wg.match_team(clean(m["away"]), names)
    if not hc or not ac or hc == ac:
        return False
    hg, ag = team_games(hc, rows, kick), team_games(ac, rows, kick)
    if not hg or not ag:
        return False
    row["openligadb"] = {"league": lg, "home": hc, "away": ac}
    row["games"], row["games_ft_only"] = {"home": hg, "away": ag}, False
    row.setdefault("teams", {}).setdefault("home", {}).update(dr.profile(hg))
    row["teams"].setdefault("away", {}).update(dr.profile(ag))
    row["teams"]["home"]["source"] = row["teams"]["away"]["source"] = "OpenLigaDB"
    row["h2h"] = [f"{g['date']}: {hc} {sum(g['for'])}-{sum(g['against'])} {ac} (İY {g['for'][0]}-{g['against'][0]})"
                  for g in hg if g["opp"] == ac]
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
    found = []
    for r in rows:
        if r.get("espn") or not r.get("legs") or str(r["code"]) not in ms:
            continue
        if research(r, ms[str(r["code"])]):
            found.append(r["match"])
            r["pick"], r["dropped"] = dtah.choose(r["legs"]), [x for x in r["legs"] if x["verdict"].startswith("⚠")]
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(dtah.to_markdown(args.tarih, rows), encoding="utf-8")
    print(f"OpenLigaDB: {len(found)} maçta takım geçmişi bulundu; tablo {dtah.update_table(args.tarih, rows)} satır")
    for x in found:
        print("  +", x)


if __name__ == "__main__":
    main()
