"""Next-day evaluation of every AI's predictions, written to the SHARED area that everyone can see.

    python scripts/gun_degerlendirme.py --tarih 2026-11-20

User rule (20 Nov): each AI keeps its predictions private in tahminler/<ai>/<date>/ (never on GitHub). The day
after, the matches are settled and every AI's predictions are evaluated in one shared report:

  degerlendirme/<date>.md / .json   results of the evaluated matches, per-AI scorecard (main-pick hit rate, flat
                                    1-unit return on the main picks, 1X2 Brier / log-loss, coupons and legs won),
                                    each AI's biggest misses (most confident main picks that lost), and — when the
                                    AI ran scripts/derin_arastirma.py — how its ✓ / ~ / ⚠ research verdicts fared
  degerlendirme/derin_arastirma_ozet.md   the verdict scorecard accumulated over every evaluated day

Only FINISHED matches appear, so nothing about an open match is ever revealed. Inputs are the common CSV files of
tahminler/README.md (mac_tahminleri.csv, kuponlar.csv); results come from Nesine's own results feed, keyed by the
same Nesine event code.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.nesine import fetch_results  # noqa: E402
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402

TAHMIN = ROOT / "tahminler"
OUT = ROOT / "degerlendirme"
VERDICT_STATS = ROOT / "data" / "calibration" / "verdict_stats.json"  # read by kupon_kur.py
TSI = dt.timezone(dt.timedelta(hours=3))


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(x) -> float | None:
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None


def selection_name(market: str, sel: str, lookup: dict[tuple[str, str], str] | None = None) -> str | None:
    """Nesine market + selection label -> settlement grammar (e.g. '2,5 Gol Alt/Üst', '2,5 Üst' -> '2.5 Üst')."""
    market, sel = (market or "").strip(), (sel or "").strip()
    if lookup and (market, sel) in lookup:
        return lookup[(market, sel)]
    if market == "Maç Sonucu" and sel in ("1", "X", "0", "2"):
        return f"MS {'0' if sel in ('X', '0') else sel}"
    if market == "Çifte Şans":
        return {"1-X": "ÇŞ 1X", "1-2": "ÇŞ 12", "X-2": "ÇŞ X2"}.get(sel)
    if market == "Karşılıklı Gol" and sel in ("Var", "Yok"):
        return f"KG {sel}"
    if market == "İlk Yarı/Maç Sonucu" and re.fullmatch(r"[12X0]/[12X0]", sel):
        return "İY/MS " + sel.replace("X", "0")
    m = re.fullmatch(r"(\d)[,.]5 (Alt|Üst)", sel)
    if m and re.fullmatch(r"(\d[,.]5 )?Gol Alt/Üst", market):
        return f"{m.group(1)}.5 {m.group(2)}"
    return None


def _lookup_for(ai_dir: Path) -> dict[str, dict[tuple[str, str], str]]:
    """Per match code: (market, selection) -> name, from that AI's own analysis file when it has one."""
    out: dict[str, dict[tuple[str, str], str]] = {}
    path = ai_dir / "nesine_global.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for m in data.get("matches", []):
            out[str(m["code"])] = {(s["market"], s["selection"]): s["name"] for s in m.get("selections") or []}
    return out


def _settle(name: str | None, res: dict) -> bool | None:
    if not name or not res.get("completed"):
        return None
    try:
        return settle_selection(name, tuple(res["ht"]), tuple(res["ft90"]))
    except (ValueError, KeyError):
        return None


VERDICT_CLASSES = (("✓", "geçmiş destekliyor"), ("~", "geçmiş zayıf destekliyor"), ("⚠", "geçmiş desteklemiyor"),
                   ("?", "geçmiş yetersiz"))


def _verdict_class(v: str) -> str:
    return next((c for c, _ in VERDICT_CLASSES if (v or "").startswith(c)), "?")


