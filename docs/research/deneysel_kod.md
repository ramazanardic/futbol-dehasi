# Deneysel / geri alınmış kod — 22 Kasım 2026 denetimi

Bu not, üretim fiyatlamasına **girmeyen** ya da arşivde sınanıp **geri alınan** parçaları kayıt altına alır.
Test komutu: `python scripts/pazar_kalibrasyonu.py analiz` → `reports/research/pazar_kalibrasyonu.md`
(walk-forward, 2016+ sezonları, 77 519 test maçı; karar kuralı: log-loss farkının %95 bootstrap güven aralığının
tamamı 0'ın altında değilse değişiklik tutulmaz).

## 1. `scripts/quantfoot_v82_multi_ai_cross_learner.py` — KALDIRILDI (24 Kasım 2026)
- Üretimde hiçbir betik tarafından çağrılmayan, veriye uydurulmamış sabitler içeren ölü kod olduğu için depodan temizlendi.

## 2. 141e724 — yüksek toplam gol beklentisinde Dixon–Coles rho "taper"ı → KAPALI
`tail_goals.HIGH_TOTAL_RHO_TAPER = False`.
- KG Var log-loss'u anlamlı biçimde kötüleştiriyor: tüm maçlarda +0.0000159 (GA [+0.0000093, +0.0000234]);
  toplam beklenti > 2.8 olan 25 939 maçta +0.0000476 (GA [+0.000026, +0.0000697]).
- 3.5 Üst ve 0-0 için fark anlamsız (GA 0'ı içeriyor).

## 3. 141e724 — v7 rejim tokenları (uae./qat./aus./usa./afc.cup/svk.cup/svn.cup/jor.cup/egy./alg./irn./zam.) → GERİ ALINDI
- Bu ligler arşivde yok. `tipsaudit.csv` yalnız 1X2 sonucu içeriyor, bu yüzden sınanamadı.
- Ayar 19 Kasım'ın kendi maçlarına bakılarak yapılmıştı (in-sample); kırık `verify_v7_repair_on_nov19.py` betiği depodan temizlendi.
- Bu ligler artık `CLUB_REGIME`'e düşüyor. Kadın rejimleri de 141e724 öncesi değerlere döndü.

## 4. 7cb38ea — KG Var ağırlıkları (2.5 / 4.5 "blowout") → GERİ ALINDI
- `BTTS_FIT_WEIGHT = 2.0`.
- Arşivde KG Var fiyatı yok, bu yüzden uydurma ağırlığı sınanamadı. Nötr değere dönüldü.

## 5. `data/calibration/live_calibration.json` (60 maç) → NÖTR
`auto_learn.load_live_calibration`, sonuçlanmış maç sayısı `MIN_LIVE_CAL_MATCHES = 300`'ün altındaysa
prob_shift ile kaynak/aile sigma düzeltmelerini boş döndürür ve `neutralized_reason` alanını yazar.
- Arşiv testinde "model" prob_shift KG Var'ı anlamlı biçimde kötüleştirdi: +0.00085 (GA [+0.00065, +0.00105]).
- 2.5 Üst, 3.5 Üst ve MS 1 kaydırmaları anlamsız çıktı.
- Örneklem 300 maça ulaşınca kayma yeniden arşivde sınanmalı.

## 6. `coupon_builder` koruma katmanları — DOKUNULMADI
- Arşivde Nesine kupon fiyatı olmadığı için sınanamıyor. Olduğu gibi bırakıldı.

## Tutulan (out-of-sample kazanç gösteren) değişiklikler
- **KG Var Platt + lig kalibrasyonu**
  - Yalnız türetilmiş (doğrudan kote edilmeyen) KG Var/KG Yok seçimlerinde uygulanır.
  - Sonuç: −0.000847 LL (GA [−0.001144, −0.000532]); ECE 0.0172 → 0.0015.
  - Dosya: `data/calibration/market_calibration.json`.
- **EV tabanlı ana tercih**
  - Kural: `PICK_MIN_EV = 0.02`, `simulasyon.best_value_bet`, `derin_tahmin.choose`.
  - Max fiyatla: olasılık seçimi −0.09%, EV seçimi +2.15% (GA +0.1% – +4.5%).
- **Zor pazarlarda EV tabanı**
  - Pazarlar: 2.5/3.5 Üst, KG Var, İY/MS, Skor, MS 1 1.70–2.30.
  - Kural: `HARD_MARKET_MIN_EV = 0.03`, sigma +0.010.
  - ROI vekilinde eşik yükseldikçe getiri artıyor; ayrıntı rapordaki "ROI vekili" bölümünde.
