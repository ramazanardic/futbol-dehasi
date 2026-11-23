"""Exercise the local terminal over HTTP without fetching live prices."""

from http.client import HTTPConnection
import json
from threading import Thread
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from terminal import TerminalServer, command


def test_terminal_runs_the_shared_commands():
    assert command("2026-11-23", "analiz")[-6:] == [
        "--tarih", "2026-11-23", "--yalniz", "bulten", "tahmin", "derin",
    ]
    assert command("2026-11-23", "derin")[-5:] == ["--derin-veri", "--yalniz", "bulten", "tahmin", "derin"]
    assert command("2026-11-23", "kupon")[-2:] == ["--tarih", "2026-11-23"]
    assert command("2026-11-23", "kontrol")[-4:] == ["kontrol", "--date", "2026-11-23", "--sessiz"]


def test_terminal_requires_same_origin_and_serves_own_reports(tmp_path, monkeypatch):
    area = tmp_path / "chatgbttahmin"
    folder = area / "2026-11-23"
    folder.mkdir(parents=True)
    (folder / "nesine_global.json").write_text('{"matches":[]}', encoding="utf-8")
    started = []

    with TerminalServer(0, area) as server:
        monkeypatch.setattr(server, "start", lambda day, mode: started.append((day, mode)) or True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)

        def request(method, path, body=None, headers=None):
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read()

        try:
            status, payload = request("GET", "/api/terminal")
            assert status == 200 and json.loads(payload)["profile"] == "chatgbttahmin"
            assert request("GET", "/api/reports/2026-11-23/bulten") == (200, b'{"matches":[]}')
            assert request("GET", "/api/reports/2026-02-30/bulten")[0] == 400
            assert request("GET", "/.env")[0] == 404
            headers = {"Origin": "https://example.com", "Content-Type": "application/json", "X-QuantFoot-Terminal": "1"}
            body = '{"date":"2026-11-23","mode":"analiz"}'
            assert request("POST", "/api/terminal", body, headers)[0] == 403
            assert not started
            headers["Origin"] = server.origin
            assert request("POST", "/api/terminal", body, headers)[0] == 202
            assert started == [("2026-11-23", "analiz")]
        finally:
            connection.close()
            server.shutdown()
            thread.join()
