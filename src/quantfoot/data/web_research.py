"""Maç başına web-araştırma adımı: kupona aday maçlar için herkese açık kaynaklardan takım bilgisi toplar.

Toplananlar (her biri ``kaynak`` + ``zaman`` damgalı, bulunamayan ``"bilinmiyor"``; hiçbir şey uydurulmaz):
  * son 5–10 maç ve skor (ESPN scoreboard + Open Matchday + Nesine sonuç havuzu: ``recent_form``),
  * puan durumu (ESPN maç özeti varsa o; yoksa Open Matchday sonuçlarından hesaplanır; haritalı liglerde Wikipedia tablosu),
  * gol ve xG (ESPN takım sezon xG'si varsa o; yoksa şut tabanlı xG VEKİLİ — ayrı etiketli, gerçek xG değildir),
  * sakat/cezalı + ilk 11 (FPL, API-Football ``injuries``, ESPN ilk 11 — ``free_absences``),
  * haber: ESPN takım başlıkları (hoca/rotasyon/sakatlık sözcükleri) ve Wikipedia "Managerial changes" bölümü.

İzin/erişim kuralları: yalnız herkese açık uçlar; Wikipedia için robots.txt'in izin verdiği ``/wiki/`` HTML sayfaları
(``/w/`` ve ``/api/`` kapalı, kullanılmaz); ESPN ve FPL kendi herkese açık JSON uçları. Google Haberler RSS'i
(robots.txt ``Disallow: /``; akış şartı yalnız kişisel okuyucu) ve GDELT (429 / boş / ~18 sn) KULLANILMAZ; Transfermarkt,
Sofascore, FBref, Understat bot korumalı/kapalı olduğundan atlanır (docs/WEB_ARASTIRMA.md).

Çıktı ``research["web"]`` altına yazılır; ``research["teams"][taraf]`` içinde eksik alanlar (form, last5, table) doldurulur
(mevcut ESPN değerlerinin üzerine YAZILMAZ). Sakatlık kalkanına etkisi ``settings.FREE_ABSENCES_ENABLED`` bayrağına bağlı.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import threading
import time
import urllib.robotparser
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from quantfoot.data import free_absences as FA
from quantfoot.data import recent_form as RF
from quantfoot.data.oddsmath import _norm_team, _team_sim
from quantfoot.paths import REPO_ROOT

CACHE = REPO_ROOT / "data" / "cache" / "web_research"
UA = "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma; github.com/ramazanardic/futbol-dehasi)"
UNKNOWN = "bilinmiyor"
CANDIDATE_MIN_P = 0.62
CANDIDATE_MIN_ODDS = 1.20
TIMEOUT_S = 12
OM_RAW = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master"
ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
NEWS_RE = re.compile(r"(sack|fired|dismiss|appoint|new (head )?coach|new manager|parts? ways|interim|caretaker|resign|"
                     r"rotation|rest(ed)?|injur|suspend|ban|doubt|out for|ruled out|"
                     r"teknik direkt|hoca|ayrıl|görevden|sakat|cezalı|kadro dışı|rotasyon)", re.IGNORECASE)
COACH_RE = re.compile(r"(sack|fired|dismiss|appoint|new (head )?coach|new manager|parts? ways|interim|caretaker|resign|"
                      r"teknik direkt|hoca|görevden|ayrıl)", re.IGNORECASE)


def enabled() -> bool:
    import os

    from quantfoot import settings

    env = os.environ.get("QF_WEB_RESEARCH")
    return env != "0" if env is not None else bool(getattr(settings, "WEB_RESEARCH_ENABLED", True))


def af_enabled() -> bool:
    import os

    from quantfoot import settings

    env = os.environ.get("QF_WEB_AF")
    return env == "1" if env is not None else bool(getattr(settings, "WEB_RESEARCH_AF", False))


# ---------------------------------------------------------------------------- HTTP (önbellek + zaman aşımı + kayıt)
class Http:
    """Önbellekli GET: aynı ana makineye en az ``min_gap`` sn ara, ``timeout`` sn zaman aşımı, her çağrı ``log``'a yazılır."""

    def __init__(self, cache_dir: Path = CACHE, timeout: float = TIMEOUT_S, min_gap: float = 0.15,
                 session: requests.Session | None = None, now: Callable[[], float] = time.time):
        self.dir, self.timeout, self.min_gap, self.now = Path(cache_dir), timeout, min_gap, now
        self.s = session or requests.Session()
        self.s.headers["User-Agent"] = UA
        self.log: list[dict] = []
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _path(self, url: str, params: dict | None) -> Path:
        h = hashlib.sha1(json.dumps([url, params or {}], sort_keys=True).encode()).hexdigest()[:20]
        return self.dir / f"{h}.json"

    def robots_ok(self, url: str) -> bool:
        m = re.match(r"(https?://[^/]+)(/.*)?", url)
        host = m.group(1)
        with self._lock:
            if host not in self._robots:
                rp = urllib.robotparser.RobotFileParser()
                try:
                    r = self.s.get(host + "/robots.txt", timeout=self.timeout)
                    rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                    self._robots[host] = rp
                except requests.RequestException:
                    self._robots[host] = None
            rp = self._robots[host]
        return True if rp is None else rp.can_fetch(UA, url)

    def get(self, name: str, url: str, params: dict | None = None, ttl: float = 3600, kind: str = "json",
            check_robots: bool = False) -> Any:
        """``kind``: 'json' | 'text'. Başarısızsa None. Önbellek TTL içindeyse ağa çıkmaz."""
        f = self._path(url, params)
        t0 = self.now()
        entry = {"kaynak": name, "url": url}
        stale = None
        if f.exists():
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
                stale = c if c.get("data") is not None else None
                if t0 - c["t"] < ttl:
                    self.log.append({**entry, "ok": c["data"] is not None, "sn": 0.0, "onbellek": True,
                                     "zaman": _iso(c["t"])})
                    return c["data"]
            except (OSError, ValueError, KeyError):
                pass
        if check_robots and not self.robots_ok(url):
            self.log.append({**entry, "ok": False, "sn": 0.0, "onbellek": False, "zaman": _iso(t0), "hata": "robots.txt yasak"})
            return None
        host = re.match(r"https?://([^/]+)", url).group(1)
        with self._lock:
            slot = max(self.now(), self._last.get(host, 0) + self.min_gap)
            wait = slot - self.now()
            self._last[host] = slot
        if wait > 0:
            time.sleep(wait)
        data, err = None, None
        try:
            r = self.s.get(url, params=params, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json() if kind == "json" else r.text
            else:
                err = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            err = type(e).__name__
        if data is None and stale is not None:  # ağ yok / kaynak çöktü: eski kopya hiç yoktan iyidir (zamanı kayıtlı)
            self.log.append({**entry, "ok": True, "sn": round(self.now() - t0, 2), "onbellek": True, "eski": True,
                             "zaman": _iso(stale["t"]), "hata": err})
            return stale["data"]
        self.log.append({**entry, "ok": data is not None, "sn": round(self.now() - t0, 2), "onbellek": False,
                         "zaman": _iso(t0), **({"hata": err} if err else {})})
        if data is not None or err == "HTTP 404":
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps({"t": t0, "data": data}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        return data


def _iso(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=3))).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------- aday seçimi
def is_candidate(rec: dict, min_p: float = CANDIDATE_MIN_P, min_odds: float = CANDIDATE_MIN_ODDS) -> bool:
    """Kupona aday: fiyatlanmış, özel bahis değil, en az bir seçimi P >= ``min_p`` ve oran >= ``min_odds``."""
    if rec.get("status") != "fiyatlandı" or rec.get("price_tier") == "ozel_bahis":
        return False
    return any((s.get("fair_prob") or 0) >= min_p and (s.get("odds") or 0) >= min_odds for s in rec.get("selections") or [])


