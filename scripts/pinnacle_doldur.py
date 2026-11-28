"""data/matches.csv'ye Pinnacle açılış/kapanış sütunlarını ekler ve geriye doldurur (28 Kas 2026, veri kapsam denetimi #3).

football-data.co.uk sezon dosyaları (mmz4281/<sezon>/<div>.csv, 2012/13'ten beri PSH/PSD/PSA ve PSCH/PSCD/PSCA;
2019/20'den beri P>2.5 / PC>2.5) ve ek lig dosyaları (new/<KOD>.csv, yalnız kapanış PSCH/PSCD/PSCA) okunur. Ücretsiz,
robots izinli araştırma verisi; atıf: www.football-data.co.uk.

Yeni sütunlar (sona eklenir; eski sütunlar ve değerleri BAYT BAYT aynı kalır, dosya metin düzeyinde yazılır):
  PSHome PSDraw PSAway           Pinnacle 1X2 (football-data'nın "maç öncesi son toplama" anı)
  PSCHome PSCDraw PSCAway        Pinnacle kapanış 1X2
  PSOver25 PSUnder25             Pinnacle 2.5 Üst/Alt
  PSCOver25 PSCUnder25           Pinnacle kapanış 2.5 Üst/Alt
  Source                         boş = football-data; "espn" = ESPN'den yalnız skor (oran/İY yok, sonradan değişebilir)
Eşleşme: Division + tarih + takım adları (harf/rakam dışı atılarak); olmazsa aynı gün aynı skorla TEK aday. Bulunamayan
hücre boş kalır — hiçbir değer uydurulmaz.

    python scripts/pinnacle_doldur.py --ham /workspace/fd_hist        # mmz_<sezon>_<div>.csv, new_<KOD>.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "matches.csv"
SEASONS = ROOT / "data" / "global_odds" / "latest"
PIN_COLS = ["PSHome", "PSDraw", "PSAway", "PSCHome", "PSCDraw", "PSCAway", "PSOver25", "PSUnder25", "PSCOver25",
            "PSCUnder25"]
NEW_COLS = [*PIN_COLS, "Source"]
# arşiv sütunu <- football-data sütunu
FD_PIN = {"PSHome": "PSH", "PSDraw": "PSD", "PSAway": "PSA", "PSCHome": "PSCH", "PSCDraw": "PSCD", "PSCAway": "PSCA",
          "PSOver25": "P>2.5", "PSUnder25": "P<2.5", "PSCOver25": "PC>2.5", "PSCUnder25": "PC<2.5"}
NEW_LEAGUES = {"ARG": "ARG", "AUT": "AUT", "BRA": "BRA", "CHN": "CHN", "DNK": "DEN", "FIN": "FIN", "IRL": "IRL",
               "JPN": "JAP", "MEX": "MEX", "NOR": "NOR", "POL": "POL", "ROU": "ROM", "RUS": "RUS", "SWZ": "SUI",
               "SWE": "SWE", "USA": "USA"}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _date(s: str) -> str | None:
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s.strip())
    if not m:
        return None
    d, mo, y = m.groups()
    y = int(y)
    y = y + 2000 if y < 100 else y
    return f"{y:04d}-{int(mo):02d}-{int(d):02d}"


def _num(v: str | None) -> str:
    if v is None:
        return ""
    v = v.strip()
    try:
        f = float(v)
    except ValueError:
        return ""
    return v if f > 1.0 else ""


def read_fd(path: Path, division: str | None = None) -> list[dict]:
    """Bir football-data dosyasından (eski ya da ek lig düzeni) Pinnacle değerleri olan satırlar."""
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        div = division or (r.get("Div") or "").strip()
        home, away = r.get("HomeTeam") or r.get("Home"), r.get("AwayTeam") or r.get("Away")
        fh, fa = r.get("FTHG") or r.get("HG"), r.get("FTAG") or r.get("AG")
        date = _date(r.get("Date") or "")
        if not (div and home and away and date):
            continue
        vals = {c: _num(r.get(src)) for c, src in FD_PIN.items()}
        if not any(vals.values()):
            continue
        out.append({"div": div, "date": date, "h": norm(home), "a": norm(away), "fh": (fh or "").strip(),
                    "fa": (fa or "").strip(), **vals})
    return out


def build_lookup(files: list[tuple[Path, str | None]]) -> tuple[dict, dict]:
    exact, by_score = {}, {}
    for path, div in files:
        try:
            rows = read_fd(path, div)
        except (OSError, csv.Error):
            continue
        for r in rows:
            vals = {c: r[c] for c in PIN_COLS}
            k = (r["div"], r["date"], r["h"], r["a"])
            old = exact.get(k)
            if old is None or sum(bool(v) for v in vals.values()) > sum(bool(v) for v in old.values()):
                exact[k] = vals
            by_score.setdefault((r["div"], r["date"], r["fh"], r["fa"]), []).append(vals)
    return exact, by_score


def _fmt_score(v: str) -> str:
    try:
        return str(int(float(v)))
    except ValueError:
        return ""


def fill(archive: Path, exact: dict, by_score: dict) -> dict:
    """matches.csv'yi metin düzeyinde yeniden yazar: eski sütunlar aynen, NEW_COLS sonda."""
    lines = archive.read_text(encoding="utf-8").split("\n")
    header = next(csv.reader([lines[0]]))
    have_new = all(c in header for c in NEW_COLS)
    if have_new:
        base_n = header.index(NEW_COLS[0])
    else:
        base_n = len(header)
        lines[0] = lines[0] + "," + ",".join(NEW_COLS)
    idx = {c: header.index(c) for c in ("Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway")}
    stats = {"satir": 0, "tam_eslesme": 0, "skor_eslesme": 0, "bos": 0}
    out = [lines[0]]
    for ln in lines[1:]:
        if not ln:
            out.append(ln)
            continue
        f = next(csv.reader([ln]))
        stats["satir"] += 1
        prev = f[base_n:base_n + len(NEW_COLS)] if have_new else []
        prev += [""] * (len(NEW_COLS) - len(prev))
        src = prev[-1]
        k = (f[idx["Division"]], f[idx["MatchDate"]], norm(f[idx["HomeTeam"]]), norm(f[idx["AwayTeam"]]))
        vals = exact.get(k)
        if vals is None and k[0] in NEW_LEAGUES.values():  # eski ek lig satırlarında gün/ay ters okunmuş tarih
            y, m, d = (k[1].split("-") + ["", ""])[:3]
            if d and int(d) <= 12:
                vals = exact.get((k[0], f"{y}-{d}-{m}", k[2], k[3]))
        if vals is not None:
            stats["tam_eslesme"] += 1
        else:
            cands = by_score.get((k[0], k[1], _fmt_score(f[idx["FTHome"]]), _fmt_score(f[idx["FTAway"]])), [])
            if len(cands) == 1:
                vals = cands[0]
                stats["skor_eslesme"] += 1
        if vals is None:
            stats["bos"] += 1
            new = prev[:-1]
        else:  # mevcut dolu hücre korunur, yalnız boşlar doldurulur
            new = [p or vals[c] for p, c in zip(prev[:-1], PIN_COLS)]
        head = ln if not have_new else ln.rsplit(",", len(NEW_COLS))[0]
        out.append(head + "," + ",".join([*new, src]))
    archive.write_text("\n".join(out), encoding="utf-8")
    return stats


def source_files(ham: Path | None) -> list[tuple[Path, str | None]]:
    files: list[tuple[Path, str | None]] = []
    if ham:
        files += [(p, None) for p in sorted(ham.glob("mmz_*.csv"))]
        files += [(p, NEW_LEAGUES[p.stem[4:]]) for p in sorted(ham.glob("new_*.csv")) if p.stem[4:] in NEW_LEAGUES]
    files += [(p, None) for p in sorted(SEASONS.glob("season_*/*.csv"))]
    files += [(p, NEW_LEAGUES[p.stem]) for p in sorted((SEASONS / "new_leagues").glob("*.csv")) if p.stem in NEW_LEAGUES]
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ham", type=Path, default=None, help="indirilmiş football-data dosyaları klasörü")
    ap.add_argument("--arsiv", type=Path, default=ARCHIVE)
    a = ap.parse_args()
    exact, by_score = build_lookup(source_files(a.ham))
    print(fill(a.arsiv, exact, by_score))


if __name__ == "__main__":
    sys.exit(main())
