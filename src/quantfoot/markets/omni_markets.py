"""Omni-market probability engine covering all FT, 1H, 2H, HT/FT, Goal Band, BTTS, and Exact Score markets."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from quantfoot.markets.halves_btts import compute_halves_btts, half_model_params
from quantfoot.markets.tail_goals import (
    _apply_dixon_coles_low_scores,
    com_poisson_pmf,
    league_tail_regime,
    regime_score_matrix,
)

HTFT_OUTCOMES: tuple[str, ...] = (
    "1/1", "1/0", "1/2",
    "0/1", "0/0", "0/2",
    "2/1", "2/0", "2/2",
)


def _outcome_idx(h: int, a: int) -> int:
    if h > a:
        return 0  # '1'
    if h == a:
        return 1  # '0'
    return 2      # '2'


def _safe_fair_odds(prob: float) -> float:
    return round(float(1.0 / prob), 2) if prob > 1e-6 else 9999.0


@dataclass(frozen=True)
class OmniMarketBundle:
    """Complete probability distribution across all standard and derivative football betting markets."""

    mu_home: float
    mu_away: float
    expected_total: float
    exp_1h_home: float
    exp_1h_away: float
    exp_1h_total: float
    exp_2h_home: float
    exp_2h_away: float
    exp_2h_total: float
    ft_1x2: dict[str, float]
    double_chance: dict[str, float]
    ht_1x2: dict[str, float]
    h2_1x2: dict[str, float]
    ht_ft: dict[str, float]
    goal_bands: dict[str, float]
    ft_ou: dict[str, float]
    ht_ou: dict[str, float]
    h2_ou: dict[str, float]
    btts: dict[str, float]
    combos: dict[str, float]
    top_ft_scores: list[dict[str, float | str]]
    top_ht_scores: list[dict[str, float | str]]
    top2_score_cluster: dict[str, float | list[str]]
    top3_score_cluster: dict[str, float | list[str]]
    score_entropy: float
    # Coherent joint goal distribution J[h1, a1, h2, a2] (1st-half and 2nd-half goals per team).
    # Its full-time score marginal equals the FT matrix and its 1H marginal equals the HT matrix,
    # so every goal-based market and same-game combination can be priced exactly from it.
    joint: np.ndarray | None = field(default=None, repr=False, compare=False)

    def all_probabilities(self) -> dict[str, float]:
        """Return a flat dictionary of all market selection probabilities."""
        out: dict[str, float] = {}
        for k, v in self.ft_1x2.items():
            out[f"MS {k}"] = v
        for k, v in self.double_chance.items():
            out[f"ÇŞ {k}"] = v
        out.update(self.ht_1x2)
        out.update(self.h2_1x2)
        for k, v in self.ht_ft.items():
            out[f"İY/MS {k}"] = v
        out.update(self.goal_bands)
        out.update(self.ft_ou)
        out.update(self.ht_ou)
        out.update(self.h2_ou)
        out.update(self.btts)
        out.update(self.combos)
        return out


def rake_joint_to_margins(
    joint: np.ndarray,
    target_ft: np.ndarray,
    target_ht: np.ndarray,
    max_iter: int = 300,
    tol: float = 1e-10,
) -> np.ndarray:
    """Iterative proportional fitting of J[h1, a1, h2, a2] to a full-time and a half-time score margin.

    The FT margin is the distribution of (h1 + h2, a1 + a2); the HT margin is (h1, a1).
    `target_ft` must be (2G-1) x (2G-1) for a G x G x G x G joint.
    """
    g = joint.shape[0]
    n = 2 * g - 1
    if target_ft.shape != (n, n):
        raise ValueError(f"target_ft must have shape {(n, n)}, got {target_ft.shape}")
    i1, j1, i2, j2 = np.indices(joint.shape)
    ft_idx = ((i1 + i2) * n + (j1 + j2)).ravel()
    ht_idx = (i1 * g + j1).ravel()
    tgt_ft = (target_ft / target_ft.sum()).ravel()
    tgt_ht = (target_ht / target_ht.sum()).ravel()
    flat = joint.ravel().astype(float).copy()
    flat /= flat.sum()
    for _ in range(max_iter):
        cur_ft = np.bincount(ft_idx, flat, minlength=n * n)
        flat *= np.divide(tgt_ft, cur_ft, out=np.zeros_like(tgt_ft), where=cur_ft > 0)[ft_idx]
        cur_ht = np.bincount(ht_idx, flat, minlength=g * g)
        flat *= np.divide(tgt_ht, cur_ht, out=np.zeros_like(tgt_ht), where=cur_ht > 0)[ht_idx]
        if np.max(np.abs(np.bincount(ft_idx, flat, minlength=n * n) - tgt_ft)) < tol:
            break
    flat /= flat.sum()
    return flat.reshape(joint.shape)


def compute_omni_markets(
    mu_home: float,
    mu_away: float,
    league: str | None = None,
    ft_matrix: np.ndarray | None = None,
    first_half_share: float | None = None,
    home_1h_urgency_shift: float = 0.0,
    away_1h_urgency_shift: float = 0.0,
    max_half_goals: int = 7,
    max_ft_goals: int = 14,
) -> OmniMarketBundle:
    """Compute unified probabilities across all FT, 1H, 2H, HT/FT, Goal Band, BTTS, and Exact Score markets.

    Uses empirically calibrated (184,276 matches) first-half goal shares, mean-conserving
    second-half game-state elasticity (trailing team urgency & 0-0 tactical lock), and
    15x15 tail-preserving full-time matrices.
    """
    mu_h = float(max(0.05, mu_home))
    mu_a = float(max(0.05, mu_away))

    a1_base, match_kappa, half_alpha, fgm_1h, fgm_2h = half_model_params(league)
    com_nu, alpha_nb, shared_kappa = league_tail_regime(league)

    if first_half_share is not None:
        a1_base = float(np.clip(first_half_share, 0.30, 0.55))

    # Empirical home vs away 1H split (+0.0023 home / -0.0023 away around a1_base) + urgency shifts
    a1_h = float(np.clip(a1_base + 0.0023 + home_1h_urgency_shift, 0.28, 0.58))
    a1_a = float(np.clip(a1_base - 0.0023 + away_1h_urgency_shift, 0.28, 0.58))

    lam1_h = max(0.02, mu_h * a1_h)
    lam1_a = max(0.02, mu_a * a1_a)
    lam2_h_base = max(0.02, mu_h * (1.0 - a1_h))
    lam2_a_base = max(0.02, mu_a * (1.0 - a1_a))

    # 1. Full-Time 15x15 score matrix (preserving tail goals 0..14 and Dixon-Coles low-score rho)
    if ft_matrix is not None:
        mat_ft = np.asarray(ft_matrix, dtype=float)
        mat_ft = mat_ft / mat_ft.sum()
    else:
        mat_ft = regime_score_matrix(
            mu_h,
            mu_a,
            alpha_nb=alpha_nb,
            rho=-0.07,
            shared_kappa=shared_kappa,
            com_nu=com_nu,
            max_goals=max_ft_goals,
        )

    # 2. First-Half score matrix (0..max_half_goals)
    nu_half = com_nu if com_nu is not None else 1.0
    p1_h = com_poisson_pmf(lam1_h, nu_half, max_half_goals)
    p1_a = com_poisson_pmf(lam1_a, nu_half, max_half_goals)
    mat_1h = np.outer(p1_h, p1_a)
    if abs(fgm_1h) > 1e-6:
        # Binary FGM scores matching halves_btts: P(both score) = ph*pa*(1 + fgm*p0_h*p0_a)
        s1_h = np.where(np.arange(max_half_goals + 1) == 0, -(1.0 - p1_h[0]), p1_h[0])
        s1_a = np.where(np.arange(max_half_goals + 1) == 0, -(1.0 - p1_a[0]), p1_a[0])
        cop1 = np.clip(1.0 + fgm_1h * np.outer(s1_h, s1_a), 0.25, 2.5)
        mat_1h = mat_1h * cop1
    mat_1h /= mat_1h.sum()

    # 3. Mean-conserving game-state conditional 2H matrices for 9-way HT/FT & 2H markets
    raw_mults = {
        "00": (0.965, 0.955),       # 0-0 at HT reflects tighter defensive lock
        "tied_g": (1.025, 1.025),   # 1-1+ at HT reflects open transition tempo
        "h_plus1": (0.960, 1.095),  # Home +1 at HT -> Away pushes harder in 2H (1/0, 1/2)
        "a_plus1": (1.105, 0.955),  # Away +1 at HT -> Home pushes harder in 2H (2/0, 2/1)
        "h_plus2": (1.030, 0.990),
        "a_plus2": (0.990, 1.040),
    }

    G = max_half_goals + 1
    state_probs = {k: 0.0 for k in raw_mults}
    for i1 in range(G):
        for j1 in range(G):
            if i1 == 0 and j1 == 0:
                sk = "00"
            elif i1 == j1:
                sk = "tied_g"
            elif i1 - j1 == 1:
                sk = "h_plus1"
            elif j1 - i1 == 1:
                sk = "a_plus1"
            elif i1 - j1 >= 2:
                sk = "h_plus2"
            else:
                sk = "a_plus2"
            state_probs[sk] += float(mat_1h[i1, j1])

    norm_h = 1.0 / max(sum(state_probs[k] * raw_mults[k][0] for k in raw_mults), 1e-6)
    norm_a = 1.0 / max(sum(state_probs[k] * raw_mults[k][1] for k in raw_mults), 1e-6)

    mats_2h: dict[str, np.ndarray] = {}
    dc_2h = -0.04
    for sk, (mh, ma) in raw_mults.items():
        l2h = lam2_h_base * mh * norm_h
        l2a = lam2_a_base * ma * norm_a
        p2h = com_poisson_pmf(l2h, nu_half, max_half_goals)
        p2a = com_poisson_pmf(l2a, nu_half, max_half_goals)
        # Dixon-Coles: tau(1,0) = 1 + mu_away*rho, tau(0,1) = 1 + mu_home*rho (shared implementation)
        m2 = _apply_dixon_coles_low_scores(np.outer(p2h, p2a), l2h, l2a, dc_2h)
        m2 /= m2.sum()
        mats_2h[sk] = m2

    # Joint J[h1, a1, h2, a2] = P(1H score) * P(2H score | 1H game state)
    joint = np.zeros((G, G, G, G), dtype=float)
    for i1 in range(G):
        for j1 in range(G):
            if i1 == 0 and j1 == 0:
                sk = "00"
            elif i1 == j1:
                sk = "tied_g"
            elif i1 - j1 == 1:
                sk = "h_plus1"
            elif j1 - i1 == 1:
                sk = "a_plus1"
            elif i1 - j1 >= 2:
                sk = "h_plus2"
            else:
                sk = "a_plus2"
            joint[i1, j1] = float(mat_1h[i1, j1]) * mats_2h[sk]

    # Rake the joint so its FT score margin equals mat_ft and its 1H margin equals mat_1h.
    n_ft = 2 * G - 1
    target_ft = np.zeros((n_ft, n_ft), dtype=float)
    k_ft = min(n_ft, mat_ft.shape[0], mat_ft.shape[1])
    target_ft[:k_ft, :k_ft] = mat_ft[:k_ft, :k_ft]
    joint = rake_joint_to_margins(joint, target_ft, mat_1h)

    mat_2h = joint.sum(axis=(0, 1))
    i1g, j1g, i2g, j2g = np.indices(joint.shape)
    ht_code = np.sign(i1g - j1g)
    ft_code = np.sign((i1g + i2g) - (j1g + j2g))
    order = (1, 0, -1)  # rows/cols: '1', '0', '2'
    htft_aligned = np.array(
        [[float(joint[(ht_code == r) & (ft_code == c)].sum()) for c in order] for r in order]
    )
    # FT markets below read the raked joint's FT margin (identical to mat_ft up to truncation).
    mat_ft = target_ft / target_ft.sum()
    p_ft_1 = float(np.sum(np.tril(mat_ft, k=-1)))
    p_ft_0 = float(np.trace(mat_ft))
    p_ft_2 = float(np.sum(np.triu(mat_ft, k=1)))

    # 4. Extract 1X2, Double Chance, HT 1X2, 2H 1X2, and HT/FT
    ft_1x2 = {
        "1": round(p_ft_1, 4),
        "0": round(p_ft_0, 4),
        "2": round(p_ft_2, 4),
    }
    double_chance = {
        "10": round(p_ft_1 + p_ft_0, 4),
        "12": round(p_ft_1 + p_ft_2, 4),
        "02": round(p_ft_0 + p_ft_2, 4),
    }

    p_ht_1 = float(np.sum(np.tril(mat_1h, k=-1)))
    p_ht_0 = float(np.trace(mat_1h))
    p_ht_2 = float(np.sum(np.triu(mat_1h, k=1)))
    ht_1x2 = {
        "İY 1": round(p_ht_1, 4),
        "İY 0": round(p_ht_0, 4),
        "İY 2": round(p_ht_2, 4),
    }

    p_h2_1 = float(np.sum(np.tril(mat_2h, k=-1)))
    p_h2_0 = float(np.trace(mat_2h))
    p_h2_2 = float(np.sum(np.triu(mat_2h, k=1)))
    h2_1x2 = {
        "2Y 1": round(p_h2_1, 4),
        "2Y 0": round(p_h2_0, 4),
        "2Y 2": round(p_h2_2, 4),
    }

    ht_codes = ("1", "0", "2")
    ht_ft = {
        f"{ht_codes[r]}/{ht_codes[c]}": round(float(htft_aligned[r, c]), 4)
        for r in range(3)
        for c in range(3)
    }

    # 5. Goal Bands & Over/Under (FT, 1H, 2H)
    ft_grid = np.add.outer(np.arange(mat_ft.shape[0]), np.arange(mat_ft.shape[1]))
    goal_bands = {
        "0-1 Gol": round(float(mat_ft[ft_grid <= 1].sum()), 4),
        "2-3 Gol": round(float(mat_ft[(ft_grid >= 2) & (ft_grid <= 3)].sum()), 4),
        "3-5 Gol": round(float(mat_ft[(ft_grid >= 3) & (ft_grid <= 5)].sum()), 4),
        "2-4 Gol": round(float(mat_ft[(ft_grid >= 2) & (ft_grid <= 4)].sum()), 4),
        "4-5 Gol": round(float(mat_ft[(ft_grid >= 4) & (ft_grid <= 5)].sum()), 4),
        "+6 Gol": round(float(mat_ft[ft_grid >= 6].sum()), 4),
    }

    ft_ou: dict[str, float] = {}
    for line in (1.5, 2.5, 3.5, 4.5, 5.5):
        p_ov = float(mat_ft[ft_grid > line].sum())
        ft_ou[f"{line:.1f} Üst"] = round(p_ov, 4)
        ft_ou[f"{line:.1f} Alt"] = round(1.0 - p_ov, 4)

    h1_grid = np.add.outer(np.arange(mat_1h.shape[0]), np.arange(mat_1h.shape[1]))
    ht_ou: dict[str, float] = {}
    for line in (0.5, 1.5, 2.5):
        p_ov = float(mat_1h[h1_grid > line].sum())
        ht_ou[f"İY {line:.1f} Üst"] = round(p_ov, 4)
        ht_ou[f"İY {line:.1f} Alt"] = round(1.0 - p_ov, 4)

    h2_grid = np.add.outer(np.arange(mat_2h.shape[0]), np.arange(mat_2h.shape[1]))
    h2_ou: dict[str, float] = {}
    for line in (0.5, 1.5, 2.5):
        p_ov = float(mat_2h[h2_grid > line].sum())
        h2_ou[f"2Y {line:.1f} Üst"] = round(p_ov, 4)
        h2_ou[f"2Y {line:.1f} Alt"] = round(1.0 - p_ov, 4)

    # 6. BTTS (FT, 1H, 2H, 1H & 2H) using calibrated QuantFoot-v5 halves_btts engine
    hb = compute_halves_btts(
        mu_h,
        mu_a,
        first_half_share=0.5 * (a1_h + a1_a),
        match_kappa=match_kappa,
        half_alpha=half_alpha,
        fgm_1h=fgm_1h,
        fgm_2h=fgm_2h,
    )
    p_ft_kg = float(mat_ft[1:, 1:].sum())
    btts = {
        "KG Var": round(p_ft_kg, 4),
        "KG Yok": round(1.0 - p_ft_kg, 4),
        "1. Yarı KG Var": round(hb.p_1h_kg, 4),
        "1. Yarı KG Yok": round(1.0 - hb.p_1h_kg, 4),
        "2. Yarı KG Var": round(hb.p_2h_kg, 4),
        "2. Yarı KG Yok": round(1.0 - hb.p_2h_kg, 4),
        "1Y ve 2Y KG Var": round(hb.p_both_halves_kg, 4),
        "En Az Bir Devre KG Var": round(hb.p_either_half_kg, 4),
    }

    # 7. Popular Combo Markets
    h_idx = np.arange(mat_ft.shape[0])[:, None]
    a_idx = np.arange(mat_ft.shape[1])[None, :]
    ms1_mask = h_idx > a_idx
    ms2_mask = a_idx > h_idx
    kg_yes_mask = (h_idx >= 1) & (a_idx >= 1)
    kg_no_mask = ~kg_yes_mask

    combos = {
        "MS 1 & 1.5 Üst": round(float(mat_ft[ms1_mask & (ft_grid >= 2)].sum()), 4),
        "MS 2 & 1.5 Üst": round(float(mat_ft[ms2_mask & (ft_grid >= 2)].sum()), 4),
        "MS 1 & 2.5 Üst": round(float(mat_ft[ms1_mask & (ft_grid >= 3)].sum()), 4),
        "MS 2 & 2.5 Üst": round(float(mat_ft[ms2_mask & (ft_grid >= 3)].sum()), 4),
        "MS 1 & KG Yok": round(float(mat_ft[ms1_mask & kg_no_mask].sum()), 4),
        "MS 2 & KG Yok": round(float(mat_ft[ms2_mask & kg_no_mask].sum()), 4),
        "2.5 Alt & KG Yok": round(float(mat_ft[(ft_grid <= 2) & kg_no_mask].sum()), 4),
        "2.5 Üst & KG Var": round(float(mat_ft[(ft_grid >= 3) & kg_yes_mask].sum()), 4),
    }

    # 8. Exact Score Ranking, Clusters, and Shannon Score Entropy
    ft_flat = [
        (f"{i}-{j}", float(mat_ft[i, j]))
        for i in range(mat_ft.shape[0])
        for j in range(mat_ft.shape[1])
    ]
    ft_flat.sort(key=lambda x: x[1], reverse=True)
    top_ft_scores = [
        {"score": sc, "prob": round(p, 4), "fair_odds": _safe_fair_odds(p)}
        for sc, p in ft_flat[:8]
    ]

    ht_flat = [
        (f"{i}-{j}", float(mat_1h[i, j]))
        for i in range(mat_1h.shape[0])
        for j in range(mat_1h.shape[1])
    ]
    ht_flat.sort(key=lambda x: x[1], reverse=True)
    top_ht_scores = [
        {"score": sc, "prob": round(p, 4), "fair_odds": _safe_fair_odds(p)}
        for sc, p in ht_flat[:6]
    ]

    p_top2 = float(sum(p for _, p in ft_flat[:2]))
    p_top3 = float(sum(p for _, p in ft_flat[:3]))
    top2_cluster = {
        "scores": [sc for sc, _ in ft_flat[:2]],
        "prob": round(p_top2, 4),
        "fair_odds": _safe_fair_odds(p_top2),
    }
    top3_cluster = {
        "scores": [sc for sc, _ in ft_flat[:3]],
        "prob": round(p_top3, 4),
        "fair_odds": _safe_fair_odds(p_top3),
    }

    nonzero = mat_ft[mat_ft > 1e-12]
    entropy = float(-np.sum(nonzero * np.log(nonzero)))

    exp_ft_h = float(np.sum(h_idx * mat_ft))
    exp_ft_a = float(np.sum(a_idx * mat_ft))
    exp_1h_h = float(np.sum(np.arange(mat_1h.shape[0])[:, None] * mat_1h))
    exp_1h_a = float(np.sum(np.arange(mat_1h.shape[1])[None, :] * mat_1h))
    exp_2h_h = float(np.sum(np.arange(mat_2h.shape[0])[:, None] * mat_2h))
    exp_2h_a = float(np.sum(np.arange(mat_2h.shape[1])[None, :] * mat_2h))

    return OmniMarketBundle(
        mu_home=round(exp_ft_h, 3),
        mu_away=round(exp_ft_a, 3),
        expected_total=round(exp_ft_h + exp_ft_a, 3),
        exp_1h_home=round(exp_1h_h, 3),
        exp_1h_away=round(exp_1h_a, 3),
        exp_1h_total=round(exp_1h_h + exp_1h_a, 3),
        exp_2h_home=round(exp_2h_h, 3),
        exp_2h_away=round(exp_2h_a, 3),
        exp_2h_total=round(exp_2h_h + exp_2h_a, 3),
        ft_1x2=ft_1x2,
        double_chance=double_chance,
        ht_1x2=ht_1x2,
        h2_1x2=h2_1x2,
        ht_ft=ht_ft,
        goal_bands=goal_bands,
        ft_ou=ft_ou,
        ht_ou=ht_ou,
        h2_ou=h2_ou,
        btts=btts,
        combos=combos,
        top_ft_scores=top_ft_scores,
        top_ht_scores=top_ht_scores,
        top2_score_cluster=top2_cluster,
        top3_score_cluster=top3_cluster,
        score_entropy=round(entropy, 4),
        joint=joint,
    )
