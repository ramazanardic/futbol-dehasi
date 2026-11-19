"""Match dossier: research summary, every bet family with its probability (most certain first), scores.

    python scripts/mac_dosyasi.py --mac "Vasco"             # one match (name substring), today
    python scripts/mac_dosyasi.py --tarih 2026-11-21        # every not-started priced match of a day

Probabilities come from the global sharp price: a selection the exchange quotes itself uses that quote
("doğrudan"); every other selection comes from the goal distribution fitted to that price ("model").
Within a family the outcomes add up to 100 %. Nesine is shown only as the place to bet (its odds).
Output: reports/daily/<date>/mac_dosyalari/<code>.md (+ printed).
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nesine_global as ng  # noqa: E402

from quantfoot.markets.goal_markets import goal_probability  # noqa: E402

LINES = ("0.5", "1.5", "2.5", "3.5", "4.5", "5.5")


def families(home: str, away: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """(family, [(label, selection name in goal-grammar)]) for every family the goal distribution prices."""
    side = {"1": home, "0": "beraberlik", "2": away}
    fam = [
        ("Maç sonucu", [(f"1 ({home})", "MS 1"), ("X (beraberlik)", "MS 0"), (f"2 ({away})", "MS 2")]),
        ("Çifte şans", [("1-X", "ÇŞ 1X"), ("1-2 (beraberlik olmaz)", "ÇŞ 12"), ("X-2", "ÇŞ X2")]),
        ("Karşılıklı gol", [("Var", "KG Var"), ("Yok", "KG Yok")]),
        ("Tek / Çift", [("Tek", "Tek"), ("Çift", "Çift")]),
        ("Toplam gol aralığı", [("0-1 gol", "0-1 Gol"), ("2-3 gol", "2-3 Gol"), ("4-5 gol", "4-5 Gol"), ("6+ gol", "6+ Gol")]),
    ]
    for ln in LINES:
        fam.append((f"Toplam gol {ln.replace('.', ',')} Alt/Üst", [(f"{ln.replace('.', ',')} Üst", f"{ln} Üst"),
                                                                 (f"{ln.replace('.', ',')} Alt", f"{ln} Alt")]))
    fam += [
        ("1. yarı sonucu", [(f"İY 1 ({home})", "İY 1"), ("İY X", "İY 0"), (f"İY 2 ({away})", "İY 2")]),
        ("1. yarı çifte şans", [("İY 1-X", "İY ÇŞ 1X"), ("İY 1-2", "İY ÇŞ 12"), ("İY X-2", "İY ÇŞ X2")]),
        ("2. yarı sonucu", [(f"2Y 1 ({home})", "2Y 1"), ("2Y X", "2Y 0"), (f"2Y 2 ({away})", "2Y 2")]),
        ("1. yarı karşılıklı gol", [("İY KG Var", "İY KG Var"), ("İY KG Yok", "İY KG Yok")]),
        ("2. yarı karşılıklı gol", [("2Y KG Var", "2Y KG Var"), ("2Y KG Yok", "2Y KG Yok")]),
        ("İlk yarı / maç sonucu", [(f"{a}/{b}", f"İY/MS {a}/{b}") for a in "102" for b in "102"]),
        ("En çok gol olan yarı", [("1. yarı", "En Çok Gol 1Y"), ("Eşit", "En Çok Gol Eşit"), ("2. yarı", "En Çok Gol 2Y")]),
        ("Kaç farkla kazanır", [(f"{home} 1 farkla", "Fark Ev 1"), (f"{home} 2 farkla", "Fark Ev 2"), (f"{home} 3+ farkla", "Fark Ev 3+"),
                                ("beraberlik", "Fark 0"), (f"{away} 1 farkla", "Fark Dep 1"), (f"{away} 2 farkla", "Fark Dep 2"),
                                (f"{away} 3+ farkla", "Fark Dep 3+")]),
        ("Handikap (-1, ev sahibine)", [(f"{home} 2+ farkla", "Hnd(-1) 1"), (f"{home} tam 1 farkla", "Hnd(-1) 0"),
                                        (f"{away} kaybetmez", "Hnd(-1) 2")]),
        ("Maç sonucu & karşılıklı gol", [(f"{x} & KG {k}", f"MS {c} & KG {k}") for c, x in side.items() for k in ("Var", "Yok")]),
        ("Maç sonucu & 2,5 Alt/Üst", [(f"{x} & 2,5 {u}", f"MS {c} & 2.5 {u}") for c, x in side.items() for u in ("Üst", "Alt")]),
    ]
    for ln in ("0.5", "1.5", "2.5"):
        fam.append((f"1. yarı {ln.replace('.', ',')} Alt/Üst", [(f"İY {ln.replace('.', ',')} Üst", f"İY {ln} Üst"),
                                                               (f"İY {ln.replace('.', ',')} Alt", f"İY {ln} Alt")]))
    for ln in ("0.5", "1.5"):
        fam.append((f"2. yarı {ln.replace('.', ',')} Alt/Üst", [(f"2Y {ln.replace('.', ',')} Üst", f"2Y {ln} Üst"),
                                                               (f"2Y {ln.replace('.', ',')} Alt", f"2Y {ln} Alt")]))
    for team, label in (("Ev", home), ("Dep", away)):
        for ln in ("0.5", "1.5", "2.5"):
            fam.append((f"{label} gol {ln.replace('.', ',')} Alt/Üst", [(f"{label} {ln.replace('.', ',')} Üst", f"{team} {ln} Üst"),
                                                                       (f"{label} {ln.replace('.', ',')} Alt", f"{team} {ln} Alt")]))
        fam.append((f"{label} 1. yarı gol", [(f"{label} İY gol atar", f"{team} İY 0.5 Üst"), (f"{label} İY gol atamaz", f"{team} İY 0.5 Alt")]))
        fam.append((f"{label} yarılar", [(f"{label} en az bir yarıyı kazanır", f"{team} En Az Bir Yarıyı Kazanır"),
                                         (f"{label} her iki yarıyı kazanır", f"{team} Her İki Yarıyı Kazanır"),
                                         (f"{label} iki yarıda da gol atar", f"{team} İki Yarıda Gol"),
                                         (f"{label} gol yemez", f"{team} Gol Yemez"),
                                         (f"{label} gol yemeden kazanır", f"{team} Gol Yemeden Kazanır")]))
    fam.append(("Her iki yarıda karşılıklı gol", [("İki yarıda da KG var", "İki Yarıda KG Var")]))
    return fam


def _prob(name: str, priced: dict) -> tuple[float, bool]:
    if name in priced["quoted"]:
        return priced["quoted"][name], True
    # 1X2 and the quoted O/U line are the fit inputs: their probability is the exchange's own
    return goal_probability(name, priced["joint"]), name in priced.get("inputs", ())


def score_tables(joint: np.ndarray, home: str, away: str, top: int = 12) -> list[str]:
    g = joint.shape[0]
    ft = np.zeros((2 * g - 1, 2 * g - 1))
    ht = joint.sum(axis=(2, 3))
    for h1 in range(g):
        for a1 in range(g):
            ft[h1:h1 + g, a1:a1 + g] += joint[h1, a1]
    rows = sorted(((ft[i, j], i, j) for i in range(ft.shape[0]) for j in range(ft.shape[1])), reverse=True)
    out = [f"### Maç sonu skoru ({home} - {away})", "", "| Skor | Olasılık |", "|---|---|"]
    out += [f"| {i}-{j} | %{p * 100:.1f} |" for p, i, j in rows[:top]]
    out.append(f"| diğer tüm skorlar | %{(1 - sum(p for p, _, _ in rows[:top])) * 100:.1f} |")
    hrows = sorted(((ht[i, j], i, j) for i in range(g) for j in range(g)), reverse=True)
    out += ["", "### İlk yarı skoru", "", "| Skor | Olasılık |", "|---|---|"]
    out += [f"| {i}-{j} | %{p * 100:.1f} |" for p, i, j in hrows[:6]]
    hf = sorted(((joint[h1, a1, h2, a2], h1, a1, h1 + h2, a1 + a2) for h1 in range(g) for a1 in range(g)
                 for h2 in range(g) for a2 in range(g)), reverse=True)
    agg: dict[tuple, float] = {}
    for p, h1, a1, fh, fa in hf:
        agg[(h1, a1, fh, fa)] = agg.get((h1, a1, fh, fa), 0.0) + p
    out += ["", "### İlk yarı / maç skoru", "", "| İY / MS | Olasılık |", "|---|---|"]
    out += [f"| {k[0]}-{k[1]} / {k[2]}-{k[3]} | %{v * 100:.1f} |" for k, v in sorted(agg.items(), key=lambda kv: -kv[1])[:8]]
    return out


def dossier(m: dict) -> str:
    priced = ng.PRICED[m["code"]]
    nes = {s["name"]: s["odds"] for s in m.get("selections", [])}
    reliability = "global borsa fiyatı" if m["status"] == "fiyatlandı" else "DÜŞÜK GÜVEN (global fiyat yok, Nesine oranından)"
    lines = [f"# {m['kickoff']} · {m['home']} - {m['away']} ({m['league']})", "",
             f"Kaynak: {m['reference']} — {reliability}. Beklenen gol: {m['mu_home']:.2f} - {m['mu_away']:.2f}. "
             "Bir ailenin sonuçları toplamda %100 eder. 'doğrudan' = borsanın bu seçimi kendisi fiyatlıyor; "
             "'model' = global fiyattan gol dağılımıyla.", ""]
    r = m.get("research") or {}
    if r.get("teams") or r.get("user_absences"):
        h, a = ng._side_rows(r, "home"), ng._side_rows(r, "away")
        lines += ["## Araştırma", "", "| | Ev | Deplasman |", "|---|---|---|"]
        for key in dict.fromkeys(list(h) + list(a)):
            lines.append(f"| {key} | {h.get(key, '-')} | {a.get(key, '-')} |")
        flags = (r.get("flags") or []) + ((r.get("user_absences") or {}).get("alerts") or [])
        lines += ["", f"Uyarılar: {'; '.join(flags) or '-'}", ""]
    else:
        lines += ["## Araştırma", "", "_Bu maç için form / sakatlık verisi bulunamadı._", ""]

    rows = []
    for fam, outs in families(m["home"], m["away"]):
        for label, name in outs:
            try:
                p, direct = _prob(name, priced)
            except KeyError:
                continue
            rows.append((p, fam, label, direct, nes.get(name)))
    first_goal = priced["timing"]
    for label, key in ((f"İlk golü {m['home']} atar", "İlk Gol Ev"), (f"İlk golü {m['away']} atar", "İlk Gol Dep"), ("Gol olmaz", "İlk Gol Yok")):
        if key in first_goal:
            rows.append((first_goal[key], "İlk gol", label, False, nes.get(key)))

    def fmt(p, fam, label, direct, odds):
        return f"| %{p * 100:.1f} | {fam} | {label} | {'doğrudan' if direct else 'model'} | {odds:.2f} |" if odds else \
               f"| %{p * 100:.1f} | {fam} | {label} | {'doğrudan' if direct else 'model'} | Nesine'de yok |"

    lines += ["## Tüm tahminler — en garantiden aşağıya", "",
              "| Olasılık | Bahis ailesi | Sonuç | Kaynak | Nesine oranı |", "|---|---|---|---|---|"]
    lines += [fmt(*row) for row in sorted(rows, key=lambda x: -x[0])]
    lines += ["", "## Skor tahminleri", ""] + score_tables(priced["joint"], m["home"], m["away"])
    lines += ["", "> En olası skor bile genellikle %10–18 civarındadır; skor tahmini hiçbir zaman garanti değildir."]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(ng.TSI).date().isoformat())
    ap.add_argument("--mac", help="Maç adında geçen metin (ör. 'Vasco'); yoksa günün tüm başlamamış maçları")
    args = ap.parse_args()
    matches, _, _ = ng.analyze_day(dt.date.fromisoformat(args.tarih), verbose=False)
    now = dt.datetime.now(ng.TSI)
    pick = [m for m in matches if m["code"] in ng.PRICED and dt.datetime.fromisoformat(m["kickoff_iso"]) > now
            and (not args.mac or args.mac.lower() in f"{m['home']} {m['away']}".lower())]
    out_dir = ng.DAILY / args.tarih / "mac_dosyalari"
    out_dir.mkdir(parents=True, exist_ok=True)
    for m in pick:
        text = dossier(m)
        (out_dir / f"{m['code']}.md").write_text(text, encoding="utf-8")
        if args.mac:
            print(text)
    print(f"{len(pick)} maç dosyası -> {out_dir.relative_to(ng.ROOT)}")


if __name__ == "__main__":
    main()
