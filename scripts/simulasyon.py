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
from quantfoot.markets.league_halves import league_first_half_share  # noqa: E402
from quantfoot.markets.match_intelligence import weather_goal_multiplier  # noqa: E402

HT_SHARE = 0.44        # first-half share of goals (184k matches in the repo's archive, docs/markets.md)
HT_PRIOR = 20.0        # goals of prior weight when a match's own first-half share is estimated
AWAY_HT_DELTA = -0.015 # 22 Nov audit: away 1H goal share (%41.7) lags home (%43.5) by ~1.5-1.8 pts
SIM_KAPPA = 0.030      # shared Gamma match-tempo variance (matches halves_btts 184k-match archive calibration)
HOME_ADV_FORM = 1.08   # home/away multiplier when form gf/ga is pooled across venues
AWAY_ADV_FORM = 0.92
ABSENCE = 0.08
FLOOR, MAX_GAP = 0.55, 0.05
G = 9                  # goals per team per half kept in the joint grid


def half_share(row: dict) -> float:
    """First-half share of goals in both teams' recent games, shrunk towards the league's empirical 1H share."""
    prior_share = league_first_half_share(row.get("league")) or HT_SHARE
    g1 = gt = 0
    for side in ("home", "away"):
        for g in ((row.get("games") or {}).get(side) or []):
            f, a = g.get("for") or (None, None), g.get("against") or (None, None)
            if None in (f[0], a[0]):
                continue  # full-time-only source (Wikipedia)
            g1 += f[0] + a[0]
            gt += f[0] + f[1] + a[0] + a[1]
    return (g1 + prior_share * HT_PRIOR) / (gt + HT_PRIOR)


def _venue_adjusted_form(row: dict, th: dict, ta: dict) -> tuple[float, float]:
    """Form xG with home-advantage adjustment (prevents pooled gf/ga from flattening strong home favourites)."""
    raw_fh = (th["gf"] + ta["ga"]) / 2.0
    raw_fa = (ta["gf"] + th["ga"]) / 2.0
    # Use venue-specific games when at least 4 home games for home team and 4 away games for away team exist
    games = row.get("games") or {}
    hg = [g for g in (games.get("home") or []) if g.get("side") == "home" and g.get("for") and g.get("against")]
    ag = [g for g in (games.get("away") or []) if g.get("side") == "away" and g.get("for") and g.get("against")]
    if len(hg) >= 4 and len(ag) >= 4:
        def _ft_tot(pair):
            return (pair[0] or 0) + (pair[1] or 0)
        h_gf = sum(_ft_tot(g["for"]) for g in hg) / len(hg)
        h_ga = sum(_ft_tot(g["against"]) for g in hg) / len(hg)
        a_gf = sum(_ft_tot(g["for"]) for g in ag) / len(ag)
        a_ga = sum(_ft_tot(g["against"]) for g in ag) / len(ag)
        vh, va = (h_gf + a_ga) / 2.0, (a_gf + h_ga) / 2.0
        # Blend 50% venue-specific + 50% home-advantage-scaled overall form to control small-sample noise
        return 0.5 * vh + 0.5 * (raw_fh * HOME_ADV_FORM), 0.5 * va + 0.5 * (raw_fa * AWAY_ADV_FORM)
    return raw_fh * HOME_ADV_FORM, raw_fa * AWAY_ADV_FORM


