"""Entry point for the Windows Task Scheduler jobs that keep the daily ledger running.

    python scripts/scheduled.py morning    # 09:00: settle yesterday (results + verify + summary), run today,
                                           #        then price the Nesine bulletin against the global reference
    python scripts/scheduled.py snapshot   # every 30 min: record pre-kickoff odds for today and yesterday
    python scripts/scheduled.py kadro      # at :10 and :30: re-analyse today (line-ups published ~1 h before kick-off)
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


GLOBAL_FILE = ROOT / "data" / "global_odds" / "latest" / "references.json"
TRIGGER_FILE = ROOT / "data" / "global_odds" / "trigger.txt"
STALE_HOURS = 2.5   # GitHub's scheduler skipped runs if the sharp prices are older than this (coupons refuse > 3 h)
RETRIGGER_HOURS = 1.5


def _data_age_hours() -> float | None:
    try:
        import json
        gen = json.loads(GLOBAL_FILE.read_text(encoding="utf-8")).get("generated_utc")
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(gen)).total_seconds() / 3600
    except (OSError, ValueError, TypeError):
        return None


def _kick_fetch_if_stale(log) -> None:
    """Backup for GitHub's best-effort cron: when the overseas fetch has not run for STALE_HOURS, push a
    one-line trigger file; the workflow runs on pushes to that path (a normal git push, no extra token)."""
    age = _data_age_hours()
    if age is not None and age < STALE_HOURS:
        return
    if TRIGGER_FILE.exists():
        try:
            last = dt.datetime.fromisoformat(TRIGGER_FILE.read_text(encoding="utf-8").strip())
            if dt.datetime.now(dt.timezone.utc) - last < dt.timedelta(hours=RETRIGGER_HOURS):
                return  # already kicked recently; give that run time to finish
        except ValueError:
            pass
    TRIGGER_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds") + "\n", encoding="utf-8")
    rel = str(TRIGGER_FILE.relative_to(ROOT))
    steps = (["git", "add", rel], ["git", "commit", "-q", "-m", f"chore(trigger): global data {age if age is None else round(age, 1)} h old",
                                    "--", rel], ["git", "push", "-q"])
    for cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        log.write(f"[tetik] {' '.join(cmd[:2])}: {r.returncode} {r.stderr.strip()}\n")
        if r.returncode:
            return


STATUS_FILE = ROOT / "reports" / "DURUM.md"
ALERT_HOURS = 8.0  # data this old even after the backup trigger -> pop-up warning on this PC


def _write_status(log, note: str) -> None:
    """One-page health report (data age, last runs); a Windows pop-up when the sharp data is very stale."""
    age = _data_age_hours()
    last_trigger = TRIGGER_FILE.read_text(encoding="utf-8").strip() if TRIGGER_FILE.exists() else "-"
    lines = ["# QuantFoot sistem durumu", "",
             f"- Son kontrol: {dt.datetime.now().isoformat(timespec='minutes')} ({note})",
             f"- Global veri yaşı: {'bilinmiyor' if age is None else f'{age:.1f} saat'}"
             + ("" if age is None or age < STALE_HOURS else " ⚠ ESKİ"),
             f"- Son yedek tetikleme: {last_trigger}",
             f"- Günlük kayıt: reports/daily/logs/{dt.date.today().isoformat()}.log", ""]
    STATUS_FILE.write_text("\n".join(lines), encoding="utf-8")
    if age is not None and age >= ALERT_HOURS:
        msg = f"QuantFoot: global fiyatlar {age:.0f} saattir yenilenmedi. Kupon oynamadan önce kontrol edin."
        subprocess.run(["msg", os.environ.get("USERNAME", "*"), "/TIME:600", msg], capture_output=True, timeout=30)
        log.write(f"[uyarı] {msg}\n")


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
            # settle yesterday's Nesine predictions and refresh the cumulative hit-rate report
            _run(["sonuc", "--date", y], log, ROOT / "scripts" / "nesine_takip.py")
            _run(["rapor"], log, ROOT / "scripts" / "nesine_takip.py")
        elif mode == "kadro":
            _pull(log)
            day = today if dt.datetime.now().hour >= 7 else yesterday
            _run(["--date", day.isoformat()], log, ROOT / "scripts" / "nesine_global.py")
            _write_status(log, "kadro")
        elif mode == "analiz":
            _pull(log)
            _kick_fetch_if_stale(log)
            # betting day runs 07:00-07:00: before 07:00 the current slate is still yesterday's
            day = today if dt.datetime.now().hour >= 7 else yesterday
            _run(["--date", day.isoformat(), "--hafta", "5"], log, ROOT / "scripts" / "nesine_global.py")
            _write_status(log, "saatlik analiz")
        elif mode == "snapshot":
            for day in (yesterday, today):
                if (ROOT / "reports" / "daily" / day.isoformat() / "predictions.json").exists():
                    _run(["snapshot", "--date", day.isoformat()], log)
        else:
            raise SystemExit("Kullanım: scheduled.py morning|snapshot|kadro|analiz")


if __name__ == "__main__":
    main()
