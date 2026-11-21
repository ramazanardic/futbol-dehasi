"""
DENEYSEL — ÜRETİMDE KULLANILMAZ (22 Kasım 2026 denetimi).

QuantFoot v8.1 & v8.2 — Yasaksız Yapısal Stokastik Evrim & Çoklu Yapay Zeka (Claude + Gemini)
Çapraz Öğrenme (Cross-AI Self-Learning) Motoru (commit 17bf360).

Durum:
- Hiçbir betik, kupon motoru veya test bu dosyayı içe aktarmaz (ölü kod).
- Sabitler (rejim ağırlıkları 0.820/0.095/0.085, çarpanlar 0.72/0.88/1.18/1.24/0.86, ρ = −0.19/−0.15/−0.09) veriye
  UYDURULMAMIŞTIR; arşivde walk-forward doğrulaması ve birim testi yoktur.
- Bu yüzden çıktısı bir olasılık/fiyat kaynağı olarak kullanılmamalıdır. Kullanılmak istenirse önce
  scripts/pazar_kalibrasyonu.py düzeninde sızıntısız bir arşiv testi gerekir (bkz. docs/research/deneysel_kod.md).
Silinmedi: kullanıcının/diğer yapay zekâların referansı için bırakıldı.
"""
import math

def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def build_structural_tensor_v82(
    lam_h: float,
    lam_a: float,
    is_knockout_90min: bool = False,
    is_heavy_fav_vs_low_block: bool = False,
    is_eliminated_home_open_play: bool = False,
    is_u23_youth_match: bool = False,
    max_goals: int = 8,
):
    if is_heavy_fav_vs_low_block:
        lam_h *= 0.72
        lam_a *= 0.88
    if is_eliminated_home_open_play:
        lam_h *= 1.18
        lam_a *= 1.24
    if is_knockout_90min:
        lam_h *= 0.86
        lam_a *= 0.86

    regimes = [
        (0.820, 1.00, 1.00),
        (0.095, 0.58, 1.38),
        (0.085, 1.36, 0.58),
    ]
    rho = -0.19 if is_knockout_90min else (-0.15 if (lam_h + lam_a) < 2.35 else -0.09)
    regime_matrices = []

    for weight, mult_h, mult_a in regimes:
        lh = max(0.20, lam_h * mult_h)
        la = max(0.20, lam_a * mult_a)
        mat = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
        total = 0.0
        for i in range(max_goals + 1):
            pi = poisson_pmf(i, lh)
            for j in range(max_goals + 1):
                pj = poisson_pmf(j, la)
                tau = 1.0
                if i == 0 and j == 0:
                    tau = 1.0 - lh * la * rho
                elif i == 0 and j == 1:
                    tau = 1.0 + lh * rho
                elif i == 1 and j == 0:
                    tau = 1.0 + la * rho
                elif i == 1 and j == 1:
                    tau = 1.0 - rho
                val = max(0.0, pi * pj * tau)
                mat[i][j] = val
                total += val
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                mat[i][j] /= total

        gamma = 0.24 if (lh + la) >= 2.30 else 0.14
        if is_knockout_90min:
            gamma *= 0.45
        p21 = mat[2][1]
        shift21 = p21 * gamma
        mat[2][1] -= shift21
        mat[3][1] += shift21 * 0.58
        mat[2][2] += shift21 * 0.42

        p12 = mat[1][2]
        shift12 = p12 * gamma
        mat[1][2] -= shift12
        mat[1][3] += shift12 * 0.58
        mat[2][2] += shift12 * 0.42
        regime_matrices.append((weight, mat))

    mix = [[0.0] * (max_goals + 1) for _ in range(max_goals + 1)]
    for w, mat in regime_matrices:
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                mix[i][j] += w * mat[i][j]
    return mix
