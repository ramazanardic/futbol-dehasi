"""Automated per-AI Nesine opening-vs-closing CLV ledger (Roadmap P0-1 & Gap Analysis §8 #3).

Strictly adheres to AGENTS.md / GEMINI.md isolation rules:
  * Reads and writes ONLY inside the active AI's own folder (`tahminler/<QUANTFOOT_AI>/`).
  * Never opens, lists, or touches any other AI's prediction folder.

Tracks every recommended pick (`mac_tahminleri.csv` & `kuponlar.csv`) with:
  - Taken soft odds (Nesine) and opening sharp fair probability (`p_open_sharp`)
  - Pre-kickoff sharp closing fair probability (`p_close_sharp`) updated via `update_closing_lines`
  - Exact Closing Line Value (`clv = odds_taken * p_close_sharp - 1.0`)
  - Opening-to-closing sharp steam (`steam_delta_p = p_close_sharp - p_open_sharp`)
  - Official settlement outcome (`won`) and 1u flat return
  - Statistical summary combining `clv_significance`, exact bin-free `corp_reliability_decomposition`,
    and `steam_aligned` vs `steam_against` splits.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from quantfoot.evaluation.auto_learn import market_family
from quantfoot.evaluation.clv_tracker import (
    clv_significance,
    compute_clv,
    corp_reliability_decomposition,
)
from quantfoot.evaluation.settlement import settle_selection


def _canonical_name(name: str | None) -> str:
    from quantfoot.markets.market_diagnosis import canonical_name
    return canonical_name(name)

TSI = dt.timezone(dt.timedelta(hours=3))


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(str(val).replace(",", "."))
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _entry_key(date_str: str, code: int, sel_name: str, source_file: str) -> str:
    return f"{date_str}|{code}|{sel_name}|{source_file}"


def load_ledger(ledger_path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if not ledger_path.exists():
        return records
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = rec.get("id")
        if key:
            records[str(key)] = rec
    return records


def save_ledger(ledger_path: Path, records: Mapping[str, Mapping[str, Any]]) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(records[k], ensure_ascii=False) for k in sorted(records.keys())]
    ledger_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _index_ng_selections(ng_payload: Mapping[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for m in ng_payload.get("matches") or []:
        try:
            code = int(m["code"])
        except (KeyError, TypeError, ValueError):
            continue
        ref = m.get("reference")
        if isinstance(ref, Mapping):
            ref_src = ref.get("source") or m.get("source")
        else:
            ref_src = (str(ref) if ref else None) or m.get("source")
        for sel in m.get("selections") or []:
            cname = _canonical_name(sel.get("name"))
            if not cname:
                continue
            out[(code, cname)] = {
                "fair_prob": _flt(sel.get("fair_prob")),
                "odds": _flt(sel.get("odds")),
                "direct": bool(sel.get("direct")),
                "ref_source": ref_src,
            }
    return out


def record_daily_picks(ai_dir: Path, date_str: str, *, ledger_path: Path | None = None) -> dict[str, Any]:
    """Snapshot an AI's daily `mac_tahminleri.csv` and `kuponlar.csv` picks into its own CLV ledger."""
    ai_root = Path(ai_dir).resolve()
    day_dir = ai_root / date_str
    lpath = ledger_path or (ai_root / "clv_defteri.jsonl")
    records = load_ledger(lpath)

    ng_path = day_dir / "nesine_global.json"
    ng_idx: dict[tuple[int, str], dict[str, Any]] = {}
    if ng_path.exists():
        ng_idx = _index_ng_selections(json.loads(ng_path.read_text(encoding="utf-8")))

    added = 0
    now_iso = dt.datetime.now(TSI).isoformat(timespec="minutes")

    for fname in ("mac_tahminleri.csv", "kuponlar.csv"):
        csv_path = day_dir / fname
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code_s = str(row.get("nesine_kodu") or row.get("code") or "").strip()
                if not code_s.isdigit():
                    continue
                code = int(code_s)
                cname = _canonical_name(row.get("secim_adi") or row.get("secim") or row.get("selection"))
                odds = _flt(row.get("nesine_oran") or row.get("odds"))
                p_open = _flt(row.get("olasilik") or row.get("p"))
                if not cname or odds is None or odds <= 1.01 or p_open is None or not (0.0 < p_open < 1.0):
                    continue
                key = _entry_key(date_str, code, cname, fname)
                if key in records:
                    continue
                ng_info = ng_idx.get((code, cname)) or {}
                p_sharp_open = ng_info.get("fair_prob") or p_open
                records[key] = {
                    "id": key,
                    "date": date_str,
                    "code": code,
                    "match": row.get("mac") or "",
                    "source_file": fname,
                    "selection": cname,
                    "family": market_family(cname),
                    "odds_taken": round(odds, 4),
                    "p_model": round(p_open, 5),
                    "p_open_sharp": round(float(p_sharp_open), 5),
                    "ev_open": round(float(p_sharp_open) * odds - 1.0, 5),
                    "direct": bool(ng_info.get("direct")),
                    "ref_source": ng_info.get("ref_source") or row.get("fiyat_kaynagi") or "",
                    "recorded_at": now_iso,
                    "p_close_sharp": None,
                    "clv": None,
                    "steam_delta_p": None,
                    "won": None,
                    "flat_pnl": None,
                }
                added += 1

    save_ledger(lpath, records)
    return {"ledger_path": str(lpath), "added": added, "total_entries": len(records)}


