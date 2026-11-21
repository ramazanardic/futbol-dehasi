#!/usr/bin/env python3
"""300 TL → ≥2000 TL kupon (oran ≥6.70). Bahis oynamaz."""
from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from quantfoot.markets.families import bet_family
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition, is_cup_competition
from quantfoot.data.oddsmath import is_women_match, is_youth_or_reserve_match
from nesine_global import is_sharp_source, _sim  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
TSI = dt.timezone(dt.timedelta(hours=3))

MIN_ODDS, MAX_ODDS = 1.25, 2.10
MIN_P, RELAX_P = 0.55, 0.53
LEAD_MIN = 25
DAY_END = dt.datetime(2026, 11, 22, 7, 0, tzinfo=TSI)
TARGET_ODDS_LO, TARGET_ODDS_HI = 6.70, 7.20
ODDS_HARD_MAX = 7.80  # "not much higher" than 7.20
STAKE_TL = 300.0
MIN_PAYOUT = 2000.0

# Bugün oynanmış bütün kupon maçları (K1, K3–K6, banko 7.27, 5.00'lik, 10'lu MS1, 10'lu banko).
# 10'lu banko oynanan hali: Tottenham/Mineiro yerine Genk + West Ham.
# Dosyadaki Tottenham/Mineiro da güvenlik için çıkarıldı (kupon_10_banko.json).
USED = {
    # K1
    3319709, 3359425, 3318200,
    # K3
    3314007, 3314236, 3313105,  # Galatasaray, Southampton, Charleroi
    # K4
    3318757, 3313080, 3313626,  # Vallecano, Fleury, Bolton
    # K5
    3313940, 3313644, 3313868,  # CSKA, Carrarese, Yeovil
    # K6
    3312554, 3314647, 3319368,  # Norwich, Millwall, Elche B
    # Banko 5'li (7.27, 400 TL)
    3313572, 3312753, 3318505, 3313774, 3314607,  # Barendrecht, Coleraine, Antequera, Grazer, Lille
    # 5.00'lik (100 TL)
    3318770, 3314269, 3312556, 3314246, 3312717,  # Milan(K), Sturm II, Catanzaro, Lazio, Napoli
    # 10'lu MS 1 (100 TL)
    3313785, 3314719, 3314324, 3313822, 3319951,
    3318479, 3313708, 3313035, 3313692, 3314218,
    # 10'lu banko (150 TL) — oynanan hali + dosyadaki düşürülen iki maç
    3314600, 3314363, 3318436, 3391094, 3312528,
    3314573, 3313958, 3314396, 3313833, 3314223,
    3313082, 3339060,  # Tottenham, Mineiro (dosyada vardı, oynanmadı)
    # Canlı 3'lü
    3307474, 3314339, 3405042,  # Kokand, Khor Fakkan, Reading
}

RED_MATCHES = {3312656, 3318418, 3312726, 3313417}  # LASK, Hamkam, Dundee-Hearts, Ferencváros
SOFT_SKIP = {
    3312511,  # Nice–PSG
    3312540,  # Sheffield Utd–Watford
    3312698,  # Lens–Toulouse
    3313263,  # Feyenoord–Excelsior
    3313622,  # Falkirk–St Johnstone
    3313762,  # Mechelen–Club Brugge
    3318615,  # Real Madrid–Celta
    3318820,  # Sevilla–Betis
    3320028,  # Palmeiras–Flamengo (ağır steam)
}

ALLOWED_FAMILIES = {
    "Çifte Şans", "Alt/Üst", "Maç Sonucu", "Karşılıklı Gol",
    "Takım Golleri", "İY Alt/Üst", "2Y Alt/Üst", "Handikap",
    "İY Sonucu", "2Y Sonucu",
}
CUP_OK_FAMILIES = {"Alt/Üst", "Takım Golleri", "Karşılıklı Gol", "İY Alt/Üst", "2Y Alt/Üst"}
CLASSIC_FAM = {"Alt/Üst", "Maç Sonucu", "Çifte Şans", "Karşılıklı Gol", "İY Alt/Üst"}
FAMILY_RANK = {
    "Çifte Şans": 0, "Alt/Üst": 1, "Maç Sonucu": 2, "Karşılıklı Gol": 3,
    "Takım Golleri": 4, "İY Alt/Üst": 5, "İY Sonucu": 6, "2Y Alt/Üst": 7,
    "2Y Sonucu": 8, "Handikap": 9, "Yarı Özel": 10, "Tek/Çift": 11,
    "Toplam Gol Aralığı": 12, "Yarı KG": 13, "İY/MS": 14, "Fark": 15,
    "Kombine": 16, "İlk Gol": 17, "Doğru Skor": 18, "Korner": 19,
    "Kart": 20, "Diğer": 21,
}
MAIN_DIRECT = {
    "MS 1", "MS 0", "MS 2",
    "ÇŞ 1X", "ÇŞ 10", "ÇŞ 12", "ÇŞ X2", "ÇŞ 02", "ÇŞ 1-X", "ÇŞ 1-2", "ÇŞ X-2",
    "1.5 Alt", "1.5 Üst", "2.5 Alt", "2.5 Üst", "3.5 Alt", "3.5 Üst", "0.5 Alt", "0.5 Üst",
    "4.5 Alt", "4.5 Üst",
    "KG Var", "KG Yok",
}

