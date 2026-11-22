"""6+ Gol / 5,5 Üst ve İki Yarıda KG Var uzman tarama, kuyruk fiyatlama ve DNA skorlama motoru.

22 Kasım 2026 denetiminden çıkan yapısal derslerle oluşturuldu (319 bitmiş fiyatlı maç):
  * 319 maçın 31'inde (%9,7) 6+ Gol, 20'sinde (%6,3) İki Yarıda KG Var gerçekleşti.
  * 6+ Gol iki ayrı arketipten geliyor:
      (A) Tek taraflı yıkım (mu_tot ≥ 3.55, |mu_h − mu_a| ≥ 1.15; ör. Lyon 5-2, Beerschot 5-1, AZ 1-5)
      (B) Açık tempo düello (mu_tot ≥ 3.10, min_mu ≥ 1.20; ör. Schaffhausen 2-6, Konyaspor 2-4, Fabril 3-3)
    mu_tot ≥ 3.6 diliminde gerçek 6+ Gol oranı %22,9 (8/35) çıktı.
  * İki Yarıda KG Var için belirleyici eşik çift taraflı hücum simetrisi (min_mu ≥ 1.20, özellikle ≥ 1.45;
    Santander–R. Sociedad 2-1/3-2 @6,81) + her iki takımın ayrı ayrı 1. ve 2. yarıda gol bulma/yeme temposu.
  * Bağımsız Poisson hem 6+ Gol kuyruğunu hem de maç-temposu korelasyonunu hafife alırken, deplasman
    takımlarının ilk yarı gol payını (gerçek ~%41,7 vs ev %43,5) aşırı tahmin eder. Bu modül
    tail_goals.regime_score_matrix (overdispersed kuyruk) ve halves_btts.compute_halves_btts (Gamma-Poisson
    ortak tempo + FGM bağımlılığı) üzerine çift-katmanlı DNA skoru ve güvenli gol merdiveni üretir.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from typing import Any

import numpy as np

from quantfoot.coupons.system_builder import SystemEvaluation, SystemLeg, optimize_system
from quantfoot.markets.halves_btts import compute_halves_btts, half_model_params
from quantfoot.markets.market_diagnosis import parse_steam_pp
from quantfoot.markets.tail_goals import league_tail_regime, regime_score_matrix, summarize_tail_goals
from quantfoot.strategy.banko_guard import league_tier

HOME_1H_SHARE_DEFAULT = 0.438
AWAY_1H_SHARE_DEFAULT = 0.420
MIN_CLUB_KAPPA = 0.030  # yüksek xG kulüp maçlarında ortak maç temposu varyansı


@dataclass(frozen=True)
class SafeLadderLeg:
    name: str
    market: str
    selection: str
    odds: float
    fair_prob: float


@dataclass(frozen=True)
class ExtremeGoalCandidate:
    code: int
    kickoff: str
    league: str
    match: str
    league_tier: str | None
    kind: str  # "6+ Gol" veya "İki Yarıda KG Var"
    archetype: str  # "yıkım" | "düello" | "dengeli_tempo" | "zayıf"
    mu_home: float
    mu_away: float
    mu_total: float
    min_mu: float
    dna_score: float  # 0..100
    p_tail: float     # overdispersed kuyruk olasılığı
    p_market: float | None
    nesine_market: str | None
    nesine_selection: str | None
    nesine_odds: float | None
    ev: float | None
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    safe_ladder: tuple[SafeLadderLeg, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


def _flt(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        v = float(val)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _extract_history_metrics(row: Mapping[str, Any] | None) -> dict[str, float | int | None]:
    """Takım geçmişi maçlarından (derin_tahminler / research) 1Y/2Y ve yüksek gol hızlarını çıkar."""
    out: dict[str, float | int | None] = {
        "n_home": 0, "n_away": 0,
        "h_over35": None, "a_over35": None,
        "h_over45": None, "a_over45": None,
        "h_s1": None, "a_s1": None,
        "h_c1": None, "a_c1": None,
        "h_s2": None, "a_s2": None,
        "h_c2": None, "a_c2": None,
        "h_btts": None, "a_btts": None,
        "h_both_half_btts": None, "a_both_half_btts": None,
    }
    if not row:
        return out
    games = row.get("games") or {}
    teams = row.get("teams") or {}
    for side, pfx in (("home", "h"), ("away", "a")):
        t = teams.get(side) or {}
        if _flt(t.get("score1H")) is not None:
            out[f"{pfx}_s1"] = _flt(t.get("score1H"))
        if _flt(t.get("concede1H")) is not None:
            out[f"{pfx}_c1"] = _flt(t.get("concede1H"))
        glist = games.get(side) or []
        if not glist:
            continue
        out[f"n_{side}"] = len(glist)
        o35 = o45 = btts = 0
        s1 = c1 = s2 = c2 = bh_btts = n_half = 0
        for g in glist:
            gf = g.get("for") or (None, None)
            ga = g.get("against") or (None, None)
            if gf[0] is not None and ga[0] is not None and gf[1] is not None and ga[1] is not None:
                f1, f2 = int(gf[0]), int(gf[1])
                a1, a2 = int(ga[0]), int(ga[1])
                tot = f1 + f2 + a1 + a2
                o35 += int(tot >= 4)
                o45 += int(tot >= 5)
                btts += int((f1 + f2) >= 1 and (a1 + a2) >= 1)
                s1 += int(f1 >= 1)
                c1 += int(a1 >= 1)
                s2 += int(f2 >= 1)
                c2 += int(a2 >= 1)
                bh_btts += int(f1 >= 1 and a1 >= 1 and f2 >= 1 and a2 >= 1)
                n_half += 1
            elif gf[1] is not None and ga[1] is not None:
                tot = int(gf[1]) + int(ga[1])
                o35 += int(tot >= 4)
                o45 += int(tot >= 5)
                btts += int(int(gf[1]) >= 1 and int(ga[1]) >= 1)
        n_all = len(glist)
        out[f"{pfx}_over35"] = o35 / n_all
        out[f"{pfx}_over45"] = o45 / n_all
        out[f"{pfx}_btts"] = btts / n_all
        if n_half >= 4:
            out[f"{pfx}_s1"] = s1 / n_half
            out[f"{pfx}_c1"] = c1 / n_half
            out[f"{pfx}_s2"] = s2 / n_half
            out[f"{pfx}_c2"] = c2 / n_half
            out[f"{pfx}_both_half_btts"] = bh_btts / n_half
    return out


def tail_6plus_probability(mu_home: float, mu_away: float, league: str | None = None) -> float:
    """Overdispersed (ortak maç-temposu + lig rejimi) 6+ Gol olasılığı."""
    mh = max(1e-4, float(mu_home))
    ma = max(1e-4, float(mu_away))
    nu, alpha_nb, shared_kappa = league_tail_regime(league)
    # Yüksek beklentili (≥3.0) maçlarda maçın açılması ortak pozitif tempo varyansı yaratır
    kappa_eff = max(shared_kappa, MIN_CLUB_KAPPA if (mh + ma) >= 3.0 else 0.015)
    alpha_eff = max(alpha_nb, 0.025 if (mh + ma) >= 3.4 else 0.0)
    mat = regime_score_matrix(mh, ma, com_nu=min(nu, 1.0), alpha_nb=alpha_eff, shared_kappa=kappa_eff, max_goals=14)
    return float(summarize_tail_goals(mat).p_6plus)


def both_halves_btts_probability(
    mu_home: float,
    mu_away: float,
    league: str | None = None,
    *,
    home_1h_share: float = HOME_1H_SHARE_DEFAULT,
    away_1h_share: float = AWAY_1H_SHARE_DEFAULT,
) -> float:
    """Asimetrik Ev/Dep 1Y gol payı + Gamma-Poisson ortak tempo ile İki Yarıda KG Var olasılığı."""
    mh = max(1e-4, float(mu_home))
    ma = max(1e-4, float(mu_away))
    a1_lg, kappa, h_alpha, fgm_1h, fgm_2h = half_model_params(league)
    # Ev ve deplasman ilk yarı paylarının xG ağırlıklı ortalaması + lig profili harmanı
    w_share = (mh * home_1h_share + ma * away_1h_share) / (mh + ma)
    eff_share = 0.5 * a1_lg + 0.5 * w_share
    kappa_eff = max(kappa, MIN_CLUB_KAPPA)
    summary = compute_halves_btts(
        mh, ma,
        first_half_share=eff_share,
        match_kappa=kappa_eff,
        half_alpha=h_alpha,
        fgm_1h=fgm_1h,
        fgm_2h=fgm_2h,
    )
    # Deplasman 1Y gol payı daha düşük olduğundan simetrik modele küçük asimetri düzeltmesi
    asymmetry_scale = float(np.clip((away_1h_share / max(eff_share, 0.30)) ** 0.35, 0.92, 1.02))
    return float(np.clip(summary.p_both_halves_kg * asymmetry_scale, 0.0, 1.0))


def _safe_ladder(match: Mapping[str, Any]) -> tuple[SafeLadderLeg, ...]:
    """Aynı yüksek-gol DNA'lı maçta %65+ (tercihen %70+) güvenli gol merdiveni bacakları."""
    wanted = ("İY 0.5 Üst", "1.5 Üst", "2.5 Üst", "KG Var", "Ev 0.5 Üst", "Dep 0.5 Üst")
    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    out: list[SafeLadderLeg] = []
    for nm in wanted:
        s = sels.get(nm)
        if not s:
            continue
        odds = _flt(s.get("odds")) or 0.0
        p = _flt(s.get("fair_prob")) or 0.0
        if odds >= 1.20 and p >= 0.64:
            out.append(SafeLadderLeg(
                name=nm,
                market=str(s.get("market") or ""),
                selection=str(s.get("selection") or ""),
                odds=odds,
                fair_prob=p,
            ))
    out.sort(key=lambda x: (-x.fair_prob, x.odds))
    return tuple(out[:3])


