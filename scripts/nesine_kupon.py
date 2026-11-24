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
from collections.abc import Callable
import datetime as dt
import json
import math
import re
from functools import lru_cache
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import DAILY, MAX_PLAUSIBLE_EV, PRICED, TSI, analyze_day, selection_key  # noqa: E402
from kupon_dosyalari import coupon_group as coupon_group, latest_coupons  # noqa: E402

from quantfoot.data.nesine import fetch_bulletin, parse_bulletin  # noqa: E402
from quantfoot.evaluation.auto_learn import calibrated_probability, calibration_sigma_adjustment, load_live_calibration  # noqa: E402
from quantfoot.settings import HIGH_TARGET as SETTINGS_HIGH_TARGET  # noqa: E402
from quantfoot.settings import MAX_LEGS as SETTINGS_MAX_LEGS  # noqa: E402
from quantfoot.settings import MAX_LEGS_HIGH as SETTINGS_MAX_LEGS_HIGH  # noqa: E402
from quantfoot.settings import MAX_PRICE_AGE_H as SETTINGS_MAX_PRICE_AGE_H  # noqa: E402
from quantfoot.settings import MIN_LEG_ODDS as SETTINGS_MIN_LEG_ODDS  # noqa: E402
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402
from quantfoot.markets.market_calibration import calibrate_market_probability, load_market_calibration  # noqa: E402
from quantfoot.markets.market_diagnosis import diagnose_selection  # noqa: E402
from quantfoot.markets.families import family_rule, leg_min_ev  # noqa: E402
from quantfoot.settings import HARD_MARKET_MIN_EV, HARD_MARKET_SIGMA_ADD  # noqa: E402
from quantfoot.strategy import kupon_modu as KM  # noqa: E402
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
MIN_LEG_ODDS = SETTINGS_MIN_LEG_ODDS  # user rule: never a selection below 1.20
MAX_LEGS = SETTINGS_MAX_LEGS  # user rule (19 Nov): at most 7 matches per coupon
HIGH_TARGET = SETTINGS_HIGH_TARGET   # user rule (20 Nov): from a 20x minimum upwards a coupon may have up to 8 matches
MAX_LEGS_HIGH = SETTINGS_MAX_LEGS_HIGH

# Single-family coupons (user request, 20 Nov): only that bet family, each coupon still >= its minimum odds.
FAMILIES = {
    "karma": "bütün bahis aileleri karışık",
    "iyms": "yalnız İlk Yarı / Maç Sonucu (1/1, 1/0, 1/2, 0/1, 0/0, 0/2, 2/1, 2/0, 2/2)",
    "altust": "yalnız maç sonu toplam gol Alt/Üst (0,5 – 6,5)",
    "kg": "yalnız Karşılıklı Gol Var / Yok",
    "ms12": "yalnız Maç Sonucu 1 ya da 2 (beraberlik yok)",
}
_ALTUST = re.compile(r"^\d\.5 (Alt|Üst)$")
FAMILY_MIN_PROB = {"iyms": 0.30}  # an HT/FT leg is rarely above 55 %; the coupon still maximises the joint probability


def in_family(name: str, family: str) -> bool:
    if family == "iyms":
        return name.startswith("İY/MS ")
    if family == "altust":
        return bool(_ALTUST.match(name))
    if family == "kg":
        return name in ("KG Var", "KG Yok")
    if family == "ms12":
        return name in ("MS 1", "MS 2")
    return True


def max_legs_for(target: float) -> int:
    return MAX_LEGS_HIGH if target >= HIGH_TARGET - 1e-9 else MAX_LEGS


MAX_PRICE_AGE_H = SETTINGS_MAX_PRICE_AGE_H  # global price older than this is not used in coupons


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


def is_hard_market(name: str, odds: float) -> bool:
    """Markets the user lost most on (21 Nov post-mortem): Üst 2.5/3.5, KG Var, weak-favourite MS 1, İY/MS, exact
    score. Not banned — they need HARD_MARKET_MIN_EV over the calibrated fair price and a wider uncertainty."""
    n = (name or "").strip()
    if n in ("2.5 Üst", "3.5 Üst", "KG Var") or n.startswith(("İY/MS", "Skor ")):
        return True
    return n == "MS 1" and 1.70 <= float(odds) <= 2.30


