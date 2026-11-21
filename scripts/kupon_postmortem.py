"""Nesine kupon geçmişi post-mortem (yalnız okuma; sonuç kendi klasörüne yazılır).

    QUANTFOOT_AI=grokbottahmin python scripts/kupon_postmortem.py

Girdi (QUANTFOOT_AI klasörü): nesine_kupon_gecmisi.csv (bacak düzeyi), nesine_kupon_liste.csv (kupon düzeyi),
<gün>/nesine_global.json (o günün global adil fiyatları), postmortem_cache/espn_YYYYMMDD.json (lig adları).
Ortak veriler: data/global_odds/latest/{references.json,season_2627/*.csv} (global / kapanış oranları).
Çıktı: <klasör>/kupon_postmortem.json ve kupon_postmortem_bacaklar.csv.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from quantfoot.evaluation.coupon_postmortem import (
    binom_two_sided_p,
    canonical_leg,
    implied_prob,
    legs_bucket,
    odds_band,
    parse_tl,
)
from quantfoot.paths import ai_area

AY = {"Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6, "Temmuz": 7, "Ağustos": 8,
      "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12}
PARTIAL_REFUND = {"4605462726493704"}  # 'Kazandı' görünür ama 247 TL'ye 5,76 TL döndü: iptal bacaklı kısmi iade
COMPLETE_FROM = dt.datetime(2026, 11, 20)  # bacak düzeyinde kaybedenler bu tarihten itibaren eksiksiz
DEFAULT_OVERROUND = 0.10  # pazar marjı bilinmezse kaba varsayım (raporda belirtilir)


def parse_placed(s: str) -> dt.datetime:
    d, m, y, hm = s.split()
    h, mi = hm.split(":")
    return dt.datetime(int(y), AY[m], int(d), int(h), int(mi))


def load_detail(area: Path) -> list[dict]:
    rows = list(csv.DictReader(open(area / "nesine_kupon_gecmisi.csv", encoding="utf-8-sig")))
    for r in rows:
        r["leg_odds"] = float(r["leg_odds"]) if r["leg_odds"] else None
        r["placed_dt"] = parse_placed(r["placed"])
        c = canonical_leg(r["market"], r["selection"], r["leg_odds"])
        r["name"], r["family"], r["hard"] = c.name, c.family, c.hard
        if r["leg_odds"] is not None and r["leg_odds"] <= 1.001:
            r["leg_result"] = "void"  # 1.00 oranlı bacak (ör. Sheffield Utd U21): iptal/geçersiz sayılır
    return rows


def coupons_from_detail(rows: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["coupon_id"]].append(r)
    out = []
    for cid, legs in by.items():
        f = legs[0]
        status = f["status"]
        if cid in PARTIAL_REFUND:
            status = "Kısmi iade"
        res = Counter(("pending" if x["leg_result"].startswith("pending") else x["leg_result"]) for x in legs)
        out.append({"coupon_id": cid, "placed": f["placed_dt"], "stake": parse_tl(f["stake_TL"]),
                    "total_odds": parse_tl(f["total_odds"]), "payout": parse_tl(f["win_TL"]), "status": status,
                    "legs": int(f["legs_count"]), "lost_legs": res["lost"], "won_legs": res["won"],
                    "pending_legs": res["pending"], "source": "bacak"})
    return out


def coupons_from_list(area: Path, detail_ids_times: set) -> list[dict]:
    out = []
    for r in csv.DictReader(open(area / "nesine_kupon_liste.csv", encoding="utf-8-sig")):
        t = parse_placed(r["placed"])
        if t in detail_ids_times:
            continue  # aynı kupon bacak düzeyinde de var
        out.append({"coupon_id": None, "placed": t, "stake": parse_tl(r["stake_TL"]), "total_odds": parse_tl(r["total_odds"]),
                    "payout": parse_tl(r["win_TL"]), "status": r["status"], "legs": int(r["legs_count"]),
                    "copied_from": r.get("kupondas_source") or None, "source": "liste"})
    return out


def roi_table(coupons: list[dict], key) -> list[dict]:
    g = defaultdict(list)
    for c in coupons:
        if c["status"] in ("Devam",):
            continue
        g[key(c)].append(c)
    rows = []
    for k in sorted(g, key=str):
        cs = g[k]
        st = sum(c["stake"] for c in cs)
        pay = sum(c["payout"] for c in cs)
        rows.append({"grup": k, "kupon": len(cs), "kazanan": sum(c["status"] == "Kazandı" for c in cs),
                     "yatirilan_TL": round(st, 2), "donen_TL": round(pay, 2), "net_TL": round(pay - st, 2),
                     "roi": round(pay / st - 1, 4) if st else None})
    return rows


def total_odds_band(o: float) -> str:
    for hi, lbl in ((3, "<3"), (5, "3–5"), (10, "5–10"), (20, "10–20"), (50, "20–50")):
        if o < hi:
            return lbl
    return "≥50"


# ---------------------------------------------------------------- global / closing reference matching
def _tsi(iso: str) -> dt.datetime | None:
    """ISO zaman damgası -> TSİ (UTC+3) saf datetime (kupon saatleriyle karşılaştırmak için)."""
    try:
        t = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        return t
    return (t.astimezone(dt.timezone(dt.timedelta(hours=3)))).replace(tzinfo=None)


def _load_refs() -> list[dict]:
    from nesine_global import _sim  # noqa: F401  (import check)

    refs = []
    p = ROOT / "data" / "global_odds" / "latest" / "references.json"
    if p.exists():
        d = json.load(open(p, encoding="utf-8"))
        fetched = _tsi(d["generated_utc"])
        for r in d.get("references", []):
            ko = _tsi(r["kickoff_utc"])
            if "football-data" not in r["source"] and ko is not None and fetched is not None and ko <= fetched:
                continue  # borsa fiyatı maç başladıktan sonra çekilmiş: canlı/bitmiş fiyat, maç öncesi referans değil
            refs.append({"home": r["home"], "away": r["away"], "date": r["kickoff_utc"][:10], "league": r.get("league", ""),
                         "x12": r.get("x12"), "ou": r.get("ou"), "ko": _tsi(r["kickoff_utc"]), "kind": f"global ({r['source']}, {d['generated_utc'][:16]}Z)"})
    for f in sorted((ROOT / "data" / "global_odds" / "latest" / "season_2627").glob("*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            try:
                day = dt.datetime.strptime(r["Date"], "%d/%m/%Y").date().isoformat()
            except ValueError:
                continue
            if day < "2026-11-10":
                continue

            def trio(prefix: str):
                try:
                    v = [float(r[f"{prefix}H"]), float(r[f"{prefix}D"]), float(r[f"{prefix}A"])]
                    return v if all(x > 1 for x in v) else None
                except (KeyError, ValueError):
                    return None

            def pair(prefix: str):
                try:
                    v = [float(r[f"{prefix}>2.5"]), float(r[f"{prefix}<2.5"])]
                    return v if all(x > 1 for x in v) else None
                except (KeyError, ValueError):
                    return None

            for pre, lbl in (("BFEC", "Betfair borsa kapanış"), ("AvgC", "piyasa ort. kapanış"), ("B365C", "Bet365 kapanış")):
                x12 = trio(pre)
                if x12:
                    ou = pair(pre)
                    ko = None
                    if r.get("Time"):
                        ko = _tsi(f"{day}T{r['Time']}:00+00:00")  # football-data saatleri İngiltere saati (Kasım: UTC)
                    refs.append({"home": r["HomeTeam"], "away": r["AwayTeam"], "date": day, "league": r["Div"], "x12": x12, "ko": ko,
                                 "ou": [2.5, ou] if ou else None, "kind": f"{lbl} (football-data)",
                                 "result": (r.get("FTHG"), r.get("FTAG"))})
                    break
    return refs


def _espn_leagues(area: Path) -> list[dict]:
    out = []
    for f in sorted((area / "postmortem_cache").glob("espn_*.json")):
        for ev in json.load(open(f, encoding="utf-8")).get("events", []):
            comp = ev["competitions"][0]
            try:
                h = next(t for t in comp["competitors"] if t["homeAway"] == "home")["team"]["displayName"]
                a = next(t for t in comp["competitors"] if t["homeAway"] == "away")["team"]["displayName"]
            except StopIteration:
                continue
            out.append({"home": h, "away": a, "date": ev["date"][:10], "league": (ev.get("season") or {}).get("slug", ""),
                        "ko": _tsi(ev["date"].replace("Z", ":00+00:00") if ev["date"].count(":") == 1 else ev["date"].replace("Z", "+00:00"))})
    return out


def _nesine_global_days(area: Path) -> list[dict]:
    out = []
    for f in sorted(area.glob("2026-*/nesine_global.json")):
        d = json.load(open(f, encoding="utf-8"))
        for m in d.get("matches", []):
            if m.get("status") != "fiyatlandı":
                continue
            out.append({"home": m["home"], "away": m["away"], "date": m["kickoff_iso"][:10], "league": m["league"], "ko": _tsi(m["kickoff_iso"]),
                        "sel": {s["name"]: (s["fair_prob"], s["odds"], s.get("direct")) for s in m.get("selections", [])},
                        "margin": m.get("nesine_ms_margin"), "ref": m.get("reference"), "ref_t": m.get("ref_fetched_utc")})
    return out


def best_match(home: str, away: str, day: dt.date, cands: list[dict], days_after: int = 2, thr: float = 0.85):
    from nesine_global import _sim

    best, score = None, 0.0
    lo, hi = day.isoformat(), (day + dt.timedelta(days=days_after)).isoformat()
    for c in cands:
        if not (lo <= c["date"] <= hi):
            continue
        s = (_sim(home, c["home"]) + _sim(away, c["away"])) / 2
        if s > score:
            best, score = c, s
    return (best, score) if score >= thr else (None, score)


MAX_PLAUSIBLE_EV = 0.25  # nesine_global ile aynı: bunun üstü eşleşme/etiket hatası şüphesi


_JOINT_CACHE: dict = {}


def ref_probability(name: str, ref: dict) -> tuple[float | None, bool]:
    """Fair probability of an engine selection from a 1X2 (+O/U 2.5) reference, production pipeline."""
    from quantfoot.markets.devig import devig
    from quantfoot.markets.goal_markets import goal_probability
    from quantfoot.markets.omni_markets import compute_omni_markets
    from quantfoot.markets.tail_goals import (
        fit_tail_rates_from_markets,
        league_tail_regime,
    )

    p1x2 = devig(ref["x12"], method="power").probabilities
    direct = {"MS 1": p1x2[0], "MS 0": p1x2[1], "MS 2": p1x2[2], "ÇŞ 10": p1x2[0] + p1x2[1], "ÇŞ 02": p1x2[1] + p1x2[2],
              "ÇŞ 12": p1x2[0] + p1x2[2]}
    p_ov = None
    if ref.get("ou") and ref["ou"][1]:
        p_ov = float(devig(ref["ou"][1], method="power").probabilities[0])
        ln = float(ref["ou"][0])
        direct[f"{ln:.1f} Üst"], direct[f"{ln:.1f} Alt"] = p_ov, 1 - p_ov
    if name in direct:
        return float(direct[name]), True
    if p_ov is None and not name.startswith(("MS ", "ÇŞ ")):
        return None, False  # gol pazarı için toplam gol çapası yok
    key = (tuple(ref["x12"]), json.dumps(ref.get("ou")))
    if key not in _JOINT_CACHE:
        nu, alpha, kappa = league_tail_regime((ref.get("league") or "e0").lower())
        mu_h, mu_a, _ = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5 if p_ov is not None else None, p_over=p_ov,
                                                    seed_rates=(1.45, 1.15), alpha_nb=alpha, shared_kappa=kappa, com_nu=nu,
                                                    fund_weight=0.0)
        _JOINT_CACHE[key] = compute_omni_markets(mu_h, mu_a, league="e0").joint
    try:
        return float(goal_probability(name, _JOINT_CACHE[key])), False
    except KeyError:
        return None, False


def family_overround(area: Path) -> dict[str, float]:
    """Nesine pazar marjı (son analiz günündeki ortalama) → aile eşlemesi."""
    files = sorted(area.glob("2026-*/nesine_global.json"))
    if not files:
        return {}
    m = json.load(open(files[-1], encoding="utf-8")).get("nesine_margins") or {}

    def g(k):
        return float(m.get(k, {}).get("margin", DEFAULT_OVERROUND))

    return {"MS": g("Maç Sonucu"), "Toplam Gol 2.5": g("2,5 Gol Alt/Üst"), "Toplam Gol 3.5": g("3,5 Gol Alt/Üst"),
            "Toplam Gol 1.5": g("1,5 Gol Alt/Üst"), "KG": g("Karşılıklı Gol"), "İY Gol": g("1. Yarı 0,5 Gol Alt/Üst"),
            "İY/MS": g("İlk Yarı/Maç Sonucu"), "Kombine": g("2,5 Alt/Üst ve Karşılıklı Gol"),
            "Takım golü": g("Ev Sahibi 1,5 Gol Alt/Üst"), "Handikap": g("Handikaplı Maç Sonucu (X)")}


def overround_for(family: str, ovr: dict[str, float]) -> float:
    for k, v in ovr.items():
        if family.startswith(k) or (k == "MS" and family.startswith("MS")) or (k == "KG" and family.startswith("KG")):
            return v
    return DEFAULT_OVERROUND


def main() -> None:
    area = Path(ai_area())
    rows = load_detail(area)
    cd = coupons_from_detail(rows)
    cl = coupons_from_list(area, {c["placed"] for c in cd})
    allc = cd + cl
    complete = cl + [c for c in cd if c["placed"] >= COMPLETE_FROM]

    # ---- references per leg
    refs, espn, ng = _load_refs(), _espn_leagues(area), _nesine_global_days(area)
    ovr = family_overround(area)
    for r in rows:
        r["league"], r["p_global"], r["global_kind"], r["global_direct"], r["kickoff"], r["live"] = "", None, "eşleşmedi", None, None, None
        try:
            home, away = [x.strip() for x in r["match"].split(" - ", 1)]
        except ValueError:
            continue
        day = r["placed_dt"].date()
        m, sc = best_match(home, away, day, ng, days_after=1)
        if m:
            r["league"] = m["league"]
            r["kickoff"] = m["ko"]
            if r["name"] and r["name"] in m["sel"]:
                p, _o, direct = m["sel"][r["name"]]
                r["p_global"], r["global_kind"], r["global_direct"] = p, f"nesine_global {m['ref']} ({(m['ref_t'] or '')[:16]}Z)", direct
                r["ref_match"] = f"{m['home']} - {m['away']} ({sc:.2f})"
        if r["p_global"] is None and r["name"]:
            m2, sc = best_match(home, away, day, refs)
            if m2:
                r["league"] = r["league"] or m2["league"]
                r["kickoff"] = r["kickoff"] or m2.get("ko")
                p, direct = ref_probability(r["name"], m2)
                if p is not None:
                    r["p_global"], r["global_kind"], r["global_direct"] = p, m2["kind"], direct
                    r["ref_match"] = f"{m2['home']} - {m2['away']} ({sc:.2f})"
        if r["p_global"] is not None and r["leg_odds"] and r["p_global"] * r["leg_odds"] - 1 > MAX_PLAUSIBLE_EV:
            r["global_kind"] = f"şüpheli (EV>{MAX_PLAUSIBLE_EV:+.0%}, p={r['p_global']:.2f}): " + r["global_kind"]
            r["p_global"] = None
        if not r["league"]:
            e, _ = best_match(home, away, day, espn)
            if e:
                r["league"] = f"ESPN:{e['league']}"
        if not r["kickoff"]:
            e, _ = best_match(home, away, day, espn)
            if e:
                r["kickoff"] = e["ko"]
        if r["kickoff"]:
            r["live"] = r["placed_dt"] >= r["kickoff"]
        if r["live"] and r["p_global"] is not None:
            r["global_kind"] = "canlı bahis (maç başladıktan sonra oynanmış; maç öncesi adil fiyatla kıyaslanmaz): " + r["global_kind"]
            r["p_global"] = None
        if r["leg_odds"]:
            r["p_impl"] = implied_prob(r["leg_odds"], overround_for(r["family"], ovr))
        else:
            r["p_impl"] = None

    settled = [r for r in rows if r["leg_result"] in ("won", "lost")]

    def fam_table(key):
        g = defaultdict(list)
        for r in settled:
            g[key(r)].append(r)
        out = []
        for k, rs in sorted(g.items(), key=lambda kv: -len(kv[1])):
            n = len(rs)
            w = sum(r["leg_result"] == "won" for r in rs)
            pi = [r["p_impl"] for r in rs if r["p_impl"]]
            pg = [(r["p_global"], r["leg_result"] == "won", r["leg_odds"]) for r in rs if r["p_global"] is not None]
            mean_impl = sum(pi) / len(pi) if pi else None
            out.append({
                "grup": k, "n": n, "tutan": w, "isabet": round(w / n, 3),
                "ort_oran": round(sum(r["leg_odds"] for r in rs if r["leg_odds"]) / n, 3),
                "nesine_ima_marjsiz": None if mean_impl is None else round(mean_impl, 3),
                "beklenen_tutan_nesine": None if mean_impl is None else round(sum(pi), 1),
                "binom_p": None if mean_impl is None else round(binom_two_sided_p(w, n, mean_impl), 3),
                "global_eslesen": len(pg),
                "global_ort_p": round(sum(x[0] for x in pg) / len(pg), 3) if pg else None,
                "global_tutan": sum(x[1] for x in pg) if pg else None,
                "global_ev_ort": round(sum(x[0] * x[2] - 1 for x in pg) / len(pg), 3) if pg else None,
                "flat_roi_bacak": round(sum((r["leg_odds"] - 1) if r["leg_result"] == "won" else -1 for r in rs) / n, 3),
            })
        return out

    # ---- coupon diagnostics (bacak düzeyi)
    lost = [c for c in cd if c["status"] == "Kaybetti"]
    one_leg = [c for c in lost if c["lost_legs"] == 1]
    one_leg_clean = [c for c in one_leg if c["pending_legs"] == 0]
    culprit = []
    for c in one_leg:
        for r in rows:
            if r["coupon_id"] == c["coupon_id"] and r["leg_result"] == "lost":
                culprit.append({"kupon": c["coupon_id"], "mac": r["match"], "pazar": r["family"], "secim": r["selection"],
                                "oran": r["leg_odds"], "skor": r["score"], "p_global": r["p_global"]})
    # correlated exposure
    by_match = defaultdict(list)
    for r in rows:
        by_match[r["match"]].append(r)
    exposure = []
    for mt, rs in by_match.items():
        cids = {r["coupon_id"] for r in rs}
        if len(cids) >= 2:
            stake = sum(c["stake"] for c in cd if c["coupon_id"] in cids)
            exposure.append({"mac": mt, "kupon": len(cids), "secimler": sorted({f"{r['family']}:{r['selection']}" for r in rs}),
                             "sonuc": sorted({r["leg_result"] for r in rs}), "kupon_stake_TL": stake})
    exposure.sort(key=lambda x: (-x["kupon"], -x["kupon_stake_TL"]))
    # structural flags
    struct = {
        "bacak_sayisi_7_ustu_kupon": sum(c["legs"] > 7 for c in allc),
        "toplam_kupon": len(allc),
        "oran_1_20_alti_bacak": sum(1 for r in rows if r["leg_odds"] and 1.0 < r["leg_odds"] < 1.20),
        "oran_4_ustu_bacak": sum(1 for r in rows if r["leg_odds"] and r["leg_odds"] >= 4.0),
        "oran_4_ustu_tutan": sum(1 for r in rows if r["leg_odds"] and r["leg_odds"] >= 4.0 and r["leg_result"] == "won"),
        "toplam_oran_50_ustu_kupon": sum(c["total_odds"] >= 50 for c in allc),
        "kupondas_kopya_kupon": sum(1 for c in cl if c.get("copied_from")),
        "kupondas_kopya_kazanan": sum(1 for c in cl if c.get("copied_from") and c["status"] == "Kazandı"),
    }
    # theoretical value of each coupon using global fair probabilities where every leg is matched
    coupon_ev = []
    for c in cd:
        legs = [r for r in rows if r["coupon_id"] == c["coupon_id"] and r["leg_result"] != "void"]
        if legs and all(r["p_global"] is not None and r["leg_odds"] for r in legs):
            prod = 1.0
            for r in legs:
                prod *= r["p_global"] * r["leg_odds"]
            coupon_ev.append({"kupon": c["coupon_id"], "bacak": len(legs), "beklenen_donus_carpani": round(prod, 3), "durum": c["status"]})
    leg_ev = [r["p_global"] * r["leg_odds"] - 1 for r in rows if r["p_global"] is not None and r["leg_odds"]]

    out = {
        "uretim": dt.datetime.now().isoformat(timespec="minutes"),
        "kapsam": {"bacak_duzeyi_kupon": len(cd), "bacak": len(rows), "liste_duzeyi_ek_kupon": len(cl),
                   "liste_tarih": [min(c["placed"] for c in cl).isoformat(), max(c["placed"] for c in cl).isoformat()] if cl else None,
                   "bacak_tarih": [min(c["placed"] for c in cd).isoformat(), max(c["placed"] for c in cd).isoformat()]},
        "roi_genel": roi_table(allc, lambda c: "tümü"),
        # 13–19 Kasım için yalnız KAZANAN kuponlar çekilebildi (kaybedenler eksik): ROI'yi şişirir, ayrı raporlanır
        "roi_tam_donem": roi_table(complete, lambda c: "liste (20 Eki–10 Kas) + bacak (20–21 Kas)"),
        "roi_tam_donem_bacak_sayisi": roi_table(complete, lambda c: legs_bucket(c["legs"])),
        "roi_tam_donem_toplam_oran": roi_table(complete, lambda c: total_odds_band(c["total_odds"])),
        "eksik_donem_13_19_kasim": roi_table([c for c in cd if c["placed"] < COMPLETE_FROM], lambda c: "13–19 Kas (yalnız kazananlar)"),
        "roi_kaynak": roi_table(allc, lambda c: c["source"]),
        "roi_bacak_sayisi": roi_table(allc, lambda c: legs_bucket(c["legs"])),
        "roi_toplam_oran": roi_table(allc, lambda c: total_odds_band(c["total_odds"])),
        "kaybeden_bacak_duzeyi": len(lost), "tek_bacakla_kaybeden": len(one_leg),
        "tek_bacakla_kaybeden_bekleyensiz": len(one_leg_clean), "tek_bacak_suclular": culprit,
        "pazar_ailesi": fam_table(lambda r: r["family"]),
        "zor_pazarlar": fam_table(lambda r: "zor (Üst2.5/3.5, KG Var, zayıf MS1, İY/MS, uzun atış)" if r["hard"] else "diğer"),
        "oran_bandi": fam_table(lambda r: odds_band(r["leg_odds"]) if r["leg_odds"] else "?"),
        "korelasyon": exposure,
        "yapisal": struct,
        "global_eslesen_bacak": sum(r["p_global"] is not None for r in rows),
        "baslama_saati_bilinen_bacak": sum(r["kickoff"] is not None for r in rows),
        "canli_oynanan_bacak": sum(bool(r["live"]) for r in rows),
        "canli_bacak_sonuc": dict(Counter(r["leg_result"] for r in rows if r["live"])),
        "lig_bulunan_bacak": sum(bool(r["league"]) for r in rows),
        "bacak_ev_global_ort": round(sum(leg_ev) / len(leg_ev), 4) if leg_ev else None,
        "bacak_ev_global_n": len(leg_ev),
        "kupon_beklenen_donus": coupon_ev,
        "nesine_marj_varsayimi": ovr,
    }
    (area / "kupon_postmortem.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with open(area / "kupon_postmortem_bacaklar.csv", "w", newline="", encoding="utf-8-sig") as f:
        cols = ["coupon_id", "placed", "match", "league", "market", "selection", "name", "family", "hard", "leg_odds", "leg_result",
                "score", "kickoff", "live", "p_impl", "p_global", "global_direct", "global_kind", "ref_match"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(json.dumps({k: out[k] for k in ("kapsam", "roi_genel", "roi_tam_donem", "roi_tam_donem_bacak_sayisi",
                                          "roi_tam_donem_toplam_oran", "eksik_donem_13_19_kasim", "roi_kaynak", "roi_bacak_sayisi", "roi_toplam_oran", "yapisal",
                                          "kaybeden_bacak_duzeyi", "tek_bacakla_kaybeden", "tek_bacakla_kaybeden_bekleyensiz",
                                          "global_eslesen_bacak", "lig_bulunan_bacak", "baslama_saati_bilinen_bacak", "canli_oynanan_bacak", "canli_bacak_sonuc", "bacak_ev_global_ort", "bacak_ev_global_n")},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
