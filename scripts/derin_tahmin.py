"""Deep-researched main pick for every not-started match of a day (user request, 20 Nov: "sıfırdan baştan araştır").

    python scripts/derin_tahmin.py --tarih 2026-11-20

Run after scripts/nesine_global.py (and scripts/ai_tahmin.py) for the same day, in the AI's own folder. Per match:

1. candidates: the most probable DIRECT-price selections (Nesine odds >= 1.20, global probability >= 55 %, at most
   --aday of them) — model-derived selections are not used (20 Nov: 51 % realised for 62 % predicted);
2. each candidate is settled on both teams' recent games with scripts/derin_arastirma.py (team half profiles, H2H,
   European fixture, absences, weather);
3. candidates the teams' history contradicts (verdict ⚠) are dropped; the main pick is the most probable survivor.

Output in tahminler/<ai>/<date>/: derin_tahminler.md / .json, and mac_tahminleri.csv's main-pick columns are
replaced by the researched pick (note column: verdict and team-history rate), so the next-day evaluation scores it.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

AREA = dr.AREA
TSI = dr.TSI
MIN_ODDS, MIN_PROB = 1.20, 0.55


def candidates(m: dict, n: int) -> list[dict]:
    sels = [s for s in m.get("selections") or [] if s.get("direct") and s["odds"] >= MIN_ODDS and s["fair_prob"] >= MIN_PROB]
    sels.sort(key=lambda s: -s["fair_prob"])
    return [{"name": s["name"], "label": f"{s['market']}: {s['selection']}", "market": s["market"], "selection": s["selection"],
             "p": s["fair_prob"], "odds": s["odds"], "coupons": []} for s in sels[:n]]


def choose(legs: list[dict]) -> dict | None:
    """The best-evidenced candidate the teams' history does not contradict: ✓ before ~ before untested, then the most
    probable (21 Nov: same evidence order as the coupon rule; untested picks lost most often)."""
    ok = [x for x in legs if not x["verdict"].startswith("⚠")]
    rank = lambda x: 0 if x["verdict"].startswith("✓") else 1 if x["verdict"].startswith("~") else 2  # noqa: E731
    return min(ok, key=lambda x: (rank(x), -x["p"])) if ok else None


def research_day(date: str, n_cand: int, workers: int = 2) -> list[dict]:
    data = json.loads((AREA / date / "nesine_global.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(TSI)
    todo = [m for m in data["matches"] if m.get("status") == "fiyatlandı"
            and dt.datetime.fromisoformat(m["kickoff_iso"]) > now + dt.timedelta(minutes=5)]

    def one(m):
        legs = candidates(m, n_cand)
        row = dr.research_match(m, legs) if legs else {"code": m["code"], "match": f"{m['home']} - {m['away']}",
                                                         "kickoff": m["kickoff"], "league": m["league"], "legs": [], "espn": False}
        cand = {x["name"]: x for x in legs}
        for x in row["legs"]:
            c = cand[x["name"]]
            x.update({"label": c["label"], "market": c["market"], "sel": c["selection"]})
        row["pick"] = choose(row["legs"])
        row["dropped"] = [x for x in row["legs"] if x["verdict"].startswith("⚠")]
        return row

    rows = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, row in enumerate(ex.map(one, todo), 1):
            rows.append(row)
            if i % 10 == 0:
                print(f"{i}/{len(todo)} maç araştırıldı", flush=True)
    return sorted(rows, key=lambda r: r["kickoff"])


def update_table(date: str, rows: list[dict]) -> int:
    """Replace the main pick of mac_tahminleri.csv with the researched pick (not-started matches only)."""
    path = AREA / date / "mac_tahminleri.csv"
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as fh:
        table = list(csv.DictReader(fh))
    by = {str(r["code"]): r for r in rows}
    n = 0
    for t in table:
        r = by.get(str(t.get("nesine_kodu")))
        if not r:
            continue
        pk = r["pick"]
        if pk:
            hist = "-" if pk.get("mean") is None else f"%{100 * pk['mean']:.0f}"
            t.update({"ana_secim_pazar": pk["market"], "ana_secim": pk["sel"], "nesine_oran": pk["odds"], "secim_adi": pk["name"],
                      "olasilik": f"{pk['p']:.4f}", "not": f"derin araştırma: {pk['verdict']} (takım geçmişi {hist})"})
        else:
            t.update({"ana_secim_pazar": "", "ana_secim": "", "nesine_oran": "", "olasilik": "", "secim_adi": "",
                      "not": "derin araştırma: uygun borsa fiyatlı tercih yok ya da geçmiş çürüttü"})
        n += 1
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        cols = list(table[0]) + ([] if "secim_adi" in table[0] else ["secim_adi"])
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(table)
    return n


def to_markdown(date: str, rows: list[dict]) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    with_pick = [r for r in rows if r["pick"]]
    md = [f"# {date} — sıfırdan derin araştırma ({dt.datetime.now(TSI):%H:%M} TSİ)", "",
          f"{len(rows)} başlamamış global fiyatlı maç · {len(with_pick)} maçta ana tercih · "
          f"{sum(1 for r in rows if r.get('espn'))} maçta ESPN takım geçmişi · {sum(len(r['dropped']) for r in rows)} aday "
          "takım geçmişi çürüttüğü için elendi.", "",
          "Kurallar: yalnız borsa fiyatlı seçimler (oran ≥ 1,20, olasılık ≥ %55); her aday iki takımın son ~15 maçında "
          "test edildi; ⚠ alan aday elendi, kalanların en olasısı ana tercih.", "",
          "| Saat | Lig | Maç | Ana tercih | Oran | Olasılık | Takım geçmişi | İşaret | Elenen |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        pk = r["pick"]
        dropped = "; ".join(f"{x['label']} ({pct(x['mean'])})" for x in r["dropped"]) or "-"
        if pk:
            md.append(f"| {r['kickoff'][11:16]} | {r['league']} | {r['match']} | {pk['label']} | {pk['odds']:.2f} | {pct(pk['p'])} | "
                      f"{pct(pk.get('mean'))} | {pk['verdict']} | {dropped} |")
        else:
            md.append(f"| {r['kickoff'][11:16]} | {r['league']} | {r['match']} | — | | | | | {dropped} |")
    md += ["", "Ayrıntı (takım profilleri, aralarındaki maçlar, eksikler, hava): derin_tahminler_ayrinti.md", ""]
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--aday", type=int, default=5, help="Maç başına test edilecek en çok aday")
    args = ap.parse_args()
    rows = research_day(args.tarih, args.aday)
    out = AREA / args.tarih
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(to_markdown(args.tarih, rows), encoding="utf-8")
    (out / "derin_tahminler_ayrinti.md").write_text(dr.to_markdown(args.tarih, [r for r in rows if r["legs"]]), encoding="utf-8")
    n = update_table(args.tarih, rows)
    import bahis_aileleri
    bahis_aileleri.build_day(args.tarih)  # every bet family of every match, with probabilities -> bahis_aileleri.md
    print(f"{len(rows)} maç araştırıldı, {sum(1 for r in rows if r['pick'])} ana tercih; mac_tahminleri.csv'de {n} satır "
          f"güncellendi -> {out / 'derin_tahminler.md'}")


if __name__ == "__main__":
    main()
