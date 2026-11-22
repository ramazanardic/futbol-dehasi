"""Run the Windows coupon watcher without console or notification windows."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    python = Path(sys.executable).with_name("python.exe")
    log = root / "reports" / "daily" / "logs" / "kupon_izle.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, QUANTFOOT_AI="chatgbttahmin", PYTHONIOENCODING="utf-8")
    tasks = (
        ("scripts/kupon_kontrol.py", "kontrol", "--sessiz"),
        ("scripts/api_gecmis.py", "--arsiv"),
    )
    exit_code = 0
    with log.open("a", encoding="utf-8") as output:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] KuponIzle silent", file=output, flush=True)
        for args in tasks:
            result = subprocess.run(
                [python, *args], cwd=root, env=env, stdout=output,
                stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            exit_code = exit_code or result.returncode
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] KuponIzle exit={exit_code}", file=output, flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
