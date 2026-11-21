"""Kombine politikası için örneklem-dışı kanıt (gerçek sonuçlarla, uydurma sayı yok).

    python scripts/kombine_dogrulama.py            # → docs/research/kombine_dogrulama_2026_11_21.md (+ .json)

Deney A — marj bileşikleşmesi (data/matches.csv, 2021-07+): her gün aynı günün maçlarından rastgele k bacaklı
kuponlar; bacak = piyasa favorisi (marjsız olasılık ≥ %55, oran ≥ 1.20), oran = arşivdeki ortalama oran (marj ≈ %6).
"Önceki alışkanlık": EV'ye bakmadan güvenli görünen favorileri biriktirmek.

Deney B — politika (data/tipsaudit.csv, 2026-06 – 2026-10): olasılık = Pinnacle AÇILIŞ oranının marjsız hâli
(maç öncesi bilinir), oran = en iyi yumuşak büro. "Önce": aynı kurallarla EV'ye bakmadan favoriler; "sonra":
accumulator_policy (bacak EV ≥ eşik, en çok k bacak, maç başına tek bacak, aynı maç tek kuponda).

Güven aralıkları gün-kümeli bootstrap (aynı günün kuponları bağımlıdır).
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.markets.devig import devig_batch  # noqa: E402
from quantfoot.strategy.accumulator_policy import Leg, PolicyConfig, build_daily_portfolio  # noqa: E402

RNG = np.random.default_rng(20261121)
OUT = ROOT / "docs" / "research"


def _boot_roi(day_ids: np.ndarray, payout: np.ndarray, n_boot: int = 1000) -> tuple[float, float, float]:
    roi = float(payout.mean() - 1.0)
    days = np.unique(day_ids)
    idx = {d: np.flatnonzero(day_ids == d) for d in days}
    sums = np.array([payout[idx[d]].sum() for d in days])
    cnts = np.array([len(idx[d]) for d in days])
    bs = []
    for _ in range(n_boot):
        s = RNG.integers(0, len(days), len(days))
        bs.append(sums[s].sum() / cnts[s].sum() - 1.0)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return roi, float(lo), float(hi)


def _random_coupons(day_legs: dict, k: int, per_day: int = 30) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    days, pay, ev = [], [], []
    for d, legs in day_legs.items():
        if len(legs) < k:
            continue
        for _ in range(per_day):
            pick = RNG.choice(len(legs), k, replace=False)
            o = np.prod([legs[i][0] for i in pick])
            p = np.prod([legs[i][1] for i in pick])
            won = all(legs[i][2] for i in pick)
            days.append(d)
            pay.append(o if won else 0.0)
            ev.append(p * o - 1)
    return np.array(days), np.array(pay), np.array(ev)


def experiment_a() -> dict:
    m = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False,
                    usecols=["MatchDate", "HomeTeam", "AwayTeam", "OddHome", "OddDraw", "OddAway", "FTResult"])
    m = m[m.MatchDate >= "2021-07-01"].dropna(subset=["OddHome", "OddDraw", "OddAway", "FTResult"])
    odds = m[["OddHome", "OddDraw", "OddAway"]].to_numpy(float)
    ok = (odds > 1.0).all(1)
    m, odds = m[ok], odds[ok]
    fair = devig_batch(odds, method="power")
    res = m.FTResult.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    j = fair.argmax(1)
    pf = fair[np.arange(len(m)), j]
    of = odds[np.arange(len(m)), j]
    keep = (pf >= 0.55) & (of >= 1.20)
    day_legs: dict = {}
    for d, o, p, w in zip(m.MatchDate.to_numpy()[keep], of[keep], pf[keep], (res == j)[keep]):
        day_legs.setdefault(d, []).append((float(o), float(p), bool(w)))
    margin = float(np.median(1 / odds[:, 0] + 1 / odds[:, 1] + 1 / odds[:, 2] - 1))
    rows = []
    for k in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        days, pay, _ = _random_coupons(day_legs, k)
        roi, lo, hi = _boot_roi(days, pay)
        rows.append({"k": k, "n": int(len(pay)), "hit": float((pay > 0).mean()), "roi": roi, "lo": lo, "hi": hi})
    return {"n_legs_pool": int(keep.sum()), "median_margin": margin, "rows": rows}


def experiment_b(min_ev: float = 0.025) -> dict:
    t = pd.read_csv(ROOT / "data" / "tipsaudit.csv")
    sides = ["home", "draw", "away"]
    pin = t[[f"pin_open_{s}" for s in sides]].to_numpy(float)
    soft = t[[f"best_soft_{s}" for s in sides]].to_numpy(float)
    ok = np.isfinite(pin).all(1) & np.isfinite(soft).all(1) & (pin > 1).all(1) & t.result.isin(["1", "X", "2"]).to_numpy()
    t, pin, soft = t[ok].reset_index(drop=True), pin[ok], soft[ok]
    p = devig_batch(pin, method="power")
    res = t.result.map({"1": 0, "X": 1, "2": 2}).to_numpy()
    day = t.kickoff_utc.str[:10].to_numpy()
    out: dict = {"n_matches": int(len(t)), "min_ev": min_ev}
    # Önce: favori (p ≥ .55, oran ≥ 1.20), EV'ye bakılmadan
    j = p.argmax(1)
    pf, of = p[np.arange(len(t)), j], soft[np.arange(len(t)), j]
    keep = (pf >= 0.55) & (of >= 1.20) & (of <= 3.5)
    day_legs: dict = {}
    for d, o, q, w in zip(day[keep], of[keep], pf[keep], (res == j)[keep]):
        day_legs.setdefault(d, []).append((float(o), float(q), bool(w)))
    before = []
    for k in (1, 2, 3, 4, 5, 6, 7):
        days, pay, ev = _random_coupons(day_legs, k)
        roi, lo, hi = _boot_roi(days, pay)
        before.append({"k": k, "n": int(len(pay)), "hit": float((pay > 0).mean()), "mean_ev": float(ev.mean()),
                       "roi": roi, "lo": lo, "hi": hi})
    out["before"] = before
    # Sonra: politika motoru (her gün aynı maçı tekrar etmeyen en çok 3 kupon)
    after = []
    for max_legs in (1, 2, 3, 4):
        cfg = PolicyConfig(min_leg_ev=min_ev, min_coupon_ev=min_ev, max_legs=max_legs, max_coupon_odds=60.0,
                           max_plausible_leg_ev=0.25)
        days, pay, legs_n, evs = [], [], [], []
        for d in np.unique(day):
            idx = np.flatnonzero(day == d)
            cands = [Leg(str(t.id[i]), s, float(soft[i, c]), float(p[i, c]))
                     for i in idx for c, s in enumerate(("1", "X", "2")) if soft[i, c] <= 3.5]
            for cp, _stake in build_daily_portfolio(cands, bankroll=1000.0, n_coupons=3, cfg=cfg):
                won = all(res[int(np.flatnonzero(t.id.astype(str).to_numpy() == l.match_id)[0])] == "1X2".index(l.selection)
                          for l in cp.legs)
                days.append(d)
                pay.append(cp.odds if won else 0.0)
                legs_n.append(cp.n_legs)
                evs.append(cp.ev)
        days, pay = np.array(days), np.array(pay)
        roi, lo, hi = _boot_roi(days, pay)
        after.append({"max_legs": max_legs, "n": int(len(pay)), "avg_legs": float(np.mean(legs_n)),
                      "hit": float((pay > 0).mean()), "mean_ev": float(np.mean(evs)), "roi": roi, "lo": lo, "hi": hi})
    out["after"] = after
    return out


def main() -> None:
    a = experiment_a()
    b = experiment_b()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "kombine_dogrulama_2026_11_21.json").write_text(json.dumps({"A": a, "B": b}, indent=2, ensure_ascii=False))
    pct = lambda x: f"{x:+.1%}"  # noqa: E731
    md = ["# Kombine politikası — örneklem-dışı doğrulama (21 Kasım 2026)", "",
          "Üretim: `python scripts/kombine_dogrulama.py`. Sonuçlar gerçek maç sonuçlarıyla; güven aralığı gün-kümeli bootstrap.", "",
          f"## A. Marj bileşikleşmesi — `data/matches.csv` 2021-07+ ({a['n_legs_pool']} favori bacak, medyan 1X2 marjı {a['median_margin']:.1%})", "",
          "Bacak: marjsız olasılığı ≥ %55 ve oranı ≥ 1.20 olan favori, ortalama piyasa oranından. Aynı günden rastgele k maç.", "",
          "| Bacak | Kupon | Tutma | ROI (%95 GA) |", "|---|---|---|---|"]
    md += [f"| {r['k']} | {r['n']} | {r['hit']:.1%} | {pct(r['roi'])} ({pct(r['lo'])} – {pct(r['hi'])}) |" for r in a["rows"]]
    md += ["", f"## B. Politika — `data/tipsaudit.csv` ({b['n_matches']} maç, olasılık = Pinnacle açılışı marjsız, oran = en iyi yumuşak büro)", "",
           "**Önce (EV'ye bakmadan favori biriktirmek, aynı günden rastgele k maç):**", "",
           "| Bacak | Kupon | Tutma | Ortalama ex-ante EV | ROI (%95 GA) |", "|---|---|---|---|---|"]
    md += [f"| {r['k']} | {r['n']} | {r['hit']:.1%} | {pct(r['mean_ev'])} | {pct(r['roi'])} ({pct(r['lo'])} – {pct(r['hi'])}) |" for r in b["before"]]
    md += ["", f"**Sonra (accumulator_policy: bacak EV ≥ {b['min_ev']:.1%}, günde en çok 3 kupon, aynı maç tek kuponda):**", "",
           "| En çok bacak | Kupon | Ort. bacak | Tutma | Ortalama ex-ante EV | ROI (%95 GA) |", "|---|---|---|---|---|---|"]
    md += [f"| {r['max_legs']} | {r['n']} | {r['avg_legs']:.2f} | {r['hit']:.1%} | {pct(r['mean_ev'])} | {pct(r['roi'])} ({pct(r['lo'])} – {pct(r['hi'])}) |" for r in b["after"]]
    md += ["", "Çekinceler: tipsaudit'teki 'en iyi yumuşak oran' ~17 büronun en iyisidir (tek büroda yok) ve alınma anı "
           "bilinmiyor; Nesine marjı bu bürolardan yüksektir, dolayısıyla gerçek Nesine ROI'si daha düşük olur. "
           "Deney B'deki ROI'ler 5 aylık tek bir dönemdir."]
    (OUT / "kombine_dogrulama_2026_11_21.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