# Akşam 5'li (oynanmadı) — serbestçe kullanılabilir
AKSAM5 = {3314672, 3314242, 3314141, 3318334, 3319486}


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def load_flags() -> tuple[dict, dict]:
    by_code: dict[int, dict] = {}
    euro: dict[str, str] = {}
    p = Path("/tmp/ba_stage2.json")
    if p.exists():
        s2 = json.loads(p.read_text())
        euro = s2.get("euro_teams") or {}
        for row in (s2.get("banko_all") or []) + (s2.get("ranked") or []):
            rec = by_code.setdefault(int(row["code"]), {})
            if row.get("rotation"):
                rec["rotation"] = list(dict.fromkeys((rec.get("rotation") or []) + list(row["rotation"])))
            if row.get("soft_flags"):
                rec["soft_flags"] = list(dict.fromkeys((rec.get("soft_flags") or []) + list(row["soft_flags"])))
            for k in ("home_unavailable", "away_unavailable", "form", "reason"):
                if row.get(k) and k not in rec:
                    rec[k] = row[k]
    return by_code, euro


def _tokens(s: str) -> set[str]:
    stop = {
        "fc", "cf", "sc", "ac", "sk", "fk", "nk", "cd", "ca", "club", "de", "da",
        "the", "utd", "united", "k", "w", "bk", "if", "ik", "afc", "as", "ssc", "us",
    }
    return {t for t in _norm(s).split() if t and t not in stop and len(t) >= 3}


GENERIC_CLUB = {
    "dinamo", "dynamo", "sporting", "inter", "real", "port", "union", "racing",
    "atletico", "athletic", "rangers", "wanderers", "sport", "city", "town",
}


def euro_hits(home: str, away: str, euro: dict[str, str]) -> list[str]:
    out = []
    for name, comp in euro.items():
        for side in (home, away):
            nt, st = _tokens(name), _tokens(side)
            if not nt or not st:
                continue
            sim = _sim(name, side)
            same_tokens = nt == st
            if not same_tokens and sim < 0.80:
                continue
            if (len(nt) == 1 and next(iter(nt)) in GENERIC_CLUB and nt != st) or (
                len(st) == 1 and next(iter(st)) in GENERIC_CLUB and nt != st
            ):
                continue
            if not same_tokens and (nt - st) and (st - nt):
                continue
            out.append(f"{name}: {comp}")
            break
    return list(dict.fromkeys(out))


def is_reserve_side(league: str, home: str, away: str) -> bool:
    if is_youth_or_reserve_match(league, home, away) or is_women_match(league, home, away):
        return True
    txt = f"{home} {away}"
    return bool(re.search(r"(?:^|\s)(?:2|II)\s*$|\(Amt|\bAmt\.|\breserves?\b|\bII\b", txt, re.I))


def steam_against(market: str, sel: str, steam: list) -> float | None:
    if not steam or len(steam) < 3:
        return None
    if market == "Maç Sonucu":
        i = {"1": 0, "X": 1, "0": 1, "2": 2}.get(str(sel).strip())
        return None if i is None else float(steam[i])
    if market == "Çifte Şans":
        key = str(sel).replace(" ", "").upper()
        idx = {
            "1-X": (0, 1), "1X": (0, 1), "10": (0, 1),
            "1-2": (0, 2), "12": (0, 2),
            "X-2": (1, 2), "X2": (1, 2), "02": (1, 2),
        }.get(key)
        if not idx:
            return None
        return float(steam[idx[0]] + steam[idx[1]])
    return None


def cs_prob(fair_1x2, sel: str) -> float | None:
    if not fair_1x2 or len(fair_1x2) < 3:
        return None
    key = str(sel).replace(" ", "").upper()
    f0, f1, f2 = map(float, fair_1x2)
    return {
        "1-X": f0 + f1, "1X": f0 + f1, "10": f0 + f1,
        "1-2": f0 + f2, "12": f0 + f2,
        "X-2": f1 + f2, "X2": f1 + f2, "02": f1 + f2,
    }.get(key)


def ref_age_h(m: dict, now: dt.datetime) -> float | None:
    raw = m.get("ref_fetched_utc")
    if not raw:
        return m.get("ref_age_hours")
    try:
        t = dt.datetime.fromisoformat(raw)
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (now.astimezone(dt.timezone.utc) - t.astimezone(dt.timezone.utc)).total_seconds() / 3600
    except ValueError:
        return m.get("ref_age_hours")


