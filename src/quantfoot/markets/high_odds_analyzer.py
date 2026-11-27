"""Yüksek oranlı dengeli 1X2, 1/2 & 2/1 geri dönüş ve 6-Altın-Skor uzman analiz motoru.

240.240 maçlık tarihsel veri (2018-2026: 65.669 modern maç + 11.141 dengeli 1X2 maç) ve
günlük canlı bülten/araştırma sinyalleri üzerine kuruldu:

1. Dengeli / yüksek oranlı 1X2 (`MS 1 / X / 2`, ör. 2.20 / 3.30 / 2.55):
   * 11.141 dengeli maçta düşük tempolu (2.5 Üst >= 2.10) karşılaşmalarda beraberlik piyasanın
     +3,5 puan üstünde (%33,7 vs %30,2); açık tempolu maçlarda ise beraberlik %27,0'a düşer.
   * Favori pozisyonda görünüp (sıralama / form üstünlüğü) piyasada hâlâ dengeli oran alan
     ev sahiplerinde ("tuzak favori") ev galibiyeti zayıflar ve beraberlik artı değer üretir.
   * Keskin borsa akışı (`steam_1x2`), kaleci/golcü/savunma eksikleri, dinlenme farkı,
     bağımsız xG uyumu ve hava durumu Bayesian log-odds katmanında birleştirilir. Çelişki
     veya marj baskısı varsa dürüstçe `PAS (Yazı-Tura)` üretilir.

2. 1/2 ve 2/1 geri dönüş (`İY/MS 1/2`, `İY/MS 2/1`) + devre dönüşü (`İY 1 & 2Y 2`, `İY 2 & 2Y 1`):
   * 65.669 modern maçta deplasman favori (p2 >= 0.50) + açık tempo (2.5 Üst < 1.65)
     maçlarında `İY/MS 1/2` oranı %4,07'ye (genel ortalamanın 1,82 katı) çıkar.
   * Ev favori (p1 >= 0.55) + açık tempo maçlarında `İY/MS 2/1` oranı %3,88'e (1,44 katı) çıkar.
   * Dengeli + açık maçlarda devre dönüşü (`İY 1 & 2Y 2` / `İY 2 & 2Y 1`) ~%11,0 gerçekleşir.
   * Takım geçmişinin 1. yarı vs 2. yarı gol atma/yeme asimetrisi + `league_comeback_rates`
     harmanı ile adaylar 0-100 DNA puanı ve gerçek Nesine EV'siyle sıralanır.

3. 6 Altın Skor (`1-0, 0-1, 2-0, 0-2, 2-1, 1-2`) + canlı Nesine MTID 777 skor EV'si:
   * `rank_macro_coherent_scores` çıktısını canlı Nesine skor oranlarıyla eşleştirir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import datetime as dt
import math
from typing import Any

from quantfoot.markets.club_half_dna import lookup_club_dna
from quantfoot.markets.extreme_goals import _absences, _extract_history_metrics, _extract_sim_xg
from quantfoot.markets.league_halves import league_comeback_rates, league_first_half_share
from quantfoot.markets.market_diagnosis import parse_steam_pp, rank_macro_coherent_scores
from quantfoot.markets.score_calibrator import (
    ScoreDutchingPlan,
    calibrate_score_distribution,
    optimize_score_dutching,
)
from quantfoot.models.balanced_residual import predict_balanced_residual

GOLDEN_SCORES: frozenset[str] = frozenset({"1-0", "0-1", "2-0", "0-2", "2-1", "1-2"})


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _form_points(form: str | None) -> float | None:
    """'WDLWW' -> son 5 maç puanı (0..15)."""
    if not form or not isinstance(form, str):
        return None
    pts = {"W": 3.0, "G": 3.0, "D": 1.0, "B": 1.0, "L": 0.0, "M": 0.0}
    vals = [pts[ch] for ch in form.upper() if ch in pts]
    if len(vals) < 3:
        return None
    return sum(vals) * (5.0 / len(vals))


def _team_rank(res: Mapping[str, Any], side: str) -> int | None:
    teams = res.get("teams") or {}
    tm = res.get("tm_absences") or {}
    tab = (teams.get(side) or {}).get("table") or {}
    rk = _flt(tab.get("rank"))
    if rk is None:
        rk = _flt((tm.get(side) or {}).get("rank"))
    return int(rk) if rk is not None and rk > 0 else None


def _team_xg_avg(res: Mapping[str, Any], side: str) -> float | None:
    """FotMob veya ESPN team_stats içinden maç başı xG veya şut gücünü al."""
    fm = res.get("fotmob") or {}
    fm_stats = (fm.get("stats") or {}).get(side) or {}
    if _flt(fm_stats.get("xg")) is not None:
        return _flt(fm_stats.get("xg"))
    t_stats = ((res.get("teams") or {}).get(side) or {}).get("team_stats") or {}
    for k, v in t_stats.items():
        if "xg" in str(k).lower() and "xga" not in str(k).lower():
            val = _flt(str(v).split()[0].replace(",", "."))
            if val is not None:
                return val
    return None


@dataclass(frozen=True)
class Balanced1X2Analysis:
    code: int
    kickoff: str
    league: str
    match: str
    nesine_ms: tuple[float | None, float | None, float | None]
    market_probs: tuple[float, float, float]
    post_probs: tuple[float, float, float]
    evs: tuple[float | None, float | None, float | None]
    verdict: str  # "MS 1" | "MS 0" | "MS 2" | "PAS (Yazı-Tura)"
    best_side: str
    best_odds: float | None
    best_ev: float | None
    confidence_score: float  # 0..100
    trap_draw_alert: bool
    signals: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComebackCandidate:
    code: int
    kickoff: str
    league: str
    match: str
    market_family: str  # "İY/MS" veya "Devre Dönüşü"
    selection: str      # "İY/MS 1/2", "İY/MS 2/1", "İY 1 & 2Y 2", "İY 2 & 2Y 1"
    archetype: str
    p_model: float
    p_calibrated: float
    nesine_odds: float | None
    ev: float | None
    dna_score: float    # 0..100
    insurance_leg: str | None
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoldenScoreRank:
    score: str
    is_golden: bool
    p_model: float
    nesine_odds: float | None
    ev: float | None


def analyze_balanced_1x2(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
    sim_xg: Sequence[float] | None = None,
) -> Balanced1X2Analysis | None:
    """Dengeli / yüksek oranlı 1X2 maçlarını çoklu sinyalle çöz (veya dürüstçe PAS ver)."""
    f1x2 = match.get("fair_1x2") or []
    if len(f1x2) != 3 or any(_flt(x) is None for x in f1x2):
        return None
    p1, px, p2 = (max(0.02, float(f1x2[0])), max(0.02, float(f1x2[1])), max(0.02, float(f1x2[2])))
    tot_p = p1 + px + p2
    p1, px, p2 = p1 / tot_p, px / tot_p, p2 / tot_p

    nes_ms_raw = match.get("nesine_ms") or [None, None, None]
    n1 = _flt(nes_ms_raw[0]) if len(nes_ms_raw) == 3 else None
    nx = _flt(nes_ms_raw[1]) if len(nes_ms_raw) == 3 else None
    n2 = _flt(nes_ms_raw[2]) if len(nes_ms_raw) == 3 else None

    # Dengeli / yüksek oran bandı: her iki taraf >= 1.85 veya max(p1, p2) < 0.54
    is_high_odds = (n1 is not None and n2 is not None and min(n1, n2) >= 1.85) or max(p1, p2) < 0.54
    if not is_high_odds:
        return None

    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    mu_tot = (mh + ma) if (mh is not None and ma is not None) else None

    res = match.get("research") or {}
    teams = (research_row or {}).get("teams") or res.get("teams") or {}
    h_gk, a_gk, h_sc, a_sc = _absences(match, research_row)
    s_xg = _extract_sim_xg(match, research_row, sim_xg)

    # 0. Piyasa-artık (LightGBM Residual) tabanı + kulüp DNA öznitelikleri
    hdna = lookup_club_dna(match.get("home"))
    adna = lookup_club_dna(match.get("away"))
    p_o25_fair = _flt((match.get("selections") or [{}])[0].get("fair_prob")) if False else None
    for s_tmp in (match.get("selections") or []):
        if s_tmp.get("name") == "2.5 Üst":
            p_o25_fair = _flt(s_tmp.get("fair_prob"))
            break
    rk_h_pre = _team_rank(match.get("research") or {}, "home")
    rk_a_pre = _team_rank(match.get("research") or {}, "away")
    f_h_pre = _form_points((((research_row or {}).get("teams") or (match.get("research") or {}).get("teams") or {}).get("home") or {}).get("form"))
    f_a_pre = _form_points((((research_row or {}).get("teams") or (match.get("research") or {}).get("teams") or {}).get("away") or {}).get("form"))
    p_ml = predict_balanced_residual(
        (p1, px, p2),
        p_over25=p_o25_fair,
        form5_diff=(f_h_pre - f_a_pre) if (f_h_pre is not None and f_a_pre is not None) else None,
        club_h_1h=hdna.first_half_share if hdna else None,
        club_a_1h=adna.first_half_share if adna else None,
        club_cb_diff=(hdna.comeback_rate - adna.comeback_rate) if (hdna and adna) else None,
    )
    b1, bx, b2 = p_ml

    # Log-prob uzayında düzeltme (Bayesian log-odds kayması)
    d1 = dx = d2 = 0.0
    signals: list[str] = []
    warnings: list[str] = []
    dir_votes: list[int] = []  # +1: Ev, 0: Beraberlik, -1: Dep
    if max(abs(b1 - p1), abs(bx - px), abs(b2 - p2)) >= 0.008:
        mx_i = max(range(3), key=lambda i: (b1 - p1, bx - px, b2 - p2)[i])
        dir_votes.append(1 if mx_i == 0 else (0 if mx_i == 1 else -1))
        signals.append(f"ML Residual -> {('MS 1', 'MS 0', 'MS 2')[mx_i]} ({(b1-p1, bx-px, b2-p2)[mx_i]*100:+.1f}p)")

    # Maça < 4 saat kala güçlü keskin steam varsa Sharp-Lag aciliyet oyu ekle
    ko_iso = match.get("kickoff_iso")
    steam_raw = match.get("steam_1x2")
    if ko_iso and isinstance(steam_raw, (list, tuple)) and len(steam_raw) == 3:
        try:
            ko_dt = dt.datetime.fromisoformat(str(ko_iso).replace("Z", "+00:00"))
            now_ref = dt.datetime.now(ko_dt.tzinfo or dt.timezone.utc)
            hrs = (ko_dt - now_ref).total_seconds() / 3600.0
            if 0.0 <= hrs <= 4.0 and max(abs(float(x or 0.0)) for x in steam_raw) >= 0.04:
                st_idx = max(range(3), key=lambda i: float(steam_raw[i] or 0.0))
                if float(steam_raw[st_idx] or 0.0) >= 0.04:
                    dir_votes.append(1 if st_idx == 0 else (0 if st_idx == 1 else -1))
                    signals.append(f"Sharp-Lag ({hrs:.1f}s kala {('Ev', 'X', 'Dep')[st_idx]} +{float(steam_raw[st_idx])*100:.1f}p)")
        except ValueError:
            pass

    # 1. Tempo / gol beklentisine göre beraberlik kayması (65.669 maçlık bulgu, 2024-2026 holdout kalibreli)
    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    o25_sel = sels.get("2.5 Üst")
    o25_odds = _flt(o25_sel.get("odds")) if o25_sel else None
    if (mu_tot is not None and mu_tot <= 2.25) or (o25_odds is not None and o25_odds >= 2.10):
        dx += 0.035
        dir_votes.append(0)
        signals.append(f"düşük gol temposu ({mu_tot:.2f} xG) -> hafif beraberlik eğilimi" if mu_tot else "düşük gol temposu (2.5Ü ≥ 2.10) -> hafif beraberlik eğilimi")
    elif (mu_tot is not None and mu_tot >= 2.85) or (o25_odds is not None and o25_odds <= 1.72):
        signals.append(f"yüksek gol temposu ({mu_tot:.2f} xG) -> açık maç" if mu_tot else "yüksek tempo (2.5Ü ≤ 1.72) -> açık maç")

    # 2. Keskin borsa steam yönü
    steam = match.get("steam_1x2")
    if isinstance(steam, (list, tuple)) and len(steam) == 3:
        s1 = _flt(steam[0]) or 0.0
        sx = _flt(steam[1]) or 0.0
        s2 = _flt(steam[2]) or 0.0
        if max(abs(s1), abs(sx), abs(s2)) >= 0.025:
            d1 += _clip(s1 * 2.2, -0.18, 0.18)
            dx += _clip(sx * 2.0, -0.15, 0.15)
            d2 += _clip(s2 * 2.2, -0.18, 0.18)
            if s1 >= 0.025:
                dir_votes.append(1)
                signals.append(f"keskin para Ev lehine akıyor ({s1*100:+.1f}p)")
            elif s2 >= 0.025:
                dir_votes.append(-1)
                signals.append(f"keskin para Dep lehine akıyor ({s2*100:+.1f}p)")
            elif sx >= 0.025:
                dir_votes.append(0)
                signals.append(f"keskin para Beraberlik lehine akıyor ({sx*100:+.1f}p)")

    # 3. Tuzak Favori Tespiti: Sıralama/form üstün ama piyasa hâlâ dengeli -> X ROI artı
    rk_h = _team_rank(res, "home")
    rk_a = _team_rank(res, "away")
    f_h = _form_points((teams.get("home") or {}).get("form"))
    f_a = _form_points((teams.get("away") or {}).get("form"))
    trap_draw = False
    if rk_h is not None and rk_a is not None:
        rank_gap = rk_a - rk_h  # pozitif: Ev daha üst sırada
        if rank_gap >= 5 and p1 < 0.44:
            trap_draw = True
            dx += 0.11
            d1 -= 0.07
            dir_votes.append(0)
            warnings.append(f"tuzak ev favorisi: Ev #{rk_h} vs Dep #{rk_a} ama piyasa dengeli (%{100*p1:.0f}) -> Beraberlik güçleniyor")
        elif rank_gap <= -5 and p2 < 0.40:
            trap_draw = True
            dx += 0.09
            d2 -= 0.06
            dir_votes.append(0)
            warnings.append(f"tuzak dep favorisi: Dep #{rk_a} vs Ev #{rk_h} ama piyasa dengeli -> Beraberlik güçleniyor")

    if f_h is not None and f_a is not None:
        f_diff = f_h - f_a
        if f_diff >= 4.0 and not trap_draw:
            d1 += 0.07
            dir_votes.append(1)
            signals.append(f"form üstünlüğü Ev ({f_h:.0f} vs {f_a:.0f} puan)")
        elif f_diff <= -4.0 and not trap_draw:
            d2 += 0.07
            dir_votes.append(-1)
            signals.append(f"form üstünlüğü Dep ({f_a:.0f} vs {f_h:.0f} puan)")

    # 4. Kadro / kaleci / golcü eksikleri & dinlenme günü
    if h_gk:
        d2 += 0.16
        d1 -= 0.10
        dir_votes.append(-1)
        signals.append("Ev 1. kaleci eksik -> Dep avantajı")
    if a_gk:
        d1 += 0.16
        d2 -= 0.10
        dir_votes.append(1)
        signals.append("Dep 1. kaleci eksik -> Ev avantajı")
    if h_sc and not a_sc:
        d1 -= 0.09
        dx += 0.04
        d2 += 0.05
        warnings.append("Ev gol kralı eksik")
    elif a_sc and not h_sc:
        d2 -= 0.09
        dx += 0.04
        d1 += 0.05
        warnings.append("Dep gol kralı eksik")

    rest_h = _flt((teams.get("home") or {}).get("rest_days"))
    rest_a = _flt((teams.get("away") or {}).get("rest_days"))
    if rest_h is not None and rest_a is not None:
        if rest_h - rest_a >= 3.0:
            d1 += 0.06
            dir_votes.append(1)
            signals.append(f"dinlenme avantajı Ev ({rest_h:.0f}g vs {rest_a:.0f}g)")
        elif rest_a - rest_h >= 3.0:
            d2 += 0.06
            dir_votes.append(-1)
            signals.append(f"dinlenme avantajı Dep ({rest_a:.0f}g vs {rest_h:.0f}g)")

    # 5. Şiddetli hava -> beraberlik + alt eğilimi
    wx = res.get("weather") or {}
    if wx.get("flag"):
        dx += 0.07
        dir_votes.append(0)
        warnings.append(f"hava etkisi: {wx['flag']}")

    # 6. Bağımsız form/DC simülasyonu veya xG üstünlüğü
    if s_xg is not None and mh is not None and ma is not None:
        sim_diff = (s_xg[0] - s_xg[1]) - (mh - ma)
        if sim_diff >= 0.35:
            d1 += 0.07
            dir_votes.append(1)
            signals.append(f"bağımsız simülasyon Ev'i daha güçlü görüyor ({s_xg[0]:.2f}-{s_xg[1]:.2f})")
        elif sim_diff <= -0.35:
            d2 += 0.07
            dir_votes.append(-1)
            signals.append(f"bağımsız simülasyon Dep'i daha güçlü görüyor ({s_xg[0]:.2f}-{s_xg[1]:.2f})")

    xh = _team_xg_avg(res, "home")
    xa = _team_xg_avg(res, "away")
    if xh is not None and xa is not None and abs(xh - xa) >= 0.45:
        if xh > xa:
            d1 += 0.06
            dir_votes.append(1)
            signals.append(f"maç başı xG üstünlüğü Ev ({xh:.2f} vs {xa:.2f})")
        else:
            d2 += 0.06
            dir_votes.append(-1)
            signals.append(f"maç başı xG üstünlüğü Dep ({xa:.2f} vs {xh:.2f})")

    # Log-uzay posterior hesapla
    raw = [
        math.exp(math.log(max(0.02, b1)) + _clip(d1, -0.32, 0.32)),
        math.exp(math.log(max(0.02, bx)) + _clip(dx, -0.28, 0.28)),
        math.exp(math.log(max(0.02, b2)) + _clip(d2, -0.32, 0.32)),
    ]
    s_raw = sum(raw)
    post = (round(raw[0] / s_raw, 4), round(raw[1] / s_raw, 4), round(raw[2] / s_raw, 4))

    odds_tuple = (n1, nx, n2)
    evs_list: list[float | None] = []
    for pr, od in zip(post, odds_tuple):
        evs_list.append(round(pr * od - 1.0, 4) if od is not None else None)
    evs = (evs_list[0], evs_list[1], evs_list[2])

    labels = ("MS 1", "MS 0", "MS 2")
    shifts = (post[0] - p1, post[1] - px, post[2] - p2)
    # En iyi yön: pozitif shift + yüksek EV + piyasa payı dengesi
    best_idx = max(
        range(3),
        key=lambda i: (
            (evs[i] if evs[i] is not None else -0.10) + 1.8 * shifts[i] + 0.15 * post[i]
        ),
    )
    best_side = labels[best_idx]
    best_odds = odds_tuple[best_idx]
    best_ev = evs[best_idx]

    # Karar ve güven skoru (0..100)
    shift_mag = max(abs(x) for x in shifts)
    vote_target = 1 if best_idx == 0 else (0 if best_idx == 1 else -1)
    agree_votes = sum(1 for v in dir_votes if v == vote_target)
    oppose_votes = sum(1 for v in dir_votes if v != vote_target)

    conf = 35.0 + min(30.0, shift_mag * 500.0) + 10.0 * agree_votes - 7.0 * oppose_votes
    if best_ev is not None:
        conf += _clip(best_ev * 120.0, -15.0, 20.0)
    if str(match.get("price_tier")) == "keskin":
        conf += 6.0
    elif str(match.get("price_tier")) == "dusuk_guven":
        conf -= 15.0
    conf = round(_clip(conf, 0.0, 100.0), 1)

    is_sharp_or_mid = match.get("status") == "fiyatlandı"
    ev_ok = best_ev is None or best_ev >= -0.02
    if is_sharp_or_mid and conf >= 58.0 and ev_ok and agree_votes >= 2 and shifts[best_idx] >= 0.006:
        verdict = best_side
    else:
        verdict = "PAS (Yazı-Tura)"

    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    return Balanced1X2Analysis(
        code=int(match["code"]),
        kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
        league=str(match.get("league") or ""),
        match=mname,
        nesine_ms=(n1, nx, n2),
        market_probs=(round(p1, 4), round(px, 4), round(p2, 4)),
        post_probs=post,
        evs=evs,
        verdict=verdict,
        best_side=best_side,
        best_odds=best_odds,
        best_ev=best_ev,
        confidence_score=conf,
        trap_draw_alert=trap_draw,
        signals=tuple(signals[:4]),
        warnings=tuple(warnings[:3]),
    )


def _poisson_half_reversal_base(mh: float, ma: float, h1_share: float) -> dict[str, float]:
    """İki takımlı hızlı analitik taban: 1Y ve 2Y bağımsız/yarı-elastik dağılımından 1/2, 2/1 tahmini."""
    h1_h = max(0.05, mh * h1_share)
    h1_a = max(0.05, ma * (h1_share - 0.015))
    h2_h = max(0.05, mh * (1.0 - h1_share))
    h2_a = max(0.05, ma * (1.0 - (h1_share - 0.015)))

    def pmf(lam: float, n: int = 6) -> list[float]:
        return [math.exp(-lam) * (lam ** k) / math.factorial(k) for k in range(n)]

    p1h, p1a = pmf(h1_h), pmf(h1_a)
    p2h, p2a = pmf(h2_h), pmf(h2_a)

    # 1Y sonuçları
    p_ht_1 = sum(p1h[i] * p1a[j] for i in range(6) for j in range(6) if i > j)
    p_ht_2 = sum(p1h[i] * p1a[j] for i in range(6) for j in range(6) if j > i)
    p_2h_1 = sum(p2h[i] * p2a[j] for i in range(6) for j in range(6) if i > j)
    p_2h_2 = sum(p2h[i] * p2a[j] for i in range(6) for j in range(6) if j > i)

    # Tam İY/MS 1/2 ve 2/1 (~devre farkı telafisi gerektirir)
    iyms_12 = 0.0
    iyms_21 = 0.0
    for i1 in range(6):
        for j1 in range(6):
            w1 = p1h[i1] * p1a[j1]
            if w1 < 1e-6 or i1 == j1:
                continue
            for i2 in range(6):
                for j2 in range(6):
                    w = w1 * p2h[i2] * p2a[j2]
                    if i1 > j1 and (i1 + i2) < (j1 + j2):
                        iyms_12 += w
                    elif j1 > i1 and (i1 + i2) > (j1 + j2):
                        iyms_21 += w
    return {
        "İY/MS 1/2": iyms_12,
        "İY/MS 2/1": iyms_21,
        "İY 1 & 2Y 2": p_ht_1 * p_2h_2,
        "İY 2 & 2Y 1": p_ht_2 * p_2h_1,
    }


def score_comeback_reversals(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
    sim_xg: Sequence[float] | None = None,
    *,
    htft_dist: Mapping[str, float] | None = None,
    min_dna: float = 48.0,
) -> list[ComebackCandidate]:
    """Bir maç için 1/2 & 2/1 geri dönüş ve İY 1 & 2Y 2 / İY 2 & 2Y 1 adaylarını puanla."""
    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    if mh is None or ma is None or (mh + ma) <= 0:
        return []
    mtot = mh + ma
    mmin = min(mh, ma)
    if mtot < 2.20 or mmin < 0.55:
        return []

    f1x2 = match.get("fair_1x2") or [0.34, 0.32, 0.34]
    p1 = _flt(f1x2[0]) or 0.34
    p2 = _flt(f1x2[2]) or 0.34

    lg = str(match.get("league") or "")
    h1_share = league_first_half_share(lg) or 0.440
    base_probs = _poisson_half_reversal_base(mh, ma, h1_share)
    lg_cb = league_comeback_rates(lg) or {}

    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    hist = _extract_history_metrics(research_row)
    h_gk, a_gk, _, _ = _absences(match, research_row)
    steam = match.get("steam_1x2") or [0.0, 0.0, 0.0]
    hdna = lookup_club_dna(match.get("home"))
    adna = lookup_club_dna(match.get("away"))

    # Güvenli sigorta bacağı (aynı yüksek tempolu maçtan)
    ins_leg = None
    for cand_ins in ("1.5 Üst", "2.5 Üst", "KG Var", "2Y 0.5 Üst"):
        si = sels.get(cand_ins)
        if si and (_flt(si.get("fair_prob")) or 0.0) >= 0.65 and (_flt(si.get("odds")) or 0.0) >= 1.20:
            ins_leg = f"{cand_ins} @{float(si['odds']):.2f} (%{100*float(si['fair_prob']):.0f})"
            break

    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    out: list[ComebackCandidate] = []

    configs = [
        ("İY/MS", "İY/MS 1/2", "1/2", "iyms_1/2", mh, ma, p2, 1),
        ("İY/MS", "İY/MS 2/1", "2/1", "iyms_2/1", ma, mh, p1, 0),
        ("Devre Dönüşü", "İY 1 & 2Y 2", "1/2_devre", "iy2y_1/2", mh, ma, p2, 1),
        ("Devre Dönüşü", "İY 2 & 2Y 1", "2/1_devre", "iy2y_2/1", ma, mh, p1, 0),
    ]

    for fam, sel_name, tag_key, csv_col, first_leader_mu, comeback_mu, comeback_p, side_flag in configs:
        is_full_htft = fam == "İY/MS"
        if not is_full_htft and mmin < 0.85:
            continue
        # Temel model olasılığı
        s_obj = sels.get(sel_name)
        p_mod = _flt(s_obj.get("fair_prob")) if s_obj else None
        if p_mod is None and is_full_htft and htft_dist:
            p_mod = _flt(htft_dist.get(tag_key))
        if p_mod is None:
            p_mod = base_probs.get(sel_name, 0.025)

        # Lig ampirik geri dönüş oranı ile %70 model + %30 lig tabanı harmanı
        if csv_col in lg_cb:
            p_cal = 0.70 * float(p_mod) + 0.30 * float(lg_cb[csv_col])
        else:
            p_cal = float(p_mod)

        # 65.669 maçlık ampirik arketip tepkisi + oyun durumu
        reasons: list[str] = []
        warnings: list[str] = []
        dna = 0.0

        # 1. Tempo & çift yönlü tehdit (2024-2026 holdout kalibreli)
        if is_full_htft:
            if mtot >= 3.15 and mmin >= 0.60:
                dna += 28.0
                reasons.append(f"açık yüksek tempo ({mtot:.2f} xG, min taraf {mmin:.2f})")
            elif mtot >= 2.80 and mmin >= 0.60:
                dna += 22.0
                reasons.append(f"yeterli gol temposu ({mtot:.2f} xG)")
            elif mtot >= 2.55 and mmin >= 0.70:
                dna += 14.0
                reasons.append(f"orta gol temposu ({mtot:.2f} xG)")
            else:
                dna += max(0.0, (mtot - 2.0) * 10.0)
        else:
            if mtot >= 3.10 and mmin >= 1.15:
                dna += 30.0
                reasons.append(f"açık yüksek tempo ({mtot:.2f} xG, min taraf {mmin:.2f})")
            elif mtot >= 2.75 and mmin >= 1.00:
                dna += 22.0
                reasons.append(f"yeterli gol temposu ({mtot:.2f} xG)")
            else:
                dna += max(0.0, (mtot - 2.0) * 14.0)

        # 2. Dönüş yapacak tarafın gücü & ilk golü atacak tarafın 2Y savunma kırılganlığı
        if is_full_htft:
            if comeback_p >= 0.52 and mtot >= 3.00 and first_leader_mu >= 0.60:
                archetype = "favori_geri_donus"
                dna += 35.0
                p_cal *= 1.24
                reasons.append(f"güçlü geri dönüş favorisi (%{100*comeback_p:.0f}, açık maçta %4+ arketip)")
            elif comeback_p >= 0.46 and mtot >= 2.75 and first_leader_mu >= 0.60:
                archetype = "favori_geri_donus"
                dna += 30.0
                p_cal *= 1.18
                reasons.append(f"dönüş yapacak taraf favori (%{100*comeback_p:.0f}, 65k maç arketipi: ~%4)")
            elif abs(p1 - p2) <= 0.12 and mtot >= 2.95 and mmin >= 1.10:
                archetype = "dengeli_duello_donusu"
                dna += 24.0
                p_cal *= 1.10
                reasons.append("dengeli açık düelloda erken gol + 2Y kırılma")
            else:
                archetype = "zayif_donus"
                dna += 6.0
                if comeback_p < 0.30:
                    dna -= 10.0
                    warnings.append(f"zayıf taraf dönüşü nadir (%{100*comeback_p:.0f})")
        else:
            if abs(p1 - p2) <= 0.12 and mtot >= 2.75 and mmin >= 1.10:
                archetype = "devre_denge_donusu"
                dna += 26.0
                p_cal *= 1.08
                reasons.append("dengeli açık maçta devre dönüşü arketipi (%11+ tarihsel taban)")
            elif comeback_p >= 0.45 and mtot >= 2.75:
                archetype = "favori_2y_tepkisi"
                dna += 22.0
                reasons.append(f"2. yarı baskı arketipi (dönüş tarafı %{100*comeback_p:.0f})")
            else:
                archetype = "zayif_devre_donusu"
                dna += 10.0

        # 3. Takım geçmişinde 1Y / 2Y asimetrisi (1/2 için Ev 1Y atar & 2Y yer; Dep 1Y yer & 2Y atar)
        if tag_key.startswith("1/2"):
            s1_leader, c2_leader = hist.get("h_s1"), hist.get("h_c2")
            c1_comeb, s2_comeb = hist.get("a_c1"), hist.get("a_s2")
        else:
            s1_leader, c2_leader = hist.get("a_s1"), hist.get("a_c2")
            c1_comeb, s2_comeb = hist.get("h_c1"), hist.get("h_s2")

        asym_hits = 0
        if s1_leader is not None and s1_leader >= 0.45:
            asym_hits += 1
        if c2_leader is not None and c2_leader >= 0.50:
            asym_hits += 1
        if c1_comeb is not None and c1_comeb >= 0.45:
            asym_hits += 1
        if s2_comeb is not None and s2_comeb >= 0.55:
            asym_hits += 1
        if asym_hits >= 3:
            dna += 18.0
            p_cal *= 1.12
            reasons.append(f"geçmişte 1Y/2Y devir-teslim profili güçlü ({asym_hits}/4 gösterge)")
        elif asym_hits >= 2:
            dna += 10.0
            reasons.append(f"kısmi 1Y/2Y asimetri ({asym_hits}/4)")
        elif all(v is None for v in (s1_leader, c2_leader, c1_comeb, s2_comeb)):
            dna += 7.0  # nötr taban

        # 4. İlk yarı lideri olacak tarafın açılış gücü + kaleci eksikliği + keskin akış
        if first_leader_mu >= 0.65 and comeback_mu >= 1.65:
            dna += 8.0
        elif first_leader_mu >= 1.10 and comeback_mu >= 1.25:
            dna += 6.0
        if (side_flag == 1 and h_gk) or (side_flag == 0 and a_gk):
            dna += 7.0
            reasons.append("1. yarı öne geçen tarafın 2. yarı savunma/kaleci zaafı")
        if isinstance(steam, (list, tuple)) and len(steam) == 3:
            st_cb = _flt(steam[2 if side_flag == 1 else 0]) or 0.0
            if st_cb >= 0.03:
                dna += 5.0
                reasons.append(f"keskin para dönüş tarafına akıyor ({st_cb*100:+.1f}p)")

        # Kulüp 1Y/2Y DNA uyumu (488 kulüplük Empirical Bayes tablosu)
        leader_dna = hdna if tag_key.startswith("1/2") else adna
        comeb_dna = adna if tag_key.startswith("1/2") else hdna
        if leader_dna and comeb_dna and leader_dna.n_eff >= 6.0 and comeb_dna.n_eff >= 6.0:
            if leader_dna.lead_hold_vuln >= 0.48 and comeb_dna.comeback_rate >= 0.38:
                dna += 6.0
                p_cal *= 1.08
                reasons.append(
                    f"kulüp DNA uyumu: {leader_dna.club} 2Y zaaf %{100*leader_dna.lead_hold_vuln:.0f} / "
                    f"{comeb_dna.club} dönüş %{100*comeb_dna.comeback_rate:.0f}"
                )

        cap = 0.095 if is_full_htft else 0.195
        p_cal = round(_clip(p_cal, 0.005, cap), 5)

        odds = _flt(s_obj.get("odds")) if s_obj else None
        ev = round(p_cal * odds - 1.0, 4) if odds is not None else None
        if ev is not None:
            if ev >= 0.05:
                dna += min(10.0, ev * 20.0)
                reasons.append(f"pozitif EV ({ev*100:+.1f}%)")
            elif ev < -0.22:
                dna -= 8.0
                warnings.append(f"Nesine oranı düşük (EV {ev*100:+.1f}%)")

        dna = round(_clip(dna, 0.0, 100.0), 1)
        if dna < min_dna:
            continue
        out.append(
            ComebackCandidate(
                code=int(match["code"]),
                kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
                league=lg,
                match=mname,
                market_family=fam,
                selection=sel_name,
                archetype=archetype,
                p_model=round(float(p_mod), 5),
                p_calibrated=p_cal,
                nesine_odds=odds,
                ev=ev,
                dna_score=dna,
                insurance_leg=ins_leg,
                reasons=tuple(reasons[:3]),
                warnings=tuple(warnings[:2]),
            )
        )
    out.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0)))
    return out


def rank_golden_scores_with_ev(
    match: Mapping[str, Any],
    ft_dist: Mapping[str, float] | None,
    *,
    top_n: int = 5,
) -> list[GoldenScoreRank]:
    """Maçın 6-Altın-Skor ağırlıklı sıralamasını ve canlı Nesine MTID 777 skor EV'sini döndür."""
    if not ft_dist:
        return []
    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    mkt_sc_odds: dict[str, float] = {}
    for nm, s in sels.items():
        if str(nm).startswith("Skor ") and s.get("odds"):
            sc = str(nm).replace("Skor ", "").replace(":", "-").strip()
            ov = _flt(s.get("odds"))
            if ov is not None and ov > 1.0:
                mkt_sc_odds[sc] = ov

    p_o25 = _flt((sels.get("2.5 Üst") or {}).get("fair_prob"))
    cal_dist = calibrate_score_distribution(ft_dist, match.get("fair_1x2"), p_o25)

    ranked = rank_macro_coherent_scores(
        cal_dist,
        f1x2=match.get("fair_1x2"),
        p_o25=p_o25,
        p_btts=_flt((sels.get("KG Var") or {}).get("fair_prob")),
        mu_home=_flt(match.get("mu_home")),
        mu_away=_flt(match.get("mu_away")),
        market_score_odds=mkt_sc_odds or None,
        ref_ah=match.get("ref_ah"),
        steam_1x2=match.get("steam_1x2"),
    )
    out: list[GoldenScoreRank] = []
    for sc, p_mod in ranked[:top_n]:
        od = mkt_sc_odds.get(sc)
        ev = round(float(p_mod) * od - 1.0, 4) if od is not None else None
        out.append(
            GoldenScoreRank(
                score=sc,
                is_golden=sc in GOLDEN_SCORES,
                p_model=round(float(p_mod), 4),
                nesine_odds=od,
                ev=ev,
            )
        )
    return out


