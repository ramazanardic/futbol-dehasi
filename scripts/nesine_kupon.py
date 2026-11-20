"""Nesine kuponu: olasılıklar global keskin fiyattan, toplam oran Nesine oranlarından.

    python scripts/nesine_kupon.py --hedef 10              # en çok 7 maç, her bacak ≥ %55 ve ≥ 1.20
    python scripts/nesine_kupon.py --hedef 5 --adet 3 --max-mac 6 --min-oran 1.20

Kural:
  * Her seçimin tutma olasılığı global referanstan gelir (Pinnacle → Smarkets → Betfair borsası;
    ESPN yalnızca --espn ile). Bkz. scripts/nesine_global.py.
  * Kupon oranı NESİNE oranlarının çarpımıdır: "10 oranlık kupon" Nesine'de oynanınca 10'u geçer.
  * Hedef orana ulaşan kuponlar arasında global birleşik tutma olasılığı en yüksek olan seçilir.
    log P(kupon) = Σ log(1 + EV_i) − log(Nesine oranı) olduğundan bu, Nesine'nin en az kestiği
    (global fiyata en yakın ya da üstünde ödediği) bacakları seçmek demektir.
  * Maç başına tek seçim; Nesine MBS kuralı (kupondaki maç sayısı ≥ bacakların en büyük MBS'i).
  * Arama dinamik programlamayla kesindir (açgözlü değil): maç başına baskın olmayan adaylar, Nesine
    oranının logaritması 0.005'lik dilimlerle.

Not: Aynı hedef oran için daha az maç genellikle daha yüksek tutma olasılığı verir, çünkü her ek maç
Nesine marjını yeniden ekler. Kombine isteniyorsa --min-mac ve --min-olasilik ile sınırlanır
(ör. --min-mac 4 --min-olasilik 0.55: en az 4 maç, her bacak en az %55).

Uyarı: Nesine marjı pazarların çoğunda ~%20'dir; kupon EV'si bu yüzden genellikle negatiftir.
Bu araç kayıp beklentisini en aza indirir, kazanç garanti etmez.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from functools import lru_cache
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import DAILY, MAX_PLAUSIBLE_EV, PRICED, TSI, analyze_day, selection_key  # noqa: E402

from quantfoot.data.nesine import fetch_bulletin, parse_bulletin  # noqa: E402
from quantfoot.evaluation.auto_learn import calibration_sigma_adjustment, load_live_calibration  # noqa: E402
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402
from quantfoot.strategy.coupon_builder import (  # noqa: E402
    _conflicting_selections,
    is_cup_competition,
    is_main_market_selection,
    is_uncalibrated_competition,
)

SHARP_SOURCES = ("Pinnacle", "Smarkets", "Matchbook", "Betfair", "OddsMath (BetInAsia", "OddsMath (Borsa")
MID_GLOBAL_PREFIXES = ("OddsMath (", "OddsPapi (", "API-Football (")
MID_GLOBAL_MIN_PROB = 0.62  # researched mid-tier global books (e.g. Marathonbet/1XBET) must clear >= 62%


def _has_full_research(m: dict) -> bool:
    """True when both teams have live ESPN or Transfermarkt data (or user-supplied absence coverage)."""
    r = m.get("research") or {}
    teams = r.get("teams") or {}
    tm = r.get("tm_absences") or {}
    return bool((teams.get("home") and teams.get("away")) or (tm.get("home") and tm.get("away")) or r.get("user_absences"))
RES = 0.002  # log-odds bucket width
MIN_LEG_ODDS = 1.20  # user rule: never a selection below 1.20
MAX_LEGS = 7  # user rule (19 Nov): at most 7 matches per coupon, whatever the target
MAX_PRICE_AGE_H = 3.0  # global price older than this may predate team news / line-ups: not used in coupons


def price_age_hours(m: dict, now: dt.datetime) -> float | None:
    t = m.get("ref_fetched_utc")
    return None if not t else (now - dt.datetime.fromisoformat(t)).total_seconds() / 3600


def match_context(m: dict) -> str:
    """Short research summary of a match for the coupon's reasoning column."""
    r = m.get("research") or {}
    parts = []
    teams = r.get("teams") or {}
    for side, label in (("home", "Ev"), ("away", "Dep")):
        t = teams.get(side) or {}
        bits = []
        if t.get("form"):
            bits.append(f"form {t['form']}")
        tab = t.get("table") or {}
        if tab.get("rank"):
            bits.append(f"{int(tab['rank'])}./{tab['size']}")
        ua = (r.get("user_absences") or {}).get(side) or {}
        n_inj, n_card = len(ua.get("injuries") or []), len(ua.get("cards") or [])
        if n_inj or n_card:
            bits.append(f"{n_inj} sakat, {n_card} cezalı" + (" (kaleci yok)" if ua.get("gk_out") else ""))
        tm = (r.get("tm_absences") or {}).get(side) or {}
        if tm:
            crit_n = len(tm.get("critical_absences") or [])
            if tm.get("gk1_out"):
                bits.append("TM: 1. kaleci eksik")
            elif tm.get("top_scorer_out"):
                bits.append("TM: golcü eksik")
            elif crit_n:
                bits.append(f"TM: {crit_n} kilit eksik")
        la = [x for x in t.get("likely_absent") or [] if "rotasyon" not in x["reason"]]
        if la:
            bits.append(f"son kadroda yok: {', '.join(x['name'] for x in la[:2])}")
        if bits:
            parts.append(f"{label}: {', '.join(bits)}")
    if r.get("flags"):
        parts.append("⚠ " + "; ".join(r["flags"]))
    return " · ".join(parts)


