"""scripts/derin_tahmin.py and scripts/wiki_gecmis.py (deep-researched daily picks, Wikipedia season history)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_candidates_direct_only_and_thresholds():
    dt_ = _load("derin_tahmin")
    sel = lambda n, p, o, d=True: {"name": n, "market": "M", "selection": n, "fair_prob": p, "odds": o, "direct": d}  # noqa: E731
    m = {"status": "fiyatlandı", "reference": "OddsMath (BetInAsia/Pinnacle)", "selections": [sel("a", 0.70, 1.30), sel("b", 0.80, 1.15), sel("c", 0.75, 1.40, False), sel("d", 0.54, 1.80),
                        sel("e", 0.60, 1.50)]}
    assert [c["name"] for c in dt_.candidates(m, 5, calibration={})] == ["a", "e"]   # odds < 1.20, model-derived and p < 55 % left out


def test_choose_skips_warned_legs_and_picks_by_value():
    dt_ = _load("derin_tahmin")
    legs = [{"p": 0.7, "odds": 1.80, "verdict": "⚠ geçmiş desteklemiyor"},      # best EV but history contradicts -> out
            {"p": 0.6, "odds": 1.75, "verdict": "geçmiş yetersiz"},             # EV +0.05
            {"p": 0.65, "odds": 1.50, "verdict": "✓ geçmiş destekliyor"}]       # EV -0.025 (most probable survivor)
    assert dt_.choose(legs)["p"] == 0.6                                          # value decides, evidence filters
    assert dt_.choose([legs[0]]) is None
    assert dt_.choose([legs[2]]) is None                                         # most probable but negative value -> no pick
    eq = [{"p": 0.6, "odds": 1.75, "verdict": "geçmiş yetersiz"}, {"p": 0.6, "odds": 1.75, "verdict": "✓ geçmiş destekliyor"}]
    assert dt_.choose(eq)["verdict"].startswith("✓")                             # equal value: better evidence first
    assert dt_.choose([legs[1]], min_ev=0.06) is None


def test_window_crosses_midnight_and_is_validated():
    import argparse
    import pytest
    dt_ = _load("derin_tahmin")
    assert dt_.in_window("2026-11-21 23:30", "22:00-02:00") and dt_.in_window("2026-11-22 01:15", "22:00-02:00")
    assert not dt_.in_window("2026-11-21 12:00", "22:00-02:00") and dt_.in_window("2026-11-22 02:00", "22:00-02:00")
    for bad in ("6-10", "06:00", "25:00-26:00", "06:00–10:00", "06:60-07:00"):
        with pytest.raises(argparse.ArgumentTypeError):
            dt_.parse_window(bad)


def test_results_matrix_and_crosstable():
    wg = _load("wiki_gecmis")
    en = "|name_ABC = [[Alpha FC]]\n|name_DEF = [[Delta United|Delta]]\n|match_ABC_DEF = 2–1\n|match_DEF_ABC = [[x|0–0]]\n|match_ABC_XYZ = \n"
    names, games = wg.results_matrix(en)
    assert names == {"ABC": "Alpha FC", "DEF": "Delta"}
    assert games == [("ABC", "DEF", 2, 1), ("DEF", "ABC", 0, 0)]
    de = ("=== Kreuztabelle ===\n{| class=\"wikitable\"\n|-\n! 2026/27\n! [[Datei:a.svg|22px|Alpha]]\n! [[Datei:b.svg|22px|Beta]]\n"
          "|-\n| style=\"text-align: left;\" | [[Alpha]]\n| class=\"h\" | || 3:1\n"
          "|-\n| style=\"text-align: left;\" | [[Beta]]\n| : || class=\"h\" |\n|}")
    names, games = wg.crosstable(de)
    assert names == {"0": "Alpha", "1": "Beta"} and games == [("0", "1", 3, 1)]   # unplayed ":" cells skipped


def test_match_team_alias_and_fuzzy():
    wg = _load("wiki_gecmis")
    names = {"A": "SK Rapid II", "B": "Austria Wien II", "C": "Auckland City", "D": "Lokomotiv Plovdiv"}
    assert wg.match_team("R. Wien (Amt)", names) == "A"      # alias beats the fuzzy match
    assert wg.match_team("Auckland", names) is None          # alias None: never guess
    assert wg.match_team("Loko Plovdiv", names) == "D"
    assert wg.match_team("Completely Different", names) is None


def test_wiki_leg_history_full_time_only():
    wg = _load("wiki_gecmis")
    names = {"H": "Home", "A": "Away", "X": "Other"}
    games = [("H", "X", 2, 0), ("H", "X", 0, 1), ("X", "A", 1, 1), ("X", "A", 3, 0), ("A", "X", 5, 5)]
    hg, ag = wg.team_games("H", names, games), wg.team_games("A", names, games)
    hist = wg.leg_history("2.5 Alt", hg, ag)     # home team's home games, away team's away games only
    assert (hist["home_n"], hist["away_n"]) == (2, 2) and hist["home_rate"] == 1.0 and hist["away_rate"] == 0.5
    assert wg.leg_history("İY 0.5 Üst", hg, ag)["mean"] is None   # no half-time scores on Wikipedia
    assert wg.verdict(0.7, hist) == "geçmiş yetersiz"        # fewer than 4 home / 4 away games


def test_simulation_matches_poisson_and_judges_three_views():
    sim = _load("simulasyon")
    from quantfoot.markets.goal_markets import goal_probability
    joint, top = sim.simulate(1.5, 1.0, 40000, seed=1)
    import math
    p_under = sum(math.exp(-2.5) * 2.5 ** k / math.factorial(k) for k in range(3))   # total ~ Poisson(2.5)
    assert abs(goal_probability("2.5 Alt", joint) - p_under) < 0.01
    assert abs(joint.sum() - 1) < 1e-9 and len(top) == 5
    assert sim.judge(0.65, 0.66, 0.70)[0] == "üçlü onay"
    assert sim.judge(0.65, 0.50, 0.70)[0] == "çelişki"
    assert sim.judge(0.65, 0.62, None)[0] == "eksik kanıt"
    assert sim.history({"verdict": "✓ geçmiş destekliyor", "mean": 0.70, "web": "son 6+6 maç %58"}) - 0.64 < 1e-9
    assert sim.history({"verdict": "geçmiş yetersiz", "mean": None}) is None
    # insufficient history: neither a stored rate nor a free-text note may stand in for it (22 Nov audit)
    assert sim.history({"verdict": "geçmiş yetersiz", "mean": 0.9, "web": "son 6+6 maç %80"}) is None


def test_simulation_main_pick_by_value_among_triple_confirmed():
    sim = _load("simulasyon")
    bets = [{"label": "A", "verdict": "üçlü onay", "market": 0.70, "odds": 1.40, "low": 0.68},   # EV -0.02
            {"label": "B", "verdict": "üçlü onay", "market": 0.60, "odds": 1.75, "low": 0.58},   # EV +0.05
            {"label": "C", "verdict": "kısmi onay", "market": 0.60, "odds": 2.00, "low": 0.50}]  # best EV, not confirmed
    assert sim.best_value_bet(bets)["label"] == "B"
    assert sim.best_value_bet(bets[:1]) is None

def test_simulation_rates_blend_form_and_absences():
    sim = _load("simulasyon")
    row = {"teams": {"home": {"gf": 2.0, "ga": 1.0, "n": 10, "top_scorer_out": True}, "away": {"gf": 1.0, "ga": 2.0, "n": 10}}}
    m = {"mu_home": 1.5, "mu_away": 1.0, "research": {"flags": ["Dep: düzenli kaleci ilk 11'de yok"]}}
    mh, ma, why = sim.rates(row, m, {"xg": [1.0, 1.0]})   # market xG is NOT used: league model and form only
    assert abs(mh - (1.0 + 2.0) / 2 * 0.92 * 1.08) < 1e-9 and abs(ma - (1.0 + 1.0) / 2) < 1e-9
    assert any("golcüsü" in w for w in why) and any("kalecisi" in w for w in why)
    assert sim.rates({"teams": {}}, m) == (None, None, ["bağımsız veri yok (yalnız piyasa)"])
    games = {"home": [{"for": (2, 0), "against": (0, 0)}], "away": [{"for": (None, 1), "against": (None, 0)}]}
    assert abs(sim.half_share({"games": games}) - (2 + 0.44 * 20) / (2 + 20)) < 1e-9


def test_single_pick_rule_and_kept_notes():
    dt_ = _load("derin_tahmin")
    old = [{"code": 1, "onizleme": "son 10 maç …", "legs": [{"label": "A", "verdict": "✓ geçmiş destekliyor", "mean": 0.7,
                                                         "web": "son 6+6 maç %70", "p": 0.6}]}]
    new = [{"code": 1, "legs": [{"label": "A", "verdict": "geçmiş yetersiz", "mean": None, "p": 0.6, "odds": 1.8}]}]
    assert dt_.keep_notes(old, new) == 1
    leg = new[0]["legs"][0]
    assert leg["web"] == "son 6+6 maç %70" and new[0]["onizleme"]                 # note text carried over …
    assert leg["verdict"] == "geçmiş yetersiz" and leg["mean"] is None            # … but it never overrides the verdict
    assert new[0]["pick"]["label"] == "A"                                         # EV 0.6×1.8−1 = +0.08


def test_coupon_drops_simulation_contradiction(monkeypatch):
    kk = _load("kupon_kur")
    legs = [{"code": 7, "key": "k", "match": "M", "market": "Maç Sonucu", "selection": "1", "name": "MS 1", "p": 0.6, "odds": 1.5}]
    monkeypatch.setattr(kk, "research_leg", lambda m, leg, fx: {"legs": [{"verdict": "✓ geçmiş destekliyor", "mean": 0.7}]})
    bad, _ = kk.check(legs, {"7": {"code": 7}}, sim={("7", "Maç Sonucu: 1"): "çelişki"})
    assert len(bad) == 1 and "simülasyon" in bad[0][1]
    assert kk.check(legs, {"7": {"code": 7}}, sim={})[0] == []


def test_openfootball_games_keep_half_scores():
    of = _load("openfootball_gecmis")
    import datetime as dt
    ms = [{"date": "2026-08-21", "team1": "Arsenal FC", "team2": "Coventry City FC", "score": {"ht": [2, 0], "ft": [3, 0]}},
          {"date": "2026-08-29", "team1": "Coventry City FC", "team2": "Arsenal FC", "score": {"ht": [1, 1], "ft": [1, 2]}},
          {"date": "2026-12-01", "team1": "Arsenal FC", "team2": "X", "score": {}}]
    games = of.played(ms, dt.date(2026, 11, 20))
    g = of.team_games("Arsenal FC", games)
    assert [x["side"] for x in g] == ["home", "away"]
    assert g[0]["for"] == (2, 1) and g[0]["against"] == (0, 0) and g[1]["for"] == (1, 1) and g[1]["against"] == (1, 0)
    assert of.season_of(dt.date(2026, 11, 20)) == "2026-27" and of.season_of(dt.date(2027, 3, 1)) == "2026-27"
    assert of.league_file("Bilinmeyen Lig", dt.date(2026, 11, 20)) == []


def test_dc_half_joint_keeps_full_time_matrix():
    dc = _load("dc_model")
    import numpy as np
    ft = np.zeros((15, 15)); ft[1, 0], ft[2, 2], ft[0, 0] = 0.5, 0.3, 0.2
    j = dc.half_joint(ft)
    assert abs(j.sum() - 1) < 1e-12
    assert abs(dc.bet_probability("MS 1", j) - 0.5) < 1e-9 and abs(dc.bet_probability("2.5 Üst", j) - 0.3) < 1e-9
    assert abs(dc.bet_probability("İY 0.5 Alt", j) - (0.2 + 0.5 * 0.56 + 0.3 * 0.56 ** 4)) < 1e-9


def test_model_view_only_downgrades_large_disagreement():
    sim = _load("simulasyon")
    assert sim.with_model("üçlü onay", 0.65, 0.66, 0.60) == ("üçlü onay", 0.60)
    assert sim.with_model("üçlü onay", 0.65, 0.66, 0.50) == ("kısmi onay", 0.50)
    assert sim.with_model("kısmi onay", 0.60, 0.66, None) == ("kısmi onay", 0.60)


def test_openmatchday_games_and_history(monkeypatch):
    om = _load("openmatchday_gecmis")
    import datetime as dt
    rows = [{"date": "2026-11-0%d" % i, "time": "19:00", "home": h, "away": a, "ft_home": fh, "ft_away": fa,
             "ht_home": hh, "ht_away": ha} for i, (h, a, fh, fa, hh, ha) in enumerate(
        [("Pontypridd", "X", "2", "1", "1", "0"), ("Y", "Carmarthen", "3", "1", "", ""), ("Pontypridd", "Z", "1", "0", "", ""),
         ("W", "Carmarthen", "2", "2", "0", "1"), ("Pontypridd", "Carmarthen", "9", "9", "", "")], start=1)]
    kick = dt.datetime(2026, 11, 5, 20, 0, tzinfo=dt.timezone.utc)
    hg, ag = om.team_games("Pontypridd", rows, kick), om.team_games("Carmarthen", rows, kick)
    assert len(hg) == 2 and hg[0]["for"] == (1, 1) and hg[1]["for"] == (None, 1)       # game on kick-off day excluded
    assert ag[0]["for"] == (None, 1) and ag[1]["for"] == (1, 1) and ag[1]["against"] == (0, 2)
    assert om.leg_history("MS 1", hg, ag)["home_rate"] == 1.0                          # full-time bet: all games
    assert om.leg_history("İY 0.5 Üst", hg, ag)["home_n"] == 1                         # half bet: games with half scores
    assert om.folder_for("Galler Championship, Güney") == "WAL_3_cymru-south"
    assert om.folder_for("İngiltere Ulusal Lig Kuzey") == "ENG_6_national-league-north"


def test_footballcharts_games_with_half_scores():
    fc = _load("footballcharts_gecmis")
    import datetime as dt
    rows = [{"id": 1, "date": "2026-11-01", "kickoff_utc": "2026-11-01T18:00:00Z", "homeTeam": "Pribram", "awayTeam": "X",
             "score": "2:1", "ht_result": "1:0"},
            {"id": 2, "date": "2026-11-08", "kickoff_utc": "2026-11-08T18:00:00Z", "homeTeam": "Y", "awayTeam": "Pribram",
             "score": "3:1", "ht_result": "0:1"},
            {"id": 3, "date": "2026-11-20", "kickoff_utc": "2026-11-20T17:00:00Z", "homeTeam": "Pribram", "awayTeam": "Z",
             "score": "", "ht_result": ""}]
    g = fc.team_games("Pribram", rows, dt.datetime(2026, 11, 20, 17, 0, tzinfo=dt.timezone.utc))
    assert [x["event"] for x in g] == [1, 2]
    assert g[0]["for"] == (1, 1) and g[0]["against"] == (0, 1) and g[1]["for"] == (1, 0) and g[1]["against"] == (0, 3)
    assert fc.leagues_for("Çekya 2. Lig") == ("czech2",) and fc.leagues_for("İtalya Serie C, A Grubu") == ("italy3a", "italy3b")
    assert fc.leagues_for("Almanya Bundesliga 2") == ("germany2",) and fc.leagues_for("Bilinmeyen") == ()


def test_datalake_league_rates_tiers():
    dl = _load("datalake_lig")
    rows = [{"country": c, "league": lg, "n": "500"} for c, lg in (
        ("Germany", "Bundesliga"), ("Germany", "2. Bundesliga"), ("Spain", "La Liga"), ("Spain", "Segunda Division"),
        ("England", "Premier League"), ("England", "Championship"), ("England", "League One"), ("England", "League Two"),
        ("Netherlands", "Eredivisie"), ("Netherlands", "Eerste Divisie"), ("Italy", "Serie A"), ("Italy", "Serie B"))]
    got = lambda n: (dl.league_rates(n, rows) or {}).get("league")  # noqa: E731
    assert got("Almanya Bundesliga 2") == "2. Bundesliga" and got("Almanya Bundesliga") == "Bundesliga"
    assert got("İspanya La Liga 2") == "Segunda Division" and got("İspanya 2. Lig") == "Segunda Division"
    assert got("İngiltere 1. Lig") == "League One" and got("İngiltere 2. Lig") == "League Two"
    assert got("Hollanda 1. Lig") == "Eerste Divisie" and got("Hollanda Eredivisie") == "Eredivisie"
    assert got("İtalya Serie C") is None                                    # never the top flight for a lower tier
    assert got("Almanya Bundesliga Günlük Bahisler") is None and got("Almanya U19 Gençlik Ligi") is None


def test_datalake_league_rates_mapping():
    dl = _load("datalake_lig")
    rows = [{"country": "Wales", "league": "Premier League", "n": "391", "goals": "2.9"},
            {"country": "Northern-Ireland", "league": "Championship", "n": "458", "goals": "3.1"},
            {"country": "Northern-Ireland", "league": "Premiership", "n": "500", "goals": "2.7"}]
    assert dl.league_rates("Galler Premier Lig", rows)["league"] == "Premier League"
    assert dl.league_rates("Kuzey İrlanda Championship", rows)["league"] == "Championship"
    assert dl.league_rates("Portekiz Kupası", rows) is None and dl.league_rates("Bilinmeyen Lig", rows) is None


def test_openligadb_games_with_half_scores():
    ol = _load("openligadb_gecmis")
    import datetime as dt
    def m(i, h, a, ht, ft, done=True):
        return {"matchID": i, "matchDateTimeUTC": f"2026-11-0{i}T13:00:00Z", "matchIsFinished": done,
                "team1": {"teamName": h}, "team2": {"teamName": a},
                "matchResults": [{"resultTypeID": 1, "pointsTeam1": ht[0], "pointsTeam2": ht[1]},
                                 {"resultTypeID": 2, "pointsTeam1": ft[0], "pointsTeam2": ft[1]}]}
    rows = [m(1, "1. FC Union Berlin", "X", (1, 0), (2, 0)), m(2, "Y", "1. FC Union Berlin", (0, 0), (1, 1)),
            m(3, "1. FC Union Berlin", "Z", (0, 0), (0, 0), done=False)]
    g = ol.team_games("1. FC Union Berlin", rows, dt.datetime(2026, 11, 20, tzinfo=dt.timezone.utc))
    assert [x["event"] for x in g] == [1, 2] and g[0]["for"] == (1, 1) and g[1]["against"] == (0, 1)
    assert ol.league_for("Almanya Kadınlar Bundesliga") == "ffb1" and ol.league_for("Almanya Bundesliga 2") == "bl2"
    assert ol.league_for("Almanya Böl. Lig, Kuzey Doğu") == "rlno" and ol.season_of(dt.date(2026, 11, 20)) == 2026


def test_kickoff_window():
    dt_ = _load("derin_tahmin")
    assert dt_.in_window("2026-11-21 06:00", "06:00-10:00") and dt_.in_window("2026-11-21 10:00", "06:00-10:00")
    assert not dt_.in_window("2026-11-21 10:30", "06:00-10:00") and dt_.in_window("2026-11-21 23:00", None)


def test_deep_candidates_respect_main_pick_source_and_floor():
    deep = _load("derin_tahmin")
    pick = dict(name="MS 1", market="Maç Sonucu", selection="1", fair_prob=.60, odds=1.6, direct=True)
    match = dict(status="fiyatlandı", reference="ESPN (DraftKings/ESPN BET)", selections=[pick])
    assert not deep.candidates(match, 5, calibration={})
    match.update(reference="OddsMath (Marathonbet)")
    assert not deep.candidates(match, 5, calibration={})
    match["research"] = {"teams": {"home": {"rank": 2}, "away": {"rank": 5}}}
    assert not deep.candidates(match, 5, calibration={})
    pick["fair_prob"] = .63
    assert deep.candidates(match, 5, calibration={})[0]["p"] == .63


def test_main_pick_ranks_and_exports_calibrated_probability(monkeypatch):
    ga = _load("gunluk_analiz")
    monkeypatch.setattr(ga, "load_market_calibration", lambda: {"markets": {"KG Var": {"a": -.4, "b": 1}}})
    kg = dict(name="KG Var", odds=1.5, fair_prob=.7, ev=.05, direct=False)
    ms = dict(name="MS 1", odds=1.5, fair_prob=.65, ev=-.025, direct=True)
    match = dict(status="fiyatlandı", reference="OddsMath (BetInAsia/Pinnacle)", selections=[kg, ms])
    assert ga.best_pick(match)[0]["name"] == "MS 1"
    match["selections"] = [kg]
    pick = ga.best_pick(match)[0]
    assert .60 < pick["fair_prob"] < .62 and kg["fair_prob"] == .7
    assert pick["ev"] == pick["fair_prob"] * pick["odds"] - 1
    kg["direct"] = True
    assert ga.best_pick(match)[0]["fair_prob"] == .7
