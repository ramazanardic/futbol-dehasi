"""Sharp-vs-soft price scan: compare bookmaker odds with Pinnacle's margin-free price.

The strongest evidence in this repository (reports/research/sharp_soft.md) is not a model
but a price gap: betting soft-book prices that exceed Pinnacle's devigged probability earned
positive closing-line value and ROI on 7,348 matches (cf. Kaunitz et al. 2017,
arXiv:1710.02824). This script applies that rule live.

    # Live scan with The Odds API (needs a key: env ODDS_API_KEY or --api-key)
    python scripts/sharp_scan.py scan --date 2026-11-21
    # Re-run close to kick-off to record Pinnacle closing prices, then measure CLV of the picks
    python scripts/sharp_scan.py scan --date 2026-11-21
    python scripts/sharp_scan.py clv --date 2026-11-21
    # Check your own bookmaker's odds (e.g. Nesine) against the latest Pinnacle scan:
    python scripts/sharp_scan.py check --date 2026-11-21 --my-odds nesine.csv

`--my-odds` CSV columns: home,away,selection,odds   (selection: 1, X, 2, Üst 2.5, Alt 2.5)

Only bet with operators that are legal where you live. Winning accounts at soft bookmakers
are often limited (Kaunitz et al. 2017).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import json
import os
from pathlib import Path

import requests

from quantfoot.markets.devig import devig

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "reports" / "daily"
API = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"
DEFAULT_SPORTS = (
    "soccer_epl", "soccer_efl_champ", "soccer_spain_la_liga", "soccer_germany_bundesliga", "soccer_italy_serie_a",
    "soccer_france_ligue_one", "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    "soccer_turkey_super_league", "soccer_uefa_champs_league", "soccer_uefa_europa_league", "soccer_brazil_campeonato",
)
EXCHANGES = {"betfair_ex_eu", "betfair_ex_uk", "matchbook", "smarkets", "betdaq"}


def _sel_names(market: str, outcome: dict, home: str, away: str) -> str | None:
    name = outcome.get("name")
    if market == "h2h":
        return {home: "1", away: "2", "Draw": "X"}.get(name)
    if market == "totals" and outcome.get("point") is not None:
        return f"{'Üst' if name == 'Over' else 'Alt'} {float(outcome['point']):g}"
    return None


def parse_events(payload: list[dict]) -> list[dict]:
    """Normalise The Odds API events into {id, kickoff, home, away, books: {book: {selection: odds}}}."""
    events = []
    for ev in payload:
        home, away = ev["home_team"], ev["away_team"]
        books: dict[str, dict[str, float]] = {}
        for bm in ev.get("bookmakers", []):
            prices: dict[str, float] = {}
            for mk in bm.get("markets", []):
                for oc in mk.get("outcomes", []):
                    sel = _sel_names(mk["key"], oc, home, away)
                    if sel and oc.get("price", 0) > 1.0:
                        prices[sel] = float(oc["price"])
            if prices:
                books[bm["key"]] = prices
        events.append({"id": ev["id"], "kickoff": ev["commence_time"], "home": home, "away": away, "books": books})
    return events


def pinnacle_fair(prices: dict[str, float]) -> dict[str, float]:
    """Devig Pinnacle's 1X2 and each totals line separately (power method)."""
    fair: dict[str, float] = {}
    if all(k in prices for k in ("1", "X", "2")):
        p = devig([prices["1"], prices["X"], prices["2"]], method="power").probabilities
        fair.update({"1": float(p[0]), "X": float(p[1]), "2": float(p[2])})
    for sel in prices:
        if sel.startswith("Üst "):
            under = "Alt " + sel[4:]
            if under in prices:
                p = devig([prices[sel], prices[under]], method="power").probabilities
                fair[sel], fair[under] = float(p[0]), float(p[1])
    return fair


def find_value(events: list[dict], min_ev: float, max_odds: float, commission: float) -> list[dict]:
    picks = []
    for ev in events:
        pin = ev["books"].get("pinnacle")
        if not pin:
            continue
        fair = pinnacle_fair(pin)
        for book, prices in ev["books"].items():
            if book == "pinnacle":
                continue
            c = commission if book in EXCHANGES else 0.0
            for sel, odds in prices.items():
                if sel not in fair or odds > max_odds:
                    continue
                ev_val = fair[sel] * (1.0 + (odds - 1.0) * (1.0 - c)) - 1.0
                if ev_val >= min_ev:
                    picks.append({"event_id": ev["id"], "kickoff": ev["kickoff"], "match": f"{ev['home']} - {ev['away']}",
                                  "book": book, "selection": sel, "odds": odds, "pinnacle_odds": pin.get(sel),
                                  "fair_prob": round(fair[sel], 5), "ev": round(ev_val, 4)})
    picks.sort(key=lambda p: p["ev"], reverse=True)
    best: dict[tuple, dict] = {}
    for p in picks:  # keep the best price per (match, selection)
        best.setdefault((p["event_id"], p["selection"]), p)
    return list(best.values())


