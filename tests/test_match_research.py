"""ESPN research layer: regular starters, absences, staleness guard, table labels (offline, synthetic data)."""

import datetime as dt

from quantfoot.data import match_research as mr


def _roster(team_id, players):
    return {"team": {"id": team_id}, "roster": [{"starter": True, "athlete": {"id": pid, "displayName": f"P{pid}"},
                                                  "position": {"abbreviation": pos}} for pid, pos in players]}


XI = [(str(i), "G" if i == 1 else "M") for i in range(1, 12)]


def _fake_summaries(today_xi):
    past = {str(100 + k): {"rosters": [_roster("7", XI)]} for k in range(5)}
    games = [{"id": str(100 + k), "gameResult": "W", "score": "1-0", "atVs": "vs", "opponent": {"displayName": "X"},
              "gameDate": f"2026-11-{10 + k:02d}T18:00Z"} for k in range(5)]
    today = {
        "header": {"league": {"slug": "bra.1"}, "competitions": [{"date": "2026-11-19T18:00Z", "competitors": [
            {"homeAway": "home", "team": {"id": "7"}}, {"homeAway": "away", "team": {"id": "8"}}]}]},
        "lastFiveGames": [{"team": {"id": "7", "displayName": "Home FC"}, "events": games}],
        "leaders": [{"team": {"id": "7"}, "leaders": [{"name": "goalsLeaders", "leaders": [
            {"displayValue": "G: 9", "athlete": {"id": "11", "displayName": "P11"}}]}]}],
        "standings": {"groups": [{"standings": {"entries": [
            {"id": str(t), "stats": [{"name": "rank", "value": t}, {"name": "points", "value": 40 - t}, {"name": "gamesPlayed", "value": 30}]}
            for t in range(1, 21)]}}]},
        "rosters": [_roster("7", today_xi)],
    }
    return {"999": today, **past}


def test_absent_goalkeeper_and_top_scorer_are_flagged(monkeypatch):
    xi = [("1b", "G")] + [(str(i), "M") for i in range(2, 11)] + [("12", "F")]  # keeper 1 and scorer 11 out
    data = _fake_summaries(xi)
    monkeypatch.setattr(mr, "_summary", lambda eid: data.get(eid))
    res = mr.research("999")
    home = res["teams"]["home"]
    assert home["form"] == "WWWWW" and home["rest_days"] == 5.0
    assert home["lineup_announced"] and home["goalkeeper_changed"] and home["top_scorer_missing"]
    assert {p["id"] for p in home["missing_regulars"]} == {"1", "11"}
    old_price = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
    flags = mr.staleness_flags(res, old_price)
    assert any("kaleci" in f for f in flags) and flags[-1].startswith("global fiyat")
    assert not mr.staleness_flags(res, dt.datetime.now(dt.timezone.utc))[-1].startswith("global fiyat")


def test_full_regular_lineup_raises_nothing(monkeypatch):
    data = _fake_summaries(XI)
    monkeypatch.setattr(mr, "_summary", lambda eid: data.get(eid))
    res = mr.research("999")
    assert res["teams"]["home"]["missing_regulars"] == []
    assert mr.staleness_flags(res, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)) == []


def test_motivation_only_for_domestic_leagues():
    rec = {"table": {"rank": 18, "size": 20, "points": 30}}
    assert "küme hattı" in mr.motivation(rec, "bra.1")
    assert mr.motivation({"table": {"rank": 2, "size": 20, "points": 70}}, "eng.1").startswith("2./20 (zirve")
    assert mr.motivation(rec, "uefa.wchampions") is None


def test_fpl_availability_marks_key_players(monkeypatch):
    feed = {"teams": [{"id": 1, "name": "Arsenal"}],
            "elements": [{"team": 1, "web_name": "Saka", "status": "i", "starts": 10, "chance_of_playing_next_round": 0,
                          "news": "Thigh", "goals_scored": 5},
                         {"team": 1, "web_name": "Kid", "status": "d", "starts": 1, "chance_of_playing_next_round": 75,
                          "news": "Knock", "goals_scored": 0},
                         {"team": 1, "web_name": "Fit", "status": "a", "starts": 12}]}
    mr.fpl_availability.cache_clear()
    monkeypatch.setattr(mr, "_get", lambda url, **p: feed)
    a = mr.fpl_availability()["Arsenal"]
    mr.fpl_availability.cache_clear()
    assert [(p["name"], p["status"], p["key"]) for p in a] == [("Saka", "sakat", True), ("Kid", "şüpheli", False)]


def test_team_profile_and_stats(monkeypatch):
    def ath(name, pos, **st):
        return {"displayName": name, "position": {"abbreviation": pos},
                "statistics": {"splits": {"categories": [{"stats": [{"name": k, "value": v} for k, v in st.items()]}]}}}
    roster = {"athletes": [ath("Keeper", "G", appearances=30, saves=90, goalsConceded=30),
                           ath("Striker", "F", appearances=30, totalGoals=12, goalAssists=2, yellowCards=5),
                           ath("Playmaker", "M", appearances=28, totalGoals=3, goalAssists=9)]}
    stats = {"splits": {"categories": [{"stats": [{"name": "appearances", "value": 30}, {"name": "totalShots", "value": 450},
                                                  {"name": "possessionPct", "value": 55.2}, {"name": "passPct", "value": 0.86},
                                                  {"name": "avgExpectedGoals", "value": 1.57}]}]}}
    monkeypatch.setattr(mr, "_get", lambda url, **p: roster if url.endswith("/roster") else stats)
    mr.team_profile.cache_clear(); mr.team_stats.cache_clear()
    prof = mr.team_profile("bra.1", "1")
    assert prof["top_scorers"][0]["name"] == "Striker" and prof["top_assists"][0]["name"] == "Playmaker"
    assert prof["goalkeeper"]["save_pct"] == 0.75 and prof["goalkeeper"]["conceded_per_game"] == 1.0
    assert [p["name"] for p in prof["cards"]] == ["Striker"]
    ts = mr.team_stats("bra.1", 2026, "1")
    assert ts == {"Topla oynama": "%55.2", "Şut": "15.0 / maç", "xG (beklenen gol)": "1.57", "Pas isabeti": "%86"}
    mr.team_profile.cache_clear(); mr.team_stats.cache_clear()
