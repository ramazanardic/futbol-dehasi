"""ESPN maç özetinden (``/soccer/<slug>/summary?event=<id>``) İY skoru ve maç istatistikleri (korner, şut, isabetli şut,
faul, sarı/kırmızı) indirir (28 Kas 2026, veri kapsam Faz 3).

Maç kimlikleri lig scoreboard'undan (gün başına 1 istek) gelir; her biten maç için 1 özet isteği. Nazik hız (~3/sn),
devam edilebilir (inen kimlikler atlanır). Saklanan: yalnız olgusal sayılar; ham JSON saklanmaz. Kaynakta olmayan
alan BOŞ yazılır (uydurulmaz).

    python scripts/espn_detay_tara.py --lig nor.1 swe.1 --bas 2025-01-01 --bit 2026-11-28 --cikti /workspace/arsiv_ham/espn_detay
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import time
from pathlib import Path

import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/{what}"
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)"}
STATS = {"wonCorners": "c", "totalShots": "s", "shotsOnTarget": "st", "foulsCommitted": "f", "yellowCards": "y",
         "redCards": "r"}


def _get(s: requests.Session, url: str, params: dict, gap: float) -> dict | None:
    for t in range(3):
        try:
            r = s.get(url, params=params, timeout=30)
            time.sleep(gap)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 404):
                return None
        except (requests.RequestException, ValueError):
            time.sleep(2 * (t + 1))
    return None


def _int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def detail(d: dict) -> dict:
    out: dict = {}
    comp = (d.get("header", {}).get("competitions") or [{}])[0]
    for c in comp.get("competitors") or []:
        side = "h" if c.get("homeAway") == "home" else "a"
        ls = c.get("linescores") or []
        out[f"ht_{side}"] = _int(ls[0].get("displayValue")) if len(ls) >= 2 else None
    for t in (d.get("boxscore") or {}).get("teams") or []:
        side = "h" if t.get("homeAway") == "home" else "a"
        for st in t.get("statistics") or []:
            if st.get("name") in STATS:
                out[f"{STATS[st['name']]}_{side}"] = _int(st.get("displayValue"))
    return out


def run(slug: str, start: dt.date, end: dt.date, out: Path, gap: float = 0.3) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{slug}.jsonl.gz"
    done = {}
    if f.exists():
        with gzip.open(f, "rt", encoding="utf-8") as g:
            for ln in g:
                r = json.loads(ln)
                done[r["id"]] = r
    s = requests.Session()
    s.headers.update(UA)
    day, new = start, 0
    while day <= end:
        sb = _get(s, BASE.format(slug=slug, what="scoreboard"), {"dates": day.strftime("%Y%m%d"), "limit": 200}, gap) or {}
        for e in sb.get("events") or []:
            comp = (e.get("competitions") or [{}])[0]
            if not (comp.get("status") or {}).get("type", {}).get("completed") or e.get("id") in done:
                continue
            cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
            try:
                row = {"id": e["id"], "d": e["date"][:10], "t": e["date"][11:16], "l": slug,
                       "h": cs["home"]["team"]["displayName"], "a": cs["away"]["team"]["displayName"],
                       "hg": int(cs["home"]["score"]), "ag": int(cs["away"]["score"])}
            except (KeyError, ValueError, TypeError):
                continue
            sm = _get(s, BASE.format(slug=slug, what="summary"), {"event": e["id"]}, gap)
            if sm:
                row.update(detail(sm))
            done[e["id"]] = row
            new += 1
        if new and new % 200 == 0:
            _save(f, done)
        day += dt.timedelta(days=1)
    _save(f, done)
    return {"lig": slug, "mac": len(done), "yeni": new}


def _save(f: Path, done: dict) -> None:
    with gzip.open(f, "wt", encoding="utf-8") as g:
        for r in sorted(done.values(), key=lambda x: (x["d"], x["t"])):
            g.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lig", nargs="+", required=True)
    ap.add_argument("--bas", type=dt.date.fromisoformat, required=True)
    ap.add_argument("--bit", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--cikti", type=Path, default=Path("/workspace/arsiv_ham/espn_detay"))
    a = ap.parse_args()
    for slug in a.lig:
        print(json.dumps(run(slug, a.bas, a.bit, a.cikti)), flush=True)


if __name__ == "__main__":
    main()
