"""Find the current coupon for each target and market family in one betting day."""

import datetime as dt
import json
from pathlib import Path

from quantfoot.data.nesine import BETTING_DAY_START, TSI


def coupon_group(path: Path) -> tuple[str, str]:
    parts = path.stem.split("_")
    return parts[1], parts[2] if len(parts) >= 4 else "karma"


def latest_coupons(day: Path) -> dict[tuple[str, str], Path]:
    latest = {}
    for path in day.glob("kupon_*x_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            stamp = data.get("created")
            if stamp:
                created = dt.datetime.fromisoformat(stamp)
            else:  # Legacy filenames record only Istanbul time within the betting day.
                hhmm = path.stem.rsplit("_", 1)[1]
                if len(hhmm) != 4:
                    continue
                clock = dt.time(int(hhmm[:2]), int(hhmm[2:]))
                date = dt.date.fromisoformat(day.name) + dt.timedelta(days=clock < BETTING_DAY_START)
                created = dt.datetime.combine(date, clock)
            if created.tzinfo is None:
                created = created.replace(tzinfo=TSI)
            group = coupon_group(path)
            candidate = (created.timestamp(), path)
        except (OSError, ValueError, TypeError, IndexError):
            continue
        if group not in latest or candidate > latest[group]:
            latest[group] = candidate
    return {group: path for group, (_, path) in latest.items()}
