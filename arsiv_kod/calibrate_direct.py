"""Calibrate the goal model against directly quoted exchange prices (free, growing validation set).

    python arsiv_kod/calibrate_direct.py            # all references.json snapshots in git history (last 7 days)

Every Smarkets reference carries complete, liquid books for many derivative markets (BTTS, every O/U
line, half-time result, HT/FT, halves O/U, odd/even, goal ranges, result & BTTS / O-U combos). The model
is fitted on the market inputs we use in production and scored on the *other* directly quoted
selections with the binary KL divergence KL(q || p) (q = exchange, p = model). Matches are split in
two halves by a hash of their names: parameters are chosen on one half and reported on the other.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nesine_global import direct_probabilities  # noqa: E402

import quantfoot.markets.omni_markets as om  # noqa: E402
from quantfoot.markets.devig import devig  # noqa: E402
from quantfoot.markets.goal_markets import goal_probability  # noqa: E402
from quantfoot.markets.tail_goals import fit_tail_rates_from_markets  # noqa: E402

REF = "data/global_odds/latest/references.json"
OUT = ROOT / "reports" / "research" / "direct_calibration.md"


def snapshots() -> list[dict]:
    """Latest Smarkets record per match across the git history of references.json."""
    shas = subprocess.run(["git", "log", "--format=%H", "--since=120 days ago", "--", REF], cwd=ROOT,
                          capture_output=True, text=True).stdout.split()
    best: dict[tuple, dict] = {}
    for sha in reversed(shas):  # oldest first, later snapshots overwrite
        raw = subprocess.run(["git", "show", f"{sha}:{REF}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        try:
            refs = json.loads(raw).get("references", [])
        except json.JSONDecodeError:
            continue
        for r in refs:
            if r.get("source", "").startswith("Smarkets") and r.get("markets") and r.get("x12") and r.get("ou"):
                best[(r["home"], r["away"], r.get("kickoff_utc"))] = r
    return list(best.values())


def _fit_inputs(q: dict[str, float]) -> tuple[list[tuple[float, float]], float | None]:
    lines = sorted({float(k.split()[0]) for k in q if k.endswith(" Üst") and k[0].isdigit() and "&" not in k})
    ou = [(ln, q[f"{ln:.1f} Üst"]) for ln in lines if f"{ln:.1f} Üst" in q]
    return ou, q.get("KG Var")


def is_input(name: str, mode: str) -> bool:
    if name in ("MS 1", "MS 0", "MS 2", "2.5 Üst", "2.5 Alt"):
        return True
    if mode == "full":  # every full-time O/U line and BTTS are fit inputs
        return (name[0].isdigit() and "&" not in name and ("Üst" in name or "Alt" in name)) or name in ("KG Var", "KG Yok")
    return False


def kl(q: float, p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    q = min(max(q, 1e-6), 1 - 1e-6)
    return q * math.log(q / p) + (1 - q) * math.log((1 - q) / (1 - p))


def score(refs: list[dict], rho: float, nu: float, kappa: float, a1: float, mode: str) -> tuple[float, dict[str, list[float]]]:
    om.DEFAULT_RHO = rho
    om.league_tail_regime = lambda _league: (nu, 0.0, kappa)
    total, n, by_market = 0.0, 0, {}
    for r in refs:
        q = direct_probabilities(r)
        p1x2 = devig(r["x12"], method="power").probabilities
        p_over = float(devig(r["ou"][1], method="power").probabilities[0])
        kw = {}
        if mode == "full":
            ou, btts = _fit_inputs(q)
            kw = {"ou_lines": [x for x in ou if abs(x[0] - 2.5) > 1e-9], "p_btts": btts}
        mu_h, mu_a, _ = fit_tail_rates_from_markets(p_1x2=p1x2, ou_line=2.5, p_over=p_over, seed_rates=(1.45, 1.15), alpha_nb=0.0,
                                                    rho=rho, shared_kappa=kappa, com_nu=nu, fund_weight=0.0, **kw)
        joint = om.compute_omni_markets(mu_h, mu_a, league=None, first_half_share=a1).joint
        for name, qv in q.items():
            if is_input(name, "full"):  # same evaluation set for both modes: never score O/U or BTTS
                continue
            try:
                pv = goal_probability(name, joint)
            except Exception:  # selection syntax the grid cannot express
                continue
            d = kl(qv, pv)
            total += d
            n += 1
            fam = name.split(" ")[0] if not name[0].isdigit() else ("Gol aralığı" if "Gol" in name else "KG&AÜ")
            by_market.setdefault(fam, []).append(d)
    return (total / n if n else float("nan")), by_market


def main() -> None:
    refs = snapshots()
    half = [r for r in refs if int(hashlib.md5((r["home"] + r["away"]).encode()).hexdigest(), 16) % 2 == 0]
    rest = [r for r in refs if r not in half]
    print(f"{len(refs)} maç (kalibrasyon {len(half)}, test {len(rest)})")
    base = {"rho": -0.03, "nu": 1.0, "kappa": 0.0, "a1": 0.44}
    lines = [f"# Gol modeli — doğrudan borsa fiyatlarına kalibrasyon ({len(refs)} maç)", "",
             "Kayıp = doğrudan kote edilen, modele girdi olmayan seçimlerde ortalama KL(borsa || model). Düşük = daha iyi.", ""]
    results = {}
    for mode in ("basic", "full"):
        grid = []
        for rho, nu, kappa, a1 in itertools.product((-0.08, -0.03, 0.0, 0.04), (0.92, 1.0, 1.08), (0.0, 0.06), (0.42, 0.44, 0.46)):
            loss, _ = score(half, rho, nu, kappa, a1, mode)
            grid.append((loss, rho, nu, kappa, a1))
        grid.sort()
        best = grid[0]
        b_test, b_fam = score(rest, base["rho"], base["nu"], base["kappa"], base["a1"], mode)
        n_test, n_fam = score(rest, best[1], best[2], best[3], best[4], mode)
        results[mode] = (best, b_test, n_test, b_fam, n_fam)
        print(mode, "en iyi", best, "test: mevcut", round(b_test, 5), "yeni", round(n_test, 5))
    lines += ["| Uydurma girdisi | Seçilen ρ / ν / κ / İY payı | Test kaybı (mevcut ayar) | Test kaybı (seçilen ayar) |", "|---|---|---|---|"]
    for mode, (best, b_test, n_test, _, _) in results.items():
        label = "1X2 + 2,5 Alt/Üst (bugünkü üretim)" if mode == "basic" else "1X2 + tüm Alt/Üst çizgileri + KG"
        lines.append(f"| {label} | {best[1]:+.2f} / {best[2]:.2f} / {best[3]:.2f} / {best[4]:.2f} | {b_test:.5f} | {n_test:.5f} |")
    lines += ["", "## Pazar ailesine göre test kaybı (seçilen ayar)", "", "| Aile | basic | full |", "|---|---|---|"]
    fams = sorted(set(results["basic"][4]) | set(results["full"][4]))
    for f in fams:
        b = np.mean(results["basic"][4].get(f, [np.nan]))
        u = np.mean(results["full"][4].get(f, [np.nan]))
        lines.append(f"| {f} | {b:.5f} | {u:.5f} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
