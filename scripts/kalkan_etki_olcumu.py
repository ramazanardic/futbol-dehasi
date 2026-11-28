"""ESPN ilk-11 kalkanı (free_absences.lineup_record) 18–28 Kas denetim seçimlerinde: işaretli bacaklar gerçekten daha mı kötü?

Her seçim için takımın maçtan ÖNCEKİ son 5 ESPN maç kadrosundan düzenli ilk 11 çıkarılır (>= %60 başlama);
o maçın açıklanan ilk 11'inde düzenli oyuncu yoksa kalkan işaretlenir (1. kaleci / >=2 savunma / >=2 hücum / >=3 toplam).
Kalkan yalnız ilk 11 açıklandıktan sonra (maçtan ~1 sa önce) çalışabilir; ölçüm bu koşulu varsayar.

    python scripts/kalkan_etki_olcumu.py --havuz /workspace/fd_kaynak_2026-11-28
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data import free_absences as fa
from quantfoot.data import recent_form as rf


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - h) / d, 3), round((c + h) / d, 3)]


def _core(rec: dict) -> int:
    return rec["def_core_out"] + rec["att_core_out"] + rec["mid_core_out"]


KURALLAR = {  # kalkan sertliği: gevşek (varsayılan kural) -> sıkı
    "gevsek(gk|>=2 def|>=2 att|>=3 toplam)": lambda r: bool(r["gk1_out"] or r["def_core_out"] >= 2 or r["att_core_out"] >= 2 or _core(r) >= 3),
    "orta(gk|>=3 toplam)": lambda r: bool(r["gk1_out"] or _core(r) >= 3),
    "sik(gk|>=4 toplam)": lambda r: bool(r["gk1_out"] or _core(r) >= 4),
    "yalniz_kaleci": lambda r: bool(r["gk1_out"]),
}


def flagged(rec: dict) -> bool:
    return KURALLAR["gevsek(gk|>=2 def|>=2 att|>=3 toplam)"](rec)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--havuz", type=Path, default=Path("/workspace/fd_kaynak_2026-11-28"))
    ap.add_argument("--rows", type=Path, default=ROOT / "tahminler/grokbottahmin/2026-11-28/surum_denetimi/rows.json")
    ap.add_argument("--sonuc", type=Path, default=Path("/workspace/fd_denetim_2026-11-28/sonuc"))
    ap.add_argument("--out", type=Path, default=ROOT / "reports/research/kalkan_etki_2026-11-28.json")
    a = ap.parse_args()
    ozet = {}
    for f in (a.havuz / "espn_ozet").glob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        ozet[str(j["eid"])] = j["rosters"]
    pool = []
    for f in sorted((a.havuz / "espn_gunler").glob("*.json")):
        pool += rf.parse_espn_day(json.loads(f.read_text(encoding="utf-8")))
    idx: dict[str, list[dict]] = {}
    for r in pool:
        idx.setdefault(r["nh"], []).append(r)
        idx.setdefault(r["na"], []).append(r)
    info = {}
    for f in glob.glob(str(a.sonuc / "unlive_*.json")):
        for m in json.loads(Path(f).read_text(encoding="utf-8"))["d"]:
            info[m["C"]] = m
    rows = [r for r in json.loads(a.rows.read_text(encoding="utf-8")) if r.get("kod") in info and r.get("won") is not None and r.get("p") is not None]
    cache: dict[tuple, dict | None] = {}

    def side_rec(day: str, kod: int, side: str) -> dict | None:
        key = (day, kod, side)
        if key in cache:
            return cache[key]
        m = info[kod]
        kh, ka = rf._norm_team(m["HT"]), rf._norm_team(m["AT"])
        ev = [r for r in idx.get(kh, []) if r["na"] == ka and abs((dt.date.fromisoformat(r["day"]) - dt.date.fromisoformat(day)).days) <= 1]
        res = None
        if ev and str(ev[0]["eid"]) in ozet and side in ozet[str(ev[0]["eid"])]:
            e = ev[0]
            ro = ozet[str(e["eid"])][side]
            tk = e["nh"] if side == "home" else e["na"]
            past = sorted([r for r in idx[tk] if r["day"] < e["day"]], key=lambda r: r["day"])[-5:]
            prev = []
            for r in past:
                pr = ozet.get(str(r["eid"]), {})
                s = "home" if r["nh"] == tk else "away"
                if s in pr:
                    prev.append(pr[s])
            reg = fa.regulars(prev)
            xi = [p for p in ro["players"] if p["starter"]]
            if reg and len(xi) >= 11:
                res = fa.lineup_record(ro["team"], xi, reg)
        cache[key] = res
        return res

    ev_rows = []
    for r in rows:
        h, aw = side_rec(r["tarih"], r["kod"], "home"), side_rec(r["tarih"], r["kod"], "away")
        if not h or not aw:
            continue
        ev_rows.append({**r, "flag": flagged(h) or flagged(aw), "gk": h["gk1_out"] or aw["gk1_out"],
                        **{f"f_{k}": f(h) or f(aw) for k, f in KURALLAR.items()}})
    out = {"toplam_secim": len(rows), "kadro_kontrollu_secim": len(ev_rows),
           "kadro_kontrollu_mac": len({(r["tarih"], r["kod"]) for r in ev_rows}),
           "isaretli_mac": len({(r["tarih"], r["kod"]) for r in ev_rows if r["flag"]})}

    def summ(sub):
        n = len(sub)
        k = sum(1 for r in sub if r["won"])
        return {"n": n, "isabet": round(k / n, 3) if n else None, "ort_p": round(sum(r["p"] for r in sub) / n, 3) if n else None,
                "isabet_ci95": wilson(k, n)}

    for name, sel in (("hepsi", lambda r: True), ("P>=0.70", lambda r: r["p"] >= 0.70),
                      ("P>=0.70_ust_KG_var", lambda r: r["p"] >= 0.70 and any(t in r["secim"] for t in ("Üst", "KG Var"))),
                      ("P>=0.70_alt_KG_yok", lambda r: r["p"] >= 0.70 and any(t in r["secim"] for t in ("Alt", "KG Yok")))):
        sub = [r for r in ev_rows if sel(r)]
        out[name] = {"isaretli": summ([r for r in sub if r["flag"]]), "isaretsiz": summ([r for r in sub if not r["flag"]]),
                     "kaleci_eksik": summ([r for r in sub if r["gk"]])}
    import numpy as np

    def cluster_diff(sub, col, n=2000, seed=7):
        """(işaretsiz isabet) - (işaretli isabet): maç kümesi bootstrap %95 aralığı; ayrıca takvim-sapması (isabet - ort P)."""
        keys = sorted({(r["tarih"], r["kod"]) for r in sub})
        by = {k: [r for r in sub if (r["tarih"], r["kod"]) == k] for k in keys}
        rng = np.random.default_rng(seed)
        ds = []
        for _ in range(n):
            pick = [by[keys[i]] for i in rng.integers(0, len(keys), len(keys))]
            rr = [x for g in pick for x in g]
            f = [x for x in rr if x[col]]
            u = [x for x in rr if not x[col]]
            if f and u:
                ds.append((sum(x["won"] for x in u) / len(u) - sum(x["p"] for x in u) / len(u)) - (sum(x["won"] for x in f) / len(f) - sum(x["p"] for x in f) / len(f)))
        return {"fark_kalibrasyon_sapmasi": round(float(np.mean(ds)), 3), "ci95": [round(float(np.percentile(ds, 2.5)), 3), round(float(np.percentile(ds, 97.5)), 3)]}

    out["kural_karsilastirma"] = {}
    for k in KURALLAR:
        col = f"f_{k}"
        for nm, sub in (("hepsi", ev_rows), ("P>=0.70", [r for r in ev_rows if r["p"] >= 0.70])):
            out["kural_karsilastirma"][f"{k}|{nm}"] = {
                "isaretli_mac": len({(r["tarih"], r["kod"]) for r in sub if r[col]}), "isaretli": summ([r for r in sub if r[col]]),
                "isaretsiz": summ([r for r in sub if not r[col]]), "kume_bootstrap": cluster_diff(sub, col)}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
