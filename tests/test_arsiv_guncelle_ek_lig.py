"""arsiv_guncelle: ek lig (football-data "new leagues") ekleme, gün/ay ters tarih çift kaydı, form doldurma."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLS = ["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "HomeElo", "AwayElo", "Form3Home", "Form5Home",
        "Form3Away", "Form5Away", "FTHome", "FTAway", "FTResult", "OddHome", "OddDraw", "OddAway", "MaxHome", "MaxDraw",
        "MaxAway"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"t_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _archive(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows, columns=COLS).to_csv(path, index=False)


def test_new_league_rows_added_with_closing_odds_and_swapped_date_dedup(tmp_path):
    ag = _load("arsiv_guncelle")
    arch = tmp_path / "matches.csv"
    # eski satır: 12/08/2024 yanlışlıkla 2024-12-08 okunmuş
    _archive(arch, [{"Division": "ARG", "MatchDate": "2024-12-08", "MatchTime": "23:00:00", "HomeTeam": "Tigre",
                     "AwayTeam": "Godoy Cruz", "FTHome": 0, "FTAway": 2, "FTResult": "A"}])
    nl = tmp_path / "latest" / "new_leagues"
    nl.mkdir(parents=True)
    (nl / "ARG.csv").write_text(
        "Country,League,Season,Date,Time,Home,Away,HG,AG,Res,PSCH,PSCD,PSCA,MaxCH,MaxCD,MaxCA,AvgCH,AvgCD,AvgCA\n"
        "Argentina,Liga Profesional,2024,12/08/2024,23:00,Tigre,Godoy Cruz,0,2,A,2.43,2.87,3.59,2.45,3,3.64,2.38,2.84,3.46\n"
        "Argentina,Liga Profesional,2026,20/11/2026,20:00,Tigre,Lanus,2,1,H,,,,2.2,3.2,3.6,2.1,3.1,3.5\n"
        "Argentina,Liga Profesional,2026,26/11/2026,20:00,Lanus,Tigre,1,1,D,,,,x,3.2,3.6,x,3.1,3.5\n"
        "Argentina,Liga Profesional,2026,30/11/2026,20:00,Boca,River,,,,,,,,,,,,\n",
        encoding="utf-8")
    (nl / "XXX.csv").write_text("Country,League\n", encoding="utf-8")  # bilinmeyen kod yok sayılır
    n = ag.update(arch, tmp_path / "latest")
    assert n == 2  # çift kayıt ve oynanmamış maç eklenmez
    d = pd.read_csv(arch)
    new = d.iloc[1:]
    assert list(new["MatchDate"]) == ["2026-11-20", "2026-11-26"]
    assert new.iloc[0]["OddHome"] == 2.1 and new.iloc[0]["MaxHome"] == 2.2
    assert pd.isna(new.iloc[1]["OddHome"])  # bozuk 'x' hücresi boş kalır
    # form: Tigre önceki maç (0-2 kayıp) → 0 puan; ikinci maçta Tigre 1 galibiyet → 3
    assert new.iloc[0]["Form3Home"] == 0 and new.iloc[1]["Form3Away"] == 3
    assert pd.isna(new.iloc[0]["HomeElo"])
    assert n == 2 and ag.update(arch, tmp_path / "latest") == 0  # ikinci çalıştırma bir şey eklemez


def test_existing_rows_stay_byte_identical(tmp_path):
    ag = _load("arsiv_guncelle")
    arch = tmp_path / "matches.csv"
    _archive(arch, [{"Division": "E0", "MatchDate": "2026-11-01", "MatchTime": "15:00", "HomeTeam": "A", "AwayTeam": "B",
                     "FTHome": 1, "FTAway": 0, "FTResult": "H"}])
    before = arch.read_bytes()
    s = tmp_path / "latest" / "season_2627"
    s.mkdir(parents=True)
    (s / "E0.csv").write_text("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,AvgH,AvgD,AvgA\n"
                              "E0,01/11/2026,15:00,A,B,1,0,H,2,3,4\nE0,22/11/2026,15:00,B,A,2,2,D,2.5,3.1,2.9\n",
                              encoding="utf-8")
    assert ag.update(arch, tmp_path / "latest") == 1
    after = arch.read_bytes()
    assert after.startswith(before)
    row = pd.read_csv(arch).iloc[-1]
    assert row["Form3Home"] == 0 and row["Form3Away"] == 3


def test_fetch_new_league_mapping_matches_archive_codes():
    fg = _load("fetch_global_odds")
    ag = _load("arsiv_guncelle")
    assert fg.NEW_LEAGUES == ag.NEW_LEAGUES


def test_banko_band_check_runs_on_tiny_archive(tmp_path):
    bb = _load("banko_bant_kontrol")
    arch = tmp_path / "m.csv"
    pd.DataFrame([{"Division": "E0", "MatchDate": "2026-11-01", "FTHome": 2, "FTAway": 0, "OddHome": 1.30,
                   "OddDraw": 5.0, "OddAway": 9.0, "Over25": 1.6, "Under25": 2.3}] * 3).to_csv(arch, index=False)
    rep = bb.market_check(arch, since="2026-07-01")
    tot = next(r for r in rep["ms_1_2"] if r["bant"].startswith("≥0.70"))
    assert tot["n"] == 3 and tot["isabet"] == 1.0
