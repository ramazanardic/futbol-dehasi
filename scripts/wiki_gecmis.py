"""Season results of leagues ESPN does not cover, from Wikipedia season articles (user request, 20 Nov: research
every match of the day, not only the ESPN-covered ones).

Wikipedia's MediaWiki API allows automated reading (content CC BY-SA); one request per league per 6 h, cached in
data/cache/wiki. The results matrix ("Module:Sports results": ``|match_ABC_DEF = 2–1``) gives every played
home/away pairing of the season with the full-time score — no dates and no half-time score, so only full-time bets
(1X2, double chance, totals, both teams to score, team totals) can be settled on it; half bets stay "geçmiş yetersiz".

    python scripts/wiki_gecmis.py --tarih 2026-11-20      # re-test the day's derin_tahminler.json on this history
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402
import derin_tahmin as dtah  # noqa: E402

CACHE = dr.ROOT / "data" / "cache" / "wiki"
API = "https://{lang}.wikipedia.org/w/api.php"
TTL_H = 6.0
_session = requests.Session()
_session.headers["User-Agent"] = "quantfoot-research/1.0 (football statistics research)"

# Nesine league name prefix -> English Wikipedia season article(s); the first one with a results matrix is used.
SEASON = {
    "Cezayir 1. Lig": ["2026–27 Algerian Ligue Professionnelle 1"],
    "Çekya 2. Lig": ["2026–27 Czech National Football League"],
    "Bulgaristan Parva Ligi": ["2026–27 First Professional Football League (Bulgaria)"],
    "Gürcistan Erovnuli Ligi": ["2026 Erovnuli Liga"],
    "Slovenya 2. Lig": ["2026–27 Slovenian Second League", "2026–27 Slovenian Second Football League"],
    "Ukrayna Premier Ligi": ["2026–27 Ukrainian Premier League"],
    "Kosova Superliga": ["2026–27 Football Superleague of Kosovo"],
    "Irak Ligi": ["2026–27 Iraq Stars League"],
    "Türkiye 1. Lig": ["2026–27 TFF 1. Lig"],
    "Polonya 1. Lig": ["2026–27 I liga"],
    "Polonya 2. Lig": ["2026–27 II liga"],
    "Polonya Ekstraklasa": ["2026–27 Ekstraklasa"],
    "Malta Premier Lig": ["2026–27 Maltese Premier League"],
    "Mozambik Mocambola": ["2026 Moçambola", "2026–27 Moçambola"],
    "Almanya Kadınlar Bundesliga": ["de:Frauen-Bundesliga 2026/27"],
    "Avusturya 2. Lig": ["2026–27 2. Liga (Austria)", "2026–27 Austrian Football Second League"],
    "Almanya Bundesliga 2": ["de:2. Fußball-Bundesliga 2026/27"],
    "Arnavutluk Süper Ligi": ["2026–27 Kategoria Superiore"],
    "Almanya Böl. Lig, Bavyera": ["de:Fußball-Regionalliga Bayern 2026/27"],
    "Almanya 3. Lig": ["de:3. Fußball-Liga 2026/27"],
    "Almanya Böl. Lig, Güney Batı": ["de:Fußball-Regionalliga Südwest 2026/27"],
    "Danimarka 1. Lig": ["2026–27 Danish 1st Division"],
    "Almanya Böl. Lig, Kuzey Doğu": ["de:Fußball-Regionalliga Nordost 2026/27"],
    "Almanya Böl. Lig, Kuzey": ["de:Fußball-Regionalliga Nord 2026/27"],
    "Almanya Böl. Lig, Batı": ["de:Fußball-Regionalliga West 2026/27"],
    "İspanya Primera RFEF": ["2026–27 Primera Federación"],
    "İsviçre Challenge Ligi": ["2026–27 Swiss Challenge League"],
    "Romanya 1. Lig": ["2026–27 Liga I"],
    "Belçika 2. Lig": ["2026–27 Challenger Pro League"],
    "Hollanda 1. Lig": ["2026–27 Eerste Divisie"],
    "Karadağ 1. CFL": ["2026–27 Montenegrin First League"],
    "İtalya Serie C": ["2026–27 Serie C"],
    "Galler Championship, Güney": ["2026–27 Cymru South"],
    "Galler Premier Lig": ["2026–27 Cymru Premier"],
    "Kuzey İrlanda Premiership": ["2026–27 NIFL Premiership"],
    "Kuzey İrlanda Championship": ["2026–27 NIFL Championship"],
    "İngiltere Ulusal Lig": ["2026–27 National League"],
    "Fransa Kadınlar 1. Lig": ["2026–27 Première Ligue"],
    "Yeni Zelanda Premiership": ["2026 New Zealand National League"],
    "Uruguay Prmr Ligi": ["2026 Uruguayan Primera División season"],
    "Nikaragua Prmr Ligi": ["2026–27 Liga Primera de Nicaragua"],
}


def wikitext(title: str) -> str:
    """Wikitext of an article; a "de:" prefix reads German Wikipedia."""
    lang, _, page = title.rpartition(":") if title.startswith("de:") else ("en", "", title)
    key = hashlib.sha1(title.encode()).hexdigest()
    f = CACHE / f"{key}.txt"
    if f.exists() and time.time() - f.stat().st_mtime < TTL_H * 3600:
        return f.read_text(encoding="utf-8")
    for wait in (1, 5, 20):
        time.sleep(wait)
        try:
            r = _session.get(API.format(lang=lang), params=dict(action="parse", page=page, prop="wikitext", format="json",
                                              formatversion=2, redirects=1), timeout=30)
            j = r.json()
        except (requests.RequestException, ValueError):
            continue  # throttled / non-JSON: back off and retry
        w = (j.get("parse") or {}).get("wikitext", "")
        if not w and (j.get("error") or {}).get("code") != "missingtitle":
            continue  # rate-limited: never cache an empty answer
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(w, encoding="utf-8")
        return w
    return ""


def _clean(link: str) -> str:
    link = re.sub(r"<ref.*?(</ref>|/>)", "", link, flags=re.S)
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", link)
    name = (m.group(2) or m.group(1)) if m else link
    return re.sub(r"\{\{.*?\}\}|'''?", "", name).strip()


def results_matrix(w: str) -> tuple[dict[str, str], list[tuple[str, str, int, int]]]:
    """({code: team name}, [(home code, away code, home goals, away goals)]) from a Sports results matrix."""
    names = {m.group(1): _clean(m.group(2)) for m in re.finditer(r"\|\s*name_([A-Za-z0-9]+)\s*=\s*([^\n]+)", w)}
    games = []
    for m in re.finditer(r"\|\s*match_([A-Za-z0-9]+)_([A-Za-z0-9]+)\s*=\s*(?:\[\[[^\]|]*\|)?\s*(\d+)\s*[–-]\s*(\d+)", w):
        games.append((m.group(1), m.group(2), int(m.group(3)), int(m.group(4))))
    return names, games


def crosstable(w: str) -> tuple[dict[str, str], list[tuple[str, str, int, int]]]:
    """German Wikipedia "Kreuztabelle" (home team = row, away team = column, cells "2:1")."""
    i = w.find("Kreuztabelle")
    if i < 0:
        return {}, []
    table = w[w.find("{|", i): w.find("\n|}", i)]
    cols, names, games = [], {}, []
    rows = table.split("\n|-")
    for line in rows[1].splitlines() if len(rows) > 1 else []:
        m = re.search(r"\|([^|\]]+)\]\]\s*$", line)
        if line.startswith("!") and m:
            cols.append(m.group(1).strip())
    for k, nm in enumerate(cols):
        names[str(k)] = nm
    for r, block in enumerate(rows[2:2 + len(cols)]):
        lines = [x for x in block.strip().splitlines() if x.startswith("|")]
        if len(lines) < 2:
            continue
        cells = lines[1].lstrip("|").split("||")
        for c, cell in enumerate(cells[:len(cols)]):
            m = re.search(r"(\d+):(\d+)", cell.rsplit("|", 1)[-1] if "[[" not in cell else cell)
            if m and c != r:
                games.append((str(r), str(c), int(m.group(1)), int(m.group(2))))
    return names, games


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(fc|fk|nk|sk|sv|kf|cd|ud|sc|afc|ac|as|tsv|vfl|club|cf|bk|ks|gks|1906|1921|1900|u21|utd|united|city|town)\b", " ", s)
    return re.sub(r"[^a-z0-9 ]", " ", s).strip()


# Nesine names the fuzzy match gets wrong or misses -> a word of the Wikipedia name (None = do not match)
ALIAS = {"R. Wien (Amt)": "Rapid II", "TNS": "New Saints", "Iğdır FK": "Iğdır", "Ümraniyespor": "Ümraniyespor",
         "Levy Bereg Kiev": "Livyi Bereh", "Floridsdorfer": "FAC", "Aalborg BK": "AaB", "Std. Nyonnis": "Nyon",
         "Slask Wroclaw": "Śląsk", "LKS Lodz": "ŁKS", "Auckland": None, "C. Glogow": "Chrobry",
         "Karvina": "Karviná", "A. Bielefeld": "Bielefeld", "Magdeburg": "Magdeburg", "Magdeburg II": "Magdeburg II",
         "Weiss Erfurt": "Erfurt", "Steinb. 1921": "Steinbach", "TSV S. Augsburg": "Schwaben Augsburg",
         "Union Berlin (K)": "Union Berlin", "B. Leverkusen (K)": "Leverkusen", "Pribram": "Příbram", "Usti Nad Labem": "Ústí"}


def match_team(nesine: str, names: dict[str, str]) -> str | None:
    """Wikipedia team code of a Nesine (often abbreviated) team name; None when unsure."""
    if nesine in ALIAS:
        want = ALIAS[nesine]
        hits = [c for c, nm in names.items() if want and want.lower() in nm.lower()]
        return hits[0] if len(hits) == 1 else None
    target = _norm(nesine)
    best, score = None, 0.0
    for code, nm in names.items():
        cand = _norm(nm)
        tok = {t for t in target.split() if len(t) > 2} & {t for t in cand.split() if len(t) > 2}
        sc = difflib.SequenceMatcher(None, target, cand).ratio() + 0.4 * bool(tok)
        if target and cand and (cand.startswith(target.split()[0]) or target.startswith(cand.split()[0])):
            sc += 0.2
        if sc > score:
            best, score = code, sc
    return best if score >= 0.75 else None


def team_games(code: str, names: dict[str, str], games: list[tuple]) -> list[dict]:
    """Games in derin_arastirma's oriented form; first half unknown (for = (None, goals))."""
    out = []
    for h, a, gh, ga in games:
        if code == h:
            out.append({"event": f"{h}_{a}", "date": "", "side": "home", "opp": names.get(a, a), "opp_id": a,
                        "for": (None, gh), "against": (None, ga)})
        elif code == a:
            out.append({"event": f"{h}_{a}", "date": "", "side": "away", "opp": names.get(h, h), "opp_id": h,
                        "for": (None, ga), "against": (None, gh)})
    return out


