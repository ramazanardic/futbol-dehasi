"""ESPN lig kimliği -> slug/ad tablosu (data/arsiv/espn_ligler.csv). Core API ``/soccer/leagues`` (220 lig, herkese açık)."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)"}


def main() -> None:
    s = requests.Session()
    s.headers.update(UA)
    items = s.get("https://sports.core.api.espn.com/v2/sports/soccer/leagues", params={"limit": 1000}, timeout=40).json()["items"]
    rows = []
    for it in items:
        ref = it["$ref"].replace("http://", "https://")
        for t in range(3):
            try:
                d = s.get(ref, timeout=30).json()
                rows.append({"id": d.get("id", ""), "slug": d.get("slug", ""), "ad": d.get("name", ""), "kisa": d.get("abbreviation", ""),
                             "turnuva": d.get("isTournament", "")})
                break
            except (requests.RequestException, ValueError):
                time.sleep(2)
        time.sleep(0.1)
    out = ROOT / "data" / "arsiv" / "espn_ligler.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "slug", "ad", "kisa", "turnuva"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["slug"]))
    print(len(rows), "lig ->", out)


if __name__ == "__main__":
    sys.exit(main())
