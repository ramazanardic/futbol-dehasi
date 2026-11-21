"""Bahis aileleri: her Nesine pazar ailesinin arşivde walk-forward kalibrasyonu ve oran karşılaştırması.

    python scripts/bahis_aileleri_kalibrasyon.py onbellek [--limit N] [--isci 6]   # arşivi üretim hattıyla fiyatla
    python scripts/bahis_aileleri_kalibrasyon.py analiz [--yaz]                     # güvenilirlik, ECE, LL, CI, ROI
    QF_AILE_VARYANT=ham python scripts/bahis_aileleri_kalibrasyon.py onbellek       # eski hat (tırmıksız) — karşılaştırma
    python scripts/bahis_aileleri_kalibrasyon.py karsilastir ham ""                # iki önbelleği eşli karşılaştır

Fiyatlama = scripts/nesine_global.price_event hattı: marjsız (power) 1X2 + 2.5 Alt/Üst → fund_weight=0 gol oranları
→ (üretim) skor matrisi kotasyonlara tırmıklanır → compute_omni_markets ortak tensörü → goal_probability.
Türev her seçim aynı tensörden gelir (tutarlı). Sonuç (y) aynı ayrıştırıcıyla, gerçekleşen İY/2Y skorundan
tek-sıcak tensörle hesaplanır → fiyat ile hesaplaşma aynı tanımı kullanır.

Walk-forward: her test sezonu (Temmuz–Haziran) için kalibratör yalnız ÖNCEKİ sezonlarla kurulur (sızıntı yok).
Bir kalibratör yalnız test log-loss farkının %95 bootstrap güven aralığının ÜST ucu < 0 ise tutulur.

Arşiv oranları (data/matches.csv): ortalama büro (AvgH/Avg>2.5, yoksa B365) + en iyi fiyat (MaxH/Max>2.5) +
ortalama Asya handikabı (AvgAHH/AHA). Diğer ailelerin arşivde oranı yok → yalnız kalibrasyon, ROI yok.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):  # one BLAS thread per worker process
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

VARIANT = os.environ.get("QF_AILE_VARYANT", "")  # "" = production pipeline, "ham" = pre-21-Nov (no raking)
RESEARCH = ROOT / "reports" / "research"
OUT_JSON = RESEARCH / "bahis_aileleri_kalibrasyon.json"
CAL_FILE = ROOT / "data" / "calibration" / "market_calibration.json"
START = "2011-07-01"
FIRST_TEST = 2016
G = 8  # joint grid per half (0..7 goals per team per half)


def cache_path(variant: str = VARIANT) -> Path:
    return RESEARCH / f"backtest_cache_bahis_aileleri{('_' + variant) if variant else ''}.npz"  # .gitignore: backtest_cache*


FAMILIES: dict[str, list[str]] = {
    "Maç Sonucu": ["MS 1", "MS 0", "MS 2"],
    "Çifte Şans": ["ÇŞ 1X", "ÇŞ 12", "ÇŞ X2"],
    "Alt/Üst": ["0.5 Üst", "1.5 Üst", "2.5 Üst", "3.5 Üst", "4.5 Üst", "5.5 Üst"],
    "Karşılıklı Gol": ["KG Var"],
    "İY Sonucu": ["İY 1", "İY 0", "İY 2", "İY ÇŞ 1X", "İY ÇŞ X2"],
    "İY Alt/Üst": ["İY 0.5 Üst", "İY 1.5 Üst", "İY 2.5 Üst"],
    "2Y Sonucu / Alt-Üst": ["2Y 1", "2Y 0", "2Y 2", "2Y 0.5 Üst", "2Y 1.5 Üst"],
    "İY/MS": [f"İY/MS {a}/{b}" for a in "102" for b in "102"],
    "Handikap (Avrupa)": ["Hnd(-1) 1", "Hnd(-1) 0", "Hnd(-1) 2", "Hnd(+1) 1", "Hnd(+1) 0", "Hnd(+1) 2",
                          "Hnd(-2) 1", "Hnd(-2) 0", "Hnd(-2) 2"],
    "Toplam Gol Aralığı": ["0-1 Gol", "2-3 Gol", "4-5 Gol", "6+ Gol"],
    "Tek/Çift": ["Tek", "İY Tek"],
    "Doğru Skor": [f"Skor {i}-{j}" for i, j in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1), (1, 2), (2, 2),
                                                  (3, 0), (3, 1), (1, 3), (0, 3))]
                  + ["İY Skor 0-0", "İY Skor 1-0", "İY Skor 0-1", "İY Skor 1-1"],
    "Takım Golleri": ["Ev 0.5 Üst", "Ev 1.5 Üst", "Ev 2.5 Üst", "Dep 0.5 Üst", "Dep 1.5 Üst", "Dep 2.5 Üst",
                      "Ev İY 0.5 Üst", "Ev İY 1.5 Üst", "Dep İY 0.5 Üst", "Dep İY 1.5 Üst"],
    "Yarı KG": ["İY KG Var", "2Y KG Var", "İki Yarıda KG Var"],
    "Yarı Özel": ["Ev İki Yarıda Gol", "Dep İki Yarıda Gol", "Ev Her İki Yarıyı Kazanır", "Dep Her İki Yarıyı Kazanır",
                  "Ev En Az Bir Yarıyı Kazanır", "Dep En Az Bir Yarıyı Kazanır", "En Çok Gol 1Y", "En Çok Gol 2Y",
                  "En Çok Gol Eşit", "Ev En Çok Gol 1Y", "Ev En Çok Gol 2Y", "Dep En Çok Gol 1Y", "Dep En Çok Gol 2Y"],
    "Fark": ["Fark Ev 1", "Fark Ev 2", "Fark Ev 3+", "Fark 0", "Fark Dep 1", "Fark Dep 2", "Fark Dep 3+"],
    "Kombine": ["MS 1 & 2.5 Üst", "MS 1 & 2.5 Alt", "MS 2 & 2.5 Üst", "MS 2 & 2.5 Alt", "MS 0 & 2.5 Alt",
                "MS 1 & KG Var", "MS 1 & KG Yok", "MS 2 & KG Var", "MS 2 & KG Yok", "MS 0 & KG Var",
                "2.5 Üst & KG Var", "2.5 Üst & KG Yok", "2.5 Alt & KG Var", "2.5 Alt & KG Yok",
                "MS 1 & 1.5 Üst", "MS 1 & 3.5 Üst", "MS 2 & 1.5 Üst", "İY 1 & İY KG Yok", "İY 0 & İY KG Yok",
                "İY 1 & İY 1.5 Alt", "İY 0 & İY 1.5 Alt"],
}
DIRECT = {"MS 1", "MS 0", "MS 2", "ÇŞ 1X", "ÇŞ 12", "ÇŞ X2", "2.5 Üst"}  # pricing inputs (quoted by the reference)
SELECTIONS: list[str] = [s for v in FAMILIES.values() for s in v]
FAMILY_OF = {s: f for f, v in FAMILIES.items() for s in v}

_MASKS: np.ndarray | None = None


def masks() -> np.ndarray:
    """(n_sel, G**4) boolean event masks on the joint state space (same parser as production)."""
    global _MASKS
    if _MASKS is None:
        from quantfoot.markets.goal_markets import GoalGrid, goal_event_mask

        g = GoalGrid(np.ones((G, G, G, G)))
        _MASKS = np.stack([goal_event_mask(s, g) for s in SELECTIONS])
    return _MASKS


def _season(d: pd.Timestamp) -> int:
    return d.year if d.month >= 7 else d.year - 1


def _price(task: tuple) -> tuple | None:
    from quantfoot.markets import tail_goals
    from quantfoot.markets.devig import devig
    from quantfoot.markets.goal_markets import asian_handicap
    from quantfoot.markets.omni_markets import compute_omni_markets

    div, oh, od, oa, ov, un, ah_line = task
    try:
        p1x2 = devig([oh, od, oa], method="power").probabilities
        p_ov = float(devig([ov, un], method="power").probabilities[0])
        nu, alpha, kappa = tail_goals.league_tail_regime(div.lower())
        mu_h, mu_a, mat = tail_goals.fit_tail_rates_from_markets(
            p_1x2=p1x2, ou_line=2.5, p_over=p_ov, seed_rates=(1.45, 1.15), alpha_nb=alpha, shared_kappa=kappa,
            com_nu=nu, fund_weight=0.0)
        ft = None
        if VARIANT != "ham":
            ft = tail_goals.rake_score_matrix_to_markets(mat, p_1x2=p1x2, ou_lines=[(2.5, p_ov)])
        joint = compute_omni_markets(mu_h, mu_a, league=div.lower(), ft_matrix=ft).joint
        flat = joint.ravel() / joint.sum()
        probs = masks().astype(float) @ flat
        # production overrides the quoted selections with the devigged reference itself (nesine_global.exact_direct)
        direct = {"MS 1": p1x2[0], "MS 0": p1x2[1], "MS 2": p1x2[2], "ÇŞ 1X": p1x2[0] + p1x2[1],
                  "ÇŞ 12": p1x2[0] + p1x2[2], "ÇŞ X2": p1x2[1] + p1x2[2], "2.5 Üst": p_ov}
        for k, v in direct.items():
            probs[SELECTIONS.index(k)] = v
        ah = [np.nan] * 8
        if np.isfinite(ah_line):
            o_h = asian_handicap(joint, float(ah_line), "Ev")
            o_a = asian_handicap(joint, -float(ah_line), "Dep")
            ah = [o_h.win, o_h.half_win, o_h.push, o_h.half_lose, o_a.win, o_a.half_win, o_a.push, o_a.half_lose]
        return probs.astype(np.float32), np.array([mu_h, mu_a, *ah], dtype=np.float32)
    except Exception:  # noqa: BLE001 — a failed fit just drops the match
        return None


def load_archive() -> pd.DataFrame:
    from quantfoot.data.loader import normalize_quarter_handicap

    cols = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "OddHome", "OddDraw", "OddAway", "Over25", "Under25",
            "MaxHome", "MaxDraw", "MaxAway", "MaxOver25", "MaxUnder25", "HandiSize", "HandiHome", "HandiAway",
            "FTHome", "FTAway", "HTHome", "HTAway"]
    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False, parse_dates=["MatchDate"], usecols=cols)
    need = ["OddHome", "OddDraw", "OddAway", "Over25", "Under25", "FTHome", "FTAway", "HTHome", "HTAway"]
    df = df.dropna(subset=need)
    df = df[(df[["OddHome", "OddDraw", "OddAway", "Over25", "Under25"]] > 1.0).all(axis=1) & (df.MatchDate >= START)]
    h2 = df.FTHome - df.HTHome
    a2 = df.FTAway - df.HTAway
    ok = (df.HTHome >= 0) & (df.HTAway >= 0) & (h2 >= 0) & (a2 >= 0) & (df[["HTHome", "HTAway"]].max(axis=1) < G) & (
        pd.concat([h2, a2], axis=1).max(axis=1) < G)
    df = df[ok].sort_values(["MatchDate", "Division", "HomeTeam"]).reset_index(drop=True)
    df["AH"] = normalize_quarter_handicap(df["HandiSize"])
    return df


def cmd_cache(args: argparse.Namespace) -> None:
    df = load_archive()
    if args.limit:
        df = df.iloc[-args.limit:].reset_index(drop=True)
    tasks = list(df[["Division", "OddHome", "OddDraw", "OddAway", "Over25", "Under25", "AH"]].itertuples(index=False, name=None))
    with ProcessPoolExecutor(max_workers=args.isci) as pool:
        out = list(pool.map(_price, tasks, chunksize=300))
    keep = np.array([o is not None for o in out])
    P = np.stack([o[0] for o in out if o is not None])
    X = np.stack([o[1] for o in out if o is not None])
    d = df[keep].reset_index(drop=True)
    h1, a1 = d.HTHome.to_numpy(int), d.HTAway.to_numpy(int)
    h2, a2 = d.FTHome.to_numpy(int) - h1, d.FTAway.to_numpy(int) - a1
    state = ((h1 * G + a1) * G + h2) * G + a2
    Y = masks()[:, state].T.astype(np.int8)
    np.savez_compressed(
        cache_path(), P=P, X=X, Y=Y, sel=np.array(SELECTIONS), div=d.Division.to_numpy(str),
        date=d.MatchDate.dt.strftime("%Y-%m-%d").to_numpy(str),
        odds=d[["OddHome", "OddDraw", "OddAway", "Over25", "Under25", "MaxHome", "MaxDraw", "MaxAway", "MaxOver25",
                "MaxUnder25", "AH", "HandiHome", "HandiAway"]].to_numpy(float),
        goals=d[["HTHome", "HTAway", "FTHome", "FTAway"]].to_numpy(int))
    print(f"{int(keep.sum())} / {len(df)} maç fiyatlandı -> {cache_path()}")


# ------------------------------------------------------------------------------------------ metrics
def ll_vec(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def ece(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Equal-width 10-bin expected calibration error."""
    b = np.minimum((p * bins).astype(int), bins - 1)
    return float(sum(abs(p[b == k].mean() - y[b == k].mean()) * (b == k).mean() for k in range(bins) if (b == k).any()))


