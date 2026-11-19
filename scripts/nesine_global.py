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
import datetime as dt
import difflib
import json
from pathlib import Path
import re
import unicodedata

from quantfoot.data.live_espn import fetch_espn_slate
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
SOURCE_RANK = {"Pinnacle (football-data)": 0, "Betfair Borsası (football-data)": 1, "Smarkets (borsa)": 1, "ESPN (DraftKings/ESPN BET)": 2}
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
    rows = []
    for s in event.selections:
        direct = s.name in ("MS 1", "MS 0", "MS 2") or (ou_line is not None and s.name in (f"{ou_line:.1f} Üst", f"{ou_line:.1f} Alt"))
        if not direct and not derivatives_ok:
            continue  # derivative distribution not calibrated for this competition
        if s.name.startswith("İlk Gol"):
            p = timing.get(s.name)
        else:
            p = goal_probability(s.name, joint)
        if p is None:
            continue
        if s.negate:
            p = 1.0 - p
        rows.append({"market": s.market_title, "selection": s.label, "name": s.name if not s.negate else f"DEĞİL({s.name})",
                     "odds": s.odds, "fair_prob": round(p, 5), "fair_odds": round(1 / p, 3) if p > 1e-9 else None,
                     "ev": round(p * s.odds - 1.0, 4), "mbs": s.mbs, "direct": direct})
    rows.sort(key=lambda r: r["ev"], reverse=True)
    nesine_ms = [event.odds_of(f"MS {c}") for c in "102"]
    margin = sum(1 / o for o in nesine_ms) - 1 if all(nesine_ms) else None
    return {"mu_home": round(float(mu_h), 3), "mu_away": round(float(mu_a), 3), "reference": ref["source"],
            "ref_1x2": ref["x12"], "ref_ou": ref.get("ou"), "fair_1x2": [round(float(x), 4) for x in p1x2],
            "nesine_ms_margin": None if margin is None else round(margin, 4), "derivatives_priced": derivatives_ok, "selections": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--min-ev", type=float, default=0.0)
    args = ap.parse_args()
    day = dt.date.fromisoformat(args.date)
    nxt = day + dt.timedelta(days=1)

    payload = fetch_bulletin()
    leagues = league_names(payload)
    events = [e for e in parse_bulletin(payload)
              if e.kickoff.date() == day or (e.kickoff.date() == nxt and e.kickoff.hour < 7)]
    print(f"Nesine {args.date}: {len(events)} futbol maçı")

    sharp, generated = global_references()
    print(f"Global (Pinnacle/Smarkets): {len(sharp)} referans (oluşturulma {generated or 'yok'})")
    espn = espn_references([day.isoformat(), nxt.isoformat()])
    print(f"ESPN: {len(espn)} maçta oran bulundu")
    refs = sharp + espn

    out, priced = [], 0
    for e in sorted(events, key=lambda x: x.kickoff):
        league = leagues.get(e.league_code, str(e.league_code))
        ref, score = None, 0.0
        for rank in sorted(set(SOURCE_RANK.values())):  # best source first
            pool = [r for r in refs if SOURCE_RANK.get(r["source"], 9) == rank]
            ref, score = _match(e, pool) if pool else (None, 0.0)
            if ref is not None:
                break
        rec = {"code": e.code, "kickoff": e.kickoff.strftime("%Y-%m-%d %H:%M"), "league": league, "home": e.home, "away": e.away,
               "nesine_ms": [e.odds_of(f"MS {c}") for c in "102"], "n_nesine_selections": len(e.selections)}
        if ref is None:
            rec["status"] = "global referans bulunamadı — fiyatlanmadı"
        else:
            rec.update(match_score=round(score, 2), ref_match=f"{ref['home']} - {ref['away']}", **price_event(e, ref, league))
            rec["status"] = "fiyatlandı"
            priced += 1
        out.append(rec)

    d = DAILY / args.date
    d.mkdir(parents=True, exist_ok=True)
    (d / "nesine_global.json").write_text(json.dumps({"date": args.date, "generated_at": dt.datetime.now(TSI).isoformat(timespec="seconds"),
                                                      "nesine_margins": market_overrounds(payload, {e.code for e in events}),
                                                      "matches": out}, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    md = [f"# {args.date} — Nesine bülteni, global referans fiyatına göre", "",
          f"Referans önceliği: Pinnacle → Smarkets borsası → ESPN. {len(events)} maçın {priced}'i fiyatlandı; "
          "global fiyatı olmayan maçlar Nesine oranından türetilmez, fiyatlanmaz.", "",
          "> EV = global adil olasılık × Nesine oranı − 1. Türev pazarlar (İY/MS, KG, aralık, kombine…) referans 1X2 + Alt/Üst'ten "
          "kalibre edilmiş ortak gol dağılımıyla hesaplanır. DraftKings keskin bir büro değildir: küçük artı EV'ler gürültü olabilir.", ""]
    value = [(m, s) for m in out if m["status"] == "fiyatlandı" for s in m["selections"] if s["ev"] >= args.min_ev]
    value.sort(key=lambda x: x[1]["ev"], reverse=True)
    md += ["## Nesine'nin global adil fiyatın üstünde verdiği seçimler", ""]
    if value:
        md += ["| Saat | Maç | Pazar | Seçim | Nesine | Adil oran | EV | MBS | Referans |", "|---|---|---|---|---|---|---|---|---|"]
        for m, s in value[:60]:
            md.append(f"| {m['kickoff'][11:]} | {m['home']} - {m['away']} | {s['market']} | {s['selection']} | {s['odds']:.2f} | "
                      f"{s['fair_odds']:.2f} | {s['ev']:+.1%} | {s['mbs']} | {m['reference'].split(' ')[0]} |")
    else:
        md.append("_Bugün Nesine'nin global adil fiyatın üstünde verdiği seçim yok._")
    md += ["", "## Fiyatlanan maçlar", "", "| Saat | Lig | Maç | Nesine 1/X/2 | Global adil 1/X/2 | Nesine MS marjı | Referans | En iyi EV |",
           "|---|---|---|---|---|---|---|---|"]
    for m in out:
        if m["status"] != "fiyatlandı":
            continue
        fair = "/".join(f"{1 / p:.2f}" for p in m["fair_1x2"])
        nes = "/".join(f"{o:.2f}" if o else "-" for o in m["nesine_ms"])
        best = m["selections"][0] if m["selections"] else None
        best_s = f"{best['market']}: {best['selection']} {best['ev']:+.1%}" if best else "-"
        marg = f"%{m['nesine_ms_margin'] * 100:.1f}" if m["nesine_ms_margin"] is not None else "-"
        md.append(f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | {nes} | {fair} | {marg} | {m['reference'].split(' ')[0]} | {best_s} |")
    margins = market_overrounds(payload, {e.code for e in events})
    top = sorted(((k, v) for k, v in margins.items() if v["n"] >= 5), key=lambda kv: kv[1]["margin"])
    md += ["", "## Nesine marjları (bugünkü maçlar, tam seçenek setleri)", "",
           "Marj = oranların tersleri toplamı − 1. Pinnacle'da maç sonucu marjı tipik olarak %2–3'tür; "
           "marj ne kadar yüksekse uzun vadeli beklenen kayıp o kadar büyüktür.", "",
           "| Pazar | Maç | Ortalama marj |", "|---|---|---|"]
    md += [f"| {k} | {v['n']} | %{v['margin'] * 100:.1f} |" for k, v in top]
    md += ["", "## Global fiyatı bulunamayan maçlar (fiyatlanmadı)", ""]
    md += [f"- {m['kickoff'][11:]} {m['league']}: {m['home']} - {m['away']}" for m in out if m["status"] != "fiyatlandı"]
    (d / "nesine_global.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"{priced}/{len(events)} maç fiyatlandı; {len(value)} seçim EV ≥ {args.min_ev:+.1%}. -> {d.relative_to(ROOT)}/nesine_global.md")


if __name__ == "__main__":
    main()