# ---------------------------------------------------------------------------- sonuç havuzu (son 120 gün)
def refresh_pool(asof: str, http: Http, window: int = RF.WINDOW_DAYS, max_new_days: int = 130,
                 workers: int = 6) -> tuple[list[dict], dict]:
    """ESPN scoreboard (gün başı 1 istek; biten günler kalıcı önbellek), Open Matchday CSV'leri (6 sa), Nesine sonuçları.
    Dönüş: (havuz, durum). Bir kaynak çökerse eldeki ile devam edilir."""
    ref = dt.date.fromisoformat(asof)
    days = [(ref - dt.timedelta(days=i)) for i in range(1, window + 1)]
    rows: list[dict] = []
    status = {"espn_gun": 0, "om_lig": 0}

    def _espn(d: dt.date):
        p = http.get("ESPN scoreboard", ESPN_SB, {"dates": d.strftime("%Y%m%d")}, ttl=86400 * 400 if d < ref - dt.timedelta(days=2)
                     else 3600)
        return RF.parse_espn_day(p) if p else []

    todo = days[:max_new_days]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(_espn, todo):
            if part:
                status["espn_gun"] += 1
            rows += part
    idx = http.get("Open Matchday dizin", "https://api.github.com/repos/oladeeayo/open-matchday/contents/data", ttl=21600) or []
    folders = [x["name"] for x in idx if isinstance(x, dict) and x.get("type") == "dir"]
    def _om(folder: str):
        t = http.get("Open Matchday", f"{OM_RAW}/data/{folder}/results_2627.csv", ttl=21600, kind="text")
        return RF.parse_openmatchday(t, folder) if t else []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for part in ex.map(_om, folders):
            if part:
                status["om_lig"] += 1
            rows += part
    status["kaynak_ozet"] = "ESPN scoreboard + Open Matchday (ticari olmayan, atıf)"
    return RF.dedupe(rows), status


