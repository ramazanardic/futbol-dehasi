"""Money report: does any kind of bet actually earn on Nesine? (user, 26 Nov: "sistem kazandırmıyor").

    QUANTFOOT_AI=claudetahmin python scripts/getiri_raporu.py      # -> tahminler/<ai>/takip/getiri.md

Over every settled day (the AI's own folder plus the shared archive up to 19 Nov) it settles each selection that
meets the leg rule (Nesine odds >= 1.20, probability >= 50 %) at 1 unit and reports hit rate and return per unit
by expected value (probability x Nesine odds - 1), probability band and price type, and the played coupons of the
ledger (stake, payout, net). A return near the expected value means the probabilities are right and the price
decides the result; only bets whose Nesine odds pay more than the true odds can earn over time.
"""

from __future__ import annotations

import collections
import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.paths import ai_area  # noqa: E402

BANDS = ((0.03, "EV ≥ +3 %"), (0.0, "EV 0 … +3 %"), (-0.05, "EV −5 … 0 %"), (-0.10, "EV −10 … −5 %"), (-9.0, "EV < −10 %"))


def ev_band(ev: float) -> str:
    return next(lbl for lo, lbl in BANDS if ev >= lo)


def day_dirs(area: Path) -> list[Path]:
    found = {}
    for base in (ROOT / "reports" / "daily", area):
        for p in base.iterdir() if base.exists() else []:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name) and (p / "takip_sonuc.json").exists() and (p / "takip_kayit.json").exists():
                found[p.name] = p
    return [found[k] for k in sorted(found)]


def selection_returns(days: list[Path]) -> dict[str, dict[str, list[float]]]:
    """{view: {group: [n, units returned, wins]}}."""
    out: dict[str, dict] = {v: collections.defaultdict(lambda: [0, 0.0, 0]) for v in ("ev", "p", "fiyat")}
    for d in days:
        store = json.loads((d / "takip_kayit.json").read_text(encoding="utf-8"))
        res = json.loads((d / "takip_sonuc.json").read_text(encoding="utf-8"))
        for code, r in res.items():
            if not r.get("completed") or code not in store:
                continue
            for name, won in (r.get("won") or {}).items():
                v = store[code]["s"].get(name)
                if not v:
                    continue
                p, odds, direct = float(v[0]), float(v[1]), bool(v[2])
                if odds < 1.20 or p < 0.50:
                    continue
                ret = (odds - 1) if won else -1.0
                lo = int(p * 10) * 10
                for view, key in (("ev", ev_band(p * odds - 1)), ("p", f"%{lo}–{lo + 10}"), ("fiyat", "borsa" if direct else "model")):
                    g = out[view][key]
                    g[0] += 1
                    g[1] += ret
                    g[2] += bool(won)
    return out


def ledger(area: Path) -> tuple[int, int, float, float]:
    n = won = 0
    stake = payout = 0.0
    for f in sorted((area / "defter").glob("placed_bets_*.csv")):
        with f.open(encoding="utf-8") as fh:
            coupons = {}
            for row in csv.DictReader(fh):
                coupons.setdefault(row["coupon_id"], row)
        for c in coupons.values():
            n += 1
            stake += float(c.get("stake_tl") or 0)
            if c.get("coupon_screen") in ("tuttu", "kazandı"):
                won += 1
                payout += float(c.get("payout_tl") or 0)
    return n, won, stake, payout


def to_markdown(days: list[Path], sel: dict, led: tuple) -> str:
    names = {"ev": "Beklenen değere göre", "p": "Olasılığa göre", "fiyat": "Fiyat türüne göre"}
    md = ["# Getiri raporu — hangi bahis gerçekten kazandırıyor?", "",
          f"Sonuçlanmış günler: {', '.join(d.name for d in days)}. Her seçim 1 birim, Nesine oranıyla (oran ≥ 1,20, "
          "olasılık ≥ %50).", ""]
    n, won, stake, payout = led
    if n:
        md += [f"**Oynanan kuponlar (defter):** {n} kupon, {won} tuttu · yatırılan {stake:,.0f} TL · geri gelen "
               f"{payout:,.0f} TL · net **{payout - stake:+,.0f} TL**", ""]
    for view in ("ev", "p", "fiyat"):
        md += [f"## {names[view]}", "", "| Grup | Seçim | İsabet | Birim başına getiri |", "|---|---:|---:|---:|"]
        order = [lbl for _, lbl in BANDS] if view == "ev" else sorted(sel[view])
        for key in order:
            if key in sel[view]:
                c, r, w = sel[view][key]
                md.append(f"| {key} | {c} | %{100 * w / c:.1f} | %{100 * r / c:+.1f} |")
        md.append("")
    md += ["Getiri, beklenen değere yakınsa olasılıklar doğrudur ve sonucu fiyat belirler: Nesine oranı gerçek oranın "
           "altındaysa (EV < 0) bahis uzun vadede kaybettirir. Çok bacaklı kuponda bu eksik her bacakta çarpılır.", ""]
    return "\n".join(md)


def main() -> None:
    area = ai_area(ROOT)
    days = day_dirs(area)
    out = area / "takip" / "getiri.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(days, selection_returns(days), ledger(area)), encoding="utf-8")
    print(f"{len(days)} gün -> {out}")


if __name__ == "__main__":
    main()
