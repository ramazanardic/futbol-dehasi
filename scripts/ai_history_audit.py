#!/usr/bin/env python3
"""Read-only, cross-AI historical audit: independently settle matches and coupon legs.

This is an evidence audit, not a prediction generator. It NEVER trusts a CSV's own
"TUTTU" field as the actual outcome; it does not edit predictions or place bets.

Usage: python scripts/ai_history_audit.py [--root .] [--out reports/audits]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.evaluation.settlement import settle_selection  # noqa: E402
from quantfoot.markets.market_diagnosis import classify_family  # noqa: E402

AIS = ("antigravitytahmin", "chatgbttahmin", "claudetahmin",
       "geminitahmin", "grokbottahmin")
TSI = dt.timezone(dt.timedelta(hours=3))
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCORE = re.compile(r"^\s*(\d+)\s*[-:]\s*(\d+)")
MISSING = {"", "?", "-", "none", "null", "nan"}


def number(value):
    if value is None or str(value).strip().lower() in MISSING:
        return None
    try:
        value = float(str(value).strip().replace(",", "."))
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def rows(path):
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def normal(name):
    s = unicodedata.normalize("NFKD", str(name or "").casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def score(value):
    m = SCORE.match(str(value or ""))
    return [int(m.group(1)), int(m.group(2))] if m else None


def canonical_selection(row, coupon=False):
    """Strict legacy conversion; never infer an unspecified market."""
    raw = str(row.get("secim_adi") or row.get("ana_tahmin")
              or row.get("tercih") or row.get("ana_secim")
              or row.get("secim") or "").strip()
    market = str(row.get("ana_secim_pazar") or row.get("bahis_ailesi")
                 or row.get("pazar") or "").strip()
    if not raw:
        return None
    if raw in {"1", "2", "0", "X"} and market in ("Maç Sonucu", "MS"):
        return "MS " + ("0" if raw == "X" else raw)
    if raw in {"Var", "Yok"} and "Karşılıklı Gol" in market:
        return "KG " + raw
    if raw.startswith("ÇŞ"):
        return "ÇŞ " + re.sub(r"[^12X]", "", raw[2:])
    if raw.startswith(("1-X", "X-2", "1-2")) and market.startswith("Çifte"):
        return "ÇŞ " + raw.replace("-", "")
    if re.fullmatch(r"\d+[,.]5\s+(Alt|Üst)", raw):
        return raw.replace(",", ".")
    if re.fullmatch(r"MS\s+[12X0]", raw):
        return raw.replace("X", "0")
    return raw


def group_market(name):
    if not name:
        return "tanımsız"
    if name.startswith("MS "):
        return "MS"
    if name.startswith("KG "):
        return "KG"
    if name.startswith("ÇŞ "):
        return "Çifte şans"
    if re.fullmatch(r"\d+[.]5 (Alt|Üst)", name):
        return "Gol alt/üst"
    if name.startswith(("Ev ", "Dep ")):
        return "Takım golü"
    if name.startswith(("İY ", "2Y ")):
        return "Yarı"
    return "Diğer"


def add_reference(target, date, code, match, ht, ft, source):
    if not (isinstance(ft, (list, tuple)) and len(ft) == 2):
        return
    try:
        ft = [int(ft[0]), int(ft[1])]
        ht = [int(ht[0]), int(ht[1])] if ht and len(ht) == 2 else None
    except (TypeError, ValueError):
        return
    if min(ft) < 0 or (ht is not None and (min(ht) < 0 or ht[0] > ft[0] or ht[1] > ft[1])):
        return
    target[(date, str(code))] = {"match": match, "ht": ht, "ft": ft, "source": source}


def load_references(root):
    refs = {}
    for p in sorted((root / "degerlendirme").glob("????-??-??.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        day = data.get("date") or p.stem
        for code, m in (data.get("matches") or {}).items():
            add_reference(refs, day, code, m.get("match"), m.get("ht"), m.get("ft"), str(p.relative_to(root)))
    # Early historical results precede the cross-AI scoreboards.
    p = root / "reports/ledger/nov18_audit_results.json"
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        for m in data.get("matches", []):
            ft = ([m["ft_h"], m["ft_a"]] if m.get("ft_h") is not None and m.get("ft_a") is not None else None)
            ht = ([m["ht_h"], m["ht_a"]] if m.get("ht_h") is not None and m.get("ht_a") is not None else None)
            if ft is not None:
                add_reference(refs, "2026-11-18", m.get("event_id") or "legacy_" + str(m.get("idx")),
                              (str(m.get("home")) + " - " + str(m.get("away"))), ht, ft,
                              str(p.relative_to(root)))
    return refs


def index_reference(refs):
    by_name = defaultdict(list)
    for (day, code), record in refs.items():
        by_name[(day, normal(record["match"]))].append((code, record))
    return by_name


def resolve_reference(refs, by_name, day, row):
    raw_code = str(row.get("nesine_kodu") or row.get("kod") or "").strip()
    # Exact Nesine ID wins; synthetic MBS codes are NOT authentic IDs.
    if raw_code.isdigit() and (day, raw_code) in refs:
        return refs[(day, raw_code)], "exact_code"
    name = normal(row.get("mac") or row.get("match"))
    choices = by_name.get((day, name), [])
    if len(choices) == 1:
        return choices[0][1], "unique_name"
    return None, "ambiguous_name" if len(choices) > 1 else "no_reference"


@lru_cache(maxsize=200_000)
def _grade_cached(name, ht, ft):
    try:
        return settle_selection(name, ht, ft)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def evaluate_selection(name, reference):
    if not name or reference is None:
        return None
    ht, ft = reference["ht"], reference["ft"]
    if ht is None:
        # Never guess half-time/first-goal outcomes from the full-time result.
        if group_market(name) not in {"MS", "KG", "Gol alt/üst", "Çifte şans", "Takım golü"}:
            return None
        ht = [0, 0]
    return _grade_cached(name, tuple(ht), tuple(ft))


def first_git_publication(root, relpath):
    """Git date is a lower-confidence publication bound, NOT row-level proof."""
    try:
        p = subprocess.run(["git", "log", "--reverse", "--diff-filter=A", "--format=%cI",
                            "--", str(relpath)], cwd=root, text=True, capture_output=True,
                           timeout=12, check=True)
        dates = [x.strip() for x in p.stdout.splitlines() if x.strip()]
        return dates[0] if dates else None
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None


def row_kickoff(row, day):
    date = row.get("tarih") or day
    time = row.get("saat") or row.get("saat_tsi")
    if not time or not re.fullmatch(r"\d\d:\d\d", str(time)):
        return None
    try:
        return dt.datetime.fromisoformat(str(date)[:10] + "T" + str(time)).replace(tzinfo=TSI)
    except ValueError:
        return None


def summary(items):
    settled = [r for r in items if r.get("won") is not None]
    with_p = [r for r in settled if r.get("p") is not None]
    with_price = [r for r in settled if r.get("odds") is not None and r["odds"] > 1]
    gains = sum((r["odds"] - 1 if r["won"] else -1) for r in with_price)
    cal_gap = ((sum(r["won"] for r in with_p) - sum(r["p"] for r in with_p)) / len(with_p)
               if with_p else None)
    return {
        "rows": len(items), "settled": len(settled),
        "wins": sum(r["won"] is True for r in settled),
        "hit_rate": sum(r["won"] is True for r in settled) / len(settled) if settled else None,
        "priced_n": len(with_price), "flat_units": round(gains, 4),
        "flat_roi": round(gains / len(with_price), 6) if with_price else None,
        "calibration_gap": round(cal_gap, 6) if cal_gap is not None else None,
        "negative_ev_winners": sum(r["won"] is True and r.get("ev") is not None and r["ev"] < 0 for r in settled),
        "positive_ev_losers": sum(r["won"] is False and r.get("ev") is not None and r["ev"] > 0 for r in settled),
        "no_reference": sum(r.get("reference_status") in {"no_reference", "ambiguous_name"} for r in items),
        "unresolved": len(items) - len(settled),
    }


def audit_prediction_file(root, refs, nameindex, ai, day, path):
    prediction_rows = rows(path)
    published = first_git_publication(root, path.relative_to(root))
    pub_dt = None
    if published:
        try:
            pub_dt = dt.datetime.fromisoformat(published)
        except ValueError:
            pass
    predictions = []
    quality = Counter()
    quality["raw_rows"] = len(prediction_rows)
    scores_mismatched = []
    statuses_mismatched = []
    for row in prediction_rows:
        select = canonical_selection(row)
        if not select:
            quality["no_main_selection"] += 1
        match, how = resolve_reference(refs, nameindex, day, row)
        quality["join_" + how] += 1
        p = number(row.get("olasilik") if row.get("olasilik") else row.get("kalibre_olasilik_pct"))
        if row.get("kalibre_olasilik_pct") and not row.get("olasilik") and p is not None:
            p /= 100
        odds = number(row.get("nesine_oran") or row.get("oran"))
        if p is not None and not 0 <= p <= 1:
            quality["invalid_probability"] += 1
            p = None
        if odds is not None and odds <= 1:
            quality["invalid_odds"] += 1
            odds = None
        ko = row_kickoff(row, day)
        if ko and pub_dt:
            quality["published_after_kickoff" if pub_dt > ko else "file_published_before_kickoff"] += 1
        elif ko and not pub_dt:
            quality["no_git_provenance"] += 1
        won = evaluate_selection(select, match)
        if select and match is not None and won is None:
            quality["ungradeable_market"] += 1
        claim_score = score(row.get("gerceklesen_skor"))
        if claim_score and match is not None and claim_score != match["ft"]:
            scores_mismatched.append({"match": row.get("mac"), "claimed": claim_score,
                                     "reference": match["ft"], "source": match["source"]})
        claimed_status = str(row.get("durum") or "").upper()
        if claimed_status in ("TUTTU", "YATTI") and won is not None:
            if (claimed_status == "TUTTU") != won:
                statuses_mismatched.append({"match": row.get("mac"), "selection": select,
                                            "claimed": claimed_status, "actual": bool(won)})
        ev = p * odds - 1 if p is not None and odds is not None else None
        predictions.append({"match": row.get("mac"), "selection": select,
                            "market": group_market(select), "p": p, "odds": odds, "ev": ev,
                            "won": won, "reference_status": how, "source": match["source"] if match else None})
    return {"file": str(path.relative_to(root)), "first_git_commit": published,
            "quality": dict(quality), "metrics": summary(predictions),
            "by_market": {k: summary([x for x in predictions if x["market"] == k])
                          for k in sorted({x["market"] for x in predictions})},
            "scores_mismatched": scores_mismatched, "statuses_mismatched": statuses_mismatched,
            "predictions": predictions}


def audit_coupons(root, refs, nameindex, ai, day, path):
    data = rows(path)
    coupons = defaultdict(list)
    used_match = defaultdict(set)
    for r in data:
        cid = str(r.get("kupon_adi") or r.get("kupon") or "").strip()
        cno = str(r.get("kupon_no") or "").strip()
        key = cid + (" #" + cno if cno else "")
        if not cid:
            key = "<unidentified>"
        ref, how = resolve_reference(refs, nameindex, day, r)
        name = canonical_selection(r, coupon=True)
        won = evaluate_selection(name, ref)
        match_id = str(r.get("nesine_kodu") or normal(r.get("mac")))
        coupons[key].append({"match": r.get("mac"), "selection": name,
                             "won": won, "reference_status": how,
                             "odds": number(r.get("nesine_oran")),
                             "p": number(r.get("olasilik")),
                             "claimed_status": r.get("ayak_durumu"),
                             "source": ref["source"] if ref else None})
        used_match[match_id].add(key)
    out = []
    for cid, legs in sorted(coupons.items()):
        known = all(x["won"] is not None for x in legs)
        odds = [x["odds"] for x in legs]
        p = [x["p"] for x in legs]
        claimed = Counter(str(x.get("claimed_status") or "") for x in legs)
        out.append({"coupon": cid, "legs": len(legs), "matched_legs": sum(x["won"] is not None for x in legs),
                    "status": ("won" if all(x["won"] for x in legs) else "lost") if known else "unverified",
                    "odds_product": round(math.prod(odds), 4) if all(x and x > 1 for x in odds) else None,
                    "independent_p_product": round(math.prod(p), 6) if all(x is not None and 0 <= x <= 1 for x in p) else None,
                    "claimed_leg_statuses": dict(claimed),
                    "losers": [x["match"] + " | " + str(x["selection"]) for x in legs if x["won"] is False]})
    n_cross = sum(1 for uses in used_match.values() if len(uses) > 1)
    return {"file": str(path.relative_to(root)), "rows": len(data), "coupons": out,
            "summary": {"coupons": len(out), "verified": sum(x["status"] != "unverified" for x in out),
                        "won": sum(x["status"] == "won" for x in out),
                        "reused_matches": n_cross,
                        "max_coupons_using_same_match": max((len(v) for v in used_match.values()), default=0)}}



def audit_market_prices(root, refs, nameindex, day, path):
    """Settle ALL priced selections, not only the single main CSV pick.

    A priced selection is not evidence that a bet was advised or placed.
    All selections for one match are correlated; family counts are NOT
    independent trial counts. Retain match counts by family for context.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, MemoryError) as exc:
        return {"file": str(path.relative_to(root)), "error": type(exc).__name__}
    games = data.get("matches") or []
    match_count = len(games)
    counters = Counter()
    buckets = defaultdict(lambda: {"n": 0, "settled": 0, "won": 0, "p_sum": 0.0,
                                    "p_n": 0, "priced": 0, "units": 0.0,
                                    "negative_ev_winners": 0, "positive_ev_losers": 0,
                                    "match_ids": set()})
    for game in games:
        code = game.get("code")
        match_name = game.get("match") or f"{game.get('home', '')} - {game.get('away', '')}"
        ref, how = resolve_reference(refs, nameindex, day, {
            "nesine_kodu": code, "mac": match_name})
        counters["matches"] += 1
        counters["match_join_" + how] += 1
        for sel in game.get("selections") or []:
            if not isinstance(sel, dict):
                continue
            name = sel.get("name")
            if not name:
                counters["selections_no_name"] += 1
                continue
            counters["selections_total"] += 1
            family = classify_family(str(name)) or group_market(str(name))
            direct = "direct" if sel.get("direct") is True else (
                "derived" if sel.get("direct") is False else "unknown")
            p = number(sel.get("fair_prob"))
            price = number(sel.get("odds"))
            if p is not None and not 0 <= p <= 1:
                counters["invalid_probabilities"] += 1
                p = None
            w = evaluate_selection(str(name), ref)
            for key in (family, "DIRECT:" + direct):
                group = buckets[key]
                group["n"] += 1
                if p is not None:
                    group["p_sum"] += p
                    group["p_n"] += 1
                if w is None:
                    continue
                group["settled"] += 1
                group["won"] += bool(w)
                group["match_ids"].add(str(code) if code is not None else normal(match_name))
                if price is not None and price > 1:
                    group["priced"] += 1
                    group["units"] += price - 1 if w else -1
                    if p is not None:
                        ev = p * price - 1
                        group["negative_ev_winners"] += bool(w and ev < 0)
                        group["positive_ev_losers"] += bool(not w and ev > 0)
            if w is not None:
                counters["settled_selections"] += 1
            else:
                counters["unsettled_selections"] += 1
    summarized = {}
    for family, group in buckets.items():
        n = group["settled"]
        priced = group["priced"]
        summarized[family] = {
            "total_choices": group["n"], "settled_choices": n,
            "distinct_matches": len(group["match_ids"]),
            "hits": group["won"],
            "hit_rate": round(group["won"] / n, 6) if n else None,
            "avg_predicted": round(group["p_sum"] / group["p_n"], 6) if group["p_n"] else None,
            "flat_roi": round(group["units"] / priced, 6) if priced else None,
            "negative_ev_winners": group["negative_ev_winners"],
            "positive_ev_losers": group["positive_ev_losers"],
        }
    return {"file": str(path.relative_to(root)), "matches": match_count,
            "coverage": dict(counters), "families": summarized,
            "caution": "Same-match choices are highly correlated; raw fair_prob may differ from final calibrated P."}

