"""Price every Nesine selection of the day against a GLOBAL reference price, never against Nesine itself.

    python scripts/nesine_global.py --date 2026-11-19            # writes reports/daily/<date>/nesine_global.{json,md}
    python scripts/nesine_global.py --date 2026-11-19 --min-ev 0.0

Reference price, best available per match (all free, no key, no quota):
  1. Pinnacle — from football-data.co.uk fixture files
  2. Smarkets exchange — bid/offer mid
     (1 and 2 are not reachable from Turkey; GitHub Actions fetches them abroad into
      data/global_odds/latest/references.json, see .github/workflows/global-odds.yml)
  3. ESPN odds feed (DraftKings) — fetched locally, weakest reference.
Matches without any reference are listed but NOT priced (fair prices are never derived from
Nesine's own odds).

From the reference 1X2 (+ O/U when quoted) the margin is removed (power method), goal rates are
fitted with no model prior (fund_weight = 0) and every Nesine market — İY/MS, KG, gol aralığı,
handikap, kombineler … — is priced from the coherent joint goal distribution (docs/markets.md;
derivative calibration in docs/research/experiments_2026_11.md). EV = fair probability × Nesine odds − 1.

Research context (reports/research/): fundamental models add no information to sharp prices;
the documented edge is a soft book offering more than the sharp fair price.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import difflib
import json
from pathlib import Path
import re
import unicodedata

from quantfoot.data.live_espn import fetch_espn_slate
from quantfoot.data.match_research import espn_events, fpl_availability, motivation, research, staleness_flags
from quantfoot.data.nesine import TSI, fetch_bulletin, league_names, market_overrounds, parse_bulletin
from quantfoot.markets.devig import devig
from quantfoot.markets.goal_markets import goal_probability
from quantfoot.markets.goal_timing import GoalTimingModel
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.tail_goals import fit_tail_rates_from_markets, league_tail_regime
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "reports" / "daily"
_STOP = r"\b(fc|cf|sc|ac|sk|fk|nk|cd|ca|club|de|da|the|utd|united|k|w|women|kadinlar|u\d+|bk|if|ik|afc|scc|sp|ba)\b"


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(k\)|\(kol\)", " ", s)
    s = re.sub(_STOP, " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _sim(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    pref = 1.0 if (na[:5] == nb[:5] and len(na) >= 5) else 0.0
    return max(ratio, jacc, 0.85 * pref)


def _match(event, candidates: list[dict], max_hours: float = 3.0, threshold: float = 0.62) -> tuple[dict | None, float]:
    best, score = None, 0.0
    for c in candidates:
        if abs((c["kickoff"] - event.kickoff).total_seconds()) > max_hours * 3600:
            continue
        s = (_sim(event.home, c["home"]) + _sim(event.away, c["away"])) / 2
        if s > score:
            best, score = c, s
    return (best, score) if score >= threshold else (None, score)


# ---- reference sources ------------------------------------------------------------------
MAX_PLAUSIBLE_EV = 0.25
SOURCE_RANK = {"Pinnacle (football-data)": 0, "Smarkets (borsa)": 1, "Matchbook (borsa)": 1,
               "Betfair Borsası (football-data)": 2, "ESPN (DraftKings/ESPN BET)": 3}
EXCHANGES = ("Smarkets (borsa)", "Matchbook (borsa)")


MAX_CONSENSUS_GAP = 0.08  # two sharp exchanges disagreeing by > 8 pts on one outcome = one of them is wrong


def _gap(x: list[float], y: list[float]) -> float:
    return max(abs(u - v) for u, v in zip(devig(x, method="power").probabilities, devig(y, method="power").probabilities))


def consensus(a: dict, b: dict) -> dict | None:
    """Average the margin-free probabilities of two independent exchanges (1X2, and O/U on the same line)."""
    def _avg(x: list[float], y: list[float]) -> list[float]:
        px = devig(x, method="power").probabilities
        py = devig(y, method="power").probabilities
        return [round(2 / (u + v), 4) for u, v in zip(px, py)]

    if _gap(a["x12"], b["x12"]) > MAX_CONSENSUS_GAP:
        return None  # exchanges contradict each other: do not price this match
    out = dict(a, source=" + ".join(sorted({a["source"].split(" ")[0], b["source"].split(" ")[0]})) + " (borsa)")
    out["x12"] = _avg(a["x12"], b["x12"])
    if a.get("ou") and b.get("ou") and a["ou"][0] == b["ou"][0]:
        # contradictory totals -> use neither (fit on 1X2 only) rather than a possibly wrong line
        out["ou"] = [a["ou"][0], _avg(a["ou"][1], b["ou"][1])] if _gap(a["ou"][1], b["ou"][1]) <= MAX_CONSENSUS_GAP else None
    else:
        out["ou"] = a.get("ou") or b.get("ou")
    out["markets"] = a.get("markets") or b.get("markets")
    out["fetched_utc"] = min(filter(None, [a.get("fetched_utc"), b.get("fetched_utc")]), default=None)
    out["consensus_gap"] = round(_gap(a["x12"], b["x12"]), 4)
    return out
GLOBAL_FILE = ROOT / "data" / "global_odds" / "latest" / "references.json"


def global_references(max_age_hours: float = 30.0) -> tuple[list[dict], str | None]:
    """Sharp references fetched abroad by GitHub Actions (empty if missing or stale)."""
    if not GLOBAL_FILE.exists():
        return [], None
    data = json.loads(GLOBAL_FILE.read_text(encoding="utf-8"))
    generated = data.get("generated_utc")
    if generated:
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)
        if age.total_seconds() > max_age_hours * 3600:
            return [], generated
    refs = []
    for r in data.get("references", []):
        try:
            refs.append({**r, "kickoff": dt.datetime.fromisoformat(r["kickoff_utc"].replace("Z", "+00:00"))})
        except (KeyError, TypeError, ValueError):
            continue
    return refs, generated


def espn_references(dates: list[str]) -> list[dict]:
    refs = []
    for d in dates:
        for f in fetch_espn_slate(d.replace("-", "")):
            if not f.cur_1x2:
                continue
            refs.append({
                "source": "ESPN (DraftKings/ESPN BET)",
                "home": f.home_team, "away": f.away_team,
                "kickoff": dt.datetime.fromisoformat(f.date_utc.replace("Z", "+00:00")),
                "x12": list(f.cur_1x2),
                "ou": (float(f.ou_line), list(f.ou_odds)) if f.ou_line is not None and f.ou_odds and float(f.ou_line) % 1 == 0.5 else None,
            })
    return refs


# ---- pricing ----------------------------------------------------------------------------
_SIDE = {"HOME": "1", "DRAW": "0", "AWAY": "2"}
_KG = {"YES": "KG Var", "NO": "KG Yok"}
_OU = {"OVER": "Üst", "UNDER": "Alt"}


def _line(market: str) -> str | None:
    m = re.search(r"(\d+\.5)", market)
    return f"{float(m.group(1)):.1f}" if m else None


def _direct_name(market: str, label: str) -> str | None:
    """Smarkets market name + "CONTRACT_TYPE|contract name" -> canonical selection name (goal_markets syntax)."""
    ctype, _, cname = label.partition("|")
    parts = ctype.split("_")
    mk, line = market.lower(), _line(market)
    if mk.startswith("over/under") and line and ctype in _OU:
        return f"{line} {_OU[ctype]}"
    if mk.startswith("first half over/under") and line and ctype in _OU:
        return f"İY {line} {_OU[ctype]}"
    if mk.startswith("second half over/under") and line and ctype in _OU:
        return f"2Y {line} {_OU[ctype]}"
    if mk == "both teams to score" and ctype in _KG:
        return _KG[ctype]
    if mk == "both teams to score in first half" and ctype in _KG:
        return f"İY {_KG[ctype]}"
    if mk == "both teams to score in second half" and ctype in _KG:
        return f"2Y {_KG[ctype]}"
    if mk == "both teams to score in first half / second half" and ctype == "YES_YES":
        return "İki Yarıda KG Var"
    if mk.startswith("both teams to score and over/under") and line and len(parts) == 2 and parts[0] in _KG and parts[1] in _OU:
        return f"{line} {_OU[parts[1]]} & {_KG[parts[0]]}"
    if mk == "half-time result" and ctype in _SIDE:
        return f"İY {_SIDE[ctype]}"
    if mk == "second half result" and ctype in _SIDE:
        return f"2Y {_SIDE[ctype]}"
    if mk == "half-time/full-time" and len(parts) == 2 and all(x in _SIDE for x in parts):
        return f"İY/MS {_SIDE[parts[0]]}/{_SIDE[parts[1]]}"
    if mk == "odd or even score" and ctype in ("ODD", "EVEN"):
        return "Tek" if ctype == "ODD" else "Çift"
    if mk == "first half odd or even score" and ctype in ("ODD", "EVEN"):
        return "İY Tek" if ctype == "ODD" else "İY Çift"
    if mk == "goal range" and cname.replace(" ", "") in ("0-1", "2-3"):  # Nesine bands 4-5 / 6+ differ from 4-6 / 7+
        return f"{cname.replace(' ', '')} Gol"
    if mk == "winner and both teams to score" and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _KG:
        return f"MS {_SIDE[parts[0]]} & {_KG[parts[1]]}"
    if mk.startswith("winner and over/under") and line and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _OU:
        return f"MS {_SIDE[parts[0]]} & {line} {_OU[parts[1]]}"
    if mk == "first half winner and both teams to score" and len(parts) == 2 and parts[0] in _SIDE and parts[1] in _KG:
        return f"İY {_SIDE[parts[0]]} & İY {_KG[parts[1]]}"
    return None


def direct_probabilities(ref: dict) -> dict[str, float]:
    """Margin-free probabilities quoted directly by the global source for individual selections."""
    out: dict[str, float] = {}
    for market, contracts in (ref.get("markets") or {}).items():
        for label, p in contracts.items():
            name = _direct_name(market, label)
            if name:
                out[name] = float(p)
    return out


def price_event(event, ref: dict, league: str) -> dict:
    p1x2 = devig(ref["x12"], method="power").probabilities
    ou_line, p_over = None, None
    if ref.get("ou"):
        ou_line = ref["ou"][0]
        p_over = float(devig(ref["ou"][1], method="power").probabilities[0])
    regime_key = "women" if is_uncalibrated_competition(league) else None
    nu, alpha, kappa = league_tail_regime(regime_key)
    mu_h, mu_a, _ = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=ou_line, p_over=p_over, seed_rates=(1.45, 1.15),
                                                alpha_nb=alpha, shared_kappa=kappa, com_nu=nu, fund_weight=0.0)
    joint = compute_omni_markets(mu_h, mu_a, league=regime_key).joint
    timing = GoalTimingModel.from_joint(joint).markets()["İlk Golü Atan Takım"]
    derivatives_ok = not is_uncalibrated_competition(league)
    quoted = direct_probabilities(ref)
    # Without any quoted total the goal level is extrapolated from 1X2 alone (it overshoots for big favourites):
    # then only pure result markets are priced from the model.
    totals_known = ou_line is not None or any("Üst" in k or "Alt" in k for k in quoted)
    rows = []
    for s in event.selections:
        direct = s.name in ("MS 1", "MS 0", "MS 2") or (ou_line is not None and s.name in (f"{ou_line:.1f} Üst", f"{ou_line:.1f} Alt"))
        if s.name in quoted:
            direct = True  # the global source prices this exact selection: use its own price, not the model
        if not direct and not derivatives_ok:
            continue  # derivative distribution not calibrated for this competition
        if not direct and not totals_known and not (s.name.startswith(("MS ", "ÇŞ ")) and "&" not in s.name):
            continue  # goal-count market with no global total to anchor it
        if s.name in quoted:
            p = quoted[s.name]
        elif s.name.startswith("İlk Gol"):
            p = timing.get(s.name)
        else:
            p = goal_probability(s.name, joint)
        if p is None:
            continue
        if s.negate:
            p = 1.0 - p
        # Nesine templates ("{{handicap}} Gol Alt/Üst" / "{{SOV}} Üst"): show the resolved name instead.
        market = s.market_title.replace("{{handicap}} ", "").replace(" ({{handicap}})", "")
        label = s.name if "{{" in s.label or "{{" in s.market_title else s.label
        rows.append({"market": market, "selection": label, "name": s.name if not s.negate else f"DEĞİL({s.name})",
                     "odds": s.odds, "fair_prob": round(p, 5), "fair_odds": round(1 / p, 3) if p > 1e-9 else None,
                     "ev": round(p * s.odds - 1.0, 4), "mbs": s.mbs, "direct": direct})
    rows.sort(key=lambda r: r["ev"], reverse=True)
    nesine_ms = [event.odds_of(f"MS {c}") for c in "102"]
    margin = sum(1 / o for o in nesine_ms) - 1 if all(nesine_ms) else None
    return {"mu_home": round(float(mu_h), 3), "mu_away": round(float(mu_a), 3), "reference": ref["source"],
            "ref_fetched_utc": ref.get("fetched_utc"), "consensus_gap": ref.get("consensus_gap"),
            "ref_1x2": ref["x12"], "ref_ou": ref.get("ou"), "fair_1x2": [round(float(x), 4) for x in p1x2],
            "nesine_ms_margin": None if margin is None else round(margin, 4), "derivatives_priced": derivatives_ok, "selections": rows}


MAX_PAIRING_GAP = 0.15  # Nesine's own 1X2, devigged, vs the reference: a bigger gap means a wrong pairing


def _consistent(event, ref: dict) -> bool:
    """Sanity check of a name/time pairing: Nesine's 1X2 must tell roughly the same story as the reference."""
    nes = [event.odds_of(f"MS {c}") for c in "102"]
    if not all(nes) or not ref.get("x12"):
        return True  # nothing to compare
    pn = devig(nes, method="power").probabilities
    pr = devig(ref["x12"], method="power").probabilities
    return max(abs(a - b) for a, b in zip(pn, pr)) <= MAX_PAIRING_GAP


