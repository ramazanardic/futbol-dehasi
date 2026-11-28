"""Live Transfermarkt injury, suspension, standings, and 2026/27 player-importance intelligence.

Fetches public Transfermarkt league pages (``verletztespieler`` & ``sperrenausfaelle``) and
club seasonal squad statistics (``leistungsdaten/verein/{id}/plus/1``), then classifies every
absent player by genuine on-pitch role:

- ``GK1``: starting goalkeeper (most minutes among goalkeepers in the current season)
- ``TOP_SCORER(nG)``: top-2 club goalscorer with >= 3 goals
- ``TOP_ASSIST(nA)``: top club assister with >= 3 assists
- ``CORE``: >= 50% of the squad's maximum seasonal minutes
- ``ROT``: 20%–50% of seasonal minutes
- ``BENCH``: < 20% of seasonal minutes

Strict hygiene:
- ``Sınırdaki oyuncular`` (yellow-card suspension-risk tables) are explicitly excluded from
  actual suspensions so available players on 4 yellows are never flagged as suspended.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import difflib
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable
import unicodedata

from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter

TM_BASE_URL = "https://www.transfermarkt.com.tr"
TM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _tm_session(pool_size: int = 16) -> requests.Session:
    sess = requests.Session()
    sess.headers.update(TM_HEADERS)
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess

#: QuantFoot division code -> Transfermarkt ``wettbewerb`` code.
DIVISION_TO_TM: dict[str, str] = {
    "E0": "GB1",
    "E1": "GB2",
    "E2": "GB3",
    "SP1": "ES1",
    "SP2": "ES2",
    "D1": "L1",
    "D2": "L2",
    "I1": "IT1",
    "I2": "IT2",
    "F1": "FR1",
    "F2": "FR2",
    "T1": "TR1",
    "TR2": "TR2",
    "N1": "NL1",
    "P1": "PO1",
    "B1": "BE1",
    "SC0": "SC1",
    "G1": "GR1",
}

#: Turkish Nesine / common league name -> list of Transfermarkt ``wettbewerb`` codes.
TM_LEAGUE_MAP: dict[str, list[str]] = {
    # Big-5 + European 1st/2nd/3rd tiers
    "İngiltere Premier Lig": ["GB1"],
    "İngiltere Championship": ["GB2"],
    "İngiltere 1. Lig": ["GB3"],
    "İngiltere 2. Lig": ["GB4"],
    "İngiltere Ulusal Lig": ["CNAT"],
    "Almanya Bundesliga": ["L1"],
    "Almanya Bundesliga 2": ["L2"],
    "Almanya 3. Lig": ["L3"],
    "Almanya Böl. Lig, Bavyera": ["RLB3"],
    "Almanya Böl. Lig, Kuzey Doğu": ["RLN4"],
    "Almanya Böl. Lig, Güney Batı": ["RLSW"],
    "Almanya Böl. Lig, Kuzey": ["RLN3"],
    "Almanya Böl. Lig, Batı": ["RLW3"],
    "İspanya La Liga": ["ES1"],
    "İspanya 2. Lig": ["ES2"],
    "İspanya Primera RFEF": ["E3G1", "E3G2"],
    "İspanya Segunda RFEF": ["E4G1", "E4G2", "E4G3", "E4G4", "E4G5"],
    "Fransa Ligue 1": ["FR1"],
    "Fransa Ligue 2": ["FR2"],
    "İtalya Serie A": ["IT1"],
    "İtalya Serie B": ["IT2"],
    "İtalya Serie C": ["IT3A", "IT3B", "IT3C"],
    "Türkiye Süper Lig": ["TR1"],
    "Türkiye Süper Ligi": ["TR1"],
    "Türkiye 1. Lig": ["TR2"],
    "Türkiye Nesine 2. Lig, Beyaz Grup": ["TR3B"],
    "Hollanda Eredivisie": ["NL1"],
    "Hollanda 1. Lig": ["NL2"],
    "Portekiz Premier Lig": ["PO1"],
    "Portekiz 2. Lig": ["PO2"],
    "Portekiz Kupası": ["PO1", "PO2"],
    "Belçika Pro Lig": ["BE1"],
    "Belçika 2. Lig, İlk Etap": ["BE2"],
    "İskoçya Premier Lig": ["SC1"],
    "İskoçya Championship": ["SC2"],
    "Yunanistan Süper Lig": ["GR1"],
    "Avusturya Bundesliga": ["A1"],
    "Avusturya 2. Lig": ["A2"],
    "İsviçre Süper Lig": ["C1"],
    "İsviçre Challenge Ligi": ["C2"],
    "İsviçre Yükselme 1.Ligi": ["CHPR"],
    "Belarus Premier Lig": ["WER1"],
    "Belarus Pervaya Ligi": ["WER2"],
    "Norveç Eliteserien": ["NO1"],
    "İsveç Allsvenskan": ["SE1"],
    "Danimarka Süper Ligi": ["DK1"],
    "Danimarka 1. Lig": ["DK2"],
    "Finlandiya Veikkausliiga": ["FI1"],
    "Polonya Ekstraklasa": ["PL1"],
    "Polonya 1. Lig": ["PL2"],
    "Polonya 2. Lig": ["PL3"],
    "Rusya Premier Lig": ["RU1"],
    "Ukrayna Premier Ligi": ["UKR1"],
    "Romanya 1. Lig": ["RO1"],
    "Romanya 2. Lig": ["RO2"],
    "Bulgaristan Parva Ligi": ["BU1"],
    "Çekya 1. Lig": ["TS1"],
    "Çekya 2. Lig": ["TS2"],
    "Hırvatistan HNL": ["KR1"],
    "Hırvatistan Prva NL": ["KR2"],
    "Sırbistan Süper Lig": ["SER1"],
    "Macaristan NB I": ["UNG1"],
    "Slovakya Super Liga": ["SLO1"],
    "Slovenya PrvaLiga": ["SL1"],
    "Slovenya 2. Lig": ["SL2"],
    "Galler Premier Lig": ["WAL1"],
    "Galler Championship, Güney": ["WA2S"],
    "Galler Championship, Kuzey": ["WAL2"],
    "Kuzey İrlanda Premiership": ["NIR1"],
    "Kuzey İrlanda Championship": ["NIR2"],
    "İngiltere U21 Premier Lig Kupası": ["GB21"],
    "Belçika U21 Pro Ligi, 1. Grup": ["BE21"],
    "Letonya Virsliga": ["LET1"],
    "Letonya Kupası": ["LET1"],
    "Azerbaycan Premier Lig": ["AZ1"],
    "Arnavutluk Süper Ligi": ["ALB1"],
    "Kosova Superliga": ["KO1"],
    "Gürcistan Erovnuli Ligi": ["GE1N"],
    "Karadağ 1. CFL": ["MNE1"],
    "Malta Premier Lig, Düşme Turu": ["MAL1"],
    "Kuzey Makedonya 1. MFL": ["MAZ1"],
    # UEFA competitions
    "UEFA Şampiyonlar Ligi": ["CL"],
    "UEFA Avrupa Ligi": ["EL"],
    "UEFA Avrupa Konferans Ligi": ["UCOL"],
    # Middle East, Asia, Oceania, Africa
    "Suudi Arabistan Pro Lig": ["SA1"],
    "Suudi Arabistan 1. Lig": ["SA2L"],
    "Katar Yıldızlar Ligi": ["QSL"],
    "BAE - Arap Körfez Ligi": ["UAE1"],
    "BAE 1.Lig": ["UAE2"],
    "İran Pro Ligi": ["IRN1"],
    "Irak Ligi": ["IRQ1"],
    "Lübnan Premier Lig": ["LIB1"],
    "Japonya J Ligi": ["JAP1"],
    "Güney Kore K-League 1": ["RSK1"],
    "Avustralya A-Ligi": ["AUS1"],
    "Yeni Zelanda Premiership": ["NZNL"],
    "Endonezya 1. Lig": ["IN1L"],
    "Özbekistan Süper Ligi": ["UZ1"],
    "Malezya Süper Ligi": ["MYS1"],
    "Vietnam V-Ligi": ["VIE1"],
    "Hindistan Süper Ligi": ["IND1"],
    "Singapur Premier Lig": ["SIN1"],
    "Hong Kong Premier Lig": ["HGKG"],
    "Tayland Şampiyonası": ["THA1"],
    "Çin Federasyon Kupası": ["CSL"],
    "Mısır Premier Lig": ["EGY1"],
    "Mısır Kupası": ["EGY1", "EGY2"],
    "Mısır 2. Lig": ["EGY2"],
    "Tunus 1. Lig": ["TUN1"],
    "Cezayir 1. Lig": ["ALG1"],
    "Fas Botola Pro": ["MAR1"],
    "Gana Premier Lig": ["GHPL"],
    "Nijerya Premier Ligi": ["NPFL"],
    "Etiyopya Premier Lig": ["ETP1"],
    # Americas
    "ABD Major Lig": ["MLS1"],
    "Brezilya Serie A": ["BRA1"],
    "Brezilya Serie B": ["BRA2"],
    "Arjantin Primera Lpf, Clausura Playoff": ["AR1N"],
    "Arjantin Premier Lig": ["AR1N"],
    "Uruguay Prmr Ligi, Kapanış": ["URU1"],
    "Ekvador Pro Lig": ["EC1N"],
    "Şili Premier Lig": ["CLPD"],
    "Kolombiya DIMAYOR Grup A": ["COLP"],
    "Kolombiya DIMAYOR Grup B": ["COLP"],
    "Meksika Prmr Ligi, Açılış": ["MEXA"],
    "Meksika Liga MX": ["MEXA"],
    "Kosta Rika Prmr Ligi, Açılış": ["CRPD"],
    "Nikaragua Prmr Ligi, Açılış": ["NC1A"],
}

_STOP_RE = re.compile(
    r"\b(fc|cf|sc|ac|sk|fk|nk|cd|ca|club|de|da|the|utd|united|sv|vfb|tsg|rc|ud|ad|sd|sp|bk|"
    r"if|ik|afc|ssc|as|us|ss|uc|cs|cr|al|el|bsc|tsv|sg|fsv|spvgg|vv|vvv|rkc|nac|kvc|kv|ksc|"
    r"rsc|krc|ogc|osc|aj|sm|ea|stade|olympique|sporting|real|atletico|deportivo|"
    r"1|04|05|07|09|1899|1908|1913)\b"
)


def _make_soup(html: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"\(k\)|\(kol\)|\(amt\)|\(w\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = _STOP_RE.sub(" ", s)
    return " ".join(s.split())


def _name_sim(a: str, b: str) -> float:
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(1, len(ta | tb))
    sub = 0.85 if (min(len(na), len(nb)) >= 4 and (na in nb or nb in na)) else 0.0
    return max(ratio, jacc, sub)


def _is_women_match(league: str, home: str, away: str) -> bool:
    txt = f"{league} {home} {away}".lower()
    return bool(re.search(r"kad[ıi]n|\(k\)|\bwomen\b|\bfemin|\bdamen|\bladies\b|vrouwen", txt))


def parse_market_value_eur(txt: str) -> float:
    """Parse Transfermarkt market value strings such as ``'12.50 Mn €'`` or ``'450 Bin €'``."""
    t = str(txt).replace(",", ".").strip()
    m = re.search(r"([\d.]+)\s*(Mn|Bin|m|k)", t, re.I)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2).lower()
    return val * 1e6 if unit in ("mn", "m") else val * 1e3


def extract_club_id(href: str | None) -> str | None:
    """Extract numeric Transfermarkt club ID from a ``/verein/<id>`` URL."""
    if not href:
        return None
    m = re.search(r"/verein/(\d+)", href)
    return m.group(1) if m else None


def _normalized_league_lookup() -> dict[str, list[str]]:
    return {k.strip().lower(): v for k, v in TM_LEAGUE_MAP.items()}


_LEAGUE_MAP_LOWER = _normalized_league_lookup()


def resolve_tm_league_codes(league: str | None) -> list[str]:
    """Map a Nesine league name, QuantFoot division code (``E0``, ``T1``), or raw TM code to TM codes."""
    if not league:
        return []
    key = " ".join(str(league).split())
    if key in TM_LEAGUE_MAP:
        return list(TM_LEAGUE_MAP[key])
    low = key.lower()
    if low in _LEAGUE_MAP_LOWER:
        return list(_LEAGUE_MAP_LOWER[low])
    if low.endswith(" ligi") and (low[:-1] in _LEAGUE_MAP_LOWER):
        return list(_LEAGUE_MAP_LOWER[low[:-1]])
    if low.endswith(" lig") and (low + "i" in _LEAGUE_MAP_LOWER):
        return list(_LEAGUE_MAP_LOWER[low + "i"])
    upper = key.upper()
    if upper in DIVISION_TO_TM:
        return [DIVISION_TO_TM[upper]]
    # Accept direct TM codes like "L1", "TR1", "GB1", "ES1", "IT1", "FR1", "QSL", "CLPD"
    if re.fullmatch(r"[A-Z0-9]{2,5}", upper) and upper in {c for vals in TM_LEAGUE_MAP.values() for c in vals}:
        return [upper]
    return []


# ---- Pure HTML parsers (100% testable offline) -----------------------------------------------


def parse_tm_injuries_html(html: str, code: str) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Parse Transfermarkt ``verletztespieler`` HTML into ``(clubs_with_standings, injuries_by_club_id)``."""
    clubs: dict[str, dict[str, Any]] = {}
    injuries: dict[str, list[dict[str, Any]]] = {}
    soup = _make_soup(html)

    for tbl in soup.select("table.items"):
        prev = tbl.find_previous(["h2", "div"], class_=lambda c: c and ("headline" in c or "table-header" in c))
        hdr = prev.get_text(" ", strip=True).lower() if prev else ""
        if "puan durumu" in hdr:
            for tr in tbl.select("tbody > tr"):
                tds = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
                ca = tr.select_one("a[href*='/verein/']")
                cid = extract_club_id(ca.get("href") if ca else None)
                if cid and len(tds) >= 6:
                    cname = (ca.get("title") or tds[2]).strip()
                    clubs[cid] = {
                        "club_id": cid,
                        "name": cname,
                        "rank": int(tds[0]) if tds[0].isdigit() else None,
                        "played": int(tds[3]) if tds[3].isdigit() else None,
                        "gd": tds[4],
                        "points": int(tds[5]) if tds[5].isdigit() else None,
                        "league_code": code,
                    }
        else:
            for tr in tbl.select("tbody > tr"):
                pa = tr.select_one("a[href*='/profil/spieler/']")
                ca = tr.select_one("a[href*='/verein/']")
                if not pa or not ca:
                    continue
                cid = extract_club_id(ca.get("href"))
                if not cid:
                    continue
                cname = (ca.get("title") or ca.get_text(strip=True)).strip()
                clubs.setdefault(cid, {"club_id": cid, "name": cname, "league_code": code})
                tds = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
                pname = pa.get_text(strip=True)
                pos = tds[0].replace(pname, "").strip() if tds else ""
                reason = tds[2] if len(tds) > 2 else ""
                mv = parse_market_value_eur(tds[4]) if len(tds) > 4 else 0.0
                injuries.setdefault(cid, []).append(
                    {
                        "name": pname,
                        "pos": pos,
                        "reason": reason,
                        "mv_eur": mv,
                        "is_gk": "kaleci" in pos.lower(),
                    }
                )
    return clubs, injuries


