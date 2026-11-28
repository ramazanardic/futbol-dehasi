"""Son-120-gün takım formu agregatını yazar: data/form/takim_son120_form.csv (takım başına ortalama atılan/yenilen, ev/dep).

Ham maç satırları repoya konmaz (data/cache altında git-ignored); yalnız takım agregatı yazılır.
    python scripts/form_turet.py --tarih 2026-11-28
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data import recent_form as rf
from quantfoot.data import web_research as wr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tarih", required=True, help="maç günü (bu günden ÖNCEKİ 120 gün)")
    a = ap.parse_args()
    pool, st = wr.refresh_pool(a.tarih, wr.Http())
    rows = rf.summary_rows(pool, a.tarih)
    out = ROOT / "data" / "form" / "takim_son120_form.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} takım, havuz {len(pool)} maç, kaynak durumu {st} -> {out}")


if __name__ == "__main__":
    main()
