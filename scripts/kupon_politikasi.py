"""Kupon / kasa politikası: oynamadan önce EV, marj maliyeti, aynı maç maruziyeti, pay dağıtımı ve risk.
Hiçbir zaman bahis yapmaz. Olasılıklar keskin/marjsız kaynaktan gelmelidir (Nesine değil).

    # verilen kuponları denetle + kasayı dağıt + risk
    python scripts/kupon_politikasi.py --bacaklar kupon.csv --kasa 250 --gunluk-limit-oran 1.0 --kupon-limit-oran 0.2
    # adaylardan en çok 5 kupon kur (aynı maç tek kuponda) + dağıt
    python scripts/kupon_politikasi.py --adaylar adaylar.csv --kasa 250 --adet 5
    # hedef katlama: P(gün sonu kasa ≥ 10 × 250) en yüksek plan, 100 TL canlıya ayrılır
    python scripts/kupon_politikasi.py --adaylar adaylar.csv --kasa 250 --hedef-kat 10 --canli-rezerv 100
    # geçmiş kuponlarda çift maruziyet / bacak sayısı
    python scripts/kupon_politikasi.py --gecmis nesine_kupon_gecmisi.csv

CSV sütunları: match_id,selection,odds,prob[,prob_sd][,coupon]  (odds = Nesine oranı, prob = adil olasılık)
--canli-rezerv verilirse tahminler/<QUANTFOOT_AI>/canli/rezerv.json'a yazılır; canli_tarama.py payları buradan hesaplar.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from quantfoot import settings as S  # noqa: E402
from quantfoot.strategy.accumulator_policy import (  # noqa: E402
    CouponEvaluation,
    ExposureBook,
    Leg,
    PolicyConfig,
    allocate_budget,
    build_daily_portfolio,
    check_coupon,
    plan_metrics,
    risk_report,
    search_target_plan,
)


def audit_history(path: Path) -> str:
    g = pd.read_csv(path)
    per = g.groupby("coupon_id").size()
    c = g.groupby("match").coupon_id.nunique()
    dup = c[c > 1].sort_values(ascending=False)
    lines = [f"Kupon: {per.size}, bacak: {len(g)}, kupon başı bacak ortalama {per.mean():.1f} (en çok {per.max()})",
             f"Birden çok kupona giren maç: {len(dup)} / {len(c)}"]
    lines += [f"  {m}: {n} kupon" for m, n in dup.head(10).items()]
    over = int((per > PolicyConfig().max_legs).sum())
    lines.append(f"Politika tavanını ({PolicyConfig().max_legs} bacak) aşan kupon: {over}")
    return "\n".join(lines)


def read_legs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = {"match_id", "selection", "odds", "prob"} - set(df.columns)
    if missing:
        raise SystemExit(f"{path}: eksik sütun {sorted(missing)}")
    return df


def to_legs(df: pd.DataFrame) -> list[Leg]:
    return [Leg(str(r.match_id), str(r.selection), float(r.odds), float(r.prob),
                float(getattr(r, "prob_sd", 0.0) or 0.0)) for r in df.itertuples()]


def describe(ev: CouponEvaluation, name: str) -> list[str]:
    out = [f"== {name}: {ev.n_legs} bacak, oran {ev.odds:.2f}, tutma %{ev.prob * 100:.1f}, EV {ev.ev:+.1%}, "
           f"marj maliyeti %{ev.margin_drag * 100:.1f}"]
    out += [f"   {l.match_id} {l.selection}: oran {l.odds:.2f}, p %{l.prob * 100:.1f}, EV {l.ev:+.1%}" for l in ev.legs]
    return out


def risk_lines(coupons, stakes, kasa: float) -> list[str]:
    if sum(stakes) <= 0:
        return ["Risk: pay yok → risk yok."]
    r = risk_report(coupons, stakes, kasa)
    s = risk_report(coupons, stakes, kasa, prob_haircut=0.05)
    lines = [f"Toplam pay {r['stake_total']:.0f} TL (kasanın %{r['stake_frac'] * 100:.0f}'i).",
             f"Bugün: hepsini kaybetme olasılığı %{r['p_lose_all_today'] * 100:.1f}, zarar olasılığı %{r['p_loss_today'] * 100:.1f}, "
             f"beklenen kâr {r['exp_pnl_today']:+.1f} TL, kötü %5 senaryo {r['p5_pnl_today']:+.0f} TL.",
             f"Bu kasa oranlarıyla 30 gün tekrarlanırsa (model olasılıkları): medyan kasa {r['median_end']:.0f} TL, "
             f"kasanın yarıya düşme olasılığı %{r['p_half'] * 100:.0f}, batma (en küçük payı karşılayamama) %{r['p_ruin'] * 100:.0f}, "
             f"medyan en büyük düşüş %{r['median_max_dd'] * 100:.0f}.",
             f"Stres (her bacak olasılığı %5 düşük): medyan kasa {s['median_end']:.0f} TL, batma %{s['p_ruin'] * 100:.0f}."]
    if r["log_growth"] < 0:
        lines.append("UYARI: Bu dağıtım uzun vadede kasayı küçültür (beklenen log-büyüme negatif = aşırı bahis). "
                     "Kelly payları daha küçük ama kasayı büyüten paylardır.")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bacaklar", type=Path)
    ap.add_argument("--adaylar", type=Path)
    ap.add_argument("--gecmis", type=Path)
    ap.add_argument("--kasa", type=float, default=0.0)
    ap.add_argument("--gunluk-limit-oran", type=float, default=S.STAKE_DAILY_FRAC)
    ap.add_argument("--kupon-limit-oran", type=float, default=S.STAKE_COUPON_FRAC)
    ap.add_argument("--max-mac", type=int, default=PolicyConfig().max_legs)
    ap.add_argument("--min-ev", type=float, default=S.MIN_COUPON_EV)
    ap.add_argument("--adet", type=int, default=5)
    ap.add_argument("--kelly", action="store_true", help="bütçeyi doldurma; yalnız kesirli Kelly payı")
    ap.add_argument("--hedef-kat", type=float, default=0.0)
    ap.add_argument("--canli-rezerv", type=float, default=0.0)
    args = ap.parse_args()
    if args.gecmis:
        print(audit_history(args.gecmis))
        return
    if not (args.bacaklar or args.adaylar):
        ap.error("--bacaklar, --adaylar ya da --gecmis gerekli")
    kasa = args.kasa or 1.0
    if args.canli_rezerv and os.environ.get("QUANTFOOT_AI"):
        from quantfoot.paths import ai_area
        d = ai_area() / "canli"
        d.mkdir(parents=True, exist_ok=True)
        (d / "rezerv.json").write_text(json.dumps({"canli_rezerv_tl": args.canli_rezerv, "kasa_tl": args.kasa}))
    oyun_kasasi = max(0.0, kasa - args.canli_rezerv)
    cfg = PolicyConfig(max_legs=args.max_mac, min_coupon_ev=args.min_ev, max_coupon_odds=1000.0,
                       max_stake_frac=args.kupon_limit_oran * kasa / oyun_kasasi if oyun_kasasi else 0.0,
                       max_daily_frac=args.gunluk_limit_oran * min(1.0, oyun_kasasi / kasa) * kasa / oyun_kasasi if oyun_kasasi else 0.0)
    if args.bacaklar:
        df = read_legs(args.bacaklar)
        groups = df.groupby("coupon", sort=False) if "coupon" in df.columns else [("kupon", df)]
        book = ExposureBook(oyun_kasasi, cfg)
        coupons, names = [], []
        for name, part in groups:
            ev = check_coupon(to_legs(part), cfg)
            c = book.conflicts(ev.legs)
            if c:
                ev.reasons.append("aynı maç başka kuponda (korelasyonlu maruziyet): " + ", ".join(c))
            for leg in ev.legs:
                book.match_count[leg.match_id] = book.match_count.get(leg.match_id, 0) + 1
            coupons.append(ev)
            names.append(str(name))
    else:
        cands = to_legs(read_legs(args.adaylar))
        coupons = [c for c, _ in build_daily_portfolio(cands, oyun_kasasi, n_coupons=args.adet, cfg=cfg)]
        names = [f"kupon {i + 1}" for i in range(len(coupons))]
    stakes = allocate_budget(coupons, oyun_kasasi, cfg, fill_budget=not args.kelly)
    kelly = allocate_budget(coupons, oyun_kasasi, cfg, fill_budget=False)
    print(f"Kasa {kasa:.0f} TL · canlı rezerv {args.canli_rezerv:.0f} TL · maç öncesi bütçe "
          f"{min(args.gunluk_limit_oran * kasa, oyun_kasasi):.0f} TL · kupon başı en çok {args.kupon_limit_oran * kasa:.0f} TL")
    for ev, name, st, kl in zip(coupons, names, stakes, kelly):
        print("\n".join(describe(ev, name)))
        if st > 0:
            print(f"   KARAR: OYNANABİLİR — önerilen pay {st:.0f} TL (yalnız kesirli Kelly: {kl:.0f} TL)")
        else:
            print("   KARAR: OYNAMA" if ev.reasons or ev.ev < cfg.min_coupon_ev else "   KARAR: pay 5 TL altında → oynama")
            for w in ev.reasons:
                print(f"   - {w}")
    if not any(s > 0 for s in stakes):
        print("\n+EV kupon yok → önerilen toplam pay 0 TL.")
    else:
        print("\nRisk (Monte Carlo, ortak bacaklar tek değişken):")
        print("\n".join("  " + x for x in risk_lines(coupons, stakes, kasa)))
    if args.hedef_kat and args.adaylar:
        target = args.hedef_kat * kasa
        plan = search_target_plan(cands, kasa, args.hedef_kat, reserve=args.canli_rezerv, cfg=cfg)
        print(f"\n## Hedef katlama: {args.hedef_kat:g} kat → gün sonu kasa ≥ {target:.0f} TL "
              f"(bu modda kupon başı tavan uygulanmaz; bütçe = kasa − canlı rezerv)")
        if plan is None:
            print("Uygun +EV kupon yok → hedef planı kurulamaz, pay 0 TL.")
            return
        for i, (c, st) in enumerate(zip(plan.coupons, plan.stakes), 1):
            print("\n".join(describe(c, f"hedef kupon {i} — pay {st:.0f} TL")))
        print(f"Hedefe ulaşma olasılığı %{plan.p_reach * 100:.1f} (üst sınır E[kasa]/hedef = %{plan.markov_bound * 100:.1f}); "
              f"bütün kupon parasını kaybetme %{plan.p_lose_all * 100:.1f}; beklenen gün sonu kasa {plan.exp_final:.0f} TL.")
        kp = plan_metrics(coupons, kelly, kasa, target, args.canli_rezerv, n_sims=40000)
        print(f"Karşılaştırma — kesirli Kelly planı (toplam {sum(kelly):.0f} TL): hedefe ulaşma %{kp.p_reach * 100:.1f}, "
              f"hepsini kaybetme %{kp.p_lose_all * 100:.1f}, beklenen kasa {kp.exp_final:.0f} TL.")
        print("Not: tek günde büyük kat hedefi, kasanın büyük kısmını kaybetme olasılığını da büyütür; Kelly planı "
              "hedefi nadiren tutturur ama kasayı korur.")


if __name__ == "__main__":
    main()
