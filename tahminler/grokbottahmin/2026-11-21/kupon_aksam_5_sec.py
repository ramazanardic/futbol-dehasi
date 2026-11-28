#!/usr/bin/env python3
"""Akşam 5'li (gerekirse 6) banko kupon. Bahis oynamaz."""
from __future__ import annotations

import datetime as dt
import itertools
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration
from quantfoot.markets.families import bet_family
from quantfoot.strategy.banko_guard import BankoLeg, check_coupon
from quantfoot.strategy.coupon_builder import is_uncalibrated_competition, is_cup_competition
from quantfoot.data.oddsmath import is_women_match, is_youth_or_reserve_match
from nesine_global import is_sharp_source, _sim  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
TSI = dt.timezone(dt.timedelta(hours=3))
MIN_ODDS, SELECT_MIN_ODDS, PREFER_ODDS, MAX_ODDS = 1.20, 1.22, 1.25, 1.80
MIN_P, PREFER_P = 0.65, 0.70
LEAD_MIN = 25
DAY_END = dt.datetime(2026, 11, 22, 7, 0, tzinfo=TSI)
TARGET_ODDS_LO, TARGET_ODDS_HI = 3.0, 4.5
N_LEGS = 5

# Bugün oynanmış bütün kupon maçları (K1, K3–K6, banko 7.27, 5.00'lik, 10'lu MS1, 10'lu banko).
# 10'lu banko oynanan hali: Tottenham/Mineiro yerine Genk + West Ham.
USED = {
    # K1
    3319709, 3359425, 3318200,
    # K3
    3314007, 3314236, 3313105,  # Galatasaray, Southampton (3314236), Charleroi
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
    # 10'lu banko (150 TL) — oynanan hali
    3314600, 3314363, 3318436, 3391094, 3312528,
    3314573, 3313958, 3314396, 3313833, 3314223,
    # Canlı 3'lü (zaten bitmiş/başlamış; güvenlik)
    3307474, 3314339, 3405042,  # Kokand, Khor Fakkan, Reading
}

RED_MATCHES = {3312656, 3318418, 3312726, 3313417}  # LASK, Hamkam, Dundee-Hearts, Ferencváros
# Önceki araştırmada ağır Avrupa rotasyonu / çok eksik
SOFT_SKIP = {
    3312511,  # Nice–PSG, CL rotasyon + çok eksik
    3312540,  # Sheffield Utd–Watford, çok eksik
    3312698,  # Lens–Toulouse, CL rotasyon
    3313263,  # Feyenoord–Excelsior, CL rotasyon
    3313622,  # Falkirk–St Johnstone, çok eksik
    3313762,  # Mechelen–Club Brugge, CL rotasyon
    3318615,  # Real Madrid–Celta, CL/EL rotasyon
    3318820,  # Sevilla–Betis, CL rotasyon
}

BANKO_FAMILIES = {
    "Çifte Şans", "Alt/Üst", "Maç Sonucu", "Karşılıklı Gol",
    "Takım Golleri", "İY Alt/Üst", "2Y Alt/Üst", "Handikap",
    "İY Sonucu", "2Y Sonucu",
}
CUP_OK_FAMILIES = {"Alt/Üst", "Takım Golleri", "Karşılıklı Gol", "İY Alt/Üst", "2Y Alt/Üst"}
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


def _norm(s: str) -> str:
    import unicodedata
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
    stop = {"fc", "cf", "sc", "ac", "sk", "fk", "nk", "cd", "ca", "club", "de", "da", "the", "utd", "united", "k", "w", "bk", "if", "ik", "afc", "as", "ssc", "us"}
    return {t for t in _norm(s).split() if t and t not in stop and len(t) >= 3}


GENERIC_CLUB = {
    "dinamo", "dynamo", "sporting", "inter", "real", "port", "union", "racing",
    "atletico", "athletic", "rangers", "wanderers", "sport", "city", "town",
}


def euro_hits(home: str, away: str, euro: dict[str, str]) -> list[str]:
    """Match clubs conservatively. Token equality catches 'AS Roma' vs 'Roma'
    (string sim can be <0.80); do not use token-subset (Eindhoven vs PSV Eindhoven)."""
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
        idx = {"1-X": (0, 1), "1X": (0, 1), "10": (0, 1), "1-2": (0, 2), "12": (0, 2),
               "X-2": (1, 2), "X2": (1, 2), "02": (1, 2)}.get(key)
        if not idx:
            return None
        return float(steam[idx[0]] + steam[idx[1]])
    return None


