"""Shared operational thresholds and paths for QuantFoot daily / Nesine flows.

Backtest research defaults (e.g. min_ev=0.015 in walk-forward studies) stay in
evaluation.backtest so historical numbers are not silently rewritten.
"""

from __future__ import annotations

import datetime as dt

# Europe/Istanbul has been permanently UTC+3 since 2016 (no DST).
TSI = dt.timezone(dt.timedelta(hours=3))

# Official Nesine coupon rules (tahminler/README.md, 20 Nov 2026).
MIN_LEG_ODDS = 1.20
MAX_LEGS = 7
MAX_LEGS_HIGH = 8
HIGH_TARGET = 20.0
STANDARD_COUPON_TARGETS: tuple[float, ...] = (5.0, 10.0, 20.0, 30.0, 50.0)
MIN_LEG_PROB_OPTIMUM = 0.55
MIN_LEG_PROB_SAFE = 0.60

# ESPN/model-only daily.py coupon scanner (NOT the official Nesine coupon).
# These legs are fitted to the same book's odds; they are not a betting edge.
MODEL_ONLY_MIN_EV = 0.02
MODEL_ONLY_TARGETS: tuple[float, ...] = (3.0, 5.0, 10.0)
MODEL_ONLY_MAX_LEGS = 4

# Global reference age. Analysis may still *price* older snapshots (clearly marked).
# Anything betting-related (coupons, official picks) must not use prices older than this.
MAX_PRICE_AGE_H = 3.0
# How old a references.json snapshot may be before global_references() drops it
# entirely (analysis can pass a larger cap to still render a report).
REFERENCE_LOAD_AGE_H = 30.0

# Selections with EV above this are listed as "reference error suspected", never as tips.
MAX_PLAUSIBLE_EV = 0.25

# Main pick of a match (derin_tahmin.choose / simulasyon.update_picks): value, not just probability.
# A pick needs calibrated EV = p × Nesine odds − 1 ≥ this; evidence verdicts only FILTER (⚠ / not triple-confirmed).
PICK_MIN_EV = 0.02

# "Hard" markets the user lost most on (21 Nov post-mortem: Üst 2.5/3.5, KG Var, weak-favourite MS 1, İY/MS).
# Not banned: they enter a coupon only with a larger margin over the calibrated global fair price.
HARD_MARKET_MIN_EV = 0.03
HARD_MARKET_SIGMA_ADD = 0.010

# Score-matrix margin tilt applied before raking onto the quotes (tail_goals.rake_score_matrix_to_markets): the raked
# joint over-priced big wins (Fark Ev 3+ 0.104 vs 0.094 realised, Fark Ev 1 0.205 vs 0.219). θ chosen on seasons
# < 2016/17 only (12k-match grid {0, .05, .1, .15, .2, .3, .4}: margin-bucket LL best at .05); test 2016/17+ (77,503
# matches) vs raking alone: 44 selections better / 9 worse / 68 unchanged (Hnd(-1) 1 ΔLL −0.00065 CI [−0.00079,
# −0.00051]); reports/research/bahis_aileleri_karsilastirma_uretim_fark0.05.json.
MARGIN_TILT = 0.05

# Per bet-family value rules (21 Nov bet-family audit; docs/research/bahis_aileleri_2026_11_21.md,
# reports/research/bahis_aileleri_kalibrasyon.json). family -> (minimum calibrated EV, extra σ on the leg probability).
# Coupon legs (nesine_kupon.candidates): every leg gets σ + family σ (+ the hard-market σ); a MODEL-DERIVED leg (no
# direct global quote) needs EV >= max(family floor, HARD_MARKET_MIN_EV if hard); a directly quoted leg keeps the PR #3
# rule (EV floor only on hard markets). Main picks (derin_tahmin / simulasyon) need EV >= max(PICK_MIN_EV, family
# floor). quantfoot.markets.families maps a selection name to its family.
# Floors grow with (a) the family's residual out-of-sample miscalibration after raking + Platt and (b) its payout
# variance (long odds need a bigger margin before the edge is distinguishable from noise):
#   - archive best-price test: MS / 2.5 Üst only turned reliably positive at EV >= 3 % (2.5 Üst: +12 %, CI [+0.5, +24]);
#   - raw derived Asian handicap LOST at every EV threshold (-4.8 % at EV >= 0, CI [-6.9, -2.9]) -> handicap/margin
#     families need calibration AND a larger floor; correct score / HT-FT / margin are long-odds families.
FAMILY_VALUE_RULES: dict[str, tuple[float, float]] = {
    "Maç Sonucu": (0.03, 0.000),
    "Çifte Şans": (0.02, 0.000),
    "Alt/Üst": (0.03, 0.000),
    "Karşılıklı Gol": (0.03, 0.000),
    "Takım Golleri": (0.03, 0.000),
    "Toplam Gol Aralığı": (0.04, 0.005),
    "İY Sonucu": (0.04, 0.005),
    "İY Alt/Üst": (0.04, 0.005),
    "2Y Sonucu": (0.04, 0.005),
    "2Y Alt/Üst": (0.04, 0.005),
    "Yarı KG": (0.04, 0.005),
    "Yarı Özel": (0.04, 0.005),
    "Tek/Çift": (0.04, 0.005),
    "Handikap": (0.05, 0.005),
    "Kombine": (0.05, 0.010),
    "İlk Gol": (0.05, 0.010),     # not testable on the archive (no first-goal team)
    "İY/MS": (0.06, 0.010),
    "Fark": (0.06, 0.010),
    "Doğru Skor": (0.08, 0.010),
    "Korner": (0.05, 0.015),      # priced only from a direct exchange quote (no corner odds in the archive)
    "Kart": (0.05, 0.015),        # idem
    "Diğer": (0.05, 0.010),
}

# Kasa / pay politikası (kullanıcı kararı, 21 Kasım: %2 / %6 çok düşük bulundu). Hepsi CLI ile değiştirilebilir:
# scripts/kupon_politikasi.py --kasa 250 --gunluk-limit-oran 1.0 --kupon-limit-oran 0.2
STAKE_DAILY_FRAC = 1.0      # gün içinde +EV kuponlara dağıtılabilecek en çok kasa oranı
STAKE_COUPON_FRAC = 0.2     # tek kupona en çok kasa oranı (250 TL → 50 TL)
STAKE_STEP_TL = 5.0         # paylar 5 TL'nin katı
MIN_STAKE_TL = 5.0          # Nesine'nin resmî asgari kupon tutarı doğrulanmadı; güvenli varsayım 5 TL
MIN_COUPON_EV = 0.02        # kupon EV eşiği (her bacak ayrıca EV ≥ 0 olmalı)
KELLY_MULTIPLIER = 0.25
LIVE_MIN_EV = 0.05          # canlı fırsat eşiği (model belirsizliği yüksek)
LIVE_RESERVE_TL = 0.0       # canlı için ayrılan kasa (CLI --canli-rezerv)
