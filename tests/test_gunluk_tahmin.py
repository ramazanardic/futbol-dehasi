"""Ortak sistem giriş komutu (scripts/gunluk_tahmin.py) ve kupon kural denetimi."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gunluk_tahmin as G  # noqa: E402


def _leg(code, name, odds=1.25, p=0.80, kupon="kupon_3x_2200", no=1):
    return {"kupon": kupon, "kupon_no": no, "mac": f"Ev{code} - Dep{code}", "nesine_kodu": str(code),
            "secim_adi": name, "secim": name, "nesine_oran": str(odds), "olasilik": str(p)}


def test_step_order_and_banko_mode():
    cmds = G.step_commands("2026-11-22", [3.0, 4.0], py="py")
    assert list(cmds) == list(G.STEPS)
    assert cmds["bulten"][0][1].endswith("nesine_global.py")
    assert cmds["tahmin"][0][1].endswith("ai_tahmin.py")
    assert cmds["derin"][0][1].endswith("derin_tahmin.py")
    assert len(cmds["kupon"]) == 2
    assert all("--mod" in c and c[c.index("--mod") + 1] == "banko" for c in cmds["kupon"])


def test_clean_five_leg_coupon_passes_and_reports_probability():
    rows = [_leg(i, "İY 0.5 Üst") for i in range(5)]
    audit = G.audit_coupons(rows)
    assert audit["ok"], audit
    c = audit["coupons"][0]
    assert c["bacak"] == 5
    assert abs(c["toplam_oran"] - 1.25 ** 5) < 0.01
    assert 0 < c["tutma_olasiligi"] <= 0.80 ** 5 + 1e-4


def test_banned_and_weak_legs_are_flagged():
    rows = [_leg(0, "MS 0", odds=3.2, p=0.30), _leg(1, "KG Var", p=0.75), _leg(2, "İY 0.5 Üst", p=0.60),
            _leg(3, "İY 0.5 Üst", odds=1.10), _leg(4, "İY 0.5 Üst")]
    audit = G.audit_coupons(rows)
    assert not audit["ok"]
    text = " | ".join(audit["coupons"][0]["ihlaller"])
    assert "beraberlik" in text
    assert "Karşılıklı gol" in text
    assert "düzeltilmiş P" in text
    assert "1.10" in text


def test_leg_count_same_match_and_reuse_across_coupons():
    too_many = [_leg(i, "İY 0.5 Üst", kupon="a") for i in range(7)]
    audit = G.audit_coupons(too_many)
    assert any("bacak" in x for x in audit["coupons"][0]["ihlaller"])
    same_match = [_leg(0, "İY 0.5 Üst", kupon="b"), _leg(0, "1.5 Üst", kupon="b")] + \
                 [_leg(i, "İY 0.5 Üst", kupon="b") for i in range(1, 4)]
    assert any("aynı maçtan" in x for x in G.audit_coupons(same_match)["coupons"][0]["ihlaller"])
    reuse = [_leg(i, "İY 0.5 Üst", kupon="c") for i in range(5)] + \
            [_leg(i, "İY 0.5 Üst", kupon="d") for i in range(4, 9)]
    a = G.audit_coupons(reuse)
    assert not a["ok"]
    assert any("aynı tercih" in x for c in a["coupons"] for x in c["ihlaller"])


def test_requires_valid_ai(monkeypatch, capsys):
    monkeypatch.delenv("QUANTFOOT_AI", raising=False)
    assert G.main(["--kuru"]) == 2
    assert G.main(["--kuru", "--ai", "grokbottahmin", "--tarih", "2026-11-22"]) == 0
    out = capsys.readouterr().out
    assert "kupon_kur.py" in out and "nesine_global.py" in out


def test_audit_writes_report_only_in_own_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "ROOT", tmp_path)
    day = tmp_path / "tahminler" / "grokbottahmin" / "2026-11-22"
    day.mkdir(parents=True)
    import csv
    with (day / "kuponlar.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        rows = [_leg(i, "İY 0.5 Üst") for i in range(5)]
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    audit = G.run_audit("2026-11-22", "grokbottahmin")
    assert audit["ok"]
    md = (day / "kupon_denetim.md").read_text(encoding="utf-8")
    assert "UYGUN" in md and "tutma olasılığı" in md
    assert [p.name for p in (tmp_path / "tahminler").iterdir()] == ["grokbottahmin"]


def test_failed_steps_do_not_report_success(tmp_path, monkeypatch):
    from subprocess import CompletedProcess
    monkeypatch.setattr(G, "ROOT", tmp_path)
    monkeypatch.setattr(G.subprocess, "run", lambda cmd, **kw: CompletedProcess(cmd, 7))
    args = ["--ai", "chatgbttahmin", "--tarih", "2026-11-21", "--yalniz"]
    for step in ["derin", "kupon"]:
        assert G.main(args + [step, "denetim"]) == 7
    assert G.main(args + ["denetim"]) != 0


def test_midnight_coupon_export_and_probability_match_audit(tmp_path):
    import json
    import ai_tahmin
    import nesine_kupon

    day = tmp_path / "2026-11-21"
    day.mkdir()
    legs = [dict(code=i, name="1.5 Üst", odds=1.25, p=.76, mbs=1, market="Alt/Üst",
                 selection="Üst", match=f"A{i}-B{i}", kickoff="2026-11-22 02:00") for i in range(1, 6)]
    pools = nesine_kupon.apply_coupon_rules_to_pools([[leg] for leg in legs])
    coupon = nesine_kupon._summary([pool[0] for pool in pools])
    for stamp in ["2350", "0010"]:
        (day / f"kupon_2.5x_{stamp}.json").write_text(json.dumps({"coupons": [coupon]}))
    rows = ai_tahmin.coupon_rows(day.name, tmp_path)
    assert len(rows) == 5 and all(row["kupon"].endswith("0010") for row in rows)
    audit = G.audit_coupons(rows)
    assert audit["ok"]
    assert audit["coupons"][0]["tutma_olasiligi"] == float(rows[0]["kupon_tutma_olasiligi"]) == .2409
