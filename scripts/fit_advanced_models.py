"""5 ileri algoritmanın ortak kalibrasyon dosyalarını üretir ve 2024-2026 holdout üzerinde doğrular.

    python scripts/fit_advanced_models.py

Üretilen dosyalar (tüm yapay zekâlar için ortak):
  - data/calibration/club_half_dna.json
  - data/calibration/balanced_residual_lgbm.txt
  - data/calibration/balanced_residual_meta.json
  - data/calibration/score_calibration.json
"""

from __future__ import annotations

from collections import defaultdict
import datetime as dt
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.markets.club_half_dna import (  # noqa: E402
    CALIBRATION_PATH as DNA_PATH,
    PRIOR_1H_SHARE,
    PRIOR_BOTH_HALVES,
    PRIOR_COMEBACK,
    PRIOR_EARLY_SCORE,
    PRIOR_LEAD_HOLD_VULN,
    normalize_club_name,
)
from quantfoot.markets.score_calibrator import (  # noqa: E402
    CALIBRATION_PATH as SCORE_CAL_PATH,
    calibrate_score_distribution,
    classify_score_regime,
)
from quantfoot.models.balanced_residual import fit_balanced_residual, _softmax  # noqa: E402


def _load_half_matches() -> pd.DataFrame:
    """matches.csv (>=2022) + season_2627 CSV dosyalarını tek şemada birleştir ve deduplicate et."""
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    # Önce güncel 2026/27 sezon dosyalarını yükle (öncelik)
    s26_dir = ROOT / "data" / "global_odds" / "latest" / "season_2627"
    if s26_dir.exists():
        for csv_p in sorted(s26_dir.glob("*.csv")):
            try:
                d = pd.read_csv(csv_p)
            except Exception:
                continue
            need = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "HTHG", "HTAG"}
            if not need.issubset(d.columns):
                continue
            for _, r in d.dropna(subset=list(need)).iterrows():
                ds = str(r["Date"]).strip()
                try:
                    dt_iso = dt.datetime.strptime(ds, "%d/%m/%Y" if len(ds.split("/")[-1]) == 4 else "%d/%m/%y").date().isoformat()
                except ValueError:
                    continue
                h_team, a_team = str(r["HomeTeam"]).strip(), str(r["AwayTeam"]).strip()
                key = (dt_iso, normalize_club_name(h_team), normalize_club_name(a_team))
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "date": dt_iso, "home": h_team, "away": a_team,
                    "fh": int(r["FTHG"]), "fa": int(r["FTAG"]),
                    "hh": int(r["HTHG"]), "ha": int(r["HTAG"]),
                })

    df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False)
    sub = df[(df["MatchDate"] >= "2022-01-01") & df["FTHome"].notna() & df["FTAway"].notna() & df["HTHome"].notna() & df["HTAway"].notna()].copy()
    for c in ("FTHome", "FTAway", "HTHome", "HTAway"):
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna(subset=["FTHome", "FTAway", "HTHome", "HTAway"])
    for _, r in sub.iterrows():
        dt_iso = str(r["MatchDate"]).strip()[:10]
        h_team, a_team = str(r["HomeTeam"]).strip(), str(r["AwayTeam"]).strip()
        key = (dt_iso, normalize_club_name(h_team), normalize_club_name(a_team))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "date": dt_iso, "home": h_team, "away": a_team,
            "fh": int(r["FTHome"]), "fa": int(r["FTAway"]),
            "hh": int(r["HTHome"]), "ha": int(r["HTAway"]),
        })

    out = pd.DataFrame(rows)
    out = out.sort_values("date").reset_index(drop=True)
    return out


