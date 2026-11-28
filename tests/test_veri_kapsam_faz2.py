"""Veri kapsam Faz 2/3 (28 Kas 2026): football-data sezon delikleri ve boş İY/istatistik hücrelerinin dış kaynakla
doldurulması — eski hücre asla değişmez, belirsiz eşleşme doldurulmaz, İY > FT yazılmaz."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLS = ["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "Form3Home", "Form5Home", "Form3Away", "Form5Away",
        "FTHome", "FTAway", "FTResult", "HTHome", "HTAway", "HTResult", "HomeCorners", "AwayCorners", "OddHome",
        "PSCHome", "Source"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"t_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hole_fill_appends_only_missing_matches(tmp_path):
    dd = _load("arsiv_delik_doldur")
    arch = tmp_path / "matches.csv"
    pd.DataFrame([{"Division": "G1", "MatchDate": "2022-08-20", "HomeTeam": "Olympiakos", "AwayTeam": "PAOK",
                   "FTHome": 1, "FTAway": 0, "FTResult": "H"}], columns=COLS).to_csv(arch, index=False, lineterminator="\n")
    before = arch.read_text(encoding="utf-8")
    src = tmp_path / "mmz_2223_G1.csv"
    src.write_text("Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,AvgH,AvgD,AvgA,PSCH\n"
                   "G1,21/08/2022,18:00,Olympiakos ,PAOK,1,0,H,0,0,D,1.8,3.4,4.5,1.85\n"       # zaten var (±1 gün)
                   "G1,27/08/2022,18:00,PAOK,AEK,2,2,D,1,1,D,2.1,3.3,3.4,2.15\n", encoding="utf-8")
    assert dd.run(arch, [src])["eklenen"] == 1
    d = pd.read_csv(arch)
    assert arch.read_text(encoding="utf-8").startswith(before)
    r = d.iloc[-1]
    assert (r.HomeTeam, r.HTHome, r.PSCHome, r.OddHome) == ("PAOK", 1, 2.15, 2.1)
    assert r.Form3Home == 0  # PAOK önceki maçı kaybetti
    assert dd.run(arch, [src])["eklenen"] == 0


def test_detail_fill_only_empty_cells_and_unique_matches(tmp_path, monkeypatch):
    md = _load("mac_detay_doldur")
    arch = tmp_path / "matches.csv"
    rows = [{"Division": "NOR", "MatchDate": "2025-05-01", "HomeTeam": "Bodo/Glimt", "AwayTeam": "Molde", "FTHome": 2,
             "FTAway": 1, "FTResult": "H"},
            {"Division": "NOR", "MatchDate": "2025-05-02", "HomeTeam": "Brann", "AwayTeam": "Viking", "FTHome": 1,
             "FTAway": 1, "FTResult": "D", "HTHome": 1, "HTAway": 0, "HTResult": "H"},
            {"Division": "NOR", "MatchDate": "2025-05-03", "HomeTeam": "Rosenborg", "AwayTeam": "Tromso", "FTHome": 0,
             "FTAway": 0, "FTResult": "D"}]
    pd.DataFrame(rows, columns=COLS).to_csv(arch, index=False, lineterminator="\n")
    lines0 = arch.read_text(encoding="utf-8").split("\n")
    ham = tmp_path / "espn"
    ham.mkdir()
    with gzip.open(ham / "nor.1.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in ({"d": "2025-05-01", "h": "FK Bodo/Glimt", "a": "Molde FK", "hg": 2, "ag": 1, "ht_h": 1, "ht_a": 1, "c_h": 7, "c_a": 3},
                  {"d": "2025-05-02", "h": "Brann", "a": "Viking FK", "hg": 1, "ag": 1, "ht_h": 0, "ht_a": 0, "c_h": 4, "c_a": 5},
                  {"d": "2025-05-03", "h": "Rosenborg", "a": "Tromso", "hg": 0, "ag": 0, "ht_h": 1, "ht_a": 0}):  # İY > FT
            g.write(json.dumps(r) + "\n")
    base = pd.read_csv(arch)
    found = md.match(base, md.load_source("espn", ham, {"nor.1": "NOR"}))
    assert set(found) == {0, 1, 2}
    v = md.validate(base, found)
    assert v["HTHome"] == {"n": 1, "uyum": 0.0}
    st = md.fill(arch, base, found, {"HTHome", "HTAway", "HomeCorners", "AwayCorners"})
    d = pd.read_csv(arch)
    assert (d.HTHome.iloc[0], d.HTAway.iloc[0], d.HTResult.iloc[0], d.HomeCorners.iloc[0]) == (1, 1, "D", 7)
    assert (d.HTHome.iloc[1], d.HTResult.iloc[1], d.HomeCorners.iloc[1]) == (1, "H", 4)  # dolu İY korunur
    assert pd.isna(d.HTHome.iloc[2])  # İY > FT yazılmaz
    lines = arch.read_text(encoding="utf-8").split("\n")
    assert lines[0] == lines0[0] and st["satir"] == 2
