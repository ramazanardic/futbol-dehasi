"""Results tracking for the Nesine predictions: settle, then measure whether the probabilities are right.

    python scripts/nesine_takip.py sonuc --date 2026-11-19   # fetch results, settle every recorded selection
    python scripts/nesine_takip.py rapor                      # cumulative hit-rate / calibration report

Inputs: reports/daily/<date>/takip_kayit.json (last pre-kick-off prediction per match, written by
nesine_global.py) and the coupons in reports/daily/<date>/kupon_*.json. Results (HT and 90-minute score) come
from Nesine's public live-score feed by event code, ESPN as fallback. Output: takip_sonuc.json per day and
reports/takip/ozet.md (calibration by probability band, by market family, direct vs model, the safest pick
per match, and every coupon built).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from nesine_global import DAILY, PREDICTIONS_FILE, TSI, _match  # noqa: E402

from quantfoot.data.match_research import espn_events  # noqa: E402
from quantfoot.data.nesine import fetch_results as fetch_nesine_results  # noqa: E402
from quantfoot.evaluation.settlement import fetch_espn_result, settle_selection  # noqa: E402

RESULTS_FILE = "takip_sonuc.json"
OUT = ROOT / "reports" / "takip" / "ozet.md"


def _event_ids(day: str, store: dict) -> dict[str, str]:
    """ESPN event id per recorded match: from the research, else by name/kick-off matching."""
    ids = {code: rec["espn_event"] for code, rec in store.items() if rec.get("espn_event")}
    missing = {c: r for c, r in store.items() if c not in ids}
    if missing:
        d = dt.date.fromisoformat(day)
        pool = [x for k in (-1, 0, 1) for x in espn_events((d + dt.timedelta(days=k)).strftime("%Y%m%d"))]
        for code, rec in missing.items():
            ev = type("E", (), {"home": rec["home"], "away": rec["away"],
                                "kickoff": dt.datetime.fromisoformat(rec["kickoff_iso"])})
            hit, _ = _match(ev, pool)
            if hit:
                ids[code] = hit["id"]
    return ids


def settle_day(day: str) -> dict:
    d = DAILY / day
    path = d / PREDICTIONS_FILE
    if not path.exists():
        return {}
    store = json.loads(path.read_text(encoding="utf-8"))
    res_path = d / RESULTS_FILE
    results = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    # Nesine's own results first (keyed by the same event code: covers every Nesine match), ESPN for the rest.
    d0 = dt.date.fromisoformat(day)
    nesine = fetch_nesine_results([d0.isoformat(), (d0 + dt.timedelta(days=1)).isoformat()])
    fetched = {c: nesine[int(c)] for c in store if not (results.get(c) or {}).get("completed") and int(c) in nesine}
    left = {c: r for c, r in store.items() if not (results.get(c) or {}).get("completed")
            and not (fetched.get(c) or {}).get("completed")}
    for code, eid in _event_ids(day, left).items():
        fetched[code] = fetch_espn_result(eid)
    for code, r in fetched.items():
        if not r.get("completed"):
            results[code] = {"completed": False, "status": r.get("status")}
            continue
        ht, ft = tuple(r["ht"]), tuple(r["ft90"])
        won = {}
        for name in store[code]["s"]:
            neg = name.startswith("DEĞİL(")
            base = name[6:-1] if neg else name
            try:
                v = settle_selection(base, ht, ft)
            except (ValueError, KeyError):
                v = None
            if v is not None:
                won[name] = (not v) if neg else v
        results[code] = {"completed": True, "ht": list(ht), "ft90": list(ft), "won": won}
    res_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    done = sum(1 for v in results.values() if v.get("completed"))
    print(f"{day}: {len(store)} maç kayıtlı, {done} sonuçlandı")
    return results


def _family(name: str) -> str:
    n = name.replace("DEĞİL(", "")
    if n.startswith("İY/MS"):
        return "İY/MS"
    if "&" in n:
        return "Kombine (A & B)"
    for prefix, fam in (("MS ", "Maç sonucu"), ("ÇŞ ", "Çifte şans"), ("KG", "Karşılıklı gol"), ("İY KG", "İY karşılıklı gol"),
                        ("2Y KG", "2Y karşılıklı gol"), ("İY ", "İlk yarı"), ("2Y ", "İkinci yarı"), ("Ev ", "Ev sahibi golleri"),
                        ("Dep ", "Deplasman golleri"), ("Hnd", "Handikap"), ("İlk Gol", "İlk gol"), ("Tek", "Tek/Çift"), ("Çift", "Tek/Çift")):
        if n.startswith(prefix):
            return fam
    if n[0].isdigit() and ("Üst" in n or "Alt" in n):
        return "Alt/Üst"
    if "Gol" in n:
        return "Gol aralığı"
    return "Diğer"


def _rows(days: list[str]) -> tuple[list[tuple], list[dict]]:
    """(p, won, family, direct, is_safest_pick) per settled selection, and settled coupons."""
    rows, coupons = [], []
    for day in days:
        d = DAILY / day
        if not (d / RESULTS_FILE).exists():
            continue
        store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8"))
        results = json.loads((d / RESULTS_FILE).read_text(encoding="utf-8"))
        for code, res in results.items():
            if not res.get("completed") or code not in store:
                continue
            sels = store[code]["s"]
            eligible = [(v[0], n) for n, v in sels.items() if v[1] >= 1.20 and n in res["won"]]
            safest = max(eligible)[1] if eligible else None
            for name, won in res["won"].items():
                p, odds, direct = sels[name]
                rows.append((p, bool(won), _family(name), bool(direct), name == safest, odds))
        for f in sorted(d.glob("kupon_*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            for c in data.get("coupons", []):
                status = []
                for leg in c["legs"]:
                    name = leg.get("name") or (leg.get("key") or "||").split("|")[1]
                    res = results.get(str(leg["code"])) or {}
                    status.append(res.get("won", {}).get(name) if res.get("completed") else None)
                if status and all(s is not None for s in status):
                    coupons.append({"file": f"{day}/{f.name}", "odds": c["nesine_odds"], "p": c["probability"],
                                    "won": all(status), "legs_won": sum(status), "legs": len(status)})
    return rows, coupons


LEDGER = ROOT / "reports" / "ledger"
NESINE_CACHE = LEDGER / "results_nesine.json"
ALIASES = {"+6 Gol": "6+ Gol"}


def _settle_leg(sel: str, res: dict | None) -> bool | None:
    if not res or not res.get("completed") or not sel or sel == "?":
        return None
    sel = ALIASES.get(sel, sel)
    neg = sel.startswith("DEĞİL(")
    base = sel[6:-1] if neg else sel
    try:
        v = settle_selection(base, tuple(res["ht"]), tuple(res["ft90"]))
    except (KeyError, ValueError):
        return None
    return None if v is None else (v != neg)


def _system_prob(code: str, sel: str, kickoff: str) -> float | None:
    """The system's last pre-kick-off probability for a played leg (betting day 07:00-07:00)."""
    try:
        ko = dt.datetime.fromisoformat(kickoff.strip())
    except ValueError:
        return None
    day = (ko.date() if ko.hour >= 7 else ko.date() - dt.timedelta(days=1)).isoformat()
    path = DAILY / day / PREDICTIONS_FILE
    if not code or not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8")).get(code) or {}
    v = (rec.get("s") or {}).get(sel)
    return v[0] if v else None


