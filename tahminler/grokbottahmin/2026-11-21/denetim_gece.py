#!/usr/bin/env python3
"""Akşam denetimi 2026-11-21: tahminleri gerçek sonuçlarla notla.

Kaynaklar (API-Football yok):
  - Nesine GetUnliveMatches (biten maçlar, İY + 90')
  - FotMob herkese açık JSON (canlı ≥80' geçici not; İY için matchDetails)
  - ESPN public scoreboard (sabah predictions.json, event_id ile)
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

ROOT = Path("/workspace/futbol-dehasi")
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.match_dossier import team_match_score  # noqa: E402
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402

D = ROOT / "tahminler/grokbottahmin/2026-11-21"
CACHE = Path("/tmp/results_raw")
CACHE.mkdir(exist_ok=True)
FM_CACHE = CACHE / "fotmob_details"
FM_CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "QuantFoot-GrokBot/1.0 (kisisel futbol arastirmasi)", "Accept": "application/json"}
FINISHED = {"MS", "UZT", "PEN"}
TSI = dt.timezone(dt.timedelta(hours=3))
NOW = dt.datetime.now(TSI)
NEED_HT = re.compile(r"İY|2Y|Yarı|İlk Gol|En Çok Gol")
NAMEFIX = {
    "MS 0 (beraberlik)": "MS 0",
    "MS 2 ve 3,5 Alt": "MS 2 & 3.5 Alt",
    "1": "MS 1",
    "2,5 Alt": "2.5 Alt",
    "3,5 Alt": "3.5 Alt",
    "2,5 Üst": "2.5 Üst",
    "Ev 1.5 Üst": "Ev 1.5 Üst",
}


def get_json(url, params=None, timeout=40, retries=3):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=timeout)
            if r.status_code == 200 and r.content:
                return r.json()
            last = f"HTTP {r.status_code} len={len(r.content)}"
        except Exception as e:
            last = str(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url} failed: {last}")


def save_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def fetch_nesine() -> dict[int, dict]:
    out: dict[int, dict] = {}
    for day in ("2026-11-21", "2026-11-22"):
        j = get_json("https://ls.nesine.com/api/v2/LiveScore/GetUnliveMatches", {"sportType": 1, "date": day})
        save_json(CACHE / f"unlive_{day}.json", j)
        for m in j.get("d") or []:
            try:
                code = int(m["C"])
            except (KeyError, TypeError, ValueError):
                continue
            sc = {e.get("T"): (int(e.get("H", 0)), int(e.get("A", 0))) for e in m.get("ES") or []}
            rec = {
                "st": m.get("ST"),
                "home": m.get("HTTR") or m.get("HT"),
                "away": m.get("ATTR") or m.get("AT"),
                "league": m.get("L"),
            }
            if m.get("ST") in FINISHED and 2 in sc and (3 in sc or 1 in sc):
                rec.update(state="final", ht=list(sc[2]), ft=list(sc.get(3, sc.get(1))), src="nesine")
            elif m.get("ST") in ("Ert.", "Ksl."):
                rec.update(state="void", why=m.get("ST"), src="nesine")
            elif m.get("ST") == "Başlamadı.":
                rec.update(state="başlamadı", src="nesine")
            out[code] = rec
    return out


def parse_fm_minute(st: dict) -> int | None:
    lt = st.get("liveTime") or {}
    short = str(lt.get("short") or "")
    if "HT" in short.upper() or "Half" in str(lt.get("long") or ""):
        return 45
    m = re.search(r"(\d+)", str(lt.get("long") or ""))
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", short.replace("\u200e", ""))
    return int(m.group(1)) if m else None


def fetch_fotmob_list() -> list[dict]:
    out = []
    for day in ("20261121", "20261122"):
        j = get_json("https://www.fotmob.com/api/data/matches", {"date": day})
        save_json(CACHE / f"fotmob_{day}.json", j)
        for lg in j.get("leagues") or []:
            for m in lg.get("matches") or []:
                s = m.get("status") or {}
                out.append(
                    {
                        "id": m.get("id"),
                        "league": lg.get("name"),
                        "home": (m.get("home") or {}).get("name"),
                        "away": (m.get("away") or {}).get("name"),
                        "hg": (m.get("home") or {}).get("score"),
                        "ag": (m.get("away") or {}).get("score"),
                        "fin": bool(s.get("finished")),
                        "live": bool(s.get("ongoing") or (s.get("started") and not s.get("finished"))),
                        "canc": bool(s.get("cancelled")),
                        "reason": ((s.get("reason") or {}).get("short") if isinstance(s.get("reason"), dict) else None),
                        "minute": parse_fm_minute(s),
                        "utc": s.get("utcTime"),
                    }
                )
    return out


def fm_find(fm: list[dict], home: str, away: str, min_score: float = 0.72):
    best, sc = None, 0.0
    for m in fm:
        s = min(team_match_score(home, m["home"] or ""), team_match_score(away, m["away"] or ""))
        if s > sc:
            best, sc = m, s
    return (best, sc) if best and sc >= min_score else (None, sc)


def fm_ht(mid) -> list[int] | None:
    if mid is None:
        return None
    path = FM_CACHE / f"{mid}.json"
    if path.exists() and path.stat().st_size > 20:
        try:
            d = json.loads(path.read_text())
            _ev = ((d.get("content") or {}).get("matchFacts") or {}).get("events", {}).get("events") or []
            if not any(e.get("type") == "Half" and e.get("halfStrShort") == "HT" for e in _ev):
                d = None  # önbellek İY öncesinden kalmış; tazele
        except Exception:
            d = None
    else:
        d = None
    if d is None:
        try:
            time.sleep(0.55)
            d = get_json("https://www.fotmob.com/api/data/matchDetails", {"matchId": str(mid)}, timeout=30)
            save_json(path, d)
        except Exception:
            return None
    ev = ((d.get("content") or {}).get("matchFacts") or {}).get("events", {}).get("events") or []
    ht = [e for e in ev if e.get("type") == "Half" and e.get("halfStrShort") == "HT"]
    if ht:
        return [ht[0].get("homeScore"), ht[0].get("awayScore")]
    # fallback: first-half goals
    goals = [
        e
        for e in ev
        if e.get("type") in ("Goal", "OwnGoal", "Penalty") or e.get("isGoal")
    ]
    # if no structured HT, give up rather than guess
    return None


def split_teams(match: str) -> tuple[str, str]:
    parts = re.split(r"\s+-\s+", match, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return match, ""


def tier(lg: str) -> str:
    l = (lg or "").lower()
    if re.search(
        r"u1[5789]|u2\d|gençler|genç |kadın|\(k\)| kdn|rezerv|amatör|bölgesel|isthmian|"
        r"güney ligi|kuzey premier|ulusal lig|3\. lig|4\. lig|3\. federasyon|4\. federasyon|"
        r"regionalliga|oberliga|play.?off|gençler onur",
        l,
    ):
        return "3-alt/genç/kadın"
    if re.search(
        r"ingiltere premier|premier league|la liga$|ispanya la liga|bundesliga$|"
        r"almanya bundesliga|italya serie a|serie a$|fransa ligue 1|ligue 1|"
        r"türkiye süper lig|süper lig$|hollanda eredivisie|eredivisie|"
        r"portekiz liga|belçika pro|iskoçya prem|şampiyonlar l|avrupa ligi|"
        r"konferans lig|brazilya serie a|brezilya serie a|arjantin liga|liga mx|"
        r"mls$|major league soccer",
        l,
    ):
        return "1-büyük lig"
    if re.search(
        r"championship|ingiltere 1\. lig|ingiltere 2\. lig|serie b|ligue 2|2\. bundesliga|"
        r"la liga 2|2\. lig|primera|eerste|liga portugal 2|championship",
        l,
    ):
        return "2-ikinci/orta"
    return "2-diğer"


def needs_ht(name: str) -> bool:
    return bool(NEED_HT.search(name or ""))


def grade(name: str, rec: dict):
    if rec.get("state") == "void":
        return None, "void", rec.get("why") or "ertelendi/iptal"
    if rec.get("state") not in ("final", "prov"):
        return None, rec.get("state") or "bekliyor", rec.get("why")
    ht, ft = rec.get("ht"), rec.get("ft")
    if not ft or any(x is None for x in ft):
        return None, rec.get("state"), "skor yok"
    if ht is None or any(x is None for x in ht):
        if needs_ht(name):
            return None, rec.get("state"), "İY skoru yok"
        ht = [0, 0]  # 90' markets only; 2H reconstructed would be wrong so those are needs_ht
    try:
        won = settle_selection(name, tuple(ht), tuple(ft))
    except Exception as e:
        return None, rec.get("state"), f"notlanamadı: {e}"
    if won is None:
        return None, rec.get("state"), "seçim skorla çözülemedi"
    return won, rec.get("state"), None


def build_results(preds, nes, fm) -> dict[int, dict]:
    results: dict[int, dict] = {}
    for m in preds:
        code = int(m["code"])
        ko = dt.datetime.strptime(m["kickoff"], "%Y-%m-%d %H:%M").replace(tzinfo=TSI)
        rec = dict(nes.get(code) or {})
        if rec.get("state") == "final":
            results[code] = rec
            continue
        if rec.get("state") == "void":
            results[code] = rec
            continue
        if ko > NOW + dt.timedelta(minutes=5):
            rec.setdefault("state", "başlamadı")
            results[code] = rec
            continue
        home, away = split_teams(m["match"])
        f, sc = fm_find(fm, home, away)
        if not f:
            rec.update(state="eşleşmedi", why="Nesine bitmedi/yok, FotMob eşleşmesi yok", fm_score=round(sc, 3))
            results[code] = rec
            continue
        rec["fm_id"] = f["id"]
        rec["fm_match"] = f"{f['home']} - {f['away']}"
        rec["fm_score"] = round(sc, 3)
        if f["canc"] or f["reason"] in ("PP", "Ab"):
            rec.update(state="void", why=f["reason"] or "iptal", src="fotmob")
            results[code] = rec
            continue
        if f["fin"]:
            rec.update(state="final", ft=[f["hg"], f["ag"]], src="fotmob")
            results[code] = rec
            continue
        if f["live"] and (f["minute"] or 0) >= 80:
            rec.update(state="prov", ft=[f["hg"], f["ag"]], minute=f["minute"], src="fotmob-canlı")
            results[code] = rec
            continue
        if f["live"]:
            rec.update(state="canlı<80", minute=f["minute"], ft=[f["hg"], f["ag"]], src="fotmob-canlı")
            results[code] = rec
            continue
        rec.update(state="bekliyor", why="FotMob'da başladı görünmüyor / bitmedi", src="fotmob")
        results[code] = rec
    # fetch HT only when a suitable IY/2Y selection exists for a graded match
    need = []
    for m in preds:
        rec = results[int(m["code"])]
        if rec.get("state") not in ("final", "prov"):
            continue
        if rec.get("ht") is not None:
            continue
        names = [s.get("name") or "" for f in m.get("families") or [] for s in f.get("suitable") or []]
        if any(needs_ht(n) for n in names) or rec.get("fm_id"):
            # always try HT when fotmob id exists and we grade the match — cheap enough for headline too
            if rec.get("fm_id"):
                need.append(int(m["code"]))
            elif any(needs_ht(n) for n in names):
                need.append(int(m["code"]))
    print(f"İY skoru çekilecek maç: {len(need)}", flush=True)
    for i, code in enumerate(need, 1):
        rec = results[code]
        if not rec.get("fm_id"):
            # try find again from names stored? skip
            continue
        ht = fm_ht(rec["fm_id"])
        if ht is not None:
            rec["ht"] = ht
        if i % 25 == 0:
            print(f"  HT {i}/{len(need)}", flush=True)
    return results


def attach_ht_via_fm(rec, match_name, fm):
    if rec.get("ht") is not None:
        return rec
    home, away = split_teams(match_name)
    f, _ = fm_find(fm, home, away)
    if f and (f["fin"] or (f["live"] and (f["minute"] or 0) >= 80)):
        rec = dict(rec)
        if not rec.get("ft"):
            rec["ft"] = [f["hg"], f["ag"]]
            rec["state"] = "final" if f["fin"] else "prov"
            if f["live"]:
                rec["minute"] = f["minute"]
                rec["src"] = rec.get("src") or "fotmob-canlı"
        rec["fm_id"] = f["id"]
        ht = fm_ht(f["id"])
        if ht is not None:
            rec["ht"] = ht
    return rec


def selections(m):
    out = []
    for f in m.get("families") or []:
        for s in f.get("suitable") or []:
            if (s.get("odds") or 0) >= 1.20 and s.get("name"):
                out.append({**s, "family": f["family"]})
    return out


def summ(rs):
    g = [x for x in rs if x["won"] is True or x["won"] is False]
    n = len(g)
    w = sum(1 for x in g if x["won"] is True)
    void = sum(1 for x in rs if x.get("note") == "void" or x.get("kind") == "void")
    ungr = sum(1 for x in rs if x["won"] is None and x.get("kind") in ("final", "prov"))
    return {
        "n_graded": n,
        "correct": w,
        "wrong": n - w,
        "void": void,
        "ungraded": ungr,
        "hit_rate": round(w / n, 4) if n else None,
        "avg_predicted_p": round(sum(x["p"] for x in g) / n, 4) if n else None,
        "calibration_gap": round((w / n) - (sum(x["p"] for x in g) / n), 4) if n else None,
    }


def bins(rs, edges=None):
    edges = edges or ((0.0, 0.60, "<60"), (0.60, 0.65, "60-65"), (0.65, 0.70, "65-70"), (0.70, 0.75, "70-75"), (0.75, 2.0, "75+"))
    out = {}
    for lo, hi, lab in edges:
        out[lab] = summ([x for x in rs if lo <= (x.get("p") or 0) < hi])
    return out


def group(rs, key):
    d = defaultdict(list)
    for x in rs:
        d[x.get(key) or "?"] .append(x)
    return {k: summ(v) for k, v in sorted(d.items(), key=lambda kv: (-(kv[1] and (summ(kv[1])["n_graded"] or 0)), kv[0]))}


def espn_events_from_disk_or_fetch():
    events = {}
    for day in ("20261121", "20261122"):
        path = CACHE / f"espn_{day}_limit500.json"
        data = None
        try:
            data = get_json(
                "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard",
                {"dates": day, "limit": 500},
                timeout=50,
            )
            save_json(path, data)
        except Exception as e:
            print("ESPN fetch failed, using disk:", e, flush=True)
            if path.exists():
                data = json.loads(path.read_text())
        if not data:
            continue
        for e in data.get("events") or []:
            events[str(e["id"])] = e
    return events


def ht_from_espn(event) -> list[int] | None:
    comp = (event.get("competitions") or [{}])[0]
    sides = {c["homeAway"]: c for c in comp.get("competitors") or []}
    hid = ((sides.get("home") or {}).get("team") or {}).get("id")
    hh = ha = 0
    goals = [d for d in (comp.get("details") or []) if d.get("scoringPlay") and not d.get("shootout")]
    if not goals and not (comp.get("details") or []):
        # no play-by-play: HT unknown (unless 0-0 and HT/1H)
        st = (event.get("status") or {}).get("type") or {}
        score_h = int((sides.get("home") or {}).get("score") or 0)
        score_a = int((sides.get("away") or {}).get("score") or 0)
        if st.get("name") in ("STATUS_HALFTIME", "STATUS_FIRST_HALF") or (
            st.get("name") in ("STATUS_FULL_TIME", "STATUS_SECOND_HALF") and score_h + score_a == 0
        ):
            return [score_h, score_a] if st.get("name") in ("STATUS_HALFTIME", "STATUS_FIRST_HALF") else [0, 0]
        return None
    for g in goals:
        dv = str((g.get("clock") or {}).get("displayValue") or "")
        # 45'+n or minute <= 45 => first half; "46'"+"47'" without plus are ambiguous — treat clock<2700 as 1H
        clock = (g.get("clock") or {}).get("value")
        m = re.match(r"(\d+)'(?:\+(\d+))?", dv)
        first = None
        if m:
            base, plus = int(m.group(1)), m.group(2)
            if plus is not None:
                first = base <= 45
            elif base <= 45:
                first = True
            elif base >= 46 and clock is not None:
                first = float(clock) < 2700
            else:
                first = False
        elif clock is not None:
            first = float(clock) < 2700
        else:
            return None  # don't guess
        if first:
            if str((g.get("team") or {}).get("id")) == str(hid):
                hh += 1
            else:
                ha += 1
    return [hh, ha]


def espn_rec(event) -> dict:
    typ = (event.get("status") or {}).get("type") or {}
    clock = event.get("status") or {}
    sides = {c["homeAway"]: c for c in (event.get("competitions") or [{}])[0].get("competitors") or []}
    ft = [
        int((sides.get("home") or {}).get("score") or 0),
        int((sides.get("away") or {}).get("score") or 0),
    ]
    disp = str(clock.get("displayClock") or typ.get("shortDetail") or "")
    mm = re.search(r"(\d+)", disp.replace("'", " "))
    minute = int(mm.group(1)) if mm else None
    name = typ.get("name")
    rec = {"ft": ft, "ht": ht_from_espn(event), "minute": minute, "espn_status": name, "src": "espn"}
    if typ.get("completed") or name == "STATUS_FULL_TIME":
        rec["state"] = "final"
    elif name in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_ABANDONED"):
        rec["state"] = "void"
        rec["why"] = name
    elif name == "STATUS_SECOND_HALF" and (minute or 0) >= 80:
        rec["state"] = "prov"
    elif name in ("STATUS_FIRST_HALF", "STATUS_HALFTIME", "STATUS_SECOND_HALF", "STATUS_IN_PROGRESS"):
        rec["state"] = "canlı<80" if (minute or 0) < 80 else "prov"
        if (minute or 0) >= 80:
            rec["state"] = "prov"
    else:
        rec["state"] = "başlamadı"
    return rec


def main():
    print("Nesine sonuçları…", flush=True)
    nes = fetch_nesine()
    print(f"  Nesine kod: {len(nes)}, bitmiş: {sum(1 for r in nes.values() if r.get('state')=='final')}", flush=True)
    print("FotMob listesi…", flush=True)
    fm = fetch_fotmob_list()
    print(f"  FotMob: {len(fm)} fin={sum(x['fin'] for x in fm)} live={sum(x['live'] for x in fm)}", flush=True)

    preds = json.loads((D / "derin_tahminler.json").read_text())
    print(f"Tahmin: {len(preds)} maç", flush=True)
    results = build_results(preds, nes, fm)
    save_json(CACHE / "denetim_gece_results_partial.json", results)
    st = Counter(r.get("state") for r in results.values())
    print("maç durumları", dict(st), flush=True)

    rows = []
    for m in preds:
        rec = results[int(m["code"])]
        sel = selections(m)
        if not sel:
            continue
        top = max(sel, key=lambda s: (s["p"], -s["odds"]))
        for s in sel:
            won, kind, why = grade(s["name"], rec)
            rows.append(
                {
                    "code": m["code"],
                    "match": m["match"],
                    "league": m["league"],
                    "tier": tier(m["league"]),
                    "kickoff": m["kickoff"],
                    "name": s["name"],
                    "label": s.get("label"),
                    "family": s["family"],
                    "p": s["p"],
                    "odds": s["odds"],
                    "headline": s["name"] == top["name"] and s["p"] == top["p"],
                    "won": won,
                    "kind": kind,
                    "note": why,
                    "ht": rec.get("ht"),
                    "ft": rec.get("ft"),
                    "minute": rec.get("minute"),
                    "src": rec.get("src"),
                }
            )

    # ensure one headline per match (ties)
    seen = set()
    for x in rows:
        if x["headline"]:
            key = x["code"]
            if key in seen:
                x["headline"] = False
            else:
                seen.add(key)

    fin = [x for x in rows if x["kind"] == "final"]
    prov = [x for x in rows if x["kind"] == "prov"]
    head_f = [x for x in fin if x["headline"]]
    head_p = [x for x in prov if x["headline"]]

    misses = sorted([x for x in head_f if x["won"] is False], key=lambda x: (-x["p"], x["odds"]))[:20]
    hits_high = sorted([x for x in head_f if x["won"] is True], key=lambda x: (-x["p"], x["odds"]))[:5]

    # morning predictions.json
    print("ESPN (sabah predictions.json)…", flush=True)
    events = espn_events_from_disk_or_fetch()
    morning = json.loads((D / "predictions.json").read_text())["matches"]
    mrows = []
    mstate = Counter()
    for m in morning:
        ev = events.get(str(m["event_id"]))
        if not ev:
            mstate["ESPN'de yok"] += 1
            continue
        rec = espn_rec(ev)
        offered = m.get("offered_odds") or {}
        probs = m.get("probs") or {}
        cands = []
        for name, odds in offered.items():
            if odds and odds >= 1.20 and name in probs:
                cands.append({"name": name, "odds": odds, "p": probs[name]})
        if not cands:
            mstate[rec["state"] + " (seçim yok)"] += 1
            continue
        top = max(cands, key=lambda s: (s["p"], -s["odds"]))
        if rec["state"] not in ("final", "prov", "void"):
            mstate[rec["state"]] += 1
            continue
        won, kind, why = grade(top["name"], rec)
        mstate[kind or rec["state"]] += 1
        mrows.append(
            {
                "match": f'{m["home"]} - {m["away"]}',
                "league": m["league"],
                "name": top["name"],
                "p": top["p"],
                "odds": top["odds"],
                "won": won,
                "kind": kind,
                "note": why,
                "ft": rec.get("ft"),
                "ht": rec.get("ht"),
            }
        )

    # 10 picks
    TEN = [
        ("Lugano", "MS 1"),
        ("Sevilla", "3.5 Alt"),
        ("Feyenoord", "Dep İY 0.5 Alt"),
        ("Mechelen", "MS 2"),
        ("Strasbourg", "İY 0.5 Üst"),
        ("Lens", "DEĞİL(Ev İki Yarıda Gol)"),
        # user said "RC Lens – Toulouse: Ev sahibi iki yarıda da gol atamaz"
        ("Lille", "ÇŞ 12"),
        ("Real Madrid", "2.5 Üst"),
        ("Inter Miami", "4.5 Alt"),
        ("Pumas", "İY 0.5 Üst"),
    ]
    ten = []
    for team, nm in TEN:
        mm = next((m for m in preds if team.lower() in m["match"].lower()), None)
        if not mm:
            ten.append({"pick": f"{team} {nm}", "state": "tahmin dosyasında yok"})
            continue
        rec = results[int(mm["code"])]
        won, kind, why = grade(nm, rec)
        ten.append(
            {
                "pick": f"{mm['match']} — {nm}",
                "code": mm["code"],
                "kickoff": mm["kickoff"],
                "league": mm["league"],
                "won": won,
                "state": kind,
                "note": why,
                "ht": rec.get("ht"),
                "ft": rec.get("ft"),
                "minute": rec.get("minute"),
            }
        )

    # coupons
    coupons_in = json.loads((ROOT / "tahminler/grokbottahmin/oynanan_kuponlar.json").read_text())["coupons"]
    coupons = []
    for c in coupons_in:
        legs = []
        for L in c["legs"]:
            nm = NAMEFIX.get(L["name"], L["name"])
            rec = dict(results.get(int(L["code"])) or nes.get(int(L["code"])) or {})
            if rec.get("state") not in ("final", "prov", "void"):
                rec = attach_ht_via_fm(rec, L["match"], fm)
            # if still no result but earlier ledger already settled a HT market
            won, kind, why = grade(nm, rec)
            if won is None and L.get("won") is not None and kind not in ("final", "prov"):
                # only use prior grade if the previous audit had a definitive won/lost
                won, kind, why = L["won"], "önceki-denetim", "bu akşam skor bulunamadı; önceki kesin not"
            legs.append(
                {
                    "code": L["code"],
                    "kickoff": L.get("ko"),
                    "match": L["match"],
                    "name": nm,
                    "odds": L["odds"],
                    "p": L["p"],
                    "won": won,
                    "state": kind,
                    "note": why,
                    "ht": rec.get("ht"),
                    "ft": rec.get("ft") or rec.get("score"),
                    "minute": rec.get("minute"),
                    "prior_won": L.get("won"),
                }
            )
        if any(l["won"] is False for l in legs):
            status = "KAYBETTİ"
        elif all(l["won"] is True for l in legs) and legs:
            status = "KAZANDI"
        else:
            status = "açık"
        coupons.append(
            {
                "id": c["id"],
                "stake": c["stake"],
                "odds": c["odds"],
                "mode": c["mode"],
                "prior_status": c.get("status"),
                "status": status,
                "legs_won": sum(l["won"] is True for l in legs),
                "legs_lost": sum(l["won"] is False for l in legs),
                "legs_pending": sum(l["won"] is None for l in legs),
                "legs": legs,
            }
        )

    match_states = dict(Counter(r.get("state") for r in results.values()))
    ungraded = Counter()
    for x in rows:
        if x["won"] is None and x["kind"] in ("final", "prov"):
            ungraded[x.get("note") or "bilinmiyor"] += 1

    out = {
        "generated_at": NOW.strftime("%Y-%m-%dT%H:%M+03:00"),
        "timezone": "Europe/Istanbul (UTC+3)",
        "sources": (
            "Nesine GetUnliveMatches (biten, İY+90'); "
            "FotMob public JSON (canlı ≥80' geçici not, İY için matchDetails); "
            "ESPN public scoreboard (sabah predictions.json, event_id). "
            "API-Football kullanılmadı. SofaScore 403 verdi, kullanılmadı."
        ),
        "n_deep_matches": len(preds),
        "n_morning_matches": len(morning),
        "match_states": match_states,
        "headline_final": summ(head_f),
        "headline_provisional": summ(head_p),
        "all_suitable_final": summ(fin),
        "all_suitable_provisional": summ(prov),
        "calibration_headline_final": bins(head_f),
        "calibration_all_final": bins(fin),
        "tier_headline_final": group(head_f, "tier"),
        "tier_all_final": group(fin, "tier"),
        "family_headline_final": group(head_f, "family"),
        "family_all_final": group(fin, "family"),
        "ungraded_on_finished_or_prov": dict(ungraded),
        "biggest_headline_misses": [
            {k: x[k] for k in ("match", "kickoff", "league", "name", "p", "odds", "ft", "ht", "src")}
            for x in misses
        ],
        "morning_predictions": {
            "states": dict(mstate),
            "headline_final": summ([x for x in mrows if x["kind"] == "final"]),
            "headline_provisional": summ([x for x in mrows if x["kind"] == "prov"]),
            "rows": mrows,
        },
        "ten_picks_1933": ten,
        "coupons": coupons,
        "rows": rows,
        "results_index": {str(k): v for k, v in results.items()},
    }
    save_json(D / "denetim_gece_2026-11-21.json", out)
    print("JSON yazıldı", flush=True)
    print("HEADLINE final", out["headline_final"], flush=True)
    print("HEADLINE prov", out["headline_provisional"], flush=True)
    print("ALL final", out["all_suitable_final"], flush=True)
    print("ALL prov", out["all_suitable_provisional"], flush=True)
    print("CALIB", out["calibration_headline_final"], flush=True)
    print("TIER", out["tier_headline_final"], flush=True)
    print("TEN", json.dumps(ten, ensure_ascii=False, indent=1), flush=True)
    print("COUPONS", flush=True)
    for c in coupons:
        print(f"  {c['id']} {c['status']} W{c['legs_won']} L{c['legs_lost']} P{c['legs_pending']}", flush=True)
    print("MORNING", out["morning_predictions"]["states"], out["morning_predictions"]["headline_final"], flush=True)
    print("STATES", match_states, "ungraded", dict(ungraded), flush=True)


if __name__ == "__main__":
    main()
