"""Every goal-based betting market priced exactly from one coherent joint distribution.

The joint J[h1, a1, h2, a2] (goals per team in each half, see `OmniMarketBundle.joint`) is
the single source of truth: each selection is an event on that state space, so all markets
and all same-game combinations are mutually consistent by construction (cf. Rana et al.
2026, "ParlayMarket", arXiv:2603.22596: parlay prices as marginals of one coherent
distribution).

Selection names (Turkish market conventions; draw = "0", "X" also accepted):
    MS 1 | MS 0 | MS 2                      Maç sonucu
    ÇŞ 1X | ÇŞ 12 | ÇŞ X2                   Çifte şans
    2.5 Üst | 2.5 Alt                       Maç geneli alt/üst (any n.5)
    İY 1.5 Üst | 2Y 0.5 Alt                 Devre alt/üst
    Ev 1.5 Üst | Dep 0.5 Alt                Takım alt/üst
    0-1 Gol | 2-3 Gol | 4-5 Gol | 6+ Gol    Toplam gol aralığı (any a-b)
    Tek | Çift | İY Tek | İY Çift           Tek/çift
    KG Var | KG Yok | İY KG Var | 2Y KG Var | İki Yarıda KG Var
    Skor 2-1 | İY Skor 1-0 | 2Y Skor 0-0    Doğru skor
    İY 1 | İY 0 | İY 2 | 2Y 1 | 2Y 0 | 2Y 2 Devre sonucu
    İY/MS 1/1 | İY/MS 0/2 ...               İlk yarı / maç sonucu
    Hnd(-1) 1 | Hnd(-1) 0 | Hnd(+2) 2       Avrupa handikabı (applied to the home team)
    Ev Gol Atar | Ev Gol Yemez | Ev Gol Yemeden Kazanır | Ev İki Yarıda Gol
    Ev Her İki Yarıyı Kazanır | Ev En Az Bir Yarıyı Kazanır   (same for "Dep")
    En Çok Gol 1Y | En Çok Gol 2Y | En Çok Gol Eşit
    A & B & ...                             Kombine: logical AND of any of the above

Markets with pushes / half results (Asian handicap, Asian totals, Draw-No-Bet) are
returned as `Outcome` objects because their settlement is not a single probability.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

import numpy as np

_DRAW_ALIASES = {"0": 0, "X": 0, "x": 0, "1": 1, "2": -1}
_DC = {"1X": (1, 0), "10": (1, 0), "12": (1, -1), "X2": (0, -1), "02": (0, -1)}


@dataclass(frozen=True)
class Outcome:
    """Settlement probabilities for one selection (Asian lines can half-win / push / half-lose)."""

    win: float
    push: float = 0.0
    half_win: float = 0.0
    half_lose: float = 0.0

    @property
    def lose(self) -> float:
        return max(0.0, 1.0 - self.win - self.push - self.half_win - self.half_lose)

    def ev(self, decimal_odds: float) -> float:
        """Expected profit per unit stake at the given decimal odds."""
        gain = self.win + 0.5 * self.half_win
        loss = self.lose + 0.5 * self.half_lose
        return gain * (decimal_odds - 1.0) - loss

    @property
    def fair_odds(self) -> float:
        """Zero-EV decimal odds."""
        gain = self.win + 0.5 * self.half_win
        loss = self.lose + 0.5 * self.half_lose
        return float("inf") if gain <= 1e-12 else 1.0 + loss / gain


class GoalGrid:
    """Flattened view of the joint goal distribution with per-state goal counts."""

    def __init__(self, joint: np.ndarray) -> None:
        j = np.asarray(joint, dtype=float)
        if j.ndim != 4:
            raise ValueError("joint must be a 4-D array J[h1, a1, h2, a2].")
        i1, j1, i2, j2 = np.indices(j.shape)
        self.p = (j / j.sum()).ravel()
        self.h1, self.a1, self.h2, self.a2 = i1.ravel(), j1.ravel(), i2.ravel(), j2.ravel()
        self.fh, self.fa = self.h1 + self.h2, self.a1 + self.a2

    def prob(self, mask: np.ndarray) -> float:
        return float(self.p[mask].sum())


def _sign(x: np.ndarray) -> np.ndarray:
    return np.sign(x).astype(int)


def _half(g: GoalGrid, which: str) -> tuple[np.ndarray, np.ndarray]:
    if which == "İY":
        return g.h1, g.a1
    if which == "2Y":
        return g.h2, g.a2
    return g.fh, g.fa


def _team(g: GoalGrid, team: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (scored_1h, conceded_1h, scored_2h, conceded_2h) for 'Ev' or 'Dep'."""
    if team == "Ev":
        return g.h1, g.a1, g.h2, g.a2
    return g.a1, g.h1, g.a2, g.h2


