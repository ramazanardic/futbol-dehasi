"""Calibrate the half-time / game-state part of the goal model against direct exchange prices.

    python arsiv_kod/calibrate_halves.py

Free parameters (symmetric home/away):
  a1      share of a team's goals expected in the first half
  z, g    second-half scoring multiplier when level at HT: 0-0 / level with goals
  l1, t1  leader / trailer multiplier when one side leads by one at HT
  l2, t2  leader / trailer multiplier when one side leads by two or more
Targets: every directly quoted half market (HT/FT, HT result, HT O/U, HT BTTS, HT result & BTTS,
2H result, 2H O/U, 2H BTTS, BTTS in both halves). The full-time distribution is fitted exactly as in
production (1X2 + O/U 2.5) and is unaffected by these parameters. Matches are split in halves by a
hash of their names: parameters are fitted on one half (Nelder-Mead) and reported on the other.
Literature check: Maia et al. (2023, Brazil Série A) find a team trailing by one scores ~10 % more,
by two ~20 % more; Heuer & Rubner (2012, Bundesliga) report strong score effects late on.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from calibrate_direct import kl, snapshots  # noqa: E402
from nesine_global import direct_probabilities  # noqa: E402

from quantfoot.markets.devig import devig  # noqa: E402
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402
import quantfoot.markets.omni_markets as om  # noqa: E402
from quantfoot.markets.tail_goals import fit_tail_rates_from_markets  # noqa: E402

OUT = ROOT / "reports" / "research" / "halves_calibration.md"
NAMES = ("a1", "z", "g", "l1", "t1", "l2", "t2")
CURRENT = np.array([0.44, 0.96, 1.025, 0.958, 1.10, 1.01, 1.015])  # production values (symmetrised)
LOW = np.array([0.38, 0.80, 0.85, 0.80, 0.90, 0.75, 0.85])
HIGH = np.array([0.50, 1.15, 1.20, 1.15, 1.40, 1.25, 1.50])


def is_half_market(name: str) -> bool:
    return name.startswith(("İY", "2Y", "İki Yarıda"))


def prepare(refs: list[dict]) -> list[tuple[float, float, dict[str, float]]]:
    rows = []
    for r in refs:
        q = {k: v for k, v in direct_probabilities(r).items() if is_half_market(k)}
        if not q:
            continue
        p1x2 = devig(r["x12"], method="power").probabilities
        p_over = float(devig(r["ou"][1], method="power").probabilities[0])
        mu_h, mu_a, _ = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_over, seed_rates=(1.45, 1.15),
                                                    alpha_nb=0.0, shared_kappa=0.0, com_nu=1.0, fund_weight=0.0)
        rows.append((mu_h, mu_a, q))
    return rows


def loss(x: np.ndarray, rows, by_family: dict | None = None) -> float:
    x = np.clip(x, LOW, HIGH)
    mults = om.game_state_mults(*x[1:])
    total, n = 0.0, 0
    for mu_h, mu_a, q in rows:
        joint = om.compute_omni_markets(mu_h, mu_a, league=None, first_half_share=float(x[0]), state_mults=mults).joint
        for name, qv in q.items():
            try:
                pv = goal_probability(name, joint)
            except Exception:  # selection the grid cannot express
                continue
            d = kl(qv, pv)
            total += d
            n += 1
            if by_family is not None:
                fam = "İY/MS" if name.startswith("İY/MS") else " ".join(name.split()[:1 + (name.startswith(("İY", "2Y")) and "&" in name)])
                by_family.setdefault(fam, []).append(d)
    return total / n if n else math.nan


def main() -> None:
    refs = snapshots()
    rows_all = [(r, row) for r in refs for row in prepare([r])]
    train = [row for r, row in rows_all if int(hashlib.md5((r["home"] + r["away"]).encode()).hexdigest(), 16) % 2 == 0]
    test = [row for r, row in rows_all if int(hashlib.md5((r["home"] + r["away"]).encode()).hexdigest(), 16) % 2 == 1]
    print(f"{len(rows_all)} maç (kalibrasyon {len(train)}, test {len(test)}); "
          f"{sum(len(q) for _, _, q in train)} / {sum(len(q) for _, _, q in test)} yarı seçimi")
    res = minimize(loss, CURRENT, args=(train,), method="Nelder-Mead", options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-7})
    best = np.clip(res.x, LOW, HIGH)
    fam_cur, fam_new = {}, {}
    cur_tr, new_tr = loss(CURRENT, train), loss(best, train)
    cur_te, new_te = loss(CURRENT, test, fam_cur), loss(best, test, fam_new)
    lines = [f"# İlk yarı / oyun durumu kalibrasyonu ({len(rows_all)} maç, doğrudan borsa fiyatları)", "",
             "Kayıp = ortalama KL(borsa || model), yarı pazarlarında. Düşük = daha iyi.", "",
             "| Parametre | Mevcut | Kalibre |", "|---|---|---|"]
    lines += [f"| {k} | {c:.3f} | {b:.3f} |" for k, c, b in zip(NAMES, CURRENT, best)]
    lines += ["", "| | Kalibrasyon kaybı | Test kaybı |", "|---|---|---|",
              f"| Mevcut | {cur_tr:.5f} | {cur_te:.5f} |", f"| Kalibre | {new_tr:.5f} | {new_te:.5f} |",
              "", "## Test kaybı, pazar ailesine göre", "", "| Aile | n | Mevcut | Kalibre |", "|---|---|---|---|"]
    for f in sorted(fam_cur):
        lines.append(f"| {f} | {len(fam_cur[f])} | {np.mean(fam_cur[f]):.5f} | {np.mean(fam_new.get(f, [np.nan])):.5f} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    np.save(ROOT / "reports" / "research" / "halves_params.npy", best)


if __name__ == "__main__":
    main()
