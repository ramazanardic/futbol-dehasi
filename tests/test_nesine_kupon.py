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
             {"market": "İY/MS", "selection": "2/2", "name": "İY/MS 2/2", "odds": 6.0, "fair_prob": 0.15, "ev": -0.1, "mbs": 1, "direct": True}]}
    legs = kupon.candidates([m], now, 1.2, 0.0, False)[0]
    assert [leg["selection"] for leg in legs] == ["2/2"]


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
    assert coupon["legs"][0]["odds"] == 1.50 and coupon["nesine_odds"] == round(1.50 * 1.80, 2)
    assert len(notes) == 2
