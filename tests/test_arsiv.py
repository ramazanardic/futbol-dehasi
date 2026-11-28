"""data/arsiv ayrıştırıcıları ve tekrar ayıklama (ağ yok, küçük örnekler)."""

from quantfoot.data import arsiv as A

TXT = """= Premier League 2017/18
# Date  Aug 11 2017 - May 13 2018

» Matchday 1
Fri Aug 11
  20:45  Arsenal FC    4-3 (2-2)  Leicester City
Sat Aug 12
  Watford  2-2  Liverpool

» Round 2
Wed Sep 18 2019
  Real Madrid  v  Sevilla   1-1 aet (1-1, 0-0), 5-4 pen
  Ajax  0-3  Benfica
"""


def test_parse_score_variants():
    assert A.parse_score("2-1 (1-0)")["iy_ev"] == 1
    r = A.parse_score("2-2 aet (2-2, 1-0), 6-5 pen")
    assert (r["durum"], r["hg"], r["ag"], r["iy_ev"]) == ("PEN", 2, 2, 1)
    r = A.parse_score("4-3 pen.")
    assert r["durum"] == "PEN" and r["hg"] is None and r["ham_skor"]
    assert A.parse_score("postponed") is None


def test_football_txt_dates_and_scores():
    rows = A.parse_football_txt(TXT, "england/2017-18/1-pl.txt", "england/pl")
    assert len(rows) == 4
    assert rows[0]["tarih"] == "2017-08-11" and (rows[0]["hg"], rows[0]["ag"], rows[0]["iy_ev"]) == (4, 3, 2)
    assert rows[1]["ev"] == "Watford" and rows[1]["dep"] == "Liverpool"
    assert rows[2]["tarih"] == "2019-09-18" and rows[2]["durum"] == "PEN"
    assert all(r["kaynak"] == "openfootball" for r in rows)


def test_football_txt_header_overrides_year_for_calendar_leagues():
    txt = "# Date  Fri Jan 07 2011 - Sun Sep 25 2011\n\n» Round 1\n  07.01.\n    16:00  Enyimba FC   v ABS FC    2-0 (0-0)\n"
    rows = A.parse_football_txt(txt, "nigeria/2011-12_ng1.txt", "ng1")
    assert rows and rows[0]["tarih"] == "2011-01-07"


def test_clean_team_strips_country_and_index():
    assert A._clean_team("Sporting CP › POR (1)") == "Sporting CP"
    assert A._clean_team("Club Brugge KV (BEL)") == "Club Brugge KV"
    assert A._clean_team("Real Madrid") == "Real Madrid"


def test_football_data_csv():
    csv_text = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,HTHG,HTAG\nE0,19/08/95,Aston Villa,Man United,3,1,2,0\nE0,bozuk,A,B,1,1,0,0\n"
    rows = A.parse_football_data(csv_text, "1995/96", "fd/E0")
    assert len(rows) == 1 and rows[0]["tarih"] == "1995-08-19" and rows[0]["iy_ev"] == 2


def test_espn_rows_filters_women_and_marks_extra_time():
    leagues = {"1": ("uefa.champions", "UEFA Champions League"), "2": ("usa.nwsl", "NWSL")}
    comp = [
        {"d": "2020-08-15", "l": 1, "s": "2019-20-uefa-champions", "h": "A", "a": "B", "hg": 2, "ag": 2, "st": "PEN", "id": 1},
        {"d": "2020-08-16", "l": 2, "s": "2020-nwsl", "h": "C", "a": "D", "hg": 1, "ag": 0, "st": "FT", "id": 2},
        {"d": "2020-08-17", "l": 1, "s": "2019-20-uefa-champions", "h": "E", "a": "F", "hg": 1, "ag": 0, "st": "FT", "id": 3},
    ]
    rows = A.espn_rows(comp, leagues)
    assert len(rows) == 2
    assert rows[0]["hg"] is None and rows[0]["durum"] == "PEN" and "2-2" in rows[0]["ham_skor"]
    assert rows[1]["hg"] == 1 and rows[1]["sezon"] == "2019/20"


def test_tur_of_classification():
    assert A.tur_of("espn/uefa.champions") == "kita_kulup"
    assert A.tur_of("espn/fifa.world") == "milli"
    assert A.tur_of("openfootball/england/pl") == "lig"
    assert A.tur_of("espn/eng.fa") == "kupa"
    assert A.tur_of("espn/uefa.europa") == "kita_kulup"  # 'uefa.euro' ile karışmaz
    assert A.tur_of("espn/uefa.euro_u21") == "milli"
    assert A.tur_of("england/2-championship") == "lig"  # 'championship' kıtasal şampiyonlar ligi sayılmaz
    assert A.tur_of("espn/club.friendly") == "hazirlik"