def rates(row: dict, m: dict, league: dict | None = None, *, home_adv: bool = False) -> tuple[float | None, float | None, list[str]]:
    """Expected goals (home, away) WITHOUT the market (21 Nov: the market is one of the views, so the simulation must
    not lean on it): the league model's xG and the teams' own form, averaged when both exist, then the absences.
    (None, None) when neither exists — the simulation then gives no independent view.

    When ``home_adv=True`` (production runs), pooled form gf/ga is adjusted for home advantage / venue splits
    and the league Dixon-Coles model gets 60 % weight when both views exist (22 Nov audit: raw pooled form
    flattened favourites and produced false 'çelişki' flags on winning MS/Over picks).
    """
    why, views, weights = [], [], []
    res = m.get("research") or {}
    xg_intel = res.get("xg_intelligence") or {}
    if home_adv and xg_intel.get("xg_mu_home") and xg_intel.get("xg_mu_away"):
        xh, xa = float(xg_intel["xg_mu_home"]), float(xg_intel["xg_mu_away"])
        views.append((xh, xa))
        weights.append(0.45)
        why.append(f"sezon xG profili {xh:.2f}-{xa:.2f}")
    if league:
        views.append(tuple(league["xg"]))
        weights.append((0.35 if xg_intel.get("xg_mu_home") else 0.60) if home_adv else 1.0)
        why.append(f"lig modeli xG {league['xg'][0]:.2f}-{league['xg'][1]:.2f}")
    th, ta = (row.get("teams") or {}).get("home") or {}, (row.get("teams") or {}).get("away") or {}
    if th.get("gf") is not None and ta.get("gf") is not None and th.get("n", 0) >= 6 and ta.get("n", 0) >= 6:
        if home_adv:
            fh, fa = _venue_adjusted_form(row, th, ta)
        else:
            fh, fa = (th["gf"] + ta["ga"]) / 2, (ta["gf"] + th["ga"]) / 2
        views.append((fh, fa))
        weights.append((0.20 if xg_intel.get("xg_mu_home") else 0.40) if home_adv else 1.0)
        why.append(f"form xG {fh:.2f}-{fa:.2f}")
    if not views:
        return None, None, ["bağımsız veri yok (yalnız piyasa)"]
    w_sum = sum(weights)
    mh = sum(w * v[0] for w, v in zip(weights, views)) / w_sum
    ma = sum(w * v[1] for w, v in zip(weights, views)) / w_sum
    flags = " ".join(res.get("flags") or []) + " " + " ".join(row.get("flags") or [])
    for side, me in (("home", "Ev"), ("away", "Dep")):
        t = th if side == "home" else ta
        if t.get("top_scorer_out") or f"{me}: gol kralı" in flags or f"{me}: golcü eksik" in flags:
            mh, ma = (mh * (1 - ABSENCE), ma) if side == "home" else (mh, ma * (1 - ABSENCE))
            why.append(f"{me} golcüsü yok")
        if t.get("gk1_out") or f"{me}: düzenli kaleci" in flags:
            mh, ma = (mh, ma * (1 + ABSENCE)) if side == "home" else (mh * (1 + ABSENCE), ma)
            why.append(f"{me} kalecisi yok")
    if home_adv:
        w_mult = weather_goal_multiplier(res.get("weather") or row.get("weather"))
        if w_mult < 0.999:
            mh *= w_mult
            ma *= w_mult
            why.append(f"şiddetli hava gol çarpanı ×{w_mult:.2f}")
        fat = res.get("fatigue") or {}
        if fat.get("fatigued_side"):
            mh *= float(fat.get("home_mult", 1.0))
            ma *= float(fat.get("away_mult", 1.0))
            why.append(fat.get("flag") or f"yorgunluk ({fat['fatigued_side']})")
        scout = res.get("squad_scouting") or {}
        if isinstance(scout, dict) and float(scout.get("confidence") or 0.0) >= 0.35:
            gm = scout.get("scouting_goal_mult") or {}
            sh = float(gm.get("home", 1.0))
            sa = float(gm.get("away", 1.0))
            if abs(sh - 1.0) >= 0.012 or abs(sa - 1.0) >= 0.012:
                mh *= max(0.95, min(1.05, sh))
                ma *= max(0.95, min(1.05, sa))
                why.append(f"kadro hat eşleşmesi ×{sh:.2f}/×{sa:.2f}")
    return mh, ma, why


def simulate(
    mh: float,
    ma: float,
    n: int,
    seed: int,
    share: float = HT_SHARE,
    *,
    kappa: float = 0.0,
    away_share_delta: float = 0.0,
    game_state: bool = False,
    match: dict | None = None,
    deep: bool = False,
) -> tuple[np.ndarray, dict]:
    """Joint (h1, a1, h2, a2) distribution from n simulated matches, and the most common final scores.

    When ``deep=True`` (used in production runs), delegates to the 6-segment minute-by-minute football
    simulator (``quantfoot.markets.match_simulator.simulate_deep_match``) with empirical 15-min goal curve,
    team-specific 1H/2H splits, dynamic score-state tactics, and referee/derby-conditioned red cards.
    """
    if deep:
        from quantfoot.markets.match_simulator import MatchSimConfig, simulate_deep_match

        cfg = MatchSimConfig.from_match_record(
            mh, ma, match, base_1h_share=share, away_1h_delta=away_share_delta,
        )
        res = simulate_deep_match(cfg, n=n, seed=seed)
        return res.joint, dict(list(res.top_scores.items())[:5])

    rng = np.random.default_rng(seed)
    s_h = float(np.clip(share, 0.30, 0.55))
    s_a = float(np.clip(share + away_share_delta, 0.28, 0.55))
    if kappa > 1e-6:
        tempo = rng.gamma(1.0 / kappa, kappa, n)
        mh_arr, ma_arr = mh * tempo, ma * tempo
    else:
        mh_arr, ma_arr = mh, ma
    h1, a1 = rng.poisson(mh_arr * s_h, n), rng.poisson(ma_arr * s_a, n)
    lam2_h = mh_arr * (1.0 - s_h)
    lam2_a = ma_arr * (1.0 - s_a)
    if game_state:
        # Mean-conserving 2H game-state elasticity (matches omni_markets.GAME_STATE_MULTS)
        diff1 = h1 - a1
        mult_h = np.ones(n, dtype=float)
        mult_a = np.ones(n, dtype=float)
        m_00 = (h1 == 0) & (a1 == 0)
        m_tg = (h1 == a1) & (h1 > 0)
        m_h1 = diff1 == 1
        m_a1 = diff1 == -1
        m_h2 = diff1 >= 2
        m_a2 = diff1 <= -2
        mult_h[m_00], mult_a[m_00] = 0.965, 0.955
        mult_h[m_tg], mult_a[m_tg] = 1.025, 1.025
        mult_h[m_h1], mult_a[m_h1] = 0.960, 1.095
        mult_h[m_a1], mult_a[m_a1] = 1.105, 0.955
        mult_h[m_h2], mult_a[m_h2] = 1.030, 0.990
        mult_h[m_a2], mult_a[m_a2] = 0.990, 1.040
        mult_h /= max(float(np.mean(mult_h)), 1e-6)
        mult_a /= max(float(np.mean(mult_a)), 1e-6)
        lam2_h = lam2_h * mult_h
        lam2_a = lam2_a * mult_a
    h2, a2 = rng.poisson(lam2_h, n), rng.poisson(lam2_a, n)
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


