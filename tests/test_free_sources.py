"""recent_form / free_absences / form_priors: ağsız birim testleri (sahte yanıtlar)."""

from __future__ import annotations

import datetime as dt

from quantfoot.data import free_absences as FA
from quantfoot.data import recent_form as RF
from quantfoot.markets import form_priors as FP


def _espn(events):
    return {"events": events}


def _ev(day, h, a, hs, as_, done=True, slug="eng.1"):
    return {"id": "1", "date": f"{day}T15:00Z", "season": {"slug": slug},
            "competitions": [{"status": {"type": {"completed": done}},
                              "competitors": [{"homeAway": "home", "team": {"displayName": h}, "score": str(hs)},
                                              {"homeAway": "away", "team": {"displayName": a}, "score": str(as_)}]}]}


def test_parse_espn_day_skips_unfinished_and_women():
    rows = RF.parse_espn_day(_espn([_ev("2026-11-01", "A", "B", 2, 1), _ev("2026-11-02", "C", "D", 0, 0, done=False),
                                    _ev("2026-11-03", "E", "F", 1, 1, slug="english-womens-super-league")]))
    assert [(r["home"], r["hg"], r["ag"]) for r in rows] == [("A", 2, 1)]


def test_parse_openmatchday_reads_shots_and_skips_unplayed():
    txt = ("date,home,away,ft_home,ft_away,home_shots,away_shots,home_target,away_target\n"
           "2026-11-01,A,B,2,1,12,8,5,3\n2026-11-08,C,D,,,,,,\n")
    rows = RF.parse_openmatchday(txt, "XXX_1_lig")
    assert len(rows) == 1 and rows[0]["hs"] == 12 and rows[0]["ht"] == 5 and rows[0]["league"] == "XXX_1_lig"


def test_dedupe_prefers_nesine_and_merges_same_match():
    a = RF._row("2026-11-01", "Alpha FC", "Beta FC", 2, 1, "espn")
    b = RF._row("2026-11-01", "Alpha", "Beta", 2, 1, "nesine", league="N")
    out = RF.dedupe([a, b])
    assert len(out) == 1 and out[0]["src"] == "nesine"


def _pool():
    rows = []
    for i in range(6):
        d = f"2026-10-{10 + i:02d}"
        rows.append(RF._row(d, "Alpha FC", f"Opp{i} FC", 3, 1, "espn", league="L"))
        rows.append(RF._row(d, f"Foe{i} FC", "Beta FC", 0, 0, "espn", league="L"))
    return RF.dedupe(rows)


def test_team_form_has_no_leakage_and_needs_min_games():
    pool = _pool()
    idx = RF.build_index(pool)
    k = RF.resolve_team("Alpha FC", idx)
    assert RF.team_form(k, idx, "2026-10-10") is None  # maç gününde / öncesinde veri yok
    f = RF.team_form(k, idx, "2026-11-01")
    assert f["n"] == 6 and f["gf"] == 3 and f["ga"] == 1
    assert RF.team_form(k, idx, "2026-10-13")["n"] == 3  # yalnız önceki maçlar (sızıntı yok)


def test_lambdas_shrink_toward_pool_mean_and_need_both_teams():
    pool = _pool()
    idx = RF.build_index(pool)
    means = RF.pool_means(pool, "2026-11-01")
    assert RF.lambdas("Alpha FC", "Nobody", idx, "2026-11-01", means) is None
    lh_, la_, info = RF.lambdas("Alpha FC", "Beta FC", idx, "2026-11-01", means)
    assert 0.15 < lh_ < 3.0 and 0.15 < la_ < 3.0 and info["n_ev"] >= 3


