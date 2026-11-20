"""Monte Carlo simulation of every not-started match from all the evidence gathered (user request, 21 Nov: "her şeyi
detaylı araştırıp maçları karşılaştır, simülasyonlar yaratıp gerçek sonuca ulaş").

Per match, three independent views of each candidate bet are put side by side:

1. market   — the sharp global price (no-vig probability, already in derin_tahminler.json);
2. simulation — N simulated matches (Poisson goals per half) whose scoring rates blend the market's expected goals
   with the teams' own recent attack/defence (ESPN or Wikipedia goals for/against) and the known absences
   (top scorer out: that team scores 8 % less; first-choice goalkeeper out: the opponent scores 8 % more);
3. history  — how often the same bet won in both teams' recent games (deep-research verdict).

A bet is "üçlü onay" (triple confirmed) only when all three views give it at least the leg floor (55 %) and the
simulation and history do not fall more than 5 points below the market. The table ranks bets by the lowest of the
three views, i.e. by the most pessimistic evidence — the honest number to plan with.

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
import derin_arastirma as dr  # noqa: E402

sys.path.insert(0, str(dr.ROOT / "src"))
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402

HT_SHARE = 0.44        # first-half share of goals (184k matches in the repo's archive, docs/markets.md)
W_MARKET = 0.65        # weight of the market's expected goals against the teams' recent form
ABSENCE = 0.08
FLOOR, MAX_GAP = 0.55, 0.05
G = 9                  # goals per team per half kept in the joint grid


def rates(row: dict, m: dict) -> tuple[float, float, list[str]]:
    """Blended expected goals (home, away) and the reasons for each adjustment."""
    mh, ma = (m.get("mu_home") or 1.3), (m.get("mu_away") or 1.1)
    why = [f"piyasa xG {mh:.2f}-{ma:.2f}"]
    th, ta = (row.get("teams") or {}).get("home") or {}, (row.get("teams") or {}).get("away") or {}
    if th.get("gf") is not None and ta.get("gf") is not None and th.get("n", 0) >= 4 and ta.get("n", 0) >= 4:
        fh, fa = (th["gf"] + ta["ga"]) / 2, (ta["gf"] + th["ga"]) / 2
        mh, ma = W_MARKET * mh + (1 - W_MARKET) * fh, W_MARKET * ma + (1 - W_MARKET) * fa
        why.append(f"form xG {fh:.2f}-{fa:.2f}")
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


def simulate(mh: float, ma: float, n: int, seed: int) -> tuple[np.ndarray, dict]:
    """Joint (h1, a1, h2, a2) distribution from n simulated matches, and the most common final scores."""
    rng = np.random.default_rng(seed)
    h1, a1 = rng.poisson(mh * HT_SHARE, n), rng.poisson(ma * HT_SHARE, n)
    h2, a2 = rng.poisson(mh * (1 - HT_SHARE), n), rng.poisson(ma * (1 - HT_SHARE), n)
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
    m = re.search(r"son 6\+6 maç %(\d+)", leg.get("web") or "")
    recent = int(m.group(1)) / 100 if m else None
    base = leg.get("mean") if not leg["verdict"].startswith("geçmiş") or recent is not None else None
    vals = [v for v in (base, recent) if v is not None]
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
    res = []
    for row in rows:
        m = ms.get(str(row["code"]))
        if not m or dt.datetime.fromisoformat(m["kickoff_iso"]) <= now or not row.get("legs"):
            continue
        mh, ma, why = rates(row, m)
        joint, top = simulate(mh, ma, n, seed=int(row["code"]) % 2**32)
        dc = dc_model.match_view(m)
        bets = []
        for x in row["legs"]:
            try:
                sim = float(goal_probability(x["name"], joint))
            except (KeyError, ValueError):
                sim = None
            hist = history(x)
            verdict, low = judge(x["p"], sim, hist)
            dcp = dc_model.bet_probability(x["name"], dc[0]) if dc else None
            verdict, low = with_model(verdict, low, x["p"], dcp)
            bets.append({"label": x["label"], "odds": x["odds"], "market": x["p"], "sim": sim, "hist": hist, "dc": dcp,
                         "research": x["verdict"], "verdict": verdict, "low": low})
        bets.sort(key=lambda b: (b["verdict"] != "üçlü onay", -b["low"]))
        res.append({"code": row["code"], "kickoff": row["kickoff"], "match": row["match"], "league": row["league"],
                    "xg": [round(mh, 2), round(ma, 2)], "why": why, "top_scores": top, "bets": bets,
                    "dc": dc[1] if dc else None})
    return sorted(res, key=lambda r: r["kickoff"])


def to_markdown(date: str, res: list[dict], n: int) -> str:
    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    best = sorted((b | {"match": r["match"], "kickoff": r["kickoff"]} for r in res for b in r["bets"]
                   if b["verdict"] == "üçlü onay"), key=lambda b: -b["low"])
    md = [f"# {date} — maç simülasyonu ({dt.datetime.now(dr.TSI):%H:%M} TSİ, maç başına {n:,} simülasyon)", "",
          "Her bahis üç bağımsız açıdan: **piyasa** (keskin global fiyat), **simülasyon** (piyasa xG + takımların son "
          "formu + eksikler ile oynatılan maçlar), **geçmiş** (aynı bahsin iki takımın son maçlarında tutma oranı). "
          "'Üçlü onay': üçü de %55 ve üstü, simülasyon ve geçmiş piyasanın 5 puan altına düşmüyor. 'En düşük' sütunu "
          "üç görüşün en kötümseridir; plan yaparken bu sayıya bakın. Simülasyon sonucu bilemez, bu tür maçlarda "
          "bahsin ne sıklıkla tuttuğunu söyler. **Model** (dördüncü görüş): ligin bu sezonki maçlarıyla kurulan "
          "Dixon-Coles gol modeli (penaltyblog); piyasanın 10 puandan fazla altındaysa üçlü onay kısmi onaya düşer.", "",
          f"## Üçlü onaylı bahisler ({len(best)})", "",
          "| Saat | Maç | Bahis | Oran | Piyasa | Simülasyon | Geçmiş | Model | En düşük |", "|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {b['kickoff'][11:16]} | {b['match']} | {b['label']} | {b['odds']:.2f} | {pct(b['market'])} | {pct(b['sim'])} | "
           f"{pct(b['hist'])} | {pct(b.get('dc'))} | **{pct(b['low'])}** |" for b in best]
    md += ["", "## Maç maç", ""]
    for r in res:
        sc = ", ".join(f"{k} {pct(v)}" for k, v in r["top_scores"].items())
        md += [f"### {r['kickoff'][11:16]} {r['match']} — {r['league']}", "",
               f"Simülasyon xG {r['xg'][0]}-{r['xg'][1]} ({'; '.join(r['why'])}). En olası skorlar: {sc}."
               + (f" Lig modeli ({r['dc']['source']}) xG {r['dc']['xg'][0]}-{r['dc']['xg'][1]}." if r.get("dc") else ""), "",
               "| Bahis | Oran | Piyasa | Simülasyon | Geçmiş | Model | Sonuç |", "|---|---|---|---|---|---|---|"]
        md += [f"| {b['label']} | {b['odds']:.2f} | {pct(b['market'])} | {pct(b['sim'])} | {pct(b['hist'])} | {pct(b.get('dc'))} | "
               f"{b['verdict']} |" for b in r["bets"]]
        md.append("")
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tarih", default=dt.datetime.now(dr.TSI).date().isoformat())
    ap.add_argument("--n", type=int, default=20000, help="Maç başına simülasyon sayısı")
    args = ap.parse_args()
    write_day(args.tarih, args.n)


def update_picks(date: str, res: list[dict]) -> int:
    """Main pick of a not-started match = its triple-confirmed bet with the best pessimistic view (user, 21 Nov:
    "böyle devam"); a match without one keeps the deep-research pick."""
    import derin_tahmin as dtah
    out = dr.AREA / date
    rows = json.loads((out / "derin_tahminler.json").read_text(encoding="utf-8"))
    by = {str(r["code"]): r for r in res}
    n = 0
    for row in rows:
        tri = [b for b in (by.get(str(row["code"])) or {}).get("bets", []) if b["verdict"] == "üçlü onay"]
        if not tri:
            continue
        best = max(tri, key=lambda b: b["low"])
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
