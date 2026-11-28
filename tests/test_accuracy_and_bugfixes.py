"""Regression tests for critical bug fixes and prediction/calibration upgrades."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from quantfoot.data.nesine import NesineEvent, NesineSelection
from quantfoot.evaluation import leg_grading as lg
from quantfoot.markets import inplay
from quantfoot.markets.market_diagnosis import diagnose_selection
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.strategy.coupon_builder import _conflicting_selections, is_main_market_selection

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_nesine_global_prices_real_double_chance_names_as_direct():
    ng = _load_script("nesine_global")
    event = NesineEvent(
        code=999001,
        home="Team A",
        away="Team B",
        kickoff=dt.datetime(2026, 11, 26, 20, 0, tzinfo=ng.TSI),
        league_code=1,
        selections=[
            NesineSelection(1, "Maç Sonucu", "1", "MS 1", 1.85, mbs=1),
            NesineSelection(1, "Maç Sonucu", "X", "MS 0", 3.40, mbs=1),
            NesineSelection(1, "Maç Sonucu", "2", "MS 2", 4.20, mbs=1),
            NesineSelection(3, "Çifte Şans", "1-X", "ÇŞ 1X", 1.24, mbs=1),
            NesineSelection(3, "Çifte Şans", "1-2", "ÇŞ 12", 1.30, mbs=1),
            NesineSelection(3, "Çifte Şans", "X-2", "ÇŞ X2", 1.92, mbs=1),
        ],
    )
    ref = {
        "source": "Pinnacle",
        "x12": [1.90, 3.60, 4.40],
        "ou": (2.5, [1.95, 1.90]),
    }
    # Even in an uncalibrated competition (women's league), direct 1X2-derived ÇŞ 1X / ÇŞ X2 MUST be kept as direct!
    out = ng.price_event(event, ref, league="İngiltere Kadınlar Süper Lig (K)")
    by_name = {s["name"]: s for s in out["selections"]}
    assert "ÇŞ 1X" in by_name and "ÇŞ X2" in by_name and "ÇŞ 12" in by_name
    assert by_name["ÇŞ 1X"]["direct"] is True
    assert by_name["ÇŞ X2"]["direct"] is True
    p1, px, p2 = out["fair_1x2"]
    assert by_name["ÇŞ 1X"]["fair_prob"] == pytest.approx(p1 + px, abs=1e-3)
    assert by_name["ÇŞ X2"]["fair_prob"] == pytest.approx(px + p2, abs=1e-3)


def test_coupon_builder_recognizes_real_nesine_double_chance_aliases():
    for name in ("MS X", "ÇŞ 1X", "ÇŞ X2", "ÇŞ 10", "ÇŞ 02", "ÇŞ 12"):
        assert is_main_market_selection(name), name
    assert "ÇŞ X2" in _conflicting_selections("MS 1")
    assert "ÇŞ 1X" in _conflicting_selections("MS 2")
    assert "MS 2" in _conflicting_selections("ÇŞ 1X")
    assert "MS 1" in _conflicting_selections("ÇŞ X2")
    assert "MS X" in _conflicting_selections("ÇŞ 12")


def test_kupon_kur_has_no_rule_relaxing_fallback_and_refuses_honestly(tmp_path, monkeypatch, capsys):
    """Kural onarımı (28 Kas): 'asla hayır deme' yedek turu kaldırıldı — kurallara uyan kupon yoksa dürüst ret."""
    kk = _load_script("kupon_kur")
    day_dir = tmp_path / "2026-11-26"
    day_dir.mkdir(parents=True)
    (day_dir / "nesine_global.json").write_text(json.dumps({"matches": []}), encoding="utf-8")

    monkeypatch.setattr(kk.nesine_kupon, "AI_AREA", tmp_path)
    monkeypatch.setattr(kk.af, "day_fixtures", lambda _d: None)
    monkeypatch.setattr(kk, "simulation_verdicts", lambda _d: {})
    monkeypatch.setattr(kk, "weak_legs_allowed", lambda: True)
    monkeypatch.setattr(kk.dr, "to_markdown", lambda date, rows: "# ok")

    calls: list[list[str]] = []

    def fake_main(opts, review=None):
        calls.append(list(opts))
        return None  # nesine_kupon kurallara uyan kupon bulamadı

    monkeypatch.setattr(kk.nesine_kupon, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["kupon_kur.py", "--hedef", "3", "--tarih", "2026-11-26", "--tur", "2"])

    kk.main()
    assert len(calls) == 1
    assert not any("--yontem" in c or "--model-bacak" in c for c in calls)
    assert "dürüst ret" in capsys.readouterr().out
    assert not list(day_dir.glob("kupon_*_derin.md"))


def test_nesine_kupon_fallback_tier_never_leaks_banned_families():
    nk = _load_script("nesine_kupon")
    now = dt.datetime(2026, 11, 26, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    matches = [
        {
            "status": "fiyatlandı",
            "reference": "Pinnacle",
            "ref_fetched_utc": "2026-11-26T06:30:00+00:00",
            "kickoff_iso": "2026-11-26T18:00:00+03:00",
            "kickoff": "2026-11-26 18:00",
            "code": 201,
            "league": "Almanya Bundesliga",
            "home": "Ev",
            "away": "Dep",
            "mu_home": 1.48,
            "mu_away": 1.32,
            "fair_1x2": [0.42, 0.27, 0.31],
            "selections": [
                # KG Var is in BANNED_FAMILIES even when diagnosis_ok is True!
                {
                    "name": "KG Var",
                    "market": "Karşılıklı Gol",
                    "selection": "Var",
                    "odds": 1.45,
                    "fair_prob": 0.72,
                    "ev": 0.044,
                    "mbs": 1,
                    "direct": True,
                    "key": "kg_var",
                },
            ],
        }
    ]
    pol = nk.KM.policy("banko")
    pools = nk.build_Pool_fallback_pools(
        matches,
        now,
        pol,
        min_odds=1.20,
        min_prob=0.65,
        allow_espn=False,
        direct_only=False,
        exclude_cups=True,
        main_markets_only=False,
        allow_mid_researched=False,
        family="karma",
        calibration=None,
        family_ev=True,
        banko_min_ev=-0.115,
    )
    assert pools == [], "Banned family KG Var must never leak through final banko fallback tier"


@pytest.mark.parametrize(
    "leg,res,expected",
    [
        # Half-time double chance graded on HT (0-0 -> 1X true), NOT FT (0-2 -> 1X false)
        ({"market": "1. Yarı Çifte Şans", "sel": "1-X", "name": "İY ÇŞ 1X"}, {"state": "bitti", "ht": [0, 0], "ft": [0, 2]}, True),
        ({"market": "1. Yarı Çifte Şans", "sel": "X-2", "name": "İY ÇŞ X2"}, {"state": "bitti", "ht": [1, 0], "ft": [1, 2]}, False),
        # 2Y totals & 2Y BTTS must not crash or fall into 2Y 1/0/2
        ({"market": "2. Yarı 0,5 Gol Alt/Üst", "sel": "0,5 Üst", "name": "2Y 0.5 Üst"}, {"state": "bitti", "ht": [1, 0], "ft": [2, 0]}, True),
        ({"market": "2. Yarı 1,5 Gol Alt/Üst", "sel": "1,5 Alt", "name": "2Y 1.5 Alt"}, {"state": "bitti", "ht": [2, 1], "ft": [2, 2]}, True),
        ({"market": "2. Yarı Karşılıklı Gol", "sel": "Yok", "name": "2Y KG Yok"}, {"state": "bitti", "ht": [1, 1], "ft": [2, 1]}, True),
        ({"market": "2. Yarı Karşılıklı Gol", "sel": "Var", "name": "2Y KG Var"}, {"state": "bitti", "ht": [1, 1], "ft": [2, 1]}, False),
        # 1Y BTTS graded on HT, not FT
        ({"market": "1. Yarı Karşılıklı Gol", "sel": "Var", "name": "İY KG Var"}, {"state": "bitti", "ht": [1, 0], "ft": [1, 1]}, False),
        ({"market": "1. Yarı Karşılıklı Gol", "sel": "Yok", "name": "İY KG Yok"}, {"state": "bitti", "ht": [1, 0], "ft": [1, 1]}, True),
        # Tek / Çift with half scope
        ({"market": "Toplam Gol Tek/Çift", "sel": "Çift", "name": "Çift"}, {"state": "bitti", "ht": [1, 0], "ft": [2, 0]}, True),
        ({"market": "1. Yarı Tek/Çift", "sel": "Tek", "name": "İY Tek"}, {"state": "bitti", "ht": [1, 0], "ft": [2, 0]}, True),
        ({"market": "1. Yarı Tek/Çift", "sel": "Çift", "name": "İY Çift"}, {"state": "bitti", "ht": [1, 0], "ft": [2, 0]}, False),
        # DEĞİL(...) negation
        ({"market": "Maç Sonucu", "sel": "", "name": "DEĞİL(MS 0)"}, {"state": "bitti", "ht": [0, 0], "ft": [1, 0]}, True),
        ({"market": "Maç Sonucu", "sel": "", "name": "DEĞİL(MS 0)"}, {"state": "bitti", "ht": [0, 0], "ft": [1, 1]}, False),
        # early_decide: Ev Sahibi 1,5 Üst with score 1-0 MUST be None (not True!)
        ({"market": "Ev Sahibi 1,5 Gol Alt/Üst", "sel": "1,5 Üst", "name": "Ev 1.5 Üst"}, {"state": "canlı", "score": [1, 0], "minute": 55}, None),
        ({"market": "Ev Sahibi 1,5 Gol Alt/Üst", "sel": "1,5 Üst", "name": "Ev 1.5 Üst"}, {"state": "canlı", "score": [2, 0], "minute": 55}, True),
        ({"market": "Ev Sahibi 0,5 Gol Alt/Üst", "sel": "0,5 Üst", "name": "Ev 0.5 Üst"}, {"state": "canlı", "score": [1, 0], "minute": 55}, True),
        # early_decide: 1. Yarı KG Var with HT 1-0 and live FT 1-1 MUST be False (decided at HT!)
        ({"market": "1. Yarı Karşılıklı Gol", "sel": "Var", "name": "İY KG Var"}, {"state": "canlı", "ht": [1, 0], "score": [1, 1], "minute": 60}, False),
    ],
)
def test_leg_grading_all_fixed_cases(leg, res, expected):
    assert lg.decide(leg, res) is expected


def test_gunluk_analiz_best_pick_prefers_clean_lower_vig_direct_over_heavy_vig_trap():
    ga = _load_script("gunluk_analiz")
    match = {
        "status": "fiyatlandı",
        "reference": "Pinnacle",
        "league": "İngiltere Premier Lig",
        "mu_home": 1.45,
        "mu_away": 0.90,
        "fair_1x2": [0.50, 0.27, 0.23],
        "selections": [
            # Heavy-vig derived selection (EV = -18.4%) with slightly higher raw fair_prob
            {
                "name": "İY 1.5 Alt",
                "market": "1. Yarı 1,5 Alt/Üst",
                "selection": "Alt",
                "fair_prob": 0.68,
                "odds": 1.20,
                "ev": -0.184,
                "direct": False,
            },
            # Clean direct selection with far lower Nesine vig (EV = -8.9%)
            {
                "name": "3.5 Alt",
                "market": "3,5 Gol Alt/Üst",
                "selection": "Alt",
                "fair_prob": 0.66,
                "odds": 1.38,
                "ev": -0.089,
                "direct": True,
            },
        ],
    }
    pick, _ = ga.best_pick(match)
    assert pick is not None
    assert pick["name"] == "3.5 Alt"


def test_kasa_koruma_rejects_stale_nonsharp_draws_and_banned_families(tmp_path, monkeypatch):
    kk = _load_script("kasa_koruma")
    monkeypatch.setattr(kk, "ai_area", lambda _root: tmp_path)
    day_dir = tmp_path / "2026-11-26"
    day_dir.mkdir(parents=True)
    now = dt.datetime.now(kk.TSI)
    future_ko = (now + dt.timedelta(hours=3)).isoformat()
    fresh_utc = (now - dt.timedelta(minutes=20)).astimezone(dt.timezone.utc).isoformat()
    stale_utc = (now - dt.timedelta(hours=10)).astimezone(dt.timezone.utc).isoformat()

    def make_match(code: int, ref: str, fetched: str, sel_name: str, odds: float, prob: float):
        return {
            "code": code,
            "home": f"H{code}",
            "away": f"A{code}",
            "league": "İspanya La Liga",
            "status": "fiyatlandı",
            "reference": ref,
            "ref_fetched_utc": fetched,
            "kickoff_iso": future_ko,
            "kickoff": "2026-11-26 21:00",
            "mu_home": 1.35,
            "mu_away": 0.90,
            "fair_1x2": [0.48, 0.28, 0.24],
            "selections": [
                {"name": sel_name, "odds": odds, "fair_prob": prob, "direct": True, "mbs": 1}
            ],
        }

    payload = {
        "matches": [
            # Valid sharp + fresh + allowed family (3 matches needed for 1 ticket of 3 legs)
            make_match(1, "Pinnacle", fresh_utc, "3.5 Alt", 1.32, 0.74),
            make_match(2, "Smarkets (borsa)", fresh_utc, "3.5 Alt", 1.34, 0.73),
            make_match(3, "Pinnacle", fresh_utc, "3.5 Alt", 1.35, 0.72),
            # Should be REJECTED: stale price (10h old)
            make_match(4, "Pinnacle", stale_utc, "3.5 Alt", 1.45, 0.76),
            # Should be REJECTED: non-sharp bookmaker
            make_match(5, "ESPN (DraftKings)", fresh_utc, "3.5 Alt", 1.45, 0.76),
            # Should be REJECTED: banned family KG Var
            make_match(6, "Pinnacle", fresh_utc, "KG Var", 1.45, 0.76),
            # Should be REJECTED: draw leg MS 0
            make_match(7, "Pinnacle", fresh_utc, "MS 0", 1.45, 0.76),
        ]
    }
    (day_dir / "nesine_global.json").write_text(json.dumps(payload), encoding="utf-8")

    plan, _, _ = kk.run("2026-11-26", bankroll_tl=1000.0, legs_per_ticket=3, min_ev=-0.10, min_p=0.60)
    assert len(plan.tickets) == 1
    chosen_ids = {lg_item.match_id for lg_item in plan.tickets[0].legs}
    assert chosen_ids == {"1", "2", "3"}


def test_market_diagnosis_catches_over35_traps():
    # Low total xG (< 3.45) must fail 3.5 Üst diagnosis
    low_xg = {"mu_home": 1.80, "mu_away": 1.30, "reference": "Pinnacle", "direct": True}
    d_low = diagnose_selection("3.5 Üst", 0.60, low_xg, for_coupon=True)
    assert not d_low.ok and d_low.residual_adjustment <= -0.05

    # Single-sided match (min_mu < 1.05, total < 3.85) must fail
    one_sided = {"mu_home": 2.75, "mu_away": 0.85, "reference": "Pinnacle", "direct": True}
    d_one = diagnose_selection("3.5 Üst", 0.60, one_sided, for_coupon=True)
    assert not d_one.ok

    # Genuine high-tempo two-sided match passes
    open_match = {"mu_home": 2.15, "mu_away": 1.65, "reference": "Pinnacle", "direct": True}
    d_ok = diagnose_selection("3.5 Üst", 0.62, open_match, for_coupon=True)
    assert d_ok.ok


def test_inplay_dixon_coles_draw_correlation_and_stability():
    # Dixon-Coles negative rho raises draw probability compared to independent Poisson (rho=0)
    g_ind = inplay._grid(1.3, 1.1, rho=0.0)
    g_dc = inplay._grid(1.3, 1.1, rho=inplay.DEFAULT_INPLAY_RHO)
    assert g_dc.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.trace(g_dc) > np.trace(g_ind)

    # final_probabilities exposes real double-chance keys summing cleanly
    p = inplay.final_probabilities(1.2, 1.0, 0, 0)
    assert p["ÇŞ 1X"] == pytest.approx(p["MS 1"] + p["MS X"], abs=1e-9)
    assert p["ÇŞ 12"] == pytest.approx(p["MS 1"] + p["MS 2"], abs=1e-9)
    assert p["ÇŞ X2"] == pytest.approx(p["MS X"] + p["MS 2"], abs=1e-9)

    # fit_lambdas remains finite and bounded even on extreme targets
    lh, la = inplay.fit_lambdas({"MS 1": 0.99, "MS X": 0.005, "MS 2": 0.005, "2.5 Üst": 0.98})
    assert 0.0 < la < lh < 20.0


def test_omni_markets_home_away_first_half_asymmetry():
    # Equal full-time expected goals preserve calibrated home > away 1H split
    bundle = compute_omni_markets(1.40, 1.40)
    assert bundle.ht_1x2["İY 1"] > bundle.ht_1x2["İY 2"]


def test_nesine_kupon_source_never_hardcodes_fake_guard_ok():
    src = (SCRIPTS / "nesine_kupon.py").read_text(encoding="utf-8")
    assert '"ok": True, "errors": []' not in src
