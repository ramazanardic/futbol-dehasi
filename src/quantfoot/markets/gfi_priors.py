"""GLOBAL FOOTBALL INTELLIGENCE türetilmiş öncülleri (data/gfi/*.csv, scripts/gfi_turet.py).

Üç tablo, hepsi agregat (maç satırı yok):
  * lig_taban_gfi.csv      lig taban oranları; arşivde/lig_oranlari'nda olmayan küçük liglerin (wr:<ülke>) gol düzeyi
  * takim_form_gfi.csv     arşiv dışı liglerde takım son-10 atılan/yenilen (ev/dep ayrı)
  * lig_yari_dakika_gfi.csv  world_incidents gol dakikalarından lig İY gol payı ve 15 dk dağılımı, _genel satırıyla

İnce-lig mantığı Bayesçi büzmedir: takım oranları lig ortalamasına FORM_K sözde-maçla, lig İY payı league_halves.PRIOR'a
league_halves.PRIOR_GOALS sözde-golle çekilir. Varsayılan KAPALI (settings.GFI_PRIORS_ENABLED / QF_GFI_PRIORS=1);
gerekçe reports/research/gfi_etki_2026-11-28.md.
"""

from __future__ import annotations

import csv
import math
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

from quantfoot.coupons.coupon_rules import normalize_leg_name
from quantfoot.data.oddsmath import _norm_team, _team_sim
from quantfoot.markets import league_halves as lh

DIR = Path(__file__).resolve().parents[3] / "data" / "gfi"
FORM_K = 5.0            # takım son-10 ortalamasının lig ortalamasına büzülmesi (sözde maç)
FORM_MAX_AGE_DAYS = 120  # daha eski form kullanılmaz (world_results 2025-09'da biter)
MIN_N = 80
MAX_GOALS = 10

# Nesine ülke sözcüğü -> world_results ülke anahtarı (o ülkenin üst ligi)
COUNTRY_SLUG = {
    "arnavutluk": "albania", "andorra": "andorra", "ermenistan": "armenia", "azerbaycan": "azerbaijan", "bahreyn": "bahrain",
    "bangladeş": "bangladesh", "belarus": "belarus", "bolivya": "bolivia", "bosna hersek": "bosnia-herzegovina",
    "botsvana": "botswana", "bulgaristan": "bulgaria", "kamerun": "cameroon", "kanada": "canada", "şili": "chile",
    "kosta rika": "costa-rica", "fildişi sahili": "cote-divoire", "hırvatistan": "croatia", "kıbrıs": "cyprus",
    "danimarka": "denmark", "ekvador": "ecuador", "el salvador": "el-salvador", "estonya": "estonia", "etiyopya": "ethiopia",
    "faroe adaları": "faroe-islands", "finlandiya": "finland", "gürcistan": "georgia", "gana": "ghana", "cebelitarık": "gibraltar",
    "guatemala": "guatemala", "honduras": "honduras", "hong kong": "hong-kong", "izlanda": "iceland", "hindistan": "india",
    "endonezya": "indonesia", "iran": "iran", "irak": "iraq", "irlanda": "ireland-republic", "israil": "israel",
    "jamaika": "jamaica", "ürdün": "jordan", "kazakistan": "kazakhstan", "kenya": "kenya", "güney kore": "korea-republic",
    "kosova": "kosovo", "kuveyt": "kuwait", "letonya": "latvia", "lübnan": "lebanon", "litvanya": "lithuania",
    "lüksemburg": "luxembourg", "kuzey makedonya": "macedonia-fyr", "malezya": "malaysia", "malta": "malta",
    "moldova": "moldova", "karadağ": "montenegro", "mozambik": "mozambique", "yeni zelanda": "new-zealand",
    "nikaragua": "nicaragua", "nijerya": "nigeria", "kuzey irlanda": "northern-ireland", "norveç": "norway", "umman": "oman",
    "panama": "panama", "paraguay": "paraguay", "peru": "peru", "polonya": "poland", "katar": "qatar", "romanya": "romania",
    "ruanda": "rwanda", "suudi arabistan": "saudi-arabia", "senegal": "senegal", "sırbistan": "serbia", "singapur": "singapore",
    "slovakya": "slovakia", "slovenya": "slovenia", "güney afrika": "south-africa", "isveç": "sweden", "tanzanya": "tanzania",
    "tayland": "thailand", "tunus": "tunisia", "uganda": "uganda", "ukrayna": "ukraine", "bae": "united-arab-emirates",
    "uruguay": "uruguay", "özbekistan": "uzbekistan", "venezuela": "venezuela", "vietnam": "vietnam", "galler": "wales",
    "zambiya": "zambia", "zimbabve": "zimbabwe", "kolombiya": "colombia", "cezayir": "algeria", "mısır": "egypt", "fas": "morocco",
    "avustralya": "australia", "çin": "china-pr", "japonya": "japan", "meksika": "mexico", "abd": "united-states",
    "brezilya": "brazil", "arjantin": "argentina", "rusya": "russia", "macaristan": "hungary", "çekya": "czech-republic",
    "avusturya": "austria", "isviçre": "switzerland", "yunanistan": "greece",
}
_TOP = re.compile(r"(premier|süper|super|prva|pro lig|primera division|eliteserien|allsvenskan|ekstraklasa|veikkausliiga|"
                  r"erovnuli|parva|botola pro|v-lig|yıldızlar|meistriliiga|a-lig|k-lig 1|1\. ?hnl|1\. ?mfl|1\. ?cfl|"
                  r"prmr|major lig|j1? ligi|\b1\. ?lig)", re.IGNORECASE)