def _absences(match: Mapping[str, Any], row: Mapping[str, Any] | None) -> tuple[bool, bool, bool, bool]:
    res = match.get("research") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    teams = (row or {}).get("teams") or res.get("teams") or {}
    h_gk = bool((tm.get("home") or {}).get("gk1_out") or (ua.get("home") or {}).get("gk_out") or (teams.get("home") or {}).get("gk1_out"))
    a_gk = bool((tm.get("away") or {}).get("gk1_out") or (ua.get("away") or {}).get("gk_out") or (teams.get("away") or {}).get("gk1_out"))
    h_sc = bool((tm.get("home") or {}).get("top_scorer_out") or (teams.get("home") or {}).get("top_scorer_out"))
    a_sc = bool((tm.get("away") or {}).get("top_scorer_out") or (teams.get("away") or {}).get("top_scorer_out"))
    return h_gk, a_gk, h_sc, a_sc


def _extract_sim_xg(
    match: Mapping[str, Any],
    row: Mapping[str, Any] | None,
    sim_xg: Sequence[float] | None = None,
) -> tuple[float, float] | None:
    """Bağımsız form/DC simülasyonu xG çiftini çıkar (varsa)."""
    raw = sim_xg
    if raw is None and row:
        raw = row.get("sim_xg") or row.get("xg")
    if raw is None:
        raw = match.get("sim_xg")
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        a, b = _flt(raw[0]), _flt(raw[1])
        if a is not None and b is not None and (a + b) > 0:
            return (a, b)
    return None