def judge(market: float, sim: float | None, hist: float | None, *, min_side: float | None = None) -> tuple[str, float]:
    views = [v for v in (market, sim, hist) if v is not None]
    low = min(views)
    if sim is None or hist is None:
        return "eksik kanıt", low
    if min_side is not None and min_side < 0.45:
        low = min(low, min_side)
        if min_side < market - 0.22:
            return "çelişki", low
        return "kısmi onay", low
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
    from bahis_aileleri import top_five

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
        mh, ma, why = rates(row, m, dc[1] if dc else None, home_adv=True)
        share = half_share(row)
        deep_sim = None
        if mh is not None:
            from quantfoot.markets.match_simulator import MatchSimConfig, evaluate_21_families, simulate_deep_match

            cfg = MatchSimConfig.from_match_record(
                mh, ma, m, base_1h_share=share, away_1h_delta=AWAY_HT_DELTA,
            )
            deep_sim = simulate_deep_match(cfg, n=n, seed=int(row["code"]) % 2**32)
            joint, top = deep_sim.joint, dict(list(deep_sim.top_scores.items())[:5])
            why.append(
                f"6-periyot derin simülasyon (1Y Ev %{100*cfg.home_1h_share:.0f}/Dep %{100*cfg.away_1h_share:.0f}, "
                f"kırmızı kart %{100*deep_sim.diagnostics['red_card_match_prob']:.0f}, κ={cfg.kappa:.3f}, oyun-durumu aktif)"
            )
        else:
            joint, top = None, {}
        elo = elo_gorus.match_view(m)
        bets = []
        hist_map: dict[str, float | None] = {}
        dc_map: dict[str, float | None] = {}
        for x in row["legs"]:
            try:
                sim = float(goal_probability(x["name"], joint)) if joint is not None else None
            except (KeyError, ValueError):
                sim = None
            hist = history(x)
            hist_map[x["name"]] = hist
            side_vals = [v for v, cnt in ((x.get("home_rate"), x.get("home_n") or 0), (x.get("away_rate"), x.get("away_n") or 0))
                         if v is not None and cnt >= 5]
            min_side = min(side_vals) if len(side_vals) == 2 else None
            verdict, low = judge(x["p"], sim, hist, min_side=min_side)
            if x["verdict"].startswith("⚠"):
                verdict = "çelişki"
            dcp = dc_model.bet_probability(x["name"], dc[0]) if dc else None
            dc_map[x["name"]] = dcp
            verdict, low = with_model(verdict, low, x["p"], dcp)
            elp = (elo or {}).get(x["name"])
            verdict, low = with_model(verdict, low, x["p"], elp)  # Club Elo: 1X2 / double chance only
            if verdict == "üçlü onay" and x.get("name") in ("2.5 Üst", "3.5 Alt") and float(x.get("p") or 0.0) < 0.61:
                # 24 Kas denetimi: P < %61 olan sınırda 2.5 Üst / 3.5 Alt üçlü onayları 0/4 (%0) kaldı; P >= %62 olanlar 3/3 (%100) tuttu
                verdict = "kısmi onay"
            bets.append({"label": x["label"], "name": x["name"], "odds": x["odds"], "market": x["p"], "sim": sim, "hist": hist, "dc": dcp, "elo": elp,
                         "research": x["verdict"], "verdict": verdict, "low": low})
        bets.sort(key=lambda b: (b["verdict"] != "üçlü onay", -b["low"]))
        fam21_dict = None
        if deep_sim is not None:
            from quantfoot.markets.match_simulator import evaluate_21_families

            fam21 = evaluate_21_families(m, deep_sim, history_map=hist_map, dc_probs=dc_map)
            fam21_dict = fam21.to_dict()
        res.append({"code": row["code"], "kickoff": row["kickoff"], "match": row["match"], "league": row["league"],
                    "xg": [round(mh, 2), round(ma, 2)] if mh is not None else None, "why": why, "top_scores": top, "bets": bets,
                    "dc": dc[1] if dc else None, "elo": (elo or {}).get("_clubs"),
                    "league_rates": dl.league_rates(row["league"], lig),
                    "sim_diagnostics": deep_sim.diagnostics if deep_sim is not None else None,
                    "twenty_one_families": fam21_dict,
                    "en_yuksek_5": row["en_yuksek_5"] if "en_yuksek_5" in row else top_five(m)})
    return sorted(res, key=lambda r: r["kickoff"])