def research_verdicts(ai_dir: Path, results: dict[int, dict]) -> dict[str, dict]:
    """Settled legs of the AI's deep-research files (coupon legs and the day's researched picks) grouped by verdict:
    did ⚠ legs really lose more often?"""
    out: dict[str, dict] = {}
    seen: set[tuple[str, str]] = set()
    for fname in ("derin_tahminler.json", "derin_arastirma.json"):
        path = ai_dir / fname
        if not path.exists():
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            res = results.get(int(row["code"])) if str(row.get("code", "")).isdigit() else None
            legs = [x for x in row.get("legs") or [] if (str(row.get("code")), str(x.get("name"))) not in seen]
            seen |= {(str(row.get("code")), str(x.get("name"))) for x in legs}
            _count(out, legs, res)
    return out


def _count(out: dict[str, dict], legs: list[dict], res: dict | None) -> None:
    for leg in legs:
        won = _settle(leg.get("name"), res or {})
        if won is None:
            continue
        g = out.setdefault(_verdict_class(leg.get("verdict")), {"n": 0, "won": 0, "p_sum": 0.0, "p_n": 0, "h_sum": 0.0, "h_n": 0})
        g["n"] += 1
        g["won"] += int(won)
        if leg.get("p") is not None:
            g["p_sum"] += leg["p"]; g["p_n"] += 1
        if leg.get("mean") is not None:
            g["h_sum"] += leg["mean"]; g["h_n"] += 1


def evaluate(date: str, results: dict[int, dict] | None = None) -> dict:
    ais = sorted(p.name for p in TAHMIN.iterdir() if (p / date).is_dir()) if TAHMIN.exists() else []
    files = {ai: (_read(TAHMIN / ai / date / "mac_tahminleri.csv"), _read(TAHMIN / ai / date / "kuponlar.csv")) for ai in ais}
    if results is None:
        d0 = dt.date.fromisoformat(date)
        results = fetch_results([d0.isoformat(), (d0 + dt.timedelta(days=1)).isoformat()])
    matches: dict[str, dict] = {}
    report = {"date": date, "built": dt.datetime.now(TSI).isoformat(timespec="minutes"), "ais": {}, "matches": matches}
    for ai, (rows, legs) in files.items():
        lookup = _lookup_for(TAHMIN / ai / date)
        picks, brier, logloss, misses = [], [], [], []
        for r in rows:
            code = str(r.get("nesine_kodu") or "")
            res = results.get(int(code)) if code.isdigit() else None
            if not res or not res.get("completed"):
                continue  # open / unknown match: never revealed
            ht, ft = res["ht"], res["ft90"]
            mrec = matches.setdefault(code, {"match": r.get("mac"), "league": r.get("lig"), "kickoff": r.get("saat"),
                                             "ht": ht, "ft": ft, "picks": {}})
            p1, px, p2 = (_f(r.get(k)) for k in ("olasilik_1", "olasilik_X", "olasilik_2"))
            if None not in (p1, px, p2):
                outcome = (1, 0, 0) if ft[0] > ft[1] else ((0, 1, 0) if ft[0] == ft[1] else (0, 0, 1))
                brier.append(sum((p - o) ** 2 for p, o in zip((p1, px, p2), outcome)))
                logloss.append(-math.log(max(1e-6, (p1, px, p2)[outcome.index(1)])))
            name = selection_name(r.get("ana_secim_pazar"), r.get("ana_secim"), lookup.get(code))
            won = _settle(name, res)
            if won is None:
                continue
            p, odds = _f(r.get("olasilik")), _f(r.get("nesine_oran"))
            picks.append((won, p, odds))
            mrec["picks"][ai] = {"pick": f"{r.get('ana_secim_pazar')}: {r.get('ana_secim')}", "p": p, "odds": odds, "won": won}
            if not won and p is not None:
                misses.append((p, r.get("mac"), f"{r.get('ana_secim_pazar')}: {r.get('ana_secim')}", f"{ht[0]}-{ht[1]} / {ft[0]}-{ft[1]}"))
        coupons: dict[tuple[str, str], list] = {}
        for leg in legs:
            code = str(leg.get("nesine_kodu") or "")
            res = results.get(int(code)) if code.isdigit() else None
            lookup_c = lookup.get(code)
            won = _settle(selection_name(leg.get("pazar"), leg.get("secim"), lookup_c), res or {})
            coupons.setdefault((leg.get("kupon"), leg.get("kupon_no")), []).append(
                {"match": leg.get("mac"), "sel": f"{leg.get('pazar')}: {leg.get('secim')}", "won": won,
                 "odds": _f(leg.get("kupon_toplam_oran")), "p": _f(leg.get("kupon_tutma_olasiligi")),
                 "type": leg.get("kupon_turu") or "karma"})
        settled = {k: v for k, v in coupons.items() if all(x["won"] is not None for x in v)}
        n = len(picks)
        report["ais"][ai] = {
            "main_picks": n, "hits": sum(1 for w, *_ in picks if w),
            "avg_pred": (sum(p for _, p, _ in picks if p is not None) / max(1, sum(1 for _, p, _ in picks if p is not None))) if n else None,
            "flat_return": sum(((o - 1) if w else -1) for w, _, o in picks if o) if n else 0.0,
            "brier_1x2": sum(brier) / len(brier) if brier else None, "logloss_1x2": sum(logloss) / len(logloss) if logloss else None,
            "n_1x2": len(brier),
            "coupons": [{"coupon": f"{k[0]} #{k[1]}", "type": v[0]["type"], "odds": v[0]["odds"], "p": v[0]["p"],
                         "won": all(x["won"] for x in v), "legs_won": sum(1 for x in v if x["won"]), "legs": len(v),
                         "lost_legs": [f"{x['match']} — {x['sel']}" for x in v if not x["won"]]} for k, v in sorted(settled.items())],
            "coupons_open": len(coupons) - len(settled),
            "biggest_misses": [{"p": p, "match": m, "pick": s, "score": sc} for p, m, s, sc in sorted(misses, reverse=True)[:10]],
            "research_verdicts": research_verdicts(TAHMIN / ai / date, results),
        }
    return report


