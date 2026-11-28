"""Lig taban oranı öncülü, geçmişi olmayan liglerde işe yarıyor mu? (28 Kas 2026, veri kapsam #5 — GFI yeniden testi)

GFI dışa aktarımı (/workspace/gfi_import) artık kutuda yok; bu yüzden aynı fikir (0.6·P + 0.4·lig taban oranı) GFI
yerine data/arsiv/maclar.csv.gz + data/matches.csv ile, ZAMAN SIZINTISIZ yeniden ölçülür:
  * seçim günü D için yalnız D'den önceki tarihli maçlar kullanılır (tarihsiz Wikipedia satırları dışarıda);
  * lig, iki takımın son 400 günde birlikte göründüğü yarışmadır (takım adı benzerliği ≥ 0.82, aynı yarışma);
  * taban oran = o yarışmanın son 730 günü (≥ 60 maç; İY pazarları için İY skorlu ≥ 60 maç).
Seçimler: sürüm denetimi rows.json (sonucu Nesine'den doğrulanmış), gol aileleri: X.5 Üst/Alt, İY X.5 Üst/Alt, KG.

    python scripts/arsiv_oncul_olcumu.py [--rows ...rows.json] [--sonuc /workspace/fd_denetim_2026-11-28/sonuc]
"""

from __future__ import annotations

import argparse
import collections
import difflib
import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.oddsmath import _norm_team
from quantfoot.markets import league_halves as lh
from quantfoot.markets.market_calibration import NESINE_TO_DIVISION

SIM = 0.82


