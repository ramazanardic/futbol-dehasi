"""Geniş maç arşivi: açık/izinli kaynaklardan ayrıştırıcılar, ortak şema, tekrar ayıklama.

Kaynaklar ve lisansları (data/arsiv/BENIOKU.md): openfootball (CC0), footballcsv (CC0), martj42/international_results (CC0),
football-data.co.uk (robots izinli, ücretsiz araştırma verisi), ESPN herkese açık scoreboard (yalnız sonuç satırı),
jfjelstul/worldcup (CC BY-SA 4.0, atıf). Ham dosyalar repoya konmaz; ``scripts/arsiv_kur.py`` sıkıştırılmış tablo üretir.

Ortak maç satırı: tarih (ISO; yalnız sezon biliniyorsa boş), sezon, yarisma (anahtar), ev, dep, hg, ag (90 dk; bilinmiyorsa
boş), iy_ev, iy_dep, durum (FT/AET/PEN), ham_skor (yalnız AET/PEN satırlarında), kaynak.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from collections.abc import Iterable

from quantfoot.data.oddsmath import _norm_team

MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
COLS = ["tarih", "sezon", "yarisma", "tur", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep", "durum", "ham_skor", "kaynak"]

_DATE = re.compile(r"^\s*\[?(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[ ,/]+)?(?P<mon>[A-Z][a-z]{2})[a-z]*[ /]+(?P<day>\d{1,2})(?:[ ,]+(?P<year>\d{4}))?\]?(?:\s+\d{1,2}[:.]\d{2}.*|\s*\|.*)?\s*$")
_DMY = re.compile(r"^\s*(?P<day>\d{1,2})\.(?P<mon>\d{1,2})\.(?P<year>\d{4})?\s*$")
_ISO = re.compile(r"^\s*\[?(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\]?\s*$")
_P2 = re.compile(r"^(?P<t1>.+?)\s+v\s+(?P<t2>.+?)\s+(?P<rest>\d+-\d+(?:\s.*)?)$")
_P3 = re.compile(r"^(?P<t1>[^\d(@].*?)\s+(?P<rest>\d+-\d+(?:\s*\((?:\d+-\d+|aet[^)]*)\))?(?:\s+(?:a\.e\.t\.|pen\.))*)\s+(?P<t2>[^\s(@].*?)(?:\s+@.*)?$")
_P1 = re.compile(r"^(?P<t1>.+?)\s{2,}(?P<rest>\d+-\d+(?:\s|$)[^A-Za-z]*(?:a\.e\.t\.|aet|pen\.)?[^A-Za-z@]*(?:\([^)]*\))?[^A-Za-z@]*(?:pen\.?[^A-Za-z@]*)?(?:a\.e\.t\.[^A-Za-z@]*(?:\([^)]*\))?)?)\s+(?P<t2>[^\s\d(].*?)(?:\s+@.*)?$")
_INLINE = re.compile(r"^\s*(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*[ ,]+)?(?:(?P<mon>[A-Z][a-z]{2,8})[ /]+(?P<day>\d{1,2})|(?P<day2>\d{1,2})[ /]+(?P<mon2>[A-Z][a-z]{2,8}))"
                     r"(?:[ ,]+(?P<year>\d{4}))?(?:\s+\d{1,2}[:.]\d{2})?(?=\s{2,}|\s+\d{1,2}[:.]\d{2})")
_TIME = re.compile(r"^\s*(?:\d{1,2}[:.]\d{2}|\(\d+\))\s+")
_COUNTRY = re.compile(r"\s*(?:›\s*[A-Z]{2,3}\s*)?\((?:[A-Z]{3}|[A-Z]{2}|\d+)\)\s*$|\s*›\s*[A-Z]{2,3}(?:\s*\(\d+\))?\s*$")


def _clean_team(t: str) -> str:
    t = _COUNTRY.sub("", t.strip())
    return re.sub(r"\s{2,}", " ", t).strip(" @")


def parse_score(rest: str) -> dict | None:
    """'2-1 (1-0)', '2-2 aet (2-2, 1-0), 6-5 pen', '5-6 pen. 1-1 a.e.t. (1-1, 0-1)', '2-4 a.e.t.', '4-3 pen.' -> alanlar."""
    m = re.match(r"(\d+)-(\d+)", rest)
    if not m:
        return None
    a, b = int(m[1]), int(m[2])
    low = rest.lower()
    paren = re.findall(r"\((\d+)-(\d+)(?:,\s*(\d+)-(\d+))?\)", rest)
    et = "a.e.t" in low or re.search(r"\baet\b", low)
    pen = re.search(r"pen", low)
    out = {"hg": a, "ag": b, "iy_ev": None, "iy_dep": None, "durum": "FT", "ham_skor": None}
    if et or pen:
        out["durum"] = "PEN" if pen else "AET"
        out["ham_skor"] = re.sub(r"\s+", " ", rest.strip())
        if paren and paren[0][2] != "":  # (90 dk skoru, İY)
            out["hg"], out["ag"] = int(paren[0][0]), int(paren[0][1])
            out["iy_ev"], out["iy_dep"] = int(paren[0][2]), int(paren[0][3])
        elif paren:
            out["hg"], out["ag"] = (None, None)
            out["iy_ev"], out["iy_dep"] = int(paren[0][0]), int(paren[0][1])
        else:
            out["hg"], out["ag"] = None, None
    elif paren:
        out["iy_ev"], out["iy_dep"] = int(paren[0][0]), int(paren[0][1])
    return out


def season_of(text: str) -> tuple[str | None, int | None, bool]:
    """Başlık/yoldaki sezon: ('2017/18', başlangıç yılı, bölünmüş sezon mu)."""
    m = re.search(r"(\d{4})[/-](\d{2,4})", text)
    if m:
        y = int(m[1])
        return f"{y}/{str(y + 1)[2:]}" if int(m[2][-2:]) == (y + 1) % 100 else f"{y}/{m[2][-2:]}", y, True
    m = re.search(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)", text)
    return (m[1], int(m[1]), False) if m else (None, None, False)


def parse_football_txt(text: str, path_hint: str = "", yarisma: str = "", kaynak: str = "openfootball") -> list[dict]:
    """Football.TXT biçimi (openfootball). Skoru olmayan (oynanmamış) satırlar atlanır."""
    sezon, y0, split = (None, None, False)
    for line in text.splitlines()[:6]:
        if line.startswith("="):
            sezon, y0, split = season_of(line)
            break
    if sezon is None:
        sezon, y0, split = season_of(path_hint)
    start_mon = 7
    hm = re.search(r"^#\s*Dates?\s+(?:[A-Za-z]{3}\s+)?(?P<m1>[A-Z][a-z]{2})[a-z]*\s+\d{1,2}\s+(?P<y1>\d{4})\s*-\s*(?:[A-Za-z]{3}\s+)?[A-Z][a-z]{2}[a-z]*\s+\d{1,2}\s+(?P<y2>\d{4})",
                   text[:600], re.MULTILINE)
    if hm and hm["m1"].lower() in MONTHS:  # başlık tarih aralığı varsa sezon yılı ondan okunur (başlıktaki yıl yanıltabilir)
        y0, split, start_mon = int(hm["y1"]), int(hm["y2"]) > int(hm["y1"]), MONTHS[hm["m1"].lower()]
    rows: list[dict] = []
    cur: dt.date | None = None
    last_month = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith(("#", "=", "▪", "»", "Group", "Matchday", "|")):
            continue
        mi = _ISO.match(line)
        if mi:
            cur = dt.date(int(mi["y"]), int(mi["m"]), int(mi["d"]))
            continue
        mdm = _DMY.match(line)
        if mdm and y0 is not None:
            mon = int(mdm["mon"])
            yr = int(mdm["year"]) if mdm["year"] else ((y0 if mon >= start_mon else y0 + 1) if split else y0)
            try:
                cur = dt.date(yr, mon, int(mdm["day"]))
            except ValueError:
                cur = None
            continue
        md = _DATE.match(line)
        if md and md["mon"].lower() in MONTHS and not re.search(r"\d+-\d+", line):
            mon = MONTHS[md["mon"].lower()]
            if md["year"]:
                yr = int(md["year"])
            elif y0 is None:
                yr = None
            else:
                yr = (y0 if mon >= start_mon else y0 + 1) if split else y0
                if not split and last_month and mon < last_month - 6:
                    yr = y0
            try:
                cur = dt.date(yr, mon, int(md["day"])) if yr else None
            except ValueError:
                cur = None
            last_month = mon
            continue
        body = line
        mn = _INLINE.match(line)
        if mn and (mn["mon"] or mn["mon2"]).lower()[:3] in MONTHS:  # 'Fri Jun 11 16:00  A  1-0  B' ya da '16 June   A  1-0  B'
            mon = MONTHS[(mn["mon"] or mn["mon2"]).lower()[:3]]
            day = int(mn["day"] or mn["day2"])
            if mn["year"]:
                yr = int(mn["year"])
            elif y0 is None:
                yr = None
            else:
                yr = (y0 if mon >= start_mon else y0 + 1) if split else y0
            try:
                cur = dt.date(yr, mon, day) if yr else cur
            except ValueError:
                pass
            body = line[mn.end():]
        body = _TIME.sub("", body, count=1).strip()
        m = _P2.match(body) or _P1.match(body) or _P3.match(body)
        if not m:
            continue
        sc = parse_score(m["rest"])
        if not sc:
            continue
        rows.append({"tarih": cur.isoformat() if cur else "", "sezon": sezon or "", "yarisma": yarisma,
                     "ev": _clean_team(m["t1"]), "dep": _clean_team(m["t2"]), **sc, "kaynak": kaynak})
    return rows


def _dash(s: str) -> str:
    return s.replace("–", "-").replace("—", "-").replace("−", "-")


def parse_footballcsv(text: str, sezon: str, yarisma: str, kaynak: str = "footballcsv") -> list[dict]:
    """footballcsv: Round,Date,Team 1,FT,[HT,]Team 2 (tarih 'Sat Aug 15 1992' ya da ISO)."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        ft = _dash((r.get("FT") or "").strip())
        m = re.match(r"^(\d+)-(\d+)$", ft)
        if not m:
            continue
        d = re.sub(r"\s*\(W\d+\)$", "", re.sub(r"^\((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\)\s*", "", (r.get("Date") or "").strip()))
        iso = ""
        for f in ("%a %b %d %Y", "%Y-%m-%d", "%d %b %Y", "%a %b/%d %Y", "%a %d %b %Y"):
            try:
                iso = dt.datetime.strptime(d, f).date().isoformat()
                break
            except ValueError:
                continue
        ht = re.match(r"^(\d+)-(\d+)$", _dash((r.get("HT") or "").strip()))
        et, pk = (r.get("ET") or "").strip(), (r.get("P") or "").strip()
        out.append({"tarih": iso, "sezon": sezon, "yarisma": yarisma, "ev": _clean_team(r["Team 1"]), "dep": _clean_team(r["Team 2"]),
                    "hg": int(m[1]), "ag": int(m[2]), "iy_ev": int(ht[1]) if ht else None, "iy_dep": int(ht[2]) if ht else None,
                    "durum": "PEN" if pk else "AET" if et else "FT", "ham_skor": f"ET {et} P {pk}".strip() if (et or pk) else None,
                    "kaynak": kaynak})
    return out