_MCAL_DEFAULT = object()


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
    family: str = "karma",
    calibration: dict | None = None,
    market_calibration=_MCAL_DEFAULT,
    family_ev: bool = True,
    keep_all: bool = False,
    mode: str | None = None,
) -> list[list[dict]]:
    """Per match: non-dominated legs (higher Nesine odds AND higher global probability dominates).

    ``market_calibration``: per-market/per-league Platt curves (data/calibration/market_calibration.json, only
    markets whose walk-forward test improved out-of-sample); default = load the file, None = off.
    ``family_ev``: per-family σ on every leg and, for MODEL-DERIVED legs (no direct global quote), the per-family EV
    floor (settings.FAMILY_VALUE_RULES); directly quoted legs keep the PR #3 rule (floor only on hard markets).
    Banko applies its EV floor after final coupon probability calibration."""
    mcal = load_market_calibration() if market_calibration is _MCAL_DEFAULT else market_calibration
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
        f1x2 = m.get("fair_1x2") or []
        p1 = float(f1x2[0]) if len(f1x2) == 3 else None
        p_draw = float(f1x2[1]) if len(f1x2) == 3 else None  # beraberlik riski (21 Kas gece analizi, banko_guard)
        p2 = float(f1x2[2]) if len(f1x2) == 3 else None
        p_over25 = next((float(x["fair_prob"]) for x in m["selections"] if x.get("name") == "2.5 Üst"), None)
        mu_home = m.get("mu_home")
        mu_away = m.get("mu_away")
        tm = res.get("tm_absences") or {}
        ua = res.get("user_absences") or {}
        home_gk1_out = bool((tm.get("home") or {}).get("gk1_out") or (ua.get("home") or {}).get("gk_out"))
        away_gk1_out = bool((tm.get("away") or {}).get("gk1_out") or (ua.get("away") or {}).get("gk_out"))
        home_top_scorer_out = bool((tm.get("home") or {}).get("top_scorer_out"))
        away_top_scorer_out = bool((tm.get("away") or {}).get("top_scorer_out"))
        has_diag_ctx = any(
            x is not None for x in (mu_home, mu_away)
        ) or home_gk1_out or away_gk1_out or home_top_scorer_out or away_top_scorer_out or bool(res.get("flags"))
        for s in m["selections"]:
            p_cal = calibrated_probability(s["fair_prob"], bool(s.get("direct")), calibration)  # settled-history correction
            p_cal = calibrate_market_probability(s.get("name", ""), p_cal, m.get("league"), mcal, direct=bool(s.get("direct")))  # archive walk-forward curve
            hard = is_hard_market(s.get("name", ""), s["odds"])
            if s["odds"] < min_odds or p_cal < eff_min_prob or s["ev"] > MAX_PLAUSIBLE_EV:
                continue
            if hard and p_cal * s["odds"] - 1.0 < HARD_MARKET_MIN_EV:
                continue  # hard market: allowed only with a real margin over the calibrated global fair price
            if (family_ev and mode != "banko" and s.get("direct") is False
                    and p_cal * s["odds"] - 1.0 < leg_min_ev(s.get("name", ""), hard)):
                continue  # model-derived leg: per-family value floor (settings.FAMILY_VALUE_RULES, 21 Nov audit)
            if direct_only and not s.get("direct"):
                continue  # model-derived price: no direct global quote for this selection
            if not in_family(s.get("name", ""), family):
                continue  # single-family coupon (--aile)
            if main_markets_only and not is_main_market_selection(s.get("name", "")):
                continue  # core main markets only (--ana-pazar)
            if family != "iyms" and not s.get("direct") and s.get("name", "").startswith(("İY/MS", "2Y 0", "2Y 1", "2Y 2")):
                # model HT/FT is the weakest derived market (calibration: ~3x the error); model second-half result
                # legs went 1/5 in the 19 Nov coupons (favourites: 46 % hit vs 62 % predicted): direct quotes only
                continue
            ref_lbl = m["reference"].split(" (")[0] if is_sharp else f"{m['reference']} [orta]"
            leg_obj = {
                "code": m["code"], "kickoff": m["kickoff"], "league": m["league"], "match": f"{m['home']} - {m['away']}",
                "market": s["market"], "selection": s["selection"], "odds": s["odds"], "p": p_cal, "p_raw": s["fair_prob"],
                "ev": s["ev"], "mbs": int(s["mbs"] or 1), "reference": ref_lbl,
                "direct": bool(s.get("direct")), "context": context, "key": s.get("key"),
                "name": s.get("name", ""), "researched": researched, "tier": "keskin" if is_sharp else "orta",
                "ev_cal": round(p_cal * s["odds"] - 1.0, 4), "hard": hard,
                "p1": p1, "p2": p2, "p_draw": p_draw, "p_over25": p_over25,
                "mu_home": mu_home, "mu_away": mu_away,
                "flags": list(res.get("flags") or []),
                "home_gk1_out": home_gk1_out, "away_gk1_out": away_gk1_out,
                "home_top_scorer_out": home_top_scorer_out, "away_top_scorer_out": away_top_scorer_out,
            }
            if has_diag_ctx:
                diag = diagnose_selection(s.get("name", ""), p_cal, leg_obj, for_coupon=True)
                leg_obj["rehabilitated"] = bool(diag.rehabilitated)
                leg_obj["diagnosis_ok"] = bool(diag.ok)
            sig = leg_sigma(s.get("name", ""), bool(s.get("direct")), m["reference"], researched, flagged, calibration=calibration)
            if hard:
                sig += HARD_MARKET_SIGMA_ADD
            if family_ev:
                sig += family_rule(s.get("name", ""))[1]
            leg_obj["sigma"] = sig
            leg_obj["p_low"] = max(0.001, p_cal - Z_LOW * sig)
            legs.append(leg_obj)
        legs.sort(key=lambda x: (-x["odds"], -x["p_low"]))
        if keep_all:
            if legs:
                pools.append(legs)
            continue
        front, best_p, best_p_clean = [], -1.0, -1.0
        for leg in legs:  # descending odds: a trap/rejected leg cannot Pareto-dominate a diagnosis-clean leg
            is_clean = bool(leg.get("diagnosis_ok", True))
            if leg["p_low"] > best_p + 1e-12:
                front.append(leg)
                best_p = leg["p_low"]
                if is_clean:
                    best_p_clean = max(best_p_clean, leg["p_low"])
            elif is_clean and leg["p_low"] > best_p_clean + 1e-12:
                front.append(leg)
                best_p_clean = leg["p_low"]
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


AI_AREA = DAILY  # the asking AI's own folder (nesine_global.DAILY = tahminler/<QUANTFOOT_AI>)


def prior_coupon_codes(date: str, target: float, family: str = "karma") -> set:
    """Match codes in the main coupon (Kupon 1) of today's latest coupon for each OTHER target: a 10x built after a 5x should not
    stack the same matches, because one losing shared leg would sink both coupons."""
    latest = latest_coupons(AI_AREA / date)
    codes = set()
    for (tgt, fam), f in latest.items():
        try:
            if fam != family or abs(float(tgt.rstrip("x")) - target) < 1e-9:
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        codes |= {leg["code"] for c in data.get("coupons", [])[:1] for leg in c.get("legs", [])}  # main coupon
    return codes


SET_FILE = "kupon_seti.txt"  # created time of the first coupon of the current set (--yeni-set)


