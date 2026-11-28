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

# Banko/garanti modu (kullanıcı kuralı t57u, 21 Kas; 21 Kas denetimiyle sıkılaştırıldı — strategy/banko_guard.py).
BANKO_MIN_PROB = 0.65          # ön süzgeç; banko kupon bacağı ayrıca coupon_rules ile düzeltilmiş P ≥ %70 (docs/ORTAK_SISTEM.md)
BANKO_MAX_LEG_ODDS = 1.80      # tek bir yüksek oranlı bacakla toplamı şişirme yok
BANKO_SELECT_MIN_ODDS = 1.22   # seçerken 1.20 tabanına tampon: 1.20–1.21'lik bacaklar oynarken 1.17–1.19'a düştü
BANKO_MAX_COUPONS_PER_MATCH = 2  # aynı maç en çok 2 açık kuponda (korelasyonlu risk)
LOTTERY_P_WIN = 0.05           # P(kupon) bunun altındaysa "piyango kuponu" uyarısı (banko modunda reddedilir)
BANKO_PREFER_MIN_ODDS = 1.25   # kurarken tercih edilen en düşük oran (oynayana kadar oran kayması tamponu)
BANKO_MIN_LEGS = 2             # Ramazan'ın kuralı (kural onarımı 28 Kas): banko kupon 2–5 bacak; kurulamazsa dürüst ret
BANKO_MAX_LEGS = 5             # varsayılan üst sınır (açıkça istenirse 6: BANKO_HARD_MAX_LEGS)
BANKO_HARD_MAX_LEGS = 6        # banko kupon hiçbir koşulda 6 bacağı aşmaz
BANKO_MAX_TOTAL_ODDS = 20.0    # banko kupon toplam oranı 20'nin altında kalır (20+ "loto" kupon varsayılan olarak yok)
# Akşam denetimi dersleri (21 Kas 2026, ~320 bitmiş maç, TEK GÜN — küçük örnek; bkz. reports/research/kalibrasyon_dersleri_21kasim.md).
# Ana tercihler %67 beklenip %63,4 tuttu; %60–65 bandı %50, %70–75 bandı %64; "diğer" ligler %59,5 (P %66,7);
# ev sahibi golleri %49 (P %67), çifte şans %50 (P %65,5); Alt/Üst kalibre. Değerler bilinçli olarak ılımlı.
# 21 Kas GECE hata analizi (reports/research/hata_analizi_21kasim.md; 19 + 21 Kas canlı, 2.719 türetilmiş seçim + arşiv):
# türetilmiş P'nin iyimserliği pazara değil LİGE bağlı — arşiv kalibrasyon alanındaki liglerde (market_calibration
# NESINE_TO_DIVISION) kalibre (arşiv artığı ≈ 0; canlı n=778 en iyi k = 0,005), alan dışında iki bağımsız günde de
# k = 0,147 / 0,148. Pazar başına canlı sapmalar günden güne tutarsız (korelasyon ≈ 0, EB τ = 0) → pazar düzeltmesi yok.
SHRINK_DERIVED = 0.15          # türetilmiş P, lig arşiv kalibrasyon alanı DIŞINDA (ya da lig bilinmiyor): p' = 0.5 + (p − 0.5)·(1 − k)
SHRINK_DERIVED_IN_DOMAIN = 0.0  # türetilmiş P, lig arşiv kalibrasyon alanında (Platt eğrileri orada sınandı) — büzme yok
SHRINK_DIRECT = 0.0            # doğrudan keskin fiyatlı seçimler piyasa P'si zaten — büzme yok (canlı: k = −0,035)
SHRINK_OTHER_TIER_EXTRA = 0.05  # "2-diğer" kademe ek büzme (türetilmişte birikerek → toplam ≈ 0,19, eskisiyle aynı; doğrudanda yarısı)
SHRINK_UNTESTED_MARKET_EXTRA = 0.15  # arşivde sınanamayan pazar (İlk Gol, "İY KG Yok & 2Y KG Yok" …) türetilmiş P'sine ek büzme
UNTESTED_MARKET_P_LOW_PENALTY = 0.0  # kurucularda sıralama için ek p_low cezası (P'ye yansıyan büzme zaten sıralamaya girer)
WEAK_FAMILIES: tuple[str, ...] = ("ev_golleri", "cifte_sans")  # banko'da yalnız doğrudan keskin fiyatla + ek P
WEAK_FAMILY_EXTRA_MIN_PROB = 0.05  # zayıf aile doğrudan fiyatlıysa banko P tabanı + 5 puan (%70)
WEAK_FAMILY_REQUIRE_DIRECT = True  # zayıf aile türetilmiş P ile banko bacağı olamaz
# 21 Kas gece hata analizi (arsiv_kod/hata_analizi_21kasim.py; reports/research/hata_analizi_21kasim.md). Yalnız arşivde
# (2011/12–2020/21 eğitim, 2021/22+ test) doğrulanan dersler; tek günün pazar sapmalarının çoğu arşivde gürültü çıktı.
TAIL_CALIBRATION_ON = True     # data/calibration/market_tail_calibration.json: banko bölgesi (P .55–.90) logit kaymaları
UNTESTED_MARKET_SHRINK = 0.05  # arşivde sınanamayan TÜRETİLMİŞ pazarlara (İlk Gol, yarı KG kombineleri…) ek büzme
BANKO_DRAW_RISK_MAX = 0.27     # banko MS 1/MS 2 bacağı: beraberlik riski ≥ bu → ret (ÇŞ / Hnd(+1) önerilir)
BANKO_DRAW_RISK_WARN = 0.24    # ≥ bu → uyarı (düşük toplamlı maçta favori; ÇŞ/handikap daha güvenli)
DRAW_ZONE_MAX_OVER25 = 0.45    # P(2.5 Üst) bunun altı = arşivde beraberliğin piyasadan fazla geldiği bölge (+1.6 puan)
DRAW_PICK_MIN_P = 0.28         # risk modu MS 0 seçimi: piyasa beraberlik P tabanı
DRAW_PICK_MIN_EV = 0.03        # risk modu MS 0 seçimi: risk P'siyle EV tabanı (Nesine payı yüzünden çoğu ret)
# Yüksek oranlı pazarlar (İY/MS, İY/2Y sonucu, iki yarıda KG, skor) — "yuksek_oran" modu (kullanıcı t100u, 21 Kas).
HIGH_ODDS_MAX_MODEL_SHARP_GAP = 0.15  # keskin fiyat varsa |model − keskin| / keskin ≤ %15
HIGH_ODDS_NO_SHARP_HAIRCUT = 0.10     # keskin fiyat yoksa model P × 0.90 (yalnız arşivde sınanmış pazar)
HIGH_ODDS_MIN_EV = 0.06               # EV tabanı (aile tabanıyla büyüğü); Nesine ödemesi İY/MS'te ≈ .75
HIGH_ODDS_MAX_ODDS = 15.0             # üstü piyango sayılır
HIGH_ODDS_MAX_LEGS = 2                # bu modda kupon en çok 2 maç (tekli tercih edilir)
# Risk modu: yalnız kullanıcı banko ile ulaşılamayan bir hedef (ör. "en az 2.000 TL") isterse.
RISK_MAX_LEG_ODDS = 2.10       # tek bacak en çok 2.10 (3–4 oranlı beraberlik/İY bacakları yok)
RISK_MIN_PROB = 0.45           # bacak başı keskin P tabanı
RISK_MIN_LEGS = 3
RISK_MAX_LEGS = 6
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
    "Korner": (0.05, 0.015),      # exchange quote, or the walk-forward corner model (markets/korner_banko.py, banko)
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

