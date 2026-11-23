"""The shared leaderboard must expose missing/invalid AI data, not report silent zero success."""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gun_degerlendirme as G  # noqa: E402


def _csv(path, fieldnames, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def test_incompatible_ai_file_is_reported_not_treated_as_zero_accuracy(tmp_path, monkeypatch):
    root = tmp_path / "tahminler"
    path = root / "geminitahmin" / "2026-11-21/mac_tahminleri.csv"
    _csv(path, ["kod", "mac", "ana_tahmin", "kalibre_olasilik_pct"],
         [{"kod": "MBS1-42", "mac": "Ev - Dep", "ana_tahmin": "MS 1",
           "kalibre_olasilik_pct": 75}])
    monkeypatch.setattr(G, "TAHMIN", root)
    monkeypatch.setattr(G, "label_names", lambda _p: {})
    report = G.evaluate("2026-11-21", results={42: {
        "completed": True, "ht": [1, 0], "ft90": [2, 0]}})
    stats = report["ais"]["geminitahmin"]
    assert stats["main_picks"] == 0
    assert stats["avg_pred"] is None
    assert stats["data_quality"]["schema"] == "incompatible"
    assert stats["data_quality"]["prediction_rows"] == 1
    assert stats["data_quality"]["missing_nesine_code"] == 1
    assert "incompatible" in G.to_markdown(report)


def test_invalid_1x2_probabilities_are_not_scored(tmp_path, monkeypatch):
    root = tmp_path / "tahminler"
    path = root / "chatgbttahmin" / "2026-11-21/mac_tahminleri.csv"
    _csv(path, ["nesine_kodu", "mac", "lig", "saat", "ana_secim_pazar",
                "ana_secim", "secim_adi", "olasilik", "nesine_oran",
                "olasilik_1", "olasilik_X", "olasilik_2"],
         [{"nesine_kodu": 42, "mac": "Ev - Dep", "lig": "test", "saat": "14:00",
           "ana_secim_pazar": "Karşılıklı Gol", "ana_secim": "Var",
           "secim_adi": "KG Var", "olasilik": "0.75", "nesine_oran": "1.50",
           "olasilik_1": "1.5", "olasilik_X": "-0.1", "olasilik_2": "-0.4"}])
    monkeypatch.setattr(G, "TAHMIN", root)
    monkeypatch.setattr(G, "label_names", lambda _p: {})
    report = G.evaluate("2026-11-21", results={42: {
        "completed": True, "ht": [1, 0], "ft90": [2, 1]}})
    stats = report["ais"]["chatgbttahmin"]
    assert stats["main_picks"] == 1
    assert stats["hits"] == 1
    assert stats["brier_1x2"] is None
    assert stats["n_1x2"] == 0
    assert stats["data_quality"]["invalid_1x2_distribution"] == 1
