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
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import derin_arastirma as dr  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))
from quantfoot.evaluation.auto_learn import calibrated_probability, load_live_calibration, market_family  # noqa: E402
from quantfoot.markets.market_calibration import calibrate_market_probability, load_market_calibration  # noqa: E402

MIN_ODDS, MIN_PROB = 1.20, 0.55
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


def priced_selections(m: dict, calibration: dict | None = None) -> list[dict]:
    """Calibrate the match's global quotes without applying coupon thresholds."""
    if m.get("status") not in (None, "fiyatlandı"):
        return []
    market_calibration = load_market_calibration()
    selections = []
    for selection in m.get("selections") or []:
        raw = selection.get("fair_prob")
        if raw is None or not math.isfinite(raw) or not 0 <= raw <= 1:
            continue
        direct = bool(selection.get("direct"))
        p = calibrated_probability(raw, direct, calibration)
        p = calibrate_market_probability(selection["name"], p, m.get("league"), market_calibration, direct=direct)
        selections.append({**selection, "p": p, "family": market_family(selection["name"])})
    return selections


def top_five(m: dict, calibration: dict | None = None) -> list[dict]:
    """Choose the most probable selection in each family, then rank up to five families."""
    if calibration is None:
        calibration = load_live_calibration()
    ranked = sorted(priced_selections(m, calibration),
                    key=lambda x: (-x["p"], not x.get("direct"), x["family"], x["name"]))
    best = {}
    for selection in ranked:
        family = selection["family"]
        best.setdefault(family, {"family": family, "name": selection["name"], "p": selection["p"]})
        if len(best) == 5:
            break
    return list(best.values())


def format_top_five(selections: list[dict] | None) -> str:
    if not selections:
        return "Doğrulanmış olasılık yok"
    parts = [f"{x['name']} %{100 * x['p']:.1f}".replace(".", ",") for x in selections]
    return " · ".join(parts).replace("|", "/")


def family_table(m: dict, games: dict | None = None, ft_only: bool = False, calibration: dict | None = None) -> list[dict]:
    """All offered selections grouped by market family, with research eligibility."""
    import wiki_gecmis as wg
    fams: dict[str, list[dict]] = {}
    priced = priced_selections(m, calibration)
    quotes = {s["key"]: s for s in priced if "key" in s}
    for offer in m.get("offered_selections", priced):
        selection = quotes.get(offer.get("key"), offer)
        if "p" not in selection:
            selection = {**selection, "p": None}
        family = selection.get("family") or market_family(selection["name"])
        fams.setdefault(family, []).append(selection)
    for label in m.get("untranslated_selections") or []:
        fams.setdefault("Eşlenemeyen Nesine pazarları", []).append(
            {"market": "", "selection": label, "p": None, "odds": None}
        )
    out = []
    for fam in sorted(fams, key=lambda f: FAMILY_ORDER.index(f) if f in FAMILY_ORDER else len(FAMILY_ORDER)):
        sels = sorted(fams[fam], key=lambda x: -(x["p"] or 0))
        rows, rejected = [], []
        for x in sels:
            label = f"{x['market'].strip()}: {x['selection']}" if x["market"] else x["selection"]
            if x["p"] is None or x["odds"] < MIN_ODDS or x["p"] < MIN_PROB:
                reason = ("Pazar eşlemesi yok" if not x["market"] else "Doğrulanmış fiyat yok") if x["p"] is None else "Araştırma eşiğinin altında"
                rejected.append({"label": label, "p": x["p"], "odds": x["odds"], "reason": reason})
                continue
            mean, n, _ = _history(x["name"], games, ft_only)
            hist = {"mean": mean, "home_n": n, "away_n": n}
            verdict = (wg.verdict if ft_only else dr.verdict)(x["p"], hist)
            rows.append({"label": f"{x['market'].strip()}: {x['selection']}", "name": x["name"], "p": x["p"], "odds": x["odds"],
                         "direct": bool(x.get("direct")), "hist": mean, "n": n, "verdict": verdict})
        other = next((x for x in rejected if x["p"] is not None and x["odds"] >= MIN_ODDS), None) if not rows else None
        out.append({"family": fam, "suitable": rows, "best_other": other, "other": rejected})
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
          "Nesine’deki açık seçimler ailelerine göre listelenir. Takım geçmişi testi için oran ≥ 1,20 ve olasılık ≥ %55 gerekir. "
          "Takım geçmişi aynı bahsin iki takımın son maçlarında tutma oranını gösterir (ev sahibi evinde, "
          "deplasman deplasmanda). Borsa = doğrudan global fiyat, model = gol modelinden türetilmiş.", ""]
    ev = lambda p, odds: "—" if p is None or odds is None else f"%{100 * (p * odds - 1):+.1f}"  # noqa: E731
    for row, table in items:
        if not table:
            continue
        md += [f"## {row['kickoff'][11:16]} {row['match']} — {row['league']}", ""]
        md += [f"**En yüksek 5 aile olasılığı** · {format_top_five(row.get('en_yuksek_5'))}", ""]
        best = best_families(table)
        if best:
            md += ["**En uygun aileler:** " + " · ".join(f"{fam}: {r['label']} ({pct(r['p'])}, {r['odds']:.2f}, {r['verdict']})"
                                                          for fam, r in best), ""]
        md += ["| Aile | Seçim | Olasılık | Oran | Beklenen değer | Fiyat | Takım geçmişi | İşaret |", "|---|---|---|---|---|---|---|---|"]
        for f in table:
            if f["suitable"]:
                for i, r in enumerate(f["suitable"]):
                    md.append(f"| {f['family'] if i == 0 else ''} | {r['label']} | {pct(r['p'])} | {r['odds']:.2f} | {ev(r['p'], r['odds'])} | "
                              f"{'borsa' if r['direct'] else 'model'} | {pct(r['hist'])} ({r['n']}) | {r['verdict']} |")
            for i, r in enumerate(f["other"]):
                odds = f"{r['odds']:.2f}" if r["odds"] is not None else "—"
                md.append(f"| {f['family'] if i == 0 and not f['suitable'] else ''} | {r['label']} | "
                          f"{pct(r['p'])} | {odds} | {ev(r['p'], r['odds'])} | | | {r['reason']} |")
        md.append("")
    return "\n".join(md)


def build_day(date: str, *, window: str | None = None) -> Path:
    from derin_tahmin import in_window
    out = dr.AREA / date
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    cal = load_live_calibration() or {}
    items = []
    by_code = {str(r["code"]): r for r in rows}
    now = dt.datetime.now(dr.TSI)
    for code, m in sorted(ms.items(), key=lambda entry: entry[1]["kickoff"]):
        if (m.get("price_tier") == "ozel_bahis" or dt.datetime.fromisoformat(m["kickoff_iso"]) <= now
                or not in_window(m["kickoff"], window)):
            continue
        row = by_code.get(code) or {"kickoff": m["kickoff"], "match": f"{m['home']} - {m['away']}", "league": m["league"]}
        games, ft_only = games_for(m, row) if m.get("status") == "fiyatlandı" else (None, False)
        table = family_table(m, games, ft_only, cal)
        row["families"] = table
        row["en_yuksek_5"] = top_five(m, cal)
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