def leg_reason(leg: dict) -> str:
    src = "kendi borsa fiyatı" if leg.get("direct") else "global 1X2+Alt/Üst'ten gol modeli"
    text = f"Global olasılık %{leg['p'] * 100:.0f} ({src}, {leg['reference']}); adil oran {1 / leg['p']:.2f}, Nesine {leg['odds']:.2f}"
    if leg.get("scores"):
        text += " · bu bacakla uyumlu en olası skorlar: " + ", ".join(f"{sc} %{p * 100:.1f}" for sc, p in leg["scores"])
    return text + (f" · {leg['context']}" if leg.get("context") else "")


def consistent_scores(joint, name: str, top: int = 3) -> list[tuple[str, float]]:
    """Most likely full-time scores on which the leg WINS (probability of score and leg together), so a score
    shown next to a coupon leg can never contradict it. joint[h1, a1, h2, a2] = first / second half goals."""
    import numpy as np
    j = np.asarray(joint)
    g = j.shape[0]
    neg = name.startswith("DEĞİL(")
    base = name[6:-1] if neg else name
    win: dict[tuple[int, int], float] = {}
    for h1, a1, h2, a2 in product(range(g), repeat=4):
        p = float(j[h1, a1, h2, a2])
        if p <= 0:
            continue
        ft = (h1 + h2, a1 + a2)
        try:
            w = settle_selection(base, (h1, a1), ft)
        except (KeyError, ValueError):
            return []
        if w is None:
            return []
        if w != neg:
            win[ft] = win.get(ft, 0.0) + p
    total = float(j.sum()) or 1.0
    best = sorted(win.items(), key=lambda kv: -kv[1])[:top]
    return [(f"{h}-{a}", p / total) for (h, a), p in best]


HALF_TOKENS = ("İY", "2Y", "İki Yarıda", "En Çok Gol", "Yarıyı", "Yarıda")
Z_LOW = 1.28  # one-sided 90 % lower bound


def leg_sigma(
    name: str,
    direct: bool,
    reference: str,
    researched: bool,
    flagged: bool,
    calibration: dict | None = None,
) -> float:
    """Uncertainty (probability points) of a leg's probability, from what the calibration work measured:
    a direct exchange quote is within ~1 pt, a goal-model derivative ~2-3 pts, half-time / second-half
    model markets less certain still; a single exchange, non-sharp global book, missing research or a
    team-news flag widen it. Optional ``calibration`` applies Empirical-Bayes deltas learned from settled days."""
    if direct:
        sigma = 0.010
    elif any(t in name for t in HALF_TOKENS):
        sigma = 0.035
    else:
        sigma = 0.025
    if "+" not in reference:  # one exchange instead of two agreeing ones
        sigma += 0.005
    if not reference.startswith(SHARP_SOURCES):  # mid-tier global book (e.g. Marathonbet/1XBET) carries extra margin noise
        sigma += 0.020
    if not researched:
        sigma += 0.010
    if flagged:
        sigma += 0.020
    if calibration:
        sigma = max(0.008, sigma + calibration_sigma_adjustment(reference, name, calibration))
    return sigma


