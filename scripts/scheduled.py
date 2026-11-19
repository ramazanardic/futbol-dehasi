"""Entry point for the Windows Task Scheduler jobs that keep the daily ledger running.

    python scripts/scheduled.py morning    # 09:00: settle yesterday (results + verify + summary), run today,
                                           #        then price the Nesine bulletin against the global reference
    python scripts/scheduled.py snapshot   # every 30 min: record pre-kickoff odds for today and yesterday
    python scripts/scheduled.py analiz     # hourly at :50: pull the fresh global prices (Actions refreshes at :40)
                                           #        and re-run the Nesine analysis for the next 5 betting days

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


def _run(args: list[str], log, script: Path = DAILY_SCRIPT) -> int:
    log.write(f"\n[{dt.datetime.now().isoformat(timespec='seconds')}] {script.name} {' '.join(args)}\n")
    log.flush()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, str(script), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    log.write(proc.stdout)
    if proc.returncode:
        log.write(f"HATA (çıkış kodu {proc.returncode}):\n{proc.stderr}\n")
    log.flush()
    return proc.returncode


def _pull(log) -> None:
    pull = subprocess.run(["git", "pull", "--rebase", "--autostash", "-q"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    log.write(f"\n[git pull] çıkış kodu {pull.returncode} {pull.stderr.strip()}\n")


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
            # Pull the sharp prices GitHub Actions fetched abroad (data/global_odds/latest), then price
            # the Nesine bulletin against them (Pinnacle -> Smarkets -> ESPN).
            _pull(log)
            _run(["--date", today.isoformat()], log, ROOT / "scripts" / "nesine_global.py")
        elif mode == "analiz":
            _pull(log)
            # betting day runs 07:00-07:00: before 07:00 the current slate is still yesterday's
            day = today if dt.datetime.now().hour >= 7 else yesterday
            _run(["--date", day.isoformat(), "--hafta", "5"], log, ROOT / "scripts" / "nesine_global.py")
        elif mode == "snapshot":
            for day in (yesterday, today):
                if (ROOT / "reports" / "daily" / day.isoformat() / "predictions.json").exists():
                    _run(["snapshot", "--date", day.isoformat()], log)
        else:
            raise SystemExit("Kullanım: scheduled.py morning|snapshot|analiz")


if __name__ == "__main__":
    main()
