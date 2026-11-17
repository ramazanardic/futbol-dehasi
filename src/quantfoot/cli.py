"""Command-line interface for QuantFoot backtesting, matchup analysis, and portfolio Kelly."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from quantfoot.data.live_espn import (
    ESPN_CLUB_LEAGUES,
    LiveFixture,
    fetch_club_slate,
    fetch_espn_slate,
    load_international_history,
    sync_club_recent_results,
)
from quantfoot.data.loader import DEFAULT_LEAGUES, LEAGUE_NAMES, load_matches
from quantfoot.data.xg_proxy import BoxScoreXGModel
from quantfoot.evaluation.backtest import run_pinnacle_soft_backtest, run_walk_forward_backtest
from quantfoot.evaluation.reporting import generate_backtest_charts
from quantfoot.markets.devig import DevigMethod, book_overround, devig
from quantfoot.markets.pricing import expected_ah_ev, over_under_probability, price_all_markets
from quantfoot.models.bivariate_poisson import DiagonalBivariatePoisson
from quantfoot.models.dixon_coles import TimeDecayedDixonColes
from quantfoot.models.gap_ratings import WheatcroftGAPRatings
from quantfoot.models.gas_poisson import GASPoissonModel
from quantfoot.models.glicko2 import FootballGlicko2
from quantfoot.models.kalman import KalmanPoissonModel
from quantfoot.models.pyramid import PYRAMID_DIVISIONS
from quantfoot.models.ratings import CausalRatingEngine
from quantfoot.models.weibull_copula import (
    frank_copula_score_matrix,
    weibull_alpha_table,
    weibull_count_pmf,
)
from quantfoot.strategy.kelly import (
    baker_mchale_kelly_fraction,
    kelly_fraction,
    maclean_doubling_before_halving,
    optimize_correlated_kelly,
)
from quantfoot.strategy.value import bayesian_log_odds_blend, evaluate_1x2_value, evaluate_multimarket_value


def _resolve_team_name(name: str, known_teams: list[str]) -> str:
    if name in known_teams:
        return name
    lower_map = {t.lower(): t for t in known_teams}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    matches = difflib.get_close_matches(name, known_teams, n=3, cutoff=0.5)
    if matches:
        return matches[0]
    raise ValueError(f"Unknown team '{name}'. Sample teams in league: {sorted(known_teams)[:12]}")


def _cmd_backtest(args: argparse.Namespace) -> None:
    leagues = args.leagues or DEFAULT_LEAGUES
    print(f"Running walk-forward backtest across leagues: {', '.join(leagues)} ...")
    wf = run_walk_forward_backtest(
        leagues=leagues,
        devig_method=args.devig,
        min_ev=args.min_ev,
        max_odds=args.max_odds,
        kelly_mult=args.kelly_mult,
    )
    pin = run_pinnacle_soft_backtest(
        devig_method=args.devig,
        min_ev=max(args.min_ev, 0.025),
        max_odds=max(args.max_odds, 4.0),
        kelly_mult=args.kelly_mult,
    )

    print(f"\n=== Out-of-Sample Proper Scoring Rules (cal={wf['n_cal']:,}, test={wf['n_test']:,}) ===")
    for name, s in wf["model_scores"].items():
        print(
            f"  {name:40s} | LogLoss={s['log_loss']:.5f} | RPS={s['rps']:.5f} | "
            f"Brier={s['brier']:.5f} | ECE={s['ece']:.5f}"
        )
    ens = wf["ensemble"]
    w_str = ", ".join(f"{n}={w:.3f}" for n, w in zip(ens.SUBMODEL_NAMES, ens.weights_))
    print(f"  V4 OOF Simplex Weights: [{w_str}] | Temperature={ens.temperature:.3f}")

    print("\n=== Club Leagues Betting Strategies (Zero Leakage, Real Odds) ===")
    for name, strat in wf["strategies"].items():
        m = strat["metrics"]
        k = strat["kelly"]
        print(
            f"  {name:58s} | bets={m['bets']:5d} | win={m['win_rate']:.3f} | "
            f"avg_o={m['avg_odds']:.2f} | flat_ROI={m['roi']*100:+6.2f}% (t={m['t_stat']:+5.2f}) | "
            f"Kelly=${k['final_bankroll']:,.2f} (DD={k['max_drawdown_pct']:.1f}%)"
        )

    print(f"\n=== 2026 Pinnacle Sharp vs Best Soft Book (n={pin['n_matches']:,}) ===")
    po = pin["pin_open_vs_soft"]
    pc = pin["pin_close_vs_soft"]
    phl = pin["pin_open_high_liq"]
    pwf = pin["pin_open_wf_clv"]
    for lbl, st, clv_val in (
        ("Pin Open vs BestSoft (Base)", po, pin["mean_closing_ev_clv_pct"]),
        ("Pin Open High-Liq (B>=12, O<=3.5)", phl, pin["high_liq_clv_pct"]),
        ("Pin Open WF CLV-ML (P>=0.70, O<=3.5)", pwf, pin["wf_clv_ml_pct"]),
        ("Pin Close vs BestSoft", pc, None),
    ):
        m, k = st["metrics"], st["kelly"]
        clv_txt = f" | CLV={clv_val:+.2f}%" if clv_val is not None else ""
        print(
            f"  {lbl:37s} | bets={m['bets']:5d} | win={m['win_rate']:.3f} | avg_o={m['avg_odds']:.2f} | "
            f"flat_ROI={m['roi']*100:+6.2f}% (t={m['t_stat']:+5.2f}, p={m['p_value']:.4f}){clv_txt} | "
            f"Kelly=${k['final_bankroll']:,.2f} (DD={k['max_drawdown_pct']:.1f}%)"
        )

    report_dir = Path(args.report_dir)
    charts = generate_backtest_charts(wf, pin, report_dir)
    summary = {
        "leagues": leagues,
        "n_cal": wf["n_cal"],
        "n_test": wf["n_test"],
        "ensemble_weights": {n: float(w) for n, w in zip(ens.SUBMODEL_NAMES, ens.weights_)},
        "ensemble_temperature": float(ens.temperature),
        "model_scores": wf["model_scores"],
        "strategies": {
            k: {"metrics": v["metrics"], "kelly_final": v["kelly"]["final_bankroll"], "max_dd_pct": v["kelly"]["max_drawdown_pct"]}
            for k, v in wf["strategies"].items()
        },
        "pinnacle_2026": {
            "n_matches": pin["n_matches"],
            "mean_clv_pct": pin["mean_closing_ev_clv_pct"],
            "high_liq_clv_pct": pin["high_liq_clv_pct"],
            "wf_clv_ml_pct": pin["wf_clv_ml_pct"],
            "pin_open_vs_soft": {
                "metrics": po["metrics"],
                "kelly_final": po["kelly"]["final_bankroll"],
                "max_dd_pct": po["kelly"]["max_drawdown_pct"],
            },
            "pin_open_high_liq": {
                "metrics": phl["metrics"],
                "kelly_final": phl["kelly"]["final_bankroll"],
                "max_dd_pct": phl["kelly"]["max_drawdown_pct"],
            },
            "pin_open_wf_clv": {
                "metrics": pwf["metrics"],
                "kelly_final": pwf["kelly"]["final_bankroll"],
                "max_dd_pct": pwf["kelly"]["max_drawdown_pct"],
            },
            "pin_close_vs_soft": {
                "metrics": pc["metrics"],
                "kelly_final": pc["kelly"]["final_bankroll"],
                "max_dd_pct": pc["kelly"]["max_drawdown_pct"],
            },
        },
        "charts": [str(c) for c in charts],
    }
    summary_path = report_dir / "backtest_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved summary and {len(charts)} charts to: {report_dir.resolve()}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    df = load_matches(leagues=[args.league], min_date="2014-01-01", require_odds=False)
    if len(df) < 150:
        raise ValueError(f"Insufficient matches found for league '{args.league}'.")
    if not args.no_sync and args.league in ESPN_CLUB_LEAGUES:
        df = sync_club_recent_results(df, divisions=[args.league])

    xg_model = BoxScoreXGModel().fit(df.iloc[: max(len(df) // 2, 100)])
    h_xg, a_xg = xg_model.transform(df)
    df["h_xg_proxy"] = h_xg
    df["a_xg_proxy"] = a_xg

    teams = sorted(set(df["HomeTeam"]).union(set(df["AwayTeam"])))
    home = _resolve_team_name(args.home, teams)
    away = _resolve_team_name(args.away, teams)

    rating = CausalRatingEngine()
    glicko = FootballGlicko2()
    kalman = KalmanPoissonModel()
    gas = GASPoissonModel()
    gap_sot = WheatcroftGAPRatings(lam=0.06, phi1=0.70, phi2=0.70, base_stat=9.0)
    for _, row in df.iterrows():
        hg, ag = float(row["FTHome"]), float(row["FTAway"])
        hxg, axg = float(row["h_xg_proxy"]), float(row["a_xg_proxy"])
        hsot = float(row["HomeTarget"]) if pd.notna(row["HomeTarget"]) else 4.2
        asot = float(row["AwayTarget"]) if pd.notna(row["AwayTarget"]) else 4.2
        hsh = float(row["HomeShots"]) if pd.notna(row["HomeShots"]) else 12.0
        ash = float(row["AwayShots"]) if pd.notna(row["AwayShots"]) else 12.0
        gas.update(row["HomeTeam"], row["AwayTeam"], hg, ag, hxg=hxg, axg=axg, match_date=row["MatchDate"])
        kalman.update(row["HomeTeam"], row["AwayTeam"], hg, ag, hxg=hxg, axg=axg, hsot=hsot, asot=asot, match_date=row["MatchDate"], div=args.league)
        glicko.update(row["HomeTeam"], row["AwayTeam"], hg, ag, row["MatchDate"], div=args.league)
        gap_sot.update(row["HomeTeam"], row["AwayTeam"], hsot, asot, div=args.league)
        rating.update(
            row["HomeTeam"],
            row["AwayTeam"],
            hg,
            ag,
            hxg,
            axg,
            hsot,
            asot,
            hsh,
            ash,
            row["MatchDate"],
            div=args.league,
        )

    recent = df.tail(min(len(df), 900)).copy()
    max_date = recent["MatchDate"].max()
    days_ago = (max_date - recent["MatchDate"]).dt.days.to_numpy(dtype=float)

    dc_g = TimeDecayedDixonColes(xi=0.0020, l2_reg=0.06).fit(
        recent["HomeTeam"], recent["AwayTeam"], recent["FTHome"], recent["FTAway"], days_ago,
        home_xg=recent["h_xg_proxy"], away_xg=recent["a_xg_proxy"], xg_weight=0.25,
    )
    dibp = DiagonalBivariatePoisson(xi=0.0020, l2_reg=0.08).fit(
        recent["HomeTeam"], recent["AwayTeam"], recent["FTHome"], recent["FTAway"], days_ago
    )

    mat_g = dc_g.score_matrix(home, away)
    mat_kal = kalman.score_matrix(home, away, match_date=max_date, div=args.league)
    mat_gas = gas.score_matrix(home, away)
    mat_b = dibp.score_matrix(home, away)
    lam_g, mu_g = dc_g.expected_goals(home, away)
    alpha_w = weibull_alpha_table(1.08, max_n=8)
    mat_w = frank_copula_score_matrix(
        weibull_count_pmf(lam_g, 1.08, max_n=8, alpha_table=alpha_w),
        weibull_count_pmf(mu_g, 1.08, max_n=8, alpha_table=alpha_w),
        theta=-0.20,
    )
    mat_blend = 0.28 * mat_g + 0.28 * mat_kal + 0.20 * mat_gas + 0.12 * mat_b + 0.12 * mat_w
    mat_blend /= np.sum(mat_blend)

    priced = price_all_markets(mat_blend)
    exp_sot_h, exp_sot_a = gap_sot.expected_stats(home, away, div=args.league)
    rh = rating.team_rolling(home, 10)
    ra = rating.team_rolling(away, 10)
    e_h, e_a = rating.get_elo(home, div=args.league), rating.get_elo(away, div=args.league)
    gl_h, rdh = glicko.get_rating(home, max_date, div=args.league)
    gl_a, rda = glicko.get_rating(away, max_date, div=args.league)
    pi_hh, pi_ha = rating.get_pi(home)
    pi_ah, pi_aa = rating.get_pi(away)

    print(f"\n=== QuantFoot v4 Match Analysis: {home} vs {away} [{LEAGUE_NAMES.get(args.league, args.league)}] ===")
    print(f"Data through: {max_date.date()} ({len(recent)} weighted recent league matches)")
    print(f"  {home:18s} | Elo={e_h:.0f} | Glicko2={gl_h:.0f}+/-{rdh:.0f} | Pi(H/A)=({pi_hh:+.2f}/{pi_ha:+.2f}) | L10 xGF={rh['xgf']:.2f} xGA={rh['xga']:.2f} | Luck={rh['gf']-rh['xgf']:+.2f}")
    print(f"  {away:18s} | Elo={e_a:.0f} | Glicko2={gl_a:.0f}+/-{rda:.0f} | Pi(H/A)=({pi_ah:+.2f}/{pi_aa:+.2f}) | L10 xGF={ra['xgf']:.2f} xGA={ra['xga']:.2f} | Luck={ra['gf']-ra['xgf']:+.2f}")
    print(f"  Expected Goals: {home} {priced['expected_home_goals']:.2f} - {priced['expected_away_goals']:.2f} {away} | Wheatcroft GAP SOT={exp_sot_h:.1f}-{exp_sot_a:.1f} (DC rho={dc_g.rho:+.3f}, Kal HFA={kalman._env(args.league)[1]:+.2f}, DIBP lam3={dibp.lambda3:.3f})")

    p1 = priced["1x2"]
    print(f"\nFundamental Fair 1X2:  1={p1['H']:.1%} ({1/p1['H']:.2f}) | X={p1['D']:.1%} ({1/p1['D']:.2f}) | 2={p1['A']:.1%} ({1/p1['A']:.2f})")
    dc = priced["double_chance"]
    print(f"Double Chance:         1X={dc['1X']:.1%} ({1/dc['1X']:.2f}) | X2={dc['X2']:.1%} ({1/dc['X2']:.2f}) | 12={dc['12']:.1%} ({1/dc['12']:.2f})")
    ou = priced["over_under"]
    print(f"Totals & BTTS:         O2.5={ou['over_2.5']:.1%} ({1/ou['over_2.5']:.2f}) | U2.5={ou['under_2.5']:.1%} ({1/ou['under_2.5']:.2f}) | BTTS Yes={priced['btts']['yes']:.1%} ({1/priced['btts']['yes']:.2f})")
    top_sc = ", ".join(f"{s['score']} ({s['prob']:.1%})" for s in priced["top_exact_scores"])
    print(f"Top Exact Scores:      {top_sc}")

    fund_1x2 = np.array([p1["H"], p1["D"], p1["A"]], dtype=float)
    override_1x2 = None
    if args.sharp_odds is not None:
        sharp_res = devig(args.sharp_odds, method=args.devig)
        print(f"\nSharp Market ({args.devig}, vig={sharp_res.overround*100:.2f}%): 1={sharp_res.probabilities[0]:.1%} | X={sharp_res.probabilities[1]:.1%} | 2={sharp_res.probabilities[2]:.1%}")
        if args.fund_weight > 0.0:
            override_1x2 = bayesian_log_odds_blend(sharp_res.probabilities, fund_1x2, fundamental_weight=args.fund_weight)
        else:
            override_1x2 = sharp_res.probabilities

    if args.odds is not None:
        print(f"Offered 1X2 Book Vig:  {book_overround(args.odds)*100:.2f}%")

    opps = evaluate_multimarket_value(
        mat_blend,
        offered_1x2=args.odds,
        sharp_1x2=args.sharp_odds if args.fund_weight == 0.0 else None,
        offered_ou25=args.ou25,
        offered_ah=tuple(args.ah) if args.ah is not None else None,
        devig_method=args.devig,
        min_ev=args.min_ev,
        max_odds=args.max_odds,
        kelly_mult=args.kelly_mult,
        fundamental_1x2_override=override_1x2,
    )

    print("\n=== +EV Betting Signals ===")
    if not opps:
        print("  No positive expected-value opportunities exceed thresholds.")
    else:
        mtz = maclean_doubling_before_halving(args.kelly_mult)
        for opp in opps:
            stake_amt = args.bankroll * opp.kelly_stake
            print(
                f"  [{opp.market:14s}] {opp.selection:18s} | P={opp.model_prob:.1%} | Fair={opp.fair_odds:.2f} | "
                f"Offered={opp.offered_odds:.2f} | EV={opp.expected_value*100:+5.2f}% | "
                f"Stake={opp.kelly_stake*100:.2f}% (${stake_amt:,.2f})"
            )
        print(
            f"  Risk Profile ({args.kelly_mult:.2f}x Kelly): RelGrowth={mtz['relative_growth_rate']:.1%}, "
            f"P(2x before 0.5x)={mtz['prob_double_before_half']:.2%}"
        )


def _cmd_portfolio(args: argparse.Namespace) -> None:
    payload = json.loads(Path(args.bets_json).read_text(encoding="utf-8"))
    probs = np.array([b["prob"] for b in payload["bets"]], dtype=float)
    odds = np.array([b["odds"] for b in payload["bets"]], dtype=float)
    corr = np.array(payload["correlation_matrix"], dtype=float) if "correlation_matrix" in payload else None

    res = optimize_correlated_kelly(
        probs=probs,
        odds=odds,
        corr_matrix=corr,
        multiplier=args.kelly_mult,
        max_per_bet=args.max_stake,
        max_total=args.max_total,
    )
    print("\n=== Simultaneous Correlated Kelly Portfolio Allocation ===")
    for bet, f_full, f_frac in zip(payload["bets"], res["full_kelly"], res["fractions"]):
        print(
            f"  {bet.get('label', 'Bet'):28s} | p={bet['prob']:.3f} | odds={bet['odds']:.2f} | "
            f"EV={(bet['prob']*bet['odds']-1)*100:+5.2f}% | Full={f_full*100:5.2f}% | "
            f"Allocated={f_frac*100:5.2f}% (${args.bankroll * f_frac:,.2f})"
        )
    print(f"Total Exposure: {np.sum(res['fractions'])*100:.2f}% | Expected Log Growth: {res['expected_log_growth']:.6f}")


def _intl_comp_weight(tournament: str) -> float:
    t = str(tournament).lower()
    if "friendly" in t:
        return 0.45
    if any(k in t for k in ("world cup", "euro", "copa américa", "copa america", "african cup")):
        return 1.25
    return 1.0


def _score_live_fixture(
    fx: LiveFixture,
    sub_mats: tuple[np.ndarray, ...],
    weights: tuple[float, ...],
    model_banner: str,
    args: argparse.Namespace,
    portfolio_candidates: list[dict],
) -> None:
    """Evaluate steam, Bayesian log-odds blend, multi-market +EV, and Baker-McHale Kelly on a live fixture."""
    mat = sum(w * m for w, m in zip(weights, sub_mats))
    mat /= np.sum(mat)

    sub_1x2 = np.vstack([
        [float(np.sum(np.tril(m, -1))), float(np.sum(np.diag(m))), float(np.sum(np.triu(m, 1)))]
        for m in sub_mats
    ])
    std_1x2 = np.std(sub_1x2, axis=0)
    priced = price_all_markets(mat)
    p1 = priced["1x2"]
    fund_1x2 = np.array([p1["H"], p1["D"], p1["A"]], dtype=float)

    print(
        f"  {model_banner}: xG={priced['expected_home_goals']:.2f}-{priced['expected_away_goals']:.2f} | "
        f"Fair 1X2=({fund_1x2[0]:.1%}, {fund_1x2[1]:.1%}, {fund_1x2[2]:.1%}) | "
        f"Fair O2.5={priced['over_under']['over_2.5']:.1%} | BTTS={priced['btts']['yes']:.1%}"
    )

    match_opps = []
    steam_1x2 = None
    if fx.open_1x2 and fx.cur_1x2:
        p_open_1x2 = devig(list(fx.open_1x2), method=args.devig).probabilities
        p_cur_1x2 = devig(list(fx.cur_1x2), method=args.devig).probabilities
        steam_1x2 = p_cur_1x2 - p_open_1x2

    if fx.cur_1x2:
        p_cur = devig(list(fx.cur_1x2), method=args.devig).probabilities
        p_post = bayesian_log_odds_blend(p_cur, fund_1x2, fundamental_weight=args.fund_weight)
        opp = evaluate_1x2_value(
            p_post,
            list(fx.cur_1x2),
            min_ev=args.min_ev,
            max_odds=args.max_odds,
            kelly_mult=args.kelly_mult,
        )
        if opp is not None:
            sel_idx = {"Home (1)": 0, "Draw (X)": 1, "Away (2)": 2}[opp.selection]
            warn = ""
            if steam_1x2 is not None and steam_1x2[sel_idx] <= -0.05:
                warn = f" [STEAM WARNING: {steam_1x2[sel_idx]:+.1%} against]"
            p_std = float(std_1x2[sel_idx] * args.fund_weight + 0.015)
            match_opps.append((opp.market, opp.selection + warn, opp.model_prob, opp.offered_odds, opp.expected_value, p_std, bool(warn)))

    if fx.ou_line is not None and fx.ou_odds is not None:
        p_over, p_under = over_under_probability(mat, fx.ou_line)
        sub_ou = np.array([over_under_probability(m, fx.ou_line)[0] for m in sub_mats])
        ou_std = float(np.std(sub_ou) * args.fund_weight + 0.015)
        p_mkt_ou = devig(list(fx.ou_odds), method=args.devig).probabilities
        p_ou_post = bayesian_log_odds_blend(p_mkt_ou, np.array([p_over, p_under]), fundamental_weight=args.fund_weight)
        for label, p_val, o_val in (
            (f"Over {fx.ou_line}", float(p_ou_post[0]), fx.ou_odds[0]),
            (f"Under {fx.ou_line}", float(p_ou_post[1]), fx.ou_odds[1]),
        ):
            ev = p_val * o_val - 1.0
            if 1.25 <= o_val <= args.max_odds and ev >= args.min_ev:
                match_opps.append((f"O/U {fx.ou_line}", label, p_val, o_val, float(ev), ou_std, False))

    if fx.ah_line is not None and fx.ah_odds is not None:
        p_mkt_ah = devig(list(fx.ah_odds), method=args.devig).probabilities
        for idx_side, is_home, label, o_val in (
            (0, True, f"Home AH ({fx.ah_line:+.2f})", fx.ah_odds[0]),
            (1, False, f"Away AH ({-fx.ah_line:+.2f})", fx.ah_odds[1]),
        ):
            if 1.25 <= o_val <= args.max_odds:
                ev_mkt = float(p_mkt_ah[idx_side] * o_val - 1.0)
                ev_fund = expected_ah_ev(mat, fx.ah_line, o_val, is_home=is_home)
                ev = (1.0 - args.fund_weight) * ev_mkt + args.fund_weight * ev_fund
                if ev >= args.min_ev:
                    p_eff = (ev + 1.0) / o_val
                    steam_warn = steam_1x2 is not None and steam_1x2[0 if is_home else 2] <= -0.05
                    lbl = label + (" [STEAM WARNING]" if steam_warn else "")
                    p_std = float(std_1x2[0 if is_home else 2] * args.fund_weight + 0.015)
                    match_opps.append(("Spread/AH", lbl, float(p_eff), o_val, float(ev), p_std, steam_warn))

    if not match_opps:
        print("  No +EV signals above threshold.")
    else:
        match_key = f"{fx.home_team} vs {fx.away_team}"
        for mkt, sel, p_val, o_val, ev, p_std, has_warn in match_opps:
            stake = baker_mchale_kelly_fraction(p_val, o_val, prob_std=p_std, multiplier=args.kelly_mult, max_stake=0.03)
            print(
                f"  +EV [{mkt:9s}] {sel:34s} | P={p_val:.1%} (±{p_std:.1%}) | "
                f"Odds={o_val:.3f} | EV={ev*100:+5.2f}% | BM-Kelly={stake*100:.2f}%"
            )
            if not has_warn:
                portfolio_candidates.append(
                    {"match": match_key, "label": f"{match_key} | {sel}", "prob": p_val, "odds": o_val, "ev": ev}
                )


def _run_intl_slate(args: argparse.Namespace, dates: list[str], today_utc: dt.date, portfolio_candidates: list[dict]) -> None:
    print(f"Syncing international match history through {today_utc.isoformat()} ...")
    hist = load_international_history(sync_through_date=today_utc.isoformat(), min_date="2016-01-01")
    hist["is_neutral"] = hist["neutral"].fillna(False).astype(bool) if "neutral" in hist.columns else False
    hist["comp_w"] = hist["tournament"].map(_intl_comp_weight) if "tournament" in hist.columns else 1.0
    known_teams = set(hist["home_team"]).union(set(hist["away_team"]))

    rating = CausalRatingEngine()
    glicko = FootballGlicko2(offseason_days=60, offseason_reversion=0.90)
    kalman = KalmanPoissonModel(mu0=0.10, home_adv=0.22, offseason_days=60, reversion=0.85)
    gas = GASPoissonModel(mu0=0.10, home_adv=0.22, persist=0.985, k_att=0.06, k_def=0.06, offseason_days=60, offseason_reversion=0.82)
    for _, row in hist.iterrows():
        hg, ag = float(row["home_score"]), float(row["away_score"])
        is_neut = bool(row["is_neutral"])
        cw = float(row["comp_w"])
        gas.update(row["home_team"], row["away_team"], min(hg, 5.0), min(ag, 5.0), neutral=is_neut, match_date=row["date"], comp_weight=cw)
        kalman.update(row["home_team"], row["away_team"], min(hg, 5.0), min(ag, 5.0), match_date=row["date"], neutral=is_neut, comp_weight=cw)
        glicko.update(row["home_team"], row["away_team"], min(hg, 5.0), min(ag, 5.0), row["date"], neutral=is_neut)
        rating.update(row["home_team"], row["away_team"], hg, ag, hg, ag, 4.0, 4.0, 12.0, 12.0, row["date"], neutral=is_neut)

    recent = hist[hist["date"] >= (hist["date"].max() - pd.Timedelta(days=900))].copy()
    max_d = recent["date"].max()
    days_ago = (max_d - recent["date"]).dt.days.to_numpy(dtype=float)

    dc = TimeDecayedDixonColes(xi=0.0018, l2_reg=0.15).fit(
        recent["home_team"], recent["away_team"], recent["home_score"], recent["away_score"], days_ago,
        neutral_venue=recent["is_neutral"], sample_weights=recent["comp_w"], goal_cap=5.0,
    )
    dibp = DiagonalBivariatePoisson(xi=0.0018, l2_reg=0.18).fit(
        recent["home_team"], recent["away_team"], np.minimum(recent["home_score"], 5.0), np.minimum(recent["away_score"], 5.0), days_ago,
    )
    alpha_w = weibull_alpha_table(1.06, max_n=8)

    all_fixtures = []
    for d in dates:
        all_fixtures.extend(fetch_espn_slate(d))
    scheduled = [f for f in all_fixtures if f.status == "STATUS_SCHEDULED" and (f.cur_1x2 or f.ou_odds or f.ah_odds)]
    print(f"Loaded {len(hist):,} international matches (latest: {max_d.date()}); {len(scheduled)} upcoming with odds.\n")

    for fx in scheduled:
        kickoff_tsi = dt.datetime.fromisoformat(fx.date_utc.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=3)))
        print(f"--- {kickoff_tsi.strftime('%Y-%m-%d %H:%M TSI')} | {fx.home_team} vs {fx.away_team} [{fx.competition}] ---")
        if fx.open_1x2 and fx.cur_1x2:
            p_open = devig(list(fx.open_1x2), method=args.devig).probabilities
            p_cur = devig(list(fx.cur_1x2), method=args.devig).probabilities
            steam = p_cur - p_open
            print(f"  Market 1X2: Open={fx.open_1x2} -> Cur={fx.cur_1x2} | Power Prob=({p_cur[0]:.1%}, {p_cur[1]:.1%}, {p_cur[2]:.1%}) | Steam=({steam[0]:+.1%}, {steam[1]:+.1%}, {steam[2]:+.1%})")

        if fx.home_canonical not in known_teams or fx.away_canonical not in known_teams:
            print("  [Fixture outside senior international history — scored in Club/UCL slate when applicable]")
            continue

        mat_dc = dc.score_matrix(fx.home_canonical, fx.away_canonical)
        mat_kal = kalman.score_matrix(fx.home_canonical, fx.away_canonical, match_date=max_d)
        mat_gas = gas.score_matrix(fx.home_canonical, fx.away_canonical)
        mat_dibp = dibp.score_matrix(fx.home_canonical, fx.away_canonical)
        lam_dc, mu_dc = dc.expected_goals(fx.home_canonical, fx.away_canonical)
        mat_wc = frank_copula_score_matrix(
            weibull_count_pmf(lam_dc, 1.06, max_n=8, alpha_table=alpha_w),
            weibull_count_pmf(mu_dc, 1.06, max_n=8, alpha_table=alpha_w),
            theta=-0.15,
        )
        eh, ea = rating.get_elo(fx.home_canonical), rating.get_elo(fx.away_canonical)
        glh, rdh = glicko.get_rating(fx.home_canonical, max_d)
        gla, rda = glicko.get_rating(fx.away_canonical, max_d)
        banner = f"Intl v4 (Elo {eh:.0f}/{ea:.0f}, Glicko {glh:.0f}+/-{rdh:.0f}/{gla:.0f}+/-{rda:.0f})"
        _score_live_fixture(fx, (mat_dc, mat_kal, mat_gas, mat_dibp, mat_wc), (0.30, 0.25, 0.25, 0.10, 0.10), banner, args, portfolio_candidates)


def _run_club_slate(args: argparse.Namespace, portfolio_candidates: list[dict]) -> None:
    print("Loading Pyramid club matches & syncing 2026-27 ESPN club results ...")
    df = load_matches(leagues=list(PYRAMID_DIVISIONS), min_date="2018-01-01", require_odds=False)
    if not args.no_sync:
        df = sync_club_recent_results(df, divisions=DEFAULT_LEAGUES)
    df = df.sort_values(["MatchDate", "Division"]).reset_index(drop=True)
    known_teams = set(df["HomeTeam"]).union(set(df["AwayTeam"]))

    xg_model = BoxScoreXGModel().fit(df[df["MatchDate"] < "2024-01-01"])
    hx, ax = xg_model.transform(df)
    df["h_xg_proxy"], df["a_xg_proxy"] = hx, ax

    rating = CausalRatingEngine()
    glicko = FootballGlicko2()
    kalman = KalmanPoissonModel()
    for r in df.itertuples(index=False):
        div = str(r.Division)
        hg, ag = float(r.FTHome), float(r.FTAway)
        hxg, axg = float(r.h_xg_proxy), float(r.a_xg_proxy)
        hsot = float(r.HomeTarget) if hasattr(r, "HomeTarget") and pd.notna(r.HomeTarget) else 4.2
        asot = float(r.AwayTarget) if hasattr(r, "AwayTarget") and pd.notna(r.AwayTarget) else 4.2
        hsh = float(r.HomeShots) if hasattr(r, "HomeShots") and pd.notna(r.HomeShots) else 12.0
        ash = float(r.AwayShots) if hasattr(r, "AwayShots") and pd.notna(r.AwayShots) else 12.0
        kalman.update(r.HomeTeam, r.AwayTeam, hg, ag, hxg=hxg, axg=axg, hsot=hsot, asot=asot, match_date=r.MatchDate, div=div)
        glicko.update(r.HomeTeam, r.AwayTeam, hg, ag, r.MatchDate, div=div)
        rating.update(r.HomeTeam, r.AwayTeam, hg, ag, hxg, axg, hsot, asot, hsh, ash, r.MatchDate, div=div)

    dc_by_div: dict[str, TimeDecayedDixonColes] = {}
    for div_code in DEFAULT_LEAGUES:
        sub = df[df["Division"] == div_code].tail(900)
        if len(sub) >= 120:
            md = sub["MatchDate"].max()
            days_ago = (md - sub["MatchDate"]).dt.days.to_numpy(dtype=float)
            dc_by_div[div_code] = TimeDecayedDixonColes(xi=0.0020, l2_reg=0.06).fit(
                sub["HomeTeam"], sub["AwayTeam"], sub["FTHome"], sub["FTAway"], days_ago,
                home_xg=sub["h_xg_proxy"], away_xg=sub["a_xg_proxy"], xg_weight=0.25,
            )

    max_d = df["MatchDate"].max()
    alpha_w = weibull_alpha_table(1.08, max_n=8)
    club_fixtures = [f for f in fetch_club_slate(known_teams=known_teams) if f.status == "STATUS_SCHEDULED" and (f.cur_1x2 or f.ou_odds or f.ah_odds)]
    print(f"Synced {len(df):,} club matches (latest: {max_d.date()}); found {len(club_fixtures)} upcoming club/UCL fixtures with odds.\n")

    for fx in club_fixtures:
        kickoff_tsi = dt.datetime.fromisoformat(fx.date_utc.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=3)))
        print(f"--- {kickoff_tsi.strftime('%Y-%m-%d %H:%M TSI')} | {fx.home_team} vs {fx.away_team} [{fx.division or fx.competition}] ---")
        if fx.open_1x2 and fx.cur_1x2:
            p_open = devig(list(fx.open_1x2), method=args.devig).probabilities
            p_cur = devig(list(fx.cur_1x2), method=args.devig).probabilities
            steam = p_cur - p_open
            print(f"  Market 1X2: Open={fx.open_1x2} -> Cur={fx.cur_1x2} | Power Prob=({p_cur[0]:.1%}, {p_cur[1]:.1%}, {p_cur[2]:.1%}) | Steam=({steam[0]:+.1%}, {steam[1]:+.1%}, {steam[2]:+.1%})")

        if fx.home_canonical not in known_teams or fx.away_canonical not in known_teams:
            print(f"  [Team outside synced club history: '{fx.home_canonical}' vs '{fx.away_canonical}' — market odds only]")
            continue

        div_for_model = fx.division if fx.division in dc_by_div else None
        mat_kal = kalman.score_matrix(fx.home_canonical, fx.away_canonical, match_date=max_d, div=div_for_model)
        lam_k, mu_k = kalman.expected_goals(fx.home_canonical, fx.away_canonical, match_date=max_d, div=div_for_model)
        mat_wc = frank_copula_score_matrix(
            weibull_count_pmf(lam_k, 1.08, max_n=8, alpha_table=alpha_w),
            weibull_count_pmf(mu_k, 1.08, max_n=8, alpha_table=alpha_w),
            theta=-0.18,
        )
        if div_for_model is not None:
            mat_dc = dc_by_div[div_for_model].score_matrix(fx.home_canonical, fx.away_canonical)
            sub_mats: tuple[np.ndarray, ...] = (mat_kal, mat_dc, mat_wc)
            wts: tuple[float, ...] = (0.45, 0.35, 0.20)
        else:
            sub_mats = (mat_kal, mat_wc)
            wts = (0.70, 0.30)

        eh = rating.get_elo(fx.home_canonical, div=div_for_model)
        ea = rating.get_elo(fx.away_canonical, div=div_for_model)
        glh, rdh = glicko.get_rating(fx.home_canonical, max_d, div=div_for_model)
        gla, rda = glicko.get_rating(fx.away_canonical, max_d, div=div_for_model)
        banner = f"Club v4 ({fx.home_canonical} vs {fx.away_canonical} | Elo {eh:.0f}/{ea:.0f}, Glicko {glh:.0f}+/-{rdh:.0f}/{gla:.0f}+/-{rda:.0f})"
        _score_live_fixture(fx, sub_mats, wts, banner, args, portfolio_candidates)


def _cmd_slate(args: argparse.Namespace) -> None:
    today_utc = dt.datetime.now(dt.timezone.utc).date()
    dates = args.dates or [today_utc.strftime("%Y%m%d"), (today_utc + dt.timedelta(days=1)).strftime("%Y%m%d")]
    portfolio_candidates: list[dict] = []

    if args.mode in ("all", "intl"):
        _run_intl_slate(args, dates, today_utc, portfolio_candidates)
    if args.mode in ("all", "clubs"):
        _run_club_slate(args, portfolio_candidates)

    if portfolio_candidates:
        # Sort by EV and run Simultaneous Correlated Kelly on top candidates (up to 12 bets)
        top = sorted(portfolio_candidates, key=lambda x: x["ev"], reverse=True)[:12]
        n = len(top)
        corr = np.eye(n, dtype=float)
        for i in range(n):
            for j in range(i + 1, n):
                if top[i]["match"] == top[j]["match"]:
                    corr[i, j] = corr[j, i] = 0.25
        res = optimize_correlated_kelly(
            probs=[x["prob"] for x in top],
            odds=[x["odds"] for x in top],
            corr_matrix=corr,
            multiplier=args.kelly_mult,
            max_per_bet=0.03,
            max_total=0.15,
        )
        print("\n=== Slate Correlated Fractional Kelly Portfolio ===")
        for item, f_frac in zip(top, res["fractions"]):
            if f_frac > 1e-4:
                print(
                    f"  {item['label']:46s} | Odds={item['odds']:.3f} | EV={item['ev']*100:+5.2f}% | "
                    f"Stake={f_frac*100:5.2f}% (${args.bankroll * f_frac:,.2f})"
                )
        print(f"Total Portfolio Exposure: {np.sum(res['fractions'])*100:.2f}% (${args.bankroll * np.sum(res['fractions']):,.2f})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="quantfoot", description="Quantitative Football Betting Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bt = sub.add_parser("backtest", help="Run zero-leakage walk-forward backtest and generate charts")
    p_bt.add_argument("--leagues", nargs="+", default=None, help="League codes (e.g. E0 SP1 D1 I1 F1 T1)")
    p_bt.add_argument("--devig", choices=["power", "shin", "odds_ratio", "multiplicative"], default="power")
    p_bt.add_argument("--min-ev", type=float, default=0.015)
    p_bt.add_argument("--max-odds", type=float, default=3.50)
    p_bt.add_argument("--kelly-mult", type=float, default=0.25)
    p_bt.add_argument("--report-dir", default="reports")
    p_bt.set_defaults(func=_cmd_backtest)

    p_an = sub.add_parser("analyze", help="Analyze a matchup and size +EV bets")
    p_an.add_argument("--league", default="T1", help="League division code (e.g. T1, E0, SP1, D1, I1, F1)")
    p_an.add_argument("--home", required=True, help="Home team name")
    p_an.add_argument("--away", required=True, help="Away team name")
    p_an.add_argument("--odds", nargs=3, type=float, default=None, metavar=("H", "D", "A"), help="Offered 1X2 odds")
    p_an.add_argument("--sharp-odds", nargs=3, type=float, default=None, metavar=("H", "D", "A"), help="Sharp reference 1X2 odds")
    p_an.add_argument("--ou25", nargs=2, type=float, default=None, metavar=("OVER", "UNDER"), help="Offered O/U 2.5 odds")
    p_an.add_argument("--ah", nargs=3, type=float, default=None, metavar=("LINE", "HOME", "AWAY"), help="Home AH line and odds")
    p_an.add_argument("--devig", choices=["power", "shin", "odds_ratio", "multiplicative"], default="power")
    p_an.add_argument("--fund-weight", type=float, default=0.0, help="Bayesian fundamental log-odds weight when sharp odds given")
    p_an.add_argument("--min-ev", type=float, default=0.02)
    p_an.add_argument("--max-odds", type=float, default=3.50)
    p_an.add_argument("--kelly-mult", type=float, default=0.25)
    p_an.add_argument("--bankroll", type=float, default=1000.0)
    p_an.add_argument("--no-sync", action="store_true", help="Skip live ESPN 2026-27 result sync")
    p_an.set_defaults(func=_cmd_analyze)

    p_pf = sub.add_parser("portfolio", help="Optimize simultaneous correlated Kelly stakes from JSON")
    p_pf.add_argument("--bets-json", required=True, help="Path to JSON file with bets and correlation_matrix")
    p_pf.add_argument("--kelly-mult", type=float, default=0.25)
    p_pf.add_argument("--max-stake", type=float, default=0.03)
    p_pf.add_argument("--max-total", type=float, default=0.15)
    p_pf.add_argument("--bankroll", type=float, default=1000.0)
    p_pf.set_defaults(func=_cmd_portfolio)

    p_sl = sub.add_parser("slate", help="Research live ESPN fixtures/odds across Intl, Top European Clubs & UCL")
    p_sl.add_argument("--dates", nargs="+", default=None, help="YYYYMMDD dates (default: today and tomorrow UTC)")
    p_sl.add_argument("--mode", choices=["all", "clubs", "intl"], default="all", help="Which live universe to scan")
    p_sl.add_argument("--no-sync", action="store_true", help="Skip live ESPN 2026-27 club result sync")
    p_sl.add_argument("--devig", choices=["power", "shin", "odds_ratio", "multiplicative"], default="power")
    p_sl.add_argument("--fund-weight", type=float, default=0.25, help="Bayesian fundamental log-odds weight [0..1]")
    p_sl.add_argument("--min-ev", type=float, default=0.02)
    p_sl.add_argument("--max-odds", type=float, default=3.50)
    p_sl.add_argument("--kelly-mult", type=float, default=0.25)
    p_sl.add_argument("--bankroll", type=float, default=1000.0)
    p_sl.set_defaults(func=_cmd_slate)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