def leg_history(name: str, home_games: list[dict], away_games: list[dict]) -> dict:
    """Like derin_arastirma.leg_history, full time only: the home team's home games, the away team's away games."""
    def rate(games, side):
        res = []
        for g in games:
            if g["side"] != side:
                continue
            ft = (g["for"][1], g["against"][1]) if side == "home" else (g["against"][1], g["for"][1])
            try:  # half score unknown: settle with the two extreme half scores; a full-time bet gives the same answer
                lo, hi = dr.settle_selection(name, (0, 0), ft), dr.settle_selection(name, ft, ft)
                v = lo if lo == hi else None  # depends on the half: no half scores on Wikipedia
            except (ValueError, KeyError, TypeError):
                v = None
            if v is not None:
                res.append(v)
        return (sum(res) / len(res), len(res)) if res else (None, 0)
    h, nh = rate(home_games, "home")
    a, na = rate(away_games, "away")
    vals = [x for x in (h, a) if x is not None]
    return {"home_rate": h, "home_n": nh, "away_rate": a, "away_n": na, "mean": sum(vals) / len(vals) if vals else None}


def verdict(p: float | None, hist: dict) -> str:
    """The same standard as every other history source (21 Nov): derin_arastirma's thresholds and at least 6 home
    games of the home team and 6 away games of the away team."""
    return dr.verdict(p, hist)


