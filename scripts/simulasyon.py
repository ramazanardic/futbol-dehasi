"""Monte Carlo simulation of every not-started match from all the evidence gathered (user request, 21 Nov: "her şeyi
detaylı araştırıp maçları karşılaştır, simülasyonlar yaratıp gerçek sonuca ulaş").

Per match, three independent views of each candidate bet are put side by side:

1. market   — the sharp global price, margin removed (no-vig probability with the settled-history correction, the
   same calibrated number as in derin_tahminler.json);
2. simulation — N simulated matches (Poisson goals per half) whose scoring rates do NOT use the market: the league
   model's xG (scripts/dc_model.py) and the teams' own recent attack/defence (ESPN or Wikipedia goals for/against),
   averaged when both exist, then the known absences (top scorer out: that team scores 8 % less; first-choice
   goalkeeper out: the opponent scores 8 % more); no independent data = no simulation view;
3. history  — how often the same bet won in both teams' recent games (deep-research rate; none when the verdict is
   'geçmiş yetersiz' — too few games — free-text notes never stand in for it).

A bet is "üçlü onay" (triple confirmed) only when all three views give it at least the leg floor (55 %) and the
simulation and history do not fall more than 5 points below the market. The table ranks bets by the lowest of the
three views, i.e. by the most pessimistic evidence. The main pick (update_picks) is the triple-confirmed bet with the
highest calibrated EV (market p × Nesine odds − 1 ≥ settings.PICK_MIN_EV): evidence filters, value decides.
League base rates (Data Lake) are display-only context, not an input.

Nothing here can know a result in advance; the simulation tells how often a bet wins in matches like this one.

    python scripts/simulasyon.py --tarih 2026-11-20 [--n 20000]   # -> tahminler/<ai>/<date>/simulasyon.md / .json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import re
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc_model  # noqa: E402
import elo_gorus  # noqa: E402
import derin_arastirma as dr  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402

HT_SHARE = 0.44        # first-half share of goals (184k matches in the repo's archive, docs/markets.md)
HT_PRIOR = 20.0        # goals of prior weight when a match's own first-half share is estimated
ABSENCE = 0.08
FLOOR, MAX_GAP = 0.55, 0.05
G = 9                  # goals per team per half kept in the joint grid


def half_share(row: dict) -> float:
    """First-half share of goals in both teams' recent games (half scores), shrunk towards the 44 % league norm."""
    g1 = gt = 0
    for side in ("home", "away"):
        for g in ((row.get("games") or {}).get(side) or []):
            f, a = g.get("for") or (None, None), g.get("against") or (None, None)
            if None in (f[0], a[0]):
                continue  # full-time-only source (Wikipedia)
            g1 += f[0] + a[0]
            gt += f[0] + f[1] + a[0] + a[1]
    return (g1 + HT_SHARE * HT_PRIOR) / (gt + HT_PRIOR)


def rates(row: dict, m: dict, league: dict | None = None) -> tuple[float | None, float | None, list[str]]:
    """Expected goals (home, away) WITHOUT the market (21 Nov: the market is one of the views, so the simulation must
    not lean on it): the league model's xG and the teams' own form, averaged when both exist, then the absences.
    (None, None) when neither exists — the simulation then gives no independent view."""
    why, views = [], []
    if league:
        views.append(tuple(league["xg"]))
        why.append(f"lig modeli xG {league['xg'][0]:.2f}-{league['xg'][1]:.2f}")
    th, ta = (row.get("teams") or {}).get("home") or {}, (row.get("teams") or {}).get("away") or {}
    if th.get("gf") is not None and ta.get("gf") is not None and th.get("n", 0) >= 6 and ta.get("n", 0) >= 6:
        fh, fa = (th["gf"] + ta["ga"]) / 2, (ta["gf"] + th["ga"]) / 2
        views.append((fh, fa))
        why.append(f"form xG {fh:.2f}-{fa:.2f}")
    if not views:
        return None, None, ["bağımsız veri yok (yalnız piyasa)"]
    mh, ma = sum(v[0] for v in views) / len(views), sum(v[1] for v in views) / len(views)
    flags = " ".join((m.get("research") or {}).get("flags") or []) + " " + " ".join(row.get("flags") or [])
    for side, me in (("home", "Ev"), ("away", "Dep")):
        t = th if side == "home" else ta
        if t.get("top_scorer_out") or f"{me}: gol kralı" in flags or f"{me}: golcü eksik" in flags:
            mh, ma = (mh * (1 - ABSENCE), ma) if side == "home" else (mh, ma * (1 - ABSENCE))
            why.append(f"{me} golcüsü yok")
        if t.get("gk1_out") or f"{me}: düzenli kaleci" in flags:
            mh, ma = (mh, ma * (1 + ABSENCE)) if side == "home" else (mh * (1 + ABSENCE), ma)
            why.append(f"{me} kalecisi yok")
    return mh, ma, why