def _owners(events: list, refs: list[dict]) -> dict[int, object]:
    """Each reference belongs to the one Nesine event it resembles most (no reference priced twice)."""
    best: dict[int, tuple[float, object]] = {}
    for e in events:
        for r in refs:
            if abs((r["kickoff"] - e.kickoff).total_seconds()) > 3 * 3600:
                continue
            sc = (_sim(e.home, r["home"]) + _sim(e.away, r["away"])) / 2
            if sc > best.get(id(r), (0.0, None))[0]:
                best[id(r)] = (sc, e.code)
    return {k: v[1] for k, v in best.items()}


def _absent(r: dict, side: str) -> str:
    """Key absences for the report (Premier League official list); '-' when unknown."""
    a = (r.get("absences") or {}).get(side)
    if not a:
        return "-"
    key = []
    for p in a["players"]:
        if p["key"]:
            chance = f" %{p['chance']}" if p["chance"] not in (None, 0) else ""
            key.append(f"{p['name']} ({p['status']}{chance})")
    return ", ".join(key) or "kilit eksik yok"


def attach_research(out: list[dict], events: list, day: dt.date, sharp_generated: str | None) -> None:
    """Add ESPN research (form, table, rest, line-ups, absences) to priced matches; flag stale prices."""
    pool = []
    for d in (day - dt.timedelta(days=1), day, day + dt.timedelta(days=1)):
        pool += [{**x, "source": "ESPN"} for x in espn_events(d.strftime("%Y%m%d"))]
    by_code = {e.code: e for e in events}
    jobs = {}
    for rec in out:
        if rec.get("status") != "fiyatlandı":
            continue
        hit, _ = _match(by_code[rec["code"]], pool)
        if hit:
            jobs[rec["code"]] = hit["id"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(zip(jobs, ex.map(research, jobs.values())))
    gen = dt.datetime.fromisoformat(sharp_generated) if sharp_generated else None
    for rec in out:
        res = results.get(rec["code"])
        if not res:
            continue
        if rec.get("ref_fetched_utc"):
            price_time = dt.datetime.fromisoformat(rec["ref_fetched_utc"])
        else:  # ESPN references are fetched live, now
            price_time = None if rec["reference"].startswith("ESPN") else gen
        flags = staleness_flags(res, price_time)
        res["motivation"] = {side: motivation(t, res.get("league_slug")) for side, t in res["teams"].items()}
        res["flags"] = flags
        rec["research"] = res
        # Important absence in a line-up published after our price was fetched -> keep out of coupons.
        rec["research_block"] = bool(flags) and flags[-1].startswith("global fiyat")
    # Premier League: official injury / suspension list (already priced by the market; shown as context).
    fpl = None
    for rec in out:
        if rec.get("status") != "fiyatlandı" or rec.get("league") != "İngiltere Premier Lig":
            continue
        fpl = fpl if fpl is not None else fpl_availability()
        absences = {}
        for side, name in (("home", rec["home"]), ("away", rec["away"])):
            team = max(fpl, key=lambda t: _sim(name, t), default=None)
            if team and _sim(name, team) >= 0.6:
                absences[side] = {"team": team, "players": fpl[team]}
        if absences:
            rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})["absences"] = absences


