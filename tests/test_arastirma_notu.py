"""Araştırma notu (t190u): şema, saklama, veto/uyarı/not-yok davranışı, P'nin yükseltilememesi, etki ölçümü."""

import datetime as dt
import importlib.util
import json
from argparse import Namespace
from pathlib import Path
import sys

import pytest

from quantfoot.data import arastirma_notu as AN

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kupon = _load("nesine_kupon")
olcum = _load("arastirma_etki_olcumu")
arastirma = _load("mac_web_arastirma")

NOW = dt.datetime(2026, 11, 28, 9, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))


def _match(code=1):
    return {"status": "fiyatlandı", "reference": "Smarkets (borsa)", "kickoff_iso": "2026-11-28T20:00:00+03:00",
            "kickoff": "2026-11-28 20:00", "code": code, "league": "L", "home": "A", "away": "B", "selections": [
                {"market": "MS", "selection": "1", "name": "MS 1", "odds": 1.50, "fair_prob": 0.72, "ev": -0.08, "mbs": 1, "direct": True},
                {"market": "AÜ", "selection": "Üst", "name": "2.5 Üst", "odds": 1.90, "fair_prob": 0.74, "ev": 0.0, "mbs": 1, "direct": True},
                {"market": "KG", "selection": "Var", "name": "KG Var", "odds": 1.30, "fair_prob": 0.60, "ev": -0.2, "mbs": 1, "direct": True},
            ]}


def _note(decisions, code=1):
    n = AN.empty_note("2026-11-28", code, "A", "B", "2026-11-28T20:00:00+03:00", "L")
    n["bacak_kararlari"] = decisions
    return n


def _legs(notes, min_prob=0.0):
    pools = kupon.candidates([_match()], NOW, 1.2, min_prob, False, keep_all=True, notes=notes)
    return {leg["name"]: leg for pool in pools for leg in pool}


# ---------------------------------------------------------------- şema
def test_validation_rules():
    ok = _note([{"secim": "MS 1", "karar": "veto", "gerekce": "kaleci yok"}])
    assert AN.validate(ok) == []
    assert any("gerekçe" in e for e in AN.validate(_note([{"secim": "MS 1", "karar": "veto"}])))
    assert any("gerekçe" in e for e in AN.validate(_note([{"secim": "MS 1", "karar": "uyari", "gerekce": " "}])))
    assert AN.validate(_note([{"secim": "MS 1", "karar": "onay"}])) == []  # onay gerekçesiz de geçerli
    assert any("karar" in e for e in AN.validate(_note([{"secim": "MS 1", "karar": "belki", "gerekce": "x"}])))
    bad = _note([])
    bad["takimlar"]["ev"]["kesin_eksik"] = [{"oyuncu": "X", "rol": "GK", "onem": 5}]
    assert any("onem" in e for e in AN.validate(bad))
    # not olasılık/oran taşıyamaz
    assert any("olasılık" in e for e in AN.validate(_note([{"secim": "MS 1", "karar": "onay", "p": 0.99}])))


def test_save_load_and_empty_fields(tmp_path):
    n = _note([{"secim": "1", "karar": "uyari", "gerekce": "rotasyon"}])
    p = AN.save(n, "2026-11-28", tmp_path)
    assert p.parent.name == "2026-11-28" and p.name.startswith("1_a_b")
    got = AN.load_day("2026-11-28", tmp_path)["1"]
    assert "hakem" in got["bos_alanlar"] and "bacak_kararlari" not in got["bos_alanlar"]
    with pytest.raises(ValueError):
        AN.save(_note([{"secim": "MS 1", "karar": "veto"}]), "2026-11-28", tmp_path)


def test_merge_patch_updates_decisions_by_selection():
    n = _note([{"secim": "MS 1", "karar": "uyari", "gerekce": "a"}])
    out = AN.merge_patch(n, {"bacak_kararlari": [{"secim": "1", "karar": "veto", "gerekce": "b"},
                                                 {"secim": "2.5 Üst", "karar": "onay"}],
                             "takimlar": {"ev": {"kesin_eksik": [{"oyuncu": "K", "rol": "GK", "onem": 3}]}},
                             "kaynaklar": [{"url": "https://x.org/a", "baslik": "x"}]})
    ds = {d["secim"]: d for d in out["bacak_kararlari"]}
    assert ds["MS 1"]["karar"] == "veto" and ds["2.5 Üst"]["karar"] == "onay" and len(ds) == 2
    assert out["takimlar"]["ev"]["kesin_eksik"][0]["kaynak"] == "yapay_zeka"
    assert AN.validate(out) == []