def cs_prob(fair_1x2, sel: str) -> float | None:
    if not fair_1x2 or len(fair_1x2) < 3:
        return None
    key = str(sel).replace(" ", "").upper()
    f0, f1, f2 = map(float, fair_1x2)
    return {"1-X": f0 + f1, "1X": f0 + f1, "10": f0 + f1,
            "1-2": f0 + f2, "12": f0 + f2,
            "X-2": f1 + f2, "X2": f1 + f2, "02": f1 + f2}.get(key)


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
        bits.append(f"form {'/'.join(form)}")
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


def to_banko_legs(rows: list[dict]) -> list[BankoLeg]:
    return [
        BankoLeg(
            match_id=r["code"],
            label=f"{r['match']} {r['market']} {r['sel']}",
            odds=float(r["odds"]),
            p=float(r["p"]),
            offered=True,
            sharp_ref=bool(r["sharp"]),
            live=False,
            red_flags=tuple(r.get("red_flags") or ()),
        )
        for r in rows
    ]


def summary(ls: list[dict]) -> dict:
    if not ls:
        return {}
    total_odds = math.prod(x["odds"] for x in ls)
    p_win = math.prod(x["p"] for x in ls)
    ev = p_win * total_odds - 1
    fair_total = math.prod((x["fair"] or 1) for x in ls)
    return dict(
        n=len(ls),
        total_odds=round(total_odds, 4),
        p_win=round(p_win, 6),
        ev=round(ev, 4),
        fair_total=round(fair_total, 2),
        max_mbs=max(x["mbs"] for x in ls),
        mbs_ok=len(ls) >= max(x["mbs"] for x in ls),
        n_prefer70=sum(1 for x in ls if x["p"] >= PREFER_P),
        n_prefer_odds=sum(1 for x in ls if x["odds"] + 1e-12 >= PREFER_ODDS),
        n_sharp=sum(1 for x in ls if x["sharp"]),
        earliest=min(x["ko"] for x in ls),
        latest=max(x["ko"] for x in ls),
        guard_ok=True,
    )


def odds_gap(total: float) -> float:
    if TARGET_ODDS_LO <= total <= TARGET_ODDS_HI:
        return 0.0
    if total < TARGET_ODDS_LO:
        return TARGET_ODDS_LO - total
    return total - TARGET_ODDS_HI


def pick_combo(pool: list[dict], n: int) -> tuple[list[dict], str]:
    """Maximize joint P; prefer total odds in ~3–4.5; must pass banko_guard."""
    if len(pool) < n:
        return [], f"havuzda {len(pool)} maç var, {n} bacak yetmez"
    # Search at most the top 36 by P (C(36,5)=376992, C(36,6)=1.9M — 6'lıyı ayrıca daraltırız)
    cap = 28 if n >= 6 else 36
    ranked = sorted(pool, key=lambda r: (-r["p"], -r["ev"], FAMILY_RANK.get(r["family"], 99), -r["odds"]))
    search = ranked[: max(n, min(cap, len(ranked)))]

    best_in: tuple | None = None
    best_any: tuple | None = None
    n_ok = 0
    for combo in itertools.combinations(search, n):
        legs = list(combo)
        guard = check_coupon(to_banko_legs(legs), open_exposure=None, at_selection=True)
        if not guard.ok:
            continue
        n_ok += 1
        total = guard.total_odds
        p_win = guard.p_win
        prefer_odds_n = sum(1 for x in legs if x["odds"] + 1e-12 >= PREFER_ODDS)
        prefer_p_n = sum(1 for x in legs if x["p"] >= PREFER_P)
        # sort key: higher P, more preferred-odds legs, more P>=70, then closer to odds band, then higher EV
        ev = p_win * total - 1
        key = (p_win, prefer_odds_n, prefer_p_n, -odds_gap(total), ev)
        if best_any is None or key > best_any[0]:
            best_any = (key, legs, guard)
        if odds_gap(total) == 0 and (best_in is None or key > best_in[0]):
            best_in = (key, legs, guard)

    if best_in is not None:
        # If the unconstrained max-P is materially better (>3 rel. pp of joint P) and only slightly out of band, we still prefer in-band
        # unless in-band P is much worse. In-band already chosen here.
        _, legs, guard = best_in
        why = f"banko_guard geçti ({n_ok} kombinasyon); toplam oran {guard.total_odds:.2f} hedef bantta; ortak P maksimize"
        return sorted(legs, key=lambda r: r["ko"]), why

    if best_any is None:
        return [], "banko_guard'ı geçen kombinasyon yok"

    _, legs, guard = best_any
    why = (
        f"banko_guard geçti ({n_ok} kombinasyon); hedef bantta (3.00–4.50) 5'li yok, "
        f"en yüksek ortak P seçildi (oran {guard.total_odds:.2f}, bant dışı {odds_gap(guard.total_odds):.2f})"
    )
    return sorted(legs, key=lambda r: r["ko"]), why


