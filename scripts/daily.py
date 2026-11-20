"""Günlük QuantFoot akışı — tarihe bağlı eski betiklerin tek, parametreli karşılığı.

Alt komutlar (hepsi --date YYYY-MM-DD alır; çıktılar tahminler/<yapay zekâ>/<tarih>/ altına yazılır):

    predict   ESPN'den maçları + canlı oranları çeker, gol beklentisini piyasaya uydurur,
              tüm gol pazarlarını fiyatlar               -> predictions.json
    coupons   Artı EV tekiller ve (varsa) artı EV kombineler -> coupons.json / coupons.md
    report    Maç maç okunabilir rapor                     -> report.md
    results   İY ve 90. dakika skorlarını çeker (+ manual_results.json) -> results.json
    snapshot  Başlamamış maçların güncel oranlarını kaydeder; maç başlamadan önceki son kayıt
              kapanış oranıdır (gün içinde birkaç kez / maçlardan hemen önce çalıştırın)
                                                           -> closing_odds.json
    verify    Tahminleri ve kuponları sonuçlarla denetler; havuz ağırlığı testi (model piyasaya
              bilgi katıyor mu?) ve değer tekillerinin CLV'si   -> verify.json / verify.md
    summary   Tüm günleri birleştirip havuz testi ve CLV'yi güven aralığıyla raporlar
                                                           -> reports/daily/summary.md
    run       predict + coupons + report

Örnekler:
    python scripts/daily.py run --date 2026-11-20
    python scripts/daily.py results --date 2026-11-20
    python scripts/daily.py verify --date 2026-11-20

Gol beklentisi hakkında: tohum (seed) değerleri verilmezse gol beklentisi tamamen canlı
oranlardan çıkar (fund_weight=0). O zaman model aynı büronun oranlarına karşı değer bulamaz;
EV yaklaşık "eksi büro marjı" olur — bu dürüst sonuçtur. Sabit bir önsel kullanmak favorileri
zayıflatıp altları ve beraberlikleri yapay olarak "değerli" gösterir. Bağımsız bir sinyal için
--seeds ile model tahminleri verin ({"<event_id>": [ev_xg, dep_xg], ...}).

Eski 18 Kasım dosyaları (reports/today_v6_predictions_2026_11_18.json,
reports/ledger/coupons_2026_11_18.json) `verify` tarafından otomatik okunur.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
import os
from pathlib import Path

import numpy as np

from quantfoot.data.live_espn import fetch_league_slate
from quantfoot.evaluation.market_benchmark import fair_clv, mean_with_ci, pooling_test, raw_clv
from quantfoot.evaluation.settlement import fetch_espn_result, settle_selection
from quantfoot.markets.devig import devig
from quantfoot.markets.goal_markets import asian_handicap, price_goal_markets
from quantfoot.markets.omni_markets import compute_omni_markets
from quantfoot.markets.tail_goals import fit_tail_rates_from_markets, league_tail_regime
from quantfoot.strategy.coupon_builder import (
    MatchRiskContext,
    build_target_odds_coupon,
    is_uncalibrated_competition,
    select_best_valid_bet,
)

ROOT = Path(__file__).resolve().parents[1]
DAILY = ROOT / "tahminler" / os.environ.get("QUANTFOOT_AI", "claudetahmin")  # the AI's own folder (20 Nov)
LEDGER = ROOT / "reports" / "ledger"

DEFAULT_SLUGS: tuple[str, ...] = (
    "eng.1", "eng.2", "eng.3", "eng.4", "eng.5", "esp.1", "esp.2", "ger.1", "ger.2", "ita.1", "ita.2",
    "fra.1", "fra.2", "tur.1", "ned.1", "por.1", "bel.1", "sco.1", "gre.1",
    "uefa.champions", "uefa.europa", "uefa.europa.conf", "uefa.nations", "fifa.friendly", "fifa.worldq.uefa",
    "bra.1", "arg.1", "usa.1", "mex.1",
    "esp.copa_del_rey", "eng.fa", "eng.league_cup", "ita.coppa_italia", "ger.dfb_pokal", "fra.coupe_de_france",
    "uefa.wchampions", "eng.w.1",
)
SLUG_TO_DIVISION = {
    "eng.1": "E0", "eng.2": "E1", "eng.3": "E2", "eng.4": "E3", "eng.5": "EC", "esp.1": "SP1", "esp.2": "SP2",
    "ger.1": "D1", "ger.2": "D2", "ita.1": "I1", "ita.2": "I2", "fra.1": "F1", "fra.2": "F2", "tur.1": "T1",
    "ned.1": "N1", "por.1": "P1", "bel.1": "B1", "sco.1": "SC0", "gre.1": "G1",
}


def _day_dir(date: str) -> Path:
    d = DAILY / date
    d.mkdir(parents=True, exist_ok=True)
    return d


def _legacy_name(date: str) -> str:
    return date.replace("-", "_")


def _read_json(path: Path) -> dict | list | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"yazıldı: {path.relative_to(ROOT)}")


# ----------------------------------------------------------------------------------------------
# predict
# ----------------------------------------------------------------------------------------------
def _offered_odds(fx) -> dict[str, float]:
    odds: dict[str, float] = {}
    if fx.cur_1x2:
        odds.update({"MS 1": fx.cur_1x2[0], "MS 0": fx.cur_1x2[1], "MS 2": fx.cur_1x2[2]})
    if fx.ou_line is not None and fx.ou_odds and float(fx.ou_line) % 1 == 0.5:
        odds[f"{float(fx.ou_line):.1f} Üst"] = fx.ou_odds[0]
        odds[f"{float(fx.ou_line):.1f} Alt"] = fx.ou_odds[1]
    if fx.ah_line is not None and fx.ah_odds:
        odds[f"AH Ev {float(fx.ah_line):+.2f}"] = fx.ah_odds[0]
        odds[f"AH Dep {-float(fx.ah_line):+.2f}"] = fx.ah_odds[1]
    return {k: round(float(v), 3) for k, v in odds.items()}


def _fair_probs(odds: dict[str, float]) -> dict[str, float]:
    """Margin-free probabilities per selection, devigging each market (1X2, O/U line, AH line) separately."""
    groups: dict[str, list[str]] = {}
    for sel in odds:
        if sel.startswith("MS "):
            key = "1x2"
        elif sel.startswith("AH "):
            key = "ah"
        else:
            key = "ou " + sel.split()[0]
        groups.setdefault(key, []).append(sel)
    fair: dict[str, float] = {}
    for sels in groups.values():
        if len(sels) < 2:
            continue
        probs = devig([odds[s] for s in sels], method="power").probabilities
        fair.update({s: float(p) for s, p in zip(sels, probs)})
    return fair


def _price_match(fx, slug: str, league: str, seeds: dict, fund_weight: float) -> dict:
    rec: dict = {
        "event_id": fx.event_id, "slug": slug, "league": league, "division": SLUG_TO_DIVISION.get(slug),
        "home": fx.home_team, "away": fx.away_team, "kickoff_utc": fx.date_utc, "status": fx.status,
        "cur_1x2": fx.cur_1x2, "open_1x2": fx.open_1x2, "ou_line": fx.ou_line, "ou_odds": fx.ou_odds,
        "ah_line": fx.ah_line, "ah_odds": fx.ah_odds,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    if is_uncalibrated_competition(league) or is_uncalibrated_competition(slug):
        rec["skipped"] = "kalibre edilmemiş yarışma (ör. kadın futbolu)"
        return rec
    if not fx.cur_1x2:
        rec["skipped"] = "1X2 oranı yok"
        return rec
    seed = tuple(seeds.get(str(fx.event_id), (1.45, 1.15)))
    com_nu, alpha_nb, kappa = league_tail_regime(slug)
    p_mkt = devig(list(fx.cur_1x2), method="power").probabilities
    p_over = None
    if fx.ou_line is not None and fx.ou_odds:
        p_over = float(devig(list(fx.ou_odds), method="power").probabilities[0])
    mu_h, mu_a, _ = fit_tail_rates_from_markets(
        p_1x2=p_mkt, ou_line=fx.ou_line if p_over is not None else None, p_over=p_over,
        seed_rates=(float(seed[0]), float(seed[1])), alpha_nb=alpha_nb, shared_kappa=kappa,
        com_nu=com_nu, fund_weight=fund_weight,
    )
    bundle = compute_omni_markets(mu_h, mu_a, league=slug)
    probs = {k: round(v, 5) for fam in price_goal_markets(bundle.joint).values() for k, v in fam.items()}
    offered = _offered_odds(fx)
    value = [
        {"selection": s, "odds": o, "prob": probs[s], "ev": round(probs[s] * o - 1.0, 4)}
        for s, o in offered.items() if s in probs
    ]
    if fx.ah_line is not None and fx.ah_odds:
        for side, odds in (("Ev", fx.ah_odds[0]), ("Dep", fx.ah_odds[1])):
            line = float(fx.ah_line) if side == "Ev" else -float(fx.ah_line)
            out = asian_handicap(bundle.joint, line, side)
            value.append({"selection": f"AH {side} {line:+.2f}", "odds": round(float(odds), 3),
                          "prob": round(out.win + 0.5 * out.half_win, 5), "ev": round(out.ev(float(odds)), 4)})
    value.sort(key=lambda v: v["ev"], reverse=True)
    rec.update(
        mu_home=round(float(mu_h), 4), mu_away=round(float(mu_a), 4),
        p_market_1x2=[round(float(x), 5) for x in p_mkt], p_market_over=None if p_over is None else round(p_over, 5),
        offered_odds=offered, probs=probs, value=value,
        top_scores=[s["score"] for s in bundle.top_ft_scores[:3]],
    )
    return rec


def cmd_predict(args: argparse.Namespace) -> None:
    ymd = args.date.replace("-", "")
    seeds = _read_json(Path(args.seeds)) if args.seeds else {}
    if args.fund_weight is None:
        # Without independent model seeds, a fixed prior (1.45-1.15) would only bias the market-fitted
        # rates toward an average match and manufacture fake "value" (weaker favourites, unders, draws).
        args.fund_weight = 0.22 if seeds else 0.0
    slugs = args.slugs or list(DEFAULT_SLUGS)

    def _fetch(slug: str):
        try:
            return slug, *fetch_league_slate(slug, ymd)
        except Exception as exc:  # unknown slug / network: skip that competition
            return slug, f"hata: {exc}", []

    with ThreadPoolExecutor(max_workers=12) as pool:
        slates = list(pool.map(_fetch, slugs))
    matches, seen = [], set()
    for slug, league, fixtures in slates:
        for fx in fixtures:
            if fx.event_id in seen:
                continue
            seen.add(fx.event_id)
            matches.append(_price_match(fx, slug, league, seeds or {}, args.fund_weight))
    matches.sort(key=lambda m: (m["kickoff_utc"], m["league"], m["home"]))
    priced = sum(1 for m in matches if "probs" in m)
    print(f"{args.date}: {len(matches)} maç bulundu, {priced} fiyatlandı, {len(matches) - priced} atlandı.")
    _write_json(_day_dir(args.date) / "predictions.json", {
        "date": args.date, "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "fund_weight": args.fund_weight, "seeds_file": args.seeds, "slugs": slugs, "matches": matches,
    })


# ----------------------------------------------------------------------------------------------
# coupons
# ----------------------------------------------------------------------------------------------
def cmd_coupons(args: argparse.Namespace) -> None:
    pred = _read_json(_day_dir(args.date) / "predictions.json")
    if not pred:
        raise SystemExit("Önce `predict` çalıştırın.")
    singles, pool = [], []
    for m in pred["matches"]:
        if "probs" not in m:
            continue
        for v in m["value"]:
            if v["ev"] >= args.min_ev:
                singles.append({**v, "event_id": m["event_id"], "match": f"{m['home']} - {m['away']}", "league": m["league"]})
        bundle = compute_omni_markets(m["mu_home"], m["mu_away"], league=m["slug"])
        recs = select_best_valid_bet(
            m["event_id"], m["home"], m["away"], m["league"], m["kickoff_utc"], bundle,
            offered_odds_map=m["offered_odds"], risk_ctx=MatchRiskContext(group_id=m["event_id"]),
        )
        recs = [r for r in recs if not r.odds_is_estimated]  # only bookmaker-priced legs
        if recs:
            pool.append(recs)
    singles.sort(key=lambda v: v["ev"], reverse=True)
    coupons = []
    for target in args.targets:
        plan = build_target_odds_coupon(pool, target_odds=target, max_legs=args.max_legs, min_leg_ev=args.min_ev,
                                        title=f"Hedef {target:g}x (yalnızca artı EV bacaklar)")
        coupons.append({
            "title": plan.title, "target_odds": target, "reached_target": plan.reached_target,
            "achieved_odds": plan.achieved_odds, "joint_probability": plan.joint_probability,
            "expected_value": plan.expected_value,
            "legs": [{"event_id": leg.match_id, "match": f"{leg.home} - {leg.away}", "selection": leg.selection,
                      "odds": leg.offered_odds, "prob": leg.probability, "ev": leg.ev} for leg in plan.legs],
        })
    out = {"date": args.date, "min_ev": args.min_ev, "value_singles": singles, "coupons": coupons}
    d = _day_dir(args.date)
    _write_json(d / "coupons.json", out)
    md = [f"# {args.date} — Değer Tekilleri ve Kuponlar", "",
          f"Eşik: model EV ≥ {args.min_ev:+.1%}. Yalnızca büronun gerçek oranları kullanılır.", "",
          "> **Bu liste bahis önerisi değildir.** Gol beklentisi bu büronun oranlarına uydurulduğu için buradaki "
          "artı EV, modelin gol dağılımı ile piyasanın yapısal farkıdır. Geçmiş testte (16.423 maç, 2021–2026) repodaki "
          "15 modelin hiçbiri Bet365 fiyatına bilgi katmadı (havuz ağırlığı w = 0.00; `reports/research/pooling_test.md`). "
          "Nesine için global referans karşılaştırması: `scripts/nesine_global.py`.", ""]
    md += ["## Artı EV tekiller", ""]
    if singles:
        md += ["| Maç | Seçim | Oran | Model P | EV |", "|---|---|---|---|---|"]
        md += [f"| {s['match']} | {s['selection']} | {s['odds']:.2f} | %{s['prob'] * 100:.1f} | {s['ev']:+.1%} |" for s in singles]
    else:
        md.append("_Eşiği geçen tekil yok — bugün oynanacak değer bulunmadı._")
    md += ["", "## Kuponlar", ""]
    for c in coupons:
        if not c["legs"]:
            md.append(f"- **{c['title']}**: kurulamadı (yeterli artı EV bacak yok).")
            continue
        flag = "" if c["reached_target"] else " (hedefe ulaşılamadı)"
        md.append(f"- **{c['title']}**{flag}: oran {c['achieved_odds']:.2f}, olasılık %{c['joint_probability'] * 100:.1f}, EV {c['expected_value']:+.1%}")
        md += [f"  - {leg['match']}: {leg['selection']} @ {leg['odds']:.2f} (P %{leg['prob'] * 100:.1f}, EV {leg['ev']:+.1%})" for leg in c["legs"]]
    (d / "coupons.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _update_index(args.date, len(pred["matches"]), len(singles), sum(1 for c in coupons if c["legs"]))


def _update_index(date: str, n_matches: int, n_singles: int, n_coupons: int) -> None:
    path = LEDGER / "INDEX.md"
    row = (f"| **{date}** | `daily.py` | {n_matches} Maç | [coupons.md](../daily/{date}/coupons.md) / "
           f"[report.md](../daily/{date}/report.md) | `{n_singles} artı EV tekil, {n_coupons} kupon` |")
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else [
        "# QuantFoot Tahmin ve Kupon Arşivi", "", "| Tarih | Motor | Maç Sayısı | Dosyalar | Durum |",
        "| :---: | :--- | :---: | :--- | :--- |"]
    lines = [ln for ln in lines if not ln.startswith(f"| **{date}** | `daily.py`")]
    rows = sorted([ln for ln in lines if ln.startswith("| **")] + [row])  # chronological (ISO dates sort lexically)
    first = next((i for i, ln in enumerate(lines) if ln.startswith("| **")), len(lines))
    lines = [ln for ln in lines[:first] if not ln.startswith("| **")] + rows + [ln for ln in lines[first:] if not ln.startswith("| **")]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------------------------
# report
# ----------------------------------------------------------------------------------------------
def cmd_report(args: argparse.Namespace) -> None:
    pred = _read_json(_day_dir(args.date) / "predictions.json")
    if not pred:
        raise SystemExit("Önce `predict` çalıştırın.")
    priced = [m for m in pred["matches"] if "probs" in m]
    skipped = [m for m in pred["matches"] if "probs" not in m]
    md = [f"# {args.date} — Maç Tahminleri", "",
          f"{len(priced)} maç fiyatlandı, {len(skipped)} maç atlandı. Gol beklentisi canlı oranlara uydurulmuştur "
          f"(fund_weight={pred['fund_weight']}).", "",
          "| Saat (UTC) | Lig | Maç | Oran 1/X/2 | xG | MS 1 / X / 2 | 2.5 Üst | KG Var | En iyi EV |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in priced:
        p, o = m["probs"], m["cur_1x2"]
        best = m["value"][0] if m["value"] else None
        best_s = f"{best['selection']} @ {best['odds']:.2f} ({best['ev']:+.1%})" if best else "-"
        md.append(
            f"| {m['kickoff_utc'][11:16]} | {m['league']} | {m['home']} - {m['away']} | {o[0]:.2f}/{o[1]:.2f}/{o[2]:.2f} | "
            f"{m['mu_home']:.2f}-{m['mu_away']:.2f} | %{p['MS 1'] * 100:.0f} / %{p['MS 0'] * 100:.0f} / %{p['MS 2'] * 100:.0f} | "
            f"%{p['2.5 Üst'] * 100:.0f} | %{p['KG Var'] * 100:.0f} | {best_s} |"
        )
    if skipped:
        md += ["", "## Atlanan maçlar", ""] + [f"- {m['league']}: {m['home']} - {m['away']} — {m['skipped']}" for m in skipped]
    out = _day_dir(args.date) / "report.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"yazıldı: {out.relative_to(ROOT)}")


# ----------------------------------------------------------------------------------------------
# results / verify
# ----------------------------------------------------------------------------------------------
def _load_predictions(date: str) -> list[dict]:
    pred = _read_json(_day_dir(date) / "predictions.json")
    if pred:
        return pred["matches"]
    legacy = _read_json(ROOT / "reports" / f"today_v6_predictions_{_legacy_name(date)}.json")
    if legacy:
        print("eski biçimli tahmin dosyası kullanılıyor (today_v6_predictions_*.json)")
        return legacy["matches"]
    raise SystemExit(f"{date} için tahmin dosyası yok.")


def _match_probs(m: dict) -> dict[str, float]:
    """Flat selection -> probability for new and legacy prediction records."""
    if "probs" in m:
        return m["probs"]
    out: dict[str, float] = {}
    for k, v in (m.get("ft_1x2") or {}).items():
        out[f"MS {k}"] = v
    for group in ("ht_1x2", "h2_1x2", "goal_bands", "ft_ou", "ht_ou", "h2_ou", "btts", "combos"):
        out.update(m.get(group) or {})
    for k, v in (m.get("ht_ft") or {}).items():
        out[f"İY/MS {k}"] = v
    return out


def cmd_results(args: argparse.Namespace) -> None:
    matches = _load_predictions(args.date)
    d = _day_dir(args.date)
    cache = _read_json(d / "results.json") or {}
    todo = [m for m in matches if not cache.get(str(m["event_id"]), {}).get("completed")]
    with ThreadPoolExecutor(max_workers=12) as pool:
        for m, rec in zip(todo, pool.map(lambda x: fetch_espn_result(str(x["event_id"]), x.get("slug")), todo)):
            cache[str(m["event_id"])] = rec
    manual = _read_json(d / "manual_results.json") or {}
    for eid, rec in manual.items():
        cache[str(eid)] = {"completed": True, "status": "manuel", "ht": rec["ht"], "ft90": rec["ft90"]}
    done = sum(1 for r in cache.values() if r.get("completed"))
    print(f"{done}/{len(matches)} maç sonuçlandı.")
    _write_json(d / "results.json", cache)


def _load_coupons(date: str) -> list[dict]:
    cur = _read_json(_day_dir(date) / "coupons.json")
    if cur:
        return [{"title": c["title"], "legs": c["legs"]} for c in cur["coupons"] if c["legs"]]
    legacy = _read_json(LEDGER / f"coupons_{_legacy_name(date)}.json")
    if legacy:
        return [{"title": c["title"], "legs": c["legs"]} for c in legacy["coupons"]]
    return []


def _collect_day(date: str) -> dict:
    """Settle one day: per-match rows, 1X2 arrays for the pooling test, CLV and flat P/L of value singles."""
    matches = _load_predictions(date)
    d = DAILY / date
    results = _read_json(d / "results.json") or {}
    closing = _read_json(d / "closing_odds.json") or {}
    rows, p_mkt_rows, p_mod_rows, ys = [], [], [], []
    for m in matches:
        eid = str(m["event_id"])
        res = results.get(eid, {})
        if not res.get("completed"):
            continue
        ht, ft = tuple(res["ht"]), tuple(res["ft90"])
        probs = _match_probs(m)
        k = 0 if ft[0] > ft[1] else (1 if ft[0] == ft[1] else 2)
        close_fair = _fair_probs(closing[eid]["odds"]) if eid in closing else {}
        if all(f"MS {c}" in close_fair for c in "102"):
            p_mkt, mkt_src = [close_fair["MS 1"], close_fair["MS 0"], close_fair["MS 2"]], "kapanış"
        elif m.get("p_market_1x2") is not None:
            p_mkt, mkt_src = m["p_market_1x2"], "tahmin anı"
        elif m.get("cur_1x2"):
            p_mkt, mkt_src = list(devig(list(m["cur_1x2"]), method="power").probabilities), "tahmin anı"
        else:
            p_mkt, mkt_src = None, None
        if p_mkt is not None and all(f"MS {c}" in probs for c in "102"):
            p_mkt_rows.append(list(p_mkt))
            p_mod_rows.append([probs["MS 1"], probs["MS 0"], probs["MS 2"]])
            ys.append(k)
        best = (m.get("value") or [None])[0] if "value" in m else m.get("best_valid_bet")
        hit = settle_selection(best["selection"], ht, ft) if best and not best["selection"].startswith("AH ") else None
        rows.append({"event_id": eid, "match": f"{m['home']} - {m['away']}", "score": f"{ft[0]}-{ft[1]} (İY {ht[0]}-{ht[1]})",
                     "best_selection": best["selection"] if best else None, "hit_best": hit, "market_source": mkt_src})

    singles = (_read_json(d / "coupons.json") or {}).get("value_singles", [])
    clv_rows = []
    for sgl in singles:
        eid = str(sgl["event_id"])
        res = results.get(eid, {})
        close_odds = (closing.get(eid) or {}).get("odds", {})
        close_fair = _fair_probs(close_odds) if close_odds else {}
        won = None
        if res.get("completed") and not sgl["selection"].startswith("AH "):
            won = settle_selection(sgl["selection"], tuple(res["ht"]), tuple(res["ft90"]))
        sel = sgl["selection"]
        clv_rows.append({
            "event_id": eid, "selection": sel, "taken_odds": sgl["odds"], "model_ev": sgl["ev"],
            "closing_odds": close_odds.get(sel),
            "raw_clv": raw_clv(sgl["odds"], close_odds[sel]) if sel in close_odds else None,
            "fair_clv": fair_clv(sgl["odds"], close_fair[sel]) if sel in close_fair else None,
            "won": won, "profit": None if won is None else (sgl["odds"] - 1.0 if won else -1.0),
        })
    return {"rows": rows, "p_market": p_mkt_rows, "p_model": p_mod_rows, "y": ys, "clv": clv_rows}


def _benchmark_lines(p_market: list, p_model: list, y: list, clv: list[dict]) -> tuple[dict, list[str]]:
    """Pooling test + CLV / P&L summary as a dict and Markdown lines."""
    out: dict = {"n_matches_1x2": len(y)}
    md: list[str] = ["## Model piyasaya bilgi katıyor mu?", ""]
    if len(y) >= 5:
        res = pooling_test(np.array(p_market), np.array(p_model), np.array(y))
        out["pool"] = res.__dict__
        verdict = ("Aralık 0'ı içeriyor: model piyasaya **kanıtlanmış bilgi katmıyor**." if res.ci_low <= 0.0
                   else "Aralık 0'ın üstünde: model piyasaya bilgi katıyor olabilir.")
        md += [
            f"- 1X2 log-loss ({res.n} maç) — piyasa: **{res.logloss_market:.4f}**, model: **{res.logloss_model:.4f}**, "
            f"en iyi havuz: {res.logloss_pool:.4f}",
            f"- Havuzda modelin ağırlığı **w = {res.weight:.2f}** (%95 güven aralığı {res.ci_low:.2f} – {res.ci_high:.2f}). {verdict}",
        ]
    else:
        md.append(f"- Havuz testi için en az 5 sonuçlanmış maç gerekli (şu an {len(y)}).")
    with_fair = [c["fair_clv"] for c in clv if c["fair_clv"] is not None]
    fair = mean_with_ci(with_fair)
    raw = mean_with_ci([c["raw_clv"] for c in clv if c["raw_clv"] is not None])
    pl = [c["profit"] for c in clv if c["profit"] is not None]
    out.update(n_value_singles=len(clv), clv_fair=fair, clv_raw=raw, flat_profit=sum(pl) if pl else None, n_settled_singles=len(pl))
    md += ["", "## Değer tekilleri: kapanış çizgisi (CLV) ve kâr/zarar", ""]
    if fair:
        md.append(f"- Ortalama adil CLV (kapanışın marjsız fiyatına göre EV): **{fair[0]:+.2%}** "
                  f"(%95 GA {fair[1]:+.2%} – {fair[2]:+.2%}, {len(with_fair)} bahis)")
    if raw:
        md.append(f"- Ortalama ham CLV (alınan / kapanış oranı − 1): {raw[0]:+.2%} (%95 GA {raw[1]:+.2%} – {raw[2]:+.2%})")
    if not fair and not raw:
        md.append("- Kapanış oranı yok: maçlardan önce `snapshot` çalıştırılmalı.")
    if pl:
        md.append(f"- Sonuçlanan {len(pl)} tekilde düz (1 birim) kâr/zarar: **{sum(pl):+.2f} birim** (ROI {sum(pl) / len(pl):+.1%})")
    md += ["", "_Karar kuralı: haftalar boyunca adil CLV'nin güven aralığı sıfırın üstünde değilse bahis yapılmamalı._"]
    return out, md


def cmd_verify(args: argparse.Namespace) -> None:
    day = _collect_day(args.date)
    rows = day["rows"]
    d = _day_dir(args.date)
    results = _read_json(d / "results.json") or {}
    coupon_rows = []
    for c in _load_coupons(args.date):
        legs = []
        for leg in c["legs"]:
            res = results.get(str(leg["event_id"]), {})
            legs.append(settle_selection(leg["selection"], tuple(res["ht"]), tuple(res["ft90"])) if res.get("completed") else None)
        status = "KAYBETTİ" if False in legs else ("KAZANDI" if legs and all(legs) else "BEKLİYOR")
        coupon_rows.append({"title": c["title"], "legs_hit": sum(1 for x in legs if x), "legs": len(legs), "status": status})
    bench, bench_md = _benchmark_lines(day["p_market"], day["p_model"], day["y"], day["clv"])
    summary = {
        "settled_matches": len(rows),
        "best_pick_hits": sum(1 for r in rows if r["hit_best"]),
        "best_pick_settled": sum(1 for r in rows if r["hit_best"] is not None),
        **bench,
    }
    _write_json(d / "verify.json", {"date": args.date, "summary": summary, "matches": rows, "coupons": coupon_rows, "clv": day["clv"]})
    md = [f"# {args.date} — Tahmin ve Kupon Denetimi", "",
          f"- Sonuçlanan maç: **{summary['settled_matches']}**; en iyi seçim isabeti: "
          f"**{summary['best_pick_hits']}/{summary['best_pick_settled']}**", ""]
    md += bench_md + ["", "## Kuponlar", ""]
    md += [f"- {c['title']}: {c['legs_hit']}/{c['legs']} bacak tuttu — **{c['status']}**" for c in coupon_rows] or ["_Kupon yok._"]
    md += ["", "## Maçlar", "", "| Maç | Skor | En iyi seçim | Sonuç | Piyasa kaynağı |", "|---|---|---|---|---|"]
    for r in rows:
        mark = "✓" if r["hit_best"] else ("✗" if r["hit_best"] is False else "-")
        md.append(f"| {r['match']} | {r['score']} | {r['best_selection'] or '-'} | {mark} | {r['market_source'] or '-'} |")
    (d / "verify.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(bench_md[2:4]))


def cmd_snapshot(args: argparse.Namespace) -> None:
    """Record current odds for matches that have not kicked off; the last snapshot before kickoff is the closing line."""
    pred = _read_json(_day_dir(args.date) / "predictions.json")
    if not pred:
        raise SystemExit("Önce `predict` çalıştırın.")
    ids = {str(m["event_id"]) for m in pred["matches"]}
    slugs = sorted({m["slug"] for m in pred["matches"]})
    ymd = args.date.replace("-", "")
    with ThreadPoolExecutor(max_workers=12) as pool:
        slates = list(pool.map(lambda sl: fetch_league_slate(sl, ymd), slugs))
    path = _day_dir(args.date) / "closing_odds.json"
    closing = _read_json(path) or {}
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    updated = frozen = 0
    for _, fixtures in slates:
        for fx in fixtures:
            eid = str(fx.event_id)
            if eid not in ids:
                continue
            if fx.status == "STATUS_SCHEDULED":
                odds = _offered_odds(fx)
                if odds:
                    closing[eid] = {"captured_at": now, "kickoff_utc": fx.date_utc, "odds": odds}
                    updated += 1
            else:
                frozen += 1
    print(f"{updated} maçın oranı güncellendi; {frozen} maç başladı/bitti (son kayıt kapanış sayılır).")
    _write_json(path, closing)


def cmd_summary(args: argparse.Namespace) -> None:
    """Pool every verified day: the evidence that matters is the multi-day pooling weight and CLV."""
    p_mkt, p_mod, ys, clv, days = [], [], [], [], []
    for d in sorted(p for p in DAILY.iterdir() if p.is_dir()):
        if not (d / "results.json").exists():
            continue
        try:
            day = _collect_day(d.name)
        except SystemExit:
            continue
        days.append(d.name)
        p_mkt += day["p_market"]
        p_mod += day["p_model"]
        ys += day["y"]
        clv += day["clv"]
    bench, bench_md = _benchmark_lines(p_mkt, p_mod, ys, clv)
    md = ["# QuantFoot — Çok Günlük Model ve CLV Özeti", "", f"Günler: {', '.join(days) or '-'}", ""] + bench_md
    (DAILY / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _write_json(DAILY / "summary.json", {"days": days, **bench})
    print("\n".join(bench_md[2:4]))


def cmd_run(args: argparse.Namespace) -> None:
    cmd_predict(args)
    cmd_coupons(args)
    cmd_report(args)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    today = dt.date.today().isoformat()

    def _add(name, fn, predict=False, coupons=False):
        p = sub.add_parser(name)
        p.add_argument("--date", default=today, help="YYYY-MM-DD (varsayılan: bugün)")
        if predict:
            p.add_argument("--slugs", nargs="+", default=None, help="ESPN yarışma kodları (varsayılan liste: DEFAULT_SLUGS)")
            p.add_argument("--seeds", default=None, help='JSON: {"event_id": [ev_xg, dep_xg]} bağımsız model tahminleri')
            p.add_argument("--fund-weight", type=float, default=None,
                           help="Tohum gol beklentisinin ağırlığı (varsayılan: --seeds varsa 0.22, yoksa 0 = saf piyasa)")
        if coupons:
            p.add_argument("--min-ev", type=float, default=0.02, help="Bacak / tekil için en düşük model EV'si")
            p.add_argument("--targets", nargs="+", type=float, default=[3.0, 5.0, 10.0])
            p.add_argument("--max-legs", type=int, default=4)
        p.set_defaults(func=fn)

    _add("predict", cmd_predict, predict=True)
    _add("coupons", cmd_coupons, coupons=True)
    _add("report", cmd_report)
    _add("results", cmd_results)
    _add("verify", cmd_verify)
    _add("snapshot", cmd_snapshot)
    sub.add_parser("summary").set_defaults(func=cmd_summary)
    _add("run", cmd_run, predict=True, coupons=True)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
