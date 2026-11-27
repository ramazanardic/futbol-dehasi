"""Comprehensive tests for production pipeline wiring, bug fixes, and quantitative upgrades."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_global_odds as FGO  # noqa: E402
import gunluk_tahmin as GT  # noqa: E402
import nesine_global as NG  # noqa: E402
from quantfoot.coupons.system_builder import SystemLeg, build_capital_shield_plan  # noqa: E402
from quantfoot.data import live_scan as LS  # noqa: E402
from quantfoot.evaluation.clv_ledger import record_daily_picks  # noqa: E402
from quantfoot.evaluation.self_improve import render_markdown, run_self_audit  # noqa: E402
from quantfoot.markets import league_halves as LH  # noqa: E402
from quantfoot.markets.market_diagnosis import diagnose_selection, parse_directional_steam  # noqa: E402


def test_clv_ledger_handles_string_reference_from_real_nesine_global(tmp_path: Path):
    ai_dir = tmp_path / "geminitahmin"
    day_dir = ai_dir / "2026-11-26"
    day_dir.mkdir(parents=True)
    # Real nesine_global.json stores `reference` as a string, not a dict!
    ng = {
        "matches": [
            {
                "code": 5001,
                "reference": "Pinnacle (football-data)",
                "selections": [{"name": "MS 1", "odds": 1.65, "fair_prob": 0.62, "direct": True}],
            }
        ]
    }
    (day_dir / "nesine_global.json").write_text(json.dumps(ng), encoding="utf-8")
    with (day_dir / "mac_tahminleri.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["nesine_kodu", "mac", "secim_adi", "nesine_oran", "olasilik"])
        w.writeheader()
        w.writerow({"nesine_kodu": "5001", "mac": "A - B", "secim_adi": "MS 1", "nesine_oran": "1.65", "olasilik": "0.62"})

    res = record_daily_picks(ai_dir, "2026-11-26")
    assert res["added"] == 1
    row = json.loads((ai_dir / "clv_defteri.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["ref_source"] == "Pinnacle (football-data)"
    assert row["direct"] is True


def test_gunluk_tahmin_loads_all_sharp_env_keys_and_unified_diag_context(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "API_FOOTBALL_KEY=af_test\nTHE_ODDS_API_KEY=toa_test\nODDSPAPI_API_KEY=op_test\n",
        encoding="utf-8",
    )
    env: dict[str, str] = {}
    loaded = GT.load_env_keys(env_file=env_file, environ=env)
    assert set(loaded) == {"API_FOOTBALL_KEY", "THE_ODDS_API_KEY", "ODDSPAPI_API_KEY"}
    assert env["THE_ODDS_API_KEY"] == "toa_test"

    match_rec = {
        "mu_home": 1.7,
        "mu_away": 0.9,
        "fair_1x2": [0.58, 0.24, 0.18],
        "reference": "Pinnacle",
        "league": "İngiltere Premier Lig",
        "steam_1x2": [-0.05, 0.02, 0.03],
        "consensus_gap": 0.02,
        "consensus_dispersion": {"max_prob_std": 0.012, "max_kl_divergence": 0.004, "n_books": 3},
        "research": {
            "flags": [],
            "motivation_regime": {"dead_rubber": True},
            "referee_profile": {"card_zscore": 2.3},
        },
        "selections": [{"name": "MS 1", "fair_prob": 0.58, "direct": True}],
    }
    ctx = GT._match_diag_context(match_rec, "MS 1")
    assert ctx["dead_rubber"] is True
    assert ctx["referee_card_zscore"] == pytest.approx(2.3)
    assert ctx["steam_1x2"] == [-0.05, 0.02, 0.03]
    assert ctx["consensus_kl"] == pytest.approx(0.004)
    assert ctx["fair_1x2"] == [0.58, 0.24, 0.18]


def test_consensus_multi_and_synthetic_coherence_in_nesine_global():
    r1 = {"source": "Pinnacle (football-data)", "x12": [2.00, 3.60, 4.00], "ou": [2.5, [1.90, 1.95]]}
    r2 = {"source": "Smarkets (borsa)", "x12": [2.04, 3.55, 3.90], "ou": [2.5, [1.92, 1.93]]}
    r3 = {"source": "Matchbook (borsa)", "x12": [2.02, 3.58, 3.95], "ou": [2.5, [1.91, 1.94]]}
    c = NG.consensus_multi([r1, r2, r3])
    assert c is not None
    assert c["consensus_dispersion"]["n_books"] == 3
    assert c["consensus_dispersion"]["max_kl_divergence"] < 0.005
    assert sum(1.0 / o for o in c["x12"]) == pytest.approx(1.0, abs=1e-3)

    # Contradicting 3rd exchange is rejected
    r_bad = {"source": "Matchbook (borsa)", "x12": [4.20, 3.60, 1.85]}
    assert NG.consensus_multi([r1, r2, r_bad]) is None

    # Synthetic coherence attached in price_event
    sels = [
        SimpleNamespace(market_id=1, market_title="MS", label="1", name="MS 1", odds=2.10, negate=False, mbs=1),
        SimpleNamespace(market_id=1, market_title="MS", label="X", name="MS 0", odds=3.40, negate=False, mbs=1),
        SimpleNamespace(market_id=1, market_title="MS", label="2", name="MS 2", odds=3.50, negate=False, mbs=1),
        SimpleNamespace(market_id=2, market_title="ÇŞ", label="1-0", name="ÇŞ 10", odds=1.22, negate=False, mbs=1),
    ]
    ev = SimpleNamespace(code=90001, selections=sels, odds_of=lambda n: next((s.odds for s in sels if s.name == n), None))
    priced = NG.price_event(ev, c, "İngiltere Premier Lig")
    assert priced["consensus_dispersion"]["n_books"] == 3
    assert priced["synthetic_coherence"] is not None
    assert "ÇŞ 1X" in priced["synthetic_coherence"]["synthetic_dc_odds"]


def test_fetch_global_odds_stdlib_log_pool_consensus():
    books = {
        "PS": [1.95, 3.55, 4.15],
        "BFE": [1.98, 3.60, 4.20],
        "B365": [1.91, 3.50, 4.00],
    }
    odds, gap = FGO._log_pool_consensus_x12(books)
    assert len(odds) == 3
    assert sum(1.0 / o for o in odds) == pytest.approx(1.0, abs=1e-3)
    assert 0.0 <= gap < 0.02


def test_live_scan_extracts_last_goal_for_hawkes_and_prices_next_goal():
    espn_payload = {
        "events": [
            {
                "id": "e1",
                "status": {"type": {"state": "in"}, "displayClock": "62'", "period": 2},
                "competitions": [
                    {
                        "competitors": [
                            {"homeAway": "home", "score": "1", "team": {"id": "10", "displayName": "Home FC"}},
                            {"homeAway": "away", "score": "0", "team": {"id": "20", "displayName": "Away FC"}},
                        ],
                        "details": [
                            {"scoringPlay": True, "team": {"id": "10"}, "clock": {"displayValue": "60'"}},
                        ],
                    }
                ],
            }
        ]
    }
    parsed = LS.parse_espn_scoreboard(espn_payload)
    assert len(parsed) == 1
    assert parsed[0]["last_goal_minute"] == pytest.approx(60.0)
    assert parsed[0]["last_goal_side"] == "home"

    nes = {"code": 1, "home": "Home FC", "away": "Away FC", "markets": {"2.5 Üst": 2.40, "Sıradaki Gol Ev": 2.80}}
    ops_burst = LS.evaluate(nes, parsed[0], (1.5, 1.1, "test"), {}, min_ev=-0.5, reserve=100,
                            kelly_mult=0.25, cap_frac=0.2, step=5, min_stake=5)
    quiet = dict(parsed[0], last_goal_minute=None, last_goal_side=None)
    ops_quiet = LS.evaluate(nes, quiet, (1.5, 1.1, "test"), {}, min_ev=-0.5, reserve=100,
                            kelly_mult=0.25, cap_frac=0.2, step=5, min_stake=5)
    b_map = {o["market"]: o for o in ops_burst}
    q_map = {o["market"]: o for o in ops_quiet}
    assert b_map["2.5 Üst"]["lambda_remaining"][0] > q_map["2.5 Üst"]["lambda_remaining"][0]
    assert "Sıradaki Gol Ev" in b_map
    ng_probs = b_map["2.5 Üst"]["next_goal_probs"]
    assert sum(ng_probs.values()) == pytest.approx(1.0, abs=1e-3)


def test_league_halves_covers_expanded_high_sample_leagues():
    LH._table.cache_clear()
    for lg in ("ABD Major Lig", "Arjantin Premier Lig", "Çin Süper Lig", "Kolombiya Primera A",
               "Copa Libertadores", "Portekiz 2. Lig", "İspanya Segunda RFEF", "Yunanistan Süper Lig 2"):
        share = LH.league_first_half_share(lg)
        assert share is not None and 0.35 < share < 0.55, f"Missing/invalid 1H share for {lg}: {share}"
    assert LH.league_first_half_share("Bilinmeyen Yerel Lig") is None


def test_capital_shield_drawdown_circuit_breaker_and_dispersion_throttle():
    cands = [
        SystemLeg(str(100 + i), f"Ev{i} - Dep{i}", "MS 1", odds=1.45, p=0.68, mbs=1, consensus_dispersion=0.01)
        for i in range(3)
    ]
    base = build_capital_shield_plan(cands, bankroll_tl=1000.0, max_tickets=1, legs_per_ticket=3)
    dd12 = build_capital_shield_plan(cands, bankroll_tl=1000.0, max_tickets=1, legs_per_ticket=3, drawdown_pct=0.12)
    dd25 = build_capital_shield_plan(cands, bankroll_tl=1000.0, max_tickets=1, legs_per_ticket=3, drawdown_pct=0.25)

    assert len(base.tickets) == 1 and base.tickets[0].stake_tl == 30.0
    assert len(dd12.tickets) == 1 and dd12.tickets[0].stake_tl < base.tickets[0].stake_tl
    assert len(dd25.tickets) == 0 and dd25.total_staked_tl == 0.0

    high_disp = [
        SystemLeg(str(200 + i), f"Ev{i} - Dep{i}", "MS 1", odds=1.45, p=0.68, mbs=1, consensus_dispersion=0.05)
        for i in range(3)
    ]
    disp_plan = build_capital_shield_plan(high_disp, bankroll_tl=1000.0, max_tickets=1, legs_per_ticket=3)
    assert len(disp_plan.tickets) == 1 and disp_plan.tickets[0].stake_tl < base.tickets[0].stake_tl


def test_market_diagnosis_directional_steam_and_consensus_kl():
    ctx_against = {
        "mu_home": 1.8, "mu_away": 0.7, "fair_1x2": [0.66, 0.21, 0.13],
        "reference": "Pinnacle", "direct": True, "steam_1x2": [-0.055, 0.025, 0.030],
    }
    assert parse_directional_steam(ctx_against, "MS 1") == pytest.approx(-0.055)
    d_bad = diagnose_selection("MS 1", 0.66, ctx_against, for_coupon=True)
    assert not d_bad.ok and any("TERS" in r for r in d_bad.reasons)

    ctx_with = {
        "mu_home": 1.8, "mu_away": 0.7, "fair_1x2": [0.66, 0.21, 0.13],
        "reference": "Pinnacle", "direct": True, "steam_1x2": [0.045, -0.020, -0.025],
    }
    d_good = diagnose_selection("MS 1", 0.66, ctx_with, for_coupon=True)
    assert d_good.ok and any("yön uyumlu" in s for s in d_good.strengths)

    ctx_kl = {**ctx_with, "consensus_kl": 0.028}
    d_kl = diagnose_selection("MS 1", 0.66, ctx_kl, for_coupon=True)
    assert not d_kl.ok and any("KL=" in r for r in d_kl.reasons)


def test_self_improve_reports_corp_calibration_and_isolated_clv_summary(tmp_path: Path):
    ai_dir = tmp_path / "tahminler" / "geminitahmin"
    day = ai_dir / "2026-11-25"
    day.mkdir(parents=True)
    matches = []
    results = {}
    for i in range(1, 7):
        code = 3000 + i
        matches.append({
            "code": code, "league": "İspanya La Liga", "status": "fiyatlandı", "reference": "Pinnacle",
            "mu_home": 1.6, "mu_away": 0.9, "fair_1x2": [0.55, 0.25, 0.20], "research": {"flags": []},
            "selections": [{"name": "3.5 Alt", "odds": 1.32, "fair_prob": 0.70 + 0.02 * (i % 3), "direct": True}],
        })
        results[code] = {"completed": True, "ht": [0, 0], "ft90": [1, 0] if i <= 5 else [3, 2]}
    (day / "nesine_global.json").write_text(json.dumps({"matches": matches}), encoding="utf-8")

    # Add isolated CLV ledger entry with closing prob
    clv_entry = {
        "id": "2026-11-25|3001|3.5 Alt|kuponlar.csv", "date": "2026-11-25", "code": 3001,
        "match": "A - B", "source_file": "kuponlar.csv", "selection": "3.5 Alt", "family": "Alt/Üst",
        "odds_taken": 1.32, "p_model": 0.76, "p_open_sharp": 0.76, "p_close_sharp": 0.78,
        "clv": 1.32 * 0.78 - 1.0, "steam_delta_p": 0.02, "won": True, "flat_pnl": 0.32,
    }
    (ai_dir / "clv_defteri.jsonl").write_text(json.dumps(clv_entry) + "\n", encoding="utf-8")

    rep = run_self_audit(ai_dir, results_by_code=results, min_n=1)
    corp = rep["corp_calibration"]
    assert corp is not None and corp["n"] == 6 and corp["corp_ece"] >= 0.0
    assert corp["brier"] == pytest.approx(corp["mcb"] - corp["dsc"] + corp["unc"], abs=1e-4)
    assert rep["clv_summary"] is not None and rep["clv_summary"]["n_with_closing_clv"] == 1
    assert rep["clv_summary"]["clv_report"]["mean_clv"] > 0.0
    md = render_markdown(rep)
    assert "CORP Kutusuz Kalibrasyon" in md
    assert "CLV Defteri" in md