_NOT_TOP = re.compile(r"(kadın|u\d\d|gençlik|kupa|kupası|championship|2\.|3\.|isthmian|güney ligi|kuzey premier|böl\. lig|"
                      r"ulusal lig|regionalliga|reserve|yedek)", re.IGNORECASE)
# 1. Lig adı o ülkede ikinci kademe olanlar (league_halves / datalake_lig takma adları zaten kapsar)
_FIRST_IS_SECOND = ("ingiltere", "hollanda", "türkiye", "iskoçya", "danimarka", "polonya", "suudi arabistan", "bae", "abd",
                    "japonya", "rusya", "isviçre", "isveç")
CONTINENTAL = {"uefa şampiyonlar ligi": "uefa.cl", "uefa avrupa ligi": "wr:UEFA EL", "uefa konferans ligi": "wr:UEFA CONF L",
               "afc asya şampiyonlar ligi": "wr:AFC CL", "afc kupası": "wr:AFC Pokal", "caf şampiyonlar ligi": "wr:CAF CL",
               "sudamericana kupası": "wr:Copa Sud", "libertadores kupası": "copa.l", "concacaf şampiyonlar kupası": "wr:CONCACAF CC"}
WI_ALIAS = {"fc.denmark1": "wr:denmark", "fc.poland1": "wr:poland"}


def enabled() -> bool:
    from quantfoot import settings

    env = os.environ.get("QF_GFI_PRIORS")
    return env == "1" if env is not None else bool(getattr(settings, "GFI_PRIORS_ENABLED", False))


def _read(name: str) -> list[dict]:
    p = DIR / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))


@lru_cache(maxsize=1)
def league_table() -> dict[str, dict]:
    return {r["lig"]: r for r in _read("lig_taban_gfi.csv")}


@lru_cache(maxsize=1)
def form_table() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in _read("takim_form_gfi.csv"):
        out.setdefault(r["lig"], []).append(r)
    return out


@lru_cache(maxsize=1)
def minute_table() -> dict[str, dict]:
    return {r["lig"]: r for r in _read("lig_yari_dakika_gfi.csv")}


def _low(s: str) -> str:
    return " ".join(s.replace("İ", "i").replace("I", "ı").lower().split())


