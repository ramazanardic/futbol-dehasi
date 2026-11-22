"""Tam maç dosyası (dossier): bir maçın oran dışındaki bütün bilgisini güvenilir kaynaklardan toplar.

Kaynaklar (hepsi önbellekli, biri çökerse diğerleri devam eder):

* **API-Football** (lisanslı anahtar, ücretsiz plan 100 istek/gün): günün fikstürü (hakem, stat, şehir),
  sakat/cezalı listesi, tahmin uç noktası (son 5 maç, karşılaşma geçmişi, karşılaştırma), oranlar
  (Pinnacle + 9 büro → keskin–yumuşak farkı ve oran hareketi), açıklanınca ilk 11'ler.
  **Dinlenme günü ve fikstür yoğunluğu** tarih bazlı fikstürlerden hesaplanır: bu uç nokta *bütün*
  turnuvaları (kupa, Avrupa) kapsadığı için eski deneydeki "kupa maçları eksik" sorununu giderir.
  Geçmiş günler kalıcı önbelleğe alınır; günlük kota koruması vardır.
* **Open-Meteo** (anahtarsız, açık lisans): stat şehrinin koordinatı (geocoding) ve başlama saatindeki
  yağış / rüzgâr / kar.
* **football-data.co.uk** (anahtarsız CSV): İngiltere/İskoçya liglerinde hakem kart / faul eğilimi.

Bu modül olasılık DEĞİŞTİRMEZ. Çıktı, analistin ve kupon denetçisinin okuyacağı yapılandırılmış bir
kayıttır + risk bayrakları. Olasılığa etki eden her özellik önce ileri-yürüyen testten geçmelidir
(bkz. docs/research/gap_analysis_2026_11_21.md).
"""

from __future__ import annotations

import csv
import datetime as dt
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import unicodedata
from typing import Any, Callable

import requests

from quantfoot.data.weather import evaluate_hourly_weather
from quantfoot.paths import REPO_ROOT

AF_BASE = "https://v3.football.api-sports.io"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FD_SEASON_URL = "https://www.football-data.co.uk/mmz4281/{season}/{div}.csv"
SHARP_BOOKS = ("Pinnacle", "Betfair")
DEFAULT_CACHE = Path(os.environ.get("QUANTFOOT_DOSSIER_CACHE", REPO_ROOT / "data" / "cache" / "dossier"))
UTC = dt.timezone.utc

# API-Football lig kimliği → football-data bölümü (hakem sütunu olan ligler)
FD_REFEREE_DIVS = {39: "E0", 40: "E1", 41: "E2", 42: "E3", 179: "SC0"}


class QuotaExceeded(RuntimeError):
    pass


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|sk|fk|cd|ud|sv|bk|if|club|de|calcio|s\.k\.|f\.k\.)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return " ".join(_ALIASES.get(t, t) for t in s.split())


_ALIASES = {"man": "manchester", "utd": "united", "wolves": "wolverhampton", "spurs": "tottenham",
            "psg": "paris saint germain", "inter": "inter", "gs": "galatasaray", "fb": "fenerbahce", "bjk": "besiktas"}

_YOUTH = re.compile(r"\b(u ?1[5-9]|u ?2[0-3]|ii|b|w|women|woman|kadin|reserves?|youth|primavera|jong|sub ?\d+)\b")


def team_match_score(query: str, candidate: str) -> float:
    """Benzerlik; altyapı/kadın/rezerv takımı sorguda yoksa cezalı, tam eşleşme ödüllü."""
    s = name_similarity(query, candidate)
    nq, nc = _norm(query), _norm(candidate)
    if bool(_YOUTH.search(nc)) != bool(_YOUTH.search(nq)):
        s -= 0.3
    if nq == nc:
        s += 0.05
    return s