# ---------------------------------------------------------------------------- puan durumu (Open Matchday sonuçlarından)
def table_from_pool(pool: list[dict], league: str, asof: str) -> list[dict]:
    """Bir Open Matchday liginin (``league``) ``asof`` öncesi sonuçlarından puan durumu: sıra, puan, O/G/B/M, averaj."""
    t: dict[str, dict] = {}
    for r in pool:
        if r.get("league") != league or r["day"] >= asof:
            continue
        for team, gf, ga in ((r["home"], r["hg"], r["ag"]), (r["away"], r["ag"], r["hg"])):
            x = t.setdefault(team, {"team": team, "played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "points": 0})
            x["played"] += 1
            x["gf"] += gf
            x["ga"] += ga
            k = "wins" if gf > ga else "losses" if gf < ga else "draws"
            x[k] += 1
            x["points"] += 3 if gf > ga else 1 if gf == ga else 0
    rows = sorted(t.values(), key=lambda x: (-x["points"], -(x["gf"] - x["ga"]), -x["gf"], x["team"]))
    for i, x in enumerate(rows, 1):
        x["rank"] = i
        x["goal_diff"] = x["gf"] - x["ga"]
    return rows


def table_entry(rows: list[dict], team: str) -> dict | None:
    if not rows:
        return None
    hit = next((x for x in rows if _norm_team(x["team"]) == _norm_team(team)), None) or \
        max(rows, key=lambda x: _team_sim(team, x["team"]))
    if _norm_team(hit["team"]) != _norm_team(team) and _team_sim(team, hit["team"]) < RF_MIN_SIM:
        return None
    played = [x["played"] for x in rows]
    return {"rank": hit["rank"], "points": hit["points"], "played": hit["played"], "wins": hit["wins"], "draws": hit["draws"],
            "losses": hit["losses"], "goal_diff": hit["goal_diff"], "size": len(rows),
            "komple": max(played) - min(played) <= 3}


RF_MIN_SIM = 0.80


# ---------------------------------------------------------------------------- Wikipedia (yalnız /wiki/ HTML — robots.txt izinli)
WIKI = "https://en.wikipedia.org/wiki/"
# Open Matchday klasörü -> Wikipedia sezon sayfası başlığı ({S}: sonbahar-bahar "2026–27", takvim yılı "2026")
WIKI_TITLES = {
    "ENG_1_premier-league": "{A} Premier League", "ENG_2_championship": "{A} EFL Championship", "ENG_3_league-one": "{A} EFL League One",
    "ENG_4_league-two": "{A} EFL League Two", "ESP_1_la-liga": "{A} La Liga", "ESP_2_segunda-division": "{A} Segunda División",
    "ITA_1_serie-a": "{A} Serie A", "ITA_2_serie-b": "{A} Serie B", "GER_1_bundesliga": "{A} Bundesliga",
    "GER_2_2-bundesliga": "{A} 2. Bundesliga", "GER_3_3-liga": "{A} 3. Liga", "FRA_1_ligue-1": "{A} Ligue 1",
    "FRA_2_ligue-2": "{A} Ligue 2", "NED_1_eredivisie": "{A} Eredivisie", "POR_1_primeira-liga": "{A} Primeira Liga",
    "BEL_1_pro-league": "{A} Belgian Pro League", "TUR_1_super-lig": "{A} Süper Lig", "SCO_1_premiership": "{A} Scottish Premiership",
    "GRE_1_super-league": "{A} Super League Greece", "AUT_1_bundesliga": "{A} Austrian Football Bundesliga",
    "SUI_1_super-league": "{A} Swiss Super League", "CZE_1_chance-liga": "{A} Czech First League",
    "POL_1_ekstraklasa": "{A} Ekstraklasa", "CRO_1_hnl": "{A} Croatian Football League", "RUS_1_premier-liga": "{A} Russian Premier League",
    "UKR_1_premier-league": "{A} Ukrainian Premier League", "ROU_1_liga-1": "{A} Liga I", "DEN_1_superliga": "{A} Danish Superliga",
    "SWE_1_allsvenskan": "{B} Allsvenskan", "NOR_1_eliteserien": "{B} Eliteserien", "BRA_1_serie-a": "{B} Campeonato Brasileiro Série A",
    "ARG_1_liga-profesional": "{B} Argentine Primera División", "JPN_1_j1-league": "{B} J1 League", "USA_1_mls": "{B} Major League Soccer season",
    "MEX_1_liga-mx": "{A} Liga MX season", "AUS_1_a-league": "{A} A-League Men",
}


def wiki_title(folder: str, asof: str) -> list[str]:
    tpl = WIKI_TITLES.get(folder)
    if not tpl:
        return []
    d = dt.date.fromisoformat(asof)
    y = d.year if d.month >= 7 else d.year - 1  # sonbahar-bahar sezonunun başlangıç yılı
    a, b = f"{y}–{str(y + 1)[2:]}", str(d.year)
    return [tpl.replace("{A}", a).replace("{B}", b)]


def _clean_cell(x: Any) -> str:
    return re.sub(r"\[[^\]]*\]|\s+", " ", str(x)).strip()


def parse_wiki_tables(html: str) -> dict:
    """HTML -> {'table': [{team,rank,played,points,...}], 'managers': [{team,out,manner,date,in}]}.
    Tablo: 'Pos' + 'Team' + 'Pts' sütunlu; hoca değişimi: 'Outgoing manager' + 'Incoming manager' sütunlu."""
    import io

    import pandas as pd

    out: dict = {"table": [], "managers": []}
    try:
        tabs = pd.read_html(io.StringIO(html))
    except (ValueError, ImportError):
        return out
    for t in tabs:
        cols = [_clean_cell(c if not isinstance(c, tuple) else c[-1]).lower() for c in t.columns]
        t.columns = cols
        if not out["table"] and "pos" in cols and "pts" in cols and any(c.startswith("team") for c in cols):
            team_c = next(c for c in cols if c.startswith("team"))
            for _, r in t.iterrows():
                try:
                    out["table"].append({"team": re.sub(r"\s*\([A-Z,]+\)$", "", _clean_cell(r[team_c])), "rank": int(str(r["pos"])[:3]),
                                         "played": int(r.get("pld", 0)), "points": int(r["pts"]), "wins": int(r.get("w", 0)),
                                         "draws": int(r.get("d", 0)), "losses": int(r.get("l", 0)),
                                         "goal_diff": int(str(r.get("gd", "0")).replace("+", "").replace("−", "-") or 0),
                                         "gf": int(r.get("gf", 0)), "ga": int(r.get("ga", 0))})
                except (ValueError, TypeError, KeyError):
                    continue
        if "outgoing manager" in cols and "incoming manager" in cols:
            tc = next((c for c in cols if c in ("team", "club")), cols[0])
            dc = [c for c in cols if "date" in c]
            for _, r in t.iterrows():
                out["managers"].append({"team": _clean_cell(r[tc]), "out": _clean_cell(r["outgoing manager"]),
                                        "manner": _clean_cell(r.get("manner of departure", "")),
                                        "date": _clean_cell(r[dc[0]]) if dc else "", "in": _clean_cell(r["incoming manager"]),
                                        "in_date": _clean_cell(r[dc[-1]]) if len(dc) > 1 else ""})
    return out


def wiki_league(folder: str, asof: str, http: Http) -> dict | None:
    for title in wiki_title(folder, asof):
        url = WIKI + title.replace(" ", "_")
        html = http.get("Wikipedia (sezon sayfası)", url, ttl=6 * 3600, kind="text", check_robots=True)
        if html:
            r = parse_wiki_tables(html)
            r.update({"title": title, "url": url})
            return r
    return None


# ---------------------------------------------------------------------------- haber / hoca
def news_items(headlines: list[str], source: str, when: str) -> list[dict]:
    return [{"baslik": h, "kaynak": source, "zaman": when, "hoca_degisikligi": bool(COACH_RE.search(h))}
            for h in headlines if h and NEWS_RE.search(h)]


def _parse_wiki_date(txt: str) -> dt.date | None:
    for f in ("%d %B %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(re.sub(r"(\d)(st|nd|rd|th)", r"\1", txt.strip()), f).date()
        except ValueError:
            continue
    return None


def manager_changes_for(team: str, managers: list[dict], asof: str, days: int = 90) -> list[dict]:
    """Takımın Wikipedia 'Managerial changes' satırları, yalnız son ``days`` gün. Tarih sütunu ayrıştırılamıyorsa
    (rowspan kaymış satır) giden hocanın adı ve çıkış biçimi 'tarih belirsiz' etiketiyle tutulur, girenin adı verilmez."""
    out = []
    ref = dt.date.fromisoformat(asof)
    for r in managers:
        if _team_sim(team, r["team"]) < RF_MIN_SIM and _norm_team(team) != _norm_team(r["team"]):
            continue
        d = _parse_wiki_date(r["date"])
        if d is None:
            out.append({"team": r["team"], "out": r["out"], "manner": r["manner"], "tarih": "belirsiz"})
        elif 0 <= (ref - d).days <= days:
            out.append({**r, "tarih": d.isoformat()})
    return out


# ---------------------------------------------------------------------------- takım adı eşleme
# ``_norm_team`` "united/city" sonekini düşürür; kısaltılmış kaynak adları (FPL "Man Utd") bu yüzden ayrıca açılır.
ALIAS = {"man utd": "manchester united", "man united": "manchester united", "man city": "manchester city",
         "spurs": "tottenham hotspur", "tottenham": "tottenham hotspur", "wolves": "wolverhampton wanderers",
         "nott'm forest": "nottingham forest", "nottm forest": "nottingham forest", "newcastle": "newcastle united",
         "west ham": "west ham united", "leeds": "leeds united", "brighton": "brighton hove albion",
         "sheffield utd": "sheffield united", "sheff utd": "sheffield united", "sheff wed": "sheffield wednesday",
         "west brom": "west bromwich albion", "qpr": "queens park rangers", "leicester": "leicester city",
         "norwich": "norwich city", "stoke": "stoke city", "swansea": "swansea city", "cardiff": "cardiff city",
         "hull": "hull city", "coventry": "coventry city", "ipswich": "ipswich town", "luton": "luton town"}


def variants(name: str) -> list[str]:
    k = re.sub(r"\s+", " ", name.strip().lower())
    out = [name]
    if k in ALIAS:
        out.append(ALIAS[k])
    for a, full in ALIAS.items():
        if full == k:
            out.append(a)
    return out


def resolve_any(name: str, idx: dict, cache: dict) -> str | None:
    for v in variants(name):
        k = RF.resolve_team(v, idx, cache)
        if k:
            return k
    return None


def match_any(name: str, names: dict | None) -> str | None:
    for v in variants(name):
        k = FA._match_key(v, names) if names else None
        if k:
            return k
    return None


# ---------------------------------------------------------------------------- takım kaydı
def last_games(key: str | None, idx: dict, asof: str, n: int = 10) -> list[dict]:
    if not key:
        return []
    lo = (dt.date.fromisoformat(asof) - dt.timedelta(days=RF.WINDOW_DAYS)).isoformat()
    g = [m for m in idx.get(key, []) if lo <= m["day"] < asof][-n:]
    return [{"tarih": m["day"], "rakip": m.get("opp", UNKNOWN), "saha": m["venue"], "skor": f"{m['gf']}-{m['ga']}",
             "sonuc": "G" if m["gf"] > m["ga"] else "M" if m["gf"] < m["ga"] else "B", "kaynak": m["src"],
             **({"xg_vekil": round(m["xf"], 2)} if m.get("xf") is not None else {})} for m in g]


def _espn_xg(team_stats: dict | None) -> dict | None:
    if not team_stats:
        return None
    x, xa = team_stats.get("xG (beklenen gol)"), team_stats.get("xGA (beklenen yenen gol)")
    def _f(v):
        try:
            return float(v) if float(v) > 0 else None  # ESPN kapsamadığı ligde "0" döner: veri yok demektir
        except (TypeError, ValueError):
            return None

    x, xa = _f(x), _f(xa)
    return {"xg": x, "xga": xa, "kaynak": "ESPN takım sezon istatistiği"} if x and xa else None


def team_block(name: str, side: str, ctx: Ctx, espn_rec: dict | None) -> tuple[dict, list[str]]:
    """Tek takım için normalize kayıt + bilinmeyen alan listesi."""
    unknown: list[str] = []
    key = resolve_any(name, ctx.idx, ctx.cache)
    games = last_games(key, ctx.idx, ctx.asof, 10)
    blk: dict[str, Any] = {"name": name}
    if games:
        blk["son_maclar"] = games
        blk["form"] = "".join(g["sonuc"] for g in games[-5:])
        blk["gol_ort"] = {"n": len(games), "atilan": round(sum(int(g["skor"].split("-")[0]) for g in games) / len(games), 2),
                          "yenen": round(sum(int(g["skor"].split("-")[1]) for g in games) / len(games), 2)}
        f = RF.team_form(key, ctx.idx, ctx.asof)
        if f and f["n_xg"] >= 3:
            blk["xg_vekil"] = {"xf": round(f["xf"], 2), "xa": round(f["xa"], 2), "n": f["n_xg"],
                               "kaynak": "şut tabanlı Poisson vekili (gerçek xG değil)"}
        league = (f or {}).get("lig") or ""
    else:
        unknown.append(f"{side}.son_maclar")
        league = ""
    blk["lig_kodu"] = league or None
    xg = _espn_xg((espn_rec or {}).get("team_stats"))
    if xg:
        blk["xg"] = xg
    elif "xg_vekil" not in blk:
        unknown.append(f"{side}.xg")
    tab = (espn_rec or {}).get("table")
    if tab:
        blk["puan_durumu"] = {**tab, "kaynak": "ESPN"}
    elif league and league in ctx.om_tables:
        e = table_entry(ctx.om_tables[league], name)
        if e:
            blk["puan_durumu"] = {**e, "kaynak": "Open Matchday sonuçlarından hesaplandı"}
    if "puan_durumu" not in blk:
        wl = ctx.wiki_for(league) if league else None
        e = table_entry(wl["table"], name) if wl and wl.get("table") else None
        if e:
            blk["puan_durumu"] = {**e, "kaynak": f"Wikipedia ({wl['title']})"}
    if "puan_durumu" not in blk:
        unknown.append(f"{side}.puan_durumu")
    wl = ctx.wiki_for(league) if league else None
    chg = manager_changes_for(name, wl["managers"], ctx.asof) if wl and wl.get("managers") else []
    if chg:
        blk["hoca_degisikligi"] = [{**c, "kaynak": f"Wikipedia ({wl['title']})"} for c in chg]
    elif wl:
        blk["hoca_degisikligi"] = "son 90 günde kayıt yok (Wikipedia sezon sayfası)"
    else:
        blk["hoca_degisikligi"] = UNKNOWN
        unknown.append(f"{side}.hoca_degisikligi")
    return blk, unknown


class Ctx:
    """Bir günlük araştırma için ortak durum: havuz, indeks, tablolar, sakatlık kaynakları, Wikipedia önbelleği."""

    def __init__(self, asof: str, http: Http, pool: list[dict] | None = None, fpl: dict | None = None, af: dict | None = None,
                 wiki: Callable[[str, str, Http], dict | None] = wiki_league):
        self.asof, self.http = asof, http
        self.pool = pool if pool is not None else refresh_pool(asof, http)[0]
        self.idx = RF.build_index(self.pool)
        self.cache: dict = {}
        self.om_tables = {lg: table_from_pool(self.pool, lg, asof) for lg in {r.get("league") for r in self.pool if r.get("league")}}
        self.fpl, self.af = fpl, af
        self._wiki, self._wiki_cache = wiki, {}
        self._lock = threading.Lock()

    def wiki_for(self, league: str) -> dict | None:
        with self._lock:
            if league not in self._wiki_cache:
                self._wiki_cache[league] = self._wiki(league, self.asof, self.http)
            return self._wiki_cache[league]


def lineup_from_espn(name: str, espn_rec: dict | None) -> dict | None:
    """ESPN araştırma kaydındaki eksik düzenli oyunculardan kalkan kaydı (ilk 11 açıklandıysa)."""
    if not espn_rec or not espn_rec.get("lineup_announced"):
        return None
    rec = FA._empty_rec(name, "espn-kadro")
    rec["lineup_confirmed"] = True
    for c in espn_rec.get("missing_regulars") or []:
        g = FA._pos_group(c.get("pos"))
        row = {"name": c.get("name"), "importance": "GK1" if g == "GK" else "CORE", "state": "out", "pos": g,
               "reason": "ilk 11'de yok (düzenli oyuncu)"}
        rec["injuries"].append(row)
        rec["critical_absences"].append(row)
        if g == "GK":
            rec["gk1_out"] = True
        elif g == "DEF":
            rec["def_core_out"] += 1
        elif g == "ATT":
            rec["att_core_out"] += 1
        else:
            rec["mid_core_out"] += 1
    rec["top_scorer_out"] = bool(espn_rec.get("top_scorer_missing"))
    return rec


def research_match(m: dict, ctx: Ctx) -> dict:
    """Tek maç için web-araştırma kaydı (``research["web"]``). Ağ hataları yakalanır; eksik alanlar ``bilinmiyor``."""
    t0 = time.time()
    n0 = len(ctx.http.log)
    res = m.get("research") or {}
    web: dict[str, Any] = {"surum": 1, "tarih": ctx.asof, "takimlar": {}, "haber": [], "bilinmiyor": []}
    parts: dict[str, dict] = {}
    for side in ("home", "away"):
        espn_rec = (res.get("teams") or {}).get(side)
        try:
            blk, unk = team_block(m[side], side, ctx, espn_rec)
        except Exception as e:  # noqa: BLE001 — tek takımın hatası bültenin geri kalanını bozmasın
            blk, unk = {"name": m[side], "hata": type(e).__name__}, [f"{side}.hepsi"]
        web["bilinmiyor"] += unk
        if espn_rec:
            blk["espn_son5"] = espn_rec.get("last5")
            news = news_items(espn_rec.get("news_flags") or [], "ESPN takım haberleri", _iso(time.time()))
            web["haber"] += [{**n, "takim": side} for n in news]
        parts[side] = {}
        recs = []
        for src in (ctx.fpl, ctx.af):
            k = match_any(m[side], src)
            if k:
                recs.append(src[k])
        lu = lineup_from_espn(m[side], espn_rec)
        if lu:
            recs.append(lu)
        ab = FA.merge_records(*recs)
        if ab:
            blk["sakat_cezali"] = ab
        else:
            blk["sakat_cezali"] = UNKNOWN
            web["bilinmiyor"].append(f"{side}.sakat_cezali")
        blk["ilk11"] = ("açıklandı" if (espn_rec or {}).get("lineup_announced") else
                        "bilinmiyor (açıklanmamış ya da kaynakta yok)")
        if blk["ilk11"] != "açıklandı":
            web["bilinmiyor"].append(f"{side}.ilk11")
        web["takimlar"][side] = blk
        if ab:
            parts[side] = ab
    if not web["haber"]:
        web["haber"] = UNKNOWN
        web["bilinmiyor"].append("haber")
    web["alerts"] = []
    for side, label in (("home", "Ev"), ("away", "Dep")):
        ab = parts.get(side)
        if ab:
            if ab["gk1_out"]:
                web["alerts"].append(f"{label}: 1. kaleci eksik")
            if ab["top_scorer_out"]:
                web["alerts"].append(f"{label}: golcü eksik")
            if ab["def_core_out"] >= 2:
                web["alerts"].append(f"{label}: {ab['def_core_out']} kilit savunma eksiği")
            if ab["att_core_out"] >= 2 and not ab["top_scorer_out"]:
                web["alerts"].append(f"{label}: {ab['att_core_out']} kilit hücum eksiği")
    web["kaynaklar"] = ctx.http.log[n0:]
    web["sure_sn"] = round(time.time() - t0, 2)
    return web


def normalize_into(rec: dict, web: dict, *, shield: bool) -> None:
    """``web`` kaydını mevcut research yapısına işler: eksik ``teams[taraf]`` alanları doldurulur (ESPN'e dokunulmaz);
    ``shield`` açıksa ve Transfermarkt verisi yoksa ``tm_absences`` aynı şekilde yazılır (banko kalkanı okur)."""
    res = rec.setdefault("research", {"teams": {}, "flags": [], "motivation": {}})
    res["web"] = web
    for side in ("home", "away"):  # yalnız var olan ESPN takım kaydı tamamlanır; yeni kayıt AÇILMAZ (teams varlığı
        w = web["takimlar"].get(side) or {}  # kupon uygunluğunu belirler -> web verisi tek başına bunu değiştirmemeli)
        t = (res.get("teams") or {}).get(side)
        if t is None:
            continue
        if w.get("form") and not t.get("form"):
            t["form"] = w["form"]
            t["form_kaynak"] = "web-arastirma"
        if w.get("son_maclar") and not t.get("last5"):
            t["last5"] = [f"{g['sonuc']} {g['skor']} {'H' if g['saha'] == 'ev' else 'A'} {g['rakip']}" for g in w["son_maclar"][-5:]]
        if w.get("puan_durumu") and not t.get("table"):
            t["table"] = w["puan_durumu"]
    if shield and not res.get("tm_absences"):
        pair = {side: (web["takimlar"][side].get("sakat_cezali") if isinstance(web["takimlar"][side].get("sakat_cezali"), dict)
                       else None) for side in ("home", "away")}
        if pair["home"] or pair["away"]:
            res["tm_absences"] = {**pair, "alerts": list(web.get("alerts") or []), "source": "web-arastirma (FPL/API-Football/ESPN)"}
            for al in web.get("alerts") or []:
                tag = f"Web: {al}"
                if tag not in res.setdefault("flags", []):
                    res["flags"].append(tag)


def summarize_log(log: list[dict]) -> dict[str, dict]:
    """Kaynak adına göre: istek, başarılı, önbellekten, toplam sn."""
    agg: dict[str, dict] = {}
    for k in log:
        x = agg.setdefault(k["kaynak"], {"istek": 0, "basarili": 0, "onbellek": 0, "sn": 0.0})
        x["istek"] += 1
        x["basarili"] += int(bool(k["ok"]))
        x["onbellek"] += int(bool(k.get("onbellek")))
        x["sn"] = round(x["sn"] + (k.get("sn") or 0), 2)
    return agg


def attach(out: list[dict], day: dt.date, *, shield: bool | None = None, http: Http | None = None, budget_s: float = 240.0,
           max_matches: int = 80, ctx: Ctx | None = None, verbose: bool = False) -> dict:
    """Aday maçlara web-araştırma adımını uygular (yalnız kupona aday maçlar). Toplam süre ``budget_s`` ile sınırlı;
    sınır aşılırsa kalan maçlar atlanır. Dönüş: özet (maç sayısı, ortalama sn/maç, kaynak sayıları)."""
    shield = FA.enabled() if shield is None else shield
    cands = [m for m in out if is_candidate(m)][:max_matches]
    summary = {"aday": len(cands), "islenen": 0, "atlanan_sure": 0, "sure_sn": 0.0}
    if not cands:
        return summary
    t0 = time.time()
    http = http or Http()
    asof = day.isoformat()
    if ctx is None:
        fpl = {}
        try:
            fpl = FA.fetch_fpl() if any(m.get("league") == "İngiltere Premier Lig" for m in cands) else {}
        except Exception:  # noqa: BLE001
            fpl = {}
        af = {}
        if af_enabled():
            try:
                af = FA.fetch_af_injuries(asof)
            except Exception:  # noqa: BLE001
                af = {}
        ctx = Ctx(asof, http, fpl=fpl, af=af)
    summary["havuz_hazirlik_sn"] = round(time.time() - t0, 1)
    per = []
    for m in cands:
        if time.time() - t0 > budget_s:
            summary["atlanan_sure"] += 1
            continue
        w = research_match(m, ctx)
        normalize_into(m, w, shield=shield)
        per.append(w["sure_sn"])
        summary["islenen"] += 1
        if verbose:
            print(f"  web-araştırma {m['home']} - {m['away']}: {w['sure_sn']} sn, bilinmeyen {len(w['bilinmiyor'])}")
    summary["sure_sn"] = round(time.time() - t0, 1)
    summary["mac_basi_sn"] = round(sum(per) / len(per), 2) if per else None
    summary["kaynak_ozeti"] = summarize_log(http.log)
    return summary