def analyze_day(day: dt.date, verbose: bool = True, with_research: bool = True) -> tuple[list[dict], dict, list]:
    """Fetch the live Nesine bulletin and price every match of `day` against the best global reference.

    Returns (match records, raw bulletin payload, parsed events). Used by main() and nesine_kupon.py.
    """
    nxt = day + dt.timedelta(days=1)
    payload = fetch_bulletin()
    leagues = league_names(payload)
    # Betting day = 07:00–07:00 TSİ, so consecutive days never share a match.
    events = [e for e in parse_bulletin(payload)
              if (e.kickoff.date() == day and e.kickoff.hour >= 7) or (e.kickoff.date() == nxt and e.kickoff.hour < 7)]
    sharp, generated = global_references()
    espn = espn_references([day.isoformat(), nxt.isoformat()])
    if verbose:
        print(f"Nesine {day}: {len(events)} futbol maçı")
        print(f"Global (Pinnacle/Smarkets/Betfair): {len(sharp)} referans (oluşturulma {generated or 'yok'})")
        print(f"ESPN: {len(espn)} maçta oran bulundu")
    refs = sharp + espn
    owner = _owners(events, refs)
    out = []
    for e in sorted(events, key=lambda x: x.kickoff):
        league = leagues.get(e.league_code, str(e.league_code))
        ref, score = None, 0.0
        mine = [r for r in refs if owner.get(id(r)) == e.code and _consistent(e, r)]
        for rank in sorted(set(SOURCE_RANK.values())):  # best source first
            pool = [r for r in mine if SOURCE_RANK.get(r["source"], 9) == rank]
            ref, score = _match(e, pool) if pool else (None, 0.0)
            if ref is not None:
                break
        contradiction = False
        if ref is not None and ref["source"] in EXCHANGES:
            other, _ = _match(e, [r for r in mine if r["source"] in EXCHANGES and r["source"] != ref["source"]])
            if other is not None:
                ref = consensus(ref, other)  # None when the two exchanges contradict each other
                contradiction = ref is None
        rec = {"code": e.code, "kickoff": e.kickoff.strftime("%Y-%m-%d %H:%M"), "kickoff_iso": e.kickoff.isoformat(),
               "league": league, "home": e.home, "away": e.away,
               "nesine_ms": [e.odds_of(f"MS {c}") for c in "102"], "n_nesine_selections": len(e.selections)}
        if ref is None:
            rec["status"] = ("borsalar birbiriyle çelişiyor (> 8 puan) — fiyatlanmadı" if contradiction
                             else "global referans bulunamadı — fiyatlanmadı")
        else:
            rec.update(match_score=round(score, 2), ref_match=f"{ref['home']} - {ref['away']}", **price_event(e, ref, league))
            rec["status"] = "fiyatlandı"
        out.append(rec)
    if with_research:
        attach_research(out, events, day, generated)
    return out, payload, events


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--min-ev", type=float, default=0.0)
    ap.add_argument("--hafta", type=int, default=1, help="Kaç gün analiz edilsin (ör. 7: bugünden itibaren bütün hafta)")
    args = ap.parse_args()
    start = dt.date.fromisoformat(args.date)
    week = []
    for k in range(args.hafta):
        day = (start + dt.timedelta(days=k)).isoformat()
        out, payload, events = analyze_day(dt.date.fromisoformat(day), verbose=args.hafta == 1)
        write_report(day, out, payload, events, args.min_ev)
        week.append((day, out))
    if args.hafta > 1:
        write_week(start, week, args.min_ev)


