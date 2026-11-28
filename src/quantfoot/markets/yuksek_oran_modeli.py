"""Yüksek oranlı pazarlar için yarı-bazlı skor modeli (analiz katmanı, banko kupona GİRMEZ).

Pazarlar: kesin skor, İY skoru, İY/MS (9 hücre), 2. yarı KG, korner alt/üst.

Model (28 Kas 2026, `scripts/yuksek_oran_pazarlar.py backtest` ile seçildi ve ölçüldü):

1. **Gol beklentisi.** Takım hücum/savunma oranları zaman ağırlıklı Maher (1982) çarpımsal Poisson'la
   (`fit_maher`) bulunur ve 1X2 + 2.5 Alt/Üst oranlarından ters çevrilmiş piyasa beklentisiyle
   (`MarketInverter`) log-uzayda harmanlanır.
2. **Yarılara bölme.** Lig İY gol payı eğitim verisinden ölçülür, `data/gfi/lig_yari_dakika_gfi.csv` önceline
   sözde-golle büzülür (sabit %44.4 yerine). Takımın kendi İY eğilimi (`gamma_team`) doğrulamada zarar verdiği için 0.
3. **Düşük skor düzeltmesi.** Yarı matrislerine Dixon-Coles tau (rho) uygulanabilir; doğrulamada rho=0 seçildi
   (beraberlik/düşük skor şişmesini hücre kalibrasyonu daha iyi yakalıyor).
4. **İY/MS.** 2. yarı gol beklentisi devre-arası skoruna bağlı (`game_state_model`: geride kapatan daha çok, önde
   kapatan daha az atar); MS = İY + 2Y konvolüsyonu. Geri dönüşler (1/2, 2/1) ve tüm hücreler, geçmiş örneklem-dışı
   tahminlerin gerçek frekansına hücre çarpanıyla kalibre edilir (`apply_cell_factors`; favori kovası başına).
5. **Kesin skor / İY skoru.** Yarı modelinden gelen maç skoru matrisi + skor hücresi çarpanları (beraberlik şişmesi).
6. **2Y KG.** 2. yarı DC matrisinden; logit kalibrasyonu.
7. **Korner.** Takım korner kazanma/yeme oranları (zaman ağırlıklı Maher, korner sayıları); beklenen toplam,
   geçmiş örneklem-dışı satırlarla doğrusal büzülür (toplam ≈ a + b·beklenti + c·|üstünlük|, b ≈ 0.57) ve
   negatif binomla fiyatlanır (Var/Ort geçmiş artıklardan).

Piyasa payı nedeniyle bu pazarlarda pozitif beklenen değer garanti değildir; arşivde bu pazarların oranı yok,
o yüzden ROI ölçülemez. Çıktılar yalnız olasılıktır.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.special import gammaln
from scipy.stats import nbinom

ROOT = Path(__file__).resolve().parents[3]
PARAMS_PATH = ROOT / "data" / "calibration" / "yuksek_oran_kalibrasyon.json"

MAXG = 10  # yarı ve maç matrisi 0..MAXG
HTFT_LABELS = ("1/1", "1/0", "1/2", "0/1", "0/0", "0/2", "2/1", "2/0", "2/2")
FT_SCORES = tuple((h, a) for h in range(5) for a in range(5))  # + "diğer"
HT_SCORES = tuple((h, a) for h in range(3) for a in range(3))  # + "diğer"
CORNER_LINES = (8.5, 9.5, 10.5, 11.5)
DEFAULT_FIRST_HALF_SHARE = 0.445

# football-data bölüm kodu -> data/gfi/lig_yari_dakika_gfi.csv lig kodu (yalnız eşleşenler)
DIV_TO_GFI = {
    "E0": "en.1", "D1": "de.1", "SP1": "es.1", "I1": "it.1", "F1": "fr.1", "N1": "nl.1",
    "P1": "pt.1", "B1": "be.1", "AUT": "at.1", "SUI": "ch.1", "DEN": "wr:denmark", "POL": "wr:poland",
}


# ----------------------------------------------------------------------------------------------
# Temel olasılık yapıları (vektörel: ilk eksen maç)
# ----------------------------------------------------------------------------------------------
def poisson_pmf(lam: np.ndarray, n: int = MAXG) -> np.ndarray:
    lam = np.clip(np.asarray(lam, float), 1e-6, None)[..., None]
    k = np.arange(n + 1)
    return np.exp(k * np.log(lam) - lam - gammaln(k + 1))


def dc_matrix(lh: np.ndarray, la: np.ndarray, rho: float = 0.0, n: int = MAXG) -> np.ndarray:
    """(N, n+1, n+1) Dixon-Coles düzeltmeli bağımsız Poisson skor matrisi, satır=ev golü."""
    lh = np.atleast_1d(np.asarray(lh, float))
    la = np.atleast_1d(np.asarray(la, float))
    m = poisson_pmf(lh, n)[:, :, None] * poisson_pmf(la, n)[:, None, :]
    if rho:
        lhc, lac = np.clip(lh, 1e-6, None), np.clip(la, 1e-6, None)
        t00 = np.clip(1.0 - lhc * lac * rho, 1e-6, None)
        t01 = np.clip(1.0 + lhc * rho, 1e-6, None)
        t10 = np.clip(1.0 + lac * rho, 1e-6, None)
        t11 = np.clip(1.0 - rho, 1e-6, None)
        m[:, 0, 0] *= t00
        m[:, 0, 1] *= t01
        m[:, 1, 0] *= t10
        m[:, 1, 1] *= t11
    m /= m.sum(axis=(1, 2), keepdims=True)
    return m


def diff_dist(mat: np.ndarray) -> np.ndarray:
    """Skor matrisinden ev-dep farkı dağılımı; indeks d+n (d = -n..n)."""
    n = mat.shape[1] - 1
    out = np.zeros((mat.shape[0], 2 * n + 1))
    for i in range(n + 1):
        for j in range(n + 1):
            out[:, i - j + n] += mat[:, i, j]
    return out


def htft_from_halves(m1: np.ndarray, m2: np.ndarray) -> np.ndarray:
    """(N, 9) İY/MS olasılıkları, sıra HTFT_LABELS. İki yarı koşullu bağımsız."""
    d1, d2 = diff_dist(m1), diff_dist(m2)
    n = m1.shape[1] - 1
    vals = np.arange(-n, n + 1)
    c2 = np.cumsum(d2, axis=1)  # P(D2 <= v)

    def p_le(v: np.ndarray) -> np.ndarray:  # P(D2 <= v), v tamsayı dizisi (k,)
        idx = np.clip(v + n, -1, 2 * n)
        res = np.where(idx[None, :] < 0, 0.0, c2[:, np.clip(idx, 0, 2 * n)])
        return res

    out = np.zeros((m1.shape[0], 9))
    ht_codes = {1: vals > 0, 0: vals == 0, 2: vals < 0}
    for hi, hc in enumerate((1, 0, 2)):
        sel = ht_codes[hc]
        dv = vals[sel]
        w = d1[:, sel]  # (N, k)
        p_away = p_le(-dv - 1)  # D1+D2 < 0
        p_le0 = p_le(-dv)  # D1+D2 <= 0
        p_draw = p_le0 - p_away
        p_home = 1.0 - p_le0
        for fi, arr in enumerate((p_home, p_draw, p_away)):
            out[:, hi * 3 + fi] = (w * arr).sum(axis=1)
    out /= out.sum(axis=1, keepdims=True)
    return out


def half_state_masks(n: int = MAXG) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """İY skor hücreleri için durum maskeleri: (ev önde, eşit, ev geride)."""
    i, j = np.indices((n + 1, n + 1))
    return i > j, i == j, i < j


def game_state_model(m1: np.ndarray, lam2: np.ndarray, mu2: np.ndarray, mult_h: np.ndarray, mult_a: np.ndarray,
                     rho2: float = 0.0) -> dict[str, np.ndarray]:
    """Devre arası skoruna bağlı 2. yarı: durum s (0 ev önde, 1 eşit, 2 ev geride) için
    λ2·mult_h[:, s], μ2·mult_a[:, s]. İY/MS, maç sonu matrisi ve 2Y KG döner.

    Gerekçe (data/matches.csv, piyasa beklentisine göre): geride kapatan takım 2. yarıda ~%8-11 daha çok,
    önde kapatan ~%4-6 daha az gol atıyor; üç dönemde de tutarlı.
    """
    n = m1.shape[1] - 1
    masks = half_state_masks(n)
    m2s = [dc_matrix(lam2 * mult_h[:, s], mu2 * mult_a[:, s], rho2, n) for s in range(3)]
    d1 = diff_dist(m1)
    vals = np.arange(-n, n + 1)
    out = np.zeros((m1.shape[0], 9))
    for hi, (sel, s) in enumerate(((vals > 0, 0), (vals == 0, 1), (vals < 0, 2))):
        c2 = np.cumsum(diff_dist(m2s[s]), axis=1)
        dv = vals[sel]
        w = d1[:, sel]

        def p_le(v: np.ndarray, c2: np.ndarray = c2) -> np.ndarray:
            idx = v + n
            return np.where(idx[None, :] < 0, 0.0, c2[:, np.clip(idx, 0, 2 * n)])

        p_away = p_le(-dv - 1)
        p_le0 = p_le(-dv)
        for fi, arr in enumerate((1.0 - p_le0, p_le0 - p_away, p_away)):
            out[:, hi * 3 + fi] = (w * arr).sum(axis=1)
    out /= out.sum(axis=1, keepdims=True)
    ft = np.zeros_like(m1)
    kg2 = np.zeros(m1.shape[0])
    for s in range(3):
        ft += convolve_halves(m1 * masks[s][None], m2s[s], n, normalize=False)
        kg2 += (m1 * masks[s][None]).sum(axis=(1, 2)) * btts_from_matrix(m2s[s])
    ft /= ft.sum(axis=(1, 2), keepdims=True)
    return {"htft": out, "ft_matrix": ft, "kg2": kg2}


def convolve_halves(m1: np.ndarray, m2: np.ndarray, n: int = MAXG, normalize: bool = True) -> np.ndarray:
    """İki yarı matrisinin toplamı (maç sonu skoru), 0..n'de kesilip normalize."""
    N, k, _ = m1.shape
    out = np.zeros((N, n + 1, n + 1))
    for i in range(k):
        for j in range(k):
            w = m1[:, i, j]
            if not np.any(w > 1e-12):
                continue
            hi, hj = min(n + 1 - i, k), min(n + 1 - j, k)
            if hi <= 0 or hj <= 0:
                continue
            out[:, i:i + hi, j:j + hj] += w[:, None, None] * m2[:, :hi, :hj]
    if normalize:
        out /= np.clip(out.sum(axis=(1, 2), keepdims=True), 1e-300, None)
    return out


