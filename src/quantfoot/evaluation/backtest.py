"""Strict zero-leakage walk-forward v4 backtester across Pyramid club leagues and Pinnacle 2026 feeds."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

from quantfoot.data.loader import DEFAULT_LEAGUES, load_matches, load_tipsaudit
from quantfoot.data.xg_proxy import BoxScoreXGModel
from quantfoot.evaluation.metrics import (
    betting_metrics,
    classwise_ece,
    multiclass_brier,
    multiclass_log_loss,
    ranked_probability_score,
    simulate_kelly_equity,
)
from quantfoot.markets.devig import DevigMethod, devig_batch
from quantfoot.markets.pricing import invert_ah_ou_1x2, price_all_markets
from quantfoot.models.dixon_coles import TimeDecayedDixonColes
from quantfoot.models.ensemble import FundamentalEnsemble
from quantfoot.models.gap_ratings import WheatcroftGAPRatings
from quantfoot.models.gas_poisson import GASPoissonModel
from quantfoot.models.glicko2 import FootballGlicko2
from quantfoot.models.kalman import KalmanPoissonModel
from quantfoot.models.pyramid import PYRAMID_DIVISIONS
from quantfoot.models.ratings import CausalRatingEngine
from quantfoot.strategy.clv_filter import CLVPreservationFilter
from quantfoot.strategy.kelly import baker_mchale_kelly_fraction


def _evaluate_selection_strategy(
    probs_mat: np.ndarray,
    odds_mat: np.ndarray,
    y_idx: np.ndarray,
    min_ev: float,
    min_odds: float,
    max_odds: float,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
) -> dict[str, object]:
    ev_mat = probs_mat * odds_mat - 1.0
    best_c = np.argmax(ev_mat, axis=1)
    best_ev = ev_mat[np.arange(len(ev_mat)), best_c]
    taken_odds = odds_mat[np.arange(len(odds_mat)), best_c]
    sel_probs = probs_mat[np.arange(len(probs_mat)), best_c]

    mask = (best_ev >= min_ev) & (taken_odds >= min_odds) & (taken_odds <= max_odds)
    won = y_idx[mask] == best_c[mask]
    flat_returns = np.where(won, taken_odds[mask] - 1.0, -1.0)
    flat_curve = np.concatenate([[0.0], np.cumsum(flat_returns)])
    kelly_sim = simulate_kelly_equity(
        sel_probs[mask],
        taken_odds[mask],
        won,
        kelly_mult=kelly_mult,
        max_stake=max_stake,
    )
    return {
        "metrics": betting_metrics(flat_returns, taken_odds[mask]),
        "flat_curve": flat_curve,
        "kelly": kelly_sim,
        "mask": mask,
        "selected_probs": sel_probs[mask],
        "taken_odds": taken_odds[mask],
        "won": won,
    }


def _evaluate_masked_bm_kelly(
    probs: np.ndarray,
    odds: np.ndarray,
    won: np.ndarray,
    mask: np.ndarray,
    prob_std: np.ndarray | float = 0.012,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
    initial_bankroll: float = 1000.0,
) -> dict[str, object]:
    sel_won = won[mask]
    sel_odds = odds[mask]
    sel_probs = probs[mask]
    flat_returns = np.where(sel_won, sel_odds - 1.0, -1.0)
    stds = np.full(len(sel_odds), prob_std) if np.ndim(prob_std) == 0 else np.asarray(prob_std)[mask]

    bank = float(initial_bankroll)
    peak = bank
    max_dd = 0.0
    curve = [bank]
    for p, o, w, sd in zip(sel_probs, sel_odds, sel_won, stds):
        f = baker_mchale_kelly_fraction(float(p), float(o), prob_std=float(sd), multiplier=kelly_mult, max_stake=max_stake)
        if f <= 0.0:
            continue
        stake = bank * f
        bank += stake * (float(o) - 1.0) if bool(w) else -stake
        peak = max(peak, bank)
        dd = (peak - bank) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        curve.append(bank)

    return {
        "metrics": betting_metrics(flat_returns, sel_odds),
        "flat_curve": np.concatenate([[0.0], np.cumsum(flat_returns)]) if len(flat_returns) else np.array([0.0]),
        "kelly": {
            "initial_bankroll": initial_bankroll,
            "final_bankroll": float(bank),
            "total_return_pct": float((bank / initial_bankroll - 1.0) * 100.0),
            "max_drawdown_pct": float(max_dd * 100.0),
            "curve": np.asarray(curve, dtype=float),
        },
        "mask": mask,
        "selected_probs": sel_probs,
        "taken_odds": sel_odds,
        "won": sel_won,
    }


def _best_market_candidates(probs_mat: np.ndarray, odds_mat: np.ndarray, y_idx: np.ndarray):
    ev_mat = probs_mat * odds_mat - 1.0
    best_c = np.argmax(ev_mat, axis=1)
    rows = np.arange(len(ev_mat))
    return (
        ev_mat[rows, best_c],
        odds_mat[rows, best_c],
        probs_mat[rows, best_c],
        y_idx == best_c,
    )


def _evaluate_joint_portfolio(
    p_1x2: np.ndarray,
    odds_1x2: np.ndarray,
    y_1x2: np.ndarray,
    p_ou: np.ndarray,
    odds_ou: np.ndarray,
    y_ou: np.ndarray,
    ou_ok: np.ndarray,
    min_ev_1x2: float,
    max_odds_1x2: float,
    min_ev_ou: float = 0.010,
    max_odds_ou: float = 3.00,
    min_odds: float = 1.25,
    kelly_mult: float = 0.25,
    max_stake: float = 0.03,
    same_match_corr_damp: float = 0.85,
    prob_std: float = 0.01,
    initial_bankroll: float = 1000.0,
) -> dict[str, object]:
    """Simulate a joint 1X2 + O/U 2.5 portfolio with Baker-McHale Kelly & same-match correlation dampening."""
    ev_1x2, odd_1x2, prob_1x2, won_1x2 = _best_market_candidates(p_1x2, odds_1x2, y_1x2)
    ev_ou, odd_ou, prob_ou, won_ou = _best_market_candidates(p_ou, odds_ou, y_ou)

    bank = float(initial_bankroll)
    peak = bank
    max_dd = 0.0
    curve = [bank]
    flat_returns: list[float] = []
    taken_odds_list: list[float] = []
    sel_probs_list: list[float] = []
    won_list: list[bool] = []
    mask = np.zeros(len(y_1x2), dtype=bool)

    for i in range(len(y_1x2)):
        take_1 = (ev_1x2[i] >= min_ev_1x2) and (min_odds <= odd_1x2[i] <= max_odds_1x2)
        take_2 = bool(ou_ok[i]) and (ev_ou[i] >= min_ev_ou) and (min_odds <= odd_ou[i] <= max_odds_ou)
        if not (take_1 or take_2):
            continue

        mask[i] = True
        damp = same_match_corr_damp if (take_1 and take_2) else 1.0
        pnl = 0.0
        if take_1:
            f1 = baker_mchale_kelly_fraction(
                float(prob_1x2[i]), float(odd_1x2[i]), prob_std=prob_std, multiplier=kelly_mult, max_stake=max_stake
            ) * damp
            s1 = bank * f1
            pnl += s1 * (float(odd_1x2[i]) - 1.0) if bool(won_1x2[i]) else -s1
            flat_returns.append(float(odd_1x2[i]) - 1.0 if bool(won_1x2[i]) else -1.0)
            taken_odds_list.append(float(odd_1x2[i]))
            sel_probs_list.append(float(prob_1x2[i]))
            won_list.append(bool(won_1x2[i]))

        if take_2:
            f2 = baker_mchale_kelly_fraction(
                float(prob_ou[i]), float(odd_ou[i]), prob_std=prob_std, multiplier=kelly_mult, max_stake=max_stake
            ) * damp
            s2 = bank * f2
            pnl += s2 * (float(odd_ou[i]) - 1.0) if bool(won_ou[i]) else -s2
            flat_returns.append(float(odd_ou[i]) - 1.0 if bool(won_ou[i]) else -1.0)
            taken_odds_list.append(float(odd_ou[i]))
            sel_probs_list.append(float(prob_ou[i]))
            won_list.append(bool(won_ou[i]))

        bank += pnl
        peak = max(peak, bank)
        dd = (peak - bank) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        curve.append(bank)

    flat_arr = np.asarray(flat_returns, dtype=float)
    odds_arr = np.asarray(taken_odds_list, dtype=float)
    return {
        "metrics": betting_metrics(flat_arr, odds_arr),
        "flat_curve": np.concatenate([[0.0], np.cumsum(flat_arr)]) if len(flat_arr) else np.array([0.0]),
        "kelly": {
            "initial_bankroll": initial_bankroll,
            "final_bankroll": float(bank),
            "total_return_pct": float((bank / initial_bankroll - 1.0) * 100.0),
            "max_drawdown_pct": float(max_dd * 100.0),
            "curve": np.asarray(curve, dtype=float),
        },
        "mask": mask,
        "selected_probs": np.asarray(sel_probs_list, dtype=float),
        "taken_odds": odds_arr,
        "won": np.asarray(won_list, dtype=bool),
    }


def order_matches_for_backtest(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic same-day order: date, kickoff/time when present, then division."""
    sort_cols = ["MatchDate"]
    if "MatchTime" in df.columns:
        sort_cols.append("MatchTime")
    if "kickoff_utc" in df.columns:
        sort_cols.append("kickoff_utc")
    if "Division" in df.columns:
        sort_cols.append("Division")
    return df.sort_values(sort_cols, na_position="first").reset_index(drop=True)


