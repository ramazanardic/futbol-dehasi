"""Strictly causal walk-forward evaluator for Close-Match 1X2, HT/FT Comebacks (1/2 & 2/1),
Both-Halves BTTS, and Exact Score models on live 2026/27 European season archives.

Every match on date D uses ONLY past matches played strictly before date D (``Date < D``)
for xG profiles, finishing-luck regression, and team 1H/2H half-split profiles — zero leakage.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import math
from pathlib import Path
from typing import Any

from quantfoot.markets.devig import devig
from quantfoot.markets.extreme_goals import score_both_halves_btts_match
from quantfoot.markets.high_odds_engine import (
    analyze_close_match,
    analyze_exact_scores,
    score_comeback_htft,
)
from quantfoot.markets.match_intelligence import (
    SEASON_DATA_DIR,
    _flt,
    _parse_csv_date,
    compute_team_half_profiles,
    load_division_rows,
)
from quantfoot.markets.lineup_xg import compute_team_xg_profiles
from quantfoot.markets.pricing import invert_ah_ou_1x2


@dataclass(frozen=True)
class WalkForwardSummary:
    n_matches: int
    n_close_matches: int
    close_market_brier: float
    close_model_brier: float
    close_market_logloss: float
    close_model_logloss: float
    close_high_draw_n: int
    close_high_draw_rate: float
    close_base_draw_rate: float
    comeback_base_rate: float
    comeback_top_dna_rate: float
    comeback_top_dna_n: int
    comeback_mean_pred: float
    both_btts_base_rate: float
    both_btts_top_dna_rate: float
    both_btts_top_dna_n: int
    both_btts_mean_pred: float
    exact_top1_rate: float
    exact_top3_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _brier_3(probs: tuple[float, float, float], outcome: int) -> float:
    return sum((probs[i] - (1.0 if i == outcome else 0.0)) ** 2 for i in range(3))


def _logloss_3(probs: tuple[float, float, float], outcome: int) -> float:
    return -math.log(max(1e-6, probs[outcome]))


def _extract_odds_triplet(row: dict[str, Any], keys: tuple[str, str, str]) -> list[float] | None:
    vals = [_flt(row.get(k)) for k in keys]
    if all(v is not None and v > 1.01 for v in vals):
        return [float(v) for v in vals]  # type: ignore[arg-type]
    return None


def evaluate_high_odds_walkforward(
    divisions: tuple[str, ...] = ("E0", "D1", "SP1", "I1", "F1", "T1", "N1"),
    *,
    min_prior_team_matches: int = 5,
    xg_weight_cap: float = 0.14,
    steam_weight: float = 0.30,
    luck_cap: float = 0.020,
    data_dir: str = str(SEASON_DATA_DIR),
) -> WalkForwardSummary:
    """Run strictly causal walk-forward validation across played 2026/27 matches."""
    n_matches = 0
    n_close = 0
    close_mkt_brier = 0.0
    close_mod_brier = 0.0
    close_mkt_ll = 0.0
    close_mod_ll = 0.0
    high_draw_n = 0
    high_draw_hits = 0
    close_draw_hits = 0

    cb_records: list[tuple[float, float, int]] = []  # (dna, p_pred, hit)
    bb_records: list[tuple[float, float, int]] = []  # (dna, p_pred, hit)
    exact_top1 = 0
    exact_top3 = 0

    for div in divisions:
        raw_rows = list(load_division_rows(div, data_dir=data_dir))
        dated_rows: list[tuple[dt.date, dict[str, Any]]] = []
        for r in raw_rows:
            d = _parse_csv_date(r.get("Date"))
            if d is None:
                continue
            if _flt(r.get("HTHG")) is None or _flt(r.get("HTAG")) is None:
                continue
            dated_rows.append((d, r))
        dated_rows.sort(key=lambda x: x[0])

        # Group by matchdate so profiles are computed strictly on rows with Date < d (O(dates), fast!)
        unique_dates = sorted({d for d, _ in dated_rows})
        idx_ptr = 0
        history_rows: list[dict[str, Any]] = []

        for d in unique_dates:
            day_rows: list[dict[str, Any]] = []
            while idx_ptr < len(dated_rows) and dated_rows[idx_ptr][0] == d:
                day_rows.append(dated_rows[idx_ptr][1])
                idx_ptr += 1

            if len(history_rows) >= 40:
                xg_profiles = compute_team_xg_profiles(history_rows, as_of=d)
                half_profiles, lg_1h = compute_team_half_profiles(history_rows, as_of=d)
                h_xgs = [x for x in (_flt(r.get("HxG")) for r in history_rows) if x is not None]
                a_xgs = [x for x in (_flt(r.get("AxG")) for r in history_rows) if x is not None]
                mean_h = sum(h_xgs) / max(len(h_xgs), 1)
                mean_a = sum(a_xgs) / max(len(a_xgs), 1)
                lg_avg = max(0.5, 0.5 * (mean_h + mean_a))
                n_m = float(len(h_xgs))
                h_mult = ((mean_h / lg_avg) * n_m + 1.11 * 30.0) / (n_m + 30.0)
                a_mult = ((mean_a / lg_avg) * n_m + 0.89 * 30.0) / (n_m + 30.0)

                for r in day_rows:
                    home, away = str(r["HomeTeam"]), str(r["AwayTeam"])
                    hp_xg, ap_xg = xg_profiles.get(home), xg_profiles.get(away)
                    hp_hf, ap_hf = half_profiles.get(home), half_profiles.get(away)
                    if not hp_xg or not ap_xg or not hp_hf or not ap_hf:
                        continue
                    if min(hp_xg.matches, ap_xg.matches) < min_prior_team_matches:
                        continue

                    open_1x2 = (
                        _extract_odds_triplet(r, ("BFEH", "BFED", "BFEA"))
                        or _extract_odds_triplet(r, ("AvgH", "AvgD", "AvgA"))
                    )
                    close_1x2 = (
                        _extract_odds_triplet(r, ("BFECH", "BFECD", "BFECA"))
                        or _extract_odds_triplet(r, ("AvgCH", "AvgCD", "AvgCA"))
                        or open_1x2
                    )
                    ou_odds = (
                        [_flt(r.get("BFE>2.5")), _flt(r.get("BFE<2.5"))]
                        if _flt(r.get("BFE>2.5")) and _flt(r.get("BFE<2.5"))
                        else [_flt(r.get("Avg>2.5")), _flt(r.get("Avg<2.5"))]
                    )
                    if not open_1x2 or not close_1x2 or not ou_odds[0] or not ou_odds[1]:
                        continue

                    p_open = devig(open_1x2, method="power").probabilities
                    p_close = devig(close_1x2, method="power").probabilities
                    steam_1x2 = [round(float(p_close[i] - p_open[i]), 5) for i in range(3)]
                    p_o25 = float(devig([float(ou_odds[0]), float(ou_odds[1])], method="power").probabilities[0])

                    ah_line = _flt(r.get("AHCh") if r.get("AHCh") not in (None, "") else r.get("AHh"))
                    ah_h = _flt(r.get("BFECAHH") or r.get("BFEAHH") or r.get("AvgCAHH") or r.get("AvgAHH"))
                    ah_a = _flt(r.get("BFECAHA") or r.get("BFEAHA") or r.get("AvgCAHA") or r.get("AvgAHA"))
                    ref_ah = [ah_line, [ah_h, ah_a]] if (ah_line is not None and ah_h and ah_a) else None

                    if ref_ah is not None:
                        p_ah_h = float(devig([ah_h, ah_a], method="power").probabilities[0])
                        mu_h, mu_a, _ = invert_ah_ou_1x2(ah_line, p_ah_h, p_o25)
                    else:
                        tot = max(1.5, min(4.2, 2.55 + 2.2 * (p_o25 - 0.5)))
                        diff = max(-1.8, min(1.8, 2.4 * (float(p_close[0]) - float(p_close[2]))))
                        mu_h = max(0.35, 0.5 * (tot + diff))
                        mu_a = max(0.35, 0.5 * (tot - diff))

                    xg_mu_h = max(0.25, min(4.2, lg_avg * hp_xg.attack_index * ap_xg.defense_index * h_mult))
                    xg_mu_a = max(0.25, min(4.2, lg_avg * ap_xg.attack_index * hp_xg.defense_index * a_mult))

                    home_eff = 0.60 * hp_hf.h1_attack_share + 0.40 * ap_hf.h1_concede_share
                    away_eff = 0.60 * ap_hf.h1_attack_share + 0.40 * hp_hf.h1_concede_share
                    sw = min(1.0, min(hp_hf.matches, ap_hf.matches) / 12.0)
                    h_sh = max(-0.08, min(0.08, (home_eff - lg_1h) * sw))
                    a_sh = max(-0.08, min(0.08, (away_eff - lg_1h) * sw))

                    match_rec: dict[str, Any] = {
                        "code": n_matches + 1,
                        "kickoff": f"{d.isoformat()} 15:00",
                        "league": div,
                        "home": home,
                        "away": away,
                        "status": "fiyatlandı",
                        "mu_home": round(float(mu_h), 3),
                        "mu_away": round(float(mu_a), 3),
                        "fair_1x2": [round(float(x), 5) for x in p_open],
                        "steam_1x2": steam_1x2,
                        "ref_ah": ref_ah,
                        "selections": [
                            {"name": "MS 1", "odds": open_1x2[0], "fair_prob": float(p_open[0]), "direct": True},
                            {"name": "MS 0", "odds": open_1x2[1], "fair_prob": float(p_open[1]), "direct": True},
                            {"name": "MS 2", "odds": open_1x2[2], "fair_prob": float(p_open[2]), "direct": True},
                            {"name": "2.5 Üst", "odds": float(ou_odds[0]), "fair_prob": p_o25, "direct": True},
                        ],
                        "research": {
                            "xg_intelligence": {
                                "xg_mu_home": round(xg_mu_h, 3),
                                "xg_mu_away": round(xg_mu_a, 3),
                                "home": {
                                    "matches": hp_xg.matches,
                                    "finishing_luck": hp_xg.finishing_overperformance,
                                    "defensive_luck": hp_xg.defensive_overperformance,
                                },
                                "away": {
                                    "matches": ap_xg.matches,
                                    "finishing_luck": ap_xg.finishing_overperformance,
                                    "defensive_luck": ap_xg.defensive_overperformance,
                                },
                            },
                            "half_split": {
                                "league_1h_share": lg_1h,
                                "home_eff_1h_share": round(lg_1h + h_sh, 4),
                                "away_eff_1h_share": round(lg_1h + a_sh, 4),
                                "home_1h_urgency_shift": round(h_sh, 4),
                                "away_1h_urgency_shift": round(a_sh, 4),
                                "home": hp_hf.to_dict(),
                                "away": ap_hf.to_dict(),
                            },
                            "flags": [],
                        },
                    }

                    ft_h, ft_a = int(_flt(r["FTHG"]) or 0), int(_flt(r["FTAG"]) or 0)
                    ht_h, ht_a = int(_flt(r["HTHG"]) or 0), int(_flt(r["HTAG"]) or 0)
                    h2_h, h2_a = ft_h - ht_h, ft_a - ht_a
                    outcome_idx = 0 if ft_h > ft_a else (1 if ft_h == ft_a else 2)
                    n_matches += 1

                    # 1. Close-match evaluation (balanced odds regime, e.g. 2.20 / 3.30 / 2.55)
                    if 1.85 <= open_1x2[0] <= 3.30 and 1.85 <= open_1x2[2] <= 3.30:
                        cm = analyze_close_match(
                            match_rec,
                            xg_weight_cap=xg_weight_cap,
                            steam_weight=steam_weight,
                            luck_cap=luck_cap,
                        )
                        if cm is not None:
                            n_close += 1
                            mkt_p = (cm.market_1x2["MS 1"], cm.market_1x2["MS 0"], cm.market_1x2["MS 2"])
                            mod_p = (cm.model_1x2["MS 1"], cm.model_1x2["MS 0"], cm.model_1x2["MS 2"])
                            close_mkt_brier += _brier_3(mkt_p, outcome_idx)
                            close_mod_brier += _brier_3(mod_p, outcome_idx)
                            close_mkt_ll += _logloss_3(mkt_p, outcome_idx)
                            close_mod_ll += _logloss_3(mod_p, outcome_idx)
                            if outcome_idx == 1:
                                close_draw_hits += 1
                            if cm.draw_regime_score >= 62.0:
                                high_draw_n += 1
                                if outcome_idx == 1:
                                    high_draw_hits += 1

                    # 2. Comeback HT/FT (1/2 & 2/1)
                    hit_12 = int(ht_h > ht_a and ft_h < ft_a)
                    hit_21 = int(ht_h < ht_a and ft_h > ft_a)
                    for cb in score_comeback_htft(match_rec):
                        hit = hit_12 if cb.kind == "İY/MS 1/2" else hit_21
                        cb_records.append((cb.dna_score, cb.p_comeback, hit))

                    # 3. Both-Halves BTTS
                    hit_bb = int(ht_h >= 1 and ht_a >= 1 and h2_h >= 1 and h2_a >= 1)
                    bb = score_both_halves_btts_match(match_rec)
                    if bb is not None:
                        bb_records.append((bb.dna_score, bb.p_tail, hit_bb))

                    # 4. Exact Scores
                    es = analyze_exact_scores(match_rec)
                    if es is not None and es.top_coherent:
                        actual_sc = f"{ft_h}-{ft_a}"
                        top3_sc = [x.score for x in es.top_coherent[:3]]
                        if top3_sc[0] == actual_sc:
                            exact_top1 += 1
                        if actual_sc in top3_sc:
                            exact_top3 += 1

            history_rows.extend(day_rows)

    def _top_decile_stats(recs: list[tuple[float, float, int]], frac: float = 0.15) -> tuple[float, float, int, float]:
        if not recs:
            return 0.0, 0.0, 0, 0.0
        base = sum(x[2] for x in recs) / len(recs)
        mean_p = sum(x[1] for x in recs) / len(recs)
        s = sorted(recs, key=lambda x: -x[0])
        k = max(1, int(round(len(s) * frac)))
        top_rate = sum(x[2] for x in s[:k]) / k
        return round(base, 4), round(top_rate, 4), k, round(mean_p, 4)

    cb_base, cb_top, cb_top_n, cb_pred = _top_decile_stats(cb_records)
    bb_base, bb_top, bb_top_n, bb_pred = _top_decile_stats(bb_records)

    return WalkForwardSummary(
        n_matches=n_matches,
        n_close_matches=n_close,
        close_market_brier=round(close_mkt_brier / max(n_close, 1), 5),
        close_model_brier=round(close_mod_brier / max(n_close, 1), 5),
        close_market_logloss=round(close_mkt_ll / max(n_close, 1), 5),
        close_model_logloss=round(close_mod_ll / max(n_close, 1), 5),
        close_high_draw_n=high_draw_n,
        close_high_draw_rate=round(high_draw_hits / max(high_draw_n, 1), 4),
        close_base_draw_rate=round(close_draw_hits / max(n_close, 1), 4),
        comeback_base_rate=cb_base,
        comeback_top_dna_rate=cb_top,
        comeback_top_dna_n=cb_top_n,
        comeback_mean_pred=cb_pred,
        both_btts_base_rate=bb_base,
        both_btts_top_dna_rate=bb_top,
        both_btts_top_dna_n=bb_top_n,
        both_btts_mean_pred=bb_pred,
        exact_top1_rate=round(exact_top1 / max(n_matches, 1), 4),
        exact_top3_rate=round(exact_top3 / max(n_matches, 1), 4),
    )


if __name__ == "__main__":
    summary = evaluate_high_odds_walkforward()
    for k, v in summary.to_dict().items():
        print(f"{k}: {v}")
