"""Write Claude's predictions of a betting day into its own area of the AI comparison (tahminler/claudetahmin).

    python scripts/ai_tahmin.py --tarih 2026-11-20

The user compares four AIs (claudetahmin, geminitahmin, antigravitytahmin, chatgbttahmin); every AI writes only to
tahminler/<its area>/<date>/ in the common format described in tahminler/README.md:

  mac_tahminleri.csv  one row per Nesine match: 1X2 probabilities, expected goals, most likely score and the main
                      pick (the most probable bettable selection under the coupon rules, gunluk_analiz.best_pick)
  kuponlar.csv        one row per coupon leg: every coupon of the day's latest coupon file for each target

Sources: reports/daily/<date>/nesine_global.json (+ predictions store) and kupon_*x_*.json. Run by the morning job,
after every coupon build and at each line-up re-analysis, so the area always holds the latest version.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gunluk_analiz import best_pick  # noqa: E402
from nesine_global import DAILY, NESINE_ONLY_STATUS, PREDICTIONS_FILE, TSI, classify_price_tier  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "tahminler" / "claudetahmin"

MATCH_COLS = ["tarih", "saat", "lig", "mac", "nesine_kodu", "olasilik_1", "olasilik_X", "olasilik_2",
              "beklenen_gol_ev", "beklenen_gol_dep", "en_olasi_skor", "ana_secim_pazar", "ana_secim",
              "nesine_oran", "olasilik", "fiyat_kaynagi", "guven", "not"]
COUPON_COLS = ["tarih", "kupon", "kupon_no", "kupon_toplam_oran", "kupon_tutma_olasiligi", "saat", "mac",
               "nesine_kodu", "pazar", "secim", "nesine_oran", "olasilik"]


def _pct(x) -> str:
    return "" if x is None else f"{float(x):.4f}"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def match_rows(date: str, frozen: dict[str, dict] | None = None, now: dt.datetime | None = None) -> list[dict]:
    """Rows for every match; a match that has kicked off keeps the row written before kick-off (``frozen``),
    so later re-analyses never change a prediction after the fact."""
    frozen = frozen or {}
    now = now or dt.datetime.now(TSI)
    d = DAILY / date
    data = json.loads((d / "nesine_global.json").read_text(encoding="utf-8"))
    store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8")) if (d / PREDICTIONS_FILE).exists() else {}
    rows = []
    for m in sorted(data["matches"], key=lambda x: x["kickoff"]):
        tier = m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))
        if tier == "ozel_bahis":
            continue
        if str(m["code"]) in frozen and dt.datetime.fromisoformat(m["kickoff_iso"]) <= now:
            rows.append(frozen[str(m["code"])])
            continue
        priced = m["status"] in ("fiyatlandı", NESINE_ONLY_STATUS)
        f = (m.get("fair_1x2") or [None] * 3) if priced else [None] * 3
        dist = (store.get(str(m["code"])) or {}).get("dist") or {}
        top = next(iter((dist.get("ft") or {}).items()), None)
        pick, why = best_pick(m) if priced else (None, "global fiyat yok")
        rows.append({
            "tarih": date, "saat": m["kickoff"][11:16], "lig": m["league"], "mac": f"{m['home']} - {m['away']}",
            "nesine_kodu": m["code"], "olasilik_1": _pct(f[0]), "olasilik_X": _pct(f[1]), "olasilik_2": _pct(f[2]),
            "beklenen_gol_ev": m.get("mu_home") if priced else "", "beklenen_gol_dep": m.get("mu_away") if priced else "",
            "en_olasi_skor": f"{top[0]} ({top[1]:.3f})" if top else "",
            "ana_secim_pazar": pick["market"] if pick else "", "ana_secim": pick["selection"] if pick else "",
            "nesine_oran": pick["odds"] if pick else "", "olasilik": _pct(pick["fair_prob"]) if pick else "",
            "fiyat_kaynagi": (m.get("reference") or "") if priced else "",
            "guven": {"keskin": "yüksek", "global_buro": "orta", "dusuk_guven": "düşük"}.get(tier, ""),
            "not": "" if pick and not why else (why or ""),
        })
    return rows


def coupon_rows(date: str) -> list[dict]:
    latest: dict[str, Path] = {}
    for f in sorted((DAILY / date).glob("kupon_*x_*.json")):
        latest[f.name.split("_")[1]] = f  # HHMM order: latest file per target wins
    rows = []
    for _, f in sorted(latest.items(), key=lambda kv: float(kv[0].rstrip("x"))):
        data = json.loads(f.read_text(encoding="utf-8"))
        for i, c in enumerate(data.get("coupons", []), 1):
            for leg in c["legs"]:
                rows.append({"tarih": date, "kupon": f.stem, "kupon_no": i, "kupon_toplam_oran": c["nesine_odds"],
                             "kupon_tutma_olasiligi": _pct(c["probability"]), "saat": leg["kickoff"][11:16],
                             "mac": leg["match"], "nesine_kodu": leg["code"], "pazar": leg["market"],
                             "secim": leg["selection"], "nesine_oran": leg["odds"], "olasilik": _pct(leg["p"])})
    return rows


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM: opens correctly in Excel
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def export(date: str, area: Path = AREA, now: dt.datetime | None = None) -> tuple[int, int]:
    out = area / date
    frozen = {r["nesine_kodu"]: r for r in _read(out / "mac_tahminleri.csv")}
    m, c = match_rows(date, frozen, now), coupon_rows(date)
    _write(out / "mac_tahminleri.csv", MATCH_COLS, m)
    _write(out / "kuponlar.csv", COUPON_COLS, c)
    return len(m), len(c)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    args = ap.parse_args()
    n_m, n_c = export(args.tarih)
    print(f"claudetahmin {args.tarih}: {n_m} maç tahmini, {n_c} kupon bacağı -> {AREA / args.tarih}")


if __name__ == "__main__":
    main()
