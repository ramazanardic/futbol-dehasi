"""Ücretsiz ve izinli kaynaklardan sakat/cezalı ve kadro bilgisi — Transfermarkt erişilemediğinde yedek.

``absences.fetch_matchday_absences`` ile AYNI kayıt şeklini (``gk1_out``, ``top_scorer_out``, ``def_core_out``,
``att_core_out``, ``critical_absences``, ``injuries``) üretir, böylece mevcut banko kalkanı (market_diagnosis) hiç
değişmeden okur. Kaynaklar:

* **FPL resmî oyun API'si** (fantasy.premierleague.com/api/bootstrap-static/): yalnız Premier League; oyuncu durumu
  (sakat/şüpheli/cezalı, oynama şansı) ve sezon dakikası. Anahtarsız, ücretsiz, robots kısıtı yok.
* **API-Football** ``/injuries?date=``: günde 1 istek tüm ligleri döndürür (ücretsiz planda yalnız büyük 12 lig, bugün ±1).
  Oyuncu adı + neden verir, mevki/dakika vermez -> önem ``UNKNOWN`` (yalnız sayım). Kota: api_budget (günde ≤ 60).
* **ESPN maç özeti kadroları**: ilk 11 + mevki. Düzenli oyuncular (son maçlarda ilk 11 payı >= %60) ilk 11'de yoksa
  ``gk1_out`` / ``def_core_out`` / ``att_core_out``. ESPN'in kapsadığı liglerle sınırlıdır.

Hepsi varsayılan KAPALI (``settings.FREE_ABSENCES_ENABLED``, ortam ``QF_FREE_ABSENCES=1``): 18–28 Kas ölçümü
(reports/research/kaynak_etki_2026-11-28.md, kalkan: kalkan_etki_2026-11-28.json) yeterli kanıt vermedikçe olasılıklara dokunmaz.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import defaultdict
from typing import Any

import requests

from quantfoot.data.oddsmath import _norm_team, _team_sim
from quantfoot.paths import REPO_ROOT

CACHE = REPO_ROOT / "data" / "cache" / "free_absences"
UA = {"User-Agent": "QuantFoot/3.0 (kisisel futbol arastirmasi; dusuk hizli okuma)"}
FPL_BOOTSTRAP = "https://fantasy.premierleague.com/api/bootstrap-static/"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
AF_INJURIES = "https://v3.football.api-sports.io/injuries"
REGULAR_SHARE = 0.60
MIN_PREV_MATCHES = 3
MIN_TEAM_SIM = 0.80


def enabled() -> bool:
    from quantfoot import settings

    env = os.environ.get("QF_FREE_ABSENCES")
    return env == "1" if env is not None else bool(getattr(settings, "FREE_ABSENCES_ENABLED", False))


def _empty_rec(name: str, source: str) -> dict[str, Any]:
    return {"name": name, "source": source, "injuries": [], "suspensions": [], "critical_absences": [],
            "gk1_out": False, "top_scorer_out": False, "def_core_out": 0, "att_core_out": 0, "mid_core_out": 0}


# ---------------------------------------------------------------- FPL (Premier League)
def fpl_club_records(bootstrap: dict) -> dict[str, dict[str, Any]]:
    """FPL bootstrap -> {takım adı: kayıt}. ``out`` = oynama şansı 0 (sakat/cezalı/yok), ``doubt`` = %25–75."""
    teams = {t["id"]: t for t in bootstrap.get("teams", [])}
    by_team: dict[int, list[dict]] = defaultdict(list)
    for p in bootstrap.get("elements", []):
        if p.get("status") != "u":  # kulüpten ayrılanlar (u) sayılmaz
            by_team[p["team"]].append(p)
    out: dict[str, dict[str, Any]] = {}
    for tid, players in by_team.items():
        games = max((p.get("minutes", 0) for p in players), default=0) / 90.0
        rec = _empty_rec(teams[tid]["name"], "fpl")
        rec["short_name"] = teams[tid].get("short_name")
        gk1 = max((p for p in players if p["element_type"] == 1), key=lambda p: p.get("minutes", 0), default=None)
        scorers = sorted((p for p in players if p.get("goals_scored", 0) >= 3), key=lambda p: -p["goals_scored"])[:2]
        top_ids = {p["id"] for p in scorers}
        for p in players:
            if p.get("status") == "a":
                continue
            chance = p.get("chance_of_playing_next_round")
            chance = 0 if chance is None and p.get("status") in ("i", "s", "n") else chance
            if chance is None or chance >= 100:
                continue
            share = min(1.0, p.get("minutes", 0) / (games * 90.0)) if games else 0.0
            tags = []
            if gk1 is not None and p["id"] == gk1["id"]:
                tags.append("GK1")
            if p["id"] in top_ids:
                tags.append(f"TOP_SCORER({p['goals_scored']}G)")
            if share >= 0.5:
                tags.append("CORE")
            elif share >= 0.2:
                tags.append("ROT")
            row = {"name": p.get("web_name"), "reason": (p.get("news") or "")[:80], "chance": chance,
                   "importance": "+".join(tags) or "BENCH", "min_pct": round(100 * share), "goals": p.get("goals_scored", 0),
                   "state": "out" if chance == 0 else "doubt"}
            (rec["suspensions"] if p.get("status") == "s" else rec["injuries"]).append(row)
            if row["state"] != "out":
                continue
            if tags:
                rec["critical_absences"].append(row)
            if "GK1" in tags:
                rec["gk1_out"] = True
            if any(t.startswith("TOP_SCORER") for t in tags):
                rec["top_scorer_out"] = True
            if "CORE" in tags:
                key = {2: "def_core_out", 3: "mid_core_out", 4: "att_core_out"}.get(p["element_type"])
                if key:
                    rec[key] += 1
        out[teams[tid]["name"]] = rec
    return out


# ---------------------------------------------------------------- API-Football injuries
def af_injury_records(payload: dict) -> dict[str, dict[str, Any]]:
    """``/injuries?date=`` yanıtı -> {takım adı: kayıt}. Mevki/dakika olmadığından önem UNKNOWN; yalnız sayım ve ad."""
    out: dict[str, dict[str, Any]] = {}
    for r in payload.get("response") or []:
        name = r["team"]["name"]
        rec = out.setdefault(name, _empty_rec(name, "api-football"))
        state = "doubt" if r["player"].get("type") == "Questionable" else "out"
        row = {"name": r["player"].get("name"), "reason": r["player"].get("reason"), "importance": "UNKNOWN", "state": state,
               "fixture": (r.get("fixture") or {}).get("id")}
        rec["injuries"].append(row)
    return out


def fetch_af_injuries(day: str, budget=None, key: str | None = None) -> dict[str, dict[str, Any]]:
    """Günün sakat listesi: günde 1 istek, kalıcı önbellek, ``api_budget`` kotası. Anahtar yoksa / kota doluysa {}."""
    f = CACHE / f"af_injuries_{day}.json"
    if f.exists():
        return af_injury_records(json.loads(f.read_text(encoding="utf-8")))
    from quantfoot.data.api_budget import default_budget

    key = key or os.environ.get("API_FOOTBALL_KEY", "").strip()
    if not key:
        envf = REPO_ROOT / ".env"
        if envf.exists():
            for line in envf.read_text(encoding="utf-8").splitlines():
                if line.startswith("API_FOOTBALL_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
    budget = budget or default_budget()
    if not key or not budget.spend(1, f"injuries?date={day}"):
        return {}
    r = requests.get(AF_INJURIES, params={"date": day}, headers={"x-apisports-key": key}, timeout=40)
    r.raise_for_status()
    j = r.json()
    if j.get("errors"):
        return {}
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return af_injury_records(j)


# ---------------------------------------------------------------- ESPN kadroları
def _pos_group(pos: str | None) -> str:
    p = (pos or "").upper()
    if p == "G":
        return "GK"
    if p in ("F", "LF", "RF", "CF", "CF-L", "CF-R", "RCF", "LCF", "ST", "SS") or p.startswith(("CF", "LW", "RW")):
        return "ATT"
    if p in ("CD", "CD-L", "CD-R", "LB", "RB", "SW", "LWB", "RWB"):
        return "DEF"
    return "MID"


def parse_roster_summary(summary: dict) -> dict[str, dict]:
    """ESPN summary (ya da önbellekteki ``{'rosters': ...}``) -> {'home'|'away': {team, players:[{id,name,starter,pos}]}}."""
    if "rosters" in summary and isinstance(summary["rosters"], dict):
        return summary["rosters"]
    out = {}
    for x in summary.get("rosters") or []:
        out[x["homeAway"]] = {"team": x["team"]["displayName"], "formation": x.get("formation"),
                              "players": [{"id": p["athlete"]["id"], "name": p["athlete"]["displayName"],
                                           "starter": bool(p.get("starter")),
                                           "pos": (p.get("position") or {}).get("abbreviation")}
                                          for p in x.get("roster") or []]}
    return out


def regulars(prev_rosters: list[dict]) -> dict[str, dict]:
    """Takımın önceki maç kadrolarından düzenli ilk 11 oyuncuları: {id: {name, pos, share}} (pay >= REGULAR_SHARE)."""
    if len(prev_rosters) < MIN_PREV_MATCHES:
        return {}
    starts: dict[str, int] = defaultdict(int)
    info: dict[str, dict] = {}
    for r in prev_rosters:
        for p in r.get("players", []):
            info[p["id"]] = p
            if p.get("starter"):
                starts[p["id"]] += 1
    n = len(prev_rosters)
    return {i: {"name": info[i]["name"], "pos": info[i].get("pos"), "share": c / n} for i, c in starts.items() if c / n >= REGULAR_SHARE}


def lineup_record(name: str, xi: list[dict], reg: dict[str, dict]) -> dict[str, Any]:
    """İlk 11 (açıklanmış kadro) ile düzenli oyuncular karşılaştırılır: eksik düzenliler -> kalkan bayrakları."""
    rec = _empty_rec(name, "espn-kadro")
    on = {p["id"] for p in xi if p.get("starter")}
    for pid, r in reg.items():
        if pid in on:
            continue
        g = _pos_group(r.get("pos"))
        row = {"name": r["name"], "importance": ("GK1" if g == "GK" else "CORE"), "reason": "ilk 11'de yok (düzenli oyuncu)",
               "min_pct": round(100 * r["share"]), "state": "out", "pos": g}
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
    rec["lineup_confirmed"] = bool(on)
    return rec


def _match_key(name: str, names: dict[str, Any]) -> str | None:
    if name in names:
        return name
    k = _norm_team(name)
    best, sc = None, 0.0
    for n in names:
        s = 1.0 if _norm_team(n) == k else _team_sim(name, n)
        if s > sc:
            best, sc = n, s
    return best if sc >= MIN_TEAM_SIM else None


def merge_records(*sources: dict[str, dict]) -> dict[str, Any] | None:
    """Aynı takımın kayıtlarını birleştirir (bayraklar OR, sayaçlar max, listeler birleşir)."""
    recs = [s for s in sources if s]
    if not recs:
        return None
    out = _empty_rec(recs[0]["name"], "+".join(sorted({r["source"] for r in recs})))
    seen = set()
    for r in recs:
        out["gk1_out"] |= bool(r.get("gk1_out"))
        out["top_scorer_out"] |= bool(r.get("top_scorer_out"))
        for k in ("def_core_out", "att_core_out", "mid_core_out"):
            out[k] = max(out[k], int(r.get(k) or 0))
        for k in ("injuries", "suspensions", "critical_absences"):
            for x in r.get(k) or []:
                if (k, x.get("name")) not in seen:
                    seen.add((k, x.get("name")))
                    out[k].append(x)
        out["lineup_confirmed"] = out.get("lineup_confirmed", False) or bool(r.get("lineup_confirmed"))
    return out


def fetch_free_absences(matches: list[dict], *, fpl: dict | None = None, af: dict | None = None,
                        lineups: dict[Any, dict] | None = None) -> dict[Any, dict[str, Any]]:
    """``fetch_matchday_absences`` ile aynı çıktı: {kod: {'home': kayıt|None, 'away': kayıt|None, 'alerts': []}}.

    ``fpl`` / ``af`` / ``lineups`` verilmezse ağdan okunmaz (saf birleştirme; ağ katmanı çağıranın işi). ``lineups``:
    {kod: {'home': kayıt, 'away': kayıt}} (``lineup_record`` çıktısı)."""
    fpl, af, lineups = fpl or {}, af or {}, lineups or {}
    out: dict[Any, dict[str, Any]] = {}
    for i, m in enumerate(matches):
        key = m.get("code", i)
        pair: dict[str, Any] = {"home": None, "away": None, "alerts": []}
        for side, label in (("home", "Ev"), ("away", "Dep")):
            team = m.get(side) or ""
            parts = []
            for src in (fpl, af):
                k = _match_key(team, src) if src else None
                if k:
                    parts.append(src[k])
            if lineups.get(key, {}).get(side):
                parts.append(lineups[key][side])
            rec = merge_records(*parts)
            pair[side] = rec
            if rec:
                if rec["gk1_out"]:
                    pair["alerts"].append(f"{label}: 1. kaleci eksik")
                if rec["top_scorer_out"]:
                    pair["alerts"].append(f"{label}: golcü eksik")
                if rec["def_core_out"] >= 2:
                    pair["alerts"].append(f"{label}: {rec['def_core_out']} kilit savunma eksiği")
                if rec["att_core_out"] >= 2 and not rec["top_scorer_out"]:
                    pair["alerts"].append(f"{label}: {rec['att_core_out']} kilit hücum eksiği")
        if pair["home"] or pair["away"]:
            out[key] = pair
    return out


def fetch_fpl(timeout: int = 30) -> dict[str, dict[str, Any]]:
    """Canlı FPL bootstrap (saatlik önbellek) -> kulüp kayıtları."""
    f = CACHE / "fpl_bootstrap.json"
    if not (f.exists() and (dt.datetime.now().timestamp() - f.stat().st_mtime) < 3600):
        r = requests.get(FPL_BOOTSTRAP, headers=UA, timeout=timeout)
        r.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text, encoding="utf-8")
    return fpl_club_records(json.loads(f.read_text(encoding="utf-8")))


def slug_team(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm_team(name))