def build_club_half_dna(half_df: pd.DataFrame) -> dict:
    """Zaman-ağırlıklı (half-life = 365 gün) Empirical Bayes kulüp 1Y/2Y DNA tablosu."""
    ref_date = dt.date.fromisoformat(str(half_df["date"].max()))
    acc: dict[str, dict[str, float | str]] = {}

    def _entry(norm_k: str, orig: str) -> dict:
        if norm_k not in acc:
            acc[norm_k] = {
                "club": orig, "n_eff": 0.0,
                "g1": 0.0, "gtot": 0.0,
                "early_w": 0.0, "lead_w": 0.0, "lead_vuln_w": 0.0,
                "trail_w": 0.0, "comeb_w": 0.0, "bh_w": 0.0,
            }
        return acc[norm_k]

    dates = pd.to_datetime(half_df["date"]).dt.date.tolist()
    for idx, r in half_df.iterrows():
        days_ago = max(0, (ref_date - dates[idx]).days)
        w = math.exp(-math.log(2.0) * days_ago / 365.0)
        fh, fa, hh, ha = int(r["fh"]), int(r["fa"]), int(r["hh"]), int(r["ha"])
        h2_h, h2_a = max(0, fh - hh), max(0, fa - ha)

        for is_home, team in ((True, r["home"]), (False, r["away"])):
            nk = normalize_club_name(team)
            if not nk:
                continue
            d = _entry(nk, str(team))
            d["club"] = str(team)  # en güncel isim kalsın
            gf1, ga1 = (hh, ha) if is_home else (ha, hh)
            gf2, ga2 = (h2_h, h2_a) if is_home else (h2_a, h2_h)
            gf, ga = (fh, fa) if is_home else (fa, fh)

            d["n_eff"] += w
            d["g1"] += w * (gf1 + ga1)
            d["gtot"] += w * (gf + ga)
            if gf1 >= 1:
                d["early_w"] += w
            if gf1 > ga1:
                d["lead_w"] += w
                if ga2 > gf2 or gf <= ga:
                    d["lead_vuln_w"] += w
            if gf1 < ga1:
                d["trail_w"] += w
                if gf2 > ga2 or gf >= ga:
                    d["comeb_w"] += w
            if (gf1 >= 1 or ga1 >= 1) and (gf2 >= 1 or ga2 >= 1) and ((gf1 >= 1 and gf2 >= 1) or (ga1 >= 1 and ga2 >= 1)):
                d["bh_w"] += w

    # Empirical Bayes küçültme (pseudo-match = 18, lead/trail için 10)
    clubs_out: dict[str, dict] = {}
    for nk, d in acc.items():
        n = float(d["n_eff"])
        if n < 3.0:
            continue
        g1, gtot = float(d["g1"]), float(d["gtot"])
        share_1h = (g1 + 35.0 * PRIOR_1H_SHARE) / (gtot + 35.0)
        early = (float(d["early_w"]) + 14.0 * PRIOR_EARLY_SCORE) / (n + 14.0)
        lead_vuln = (float(d["lead_vuln_w"]) + 8.0 * PRIOR_LEAD_HOLD_VULN) / (float(d["lead_w"]) + 8.0)
        comeb = (float(d["comeb_w"]) + 8.0 * PRIOR_COMEBACK) / (float(d["trail_w"]) + 8.0)
        both_h = (float(d["bh_w"]) + 14.0 * PRIOR_BOTH_HALVES) / (n + 14.0)
        clubs_out[nk] = {
            "club": d["club"],
            "n_eff": round(n, 2),
            "first_half_share": round(share_1h, 4),
            "early_score_rate": round(early, 4),
            "lead_hold_vuln": round(lead_vuln, 4),
            "comeback_rate": round(comeb, 4),
            "both_halves_rate": round(both_h, 4),
        }

    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "ref_date": ref_date.isoformat(),
        "n_clubs": len(clubs_out),
        "clubs": clubs_out,
    }
    DNA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DNA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _causal_expanding_features(df: pd.DataFrame) -> pd.DataFrame:
    """Sıfır sızıntılı (causal) maç-bazlı öznitelik tablosu üret (2018-2026)."""
    sub = df[(df["MatchDate"] >= "2018-01-01") & df["OddHome"].notna() & df["OddDraw"].notna() & df["OddAway"].notna() & df["FTResult"].notna()].copy()
    for c in ("OddHome", "OddDraw", "OddAway", "Over25", "HandiSize", "HomeElo", "AwayElo", "Form5Home", "Form5Away", "FTHome", "FTAway", "HTHome", "HTAway"):
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    sub = sub.dropna(subset=["OddHome", "OddDraw", "OddAway", "FTHome", "FTAway"]).sort_values("MatchDate").reset_index(drop=True)

    inv = 1.0 / sub["OddHome"] + 1.0 / sub["OddDraw"] + 1.0 / sub["OddAway"]
    sub["p_mkt_h"] = (1.0 / sub["OddHome"]) / inv
    sub["p_mkt_d"] = (1.0 / sub["OddDraw"]) / inv
    sub["p_mkt_a"] = (1.0 / sub["OddAway"]) / inv
    sub["p_gap_12"] = sub["p_mkt_h"] - sub["p_mkt_a"]
    sub["abs_gap"] = sub["p_gap_12"].abs()
    sub["p_over25"] = (1.0 / sub["Over25"]) / 1.06
    sub["handi_size"] = sub["HandiSize"]
    sub["elo_diff"] = sub["HomeElo"] - sub["AwayElo"]
    sub["form5_diff"] = sub["Form5Home"] - sub["Form5Away"]
    sub["target"] = sub["FTResult"].map({"H": 0, "D": 1, "A": 2})
    sub = sub.dropna(subset=["target"]).copy()
    sub["target"] = sub["target"].astype(int)

    # Expanding kulüp 1Y/comeback geçmişi (maç öncesi kümülatif — gelecek yok!)
    g1_sum = defaultdict(float)
    gtot_sum = defaultdict(float)
    cb_cnt = defaultdict(float)
    tr_cnt = defaultdict(float)
    h1_list = []
    a1_list = []
    cbd_list = []

    for _, r in sub.iterrows():
        hk, ak = normalize_club_name(r["HomeTeam"]), normalize_club_name(r["AwayTeam"])
        h_1h = (g1_sum[hk] + 35.0 * PRIOR_1H_SHARE) / (gtot_sum[hk] + 35.0)
        a_1h = (g1_sum[ak] + 35.0 * PRIOR_1H_SHARE) / (gtot_sum[ak] + 35.0)
        h_cb = (cb_cnt[hk] + 8.0 * PRIOR_COMEBACK) / (tr_cnt[hk] + 8.0)
        a_cb = (cb_cnt[ak] + 8.0 * PRIOR_COMEBACK) / (tr_cnt[ak] + 8.0)
        h1_list.append(h_1h)
        a1_list.append(a_1h)
        cbd_list.append(h_cb - a_cb)

        # Maç sonrası güncelle
        if pd.notna(r["HTHome"]) and pd.notna(r["HTAway"]):
            hh, ha = float(r["HTHome"]), float(r["HTAway"])
            fh, fa = float(r["FTHome"]), float(r["FTAway"])
            tot = fh + fa
            g1 = hh + ha
            g1_sum[hk] += g1
            gtot_sum[hk] += tot
            g1_sum[ak] += g1
            gtot_sum[ak] += tot
            if hh < ha:
                tr_cnt[hk] += 1.0
                if fh >= fa or (fh - hh) > (fa - ha):
                    cb_cnt[hk] += 1.0
            if ha < hh:
                tr_cnt[ak] += 1.0
                if fa >= fh or (fa - ha) > (fh - hh):
                    cb_cnt[ak] += 1.0

    sub["club_h_1h"] = h1_list
    sub["club_a_1h"] = a1_list
    sub["club_cb_diff"] = cbd_list
    return sub


