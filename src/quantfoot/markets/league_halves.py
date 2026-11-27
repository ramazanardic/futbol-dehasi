"""League first-half goal share from data/lig_yari_oranlari.csv (scripts/gfi_yari_oranlari.py).

Sources: openfootball/football.json (CC0) and, for fc.* codes, Data: Football Charts (football-charts.com), CC BY 4.0.

The half model splits each team's goal rate into halves with a first-half share; without a league profile every Nesine
club league used 0.444 (the 'e0' profile). This gives the share measured in that league's own archive, shrunk toward
0.440 so a small sample cannot move it far.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

CSV = Path(__file__).resolve().parents[3] / "data" / "lig_yari_oranlari.csv"
PRIOR = 0.440
PRIOR_GOALS = 400.0  # pseudo-goals of the prior
MIN_MATCHES = 80

# Nesine league name (text before the first comma) -> archive league codes (pooled). openfootball codes (several
# seasons) where they exist, Football Charts 2025-26 (fc.*) for the rest. Names as they appear in Nesine bulletins.
NESINE_TO_CODES: dict[str, tuple[str, ...]] = {
    "İngiltere Premier Lig": ("en.1",), "İngiltere Championship": ("en.2",), "İngiltere 1. Lig": ("en.3",),
    "İngiltere 2. Lig": ("en.4",), "İngiltere Ulusal Lig": ("fc.national",),
    "Almanya Bundesliga": ("de.1",), "Almanya Bundesliga 2": ("de.2",), "Almanya 3. Lig": ("de.3",),
    "İspanya La Liga": ("es.1",), "İspanya La Liga 2": ("es.2",), "İspanya 2. Lig": ("es.2",),
    "İspanya Primera RFEF": ("fc.primera1", "fc.primera2"),
    "İtalya Serie A": ("it.1",), "İtalya Serie B": ("it.2",), "İtalya Serie C": ("fc.italy3a", "fc.italy3b"),
    "Fransa Ligue 1": ("fr.1",), "Fransa Ligue 2": ("fr.2",), "Fransa Ulusal Lig": ("fc.france3",),
    "Hollanda Eredivisie": ("nl.1",), "Hollanda 1. Lig": ("fc.holland2",),
    "Portekiz Premier Lig": ("pt.1",), "Portekiz Süper Lig": ("pt.1",),
    "Türkiye Süper Ligi": ("tr.1",), "Türkiye Süper Lig": ("tr.1",), "Türkiye 1. Lig": ("tr.2",),
    "Belçika Pro Lig": ("be.1",), "Avusturya Bundesliga": ("at.1",), "Avusturya 2. Lig": ("at.2",),
    "İsviçre Süper Lig": ("ch.1",), "İsviçre Challenge Ligi": ("ch.2",),
    "Çekya 1. Lig": ("cz.1",), "Çekya 2. Lig": ("fc.czech2",), "Yunanistan Süper Lig": ("gr.1",),
    "İskoçya Premiership": ("sco.1",), "İskoçya Championship": ("fc.scot-champ",), "İskoçya 1. Lig": ("fc.scot1",),
    "İskoçya 2. Lig": ("fc.scot2",),
    "Rusya Premier Lig": ("ru.1",), "Rusya Ulusal Ligi": ("ru.2",), "Macaristan 1. Ligi": ("hu.1",),
    "Macaristan 2. Ligi": ("fc.hungary2",),
    "Danimarka Süper Ligi": ("fc.denmark1",), "Danimarka 1. Lig": ("fc.denmark2",),
    "Polonya Ekstraklasa": ("fc.poland1",), "Polonya 1. Lig": ("fc.poland2",), "Romanya 1. Lig": ("fc.romania1",),
    "Bulgaristan Parva Ligi": ("fc.bulgaria1",), "Sırbistan Superliga": ("fc.serbia1",),
    "Slovenya PrvaLiga": ("fc.slovenia1",), "Azerbaycan Premier Lig": ("fc.azer",),
    "Suudi Arabistan Pro Lig": ("fc.saudi1",), "Suudi Arabistan 1. Lig": ("fc.saudi2",),
    "Suudi Arabistan 2. Lig": ("fc.saudi2",), "Suudi Arabistan 2.Lig": ("fc.saudi2",),
    "Mısır Premier Lig": ("eg.1", "fc.egypt"), "Fas Botola Pro": ("ma.1", "fc.morocco"),
    "Cezayir 1. Lig": ("dz.1", "fc.algir1"), "Tayland 1.Lig": ("fc.thai1",),
    "Tayland Şampiyonası": ("fc.thai1",), "Tayland 1. Lig": ("fc.thai1",),
    "Hindistan Süper Ligi": ("fc.india1",), "Japonya J Ligi": ("jp.1", "fc.japan1"),
    "Japonya J1 Ligi": ("jp.1", "fc.japan1"), "Avustralya A-Ligi": ("fc.australia",),
    "Brezilya Serie A": ("br.1",), "Brezilya Serie B": ("br.2",),
    "Meksika P. Ligi": ("mx.1",), "UEFA Şampiyonlar Ligi": ("uefa.cl",),
    "Arjantin Primera Lig": ("ar.1",), "Arjantin Liga Profesional": ("ar.1",),
    "Çin Süper Ligi": ("cn.1",), "Kolombiya Primera A": ("co.1",), "Copa Libertadores": ("copa.l",),
    "ABD MLS": ("mls",), "Yunanistan Süper Lig 2": ("fc.greece2",), "Hollanda 2. Lig": ("fc.holland3",),
    "Kuveyt Premier Lig": ("fc.kuwait",), "Almanya Kupası": ("de.cup",), "Avusturya Kupası": ("at.cup",),
    "İspanya Segunda RFEF": ("fc.segunda1", "fc.segunda2", "fc.segunda3", "fc.segunda4", "fc.segunda5"),
    "İngiltere Ulusal Lig Kuzey": ("fc.north",), "İngiltere Ulusal Lig Güney": ("fc.south",),
    "Almanya Regionalliga Kuzey": ("fc.germany-north",), "Çekya 3. Lig": ("fc.czech3a", "fc.czech3b"),
    "İtalya Primavera": ("fc.italy19",), "Fransa Kadınlar 1. Lig": ("fc.wfrance1",),
    "Almanya Kadınlar Bundesliga": ("fc.wgermany1",), "Belçika Kadınlar Süper Lig": ("fc.wbelgium1",),
}


def _norm_league_key(name: str) -> str:
    return " ".join(
        name.split(",")[0]
        .replace("İ", "i")
        .replace("I", "ı")
        .lower()
        .replace(".", " ")
        .split()
    )


_NORM_NESINE_TO_CODES: dict[str, tuple[str, ...]] = {
    _norm_league_key(k): v for k, v in NESINE_TO_CODES.items()
}


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, str]]:
    if not CSV.exists():
        return {}
    with CSV.open(encoding="utf-8") as fh:
        return {r["lig"]: r for r in csv.DictReader(ln for ln in fh if not ln.startswith("#"))}


def _rows(nesine_league: str | None) -> list[dict[str, str]]:
    if not nesine_league:
        return []
    head = " ".join(nesine_league.split(",")[0].split())
    codes = NESINE_TO_CODES.get(head) or _NORM_NESINE_TO_CODES.get(_norm_league_key(head), ())
    return [r for c in codes if (r := _table().get(c))]


def _goals() -> dict[str, tuple[int, float, float]]:
    """league code -> (matches, all goals, first-half goals)."""
    out = {}
    for code, r in _table().items():
        if r.get("iy_gol_payi"):
            n = int(r["n"])
            goals = n * float(r["gol"])
            out[code] = (n, goals, goals * float(r["iy_gol_payi"]))
    return out


# GFI half-family replay (2023-25, ~25,500 source-local evaluations, docs/HALF_FAMILY_REPLAY.md in the user's GLOBAL
# FOOTBALL INTELLIGENCE project): for both-halves BTTS and the highest-scoring half the empirical league rate scored a
# lower Brier than the team model, while the team model won the other half families. So these selections are blended
# toward the league rate. MODEL_WEIGHT is a prior choice, not fitted: our model starts from sharp prices, so it keeps
# the larger share.
LEAGUE_BLEND = {"İki Yarıda KG Var": "kg_iki_yari", "En Çok Gol 1Y": "en_cok_1y", "En Çok Gol 2Y": "en_cok_2y",
                "En Çok Gol Eşit": "en_cok_esit"}
MODEL_WEIGHT = 0.6


def league_rate(nesine_league: str | None, column: str) -> float | None:
    """Pooled league frequency of a CSV column, or None without MIN_MATCHES matches."""
    rows = [r for r in _rows(nesine_league) if r.get(column)]
    n = sum(int(r["n"]) for r in rows)
    if n < MIN_MATCHES:
        return None
    return sum(int(r["n"]) * float(r[column]) for r in rows) / n


def blend_with_league(name: str, p_model: float, nesine_league: str | None) -> float:
    """Model probability blended toward the league rate for LEAGUE_BLEND selections; others unchanged."""
    col = LEAGUE_BLEND.get(name)
    rate = league_rate(nesine_league, col) if col else None
    return p_model if rate is None else MODEL_WEIGHT * p_model + (1.0 - MODEL_WEIGHT) * rate


def league_first_half_share(nesine_league: str | None) -> float | None:
    """Shrunk first-half goal share of a Nesine league, or None when the archive has no reliable sample."""
    if not nesine_league:
        return None
    goals = _goals()
    rows = [goals[r["lig"]] for r in _rows(nesine_league) if r["lig"] in goals]
    n = sum(r[0] for r in rows)
    if n < MIN_MATCHES:
        return None
    goals, first = sum(r[1] for r in rows), sum(r[2] for r in rows)
    return (first + PRIOR * PRIOR_GOALS) / (goals + PRIOR_GOALS)


def league_comeback_rates(nesine_league: str | None) -> dict[str, float] | None:
    """Return pooled empirical rates for HT/FT reversals, half-reversals, and both-halves BTTS."""
    cols = ("iyms_1/2", "iyms_2/1", "iy2y_1/2", "iy2y_2/1", "kg_iki_yari")
    out: dict[str, float] = {}
    for col in cols:
        val = league_rate(nesine_league, col)
        if val is not None:
            out[col] = round(float(val), 5)
    return out or None
