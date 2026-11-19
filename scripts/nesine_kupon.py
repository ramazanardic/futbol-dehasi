"""Nesine kuponu: olasılıklar global keskin fiyattan, toplam oran Nesine oranlarından.

    python scripts/nesine_kupon.py --hedef 10
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
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import DAILY, MAX_PLAUSIBLE_EV, TSI, analyze_day  # noqa: E402

SHARP_SOURCES = ("Pinnacle", "Smarkets", "Betfair")
RES = 0.002  # log-odds bucket width


def candidates(matches: list[dict], now: dt.datetime, min_odds: float, min_prob: float, allow_espn: bool) -> list[list[dict]]:
    """Per match: non-dominated legs (higher Nesine odds AND higher global probability dominates)."""
    pools = []
    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        if not allow_espn and not m["reference"].startswith(SHARP_SOURCES):
            continue
        if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now + dt.timedelta(minutes=5):
            continue  # started or about to start
        legs = []
        for s in m["selections"]:
            if s["odds"] < min_odds or s["fair_prob"] < min_prob or s["ev"] > MAX_PLAUSIBLE_EV:
                continue
            legs.append({"code": m["code"], "kickoff": m["kickoff"], "league": m["league"], "match": f"{m['home']} - {m['away']}",
                         "market": s["market"], "selection": s["selection"], "odds": s["odds"], "p": s["fair_prob"],
                         "ev": s["ev"], "mbs": int(s["mbs"] or 1), "reference": m["reference"].split(" ")[0]})
        legs.sort(key=lambda x: (-x["odds"], -x["p"]))
        front, best_p = [], -1.0
        for leg in legs:  # descending odds: keep a leg only if no higher-odds leg has a higher probability
            if leg["p"] > best_p + 1e-12:
                front.append(leg)
                best_p = leg["p"]
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
                val = lp + math.log(leg["p"])
                old = new.get(key)
                # Keep the more probable state; on (near) ties keep the one with the higher odds.
                if old is None or val > old[0] + 1e-12 or (abs(val - old[0]) <= 1e-12 and nlo > old[1]):
                    new[key] = (val, nlo, legs + (leg,))
        states = new
    finals = [(lp, legs) for (n, mbs, b), (lp, lo, legs) in states.items() if b == tb and n >= max(mbs, min_legs, 1)]
    if not finals:
        return None
    lp, legs = max(finals, key=lambda x: (x[0], -len(x[1])))
    odds = math.prod(x["odds"] for x in legs)
    p = math.exp(lp)
    return {"legs": list(sorted(legs, key=lambda x: x["kickoff"])), "nesine_odds": round(odds, 2), "probability": p,
            "global_fair_odds": round(1 / p, 2), "ev": p * odds - 1.0, "min_mbs": max(x["mbs"] for x in legs)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hedef", type=float, required=True, help="Hedef toplam Nesine oranı (ör. 10)")
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--adet", type=int, default=3, help="Kaç alternatif kupon (maçlar birbirinden ayrı)")
    ap.add_argument("--max-mac", type=int, default=8)
    ap.add_argument("--min-mac", type=int, default=1, help="Kupondaki en az maç sayısı (kombine için ör. 3)")
    ap.add_argument("--min-oran", type=float, default=1.15, help="Bacak başına en düşük Nesine oranı")
    ap.add_argument("--min-olasilik", type=float, default=0.0, help="Bacak başına en düşük global olasılık")
    ap.add_argument("--espn", action="store_true", help="ESPN (keskin olmayan) referanslı maçları da kullan")
    args = ap.parse_args()

    matches, _, _ = analyze_day(dt.date.fromisoformat(args.tarih), verbose=False)
    now = dt.datetime.now(TSI)
    pools = candidates(matches, now, args.min_oran, args.min_olasilik, args.espn)
    print(f"{sum(1 for m in matches if m.get('status') == 'fiyatlandı')} maç global fiyatlı; {len(pools)} maç kupona uygun "
          f"(başlamamış, {'ESPN dahil' if args.espn else 'yalnız keskin referans'}).")

    coupons, used = [], set()
    for _ in range(args.adet):
        c = best_coupon([p for p in pools if p[0]["code"] not in used], args.hedef, args.max_mac, args.min_mac)
        if c is None:
            break
        coupons.append(c)
        used |= {leg["code"] for leg in c["legs"]}

    stamp = now.strftime("%H%M")
    md = [f"# {args.tarih} — Nesine {args.hedef:g} oranlık kupon ({now:%H:%M} TSİ)", "",
          "Olasılıklar global keskin fiyattan (Pinnacle / Smarkets / Betfair borsası), oranlar Nesine'den. "
          "Kupon, hedef Nesine oranına ulaşanlar arasında **tutma olasılığı en yüksek** olandır. Oranlar maç saatine kadar "
          "değişebilir; oynamadan önce Nesine'de kontrol edin.", ""]
    if not coupons:
        md.append("_Bu hedefe uygun kupon kurulamadı (yeterli keskin referanslı, başlamamış maç yok)._")
    for i, c in enumerate(coupons, 1):
        md += [f"## Kupon {i}: Nesine oranı **{c['nesine_odds']:.2f}** · tutma olasılığı **%{c['probability'] * 100:.1f}** "
               f"· global adil oranı {c['global_fair_odds']:.2f} · beklenen değer {c['ev']:+.1%} · en az {c['min_mbs']} maç (MBS)", "",
               "| Saat | Maç | Pazar | Seçim | Nesine oranı | Global olasılık | Global adil oran | MBS | Referans |",
               "|---|---|---|---|---|---|---|---|---|"]
        for leg in c["legs"]:
            md.append(f"| {leg['kickoff'][11:]} | {leg['match']} | {leg['market']} | {leg['selection']} | {leg['odds']:.2f} | "
                      f"%{leg['p'] * 100:.1f} | {1 / leg['p']:.2f} | {leg['mbs']} | {leg['reference']} |")
        md.append("")
    md += ["> Beklenen değer = tutma olasılığı × Nesine oranı − 1. Negatifse uzun vadede kaybettirir; araç bu kaybı en aza "
           "indiren bacakları seçer ama kazanç garanti etmez."]
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