def _quick_score_matrix(p1: float, px: float, p2: float, p_o25: float | None) -> dict[str, float]:
    """Hızlı Poisson+Dixon-Coles tabanlı 7x7 FT skor dağılımı (1X2 ve O2.5 uyumlu)."""
    mu_tot = 2.45
    if p_o25 is not None and math.isfinite(p_o25):
        # 2.5 Üst olasılığından toplam lambda tersleme
        lo, hi = 0.8, 5.2
        for _ in range(18):
            mid = 0.5 * (lo + hi)
            p_cand = 1.0 - math.exp(-mid) * (1.0 + mid + 0.5 * mid * mid)
            if p_cand < p_o25:
                lo = mid
            else:
                hi = mid
        mu_tot = 0.5 * (lo + hi)
    share_h = float(np.clip(0.5 + 0.58 * (p1 - p2), 0.16, 0.84))
    mh = max(0.15, mu_tot * share_h)
    ma = max(0.15, mu_tot - mh)
    ph = [math.exp(-mh) * (mh ** i) / math.factorial(i) for i in range(7)]
    pa = [math.exp(-ma) * (ma ** j) / math.factorial(j) for j in range(7)]
    dist = {}
    rho = -0.05
    tot = 0.0
    for i in range(7):
        for j in range(7):
            p = ph[i] * pa[j]
            if i == 0 and j == 0:
                p *= max(0.2, 1.0 - mh * ma * rho)
            elif i == 1 and j == 0:
                p *= max(0.2, 1.0 + ma * rho)
            elif i == 0 and j == 1:
                p *= max(0.2, 1.0 + mh * rho)
            elif i == 1 and j == 1:
                p *= max(0.2, 1.0 - rho)
            dist[f"{i}-{j}"] = p
            tot += p
    return {k: v / tot for k, v in dist.items()}