def score_classes(mat: np.ndarray, scores: tuple[tuple[int, int], ...]) -> np.ndarray:
    """(N, len(scores)+1) skor sınıfları + 'diğer'."""
    cols = [mat[:, h, a] for h, a in scores]
    p = np.stack(cols, axis=1)
    other = np.clip(1.0 - p.sum(axis=1, keepdims=True), 1e-9, None)
    out = np.concatenate([p, other], axis=1)
    return out / out.sum(axis=1, keepdims=True)


def btts_from_matrix(mat: np.ndarray) -> np.ndarray:
    return 1.0 - mat[:, 0, :].sum(axis=1) - mat[:, :, 0].sum(axis=1) + mat[:, 0, 0]


# ----------------------------------------------------------------------------------------------
# Zaman ağırlıklı Maher (çarpımsal Poisson) takım oranları
# ----------------------------------------------------------------------------------------------
@dataclass
class MaherFit:
    att: dict[str, float]
    dfn: dict[str, float]
    base_h: float
    base_a: float

    def expect(self, home: str, away: str) -> tuple[float, float]:
        ah, dh = self.att.get(home, 1.0), self.dfn.get(home, 1.0)
        aa, da = self.att.get(away, 1.0), self.dfn.get(away, 1.0)
        return self.base_h * ah * da, self.base_a * aa * dh


