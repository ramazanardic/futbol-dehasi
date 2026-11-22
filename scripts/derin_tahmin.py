"""Deep-researched main pick for every not-started match of a day (user request, 20 Nov: "sıfırdan baştan araştır").

    python scripts/derin_tahmin.py --tarih 2026-11-20

Run after scripts/nesine_global.py (and scripts/ai_tahmin.py) for the same day, in the AI's own folder. Per match:

1. candidates: DIRECT-price selections at the leg floor (Nesine odds >= 1.20, calibrated global probability >= 55 %),
   ranked by calibrated EV = p × Nesine odds − 1, at most --aday of them — model-derived selections are not used
   (20 Nov: 51 % realised for 62 % predicted);
2. each candidate is settled on both teams' recent games with scripts/derin_arastirma.py (team half profiles, H2H,
   European fixture, absences, weather);
3. evidence is a FILTER: candidates the teams' history contradicts (verdict ⚠) are dropped; the main pick is the
   survivor with the highest calibrated EV, and only if EV >= settings.PICK_MIN_EV (22 Nov audit: picking the most
   probable selection ignores the price — Nesine's margin makes most of them negative-value). No value = no pick.

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
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))

AREA = dr.AREA
TSI = dr.TSI
MIN_ODDS = 1.20
_WINDOW = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")


def candidates(m: dict, n: int, calibration: dict | None = None) -> list[dict]:
    """Direct-price selections at the leg floor; probability = the global one corrected by the settled-history
    calibration, the same number the coupon builder and the family table use (21 Nov)."""
    from quantfoot.evaluation.auto_learn import calibrated_probability
    from gunluk_analiz import main_pick_floor
    min_p, _ = main_pick_floor(m)
    if min_p is None:
        return []
    cal = calibration if calibration is not None else _calibration()
    sels = [(s, calibrated_probability(s["fair_prob"], True, cal)) for s in m.get("selections") or [] if s.get("direct")]
    sels = sorted([x for x in sels if x[0]["odds"] >= MIN_ODDS and x[1] >= min_p], key=lambda x: -(x[1] * x[0]["odds"]))
    return [{"name": s["name"], "label": f"{s['market']}: {s['selection']}", "market": s["market"], "selection": s["selection"],
             "p": p, "odds": s["odds"], "ev": round(p * s["odds"] - 1.0, 4), "coupons": []} for s, p in sels[:n]]


def _calibration() -> dict:
    from quantfoot.evaluation.auto_learn import load_live_calibration
    return load_live_calibration() or {}


def leg_ev(x: dict) -> float:
    """Calibrated EV of a leg (p already carries the settled-history correction)."""
    return float(x["p"]) * float(x["odds"]) - 1.0


def choose(legs: list[dict], min_ev: float | None = None) -> dict | None:
    """Main pick = highest calibrated EV among candidates the teams' history does not contradict, EV >= min_ev.

    Evidence only filters (⚠ out); among equal EV the better-evidenced one wins (✓ before ~ before untested).
    Picking by probability alone ignored the odds (audit 21 Nov), so a match without value gets no pick."""
    from quantfoot.markets.families import leg_min_ev
    from quantfoot.settings import PICK_MIN_EV

    def floor(x: dict) -> float:  # default: the stricter of the pick floor and the leg's bet-family floor
        return max(PICK_MIN_EV, leg_min_ev(x.get("name", ""))) if min_ev is None else min_ev

    ok = [x for x in legs if not x["verdict"].startswith("⚠") and x.get("odds") and leg_ev(x) >= floor(x)]
    rank = lambda x: 0 if x["verdict"].startswith("✓") else 1 if x["verdict"].startswith("~") else 2  # noqa: E731
    return max(ok, key=lambda x: (round(leg_ev(x), 6), -rank(x))) if ok else None


def parse_window(window: str | None) -> str | None:
    """Validate '--saat HH:MM-HH:MM' (argparse type). Crossing midnight ('22:00-02:00') is allowed."""
    if window is None:
        return None
    w = window.strip()
    if not _WINDOW.match(w):
        raise argparse.ArgumentTypeError(f"--saat biçimi SS:DD-SS:DD olmalı (ör. 06:00-10:00 ya da 22:00-02:00): {window!r}")
    return w


def in_window(kickoff: str, window: str | None) -> bool:
    """Kick-off 'YYYY-MM-DD HH:MM' inside 'HH:MM-HH:MM' (both ends included); no window = every match.
    A window whose start is after its end crosses midnight: '22:00-02:00' = 22:00–23:59 or 00:00–02:00."""
    if not window:
        return True
    lo, hi = parse_window(window).split("-")
    t = kickoff[11:16]
    return lo <= t <= hi if lo <= hi else (t >= lo or t <= hi)


def research_day(date: str, n_cand: int, workers: int = 2, window: str | None = None) -> list[dict]:
    data = json.loads((AREA / date / "nesine_global.json").read_text(encoding="utf-8"))
    now = dt.datetime.now(TSI)
    todo = [m for m in data["matches"] if m.get("status") == "fiyatlandı" and in_window(m["kickoff"], window)
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


def keep_notes(old_rows: list[dict], rows: list[dict]) -> int:
    """Carry the hand-made research (web / preview notes) into a fresh run, so a rerun never erases it (21 Nov).

    The notes are free text: they are shown, but they never set or override a verdict or a history rate (22 Nov
    audit) — a verdict comes only from the measured team history of this run."""
    old = {(str(r["code"]), x["label"]): (r, x) for r in old_rows for x in r.get("legs") or [] if x.get("web")}
    n = 0
    for r in rows:
        for x in r.get("legs") or []:
            hit = old.get((str(r["code"]), x["label"]))
            if not hit:
                continue
            orow, ox = hit
            x["web"] = ox["web"]
            r["web"] = True
            if orow.get("onizleme"):
                r["onizleme"] = orow["onizleme"]
            n += 1
        r["pick"], r["dropped"] = choose(r.get("legs") or []), [x for x in r.get("legs") or [] if x["verdict"].startswith("⚠")]
    return n


NO_VALUE_NOTE = "derin araştırma: değerli tercih yok (EV < taban) — en olası tercih korundu, değer bahsi değil"


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
        elif (t.get("secim_adi") or "").strip() and t["secim_adi"].strip() not in {
                (x.get("name") or "").strip() for x in r.get("dropped") or []}:
            # No value pick (EV floor): keep the most probable selection ai_tahmin wrote (apply_research_picks'
            # documented fallback), flagged, so every match still has a graded prediction (22 Nov live test: the EV
            # floor blanked all 431 main picks and the next-day evaluation had nothing to score).
            t["not"] = NO_VALUE_NOTE
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
          "Kurallar: yalnız borsa fiyatlı seçimler (oran ≥ 1,20, kalibre olasılık ≥ %55); her aday iki takımın son ~15 maçında "
          "test edildi; ⚠ alan aday elendi; kalanlardan kalibre beklenen değeri (olasılık × oran − 1) en yüksek olan, "
          "en az +%2 ise ana tercih. Değer yoksa ana tercih yok.", "",
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
    ap.add_argument("--saat", type=parse_window,
                    help="Yalnız bu başlama saatleri, ör. 06:00-10:00; gece yarısını geçebilir: 22:00-02:00")
    args = ap.parse_args()
    rows = research_day(args.tarih, args.aday, window=args.saat)
    import footballcharts_gecmis as fc
    import openligadb_gecmis as ol
    import openmatchday_gecmis as om
    import wiki_gecmis as wg
    ms = {str(m["code"]): m for m in json.loads((AREA / args.tarih / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    for r in rows:  # leagues ESPN lacks: Football Charts (half scores), Open Matchday, else the Wikipedia table
        if not r.get("espn") and r.get("legs") and str(r["code"]) in ms:
            r.setdefault("teams", {})
            m = ms[str(r["code"])]
            if ol.research(r, m) or fc.research(r, m) or om.research(r, m) or wg.research(r, m):
                r["pick"], r["dropped"] = choose(r["legs"]), [x for x in r["legs"] if x["verdict"].startswith("⚠")]
    out = AREA / args.tarih
    if (out / "derin_tahminler.json").exists():  # hand-made research of an earlier run survives the rerun
        keep_notes(json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8")), rows)
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(to_markdown(args.tarih, rows), encoding="utf-8")
    (out / "derin_tahminler_ayrinti.md").write_text(dr.to_markdown(args.tarih, [r for r in rows if r["legs"]]), encoding="utf-8")
    n = update_table(args.tarih, rows)
    import bahis_aileleri
    bahis_aileleri.build_day(args.tarih)  # every bet family of every match, with probabilities -> bahis_aileleri.md
    import simulasyon
    simulasyon.write_day(args.tarih, 20000)  # market / simulation / history side by side -> simulasyon.md
    print(f"{len(rows)} maç araştırıldı, {sum(1 for r in rows if r['pick'])} ana tercih; mac_tahminleri.csv'de {n} satır "
          f"güncellendi -> {out / 'derin_tahminler.md'}")


if __name__ == "__main__":
    main()