def fit_and_eval_score_calibration(feat_df: pd.DataFrame) -> dict:
    """2018-2023 eğitiminden 6-rejimli Empirical Bayes skor çarpanlarını öğren ve 2024-2026 holdout'ta test et."""
    tr = feat_df[feat_df["MatchDate"] < "2024-01-01"].copy()
    ho = feat_df[feat_df["MatchDate"] >= "2024-01-01"].copy()

    exp_sum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    obs_sum: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    reg_cnt: dict[str, int] = defaultdict(int)

    for _, r in tr.iterrows():
        p1, px, p2 = float(r["p_mkt_h"]), float(r["p_mkt_d"]), float(r["p_mkt_a"])
        po = float(r["p_over25"]) if pd.notna(r["p_over25"]) else None
        reg = classify_score_regime(p1, px, p2, po)
        reg_cnt[reg] += 1
        dist = _quick_score_matrix(p1, px, p2, po)
        for sc, p in dist.items():
            exp_sum[reg][sc] += p
        act_sc = f"{int(r['FTHome'])}-{int(r['FTAway'])}"
        if act_sc in dist:
            obs_sum[reg][act_sc] += 1.0

    # Empirical Bayes çarpan: (obs + 30 * (exp/n)*n? -> (obs + prior_exp) / (exp + prior_exp) where prior_exp = 25)
    regimes_out: dict[str, dict] = {}
    for reg, n in reg_cnt.items():
        mults: dict[str, float] = {}
        for sc, e_val in exp_sum[reg].items():
            o_val = obs_sum[reg].get(sc, 0.0)
            if e_val >= 8.0:
                ratio = (o_val + 25.0) / (e_val + 25.0)
                mults[sc] = round(float(np.clip(ratio, 0.72, 1.38)), 4)
        regimes_out[reg] = {"n": int(n), "multipliers": mults}

    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "train_n": int(len(tr)),
        "regimes": regimes_out,
    }
    SCORE_CAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCORE_CAL_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # 2024-2026 holdout doğrulaması
    ll_raw, ll_cal = [], []
    top1_raw = top1_cal = top3_raw = top3_cal = 0
    for _, r in ho.iterrows():
        p1, px, p2 = float(r["p_mkt_h"]), float(r["p_mkt_d"]), float(r["p_mkt_a"])
        po = float(r["p_over25"]) if pd.notna(r["p_over25"]) else None
        dist_raw = _quick_score_matrix(p1, px, p2, po)
        dist_cal = calibrate_score_distribution(dist_raw, (p1, px, p2), po, table=payload)
        act_sc = f"{int(r['FTHome'])}-{int(r['FTAway'])}"
        p_r = max(1e-6, dist_raw.get(act_sc, 1e-4))
        p_c = max(1e-6, dist_cal.get(act_sc, 1e-4))
        ll_raw.append(-math.log(p_r))
        ll_cal.append(-math.log(p_c))
        r_sorted = [k for k, _ in sorted(dist_raw.items(), key=lambda x: -x[1])]
        c_sorted = [k for k, _ in sorted(dist_cal.items(), key=lambda x: -x[1])]
        if r_sorted[0] == act_sc:
            top1_raw += 1
        if c_sorted[0] == act_sc:
            top1_cal += 1
        if act_sc in r_sorted[:3]:
            top3_raw += 1
        if act_sc in c_sorted[:3]:
            top3_cal += 1

    n_ho = max(1, len(ho))
    return {
        "holdout_n": len(ho),
        "raw_logloss": round(float(np.mean(ll_raw)), 5),
        "cal_logloss": round(float(np.mean(ll_cal)), 5),
        "raw_top1_pct": round(top1_raw / n_ho * 100.0, 2),
        "cal_top1_pct": round(top1_cal / n_ho * 100.0, 2),
        "raw_top3_pct": round(top3_raw / n_ho * 100.0, 2),
        "cal_top3_pct": round(top3_cal / n_ho * 100.0, 2),
    }


