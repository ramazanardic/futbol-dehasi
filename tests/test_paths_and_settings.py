"""QUANTFOOT_AI is required; outputs stay in the asking AI's folder; shared settings exist."""

from __future__ import annotations

import argparse
import compileall
import datetime as dt
import importlib
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from quantfoot.evaluation.backtest import order_matches_for_backtest
from quantfoot.paths import VALID_AIS, QuantfootAIError, ai_area, ai_name
from quantfoot.settings import MAX_LEGS, MAX_PRICE_AGE_H, MIN_LEG_ODDS, MODEL_ONLY_MIN_EV, TSI

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_missing_quantfoot_ai_raises(monkeypatch):
    monkeypatch.delenv("QUANTFOOT_AI", raising=False)
    with pytest.raises(QuantfootAIError, match="tanımlı değil"):
        ai_name()
    with pytest.raises(QuantfootAIError):
        ai_area()


def test_invalid_quantfoot_ai_raises(monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "not-an-ai")
    with pytest.raises(QuantfootAIError, match="geçersiz"):
        ai_name()


@pytest.mark.parametrize("name", sorted(VALID_AIS))
def test_valid_ai_names(name, tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", name)
    assert ai_name() == name
    assert ai_area(tmp_path) == tmp_path / "tahminler" / name


def test_outputs_stay_under_own_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    area = ai_area(tmp_path)
    area.mkdir(parents=True)
    (area / "probe.txt").write_text("ok", encoding="utf-8")
    for name in VALID_AIS - {"grokbottahmin"}:
        assert not (tmp_path / "tahminler" / name / "probe.txt").exists()
    assert (tmp_path / "tahminler" / "grokbottahmin" / "probe.txt").read_text(encoding="utf-8") == "ok"


def test_daily_index_is_written_under_ai_folder_not_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import daily as daily_mod

    monkeypatch.setattr(daily_mod, "DAILY", tmp_path / "tahminler" / "grokbottahmin")
    daily_mod._update_index("2026-11-21", 3, 0, 0)
    own = tmp_path / "tahminler" / "grokbottahmin" / "INDEX.md"
    assert own.exists()
    text = own.read_text(encoding="utf-8")
    assert "2026-11-21" in text and "model-only" in text
    assert not (tmp_path / "reports" / "ledger" / "INDEX.md").exists()
    assert "reports/daily" not in text


def test_daily_uses_tsi_clock(monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import daily as daily_mod

    assert daily_mod.TSI is TSI
    assert dt.datetime.now(daily_mod.TSI).utcoffset() == dt.timedelta(hours=3)


def test_nesine_kupon_help_exits_zero():
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "nesine_kupon.py"), "--help"],
        cwd=SCRIPTS.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "--hedef" in r.stdout
    assert "--pull" in r.stdout
    assert "63" in r.stdout  # escaped percent in --dogrudan help is rendered


def test_gun_degerlendirme_compiles_and_fmt3():
    src = SCRIPTS / "gun_degerlendirme.py"
    assert compileall.compile_file(str(src), quiet=1, force=True)
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import gun_degerlendirme as g

    assert g._fmt3(None) == "-"
    assert g._fmt3(0.1234) == "0.123"


def test_same_day_backtest_order_by_match_time():
    df = pd.DataFrame(
        {
            "MatchDate": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01"]),
            "MatchTime": ["18:00", "12:00", None],
            "Division": ["E0", "E0", "E0"],
            "HomeTeam": ["A", "C", "E"],
            "AwayTeam": ["B", "D", "F"],
        }
    )
    out = order_matches_for_backtest(df)
    # Missing time first (na_position=first), then chronological kickoff.
    # pandas stores a missing value as NaN once the column is mixed.
    times = list(out["MatchTime"])
    assert times[0] != times[0] or times[0] is None  # NaN or None
    assert times[1:] == ["12:00", "18:00"]
    assert list(out["HomeTeam"]) == ["E", "C", "A"]


def test_same_day_earlier_kickoff_is_processed_first_for_ratings():
    """Two same-day matches sharing a team: earlier kickoff must precede the later one (no look-ahead)."""
    df = pd.DataFrame(
        {
            "MatchDate": pd.to_datetime(["2024-03-10", "2024-03-10"]),
            "MatchTime": ["20:00", "14:00"],
            "Division": ["E0", "E0"],
            "HomeTeam": ["LaterHome", "EarlyHome"],
            "AwayTeam": ["Shared", "Shared"],
        }
    )
    ordered = order_matches_for_backtest(df)
    assert list(ordered["MatchTime"]) == ["14:00", "20:00"]
    assert list(ordered["HomeTeam"]) == ["EarlyHome", "LaterHome"]


def test_settings_coupon_floors():
    assert MIN_LEG_ODDS == 1.20
    assert MAX_LEGS == 7
    assert MAX_PRICE_AGE_H == 3.0
    assert MODEL_ONLY_MIN_EV == 0.02


class _CaptureParse(Exception):
    def __init__(self, ns: argparse.Namespace):
        self.ns = ns


def _parse_script_main(mod_name: str, argv: list[str], monkeypatch) -> argparse.Namespace:
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    orig = argparse.ArgumentParser.parse_args

    def _capture(self, args=None, namespace=None):
        ns = orig(self, args, namespace)
        raise _CaptureParse(ns)

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", _capture)
    monkeypatch.setattr(sys, "argv", [mod_name + ".py", *argv])
    importlib.invalidate_caches()
    mod = importlib.import_module(mod_name)
    importlib.reload(mod)
    with pytest.raises(_CaptureParse) as exc:
        mod.main()
    return exc.value.ns


def test_nesine_kupon_pull_and_tm_default_off(monkeypatch):
    ns = _parse_script_main("nesine_kupon", ["--hedef", "5"], monkeypatch)
    assert ns.pull is False
    assert ns.no_pull is False
    assert ns.tm is False
    assert ns.no_tm is False


def test_nesine_kupon_pull_opt_in(monkeypatch):
    ns = _parse_script_main("nesine_kupon", ["--hedef", "5", "--pull"], monkeypatch)
    assert ns.pull is True
    assert ns.no_pull is False


def test_nesine_global_tm_default_off(monkeypatch):
    monkeypatch.setenv("QUANTFOOT_AI", "grokbottahmin")
    ns = _parse_script_main("nesine_global", [], monkeypatch)
    assert ns.tm is False
    assert ns.no_tm is False


def test_scripts_import_without_quantfoot_ai(monkeypatch):
    """Importing writers must not require the env var; first path use does."""
    monkeypatch.delenv("QUANTFOOT_AI", raising=False)
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import importlib
    for name in ("nesine_takip", "kupon_kur", "ai_tahmin", "nesine_kupon", "nesine_global"):
        sys.modules.pop(name, None)
        importlib.import_module(name)
