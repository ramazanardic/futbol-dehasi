"""League base rates from the Global Football Data Lake (huggingface.co/datasets/eatpizzanot/soccer-dataset,
CC BY 4.0; user decision, 21 Nov).

The Data Lake holds 673,966 fixtures of 271 leagues (API-Football + football-data.co.uk), current to 5 July 2026,
full-time scores only. Its use here: how a league usually plays — goals per match, both-teams-score, over 2.5,
home win and draw rates over the last two seasons. These rates are DISPLAY-ONLY context in simulasyon.md (shown next
to each match so a reader can compare a pick with what is normal in that league); they are NOT an input of the
simulation, the market price or any verdict (no walk-forward evidence that they add information beyond the price). Files are downloaded once into data/cache/datalake (git-ignored); the derived table is
data/lig_oranlari.csv (with attribution).

    python scripts/datalake_lig.py            # (re)build data/lig_oranlari.csv
    python scripts/datalake_lig.py --lig "Galler Premier Lig"

Data: Global Football Data Lake by eatpizzanot, CC BY 4.0.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import re
from pathlib import Path
import sys

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

HF = "https://huggingface.co/datasets/eatpizzanot/soccer-dataset/resolve/main/{name}.parquet"
CACHE = dr.ROOT / "data" / "cache" / "datalake"
OUT = dr.ROOT / "data" / "lig_oranlari.csv"
SINCE = "2024-07-01"
MIN_N = 60
# Nesine country words -> Data Lake country
COUNTRY = {"İngiltere": "England", "Galler": "Wales", "İskoçya": "Scotland", "Kuzey İrlanda": "Northern-Ireland",
           "İrlanda": "Ireland", "Almanya": "Germany", "İspanya": "Spain", "İtalya": "Italy", "Fransa": "France",
           "Hollanda": "Netherlands", "Belçika": "Belgium", "Portekiz": "Portugal", "Türkiye": "Turkey", "Yunanistan": "Greece",
           "Avusturya": "Austria", "İsviçre": "Switzerland", "Danimarka": "Denmark", "Norveç": "Norway", "İsveç": "Sweden",
           "Finlandiya": "Finland", "Polonya": "Poland", "Çekya": "Czech-Republic", "Slovakya": "Slovakia", "Slovenya": "Slovenia",
           "Hırvatistan": "Croatia", "Sırbistan": "Serbia", "Romanya": "Romania", "Bulgaristan": "Bulgaria", "Macaristan": "Hungary",
           "Ukrayna": "Ukraine", "Rusya": "Russia", "Gürcistan": "Georgia", "Ermenistan": "Armenia", "Azerbaycan": "Azerbaijan",
           "Kosova": "Kosovo", "Arnavutluk": "Albania", "Karadağ": "Montenegro", "Malta": "Malta", "Kıbrıs": "Cyprus",
           "Letonya": "Latvia", "Litvanya": "Lithuania", "Estonya": "Estonia", "Cezayir": "Algeria", "Mısır": "Egypt",
           "Fas": "Morocco", "Tunus": "Tunisia", "Irak": "Iraq", "Ürdün": "Jordan", "Suudi Arabistan": "Saudi-Arabia",
           "Katar": "Qatar", "BAE": "United-Arab-Emirates", "Japonya": "Japan", "Güney Kore": "South-Korea", "Çin": "China",
           "Hindistan": "India", "Avustralya": "Australia", "Yeni Zelanda": "New-Zealand", "ABD": "USA", "Meksika": "Mexico",
           "Brezilya": "Brazil", "Arjantin": "Argentina", "Uruguay": "Uruguay", "Şili": "Chile", "Kolombiya": "Colombia",
           "Peru": "Peru", "Ekvador": "Ecuador", "Paraguay": "Paraguay", "Kosta Rika": "Costa-Rica", "Nikaragua": "Nicaragua",
           "Mozambik": "Mozambique"}
TIER_WORDS = {"Premier": "1", "Süper": "1", "1. Lig": "2", "2. Lig": "3", "3. Lig": "4", "Championship": "2", "Kupa": "cup"}


def _parquet(name: str):
    import pandas as pd
    f = CACHE / f"{name}.parquet"
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        r = requests.get(HF.format(name=name), timeout=600)
        r.raise_for_status()
        f.write_bytes(r.content)
    return pd.read_parquet(f)


def build() -> int:
    fx, lg = _parquet("fixtures"), _parquet("leagues")
    fx = fx[fx["is_played"] & (fx["date_utc"].astype(str) >= SINCE)].dropna(subset=["goals_home", "goals_away"])
    rows = []
    for lid, g in fx.groupby("league_id"):
        if len(g) < MIN_N:
            continue
        meta = lg[lg["id"] == lid].iloc[0] if (lg["id"] == lid).any() else None
        tot = g["goals_home"] + g["goals_away"]
        rows.append({"league_id": int(lid), "country": meta["country"] if meta is not None else "",
                     "league": meta["name"] if meta is not None else "", "n": len(g), "goals": round(tot.mean(), 3),
                     "btts": round(((g["goals_home"] > 0) & (g["goals_away"] > 0)).mean(), 3),
                     "over15": round((tot > 1).mean(), 3), "over25": round((tot > 2).mean(), 3), "over35": round((tot > 3).mean(), 3),
                     "home": round((g["goals_home"] > g["goals_away"]).mean(), 3),
                     "draw": round((g["goals_home"] == g["goals_away"]).mean(), 3),
                     "away": round((g["goals_home"] < g["goals_away"]).mean(), 3)})
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        fh.write("# Global Football Data Lake (eatpizzanot, CC BY 4.0), maçlar 2024-07-01 .. 2026-07-05\n")
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["country"], r["league"])))
    return len(rows)


def table() -> list[dict]:
    if not OUT.exists():
        return []
    with OUT.open(encoding="utf-8") as fh:
        return list(csv.DictReader(ln for ln in fh if not ln.startswith("#")))


# Exact Nesine name -> Data Lake league name. Needed because Nesine's tier words are country-specific
# ("İngiltere 1. Lig" = League One, tier 3; "İspanya 2. Lig" = Segunda División, tier 2; "Hollanda 1. Lig" = Eerste
# Divisie) and a fuzzy name match picks the top flight for "Almanya Bundesliga 2" / "İspanya La Liga 2".
ALIASES = {
    "İngiltere Premier Lig": "Premier League", "İngiltere Championship": "Championship", "İngiltere 1. Lig": "League One",
    "İngiltere 2. Lig": "League Two", "İngiltere Ulusal Lig": "National League",
    "Almanya Bundesliga": "Bundesliga", "Almanya Bundesliga 2": "2. Bundesliga", "Almanya 3. Lig": "3. Liga",
    "İspanya La Liga": "La Liga", "İspanya La Liga 2": "Segunda Division", "İspanya 2. Lig": "Segunda Division",
    "İtalya Serie A": "Serie A", "İtalya Serie B": "Serie B",
    "Fransa Ligue 1": "Ligue 1", "Fransa Ligue 2": "Ligue 2", "Fransa Ulusal Lig": "National 1",
    "Hollanda Eredivisie": "Eredivisie", "Hollanda 1. Lig": "Eerste Divisie",
    "Türkiye Süper Ligi": "Süper Lig", "Türkiye Süper Lig": "Süper Lig", "Türkiye 1. Lig": "1. Lig",
    "Belçika Pro Lig": "Jupiler Pro League", "Belçika 2. Lig": "Challenger Pro League",
    "Portekiz Premier Lig": "Primeira Liga", "Portekiz 2. Lig": "Liga Portugal 2",
    "Yunanistan Süper Lig": "Super League 1", "Yunanistan Süper Lig 2": "Super League 2",
    "İskoçya Premiership": "Premiership", "İskoçya Championship": "Championship", "İskoçya 1. Lig": "League One",
    "İskoçya 2. Lig": "League Two",
}
SPECIAL_WORDS = ("Bahisler", "U19", "U21", "U23", "U17", "Gençlik", "Gençler", "Kupa", "Kupası")


def _digits(s: str) -> set[str]:
    """Tier tokens of a league name: digits and single-letter grades ("Serie C", "Bundesliga 2")."""
    return set(re.findall(r"\d", s)) | {t.upper() for t in re.findall(r"\b([A-Za-z])\b", s)}


def league_rates(nesine_league: str, rows: list[dict] | None = None) -> dict | None:
    """Base rates of the Data Lake league matching a Nesine league name.

    1. exact alias table (tiers checked by hand); 2. same country + closest name, but only when the tier digits
    agree ("Bundesliga 2" never matches "Bundesliga"); 3. a country's single league for a top-flight name."""
    rows = table() if rows is None else rows
    name = " ".join(nesine_league.split())
    if any(w in name for w in SPECIAL_WORDS):
        return None
    country = next((v for k, v in sorted(COUNTRY.items(), key=lambda kv: -len(kv[0])) if name.startswith(k)), None)
    if not country:
        return None
    cands = [r for r in rows if r["country"] == country]
    if not cands:
        return None
    base = name.split(",")[0].strip()  # "Belçika 2. Lig, İlk Etap" -> "Belçika 2. Lig"
    if base in ALIASES:
        hit = [r for r in cands if r["league"] == ALIASES[base]]
        return hit[0] if hit else None
    rest = base[len(next(k for k in sorted(COUNTRY, key=len, reverse=True) if base.startswith(k))):].strip()
    tier = next((t for w, t in TIER_WORDS.items() if w in rest), "1")
    if tier == "cup":
        return None
    same_tier = [r for r in cands if _digits(r["league"]) == _digits(rest)]
    if same_tier:
        named = max(same_tier, key=lambda r: difflib.SequenceMatcher(None, rest.lower(), r["league"].lower()).ratio())
        if difflib.SequenceMatcher(None, rest.lower(), named["league"].lower()).ratio() >= 0.6:
            return named
    top = sorted(cands, key=lambda r: -int(r["n"]))
    return top[0] if tier == "1" and len(top) == 1 and not _digits(rest) else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lig", help="Bir Nesine lig adının lig ortalamalarını göster")
    args = ap.parse_args()
    if args.lig:
        print(league_rates(args.lig))
        return
    print(f"{build()} lig -> {OUT}")


if __name__ == "__main__":
    main()