def write_week(start: dt.date, week: list[tuple[str, list[dict]]], min_ev: float) -> None:
    """One-page summary of a multi-day run: coverage per day and every plausible value selection of the week."""
    lines = [f"# Nesine haftalık analiz ({start} – {week[-1][0]})", "",
             "| Gün | Nesine maçı | Global fiyatlı | Doğrudan borsa seçimi | Araştırma (ESPN/PL) | Uyarılı |", "|---|---|---|---|---|---|"]
    value = []
    for day, out in week:
        priced = [m for m in out if m["status"] == "fiyatlandı"]
        direct = sum(1 for m in priced for s in m["selections"] if s.get("direct"))
        lines.append(f"| {day} | {len(out)} | {len(priced)} | {direct} | {sum(1 for m in out if m.get('research'))} | "
                     f"{sum(1 for m in out if (m.get('research') or {}).get('flags'))} |")
        value += [(m, s) for m in priced for s in m["selections"] if min_ev <= s["ev"] <= MAX_PLAUSIBLE_EV]
    value.sort(key=lambda x: x[1]["ev"], reverse=True)
    lines += ["", "## Haftanın değerli seçimleri (Nesine oranı > global adil oran)", "",
              "| Gün saat | Maç | Pazar | Seçim | Nesine | Global olasılık | EV | Fiyat | Referans |", "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {m['kickoff']} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
              f"%{s['fair_prob'] * 100:.1f} | {s['ev']:+.1%} | {'doğrudan' if s.get('direct') else 'model'} | "
              f"{m['reference'].split(' (')[0]} |" for m, s in value[:100]] or ["_Yok._"]
    path = ROOT / "reports" / "weekly" / f"{start}_nesine_hafta.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"-> {path.relative_to(ROOT)}")


