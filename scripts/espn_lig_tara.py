"""ESPN herkese açık lig scoreboard'undan (``/soccer/<slug>/scoreboard?dates=YYYYMMDD``) biten maçları indirir.

``/soccer/all`` taraması (scripts/arsiv_espn_tara.py) bazı ligleri eksik getiriyor (ör. por.1 2026/27: 27 maç); lig
bazlı uç tam liste verir. Günde lig başına 1 istek, nazik hız (~3 istek/sn). Yalnız sonuç satırı saklanır; ESPN bu
uçta İY skoru vermez, bu yüzden iy_* BOŞ kalır (uydurulmaz).

    python scripts/espn_lig_tara.py --lig por.1 rus.1 --bas 2026-07-01 --bit 2026-11-28 --cikti /workspace/arsiv_ham/espn_lig
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import time
from pathlib import Path

import requests

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)"}


def compact(payload: dict, slug: str) -> list[dict]:
    out = []
    for e in payload.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type", {})
        if not st.get("completed"):
            continue
        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        try:
            h, a = cs["home"], cs["away"]
            out.append({"d": e["date"][:10], "t": e["date"][11:16], "l": slug, "h": h["team"]["displayName"],
                        "a": a["team"]["displayName"], "hg": int(h["score"]), "ag": int(a["score"]),
                        "st": st.get("shortDetail", "FT")[:8], "id": e.get("id")})
        except (KeyError, ValueError, TypeError):
            continue
    return out


def fetch(slug: str, day: dt.date, s: requests.Session) -> list[dict] | None:
    for t in range(3):
        try:
            r = s.get(URL.format(slug=slug), params={"dates": day.strftime("%Y%m%d"), "limit": 200}, timeout=30)
            if r.status_code == 200:
                return compact(r.json(), slug)
            if r.status_code in (400, 404):
                return []
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (t + 1))
    return None


def run(slugs: list[str], start: dt.date, end: dt.date, out: Path, gap: float = 0.3) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    res = {}
    for slug in slugs:
        rows, seen, fail = [], set(), 0
        day = start
        while day <= end:
            got = fetch(slug, day, s)
            if got is None:
                fail += 1
            for r in got or []:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    rows.append(r)
            day += dt.timedelta(days=1)
            time.sleep(gap)
        with gzip.open(out / f"{slug}.jsonl.gz", "wt", encoding="utf-8") as g:
            for r in sorted(rows, key=lambda x: (x["d"], x["t"])):
                g.write(json.dumps(r, ensure_ascii=False) + "\n")
        res[slug] = {"mac": len(rows), "basarisiz_gun": fail}
        print(slug, res[slug], flush=True)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lig", nargs="+", required=True)
    ap.add_argument("--bas", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--bit", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--cikti", type=Path, default=Path("/workspace/arsiv_ham/espn_lig"))
    a = ap.parse_args()
    run(a.lig, a.bas, a.bit, a.cikti)


if __name__ == "__main__":
    main()
