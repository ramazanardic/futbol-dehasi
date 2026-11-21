"""Tam maç dosyası: oran dışı her şey (eksikler, dinlenme/yoğunluk, form, karşılaşma geçmişi, keskin piyasa
ve hareketi, hava, hakem, ilk 11). Ayrıntı: src/quantfoot/data/match_dossier.py

    QUANTFOOT_AI=grokbottahmin python scripts/tam_analiz.py --ev "Manchester City" --dep "Fulham"
    python scripts/tam_analiz.py --tarih 2026-11-21 --ev Alaves --dep "La Coruna" --gecmis-yok   # kota tasarrufu

Çıktı: tahminler/<QUANTFOOT_AI>/<tarih>/mac_dosyalari_tam/<ev>-<dep>.md (+ .json) ve ekrana.
İlk çalıştırmada son 14 + sonraki 4 günün fikstürü çekilir (≈19 API-Football isteği, sonra önbellekten);
maç başına ek ≈3 istek (sakat, form, oran).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from quantfoot.data.match_dossier import ApiFootball, CachedHttp, build_dossier, render_markdown  # noqa: E402
from quantfoot.paths import ai_area  # noqa: E402
from quantfoot.settings import TSI  # noqa: E402


def _load_env() -> None:
    for env in (ROOT / ".env", Path("/workspace/futbol-dehasi/.env")):
        if env.exists():
            for line in env.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))
            return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tarih", default=dt.datetime.now(TSI).date().isoformat())
    ap.add_argument("--ev", required=True)
    ap.add_argument("--dep", required=True)
    ap.add_argument("--gecmis-yok", action="store_true", help="dinlenme/yoğunluk için ek fikstür günü çekme")
    ap.add_argument("--kota", type=int, default=90, help="API-Football günlük koruma sınırı")
    args = ap.parse_args()
    _load_env()
    area = ai_area()
    http = CachedHttp()
    d = build_dossier(dt.date.fromisoformat(args.tarih), args.ev, args.dep, http=http,
                      api=ApiFootball(http, daily_limit=args.kota), fetch_history=not args.gecmis_yok)
    md = render_markdown(d)
    out = area / args.tarih / "mac_dosyalari_tam"
    out.mkdir(parents=True, exist_ok=True)
    folded = unicodedata.normalize("NFKD", f"{args.ev}-{args.dep}".replace("ı", "i")).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    (out / f"{slug}.md").write_text(md)
    (out / f"{slug}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str))
    print(md)
    print(f"→ {out / (slug + '.md')}")


if __name__ == "__main__":
    main()
