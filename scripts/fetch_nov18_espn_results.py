"""Fetch actual HT and FT scores from ESPN for all Nov 18, 2026 matches."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]


def fetch_one(m: dict) -> dict:
    eid = str(m["event_id"])
    slug = m["slug"]
    if not eid.isdigit():
        return {"idx": m["idx"], "event_id": eid, "found": False}

    jd = {}
    for s in (slug, "all"):
        try:
            r = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/soccer/{s}/summary",
                params={"event": eid},
                timeout=10,
            )
            if r.status_code == 200:
                jd = r.json()
                break
        except Exception:
            continue

    comp = ((jd.get("header") or {}).get("competitions") or [{}])[0]
    st = comp.get("status", {}).get("type", {})
    cs = comp.get("competitors", [])
    hc = next((c for c in cs if c.get("homeAway") == "home"), {})
    ac = next((c for c in cs if c.get("homeAway") == "away"), {})

    # Extract halftime score from keyEvents or commentary or linescores
    ft_h = hc.get("score")
    ft_a = ac.get("score")
    ht_h = None
    ht_a = None

    key_events = jd.get("keyEvents") or []
    if key_events and ft_h is not None and ft_a is not None:
        h1, a1 = 0, 0
        hid = str(hc.get("id") or (hc.get("team") or {}).get("id") or "")
        aid = str(ac.get("id") or (ac.get("team") or {}).get("id") or "")
        for kev in key_events:
            t_txt = (kev.get("type") or {}).get("text", "").lower()
            is_goal = ("goal" in t_txt or "penalty - scored" in t_txt or "own goal" in t_txt) and ("miss" not in t_txt and "saved" not in t_txt and "disallowed" not in t_txt)
            if not is_goal:
                continue
            period = (kev.get("period") or {}).get("number", 0)
            clock_val = (kev.get("clock") or {}).get("value", 0)
            disp_clock = (kev.get("clock") or {}).get("displayValue", "")
            in_1h = (period == 1) or (period == 0 and (clock_val <= 2700 or disp_clock.startswith("45'")))
            if in_1h:
                ev_tid = str((kev.get("team") or {}).get("id", ""))
                if ev_tid == hid:
                    h1 += 1
                elif ev_tid == aid:
                    a1 += 1
        ht_h, ht_a = h1, a1

    return {
        "idx": m["idx"],
        "event_id": eid,
        "ko_tsi": m["ko_tsi"],
        "league": m["league"],
        "home": m["home"],
        "away": m["away"],
        "status_name": st.get("name"),
        "status_detail": st.get("detail"),
        "state": st.get("state"),
        "ft_h": int(ft_h) if str(ft_h).isdigit() else None,
        "ft_a": int(ft_a) if str(ft_a).isdigit() else None,
        "ht_h": ht_h,
        "ht_a": ht_a,
        "best_bet": m["best_valid_bet"]["selection"] if m.get("best_valid_bet") else None,
        "best_odds": m["best_valid_bet"]["offered_odds"] if m.get("best_valid_bet") else None,
    }


def main() -> None:
    d = json.loads((REPO_ROOT / "reports" / "today_v6_predictions_2026_11_18.json").read_text(encoding="utf-8"))["matches"]
    espn_m = [m for m in d if str(m["event_id"]).isdigit()]
    results = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        for res in pool.map(fetch_one, espn_m):
            results.append(res)

    results.sort(key=lambda x: x["idx"])
    for r in results:
        ht_str = f"(İY {r['ht_h']}-{r['ht_a']})" if r["ht_h"] is not None else ""
        print(
            f"#{r['idx']:2d} [{r['ko_tsi']}] {r['home']} vs {r['away']} ({r['league']}) -> "
            f"{r['status_name']} ({r['status_detail']}): MS {r['ft_h']}-{r['ft_a']} {ht_str} | "
            f"BestBet: {r['best_bet']} @ {r['best_odds']}"
        )

    out_p = REPO_ROOT / "reports" / "nov18_espn_actuals.json"
    out_p.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
