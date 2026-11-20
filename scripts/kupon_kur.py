"""Build a coupon the safe way (user rules, 20 Nov): direct-price legs only and deep research on every leg before the
coupon is given.

    python scripts/kupon_kur.py --hedef 5
    python scripts/kupon_kur.py --hedef 10 --min-mac 4 -- --hic-kullanilmamis --mac-limit 2

Each round runs scripts/nesine_kupon.py (direct-price legs by default), then scripts/derin_arastirma.py's checks on
every leg. A leg is ruled out and the coupon rebuilt (up to --tur rounds) when the leg's own bet clearly failed in
both teams' recent games (deep-research verdict ⚠; on 20 Nov 3 of 4 ⚠ legs lost). There is no league / kick-off
limit (user decision, 20 Nov).

Rejected builds are deleted; the final coupon is kept with its research next to it (<coupon>_derin.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import derin_arastirma as dr  # noqa: E402

AREA = dr.AREA
TSI = dr.TSI


def run_builder(target: float, extra: list[str], haric: list[str]) -> Path | None:
    before = set((AREA).glob("*/kupon_*x_*.json"))
    cmd = [sys.executable, str(ROOT / "scripts" / "nesine_kupon.py"), "--hedef", f"{target:g}", "--adet", "1", "--kupasiz",
           "--no-pull", *extra] + (["--haric", *haric] if haric else [])
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    if r.returncode:
        print(r.stderr[-1500:])
        return None
    new = sorted(set(AREA.glob("*/kupon_*x_*.json")) - before, key=lambda f: f.stat().st_mtime)
    return new[-1] if new else None


def check(legs: list[dict], analysis: dict[str, dict]) -> tuple[list[tuple[dict, str]], list[dict]]:
    """(rejected legs with the reason, research rows)."""
    bad, rows = [], []
    for leg in legs:
        m = analysis.get(str(leg["code"]))
        if not m:
            continue
        row = dr.research_match(m, [{"name": leg.get("name"), "label": f"{leg['market']}: {leg['selection']}",
                                     "p": leg["p"], "odds": leg["odds"], "coupons": []}])
        rows.append(row)
        v = row["legs"][0]["verdict"] if row["legs"] else ""
        if v.startswith("⚠"):
            bad.append((leg, f"derin araştırma: {v} (geçmiş %{100 * (row['legs'][0]['mean'] or 0):.0f}, model %{100 * leg['p']:.0f})"))
    return bad, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hedef", type=float, required=True)
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--tur", type=int, default=4, help="En çok yeniden kurma turu")
    ap.add_argument("ekstra", nargs="*", help="nesine_kupon.py'ye aynen geçen seçenekler ('--' sonrası)")
    args = ap.parse_args()
    analysis_path = AREA / args.tarih / "nesine_global.json"
    analysis = {str(m["code"]): m for m in json.loads(analysis_path.read_text(encoding="utf-8"))["matches"]} \
        if analysis_path.exists() else {}
    haric: list[str] = []
    log = []
    for rnd in range(1, args.tur + 1):
        f = run_builder(args.hedef, args.ekstra, haric)
        data = json.loads(f.read_text(encoding="utf-8")) if f else {}
        if not data.get("coupons"):
            print(f"Tur {rnd}: kurallara uyan kupon kurulamadı.")
            if f:
                f.unlink(); f.with_suffix(".md").unlink(missing_ok=True)
            return
        legs = data["coupons"][0]["legs"]
        bad, rows = check(legs, analysis)
        if not bad:
            (f.parent / f"{f.stem}_derin.md").write_text(dr.to_markdown(args.tarih, rows), encoding="utf-8")
            print(f"Tur {rnd}: kupon temiz -> {f.with_suffix('.md').relative_to(ROOT)} (+ {f.stem}_derin.md)")
            for line in log:
                print("  çıkarılan:", line)
            return
        for leg, why in bad:
            haric.append(f"{leg['code']}|{leg.get('key')}")
            log.append(f"{leg['match']} — {leg['market']}: {leg['selection']} ({why})")
        f.unlink(); f.with_suffix(".md").unlink(missing_ok=True)
        print(f"Tur {rnd}: {len(bad)} bacak çıkarıldı, yeniden kuruluyor")
    print("Tur sınırına ulaşıldı; temiz kupon kurulamadı. Çıkarılanlar:")
    for line in log:
        print("  ", line)


if __name__ == "__main__":
    main()