def to_markdown(date: str, res: list[dict], n: int) -> str:
    from bahis_aileleri import format_top_five

    pct = lambda x: "-" if x is None else f"%{100 * x:.0f}"  # noqa: E731
    best = sorted((b | {"match": r["match"], "kickoff": r["kickoff"]} for r in res for b in r["bets"]
                   if b["verdict"] == "üçlü onay"), key=lambda b: -b["low"])
    md = [f"# {date} — maç simülasyonu ({dt.datetime.now(dr.TSI):%H:%M} TSİ, maç başına {n:,} simülasyon)", "",
          "Her bahis üç bağımsız açıdan: **piyasa** (keskin global fiyat, marjsız ve kalibre olasılık), **simülasyon** (piyasadan BAĞIMSIZ: 6-periyotlu dakika-dakika "
          "taktik simülatör — lig modeli xG + 2026/27 xG/hat eşleşmesi + takımların 1Y/2Y gol payları + dinamik skor-durumu + hakem/derbi kırmızı kartları), **geçmiş** (aynı bahsin iki takımın son maçlarında tutma oranı). "
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
               f"**En yüksek 5 aile olasılığı** · {format_top_five(r.get('en_yuksek_5'))}", "",
               (f"Simülasyon xG {r['xg'][0]}-{r['xg'][1]} ({'; '.join(r['why'])}). En olası skorlar: {sc}." if r.get("xg")
                else f"Simülasyon yok: {'; '.join(r['why'])}.")
               + (f" Lig modeli ({r['dc']['source']}) xG {r['dc']['xg'][0]}-{r['dc']['xg'][1]}." if r.get("dc") else "")
               + (f" Club Elo: {r['elo']}." if r.get("elo") else "")
               + (f" Lig ortalaması (yalnız bilgi, simülasyona girmez; Data Lake, {lr['n']} maç): {lr['goals']} gol, KG %{100 * float(lr['btts']):.0f}, "
                  f"2,5 üst %{100 * float(lr['over25']):.0f}, 3,5 üst %{100 * float(lr['over35']):.0f}, ev/ber/dep "
                  f"%{100 * float(lr['home']):.0f}/%{100 * float(lr['draw']):.0f}/%{100 * float(lr['away']):.0f}."
                  if (lr := r.get("league_rates")) else ""), ""]
        sd = r.get("sim_diagnostics")
        if isinstance(sd, dict):
            md.append(
                f"**Derin Simülasyon Senaryoları:** 1Y ort. {sd['avg_goals_1h']:.2f} / 2Y ort. {sd['avg_goals_2h']:.2f} gol · "
                f"İY 1.5 Üst %{100*sd['p_ht_over15']:.0f} · Ev 1.5 Üst %{100*sd['p_home_over15']:.0f} · "
                f"Dep 1.5 Üst %{100*sd['p_away_over15']:.0f} · MS 1 & 1.5 Üst %{100*sd['p_ms1_and_o15']:.0f} · "
                f"MS 2 & 1.5 Üst %{100*sd['p_ms2_and_o15']:.0f} · İki Yarıda KG %{100*sd['p_both_halves_btts']:.0f}"
            )
            f21 = r.get("twenty_one_families") or {}
            smart = f21.get("smart_attacking_picks") or []
            if smart:
                sp_str = " · ".join(
                    f"**{x['name']}** (Füzyon %{100*x['p_fused']:.0f}, uyum {x['agreement_score']:.0f}/100)"
                    for x in smart[:4]
                )
                md.append(f"**21 Aile Akıllı Fırsatlar ({f21.get('match_character', '-')}):** {sp_str}")
            md.append("")
        md += ["| Bahis | Oran | Piyasa (keskin, marjsız) | Simülasyon | Geçmiş | Model | Elo | Sonuç |", "|---|---|---|---|---|---|---|---|"]
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
        if leg and not leg["verdict"].startswith("⚠"):
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
