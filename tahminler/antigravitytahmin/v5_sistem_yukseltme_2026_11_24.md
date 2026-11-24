# QuantFoot v5 — Tüm 5 Yapay Zekâ Ortak Kasa Koruma ve Maksimum 5 Maçlı Garantili Kupon Yükseltmesi (24 Kasım 2026)

## 1. Kullanıcı Kuralları ve Çözülen Temel Kayıplar
1. **Maksimum En Garanti 5 Maç (`1–5` Bacak, 6+ Maç Yasak):**
   - `src/quantfoot/settings.py` (`BANKO_MIN_LEGS = 1`, `BANKO_MAX_LEGS = 5`) ve `src/quantfoot/coupons/coupon_rules.py` (`DEFAULT_MIN_LEGS = 1`, `DEFAULT_MAX_LEGS = 5`) güncellendi.
   - Banko kuponlarda 6. maçın birleşik olasılığı düşürmesi kesin olarak engellendi.
2. **Kupon İstendiğinde Asla "Hayır" Dememe (Kademeli Güvenli Havuz + `safest_first_coupon`):**
   - `scripts/nesine_kupon.py` (`build_Pool_fallback_pools`) ve `scripts/kupon_kur.py`: İstenen hedef orana 5 maç içinde ulaşılamasa bile sistem kupon vermeyi reddetmez; kademeli güvenli havuzdan en yüksek güvenilirlikli (`p_low`) **maksimum 5 maçı** seçerek kuponu ve `100 TL Tek-Bacak Sigorta (Sistem n-1, n)` alternatifini oluşturur.
3. **Derin Tahmin (`scripts/derin_tahmin.py`), Derin Araştırma (`scripts/derin_arastirma.py`), Bahis Aileleri (`scripts/bahis_aileleri.py`), Simülasyon (`scripts/simulasyon.py`) ve Günlük Analiz (`scripts/gunluk_analiz.py`) Kök-Neden Teşhisi:**
   - Ana maç tahminlerinde, en yüksek 5 aile özetinde (`top_five`) ve derin araştırmada (`flags` aktarımıyla) `market_diagnosis.diagnose_selection(..., for_coupon=False)` zorunlu hale getirildi; sert steam tuzakları (`≥6p MS 1/2`, `≥5p İY 1.5 Alt`), `İY ÇŞ 12`, `İY Çift`, kaleci/golcü eksikleri ve `DEĞİL(Ev/Dep İki Yarıda Gol) ≥ 1.45` tuzakları ana tahmin tablosuna (`mac_tahminleri.csv`) ve ilk 5 aile vitrinine sızamaz.
   - `scripts/gunluk_tahmin.py` ortak üretim hattının `derin` adımına `scripts/simulasyon.py` doğrudan bağlandı; böylece kupon kurulmadan önce 3'lü onay (`piyasa + bağımsız simülasyon + takım geçmişi`) ve simülasyon çelişkisi (`çelişki`) otomatik olarak üretilip kupon kurucuya (`kupon_kur.py`) aktarılır.
4. **Matematiksel Devig ve EV Sıralaması Düzeltmeleri:**
   - `src/quantfoot/markets/devig.py`: Çok düşük oranlı ağır favorilerde (`1.01–1.05`) `_solve_power` üst sınırı dinamik genişletildi (`upper *= 2.0`).
   - `scripts/nesine_kupon.py`: Banko modunda türetilmiş seçimlerin EV tabanı son kalibre olasılık sonrası tek seferde uygulanır (çifte kırpma önlendi), 3 saatlik bayat fiyat kalkanı (`MAX_PRICE_AGE_H = 3.0`) korundu.
5. **Depo, Ölü Kod, PR ve Görev Zamanlayıcısı Temizliği:**
   - Yerel depo `origin/main` ile birebir eşitlendi, çakışan/eski PR'lar (`#16`, `#19`, `#22`) ve 8 ölü uzak dal temizlendi, silinmiş betiği çağıran Windows `\QuantFoot\KuponIzle` görevi devre dışı bırakıldı.
   - Kırık / ölü deneysel betikler (`scripts/verify_v7_repair_on_nov19.py`, `scripts/quantfoot_v82_multi_ai_cross_learner.py`) ve uydurma `v81` rapor artıkları (`reports/nov22_night_v81_coupons.md`, `reports/ledger/coupons_2026_11_22_night_v81.json`) depodan tamamen silindi.
