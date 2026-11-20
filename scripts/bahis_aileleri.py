"""Every bet family of a match with its suitable selections and probabilities (user request, 21 Nov: "bir karşılaşmayı
araştırırken tüm bahis ailelerinden hangileri o karşılaşmaya uygun, % ile listele").

Per match and per family (Maç sonucu, Çifte şans, Alt/Üst, Gol aralığı, Karşılıklı gol, İY / 2Y karşılıklı gol,
İlk yarı, İkinci yarı, İY/MS, Ev / Deplasman golleri, Handikap, İlk gol, Tek/Çift, Korner, Kombine …):

* the selections Nesine offers that meet the leg rule (Nesine odds >= 1.20, probability >= 55 %), best first;
  the probability is the global one corrected by the settled-history calibration (auto_learn prob_shift);
* each is settled on both teams' recent games (ESPN half scores; Wikipedia: full-time bets only) -> history rate
  and verdict, the same test the coupon builder uses;
* a family with no suitable selection shows its most probable one, so it is clear why it does not fit.

Families are then ranked by their best selection that history does not contradict ("en uygun aileler").

    python scripts/bahis_aileleri.py --tarih 2026-11-20      # -> tahminler/<ai>/<date>/bahis_aileleri.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration, market_family  # noqa: E402

MIN_ODDS, MIN_PROB = 1.20, 0.55
PER_FAMILY = 3
FAMILY_ORDER = ("Maç sonucu", "Çifte şans", "Alt/Üst", "Gol aralığı", "Karşılıklı gol", "İY karşılıklı gol",
                "2Y karşılıklı gol", "İlk yarı", "İkinci yarı", "İY/MS", "Ev sahibi golleri", "Deplasman golleri",
                "Handikap", "İlk gol", "Tek/Çift", "Korner", "İY korner", "Kombine (A & B)", "Diğer")


def _history(name: str, games: dict | None, ft_only: bool) -> tuple[float | None, int, str]:
    if not games or not games.get("home") or not games.get("away"):
        return None, 0, "geçmiş yok"
    if ft_only:
        import wiki_gecmis as wg
        hist = wg.leg_history(name, games["home"], games["away"])
        return hist["mean"], min(hist["home_n"], hist["away_n"]), ""
    hist = dr.leg_history(name, games["home"], games["away"])
    return hist["mean"], min(hist["home_n"], hist["away_n"]), ""


def family_table(m: dict, games: dict | None = None, ft_only: bool = False, calibration: dict | None = None) -> list[dict]:
    """[{family, suitable: [...], best_other: {...} | None}] in FAMILY_ORDER (families Nesine offers only)."""
    import wiki_gecmis as wg
    fams: dict[str, list[dict]] = {}
    for s in m.get("selections") or []:
        p = calibrated_probability(s["fair_prob"], bool(s.get("direct")), calibration)
        fams.setdefault(market_family(s["name"]), []).append({**s, "p": p})
    out = []
    for fam in sorted(fams, key=lambda f: FAMILY_ORDER.index(f) if f in FAMILY_ORDER else len(FAMILY_ORDER)):
        sels = sorted(fams[fam], key=lambda x: -x["p"])
        ok = [x for x in sels if x["odds"] >= MIN_ODDS and x["p"] >= MIN_PROB][:PER_FAMILY]
        rows = []
        for x in ok:
            mean, n, _ = _history(x["name"], games, ft_only)
            hist = {"mean": mean, "home_n": n, "away_n": n}
            verdict = (wg.verdict if ft_only else dr.verdict)(x["p"], hist)
            rows.append({"label": f"{x['market'].strip()}: {x['selection']}", "name": x["name"], "p": x["p"], "odds": x["odds"],
                         "direct": bool(x.get("direct")), "hist": mean, "n": n, "verdict": verdict})
        other = next(({"label": f"{x['market'].strip()}: {x['selection']}", "p": x["p"], "odds": x["odds"]}
                      for x in sels if x["odds"] >= MIN_ODDS), None) if not ok else None
        out.append({"family": fam, "suitable": rows, "best_other": other})
    return out


def best_families(table: list[dict], k: int = 3) -> list[tuple[str, dict]]:
    """Families ranked by their most probable suitable selection that history does not contradict."""
    cands = []
    for f in table:
        good = [r for r in f["suitable"] if not r["verdict"].startswith("⚠")]
        if good:
            top = max(good, key=lambda r: (r["verdict"].startswith("✓"), r["p"]))
            cands.append((f["family"], top))
    return sorted(cands, key=lambda c: (-c[1]["verdict"].startswith("✓"), -c[1]["p"]))[:k]


def games_for(m: dict, row: dict) -> tuple[dict | None, bool]:
    """Recent games of both teams for a research row (ESPN cache first, then Wikipedia)."""
    if row.get("games"):
        return row["games"], bool(row.get("games_ft_only"))
    tmp = dr.research_match(m, [])
    if tmp.get("espn") and (tmp.get("games") or {}).get("home"):
        return tmp["games"], False
    import wiki_gecmis as wg
    tmp = {"league": m["league"], "legs": [], "teams": {}}
    if wg.research(tmp, m):
        return tmp["games"], True
    return None, False


def to_markdown(date: str, items: list[tuple[dict, list[dict]]]) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    md = [f"# {date} — maç başına bütün bahis aileleri ({dt.datetime.now(dr.TSI):%H:%M} TSİ)", "",
          "Her ailede kurala uyan seçimler (Nesine oranı ≥ 1,20, olasılık ≥ %55; olasılık bitmiş günlere göre düzeltilmiş), "
          "en olasısı önce. 'Takım geçmişi': aynı bahsin iki takımın son maçlarında tutma oranı (ev sahibi evinde, "
          "deplasman deplasmanda). Borsa = doğrudan global fiyat, model = gol modelinden türetilmiş.", ""]
    for row, table in items:
        if not table:
            continue
        md += [f"## {row['kickoff'][11:16]} {row['match']} — {row['league']}", ""]
        best = best_families(table)
        if best:
            md += ["**En uygun aileler:** " + " · ".join(f"{fam}: {r['label']} ({pct(r['p'])}, {r['odds']:.2f}, {r['verdict']})"
                                                          for fam, r in best), ""]
        md += ["| Aile | Seçim | Olasılık | Oran | Fiyat | Takım geçmişi | İşaret |", "|---|---|---|---|---|---|---|"]
        for f in table:
            if f["suitable"]:
                for i, r in enumerate(f["suitable"]):
                    md.append(f"| {f['family'] if i == 0 else ''} | {r['label']} | {pct(r['p'])} | {r['odds']:.2f} | "
                              f"{'borsa' if r['direct'] else 'model'} | {pct(r['hist'])} ({r['n']}) | {r['verdict']} |")
            else:
                o = f["best_other"]
                md.append(f"| {f['family']} | uygun seçim yok" + (f" (en olası: {o['label']} {pct(o['p'])}, {o['odds']:.2f})" if o else "")
                          + " | | | | | |")
        md.append("")
    return "\n".join(md)


def build_day(date: str) -> Path:
    out = dr.AREA / date
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    cal = load_live_calibration() or None
    items = []
    for row in rows:
        m = ms.get(str(row["code"]))
        if not m:
            continue
        games, ft_only = games_for(m, row)
        table = family_table(m, games, ft_only, cal)
        row["families"] = table
        items.append((row, table))
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    path = out / "bahis_aileleri.md"
    path.write_text(to_markdown(date, items), encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    args = ap.parse_args()
    print(f"-> {build_day(args.tarih)}")


if __name__ == "__main__":
    main()
