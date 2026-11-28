"""Yüksek oranlı pazarlar için sızıntısız ileri-yürüyen (walk-forward) geriye dönük test.

Her hafta başı D için yalnız `MatchDate < D` maçlarla takım oranları kurulur ve [D, D+7) maçları tahmin edilir.
Kalibrasyon çarpanları ay başı M için yalnız M'den önceki ÖRNEKLEM-DIŞI tahminlerden hesaplanır.
Hiperparametreler doğrulama döneminde (varsayılan 2022-07-01..2024-06-30) seçilir; rapor test döneminde
(2024-07-01 sonrası, son 2+ sezon) verilir.

Pazar oranları (İY/MS, skor, korner) arşivde YOK; bu yüzden ROI hesaplanamaz. "Piyasa türevi" kıyas modeli
1X2 + 2.5 Alt/Üst oranlarından ters çevrilmiş gol beklentisiyle aynı pazarı fiyatlar.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantfoot.markets import yuksek_oran_modeli as ym

ROOT = Path(__file__).resolve().parents[3]
OLD_SHARE = 0.444  # eski analitik taban (high_odds_analyzer / halves 'e0' profili)


# ----------------------------------------------------------------------------------------------
# Veri
# ----------------------------------------------------------------------------------------------
def load_matches(path: Path | None = None, since: str = "2018-07-01") -> pd.DataFrame:
    cols = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "HTHome", "HTAway",
            "HomeCorners", "AwayCorners", "OddHome", "OddDraw", "OddAway", "Over25", "Under25"]
    df = pd.read_csv(path or ROOT / "data" / "matches.csv", usecols=cols, low_memory=False)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    df = df.dropna(subset=["MatchDate", "FTHome", "FTAway", "HomeTeam", "AwayTeam"])
    df = df[df.MatchDate >= since].sort_values(["MatchDate", "Division"]).reset_index(drop=True)
    # bozuk İY satırları (İY > MS) atılır
    bad = (df.HTHome > df.FTHome) | (df.HTAway > df.FTAway)
    df.loc[bad, ["HTHome", "HTAway"]] = np.nan
    p = ym.devig(df[["OddHome", "OddDraw", "OddAway"]].to_numpy())
    df["p1"], df["px"], df["p2"] = p[:, 0], p[:, 1], p[:, 2]
    ou = df[["Over25", "Under25"]].to_numpy(float)
    ou = np.where((ou > 1.0) & (ou < 30), ou, np.nan)
    po = ym.devig(ou)
    df["po"] = po[:, 0]
    return df


def gfi_share_prior() -> dict[str, float]:
    f = ROOT / "data" / "gfi" / "lig_yari_dakika_gfi.csv"
    if not f.exists():
        return {}
    t = pd.read_csv(f, comment="#")
    m = dict(zip(t.lig, t.iy_payi))
    return {div: float(m[code]) for div, code in ym.DIV_TO_GFI.items() if code in m} | {"_genel": float(m.get("_genel", ym.DEFAULT_FIRST_HALF_SHARE))}


# ----------------------------------------------------------------------------------------------
# 1. aşama: haftalık takım oranları (sızıntısız)
# ----------------------------------------------------------------------------------------------
@dataclass
class FeatureConfig:
    start: str = "2021-07-01"
    window_days: int = 3 * 365
    half_life: float = 240.0
    k_goals: float = 4.0
    k_half: float = 6.0
    k_corner: float = 25.0
    share_prior_goals: float = 400.0


def build_features(df: pd.DataFrame, cfg: FeatureConfig | None = None, progress: bool = False) -> pd.DataFrame:
    cfg = cfg or FeatureConfig()
    prior = gfi_share_prior()
    g_prior = prior.get("_genel", ym.DEFAULT_FIRST_HALF_SHARE)
    out_cols = ["lam_m", "mu_m", "s_h", "s_a", "s_lig", "ch_m", "ca_m", "c_vm"]
    feats = np.full((len(df), len(out_cols)), np.nan)
    dates = df.MatchDate.to_numpy()
    divs = df.Division.to_numpy()
    week_starts = pd.date_range(pd.Timestamp(cfg.start) - pd.Timedelta(days=pd.Timestamp(cfg.start).weekday()),
                                df.MatchDate.max() + pd.Timedelta(days=1), freq="7D")
    by_div = {d: np.flatnonzero(divs == d) for d in np.unique(divs)}
    H, A = df.HomeTeam.to_numpy(), df.AwayTeam.to_numpy()
    FH, FA = df.FTHome.to_numpy(float), df.FTAway.to_numpy(float)
    HH, HA = df.HTHome.to_numpy(float), df.HTAway.to_numpy(float)
    CH, CA = df.HomeCorners.to_numpy(float), df.AwayCorners.to_numpy(float)
    for wi, D in enumerate(week_starts):
        D64, E64 = np.datetime64(D), np.datetime64(D + pd.Timedelta(days=7))
        lo64 = np.datetime64(D - pd.Timedelta(days=cfg.window_days))
        for div, idx in by_div.items():
            dd = dates[idx]
            tgt = idx[(dd >= D64) & (dd < E64)]
            if not len(tgt):
                continue
            tr = idx[(dd < D64) & (dd >= lo64)]
            if len(tr) < 150:
                continue
            age = (D64 - dates[tr]).astype("timedelta64[D]").astype(float)
            w = 0.5 ** (age / cfg.half_life)
            ft = ym.fit_maher(H[tr], A[tr], FH[tr], FA[tr], w, cfg.k_goals)
            hm = np.isfinite(HH[tr])
            h1 = h2 = None
            s_lig = prior.get(div, g_prior)
            if hm.sum() >= 150:
                t2 = tr[hm]
                h1 = ym.fit_maher(H[t2], A[t2], HH[t2], HA[t2], w[hm], cfg.k_half)
                h2 = ym.fit_maher(H[t2], A[t2], FH[t2] - HH[t2], FA[t2] - HA[t2], w[hm], cfg.k_half)
                g1, gt = (HH[t2] + HA[t2]).sum(), (FH[t2] + FA[t2]).sum()
                s0 = prior.get(div, g_prior)
                s_lig = (g1 + cfg.share_prior_goals * s0) / (gt + cfg.share_prior_goals)
            cm = np.isfinite(CH[tr]) & np.isfinite(CA[tr])
            cf, cvm = None, np.nan
            if cm.sum() >= 150:
                t3 = tr[cm]
                cf = ym.fit_maher(H[t3], A[t3], CH[t3], CA[t3], w[cm], cfg.k_corner)
                eh = np.array([cf.expect(h, a) for h, a in zip(H[t3], A[t3])])
                et = eh.sum(axis=1)
                tot = CH[t3] + CA[t3]
                cvm = float(np.average((tot - et) ** 2, weights=w[cm]) / np.average(et, weights=w[cm]))
            for i in tgt:
                lm, mm = ft.expect(H[i], A[i])
                sh = sa = s_lig
                if h1 is not None:
                    a1, b1 = h1.expect(H[i], A[i])
                    a2, b2 = h2.expect(H[i], A[i])
                    sh, sa = a1 / (a1 + a2), b1 / (b1 + b2)
                ch = ca = np.nan
                if cf is not None:
                    ch, ca = cf.expect(H[i], A[i])
                feats[i] = (lm, mm, sh, sa, s_lig, ch, ca, cvm)
        if progress and wi % 26 == 0:
            print(f"  hafta {D.date()} ({wi}/{len(week_starts)})", flush=True)
    out = df.copy()
    for j, c in enumerate(out_cols):
        out[c] = feats[:, j]
    return out


# ----------------------------------------------------------------------------------------------
# 2. aşama: olasılıklar
# ----------------------------------------------------------------------------------------------
@dataclass
class ProbConfig:
    w_market: float = 0.8  # log-λ harman ağırlığı (piyasa)
    gamma_team: float = 0.5  # takım İY eğiliminin lig payına eklenme oranı
    rho_iy: float = -0.05
    rho_2y: float = -0.03
    rho_ms: float = -0.05


def add_market_lambdas(df: pd.DataFrame, inverter: ym.MarketInverter | None = None) -> pd.DataFrame:
    inv = inverter or ym.MarketInverter()
    lam, mu = inv.invert(df.p1.to_numpy(), df.p2.to_numpy(), df.po.to_numpy())
    out = df.copy()
    out["lam_p"], out["mu_p"] = lam, mu
    return out


def outcomes(df: pd.DataFrame) -> dict[str, np.ndarray]:
    fh, fa = df.FTHome.to_numpy(int), df.FTAway.to_numpy(int)
    hh, ha = df.HTHome.to_numpy(float), df.HTAway.to_numpy(float)
    ht_ok = np.isfinite(hh)
    hhi, hai = np.nan_to_num(hh).astype(int), np.nan_to_num(ha).astype(int)
    r_ht = np.where(hhi > hai, 0, np.where(hhi == hai, 1, 2))
    r_ft = np.where(fh > fa, 0, np.where(fh == fa, 1, 2))
    htft = r_ht * 3 + r_ft
    ft_cls = np.full(len(df), len(ym.FT_SCORES))
    for c, (h, a) in enumerate(ym.FT_SCORES):
        ft_cls[(fh == h) & (fa == a)] = c
    ht_cls = np.full(len(df), len(ym.HT_SCORES))
    for c, (h, a) in enumerate(ym.HT_SCORES):
        ht_cls[(hhi == h) & (hai == a)] = c
    kg2 = ((fh - hhi) > 0) & ((fa - hai) > 0)
    ch, ca = df.HomeCorners.to_numpy(float), df.AwayCorners.to_numpy(float)
    return {"ht_ok": ht_ok, "htft": htft, "ft": ft_cls, "ht": ht_cls, "kg2": kg2.astype(int),
            "c_ok": np.isfinite(ch) & np.isfinite(ca), "ctot": ch + ca, "ch": ch, "ca": ca}


def blended_lambdas(df: pd.DataFrame, cfg: ProbConfig) -> tuple[np.ndarray, np.ndarray]:
    """log-λ harmanı; piyasa yoksa model, model yoksa piyasa."""
    lp, mp = df.lam_p.to_numpy(), df.mu_p.to_numpy()
    lm, mm = df.lam_m.to_numpy(), df.mu_m.to_numpy()
    has_p, has_m = np.isfinite(lp), np.isfinite(lm)
    w = np.where(has_p & has_m, cfg.w_market, np.where(has_p, 1.0, 0.0))
    lam = np.exp(w * np.log(np.where(has_p, lp, 1)) + (1 - w) * np.log(np.where(has_m, lm, 1)))
    mu = np.exp(w * np.log(np.where(has_p, mp, 1)) + (1 - w) * np.log(np.where(has_m, mm, 1)))
    bad = ~(has_p | has_m)
    lam[bad], mu[bad] = np.nan, np.nan
    return lam, mu


def half_shares(df: pd.DataFrame, cfg: ProbConfig) -> tuple[np.ndarray, np.ndarray]:
    sl = np.nan_to_num(df.s_lig.to_numpy(), nan=ym.DEFAULT_FIRST_HALF_SHARE)
    shh = np.where(np.isfinite(df.s_h.to_numpy()), df.s_h.to_numpy(), sl)
    saa = np.where(np.isfinite(df.s_a.to_numpy()), df.s_a.to_numpy(), sl)
    return np.clip(sl + cfg.gamma_team * (shh - sl), 0.3, 0.6), np.clip(sl + cfg.gamma_team * (saa - sl), 0.3, 0.6)


def game_state_multipliers(df: pd.DataFrame, cfg: ProbConfig, prior_goals: float = 300.0,
                           min_rows: int = 2000) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Aylık, yalnız geçmiş İY'li maçlardan: durum başına 2Y gözlenen/beklenen gol oranı (1'e büzülmüş)."""
    lam, mu = blended_lambdas(df, cfg)
    sh, sa = half_shares(df, cfg)
    e2h, e2a = lam * (1 - sh), mu * (1 - sa)
    hh, ha = df.HTHome.to_numpy(float), df.HTAway.to_numpy(float)
    o2h, o2a = df.FTHome.to_numpy(float) - hh, df.FTAway.to_numpy(float) - ha
    ok = np.isfinite(hh) & np.isfinite(e2h)
    state = np.where(hh > ha, 0, np.where(hh == ha, 1, 2))
    months = df.MatchDate.dt.to_period("M").to_numpy()
    mh, ma = np.ones((len(df), 3)), np.ones((len(df), 3))
    last: dict[str, Any] = {}
    for m in sorted(set(months)):
        cur = months == m
        past = (months < m) & ok
        if past.sum() < min_rows:
            continue
        gh, ga = np.ones(3), np.ones(3)
        for st in range(3):
            q = past & (state == st)
            gh[st] = (o2h[q].sum() + prior_goals) / (e2h[q].sum() + prior_goals)
            ga[st] = (o2a[q].sum() + prior_goals) / (e2a[q].sum() + prior_goals)
        mh[cur], ma[cur] = gh, ga
        last = {"ev": gh.round(4).tolist(), "dep": ga.round(4).tolist(), "son_ay": str(m)}
    return mh, ma, last