def fit_maher(home: np.ndarray, away: np.ndarray, gh: np.ndarray, ga: np.ndarray, w: np.ndarray,
              k: float = 4.0, iters: int = 25) -> MaherFit:
    """Ağırlıklı Maher; k = takım başına sözde-gol (1.0'a büzme)."""
    teams, inv = np.unique(np.concatenate([home, away]), return_inverse=True)
    T = len(teams)
    hi, ai = inv[: len(home)], inv[len(home):]
    sw = w.sum()
    base_h = float((w * gh).sum() / max(sw, 1e-9))
    base_a = float((w * ga).sum() / max(sw, 1e-9))
    att = np.ones(T)
    dfn = np.ones(T)
    scored = np.bincount(hi, w * gh, T) + np.bincount(ai, w * ga, T)
    conceded = np.bincount(hi, w * ga, T) + np.bincount(ai, w * gh, T)
    for _ in range(iters):
        exp_att = np.bincount(hi, w * base_h * dfn[ai], T) + np.bincount(ai, w * base_a * dfn[hi], T)
        att = (scored + k) / (exp_att + k)
        att /= np.average(att, weights=np.bincount(hi, w, T) + np.bincount(ai, w, T) + 1e-9)
        exp_def = np.bincount(hi, w * base_a * att[ai], T) + np.bincount(ai, w * base_h * att[hi], T)
        dfn = (conceded + k) / (exp_def + k)
        dfn /= np.average(dfn, weights=np.bincount(hi, w, T) + np.bincount(ai, w, T) + 1e-9)
    return MaherFit(dict(zip(teams.tolist(), att.tolist())), dict(zip(teams.tolist(), dfn.tolist())), base_h, base_a)


