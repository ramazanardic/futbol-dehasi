"""Geniş maç arşivini kurar: açık/izinli kaynaklar -> tekrarsız sıkıştırılmış tablolar (data/arsiv/).

Ham veri repoya girmez; ``--ham`` klasörü (varsayılan /workspace/arsiv_ham) şunları içerir:
  of/<repo>            openfootball depoları (git clone --depth 1)       CC0
  fc/<repo>            footballcsv depoları + martj42 + jfjelstul          CC0 / CC0 / CC BY-SA 4.0
  fdold/<sezon>_<div>.csv   football-data.co.uk 1993/94–1999/00          robots izinli, ücretsiz araştırma verisi
  espn/<yıl>-<ay>.jsonl.gz  scripts/arsiv_espn_tara.py çıktısı            herkese açık scoreboard (yalnız sonuç satırı)
  wiki/*.jsonl.gz           scripts/arsiv_wiki_tara.py çıktısı (varsa)    Wikipedia, CC BY-SA 4.0
Çıktılar: maclar.csv.gz, yarismalar.csv, takimlar.csv.gz, oyuncular.csv.gz, oyuncu_kunye.csv.gz, ozet.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data import arsiv as A

RANK = {"football-data": 0, "openfootball": 1, "footballcsv": 2, "jfjelstul/worldcup": 3, "martj42": 4, "wikipedia": 5, "espn": 6}
OF_SKIP_DIRS = {"players", "clubs", "leagues", "internationals", "internationals.more", "world.more", ".git"}
OF_NOISE = ("rsssf", "planetworldcup", "rapidarchiv.at", "austriasoccer.at", "attic", "more")


def of_key(p: Path, root: Path) -> str:
    rel = p.relative_to(root).parts
    stem = re.sub(r"^\d{4}([-_/]\d{2,4})?[-_.]?", "", p.stem) or p.stem
    mid = [x for x in rel[1:-1] if not re.match(r"^\d{4}", x)]
    return "/".join([rel[0], *mid, stem])


def load_openfootball(root: Path) -> list[dict]:
    rows = []
    for p in sorted(root.rglob("*.txt")):
        rel = p.relative_to(root).parts
        if rel[0] in OF_SKIP_DIRS or p.name.startswith(".") or p.stem.lower() in ("readme", "notes") or any(x in OF_NOISE for x in rel):
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        key = of_key(p, root)
        for r in A.parse_football_txt(txt, str(p), key):
            rows.append(r)  # noqa: PERF402
    return rows


def load_footballcsv(root: Path) -> list[dict]:
    rows = []
    for repo in sorted(root.iterdir()):
        if not repo.is_dir() or repo.name in ("worldcup", "international_results", "cache.footballsquads"):
            continue
        for p in sorted(repo.rglob("*.csv")):
            m = re.search(r"/(\d{4}(?:-\d{2})?)/([^/]+)\.csv$", str(p))
            if not m:
                continue
            sez = m[1] if "-" not in m[1] else f"{m[1][:4]}/{m[1][-2:]}"
            rows += A.parse_footballcsv(p.read_text(encoding="utf-8", errors="ignore"), sez, f"{repo.name}/{m[2]}")
    return rows


def load_fdold(root: Path) -> list[dict]:
    rows = []
    for p in sorted(root.glob("*.csv")):
        s, d = p.stem.split("_")
        y = int(s[:2])
        y = 1900 + y if y >= 90 else 2000 + y
        rows += A.parse_football_data(p.read_text(encoding="latin-1"), f"{y}/{str(y + 1)[2:]}", f"fd/{d}")
    return rows


def load_espn(root: Path) -> list[dict]:
    rows = []
    lg_file = ROOT / "data" / "arsiv" / "espn_ligler.csv"
    leagues = {r["id"]: (r["slug"], r["ad"]) for r in csv.DictReader(lg_file.open(encoding="utf-8"))} if lg_file.exists() else {}
    for f in sorted(root.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as g:
            rows += A.espn_rows((json.loads(line) for line in g), leagues)
    return rows


def load_wiki(root: Path) -> tuple[list[dict], list[dict]]:
    m, p = [], []
    for f in sorted(root.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as g:
            for line in g:
                r = json.loads(line)
                (m if r.pop("_t") == "mac" else p).append(r)
    return m, p


def existing_keys(repo: Path) -> set:
    """Repodaki mevcut arşiv (data/matches.csv, data/international_results.csv): tekrar sayılacak anahtarlar."""
    import datetime as dt

    keys = set()
    with (repo / "data" / "matches.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["FTHome"] == "" or r["FTAway"] == "" or r.get("Source") == "espn":  # ESPN dolgusu kaynak sayılmaz
                continue
            keys.add((r["MatchDate"], A.team_key(r["HomeTeam"])[:8], A.team_key(r["AwayTeam"])[:8], (int(float(r["FTHome"])), int(float(r["FTAway"])))))
    with (repo / "data" / "international_results.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["home_score"] in ("", "NA"):
                continue
            keys.add((r["date"], A.team_key(r["home_team"])[:8], A.team_key(r["away_team"])[:8], (int(r["home_score"]), int(r["away_score"]))))
    ext = set()
    for d, h, a, sc in keys:
        day = dt.date.fromisoformat(d)
        for k in (-1, 0, 1):
            ext.add(((day + dt.timedelta(days=k)).isoformat(), h, a, sc))
    return ext


def write_gz(path: Path, cols: list[str], rows: list[dict]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="", compresslevel=9) as g:
        w = csv.DictWriter(g, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r[k]) for k in cols})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ham", type=Path, default=Path("/workspace/arsiv_ham"))
    ap.add_argument("--cikti", type=Path, default=ROOT / "data" / "arsiv")
    a = ap.parse_args()
    ham, out = a.ham, a.cikti
    out.mkdir(parents=True, exist_ok=True)
    stats: dict = {"kaynak_ham_satir": {}}
    rows: list[dict] = []
    players: list[dict] = []

    def add(name, part):
        stats["kaynak_ham_satir"][name] = len(part)
        rows.extend(part)

    add("openfootball", load_openfootball(ham / "of"))
    add("footballcsv", load_footballcsv(ham / "fc"))
    add("football-data(1993-2000)", load_fdold(ham / "fdold"))
    fc = ham / "fc"
    # martj42: milli maçlar + gol atanlar
    res_text = (fc / "international_results" / "results.csv").read_text(encoding="utf-8")
    comp_of: dict[tuple, str] = {}
    mm = []
    for r in csv.DictReader(res_text.splitlines()):
        comp_of[(r["date"], r["home_team"], r["away_team"])] = r["tournament"]
        if r["home_score"] in ("", "NA"):
            continue
        mm.append({"tarih": r["date"], "sezon": r["date"][:4], "yarisma": f"milli/{r['tournament']}", "ev": r["home_team"],
                   "dep": r["away_team"], "hg": int(r["home_score"]), "ag": int(r["away_score"]), "iy_ev": None, "iy_dep": None,
                   "durum": "FT", "ham_skor": None, "kaynak": "martj42"})
    add("martj42", mm)
    players += A.goalscorer_rows((fc / "international_results" / "goalscorers.csv").read_text(encoding="utf-8"), comp_of)
    wc = fc / "worldcup" / "data-csv"
    add("jfjelstul/worldcup", A.worldcup_match_rows((wc / "matches.csv").read_text(encoding="utf-8")))
    players += A.worldcup_player_rows(*(((wc / f"{n}.csv").read_text(encoding="utf-8")) for n in ("player_appearances", "goals", "bookings")))
    add("espn", load_espn(ham / "espn"))
    if (ham / "wiki").exists():
        wm, wp = load_wiki(ham / "wiki")
        add("wikipedia", wm)
        players += wp

    seen_extra = existing_keys(ROOT)
    uniq, dd = A.dedupe(rows, RANK, seen_extra)
    uniq.sort(key=lambda r: (r["tarih"] or r["sezon"], r["yarisma"], r["ev"]))
    for r in uniq:
        r["tur"] = A.tur_of(r["yarisma"])
        if r["iy_ev"] is not None and r["hg"] is not None and (r["iy_ev"] > r["hg"] or r["iy_dep"] > r["ag"]):
            r["iy_ev"] = r["iy_dep"] = None  # İY skoru final skoru aşamaz: kaynak hatası, İY atılır
    stats["tekrar_ayiklanan"] = dd
    write_gz(out / "maclar.csv.gz", A.COLS, uniq)

    # yarışma kataloğu
    cat: dict[str, dict] = {}
    for r in uniq:
        c = cat.setdefault(r["yarisma"], {"yarisma": r["yarisma"], "tur": r["tur"], "kaynak": r["kaynak"], "sezonlar": set(), "mac": 0, "takimlar": set()})
        c["sezonlar"].add(r["sezon"])
        c["mac"] += 1
        c["takimlar"].update((A.team_key(r["ev"]), A.team_key(r["dep"])))
    cat_rows = [{"yarisma": c["yarisma"], "tur": c["tur"], "kaynak": c["kaynak"], "ilk_sezon": min(c["sezonlar"]), "son_sezon": max(c["sezonlar"]),
                 "sezon_sayisi": len(c["sezonlar"]), "mac": c["mac"], "takim_sayisi": len(c["takimlar"])} for c in cat.values()]
    cat_rows.sort(key=lambda r: (r["tur"], r["yarisma"]))
    with (out / "yarismalar.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(cat_rows[0]))
        w.writeheader()
        w.writerows(cat_rows)

    # takım kataloğu
    teams: dict[str, dict] = {}
    for r in uniq:
        for side in ("ev", "dep"):
            k = A.team_key(r[side])
            t = teams.setdefault(k, {"anahtar": k, "adlar": collections.Counter(), "yarismalar": set(), "ilk": "9999", "son": "", "mac": 0})
            t["adlar"][r[side]] += 1
            t["yarismalar"].add(r["yarisma"])
            d = r["tarih"] or r["sezon"]
            t["ilk"], t["son"] = min(t["ilk"], d), max(t["son"], d)
            t["mac"] += 1
    team_rows = [{"takim": t["adlar"].most_common(1)[0][0], "anahtar": k, "yarisma_sayisi": len(t["yarismalar"]), "ilk": t["ilk"], "son": t["son"],
                  "mac": t["mac"]} for k, t in teams.items()]
    team_rows.sort(key=lambda r: -r["mac"])
    write_gz(out / "takimlar.csv.gz", ["takim", "anahtar", "yarisma_sayisi", "ilk", "son", "mac"], team_rows)

    # oyuncular
    players.sort(key=lambda r: (r["yarisma"], r["sezon"], -(r["gol"] or 0), r["oyuncu"]))
    write_gz(out / "oyuncular.csv.gz", A.PLAYER_COLS, players)
    bios = []
    for p in sorted((ham / "of" / "players").rglob("*.txt")):
        if ".git" in p.parts or "attic" in p.parts:
            continue
        bios += A.bio_rows(p.read_text(encoding="utf-8", errors="ignore"), "openfootball/players")
    write_gz(out / "oyuncu_kunye.csv.gz", ["oyuncu", "takim", "mevki", "boy_m", "dogum", "dogum_yeri", "kaynak"], bios)

    yrs = sorted({(r["tarih"] or r["sezon"])[:4] for r in uniq})
    stats.update({"mac": len(uniq), "yarisma": len(cat_rows), "takim": len(team_rows), "oyuncu_satiri": len(players), "oyuncu_kunye": len(bios),
                  "yil_araligi": [yrs[0], yrs[-1]], "yil_sayisi": len(yrs), "turlere_gore_mac": dict(collections.Counter(r["tur"] for r in uniq)),
                  "turlere_gore_yarisma": dict(collections.Counter(c["tur"] for c in cat_rows)),
                  "kaynaga_gore_mac": dict(collections.Counter(r["kaynak"] for r in uniq)),
                  "iy_skoru_olan_mac": sum(1 for r in uniq if r["iy_ev"] is not None),
                  "yarisma_sezon_cifti": len({(r["yarisma"], r["sezon"]) for r in uniq}),
                  "tarihsiz_mac": sum(1 for r in uniq if not r["tarih"]),
                  "oyuncu_satiri_kaynaga_gore": dict(collections.Counter(r["kaynak"] for r in players))})
    (out / "ozet.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    for f in sorted(out.iterdir()):
        print(f.name, round(f.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