def raw_probs(df: pd.DataFrame, cfg: ProbConfig, variant: str, mult: tuple[np.ndarray, np.ndarray] | None = None,
              ft_from_halves: bool = False) -> dict[str, np.ndarray]:
    """variant: 'once' (model λ, sabit pay, DC yok), 'piyasa' (piyasa λ, sabit pay, DC yok),
    'sonra' (harman λ + lig/takım payı + DC + devre-arası durum çarpanları)."""
    n = len(df)
    if variant in ("once", "piyasa"):
        lam = (df.lam_m if variant == "once" else df.lam_p).to_numpy()
        mu = (df.mu_m if variant == "once" else df.mu_p).to_numpy()
        sh = sa = np.full(n, OLD_SHARE)
        r1 = r2 = rf = 0.0
    else:
        lam, mu = blended_lambdas(df, cfg)
        sh, sa = half_shares(df, cfg)
        r1, r2, rf = cfg.rho_iy, cfg.rho_2y, cfg.rho_ms
    lam, mu = np.nan_to_num(lam, nan=1.4), np.nan_to_num(mu, nan=1.1)
    m1 = ym.dc_matrix(lam * sh, mu * sa, r1)
    mh, ma = mult if (mult is not None and variant == "sonra") else (np.ones((n, 3)), np.ones((n, 3)))
    gs = ym.game_state_model(m1, lam * (1 - sh), mu * (1 - sa), mh, ma, r2)
    mf = gs["ft_matrix"] if ft_from_halves else ym.dc_matrix(lam, mu, rf)
    i, j = np.indices(mf.shape[1:])
    p_home = (mf * (i > j)).sum(axis=(1, 2))
    p_away = (mf * (i < j)).sum(axis=(1, 2))
    return {"htft": gs["htft"], "ft": ym.score_classes(mf, ym.FT_SCORES),
            "ht": ym.score_classes(m1, ym.HT_SCORES), "kg2": gs["kg2"],
            "bucket": ym.fav_bucket(p_home, p_away)}