def simulate(mh: float, ma: float, n: int, seed: int, share: float = HT_SHARE) -> tuple[np.ndarray, dict]:
    """Joint (h1, a1, h2, a2) distribution from n simulated matches, and the most common final scores."""
    rng = np.random.default_rng(seed)
    h1, a1 = rng.poisson(mh * share, n), rng.poisson(ma * share, n)
    h2, a2 = rng.poisson(mh * (1 - share), n), rng.poisson(ma * (1 - share), n)
    c = lambda x: np.minimum(x, G - 1)  # noqa: E731
    joint = np.zeros((G, G, G, G))
    np.add.at(joint, (c(h1), c(a1), c(h2), c(a2)), 1.0)
    joint /= n
    ft = {}
    for x, y in zip(h1 + h2, a1 + a2):
        ft[f"{x}-{y}"] = ft.get(f"{x}-{y}", 0) + 1
    top = {k: v / n for k, v in sorted(ft.items(), key=lambda kv: -kv[1])[:5]}
    return joint, top


def history(leg: dict) -> float | None:
    """Team-history rate of a bet: the deep-research rate, averaged with the recent-form rate read from the open
    match previews ("son 6+6 maç %N" in the web note) when there is one."""
    if leg["verdict"].startswith("geçmiş"):
        return None  # 'geçmiş yetersiz': too few games — neither the stored rate nor a free-text note counts as history
    m = re.search(r"son 6\+6 maç %(\d+)", leg.get("web") or "")
    recent = int(m.group(1)) / 100 if m else None
    vals = [v for v in (leg.get("mean"), recent) if v is not None]
    return sum(vals) / len(vals) if vals else None


def judge(market: float, sim: float | None, hist: float | None) -> tuple[str, float]:
    views = [v for v in (market, sim, hist) if v is not None]
    low = min(views)
    if sim is None or hist is None:
        return "eksik kanıt", low
    if min(market, sim, hist) >= FLOOR and sim >= market - MAX_GAP and hist >= market - MAX_GAP:
        return "üçlü onay", low
    if sim < market - 0.10 or hist < market - 0.15:
        return "çelişki", low
    return "kısmi onay", low


def with_model(verdict: str, low: float, market: float, dc: float | None) -> tuple[str, float]:
    """Fourth view (penaltyblog Dixon-Coles league model, scripts/dc_model.py): a triple-confirmed bet the league
    model prices more than 10 points under the market is only partly confirmed; the pessimistic view includes it."""
    if dc is None:
        return verdict, low
    low = min(low, dc)
    if verdict == "üçlü onay" and dc < market - 0.10:
        return "kısmi onay", low
    return verdict, low


