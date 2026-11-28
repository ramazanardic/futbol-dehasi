"""Unit & integration tests for Close-Match 1X2 Resolver, HT/FT Comeback (1/2 & 2/1),
Team Half-Split Intelligence, Both-Halves BTTS upgrade, Exact Score Intelligence,
Nesine Stale-Odds Scanner, and Auto League/Market Blacklist."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import gunluk_tahmin as G  # noqa: E402
from quantfoot.markets.extreme_goals import score_both_halves_btts_match  # noqa: E402
from quantfoot.markets.high_odds_engine import (  # noqa: E402
    analyze_close_match,
    analyze_exact_scores,
    build_league_market_blacklist,
    scan_high_odds_day,
    scan_nesine_value_anomalies,
    score_comeback_htft,
)
from quantfoot.markets.match_intelligence import (  # noqa: E402
    build_half_split_view,
    compute_team_half_profiles,
    enrich_match_record,
)


def _sample_close_match(**overrides) -> dict:
    base = {
        "code": 7701,
        "kickoff": "2026-11-26 20:00",
        "kickoff_iso": "2026-11-26T20:00:00+03:00",
        "league": "İngiltere Premier Lig",
        "home": "Brighton",
        "away": "Newcastle",
        "status": "fiyatlandı",
        "reference": "Pinnacle + Smarkets",
        "mu_home": 1.42,
        "mu_away": 1.32,
        "fair_1x2": [0.39, 0.26, 0.35],
        "nesine_ms_margin": 0.088,
        "selections": [
            {"name": "MS 1", "market": "Maç Sonucu", "selection": "1", "odds": 2.20, "fair_prob": 0.39, "direct": True},
            {"name": "MS 0", "market": "Maç Sonucu", "selection": "0", "odds": 3.30, "fair_prob": 0.26, "direct": True},
            {"name": "MS 2", "market": "Maç Sonucu", "selection": "2", "odds": 2.55, "fair_prob": 0.35, "direct": True},
            {"name": "ÇŞ 10", "market": "Çifte Şans", "selection": "1-0", "odds": 1.38, "fair_prob": 0.68, "direct": True},
            {"name": "ÇŞ 02", "market": "Çifte Şans", "selection": "0-2", "odds": 1.52, "fair_prob": 0.60, "direct": True},
            {"name": "2.5 Üst", "market": "2.5 Alt/Üst", "selection": "Üst", "odds": 1.75, "fair_prob": 0.54, "direct": True},
            {"name": "KG Var", "market": "Karşılıklı Gol", "selection": "Var", "odds": 1.62, "fair_prob": 0.58, "direct": True},
            {"name": "İY/MS 1/2", "market": "İY/MS", "selection": "1/2", "odds": 26.0, "fair_prob": 0.036, "direct": False},
            {"name": "İY/MS 2/1", "market": "İY/MS", "selection": "2/1", "odds": 24.0, "fair_prob": 0.040, "direct": False},
            {"name": "İki Yarıda KG Var", "market": "Her İki Yarıda KG", "selection": "Var", "odds": 11.5, "fair_prob": 0.09, "direct": False},
            {"name": "Skor 2-1", "market": "Maç Skoru", "selection": "2-1", "odds": 9.0, "fair_prob": 0.10, "direct": False},
            {"name": "Skor 1-2", "market": "Maç Skoru", "selection": "1-2", "odds": 9.8, "fair_prob": 0.09, "direct": False},
            {"name": "Skor 1-1", "market": "Maç Skoru", "selection": "1-1", "odds": 6.4, "fair_prob": 0.12, "direct": False},
            {"name": "Skor 2-2", "market": "Maç Skoru", "selection": "2-2", "odds": 13.5, "fair_prob": 0.06, "direct": False},
        ],
        "research": {"flags": []},
    }
    base.update(overrides)
    return base


def test_close_match_220_330_255_identifies_hidden_xg_and_steam_edge():
    # Classic 2.20 / 3.30 / 2.55 balanced odds match where Away has strong xG + finishing bad-luck + sharp steam!
    m = _sample_close_match(
        steam_1x2=[-0.045, 0.005, 0.040],
        research={
            "flags": [],
            "xg_intelligence": {
                "xg_mu_home": 1.10,
                "xg_mu_away": 1.85,
                "home": {"matches": 10, "finishing_luck": 0.60, "defensive_luck": 0.25},
                "away": {"matches": 10, "finishing_luck": -0.55, "defensive_luck": -0.10},
            },
        },
    )
    res = analyze_close_match(m)
    assert res is not None
    assert res.is_close_match is True
    assert sum(res.model_1x2.values()) == pytest.approx(1.0, abs=1e-3)
    # Away model prob must rise significantly above market 32% and become best_outcome (MS 2 @ 2.55)
    assert res.model_1x2["MS 2"] > res.market_1x2["MS 2"] + 0.05
    assert res.best_outcome == "MS 2"
    assert res.verdict in ("GÜÇLÜ DEĞER", "DEĞER")
    assert res.conviction_score >= 60.0
    assert any("xG" in r for r in res.reasons)
    assert any("steam" in r.lower() or "akışı" in r.lower() for r in res.reasons)


def test_close_match_detects_true_draw_regime_for_330_odds():
    m = _sample_close_match(
        mu_home=0.98,
        mu_away=0.95,
        fair_1x2=[0.35, 0.31, 0.34],
        steam_1x2=[-0.01, 0.025, -0.015],
        research={
            "flags": [],
            "weather": {"severe": True, "rain_mm": 8.0, "wind_kmh": 45.0},
            "half_split": {
                "home": {"draw_rate": 0.38},
                "away": {"draw_rate": 0.40},
            },
        },
    )
    res = analyze_close_match(m)
    assert res is not None
    assert res.draw_regime_score >= 70.0
    assert res.model_1x2["MS 0"] > res.market_1x2["MS 0"]
    assert res.best_outcome == "MS 0"


def test_team_half_profiles_and_asymmetric_comeback_12_and_21():
    # Build synthetic causal season rows: FastHome scores early & blows leads; CloserAway scores late & wins comebacks
    rows = []
    for i in range(1, 13):
        d = f"{i:02d}/10/2026"
        # FastHome leads 1-0 at HT, concedes 2 in 2H -> loses 1-2
        rows.append({"Date": d, "HomeTeam": "FastHome", "AwayTeam": f"Opp{i}", "HTHG": 1, "HTAG": 0, "FTHG": 1, "FTAG": 2})
        # CloserAway trails 0-1 at HT, scores 2 in 2H -> wins 2-1
        rows.append({"Date": d, "HomeTeam": f"Opp{i}", "AwayTeam": "CloserAway", "HTHG": 1, "HTAG": 0, "FTHG": 1, "FTAG": 2})

    profs, lg_1h = compute_team_half_profiles(rows, as_of=dt.date(2026, 11, 26))
    fh, ca = profs["FastHome"], profs["CloserAway"]
    assert fh.h1_attack_share > ca.h1_attack_share
    assert fh.lead_lost_rate > 0.40
    assert ca.comeback_win_rate > 0.40

    # Feed this asymmetric profile into score_comeback_htft
    m_asym = _sample_close_match(
        mu_home=1.45,
        mu_away=1.65,
        research={
            "flags": [],
            "half_split": {
                "league_1h_share": lg_1h,
                "home_eff_1h_share": 0.52,
                "away_eff_1h_share": 0.36,
                "home_1h_urgency_shift": 0.08,
                "away_1h_urgency_shift": -0.08,
                "home": fh.to_dict(),
                "away": ca.to_dict(),
            },
        },
    )
    m_flat = _sample_close_match(mu_home=1.45, mu_away=1.65, research={"flags": []})
    cb_asym = {c.kind: c for c in score_comeback_htft(m_asym)}
    cb_flat = {c.kind: c for c in score_comeback_htft(m_flat)}

    # Asymmetric FastHome + CloserAway MUST boost İY/MS 1/2 probability & DNA far above flat symmetric model!
    assert cb_asym["İY/MS 1/2"].p_comeback > cb_flat["İY/MS 1/2"].p_comeback * 1.25
    assert cb_asym["İY/MS 1/2"].dna_score > cb_flat["İY/MS 1/2"].dna_score
    assert cb_asym["İY/MS 1/2"].dna_score >= 70.0
    assert cb_asym["İY/MS 1/2"].archetype == "hizli_basla_yavasla"
    # And İY/MS 1/2 beats İY/MS 2/1 on this matchup
    assert cb_asym["İY/MS 1/2"].dna_score > cb_asym["İY/MS 2/1"].dna_score


def test_both_halves_btts_consumes_live_half_split_profile():
    m_open = _sample_close_match(
        mu_home=1.75,
        mu_away=1.55,
        research={
            "flags": [],
            "half_split": {
                "home_eff_1h_share": 0.48,
                "away_eff_1h_share": 0.47,
                "home": {"matches": 10, "h1_gf": 0.9, "h1_ga": 0.8, "h2_gf": 1.1, "both_halves_btts_rate": 0.20},
                "away": {"matches": 10, "h1_gf": 0.8, "h1_ga": 0.9, "h2_gf": 1.0, "both_halves_btts_rate": 0.18},
            },
        },
    )
    m_slow = _sample_close_match(
        mu_home=1.75,
        mu_away=1.55,
        research={
            "flags": [],
            "half_split": {
                "home_eff_1h_share": 0.34,
                "away_eff_1h_share": 0.33,
                "home": {"matches": 10, "h1_gf": 0.25, "h1_ga": 0.25, "h2_gf": 1.2, "both_halves_btts_rate": 0.00},
                "away": {"matches": 10, "h1_gf": 0.25, "h1_ga": 0.25, "h2_gf": 1.1, "both_halves_btts_rate": 0.00},
            },
        },
    )
    r_open = score_both_halves_btts_match(m_open)
    r_slow = score_both_halves_btts_match(m_slow)
    assert r_open is not None and r_slow is not None
    assert r_open.p_tail > r_slow.p_tail
    assert r_open.dna_score > r_slow.dna_score


def test_exact_scores_stale_odds_and_auto_blacklist():
    m = _sample_close_match(
        mu_home=1.65,
        mu_away=1.25,
        fair_1x2=[0.48, 0.25, 0.27],
        steam_1x2=[0.045, -0.02, -0.025],
        selections=[
            {"name": "MS 1", "market": "Maç Sonucu", "selection": "1", "odds": 2.25, "fair_prob": 0.48, "direct": True},
            {"name": "MS 0", "market": "Maç Sonucu", "selection": "0", "odds": 3.40, "fair_prob": 0.25, "direct": True},
            {"name": "MS 2", "market": "Maç Sonucu", "selection": "2", "odds": 3.30, "fair_prob": 0.27, "direct": True},
            {"name": "2.5 Üst", "market": "2.5 Alt/Üst", "selection": "Üst", "odds": 1.72, "fair_prob": 0.57, "direct": True},
            {"name": "KG Var", "market": "Karşılıklı Gol", "selection": "Var", "odds": 1.62, "fair_prob": 0.60, "direct": True},
            {"name": "Skor 2-1", "market": "Maç Skoru", "selection": "2-1", "odds": 11.0, "fair_prob": 0.09, "direct": False},
            {"name": "Skor 1-2", "market": "Maç Skoru", "selection": "1-2", "odds": 10.5, "fair_prob": 0.07, "direct": False},
            {"name": "Skor 2-2", "market": "Maç Skoru", "selection": "2-2", "odds": 15.0, "fair_prob": 0.05, "direct": False},
        ],
    )
    es = analyze_exact_scores(m)
    assert es is not None
    assert len(es.top_coherent) == 3
    assert es.top_coherent[0].score == "2-1"  # macro-coherent KG+Over win cluster!
    assert any(x.score == "2-1" and (x.ev or 0) > 0 for x in es.value_scores)
    assert len(es.comeback_scores) == 3

    anomalies = scan_nesine_value_anomalies([m])
    assert anomalies and anomalies[0].kind == "bayat_oran" and anomalies[0].selection_name == "MS 1"

    # Auto blacklist flags chronic loser league-market pairs (>= 15 matches, bias <= -8pp, ROI <= -15%)
    settled = [
        {"league": "Bad League", "selection": "2.5 Alt", "p": 0.65, "odds": 1.55, "won": i < 6}
        for i in range(20)
    ] + [
        {"league": "Good League", "selection": "1.5 Üst", "p": 0.72, "odds": 1.45, "won": i < 16}
        for i in range(20)
    ]
    blocked = build_league_market_blacklist(settled)
    assert len(blocked) == 1
    assert blocked[0]["league"] == "Bad League" and blocked[0]["family"] == "Alt/Üst"


def test_live_2026_27_half_split_lookup_and_daily_scanner():
    hv = build_half_split_view("İngiltere Premier Lig", "Arsenal", "Chelsea", as_of=dt.date(2026, 11, 26))
    assert hv is not None
    assert -0.08 <= hv.home_1h_urgency_shift <= 0.08
    assert -0.08 <= hv.away_1h_urgency_shift <= 0.08

    rec = _sample_close_match(home="Arsenal", away="Chelsea")
    enrich_match_record(rec, as_of=dt.date(2026, 11, 26))
    assert "half_split" in rec["research"]
    assert "xg_intelligence" in rec["research"]

    day_out = scan_high_odds_day([rec], only_offered=False, min_comeback_dna=20.0, min_btts_dna=20.0)
    assert day_out["close_matches"]
    assert day_out["comebacks"]
    assert day_out["exact_scores"]

    # Kural onarımı (28 Kas): eski yüksek oran motoru günlük ortak hattan ÇIKARILDI ve betikleri silindi (t178u); kilit korunur
    cmds = G.step_commands("2026-11-26", [2.5], py="py")
    assert not any(c[1].endswith(("yuksek_oran_analiz.py", "yuksek_oran_motoru.py")) for c in cmds["derin"])