def _day(date: str) -> Path:
    d = DAILY / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def cmd_scan(args: argparse.Namespace) -> None:
    key = args.api_key or os.environ.get("ODDS_API_KEY")
    if not key:
        raise SystemExit("The Odds API anahtarı gerekli: --api-key veya ODDS_API_KEY ortam değişkeni.")
    events: list[dict] = []
    for sport in args.sports:
        r = requests.get(API.format(sport=sport), timeout=20, params={
            "apiKey": key, "regions": "eu,uk", "markets": "h2h,totals", "oddsFormat": "decimal"})
        if r.status_code != 200:
            print(f"{sport}: HTTP {r.status_code}")
            continue
        print(f"{sport}: {len(r.json())} maç, kalan istek {r.headers.get('x-requests-remaining')}")
        events += parse_events(r.json())
    day = args.date
    events = [e for e in events if e["kickoff"][:10] in (day, (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat())]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    d = _day(day)
    snaps = json.loads((d / "pinnacle_snapshots.json").read_text(encoding="utf-8")) if (d / "pinnacle_snapshots.json").exists() else {}
    for ev in events:
        if "pinnacle" in ev["books"] and ev["kickoff"] > now:  # pre-kickoff only: the last one is the close
            snaps[ev["id"]] = {"captured_at": now, "kickoff": ev["kickoff"], "match": f"{ev['home']} - {ev['away']}",
                               "home": ev["home"], "away": ev["away"], "pinnacle": ev["books"]["pinnacle"]}
    (d / "pinnacle_snapshots.json").write_text(json.dumps(snaps, ensure_ascii=False, indent=2), encoding="utf-8")
    picks = find_value([e for e in events if e["kickoff"] > now], args.min_ev, args.max_odds, args.commission)
    prev = json.loads((d / "sharp_picks.json").read_text(encoding="utf-8")) if (d / "sharp_picks.json").exists() else []
    seen = {(p["event_id"], p["selection"], p["book"]) for p in prev}
    for p in picks:
        if (p["event_id"], p["selection"], p["book"]) not in seen:
            prev.append({**p, "found_at": now})
    (d / "sharp_picks.json").write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(events)} maç tarandı, {len(picks)} değer bulundu (toplam kayıt {len(prev)}).")
    for p in picks[:20]:
        print(f"  {p['match']}: {p['selection']} @ {p['odds']:.2f} ({p['book']}) | Pinnacle {p['pinnacle_odds']} | EV {p['ev']:+.1%}")


def cmd_clv(args: argparse.Namespace) -> None:
    d = _day(args.date)
    picks = json.loads((d / "sharp_picks.json").read_text(encoding="utf-8"))
    snaps = json.loads((d / "pinnacle_snapshots.json").read_text(encoding="utf-8"))
    vals = []
    for p in picks:
        snap = snaps.get(p["event_id"])
        if not snap or snap["captured_at"] <= p["found_at"]:
            continue  # no later Pinnacle price yet
        fair = pinnacle_fair(snap["pinnacle"])
        if p["selection"] in fair:
            vals.append(fair[p["selection"]] * p["odds"] - 1.0)
    if not vals:
        print("CLV için bahisten sonra alınmış bir Pinnacle kaydı yok (maçlardan önce tekrar `scan` çalıştırın).")
        return
    print(f"{len(vals)} bahis: ortalama adil CLV {sum(vals) / len(vals):+.2%}")


def cmd_check(args: argparse.Namespace) -> None:
    snaps = json.loads((_day(args.date) / "pinnacle_snapshots.json").read_text(encoding="utf-8"))
    names = {f"{s['home']} - {s['away']}": s for s in snaps.values()}
    with open(args.my_odds, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"{'Maç':<40} {'Seçim':<8} {'Oran':>6} {'Pinnacle adil':>14} {'EV':>8}")
    for r in rows:
        key = f"{r['home']} - {r['away']}"
        match = difflib.get_close_matches(key, names, n=1, cutoff=0.6)
        if not match:
            print(f"{key:<40} Pinnacle kaydı bulunamadı")
            continue
        fair = pinnacle_fair(names[match[0]]["pinnacle"])
        sel = r["selection"].replace(",", ".")
        if sel not in fair:
            print(f"{key:<40} {sel:<8} Pinnacle'da bu seçim yok")
            continue
        odds = float(r["odds"].replace(",", "."))
        ev = fair[sel] * odds - 1.0
        print(f"{match[0]:<40} {sel:<8} {odds:6.2f} {1 / fair[sel]:14.2f} {ev:+8.1%}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    today = dt.date.today().isoformat()
    s = sub.add_parser("scan")
    s.add_argument("--date", default=today)
    s.add_argument("--api-key", default=None)
    s.add_argument("--sports", nargs="+", default=list(DEFAULT_SPORTS))
    s.add_argument("--min-ev", type=float, default=0.025, help="Backtest'te ROI ve CLV'nin belirginleştiği eşik")
    s.add_argument("--max-odds", type=float, default=3.5)
    s.add_argument("--commission", type=float, default=0.02, help="Borsa (exchange) kazanç komisyonu")
    s.set_defaults(func=cmd_scan)
    c = sub.add_parser("clv")
    c.add_argument("--date", default=today)
    c.set_defaults(func=cmd_clv)
    k = sub.add_parser("check")
    k.add_argument("--date", default=today)
    k.add_argument("--my-odds", required=True)
    k.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
