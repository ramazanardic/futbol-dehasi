"""Odds double-read, cross-coupon shared-match limit, pre-kick-off leg check and closing-price (CLV) record."""

import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kupon = _load("nesine_kupon")
kontrol = _load("kupon_kontrol")
TSI = dt.timezone(dt.timedelta(hours=3))


def test_double_read_keeps_lowest_odds_and_reports_flicker(monkeypatch):
    reads = iter([{"odds": 1.71}, {"odds": 1.65}])
    monkeypatch.setattr(kupon, "fetch_bulletin", lambda: next(reads))
    monkeypatch.setattr(kupon, "selection_key", lambda s: s.key)

    def parse(payload):
        sels = [SimpleNamespace(key="13|3.5 Alt|0", odds=payload["odds"]), SimpleNamespace(key="1|MS 1|0", odds=1.30)]
        return [SimpleNamespace(code=7, selections=sels)]

    monkeypatch.setattr(kupon, "parse_bulletin", parse)
    odds, flicker = kupon.read_bulletin_odds(reads=2, gap_s=0)
    assert odds[7]["13|3.5 Alt|0"] == 1.65
    assert flicker == {(7, "13|3.5 Alt|0"): (1.65, 1.71)}
    assert (7, "1|MS 1|0") not in flicker


def test_prior_codes_use_latest_main_coupon_of_other_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "DAILY", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()

    def write(name, coupons):
        (day / name).write_text(json.dumps({"coupons": [{"legs": [{"code": c} for c in cs]} for cs in coupons]}))

    write("kupon_5x_0800.json", [[1, 2]])
    write("kupon_5x_0851.json", [[3, 4], [5]])   # latest 5x: only its main coupon counts
    write("kupon_10x_0858.json", [[9]])          # same target as the one being built: ignored
    assert kupon.prior_coupon_codes("2026-11-20", 10) == {3, 4}


def _day(tmp_path, kick_iso, p_now, odds_now=1.50, flags=None):
    day = tmp_path / "2026-11-20"
    day.mkdir(exist_ok=True)
    leg = {"code": 1, "key": "13|3.5 Alt|0", "kickoff": kick_iso[:16].replace("T", " "), "match": "A - B",
           "market": "3,5 Gol Alt/Üst", "selection": "3,5 Alt", "odds": 1.50, "p": 0.62}
    (day / "kupon_5x_0851.json").write_text(json.dumps({"coupons": [{"legs": [leg]}]}), encoding="utf-8")
    match = {"code": 1, "kickoff_iso": kick_iso, "status": "fiyatlandı", "reference": "Matchbook + Smarkets",
             "research": {"flags": flags or []},
             "selections": [{"key": "13|3.5 Alt|0", "fair_prob": p_now, "odds": odds_now}]}
    (day / "nesine_global.json").write_text(json.dumps({"matches": [match]}), encoding="utf-8")


def test_check_warns_on_probability_drop_and_records_closing_price(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.56)
    now = dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI)
    rows, clv = kontrol.check("2026-11-20", now)
    assert rows[0]["warn"] == ["olasılık 6 puan düştü"]
    assert rows[0]["new_warn"] == rows[0]["warn"]
    rec = clv["1|13|3.5 Alt|0"]
    assert rec["p_pick"] == 0.62 and rec["p_close"] == 0.56
    # a second run does not re-alert the same warning
    rows, _ = kontrol.check("2026-11-20", now)
    assert rows[0]["warn"] and not rows[0]["new_warn"]


def test_check_floor_odds_and_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.50, odds_now=1.18, flags=["TM: golcü eksik"])
    rows, _ = kontrol.check("2026-11-20", dt.datetime(2026, 11, 20, 21, 0, tzinfo=TSI))
    w = rows[0]["warn"]
    assert any("%55 altına" in x for x in w) and any("1,20 altında" in x for x in w) and "uyarı: TM: golcü eksik" in w


def test_closing_price_frozen_after_kickoff_and_clv_stats(tmp_path, monkeypatch):
    monkeypatch.setattr(kontrol, "DAILY", tmp_path)
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.65)
    kontrol.check("2026-11-20", dt.datetime(2026, 11, 20, 21, 40, tzinfo=TSI))
    _day(tmp_path, "2026-11-20T22:00:00+03:00", p_now=0.40)  # in-play price after kick-off must not count
    after = dt.datetime(2026, 11, 20, 22, 30, tzinfo=TSI)
    rows, clv = kontrol.check("2026-11-20", after)
    assert rows[0]["started"] and clv["1|13|3.5 Alt|0"]["p_close"] == 0.65
    st = kontrol.clv_stats(clv, after)
    assert st["n"] == 1 and st["pos"] == 1 and abs(st["mean"] - 0.03) < 1e-9


def test_apply_live_odds_lowers_and_drops_suspended():
    matches = [{"code": 7, "selections": [
        {"key": "a", "odds": 1.71, "fair_prob": 0.58, "ev": 0.0},
        {"key": "b", "odds": 1.30, "fair_prob": 0.70, "ev": 0.0},
        {"key": "c", "odds": 2.00, "fair_prob": 0.40, "ev": 0.0}]},
        {"code": 8, "selections": [{"key": "x", "odds": 1.5, "fair_prob": 0.6, "ev": 0.0}]}]
    kupon.apply_live_odds(matches, {7: {"a": 1.65, "b": 1.35}})
    sel = {s["key"]: s for s in matches[0]["selections"]}
    assert sel["a"]["odds"] == 1.65 and abs(sel["a"]["ev"] - (0.58 * 1.65 - 1)) < 1e-12
    assert sel["b"]["odds"] == 1.30          # a higher live price is not used
    assert "c" not in sel                    # no longer offered
    assert matches[1]["selections"][0]["odds"] == 1.5  # match not in the bulletin (started): untouched


def test_prior_legs_block_same_selection_but_allow_other_selection_on_same_match(tmp_path, monkeypatch):
    monkeypatch.setattr(kupon, "DAILY", tmp_path)
    day = tmp_path / "2026-11-20"
    day.mkdir()
    leg = {"code": 1, "key": "1|MS 1|0", "name": "MS 1"}
    (day / "kupon_5x_0926.json").write_text(json.dumps({"coupons": [{"legs": [leg]}]}), encoding="utf-8")
    prior = kupon.prior_coupon_legs("2026-11-20", 10)
    assert prior == [leg] and kupon.prior_coupon_legs("2026-11-20", 5) == []
    pool = [[{"code": 1, "key": "1|MS 1|0", "name": "MS 1"}, {"code": 1, "key": "12|2.5 Üst|0", "name": "2.5 Üst"},
             {"code": 1, "key": "1|MS 2|0", "name": "MS 2"}]]
    left = {x["name"] for x in kupon.drop_conflicts(pool, prior)[0]}
    assert left == {"2.5 Üst"}  # same bet and the contradicting MS 2 are gone, a compatible bet stays
