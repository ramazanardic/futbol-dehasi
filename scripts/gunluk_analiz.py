"""One-page analysis of every Nesine match of a betting day, built fresh from that day's run.

    python scripts/gunluk_analiz.py --tarih 2026-11-20      # after nesine_global.py for the same day

Per match: price source and reliability, research (form, table, rest, absences), 1X2, expected goals, 2.5 Over,
BTTS, the three most likely scores, the most likely HT/FT, and the most probable bettable selection (Nesine odds
>= 1.20) under the coupon rules learned from the tracked results (no model HT/FT or second-half result legs,
no low-confidence prices, no correct-score style legs). Output: reports/daily/<date>/gunluk_analiz.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import DAILY, NESINE_ONLY_STATUS, PREDICTIONS_FILE, TSI  # noqa: E402

EXCLUDED_MODEL = ("İY/MS", "2Y 0", "2Y 1", "2Y 2")


def _form(r: dict, side: str) -> str:
    t = ((r or {}).get("teams") or {}).get(side) or {}
    bits = []
    if t.get("form"):
        bits.append(t["form"])
    tab = t.get("table") or {}
    if tab.get("rank"):
        bits.append(f"{int(tab['rank'])}./{tab['size']}")
    if t.get("rest_days") not in (None, "-"):
        bits.append(f"{t['rest_days']}g dinlenme")
    out = [x["name"] for x in t.get("likely_absent") or [] if "rotasyon" not in x.get("reason", "")][:2]
    if out:
        bits.append("yok: " + ", ".join(out))
    return " ".join(bits) or "-"


def best_pick(m: dict) -> tuple[dict | None, str]:
    """Most probable selection with Nesine odds >= 1.20 that the coupon rules allow; reason when none."""
    if m["status"] == NESINE_ONLY_STATUS:
        return None, "düşük güven: kupona alınmaz"
    if m["status"] != "fiyatlandı":
        return None, "global fiyat yok"
    if m["reference"].startswith("ESPN"):
        return None, "yalnız ESPN fiyatı (keskin değil)"
    ok = [s for s in m["selections"] if s["odds"] >= 1.20 and s["ev"] <= 0.25
          and (s.get("direct") or not s["name"].startswith(EXCLUDED_MODEL))
          and "Skor" not in s["name"] and not s["name"].startswith("İki Yarıda")]
    if not ok:
        return None, "1,20+ uygun seçim yok"
    return max(ok, key=lambda s: (s["fair_prob"], s["odds"])), ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    args = ap.parse_args()
    d = DAILY / args.tarih
    data = json.loads((d / "nesine_global.json").read_text(encoding="utf-8"))
    store = json.loads((d / PREDICTIONS_FILE).read_text(encoding="utf-8")) if (d / PREDICTIONS_FILE).exists() else {}
    ms = sorted(data["matches"], key=lambda m: m["kickoff"])
    glob = [m for m in ms if m["status"] == "fiyatlandı"]
    low = [m for m in ms if m["status"] == NESINE_ONLY_STATUS]
    lines = [f"# {args.tarih} — günün bütün maçları ({len(ms)} maç, analiz {data['generated_at'][11:16]} TSİ)", "",
             f"Global borsa fiyatlı: **{len(glob)}** · düşük güven (yalnız Nesine fiyatı): **{len(low)}** · "
             f"fiyatsız: {len(ms) - len(glob) - len(low)}. Olasılıklar maç başlamadan önce yenilenir; kupon kurarken "
             "taze fiyat çekilir.", "",
             "Dünkü sonuçlardan uygulanan dersler: düşük güvenli tahminler kupona girmez (19 Kasım'da %86 ve %80 verilen "
             "iki düşük güvenli favori yattı); modelden türetilen İY/MS ve 2. yarı sonucu bacak olmaz; skor, İY/MS ve iki "
             "yarıda KG yalnız bilgi olarak verilir (18–19 Kasım'da bu türden 13 kuponun hepsi yattı).", "",
             "**Düşük güven** satırları: hiçbir ücretsiz keskin kaynak (Smarkets, Matchbook, Betfair, Pinnacle) bu maçları "
             "listelemiyor; olasılıklar yalnız Nesine'nin kendi oranından. 19 Kasım ölçümü: bu tahminlerin hatası global "
             "fiyatlıların ~1,6 katı (Brier 0,257 / 0,157), %80+ verilenlerin yalnız üçte biri tuttu. Bilgi amaçlıdır.", "",
             "| Saat | Lig | Maç | Kaynak | 1 / X / 2 | Gol (ev-dep) | 2,5Ü | KG | En olası skorlar | En olası İY/MS | "
             "En güvenilir tercih (Nesine ≥1,20) | Ev formu | Dep formu |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m in ms:
        if m["status"] not in ("fiyatlandı", NESINE_ONLY_STATUS):
            lines.append(f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | fiyat yok | - | - | - | - | - | - | - | - | - |")
            continue
        sel = {s["name"]: s["fair_prob"] for s in m["selections"]}
        f1x2 = m.get("fair_1x2") or [None] * 3
        dist = (store.get(str(m["code"])) or {}).get("dist") or {}
        scores = ", ".join(f"{k} %{v * 100:.0f}" for k, v in list((dist.get("ft") or {}).items())[:3]) or "-"
        htft = next(iter((dist.get("htft") or {}).items()), None)
        pick, why = best_pick(m)
        pick_s = (f"{pick['market']}: {pick['selection']} — %{pick['fair_prob'] * 100:.0f}, {pick['odds']:.2f} "
                  f"({'doğrudan' if pick.get('direct') else 'model'})") if pick else f"_{why}_"
        src = "düşük güven" if m["status"] == NESINE_ONLY_STATUS else m["reference"].split(" (")[0]
        warn = []
        if m["mu_home"] + m["mu_away"] > 5:
            warn.append("aşırı gol beklentisi")
        if (m.get("research") or {}).get("flags"):
            warn.append("⚠ " + "; ".join(m["research"]["flags"]))
        lines.append(
            f"| {m['kickoff'][11:]} | {m['league']} | {m['home']} - {m['away']} | {src}{' · ' + ' · '.join(warn) if warn else ''} | "
            + (f"%{f1x2[0] * 100:.0f} / %{f1x2[1] * 100:.0f} / %{f1x2[2] * 100:.0f}" if f1x2[0] is not None else "-")
            + f" | {m['mu_home']:.2f}-{m['mu_away']:.2f} | "
            f"{'%' + format(sel['2.5 Üst'] * 100, '.0f') if '2.5 Üst' in sel else '-'} | "
            f"{'%' + format(sel['KG Var'] * 100, '.0f') if 'KG Var' in sel else '-'} | {scores} | "
            f"{(htft[0] + ' %' + format(htft[1] * 100, '.0f')) if htft else '-'} | {pick_s} | "
            f"{_form(m.get('research'), 'home')} | {_form(m.get('research'), 'away')} |")
    lines += ["", "Ayrıntılı maç dosyaları (her bahis ailesi, araştırma, skor tabloları): "
              f"`reports/daily/{args.tarih}/mac_dosyalari/<Nesine kodu>.md`."]
    (d / "gunluk_analiz.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(ms)} maç -> {(d / 'gunluk_analiz.md').relative_to(DAILY.parents[1])}")


if __name__ == "__main__":
    main()