def candidates(
    matches: list[dict],
    now: dt.datetime,
    min_odds: float,
    min_prob: float,
    allow_espn: bool,
    direct_only: bool = False,
    *,
    exclude_cups: bool = False,
    main_markets_only: bool = False,
    allow_mid_researched: bool = True,
    calibration: dict | None = None,
) -> list[list[dict]]:
    """Per match: non-dominated legs (higher Nesine odds AND higher global probability dominates)."""
    pools = []
    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        is_sharp = m["reference"].startswith(SHARP_SOURCES)
        res = m.get("research") or {}
        flagged = bool(res.get("flags"))
        full_research = _has_full_research(m)
        is_mid_global = (not is_sharp) and m["reference"].startswith(MID_GLOBAL_PREFIXES)
        if not is_sharp:
            if is_mid_global and allow_mid_researched:
                # Researched mid-tier global book: allowed ONLY when both teams have live research,
                # zero risk/steam flags, and competition is inside calibration domain.
                if not full_research or flagged or is_uncalibrated_competition(m.get("league")):
                    continue
            elif not allow_espn:
                continue
        if exclude_cups and is_cup_competition(m.get("league")):
            continue  # cup/playoff knockout rotation & 90' draw guard (--kupasiz)
        if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now + dt.timedelta(minutes=5):
            continue  # started or about to start
        if m.get("research_block"):
            continue  # important absence announced after the global price was fetched
        age = price_age_hours(m, now)
        if age is not None and age > MAX_PRICE_AGE_H:
            continue  # stale global price (GitHub's scheduler skipped runs)
        legs = []
        context = match_context(m)
        researched = bool(res.get("teams") or res.get("user_absences") or res.get("tm_absences"))
        eff_min_prob = max(min_prob, MID_GLOBAL_MIN_PROB) if (not is_sharp and is_mid_global) else min_prob
        for s in m["selections"]:
            if s["odds"] < min_odds or s["fair_prob"] < eff_min_prob or s["ev"] > MAX_PLAUSIBLE_EV:
                continue
            if direct_only and not s.get("direct"):
                continue  # model-derived price: no direct global quote for this selection
            if main_markets_only and not is_main_market_selection(s.get("name", "")):
                continue  # core main markets only (--ana-pazar)
            if not s.get("direct") and s.get("name", "").startswith(("İY/MS", "2Y 0", "2Y 1", "2Y 2")):
                # model HT/FT is the weakest derived market (calibration: ~3x the error); model second-half result
                # legs went 1/5 in the 19 Nov coupons (favourites: 46 % hit vs 62 % predicted): direct quotes only
                continue
            ref_lbl = m["reference"].split(" (")[0] if is_sharp else f"{m['reference']} [orta]"
            legs.append({"code": m["code"], "kickoff": m["kickoff"], "league": m["league"], "match": f"{m['home']} - {m['away']}",
                         "market": s["market"], "selection": s["selection"], "odds": s["odds"], "p": s["fair_prob"],
                         "ev": s["ev"], "mbs": int(s["mbs"] or 1), "reference": ref_lbl,
                         "direct": bool(s.get("direct")), "context": context, "key": s.get("key"),
                         "name": s.get("name", ""), "researched": researched, "tier": "keskin" if is_sharp else "orta"})
            sig = leg_sigma(s.get("name", ""), bool(s.get("direct")), m["reference"], researched, flagged, calibration=calibration)
            legs[-1]["sigma"] = sig
            legs[-1]["p_low"] = max(0.001, s["fair_prob"] - Z_LOW * sig)
        legs.sort(key=lambda x: (-x["odds"], -x["p_low"]))
        front, best_p = [], -1.0
        for leg in legs:  # descending odds: keep a leg only if no higher-odds leg is more reliably probable
            if leg["p_low"] > best_p + 1e-12:
                front.append(leg)
                best_p = leg["p_low"]
        if front:
            pools.append(front)
    return pools


def best_coupon(pools: list[list[dict]], target: float, max_legs: int, min_legs: int = 1) -> dict | None:
    """Maximise Σ log p subject to Π Nesine odds ≥ target, ≤ max_legs, one leg per match, MBS rule."""
    log_t = math.log(target)
    tb = math.ceil(log_t / RES)

    def _bucket(lo: float) -> int:
        # Reaching the target collapses to one bucket; below it, never round up into the target bucket.
        return tb if lo >= log_t - 1e-12 else min(int(lo / RES), tb - 1)

    # state key: (n_legs, max_mbs, bucket) -> (sum_logp, exact_sum_log_odds, legs)
    states: dict[tuple[int, int, int], tuple[float, float, tuple]] = {(0, 1, 0): (0.0, 0.0, ())}
    for pool in pools:
        new = dict(states)
        for (n, mbs, _), (lp, lo, legs) in states.items():
            if n >= max_legs:
                continue
            for leg in pool:
                nlo = lo + math.log(leg["odds"])
                key = (n + 1, max(mbs, leg["mbs"]), _bucket(nlo))
                val = lp + math.log(leg.get("p_low", leg["p"]))
                old = new.get(key)
                # Keep the more probable state; on (near) ties keep the one with the higher odds.
                if old is None or val > old[0] + 1e-12 or (abs(val - old[0]) <= 1e-12 and nlo > old[1]):
                    new[key] = (val, nlo, legs + (leg,))
        states = new
    finals = [(lp, legs) for (n, mbs, b), (lp, lo, legs) in states.items() if b == tb and n >= max(mbs, min_legs, 1)]
    if not finals:
        return None
    _, legs = max(finals, key=lambda x: (x[0], -len(x[1])))
    return _summary(list(legs))


