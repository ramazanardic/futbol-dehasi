"""Nesine coupon builder: exact optimum, Nesine-odds target, MBS rule, one leg per match."""

import importlib.util
from itertools import product
import math
from pathlib import Path
import random
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("nesine_kupon", SCRIPTS / "nesine_kupon.py")
kupon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kupon)


def _pools(seed: int, n_matches: int = 6, per_match: int = 3) -> list[list[dict]]:
    rng = random.Random(seed)
    pools = []
    for m in range(n_matches):
        legs = []
        for k in range(per_match):
            p = rng.uniform(0.35, 0.85)
            odds = round((1 / p) * rng.uniform(0.75, 0.95), 2)  # Nesine pays below fair (margin)
            legs.append({"code": m, "kickoff": f"2026-11-19 {12 + m}:00", "odds": max(odds, 1.16), "p": p,
                         "mbs": rng.choice([1, 2, 3]), "ev": 0.0})
        pools.append(legs)
    return pools


def _brute(pools, target, max_legs):
    best = None
    for choice in product(*[[None] + pool for pool in pools]):
        legs = [x for x in choice if x is not None]
        if not legs or len(legs) > max_legs or len(legs) < max(x["mbs"] for x in legs):
            continue
        if math.prod(x["odds"] for x in legs) < target:
            continue
        lp = sum(math.log(x["p"]) for x in legs)
        if best is None or lp > best + 1e-12:
            best = lp
    return best


@pytest.mark.parametrize("seed", range(8))
@pytest.mark.parametrize("target", [3.0, 6.0])
def test_dp_matches_brute_force(seed, target):
    pools = _pools(seed)
    c = kupon.best_coupon(pools, target, max_legs=5)
    ref = _brute(pools, target, 5)
    if ref is None:
        assert c is None
        return
    assert c is not None
    assert c["nesine_odds"] >= target - 1e-9
    assert len({leg["code"] for leg in c["legs"]}) == len(c["legs"])  # one leg per match
    assert len(c["legs"]) >= max(leg["mbs"] for leg in c["legs"])  # MBS
    # Log-odds bucketing may lose at most a sliver of optimality.
    assert math.log(c["probability"]) == pytest.approx(ref, abs=0.03)


@pytest.mark.parametrize("seed", range(4))
def test_min_legs_is_respected(seed):
    pools = _pools(seed)
    c = kupon.best_coupon(pools, 3.0, max_legs=5, min_legs=4)
    if c is not None:
        assert len(c["legs"]) >= 4
        assert c["nesine_odds"] >= 3.0 - 1e-9
        free = kupon.best_coupon(pools, 3.0, max_legs=5)
        assert c["probability"] <= free["probability"] + 1e-12  # a constraint cannot raise the optimum


def test_candidates_keep_only_non_dominated_legs():
    import datetime as dt

    now = dt.datetime(2026, 11, 19, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    match = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-19T20:00:00+03:00",
             "kickoff": "2026-11-19 20:00", "code": 1, "league": "L", "home": "A", "away": "B",
             "selections": [
                 {"market": "MS", "selection": "1", "odds": 1.50, "fair_prob": 0.60, "ev": -0.10, "mbs": 1},
                 {"market": "ÇŞ", "selection": "1-X", "odds": 1.20, "fair_prob": 0.55, "ev": -0.34, "mbs": 1},  # dominated
                 {"market": "AÜ", "selection": "Üst", "odds": 1.90, "fair_prob": 0.50, "ev": -0.05, "mbs": 1},
                 {"market": "X", "selection": "?", "odds": 5.0, "fair_prob": 0.40, "ev": 1.0, "mbs": 1},  # implausible EV
             ]}
    espn = dict(match, code=2, reference="ESPN (DraftKings/ESPN BET)")
    pools = kupon.candidates([match, espn], now, min_odds=1.15, min_prob=0.0, allow_espn=False)
    assert len(pools) == 1
    assert {(leg["market"], leg["odds"]) for leg in pools[0]} == {("MS", 1.50), ("AÜ", 1.90)}
    complete = kupon.candidates([match, espn], now, min_odds=1.15, min_prob=0.0, allow_espn=False, keep_all=True)
    assert {(leg["market"], leg["odds"]) for leg in complete[0]} == {("MS", 1.50), ("ÇŞ", 1.20), ("AÜ", 1.90)}



