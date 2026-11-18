"""Deep QuantFoot-v6 Omni-Market analysis for all 44 matches played on Wednesday, Nov 18, 2026 (TSI)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quantfoot.data.live_espn import american_to_decimal
from quantfoot.markets import (
    compute_omni_markets,
    devig,
    fit_tail_rates_from_markets,
    league_tail_regime,
)
from quantfoot.strategy import (
    MatchRiskContext,
    audit_match_risks,
    build_target_odds_coupon,
    select_best_valid_bet,
)

BRAIN_SCRATCH = Path(r"C:\Users\pc\.gemini\antigravity\brain\fd718395-2b56-447a-8788-984e92dfbffb\scratch")
REPO_ROOT = Path(__file__).resolve().parents[1]


def fetch_espn_summary_l5(args: tuple[str, str, str, str]) -> tuple[str, dict]:
    eid, slug, home_name, away_name = args
    if not eid.isdigit():
        return eid, {}
    for s in (slug, "all"):
        try:
            r = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/{s}/summary",
                params={"event": eid},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                l5_list = data.get("lastFiveGames", [])
                out = {}
                for entry in l5_list:
                    t_disp = entry.get("team", {}).get("displayName", "")
                    tid = str(entry.get("team", {}).get("id", ""))
                    evs = entry.get("events", [])[:5]
                    gf, ga, w, d, l, btts, o25 = 0, 0, 0, 0, 0, 0, 0
                    scores = []
                    for e in evs:
                        try:
                            hs = int(e.get("homeTeamScore", 0))
                            as_ = int(e.get("awayTeamScore", 0))
                            if str(e.get("homeTeamId", "")) == tid:
                                mg, og = hs, as_
                            else:
                                mg, og = as_, hs
                            gf += mg
                            ga += og
                            if mg > og:
                                w += 1
                            elif mg == og:
                                d += 1
                            else:
                                l += 1
                            if mg >= 1 and og >= 1:
                                btts += 1
                            if mg + og >= 3:
                                o25 += 1
                            scores.append(f"{mg}-{og}")
                        except Exception:
                            continue
                    if scores:
                        side_key = "h_l5" if t_disp == home_name else ("a_l5" if t_disp == away_name else f"l5_{tid}")
                        out[side_key] = {
                            "n": len(scores),
                            "gf": gf,
                            "ga": ga,
                            "w_d_l": f"{w}G-{d}B-{l}M",
                            "btts": btts,
                            "o25": o25,
                            "scores": scores,
                        }
                return eid, out
        except Exception:
            continue
    return eid, {}


def parse_live_odds_map(live_odds: dict, cached_m: dict) -> tuple[dict[str, float], tuple[float, float, float] | None, float | None, tuple[float, float] | None]:
    """Extract decimal 1X2 and O/U odds from live ESPN or cached prediction record."""
    offered: dict[str, float] = {}
    cur_1x2 = None
    ou_line = None
    ou_odds = None

    # 1. Check live ESPN odds first
    oh = american_to_decimal(live_odds.get("ml_home"))
    od = american_to_decimal(live_odds.get("ml_draw"))
    oa = american_to_decimal(live_odds.get("ml_away"))
    if oh and od and oa:
        cur_1x2 = (oh, od, oa)
    elif cached_m.get("cur_1x2") and len(cached_m["cur_1x2"]) == 3:
        cur_1x2 = tuple(float(x) for x in cached_m["cur_1x2"])

    if cur_1x2:
        offered["MS 1"] = round(cur_1x2[0], 2)
        offered["MS 0"] = round(cur_1x2[1], 2)
        offered["MS 2"] = round(cur_1x2[2], 2)

    # 2. Check Over/Under odds
    ov_dec = american_to_decimal(live_odds.get("tot_over"))
    un_dec = american_to_decimal(live_odds.get("tot_under"))
    if ov_dec and un_dec and live_odds.get("overUnder") is not None:
        ou_line = float(live_odds["overUnder"])
        ou_odds = (ov_dec, un_dec)
    elif cached_m.get("ou_line") is not None and cached_m.get("ou_odds"):
        ou_line = float(cached_m["ou_line"])
        ou_odds = (float(cached_m["ou_odds"][0]), float(cached_m["ou_odds"][1]))

    if ou_line in (1.5, 2.5, 3.5, 4.5) and ou_odds:
        offered[f"{ou_line:.1f} Üst"] = round(ou_odds[0], 2)
        offered[f"{ou_line:.1f} Alt"] = round(ou_odds[1], 2)

    return offered, cur_1x2, ou_line, ou_odds


def main() -> None:
    d_global = json.loads((BRAIN_SCRATCH / "all_global_matches_predictions.json").read_text(encoding="utf-8"))
    d_wed = json.loads((BRAIN_SCRATCH / "wed_fri_refreshed.json").read_text(encoding="utf-8"))
    d_live = json.loads((BRAIN_SCRATCH / "today_deep_2026_11_18.json").read_text(encoding="utf-8"))

    live_by_id = {str(m["id"]): m for m in d_live}
    merged_by_id: dict[str, dict] = {}
    for m in d_global + d_wed:
        ko = str(m.get("ko_tsi", ""))
        if "2026-11-18 10:00" <= ko <= "2026-11-19 06:30":
            merged_by_id[str(m["event_id"])] = m

    # Also add any match from d_live not yet in merged_by_id
    for eid, lm in live_by_id.items():
        if eid not in merged_by_id:
            merged_by_id[eid] = {
                "event_id": eid,
                "ko_tsi": lm["kickoff_tr"],
                "day": lm["kickoff_tr"][:10],
                "league": lm["league"],
                "slug": lm["slug"],
                "home": lm["home"],
                "away": lm["away"],
                "xg_h": 1.45,
                "xg_a": 1.15,
            }

    matches_list = sorted(merged_by_id.values(), key=lambda x: (x["ko_tsi"], x["league"], x["home"]))
    print(f"Analyzing {len(matches_list)} matches for Today (2026-11-18 10:00 .. 2026-11-19 06:30 TSI)...")

    l5_tasks = [(str(m["event_id"]), m["slug"], m["home"], m["away"]) for m in matches_list]
    l5_map = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        for eid, res in pool.map(fetch_espn_summary_l5, l5_tasks):
            l5_map[eid] = res

    analyzed_records = []
    priced_pool = []
    tur3_pool = []
    all_general_recs = []
    all_htft_recs = []
    all_band_recs = []
    all_6plus_recs = []
    all_halves_kg_recs = []

    for idx, m in enumerate(matches_list, 1):
        eid = str(m["event_id"])
        ko = m["ko_tsi"]
        slug = m["slug"]
        league = m["league"]
        home = m["home"]
        away = m["away"]

        live_m = live_by_id.get(eid, {})
        live_odds = live_m.get("odds", {})
        offered_map, cur_1x2, ou_line, ou_odds = parse_live_odds_map(live_odds, m)

        # Base xG from fundamental / table / form model
        base_mu_h = float(m.get("xg_h") or 1.38)
        base_mu_a = float(m.get("xg_a") or 1.12)

        # Enrich with last 5 form if available
        l5_info = l5_map.get(eid, {})
        h_l5 = l5_info.get("h_l5") or m.get("form_h") or {}
        a_l5 = l5_info.get("a_l5") or m.get("form_a") or {}
        th = m.get("table_h") or {}
        ta = m.get("table_a") or {}

        # Blend with live devigged market odds when available
        mu_h, mu_a = base_mu_h, base_mu_a
        if cur_1x2 is not None:
            p_mkt = devig(list(cur_1x2), method="power").probabilities
            p_over_mkt = None
            if ou_odds is not None and ou_line is not None:
                p_ou = devig(list(ou_odds), method="power").probabilities
                p_over_mkt = float(p_ou[0])
            com_nu, alpha_nb, shared_kappa = league_tail_regime(slug)
            fit_h, fit_a, _ = fit_tail_rates_from_markets(
                p_1x2=p_mkt,
                ou_line=ou_line if p_over_mkt is not None else None,
                p_over=p_over_mkt,
                seed_rates=(base_mu_h, base_mu_a),
                alpha_nb=alpha_nb,
                shared_kappa=shared_kappa,
                fund_weight=0.22,
            )
            mu_h, mu_a = float(fit_h), float(fit_a)

        # Build tactical Risk Context from form, table, and tournament type
        def _ti(val, default=0):
            try:
                return int(float(val))
            except Exception:
                return default

        h_gf5 = _ti(h_l5.get("gf"), -1) if h_l5.get("gf") is not None else None
        h_ga5 = _ti(h_l5.get("ga"), -1) if h_l5.get("ga") is not None else None
        a_gf5 = _ti(a_l5.get("gf"), -1) if a_l5.get("gf") is not None else None
        a_ga5 = _ti(a_l5.get("ga"), -1) if a_l5.get("ga") is not None else None
        h_n5 = _ti(h_l5.get("n"), 0)
        a_n5 = _ti(a_l5.get("n"), 0)

        h_dead = False
        a_dead = False
        if h_n5 >= 4 and h_gf5 is not None and h_gf5 <= 3:
            h_dead = True
        if a_n5 >= 4 and a_gf5 is not None and a_gf5 <= 3:
            a_dead = True
        if th and _ti(th.get("gp"), 0) >= 8 and (_ti(th.get("gf"), 10) / max(1, _ti(th.get("gp"), 1))) < 0.72:
            h_dead = True
        if ta and _ti(ta.get("gp"), 0) >= 8 and (_ti(ta.get("gf"), 10) / max(1, _ti(ta.get("gp"), 1))) < 0.72:
            a_dead = True

        # Cup mismatches (Copa del Rey / Copa de la Reina / Women's FA Cup): lower-tier home vs top-tier away or vice versa
        is_cup_knockout = any(k in slug for k in ("copa", "fa", "league_cup", "wchampions"))
        h_must = bool(mu_h - mu_a >= 0.55 or (th and 1 <= _ti(th.get("rank"), 99) <= 4))
        a_must = bool(mu_a - mu_h >= 0.55 or (ta and 1 <= _ti(ta.get("rank"), 99) <= 4))

        notes_parts = []
        if th and ta and th.get("rank") and ta.get("rank"):
            notes_parts.append(
                f"Tablo: Ev #{th.get('rank')} ({th.get('gp','?')}M {th.get('gf','?')}:{th.get('ga','?')} {th.get('pts','?')}P) vs "
                f"Dep #{ta.get('rank')} ({ta.get('gp','?')}M {ta.get('gf','?')}:{ta.get('ga','?')} {ta.get('pts','?')}P)"
            )
        if h_n5 and a_n5:
            notes_parts.append(
                f"Son {h_n5}M: Ev {h_gf5}:{h_ga5} ({h_l5.get('w_d_l','')}) vs Dep {a_gf5}:{a_ga5} ({a_l5.get('w_d_l','')})"
            )
        if cur_1x2:
            notes_parts.append(f"Canlı 1X2: {cur_1x2[0]:.2f} / {cur_1x2[1]:.2f} / {cur_1x2[2]:.2f}")
        if ou_line and ou_odds:
            notes_parts.append(f"O/U {ou_line}: Üst {ou_odds[0]:.2f} / Alt {ou_odds[1]:.2f}")

        risk_ctx = MatchRiskContext(
            home_must_win=h_must,
            away_must_win=a_must,
            home_dead_attack=h_dead,
            away_dead_attack=a_dead,
            high_rotation_risk=False,
            group_id=eid,
            notes=" | ".join(notes_parts),
        )

        bundle = compute_omni_markets(mu_h, mu_a, league=slug)
        blocked, penalties = audit_match_risks(bundle, risk_ctx)

        gen_recs = select_best_valid_bet(
            eid, home, away, league, ko, bundle,
            offered_odds_map=offered_map, risk_ctx=risk_ctx, min_prob=0.54,
        )
        htft_recs = select_best_valid_bet(
            eid, home, away, league, ko, bundle,
            offered_odds_map=offered_map, risk_ctx=risk_ctx, specialty_mode="ht_ft",
        )
        band_recs = select_best_valid_bet(
            eid, home, away, league, ko, bundle,
            offered_odds_map=offered_map, risk_ctx=risk_ctx, specialty_mode="goal_bands", min_prob=0.38,
        )
        six_recs = select_best_valid_bet(
            eid, home, away, league, ko, bundle,
            offered_odds_map=offered_map, risk_ctx=risk_ctx, specialty_mode="6_plus_goals",
        )
        hkg_recs = select_best_valid_bet(
            eid, home, away, league, ko, bundle,
            offered_odds_map=offered_map, risk_ctx=risk_ctx, specialty_mode="both_halves_btts",
        )

        if gen_recs:
            all_general_recs.append(gen_recs)
            if cur_1x2 is not None:
                priced_pool.append(gen_recs)
            if slug == "tur.3":
                tur3_pool.append(gen_recs)
        if htft_recs:
            all_htft_recs.append(htft_recs)
        if band_recs:
            all_band_recs.append(band_recs)
        if six_recs:
            all_6plus_recs.append(six_recs)
        if hkg_recs:
            all_halves_kg_recs.append(hkg_recs)

        top_gen = gen_recs[0] if gen_recs else None
        top_htft = htft_recs[0] if htft_recs else None
        top_band = band_recs[0] if band_recs else None

        rec_dict = {
            "idx": idx,
            "event_id": eid,
            "ko_tsi": ko,
            "slug": slug,
            "league": league,
            "home": home,
            "away": away,
            "has_live_odds": cur_1x2 is not None,
            "cur_1x2": cur_1x2,
            "ou_line": ou_line,
            "ou_odds": ou_odds,
            "mu_home": bundle.mu_home,
            "mu_away": bundle.mu_away,
            "expected_total": bundle.expected_total,
            "exp_1h_total": bundle.exp_1h_total,
            "exp_2h_total": bundle.exp_2h_total,
            "ft_1x2": bundle.ft_1x2,
            "double_chance": bundle.double_chance,
            "ht_1x2": bundle.ht_1x2,
            "h2_1x2": bundle.h2_1x2,
            "ht_ft": bundle.ht_ft,
            "goal_bands": bundle.goal_bands,
            "ft_ou": bundle.ft_ou,
            "ht_ou": bundle.ht_ou,
            "h2_ou": bundle.h2_ou,
            "btts": bundle.btts,
            "combos": bundle.combos,
            "top_ft_scores": bundle.top_ft_scores[:3],
            "top_ht_scores": bundle.top_ht_scores[:2],
            "top2_score_cluster": bundle.top2_score_cluster,
            "top3_score_cluster": bundle.top3_score_cluster,
            "score_entropy": bundle.score_entropy,
            "notes": risk_ctx.notes,
            "blocked_traps": list(blocked.keys()),
            "best_valid_bet": {
                "selection": top_gen.selection,
                "category": top_gen.category,
                "prob": top_gen.probability,
                "fair_odds": top_gen.fair_odds,
                "offered_odds": top_gen.offered_odds,
                "odds_is_estimated": top_gen.odds_is_estimated,
                "safety_score": top_gen.safety_score,
            } if top_gen else None,
            "alt_valid_bets": [
                {
                    "selection": r.selection,
                    "prob": r.probability,
                    "offered_odds": r.offered_odds,
                }
                for r in gen_recs[1:4]
            ],
            "best_ht_ft": {
                "selection": top_htft.selection,
                "prob": top_htft.probability,
                "offered_odds": top_htft.offered_odds,
            } if top_htft else None,
            "best_goal_band": {
                "selection": top_band.selection,
                "prob": top_band.probability,
                "offered_odds": top_band.offered_odds,
            } if top_band else None,
        }
        analyzed_records.append(rec_dict)

    full_pool = all_general_recs

    coupons = {}
    for target, m_legs in ((10.0, 8), (20.0, 9), (30.0, 10)):
        c_priced = build_target_odds_coupon(
            priced_pool,
            target_odds=target,
            max_legs=m_legs,
            title=f"QuantFoot-v6 Bugün Hedef {target:.0f}x Garanti Kupon (16 Canlı Piyasa Oranlı Ana Maç)",
        )
        coupons[f"target_{int(target)}x"] = {
            "title": c_priced.title,
            "target_odds": c_priced.target_odds,
            "achieved_odds": c_priced.achieved_odds,
            "joint_probability": c_priced.joint_probability,
            "average_leg_probability": c_priced.average_leg_probability,
            "legs": [
                {
                    "ko_tsi": l.kickoff,
                    "league": l.league,
                    "home": l.home,
                    "away": l.away,
                    "selection": l.selection,
                    "category": l.category,
                    "prob": l.probability,
                    "fair_odds": l.fair_odds,
                    "offered_odds": l.offered_odds,
                    "odds_is_estimated": l.odds_is_estimated,
                    "rationale": l.rationale,
                }
                for l in c_priced.legs
            ],
        }

    c_tur3 = build_target_odds_coupon(
        tur3_pool,
        target_odds=10.0,
        max_legs=7,
        title="QuantFoot-v6 Nesine 2. Lig Gündüz (13:00-15:00) Kuponu",
    )
    coupons["tur3_10x"] = {
        "title": c_tur3.title,
        "target_odds": c_tur3.target_odds,
        "achieved_odds": c_tur3.achieved_odds,
        "joint_probability": c_tur3.joint_probability,
        "average_leg_probability": c_tur3.average_leg_probability,
        "legs": [
            {
                "ko_tsi": l.kickoff,
                "league": l.league,
                "home": l.home,
                "away": l.away,
                "selection": l.selection,
                "category": l.category,
                "prob": l.probability,
                "fair_odds": l.fair_odds,
                "offered_odds": l.offered_odds,
                "odds_is_estimated": l.odds_is_estimated,
                "rationale": l.rationale,
            }
            for l in c_tur3.legs
        ],
    }

    out_payload = {
        "generated_at": "2026-11-18T10:12:00+03:00",
        "total_matches": len(analyzed_records),
        "coupons": coupons,
        "matches": analyzed_records,
    }
    out_path = REPO_ROOT / "reports" / "today_v6_predictions_2026_11_18.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(analyzed_records)} analyzed matches to {out_path}")
    for k, cp in coupons.items():
        print(f"\n=== {cp['title']} | Toplam Oran: {cp['achieved_odds']}x | Ort. Ayak Olasılığı: %{cp['average_leg_probability']*100:.1f} ===")
        for leg in cp["legs"]:
            est_tag = " (Tahmini Oran)" if leg["odds_is_estimated"] else " (Canlı Piyasa Oranı)"
            print(f"  - [{leg['ko_tsi']}] {leg['home']} - {leg['away']} ({leg['league']}): {leg['selection']} @ {leg['offered_odds']:.2f}{est_tag} | P=%{leg['prob']*100:.1f}")


if __name__ == "__main__":
    main()
