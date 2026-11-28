"""28 Kas post-mortem: notlayıcı düzeltmeleri ve Pinnacle verisiyle eklenen türev kalibrasyon eğrileri."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantfoot.evaluation.leg_grading import grade
from quantfoot.markets.market_calibration import calibrate_market_probability, load_market_calibration

ROOT = Path(__file__).resolve().parents[1]
BITTI = {"state": "bitti", "ht": [0, 2], "ft": [0, 4]}  # Man Utd 0-4 Brentford (İY 0-2)


@pytest.mark.parametrize("name,market,sel,expected", [
    ("Hnd(+1) 1", "Handikaplı Maç Sonucu", "Hnd(+1) 1", False),   # önceden None: '+' işareti okunmuyordu
    ("Hnd(+1) 2", "Handikaplı Maç Sonucu", "Hnd(+1) 2", True),
    ("Hnd(-1) 2", "Handikaplı Maç Sonucu", "Hnd(-1) 2", True),
    ("MS 1 & 1.5 Üst", "Maç Sonucu ve 1,5 Alt/Üst", "1 & Üst", False),  # kısa seçim adı → kısa addan çöz
    ("MS 2 & 1.5 Üst", "Maç Sonucu ve 1,5 Alt/Üst", "2 & Üst", True),
    ("DEĞİL(Ev Her İki Yarıyı Kazanır)", "Ev Sahibi Her İki Yarıyı da Kazanır", "Hayır", True),
    ("Dep Her İki Yarıyı Kazanır", "Deplasman Her İki Yarıyı da Kazanır", "Evet", True),
    ("Ev İki Yarıda Gol", "Ev Sahibi İki Yarıda da Gol", "Atar", False),
    ("Dep İki Yarıda Gol", "Deplasman İki Yarıda da Gol", "Atar", True),
    ("DEĞİL(Ev En Az Bir Yarıyı Kazanır)", "Ev Sahibi Herhangi Bir Yarıyı Kazanır", "Hayır", True),
    ("Dep En Az Bir Yarıyı Kazanır", "Deplasman Herhangi Bir Yarıyı Kazanır", "Evet", True),
])
def test_grade_fixed_markets(name, market, sel, expected):
    assert grade({"name": name, "market": market, "sel": sel}, BITTI) is expected


def test_half_markets_need_half_time():
    r = {"state": "bitti", "ht": None, "ft": [2, 1]}
    assert grade({"name": "Ev Her İki Yarıyı Kazanır", "market": "", "sel": ""}, r) is None
    assert grade({"name": "Ev İki Yarıda Gol", "market": "", "sel": ""}, r) is None


def test_one_one_draw_half_wins():
    r = {"state": "bitti", "ht": [1, 0], "ft": [2, 2]}  # ev 1. yarıyı kazandı, 2. yarıyı kaybetti
    assert grade({"name": "Ev En Az Bir Yarıyı Kazanır", "market": "", "sel": ""}, r) is True
    assert grade({"name": "Ev Her İki Yarıyı Kazanır", "market": "", "sel": ""}, r) is False


def test_pinnacle_curves_added_and_existing_untouched():
    cal = json.loads((ROOT / "data/calibration/market_calibration.json").read_text(encoding="utf-8"))["markets"]
    new = {"0.5 Üst", "Skor 0-0", "İY/MS 0/0", "Dep İY 0.5 Üst", "En Çok Gol 2Y"}
    assert new <= set(cal)
    for k in new:
        assert cal[k]["kaynak"] == "pinnacle_kalibrasyon_olcumu.py"
        assert cal[k]["oos_ci95"][1] < 0  # tutma kuralı: OOS log-loss farkının GA üst ucu < 0
        assert cal[k]["direct_in_production"] is False
    assert cal["İY 0.5 Üst"]["kaynak"] == "bahis_aileleri_kalibrasyon.py"  # mevcut eğriler değişmedi
    # 3.5 / 1.5 hatları Pinnacle'da zaten kalibre: eğri eklenmedi
    assert "1.5 Üst" not in cal and "3.5 Üst" not in cal


def test_dep_iy_alt_shrinks_toward_reality():
    cal = load_market_calibration()
    p = calibrate_market_probability("Dep İY 0.5 Alt", 0.73, "İngiltere Premier Lig", cal)
    assert 0.70 < p < 0.73
    assert calibrate_market_probability("3.5 Alt", 0.74, "İngiltere Premier Lig", cal) == pytest.approx(0.74)


def test_pinnacle_variant_flag():
    import importlib
    import os
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    old = os.environ.get("QF_AILE_VARYANT")
    os.environ["QF_AILE_VARYANT"] = "pinnacle"
    try:
        import bahis_aileleri_kalibrasyon as BA
        BA = importlib.reload(BA)
        assert BA.PINNACLE and BA.TILT == BA._settings.MARGIN_TILT
        assert BA.cache_path().name.endswith("_pinnacle.npz")
    finally:
        if old is None:
            os.environ.pop("QF_AILE_VARYANT", None)
        else:
            os.environ["QF_AILE_VARYANT"] = old
        importlib.reload(BA)