def _side_rows(r: dict, side: str) -> dict[str, str]:
    t = (r.get("teams") or {}).get(side) or {}
    tab, sea, prof = t.get("table") or {}, t.get("season") or {}, t.get("profile") or {}
    row: dict[str, str] = {"Takım": t.get("name") or "-", "Son 5 maç": " · ".join(t.get("last5") or []) or "-",
                           "Form": t.get("form") or "-", "Dinlenme (gün)": str(t.get("rest_days", "-"))}
    if tab.get("rank"):
        row["Puan durumu"] = (f"{int(tab['rank'])}./{tab['size']} · {int(tab.get('points') or 0)} p · "
                              f"{int(tab.get('wins') or 0)}G {int(tab.get('draws') or 0)}B {int(tab.get('losses') or 0)}M")
    if sea.get("goals_for") and sea.get("played"):
        n = float(sea["played"]) or 1.0
        row["Sezon gol (at / ye)"] = (f"{sea['goals_for']} / {sea['goals_against']} "
                                     f"({float(sea['goals_for']) / n:.2f} / {float(sea['goals_against']) / n:.2f} maç başı)")
    if prof.get("top_scorers"):
        row["Golcüler"] = ", ".join(f"{p['name']} {p['goals']}G {p['assists']}A" for p in prof["top_scorers"])
    if prof.get("top_assists"):
        row["Asist yapanlar"] = ", ".join(f"{p['name']} {p['assists']}A {p['goals']}G" for p in prof["top_assists"])
    gk = prof.get("goalkeeper")
    if gk:
        sp = f"%{gk['save_pct'] * 100:.0f} kurtarış" if gk.get("save_pct") is not None else "kurtarış verisi yok"
        row["Kaleci"] = f"{gk['name']} ({gk['apps']} maç, {sp}, maç başı {gk['conceded_per_game']} gol)"
    if prof.get("cards"):
        row["Kart riski"] = ", ".join(f"{p['name']} {p['yellow']}S" + (f" {p['red']}K" if p["red"] else "")
                                      for p in prof["cards"])
    for label, value in (t.get("team_stats") or {}).items():
        row[label] = value
    row["Eksikler"] = _absent(r, side)
    if t.get("news_flags"):
        row["Haber (sakatlık/ceza)"] = " · ".join(t["news_flags"])
    if t.get("likely_absent"):
        row["Muhtemel eksikler (son kadrolardan)"] = "; ".join(f"{p['name']}: {p['reason']}" for p in t["likely_absent"][:6])
    if t.get("lineup_announced"):
        miss = [p["name"] for p in t.get("missing_regulars") or []]
        row["İlk 11"] = "açıklandı" + (f"; düzenli oyunculardan yok: {', '.join(miss)}" if miss else "")
    return row