def played_coupons() -> list[dict]:
    """The user's real coupons (reports/ledger/placed_bets_*.csv), settled leg by leg: Nesine results by event
    code, ESPN by event id; legs the system cannot settle fall back to the result read off the Nesine screen."""
    import csv
    cache = json.loads(NESINE_CACHE.read_text(encoding="utf-8")) if NESINE_CACHE.exists() else {}
    by: dict = {}
    for f in sorted(LEDGER.glob("placed_bets_*.csv")):
        espn_path = LEDGER / f"results_{f.stem.replace('placed_bets_', '')}.json"
        espn_cache = json.loads(espn_path.read_text(encoding="utf-8")) if espn_path.exists() else {}
        rows = list(csv.DictReader(f.open(encoding="utf-8")))
        codes = {r.get("nesine_code") for r in rows if r.get("nesine_code")}
        need = sorted({r["kickoff"][:10] for r in rows if r.get("nesine_code") and r.get("kickoff")
                       and not (cache.get(r["nesine_code"]) or {}).get("completed")})
        if need:
            cache.update({str(k): v for k, v in fetch_nesine_results(need).items() if str(k) in codes})
        for r in rows:
            res = None
            if r.get("nesine_code"):
                res = cache.get(r["nesine_code"])
            elif r.get("event_id"):
                res = espn_cache.get(r["event_id"])
                if not (res or {}).get("completed"):
                    res = espn_cache[r["event_id"]] = fetch_espn_result(r["event_id"])
            won = _settle_leg(r.get("selection", ""), res)
            if won is None and r.get("leg_screen") in ("✓", "✗"):
                won = r["leg_screen"] == "✓"
            c = by.setdefault((f.stem, r["coupon_id"]), {
                "day": f.stem.replace("placed_bets_", "").replace("_", "-"), "id": r["coupon_id"], "placed": r["placed_at"],
                "stake": float(r["stake_tl"]) if r["stake_tl"] else None, "odds": float(r["total_odds"]) if r["total_odds"] else None,
                "n": int(r["n_legs"] or 0), "screen": r.get("coupon_screen") or "", "legs": []})
            if r.get("match"):
                c["legs"].append({"match": r["match"], "sel": r["selection"], "won": won,
                                  "p": _system_prob(r.get("nesine_code") or "", r["selection"], r.get("kickoff") or "")})
        if espn_cache:
            espn_path.write_text(json.dumps(espn_cache, ensure_ascii=False, indent=1), encoding="utf-8")
    if cache:
        NESINE_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    out = []
    for c in by.values():
        st = [leg["won"] for leg in c["legs"]]
        if False in st:
            c["status"] = "yattı"
        elif st and all(st) and len(st) >= c["n"]:
            c["status"] = "TUTTU"
        elif c["screen"] in ("KAZANDI", "yattı"):
            c["status"] = "TUTTU" if c["screen"] == "KAZANDI" else "yattı"
        else:
            c["status"] = "bekliyor"
        c["payout"] = round(c["stake"] * c["odds"], 2) if c["status"] == "TUTTU" and c["stake"] and c["odds"] else 0.0
        ps = [leg["p"] for leg in c["legs"]]
        c["p"] = float(np.prod(ps)) if ps and all(p is not None for p in ps) and len(ps) >= c["n"] else None
        out.append(c)
    return out