def test_direct_quote_names_map_to_nesine_selections():
    import nesine_global as ng

    assert ng._direct_name("Over/under 3.5", "OVER|Over 3.5 goals") == "3.5 Üst"
    assert ng._direct_name("Both teams to score", "NO|No") == "KG Yok"
    assert ng._direct_name("First half over/under 0.5", "UNDER|Under 0.5 goals") == "İY 0.5 Alt"
    assert ng._direct_name("Half-time/full-time", "DRAW_HOME|Draw / Amiens") == "İY/MS 0/1"
    assert ng._direct_name("Winner and over/under 1.5", "HOME_OVER|Amiens / over 1.5 goals") == "MS 1 & 1.5 Üst"
    assert ng._direct_name("Both teams to score and over/under 2.5", "YES_UNDER|Yes / Under") == "2.5 Alt & KG Var"
    assert ng._direct_name("Goal range", "RANGE|2 - 3") == "2-3 Gol"
    assert ng._direct_name("Goal range", "RANGE|4 - 6") is None  # Nesine's 4-5 band is a different event
    assert ng._direct_name("Correct score", "X|1-0") is None


def test_two_exchange_consensus_averages_probabilities():
    import nesine_global as ng

    a = {"source": "Smarkets (borsa)", "x12": [2.0, 4.0, 4.0], "ou": [2.5, [2.0, 2.0]], "markets": {"m": {}}, "fetched_utc": "2026-11-19T07:00:00+00:00"}
    b = {"source": "Matchbook (borsa)", "x12": [1 / 0.44, 4.0, 1 / 0.31], "ou": [2.5, [1.8, 2.25]], "fetched_utc": "2026-11-19T08:00:00+00:00"}
    c = ng.consensus(a, b)
    assert c["source"] == "Matchbook + Smarkets (borsa)"
    p = [1 / x for x in c["x12"]]
    assert sum(p) == pytest.approx(1.0, abs=1e-3)
    assert p[0] == pytest.approx((0.5 + 0.44) / 2, abs=1e-3)
    assert c["consensus_gap"] == pytest.approx(0.06, abs=1e-3)
    assert c["markets"] == {"m": {}} and c["fetched_utc"].startswith("2026-11-19T07")  # older fetch time is the honest one


def test_contradicting_exchanges_are_not_priced():
    import nesine_global as ng

    a = {"source": "Smarkets (borsa)", "x12": [2.0, 4.0, 4.0], "ou": [2.5, [2.0, 2.0]]}
    b = {"source": "Matchbook (borsa)", "x12": [2.0, 4.0, 4.0], "ou": [2.5, [8.0, 1 / 0.875]]}  # wrong market read as O/U
    assert ng.consensus(a, b)["ou"] is None  # contradictory totals are dropped, 1X2 still averaged
    c = {"source": "Matchbook (borsa)", "x12": [4.0, 4.0, 2.0]}
    assert ng.consensus(a, c) is None


def test_wrong_pairing_is_rejected_and_each_reference_used_once():
    import datetime as dt
    from types import SimpleNamespace

    import nesine_global as ng

    ko = dt.datetime(2026, 11, 19, 16, 0, tzinfo=dt.timezone.utc)

    def ev(code, home, away, ms, hours=0):
        odds = dict(zip(("MS 1", "MS 0", "MS 2"), ms))
        return SimpleNamespace(code=code, home=home, away=away, kickoff=ko + dt.timedelta(hours=hours), odds_of=odds.get)

    salt = ev(1, "AL Salt", "Al Yarmouk", (1.29, 3.62, 5.46))
    ahli = ev(2, "AL Ahli Doha", "AL Shamal", (2.69, 3.32, 1.79), hours=2.5)
    ref = {"home": "Al-Ahli", "away": "Al-Shamal", "kickoff": ahli.kickoff, "x12": [3.19, 4.21, 2.23]}
    assert not ng._consistent(salt, ref)  # Nesine says ~70% home, the reference says ~31%
    assert ng._consistent(ahli, ref)
    assert ng._owners([salt, ahli], [ref])[id(ref)] == 2