def write_team_files(date: str, out: list[dict], d: Path) -> None:
    """Per-match dossier of both teams (ESPN + Premier League official availability)."""
    md = [f"# {date} — Takım dosyaları", "",
          "Kaynak: ESPN (form, son maçlar, puan durumu, sezon golleri, golcüler, kaleci, kartlar, ilk 11) ve Premier Lig "
          "resmî sakat/cezalı listesi. Olasılıklar bu bilgilerden değil global borsa fiyatından gelir; bu dosya bağlam ve "
          "kontrol içindir.", ""]
    for m in out:
        r = m.get("research")
        if not r or not r.get("teams"):
            continue
        h, a = _side_rows(r, "home"), _side_rows(r, "away")
        md += [f"## {m['kickoff'][11:]} · {m['home']} - {m['away']} ({m['league']})", "",
               f"Aralarında: {r.get('h2h') or '-'} · Uyarı: {'; '.join(r.get('flags') or []) or '-'}", "",
               "| | Ev | Deplasman |", "|---|---|---|"]
        for key in dict.fromkeys(list(h) + list(a)):
            md.append(f"| {key} | {h.get(key, '-')} | {a.get(key, '-')} |")
        md.append("")
    (d / "takim_dosyalari.md").write_text("\n".join(md) + "\n", encoding="utf-8")


HISTORY_FILE = "nesine_history.jsonl"
MIN_MOVE = 0.03  # exchange probability move (3 pts) that Nesine's unchanged price has not followed


