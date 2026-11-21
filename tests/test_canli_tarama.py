"""Canlı tarayıcı — kaydedilmiş gerçek yanıtlarla, ağ yok."""

import argparse
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

from quantfoot.data import fotmob as fm
from quantfoot.data import live_scan as ls
from quantfoot.markets import inplay

FIX = Path(__file__).parent / "fixtures" / "canli"
TSI = dt.timezone(dt.timedelta(hours=3))


def _j(name):
    return json.loads((FIX / name).read_text())


def test_parse_nesine_live_skips_locked_odds():
    ev = ls.parse_nesine_live(_j("nesine_live.json"))
    slatina = next(e for e in ev if "Slatina" in e["home"])
    assert "MS 1" not in slatina["markets"]          # 1.00 = kapalı
    assert slatina["markets"]["MS X"] == 4.71
    assert "3.5 Üst" not in slatina["markets"]   # MTID 68 durumu MS=0 (kapalı) → fiyatlanmaz (21 Kas denetimi)
    satu = next(e for e in ev if "Satu" in e["home"])
    assert satu["markets"]["2.5 Alt"] == 1.43 and satu["markets"]["2.5 Üst"] == 1.7


def test_espn_scoreboard_and_summary():
    live = ls.parse_espn_scoreboard(_j("espn_scoreboard.json"))
    assert live and live[0]["minute"] is not None and live[0]["home"]
    st = ls.parse_espn_summary(_j("espn_summary.json"), live[0]["home_id"], live[0]["away_id"])
    assert set(st) == {"home", "away"} and st["home"]["shots"] is not None


def test_fotmob_live_matching_and_state():
    matches = fm.parse_matches(_j("fotmob_matches.json"), live_only=True)
    nes = ls.parse_nesine_live(_j("nesine_live.json"))
    satu = next(e for e in nes if "Satu" in e["home"])
    m = fm.find_match(matches, satu["home"], satu["away"])
    assert m and "Satu Mare" in m["home"]
    lv = ls.live_from_fotmob(m, _j("fotmob_detail_live.json"))
    assert lv["minute"] > 45 and lv["home_red"] == 0


def test_inplay_model_basic_properties():
    lh, la = inplay.fit_lambdas({"MS 1": 0.5, "MS X": 0.27, "MS 2": 0.23, "2.5 Üst": 0.52})
    assert lh > la > 0
    assert inplay.remaining_share(0) == pytest.approx(1.0)
    assert inplay.remaining_share(94) == pytest.approx(0.0)
    assert 0.4 < inplay.remaining_share(45) < 0.6  # yoğunluk artıyor → ikinci yarı payı > yarı
    p = inplay.final_probabilities(0.4, 0.3, 2, 0)
    assert p["MS 1"] > 0.9 and p["1.5 Üst"] == pytest.approx(1.0)
    s = inplay.LiveState(minute=60, home_red=1)
    rh, ra, notes = inplay.remaining_lambdas(1.5, 1.2, s)
    s0 = inplay.LiveState(minute=60)
    rh0, ra0, _ = inplay.remaining_lambdas(1.5, 1.2, s0)
    assert rh < rh0 and ra > ra0 and any("kırmızı" in n for n in notes)
    hi = inplay.LiveState(minute=60, stats={"home": {"xg": 2.5}})
    assert inplay.remaining_lambdas(1.5, 1.2, hi)[0] > rh0


def test_evaluate_flags_value_and_stakes_from_reserve():
    nes = {"code": 1, "home": "A", "away": "B", "markets": {"2.5 Üst": 1.9, "MS 1": 1.05}}
    live = {"minute": 30.0, "hg": 1, "ag": 0, "home_red": 0, "away_red": 0}
    ops = ls.evaluate(nes, live, (1.6, 1.2, "test"), {}, min_ev=0.05, reserve=100, kelly_mult=0.25,
                      cap_frac=0.2, step=5, min_stake=5)
    assert len(ops) == 1 and ops[0]["market"] == "2.5 Üst" and ops[0]["ev"] > 0.05
    assert ops[0]["stake_tl"] % 5 == 0
    none = ls.evaluate(nes, live, (1.6, 1.2, "test"), {}, min_ev=0.05, reserve=0, kelly_mult=0.25,
                       cap_frac=0.2, step=5, min_stake=5)
    assert none[0]["stake_tl"] == 0
    late = dict(live, minute=88)
    assert ls.evaluate(nes, late, (1.6, 1.2, "t"), {}, min_ev=0.05, reserve=100, kelly_mult=0.25, cap_frac=0.2,
                       step=5, min_stake=5) == []


def test_dedupe_only_resends_on_better_odds():
    now = dt.datetime(2026, 11, 21, 13, 0, tzinfo=TSI)
    state = {}
    op = {"code": 1, "market": "2.5 Üst", "nesine_odds": 2.0, "ev": 0.1}
    assert ls.dedupe([op], state, now) == [op]
    assert ls.dedupe([op], state, now + dt.timedelta(minutes=5)) == []
    better = dict(op, nesine_odds=2.1)
    assert ls.dedupe([better], state, now + dt.timedelta(minutes=10)) == [better]


def test_scan_once_offline(tmp_path):
    spec = importlib.util.spec_from_file_location("canli_tarama", Path(__file__).parents[1] / "scripts" / "canli_tarama.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    nes = _j("nesine_live.json")
    satu = next(e for e in nes["sg"]["EA"] if "Satu" in e["HN"])
    # maç öncesi bültende aynı kod: güçlü ev favorisi, düşük gol beklentisi
    pre = {"sg": {"EA": [{"TYPE": 1, "C": satu["C"], "HN": satu["HN"], "AN": satu["AN"], "ESD": 1795251600000,
                          "MA": [{"MTID": 1, "OCA": [{"N": 1, "O": 1.6}, {"N": 2, "O": 3.8}, {"N": 3, "O": 5.0}]},
                                 {"MTID": 12, "OCA": [{"N": 1, "O": 1.7}, {"N": 2, "O": 2.05}]}]}]}}
    calls = []

    def fetch(url, params, timeout):
        calls.append(url)
        if url == ls.NESINE_LIVE_URL:
            return nes
        if url == ls.NESINE_PRE_URL:
            return pre
        if url == ls.ESPN_SCOREBOARD:
            return {"events": []}
        return None

    class FakeFM:
        def matches_on(self, day, ttl_s=60):
            return _j("fotmob_matches.json")

        def details(self, mid, ttl_s=240):
            return _j("fotmob_detail_live.json")

    args = argparse.Namespace(min_ev=0.0, canli_rezerv=100.0, kupon_limit_oran=0.2, fotmob_detay=8)
    now = dt.datetime(2026, 11, 21, 13, 10, tzinfo=TSI)
    fresh, stats = mod.scan_once(args, tmp_path, fetch=fetch, now=now, fotmob=FakeFM())
    assert stats["nesine_live"] >= 5 and stats["matched"] >= 1 and stats["priced"] == 1
    assert all("api-sports" not in u for u in calls)          # API-Football asla
    again, _ = mod.scan_once(args, tmp_path, fetch=fetch, now=now + dt.timedelta(minutes=5), fotmob=FakeFM())
    assert again == []                                         # aynı fırsat tekrar gönderilmez
    if fresh:
        assert (tmp_path / "2026-11-21.jsonl").exists() and (tmp_path / "2026-11-21.md").exists()
