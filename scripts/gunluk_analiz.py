"""One-page analysis of every Nesine match of a betting day, built fresh from that day's run.

    python scripts/gunluk_analiz.py --tarih 2026-11-20      # after nesine_global.py for the same day

Per match: price source and reliability, research (form, table, rest, absences), 1X2, expected goals, 2.5 Over,
BTTS, the three most likely scores, the most likely HT/FT, and the most probable bettable selection (Nesine odds
>= 1.20) under the coupon rules learned from the tracked results (no model HT/FT or second-half result legs,
no low-confidence prices, no correct-score style legs). Output: reports/daily/<date>/gunluk_analiz.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import (  # noqa: E402
    DAILY,
    NESINE_ONLY_STATUS,
    PREDICTIONS_FILE,
    TSI,
    classify_price_tier,
    is_sharp_source,
)
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition  # noqa: E402

EXCLUDED_MODEL = ("İY/MS", "2Y 0", "2Y 1", "2Y 2")
MID_GLOBAL_MIN_PROB = 0.62


def _has_full_research(m: dict) -> bool:
    r = m.get("research") or {}
    teams = r.get("teams") or {}
    tm = r.get("tm_absences") or {}
    return bool((teams.get("home") and teams.get("away")) or (tm.get("home") and tm.get("away")) or r.get("user_absences"))


def _form(r: dict, side: str) -> str:
    t = ((r or {}).get("teams") or {}).get(side) or {}
    tm = ((r or {}).get("tm_absences") or {}).get(side) or {}
    bits = []
    if t.get("form"):
        bits.append(t["form"])
    tab = t.get("table") or {}
    if tab.get("rank"):
        bits.append(f"{int(tab['rank'])}./{tab['size']}")
    elif tm.get("rank"):
        pts = f" {tm['points']}p" if tm.get("points") is not None else ""
        bits.append(f"TM #{tm['rank']}{pts}")
    if t.get("rest_days") not in (None, "-"):
        bits.append(f"{t['rest_days']}g dinlenme")
    out = [x["name"] for x in t.get("likely_absent") or [] if "rotasyon" not in x.get("reason", "")][:2]
    if out:
        bits.append("yok: " + ", ".join(out))
    if tm.get("gk1_out"):
        bits.append("⚠ 1.kaleci yok")
    elif tm.get("top_scorer_out"):
        bits.append("⚠ golcü yok")
    elif tm.get("critical_absences"):
        bits.append(f"{len(tm['critical_absences'])} kilit eksik")
    return " · ".join(bits) or "-"


def best_pick(m: dict) -> tuple[dict | None, str]:
    """Most probable selection with Nesine odds >= 1.20 that the coupon rules allow; reason when none."""
    tier = m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))
    if tier == "ozel_bahis":
        return None, "özel bahis (maç değil)"
    if tier == "dusuk_guven" or m["status"] == NESINE_ONLY_STATUS:
        return None, "düşük güven: kupona alınmaz"
    if m["status"] != "fiyatlandı":
        return None, "global fiyat yok"
    is_sharp = is_sharp_source(m.get("reference"))
    min_p = 0.55  # coupon leg floor (user rule); a 9 % pick was once shown as "most reliable"
    if not is_sharp:
        if not (m.get("reference") or "").startswith(("OddsMath (", "OddsPapi (", "API-Football (")):
            return None, "yalnız ESPN fiyatı (keskin değil)"
        r = m.get("research") or {}
        if not _has_full_research(m):
            return None, "orta güven — araştırma eksik, kupona alınmaz"
        if r.get("flags"):
            return None, "orta güven — risk/steam uyarısı var, kupona alınmaz"
        if is_uncalibrated_competition(m.get("league")):
            return None, "orta güven — kalibre edilmemiş yarışma"
        min_p = MID_GLOBAL_MIN_PROB
    ok = [s for s in m["selections"] if s["odds"] >= 1.20 and s["fair_prob"] >= min_p and s["ev"] <= 0.25
          and (s.get("direct") or not s["name"].startswith(EXCLUDED_MODEL))
          and "Skor" not in s["name"] and not s["name"].startswith("İki Yarıda")]
    if not ok:
        return None, ("orta güven — %62+ uygun seçim yok" if not is_sharp else "1,20+ uygun seçim yok")
    return max(ok, key=lambda s: (s["fair_prob"], s["odds"])), ("" if is_sharp else "orta güven · araştırmalı")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    args = ap.parse_args()
    d = DAILY / args.tarih
    data = json.loads((d / "nesine_global.json").read_text(encoding="utf-8"))
    store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8")) if (d / PREDICTIONS_FILE).exists() else {}
    ms = sorted(data["matches"], key=lambda m: m["kickoff"])
    real_ms = [m for m in ms if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) != "ozel_bahis"]
    sharp_ms = [m for m in real_ms if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) == "keskin"]
    book_ms = [m for m in real_ms if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) == "global_buro"]
    low = [m for m in real_ms if (m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))) == "dusuk_guven"]
    no_price = len(real_ms) - len(sharp_ms) - len(book_ms) - len(low)
    n_res = sum(1 for m in real_ms if (m.get("research") or {}).get("teams") or (m.get("research") or {}).get("tm_absences"))
    n_spec = len(ms) - len(real_ms)
    spec_txt = f" (+{n_spec} haftalık özel bahis)" if n_spec else ""
    lines = [f"# {args.tarih} — günün bütün maçları ({len(real_ms)} maç{spec_txt}, analiz {data['generated_at'][11:16]} TSİ)", "",
             f"Global fiyatlı toplam: **{len(sharp_ms) + len(book_ms)}/{len(real_ms)}** "
             f"(**{len(sharp_ms)}** keskin borsa/Pinnacle/BetInAsia · **{len(book_ms)}** global büro orta güven) · "
             f"düşük güven (yalnız Nesine): **{len(low)}** · fiyatsız: {no_price} · "
             f"canlı araştırma (ESPN + Transfermarkt): **{n_res}** maç.", "",
             "Dünkü sonuçlardan uygulanan dersler: **keskin global** fiyatlı maçlar ile **iki takımı da araştırılmış, "
             "uyarısız ve ≥%62 olasılıklı orta güven global büro** (Marathonbet/1XBET) maçları (+2 puan ek belirsizlik "
             "payıyla) kupona aday olabilir; düşük güvenli (yalnız Nesine) tahminler kupona asla girmez; modelden "
             "türetilen İY/MS ve 2. yarı sonucu bacak olmaz.", "",
             "| Saat | Lig | Maç | Kaynak | 1 / X / 2 | Gol (ev-dep) | 2,5Ü | KG | En olası skorlar | En olası İY/MS | "
             "En güvenilir tercih (Nesine ≥1,20) | Ev (form / TM) | Dep (form / TM) |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in real_ms:
        if m["status"] not in ("fiyatlandı", NESINE_ONLY_STATUS):
            lines.append(f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | fiyat yok | - | - | - | - | - | - | - | {_form(m.get('research'), 'home')} | {_form(m.get('research'), 'away')} |")
            continue
        sel = {s["name"]: s["fair_prob"] for s in m["selections"]}
        f1x2 = m.get("fair_1x2") or [None] * 3
        dist = (store.get(str(m["code"])) or {}).get("dist") or {}
        scores = ", ".join(f"{k} %{v * 100:.0f}" for k, v in list((dist.get("ft") or {}).items())[:3]) or "-"
        htft = next(iter((dist.get("htft") or {}).items()), None)
        pick, why = best_pick(m)
        tag = f", {why}" if pick and why else ""
        pick_s = (f"{pick['market']}: {pick['selection']} — %{pick['fair_prob'] * 100:.0f}, {pick['odds']:.2f} "
                  f"({'doğrudan' if pick.get('direct') else 'model'}{tag})") if pick else f"_{why}_"
        tier = m.get("price_tier") or classify_price_tier(m["status"], m.get("reference"))
        if tier == "dusuk_guven":
            src = "düşük güven"
        elif tier == "global_buro":
            src = f"{m['reference']} [orta]"
        else:
            src = m["reference"].replace(" (football-data)", "").replace(" (borsa)", "")
        warn = []
        if m["mu_home"] + m["mu_away"] > 5:
            warn.append("aşırı gol beklentisi")
        if (m.get("research") or {}).get("flags"):
            warn.append("⚠ " + "; ".join(m["research"]["flags"]))
        lines.append(
            f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | {src}{' · ' + ' · '.join(warn) if warn else ''} | "
            + (f"%{f1x2[0] * 100:.0f} / %{f1x2[1] * 100:.0f} / %{f1x2[2] * 100:.0f}" if f1x2[0] is not None else "-")
            + f" | {m['mu_home']:.2f}-{m['mu_away']:.2f} | "
            f"{'%' + format(sel['2.5 Üst'] * 100, '.0f') if '2.5 Üst' in sel else '-'} | "
            f"{'%' + format(sel['KG Var'] * 100, '.0f') if 'KG Var' in sel else '-'} | {scores} | "
            f"{(htft[0] + ' %' + format(htft[1] * 100, '.0f')) if htft else '-'} | {pick_s} | "
            f"{_form(m.get('research'), 'home')} | {_form(m.get('research'), 'away')} |")
    lines += ["", "Ayrıntılı maç dosyaları (her bahis ailesi, araştırma, skor tabloları): "
              f"`reports/daily/{args.tarih}/mac_dosyalari/<Nesine kodu>.md`."]
    (d / "gunluk_analiz.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(ms)} maç -> {(d / 'gunluk_analiz.md').relative_to(DAILY.parents[1])}")


if __name__ == "__main__":
    main()
