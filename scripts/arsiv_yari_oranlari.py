"""Orta Avrupa ligleri için yarı taban oranlarını data/arsiv/maclar.csv.gz'den türetir (28 Kas 2026, veri kapsam #2).

lig_yari_oranlari.csv'de bu liglerin satırı ya yoktu (HNL, Bosna, Slovakya) ya da küçük örneklemliydi (Slovenya n=73
→ hiç kullanılmıyordu; Sırbistan 136, Macaristan 183 …). Arşivdeki İY skorlu maçlardan aynı sütunlar (n, gol, İY gol
payı, İY/2Y/İY-MS/İY-2Y oranları, iki yarıda KG …) ``arsiv.<kod>`` satırları olarak yazılır; Nesine adı eşlemesi
src/quantfoot/markets/league_halves.py'dedir. Bir lig YALNIZ zaman sızıntısız ileri yürüyen ölçümde (``--olc``) mevcut
duruma göre log-loss/Brier'i kötüleştirmiyorsa eşlemeye alınır.

Kaynaklar arşivdeki gibi: openfootball (CC0), OpenLigaDB (ODbL, "Daten: OpenLigaDB"). Yalnız agregat yazılır.

    python scripts/arsiv_yari_oranlari.py --olc     # ileri yürüyen ölçüm -> reports/research/arsiv_yari_olcum.json
    python scripts/arsiv_yari_oranlari.py --yaz     # arsiv.* satırlarını data/lig_yari_oranlari.csv'ye ekler/yeniler
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import gfi_yari_oranlari as gy

from quantfoot.markets import league_halves as lh

ARSIV = ROOT / "data" / "arsiv" / "maclar.csv.gz"
OUT = ROOT / "data" / "lig_yari_oranlari.csv"
# arsiv kodu -> (arşiv yarışmaları, Nesine adı). Aynı lig iki kaynakta varsa sezon başına tek kaynak (ilk sıradaki).
CODES: dict[str, tuple[tuple[str, ...], str]] = {
    "arsiv.hr.1": (("europe/croatia/hr1",), "Hırvatistan 1. Hnl"),
    "arsiv.ba.1": (("europe/bosnia-herzegovina/ba1",), "Bosna Hersek Premier Lig"),
    "arsiv.sk.1": (("europe/slovakia/sk1",), "Slovakya Superliga"),
    "arsiv.si.1": (("europe/slovenia/si1",), "Slovenya Prvaliga"),
    "arsiv.rs.1": (("europe/serbia/rs1",), "Sırbistan Superliga"),
    "arsiv.hu.1": (("europe/hungary/hu1",), "Macaristan 1. Ligi"),
    "arsiv.cz.1": (("europe/czech-republic/cz1",), "Çekya 1. Lig"),
    "arsiv.ch.2": (("europe/switzerland/ch2",), "İsviçre Challenge Ligi"),
    "arsiv.at.2": (("austria/2-liga2",), "Avusturya 2. Lig"),
    "arsiv.de.3": (("openligadb/bl3", "deutschland/3-liga3"), "Almanya 3. Lig"),
    "arsiv.tr.2": (("europe/turkey/tr2",), "Türkiye 1. Lig"),
    "arsiv.it.3": (("italy/3-seriec_a", "italy/3-seriec_b", "italy/3-seriec_c"), "İtalya Serie C"),
}
SERIEC = ("italy/3-seriec_a", "italy/3-seriec_b", "italy/3-seriec_c")


def load(arsiv: Path = ARSIV) -> pd.DataFrame:
    a = pd.read_csv(arsiv, low_memory=False, usecols=["tarih", "sezon", "yarisma", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep"])
    want = {y for ys, _ in CODES.values() for y in ys}
    a = a[a.yarisma.isin(want)].dropna(subset=["hg", "ag", "iy_ev", "iy_dep"]).copy()
    for c in ("hg", "ag", "iy_ev", "iy_dep"):
        a[c] = a[c].astype(int)
    rows = []
    for code, (ys, _) in CODES.items():
        x = a[a.yarisma.isin(ys)]
        if x.empty:
            continue
        # sezon başına tek kaynak (Serie C grupları birlikte tek kaynak sayılır)
        grp = x.yarisma.where(~x.yarisma.isin(SERIEC), "seriec")
        order = {("seriec" if y in SERIEC else y): i for i, y in enumerate(ys)}
        x = x.assign(_g=grp, _o=grp.map(order))
        best = x.groupby("sezon")["_o"].min()
        x = x[x["_o"] == x.sezon.map(best)]
        rows.append(x.assign(kod=code))
    return pd.concat(rows, ignore_index=True)


def rates(df: pd.DataFrame) -> dict[str, dict]:
    it = ((k, h, a, {"score": {"ht": [ih, ia]}}) for k, h, a, ih, ia in
          zip(df.kod, df.hg, df.ag, df.iy_ev, df.iy_dep))
    return gy.league_rates(it)


def _ll(p: float, y: bool) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -math.log(p if y else 1 - p)


def _p_over(mu: float, line: int) -> float:
    """Poisson P(X >= line)."""
    return 1.0 - sum(math.exp(-mu) * mu ** k / math.factorial(k) for k in range(line))


def shrunk(n: int, gol: float, share: float) -> float:
    goals = n * gol
    return (goals * share + lh.PRIOR * lh.PRIOR_GOALS) / (goals + lh.PRIOR_GOALS)


def measure(df: pd.DataFrame) -> dict:
    blend_cols = list(lh.LEAGUE_BLEND.values())
    tab = lh._table()
    glob_rate = {c: sum(float(r[c]) * int(r["n"]) for r in tab.values() if r.get(c)) /
                 sum(int(r["n"]) for r in tab.values() if r.get(c)) for c in blend_cols}
    out = {}
    for code, (_, nesine) in CODES.items():
        x = df[df.kod == code]
        seasons = sorted(x.sezon.unique())
        cur_share = lh.league_first_half_share(nesine) or lh.PRIOR
        cur_rate = {c: lh.league_rate(nesine, c) for c in blend_cols}
        acc = {"n": 0, "A": 0.0, "B": 0.0, "brierA": 0.0, "brierB": 0.0, "nb": 0, "sezonlar": []}
        for s in seasons:
            test, train = x[x.sezon == s], x[x.sezon < s]
            if len(test) < 60 or len(train) < lh.MIN_MATCHES:
                continue
            r = rates(train)[code]
            lam = float(r["gol"])
            new_share = shrunk(int(r["n"]), lam, float(r["iy_gol_payi"]))
            g1 = (test.iy_ev + test.iy_dep).to_numpy()
            g2 = (test.hg + test.ag - test.iy_ev - test.iy_dep).to_numpy()
            for share, arm in ((cur_share, "A"), (new_share, "B")):
                tot = 0.0
                for line in (1, 2):
                    p1, p2 = _p_over(lam * share, line), _p_over(lam * (1 - share), line)
                    tot += sum(_ll(p1, g >= line) for g in g1) + sum(_ll(p2, g >= line) for g in g2)
                acc[arm] += tot
            acc["n"] += 4 * len(test)
            # LEAGUE_BLEND sütunları: mevcut lig oranı (yoksa genel ortalama) vs arşiv oranı (yalnız geçmiş sezonlar)
            obs = rates(test.assign(kod=code))[code]
            for c in blend_cols:
                a_rate = cur_rate[c] if cur_rate[c] is not None else glob_rate[c]
                b_rate = float(r[c])
                y = float(obs[c])  # test sezonundaki oran: Brier = p² - 2p·y + y (maç başına ortalama)
                acc["brierA"] += len(test) * (a_rate ** 2 - 2 * a_rate * y + y)
                acc["brierB"] += len(test) * (b_rate ** 2 - 2 * b_rate * y + y)
                acc["nb"] += len(test)
            acc["sezonlar"].append({"sezon": s, "test": len(test), "egitim": len(train), "pay_A": round(cur_share, 4),
                                    "pay_B": round(new_share, 4), "gercek_pay": round(float(g1.sum() / (g1.sum() + g2.sum())), 4)})
        if acc["n"]:
            out[code] = {"nesine": nesine, "mevcut_kodlar": [r["lig"] for r in lh._rows(nesine)],
                         "yari_gol_logloss_A": round(acc["A"] / acc["n"], 5), "yari_gol_logloss_B": round(acc["B"] / acc["n"], 5),
                         "blend_brier_A": round(acc["brierA"] / acc["nb"], 5), "blend_brier_B": round(acc["brierB"] / acc["nb"], 5),
                         "olcum_n": acc["n"] // 4, "sezonlar": acc["sezonlar"]}
            o = out[code]
            o["karar"] = "al" if (o["yari_gol_logloss_B"] <= o["yari_gol_logloss_A"] + 1e-5
                                  and o["blend_brier_B"] <= o["blend_brier_A"] + 1e-5) else "alma"
    return out


def write(df: pd.DataFrame, keep: set[str]) -> int:
    r = rates(df)
    with OUT.open(encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    head = [ln for ln in lines if ln.startswith("#")]
    body = [ln for ln in lines if not ln.startswith("#")]
    rdr = list(csv.DictReader(body))
    fields = body[0].split(",")
    rows = [x for x in rdr if not x["lig"].startswith("arsiv.")]
    rows += [{"lig": k, **r[k]} for k in sorted(keep) if k in r]
    note = "# arsiv.* = data/arsiv/maclar.csv.gz (openfootball CC0; OpenLigaDB ODbL) — scripts/arsiv_yari_oranlari.py"
    if note not in head:
        head.append(note)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(head) + "\n")
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for x in sorted(rows, key=lambda d: d["lig"]):
            w.writerow(x)
    return len(keep)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--olc", action="store_true")
    ap.add_argument("--yaz", action="store_true")
    ap.add_argument("--rapor", type=Path, default=ROOT / "reports" / "research" / "arsiv_yari_olcum.json")
    a = ap.parse_args()
    df = load()
    res = measure(df)
    if a.olc:
        a.rapor.parent.mkdir(parents=True, exist_ok=True)
        a.rapor.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res.items():
        print(f"{k:12s} {v['nesine']:26s} n={v['olcum_n']:5d} yariLL {v['yari_gol_logloss_A']:.5f}->{v['yari_gol_logloss_B']:.5f} "
              f"blendBrier {v['blend_brier_A']:.5f}->{v['blend_brier_B']:.5f} {v['karar']}")
    if a.yaz:
        print("yazıldı:", write(df, {k for k, v in res.items() if v["karar"] == "al"}))


if __name__ == "__main__":
    main()
