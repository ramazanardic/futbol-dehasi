"""data/arsiv/maclar.csv.gz'ye ek kaynakları tekrarsız ekler (28 Kas 2026, veri kapsam denetimi #1/#4).

Kaynaklar (ham veri repoya girmez; varsayılan kök /workspace/arsiv_ham):
  espn_lig/<slug>.jsonl.gz     scripts/espn_lig_tara.py — ESPN lig scoreboard'u (yalnız tam skor, İY yok)
  openligadb/<lig>_<yıl>.json  api.openligadb.de/getmatchdata/<lig>/<yıl> — yalnız tam skor (Daten: OpenLigaDB, ODbL).
                               İY YAZILMAZ: openfootball ile karşılaştırmada İY'nin ~%10'u yanlış, uyuşmayanların
                               neredeyse hepsi 0:0 yer tutucusu (2023/24–2025/26, takım eşlemeli kontrol, 28 Kas).
  wiki_ek/*.jsonl.gz           scripts/arsiv_wiki_tara.py biçimi — Wikipedia sonuç matrisi (tarihsiz, CC BY-SA 4.0)
data/matches.csv ve data/international_results.csv'de zaten olan maçlar (±1 gün, normalize takım, aynı skor;
scripts/arsiv_kur.py ile aynı kural) alınmaz. Mevcut satırlar aynen kalır; yalnız (yarışma, tarih, ev, dep) — tarihsizlerde (yarışma, sezon, ev, dep) — anahtarı
olmayan satırlar eklenir. Eksik alan (İY, tarih) boş kalır; hiçbir değer uydurulmaz.

    python scripts/arsiv_ek_kaynak.py [--ham /workspace/arsiv_ham]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from quantfoot.data.arsiv import team_key

ARSIV = ROOT / "data" / "arsiv" / "maclar.csv.gz"
COLS = ["tarih", "sezon", "yarisma", "tur", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep", "durum", "ham_skor", "kaynak"]
OLDB_NAMES = {"bl3": "openligadb/bl3", "bl2": "openligadb/bl2", "bl1": "openligadb/bl1"}


def season_of(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    s = y if m >= 7 else y - 1
    return f"{s}/{str(s + 1)[2:]}"


def espn_rows(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as g:
            for ln in g:
                r = json.loads(ln)
                st = "PEN" if "Pen" in r.get("st", "") else "AET" if "AET" in r.get("st", "") else "FT"
                out.append({"tarih": r["d"], "sezon": season_of(r["d"]), "yarisma": f"espn/{r['l']}", "tur": "lig",
                            "ev": r["h"], "dep": r["a"], "hg": r["hg"], "ag": r["ag"], "iy_ev": None, "iy_dep": None,
                            "durum": st, "ham_skor": None, "kaynak": "espn"})
    return out


def openligadb_rows(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*_*.json")):
        lig = f.stem.split("_")[0]
        for m in json.loads(f.read_text(encoding="utf-8")):
            if not m.get("matchIsFinished"):
                continue
            res = {r.get("resultTypeID"): r for r in m.get("matchResults") or []}
            ft = res.get(2)
            if not ft:
                continue
            date = (m.get("matchDateTime") or "")[:10]
            out.append({"tarih": date, "sezon": season_of(date), "yarisma": OLDB_NAMES.get(lig, f"openligadb/{lig}"),
                        "tur": "lig", "ev": m["team1"]["teamName"], "dep": m["team2"]["teamName"],
                        "hg": ft["pointsTeam1"], "ag": ft["pointsTeam2"],
                        "iy_ev": None, "iy_dep": None,  # İY güvenilmez (0:0 yer tutucuları), uydurulmaz
                        "durum": "FT", "ham_skor": None, "kaynak": "openligadb"})
    return out


def wiki_rows(d: Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*.jsonl.gz")):
        with gzip.open(f, "rt", encoding="utf-8") as g:
            for ln in g:
                r = json.loads(ln)
                if r.pop("_t", None) == "mac":
                    out.append({**r, "tur": r.get("tur") or "lig"})
    return out


def _keys(df: pd.DataFrame) -> pd.Series:
    t = df["tarih"].fillna("").astype(str)
    return df["yarisma"].astype(str) + "|" + t.where(t != "", "S" + df["sezon"].astype(str)) + "|" + \
        df["ev"].astype(str) + "|" + df["dep"].astype(str)


def _ext_key(r) -> tuple:
    return (r.tarih, team_key(r.ev)[:8], team_key(r.dep)[:8], (int(r.hg), int(r.ag)))


def merge(arsiv: Path, ham: Path, dis_anahtar: set | None = None) -> dict:
    base = pd.read_csv(arsiv, low_memory=False, dtype=str, keep_default_na=False)
    new = pd.DataFrame(espn_rows(ham / "espn_lig") + openligadb_rows(ham / "openligadb") + wiki_rows(ham / "wiki_ek"),
                       columns=COLS)
    if new.empty:
        return {"eklenen": 0}
    new = new.astype(object).where(new.notna(), "")
    for c in ("hg", "ag", "iy_ev", "iy_dep"):
        new[c] = new[c].map(lambda v: "" if v == "" else str(int(float(v))))
    seen = set(_keys(base))
    k = _keys(new)
    add = new[~k.isin(seen) & ~k.duplicated()]
    if dis_anahtar:
        dated = add.tarih != ""
        dup = [bool(d) and _ext_key(r) in dis_anahtar for d, r in zip(dated, add.itertuples(index=False))]
        add = add[[not x for x in dup]]
    # metin düzeyinde ekleme: mevcut satırlar bayt bayt aynı kalır (dosya CRLF satır sonlu)
    raw = gzip.decompress(arsiv.read_bytes()).decode("utf-8")
    eol = "\r\n" if "\r\n" in raw[:4096] else "\n"
    if raw and not raw.endswith(eol):
        raw += eol
    buf = io.StringIO()
    csv.writer(buf, lineterminator=eol).writerows(add[COLS].itertuples(index=False, name=None))
    arsiv.write_bytes(gzip.compress((raw + buf.getvalue()).encode("utf-8"), compresslevel=9, mtime=0))
    return {"eklenen": len(add), "yarisma": add.groupby("yarisma").size().to_dict()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ham", type=Path, default=Path("/workspace/arsiv_ham"))
    ap.add_argument("--arsiv", type=Path, default=ARSIV)
    a = ap.parse_args()
    import arsiv_kur

    print(json.dumps(merge(a.arsiv, a.ham, arsiv_kur.existing_keys(ROOT)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