def reason_line(m, s, flags, mu, steam, form, n_abs) -> str:
    bits = []
    if mu and mu[0] and mu[1]:
        bits.append(f"xG-μ {mu[0]:.2f}-{mu[1]:.2f}")
    if form and any(form):
        bits.append(f"form {'/'.join(x or '-' for x in form)}")
    if steam and any(abs(x or 0) >= 0.015 for x in steam[:3]):
        bits.append("steam 1/X/2 " + "/".join(f"{(x or 0)*100:+.1f}p" for x in steam[:3]))
    if n_abs:
        bits.append(n_abs)
    if flags.get("rotation"):
        bits.append("rotasyon " + "; ".join(flags["rotation"][:2]))
    src = (m.get("reference") or "").split(" (")[0]
    if src:
        bits.append(src)
    return "; ".join(bits) or "keskin fiyattan türetilmiş olasılık"


def prod(xs) -> float:
    out = 1.0
    for x in xs:
        out *= x
    return out


def summary(ls: list[dict]) -> dict:
    if not ls:
        return {}
    total_odds = prod(x["odds"] for x in ls)
    p_win = prod(x["p"] for x in ls)
    ev = p_win * total_odds - 1
    payout = STAKE_TL * total_odds
    return dict(
        n=len(ls),
        total_odds=round(total_odds, 4),
        p_win=round(p_win, 6),
        ev=round(ev, 4),
        stake_tl=STAKE_TL,
        payout_tl=round(payout, 2),
        payout_ok=payout + 1e-9 >= MIN_PAYOUT,
        max_mbs=max(x["mbs"] for x in ls),
        mbs_ok=len(ls) >= max(x["mbs"] for x in ls),
        n_classic=sum(1 for x in ls if x["family"] in CLASSIC_FAM),
        n_direct=sum(1 for x in ls if x["direct"]),
        n_p65=sum(1 for x in ls if x["p"] >= 0.65),
        n_p55_65=sum(1 for x in ls if 0.55 <= x["p"] < 0.65),
        n_sharp=sum(1 for x in ls if x["sharp"]),
        earliest=min(x["ko"] for x in ls),
        latest=max(x["ko"] for x in ls),
        in_band=TARGET_ODDS_LO - 1e-9 <= total_odds <= TARGET_ODDS_HI + 1e-9,
        reused_aksam5=[x["match"] for x in ls if x["code"] in AKSAM5],
    )


def score_coupon(legs: list[dict]) -> tuple:
    """Higher is better. Primary: joint P; prefer in-band; then fewer legs; quality tie-breaks."""
    total = prod(x["odds"] for x in legs)
    p_win = prod(x["p"] for x in legs)
    in_band = 1 if TARGET_ODDS_LO - 1e-9 <= total <= TARGET_ODDS_HI + 1e-9 else 0
    n_direct = sum(1 for x in legs if x["direct"])
    n_classic = sum(1 for x in legs if x["family"] in CLASSIC_FAM)
    # Prefer being close to 6.70 (price-slip buffer) once payout is met
    gap = 0.0 if in_band else abs(total - (TARGET_ODDS_LO if total < TARGET_ODDS_LO else TARGET_ODDS_HI))
    earliest = min(x["ko"] for x in legs)
    return (in_band, p_win, -len(legs), n_direct, n_classic, -gap, earliest)


def compact_leg(x: dict) -> dict:
    return {
        "code": x["code"],
        "kickoff_tsi": x["kickoff_tsi"],
        "ko": x["ko"],
        "league": x["league"],
        "match": x["match"],
        "market": x["market"],
        "sel": x["sel"],
        "odds": x["odds"],
        "p_blend": x["p"],
        "p_sharp": x["p_sharp"],
        "fair": x["fair"],
        "ev": x["ev"],
        "direct": x["direct"],
        "family": x["family"],
        "mbs": x["mbs"],
        "ref": x["ref"],
        "reason": x["reason"],
        "from_aksam5": x["code"] in AKSAM5,
    }


def combo_record(legs: list[dict], label: str) -> dict:
    legs = sorted(legs, key=lambda r: r["ko"])
    sm = summary(legs)
    sm["label"] = label
    sm["legs"] = [compact_leg(x) for x in legs]
    return sm


def pick_options(recs: list[dict], max_opts: int = 3) -> list[dict]:
    recs = sorted(
        recs,
        key=lambda r: (
            r["p"] + (0.008 if r["direct"] else 0.0) + (0.003 if r["family"] in CLASSIC_FAM else 0.0),
            r["ev"],
            -FAMILY_RANK.get(r["family"], 99),
        ),
        reverse=True,
    )
    opts = [recs[0]]
    seen = {(recs[0]["market"], recs[0]["sel"])}

    def add(r):
        key = (r["market"], r["sel"])
        if key in seen:
            return
        if abs(r["odds"] - opts[0]["odds"]) < 0.04 and r["p"] < opts[0]["p"] - 0.005:
            return
        opts.append(r)
        seen.add(key)

    # Higher-odds alternative that still keeps most of the probability
    for r in recs[1:]:
        if r["odds"] >= opts[0]["odds"] + 0.08 and r["p"] >= opts[0]["p"] - 0.04:
            add(r)
            break
    # Mid-band (1.40–1.70) alternative for 5-leg construction
    mid = [r for r in recs if 1.40 - 1e-12 <= r["odds"] <= 1.70 + 1e-12]
    if mid:
        add(mid[0])
    # High-band (1.55–2.10) if useful
    high = [r for r in recs if r["odds"] >= 1.55]
    if high:
        add(high[0])
    return opts[:max_opts]


