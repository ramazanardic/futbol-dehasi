"""Result fetching and bet settlement shared by the daily pipeline and the bet ledger.

Settlement reuses the exact selection parser used for pricing (`goal_markets.goal_event_mask`)
on a one-state distribution, so a market can never be priced one way and settled another.
Bets settle on the 90-minute score: ESPN period line scores give HT = 1st period and
90' = 1st + 2nd period, so extra time and penalties are excluded.
"""

from __future__ import annotations

import numpy as np
import requests

from quantfoot.markets.goal_markets import goal_probability

ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/summary"


def settle_selection(name: str, ht: tuple[int, int], ft90: tuple[int, int]) -> bool | None:
    """True / False for a goal-based selection given HT and 90-minute scores; None if unknown."""
    h1, a1 = int(ht[0]), int(ht[1])
    h2, a2 = int(ft90[0]) - h1, int(ft90[1]) - a1
    if min(h1, a1, h2, a2) < 0:
        raise ValueError(f"İY skoru maç sonu skorunu aşamaz: İY {ht}, MS {ft90}")
    if name in ("İlk Gol Ev", "İlk Gol Dep", "İlk Gol Yok"):
        # First scorer from the scores alone: only one side scored (in the match, or in the first half);
        # both sides scoring in the same half leaves the order unknown.
        if h1 + a1 + h2 + a2 == 0:
            first = "Yok"
        elif (h1 > 0) != (a1 > 0):
            first = "Ev" if h1 > 0 else "Dep"
        elif h1 + a1 == 0 and (h2 > 0) != (a2 > 0):
            first = "Ev" if h2 > 0 else "Dep"
        else:
            return None
        return name.endswith(first)
    g = max(h1, a1, h2, a2) + 1
    joint = np.zeros((g, g, g, g))
    joint[h1, a1, h2, a2] = 1.0
    try:
        return goal_probability(name, joint) > 0.5
    except KeyError:
        return None


def fetch_espn_result(event_id: str, slug: str | None = None, timeout: float = 15.0) -> dict:
    """Fetch {'completed', 'status', 'ht', 'ft90'} for one ESPN event (ht / ft90 only when completed)."""
    rec: dict = {"completed": False, "status": None}
    if not str(event_id).isdigit():
        rec["status"] = "ESPN dışı maç (manuel sonuç gerekli)"
        return rec
    for s in [x for x in (slug, "all") if x]:
        try:
            r = requests.get(ESPN_SUMMARY.format(slug=s), params={"event": event_id}, timeout=timeout)
            if r.status_code != 200:
                continue
            comp = r.json()["header"]["competitions"][0]
        except Exception as exc:  # network error or unexpected payload: leave pending
            rec["status"] = f"hata: {exc}"
            continue
        st = comp["status"]["type"]
        sides = {
            c["homeAway"]: [int(float(x.get("displayValue", 0) or 0)) for x in c.get("linescores", [])]
            for c in comp["competitors"]
        }
        h, a = sides.get("home", []), sides.get("away", [])
        rec["status"] = st.get("detail")
        if st.get("completed") and len(h) >= 2 and len(a) >= 2:
            rec.update(completed=True, ht=[h[0], a[0]], ft90=[h[0] + h[1], a[0] + a[1]])
        return rec
    return rec
