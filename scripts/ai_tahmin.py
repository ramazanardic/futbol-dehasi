"""Write this AI's OWN predictions of a betting day into tahminler/<QUANTFOOT_AI>/.

    python scripts/ai_tahmin.py --tarih 2026-11-20

The user compares AIs (claudetahmin, geminitahmin, antigravitytahmin, chatgbttahmin, grokbottahmin). Code, algorithms and
data sources are shared, but every AI produces its own predictions (user rule, 20 Nov): this area is never copied
from the shared reports (reports/daily, which other AIs' runs also write). Instead:

  * the match predictions come from a fresh analysis run made here (nesine_global.analyze_day: live Nesine bulletin,
    sharp global prices, research), and
  * the coupons are the ones Claude builds with scripts/nesine_kupon.py, which writes them ONLY into this area
    (kupon_<target>x_<HHMM>.json/.md, one file per build), never into the shared reports.

Output per day, in the common format of tahminler/README.md:
  mac_tahminleri.csv  one row per Nesine match: 1X2 probabilities, expected goals, most likely score and the main
                      pick (the most probable bettable selection under the coupon rules, gunluk_analiz.best_pick)
  kuponlar.csv        one row per coupon leg of Claude's latest coupon file for each target
Rows of matches that have kicked off are frozen, so later runs never change a prediction after the fact.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kupon_dosyalari import coupon_group, latest_coupons
from gunluk_analiz import best_pick  # noqa: E402
import nesine_global as ng  # noqa: E402

TSI = ng.TSI
ROOT = Path(__file__).resolve().parents[1]
AREA = ng.DAILY  # tahminler/<QUANTFOOT_AI>/ (required)

MATCH_COLS = ["tarih", "saat", "lig", "mac", "nesine_kodu", "olasilik_1", "olasilik_X", "olasilik_2",
              "beklenen_gol_ev", "beklenen_gol_dep", "en_olasi_skor", "ana_secim_pazar", "ana_secim",
              "nesine_oran", "olasilik", "fiyat_kaynagi", "guven", "not", "secim_adi"]
COUPON_COLS = ["tarih", "kupon_turu", "kupon", "kupon_no", "kupon_toplam_oran", "kupon_tutma_olasiligi", "saat", "mac",
               "nesine_kodu", "pazar", "secim", "nesine_oran", "olasilik", "secim_adi", "kural_oncesi_olasilik"]


def _pct(x) -> str:
    return "" if x is None else f"{float(x):.4f}"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def own_analysis(date: str) -> list[dict]:
    """Claude's own run of the shared pipeline (no files of the shared reports are read or written)."""
    matches, _, _ = ng.analyze_day(dt.date.fromisoformat(date), verbose=False)
    return matches


def _top_score(code) -> str:
    priced = ng.PRICED.get(int(code))
    if not priced:
        return ""
    k, v = next(iter(ng.score_distributions(priced["joint"])["ft"].items()))
    return f"{k} ({v:.3f})"


def kickoff_date(kickoff: str | None, fallback: str) -> str:
    """Takvim günü = Nesine'nin başlama zamanı (ESD/MD) — bahis günü değil.

    Nesine bülteni bir "bahis günü"nü 07:00'den ertesi sabah 06:59'a kadar verir; 00:00 sonrası maçlar ertesi
    takvim gününe aittir (22 Kas denetimi: 23 Kas 00:00–04:10 maçları 22 Kas diye yazılmıştı).
    """
    ko = (kickoff or "").strip()
    try:
        return dt.date.fromisoformat(ko[:10]).isoformat()
    except ValueError:
        return fallback


def match_rows(date: str, matches: list[dict], frozen: dict[str, dict] | None = None,
               now: dt.datetime | None = None) -> list[dict]:
    frozen = frozen or {}
    now = now or dt.datetime.now(TSI)
    rows = []
    for m in sorted(matches, key=lambda x: x["kickoff"]):
        tier = m.get("price_tier") or ng.classify_price_tier(m["status"], m.get("reference"))
        if tier == "ozel_bahis":
            continue
        if dt.datetime.fromisoformat(m["kickoff_iso"]) <= now:
            if str(m["code"]) in frozen:
                # donmuş satır olduğu gibi kalır; yalnız (eski sürümün yanlış yazdığı) takvim günü düzeltilir
                rows.append({**frozen[str(m["code"])], "tarih": kickoff_date(m["kickoff"], date)})
            continue
        priced = m["status"] in ("fiyatlandı", ng.NESINE_ONLY_STATUS)
        f = (m.get("fair_1x2") or [None] * 3) if priced else [None] * 3
        pick, why = best_pick(m) if priced else (None, "global fiyat yok")
        rows.append({
            "tarih": kickoff_date(m["kickoff"], date), "saat": m["kickoff"][11:16], "lig": m["league"], "mac": f"{m['home']} - {m['away']}",
            "nesine_kodu": m["code"], "olasilik_1": _pct(f[0]), "olasilik_X": _pct(f[1]), "olasilik_2": _pct(f[2]),
            "beklenen_gol_ev": m.get("mu_home") if priced else "", "beklenen_gol_dep": m.get("mu_away") if priced else "",
            "en_olasi_skor": _top_score(m["code"]) if priced else "",
            "ana_secim_pazar": pick["market"] if pick else "", "ana_secim": pick["selection"] if pick else "",
            "nesine_oran": pick["odds"] if pick else "", "olasilik": _pct(pick["fair_prob"]) if pick else "",
            "fiyat_kaynagi": (m.get("reference") or "") if priced else "",
            "guven": {"keskin": "yüksek", "global_buro": "orta", "dusuk_guven": "düşük"}.get(tier, ""),
            "not": "" if pick and not why else (why or ""),
            "secim_adi": pick.get("name", "") if pick else "",  # settlement name, read by gun_degerlendirme.py
        })
    # a frozen (started) match that dropped out of the bulletin keeps its pre-kick-off row
    seen = {str(r["nesine_kodu"]) for r in rows}
    rows += [r for code, r in frozen.items() if code not in seen]
    return sorted(rows, key=lambda r: (r.get("tarih") or "", r.get("saat") or ""))


