"""API-Football günlük kota bütçesi ve gün önbelleği (ücretsiz plan 100 istek/gün)."""

from __future__ import annotations

import sys
from pathlib import Path

from quantfoot.data import api_football as AF
from quantfoot.data.api_budget import ApiBudget

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_budget_caps_and_persists(tmp_path):
    b = ApiBudget(tmp_path, limit=3, today="2026-11-22")
    assert b.spend(1, "a") and b.spend(2, "b")
    assert not b.spend(1, "c")
    assert ApiBudget(tmp_path, limit=3, today="2026-11-22").used() == 3
    assert ApiBudget(tmp_path, limit=3, today="2026-11-23").used() == 0  # new day, new counter


class _Resp:
    def __init__(self, body):
        self.status_code, self._body = 200, body

    def json(self):
        return self._body


def test_fetch_respects_budget_and_caches(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/fixtures"):
            return _Resp({"response": [{"fixture": {"id": 1, "date": "2026-11-22T15:00:00+00:00"},
                                        "league": {"name": "L"}, "teams": {"home": {"name": "A"}, "away": {"name": "B"}}}]})
        return _Resp({"response": [], "paging": {"current": 1, "total": 5}})

    monkeypatch.setattr(AF.requests, "get", fake_get)
    b = ApiBudget(tmp_path, limit=3, today="2026-11-22")
    AF.fetch_api_football_references(["2026-11-22", "2026-11-23"], api_key="k", budget=b, cache_dir=tmp_path)
    assert len(calls) == 3 and b.used() == 3  # 1 fixtures + 2 odds pages, then the cap stops everything


def test_cached_day_is_not_refetched(tmp_path, monkeypatch):
    import json
    (tmp_path / "odds_refs_2026-11-22.json").write_text(json.dumps([{"source": "Pinnacle (API-Football)",
        "home": "A", "away": "B", "kickoff": "x", "kickoff_utc": "2026-11-22T15:00:00+00:00", "x12": [2, 3, 4]}]))
    monkeypatch.setattr(AF.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    b = ApiBudget(tmp_path, limit=10, today="2026-11-22")
    refs = AF.fetch_api_football_references(["2026-11-22"], api_key="k", budget=b, cache_dir=tmp_path)
    assert len(refs) == 1 and refs[0]["kickoff"].hour == 15 and b.used() == 0


def test_gunluk_tahmin_loads_only_whitelisted_env_keys(tmp_path):
    import gunluk_tahmin as G
    f = tmp_path / ".env"
    f.write_text("API_FOOTBALL_KEY=abc\nOTHER_SECRET=zzz\n")
    env = {}
    assert G.load_env_keys(f, env) == ["API_FOOTBALL_KEY"]
    assert env == {"API_FOOTBALL_KEY": "abc"}
    env2 = {"API_FOOTBALL_KEY": "own"}
    G.load_env_keys(f, env2)
    assert env2["API_FOOTBALL_KEY"] == "own"


def test_empty_day_is_cached_so_quota_is_not_respent(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(AF.requests, "get", lambda url, **k: calls.append(url) or _Resp({"response": []}))
    b = ApiBudget(tmp_path, limit=10, today="2026-11-22")
    for _ in range(3):
        AF.fetch_api_football_references(["2026-11-24"], api_key="k", budget=b, cache_dir=tmp_path)
    assert len(calls) == 1 and b.used() == 1


def test_concurrent_reservations_share_one_limit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    start = Barrier(8)
    def reserve(_):
        budget = ApiBudget(tmp_path, limit=1)
        start.wait()
        return budget.spend()

    with ThreadPoolExecutor(8) as workers:
        assert sum(workers.map(reserve, range(8))) == 1
    assert ApiBudget(tmp_path).used() == 1


def test_corrupt_budget_fails_closed(tmp_path):
    b = ApiBudget(tmp_path, limit=3, today="2026-11-22")
    for raw in ("{broken", '{"used": -1}', '{"used": "bad"}', '{}'):
        b.path.write_text(raw, encoding="utf-8")
        assert b.remaining() == 0
        assert not b.spend()
        assert b.path.read_text(encoding="utf-8") == raw