def build_pool(ng: dict, now: dt.datetime, cutoff: dt.datetime, min_p: float) -> tuple[list[dict], dict, set, set]:
    cal = load_live_calibration() or {}
    flag_by, euro = load_flags()
    all_recs: list[dict] = []
    skipped = {
        "used": 0, "red": 0, "rotation": 0, "soft": 0, "early": 0,
        "late": 0, "not_priced": 0, "steam": 0, "not_sharp": 0, "no_leg": 0,
    }
    families_seen: set[str] = set()
    families_eligible: set[str] = set()

    for m in ng.get("matches") or []:
        try:
            ko = dt.datetime.fromisoformat(m["kickoff_iso"])
            if ko.tzinfo is None:
                ko = ko.replace(tzinfo=TSI)
        except Exception:
            continue
        if ko < cutoff:
            skipped["early"] += 1
            continue
        if ko >= DAY_END:
            skipped["late"] += 1
            continue
        code = int(m["code"])
        if m.get("status") != "fiyatlandı" or m.get("price_tier") not in {"keskin", "global_buro"}:
            skipped["not_priced"] += 1
            continue
        if code in USED:
            skipped["used"] += 1
            continue
        if code in RED_MATCHES:
            skipped["red"] += 1
            continue
        flags = dict(flag_by.get(code, {}) or {})
        rot = list(flags.get("rotation") or [])
        rot += [
            h for h in euro_hits(m["home"], m["away"], euro)
            if any(tok in h.lower() for tok in (
                "champions league", "europa league", "conference league",
                "libertadores", "sudamericana",
            ))
        ]
        rot = list(dict.fromkeys(rot))
        flags["rotation"] = rot
        heavy = [r for r in rot if any(tok in r.lower() for tok in (
            "champions league", "europa league", "conference league",
            "libertadores", "sudamericana",
        ))]
        if heavy or code in SOFT_SKIP:
            skipped["rotation" if heavy else "soft"] += 1
            continue
        if is_reserve_side(m.get("league") or "", m["home"], m["away"]):
            skipped["soft"] += 1
            continue
        hu, au = flags.get("home_unavailable") or [], flags.get("away_unavailable") or []
        if "çok eksik oyuncu" in (flags.get("soft_flags") or []) or len(hu) >= 7 or len(au) >= 7:
            skipped["soft"] += 1
            continue

        research = m.get("research") or {}
        rflags = research.get("flags") or []
        if any("şiddetli" in str(f).lower() or "severe" in str(f).lower() for f in rflags):
            skipped["soft"] += 1
            continue
        wx = (research.get("weather") or {})
        if wx.get("severe"):
            skipped["soft"] += 1
            continue

        steam = m.get("steam_1x2") or [0, 0, 0]
        if any(abs(float(x or 0)) >= 0.08 for x in steam[:3]):
            skipped["steam"] += 1
            continue

        mu = (m.get("mu_home"), m.get("mu_away"))
        sharp = m.get("price_tier") == "keskin" and is_sharp_source(m.get("reference"))
        if not sharp:
            skipped["not_sharp"] += 1
            continue
        age = ref_age_h(m, now)
        uncal = is_uncalibrated_competition(m.get("league"))
        form = flags.get("form")
        if not form:
            th = ((research.get("teams") or {}).get("home") or {}).get("form")
            ta = ((research.get("teams") or {}).get("away") or {}).get("form")
            form = [th, ta] if th or ta else None
        n_abs = f"eksik ev {len(hu)} / dep {len(au)}" if (hu or au) else None

        kept = 0
        for s in m.get("selections") or []:
            odds = s.get("odds")
            if not odds or odds < MIN_ODDS - 1e-9 or odds > MAX_ODDS + 1e-9:
                continue
            fam = bet_family(s.get("name") or "")
            families_seen.add(fam)
            if uncal and (s.get("name") not in MAIN_DIRECT and not (
                s.get("market") in {
                    "Maç Sonucu", "Çifte Şans", "1,5 Gol Alt/Üst", "2,5 Gol Alt/Üst",
                    "3,5 Gol Alt/Üst", "Karşılıklı Gol",
                } and s.get("direct")
            )):
                continue
            if fam not in ALLOWED_FAMILIES:
                continue
            if is_cup_competition(m.get("league")) and fam not in CUP_OK_FAMILIES:
                continue
            fp = s.get("fair_prob")
            if s.get("market") == "Çifte Şans":
                alt = cs_prob(m.get("fair_1x2"), s.get("selection"))
                if alt:
                    fp = alt
            if not fp or fp <= 0:
                continue
            p_sharp = float(fp)
            p = calibrated_probability(p_sharp, bool(s.get("direct")), cal)
            p_blend = 0.70 * float(p) + 0.30 * p_sharp
            if p_blend < min_p - 1e-12:
                continue
            sa = steam_against(s.get("market") or "", str(s.get("selection") or ""), steam)
            if sa is not None and sa <= -0.05:
                skipped["steam"] += 1
                continue
            families_eligible.add(fam)
            ev = p_blend * float(odds) - 1
            all_recs.append(dict(
                code=code,
                ko=m["kickoff"],
                ko_iso=m["kickoff_iso"],
                kickoff_tsi=m["kickoff"][11:] if len(m["kickoff"]) >= 16 else m["kickoff"],
                league=m.get("league"),
                match=f"{m['home']} - {m['away']}",
                home=m["home"],
                away=m["away"],
                market=s["market"],
                sel=s["selection"],
                name=s.get("name"),
                family=fam,
                odds=round(float(odds), 4),
                p=round(p_blend, 4),
                p_cal=round(float(p), 4),
                p_sharp=round(p_sharp, 4),
                fair=round(1 / p_blend, 3) if p_blend > 0 else None,
                ev=round(ev, 4),
                mbs=int(s.get("mbs") or 1),
                direct=bool(s.get("direct")),
                offered=True,
                sharp=True,
                ref=m.get("reference"),
                ref_fetched_utc=m.get("ref_fetched_utc"),
                ref_age_h=None if age is None else round(age, 2),
                price_tier=m.get("price_tier"),
                mu=[None if mu[0] is None else round(float(mu[0]), 3),
                    None if mu[1] is None else round(float(mu[1]), 3)],
                steam=steam,
                form=form,
                rotation=rot,
                research_flags=rflags,
                reason=reason_line(m, s, flags, mu, steam, form, n_abs),
                red_flags=[],
            ))
            kept += 1
        if kept == 0:
            skipped["no_leg"] += 1
    return all_recs, skipped, families_seen, families_eligible