# ----------------------------------------------------------------------------------------------
# Piyasa (1X2 + 2.5 Alt/Üst) -> gol beklentisi
# ----------------------------------------------------------------------------------------------
def devig(odds: np.ndarray) -> np.ndarray:
    """Oran dizisi (N, k) -> orantısal marjsız olasılık; geçersizler NaN."""
    o = np.asarray(odds, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = np.where(o > 1.0, 1.0 / np.where(o > 1.0, o, 2.0), np.nan)
    return inv / inv.sum(axis=1, keepdims=True)


class MarketInverter:
    """λ, μ ızgarası üzerinde (P1, P2[, PÜst2.5]) en yakın komşu ters çevirme (DC rho ile)."""

    def __init__(self, rho: float = -0.05, step: float = 0.02, lo: float = 0.10, hi: float = 4.5) -> None:
        from scipy.spatial import cKDTree

        g = np.arange(lo, hi + 1e-9, step)
        L, M = np.meshgrid(g, g, indexing="ij")
        self.lam, self.mu = L.ravel(), M.ravel()
        mat = dc_matrix(self.lam, self.mu, rho, n=12)
        i, j = np.indices(mat.shape[1:])
        p1 = (mat * (i > j)).sum(axis=(1, 2))
        p2 = (mat * (i < j)).sum(axis=(1, 2))
        po = (mat * (i + j > 2.5)).sum(axis=(1, 2))
        self.tree3 = cKDTree(np.c_[p1, p2, po])
        self.tree2 = cKDTree(np.c_[p1, p2])

    def invert(self, p1: np.ndarray, p2: np.ndarray, po: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        p1, p2 = np.asarray(p1, float), np.asarray(p2, float)
        lam = np.full(len(p1), np.nan)
        mu = np.full(len(p1), np.nan)
        ok2 = np.isfinite(p1) & np.isfinite(p2)
        has_o = ok2 & (np.isfinite(po) if po is not None else np.zeros(len(p1), bool))
        if has_o.any():
            _, idx = self.tree3.query(np.c_[p1[has_o], p2[has_o], np.asarray(po)[has_o]])
            lam[has_o], mu[has_o] = self.lam[idx], self.mu[idx]
        only2 = ok2 & ~has_o
        if only2.any():
            _, idx = self.tree2.query(np.c_[p1[only2], p2[only2]])
            lam[only2], mu[only2] = self.lam[idx], self.mu[idx]
        return lam, mu


# ----------------------------------------------------------------------------------------------
# Kalibrasyon
# ----------------------------------------------------------------------------------------------
def fav_bucket(p_home: np.ndarray, p_away: np.ndarray) -> np.ndarray:
    """0: deplasman favori, 1: dengeli, 2: ev favori (MS olasılık farkına göre)."""
    d = np.asarray(p_home) - np.asarray(p_away)
    return np.where(d < -0.15, 0, np.where(d > 0.15, 2, 1))


def cell_factors(pred: np.ndarray, outcome: np.ndarray, prior: float = 60.0) -> np.ndarray:
    """Hücre çarpanı f_c = (gözlenen + a) / (beklenen + a); a = prior * ortalama hücre payı."""
    k = pred.shape[1]
    obs = np.bincount(outcome, minlength=k).astype(float)
    exp = pred.sum(axis=0)
    a = prior * np.clip(exp / max(exp.sum(), 1e-9), 1e-3, None)
    return (obs + a) / (exp + a)


def apply_cell_factors(pred: np.ndarray, factors: np.ndarray) -> np.ndarray:
    p = pred * factors
    return p / p.sum(axis=1, keepdims=True)


def fit_logit_calibration(p: np.ndarray, y: np.ndarray, l2: float = 1.0) -> tuple[float, float]:
    """y ~ sigmoid(a + b·logit(p)); küçük L2 ile (a=0, b=1 kimliğine büzülür). Newton."""
    p = np.clip(p, 1e-4, 1 - 1e-4)
    x = np.log(p / (1 - p))
    a, b = 0.0, 1.0
    for _ in range(30):
        z = a + b * x
        q = 1 / (1 + np.exp(-z))
        g = np.array([(q - y).sum() + l2 * a, ((q - y) * x).sum() + l2 * (b - 1)])
        wv = q * (1 - q)
        H = np.array([[wv.sum() + l2, (wv * x).sum()], [(wv * x).sum(), (wv * x * x).sum() + l2]])
        step = np.linalg.solve(H, g)
        a, b = a - step[0], b - step[1]
        if np.abs(step).max() < 1e-8:
            break
    return float(a), float(b)


def apply_logit(p: np.ndarray, ab: tuple[float, float]) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    z = ab[0] + ab[1] * np.log(p / (1 - p))
    return 1 / (1 + np.exp(-z))


# ----------------------------------------------------------------------------------------------
# Korner
# ----------------------------------------------------------------------------------------------
def nb_over(mean: np.ndarray, var_mean: np.ndarray | float, line: float) -> np.ndarray:
    """P(T > line), T ~ NB(ort, Var/Ort oranı); oran <= 1 ise Poisson."""
    mean = np.asarray(mean, float)
    vm = np.broadcast_to(np.asarray(var_mean, float), mean.shape)
    k = math.floor(line)
    out = np.empty_like(mean)
    nbm = vm > 1.0 + 1e-6
    if nbm.any():
        r = mean[nbm] / (vm[nbm] - 1.0)
        out[nbm] = nbinom.sf(k, r, r / (r + mean[nbm]))
    if (~nbm).any():
        from scipy.stats import poisson

        out[~nbm] = poisson.sf(k, mean[~nbm])
    return out


# ----------------------------------------------------------------------------------------------
# Canlı kullanım (açık komutla; günlük akışta yok)
# ----------------------------------------------------------------------------------------------
def load_params(path: Path | None = None) -> dict[str, Any]:
    p = path or PARAMS_PATH
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def predict_markets(lam: float, mu: float, *, division: str | None = None, team_share_h: float | None = None,
                    team_share_a: float | None = None, corners: tuple[float, float] | None = None,
                    params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tek maç için kalibre edilmiş yüksek oran pazar olasılıkları (analiz; banko kupona girmez).

    lam, mu: maç sonu gol beklentisi (piyasa/model harmanı). team_share_*: takımın İY gol payı (yoksa lig payı).
    corners: (ev, dep) korner beklentisi.
    """
    P = params if params is not None else load_params()
    hp = P.get("hiperparametre", {})
    rho1, rho2 = hp.get("rho_iy", 0.0), hp.get("rho_2y", 0.0)
    shares = P.get("lig_iy_payi", {})
    share = shares.get(division or "", shares.get("_genel", DEFAULT_FIRST_HALF_SHARE))
    g = float(hp.get("gamma_team", 0.0))
    sh = share + g * ((team_share_h if team_share_h is not None else share) - share)
    sa = share + g * ((team_share_a if team_share_a is not None else share) - share)
    gsm = P.get("durum_carpani", {"ev": [1, 1, 1], "dep": [1, 1, 1]})
    m1 = dc_matrix([lam * sh], [mu * sa], rho1)
    gs = game_state_model(m1, np.array([lam * (1 - sh)]), np.array([mu * (1 - sa)]),
                          np.array([gsm["ev"]], float), np.array([gsm["dep"]], float), rho2)
    mf = gs["ft_matrix"]
    i, j = np.indices(mf.shape[1:])
    p_home, p_away = float((mf[0] * (i > j)).sum()), float((mf[0] * (i < j)).sum())
    b = int(fav_bucket(np.array([p_home]), np.array([p_away]))[0])
    cal = P.get("kalibrasyon", {})
    htft = gs["htft"]
    if "htft" in cal:
        htft = apply_cell_factors(htft, np.asarray(cal["htft"][str(b)]))
    ft = score_classes(mf, FT_SCORES)
    if "skor" in cal:
        ft = apply_cell_factors(ft, np.asarray(cal["skor"]))
    ht = score_classes(m1, HT_SCORES)
    if "iy_skor" in cal:
        ht = apply_cell_factors(ht, np.asarray(cal["iy_skor"]))
    kg2 = gs["kg2"]
    if "kg2" in cal:
        kg2 = apply_logit(kg2, tuple(cal["kg2"]))
    out: dict[str, Any] = {
        "İY/MS": {f"İY/MS {lab}": float(v) for lab, v in zip(HTFT_LABELS, htft[0])},
        "Skor": {**{f"Skor {h}-{a}": float(v) for (h, a), v in zip(FT_SCORES, ft[0])}, "Skor Diğer": float(ft[0, -1])},
        "İY Skor": {**{f"İY Skor {h}-{a}": float(v) for (h, a), v in zip(HT_SCORES, ht[0])},
                    "İY Skor Diğer": float(ht[0, -1])},
        "2Y KG": {"2Y KG Var": float(kg2[0]), "2Y KG Yok": float(1 - kg2[0])},
    }
    if corners is not None:
        vms = P.get("korner_var_ort", {})
        vm = vms.get(division or "", vms.get("_genel", 1.2))
        tot = np.array([sum(corners)])
        out["Korner"] = {}
        for ln in CORNER_LINES:
            po = float(nb_over(tot, vm, ln)[0])
            out["Korner"][f"Korner {ln} Üst"] = po
            out["Korner"][f"Korner {ln} Alt"] = 1 - po
    for grp in out.values():
        for kname, v in list(grp.items()):
            grp[kname] = round(v, 5)
    return out
