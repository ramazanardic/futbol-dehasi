"""Deep research for coupon legs / candidate matches — the standard for every analysis (user rule, 20 Nov).

    python scripts/derin_arastirma.py --tarih 2026-11-20 --kuponlar          # every leg of the latest coupons
    python scripts/derin_arastirma.py --tarih 2026-11-20 --kod 3309603 3310218 --sec "İY KG Var & 2Y KG Var"

Per match (Nesine code, from the AI's own analysis file tahminler/<ai>/<date>/nesine_global.json):

* **team profiles** from ESPN (also for matches the analysis could not link: league slug + kick-off + home name) — the last ~15 completed matches of each team with HALF scores (match summaries):
  form, goals for/against, scoring / conceding in the 1st and 2nd half, BTTS, 2,5 Üst, both-halves BTTS;
* **leg test** — the leg's own bet settled on each team's past matches (oriented so the team keeps its side), i.e.
  how often this exact bet would have won in these teams' recent games, next to the model probability;
* **context** — head-to-head among the fetched games, a European fixture within 6 days (rotation risk), and the
  analysis' own research: absences, risk / steam flags, weather, motivation.

Output: tahminler/<ai>/<date>/derin_arastirma.md / .json (private folder). ESPN is queried politely: every response
is cached under data/cache/espn/ (finished matches for good, schedules for 6 h), at most 4 requests in flight, and
a non-JSON answer (rate limit) is retried after a pause.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402

AREA = ROOT / "tahminler" / os.environ.get("QUANTFOOT_AI", "claudetahmin")
CACHE = ROOT / "data" / "cache" / "espn"
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
UEFA = ("uefa.champions", "uefa.europa", "uefa.europa.conf")
TSI = dt.timezone(dt.timedelta(hours=3))
N_RECENT = 15
SCHEDULE_TTL_H = 6.0
_session = requests.Session()
MIN_INTERVAL_S = 0.34  # at most ~3 requests per second (ESPN blocked ~900 fast parallel requests on 20 Nov)
_rate_lock = threading.Lock()
_last_call = [0.0]


def _throttle() -> None:
    with _rate_lock:
        wait = _last_call[0] + MIN_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()


def espn(path: str, ttl_h: float | None = None, **params) -> dict | None:
    """GET an ESPN site-API path with a disk cache (ttl_h None = keep for good) and a rate-limit back-off."""
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists() and (ttl_h is None or time.time() - f.stat().st_mtime < ttl_h * 3600):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    for wait in (0, 20, 60):
        if wait:
            time.sleep(wait)
        _throttle()
        try:
            r = _session.get(f"{BASE}/{path}", params=params, timeout=30)
            data = r.json()
        except (requests.RequestException, ValueError):
            continue  # blocked / non-JSON: back off and retry
        if r.status_code == 200:
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(data), encoding="utf-8")
            return data
        return None
    return None


def half_scores(slug: str, event_id: str) -> dict | None:
    """{team_id: (first-half goals, second-half goals, 'home'|'away')} of a finished match."""
    s = espn(f"{slug}/summary", None, event=event_id)
    try:
        done = s["header"]["competitions"][0]["status"]["type"].get("completed")
    except (KeyError, IndexError, TypeError):
        done = False
    if not done:  # a summary cached before kick-off must not hide the final result
        s = espn(f"{slug}/summary", 0.0, event=event_id)
    try:
        comp = s["header"]["competitions"][0]
        if not comp["status"]["type"].get("completed"):
            return None
        out = {}
        for c in comp["competitors"]:
            ls = c.get("linescores") or []
            out[c["team"]["id"]] = (int(ls[0]["displayValue"]), int(ls[1]["displayValue"]), c["homeAway"], c["team"]["displayName"])
        return out if len(out) == 2 else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def team_games(slug: str, team_id: str, before: dt.datetime, n: int = N_RECENT) -> list[dict]:
    """Last n finished matches of a team before ``before``, with half scores, oriented to the team."""
    sch = espn(f"{slug}/teams/{team_id}/schedule", SCHEDULE_TTL_H) or {}
    evs = [e for e in sch.get("events") or [] if e["competitions"][0]["status"]["type"].get("completed")
           and dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00")) < before][-n:]
    with cf.ThreadPoolExecutor(4) as ex:
        halves = list(ex.map(lambda e: half_scores(slug, e["id"]), evs))
    games = []
    for e, h in zip(evs, halves):
        if not h or team_id not in h:
            continue
        me = h[team_id]
        opp_id, opp = next((k, v) for k, v in h.items() if k != team_id)
        games.append({"event": e["id"], "date": e["date"][:10], "side": me[2], "opp": opp[3], "opp_id": opp_id,
                      "for": (me[0], me[1]), "against": (opp[0], opp[1])})
    return games


def oriented(g: dict, as_side: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """(HT, FT) of a past game with the team placed on ``as_side`` ('home'/'away'), whatever side it really played."""
    f, a = g["for"], g["against"]
    ht_t, ft_t = f[0], f[0] + f[1]
    ht_o, ft_o = a[0], a[0] + a[1]
    return ((ht_t, ht_o), (ft_t, ft_o)) if as_side == "home" else ((ht_o, ht_t), (ft_o, ft_t))


def profile(games: list[dict]) -> dict:
    n = len(games)
    if not n:
        return {"n": 0}
    rate = lambda cond: sum(1 for g in games if cond(g)) / n  # noqa: E731
    pts = sum(3 if sum(g["for"]) > sum(g["against"]) else (1 if sum(g["for"]) == sum(g["against"]) else 0) for g in games)
    return {
        "n": n, "form": "".join("G" if sum(g["for"]) > sum(g["against"]) else ("B" if sum(g["for"]) == sum(g["against"]) else "M")
                                for g in games[-5:]),
        "ppg": pts / n, "gf": sum(sum(g["for"]) for g in games) / n, "ga": sum(sum(g["against"]) for g in games) / n,
        "score1H": rate(lambda g: g["for"][0] > 0), "score2H": rate(lambda g: g["for"][1] > 0),
        "concede1H": rate(lambda g: g["against"][0] > 0), "concede2H": rate(lambda g: g["against"][1] > 0),
        "btts": rate(lambda g: sum(g["for"]) > 0 and sum(g["against"]) > 0),
        "over25": rate(lambda g: sum(g["for"]) + sum(g["against"]) > 2),
        "both_halves_btts": rate(lambda g: min(g["for"][0], g["for"][1], g["against"][0], g["against"][1]) > 0),
    }


def leg_history(name: str, home_games: list[dict], away_games: list[dict]) -> dict:
    """How often bet ``name`` won in each team's past games (home team kept at home, away team kept away)."""
    def rate(games, side):
        res = []
        for g in games:
            ht, ft = oriented(g, side)
            try:
                v = settle_selection(name, ht, ft)
            except (ValueError, KeyError):
                v = None
            if v is not None:
                res.append(v)
        return (sum(res) / len(res), len(res)) if res else (None, 0)
    h, nh = rate(home_games, "home")
    a, na = rate(away_games, "away")
    vals = [x for x in (h, a) if x is not None]
    return {"home_rate": h, "home_n": nh, "away_rate": a, "away_n": na, "mean": sum(vals) / len(vals) if vals else None}


