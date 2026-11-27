import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gfi_yari_oranlari as g  # noqa: E402


def test_league_rates_counts_half_combos_and_skips_bad_half_scores():
    rows = [("tr.1", 2, 1, {"score": {"ht": [0, 1]}}),   # İY 2, 2Y 1, MS 1 -> 2/1, both-halves BTTS no
            ("tr.1", 2, 2, {"score": {"ht": [1, 1]}}),   # İY 0, 2Y 0, both halves BTTS yes
            ("tr.1", 1, 0, {"score": {"ht": [2, 0]}}),   # half score above full time: skipped
            ("tr.1", 0, 0, {"score": {}})]               # no half score: skipped
    r = g.league_rates(rows)["tr.1"]
    assert r["n"] == 2
    assert r["iyms_2/1"] == 0.5 and r["iy2y_2/1"] == 0.5
    assert r["iy2"] == 0.5 and r["iy0"] == 0.5
    assert r["kg_iki_yari"] == 0.5 and r["gol_iki_yari"] == 1.0 and r["iy00"] == 0.0


def test_league_first_half_share_is_shrunk_and_mapped(tmp_path, monkeypatch):
    from quantfoot.markets import league_halves as lh
    p = tmp_path / "r.csv"
    p.write_text("# x\nlig,n,gol,iy_gol_payi\ntr.1,1000,3.0,0.40\nhu.1,60,3.0,0.30\n", encoding="utf-8")
    monkeypatch.setattr(lh, "CSV", p)
    lh._table.cache_clear()
    s = lh.league_first_half_share("Türkiye Süper Lig, Normal Sezon")
    assert 0.40 < s < 0.44 and abs(s - (0.40 * 3000 + 0.44 * 400) / 3400) < 1e-9
    assert lh.league_first_half_share("Macaristan NB III") is None  # unmapped keeps the profile
    assert lh.league_first_half_share("Macaristan 1. Ligi") is None  # 60 matches < MIN_MATCHES
    lh._table.cache_clear()


def test_blend_pulls_both_halves_btts_toward_league_rate(tmp_path, monkeypatch):
    from quantfoot.markets import league_halves as lh
    p = tmp_path / "r.csv"
    p.write_text("lig,n,gol,iy_gol_payi,kg_iki_yari,en_cok_2y\ntr.1,1000,3.0,0.43,0.05,0.45\n", encoding="utf-8")
    monkeypatch.setattr(lh, "CSV", p)
    lh._table.cache_clear()
    assert abs(lh.blend_with_league("İki Yarıda KG Var", 0.15, "Türkiye Süper Ligi") - (0.6 * 0.15 + 0.4 * 0.05)) < 1e-12
    assert abs(lh.blend_with_league("En Çok Gol 2Y", 0.40, "Türkiye Süper Ligi") - 0.42) < 1e-12
    assert lh.blend_with_league("KG Var", 0.55, "Türkiye Süper Ligi") == 0.55  # other markets untouched
    assert lh.blend_with_league("İki Yarıda KG Var", 0.15, "Kenya Premier Lig") == 0.15  # no league sample
    lh._table.cache_clear()
