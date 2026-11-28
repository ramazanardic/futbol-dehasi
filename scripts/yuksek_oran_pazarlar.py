#!/usr/bin/env python3
"""Yüksek oranlı pazarlar: kesin skor, İY skoru, İY/MS, 2Y KG — ANALİZ katmanı (korner banko ailesine taşındı: scripts/korner_olcum.py).

Banko kupona GİRMEZ (KURALLAR.md: İY/MS, skor, KG banko kuponda yasak). Günlük akışa bağlı değildir;
yalnız bu komut açıkça çalıştırılınca çalışır.

    # sızıntısız ileri-yürüyen test + rapor + kalibrasyon dosyası
    python scripts/yuksek_oran_pazarlar.py backtest
    # tek maç olasılıkları (oranlar Nesine/piyasa 1X2 ve isteğe bağlı 2.5 Alt/Üst)
    python scripts/yuksek_oran_pazarlar.py tahmin --lig E0 --ev Arsenal --dep Chelsea --oran 1.95 3.6 4.0 --ust-alt 1.85 1.95

Çıktılar: reports/research/yuksek_oran_pazarlar_<tarih>.{md,json}, data/calibration/yuksek_oran_kalibrasyon.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.evaluation import yuksek_oran_backtest as bt
from quantfoot.markets import yuksek_oran_modeli as ym

FT_LABELS = [f"{h}-{a}" for h, a in ym.FT_SCORES] + ["diğer"]
HT_LABELS = [f"{h}-{a}" for h, a in ym.HT_SCORES] + ["diğer"]


def _split(df: pd.DataFrame, a: str, b: str | None = None) -> np.ndarray:
    m = (df.MatchDate >= a).to_numpy().copy()
    if b:
        m &= (df.MatchDate < b).to_numpy()
    return m


def _objective(f: pd.DataFrame, y: dict, mask: np.ndarray, cfg: bt.ProbConfig) -> tuple[float, dict]:
    mh, ma, _ = bt.game_state_multipliers(f, cfg)
    v = f[mask].reset_index(drop=True)
    yy = {k: a[mask] for k, a in y.items()}
    ht = yy["ht_ok"]
    r = bt.raw_probs(v, cfg, "sonra", (mh[mask], ma[mask]), ft_from_halves=True)
    parts = {
        "skor": bt.multi_metrics(r["ft"], yy["ft"])["logloss"],
        "iyms": bt.multi_metrics(r["htft"][ht], yy["htft"][ht])["logloss"],
        "iy_skor": bt.multi_metrics(r["ht"][ht], yy["ht"][ht])["logloss"],
        "kg2": bt.binary_metrics(r["kg2"][ht], yy["kg2"][ht])["logloss"],
    }
    return sum(parts.values()), parts


def _market_block(name: str, preds: dict[str, np.ndarray], y: np.ndarray, labels: list[str] | None) -> dict:
    out: dict = {"pazar": name, "modeller": {}}
    ll = {}
    for k, p in preds.items():
        met = bt.multi_metrics(p, y) if p.ndim == 2 else bt.binary_metrics(p, y)
        met["ece"] = bt.ece(p, y)
        met["kalibrasyon"] = bt.calibration_table(p, y)
        if labels:
            met["secim_frekans"] = bt.class_freq(p, y, labels)
        out["modeller"][k] = met
        ll[k] = bt.per_row_ll(p, y)
    if "sonra" in ll:
        out["fark"] = {f"sonra-{k}": bt.paired_delta(ll[k], ll["sonra"]) for k in ll if k != "sonra"}
    return out


def _selection_reliability(name: str, p: np.ndarray, y: np.ndarray, labels: list[str], min_n: int = 40) -> list[dict]:
    """Seçim bazında: modelin bu seçime verdiği olasılık bandında gerçekleşen frekans (z-skoru)."""
    rows = []
    for c, lab in enumerate(labels):
        pc = p[:, c]
        yc = (y == c).astype(float)
        for lo, hi in ((0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.35), (0.35, 0.55), (0.55, 1.01)):
            s = (pc >= lo) & (pc < hi)
            n = int(s.sum())
            if n < min_n:
                continue
            exp, obs = float(pc[s].mean()), float(yc[s].mean())
            se = np.sqrt(max(exp * (1 - exp), 1e-9) / n)
            rows.append({"pazar": name, "secim": lab, "bant": f"{lo:.0%}-{min(hi, 1):.0%}", "n": n,
                         "tahmin": round(exp, 4), "gercek": round(obs, 4), "z": round((obs - exp) / se, 2),
                         "adil_oran": round(1 / exp, 2) if exp > 0 else None})
    return rows


def backtest(args: argparse.Namespace) -> None:
    df = bt.load_matches()
    hls = [float(x) for x in args.half_lives.split(",")]
    feats = {}
    for hl in hls:
        cache = Path(args.cache) / f"feat_{int(hl)}.pkl" if args.cache else None
        if cache and cache.exists():
            f = pd.read_pickle(cache)
        else:
            print(f"özellikler: yarı ömür {hl:.0f} gün", flush=True)
            f = bt.add_market_lambdas(bt.build_features(df, bt.FeatureConfig(half_life=hl)))
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                f.to_pickle(cache)
        feats[hl] = f
    val_a, val_b, test_a = args.val_from, args.test_from, args.test_from
    # yarı ömür: model-yalnız (önce) skor log-loss'u ile, doğrulamada
    best_hl, best = None, 1e9
    hl_scores = {}
    for hl, f in feats.items():
        m = _split(f, val_a, val_b) & f.lam_m.notna().to_numpy()
        r = bt.raw_probs(f[m].reset_index(drop=True), bt.ProbConfig(), "once")
        ll = bt.multi_metrics(r["ft"], bt.outcomes(f[m].reset_index(drop=True))["ft"])["logloss"]
        hl_scores[hl] = ll
        if ll < best:
            best_hl, best = hl, ll
    f = feats[best_hl]
    f = f[f.lam_p.notna() | f.lam_m.notna()].reset_index(drop=True)
    y = bt.outcomes(f)
    vmask = _split(f, val_a, val_b) & f.lam_m.notna().to_numpy() & f.lam_p.notna().to_numpy()
    grid = list(itertools.product((0.8, 0.9, 1.0), (0.0, 0.25), (0.0, -0.05), (0.0, -0.05)))
    best_cfg, best_obj, grid_rows = None, 1e9, []
    for w, g, r1, r2 in grid:
        cfg = bt.ProbConfig(w_market=w, gamma_team=g, rho_iy=r1, rho_2y=r2, rho_ms=0.0)
        obj, parts = _objective(f, y, vmask, cfg)
        grid_rows.append({"w_market": w, "gamma_team": g, "rho_iy": r1, "rho_2y": r2, **parts, "toplam": round(obj, 5)})
        if obj < best_obj:
            best_cfg, best_obj = cfg, obj
    print("seçilen:", best_cfg, flush=True)

    # tüm satırlar: ham 'sonra' + aylık sızıntısız kalibrasyon
    mh, ma, gs_last = bt.game_state_multipliers(f, best_cfg)
    raw = bt.raw_probs(f, best_cfg, "sonra", (mh, ma), ft_from_halves=True)
    raw_nocal = {k: v.copy() for k, v in raw.items()}
    cal, cal_last = bt.walk_forward_calibrate(f, raw, y, args.cal_from)
    test = _split(f, test_a) & f.lam_m.notna().to_numpy() & f.lam_p.notna().to_numpy()
    tf = f[test].reset_index(drop=True)
    yt = {k: a[test] for k, a in y.items()}
    once = bt.raw_probs(tf, best_cfg, "once")
    piy = bt.raw_probs(tf, best_cfg, "piyasa")
    nocal = {k: v[test] for k, v in raw_nocal.items()}
    son = {k: v[test] for k, v in cal.items()}
    ht = yt["ht_ok"]
    variants = (("once", once), ("piyasa", piy), ("sonra_kalibrasyonsuz", nocal), ("sonra", son))

    markets = {}
    markets["iyms"] = _market_block("İY/MS", {k: d["htft"][ht] for k, d in variants}, yt["htft"][ht], list(ym.HTFT_LABELS))
    markets["skor"] = _market_block("Kesin skor", {k: d["ft"] for k, d in variants}, yt["ft"], FT_LABELS)
    markets["iy_skor"] = _market_block("İY skoru", {k: d["ht"][ht] for k, d in variants}, yt["ht"][ht], HT_LABELS)
    markets["kg2"] = _market_block("2. yarı KG Var", {k: d["kg2"][ht] for k, d in variants}, yt["kg2"][ht], None)

    # alt kümeler: lig x pazar
    subsets = []
    divs = tf.Division.to_numpy()
    ykey = {"iyms": yt["htft"], "skor": yt["ft"], "iy_skor": yt["ht"], "kg2": yt["kg2"]}
    for key, pk, msk in (("iyms", "htft", ht), ("skor", "ft", np.ones(len(tf), bool)), ("iy_skor", "ht", ht), ("kg2", "kg2", ht)):
        yk = ykey[key]
        for d in np.unique(divs):
            s = msk & (divs == d)
            if s.sum() < args.min_subset:
                continue
            l_s = bt.per_row_ll(son[pk][s], yk[s])
            l_p = bt.per_row_ll(piy[pk][s], yk[s])
            l_o = bt.per_row_ll(once[pk][s], yk[s])
            dp, do = bt.paired_delta(l_p, l_s), bt.paired_delta(l_o, l_s)
            e_s, e_p = bt.ece(son[pk][s], yk[s]), bt.ece(piy[pk][s], yk[s])
            subsets.append({"pazar": key, "lig": d, "n": int(s.sum()), "sonra_vs_piyasa": dp, "sonra_vs_once": do,
                            "ece_sonra": e_s, "ece_piyasa": e_p,
                            "guvenilir": bool(dp["fark"] < 0 and dp["t"] <= -2.0 and e_s <= e_p)})
    sel = []
    sel += _selection_reliability("İY/MS", son["htft"][ht], yt["htft"][ht], list(ym.HTFT_LABELS))
    sel += _selection_reliability("Skor", son["ft"], yt["ft"], FT_LABELS)
    sel += _selection_reliability("İY skoru", son["ht"][ht], yt["ht"][ht], HT_LABELS)

    # canlı parametreler (son ay itibarıyla)
    last_rows = f.sort_values("MatchDate").groupby("Division").tail(1)
    shares = {r.Division: round(float(r.s_lig), 4) for r in last_rows.itertuples() if np.isfinite(r.s_lig)}
    shares["_genel"] = round(float(np.nanmedian(list(shares.values()))), 4) if shares else ym.DEFAULT_FIRST_HALF_SHARE
    params = {
        "olusturma": str(date.today()), "kaynak": "scripts/yuksek_oran_pazarlar.py backtest",
        "not": "Analiz katmanı; banko kupona girmez (KURALLAR.md).",
        "hiperparametre": {"half_life": best_hl, "w_market": best_cfg.w_market, "gamma_team": best_cfg.gamma_team,
                           "rho_iy": best_cfg.rho_iy, "rho_2y": best_cfg.rho_2y},
        "durum_carpani": {"ev": gs_last.get("ev", [1, 1, 1]), "dep": gs_last.get("dep", [1, 1, 1])},
        "kalibrasyon": cal_last, "lig_iy_payi": shares,
    }
    res = {"tarih": str(date.today()), "dogrulama": [val_a, val_b], "test_baslangic": test_a,
           "yari_omur_secimi": {str(k): v for k, v in hl_scores.items()}, "izgara": grid_rows,
           "secilen": params["hiperparametre"], "durum_carpani": params["durum_carpani"],
           "pazarlar": markets, "alt_kumeler": subsets, "secim_guvenilirligi": sel,
           "roi": "Hesaplanamadı: data/matches.csv'de yalnız 1X2 ve 2.5 Alt/Üst oranı var; İY/MS, skor, İY skoru, "
                  "2Y KG oranı yok. Uydurma ROI yazılmadı."}
    out_dir = ROOT / "reports" / "research"
    stamp = args.stamp or str(date.today())
    (out_dir / f"yuksek_oran_pazarlar_{stamp}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    ym.PARAMS_PATH.write_text(json.dumps(params, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / f"yuksek_oran_pazarlar_{stamp}.md").write_text(render_md(res), encoding="utf-8")
    print(render_md(res))


def render_md(res: dict) -> str:
    L = [f"# Yüksek oranlı pazarlar — sızıntısız ileri-yürüyen test ({res['tarih']})", "",
         ("Analiz katmanı: **banko kupona girmez** (KURALLAR.md, İY/MS-skor-KG yasak). Günlük akışta yok; yalnız "
          "`scripts/yuksek_oran_pazarlar.py` açıkça çalıştırılınca."), "",
         (f"- Doğrulama (hiperparametre seçimi): {res['dogrulama'][0]} – {res['dogrulama'][1]}; "
          f"**test: {res['test_baslangic']} sonrası** (son 2+ sezon). Takım oranları her hafta yalnız o tarihten önceki "
          "maçlarla; kalibrasyon her ay yalnız önceki ayların örneklem-dışı tahminleriyle."),
         f"- Seçilen: {res['secilen']}",
         (f"- Devre-arası durum çarpanları (2Y gol, [ev önde, eşit, ev geride]): ev {res['durum_carpani']['ev']}, "
          f"dep {res['durum_carpani']['dep']}"),
         ("- **önce** = depodaki eski analitik taban (takım oranı λ, sabit %44.4 İY payı, bağımsız Poisson, kalibrasyon "
          "yok). **piyasa** = 1X2 + 2.5 Alt/Üst oranlarından ters çevrilmiş λ ile aynı "
          "taban (bu pazarların gerçek piyasa fiyatı arşivde yok). **sonra** = yeni model."), "",
         "## Pazar özeti (test)", "",
         "| Pazar | n | log-loss önce | piyasa | sonra | Brier önce → sonra | ECE önce → sonra | sonra−piyasa (t) |",
         "|---|---|---|---|---|---|---|---|"]
    for m in res["pazarlar"].values():
        md = m["modeller"]
        o, s, p = md["once"], md["sonra"], md.get("piyasa")
        fp = m.get("fark", {}).get("sonra-piyasa")
        L.append(f"| {m['pazar']} | {s['n']} | {o['logloss']:.4f} | " + (f"{p['logloss']:.4f}" if p else "—")
                 + f" | {s['logloss']:.4f} | {o['brier']:.4f} → {s['brier']:.4f} | {o['ece']:.4f} → {s['ece']:.4f} | "
                 + (f"{fp['fark']:+.4f} ({fp['t']})" if fp else "—") + " |")
    L += ["", "## İY/MS: tahmin vs gerçek frekans (test)", "", "| Seçim | önce | piyasa | sonra | gerçek |", "|---|---|---|---|---|"]
    md = res["pazarlar"]["iyms"]["modeller"]
    for i, row in enumerate(md["sonra"]["secim_frekans"]):
        L.append(f"| {row['secim']} | {md['once']['secim_frekans'][i]['tahmin']:.4f} | {md['piyasa']['secim_frekans'][i]['tahmin']:.4f} | "
                 f"{row['tahmin']:.4f} | {row['gercek']:.4f} |")
    L += ["", "## Kesin skor: tahmin vs gerçek (test, en sık 12)", "", "| Skor | önce | piyasa | sonra | gerçek |", "|---|---|---|---|---|"]
    md = res["pazarlar"]["skor"]["modeller"]
    rows = sorted(range(len(md["sonra"]["secim_frekans"])), key=lambda i: -md["sonra"]["secim_frekans"][i]["gercek"])[:12]
    for i in rows:
        r = md["sonra"]["secim_frekans"][i]
        L.append(f"| {r['secim']} | {md['once']['secim_frekans'][i]['tahmin']:.4f} | {md['piyasa']['secim_frekans'][i]['tahmin']:.4f} | "
                 f"{r['tahmin']:.4f} | {r['gercek']:.4f} |")
    L += ["", "## Kalibrasyon tablosu (sonra, test; çok sınıflılarda hücreler havuzlanmış)", ""]
    for k in ("iyms", "skor", "iy_skor", "kg2"):
        m = res["pazarlar"][k]
        L.append(f"**{m['pazar']}**: " + "; ".join(f"{r['bant']} n={r['n']} tahmin {r['tahmin']:.3f} / gerçek {r['gercek']:.3f}"
                                                for r in m["modeller"]["sonra"]["kalibrasyon"]))
        L.append("")
    good = [s for s in res["alt_kumeler"] if s["guvenilir"]]
    L += ["## Güvenilir alt kümeler (lig × pazar)", "",
          ("Ölçüt: test n ≥ eşik, sonra log-loss'u kıyas modelinden (piyasa türevi) anlamlı düşük "
           "(t ≤ −2) ve kalibrasyon hatası (ECE) da düşük."), ""]
    if good:
        L += ["| Pazar | Lig | n | log-loss farkı | t |", "|---|---|---|---|---|"]
        for s in sorted(good, key=lambda s: (s["pazar"], s["lig"])):
            d = s.get("sonra_vs_piyasa") or s["sonra_vs_once"]
            L.append(f"| {s['pazar']} | {s['lig']} | {s['n']} | {d['fark']:+.4f} | {d['t']} |")
    else:
        L.append("Hiçbir lig-pazar kombinasyonu ölçütü geçmedi.")
    sel = [r for r in res["secim_guvenilirligi"] if r["tahmin"] < 0.35 and r["n"] >= 100 and r["secim"] != "diğer"]
    trusted = [r for r in sel if abs(r["z"]) < 2]
    L += ["", "## Yüksek oranlı seçimlerde kalibrasyon (sonra, test)", "",
          ("Model bir seçime bu bantta olasılık verdiğinde gerçekte ne kadar çıktı. |z| < 2 ise olasılık güvenilir; "
           "'adil oran' = 1/olasılık. Nesine oranı bunun **üstündeyse** değer olabilir; altındaysa yok."), "",
          "| Pazar | Seçim | Bant | n | tahmin | gerçek | z | adil oran |", "|---|---|---|---|---|---|---|---|"]
    for r in sel:
        L.append(f"| {r['pazar']} | {r['secim']} | {r['bant']} | {r['n']} | {r['tahmin']:.3f} | {r['gercek']:.3f} | {r['z']} | {r['adil_oran']} |")
    L += ["", f"Güvenilir (|z| < 2, n ≥ 100) yüksek oran seçim bandı: {len(trusted)} / {len(sel)}.", "",
          "## ROI", "", res["roi"],
          "Bu pazarlarda bahis şirketi kesintisi 1X2'den genelde yüksektir; kalibre olasılık tek başına kâr garantisi değildir.", ""]
    return "\n".join(L)


def tahmin(args: argparse.Namespace) -> None:
    params = ym.load_params()
    if not params:
        sys.exit("Önce: python scripts/yuksek_oran_pazarlar.py backtest")
    hp = params["hiperparametre"]
    df = bt.load_matches()
    div = args.lig
    tr = df[(df.Division == div) & (df.MatchDate >= df.MatchDate.max() - pd.Timedelta(days=3 * 365))]
    lam = mu = sh = sa = None
    if len(tr) >= 150:
        age = (df.MatchDate.max() - tr.MatchDate).dt.days.to_numpy(float)
        w = 0.5 ** (age / hp["half_life"])
        H, A = tr.HomeTeam.to_numpy(), tr.AwayTeam.to_numpy()
        ft = ym.fit_maher(H, A, tr.FTHome.to_numpy(float), tr.FTAway.to_numpy(float), w)
        lam, mu = ft.expect(args.ev, args.dep)
        h = tr.HTHome.notna().to_numpy()
        if h.sum() >= 150:
            t2 = tr[h]
            f1 = ym.fit_maher(H[h], A[h], t2.HTHome.to_numpy(float), t2.HTAway.to_numpy(float), w[h], 6.0)
            f2 = ym.fit_maher(H[h], A[h], (t2.FTHome - t2.HTHome).to_numpy(float), (t2.FTAway - t2.HTAway).to_numpy(float), w[h], 6.0)
            a1, b1 = f1.expect(args.ev, args.dep)
            a2, b2 = f2.expect(args.ev, args.dep)
            sh, sa = a1 / (a1 + a2), b1 / (b1 + b2)
    if args.oran:
        p = ym.devig(np.array([args.oran]))
        po = ym.devig(np.array([args.ust_alt]))[:, 0] if args.ust_alt else None
        lp, mp = ym.MarketInverter().invert(p[:, 0], p[:, 2], po)
        if lam is None:
            lam, mu = float(lp[0]), float(mp[0])
        else:
            wm = hp["w_market"]
            lam = float(np.exp(wm * np.log(lp[0]) + (1 - wm) * np.log(lam)))
            mu = float(np.exp(wm * np.log(mp[0]) + (1 - wm) * np.log(mu)))
    if lam is None:
        sys.exit("Bu lig için arşiv yok ve oran verilmedi.")
    out = ym.predict_markets(lam, mu, division=div, team_share_h=sh, team_share_a=sa, params=params)
    print(f"{args.ev} - {args.dep} ({div}) λ={lam:.2f} μ={mu:.2f}  [analiz; banko kupona girmez]")
    for grp, sel in out.items():
        print(f"\n{grp}:")
        for k, v in sorted(sel.items(), key=lambda kv: -kv[1])[: args.top]:
            print(f"  {k:<22} P={v:6.1%}  adil oran {1 / max(v, 1e-6):6.2f}")
    if args.json:
        print(json.dumps(out, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backtest")
    b.add_argument("--half-lives", default="120,240,400")
    b.add_argument("--val-from", default="2022-07-01")
    b.add_argument("--test-from", default="2024-07-01")
    b.add_argument("--cal-from", default="2019-07-01")
    b.add_argument("--min-subset", type=int, default=300)
    b.add_argument("--cache", default="", help="özellik önbellek klasörü (repo dışı)")
    b.add_argument("--stamp", default="")
    t = sub.add_parser("tahmin")
    t.add_argument("--lig", required=True, help="football-data bölüm kodu, ör. E0, T1, SP1")
    t.add_argument("--ev", required=True)
    t.add_argument("--dep", required=True)
    t.add_argument("--oran", nargs=3, type=float, metavar=("MS1", "MS0", "MS2"))
    t.add_argument("--ust-alt", nargs=2, type=float, metavar=("UST25", "ALT25"))
    t.add_argument("--top", type=int, default=6)
    t.add_argument("--json", action="store_true")
    args = ap.parse_args()
    {"backtest": backtest, "tahmin": tahmin}[args.cmd](args)


if __name__ == "__main__":
    main()