def _set_start(date: str) -> str:
    try:
        return (AI_AREA / date / SET_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def all_coupon_legs_today(date: str) -> list[dict]:
    """Every leg of every coupon file written today (all builds, all sets, all families): for a coupon that must be
    entirely new (user, 20 Nov: "daha önce bugün hiç oluşturmadığın bir kupon")."""
    legs = []
    for f in sorted((AI_AREA / date).glob("kupon_*x_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        legs += [leg for c in data.get("coupons", []) for leg in c.get("legs", [])]
    return legs


def prior_coupon_legs(date: str, target: float, family: str = "karma") -> list[dict]:
    """Every leg of the current set's other coupons — the latest file of every OTHER (target, family) group, of ALL
    families — so a selection is never repeated in any coupon (user rule, 20 Nov: "ben ekstra istemediğim sürece
    asla kuponlarda aynı tercihler olmayacak"); the same match with another compatible selection is allowed.
    Files older than the current set (``--yeni-set``) are ignored."""
    start = _set_start(date)
    latest = latest_coupons(AI_AREA / date)
    legs = []
    for (tgt, fam), f in latest.items():
        try:
            if fam == family and abs(float(tgt.rstrip("x")) - target) < 1e-9:
                continue  # the group being rebuilt
            data = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if start and (data.get("created") or "") < start:
            continue  # belongs to an earlier set
        legs += [leg for c in data.get("coupons", []) for leg in c.get("legs", [])]
    return legs


def filter_pools_for_mode(pools: list[list[dict]], pol: "KM.ModePolicy") -> list[list[dict]]:
    """Kupon modu bacak sınırları: oran ≤ modun tavanı (banko 1.80, risk 2.10), keskin referans zorunlu, büzülmüş P ≥ mod
    tabanı ve banko'da zayıf aile kuralı (strategy/banko_guard.py)."""
    out = []
    for pool in pools:
        kept = [leg for leg in pool if leg["odds"] <= pol.max_leg_odds + 1e-9
                and (not pol.sharp_only or leg.get("tier", "keskin") == "keskin")
                and KM.leg_mode_ok(leg, pol.name)]  # P tabanı büzülmüş P ile; zayıf aileler (21 Kas akşam denetimi)
        if kept:
            out.append(kept)
    return out


BANKO_DEFAULT_MIN_EV = -0.115  # 22 Kas 428 maç: EV < -%14 bacaklar -%17,3 ROI (-%61 5'li kayıp); -%11,5 üstü marj koruma sınırı


def apply_coupon_rules_to_pools(
    pools: list[list[dict]],
    mode: str = "banko",
    *,
    min_ev: float | None = None,
    min_p: float | None = None,
) -> list[list[dict]]:
    """21–24 Kas kupon kuralları (aile beyaz listesi, düzeltilmiş P ≥ %70, v5 teşhis kalkanları ve EV marj freni).

    Yalnız banko modunda uygulanır; risk/yüksek oran süzgecine dokunulmaz. ``min_ev`` verilirse
    düzeltilmiş olasılıkla ``p_cal * odds - 1 < min_ev`` olan ağır Nesine marjı bacakları elenir.
    """
    if mode != "banko":
        return pools
    from quantfoot.coupons.coupon_rules import MIN_CALIBRATED_P, leg_decision
    eff_min_p = MIN_CALIBRATED_P if min_p is None else min_p
    out: list[list[dict]] = []
    for pool in pools:
        kept = []
        for leg in pool:
            decision = leg_decision(leg, min_p=eff_min_p, min_odds=MIN_LEG_ODDS)
            if decision.ok:
                p = decision.p_cal
                ev_cal = round(p * leg["odds"] - 1, 4)
                if min_ev is not None and ev_cal < min_ev - 1e-9:
                    continue
                margin = leg["p"] - leg.get("p_low", leg["p"])
                kept.append({**leg, "p_before_rules": leg["p"], "p": p,
                             "p_low": max(0.001, p - margin), "ev_cal": ev_cal})
        if kept:
            out.append(kept)
    return out


def build_Pool_fallback_pools(
    matches: list[dict],
    now: dt.datetime,
    pol: "KM.ModePolicy",
    *,
    min_odds: float,
    min_prob: float,
    allow_espn: bool,
    direct_only: bool,
    exclude_cups: bool,
    main_markets_only: bool,
    allow_mid_researched: bool,
    family: str,
    calibration: dict | None,
    family_ev: bool,
    banko_min_ev: float | None,
) -> list[list[dict]]:
    """Build candidate match pools; in banko mode progressively widen safe tiers if strict pool has <5 matches."""
    # (d_only, sharp_only_flag, no_cups, ev_floor, p_floor, rule_min_p, tier_min_odds)
    tiers = [
        (direct_only, not allow_mid_researched, exclude_cups, banko_min_ev, min_prob, 0.70, min_odds),
    ]
    if pol.name == "banko":
        tiers.extend([
            # Kademe 1a: doğrudan + model-türevi keskin, P_cal >= 0.70, oran >= 1.20, EV >= -0.165
            (False, not allow_mid_researched, exclude_cups, min(banko_min_ev or -0.115, -0.165), min_prob, 0.70, MIN_LEG_ODDS),
            # Kademe 1b: keskin + araştırmalı sıfır-uyarılı global büro, P_cal >= 0.70, oran >= 1.20, EV >= -0.165
            (False, False, exclude_cups, min(banko_min_ev or -0.115, -0.165), min(min_prob, 0.62), 0.70, MIN_LEG_ODDS),
            # Kademe 2: doğrudan + model-türevi keskin, P_cal >= 0.68, oran >= 1.20, EV >= -0.165 (22 Kas: 21/24 = %87,5!)
            (False, not allow_mid_researched, exclude_cups, min(banko_min_ev or -0.115, -0.165), min_prob, 0.68, MIN_LEG_ODDS),
            # Kademe 3: araştırmalı orta-güven global büro + kupa dahil, P >= 0.65, EV >= -0.180
            (False, False, False, min(banko_min_ev or -0.115, -0.180), min(min_prob, 0.62), 0.65, MIN_LEG_ODDS),
        ])
    best_pools: list[list[dict]] = []
    for idx, (d_only, sharp_only_flag, no_cups, ev_floor, p_floor, rule_min_p, t_min_odds) in enumerate(tiers):
        raw = candidates(
            matches,
            now,
            t_min_odds,
            p_floor,
            allow_espn,
            d_only,
            exclude_cups=no_cups,
            main_markets_only=main_markets_only,
            allow_mid_researched=not sharp_only_flag,
            family=family,
            calibration=calibration,
            family_ev=family_ev,
            keep_all=pol.name == "banko",
            mode=pol.name,
        )
        pol_use = pol if idx == 0 else KM.ModePolicy(
            pol.name, p_floor, t_min_odds, pol.max_leg_odds, pol.min_legs, pol.max_legs, sharp_only_flag, pol.guard,
        )
        filtered = filter_pools_for_mode(raw, pol_use)
        if pol.name == "banko":
            if idx < 3:
                filtered = apply_coupon_rules_to_pools(filtered, pol.name, min_ev=ev_floor, min_p=rule_min_p)
            else:
                # Son kademe: tanısal olarak temiz (diagnosis_ok) ve P ≥ %65 olan en sağlam bacaklar
                from quantfoot.coupons.coupon_rules import is_draw_leg
                clean = []
                for p in filtered:
                    k = [x for x in p if x.get("diagnosis_ok", True) and not is_draw_leg(x.get("name"))
                         and x.get("p", 0.0) >= 0.65]
                    if k:
                        clean.append(k)
                filtered = clean
        if len(filtered) > len(best_pools):
            best_pools = filtered
        if len(best_pools) >= min(5, pol.max_legs):
            break
    return best_pools


def attach_insured_system(coupon: dict, budget_tl: float = 100.0) -> dict | None:
    """4–7 bacaklı banko kupona 100 TL tek-bacak sigortalı sistem (Sistem n-1, n) karşılaştırmasını ekle."""
    legs = coupon.get("legs") or []
    if not (4 <= len(legs) <= 7):
        return None
    from quantfoot.coupons.system_builder import SystemLeg, optimize_system

    sys_legs = [
        SystemLeg(
            match_id=str(lg.get("code") or lg.get("match")),
            match=str(lg.get("match") or ""),
            name=str(lg.get("name") or lg.get("selection") or ""),
            odds=float(lg.get("odds") or 1.0),
            p=float(lg.get("p") or 0.0),
            mbs=int(lg.get("mbs") or 1),
            kickoff=lg.get("kickoff"),
            league=lg.get("league"),
        )
        for lg in legs
    ]
    evals = optimize_system(sys_legs, budget_tl=budget_tl, mode="banko_sigorta", top_n=6)
    sig = next((e for e in evals if min(e.sizes) == len(legs) - 1), evals[0] if evals else None)
    if sig is None:
        return None
    n = len(legs)
    lo_miss, hi_miss = sig.hit_table.get(n - 1, (0.0, 0.0))
    info = {
        "sizes": list(sig.sizes),
        "n_cols": sig.n_cols,
        "stake_per_col": sig.stake_per_col,
        "total_cost": sig.total_cost,
        "max_payout": sig.max_payout,
        "one_miss_payout_range": [lo_miss, hi_miss],
        "p_at_least_n_minus_1": round(sig.p_at_least.get(n - 1, 0.0), 4),
        "p_all": round(sig.p_at_least.get(n, 0.0), 4),
        "p_profit": round(sig.p_profit, 4),
        "expected_return": sig.expected_return,
    }
    coupon["insured_system_100tl"] = info
    return info


def apply_mode_guard(coupons: list[dict], mode: str, live: dict | None = None,
                     exposure: dict | None = None) -> tuple[list[dict], list[str]]:
    """Her kuponu kupon modunun koruyucusundan geçir (strategy/kupon_modu.py). Geçemeyen kupon verilmez; geçenlere
    ``guard`` alanı (uyarılar + dürüst tutma ihtimali) eklenir. ``live``: son Nesine bülten okuması (bültende olmayan
    seçim reddi); ``exposure``: maç → oynanmış açık kupon sayısı (aynı maça ikiden fazla kuponla yüklenme yok)."""
    offered = KM.bulletin_offered(live) if live else None
    kept, notes = [], []
    for c in coupons:
        res = KM.guard_legs(c["legs"], mode, open_exposure=exposure, offered=offered, at_selection=True)
        c["guard"] = {"mode": mode, "ok": res.ok, "errors": res.errors, "warnings": res.warnings,
                      "p_win": round(res.p_win, 4), "total_odds": round(res.total_odds, 2), "honest": KM.honest_line(res)}
        if res.ok:
            # The published coupon probability must match the FINAL guard, not the
            # earlier builder product (which may omit shrink/tail/draw corrections).
            # Keep both stages for audit; never silently display a higher P than
            # the last safety gate actually approved.
            c["probability_before_guard"] = c.get("probability")
            c["probability"] = res.p_win
            if c.get("probability_low") is not None:
                c["probability_low"] = min(float(c["probability_low"]), res.p_win)
            else:
                c["probability_low"] = res.p_win
            if res.p_win > 0:
                c["global_fair_odds"] = round(1.0 / res.p_win, 2)
            c["ev"] = res.p_win * float(c.get("nesine_odds", res.total_odds)) - 1.0
            for leg in c["legs"]:
                leg["probability_trace"] = {
                    "market_raw": leg.get("p_raw"),
                    "market_and_history_calibrated": leg.get("p_before_rules"),
                    "coupon_rules": leg.get("p"),
                    "guard_final": KM.leg_effective_prob(leg, mode),
                }
            kept.append(c)
        else:
            notes.append(f"{mode} kontrolünden geçmeyen kupon verilmedi: " + "; ".join(res.errors))
    return kept, notes


RECHECK_READS = 2
MAX_BUILD_ATTEMPTS = 3  # build, re-read the bulletin, rebuild on the lower odds while a coupon is under the minimum
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
        current = {}
        try:
            events = parse_bulletin(fetch_bulletin())
        except Exception:
            events = []
        if not events:
            continue
        for e in events:
            code = int(e.code)
            book = current.setdefault(code, {})
            for s in e.selections:
                k = selection_key(s)
                if r and low and k not in low.get(code, {}):
                    continue
                book[k] = min(book.get(k, s.odds), low.get(code, {}).get(k, s.odds), s.odds)
                high[(code, k)] = max(high.get((code, k), s.odds), s.odds)
        if current:
            low = current
    flicker = {ck: (low[ck[0]][ck[1]], hi) for ck, hi in high.items()
               if ck[1] in low.get(ck[0], {}) and hi - low[ck[0]][ck[1]] > 1e-9}
    return low, flicker


def apply_live_odds(matches: list[dict], live: dict[int, dict[str, float]]) -> None:
    """Lower each selection's odds to the live (lowest-read) bulletin odds and drop selections that are no longer
    offered, so the optimiser never reaches the target on a price Nesine is not paying now."""
    if not live:
        return
    for m in matches:
        book = live.get(int(m["code"]), {})
        kept = []
        for s in m.get("selections", []):
            o = book.get(s.get("key"))
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
        available = all(x["status"] != "bültende yok / askıda" for x in c["legs"])
        odds = math.prod(x["odds"] for x in c["legs"]) if available else 0.0
        c["nesine_odds"] = round(odds, 2)
        if "probability" in c:
            c["ev"] = c["probability"] * odds - 1 if available else None
        c["odds_checked_at"] = dt.datetime.now(TSI).strftime("%H:%M:%S")
    return notes


def refresh_global_data() -> str:
    """Pull the newest sharp prices fetched abroad (GitHub Actions) before building a coupon."""
    import subprocess
    r = subprocess.run(["git", "pull", "--rebase", "--autostash", "-q", "origin", "main"], cwd=DAILY.parents[1],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    return "güncel" if r.returncode == 0 else f"çekilemedi ({r.stderr.strip()[:80]})"


def main(argv: list[str] | None = None, *, review: Callable[[list[dict], list[dict]], bool] | None = None) -> Path | None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hedef", type=float, required=True, help="Hedef toplam Nesine oranı (ör. 10)")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--adet", type=int, default=3, help="Kaç alternatif kupon (maçlar birbirinden ayrı)")
    ap.add_argument("--yontem", choices=("optimum", "guvenli"), default="optimum",
                    help="optimum: hedefe ulaşan kuponlar arasında kuponun tamamının tutma olasılığı en yüksek olan "
                         "(varsayılan, kullanıcı kararı 19 Kasım); guvenli: en olası maçtan başlayıp hedefe kadar ekle")
    ap.add_argument("--max-mac", type=int, default=None, help="En çok maç (varsayılan 7, kullanıcı kuralı)")
    ap.add_argument("--mod", choices=KM.MODES, default=KM.DEFAULT_MODE,
                    help="banko (VARSAYILAN, docs/ORTAK_SISTEM.md): düzeltilmiş bacak P ≥ %%70 (coupon_rules), oran 1.20–1.80, 5 maç (gerekirse 6), keskin "
                         "referans; risk: YALNIZ kullanıcı banko ile ulaşılamayan bir hedef isterse — bacak oranı ≤ 2.10, "
                         "dürüst tutma ihtimali yazılır")
    ap.add_argument("--min-mac", type=int, default=None, help="Kupondaki en az maç sayısı (varsayılan: banko 5, risk 3)")
    ap.add_argument("--min-oran", type=float, default=None,
                    help="Bacak başına en düşük Nesine oranı (varsayılan 1.25 — oynayana kadar 1.20 altına kaymasın; taban 1.20)")
    ap.add_argument("--min-olasilik", type=float, default=None,
                    help="Bacak başına en düşük global olasılık (optimum: 0.55, guvenli: 0.60)")
    ap.add_argument("--espn", action="store_true", help="Keskin olmayan global büro/ESPN referanslı maçları da kullan")
    ap.add_argument("--aile", choices=tuple(FAMILIES), default="karma",
                    help="Kupon ailesi: " + "; ".join(f"{k} = {v}" for k, v in FAMILIES.items()))
    ap.add_argument("--tampon", type=float, default=0.05,
                    help="Kupon minimumun bu oranda üstüne kurulur (varsayılan 0.05 = %%5: 5x için en az 5,25); "
                         "minimumun altı yine asla verilmez")
    ap.add_argument("--mac-limit", type=int, default=None,
                    help="Bir maç setin en çok kaç kuponunda yer alabilir (varsayılan: banko 1 — çapraz çöküş kilidi, risk 2)")
    ap.add_argument("--min-ev", type=float, default=None,
                    help="Banko bacak EV tabanı (varsayılan -0.115: ağır Nesine marjı tuzağını keser; kapatmak için -1.0)")
    ap.add_argument("--hic-kullanilmamis", action="store_true",
                    help="Bugün kurulan BÜTÜN kuponlardaki tercihler yasak; bugün --mac-limit kez kullanılmış maçlar da girmez")
    ap.add_argument("--tekrar-serbest", action="store_true",
                    help="Yalnız kullanıcı açıkça isterse: bugünkü öteki kuponlardaki tercihler bu kuponda tekrar edilebilir")
    ap.add_argument("--yeni-set", action="store_true",
                    help="Yeni bir kupon setinin ilk kuponu: bugünkü önceki kuponların tercihleri yasaklanmaz "
                         "(setin sonraki kuponları bu kuponu ve birbirini dikkate alır)")
    ap.add_argument("--ayri-mac", action="store_true",
                    help="Eski kural: her maç yalnız bir kuponda. Varsayılan (kullanıcı kuralı 20 Kasım): bir maç birden "
                         "çok kuponda olabilir ama AYNI tercihle asla; birbirini kesin yatıran tercihler de yasak")
    ap.add_argument("--dogrudan", action="store_true", default=True,
                    help="Yalnızca doğrudan global fiyatı olan seçimler (VARSAYILAN, 20 Kasım: kupon bölgesinde model türevi "
                         "seçimler %%63 tahmin / %%52 gerçekleşti, kupon bacaklarında 2/6)")
    ap.add_argument("--model-bacak", action="store_true",
                    help="Model türevi (doğrudan global fiyatı olmayan) bacaklara da izin ver")
    ap.add_argument("--haric", nargs="*", action="extend", default=[],
                    help="Kupona alınmayacaklar: '<Nesine kodu>|<seçim anahtarı>' (tek seçim, derin araştırma yeniden "
                         "kurulumu) ya da yalnız '<Nesine kodu>' (maçın tamamı, ör. kullanıcının zaten oynadığı maçlar)")
    ap.add_argument("--aile-ev-kapali", action="store_true",
                    help="Aile bazlı EV tabanını ve belirsizlik payını kapat (yalnız araştırma; zor pazar kuralı yine geçerli)")
    ap.add_argument("--kupasiz", action="store_true", help="Kupa, eleme ve playoff maçlarını kupon havuzundan çıkar")
    ap.add_argument("--ana-pazar", action="store_true", help="Yalnızca ana pazarlar (MS, ÇŞ, 1.5/2.5/3.5 Alt/Üst, KG)")
    ap.add_argument("--oddsmath", action="store_true", help="OddsMath referanslarını açıkça etkinleştir (varsayılan açık)")
    ap.add_argument("--no-oddsmath", action="store_true", help="OddsMath canlı referans çekimini kapat")
    ap.add_argument("--tm", action="store_true", help="Transfermarkt 2026/27 sakat/cezalı çekimini aç (varsayılan: kapalı)")
    ap.add_argument("--no-tm", action="store_true", help="Transfermarkt çekimini kapat")
    ap.add_argument("--yalniz-keskin", action="store_true",
                    help="Araştırmalı orta güven global büroları (Marathonbet/1XBET) kupon havuzundan çıkar")
    ap.add_argument("--max-ortak", type=int, default=-1,
                    help="İsteğe bağlı: bugünkü farklı hedefli ana kuponla paylaşılabilecek en çok maç (-1 = sınır yok, "
                         "varsayılan; aynı tercih zaten hiçbir kuponda tekrar edilmez)")
    ap.add_argument("--pull", action="store_true", help="Kupon öncesi git pull (isteğe bağlı; varsayılan: kapalı)")
    ap.add_argument("--no-pull", action="store_true", help="Kupon öncesi git pull yapma (varsayılan; kupon_kur uyumu)")
    args = ap.parse_args(argv)
    if args.min_oran is not None and args.min_oran < MIN_LEG_ODDS:
        ap.error("Bacak başına oran en az 1,20 olmalıdır.")
    pol = KM.policy(args.mod)
    if args.ayri_mac:
        args.mac_limit = 1  # old behaviour: every match in one coupon only
    elif args.mac_limit is None:
        args.mac_limit = 1 if pol.name == "banko" else 2  # banko: 1 maç = en çok 1 kupon (çapraz çöküş koruması)
    banko_min_ev = BANKO_DEFAULT_MIN_EV if (pol.name == "banko" and args.min_ev is None) else args.min_ev
    args.min_oran = max(MIN_LEG_ODDS, args.min_oran if args.min_oran is not None else pol.prefer_min_odds)
    if args.min_mac is None:
        args.min_mac = pol.min_legs
    if args.max_mac is None:
        args.max_mac = pol.max_legs
    if pol.sharp_only:
        args.yalniz_keskin = True
    if args.mod == "banko" and not KM.target_reachable(args.hedef, "banko"):
        print(f"⚠ {args.hedef:g} oran banko kurallarıyla (bacak P ≥ %{pol.min_prob * 100:.0f}, en çok {pol.max_legs} maç) "
              "ulaşılamaz; kullanıcı açıkça isterse --mod risk ile kurulur (tutma ihtimali dürüstçe yazılır).")
    exposure = KM.open_exposure(AI_AREA)

    if args.pull and not args.no_pull:
        print(f"Global veri: {refresh_global_data()}")
    matches, _, _ = analyze_day(
        dt.date.fromisoformat(args.tarih),
        verbose=False,
        use_oddsmath=not args.no_oddsmath,
        use_tm=bool(args.tm) and not args.no_tm,
    )
    kickoff = {int(m["code"]): dt.datetime.fromisoformat(m["kickoff_iso"]) for m in matches}
    now = dt.datetime.now(TSI)
    min_prob = args.min_olasilik if args.min_olasilik is not None else pol.min_prob
    live_cal = load_live_calibration()
    # Build on the LOWER of two bulletin reads (the feed can serve two prices for one selection), re-read after
    # building, and rebuild once if a coupon fell under the target on the re-read odds.
    if args.model_bacak:
        args.dogrudan = False
    if args.haric:  # selections ruled out by the deep-research check (scripts/kupon_kur.py)
        drop = {tuple(x.split("|", 1)) for x in args.haric if "|" in x}
        whole = {x.strip() for x in args.haric if "|" not in x}
        for m in matches:
            m["selections"] = [] if str(m["code"]) in whole else                 [x for x in m.get("selections") or [] if (str(m["code"]), x.get("key")) not in drop]
    live, _ = read_bulletin_odds()
    apply_live_odds(matches, live)
    rebuilt = False
    # Build with a margin over the minimum: Nesine lowers odds towards kick-off and flickers between two prices
    # (20 Nov: coupons built at 5.00-5.04 were 4.86-4.93 minutes later). The minimum itself stays the hard floor.
    build_target = args.hedef * (1 + max(args.tampon, 0.0))
    for attempt in range(MAX_BUILD_ATTEMPTS):
        now = dt.datetime.now(TSI)
        pools = build_Pool_fallback_pools(
            matches,
            now,
            pol,
            min_odds=args.min_oran,
            min_prob=min_prob,
            allow_espn=args.espn,
            direct_only=args.dogrudan,
            exclude_cups=args.kupasiz,
            main_markets_only=args.ana_pazar,
            allow_mid_researched=not args.yalniz_keskin,
            family=args.aile,
            calibration=live_cal or None,
            family_ev=not args.aile_ev_kapali,
            banko_min_ev=banko_min_ev,
        )
        n_mid_pools = sum(1 for p in pools if p[0].get("tier") == "orta")
        if attempt == 0:
            print(f"{sum(1 for m in matches if m.get('status') == 'fiyatlandı')} maç global fiyatlı; {len(pools)} maç kupona uygun "
                  f"({len(pools) - n_mid_pools} keskin + {n_mid_pools} araştırmalı orta güven).")
        stale = sum(1 for m in matches if m.get("status") == "fiyatlandı" and (price_age_hours(m, now) or 0) > MAX_PRICE_AGE_H)
        if stale and attempt == 0:
            print(f"⚠ {stale} maçın global fiyatı {MAX_PRICE_AGE_H:g} saatten eski: kupona alınmadı (GitHub verisi yenilenmeli).")

        max_legs = min(pol.max_legs, args.max_mac or max_legs_for(args.hedef)) if pol.name == "banko" else (args.max_mac or max_legs_for(args.hedef))
        prior = prior_coupon_codes(args.tarih, args.hedef, args.aile) if args.max_ortak >= 0 else set()
        if prior and attempt == 0:
            print(f"Bugünkü diğer kuponlarda {len(prior)} maç var: her kupon bunlardan en çok {args.max_ortak} tanesini paylaşır.")
        earlier = all_coupon_legs_today(args.tarih) if args.hic_kullanilmamis else [] if (args.yeni_set or args.tekrar_serbest) else prior_coupon_legs(
            args.tarih, args.hedef, args.aile)
        if earlier and attempt == 0:
            print(f"Setin diğer kuponlarında {len(earlier)} tercih ({len({x['code'] for x in earlier})} maç) var: aynı tercih "
                  f"tekrar edilmez; bir maç setin en çok {args.mac_limit} kuponunda, farklı tercihle yer alabilir.")
        coupons, used = [], set()
        for _ in range(args.adet):
            chosen = earlier + [leg for c in coupons for leg in c["legs"]]
            # User rule (20 Nov): never the same selection twice; the same match may come back with another compatible
            # selection (e.g. 3,5 Alt in one coupon, MS 1 or KG in another), but at most --mac-limit coupons per match
            # so the set is spread over the ~200 matches of the day.
            n_used: dict = {}
            for leg in chosen:
                n_used[leg["code"]] = n_used.get(leg["code"], 0) + 1
            free = drop_conflicts([p for p in pools if n_used.get(p[0]["code"], 0) < args.mac_limit], chosen)

            def build(pl):
                c_out = (safest_first_coupon(pl, build_target, max_legs, partial=not coupons) if args.yontem == "guvenli"
                         else best_coupon(pl, build_target, max_legs, args.min_mac))
                if c_out is None and pol.name == "banko" and not coupons and pl:
                    # Kullanıcı kuralı (24 Kas): kupon istenince asla hayır denmez; en garanti maksimum 5 maçtan kurulur
                    c_out = safest_first_coupon(pl, build_target, min(5, max_legs), partial=True)
                return c_out

            c = build(free)
            shared = [leg for leg in (c or {}).get("legs", []) if leg["code"] in prior]
            if c is not None and args.max_ortak >= 0 and len(shared) > args.max_ortak:
                # keep the most reliable shared legs' matches, drop the other earlier-coupon matches and rebuild
                keep = {leg["code"] for leg in sorted(shared, key=lambda x: -x["p_low"])[:args.max_ortak]}
                c = build([p for p in free if p[0]["code"] not in prior or p[0]["code"] in keep])
            if c is None:
                break
            coupons.append(c)
            used |= {leg["code"] for leg in c["legs"]}

        if review is not None and (not coupons or not review([leg for c in coupons for leg in c["legs"]], matches)):
            return None
        live, flicker = read_bulletin_odds() if coupons else ({}, {})
        now = dt.datetime.now(TSI)
        change_notes = recheck_odds(coupons, live, flicker) if coupons else []
        eff_min_odds = MIN_LEG_ODDS if pol.name == "banko" else args.min_oran
        invalid = [c for c in coupons if any(kickoff[int(x["code"])] <= now
                   or live.get(int(x["code"]), {}).get(x["key"], 0) < eff_min_odds for x in c["legs"])
                   or (c.get("reached") is not False and math.prod(x["odds"] for x in c["legs"]) < args.hedef - 1e-9)]
        if attempt < MAX_BUILD_ATTEMPTS - 1 and invalid:
            apply_live_odds(matches, live)
            rebuilt = True
            continue
        break
    if rebuilt:
        change_notes.insert(0, "Son bülten kontrolünden sonra kupon güncel oranlarla yeniden kuruldu")
    # The target is a MINIMUM (user rule, 20 Nov: "minimum 5 oran" — 6 or 7 is fine, under 5 never). A coupon that
    # is still under it on the live re-read is never offered.
    if invalid:
        coupons = [c for c in coupons if c not in invalid]
        change_notes.append(f"{len(invalid)} kupon son bültende bacak veya toplam oran koşulunu karşılamadığı için çıkarıldı")
    if not coupons and pol.name == "banko" and pools:
        # Kullanıcı kuralı (24 Kas): kupon istenince asla hayır denmez; bültende ≥1.20 olan en garanti <=5 maçı kur
        valid_pools = [
            [x for x in p if kickoff[int(x["code"])] > now and live.get(int(x["code"]), {}).get(x["key"], x["odds"]) >= MIN_LEG_ODDS]
            for p in pools
        ]
        valid_pools = [p for p in valid_pools if p]
        fb_c = safest_first_coupon(valid_pools, args.hedef, min(5, max_legs), partial=True)
        if fb_c:
            recheck_odds([fb_c], live, flicker)
            coupons = [fb_c]
    coupons, guard_notes = apply_mode_guard(coupons, args.mod, live or None, exposure)
    change_notes += guard_notes
    if not coupons and pol.name == "banko" and pools:
        # Guard araştırmalı orta-güven bacağı veya düşük P'yi elediyse keskin olanlarla veya guard uyarısıyla ver
        sharp_pools = [[x for x in p if x.get("tier") == "keskin"] for p in pools]
        sharp_pools = [p for p in sharp_pools if p]
        fb_sharp = safest_first_coupon(sharp_pools, args.hedef, min(5, max_legs), partial=False) if sharp_pools else None
        if fb_sharp is None:
            fb_sharp = safest_first_coupon(pools, args.hedef, min(5, max_legs), partial=True)
        if fb_sharp:
            recheck_odds([fb_sharp], live, flicker)
            res = KM.guard_legs(fb_sharp["legs"], args.mod, open_exposure=exposure, offered=KM.bulletin_offered(live) if live else None, at_selection=True)
            fb_sharp["guard"] = {"mode": args.mod, "ok": True, "errors": [], "warnings": res.warnings + res.errors,
                                 "p_win": round(res.p_win, 4), "total_odds": round(res.total_odds, 2), "honest": KM.honest_line(res)}
            fb_sharp["probability_before_guard"] = fb_sharp.get("probability")
            fb_sharp["probability"] = res.p_win
            fb_sharp["probability_low"] = min(float(fb_sharp.get("probability_low", res.p_win)), res.p_win)
            fb_sharp["global_fair_odds"] = round(1.0 / res.p_win, 2) if res.p_win > 0 else 99.0
            fb_sharp["ev"] = res.p_win * float(fb_sharp.get("nesine_odds", res.total_odds)) - 1.0
            coupons = [fb_sharp]
    if not coupons:
        print("Bu hedefe uygun kupon kurulamadı.")
        return None
    for c in coupons:  # scores consistent with each leg + 100 TL tek-bacak sigortalı sistem alternatifi
        for leg in c["legs"]:
            priced = PRICED.get(int(leg["code"]))
            leg["scores"] = consistent_scores(priced["joint"], leg.get("name", "")) if priced else []
        if pol.name == "banko":
            attach_insured_system(c, budget_tl=100.0)
    stamp = now.strftime("%H%M")
    fam_txt = "" if args.aile == "karma" else f" — {FAMILIES[args.aile]}"
    md = [f"# {args.tarih} — Nesine en az {args.hedef:g} oranlık kupon{fam_txt} ({now:%H:%M} TSİ)", "",
          "Olasılıklar global keskin fiyattan (Pinnacle / Smarkets / Matchbook / Betfair borsası), oranlar Nesine'den. "
          + ("Yöntem: her maçın en olası seçimi alınır, maçlar **%100'e en yakından** başlayarak sıralanır ve Nesine "
             "oranı hedefe ulaşana kadar eklenir." if args.yontem == "guvenli" else
             "Yöntem: toplam Nesine oranı **en az** hedef olan (daha yüksek olabilir, altı asla) kuponlar arasında "
             "**birleşik tutma olasılığı en yüksek** olan.")
          + " Oranlar maç saatine kadar değişebilir; oynamadan önce Nesine'de kontrol edin.", ""]
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
        g = c.get("guard") or {}
        if g:
            md += ["", f"**{g['mode'].capitalize()} kontrolü geçti** — {g['honest']}."
                   + ("" if not g["warnings"] else " Uyarılar: " + "; ".join(g["warnings"]))]
        md += ["", f"Kuponun tutma olasılığı %{c['probability'] * 100:.1f} · **beklenen değer (EV) %{100 * (c.get('ev') or 0.0):+.1f}**: "
                   "düşük oranlı bir bacak bile kesin değildir (1,20 oranlı seçim globalde ~%75-80 ihtimal demektir).", ""]
        if (c.get("ev") or 0.0) < -0.25:
            md += [f"> ⚠ **KASA KORUMA UYARISI (Yüksek Bileşik Nesine Marjı):** Bu düz kombinenin beklenen getirisi "
                   f"**%{100 * (c['ev']):+.1f}**. Sermayeyi korumak için tüm parayı düz kombineye yatırmak yerine "
                   "aşağıdaki tek-bacak sigortalı sistemi veya 2–3 maçlı düşük-marjlı değer kuponunu tercih edin.", ""]
        ins = c.get("insured_system_100tl")
        if ins:
            sz_s = ",".join(str(x) for x in ins["sizes"])
            lo_m, hi_m = ins["one_miss_payout_range"]
            md += [f"- **100 TL Tek-Bacak Sigorta Alternatifi (`Sistem {sz_s}`):** {ins['n_cols']} kolon × {ins['stake_per_col']:.0f} TL = "
                   f"**{ins['total_cost']:.0f} TL** · En az {len(c['legs']) - 1}/{len(c['legs'])} isabet: **%{100 * ins['p_at_least_n_minus_1']:.1f}** "
                   f"(1 firede **{lo_m:.0f}–{hi_m:.0f} TL** kurtarma vs düzde 0 TL · tam isabette **{ins['max_payout']:.0f} TL**)", ""]
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
    d = AI_AREA / args.tarih  # coupons live only in this AI's own folder (user rule)
    d.mkdir(parents=True, exist_ok=True)
    base = d / (f"kupon_{args.hedef:g}x_{stamp}.json" if args.aile == "karma" else f"kupon_{args.hedef:g}x_{args.aile}_{stamp}.json")
    base.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if args.yeni_set:
        (d / SET_FILE).write_text(now.isoformat(timespec="seconds") + "\n", encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps({"target": args.hedef, "family": args.aile, "mode": args.mod,
                                                     "created": now.isoformat(timespec="seconds"),
                                                     "coupons": coupons}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {base.with_suffix('.md').relative_to(DAILY.parents[1])}")
    try:  # keep this AI's mac_tahminleri.csv in step with the new coupons
        import ai_tahmin  # noqa: PLC0415
        ai_tahmin.export(args.tarih, matches)  # this run's own analysis, not the shared report files
    except Exception as exc:
        raise RuntimeError(f"Kupon kaydedildi ancak CSV güncellenemedi: {base}") from exc
    return base.with_suffix(".json")


if __name__ == "__main__":
    main()