def _summary(legs: list[dict]) -> dict:
    odds = math.prod(x["odds"] for x in legs)
    p = math.prod(x["p"] for x in legs)
    p_low = math.prod(x.get("p_low", x["p"]) for x in legs)
    return {"legs": list(sorted(legs, key=lambda x: x["kickoff"])), "nesine_odds": round(odds, 2), "probability": p,
            "probability_low": p_low, "global_fair_odds": round(1 / p, 2), "ev": p * odds - 1.0,
            "min_mbs": max(x["mbs"] for x in legs)}


@lru_cache(maxsize=20000)
def compatible(a: str, b: str) -> bool:
    """True when some half-time / full-time score settles both selections as winners (else the two bets
    can never win together, e.g. 'ÇŞ 12' and 'İY Skor 0-0 & Skor 0-0'). Unknown syntax: assume compatible."""
    def win(name: str, h1: int, a1: int, h2: int, a2: int) -> bool | None:
        neg = name.startswith("DEĞİL(")
        base = name[6:-1] if neg else name
        try:
            v = settle_selection(base, (h1, a1), (h1 + h2, a1 + a2))
        except (KeyError, ValueError):
            return None
        return None if v is None else (not v if neg else v)
    for h1, a1, h2, a2 in product(range(5), repeat=4):
        wa, wb = win(a, h1, a1, h2, a2), win(b, h1, a1, h2, a2)
        if wa is None or wb is None:
            return True
        if wa and wb:
            return True
    return False


def drop_conflicts(pools: list[list[dict]], chosen: list[dict]) -> list[list[dict]]:
    """Remove legs that repeat a chosen bet, contradict its direction, or can never win together on the same match."""
    by_code: dict = {}
    for leg in chosen:
        by_code.setdefault(leg["code"], []).append(leg)
    out = []
    for pool in pools:
        taken = by_code.get(pool[0]["code"], [])
        keep = [
            x for x in pool
            if all(
                x.get("key") != t.get("key")
                and x.get("name", "") not in _conflicting_selections(t.get("name", ""))
                and t.get("name", "") not in _conflicting_selections(x.get("name", ""))
                and compatible(x.get("name", ""), t.get("name", ""))
                for t in taken
            )
        ]
        if keep:
            out.append(keep)
    return out


def _trust(leg: dict) -> float:
    # Reliability-adjusted probability: the lower bound already penalises model prices, missing research
    # and team-news flags.
    return leg.get("p_low", leg["p"])


def safest_first_coupon(pools: list[list[dict]], target: float, max_legs: int, partial: bool = False) -> dict | None:
    """User's method: take each match's most probable selection (any market family), sort the matches from the
    surest downwards and add them one by one until the product of Nesine odds reaches the target (MBS kept).
    With partial=True an unreachable target returns every safe leg instead of None (flagged reached=False)."""
    best = [max(pool, key=lambda x: (_trust(x), x["odds"])) for pool in pools]
    best.sort(key=lambda x: (-_trust(x), -x["odds"]))
    legs: list[dict] = []
    for leg in best:
        if len(legs) >= max_legs:
            break
        legs.append(leg)
        if math.prod(x["odds"] for x in legs) >= target and len(legs) >= max(x["mbs"] for x in legs):
            return {**_summary(legs), "reached": True}
    if partial and legs and len(legs) >= max(x["mbs"] for x in legs):
        return {**_summary(legs), "reached": False}
    return None


def prior_coupon_codes(date: str, target: float) -> set:
    """Match codes in the main coupon (Kupon 1) of today's latest coupon for each OTHER target: a 10x built after a 5x should not
    stack the same matches, because one losing shared leg would sink both coupons."""
    latest: dict[str, Path] = {}
    for f in sorted((DAILY / date).glob("kupon_*x_*.json")):
        tgt = f.name.split("_")[1]
        latest[tgt] = f  # sorted by HHMM: last one wins
    codes = set()
    for tgt, f in latest.items():
        try:
            if abs(float(tgt.rstrip("x")) - target) < 1e-9:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        codes |= {leg["code"] for c in data.get("coupons", [])[:1] for leg in c.get("legs", [])}  # main coupon
    return codes