def search_n(by_match: list[tuple[int, list[dict]]], n: int, match_cap: int) -> dict | None:
    """Maximize joint P among n-leg coupons with odds in [6.70, hard_max], prefer [6.70, 7.20]."""
    ranked = sorted(by_match, key=lambda kv: -kv[1][0]["p"])[: max(n, min(match_cap, len(by_match)))]
    if len(ranked) < n:
        return None
    best: tuple | None = None
    best_legs: list[dict] | None = None
    n_ok = 0
    n_seen = 0
    for idxs in itertools.combinations(range(len(ranked)), n):
        option_lists = [ranked[i][1] for i in idxs]
        max_odds = prod(max(o["odds"] for o in opts) for opts in option_lists)
        if max_odds < TARGET_ODDS_LO - 1e-9:
            continue
        min_odds = prod(min(o["odds"] for o in opts) for opts in option_lists)
        if min_odds > ODDS_HARD_MAX + 1e-9:
            continue
        max_p = prod(max(o["p"] for o in opts) for opts in option_lists)
        # If even the max-P product is worse than current best AND that product can be in-band,
        # we might still need a lower-P higher-odds product to enter the band.
        # Only prune when we already have an in-band coupon and max_p cannot beat it.
        if best is not None and best[0] == 1 and max_p < best[1] - 1e-15:
            continue
        for opts in itertools.product(*option_lists):
            n_seen += 1
            total = prod(o["odds"] for o in opts)
            if total < TARGET_ODDS_LO - 1e-9 or total > ODDS_HARD_MAX + 1e-9:
                continue
            if total * STAKE_TL + 1e-9 < MIN_PAYOUT:
                continue
            legs = list(opts)
            if max(x["mbs"] for x in legs) > n:
                continue
            sc = score_coupon(legs)
            n_ok += 1
            if best is None or sc > best:
                best = sc
                best_legs = legs
    if not best_legs:
        return None
    rec = combo_record(best_legs, f"{n} bacak")
    rec["n_ok"] = n_ok
    rec["n_seen"] = n_seen
    return rec


