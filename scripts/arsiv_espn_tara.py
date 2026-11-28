"""ESPN herkese açık scoreboard'dan geçmiş günleri sıkıştırılmış satırlara indirir (ham JSON saklanmaz).

``/soccer/all/scoreboard?dates=YYYYMMDD&limit=1000`` günde 1 istek (limit=1000 şart: varsayılan 100'de yoğun günler kesilir).
Yalnız biten erkek/açık yaş maçları; satır: gün, ESPN lig kimliği, sezon-lig slug'ı, ev, dep, skorlar, durum (FT/AET/PEN).
Devam edilebilir (ay başına bir ``.jsonl.gz``; mevcut tam aylar atlanır). Kullanım:
    python scripts/arsiv_espn_tara.py --bas 2003-01-01 --bit 2026-11-27 --cikti /workspace/arsiv_ham/espn
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)"}
SKIP = ("ncaa", "women", "womens", "-w-", "nwsl", "wsl")


def compact(payload: dict) -> list[dict]:
    out = []
    for e in payload.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type", {})
        if not st.get("completed"):
            continue
        slug = (e.get("season") or {}).get("slug", "")
        if any(s in slug for s in SKIP):
            continue
        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        try:
            h, a = cs["home"], cs["away"]
            lid = e["uid"].split("~")[1].replace("l:", "")
            out.append({"d": e["date"][:10], "l": lid, "s": slug, "h": h["team"]["displayName"], "a": a["team"]["displayName"],
                        "hg": int(h["score"]), "ag": int(a["score"]), "st": st.get("shortDetail", "FT")[:8], "id": e.get("id")})
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return out


def fetch_day(day: dt.date, s: requests.Session) -> list[dict] | None:
    for t in range(4):
        try:
            r = s.get(URL, params={"dates": day.strftime("%Y%m%d"), "limit": 1000}, timeout=40)
            if r.status_code == 200:
                return compact(r.json())
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (t + 1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bas", required=True)
    ap.add_argument("--bit", required=True)
    ap.add_argument("--cikti", type=Path, required=True)
    ap.add_argument("--is", dest="workers", type=int, default=6)
    a = ap.parse_args()
    a.cikti.mkdir(parents=True, exist_ok=True)
    d0, d1 = dt.date.fromisoformat(a.bas), dt.date.fromisoformat(a.bit)
    months = sorted({(d.year, d.month) for d in (d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1))}, reverse=True)
    s = requests.Session()
    s.headers.update(UA)
    for y, m in months:
        f = a.cikti / f"{y}-{m:02d}.jsonl.gz"
        first = dt.date(y, m, 1)
        last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        lo, hi = max(first, d0), min(last, d1)
        if f.exists() and (hi < dt.date.today() - dt.timedelta(days=3)) and lo == first and hi == last:
            continue
        days = [lo + dt.timedelta(days=i) for i in range((hi - lo).days + 1)]
        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(lambda d: fetch_day(d, s), days))
        if any(r is None for r in res):
            print(f"{y}-{m:02d}: {sum(r is None for r in res)} gün alınamadı, ay yazılmadı", flush=True)
            continue
        rows = [r for part in res for r in part]
        with gzip.open(f, "wt", encoding="utf-8") as g:
            for r in rows:
                g.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{y}-{m:02d}: {len(rows)} maç", flush=True)


if __name__ == "__main__":
    sys.exit(main())
