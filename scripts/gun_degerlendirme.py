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
from ai_tahmin import clv_summary
from quantfoot.data.nesine import fetch_results  # noqa: E402
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402

TAHMIN = ROOT / "tahminler"
OUT = ROOT / "degerlendirme"
VERDICT_STATS = ROOT / "data" / "calibration" / "verdict_stats.json"  # read by kupon_kur.py
TSI = dt.timezone(dt.timedelta(hours=3))


def _fmt3(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


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
    """Per match code: (market, selection) -> name, from that AI's own analysis file when it has one. Labels are
    compared without surrounding spaces (Nesine pads some market names)."""
    out: dict[str, dict[tuple[str, str], str]] = {}
    path = ai_dir / "nesine_global.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for m in data.get("matches", []):
            out[str(m["code"])] = {(s["market"].strip(), s["selection"].strip()): s["name"] for s in m.get("selections") or []}
    return out


def label_names(ai_dir: Path) -> dict[tuple[str, str], str]:
    """(market, selection) -> settlement name learnt from the AI's analysis files of every day, kept only when the
    label always maps to the same name (a match that left the bulletin is missing from that day's file)."""
    seen: dict[tuple[str, str], set[str]] = {}
    for f in ai_dir.parent.glob("*/nesine_global.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for m in data.get("matches", []):
            for s in m.get("selections") or []:
                seen.setdefault((s["market"].strip(), s["selection"].strip()), set()).add(s["name"])
    return {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}


def row_name(row: dict, market_key: str, sel_key: str, lookup: dict[tuple[str, str], str] | None,
             labels: dict[tuple[str, str], str] | None = None) -> str | None:
    """Settlement name of a table row: its secim_adi column (written since 21 Nov), else the label mapping, else the
    selection itself when it is already a settlement name (e.g. 'Ev İY 0.5 Alt')."""
    if (row.get("secim_adi") or "").strip():
        return row["secim_adi"].strip()
    name = selection_name(row.get(market_key), row.get(sel_key), lookup)
    if name:
        return name
    sel = (row.get(sel_key) or "").strip()
    if labels and ((row.get(market_key) or "").strip(), sel) in labels:
        return labels[((row.get(market_key) or "").strip(), sel)]
    try:
        return sel if sel and settle_selection(sel, (0, 0), (0, 0)) is not None else None
    except (ValueError, KeyError, IndexError):
        return None


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


def clv_of(ai_dir: Path) -> dict | None:
    """Closing-price summary of the AI's main picks (tahmin_clv.json, written by scripts/ai_tahmin.py)."""
    path = ai_dir / "tahmin_clv.json"
    if not path.exists():
        return None
    summary = clv_summary(json.loads(path.read_text(encoding="utf-8")))
    return summary if summary["n"] else None


SIM_CLASSES = ("üçlü onay", "kısmi onay", "çelişki", "eksik kanıt")


def simulation_verdicts(ai_dir: Path, results: dict[int, dict]) -> dict[str, dict]:
    """Settled bets of the AI's simulation file (scripts/simulasyon.py) by verdict: do triple-confirmed bets really
    win as often as priced, and do 'çelişki' bets lose more?"""
    path = ai_dir / "simulasyon.json"
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for row in json.loads(path.read_text(encoding="utf-8")):
        res = results.get(int(row["code"])) if str(row.get("code", "")).isdigit() else None
        for b in row.get("bets") or []:
            won = _settle(b.get("name"), res or {})
            if won is None:
                continue
            g = out.setdefault(b["verdict"], {"n": 0, "won": 0, "p_sum": 0.0, "p_n": 0, "h_sum": 0.0, "h_n": 0})
            g["n"] += 1
            g["won"] += int(won)
            g["p_sum"] += b["market"]; g["p_n"] += 1
            if b.get("sim") is not None:
                g["h_sum"] += b["sim"]; g["h_n"] += 1
    return out


def evaluate(date: str, results: dict[int, dict] | None = None) -> dict:
    ais = sorted(p.name for p in TAHMIN.iterdir() if (p / date).is_dir()) if TAHMIN.exists() else []
    files = {ai: (_read(TAHMIN / ai / date / "mac_tahminleri.csv"), _read(TAHMIN / ai / date / "kuponlar.csv")) for ai in ais}
    if results is None:
        d0 = dt.date.fromisoformat(date)
        results = fetch_results([d0.isoformat(), (d0 + dt.timedelta(days=1)).isoformat()], strict=True)
        if not any(result["completed"] for result in results.values()):
            raise RuntimeError("Nesine sonuçlarında doğrulanmış bitmiş maç yok")
    matches: dict[str, dict] = {}
    report = {"date": date, "built": dt.datetime.now(TSI).isoformat(timespec="minutes"), "ais": {}, "matches": matches}
    for ai, (rows, legs) in files.items():
        lookup = _lookup_for(TAHMIN / ai / date)
        labels = label_names(TAHMIN / ai / date)
        picks, brier, logloss, misses = [], [], [], []
        expected_columns = {"nesine_kodu", "ana_secim", "olasilik_1", "olasilik_X", "olasilik_2"}
        columns = set(rows[0]) if rows else set()
        quality = {
            "prediction_rows": len(rows), "coupon_rows": len(legs),
            "schema": "standard" if expected_columns.issubset(columns) else
                      ("incompatible" if rows else "no_prediction_rows"),
            "missing_nesine_code": sum(not str(x.get("nesine_kodu") or "").isdigit() for x in rows),
            "missing_main_pick": sum(not (x.get("ana_secim") or x.get("secim_adi")) for x in rows),
            "unmatched_or_open": 0, "ungradeable_selection": 0,
            "invalid_1x2_distribution": 0,
        }
        # Keep the last explicitly recorded pick per Nesine event; blank duplicates never erase a pick.
        by_code = {}
        for r in rows:
            code = str(r.get("nesine_kodu") or "")
            if code not in by_code or r.get("secim_adi") or r.get("ana_secim"):
                by_code[code] = r
        for code, r in by_code.items():
            res = results.get(int(code)) if code.isdigit() else None
            if not res or not res.get("completed"):
                quality["unmatched_or_open"] += 1
                continue  # open / unknown match: never revealed
            ht, ft = res["ht"], res["ft90"]
            mrec = matches.setdefault(code, {"match": r.get("mac"), "league": r.get("lig"), "kickoff": r.get("saat"),
                                             "ht": ht, "ft": ft, "picks": {}})
            p1, px, p2 = (_f(r.get(k)) for k in ("olasilik_1", "olasilik_X", "olasilik_2"))
            if None not in (p1, px, p2):
                # Do not score impossible/non-normalized distributions as if they were valid forecasts.
                if all(math.isfinite(p) and 0 <= p <= 1 for p in (p1, px, p2)) and abs(p1 + px + p2 - 1) <= 0.02:
                    outcome = (1, 0, 0) if ft[0] > ft[1] else ((0, 1, 0) if ft[0] == ft[1] else (0, 0, 1))
                    brier.append(sum((p - o) ** 2 for p, o in zip((p1, px, p2), outcome)))
                    logloss.append(-math.log(max(1e-6, (p1, px, p2)[outcome.index(1)])))
                else:
                    quality["invalid_1x2_distribution"] += 1
            name = row_name(r, "ana_secim_pazar", "ana_secim", lookup.get(code), labels)
            won = _settle(name, res)
            if won is None:
                if name:
                    quality["ungradeable_selection"] += 1
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
            won = _settle(row_name(leg, "pazar", "secim", lookup_c, labels), res or {})
            coupons.setdefault((leg.get("kupon"), leg.get("kupon_no")), []).append(
                {"match": leg.get("mac"), "sel": f"{leg.get('pazar')}: {leg.get('secim')}", "won": won,
                 "odds": _f(leg.get("kupon_toplam_oran")), "p": _f(leg.get("kupon_tutma_olasiligi")),
                 "type": leg.get("kupon_turu") or "karma"})
        settled = {k: v for k, v in coupons.items() if all(x["won"] is not None for x in v)}
        n = len(picks)
        report["ais"][ai] = {
            "main_picks": n, "hits": sum(1 for w, *_ in picks if w),
            "data_quality": quality,
            "avg_pred": (sum(p for _, p, _ in picks if p is not None) / sum(1 for _, p, _ in picks if p is not None))
                        if any(p is not None for _, p, _ in picks) else None,
            "flat_return": sum(((o - 1) if w else -1) for w, _, o in picks if o) if n else 0.0,
            "brier_1x2": sum(brier) / len(brier) if brier else None, "logloss_1x2": sum(logloss) / len(logloss) if logloss else None,
            "n_1x2": len(brier),
            "coupons": [{"coupon": f"{k[0]} #{k[1]}", "type": v[0]["type"], "odds": v[0]["odds"], "p": v[0]["p"],
                         "won": all(x["won"] for x in v), "legs_won": sum(1 for x in v if x["won"]), "legs": len(v),
                         "lost_legs": [f"{x['match']} — {x['sel']}" for x in v if not x["won"]]} for k, v in sorted(settled.items())],
            "coupons_open": len(coupons) - len(settled),
            "biggest_misses": [{"p": p, "match": m, "pick": s, "score": sc} for p, m, s, sc in sorted(misses, reverse=True)[:10]],
            "research_verdicts": research_verdicts(TAHMIN / ai / date, results),
            "simulation_verdicts": simulation_verdicts(TAHMIN / ai / date, results),
            "clv": clv_of(TAHMIN / ai / date),
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
                  f"{_fmt3(a['brier_1x2'])} | {_fmt3(a['logloss_1x2'])} | "
                  f"{won_c}/{len(a['coupons'])}" + (f" (+{a['coupons_open']} açık)" if a["coupons_open"] else "") + " |")
    md += ["", "Brier ve log-loss: düşük olan daha iyi. Sabit bahis: her ana tercihe 1 birim, Nesine oranıyla.", "",
           "## Girdi kapsamı / eksik kayıt uyarıları", "",
           "| Yapay zekâ | CSV satırı | Şema | Kimliksiz | Ana seçim yok | Sonuçsuz/eşleşmeyen | Puanlanamayan seçim | Hatalı 1X2 |",
           "|---|---:|---|---:|---:|---:|---:|---:|"]
    for ai, a in rep["ais"].items():
        q = a.get("data_quality") or {}
        md.append(f"| {ai} | {q.get('prediction_rows', 0)} | {q.get('schema', 'belirsiz')} | "
                  f"{q.get('missing_nesine_code', 0)} | {q.get('missing_main_pick', 0)} | "
                  f"{q.get('unmatched_or_open', 0)} | {q.get('ungradeable_selection', 0)} | "
                  f"{q.get('invalid_1x2_distribution', 0)} |")
    md += ["", "Şeması uyumsuz dosyalar 0 başarı olarak yorumlanmaz. Sonuçsuz/eşleşmeyen sayısı açık maçları da içerir.",
           "Skor kaynağı ve ilk yayımlanma zamanı ayrı geçmiş denetiminde kontrol edilir.", ""]
    for ai, a in rep["ais"].items():
        md += [f"## {ai}", ""]
        if a.get("clv"):
            c = a["clv"]
            md += [f"Kapanış fiyatı (CLV): {c['n']} ana tercih, ortalama {100 * c['mean']:+.1f} puan, "
                   f"{c['positive']}/{c['n']} tercihte piyasa tercihe doğru kaydı.", ""]
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
        if a.get("simulation_verdicts"):
            md += ["Simülasyon kararları (piyasa / simülasyon / geçmiş / model karşılaştırması):", "",
                   "| Karar | Bahis | Tutan | İsabet | Piyasa ortalaması | Simülasyon ortalaması |", "|---|---|---|---|---|---|"]
            md += _sim_rows(a["simulation_verdicts"])
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


def _sim_rows(v: dict[str, dict]) -> list[str]:
    pct = lambda x: "-" if x is None else f"%{100 * x:.1f}"  # noqa: E731
    return [f"| {c} | {v[c]['n']} | {v[c]['won']} | {pct(v[c]['won'] / v[c]['n'])} | "
            f"{pct(v[c]['p_sum'] / v[c]['p_n'] if v[c]['p_n'] else None)} | {pct(v[c]['h_sum'] / v[c]['h_n'] if v[c]['h_n'] else None)} |"
            for c in SIM_CLASSES if v.get(c) and v[c]["n"]]


def verdict_totals(out_dir: Path = OUT) -> tuple[list[str], dict[str, dict[str, dict]]]:
    """(evaluated days, {ai: {verdict class: counts}}) over every evaluated day."""
    total: dict[str, dict[str, dict]] = {}
    days = []
    for f in sorted(out_dir.glob("20*.json")):
        rep = json.loads(f.read_text(encoding="utf-8"))
        days.append(rep["date"])
        for ai, a in rep.get("ais", {}).items():
            sims = {f"sim:{c}": g for c, g in (a.get("simulation_verdicts") or {}).items()}
            for c, g in {**(a.get("research_verdicts") or {}), **sims}.items():
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
        sim = {c[4:]: x for c, x in v.items() if c.startswith("sim:")}
        if sim:
            md += ["| Simülasyon kararı | Bahis | Tutan | İsabet | Piyasa ortalaması | Simülasyon ortalaması |",
                   "|---|---|---|---|---|---|", *_sim_rows(sim), ""]
    return "\n".join(md) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=(dt.datetime.now(TSI).date() - dt.timedelta(days=1)).isoformat())
    args = ap.parse_args()
    try:
        rep = evaluate(args.tarih)
        old_file = OUT / f"{args.tarih}.json"
        if old_file.exists():
            previous = json.loads(old_file.read_text(encoding="utf-8"))
            missing = previous.get("matches", {}).keys() - rep["matches"].keys()
            if missing:
                raise RuntimeError(f"Daha önce puanlanan {len(missing)} maç eksik, mevcut karne korundu")
            for ai, old in previous.get("ais", {}).items():
                if rep["ais"].get(ai, {}).get("main_picks", 0) < old.get("main_picks", 0):
                    raise RuntimeError(f"{ai} için önceki tahminler eksik, mevcut karne korundu")
    except (RuntimeError, OSError, ValueError) as exc:
        ap.exit(2, f"Değerlendirme tamamlanamadı: {exc}\n")
    OUT.mkdir(exist_ok=True)
    (OUT / f"{args.tarih}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / f"{args.tarih}.md").write_text(to_markdown(rep), encoding="utf-8")
    (OUT / "derin_arastirma_ozet.md").write_text(cumulative_verdicts(), encoding="utf-8")
    VERDICT_STATS.write_text(json.dumps(verdict_totals()[1], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{args.tarih}: {len(rep['ais'])} yapay zekâ, {len(rep['matches'])} bitmiş maç -> degerlendirme/{args.tarih}.md")


if __name__ == "__main__":
    main()
