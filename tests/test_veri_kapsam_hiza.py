"""matches.csv'de tarihsel bir boş satır var (pandas skip_blank_lines ile atlar). Metin düzeyinde yazan araçlar pandas
satır indeksini fiziksel satıra boş satırları sayarak çevirmeli; aksi hâlde yazım bir önceki maça kayar (28 Kas 2026
Faz 2 İY dolgusu hatası)."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HDR = "Division,MatchDate,HomeTeam,AwayTeam,FTHome,FTAway,FTResult,HTHome,HTAway,HTResult,HomeCorners,AwayCorners,Source"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"h_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _arch(tmp_path: Path) -> Path:
    p = tmp_path / "matches.csv"
    p.write_text(HDR + "\n"
                 "NOR,2025-03-29,Fredrikstad,Brann,3,0,H,,,,,,\n"
                 "\n"  # tarihsel boş satır
                 "NOR,2025-03-30,Molde,Sarpsborg 08,0,2,A,,,,,,\n"
                 "NOR,2025-03-30,Tromso,Haugesund,1,0,H,,,,,,\n"
                 "NOR,2025-03-31,Bryne,Bodo/Glimt,0,1,A,,,,,,espn\n", encoding="utf-8")
    return p


def test_detail_fill_after_blank_line_hits_right_row(tmp_path):
    md = _load("mac_detay_doldur")
    arch = _arch(tmp_path)
    ham = tmp_path / "espn"
    ham.mkdir()
    with gzip.open(ham / "nor.1.jsonl.gz", "wt", encoding="utf-8") as g:
        g.write(json.dumps({"d": "2025-03-30", "h": "Tromsø IL", "a": "FK Haugesund", "hg": 1, "ag": 0,
                            "ht_h": 1, "ht_a": 0, "c_h": 6, "c_a": 2}) + "\n")
    base = pd.read_csv(arch)
    found = md.match(base, md.load_source("espn", ham, {"nor.1": "NOR"}))
    md.fill(arch, base, found, {"HTHome", "HTAway", "HomeCorners", "AwayCorners"})
    d = pd.read_csv(arch)
    tr = d[d.HomeTeam == "Tromso"].iloc[0]
    mo = d[d.HomeTeam == "Molde"].iloc[0]
    assert (tr.HTHome, tr.HTAway, tr.HTResult, tr.HomeCorners) == (1, 0, "H", 6)
    assert pd.isna(mo.HTHome) and pd.isna(mo.HomeCorners)  # komşu satır değişmez
    assert arch.read_text(encoding="utf-8").split("\n")[2] == ""  # boş satır yerinde


def test_drop_lines_after_blank_line_drops_right_row(tmp_path):
    ag = _load("arsiv_guncelle")
    arch = _arch(tmp_path)
    base = pd.read_csv(arch)
    i = base.index[base.HomeTeam == "Bryne"][0]
    ag._drop_lines(arch, {base.index.get_loc(i)})
    d = pd.read_csv(arch)
    assert list(d.HomeTeam) == ["Fredrikstad", "Molde", "Tromso"]
