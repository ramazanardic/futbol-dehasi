"""derin_tahmin.update_table: değer tercihi yoksa en olası tercih korunur (yalnız geçmiş çürüttüyse silinir)."""

from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _table(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_no_value_keeps_probable_pick_but_drops_contradicted(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    dt_mod = importlib.import_module("derin_tahmin")
    monkeypatch.setattr(dt_mod, "AREA", tmp_path)
    day = tmp_path / "2026-11-22"
    day.mkdir()
    base = {"ana_secim_pazar": "1. Yarı 0,5 Gol Alt/Üst", "ana_secim": "0,5 Üst", "nesine_oran": "1.25",
            "olasilik": "0.7300", "secim_adi": "İY 0.5 Üst", "not": ""}
    _table(day / "mac_tahminleri.csv", [{"nesine_kodu": "1", **base}, {"nesine_kodu": "2", **base},
                                        {"nesine_kodu": "3", **base}])
    rows = [
        {"code": 1, "pick": None, "dropped": []},
        {"code": 2, "pick": None, "dropped": [{"name": "İY 0.5 Üst", "verdict": "⚠"}]},
        {"code": 3, "pick": {"market": "2,5 Gol Alt/Üst", "sel": "2,5 Alt", "odds": 1.6, "name": "2.5 Alt",
                             "p": 0.66, "verdict": "✓", "mean": 0.7}, "dropped": []},
    ]
    assert dt_mod.update_table("2026-11-22", rows) == 3
    out = {r["nesine_kodu"]: r for r in csv.DictReader((day / "mac_tahminleri.csv").open(encoding="utf-8-sig"))}
    assert out["1"]["secim_adi"] == "İY 0.5 Üst" and out["1"]["not"] == dt_mod.NO_VALUE_NOTE
    assert out["2"]["secim_adi"] == "" and out["2"]["olasilik"] == ""
    assert out["3"]["secim_adi"] == "2.5 Alt" and out["3"]["nesine_oran"] == "1.6"
