"""Match dossier: every family sums to 100 %, scores are a proper distribution."""

import importlib.util
from pathlib import Path
import sys

import numpy as np

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("mac_dosyasi", SCRIPTS / "mac_dosyasi.py")
md = importlib.util.module_from_spec(spec)
spec.loader.exec_module(md)

from quantfoot.markets.omni_markets import compute_omni_markets  # noqa: E402

EXCLUSIVE = ("Maç sonucu", "Karşılıklı gol", "Tek / Çift", "Toplam gol aralığı", "1. yarı sonucu", "2. yarı sonucu",
             "İlk yarı / maç sonucu", "En çok gol olan yarı", "Kaç farkla kazanır", "Handikap (-1, ev sahibine)",
             "Maç sonucu & karşılıklı gol", "Maç sonucu & 2,5 Alt/Üst")


def test_exclusive_families_sum_to_one_and_scores_are_distribution():
    joint = compute_omni_markets(1.9, 1.0).joint
    priced = {"joint": joint, "quoted": {}, "inputs": set()}
    for fam, outs in md.families("A", "B"):
        if fam in EXCLUSIVE or "Alt/Üst" in fam:
            total = sum(md._prob(name, priced)[0] for _, name in outs)
            assert abs(total - 1.0) < 1e-6, fam
    lines = md.score_tables(joint, "A", "B", top=200)
    probs = [float(x.split("%")[1].rstrip(" |")) for x in lines if x.startswith("| ") and "-" in x.split("|")[1]
             and "/" not in x.split("|")[1]][:200]
    assert probs == sorted(probs, reverse=True)
    assert np.isclose(joint.sum(), 1.0)