def test_form_priors_off_by_default_and_blend_changes_only_goal_families(monkeypatch):
    monkeypatch.delenv("QF_RECENT_FORM", raising=False)
    assert FP.blend("2.5 Üst", 0.61, "L", "Alpha FC", "Beta FC", dt.date(2026, 11, 1)) == 0.61  # kapalı: aynen
    monkeypatch.setenv("QF_RECENT_FORM", "1")
    pool = _pool()
    state = {"idx": RF.build_index(pool), "means": RF.pool_means(pool, "2026-11-01"), "cache": {}, "xg": False}
    monkeypatch.setitem(FP._STATE, "2026-11-01", state)
    p = FP.blend("2.5 Üst", 0.61, "L", "Alpha FC", "Beta FC", dt.date(2026, 11, 1))
    assert p != 0.61 and 0.0 < p < 1.0
    assert FP.blend("MS 1", 0.61, "L", "Alpha FC", "Beta FC", dt.date(2026, 11, 1)) == 0.61  # maç sonucu ailesi: değişmez
    assert FP.blend("2.5 Üst", 0.61, "L", "Alpha FC", "Yok FC", dt.date(2026, 11, 1)) == 0.61  # öncül yok: değişmez


# ---------------------------------------------------------------- free_absences
def _fpl():
    return {"teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
            "elements": [
                {"id": 1, "team": 1, "element_type": 1, "web_name": "Raya", "minutes": 900, "status": "i",
                 "chance_of_playing_next_round": 0, "news": "Knee", "goals_scored": 0},
                {"id": 2, "team": 1, "element_type": 4, "web_name": "Jesus", "minutes": 800, "status": "d",
                 "chance_of_playing_next_round": 50, "news": "Doubt", "goals_scored": 6},
                {"id": 3, "team": 1, "element_type": 3, "web_name": "Bench", "minutes": 0, "status": "a",
                 "chance_of_playing_next_round": None, "news": "", "goals_scored": 0}]}


def test_fpl_records_flag_gk_and_treat_doubt_as_not_out():
    r = FA.fpl_club_records(_fpl())["Arsenal"]
    assert r["gk1_out"] is True and r["top_scorer_out"] is False  # şüpheli (%50) 'out' sayılmaz
    assert any(x["state"] == "doubt" for x in r["injuries"])


def test_lineup_record_flags_missing_regular_starters():
    prev = [{"players": [{"id": "1", "name": "GK", "pos": "G", "starter": True},
                         {"id": "2", "name": "CB", "pos": "CD-L", "starter": True}]} for _ in range(4)]
    reg = FA.regulars(prev)
    assert set(reg) == {"1", "2"}
    rec = FA.lineup_record("X", [{"id": "2", "starter": True}], reg)
    assert rec["gk1_out"] is True and rec["def_core_out"] == 0 and rec["lineup_confirmed"] is True
    assert FA.regulars(prev[:2]) == {}  # < 3 önceki maç: düzenli oyuncu tahmini yapılmaz


def test_merge_and_fetch_free_absences_alerts():
    fpl = FA.fpl_club_records(_fpl())
    got = FA.fetch_free_absences([{"code": 7, "home": "Arsenal", "away": "Zzz United"}], fpl=fpl)
    assert got[7]["home"]["gk1_out"] and "Ev: 1. kaleci eksik" in got[7]["alerts"] and got[7]["away"] is None
    assert FA.fetch_free_absences([{"code": 8, "home": "Q", "away": "R"}], fpl=fpl) == {}


def test_af_injury_records_have_unknown_importance():
    payload = {"response": [{"team": {"name": "Lyon"}, "player": {"name": "P", "type": "Missing Fixture", "reason": "Knee"},
                             "fixture": {"id": 5}}]}
    r = FA.af_injury_records(payload)["Lyon"]
    assert r["injuries"][0]["importance"] == "UNKNOWN" and r["gk1_out"] is False  # mevki bilinmiyor: kalkan tetiklenmez


def test_free_absences_disabled_by_default(monkeypatch):
    monkeypatch.delenv("QF_FREE_ABSENCES", raising=False)
    assert FA.enabled() is False
