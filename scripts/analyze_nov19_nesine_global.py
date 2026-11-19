"""Global Sharp Benchmark (Pinnacle / Flashscore Global / ESPN) Quantitative Analysis for all 59 Nesine Nov 19-20, 2026 Matches."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from quantfoot.markets import (
    book_overround,
    compute_omni_markets,
    devig,
    fit_tail_rates_from_markets,
    league_tail_regime,
)
from quantfoot.strategy import (
    MIN_ALLOWED_ODDS,
    CouponPlan,
    MarketRecommendation,
    MatchRiskContext,
    audit_match_risks,
    build_target_odds_coupon,
    select_best_valid_bet,
)


def _league_slug_and_prior(league_tr: str) -> tuple[str, float, bool]:
    """Map Turkish Nesine league names to QuantFoot tail-regime slug, league average total goals, and knockout flag."""
    s = league_tr.replace("İ", "i").replace("I", "i").lower()
    if "uefa şamp. ligi kadınlar" in s or "wchampions" in s:
        return "uefa.wchampions", 3.35, False
    if "avustralya şampiyonası" in s:
        return "aus.1", 3.25, False
    if "brezilya serie a" in s:
        return "bra.1", 2.55, False
    if "abd major lig" in s:
        return "usa.1", 3.10, True
    if "danimarka 1. lig" in s:
        return "den.2", 2.85, False
    if "fransa ulusal" in s:
        return "fra.3", 2.40, False
    if "mısır 2. lig" in s:
        return "egy.2", 1.95, False
    if "mısır kupası" in s:
        return "egy.cup", 2.15, True
    if "cezayir 1. lig" in s:
        return "alg.1", 1.95, False
    if "iran pro ligi" in s:
        return "irn.1", 1.85, False
    if "irak ligi" in s:
        return "irq.1", 2.25, False
    if "katar yıldızlar" in s:
        return "qat.1", 3.05, False
    if "arap körfez ligi" in s:
        return "uae.1", 3.30, False
    if "özbekistan" in s:
        return "uzb.1", 2.35, False
    if "uganda" in s:
        return "uga.1", 2.25, False
    if "zambiya" in s:
        return "zam.1", 1.95, False
    if "ürdün kupası" in s:
        return "jor.cup", 2.65, True
    if "slovakya kupası" in s:
        return "svk.cup", 3.15, True
    if "slovenya kupası" in s:
        return "svn.cup", 2.95, True
    if "asean kulüpler" in s:
        return "afc.cup", 2.95, False
    if "bulgaristan 2. lig" in s:
        return "bul.2", 2.45, False
    if "isveç allsvenskan kad" in s:
        return "swe.w.1", 2.85, True
    if "litvanya" in s:
        return "ltu.2", 2.75, True
    if "japonya we ligi" in s:
        return "jpn.w.1", 2.55, False
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


# Complete dataset of all 59 Nesine-visible matches (50 Bugün 19.11 + 9 Overnight 20.11)
# Paired with VERIFIED Global Sharp Market Odds (Tier-1 Pinnacle where available, Tier-2 Flashscore Global id=417)
MATCH_DATA: list[dict] = [
    # --- PART 1: BUGÜN 19.11.2026 (11:30 - 23:00 TSİ, 50 MAÇ) ---
    {
        "idx": 1, "day": "Bugün 19.11", "ko": "11:30", "id": "3307443", "mbs": 2, "extra": "+121",
        "league": "Avustralya Şampiyonası", "home": "Preston Lions", "away": "South Hobart",
        "nes": {"MS 1": None, "MS 0": 6.58, "MS 2": 9.80, "2.5 Alt": 3.28, "2.5 Üst": 1.08, "3.5 Alt": 1.90, "3.5 Üst": 1.41, "ÇŞ 02": 3.33, "KG Var": 1.45, "KG Yok": 1.85},
        "glb_src": "Flashscore Global", "glb_1x2": [1.15, 7.60, 12.20], "glb_ou25": [1.21, 3.58], "glb_ou35": [1.63, 2.17],
    },
    {
        "idx": 2, "day": "Bugün 19.11", "ko": "11:30", "id": "3307643", "mbs": 2, "extra": "+121",
        "league": "Avustralya Şampiyonası", "home": "Queensland L.", "away": "Woll. Wolves",
        "nes": {"MS 1": 1.40, "MS 0": 3.87, "MS 2": 3.89, "2.5 Alt": 2.45, "2.5 Üst": 1.21, "3.5 Alt": 1.54, "3.5 Üst": 1.72, "ÇŞ 02": 1.84, "KG Var": 1.28, "KG Yok": 2.22},
        "glb_src": "Flashscore Global", "glb_1x2": [1.58, 4.33, 4.63], "glb_ou25": [1.36, 2.70], "glb_ou35": [1.99, 1.75],
    },
    {
        "idx": 3, "day": "Bugün 19.11", "ko": "12:00", "id": "3307523", "mbs": 3, "extra": "+19",
        "league": "Japonya WE Ligi Kadınlar", "home": "Omiya (K)", "away": "INAC Kobe L. (K)",
        "nes": {"MS 1": 3.73, "MS 0": 3.24, "MS 2": 1.53, "2.5 Alt": 1.67, "2.5 Üst": 1.57, "ÇŞ 10": 1.67, "ÇŞ 12": 1.09, "KG Var": 1.54, "KG Yok": 1.71},
        "glb_src": "Flashscore Global", "glb_1x2": [3.94, 3.54, 1.75], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 4, "day": "Bugün 19.11", "ko": "15:00", "id": "3307575", "mbs": 3, "extra": "+97",
        "league": "ASEAN Kulüpler Şamp. Grup B", "home": "Preah Khan R. S.", "away": "Port",
        "nes": {"MS 1": 2.12, "MS 0": 3.05, "MS 2": 2.31, "2.5 Alt": 1.74, "2.5 Üst": 1.52, "1.5 Alt": 3.31, "1.5 Üst": 1.08, "3.5 Alt": 1.21, "3.5 Üst": 2.46, "ÇŞ 10": 1.24, "ÇŞ 12": 1.12, "ÇŞ 02": 1.30, "KG Var": 1.41, "KG Yok": 1.89},
        "glb_src": "Flashscore Global", "glb_1x2": [2.32, 3.38, 2.53], "glb_ou25": [1.66, 2.05], "glb_ou35": [2.59, 1.39],
    },
    {
        "idx": 5, "day": "Bugün 19.11", "ko": "15:00", "id": "3307608", "mbs": 3, "extra": "+97",
        "league": "ASEAN Kulüpler Şamp. Grup B", "home": "Persib Bandung", "away": "Shan Utd",
        "nes": {"MS 1": None, "MS 0": 8.09, "MS 2": 17.20, "2.5 Alt": 2.87, "2.5 Üst": 1.13, "3.5 Alt": 1.72, "3.5 Üst": 1.54, "ÇŞ 02": 4.22, "KG Var": 1.92, "KG Yok": 1.41},
        "glb_src": "Flashscore Global + Betfair", "glb_1x2": [1.07, 10.20, 10.60], "glb_ou25": [1.26, 3.20], "glb_ou35": [1.74, 1.94],
    },
    {
        "idx": 6, "day": "Bugün 19.11", "ko": "15:00", "id": "3343240", "mbs": 3, "extra": "+40",
        "league": "Slovakya Kupası", "home": "MFK Lokomotiva Zvolen", "away": "FK Kosice",
        "nes": {"MS 1": 6.98, "MS 0": 4.85, "MS 2": 1.13, "3.5 Alt": 1.57, "3.5 Üst": 1.68, "ÇŞ 10": 2.58, "KG Var": 1.45, "KG Yok": 1.84},
        "glb_src": "Flashscore Global", "glb_1x2": [8.50, 5.50, 1.24], "glb_ou25": [1.33, 2.83], "glb_ou35": [1.93, 1.75],
    },
    {
        "idx": 7, "day": "Bugün 19.11", "ko": "15:30", "id": "3307660", "mbs": 3, "extra": "+97",
        "league": "ASEAN Kulüpler Şamp. Grup B", "home": "Cong An Nhan Dan", "away": "Johor Darul",
        "nes": {"MS 1": 3.63, "MS 0": 3.31, "MS 2": 1.52, "2.5 Alt": 1.87, "2.5 Üst": 1.43, "1.5 Alt": 3.64, "3.5 Alt": 1.28, "3.5 Üst": 2.23, "ÇŞ 10": 1.67, "ÇŞ 12": 1.08, "ÇŞ 02": 1.06, "KG Var": 1.42, "KG Yok": 1.88},
        "glb_src": "Flashscore Global", "glb_1x2": [4.20, 3.90, 1.63], "glb_ou25": [1.50, 2.28], "glb_ou35": [2.33, 1.51],
    },
    {
        "idx": 8, "day": "Bugün 19.11", "ko": "15:30", "id": "3307479", "mbs": 3, "extra": "+19",
        "league": "Mısır 2. Lig", "home": "EL Terasanah", "away": "Telecom Egypt",
        "nes": {"MS 1": 2.17, "MS 0": 2.23, "MS 2": 3.09, "1.5 Alt": 1.84, "1.5 Üst": 1.45, "ÇŞ 10": 1.11, "ÇŞ 12": 1.27, "ÇŞ 02": 1.28, "KG Var": 2.07, "KG Yok": 1.34},
        "glb_src": "Flashscore Global", "glb_1x2": [2.23, 2.75, 3.36], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 9, "day": "Bugün 19.11", "ko": "15:30", "id": "3307497", "mbs": 3, "extra": "+19",
        "league": "Mısır 2. Lig", "home": "La Viena", "away": "El Sekka El Hadid",
        "nes": {"MS 1": 2.32, "MS 0": 2.35, "MS 2": 2.65, "1.5 Alt": 1.91, "1.5 Üst": 1.41, "ÇŞ 10": 1.17, "ÇŞ 12": 1.24, "ÇŞ 02": 1.24, "KG Var": 2.00, "KG Yok": 1.36},
        "glb_src": "Flashscore Global", "glb_1x2": [2.49, 2.75, 2.80], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 10, "day": "Bugün 19.11", "ko": "15:30", "id": "3307500", "mbs": 3, "extra": "+19",
        "league": "Mısır 2. Lig", "home": "El Daklyeh", "away": "Ismaily Sc",
        "nes": {"MS 1": 3.08, "MS 0": 2.50, "MS 2": 1.97, "1.5 Alt": 2.13, "1.5 Üst": 1.31, "ÇŞ 10": 1.35, "ÇŞ 12": 1.21, "ÇŞ 02": 1.11, "KG Var": 1.86, "KG Yok": 1.44},
        "glb_src": "Flashscore Global", "glb_1x2": [3.38, 2.95, 2.11], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 11, "day": "Bugün 19.11", "ko": "15:30", "id": "3307505", "mbs": 3, "extra": "+19",
        "league": "Mısır 2. Lig", "home": "Farco", "away": "Entag Harby",
        "nes": {"MS 1": 1.70, "MS 0": 2.76, "MS 2": 3.54, "2.5 Alt": 1.42, "2.5 Üst": 1.88, "ÇŞ 10": 1.07, "ÇŞ 12": 1.15, "ÇŞ 02": 1.51, "KG Var": 1.70, "KG Yok": 1.55},
        "glb_src": "Flashscore Global", "glb_1x2": [1.85, 3.20, 3.91], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 12, "day": "Bugün 19.11", "ko": "15:30", "id": "3307707", "mbs": 3, "extra": "+19",
        "league": "Mısır 2. Lig", "home": "Baladiyyat AL M.", "away": "Haras Hodood",
        "nes": {"MS 1": 2.47, "MS 0": 2.53, "MS 2": 2.30, "2.5 Alt": 1.38, "2.5 Üst": 1.97, "ÇŞ 10": 1.25, "ÇŞ 12": 1.20, "ÇŞ 02": 1.21, "KG Var": 1.67, "KG Yok": 1.58},
        "glb_src": "Flashscore Global", "glb_1x2": [2.60, 2.97, 2.49], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 13, "day": "Bugün 19.11", "ko": "15:30", "id": "3351650", "mbs": 3, "extra": "+3",
        "league": "Slovenya Kupası", "home": "ND Beltinci", "away": "NK Celje",
        "nes": {"MS 1": 5.72, "MS 0": 4.37, "MS 2": 1.21},
        "glb_src": "Flashscore Global", "glb_1x2": [7.13, 4.80, 1.32], "glb_ou25": [1.45, 2.41], "glb_ou35": [2.22, 1.56],
    },
    {
        "idx": 14, "day": "Bugün 19.11", "ko": "15:30", "id": "3351652", "mbs": 3, "extra": "+3",
        "league": "Slovenya Kupası", "home": "Roltek Dob", "away": "NK Bistrica",
        "nes": {"MS 1": 3.94, "MS 0": 3.36, "MS 2": 1.47},
        "glb_src": "Flashscore Global", "glb_1x2": [4.29, 3.74, 1.65], "glb_ou25": [1.65, 2.06], "glb_ou35": [2.63, 1.38],
    },
    {
        "idx": 15, "day": "Bugün 19.11", "ko": "15:45", "id": "3307557", "mbs": 2, "extra": "+124",
        "league": "BAE - Arap Körfez Ligi", "home": "Al Wasl", "away": "Hatta SC",
        "nes": {"MS 1": None, "MS 0": 7.62, "MS 2": 11.60, "2.5 Alt": 3.19, "2.5 Üst": 1.08, "3.5 Alt": 1.86, "3.5 Üst": 1.44, "ÇŞ 02": 3.73, "KG Var": 1.57, "KG Yok": 1.67},
        "glb_src": "Flashscore Global", "glb_1x2": [1.09, 7.70, 15.00], "glb_ou25": [1.22, 3.50], "glb_ou35": [1.64, 2.08],
    },
    {
        "idx": 16, "day": "Bugün 19.11", "ko": "16:00", "id": "3386707", "mbs": 2, "extra": "+97",
        "league": "İran Pro Ligi", "home": "Malavan Bandar A.", "away": "GOL Gohar",
        "nes": {"MS 1": 2.36, "MS 0": 2.42, "MS 2": 2.52, "2.5 Alt": 1.15, "2.5 Üst": 2.77, "1.5 Alt": 1.78, "1.5 Üst": 1.49, "ÇŞ 10": 1.20, "ÇŞ 12": 1.22, "ÇŞ 02": 1.23, "KG Var": 2.18, "KG Yok": 1.29},
        "glb_src": "Flashscore Global", "glb_1x2": [2.62, 2.68, 2.75], "glb_ou25": [3.08, 1.28], "glb_ou35": [6.70, 1.05],
    },
    {
        "idx": 17, "day": "Bugün 19.11", "ko": "16:00", "id": "3307430", "mbs": 3, "extra": "+40",
        "league": "Özbekistan Süper Ligi", "home": "Surkhon Termez", "away": "Andijon",
        "nes": {"MS 1": 2.88, "MS 0": 2.87, "MS 2": 1.86, "2.5 Alt": 1.39, "2.5 Üst": 1.94, "ÇŞ 10": 1.39, "ÇŞ 12": 1.15, "ÇŞ 02": 1.14, "KG Var": 1.72, "KG Yok": 1.54},
        "glb_src": "Flashscore Global", "glb_1x2": [3.41, 3.26, 2.13], "glb_ou25": [2.25, 1.60], "glb_ou35": [4.02, 1.18],
    },
    {
        "idx": 18, "day": "Bugün 19.11", "ko": "16:00", "id": "3307410", "mbs": 3, "extra": "+40",
        "league": "Uganda Premier Ligi", "home": "Maroons", "away": "NEC",
        "nes": {"MS 1": 3.75, "MS 0": 2.71, "MS 2": 1.67, "2.5 Alt": 1.29, "2.5 Üst": 2.17, "ÇŞ 10": 1.53, "ÇŞ 12": 1.16, "KG Var": 1.92, "KG Yok": 1.41},
        "glb_src": "Flashscore Global", "glb_1x2": [4.39, 2.93, 1.85], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 19, "day": "Bugün 19.11", "ko": "16:00", "id": "3307513", "mbs": 3, "extra": "+40",
        "league": "Uganda Premier Ligi", "home": "Kigezi Homeoyz", "away": "Express",
        "nes": {"MS 1": 3.65, "MS 0": 2.96, "MS 2": 1.61, "2.5 Alt": 1.46, "2.5 Üst": 1.82, "ÇŞ 10": 1.58, "ÇŞ 12": 1.13, "ÇŞ 02": 1.06, "KG Var": 1.70, "KG Yok": 1.54},
        "glb_src": "Flashscore Global", "glb_1x2": [4.83, 3.34, 1.66], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 20, "day": "Bugün 19.11", "ko": "16:00", "id": "3307622", "mbs": 3, "extra": "+40",
        "league": "Uganda Premier Ligi", "home": "Gaddafi (Entebbe)", "away": "Kataka",
        "nes": {"MS 1": 1.07, "MS 0": 5.21, "MS 2": 9.67, "2.5 Alt": 2.00, "2.5 Üst": 1.36, "ÇŞ 02": 2.95, "KG Var": 1.87, "KG Yok": 1.43},
        "glb_src": "Flashscore Global", "glb_1x2": [1.15, 5.80, 13.00], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 21, "day": "Bugün 19.11", "ko": "16:00", "id": "3372578", "mbs": 3, "extra": "+19",
        "league": "Ürdün Kupası", "home": "AL Salt", "away": "Al Yarmouk",
        "nes": {"MS 1": 1.34, "MS 0": 3.42, "MS 2": 5.21, "2.5 Alt": 1.54, "2.5 Üst": 1.71, "ÇŞ 12": 1.07, "ÇŞ 02": 1.94, "KG Var": 1.80, "KG Yok": 1.47},
        "glb_src": "Flashscore Global", "glb_1x2": [1.50, 3.80, 6.26], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 22, "day": "Bugün 19.11", "ko": "16:00", "id": "3304917", "mbs": 3, "extra": "+19",
        "league": "Zambiya Süper Lig, Grup B", "home": "Nkwazi", "away": "Mutondo Stars",
        "nes": {"MS 1": 1.54, "MS 0": 2.67, "MS 2": 4.75, "1.5 Alt": 1.89, "1.5 Üst": 1.41, "ÇŞ 12": 1.16, "ÇŞ 02": 1.64, "KG Var": 2.26, "KG Yok": 1.27},
        "glb_src": "Flashscore Global", "glb_1x2": [1.68, 3.06, 5.36], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 23, "day": "Bugün 19.11", "ko": "16:00", "id": "3305105", "mbs": 3, "extra": "+19",
        "league": "Zambiya Süper Lig, Grup B", "home": "Zesco Utd", "away": "Red Arrows",
        "nes": {"MS 1": 1.81, "MS 0": 2.57, "MS 2": 3.40, "1.5 Alt": 1.87, "1.5 Üst": 1.43, "ÇŞ 10": 1.08, "ÇŞ 12": 1.19, "ÇŞ 02": 1.43, "KG Var": 2.15, "KG Yok": 1.30},
        "glb_src": "Flashscore Global", "glb_1x2": [2.03, 2.82, 3.82], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 24, "day": "Bugün 19.11", "ko": "16:00", "id": "3305281", "mbs": 3, "extra": "+19",
        "league": "Zambiya Süper Lig, Grup B", "home": "Mufulira Wanderers", "away": "Kabwe Warriors",
        "nes": {"MS 1": 2.63, "MS 0": 2.42, "MS 2": 2.26, "1.5 Alt": 1.88, "1.5 Üst": 1.42, "ÇŞ 10": 1.26, "ÇŞ 12": 1.22, "ÇŞ 02": 1.17, "KG Var": 2.05, "KG Yok": 1.34},
        "glb_src": "Flashscore Global", "glb_1x2": [2.93, 2.75, 2.47], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 25, "day": "Bugün 19.11", "ko": "18:00", "id": "3402559", "mbs": 3, "extra": "+40",
        "league": "Bulgaristan 2. Lig", "home": "Dobrudzha Dobrich", "away": "Fratria Varna",
        "nes": {"MS 1": 3.24, "MS 0": 3.46, "MS 2": 1.57, "2.5 Alt": 1.66, "2.5 Üst": 1.59, "ÇŞ 10": 1.61, "ÇŞ 12": 1.08, "ÇŞ 02": 1.09, "KG Var": 1.55, "KG Yok": 1.69},
        "glb_src": "Flashscore Global", "glb_1x2": [4.11, 3.52, 1.72], "glb_ou25": [1.81, 1.86], "glb_ou35": [2.97, 1.30],
    },
    {
        "idx": 26, "day": "Bugün 19.11", "ko": "18:00", "id": "3398361", "mbs": 3, "extra": "+40",
        "league": "Mısır Kupası", "home": "Al Mokawloon", "away": "Alqana",
        "nes": {"MS 1": 1.45, "MS 0": 3.18, "MS 2": 4.37, "2.5 Alt": 1.43, "2.5 Üst": 1.87, "ÇŞ 12": 1.09, "ÇŞ 02": 1.75, "KG Var": 1.85, "KG Yok": 1.45},
        "glb_src": "Flashscore Global", "glb_1x2": [1.62, 3.44, 4.98], "glb_ou25": [2.11, 1.62], "glb_ou35": [3.88, 1.18],
    },
    {
        "idx": 27, "day": "Bugün 19.11", "ko": "18:00", "id": "3398362", "mbs": 3, "extra": "+40",
        "league": "Mısır Kupası", "home": "Al Masry", "away": "Asyut Petroleum",
        "nes": {"MS 1": 1.56, "MS 0": 2.86, "MS 2": 4.09, "1.5 Alt": 2.13, "1.5 Üst": 1.31, "ÇŞ 12": 1.14, "ÇŞ 02": 1.62, "KG Var": 2.02, "KG Yok": 1.35},
        "glb_src": "Flashscore Global", "glb_1x2": [1.71, 3.20, 4.74], "glb_ou25": [2.33, 1.48], "glb_ou35": [4.45, 1.14],
    },
    {
        "idx": 28, "day": "Bugün 19.11", "ko": "18:25", "id": "3307658", "mbs": 2, "extra": "+124",
        "league": "BAE - Arap Körfez Ligi", "home": "AL Ain", "away": "AL Dhafra Scc",
        "nes": {"MS 1": None, "MS 0": 7.20, "MS 2": 11.50, "2.5 Alt": 2.76, "2.5 Üst": 1.15, "3.5 Alt": 1.66, "3.5 Üst": 1.59, "ÇŞ 02": 3.63, "KG Var": 1.69, "KG Yok": 1.56},
        "glb_src": "Flashscore Global", "glb_1x2": [1.09, 7.30, 14.70], "glb_ou25": [1.30, 2.97], "glb_ou35": [1.82, 1.85],
    },
    {
        "idx": 29, "day": "Bugün 19.11", "ko": "18:30", "id": "3343161", "mbs": 3, "extra": "+40",
        "league": "Irak Ligi", "home": "Al Garaf", "away": "AL Jawiya",
        "nes": {"MS 1": 3.31, "MS 0": 2.83, "MS 2": 1.74, "2.5 Alt": 1.39, "2.5 Üst": 1.94, "ÇŞ 10": 1.48, "ÇŞ 12": 1.15, "ÇŞ 02": 1.08, "KG Var": 1.75, "KG Yok": 1.51},
        "glb_src": "Flashscore Global", "glb_1x2": [3.55, 3.13, 1.97], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 30, "day": "Bugün 19.11", "ko": "18:30", "id": "3347002", "mbs": 2, "extra": "+124",
        "league": "Katar Yıldızlar Ligi", "home": "Al Ahli Doha", "away": "AL Shamal",
        "nes": {"MS 1": 2.78, "MS 0": 3.32, "MS 2": 1.74, "2.5 Alt": 2.26, "2.5 Üst": 1.27, "3.5 Alt": 1.46, "3.5 Üst": 1.82, "ÇŞ 10": 1.47, "ÇŞ 12": 1.09, "ÇŞ 02": 1.15, "KG Var": 1.25, "KG Yok": 2.32},
        "glb_src": "Flashscore Global", "glb_1x2": [2.98, 3.64, 2.02], "glb_ou25": [1.39, 2.59], "glb_ou35": [2.05, 1.66],
    },
    {
        "idx": 31, "day": "Bugün 19.11", "ko": "19:00", "id": "3343186", "mbs": 3, "extra": "+40",
        "league": "Irak Ligi", "home": "Gas Alshimal", "away": "AL Karkh",
        "nes": {"MS 1": 1.95, "MS 0": 2.74, "MS 2": 2.81, "2.5 Alt": 1.33, "2.5 Üst": 2.09, "ÇŞ 10": 1.15, "ÇŞ 12": 1.16, "ÇŞ 02": 1.37, "KG Var": 1.80, "KG Yok": 1.47},
        "glb_src": "Flashscore Global", "glb_1x2": [2.18, 3.00, 3.17], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 32, "day": "Bugün 19.11", "ko": "19:00", "id": "3372592", "mbs": 3, "extra": "+19",
        "league": "Ürdün Kupası", "home": "Al Jazeera", "away": "Hay AL Amir Hassan",
        "nes": {"MS 1": 1.15, "MS 0": 4.38, "MS 2": 7.53, "2.5 Alt": 1.94, "2.5 Üst": 1.39, "ÇŞ 02": 2.50, "KG Var": 1.71, "KG Yok": 1.54},
        "glb_src": "Flashscore Global", "glb_1x2": [1.31, 4.90, 8.15], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 33, "day": "Bugün 19.11", "ko": "19:45", "id": "3266482", "mbs": 3, "extra": "+97",
        "league": "Cezayir 1. Lig", "home": "MB Rouisset", "away": "CR Belouizdad",
        "nes": {"MS 1": 4.07, "MS 0": 2.59, "MS 2": 1.67, "2.5 Alt": 1.22, "2.5 Üst": 2.41, "1.5 Alt": 1.99, "1.5 Üst": 1.37, "ÇŞ 10": 1.54, "ÇŞ 12": 1.18, "KG Var": 2.09, "KG Yok": 1.33},
        "glb_src": "Flashscore Global", "glb_1x2": [4.80, 2.85, 1.83], "glb_ou25": [2.74, 1.35], "glb_ou35": [5.70, 1.08],
    },
    {
        "idx": 34, "day": "Bugün 19.11", "ko": "19:45", "id": "3266497", "mbs": 3, "extra": "+97",
        "league": "Cezayir 1. Lig", "home": "MC Alger", "away": "Olympique Akbou",
        "nes": {"MS 1": 1.22, "MS 0": 3.54, "MS 2": 7.60, "2.5 Alt": 1.41, "2.5 Üst": 1.92, "1.5 Alt": 2.44, "1.5 Üst": 1.21, "3.5 Alt": 1.06, "3.5 Üst": 3.49, "ÇŞ 02": 2.23, "KG Var": 2.26, "KG Yok": 1.27},
        "glb_src": "Flashscore Global", "glb_1x2": [1.37, 3.84, 8.60], "glb_ou25": [2.15, 1.60], "glb_ou35": [3.84, 1.18],
    },
    {
        "idx": 35, "day": "Bugün 19.11", "ko": "20:00", "id": "3406102", "mbs": 3, "extra": "+40",
        "league": "İsveç Allsvenskan Kad. Düş/Yük", "home": "KIF Orebro DFF (K)", "away": "Rosengard (K)",
        "nes": {"MS 1": 4.78, "MS 0": 3.83, "MS 2": 1.31, "2.5 Alt": 1.93, "2.5 Üst": 1.40, "ÇŞ 10": 2.00, "KG Var": 1.50, "KG Yok": 1.76},
        "glb_src": "Flashscore Global", "glb_1x2": [5.98, 4.30, 1.41], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 36, "day": "Bugün 19.11", "ko": "20:00", "id": "3406094", "mbs": 3, "extra": "+40",
        "league": "Litvanya 1.Lig , Düş./Yük. Playoff", "home": "Sveikata", "away": "Hegelmann Litauen B",
        "nes": {"MS 1": 2.15, "MS 0": 3.20, "MS 2": 2.19, "3.5 Alt": 1.35, "3.5 Üst": 2.03, "ÇŞ 10": 1.28, "ÇŞ 12": 1.10, "ÇŞ 02": 1.29, "KG Var": 1.29, "KG Yok": 2.17},
        "glb_src": "Flashscore Global", "glb_1x2": [2.45, 3.50, 2.47], "glb_ou25": [1.55, 2.30], "glb_ou35": [2.36, 1.52],
    },
    {
        "idx": 37, "day": "Bugün 19.11", "ko": "20:45", "id": "3307411", "mbs": 1, "extra": "+124",
        "league": "UEFA Şamp. Ligi Kadınlar", "home": "FK Austria Wien (K)", "away": "B. Münih (K)",
        "nes": {"MS 1": 17.35, "MS 0": 9.46, "MS 2": None, "2.5 Alt": 3.41, "2.5 Üst": 1.07, "3.5 Alt": 1.96, "3.5 Üst": 1.38, "ÇŞ 10": 4.71, "KG Var": 1.91, "KG Yok": 1.41},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [18.67, 8.92, 1.078], "glb_ou25": [1.24, 3.34], "glb_ou35": [1.70, 1.99],
    },
    {
        "idx": 38, "day": "Bugün 19.11", "ko": "20:45", "id": "3307697", "mbs": 1, "extra": "+124",
        "league": "UEFA Şamp. Ligi Kadınlar", "home": "Paris (K)", "away": "HB Koege (K)",
        "nes": {"MS 1": 1.39, "MS 0": 3.73, "MS 2": 4.09, "2.5 Alt": 2.16, "2.5 Üst": 1.30, "3.5 Alt": 1.41, "3.5 Üst": 1.93, "ÇŞ 02": 1.85, "KG Var": 1.36, "KG Yok": 2.00},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [1.67, 4.08, 4.38], "glb_ou25": [1.44, 2.43], "glb_ou35": [2.18, 1.58],
    },
    {
        "idx": 39, "day": "Bugün 19.11", "ko": "21:00", "id": "3408911", "mbs": 3, "extra": "+19",
        "league": "Arjantin Primera A Kapanış, Kadınlar", "home": "Ferro Carril (K)", "away": "CA River Plate (K)",
        "nes": {"MS 1": 1.95, "MS 0": 2.77, "MS 2": 2.78, "2.5 Alt": 1.47, "2.5 Üst": 1.81, "ÇŞ 10": 1.15, "ÇŞ 12": 1.15, "ÇŞ 02": 1.36, "KG Var": 1.60, "KG Yok": 1.64},
        "glb_src": "Flashscore Global", "glb_1x2": [2.16, 3.13, 3.07], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 40, "day": "Bugün 19.11", "ko": "21:00", "id": "3314224", "mbs": 3, "extra": "+245",
        "league": "Danimarka 1. Lig", "home": "Fredericia", "away": "Hilleroed",
        "nes": {"MS 1": 1.15, "MS 0": 4.76, "MS 2": 6.43, "2.5 Alt": 2.37, "2.5 Üst": 1.23, "1.5 Alt": 4.77, "3.5 Alt": 1.49, "3.5 Üst": 1.78, "ÇŞ 02": 2.48, "KG Var": 1.47, "KG Yok": 1.80},
        "glb_src": "Flashscore Global", "glb_1x2": [1.31, 5.30, 7.85], "glb_ou25": [1.38, 2.63], "glb_ou35": [2.05, 1.71],
    },
    {
        "idx": 41, "day": "Bugün 19.11", "ko": "21:00", "id": "3381559", "mbs": 3, "extra": "+19",
        "league": "İspanya Kupası, Kadınlar", "home": "RC Celta de Vigo (K)", "away": "RCD Espanyol (K)",
        "nes": {"MS 1": 6.69, "MS 0": 4.55, "MS 2": 1.15, "3.5 Alt": 1.45, "3.5 Üst": 1.85, "ÇŞ 10": 2.46, "KG Var": 1.51, "KG Yok": 1.75},
        "glb_src": "Flashscore Global", "glb_1x2": [7.70, 5.05, 1.28], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 42, "day": "Bugün 19.11", "ko": "21:00", "id": "3398367", "mbs": 3, "extra": "+40",
        "league": "Mısır Kupası", "home": "ZED", "away": "Smouha SC",
        "nes": {"MS 1": 2.21, "MS 0": 2.26, "MS 2": 2.93, "1.5 Alt": 2.04, "1.5 Üst": 1.34, "ÇŞ 10": 1.13, "ÇŞ 12": 1.26, "ÇŞ 02": 1.27, "KG Var": 1.87, "KG Yok": 1.43},
        "glb_src": "Flashscore Global", "glb_1x2": [2.32, 2.88, 3.03], "glb_ou25": [2.56, 1.40], "glb_ou35": [5.30, 1.09],
    },
    {
        "idx": 43, "day": "Bugün 19.11", "ko": "22:00", "id": "3266477", "mbs": 3, "extra": "+97",
        "league": "Cezayir 1. Lig", "home": "JS Kabylie", "away": "USM Alger",
        "nes": {"MS 1": 1.93, "MS 0": 2.45, "MS 2": 3.24, "2.5 Alt": 1.28, "2.5 Üst": 2.24, "1.5 Alt": 2.15, "1.5 Üst": 1.30, "ÇŞ 10": 1.09, "ÇŞ 12": 1.21, "ÇŞ 02": 1.37, "KG Var": 1.85, "KG Yok": 1.44},
        "glb_src": "Flashscore Global", "glb_1x2": [2.11, 2.76, 3.71], "glb_ou25": [2.52, 1.41], "glb_ou35": [5.00, 1.11],
    },
    {
        "idx": 44, "day": "Bugün 19.11", "ko": "22:30", "id": "3406921", "mbs": 3, "extra": "+12",
        "league": "Uruguay Prmr Ligi, Kapanış", "home": "CA Progreso", "away": "Torque",
        "nes": {"MS 1": 5.47, "MS 0": 3.96, "MS 2": 1.25, "2.5 Alt": 1.96, "2.5 Üst": 1.38, "KG Var": 1.54, "KG Yok": 1.71},
        "glb_src": "Flashscore Global", "glb_1x2": [6.11, 4.30, 1.41], "glb_ou25": [1.56, 2.22], "glb_ou35": [2.35, 1.47],
    },
    {
        "idx": 45, "day": "Bugün 19.11", "ko": "22:30", "id": "3406922", "mbs": 3, "extra": "+12",
        "league": "Uruguay Prmr Ligi, Kapanış", "home": "Penarol", "away": "Cerro Largo",
        "nes": {"MS 1": 1.27, "MS 0": 3.63, "MS 2": 5.99, "2.5 Alt": 1.52, "2.5 Üst": 1.74, "KG Var": 1.93, "KG Yok": 1.40},
        "glb_src": "Flashscore Global", "glb_1x2": [1.39, 4.05, 7.15], "glb_ou25": [1.94, 1.74], "glb_ou35": [3.28, 1.25],
    },
    {
        "idx": 46, "day": "Bugün 19.11", "ko": "22:30", "id": "3406925", "mbs": 3, "extra": "+12",
        "league": "Uruguay Prmr Ligi, Kapanış", "home": "Boston River", "away": "D. Maldonado",
        "nes": {"MS 1": 3.57, "MS 0": 3.14, "MS 2": 1.58, "2.5 Alt": 1.65, "2.5 Üst": 1.60, "KG Var": 1.54, "KG Yok": 1.71},
        "glb_src": "Flashscore Global", "glb_1x2": [3.99, 3.52, 1.75], "glb_ou25": [1.81, 1.86], "glb_ou35": [2.97, 1.30],
    },
    {
        "idx": 47, "day": "Bugün 19.11", "ko": "22:45", "id": "3307710", "mbs": 3, "extra": "+245",
        "league": "Fransa Ulusal Lig", "home": "Amiens", "away": "Caen",
        "nes": {"MS 1": 1.95, "MS 0": 2.89, "MS 2": 2.67, "2.5 Alt": 1.59, "2.5 Üst": 1.66, "1.5 Alt": 2.93, "1.5 Üst": 1.12, "3.5 Alt": 1.15, "3.5 Üst": 2.79, "ÇŞ 10": 1.17, "ÇŞ 12": 1.14, "ÇŞ 02": 1.37, "KG Var": 1.51, "KG Yok": 1.75},
        "glb_src": "Flashscore Global", "glb_1x2": [2.18, 3.08, 3.10], "glb_ou25": [1.88, 1.79], "glb_ou35": [3.14, 1.27],
    },
    {
        "idx": 48, "day": "Bugün 19.11", "ko": "23:00", "id": "3307516", "mbs": 1, "extra": "+118",
        "league": "UEFA Şamp. Ligi Kadınlar", "home": "Arsenal (K)", "away": "O. Lyon (K)",
        "nes": {"MS 1": 3.65, "MS 0": 3.50, "MS 2": 1.48, "2.5 Alt": 1.98, "2.5 Üst": 1.38, "1.5 Alt": 3.88, "3.5 Alt": 1.32, "3.5 Üst": 2.11, "ÇŞ 10": 1.71, "ÇŞ 12": 1.07, "ÇŞ 02": 1.06, "KG Var": 1.40, "KG Yok": 1.93},
        "glb_src": "Pinnacle (1X2) + Flashscore/Sofascore (O/U)", "glb_1x2": [3.77, 3.59, 1.892], "glb_ou25": [1.52, 2.24], "glb_ou35": [2.36, 1.50],
    },
    {
        "idx": 49, "day": "Bugün 19.11", "ko": "23:00", "id": "3307525", "mbs": 1, "extra": "+32",
        "league": "UEFA Şamp. Ligi Kadınlar", "home": "Barcelona (K)", "away": "Servette (K)",
        "nes": {"MS 1": None, "MS 0": 15.05, "MS 2": 17.35},
        "glb_src": "Flashscore Global + ESPN", "glb_1x2": [1.03, 26.00, 32.00], "glb_ou25": [1.03, 12.50], "glb_ou35": [1.08, 6.20],
    },
    {
        "idx": 50, "day": "Bugün 19.11", "ko": "23:00", "id": "3307686", "mbs": 1, "extra": "+124",
        "league": "UEFA Şamp. Ligi Kadınlar", "home": "Benfica (K)", "away": "AS Roma (K)",
        "nes": {"MS 1": 1.81, "MS 0": 3.33, "MS 2": 2.62, "2.5 Alt": 2.12, "2.5 Üst": 1.31, "3.5 Alt": 1.39, "3.5 Üst": 1.95, "ÇŞ 10": 1.17, "ÇŞ 12": 1.09, "ÇŞ 02": 1.43, "KG Var": 1.28, "KG Yok": 2.19},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [2.10, 3.93, 2.93], "glb_ou25": [1.47, 2.35], "glb_ou35": [2.24, 1.55],
    },
    # --- PART 2: YARIN GECE 20.11.2026 (01:30 - 03:45 TSİ, 9 MAÇ) ---
    {
        "idx": 51, "day": "Gece 20.11", "ko": "01:30", "id": "3304862", "mbs": 1, "extra": "+409",
        "league": "Brezilya Serie A", "home": "Vitoria BA", "away": "Bragantino",
        "nes": {"MS 1": 2.36, "MS 0": 3.07, "MS 2": 2.28, "2.5 Alt": 1.78, "2.5 Üst": 1.60, "1.5 Alt": 3.55, "1.5 Üst": 1.10, "3.5 Alt": 1.23, "3.5 Üst": 2.65, "ÇŞ 10": 1.33, "ÇŞ 12": 1.17, "ÇŞ 02": 1.30, "KG Var": 1.47, "KG Yok": 1.98},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [2.81, 3.42, 2.52], "glb_ou25": [1.83, 2.02], "glb_ou35": [2.89, 1.40],
    },
    {
        "idx": 52, "day": "Gece 20.11", "ko": "01:30", "id": "3305120", "mbs": 1, "extra": "+421",
        "league": "Brezilya Serie A", "home": "Vasco Da G.", "away": "Internacional",
        "nes": {"MS 1": 1.47, "MS 0": 3.58, "MS 2": 4.41, "2.5 Alt": 1.82, "2.5 Üst": 1.56, "1.5 Alt": 3.63, "1.5 Üst": 1.09, "3.5 Alt": 1.25, "3.5 Üst": 2.59, "ÇŞ 12": 1.11, "ÇŞ 02": 1.93, "KG Var": 1.59, "KG Yok": 1.79},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [1.69, 4.00, 4.83], "glb_ou25": [1.83, 2.02], "glb_ou35": [2.94, 1.38],
    },
    {
        "idx": 53, "day": "Gece 20.11", "ko": "01:30", "id": "3361180", "mbs": 3, "extra": "+40",
        "league": "Kolombiya Prmr B Kapanış, Yük. Gr A", "home": "U. Magdalena", "away": "Boca Juniors (Kol)",
        "nes": {"MS 1": 1.34, "MS 0": 3.35, "MS 2": 5.24, "2.5 Alt": 1.56, "2.5 Üst": 1.69, "ÇŞ 12": 1.08, "ÇŞ 02": 1.93, "KG Var": 1.77, "KG Yok": 1.50},
        "glb_src": "Flashscore Global", "glb_1x2": [1.51, 3.68, 5.81], "glb_ou25": [1.89, 1.78], "glb_ou35": [3.20, 1.26],
    },
    {
        "idx": 54, "day": "Gece 20.11", "ko": "01:30", "id": "3361195", "mbs": 3, "extra": "+40",
        "league": "Kolombiya Prmr B Kapanış, Yük. Gr A", "home": "Independiente Yumbo", "away": "Envigado",
        "nes": {"MS 1": 2.37, "MS 0": 2.53, "MS 2": 2.40, "2.5 Alt": 1.30, "2.5 Üst": 2.15, "ÇŞ 10": 1.22, "ÇŞ 12": 1.20, "ÇŞ 02": 1.23, "KG Var": 1.78, "KG Yok": 1.48},
        "glb_src": "Flashscore Global", "glb_1x2": [2.62, 2.78, 2.65], "glb_ou25": [2.41, 1.48], "glb_ou35": [4.50, 1.13],
    },
    {
        "idx": 55, "day": "Gece 20.11", "ko": "01:30", "id": "3355406", "mbs": 3, "extra": "+3",
        "league": "Venezuela Kupası, Eleme Turu", "home": "Dep. La Gua.", "away": "Academia Anzoategui",
        "nes": {"MS 1": 1.17, "MS 0": 4.18, "MS 2": 7.01},
        "glb_src": "Flashscore Global", "glb_1x2": [1.31, 4.60, 8.00], "glb_ou25": None, "glb_ou35": None,
    },
    {
        "idx": 56, "day": "Gece 20.11", "ko": "03:30", "id": "3305027", "mbs": 1, "extra": "+415",
        "league": "Brezilya Serie A", "home": "Sao Paulo SP", "away": "Fluminense",
        "nes": {"MS 1": 2.15, "MS 0": 2.86, "MS 2": 2.68, "2.5 Alt": 1.53, "2.5 Üst": 1.88, "1.5 Alt": 2.84, "1.5 Üst": 1.20, "3.5 Alt": 1.12, "3.5 Üst": 3.39, "ÇŞ 10": 1.23, "ÇŞ 12": 1.20, "ÇŞ 02": 1.38, "KG Var": 1.65, "KG Yok": 1.72},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [2.40, 3.28, 3.09], "glb_ou25": [2.15, 1.74], "glb_ou35": [3.72, 1.26],
    },
    {
        "idx": 57, "day": "Gece 20.11", "ko": "03:30", "id": "3386737", "mbs": 1, "extra": "+372",
        "league": "ABD Major Lig Playoff", "home": "Orlando City", "away": "Cincinnati",
        "nes": {"MS 1": 2.15, "MS 0": 3.64, "MS 2": 2.24, "2.5 Alt": 3.21, "2.5 Üst": 1.15, "1.5 Alt": 7.18, "3.5 Alt": 1.81, "3.5 Üst": 1.57, "ÇŞ 10": 1.34, "ÇŞ 12": 1.11, "ÇŞ 02": 1.38, "KG Var": 1.16, "KG Yok": 3.07},
        "glb_src": "Pinnacle (1X2) + Flashscore (O/U)", "glb_1x2": [2.52, 4.00, 2.55], "glb_ou25": [1.29, 3.41], "glb_ou35": [1.80, 2.11],
    },
    {
        "idx": 58, "day": "Gece 20.11", "ko": "03:45", "id": "3408920", "mbs": 3, "extra": "+40",
        "league": "Kolombiya Prmr B Kapanış, Yük. Gr B", "home": "R. Cartagena", "away": "Tigres (Kol)",
        "nes": {"MS 1": 1.16, "MS 0": 4.03, "MS 2": 7.84, "2.5 Alt": 1.63, "2.5 Üst": 1.61, "ÇŞ 02": 2.42, "KG Var": 1.99, "KG Yok": 1.37},
        "glb_src": "Flashscore Global", "glb_1x2": [1.32, 4.33, 8.45], "glb_ou25": [1.80, 1.87], "glb_ou35": [2.92, 1.31],
    },
    {
        "idx": 59, "day": "Gece 20.11", "ko": "03:45", "id": "3408921", "mbs": 3, "extra": "+40",
        "league": "Kolombiya Prmr B Kapanış, Yük. Gr B", "home": "R. S. Cundinamarca", "away": "Deportes Quindio",
        "nes": {"MS 1": 2.67, "MS 0": 2.51, "MS 2": 2.17, "2.5 Alt": 1.32, "2.5 Üst": 2.11, "ÇŞ 10": 1.28, "ÇŞ 12": 1.21, "ÇŞ 02": 1.17, "KG Var": 1.75, "KG Yok": 1.51},
        "glb_src": "Flashscore Global", "glb_1x2": [3.05, 2.79, 2.38], "glb_ou25": [2.44, 1.47], "glb_ou35": [4.65, 1.12],
    },
]


def _load_espn_l5() -> dict[int, dict]:
    """Load matched ESPN L5 stats (gf, ga, wdl) by Nesine match idx where available."""
    espn_path = Path(r"C:\Users\pc\.gemini\antigravity\brain\fd718395-2b56-447a-8788-984e92dfbffb\scratch\espn_nov19_global.json")
    if not espn_path.exists():
        return {}
    raw = json.loads(espn_path.read_text(encoding="utf-8"))
    by_eid = {e["id"]: e for e in raw}
    mapping = {
        37: "401916978",  # Austria Vienna W - Bayern W
        38: "401916977",  # Paris FC W - HB Koge W
        41: "401928542",  # Celta Vigo W - Espanyol W
        48: "401916976",  # Arsenal W - OL Lyonnes W
        49: "401916975",  # Barcelona W - Servette W
        50: "401916974",  # Benfica W - AS Roma W
        51: "401841317",  # Vitoria BA - Bragantino
        52: "401841308",  # Vasco da Gama - Internacional
        56: "401841309",  # Sao Paulo - Fluminense
        57: "401933535",  # Orlando City - Cincinnati
    }
    out = {}
    for idx, eid in mapping.items():
        if eid in by_eid:
            out[idx] = by_eid[eid]
    return out


ESPN_L5_BY_IDX = _load_espn_l5()


def analyze_match(m: dict) -> dict:
    slug, league_prior_tot, is_ko = _league_slug_and_prior(m["league"])
    com_nu, alpha_nb, shared_kappa = league_tail_regime(slug)

    # 1. PURE GLOBAL PROBABILITY EXTRACTION (zero Nesine contamination!)
    g_1x2 = m["glb_1x2"]
    g_over25 = m["glb_ou25"]
    g_over35 = m["glb_ou35"]

    res_1x2 = devig(g_1x2, method="power")
    p_1x2 = res_1x2.probabilities
    glb_vig_1x2 = book_overround(g_1x2)

    ou_line = None
    p_over = None
    p_glb_o25 = float(devig(g_over25, method="power").probabilities[0]) if g_over25 is not None else None
    p_glb_o35 = float(devig(g_over35, method="power").probabilities[0]) if g_over35 is not None else None

    # Use 3.5 whenever 2.5 is skewed below 1.32 AND 3.5 line exists (gives exact tail fit on both 2.5 & 3.5!)
    if g_over35 is not None and (g_over25 is None or min(g_over25) < 1.32):
        ou_line = 3.5
        p_over = p_glb_o35
    elif g_over25 is not None:
        ou_line = 2.5
        p_over = p_glb_o25

    # Estimate seed rates cleanly from Global p_1x2 and league prior total
    seed_h = max(0.25, league_prior_tot * (p_1x2[0] + 0.5 * p_1x2[1]))
    seed_a = max(0.25, league_prior_tot * (p_1x2[2] + 0.5 * p_1x2[1]))

    # Note: Barcelona W - Servette W (1.03, O/U 6.5 on DraftKings 1.71/2.05) -> handle extreme 6.5 cap
    if "Barcelona (K)" in m["home"]:
        mu_h, mu_a = 6.20, 0.25
    else:
        mu_h, mu_a, _ = fit_tail_rates_from_markets(
            p_1x2=p_1x2,
            ou_line=ou_line,
            p_over=p_over,
            seed_rates=(seed_h, seed_a),
            alpha_nb=alpha_nb,
            shared_kappa=shared_kappa,
            fund_weight=0.04 if ou_line is not None else 0.14,
        )

    # ESPN L5 verification note & tactical adjustments
    espn_entry = ESPN_L5_BY_IDX.get(m["idx"])
    l5_note = None
    if espn_entry and espn_entry.get("l5"):
        parts = []
        for tname, st in espn_entry["l5"].items():
            if st["n"] > 0:
                parts.append(f"{tname} ({st['wdl']}, {st['gf']}-{st['ga']})")
        if parts:
            l5_note = " | ".join(parts)

    # 2. Tactical & Post-Mortem Risk Context
    h_dead = mu_h < 0.62
    a_dead = mu_a < 0.62
    if m["idx"] == 51:  # Vitoria BA L5: 0G-2B-3M, 3 GF / 9 GA -> cold attack warning
        h_dead = True
    risk_ctx = MatchRiskContext(
        home_must_win=is_ko and (mu_h > mu_a + 0.35),
        away_must_win=is_ko and (mu_a > mu_h + 0.35),
        home_dead_attack=h_dead,
        away_dead_attack=a_dead,
        group_id=m["id"],
        notes=f"Global ({m['glb_src']}) | Vig: %{glb_vig_1x2*100:.1f} | MBS {m['mbs']}",
    )

    bundle = compute_omni_markets(mu_h, mu_a, league=slug)
    blocked, penalties = audit_match_risks(bundle, risk_ctx)

    # Additional global post-mortem risk guards:
    # Block ÇŞ 12 when Global Draw probability >= 27.5% (or KO >= 25%) -> protects against 0-0 / 1-1 trap!
    p_draw = float(p_1x2[1])
    if p_draw >= 0.275 or (is_ko and p_draw >= 0.25):
        blocked["ÇŞ 12"] = f"Yuksek Beraberlik Riski (Global P(X)=%{p_draw*100:.1f})"
    # Caution on Bayern W defense (9 GA in L5) vs Austria Wien W (7 GF in L5)
    if m["idx"] == 37:
        penalties["KG Yok"] = min(penalties.get("KG Yok", 1.0), 0.90)
    # Caution on OL Lyonnes W (only 3 GA in L5) for KG Var
    if m["idx"] == 48:
        penalties["KG Var"] = min(penalties.get("KG Var", 1.0), 0.90)

    # Check Nesine main-grid vig for comparison
    nes = m["nes"]
    nes_1x2_vig = None
    if nes.get("MS 1") and nes.get("MS 0") and nes.get("MS 2"):
        nes_1x2_vig = book_overround([nes["MS 1"], nes["MS 0"], nes["MS 2"]])

    all_probs = bundle.all_probabilities()
    nesine_market_audit = []
    for sel, n_odd in nes.items():
        if n_odd is None or sel not in all_probs:
            continue
        p_g = float(all_probs[sel])
        # Use direct devigged Global probability if it's MS 1/0/2, ÇŞ, or O/U 2.5/3.5 directly quoted on Flashscore/Pinnacle!
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
        elif sel in ("2.5 Üst", "2.5 Alt") and p_glb_o25 is not None:
            p_g = float(p_glb_o25 if sel == "2.5 Üst" else 1.0 - p_glb_o25)
        elif sel in ("3.5 Üst", "3.5 Alt") and p_glb_o35 is not None:
            p_g = float(p_glb_o35 if sel == "3.5 Üst" else 1.0 - p_glb_o35)

        fair_g = round(1.0 / max(p_g, 1e-6), 2)
        nes_ev = round(p_g * float(n_odd) - 1.0, 4)
        payout_ratio = round(float(n_odd) / max(fair_g, 1e-4), 4)
        is_blocked = sel in blocked
        nesine_market_audit.append({
            "selection": sel,
            "nesine_odds": float(n_odd),
            "global_prob": round(p_g, 4),
            "global_fair_odds": fair_g,
            "nesine_ev": nes_ev,
            "payout_ratio": payout_ratio,
            "blocked": is_blocked,
            "block_reason": blocked.get(sel),
        })

    valid_nesine = [
        x for x in nesine_market_audit
        if (not x["blocked"]) and x["nesine_odds"] >= MIN_ALLOWED_ODDS and x["global_prob"] >= 0.50
    ]

    def _rank_score(x: dict) -> float:
        pen = penalties.get(x["selection"], 1.0)
        ev_adj = max(0.55, min(1.22, 1.0 + 0.85 * x["nesine_ev"]))
        return (x["global_prob"] ** 1.30) * pen * ev_adj

    valid_nesine.sort(key=_rank_score, reverse=True)

    # Omni-market top special picks (1Y/2Y KG, Gol Aralığı, İY/MS) from Global bundle
    all_probs_dict = bundle.all_probabilities()
    best_htft = max(bundle.ht_ft.items(), key=lambda kv: kv[1])
    best_band = max(bundle.goal_bands.items(), key=lambda kv: kv[1])
    btts_h1_yes = bundle.btts.get("1. Yarı KG Var", 0.0)
    btts_h2_yes = bundle.btts.get("2. Yarı KG Var", 0.0)
    btts_both = bundle.btts.get("1Y ve 2Y KG Var", 0.0)
    recs_all = select_best_valid_bet(
        m["id"], m["home"], m["away"], m["league"], f"{m['day']} {m['ko']}",
        bundle, offered_odds_map={k: v for k, v in nes.items() if v is not None},
        risk_ctx=risk_ctx, min_prob=0.52,
    )

    return {
        "idx": m["idx"],
        "day": m["day"],
        "ko": m["ko"],
        "id": m["id"],
        "mbs": m["mbs"],
        "extra": m["extra"],
        "league": m["league"],
        "slug": slug,
        "is_knockout": is_ko,
        "home": m["home"],
        "away": m["away"],
        "glb_src": m["glb_src"],
        "glb_1x2": g_1x2,
        "glb_ou25": g_over25,
        "glb_ou35": g_over35,
        "glb_vig_1x2": round(glb_vig_1x2, 4),
        "nes_vig_1x2": round(nes_1x2_vig, 4) if nes_1x2_vig is not None else None,
        "has_global_ou": g_over25 is not None or g_over35 is not None,
        "l5_note": l5_note,
        "mu_home": bundle.mu_home,
        "mu_away": bundle.mu_away,
        "expected_total": bundle.expected_total,
        "exp_1h_total": bundle.exp_1h_total,
        "exp_2h_total": bundle.exp_2h_total,
        "ft_1x2": {"1": round(float(p_1x2[0]), 4), "0": round(float(p_1x2[1]), 4), "2": round(float(p_1x2[2]), 4)},
        "ht_1x2": bundle.ht_1x2,
        "ht_ft": bundle.ht_ft,
        "goal_bands": bundle.goal_bands,
        "ft_ou": bundle.ft_ou,
        "ht_ou": bundle.ht_ou,
        "h2_ou": bundle.h2_ou,
        "btts": bundle.btts,
        "special_summary": {
            "best_ht_ft": {"sel": best_htft[0], "prob": round(best_htft[1], 4), "fair_odds": round(1.0 / max(best_htft[1], 1e-6), 2)},
            "best_band": {"sel": best_band[0], "prob": round(best_band[1], 4), "fair_odds": round(1.0 / max(best_band[1], 1e-6), 2)},
            "1Y_KG_Var": round(btts_h1_yes, 4),
            "2Y_KG_Var": round(btts_h2_yes, 4),
            "Her_2_Yari_KG": round(btts_both, 4),
            "6_plus_gol": round(bundle.goal_bands.get("+6 Gol", 0.0), 4),
        },
        "top_ft_scores": bundle.top_ft_scores[:3],
        "top3_cluster": bundle.top3_score_cluster,
        "score_entropy": bundle.score_entropy,
        "blocked_traps": blocked,
        "best_nesine_bet": valid_nesine[0] if valid_nesine else None,
        "alt_nesine_bets": valid_nesine[1:4],
        "best_omni_bet": {
            "selection": recs_all[0].selection,
            "odds": recs_all[0].offered_odds,
            "prob": recs_all[0].probability,
            "estimated": recs_all[0].odds_is_estimated,
        } if recs_all else None,
        "all_nesine_audit": sorted(nesine_market_audit, key=lambda x: x["nesine_ev"], reverse=True),
    }


def _pick_leg(by_idx: dict[int, dict], idx: int, sel: str, note: str, category: str) -> dict:
    """Resolve an exact verified Nesine selection from analyzed match results with strict validation."""
    r = by_idx[idx]
    match_aud = next((a for a in r["all_nesine_audit"] if a["selection"] == sel), None)
    if match_aud is None:
        raise ValueError(f"Selection {sel!r} missing in Nesine audit for match #{idx} {r['home']}")
    if match_aud["nesine_odds"] < MIN_ALLOWED_ODDS:
        raise ValueError(f"Selection {sel!r} odds {match_aud['nesine_odds']} < {MIN_ALLOWED_ODDS} on #{idx}")
    if match_aud["blocked"]:
        raise ValueError(f"Selection {sel!r} blocked on #{idx}: {match_aud['block_reason']}")

    return {
        "idx": r["idx"],
        "event_id": r["id"],
        "ko_tsi": f"{r['day']} {r['ko']}",
        "league": r["league"],
        "home": r["home"],
        "away": r["away"],
        "mbs": r["mbs"],
        "selection": sel,
        "category": category,
        "odds": float(match_aud["nesine_odds"]),
        "prob": float(match_aud["global_prob"]),
        "fair_odds": float(match_aud["global_fair_odds"]),
        "nesine_ev": float(match_aud["nesine_ev"]),
        "odds_source": f"Canlı Nesine 19.11 vs {r['glb_src']}",
        "xg_summary": f"{r['mu_home']:.2f}-{r['mu_away']:.2f} (1Y {r['exp_1h_total']:.2f} / 2Y {r['exp_2h_total']:.2f})",
        "top_scores": [s["score"] for s in r["top_ft_scores"][:3]],
        "note": note,
        "result": "BEKLİYOR",
    }


def _build_verified_coupon(
    coupon_id: str,
    title: str,
    tier: str,
    stake_pct: str,
    system_note: str,
    legs: list[dict],
) -> dict:
    """Validate MBS & odds >= 1.20 constraints and assemble structured coupon payload."""
    max_mbs = max(l["mbs"] for l in legs)
    if len(legs) < max_mbs:
        raise ValueError(f"Coupon {coupon_id} violates MBS: legs={len(legs)} < max_mbs={max_mbs}")
    total_odds = round(math.prod(l["odds"] for l in legs), 2)
    joint_prob = round(math.prod(l["prob"] for l in legs), 4)
    avg_prob = round(sum(l["prob"] for l in legs) / len(legs), 4)
    avg_ev = round(sum(l["nesine_ev"] for l in legs) / len(legs), 4)
    return {
        "coupon_id": coupon_id,
        "date": "2026-11-19",
        "title": title,
        "tier": tier,
        "recommended_stake_pct": stake_pct,
        "system_note": system_note,
        "leg_count": len(legs),
        "max_mbs": max_mbs,
        "total_odds": total_odds,
        "joint_probability": joint_prob,
        "average_leg_probability": avg_prob,
        "average_nesine_ev": avg_ev,
        "status": "PENDING",
        "legs": legs,
    }


def _format_special_top_lists(results: list[dict]) -> dict[str, list[dict]]:
    """Rank top special-market global signals across all 59 matches."""
    # High-goal 6+ & 3.5+ candidates
    hi_goal = sorted(
        [r for r in results if r["has_global_ou"]],
        key=lambda r: r["expected_total"],
        reverse=True,
    )[:6]
    # 1Y / 2Y KG candidates
    btts_halves = sorted(
        [r for r in results if r["has_global_ou"]],
        key=lambda r: r["special_summary"]["Her_2_Yari_KG"],
        reverse=True,
    )[:6]
    # 1/2 or 2/1 turnaround or 0/1 - 0/2 HT/FT draws-to-win
    ht_draw_ft_win = []
    for r in results:
        if not r["has_global_ou"]:
            continue
        p01 = r["ht_ft"].get("0/1", 0.0)
        p02 = r["ht_ft"].get("0/2", 0.0)
        best_0x = ("0/1", p01) if p01 >= p02 else ("0/2", p02)
        if best_0x[1] >= 0.22:
            ht_draw_ft_win.append((best_0x[1], best_0x[0], r))
    ht_draw_ft_win.sort(key=lambda x: x[0], reverse=True)
    # Tightest Top-3 exact score clusters
    top_scores = sorted(
        [r for r in results if r["has_global_ou"]],
        key=lambda r: r["top3_cluster"]["prob"],
        reverse=True,
    )[:6]
    return {
        "high_total": hi_goal,
        "btts_halves": btts_halves,
        "ht0_ft_win": [{"prob": p, "sel": sel, "r": r} for p, sel, r in ht_draw_ft_win[:6]],
        "top_clusters": top_scores,
    }


def _write_markdown_reports(results: list[dict], coupons: list[dict], specials: dict[str, list[dict]]) -> None:
    """Persist full 59-match analysis & coupon ledger in UTF-8 Markdown + Ledger INDEX + Artifact."""
    with_ou = sum(1 for r in results if r["has_global_ou"])
    ou_only = len(results) - with_ou
    nes_vigs = [r["nes_vig_1x2"] for r in results if r["nes_vig_1x2"] is not None]
    glb_vigs = [r["glb_vig_1x2"] for r in results]
    avg_nes_vig = (sum(nes_vigs) / len(nes_vigs)) * 100.0 if nes_vigs else 0.0
    avg_glb_vig = (sum(glb_vigs) / len(glb_vigs)) * 100.0 if glb_vigs else 0.0

    lines: list[str] = [
        "# 19 Kasım 2026 Nesine Tam Bülten — Global Sharp Benchmark (Pinnacle / Flashscore Global / ESPN L5) Omni-Analiz Raporu",
        "",
        f"**Tarih:** 19 Kasım 2026 Perşembe (19.11 `11:30–23:00` + 20.11 Gece `01:30–03:45` TSİ)  ",
        "**Motor:** `QuantFoot-v6.1 (Global-First Power Devig + Bivariate COM-Poisson/NegBin Tail Calibration + 5-Katmanlı Risk Kalkanı)`  ",
        f"**Kapsam:** Nesine'deki tüm **{len(results)} maç** (`{with_ou}` maç tam Global `1X2 + O/U 2.5 & 3.5` verili, `{ou_only}` maç Global `1X2 + Lig Gol Önseli`)  ",
        f"**Ortalama Karşılaştırmalı Marjin (Vig):** Global Sharp **`%{avg_glb_vig:.1f}`** vs Nesine **`%{avg_nes_vig:.1f}`**  ",
        "",
        "> **Metodoloji Kuralı:** Tüm kazanma olasılıkları ve adil oranlar **asla Nesine oranlarından türetilmemiştir**. Olasılıklar Tier-1 **Pinnacle** (UWCL, Brezilya Série A, ABD MLS) ve Tier-2 **Flashscore Global (bookmakerId=417)** keskin oranlarının güç yöntemiyle (*power devig*) marjinden arındırılmasıyla elde edilmiş; **Sofascore (`providerId=1`)** ve **ESPN L5** form kayıtlarıyla çapraz doğrulanmıştır. Sonrasında bu küresel olasılıklar **canlı Nesine oranlarıyla** karşılaştırılarak gizli Nesine komisyon vergisi (*EV*) ortaya çıkarılmıştır.",
        "",
        "---",
        "",
        "## 1. En Düşük Vergili & +EV Nesine Değer Radarı (Global Adil Orana Göre)",
        "",
        "| # | Saat | Maç (Lig) | MBS | Global Doğrulama | Tercih | Nesine | Global Adil | Global % | EV | Durum / Not |",
        "| :---: | :---: | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    ev_rows = []
    for r in results:
        for aud in r["all_nesine_audit"]:
            if not aud["blocked"] and aud["nesine_odds"] >= 1.20 and aud["global_prob"] >= 0.52:
                ev_rows.append((aud["nesine_ev"], aud["global_prob"], r, aud))
    ev_rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for ev, gp, r, aud in ev_rows[:18]:
        tag = "Tam 1X2+O/U" if r["has_global_ou"] else "Sadece 1X2*"
        note_str = "Sıfır vergi / +EV" if ev >= -0.02 else ("Makul marj" if ev >= -0.13 else "Standart vergi")
        if r["idx"] == 37:
            note_str += " (Dikkat: Bayern L5 9 GA)"
        elif r["is_knockout"]:
            note_str += " (Kupa 90')"
        lines.append(
            f"| {r['idx']} | {r['day']} {r['ko']} | {r['home']} - {r['away']} ({r['league']}) | {r['mbs']} | {tag} | "
            f"**{aud['selection']}** | **{aud['nesine_odds']:.2f}** | {aud['global_fair_odds']:.2f} | %{gp*100:.1f} | **{ev*100:+.1f}%** | {note_str} |"
        )

    lines.extend([
        "",
        "*Not: `Sadece 1X2*` işaretli maçlarda Flashscore üzerinde küresel Alt/Üst kotasyonu açık olmadığından gol beklentisi lig önselinden türetilmiştir; bu nedenle ana güven kuponlarına yalnızca `Tam 1X2+O/U` maçları dahil edilmiştir.*",
        "",
        "---",
        "",
        "## 2. Günün 59 Maçlık Tam Global Omni-Market Tablosu",
        "",
    ])

    groups = [
        ("Avustralya, Japonya & ASEAN (11:30 - 15:30 TSİ)", lambda r: r["idx"] in (1, 2, 3, 4, 5, 7)),
        ("Mısır, Körfez (BAE/Katar/İran/Irak), Afrika & Ürdün (15:30 - 21:00 TSİ)", lambda r: r["idx"] in (8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33, 34, 42, 43)),
        ("Avrupa Kupaları, Playofflar & Ligler (15:00 - 22:45 TSİ)", lambda r: r["idx"] in (6, 13, 14, 25, 35, 36, 40, 41, 47)),
        ("UEFA Kadınlar Şampiyonlar Ligi (20:45 - 23:00 TSİ)", lambda r: r["idx"] in (37, 38, 48, 49, 50)),
        ("Amerika, Brezilya Série A, MLS Playoff & Kolombiya/Uruguay (21:00 - 03:45 TSİ)", lambda r: r["idx"] in (39, 44, 45, 46, 51, 52, 53, 54, 55, 56, 57, 58, 59)),
    ]

    for gtitle, pred in groups:
        lines.extend([
            f"### {gtitle}",
            "",
            "| # | Saat | Maç | MBS | Global 1X2 (%) | xG (Ev-Dep / Top) | İY/MS Favori | En Olası Band | 1Y/2Y KG | İlk 3 Skor | En Sağlam Nesine (Adil / EV) |",
            "| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :--- |",
        ])
        for r in [x for x in results if pred(x)]:
            p1x2 = r["ft_1x2"]
            p_str = f"{p1x2['1']*100:.0f}-{p1x2['0']*100:.0f}-{p1x2['2']*100:.0f}"
            xg_str = f"{r['mu_home']:.2f}-{r['mu_away']:.2f} ({r['expected_total']:.2f})"
            sp = r["special_summary"]
            htft_s = f"{sp['best_ht_ft']['sel']} (%{sp['best_ht_ft']['prob']*100:.0f})"
            band_s = f"{sp['best_band']['sel']} (%{sp['best_band']['prob']*100:.0f})"
            btts_h = f"%{sp['1Y_KG_Var']*100:.0f} / %{sp['2Y_KG_Var']*100:.0f}"
            scores_s = ", ".join(f"{s['score']} (%{s['prob']*100:.1f})" for s in r["top_ft_scores"])
            b = r["best_nesine_bet"]
            if b:
                ko_tag = " [Kupa]" if r["is_knockout"] else ""
                ou_tag = "" if r["has_global_ou"] else "*"
                bet_s = f"**{b['selection']} @ {b['nesine_odds']:.2f}** (Adil {b['global_fair_odds']:.2f}, P=%{b['global_prob']*100:.0f}, {b['nesine_ev']*100:+.1f}%){ko_tag}{ou_tag}"
            else:
                bet_s = "Uygun >=1.20 Yok / Bloke"
            lines.append(
                f"| {r['idx']} | {r['day'].split()[1]} {r['ko']} | {r['home']} - {r['away']} | {r['mbs']} | {p_str} | {xg_str} | {htft_s} | {band_s} | {btts_h} | {scores_s} | {bet_s} |"
            )
        lines.append("")

    # Section 3: ESPN L5 Verification Notes
    lines.extend([
        "---",
        "",
        "## 3. ESPN L5 Canlı Form & Risk Kalkanı Bulguları",
        "",
    ])
    for r in results:
        if r["l5_note"]:
            lines.append(f"- **#{r['idx']} {r['home']} - {r['away']} (`{r['league']}`):** {r['l5_note']}")
    lines.extend([
        "- **Vitoria BA - Bragantino (`KG Var`) Elenmesi:** Vitória son 5 maçta `0G-2B-3M (3 gol attı / 9 yedi)`, bu nedenle soğuk hücum kalkanı ile kupon dışı bırakıldı.",
        "- **Yüksek Beraberlik `ÇŞ 12` Kalkanı:** `ZED - Smouha (X=%31.1)`, `Malavan - GOL Gohar (X=%33.4)`, `Sao Paulo - Fluminense (X=%29.0)` gibi maçlarda `0-0 / 1-1` riskine karşı `ÇŞ 12` kilitlendi.",
        "- **Bayern (K) Defans Notu:** `Austria Wien (K) - B. Münih (K)` maçında `KG Yok @ 1.41` küresel adil fiyatında (`+0.5% EV`), ancak Bayern (K) L5'te `9 gol` yediği için yüksek güven çekirdek kupon yerine dengeli değer katmanına konumlandırıldı.",
        "",
        "---",
        "",
        "## 4. Global Özel Market Radarı (İY/MS, 1Y/2Y KG, 6+ Gol, Top-3 Skor)",
        "",
        "> *Nesine ana bültende yer almayan özel marketlerin oranları yalnızca Global xG modeliyle üretilen **Adil Oran** olarak listelenmiştir; doğrudan Nesine maç detay ekranındaki oranla kıyaslayarak oynanmalıdır.*",
        "",
        "### En Yüksek 6+ Gol / Gollü Geçmeye Aday Maçlar",
    ])
    for r in specials["high_total"]:
        p6 = r["special_summary"]["6_plus_gol"]
        lines.append(
            f"- **#{r['idx']} {r['home']} - {r['away']}** (`Top xG: {r['expected_total']:.2f}`) -> "
            f"`3.5 Üst: %{r['ft_ou']['3.5 Üst']*100:.1f}` | `6+ Gol: %{p6*100:.1f}` (Adil `{1.0/max(p6,1e-4):.2f}`) | En olası skor: `{r['top_ft_scores'][0]['score']}`"
        )
    lines.extend(["", "### 1. Yarı & 2. Yarı KG Var Adayları (Her İki Yarı KG)"])
    for r in specials["btts_halves"]:
        sp = r["special_summary"]
        lines.append(
            f"- **#{r['idx']} {r['home']} - {r['away']}** (`xG: {r['mu_home']:.2f}-{r['mu_away']:.2f}`) -> "
            f"`1Y KG Var: %{sp['1Y_KG_Var']*100:.1f}` | `2Y KG Var: %{sp['2Y_KG_Var']*100:.1f}` | `İki Yarı KG: %{sp['Her_2_Yari_KG']*100:.1f}` (Adil `{1.0/max(sp['Her_2_Yari_KG'],1e-4):.2f}`)"
        )
    lines.extend(["", "### İlk Yarı Berabere -> Maç Sonu Kazanan (`0/1` & `0/2`) Adayları"])
    for item in specials["ht0_ft_win"]:
        rr = item["r"]
        lines.append(
            f"- **#{rr['idx']} {rr['home']} - {rr['away']}** -> **`{item['sel']}`** `P=%{item['prob']*100:.1f}` (Global Adil `{1.0/max(item['prob'],1e-4):.2f}`)"
        )
    lines.extend(["", "### En Yüksek Olasılıklı İlk 3 Kesin Skor Kümeleri (Düşük Entropi)"])
    for r in specials["top_clusters"]:
        c3 = r["top3_cluster"]
        lines.append(
            f"- **#{r['idx']} {r['home']} - {r['away']}** -> Küme: **`{', '.join(c3['scores'])}`** (Küme Olasılığı **`%{c3['prob']*100:.1f}`**, Adil `{c3['fair_odds']:.2f}`, Entropi `{r['score_entropy']:.2f}`)"
        )
    lines.extend(["", "---", "", "## 5. 19 Kasım 2026 Resmi Nesine Kupon Portföyü (Tamamı `>= 1.20` Oran & MBS Uyumlu)", ""])

    coupon_md_blocks: list[str] = []
    for c in coupons:
        block = [
            f"### {c['title']}",
            f"- **Kademe:** {c['tier']} | **Önerilen Pay:** {c['recommended_stake_pct']}",
            f"- **Toplam Nesine Oranı:** **`{c['total_odds']:.2f}x`** | **Maç Sayısı:** {c['leg_count']} (Maks MBS: {c['max_mbs']}) | **Ort. Global Olasılık:** **`%{c['average_leg_probability']*100:.1f}`** | **Birleşik Olasılık:** `%{c['joint_probability']*100:.2f}` | **Ort. EV:** `{c['average_nesine_ev']*100:+.1f}%`",
            f"- **Sistem Notu:** {c['system_note']}",
            "",
            "| # | Saat | Maç | Lig | MBS | Tercih | Nesine Oran | Global Adil | Global % | EV | xG & Top-3 Skor |",
            "| :---: | :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :--- |",
        ]
        for l in c["legs"]:
            block.append(
                f"| {l['idx']} | {l['ko_tsi']} | {l['home']} - {l['away']} | {l['league']} | {l['mbs']} | "
                f"**{l['selection']}** | **{l['odds']:.2f}** | {l['fair_odds']:.2f} | %{l['prob']*100:.1f} | {l['nesine_ev']*100:+.1f}% | `{l['xg_summary']}` / {', '.join(l['top_scores'])} |"
            )
        block.append("")
        coupon_md_blocks.extend(block)

    lines.extend(coupon_md_blocks)

    report_path = REPO_ROOT / "reports" / "today_all_59_nesine_global_2026_11_19.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    ledger_md_lines = [
        "# 19 Kasım 2026 Resmi Kupon Defteri (Global-Verified Nesine Portföyü)",
        "",
        "**Kayıt Zamanı:** 2026-11-19 07:20 TSİ (Tüm maçlar öncesi)  ",
        "**Benchmark Kaynakları:** Tier-1 Pinnacle + Tier-2 Flashscore Global (`bookmakerId=417`) + Sofascore / ESPN L5  ",
        "**Kurallar:** Minimum tekil oran `1.20`, tüm MBS kuralları (`len(legs) >= max(mbs)`) doğrulanmış, sıfır tahminî Nesine oranı.",
        "",
    ] + coupon_md_blocks
    ledger_md_path = REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_19.md"
    ledger_md_path.write_text("\n".join(ledger_md_lines), encoding="utf-8")

    ledger_json_path = REPO_ROOT / "reports" / "ledger" / "coupons_2026_11_19.json"
    ledger_json_path.write_text(
        json.dumps(
            {
                "date": "2026-11-19",
                "engine_version": "QuantFoot-v6.1 (Global Sharp Benchmark + 5-Layer Post-Mortem Guard)",
                "global_sources": "Pinnacle + Flashscore Global (id=417) + Sofascore (id=1) + ESPN L5",
                "min_allowed_odds": MIN_ALLOWED_ODDS,
                "total_matches_analyzed": len(results),
                "total_coupons": len(coupons),
                "coupons": coupons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    artifact_path = Path(
        r"C:\Users\pc\.gemini\antigravity\brain\fd718395-2b56-447a-8788-984e92dfbffb\nov19_nesine_global_analysis_2026_11_19.md"
    )
    artifact_path.write_text("\n".join(lines), encoding="utf-8")

    # Update ledger INDEX.md idempotently
    index_path = REPO_ROOT / "reports" / "ledger" / "INDEX.md"
    if index_path.exists():
        idx_lines = [ln for ln in index_path.read_text(encoding="utf-8").splitlines() if "QuantFoot-v6.1 (Global Benchmark)" not in ln]
        idx_lines.append(
            "| **2026-11-19** | `QuantFoot-v6.1 (Global Benchmark)` | 59 Maç | "
            "[today_all_59_nesine_global_2026_11_19.md](../today_all_59_nesine_global_2026_11_19.md) / "
            "[coupons_2026_11_19.md](coupons_2026_11_19.md) / [coupons_2026_11_19.json](coupons_2026_11_19.json) | "
            "`7 Resmi Kupon (MBS & >=1.20 Doğrulanmış) - BEKLİYOR` |"
        )
        index_path.write_text("\n".join(idx_lines) + "\n", encoding="utf-8")


def main() -> None:
    results = [analyze_match(m) for m in MATCH_DATA]
    by_idx = {r["idx"]: r for r in results}

    with_ou = [r for r in results if r["has_global_ou"]]
    print(f"Analyzed {len(results)} Nesine matches ({len(with_ou)} with Full Global 1X2+O/U, {len(results)-len(with_ou)} with Global 1X2).")

    # Build 7 MBS-valid, strictly >= 1.20, Global-Verified Nesine coupons
    coupons = [
        _build_verified_coupon(
            coupon_id="2026_11_19_C1_DUO_BANKO",
            title="KUPON 1 — 2 Maçlık MBS 1-2 Akıllı İkili Banko (~2.0x)",
            tier="Kademe 1A (MBS<=2 Banko İkili)",
            stake_pct="Günlük bütçenin %25'i",
            system_note="Düz İkili (MBS<=2 — AL Ain sıfır vergi %64.5 + Vasco Pinnacle/Flashscore O/U 3.5 Alt %69.9)",
            legs=[
                _pick_leg(by_idx, 28, "KG Yok", "Sıfır Nesine vergisi (+0.5% EV); AL Ain 1.09 favori, xG 3.25-0.45.", "Karşılıksız Gol"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Pinnacle 1X2 + Flashscore O/U 3.5 (1.38 Under); Vasco L5 8-7, Inter 6-5.", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C2_CORE_3LEG",
            title="KUPON 2 — 3 Maçlık Çekirdek Güven Kuponu (Kasa Koruma, Farklı Kıta & Market)",
            tier="Kademe 1B (Ana Kasa Koruma — En Dengeli Çekirdek)",
            stake_pct="Günlük bütçenin %25'i",
            system_note="Düz 3'lü (3 farklı lig/kıta + 3 farklı market: KG Yok + MS 1 + 3.5 Alt; 0 kupa riski)",
            legs=[
                _pick_leg(by_idx, 28, "KG Yok", "BAE Ligi 1.09 favori, Global P=%64.5, EV=+0.5%.", "Karşılıksız Gol"),
                _pick_leg(by_idx, 45, "MS 1", "Penarol iç saha dominasyonu (Flashscore 1.39 -> P=%68.8), lig maçı.", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Pinnacle + Flashscore 3.5 Alt (P=%69.9), MBS 1.", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C3_BALANCED_4LEG",
            title="KUPON 3 — 4 Maçlık Düşük Vergi & Küresel Dengeli Kupon (~5x)",
            tier="Kademe 2 (Düşük Nesine Vergisi — Dengeli Oran)",
            stake_pct="Günlük bütçenin %15'i",
            system_note="Düz 4'lü (Ortalama %-7.2 EV — Nesine'nin en adil fiyatladığı 4 Tam O/U lig/UEFA maçı)",
            legs=[
                _pick_leg(by_idx, 15, "KG Yok", "Al Wasl 1.09 favori (Flashscore O3.5=1.64 -> xG 3.48-0.54, EV=-1.4%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 28, "KG Yok", "AL Ain 1.09 favori (xG 3.25-0.45, EV=+0.5%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 7, "2.5 Üst", "ASEAN Grup B yüksek tempo (Flashscore 1.50 Over -> P=%62.1).", "Alt/Üst"),
                _pick_leg(by_idx, 50, "2.5 Üst", "Benfica (K) L5 6-9 vs Roma (K) L5 8-10 (Flashscore 1.47 Over -> P=%63.5).", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C4_GOALS_BTTS_6LEG",
            title="KUPON 4 — 6 Maçlık Gol & KG Global Özel Kupon (~5.4x)",
            tier="Kademe 2B (Sıfır Taraf / MS Riski — Saf Gol & KG)",
            stake_pct="Günlük bütçenin %12'si",
            system_note="Düz 6'lı (Yalnızca Alt/Üst ve KG seçenekleri; tüm ayaklarda Global P >= %62.1, Ort %67.2)",
            legs=[
                _pick_leg(by_idx, 28, "KG Yok", "AL Ain vs AL Dhafra: P=%64.5, EV=+0.5%.", "Karşılıksız Gol"),
                _pick_leg(by_idx, 7, "2.5 Üst", "Cong An vs Johor Darul: P=%62.1, EV=-11.2%.", "Alt/Üst"),
                _pick_leg(by_idx, 38, "2.5 Üst", "Paris FC (K) L5 9-6 vs HB Koege (K) L5 7-12 (Flashscore P=%65.0).", "Alt/Üst"),
                _pick_leg(by_idx, 30, "KG Var", "Katar Yıldızlar Ligi tempolu eşleşme (xG 1.55-1.95 -> P=%69.4).", "Karşılıklı Gol"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Vasco vs Internacional (Flashscore 3.5 Alt -> P=%69.9).", "Alt/Üst"),
                _pick_leg(by_idx, 56, "1.5 Üst", "Sao Paulo (6-5) vs Fluminense (8-5): P(2+ gol)=%72.1, MBS 1.", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C5_TARGET_10X",
            title="KUPON 5 — Hedef 10x Global-Optimize Kupon (~10.8x)",
            tier="Kademe 3 (Orta-Yüksek Oran — Sıfır Kupa Riski)",
            stake_pct="Günlük bütçenin %10'u",
            system_note="Düz 7'li (7 farklı lig/saat kombinasyonu, her ayak >= %59.1 Global olasılık, Kupa maçı 0)",
            legs=[
                _pick_leg(by_idx, 15, "KG Yok", "Al Wasl 1.09 favori (EV=-1.4%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 28, "KG Yok", "AL Ain 1.09 favori (EV=+0.5%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 7, "2.5 Üst", "Cong An vs Johor Darul (P=%62.1).", "Alt/Üst"),
                _pick_leg(by_idx, 4, "KG Var", "Preah Khan vs Port (xG 1.51-1.43, 1.41 makul vergi, P=%61.4).", "Karşılıklı Gol"),
                _pick_leg(by_idx, 38, "2.5 Üst", "Paris (K) vs HB Koege (K) (P=%65.0).", "Alt/Üst"),
                _pick_leg(by_idx, 45, "MS 1", "Penarol iç saha (P=%68.8).", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Vasco vs Internacional (P=%69.9).", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C6_TARGET_20X",
            title="KUPON 6 — Hedef 20x Global Değer Kuponu (~22.0x)",
            tier="Kademe 4 (20x Hedef — Global Verimli Seçimler)",
            stake_pct="Günlük bütçenin %8'i",
            system_note="Düz 9'lu veya Sistem 7-8/9 önerilir (Tamamı Flashscore Global 1X2+O/U doğrulanmış lig maçları)",
            legs=[
                _pick_leg(by_idx, 15, "KG Yok", "Al Wasl (P=%59.1, EV=-1.4%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 28, "KG Yok", "AL Ain (P=%64.5, EV=+0.5%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 7, "2.5 Üst", "Cong An vs Johor (P=%62.1).", "Alt/Üst"),
                _pick_leg(by_idx, 4, "KG Var", "Preah Khan vs Port (P=%61.4).", "Karşılıklı Gol"),
                _pick_leg(by_idx, 16, "KG Yok", "İran Pro Ligi 1.78 xG (Malavan - Gol Gohar: P=%68.5, EV=-11.6%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 25, "MS 2", "Bulgaristan 2. Lig: Fratria Varna (Flashscore 1.72 -> P=%54.7).", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 38, "2.5 Üst", "Paris (K) vs HB Koege (K) (P=%65.0).", "Alt/Üst"),
                _pick_leg(by_idx, 45, "MS 1", "Penarol iç saha (P=%68.8).", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Vasco vs Internacional (P=%69.9).", "Alt/Üst"),
            ],
        ),
        _build_verified_coupon(
            coupon_id="2026_11_19_C7_TARGET_30X",
            title="KUPON 7 — Hedef 30x Global Akıllı Kombine (~33.0x)",
            tier="Kademe 5 (30x+ Hedef — Global Yüksek Oranlı Kombine)",
            stake_pct="Günlük bütçenin %5'i",
            system_note="Düz 11'li veya Sistem 9/11 önerilir (Tüm ayaklarda Global P >= %54.7 ve Nesine >= 1.20)",
            legs=[
                _pick_leg(by_idx, 15, "KG Yok", "Al Wasl (EV=-1.4%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 28, "KG Yok", "AL Ain (EV=+0.5%).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 7, "2.5 Üst", "Cong An vs Johor (P=%62.1).", "Alt/Üst"),
                _pick_leg(by_idx, 4, "KG Var", "Preah Khan vs Port (P=%61.4).", "Karşılıklı Gol"),
                _pick_leg(by_idx, 16, "KG Yok", "Malavan vs Gol Gohar (P=%68.5).", "Karşılıksız Gol"),
                _pick_leg(by_idx, 30, "KG Var", "Al Ahli Doha vs Al Shamal (P=%69.4).", "Karşılıklı Gol"),
                _pick_leg(by_idx, 25, "MS 2", "Fratria Varna deplasman (P=%54.7).", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 38, "2.5 Üst", "Paris (K) vs HB Koege (K) (P=%65.0).", "Alt/Üst"),
                _pick_leg(by_idx, 45, "MS 1", "Penarol iç saha (P=%68.8).", "Maç Sonucu (1X2)"),
                _pick_leg(by_idx, 52, "3.5 Alt", "Vasco vs Internacional (P=%69.9).", "Alt/Üst"),
                _pick_leg(by_idx, 56, "1.5 Üst", "Sao Paulo vs Fluminense (P=%72.1).", "Alt/Üst"),
            ],
        ),
    ]

    specials = _format_special_top_lists(results)
    _write_markdown_reports(results, coupons, specials)

    out_json = REPO_ROOT / "reports" / "nov19_nesine_global_analysis.json"
    out_json.write_text(
        json.dumps(
            {
                "generated_at": "2026-11-19T07:20:00+03:00",
                "global_sources": "Tier 1: Pinnacle Benchmark (UWCL, Brazil Serie A, MLS); Tier 2: Flashscore Global Odds Feed (bookmakerId=417, 1X2 + O/U 2.5/3.5); Cross-check: Sofascore & ESPN DraftKings",
                "total_matches": len(results),
                "matches": results,
                "coupons": {c["coupon_id"]: c for c in coupons},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    for c in coupons:
        print(
            f"\n=== {c['title']} | Toplam Oran: {c['total_odds']:.2f}x | Ayak: {c['leg_count']} (MBS<= {c['max_mbs']}) | "
            f"Ort. P: %{c['average_leg_probability']*100:.1f} | Birleşik P: %{c['joint_probability']*100:.2f} | Ort. EV: {c['average_nesine_ev']*100:+.1f}% ==="
        )
        for l in c["legs"]:
            print(
                f"  - [{l['ko_tsi']}] #{l['idx']} {l['home']} - {l['away']} ({l['league']}, MBS {l['mbs']}): "
                f"{l['selection']} @ {l['odds']:.2f} | Global Adil {l['fair_odds']:.2f} (P=%{l['prob']*100:.1f}, EV={l['nesine_ev']*100:+.1f}%)"
            )


if __name__ == "__main__":
    main()
