#!/usr/bin/env python3
"""v2 aşama 1: taze analiz (canlı OddsMath keskin referans) + Nesine bülten oranları -> /tmp pickle."""
import datetime as dt, pickle, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kupon_10x_sec as K
ng, nk = K.ng, K.nk
now = dt.datetime.now(K.TSI)
ng.global_references = K._fresh_global_references
matches, payload, events = ng.analyze_day(dt.date.fromisoformat(K.DATE), verbose=False, use_oddsmath=True, use_tm=False, use_weather=True)
live, flicker = nk.read_bulletin_odds()
nk.apply_live_odds(matches, live)
pickle.dump({"now": now, "matches": matches, "live": live, "flicker": flicker,
             "priced": {k: v for k, v in getattr(ng, "PRICED", {}).items()}}, open("/tmp/k10v2.pkl", "wb"))
print("ok", now, len(matches), sum(1 for m in matches if m.get("status") == "fiyatlandı"), dt.datetime.now(K.TSI))
