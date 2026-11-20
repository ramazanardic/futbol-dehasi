"""Team history from Open Matchday (github.com/oladeeayo/open-matchday) for leagues ESPN does not cover (user
decision, 21 Nov: "open matchdayi kur").

Open Matchday publishes the 2026/27 results of 75 competitions as CSV, updated daily, free for non-commercial use
with attribution (its DISCLAIMER.md). Many of the smaller leagues there (Welsh, Polish, Danish, Belgian U21 …) were
compiled from Soccerway; we only read the repository's published CSV files and never contact Soccerway. Half-time
scores are present for part of the matches only, so half bets are tested on the matches that have them and
full-time bets on all of them. Files are cached for 6 h in data/cache/openmatchday (git-ignored).

    python scripts/openmatchday_gecmis.py --tarih 2026-11-20   # fill the day's derin_tahminler.json where history is missing

Data: Open Matchday (https://github.com/oladeeayo/open-matchday), with the providers it credits.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from pathlib import Path
import sys
import time

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402
import wiki_gecmis as wg  # noqa: E402

RAW = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data/{folder}/results_2627.csv"
CACHE = dr.ROOT / "data" / "cache" / "openmatchday"
TTL_H = 6.0
N_RECENT = 15

# Nesine league name prefix -> Open Matchday folder (longest prefix wins)
FOLDERS = {
    "Galler Premier Lig": "WAL_1_cymru-premier", "Galler Championship, Kuzey": "WAL_2_cymru-north",
    "Galler Championship, Güney": "WAL_3_cymru-south", "Belçika U21": "BEL_U21_pro-league",
    "Belçika Pro Lig": "BEL_1_pro-league", "Polonya Ekstraklasa": "POL_1_ekstraklasa", "Polonya 1. Lig": "POL_2_division-1",
    "Polonya 2. Lig": "POL_3_division-2", "Danimarka Süper Ligi": "DEN_1_superliga", "Norveç Eliteserien": "NOR_1_eliteserien",
    "İsveç Allsvenskan": "SWE_1_allsvenskan", "Romanya 1. Lig": "ROU_1_liga-1", "Çekya 1. Lig": "CZE_1_chance-liga",
    "Slovenya 1. Lig": "SVN_1_prva-liga", "Hırvatistan 1. Lig": "CRO_1_hnl", "Ukrayna Premier Ligi": "UKR_1_premier-league",
    "Kıbrıs 1. Lig": "CYP_1_first-division", "Slovakya 1. Lig": "SVK_1_nike-liga", "Finlandiya Veikkausliiga": "FIN_1_veikkausliiga",
    "Kazakistan Premier Ligi": "KAZ_1_premier-league", "İsviçre Süper Ligi": "SUI_1_super-league",
    "Avusturya Bundesliga": "AUT_1_bundesliga", "Rusya Premier Ligi": "RUS_1_premier-liga",
    "İrlanda 1. Lig": "IRE_2_first-division", "İngiltere Ulusal Lig Kuzey": "ENG_6_national-league-north",
    "İngiltere Ulusal Lig Güney": "ENG_6_national-league-south", "İngiltere Ulusal Lig": "ENG_5_national-league",
    "İskoçya Championship": "SCO_2_championship", "İskoçya 1. Lig": "SCO_3_league-one", "İskoçya 2. Lig": "SCO_4_league-two",
    "İngiltere 2. Lig": "ENG_3_league-one", "İngiltere 1. Lig": "ENG_2_championship", "İngiltere 3. Lig": "ENG_4_league-two",
    "Türkiye Süper Lig": "TUR_1_super-lig", "Yunanistan Süper Lig": "GRE_1_super-league", "İspanya 2. Lig": "ESP_2_segunda-division",
    "İtalya Serie B": "ITA_2_serie-b", "Fransa Ligue 2": "FRA_2_ligue-2", "Hollanda 1. Lig": "NED_2_eerste-divisie",
    "Almanya 3. Lig": "GER_3_3-liga", "Almanya Bundesliga 2": "GER_2_2-bundesliga",
}


def folder_for(league: str) -> str | None:
    hits = [k for k in FOLDERS if league.startswith(k)]
    return FOLDERS[max(hits, key=len)] if hits else None


def results(folder: str) -> list[dict]:
    f = CACHE / f"{folder}.csv"
    if not (f.exists() and time.time() - f.stat().st_mtime < TTL_H * 3600):
        try:
            r = requests.get(RAW.format(folder=folder), timeout=30)
            if r.status_code == 200 and r.text.startswith("gw,"):
                CACHE.mkdir(parents=True, exist_ok=True)
                f.write_text(r.text, encoding="utf-8")
        except requests.RequestException:
            pass
    if not f.exists():
        return []
    return list(csv.DictReader(io.StringIO(f.read_text(encoding="utf-8"))))


def _int(x: str) -> int | None:
    return int(x) if (x or "").strip().isdigit() else None


def team_games(team: str, rows: list[dict], before: dt.datetime) -> list[dict]:
    """Last finished games of a team in derin_arastirma's oriented form; first half None when not published."""
    out = []
    for r in sorted(rows, key=lambda x: (x["date"], x.get("time") or "")):
        if team not in (r["home"], r["away"]) or dt.date.fromisoformat(r["date"]) >= before.date():
            continue
        fh, fa, hh, ha = _int(r["ft_home"]), _int(r["ft_away"]), _int(r.get("ht_home")), _int(r.get("ht_away"))
        if fh is None or fa is None:
            continue
        side = "home" if r["home"] == team else "away"
        me, op = ((fh, hh), (fa, ha)) if side == "home" else ((fa, ha), (fh, hh))
        half = me[1] is not None and op[1] is not None and me[1] <= me[0] and op[1] <= op[0]
        out.append({"event": f"{r['date']}:{r['home']}-{r['away']}", "date": r["date"], "side": side,
                    "opp": r["away"] if side == "home" else r["home"], "opp_id": r["away"] if side == "home" else r["home"],
                    "for": (me[1], me[0] - me[1]) if half else (None, me[0]),
                    "against": (op[1], op[0] - op[1]) if half else (None, op[0])})
    return out[-N_RECENT:]