def run(date: str, n: int) -> list[dict]:
    out_dir = dr.AREA / date
    rows = json.loads((out_dir / "derin_tahminler.json").read_text(encoding="utf-8"))
    ms = {str(m["code"]): m for m in json.loads((out_dir / "nesine_global.json").read_text(encoding="utf-8"))["matches"]}
    now = dt.datetime.now(dr.TSI)
    import datalake_lig as dl
    lig = dl.table()  # league base rates from the Global Football Data Lake (data/lig_oranlari.csv)
    res = []
    for row in rows:
        m = ms.get(str(row["code"]))
        if not m or dt.datetime.fromisoformat(m["kickoff_iso"]) <= now or not row.get("legs"):
            continue
        dc = dc_model.match_view(m)
        mh, ma, why = rates(row, m, dc[1] if dc else None)
        share = half_share(row)
        joint, top = simulate(mh, ma, n, seed=int(row["code"]) % 2**32, share=share) if mh is not None else (None, {})
        why.append(f"ilk yarı gol payı %{100 * share:.0f}")
        elo = elo_gorus.match_view(m)
        bets = []
        for x in row["legs"]:
            try:
                sim = float(goal_probability(x["name"], joint)) if joint is not None else None
            except (KeyError, ValueError):
                sim = None
            hist = history(x)
            verdict, low = judge(x["p"], sim, hist)
            dcp = dc_model.bet_probability(x["name"], dc[0]) if dc else None
            verdict, low = with_model(verdict, low, x["p"], dcp)
            elp = (elo or {}).get(x["name"])
            verdict, low = with_model(verdict, low, x["p"], elp)  # Club Elo: 1X2 / double chance only
            bets.append({"label": x["label"], "name": x["name"], "odds": x["odds"], "market": x["p"], "sim": sim, "hist": hist, "dc": dcp, "elo": elp,
                         "research": x["verdict"], "verdict": verdict, "low": low})
        bets.sort(key=lambda b: (b["verdict"] != "üçlü onay", -b["low"]))
        res.append({"code": row["code"], "kickoff": row["kickoff"], "match": row["match"], "league": row["league"],
                    "xg": [round(mh, 2), round(ma, 2)] if mh is not None else None, "why": why, "top_scores": top, "bets": bets,
                    "dc": dc[1] if dc else None, "elo": (elo or {}).get("_clubs"),
                    "league_rates": dl.league_rates(row["league"], lig)})
    return sorted(res, key=lambda r: r["kickoff"])


def to_markdown(date: str, res: list[dict], n: int) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    best = sorted((b | {"match": r["match"], "kickoff": r["kickoff"]} for r in res for b in r["bets"]
                   if b["verdict"] == "üçlü onay"), key=lambda b: -b["low"])
    md = [f"# {date} — maç simülasyonu ({dt.datetime.now(dr.TSI):%H:%M} TSİ, maç başına {n:,} simülasyon)", "",
          "Her bahis üç bağımsız açıdan: **piyasa** (keskin global fiyat, marjsız ve kalibre olasılık), **simülasyon** (piyasadan BAĞIMSIZ: lig "
          "modeli xG + takımların son formu + eksikler + maçın kendi ilk yarı gol payı ile oynatılan maçlar), **geçmiş** (aynı bahsin iki takımın son maçlarında tutma oranı). "
          "'Üçlü onay': üçü de %55 ve üstü, simülasyon ve geçmiş piyasanın 5 puan altına düşmüyor. 'En düşük' sütunu "
          "üç görüşün en kötümseridir; plan yaparken bu sayıya bakın. Simülasyon sonucu bilemez, bu tür maçlarda "
          "bahsin ne sıklıkla tuttuğunu söyler. **Model** (dördüncü görüş): ligin bu sezonki maçlarıyla kurulan "
          "Dixon-Coles / Bayes gol modeli (penaltyblog); **Elo**: Club Elo puan farkından, arşivdeki 240 bin maçta ölçülen "
          "1/X/2 sıklıkları (yalnız maç sonucu ve çifte şans). İkisinden biri piyasanın 10 puandan fazla altındaysa üçlü "
          "onay kısmi onaya düşer.", "",
          f"## Üçlü onaylı bahisler ({len(best)})", "",
          "| Saat | Maç | Bahis | Oran | Piyasa (keskin, marjsız) | Simülasyon | Geçmiş | Model | En düşük |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {b['kickoff'][11:16]} | {b['match']} | {b['label']} | {b['odds']:.2f} | {pct(b['market'])} | {pct(b['sim'])} | "
           f"{pct(b['hist'])} | {pct(b.get('dc'))} | **{pct(b['low'])}** |" for b in best]
    md += ["", "## Maç maç", ""]
    for r in res:
        sc = ", ".join(f"{k} {pct(v)}" for k, v in r["top_scores"].items())
        md += [f"### {r['kickoff'][11:16]} {r['match']} — {r['league']}", "",
               (f"Simülasyon xG {r['xg'][0]}-{r['xg'][1]} ({'; '.join(r['why'])}). En olası skorlar: {sc}." if r.get("xg")
                else f"Simülasyon yok: {'; '.join(r['why'])}.")
               + (f" Lig modeli ({r['dc']['source']}) xG {r['dc']['xg'][0]}-{r['dc']['xg'][1]}." if r.get("dc") else "")
               + (f" Club Elo: {r['elo']}." if r.get("elo") else "")
               + (f" Lig ortalaması (yalnız bilgi, simülasyona girmez; Data Lake, {lr['n']} maç): {lr['goals']} gol, KG %{100 * float(lr['btts']):.0f}, "
                  f"2,5 üst %{100 * float(lr['over25']):.0f}, 3,5 üst %{100 * float(lr['over35']):.0f}, ev/ber/dep "
                  f"%{100 * float(lr['home']):.0f}/%{100 * float(lr['draw']):.0f}/%{100 * float(lr['away']):.0f}."
                  if (lr := r.get("league_rates")) else ""), "",
               "| Bahis | Oran | Piyasa (keskin, marjsız) | Simülasyon | Geçmiş | Model | Elo | Sonuç |", "|---|---|---|---|---|---|---|---|"]
        md += [f"| {b['label']} | {b['odds']:.2f} | {pct(b['market'])} | {pct(b['sim'])} | {pct(b['hist'])} | {pct(b.get('dc'))} | "
               f"{pct(b.get('elo'))} | {b['verdict']} |" for b in r["bets"]]
        md.append("")
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    ap.add_argument("--n", type=int, default=20000, help="Maç başına simülasyon sayısı")
    args = ap.parse_args()
    write_day(args.tarih, args.n)


