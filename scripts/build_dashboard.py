"""Build the live static GitHub Pages dashboard payload (`docs/data/dashboard.json`).

    python scripts/build_dashboard.py

Packages the latest analyzed days from ``reports/daily/<date>/``, automatic coupons
(``kupon_*.json``), and the self-learning calibration snapshot (``data/calibration/live_calibration.json``)
into a compact, fast-loading JSON consumed by ``docs/index.html``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from gunluk_analiz import best_pick  # noqa: E402
from nesine_global import DAILY, PREDICTIONS_FILE, TSI, classify_price_tier  # noqa: E402
from quantfoot.paths import QuantfootAIError, ai_area
from quantfoot.data.absences import format_tm_absence_brief  # noqa: E402


def _compact_team_research(r: dict[str, Any] | None, side: str) -> dict[str, Any]:
    r = r or {}
    t = (r.get("teams") or {}).get(side) or {}
    tm = (r.get("tm_absences") or {}).get(side) or {}
    tab = t.get("table") or {}
    out: dict[str, Any] = {}
    if t.get("form"):
        out["form"] = t["form"]
    if tab.get("rank"):
        out["rank"] = f"{int(tab['rank'])}/{tab.get('size', '?')}"
        out["points"] = tab.get("points")
    elif tm.get("rank"):
        out["rank"] = f"#{tm['rank']} (TM)"
        out["points"] = tm.get("points")
    if t.get("rest_days") not in (None, "-"):
        out["rest_days"] = t["rest_days"]
    if tm:
        out["tm_brief"] = format_tm_absence_brief(tm, max_items=4)
        out["gk1_out"] = bool(tm.get("gk1_out"))
        out["top_scorer_out"] = bool(tm.get("top_scorer_out"))
        out["critical_n"] = len(tm.get("critical_absences") or [])
        if tm.get("top_scorers"):
            out["top_scorers"] = [f"{p['name']} ({p['goals']}G)" for p in tm["top_scorers"][:2]]
    if t.get("likely_absent"):
        out["espn_absent"] = [p["name"] for p in t["likely_absent"][:3]]
    return out


def build_day_payload(day_dir: Path) -> dict[str, Any] | None:
    ng_path = day_dir / "nesine_global.json"
    if not ng_path.exists():
        return None
    try:
        data = json.loads(ng_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    store_path = day_dir / PREDICTIONS_FILE
    store = {}
    if store_path.exists():
        try:
            store = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            store = {}

    matches_out: list[dict[str, Any]] = []
    tiers = {"keskin": 0, "global_buro": 0, "dusuk_guven": 0, "fiyatsiz": 0, "ozel_bahis": 0}
    researched_n = 0
    steam_warn_n = 0
    tm_warn_n = 0
    weather_warn_n = 0

    for m in sorted(data.get("matches") or [], key=lambda x: x.get("kickoff", "")):
        tier = m.get("price_tier") or classify_price_tier(m.get("status", ""), m.get("reference"))
        tiers[tier] = tiers.get(tier, 0) + 1
        if tier == "ozel_bahis":
            continue

        r = m.get("research") or {}
        has_res = bool(r.get("teams") or r.get("tm_absences") or r.get("user_absences"))
        if has_res:
            researched_n += 1
        flags = list(r.get("flags") or [])
        if any("Sharp steam" in f for f in flags):
            steam_warn_n += 1
        if any(f.startswith("TM:") for f in flags):
            tm_warn_n += 1
        if any(f.startswith("Hava uyarısı:") for f in flags):
            weather_warn_n += 1

        sels = m.get("selections") or []
        sel_map = {s.get("name"): s.get("fair_prob") for s in sels}
        pick, pick_tag = best_pick(m)
        dist = (store.get(str(m.get("code"))) or {}).get("dist") or {}
        top_scores = [[k, round(float(v), 4)] for k, v in list((dist.get("ft") or {}).items())[:4]]
        htft_top = next(iter((dist.get("htft") or {}).items()), None)

        top_sels = sorted(
            [s for s in sels if (s.get("odds") or 0) >= 1.20 and (s.get("ev") or 0) <= 0.25],
            key=lambda s: -(s.get("fair_prob") or 0.0),
        )[:10]

        matches_out.append(
            {
                "code": m.get("code"),
                "kickoff": m.get("kickoff"),
                "league": m.get("league"),
                "home": m.get("home"),
                "away": m.get("away"),
                "tier": tier,
                "reference": m.get("reference") or "-",
                "fair_1x2": m.get("fair_1x2"),
                "nesine_ms": m.get("nesine_ms"),
                "mu_home": m.get("mu_home"),
                "mu_away": m.get("mu_away"),
                "p_o25": sel_map.get("2.5 Üst"),
                "p_btts": sel_map.get("KG Var"),
                "steam_1x2": m.get("steam_1x2"),
                "top_scores": top_scores,
                "htft": [htft_top[0], round(float(htft_top[1]), 4)] if htft_top else None,
                "best_pick": (
                    {
                        "market": pick["market"],
                        "selection": pick["selection"],
                        "name": pick["name"],
                        "prob": pick["fair_prob"],
                        "odds": pick["odds"],
                        "direct": bool(pick.get("direct")),
                        "tag": pick_tag,
                    }
                    if pick
                    else None
                ),
                "best_pick_note": pick_tag if not pick else "",
                "top_selections": [
                    {
                        "market": s["market"],
                        "selection": s["selection"],
                        "odds": s["odds"],
                        "prob": s["fair_prob"],
                        "ev": s["ev"],
                        "direct": bool(s.get("direct")),
                    }
                    for s in top_sels
                ],
                "flags": flags,
                "weather": r.get("weather"),
                "research": {
                    "has_data": has_res,
                    "h2h": r.get("h2h"),
                    "home": _compact_team_research(r, "home"),
                    "away": _compact_team_research(r, "away"),
                },
            }
        )

    coupons_out: list[dict[str, Any]] = []
    coupon_files = list(day_dir.glob("kupon_*.json"))
    # Optional extra look in this AI's own folder when day_dir is a legacy/shared path.
    # Never opens another AI's folder. If QUANTFOOT_AI is unset, only day_dir is used.
    try:
        own_dir = ai_area() / day_dir.name
    except QuantfootAIError:
        own_dir = day_dir
    if Path(own_dir).resolve() != day_dir.resolve():
        coupon_files += list(Path(own_dir).glob("kupon_*x_*.json"))
    for kf in sorted(coupon_files, key=lambda f: f.name, reverse=True)[:8]:
        try:
            kd = json.loads(kf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        coupons_out.append(
            {
                "file": kf.name,
                "target": kd.get("target"),
                "created": kd.get("created"),
                "coupons": kd.get("coupons") or [],
            }
        )

    real_total = len(matches_out)
    global_total = tiers["keskin"] + tiers["global_buro"]
    return {
        "date": day_dir.name,
        "generated_at": data.get("generated_at"),
        "summary": {
            "real_matches": real_total,
            "global_priced": global_total,
            "global_pct": round(global_total / real_total * 100.0, 1) if real_total else 0.0,
            "keskin": tiers["keskin"],
            "global_buro": tiers["global_buro"],
            "dusuk_guven": tiers["dusuk_guven"],
            "fiyatsiz": tiers["fiyatsiz"],
            "ozel_bahis": tiers["ozel_bahis"],
            "researched": researched_n,
            "steam_alerts": steam_warn_n,
            "tm_alerts": tm_warn_n,
            "weather_alerts": weather_warn_n,
        },
        "matches": matches_out,
        "coupons": coupons_out,
    }



def current_betting_day(now: dt.datetime | None = None) -> str:
    """The Nesine betting day runs 07:00-07:00 TSİ; before 07:00 the current slate is still yesterday's."""
    now = now or dt.datetime.now(TSI)
    return (now.date() if now.hour >= 7 else now.date() - dt.timedelta(days=1)).isoformat()