def _played_section() -> list[str]:
    coupons = played_coupons()
    if not coupons:
        return []
    done = [c for c in coupons if c["status"] != "bekliyor" and c["stake"]]
    lines = ["", "## Oynanan kuponlar (gerçek para)", "",
             "Kaynak: reports/ledger/placed_bets_*.csv (Nesine ekran görüntülerinden). Kazanç = tutar × toplam oran.", ""]
    if done:
        stake, pay = sum(c["stake"] for c in done), sum(c["payout"] for c in done)
        lines += [f"**Toplam:** {len(done)} kupon · yatırılan {stake:,.0f} TL · dönen {pay:,.2f} TL · net **{pay - stake:+,.2f} TL** · "
                  f"tutan {sum(c['status'] == 'TUTTU' for c in done)}", "",
                  "| Gün | Kupon | Yatırılan | Dönen | Net | Tutan |", "|---|---|---|---|---|---|"]
        for day in sorted({c["day"] for c in done}):
            b = [c for c in done if c["day"] == day]
            st, py = sum(c["stake"] for c in b), sum(c["payout"] for c in b)
            lines.append(f"| {day} | {len(b)} | {st:,.0f} TL | {py:,.2f} TL | {py - st:+,.2f} TL | {sum(c['status'] == 'TUTTU' for c in b)} |")
        lines += ["", "### Toplam orana göre", "", "| Oran | Kupon | Tutan | Yatırılan | Net |", "|---|---|---|---|---|"]
        for lo, hi, lab in ((0, 7, "≤ 7"), (7, 15, "7–15"), (15, 50, "15–50"), (50, 1e12, "> 50")):
            b = [c for c in done if c["odds"] and lo < c["odds"] <= hi]
            if b:
                st, py = sum(c["stake"] for c in b), sum(c["payout"] for c in b)
                lines.append(f"| {lab} | {len(b)} | {sum(c['status'] == 'TUTTU' for c in b)} | {st:,.0f} TL | {py - st:+,.2f} TL |")
    lines += ["", "### Kupon kupon", "",
              "| Gün | Kupon | Saat | Oran | Tutar | Sistemin ihtimali | Sonuç | Tutan bacak | Yatıran bacaklar |",
              "|---|---|---|---|---|---|---|---|---|"]
    for c in sorted(coupons, key=lambda c: (c["day"], c["placed"])):
        bad = "; ".join(f"{leg['match']} {leg['sel']}" for leg in c["legs"] if leg["won"] is False)
        prob = f"%{c['p'] * 100:.2f}" if c["p"] is not None else "-"
        lines.append(f"| {c['day']} | {c['id']} | {c['placed'][11:]} | {c['odds'] or '?'} | {c['stake'] or '?'} | {prob} | "
                     f"{c['status']} | {sum(1 for leg in c['legs'] if leg['won'])}/{c['n']} | {bad or '-'} |")
    legs = [(leg["p"], leg["won"]) for c in coupons for leg in c["legs"] if leg["p"] is not None and leg["won"] is not None]
    if legs:
        lines += ["", f"Sistemin olasılığı bilinen {len(legs)} oynanan bacak: ortalama tahmin "
                      f"%{np.mean([p for p, _ in legs]) * 100:.1f}, tutan %{np.mean([w for _, w in legs]) * 100:.1f}."]
    return lines