def verdict(p_model: float | None, hist: dict) -> str:
    m, n = hist.get("mean"), min(hist.get("home_n") or 0, hist.get("away_n") or 0)
    if m is None or p_model is None or n < 6:
        return "geçmiş yetersiz"
    if m >= p_model - 0.05:
        return "✓ geçmiş destekliyor"
    if m >= p_model - 0.15:
        return "~ geçmiş zayıf destekliyor"
    return "⚠ geçmiş desteklemiyor"


def european_fixture(team_id: str, kickoff: dt.datetime, days: int = 6) -> str | None:
    for slug in UEFA:
        sch = espn(f"{slug}/teams/{team_id}/schedule", SCHEDULE_TTL_H) or {}
        for e in sch.get("events") or []:
            t = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            if kickoff < t <= kickoff + dt.timedelta(days=days):
                return f"{e['date'][:10]} {e.get('shortName') or e.get('name')} ({slug})"
    return None


# Nesine league name prefix -> ESPN slug, for matches the analysis could not link to ESPN (e.g. renamed clubs:
# Hyderabad FC is "Sporting Club Delhi" on ESPN). Only slugs that ESPN actually serves with fixtures.
LEAGUE_SLUGS = {"Hindistan Süper Ligi": "ind.1", "İngiltere Ulusal Lig": "eng.5", "Hollanda 1. Lig": "ned.2",
                "Norveç Eliteserien": "nor.1", "İsviçre Challenge Ligi": "sui.2", "Romanya 1. Lig": "rou.1",
                "Kuzey İrlanda Premiership": "nir.1", "Türkiye 1. Lig": "tur.2", "Galler Premier Lig": "wal.1"}


def _tokens(name: str) -> set[str]:
    return {t for t in name.lower().replace(".", " ").replace("-", " ").split() if len(t) > 3}


