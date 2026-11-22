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
from quantfoot.markets.market_calibration import calibrate_market_probability, load_market_calibration
from quantfoot.markets.market_diagnosis import diagnose_selection
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


def main_pick_floor(m: dict) -> tuple[float | None, str]:
    """Minimum probability for this source, or the reason the match is ineligible."""
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
    return min_p, ("" if is_sharp else "orta güven · araştırmalı")


def best_pick(m: dict) -> tuple[dict | None, str]:
    """Rank eligible selections using the same validated market curves and root-cause diagnostics as the coupon engine."""
    min_p, reason = main_pick_floor(m)
    if min_p is None:
        return None, reason
    calibration = load_market_calibration()
    res = m.get("research") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    has_diag_ctx = (
        m.get("mu_home") is not None
        or m.get("mu_away") is not None
        or bool(tm)
        or bool(ua)
    )
    p_over25 = next((float(x["fair_prob"]) for x in m.get("selections") or [] if x.get("name") == "2.5 Üst"), None)
    eligible = []
    for selection in m["selections"]:
        name = selection["name"]
        direct = bool(selection.get("direct"))
        if ("Skor" in name or name.startswith("İki Yarıda") or (not direct and name.startswith(EXCLUDED_MODEL))
                or selection["odds"] < 1.20 or selection["ev"] > 0.25):
            continue
        p = calibrate_market_probability(name, selection["fair_prob"], m.get("league"), calibration, direct=direct)
        diag_ok = True
        if has_diag_ctx:
            diag_ctx = {
                "mu_home": m.get("mu_home"),
                "mu_away": m.get("mu_away"),
                "fair_1x2": m.get("fair_1x2"),
                "p_over25": p_over25,
                "reference": m.get("reference"),
                "league": m.get("league"),
                "direct": direct,
                "home_gk1_out": bool((tm.get("home") or {}).get("gk1_out") or (ua.get("home") or {}).get("gk_out")),
                "away_gk1_out": bool((tm.get("away") or {}).get("gk1_out") or (ua.get("away") or {}).get("gk_out")),
                "home_top_scorer_out": bool((tm.get("home") or {}).get("top_scorer_out")),
                "away_top_scorer_out": bool((tm.get("away") or {}).get("top_scorer_out")),
            }
            diag = diagnose_selection(name, p, diag_ctx, for_coupon=False)
            diag_ok = bool(diag.ok)
            if diag.residual_adjustment < 0:
                p = min(1.0, max(0.0, p + float(diag.residual_adjustment)))
        ev = p * selection["odds"] - 1
        if p >= min_p and ev <= 0.25:
            eligible.append({**selection, "fair_prob": p, "fair_odds": 1 / p, "ev": ev, "_diag_ok": diag_ok})
    if not eligible:
        return None, ("orta güven — %62+ uygun seçim yok" if reason else "1,20+ uygun seçim yok")
    best = max(eligible, key=lambda s: (bool(s.get("_diag_ok", True)), s["fair_prob"], s["odds"]))
    out_pick = {k: v for k, v in best.items() if k != "_diag_ok"}
    return out_pick, reason


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