def _defensive_crisis_and_steam(match: Mapping[str, Any], row: Mapping[str, Any] | None) -> tuple[int, float]:
    """Savunma krizi sayısını (>=2 savunmacı/kritik eksik) ve keskin borsa steam büyüklüğünü (puan) çıkar."""
    res = match.get("research") or {}
    tm = res.get("tm_absences") or {}
    ua = res.get("user_absences") or {}
    teams = (row or {}).get("teams") or res.get("teams") or {}

    def_crisis = 0
    for side in ("home", "away"):
        for src in (tm.get(side) or {}, ua.get(side) or {}, teams.get(side) or {}):
            if not isinstance(src, Mapping):
                continue
            for key in ("defenders_out", "missing_defenders", "critical_defenders_out"):
                v = _flt(src.get(key))
                if v is not None and v > 0:
                    def_crisis = max(def_crisis, int(v))
            if src.get("defensive_crisis"):
                def_crisis = max(def_crisis, 2)
            tot_out = _flt(src.get("n_out") or src.get("missing_count"))
            if tot_out is not None and tot_out >= 4:
                def_crisis = max(def_crisis, 2)

    steam_pp = parse_steam_pp(match, extra_flags=(row or {}).get("flags"))
    return def_crisis, float(steam_pp)


def score_6plus_match(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
    *,
    sim_xg: Sequence[float] | None = None,
) -> ExtremeGoalCandidate | None:
    """Bir maçı 6+ Gol / 5,5 Üst için kuyruk olasılığı + DNA (0–100) ile puanla."""
    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    if mh is None or ma is None or (mh + ma) <= 0:
        return None
    mtot = mh + ma
    mmin = min(mh, ma)
    mdiff = abs(mh - ma)
    lg = str(match.get("league") or "")
    lt = league_tier(lg)
    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    sel6 = sels.get("6+ Gol") or sels.get("5.5 Üst")

    p_tail = tail_6plus_probability(mh, ma, lg)
    p_mkt = _flt(sel6.get("fair_prob")) if sel6 else None
    odds = _flt(sel6.get("odds")) if sel6 else None
    ev = (p_tail * odds - 1.0) if odds is not None else None

    hist = _extract_history_metrics(research_row)
    h_gk, a_gk, h_sc, a_sc = _absences(match, research_row)
    s_xg = _extract_sim_xg(match, research_row, sim_xg)
    def_crisis, steam_pp = _defensive_crisis_and_steam(match, research_row)

    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0

    # 1. Beklenen toplam gol çekirdeği (0..45 puan)
    if mtot >= 4.0:
        score += 45.0
        reasons.append(f"aşırı yüksek xG ({mtot:.2f})")
    elif mtot >= 3.6:
        score += 38.0 + (mtot - 3.6) * 17.5
        reasons.append(f"çok yüksek xG ({mtot:.2f}; 22 Kas %22,9 6+ gol dilimi)")
    elif mtot >= 3.2:
        score += 26.0 + (mtot - 3.2) * 30.0
        reasons.append(f"yüksek toplam xG ({mtot:.2f})")
    elif mtot >= 2.85:
        score += 14.0 + (mtot - 2.85) * 34.0
    else:
        score += max(0.0, (mtot - 2.0) * 16.0)

    # 2. Arketip tespiti (0..22 puan): Yıkım (blowout) vs Açık Düello (shootout)
    if mtot >= 3.50 and mdiff >= 1.15:
        archetype = "yıkım"
        score += 20.0
        reasons.append(f"yıkım arketipi (fark {mdiff:.2f} xG)")
    elif mtot >= 3.10 and mmin >= 1.20:
        archetype = "düello"
        score += 22.0
        reasons.append(f"açık düello arketipi (en düşük taraf {mmin:.2f} xG)")
    elif mtot >= 2.85 and mmin >= 1.10:
        archetype = "düello"
        score += 12.0
    else:
        archetype = "zayıf"

    # 3. Takım geçmişi 4+/5+ gol temposu (0..20 puan) + kısır geçmiş freni (geçmiş yoksa nötr taban +6)
    o35_vals = [v for v in (hist["h_over35"], hist["a_over35"]) if v is not None]
    o45_vals = [v for v in (hist["h_over45"], hist["a_over45"]) if v is not None]
    if len(o35_vals) == 2:
        mean_o35 = sum(o35_vals) / 2.0
        min_o35 = min(o35_vals)
        if mean_o35 >= 0.45 and min_o35 >= 0.30:
            score += min(15.0, mean_o35 * 26.0)
            reasons.append(f"iki takımda yüksek 3.5+ Üst geçmişi (ort %{100*mean_o35:.0f})")
        elif mean_o35 < 0.22:
            score -= 10.0
            warnings.append(f"son maçlarda 3.5+ Üst seyrek (ort %{100*mean_o35:.0f})")
        else:
            score += 5.0
    else:
        score += 6.0  # geçmiş verisi olmayan yüksek xG maçları haksız geri düşmesin
    if len(o45_vals) == 2:
        mean_o45 = sum(o45_vals) / 2.0
        if mean_o45 >= 0.25:
            score += min(8.0, mean_o45 * 22.0)
            reasons.append(f"5+ gol maç geçmişi güçlü (ort %{100*mean_o45:.0f})")

    # 4. Bağımsız simülasyon vs piyasa xG uyumu (v3 — 22 Kas 427 maç bulgusu)
    # Sim xG piyasadan >=0.60 fazla şiştiğinde gerçek maç 2.00 golde kalıyor (%0 6+ gol tuzağı!).
    sim_tot = (s_xg[0] + s_xg[1]) if s_xg is not None else None
    if sim_tot is not None:
        if sim_tot - mtot >= 0.60:
            score -= 10.0
            warnings.append(f"form simülasyonu piyasadan aşırı iyimser (Sim {sim_tot:.2f} vs Piyasa {mtot:.2f} — şişkin form tuzağı)")
        elif mtot >= 3.30 and abs(sim_tot - mtot) <= 0.55:
            score += 5.0
            reasons.append(f"piyasa ve bağımsız simülasyon yüksek tempoda hemfikir (Sim {sim_tot:.2f})")

    # 5. Kadro / kaleci / savunma krizi / keskin steam (-12..+18 puan)
    if h_gk or a_gk:
        score += 8.0
        reasons.append("1. kaleci eksikliği gol patlaması riskini artırıyor")
    if def_crisis >= 2:
        score += 6.0
        reasons.append(f"savunma hattında çoklu eksik ({def_crisis}+ savunma/kritik eksik)")
    if steam_pp >= 5.0 and mtot >= 3.20 and mdiff >= 0.80:
        score += 4.0
        reasons.append(f"keskin borsada güçlü favori akışı (+{steam_pp:.1f}p)")
    if h_sc and a_sc:
        score -= 12.0
        warnings.append("iki takımın da 1. golcüsü eksik")
    elif h_sc or a_sc:
        score -= 5.0
        warnings.append("bir takımda 1. golcü eksik")

    if ev is not None and ev >= 0.05:
        score += min(8.0, ev * 25.0)
        reasons.append(f"pozitif kuyruk EV ({100*ev:+.1f}%)")
    elif ev is not None and ev < -0.25:
        score -= 6.0
        warnings.append(f"Nesine oranı düşük (EV {100*ev:+.1f}%)")

    score = round(float(np.clip(score, 0.0, 100.0)), 1)
    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    return ExtremeGoalCandidate(
        code=int(match["code"]),
        kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
        league=lg,
        match=mname,
        league_tier=lt,
        kind="6+ Gol",
        archetype=archetype,
        mu_home=round(mh, 3),
        mu_away=round(ma, 3),
        mu_total=round(mtot, 3),
        min_mu=round(mmin, 3),
        dna_score=score,
        p_tail=round(p_tail, 4),
        p_market=round(p_mkt, 4) if p_mkt is not None else None,
        nesine_market=str(sel6.get("market")) if sel6 else None,
        nesine_selection=str(sel6.get("selection")) if sel6 else None,
        nesine_odds=odds,
        ev=round(ev, 4) if ev is not None else None,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        safe_ladder=_safe_ladder(match),
        extra={
            "mbs": int(match.get("mbs") or 1),
            "sim_total": round(sim_tot, 3) if sim_tot is not None else None,
            "def_crisis": def_crisis,
            "steam_pp": round(steam_pp, 2),
        },
    )