def ece_q(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    """Equal-mass (decile) ECE — meaningful for rare events whose p all sit in one equal-width bin."""
    parts = np.array_split(np.argsort(p), bins)
    return float(sum(abs(p[i].mean() - y[i].mean()) * len(i) for i in parts if len(i)) / len(p))


def reliability(p: np.ndarray, y: np.ndarray, bins: int = 5) -> list[list[float]]:
    return [[round(float(p[i].mean()), 4), round(float(y[i].mean()), 4), len(i)] for i in np.array_split(np.argsort(p), bins)]


def boot_ci(a: np.ndarray, n: int = 500, seed: int = 11) -> tuple[float, float]:
    """95 % bootstrap CI of the mean (match-level resampling)."""
    rng = np.random.default_rng(seed)
    means = np.empty(n)
    for k in range(n):
        means[k] = a[rng.integers(0, len(a), len(a))].mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _wf_one(job: tuple) -> dict:
    """Walk-forward for one selection: raw vs Platt (global) vs Platt + shrunk league offsets."""
    from quantfoot.markets.market_calibration import (
        apply_platt_league,
        fit_platt_league,
    )

    name, p, y, div, season = job
    pr, pg, pl, yy = [], [], [], []
    for s in sorted(s for s in np.unique(season) if s >= FIRST_TEST):
        tr, te = season < s, season == s
        if te.sum() == 0 or tr.sum() < 2000:
            continue
        g = fit_platt_league(p[tr], y[tr], div[tr], league_l2=None)
        lg = fit_platt_league(p[tr], y[tr], div[tr], league_l2=200.0)
        pr.append(p[te])
        pg.append(apply_platt_league(g, p[te]))
        pl.append(apply_platt_league(lg, p[te], div[te]))
        yy.append(y[te])
    P0, PG, PL, Y = (np.concatenate(v) for v in (pr, pg, pl, yy))
    d_g = ll_vec(PG, Y) - ll_vec(P0, Y)
    d_l = ll_vec(PL, Y) - ll_vec(P0, Y)
    ci_g, ci_l = boot_ci(d_g), boot_ci(d_l)
    base = float(Y.mean())
    res = {
        "secim": name, "aile": FAMILY_OF[name], "n": len(Y), "gercek": round(base, 4),
        "ort_tahmin": round(float(P0.mean()), 4),
        "ll_ham": round(float(ll_vec(P0, Y).mean()), 5), "ll_platt": round(float(ll_vec(PG, Y).mean()), 5),
        "ll_platt_lig": round(float(ll_vec(PL, Y).mean()), 5),
        "ll_taban": round(float(ll_vec(np.full_like(P0, base), Y).mean()), 5),
        "ece_ham": round(ece(P0, Y), 4), "ece_platt": round(ece(PG, Y), 4), "ece_platt_lig": round(ece(PL, Y), 4),
        "eceq_ham": round(ece_q(P0, Y), 4), "eceq_platt": round(ece_q(PG, Y), 4), "eceq_platt_lig": round(ece_q(PL, Y), 4),
        "d_platt": round(float(d_g.mean()), 6), "ci_platt": [round(c, 6) for c in ci_g],
        "d_platt_lig": round(float(d_l.mean()), 6), "ci_platt_lig": [round(c, 6) for c in ci_l],
        "guvenilirlik_ham": reliability(P0, Y), "guvenilirlik_platt": reliability(PG, Y),
    }
    # keep rule: CI upper < 0; the league curve only when it is better than the global one AND significant
    keep = None
    if ci_g[1] < 0:
        keep = "platt"
    if ci_l[1] < 0 and (keep is None or d_l.mean() < d_g.mean()):
        keep = "platt_lig"
    res["tutulan"] = keep
    if keep:  # final curve on ALL seasons (production)
        res["egri"] = fit_platt_league(p, y, div, league_l2=200.0 if keep == "platt_lig" else None)
    return res


def roi_table(p: np.ndarray, odds: np.ndarray, won: np.ndarray, thresholds=(0.0, 0.02, 0.03, 0.05, 0.08)) -> list[dict]:
    out = []
    ev = p * odds - 1.0
    for t in thresholds:
        m = (ev >= t) & np.isfinite(odds) & (odds > 1.0) & (ev < 0.25)
        if m.sum() < 30:
            out.append({"esik": t, "n": int(m.sum())})
            continue
        prof = np.where(won[m], odds[m] - 1.0, -1.0)
        lo, hi = boot_ci(prof, n=400)
        out.append({"esik": t, "n": int(m.sum()), "roi": round(float(prof.mean()), 4), "ci": [round(lo, 4), round(hi, 4)],
                    "ort_oran": round(float(odds[m].mean()), 3)})
    return out


def _load(variant: str) -> dict:
    z = np.load(cache_path(variant), allow_pickle=False)
    out = {k: z[k] for k in z.files}
    out["season"] = np.array([_season(d) for d in pd.to_datetime(out["date"])])
    return out


def cmd_analyze(args: argparse.Namespace) -> None:
    from quantfoot.markets.goal_markets import _asian_outcome

    z = _load(VARIANT)
    P, X, Y, sel, div, season = z["P"].astype(float), z["X"].astype(float), z["Y"].astype(float), list(z["sel"]), z["div"], z["season"]
    odds, goals = z["odds"], z["goals"]
    jobs = [(s, P[:, i], Y[:, i], div, season) for i, s in enumerate(sel) if s in SELECTIONS]
    with ProcessPoolExecutor(max_workers=args.isci) as pool:
        rows = list(pool.map(_wf_one, jobs))
    oos = season >= FIRST_TEST
    roi: dict[str, dict] = {}
    i = {s: k for k, s in enumerate(sel)}
    for s, col in (("MS 1", 5), ("MS 0", 6), ("MS 2", 7), ("2.5 Üst", 8)):
        roi[f"{s} (en iyi fiyat)"] = {"esikler": roi_table(P[oos, i[s]], odds[oos, col], Y[oos, i[s]] > 0)}
    roi["2.5 Alt (en iyi fiyat)"] = {"esikler": roi_table(1 - P[oos, i["2.5 Üst"]], odds[oos, 9], Y[oos, i["2.5 Üst"]] == 0)}
    # Asian handicap: DERIVED (joint) price vs the archive's average AH price — the one derived family with real odds
    ah_line, hh, ha = odds[:, 10], odds[:, 11], odds[:, 12]
    fh, fa = goals[:, 2], goals[:, 3]
    m_ah = oos & np.isfinite(ah_line) & np.isfinite(hh) & np.isfinite(ha) & (hh > 1) & (ha > 1)
    real = np.zeros((len(P), 8))
    for k in np.where(m_ah)[0]:
        oh_ = _asian_outcome(np.array([float(fh[k] - fa[k])]), np.array([1.0]), float(ah_line[k]))
        oa_ = _asian_outcome(np.array([float(fa[k] - fh[k])]), np.array([1.0]), -float(ah_line[k]))
        real[k] = [oh_.win, oh_.half_win, oh_.push, oh_.half_lose, oa_.win, oa_.half_win, oa_.push, oa_.half_lose]
    ah_rows = {}
    for side, off, oc in (("Ev", 2, hh), ("Dep", 6, ha)):
        w, hw, pu, hl = (X[:, off + j] for j in range(4))
        gain, loss = w + 0.5 * hw, (1 - w - hw - pu - hl) + 0.5 * hl
        ev = gain * (oc - 1) - loss
        rw, rhw, rpu, rhl = (real[:, off - 2 + j] for j in range(4))
        prof = rw * (oc - 1) + rhw * 0.5 * (oc - 1) - rhl * 0.5 - (1 - rw - rhw - rpu - rhl)
        tab = []
        for t in (0.0, 0.02, 0.03, 0.05, 0.08):
            mm = m_ah & (ev >= t) & (ev < 0.25)
            if mm.sum() < 30:
                tab.append({"esik": t, "n": int(mm.sum())})
                continue
            lo, hi = boot_ci(prof[mm], n=400)
            tab.append({"esik": t, "n": int(mm.sum()), "roi": round(float(prof[mm].mean()), 4), "ci": [round(lo, 4), round(hi, 4)],
                        "ort_oran": round(float(oc[mm].mean()), 3)})
        ah_rows[side] = {"n": int(m_ah.sum()), "beklenen_kazanc_payi": round(float(np.mean(gain[m_ah])), 4),
                         "gercek_kazanc_payi": round(float(np.mean(rw[m_ah] + 0.5 * rhw[m_ah])), 4), "esikler": tab}
    roi["Asya Handikabı (türev fiyat vs ort. AH oranı)"] = ah_rows
    out = {"varyant": VARIANT or "uretim", "n_mac": len(P), "n_test": int(oos.sum()), "test_sezonlari": f"{FIRST_TEST}/{FIRST_TEST + 1}+",
           "ah_ortalama_marj": round(float(np.nanmean(1 / hh[m_ah] + 1 / ha[m_ah] - 1)), 4), "secimler": rows, "roi": roi}
    target = OUT_JSON if not VARIANT else OUT_JSON.with_name(f"bahis_aileleri_kalibrasyon_{VARIANT}.json")
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} seçim, tutulan kalibratör: {sum(1 for r in rows if r['tutulan'])} -> {target}")
    for r in rows:
        print(f"{r['aile'][:18]:18} {r['secim'][:22]:22} n={r['n']} y={r['gercek']:.3f} p={r['ort_tahmin']:.3f} "
              f"ECE {r['ece_ham']:.4f}->{r['ece_platt']:.4f} dLL {r['d_platt']:+.6f} {r['ci_platt']} lig {r['d_platt_lig']:+.6f} "
              f"{r['ci_platt_lig']} -> {r['tutulan']}")
    print(json.dumps(roi, ensure_ascii=False))
    if args.yaz:
        write_calibration(rows)


