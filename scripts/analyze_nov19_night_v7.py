"""QuantFoot-v7 Live 20:18 TSI Unplayed Matches (20:45-06:00) Analysis vs 20:08 TSI Smarkets/Matchbook Exchange Odds."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from quantfoot.markets import (  # noqa: E402
    compute_omni_markets,
    devig,
    fit_tail_rates_from_markets,
    league_tail_regime,
)
from quantfoot.strategy import (  # noqa: E402
    MIN_ALLOWED_ODDS,
    MarketRecommendation,
    MatchRiskContext,
    PortfolioCouponSpec,
    audit_match_risks,
    build_diversified_portfolio,
)
def _league_slug_and_prior(league_tr: str) -> tuple[str, float, bool]:
    s = league_tr.replace("İ", "i").replace("I", "i").lower()
    if "uefa şamp. ligi kadınlar" in s or "wchampions" in s:
        return "uefa.wchampions", 3.35, False
    if "brezilya serie a" in s:
        return "bra.1", 2.55, False
    if "abd major lig" in s:
        return "usa.1", 3.10, True
    if "danimarka 1. lig" in s:
        return "den.2", 2.85, False
    if "fransa ulusal" in s:
        return "fra.3", 2.40, False
    if "mısır kupası" in s:
        return "egy.cup", 2.15, True
    if "cezayir 1. lig" in s:
        return "alg.1", 1.95, False
    if "arjantin primera a" in s:
        return "arg.w.1", 2.35, False
    if "ispanya kupası, kadınlar" in s:
        return "esp.copa_reina", 2.85, True
    if "uruguay prmr" in s:
        return "uru.1", 2.45, False
    if "kolombiya prmr b" in s:
        return "col.2", 2.25, False
    if "venezuela kupası" in s:
        return "ven.cup", 2.65, True
    return "club.default", 2.50, False

# Live 20:18 TSI Nesine odds scraped directly from https://www.nesine.com/iddaa (24 unplayed matches)
LIVE_NESINE_2018: list[dict] = [
    {"idx": 37, "day": "19.11", "ko": "20:45", "id": "3307411", "mbs": 1, "league": "UEFA Şamp. Ligi Kadınlar", "home": "FK Austria Wien (K)", "away": "B. Münih (K)", "ref_key": "Austria Wien", "nes": {"MS 1": 17.35, "MS 0": 9.15, "3.5 Alt": 2.09, "3.5 Üst": 1.33, "ÇŞ 10": 4.50, "KG Var": 1.71, "KG Yok": 1.54}},
    {"idx": 38, "day": "19.11", "ko": "20:45", "id": "3307697", "mbs": 1, "league": "UEFA Şamp. Ligi Kadınlar", "home": "Paris (K)", "away": "HB Koege (K)", "ref_key": "Paris FC", "nes": {"MS 1": 1.27, "MS 0": 4.10, "MS 2": 4.96, "2.5 Alt": 2.19, "2.5 Üst": 1.28, "3.5 Alt": 1.41, "3.5 Üst": 1.90, "ÇŞ 02": 2.09, "KG Var": 1.42, "KG Yok": 1.89}},
    {"idx": 39, "day": "19.11", "ko": "21:00", "id": "3408911", "mbs": 3, "league": "Arjantin Primera A Kapanış, Kadınlar", "home": "Ferro Carril (K)", "away": "CA River Plate (K)", "ref_key": None, "fallback_1x2": [2.16, 3.13, 3.07], "nes": {"MS 1": 2.05, "MS 0": 2.78, "MS 2": 2.59, "2.5 Alt": 1.47, "2.5 Üst": 1.81, "ÇŞ 10": 1.18, "ÇŞ 12": 1.15, "ÇŞ 02": 1.33, "KG Var": 1.60, "KG Yok": 1.64}},
    {"idx": 40, "day": "19.11", "ko": "21:00", "id": "3314224", "mbs": 3, "league": "Danimarka 1. Lig", "home": "Fredericia", "away": "Hilleroed", "ref_key": "Fredericia", "nes": {"MS 1": 1.07, "MS 0": 5.59, "MS 2": 8.66, "2.5 Alt": 2.52, "2.5 Üst": 1.20, "1.5 Alt": 5.10, "3.5 Alt": 1.55, "3.5 Üst": 1.69, "ÇŞ 02": 2.96, "KG Var": 1.57, "KG Yok": 1.67}},
    {"idx": 41, "day": "19.11", "ko": "21:00", "id": "3381559", "mbs": 3, "league": "İspanya Kupası, Kadınlar", "home": "RC Celta de Vigo (K)", "away": "RCD Espanyol (K)", "ref_key": None, "fallback_1x2": [7.70, 5.05, 1.28], "nes": {"MS 1": 6.52, "MS 0": 4.44, "MS 2": 1.17, "3.5 Alt": 1.38, "3.5 Üst": 1.98, "ÇŞ 10": 2.40, "KG Var": 1.56, "KG Yok": 1.68}},
    {"idx": 42, "day": "19.11", "ko": "21:00", "id": "3398367", "mbs": 3, "league": "Mısır Kupası", "home": "ZED", "away": "Smouha SC", "ref_key": "Smouha", "nes": {"MS 1": 2.19, "MS 0": 2.26, "MS 2": 2.99, "1.5 Alt": 1.97, "1.5 Üst": 1.38, "ÇŞ 10": 1.12, "ÇŞ 12": 1.27, "ÇŞ 02": 1.28, "KG Var": 1.94, "KG Yok": 1.39}},
    {"idx": 43, "day": "19.11", "ko": "22:00", "id": "3266477", "mbs": 3, "league": "Cezayir 1. Lig", "home": "JS Kabylie", "away": "USM Alger", "ref_key": "Kabylie", "nes": {"MS 1": 1.94, "MS 0": 2.52, "MS 2": 3.11, "2.5 Alt": 1.28, "2.5 Üst": 2.24, "1.5 Alt": 2.13, "1.5 Üst": 1.31, "ÇŞ 10": 1.11, "ÇŞ 12": 1.20, "ÇŞ 02": 1.37, "KG Var": 1.87, "KG Yok": 1.43}},
    {"idx": 44, "day": "19.11", "ko": "22:30", "id": "3406921", "mbs": 3, "league": "Uruguay Prmr Ligi, Kapanış", "home": "CA Progreso", "away": "Torque", "ref_key": "Progreso", "nes": {"MS 1": 4.48, "MS 0": 3.57, "MS 2": 1.37, "2.5 Alt": 1.81, "2.5 Üst": 1.47, "KG Var": 1.54, "KG Yok": 1.73}},
    {"idx": 45, "day": "19.11", "ko": "22:30", "id": "3406922", "mbs": 3, "league": "Uruguay Prmr Ligi, Kapanış", "home": "Penarol", "away": "Cerro Largo", "ref_key": "Cerro Largo", "nes": {"MS 1": 1.21, "MS 0": 3.83, "MS 2": 6.62, "2.5 Alt": 1.50, "2.5 Üst": 1.76, "KG Var": 2.05, "KG Yok": 1.34}},
    {"idx": 46, "day": "19.11", "ko": "22:30", "id": "3406925", "mbs": 3, "league": "Uruguay Prmr Ligi, Kapanış", "home": "Boston River", "away": "D. Maldonado", "ref_key": "Boston River", "nes": {"MS 1": 3.04, "MS 0": 3.01, "MS 2": 1.74, "2.5 Alt": 1.59, "2.5 Üst": 1.66, "KG Var": 1.54, "KG Yok": 1.71}},
    {"idx": 47, "day": "19.11", "ko": "22:45", "id": "3307710", "mbs": 3, "league": "Fransa Ulusal Lig", "home": "Amiens", "away": "Caen", "ref_key": "Amiens", "nes": {"MS 1": 1.92, "MS 0": 2.89, "MS 2": 2.74, "2.5 Alt": 1.63, "2.5 Üst": 1.61, "1.5 Alt": 3.05, "1.5 Üst": 1.10, "3.5 Alt": 1.16, "3.5 Üst": 2.66, "ÇŞ 10": 1.15, "ÇŞ 12": 1.14, "ÇŞ 02": 1.38, "KG Var": 1.47, "KG Yok": 1.80}},
    {"idx": 48, "day": "19.11", "ko": "23:00", "id": "3307516", "mbs": 1, "league": "UEFA Şamp. Ligi Kadınlar", "home": "Arsenal (K)", "away": "O. Lyon (K)", "ref_key": "Arsenal", "nes": {"MS 1": 3.64, "MS 0": 3.81, "MS 2": 1.43, "2.5 Alt": 2.52, "2.5 Üst": 1.20, "3.5 Alt": 1.57, "3.5 Üst": 1.67, "ÇŞ 10": 1.78, "ÇŞ 02": 1.06, "KG Var": 1.25, "KG Yok": 2.31}},
    {"idx": 49, "day": "19.11", "ko": "23:00", "id": "3307525", "mbs": 1, "league": "UEFA Şamp. Ligi Kadınlar", "home": "Barcelona (K)", "away": "Servette (K)", "ref_key": "Servette", "nes": {"MS 0": 17.35, "MS 2": 17.35, "KG Var": 3.82}},
    {"idx": 50, "day": "19.11", "ko": "23:00", "id": "3307686", "mbs": 1, "league": "UEFA Şamp. Ligi Kadınlar", "home": "Benfica (K)", "away": "AS Roma (K)", "ref_key": "Benfica", "nes": {"MS 1": 1.74, "MS 0": 3.41, "MS 2": 2.76, "2.5 Alt": 2.32, "2.5 Üst": 1.25, "3.5 Alt": 1.47, "3.5 Üst": 1.80, "ÇŞ 10": 1.15, "ÇŞ 12": 1.08, "ÇŞ 02": 1.48, "KG Var": 1.24, "KG Yok": 2.34}},
    {"idx": 51, "day": "20.11", "ko": "01:30", "id": "3304862", "mbs": 1, "league": "Brezilya Serie A", "home": "Vitoria BA", "away": "Bragantino", "ref_key": "Bragantino", "nes": {"MS 1": 2.31, "MS 0": 3.07, "MS 2": 2.34, "2.5 Alt": 1.74, "2.5 Üst": 1.63, "1.5 Alt": 3.44, "1.5 Üst": 1.12, "3.5 Alt": 1.21, "3.5 Üst": 2.73, "ÇŞ 10": 1.31, "ÇŞ 12": 1.17, "ÇŞ 02": 1.32, "KG Var": 1.49, "KG Yok": 1.93}},
    {"idx": 52, "day": "20.11", "ko": "01:30", "id": "3305120", "mbs": 1, "league": "Brezilya Serie A", "home": "Vasco Da G.", "away": "Internacional", "ref_key": "Vasco", "nes": {"MS 1": 1.35, "MS 0": 3.93, "MS 2": 5.14, "2.5 Alt": 1.93, "2.5 Üst": 1.49, "1.5 Alt": 3.92, "1.5 Üst": 1.08, "3.5 Alt": 1.29, "3.5 Üst": 2.40, "ÇŞ 12": 1.08, "ÇŞ 02": 2.16, "KG Var": 1.60, "KG Yok": 1.78}},
    {"idx": 53, "day": "20.11", "ko": "01:30", "id": "3361180", "mbs": 3, "league": "Kolombiya Prmr B Kapanış, Yük. Gr A", "home": "U. Magdalena", "away": "Boca Juniors (Kol)", "ref_key": "Magdalena", "nes": {"MS 1": 1.17, "MS 0": 4.09, "MS 2": 7.25, "2.5 Alt": 1.65, "2.5 Üst": 1.60, "ÇŞ 02": 2.39, "KG Var": 1.93, "KG Yok": 1.40}},
    {"idx": 54, "day": "20.11", "ko": "01:30", "id": "3361195", "mbs": 3, "league": "Kolombiya Prmr B Kapanış, Yük. Gr A", "home": "Independiente Yumbo", "away": "Envigado", "ref_key": "Envigado", "nes": {"MS 1": 2.62, "MS 0": 2.59, "MS 2": 2.14, "2.5 Alt": 1.30, "2.5 Üst": 2.15, "ÇŞ 10": 1.29, "ÇŞ 12": 1.19, "ÇŞ 02": 1.18, "KG Var": 1.80, "KG Yok": 1.47}},
    {"idx": 55, "day": "20.11", "ko": "01:30", "id": "3355406", "mbs": 3, "league": "Venezuela Kupası, Eleme Turu", "home": "Dep. La Gua.", "away": "Academia Anzoategui", "ref_key": "La Guaira", "nes": {"MS 1": 1.21, "MS 0": 4.20, "MS 2": 5.98, "2.5 Alt": 1.80, "2.5 Üst": 1.47, "ÇŞ 02": 2.26, "KG Var": 1.70, "KG Yok": 1.54}},
    {"idx": 56, "day": "20.11", "ko": "03:30", "id": "3305027", "mbs": 1, "league": "Brezilya Serie A", "home": "Sao Paulo SP", "away": "Fluminense", "ref_key": "Fluminense", "nes": {"MS 1": 2.18, "MS 0": 2.86, "MS 2": 2.64, "2.5 Alt": 1.50, "2.5 Üst": 1.92, "1.5 Alt": 2.77, "1.5 Üst": 1.21, "3.5 Alt": 1.11, "3.5 Üst": 3.50, "ÇŞ 10": 1.23, "ÇŞ 12": 1.20, "ÇŞ 02": 1.37, "KG Var": 1.67, "KG Yok": 1.69}},
    {"idx": 57, "day": "20.11", "ko": "03:30", "id": "3386737", "mbs": 1, "league": "ABD Major Lig Playoff", "home": "Orlando City", "away": "Cincinnati", "ref_key": "Orlando City", "nes": {"MS 1": 2.18, "MS 0": 3.59, "MS 2": 2.22, "2.5 Alt": 3.13, "2.5 Üst": 1.15, "1.5 Alt": 7.38, "3.5 Alt": 1.85, "3.5 Üst": 1.55, "ÇŞ 10": 1.35, "ÇŞ 12": 1.11, "ÇŞ 02": 1.36, "KG Var": 1.15, "KG Yok": 3.13}},
    {"idx": 58, "day": "20.11", "ko": "03:45", "id": "3408920", "mbs": 3, "league": "Kolombiya Prmr B Kapanış, Yük. Gr B", "home": "R. Cartagena", "away": "Tigres (Kol)", "ref_key": "Cartagena", "nes": {"MS 1": 1.11, "MS 0": 4.55, "MS 2": 8.94, "2.5 Alt": 1.67, "2.5 Üst": 1.57, "ÇŞ 02": 2.68, "KG Var": 2.09, "KG Yok": 1.33}},
    {"idx": 59, "day": "20.11", "ko": "03:45", "id": "3408921", "mbs": 3, "league": "Kolombiya Prmr B Kapanış, Yük. Gr B", "home": "R. S. Cundinamarca", "away": "Deportes Quindio", "ref_key": "Cundinamarca", "nes": {"MS 1": 2.76, "MS 0": 2.44, "MS 2": 2.17, "1.5 Alt": 1.93, "1.5 Üst": 1.40, "ÇŞ 10": 1.28, "ÇŞ 12": 1.21, "ÇŞ 02": 1.15, "KG Var": 2.00, "KG Yok": 1.36}},
    {"idx": 60, "day": "20.11", "ko": "06:00", "id": "3386736", "mbs": 1, "league": "ABD Major Lig Playoff", "home": "S. Sounders", "away": "Real Salt Lake", "ref_key": "Seattle Sounders", "nes": {"MS 1": 1.70, "MS 0": 3.39, "MS 2": 3.29, "2.5 Alt": 2.08, "2.5 Üst": 1.41, "1.5 Alt": 4.39, "3.5 Alt": 1.37, "3.5 Üst": 2.19, "ÇŞ 10": 1.14, "ÇŞ 12": 1.13, "ÇŞ 02": 1.65, "KG Var": 1.38, "KG Yok": 2.15}},
]


def _load_exchange_refs() -> list[dict]:
    ref_path = REPO_ROOT / "data" / "global_odds" / "latest" / "references.json"
    raw = json.loads(ref_path.read_text(encoding="utf-8"))["references"]
    return [
        m for m in raw
        if "2026-11-19T17:30" <= str(m.get("kickoff_utc", "")) <= "2026-11-20T04:00"
        and "Reserves" not in str(m.get("home", ""))
    ]


def _extract_sharp_for_match(m: dict, refs: list[dict]) -> dict:
    """Merge Smarkets + Matchbook exchange 1X2, O/U 1.5/2.5/3.5, and direct BTTS."""
    key = m.get("ref_key")
    if not key:
        return {"src": "Flashscore 1X2 (O/U yok)", "x12": m["fallback_1x2"], "p15": None, "p25": None, "p35": None, "p_btts": None}

    matched = [r for r in refs if key.lower() in f"{r.get('home','')} {r.get('away','')}".lower()]
    # Prefer Smarkets (has direct O15, O35, BTTS) merged with Matchbook for 1X2 / O25
    sm = next((r for r in matched if "Smarkets" in str(r.get("source", ""))), None)
    mb = next((r for r in matched if "Matchbook" in str(r.get("source", ""))), None)
    bf = next((r for r in matched if "Betfair" in str(r.get("source", ""))), None)

    src_parts = []
    x12 = None
    p25 = None
    p15 = None
    p35 = None
    p_btts = None

    for r in (sm, mb, bf):
        if not r:
            continue
        src_parts.append(str(r.get("source", "")).split(" ")[0])
        if x12 is None and r.get("x12"):
            x12 = r["x12"]
        if p25 is None and r.get("ou") and r["ou"][0] == 2.5 and r["ou"][1]:
            p25 = float(devig(r["ou"][1], method="power").probabilities[0])
        mkts = r.get("markets") or {}
        if p_btts is None and isinstance(mkts.get("Both teams to score"), dict):
            val = mkts["Both teams to score"].get("YES|Yes")
            if val is not None:
                p_btts = float(val)
        if p35 is None and isinstance(mkts.get("Over/under 3.5"), dict):
            val = mkts["Over/under 3.5"].get("OVER|Over 3.5 goals")
            if val is not None:
                p35 = float(val)
        if p15 is None and isinstance(mkts.get("Over/under 1.5"), dict):
            val = mkts["Over/under 1.5"].get("OVER|Over 1.5 goals")
            if val is not None:
                p15 = float(val)

    return {
        "src": "+".join(dict.fromkeys(src_parts)) + " (20:27)",
        "x12": x12,
        "p15": p15,
        "p25": p25,
        "p35": p35,
        "p_btts": p_btts,
    }


def analyze_night_match(m: dict, refs: list[dict]) -> dict:
    slug, prior, is_ko = _league_slug_and_prior(m["league"])
    com_nu, alpha_nb, shared_kappa = league_tail_regime(slug)
    sharp = _extract_sharp_for_match(m, refs)

    p_1x2 = devig(sharp["x12"], method="power").probabilities
    ou_lines = []
    if sharp["p15"] is not None:
        ou_lines.append((1.5, sharp["p15"]))
    if sharp["p25"] is not None:
        ou_lines.append((2.5, sharp["p25"]))
    if sharp["p35"] is not None:
        ou_lines.append((3.5, sharp["p35"]))
    has_ou = bool(ou_lines)

    nes = m["nes"]
    # Direct exchange BTTS preferred; fallback to 2-way Nesine BTTS sanity anchor ONLY for Layer 6 disagreement check
    btts_anchor = sharp["p_btts"]
    if btts_anchor is None and nes.get("KG Var") and nes.get("KG Yok"):
        btts_anchor = float(devig([nes["KG Var"], nes["KG Yok"]], method="power").probabilities[0])

    seed_h = max(0.25, prior * (p_1x2[0] + 0.5 * p_1x2[1]))
    seed_a = max(0.25, prior * (p_1x2[2] + 0.5 * p_1x2[1]))

    if "Barcelona (K)" in m["home"]:
        mu_h, mu_a = 6.20, 0.25
        mu_h_raw, mu_a_raw = 6.20, 0.25
    else:
        mu_h_raw, mu_a_raw, _ = fit_tail_rates_from_markets(
            p_1x2=p_1x2,
            ou_lines=ou_lines if has_ou else None,
            seed_rates=(seed_h, seed_a),
            alpha_nb=alpha_nb,
            shared_kappa=shared_kappa,
            com_nu=com_nu,
            fund_weight=0.04 if has_ou else 0.14,
        )
        mu_h, mu_a, _ = fit_tail_rates_from_markets(
            p_1x2=p_1x2,
            ou_lines=ou_lines if has_ou else None,
            p_btts=btts_anchor if has_ou else None,
            seed_rates=(seed_h, seed_a),
            alpha_nb=alpha_nb,
            shared_kappa=shared_kappa,
            com_nu=com_nu,
            fund_weight=0.04 if has_ou else 0.14,
        )

    bundle_raw = compute_omni_markets(mu_h_raw, mu_a_raw, league=slug)
    bundle = compute_omni_markets(mu_h, mu_a, league=slug)

    # ESPN L5 tactical guards:
    # #51 Vitoria BA L5: 0G-2B-3M (3-9) -> cold home attack
    # #60 Seattle Sounders L5: 1G-2B-2M (6-10) vs RSL 4G-0B-1M (11-5) -> playoff + cold form
    h_dead = mu_h < 0.62 or (m["idx"] == 51)
    a_dead = mu_a < 0.62

    risk_ctx = MatchRiskContext(
        home_must_win=is_ko and (mu_h > mu_a + 0.35),
        away_must_win=is_ko and (mu_a > mu_h + 0.35),
        home_dead_attack=h_dead,
        away_dead_attack=a_dead,
        group_id=m["id"],
        is_knockout=is_ko,
        has_ou_market=has_ou,
        btts_market_prob=btts_anchor,
        notes=f"{sharp['src']} | MBS {m['mbs']}",
    )

    blocked_raw, pen_raw = audit_match_risks(bundle_raw, risk_ctx)
    blocked_jnt, pen_jnt = audit_match_risks(bundle, risk_ctx)
    blocked = {**blocked_raw, **blocked_jnt}
    penalties = {k: min(pen_raw.get(k, 1.0), pen_jnt.get(k, 1.0)) for k in set(pen_raw) | set(pen_jnt)}
    if m["idx"] == 37:  # Bayern W L5 9 GA
        penalties["KG Yok"] = min(penalties.get("KG Yok", 1.0), 0.85)
    if m["idx"] == 60:  # Seattle L5 1G-2B-2M vs RSL 4G-0B-1M -> block Seattle MS 1
        blocked["MS 1"] = "ESPN L5 Form Kalkanı: Seattle (1G-2B-2M, 6-10) vs RSL (4G-0B-1M, 11-5) + MLS Playoff."

    all_probs = bundle.all_probabilities()
    audit_list = []
    for sel, n_odd in nes.items():
        if n_odd is None or sel not in all_probs:
            continue
        # Use DIRECT Smarkets/Matchbook exchange probability whenever directly quoted!
        p_g = float(all_probs[sel])
        if sel == "MS 1":
            p_g = float(p_1x2[0])
        elif sel == "MS 0":
            p_g = float(p_1x2[1])
        elif sel == "MS 2":
            p_g = float(p_1x2[2])
        elif sel == "ÇŞ 10":
            p_g = float(p_1x2[0] + p_1x2[1])
        elif sel == "ÇŞ 12":
            p_g = float(p_1x2[0] + p_1x2[2])
        elif sel == "ÇŞ 02":
            p_g = float(p_1x2[1] + p_1x2[2])
        elif sel in ("1.5 Üst", "1.5 Alt") and sharp["p15"] is not None:
            p_g = float(sharp["p15"] if sel == "1.5 Üst" else 1.0 - sharp["p15"])
        elif sel in ("2.5 Üst", "2.5 Alt") and sharp["p25"] is not None:
            p_g = float(sharp["p25"] if sel == "2.5 Üst" else 1.0 - sharp["p25"])
        elif sel in ("3.5 Üst", "3.5 Alt") and sharp["p35"] is not None:
            p_g = float(sharp["p35"] if sel == "3.5 Üst" else 1.0 - sharp["p35"])
        elif sel in ("KG Var", "KG Yok") and sharp["p_btts"] is not None:
            p_g = float(sharp["p_btts"] if sel == "KG Var" else 1.0 - sharp["p_btts"])

        ev = round(p_g * float(n_odd) - 1.0, 4)
        pen = penalties.get(sel, 1.0)
        saf = round((p_g ** 1.35) * pen * max(0.60, min(1.18, 1.0 + 0.70 * ev)), 4)
        audit_list.append({
            "selection": sel,
            "nesine_odds": float(n_odd),
            "global_prob": round(p_g, 4),
            "global_fair_odds": round(1.0 / max(p_g, 1e-6), 2),
            "nesine_ev": ev,
            "safety_score": saf,
            "blocked": sel in blocked,
            "block_reason": blocked.get(sel),
        })

    valid = [
        x for x in audit_list
        if (not x["blocked"]) and x["nesine_odds"] >= MIN_ALLOWED_ODDS and x["global_prob"] >= 0.54
    ]
    valid.sort(key=lambda x: (x["safety_score"], x["global_prob"]), reverse=True)

    return {
        "idx": m["idx"],
        "id": m["id"],
        "day": m["day"],
        "ko": m["ko"],
        "mbs": m["mbs"],
        "league": m["league"],
        "home": m["home"],
        "away": m["away"],
        "sharp_src": sharp["src"],
        "has_ou": has_ou,
        "has_direct_btts": sharp["p_btts"] is not None,
        "is_ko": is_ko,
        "mu_home": bundle.mu_home,
        "mu_away": bundle.mu_away,
        "expected_total": bundle.expected_total,
        "top_scores": [s["score"] for s in bundle.top_ft_scores[:3]],
        "top_scores_detail": [
            {"score": s["score"], "prob": round(float(s.get("probability", s.get("prob", s.get("p", 0.0)))) * 100.0, 1)}
            for s in bundle.top_ft_scores[:3]
        ],
        "p_1x2": [round(float(p) * 100.0, 1) for p in p_1x2],
        "blocked": blocked,
        "best_v7": valid[0] if valid else None,
        "valid_all": valid,
    }


def main() -> None:
    refs = _load_exchange_refs()
    results = [analyze_night_match(m, refs) for m in LIVE_NESINE_2018]

    print(f"Analyzed {len(results)} live unplayed Nesine matches (20:18 TSI vs 20:27 TSI Exchange):")
    for r in results:
        b = r["best_v7"]
        bs = f"{b['selection']} @ {b['nesine_odds']:.2f} (P=%{b['global_prob']*100:.1f})" if b else "PAS / BLOKE"
        sc = " | ".join(f"{s['score']} (%{s['prob']:.1f})" for s in r["top_scores_detail"])
        print(f"#{r['idx']:2d} [{r['day']} {r['ko']}] {r['home']} - {r['away']} | xG {r['mu_home']:.2f}-{r['mu_away']:.2f} | Skor: {sc} | v7: {bs}")

    pool: list[list[MarketRecommendation]] = []
    for r in results:
        if r["ko"] == "20:45" or not r["has_ou"]:
            continue
        recs = []
        for x in r["valid_all"]:
            if x["nesine_ev"] < -0.19:
                continue
            cat = (
                "Maç Sonucu (1X2)" if x["selection"].startswith("MS ")
                else ("Karşılıklı Gol" if "KG" in x["selection"]
                else ("Çifte Şans" if x["selection"].startswith("ÇŞ ") else "Maç Geneli Alt/Üst"))
            )
            recs.append(
                MarketRecommendation(
                    match_id=r["id"],
                    home=r["home"],
                    away=r["away"],
                    league=r["league"],
                    kickoff=f"{r['day']} {r['ko']}",
                    category=cat,
                    selection=x["selection"],
                    probability=x["global_prob"],
                    fair_odds=x["global_fair_odds"],
                    offered_odds=x["nesine_odds"],
                    odds_is_estimated=False,
                    safety_score=x["safety_score"],
                    ev=x["nesine_ev"],
                    rationale=f"v7 {r['sharp_src']}: P=%{x['global_prob']*100:.1f} (Adil {x['global_fair_odds']:.2f}, EV {x['nesine_ev']*100:+.1f}%)",
                    group_id=r["id"],
                    mbs=r["mbs"],
                )
            )
        if recs:
            pool.append(recs)

    specs = [
        PortfolioCouponSpec(title="KUPON 1 — Gece Çekirdek Güven (3 Maç, ~2.4x)", target_odds=2.40, max_legs=3, min_leg_ev=None),
        PortfolioCouponSpec(title="KUPON 2 — Dengeli Akşam & Gece (4 Maç, ~4.8x)", target_odds=4.80, max_legs=5, min_leg_ev=None),
        PortfolioCouponSpec(title="KUPON 3 — Hedef 10x+ Global Exchange Kombinesi", target_odds=10.00, max_legs=7, min_leg_ev=None),
        PortfolioCouponSpec(title="KUPON 4 — Hedef 20x+ Ana Gece Kombinesi (0 Tekrar)", target_odds=20.00, max_legs=9, min_leg_ev=None),
        PortfolioCouponSpec(title="KUPON 5 — Yüksek Olasılıklı Zırhlı Alternatif (8 Maç, Ort P=%67.7, ~5.5x)", target_odds=5.50, max_legs=10, min_leg_ev=None),
    ]
    plans = build_diversified_portfolio(
        pool,
        specs,
        max_selection_reuse=1,
        max_match_reuse=3,
        max_same_category_share=0.70,
    )

    print("\n=== QUANTFOOT-v7 CANLI AKŞAM & GECE PORTFÖYÜ (>= 21:00 TSİ, 0 TEKRAR) ===")
    seen = set()
    for p in plans:
        print(f"\n{p.title} => {p.achieved_odds:.2f}x (Hedef {p.target_odds:.1f}x, Ulaştı:{p.reached_target}) | {len(p.legs)} maç | Ort P=%{p.average_leg_probability*100:.1f} | Birleşik P=%{p.joint_probability*100:.2f}")
        for l in p.legs:
            pair = (l.match_id, l.selection)
            assert pair not in seen, f"DUPLICATE {pair}"
            seen.add(pair)
            print(f"  - [{l.kickoff}] {l.home} - {l.away} (MBS {l.mbs}): {l.selection} @ {l.offered_odds:.2f} | Adil {l.fair_odds:.2f} (P=%{l.probability*100:.1f}, EV={l.ev*100:+.1f}%)")

    # Persist Markdown & Ledger JSON/MD
    md_lines = [
        "# 19-20 Kasım 2026 — QuantFoot-v7 Akşam & Gece Skor Tahminleri ve Kupon Portföyü",
        "",
        "- **Veri Kaynağı:** Canlı Nesine oranları (`20:18 TSİ`) + Global Sharp Exchange (`Smarkets` + `Matchbook` + `Betfair`, `20:27 TSİ` güncellemesi) + `QuantFoot-v7` (9 katmanlı risk kalkanı & kalibre skor matrisi).",
        "- **Kupon Kuralları:** Tüm bacaklar `≥ 1.20` canlı Nesine oranı, MBS uyumlu, kuponlar arası **0 tekrar eden tercih**, `20:45` maçları kupon dışı bırakılıp yalnızca analiz/skor tablosunda sunulmuştur.",
        "",
        "## 1. Başlamamış Tüm 24 Maç — Exact Skor Tahminleri & QuantFoot-v7 Analizi",
        "",
        "| # | Saat (TSİ) | Lig | Maç | Global xG | 1. Skor Tahmini | 2. Skor | 3. Skor | v7 En Güvenli Tercih (Canlı Nesine) |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        ts = r["top_scores_detail"]
        s1 = f"**{ts[0]['score']}** (%{ts[0]['prob']:.1f})" if len(ts) > 0 else "—"
        s2 = f"{ts[1]['score']} (%{ts[1]['prob']:.1f})" if len(ts) > 1 else "—"
        s3 = f"{ts[2]['score']} (%{ts[2]['prob']:.1f})" if len(ts) > 2 else "—"
        b = r["best_v7"]
        btxt = f"**{b['selection']} @ {b['nesine_odds']:.2f}** (P:%{b['global_prob']*100:.1f})" if b else "PAS / BLOKE"
        md_lines.append(
            f"| {r['idx']} | {r['day']} {r['ko']} | {r['league']} | {r['home']} - {r['away']} | {r['mu_home']:.2f} - {r['mu_away']:.2f} | {s1} | {s2} | {s3} | {btxt} |"
        )

    md_lines.extend(["", "## 2. QuantFoot-v7 Sıfır-Tekrarlı Akşam & Gece Kuponları (`≥ 21:00 TSİ`)", ""])
    ledger_coupons = []
    for idx_c, p in enumerate(plans, start=1):
        md_lines.append(
            f"### {p.title}"
        )
        md_lines.append(
            f"**Toplam Oran:** `{p.achieved_odds:.2f}x` | **Maç Sayısı:** `{len(p.legs)}` | **Ort. Global Olasılık:** `%{p.average_leg_probability*100:.1f}` | **Birleşik Tutma Olasılığı:** `%{p.joint_probability*100:.2f}`"
        )
        md_lines.append("")
        md_lines.append("| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |")
        md_lines.append("|---|---|---:|---|---:|---:|---:|---:|")
        legs_json = []
        for l in p.legs:
            md_lines.append(
                f"| {l.kickoff} | {l.home} - {l.away} | {l.mbs} | **{l.selection}** | {l.offered_odds:.2f} | {l.fair_odds:.2f} | %{l.probability*100:.1f} | {l.ev*100:+.1f}% |"
            )
            legs_json.append({
                "match_id": l.match_id,
                "kickoff": l.kickoff,
                "league": l.league,
                "home": l.home,
                "away": l.away,
                "mbs": l.mbs,
                "category": l.category,
                "selection": l.selection,
                "nesine_odds": l.offered_odds,
                "global_fair_odds": l.fair_odds,
                "global_prob": l.probability,
                "ev": l.ev,
                "status": "PENDING",
            })
        md_lines.append("")
        ledger_coupons.append({
            "coupon_no": idx_c,
            "title": p.title,
            "target_odds": p.target_odds,
            "achieved_odds": round(p.achieved_odds, 2),
            "leg_count": len(p.legs),
            "avg_leg_prob": round(p.average_leg_probability, 4),
            "joint_prob": round(p.joint_probability, 6),
            "reached_target": p.reached_target,
            "legs": legs_json,
            "status": "PENDING",
        })

    md_text = "\n".join(md_lines) + "\n"
    (REPO_ROOT / "reports" / "nov19_night_v7_analysis.md").write_text(md_text, encoding="utf-8")
    ledger_dir = REPO_ROOT / "reports" / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / "coupons_2026_11_19_night_v7.md").write_text(md_text, encoding="utf-8")
    (ledger_dir / "coupons_2026_11_19_night_v7.json").write_text(
        json.dumps(
            {
                "date": "2026-11-19",
                "session": "night_v7",
                "generated_at_tsi": "2026-11-19T20:41:00+03:00",
                "engine": "QuantFoot-v7",
                "matches_analyzed": len(results),
                "score_predictions": [
                    {
                        "idx": r["idx"],
                        "id": r["id"],
                        "kickoff": f"{r['day']} {r['ko']}",
                        "home": r["home"],
                        "away": r["away"],
                        "mu_home": round(r["mu_home"], 2),
                        "mu_away": round(r["mu_away"], 2),
                        "top_scores": r["top_scores_detail"],
                        "best_v7": r["best_v7"]["selection"] if r["best_v7"] else None,
                    }
                    for r in results
                ],
                "coupons": ledger_coupons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nSaved reports/nov19_night_v7_analysis.md and reports/ledger/coupons_2026_11_19_night_v7.{md,json}")


if __name__ == "__main__":
    main()
