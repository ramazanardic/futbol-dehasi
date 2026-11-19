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