def build_pool(ng: dict, now: dt.datetime, cutoff: dt.datetime) -> tuple[list[dict], dict, set, set]:
    cal = load_live_calibration() or {}
    flag_by, euro = load_flags()
    pool: list[dict] = []
    skipped = {
        "used": 0, "red": 0, "rotation": 0, "soft": 0, "early": 0,
        "late": 0, "not_priced": 0, "steam": 0, "not_sharp": 0,
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
        # Aşırı 1X2 steam = oyun senaryosu istikrarsız (Palmeiras tipi)
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

        best_for_match = None
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
            if fam not in BANKO_FAMILIES:
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
            # Blended P: kalibre model (keskin fiyata uydurulmuş gol dağılımı) ile ham keskin adil P.
            # Pre-match model zaten keskin piyasaya fit (fund_weight=0); 70/30 büzme aşırı sapmayı keser.
            p_blend = 0.70 * float(p) + 0.30 * p_sharp
            if p_blend < MIN_P - 1e-12:
                continue
            sa = steam_against(s.get("market") or "", str(s.get("selection") or ""), steam)
            if sa is not None and sa <= -0.05:
                skipped["steam"] += 1
                continue
            families_eligible.add(fam)
            ev = p_blend * float(odds) - 1
            rec = dict(
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
                p_raw=round(p_sharp, 4),
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
            )

            def key(r):
                # Prefer higher blended P, then direct quote, then odds closer to/above 1.25, then EV
                pref = 0.01 if r["odds"] + 1e-12 >= PREFER_ODDS else 0.0
                return (r["p"] + (0.012 if r["direct"] else 0.0) + pref, r["ev"], -FAMILY_RANK.get(r["family"], 99))

            if best_for_match is None or key(rec) > key(best_for_match):
                best_for_match = rec
        if best_for_match:
            pool.append(best_for_match)
    return pool, skipped, families_seen, families_eligible


def tier_pool(pool: list[dict], min_p: float, min_odds: float) -> list[dict]:
    return [x for x in pool if x["p"] + 1e-12 >= min_p and x["odds"] + 1e-12 >= min_odds]


def main() -> None:
    now = dt.datetime.now(TSI)
    cutoff = now + dt.timedelta(minutes=LEAD_MIN)
    ng = json.loads((D / "nesine_global.json").read_text())
    price_ts = ng.get("generated_at")
    pool, skipped, families_seen, families_eligible = build_pool(ng, now, cutoff)
    pool = sorted(pool, key=lambda r: (-r["p"], -r["ev"], FAMILY_RANK.get(r["family"], 99)))

    tiers = [
        ("P≥0.70 ve oran≥1.25", PREFER_P, PREFER_ODDS),
        ("P≥0.70 ve oran≥1.22", PREFER_P, SELECT_MIN_ODDS),
        ("P≥0.65 ve oran≥1.25", MIN_P, PREFER_ODDS),
        ("P≥0.65 ve oran≥1.22", MIN_P, SELECT_MIN_ODDS),
        ("P≥0.65 ve oran≥1.20 (yalnız yedek/son çare)", MIN_P, MIN_ODDS),
    ]

    chosen: list[dict] = []
    why = ""
    tier_used = ""
    n_used = N_LEGS
    six_justification = None

    for label, mp, mo in tiers:
        cand = tier_pool(pool, mp, mo)
        legs, reason = pick_combo(cand, N_LEGS)
        if legs:
            chosen, why, tier_used, n_used = legs, reason, label, N_LEGS
            break

    # 6. bacak: yalnız 5'linin toplam oranı ~3'ün altındaysa ve 6. banko bacak bandı dolduruyorsa.
    if chosen:
        sm5 = summary(chosen)
        if sm5["total_odds"] < TARGET_ODDS_LO - 0.02:
            used_codes = {x["code"] for x in chosen}
            # 6. bacak için en sıkı uygun havuzu dene
            for label, mp, mo in tiers[:4]:
                extra_pool = [x for x in tier_pool(pool, mp, mo) if x["code"] not in used_codes]
                # 5'li + her aday 6. bacağı dene; bandı tutan ve guard geçen, max ortak P
                best6 = None
                for extra in extra_pool:
                    legs6 = chosen + [extra]
                    guard = check_coupon(to_banko_legs(legs6), at_selection=True)
                    if not guard.ok:
                        continue
                    if not (TARGET_ODDS_LO <= guard.total_odds <= TARGET_ODDS_HI):
                        continue
                    key = (guard.p_win, guard.total_odds)
                    if best6 is None or key > best6[0]:
                        best6 = (key, legs6, guard, label)
                if best6:
                    _, legs6, guard, label = best6
                    six_justification = (
                        f"5 bacak toplam oranı {sm5['total_odds']:.2f} (<3.00). "
                        f"6. banko bacak ({label}) toplamı {guard.total_odds:.2f} bandına taşıyor; "
                        f"ortak P {guard.p_win:.1%} (5'li {sm5['p_win']:.1%})."
                    )
                    chosen, why, tier_used, n_used = (
                        sorted(legs6, key=lambda r: r["ko"]),
                        six_justification,
                        label + " (6 bacak gerekçeli)",
                        6,
                    )
                    break

    quality_swaps: list[str] = []
    # Kalite takası: playoff/ince (türetilmiş takım-yarı) bacağı, P farkı ≤1.2p olan
    # klasik ve tercihen doğrudan bir lig bacağıyla değiştir (garanti kalitesi).
    CLASSIC_FAM = {"Alt/Üst", "Maç Sonucu", "Çifte Şans", "Karşılıklı Gol", "İY Alt/Üst"}

    def _thin_or_cup(r: dict) -> bool:
        lg = (r.get("league") or "").lower()
        return any(tok in lg for tok in ("playoff", "play-off", "kupa", "cup", "sudamericana", "libertadores"))

    if chosen:
        used_codes = {x["code"] for x in chosen}
        classic_alts = [
            x for x in tier_pool(pool, MIN_P, PREFER_ODDS)
            if x["code"] not in used_codes and (x["direct"] or x["family"] in CLASSIC_FAM)
        ]
        for i, leg in enumerate(list(chosen)):
            if not _thin_or_cup(leg):
                continue
            alts = [a for a in classic_alts if a["p"] + 1e-12 >= leg["p"] - 0.012]
            alts = sorted(alts, key=lambda a: (int(a["direct"]), a["p"], a["odds"]), reverse=True)
            for alt in alts:
                trial = chosen[:i] + [alt] + chosen[i+1:]
                guard = check_coupon(to_banko_legs(trial), at_selection=True)
                if not guard.ok:
                    continue
                old_p = math.prod(x["p"] for x in chosen)
                if guard.p_win < old_p - 0.004:
                    continue
                if odds_gap(guard.total_odds) > 0 and odds_gap(math.prod(x["odds"] for x in chosen)) == 0:
                    continue
                quality_swaps.append(
                    f"{leg['match']} {leg['market']} {leg['sel']} (P {leg['p']:.1%}, {leg['league']}) → "
                    f"{alt['match']} {alt['market']} {alt['sel']} (P {alt['p']:.1%}, {'doğrudan' if alt['direct'] else 'klasik'})"
                )
                chosen[i] = alt
                used_codes.discard(leg["code"])
                used_codes.add(alt["code"])
                classic_alts = [a for a in classic_alts if a["code"] != alt["code"]]
                break
        if quality_swaps:
            chosen = sorted(chosen, key=lambda r: r["ko"])
            why = (why + " Kalite takası: " + " | ".join(quality_swaps)).strip()

    if not chosen:
        # last resort already tried; keep empty
        pass

    sm = summary(chosen) if chosen else {}
    if chosen:
        guard = check_coupon(to_banko_legs(chosen), at_selection=True)
        sm["guard_ok"] = guard.ok
        sm["guard_errors"] = guard.errors
        sm["guard_warnings"] = guard.warnings
        if not guard.ok:
            raise SystemExit(f"Seçilen kupon banko_guard'dan geçmedi: {guard.errors}")

    used_codes = {x["code"] for x in chosen}
    # Yedekler: önce P≥0.70, yoksa aynı katmandan (P≥0.65, oran≥1.25) 2 maç
    reserves: list[dict] = []
    for src in (
        tier_pool(pool, PREFER_P, PREFER_ODDS),
        tier_pool(pool, PREFER_P, SELECT_MIN_ODDS),
        tier_pool(pool, MIN_P, PREFER_ODDS),
        pool,
    ):
        for x in src:
            if x["code"] not in used_codes and x["code"] not in {r["code"] for r in reserves}:
                reserves.append(x)
            if len(reserves) >= 2:
                break
        if len(reserves) >= 2:
            break

    lg = Counter(x["league"] for x in chosen)
    clustered = {k: v for k, v in lg.items() if v >= 2}

    out = {
        "kupon": f"Akşam {n_used} maç banko (hazır, oynanmadı)",
        "date": "2026-11-21",
        "stake_suggested_tl": 100,
        "price_timestamp_nesine": price_ts,
        "built_at": now.isoformat(timespec="seconds"),
        "cutoff_kickoff_tsi": cutoff.isoformat(timespec="seconds"),
        "status": "hazır, oynanmadı",
        "placed": False,
        "method": (
            "Taze Nesine bülteni (nesine_global.py). P_blend = 0.70·kalibre model + 0.30·keskin adil P "
            "(model zaten keskin 1X2/OU'ya uydurulmuş skor matrisinden). "
            "Bacak: P_blend≥0.65 (tercihen ≥0.70), Nesine oranı 1.20–1.80 (seçimde tampon ≥1.22, tercih ≥1.25), "
            "bültende birebir açık, keskin referans zorunlu, maç başı tek seçim, KO≥şimdi+25dk. "
            "Bugün oynanmış tüm kupon maçları, kırmızı bayrak, ağır Avrupa rotasyonu, çok eksik kadro, "
            "yedek/kadın ve |steam|≥8p veya seçim aleyhine ≥5p maçlar çıkarıldı. Hedef: ortak P maksimize, toplam oran ~3–4.5. "
            "6. bacak yalnız 5'li 3.00'ın altındaysa ve 6. banko bacak bandı dolduruyorsa eklenir. "
            "strategy/banko_guard.py uygulandı. Bahis oynanmadı."
        ),
        "tier_used": tier_used,
        "selection_reason": why,
        "six_justification": six_justification,
        "quality_swaps": quality_swaps if "quality_swaps" in dir() else [],
        "rules": {
            "min_p": MIN_P,
            "prefer_p": PREFER_P,
            "min_odds": MIN_ODDS,
            "select_min_odds": SELECT_MIN_ODDS,
            "prefer_odds": PREFER_ODDS,
            "max_odds": MAX_ODDS,
            "one_per_match": True,
            "lead_minutes": LEAD_MIN,
            "target_odds": [TARGET_ODDS_LO, TARGET_ODDS_HI],
            "used_excluded": sorted(USED),
            "red_flag_matches": sorted(RED_MATCHES),
            "soft_skip": sorted(SOFT_SKIP),
        },
        "families_in_bulletin": sorted(families_seen),
        "families_with_banko_legs": sorted(families_eligible),
        "pool_size": len(pool),
        "pool_prefer70_125": len(tier_pool(pool, PREFER_P, PREFER_ODDS)),
        "skipped": skipped,
        "legs": chosen,
        "summary": sm,
        "league_clustering": clustered,
        "backups": reserves,
    }
    (D / "kupon_aksam_5.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def pct(p):
        return f"{p*100:.1f}%"

    title_n = n_used if chosen else 5
    md = [
        f"# Akşam {title_n} maçlık banko kupon — hazır, oynanmadı",
        "",
        f"Nesine fiyatı: {price_ts} TSİ. Kurulum: {now.strftime('%Y-%m-%d %H:%M')} TSİ. "
        f"KO ≥ {cutoff.strftime('%H:%M')} TSİ (şimdi+{LEAD_MIN} dk). "
        f"Her bacak P_blend ≥ %65 (tercihen ≥ %70), oran 1.20–1.80 (tercih ≥ 1.25, tampon ≥ 1.22), "
        f"maç başı tek seçim, keskin referans, bültende açık seçim. "
        f"banko_guard uygulandı. **Bahis oynanmadı.**",
        "",
    ]
    if not chosen:
        md += [
            "Uygun 5 banko bacak bulunamadı. Havuz ve filtre özeti JSON dosyasında.",
            f"Havuz: {len(pool)} maç. Atlanan: {skipped}.",
            "",
        ]
        (D / "kupon_aksam_5.md").write_text("\n".join(md), encoding="utf-8")
        print(json.dumps({"ok": False, "pool": len(pool), "skipped": skipped}, ensure_ascii=False, indent=2))
        return

    md += [
        f"## Kupon: oran **{sm['total_odds']:.2f}**, ortak P **{pct(sm['p_win'])}**, EV **{sm['ev']:+.1%}**",
        "",
        f"{sm['n']} bacak; {sm['n_prefer70']} tanesi P ≥ %70; {sm['n_prefer_odds']} tanesi oran ≥ 1.25. "
        f"Seçim katmanı: {tier_used}. {why} "
        f"En büyük MBS {sm['max_mbs']} ({'uygun' if sm['mbs_ok'] else 'UYGUN DEĞİL'}). "
        f"En erken başlama: **{sm['earliest']} TSİ** (bu saatten önce oynanmalı). "
        f"{'Lig yığılması: ' + ', '.join(f'{k} ×{v}' for k,v in clustered.items()) + '.' if clustered else 'Aynı ligde yığılma yok.'}",
        "",
        "| # | Kod | Saat (TSİ) | Lig | Maç | Pazar → Seçim | Oran | P_blend | Keskin adil P | Adil oran | EV | MBS | Ref | Gerekçe |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, x in enumerate(chosen, 1):
        md.append(
            f"| {i} | {x['code']} | {x['kickoff_tsi']} | {x['league']} | {x['match']} | "
            f"{x['market']} → {x['sel']} | {x['odds']:.2f} | {pct(x['p'])} | {pct(x['p_sharp'])} | "
            f"{x['fair']} | {x['ev']:+.1%} | {x['mbs']} | {(x['ref'] or '').split(' (')[0]} | {x['reason']} |"
        )
    if six_justification:
        md += ["", f"**6. bacak gerekçesi:** {six_justification}", ""]
    md += ["", "## Yedek bacaklar (oran hareket ederse)", ""]
    if reserves:
        for x in reserves:
            md.append(
                f"- {x['code']} {x['kickoff_tsi']} {x['match']} — {x['market']}: {x['sel']} @ {x['odds']:.2f} "
                f"(P_blend {pct(x['p'])}, keskin adil {pct(x['p_sharp'])}, EV {x['ev']:+.1%}, MBS {x['mbs']}) — {x['reason']}"
            )
    else:
        md.append("_Uygun yedek banko bacak yok._")
    md += [
        "",
        "## Notlar",
        "",
        f"- Havuz: {len(pool)} keskin-referanslı banko aday maç; sıkı katman (P≥%70 ve oran≥1.25): {len(tier_pool(pool, PREFER_P, PREFER_ODDS))}.",
        f"- Bugün oynanmış kupon maçları tamamen çıkarıldı (çift yükleme yok). banko_guard: {sm.get('guard_ok')}; uyarılar: {sm.get('guard_warnings') or 'yok'}.",
        f"- Ortak P {pct(sm['p_win'])} — 5–6 banko bacak bile garanti değildir (Nesine payı bileşikleşir). EV {sm['ev']:+.1%}.",
        f"- Önerilen pay (oynanmadı): 100 TL civarı; bakiyenin tamamı (350 TL) tek kupona yatmamalı.",
        f"- Bültende görülen aileler: {', '.join(sorted(families_seen)) or '-'}.",
        f"- Banko eşiğini geçen aileler: {', '.join(sorted(families_eligible)) or '-'}.",
        f"- Atlanan: {skipped}.",
        "",
    ]
    (D / "kupon_aksam_5.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "built_at": now.isoformat(timespec="seconds"),
        "price_ts": price_ts,
        "cutoff": cutoff.isoformat(timespec="seconds"),
        "n_legs": len(chosen),
        "tier_used": tier_used,
        "selection_reason": why,
        "six_justification": six_justification,
        "quality_swaps": quality_swaps if "quality_swaps" in dir() else [],
        "summary": sm,
        "pool": len(pool),
        "pool_prefer70_125": len(tier_pool(pool, PREFER_P, PREFER_ODDS)),
        "skipped": skipped,
        "legs": [
            f"{x['kickoff_tsi']} {x['match']} {x['market']} {x['sel']} @{x['odds']} "
            f"Pblend={x['p']:.1%} Psharp={x['p_sharp']:.1%}"
            for x in chosen
        ],
        "reserves": [
            f"{x['kickoff_tsi']} {x['match']} {x['market']} {x['sel']} @{x['odds']} Pblend={x['p']:.1%}"
            for x in reserves
        ],
        "guard_warnings": sm.get("guard_warnings"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
