import datetime as dt
import json

from quantfoot.data import match_dossier as md

UTC = dt.timezone.utc


def _fx(fid, home, away, hid, aid, when, league="Premier League", lid=39):
    return {"fixture": {"id": fid, "date": when, "referee": "Peter Bankes", "status": {"short": "NS"},
                        "venue": {"name": "Etihad", "city": "Manchester"}},
            "league": {"id": lid, "name": league, "country": "England", "round": "R11"},
            "teams": {"home": {"id": hid, "name": home}, "away": {"id": aid, "name": away}}}


def test_find_fixture_prefers_senior_team_over_youth():
    fixtures = [_fx(1, "Genclerbirligi U19", "Gaziantep U19", 1, 2, "2026-11-21T10:00:00+00:00"),
                _fx(2, "Gençlerbirliği S.K.", "Gaziantep FK", 3, 4, "2026-11-21T10:30:00+00:00")]
    assert md.find_fixture(fixtures, "Gençlerbirliği", "Gaziantep")["fixture"]["id"] == 2
    assert md.find_fixture(fixtures, "Genclerbirligi U19", "Gaziantep U19")["fixture"]["id"] == 1
    assert md.find_fixture(fixtures, "Real Madrid", "Barcelona") is None


def test_rest_and_congestion_counts_all_competitions():
    ko = dt.datetime(2026, 11, 21, 15, tzinfo=UTC)
    sched = [(ko - dt.timedelta(days=3), "UEFA Europa League", 10), (ko - dt.timedelta(days=7), "Premier League", 11),
             (ko - dt.timedelta(days=10), "League Cup", 12), (ko - dt.timedelta(days=13), "Premier League", 13),
             (ko, "Premier League", 99), (ko + dt.timedelta(days=3), "UEFA Europa League", 14)]
    rc = md.rest_and_congestion(sched, ko, 99)
    assert rc["rest_days"] == 3.0 and rc["last_competition"] == "UEFA Europa League"
    assert rc["matches_last_window"] == 4 and rc["days_to_next"] == 3.0
    flags = md.schedule_flags("City", rc)
    assert len(flags) == 3


def test_team_schedule_from_fixtures_by_day():
    by_day = {dt.date(2026, 11, 20): [_fx(5, "City", "X", 50, 7, "2026-11-20T19:00:00+00:00", "Cup", 2)],
              dt.date(2026, 11, 21): [_fx(6, "Y", "City", 8, 50, "2026-11-21T15:00:00+00:00")]}
    s = md.team_schedule(by_day, 50)
    assert [x[2] for x in s] == [5, 6]


def _odds_resp():
    def book(name, h, d, a, o, u):
        return {"name": name, "bets": [
            {"name": "Match Winner", "values": [{"value": "Home", "odd": str(h)}, {"value": "Draw", "odd": str(d)},
                                                {"value": "Away", "odd": str(a)}]},
            {"name": "Goals Over/Under", "values": [{"value": "Over 2.5", "odd": str(o)}, {"value": "Under 2.5", "odd": str(u)}]}]}
    return [{"update": "2026-11-21T09:00:00+00:00",
             "bookmakers": [book("Pinnacle", 2.0, 3.6, 4.2, 1.9, 2.0), book("Bet365", 1.95, 3.5, 4.5, 1.83, 1.95)]}]


def test_summarize_odds_sharp_vs_soft():
    o = md.summarize_odds(_odds_resp())
    m = o["1X2"]
    assert m["sharp_book"] == "Pinnacle"
    assert abs(sum(m["fair"]) - 1) < 1e-3
    assert m["best_soft"] == [1.95, 3.5, 4.5]
    assert abs(m["best_soft_ev"][2] - (m["fair"][2] * 4.5 - 1)) < 2e-4
    assert o["2.5"]["fair"][0] > 0.5


def test_odds_movement_flag():
    a = {"update": "t0", "1X2": {"fair": [0.50, 0.27, 0.23]}}
    b = {"update": "t1", "1X2": {"fair": [0.45, 0.28, 0.27]}}
    mv = md.odds_movement([a, b])
    assert mv["delta_fair"][0] == -0.05 and "1" in mv["flag"]
    assert md.odds_movement([a]) is None


def test_referee_profile_vs_league():
    rows = [{"Referee": "P Bankes", "HY": "4", "AY": "3", "HR": "0", "AR": "0", "HF": "12", "AF": "11", "FTHG": "1", "FTAG": "1"}] * 6
    rows += [{"Referee": "M Oliver", "HY": "1", "AY": "1", "HR": "0", "AR": "0", "HF": "9", "AF": "9", "FTHG": "2", "FTAG": "1"}] * 10
    prof = md.referee_profile(rows, "Peter Bankes")
    assert prof["matches"] == 6 and prof["yellow"] == 7.0 and "Kartçı" in prof["flag"]
    assert md.referee_profile(rows, "") is None


