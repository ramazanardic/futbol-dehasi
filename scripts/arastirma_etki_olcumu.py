"""Araştırma notlarının etkisini ölçer (t190u): veto / uyarı / onay bacaklarının gerçekleşme oranı ile modelin P'sini karşılaştırır.

  python scripts/arastirma_etki_olcumu.py [--bas 2026-11-28] [--bit 2026-12-31] [--cikti reports/research/arastirma_etki.md]

Her gün için ``tahminler/<QUANTFOOT_AI>/arastirma/<gün>/*.json`` notları ile aynı günün ``nesine_global.json`` bacak olasılıkları
(``fair_prob``) ve Nesine sonuçları eşleştirilir. Bacak başına bir satır: (not kararı, seçim, P, gerçekleşti mi).
Karar ``*`` ise maçın kupon-adayı bacaklarının (P >= 0.62, oran >= 1.20) hepsine uygulanır.
Gruplarda n < 50 iken yalnız "yetersiz veri" denir (yorum yok). Okuma: veto grubunda gerçekleşme < ortalama P ise veto bacakları
gerçekten daha kötü çıkmış (not işe yarıyor); onay grubunda gerçekleşme >= P ise onay zarar vermiyor. Olasılığa dokunulmaz.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.data import arastirma_notu as AN
from quantfoot.evaluation.settlement import settle_selection
from quantfoot.markets.market_diagnosis import canonical_name

MIN_N = 50
LEG_MIN_P = 0.62
LEG_MIN_ODDS = 1.20
GROUPS = ("veto", "uyari", "onay")


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def _day_matches(day: str) -> dict[str, dict]:
    files = sorted(ROOT.glob(f"tahminler/*/{day}/nesine_global.json"), key=lambda p: (("grokbottahmin" not in str(p)), -p.stat().st_mtime))
    for f in files:
        try:
            return {str(m["code"]): m for m in json.loads(f.read_text(encoding="utf-8"))["matches"]}
        except (OSError, ValueError, KeyError):
            continue
    return {}


def leg_rows(note: dict, match: dict | None, result: dict | None) -> list[dict]:
    """Notun kararları -> bacak satırları. ``match`` nesine_global kaydı (selections), ``result`` {'completed','ht','ft90'}."""
    if not match:
        return []
    sels = {canonical_name(s.get("name")): s for s in match.get("selections") or []}
    rows = []
    for d in note.get("bacak_kararlari") or []:
        if d.get("karar") not in AN.DECISIONS:
            continue
        key = AN.normalize_selection(d.get("secim"))
        if key == AN.ALL_LEGS:
            names = [n for n, s in sels.items() if (s.get("fair_prob") or 0) >= LEG_MIN_P and (s.get("odds") or 0) >= LEG_MIN_ODDS]
        else:
            names = [key] if key in sels else []
        for n in names:
            s = sels[n]
            hit = None
            if result and result.get("completed"):
                try:
                    hit = settle_selection(s.get("name", n), tuple(result["ht"]), tuple(result["ft90"]))
                except (ValueError, TypeError):
                    hit = None
            rows.append({"kod": str(match["code"]), "mac": f"{match['home']} - {match['away']}", "secim": n, "karar": d["karar"],
                         "p": s.get("fair_prob"), "oran": s.get("odds"), "gerceklesti": hit})
    return rows


def summarize(rows: list[dict]) -> dict:
    out = {}
    for g in GROUPS:
        rs = [r for r in rows if r["karar"] == g]
        settled = [r for r in rs if r["gerceklesti"] is not None and r["p"] is not None]
        n = len(settled)
        k = sum(1 for r in settled if r["gerceklesti"])
        mp = sum(r["p"] for r in settled) / n if n else None
        rec = {"bacak": len(rs), "sonuclanan": n, "isabet": k, "gerceklesme": (k / n if n else None), "ortalama_p": mp}
        if n < MIN_N:
            rec["yorum"] = f"yetersiz veri (n={n} < {MIN_N})"
        else:
            lo, hi = _wilson(k, n)
            rec["wilson95"] = [round(lo, 3), round(hi, 3)]
            gap = k / n - mp
            rec["fark"] = round(gap, 3)
            if g == "veto":
                rec["yorum"] = ("veto işe yarıyor: gerçekleşme P'nin altında" if hi < mp
                                else "veto kanıtlanmadı: gerçekleşme P ile uyumlu/üstünde (vetolar fazla temkinli olabilir)")
            else:
                rec["yorum"] = ("gerçekleşme P'nin altında (model bu grupta iyimser)" if hi < mp
                                else "P'nin üstünde" if lo > mp else "P ile uyumlu")
        out[g] = rec
    return out


def to_markdown(rows: list[dict], summ: dict, days: list[str]) -> str:
    md = [f"# Araştırma notu etki ölçümü ({days[0] if days else '-'} → {days[-1] if days else '-'})", "",
          f"Not günleri: {len(days)} · bacak satırı: {len(rows)} · n < {MIN_N} olan grup için yalnız 'yetersiz veri'.", "",
          "| Grup | Bacak | Sonuçlanan | İsabet | Gerçekleşme | Ort. P | Yorum |", "|---|---|---|---|---|---|---|"]
    for g in GROUPS:
        s = summ[g]
        md.append(f"| {g} | {s['bacak']} | {s['sonuclanan']} | {s['isabet']} | "
                  f"{'-' if s['gerceklesme'] is None else format(s['gerceklesme'] * 100, '.1f') + '%'} | "
                  f"{'-' if s['ortalama_p'] is None else format(s['ortalama_p'] * 100, '.1f') + '%'} | {s['yorum']} |")
    return "\n".join(md) + "\n"


def collect(days: list[str], results: dict[int, dict], root: Path | None = None) -> list[dict]:
    rows: list[dict] = []
    for day in days:
        notes = AN.load_day(day, root)
        if not notes:
            continue
        ms = _day_matches(day)
        for code, note in notes.items():
            rows += [{**r, "gun": day} for r in leg_rows(note, ms.get(code), results.get(int(code)) if str(code).isdigit() else None)]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bas")
    ap.add_argument("--bit")
    ap.add_argument("--cikti")
    a = ap.parse_args()
    base = AN.default_root()
    days = sorted(p.name for p in base.glob("*") if p.is_dir()) if base.exists() else []
    if a.bas:
        days = [d for d in days if d >= a.bas]
    if a.bit:
        days = [d for d in days if d <= a.bit]
    results: dict[int, dict] = {}
    if days:
        from quantfoot.data.nesine import fetch_results

        dates = sorted({x for d in days for x in (d, (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat())})
        results = fetch_results(dates)
    rows = collect(days, results)
    summ = summarize(rows)
    md = to_markdown(rows, summ, days)
    out = Path(a.cikti) if a.cikti else ROOT / "reports" / "research" / "arastirma_etki.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps({"gruplar": summ, "satirlar": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(md)
    print("->", out)


if __name__ == "__main__":
    main()