def main() -> None:
    print("1/3 Kulüp 1Y/2Y DNA tablosu oluşturuluyor...")
    half_df = _load_half_matches()
    dna_payload = build_club_half_dna(half_df)
    print(f"  -> {dna_payload['n_clubs']} kulüp yazıldı ({DNA_PATH})")

    print("2/3 Dengeli 1X2 LightGBM Residual eğitiliyor (2018-2023 -> holdout 2024-2026)...")
    raw_df = pd.read_csv(ROOT / "data" / "matches.csv", low_memory=False)
    feat_df = _causal_expanding_features(raw_df)
    tr_df = feat_df[feat_df["MatchDate"] < "2023-01-01"].copy()
    va_df = feat_df[(feat_df["MatchDate"] >= "2023-01-01") & (feat_df["MatchDate"] < "2024-01-01")].copy()
    ho_df = feat_df[feat_df["MatchDate"] >= "2024-01-01"].copy()

    # Dengeli maç alt-kümesinde eğitim + doğrulama mı, tüm maçlarda eğitip dengelide doğrulama mı?
    # Tüm maçlarda residual eğitip doğrulamayı dengeli + genel Brier karışımında optimize etmek daha kararlıdır.
    meta = fit_balanced_residual(tr_df, va_df)
    print("  meta:", meta)

    # 2024-2026 holdout Brier kontrolü (tüm + dengeli alt küme)
    from quantfoot.models.balanced_residual import FEATURE_NAMES, load_balanced_residual
    booster, alpha = load_balanced_residual()
    for lbl, sub in (("Holdout Tümü", ho_df), ("Holdout Dengeli", ho_df[ho_df["OddHome"].between(1.85, 3.05) & ho_df["OddAway"].between(1.85, 3.05)])):
        p_mkt = np.clip(sub[["p_mkt_h", "p_mkt_d", "p_mkt_a"]].to_numpy(dtype=float), 0.02, 0.96)
        p_mkt = p_mkt / p_mkt.sum(axis=1, keepdims=True)
        y_oh = np.eye(3, dtype=float)[sub["target"].to_numpy(dtype=int)]
        b_base = float(np.mean(np.sum((p_mkt - y_oh) ** 2, axis=1)))
        if booster is not None and alpha > 0:
            raw = np.clip(booster.predict(sub[list(FEATURE_NAMES)].to_numpy(dtype=float), raw_score=True), -0.40, 0.40)
            p_res = _softmax(np.log(p_mkt) + alpha * raw)
            b_res = float(np.mean(np.sum((p_res - y_oh) ** 2, axis=1)))
        else:
            b_res = b_base
        print(f"  {lbl:16s} (n={len(sub):5d}): Market Brier={b_base:.6f} -> Residual Brier={b_res:.6f} (diff={b_res-b_base:+.6f})")

    print("3/3 Multinomial Skor Kalibrasyonu eğitiliyor (2018-2023 -> holdout 2024-2026)...")
    sc_eval = fit_and_eval_score_calibration(feat_df)
    print("  Score holdout:", sc_eval)


if __name__ == "__main__":
    main()