def test_safest_first_adds_surest_matches_until_target():
    pools = [[{"code": i, "kickoff": f"2026-11-19 {10 + i}:00", "odds": o, "p": p, "mbs": 1}] for i, (o, p) in
             enumerate([(1.30, 0.80), (1.20, 0.90), (1.50, 0.65), (2.00, 0.50), (1.25, 0.85)])]
    c = kupon.safest_first_coupon(pools, 2.0, max_legs=10)
    probs = sorted(leg["p"] for leg in c["legs"])
    assert probs == [0.65, 0.80, 0.85, 0.90]  # surest first: 0.90, 0.85, 0.80, then 0.65 crosses 2.0
    assert c["nesine_odds"] >= 2.0
    assert kupon.safest_first_coupon(pools, 2.0, max_legs=3) is None
    mbs3 = [[dict(pools[1][0], mbs=3)], pools[3]]
    assert kupon.safest_first_coupon(mbs3, 1.1, max_legs=5) is None  # 2 legs cannot satisfy MBS 3


def test_lagging_nesine_price_is_detected():
    import datetime as dt

    import nesine_global as ng

    earlier = (dt.datetime.now(ng.TSI) - dt.timedelta(hours=2)).isoformat(timespec="seconds")
    history = [{"ts": earlier, "m": {"7": {"ref_t": "2026-11-19T08:00:00+00:00",
                                          "s": {"KG Var": [1.80, 0.50], "MS 1": [2.10, 0.45], "2.5 Üst": [1.90, 0.50]}}}}]
    match = {"status": "fiyatlandı", "code": 7, "ref_fetched_utc": "2026-11-19T11:00:00+00:00", "selections": [
        {"name": "KG Var", "odds": 1.80, "fair_prob": 0.56, "direct": True},   # exchange +6 pts, Nesine unchanged -> hit
        {"name": "MS 1", "odds": 1.95, "fair_prob": 0.52, "direct": True},     # Nesine already moved
        {"name": "2.5 Üst", "odds": 1.90, "fair_prob": 0.51, "direct": True},  # move below 3 pts
    ]}
    hits = ng.lagging_selections(history, [match])
    assert [(s["name"], round(p0, 2)) for _, s, p0, _ in hits] == [("KG Var", 0.50)]
    same_snapshot = dict(match, ref_fetched_utc="2026-11-19T08:00:00+00:00")
    assert ng.lagging_selections(history, [same_snapshot]) == []


def test_user_absence_file_is_read_by_nesine_code(tmp_path):
    import json

    import nesine_global as ng

    (tmp_path / "haftalik_sakatlik_ceza_x.json").write_text(json.dumps({"generated_tsi": "2026-11-19T11:50:19+03:00", "matches": [
        {"code": 11, "absences": {"covered": True, "home": {"injuries": [{"player": "A"}], "cards": []}, "alerts": ["x"]}},
        {"code": 12, "absences": {"covered": False}}]}), encoding="utf-8")
    data, src = ng.load_user_absences(tmp_path)
    assert set(data) == {11} and data[11]["home"]["injuries"][0]["player"] == "A"
    assert src.startswith("haftalik_sakatlik_ceza_x.json (2026-11-19 11:50")
    assert ng.load_user_absences(tmp_path / "none") == ({}, None)


def test_model_htft_legs_are_excluded_but_direct_ones_kept():
    import datetime as dt

    now = dt.datetime(2026, 11, 19, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    m = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-19T20:00:00+03:00",
         "kickoff": "2026-11-19 20:00", "code": 1, "league": "L", "home": "A", "away": "B", "selections": [
             {"market": "İY/MS", "selection": "1/1", "name": "İY/MS 1/1", "odds": 3.0, "fair_prob": 0.30, "ev": -0.1, "mbs": 1, "direct": False},
             {"market": "İY/MS", "selection": "2/2", "name": "İY/MS 2/2", "odds": 6.0, "fair_prob": 0.18, "ev": 0.08, "mbs": 1, "direct": True}]}
    legs = kupon.candidates([m], now, 1.2, 0.0, False)[0]
    assert [leg["selection"] for leg in legs] == ["2/2"]
    # İY/MS is a "hard" market (22 Nov post-mortem): a direct quote without a +3 % margin stays out, but is not banned
    m["selections"][1].update(fair_prob=0.15, ev=-0.1)
    assert kupon.candidates([m], now, 1.2, 0.0, False) == []


