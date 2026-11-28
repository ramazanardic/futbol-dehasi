#!/usr/bin/env python3
"""Minimum 10 oran, en fazla 5 maç — birleşik tutma olasılığı en yüksek kupon (oynanmaz).

GitHub Pinnacle/Smarkets referansı >3 saat eski olduğu için analiz, canlı OddsMath
(BetInAsia/Pinnacle) fiyatlarıyla yeniden kurulur. Açık oynanmış kupon maçları hariç tutulur.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QUANTFOOT_AI", "grokbottahmin")

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.paths import ai_area  # noqa: E402
from quantfoot.strategy import kupon_modu as KM  # noqa: E402
from quantfoot.data.oddsmath import is_youth_or_reserve_match  # noqa: E402
import nesine_global as ng  # noqa: E402
import nesine_kupon as nk  # noqa: E402

TSI = ng.TSI
DATE = "2026-11-21"
LEAD_MIN = 25
TARGET = 10.0
TARGET_HI = 11.5
MIN_ODDS_PREF = 1.45
MIN_ODDS_FLOOR = 1.25
MAX_LEG_ODDS = 2.10  # risk mode cap (user ideal band 1.45–2.20, no lottery >2.50)

# Hâlâ açık oynanmış kuponlar — tüm maç hariç (çift yükleme yok).
# 10'lu banko yattı, maçları tekrar kullanılabilir.
EXCLUDE_OPEN = {
    3319709,  # K1 Espanyol II
    3318200,  # K1 Tecnico
    3313940,  # K5 CSKA–Akhmat
    3313868,  # K5 Yeovil
    3313774,  # B5 Grazer–Rapid
    3314607,  # B5 Lille–Lyon
    3313785,  # MS10 Lugano
    3314719,  # MS10 D. Bükreş
    3319951,  # MS10 Castellon
    3313035,  # MS10 Larne
    3313692,  # MS10 CD Fas
    3319685,  # K2000 Pontevedra
    3312709,  # K2000 Motherwell–Rangers
    3318334,  # K2000 Bahia–Coritiba
    3312935,  # K2000 Águila
    3318800,  # K2000 Chapecoense–Cruzeiro
}

INJURY_ROTATION = (
    "kaleci yok", "kaleci eksik", "1. kaleci", "rotasyon", "gol kralı",
    "kilit eksik", "düzenli kaleci",
)

STEAM_RE = re.compile(r"(Ev|Ber|Dep) ([+-]\d+(?:\.\d+)?)p")


_ORIG_GLOBAL_REFERENCES = ng.global_references


def _fresh_global_references(max_age_hours: float | None = None):
    """Betting path: refuse the stale GitHub sharp file (> MAX_PRICE_AGE_H)."""
    return _ORIG_GLOBAL_REFERENCES(max_age_hours=ng.MAX_PRICE_AGE_H)


def parse_steam(flags: list[str]) -> dict[str, float]:
    out = {"Ev": 0.0, "Ber": 0.0, "Dep": 0.0}
    for f in flags or []:
        if "steam" not in f.lower():
            continue
        for lab, val in STEAM_RE.findall(f):
            out[lab] = float(val)
    return out


def steam_against(name: str, steam: dict[str, float], thresh: float = 5.0) -> bool:
    """True if a result-side pick goes against a ≥5p sharp steam."""
    n = name or ""
    home = n.startswith(("MS 1", "ÇŞ 10", "ÇŞ 1X", "Hnd")) or "MS 1 &" in n or n.startswith("İY/MS 1") or n.startswith("İY 1")
    away = n.startswith(("MS 2", "ÇŞ 02", "ÇŞ X2", "ÇŞ 2")) or "MS 2 &" in n or n.startswith("İY/MS 2") or n.startswith("İY 2")
    if home and steam.get("Ev", 0) <= -thresh:
        return True
    if away and steam.get("Dep", 0) <= -thresh:
        return True
    return False


def bad_match(m: dict, now: dt.datetime, cutoff: dt.datetime) -> str | None:
    ko = dt.datetime.fromisoformat(m["kickoff_iso"])
    if ko < cutoff:
        return "kickoff < 25 dk"
    if int(m["code"]) in EXCLUDE_OPEN:
        return "açık kuponda"
    if m.get("status") != "fiyatlandı":
        return "fiyatlanmadı"
    if m.get("research_block"):
        return "research_block"
    if is_youth_or_reserve_match(m.get("league") or "", m.get("home") or "", m.get("away") or ""):
        return "genç/rezerv"
    r = m.get("research") or {}
    flags = " ".join(r.get("flags") or []).lower()
    if any(k in flags for k in INJURY_ROTATION):
        return "sakat/rotasyon/kaleci"
    teams = r.get("teams") or {}
    for side in ("home", "away"):
        rest = (teams.get(side) or {}).get("rest_days")
        if rest is not None and rest <= 3:
            return f"dinlenme {rest} gün"
    age = nk.price_age_hours(m, now)
    if age is not None and age > nk.MAX_PRICE_AGE_H:
        return f"eski fiyat {age:.1f}s"
    return None


def filter_steam_and_band(pools: list[list[dict]], matches: dict[int, dict], min_odds: float) -> list[list[dict]]:
    by = {int(m["code"]): m for m in matches}
    out = []
    for pool in pools:
        kept = []
        for leg in pool:
            if leg["odds"] < min_odds - 1e-9 or leg["odds"] > MAX_LEG_ODDS + 1e-9:
                continue
            m = by.get(int(leg["code"]))
            steam = parse_steam((m.get("research") or {}).get("flags") or []) if m else {}
            if steam_against(leg.get("name") or "", steam):
                continue
            kept.append(leg)
        if kept:
            out.append(kept)
    return out


def summarize_build(c: dict | None) -> dict | None:
    if not c:
        return None
    ev = c["probability"] * c["nesine_odds"] - 1.0
    return {**c, "ev": ev, "n": len(c["legs"]), "earliest": c["legs"][0]["kickoff"]}


def one_line_reason(leg: dict, match: dict | None) -> str:
    bits = []
    name = leg.get("name") or f"{leg.get('market')} {leg.get('selection')}"
    ev = leg.get("ev_cal", leg.get("ev"))
    bits.append(
        f"Nesine {leg['odds']:.2f}, harman P %{leg['p']*100:.0f}"
        f" (ham adil %{leg.get('p_raw', leg['p'])*100:.0f}), EV {ev:+.0%}"
    )
    if "&" in name or "ve" in (leg.get("market") or "").lower():
        bits.append("kombine: ortak skor matrisinden (keskin 1X2+A/Ü'ye oturtulmuş), düz sonuca yakın P ile daha yüksek oran")
    if leg.get("direct"):
        bits.append("doğrudan keskin fiyat")
    else:
        bits.append("matris türevi")
    ctx = (leg.get("context") or "").strip()
    if ctx and "⚠" not in ctx:
        bits.append(ctx[:160])
    if match:
        r = match.get("research") or {}
        steam = parse_steam(r.get("flags") or [])
        if any(abs(v) >= 5 for v in steam.values()):
            bits.append("steam " + ", ".join(f"{k} {v:+.1f}p" for k, v in steam.items() if abs(v) >= 3))
        mu_h, mu_a = match.get("mu_home"), match.get("mu_away")
        if mu_h is not None:
            bits.append(f"λ {mu_h:.2f}-{mu_a:.2f}")
    return "; ".join(bits)


def reserves_for(best: dict, pools: list[list[dict]], n: int = 2) -> list[dict]:
    """Unused high-P legs that could replace a drifting/early leg."""
    used = {int(x["code"]) for x in best["legs"]}
    cands = []
    for pool in pools:
        if int(pool[0]["code"]) in used:
            continue
        top = max(pool, key=lambda x: (x["p"], -x["odds"]))
        if MIN_ODDS_FLOOR - 1e-9 <= top["odds"] <= MAX_LEG_ODDS + 1e-9:
            cands.append(top)
    cands.sort(key=lambda x: (-x["p"], x["odds"]))
    return cands[:n]


def fmt_leg_md(leg: dict, match: dict | None) -> str:
    p_raw = leg.get("p_raw", leg["p"])
    reason = one_line_reason(leg, match)
    ko = leg["kickoff"]
    return (
        f"| {ko[11:]} | {leg['match']} | {leg.get('league','')} | "
        f"{leg['market']}: {leg['selection']} | {leg['odds']:.2f} | "
        f"%{leg['p']*100:.1f} | %{p_raw*100:.1f} | {1/p_raw:.2f} | "
        f"{'doğrudan' if leg.get('direct') else 'matris'} | {leg.get('reference','')} | {reason} |"
    )


def main() -> int:
    now = dt.datetime.now(TSI)
    cutoff = now + dt.timedelta(minutes=LEAD_MIN)
    out_dir = ai_area() / DATE
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1) Fresh analysis: drop stale GitHub sharp file, use live OddsMath ---
    ng.global_references = _fresh_global_references
    day = dt.date.fromisoformat(DATE)
    print(f"{now:%H:%M} TSİ — analiz başlıyor (eski GitHub referansı atlanacak, OddsMath canlı).", flush=True)
    matches, payload, events = ng.analyze_day(day, verbose=True, use_oddsmath=True, use_tm=False, use_weather=True)
    ng.write_report(DATE, matches, payload, events, 0.0)
    priced = sum(1 for m in matches if m.get("status") == "fiyatlandı")
    ok = sum(1 for m in matches if m.get("betting_ok"))
    print(f"Fiyatlanan {priced}/{len(matches)}, betting_ok {ok}.", flush=True)

    live, flicker = nk.read_bulletin_odds()
    nk.apply_live_odds(matches, live)

    # Drop ineligible matches from the pool (25 dk, açık kupon, sakatlık, genç, eski fiyat)
    reasons = {}
    eligible = []
    for m in matches:
        why = bad_match(m, now, cutoff)
        if why:
            reasons[why] = reasons.get(why, 0) + 1
            m["selections"] = []
        else:
            eligible.append(m)
    print("Eleme:", reasons, f"uygun maç {len(eligible)}", flush=True)

    pol = KM.policy("risk")
    exposure = KM.open_exposure(ai_area())

    # Search: prefer 1.45 floor, fall back to 1.25; with/without derived combos; 4 vs 5 legs;
    # build targets 10.50 then 10.20 then 10.00.
    experiments = []
    for min_odds, label_odds in ((MIN_ODDS_PREF, "1.45+"), (MIN_ODDS_FLOOR, "1.25+")):
        for direct_only, label_dir in ((False, "kombine+dogrudan"), (True, "yalniz-dogrudan")):
            pools = nk.candidates(
                matches,
                now + dt.timedelta(minutes=LEAD_MIN - 5),  # candidates itself adds +5 min
                min_odds,
                pol.min_prob,
                allow_espn=False,
                direct_only=direct_only,
                exclude_cups=True,
                main_markets_only=False,
                allow_mid_researched=False,  # yalnız keskin
                family="karma",
                calibration=nk.load_live_calibration() or None,
                family_ev=True,
            )
            pools = nk.filter_pools_for_mode(pools, pol)
            pools = filter_steam_and_band(pools, matches, min_odds)
            n_legs = sum(len(p) for p in pools)
            print(f"  havuz {label_odds} {label_dir}: {len(pools)} maç, {n_legs} seçim", flush=True)
            for max_legs in (5, 4):
                min_legs = max_legs
                for tgt in (TARGET * 1.05, TARGET * 1.02, TARGET):
                    c = nk.best_coupon(pools, tgt, max_legs, min_legs=min_legs)
                    if not c:
                        continue
                    if c["nesine_odds"] < TARGET - 1e-9:
                        continue
                    experiments.append({
                        "min_odds": min_odds,
                        "direct_only": direct_only,
                        "label": f"{max_legs} maç · {label_odds} · {label_dir} · hedef {tgt:.2f}",
                        "max_legs": max_legs,
                        "target_used": tgt,
                        "coupon": c,
                        "pools": pools,
                    })
                    break  # first (highest buffer) that reaches >=10 is enough for this max_legs

    if not experiments:
        print("Uygun kupon kurulamadı.")
        payload_out = {"ok": False, "reason": "uygun kupon yok", "created": now.isoformat(timespec="seconds")}
        (out_dir / "kupon_10x.json").write_text(json.dumps(payload_out, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / "kupon_10x.md").write_text("# 10x kupon kurulamadı\n", encoding="utf-8")
        return 1

    def rank_key(ex):
        c = ex["coupon"]
        odds = c["nesine_odds"]
        in_band = 1 if TARGET - 1e-9 <= odds <= TARGET_HI + 1e-9 else 0
        # prefer in-band, then joint P, then closer to 10.5, prefer 1.45 floor, prefer more direct legs
        n_direct = sum(1 for x in c["legs"] if x.get("direct"))
        pref_odds = sum(1 for x in c["legs"] if x["odds"] >= MIN_ODDS_PREF - 1e-9)
        return (in_band, c["probability"], -abs(odds - 10.8), pref_odds, n_direct, -ex["min_odds"])

    # Best overall, and best 4 / best 5 for the comparison
    by4 = [e for e in experiments if e["max_legs"] == 4]
    by5 = [e for e in experiments if e["max_legs"] == 5]
    best4 = max(by4, key=rank_key) if by4 else None
    best5 = max(by5, key=rank_key) if by5 else None
    best = max(experiments, key=rank_key)

    # Re-check live odds on the chosen coupon; rebuild once if under 10
    def finalize(ex):
        if not ex:
            return None
        c = json.loads(json.dumps(ex["coupon"], ensure_ascii=False))  # shallow copy via json
        # restore is fine; legs are dicts
        live2, flicker2 = nk.read_bulletin_odds()
        notes = nk.recheck_odds([c], live2, flicker2)
        if c["nesine_odds"] < TARGET - 1e-9:
            nk.apply_live_odds(matches, live2)
            return None, notes, "oranın altına düştü"
        kept, guard_notes = nk.apply_mode_guard([c], "risk", live2 or None, exposure)
        notes += guard_notes
        if not kept:
            return None, notes, "risk kontrolünden geçmedi"
        c = kept[0]
        bym = {int(m["code"]): m for m in matches}
        for leg in c["legs"]:
            priced_j = ng.PRICED.get(int(leg["code"])) or nk.PRICED.get(int(leg["code"]))
            if priced_j and "joint" in priced_j:
                try:
                    leg["scores"] = nk.consistent_scores(priced_j["joint"], leg.get("name", ""))
                except Exception:
                    leg["scores"] = []
            m = bym.get(int(leg["code"]))
            leg["reason"] = one_line_reason(leg, m)
            if m:
                leg["mu_home"] = m.get("mu_home")
                leg["mu_away"] = m.get("mu_away")
                leg["fair_1x2"] = m.get("fair_1x2")
                leg["ref_fetched_utc"] = m.get("ref_fetched_utc")
                leg["kickoff_iso"] = m.get("kickoff_iso")
        c["odds_checked_at"] = dt.datetime.now(TSI).strftime("%H:%M")
        c["recheck_notes"] = notes
        return c, notes, None

    # Prefer the higher joint-P option between 4 and 5 if both in band; already encoded in rank_key
    chosen_ex = best
    chosen, notes, fail = finalize(chosen_ex)
    if chosen is None and best4 and best5:
        alt = best5 if chosen_ex is best4 else best4
        chosen, notes, fail = finalize(alt)
        chosen_ex = alt
    if chosen is None:
        print("Canlı oran / guard sonrası kupon kalmadı:", fail, notes)
        return 1

    # Also finalize comparison counterparts if possible (no second live pull if we just did)
    def snapshot(ex):
        if not ex:
            return None
        c = ex["coupon"]
        return {
            "n": len(c["legs"]),
            "odds": c["nesine_odds"],
            "p": c["probability"],
            "p_low": c.get("probability_low"),
            "ev": c["probability"] * c["nesine_odds"] - 1.0,
            "label": ex["label"],
            "min_odds": ex["min_odds"],
            "direct_only": ex["direct_only"],
            "legs": [
                {
                    "code": x["code"], "match": x["match"], "kickoff": x["kickoff"],
                    "market": x["market"], "selection": x["selection"], "name": x.get("name"),
                    "odds": x["odds"], "p": x["p"], "p_raw": x.get("p_raw"),
                    "direct": x.get("direct"), "reference": x.get("reference"),
                }
                for x in c["legs"]
            ],
        }

    reserves = reserves_for(chosen, chosen_ex["pools"], 2)
    bym = {int(m["code"]): m for m in matches}

    ev = chosen["probability"] * chosen["nesine_odds"] - 1.0
    one_in = (1.0 / chosen["probability"]) if chosen["probability"] else float("inf")
    earliest = chosen["legs"][0]["kickoff"]

    payload = {
        "ok": True,
        "placed": False,
        "mode": "risk",
        "target_min": TARGET,
        "target_band": [TARGET, TARGET_HI],
        "created": dt.datetime.now(TSI).isoformat(timespec="seconds"),
        "analysis_note": (
            "GitHub Pinnacle/Smarkets referansı ~5.6 saat eskiydi; analiz canlı OddsMath "
            "(BetInAsia/Pinnacle) ile yeniden kuruldu. Olasılıklar keskin 1X2+A/Ü'den oturtulmuş "
            "Dixon-Coles skor matrisinden (fund_weight=0), kalibrasyonla harmanlandı; model piyasadan "
            "yüksek tutulmadı. Kupon OYNANMADI."
        ),
        "exclude_open_codes": sorted(EXCLUDE_OPEN),
        "lead_minutes": LEAD_MIN,
        "nesine_odds": chosen["nesine_odds"],
        "probability": chosen["probability"],
        "probability_low": chosen.get("probability_low"),
        "ev": ev,
        "global_fair_odds": chosen.get("global_fair_odds"),
        "n_legs": len(chosen["legs"]),
        "earliest_kickoff": earliest,
        "one_in": one_in,
        "guard": chosen.get("guard"),
        "recheck_notes": notes,
        "build": chosen_ex["label"],
        "legs": chosen["legs"],
        "reserves": [
            {
                "code": r["code"], "match": r["match"], "kickoff": r["kickoff"],
                "market": r["market"], "selection": r["selection"], "name": r.get("name"),
                "odds": r["odds"], "p": r["p"], "p_raw": r.get("p_raw"),
                "direct": r.get("direct"), "reference": r.get("reference"),
                "reason": one_line_reason(r, bym.get(int(r["code"]))),
            }
            for r in reserves
        ],
        "comparison": {
            "best_4": snapshot(best4),
            "best_5": snapshot(best5),
            "chosen": "4" if chosen_ex["max_legs"] == 4 else "5",
            "rule": "Hedef ≥10 (tercihen 10.0–11.5) içinde birleşik P'si en yüksek olan; eşitlikte bant içi, 1.45+ bacak ve doğrudan fiyat tercih edildi.",
        },
        "pool_filters": reasons,
    }
    (out_dir / "kupon_10x.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    md = [
        f"# 10x kupon taslağı — {DATE} ({dt.datetime.now(TSI):%H:%M} TSİ)",
        "",
        "**OYNANMADI.** Toplam Nesine oranı bir minimumdur (en az 10,00; hedef bant 10,00–11,50). "
        "Tutma ihtimali banko değildir. Bugünün dersi uygulandı: olasılık keskin piyasaya yaslanıyor, "
        "model piyasadan iyimser tutulmadı.",
        "",
        f"- **Seçilen kupon:** {len(chosen['legs'])} maç · Nesine **{chosen['nesine_odds']:.2f}** · "
        f"tutma **%{chosen['probability']*100:.1f}** (yaklaşık {one_in:.0f}'de 1) · "
        f"güvenilir alt sınır %{100*chosen.get('probability_low', chosen['probability']):.1f} · "
        f"EV **{ev:+.0%}** · en erken kickoff **{earliest[11:]} TSİ**",
        f"- Kurulum: {chosen_ex['label']}",
        f"- Referans: canlı OddsMath (BetInAsia/Pinnacle); GitHub Smarkets/Pinnacle dosyası 3 saatten eski olduğu için kullanılmadı.",
        f"- Hariç: açık kupon maçları (K2000, K1, K5, Banko 5, 10'lu MS1 kalanları). 10'lu banko yatmıştı, maçları kullanılabilir.",
        f"- Filtre: kickoff ≥ 25 dk, kupa yok, genç/rezerv yok, keskin referans, bacak oranı 1,25–2,10 "
        f"(tercihen 1,45+), steam'in tersine sonuç bahsi yok, ağır sakatlık/rotasyon/kaleci yok.",
        "",
        "## Bacaklar",
        "",
        "| Saat (TSİ) | Maç | Lig | Pazar + seçim | Nesine | Harman P | Keskin adil P | Adil oran | Fiyat | Referans | Gerekçe |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for leg in chosen["legs"]:
        md.append(fmt_leg_md(leg, bym.get(int(leg["code"]))))
    md += [
        "",
        f"Oran kontrolü {chosen.get('odds_checked_at', '?')} TSİ"
        + (" — " + "; ".join(notes) if notes else " — oranlar aynı."),
        "",
        "## 4 maç vs 5 maç",
        "",
    ]
    def blk(title, snap):
        if not snap:
            return [f"**{title}:** bu ayarda ≥10 oranlı kupon kurulamadı.", ""]
        return [
            f"**{title}** ({snap['label']}): oran **{snap['odds']:.2f}**, tutma **%{snap['p']*100:.1f}**, EV {snap['ev']:+.0%}",
            "",
            *[
                f"- {x['kickoff'][11:]} {x['match']} — {x['market']}: {x['selection']} @ {x['odds']:.2f} "
                f"(P %{x['p']*100:.0f}, {'doğrudan' if x.get('direct') else 'matris'})"
                for x in snap["legs"]
            ],
            "",
        ]
    md += blk("4 maçlık en iyi", snapshot(best4))
    md += blk("5 maçlık en iyi", snapshot(best5))
    why = "5 maç" if chosen_ex["max_legs"] == 5 else "4 maç"
    md += [
        f"**Tercih: {why}.** Aynı ≥10,0 eşiğinde birleşik tutma olasılığı daha yüksek olan seçildi "
        f"(%{chosen['probability']*100:.1f}, oran {chosen['nesine_odds']:.2f}).",
        "",
        "## Yedekler",
        "",
    ]
    if reserves:
        for r in reserves:
            md.append(
                f"- {r['kickoff'][11:]} {r['match']} — {r['market']}: {r['selection']} @ {r['odds']:.2f} "
                f"(P %{r['p']*100:.0f}). {one_line_reason(r, bym.get(int(r['code'])))}"
            )
    else:
        md.append("_Uygun yedek kalmadı._")
    md += [
        "",
        "## Dürüst uyarı",
        "",
        f"Bu kuponun tutma ihtimali yaklaşık **{one_in:.0f}'de 1**. 10 oran, 4–5 görece olası bacakla bile "
        "piyango değildir ama banko da değildir. Nesine her bacakta pay aldığı için kupon EV'si genelde negatiftir. "
        "Oynamadan önce oranları kontrol edin; tek bir oran düşüşü toplamı 10'un altına indirebilir. "
        "**Bu taslak oynanmadı.**",
        "",
    ]
    (out_dir / "kupon_10x.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\n-> {out_dir / 'kupon_10x.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