def _history(d: Path) -> list[dict]:
    path = d / HISTORY_FILE
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def lagging_selections(history: list[dict], out: list[dict], hours: float = 8.0) -> list[tuple[dict, dict, float, str]]:
    """Directly quoted selections whose exchange probability rose >= MIN_MOVE since an earlier run while
    Nesine still pays the same odds: the bookmaker has not (yet) followed the market move."""
    now = dt.datetime.now(TSI)
    hits = []
    for m in out:
        if m.get("status") != "fiyatlandı":
            continue
        for s in m["selections"]:
            if not s.get("direct"):
                continue
            best = None
            for snap in history:
                ts = dt.datetime.fromisoformat(snap["ts"])
                if now - ts > dt.timedelta(hours=hours):
                    continue
                rec = (snap.get("m") or {}).get(str(m["code"]))
                if not rec or rec.get("ref_t") == m.get("ref_fetched_utc"):
                    continue  # same exchange snapshot: nothing moved
                then = (rec.get("s") or {}).get(s["name"])
                if not then or abs(then[0] - s["odds"]) > 1e-9:
                    continue  # Nesine changed its price meanwhile
                move = s["fair_prob"] - then[1]
                if move >= MIN_MOVE and (best is None or move > best[0]):
                    best = (move, then[1], snap["ts"])
            if best:
                hits.append((m, s, best[1], best[2]))
    hits.sort(key=lambda x: x[1]["fair_prob"] - x[2], reverse=True)
    return hits


def record_history(d: Path, out: list[dict]) -> None:
    """Append this run's directly quoted prices (Nesine odds + exchange probability) for move detection."""
    snap = {"ts": dt.datetime.now(TSI).isoformat(timespec="seconds"), "m": {}}
    for m in out:
        if m.get("status") != "fiyatlandı":
            continue
        sel = {s["name"]: [s["odds"], s["fair_prob"]] for s in m["selections"] if s.get("direct")}
        if sel:
            snap["m"][str(m["code"])] = {"ref_t": m.get("ref_fetched_utc"), "s": sel}
    with (d / HISTORY_FILE).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snap, ensure_ascii=False) + "\n")


