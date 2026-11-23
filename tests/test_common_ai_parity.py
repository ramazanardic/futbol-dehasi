"""Tüm 5 yapay zekânın aynı ortak sistemden, eşit koşullarla ve eşgüdümlü kurallarla çalıştığını doğrulayan CI koruma testleri."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import gunluk_tahmin as G  # noqa: E402
from quantfoot.coupons.coupon_rules import leg_decision  # noqa: E402
from quantfoot.data import fotmob, understat  # noqa: E402
from quantfoot.markets.market_diagnosis import diagnose_selection  # noqa: E402
from quantfoot.paths import VALID_AIS  # noqa: E402


def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def test_all_ai_instruction_files_point_to_the_shared_contract():
    """Her giriş kendi konumundan aynı bağlayıcı kurallara bağlanır."""
    agents = _norm((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    assert "docs/ORTAK_SISTEM.md" in agents
    assert "scripts/gunluk_tahmin.py" in agents
    assert "scripts/kasa_koruma.py" in agents
    assert "scripts/oz_gelistirme.py" in agents
    assert "scripts/gun_degerlendirme.py" in agents

    for rel in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md"):
        body = _norm((ROOT / rel).read_text(encoding="utf-8"))
        assert "\t" not in body, f"{rel} içinde bozuk sekme (tab) karakteri var!"
        prefix = "../" if rel.startswith(".github/") else ""
        assert f"]({prefix}AGENTS.md)" in body
        assert f"]({prefix}docs/ORTAK_SISTEM.md)" in body


def test_all_five_ais_have_equal_data_access_and_identical_pipeline(monkeypatch):
    """5 yapay zekânın tamamı FotMob, ortak boru hattı ve v3 karar motorunda birebir eşit davranır."""
    assert VALID_AIS == frozenset({
        "claudetahmin",
        "geminitahmin",
        "antigravitytahmin",
        "chatgbttahmin",
        "grokbottahmin",
    })

    sample_ctx = {
        "name": "İY 1.5 Alt",
        "odds": 1.30,
        "p": 0.76,
        "mu_home": 1.15,
        "mu_away": 0.85,
        "reference": "Pinnacle",
        "direct": True,
        "league": "İspanya La Liga",
        "flags": [],
    }
    expected_cmds = G.step_commands("2026-11-23", [2.5], py="py")
    expected_diag = diagnose_selection("İY 1.5 Alt", 0.76, sample_ctx, for_coupon=True)
    expected_dec = leg_decision(sample_ctx)

    for ai in sorted(VALID_AIS):
        monkeypatch.setenv("QUANTFOOT_AI", ai)
        assert fotmob.enabled() is True
        assert G.step_commands("2026-11-23", [2.5], py="py") == expected_cmds
        assert G.main(["--kuru", "--ai", ai, "--tarih", "2026-11-23"]) == 0
        assert diagnose_selection("İY 1.5 Alt", 0.76, sample_ctx, for_coupon=True) == expected_diag
        assert leg_decision(sample_ctx) == expected_dec


def test_no_single_ai_privilege_or_branded_user_agent_in_core_src():
    """Ortak src/quantfoot çekirdeğinde tek bir AI'ya özel User-Agent veya ayrıcalık kilidi bulunmamalıdır."""
    assert "GrokBot" not in fotmob.UA["User-Agent"]
    assert "GrokBot" not in understat.UA["User-Agent"]
    for py_file in sorted((ROOT / "src" / "quantfoot").rglob("*.py")):
        if py_file.name == "paths.py" or "__pycache__" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8")
        for ai in VALID_AIS:
            assert f'"{ai}"' not in text and f"'{ai}'" not in text, (
                f"{py_file.relative_to(ROOT)} içinde tek bir AI ({ai}) sabit kodlanmış!"
            )


def test_gunluk_tahmin_audit_reports_portfolio_exposure_guard():
    """audit_coupons tüm AI'lar için çapraz kupon portföy yoğunlaşmasını da raporlar."""
    rows = [
        {"kupon": "k1", "kupon_no": 1, "mac": f"Ev{i} - Dep{i}", "nesine_kodu": str(i),
         "secim_adi": "İY 0.5 Üst", "secim": "İY 0.5 Üst", "nesine_oran": "1.25", "olasilik": "0.80"}
        for i in range(5)
    ] + [
        {"kupon": "k2", "kupon_no": 1, "mac": f"Ev{i} - Dep{i}", "nesine_kodu": str(i),
         "secim_adi": "3.5 Alt" if i == 0 else "İY 0.5 Üst",
         "secim": "3.5 Alt" if i == 0 else "İY 0.5 Üst", "nesine_oran": "1.25", "olasilik": "0.80"}
        for i in (0, 10, 11, 12, 13)
    ]
    audit = G.audit_coupons(rows)
    assert audit["ok"]  # farklı tercih olduğu için bacak kuralı geçer
    port = audit["portfolio"]
    assert port["n_coupons"] == 2
    assert not port["ok"]  # maç 0 iki kuponda birden yer aldığı için portföy uyarısı verir
    assert port["concentration_score"] == 100.0
    md = G.audit_markdown("2026-11-23", "antigravitytahmin", audit)
    assert "Çapraz Kupon Portföy Yoğunlaşması" in md
