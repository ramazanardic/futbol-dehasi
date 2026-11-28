"""web_research: ağ çağrısı yok (sahte oturum / enjekte havuz). Önbellek, zaman aşımı kaydı, robots, bilinmiyor işareti,
kalkanın bayrağa bağlılığı ve ESPN kaydının üzerine yazılmaması."""

from __future__ import annotations

import time

import pytest
import requests

from quantfoot.data import free_absences as FA
from quantfoot.data import recent_form as RF
from quantfoot.data import web_research as W


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code, self._p, self.text = status, payload, text

    def json(self):
        return self._p


class _Sess:
    def __init__(self, plan):
        self.plan, self.calls, self.headers = plan, [], {}

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        r = self.plan(url) if callable(self.plan) else self.plan
        if isinstance(r, Exception):
            raise r
        return r


def _http(tmp_path, plan, **kw):
    return W.Http(cache_dir=tmp_path, session=_Sess(plan), min_gap=0, **kw)


def test_http_cache_hit_skips_network_and_logs(tmp_path):
    h = _http(tmp_path, _Resp(payload={"a": 1}))
    assert h.get("T", "https://x.test/a", ttl=100) == {"a": 1}
    assert h.get("T", "https://x.test/a", ttl=100) == {"a": 1}
    assert len(h.s.calls) == 1
    assert [x["onbellek"] for x in h.log] == [False, True]
    assert all(x["zaman"] and x["kaynak"] == "T" for x in h.log)
    assert h.s.calls[0][2] == W.TIMEOUT_S  # zaman aşımı her istekte verilir


def test_http_timeout_returns_none_and_is_logged(tmp_path):
    h = _http(tmp_path, requests.Timeout())
    assert h.get("T", "https://x.test/b") is None
    assert h.log[0]["ok"] is False and h.log[0]["hata"] == "Timeout"


def test_http_stale_copy_used_when_source_down(tmp_path):
    ok = _http(tmp_path, _Resp(payload={"v": 1}))
    ok.get("T", "https://x.test/c", ttl=0)
    down = _http(tmp_path, requests.ConnectionError())
    assert down.get("T", "https://x.test/c", ttl=0) == {"v": 1}
    assert down.log[0]["eski"] is True  # eski kopya etiketli


def test_http_respects_robots(tmp_path):
    def plan(url):
        return _Resp(text="User-agent: *\nDisallow: /w/") if url.endswith("robots.txt") else _Resp(payload={"x": 1})

    h = _http(tmp_path, plan)
    assert h.get("W", "https://wiki.test/w/api.php", check_robots=True) is None
    assert h.log[-1]["hata"] == "robots.txt yasak"
    assert h.get("W", "https://wiki.test/wiki/Page", check_robots=True) == {"x": 1}


def test_candidate_filter():
    base = {"status": "fiyatlandı", "price_tier": "keskin", "selections": [{"fair_prob": 0.72, "odds": 1.4}]}
    assert W.is_candidate(base)
    assert not W.is_candidate({**base, "price_tier": "ozel_bahis"})
    assert not W.is_candidate({**base, "status": "global referans bulunamadı — fiyatlanmadı"})
    assert not W.is_candidate({**base, "selections": [{"fair_prob": 0.50, "odds": 2.0}]})
    assert not W.is_candidate({**base, "selections": [{"fair_prob": 0.9, "odds": 1.05}]})


def _row(day, h, a, hg, ag, league="XXX_1_lig", src="openmatchday", **kw):
    return RF._row(day, h, a, hg, ag, src, league=league, **kw)


POOL = [_row("2026-11-01", "Alpha FC", "Beta FC", 2, 0), _row("2026-11-08", "Gamma FC", "Alpha FC", 1, 1),
        _row("2026-11-15", "Alpha FC", "Gamma FC", 3, 1), _row("2026-11-20", "Beta FC", "Gamma FC", 0, 2),
        _row("2026-11-21", "Beta FC", "Alpha FC", 1, 0)]


