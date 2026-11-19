"""End-to-end check of the daily CLV / settlement path on a synthetic day (no network)."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "daily.py"


@pytest.fixture()
def daily(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("daily_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DAILY", tmp_path)
    return mod


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_clv_and_profit(daily, tmp_path):
    day = tmp_path / "2026-12-01"
    probs = {"MS 1": 0.5, "MS 0": 0.27, "MS 2": 0.23, "2.5 Üst": 0.55, "2.5 Alt": 0.45}
    _write(day / "predictions.json", {"matches": [
        {"event_id": "1", "home": "A", "away": "B", "slug": "eng.1", "probs": probs,
         "p_market_1x2": [0.48, 0.28, 0.24], "value": [{"selection": "MS 1", "odds": 2.2, "prob": 0.5, "ev": 0.1}]},
    ]})
    _write(day / "coupons.json", {"value_singles": [{"event_id": "1", "selection": "MS 1", "odds": 2.2, "ev": 0.1}]})
    # Price shortened to 2.00 by kickoff: positive CLV.
    _write(day / "closing_odds.json", {"1": {"odds": {"MS 1": 2.0, "MS 0": 3.6, "MS 2": 4.0}}})
    _write(day / "results.json", {"1": {"completed": True, "ht": [1, 0], "ft90": [2, 1]}})

    out = daily._collect_day("2026-12-01")
    c = out["clv"][0]
    assert c["raw_clv"] == pytest.approx(0.10)
    assert c["fair_clv"] > 0
    assert c["won"] is True and c["profit"] == pytest.approx(1.2)
    assert out["rows"][0]["market_source"] == "kapanış"
    bench, md = daily._benchmark_lines(out["p_market"], out["p_model"], out["y"], out["clv"])
    assert bench["flat_profit"] == pytest.approx(1.2)
    assert any("CLV" in line for line in md)


def test_fair_probs_devig_each_market(daily):
    fair = daily._fair_probs({"MS 1": 2.0, "MS 0": 3.5, "MS 2": 4.0, "2.5 Üst": 1.9, "2.5 Alt": 1.95,
                              "AH Ev -0.50": 1.95, "AH Dep +0.50": 1.9})
    assert sum(fair[k] for k in ("MS 1", "MS 0", "MS 2")) == pytest.approx(1.0)
    assert fair["2.5 Üst"] + fair["2.5 Alt"] == pytest.approx(1.0)
    assert fair["AH Ev -0.50"] + fair["AH Dep +0.50"] == pytest.approx(1.0)