def prior_coupon_legs(date: str, target: float) -> list[dict]:
    """Every leg of today's latest coupon file for each OTHER target (all its coupons): those exact selections are
    not repeated in new coupons (user rule, 20 Nov), but the same match with another compatible selection is."""
    latest: dict[str, Path] = {}
    for f in sorted((DAILY / date).glob("kupon_*x_*.json")):
        latest[f.name.split("_")[1]] = f
    legs = []
    for tgt, f in latest.items():
        try:
            if abs(float(tgt.rstrip("x")) - target) < 1e-9:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        legs += [leg for c in data.get("coupons", []) for leg in c.get("legs", [])]
    return legs


RECHECK_READS = 2
RECHECK_GAP_S = 4.0


def read_bulletin_odds(reads: int = RECHECK_READS, gap_s: float = RECHECK_GAP_S
                       ) -> tuple[dict[int, dict[str, float]], dict[tuple[int, str], tuple[float, float]]]:
    """Read the Nesine bulletin several times and keep the LOWEST odds per selection: on 20 Nov the feed served
    1.65 and 1.71 for the same selection within minutes, so one read can overstate a coupon's total odds.
    Returns (odds by code and key, {(code, key): (low, high)} for selections whose reads disagreed)."""
    import time
    low: dict[int, dict[str, float]] = {}
    high: dict[tuple[int, str], float] = {}
    for r in range(reads):
        if r:
            time.sleep(gap_s)
        for e in parse_bulletin(fetch_bulletin()):
            book = low.setdefault(int(e.code), {})
            for s in e.selections:
                k = selection_key(s)
                if k in book or r == 0:
                    book[k] = min(book.get(k, s.odds), s.odds)
                high[(int(e.code), k)] = max(high.get((int(e.code), k), s.odds), s.odds)
    flicker = {ck: (low[ck[0]][ck[1]], hi) for ck, hi in high.items()
               if ck[1] in low.get(ck[0], {}) and hi - low[ck[0]][ck[1]] > 1e-9}
    return low, flicker


def apply_live_odds(matches: list[dict], live: dict[int, dict[str, float]]) -> None:
    """Lower each selection's odds to the live (lowest-read) bulletin odds and drop selections that are no longer
    offered, so the optimiser never reaches the target on a price Nesine is not paying now."""
    for m in matches:
        book = live.get(int(m["code"]))
        if book is None:
            continue
        kept = []
        for s in m.get("selections", []):
            o = book.get(s.get("key")) if s.get("key") else s["odds"]
            if o is None:
                continue  # suspended / withdrawn since the analysis
            if o < s["odds"]:
                s["odds"], s["ev"] = o, s["fair_prob"] * o - 1
            kept.append(s)
        m["selections"] = kept


def recheck_odds(coupons: list[dict], current: dict | None = None, flicker: dict | None = None) -> list[str]:
    """Fetch the Nesine bulletin again and compare every leg's odds; update legs and coupon totals in place.
    Returns human-readable change notes (empty = all odds unchanged)."""
    if current is None:
        current, flicker = read_bulletin_odds()
    flicker = flicker or {}
    notes = []
    for i, c in enumerate(coupons, 1):
        for leg in c["legs"]:
            now_odds = current.get(int(leg["code"]), {}).get(leg.get("key"))
            pair = flicker.get((int(leg["code"]), leg.get("key")))
            if pair:
                leg["flicker"] = list(pair)
                notes.append(f"Kupon {i}: {leg['match']} {leg['selection']} — Nesine iki okumada farklı oran verdi "
                             f"({pair[0]:.2f} / {pair[1]:.2f}): düşük olan esas alındı")
            if now_odds is None:
                leg["status"] = "bültende yok / askıda"
                notes.append(f"Kupon {i}: {leg['match']} {leg['selection']} — Nesine'de şu an yok ya da askıda")
            elif abs(now_odds - leg["odds"]) > 1e-9:
                low = now_odds < MIN_LEG_ODDS
                notes.append(f"Kupon {i}: {leg['match']} {leg['selection']} — oran {leg['odds']:.2f} → {now_odds:.2f}"
                             + (" (1,20 altına düştü: oynamayın / değiştirin)" if low else ""))
                leg["odds"], leg["status"] = now_odds, ("oran 1,20 altına düştü" if low else "oran değişti")
            else:
                leg["status"] = "kontrol edildi"
        live = [x for x in c["legs"] if x["status"] != "bültende yok / askıda"]
        c["nesine_odds"] = round(math.prod(x["odds"] for x in live), 2) if live else 0.0
        c["odds_checked_at"] = dt.datetime.now(TSI).strftime("%H:%M:%S")
    return notes