def score_both_halves_btts_match(
    match: Mapping[str, Any],
    research_row: Mapping[str, Any] | None = None,
    *,
    sim_xg: Sequence[float] | None = None,
) -> ExtremeGoalCandidate | None:
    """Bir maçı 'İki Yarıda KG Var' için asimetrik yarı-tempo modeli + DNA (0–100) ile puanla."""
    mh = _flt(match.get("mu_home"))
    ma = _flt(match.get("mu_away"))
    if mh is None or ma is None or (mh + ma) <= 0:
        return None
    mtot = mh + ma
    mmin = min(mh, ma)
    mdiff = abs(mh - ma)
    sym = mmin / max(mh, ma)
    lg = str(match.get("league") or "")
    lt = league_tier(lg)
    sels = {s.get("name"): s for s in (match.get("selections") or [])}
    sel_kg2 = sels.get("İki Yarıda KG Var")

    p_tail = both_halves_btts_probability(mh, ma, lg)
    p_mkt = _flt(sel_kg2.get("fair_prob")) if sel_kg2 else None
    odds = _flt(sel_kg2.get("odds")) if sel_kg2 else None
    ev = (p_tail * odds - 1.0) if odds is not None else None

    hist = _extract_history_metrics(research_row)
    h_gk, a_gk, h_sc, a_sc = _absences(match, research_row)
    s_xg = _extract_sim_xg(match, research_row, sim_xg)
    def_crisis, steam_pp = _defensive_crisis_and_steam(match, research_row)

    reasons: list[str] = []
    warnings: list[str] = []
    score = 0.0

    # 1. Çift taraflı minimum hücum gücü — İki Yarıda KG Var'ın 1 numaralı motoru (0..42 puan)
    if mmin >= 1.45:
        score += 42.0
        reasons.append(f"çok güçlü iki yönlü xG (en zayıf taraf {mmin:.2f})")
    elif mmin >= 1.25:
        score += 31.0 + (mmin - 1.25) * 55.0
        reasons.append(f"dengeli yüksek xG (en zayıf taraf {mmin:.2f})")
    elif mmin >= 1.05:
        score += 18.0 + (mmin - 1.05) * 65.0
    else:
        score += max(0.0, mmin * 14.0)
        warnings.append(f"tek taraflı xG riski (zayıf taraf {mmin:.2f} < 1.05)")

    # 2. Hücum simetrisi & toplam gol temposu (0..22 puan)
    if sym >= 0.65 and mtot >= 3.10:
        archetype = "dengeli_tempo"
        score += 22.0
        reasons.append(f"yüksek simetri ({sym:.2f}) ve tempo ({mtot:.2f} xG)")
    elif sym >= 0.55 and mtot >= 2.85:
        archetype = "dengeli_tempo"
        score += 14.0
    else:
        archetype = "zayıf"
        if mdiff >= 1.35:
            score -= 8.0
            warnings.append(f"tek taraflı fark maçı riski (xG farkı {mdiff:.2f})")

    # 3. 1. Yarı ve 2. Yarı çift taraflı gol temposu geçmişi (0..24 puan) — tek taraf maskelemesi yok!
    s1_vals = [v for v in (hist["h_s1"], hist["a_s1"]) if v is not None]
    c1_vals = [v for v in (hist["h_c1"], hist["a_c1"]) if v is not None]
    s2_vals = [v for v in (hist["h_s2"], hist["a_s2"]) if v is not None]
    if len(s1_vals) == 2:
        min_s1 = min(s1_vals)
        mean_s1 = sum(s1_vals) / 2.0
        if min_s1 >= 0.45:
            score += min(12.0, mean_s1 * 18.0)
            reasons.append(f"iki takım da 1. yarıda gol buluyor (en düşük %{100*min_s1:.0f})")
        elif min_s1 < 0.30:
            score -= 10.0
            warnings.append(f"bir takım ilk yarılarda kısır (%{100*min_s1:.0f} — 1Y KG tuzağı)")
        else:
            score += 4.0
    else:
        score += 6.0  # geçmiş verisi eksik maçlara nötr taban
    if len(c1_vals) == 2 and min(c1_vals) >= 0.40:
        score += 6.0
        reasons.append(f"iki takım da 1. yarıda gol yiyor (en düşük %{100*min(c1_vals):.0f})")
    if len(s2_vals) == 2 and min(s2_vals) >= 0.55:
        score += 6.0
        reasons.append(f"2. yarı gol sürekliliği yüksek (en düşük %{100*min(s2_vals):.0f})")

    # 4. Bağımsız simülasyon vs piyasa xG uyumu (v3 — 22 Kas 427 maç bulgusu)
    sim_tot = (s_xg[0] + s_xg[1]) if s_xg is not None else None
    if sim_tot is not None:
        if sim_tot - mtot >= 0.60:
            score -= 10.0
            warnings.append(f"form simülasyonu piyasadan aşırı iyimser (Sim {sim_tot:.2f} vs Piyasa {mtot:.2f} — 2Y KG tuzağı)")
        elif mmin >= 1.25 and abs(sim_tot - mtot) <= 0.55:
            score += 4.0
            reasons.append(f"piyasa ve simülasyon çift taraflı yüksek tempoda hemfikir (Sim {sim_tot:.2f})")

    # 5. Kadro / kaleci / savunma krizi + EV ayarı
    if h_gk or a_gk:
        score += 7.0
        reasons.append("1. kaleci eksikliği iki yarıda da gol şansını artırıyor")
    if def_crisis >= 2 and mmin >= 1.15:
        score += 5.0
        reasons.append(f"savunma hattı eksikleri ({def_crisis}+) iki yarıda da gol şansını artırıyor")
    if h_sc or a_sc:
        score -= 10.0
        warnings.append("1. golcü eksikliği çift taraflı gol beklentisini zayıflatıyor")

    if ev is not None and ev >= 0.03:
        score += min(8.0, ev * 25.0)
        reasons.append(f"pozitif kuyruk EV ({100*ev:+.1f}%)")
    elif ev is not None and ev < -0.25:
        score -= 6.0
        warnings.append(f"Nesine oranı sıkışık (EV {100*ev:+.1f}%)")

    score = round(float(np.clip(score, 0.0, 100.0)), 1)
    mname = str(match.get("match") or f"{match.get('home', '')} - {match.get('away', '')}")
    return ExtremeGoalCandidate(
        code=int(match["code"]),
        kickoff=str(match.get("kickoff") or (match.get("kickoff_iso") or "")[:16]),
        league=lg,
        match=mname,
        league_tier=lt,
        kind="İki Yarıda KG Var",
        archetype=archetype,
        mu_home=round(mh, 3),
        mu_away=round(ma, 3),
        mu_total=round(mtot, 3),
        min_mu=round(mmin, 3),
        dna_score=score,
        p_tail=round(p_tail, 4),
        p_market=round(p_mkt, 4) if p_mkt is not None else None,
        nesine_market=str(sel_kg2.get("market")) if sel_kg2 else None,
        nesine_selection=str(sel_kg2.get("selection")) if sel_kg2 else None,
        nesine_odds=odds,
        ev=round(ev, 4) if ev is not None else None,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        safe_ladder=_safe_ladder(match),
        extra={
            "mbs": int(match.get("mbs") or 1),
            "sim_total": round(sim_tot, 3) if sim_tot is not None else None,
            "def_crisis": def_crisis,
            "steam_pp": round(steam_pp, 2),
        },
    )


