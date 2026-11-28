"""data/matches.csv'deki BOŞ İY skoru ve maç istatistiği hücrelerini dış kaynaklardan doldurur (28 Kas 2026, veri kapsam Faz 3).

Kaynaklar:
  arsiv  data/arsiv/maclar.csv.gz İY skorları (openfootball CC0) — yalnız HTHome/HTAway
  espn   scripts/espn_detay_tara.py çıktısı (/workspace/arsiv_ham/espn_detay/<slug>.jsonl.gz) — İY, korner, şut,
         isabetli şut, faul, sarı, kırmızı
Eşleşme: aynı lig eşlemesi, ±1 gün, AYNI tam skor ve iki takım adının da benzer olması (normalize ad eşit ya da
SequenceMatcher ≥ 0.6, en az biri ≥ 0.8). Birden çok aday varsa doldurulmaz. Yalnız BOŞ hücre doldurulur; dolu hücre
asla değişmez; İY > tam skor ise İY yazılmaz. HTResult yalnız İY skorundan türetilir. Kaynakta olmayan alan boş kalır.

``--dogrula``: hedef hücresi DOLU satırlarda kaynağın aynı değeri verme oranı (alan başına). ``--alanlar`` ile yalnız
doğrulamayı geçen alanlar yazılır.

    python scripts/mac_detay_doldur.py --dogrula --kaynak espn --ham /workspace/arsiv_ham/espn_detay_dogrula --esle eng.1=E0
    python scripts/mac_detay_doldur.py --kaynak arsiv
    python scripts/mac_detay_doldur.py --kaynak espn --alanlar HTHome HTAway HomeCorners AwayCorners
"""

from __future__ import annotations

import argparse
import collections
import csv
import difflib
import gzip
import io
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.oddsmath import _norm_team

ARCHIVE = ROOT / "data" / "matches.csv"
ARSIV = ROOT / "data" / "arsiv" / "maclar.csv.gz"
ARSIV_MAP = {  # Division -> arşiv yarışmaları (İY skorlu)
    "ARG": ("south-america/argentina/ar1",), "AUT": ("austria/1-bundesliga", "austria/1-bundesliga-full"),
    "BRA": ("south-america/brazil/br1",), "CHN": ("world/asia/china/cn1",), "DEN": ("europe/denmark/dk1",),
    "FIN": ("europe/finland/fi1",), "IRL": ("europe/ireland/ie1",), "JAP": ("world/asia/japan/jp1",),
    "MEX": ("world/north-america/mexico/mx1",), "NOR": ("europe/norway/no1",), "POL": ("europe/poland/pl1",),
    "ROM": ("europe/romania/ro1",), "RUS": ("europe/russia/ru1",), "SUI": ("europe/switzerland/ch1",),
    "SWE": ("europe/sweden/se1",), "USA": ("world/north-america/major-league-soccer/mls",),
    "G1": ("europe/greece/gr1",), "EC": ("england/5-nationalleague",),
}
ESPN_MAP = {"aut.1": "AUT", "nor.1": "NOR", "swe.1": "SWE", "den.1": "DEN", "rus.1": "RUS", "arg.1": "ARG",
            "bra.1": "BRA", "mex.1": "MEX", "usa.1": "USA", "jpn.1": "JAP", "chn.1": "CHN", "gre.1": "G1",
            "eng.5": "EC"}
ESPN_FIELDS = {"ht_h": "HTHome", "ht_a": "HTAway", "c_h": "HomeCorners", "c_a": "AwayCorners", "s_h": "HomeShots",
               "s_a": "AwayShots", "st_h": "HomeTarget", "st_a": "AwayTarget", "f_h": "HomeFouls", "f_a": "AwayFouls",
               "y_h": "HomeYellow", "y_a": "AwayYellow", "r_h": "HomeRed", "r_a": "AwayRed"}