BASELINE_FILE = ROOT / "reports" / "research" / "score_baseline.json"


def score_baseline() -> dict:
    """Naive benchmark: historical frequency of every FT score, HT score and HT/FT result (data/matches.csv,
    2015 onwards). A prediction is only good if it beats this."""
    if BASELINE_FILE.exists():
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    import pandas as pd
    df = pd.read_csv(ROOT / "data" / "matches.csv", usecols=["MatchDate", "FTHome", "FTAway", "HTHome", "HTAway"]).dropna()
    df = df[df.MatchDate >= "2015-01-01"].astype({"FTHome": int, "FTAway": int, "HTHome": int, "HTAway": int})
    sign = lambda h, a: "1" if h > a else ("0" if h == a else "2")  # noqa: E731
    out = {"n": int(len(df)),
           "ft": (df.FTHome.astype(str) + "-" + df.FTAway.astype(str)).value_counts(normalize=True).round(5).to_dict(),
           "ht": (df.HTHome.astype(str) + "-" + df.HTAway.astype(str)).value_counts(normalize=True).round(5).to_dict(),
           "htft": pd.Series([f"{sign(a, b)}/{sign(c, d)}" for a, b, c, d in zip(df.HTHome, df.HTAway, df.FTHome, df.FTAway)])
           .value_counts(normalize=True).round(5).to_dict()}
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _score_section(days: list[str]) -> list[str]:
    """Correct-score, HT-score and HT/FT quality against the naive benchmark (log score, top-1 / top-3 hits)."""
    base = score_baseline()
    sign = lambda h, a: "1" if h > a else ("0" if h == a else "2")  # noqa: E731
    rows = {"ft": [], "ht": [], "htft": []}
    for day in days:
        d = DAILY / day
        store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8"))
        results = json.loads((d / RESULTS_FILE).read_text(encoding="utf-8"))
        for code, res in results.items():
            dist = (store.get(code) or {}).get("dist")
            if not res.get("completed") or not dist:
                continue
            (h1, a1), (h, a) = res["ht"], res["ft90"]
            actual = {"ft": f"{h}-{a}", "ht": f"{h1}-{a1}", "htft": f"{sign(h1, a1)}/{sign(h, a)}"}
            for k in rows:
                pred = dist[k]
                ranked = list(pred)
                p = pred.get(actual[k], 0.002)
                b = base[k].get(actual[k], 0.002)
                rows[k].append((np.log(p), np.log(b), actual[k] == ranked[0], actual[k] in ranked[:3],
                                pred[ranked[0]], sum(pred[x] for x in ranked[:3])))
    if not rows["ft"]:
        return []
    lines = ["", "## Skor ve İY/MS tahmin kalitesi (temel çizgiye karşı)", "",
             f"Temel çizgi: {base['n']:,} geçmiş maçta her sonucun sıklığı. Log skor farkı > 0 ise model temel çizgiden iyidir.", "",
             "| Tahmin | Maç | Model log skoru | Temel çizgi | Fark | En olası tuttu (beklenen) | İlk 3 tuttu (beklenen) |",
             "|---|---|---|---|---|---|---|"]
    for k, lab in (("ft", "Maç sonu skoru"), ("ht", "İlk yarı skoru"), ("htft", "İY/MS")):
        r = rows[k]
        n = len(r)
        lm, lb = np.mean([x[0] for x in r]), np.mean([x[1] for x in r])
        lines.append(f"| {lab} | {n} | {lm:.3f} | {lb:.3f} | {lm - lb:+.3f} | {sum(x[2] for x in r)}/{n} "
                     f"(%{np.mean([x[4] for x in r]) * 100:.0f}) | {sum(x[3] for x in r)}/{n} (%{np.mean([x[5] for x in r]) * 100:.0f}) |")
    return lines