def refresh_global_data() -> str:
    """Pull the newest sharp prices fetched abroad (GitHub Actions) before building a coupon."""
    import subprocess
    r = subprocess.run(["git", "pull", "--rebase", "--autostash", "-q", "origin", "main"], cwd=DAILY.parents[1],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return "güncel" if r.returncode == 0 else f"çekilemedi ({r.stderr.strip()[:80]})"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hedef", type=float, required=True, help="Hedef toplam Nesine oranı (ör. 10)")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--adet", type=int, default=3, help="Kaç alternatif kupon (maçlar birbirinden ayrı)")
    ap.add_argument("--yontem", choices=("optimum", "guvenli"), default="optimum",
                    help="optimum: hedefe ulaşan kuponlar arasında kuponun tamamının tutma olasılığı en yüksek olan "
                         "(varsayılan, kullanıcı kararı 19 Kasım); guvenli: en olası maçtan başlayıp hedefe kadar ekle")
    ap.add_argument("--max-mac", type=int, default=None, help="En çok maç (varsayılan 7, kullanıcı kuralı)")
    ap.add_argument("--min-mac", type=int, default=1, help="Kupondaki en az maç sayısı (kombine için ör. 3)")
    ap.add_argument("--min-oran", type=float, default=1.20, help="Bacak başına en düşük Nesine oranı (kullanıcı kuralı: 1,20)")
    ap.add_argument("--min-olasilik", type=float, default=None,
                    help="Bacak başına en düşük global olasılık (optimum: 0.55, guvenli: 0.60)")
    ap.add_argument("--espn", action="store_true", help="Keskin olmayan global büro/ESPN referanslı maçları da kullan")
    ap.add_argument("--ayri-mac", action="store_true",
                    help="Eski kural: her maç yalnız bir kuponda. Varsayılan (kullanıcı kuralı 20 Kasım): bir maç birden "
                         "çok kuponda olabilir ama AYNI tercihle asla; birbirini kesin yatıran tercihler de yasak")
    ap.add_argument("--dogrudan", action="store_true", help="Yalnızca doğrudan global fiyatı olan seçimler (model türevi yok)")
    ap.add_argument("--kupasiz", action="store_true", help="Kupa, eleme ve playoff maçlarını kupon havuzundan çıkar")
    ap.add_argument("--ana-pazar", action="store_true", help="Yalnızca ana pazarlar (MS, ÇŞ, 1.5/2.5/3.5 Alt/Üst, KG)")
    ap.add_argument("--oddsmath", action="store_true", help="OddsMath referanslarını açıkça etkinleştir (varsayılan açık)")
    ap.add_argument("--no-oddsmath", action="store_true", help="OddsMath canlı referans çekimini kapat")
    ap.add_argument("--tm", action="store_true", help="Transfermarkt 2026/27 verisini açıkça etkinleştir (varsayılan açık)")
    ap.add_argument("--no-tm", action="store_true", help="Transfermarkt canlı sakat/cezalı çekimini kapat")
    ap.add_argument("--yalniz-keskin", action="store_true",
                    help="Araştırmalı orta güven global büroları (Marathonbet/1XBET) kupon havuzundan çıkar")
    ap.add_argument("--max-ortak", type=int, default=-1,
                    help="İsteğe bağlı: bugünkü farklı hedefli ana kuponla paylaşılabilecek en çok maç (-1 = sınır yok, "
                         "varsayılan; aynı tercih zaten hiçbir kuponda tekrar edilmez)")
    ap.add_argument("--no-pull", action="store_true", help="Kupon öncesi git pull adımını atla (CI / bulut ortamı)")
    args = ap.parse_args()

    if not args.no_pull:
        print(f"Global veri: {refresh_global_data()}")
    matches, _, _ = analyze_day(
        dt.date.fromisoformat(args.tarih),
        verbose=False,
        use_oddsmath=not args.no_oddsmath,
        use_tm=not args.no_tm,
    )
    now = dt.datetime.now(TSI)
    min_prob = args.min_olasilik if args.min_olasilik is not None else (0.60 if args.yontem == "guvenli" else 0.55)
    live_cal = load_live_calibration()
    # Build on the LOWER of two bulletin reads (the feed can serve two prices for one selection), re-read after
    # building, and rebuild once if a coupon fell under the target on the re-read odds.
    live, _ = read_bulletin_odds()
    apply_live_odds(matches, live)
    rebuilt = False
    for attempt in range(2):
        pools = candidates(
            matches,
            now,
            args.min_oran,
            min_prob,
            args.espn,
            args.dogrudan,
            exclude_cups=args.kupasiz,
            main_markets_only=args.ana_pazar,
            allow_mid_researched=not args.yalniz_keskin,
            calibration=live_cal or None,
        )
        n_mid_pools = sum(1 for p in pools if p[0].get("tier") == "orta")
        if attempt == 0:
            print(f"{sum(1 for m in matches if m.get('status') == 'fiyatlandı')} maç global fiyatlı; {len(pools)} maç kupona uygun "
                  f"({len(pools) - n_mid_pools} keskin + {n_mid_pools} araştırmalı orta güven).")
        stale = sum(1 for m in matches if m.get("status") == "fiyatlandı" and (price_age_hours(m, now) or 0) > MAX_PRICE_AGE_H)
        if stale and attempt == 0:
            print(f"⚠ {stale} maçın global fiyatı {MAX_PRICE_AGE_H:g} saatten eski: kupona alınmadı (GitHub verisi yenilenmeli).")

        max_legs = args.max_mac or MAX_LEGS
        prior = prior_coupon_codes(args.tarih, args.hedef) if args.max_ortak >= 0 else set()
        if prior and attempt == 0:
            print(f"Bugünkü diğer kuponlarda {len(prior)} maç var: her kupon bunlardan en çok {args.max_ortak} tanesini paylaşır.")
        earlier = [] if args.ayri_mac else prior_coupon_legs(args.tarih, args.hedef)
        if earlier and attempt == 0:
            print(f"Bugünkü diğer kuponlardaki {len(earlier)} tercih tekrar kullanılmaz (aynı maçta başka tercih serbest).")
        coupons, used = [], set()
        for _ in range(args.adet):
            chosen = earlier + [leg for c in coupons for leg in c["legs"]]
            free = [p for p in pools if p[0]["code"] not in used] if args.ayri_mac else drop_conflicts(pools, chosen)

            def build(pl):
                return (safest_first_coupon(pl, args.hedef, max_legs, partial=not coupons) if args.yontem == "guvenli"
                        else best_coupon(pl, args.hedef, max_legs, args.min_mac))

            c = build(free)
            shared = [leg for leg in (c or {}).get("legs", []) if leg["code"] in prior]
            if c is not None and len(shared) > args.max_ortak:
                # keep the most reliable shared legs' matches, drop the other earlier-coupon matches and rebuild
                keep = {leg["code"] for leg in sorted(shared, key=lambda x: -x["p_low"])[:args.max_ortak]}
                c = build([p for p in free if p[0]["code"] not in prior or p[0]["code"] in keep])
            if c is None:
                break
            coupons.append(c)
            used |= {leg["code"] for leg in c["legs"]}

        live, flicker = read_bulletin_odds() if coupons else ({}, {})
        change_notes = recheck_odds(coupons, live, flicker) if coupons else []
        if attempt == 0 and any(c["nesine_odds"] < args.hedef - 1e-9 for c in coupons):
            apply_live_odds(matches, live)
            rebuilt = True
            continue
        break
    if rebuilt:
        change_notes.insert(0, "Son okumada bir kupon hedefin altına düştü: kupon güncel oranlarla yeniden kuruldu")
    for c in coupons:  # scores consistent with each leg (same goal distribution as the leg's probability)
        for leg in c["legs"]:
            priced = PRICED.get(int(leg["code"]))
            leg["scores"] = consistent_scores(priced["joint"], leg.get("name", "")) if priced else []
    stamp = now.strftime("%H%M")
    md = [f"# {args.tarih} — Nesine {args.hedef:g} oranlık kupon ({now:%H:%M} TSİ)", "",
          "Olasılıklar global keskin fiyattan (Pinnacle / Smarkets / Matchbook / Betfair borsası), oranlar Nesine'den. "
          + ("Yöntem: her maçın en olası seçimi alınır, maçlar **%100'e en yakından** başlayarak sıralanır ve Nesine "
             "oranı hedefe ulaşana kadar eklenir." if args.yontem == "guvenli" else
             "Yöntem: hedef Nesine oranına ulaşan kuponlar arasında **birleşik tutma olasılığı en yüksek** olan.")
          + " Oranlar maç saatine kadar değişebilir; oynamadan önce Nesine'de kontrol edin.", ""]
    if not coupons:
        md.append("_Bu hedefe uygun kupon kurulamadı (yeterli keskin referanslı, başlamamış maç yok)._")
    if stale:
        md += [f"> ⚠ {stale} maçın global fiyatı {MAX_PRICE_AGE_H:g} saatten eski olduğu için kupona alınmadı "
               "(eski fiyat sakatlık / kadro haberinden önce kalmış olabilir).", ""]
    if coupons:
        md += [f"> **Oran kontrolü {coupons[0]['odds_checked_at']} TSİ:** kupon kurulduktan sonra Nesine bülteni yeniden "
               "çekildi ve her tercih tek tek karşılaştırıldı. "
               + ("Tüm oranlar aynı." if not change_notes else "Değişenler: " + "; ".join(change_notes)), ""]
    if coupons and coupons[0].get("reached") is False:
        md += [f"> **Hedef {args.hedef:g} güvenli tercihlerle bugün ulaşılamıyor.** Aşağıdaki kupon, her bacağı en az "
               f"%{min_prob * 100:.0f} olasılıklı ve 1,{int(round((args.min_oran - 1) * 100)):02d}+ oranlı tüm güvenli "
               "tercihlerden oluşuyor; hedefe ulaşmak için daha zayıf tercih eklemedim.", ""]
    for i, c in enumerate(coupons, 1):
        md += [f"## Kupon {i}: Nesine oranı **{c['nesine_odds']:.2f}** · tutma olasılığı **%{c['probability'] * 100:.1f}** "
               f"(güvenilir alt sınır %{c.get('probability_low', c['probability']) * 100:.1f}) "
               f"· global adil oranı {c['global_fair_odds']:.2f} · {len(c['legs'])} maç (MBS en az {c['min_mbs']})", "",
               "| Saat | Maç | Pazar | Seçim | Nesine oranı | Global olasılık | Global adil oran | Uyumlu skor | MBS | Referans | Fiyat | Araştırma |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for leg in c["legs"]:
            md.append(f"| {leg['kickoff'][11:]} | {leg['match']} | {leg['market']} | {leg['selection']} | {leg['odds']:.2f} | "
                      f"%{leg['p'] * 100:.1f} | {1 / leg['p']:.2f} | "
                      f"{(leg['scores'][0][0] + ' (%' + format(leg['scores'][0][1] * 100, '.1f') + ')') if leg.get('scores') else '-'} | {leg['mbs']} | {leg['reference']} | "
                      f"{'doğrudan' if leg.get('direct') else 'model'} | {'var' if leg.get('researched') else 'yok'} |"
                      + (f" ⚠ {leg['status']}" if leg.get("status") not in (None, "kontrol edildi") else ""))
        md += ["", "**Gerekçeler**", ""]
        md += [f"- **{leg['match']} — {leg['market']}: {leg['selection']}** — {leg_reason(leg)}" for leg in c["legs"]]
        md += ["", f"Kuponun tutma olasılığı %{c['probability'] * 100:.1f}: düşük oranlı bir bacak bile kesin değildir "
                   "(ör. 1,20 oranlı seçim globalde ~%75-80 ihtimal demektir; her 4-5 denemeden biri tutmaz).", ""]
    if args.yontem == "guvenli" and coupons:
        ref = best_coupon(pools, args.hedef, max_legs)
        if ref:
            md += [f"> Karşılaştırma: aynı hedef için birleşik olasılığı en yüksek kupon {len(ref['legs'])} maçla "
                   f"%{ref['probability'] * 100:.1f} (bkz. --yontem optimum).", ""]
    if args.yontem == "optimum" and coupons:
        ref = safest_first_coupon(pools, args.hedef, max_legs)
        md += [("> Karşılaştırma: en düşük oranları biriktiren eski 'güvenli' yöntem aynı hedef için "
                f"{len(ref['legs'])} maçla %{ref['probability'] * 100:.1f}." if ref else
                f"> Karşılaştırma: eski 'güvenli' yöntem bu hedefe {max_legs} maçla ulaşamıyor."), ""]
    md += ["> Fiyat: **doğrudan** = olasılık bu seçimin kendi global borsa fiyatından; **model** = global 1X2 ve Alt/Üst "
           "fiyatından gol modeliyle türetildi (daha az güvenilir). Yalnız doğrudan için: --dogrudan."]
    d = DAILY / args.tarih
    d.mkdir(parents=True, exist_ok=True)
    base = d / f"kupon_{args.hedef:g}x_{stamp}"
    base.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({"target": args.hedef, "created": now.isoformat(timespec="seconds"),
                                                     "coupons": coupons}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {base.with_suffix('.md').relative_to(DAILY.parents[1])}")
    try:  # keep Claude's area of the AI comparison (tahminler/claudetahmin) in step with the new coupons
        import ai_tahmin  # noqa: PLC0415
        if coupons:
            ai_tahmin.save_coupons(args.tarih, args.hedef, coupons)
        ai_tahmin.export(args.tarih, matches)  # this run's own analysis, not the shared report files
    except Exception as exc:  # noqa: BLE001 - the coupon itself is already written
        print(f"⚠ claudetahmin güncellenemedi: {exc}")


if __name__ == "__main__":
    main()