def audit_placed_ledger(root):
    out = {}
    for path in sorted((root / "reports/ledger").glob("placed_bets_*.csv")):
        tickets = defaultdict(list)
        for r in rows(path):
            tickets[(r.get("coupon_id") or "").strip()].append(r)
        seen, complete, stakes, payouts = 0, 0, 0.0, 0.0
        uncertain = []
        for cid, legs in tickets.items():
            if not cid:
                uncertain.append({"ticket": cid, "reason": "missing_id"})
                continue
            seen += 1
            stake = next((number(r.get("stake_tl")) for r in legs if number(r.get("stake_tl")) is not None), None)
            payout_values = {number(r.get("payout_tl")) for r in legs if number(r.get("payout_tl")) is not None}
            payout = next(iter(payout_values)) if len(payout_values) == 1 else None
            recorded_leg_count = number(legs[0].get("n_legs"))
            coherent = (recorded_leg_count is not None and int(recorded_leg_count) == len(legs)
                        and all(r.get("selection") not in ("", "?") for r in legs))
            if not coherent or stake is None or payout is None:
                uncertain.append({"ticket": cid, "reason": "incomplete_legs_or_stake_or_payout",
                                  "rows": len(legs), "expected_legs": recorded_leg_count,
                                  "stake": stake, "payout": payout})
            else:
                complete += 1
                stakes += stake
                payouts += payout  # payout is repeated on EACH LEG; count it once per coupon
        out[path.name] = {"ticket_ids": seen, "fully_specified_with_payout": complete,
                          "known_stakes_tl": round(stakes, 2),
                          "known_payouts_tl": round(payouts, 2),
                          "known_net_tl": round(payouts - stakes, 2),
                          "excluded": uncertain,
                          "caution": "Transcribed screenshots are NOT independently verified transactions."}
    return out