def goal_event_mask(name: str, g: GoalGrid) -> np.ndarray:
    """Boolean mask over joint states for a goal-based selection name (supports 'A & B')."""
    if "&" in name:
        mask = np.ones_like(g.p, dtype=bool)
        for part in name.split("&"):
            mask &= goal_event_mask(part.strip(), g)
        return mask
    s = name.strip()

    m = re.fullmatch(r"(?:(İY|2Y) )?(MS )?([10X2x])", s)
    if m and (m.group(1) or m.group(2)):
        h, a = _half(g, m.group(1) or "MS")
        return _sign(h - a) == _DRAW_ALIASES[m.group(3)]
    m = re.fullmatch(r"İY/MS ([10X2x])/([10X2x])", s)
    if m:
        return (_sign(g.h1 - g.a1) == _DRAW_ALIASES[m.group(1)]) & (_sign(g.fh - g.fa) == _DRAW_ALIASES[m.group(2)])
    m = re.fullmatch(r"(?:(İY|2Y) )?ÇŞ (1X|10|12|X2|02)", s)
    if m:
        h, a_ = _half(g, m.group(1) or "MS")
        res = _sign(h - a_)
        a, b = _DC[m.group(2)]
        return (res == a) | (res == b)
    m = re.fullmatch(r"(Ev|Dep) (İY|2Y) (\d+\.5) (Üst|Alt)", s)
    if m:  # one team's goals in one half
        s1, _, s2, _ = _team(g, m.group(1))
        over = (s1 if m.group(2) == "İY" else s2) > float(m.group(3))
        return over if m.group(4) == "Üst" else ~over
    m = re.fullmatch(r"(?:(İY|2Y|Ev|Dep) )?(\d+\.5) (Üst|Alt)", s)
    if m:
        scope = m.group(1)
        if scope in ("Ev", "Dep"):
            s1, _, s2, _ = _team(g, scope)
            tot = s1 + s2
        else:
            h, a = _half(g, scope or "MS")
            tot = h + a
        over = tot > float(m.group(2))
        return over if m.group(3) == "Üst" else ~over
    m = re.fullmatch(r"(\d+)-(\d+) Gol", s)
    if m:
        tot = g.fh + g.fa
        return (tot >= int(m.group(1))) & (tot <= int(m.group(2)))
    m = re.fullmatch(r"(?:\+(\d+)|(\d+)\+) Gol", s)
    if m:
        return g.fh + g.fa >= int(m.group(1) or m.group(2))
    m = re.fullmatch(r"(?:(İY|2Y) )?(Tek|Çift)", s)
    if m:
        h, a = _half(g, m.group(1) or "MS")
        odd = (h + a) % 2 == 1
        return odd if m.group(2) == "Tek" else ~odd
    m = re.fullmatch(r"(?:(İY|2Y) )?KG (Var|Yok)", s)
    if m:
        h, a = _half(g, m.group(1) or "MS")
        yes = (h >= 1) & (a >= 1)
        return yes if m.group(2) == "Var" else ~yes
    if s == "İki Yarıda KG Var":
        return (g.h1 >= 1) & (g.a1 >= 1) & (g.h2 >= 1) & (g.a2 >= 1)
    m = re.fullmatch(r"(?:(İY|2Y) )?Skor (\d+)-(\d+)", s)
    if m:
        h, a = _half(g, m.group(1) or "MS")
        return (h == int(m.group(2))) & (a == int(m.group(3)))
    m = re.fullmatch(r"Hnd\(([+-]?\d+)\) ([10X2x])", s)
    if m:
        return _sign(g.fh + int(m.group(1)) - g.fa) == _DRAW_ALIASES[m.group(2)]
    m = re.fullmatch(r"(Ev|Dep) (Gol Atar|Gol Yemez|Gol Yemeden Kazanır|İki Yarıda Gol|Her İki Yarıyı Kazanır|En Az Bir Yarıyı Kazanır)", s)
    if m:
        s1, c1, s2, c2 = _team(g, m.group(1))
        kind = m.group(2)
        if kind == "Gol Atar":
            return s1 + s2 >= 1
        if kind == "Gol Yemez":
            return c1 + c2 == 0
        if kind == "Gol Yemeden Kazanır":
            return (c1 + c2 == 0) & (s1 + s2 >= 1)
        if kind == "İki Yarıda Gol":
            return (s1 >= 1) & (s2 >= 1)
        if kind == "Her İki Yarıyı Kazanır":
            return (s1 > c1) & (s2 > c2)
        return (s1 > c1) | (s2 > c2)
    m = re.fullmatch(r"(?:(Ev|Dep) )?En Çok Gol (1Y|2Y|Eşit)", s)
    if m:
        if m.group(1):
            t1, _, t2, _ = _team(g, m.group(1))
        else:
            t1, t2 = g.h1 + g.a1, g.h2 + g.a2
        return {"1Y": t1 > t2, "2Y": t2 > t1, "Eşit": t1 == t2}[m.group(2)]
    m = re.fullmatch(r"Fark (?:(Ev|Dep) (\d+)(\+)?|0)", s)
    if m:  # winning margin
        diff = g.fh - g.fa
        if not m.group(1):
            return diff == 0
        d = diff if m.group(1) == "Ev" else -diff
        n = int(m.group(2))
        return d >= n if m.group(3) else d == n
    raise KeyError(f"Bilinmeyen gol pazarı seçimi: {name!r}")


