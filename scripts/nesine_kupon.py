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
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402
from quantfoot.strategy.coupon_builder import _conflicting_selections  # noqa: E402

SHARP_SOURCES = ("Pinnacle", "Smarkets", "Matchbook", "Betfair")
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


def leg_sigma(name: str, direct: bool, reference: str, researched: bool, flagged: bool) -> float:
    """Uncertainty (probability points) of a leg's probability, from what the calibration work measured:
    a direct exchange quote is within ~1 pt, a goal-model derivative ~2-3 pts, half-time / second-half
    model markets less certain still; a single exchange, missing research or a team-news flag widen it."""
    if direct:
        sigma = 0.010
    elif any(t in name for t in HALF_TOKENS):
        sigma = 0.035
    else:
        sigma = 0.025
    if "+" not in reference:  # one exchange instead of two agreeing ones
        sigma += 0.005
    if not researched:
        sigma += 0.010
    if flagged:
        sigma += 0.020
    return sigma


def candidates(matches: list[dict], now: dt.datetime, min_odds: float, min_prob: float, allow_espn: bool,
               direct_only: bool = False) -> list[list[dict]]:
    """Per match: non-dominated legs (higher Nesine odds AND higher global probability dominates)."""
    pools = []
    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        if not allow_espn and not m["reference"].startswith(SHARP_SOURCES):
            continue
        if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now + dt.timedelta(minutes=5):
            continue  # started or about to start
        if m.get("research_block"):
            continue  # important absence announced after the global price was fetched
        age = price_age_hours(m, now)
        if age is not None and age > MAX_PRICE_AGE_H:
            continue  # stale global price (GitHub's scheduler skipped runs)
        legs = []
        context = match_context(m)
        researched = bool((m.get("research") or {}).get("teams") or (m.get("research") or {}).get("user_absences"))
        flagged = bool((m.get("research") or {}).get("flags"))
        for s in m["selections"]:
            if s["odds"] < min_odds or s["fair_prob"] < min_prob or s["ev"] > MAX_PLAUSIBLE_EV:
                continue
            if direct_only and not s.get("direct"):
                continue  # model-derived price: no direct global quote for this selection
            if not s.get("direct") and s.get("name", "").startswith("İY/MS"):
                continue  # model HT/FT is the weakest derived market (calibration: ~3x the error); direct quotes only
            legs.append({"code": m["code"], "kickoff": m["kickoff"], "league": m["league"], "match": f"{m['home']} - {m['away']}",
                         "market": s["market"], "selection": s["selection"], "odds": s["odds"], "p": s["fair_prob"],
                         "ev": s["ev"], "mbs": int(s["mbs"] or 1), "reference": m["reference"].split(" (")[0],
                         "direct": bool(s.get("direct")), "context": context, "key": s.get("key"),
                         "name": s.get("name", ""), "researched": researched})
            sig = leg_sigma(s.get("name", ""), bool(s.get("direct")), m["reference"], researched, flagged)
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


def recheck_odds(coupons: list[dict]) -> list[str]:
    """Fetch the Nesine bulletin again and compare every leg's odds; update legs and coupon totals in place.
    Returns human-readable change notes (empty = all odds unchanged)."""
    current: dict[int, dict[str, float]] = {}
    for e in parse_bulletin(fetch_bulletin()):
        current[int(e.code)] = {selection_key(s): s.odds for s in e.selections}
    notes = []
    for i, c in enumerate(coupons, 1):
        for leg in c["legs"]:
            now_odds = current.get(int(leg["code"]), {}).get(leg.get("key"))
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
    ap.add_argument("--espn", action="store_true", help="ESPN (keskin olmayan) referanslı maçları da kullan")
    ap.add_argument("--ortak-mac", action="store_true",
                    help="Kuponlar aynı maçı paylaşabilir; aynı bahis ve birbirini kesin yatıran bahis yasak")
    ap.add_argument("--dogrudan", action="store_true", help="Yalnızca doğrudan global fiyatı olan seçimler (model türevi yok)")
    args = ap.parse_args()

    print(f"Global veri: {refresh_global_data()}")
    matches, _, _ = analyze_day(dt.date.fromisoformat(args.tarih), verbose=False)
    now = dt.datetime.now(TSI)
    min_prob = args.min_olasilik if args.min_olasilik is not None else (0.60 if args.yontem == "guvenli" else 0.55)
    pools = candidates(matches, now, args.min_oran, min_prob, args.espn, args.dogrudan)
    print(f"{sum(1 for m in matches if m.get('status') == 'fiyatlandı')} maç global fiyatlı; {len(pools)} maç kupona uygun "
          f"(başlamamış, {'ESPN dahil' if args.espn else 'yalnız keskin referans'}).")
    stale = sum(1 for m in matches if m.get("status") == "fiyatlandı" and (price_age_hours(m, now) or 0) > MAX_PRICE_AGE_H)
    if stale:
        print(f"⚠ {stale} maçın global fiyatı {MAX_PRICE_AGE_H:g} saatten eski: kupona alınmadı (GitHub verisi yenilenmeli).")

    max_legs = args.max_mac or MAX_LEGS
    coupons, used = [], set()
    for _ in range(args.adet):
        chosen = [leg for c in coupons for leg in c["legs"]]
        free = drop_conflicts(pools, chosen) if args.ortak_mac else [p for p in pools if p[0]["code"] not in used]
        c = (safest_first_coupon(free, args.hedef, max_legs, partial=not coupons) if args.yontem == "guvenli"
             else best_coupon(free, args.hedef, max_legs, args.min_mac))
        if c is None:
            break
        coupons.append(c)
        used |= {leg["code"] for leg in c["legs"]}

    change_notes = recheck_odds(coupons) if coupons else []
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


if __name__ == "__main__":
    main()
