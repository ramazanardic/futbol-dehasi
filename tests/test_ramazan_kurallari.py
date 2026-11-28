"""Ramazan'ın kupon kuralları — kural onarımı (28 Kasım 2026).

KURALLAR.md'deki her kural burada en az bir testle bağlanır. Bu testler kırılırsa kural gevşetilmiş demektir:
PR birleştirilmez. Kurallar: bacak P ≥ 0,70 · oran 1,20–1,80 · maç başına tek bacak · 2–5 bacak (en çok 6) ·
yasak aileler (beraberlik, KG/BTTS, ilk gol, takım golü, İY/MS, İY/2Y, skor, çifte şans, handikap) ·
banko yoksa boş sonuç + dürüst mesaj · varsayılan 20+ oranlı kupon yok · yüksek oran motoru günlük hatta yok.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import pytest

from quantfoot import settings as S
from quantfoot.coupons import coupon_rules as R
from quantfoot.strategy import kupon_modu as KM

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"rk_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _leg(i: int, name: str = "İY 1.5 Alt", odds: float = 1.30, p: float = 0.78, **kw):
    return {"code": i, "match": f"Ev{i} - Dep{i}", "name": name, "odds": odds, "p": p, **kw}


# ---------------------------------------------------------------- 1) bacak P ≥ 0,70

def test_min_leg_probability_default_is_070_not_065():
    assert R.MIN_CALIBRATED_P == pytest.approx(0.70)
    assert inspect.signature(R.leg_decision).parameters["min_p"].default == pytest.approx(0.70)
    kk = _load("kasa_koruma")
    assert inspect.signature(kk.run).parameters["min_p"].default == pytest.approx(0.70)
    nk_src = (SCRIPTS / "nesine_kupon.py").read_text(encoding="utf-8")
    assert "Kademe 3" not in nk_src and "0.65, 0.65" not in nk_src  # 0,65 kademesi geri gelmedi


def test_leg_below_070_rejected_even_if_everything_else_is_fine():
    assert not R.leg_decision(_leg(1, p=0.66)).ok
    assert R.leg_decision(_leg(1, p=0.80)).ok


# ---------------------------------------------------------------- 2) oran 1,20–1,80

@pytest.mark.parametrize("odds,ok", [(1.19, False), (1.20, True), (1.55, True), (1.80, True), (1.81, False), (2.10, False)])
def test_leg_odds_window(odds, ok):
    assert R.leg_decision(_leg(1, odds=odds, p=0.85)).ok is ok


def test_settings_odds_window():
    assert (S.MIN_LEG_ODDS, S.BANKO_MAX_LEG_ODDS) == (1.20, 1.80)


# ---------------------------------------------------------------- 3) maç başına tek bacak

def test_one_leg_per_match_in_coupon():
    cands = [_leg(1, "İY 1.5 Alt", p=0.80), _leg(1, "3.5 Alt", p=0.82), _leg(2), _leg(3)]
    c = R.build_rules_coupon(cands)
    ids = [L.match_id for L in c.legs]
    assert len(ids) == len(set(ids)) == 3


def test_daily_audit_flags_two_legs_from_same_match():
    G = _load("gunluk_tahmin")
    rows = [{"kupon": "k", "kupon_no": "1", "nesine_kodu": "1", "mac": "A - B", "secim_adi": n,
             "nesine_oran": "1.30", "olasilik": "0.80"} for n in ("İY 1.5 Alt", "3.5 Alt")]
    audit = G.audit_coupons(rows)
    assert any("aynı maçtan" in x for x in audit["coupons"][0]["ihlaller"])


# ---------------------------------------------------------------- 4) yasak aileler

BANNED = [
    "MS X", "MS 0", "İY X", "2Y 0",                              # beraberlik
    "KG Var", "KG Yok", "2Y KG Yok", "İY KG Var",                # KG / BTTS (yarı KG dahil)
    "İlk Gol Ev", "Ev İlk Golü Atar",                            # ilk gol
    "Ev 0.5 Üst", "Dep 1.5 Alt", "Ev Gol Atar", "Dep Gol Atamaz",  # takım golü
    "Ev İki Yarıda Gol Atar", "Ev İki Yarıda Gol Atamaz", "DEĞİL(Ev İki Yarıda Gol)",
    "İY/MS 1/1", "İY/MS 2/2", "İY/2Y 1/1",                       # İY/MS, İY/2Y
    "Skor 2-1", "Skor 1-0",                                      # skor
    "Çifte Şans 1-X", "ÇŞ 1X", "Handikap 1 (-1)", "Hnd(-1) 1",   # çifte şans / handikap
]


@pytest.mark.parametrize("name", BANNED)
def test_banned_leg_never_passes_even_at_high_probability(name):
    dec = R.leg_decision(_leg(1, name=name, odds=1.40, p=0.95))
    assert not dec.ok, (name, dec.reasons)


@pytest.mark.parametrize("name", BANNED)
def test_banned_leg_cannot_be_rehabilitated(name):
    dec = R.leg_decision(_leg(1, name=name, odds=1.40, p=0.95, rehabilitated=True))
    assert not dec.ok, (name, dec.reasons)


@pytest.mark.parametrize("name", ["MS 1", "2.5 Alt", "3.5 Alt", "İY 1.5 Alt"])
def test_plain_allowed_legs_still_pass(name):
    assert R.leg_decision(_leg(1, name=name, odds=1.35, p=0.86)).ok, name


def test_combo_leg_with_banned_part_rejected():
    assert not R.leg_decision(_leg(1, name="MS 1 & KG Var", odds=1.60, p=0.90)).ok


# ---------------------------------------------------------------- 5) 2–5 bacak, en çok 6

def test_leg_count_limits():
    assert (R.DEFAULT_MIN_LEGS, R.DEFAULT_MAX_LEGS, R.HARD_MAX_LEGS) == (2, 5, 6)
    assert (S.BANKO_MIN_LEGS, S.BANKO_MAX_LEGS, S.BANKO_HARD_MAX_LEGS) == (2, 5, 6)
    pool = [_leg(i) for i in range(10)]
    assert len(R.build_rules_coupon(pool).legs) == 5
    assert len(R.build_rules_coupon(pool, prefer_n=6, max_legs=6).legs) == 6
    assert len(R.build_rules_coupon(pool, prefer_n=10, max_legs=10).legs) == 6
    pol = KM.policy("banko")
    assert (pol.min_legs, pol.max_legs, pol.guard.min_legs, pol.guard.max_legs) == (2, 5, 2, 6)


def test_guard_rejects_single_and_seven_leg_banko():
    good = [_leg(i, "2.5 Alt", 1.28, 0.80, tier="keskin") for i in range(7)]
    assert not KM.guard_legs(good[:1]).ok
    assert KM.guard_legs(good[:2]).ok
    assert KM.guard_legs(good[:6]).ok
    assert not KM.guard_legs(good[:7]).ok


# ---------------------------------------------------------------- 6) banko yoksa boş + dürüst mesaj

def test_no_banko_returns_empty_coupon_with_honest_note():
    c = R.build_rules_coupon([_leg(1), _leg(2, "KG Var"), _leg(3, "MS X"), _leg(4, p=0.60)])
    assert c.legs == () and c.short and c.p_win == 0.0
    assert any("kural gevşetilmedi" in n for n in c.notes)


def test_nesine_kupon_has_no_never_say_no_fallback():
    nk = _load("nesine_kupon")
    src = (SCRIPTS / "nesine_kupon.py").read_text(encoding="utf-8")
    assert "kural gevşetilmedi" in nk.HONEST_NO_COUPON.lower() or "Kural gevşetilmedi" in nk.HONEST_NO_COUPON
    assert "asla hayır" not in src.lower()
    assert "fb_sharp" not in src and "fb_c" not in src


def test_kupon_kur_does_not_force_model_legs_or_fallback_rounds():
    src = (SCRIPTS / "kupon_kur.py").read_text(encoding="utf-8")
    assert '"--model-bacak"' not in src
    assert "--yontem" not in src
    assert "dürüst ret" in src


# ---------------------------------------------------------------- 7) varsayılan 20+ oranlı kupon yok

def test_banko_guard_rejects_20_plus_total_odds():
    legs = [_leg(i, "2.5 Alt", 1.80, 0.95, tier="keskin") for i in range(6)]  # 1,8^6 ≈ 34
    res = KM.guard_legs(legs)
    assert not res.ok and any("20+" in e for e in res.errors)
    assert S.BANKO_MAX_TOTAL_ODDS == 20.0


def test_nesine_kupon_refuses_20_plus_target_in_banko_without_network(capsys):
    nk = _load("nesine_kupon")
    assert nk.main(["--hedef", "25", "--tarih", "2026-11-28", "--no-pull"]) is None
    assert "20+ oranlı kupon" in capsys.readouterr().out


def test_daily_pipeline_has_no_high_odds_engine_and_low_default_target():
    G = _load("gunluk_tahmin")
    cmds = G.step_commands("2026-11-28", [G.DEFAULT_TARGET], py="py")
    flat = [c[1] for step in cmds.values() for c in step]
    assert not any(x.endswith(("yuksek_oran_motoru.py", "yuksek_oran_analiz.py")) for x in flat)
    assert G.DEFAULT_TARGET < 20
    assert all("--mod" in c and c[c.index("--mod") + 1] == "banko" for c in cmds["kupon"])


def test_unified_engine_removed():
    assert not (ROOT / "src" / "quantfoot" / "coupons" / "unified_engine.py").exists()
    assert not (SCRIPTS / "temiz_kupon.py").exists()


def test_rules_document_exists_and_states_core_rules():
    txt = (ROOT / "KURALLAR.md").read_text(encoding="utf-8").lower()
    for needle in ("0,70", "1,20", "1,80", "maç başına tek bacak", "2–5", "dürüst", "20", "kendi sonucunu yazma yasak"):
        assert needle in txt, needle
    for f in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        assert "KURALLAR.md" in (ROOT / f).read_text(encoding="utf-8"), f
