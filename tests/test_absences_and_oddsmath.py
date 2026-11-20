"""Offline unit tests for Transfermarkt absences, OddsMath sharp/steam, football-data AH/season CSVs, and cup/main-market guards."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from quantfoot.cli import build_parser
from quantfoot.data import absences as tm
from quantfoot.data import loader
from quantfoot.data import oddsmath as om
from quantfoot.strategy.coupon_builder import is_cup_competition, is_main_market_selection

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(name: str):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


# ---- 1. Transfermarkt (absences.py) ----------------------------------------------------------


def test_resolve_tm_league_codes():
    assert tm.resolve_tm_league_codes("Almanya Bundesliga") == ["L1"]
    assert tm.resolve_tm_league_codes("almanya bundesliga ") == ["L1"]
    assert tm.resolve_tm_league_codes("T1") == ["TR1"]
    assert tm.resolve_tm_league_codes("E0") == ["GB1"]
    assert tm.resolve_tm_league_codes("L1") == ["L1"]
    assert tm.resolve_tm_league_codes("İtalya Serie C") == ["IT3A", "IT3B", "IT3C"]
    assert tm.resolve_tm_league_codes("Galler Championship, Güney") == ["WA2S"]
    assert tm.resolve_tm_league_codes("Irak Ligi") == ["IRQ1"]
    assert tm.resolve_tm_league_codes("Nikaragua Prmr Ligi, Açılış") == ["NC1A"]
    assert tm.resolve_tm_league_codes("Belçika U21 Pro Ligi, 1. Grup") == ["BE21"]
    assert tm.resolve_tm_league_codes("Bilinmeyen Lig") == []


def test_parse_tm_injuries_and_suspensions_skips_yellow_card_risk():
    inj_html = """
    <html><body>
      <div class="table-header">Puan durumu</div>
      <table class="items"><tbody>
        <tr>
          <td>1</td><td>img</td>
          <td><a href="/bayern/startseite/verein/27" title="Bayern Münih">Bayern</a></td>
          <td>11</td><td>+25</td><td>30</td>
        </tr>
      </tbody></table>
      <div class="table-header">Sakat oyuncular</div>
      <table class="items"><tbody>
        <tr>
          <td><a href="/manuel-neuer/profil/spieler/17259">Manuel Neuer</a> Kaleci</td>
          <td><a href="/bayern/startseite/verein/27" title="Bayern Münih">Bayern</a></td>
          <td>Kas yırtığı</td>
          <td>30 Kas 2026</td>
          <td>4,00 Mn €</td>
        </tr>
      </tbody></table>
    </body></html>
    """
    clubs, injuries = tm.parse_tm_injuries_html(inj_html, "L1")
    assert "27" in clubs
    assert clubs["27"]["rank"] == 1
    assert clubs["27"]["points"] == 30
    assert len(injuries["27"]) == 1
    assert injuries["27"][0]["name"] == "Manuel Neuer"
    assert injuries["27"][0]["is_gk"] is True
    assert injuries["27"][0]["mv_eur"] == pytest.approx(4_000_000.0)

    susp_html = """
    <html><body>
      <div class="table-header">Cezalı oyuncular</div>
      <table class="items"><tbody>
        <tr>
          <td><a href="/dayot/profil/spieler/100">Dayot Upamecano</a> Stoper</td>
          <td><a href="/bayern/startseite/verein/27" title="Bayern Münih">Bayern</a></td>
          <td>Kırmızı kart cezası</td>
          <td>1 maç</td>
        </tr>
      </tbody></table>
      <div class="table-header">Sınırdaki oyuncular</div>
      <table class="items"><tbody>
        <tr>
          <td><a href="/kimmich/profil/spieler/200">Joshua Kimmich</a> Orta saha</td>
          <td><a href="/bayern/startseite/verein/27" title="Bayern Münih">Bayern</a></td>
          <td>4 sarı kart</td>
          <td>-</td>
        </tr>
      </tbody></table>
    </body></html>
    """
    _, suspensions = tm.parse_tm_suspensions_html(susp_html, "L1")
    assert len(suspensions["27"]) == 1
    assert suspensions["27"][0]["name"] == "Dayot Upamecano"
    # Joshua Kimmich (yellow-card risk table) MUST NOT be listed as suspended!
    assert all(p["name"] != "Joshua Kimmich" for p in suspensions["27"])


def test_parse_tm_squad_stats_and_annotate_importance():
    squad_html = """
    <html><body>
      <table class="items"><tbody>
        <tr>
          <td>1</td>
          <td><table class="inline-table"><tr><td><a href="/p/profil/spieler/1">Manuel Neuer</a></td></tr><tr><td>Kaleci</td></tr></table></td>
          <td>39</td><td>DE</td><td>11</td><td>11</td><td>0</td><td>0</td><td>990'</td>
        </tr>
        <tr>
          <td>9</td>
          <td><table class="inline-table"><tr><td><a href="/p/profil/spieler/2">Harry Kane</a></td></tr><tr><td>Santrafor</td></tr></table></td>
          <td>33</td><td>EN</td><td>11</td><td>11</td><td>12</td><td>4</td><td>950'</td>
        </tr>
        <tr>
          <td>2</td>
          <td><table class="inline-table"><tr><td><a href="/p/profil/spieler/3">Dayot Upamecano</a></td></tr><tr><td>Stoper</td></tr></table></td>
          <td>28</td><td>FR</td><td>11</td><td>10</td><td>1</td><td>0</td><td>860'</td>
        </tr>
        <tr>
          <td>30</td>
          <td><table class="inline-table"><tr><td><a href="/p/profil/spieler/4">Genç Yedek</a></td></tr><tr><td>Sol Bek</td></tr></table></td>
          <td>19</td><td>DE</td><td>6</td><td>2</td><td>0</td><td>0</td><td>45'</td>
        </tr>
      </tbody></table>
    </body></html>
    """
    sq = tm.parse_tm_squad_stats_html(squad_html, "27")
    assert sq["ok"] is True
    assert sq["num1_gk"] == "Manuel Neuer"
    assert sq["top_scorers"][0]["name"] == "Harry Kane"

    rec = tm.annotate_club_absences(
        {"club_id": "27", "name": "Bayern Münih", "rank": 1},
        injuries=[
            {"name": "Manuel Neuer", "pos": "Kaleci", "reason": "Kas", "is_gk": True},
            {"name": "Harry Kane", "pos": "Santrafor", "reason": "Bilek", "is_gk": False},
            {"name": "Genç Yedek", "pos": "Sol Bek", "reason": "Grip", "is_gk": False},
        ],
        suspensions=[
            {"name": "Dayot Upamecano", "pos": "Stoper", "reason": "Kırmızı", "is_gk": False},
        ],
        squad_stats=sq,
    )
    assert rec["gk1_out"] is True
    assert rec["top_scorer_out"] is True
    assert rec["def_core_out"] == 1
    assert rec["att_core_out"] == 1
    assert len(rec["critical_absences"]) == 3  # Bench player excluded from critical_absences
    by_name = {a["name"]: a["importance"] for a in rec["injuries"] + rec["suspensions"]}
    assert "GK1" in by_name["Manuel Neuer"]
    assert "TOP_SCORER(12G)" in by_name["Harry Kane"]
    assert by_name["Genç Yedek"] == "BENCH"

    alerts = tm.build_side_alerts("Ev", rec)
    assert any("1. kaleci" in a for a in alerts)
    assert any("golcü eksik" in a for a in alerts)
    brief = tm.format_tm_absence_brief(rec)
    assert "Manuel Neuer" in brief and "GK1" in brief


# ---- 2. OddsMath (oddsmath.py) ---------------------------------------------------------------


def test_oddsmath_1x2_priority_steam_and_schema_guard():
    # Wrong schema (cat_id=4 Draw No Bet) MUST be rejected cleanly
    dnb_payload = {
        "schema": ["1", "2"],
        "subcategory": {"Handicap": "0"},
        "data": {"BetInAsia": {"live": {"1": 1.85, "2": 2.05}}},
    }
    assert om.parse_oddsmath_1x2_payload(dnb_payload)["1x2"] is None
    assert om.parse_oddsmath_ou_payload(dnb_payload, expected_total="2.5") is None

    # Valid 1X2 payload: BetInAsia must beat Bet365 and compute positive home steam
    valid_1x2 = {
        "schema": ["1", "X", "2"],
        "data": {
            "Bet365": {"live": {"1": 1.75, "X": 3.70, "2": 4.40}, "first": {"1": 1.95, "X": 3.50, "2": 3.80}},
            "BetInAsia": {"live": {"1": 1.80, "X": 3.85, "2": 4.65}, "first": {"1": 2.10, "X": 3.55, "2": 3.60}},
            "BadVigBook": {"live": {"1": 1.30, "X": 2.50, "2": 2.50}},  # vig > 50%, rejected
        },
    }
    parsed = om.parse_oddsmath_1x2_payload(valid_1x2)
    assert parsed["book_1x2"] == "BetInAsia"
    assert parsed["book_rank"] == 0
    assert parsed["books_count"] == 2
    assert parsed["1x2"] == [1.80, 3.85, 4.65]
    assert parsed["steam_1x2"] is not None
    assert parsed["steam_1x2"][0] > 0.05  # home drifted shorter => positive probability steam

    # Valid O/U 2.5 vs mismatched O/U 1.5 guard
    valid_ou25 = {
        "schema": ["O", "U"],
        "subcategory": {"Total": "2.5"},
        "data": {
            "BetInAsia": {"live": {"O": 1.92, "U": 1.96}},
            "Bet365": {"live": {"O": 1.88, "U": 1.92}},
        },
    }
    ou25 = om.parse_oddsmath_ou_payload(valid_ou25, expected_total="2.5")
    assert ou25 is not None and ou25["book"] == "BetInAsia"
    assert om.parse_oddsmath_ou_payload(valid_ou25, expected_total="1.5") is None


def test_oddsmath_women_separation_and_reference_conversion():
    day_payload = {
        "data": {
            "10": {
                "name": "Spain Primera",
                "events": {
                    "5001": {
                        "hometeam_name": "Barcelona",
                        "awayteam_name": "Sevilla",
                        "time": "2026-11-20 21:00:00",
                        "live": False,
                    },
                },
            },
            "11": {
                "name": "Spain Liga F Women",
                "events": {
                    "5002": {
                        "hometeam_name": "Barcelona Women",
                        "awayteam_name": "Sevilla Women",
                        "time": "2026-11-20 21:00:00",
                        "live": False,
                    },
                },
            },
        }
    }
    events = om.parse_oddsmath_day_payload(day_payload)
    assert len(events) == 2
    ko_utc = dt.datetime(2026, 11, 20, 18, 0, tzinfo=dt.timezone.utc)

    hit_w, _ = om.match_event_to_oddsmath("Barcelona (K)", "Sevilla (K)", ko_utc, events, league="İspanya Kadınlar Ligi")
    assert hit_w is not None and hit_w["id"] == "5002"

    hit_m, _ = om.match_event_to_oddsmath("Barcelona", "Sevilla", ko_utc, events, league="İspanya La Liga")
    assert hit_m is not None and hit_m["id"] == "5001"

    ng = _load_script("nesine_global")
    ref = om.oddsmath_to_reference(
        hit_m,
        {
            "1x2": [1.45, 4.80, 7.20],
            "book_1x2": "BetInAsia",
            "book_rank": 0,
            "vig_1x2": 0.036,
            "books_count": 10,
            "steam_1x2": [0.04, -0.02, -0.02],
            "ou": {
                "2.5": {"book": "BetInAsia", "odds": [1.75, 2.15], "vig": 0.036},
                "3.5": {"book": "BetInAsia", "odds": [2.75, 1.48], "vig": 0.039},
            },
        },
    )
    assert ref is not None
    assert ref["source"] == "OddsMath (BetInAsia/Pinnacle)"
    assert ref["ou"] == [2.5, [1.75, 2.15]]
    direct = ng.direct_probabilities(ref)
    assert "2.5 Üst" in direct and "3.5 Alt" in direct
    assert direct["2.5 Üst"] + direct["2.5 Alt"] == pytest.approx(1.0, abs=1e-4)


# ---- 3. football-data.co.uk AH extraction, Season CSV download & loader merge ----------------


def test_fetch_global_odds_pinnacle_ah_and_season_history(tmp_path, monkeypatch):
    fgo = _load_script("fetch_global_odds")
    monkeypatch.setattr(fgo, "OUT", tmp_path)

    fixtures_csv = (
        "Div,Date,Time,HomeTeam,AwayTeam,PSH,PSD,PSA,P>2.5,P<2.5,AHh,PAHH,PAHA\n"
        "E0,21/11/2026,15:00,Arsenal,Chelsea,1.85,3.70,4.50,1.78,2.10,-0.75,2.04,1.88\n"
    )
    season_csv = (
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A,PSH,PSD,PSA,AHh,PAHH,PAHA\n"
        "E0,15/11/2026,15:00,Arsenal,Liverpool,2,1,H,1,0,H,15,9,6,3,7,4,1,2,0,0,2.10,3.50,3.40,2.15,3.60,3.50,-0.25,1.90,2.00\n"
    )

    def _fake_get(url: str, **params):
        if "fixtures.csv" in url and "new_league" not in url:
            return SimpleNamespace(status_code=200, content=fixtures_csv.encode("utf-8"), raise_for_status=lambda: None)
        if "new_league_fixtures.csv" in url:
            return SimpleNamespace(status_code=200, content=b"Country,League,Date,Time,Home,Away\n", raise_for_status=lambda: None)
        if "/mmz4281/2627/E0.csv" in url:
            return SimpleNamespace(status_code=200, content=season_csv.encode("utf-8"), raise_for_status=lambda: None)
        return SimpleNamespace(status_code=404, content=b"Not Found", raise_for_status=lambda: None)

    monkeypatch.setattr(fgo, "_get", _fake_get)
    refs = fgo.football_data()
    assert len(refs) == 1
    assert refs[0]["source"] == "Pinnacle (football-data)"
    assert refs[0]["ou"] == [2.5, [1.78, 2.10]]
    assert refs[0]["ah"] == [-0.75, [2.04, 1.88]]

    saved = fgo.fetch_season_history(season="2627", divisions=("E0", "BAD"), out_dir=tmp_path)
    assert saved == 1
    assert (tmp_path / "season_2627" / "E0.csv").exists()
    assert not (tmp_path / "season_2627" / "BAD.csv").exists()

    # Verify loader.load_season_history_overrides + load_matches(include_season_history=True)
    data_root = tmp_path / "data"
    season_dir = data_root / "global_odds" / "latest" / "season_2627"
    season_dir.mkdir(parents=True)
    (season_dir / "E0.csv").write_text(season_csv, encoding="utf-8")

    base_matches = pd.DataFrame(
        [
            {
                "Division": "E0",
                "MatchDate": "2026-11-01",
                "MatchTime": "15:00",
                "HomeTeam": "Chelsea",
                "AwayTeam": "Tottenham",
                "FTHome": 1,
                "FTAway": 1,
                "FTResult": "D",
                "OddHome": 2.0,
                "OddDraw": 3.5,
                "OddAway": 3.6,
                "HandiSize": -0.3,
            }
        ]
    )
    base_matches.to_csv(data_root / "matches.csv", index=False)

    df_plain = loader.load_matches(data_dir=data_root, leagues=["E0"], include_season_history=False)
    assert len(df_plain) == 1

    df_merged = loader.load_matches(data_dir=data_root, leagues=["E0"], include_season_history=True)
    assert len(df_merged) == 2
    assert set(df_merged["HomeTeam"]) == {"Chelsea", "Arsenal"}
    assert df_merged.loc[df_merged["HomeTeam"] == "Arsenal", "PinHome"].iloc[0] == pytest.approx(2.15)


# ---- 4. Strategy guards, nesine_kupon filters & CLI ------------------------------------------


def test_cup_and_main_market_guards_in_nesine_kupon():
    assert is_cup_competition("Portekiz Kupası") is True
    assert is_cup_competition("Mısır Kupası") is True
    assert is_cup_competition("Arjantin Primera Lpf, Clausura Playoff") is True
    assert is_cup_competition("Malta Premier Lig, Düşme Turu") is True
    assert is_cup_competition("İtalya Serie B") is False
    assert is_cup_competition("Kolombiya DIMAYOR Grup B") is False
    assert is_cup_competition("Almanya Bundesliga") is False

    assert is_main_market_selection("MS 1") is True
    assert is_main_market_selection("ÇŞ 10") is True
    assert is_main_market_selection("2.5 Üst") is True
    assert is_main_market_selection("3.5 Alt") is True
    assert is_main_market_selection("KG Var") is True
    assert is_main_market_selection("İY/MS 1/1") is False
    assert is_main_market_selection("2Y 1") is False
    assert is_main_market_selection("2-3 Gol") is False
    assert is_main_market_selection("MS 1 & 2.5 Üst") is False

    kupon = _load_script("nesine_kupon")
    now = dt.datetime(2026, 11, 20, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    sels = [
        {"market": "MS", "selection": "1", "name": "MS 1", "odds": 1.60, "fair_prob": 0.62, "ev": -0.008, "mbs": 1, "direct": True},
        {"market": "Gol Aralığı", "selection": "2-3 Gol", "name": "2-3 Gol", "odds": 1.95, "fair_prob": 0.56, "ev": 0.092, "mbs": 1, "direct": False},
    ]
    league_match = {
        "status": "fiyatlandı",
        "reference": "OddsMath (BetInAsia/Pinnacle)",
        "kickoff_iso": "2026-11-20T20:00:00+03:00",
        "kickoff": "2026-11-20 20:00",
        "code": 101,
        "league": "Almanya Bundesliga",
        "home": "Mainz",
        "away": "Hoffenheim",
        "selections": sels,
    }
    cup_match = dict(league_match, code=102, league="Portekiz Kupası", home="Porto", away="Braga")

    # Default: both matches included, both selections kept
    pools_default = kupon.candidates([league_match, cup_match], now, min_odds=1.20, min_prob=0.55, allow_espn=False)
    assert len(pools_default) == 2

    # --kupasiz --ana-pazar: cup match dropped AND exotic '2-3 Gol' dropped
    pools_strict = kupon.candidates(
        [league_match, cup_match],
        now,
        min_odds=1.20,
        min_prob=0.55,
        allow_espn=False,
        exclude_cups=True,
        main_markets_only=True,
    )
    assert len(pools_strict) == 1
    assert pools_strict[0][0]["code"] == 101
    assert [leg["name"] for leg in pools_strict[0]] == ["MS 1"]


def test_nesine_global_steam_and_tm_rendering():
    ng = _load_script("nesine_global")
    assert ng._source_rank("Pinnacle (football-data)") == 0
    assert ng._source_rank("Smarkets (borsa)") == 1
    assert ng._source_rank("OddsMath (BetInAsia/Pinnacle)") == 2
    assert ng._source_rank("OddsMath (Bet365)") == 3
    assert ng._source_rank("ESPN (DraftKings/ESPN BET)") == 4

    assert ng._steam_flag([0.02, -0.01, -0.01]) is None
    flag = ng._steam_flag([0.065, -0.02, -0.045])
    assert flag is not None and "Ev +6.5p" in flag and "Dep -4.5p" in flag

    row = ng._side_rows(
        {
            "teams": {"home": {"name": "Mainz"}},
            "tm_absences": {
                "home": {
                    "rank": 12,
                    "points": 14,
                    "played": 10,
                    "gd": "-2",
                    "gk1_out": True,
                    "critical_absences": [{"name": "Robin Zentner", "importance": "GK1+CORE", "reason": "Kas"}],
                    "injuries": [{"name": "Robin Zentner", "importance": "GK1+CORE", "reason": "Kas"}],
                    "suspensions": [],
                    "top_scorers": [{"name": "Jonathan Burkardt", "goals": 7, "assists": 2}],
                }
            },
        },
        "home",
    )
    assert "Transfermarkt (2026/27 eksikler)" in row
    assert "Robin Zentner" in row["Transfermarkt (2026/27 eksikler)"]
    assert "1. kaleci eksik" in row["Kaleci"]
    assert "Jonathan Burkardt 7G 2A" in row["Golcüler (TM)"]


def test_cli_parser_supports_intel_and_extended_soccerdata_actions():
    parser = build_parser()
    args_in = parser.parse_args(["intel", "--date", "2026-11-20", "--oddsmath", "--tm", "--league", "L1", "--limit", "5"])
    assert args_in.command == "intel"
    assert args_in.oddsmath is True
    assert args_in.tm is True
    assert args_in.league == "L1"

    for act in (
        "understat-schedule",
        "understat-player-matches",
        "understat-shots",
        "fbref-schedule",
        "fbref-team-matches",
        "fbref-player-matches",
        "fbref-lineup",
        "fbref-events",
        "sofascore-schedule",
        "sofifa-versions",
        "sofifa-players",
        "whoscored-schedule",
        "whoscored-events",
    ):
        a = parser.parse_args(["soccerdata", "--action", act, "--league", "E0"])
        assert a.action == act


def test_alias_same_kickoff_matching_and_youth_guard():
    assert om.is_youth_or_reserve_match("İtalya Serie B", "Palermo", "Bari") is False
    assert om.is_youth_or_reserve_match("Kolombiya DIMAYOR Grup B", "Tolima", "Once Caldas") is False
    assert om.is_youth_or_reserve_match("Tunus 1. Lig", "Olympique B.", "AS Marsa") is False
    assert om.is_youth_or_reserve_match("İspanya Gençler Onur Klasmanı", "Real Madrid U19", "Trival U19") is True
    assert om.is_women_match("", "Union Berlin (W)", "Bayer Leverkusen (W)") is True

    # OddsMath live API uses 'history' (newest-first) for opening odds -> steam must be computed from history[-1]
    hist_payload = {
        "schema": ["1", "X", "2"],
        "data": {
            "BetInAsia": {
                "live": {"1": 1.70, "X": 3.80, "2": 5.00},
                "history": [
                    {"updated": "2026-11-20 03:00:00", "1": 1.70, "X": 3.80, "2": 5.00},
                    {"updated": "2026-11-19 15:00:00", "1": 2.05, "X": 3.50, "2": 3.70},
                ],
            }
        },
    }
    parsed_h = om.parse_oddsmath_1x2_payload(hist_payload)
    assert parsed_h["steam_1x2"] is not None
    assert parsed_h["steam_1x2"][0] > 0.08

    ko = dt.datetime(2026, 11, 20, 19, 45, tzinfo=dt.timezone.utc)
    pool = [
        {"id": "1", "league": "Wales - Premier League", "home": "The New Saints", "away": "Trefelin", "kickoff": ko},
        {"id": "2", "league": "Austria - Erste Liga", "home": "Austria Salzburg", "away": "Trenkwalder Admira", "kickoff": ko},
        {"id": "3", "league": "Uganda - Super League", "home": "Uganda Revenue Authority", "away": "Ntungasaze FC", "kickoff": ko},
        {"id": "4", "league": "Uzbekistan - PFL", "home": "Olmaliq FK", "away": "Qizilqum Zarafshon", "kickoff": ko},
        {"id": "5", "league": "Iran - Pro League", "home": "Fajr Sepasi", "away": "Bahman Shiraz", "kickoff": ko},
    ]
    for home, away, expected_id in (
        ("TNS", "Trefelin", "1"),
        ("SV Austria Salzburg", "Admira Wacker", "2"),
        ("URA", "Ntungasaze", "3"),
        ("FK Agmk", "Qizilqum Zarafshon", "4"),
        ("Fajr Sepasi", "Chador Malu Y.", "5"),
    ):
        hit, _ = om.match_event_to_oddsmath(home, away, ko, pool)
        assert hit is not None and hit["id"] == expected_id


def test_three_tier_classification_and_gunluk_analiz_tm_fallback():
    ng = _load_script("nesine_global")
    ga = _load_script("gunluk_analiz")

    assert ng.is_synthetic_special("Almanya Bundesliga Haftalık Bahisler", "Bundesliga - 10. Hafta (9 Maç)") is True
    assert ng.is_synthetic_special("Almanya Bundesliga", "Mainz") is False

    assert ng.classify_price_tier("fiyatlandı", "OddsMath (BetInAsia/Pinnacle)") == "keskin"
    assert ng.classify_price_tier("fiyatlandı", "Matchbook + Smarkets (borsa)") == "keskin"
    assert ng.classify_price_tier("fiyatlandı", "OddsMath (Marathonbet)") == "global_buro"
    assert ng.classify_price_tier("fiyatlandı", "ESPN (DraftKings/ESPN BET)") == "global_buro"
    assert ng.classify_price_tier(ng.NESINE_ONLY_STATUS, "Nesine (yerel, düşük güven)") == "dusuk_guven"
    assert ng.classify_price_tier("özel bahis (maç değil) — fiyatlanmadı") == "ozel_bahis"

    # Transfermarkt fallback populates form column when ESPN teams is empty
    tm_only_research = {
        "teams": {},
        "tm_absences": {
            "home": {"rank": 3, "points": 24, "gk1_out": True, "critical_absences": [{"name": "GK"}]},
        },
    }
    txt = ga._form(tm_only_research, "home")
    assert "TM #3 24p" in txt and "1.kaleci yok" in txt

    # best_pick: sharp always ok; unresearched/flagged global_buro rejected; BOTH-teams-researched clean global_buro >=62% accepted!
    sel = [{"market": "MS", "selection": "1", "name": "MS 1", "odds": 1.55, "fair_prob": 0.65, "ev": 0.007, "direct": True}]
    m_sharp = {"status": "fiyatlandı", "reference": "OddsMath (BetInAsia/Pinnacle)", "price_tier": "keskin", "selections": sel}
    m_book_unres = {"status": "fiyatlandı", "reference": "OddsMath (Marathonbet)", "price_tier": "global_buro", "selections": sel}
    m_book_res = {
        "status": "fiyatlandı",
        "reference": "OddsMath (Marathonbet)",
        "price_tier": "global_buro",
        "league": "İran Pro Ligi",
        "selections": sel,
        "research": {
            "teams": {},
            "flags": [],
            "tm_absences": {"home": {"rank": 2, "points": 25}, "away": {"rank": 11, "points": 12}},
        },
    }
    m_book_flag = {
        **m_book_res,
        "research": {**m_book_res["research"], "flags": ["TM: Ev: 1. kaleci eksik"]},
    }
    pick_s, _ = ga.best_pick(m_sharp)
    pick_unres, why_unres = ga.best_pick(m_book_unres)
    pick_res, tag_res = ga.best_pick(m_book_res)
    pick_flag, why_flag = ga.best_pick(m_book_flag)
    assert pick_s is not None and pick_s["name"] == "MS 1"
    assert pick_unres is None and "araştırma eksik" in why_unres
    assert pick_res is not None and tag_res == "orta güven · araştırmalı"
    assert pick_flag is None and "uyarısı" in why_flag

    # Verify nesine_kupon.candidates accepts clean researched mid-tier with +0.020 extra sigma penalty
    kupon = _load_script("nesine_kupon")
    now = dt.datetime(2026, 11, 20, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
    base_meta = {"kickoff_iso": "2026-11-20T20:00:00+03:00", "kickoff": "2026-11-20 20:00", "home": "A", "away": "B"}
    c_sharp = {**base_meta, **m_sharp, "code": 1, "league": "Almanya Bundesliga", "selections": [{**sel[0], "mbs": 1}]}
    c_mid_ok = {**base_meta, **m_book_res, "code": 2, "selections": [{**sel[0], "mbs": 1}]}
    c_mid_unres = {**base_meta, **m_book_unres, "code": 3, "league": "Kenya", "selections": [{**sel[0], "mbs": 1}]}
    c_mid_flag = {**base_meta, **m_book_flag, "code": 4, "selections": [{**sel[0], "mbs": 1}]}

    pools = kupon.candidates([c_sharp, c_mid_ok, c_mid_unres, c_mid_flag], now, min_odds=1.20, min_prob=0.55, allow_espn=False)
    codes = {p[0]["code"] for p in pools}
    assert codes == {1, 2}  # sharp + clean full-researched mid-tier ONLY
    by_code = {p[0]["code"]: p[0] for p in pools}
    assert by_code[2]["tier"] == "orta"
    assert by_code[2]["sigma"] == pytest.approx(by_code[1]["sigma"] + 0.010, abs=1e-9)  # sharp had no research (+0.01), mid had research (+0.00) + mid penalty (+0.02)

    pools_strict = kupon.candidates(
        [c_sharp, c_mid_ok], now, min_odds=1.20, min_prob=0.55, allow_espn=False, allow_mid_researched=False
    )
    assert {p[0]["code"] for p in pools_strict} == {1}
