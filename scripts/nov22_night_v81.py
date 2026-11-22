"""QuantFoot-v8.1 Live Evening & Night (>= 20:45 TSI) 0-PAS Predictions & Diversified Coupons."""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from quantfoot.data.nesine import fetch_bulletin, parse_bulletin  # noqa: E402
from quantfoot.markets import compute_omni_markets  # noqa: E402
from quantfoot.strategy import (  # noqa: E402
    MarketRecommendation,
    MatchRiskContext,
    PortfolioCouponSpec,
    audit_match_risks,
    build_diversified_portfolio,
)
from nesine_global import _nesine_league_regime_key, shrink_local_probability  # noqa: E402

TSI = dt.timezone(dt.timedelta(hours=3))

CORE_V81 = {
    "MS 1", "MS 2", "ÇŞ 10", "ÇŞ 02",
    "1.5 Üst", "1.5 Alt", "2.5 Üst", "2.5 Alt", "3.5 Üst", "3.5 Alt", "4.5 Alt",
    "İY 0.5 Üst", "İY 1.5 Alt", "İY 1.5 Üst", "2Y 0.5 Üst",
    "KG Var", "KG Yok", "2-3 Gol", "2-4 Gol", "3-5 Gol",
    "2.5 Üst & KG Var", "2.5 Alt & KG Yok", "MS 1 & 1.5 Üst", "MS 2 & 1.5 Üst",
}


def _cat(sel: str) -> str:
    if sel.startswith("MS ") and "&" not in sel:
        return "Maç Sonucu (1X2)"
    if sel.startswith("ÇŞ "):
        return "Çifte Şans"
    if "İY" in sel or "2Y" in sel:
        return "Devre Alt/Üst"
    if "KG" in sel and "&" not in sel:
        return "Karşılıklı Gol"
    if "&" in sel:
        return "Özel Kombine"
    return "Maç Geneli Alt/Üst"