def run(root):
    refs = load_references(root)
    nameindex = index_reference(refs)
    output = {"method": {
        "settlement": "Archived external result scores + shared goal-market settlement parser",
        "joining": "exact numeric Nesine code first; else unique normalized match name for the same date",
        "publication": "Earliest Git commit is a file-level upper bound on publication time, not proof of per-row pre-match creation",
        "scope": "All available standard prediction and coupon CSVs; missing/alternative formats flagged, not invented",
        "caution": "This is a historical audit, not a live forward test or proof of profitability."},
        "reference_matches": len(refs), "ais": {}, "placed_ledger": audit_placed_ledger(root)}
    for ai in AIS:
        area = root / "tahminler" / ai
        entries = {}
        all_preds = []
        for directory in sorted(area.glob("????-??-??")):
            if not directory.is_dir() or not STAMP.fullmatch(directory.name):
                continue
            day = directory.name
            mp = directory / "mac_tahminleri.csv"
            cp = directory / "kuponlar.csv"
            predict = audit_prediction_file(root, refs, nameindex, ai, day, mp) if mp.exists() else None
            coupons = audit_coupons(root, refs, nameindex, ai, day, cp) if cp.exists() else None
            if predict:
                all_preds.extend(predict.pop("predictions"))
            market_file = directory / "nesine_global.json"
            market_prices = audit_market_prices(root, refs, nameindex, day, market_file) if market_file.is_file() else None
            entries[day] = {"predictions": predict, "coupons": coupons, "market_prices": market_prices}
        output["ais"][ai] = {"dates": entries, "overall": summary(all_preds),
                             "available_prediction_files": sum(v["predictions"] is not None for v in entries.values())}
    return output