def test_table_from_pool_excludes_match_day_and_later():
    t = W.table_from_pool(POOL, "XXX_1_lig", "2026-11-21")
    assert next(x["team"] for x in t) == "Alpha FC" and t[0]["points"] == 7
    e = W.table_entry(t, "Beta FC")
    assert e["rank"] == 3 and e["played"] == 2 and e["size"] == 3
    assert W.table_entry(t, "Totally Else") is None


def _ctx(tmp_path, fpl=None, wiki=None):
    return W.Ctx("2026-11-22", _http(tmp_path, _Resp(404)), pool=POOL, fpl=fpl or {}, wiki=wiki or (lambda *a: None))


def test_research_match_marks_unknown_and_never_invents(tmp_path):
    ctx = _ctx(tmp_path)
    w = W.research_match({"home": "Alpha FC", "away": "Nowhere United"}, ctx)
    home, away = w["takimlar"]["home"], w["takimlar"]["away"]
    assert home["form"] and len(home["son_maclar"]) == 4 and home["son_maclar"][0]["rakip"]
    assert "son_maclar" not in away and "away.son_maclar" in w["bilinmiyor"]
    assert away["sakat_cezali"] == W.UNKNOWN and away["hoca_degisikligi"] == W.UNKNOWN
    assert w["haber"] == W.UNKNOWN and "home.xg" in w["bilinmiyor"]  # xG: ESPN yok + şut verisi yok -> bilinmiyor
    assert home["puan_durumu"]["kaynak"].startswith("Open Matchday")
    assert all("kaynak" in k and "zaman" in k for k in w["kaynaklar"])


def test_espn_zero_xg_is_unknown():
    assert W._espn_xg({"xG (beklenen gol)": "0", "xGA (beklenen yenen gol)": "0"}) is None
    assert W._espn_xg({"xG (beklenen gol)": "1.4", "xGA (beklenen yenen gol)": "0.9"})["xg"] == 1.4


def test_fpl_short_names_match_and_alerts(tmp_path):
    fpl = {"Man Utd": {**FA._empty_rec("Man Utd", "fpl"), "gk1_out": True}}
    assert W.match_any("Manchester United", fpl) == "Man Utd"
    ctx = _ctx(tmp_path, fpl=fpl)
    w = W.research_match({"home": "Manchester United", "away": "Alpha FC"}, ctx)
    assert "Ev: 1. kaleci eksik" in w["alerts"]


def test_normalize_does_not_create_teams_or_overwrite_espn(tmp_path):
    ctx = _ctx(tmp_path)
    rec = {"home": "Alpha FC", "away": "Beta FC", "research": {"teams": {}, "flags": []}}
    w = W.research_match(rec, ctx)
    W.normalize_into(rec, w, shield=False)
    assert rec["research"]["teams"] == {}  # teams varlığı kupon uygunluğunu belirler: web tek başına açmaz
    assert rec["research"]["web"] is w
    espn = {"name": "Alpha FC", "form": "GGGGG", "last5": ["x"], "table": {"rank": 1}}
    rec2 = {"home": "Alpha FC", "away": "Beta FC", "research": {"teams": {"home": dict(espn)}, "flags": []}}
    W.normalize_into(rec2, W.research_match(rec2, ctx), shield=False)
    assert rec2["research"]["teams"]["home"] == espn
    assert "tm_absences" not in rec2["research"]


def test_shield_only_with_flag_and_never_overrides_transfermarkt(tmp_path):
    fpl = {"Alpha FC": {**FA._empty_rec("Alpha FC", "fpl"), "gk1_out": True}}
    ctx = _ctx(tmp_path, fpl=fpl)
    rec = {"home": "Alpha FC", "away": "Beta FC", "research": {"teams": {}, "flags": []}}
    w = W.research_match(rec, ctx)
    W.normalize_into(rec, w, shield=False)
    assert "tm_absences" not in rec["research"]
    W.normalize_into(rec, w, shield=True)
    assert rec["research"]["tm_absences"]["home"]["gk1_out"] is True
    assert "Web: Ev: 1. kaleci eksik" in rec["research"]["flags"]
    tm = {"home": {"gk1_out": False}, "away": None, "alerts": []}
    rec3 = {"home": "Alpha FC", "away": "Beta FC", "research": {"teams": {}, "flags": [], "tm_absences": tm}}
    W.normalize_into(rec3, w, shield=True)
    assert rec3["research"]["tm_absences"] is tm