def find_espn_event(m: dict) -> tuple[str, str] | None:
    """(slug, event id) by league slug, kick-off time (±20 min) and a shared word in the home team's name."""
    slug = next((v for k, v in LEAGUE_SLUGS.items() if m["league"].startswith(k)), None)
    if not slug:
        return None
    kick = dt.datetime.fromisoformat(m["kickoff_iso"])
    sb = espn(f"{slug}/scoreboard", 1.0, dates=kick.astimezone(dt.timezone.utc).strftime("%Y%m%d")) or {}
    for e in sb.get("events") or []:
        t = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
        home = next((c["team"]["displayName"] for c in e["competitions"][0]["competitors"] if c["homeAway"] == "home"), "")
        if abs((t - kick).total_seconds()) <= 1200 and _tokens(home) & _tokens(m["home"]):
            return slug, e["id"]
    return None


def research_match(m: dict, legs: list[dict]) -> dict:
    r = m.get("research") or {}
    out = {"code": m["code"], "match": f"{m['home']} - {m['away']}", "kickoff": m["kickoff"], "league": m["league"],
           "reference": m.get("reference"), "mu": [m.get("mu_home"), m.get("mu_away")], "flags": r.get("flags") or [],
           "weather": r.get("weather"), "motivation": r.get("motivation"), "teams": {}, "legs": [], "h2h": [], "europe": {},
           "espn": bool(r.get("espn_event") and r.get("league_slug"))}
    for side in ("home", "away"):
        t = (r.get("teams") or {}).get(side) or {}
        tm = (r.get("tm_absences") or {}).get(side) or {}
        out["teams"][side] = {"name": m["home" if side == "home" else "away"],
                              "absent": [x["name"] for x in t.get("likely_absent") or []][:4],
                              "gk1_out": bool(tm.get("gk1_out")), "top_scorer_out": bool(tm.get("top_scorer_out"))}
    games = {"home": [], "away": []}
    link = (r["league_slug"], r["espn_event"]) if out["espn"] else find_espn_event(m)
    out["espn"] = bool(link)
    if link:
        slug, ev = link
        s = espn(f"{slug}/summary", SCHEDULE_TTL_H, event=ev) or {}
        comps = ((s.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
        ids = {c["homeAway"]: c["team"]["id"] for c in comps}
        kickoff = dt.datetime.fromisoformat(m["kickoff_iso"])
        for side in ("home", "away"):
            if side in ids:
                games[side] = team_games(slug, ids[side], kickoff)
                out["teams"][side].update(profile(games[side]))
                eu = european_fixture(ids[side], kickoff) if slug.endswith(".1") else None  # top divisions only
                if eu:
                    out["europe"][side] = eu
        if "home" in ids and "away" in ids:
            seen = {g["event"]: g for g in games["home"] if g["opp_id"] == ids["away"]}
            out["h2h"] = [f"{g['date']}: {out['teams']['home']['name']} {sum(g['for'])}-{sum(g['against'])} "
                          f"(İY {g['for'][0]}-{g['against'][0]})" for g in seen.values()]
    for leg in legs:
        hist = leg_history(leg["name"], games["home"], games["away"])
        out["legs"].append({"selection": leg.get("label") or leg["name"], "name": leg["name"], "p": leg.get("p"),
                            "odds": leg.get("odds"), "coupons": leg.get("coupons", []), **hist,
                            "verdict": verdict(leg.get("p"), hist)})
    return out


def coupon_legs(date: str) -> dict[str, list[dict]]:
    """Legs of the latest coupon file of every (target, family) group, keyed by match code."""
    latest: dict[tuple[str, str], Path] = {}
    for f in sorted((AREA / date).glob("kupon_*x_*.json")):
        parts = f.stem.split("_")
        latest[(parts[1], parts[2] if len(parts) >= 4 else "karma")] = f
    by_code: dict[str, list[dict]] = {}
    for f in latest.values():
        for i, c in enumerate(json.loads(f.read_text(encoding="utf-8")).get("coupons", []), 1):
            for leg in c["legs"]:
                rec = next((x for x in by_code.setdefault(str(leg["code"]), []) if x["name"] == leg.get("name")), None)
                if rec is None:
                    rec = {"name": leg.get("name"), "label": f"{leg['market']}: {leg['selection']}", "p": leg["p"],
                           "odds": leg["odds"], "coupons": []}
                    by_code[str(leg["code"])].append(rec)
                rec["coupons"].append(f"{f.stem} #{i}")
    return by_code


def to_markdown(date: str, rows: list[dict]) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    md = [f"# {date} — derin araştırma ({dt.datetime.now(TSI):%H:%M} TSİ)", "",
          "Takım geçmişi: ESPN, her takımın son ~15 bitmiş maçı (yarı skorlarıyla). Bacak testi: aynı bahis o "
          "takımların kendi maçlarında ne sıklıkla tuttu (ev sahibi evde, deplasman deplasmanda tutularak).", ""]
    for r in sorted(rows, key=lambda x: x["kickoff"]):
        md += [f"## {r['kickoff'][11:16]} {r['match']} ({r['league']})", "",
               f"Fiyat: {r['reference']} · gol beklentisi {r['mu'][0]}-{r['mu'][1]}"
               + (f" · ⚠ {'; '.join(r['flags'])}" if r["flags"] else ""), ""]
        if not r["espn"]:
            md += ["_ESPN takım verisi yok: soccerstats gibi ikinci bir kaynakla elle bakılmalı._", ""]
        else:
            md += ["| Takım | Maç | Form | Puan/maç | Attı/Yedi | İY atar / yer | 2Y atar / yer | KG | 2,5Ü | İki yarı KG |",
                   "|---|---|---|---|---|---|---|---|---|---|"]
            for side in ("home", "away"):
                t = r["teams"][side]
                if t.get("n"):
                    md.append(f"| {t['name']} | {t['n']} | {t['form']} | {t['ppg']:.2f} | {t['gf']:.2f} / {t['ga']:.2f} | "
                              f"{pct(t['score1H'])} / {pct(t['concede1H'])} | {pct(t['score2H'])} / {pct(t['concede2H'])} | "
                              f"{pct(t['btts'])} | {pct(t['over25'])} | {pct(t['both_halves_btts'])} |")
            md.append("")
        ctx = []
        for side in ("home", "away"):
            t = r["teams"][side]
            bits = ([f"eksik: {', '.join(t['absent'])}"] if t["absent"] else []) + (["1. kaleci yok"] if t["gk1_out"] else []) \
                + (["golcü yok"] if t["top_scorer_out"] else []) + ([f"Avrupa maçı: {r['europe'][side]}"] if side in r["europe"] else [])
            if bits:
                ctx.append(f"{t['name']}: " + "; ".join(bits))
        if r["h2h"]:
            ctx.append("Aralarında (son maçlar): " + " · ".join(r["h2h"]))
        if r.get("weather"):
            w = r["weather"]
            ctx.append(f"Hava: {w.get('temp_c')}°C, yağış {w.get('rain_mm')} mm, rüzgâr {w.get('wind_kmh')} km/s")
        md += [f"- {c}" for c in ctx] + ([""] if ctx else [])
        if r["legs"]:
            md += ["| Bacak | Kupon | Model | Ev sahibinin maçlarında | Deplasmanın maçlarında | Ortalama | Sonuç |", "|---|---|---|---|---|---|---|"]
            md += [f"| {x['selection']} | {', '.join(x['coupons'])} | {pct(x['p'])} | {pct(x['home_rate'])} ({x['home_n']}) | "
                   f"{pct(x['away_rate'])} ({x['away_n']}) | {pct(x['mean'])} | {x['verdict']} |" for x in r["legs"]]
            md.append("")
    return "\n".join(md) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--kuponlar", action="store_true", help="Günün son kuponlarının bütün bacakları")
    ap.add_argument("--kod", nargs="*", default=[], help="Nesine maç kodları")
    ap.add_argument("--sec", nargs="*", default=[], help="--kod maçları için test edilecek bahisler (sistem adıyla, ör. '2.5 Üst')")
    args = ap.parse_args()
    analysis = json.loads((AREA / args.tarih / "nesine_global.json").read_text(encoding="utf-8"))
    by_code = {str(m["code"]): m for m in analysis["matches"]}
    targets = coupon_legs(args.tarih) if args.kuponlar else {}
    for code in args.kod:
        targets.setdefault(str(code), [])
        for name in args.sec:
            sel = next((s for s in by_code.get(str(code), {}).get("selections", []) if s["name"] == name), None)
            targets[str(code)].append({"name": name, "label": f"{sel['market']}: {sel['selection']}" if sel else name,
                                       "p": sel["fair_prob"] if sel else None, "odds": sel["odds"] if sel else None, "coupons": []})
    rows = []
    for code, legs in targets.items():
        if code in by_code:
            rows.append(research_match(by_code[code], legs))
            print(f"{by_code[code]['home']} - {by_code[code]['away']}: tamam", flush=True)
    out = AREA / args.tarih
    (out / "derin_arastirma.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_arastirma.md").write_text(to_markdown(args.tarih, rows), encoding="utf-8")
    flagged = [x for r in rows for x in r["legs"] if x["verdict"].startswith("⚠")]
    print(f"{len(rows)} maç araştırıldı, {sum(len(r['legs']) for r in rows)} bacak test edildi, "
          f"{len(flagged)} bacağı geçmiş desteklemiyor -> {out / 'derin_arastirma.md'}")


if __name__ == "__main__":
    main()