def test_summarize_injuries_and_prediction():
    inj = [{"player": {"name": "A", "type": "Missing Fixture", "reason": "Knee"}, "team": {"id": 1}},
           {"player": {"name": "B", "type": "Questionable", "reason": "Knock"}, "team": {"id": 2}}]
    out = md.summarize_injuries(inj, 1, 2)
    assert out["home"][0]["player"] == "A" and out["away"][0]["type"] == "Questionable"
    pred = [{"predictions": {"advice": "x"}, "comparison": {}, "h2h": [],
             "teams": {"home": {"last_5": {"form": "40%", "goals": {"for": {"average": "1.6"}, "against": {"average": "1.0"}}},
                                "league": {"form": "WWL"}}, "away": {}}}]
    p = md.summarize_prediction(pred)
    assert p["home"]["last5_goals_for"] == "1.6" and p["home"]["league_form"] == "WWL"


def test_build_dossier_offline_with_fake_fetch(tmp_path, monkeypatch):
    calls = []
    fx = _fx(77, "Manchester City", "Fulham", 50, 36, "2026-11-21T12:30:00+00:00")
    prev = _fx(70, "Real Madrid", "Manchester City", 541, 50, "2026-11-18T20:00:00+00:00", "UEFA Champions League", 2)

    def fake(url, params, headers):
        calls.append((url, dict(params)))
        if url.endswith("/fixtures") and params.get("date") == "2026-11-21":
            return 200, {"errors": [], "response": [fx]}
        if url.endswith("/fixtures") and params.get("date") == "2026-11-20":
            return 200, {"errors": [], "response": []}
        if url.endswith("/fixtures"):
            return 200, {"errors": {"plan": "Free plans do not have access to this date"}, "response": []}
        if url.endswith("/injuries"):
            return 200, {"errors": [], "response": []}
        if url.endswith("/predictions"):
            return 200, {"errors": [], "response": []}
        if url.endswith("/odds"):
            return 200, {"errors": [], "response": _odds_resp()}
        if "geocoding" in url:
            return 200, {"results": [{"latitude": 53.4, "longitude": -2.2}]}
        if "forecast" in url:
            return 200, {"hourly": {"time": ["2026-11-21T12:00"], "precipitation": [5.0], "wind_speed_10m": [10],
                                    "snowfall": [0], "temperature_2m": [4]}}
        if "football-data" in url:
            return 200, "Div,Referee,HY,AY,HR,AR,HF,AF,FTHG,FTAG\n" + "E0,P Bankes,4,4,0,0,10,10,1,1\n" * 6 + "E0,X Y,1,1,0,0,9,9,2,2\n" * 6
        return 404, None

    http = md.CachedHttp(tmp_path, fetch=fake)
    # pre-cache an older day (free plan cannot fetch it) → read without spending a request
    http._path(f"{md.AF_BASE}/fixtures", {"date": "2026-11-18"}).write_text(
        json.dumps({"t": 0, "url": "", "params": {}, "body": {"response": [prev]}}))
    monkeypatch.setattr(md, "espn_context", lambda *a, **k: None)
    api = md.ApiFootball(http, key="k", daily_limit=50)
    d = md.build_dossier(dt.date(2026, 11, 21), "Man City", "Fulham", http=http, api=api, history_days=4,
                         future_days=1, today=dt.date(2026, 11, 21))
    assert d["fixture_id"] == 77
    assert d["home_schedule"]["rest_days"] == 2.7  # Champions League midweek counted
    assert d["odds"]["1X2"]["sharp_book"] == "Pinnacle"
    assert d["weather"]["rain_mm"] == 5.0
    assert d["referee_profile"]["matches"] == 6
    af_dates = sorted(p.get("date") for u, p in calls if u.endswith("/fixtures"))
    assert af_dates == ["2026-11-20", "2026-11-21", "2026-11-22"]  # outside the free window: cache only
    assert api.used_today() >= 5
    assert "Manchester City" in md.render_markdown(d)


def test_quota_guard_stops_requests(tmp_path):
    http = md.CachedHttp(tmp_path, fetch=lambda u, p, h: (200, {"errors": [], "response": []}))
    api = md.ApiFootball(http, key="k", daily_limit=1)
    api.get("injuries", {"fixture": 1}, 60)
    try:
        api.get("injuries", {"fixture": 2}, 60)
    except md.QuotaExceeded:
        pass
    else:
        raise AssertionError("quota guard did not trigger")
