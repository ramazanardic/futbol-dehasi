"""21 Kasım 2. tur: kupon modları (banko/risk) her kurucuda, oynanan kupon kaydı + maruziyet, sonuç defteri,
karışım ağırlıkları, OddsMath UTC saatleri, 6+ gol yardımcılarının repo kopyası."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from quantfoot import settings as S
from quantfoot.data import oddsmath as om
from quantfoot.evaluation import leg_grading as lg
from quantfoot.markets import blend, goal_tail_fit as gtf
from quantfoot.strategy import kupon_modu as KM

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _leg(code, odds, p, name="2.5 Alt", **kw):
    return {"code": code, "match": f"Ev{code} - Dep{code}", "name": name, "odds": odds, "p": p, "tier": "keskin", **kw}


BANKO5 = [_leg(i, 1.28, 0.70) for i in range(5)]


# ------------------------------------------------------------------ modlar

def test_banko_is_default_and_policy_values():
    assert KM.DEFAULT_MODE == "banko"
    b, r = KM.policy("banko"), KM.policy("risk")
    assert (b.min_prob, b.max_leg_odds, b.min_legs, b.max_legs, b.prefer_min_odds) == (0.65, 1.80, 5, 6, 1.25)
    assert r.max_leg_odds == 2.10 and r.sharp_only and b.sharp_only
    with pytest.raises(ValueError):
        KM.policy("piyango")


def test_banko_accepts_five_safe_legs_and_rejects_short_low_odds_coupons():
    assert KM.guard_legs(BANKO5).ok
    short = KM.guard_legs(BANKO5[:2])
    assert not short.ok and any("1–2 maçlık" in e for e in short.errors)
    seven = KM.guard_legs([_leg(i, 1.28, 0.75) for i in range(7)])
    assert not seven.ok and any("en çok 6" in e for e in seven.errors)


def test_banko_rejects_weak_or_high_odds_or_soft_reference_leg():
    legs = BANKO5[:4] + [_leg(9, 1.95, 0.70)]
    assert any("> 1.80" in e for e in KM.guard_legs(legs).errors)
    legs = BANKO5[:4] + [_leg(9, 1.30, 0.60)]
    assert any("< %65" in e for e in KM.guard_legs(legs).errors)
    legs = BANKO5[:4] + [dict(_leg(9, 1.30, 0.70), tier="orta")]
    assert any("keskin referans" in e for e in KM.guard_legs(legs).errors)


def test_banko_warns_below_1_22_buffer():
    legs = BANKO5[:4] + [_leg(9, 1.21, 0.80)]
    r = KM.guard_legs(legs)
    assert r.ok and any("tabana çok yakın" in w for w in r.warnings)


def test_risk_mode_allows_target_coupon_but_caps_leg_odds_and_is_honest():
    k2000 = [_leg(1, 1.60, 0.60), _leg(2, 1.42, 0.61), _leg(3, 1.41, 0.65), _leg(4, 1.46, 0.60), _leg(5, 1.44, 0.63)]
    assert not KM.guard_legs(k2000, "banko").ok
    r = KM.guard_legs(k2000, "risk")
    assert r.ok and r.p_win == pytest.approx(0.6 * 0.61 * 0.65 * 0.6 * 0.63)
    line = KM.honest_line(r, 300)
    assert "tutma ihtimali %9.0" in line and "11'de 1" in line and "beklenen değer" in line
    bad = k2000[:4] + [_leg(6, 2.30, 0.48)]
    assert any("> 2.10" in e for e in KM.guard_legs(bad, "risk").errors)
    lottery = [_leg(i, 2.05, 0.46) for i in range(5)]
    rl = KM.guard_legs(lottery, "risk")
    assert rl.ok and any("piyango" in w for w in rl.warnings)      # risk: uyarı, ret değil
    assert not KM.guard_legs(lottery, "banko").ok


def test_target_reachable():
    assert KM.target_reachable(3.3, "banko")
    assert not KM.target_reachable(20.0, "banko")


def test_to_leg_reads_various_builder_schemas():
    from quantfoot.strategy.coupon_builder import MarketRecommendation
    rec = MarketRecommendation("m1", "A", "B", "L", "k", "MS", "MS 1", 0.7, 1.43, 1.3, False, 1.0, 0.0, "")
    leg = KM.to_leg(rec)
    assert (leg.match_id, leg.odds, leg.p, leg.offered) == ("m1", 1.3, 0.7, True)
    est = MarketRecommendation("m1", "A", "B", "L", "k", "MS", "MS 1", 0.7, 1.43, 1.3, True, 1.0, 0.0, "")
    assert KM.to_leg(est).offered is False
    assert KM.to_leg({"code": 1, "odds": 1.3, "p": 0.7, "reference": "ESPN"}).sharp_ref is False
    assert KM.to_leg({"code": 1, "odds": 1.3, "p": 0.7, "reference": "Marathonbet [orta]"}).sharp_ref is False
    # model + keskin fiyat ayrı verilmişse aile ağırlığıyla karışır; MS'de w=0 → piyasa, iyimser değil düşük olan
    mixed = KM.to_leg({"code": 1, "name": "MS 1", "odds": 1.3, "p": 0.80, "p_model": 0.80, "p_sharp": 0.66})
    assert mixed.p == pytest.approx(0.66, abs=0.01)


def test_bulletin_offered_by_key_and_name():
    class Sel:
        def __init__(self, name, odds):
            self.name, self.odds = name, odds

    class Ev:
        code, selections = 77, [Sel("2.5 Alt", 1.6), Sel("MS 1", 1.3)]
    off = KM.bulletin_offered(KM.bulletin_book([Ev()]))
    assert off(77, None, "2.5 Alt") is True
    assert off(77, None, "Dep 0.5 Alt") is False          # Pécs dersi: bültende olmayan seçim
    assert off(78, None, "MS 1") is False                  # maç bültende yok
    assert KM.bulletin_offered({77: {"1|MS 1|0": 1.3}})(77, "1|MS 1|0") is True
    assert KM.bulletin_offered(None)(77, "x") is None
    legs = BANKO5[:4] + [_leg(77, 1.30, 0.70, name="Dep 0.5 Alt")]
    assert any("bülteninde yok" in e for e in KM.guard_legs(legs, offered=off).errors)


# ------------------------------------------------------------------ kayıt + maruziyet

def test_registry_and_open_exposure(tmp_path):
    now = dt.datetime(2026, 11, 21, 19, 0, tzinfo=S.TSI)
    legs = [dict(_leg(1, 1.3, 0.7), ko="2026-11-21 20:45"), dict(_leg(2, 1.3, 0.7), ko="2026-11-21 13:00")]
    KM.register_placed(tmp_path, {"id": "A", "stake": 100, "legs": legs})
    KM.register_placed(tmp_path, {"id": "B", "stake": 50, "legs": legs[:1]})
    KM.register_placed(tmp_path, {"id": "C", "stake": 50, "legs": legs[:1], "status": "kaybetti"})
    exp = KM.open_exposure(tmp_path, now=now)
    assert exp == {"1": 2}                              # maç 2 çoktan bitti, C kapandı
    KM.register_placed(tmp_path, {"id": "B", "stake": 60, "legs": legs[:1]})   # aynı id güncellenir
    assert len(KM.load_placed(tmp_path)) == 3
    r = KM.guard_legs([_leg(1, 1.3, 0.7)] + BANKO5[1:], open_exposure=exp)
    assert not r.ok and any("açık kuponda" in e for e in r.errors)
    with pytest.raises(ValueError):
        KM.register_placed(tmp_path, {"id": "X"})


# ------------------------------------------------------------------ nesine_kupon bağlantısı

def test_nesine_kupon_mode_filters_and_guard():
    nk = _load("nesine_kupon")
    pools = [[_leg(1, 1.95, 0.7), _leg(1, 1.30, 0.7)], [dict(_leg(2, 1.3, 0.7), tier="orta")], [_leg(3, 1.3, 0.7)]]
    out = nk.filter_pools_for_mode(pools, KM.policy("banko"))
    assert [[x["odds"] for x in p] for p in out] == [[1.30], [1.30]]
    assert [x["odds"] for x in nk.filter_pools_for_mode(pools, KM.policy("risk"))[0]] == [1.95, 1.30]
    good = {"legs": [dict(x, key=f"k{x['code']}") for x in BANKO5]}
    bad = {"legs": BANKO5[:2]}
    live = {i: {f"k{i}": 1.28} for i in range(5)}
    kept, notes = nk.apply_mode_guard([good, bad], "banko", live, {})
    assert kept == [good] and good["guard"]["ok"] and "tutma ihtimali" in good["guard"]["honest"]
    assert notes and "banko kontrolünden geçmeyen" in notes[0]
    live[4] = {}
    kept, _ = nk.apply_mode_guard([good], "banko", live, {})
    assert kept == []                                  # seçim bültenden kalktı


def test_kupon_politikasi_mode_guard_blocks_rule_breaking_coupon():
    kp = _load("kupon_politikasi")
    from quantfoot.strategy.accumulator_policy import Leg, evaluate_coupon
    ev = evaluate_coupon([Leg("a", "MS 1", 2.5, 0.45), Leg("b", "MS 1", 1.3, 0.8)])
    kp.mode_guard([ev], "banko")
    assert any("banko kuralı" in r for r in ev.reasons)


def test_canli_tarama_annotates_banko():
    ct = _load("canli_tarama")
    ops = [{"code": 1, "match": "A - B", "market": "MS 1", "nesine_odds": 1.30, "fair_prob": 0.80, "market_prob": 0.74},
           {"code": 2, "match": "C - D", "market": "MS 1", "nesine_odds": 3.79, "fair_prob": 0.32, "market_prob": 0.21},
           {"code": 3, "match": "E - F", "market": "MS 1", "nesine_odds": 1.30, "fair_prob": 0.80, "market_prob": None}]
    ct.annotate_banko(ops)
    assert [o["banko_ok"] for o in ops] == [True, False, False]


# ------------------------------------------------------------------ notlama + defter

@pytest.mark.parametrize("leg,res,exp", [
    ({"market": "2,5 Gol Alt/Üst", "sel": "2,5 Alt", "name": "2.5 Alt"}, {"state": "bitti", "ht": [0, 0], "ft": [1, 1]}, True),
    ({"market": "Maç Sonucu", "sel": "1", "name": "MS 1"}, {"state": "bitti", "ht": [0, 0], "ft": [0, 1]}, False),
    ({"market": "1. Yarı Sonucu", "sel": "2", "name": "İY 2"}, {"state": "bitti", "ht": [0, 0], "ft": [0, 1]}, False),
    ({"market": "Deplasman 1. Yarı 0,5 Gol Alt/Üst", "sel": "0,5 Alt", "name": "Dep İY 0.5 Alt"},
     {"state": "bitti", "ht": [0, 1], "ft": [2, 1]}, False),
    ({"market": "Handikaplı Maç Sonucu", "sel": "1", "name": "Hnd(-1) 1"}, {"state": "bitti", "ht": [1, 0], "ft": [3, 1]}, True),
    ({"market": "Çifte Şans", "sel": "1-X", "name": "ÇŞ 1X"}, {"state": "bitti", "ht": [0, 0], "ft": [1, 1]}, True),
    ({"market": "2,5 Gol Alt/Üst", "sel": "2,5 Alt", "name": "2.5 Alt"}, {"state": "canlı", "score": [2, 1], "minute": 60}, False),
    ({"market": "2,5 Gol Alt/Üst", "sel": "2,5 Alt", "name": "2.5 Alt"}, {"state": "canlı", "score": [1, 1], "minute": 60}, None),
    ({"market": "Maç Sonucu", "sel": "1", "name": "MS 1"}, {"state": "başlamadı"}, None),
])
def test_leg_grading(leg, res, exp):
    assert lg.decide(leg, res) is exp


def test_market_family():
    assert lg.market_family({"name": "MS 1", "market": "Maç Sonucu"}) == "ms"
    assert lg.market_family({"name": "KGKG"}) == "kg_iki_yari"
    assert lg.market_family({"name": "2.5 Alt", "market": "2,5 Gol Alt/Üst"}) == "alt_ust"
    assert lg.market_family({"name": "MS 1", "live": True}) == "canli"


def test_ledger_grade_append_dedupe_and_report(tmp_path):
    sd = _load("sonuc_defteri")
    legs = [{"code": 1, "match": "A - B", "market": "Maç Sonucu", "sel": "1", "name": "MS 1", "odds": 1.4, "p": 0.7, "ko": "2026-11-21 18:00"},
            {"code": 2, "match": "C - D", "market": "2,5 Gol Alt/Üst", "sel": "2,5 Alt", "name": "2.5 Alt", "odds": 1.5, "p": 0.66, "ko": "2026-11-21 20:00"}]
    KM.register_placed(tmp_path, {"id": "K", "stake": 100, "legs": legs, "mode": "banko", "date": "2026-11-21"})
    coupons = KM.load_placed(tmp_path)
    results = {1: {"state": "bitti", "ht": [1, 0], "ft": [2, 0]}, 2: {"state": "başlamadı"}}
    rows = sd.grade_coupons(coupons, results)
    assert len(rows) == 1 and rows[0]["won"] == 1 and coupons[0]["status"] == "açık"
    assert sd.append_ledger(tmp_path, rows) == 1 and sd.append_ledger(tmp_path, rows) == 0   # tekrar yazılmaz
    results[2] = {"state": "bitti", "ht": [1, 1], "ft": [2, 2]}
    rows2 = sd.grade_coupons(coupons, results)
    assert len(rows2) == 1 and rows2[0]["won"] == 0 and coupons[0]["status"] == "kaybetti"
    sd.append_ledger(tmp_path, rows2)
    led = sd.read_ledger(tmp_path)
    assert len(led) == 2
    rep = "\n".join(sd.calibration_report(led))
    assert "tümü | 2" in rep and "200" in rep
    summ = "\n".join(sd.summary_lines(coupons))
    assert "KAYBETTI" in summ and "net -100.00 TL" in summ


def test_ledger_kaydet_from_coupon_file(tmp_path, monkeypatch):
    sd = _load("sonuc_defteri")
    f = tmp_path / "kupon.json"
    f.write_text(json.dumps({"coupons": [{"legs": [dict(x, kickoff="2026-11-21 20:00", market="M", selection=x["name"]) for x in BANKO5]}]}),
                 encoding="utf-8")
    monkeypatch.setattr(sd, "ai_area", lambda: tmp_path)
    sd.main(["kaydet", "--dosya", str(f), "--id", "Z", "--tutar", "100", "--oranlar", "0=1.35"])
    c = KM.load_placed(tmp_path)[0]
    assert c["id"] == "Z" and c["legs"][0]["odds"] == 1.35 and c["guard_ok"] and c["status"] == "açık"
    assert c["odds"] == pytest.approx(round(1.35 * 1.28 ** 4, 2))


# ------------------------------------------------------------------ karışım ağırlıkları

def test_blend_defaults_to_market_without_evidence():
    assert blend.blend_probability("ms1", 0.9, 0.6, weights={}) == pytest.approx(0.6)
    assert blend.blend_probability(None, 0.9, 0.6, weights={}) == pytest.approx(0.6)
    assert blend.blend_probability("ms1", 0.9, None, weights={}) is None      # piyasasız model kupon P'si olamaz
    w = {"kg_var": {"w": 0.5, "a": 0.0, "b": 1.0}}
    assert blend.blend_probability("kg_var", 0.8, 0.5, weights=w) == pytest.approx(1 / (1 + math.exp(-0.5 * math.log(4))))
    assert blend.family_of("2,5 Üst") == "ust25" and blend.family_of("İY 0") is None


def test_shipped_blend_weights_lean_on_market():
    fam = blend.load_weights()
    assert set(fam) >= {"ms1", "msx", "ms2", "ust25", "ust35", "kg_var"}
    assert all(e["w"] <= 0.05 for e in fam.values())     # arşivde model piyasaya bilgi katmadı


def test_karisim_fit_recovers_weight_on_synthetic_data():
    kk = _load("karisim_kalibrasyonu")
    rng = np.random.default_rng(0)
    n = 20000
    truth = rng.uniform(0.2, 0.8, n)
    y = (rng.uniform(size=n) < truth) * 1.0
    market = np.clip(truth + rng.normal(0, 0.02, n), 0.05, 0.95)
    noise = np.clip(rng.uniform(0.2, 0.8, n), 0.05, 0.95)
    w, a, b = kk.fit_blend(kk.logit(market), kk.logit(noise), y)
    assert w < 0.1                                      # bilgisiz model → ağırlık ~0
    m = kk.metrics(market, y)
    assert set(m) >= {"logloss", "brier", "ece"} and m["n"] == n


# ------------------------------------------------------------------ OddsMath UTC + 6+ gol yardımcıları

def test_oddsmath_day_times_are_utc_and_matcher_tight():
    payload = {"data": {"1": {"name": "Turkey - Super League", "events": {
        "9": {"hometeam_name": "Trabzonspor", "awayteam_name": "Eyupspor", "time": "2026-11-22 16:00:00"}}}}}
    ev = om.parse_oddsmath_day_payload(payload)
    assert ev[0]["kickoff"] == dt.datetime(2026, 11, 22, 16, 0, tzinfo=dt.timezone.utc)   # 19:00 TSİ
    ko = dt.datetime(2026, 11, 22, 19, 0, tzinfo=S.TSI)
    hit, _ = om.match_event_to_oddsmath("Trabzonspor", "Eyüpspor", ko, ev)
    assert hit is not None
    hit3, _ = om.match_event_to_oddsmath("Trabzonspor", "Eyüpspor", ko + dt.timedelta(hours=3), ev)
    assert hit3 is None and om.ODDSMATH_MATCH_MAX_HOURS <= 1.5


def test_goal_tail_fit_helpers():
    assert gtf.devig2([1.9, 1.9]) == pytest.approx(0.5, abs=1e-6)
    p = gtf.com_from_mean(2.8, 1.1)
    assert float((np.arange(len(p)) * p).sum()) == pytest.approx(2.8, abs=1e-3)
    assert gtf.tail(gtf.nb_pmf(2.8, 0.0), 0) == pytest.approx(1.0)
    fit = gtf.fit_market({"1.5": [1.25, 4.0], "2.5": [1.9, 1.95], "3.5": [3.1, 1.38]})
    assert 2.3 < fit["mu"] < 3.3 and 0.0 < fit["p6_com"] < fit["p5_com"] < 0.3
    assert gtf.fit_market({}) is None