def test_stale_global_price_is_kept_out_of_coupons():
    import datetime as dt

    now = dt.datetime(2026, 11, 19, 19, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))  # 16:00 UTC
    leg = {"market": "MS", "selection": "1", "name": "MS 1", "odds": 1.5, "fair_prob": 0.7, "ev": 0.05, "mbs": 1, "direct": True}
    base = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-19T22:00:00+03:00",
            "kickoff": "2026-11-19 22:00", "code": 1, "league": "L", "home": "A", "away": "B", "selections": [leg]}
    fresh = dict(base, ref_fetched_utc="2026-11-19T14:30:00+00:00")  # 1.5 h old
    stale = dict(base, code=2, ref_fetched_utc="2026-11-19T12:30:00+00:00")  # 3.5 h old
    pools = kupon.candidates([fresh, stale], now, 1.2, 0.0, False)
    assert [p[0]["code"] for p in pools] == [1]


def test_safest_first_partial_when_target_unreachable():
    pools = [[{"code": i, "kickoff": f"2026-11-19 {10 + i}:00", "odds": 1.3, "p": 0.7, "mbs": 1}] for i in range(3)]
    assert kupon.safest_first_coupon(pools, 50.0, max_legs=10) is None
    c = kupon.safest_first_coupon(pools, 50.0, max_legs=10, partial=True)
    assert c["reached"] is False and len(c["legs"]) == 3


def test_recheck_odds_updates_changed_and_flags_missing(monkeypatch):
    from types import SimpleNamespace

    sel = lambda mid, name, odds: SimpleNamespace(market_id=mid, name=name, negate=False, odds=odds)  # noqa: E731
    events = [SimpleNamespace(code=1, selections=[sel(1, "MS 1", 1.50), sel(2, "2.5 Üst", 1.80)])]
    monkeypatch.setattr(kupon, "fetch_bulletin", lambda: None)
    monkeypatch.setattr(kupon, "parse_bulletin", lambda payload: events)
    coupon = {"legs": [{"code": 1, "match": "A - B", "selection": "1", "key": "1|MS 1|0", "odds": 1.45},
                       {"code": 1, "match": "A - B", "selection": "Üst", "key": "2|2.5 Üst|0", "odds": 1.80},
                       {"code": 2, "match": "C - D", "selection": "X", "key": "1|MS 0|0", "odds": 3.0}]}
    notes = kupon.recheck_odds([coupon])
    assert [leg["status"] for leg in coupon["legs"]] == ["oran değişti", "kontrol edildi", "bültende yok / askıda"]
    assert coupon["legs"][0]["odds"] == 1.50 and coupon["nesine_odds"] == 0.0
    assert len(notes) == 2


def test_builder_preserves_saved_coupon_when_research_or_live_check_fails(tmp_path, monkeypatch):
    import datetime as dt

    now = dt.datetime.now(kupon.TSI)
    day = now.date().isoformat()
    saved = tmp_path / day / f"kupon_5x_{now:%H%M}.json"
    saved.parent.mkdir()
    saved.write_text('{"coupons": ["saved"]}')
    matches = [{"code": 1, "status": "fiyatlandı", "kickoff_iso": (now + dt.timedelta(hours=1)).isoformat()}]
    leg = {"code": 1, "key": "k", "match": "A - B", "selection": "1", "odds": 6.0}
    monkeypatch.setattr(kupon, "AI_AREA", tmp_path)
    monkeypatch.setattr(kupon, "analyze_day", lambda *a, **kw: (matches, {}, []))
    monkeypatch.setattr(kupon, "load_live_calibration", lambda: {})
    monkeypatch.setattr(kupon, "candidates", lambda *a, **kw: [[leg]])
    monkeypatch.setattr(kupon, "filter_pools_for_mode", lambda pools, policy: pools)
    monkeypatch.setattr(kupon, "best_coupon", lambda *a, **kw: {"legs": [dict(leg)]})
    monkeypatch.setattr(kupon, "read_bulletin_odds", lambda: ({}, {}))
    options = ["--hedef", "5", "--tarih", day, "--no-pull", "--adet", "1"]
    assert kupon.main(options, review=lambda legs, match_data: False) is None
    assert kupon.main(options) is None
    assert list(saved.parent.iterdir()) == [saved]
    assert saved.read_text() == '{"coupons": ["saved"]}'


def test_corner_quotes_map_and_are_direct_only():
    import nesine_global as ng

    assert ng._direct_name("Over/under 9.5 corners", "OVER|Over 9.5 corners") == "Korner 9.5 Üst"
    assert ng._direct_name("First half over/under 4.5 corners", "UNDER|Under 4.5 corners") == "İY Korner 4.5 Alt"
    assert ng._direct_name("First half over/under 1.5", "OVER|Over 1.5 goals") == "İY 1.5 Üst"


