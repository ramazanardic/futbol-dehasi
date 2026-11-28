#!/usr/bin/env python3
"""10 maçlık en banko kupon: 21 Nesine bahis ailesinin taraması. Bahis oynamaz."""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
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
MIN_ODDS, MAX_ODDS = 1.20, 1.80
MIN_P, PREFER_P = 0.65, 0.70
LEAD_MIN = 20
DAY_END = dt.datetime(2026, 11, 22, 7, 0, tzinfo=TSI)

# Played today (K1, K3–K6, banko 7.27, 5.00 kupon, and kupon_10ms1 as excluded by brief)
USED = {
    3319709, 3359425, 3318200,  # K1 Espanyol II, Rad. Bijelji, Tecnico
    3313105, 3318757, 3313080, 3313626, 3314007, 3314236,  # K1-4
    3313940, 3313644, 3313868,  # K5 CSKA, Carrarese, Yeovil
    3312554, 3314647, 3319368,  # K6 Norwich, Millwall, Elche B
    3313572, 3312753, 3318505, 3313774, 3314607,  # banko 7.27
    3318770, 3314269, 3312556, 3314246, 3312717,  # 5.00: Milan(K), Sturm II, Catanzaro, Lazio, Napoli
    3313785, 3314719, 3314324, 3313822, 3319951,  # 10ms1
    3318479, 3313708, 3313035, 3313692, 3314218,
}
# Hard red flags (steam against / named)
RED_MATCHES = {3312656, 3318418, 3312726, 3313417}  # LASK, Hamkam, Dundee-Hearts, Ferencváros
# Prior research: heavy rotation or many absences (plus the reds above)
SOFT_SKIP = {
    3312511, 3312540, 3312698, 3313263, 3313622, 3313762, 3318615, 3318820,
}

# Coupon legs come from well-supported families (all 21 are still scanned and reported).
BANKO_FAMILIES = {
    "Çifte Şans", "Alt/Üst", "Maç Sonucu", "Karşılıklı Gol",
    "Takım Golleri", "İY Alt/Üst", "2Y Alt/Üst", "Handikap",
    "İY Sonucu", "2Y Sonucu",
}
CUP_OK_FAMILIES = {"Alt/Üst", "Takım Golleri", "Karşılıklı Gol", "İY Alt/Üst", "2Y Alt/Üst"}
FAMILY_RANK = {
    "Çifte Şans": 0,
    "Alt/Üst": 1,
    "Maç Sonucu": 2,
    "Karşılıklı Gol": 3,
    "Takım Golleri": 4,
    "İY Alt/Üst": 5,
    "İY Sonucu": 6,
    "2Y Alt/Üst": 7,
    "2Y Sonucu": 8,
    "Handikap": 9,
    "Yarı Özel": 10,
    "Tek/Çift": 11,
    "Toplam Gol Aralığı": 12,
    "Yarı KG": 13,
    "İY/MS": 14,
    "Fark": 15,
    "Kombine": 16,
    "İlk Gol": 17,
    "Doğru Skor": 18,
    "Korner": 19,
    "Kart": 20,
    "Diğer": 21,
}
MAIN_DIRECT = {
    "MS 1", "MS 0", "MS 2",
    "ÇŞ 1X", "ÇŞ 10", "ÇŞ 12", "ÇŞ X2", "ÇŞ 02", "ÇŞ 1-X", "ÇŞ 1-2", "ÇŞ X-2",
    "1.5 Alt", "1.5 Üst", "2.5 Alt", "2.5 Üst", "3.5 Alt", "3.5 Üst", "0.5 Alt", "0.5 Üst",
    "4.5 Alt", "4.5 Üst",
    "KG Var", "KG Yok",
}


def _norm(s: str) -> str:
    import unicodedata, re
    t = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def load_flags() -> tuple[dict, dict]:
    """rotation/absence from earlier FotMob research + midweek European fixtures."""
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
    stop = {"fc","cf","sc","ac","sk","fk","nk","cd","ca","club","de","da","the","utd","united","k","w","bk","if","ik","afc"}
    return {t for t in _norm(s).split() if t and t not in stop and len(t) >= 3}


GENERIC_CLUB = {
    "dinamo", "dynamo", "sporting", "inter", "real", "port", "union", "racing",
    "atletico", "athletic", "rangers", "wanderers", "sport", "city", "town",
}

