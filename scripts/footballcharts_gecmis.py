"""Team history from Football Charts (football-charts.com) — 98 leagues incl. lower divisions, every result with the
half-time score and the first-goal minute (user decision, 21 Nov).

Free API, personal use, attribution required (football-charts.com/developers): 25 requests a day without a key,
200 with a free key (FC_API_KEY in the environment or the git-ignored .env). One request returns a whole league
season, cached 12 h in data/cache/footballcharts, so a day's research costs one request per league.

    python scripts/footballcharts_gecmis.py --tarih 2026-11-20   # fill the day's derin_tahminler.json where history is missing

Data: Football Charts (https://www.football-charts.com).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402
import wiki_gecmis as wg  # noqa: E402

BASE = "https://footballcharts-backend.onrender.com/api/v1/leagues/{league}/results/"
CACHE = dr.ROOT / "data" / "cache" / "footballcharts"
TTL_H = 12.0
N_RECENT = 15

# Nesine league name prefix -> Football Charts league id (longest prefix wins)
LEAGUES = {
    "Cezayir 1. Lig": "algir1", "Avustralya A-Lig": "australia", "Avusturya Bundesliga": "austria1", "Avusturya 2. Lig": "austria2",
    "Azerbaycan Premier Lig": "azer", "Belçika Pro Lig": "belgium1", "Belçika 2. Lig": "belgium2", "Brezilya Serie A": "brazil1",
    "Brezilya Serie B": "brazil2", "Bulgaristan Parva Ligi": "bulgaria1", "İngiltere 1. Lig": "cha", "Çin Süper Lig": "china",
    "Çekya 1. Lig": "czech1", "Çekya 2. Lig": "czech2", "Danimarka Süper Ligi": "denmark1", "Danimarka 1. Lig": "denmark2",
    "İngiltere U21": "develop21", "Mısır Premier Lig": "egypt", "İngiltere 2. Lig": "eng1", "İngiltere 3. Lig": "eng2",
    "Estonya": "estonia", "Finlandiya Veikkausliiga": "finland1", "Fransa Ligue 1": "france1", "Fransa Ligue 2": "france2",
    "Fransa 3. Lig": "france3", "Almanya Böl. Lig, Kuzey ": "germany-north", "Almanya Bundesliga 2": "germany2",
    "Almanya Bundesliga": "germany1", "Almanya 3. Lig": "germany3", "Yunanistan Süper Lig 2": "greece2",
    "Yunanistan Süper Lig": "greece1", "Hollanda Eredivisie": "holland1", "Hollanda 1. Lig": "holland2", "Hollanda 2. Lig": "holland3",
    "Macaristan NB I.": "hungary1", "Macaristan NB II.": "hungary2", "Hindistan Süper Ligi": "india1",
    "İrlanda Premier Lig": "ireland1", "İrlanda 1. Lig": "ireland2", "İtalya Serie A": "italy1", "İtalya Primavera": "italy19",
    "İtalya Serie B": "italy2", "Japonya J1": "japan1", "Japonya J2": "japan2", "Güney Kore K Lig 1": "korea1",
    "Güney Kore K Lig 2": "korea2", "Kuveyt": "kuwait", "Letonya Virsliga": "latvia", "Litvanya": "lithuania", "Fas Botola": "morocco",
    "İngiltere Ulusal Lig Kuzey": "north", "İngiltere Ulusal Lig Güney": "south", "İngiltere Ulusal Lig": "national",
    "Norveç Eliteserien": "norway", "Polonya Ekstraklasa": "poland1", "Polonya 1. Lig": "poland2", "Portekiz Liga": "portugal1",
    "Portekiz 2. Lig": "portugal2", "İngiltere Premier Lig": "premier", "Romanya 1. Lig": "romania1", "Rusya Premier Ligi": "russia",
    "Suudi Arabistan Pro Lig": "saudi1", "Suudi Arabistan 1. Lig": "saudi2", "İskoçya Championship": "scot-champ",
    "İskoçya Premiership": "scot-premier", "İskoçya 1. Lig": "scot1", "İskoçya 2. Lig": "scot2", "Sırbistan Süper Lig": "serbia1",
    "Slovakya 1. Lig": "slovakia1", "Slovakya 2. Lig": "slovakia2", "Slovenya 1. Lig": "slovenia1", "İspanya La Liga": "spain1",
    "İspanya 2. Lig": "spain2", "İsveç Allsvenskan": "sweden1", "İsveç Superettan": "sweden2", "İsviçre Süper Ligi": "swiss1",
    "İsviçre Challenge Ligi": "swiss2", "Tayland": "thai1", "Türkiye Süper Lig": "turkey1", "Türkiye 1. Lig": "turkey2",
    "ABD Major Lig": "usa1",
}
SPLIT = {"İtalya Serie C": ("italy3a", "italy3b"), "Çekya 3. Lig": ("czech3a", "czech3b"),
         "İspanya Primera RFEF": ("primera1", "primera2"),
         "İspanya 2. Federasyon": ("segunda1", "segunda2", "segunda3", "segunda4", "segunda5")}


def leagues_for(league: str) -> tuple[str, ...]:
    hits = [k for k in LEAGUES if league.startswith(k)]
    if hits:
        return (LEAGUES[max(hits, key=len)],)
    return next((v for k, v in SPLIT.items() if league.startswith(k)), ())


def _key() -> str:
    k = os.environ.get("FC_API_KEY", "").strip()
    env = dr.ROOT / ".env"
    if not k and env.exists():
        k = next((ln.split("=", 1)[1].strip() for ln in env.read_text(encoding="utf-8").splitlines()
                  if ln.startswith("FC_API_KEY=")), "")
    return k


def results(league: str) -> list[dict]:
    f = CACHE / f"{league}.json"
    if not (f.exists() and time.time() - f.stat().st_mtime < TTL_H * 3600):
        k = _key()
        try:
            r = requests.get(BASE.format(league=league), timeout=60,
                             headers={"Authorization": f"Bearer {k}"} if k else {})
            if r.status_code == 200 and "matches" in r.text[:400]:
                CACHE.mkdir(parents=True, exist_ok=True)
                f.write_text(r.text, encoding="utf-8")
        except requests.RequestException:
            pass  # daily limit / offline: keep whatever is cached
    return json.loads(f.read_text(encoding="utf-8")).get("matches", []) if f.exists() else []


def _score(s: str | None) -> tuple[int, int] | None:
    try:
        a, b = (s or "").split(":")
        return int(a), int(b)
    except ValueError:
        return None


def team_games(team: str, rows: list[dict], before: dt.datetime) -> list[dict]:
    """Last finished games of a team with half scores, in derin_arastirma's oriented form."""
    out = []
    for r in sorted(rows, key=lambda x: x.get("kickoff_utc") or x["date"]):
        if team not in (r["homeTeam"], r["awayTeam"]):
            continue
        t = dt.datetime.fromisoformat((r.get("kickoff_utc") or r["date"] + "T00:00:00Z").replace("Z", "+00:00"))
        ft, ht = _score(r.get("score")), _score(r.get("ht_result"))
        if t >= before or not ft or not ht or ht[0] > ft[0] or ht[1] > ft[1]:
            continue
        side = "home" if r["homeTeam"] == team else "away"
        i, j = (0, 1) if side == "home" else (1, 0)
        out.append({"event": r.get("id"), "date": r["date"], "side": side, "opp": r["awayTeam" if side == "home" else "homeTeam"],
                    "opp_id": r["awayTeam" if side == "home" else "homeTeam"],
                    "for": (ht[i], ft[i] - ht[i]), "against": (ht[j], ft[j] - ht[j])})
    return out[-N_RECENT:]


def research(row: dict, m: dict) -> bool:
    """Fill a research row (no ESPN history) from Football Charts; True when both teams were found."""
    rows = [x for lg in leagues_for(row.get("league") or m.get("league") or "") for x in results(lg)]
    if not rows:
        return False
    names = {t: t for t in {r["homeTeam"] for r in rows} | {r["awayTeam"] for r in rows}}
    hc, ac = wg.match_team(m["home"], names), wg.match_team(m["away"], names)
    if not hc or not ac or hc == ac:
        return False
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    hg, ag = team_games(hc, rows, kick), team_games(ac, rows, kick)
    if not hg or not ag:
        return False
    row["footballcharts"] = {"home": hc, "away": ac}
    row["games"], row["games_ft_only"] = {"home": hg, "away": ag}, False
    row.setdefault("teams", {}).setdefault("home", {}).update(dr.profile(hg))
    row["teams"].setdefault("away", {}).update(dr.profile(ag))
    row["teams"]["home"]["source"] = row["teams"]["away"]["source"] = "Football Charts"
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
    print(f"Football Charts: {len(found)} maçta takım geçmişi bulundu; tablo {dtah.update_table(args.tarih, rows)} satır")
    for x in found:
        print("  +", x)


if __name__ == "__main__":
    main()