def resolve(nesine_league: str | None) -> list[str]:
    """Nesine lig adı -> GFI yarışma anahtarları (mevcut league_halves takma adları önce, sonra ülke + üst lig)."""
    if not nesine_league:
        return []
    head = " ".join(nesine_league.split(",")[0].split())
    low = _low(head)
    for k, v in CONTINENTAL.items():
        if low.startswith(k):
            return [v]
    codes = lh.NESINE_TO_CODES.get(head) or lh._NORM_NESINE_TO_CODES.get(lh._norm_league_key(head), ())
    hit = [WI_ALIAS.get(c, c) for c in codes if WI_ALIAS.get(c, c) in league_table() or c in league_table()]
    if hit:
        return hit
    country = next((k for k in sorted(COUNTRY_SLUG, key=len, reverse=True) if low.startswith(k)), None)
    if not country:
        return []
    rest = low[len(country):]
    if _NOT_TOP.search(rest) or not _TOP.search(rest):
        return []
    if re.search(r"\b1\. ?lig", rest) and country in _FIRST_IS_SECOND:
        return []
    slug = COUNTRY_SLUG[country]
    from_wr = {"england": "en.1"}.get(slug)
    key = from_wr or next((k for k in (f"wr:{slug}",) if k in league_table()), None)
    if key is None:
        same = _WR_SAME.get(slug)
        key = same if same and same in league_table() else None
    return [key] if key else []


_WR_SAME = {"czech-republic": "cz.1", "hungary": "hu.1", "egypt": "eg.1", "morocco": "ma.1", "algeria": "dz.1",
            "colombia": "co.1", "australia": "au.1", "china-pr": "cn.1", "japan": "jp.1", "mexico": "mx.1",
            "united-states": "mls", "brazil": "br.1", "argentina": "ar.1", "russia": "ru.1", "switzerland": "ch.1",
            "austria": "at.1", "greece": "gr.1"}


MAX_STALE_DAYS = 800  # son maçı bundan eski lig satırı (ör. tr.2 2020) kullanılmaz


def league_row(nesine_league: str | None, table: dict | None = None, asof: str | None = None) -> dict | None:
    """Havuzlanmış (n ağırlıklı) GFI lig satırı ya da MIN_N maçtan azsa / bayatsa None."""
    table = league_table() if table is None else table
    ref = date.fromisoformat(asof) if asof else date.today()
    rows = [table[k] for k in resolve(nesine_league) if k in table
            and (ref - date.fromisoformat(table[k]["son"])).days <= MAX_STALE_DAYS]
    n = sum(int(r["n"]) for r in rows)
    if n < MIN_N:
        return None
    out = {"n": n, "lig": "+".join(r["lig"] for r in rows), "ilk": min(r["ilk"] for r in rows), "son": max(r["son"] for r in rows)}
    for col in ("gol", "ev_gol", "dep_gol", "alt15", "alt25", "alt35", "kg", "ev", "ber", "dep"):
        out[col] = sum(int(r["n"]) * float(r[col]) for r in rows) / n
    ht = [r for r in rows if r.get("iy_gol_payi")]
    nh = sum(int(r["n_iy"]) for r in ht)
    if nh >= MIN_N:
        out["iy_gol_payi"] = sum(int(r["n_iy"]) * float(r["iy_gol_payi"]) for r in ht) / nh
        out["n_iy"] = nh
    return out


def first_half_share(nesine_league: str | None, minutes: dict | None = None, table: dict | None = None) -> float:
    """Lig İY gol payı: wi dakika tablosu > GFI İY skorları > _genel; league_halves.PRIOR'a büzülür."""
    minutes = minute_table() if minutes is None else minutes
    for k in resolve(nesine_league):
        r = minutes.get(k)
        if r and int(r["n_gol"]) >= 200:
            g = int(r["n_gol"])
            return (float(r["iy_payi"]) * g + lh.PRIOR * lh.PRIOR_GOALS) / (g + lh.PRIOR_GOALS)
    row = league_row(nesine_league, table)
    if row and row.get("iy_gol_payi"):
        g = row["n_iy"] * row["gol"]
        return (row["iy_gol_payi"] * g + lh.PRIOR * lh.PRIOR_GOALS) / (g + lh.PRIOR_GOALS)
    gen = minutes.get("_genel")
    return float(gen["iy_payi"]) if gen else lh.PRIOR


