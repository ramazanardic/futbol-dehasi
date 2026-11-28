"""Offline unit tests for the clean-slate QuantFoot Unified Decision & Coupon Engine."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import subprocess
import sys

import pytest

from quantfoot.coupons.unified_engine import (
    InjuryProfile,
    build_clean_slate_portfolio,
    evaluate_directional_injury,
    extract_clean_candidates,
    extract_injury_profile,
    optimize_unified_coupon,
)

TSI = dt.timezone(dt.timedelta(hours=3))
ROOT = Path(__file__).resolve().parents[1]


def _sample_match(
    code: int,
    *,
    league: str = "Almanya Bundesliga",
    ref: str = "Pinnacle",
    mu_h: float = 1.95,
    mu_a: float = 0.90,
    f1x2: list[float] | None = None,
    selections: list[dict] | None = None,
    tm: dict | None = None,
    flags: list[str] | None = None,
    steam: list[float] | None = None,
    kickoff_iso: str = "2026-11-28T20:00:00+03:00",
) -> dict:
    return {
        "code": code,
        "status": "fiyatlandı",
        "price_tier": "keskin" if ref.startswith(("Pinnacle", "Smarkets", "OddsMath (BetInAsia")) else "global_buro",
        "reference": ref,
        "league": league,
        "home": f"Home{code}",
        "away": f"Away{code}",
        "kickoff": kickoff_iso[:16].replace("T", " "),
        "kickoff_iso": kickoff_iso,
        "mu_home": mu_h,
        "mu_away": mu_a,
        "fair_1x2": f1x2 or [0.66, 0.20, 0.14],
        "steam_1x2": steam,
        "research": {"tm_absences": tm or {}, "flags": flags or []},
        "selections": selections or [],
    }


def test_directional_injury_engine_blocks_contradictions_and_boosts_aligned_markets():
    # Away GK1 out -> blocks Unders & MS 2, boosts HOME goals (Ev 1.5 Üst), does NOT blindly boost MS 1
    inj_gk = InjuryProfile(away_gk1_out=True)
    ok_u35, _, _ = evaluate_directional_injury("3.5 Alt", inj_gk)
    ok_ev_alt, _, _ = evaluate_directional_injury("Ev 1.5 Alt", inj_gk)
    ok_ev_ust, boost_ev, note_ev = evaluate_directional_injury("Ev 1.5 Üst", inj_gk)
    ok_ms1, boost_ms1, _ = evaluate_directional_injury("MS 1", inj_gk)
    assert ok_u35 is False
    assert ok_ev_alt is False
    assert ok_ev_ust is True and boost_ev > 0.0 and note_ev is not None
    assert ok_ms1 is True and boost_ms1 == 0.0

    # Home top scorer out -> blocks KG Var / Ev 1.5 Üst / MS 1, boosts Ev 1.5 Alt / İY Skor 0-0
    inj_sc = InjuryProfile(home_top_scorer_out=True)
    assert evaluate_directional_injury("KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("2.5 Üst & KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("Ev 1.5 Üst", inj_sc)[0] is False
    assert evaluate_directional_injury("MS 1", inj_sc)[0] is False
    ok_alt, boost_alt, _ = evaluate_directional_injury("Ev 1.5 Alt", inj_sc)
    assert ok_alt is True and boost_alt > 0.0


def test_extract_clean_candidates_enforces_gold_whitelist_xg_gates_steam_and_sharp_only():
    now = dt.datetime(2026, 11, 28, 17, 0, tzinfo=TSI)
    m_tight = _sample_match(
        101,
        mu_h=1.25,
        mu_a=1.10,
        f1x2=[0.43, 0.30, 0.27],
        selections=[
            # Tight match (tot_xg=2.35 < 2.60): 1.5 Üst MUST be blocked (Ath Bilbao B 1-0 trap)
            {"market": "AÜ", "selection": "1.5 Üst", "name": "1.5 Üst", "key": "k1", "odds": 1.24, "fair_prob": 0.72, "mbs": 1, "direct": True},
            # Poison markets MUST be blocked
            {"market": "İY ÇŞ", "selection": "1-2", "name": "İY ÇŞ 12", "key": "k2", "odds": 1.30, "fair_prob": 0.68, "mbs": 1, "direct": False},
            {"market": "KG", "selection": "Var", "name": "KG Var", "key": "k3", "odds": 1.40, "fair_prob": 0.65, "mbs": 1, "direct": False},
            # Valid Gold Core market (ÇŞ 1X, P=0.73, EV=-0.109) MUST pass
            {"market": "ÇŞ", "selection": "1-X", "name": "ÇŞ 1X", "key": "k4", "odds": 1.22, "fair_prob": 0.73, "mbs": 1, "direct": True},
            # Valid Gold Core (İY KG Yok & 2Y KG Yok, tot_xg=2.35 <= 2.65) MUST pass
            {"market": "Yarı KG", "selection": "H/H", "name": "İY KG Yok & 2Y KG Yok", "key": "k5", "odds": 1.30, "fair_prob": 0.69, "mbs": 1, "direct": False},
        ],
    )
    # Non-sharp global book & youth league MUST be excluded in banko sharp_only mode
    m_nonsharp = _sample_match(
        102,
        ref="OddsMath (Marathonbet)",
        selections=[{"market": "MS", "selection": "1", "name": "MS 1", "key": "k1", "odds": 1.35, "fair_prob": 0.70, "mbs": 1, "direct": True}],
    )
    m_youth = _sample_match(
        103,
        league="Belçika U21 Pro Ligi",
        selections=[{"market": "MS", "selection": "1", "name": "MS 1", "key": "k1", "odds": 1.35, "fair_prob": 0.70, "mbs": 1, "direct": True}],
    )
    # Strong negative steam against home (-7.0p) MUST block MS 1
    m_steam = _sample_match(
        104,
        steam=[-0.07, 0.03, 0.04],
        selections=[{"market": "MS", "selection": "1", "name": "MS 1", "key": "k1", "odds": 1.35, "fair_prob": 0.70, "mbs": 1, "direct": True}],
    )

    pools = extract_clean_candidates([m_tight, m_nonsharp, m_youth, m_steam], now=now, mode="banko", sharp_only=True)
    assert len(pools) == 1
    names = {lg.name for lg in pools[0]}
    assert names == {"ÇŞ 1X", "İY KG Yok & 2Y KG Yok"}


def test_clean_slate_portfolio_builds_short_banko_insured_balanced_and_disjoint_20x():
    now = dt.datetime(2026, 11, 28, 17, 0, tzinfo=TSI)
    leagues = [
        "Almanya Bundesliga", "İspanya La Liga", "İtalya Serie A", "Fransa Ligue 1",
        "Hollanda Eredivisie", "Portekiz Premier Lig", "Belçika Pro Lig", "İsviçre Süper Lig",
        "Avusturya Bundesliga", "Danimarka Süper Ligi", "Polonya Ekstraklasa", "Türkiye Süper Ligi",
    ]
    matches = []
    for i in range(18):
        lg_name = leagues[i % len(leagues)]
        sels = [
            {"market": "MS", "selection": "1", "name": "MS 1", "key": "ms1", "odds": 1.36, "fair_prob": 0.69, "mbs": 1, "direct": True},
            {"market": "Ev AÜ", "selection": "1.5 Üst", "name": "Ev 1.5 Üst", "key": "ev15", "odds": 1.52, "fair_prob": 0.65, "mbs": 1, "direct": False},
            {"market": "İY AÜ", "selection": "0.5 Üst", "name": "İY 0.5 Üst", "key": "iy05", "odds": 1.26, "fair_prob": 0.72, "mbs": 1, "direct": False},
            {"market": "AÜ", "selection": "2.5 Üst", "name": "2.5 Üst", "key": "o25", "odds": 1.55, "fair_prob": 0.63, "mbs": 1, "direct": True},
            {"market": "KG", "selection": "Var", "name": "KG Var", "key": "kgv", "odds": 1.62, "fair_prob": 0.60, "mbs": 1, "direct": True},
            {"market": "Kombine", "selection": "MS 1 & 1.5 Üst", "name": "MS 1 & 1.5 Üst", "key": "c1", "odds": 1.72, "fair_prob": 0.58, "mbs": 1, "direct": False},
            {"market": "Kombine", "selection": "2.5 Üst & KG Var", "name": "2.5 Üst & KG Var", "key": "c2", "odds": 1.68, "fair_prob": 0.59, "mbs": 1, "direct": False},
        ]
        matches.append(
            _sample_match(
                500 + i,
                league=lg_name,
                mu_h=2.25,
                mu_a=1.25,
                f1x2=[0.69, 0.19, 0.12],
                selections=sels,
                kickoff_iso=f"2026-11-28T{19 + (i % 4):02d}:00:00+03:00",
            )
        )

    portfolio = build_clean_slate_portfolio(matches, now=now, n_20x=2)
    by_id = {c.coupon_id: c for c in portfolio}
    assert {"U01", "U02", "U03", "U04"}.issubset(by_id)

    # U01 is a short 3-leg banko; U02 is 4-leg balanced with Sistem(3,4) insurance & ZERO shared matches with U01
    u1, u2, u3, u4 = by_id["U01"], by_id["U02"], by_id["U03"], by_id["U04"]
    assert len(u1.legs) == 3 and u1.total_odds >= 2.05
    assert len(u2.legs) == 4 and u2.total_odds >= 3.20 and u2.insurance is not None
    assert u2.insurance.sizes == (3, 4)
    assert {x.code for x in u1.legs}.isdisjoint({x.code for x in u2.legs})

    # U03 & U04 are >=20.0x and completely disjoint from each other
    assert u3.total_odds >= 20.0 and u4.total_odds >= 20.0
    assert {x.code for x in u3.legs}.isdisjoint({x.code for x in u4.legs})

    # Zero duplicate (code, key) across ALL coupons
    all_pairs = [(lg.code, lg.key) for c in portfolio for lg in c.legs]
    assert len(all_pairs) == len(set(all_pairs))


def test_temiz_kupon_cli_help_exits_zero():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "temiz_kupon.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "--pencere-saat" in r.stdout
    assert "--adet-20x" in r.stdout