def best_value_bet(bets: list[dict], min_ev: float | None = None) -> dict | None:
    """Triple-confirmed bet with the highest calibrated EV (market p × odds − 1), EV >= min_ev; ties -> higher 'low'."""
    from quantfoot.markets.families import leg_min_ev
    from quantfoot.settings import PICK_MIN_EV

    def floor(b: dict) -> float:  # default: the stricter of the pick floor and the bet's family floor
        return max(PICK_MIN_EV, leg_min_ev(b.get("name", ""))) if min_ev is None else min_ev

    tri = [b for b in bets if b["verdict"] == "üçlü onay" and b.get("odds") and b["market"] * b["odds"] - 1.0 >= floor(b)]
    return max(tri, key=lambda b: (round(b["market"] * b["odds"] - 1.0, 6), b["low"])) if tri else None


def update_picks(date: str, res: list[dict]) -> int:
    """Main pick of a not-started match = its triple-confirmed bet with the highest calibrated EV (evidence filters,
    value decides; 22 Nov audit); a match without one keeps the deep-research pick (itself EV-ranked)."""
    import derin_tahmin as dtah
    out = dr.AREA / date
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    by = {str(r["code"]): r for r in res}
    n = 0
    for row in rows:
        best = best_value_bet((by.get(str(row["code"])) or {}).get("bets", []))
        if not best:
            continue
        leg = next((x for x in row["legs"] if x["label"] == best["label"]), None)
        if leg:
            n += (row.get("pick") or {}).get("label") != leg["label"]
            row["pick"] = leg
    (out / "derin_tahminler.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    dtah.update_table(date, rows)
    return n


def write_day(date: str, n: int) -> list[dict]:
    res = run(date, n)
    out = dr.AREA / date
    (out / "simulasyon.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "simulasyon.md").write_text(to_markdown(date, res, n), encoding="utf-8")
    changed = update_picks(date, res)
    tri = sum(1 for r in res for b in r["bets"] if b["verdict"] == "üçlü onay")
    print(f"{len(res)} maç simüle edildi ({n} kez), {tri} bahis üçlü onaylı, {changed} ana tercih değişti -> {out / 'simulasyon.md'}")
    return res


if __name__ == "__main__":
    main()