def profile(games: list[dict]) -> dict:
    n = len(games)
    if not n:
        return {"n": 0}
    ft = lambda g: (g["for"][1], g["against"][1])  # noqa: E731
    w = sum(1 for g in games if ft(g)[0] > ft(g)[1])
    d = sum(1 for g in games if ft(g)[0] == ft(g)[1])
    return {"n": n, "ppg": (3 * w + d) / n, "gf": sum(ft(g)[0] for g in games) / n, "ga": sum(ft(g)[1] for g in games) / n,
            "btts": sum(1 for g in games if min(ft(g)) > 0) / n, "over25": sum(1 for g in games if sum(ft(g)) > 2) / n,
            "source": "Wikipedia sezon tablosu (yalnız maç sonu)"}


def season_for(league: str) -> tuple[str, dict, list] | None:
    for prefix, titles in SEASON.items():
        if league.startswith(prefix):
            for t in titles:
                w = wikitext(t)
                names, games = crosstable(w) if t.startswith("de:") else results_matrix(w)
                if games:
                    return t, names, games
            return None
    return None


def research(row: dict, m: dict) -> bool:
    """Fill a derin_tahminler row (no ESPN history) from Wikipedia; True when both teams were found."""
    s = season_for(row["league"])
    if not s:
        return False
    title, names, games = s
    hc, ac = match_team(m["home"], names), match_team(m["away"], names)
    if not hc or not ac or hc == ac:
        return False
    hg, ag = team_games(hc, names, games), team_games(ac, names, games)
    row["wiki"] = {"title": title, "home": names[hc], "away": names[ac]}
    row["games"], row["games_ft_only"] = {"home": hg, "away": ag}, True
    row["teams"].setdefault("home", {}).update(profile(hg))
    row["teams"].setdefault("away", {}).update(profile(ag))
    row["h2h"] = [f"sezon: {names[x[0]]} {x[2]}-{x[3]} {names[x[1]]}" for x in games if {x[0], x[1]} == {hc, ac}]
    for leg in row["legs"]:
        hist = leg_history(leg["name"], hg, ag)
        leg.update(hist)
        leg["verdict"] = verdict(leg.get("p"), hist)
    row["pick"] = dtah.choose(row["legs"])
    row["dropped"] = [x for x in row["legs"] if x["verdict"].startswith("⚠")]
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    args = ap.parse_args()
    out = dr.AREA / args.tarih
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    found, miss = 0, []
    for i, r in enumerate(rows):
        if r.get("espn"):
            continue
        if r.get("legs") and dr.find_espn_event(ms[str(r["code"])]):  # leagues added to LEAGUE_SLUGS later
            legs = [{**x, "label": x["label"], "coupons": []} for x in r["legs"]]
            again = dr.research_match(ms[str(r["code"])], legs)
            for x, old in zip(again["legs"], r["legs"]):
                x.update({k: old[k] for k in ("label", "market", "sel")})
            again["pick"], again["dropped"] = dtah.choose(again["legs"]), [x for x in again["legs"] if x["verdict"].startswith("⚠")]
            rows[i] = again
            continue
        r.setdefault("teams", {})
        if research(r, ms[str(r["code"])]):
            found += 1
        else:
            miss.append(f"{r['league']}: {r['match']}")
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out / "derin_tahminler.md").write_text(dtah.to_markdown(args.tarih, rows), encoding="utf-8")
    n = dtah.update_table(args.tarih, rows)
    print(f"Wikipedia: {found} maçta iki takımın sezon sonuçları bulundu; {len(miss)} maç bulunamadı; tablo {n} satır")
    for x in miss:
        print("  yok:", x)


if __name__ == "__main__":
    main()