def _find_team(name: str, rows: list[dict]) -> dict | None:
    key = _norm_team(name)
    best, score = None, 0.0
    for r in rows:
        s = 1.0 if r["anahtar"] == key else _team_sim(name, r["takim"])
        if s > score:
            best, score = r, s
    return best if score >= 0.62 else None


def team_lambdas(home: str, away: str, nesine_league: str | None, asof: str | None = None,
                 table: dict | None = None, forms: dict | None = None) -> tuple[float, float] | None:
    """Ev/dep beklenen gol: takım son-10 ev/dep ortalamaları lig ortalamasına FORM_K sözde-maçla büzülür."""
    lg = league_row(nesine_league, table, asof)
    if lg is None:
        return None
    forms = form_table() if forms is None else forms
    rows = [r for k in resolve(nesine_league) for r in forms.get(k, [])]
    h, a = _find_team(home, rows), _find_team(away, rows)
    if not h or not a:
        return None
    ref = date.fromisoformat(asof) if asof else date.today()
    if any((ref - date.fromisoformat(x["son_mac"])).days > FORM_MAX_AGE_DAYS for x in (h, a)):
        return None
    mh, ma = lg["ev_gol"], lg["dep_gol"]

    def shr(n, v, base):
        n = int(n or 0)
        return (n * float(v) + FORM_K * base) / (n + FORM_K) if n and v not in (None, "") else base

    h_att, h_def = shr(h["ev_n"], h["ev_at"], mh), shr(h["ev_n"], h["ev_yer"], ma)
    a_att, a_def = shr(a["dep_n"], a["dep_at"], ma), shr(a["dep_n"], a["dep_yer"], mh)
    return max(0.15, h_att * a_def / mh), max(0.15, a_att * h_def / ma)


def _pois(lam: float) -> np.ndarray:
    k = np.arange(MAX_GOALS + 1)
    p = np.exp(-lam) * lam ** k / np.array([math.factorial(int(i)) for i in k])
    return p / p.sum()