def walk_forward_calibrate(df: pd.DataFrame, raw: dict[str, np.ndarray], y: dict[str, np.ndarray],
                           cal_from: str, prior: float = 60.0) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Ay ay: ayın maçları, o aydan önceki örneklem-dışı ham tahminlerle kalibre edilir. Son durum da döner."""
    months = df.MatchDate.dt.to_period("M").to_numpy()
    out = {k: v.copy() for k, v in raw.items() if k != "bucket"}
    ht_ok = y["ht_ok"]
    valid = np.isfinite(raw["kg2"]) & np.isfinite(raw["htft"]).all(axis=1)
    first = pd.Period(cal_from, "M")
    final: dict[str, Any] = {}
    for m in sorted(set(months)):
        if m < first:
            continue
        cur = (months == m) & valid
        past = (months < m) & valid
        if past.sum() < 500:
            continue
        ph = past & ht_ok
        fac = {}
        for b in (0, 1, 2):
            sel = ph & (raw["bucket"] == b)
            fac[b] = ym.cell_factors(raw["htft"][sel], y["htft"][sel], prior)
        for b in (0, 1, 2):
            c = cur & (raw["bucket"] == b)
            out["htft"][c] = ym.apply_cell_factors(raw["htft"][c], fac[b])
        f_ft = ym.cell_factors(raw["ft"][past], y["ft"][past], prior)
        out["ft"][cur] = ym.apply_cell_factors(raw["ft"][cur], f_ft)
        f_ht = ym.cell_factors(raw["ht"][ph], y["ht"][ph], prior)
        out["ht"][cur] = ym.apply_cell_factors(raw["ht"][cur], f_ht)
        ab = ym.fit_logit_calibration(raw["kg2"][ph], y["kg2"][ph])
        out["kg2"][cur] = ym.apply_logit(raw["kg2"][cur], ab)
        final = {"htft": {str(b): fac[b].round(4).tolist() for b in fac}, "skor": f_ft.round(4).tolist(),
                 "iy_skor": f_ht.round(4).tolist(), "kg2": [round(ab[0], 4), round(ab[1], 4)], "son_ay": str(m)}
    return out, final


# ----------------------------------------------------------------------------------------------
# Korner
# ----------------------------------------------------------------------------------------------
def corner_probs(df: pd.DataFrame, y: dict[str, np.ndarray], cal_from: str,
                 use_sup: bool = True) -> tuple[dict[float, np.ndarray], dict[str, Any]]:
    """'sonra' korner: takım Maher korner beklentisi, aylık ve yalnız geçmiş örneklem-dışı satırlarla
    doğrusal düzeltilir (toplam ~ a + b·beklenti [+ c·|piyasa üstünlüğü|]; b<1 = takım farklarını büzme),
    dağılım NB, Var/Ort oranı geçmiş artıklardan."""
    months = df.MatchDate.dt.to_period("M").to_numpy()
    e = df.ch_m.to_numpy() + df.ca_m.to_numpy()
    sup = np.abs(np.nan_to_num(df.p1.to_numpy() - df.p2.to_numpy()))
    ok = y["c_ok"] & np.isfinite(e)
    tot = y["ctot"]
    adj = np.full(len(df), np.nan)
    vm = np.full(len(df), np.nan)
    coef: list[float] = []
    v_last = np.nan
    first = pd.Period(cal_from, "M")
    for m in sorted(set(months)):
        if m < first:
            continue
        cur = (months == m) & ok
        past = (months < m) & ok
        if past.sum() < 1000 or not cur.any():
            continue
        X = np.c_[np.ones(past.sum()), e[past], sup[past]] if use_sup else np.c_[np.ones(past.sum()), e[past]]
        beta = np.linalg.lstsq(X, tot[past], rcond=None)[0]
        fit = X @ beta
        v_last = float(np.mean((tot[past] - fit) ** 2) / np.mean(fit))
        Xc = np.c_[np.ones(cur.sum()), e[cur], sup[cur]] if use_sup else np.c_[np.ones(cur.sum()), e[cur]]
        adj[cur] = np.clip(Xc @ beta, 3.0, 20.0)
        vm[cur] = v_last
        coef = beta.round(4).tolist()
    probs = {ln: np.where(np.isfinite(adj), ym.nb_over(np.nan_to_num(adj, nan=10.0), np.nan_to_num(vm, nan=1.2), ln), np.nan)
             for ln in ym.CORNER_LINES}
    return probs, {"katsayi": coef, "ozellikler": ["sabit", "takim_beklentisi", "abs_ustunluk"] if use_sup
                   else ["sabit", "takim_beklentisi"], "var_ort": round(v_last, 4) if np.isfinite(v_last) else None}


def corner_probs_old(df: pd.DataFrame, y: dict[str, np.ndarray]) -> dict[float, np.ndarray]:
    """'önce' korner: depodaki CornerCardRatings (α=0.02, nedensel) + CornerDistribution."""
    from quantfoot.markets.corners_cards import CornerCardRatings, league_baseline

    rt = CornerCardRatings()
    n = len(df)
    eh, ea = np.full(n, np.nan), np.full(n, np.nan)
    H, A, D = df.HomeTeam.to_numpy(), df.AwayTeam.to_numpy(), df.Division.to_numpy()
    ok = y["c_ok"]
    # aynı gün içinde sıra: tahmin önce, güncelleme sonra (gün bazında)
    dates = df.MatchDate.to_numpy()
    i = 0
    while i < n:
        j = i
        while j < n and dates[j] == dates[i]:
            j += 1
        for k in range(i, j):
            if ok[k]:
                e = rt.expected(H[k], A[k], D[k])
                eh[k], ea[k] = e["corners_home"], e["corners_away"]
        for k in range(i, j):
            if ok[k]:
                rt.update(H[k], A[k], D[k], y["ch"][k], y["ca"][k], np.nan, np.nan)
        i = j
    vm = np.array([league_baseline(d)[2] for d in D])
    return {ln: np.where(ok, ym.nb_over(np.nan_to_num(eh + ea, nan=10.0), vm, ln), np.nan) for ln in ym.CORNER_LINES}


# ----------------------------------------------------------------------------------------------
# Metrikler
# ----------------------------------------------------------------------------------------------
BINS = (0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.70, 1.0001)


def multi_metrics(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-9, 1)
    n = len(y)
    ll = float(-np.log(p[np.arange(n), y]).mean())
    onehot = np.zeros_like(p)
    onehot[np.arange(n), y] = 1
    brier = float(((p - onehot) ** 2).sum(axis=1).mean())
    return {"n": int(n), "logloss": round(ll, 5), "brier": round(brier, 5)}


def binary_metrics(p: np.ndarray, y: np.ndarray) -> dict[str, float]:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    ll = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    return {"n": len(y), "logloss": round(ll, 5), "brier": round(float(((p - y) ** 2).mean()), 5),
            "ort_tahmin": round(float(p.mean()), 4), "gercek": round(float(y.mean()), 4)}


def calibration_table(p: np.ndarray, y: np.ndarray) -> list[dict[str, Any]]:
    """Çok sınıflı ise her hücre ayrı ikili olay olarak havuzlanır."""
    if p.ndim == 2:
        onehot = np.zeros_like(p)
        onehot[np.arange(len(y)), y] = 1
        pp, yy = p.ravel(), onehot.ravel()
    else:
        pp, yy = p, y
    rows = []
    for lo, hi in itertools.pairwise(BINS):
        s = (pp >= lo) & (pp < hi)
        if s.sum() < 30:
            continue
        rows.append({"bant": f"{lo:.0%}-{min(hi, 1):.0%}", "n": int(s.sum()), "tahmin": round(float(pp[s].mean()), 4),
                     "gercek": round(float(yy[s].mean()), 4)})
    return rows


def ece(p: np.ndarray, y: np.ndarray) -> float:
    tab = calibration_table(p, y)
    tot = sum(r["n"] for r in tab)
    return round(sum(r["n"] * abs(r["tahmin"] - r["gercek"]) for r in tab) / max(tot, 1), 5)


def class_freq(p: np.ndarray, y: np.ndarray, labels: list[str]) -> list[dict[str, Any]]:
    return [{"secim": lab, "tahmin": round(float(p[:, c].mean()), 4), "gercek": round(float((y == c).mean()), 4)}
            for c, lab in enumerate(labels)]


def paired_delta(ll_a: np.ndarray, ll_b: np.ndarray) -> dict[str, float]:
    """b - a ortalama log-loss farkı ve t (negatif = b daha iyi)."""
    d = ll_b - ll_a
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
    return {"fark": round(float(d.mean()), 5), "t": round(float(d.mean() / se), 2) if se and se > 0 else 0.0}


def per_row_ll(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    if p.ndim == 2:
        return -np.log(np.clip(p[np.arange(len(y)), y], 1e-9, 1))
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


@dataclass
class BacktestResult:
    config: dict[str, Any]
    markets: dict[str, Any] = field(default_factory=dict)
    subsets: list[dict[str, Any]] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
