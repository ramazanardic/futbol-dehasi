"""Veri kapsam düzeltmeleri (28 Kas 2026): Pinnacle sütunları, ESPN skor doldurma + football-data ile değiştirme,
arşive ek kaynak ekleme, global-odds iş akışı sırası."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLS = ["Division", "MatchDate", "MatchTime", "HomeTeam", "AwayTeam", "Form3Home", "Form5Home", "Form3Away", "Form5Away",
        "FTHome", "FTAway", "FTResult", "OddHome", "OddDraw", "OddAway", "PSHome", "PSDraw", "PSAway", "PSCHome",
        "PSCDraw", "PSCAway", "PSOver25", "PSUnder25", "PSCOver25", "PSCUnder25", "Source"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"t_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _maclar(path: Path, rows: list[dict]) -> None:
    cols = ["tarih", "sezon", "yarisma", "tur", "ev", "dep", "hg", "ag", "iy_ev", "iy_dep", "durum", "ham_skor", "kaynak"]
    df = pd.DataFrame(rows, columns=cols)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as g:
        df.to_csv(g, index=False, lineterminator="\r\n")


def _espn(t, ev, dep, hg, ag, comp="espn/rus.1"):
    return {"tarih": t, "sezon": "2026/27", "yarisma": comp, "tur": "lig", "ev": ev, "dep": dep, "hg": hg, "ag": ag,
            "durum": "FT", "kaynak": "espn"}


def test_espn_fill_after_last_football_data_day_and_replaced_later(tmp_path):
    ag = _load("arsiv_guncelle")
    arch = tmp_path / "matches.csv"
    base = [{"Division": "RUS", "MatchDate": "2026-08-02", "MatchTime": "18:00", "HomeTeam": "Zenit", "AwayTeam": "Baltika",
             "FTHome": 2, "FTAway": 0, "FTResult": "H", "OddHome": 1.5},
            {"Division": "RUS", "MatchDate": "2026-08-01", "MatchTime": "18:00", "HomeTeam": "Orenburg",
             "AwayTeam": "Krylya Sovetov", "FTHome": 1, "FTAway": 1, "FTResult": "D"}]
    pd.DataFrame(base, columns=COLS).to_csv(arch, index=False, lineterminator="\n")
    mac = tmp_path / "maclar.csv.gz"
    _maclar(mac, [_espn("2026-08-02", "Zenit St Petersburg", "FC Baltika Kaliningrad", 2, 0),  # fd'de zaten var
                  _espn("2026-08-09", "Zenit St Petersburg", "Gazovik Orenburg", 3, 1),
                  _espn("2026-08-10", "Krylia Sovetov", "Unknown FC", 0, 0)])                   # eşlenemeyen takım
    latest = tmp_path / "latest"
    latest.mkdir()
    before = arch.read_text(encoding="utf-8")
    assert ag.update(arch, latest, maclar=mac) == 1
    d = pd.read_csv(arch)
    row = d.iloc[-1]
    assert (row.HomeTeam, row.AwayTeam, row.FTResult, row.Source) == ("Zenit", "Orenburg", "H", "espn")
    assert pd.isna(row.OddHome) and pd.isna(row.PSCHome)  # oran uydurulmaz
    assert arch.read_text(encoding="utf-8").startswith(before)
    assert ag.update(arch, latest, maclar=mac) == 0
    # football-data aynı maçı bir gün farkla getirir -> ESPN satırı silinir, oranlı satır yazılır
    (latest / "season_2627").mkdir()
    (latest / "season_2627" / "RUS.csv").write_text(
        "Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,AvgH,AvgD,AvgA,PSH,PSD,PSA,PSCH,PSCD,PSCA\n"
        "RUS,10/08/2026,17:00,Zenit,Orenburg,3,1,H,1.4,4.5,7.0,1.42,4.6,7.4,1.40,4.7,7.6\n", encoding="utf-8")
    assert ag.update(arch, latest, maclar=mac) == 1
    d = pd.read_csv(arch)
    assert (d.Source == "espn").sum() == 0 and len(d) == 3
    last = d.iloc[-1]
    assert last.MatchDate == "2026-08-10" and last.PSCHome == 1.40 and last.PSHome == 1.42 and last.OddHome == 1.4
    assert arch.read_text(encoding="utf-8").startswith(before)
    assert ag.update(arch, latest, maclar=mac) == 0


def test_pinnacle_backfill_keeps_old_bytes_and_is_idempotent(tmp_path):
    pdl = _load("pinnacle_doldur")
    arch = tmp_path / "matches.csv"
    arch.write_text("Division,MatchDate,HomeTeam,AwayTeam,FTHome,FTAway,OddHome\n"
                    "E0,2024-08-17,Nott'm Forest,Bournemouth,1.0,1.0,2.10\n"
                    "E0,2024-08-18,Chelsea,Man City,0.0,2.0,4.50\n"
                    "E0,2024-08-19,X,Y,0.0,0.0,\n", encoding="utf-8")
    src = tmp_path / "mmz_2425_E0.csv"
    src.write_text("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,PSH,PSD,PSA,PSCH,PSCD,PSCA,P>2.5,P<2.5,PC>2.5,PC<2.5\n"
                   "E0,17/08/2024,Nottm Forest,Bournemouth,1,1,2.2,3.5,3.4,2.25,3.4,3.3,1.9,1.95,1.92,1.93\n"
                   "E0,18/08/2024,Chelsea FC,Manchester City,0,2,4.6,4.1,1.75,4.8,4.2,1.72,,,,\n", encoding="utf-8")
    ex, sc = pdl.build_lookup([(src, None)])
    st = pdl.fill(arch, ex, sc)
    assert st == {"satir": 3, "tam_eslesme": 1, "skor_eslesme": 1, "bos": 1}
    d = pd.read_csv(arch)
    assert list(d.columns[-11:]) == pdl.NEW_COLS
    assert d.PSCHome.tolist()[:2] == [2.25, 4.8] and d.PSCOver25.iloc[0] == 1.92 and pd.isna(d.PSHome.iloc[2])
    lines = arch.read_text(encoding="utf-8").split("\n")
    assert lines[1].startswith("E0,2024-08-17,Nott'm Forest,Bournemouth,1.0,1.0,2.10,")
    once = arch.read_text(encoding="utf-8")
    pdl.fill(arch, ex, sc)
    assert arch.read_text(encoding="utf-8") == once


def test_archive_extra_sources_append_only(tmp_path):
    ek = _load("arsiv_ek_kaynak")
    mac = tmp_path / "maclar.csv.gz"
    _maclar(mac, [_espn("2026-08-08", "Benfica", "Porto", 1, 0, "espn/por.1")])
    before = gzip.decompress(mac.read_bytes())
    ham = tmp_path / "ham"
    (ham / "espn_lig").mkdir(parents=True)
    with gzip.open(ham / "espn_lig" / "por.1.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in ({"d": "2026-08-08", "t": "19:00", "l": "por.1", "h": "Benfica", "a": "Porto", "hg": 1, "ag": 0, "st": "FT"},
                  {"d": "2026-08-15", "t": "19:00", "l": "por.1", "h": "Porto", "a": "Braga", "hg": 2, "ag": 2, "st": "FT"}):
            g.write(json.dumps(r) + "\n")
    (ham / "openligadb").mkdir()
    (ham / "openligadb" / "bl3_2026.json").write_text(json.dumps([
        {"matchIsFinished": True, "matchDateTime": "2026-08-01T14:00:00", "team1": {"teamName": "A"}, "team2": {"teamName": "B"},
         "matchResults": [{"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
                          {"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1}]},
        {"matchIsFinished": False, "matchDateTime": "2026-12-01T14:00:00", "team1": {"teamName": "A"},
         "team2": {"teamName": "C"}, "matchResults": []}]), encoding="utf-8")
    (ham / "wiki_ek").mkdir()
    with gzip.open(ham / "wiki_ek" / "x.jsonl.gz", "wt", encoding="utf-8") as g:
        g.write(json.dumps({"_t": "mac", "tarih": "", "sezon": "2025/26", "yarisma": "wiki/x", "ev": "K", "dep": "L",
                            "hg": 0, "ag": 3, "iy_ev": None, "iy_dep": None, "durum": "FT", "ham_skor": None,
                            "kaynak": "wikipedia"}) + "\n")
        g.write(json.dumps({"_t": "oyuncu", "oyuncu": "P"}) + "\n")
    res = ek.merge(mac, ham)
    assert res["eklenen"] == 3
    after = gzip.decompress(mac.read_bytes())
    assert after.startswith(before)
    d = pd.read_csv(mac, dtype=str, keep_default_na=False)
    o = d[d.yarisma == "openligadb/bl3"].iloc[0]
    assert (o.hg, o.ag, o.iy_ev, o.iy_dep, o.sezon) == ("2", "1", "", "", "2026/27")  # OpenLigaDB İY güvenilmez
    w = d[d.yarisma == "wiki/x"].iloc[0]
    assert w.tur == "lig" and w.tarih == "" and w.iy_ev == ""
    assert ek.merge(mac, ham)["eklenen"] == 0


def test_global_odds_workflow_commits_before_club_elo():
    wf = (ROOT / ".github" / "workflows" / "global-odds.yml").read_text(encoding="utf-8")
    assert wf.index("name: Commit data") < wf.index("name: Club Elo ratings")
    elo = wf[wf.index("name: Club Elo ratings"):]
    assert "continue-on-error: true" in elo and "timeout-minutes: 4" in elo
    assert "timeout-minutes: 25" in wf
    assert 'timeout=20' in (ROOT / "scripts" / "elo_gorus.py").read_text(encoding="utf-8")


def test_matches_csv_has_pinnacle_columns_and_marked_espn_rows():
    head = (ROOT / "data" / "matches.csv").open(encoding="utf-8").readline().strip().split(",")
    for c in ("PSHome", "PSCHome", "PSCOver25", "Source"):
        assert c in head
