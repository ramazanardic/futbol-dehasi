"""Öz-geliştirme ve kalibrasyon denetçisi (self_improve) birim testleri."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from quantfoot.evaluation.self_improve import render_markdown, run_self_audit, write_self_audit


def _make_match(
    code: int,
    *,
    flags: list[str] | None = None,
    selections: list[dict],
    mu_home: float = 1.40,
    mu_away: float = 1.00,
    league: str = "İspanya La Liga",
) -> dict:
    return {
        "code": code,
        "match": f"Ev{code} - Dep{code}",
        "league": league,
        "status": "fiyatlandı",
        "reference": "Pinnacle",
        "mu_home": mu_home,
        "mu_away": mu_away,
        "fair_1x2": [0.48, 0.27, 0.25],
        "research": {"flags": flags or []},
        "selections": selections,
    }


def test_self_audit_aggregates_multiday_residuals_steam_and_diagnosis_buckets(tmp_path: Path):
    ai_dir = tmp_path / "tahminler" / "antigravitytahmin"
    day1 = ai_dir / "2026-11-21"
    day2 = ai_dir / "2026-11-22"
    day1.mkdir(parents=True)
    day2.mkdir(parents=True)

    # 10 maç: İY ÇŞ 12 sürekli yatıyor (0-0 İY -> toxic alarm), Dep 1.5 Alt sürekli tutuyor (golden pool)
    # 4 maçta sert steam altında MS 1 yatıyor, 4 maçta steam yokken MS 1 tutuyor
    d1_matches = []
    d2_matches = []
    results = {}

    for i in range(1, 7):
        code = 1000 + i
        d1_matches.append(_make_match(
            code,
            flags=["keskin steam +6.8p"] if i <= 3 else [],
            mu_home=1.80,
            mu_away=0.80,
            selections=[
                {"name": "İY ÇŞ 12", "odds": 1.45, "fair_prob": 0.65, "direct": False},
                {"name": "Dep 1.5 Alt", "odds": 1.28, "fair_prob": 0.66, "direct": False},
                {"name": "MS 1", "odds": 1.40, "fair_prob": 0.68, "direct": True},
            ],
        ))
        # i<=3 (sert steam): 0-1 biter (MS 1 yatar, İY 0-0 İY ÇŞ 12 yatar, Dep 1.5 Alt tutar)
        # i>3 (steam yok): 2-0 biter (MS 1 tutar, İY 0-0 İY ÇŞ 12 yatar, Dep 1.5 Alt tutar)
        results[code] = {"completed": True, "ht": [0, 0], "ft90": [0, 1] if i <= 3 else [2, 0]}

    for i in range(1, 5):
        code = 2000 + i
        d2_matches.append(_make_match(
            code,
            flags=[],
            mu_home=1.50,
            mu_away=0.85,
            selections=[
                {"name": "İY ÇŞ 12", "odds": 1.48, "fair_prob": 0.64, "direct": False},
                {"name": "Dep 1.5 Alt", "odds": 1.30, "fair_prob": 0.65, "direct": False},
            ],
        ))
        results[code] = {"completed": True, "ht": [0, 0], "ft90": [1, 0]}

    (day1 / "nesine_global.json").write_text(json.dumps({"matches": d1_matches}), encoding="utf-8")
    (day2 / "nesine_global.json").write_text(json.dumps({"matches": d2_matches}), encoding="utf-8")

    # mac_tahminleri.csv (2 ana tahmin)
    with (day2 / "mac_tahminleri.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["nesine_kodu", "secim_adi", "olasilik", "nesine_oran"])
        w.writeheader()
        w.writerow({"nesine_kodu": "2001", "secim_adi": "Dep 1.5 Alt", "olasilik": "0.72", "nesine_oran": "1.30"})
        w.writerow({"nesine_kodu": "2002", "secim_adi": "İY ÇŞ 12", "olasilik": "0.65", "nesine_oran": "1.48"})

    report = run_self_audit(ai_dir, results_by_code=results, min_n=6)
    assert report["ai"] == "antigravitytahmin"
    assert report["dates"] == ["2026-11-21", "2026-11-22"]
    assert report["settled_matches"] == 10

    # Altın havuz & Zehirli alarm doğru ayrışır
    golden_names = {x["selection"] for x in report["golden_pools"]}
    toxic_names = {x["selection"] for x in report["toxic_alarms"]}
    assert "Dep 1.5 Alt" in golden_names
    assert "İY ÇŞ 12" in toxic_names

    # Steam kırılımı: MS 1 steam yok %100, sert steam %0
    sm = report["by_steam_market"]
    assert sm["MS 1/2 | steam_yok (<3p)"]["hit_rate"] == 1.0
    assert sm["MS 1/2 | sert_steam (>=6p)"]["hit_rate"] == 0.0

    # market_diagnosis v3 ayrıştırması: REHAB/OK > TUZAK_RED
    diag = report["by_diagnosis_v3"]
    assert diag["REHAB"]["hit_rate"] > diag["TUZAK_RED"]["hit_rate"] + 0.50

    # Ana tahminler 1/2 (%50)
    assert report["main_picks"]["hits"] == 1 and report["main_picks"]["n"] == 2

    md = render_markdown(report)
    assert "İY ÇŞ 12" in md and "Dep 1.5 Alt" in md


def test_self_audit_strictly_isolates_active_ai_folder(tmp_path: Path):
    # Kardeş AI klasöründe zehirli/farklı veri olsa bile run_self_audit ona ASLA dokunmaz
    own_dir = tmp_path / "tahminler" / "antigravitytahmin" / "2026-11-22"
    other_dir = tmp_path / "tahminler" / "claudetahmin" / "2026-11-22"
    own_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)

    own_m = [_make_match(5001, selections=[{"name": "3.5 Alt", "odds": 1.30, "fair_prob": 0.72, "direct": True}])]
    other_m = [_make_match(9999, selections=[{"name": "MS 2", "odds": 2.10, "fair_prob": 0.65, "direct": True}])]
    (own_dir / "nesine_global.json").write_text(json.dumps({"matches": own_m}), encoding="utf-8")
    (other_dir / "nesine_global.json").write_text(json.dumps({"matches": other_m}), encoding="utf-8")

    results = {
        5001: {"completed": True, "ht": [0, 0], "ft90": [1, 0]},
        9999: {"completed": True, "ht": [2, 0], "ft90": [3, 0]},
    }
    report, md_path, json_path = write_self_audit(own_dir.parent, results_by_code=results, min_n=1)
    assert report["settled_matches"] == 1
    assert "3.5 Alt" in report["by_selection"]
    assert "MS 2" not in report["by_selection"]
    assert md_path.exists() and json_path.exists()
