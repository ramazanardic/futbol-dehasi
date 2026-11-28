"""Offline unit tests for QuantFoot Unified Decision & Coupon Engine v2 and TM cache/aliases."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

import pytest

from quantfoot.coupons.unified_engine import (
    ALLOWED_HTFT_REVERSALS,
    GOLD_CORE_SELECTIONS,
    InjuryProfile,
    SelfLearningAdjustments,
    build_both_halves_btts_coupon,
    build_clean_slate_portfolio,
    build_ft_score_coupon,
    build_ht_score_coupon,
    build_htft_reversal_coupon,
    build_second_half_btts_coupon,
    build_specialty_suite,
    evaluate_directional_injury,
    extract_clean_candidates,
    load_self_learning_adjustments,
    selections_conflict,
)
from quantfoot.data import absences

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
    # Away GK1 out -> blocks Unders, MS 2, and İY Skor 0-0; boosts HOME goals (Ev 1.5 Üst), NOT MS 1
    inj_gk = InjuryProfile(away_gk1_out=True)
    assert evaluate_directional_injury("3.5 Alt", inj_gk)[0] is False
    assert evaluate_directional_injury("Ev 1.5 Alt", inj_gk)[0] is False
    assert evaluate_directional_injury("İY Skor 0-0", inj_gk)[0] is False
    ok_ev_ust, boost_ev, note_ev = evaluate_directional_injury("Ev 1.5 Üst", inj_gk)
    ok_ms1, boost_ms1, _ = evaluate_directional_injury("MS 1", inj_gk)
    assert ok_ev_ust is True and boost_ev > 0.0 and note_ev is not None
    assert ok_ms1 is True and boost_ms1 == 0.0

    # Home top scorer out -> blocks KG Var / 2Y KG Var / İki Yarıda KG Var / Ev 1.5 Üst / MS 1; boosts Ev 1.5 Alt & İY Skor 0-0
    inj_sc = InjuryProfile(home_top_scorer_out=True)
    assert evaluate_directional_injury("KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("2Y KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("İki Yarıda KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("2.5 Üst & KG Var", inj_sc)[0] is False
    assert evaluate_directional_injury("Ev 1.5 Üst", inj_sc)[0] is False
    assert evaluate_directional_injury("MS 1", inj_sc)[0] is False
    assert evaluate_directional_injury("İY/MS 0/1", inj_sc)[0] is False
    ok_alt, boost_alt, _ = evaluate_directional_injury("Ev 1.5 Alt", inj_sc)
    ok_ht00, boost_ht00, _ = evaluate_directional_injury("İY Skor 0-0", inj_sc)
    assert ok_alt is True and boost_alt > 0.0
    assert ok_ht00 is True and boost_ht00 > 0.0


def test_oos_validated_gold_core_and_symmetric_steam_shock_shield():
    now = dt.datetime(2026, 11, 28, 17, 0, tzinfo=TSI)
    # 1. Confirm 2-day overfit traps removed from Banko Gold Core
    assert "MS 2" not in GOLD_CORE_SELECTIONS
    assert "İY 0.5 Üst" not in GOLD_CORE_SELECTIONS
    assert "KG Yok" in GOLD_CORE_SELECTIONS
    assert "1.5 Üst" in GOLD_CORE_SELECTIONS

    m_tight = _sample_match(
        101,
        mu_h=1.25,
        mu_a=0.72,
        f1x2=[0.52, 0.28, 0.20],
        selections=[
            # Tight match (tot=1.97 < 2.60): 1.5 Üst MUST be blocked
            {"market": "AÜ", "selection": "1.5 Üst", "name": "1.5 Üst", "key": "k1", "odds": 1.24, "fair_prob": 0.72, "mbs": 1, "direct": True},
            # Poison / toxic markets MUST be blocked
            {"market": "İY ÇŞ", "selection": "1-2", "name": "İY ÇŞ 12", "key": "k2", "odds": 1.30, "fair_prob": 0.68, "mbs": 1, "direct": False},
            {"market": "Dep AÜ", "selection": "1.5 Üst", "name": "Dep 1.5 Üst", "key": "k3", "odds": 1.40, "fair_prob": 0.65, "mbs": 1, "direct": False},
            # Blind İY 0.5 Üst & MS 2 MUST be excluded from Banko Gold Core
            {"market": "İY AÜ", "selection": "0.5 Üst", "name": "İY 0.5 Üst", "key": "k4", "odds": 1.32, "fair_prob": 0.72, "mbs": 1, "direct": False},
            {"market": "MS", "selection": "2", "name": "MS 2", "key": "k5", "odds": 1.36, "fair_prob": 0.69, "mbs": 1, "direct": True},
            # Valid Gold Core markets MUST pass (ÇŞ 1X, İY&2Y KG Yok, KG Yok)
            {"market": "ÇŞ", "selection": "1-X", "name": "ÇŞ 1X", "key": "k6", "odds": 1.22, "fair_prob": 0.73, "mbs": 1, "direct": True},
            {"market": "Yarı KG", "selection": "H/H", "name": "İY KG Yok & 2Y KG Yok", "key": "k7", "odds": 1.30, "fair_prob": 0.69, "mbs": 1, "direct": False},
            {"market": "KG", "selection": "Yok", "name": "KG Yok", "key": "k8", "odds": 1.45, "fair_prob": 0.65, "mbs": 1, "direct": True},
        ],
    )
    # 2. Symmetric sharp steam shock (+7.5p POSITIVE steam) MUST STILL block MS 1 AND 3.5 Alt!
    m_pos_steam = _sample_match(
        104,
        mu_h=1.45,
        mu_a=0.75,
        f1x2=[0.68, 0.20, 0.12],
        steam=[0.075, -0.035, -0.040],
        selections=[
            {"market": "MS", "selection": "1", "name": "MS 1", "key": "s1", "odds": 1.35, "fair_prob": 0.70, "mbs": 1, "direct": True},
            {"market": "AÜ", "selection": "3.5 Alt", "name": "3.5 Alt", "key": "s2", "odds": 1.26, "fair_prob": 0.74, "mbs": 1, "direct": True},
            {"market": "KG", "selection": "Yok", "name": "KG Yok", "key": "s3", "odds": 1.44, "fair_prob": 0.66, "mbs": 1, "direct": True},
        ],
    )
    # 3. MS 2 in 20x mode: P=0.69 rejected, P=0.73 allowed
    m_away_fav = _sample_match(
        105,
        mu_h=0.70,
        mu_a=2.10,
        f1x2=[0.11, 0.16, 0.73],
        selections=[
            {"market": "MS", "selection": "2", "name": "MS 2", "key": "a1", "odds": 1.30, "fair_prob": 0.73, "mbs": 1, "direct": True},
        ],
    )
    m_away_weak = _sample_match(
        106,
        mu_h=0.90,
        mu_a=1.95,
        f1x2=[0.14, 0.17, 0.69],
        selections=[
            {"market": "MS", "selection": "2", "name": "MS 2", "key": "a2", "odds": 1.35, "fair_prob": 0.69, "mbs": 1, "direct": True},
        ],
    )

    banko_pools = extract_clean_candidates([m_tight, m_pos_steam], now=now, mode="banko", sharp_only=True)
    assert len(banko_pools) == 1
    assert {lg.name for lg in banko_pools[0]} == {"ÇŞ 1X", "İY KG Yok & 2Y KG Yok", "KG Yok"}

    hi_pools = extract_clean_candidates([m_away_fav, m_away_weak], now=now, mode="yuksek_20x", sharp_only=True)
    assert len(hi_pools) == 1
    assert hi_pools[0][0].code == 105 and hi_pools[0][0].name == "MS 2"


def test_self_learning_adjustments_auto_blocks_toxic_and_scales_prob_effective(tmp_path: Path):
    report = {
        "ai": "antigravitytahmin",
        "generated_at": "2026-11-28T05:11+03:00",
        "settled_matches": 614,
        "toxic_alarms": [
            {"selection": "KG Var", "n": 134, "shrunk_residual": -0.0246},
            {"selection": "SmallNoise", "n": 12, "shrunk_residual": -0.0500},
        ],
        "by_selection": {
            "KG Yok": {"n": 34, "shrunk_residual": 0.0245},
            "Ev 1.5 Alt": {"n": 118, "shrunk_residual": 0.0339},
            "MS 1": {"n": 84, "shrunk_residual": -0.0200},
        },
    }
    (tmp_path / "oz_gelistirme_raporu.json").write_text(json.dumps(report), encoding="utf-8")

    sl = load_self_learning_adjustments(tmp_path)
    assert "KG Var" in sl.blocked_selections
    assert "SmallNoise" not in sl.blocked_selections
    assert sl.prob_deltas["KG Yok"] == pytest.approx(0.0123, abs=1e-4)
    assert sl.prob_deltas["Ev 1.5 Alt"] == pytest.approx(0.0150, abs=1e-4)  # clamped at +1.5p
    assert sl.prob_deltas["MS 1"] == pytest.approx(-0.0100, abs=1e-4)

    now = dt.datetime(2026, 11, 28, 17, 0, tzinfo=TSI)
    m = _sample_match(
        201,
        mu_h=2.0,
        mu_a=1.5,
        f1x2=[0.66, 0.20, 0.14],
        selections=[
            {"market": "KG", "selection": "Var", "name": "KG Var", "key": "kgv", "odds": 1.45, "fair_prob": 0.64, "mbs": 1, "direct": True},
            {"market": "MS", "selection": "1", "name": "MS 1", "key": "ms1", "odds": 1.40, "fair_prob": 0.66, "mbs": 1, "direct": True},
        ],
    )
    pools_no_sl = extract_clean_candidates([m], now=now, mode="yuksek_20x", self_learning=None)
    pools_with_sl = extract_clean_candidates([m], now=now, mode="yuksek_20x", self_learning=sl)
    assert {"KG Var", "MS 1"} == {lg.name for lg in pools_no_sl[0]}
    assert {"MS 1"} == {lg.name for lg in pools_with_sl[0]}
    ms1_no = next(lg for lg in pools_no_sl[0] if lg.name == "MS 1")
    ms1_yes = pools_with_sl[0][0]
    assert ms1_yes.prob_effective == pytest.approx(ms1_no.prob_effective - 0.0100, abs=1e-4)


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

    u1, u2, u3, u4 = by_id["U01"], by_id["U02"], by_id["U03"], by_id["U04"]
    assert len(u1.legs) == 3 and u1.total_odds >= 2.05
    assert len(u2.legs) == 4 and u2.total_odds >= 3.20 and u2.insurance is not None
    assert u2.insurance.sizes == (3, 4)
    assert {x.code for x in u1.legs}.isdisjoint({x.code for x in u2.legs})
    assert u3.total_odds >= 20.0 and u4.total_odds >= 20.0
    assert {x.code for x in u3.legs}.isdisjoint({x.code for x in u4.legs})

    all_pairs = [(lg.code, lg.key) for c in portfolio for lg in c.legs]
    assert len(all_pairs) == len(set(all_pairs))


def test_specialty_suite_builds_all_5_coupons_with_tm_guards_and_zero_conflicts():
    now = dt.datetime(2026, 11, 28, 17, 0, tzinfo=TSI)
    leagues = [
        "Almanya Bundesliga", "İspanya La Liga", "İtalya Serie A",
        "Fransa Ligue 1", "Hollanda Eredivisie", "Belçika Pro Lig",
    ]
    matches = []
    for i in range(6):
        code = 700 + i
        # Match 700 has home GK1 out -> MUST block İY Skor 0-0 & Skor 1-0!
        # Match 701 has away top scorer out -> MUST block İki Yarıda KG Var & 2Y KG Var, BOOST İY Skor 0-0!
        tm = {}
        if code == 700:
            tm = {"home": {"gk1_out": True}}
        elif code == 701:
            tm = {"away": {"top_scorer_out": True}}
        sels = [
            {"key": "779|İY Skor 0-0|0", "market": "1. Yarı Skoru", "selection": "0:0", "name": "İY Skor 0-0", "odds": 2.95, "fair_prob": 0.31, "mbs": 1, "direct": False},
            {"key": "777|Skor 1-0|0", "market": "Maç Skoru", "selection": "1:0", "name": "Skor 1-0", "odds": 7.50, "fair_prob": 0.12, "mbs": 1, "direct": False},
            {"key": "777|Skor 2-1|0", "market": "Maç Skoru", "selection": "2:1", "name": "Skor 2-1", "odds": 8.10, "fair_prob": 0.115, "mbs": 1, "direct": False},
            {"key": "5|İY/MS 0/1|0", "market": "İlk Yarı/Maç Sonucu", "selection": "X/1", "name": "İY/MS 0/1", "odds": 4.90, "fair_prob": 0.18, "mbs": 1, "direct": False},
            {"key": "5|İY/MS 1/1|0", "market": "İlk Yarı/Maç Sonucu", "selection": "1/1", "name": "İY/MS 1/1", "odds": 2.40, "fair_prob": 0.38, "mbs": 1, "direct": False},
            {"key": "801|İki Yarıda KG Var|0", "market": "1. Yarı / 2. Yarı Karşılıklı Gol", "selection": "Evet/Evet", "name": "İki Yarıda KG Var", "odds": 9.50, "fair_prob": 0.095, "mbs": 1, "direct": False},
            {"key": "599|2Y KG Var|0", "market": "2. Yarı Karşılıklı Gol", "selection": "Var", "name": "2Y KG Var", "odds": 2.85, "fair_prob": 0.31, "mbs": 3, "direct": False},
        ]
        matches.append(
            _sample_match(
                code,
                league=leagues[i],
                mu_h=1.80,
                mu_a=1.40,
                selections=sels,
                tm=tm,
                kickoff_iso=f"2026-11-28T{19 + (i % 3):02d}:00:00+03:00",
            )
        )

    yuksek = {"golden_scores": [{"code": 703, "top_scores": [{"score": "2-1", "is_golden": True, "p_model": 0.12}]}]}
    ekstrem = {"both_halves_btts": [{"code": 704, "dna_score": 82.0}]}

    suite = build_specialty_suite(matches, now=now, ekstrem_gol_data=ekstrem, yuksek_oran_data=yuksek)
    by_id = {c.coupon_id: c for c in suite}
    assert set(by_id) == {"S01", "S02", "S03", "S04", "S05"}

    # S01 (İY Skor): 700 (GK1 out) MUST NOT be chosen with İY Skor 0-0; 701 (scorer out) SHOULD be boosted & included
    assert all(not (lg.code == 700 and lg.name == "İY Skor 0-0") for lg in by_id["S01"].legs)
    assert any(lg.code == 701 and lg.name == "İY Skor 0-0" for lg in by_id["S01"].legs)

    # S03 (İY/MS): ONLY allowed 6 outcomes (never İY/MS 1/1!)
    assert all(lg.name in ALLOWED_HTFT_REVERSALS for lg in by_id["S03"].legs)

    # S04 (İki Yarıda KG Var) & S05 (2Y KG Var): 701 (top scorer out) MUST be excluded!
    assert all(lg.code != 701 for lg in by_id["S04"].legs)
    assert all(lg.code != 701 for lg in by_id["S05"].legs)

    # Zero logical contradictions across ALL 5 specialty coupons on the same match
    all_legs = [lg for c in suite for lg in c.legs]
    for i, a in enumerate(all_legs):
        for b in all_legs[i + 1 :]:
            if a.code == b.code:
                assert not selections_conflict(a.name, b.name), f"Conflict on {a.code}: {a.name} vs {b.name}"


def test_absences_league_aliases_and_disk_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Verify newly restored live-verified league aliases and whitespace/Ligi normalization
    assert absences.resolve_tm_league_codes("Türkiye Süper Ligi") == ["TR1"]
    assert absences.resolve_tm_league_codes("  Türkiye Süper Lig  ") == ["TR1"]
    assert absences.resolve_tm_league_codes("İspanya Segunda RFEF") == ["E4G1", "E4G2", "E4G3", "E4G4", "E4G5"]
    assert absences.resolve_tm_league_codes("Türkiye Nesine 2. Lig, Beyaz Grup") == ["TR3B"]
    assert absences.resolve_tm_league_codes("Belarus Premier Lig") == ["WER1"]
    assert absences.resolve_tm_league_codes("Fas Botola Pro") == ["MAR1"]
    assert absences.resolve_tm_league_codes("İsviçre Yükselme 1.Ligi") == ["CHPR"]

    # Verify fresh disk cache hit returns cached absences without making any network call
    cache_file = tmp_path / "tm_2026-11-28.json"
    cached_payload = {"999001": {"home": {"gk1_out": True}, "away": None, "alerts": ["Ev 1. kaleci eksik"]}}
    cache_file.write_text(json.dumps(cached_payload), encoding="utf-8")

    def _forbid_network(*args, **kwargs):
        raise AssertionError("Network call must not happen on fresh TM disk cache hit!")

    monkeypatch.setattr(absences, "fetch_tm_league", _forbid_network)
    res = absences.fetch_matchday_absences(
        [{"code": 999001, "league": "Türkiye Süper Ligi", "home": "Fenerbahçe", "away": "Beşiktaş"}],
        cache_path=cache_file,
        cache_ttl_hours=4.0,
    )
    assert 999001 in res
    assert res[999001]["home"]["gk1_out"] is True


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
    assert "--ozel" in r.stdout
    assert "--ogrenme-kapali" in r.stdout