def selection_probability(name: str, lam_h: float, lam_a: float, share: float = lh.PRIOR) -> float | None:
    """Bağımsız yarı-Poisson ile bir Nesine seçiminin olasılığı; desteklenmeyen ad -> None."""
    n = normalize_leg_name(name).strip()
    neg = False
    m = re.fullmatch(r"DEĞİL\((.+)\)", n)
    if m:
        n, neg = m.group(1).strip(), True
    for suf, flip in ((" Hayır", True), (" Evet", False)):
        if n.endswith(suf):
            n, neg = n[: -len(suf)].strip(), neg ^ flip
    n = re.sub(r"^Ev Sahibi\b", "Ev", n)
    n = re.sub(r"^Deplasman\b", "Dep", n)
    p1h, p1a = _pois(lam_h * share), _pois(lam_a * share)
    p2h, p2a = _pois(lam_h * (1 - share)), _pois(lam_a * (1 - share))
    g = np.einsum("a,b,c,d->abcd", p1h, p1a, p2h, p2a)  # h1, a1, h2, a2
    i = np.arange(MAX_GOALS + 1)
    H1, A1, H2, A2 = np.meshgrid(i, i, i, i, indexing="ij")
    H, A = H1 + H2, A1 + A2
    ev = None
    if mm := re.fullmatch(r"(İY |2Y )?(\d)\.5 (Alt|Üst)", n):
        t = {"İY ": H1 + A1, "2Y ": H2 + A2}.get(mm.group(1) or "", H + A)
        ev = t <= int(mm.group(2)) if mm.group(3) == "Alt" else t > int(mm.group(2))
    elif mm := re.fullmatch(r"(Ev|Dep) (İY |2Y )?(\d)\.5 (Alt|Üst)", n):
        side = mm.group(1) == "Ev"
        t = {"İY ": H1 if side else A1, "2Y ": H2 if side else A2}.get(mm.group(2) or "", H if side else A)
        ev = t <= int(mm.group(3)) if mm.group(4) == "Alt" else t > int(mm.group(3))
    elif mm := re.fullmatch(r"(İY |2Y )?KG (Var|Yok)", n):
        h, a = {"İY ": (H1, A1), "2Y ": (H2, A2)}.get(mm.group(1) or "", (H, A))
        ev = (h > 0) & (a > 0)
        ev = ev if mm.group(2) == "Var" else ~ev
    elif mm := re.fullmatch(r"(MS|İY|2Y) (1|0|X|2)", n):
        h, a = {"MS": (H, A), "İY": (H1, A1), "2Y": (H2, A2)}[mm.group(1)]
        ev = {"1": h > a, "0": h == a, "X": h == a, "2": h < a}[mm.group(2)]
    elif mm := re.fullmatch(r"(\d)-(\d) Gol", n):
        ev = ((H + A) >= int(mm.group(1))) & ((H + A) <= int(mm.group(2)))
    elif mm := re.fullmatch(r"(Ev|Dep) (Her )?İki Yarıda (da )?Gol( Atar| Atamaz)?", n):
        side = mm.group(1) == "Ev"
        ev = ((H1 > 0) & (H2 > 0)) if side else ((A1 > 0) & (A2 > 0))
        if (mm.group(4) or "").strip() == "Atamaz":
            ev = ~ev
    elif mm := re.fullmatch(r"(Ev|Dep) (En Az Bir|Her İki) Yarıyı (da )?Kazanır", n):
        w1 = (H1 > A1) if mm.group(1) == "Ev" else (A1 > H1)
        w2 = (H2 > A2) if mm.group(1) == "Ev" else (A2 > H2)
        ev = (w1 | w2) if mm.group(2) == "En Az Bir" else (w1 & w2)
    if ev is None:
        return None
    p = float(g[ev].sum())
    return 1.0 - p if neg else p


def prior_probability(name: str, nesine_league: str | None, home: str = "", away: str = "",
                      asof: str | None = None, use_form: bool = True, table: dict | None = None,
                      forms: dict | None = None, minutes: dict | None = None) -> tuple[float, str] | None:
    """GFI öncül olasılığı: takım formu (varsa) ya da lig ortalaması gol düzeyi + lig İY payı."""
    lg = league_row(nesine_league, table, asof)
    if lg is None:
        return None
    lam = team_lambdas(home, away, nesine_league, asof, table, forms) if use_form and home and away else None
    src = "takım formu" if lam else "lig tabanı"
    lam = lam or (lg["ev_gol"], lg["dep_gol"])
    p = selection_probability(name, lam[0], lam[1], first_half_share(nesine_league, minutes, table))
    return (p, f"GFI {src} ({lg['lig']}, n={lg['n']})") if p is not None else None


# Yalnız gol-toplamı aileleri: 18–28 Kas ölçümünde MS / takım golü / yarı aileleri lig tabanına çekilince kötüleşti.
GOAL_FAMILY = re.compile(r"^((İY|2Y) )?\d\.5 (Alt|Üst)$|^KG (Var|Yok)$")


def blend(name: str, p_model: float, nesine_league: str | None, home: str = "", away: str = "",
          weight: float = lh.MODEL_WEIGHT) -> float:
    """Açıksa gol-toplamı seçimlerini GFI öncülüne weight oranında karıştırır; kapalıysa / öncül yoksa değiştirmez."""
    if not enabled() or not GOAL_FAMILY.match(name):
        return p_model
    pr = prior_probability(name, nesine_league, home, away)
    return p_model if pr is None else weight * p_model + (1.0 - weight) * pr[0]
