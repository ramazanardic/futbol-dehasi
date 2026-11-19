"""Entry point for the Windows Task Scheduler jobs that keep the daily ledger running.

    python scripts/scheduled.py morning    # 09:00: settle yesterday (results + verify + summary), then run today
    python scripts/scheduled.py snapshot   # every 30 min: record pre-kickoff odds for today and yesterday

Late kick-offs (e.g. Brazil at 03:30 TSİ) belong to the previous day's slate, so the snapshot
job also refreshes yesterday's matches that have not started yet. Each step runs in its own
process so one failure (e.g. ESPN down) does not stop the others. Output goes to
reports/daily/logs/<date>.log.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DAILY_SCRIPT = ROOT / "scripts" / "daily.py"
LOG_DIR = ROOT / "reports" / "daily" / "logs"


def _run(args: list[str], log) -> int:
    log.write(f"\n[{dt.datetime.now().isoformat(timespec='seconds')}] daily.py {' '.join(args)}\n")
    log.flush()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(DAILY_SCRIPT), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    log.write(proc.stdout)
    if proc.returncode:
        log.write(f"HATA (çıkış kodu {proc.returncode}):\n{proc.stderr}\n")
    log.flush()
    return proc.returncode


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / f"{today.isoformat()}.log").open("a", encoding="utf-8") as log:
        if mode == "morning":
            y = yesterday.isoformat()
            if (ROOT / "reports" / "daily" / y / "predictions.json").exists():
                _run(["results", "--date", y], log)
                _run(["verify", "--date", y], log)
            _run(["summary"], log)
            _run(["run", "--date", today.isoformat()], log)
        elif mode == "snapshot":
            for day in (yesterday, today):
                if (ROOT / "reports" / "daily" / day.isoformat() / "predictions.json").exists():
                    _run(["snapshot", "--date", day.isoformat()], log)
        else:
            raise SystemExit("Kullanım: scheduled.py morning|snapshot")


if __name__ == "__main__":
    main()