def _fit_causal_xg_proxies(
    df: pd.DataFrame,
    raw_all: pd.DataFrame,
    start_ts: pd.Timestamp,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit BoxScoreXGModel strictly prior to start_ts and return causal xG proxies for df."""
    try:
        xg_model = BoxScoreXGModel(alpha=1.0).fit(raw_all, max_date=start_ts)
        return xg_model.transform(df)
    except ValueError:
        hsot = df["HomeTarget"].fillna(4.2).to_numpy(dtype=float)
        asot = df["AwayTarget"].fillna(4.2).to_numpy(dtype=float)
        return np.clip(hsot * 0.30, 0.10, 5.50), np.clip(asot * 0.30, 0.10, 5.50)


def run_walk_forward_backtest(
    leagues: Iterable[str] = DEFAULT_LEAGUES,
    start_date: str = "2016-07-01",
    cal_start: str = "2018-08-01",
    test_start: str = "2021-08-01",
    refit_days: int = 14,
    devig_method: DevigMethod = "power",
    min_ev: float = 0.015,
    max_odds: float = 3.50,
    kelly_mult: float = 0.25,
    expanding_refit: bool = True,
    data_dir=None,
) -> dict[str, object]:
    """Run strict chronological walk-forward v4 Pyramid modeling & multi-market betting backtest."""
    target_leagues = list(leagues)
    target_set = set(target_leagues)
    all_load_leagues = sorted(set(PYRAMID_DIVISIONS) | target_set)
    start_ts = pd.Timestamp(start_date)
    xg_train_min = min(pd.Timestamp("2014-01-01"), start_ts - pd.Timedelta(days=730)).strftime("%Y-%m-%d")

    raw_all = load_matches(data_dir=data_dir, leagues=all_load_leagues, min_date=xg_train_min, require_odds=True)
    df = order_matches_for_backtest(raw_all[raw_all["MatchDate"] >= start_ts])
    h_xg_all, a_xg_all = _fit_causal_xg_proxies(df, raw_all, start_ts)
    df["h_xg_proxy"] = h_xg_all
    df["a_xg_proxy"] = a_xg_all

    cal_ts = pd.Timestamp(cal_start)
    # Global Pyramid rating & process state trackers across feeder and top divisions
    rating = CausalRatingEngine()
    glicko = FootballGlicko2()
    kalman = KalmanPoissonModel()
    gap_sot = WheatcroftGAPRatings(lam=0.06, phi1=0.70, phi2=0.70, base_stat=9.0)
    gap_vol = WheatcroftGAPRatings(lam=0.06, phi1=0.70, phi2=0.70, base_stat=24.0)
    gap_xg = WheatcroftGAPRatings(lam=0.075, phi1=0.72, phi2=0.72, base_stat=2.7)

    # League-scoped generative score-matrix trackers
    gas_map = {d: GASPoissonModel() for d in target_leagues}
    dc_goals_map = {d: TimeDecayedDixonColes(xi=0.0020, l2_reg=0.05) for d in target_leagues}
    dc_hybrid_map = {d: TimeDecayedDixonColes(xi=0.0020, l2_reg=0.06) for d in target_leagues}
    dc_hist = {d: [] for d in target_leagues}
    dc_last_fit = {d: None for d in target_leagues}
    dc_fitted = {d: False for d in target_leagues}
    in_div_games: dict[str, dict[str, int]] = {d: {} for d in target_leagues}
    lg_stats = {d: [0.0, 0.0, 0] for d in target_leagues}

    records = []
    for row in df.itertuples(index=False):
        div = str(row.Division)
        mdate = row.MatchDate
        home, away = row.HomeTeam, row.AwayTeam

        if div in target_set:
            if len(dc_hist[div]) >= 250 and (dc_last_fit[div] is None or (mdate - dc_last_fit[div]).days >= refit_days):
                hdf = pd.DataFrame(dc_hist[div][-900:])
                days_ago = (mdate - hdf["date"]).dt.days.to_numpy(dtype=float)
                dc_goals_map[div].fit(hdf["home"], hdf["away"], hdf["hg"], hdf["ag"], days_ago)
                dc_hybrid_map[div].fit(
                    hdf["home"], hdf["away"], hdf["hg"], hdf["ag"], days_ago,
                    home_xg=hdf["hxg"], away_xg=hdf["axg"], xg_weight=0.25,
                )
                dc_last_fit[div] = mdate
                dc_fitted[div] = True

            div_min_g = min(in_div_games[div].get(home, 0), in_div_games[div].get(away, 0))
            if dc_fitted[div] and mdate >= cal_ts and div_min_g >= 4:
                feats = rating.pre_match_features(home, away, mdate, div=div)
                glicko_feats = glicko.pre_match_features(home, away, mdate, div=div)
                kal_p = kalman.predict_1x2(home, away, match_date=mdate, div=div)
                kal_lam, kal_mu = kalman.expected_goals(home, away, match_date=mdate, div=div)
                kal_unc = kalman.posterior_uncertainty(home, away, match_date=mdate, div=div)
                exp_sot_h, exp_sot_a = gap_sot.expected_stats(home, away, div=div)
                exp_vol_h, exp_vol_a = gap_vol.expected_stats(home, away, div=div)
                exp_xg_h, exp_xg_a = gap_xg.expected_stats(home, away, div=div)
                gas_p = gas_map[div].predict_1x2(home, away)
                g1 = price_all_markets(dc_goals_map[div].score_matrix(home, away))["1x2"]
                dh_p = dc_hybrid_map[div].predict_1x2(home, away)
                lg_g, lg_h, lg_n = lg_stats[div]

                records.append(
                    {
                        "Division": div,
                        "MatchDate": mdate,
                        "HomeTeam": home,
                        "AwayTeam": away,
                        "y": int(row.y),
                        "FTHome": float(row.FTHome),
                        "FTAway": float(row.FTAway),
                        "OddHome": float(row.OddHome),
                        "OddDraw": float(row.OddDraw),
                        "OddAway": float(row.OddAway),
                        "MaxHome": float(row.MaxHome) if pd.notna(row.MaxHome) else float(row.OddHome),
                        "MaxDraw": float(row.MaxDraw) if pd.notna(row.MaxDraw) else float(row.OddDraw),
                        "MaxAway": float(row.MaxAway) if pd.notna(row.MaxAway) else float(row.OddAway),
                        "Over25": row.Over25,
                        "Under25": row.Under25,
                        "MaxOver25": row.MaxOver25,
                        "MaxUnder25": row.MaxUnder25,
                        "HandiSize": row.HandiSize if hasattr(row, "HandiSize") else np.nan,
                        "HandiHome": row.HandiHome if hasattr(row, "HandiHome") else np.nan,
                        "HandiAway": row.HandiAway if hasattr(row, "HandiAway") else np.nan,
                        "dcg_h": g1["H"],
                        "dcg_d": g1["D"],
                        "dcg_a": g1["A"],
                        "dch_h": float(dh_p[0]),
                        "dch_d": float(dh_p[1]),
                        "dch_a": float(dh_p[2]),
                        "kal_h": float(kal_p[0]),
                        "kal_d": float(kal_p[1]),
                        "kal_a": float(kal_p[2]),
                        "kal_lam": float(kal_lam),
                        "kal_mu": float(kal_mu),
                        "kal_uncert": float(kal_unc),
                        "gas_h": float(gas_p[0]),
                        "gas_d": float(gas_p[1]),
                        "gas_a": float(gas_p[2]),
                        "gap_sot_diff": exp_sot_h - exp_sot_a,
                        "gap_sot_sum": exp_sot_h + exp_sot_a,
                        "gap_vol_diff": exp_vol_h - exp_vol_a,
                        "gap_vol_sum": exp_vol_h + exp_vol_a,
                        "gap_xg_diff": exp_xg_h - exp_xg_a,
                        "gap_xg_sum": exp_xg_h + exp_xg_a,
                        "lg_avg_goals": (lg_g / lg_n) if lg_n >= 30 else 2.6,
                        "lg_home_rate": (lg_h / lg_n) if lg_n >= 30 else 0.45,
                        "is_covid": 1.0 if (pd.Timestamp("2020-05-01") <= mdate < pd.Timestamp("2021-07-01")) else 0.0,
                        **glicko_feats,
                        **feats,
                    }
                )

        hg, ag = float(row.FTHome), float(row.FTAway)
        hxg, axg = float(row.h_xg_proxy), float(row.a_xg_proxy)
        hsot = float(row.HomeTarget) if pd.notna(row.HomeTarget) else 4.2
        asot = float(row.AwayTarget) if pd.notna(row.AwayTarget) else 4.2
        hsh = float(row.HomeShots) if pd.notna(row.HomeShots) else 12.0
        ash = float(row.AwayShots) if pd.notna(row.AwayShots) else 12.0
        hc = float(row.HomeCorners) if pd.notna(row.HomeCorners) else 5.0
        ac = float(row.AwayCorners) if pd.notna(row.AwayCorners) else 5.0
        hth = float(row.HTHome) if hasattr(row, "HTHome") and pd.notna(row.HTHome) else 0.5 * hg
        hta = float(row.HTAway) if hasattr(row, "HTAway") and pd.notna(row.HTAway) else 0.5 * ag
        ht_gd = hth - hta
        cards_h = (float(row.HomeYellow) if hasattr(row, "HomeYellow") and pd.notna(row.HomeYellow) else 1.8) + 2.5 * (
            float(row.HomeRed) if hasattr(row, "HomeRed") and pd.notna(row.HomeRed) else 0.0
        )
        cards_a = (float(row.AwayYellow) if hasattr(row, "AwayYellow") and pd.notna(row.AwayYellow) else 2.0) + 2.5 * (
            float(row.AwayRed) if hasattr(row, "AwayRed") and pd.notna(row.AwayRed) else 0.0
        )
        gs_hxg = hxg * (0.90 if ht_gd <= -2.0 else (1.06 if ht_gd >= 2.0 else 1.0))
        gs_axg = axg * (0.90 if ht_gd >= 2.0 else (1.06 if ht_gd <= -2.0 else 1.0))

        kalman.update(home, away, hg, ag, hxg=gs_hxg, axg=gs_axg, hsot=hsot, asot=asot, match_date=mdate, div=div)
        glicko.update(home, away, hg, ag, mdate, div=div)
        gap_sot.update(home, away, hsot, asot, div=div)
        gap_vol.update(
            home, away,
            0.60 * hsot + 0.15 * max(hsh - hsot, 0.0) + 0.25 * hc,
            0.60 * asot + 0.15 * max(ash - asot, 0.0) + 0.25 * ac,
            div=div,
        )
        gap_xg.update(home, away, gs_hxg, gs_axg, div=div)
        rating.update(
            home, away, hg, ag, hxg, axg, hsot, asot, hsh, ash, mdate,
            div=div, ht_gd=ht_gd, cards_h=cards_h, cards_a=cards_a,
        )

        if div in target_set:
            gas_map[div].update(home, away, hg, ag, hxg=gs_hxg, axg=gs_axg, match_date=mdate)
            dc_hist[div].append({"date": mdate, "home": home, "away": away, "hg": hg, "ag": ag, "hxg": gs_hxg, "axg": gs_axg})
            in_div_games[div][home] = in_div_games[div].get(home, 0) + 1
            in_div_games[div][away] = in_div_games[div].get(away, 0) + 1
            lg_stats[div][0] += hg + ag
            lg_stats[div][1] += 1.0 if hg > ag else 0.0
            lg_stats[div][2] += 1

    rdf = pd.DataFrame(records).sort_values("MatchDate").reset_index(drop=True)
    test_ts = pd.Timestamp(test_start)
    cal_df = rdf[rdf["MatchDate"] < test_ts].reset_index(drop=True)
    test_df = rdf[rdf["MatchDate"] >= test_ts].reset_index(drop=True)
    y_test = test_df["y"].to_numpy(dtype=int)

    # Expanding yearly causal refit of FundamentalEnsemble strictly < season_start
    if expanding_refit:
        season_cuts = [test_start, "2022-08-01", "2023-08-01", "2024-08-01", "2025-08-01", "2099-01-01"]
        comp_chunks: dict[str, np.ndarray] = {}
        ensemble = FundamentalEnsemble()
        for idx in range(len(season_cuts) - 1):
            c0, c1 = pd.Timestamp(season_cuts[idx]), pd.Timestamp(season_cuts[idx + 1])
            msk = (test_df["MatchDate"] >= c0) & (test_df["MatchDate"] < c1)
            if not msk.any():
                continue
            tr_k = rdf[rdf["MatchDate"] < c0].reset_index(drop=True)
            ensemble = FundamentalEnsemble().fit(tr_k)
            c_part = ensemble.predict_components(test_df.loc[msk])
            for key, arr in c_part.items():
                if key not in comp_chunks:
                    comp_chunks[key] = np.zeros((len(test_df), *arr.shape[1:]), dtype=arr.dtype)
                comp_chunks[key][msk] = arr
        comps = comp_chunks
    else:
        ensemble = FundamentalEnsemble().fit(cal_df)
        comps = ensemble.predict_components(test_df)

    p_b365_devig = devig_batch(test_df[["OddHome", "OddDraw", "OddAway"]].to_numpy(dtype=float), method=devig_method)
    p_b365_mult = devig_batch(test_df[["OddHome", "OddDraw", "OddAway"]].to_numpy(dtype=float), method="multiplicative")

    # Cross-market low-vig Asian Handicap + O/U 2.5 implied 1X2 extraction
    ah_ou_ok = (
        test_df[["HandiSize", "HandiHome", "HandiAway", "Over25", "Under25"]].notna().all(axis=1)
        & (test_df["HandiHome"] > 1.05)
        & (test_df["HandiAway"] > 1.05)
        & (test_df["Over25"] > 1.05)
        & (test_df["Under25"] > 1.05)
    ).to_numpy()
    p_ah_implied = p_b365_devig.copy()
    if np.any(ah_ou_ok):
        p_ah_2w = devig_batch(test_df.loc[ah_ou_ok, ["HandiHome", "HandiAway"]].to_numpy(dtype=float), method=devig_method)
        p_ou_2w = devig_batch(test_df.loc[ah_ou_ok, ["Under25", "Over25"]].to_numpy(dtype=float), method=devig_method)
        ah_lines = test_df.loc[ah_ou_ok, "HandiSize"].to_numpy(dtype=float)
        ah_idx = np.flatnonzero(ah_ou_ok)
        for j, row_i in enumerate(ah_idx):
            _, _, p_ah_implied[row_i] = invert_ah_ou_1x2(float(ah_lines[j]), float(p_ah_2w[j, 0]), float(p_ou_2w[j, 1]))
    p_mkt_blend = 0.70 * p_b365_devig + 0.30 * p_ah_implied
    p_mkt_blend /= np.sum(p_mkt_blend, axis=1, keepdims=True)

    model_scores = {}
    candidates = {
        "Pyramid Causal Elo": comps["elo"],
        "Pyramid Glicko-2": comps["glicko2"],
        "Pyramid Pi-Ratings": comps["pi"],
        "Dixon-Coles (Goals)": comps["dc_goals"],
        "Dixon-Coles Hybrid (Goals+xG)": comps["dc_hybrid"],
        "Kalman State-Space Poisson": comps["kalman"],
        "Dual-GAS (GameState xG)": comps["gas_poisson"],
        "Tier-GAP + xG (MultiLogit)": comps["gap_elo"],
        "Tier-GAP + xG (OrderedLogit)": comps["gap_ordered"],
        "Regularized MLP (v4 Features)": comps["mlp"],
        "LightGBM (v4 Features)": comps["lgbm"],
        "V4-Pyramid Expanding (Raw)": comps["raw_ensemble"],
        "V4-Pyramid Expanding (Calibrated)": comps["calibrated_ensemble"],
        "Market B365 (Multiplicative)": p_b365_mult,
        "Market AH+OU Implied 1X2": p_ah_implied,
        f"Market B365 ({devig_method.title()})": p_b365_devig,
    }
    for name, pm in candidates.items():
        model_scores[name] = {
            "log_loss": multiclass_log_loss(pm, y_test),
            "rps": ranked_probability_score(pm, y_test),
            "brier": multiclass_brier(pm, y_test),
            "ece": classwise_ece(pm, y_test),
        }

    max_odds_mat = test_df[["MaxHome", "MaxDraw", "MaxAway"]].to_numpy(dtype=float)
    b365_odds_mat = test_df[["OddHome", "OddDraw", "OddAway"]].to_numpy(dtype=float)

    pure_vs_b365 = _evaluate_selection_strategy(
        comps["calibrated_ensemble"], b365_odds_mat, y_test, min_ev=0.03, min_odds=1.25, max_odds=max_odds, kelly_mult=kelly_mult
    )
    sharp_vs_max = _evaluate_selection_strategy(
        p_b365_devig, max_odds_mat, y_test, min_ev=min_ev, min_odds=1.25, max_odds=max_odds, kelly_mult=kelly_mult
    )
    cross_mkt_vs_max = _evaluate_selection_strategy(
        p_mkt_blend, max_odds_mat, y_test, min_ev=min_ev, min_odds=1.25, max_odds=max_odds, kelly_mult=kelly_mult
    )

    ou_ok = (
        test_df[["Over25", "Under25", "MaxOver25", "MaxUnder25"]].notna().all(axis=1)
        & (test_df["Over25"] > 1.01)
        & (test_df["Under25"] > 1.01)
        & (test_df["MaxOver25"] > 1.01)
        & (test_df["MaxUnder25"] > 1.01)
    ).to_numpy()
    p_ou_full = np.zeros((len(test_df), 2), dtype=float)
    p_ou_full[ou_ok] = devig_batch(test_df.loc[ou_ok, ["Under25", "Over25"]].to_numpy(dtype=float), method=devig_method)
    y_ou_full = (test_df["FTHome"] + test_df["FTAway"] > 2).to_numpy(dtype=int)
    max_ou_full = test_df[["MaxUnder25", "MaxOver25"]].fillna(1.0).to_numpy(dtype=float)

    ou_vs_max = _evaluate_selection_strategy(
        p_ou_full[ou_ok], max_ou_full[ou_ok], y_ou_full[ou_ok], min_ev=0.01, min_odds=1.25, max_odds=3.00, kelly_mult=kelly_mult
    )
    joint_portfolio = _evaluate_joint_portfolio(
        p_1x2=p_b365_devig,
        odds_1x2=max_odds_mat,
        y_1x2=y_test,
        p_ou=p_ou_full,
        odds_ou=max_ou_full,
        y_ou=y_ou_full,
        ou_ok=ou_ok,
        min_ev_1x2=min_ev,
        max_odds_1x2=max_odds,
        kelly_mult=kelly_mult,
    )

    return {
        "n_cal": int(len(cal_df)),
        "n_test": int(len(test_df)),
        "test_df": test_df,
        "y_test": y_test,
        "ensemble": ensemble,
        "components": comps,
        "p_b365_devig": p_b365_devig,
        "model_scores": model_scores,
        "strategies": {
            "Pure Fundamental vs Bet365 (EV>=3%)": pure_vs_b365,
            f"Market-{devig_method.title()} vs MaxBook (EV>={min_ev:.1%}, O<={max_odds:.1f})": sharp_vs_max,
            f"Cross-Mkt (70% 1X2+30% AH/OU) vs MaxBook (EV>={min_ev:.1%})": cross_mkt_vs_max,
            f"O/U 2.5 Market-{devig_method.title()} vs MaxBook (EV>=1%)": ou_vs_max,
            "Joint Multi-Market Portfolio (1X2 + O/U 2.5)": joint_portfolio,
        },
    }


def run_pinnacle_soft_backtest(
    devig_method: DevigMethod = "power",
    min_ev: float = 0.025,
    max_odds: float = 4.00,
    kelly_mult: float = 0.25,
    data_dir=None,
) -> dict[str, object]:
    """Backtest sharp Pinnacle opening/closing probabilities + High-Liq & WF CLV-ML filters vs soft books (2026)."""
    ta = load_tipsaudit(data_dir=data_dir).sort_values("kickoff_utc").reset_index(drop=True)
    y = ta["y"].to_numpy(dtype=int)

    pin_open_odds = ta[["pin_open_home", "pin_open_draw", "pin_open_away"]].to_numpy(dtype=float)
    pin_close_odds = ta[["pin_close_home", "pin_close_draw", "pin_close_away"]].to_numpy(dtype=float)
    soft_odds = ta[["best_soft_home", "best_soft_draw", "best_soft_away"]].to_numpy(dtype=float)

    p_open = devig_batch(pin_open_odds, method=devig_method)
    p_close = devig_batch(pin_close_odds, method=devig_method)

    open_strat = _evaluate_selection_strategy(
        p_open, soft_odds, y, min_ev=min_ev, min_odds=1.25, max_odds=max_odds, kelly_mult=kelly_mult
    )
    close_strat = _evaluate_selection_strategy(
        p_close, soft_odds, y, min_ev=min_ev, min_odds=1.25, max_odds=max_odds, kelly_mult=kelly_mult
    )

    rows = np.arange(len(ta))
    ev_mat = p_open * soft_odds - 1.0
    best_c = np.argmax(ev_mat, axis=1)
    best_ev = ev_mat[rows, best_c]
    odd_sel = soft_odds[rows, best_c]
    p_sel = p_open[rows, best_c]
    p_close_sel = p_close[rows, best_c]
    won = y == best_c
    vig_open = np.sum(1.0 / pin_open_odds, axis=1) - 1.0
    clv_ev = p_close_sel * odd_sel - 1.0
    books_n = ta["books_priced"].fillna(12.0).to_numpy(dtype=float)

    mask = open_strat["mask"]
    clv_pct = float(np.mean(clv_ev[mask]) * 100.0) if np.any(mask) else 0.0

    # High-Liquidity soft-book filter (books >= 12, O <= 3.50, Baker-McHale Kelly shrinkage)
    hl_mask = (best_ev >= min_ev) & (odd_sel >= 1.25) & (odd_sel <= 3.50) & (books_n >= 12.0)
    hl_bm_std = np.maximum(0.012, 0.5 * vig_open)
    pin_open_high_liq = _evaluate_masked_bm_kelly(p_sel, odd_sel, won, hl_mask, prob_std=hl_bm_std, kelly_mult=kelly_mult)
    hl_clv_pct = float(np.mean(clv_ev[hl_mask]) * 100.0) if np.any(hl_mask) else 0.0

    # Strict Causal Walk-Forward CLV Preservation ML Filter (refit every 600 matches after warmup=900)
    clv_df = pd.DataFrame(
        {
            "best_ev": best_ev,
            "odd_sel": odd_sel,
            "p_sel": p_sel,
            "vig_open": vig_open,
            "is_draw": (best_c == 1).astype(float),
            "is_away": (best_c == 2).astype(float),
            "books_n": books_n,
            "margin_avg": ta["market_margin_avg_pct"].fillna(4.5).to_numpy(dtype=float),
            "margin_min": ta["market_margin_min_pct"].fillna(2.5).to_numpy(dtype=float),
            "pin_vs_soft_gap": (odd_sel / pin_open_odds[rows, best_c]) - 1.0,
        }
    )
    clv_pos = (clv_ev > 0.0).astype(int)
    warmup = 900
    p_hold = np.full(len(ta), np.nan)
    for start in range(warmup, len(ta), 600):
        end = min(start + 600, len(ta))
        clv_flt = CLVPreservationFilter(min_train_ev=0.015).fit(clv_df.iloc[:start], clv_pos[:start])
        p_hold[start:end] = clv_flt.predict_hold_proba(clv_df.iloc[start:end])

    wf_clv_mask = (np.arange(len(ta)) >= warmup) & (best_ev >= min_ev) & (odd_sel >= 1.25) & (odd_sel <= 3.50) & (p_hold >= 0.70)
    wf_std = np.maximum(0.012, 0.5 * vig_open + 0.02 * (1.0 - np.nan_to_num(p_hold, nan=0.5)))
    pin_open_wf_clv = _evaluate_masked_bm_kelly(p_sel, odd_sel, won, wf_clv_mask, prob_std=wf_std, kelly_mult=kelly_mult)
    wf_clv_pct = float(np.mean(clv_ev[wf_clv_mask]) * 100.0) if np.any(wf_clv_mask) else 0.0

    return {
        "n_matches": int(len(ta)),
        "pin_open_scores": {
            "log_loss": multiclass_log_loss(p_open, y),
            "rps": ranked_probability_score(p_open, y),
            "ece": classwise_ece(p_open, y),
        },
        "pin_close_scores": {
            "log_loss": multiclass_log_loss(p_close, y),
            "rps": ranked_probability_score(p_close, y),
            "ece": classwise_ece(p_close, y),
        },
        "pin_open_vs_soft": open_strat,
        "pin_close_vs_soft": close_strat,
        "pin_open_high_liq": pin_open_high_liq,
        "pin_open_wf_clv": pin_open_wf_clv,
        "mean_closing_ev_clv_pct": clv_pct,
        "high_liq_clv_pct": hl_clv_pct,
        "wf_clv_ml_pct": wf_clv_pct,
    }
