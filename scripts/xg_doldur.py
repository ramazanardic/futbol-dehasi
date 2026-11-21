"""Gerçek xG'yi yavaşça biriktir: API-Football /fixtures?id= (biten maçın istatistiği `expected_goals` içerir).

    QUANTFOOT_AI=grokbottahmin python scripts/xg_doldur.py --butce 10     # günde en çok 10 istek

Yalnız önbellekteki dün/bugün fikstürlerinden (tam_analiz.py doldurur) seçilen liglerin biten maçları. Ortak
kota koruması (data/cache/dossier/af_quota.json) aşılmaz; maç öncesi analiz için yer bırakır.
Çıktı: data/xg/api_football_xg.csv (takım-maç satırı: tarih, lig, takım, rakip, ev/dep, gol, xG, şut, isabetli).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.match_dossier import ApiFootball, CachedHttp, QuotaExceeded  # noqa: E402

OUT = ROOT / "data" / "xg" / "api_football_xg.csv"
FIELDS = ["date", "fixture_id", "league_id", "league", "team", "opponent", "venue", "goals", "xg", "shots", "sot"]
PRIORITY = [203, 39, 140, 135, 78, 61, 88, 94, 144, 179, 40, 204, 2, 3, 848]  # Süper Lig, büyük 5, ...


def parse_fixture_xg(fx: dict) -> list[dict]:
    rows = []
    stats = {s["team"]["id"]: {x["type"]: x["value"] for x in s.get("statistics") or []} for s in fx.get("statistics") or []}
    h, a = fx["teams"]["home"], fx["teams"]["away"]
    for team, opp, venue, g in ((h, a, "home", fx["goals"]["home"]), (a, h, "away", fx["goals"]["away"])):
        st = stats.get(team["id"]) or {}
        xg = st.get("expected_goals")
        if xg in (None, ""):
            continue
        rows.append({"date": fx["fixture"]["date"][:10], "fixture_id": fx["fixture"]["id"], "league_id": fx["league"]["id"],
                     "league": fx["league"]["name"], "team": team["name"], "opponent": opp["name"], "venue": venue,
                     "goals": g, "xg": float(xg), "shots": st.get("Total Shots"), "sot": st.get("Shots on Goal")})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--butce", type=int, default=10)
    ap.add_argument("--kota", type=int, default=80, help="ortak günlük koruma sınırı (maç öncesine yer bırak)")
    args = ap.parse_args()
    for env in (ROOT / ".env", Path("/workspace/futbol-dehasi/.env")):
        if env.exists():
            import os
            for line in env.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break
    http = CachedHttp()
    api = ApiFootball(http, daily_limit=args.kota)
    done = set()
    if OUT.exists():
        done = {int(r["fixture_id"]) for r in csv.DictReader(OUT.open())}
    today = dt.datetime.now(dt.timezone.utc).date()
    cands = []
    for d in (today - dt.timedelta(days=1), today):
        for f in (http.peek("https://v3.football.api-sports.io/fixtures", {"date": d.isoformat()}) or {}).get("response") or []:
            if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN") and f["league"]["id"] in PRIORITY and f["fixture"]["id"] not in done:
                cands.append(f)
    cands.sort(key=lambda f: PRIORITY.index(f["league"]["id"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new = 0
    with OUT.open("a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if fh.tell() == 0:
            w.writeheader()
        for f in cands[: args.butce]:
            try:
                resp = api.get("fixtures", {"id": f["fixture"]["id"]}, None)
            except QuotaExceeded as exc:
                print(f"Durdu: {exc}")
                break
            for fx in resp:
                for r in parse_fixture_xg(fx):
                    w.writerow(r)
                    new += 1
    print(f"Aday {len(cands)}, yazılan takım-maç satırı {new}, bugün kullanılan API-Football (bu araçlarla) {api.used_today()}")


if __name__ == "__main__":
    main()