def render(report):
    out = ["# Beş yapay zekânın tüm erişilebilir geçmişine ilişkin veri ve tahmin denetimi", "",
           "Sonuçlar yalnızca bağımsız skor referansı bulunan maçlar için puanlandı.",
           "Eski CSV'lerdeki TUTTU/YATTI etiketleri ve yazılı skorlar, referans kabul edilmedi.",
           "Git'e sonradan yüklenen maç tahminleri ileriye dönük performans kanıtı değildir.", "",
           "## Ana tercih özeti", "",
           "| Yapay zekâ | Ham kayıt | Sonuçlanan tercih | Doğru | İsabet | 1 birim ROI | Kazanan negatif EV | Kaybeden pozitif EV |",
           "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for ai, info in report["ais"].items():
        m = info["overall"]
        hit = f"%{100 * m['hit_rate']:.1f}" if m["hit_rate"] is not None else "-"
        roi = f"%{100 * m['flat_roi']:+.1f}" if m["flat_roi"] is not None else "-"
        out.append(f"| {ai} | {m['rows']} | {m['settled']} | {m['wins']} | {hit} | {roi} | {m['negative_ev_winners']} | {m['positive_ev_losers']} |")
    out += ["", "## Veri kalitesi, tarihe göre", ""]
    for ai, info in report["ais"].items():
        out += [f"### {ai}", ""]
        if not info["dates"]:
            out.append("- Ham tarihli dosya yok; yokluk başarısızlık değildir.")
            continue
        for day, entry in info["dates"].items():
            p = entry["predictions"]
            c = entry["coupons"]
            if p:
                q = p["quality"]
                out.append(f"- {day}: {q.get('raw_rows', 0)} satır; {p['metrics']['settled']} sonuçlanabilen ana tercih; "
                           f"{q.get('no_main_selection', 0)} boş ana tercih; "
                           f"{q.get('join_unique_name', 0)} yalnız isim eşleşmesi; "
                           f"{q.get('published_after_kickoff', 0)} satırın başlama saati Git'te ilk yayından önce; "
                           f"{len(p['scores_mismatched'])} skor ve {len(p['statuses_mismatched'])} TUTTU/YATTI çelişkisi.")
            if c:
                cs = c["summary"]
                out.append(f"  Kupon: {cs['coupons']} kupon, {cs['verified']} doğrulanabilir, "
                           f"{cs['won']} kazanan, {cs['reused_matches']} kuponlar arası tekrarlanan maç.")
        out.append("")
    out += ["## Tüm fiyatlanan bahis pazarları (yalnız ana seçimler değil)", "",
            "Bu tarama nesine_global.json kayıtlarındaki bütün sunulan pazarları kapsar. "
            "Aynı maçın farklı bahisleri bağımsız değildir. Ham fair_prob son kupon kalibrasyonu değildir.", ""]
    for ai, info in report["ais"].items():
        for day, entry in info["dates"].items():
            market = entry.get("market_prices")
            if not market:
                continue
            if market.get("error"):
                out.append(f"- {ai} {day}: fiyatlama dosyası okunamadı ({market['error']}).")
                continue
            q = market["coverage"]
            out.append(f"- {ai} {day}: {market['matches']} bülten maçı, "
                       f"{q.get('selections_total', 0)} pazar seçimi, "
                       f"{q.get('settled_selections', 0)} skorla karara bağlanabilen seçim.")
            groups = [(name, rec) for name, rec in market["families"].items()
                      if not name.startswith("DIRECT:") and rec["settled_choices"] >= 30]
            groups.sort(key=lambda x: x[1]["settled_choices"], reverse=True)
            for name, rec in groups[:8]:
                roi = f"%{100 * rec['flat_roi']:+.1f}" if rec["flat_roi"] is not None else "-"
                out.append(f"  - {name}: {rec['hits']}/{rec['settled_choices']} tercih; "
                           f"{rec['distinct_matches']} farklı maç; varsayımsal ROI {roi}.")
    out += ["", "## Gerçekten oynandığı bildirilen arşiv kayıtları", "",
            "Yalnız placed_bets dosyaları; öneri kuponları bunlara dahil edilmez. "
            "Ekran aktarımı ödeme sisteminden bağımsız kanıt değildir.", ""]
    for filename, item in report["placed_ledger"].items():
        out.append(f"- {filename}: {item['ticket_ids']} kimlikli kupon; "
                   f"{item['fully_specified_with_payout']} eksiksiz/ödeme bilgili; "
                   f"{len(item['excluded'])} eksik veya belirsiz.")
    out += ["", "## Güvenlik ve yöntem", "",
            "- Sonucu bilinmeyen maç kayıp sayılmaz; aynı kuponun ödemesi her bacakta tekrar sayılmaz.",
            "- Tahmini kaybeden ama pozitif EV olan seçim ile tutan ama negatif EV olan seçim ayrıştırılır.",
            "- Kalibrasyon ve strateji değişiklikleri, sonuç sonrası seçilmiş aynı maçlarla değil bağımsız ileri dönemle onaylanır.",
            "- Kupon tahminleri, ekran görüntülerinden aktarılmış oynanmış kupon kayıtlarından ayrıdır.", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, default=None,
                    help="Output folder. Default: reports/audits relative to the repository.")
    args = ap.parse_args(argv)
    root = args.root.resolve()
    out = args.out or (root / "reports/audits")
    if not out.is_absolute():
        out = root / out
    report = run(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / "ai_history_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "ai_history_audit.md").write_text(render(report), encoding="utf-8")
    total_choices = sum((entry.get("market_prices") or {}).get("coverage", {}).get("selections_total", 0)
                        for a in report["ais"].values() for entry in a["dates"].values())
    print(f"Audited {sum(v['overall']['rows'] for v in report['ais'].values())} prediction rows "
          f"and {total_choices} priced-market selections; results: {out / 'ai_history_audit.md'}")


if __name__ == "__main__":
    main()
