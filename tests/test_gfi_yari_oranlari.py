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
