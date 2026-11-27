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
    "Suudi Arabistan Pro Lig": ("fc.saudi1",), "Suudi Arabistan 2. Lig": ("fc.saudi2",),
    "Suudi Arabistan 2.Lig": ("fc.saudi2",), "Mısır Premier Lig": ("eg.1",), "Fas Botola Pro": ("ma.1",),
    "Cezayir 1. Lig": ("dz.1",), "Tayland 1.Lig": ("fc.thai1",), "Hindistan Süper Ligi": ("fc.india1",),
    "Japonya J Ligi": ("jp.1",), "Avustralya A-Ligi": ("fc.australia",), "Brezilya Serie A": ("br.1",),
    "Meksika P. Ligi": ("mx.1",), "UEFA Şampiyonlar Ligi": ("uefa.cl",),
}


@lru_cache(maxsize=1)
def _goals() -> dict[str, tuple[int, float, float]]:
    """league code -> (matches, all goals, first-half goals)."""
    if not CSV.exists():
        return {}
    out = {}
    with CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(ln for ln in fh if not ln.startswith("#")):
            if r.get("iy_gol_payi"):
                n = int(r["n"])
                goals = n * float(r["gol"])
                out[r["lig"]] = (n, goals, goals * float(r["iy_gol_payi"]))
    return out


def league_first_half_share(nesine_league: str | None) -> float | None:
    """Shrunk first-half goal share of a Nesine league, or None when the archive has no reliable sample."""
    if not nesine_league:
        return None
    codes = NESINE_TO_CODES.get(" ".join(nesine_league.split(",")[0].split()), ())
    rows = [g for c in codes if (g := _goals().get(c))]
    n = sum(r[0] for r in rows)
    if n < MIN_MATCHES:
        return None
    goals, first = sum(r[1] for r in rows), sum(r[2] for r in rows)
    return (first + PRIOR * PRIOR_GOALS) / (goals + PRIOR_GOALS)
