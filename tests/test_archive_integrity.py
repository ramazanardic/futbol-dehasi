import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import arsiv_guncelle as archive


def test_archive_deduplicates_across_files_and_is_idempotent(tmp_path):
    target = tmp_path / "matches.csv"
    columns = ["Division", "MatchDate", "HomeTeam", "AwayTeam", "FTHome", "FTAway"]
    pd.DataFrame([["E0", "2026-11-20", "A", "B", 1, 0]], columns=columns).to_csv(target, index=False)
    season = tmp_path / "season_2627"
    season.mkdir()
    fixture = pd.DataFrame([["E0", "21/11/2026", "C", "D", 2, 1]] * 2,
                           columns=["Div", "Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"])
    fixture.to_csv(season / "a.csv", index=False)
    fixture.to_csv(season / "b.csv", index=False)
    assert archive.update(target, tmp_path) == 1
    assert archive.update(target, tmp_path) == 0
    assert len(pd.read_csv(target)) == 2