def scan_high_odds_opportunities(
    matches: Sequence[Mapping[str, Any]],
    research_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    dist_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    sim_xg_by_code: Mapping[int, Sequence[float]] | None = None,
) -> dict[str, list[Any]]:
    """Günlük bültendeki dengeli 1X2, 1/2 & 2/1 dönüş ve 6-Altın-Skor fırsatlarını tara."""
    res_map = research_by_code or {}
    dist_map = dist_by_code or {}
    sim_map = sim_xg_by_code or {}

    balanced: list[Balanced1X2Analysis] = []
    htft_reversals: list[ComebackCandidate] = []
    half_reversals: list[ComebackCandidate] = []
    golden_scores: list[dict[str, Any]] = []

    for m in matches:
        if m.get("price_tier") == "ozel_bahis" or m.get("status") not in ("fiyatlandı", "düşük güven — global fiyat yok, Nesine oranından (kupona alınmaz)"):
            continue
        code = int(m["code"])
        row = res_map.get(code)
        sxg = sim_map.get(code)
        d_rec = dist_map.get(code) or {}

        bal = analyze_balanced_1x2(m, row, sxg)
        if bal is not None:
            balanced.append(bal)

        if m.get("status") == "fiyatlandı":
            cb_list = score_comeback_reversals(m, row, sxg, htft_dist=d_rec.get("htft"))
            for cb in cb_list:
                if cb.market_family == "İY/MS":
                    htft_reversals.append(cb)
                else:
                    half_reversals.append(cb)

            ft_d = d_rec.get("ft") or {}
            if ft_d:
                gs = rank_golden_scores_with_ev(m, ft_d, top_n=3)
                if gs:
                    sels_m = {s.get("name"): s for s in (m.get("selections") or [])}
                    mkt_sc = {
                        str(nm).replace("Skor ", "").replace(":", "-").strip(): float(s["odds"])
                        for nm, s in sels_m.items()
                        if str(nm).startswith("Skor ") and s.get("odds")
                    }
                    p_o25_m = _flt((sels_m.get("2.5 Üst") or {}).get("fair_prob"))
                    cal_d = calibrate_score_distribution(ft_d, m.get("fair_1x2"), p_o25_m)
                    dutch_plans = optimize_score_dutching(cal_d, mkt_sc, budget_tl=100.0) if mkt_sc else []
                    golden_scores.append(
                        {
                            "code": code,
                            "kickoff": str(m.get("kickoff") or "")[:16],
                            "league": str(m.get("league") or ""),
                            "match": f"{m.get('home', '')} - {m.get('away', '')}",
                            "top_scores": gs,
                            "best_ev": max((x.ev for x in gs if x.ev is not None), default=None),
                            "dutching": dutch_plans[0] if dutch_plans else None,
                        }
                    )

    balanced.sort(key=lambda x: (x.verdict == "PAS (Yazı-Tura)", -x.confidence_score, -(x.best_ev if x.best_ev is not None else -9.0)))
    htft_reversals.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0)))
    half_reversals.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0)))
    golden_scores.sort(key=lambda x: (x["best_ev"] is None, -(x["best_ev"] if x["best_ev"] is not None else -9.0), -x["top_scores"][0].p_model))
    return {
        "balanced_1x2": balanced,
        "htft_reversals": htft_reversals,
        "half_reversals": half_reversals,
        "golden_scores": golden_scores,
    }