def build_dashboard_data(
    *,
    daily_dir: Path = DAILY,
    calibration_path: Path = ROOT / "data" / "calibration" / "live_calibration.json",
    out_dir: Path = ROOT / "docs" / "data",
    max_days: int = 7,
    open_from: str | None = None,
) -> Path:
    """Export per-day compact JSON files + main ``docs/data/dashboard.json`` index for GitHub Pages."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Only settled betting days are published (user, 20 Nov): today's and future predictions must not be visible on
    # GitHub, where other AIs look; a day appears here once the next morning's settlement has run.
    open_from = open_from or current_betting_day()
    day_dirs = sorted(
        [p for p in daily_dir.iterdir() if p.is_dir() and (p / "nesine_global.json").exists() and p.name < open_from],
        reverse=True,
    ) if daily_dir.exists() else []

    available_dates: list[dict[str, Any]] = []
    latest_payload: dict[str, Any] | None = None

    for d in day_dirs[:max_days]:
        day_payload = build_day_payload(d)
        if not day_payload:
            continue
        (out_dir / f"{d.name}.json").write_text(
            json.dumps(day_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        available_dates.append({"date": d.name, "summary": day_payload["summary"]})
        if latest_payload is None:
            latest_payload = day_payload


    calibration = {}
    if calibration_path.exists():
        try:
            calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            calibration = {}

    dashboard = {
        "built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "built_tsi": dt.datetime.now(TSI).isoformat(timespec="seconds"),
        "default_date": latest_payload["date"] if latest_payload else None,
        "dates": available_dates,
        "latest": latest_payload,
        "calibration": calibration,
    }
    target = out_dir / "dashboard.json"
    target.write_text(json.dumps(dashboard, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--daily-dir", type=Path, default=DAILY)
    ap.add_argument("--calibration", type=Path, default=ROOT / "data" / "calibration" / "live_calibration.json")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "docs" / "data")
    ap.add_argument("--max-days", type=int, default=7)
    args = ap.parse_args()

    target = build_dashboard_data(
        daily_dir=args.daily_dir,
        calibration_path=args.calibration,
        out_dir=args.out_dir,
        max_days=args.max_days,
    )
    print(f"Dashboard verisi üretildi -> {target}")


if __name__ == "__main__":
    main()