def choose_final(cands: dict[int, dict]) -> tuple[dict | None, str]:
    """5–6 default; 7 only if it clearly raises joint P."""
    c5, c6, c7 = cands.get(5), cands.get(6), cands.get(7)
    base = None
    why_parts = []
    # Prefer in-band, then higher P; 5 vs 6: pick higher joint P (no 'clearly' bar)
    for c in (c5, c6):
        if not c:
            continue
        if base is None:
            base = c
            continue
        # Prefer in-band
        if c["in_band"] and not base["in_band"]:
            base = c
            continue
        if base["in_band"] and not c["in_band"]:
            continue
        if c["p_win"] > base["p_win"] + 1e-15:
            base = c
        elif abs(c["p_win"] - base["p_win"]) <= 1e-15 and c["n"] < base["n"]:
            base = c
    if base is None and c7:
        base = c7
        why_parts.append("5 ve 6 bacaklı hedef bantta kupon yok; 7 bacak kullanıldı.")
    if base is None:
        return None, "Hedef oranı (6.70–7.80) karşılayan kupon bulunamadı."

    if c5 and c6:
        why_parts.append(
            f"5 bacak: oran {c5['total_odds']:.2f}, ortak P {c5['p_win']:.1%}; "
            f"6 bacak: oran {c6['total_odds']:.2f}, ortak P {c6['p_win']:.1%}."
        )
        if base is c6 and c6["p_win"] >= c5["p_win"]:
            why_parts.append("6 bacak daha yüksek (veya eşit) ortak P verdiği için seçildi.")
        elif base is c5:
            why_parts.append("5 bacak daha yüksek ortak P verdiği için seçildi.")
    elif c5:
        why_parts.append(f"Yalnız 5 bacak hedefi tuttu (oran {c5['total_odds']:.2f}, P {c5['p_win']:.1%}).")
    elif c6:
        why_parts.append(f"Yalnız 6 bacak hedefi tuttu (oran {c6['total_odds']:.2f}, P {c6['p_win']:.1%}).")

    if c7 and base is not c7:
        rel = c7["p_win"] / base["p_win"] if base["p_win"] else 0
        abs_d = c7["p_win"] - base["p_win"]
        clearly = rel >= 1.08 and abs_d >= 0.005
        why_parts.append(
            f"7 bacak: oran {c7['total_odds']:.2f}, ortak P {c7['p_win']:.1%} "
            f"(fark {abs_d:+.2%} / {rel:.2f}×)."
        )
        if clearly and (c7["in_band"] or not base["in_band"]):
            base = c7
            why_parts.append("7 bacak ortak P'yi belirgin yükselttiği için seçildi.")
        else:
            why_parts.append("7 bacak ortak P'yi belirgin yükseltmedi; 7. bacak eklenmedi.")
    return base, " ".join(why_parts)


def fmt_pct(p: float) -> str:
    return f"{p*100:.1f}%"