def load_hist() -> pd.DataFrame:
    a = pd.read_csv(ROOT / "data/arsiv/maclar.csv.gz", low_memory=False,
                    usecols=["tarih", "yarisma", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep"])
    a = a[a.tarih.notna() & (a.tarih >= "2023-01-01")]
    m = pd.read_csv(ROOT / "data/matches.csv", low_memory=False,
                    usecols=["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway", "HTHome", "HTAway"])
    m = m[m.MatchDate >= "2023-01-01"].rename(columns={"Division": "yarisma", "MatchDate": "tarih", "HomeTeam": "ev",
                                                       "AwayTeam": "dep", "FTHome": "hg", "FTAway": "ag",
                                                       "HTHome": "iy_ev", "HTAway": "iy_dep"})
    m["yarisma"] = "fd/" + m.yarisma.astype(str)
    h = pd.concat([a, m], ignore_index=True).dropna(subset=["hg", "ag"])
    h["d"] = pd.to_datetime(h.tarih, errors="coerce")
    h = h.dropna(subset=["d"])
    h["n_ev"], h["n_dep"] = h.ev.map(_norm_team), h.dep.map(_norm_team)
    return h


def find_team(name: str, names: list[str], cache: dict) -> str | None:
    n = _norm_team(name)
    if n in cache:
        return cache[n]
    hit = difflib.get_close_matches(n, names, n=1, cutoff=SIM)
    cache[n] = hit[0] if hit else None
    return cache[n]


def selection_rate(sec: str, x: pd.DataFrame) -> float | None:
    m = re.match(r"^(İY )?(\d)\.5 (Üst|Alt)$", sec)
    if m:
        half, line, side = bool(m.group(1)), int(m.group(2)), m.group(3)
        if half:
            x = x.dropna(subset=["iy_ev", "iy_dep"])
            if len(x) < 60:
                return None
            g = x.iy_ev + x.iy_dep
        else:
            g = x.hg + x.ag
        over = float((g > line).mean())
        return over if side == "Üst" else 1 - over
    if sec in ("KG Var", "KG Yok"):
        v = float(((x.hg > 0) & (x.ag > 0)).mean())
        return v if sec == "KG Var" else 1 - v
    return None


def _ll(p: float, y: bool) -> float:
    p = min(max(p, 1e-3), 1 - 1e-3)
    return -math.log(p if y else 1 - p)


def metrics(df: pd.DataFrame, col: str) -> dict:
    if df.empty:
        return {"n": 0}
    y = df.won.astype(float)
    return {"n": len(df), "logloss": round(float(np.mean([_ll(p, w) for p, w in zip(df[col], df.won)])), 4),
            "brier": round(float(((df[col] - y) ** 2).mean()), 4)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", type=Path, default=ROOT / "tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json")
    ap.add_argument("--sonuc", type=Path, default=Path("/workspace/fd_denetim_2026-11-28/sonuc"))
    ap.add_argument("--out", type=Path, default=ROOT / "reports/research/arsiv_oncul_olcumu_2026-11-28.json")
    a = ap.parse_args()
    info = {}
    for f in sorted(glob.glob(str(a.sonuc / "unlive_*.json"))):
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["d"]:
            info[m["C"]] = m
    rows = [r for r in json.loads(a.rows.read_text(encoding="utf-8"))
            if r.get("won") is not None and r.get("p") is not None and r.get("kod") in info
            and r.get("aile") in ("Alt/Üst", "İY Alt/Üst", "KG")]
    h = load_hist()
    out = []
    for day in sorted({r["tarih"] for r in rows}):
        D = pd.Timestamp(day)
        win = h[(h.d < D) & (h.d >= D - pd.Timedelta(days=400))]
        names = sorted(set(win.n_ev) | set(win.n_dep))
        comp_of: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for y, ne, nd in zip(win.yarisma, win.n_ev, win.n_dep):
            comp_of[ne][y] += 1
            comp_of[nd][y] += 1
        cache: dict = {}
        for r in (x for x in rows if x["tarih"] == day):
            m = info[r["kod"]]
            th, ta = find_team(m["HT"], names, cache), find_team(m["AT"], names, cache)
            if not th or not ta:
                continue
            common = comp_of[th] & comp_of[ta]
            if not common:
                continue
            comp = common.most_common(1)[0][0]
            x = h[(h.yarisma == comp) & (h.d < D) & (h.d >= D - pd.Timedelta(days=730))]
            if len(x) < 60:
                continue
            rate = selection_rate(r["secim"], x)
            if rate is None:
                continue
            lig = m["L"].split(",")[0].strip()
            out.append({"tarih": day, "lig": lig, "yarisma": comp, "secim": r["secim"], "aile": r["aile"], "won": bool(r["won"]),
                        "p": float(r["p"]), "oran": rate, "kod": r["kod"],
                        "yeni_lig": not lh._rows(lig) and lig not in NESINE_TO_DIVISION})
    ev = pd.DataFrame(out)
    ev["p_w06"] = 0.6 * ev.p + 0.4 * ev.oran
    ev["p_w08"] = 0.8 * ev.p + 0.2 * ev.oran
    cols = ("p", "p_w08", "p_w06")
    tek = ev.drop_duplicates(["kod", "secim"])
    res = {"toplam_gol_secimi": len(rows), "onculu_olan": len(ev), "tekil": len(tek)}
    for name, sub in (("hepsi", ev), ("yeni_lig", ev[ev.yeni_lig]), ("kapsanan_lig", ev[~ev.yeni_lig]),
                      ("P>=0.70", ev[ev.p >= 0.70]), ("yeni_lig_P>=0.70", ev[ev.yeni_lig & (ev.p >= 0.70)]),
                      ("tekil_yeni_lig", tek[tek.yeni_lig]), ("tekil_hepsi", tek)):
        res[name] = {c: metrics(sub, c) for c in cols}
    for day, g in ev[ev.yeni_lig].groupby("tarih"):
        res.setdefault("gun_yeni_lig", {})[day] = {c: metrics(g, c) for c in cols}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if not isinstance(v, dict) else {c: (v[c].get("n"), v[c].get("logloss"), v[c].get("brier"))
                                                              for c in cols if c in v})
                      for k, v in res.items() if k != "gun_yeni_lig"}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
