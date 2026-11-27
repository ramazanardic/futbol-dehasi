"""League first-half goal share from data/lig_yari_oranlari.csv (scripts/gfi_yari_oranlari.py, openfootball CC0).

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
MIN_MATCHES = 250

# Nesine league name (text before the first comma) -> openfootball league file code
NESINE_TO_CODE = {
    "İngiltere Premier Lig": "en.1", "İngiltere Championship": "en.2", "İngiltere 1. Lig": "en.3",
    "İngiltere 2. Lig": "en.4", "Almanya Bundesliga": "de.1", "Almanya Bundesliga 2": "de.2", "Almanya 3. Lig": "de.3",
    "İspanya La Liga": "es.1", "İspanya La Liga 2": "es.2", "İspanya 2. Lig": "es.2", "İtalya Serie A": "it.1",
    "İtalya Serie B": "it.2", "Fransa Ligue 1": "fr.1", "Fransa Ligue 2": "fr.2", "Hollanda Eredivisie": "nl.1",
    "Portekiz Premier Lig": "pt.1", "Portekiz Süper Lig": "pt.1", "Türkiye Süper Ligi": "tr.1", "Türkiye Süper Lig": "tr.1",
    "Belçika Pro Lig": "be.1", "Avusturya Bundesliga": "at.1", "Avusturya 2. Lig": "at.2", "İsviçre Süper Lig": "ch.1",
    "İsviçre Challenge Lig": "ch.2", "Çekya 1. Lig": "cz.1", "Yunanistan Süper Lig": "gr.1", "İskoçya Premiership": "sco.1",
    "Rusya Premier Lig": "ru.1", "Brezilya Serie A": "br.1", "Arjantin Profesyonel Lig": "ar.1", "Meksika P. Ligi": "mx.1",
    "Japonya J1 Lig": "jp.1", "UEFA Şampiyonlar Ligi": "uefa.cl",
}


@lru_cache(maxsize=1)
def _shares() -> dict[str, float]:
    if not CSV.exists():
        return {}
    out = {}
    with CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(ln for ln in fh if not ln.startswith("#")):
            n = int(r["n"])
            if n < MIN_MATCHES or not r.get("iy_gol_payi"):
                continue
            goals = n * float(r["gol"])
            out[r["lig"]] = (float(r["iy_gol_payi"]) * goals + PRIOR * PRIOR_GOALS) / (goals + PRIOR_GOALS)
    return out


def league_first_half_share(nesine_league: str | None) -> float | None:
    """Shrunk first-half goal share of a Nesine league, or None when the archive has no reliable sample."""
    if not nesine_league:
        return None
    base = " ".join(nesine_league.split(",")[0].split())
    code = NESINE_TO_CODE.get(base)
    return _shares().get(code) if code else None