def test_nesine_only_estimates_never_enter_coupons():
    import datetime as dt
    from types import SimpleNamespace

    import nesine_global as ng

    odds = {"MS 1": 2.0, "MS 0": 3.3, "MS 2": 3.6, "2.5 Üst": 1.9, "2.5 Alt": 1.85}
    ref = ng.nesine_fallback_reference(SimpleNamespace(odds_of=odds.get))
    assert ref["x12"] == [2.0, 3.3, 3.6] and ref["ou"] == [2.5, [1.9, 1.85]]
    assert ng.nesine_fallback_reference(SimpleNamespace(odds_of={"MS 1": 2.0}.get)) is None
    now = dt.datetime(2026, 11, 19, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    m = {"status": ng.NESINE_ONLY_STATUS, "reference": "Nesine (yerel, düşük güven)", "kickoff_iso": "2026-11-19T20:00:00+03:00",
         "kickoff": "2026-11-19 20:00", "code": 1, "league": "L", "home": "A", "away": "B",
         "selections": [{"market": "MS", "selection": "1", "name": "MS 1", "odds": 2.0, "fair_prob": 0.46, "ev": -0.08, "mbs": 1}]}
    assert kupon.candidates([m], now, 1.2, 0.0, True) == []


def test_compatibility_and_reliability_ordering():
    assert kupon.compatible("ÇŞ 12", "MS 1")
    assert not kupon.compatible("ÇŞ 12", "İY Skor 0-0 & Skor 0-0")
    assert not kupon.compatible("İY 0.5 Üst", "İY Skor 0-0 & Skor 0-0")
    assert kupon.compatible("İY 0.5 Üst", "İY Skor 1-0 & Skor 1-0")
    assert not kupon.compatible("2.5 Üst", "2.5 Alt")
    a = {"code": 1, "key": "k1", "name": "ÇŞ 12"}
    pools = [[{"code": 1, "key": "k2", "name": "İY Skor 0-0 & Skor 0-0"}, {"code": 1, "key": "k3", "name": "İY Skor 0-0 & Skor 1-0"}],
             [{"code": 2, "key": "k1", "name": "MS 1"}]]
    left = kupon.drop_conflicts(pools, [a])
    assert [x["key"] for x in left[0]] == ["k3"] and left[1][0]["key"] == "k1"  # other match untouched
    # a direct exchange quote at 68 % beats a model half-market at 70 %
    d = kupon.leg_sigma("2.5 Üst", True, "Matchbook + Smarkets (borsa)", True, False)
    mdl = kupon.leg_sigma("2Y KG Yok", False, "Matchbook + Smarkets (borsa)", True, False)
    assert 0.68 - kupon.Z_LOW * d > 0.70 - kupon.Z_LOW * mdl


def test_consistent_scores_never_contradict_the_leg():
    import numpy as np

    j = np.zeros((2, 2, 2, 2))
    j[1, 0, 0, 0] = 0.4  # FT 1-0 (most likely score overall)
    j[0, 0, 1, 1] = 0.3  # FT 1-1
    j[0, 1, 0, 1] = 0.3  # FT 0-2
    assert kupon.consistent_scores(j, "KG Var") == [("1-1", 0.3)]
    assert [s for s, _ in kupon.consistent_scores(j, "KG Yok")] == ["1-0", "0-2"]
    assert kupon.consistent_scores(j, "DEĞİL(KG Var)") == kupon.consistent_scores(j, "KG Yok")


def test_consensus_merges_both_exchange_direct_markets_and_drops_contradictions():
    import nesine_global as ng

    mb = {
        "source": "Matchbook (borsa)",
        "x12": [2.0, 3.6, 3.8],
        "ou": [2.5, [1.9, 1.95]],
        "markets": {"Both teams to score": {"YES|Yes": 0.54, "NO|No": 0.46}},
    }
    sm = {
        "source": "Smarkets (borsa)",
        "x12": [2.05, 3.55, 3.75],
        "ou": [2.5, [1.92, 1.93]],
        "markets": {
            "Both teams to score": {"YES|Yes": 0.56, "NO|No": 0.44},
            "Over/under 3.5": {"OVER|Over 3.5 goals": 0.31},
            "Over/under 1.5": {"OVER|Over 1.5 goals": 0.78},
        },
    }
    c = ng.consensus(mb, sm)
    assert c is not None
    assert c["markets"]["Both teams to score"]["YES|Yes"] == pytest.approx(0.55, abs=1e-4)
    assert c["markets"]["Over/under 3.5"]["OVER|Over 3.5 goals"] == pytest.approx(0.31)
    assert c["markets"]["Over/under 1.5"]["OVER|Over 1.5 goals"] == pytest.approx(0.78)


def test_price_event_uses_exact_1x2_for_double_chance_and_multi_line_btts_fit():
    from types import SimpleNamespace
    import nesine_global as ng
    from quantfoot.markets.devig import devig

    sels = [
        SimpleNamespace(market_id=1, market_title="MS", label="1", name="MS 1", odds=1.40, negate=False, mbs=1),
        SimpleNamespace(market_id=1, market_title="MS", label="X", name="MS 0", odds=4.20, negate=False, mbs=1),
        SimpleNamespace(market_id=1, market_title="MS", label="2", name="MS 2", odds=6.50, negate=False, mbs=1),
        SimpleNamespace(market_id=2, market_title="ÇŞ", label="1-X", name="ÇŞ 10", odds=1.10, negate=False, mbs=1),
        SimpleNamespace(market_id=3, market_title="KG", label="Yok", name="KG Yok", odds=1.55, negate=False, mbs=1),
    ]
    ev = SimpleNamespace(
        code=999999,
        selections=sels,
        odds_of=lambda n: next((s.odds for s in sels if s.name == n), None),
    )
    ref = {
        "source": "Matchbook + Smarkets (borsa)",
        "x12": [1.50, 4.40, 6.80],
        "ou": [2.5, [1.55, 2.50]],
        "markets": {
            "Over/under 3.5": {"OVER|Over 3.5 goals": 0.42},
            "Both teams to score": {"YES|Yes": 0.48, "NO|No": 0.52},
        },
    }
    priced = ng.price_event(ev, ref, "BAE Arap Körfez Ligi")
    by_name = {r["name"]: r for r in priced["selections"]}
    p1x2 = devig(ref["x12"], method="power").probabilities
    assert by_name["MS 1"]["direct"] is True
    assert by_name["MS 1"]["fair_prob"] == pytest.approx(float(p1x2[0]), abs=1e-4)
    assert by_name["ÇŞ 10"]["direct"] is True
    assert by_name["ÇŞ 10"]["fair_prob"] == pytest.approx(float(p1x2[0] + p1x2[1]), abs=1e-4)
    assert by_name["KG Yok"]["direct"] is True
    assert by_name["KG Yok"]["fair_prob"] == pytest.approx(0.52, abs=1e-4)


def test_drop_conflicts_blocks_directional_double_chance_hedges():
    a = {"code": 10, "key": "k1", "name": "ÇŞ 10"}
    pools = [[
        {"code": 10, "key": "k2", "name": "ÇŞ 02"},
        {"code": 10, "key": "k3", "name": "MS 2"},
        {"code": 10, "key": "k4", "name": "2.5 Üst"},
    ]]
    left = kupon.drop_conflicts(pools, [a])
    assert [x["name"] for x in left[0]] == ["2.5 Üst"]



def test_model_second_half_result_legs_are_excluded():
    import datetime as dt

    now = dt.datetime(2026, 11, 19, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    m = {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-19T20:00:00+03:00",
         "kickoff": "2026-11-19 20:00", "code": 1, "league": "L", "home": "A", "away": "B", "selections": [
             {"market": "2. Yarı Sonucu", "selection": "1", "name": "2Y 1", "odds": 1.6, "fair_prob": 0.58, "ev": -0.1, "mbs": 1, "direct": False},
             {"market": "2. Yarı Sonucu", "selection": "2", "name": "2Y 2", "odds": 1.7, "fair_prob": 0.57, "ev": -0.1, "mbs": 1, "direct": True}]}
    legs = kupon.candidates([m], now, 1.2, 0.0, False)[0]
    assert [leg["name"] for leg in legs] == ["2Y 2"]


def test_renamed_reserve_team_pairs_on_same_kickoff_only():
    import datetime as dt

    import nesine_global as ng

    ko = dt.datetime(2026, 11, 20, 20, 30, tzinfo=dt.timezone.utc)
    ev = type("E", (), {"home": "R. Wien (Amt)", "away": "Blau Weiss L.", "kickoff": ko})
    ref = {"home": "SK Rapid II", "away": "FC Blau-Weiss Linz", "kickoff": ko}
    assert ng._match(ev, [ref])[0] is ref
    late = dict(ref, kickoff=ko + dt.timedelta(hours=2))
    assert ng._match(ev, [late])[0] is None  # weak name match only accepted at the same kick-off


def test_v4_nesine_kupon_passes_flags_enforces_banko_min_ev_and_attaches_insured_system():
    import datetime as dt

    now = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    m_steam = {
        "status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-23T20:00:00+03:00",
        "kickoff": "2026-11-23 20:00", "code": 501, "league": "İspanya La Liga", "home": "A", "away": "B",
        "mu_home": 2.0, "mu_away": 0.7, "fair_1x2": [0.74, 0.17, 0.09],
        "research": {"flags": ["Sharp steam +6.8p"]},
        "selections": [{"name": "MS 1", "market": "Maç Sonucu", "selection": "1", "odds": 1.32, "fair_prob": 0.74, "ev": -0.023, "mbs": 1, "direct": True}],
    }
    pools = kupon.candidates([m_steam], now, min_odds=1.20, min_prob=0.60, allow_espn=False, keep_all=True)
    assert pools and pools[0][0]["flags"] == ["Sharp steam +6.8p"]
    assert pools[0][0]["diagnosis_ok"] is False  # sert steam kalkanı nesine_kupon içinde de aktif!

    # EV marj freni: -%14 EV'li 1.20 bacak elenir, -%2 EV'li 1.32 bacak geçer
    test_pools = [[
        {"code": 1, "match": "X - Y", "name": "MS 1", "odds": 1.20, "p": 0.73, "p_low": 0.71, "mbs": 1},
        {"code": 1, "match": "X - Y", "name": "3.5 Alt", "odds": 1.32, "p": 0.76, "p_low": 0.74, "mbs": 1},
    ]]
    filtered = kupon.apply_coupon_rules_to_pools(test_pools, "banko", min_ev=-0.115)
    assert len(filtered) == 1 and [x["name"] for x in filtered[0]] == ["3.5 Alt"]

    # Tek-bacak sigorta eklentisi (5 maç -> Sistem 4,5)
    sample_coupon = {
        "legs": [{"code": i, "match": f"M{i}", "name": "3.5 Alt", "odds": 1.32, "p": 0.74, "mbs": 1} for i in range(5)],
        "nesine_odds": round(1.32 ** 5, 2),
        "probability": 0.74 ** 5,
    }
    ins = kupon.attach_insured_system(sample_coupon, budget_tl=100.0)
    assert ins is not None and min(ins["sizes"]) == 4
    assert ins["p_at_least_n_minus_1"] > ins["p_all"] + 0.30
    assert ins["one_miss_payout_range"][0] > 40.0



def test_final_guard_probability_is_published_and_traceable(monkeypatch):
    """Builder may be optimistic; the last guard MUST own the displayed coupon P/EV."""
    from quantfoot.strategy.banko_guard import GuardResult

    monkeypatch.setattr(kupon.KM, "guard_legs", lambda *_args, **_kw:
                        GuardResult(ok=True, p_win=0.42, total_odds=2.40))
    monkeypatch.setattr(kupon.KM, "leg_effective_prob", lambda *_args: 0.70)
    coupon = {"legs": [{"code": 42, "name": "MS 1", "odds": 1.50, "p_raw": 0.82,
                        "p_before_rules": 0.79, "p": 0.74}],
              "nesine_odds": 2.40, "probability": 0.58, "probability_low": 0.45,
              "ev": 0.392}
    kept, notes = kupon.apply_mode_guard([coupon], "banko")
    assert kept == [coupon] and not notes
    assert coupon["probability_before_guard"] == 0.58
    assert coupon["probability"] == 0.42
    assert coupon["probability_low"] == 0.42
    assert coupon["ev"] == pytest.approx(0.42 * 2.40 - 1)
    trace = coupon["legs"][0]["probability_trace"]
    assert trace == {"market_raw": 0.82, "market_and_history_calibrated": 0.79,
                     "coupon_rules": 0.74, "guard_final": 0.70}