def coupon_files(date: str, area: Path = AREA) -> list[Path]:
    """This AI's coupon files of the day (written by nesine_kupon.py into this area), latest per target."""
    latest = latest_coupons(area / date)
    return [latest[k] for k in sorted(latest, key=lambda g: (g[1] != "karma", g[1], float(g[0].rstrip("x"))))]


def coupon_rows(date: str, area: Path = AREA) -> list[dict]:
    rows = []
    for f in coupon_files(date, area):
        data = json.loads(f.read_text(encoding="utf-8"))
        for i, c in enumerate(data.get("coupons", []), 1):
            for leg in c["legs"]:
                rows.append({"tarih": kickoff_date(leg.get("kickoff"), date), "kupon_turu": coupon_group(f)[1], "kupon": f.stem, "kupon_no": i, "kupon_toplam_oran": c["nesine_odds"],
                             "kupon_tutma_olasiligi": _pct(c["probability"]), "saat": leg["kickoff"][11:16],
                             "mac": leg["match"], "nesine_kodu": leg["code"], "pazar": leg["market"],
                             "secim": leg["selection"], "nesine_oran": leg["odds"], "olasilik": _pct(leg["p"]),
                             "kural_oncesi_olasilik": leg.get("p_before_rules", ""), "secim_adi": leg.get("name", "")})
    return rows


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM: opens correctly in Excel
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def record_clv(out: Path, picks: list[dict], matches: list[dict], now: dt.datetime) -> dict:
    """Closing price of every main pick (user, 21 Nov: CLV for all predictions, not only coupon legs).

    Each analysis run before kick-off updates the pick's last seen global probability; the first one stays as the
    probability the pick was made at. CLV = closing - pick probability: a sharp market moving towards our picks
    (positive CLV) is evidence of skill long before results are. -> tahmin_clv.json in the AI's day folder."""
    path = out / "tahmin_clv.json"
    clv = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    by = {str(m["code"]): m for m in matches}
    for r in picks:
        name, code = (r.get("secim_adi") or "").strip(), str(r.get("nesine_kodu") or "")
        m = by.get(code)
        if not name or not m or not r.get("olasilik") or dt.datetime.fromisoformat(m["kickoff_iso"]) <= now:
            continue
        s = next((x for x in m.get("selections") or [] if x.get("name") == name), None)
        rec = clv.setdefault(f"{code}|{name}", {"match": r.get("mac"), "pick": name, "p_pick": float(r["olasilik"]),
                                                "first_seen": now.isoformat(timespec="minutes")})
        if s and m.get("status") == "fiyatlandı":
            rec.update(p_close=s["fair_prob"], close_seen=now.isoformat(timespec="minutes"))
    out.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clv, ensure_ascii=False, indent=1), encoding="utf-8")
    return clv


def clv_summary(clv: dict) -> dict:
    d = [v["p_close"] - v["p_pick"] for v in clv.values() if v.get("p_close") is not None]
    return {"n": len(d), "mean": sum(d) / len(d) if d else None, "positive": sum(1 for x in d if x > 0)}


def export(date: str, matches: list[dict] | None = None, area: Path = AREA,
           now: dt.datetime | None = None) -> tuple[int, int]:
    """``matches``: an analysis this AI just ran (e.g. inside nesine_kupon.py); None = run one now."""
    out = area / date
    before = _read(out / "mac_tahminleri.csv")
    frozen = {r["nesine_kodu"]: r for r in before}
    matches = own_analysis(date) if matches is None else matches
    m = match_rows(date, matches, frozen, now)
    c = coupon_rows(date, area)
    _write(out / "mac_tahminleri.csv", MATCH_COLS, m)
    _write(out / "kuponlar.csv", COUPON_COLS, c)
    if area == AREA:
        apply_research_picks(date)
        m = _read(out / "mac_tahminleri.csv")
    record_clv(out, before + m, matches, now or dt.datetime.now(TSI))
    return len(m), len(c)


def apply_research_picks(date: str) -> None:
    """One main-pick rule whatever runs last (21 Nov): simulation's best triple-confirmed bet, else the deep-research
    pick, else the most probable selection written above. A fresh export must not undo the research."""
    out = AREA / date
    if not (out / "derin_tahminler.json").exists():
        return
    import derin_tahmin as dtah
    import simulasyon
    if (out / "simulasyon.json").exists():
        simulasyon.update_picks(date, json.loads((out / "simulasyon.json").read_text(encoding="utf-8")))
    else:
        dtah.update_table(date, json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8")))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    args = ap.parse_args()
    n_m, n_c = export(args.tarih)
    print(f"{ng.AI_NAME} {args.tarih}: {n_m} maç tahmini (kendi analiz çalıştırması), {n_c} kupon bacağı -> {AREA / args.tarih}")


if __name__ == "__main__":
    main()
