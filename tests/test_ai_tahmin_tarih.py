"""mac_tahminleri.csv 'tarih' sütunu Nesine başlama gününden gelir (22 Kas denetimi: gece maçları bir önceki güne yazılıyordu)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture()
def at(monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    import ai_tahmin
    return ai_tahmin


TSI = dt.timezone(dt.timedelta(hours=3))


def _m(code, kickoff):
    return {"code": code, "kickoff": kickoff, "kickoff_iso": kickoff.replace(" ", "T") + ":00+03:00",
            "league": "L", "home": f"H{code}", "away": f"A{code}", "status": "fiyatsız", "price_tier": "fiyatsiz"}


def test_kickoff_date_helper(at):
    assert at.kickoff_date("2026-11-23 00:30", "2026-11-22") == "2026-11-23"
    assert at.kickoff_date("2026-11-22 21:00", "2026-11-22") == "2026-11-22"
    assert at.kickoff_date("", "2026-11-22") == "2026-11-22"
    assert at.kickoff_date(None, "2026-11-22") == "2026-11-22"


def test_night_matches_get_next_calendar_day(at):
    now = dt.datetime(2026, 11, 22, 12, 0, tzinfo=TSI)
    rows = at.match_rows("2026-11-22", [_m(1, "2026-11-22 21:00"), _m(2, "2026-11-23 00:00"), _m(3, "2026-11-23 04:10")],
                         now=now)
    by = {str(r["nesine_kodu"]): r for r in rows}
    assert by["1"]["tarih"] == "2026-11-22"
    assert by["2"]["tarih"] == "2026-11-23" and by["2"]["saat"] == "00:00"
    assert by["3"]["tarih"] == "2026-11-23" and by["3"]["saat"] == "04:10"
    # sıralama gerçek zaman sırası: gece maçları en sonda
    assert [str(r["nesine_kodu"]) for r in rows] == ["1", "2", "3"]


def test_frozen_row_keeps_content_but_gets_correct_date(at):
    now = dt.datetime(2026, 11, 23, 5, 0, tzinfo=TSI)
    frozen = {"2": {"tarih": "2026-11-22", "saat": "00:00", "nesine_kodu": "2", "ana_secim": "1,5 Alt", "olasilik": "0.7"}}
    rows = at.match_rows("2026-11-22", [_m(2, "2026-11-23 00:00")], frozen=frozen, now=now)
    assert rows[0]["tarih"] == "2026-11-23"
    assert rows[0]["ana_secim"] == "1,5 Alt" and rows[0]["olasilik"] == "0.7"