def test_from_match_autofills_and_refresh_keeps_ai_fields():
    m = _match()
    m["research"] = {"teams": {"home": {"rest_days": 3.0}}, "motivation": {"home": "12./18 (orta sıralar)"},
                     "weather": {"temp_c": 4.0, "rain_mm": 1.0, "wind_kmh": 20.0, "severe": False, "flag": None},
                     "referee": "H. Hakem",
                     "web": {"takimlar": {"home": {"sakat_cezali": {"source": "fpl", "injuries": [
                         {"name": "Kaleci", "importance": "GK1", "state": "out", "pos": "GK"},
                         {"name": "Forvet", "importance": "CORE", "state": "doubt", "pos": "ATT"}], "suspensions": []},
                         "hoca_degisikligi": [{"yeni": "Z", "tarih": "2026-11-10"}]}},
                         "haber": [{"baslik": "Takım haberi"}], "kaynaklar": [{"url": "https://e.org", "kaynak": "ESPN", "ok": True}]}}
    auto = AN.from_match(m, "2026-11-28")
    ev = auto["takimlar"]["ev"]
    assert ev["kesin_eksik"][0]["oyuncu"] == "Kaleci" and ev["kesin_eksik"][0]["onem"] == 3
    assert ev["supheli"][0]["oyuncu"] == "Forvet"
    assert ev["rotasyon"]["dinlenme_gun"] == 3.0 and ev["hoca_degisikligi"]["var"] is True
    assert auto["hakem"]["ad"] == "H. Hakem" and auto["hava_zemin"]["hava"]["temp_c"] == 4.0
    assert auto["kaynaklar"][0]["url"] == "https://e.org" and AN.validate(auto) == []
    assert auto["bacak_kararlari"] == []  # karar yalnız yapay zekâdan gelir
    old = AN.merge_patch(auto, {"takimlar": {"dep": {"rotasyon": {"risk": "yuksek", "gerekce": "Avrupa maçı"}}},
                                "bacak_kararlari": [{"secim": "MS 1", "karar": "veto", "gerekce": "g"}]})
    again = AN.refresh(AN.from_match(m, "2026-11-28"), old)
    assert again["takimlar"]["dep"]["rotasyon"]["risk"] == "yuksek"
    assert again["bacak_kararlari"][0]["karar"] == "veto"
    assert again["takimlar"]["ev"]["kesin_eksik"][0]["oyuncu"] == "Kaleci"


def test_leg_verdict_precedence_and_aliases():
    assert AN.leg_verdict(None, "MS 1")["durum"] == "not_yok"
    n = _note([{"secim": "MS 1", "karar": "onay"}])
    assert AN.leg_verdict(n, "MS 1")["durum"] == "onay"
    assert AN.leg_verdict(n, "2.5 Üst")["durum"] == "karar_yok"
    n = _note([{"secim": "*", "karar": "uyari", "gerekce": "genel"}, {"secim": "1", "karar": "onay"}])
    assert AN.leg_verdict(n, "MS 1")["durum"] == "uyari"  # uyarı onaydan güçlü
    n = _note([{"secim": "MS 1", "karar": "onay"}, {"secim": "*", "karar": "veto", "gerekce": "maç ertelendi"}])
    assert AN.leg_verdict(n, "MS 1") == {"durum": "veto", "gerekce": "maç ertelendi"}


# ---------------------------------------------------------------- kupon entegrasyonu
def test_veto_leg_never_enters_pool():
    base = _legs(None)
    assert {"MS 1", "2.5 Üst"} <= set(base)
    notes = {"1": _note([{"secim": "MS 1", "karar": "veto", "gerekce": "kaleci cezalı"}])}
    legs = _legs(notes)
    assert "MS 1" not in legs and "2.5 Üst" in legs
    whole = {"1": _note([{"secim": "*", "karar": "veto", "gerekce": "rotasyon"}])}
    assert kupon.candidates([_match()], NOW, 1.2, 0.0, False, notes=whole) == []


def test_uyari_leg_is_kept_and_flagged_without_changing_numbers():
    base = _legs(None)
    legs = _legs({"1": _note([{"secim": "2.5 Üst", "karar": "uyari", "gerekce": "hava kötü"}])})
    assert legs["2.5 Üst"]["arastirma"] == {"durum": "uyari", "gerekce": "hava kötü"}
    for k in ("p", "p_low", "odds", "ev", "sigma"):
        assert legs["2.5 Üst"][k] == base["2.5 Üst"][k]
    assert "ARAŞTIRMA NOTU UYARI: hava kötü" in kupon.leg_reason(legs["2.5 Üst"])


def test_no_note_behaviour_unchanged_and_report_says_so():
    base = _legs(None)
    other = _legs({"999": _note([{"secim": "MS 1", "karar": "veto", "gerekce": "x"}], code=999)})  # başka maçın notu
    strip = lambda d: {k: {kk: vv for kk, vv in v.items() if kk != "arastirma"} for k, v in d.items()}  # noqa: E731
    assert strip(base) == strip(other) == strip(_legs({}))
    assert base["MS 1"]["arastirma"]["durum"] == "not_yok"
    assert "araştırma notu yok" in kupon.leg_reason(base["MS 1"])
    assert "araştırma notu yok" in kupon.research_notes_section({}, [_match()])[0]


