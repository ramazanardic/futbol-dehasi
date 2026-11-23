"""Regression tests for independent cross-AI historical auditing."""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ai_history_audit import (
    add_reference, audit_alternative_coupons, audit_coupons, audit_market_prices, audit_placed_ledger, audit_prediction_file,
    canonical_selection, index_reference, normal, number, resolve_reference,
    run, score, summary,
)


def _csv(path, header, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(data)


def _refs():
    refs = {}
    add_reference(refs, "2026-11-21", 42, "Ev - Dep", [1, 0], [2, 1], "trusted")
    add_reference(refs, "2026-11-21", 43, "Başka Ev - Başka Dep", [0, 0], [0, 1], "trusted")
    return refs


def test_legacy_selection_names_are_strict():
    assert canonical_selection({"ana_tahmin": "ÇŞ X-2"}) == "ÇŞ X2"
    assert canonical_selection({"ana_tahmin": "2,5 Alt"}) == "2.5 Alt"
    assert canonical_selection({"ana_secim": "1", "ana_secim_pazar": "Maç Sonucu"}) == "MS 1"
    assert canonical_selection({"ana_secim": "Var", "ana_secim_pazar": "Karşılıklı Gol"}) == "KG Var"
    assert canonical_selection({"ana_tahmin": ""}) is None
    assert normal("Leça - União") == normal("Leça - União")
    assert score("2-1 (İY 1-0)") == [2, 1]
    assert number("1,48") == 1.48
    assert number("nan") is None


def test_independent_grading_detects_both_winning_and_losing_claim_errors(tmp_path):
    refs = _refs()
    path = tmp_path / "tahminler/geminitahmin/2026-11-21/mac_tahminleri.csv"
    _csv(path, ["kod", "mac", "ana_tahmin", "oran", "kalibre_olasilik_pct",
                "gerceklesen_skor", "durum"],
         [
             {"kod": "MBS1-42", "mac": "Ev - Dep", "ana_tahmin": "MS 1",
              "oran": "1.48", "kalibre_olasilik_pct": "80.0",
              "gerceklesen_skor": "1-1", "durum": "YATTI"},
             {"kod": "MBS1-43", "mac": "Başka Ev - Başka Dep", "ana_tahmin": "MS 1",
              "oran": "1.36", "kalibre_olasilik_pct": "70.0",
              "gerceklesen_skor": "3-0", "durum": "TUTTU"},
             {"kod": "MBS1-44", "mac": "Bilinmeyen - Bilinmeyen", "ana_tahmin": "MS 1",
              "oran": "1.35", "kalibre_olasilik_pct": "80.0",
              "gerceklesen_skor": "2-0", "durum": "TUTTU"},
         ])
    report = audit_prediction_file(tmp_path, refs, index_reference(refs),
                                   "geminitahmin", "2026-11-21", path)
    assert report["metrics"]["rows"] == 3
    assert report["metrics"]["settled"] == 2
    assert report["metrics"]["wins"] == 1
    assert report["quality"]["join_unique_name"] == 2
    assert report["quality"]["join_no_reference"] == 1
    assert len(report["scores_mismatched"]) == 2
    assert len(report["statuses_mismatched"]) == 2
    assert report["metrics"]["negative_ev_winners"] == 0  # 0.80 * 1.48 > 1
    assert report["metrics"]["positive_ev_losers"] == 0  # 0.70 * 1.36 < 1


def test_exact_code_beats_name_and_ambiguous_name_is_not_guessed():
    refs = _refs()
    refs[("2026-11-21", "99")] = {**refs[("2026-11-21", "42")]}
    names = index_reference(refs)
    ref, how = resolve_reference(refs, names, "2026-11-21",
                                 {"nesine_kodu": "42", "mac": "incorrect"})
    assert how == "exact_code"
    assert ref["ft"] == [2, 1]
    assert resolve_reference(refs, names, "2026-11-21",
                             {"nesine_kodu": "MBS1-42", "mac": "Ev - Dep"})[1] == "ambiguous_name"


def test_winning_negative_ev_and_losing_positive_ev_are_both_counted():
    sample = [
        {"won": True, "p": 0.60, "odds": 1.35, "ev": -0.19, "reference_status": "exact_code"},
        {"won": False, "p": 0.80, "odds": 1.40, "ev": 0.12, "reference_status": "exact_code"},
        {"won": None, "p": 0.90, "odds": 1.20, "ev": 0.08, "reference_status": "no_reference"},
    ]
    s = summary(sample)
    assert (s["settled"], s["wins"], s["negative_ev_winners"], s["positive_ev_losers"]) == (2, 1, 1, 1)
    assert s["flat_units"] == -0.65
    assert s["flat_roi"] == -0.325
    assert s["no_reference"] == 1


def test_coupons_are_unverified_if_one_result_missing(tmp_path):
    refs = _refs()
    path = tmp_path / "tahminler/chatgbttahmin/2026-11-21/kuponlar.csv"
    _csv(path, ["kupon", "kupon_no", "nesine_kodu", "mac", "secim_adi",
                "nesine_oran", "olasilik"],
         [{"kupon": "C1", "kupon_no": "1", "nesine_kodu": "42", "mac": "Ev - Dep",
           "secim_adi": "KG Var", "nesine_oran": "1.2", "olasilik": "0.75"},
          {"kupon": "C1", "kupon_no": "1", "nesine_kodu": "99", "mac": "Unknown",
           "secim_adi": "MS 1", "nesine_oran": "1.3", "olasilik": "0.70"},
          {"kupon": "C2", "kupon_no": "1", "nesine_kodu": "42", "mac": "Ev - Dep",
           "secim_adi": "KG Var", "nesine_oran": "1.2", "olasilik": "0.75"}])
    result = audit_coupons(tmp_path, refs, index_reference(refs), "chatgbttahmin",
                           "2026-11-21", path)
    assert result["summary"]["coupons"] == 2
    assert result["summary"]["verified"] == 1
    assert result["summary"]["won"] == 1
    assert result["summary"]["reused_matches"] == 1
    assert result["summary"]["max_coupons_using_same_match"] == 2


def test_placed_ticket_payout_is_counted_once_and_missing_legs_excluded(tmp_path):
    path = tmp_path / "reports/ledger/placed_bets_2026_11_19.csv"
    _csv(path, ["coupon_id", "stake_tl", "payout_tl", "n_legs", "selection"],
         [{"coupon_id": "A", "stake_tl": "100", "payout_tl": "320", "n_legs": "2", "selection": "MS 1"},
          {"coupon_id": "A", "stake_tl": "100", "payout_tl": "320", "n_legs": "2", "selection": "MS 2"},
          {"coupon_id": "B", "stake_tl": "100", "payout_tl": "0", "n_legs": "3", "selection": "MS 1"}])
    ledger = audit_placed_ledger(tmp_path)[path.name]
    assert ledger["ticket_ids"] == 2
    assert ledger["fully_specified_with_payout"] == 1
    assert ledger["known_stakes_tl"] == 100
    assert ledger["known_payouts_tl"] == 320
    assert ledger["known_net_tl"] == 220
    assert len(ledger["excluded"]) == 1


def test_full_scan_never_mutates_prediction_files(tmp_path):
    source = tmp_path / "tahminler/chatgbttahmin/2026-11-21/mac_tahminleri.csv"
    _csv(source, ["nesine_kodu", "mac", "ana_secim", "olasilik", "nesine_oran"],
         [{"nesine_kodu": "42", "mac": "Ev - Dep", "ana_secim": "MS 1",
           "olasilik": "0.7", "nesine_oran": "1.3"}])
    archive = tmp_path / "degerlendirme/2026-11-21.json"
    archive.parent.mkdir(parents=True)
    archive.write_text(json.dumps({"date": "2026-11-21", "matches": {
        "42": {"match": "Ev - Dep", "ht": [1, 0], "ft": [2, 1]}}}), encoding="utf-8")
    before = source.read_bytes()
    report = run(tmp_path)
    assert source.read_bytes() == before
    assert report["ais"]["chatgbttahmin"]["overall"]["wins"] == 1
    assert report["ais"]["claudetahmin"]["overall"]["rows"] == 0


def test_every_offered_market_is_scored_not_just_main_csv_selection(tmp_path):
    refs = _refs()
    path = tmp_path / "tahminler/antigravitytahmin/2026-11-21/nesine_global.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": "2026-11-21", "matches": [
        {"code": 42, "home": "Ev", "away": "Dep",
         "selections": [
             {"name": "KG Var", "fair_prob": 0.65, "odds": 1.35, "direct": True},
             {"name": "MS 2", "fair_prob": 0.4, "odds": 5.0, "direct": False},
             {"name": "not-a-real-market", "fair_prob": 0.55, "odds": 1.8},
         ]},
    ]}), encoding="utf-8")
    result = audit_market_prices(tmp_path, refs, index_reference(refs),
                                 "2026-11-21", path)
    assert result["coverage"]["selections_total"] == 3
    assert result["coverage"]["settled_selections"] == 2
    assert result["families"]["DIRECT:direct"]["hits"] == 1
    assert result["families"]["DIRECT:direct"]["negative_ev_winners"] == 1
    assert result["families"]["DIRECT:derived"]["positive_ev_losers"] == 1


