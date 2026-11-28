"""Ortak AI çıktı doğrulayıcısı (Gemini dahil) — şema, 'kendi sonucunu yazma' yasağı ve kupon kuralları."""

from __future__ import annotations

import ast
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load():
    spec = importlib.util.spec_from_file_location("ai_cikti_dogrula_t", SCRIPTS / "ai_cikti_dogrula.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cols_from_ai_tahmin() -> dict[str, list[str]]:
    tree = ast.parse((SCRIPTS / "ai_tahmin.py").read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("MATCH_COLS", "COUPON_COLS"):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _coupon_rows(mod, legs):
    rows = []
    for i, (name, odds, p) in enumerate(legs):
        r = {c: "" for c in mod.COUPON_COLS}
        r.update(tarih="2026-11-28", kupon="kupon_2.5x", kupon_no="1", mac=f"Ev{i} - Dep{i}", nesine_kodu=str(100 + i),
                 secim_adi=name, secim=name, nesine_oran=f"{odds:.2f}", olasilik=f"{p:.4f}")
        rows.append(r)
    return rows


def test_schema_matches_shared_ai_tahmin_columns():
    mod = _load()
    cols = _cols_from_ai_tahmin()
    assert mod.MATCH_COLS == cols["MATCH_COLS"]
    assert mod.COUPON_COLS == cols["COUPON_COLS"]


def test_clean_output_passes(tmp_path):
    mod = _load()
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS,
           _coupon_rows(mod, [("İY 1.5 Alt", 1.30, 0.80), ("MS 1", 1.35, 0.78), ("2Y KG Yok", 1.25, 0.82)]))
    _write(tmp_path / "mac_tahminleri.csv", mod.MATCH_COLS, [])
    rep = mod.validate_dir(tmp_path)
    assert rep["ok"], rep
    assert mod.main(["--klasor", str(tmp_path)]) == 0


def test_self_written_results_are_rejected(tmp_path):
    mod = _load()
    cols = [*mod.COUPON_COLS, "bacak_sonucu", "kupon_sonucu"]
    rows = _coupon_rows(mod, [("İY 1.5 Alt", 1.30, 0.80), ("MS 1", 1.35, 0.78)])
    for r in rows:
        r.update(bacak_sonucu="KAZANDI (2-0)", kupon_sonucu="KAZANDI")
    _write(tmp_path / "kuponlar.csv", cols, rows)
    rep = mod.validate_dir(tmp_path)
    assert not rep["ok"]
    assert any("kendi sonucunu yazma yasak" in e for e in rep["hatalar"])
    assert mod.main(["--klasor", str(tmp_path)]) == 1


def test_result_text_inside_allowed_column_is_rejected(tmp_path):
    mod = _load()
    rows = _coupon_rows(mod, [("İY 1.5 Alt", 1.30, 0.80), ("MS 1", 1.35, 0.78)])
    rows[0]["kupon_turu"] = "banko — TUTTU"
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS, rows)
    assert any("kendi sonucunu" in e for e in mod.validate_dir(tmp_path)["hatalar"])


def test_missing_shared_columns_rejected(tmp_path):
    mod = _load()
    _write(tmp_path / "kuponlar.csv", ["kupon_no", "mac", "tercih", "oran"],
           [{"kupon_no": "1", "mac": "A - B", "tercih": "MS 1", "oran": "1.40"}])
    rep = mod.validate_dir(tmp_path)
    assert any("sütun eksik" in e for e in rep["hatalar"])


def test_rule_violations_reported(tmp_path):
    mod = _load()
    legs = [("KG Var", 1.40, 0.80), ("MS X", 1.30, 0.80), ("MS 1", 2.10, 0.80), ("2.5 Alt", 1.30, 0.60),
            ("Ev İki Yarıda Gol Atamaz", 1.30, 0.80), ("İY/MS 1/1", 1.50, 0.80), ("Skor 1-0", 1.50, 0.80)]
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS, _coupon_rows(mod, legs))
    rep = mod.validate_dir(tmp_path)
    issues = " | ".join(rep["kuponlar"][0]["ihlaller"])
    for needle in ("KG", "beraberlik", "oran 2.10", "< %70", "takım golü", "İY/MS", "skor", "7 bacak"):
        assert needle in issues, needle


def test_single_leg_and_20_plus_total_rejected(tmp_path):
    mod = _load()
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS, _coupon_rows(mod, [("MS 1", 1.30, 0.80)]))
    assert any("1 bacak" in x for x in mod.validate_dir(tmp_path)["kuponlar"][0]["ihlaller"])
    six = [("2.5 Alt", 1.80, 0.90)] * 6
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS, _coupon_rows(mod, six))
    assert any("20+" in x for x in mod.validate_dir(tmp_path)["kuponlar"][0]["ihlaller"])


def test_same_match_twice_rejected(tmp_path):
    mod = _load()
    rows = _coupon_rows(mod, [("İY 1.5 Alt", 1.30, 0.80), ("MS 1", 1.35, 0.78)])
    rows[1]["nesine_kodu"] = rows[0]["nesine_kodu"]
    _write(tmp_path / "kuponlar.csv", mod.COUPON_COLS, rows)
    assert any("aynı maçtan" in x for x in mod.validate_dir(tmp_path)["kuponlar"][0]["ihlaller"])


def test_missing_dir_exit_code(tmp_path):
    mod = _load()
    assert mod.main(["--klasor", str(tmp_path / "yok")]) == 2
