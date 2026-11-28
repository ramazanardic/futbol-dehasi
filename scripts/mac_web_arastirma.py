"""Kupona aday maçlar için web-araştırma adımını bağımsız çalıştırır (günlük analiz ``nesine_global`` içinde de çağırır).

Kullanım:
  python scripts/mac_web_arastirma.py --tarih 2026-11-22 [--girdi tahminler/<ai>/2026-11-22/nesine_global.json]
         [--en-fazla 20] [--cikti reports/research/web_arastirma_2026-11-22.json]

Çıktı: aday maç başına ``research["web"]`` kaydı + kaynak/süre özeti (hangi siteden ne alındı, maç başı sn).
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantfoot.data import web_research as W


def _find(day: str) -> Path | None:
    c = sorted(ROOT.glob(f"tahminler/*/{day}/nesine_global.json"), key=lambda p: p.stat().st_mtime)
    return c[-1] if c else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tarih", required=True)
    ap.add_argument("--girdi")
    ap.add_argument("--en-fazla", type=int, default=20)
    ap.add_argument("--cikti")
    a = ap.parse_args()
    f = Path(a.girdi) if a.girdi else _find(a.tarih)
    if not f or not f.exists():
        sys.exit(f"{a.tarih} için nesine_global.json bulunamadı")
    data = json.loads(f.read_text(encoding="utf-8"))
    ms = data["matches"]
    t0 = time.time()
    s = W.attach(ms, dt.date.fromisoformat(a.tarih), max_matches=a.en_fazla, verbose=True, shield=False)
    webs = [(m, m["research"]["web"]) for m in ms if (m.get("research") or {}).get("web")]
    unk = collections.Counter(u.split(".", 1)[-1] for _, w in webs for u in w["bilinmiyor"])
    rep = {"tarih": a.tarih, "girdi": str(f), "ozet": s, "bilinmeyen_alan_sayisi": dict(unk),
           "toplam_sn": round(time.time() - t0, 1),
           "maclar": [{"kod": m["code"], "mac": f"{m['home']} - {m['away']}", "lig": m["league"], "web": w} for m, w in webs]}
    out = Path(a.cikti) if a.cikti else ROOT / "reports" / "research" / f"web_arastirma_{a.tarih}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"ozet": s, "bilinmeyen": dict(unk)}, ensure_ascii=False, indent=1))
    print("->", out)


if __name__ == "__main__":
    main()