def update_closing_lines(
    ledger_path: Path,
    closing_ng_payload: Mapping[str, Any],
    *,
    date_filter: str | None = None,
) -> dict[str, Any]:
    """Match pre-kickoff sharp closing probabilities from a closing `nesine_global.json` snapshot."""
    records = load_ledger(ledger_path)
    close_idx = _index_ng_selections(closing_ng_payload)
    updated = 0
    now_iso = dt.datetime.now(TSI).isoformat(timespec="minutes")

    for rec in records.values():
        if date_filter and rec.get("date") != date_filter:
            continue
        code = int(rec["code"])
        cname = str(rec["selection"])
        info = close_idx.get((code, cname))
        if not info or info.get("fair_prob") is None:
            continue
        p_close = float(info["fair_prob"])
        if not (0.0 < p_close < 1.0):
            continue
        odds_taken = float(rec["odds_taken"])
        p_open = float(rec["p_open_sharp"])
        rec["p_close_sharp"] = round(p_close, 5)
        rec["clv"] = round(compute_clv(odds_taken, closing_fair_prob=p_close), 5)
        rec["steam_delta_p"] = round(p_close - p_open, 5)
        rec["closed_at"] = now_iso
        updated += 1

    save_ledger(ledger_path, records)
    return {"updated_closing": updated, "total_entries": len(records)}


def settle_ledger(
    ledger_path: Path,
    results_by_code: Mapping[int, Mapping[str, Any]],
    *,
    date_filter: str | None = None,
) -> dict[str, Any]:
    """Settle completed picks in the CLV ledger using official HT/FT90 results."""
    records = load_ledger(ledger_path)
    settled = 0

    for rec in records.values():
        if date_filter and rec.get("date") != date_filter:
            continue
        if rec.get("won") is not None:
            continue
        res = results_by_code.get(int(rec["code"]))
        if not res or not res.get("completed"):
            continue
        try:
            won = settle_selection(str(rec["selection"]), tuple(res["ht"]), tuple(res["ft90"]))
        except (ValueError, KeyError, IndexError):
            won = None
        if won is None:
            continue
        odds = float(rec["odds_taken"])
        rec["won"] = bool(won)
        rec["flat_pnl"] = round((odds - 1.0) if won else -1.0, 4)
        settled += 1

    save_ledger(ledger_path, records)
    return {"settled": settled, "total_entries": len(records)}


def summarize_clv_ledger(ledger_path: Path) -> dict[str, Any]:
    """Compute CLV significance, CORP reliability, steam-direction split, and family metrics."""
    records = list(load_ledger(ledger_path).values())
    clvs = [float(r["clv"]) for r in records if r.get("clv") is not None]
    clv_rep = clv_significance(clvs)

    settled = [r for r in records if r.get("won") is not None]
    if settled:
        y_true = np.array([1.0 if r["won"] else 0.0 for r in settled], dtype=float)
        y_prob = np.array([float(r["p_model"]) for r in settled], dtype=float)
        corp = corp_reliability_decomposition(y_true, y_prob).__dict__
        flat_roi = round(float(np.mean([float(r["flat_pnl"]) for r in settled])), 5)
        hit_rate = round(float(np.mean(y_true)), 5)
    else:
        corp = None
        flat_roi = None
        hit_rate = None

    by_steam: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_family[str(r.get("family") or "Diğer")].append(r)
        dp = r.get("steam_delta_p")
        if dp is not None:
            if float(dp) >= 0.02:
                by_steam["steam_aligned (>=+2pp)"].append(r)
            elif float(dp) <= -0.02:
                by_steam["steam_against (<=-2pp)"].append(r)
            else:
                by_steam["steam_neutral (-2pp..+2pp)"].append(r)

    def _bucket_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
        c_vals = [float(x["clv"]) for x in items if x.get("clv") is not None]
        s_items = [x for x in items if x.get("won") is not None]
        return {
            "n": len(items),
            "n_clv": len(c_vals),
            "mean_clv": round(float(np.mean(c_vals)), 5) if c_vals else None,
            "n_settled": len(s_items),
            "hit_rate": round(float(np.mean([1.0 if x["won"] else 0.0 for x in s_items])), 5) if s_items else None,
            "flat_roi": round(float(np.mean([float(x["flat_pnl"]) for x in s_items])), 5) if s_items else None,
        }

    return {
        "total_entries": len(records),
        "n_with_closing_clv": len(clvs),
        "n_settled": len(settled),
        "hit_rate": hit_rate,
        "flat_roi": flat_roi,
        "clv_report": clv_rep.__dict__,
        "corp_calibration": corp,
        "by_steam_direction": {k: _bucket_stats(v) for k, v in sorted(by_steam.items())},
        "by_family": {k: _bucket_stats(v) for k, v in sorted(by_family.items())},
    }