# GLOBAL FOOTBALL INTELLIGENCE türetilmiş öncülleri (data/gfi/, scripts/gfi_turet.py). 18–28 Kas denetim seçimlerinde
# zaman sızıntısız ölçüm (reports/research/gfi_etki_2026-11-28.md) iyileşme göstermedikçe KAPALI. Ortam değişkeni
# QF_GFI_PRIORS=1 ile açılır.
GFI_PRIORS_ENABLED = False

# Toplam korner Alt/Üst banko ailesi (28 Kas 2026, t179u). Model: markets/korner_banko.py; kalibrasyon ve geçerli
# (çizgi, yön) listesi data/calibration/korner_kalibrasyon.json (scripts/korner_olcum.py). Ölçümde P ≥ 0,70 diliminde
# gerçekleşme tahminden en çok 5 puan düşük olmak zorunda; değilse dosyada etkin=false ve bayrak ne olursa olsun
# bacak çıkmaz. QF_KORNER_BANKO=0 ile kapanır.
KORNER_BANKO_ENABLED = True


# Maç başına web-araştırma adımı (data/web_research.py): kupona aday maçlar için ESPN/Open Matchday/FPL/Wikipedia'dan
# form, puan durumu, xG, sakat/cezalı, ilk 11, hoca değişikliği. YALNIZ bilgi kaydı (research["web"]) yazar; olasılığa
# ve kupon uygunluğuna dokunmaz. Kalkan etkisi FREE_ABSENCES_ENABLED'e bağlıdır. QF_WEB_RESEARCH=0 ile kapanır.
WEB_RESEARCH_ENABLED = True
# API-Football /injuries?date= günde 1 istek (kota: api_budget). Varsayılan kapalı; QF_WEB_AF=1 ile açılır.
WEB_RESEARCH_AF = False

# Ücretsiz kaynaklardan (FPL / API-Football / ESPN ilk 11) sakat-kadro verisinin banko kalkanına (tm_absences yedeği)
# girmesi. 18–28 Kas ölçümü kanıt vermediği için varsayılan KAPALI; QF_FREE_ABSENCES=1 ile açılır.
FREE_ABSENCES_ENABLED = False

# Son-120-gün takım formu öncülü (markets/form_priors.py): gol aileleri için 0.6·P + 0.4·öncül. Ölçüm anlamlı kazanç
# göstermediği için varsayılan KAPALI; QF_RECENT_FORM=1 ile açılır (QF_RECENT_FORM_XG=1: xG vekili).
RECENT_FORM_ENABLED = False
