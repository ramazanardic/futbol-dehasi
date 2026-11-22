"""Canlı tarama: Nesine canlı bülteni (yalnız okuma) + ESPN canlı durum/istatistik + canlı gol modeli.

API-Football KULLANILMAZ (kullanıcı kararı, 21 Kasım: kota yalnız maç öncesine). Kaynaklar:
* Nesine canlı bülten  https://bulten.nesine.com/api/bulten/getlivebultenfull  (oranlar; skor/dakika yok)
* Nesine maç öncesi bülten (önbellek; maç başlamadan önceki son fiyat → maç öncesi λ)
* ESPN scoreboard + summary (dakika, skor, kırmızı kart, şut, isabetli şut, korner, topla oynama)
Bu modül hiçbir zaman bahis yapmaz; yalnız uyarı üretir.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from quantfoot.data.match_dossier import team_match_score
from quantfoot.markets import inplay

NESINE_LIVE_URL = "https://bulten.nesine.com/api/bulten/getlivebultenfull"
NESINE_PRE_URL = "https://cdnbulten.nesine.com/api/bulten/getprebultenfull"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary"

LIVE_MS = 53                      # canlı Maç Sonucu
LIVE_TOTALS = {66: 1.5, 67: 2.5, 68: 3.5}   # canlı toplam gol Alt/Üst (1 = Alt, 2 = Üst)
PRE_MS, PRE_OU25 = 1, 12
# Nesine market durumu (MA[].MS): 1 = açık, 0 = kapalı, -2 = askıda. Yalnız açık market fiyatlanır
# (21 Kasım denetimi: kapalı/askıdaki marketlerin son fiyatı fırsat gibi görünüp kupon reddine yol açtı).
MARKET_OPEN = 1
# Canlı model parametreleri doğrulanmadı; 21 Kasım'da oynanan 3 canlı bacakta model P piyasadan ortalama
# +14 puan yüksekti (Kokand 0.32 vs 0.21, Khor Fakkan 0.81 vs 0.63, Reading 0.64 vs 0.51). Karar P'si
# model ile marjsız Nesine canlı fiyatının karışımıdır; model ağırlığı kalibrasyon kanıtı gelene kadar ≤ 0.5.
LIVE_MODEL_WEIGHT = 0.5
LIVE_MODEL_WEIGHT_NO_STATS = 0.3   # şut/xG istatistiği yoksa modele daha da az güven


def _odd(x: Any) -> float | None:
    try:
        o = float(x)
    except (TypeError, ValueError):
        return None
    return o if o > 1.01 else None   # Nesine kapalı/askıdaki seçimi 1.00 gösterir


def market_open(m: dict) -> bool:
    """Nesine canlı market durumu: alan yoksa (eski kayıt) açık say; 0 / -2 / diğer → kapalı."""
    st = m.get("MS", MARKET_OPEN)
    try:
        return int(st) == MARKET_OPEN
    except (TypeError, ValueError):
        return False


def red_cards(status_red: Any, stats: dict | None) -> list[int]:
    """Kırmızı kart: FotMob/ESPN durum alanı ile istatistik ('red') alanının büyüğü (biri gecikebiliyor)."""
    st = stats or {}
    out = []
    for i, side in enumerate(("home", "away")):
        a = (status_red or [0, 0])[i] if status_red is not None else 0
        b = (st.get(side) or {}).get("red")
        out.append(max(int(a or 0), int(b or 0)))
    return out


def market_fair_probs(markets: dict[str, float]) -> dict[str, float]:
    """Nesine canlı oranlarından marjsız piyasa olasılığı (MS 1/X/2 üçlüsü ve her Alt/Üst çifti ayrı)."""
    out: dict[str, float] = {}
    trio = [markets.get(k) for k in ("MS 1", "MS X", "MS 2")]
    if all(trio):
        p = inplay.devig_power(trio)
        if p:
            out.update({"MS 1": p[0], "MS X": p[1], "MS 2": p[2]})
    for ln in sorted(set(LIVE_TOTALS.values())):
        a, u = markets.get(f"{ln} Alt"), markets.get(f"{ln} Üst")
        if a and u:
            p = inplay.devig_power([a, u])
            if p:
                out[f"{ln} Alt"], out[f"{ln} Üst"] = p[0], p[1]
    return out


def blend_with_market(p_model: float, p_market: float | None, weight: float) -> float:
    """Model olasılığını piyasaya doğru büz: w·model + (1−w)·piyasa. Piyasa yoksa model aynen döner."""
    if p_market is None:
        return p_model
    w = min(max(weight, 0.0), 1.0)
    return w * p_model + (1.0 - w) * p_market


def parse_nesine_live(payload: dict) -> list[dict]:
    out = []
    for e in ((payload or {}).get("sg") or {}).get("EA") or []:
        if e.get("TYPE") != 1:
            continue
        mk: dict[str, float] = {}
        for m in e.get("MA") or []:
            if not market_open(m):
                continue
            oc = {o.get("N"): _odd(o.get("O")) for o in m.get("OCA") or []}
            if m.get("MTID") == LIVE_MS:
                for n, lab in ((1, "MS 1"), (2, "MS X"), (3, "MS 2")):
                    if oc.get(n):
                        mk[lab] = oc[n]
            elif m.get("MTID") in LIVE_TOTALS:
                ln = LIVE_TOTALS[m["MTID"]]
                if oc.get(1):
                    mk[f"{ln} Alt"] = oc[1]
                if oc.get(2):
                    mk[f"{ln} Üst"] = oc[2]
        out.append({"code": e.get("C"), "home": e.get("HN"), "away": e.get("AN"), "kickoff_ms": e.get("ESD"),
                    "markets": mk})
    return out


def parse_nesine_prematch(payload: dict) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for e in ((payload or {}).get("sg") or {}).get("EA") or []:
        if e.get("TYPE") != 1:
            continue
        ms = ou = None
        for m in e.get("MA") or []:
            oc = {o.get("N"): _odd(o.get("O")) for o in m.get("OCA") or []}
            if m.get("MTID") == PRE_MS and all(oc.get(n) for n in (1, 2, 3)):
                ms = [oc[1], oc[2], oc[3]]
            if m.get("MTID") == PRE_OU25 and oc.get(1) and oc.get(2):
                ou = [oc[1], oc[2]]  # [Alt, Üst]
        if ms:
            out[int(e["C"])] = {"home": e.get("HN"), "away": e.get("AN"), "kickoff_ms": e.get("ESD"), "ms": ms, "ou25": ou}
    return out


def parse_minute(clock: str | None, period: int | None = None) -> float | None:
    if not clock:
        return None
    c = clock.strip().upper()
    if c in ("HT", "HALFTIME"):
        return 45.0
    m = re.match(r"(\d+)'?(?:\+(\d+))?", c)
    if not m:
        return None
    return float(m.group(1)) + (float(m.group(2)) if m.group(2) else 0.0) * 0.0  # uzatma dakikası "90" sayılır


from quantfoot.data.live_espn import american_to_decimal  # tek kaynak: EVEN/OFF desteği dahil


def parse_espn_scoreboard(payload: dict) -> list[dict]:
    out = []
    for e in (payload or {}).get("events") or []:
        st = e.get("status") or {}
        if (st.get("type") or {}).get("state") != "in":
            continue
        comp = (e.get("competitions") or [{}])[0]
        teams = {c.get("homeAway"): c for c in comp.get("competitors") or []}
        if "home" not in teams or "away" not in teams:
            continue
        hid, aid = str(teams["home"]["team"]["id"]), str(teams["away"]["team"]["id"])
        reds = {"home": 0, "away": 0}
        for d in comp.get("details") or []:
            if d.get("redCard"):
                tid = str((d.get("team") or {}).get("id"))
                if tid == hid:
                    reds["home"] += 1
                elif tid == aid:
                    reds["away"] += 1
        odds = {}
        for o in comp.get("odds") or []:
            if not isinstance(o, dict):
                continue
            h = american_to_decimal(((o.get("homeTeamOdds") or {}).get("moneyLine")))
            a = american_to_decimal(((o.get("awayTeamOdds") or {}).get("moneyLine")))
            x = american_to_decimal(((o.get("drawOdds") or {}).get("moneyLine")))
            if h and a and x:
                odds = {"ms": [h, x, a], "ou_line": o.get("overUnder")}
                break
        out.append({"event_id": str(e.get("id")), "home": teams["home"]["team"].get("displayName"),
                    "away": teams["away"]["team"].get("displayName"), "home_id": hid, "away_id": aid,
                    "minute": parse_minute(st.get("displayClock"), st.get("period")), "period": st.get("period"),
                    "hg": int(float(teams["home"].get("score") or 0)), "ag": int(float(teams["away"].get("score") or 0)),
                    "home_red": reds["home"], "away_red": reds["away"], "espn_odds": odds})
    return out


def parse_espn_summary(payload: dict, home_id: str, away_id: str) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for t in ((payload or {}).get("boxscore") or {}).get("teams") or []:
        tid = str((t.get("team") or {}).get("id"))
        side = "home" if tid == home_id else "away" if tid == away_id else None
        if not side:
            continue
        st = {x.get("name"): x.get("displayValue") for x in t.get("statistics") or []}

        def f(k: str) -> float | None:
            try:
                return float(st[k])
            except (KeyError, TypeError, ValueError):
                return None

        out[side] = {"shots": f("totalShots"), "sot": f("shotsOnTarget"), "corners": f("wonCorners"),
                     "possession": f("possessionPct"), "red": f("redCards")}
    return out


def match_live(nes: dict, espn_live: list[dict], min_score: float = 0.72) -> dict | None:
    best, score = None, 0.0
    for e in espn_live:
        s = min(team_match_score(nes["home"] or "", e["home"] or ""), team_match_score(nes["away"] or "", e["away"] or ""))
        if s > score:
            best, score = e, s
    return best if score >= min_score else None


def live_from_fotmob(m: dict, details: dict | None) -> dict:
    """FotMob canlı listesi + maç ayrıntısı → evaluate() ile uyumlu canlı durum."""
    from quantfoot.data.fotmob import parse_details
    d = parse_details(details or {}) if details else {"red": [0, 0], "stats": {}}
    score = d.get("score") or [m.get("hg"), m.get("ag")]
    reds = red_cards(d.get("red"), d.get("stats"))
    return {"source": "FotMob", "fotmob_id": m["id"], "home": m["home"], "away": m["away"], "minute": m.get("minute"),
            "hg": int(score[0] or 0), "ag": int(score[1] or 0), "home_red": reds[0],
            "away_red": reds[1], "espn_odds": {}, "stats": d.get("stats") or {}}


def match_prematch(nes: dict, pre: dict[int, dict]) -> dict | None:
    if nes.get("code") in pre:
        return pre[nes["code"]]
    best, score = None, 0.0
    for rec in pre.values():
        s = min(team_match_score(nes["home"] or "", rec["home"] or ""), team_match_score(nes["away"] or "", rec["away"] or ""))
        if s > score:
            best, score = rec, s
    return best if score >= 0.8 else None


def prematch_lambdas(pre: dict | None, espn_odds: dict | None) -> tuple[float, float, str] | None:
    if pre and pre.get("ms"):
        p = inplay.devig_power(pre["ms"])
        t = {"MS 1": p[0], "MS X": p[1], "MS 2": p[2]}
        if pre.get("ou25"):
            alt, ust = inplay.devig_power(pre["ou25"])
            t["2.5 Üst"] = ust
        lh, la = inplay.fit_lambdas(t)
        return lh, la, "Nesine maç öncesi (marjsız)"
    if espn_odds and espn_odds.get("ms"):
        p = inplay.devig_power(espn_odds["ms"])
        lh, la = inplay.fit_lambdas({"MS 1": p[0], "MS X": p[1], "MS 2": p[2]})
        return lh, la, "ESPN/DraftKings maç öncesi (marjsız)"
    return None


def evaluate(nes: dict, live: dict, lambdas: tuple[float, float, str], stats: dict | None, *,
             min_ev: float, reserve: float, kelly_mult: float, cap_frac: float, step: float, min_stake: float,
             max_minute: float = 85.0, model_weight: float | None = None) -> list[dict]:
    if live.get("minute") is None or live["minute"] >= max_minute:
        return []
    lh, la, src = lambdas
    reds = red_cards([live.get("home_red"), live.get("away_red")], stats)
    s = inplay.LiveState(minute=live["minute"], home_goals=live["hg"], away_goals=live["ag"],
                         home_red=reds[0], away_red=reds[1], stats=stats or {})
    rh, ra, notes = inplay.remaining_lambdas(lh, la, s)
    fair = inplay.final_probabilities(rh, ra, live["hg"], live["ag"])
    mkt = market_fair_probs(nes["markets"])
    has_stats = bool((stats or {}).get("home"))
    w = model_weight if model_weight is not None else (LIVE_MODEL_WEIGHT if has_stats else LIVE_MODEL_WEIGHT_NO_STATS)
    live = {**live, "home_red": reds[0], "away_red": reds[1]}
    ops = []
    for mk, odds in nes["markets"].items():
        p_model = fair.get(mk)
        if p_model is None or p_model <= 0.0 or odds < 1.20:
            continue
        p = blend_with_market(p_model, mkt.get(mk), w)
        ev = p * odds - 1.0
        if ev < min_ev or ev > 0.6:   # > %60 → veri/eşleşme hatası şüphesi, uyarı yok
            continue
        stake = inplay.kelly_stake(p, odds, reserve, kelly_mult, cap_frac, step, min_stake)
        ops.append({"code": nes["code"], "match": f"{nes['home']} - {nes['away']}", "minute": live["minute"],
                    "score": f"{live['hg']}-{live['ag']}", "red": f"{live['home_red']}-{live['away_red']}",
                    "market": mk, "nesine_odds": odds, "fair_prob": round(p, 4), "fair_odds": round(1 / p, 2),
                    "model_prob": round(p_model, 4), "market_prob": (round(mkt[mk], 4) if mk in mkt else None),
                    "model_weight": w,
                    "ev": round(ev, 4), "stake_tl": stake, "prematch_source": src,
                    "lambda_remaining": [round(rh, 3), round(ra, 3)], "notes": notes})
    return ops


def dedupe(ops: list[dict], state: dict, now: dt.datetime, improve: float = 0.03, ttl_h: float = 4.0) -> list[dict]:
    """Aynı (maç, pazar) fırsatı yalnız oran en az ``improve`` oranında iyileşirse tekrar gönderilir."""
    cutoff = (now - dt.timedelta(hours=ttl_h)).timestamp()
    for k in [k for k, v in state.items() if v.get("t", 0) < cutoff]:
        del state[k]
    fresh = []
    for o in ops:
        key = f"{o['code']}|{o['market']}"
        prev = state.get(key)
        if prev is None or o["nesine_odds"] >= prev["odds"] * (1 + improve):
            fresh.append(o)
            state[key] = {"odds": o["nesine_odds"], "ev": o["ev"], "t": now.timestamp()}
    return fresh


def format_line(o: dict) -> str:
    stake = f"önerilen pay {o['stake_tl']:.0f} TL" if o["stake_tl"] else "pay önerilmez (canlı rezerv yok / çok küçük)"
    return (f"[{o['minute']:.0f}' {o['score']}] {o['match']} — {o['market']}: Nesine {o['nesine_odds']:.2f}, "
            f"adil {o['fair_odds']:.2f} (%{o['fair_prob'] * 100:.1f}), EV {o['ev']:+.1%}, {stake}")