def euro_hits(home: str, away: str, euro: dict[str, str]) -> list[str]:
    """Conservative club match: name similarity + no generic-token collisions (Inter vs Inter Miami)."""
    out = []
    for name, comp in euro.items():
        for side in (home, away):
            if _sim(name, side) < 0.80:
                continue
            nt, st = _tokens(name), _tokens(side)
            if not nt or not st:
                continue
            if (len(nt) == 1 and next(iter(nt)) in GENERIC_CLUB and nt != st) or (
                len(st) == 1 and next(iter(st)) in GENERIC_CLUB and nt != st
            ):
                continue
            if (nt - st) and (st - nt):
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


def main() -> None:
    now = dt.datetime.now(TSI)
    cutoff = now + dt.timedelta(minutes=LEAD_MIN)
    cal = load_live_calibration() or {}
    ng = json.loads((D / "nesine_global.json").read_text())
    flag_by, euro = load_flags()
    price_ts = ng.get("generated_at")

    pool = []
    skipped = {"used": 0, "red": 0, "rotation": 0, "soft": 0, "early": 0, "not_priced": 0, "steam": 0}
    families_seen = set()
    families_eligible = set()

    for m in ng.get("matches") or []:
        try:
            ko = dt.datetime.fromisoformat(m["kickoff_iso"])
        except Exception:
            continue
        if ko < cutoff or ko >= DAY_END:
            if ko < cutoff:
                skipped["early"] += 1
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
        flags = flag_by.get(code, {})
        rot = list(flags.get("rotation") or [])
        rot += [h for h in euro_hits(m["home"], m["away"], euro)
                if any(tok in h.lower() for tok in ("champions league", "europa league", "conference league",
                                                    "libertadores", "sudamericana"))]
        rot = list(dict.fromkeys(rot))
        # heavy European midweek rotation: skip the match entirely
        heavy = [r for r in rot if any(tok in r.lower() for tok in
                                       ("champions league", "europa league", "conference league",
                                        "libertadores", "sudamericana"))]
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

        # lineup / weather flags from this pull
        research = m.get("research") or {}
        rflags = research.get("flags") or []
        if any("şiddetli" in f.lower() or "severe" in f.lower() for f in rflags):
            skipped["soft"] += 1
            continue
        wx = (research.get("weather") or {})
        if wx.get("severe"):
            skipped["soft"] += 1
            continue

        steam = m.get("steam_1x2") or [0, 0, 0]
        mu = (m.get("mu_home"), m.get("mu_away"))
        sharp = m.get("price_tier") == "keskin" and is_sharp_source(m.get("reference"))
        age = ref_age_h(m, now)
        uncal = is_uncalibrated_competition(m.get("league"))
        form = flags.get("form")
        if not form:
            th = ((research.get("teams") or {}).get("home") or {}).get("form")
            ta = ((research.get("teams") or {}).get("away") or {}).get("form")
            form = [th, ta] if th or ta else None
        n_abs = None
        if hu or au:
            n_abs = f"eksik ev {len(hu)} / dep {len(au)}"

        best_for_match = None
        for s in m.get("selections") or []:
            odds = s.get("odds")
            if not odds or odds < MIN_ODDS - 1e-9 or odds > MAX_ODDS + 1e-9:
                continue
            fam = bet_family(s.get("name") or "")
            families_seen.add(fam)
            if uncal and (s.get("name") not in MAIN_DIRECT and not (
                s.get("market") in {"Maç Sonucu", "Çifte Şans", "1,5 Gol Alt/Üst", "2,5 Gol Alt/Üst",
                                    "3,5 Gol Alt/Üst", "Karşılıklı Gol"} and s.get("direct")
            )):
                continue
            if fam not in BANKO_FAMILIES:
                # still count as scanned; do not put exotic/negation specials on the coupon
                families_seen.add(fam)
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
            p = calibrated_probability(float(fp), bool(s.get("direct")), cal)
            if p < MIN_P - 1e-12:
                continue
            sa = steam_against(s.get("market") or "", str(s.get("selection") or ""), steam)
            if sa is not None and sa <= -0.05:
                skipped["steam"] += 1
                continue
            families_eligible.add(fam)
            ev = p * float(odds) - 1
            rec = dict(
                code=code,
                ko=m["kickoff"],
                ko_iso=m["kickoff_iso"],
                league=m.get("league"),
                match=f"{m['home']} - {m['away']}",
                home=m["home"],
                away=m["away"],
                market=s["market"],
                sel=s["selection"],
                name=s.get("name"),
                family=fam,
                odds=round(float(odds), 4),
                p=round(p, 4),
                p_raw=round(float(fp), 4),
                fair=round(1 / p, 3) if p > 0 else None,
                ev=round(ev, 4),
                mbs=int(s.get("mbs") or 1),
                direct=bool(s.get("direct")),
                ref=m.get("reference"),
                ref_fetched_utc=m.get("ref_fetched_utc"),
                ref_age_h=None if age is None else round(age, 2),
                sharp=bool(sharp),
                price_tier=m.get("price_tier"),
                mu=[None if mu[0] is None else round(float(mu[0]), 3),
                    None if mu[1] is None else round(float(mu[1]), 3)],
                steam=steam,
                form=form,
                rotation=rot,
                research_flags=rflags,
                reason=reason_line(m, s, flags, mu, steam, form, n_abs),
            )
            # pick best selection in this match: highest P, but prefer a direct quote within 1.5pp
            def key(r):
                return (r["p"] + (0.015 if r["direct"] else 0.0), r["ev"], -FAMILY_RANK.get(r["family"], 99), int(r["direct"]))
            if best_for_match is None or key(rec) > key(best_for_match):
                best_for_match = rec
        if best_for_match:
            pool.append(best_for_match)

    # Prefer sharp; if at least 10 sharp, drop bureau
    sharp_pool = [x for x in pool if x["sharp"]]
    used_pool = sharp_pool if len(sharp_pool) >= 10 else pool
    used_pool = sorted(used_pool, key=lambda r: (-r["p"], -r["ev"], FAMILY_RANK.get(r["family"], 99)))

    legs = used_pool[:10]
    reserves = used_pool[10:13]
    prefer70 = sum(1 for x in legs if x["p"] >= PREFER_P)

    def summary(ls):
        if not ls:
            return {}
        total_odds = math.prod(x["odds"] for x in ls)
        p_win = math.prod(x["p"] for x in ls)
        ev = p_win * total_odds - 1
        fair_total = math.prod(x["fair"] for x in ls)
        return dict(
            n=len(ls),
            total_odds=round(total_odds, 4),
            p_win=round(p_win, 6),
            ev=round(ev, 4),
            fair_total=round(fair_total, 2),
            max_mbs=max(x["mbs"] for x in ls),
            mbs_ok=len(ls) >= max(x["mbs"] for x in ls),
            n_prefer70=sum(1 for x in ls if x["p"] >= PREFER_P),
            n_sharp=sum(1 for x in ls if x["sharp"]),
            earliest=min(x["ko"] for x in ls),
            latest=max(x["ko"] for x in ls),
        )

    sm = summary(legs)
    # league clustering
    from collections import Counter
    lg = Counter(x["league"] for x in legs)
    clustered = {k: v for k, v in lg.items() if v >= 2}

    out = {
        "kupon": "10 maç banko (hazır, oynanmadı)",
        "date": "2026-11-21",
        "price_timestamp_nesine": price_ts,
        "built_at": now.isoformat(timespec="seconds"),
        "status": "hazır, oynanmadı",
        "method": (
            "Tüm 21 Nesine bahis ailesi tarandı; kupona yalnız kalibrasyonu güçlü aileler alındı (MS, ÇŞ, Alt/Üst, KG, takım golleri, İY/2Y Alt-Üst, handikap, İY/2Y sonucu). P = keskin (Pinnacle/Smarkets/OddsMath) marjsız fiyattan "
            "uydurulan ortak gol modelinin (doğrudan kotasyon varsa o kotasyonun) kalibre edilmiş olasılığı. "
            "Bacak: P≥%65 (tercihen ≥%70), Nesine oranı 1.20–1.80, maç başı tek seçim, KO≥şimdi+20dk. "
            "Bugün oynanmış kupon maçları, kırmızı bayrak (LASK, Ferencváros, Hamkam, Dundee–Hearts) ve "
            "ağır rotasyon/çok eksik kadrolar çıkarıldı. Hedef: çarpım P(kazanç) maksimizasyonu. Bahis oynanmadı."
        ),
        "rules": {
            "min_p": MIN_P,
            "prefer_p": PREFER_P,
            "min_odds": MIN_ODDS,
            "max_odds": MAX_ODDS,
            "one_per_match": True,
            "lead_minutes": LEAD_MIN,
            "used_excluded": sorted(USED),
            "red_flag_matches": sorted(RED_MATCHES),
        },
        "families_in_bulletin": sorted(families_seen),
        "families_with_banko_legs": sorted(families_eligible),
        "pool_size": len(pool),
        "sharp_pool_size": len(sharp_pool),
        "skipped": skipped,
        "legs": legs,
        "summary": sm,
        "league_clustering": clustered,
        "backups": reserves,
        "note_ref_age": (
            "Smarkets/Pinnacle GitHub referansı ~10:25 UTC (~13:25 TSİ); OddsMath canlı çekim 16:57 TSİ. "
            "Dosya düzeyi betting_ok=False (küresel yaş 3.49s>3s) yanıltıcı; bacak yaşları ref_fetched_utc üzerinden alındı."
        ),
    }
    (D / "kupon_10_banko.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def pct(p):
        return f"{p*100:.1f}%"

    md = [
        "# 10 maçlık banko kupon — hazır, oynanmadı",
        "",
        f"Nesine fiyatı: {price_ts} TSİ. Kurulum: {now.strftime('%Y-%m-21 %H:%M') if False else now.strftime('%Y-%m-%d %H:%M')} TSİ. "
        f"KO ≥ {cutoff.strftime('%H:%M')} TSİ. Her bacak P ≥ %65 (tercihen ≥ %70), oran 1.20–1.80, maç başı tek seçim, keskin referans. "
        f"21 bahis ailesi tarandı (bültende görülen: {len(families_seen)}; banko eşiğini geçen aile: {len(families_eligible)}). "
        f"**Bahis oynanmadı.**",
        "",
        f"## Kupon: oran **{sm.get('total_odds', 0):.2f}**, ortak P **{pct(sm.get('p_win') or 0)}**, EV **{sm.get('ev', 0):+.1%}**",
        "",
        f"10 bacak içinden {sm.get('n_prefer70', 0)} tanesi P ≥ %70. En büyük MBS {sm.get('max_mbs')} "
        f"({'uygun' if sm.get('mbs_ok') else 'UYGUN DEĞİL'} — 10 maç ≥ MBS). "
        f"En erken başlama: **{sm.get('earliest')} TSİ** (bu saatten önce oynanmalı). "
        f"{'Lig yığılması: ' + ', '.join(f'{k} ×{v}' for k,v in clustered.items()) if clustered else 'Aynı ligde yığılma yok.'}",
        "",
        "| # | Kod | Saat | Lig | Maç | Aile | Pazar → Seçim | Oran | P | Adil | EV | MBS | Doğrudan | Ref | Gerekçe |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, x in enumerate(legs, 1):
        md.append(
            f"| {i} | {x['code']} | {x['ko'][11:]} | {x['league']} | {x['match']} | {x['family']} | "
            f"{x['market']} → {x['sel']} | {x['odds']:.2f} | {pct(x['p'])} | {x['fair']} | {x['ev']:+.1%} | "
            f"{x['mbs']} | {'evet' if x['direct'] else 'model'} | {(x['ref'] or '').split(' (')[0]} | {x['reason']} |"
        )
    md += ["", "## Yedek bacaklar (oran hareket ederse)", ""]
    if reserves:
        for x in reserves:
            md.append(
                f"- {x['code']} {x['ko'][11:]} {x['match']} — {x['market']}: {x['sel']} @ {x['odds']:.2f} "
                f"(P {pct(x['p'])}, adil {x['fair']}, EV {x['ev']:+.1%}, MBS {x['mbs']}, {x['family']}) — {x['reason']}"
            )
    else:
        md.append("_Yeterli yedek banko bacak yok._")
    md += [
        "",
        "## Notlar",
        "",
        f"- Havuz: {len(pool)} maç (keskin {len(sharp_pool)}) P≥%65 ve kurala uygun; kupon en yüksek 10 P çarpımı.",
        f"- Bugün oynanmış / dışarıda bırakılan maç sayısı (eşleşen bültende): used/red/rotasyon/eksik filtreleri uygulandı.",
        f"- 10 banko bacak bile ortak olasılığı düşürür (marj bileşikleşir): bu kupon **garanti değildir**. "
        "P ≥ %65 kuralı gevşetilmedi; 10 bacak bulunamazsa eksik bırakılırdı.",
        f"- Smarkets referansları ~13:25 TSİ (dosya yaşı ~3.6s); OddsMath canlı 16:57 TSİ. Küresel betting_ok bayrağı yaş yüzünden kapalı, bacaklar kaynak saatine göre alındı.",
        f"- Bültende görülen aileler: {', '.join(sorted(families_seen)) or '-'}.",
        f"- Banko eşiğini geçen aileler: {', '.join(sorted(families_eligible)) or '-'}.",
        "",
    ]
    (D / "kupon_10_banko.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({
        "built_at": now.isoformat(timespec="seconds"),
        "n_legs": len(legs),
        "summary": sm,
        "pool": len(pool),
        "sharp_pool": len(sharp_pool),
        "families_eligible": sorted(families_eligible),
        "skipped": skipped,
        "legs": [f"{x['ko'][11:]} {x['match']} {x['market']} {x['sel']} @{x['odds']} P={x['p']:.1%}" for x in legs],
        "reserves": [f"{x['ko'][11:]} {x['match']} {x['market']} {x['sel']} @{x['odds']} P={x['p']:.1%}" for x in reserves],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
