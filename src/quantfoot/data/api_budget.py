"""Daily request budget for API-Football (free plan: 100 requests/day, shared by every script and every AI).

Every network call to API-Football must ``spend()`` first; when the day's cap is reached the call is skipped and the
pipeline continues with its other sources. The counter lives in data/cache/api_football/butce_<TSİ day>.json
(git-ignored). Cap: ``API_FOOTBALL_MAX_REQ`` (default 60, leaving headroom for manual use and the coupon watcher).
Pre-match use only; live polling must never use API-Football.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from filelock import FileLock

from quantfoot.paths import REPO_ROOT

TSI = dt.timezone(dt.timedelta(hours=3))
DEFAULT_DIR = REPO_ROOT / "data" / "cache" / "api_football"
DEFAULT_CAP = 60


def cap() -> int:
    try:
        return max(0, int(os.environ.get("API_FOOTBALL_MAX_REQ", DEFAULT_CAP)))
    except ValueError:
        return DEFAULT_CAP


class ApiBudget:
    def __init__(self, directory: Path | None = None, limit: int | None = None, today: str | None = None):
        self.dir = Path(directory) if directory is not None else DEFAULT_DIR
        self.limit = cap() if limit is None else limit
        self.today = today or dt.datetime.now(TSI).date().isoformat()

    @property
    def path(self) -> Path:
        return self.dir / f"butce_{self.today}.json"

    def used(self) -> int:
        try:
            return self._read_state()["used"]
        except (OSError, ValueError, TypeError, KeyError):
            return self.limit  # unknown state must not reset the quota

    def _read_state(self) -> dict:
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"used": 0, "log": []}
        if not isinstance(state, dict) or type(state.get("used")) is not int or state["used"] < 0:
            raise ValueError("Invalid API budget state")
        if not isinstance(state.get("log", []), list):
            raise ValueError("Invalid API budget log")
        return state

    def remaining(self) -> int:
        return max(0, self.limit - self.used())

    def spend(self, n: int = 1, what: str = "") -> bool:
        """Reserve ``n`` requests; False (nothing reserved) when the cap would be exceeded."""
        if n < 1:
            raise ValueError("Request count must be positive")
        self.dir.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.path) + ".lock"):
            try:
                state = self._read_state()
            except (OSError, ValueError, TypeError, KeyError):
                return False
            used = state["used"]
            if used + n > self.limit:
                return False
            log = state.get("log", [])
            log.append({"t": dt.datetime.now(TSI).isoformat(timespec="seconds"), "n": n, "what": what})
            updated = {"used": used + n, "limit": self.limit, "log": log[-200:]}
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(updated, ensure_ascii=False), encoding="utf-8")
            temp.replace(self.path)
            return True


def default_budget() -> ApiBudget:
    return ApiBudget()