def _row(d, h, a, hg, ag, k, sezon="2018/19"):
    return {"tarih": d, "sezon": sezon, "yarisma": "x", "ev": h, "dep": a, "hg": hg, "ag": ag, "iy_ev": None, "iy_dep": None,
            "durum": "FT", "ham_skor": None, "kaynak": k}


def test_dedupe_priority_window_and_external():
    rows = [_row("2018-09-01", "Arsenal FC", "Chelsea", 2, 1, "espn"),
            _row("2018-09-02", "Arsenal", "Chelsea FC", 2, 1, "openfootball"),  # ±1 gün, aynı maç
            _row("2018-09-01", "Arsenal FC", "Chelsea", 1, 1, "espn"),  # farklı skor: farklı kayıt
            _row("2018-09-05", "X", "Y", 0, 0, "espn")]
    out, st = A.dedupe(rows, {"openfootball": 1, "espn": 6})
    assert len(out) == 3 and st["tekrar"] == 1
    assert [r["kaynak"] for r in out if r["ev"].startswith("Arsenal") and r["hg"] == 2] == ["openfootball"]
    seen = {("2018-09-05", A.team_key("X")[:8], A.team_key("Y")[:8], (0, 0))}
    out2, st2 = A.dedupe(rows, {"openfootball": 1, "espn": 6}, seen)
    assert st2["dis_tekrar"] == 1 and len(out2) == 2


def test_dateless_wiki_rows_dropped_when_dated_exists():
    rows = [_row("2018-09-01", "Arsenal FC", "Chelsea", 2, 1, "openfootball"),
            _row("", "Arsenal", "Chelsea", 2, 1, "wikipedia"),
            _row("", "Spurs", "West Ham", 3, 0, "wikipedia")]
    out, _ = A.dedupe(rows, {"openfootball": 1, "wikipedia": 5})
    assert [r["kaynak"] for r in out] == ["openfootball", "wikipedia"] and out[1]["ev"] == "Spurs"


def test_wiki_season_matrix_and_scorers():
    html = """<table><tr><th>Pos</th><th>Team</th><th>Pts</th></tr>
    <tr><td>1</td><td>Alpha FC</td><td>6</td></tr><tr><td>2</td><td>Beta United</td><td>3</td></tr></table>
    <table><tr><th>Home \\ Away</th><th>ALP</th><th>BET</th></tr>
    <tr><td>Alpha FC</td><td>—</td><td>2–0</td></tr><tr><td>Beta United</td><td>1–3</td><td>—</td></tr></table>
    <table><tr><th>Rank</th><th>Goalscorer</th><th>Team</th><th>Goals</th></tr>
    <tr><td>1</td><td>Ali Veli</td><td>Alpha FC</td><td>12</td></tr></table>"""
    r = A.parse_wiki_season(html)
    assert ("Alpha FC", "Beta United", 2, 0) in r["maclar"] and ("Beta United", "Alpha FC", 1, 3) in r["maclar"]
    assert r["golculer"] == [("Ali Veli", "Alpha FC", 12)]


def test_wiki_matrix_unresolvable_labels_skipped():
    html = """<table><tr><th>Pos</th><th>Team</th><th>Pts</th></tr><tr><td>1</td><td>Alpha FC</td><td>6</td></tr></table>
    <table><tr><th>Home \\ Away</th><th>ZZZ</th><th>QQQ</th></tr><tr><td>ZZZ</td><td>—</td><td>1–0</td></tr><tr><td>QQQ</td><td>0–1</td><td>—</td></tr></table>"""
    assert A.parse_wiki_season(html)["maclar"] == []  # uydurma eşleme yok


def test_inline_dates_and_espn_season_slugs():
    txt = "= World Cup 2010\n\n▪ Group A\n\nFri Jun 11 16:00    South Africa  1-1  Mexico      @ Soccer City, Johannesburg\n" \
          "16 June    Brazil   5-0   Mexico    @ Geneva\n"
    rows = A.parse_football_txt(txt, "worldcup/2010--south-africa/cup.txt", "wc")
    assert [r["tarih"] for r in rows] == ["2010-06-11", "2010-06-16"] and rows[0]["ev"] == "South Africa" and rows[1]["ev"] == "Brazil"
    base = {"d": "2015-03-01", "l": "7", "h": "A", "a": "B", "hg": 1, "ag": 0, "st": "FT"}
    sez = [A.espn_rows([{**base, "s": s}])[0]["sezon"] for s in ("2014-2015-x", "20142015-y", "2014-15-z", "2015-torneo", "regular-season")]
    assert sez == ["2014/15", "2014/15", "2014/15", "2015", "2015"]


def test_espn_rows_drops_negative_scores():
    base = {"d": "2008-05-01", "l": "7", "s": "2008-x", "h": "A", "a": "B", "st": "FT"}
    assert A.espn_rows([{**base, "hg": 5, "ag": -1}, {**base, "hg": 1, "ag": 0}]) and len(A.espn_rows([{**base, "hg": 5, "ag": -1}])) == 0