def goal_probability(name: str, joint: np.ndarray) -> float:
    """Probability of any goal-based selection or AND-combination."""
    g = GoalGrid(joint)
    return g.prob(goal_event_mask(name, g))


@lru_cache(maxsize=64)
def _sub_lines(line: float) -> tuple[float, ...]:
    q = round(line * 4) / 4
    return (q - 0.25, q + 0.25) if round(q * 4) % 2 else (q,)


def _asian_outcome(values: np.ndarray, probs: np.ndarray, line: float) -> Outcome:
    """Settle `values + line` (>0 win, 0 push, <0 lose), splitting quarter lines in two."""
    subs = _sub_lines(line)
    res = np.stack([np.sign(values + s) for s in subs])  # each +1 / 0 / -1
    score = res.sum(axis=0)  # for quarter lines: 2=win, 1=half win, 0=push, -1=half lose, -2=lose
    if len(subs) == 1:
        return Outcome(win=float(probs[score > 0].sum()), push=float(probs[score == 0].sum()))
    return Outcome(
        win=float(probs[score == 2].sum()),
        half_win=float(probs[score == 1].sum()),
        push=float(probs[score == 0].sum()),
        half_lose=float(probs[score == -1].sum()),
    )


def asian_handicap(joint: np.ndarray, line: float, side: str = "Ev") -> Outcome:
    """Asian handicap `line` for `side` ('Ev' or 'Dep'), whole / half / quarter lines."""
    g = GoalGrid(joint)
    gd = (g.fh - g.fa) if side == "Ev" else (g.fa - g.fh)
    return _asian_outcome(gd.astype(float), g.p, line)


def asian_total(joint: np.ndarray, line: float, side: str = "Üst") -> Outcome:
    """Asian total goals line (e.g. 2.25, 2.75); side 'Üst' or 'Alt'."""
    g = GoalGrid(joint)
    tot = (g.fh + g.fa).astype(float)
    # Over L wins when tot - L > 0; Under L wins when L - tot > 0 (quarter lines split around L).
    if side == "Üst":
        return _asian_outcome(tot, g.p, -line)
    return _asian_outcome(-tot, g.p, line)


def draw_no_bet(joint: np.ndarray, side: str = "Ev") -> Outcome:
    """Beraberlikte iade (DNB): stake returned on a draw — identical to Asian handicap 0."""
    return asian_handicap(joint, 0.0, side)


