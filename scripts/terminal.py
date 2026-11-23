"""Serve the QuantFoot Terminal and run the shared analysis on explicit request."""

from __future__ import annotations

import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Lock, Thread
from urllib.parse import urlsplit

from quantfoot.data.nesine import betting_day
from quantfoot.paths import QuantfootAIError, ai_area

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "terminal"
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css"), "/match-research.js": ("match-research.js", "text/javascript")}
REPORTS = {"bulten": ("nesine_global.json", "application/json"),
           "tahmin": ("mac_tahminleri.csv", "text/csv"),
           "kupon": ("kuponlar.csv", "text/csv"),
           "aile": ("bahis_aileleri.md", "text/plain"),
           "derin": ("derin_tahminler.json", "application/json")}
MODES = {"analiz": ["--yalniz", "bulten", "tahmin", "derin"],
         "derin": ["--derin-veri", "--yalniz", "bulten", "tahmin", "derin"],
         "kupon": [], "kontrol": []}
STAGES = {"bulten": "Bülten", "tahmin": "Tahminler", "derin": "Derin araştırma",
          "kupon": "Kupon", "denetim": "Kupon denetimi"}


def valid_date(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Geçerli bir tarih seç.")
    return date.fromisoformat(value).isoformat()


def command(day: str, mode: str) -> list[str]:
    if mode == "kontrol":
        return [sys.executable, "-u", str(ROOT / "scripts/kupon_kontrol.py"), "kontrol", "--date", day, "--sessiz"]
    return [sys.executable, "-u", str(ROOT / "scripts/gunluk_tahmin.py"), "--tarih", day, *MODES[mode]]


class TerminalServer(ThreadingHTTPServer):
    def __init__(self, port: int, area: Path):
        super().__init__(("127.0.0.1", port), TerminalHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.area = area
        self.lock = Lock()
        self.run: dict = {"state": "ready"}

    def start(self, day: str, mode: str) -> bool:
        with self.lock:
            if self.run["state"] == "running":
                return False
            self.run = {"state": "running", "date": day, "mode": mode, "stage": "Başlatılıyor"}
            Thread(target=self.execute, args=(day, mode), daemon=True).start()
        return True

    def execute(self, day: str, mode: str) -> None:
        try:
            with subprocess.Popen(command(day, mode), cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, text=True, encoding="utf-8",
                                  errors="replace") as process:
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="", file=sys.stderr, flush=True)
                    step = line.split("]", 1)[0].removeprefix("[") if line.startswith("[") else ""
                    progress = re.match(r"^([0-9]+)/([0-9]+) maç araştırıldı", line)
                    if step in STAGES or progress:
                        with self.lock:
                            if step in STAGES:
                                self.run["stage"] = STAGES[step]
                            if progress:
                                self.run["progress"] = [int(value) for value in progress.groups()]
                code = process.wait()
        except OSError as exc:
            print(f"QuantFoot başlatılamadı: {exc}", file=sys.stderr)
            code = 1
        with self.lock:
            self.run.update(state="finished" if code == 0 else "error", code=code)


class TerminalHandler(BaseHTTPRequestHandler):
    server: TerminalServer

    def reply(self, status: int, body: bytes, mime: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{mime}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def json(self, status: int, data: dict) -> None:
        self.reply(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

    def host_ok(self) -> bool:
        if self.headers.get("Host") == self.server.origin.removeprefix("http://"):
            return True
        self.json(403, {"error": "Yerel QuantFoot adresini kullan."})
        return False

    def do_GET(self) -> None:
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        if path == "/api/terminal":
            with self.server.lock:
                run = self.server.run.copy()
            self.json(200, {"day": betting_day(), "profile": self.server.area.name, "run": run})
            return
        if path in ASSETS:
            filename, mime = ASSETS[path]
            local = STATIC / filename
        elif (m := re.fullmatch(r"/api/reports/(\d{4}-\d{2}-\d{2})/([a-z]+)", path)) and m[2] in REPORTS:
            try:
                day = valid_date(m[1])
            except ValueError:
                self.json(400, {"error": "Geçerli bir tarih seç."})
                return
            filename, mime = REPORTS[m[2]]
            area = self.server.area.resolve()
            local = (area / day / filename).resolve()
            if not local.is_relative_to(area):
                self.json(403, {"error": "Rapor kendi tahmin klasöründe olmalı."})
                return
        else:
            self.json(404, {"error": "Dosya bulunamadı."})
            return
        try:
            content = local.read_bytes()
        except OSError:
            self.json(404, {"error": "Bu tarih için kayıtlı rapor bulunamadı."})
            return
        self.reply(200, content, mime)

    def do_POST(self) -> None:
        if not self.host_ok():
            return
        if self.path != "/api/terminal":
            self.json(404, {"error": "İşlem bulunamadı."})
            return
        if (self.headers.get("Origin") != self.server.origin
                or self.headers.get("X-QuantFoot-Terminal") != "1"
                or self.headers.get_content_type() != "application/json"):
            self.json(403, {"error": "Analizi yerel terminalden başlat."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 1024:
                raise ValueError("Geçersiz istek boyutu.")
            data = json.loads(self.rfile.read(size))
            day = valid_date(data["date"])
            mode = data["mode"]
            if not isinstance(mode, str) or mode not in MODES:
                raise ValueError("Geçersiz işlem.")
        except (ValueError, TypeError, KeyError):
            self.json(400, {"error": "Tarih veya işlem geçersiz."})
            return
        if not self.server.start(day, mode):
            self.json(409, {"error": "Bir QuantFoot çalışması zaten devam ediyor."})
            return
        self.json(202, {"state": "running"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        area = ai_area()
    except QuantfootAIError as exc:
        parser.error(str(exc))
    with TerminalServer(args.port, area) as server:
        print(f"QuantFoot Terminal · {server.origin} · {area.name}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nTerminal kapatıldı.")


if __name__ == "__main__":
    main()
