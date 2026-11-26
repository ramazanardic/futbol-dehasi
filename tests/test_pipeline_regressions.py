"""Regression coverage for prediction, coupon and settlement boundaries."""

import datetime as dt
import json
from pathlib import Path
import sys

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import gun_degerlendirme as evaluation
import gunluk_tahmin as pipeline
import simulasyon
from quantfoot.coupons.coupon_rules import leg_decision
from quantfoot.data import nesine


def test_old_simulation_cannot_restore_rejected_pick(monkeypatch, tmp_path):
    date = "2099-11-22"
    day = tmp_path / date
    day.mkdir()
    monkeypatch.setattr(simulasyon.dr, "AREA", tmp_path)
    leg = {"name": "KG Var", "label": "KG Var", "verdict": "⚠ Pazar teşhisi"}
    path = day / "derin_tahminler.json"
    path.write_text(json.dumps([{"code": 1, "pick": None, "legs": [leg]}]))
    bets = [{"name": "KG Var", "label": "KG Var", "verdict": "üçlü onay", "market": .72, "odds": 1.60, "low": .70}]
    assert simulasyon.update_picks(date, [{"code": 1, "bets": bets}]) == 0
    assert json.loads(path.read_text())[0]["pick"] is None


def test_regulation_score_is_required_for_extra_time():
    payload = {"d": [{"C": 4, "ST": "UZT", "ES": [{"T": 2, "H": 0, "A": 0}, {"T": 1, "H": 2, "A": 1}]}]}
    assert not nesine.parse_results(payload)[4]["completed"]


def test_partial_results_cannot_replace_existing_report(monkeypatch, tmp_path):
    date = "2026-11-22"
    path = tmp_path / f"{date}.json"
    old = '{"matches":{"1":{}}, "ais":{}}'
    path.write_text(old)
    monkeypatch.setattr(evaluation, "OUT", tmp_path)
    monkeypatch.setattr(evaluation, "TAHMIN", tmp_path / "no_predictions")
    monkeypatch.setattr(sys, "argv", ["gun_degerlendirme.py", "--tarih", date])

    def partial(url, **kwargs):
        if kwargs["params"]["date"] == date:
            return type("Response", (), {"json": lambda _: {"d": []}, "raise_for_status": lambda _: None})()
        raise requests.Timeout("network")

    monkeypatch.setattr(nesine.requests, "get", partial)
    with pytest.raises(SystemExit, match="2"):
        evaluation.main()
    assert path.read_text() == old


def test_duplicate_prediction_counted_once(monkeypatch, tmp_path):
    date = "2026-11-22"
    day = tmp_path / "chatgbttahmin" / date
    day.mkdir(parents=True)
    monkeypatch.setattr(evaluation, "TAHMIN", tmp_path)
    (day / "mac_tahminleri.csv").write_text("nesine_kodu,secim_adi\n1,MS 1\n1,MS 1\n1,\n")
    report = evaluation.evaluate(date, {1: {"completed": True, "ht": [0, 0], "ft90": [1, 0]}})
    assert report["ais"]["chatgbttahmin"]["hits"] == 1
    assert report["ais"]["chatgbttahmin"]["main_picks"] == 1


@pytest.mark.parametrize(("odds", "p"), [(float("nan"), .8), (1.25, 1.2), (1.25, float("inf"))])
def test_invalid_coupon_numbers_are_rejected(odds, p):
    assert not leg_decision({"name": "İY 0.5 Üst", "odds": odds, "p": p}).ok


def test_current_run_excludes_old_coupons_and_started_match_fails_live_audit(monkeypatch, tmp_path):
    date = "2000-01-02"
    ai = "chatgbttahmin"
    day = tmp_path / "tahminler" / ai / date
    day.mkdir(parents=True)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    stem = "kupon_2.5x_0900"
    (day / "kuponlar.csv").write_text(f"kupon,kupon_no,nesine_kodu,secim_adi,nesine_oran,olasilik\n{stem},1,1,İY 0.5 Üst,1.25,0.8\n",
                                      encoding="utf-8")
    assert pipeline.run_audit(date, ai, current_files=set(), live=True)["coupons"] == []
    leg = {"code": 1, "key": "test", "name": "İY 0.5 Üst", "kickoff": f"{date} 10:00"}
    (day / f"{stem}.json").write_text(json.dumps({"coupons": [{"legs": [leg]}]}))
    import nesine_kupon
    monkeypatch.setattr(nesine_kupon, "read_bulletin_odds", lambda: ({1: {"test": 1.25}}, {}))
    report = pipeline.run_audit(date, ai, current_files={stem}, live=True)
    assert any("maç başladı" in reason for reason in report["coupons"][0]["ihlaller"])