def parse_football_data(text: str, sezon: str, yarisma: str) -> list[dict]:
    """football-data.co.uk mmz4281 CSV (Date dd/mm/yy|yyyy, HomeTeam, AwayTeam, FTHG, FTAG, HTHG, HTAG)."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        h, a = (r.get("HomeTeam") or "").strip(), (r.get("AwayTeam") or "").strip()
        try:
            hg, ag = int(float(r["FTHG"])), int(float(r["FTAG"]))
        except (KeyError, ValueError, TypeError):
            continue
        d = (r.get("Date") or "").strip()
        iso = ""
        for f in ("%d/%m/%y", "%d/%m/%Y"):
            try:
                iso = dt.datetime.strptime(d, f).date().isoformat()
                break
            except ValueError:
                continue
        if not (h and a and iso):
            continue

        def _i(k, r=r):
            try:
                return int(float(r[k]))
            except (KeyError, ValueError, TypeError):
                return None

        out.append({"tarih": iso, "sezon": sezon, "yarisma": yarisma, "ev": h, "dep": a, "hg": hg, "ag": ag,
                    "iy_ev": _i("HTHG"), "iy_dep": _i("HTAG"), "durum": "FT", "ham_skor": None, "kaynak": "football-data"})
    return out


WOMEN = re.compile(r"(\.w\.|\.wwc|women|ladies|nwsl|ncaa|\bw\b)", re.IGNORECASE)


def espn_rows(compact_rows: Iterable[dict], leagues: dict[str, tuple[str, str]] | None = None) -> list[dict]:
    """``scripts/arsiv_espn_tara.py`` satırları -> ortak şema. ``leagues``: {ESPN lig kimliği: (slug, ad)} (espn_ligler.csv).
    Kadın ligleri atılır. Uzatma/penaltılı maçta ESPN skoru son skordur (90 dk değil): hg/ag boş, ham_skor dolu."""
    leagues = leagues or {}
    out = []
    for r in compact_rows:
        slug, name = leagues.get(str(r["l"]), ("", ""))
        if r["hg"] is None or r["ag"] is None or r["hg"] < 0 or r["ag"] < 0:
            continue  # ESPN'de nadir bozuk skor (negatif): atılır
        if WOMEN.search(f"{slug} {name} {r['s']}"):
            continue
        m = re.match(r"^(\d{4})-?(?:(?:\d{2})?(\d{2}))?-(.*)$", r["s"])  # '2014-2015-…', '20142015-…', '2014-15-…', '2014-…'
        yr, yy, sname = (m[1], m[2], m[3]) if m else ("", None, r["s"])
        sezon = f"{yr}/{yy}" if yy else (yr or r["d"][:4])  # sezon adı yıl taşımıyorsa maç tarihinin yılı
        st = (r.get("st") or "FT").upper()
        durum = "PEN" if "PEN" in st else "AET" if "AET" in st else "FT"
        extra = durum != "FT"
        key = f"espn/{slug}" if slug else f"espn/{r['l']}/{sname}"
        out.append({"tarih": r["d"], "sezon": sezon, "yarisma": key, "ev": r["h"], "dep": r["a"],
                    "hg": None if extra else r["hg"], "ag": None if extra else r["ag"], "iy_ev": None, "iy_dep": None,
                    "durum": durum, "ham_skor": f"{r['hg']}-{r['ag']} {st}" if extra else None, "kaynak": "espn"})
    return out


KITA = re.compile(r"(champions(?!hip)|europa|conference|libertadores|sudamericana|cup-winners|club-world|afc-champions|caf-champions|"
                  r"concacaf-champions|cwc|uefa|copa-lib|recopa|supercopa-sud|fifa-club|intercontinental)", re.IGNORECASE)
MILLI = re.compile(r"(world-cup|worldcup|fifa-world|euro(?:pean)?-championship|uefa-euro|copa-america|gold-cup|nations-league|"
                   r"asian-cup|african-cup|africa-cup|cup-of-nations|olympic|friendl|international|qualif|confederations)", re.IGNORECASE)
KUPA = re.compile(r"(cup|\.fa\b|pokal|coupe|copa|coppa|beker|taca|taça|supercup|super-cup|trophy|shield|fa-)", re.IGNORECASE)


MILLI_SLUG = re.compile(r"(fifa\.(world|wcq|friendly|olympics|concacaf\.olympicsq|conmebol\.olympicsq)|worldq|asian\.cup|afc\.cupq|afc\.saff|"
                        r"caf\.(nations|championship|cosafa)|concacaf\.(gold|nations|u23)|conmebol\.america|uefa\.(euro(?!pa)|nations)|finalissima|nonfifa)", re.IGNORECASE)


def tur_of(key: str) -> str:
    """Yarışma anahtarı -> 'milli' (milli takım turnuvası/elemesi), 'kita_kulup' (kıtasal kulüp), 'kupa' (ulusal kupa),
    'hazirlik' (kulüp hazırlık), 'lig'."""
    k = key.lower()
    if re.search(r"club\.friendly|friendly\.(?!w)|emirates_cup", k) and "fifa.friendly" not in k:
        return "hazirlik"  # kulüp hazırlık maçları
    if k.startswith("milli/") or MILLI_SLUG.search(k):
        return "milli"
    if KITA.search(k) and not re.search(r"national|u-?\d\d|youth|women", k):
        return "kita_kulup"
    if MILLI.search(k):
        return "milli"
    if KUPA.search(k):
        return "kupa"
    return "lig"


def team_key(name: str) -> str:
    return _norm_team(name)


def dedupe(rows: Iterable[dict], rank: dict[str, int], seen_extra: set | None = None) -> tuple[list[dict], dict]:
    """Aynı maç (±1 gün, normalize takımlar, 90 dk skoru ya da ham skor) tek satıra iner; kaynak önceliği ``rank`` (küçük = öncelikli).
    Tarihi olmayan satırlar (sezon + takımlar + skor) anahtarıyla ayıklanır. Dönüş: (satırlar, {'tekrar': n, 'dis_tekrar': n})."""
    rows = sorted(rows, key=lambda r: (not r["tarih"], rank.get(r["kaynak"], 9), r["tarih"]))  # tarihsizler en sona: tarihli kayıt öncelikli
    seen: dict[tuple, bool] = {}
    out, dup, ext = [], 0, 0
    for r in rows:
        h, a = team_key(r["ev"])[:8], team_key(r["dep"])[:8]
        sc = (r["hg"], r["ag"]) if r["hg"] is not None else (r["ham_skor"] or "")[:5]
        if r["tarih"]:
            d = dt.date.fromisoformat(r["tarih"])
            keys = [((d + dt.timedelta(days=k)).isoformat(), h, a, sc) for k in (-1, 0, 1)]
            mine = keys[1]
        else:
            keys = mine = (r["sezon"], h, a, sc)
            keys = [mine]
        if seen_extra is not None and r["tarih"] and mine in seen_extra:
            ext += 1
            continue
        if any(k in seen for k in keys):
            dup += 1
            continue
        seen[mine] = True
        if r["tarih"]:
            seen[(r["sezon"], h, a, sc)] = True  # tarihsiz (Wikipedia matrisi) satırlar aynı sezon+takım+skorla eşleşip ayıklanır
        out.append(r)
    return out, {"tekrar": dup, "dis_tekrar": ext}


# ---------------------------------------------------------------- oyuncu düzeyi
PLAYER_COLS = ["oyuncu", "takim", "yarisma", "sezon", "mac", "ilk11", "gol", "penalti_gol", "kendi_kalesine", "sari", "kirmizi", "kaynak"]


def goalscorer_rows(goals_csv: str, results: dict[tuple, str]) -> list[dict]:
    """martj42 goalscorers.csv -> (oyuncu, takım, turnuva, yıl) başına gol toplamı. ``results``: {(tarih, ev, dep): turnuva}.
    Kendi kalesine gol (own_goal=TRUE) golü atan oyuncunun değil kaleye ekleneni takımın hanesine yazılır: ayrı sütun."""
    agg: dict[tuple, dict] = {}
    for r in csv.DictReader(io.StringIO(goals_csv)):
        comp = results.get((r["date"], r["home_team"], r["away_team"]), "bilinmiyor")
        key = (r["scorer"], r["team"], f"milli/{comp}", r["date"][:4])
        x = agg.setdefault(key, {"oyuncu": r["scorer"], "takim": r["team"], "yarisma": f"milli/{comp}", "sezon": r["date"][:4],
                                 "mac": 0, "ilk11": None, "gol": 0, "penalti_gol": 0, "kendi_kalesine": 0, "sari": None, "kirmizi": None,
                                 "kaynak": "martj42", "_m": set()})
        x["_m"].add((r["date"], r["home_team"], r["away_team"]))
        if r["own_goal"].upper() == "TRUE":
            x["kendi_kalesine"] += 1
        else:
            x["gol"] += 1
            if r["penalty"].upper() == "TRUE":
                x["penalti_gol"] += 1
    out = []
    for x in agg.values():
        x["mac"] = len(x.pop("_m"))
        out.append(x)
    return out


def worldcup_player_rows(appearances: str, goals: str, bookings: str) -> list[dict]:
    """jfjelstul/worldcup (CC BY-SA 4.0) -> turnuva + oyuncu + takım toplamları (maç, ilk 11, gol, penaltı, kendi kalesine, kart)."""
    agg: dict[tuple, dict] = {}

    def row(r):
        name = f"{r['given_name']} {r['family_name']}".replace("not applicable", "").strip()
        key = (r["player_id"], r["team_name"], r["tournament_name"])
        return agg.setdefault(key, {"oyuncu": name, "takim": r["team_name"], "yarisma": f"milli/{r['tournament_name']}",
                                     "sezon": r["tournament_name"][:4], "mac": 0, "ilk11": 0, "gol": 0, "penalti_gol": 0,
                                     "kendi_kalesine": 0, "sari": 0, "kirmizi": 0, "kaynak": "jfjelstul/worldcup"})

    for r in csv.DictReader(io.StringIO(appearances)):
        x = row(r)
        x["mac"] += 1
        x["ilk11"] += int(r["starter"])
    for r in csv.DictReader(io.StringIO(goals)):
        x = row({**r, "team_name": r["player_team_name"]})
        if r["own_goal"] == "1":
            x["kendi_kalesine"] += 1
        else:
            x["gol"] += 1
            x["penalti_gol"] += int(r["penalty"])
    for r in csv.DictReader(io.StringIO(bookings)):
        x = row(r)
        x["sari"] += int(r["yellow_card"])
        x["kirmizi"] += int(r["red_card"]) + int(r["second_yellow_card"])
    return list(agg.values())


def worldcup_match_rows(matches: str) -> list[dict]:
    out = []
    for r in csv.DictReader(io.StringIO(matches)):
        et, pk = r["extra_time"] == "1", r["penalty_shootout"] == "1"
        durum = "PEN" if pk else "AET" if et else "FT"
        sc = f"{r['home_team_score']}-{r['away_team_score']}"
        out.append({"tarih": r["match_date"], "sezon": r["tournament_name"][:4], "yarisma": f"milli/{r['tournament_name']}",
                    "ev": r["home_team_name"], "dep": r["away_team_name"],
                    "hg": None if durum != "FT" else int(r["home_team_score"]), "ag": None if durum != "FT" else int(r["away_team_score"]),
                    "iy_ev": None, "iy_dep": None, "durum": durum, "ham_skor": sc if durum != "FT" else None,
                    "kaynak": "jfjelstul/worldcup"})
    return out


def bio_rows(text: str, source: str) -> list[dict]:
    """openfootball/players: 'Ad Soyad,  F,  1.75 m,  b. 18 Jun 2007 @ Hebburn' (bölüm başlığı '=  Ülke')."""
    out, section = [], ""
    for line in text.splitlines():
        if line.startswith("=") and line.strip("= ").strip():
            section = line.strip("= ").strip()
            continue
        m = re.match(r"^(?P<ad>[^,#=]+?),\s+(?P<poz>[A-Z]|-)\s*,\s+(?P<boy>[\d.]+ m|-)\s*,\s+b\. (?P<dog>[^@\[]+?)(?:\s*@\s*(?P<yer>[^\[#]+?))?\s*(?:\[.*)?$", line.strip())
        if m:
            boy = m["boy"].replace(" m", "")
            out.append({"oyuncu": m["ad"].strip(), "takim": section, "mevki": m["poz"] if m["poz"] != "-" else "",
                        "boy_m": boy if boy != "-" else "", "dogum": m["dog"].strip(), "dogum_yeri": (m["yer"] or "").strip(),
                        "kaynak": source})
    return out


# ---------------------------------------------------------------- Wikipedia sezon sayfaları (sonuç matrisi + gol krallığı)
def _abbr_match(abbr: str, teams: list[str]) -> str | None:
    a = re.sub(r"[^A-Za-z]", "", abbr).lower()
    if not a:
        return None
    cands = [t for t in teams if re.sub(r"[^a-z]", "", _norm_team(t).replace(" ", "")).startswith(a)]
    if len(cands) == 1:
        return cands[0]
    ini = [t for t in teams if "".join(w[0] for w in re.findall(r"[A-Za-zÀ-ÿ]+", t)).lower().startswith(a)]
    if len(ini) == 1:
        return ini[0]
    pre = [t for t in teams if re.sub(r"[^a-z]", "", t.lower()).startswith(a[:3])]
    return pre[0] if len(pre) == 1 else None


def parse_wiki_season(html: str) -> dict:
    """Wikipedia sezon sayfası HTML -> {'maclar': [(ev, dep, hg, ag)], 'golculer': [(oyuncu, takim, gol)], 'takimlar': [...]}.
    Matris: 'Home \\ Away' başlıklı kare tablo; satır etiketi kısaltmaysa puan durumu tablosundaki takım adlarına eşlenir.
    Eşlenemeyen matris atlanır (uydurma yok)."""
    import pandas as pd

    out: dict = {"maclar": [], "golculer": [], "takimlar": []}
    try:
        tabs = pd.read_html(io.StringIO(html))
    except (ValueError, ImportError):
        return out

    def col(t, name):
        cols = [c for c in t.columns]
        return next((c for c in cols if str(c).lower() == name), None) or next((c for c in cols if str(c).lower().startswith(name)), None)

    for t in tabs:
        t.columns = [re.sub(r"\[[^\]]*\]|\s+", " ", " ".join(map(str, c)) if isinstance(c, tuple) else str(c)).strip() for c in t.columns]
        if not out["takimlar"] and col(t, "team") is not None and col(t, "pts") is not None and col(t, "pos") is not None:
            out["takimlar"] = [re.sub(r"\s*\([^)]*\)$|\[[^\]]*\]", "", str(x)).strip() for x in t[col(t, "team")] if isinstance(x, str)]
        c0 = str(t.columns[0]).lower()
        if ("home" in c0 and "away" in c0) and out["takimlar"] and not out["maclar"]:
            labels = [str(x) for x in t.iloc[:, 0]]
            names = []
            for lab in labels:
                full = next((x for x in out["takimlar"] if _norm_team(x) == _norm_team(lab)), None)
                names.append(full or _abbr_match(lab, out["takimlar"]))
            if None in names or len(set(names)) != len(names):
                continue  # kısaltmalar puan durumundaki takımlara güvenle eşlenemedi: uydurma yok
            heads = list(t.columns[1:])
            colnames = [next((x for x in out["takimlar"] if _norm_team(x) == _norm_team(h)), None) or _abbr_match(h, out["takimlar"]) or
                        (names[i] if i < len(names) and len(heads) == len(names) else None) for i, h in enumerate(heads)]
            if len(set(colnames)) != len([c for c in colnames if c]) or None in colnames:
                continue
            for i, row in t.iterrows():
                for j, h in enumerate(heads):
                    v = str(row[h])
                    m = re.match(r"^\s*(\d+)\s*[–\-−:]\s*(\d+)", v)
                    if m and names[i] != colnames[j]:
                        out["maclar"].append((names[i], colnames[j], int(m[1]), int(m[2])))
        if col(t, "goalscorer") is not None or col(t, "player") is not None:
            pc = col(t, "goalscorer") or col(t, "player")
            tc, gc = col(t, "team") or col(t, "club"), col(t, "goals")
            if tc is not None and gc is not None:
                for _, row in t.iterrows():
                    try:
                        out["golculer"].append((re.sub(r"\[[^\]]*\]", "", str(row[pc])).strip(), re.sub(r"\[[^\]]*\]", "", str(row[tc])).strip(),
                                                int(str(row[gc]).split()[0])))
                    except (ValueError, IndexError):
                        continue
    return out