def to_markdown(rep: dict) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.1f}"  # noqa: E731
    md = [f"# {rep['date']} — bütün yapay zekâların tahmin değerlendirmesi ({rep['built'][11:16]} TSİ)", "",
          "Yalnız **bitmiş** maçlar değerlendirilir; açık maçlar hiçbir zaman yazılmaz. Tahminler her yapay zekânın kendi "
          "(paylaşılmayan) klasöründen, sonuçlar Nesine'nin sonuç akışından (aynı maç kodu).", "",
          "## Karne", "",
          "| Yapay zekâ | Ana tercih (tutan/değerlendirilen) | İsabet | Ortalama tahmin | 1 birim sabit bahis | 1X2 Brier | 1X2 log-loss | Tutan kupon |",
          "|---|---|---|---|---|---|---|---|"]
    for ai, a in rep["ais"].items():
        won_c = sum(1 for c in a["coupons"] if c["won"])
        md.append(f"| {ai} | {a['hits']}/{a['main_picks']} | {pct(a['hits'] / a['main_picks']) if a['main_picks'] else '-'} | "
                  f"{pct(a['avg_pred'])} | {a['flat_return']:+.2f} | "
                  f"{'-' if a['brier_1x2'] is None else f'{a['brier_1x2']:.3f}'} | {'-' if a['logloss_1x2'] is None else f'{a['logloss_1x2']:.3f}'} | "
                  f"{won_c}/{len(a['coupons'])}" + (f" (+{a['coupons_open']} açık)" if a["coupons_open"] else "") + " |")
    md += ["", "Brier ve log-loss: düşük olan daha iyi. Sabit bahis: her ana tercihe 1 birim, Nesine oranıyla.", ""]
    for ai, a in rep["ais"].items():
        md += [f"## {ai}", ""]
        if a["coupons"]:
            md += ["| Kupon | Tür | Oran | Tahmini tutma | Sonuç | Tutan bacak | Yatan bacaklar |", "|---|---|---|---|---|---|---|"]
            md += [f"| {c['coupon']} | {c['type']} | {c['odds'] or '-'} | {pct(c['p'])} | {'✓ tuttu' if c['won'] else '✗ yattı'} | "
                   f"{c['legs_won']}/{c['legs']} | {'; '.join(c['lost_legs']) or '-'} |" for c in a["coupons"]]
            md.append("")
        if a.get("research_verdicts"):
            md += ["Derin araştırma işaretleri (bacağın kendi bahsi, takımların son maçlarına göre):", "",
                   "| İşaret | Bacak | Tutan | İsabet | Model ortalaması | Geçmiş ortalaması |", "|---|---|---|---|---|---|"]
            md += _verdict_rows(a["research_verdicts"])
            md.append("")
        if a["biggest_misses"]:
            md += ["En güvenilen ama tutmayan ana tercihler:", "", "| Olasılık | Maç | Tercih | İY / MS |", "|---|---|---|---|"]
            md += [f"| {pct(x['p'])} | {x['match']} | {x['pick']} | {x['score']} |" for x in a["biggest_misses"]]
            md.append("")
    md += ["## Maç sonuçları ve ana tercihler", "", "| Saat | Maç | İY | MS | " + " | ".join(rep["ais"]) + " |",
           "|---|---|---|---|" + "---|" * len(rep["ais"])]
    for m in sorted(rep["matches"].values(), key=lambda x: x.get("kickoff") or ""):
        cells = []
        for ai in rep["ais"]:
            pk = m["picks"].get(ai)
            cells.append(f"{'✓' if pk['won'] else '✗'} {pk['pick']}" if pk else "-")
        md.append(f"| {m.get('kickoff') or ''} | {m['match']} | {m['ht'][0]}-{m['ht'][1]} | {m['ft'][0]}-{m['ft'][1]} | " + " | ".join(cells) + " |")
    return "\n".join(md) + "\n"