def test_lineup_from_espn_flags_missing_regulars():
    assert W.lineup_from_espn("X", {"lineup_announced": False}) is None
    r = W.lineup_from_espn("X", {"lineup_announced": True, "top_scorer_missing": True,
                                 "missing_regulars": [{"name": "K", "pos": "G"}, {"name": "D", "pos": "CD-L"}]})
    assert r["gk1_out"] and r["def_core_out"] == 1 and r["top_scorer_out"]


def test_manager_changes_window_and_ambiguous_dates():
    rows = [{"team": "Venezia", "out": "A", "manner": "Sacked", "date": "13 October 2026", "in": "B", "in_date": "14 October 2026"},
            {"team": "Venezia", "out": "Old", "manner": "Sacked", "date": "1 June 2026", "in": "C", "in_date": ""},
            {"team": "Villarreal", "out": "M", "manner": "End of contract", "date": "Iñigo Pérez", "in": "Pre-season", "in_date": ""},
            {"team": "Other", "out": "Z", "manner": "", "date": "1 November 2026", "in": "Q", "in_date": ""}]
    got = W.manager_changes_for("Venezia", rows, "2026-11-28")
    assert [g["out"] for g in got] == ["A"]
    amb = W.manager_changes_for("Villarreal", rows, "2026-11-28")
    assert amb == [{"team": "Villarreal", "out": "M", "manner": "End of contract", "tarih": "belirsiz"}]  # giren adı verilmez


def test_parse_wiki_tables_standings_and_managers():
    pytest.importorskip("lxml")
    html = """<table><tr><th>Pos</th><th>Team</th><th>Pld</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th></tr>
    <tr><td>1</td><td>Alpha</td><td>10</td><td>7</td><td>2</td><td>1</td><td>20</td><td>8</td><td>+12</td><td>23</td></tr></table>
    <table><tr><th>Team</th><th>Outgoing manager</th><th>Manner of departure</th><th>Date of vacancy</th><th>Incoming manager</th><th>Date of appointment</th></tr>
    <tr><td>Alpha</td><td>Mr A</td><td>Sacked</td><td>3 November 2026</td><td>Mr B</td><td>4 November 2026</td></tr></table>"""
    r = W.parse_wiki_tables(html)
    assert r["table"][0]["points"] == 23 and r["table"][0]["goal_diff"] == 12
    assert r["managers"][0]["in"] == "Mr B" and r["managers"][0]["date"] == "3 November 2026"


def test_attach_limits_to_candidates_and_respects_budget(tmp_path):
    import datetime as dt

    cand = {"status": "fiyatlandı", "price_tier": "keskin", "selections": [{"fair_prob": 0.8, "odds": 1.3}]}
    out = [{"home": "Alpha FC", "away": "Beta FC", **cand}, {"home": "Gamma FC", "away": "Beta FC", "status": "x", "selections": []}]
    ctx = _ctx(tmp_path)
    s = W.attach(out, dt.date(2026, 11, 22), shield=False, http=ctx.http, ctx=ctx)
    assert s["aday"] == 1 and s["islenen"] == 1
    assert "web" in out[0]["research"] and "research" not in out[1]
    out2 = [{"home": "Alpha FC", "away": "Beta FC", **cand}]
    s2 = W.attach(out2, dt.date(2026, 11, 22), shield=False, http=ctx.http, ctx=ctx, budget_s=-1)
    assert s2["islenen"] == 0 and s2["atlanan_sure"] == 1


def test_refresh_pool_degrades_when_all_sources_down(tmp_path):
    h = _http(tmp_path, requests.ConnectionError())
    t0 = time.time()
    pool, st = W.refresh_pool("2026-11-22", h, window=3)
    assert pool == [] and st["espn_gun"] == 0 and time.time() - t0 < 5