def test_note_cannot_raise_probability_or_loosen_threshold():
    base = _legs(None, min_prob=0.70)
    assert "KG Var" not in base  # P 0.60 < 0.70 eşik
    notes = {"1": _note([{"secim": "*", "karar": "onay", "gerekce": "her şey temiz"}])}
    with_note = _legs(notes, min_prob=0.70)
    assert set(with_note) == set(base)  # onay eşiğin altındaki bacağı içeri almaz
    for k, leg in with_note.items():
        assert leg["p"] == base[k]["p"] and leg["p_low"] == base[k]["p_low"] and leg["odds"] == base[k]["odds"]
        assert leg["arastirma"]["durum"] == "onay"
    assert "eşikleri gevşetmez" in kupon.leg_reason(with_note["MS 1"])


def test_vetoed_leg_does_not_hide_others_in_pareto_front():
    m = _match()
    m["selections"].append({"market": "X", "selection": "y", "name": "MS 1X", "odds": 1.40, "fair_prob": 0.80, "ev": -0.1, "mbs": 1, "direct": True})
    notes = {"1": _note([{"secim": "2.5 Üst", "karar": "veto", "gerekce": "g"}])}
    names = {leg["name"] for pool in kupon.candidates([m], NOW, 1.2, 0.0, False, notes=notes) for leg in pool}
    assert "2.5 Üst" not in names and "MS 1X" in names


def test_veto_section_lists_vetoed_legs():
    notes = {"1": _note([{"secim": "MS 1", "karar": "veto", "gerekce": "kaleci cezalı"}])}
    text = "\n".join(kupon.research_notes_section(notes, [_match()]))
    assert "VETO" in text and "kaleci cezalı" in text


# ---------------------------------------------------------------- not-yaz / not-oku arayüzü
def test_cli_not_yaz_and_oku(tmp_path, capsys):
    a = Namespace(tarih="2026-11-28", mac=["77"], json=json.dumps({
        "mac": {"ev": "Köln", "dep": "Elversberg", "lig": "Bundesliga"},
        "bacak_kararlari": [{"secim": "MS 1", "karar": "veto", "gerekce": "test"}]}),
        json_dosya=None, not_klasoru=str(tmp_path), kim="test", bos=False)
    arastirma.cmd_not_yaz(a)
    f = next((tmp_path / "2026-11-28").glob("77_*.json"))
    assert json.loads(f.read_text())["bacak_kararlari"][0]["karar"] == "veto"
    capsys.readouterr()
    arastirma.cmd_not_oku(Namespace(tarih="2026-11-28", mac=["77"], bos=True, not_klasoru=str(tmp_path)))
    assert "bos_alanlar" in capsys.readouterr().out
    with pytest.raises(SystemExit):  # gerekçesiz veto kaydedilemez
        arastirma.cmd_not_yaz(Namespace(tarih="2026-11-28", mac=["77"], json='{"bacak_kararlari":[{"secim":"MS 1","karar":"veto"}]}',
                                        json_dosya=None, not_klasoru=str(tmp_path), kim="t", bos=False))


# ---------------------------------------------------------------- etki ölçümü
def test_measurement_groups_and_insufficient_data():
    note = _note([{"secim": "MS 1", "karar": "veto", "gerekce": "g"}, {"secim": "2.5 Üst", "karar": "onay"}])
    res = {"completed": True, "ht": [0, 0], "ft90": [0, 1]}
    rows = olcum.leg_rows(note, _match(), res)
    assert {(r["secim"], r["karar"], r["gerceklesti"]) for r in rows} == {("MS 1", "veto", False), ("2.5 Üst", "onay", False)}
    s = olcum.summarize(rows)
    assert "yetersiz veri" in s["veto"]["yorum"] and "yetersiz veri" in s["onay"]["yorum"]
    assert s["uyari"]["sonuclanan"] == 0
    wild = olcum.leg_rows(_note([{"secim": "*", "karar": "uyari", "gerekce": "g"}]), _match(), res)
    assert {r["secim"] for r in wild} == {"MS 1", "2.5 Üst"}  # KG Var P 0.60 < 0.62 aday değil


def test_measurement_with_enough_data_compares_to_p():
    rows = [{"karar": "veto", "p": 0.75, "gerceklesti": i < 20} for i in range(60)]  # 33% < 75%
    s = olcum.summarize(rows)["veto"]
    assert s["sonuclanan"] == 60 and "işe yarıyor" in s["yorum"] and s["gerceklesme"] == pytest.approx(1 / 3)
    ok = olcum.summarize([{"karar": "onay", "p": 0.75, "gerceklesti": i < 45} for i in range(60)])["onay"]
    assert ok["yorum"] == "P ile uyumlu"


def test_note_decision_survives_into_coupon_legs():
    m2 = _match(2)
    notes = {"1": _note([{"secim": "2.5 Üst", "karar": "uyari", "gerekce": "hava"}]), "2": _note([], code=2)}
    pools = kupon.candidates([_match(1), m2], NOW, 1.2, 0.0, False, notes=notes)
    c = kupon.best_coupon(pools, 2.0, max_legs=3)
    assert c and {leg["arastirma"]["durum"] for leg in c["legs"]} <= {"uyari", "karar_yok", "not_yok"}
    assert all("arastirma" in leg for leg in c["legs"])
