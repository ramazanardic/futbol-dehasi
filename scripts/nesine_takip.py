"""Results tracking for the Nesine predictions: settle, then measure whether the probabilities are right.

    python scripts/nesine_takip.py sonuc --date 2026-11-19   # fetch results, settle every recorded selection
    python scripts/nesine_takip.py rapor                      # cumulative hit-rate / calibration report

Inputs: reports/daily/<date>/takip_kayit.json (last pre-kick-off prediction per match, written by
nesine_global.py) and the coupons in reports/daily/<date>/kupon_*.json. Results come from ESPN (HT and
90-minute score); matches ESPN does not list stay unsettled. Output: takip_sonuc.json per day and
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
    ids = _event_ids(day, {c: r for c, r in store.items() if not (results.get(c) or {}).get("completed")})
    for code, eid in ids.items():
        r = fetch_espn_result(eid)
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
                    name = (leg.get("key") or "||").split("|")[1]
                    res = results.get(str(leg["code"])) or {}
                    status.append(res.get("won", {}).get(name) if res.get("completed") else None)
                if status and all(s is not None for s in status):
                    coupons.append({"file": f"{day}/{f.name}", "odds": c["nesine_odds"], "p": c["probability"],
                                    "won": all(status), "legs_won": sum(status), "legs": len(status)})
    return rows, coupons


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
