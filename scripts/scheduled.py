"""Entry point for the Windows Task Scheduler jobs that keep the daily ledger running.

    python scripts/scheduled.py morning    # 09:00: settle yesterday (results + verify + summary), run today,
                                           #        then price the Nesine bulletin against the global reference
    python scripts/scheduled.py snapshot   # every 30 min: record pre-kickoff odds for today and yesterday
    python scripts/scheduled.py kadro      # at :10 and :30: light exchange refresh for kick-offs in 40-100 min
                                           #        (gh workflow run), re-analyse today (line-ups ~1 h before),
                                           #        then check every coupon leg + record closing prices (CLV)
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
import shutil
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
        data = json.loads(GLOBAL_FILE.read_text(encoding="utf-8"))
        gen = data.get("full_utc") or data.get("generated_utc")  # light runs refresh only kick-offs within 2 h
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(gen)).total_seconds() / 3600
    except (OSError, ValueError, TypeError):
        return None


GH = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
KICK_FILE = LOG_DIR / "last_dispatch.json"  # untracked: when the PC last dispatched a full / light run
LIGHT_WINDOW = (40, 100)  # minutes before a Nesine kick-off in which a light (line-up time) refresh is wanted
LIGHT_COOLDOWN_MIN = 50


def _last_kick(kind: str) -> dt.datetime | None:
    try:
        import json
        return dt.datetime.fromisoformat(json.loads(KICK_FILE.read_text(encoding="utf-8"))[kind])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _dispatch(log, kind: str, light_hours: float | None = None) -> bool:
    """Start the overseas fetch directly (`gh workflow run`); records the time per kind ('full' / 'light')."""
    import json
    cmd = [GH, "workflow", "run", "global-odds.yml"] + (["-f", f"light={light_hours:g}"] if light_hours else [])
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except OSError as exc:
        log.write(f"[gh] {kind}: {exc}\n")
        return False
    log.write(f"[gh] {kind} çalıştırma: {r.returncode} {(r.stdout + r.stderr).strip()[:200]}\n")
    if r.returncode:
        return False
    try:
        data = json.loads(KICK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[kind] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    KICK_FILE.parent.mkdir(parents=True, exist_ok=True)
    KICK_FILE.write_text(json.dumps(data), encoding="utf-8")
    return True


def _upcoming_nesine_kickoffs(now: dt.datetime) -> list[dt.datetime]:
    """Kick-offs of globally priced Nesine matches (today's and yesterday's analysis files)."""
    import json
    out = []
    for d in (now.date() - dt.timedelta(days=1), now.date()):
        try:
            data = json.loads((ROOT / "reports" / "daily" / d.isoformat() / "nesine_global.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for m in data.get("matches", []):
            if m.get("status") == "fiyatlandı" and m.get("kickoff_iso"):
                out.append(dt.datetime.fromisoformat(m["kickoff_iso"]))
    return out


def _kick_lineup_refresh(log) -> None:
    """Line-ups come out ~1 h before kick-off: a light exchange refresh for Nesine matches starting in
    40-100 minutes, at most once per LIGHT_COOLDOWN_MIN (keeps Actions minutes low)."""
    now = dt.datetime.now(dt.timezone.utc)
    lo, hi = (now + dt.timedelta(minutes=m) for m in LIGHT_WINDOW)
    if not any(lo <= k <= hi for k in _upcoming_nesine_kickoffs(now)):
        return
    last = _last_kick("light")
    if last and now - last < dt.timedelta(minutes=LIGHT_COOLDOWN_MIN):
        return
    _dispatch(log, "light", light_hours=2)


def _kick_fetch_if_stale(log) -> None:
    """GitHub's cron does not fire for this repo: when the overseas data is STALE_HOURS old, start a full run
    with `gh`; if gh fails, push the one-line trigger file (the workflow also runs on pushes to that path)."""
    age = _data_age_hours()
    if age is not None and age < STALE_HOURS:
        return
    kicks = [k for k in (_last_kick("full"),) if k]
    if TRIGGER_FILE.exists():
        try:
            kicks.append(dt.datetime.fromisoformat(TRIGGER_FILE.read_text(encoding="utf-8").strip()))
        except ValueError:
            pass
    if kicks and dt.datetime.now(dt.timezone.utc) - max(kicks) < dt.timedelta(hours=RETRIGGER_HOURS):
        return  # already kicked recently; give that run time to finish
    if _dispatch(log, "full"):
        return
    TRIGGER_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds") + "\n", encoding="utf-8")
    rel = str(TRIGGER_FILE.relative_to(ROOT))
    steps = (["git", "add", rel], ["git", "commit", "-q", "-m", f"chore(trigger): global data {age if age is None else round(age, 1)} h old",
                                    "--", rel], ["git", "push", "-q"])
    for cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        log.write(f"[tetik] {' '.join(cmd[:2])}: {r.returncode} {r.stderr.strip()}\n")
        if r.returncode:
            return


PUBLISH_PATHS = ["reports/daily", "reports/takip", "reports/ledger", "reports/weekly", "data/calibration", "docs/data"]


def _publish(log, message: str) -> None:
    """Keep every prediction and result on GitHub as well (user request, 20 Nov): commit the report folders
    (git-ignored files such as logs stay local) and push. Nothing to commit = nothing happens."""
    steps = (["git", "add", "--", *PUBLISH_PATHS],
             ["git", "commit", "-q", "-m", message + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>", "--", *PUBLISH_PATHS],
             ["git", "pull", "--rebase", "--autostash", "-q"], ["git", "push", "-q"])
    for cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        log.write(f"[yayın] {' '.join(cmd[:2])}: {r.returncode} {(r.stdout + r.stderr).strip()[:200]}\n")
        if r.returncode:
            return  # e.g. "nothing to commit": stop quietly


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
             f"- Son gh çalıştırması: tam {_last_kick('full') or '-'} · kadro saati {_last_kick('light') or '-'}",
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
            # Old model: predictions only (CLV research); its "value" coupons are no longer written
            # because they come from the model's own structure, not from global prices.
            _run(["predict", "--date", today.isoformat()], log)
            _run(["report", "--date", today.isoformat()], log)
            # Pull the sharp prices GitHub Actions fetched abroad (data/global_odds/latest), then price
            # the Nesine bulletin against them (Pinnacle -> Smarkets -> ESPN).
            _pull(log)
            _run(["--date", today.isoformat()], log, ROOT / "scripts" / "nesine_global.py")
            # every match of the day analysed from scratch: dossiers (every bet family) and the one-page table
            _run(["--tarih", today.isoformat()], log, ROOT / "scripts" / "mac_dosyasi.py")
            _run(["--tarih", today.isoformat()], log, ROOT / "scripts" / "gunluk_analiz.py")
            # settle yesterday's Nesine predictions, refresh cumulative report, self-learning calibration & dashboard
            _run(["sonuc", "--date", y], log, ROOT / "scripts" / "nesine_takip.py")
            _run(["rapor"], log, ROOT / "scripts" / "nesine_takip.py")
            _run(["kontrol", "--date", y, "--sessiz"], log, ROOT / "scripts" / "kupon_kontrol.py")
            _run(["ozet"], log, ROOT / "scripts" / "kupon_kontrol.py")
            _run([], log, ROOT / "scripts" / "auto_learn.py")
            _run([], log, ROOT / "scripts" / "build_dashboard.py")
            _run(["--date", today.isoformat(), "--mode", "morning"], log, ROOT / "scripts" / "notify_telegram.py")
            _publish(log, f"data(takip): {y} predictions, results, calibration and dashboard")
        elif mode == "kadro":
            _kick_lineup_refresh(log)
            _kick_fetch_if_stale(log)
            _pull(log)
            day = today if dt.datetime.now().hour >= 7 else yesterday
            _run(["--date", day.isoformat()], log, ROOT / "scripts" / "nesine_global.py")
            # coupon legs vs the line-up re-analysis: warn before kick-off, record the closing price (CLV)
            _run(["kontrol", "--date", day.isoformat()], log, ROOT / "scripts" / "kupon_kontrol.py")
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