def test_alternative_json_coupons_not_confused_with_candidate_list(tmp_path):
    refs = _refs()
    area = tmp_path / "tahminler/grokbottahmin/2026-11-21"
    area.mkdir(parents=True)
    (area / "kupon5000_havuz.json").write_text(json.dumps([
        {"code": 42, "name": "KG Var", "odds": 1.4},
    ]), encoding="utf-8")
    (area / "banko_kupon.json").write_text(json.dumps({
        "note": "Hazırlık, oynanmadı",
        "coupons": {
            "test_1": {"legs": [{"code": 42, "match": "Ev - Dep",
                                  "name": "KG Var", "odds": 1.5},
                                 {"code": 43, "match": "Başka Ev - Başka Dep",
                                  "name": "MS 1", "odds": 1.5}]},
            "empty": {"legs": []},
        },
    }), encoding="utf-8")
    plans = audit_alternative_coupons(tmp_path, refs, index_reference(refs),
                                     "2026-11-21", area)
    assert len(plans) == 1
    assert plans[0]["file"].endswith("banko_kupon.json")
    assert plans[0]["count"] == 1
    assert plans[0]["scored"] == 1
    assert plans[0]["won"] == 0
    assert plans[0]["proposals"][0]["settled_legs"] == 2
    assert plans[0]["proposals"][0]["status"] == "lost"