def _sim(a: str, b: str) -> float:
    a, b = _norm_team(a), _norm_team(b)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def load_source(kaynak: str, ham: Path | None, esle: dict[str, str] | None) -> list[dict]:
    """Ortak biçim: {div, d, h, a, hg, ag, alanlar: {matches sütunu: değer}}"""
    out = []
    if kaynak == "arsiv":
        rev = {y: div for div, ys in ARSIV_MAP.items() for y in ys}
        if esle:
            rev = {y: div for y, div in esle.items()}
        a = pd.read_csv(ARSIV, low_memory=False, usecols=["tarih", "yarisma", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep"])
        a = a[a.yarisma.isin(set(rev)) & a.tarih.notna() & a.iy_ev.notna() & a.hg.notna()]
        for t, y, h, w, hg, ag, ih, ia in zip(a.tarih, a.yarisma, a.ev, a.dep, a.hg, a.ag, a.iy_ev, a.iy_dep):
            out.append({"div": rev[y], "d": t, "h": h, "a": w, "hg": int(hg), "ag": int(ag),
                        "alanlar": {"HTHome": int(ih), "HTAway": int(ia)}})
    else:
        m = esle or ESPN_MAP
        for slug, div in m.items():
            f = (ham or Path("/workspace/arsiv_ham/espn_detay")) / f"{slug}.jsonl.gz"
            if not f.exists():
                continue
            with gzip.open(f, "rt", encoding="utf-8") as g:
                for ln in g:
                    r = json.loads(ln)
                    al = {col: r[k] for k, col in ESPN_FIELDS.items() if r.get(k) is not None}
                    out.append({"div": div, "d": r["d"], "h": r["h"], "a": r["a"], "hg": r["hg"], "ag": r["ag"], "alanlar": al})
    return out


def match(base: pd.DataFrame, src: list[dict]) -> dict[int, dict]:
    """matches.csv satır indeksi -> kaynak alanları (tek ve güvenilir eşleşme)."""
    idx = collections.defaultdict(list)
    d = pd.to_datetime(base["MatchDate"], errors="coerce")
    for i, div, day, fh, fa in zip(base.index, base["Division"], d, base["FTHome"], base["FTAway"]):
        if pd.notna(day) and pd.notna(fh) and pd.notna(fa):
            idx[(div, day.strftime("%Y-%m-%d"), int(fh), int(fa))].append(i)
    hits: dict[int, list[dict]] = collections.defaultdict(list)
    for r in src:
        day = pd.Timestamp(r["d"])
        cands = []
        for k in (0, -1, 1):
            for i in idx.get((r["div"], (day + pd.Timedelta(days=k)).strftime("%Y-%m-%d"), r["hg"], r["ag"]), []):
                s1, s2 = _sim(base.at[i, "HomeTeam"], r["h"]), _sim(base.at[i, "AwayTeam"], r["a"])
                if min(s1, s2) >= 0.6 and max(s1, s2) >= 0.8:
                    cands.append(i)
        if len(set(cands)) == 1:
            hits[cands[0]].append(r["alanlar"])
    return {i: v[0] for i, v in hits.items() if len(v) == 1}


def _empty(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def validate(base: pd.DataFrame, found: dict[int, dict]) -> dict:
    agree, total = collections.Counter(), collections.Counter()
    for i, al in found.items():
        for col, v in al.items():
            cur = base.at[i, col] if col in base.columns else None
            if not _empty(cur):
                total[col] += 1
                agree[col] += int(float(cur) == float(v))
    return {c: {"n": total[c], "uyum": round(agree[c] / total[c], 4)} for c in sorted(total)}


def data_lines(lines: list[str]) -> list[int]:
    """pandas satır sırası -> fiziksel satır numarası. pandas boş satırları atlar (skip_blank_lines); arşivde
    230559. satırda tarihsel bir boş satır var, bu yüzden ``get_loc(i) + 1`` sonrasını bir satır kaydırır."""
    return [k for k, ln in enumerate(lines) if k > 0 and ln.strip() != ""]


def fill(archive: Path, base: pd.DataFrame, found: dict[int, dict], fields: set[str]) -> dict:
    cols = list(base.columns)
    pos = {c: cols.index(c) for c in cols}
    lines = archive.read_text(encoding="utf-8").split("\n")
    phys = data_lines(lines)
    if len(phys) != len(base):
        raise SystemExit(f"satır sayısı uyuşmuyor: dosya {len(phys)}, pandas {len(base)}")
    stats = collections.Counter()
    for i, al in found.items():
        li = phys[base.index.get_loc(i)]
        row = next(csv.reader([lines[li]]))
        if row[pos["HomeTeam"]] != str(base.at[i, "HomeTeam"]) or row[pos["MatchDate"]] != str(base.at[i, "MatchDate"]):
            raise SystemExit(f"satır hizası bozuk: {li}")
        changed = False
        al = {c: v for c, v in al.items() if c in fields and c in pos}
        fh, fa = base.at[i, "FTHome"], base.at[i, "FTAway"]
        if ("HTHome" in al) != ("HTAway" in al) or (
                "HTHome" in al and (al["HTHome"] > fh or al["HTAway"] > fa)):
            al.pop("HTHome", None)
            al.pop("HTAway", None)
        for c, v in al.items():
            if row[pos[c]].strip() == "":
                row[pos[c]] = str(float(v))
                stats[c] += 1
                changed = True
        if "HTHome" in al and "HTResult" in pos and row[pos["HTResult"]].strip() == "" and row[pos["HTHome"]] and row[pos["HTAway"]]:
            h, a = float(row[pos["HTHome"]]), float(row[pos["HTAway"]])
            row[pos["HTResult"]] = "H" if h > a else "A" if h < a else "D"
            changed = True
        if changed:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="").writerow(row)
            lines[li] = buf.getvalue()
            stats["satir"] += 1
    archive.write_text("\n".join(lines), encoding="utf-8")
    return dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kaynak", choices=["arsiv", "espn"], required=True)
    ap.add_argument("--ham", type=Path, default=None)
    ap.add_argument("--esle", nargs="*", default=None, help="kaynak=Division (ör. eng.1=E0)")
    ap.add_argument("--dogrula", action="store_true")
    ap.add_argument("--alanlar", nargs="*", default=None)
    ap.add_argument("--arsiv-dosya", type=Path, default=ARCHIVE)
    a = ap.parse_args()
    esle = dict(x.split("=", 1) for x in a.esle) if a.esle else None
    base = pd.read_csv(a.arsiv_dosya, low_memory=False)
    src = load_source(a.kaynak, a.ham, esle)
    found = match(base, src)
    print(json.dumps({"kaynak_satir": len(src), "eslesen": len(found)}))
    if a.dogrula:
        print(json.dumps(validate(base, found), ensure_ascii=False, indent=1))
        return
    fields = set(a.alanlar) if a.alanlar else {"HTHome", "HTAway"}
    print(json.dumps(fill(a.arsiv_dosya, base, found, fields), ensure_ascii=False))


if __name__ == "__main__":
    main()