def leg_history(name: str, hg: list[dict], ag: list[dict]) -> dict:
    """Full-time bets on every game (home team at home, away team away); half bets on the games with half scores."""
    ft = lambda g: {**g, "for": (None, sum(x or 0 for x in g["for"])), "against": (None, sum(x or 0 for x in g["against"]))}  # noqa: E731
    hist = wg.leg_history(name, [ft(g) for g in hg], [ft(g) for g in ag])
    if hist["mean"] is not None:
        return hist
    hh = [g for g in hg if g["for"][0] is not None and g["side"] == "home"]
    ah = [g for g in ag if g["for"][0] is not None and g["side"] == "away"]
    return dr.leg_history(name, hh, ah) if hh and ah else hist


def research(row: dict, m: dict) -> bool:
    """Fill a research row (no ESPN history) from Open Matchday; True when both teams were found."""
    folder = folder_for(row.get("league") or m.get("league") or "")
    rows = results(folder) if folder else []
    if not rows:
        return False
    names = {t: t for t in {r["home"] for r in rows} | {r["away"] for r in rows}}
    hc, ac = wg.match_team(m["home"], names), wg.match_team(m["away"], names)
    if not hc or not ac or hc == ac:
        return False
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    hg, ag = team_games(hc, rows, kick), team_games(ac, rows, kick)
    if not hg or not ag:
        return False
    row["openmatchday"] = {"folder": folder, "home": hc, "away": ac}
    row["games"], row["games_ft_only"] = {"home": hg, "away": ag}, True
    ftg = lambda gs: [{**g, "for": (None, sum(x or 0 for x in g["for"])), "against": (None, sum(x or 0 for x in g["against"]))} for g in gs]  # noqa: E731
    row.setdefault("teams", {}).setdefault("home", {}).update(wg.profile(ftg(hg)))
    row["teams"].setdefault("away", {}).update(wg.profile(ftg(ag)))
    row["teams"]["home"]["source"] = row["teams"]["away"]["source"] = "Open Matchday"
    row["h2h"] = [f"{g['date']}: {hc} {sum(x or 0 for x in g['for'])}-{sum(x or 0 for x in g['against'])} {ac}"
                  for g in hg if g["opp"] == ac]
    for leg in row.get("legs") or []:
        hist = leg_history(leg["name"], hg, ag)
        leg.update(hist)
        leg["verdict"] = wg.verdict(leg.get("p"), hist)
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
        if r.get("espn") or not r.get("legs") or any(not x["verdict"].startswith("geçmiş") for x in r["legs"]):
            continue  # already tested on a source with more detail
        if research(r, ms[str(r["code"])]):
            found.append(r["match"])
            r["pick"], r["dropped"] = dtah.choose(r["legs"]), [x for x in r["legs"] if x["verdict"].startswith("⚠")]
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(dtah.to_markdown(args.tarih, rows), encoding="utf-8")
    print(f"Open Matchday: {len(found)} maçta takım geçmişi bulundu; tablo {dtah.update_table(args.tarih, rows)} satır")
    for x in found:
        print("  +", x)


if __name__ == "__main__":
    main()
