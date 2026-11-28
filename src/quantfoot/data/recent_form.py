"""Son ~120 günün sonuç havuzu ve takım formu (küçük/özel Nesine ligleri dahil).

Kaynaklar (hepsi ücretsiz, anahtarsız; ham dosyalar repoya konmaz, data/cache altında git-ignored):
  * ESPN herkese açık scoreboard (``/soccer/all/scoreboard?dates=YYYYMMDD``) — günde 1 istek, ~220 lig, yalnız skor.
  * Open Matchday CSV (github.com/oladeeayo/open-matchday, 75 yarışma, 2026/27) — tarih, skor, bazı İY ve şut verisi.
    Lisans: ticari olmayan kullanım + atıf (DISCLAIMER.md); satış yok.
  * Nesine canlı skor sonuç havuzu (``nesine.fetch_results`` kaynağı: ls.nesine.com GetUnliveMatches) — yalnız son
    ~14–20 gün geriye döner, bu yüzden her çalıştırmada git-ignored arşive eklenir.

Havuz maç satırı tutar ama repoya yalnız takım bazında agregat (``data/form/takim_son120_form.csv``) yazılır.
Takım adları ``oddsmath._norm_team`` ile eşlenir (mevcut alias mantığı).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections.abc import Iterable
from pathlib import Path

from quantfoot.data.oddsmath import _norm_team, _team_sim
from quantfoot.paths import REPO_ROOT

CACHE = REPO_ROOT / "data" / "cache" / "recent_form"
FORM_CSV = REPO_ROOT / "data" / "form" / "takim_son120_form.csv"
WINDOW_DAYS = 120
LAST_N = 10
FORM_K = 5.0          # takım ortalamasının havuz ortalamasına büzülmesi (sözde maç)
MIN_FORM_N = 3        # bundan az maçlı takım için form yok
_NOISE = re.compile(r"\b(women|w|u\d\d|ii|b)\b", re.IGNORECASE)


def _row(day: str, home: str, away: str, hg: int, ag: int, src: str, **extra) -> dict:
    return {"day": day, "home": home, "away": away, "hg": int(hg), "ag": int(ag), "src": src,
            "nh": _norm_team(home), "na": _norm_team(away), **extra}


def parse_espn_day(payload: dict) -> list[dict]:
    """ESPN ``all/scoreboard`` yanıtı -> biten maçlar (kadın / yaş grubu ve üniversite maçları atılır)."""
    out = []
    for e in payload.get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        if not (comp.get("status") or {}).get("type", {}).get("completed"):
            continue
        slug = (e.get("season") or {}).get("slug", "")
        if "ncaa" in slug or "women" in slug or "womens" in slug:
            continue
        cs = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        try:
            h, a = cs["home"], cs["away"]
            out.append(_row(e["date"][:10], h["team"]["displayName"], a["team"]["displayName"],
                            int(h["score"]), int(a["score"]), "espn", league=slug, eid=e.get("id")))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def parse_openmatchday(text: str, league: str) -> list[dict]:
    out = []
    for r in csv.DictReader(text.splitlines()):
        if not (r.get("ft_home") or "").strip().isdigit() or not (r.get("ft_away") or "").strip().isdigit():
            continue

        def _i(k, r=r):
            v = (r.get(k) or "").strip()
            return int(v) if v.isdigit() else None

        out.append(_row(r["date"], r["home"], r["away"], int(r["ft_home"]), int(r["ft_away"]), "openmatchday", league=league,
                        hs=_i("home_shots"), as_=_i("away_shots"), ht=_i("home_target"), at=_i("away_target")))
    return out


def parse_nesine_day(payload: dict, day: str) -> list[dict]:
    """Nesine GetUnliveMatches yanıtı -> biten maçlar (90 dk skoru, Nesine'nin kendi lig adıyla)."""
    out = []
    for m in payload.get("d") or []:
        sc = {e.get("T"): (int(e.get("H", 0)), int(e.get("A", 0))) for e in m.get("ES") or []}
        ft = sc.get(3, sc.get(1) if m.get("ST") == "MS" else None)
        if m.get("ST") in ("MS", "UZT", "PEN") and ft is not None:
            d = str(m.get("D") or "")
            dd = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else day
            out.append(_row(dd, m["HT"], m["AT"], ft[0], ft[1], "nesine", league=m.get("L", "")))
    return out


def dedupe(rows: Iterable[dict]) -> list[dict]:
    """Aynı maç (gün ±1, normalize takımlar, aynı skor) tek satıra iner; Nesine > Open Matchday > ESPN öncelikli (lig adı)."""
    rank = {"nesine": 0, "openmatchday": 1, "espn": 2}
    seen: dict[tuple, dict] = {}
    for r in sorted(rows, key=lambda r: rank.get(r["src"], 9)):
        d = dt.date.fromisoformat(r["day"])
        keys = [((d + dt.timedelta(days=k)).isoformat(), r["nh"][:7], r["na"][:7], r["hg"], r["ag"]) for k in (-1, 0, 1)]
        if any(k in seen for k in keys):
            continue
        seen[keys[1]] = r
    return sorted(seen.values(), key=lambda r: r["day"])


def load_pool(dirs: dict[str, Path]) -> list[dict]:
    """``dirs``: {'espn': dir of YYYY-MM-DD.json, 'openmatchday': dir of <folder>.csv, 'nesine': dir of YYYY-MM-DD.json}."""
    rows: list[dict] = []
    for f in sorted(Path(dirs.get("espn", "/nonexistent")).glob("*.json")):
        rows += parse_espn_day(json.loads(f.read_text(encoding="utf-8")))
    for f in sorted(Path(dirs.get("openmatchday", "/nonexistent")).glob("*.csv")):
        rows += parse_openmatchday(f.read_text(encoding="utf-8"), f.stem)
    for f in sorted(Path(dirs.get("nesine", "/nonexistent")).glob("*.json")):
        rows += parse_nesine_day(json.loads(f.read_text(encoding="utf-8")), f.stem)
    return dedupe(rows)


def fit_shot_xg(matches_csv: Path | None = None, before: str = "2026-07-01"):
    """Şut tabanlı xG vekili: isabetli şut, isabetsiz şut ve ev avantajından Poisson GLM; yalnız ``before`` öncesi football-data
    maçlarıyla (data/matches.csv) eğitilir, yani havuzdaki 2026/27 maçlarına sızıntı yok. Gerçek xG DEĞİLDİR."""
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import PoissonRegressor

    m = pd.read_csv(matches_csv or REPO_ROOT / "data" / "matches.csv", usecols=["MatchDate", "FTHome", "FTAway", "HomeShots", "AwayShots", "HomeTarget", "AwayTarget"], low_memory=False).dropna()
    m = m[m.MatchDate < before]
    th, ta = m.HomeTarget.values, m.AwayTarget.values
    xh = np.column_stack([th, (m.HomeShots.values - th).clip(0), np.ones(len(m))])
    xa = np.column_stack([ta, (m.AwayShots.values - ta).clip(0), np.zeros(len(m))])
    reg = PoissonRegressor(alpha=1.0, max_iter=500).fit(np.vstack([xh, xa]), np.concatenate([m.FTHome.values, m.FTAway.values]))

    def predict(shots: float, target: float, home: bool) -> float:
        return float(np.clip(reg.predict([[target, max(shots - target, 0.0), 1.0 if home else 0.0]])[0], 0.05, 5.0))

    return predict, len(m)


def attach_xg_proxy(pool: list[dict], predict) -> int:
    """Şut verisi olan satırlara ``xh``/``xa`` (xG vekili) ekler; eklenen satır sayısını döndürür."""
    n = 0
    for r in pool:
        if None not in (r.get("hs"), r.get("as_"), r.get("ht"), r.get("at")):
            r["xh"] = predict(r["hs"], r["ht"], True)
            r["xa"] = predict(r["as_"], r["at"], False)
            n += 1
    return n


def build_index(pool: list[dict]) -> dict[str, list[dict]]:
    """normalize takım adı -> o takımın maçları (tarih sırasıyla), gf/ga ve ev/dep ile."""
    idx: dict[str, list[dict]] = {}
    for r in pool:
        idx.setdefault(r["nh"], []).append({"day": r["day"], "gf": r["hg"], "ga": r["ag"], "venue": "ev", "src": r["src"],
                                            "team": r["home"], "league": r.get("league", ""), "opp": r["away"],
                                            "xf": r.get("xh"), "xa": r.get("xa")})
        idx.setdefault(r["na"], []).append({"day": r["day"], "gf": r["ag"], "ga": r["hg"], "venue": "dep", "src": r["src"],
                                            "team": r["away"], "league": r.get("league", ""), "opp": r["home"],
                                            "xf": r.get("xa"), "xa": r.get("xh")})
    return idx


_TOK_CACHE: dict[int, dict[str, set[str]]] = {}


def _token_index(idx: dict[str, list[dict]]) -> dict[str, set[str]]:
    tid = id(idx)
    if tid not in _TOK_CACHE:
        t: dict[str, set[str]] = {}
        for k in idx:
            for w in k.split():
                if len(w) >= 4:
                    t.setdefault(w, set()).add(k)
        _TOK_CACHE.clear()
        _TOK_CACHE[tid] = t
    return _TOK_CACHE[tid]


def resolve_team(name: str, idx: dict[str, list[dict]], cache: dict | None = None) -> str | None:
    """Takım adını indeksteki anahtara eşler: tam eşleşme, sonra ortak sözcüğü olan adaylar arasında benzerlik >= 0.80
    (II / U21 / kadın ayrımı korunur: biri işaretliyse öteki de işaretli olmalı)."""
    key = _norm_team(name)
    if key in idx:
        return key
    cache = {} if cache is None else cache
    if key in cache:
        return cache[key]
    flag = bool(_NOISE.search(name))
    toks = _token_index(idx)
    cands = set().union(*(toks.get(w, set()) for w in key.split() if len(w) >= 4)) if key else set()
    best, score = None, 0.0
    for k in cands:
        s = _team_sim(name, idx[k][0]["team"])
        if s > score and bool(_NOISE.search(idx[k][0]["team"])) == flag:
            best, score = k, s
    cache[key] = best if score >= 0.80 else None
    return cache[key]


def team_form(key: str, idx: dict[str, list[dict]], asof: str, last: int = LAST_N, window: int = WINDOW_DAYS) -> dict | None:
    """Maç gününden ÖNCEKİ son ``last`` maç (pencere içinde): ortalama atılan/yenilen, ev/dep ayrı. < MIN_FORM_N maç -> None."""
    ref = dt.date.fromisoformat(asof)
    lo = (ref - dt.timedelta(days=window)).isoformat()
    g = [m for m in idx.get(key, []) if lo <= m["day"] < asof]
    if len(g) < MIN_FORM_N:
        return None
    t = g[-last:]
    def _x(m, a, b):
        return m[a] if m.get(a) is not None else m[b]

    out = {"n": len(t), "son": t[-1]["day"], "gf": sum(m["gf"] for m in t) / len(t), "ga": sum(m["ga"] for m in t) / len(t),
           "n_xg": sum(1 for m in t if m.get("xf") is not None),
           "xf": sum(_x(m, "xf", "gf") for m in t) / len(t), "xa": sum(_x(m, "xa", "ga") for m in t) / len(t),
           "kaynaklar": sorted({m["src"] for m in t}), "takim": t[-1]["team"], "lig": t[-1]["league"]}
    for v in ("ev", "dep"):
        s = [m for m in g if m["venue"] == v][-last:]
        out[f"{v}_n"] = len(s)
        out[f"{v}_gf"] = sum(m["gf"] for m in s) / len(s) if s else None
        out[f"{v}_ga"] = sum(m["ga"] for m in s) / len(s) if s else None
        out[f"{v}_xf"] = sum(_x(m, "xf", "gf") for m in s) / len(s) if s else None
        out[f"{v}_xa"] = sum(_x(m, "xa", "ga") for m in s) / len(s) if s else None
    return out


def pool_means(pool: list[dict], asof: str, window: int = WINDOW_DAYS) -> tuple[float, float]:
    ref = dt.date.fromisoformat(asof)
    lo = (ref - dt.timedelta(days=window)).isoformat()
    g = [r for r in pool if lo <= r["day"] < asof]
    if not g:
        return 1.5, 1.15
    return sum(r["hg"] for r in g) / len(g), sum(r["ag"] for r in g) / len(g)


def lambdas(home: str, away: str, idx: dict, asof: str, means: tuple[float, float], cache: dict | None = None,
            k: float = FORM_K, use_xg: bool = False) -> tuple[float, float, dict] | None:
    """Beklenen gol (ev, dep): takım ev/dep formu havuz ortalamasına ``k`` sözde maçla büzülür. İki takımın da formu şart."""
    kh, ka = resolve_team(home, idx, cache), resolve_team(away, idx, cache)
    if not kh or not ka:
        return None
    fh, fa = team_form(kh, idx, asof), team_form(ka, idx, asof)
    if not fh or not fa:
        return None
    mh, ma = means

    def shr(n, v, base):
        return base if not n or v is None else (n * v + k * base) / (n + k)

    f, g = ("xf", "xa") if use_xg else ("gf", "ga")
    h_att, h_def = shr(fh["ev_n"], fh[f"ev_{f}"], mh), shr(fh["ev_n"], fh[f"ev_{g}"], ma)
    a_att, a_def = shr(fa["dep_n"], fa[f"dep_{f}"], ma), shr(fa["dep_n"], fa[f"dep_{g}"], mh)
    lam_h = max(0.15, h_att * a_def / mh)
    lam_a = max(0.15, a_att * h_def / ma)
    return lam_h, lam_a, {"n_ev": fh["n"], "n_dep": fa["n"], "kaynak": sorted(set(fh["kaynaklar"]) | set(fa["kaynaklar"]))}


def summary_rows(pool: list[dict], asof: str) -> list[dict]:
    """Repoya yazılacak takım agregatı (maç satırı yok)."""
    idx = build_index(pool)
    out = []
    for key in idx:
        f = team_form(key, idx, asof)
        if f:
            out.append({"takim": f["takim"], "anahtar": key, "lig": f["lig"], "n": f["n"], "son_mac": f["son"],
                        "at": round(f["gf"], 2), "yedi": round(f["ga"], 2),
                        "ev_n": f["ev_n"], "ev_at": None if f["ev_gf"] is None else round(f["ev_gf"], 2),
                        "ev_yedi": None if f["ev_ga"] is None else round(f["ev_ga"], 2),
                        "dep_n": f["dep_n"], "dep_at": None if f["dep_gf"] is None else round(f["dep_gf"], 2),
                        "dep_yedi": None if f["dep_ga"] is None else round(f["dep_ga"], 2),
                        "kaynak": "+".join(f["kaynaklar"])})
    return sorted(out, key=lambda r: (r["lig"], r["takim"]))