def price_goal_markets(joint: np.ndarray) -> dict[str, dict[str, float]]:
    """Fair probabilities for every standard goal-based selection, grouped by market family."""
    g = GoalGrid(joint)

    def fam(names: list[str]) -> dict[str, float]:
        return {n: g.prob(goal_event_mask(n, g)) for n in names}

    ft_scores = [f"Skor {i}-{j}" for i in range(7) for j in range(7)]
    ft = fam(ft_scores)
    ft["Skor Diğer"] = max(0.0, 1.0 - sum(ft.values()))
    ht_scores = [f"İY Skor {i}-{j}" for i in range(4) for j in range(4)]
    ht = fam(ht_scores)
    ht["İY Skor Diğer"] = max(0.0, 1.0 - sum(ht.values()))
    lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    team = []
    for t in ("Ev", "Dep"):
        team += [f"{t} {ln} {s}" for ln in (0.5, 1.5, 2.5, 3.5) for s in ("Üst", "Alt")]
        team += [f"{t} {k}" for k in ("Gol Atar", "Gol Yemez", "Gol Yemeden Kazanır", "İki Yarıda Gol",
                                      "Her İki Yarıyı Kazanır", "En Az Bir Yarıyı Kazanır")]
    combos = [f"MS {r} & {ln} {s}" for r in "102" for ln in (1.5, 2.5, 3.5, 4.5) for s in ("Üst", "Alt")]
    combos += [f"MS {r} & KG {k}" for r in "102" for k in ("Var", "Yok")]
    combos += [f"ÇŞ {d} & {ln} {s}" for d in ("1X", "12", "X2") for ln in (1.5, 2.5, 3.5) for s in ("Üst", "Alt")]
    combos += [f"ÇŞ {d} & KG {k}" for d in ("1X", "12", "X2") for k in ("Var", "Yok")]
    combos += [f"{ln} {s} & KG {k}" for ln in (2.5, 3.5) for s in ("Üst", "Alt") for k in ("Var", "Yok")]

    return {
        "Maç Sonucu": fam(["MS 1", "MS 0", "MS 2"]),
        "Çifte Şans": fam(["ÇŞ 1X", "ÇŞ 12", "ÇŞ X2"]),
        "Alt/Üst": fam([f"{ln} {s}" for ln in lines for s in ("Üst", "Alt")]),
        "Toplam Gol Aralığı": fam(["0-1 Gol", "2-3 Gol", "4-5 Gol", "6+ Gol", "2-4 Gol", "3-5 Gol"]),
        "Tek/Çift": fam(["Tek", "Çift", "İY Tek", "İY Çift"]),
        "Karşılıklı Gol": fam(["KG Var", "KG Yok", "İY KG Var", "İY KG Yok", "2Y KG Var", "2Y KG Yok", "İki Yarıda KG Var"]),
        "Avrupa Handikabı": fam([f"Hnd({h:+d}) {r}" for h in (-3, -2, -1, 1, 2, 3) for r in "102"]),
        "Doğru Skor": ft,
        "İlk Yarı": {**fam(["İY 1", "İY 0", "İY 2"] + [f"İY {ln} {s}" for ln in (0.5, 1.5, 2.5) for s in ("Üst", "Alt")]), **ht},
        "İkinci Yarı": fam(["2Y 1", "2Y 0", "2Y 2"] + [f"2Y {ln} {s}" for ln in (0.5, 1.5, 2.5) for s in ("Üst", "Alt")]),
        "İY/MS": fam([f"İY/MS {a}/{b}" for a in "102" for b in "102"]),
        "Takım Golleri": fam(team),
        "En Çok Gol Olan Yarı": fam(["En Çok Gol 1Y", "En Çok Gol 2Y", "En Çok Gol Eşit"]),
        "Kombine": fam(combos),
    }


def price_asian_markets(joint: np.ndarray) -> dict[str, dict[str, Outcome]]:
    """Asian handicap (whole / half / quarter), Asian totals and Draw-No-Bet with push handling."""
    ah: dict[str, Outcome] = {}
    for q in range(-12, 13):  # -3.00 ... +3.00 in 0.25 steps
        line = q / 4
        ah[f"Ev {line:+.2f}"] = asian_handicap(joint, line, "Ev")
        ah[f"Dep {line:+.2f}"] = asian_handicap(joint, line, "Dep")
    totals: dict[str, Outcome] = {}
    for q in range(6, 19):  # 1.50 ... 4.50
        line = q / 4
        totals[f"{line:.2f} Üst"] = asian_total(joint, line, "Üst")
        totals[f"{line:.2f} Alt"] = asian_total(joint, line, "Alt")
    return {
        "Asya Handikabı": ah,
        "Asya Alt/Üst": totals,
        "Beraberlikte İade": {"DNB Ev": draw_no_bet(joint, "Ev"), "DNB Dep": draw_no_bet(joint, "Dep")},
    }