def _surprises(day: str, top: int = 12) -> list[str]:
    """The day's biggest misses: confident predictions that failed and unlikely ones that happened."""
    d = DAILY / day
    store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8"))
    results = json.loads((d / RESULTS_FILE).read_text(encoding="utf-8"))
    rows = []
    for code, res in results.items():
        if not res.get("completed") or code not in store:
            continue
        rec = store[code]
        for name, won in res["won"].items():
            p = rec["s"][name][0]
            if 0.55 <= p and not won:
                src = "düşük güven (Nesine)" if str(rec.get("reference", "")).startswith("Nesine") else str(rec.get("reference", "")).split(" (")[0]
                rows.append((-np.log(1 - p), f"{rec['home']} - {rec['away']}", name, p, src, res))
    rows.sort(key=lambda x: -x[0])
    if not rows:
        return []
    lines = ["", f"## {day}: en büyük hatalar (%55+ verilip tutmayan, en emin olunandan başlayarak)", "",
             "| Maç | Tahmin | Olasılık | Fiyat kaynağı | Skor (İY / MS) |", "|---|---|---|---|---|"]
    seen = set()
    for _, match, name, p, src, res in rows:
        if (match, name) in seen or len(seen) >= top:
            continue
        seen.add((match, name))
        lines.append(f"| {match} | {name} | %{p * 100:.0f} | {src} | {res['ht'][0]}-{res['ht'][1]} / {res['ft90'][0]}-{res['ft90'][1]} |")
    return lines