def _verdict_rows(v: dict[str, dict]) -> list[str]:
    pct = lambda x: "-" if x is None else f"%{100 * x:.1f}"  # noqa: E731
    rows = []
    for c, label in VERDICT_CLASSES:
        g = v.get(c)
        if not g or not g["n"]:
            continue
        rows.append(f"| {c} {label} | {g['n']} | {g['won']} | {pct(g['won'] / g['n'])} | "
                    f"{pct(g['p_sum'] / g['p_n'] if g['p_n'] else None)} | {pct(g['h_sum'] / g['h_n'] if g['h_n'] else None)} |")
    return rows


def verdict_totals(out_dir: Path = OUT) -> tuple[list[str], dict[str, dict[str, dict]]]:
    """(evaluated days, {ai: {verdict class: counts}}) over every evaluated day."""
    total: dict[str, dict[str, dict]] = {}
    days = []
    for f in sorted(out_dir.glob("20*.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        days.append(rep["date"])
        for ai, a in rep.get("ais", {}).items():
            for c, g in (a.get("research_verdicts") or {}).items():
                t = total.setdefault(ai, {}).setdefault(c, {"n": 0, "won": 0, "p_sum": 0.0, "p_n": 0, "h_sum": 0.0, "h_n": 0})
                for k in t:
                    t[k] += g.get(k, 0)
    return days, total


def cumulative_verdicts(out_dir: Path = OUT) -> str:
    """All evaluated days together: is the deep-research warning worth acting on (e.g. dropping ⚠ legs)?"""
    days, total = verdict_totals(out_dir)
    md = ["# Derin araştırma işaretleri — bütün günler", "",
          f"Günler: {', '.join(days) or '-'}. Bir işaret ancak yeterli bacak biriktiğinde anlamlıdır: ⚠ bacakların isabeti "
          "model ortalamasının belirgin altında kalıyorsa, kupon kurucu bu bacakları elemeye başlayabilir.", ""]
    for ai, v in total.items():
        md += [f"## {ai}", "", "| İşaret | Bacak | Tutan | İsabet | Model ortalaması | Geçmiş ortalaması |", "|---|---|---|---|---|---|",
               *_verdict_rows(v), ""]
    return "\n".join(md) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=(dt.datetime.now(TSI).date() - dt.timedelta(days=1)).isoformat())
    args = ap.parse_args()
    rep = evaluate(args.tarih)
    OUT.mkdir(exist_ok=True)
    (OUT / f"{args.tarih}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / f"{args.tarih}.md").write_text(to_markdown(rep), encoding="utf-8")
    (OUT / "derin_arastirma_ozet.md").write_text(cumulative_verdicts(), encoding="utf-8")
    VERDICT_STATS.write_text(json.dumps(verdict_totals()[1], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{args.tarih}: {len(rep['ais'])} yapay zekâ, {len(rep['matches'])} bitmiş maç -> degerlendirme/{args.tarih}.md")


if __name__ == "__main__":
    main()
