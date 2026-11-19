"""Backup trigger for the overseas fetch: fires only on stale data, at most once per RETRIGGER_HOURS."""

import datetime as dt
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
        returncode, stderr = 0, ""

    monkeypatch.setattr(sched, "ROOT", tmp_path)
    monkeypatch.setattr(sched, "GLOBAL_FILE", ref)
    monkeypatch.setattr(sched, "TRIGGER_FILE", trig)
    monkeypatch.setattr(sched.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or _R())
    return calls


def test_fresh_data_does_not_trigger(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=1)
    sched._kick_fetch_if_stale(io.StringIO())
    assert calls == []


def test_stale_data_pushes_trigger_once(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=6)
    sched._kick_fetch_if_stale(io.StringIO())
    assert [c[1] for c in calls] == ["add", "commit", "push"]
    calls.clear()
    sched._kick_fetch_if_stale(io.StringIO())  # just triggered: wait for that run
    assert calls == []


def test_retriggers_after_cooldown(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=8, last_trigger_hours=4)
    sched._kick_fetch_if_stale(io.StringIO())
    assert [c[1] for c in calls] == ["add", "commit", "push"]


def test_status_file_and_alert(tmp_path, monkeypatch):
    calls = _setup(tmp_path, monkeypatch, age_hours=9)
    monkeypatch.setattr(sched, "STATUS_FILE", tmp_path / "DURUM.md")
    log = io.StringIO()
    sched._write_status(log, "test")
    text = (tmp_path / "DURUM.md").read_text(encoding="utf-8")
    assert "ESKİ" in text and calls and calls[0][0] == "msg" and "[uyarı]" in log.getvalue()
    calls.clear()
    (tmp_path / "fresh").mkdir()
    _setup(tmp_path / "fresh", monkeypatch, age_hours=1)
    monkeypatch.setattr(sched, "STATUS_FILE", tmp_path / "DURUM2.md")
    sched._write_status(io.StringIO(), "test")
    assert "ESKİ" not in (tmp_path / "DURUM2.md").read_text(encoding="utf-8")
