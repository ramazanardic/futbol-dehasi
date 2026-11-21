"""Build a coupon the safe way (user rules, 20 Nov): direct-price legs only and deep research on every leg before the
coupon is given.

    python scripts/kupon_kur.py --hedef 5
    python scripts/kupon_kur.py --hedef 10 -- --min-mac 4 --hic-kullanilmamis --mac-limit 2

Each round runs scripts/nesine_kupon.py (direct-price legs by default), then scripts/derin_arastirma.py's checks on
every leg. Team history comes from ESPN, else API-Football (scripts/api_gecmis.py), else the Wikipedia season table
(scripts/wiki_gecmis.py). A leg is ruled out and the coupon rebuilt (up to --tur rounds) when

* the leg's own bet clearly failed in both teams' games (verdict ⚠; on 20 Nov 3 of 4 ⚠ legs lost), or
* no source has enough history to test it ("geçmiş yetersiz"; 20 Nov: the worst losses came from such legs) —
  only ✓ / ~ legs stay; --kanitsiz lets untested legs in again.

There is no league / kick-off limit (user decision, 20 Nov).

Only a coupon that passes research is saved, together with its research (<coupon>_derin.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

from quantfoot.paths import ai_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import api_gecmis as af  # noqa: E402
import derin_arastirma as dr  # noqa: E402
import nesine_kupon  # noqa: E402
import openfootball_gecmis as of  # noqa: E402
import footballcharts_gecmis as fc  # noqa: E402
import openligadb_gecmis as ol  # noqa: E402
import openmatchday_gecmis as om  # noqa: E402
import wiki_gecmis as wg  # noqa: E402

AREA = dr.AREA
TSI = dr.TSI
VERDICT_STATS = ROOT / "data" / "calibration" / "verdict_stats.json"  # written by gun_degerlendirme.py
WEAK_MIN_N = 30          # settled "~" legs needed before their record may tighten the rule
WEAK_MAX_SHORTFALL = 0.05


def weak_legs_allowed(ai: str | None = None, path: Path | None = None) -> bool:
    """"~" (weakly supported) legs stay allowed unless enough of them settled and they hit clearly below the price."""
    if ai is None:
        ai = ai_name()
    if path is None:
        path = VERDICT_STATS
    try:
        g = json.loads(path.read_text(encoding="utf-8")).get(ai, {}).get("~") or {}
    except (OSError, ValueError):
        return True
    if g.get("n", 0) < WEAK_MIN_N or not g.get("p_n"):
        return True
    return g["won"] / g["n"] >= g["p_sum"] / g["p_n"] - WEAK_MAX_SHORTFALL


def research_leg(m: dict, leg: dict, fixtures: list[dict] | None) -> dict:
    """Research row of one leg: ESPN, API-Football, openfootball, OpenLigaDB, Football Charts, Open Matchday, then the Wikipedia season table."""
    row = dr.research_match(m, [{"name": leg.get("name"), "label": f"{leg['market']}: {leg['selection']}",
                                 "p": leg["p"], "odds": leg["odds"], "coupons": []}])
    if row["legs"] and row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
        if fixtures:
            try:
                af.research(row, m, fixtures)
            except af.ApiError:
                pass
        if row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
            of.research(row, m)  # openfootball: top divisions with half scores
        if row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
            ol.research(row, m)  # OpenLigaDB: German leagues incl. Regionalliga Nordost, women's Bundesliga
        if row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
            fc.research(row, m)  # Football Charts: 98 leagues, every result with the half score
        if row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
            om.research(row, m)  # Open Matchday: 2026/27 results of 75 competitions (lower leagues, U21)
        if row["legs"][0]["verdict"].startswith("geçmiş yetersiz"):
            wg.research(row, m)
    return row


def simulation_verdicts(date: str) -> dict[tuple[str, str], str]:
    """(match code, bet label) -> simulation verdict of the day (scripts/simulasyon.py), empty when not run."""
    path = AREA / date / "simulasyon.json"
    if not path.exists():
        return {}
    return {(str(r["code"]), b["label"]): b["verdict"] for r in json.loads(path.read_text(encoding="utf-8")) for b in r["bets"]}


def check(legs: list[dict], analysis: dict[str, dict], evidence: bool = True,
          fixtures: list[dict] | None = None, allow_weak: bool = True,
          sim: dict[tuple[str, str], str] | None = None) -> tuple[list[tuple[dict, str]], list[dict]]:
    """(rejected legs with the reason, research rows)."""
    bad, rows = [], []
    sim = sim or {}
    ok_marks = ("✓", "~") if allow_weak else ("✓",)
    for leg in legs:
        m = analysis.get(str(leg["code"]))
        if not m:
            if evidence:
                bad.append((leg, "araştırma için maç verisi bulunamadı"))
            continue
        if sim.get((str(leg["code"]), f"{leg['market']}: {leg['selection']}")) == "çelişki":
            bad.append((leg, "simülasyon çelişki: piyasa, simülasyon ve takım geçmişi uyuşmuyor"))
            continue
        row = research_leg(m, leg, fixtures)
        rows.append(row)
        v = row["legs"][0]["verdict"] if row["legs"] else "geçmiş yetersiz"
        if v.startswith("⚠"):
            bad.append((leg, f"derin araştırma: {v} (geçmiş %{100 * (row['legs'][0]['mean'] or 0):.0f}, model %{100 * leg['p']:.0f})"))
        elif evidence and not v.startswith(ok_marks):
            bad.append((leg, "takım geçmişi hiçbir kaynakta yeterli değil (kanıtsız bacak)" if not v.startswith("~")
                        else "~ işaretli bacaklar ölçümde fiyatın altında kaldı (verdict_stats.json)"))
    return bad, rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hedef", type=float, required=True)
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--tur", type=int, default=8, help="En çok yeniden kurma turu")
    ap.add_argument("--mod", choices=("banko", "risk"), default="banko",
                    help="Kupon modu (nesine_kupon.py --mod): banko varsayılan; risk yalnız kullanıcı açıkça isterse")
    ap.add_argument("--kanitsiz", action="store_true", help="Takım geçmişiyle test edilemeyen bacaklara da izin ver")
    ap.add_argument("ekstra", nargs="*", help="nesine_kupon.py'ye aynen geçen seçenekler ('--' sonrası)")
    args = ap.parse_args()
    try:
        fixtures = af.day_fixtures(args.tarih)
    except (af.ApiError, OSError, ValueError) as e:
        fixtures = None
        print(f"API-Football kullanılamıyor ({e}); ESPN + Wikipedia ile devam")
    sims = simulation_verdicts(args.tarih)
    allow_weak = weak_legs_allowed()
    if not allow_weak:
        print("Ölçüm: ~ işaretli bacaklar fiyatın belirgin altında tuttu; yalnız ✓ bacaklar alınıyor")
    haric: list[str] = []
    log = []

    def review(legs, matches):
        nonlocal bad, rows
        bad, rows = check(legs, {str(m["code"]): m for m in matches}, evidence=not args.kanitsiz,
                          fixtures=fixtures, allow_weak=allow_weak, sim=sims)
        return not bad

    for rnd in range(1, args.tur + 1):
        bad, rows = [], []
        options = [*args.ekstra, "--hedef", f"{args.hedef:g}", "--tarih", args.tarih, "--adet", "1", "--kupasiz", "--no-pull", "--mod", args.mod]
        if haric:
            options.extend(["--haric", *haric])
        f = nesine_kupon.main(options, review=review)
        if f:
            (f.parent / f"{f.stem}_derin.md").write_text(dr.to_markdown(args.tarih, rows), encoding="utf-8")
            print(f"Tur {rnd}: kupon temiz -> {f.with_suffix('.md').relative_to(ROOT)} (+ {f.stem}_derin.md)")
            for line in log:
                print("  çıkarılan:", line)
            return
        if not bad:
            print(f"Tur {rnd}: kurallara uyan kupon kurulamadı.")
            return
        for leg, why in bad:
            haric.append(f"{leg['code']}|{leg.get('key')}")
            log.append(f"{leg['match']} — {leg['market']}: {leg['selection']} ({why})")
        print(f"Tur {rnd}: {len(bad)} bacak çıkarıldı, yeniden kuruluyor")
    print("Tur sınırına ulaşıldı; temiz kupon kurulamadı. Çıkarılanlar:")
    for line in log:
        print("  ", line)


if __name__ == "__main__":
    main()