def parse_tm_suspensions_html(
    html: str,
    code: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Parse Transfermarkt ``sperrenausfaelle`` HTML, strictly skipping yellow-card risk tables."""
    clubs: dict[str, dict[str, Any]] = {}
    suspensions: dict[str, list[dict[str, Any]]] = {}
    soup = _make_soup(html)

    for tbl in soup.select("table.items"):
        prev = tbl.find_previous(["h2", "div"], class_=lambda c: c and ("headline" in c or "table-header" in c))
        hdr = prev.get_text(" ", strip=True).lower() if prev else ""
        # Strictly skip standings and 'Sınırdaki oyuncular' (1 yellow away from suspension, still eligible!)
        if "puan durumu" in hdr or "sınır" in hdr or "sinir" in hdr or "threat" in hdr or "risk" in hdr:
            continue
        for tr in tbl.select("tbody > tr"):
            pa = tr.select_one("a[href*='/profil/spieler/']")
            ca = tr.select_one("a[href*='/verein/']")
            if not pa or not ca:
                continue
            cid = extract_club_id(ca.get("href"))
            if not cid:
                continue
            cname = (ca.get("title") or ca.get_text(strip=True)).strip()
            clubs.setdefault(cid, {"club_id": cid, "name": cname, "league_code": code})
            tds = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]
            pname = pa.get_text(strip=True)
            pos = tds[0].replace(pname, "").strip() if tds else ""
            reason = tds[2] if len(tds) > 2 else "Cezalı"
            until = tds[3] if len(tds) > 3 else ""
            suspensions.setdefault(cid, []).append(
                {
                    "name": pname,
                    "pos": pos,
                    "reason": reason,
                    "until": until,
                    "is_gk": "kaleci" in pos.lower(),
                }
            )
    return clubs, suspensions


def parse_tm_squad_stats_html(html: str, club_id: str) -> dict[str, Any]:
    """Parse Transfermarkt ``leistungsdaten/verein/{id}/plus/1`` HTML into seasonal squad roles."""
    soup = _make_soup(html)
    tbl = soup.select_one("table.items")
    if not tbl:
        return {"club_id": club_id, "ok": False, "players": []}

    players: list[dict[str, Any]] = []
    max_min = 0

    def _to_int(s: str) -> int:
        s = s.strip()
        return int(s) if s.isdigit() else 0

    for tr in tbl.select("tbody > tr"):
        pa = tr.select_one("a[href*='/profil/spieler/']")
        if not pa:
            continue
        pname = pa.get_text(strip=True)
        pos_td = tr.select_one("table.inline-table tr:nth-of-type(2) td")
        pos = pos_td.get_text(strip=True) if pos_td else ""
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td", recursive=False)]

        mins = 0
        for txt in reversed(tds):
            if "'" in txt:
                digits = re.sub(r"[^\d]", "", txt)
                if digits:
                    mins = int(digits)
                break

        apps = _to_int(tds[5]) if len(tds) > 5 else 0
        goals = _to_int(tds[6]) if len(tds) > 6 else 0
        assists = _to_int(tds[7]) if len(tds) > 7 else 0
        if mins > max_min:
            max_min = mins
        players.append(
            {
                "name": pname,
                "pos": pos,
                "is_gk": "kaleci" in pos.lower() or "goalkeeper" in pos.lower(),
                "apps": apps,
                "goals": goals,
                "assists": assists,
                "minutes": mins,
            }
        )

    denom = max(max_min, 90)
    for p in players:
        p["min_pct"] = round(p["minutes"] / denom * 100.0, 1)

    gks = sorted([p for p in players if p["is_gk"]], key=lambda x: -x["minutes"])
    top_gk = gks[0]["name"] if gks and gks[0]["minutes"] > 0 else None
    top_scorers = sorted([p for p in players if p["goals"] > 0], key=lambda x: (-x["goals"], -x["assists"]))[:3]
    top_assists = sorted([p for p in players if p["assists"] > 0], key=lambda x: (-x["assists"], -x["goals"]))[:3]
    return {
        "club_id": club_id,
        "ok": True,
        "max_minutes": max_min,
        "num1_gk": top_gk,
        "top_scorers": top_scorers,
        "top_assists": top_assists,
        "players": players,
    }


# ---- Live HTTP fetchers ----------------------------------------------------------------------


def fetch_tm_league(code: str, *, timeout: int = 18, session: requests.Session | None = None) -> dict[str, Any]:
    """Fetch live Transfermarkt injuries, suspensions, and league standings for one ``wettbewerb`` code."""
    out: dict[str, Any] = {"code": code, "ok": False, "clubs": {}, "injuries": {}, "suspensions": {}}
    getter = session.get if session is not None else requests.get
    req_kw = {"timeout": timeout} if session is not None else {"headers": TM_HEADERS, "timeout": timeout}

    try:
        r = getter(f"{TM_BASE_URL}/x/verletztespieler/wettbewerb/{code}", **req_kw)
        if r.status_code == 200:
            out["ok"] = True
            clubs, injuries = parse_tm_injuries_html(r.text, code)
            out["clubs"].update(clubs)
            out["injuries"].update(injuries)
    except requests.RequestException:
        pass

    try:
        r2 = getter(f"{TM_BASE_URL}/x/sperrenausfaelle/wettbewerb/{code}", **req_kw)
        if r2.status_code == 200:
            out["ok"] = True
            clubs2, susp = parse_tm_suspensions_html(r2.text, code)
            for cid, cinfo in clubs2.items():
                out["clubs"].setdefault(cid, cinfo)
            out["suspensions"].update(susp)
    except requests.RequestException:
        pass

    if not out["clubs"]:
        try:
            r3 = getter(f"{TM_BASE_URL}/x/startseite/wettbewerb/{code}", **req_kw)
            if r3.status_code == 200:
                soup3 = _make_soup(r3.text)
                for a in soup3.select("table.items a[href*='/verein/']"):
                    cid = extract_club_id(a.get("href"))
                    nm = (a.get("title") or a.get_text(strip=True)).strip()
                    if cid and nm and len(nm) >= 2:
                        out["clubs"].setdefault(cid, {"club_id": cid, "name": nm, "league_code": code})
        except requests.RequestException:
            pass

    return out


def fetch_club_squad_stats(
    club_id: str,
    *,
    timeout: int = 18,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch live current-season player apps/goals/assists/minutes for one Transfermarkt club ID."""
    url = f"{TM_BASE_URL}/x/leistungsdaten/verein/{club_id}/plus/1"
    getter = session.get if session is not None else requests.get
    req_kw = {"timeout": timeout} if session is not None else {"headers": TM_HEADERS, "timeout": timeout}
    try:
        r = getter(url, **req_kw)
        if r.status_code != 200:
            return {"club_id": club_id, "ok": False, "players": []}
        return parse_tm_squad_stats_html(r.text, club_id)
    except requests.RequestException:
        return {"club_id": club_id, "ok": False, "players": []}


# ---- Absence importance classification & matchday aggregator ---------------------------------


def annotate_club_absences(
    club_info: dict[str, Any],
    injuries: list[dict[str, Any]],
    suspensions: list[dict[str, Any]],
    squad_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Annotate every injury/suspension with current-season role importance and critical-absence counters."""
    rec = {
        **club_info,
        "injuries": [dict(x) for x in injuries],
        "suspensions": [dict(x) for x in suspensions],
    }

    if squad_stats and squad_stats.get("ok"):
        rec["top_scorers"] = [
            {"name": p["name"], "goals": p["goals"], "assists": p["assists"], "min_pct": p["min_pct"]}
            for p in squad_stats.get("top_scorers", [])
        ]
        rec["top_assists"] = [
            {"name": p["name"], "goals": p["goals"], "assists": p["assists"], "min_pct": p["min_pct"]}
            for p in squad_stats.get("top_assists", [])
        ]
        rec["num1_gk"] = squad_stats.get("num1_gk")
        p_list = squad_stats.get("players") or []
        top2_scorers = {p["name"] for p in squad_stats.get("top_scorers", [])[:2]}
        top_assister = {squad_stats["top_assists"][0]["name"]} if squad_stats.get("top_assists") else set()

        def _enrich(ab: dict[str, Any]) -> dict[str, Any]:
            best_p, best_s = None, 0.0
            for p in p_list:
                sc = _name_sim(ab["name"], p["name"])
                if sc > best_s:
                    best_s, best_p = sc, p
            if best_p and best_s >= 0.72:
                ab["apps"] = best_p["apps"]
                ab["goals"] = best_p["goals"]
                ab["assists"] = best_p["assists"]
                ab["minutes"] = best_p["minutes"]
                ab["min_pct"] = best_p["min_pct"]
                tags: list[str] = []
                if best_p["name"] == squad_stats.get("num1_gk"):
                    tags.append("GK1")
                if best_p["name"] in top2_scorers and best_p["goals"] >= 3:
                    tags.append(f"TOP_SCORER({best_p['goals']}G)")
                if best_p["name"] in top_assister and best_p["assists"] >= 3:
                    tags.append(f"TOP_ASSIST({best_p['assists']}A)")
                if best_p["min_pct"] >= 50.0:
                    tags.append("CORE")
                elif best_p["min_pct"] >= 20.0:
                    tags.append("ROT")
                else:
                    tags.append("BENCH")
                ab["importance"] = "+".join(tags)
            else:
                ab["importance"] = "UNKNOWN"
            return ab

        rec["injuries"] = [_enrich(x) for x in rec["injuries"]]
        rec["suspensions"] = [_enrich(x) for x in rec["suspensions"]]

    all_abs = rec["injuries"] + rec["suspensions"]
    rec["critical_absences"] = [
        a for a in all_abs if any(k in a.get("importance", "") for k in ("GK1", "TOP_SCORER", "TOP_ASSIST", "CORE"))
    ]
    rec["gk1_out"] = any("GK1" in a.get("importance", "") for a in all_abs)
    rec["top_scorer_out"] = any("TOP_SCORER" in a.get("importance", "") for a in all_abs)
    rec["def_core_out"] = sum(
        1
        for a in rec["critical_absences"]
        if any(w in (a.get("pos") or "").lower() for w in ("stoper", "bek", "defans", "libero", "back", "defen"))
    )
    rec["att_core_out"] = sum(
        1
        for a in rec["critical_absences"]
        if any(w in (a.get("pos") or "").lower() for w in ("santrafor", "forvet", "kanat", "on numara", "hücum", "wing", "forward"))
        or "TOP_SCORER" in a.get("importance", "")
    )
    return rec


def build_side_alerts(side_label: str, club_rec: dict[str, Any] | None) -> list[str]:
    """Generate concise Turkish warning strings for genuinely impactful absences."""
    if not club_rec:
        return []
    alerts: list[str] = []
    if club_rec.get("gk1_out"):
        gk = next((a["name"] for a in club_rec.get("critical_absences", []) if "GK1" in a.get("importance", "")), "1. kaleci")
        alerts.append(f"{side_label}: 1. kaleci ({gk}) eksik")
    if club_rec.get("top_scorer_out"):
        sc_list = [
            f"{a['name']} ({a.get('goals', 0)}G)"
            for a in club_rec.get("critical_absences", [])
            if "TOP_SCORER" in a.get("importance", "")
        ]
        alerts.append(f"{side_label}: golcü eksik ({', '.join(sc_list[:2])})")
    if int(club_rec.get("def_core_out") or 0) >= 2:
        alerts.append(f"{side_label}: {club_rec['def_core_out']} kilit savunma eksiği")
    if int(club_rec.get("att_core_out") or 0) >= 2 and not club_rec.get("top_scorer_out"):
        alerts.append(f"{side_label}: {club_rec['att_core_out']} kilit hücum eksiği")
    return alerts


def format_tm_absence_brief(club_rec: dict[str, Any] | None, *, max_items: int = 5) -> str:
    """Format a club's Transfermarkt absences concisely for Markdown tables and coupon reasoning."""
    if not club_rec:
        return "-"
    crit = club_rec.get("critical_absences") or []
    all_abs = (club_rec.get("injuries") or []) + (club_rec.get("suspensions") or [])
    if not all_abs:
        return "kilit eksik yok"
    ordered = crit + [a for a in all_abs if a not in crit]
    parts = []
    for a in ordered[:max_items]:
        imp = a.get("importance")
        tag = f" [{imp}]" if imp and imp not in ("UNKNOWN", "BENCH") else ""
        reason = a.get("reason") or "eksik"
        parts.append(f"{a['name']}{tag} ({reason})")
    extra = len(ordered) - len(parts)
    if extra > 0:
        parts.append(f"+{extra} diğer")
    return "; ".join(parts)


def fetch_matchday_absences(
    matches: Iterable[dict[str, Any]],
    *,
    fetch_squad_stats: bool = True,
    max_workers: int = 12,
    min_sim: float = 0.58,
    cache_path: Path | str | None = None,
    cache_ttl_hours: float = 4.0,
) -> dict[int | str, dict[str, Any]]:
    """Fetch live Transfermarkt absences + standings + seasonal importance for a matchday slate.

    Each element in ``matches`` should have ``code`` (or index), ``league``, ``home``, ``away``.
    Returns ``{code: {"home": club_rec | None, "away": club_rec | None, "alerts": [...]}}``.
    When ``cache_path`` is provided, fresh (< ``cache_ttl_hours``) cached matchday data is reused.
    """
    match_list = list(matches)
    cpath = Path(cache_path) if cache_path is not None else None
    if cpath is not None and cpath.exists():
        try:
            age_h = (time.time() - cpath.stat().st_mtime) / 3600.0
            if age_h <= max(0.0, float(cache_ttl_hours)):
                cached = json.loads(cpath.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and cached:
                    return {(int(k) if str(k).isdigit() else k): v for k, v in cached.items()}
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    needed_codes: set[str] = set()
    for m in match_list:
        if _is_women_match(m.get("league", ""), m.get("home", ""), m.get("away", "")):
            continue
        for c in resolve_tm_league_codes(m.get("league")):
            needed_codes.add(c)

    if not needed_codes:
        return {}

    league_data: dict[str, dict[str, Any]] = {}
    sess = _tm_session(pool_size=max(max_workers + 4, 16))
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(fetch_tm_league, code, session=sess): code for code in sorted(needed_codes)}
            for fut, code in futs.items():
                try:
                    league_data[code] = fut.result()
                except Exception:
                    league_data[code] = {"code": code, "ok": False, "clubs": {}, "injuries": {}, "suspensions": {}}

        raw_matched: dict[Any, dict[str, Any]] = {}
        club_ids_to_profile: set[str] = set()

        for idx, m in enumerate(match_list):
            if _is_women_match(m.get("league", ""), m.get("home", ""), m.get("away", "")):
                continue
            codes = resolve_tm_league_codes(m.get("league"))
            if not codes:
                continue
            pool_clubs: dict[str, dict[str, Any]] = {}
            pool_inj: dict[str, list[dict[str, Any]]] = {}
            pool_sus: dict[str, list[dict[str, Any]]] = {}
            for lc in codes:
                ld = league_data.get(lc) or {}
                pool_clubs.update(ld.get("clubs") or {})
                for cid, lst in (ld.get("injuries") or {}).items():
                    pool_inj[cid] = lst
                for cid, lst in (ld.get("suspensions") or {}).items():
                    pool_sus[cid] = lst
            if not pool_clubs:
                continue

            key = m.get("code", idx)
            pair: dict[str, Any] = {"home": None, "away": None}
            for side, qname in (("home", m.get("home", "")), ("away", m.get("away", ""))):
                best_cid, best_sc = None, 0.0
                for cid, cinfo in pool_clubs.items():
                    sc = _name_sim(qname, cinfo["name"])
                    if sc > best_sc:
                        best_sc, best_cid = sc, cid
                if best_cid and best_sc >= min_sim:
                    injs = pool_inj.get(best_cid, [])
                    suss = pool_sus.get(best_cid, [])
                    pair[side] = {
                        "club_info": {**pool_clubs[best_cid], "match_sim": round(best_sc, 3)},
                        "injuries": injs,
                        "suspensions": suss,
                    }
                    if fetch_squad_stats and (injs or suss):
                        club_ids_to_profile.add(best_cid)
            if pair["home"] or pair["away"]:
                raw_matched[key] = pair

        squad_stats: dict[str, dict[str, Any]] = {}
        if fetch_squad_stats and club_ids_to_profile:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futs_sq = {
                    ex.submit(fetch_club_squad_stats, cid, session=sess): cid
                    for cid in sorted(club_ids_to_profile)
                }
                for fut, cid in futs_sq.items():
                    try:
                        squad_stats[cid] = fut.result()
                    except Exception:
                        squad_stats[cid] = {"club_id": cid, "ok": False, "players": []}
    finally:
        sess.close()

    out: dict[int | str, dict[str, Any]] = {}
    for key, pair in raw_matched.items():
        rec: dict[str, Any] = {"home": None, "away": None, "alerts": []}
        for side, label in (("home", "Ev"), ("away", "Dep")):
            node = pair.get(side)
            if not node:
                continue
            cid = node["club_info"]["club_id"]
            annotated = annotate_club_absences(
                node["club_info"],
                node["injuries"],
                node["suspensions"],
                squad_stats=squad_stats.get(cid),
            )
            rec[side] = annotated
            rec["alerts"].extend(build_side_alerts(label, annotated))
        out[key] = rec

    if cpath is not None and out:
        try:
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(json.dumps({str(k): v for k, v in out.items()}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return out