def test_open_coupon_with_zero_interim_payout_is_not_reported_as_financial_loss(tmp_path):
    path = tmp_path / "reports/ledger/placed_bets_2026_11_19.csv"
    _csv(path, ["coupon_id", "stake_tl", "payout_tl", "n_legs", "selection", "coupon_screen"],
         [{"coupon_id": "PENDING", "stake_tl": "50", "payout_tl": "0", "n_legs": "1",
           "selection": "MS 1", "coupon_screen": "bekliyor"},
          {"coupon_id": "LOST", "stake_tl": "20", "payout_tl": "0", "n_legs": "1",
           "selection": "MS 1", "coupon_screen": "yattı"}])
    x = audit_placed_ledger(tmp_path)[path.name]
    assert x["ticket_ids"] == 2
    assert x["fully_specified_with_payout"] == 1
    assert x["known_stakes_tl"] == 20
    assert x["known_net_tl"] == -20
    assert x["excluded"][0]["reason"] == "pending_settlement"


def test_all_1x2_predictions_scored_even_with_no_recommended_main_pick(tmp_path):
    refs = _refs()
    path = tmp_path / "tahminler/grokbottahmin/2026-11-21/mac_tahminleri.csv"
    _csv(path, ["nesine_kodu", "mac", "olasilik_1", "olasilik_X", "olasilik_2",
                "ana_secim", "tarih"],
         [{"nesine_kodu": "42", "mac": "Ev - Dep",
           "olasilik_1": "0.7", "olasilik_X": "0.2", "olasilik_2": "0.1",
           "ana_secim": "", "tarih": "2026-11-21"}])
    scorecard = audit_prediction_file(tmp_path, refs, index_reference(refs),
                                      "grokbottahmin", "2026-11-21", path)
    assert scorecard["metrics"]["settled"] == 0
    assert scorecard["one_x_two"]["n"] == 1
    assert scorecard["one_x_two"]["brier"] == 0.14