def _calib_table(rows: list[tuple]) -> list[str]:
    bands = [(0, .2), (.2, .4), (.4, .5), (.5, .6), (.6, .7), (.7, .8), (.8, .9), (.9, 1.01)]
    out = ["| Tahmin edilen olasılık | Seçim | Ortalama tahmin | Gerçekleşen | Fark |", "|---|---|---|---|---|"]
    for lo, hi in bands:
        b = [r for r in rows if lo <= r[0] < hi]
        if b:
            mp, hit = np.mean([r[0] for r in b]), np.mean([r[1] for r in b])
            out.append(f"| %{lo * 100:.0f}–{min(hi, 1) * 100:.0f} | {len(b)} | %{mp * 100:.1f} | %{hit * 100:.1f} | {(hit - mp) * 100:+.1f} puan |")
    return out


def report() -> None:
    days = sorted(p.name for p in DAILY.iterdir() if (p / RESULTS_FILE).exists())
    rows, coupons = _rows(days)
    lines = ["# Nesine tahminleri — sonuç takibi", "",
             f"Günler: {', '.join(days) or '-'} · sonuçlanan seçim: {len(rows)}", "",
             "Doğru kalibre bir sistemde 'gerçekleşen' sütunu 'ortalama tahmin'e yakın olmalıdır.", ""]
    if not rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(lines + ["_Henüz sonuçlanan maç yok._"]) + "\n", encoding="utf-8")
        print("Henüz sonuçlanan maç yok.")
        return
    brier = np.mean([(r[0] - r[1]) ** 2 for r in rows])
    lines += [f"Brier skoru (tüm seçimler): {brier:.4f}", "", "## Olasılık bandına göre", ""] + _calib_table(rows)
    lines += ["", "## Fiyat kaynağına göre", "", "| Kaynak | Seçim | Ortalama tahmin | Gerçekleşen |", "|---|---|---|---|"]
    for label, flag in (("Doğrudan borsa fiyatı", True), ("Gol modeli", False)):
        b = [r for r in rows if r[3] == flag]
        if b:
            lines.append(f"| {label} | {len(b)} | %{np.mean([r[0] for r in b]) * 100:.1f} | %{np.mean([r[1] for r in b]) * 100:.1f} |")
    lines += ["", "## Bahis ailesine göre", "", "| Aile | Seçim | Ortalama tahmin | Gerçekleşen | Brier |", "|---|---|---|---|---|"]
    for fam in sorted({r[2] for r in rows}):
        b = [r for r in rows if r[2] == fam]
        lines.append(f"| {fam} | {len(b)} | %{np.mean([r[0] for r in b]) * 100:.1f} | %{np.mean([r[1] for r in b]) * 100:.1f} | "
                     f"{np.mean([(r[0] - r[1]) ** 2 for r in b]):.4f} |")
    safest = [r for r in rows if r[4]]
    if safest:
        lines += ["", "## Maç başına en güvenilir tercih (oran ≥ 1,20)", "",
                  f"{len(safest)} maç: ortalama tahmin %{np.mean([r[0] for r in safest]) * 100:.1f}, "
                  f"tutan %{np.mean([r[1] for r in safest]) * 100:.1f}"]
    lines += ["", "## Kuponlar", ""]
    if coupons:
        lines += ["| Kupon | Oran | Tahmini tutma | Sonuç | Tutan bacak |", "|---|---|---|---|---|"]
        lines += [f"| {c['file']} | {c['odds']:.2f} | %{c['p'] * 100:.1f} | {'TUTTU' if c['won'] else 'yattı'} | {c['legs_won']}/{c['legs']} |"
                  for c in coupons]
    else:
        lines.append("_Sonuçlanmış kupon yok._")
    lines += _score_section(days)
    lines += _surprises(days[-1])
    lines += _played_section()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:40]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sonuc")
    p.add_argument("--date", default=(dt.datetime.now(TSI).date() - dt.timedelta(days=1)).isoformat())
    sub.add_parser("rapor")
    args = ap.parse_args()
    if args.cmd == "sonuc":
        settle_day(args.date)
    else:
        report()


if __name__ == "__main__":
    main()
