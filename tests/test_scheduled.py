"""Backup trigger for the overseas fetch: fires only on stale data, at most once per RETRIGGER_HOURS."""

import datetime as dt
import os
import importlib.util
import io
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("scheduled", SCRIPTS / "scheduled.py")
sched = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sched)


def _setup(tmp_path, monkeypatch, age_hours, last_trigger_hours=None):
    ref = tmp_path / "references.json"
    gen = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=age_hours)
    ref.write_text(json.dumps({"generated_utc": gen.isoformat()}), encoding="utf-8")
    trig = tmp_path / "data" / "trigger.txt"
    trig.parent.mkdir(parents=True)
    if last_trigger_hours is not None:
        t = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=last_trigger_hours)
        trig.write_text(t.isoformat(), encoding="utf-8")
    calls = []

    class _R:
        returncode, stderr, stdout = 0, "", ""

    monkeypatch.setattr(sched, "ROOT", tmp_path)
    monkeypatch.setattr(sched, "GLOBAL_FILE", ref)
    monkeypatch.setattr(sched, "TRIGGER_FILE", trig)
    monkeypatch.setattr(sched, "KICK_FILE", tmp_path / "last_dispatch.json")
    monkeypatch.setattr(sched.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R())
    return calls


def test_fresh_data_does_not_trigger(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=1)
    sched._kick_fetch_if_stale(io.StringIO())
    assert calls == []


def test_stale_data_dispatches_with_gh_once(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=6)
    sched._kick_fetch_if_stale(io.StringIO())
    assert [c[1:4] for c in calls] == [["workflow", "run", "global-odds.yml"]]
    calls.clear()
    sched._kick_fetch_if_stale(io.StringIO())  # just dispatched: wait for that run
    assert calls == []


def test_falls_back_to_trigger_push_when_gh_fails(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=8, last_trigger_hours=4)

    class _R:
        def __init__(self, code):
            self.returncode, self.stderr, self.stdout = code, "", ""

    monkeypatch.setattr(sched.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R(1 if cmd[1] == "workflow" else 0))
    sched._kick_fetch_if_stale(io.StringIO())
    assert [c[1] for c in calls] == ["workflow", "add", "commit", "push"]


def test_lineup_refresh_only_near_nesine_kickoffs(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=1)
    now = dt.datetime.now(dt.timezone.utc)
    day = tmp_path / "reports" / "daily" / now.date().isoformat()
    day.mkdir(parents=True)

    def _write(minutes, status="fiyatlandı"):
        k = (now + dt.timedelta(minutes=minutes)).isoformat()
        (day / "nesine_global.json").write_text(json.dumps({"matches": [{"status": status, "kickoff_iso": k}]}), encoding="utf-8")

    _write(180)
    sched._kick_lineup_refresh(io.StringIO())
    assert calls == []  # nothing within 40-100 min
    _write(70, status="global referans bulunamadı — fiyatlanmadı")
    sched._kick_lineup_refresh(io.StringIO())
    assert calls == []  # unpriced match: no exchange price to refresh
    _write(70)
    sched._kick_lineup_refresh(io.StringIO())
    assert calls and calls[0][-2:] == ["-f", "light=2"]
    calls.clear()
    sched._kick_lineup_refresh(io.StringIO())
    assert calls == []  # cooldown


def test_age_counts_from_last_full_fetch(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, age_hours=0.1)
    full = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=4)
    data = json.loads(sched.GLOBAL_FILE.read_text(encoding="utf-8"))
    sched.GLOBAL_FILE.write_text(json.dumps({**data, "full_utc": full.isoformat()}), encoding="utf-8")
    assert 3.9 < sched._data_age_hours() < 4.1  # a light run 6 min ago does not make the whole snapshot fresh


def test_status_file_and_alert(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=9)
    monkeypatch.setattr(sched, "STATUS_FILE", tmp_path / "DURUM.md")
    log = io.StringIO()
    sched._write_status(log, "test")
    text = (tmp_path / "DURUM.md").read_text(encoding="utf-8")
    assert "ESKİ" in text and "[uyarı]" in log.getvalue()
    if os.name == "nt":
        assert calls and calls[0][0] == "msg"
    else:
        assert not any(c and c[0] == "msg" for c in calls)
    calls.clear()
    (tmp_path / "fresh").mkdir()
    _setup(tmp_path / "fresh", monkeypatch, age_hours=1)
    monkeypatch.setattr(sched, "STATUS_FILE", tmp_path / "DURUM2.md")
    sched._write_status(io.StringIO(), "test")
    assert "ESKİ" not in (tmp_path / "DURUM2.md").read_text(encoding="utf-8")


def test_publish_commits_report_folders_and_pushes(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=1)
    sched._publish(io.StringIO(), "data(takip): test")
    assert [c[1] for c in calls if c[1] != "diff"] == ["add", "commit", "pull", "push"]  # diff: _recover check
    git_calls = [c for c in calls if c[1] != "diff"]
    assert "reports/ledger" in git_calls[0] and "reports/takip" in git_calls[1]


def test_publish_stops_when_nothing_to_commit(tmp_path, monkeypatch):
    calls = []

    class _R:
        def __init__(self, code):
            self.returncode, self.stdout, self.stderr = code, "", ""

    monkeypatch.setattr(sched.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R(1 if cmd[1] == "commit" else 0))
    sched._publish(io.StringIO(), "x")
    assert [c[1] for c in calls if c[1] != "diff"] == ["add", "commit"]