def write_md(path: Path, out: dict) -> None:
    sm = out["summary"]
    chosen = out["legs"]
    price_ts = out["price_timestamp_nesine"]
    now = out["built_at"]
    cutoff = out["cutoff_kickoff_tsi"]
    md = [
        "# 300 TL → en az 2.000 TL kupon — hazır, oynanmadı",
        "",
        f"Nesine fiyatı: **{price_ts}**. Kurulum: **{now}**. "
        f"Başlama saati ≥ **{cutoff[11:16] if len(cutoff) >= 16 else cutoff} TSİ** (şimdi+25 dk). "
        f"Pay **300 TL**, hedef ödeme ≥ 2.000 TL (toplam oran ≥ 6.70, hedef bant 6.70–7.20). "
        f"Bacak oranları 1.25–2.10, P_blend tercih ≥ %55, maç başı tek seçim, keskin referans "
        f"(Pinnacle/Smarkets/OddsMath BetInAsia), bültende açık. "
        f"Bugün oynanmış kupon maçları çıkarıldı. **Bahis oynanmadı.**",
        "",
        "Bu kupon **banko değildir**. Kullanıcı, zararı kapatmak için %55–65 civarı bacakları açıkça kabul etti. "
        f"Ortak tutma ihtimali yaklaşık **{fmt_pct(sm['p_win'])}** (kabaca {round(1/sm['p_win'])}'de 1). "
        f"EV **{sm['ev']:+.1%}** — Nesine payı bileşikleşir, beklenen değer negatiftir.",
        "",
        f"## Seçilen kupon: {sm['n']} maç, oran **{sm['total_odds']:.2f}**, "
        f"300 TL ile ödeme **{sm['payout_tl']:.2f} TL**, ortak P **{fmt_pct(sm['p_win'])}**, EV **{sm['ev']:+.1%}**",
        "",
        f"{out['selection_reason']}",
        "",
        f"En büyük MBS {sm['max_mbs']} ({'uygun' if sm['mbs_ok'] else 'UYGUN DEĞİL'}). "
        f"En erken başlama: **{sm['earliest']} TSİ** — bu saatten önce oynanmalı. "
        f"{'Lig yığılması: ' + ', '.join(f'{k} ×{v}' for k,v in out['league_clustering'].items()) + '.' if out['league_clustering'] else 'Aynı ligde yığılma yok.'} "
        f"{('Akşam 5\'liden alınan maçlar: ' + ', '.join(sm['reused_aksam5']) + '.') if sm.get('reused_aksam5') else 'Akşam 5\'li (oynanmadı) maçlarından hiçbiri seçilmedi; daha yüksek ortak P veren alternatifler vardı.' if out.get('aksam5_available') else ''}",
        "",
        "| # | Kod | Saat (TSİ) | Lig | Maç | Pazar → Seçim | Oran | P_blend | Keskin adil P | Adil oran | EV | MBS | Ref | Gerekçe |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, x in enumerate(chosen, 1):
        md.append(
            f"| {i} | {x['code']} | {x['kickoff_tsi']} | {x['league']} | {x['match']} | "
            f"{x['market']} → {x['sel']} | {x['odds']:.2f} | {fmt_pct(x['p'])} | {fmt_pct(x['p_sharp'])} | "
            f"{x['fair']} | {x['ev']:+.1%} | {x['mbs']} | {(x['ref'] or '').split(' (')[0]} | {x['reason']} |"
        )
    md += ["", "## Karşılaştırılan alternatifler", ""]
    alts = out.get("alternatives") or {}
    if not alts:
        md.append("_Başka bacak sayısında hedefi tutan kupon yok._")
    else:
        md.append("| Bacak | Oran | 300 TL ödeme | Ortak P | EV | Bantta? | En erken | Özet |")
        md.append("|---|---|---|---|---|---|---|---|")
        for n in (5, 6, 7):
            c = alts.get(str(n)) or alts.get(n)
            if not c:
                md.append(f"| {n} | — | — | — | — | — | — | hedef bantta yok |")
                continue
            brief = " + ".join(
                f"{lg['match'].split(' - ')[0]} {lg['sel']} @{lg['odds']:.2f}"
                for lg in c["legs"]
            )
            md.append(
                f"| {c['n']} | {c['total_odds']:.2f} | {c['payout_tl']:.2f} TL | {fmt_pct(c['p_win'])} | "
                f"{c['ev']:+.1%} | {'evet' if c['in_band'] else 'hayır'} | {c['earliest']} | {brief} |"
            )
    md += ["", "## Yedek bacaklar (oran hareket ederse)", ""]
    reserves = out.get("backups") or []
    if reserves:
        for x in reserves:
            md.append(
                f"- {x['code']} {x['kickoff_tsi']} {x['match']} — {x['market']}: {x['sel']} @ {x['odds']:.2f} "
                f"(P_blend {fmt_pct(x['p'])}, keskin adil {fmt_pct(x['p_sharp'])}, EV {x['ev']:+.1%}, MBS {x['mbs']}) — {x['reason']}"
            )
    else:
        md.append("_Uygun yedek bacak yok._")
    sk = out.get("skipped") or {}
    md += [
        "",
        "## Notlar",
        "",
        f"- Havuz: {out['pool_matches']} maç / {out['pool_selections']} seçim (P_blend ≥ {out['min_p_used']:.0%}, oran 1.25–2.10, keskin referans).",
        f"- P_blend = 0.70·kalibre model + 0.30·keskin adil P (model zaten keskin 1X2/OU skor matrisine fit).",
        f"- Oynanmış kupon maçları, kırmızı bayrak, ağır Avrupa rotasyonu, çok eksik kadro, yedek/kadın maçları, "
        f"|steam|≥8p veya seçim aleyhine ≥5p ve keskin referansı olmayan maçlar çıkarıldı.",
        f"- Atlanan: {sk}.",
        f"- Bu kupon banko korumasından (P≥%65, oran≤1.80) geçmez; kullanıcı düşük tabanı açıkça kabul etti.",
        "- Bahis oynanmadı. Oynanacaksa oranlar yeniden kontrol edilmeli.",
        "",
    ]
    path.write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> None:
    now = dt.datetime.now(TSI)
    cutoff = now + dt.timedelta(minutes=LEAD_MIN)
    ng_path = D / "nesine_global.json"
    ng = json.loads(ng_path.read_text())
    price_ts = ng.get("generated_at")

    min_p_used = MIN_P
    all_recs, skipped, families_seen, families_eligible = build_pool(ng, now, cutoff, MIN_P)
    by = defaultdict(list)
    for r in all_recs:
        by[r["code"]].append(r)
    by_match = [(code, pick_options(recs, 3)) for code, recs in by.items()]

    # If 5/6 cannot reach 6.70, relax the floor slightly
    def enough_odds(bm, n):
        top = sorted(bm, key=lambda kv: -max(o["odds"] for o in kv[1]))
        if len(top) < n:
            return False
        # crude: product of n highest-odds match-options
        bests = [max(o["odds"] for o in kv[1]) for kv in top[:n]]
        return prod(bests) >= TARGET_ODDS_LO

    if not (enough_odds(by_match, 5) or enough_odds(by_match, 6) or enough_odds(by_match, 7)):
        min_p_used = RELAX_P
        all_recs, skipped, families_seen, families_eligible = build_pool(ng, now, cutoff, RELAX_P)
        by = defaultdict(list)
        for r in all_recs:
            by[r["code"]].append(r)
        by_match = [(code, pick_options(recs, 3)) for code, recs in by.items()]

    # Search caps: keep runtime modest while covering mid vs short structures
    caps = {5: 30, 6: 26, 7: 22}
    # For 5-leg mid-odds structure, keep 3 options; for 6/7 trim to 2
    by5 = by_match
    by67 = [(c, opts[:2]) for c, opts in by_match]

    alternatives: dict[int, dict] = {}
    for n, bm, cap in ((5, by5, caps[5]), (6, by67, caps[6]), (7, by67, caps[7])):
        rec = search_n(bm, n, cap)
        if rec:
            alternatives[n] = rec

    chosen_rec, why = choose_final(alternatives)
    chosen = []
    if chosen_rec:
        # recover full leg dicts from alternatives
        chosen = []
        # We stored compact legs; map back
        key = {(lg["code"], lg["market"], lg["sel"]) for lg in chosen_rec["legs"]}
        full_index = {(r["code"], r["market"], r["sel"]): r for r in all_recs}
        for lg in chosen_rec["legs"]:
            chosen.append(full_index[(lg["code"], lg["market"], lg["sel"])])
        chosen = sorted(chosen, key=lambda r: r["ko"])
        why = why or chosen_rec.get("label", "")

    sm = summary(chosen) if chosen else {}
    used_codes = {x["code"] for x in chosen}
    # Reserves: highest P not used, odds still in range, can swap and keep payout if possible
    leftovers = []
    for code, opts in sorted(by_match, key=lambda kv: -kv[1][0]["p"]):
        if code in used_codes:
            continue
        leftovers.append(opts[0])
        if len(leftovers) >= 8:
            break
    reserves: list[dict] = leftovers[:2]

    lg = Counter(x["league"] for x in chosen)
    clustered = {k: v for k, v in lg.items() if v >= 2}
    aksam_avail = any(code in AKSAM5 for code, _ in by_match)

    out = {
        "kupon": f"{len(chosen) if chosen else 0} maç — 300 TL → ≥2000 TL (hazır, oynanmadı)",
        "date": "2026-11-21",
        "stake_tl": STAKE_TL,
        "min_payout_tl": MIN_PAYOUT,
        "price_timestamp_nesine": price_ts,
        "built_at": now.isoformat(timespec="seconds"),
        "cutoff_kickoff_tsi": cutoff.isoformat(timespec="seconds"),
        "status": "hazır, oynanmadı",
        "placed": False,
        "min_p_used": min_p_used,
        "method": (
            "Taze Nesine bülteni (scripts/nesine_global.py). "
            "P_blend = 0.70·kalibre model + 0.30·keskin adil P. "
            "Bacak: oran 1.25–2.10, P_blend ≥ 0.55 (gerekirse 0.53), bültende açık, "
            "keskin referans (Pinnacle/Smarkets/OddsMath BetInAsia), maç başı birden fazla aday seçim "
            "(yüksek P / orta oran / yüksek oran), KO≥şimdi+25dk. "
            "Oynanmış kupon maçları, kırmızı bayrak, ağır rotasyon, çok eksik, yedek/kadın, "
            "|steam|≥8p veya seçim aleyhine ≥5p çıkarıldı. "
            "Akşam 5'li maçları serbest (oynanmadı). "
            "5, 6 ve 7 bacak arandı; ortak P maksimize, hedef oran 6.70–7.20; "
            "7 bacak yalnız ortak P'yi belirgin yükseltirse. Bahis oynanmadı."
        ),
        "selection_reason": why,
        "rules": {
            "min_p": MIN_P,
            "relax_p": RELAX_P,
            "min_odds": MIN_ODDS,
            "max_odds": MAX_ODDS,
            "one_per_match": True,
            "lead_minutes": LEAD_MIN,
            "target_odds": [TARGET_ODDS_LO, TARGET_ODDS_HI],
            "odds_hard_max": ODDS_HARD_MAX,
            "stake_tl": STAKE_TL,
            "min_payout_tl": MIN_PAYOUT,
            "used_excluded": sorted(USED),
            "red_flag_matches": sorted(RED_MATCHES),
            "soft_skip": sorted(SOFT_SKIP),
        },
        "families_in_bulletin": sorted(families_seen),
        "families_eligible": sorted(families_eligible),
        "pool_matches": len(by_match),
        "pool_selections": len(all_recs),
        "aksam5_available": aksam_avail,
        "skipped": skipped,
        "alternatives": {str(k): {kk: vv for kk, vv in rec.items() if kk != "n_seen"} for k, rec in alternatives.items()},
        "legs": chosen,
        "summary": sm,
        "league_clustering": clustered,
        "backups": reserves,
        "pool_top": [
            compact_leg(opts[0])
            for code, opts in sorted(by_match, key=lambda kv: (-kv[1][0]["p"], -kv[1][0]["odds"]))[:25]
        ],
    }
    (D / "kupon_2000.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    write_md(D / "kupon_2000.md", out)

    print(json.dumps({
        "ok": bool(chosen),
        "built_at": now.isoformat(timespec="seconds"),
        "price_ts": price_ts,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "min_p_used": min_p_used,
        "pool_matches": len(by_match),
        "pool_selections": len(all_recs),
        "skipped": skipped,
        "selection_reason": why,
        "summary": sm,
        "alternatives": {
            str(n): {
                "odds": rec["total_odds"],
                "p": rec["p_win"],
                "payout": rec["payout_tl"],
                "in_band": rec["in_band"],
                "earliest": rec["earliest"],
                "legs": [f"{lg['kickoff_tsi']} {lg['match']} {lg['sel']} @{lg['odds']} P={lg['p_blend']:.1%}" for lg in rec["legs"]],
            }
            for n, rec in alternatives.items()
        },
        "legs": [
            f"{x['kickoff_tsi']} {x['match']} {x['market']} {x['sel']} @{x['odds']} "
            f"Pblend={x['p']:.1%} Psharp={x['p_sharp']:.1%}"
            for x in chosen
        ],
        "reserves": [
            f"{x['kickoff_tsi']} {x['match']} {x['market']} {x['sel']} @{x['odds']} Pblend={x['p']:.1%}"
            for x in reserves
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