def write_report(date: str, out: list[dict], payload: dict, events: list, min_ev: float) -> None:
    priced = sum(1 for m in out if m["status"] == "fiyatlandı")
    d = DAILY / date
    d.mkdir(parents=True, exist_ok=True)
    lagging = lagging_selections(_history(d), out)
    record_history(d, out)
    (d / "nesine_global.json").write_text(json.dumps({"date": date, "generated_at": dt.datetime.now(TSI).isoformat(timespec="seconds"),
                                                      "nesine_margins": market_overrounds(payload, {e.code for e in events}),
                                                      "matches": out}, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    _, generated = global_references(max_age_hours=1e9)
    age = ""
    if generated:
        mins = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(generated)).total_seconds() / 60
        age = (f"**Global veri {mins:.0f} dakika önce çekildi**" + (" — ESKİ, oranlar değişmiş olabilir." if mins > 240 else ".")
               + " (yurt dışı sunucu: günde 5 tam çekim + maç öncesi saatlik yenileme)")
    md = [f"# {date} — Nesine bülteni, global referans fiyatına göre", "", age, "",
          f"Referans önceliği: Pinnacle → Smarkets / Matchbook (ikisi varsa ortalaması) → Betfair → ESPN. {len(events)} maçın {priced}'i fiyatlandı; "
          "global fiyatı olmayan maçlar Nesine oranından türetilmez, fiyatlanmaz.", "",
          "> EV = global adil olasılık × Nesine oranı − 1. Türev pazarlar (İY/MS, KG, aralık, kombine…) referans 1X2 + Alt/Üst'ten "
          "kalibre edilmiş ortak gol dağılımıyla hesaplanır. DraftKings keskin bir büro değildir: küçük artı EV'ler gürültü olabilir.", ""]
    value = [(m, s) for m in out if m["status"] == "fiyatlandı" for s in m["selections"] if s["ev"] >= min_ev]
    value.sort(key=lambda x: x[1]["ev"], reverse=True)
    # In a liquid market an edge above +25% against a sharp price is almost always a data error
    # (thin reference, wrong match, model extrapolation) -> listed separately, never as a pick.
    plausible = [(m, s) for m, s in value if s["ev"] <= MAX_PLAUSIBLE_EV]
    suspicious = [(m, s) for m, s in value if s["ev"] > MAX_PLAUSIBLE_EV]

    def _rows(items: list) -> list[str]:
        rows = ["| Saat | Maç | Pazar | Seçim | Nesine | Adil oran | EV | MBS | Referans |", "|---|---|---|---|---|---|---|---|---|"]
        for m, s in items[:60]:
            rows.append(f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
                        f"{s['fair_odds']:.2f} | {s['ev']:+.1%} | {s['mbs']} | {m['reference'].split(' ')[0]} |")
        return rows

    md += ["## Borsa hareket etti, Nesine oranını güncellemedi", "",
           "Borsada olasılığı son 8 saatte en az 3 puan artan, Nesine'nin ise aynı oranı vermeye devam ettiği seçimler "
           "(haber / kadro sonrası geç kalan oran). Doğrudan borsa fiyatlı seçimler.", ""]
    if lagging:
        md += ["| Saat | Maç | Pazar | Seçim | Nesine (değişmedi) | Borsa olasılığı önce → şimdi | Şimdiki EV | İlk görülme |",
               "|---|---|---|---|---|---|---|---|"]
        md += [f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
               f"%{p0 * 100:.1f} → %{s['fair_prob'] * 100:.1f} | {s['ev']:+.1%} | {ts[11:16]} |" for m, s, p0, ts in lagging[:40]]
    else:
        md.append("_Şu an yok (ilk çalıştırmalarda geçmiş birikene kadar boş kalır)._")
    md += ["", "## Nesine'nin global adil fiyatın üstünde verdiği seçimler", ""]
    md += _rows(plausible) if plausible else ["_Bugün Nesine'nin global adil fiyatın üstünde verdiği seçim yok._"]
    if suspicious:
        md += ["", f"## Referans hatası şüphesi (EV > {MAX_PLAUSIBLE_EV:+.0%}) — bahis önerisi değildir", "",
               "Likit bir piyasada keskin fiyata karşı bu büyüklükte fark neredeyse her zaman veri hatasıdır "
               "(ince borsa fiyatı, yanlış eşleşen maç ya da uç favorilerde model dışı bölge).", ""]
        md += _rows(suspicious)
    md += ["", "## Fiyatlanan maçlar", "", "| Saat | Lig | Maç | Nesine 1/X/2 | Global adil 1/X/2 | Referans | En iyi EV |",
           "|---|---|---|---|---|---|---|"]
    for m in out:
        if m["status"] != "fiyatlandı":
            continue
        fair = "/".join(f"{1 / p:.2f}" for p in m["fair_1x2"])
        nes = "/".join(f"{o:.2f}" if o else "-" for o in m["nesine_ms"])
        best = m["selections"][0] if m["selections"] else None
        best_s = f"{best['market']}: {best['selection']} {best['ev']:+.1%}" if best else "-"
        md.append(f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | {nes} | {fair} | {m['reference'].split(' ')[0]} | {best_s} |")
    md += ["", "## Maç araştırması (ESPN: form, puan durumu, dinlenme, ilk 11)", "",
           "Olasılık global fiyattan gelir; bu bölüm bağlam ve güvenlik kontrolüdür. Önemli bir eksik, global fiyat "
           "çekildikten sonra açıklanan ilk 11'de görülürse maç kupona alınmaz.", "",
           "| Saat | Maç | Form (ev / dep) | Puan durumu (ev / dep) | Dinlenme (gün) | Aralarında | İlk 11 | Eksikler (ev / dep) | Uyarı |",
           "|---|---|---|---|---|---|---|---|---|"]
    for m in out:
        r = m.get("research")
        if not r:
            continue
        h, a = r["teams"].get("home", {}), r["teams"].get("away", {})
        mot = r.get("motivation", {})
        lineup = "açıklandı" if h.get("lineup_announced") or a.get("lineup_announced") else "henüz yok"
        md.append(f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {h.get('form', '-')} / {a.get('form', '-')} | "
                  f"{mot.get('home') or '-'} / {mot.get('away') or '-'} | {h.get('rest_days', '-')} / {a.get('rest_days', '-')} | "
                  f"{r.get('h2h') or '-'} | {lineup} | {_absent(r, 'home')} / {_absent(r, 'away')} | "
                  f"{'; '.join(r.get('flags') or []) or '-'} |")
    md += ["", "## Global fiyatı bulunamayan maçlar (fiyatlanmadı)", ""]
    md += [f"- {m['kickoff'][11:]} {m['league']}: {m['home']} - {m['away']}" for m in out if m["status"] != "fiyatlandı"]
    (d / "nesine_global.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    write_team_files(date, out, d)
    print(f"{priced}/{len(events)} maç fiyatlandı; {len(value)} seçim EV ≥ {min_ev:+.1%}. -> {d.relative_to(ROOT)}/nesine_global.md")


if __name__ == "__main__":
    main()
