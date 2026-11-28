"""GFI türetilmiş öncülleri: veri dosyaları, çözümleme, olasılık hesabı ve varsayılan-kapalı bayrak."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from quantfoot.markets import gfi_priors as gp
from quantfoot.markets import league_halves as lh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import gfi_turet as gt

FILES = ("lig_taban_gfi.csv", "takim_form_gfi.csv", "lig_yari_dakika_gfi.csv")


@pytest.mark.parametrize("name", FILES)
def test_files_small_with_source_note_and_no_match_rows(name):
    p = ROOT / "data" / "gfi" / name
    assert p.stat().st_size < 50 * 1024 * 1024
    first = p.read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("# Kaynak: GLOBAL FOOTBALL INTELLIGENCE") and "yalnız agregat" in first
    cols = set(pd.read_csv(p, comment="#", nrows=1).columns)
    assert not cols & {"day", "home", "away", "ft_home", "ft_away", "fh", "fa"}  # maç satırı yok


def test_resolve_small_leagues_and_tiers():
    assert gp.resolve("Belarus Premier Lig") == ["wr:belarus"]
    assert gp.resolve("Romanya 1. Lig") == ["wr:romania"]
    assert gp.resolve("Uefa Avrupa Ligi") == ["wr:UEFA EL"]
    assert gp.resolve("İngiltere 1. Lig") == ["en.3"]           # mevcut takma ad: League One
    assert gp.resolve("Hollanda 1. Lig") == []                   # ikinci kademe, ülke üst ligine düşmez
    assert gp.resolve("İngiltere Kuzey Premier Ligi") == []
    assert gp.resolve("Almanya Kadınlar Bundesliga") == []
    assert gp.league_row("Belarus Premier Lig", asof="2026-11-20")["n"] >= 80


def test_selection_probabilities_are_consistent():
    p = lambda s: gp.selection_probability(s, 1.5, 1.1, 0.44)
    assert abs(p("MS 1") + p("MS 0") + p("MS 2") - 1) < 1e-9
    assert abs(p("2.5 Alt") + p("2.5 Üst") - 1) < 1e-9
    assert abs(p("DEĞİL(Ev İki Yarıda Gol)") + p("Ev İki Yarıda Gol") - 1) < 1e-9
    assert abs(p("Ev Sahibi Herhangi Bir Yarıyı Kazanır Hayır") - (1 - p("Ev En Az Bir Yarıyı Kazanır"))) < 1e-9
    assert p("İY 0.5 Üst") < p("1.5 Üst")
    assert p("Korner 10.5 Üst") is None


def test_default_off_leaves_prices_unchanged(monkeypatch):
    monkeypatch.delenv("QF_GFI_PRIORS", raising=False)
    assert not gp.enabled()
    assert gp.blend("2.5 Üst", 0.71, "Belarus Premier Lig") == 0.71
    assert lh.league_first_half_share("Bilinmeyen Lig XYZ") is None


def test_enabled_blends_only_goal_families(monkeypatch):
    monkeypatch.setenv("QF_GFI_PRIORS", "1")
    assert gp.blend("2.5 Üst", 0.71, "Belarus Premier Lig") != 0.71
    assert gp.blend("MS 1", 0.71, "Belarus Premier Lig") == 0.71
    assert 0.35 < lh.league_first_half_share("Bilinmeyen Lig XYZ") < 0.5   # genel ortalamaya düşer


def test_code_from_path_and_half_reconstruction():
    assert gt._code_from_path("2023-24/en.2.json") == "en.2"
    assert gt._code_from_path("turkey/2024-25_tr1.txt") == "tr.1"
    assert gt._code_from_path("openliga/2025-26_de.3.txt") == "de.3"
    assert gt._code_from_path("2025-26/cup.txt") == "de.cup"
    wm = pd.DataFrame({"id": [1, 2], "league": ["x-2020-2021"] * 2, "day": ["2021-01-01"] * 2,
                       "home": ["a", "c"], "away": ["b", "d"], "hg": [2, 1], "ag": [1, 0]})
    wg = pd.DataFrame({"match_id": [1, 1, 1, 2], "ordinal": [0, 1, 2, 0], "kind": ["Goal", "Own goal", "Goal", "Goal"],
                       "team": ["home", "home", "away", "away"], "minute": ["12'", "45+2'", "80'", "30'"]})
    x = gt._halves_from_goals(wm, wg).set_index("id")
    assert (x.loc[1, "ht_h"], x.loc[1, "ht_a"]) == (2, 0)
    assert pd.isna(x.loc[2, "ht_h"])  # gol sayısı FT ile tutmuyor -> İY skoru yok