def name_similarity(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb or na in nb or nb in na:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


class CachedHttp:
    """Dosya önbellekli JSON/CSV GET. ``fetch`` testlerde değiştirilebilir."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE,
                 fetch: Callable[[str, dict, dict], tuple[int, Any]] | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._fetch = fetch or self._requests_fetch
        self.errors: list[str] = []

    @staticmethod
    def _requests_fetch(url: str, params: dict, headers: dict) -> tuple[int, Any]:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        ctype = r.headers.get("content-type", "")
        return r.status_code, (r.json() if "json" in ctype else r.text)

    def _path(self, url: str, params: dict) -> Path:
        key = hashlib.sha1((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:20]
        return self.cache_dir / f"{key}.json"

    def get(self, url: str, params: dict | None = None, headers: dict | None = None,
            ttl_s: float | None = 3600, before_fetch: Callable[[], None] | None = None) -> Any:
        params = params or {}
        p = self._path(url, params)
        if p.exists():
            rec = json.loads(p.read_text(encoding="utf-8"))
            if ttl_s is None or time.time() - rec["t"] < ttl_s:
                return rec["body"]
        if before_fetch:
            before_fetch()
        try:
            status, body = self._fetch(url, params, headers or {})
        except (requests.RequestException, ValueError) as exc:
            self.errors.append(f"{url}: {exc.__class__.__name__}")
            return None
        if status != 200:
            self.errors.append(f"{url}: HTTP {status}")
            return None
        if not (isinstance(body, dict) and body.get("errors")):  # plan/kota hataları önbelleğe alınmaz
            p.write_text(json.dumps({"t": time.time(), "url": url, "params": params, "body": body}), encoding="utf-8")
        return body

    def peek(self, url: str, params: dict | None = None) -> Any:
        """Yalnız önbellekten oku (ağ yok)."""
        p = self._path(url, params or {})
        return json.loads(p.read_text(encoding="utf-8"))["body"] if p.exists() else None


class ApiFootball:
    """API-Football v3 istemcisi: önbellek + günlük kota koruması (varsayılan 90/100)."""

    def __init__(self, http: CachedHttp, key: str | None = None, daily_limit: int = 90) -> None:
        self.http = http
        self.key = key if key is not None else os.environ.get("API_FOOTBALL_KEY", "")
        self.daily_limit = daily_limit
        self.free_window_days = int(os.environ.get("API_FOOTBALL_DATE_WINDOW", "1"))
        self.quota_file = http.cache_dir / "af_quota.json"

    def _spend(self) -> None:
        today = dt.datetime.now(UTC).strftime("%Y-%m-%d")
        q = json.loads(self.quota_file.read_text(encoding="utf-8")) if self.quota_file.exists() else {}
        used = q.get(today, 0)
        if used >= self.daily_limit:
            raise QuotaExceeded(f"API-Football günlük koruma sınırı ({self.daily_limit}) doldu")
        self.quota_file.write_text(json.dumps({today: used + 1}), encoding="utf-8")

    def used_today(self) -> int:
        today = dt.datetime.now(UTC).strftime("%Y-%m-%d")
        q = json.loads(self.quota_file.read_text(encoding="utf-8")) if self.quota_file.exists() else {}
        return int(q.get(today, 0))

    def get(self, endpoint: str, params: dict, ttl_s: float | None) -> list:
        if not self.key:
            raise QuotaExceeded("API_FOOTBALL_KEY yok")
        body = self.http.get(f"{AF_BASE}/{endpoint}", params, {"x-apisports-key": self.key}, ttl_s, self._spend)
        if not isinstance(body, dict):
            return []
        if body.get("errors"):
            self.http.errors.append(f"API-Football {endpoint}: {body['errors']}")
            return []
        return body.get("response") or []

    def fixtures_on(self, day: dt.date, today: dt.date | None = None) -> list:
        """Tarih bazlı fikstür. Ücretsiz plan yalnız dün/bugün/yarın'ı verir: o pencerenin dışındaki günler
        yalnız önbellekten okunur (her gün çalıştırıldıkça geçmiş birikir), istek harcanmaz."""
        today = today or dt.datetime.now(UTC).date()
        if abs((day - today).days) > self.free_window_days:
            body = self.http.peek(f"{AF_BASE}/fixtures", {"date": day.isoformat()})
            return (body or {}).get("response") or [] if isinstance(body, dict) else []
        ttl = None if day < today - dt.timedelta(days=1) else (1800 if day <= today else 6 * 3600)
        return self.get("fixtures", {"date": day.isoformat()}, ttl)


# ---------------------------------------------------------------- saf hesaplar (test edilebilir)

def find_fixture(fixtures: list, home: str, away: str, min_sim: float = 0.72) -> dict | None:
    best, score = None, 0.0
    for f in fixtures:
        s = min(team_match_score(home, f["teams"]["home"]["name"]), team_match_score(away, f["teams"]["away"]["name"]))
        if s > score:
            best, score = f, s
    return best if score >= min_sim else None


def team_schedule(fixtures_by_day: dict[dt.date, list], team_id: int) -> list[tuple[dt.datetime, str, int]]:
    """Takımın bütün turnuvalardaki maçları: (başlama UTC, turnuva, fixture id), sıralı."""
    out = {}
    for fixtures in fixtures_by_day.values():
        for f in fixtures:
            if team_id in (f["teams"]["home"]["id"], f["teams"]["away"]["id"]):
                ko = dt.datetime.fromisoformat(f["fixture"]["date"].replace("Z", "+00:00")).astimezone(UTC)
                out[f["fixture"]["id"]] = (ko, f["league"]["name"], f["fixture"]["id"])
    return sorted(out.values())


def rest_and_congestion(schedule: list[tuple[dt.datetime, str, int]], kickoff: dt.datetime,
                        fixture_id: int | None = None, window_days: int = 14) -> dict[str, Any]:
    """Dinlenme günü (son maçtan), son ``window_days`` gündeki maç sayısı ve sonraki maça kalan gün."""
    schedule = sorted(schedule)
    prev = [s for s in schedule if s[0] < kickoff - dt.timedelta(hours=3) and s[2] != fixture_id]
    nxt = [s for s in schedule if s[0] > kickoff + dt.timedelta(hours=3) and s[2] != fixture_id]
    rec: dict[str, Any] = {
        "rest_days": round((kickoff - prev[-1][0]).total_seconds() / 86400, 1) if prev else None,
        "last_competition": prev[-1][1] if prev else None,
        "matches_last_window": sum(1 for s in prev if s[0] >= kickoff - dt.timedelta(days=window_days)),
        "window_days": window_days,
        "days_to_next": round((nxt[0][0] - kickoff).total_seconds() / 86400, 1) if nxt else None,
        "next_competition": nxt[0][1] if nxt else None,
    }
    return rec


def _devig(odds: list[float]) -> list[float] | None:
    if not odds or any(o is None or o <= 1.0 for o in odds):
        return None
    inv = [1.0 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def summarize_odds(response: list) -> dict[str, Any]:
    """API-Football /odds → 1X2 ve 2.5 Alt/Üst: keskin (Pinnacle/Betfair) marjsız olasılık, en iyi yumuşak oran,
    yumuşak büroların keskine göre EV'si, büro marjları."""
    if not response:
        return {}
    books = response[0].get("bookmakers") or []
    rows: dict[str, dict[str, list[float]]] = {}
    for b in books:
        for bet in b.get("bets") or []:
            vals = {str(v["value"]): float(v["odd"]) for v in bet.get("values") or [] if v.get("odd")}
            if bet.get("name") == "Match Winner" and {"Home", "Draw", "Away"} <= vals.keys():
                rows.setdefault("1X2", {})[b["name"]] = [vals["Home"], vals["Draw"], vals["Away"]]
            if bet.get("name") == "Goals Over/Under" and {"Over 2.5", "Under 2.5"} <= vals.keys():
                rows.setdefault("2.5", {})[b["name"]] = [vals["Over 2.5"], vals["Under 2.5"]]
    out: dict[str, Any] = {"update": response[0].get("update"), "books": len(books)}
    labels = {"1X2": ("1", "X", "2"), "2.5": ("Üst", "Alt")}
    for mkt, by_book in rows.items():
        sharp_name = next((s for s in SHARP_BOOKS if s in by_book), None)
        fair = _devig(by_book[sharp_name]) if sharp_name else None
        soft = {k: v for k, v in by_book.items() if k not in SHARP_BOOKS}
        best = [max((v[i] for v in soft.values()), default=None) for i in range(len(labels[mkt]))]
        margins = {k: round(sum(1 / o for o in v) - 1, 4) for k, v in by_book.items()}
        m: dict[str, Any] = {"sharp_book": sharp_name, "margins": margins, "best_soft": best}
        if fair:
            m["fair"] = [round(p, 4) for p in fair]
            m["best_soft_ev"] = [round(p * o - 1, 4) if o else None for p, o in zip(fair, best)]
        out[mkt] = m
    return out


def odds_movement(snapshots: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Kaydedilmiş keskin 1X2 anlık görüntülerinden açılış→son hareket (olasılık puanı)."""
    snaps = [s for s in snapshots if (s.get("1X2") or {}).get("fair")]
    if len(snaps) < 2:
        return None
    a, b = snaps[0]["1X2"]["fair"], snaps[-1]["1X2"]["fair"]
    delta = [round(y - x, 4) for x, y in zip(a, b)]
    big = max(range(3), key=lambda i: abs(delta[i]))
    flag = None
    if abs(delta[big]) >= 0.03:
        flag = f"Keskin oran hareketi: {'1X2'[big]} {delta[big]:+.1%} (bilgili para / kadro haberi olabilir)"
    return {"from": snaps[0].get("update"), "to": snaps[-1].get("update"), "delta_fair": delta, "flag": flag}


def summarize_injuries(response: list, home_id: int, away_id: int) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {"home": [], "away": []}
    for r in response:
        side = "home" if r["team"]["id"] == home_id else "away" if r["team"]["id"] == away_id else None
        if side:
            out[side].append({"player": r["player"]["name"], "type": r["player"].get("type"),
                              "reason": r["player"].get("reason")})
    return out


def summarize_prediction(response: list) -> dict[str, Any]:
    if not response:
        return {}
    p = response[0]
    teams = p.get("teams") or {}

    def side(s: str) -> dict[str, Any]:
        t = teams.get(s) or {}
        l5 = t.get("last_5") or {}
        lg = t.get("league") or {}
        return {"last5_form": l5.get("form"), "last5_att": l5.get("att"), "last5_def": l5.get("def"),
                "last5_goals_for": ((l5.get("goals") or {}).get("for") or {}).get("average"),
                "last5_goals_against": ((l5.get("goals") or {}).get("against") or {}).get("average"),
                "league_form": lg.get("form")}

    h2h = []
    for f in (p.get("h2h") or [])[-6:]:
        h2h.append(f"{f['fixture']['date'][:10]} {f['teams']['home']['name']} {f['goals']['home']}-"
                   f"{f['goals']['away']} {f['teams']['away']['name']}")
    return {"home": side("home"), "away": side("away"), "comparison": p.get("comparison"),
            "api_advice": (p.get("predictions") or {}).get("advice"), "h2h": h2h}


def referee_profile(rows: list[dict[str, str]], referee: str) -> dict[str, Any] | None:
    """football-data sezon CSV satırlarından hakemin maç başı kart/faul ortalaması vs lig ortalaması."""
    def stats(rs: list[dict[str, str]]) -> dict[str, float] | None:
        vals = []
        for r in rs:
            try:
                vals.append((float(r["HY"]) + float(r["AY"]), float(r["HR"]) + float(r["AR"]),
                             float(r["HF"]) + float(r["AF"]), float(r["FTHG"]) + float(r["FTAG"])))
            except (KeyError, ValueError):
                continue
        if not vals:
            return None
        n = len(vals)
        return {"n": n, "yellow": sum(v[0] for v in vals) / n, "red": sum(v[1] for v in vals) / n,
                "fouls": sum(v[2] for v in vals) / n, "goals": sum(v[3] for v in vals) / n}

    if not referee:
        return None
    surname = _norm(referee).split()[-1] if _norm(referee) else ""
    mine = [r for r in rows if surname and surname in _norm(r.get("Referee", "")).split()]
    s, lg = stats(mine), stats(rows)
    if not s or not lg:
        return None
    flag = None
    if s["n"] >= 5 and s["yellow"] >= lg["yellow"] * 1.2:
        flag = f"Kartçı hakem: maç başı {s['yellow']:.1f} sarı (lig {lg['yellow']:.1f})"
    elif s["n"] >= 5 and s["yellow"] <= lg["yellow"] * 0.8:
        flag = f"Az kart gösteren hakem: {s['yellow']:.1f} sarı (lig {lg['yellow']:.1f})"
    return {"referee": referee, "matches": s["n"], "yellow": round(s["yellow"], 2), "red": round(s["red"], 3),
            "fouls": round(s["fouls"], 1), "goals": round(s["goals"], 2), "league_yellow": round(lg["yellow"], 2),
            "league_goals": round(lg["goals"], 2), "flag": flag}


def schedule_flags(side_label: str, rc: dict[str, Any]) -> list[str]:
    flags = []
    if rc.get("rest_days") is not None and rc["rest_days"] < 3.5:
        flags.append(f"{side_label}: yalnız {rc['rest_days']:.1f} gün dinlenme ({rc.get('last_competition')})")
    if rc.get("matches_last_window", 0) >= 4:
        flags.append(f"{side_label}: son {rc['window_days']} günde {rc['matches_last_window']} maç (yoğun fikstür)")
    if rc.get("days_to_next") is not None and rc["days_to_next"] < 3.5:
        flags.append(f"{side_label}: {rc['days_to_next']:.1f} gün sonra {rc.get('next_competition')} maçı (rotasyon riski)")
    return flags


def espn_context(day: dt.date, home: str, away: str) -> dict[str, Any] | None:
    """ESPN yedeği: lig dinlenme günü, puan durumu, form. Ağ hatasında None."""
    try:
        from quantfoot.data import match_research as mr
        events = mr.espn_events(day.strftime("%Y%m%d"))
        best, score = None, 0.0
        for e in events:
            sc = min(team_match_score(home, e["home"]), team_match_score(away, e["away"]))
            if sc > score:
                best, score = e, sc
        if not best or score < 0.72:
            return None
        rec = mr.research(best["id"])
    except Exception:  # noqa: BLE001 — yedek kaynak; dosyanın geri kalanını düşürmemeli
        return None
    if not rec:
        return None
    teams = rec.get("teams") or {}
    out: dict[str, Any] = {"event": best["id"]}
    for side in ("home", "away"):
        t = teams.get(side) or {}
        out[side] = {"rest_days": t.get("rest_days"), "form": t.get("form"), "table": t.get("table"),
                     "absent": [a.get("name") for a in (t.get("likely_absent") or []) if isinstance(a, dict)][:6]}
    return out


def table_flags(d: dict[str, Any], espn: dict[str, Any]) -> list[str]:
    """Motivasyon: küme düşme hattı / zirve yarışı / ortada kalmış takım (yalnız bilgi bayrağı)."""
    flags = []
    for side in ("home", "away"):
        tb = ((espn.get(side) or {}).get("table")) or {}
        rank, size, played = tb.get("rank"), tb.get("size"), tb.get("played")
        if not rank or not size:
            continue
        rank, size = int(rank), int(size)
        if rank > size - 3:
            flags.append(f"{d[side]}: {rank}./{size} — küme hattında (yüksek motivasyon)")
        elif rank <= 2:
            flags.append(f"{d[side]}: {rank}./{size} — zirve yarışında")
        elif played and size and int(played) >= 2 * (size - 1) - 3 and 6 < rank < size - 5:
            flags.append(f"{d[side]}: sezon sonu, ortada ({rank}./{size}) — motivasyon düşük olabilir")
    return flags


def season_code(day: dt.date) -> str:
    y = day.year if day.month >= 7 else day.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


# ---------------------------------------------------------------- toplayıcı

def build_dossier(day: dt.date, home: str, away: str, *, http: CachedHttp | None = None,
                  api: ApiFootball | None = None, history_days: int = 14, future_days: int = 4,
                  fetch_history: bool = True, today: dt.date | None = None, use_fotmob: bool | None = None,
                  use_understat: bool = True, xg_csv: Path | None = None) -> dict[str, Any]:
    http = http or CachedHttp()
    api = api or ApiFootball(http)
    today = today or dt.datetime.now(UTC).date()
    dossier: dict[str, Any] = {"date": day.isoformat(), "query": f"{home} - {away}", "flags": [], "sources": {}}

    def note(src: str, ok: bool, msg: str = "") -> None:
        dossier["sources"][src] = "tamam" if ok else f"yok ({msg})" if msg else "yok"

    try:
        fixtures = api.fixtures_on(day, today)
    except QuotaExceeded as exc:
        note("API-Football fikstür", False, str(exc))
        dossier["errors"] = http.errors
        return dossier
    fx = find_fixture(fixtures, home, away)
    if not fx:
        note("API-Football fikstür", False, "maç bulunamadı")
        dossier["errors"] = http.errors
        return dossier
    note("API-Football fikstür", True)
    fid = fx["fixture"]["id"]
    hid, aid = fx["teams"]["home"]["id"], fx["teams"]["away"]["id"]
    kickoff = dt.datetime.fromisoformat(fx["fixture"]["date"].replace("Z", "+00:00")).astimezone(UTC)
    venue = fx["fixture"].get("venue") or {}
    dossier.update({
        "fixture_id": fid, "league": fx["league"]["name"], "country": fx["league"].get("country"),
        "league_id": fx["league"]["id"], "round": fx["league"].get("round"),
        "home": fx["teams"]["home"]["name"], "away": fx["teams"]["away"]["name"],
        "kickoff_utc": kickoff.isoformat(), "referee": fx["fixture"].get("referee"),
        "venue": venue.get("name"), "city": venue.get("city"), "status": fx["fixture"]["status"]["short"],
    })

    # Dinlenme / yoğunluk: bütün turnuvalar, tarih bazlı fikstürler
    by_day: dict[dt.date, list] = {day: fixtures}
    missing = 0
    for off in list(range(-history_days, 0)) + list(range(1, future_days + 1)):
        d = day + dt.timedelta(days=off)
        try:
            if fetch_history:
                by_day[d] = api.fixtures_on(d, today)
        except QuotaExceeded:
            missing += 1
    sched_ok = missing == 0 and fetch_history
    for side, tid in (("home", hid), ("away", aid)):
        rc = rest_and_congestion(team_schedule(by_day, tid), kickoff, fid, window_days=history_days)
        dossier[f"{side}_schedule"] = rc
        dossier["flags"] += schedule_flags(dossier[side], rc)
    if any(dossier[f"{s}_schedule"].get("rest_days") is None for s in ("home", "away")):
        espn = espn_context(day, dossier["home"], dossier["away"])
        if espn:
            dossier["espn"] = espn
            for s in ("home", "away"):
                t = espn.get(s) or {}
                if dossier[f"{s}_schedule"].get("rest_days") is None and t.get("rest_days") is not None:
                    dossier[f"{s}_schedule"]["rest_days"] = t["rest_days"]
                    dossier[f"{s}_schedule"]["last_competition"] = "ESPN (lig)"
                    dossier["flags"] += schedule_flags(dossier[s], {"rest_days": t["rest_days"], "last_competition": "ESPN"})
            dossier["flags"] += table_flags(dossier, espn)
        note("ESPN (puan durumu, dinlenme)", bool(espn))
        sched_ok = sched_ok and all(dossier[f"{s}_schedule"].get("rest_days") is not None for s in ("home", "away"))
    note("Dinlenme / fikstür yoğunluğu", sched_ok, f"{missing} gün eksik" if missing else ("" if fetch_history else "kapalı"))

    for name, fn in (("Sakat / cezalı", lambda: summarize_injuries(api.get("injuries", {"fixture": fid}, 6 * 3600), hid, aid)),
                     ("Form / karşılaşma geçmişi", lambda: summarize_prediction(api.get("predictions", {"fixture": fid}, 12 * 3600))),
                     ("Oranlar", lambda: summarize_odds(api.get("odds", {"fixture": fid}, 1800)))):
        try:
            val = fn()
        except QuotaExceeded as exc:
            note(name, False, str(exc))
            continue
        key = {"Sakat / cezalı": "injuries", "Form / karşılaşma geçmişi": "form", "Oranlar": "odds"}[name]
        dossier[key] = val
        note(name, bool(val))
    inj = dossier.get("injuries") or {}
    for side in ("home", "away"):
        out = [i for i in inj.get(side, []) if i.get("type") == "Missing Fixture"]
        if len(out) >= 3:
            dossier["flags"].append(f"{dossier[side]}: {len(out)} oyuncu kesin yok")

    # Oran hareketi (anlık görüntü defteri)
    odds = dossier.get("odds")
    if odds:
        snap_file = http.cache_dir / f"odds_snapshots_{fid}.jsonl"
        lines = snap_file.read_text(encoding="utf-8").splitlines() if snap_file.exists() else []
        if not lines or json.loads(lines[-1]).get("update") != odds.get("update"):
            with snap_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"update": odds.get("update"), "1X2": odds.get("1X2")}) + "\n")
            lines.append(json.dumps({"update": odds.get("update"), "1X2": odds.get("1X2")}))
        mv = odds_movement([json.loads(x) for x in lines])
        if mv:
            dossier["odds_movement"] = mv
            if mv["flag"]:
                dossier["flags"].append(mv["flag"])

    # İlk 11 (genelde maçtan ~60 dk önce)
    if kickoff - dt.datetime.now(UTC) < dt.timedelta(minutes=75):
        try:
            lu = api.get("fixtures/lineups", {"fixture": fid}, 900)
            dossier["lineups"] = [{"team": t["team"]["name"], "formation": t.get("formation"),
                                   "start_xi": [p["player"]["name"] for p in t.get("startXI") or []]} for t in lu]
            note("İlk 11", bool(lu))
        except QuotaExceeded as exc:
            note("İlk 11", False, str(exc))
    else:
        note("İlk 11", False, "henüz açıklanmadı (maçtan ~1 saat önce)")

    # Hava
    if venue.get("city"):
        geo = http.get(GEOCODE_URL, {"name": venue["city"].split(",")[0], "count": 1}, ttl_s=None)
        res = (geo or {}).get("results") if isinstance(geo, dict) else None
        if res:
            lat, lon = res[0]["latitude"], res[0]["longitude"]
            d = kickoff.strftime("%Y-%m-%d")
            fc = http.get(FORECAST_URL, {"latitude": lat, "longitude": lon,
                                         "hourly": "temperature_2m,precipitation,snowfall,wind_speed_10m",
                                         "start_date": d, "end_date": d, "timezone": "UTC"}, ttl_s=3 * 3600)
            w = evaluate_hourly_weather(fc, kickoff) if isinstance(fc, dict) else None
            if w:
                dossier["weather"] = w
                if w.get("flag"):
                    dossier["flags"].append(w["flag"])
        note("Hava (Open-Meteo)", "weather" in dossier)

    # Hakem eğilimi (hakem sütunlu ligler)
    div = FD_REFEREE_DIVS.get(dossier["league_id"])
    if div and dossier.get("referee"):
        text = http.get(FD_SEASON_URL.format(season=season_code(day), div=div), ttl_s=24 * 3600)
        if isinstance(text, str) and "Referee" in text[:500]:
            rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
            prof = referee_profile(rows, dossier["referee"])
            if prof:
                dossier["referee_profile"] = prof
                if prof.get("flag"):
                    dossier["flags"].append(prof["flag"])
        note("Hakem eğilimi (football-data)", "referee_profile" in dossier)
    # FotMob (kullanıcı onayı 21 Kasım): ilk 11 / eksikler / hakem / stat / xG — yalnız analiz edilen maç
    from quantfoot.data import fotmob as fmb
    if use_fotmob if use_fotmob is not None else fmb.enabled():
        fm = fmb.FotMob(http)
        mlist = fmb.parse_matches(fm.matches_on(day, ttl_s=3600) or {})
        m = fmb.find_match(mlist, dossier["home"], dossier["away"])
        if m:
            det = fm.details(m["id"], ttl_s=1800 if kickoff - dt.datetime.now(UTC) < dt.timedelta(hours=2) else 6 * 3600)
            if det:
                info = fmb.parse_details(det)
                dossier["fotmob"] = {k: info.get(k) for k in ("referee", "stadium", "lineup_type", "home_lineup",
                                                               "away_lineup", "weather", "stats")}
                if not dossier.get("referee") and info.get("referee"):
                    dossier["referee"] = info["referee"]
        note("FotMob (ilk 11, eksikler, hakem)", "fotmob" in dossier, "" if m else "maç bulunamadı")

    # Gerçek xG formu: Understat (büyük 5 + RFPL) ve yerel API-Football xG birikimi
    if use_understat:
        from quantfoot.data import understat
        teams, msg = understat.league_teams(http, dossier["league_id"], int(season_code(day)[:2]) + 2000)
        if teams:
            dossier["understat"] = {s: understat.team_xg_form(teams, dossier[s]) for s in ("home", "away")}
            for s in ("home", "away"):
                f = dossier["understat"].get(s) or {}
                if f.get("flag"):
                    dossier["flags"].append(f"{dossier[s]}: {f['flag']} (Understat xG)")
        if dossier["league_id"] in understat.LEAGUES:
            note("Understat xG", bool(teams), msg)
    xg_csv = xg_csv or (REPO_ROOT / "data" / "xg" / "api_football_xg.csv")
    if xg_csv.exists():
        with xg_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for s in ("home", "away"):
            mine = [r for r in rows if team_match_score(dossier[s], r["team"]) >= 0.9][-6:]
            if mine:
                n = len(mine)
                dossier.setdefault("xg_local", {})[s] = {
                    "n": n, "xg": round(sum(float(r["xg"]) for r in mine) / n, 2),
                    "goals": round(sum(float(r["goals"] or 0) for r in mine) / n, 2)}

    dossier["api_football_used_today"] = api.used_today()
    dossier["errors"] = http.errors
    return dossier


def _i(x: Any) -> str:
    try:
        return str(int(float(x)))
    except (TypeError, ValueError):
        return "?"


def render_markdown(d: dict[str, Any]) -> str:
    if "fixture_id" not in d:
        return f"# {d['query']} ({d['date']})\n\nMaç bulunamadı ya da kaynak yok: {d.get('sources')}\n"
    tsi = dt.timezone(dt.timedelta(hours=3))
    ko = dt.datetime.fromisoformat(d["kickoff_utc"]).astimezone(tsi)
    L = [f"# {d['home']} - {d['away']}", "",
         f"{d['league']} ({d.get('country')}) · {d.get('round') or ''} · {ko:%d.%m.%Y %H:%M} TSİ · "
         f"{d.get('venue') or '?'}, {d.get('city') or '?'} · Hakem: {d.get('referee') or 'açıklanmadı'}", ""]
    L += ["## Risk bayrakları", ""] + ([f"- {f}" for f in d["flags"]] or ["- (yok)"]) + [""]
    L += ["## Dinlenme ve fikstür", "", "| | Dinlenme (gün) | Son maç | Son 14 günde maç | Sonraki maça (gün) |",
          "|---|---|---|---|---|"]
    for s in ("home", "away"):
        rc = d.get(f"{s}_schedule") or {}
        L.append(f"| {d[s]} | {rc.get('rest_days', '-')} | {rc.get('last_competition') or '-'} | "
                 f"{rc.get('matches_last_window', '-')} | {rc.get('days_to_next', '-')} ({rc.get('next_competition') or '-'}) |")
    espn = d.get("espn") or {}
    if espn:
        L += ["", "## Puan durumu ve form (ESPN)", ""]
        for s in ("home", "away"):
            t = espn.get(s) or {}
            tb = t.get("table") or {}
            L.append(f"- **{d[s]}**: {_i(tb.get('rank'))}./{_i(tb.get('size'))} sıra, {_i(tb.get('points'))} puan, "
                     f"averaj {_i(tb.get('goal_diff'))}; son form {t.get('form') or '-'}"
                     + (f"; olası eksik (son 5 maçın ilk 11'inden): {', '.join(t['absent'])}" if t.get("absent") else ""))
    inj = d.get("injuries") or {}
    L += ["", "## Eksikler (API-Football)", ""]
    for s in ("home", "away"):
        items = inj.get(s) or []
        txt = "; ".join(f"{i['player']} ({i.get('reason') or i.get('type')}{', şüpheli' if i.get('type') == 'Questionable' else ''})"
                        for i in items) or "bildirilen yok"
        L.append(f"- **{d[s]}**: {txt}")
    form = d.get("form") or {}
    if form:
        L += ["", "## Form ve karşılaşma geçmişi", "", "| | Son 5 form | Son 5 atak | Son 5 savunma | Attığı / yediği (ort.) | Lig formu |",
              "|---|---|---|---|---|---|"]
        for s in ("home", "away"):
            f = form.get(s) or {}
            L.append(f"| {d[s]} | {f.get('last5_form')} | {f.get('last5_att')} | {f.get('last5_def')} | "
                     f"{f.get('last5_goals_for')} / {f.get('last5_goals_against')} | {(f.get('league_form') or '-')[-8:]} |")
        if form.get("h2h"):
            L += ["", "Son karşılaşmalar: " + " · ".join(form["h2h"])]
    odds = d.get("odds") or {}
    if odds.get("1X2"):
        m = odds["1X2"]
        L += ["", "## Piyasa (API-Football oranları)", ""]
        if m.get("fair"):
            L.append(f"- Keskin ({m['sharp_book']}) marjsız 1X2: " + " / ".join(f"{p:.1%}" for p in m["fair"]))
            L.append("- En iyi yumuşak oran ve keskine göre EV: " + " / ".join(
                f"{o} ({e:+.1%})" for o, e in zip(m["best_soft"], m["best_soft_ev"]) if o is not None and e is not None))
        if odds.get("2.5", {}).get("fair"):
            L.append("- 2,5 Üst/Alt keskin: " + " / ".join(f"{p:.1%}" for p in odds["2.5"]["fair"]))
        mv = d.get("odds_movement")
        if mv:
            L.append(f"- Hareket ({mv['from']} → {mv['to']}): " + " / ".join(f"{x:+.1%}" for x in mv["delta_fair"]))
    if d.get("weather"):
        w = d["weather"]
        L += ["", f"## Hava: {w.get('temp_c')}°C, yağış {w.get('rain_mm')} mm/s, rüzgâr {w.get('wind_kmh')} km/s"]
    if d.get("referee_profile"):
        r = d["referee_profile"]
        L += ["", f"## Hakem: {r['referee']} — bu sezon {r['matches']} maç, maç başı {r['yellow']} sarı (lig {r['league_yellow']}), "
                  f"{r['fouls']} faul, {r['goals']} gol (lig {r['league_goals']})"]
    fm = d.get("fotmob") or {}
    if fm:
        L += ["", f"## FotMob ({'kesin ilk 11' if fm.get('lineup_type') == 'standard' else 'tahmini/eksik ilk 11'})"]
        for s in ("home", "away"):
            lu = fm.get(f"{s}_lineup") or {}
            if lu:
                un = "; ".join(f"{u['name']} ({u.get('reason') or '?'})" for u in lu.get("unavailable") or []) or "yok"
                L.append(f"- **{d[s]}** {lu.get('formation') or ''}: {', '.join(lu.get('starters') or []) or '-'} · eksik: {un}")
        st = fm.get("stats") or {}
        if (st.get("home") or {}).get("xg") is not None:
            L.append(f"- Maç xG: {st['home']['xg']} - {st['away']['xg']}")
    for key, title in (("understat", "Understat"), ("xg_local", "API-Football birikimi")):
        x = d.get(key) or {}
        if any(x.values()):
            L += ["", f"## Gerçek xG formu ({title}, son maçlar ortalaması)"]
            for s in ("home", "away"):
                f = x.get(s) or {}
                if f:
                    L.append(f"- {d[s]}: {f.get('n')} maç, xG {f.get('xg')}" + (f", xGA {f['xga']}" if "xga" in f else "")
                             + f", gol {f.get('goals')}")
    if d.get("lineups"):
        L += ["", "## İlk 11"] + [f"- {t['team']} ({t['formation']}): {', '.join(t['start_xi'])}" for t in d["lineups"]]
    L += ["", "## Kaynak durumu", ""] + [f"- {k}: {v}" for k, v in d["sources"].items()]
    L += ["", f"API-Football bugün kullanılan istek (bu araçla): {d.get('api_football_used_today')}"]
    return "\n".join(L) + "\n"