def cmd_compare(args: argparse.Namespace) -> None:
    """Paired per-selection log-loss difference new − old on the same matches (test seasons), 95 % bootstrap CI."""
    old, new = _load(args.eski), _load(args.yeni)
    if len(old["date"]) != len(new["date"]) or not (old["date"] == new["date"]).all():
        raise SystemExit("önbellekler aynı maçları içermiyor")
    oos = new["season"] >= FIRST_TEST
    rows = []
    for k, s in enumerate(new["sel"]):
        y = new["Y"][oos, k].astype(float)
        d = ll_vec(new["P"][oos, k].astype(float), y) - ll_vec(old["P"][oos, k].astype(float), y)
        lo, hi = boot_ci(d)
        rows.append({"secim": str(s), "aile": FAMILY_OF.get(str(s), "?"), "gercek": round(float(y.mean()), 4),
                     "eski_ort": round(float(old["P"][oos, k].mean()), 4), "yeni_ort": round(float(new["P"][oos, k].mean()), 4),
                     "ece_eski": round(ece(old["P"][oos, k].astype(float), y), 4), "ece_yeni": round(ece(new["P"][oos, k].astype(float), y), 4),
                     "d_ll": round(float(d.mean()), 6), "ci": [round(lo, 6), round(hi, 6)],
                     "karar": "iyi" if hi < 0 else ("kötü" if lo > 0 else "fark yok")})
        r = rows[-1]
        print(f"{r['aile'][:18]:18} {r['secim'][:22]:22} y={r['gercek']:.4f} {r['eski_ort']:.4f}->{r['yeni_ort']:.4f} "
              f"ECE {r['ece_eski']:.4f}->{r['ece_yeni']:.4f} dLL {r['d_ll']:+.6f} {r['ci']} {r['karar']}")
    tot = sum(r["d_ll"] for r in rows)
    print(f"iyi {sum(r['karar'] == 'iyi' for r in rows)} / kötü {sum(r['karar'] == 'kötü' for r in rows)} / "
          f"fark yok {sum(r['karar'] == 'fark yok' for r in rows)}; toplam dLL {tot:+.6f}")
    (RESEARCH / f"bahis_aileleri_karsilastirma_{args.eski or 'uretim'}_{args.yeni or 'uretim'}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def write_calibration(rows: list[dict]) -> None:
    """Merge kept curves into data/calibration/market_calibration.json (derived selections only)."""
    cal = json.loads(CAL_FILE.read_text(encoding="utf-8")) if CAL_FILE.exists() else {"version": 1, "markets": {}}
    markets = cal.setdefault("markets", {})
    for r in rows:
        if r["secim"] in DIRECT:
            continue  # quoted by the reference: never recalibrated (a devigged sharp price is the fair price)
        if r["tutulan"]:
            curve = dict(r["egri"])
            lig = r["tutulan"] == "platt_lig"
            curve.update({"direct_in_production": False, "aile": r["aile"], "kaynak": "bahis_aileleri_kalibrasyon.py",
                          "oos_ll_fark": r["d_platt_lig"] if lig else r["d_platt"],
                          "oos_ci95": r["ci_platt_lig"] if lig else r["ci_platt"]})
            markets[r["secim"]] = curve
        elif r["secim"] in markets:
            del markets[r["secim"]]  # no significant out-of-sample gain on the current pipeline: raw fair price
    cal["bahis_aileleri"] = {"fitted_on": "data/matches.csv (2011/12+; walk-forward test 2016/17+), tırmıklı üretim hattı",
                             "kural": "yalnız OOS log-loss farkının %95 GA üst ucu < 0 olan türev seçimler"}
    CAL_FILE.write_text(json.dumps(cal, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{CAL_FILE} güncellendi: {sorted(markets)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("onbellek")
    c.add_argument("--limit", type=int, default=0)
    c.add_argument("--isci", type=int, default=6)
    a = sub.add_parser("analiz")
    a.add_argument("--yaz", action="store_true")
    a.add_argument("--isci", type=int, default=6)
    k = sub.add_parser("karsilastir")
    k.add_argument("eski")
    k.add_argument("yeni")
    args = ap.parse_args()
    {"onbellek": cmd_cache, "analiz": cmd_analyze, "karsilastir": cmd_compare}[args.cmd](args)


if __name__ == "__main__":
    main()
