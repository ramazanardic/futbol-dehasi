"""Live ESPN international + club fixture/odds fetcher and match history synchronizer."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import datetime as dt
import difflib
from pathlib import Path
import unicodedata

import pandas as pd
import requests

from quantfoot.data.loader import default_data_dir, ensure_file

INTL_RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
ESPN_LEAGUE_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

ESPN_CLUB_LEAGUES: dict[str, str] = {
    "E0": "eng.1",
    "E1": "eng.2",
    "SP1": "esp.1",
    "D1": "ger.1",
    "I1": "ita.1",
    "F1": "fra.1",
    "T1": "tur.1",
    "N1": "ned.1",
    "P1": "por.1",
    "UCL": "uefa.champions",
}

_TEAM_ALIASES = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Czechia": "Czech Republic",
    "Kyrgyz Republic": "Kyrgyzstan",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "St. Lucia": "Saint Lucia",
    "St. Martin": "Saint Martin",
    "St. Vincent and the Grenadines": "Saint Vincent and the Grenadines",
    "Türkiye": "Turkey",
    "Cabo Verde": "Cape Verde",
    "Republic of Ireland": "Republic of Ireland",
}

_CLUB_ALIASES = {
    "afc bournemouth": "Bournemouth",
    "brighton hove albion": "Brighton",
    "brighton & hove albion": "Brighton",
    "manchester united": "Man United",
    "manchester city": "Man City",
    "tottenham hotspur": "Tottenham",
    "newcastle united": "Newcastle",
    "wolverhampton wanderers": "Wolves",
    "west ham united": "West Ham",
    "nottingham forest": "Nott'm Forest",
    "leeds united": "Leeds",
    "leicester city": "Leicester",
    "ipswich town": "Ipswich",
    "west bromwich albion": "West Brom",
    "blackburn rovers": "Blackburn",
    "bolton wanderers": "Bolton",
    "cardiff city": "Cardiff",
    "coventry city": "Coventry",
    "hull city": "Hull",
    "derby county": "Derby",
    "birmingham city": "Birmingham",
    "charlton athletic": "Charlton",
    "sheffield united": "Sheffield United",
    "sheffield wednesday": "Sheffield Weds",
    "queens park rangers": "QPR",
    "preston north end": "Preston",
    "stoke city": "Stoke",
    "atletico madrid": "Ath Madrid",
    "deportivo": "La Coruna",
    "deportivo la coruna": "La Coruna",
    "athletic club": "Ath Bilbao",
    "real sociedad": "Sociedad",
    "real betis": "Betis",
    "celta vigo": "Celta",
    "rayo vallecano": "Vallecano",
    "rcd espanyol": "Espanol",
    "espanyol": "Espanol",
    "deportivo alaves": "Alaves",
    "alaves": "Alaves",
    "girona fc": "Girona",
    "fc barcelona": "Barcelona",
    "1 fc union berlin": "Union Berlin",
    "1 fsv mainz 05": "Mainz",
    "bayer leverkusen": "Leverkusen",
    "borussia dortmund": "Dortmund",
    "borussia monchengladbach": "M'gladbach",
    "eintracht frankfurt": "Ein Frankfurt",
    "fc augsburg": "Augsburg",
    "bayern munich": "Bayern Munich",
    "vfb stuttgart": "Stuttgart",
    "sc freiburg": "Freiburg",
    "tsg hoffenheim": "Hoffenheim",
    "sv werder bremen": "Werder Bremen",
    "fc cologne": "FC Koln",
    "fc st pauli": "St Pauli",
    "ac milan": "Milan",
    "as roma": "Roma",
    "internazionale": "Inter",
    "hellas verona": "Verona",
    "ss lazio": "Lazio",
    "aj auxerre": "Auxerre",
    "as monaco": "Monaco",
    "le havre ac": "Le Havre",
    "paris saint germain": "Paris SG",
    "stade rennais": "Rennes",
    "olympique marseille": "Marseille",
    "olympique lyonnais": "Lyon",
    "rc lens": "Lens",
    "fenerbahce": "Fenerbahce",
    "besiktas": "Besiktas",
    "caykur rizespor": "Rizespor",
    "gaziantep fk": "Gaziantep",
    "istanbul basaksehir": "Buyuksehir",
    "konyaspor": "Konyaspor",
    "antalyaspor": "Antalyaspor",
    "kasimpasa": "Kasimpasa",
    "alanyaspor": "Alanyaspor",
    "kayserispor": "Kayserispor",
    "goztepe": "Goztepe",
    "ajax amsterdam": "Ajax",
    "feyenoord rotterdam": "Feyenoord",
    "psv eindhoven": "PSV Eindhoven",
    "az alkmaar": "AZ Alkmaar",
    "fc twente": "Twente",
    "fc utrecht": "Utrecht",
    "fc groningen": "Groningen",
    "ado den haag": "Den Haag",
    "fc porto": "Porto",
    "sl benfica": "Benfica",
    "sporting cp": "Sp Lisbon",
    "braga": "Sp Braga",
    "sc braga": "Sp Braga",
    "fc famalicao": "Famalicao",
    "cd nacional": "Nacional",
    "vitoria de guimaraes": "Guimaraes",
    "vitoria guimaraes": "Guimaraes",
}


@dataclass(frozen=True)
class LiveFixture:
    """Normalized live/upcoming fixture with open and current decimal odds."""

    date_utc: str
    status: str
    competition: str
    home_team: str
    away_team: str
    home_canonical: str
    away_canonical: str
    score: str
    open_1x2: tuple[float, float, float] | None
    cur_1x2: tuple[float, float, float] | None
    ou_line: float | None
    ou_odds: tuple[float, float] | None
    ah_line: float | None
    ah_odds: tuple[float, float] | None
    division: str | None = None
    event_id: str | None = None


def _ascii_key(name: str) -> str:
    norm = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(ch if ch.isalnum() else " " for ch in norm.lower())
    return " ".join(cleaned.split())


def normalize_international_team(name: str) -> str:
    """Map ESPN international display names to canonical martj42 team names."""
    return _TEAM_ALIASES.get(name, name)


def normalize_club_team(name: str, known_teams: set[str] | None = None) -> str:
    """Map ESPN club display names to canonical Matches.csv team names."""
    if known_teams and name in known_teams:
        return name
    key = _ascii_key(name)
    alias = _CLUB_ALIASES.get(key)
    if alias and (known_teams is None or alias in known_teams):
        return alias
    if known_teams:
        ascii_map = {_ascii_key(t): t for t in known_teams}
        if key in ascii_map:
            return ascii_map[key]
        stripped = " ".join(w for w in key.split() if w not in {"fc", "ac", "as", "sc", "rc", "cf", "fk", "sk"})
        if stripped in ascii_map:
            return ascii_map[stripped]
        close = difflib.get_close_matches(name, sorted(known_teams), n=1, cutoff=0.72)
        if close:
            return close[0]
    return alias or name


def american_to_decimal(odds_str: str | float | int | None) -> float | None:
    """Convert American odds string (e.g. '-145', '+240', 'EVEN') to decimal odds."""
    if odds_str is None:
        return None
    s = str(odds_str).strip().upper()
    if s in ("", "OFF", "NONE", "NAN"):
        return None
    if s in ("EVEN", "EV"):
        return 2.0
    try:
        val = float(s)
    except ValueError:
        return None
    if val > 0.0:
        return round(1.0 + val / 100.0, 4)
    if val < 0.0:
        return round(1.0 + 100.0 / abs(val), 4)
    return None


def _extract_odds_side(node: dict | None, side: str, phase_order: tuple[str, ...]) -> tuple[float | None, float | None]:
    if not isinstance(node, dict):
        return None, None
    sub = node.get(side)
    if not isinstance(sub, dict):
        return None, None
    for phase in phase_order:
        entry = sub.get(phase)
        if isinstance(entry, dict) and entry.get("odds") is not None:
            dec = american_to_decimal(entry.get("odds"))
            line_raw = entry.get("line")
            line_val = None
            if line_raw is not None:
                cleaned = str(line_raw).lstrip("oOuU")
                try:
                    line_val = float(cleaned)
                except ValueError:
                    line_val = None
            return dec, line_val
    return None, None


def _parse_espn_events(
    events: list[dict],
    canonical_fn,
    division: str | None = None,
) -> list[LiveFixture]:
    fixtures: list[LiveFixture] = []
    for ev in events:
        comp = ev["competitions"][0]
        competitors = comp["competitors"]
        home_c = next(t for t in competitors if t["homeAway"] == "home")
        away_c = next(t for t in competitors if t["homeAway"] == "away")
        home_name = home_c["team"]["displayName"]
        away_name = away_c["team"]["displayName"]
        score = f"{home_c.get('score', '0')}-{away_c.get('score', '0')}"
        status = ev["status"]["type"]["name"]
        slug = (ev.get("season") or {}).get("slug", "")

        open_1x2 = None
        cur_1x2 = None
        ou_line = None
        ou_odds = None
        ah_line = None
        ah_odds = None

        odds_list = comp.get("odds") or []
        if odds_list and isinstance(odds_list[0], dict):
            o = odds_list[0]
            ml = o.get("moneyline") or {}
            oh_o, _ = _extract_odds_side(ml, "home", ("open",))
            od_o, _ = _extract_odds_side(ml, "draw", ("open",))
            oa_o, _ = _extract_odds_side(ml, "away", ("open",))
            if oh_o and od_o and oa_o:
                open_1x2 = (oh_o, od_o, oa_o)

            oh_c, _ = _extract_odds_side(ml, "home", ("current", "close", "open"))
            od_c, _ = _extract_odds_side(ml, "draw", ("current", "close", "open"))
            oa_c, _ = _extract_odds_side(ml, "away", ("current", "close", "open"))
            if oh_c and od_c and oa_c:
                cur_1x2 = (oh_c, od_c, oa_c)

            tot = o.get("total") or {}
            ou_o, line_o = _extract_odds_side(tot, "over", ("current", "close", "open"))
            ou_u, _ = _extract_odds_side(tot, "under", ("current", "close", "open"))
            if ou_o and ou_u and line_o is not None:
                ou_line = line_o
                ou_odds = (ou_o, ou_u)

            sp = o.get("pointSpread") or {}
            sp_h, line_sp = _extract_odds_side(sp, "home", ("current", "close", "open"))
            sp_a, _ = _extract_odds_side(sp, "away", ("current", "close", "open"))
            if sp_h and sp_a and line_sp is not None:
                ah_line = line_sp
                ah_odds = (sp_h, sp_a)

        fixtures.append(
            LiveFixture(
                date_utc=ev["date"],
                status=status,
                competition=slug,
                home_team=home_name,
                away_team=away_name,
                home_canonical=canonical_fn(home_name),
                away_canonical=canonical_fn(away_name),
                score=score,
                open_1x2=open_1x2,
                cur_1x2=cur_1x2,
                ou_line=ou_line,
                ou_odds=ou_odds,
                ah_line=ah_line,
                ah_odds=ah_odds,
                division=division,
                event_id=str(ev.get("id", "")),
            )
        )
    return fixtures


def _fetch_espn_day(date_str: str) -> list[dict]:
    resp = requests.get(ESPN_SCOREBOARD_URL, params={"dates": date_str}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("events", [])


def fetch_league_slate(slug: str, date_str: str) -> tuple[str, list[LiveFixture]]:
    """Fetch one ESPN competition's fixtures (with odds) for YYYYMMDD; returns (league name, fixtures).

    Unlike the all-soccer scoreboard, the competition scoreboard tells us the league slug
    (e.g. 'eng.1', 'uefa.wchampions'), which the goal-regime and calibration guards need.
    """
    resp = requests.get(f"{ESPN_LEAGUE_BASE}/{slug}/scoreboard", params={"dates": date_str}, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    leagues = payload.get("leagues") or [{}]
    name = str(leagues[0].get("name") or slug)
    return name, _parse_espn_events(payload.get("events", []), lambda n: n)


def fetch_espn_slate(date_str: str) -> list[LiveFixture]:
    """Fetch scheduled, live, and finished soccer fixtures with odds for YYYYMMDD."""
    return _parse_espn_events(_fetch_espn_day(date_str), normalize_international_team)


def fetch_club_slate(
    divisions: list[str] | None = None,
    known_teams: set[str] | None = None,
) -> list[LiveFixture]:
    """Fetch upcoming scheduled club + UCL fixtures and live odds from ESPN."""
    target_divs = [d for d in (divisions or list(ESPN_CLUB_LEAGUES.keys())) if d in ESPN_CLUB_LEAGUES]

    def _fetch_div(div_code: str) -> list[LiveFixture]:
        slug = ESPN_CLUB_LEAGUES[div_code]
        try:
            resp = requests.get(f"{ESPN_LEAGUE_BASE}/{slug}/scoreboard", timeout=10)
            resp.raise_for_status()
            evs = resp.json().get("events", [])
            return _parse_espn_events(evs, lambda n: normalize_club_team(n, known_teams), division=div_code)
        except requests.RequestException:
            return []

    out: list[LiveFixture] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for batch in pool.map(_fetch_div, target_divs):
            out.extend(batch)
    return out


def sync_club_recent_results(
    hist_df: pd.DataFrame,
    divisions: list[str] | None = None,
) -> pd.DataFrame:
    """Sync recent completed 2026-27 matches from ESPN team schedules on top of Matches.csv."""
    if hist_df.empty:
        return hist_df
    known_teams = set(hist_df["HomeTeam"]).union(set(hist_df["AwayTeam"]))
    max_csv_date = pd.to_datetime(hist_df["MatchDate"]).max()
    target_divs = [d for d in (divisions or ["E0", "E1", "SP1", "D1", "I1", "F1", "T1", "N1", "P1"]) if d in ESPN_CLUB_LEAGUES]

    def _sync_div(div_code: str) -> list[dict]:
        slug = ESPN_CLUB_LEAGUES[div_code]
        rows: list[dict] = []
        try:
            t_resp = requests.get(f"{ESPN_LEAGUE_BASE}/{slug}/teams", timeout=10)
            t_resp.raise_for_status()
            teams = t_resp.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
            t_ids = [t["team"]["id"] for t in teams]
        except requests.RequestException:
            return rows

        def _fetch_sched(tid: str) -> list[dict]:
            try:
                sr = requests.get(f"{ESPN_LEAGUE_BASE}/{slug}/teams/{tid}/schedule", timeout=10).json()
                return sr.get("events", [])
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=6) as sub_pool:
            for evs in sub_pool.map(_fetch_sched, t_ids):
                for ev in evs:
                    comp = (ev.get("competitions") or [{}])[0]
                    if comp.get("status", {}).get("type", {}).get("name") != "STATUS_FULL_TIME":
                        continue
                    mdate = pd.Timestamp(ev["date"][:10])
                    if mdate <= max_csv_date:
                        continue
                    comps = comp.get("competitors", [])
                    if len(comps) < 2:
                        continue
                    hc = next((c for c in comps if c.get("homeAway") == "home"), None)
                    ac = next((c for c in comps if c.get("homeAway") == "away"), None)
                    if hc is None or ac is None:
                        continue
                    try:
                        sc_h = hc.get("score")
                        sc_a = ac.get("score")
                        hg = float(sc_h.get("value", sc_h.get("displayValue")) if isinstance(sc_h, dict) else sc_h)
                        ag = float(sc_a.get("value", sc_a.get("displayValue")) if isinstance(sc_a, dict) else sc_a)
                    except (AttributeError, TypeError, ValueError):
                        continue
                    ht = normalize_club_team(hc["team"]["displayName"], known_teams)
                    at = normalize_club_team(ac["team"]["displayName"], known_teams)
                    res_char = "H" if hg > ag else ("D" if hg == ag else "A")
                    rows.append(
                        {
                            "Division": div_code,
                            "MatchDate": mdate,
                            "HomeTeam": ht,
                            "AwayTeam": at,
                            "FTHome": hg,
                            "FTAway": ag,
                            "FTResult": res_char,
                            "y": 0 if hg > ag else (1 if hg == ag else 2),
                        }
                    )
        return rows

    extra: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for batch in pool.map(_sync_div, target_divs):
            extra.extend(batch)

    if not extra:
        return hist_df

    ext_df = pd.DataFrame(extra).drop_duplicates(subset=["Division", "MatchDate", "HomeTeam", "AwayTeam"], keep="last")
    combined = pd.concat([hist_df, ext_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["MatchDate", "HomeTeam", "AwayTeam"], keep="first")
    return combined.sort_values(["MatchDate", "Division"]).reset_index(drop=True)


def load_international_history(
    data_dir: Path | None = None,
    sync_through_date: str | None = None,
    min_date: str = "2016-01-01",
    refresh: bool = False,
) -> pd.DataFrame:
    """Load martj42 international results and sync recent completed ESPN matches up to today."""
    target_dir = Path(data_dir) if data_dir is not None else default_data_dir()
    base_csv = ensure_file(target_dir / "international_results.csv", INTL_RESULTS_URL, refresh=refresh)

    df = pd.read_csv(base_csv)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["date", "home_team", "away_team", "home_score", "away_score"]).copy()
    known_teams = set(df["home_team"]).union(set(df["away_team"]))

    last_date = df["date"].max().date()
    end_date = dt.date.fromisoformat(sync_through_date) if sync_through_date else dt.date.today()

    if end_date >= last_date:
        date_strs = [
            (last_date + dt.timedelta(days=i)).strftime("%Y%m%d")
            for i in range(1, (end_date - last_date).days + 1)
        ]
        if date_strs:
            extra_rows = []
            with ThreadPoolExecutor(max_workers=8) as pool:
                for day_events in pool.map(_fetch_espn_day, date_strs):
                    for ev in day_events:
                        if ev["status"]["type"]["name"] != "STATUS_FULL_TIME":
                            continue
                        comp = ev["competitions"][0]
                        teams = comp["competitors"]
                        hc = next(t for t in teams if t["homeAway"] == "home")
                        ac = next(t for t in teams if t["homeAway"] == "away")
                        ht = normalize_international_team(hc["team"]["displayName"])
                        at = normalize_international_team(ac["team"]["displayName"])
                        if ht not in known_teams or at not in known_teams:
                            continue
                        try:
                            hg = int(hc["score"])
                            ag = int(ac["score"])
                        except (TypeError, ValueError):
                            continue
                        extra_rows.append(
                            {
                                "date": pd.Timestamp(ev["date"][:10]),
                                "home_team": ht,
                                "away_team": at,
                                "home_score": hg,
                                "away_score": ag,
                                "tournament": (ev.get("season") or {}).get("slug", "ESPN Sync"),
                                "neutral": False,
                            }
                        )
            if extra_rows:
                df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
                df = df.drop_duplicates(subset=["date", "home_team", "away_team"], keep="last")

    df = df[df["date"] >= pd.Timestamp(min_date)].sort_values("date").reset_index(drop=True)
    return df


def fetch_the_odds_api_slate(
    api_key: str,
    sport_key: str = "soccer_uefa_nations_league",
    regions: str = "eu,uk",
    markets: str = "h2h,totals",
) -> list[dict]:
    """Fetch multi-bookmaker (Pinnacle + EU/UK) decimal odds from The Odds API when a key is provided."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    resp = requests.get(
        url,
        params={"apiKey": api_key, "regions": regions, "markets": markets, "oddsFormat": "decimal"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