def build_extreme_system(
    candidates: Sequence[ExtremeGoalCandidate],
    budget_tl: float = 100.0,
    *,
    max_legs: int = 6,
    top_n: int = 3,
) -> list[SystemEvaluation]:
    """En yüksek DNA skorlu ekstrem gol adaylarından bütçeye uygun MBS-uyumlu sistem kuponları üretir."""
    legs: list[SystemLeg] = []
    seen: set[int] = set()
    for c in candidates:
        if c.code in seen or c.nesine_odds is None or c.nesine_odds < 2.0:
            continue
        seen.add(c.code)
        legs.append(
            SystemLeg(
                match_id=str(c.code),
                match=c.match,
                name=c.kind,
                odds=float(c.nesine_odds),
                p=float(c.p_tail),
                mbs=int(c.extra.get("mbs") or 1),
                kickoff=c.kickoff,
                league=c.league,
            )
        )
        if len(legs) >= max_legs:
            break
    if len(legs) < 2:
        return []
    return optimize_system(legs, budget_tl, mode="yuksek_oran", top_n=top_n)


def scan_extreme_goals(
    matches: Sequence[Mapping[str, Any]],
    research_by_code: Mapping[int, Mapping[str, Any]] | None = None,
    *,
    only_offered: bool = True,
    min_dna_6plus: float = 55.0,
    min_dna_both_btts: float = 55.0,
    top_n: int = 10,
) -> dict[str, list[ExtremeGoalCandidate]]:
    """Bültendeki tüm fiyatlı maçları tarayıp 6+ Gol ve İki Yarıda KG Var adaylarını ayrı ayrı döndürür."""
    res_map = research_by_code or {}
    c6: list[ExtremeGoalCandidate] = []
    ckg: list[ExtremeGoalCandidate] = []

    for m in matches:
        if m.get("status") != "fiyatlandı":
            continue
        code = int(m["code"])
        row = res_map.get(code)
        r6 = score_6plus_match(m, row)
        if r6 and r6.dna_score >= min_dna_6plus and (not only_offered or r6.nesine_odds is not None):
            c6.append(r6)
        rkg = score_both_halves_btts_match(m, row)
        if rkg and rkg.dna_score >= min_dna_both_btts and (not only_offered or rkg.nesine_odds is not None):
            ckg.append(rkg)

    c6.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0), -x.p_tail))
    ckg.sort(key=lambda x: (-x.dna_score, -(x.ev if x.ev is not None else -9.0), -x.p_tail))
    return {"6plus": c6[:top_n], "both_halves_btts": ckg[:top_n]}