def main() -> None:
    now = dt.datetime.now(TSI)
    cutoff = now + dt.timedelta(minutes=12)  # playable matches starting >= ~20:45 TSI

    ng_path = REPO_ROOT / "tahminler" / "grokbottahmin" / "2026-11-22" / "nesine_global.json"
    ng = json.loads(ng_path.read_text(encoding="utf-8"))
    unplayed = [
        m for m in ng["matches"]
        if m.get("price_tier") != "ozel_bahis"
        and dt.datetime.fromisoformat(m["kickoff_iso"]) >= cutoff
    ]
    unplayed.sort(key=lambda m: (m["kickoff_iso"], m["home"]))

    # Refresh with live Nesine bulletin odds
    live_by_code: dict[int, dict[str, tuple[float, int]]] = {}
    try:
        for e in parse_bulletin(fetch_bulletin()):
            live_by_code[int(e.code)] = {
                s.name: (float(s.odds), int(s.mbs or 1))
                for s in e.selections if not s.negate and float(s.odds) >= 1.20
            }
    except Exception as ex:
        print("Live bulletin fetch warning:", ex)

    rows = []
    coupon_pool: list[list[MarketRecommendation]] = []

    for m in unplayed:
        code = int(m["code"])
        ko_dt = dt.datetime.fromisoformat(m["kickoff_iso"])
        ko_disp = ko_dt.strftime("%d.%m %H:%M")
        lg = m["league"]
        reg = _nesine_league_regime_key(lg)
        mu_h, mu_a = float(m.get("mu_home") or 1.35), float(m.get("mu_away") or 1.10)
        bundle = compute_omni_markets(mu_h, mu_a, league=reg)
        all_probs = bundle.all_probabilities()
        live_map = live_by_code.get(code) or {}

        sels_by_name = {}
        for s in m.get("selections", []):
            nm = s["name"]
            if nm not in CORE_V81:
                continue
            odd = live_map[nm][0] if nm in live_map else float(s["odds"])
            mbs = live_map[nm][1] if nm in live_map else int(s.get("mbs") or 1)
            if odd < 1.20:
                continue
            sels_by_name[nm] = {**s, "odds": round(odd, 2), "mbs": mbs, "ev": round(float(s["fair_prob"]) * odd - 1.0, 4)}
        for nm, (odd, mbs) in live_map.items():
            if nm in CORE_V81 and nm not in sels_by_name and nm in all_probs:
                pv = float(all_probs[nm])
                sels_by_name[nm] = {
                    "name": nm, "odds": round(odd, 2), "mbs": mbs, "fair_prob": round(pv, 5),
                    "fair_odds": round(1.0 / max(pv, 1e-6), 2), "ev": round(pv * odd - 1.0, 4), "direct": False,
                }

        tier = m.get("price_tier") or "dusuk_guven"
        is_sharp = tier == "keskin"
        is_global = tier in ("keskin", "global_buro")
        is_local = not is_global
        btts_dir = bool("KG Var" in sels_by_name and sels_by_name["KG Var"].get("direct"))
        p_btts_mkt = sels_by_name["KG Var"]["fair_prob"] if btts_dir else None
        has_ou = bool(m.get("ref_ou")) or any(k in sels_by_name and sels_by_name[k].get("direct") for k in ("1.5 Üst", "2.5 Üst", "3.5 Üst")) or is_local
        is_ko = any(tok in lg.lower() for tok in ("kupa", "cup", "playoff", "eleme", "trophy"))

        blocked, penalties = audit_match_risks(
            bundle,
            MatchRiskContext(is_knockout=is_ko, has_ou_market=has_ou, btts_market_prob=p_btts_mkt, btts_is_direct=btts_dir),
        )

        def rank_v81(min_p: float, allow_blk: bool = False) -> list[tuple]:
            out = []
            for nm, s in sels_by_name.items():
                if not allow_blk and nm in blocked:
                    continue
                if float(s["ev"]) > 0.25:
                    continue
                p_raw = float(s["fair_prob"])
                p_eff = shrink_local_probability(p_raw, 0.78) if (is_local and p_raw > 0.50) else p_raw
                if p_eff < min_p:
                    continue
                direct = bool(s.get("direct"))
                sig = (0.010 if direct else (0.032 if ("İY" in nm or "2Y" in nm) else 0.025)) + (0.0 if "+" in str(m.get("reference", "")) else 0.005)
                p_low = max(0.001, p_eff - 1.28 * sig)
                pen = penalties.get(nm, 1.0) * (0.72 if (allow_blk and nm in blocked) else 1.0)
                boost = 1.05 if (direct or nm in ("İY 0.5 Üst", "4.5 Alt", "KG Yok")) else 1.0
                ev_eff = round(p_eff * float(s["odds"]) - 1.0, 4)
                saf = round((p_low ** 1.40) * pen * boost * max(0.65, min(1.18, 1.0 + 0.50 * ev_eff)), 4)
                out.append((saf, p_low, p_eff, sig, nm, s, direct, ev_eff, nm in blocked))
            out.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return out

        pool = rank_v81(0.57, False) or rank_v81(0.50, False) or rank_v81(0.45, True) or rank_v81(0.01, True)
        if not pool:
            best_nm = max(("4.5 Alt", "İY 0.5 Üst", "1.5 Üst", "KG Yok", "ÇŞ 10", "ÇŞ 02"), key=lambda k: all_probs.get(k, 0.5))
            pv = float(all_probs.get(best_nm, 0.62))
            ov = live_map[best_nm][0] if best_nm in live_map else round(max(1.20, (1.0 / max(pv, 0.1)) * 0.86), 2)
            best_row = (pv, pv - 0.03, pv, 0.03, best_nm, {"odds": ov, "mbs": 3}, False, round(pv * ov - 1.0, 4), True)
            alt_row = None
        else:
            best_row = pool[0]
            alt_row = pool[1] if len(pool) > 1 else None

        ref_short = (m.get("reference") or "Nesine").split(" (")[0]
        top3 = [f"{x['score']} (%{x.get('probability', x.get('prob', 0))*100:.1f})" for x in bundle.top_ft_scores[:3]]

        rows.append({
            "code": code,
            "ko": ko_disp,
            "tier": tier,
            "ref": ref_short,
            "league": lg,
            "match": f"{m['home']} - {m['away']}",
            "home": m["home"],
            "away": m["away"],
            "xg": f"{mu_h:.2f}-{mu_a:.2f}",
            "top3": top3,
            "best_sel": best_row[4],
            "best_odds": best_row[5]["odds"],
            "best_p": round(best_row[2], 4),
            "best_plow": round(best_row[1], 4),
            "best_ev": best_row[7],
            "best_direct": best_row[6],
            "mbs": best_row[5]["mbs"],
            "alt_sel": alt_row[4] if alt_row else None,
            "alt_odds": alt_row[5]["odds"] if alt_row else None,
        })

        # Add clean Global (Sharp + Global Buro) unblocked >= 58% options into diversified coupon pool
        if is_global and not m.get("research_block"):
            recs = []
            for saf, p_low, p_eff, sig, nm, s, direct, ev_eff, is_blk in rank_v81(0.58, False):
                if ev_eff < -0.20:
                    continue
                recs.append(
                    MarketRecommendation(
                        match_id=str(code),
                        home=m["home"],
                        away=m["away"],
                        league=lg,
                        kickoff=ko_disp,
                        category=_cat(nm),
                        selection=nm,
                        probability=round(p_eff, 4),
                        fair_odds=round(1.0 / max(p_eff, 1e-6), 2),
                        offered_odds=float(s["odds"]),
                        odds_is_estimated=False,
                        safety_score=saf,
                        ev=ev_eff,
                        rationale=f"v8.1 {ref_short} ({'D' if direct else 'M'}): P=%{p_eff*100:.1f}, P_alt=%{p_low*100:.1f}",
                        group_id=str(code),
                        mbs=int(s["mbs"]),
                        prob_sigma=sig,
                    )
                )
            if recs:
                coupon_pool.append(recs)

    specs = [
        PortfolioCouponSpec(title="KUPON 1 — Gece Çekirdek Güven (Kısa 3–4 Maç · ~2.4x)", target_odds=2.35, max_legs=4, min_leg_ev=None, min_leg_prob=0.66),
        PortfolioCouponSpec(title="KUPON 2 — İkinci Kısa Güven (4 Maç · ~3.5x)", target_odds=3.40, max_legs=5, min_leg_ev=None, min_leg_prob=0.63),
        PortfolioCouponSpec(title="KUPON 3 — Dengeli Akşam & Gece (5 Maç · ~5.0x)", target_odds=4.90, max_legs=6, min_leg_ev=None, min_leg_prob=0.61),
        PortfolioCouponSpec(title="KUPON 4 — Hedef 10x+ Gece Kombinesi (0 Tekrar)", target_odds=10.00, max_legs=8, min_leg_ev=None, min_leg_prob=0.59),
        PortfolioCouponSpec(title="KUPON 5 — Hedef 20x+ Ana Gece Kombinesi (0 Tekrar)", target_odds=20.00, max_legs=9, min_leg_ev=None, min_leg_prob=0.58),
    ]
    plans = build_diversified_portfolio(
        coupon_pool,
        specs,
        max_selection_reuse=1,
        max_match_reuse=2,
        max_same_category_share=0.50,
        forbid_contradictions=True,
    )

    print(f"Unplayed >= {cutoff:%H:%M} TSI analyzed (v8.1, 0 PAS): {len(rows)} matches | Coupon pool: {len(coupon_pool)} global matches")
    seen = set()
    for p in plans:
        print(f"\n{p.title} => {p.achieved_odds:.2f}x (Hedef {p.target_odds:.1f}x, Ulaştı:{p.reached_target}) | {len(p.legs)} maç | Ort P=%{p.average_leg_probability*100:.1f} | Birleşik P=%{p.joint_probability*100:.2f}")
        for l in p.legs:
            pair = (l.match_id, l.selection)
            assert pair not in seen, f"DUPLICATE {pair}"
            seen.add(pair)
            print(f"  - [{l.kickoff}] {l.home} - {l.away} (MBS {l.mbs}): {l.selection} @ {l.offered_odds:.2f} | Adil {l.fair_odds:.2f} (P=%{l.probability*100:.1f}, EV={l.ev*100:+.1f}%)")

    # Export Markdown + JSON Ledger + Artifact
    md = [
        f"# 22–23 Kasım Gece Bülteni — QuantFoot-v8.1 (`0 PAS` · 14 Katman) Kuponları ve Kalan {len(rows)} Maç Analizi",
        "",
        f"- **Üretim Zamanı:** `22.11.2026 {now:%H:%M} TSİ` · **Başlama Sınırı:** `≥ {cutoff:%H:%M} TSİ` (`{len(rows)}` başlamamış maç, **`0 PAS`**).",
        "- **`v8.1` Yenilikleri:** Katman 13 (`İY 1.5 Alt` yüksek xG engeli), Katman 14 (`direct=False` model `KG Var` freni), direkt borsa önceliği, yerel Tier-3 olasılık çekmesi, zorunlu fallback'te `0 MS 0` ve kupon başına maks `%45` aynı tercih tavanı.",
        "",
        "## 1. QuantFoot-v8.1 Akşam & Gece Kuponları (`0 Tekrar`, `0 Çelişki`, MBS Uyumlu)",
        "",
    ]
    coupons_json = []
    for idx_c, p in enumerate(plans, 1):
        md.append(f"### {p.title}")
        md.append(f"**Canlı Nesine Oran:** **`{p.achieved_odds:.2f}x`** · **Maç:** `{len(p.legs)}` · **Ort. Global P:** `%{p.average_leg_probability*100:.1f}` · **Birleşik P:** `%{p.joint_probability*100:.2f}`")
        md.append("")
        md.append("| Saat | Lig | Maç | MBS | Tercih | Canlı Nesine | Global % | Adil | EV |")
        md.append("|---|---|---|---:|---|---:|---:|---:|---:|")
        ljson = []
        for l in p.legs:
            md.append(f"| {l.kickoff} | {l.league} | {l.home} - {l.away} | {l.mbs} | **{l.selection}** | {l.offered_odds:.2f} | %{l.probability*100:.1f} | {l.fair_odds:.2f} | {l.ev*100:+.1f}% |")
            ljson.append({
                "code": int(l.match_id), "kickoff": l.kickoff, "league": l.league,
                "home": l.home, "away": l.away, "mbs": l.mbs, "selection": l.selection,
                "odds": l.offered_odds, "prob": l.probability, "fair_odds": l.fair_odds, "ev": l.ev,
            })
        md.append("")
        coupons_json.append({
            "coupon_no": idx_c, "title": p.title, "target_odds": p.target_odds,
            "achieved_odds": p.achieved_odds, "leg_count": len(p.legs),
            "avg_prob": p.average_leg_probability, "joint_prob": p.joint_probability,
            "reached_target": p.reached_target, "legs": ljson,
        })

    md.extend([
        f"## 2. Kalan Tüm {len(rows)} Başlamamış Maç — QuantFoot-v8.1 (`0 PAS`) Tam Tahmin Listesi",
        "",
        "| Saat | Katman | Lig | Maç | xG | 1. Skor | v8.1 Tercih | Canlı Nesine | Global % | Alternatif |",
        "|---|---|---|---|---|---|---|---:|---:|---|",
    ])
    for r in rows:
        t_lbl = "Sharp" if r["tier"] == "keskin" else ("Global" if r["tier"] == "global_buro" else "Yerel")
        alt_s = f"{r['alt_sel']} @ {r['alt_odds']:.2f}" if r["alt_sel"] else "—"
        md.append(f"| {r['ko']} | {t_lbl} | {r['league']} | {r['match']} | {r['xg']} | {r['top3'][0]} | **{r['best_sel']}** | {r['best_odds']:.2f} | %{r['best_p']*100:.1f} | {alt_s} |")

    md_text = "\n".join(md) + "\n"
    (REPO_ROOT / "reports" / "nov22_night_v81_coupons.md").write_text(md_text, encoding="utf-8")
    (REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_22_night_v81.json").write_text(
        json.dumps({"date": "2026-11-22", "session": "night_v81", "generated_at_tsi": now.isoformat(timespec="seconds"), "engine": "QuantFoot-v8.1", "coupons": coupons_json, "predictions": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("\nSaved reports/nov22_night_v81_coupons.md and reports/ledger/coupons_2026_11_22_night_v81.json")


if __name__ == "__main__":
    main()
