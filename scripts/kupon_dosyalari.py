"""Find the current coupon for each target and market family in one betting day."""

import datetime as dt
import json
from pathlib import Path


def coupon_group(path: Path) -> tuple[str, str]:
    parts = path.stem.split("_")
    return parts[1], parts[2] if len(parts) >= 4 else "karma"


def latest_coupons(day: Path) -> dict[tuple[str, str], Path]:
    latest = {}
    for path in day.glob("kupon_*x_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        stamp = data.get("created")
        if not stamp:  # Legacy filenames only record Istanbul time within the 07:00–07:00 betting day.
            hhmm = path.stem.rsplit("_", 1)[1]
            date = dt.date.fromisoformat(day.name) + dt.timedelta(days=int(hhmm < "0700"))
            stamp = f"{date}T{hhmm[:2]}:{hhmm[2:]}:00+03:00"
        group = coupon_group(path)
        candidate = (dt.datetime.fromisoformat(stamp).timestamp(), path)
        if group not in latest or candidate > latest[group]:
            latest[group] = candidate
    return {group: path for group, (_, path) in latest.items()}
