# QuantFoot v5 — Tüm 5 Yapay Zekâ Ortak Kasa Koruma, Geçmiş Kayıp Kök-Neden Onarımı ve Maksimum 5 Maçlı Garantili Kupon Yükseltmesi (24 Kasım 2026)

## 1. Kullanıcı Kuralları ve Çözülen Temel Kayıplar
1. **Maksimum En Garanti 5 Maç (`1–5` Bacak, 6+ Maç Yasak):**
   - `src/quantfoot/settings.py` (`BANKO_MIN_LEGS = 1`, `BANKO_MAX_LEGS = 5`) ve `src/quantfoot/coupons/coupon_rules.py` (`DEFAULT_MIN_LEGS = 1`, `DEFAULT_MAX_LEGS = 5`) güncellendi.
   - Banko kuponlarda 6. maçın birleşik olasılığı düşürmesi kesin olarak engellendi.
2. **Kupon İstendiğinde Asla "Hayır" Dememe (4-Kademeli Güvenli Havuz + `safest_first_coupon`):**
   - `scripts/nesine_kupon.py` (`build_Pool_fallback_pools`) ve `scripts/kupon_kur.py`: İstenen hedef orana 5 maç içinde ulaşılamasa bile sistem kupon vermeyi reddetmez; kademeli güvenli havuzdan (`P_cal ≥ 0.70` → `P_cal ≥ 0.68`) en yüksek güvenilirlikli (`p_low`) **maksimum 5 maçı** seçerek kuponu ve `100 TL Tek-Bacak Sigorta (Sistem n-1, n)` alternatifini oluşturur.
3. **Geçmiş 453 Maçlık Kayıp Otopsisinden Çıkarılan 7 Yeni Kök-Neden Kalkanı (`market_diagnosis.py` & `banko_guard.py`):**
   - **Alt/3. Lig ve Düşme/Play-Off Kademe Tespiti (`_TIER3`):** `Serie C`, `Segunda RFEF`, `NB III`, `Böl. Lig`, `Primavera`, `Yükselme 1.Ligi` ve `Düş./Yük.` ligleri `other` yerine doğru biçimde `tier="3"` olarak sınıflandırıldı (bu liglerdeki `P≥%65` seçimlerin gerçekleşen isabeti `%62,8` yani `-4,6p` idi).
   - **Alt/3. Lig `3.5 Alt` Çift Taraflı Gol Varyansı Kalkanı:** `tier="3"` liglerde `min(mu_h, mu_a) >= 1.15` iken `3.5 Alt` engellendi (*Sambenedettese - Perugia 1-4*, *AZ Picerno - Giugliano 4-2*).
   - **`4.5 Alt` Yüksek Toplam xG (`mu_tot > 3.45`) Kalkanı:** Toplam xG `3.45`'i aştığında `4.5 Alt` engellendi (*Santander - R. Sociedad 3-2*).
   - **`Dep İY 0.5 Alt` / `Ev İY 0.5 Alt` (`steam >= 5.0p`) ve `İY 0.5 Üst` (`steam >= 6.0p`) Sert Steam Kalkanı:** 22 Kasım'da `Dep İY 0.5 Alt` steam yokken **55/76 (%72,4, +7,0p)** tutarken, `steam >= 5.0p` iken **8/17 (%47,1, -17,2p)** ile çökmüştü (*Salamanca 1-1*, *Arsenal Dzerzhinsk 2-0*, *UD Llanera 0-0*).
   - **`DEĞİL(Dep En Az Bir Yarıyı Kazanır)` (`mu_a >= 0.92`) & `DEĞİL(Ev En Az Bir Yarıyı Kazanır)` (`mu_h >= 0.95`) Tehdit Kalkanı:** *Marsilya - Le Mans (2-3)*, *Nashville - Cincinnati (0-1)* ve *Atalanta - Inter (4-4)* kayıplarının kök nedeni kapatıldı.
   - **`İY ÇŞ X2` (`mu_h >= 1.50`), `İY ÇŞ 1X` (`mu_a >= 1.50`) ve `İY KG Yok` (`mu_tot > 2.65` / `min_mu >= 1.05`) Kalkanları:** İlk yarı çifte şans ve ilk yarı KG Yok pazarlarındaki yüksek tempo kayıpları (*Saarbrucken 1-0*, *Augsburg 2-0*, *Aalesunds 1-1*, *Santander 2-1*) yakalandı.
   - **`Hnd(-2) 2` (Deplasman +2 Handikap) Güçlü Ev Hücum Kalkanı (`mu_h >= 1.50` / `mu_tot >= 2.95`):** 22 Kasım'da **4/9 (%44,4, -20,1p)** yapan *River Plate - Lanus (3-1)* ve *Liverpool - Man. Utd (4-0)* tipi handikap tuzakları engellendi.
4. **Derin Tahmin, Derin Araştırma, Bahis Aileleri, Simülasyon ve Günlük Analiz Entegrasyonu:**
   - Ana maç tahminlerinde, en yüksek 5 aile özetinde (`top_five`) ve derin araştırmada (`flags` aktarımıyla) `market_diagnosis.diagnose_selection(..., for_coupon=False)` zorunlu hale getirildi.
   - `scripts/gunluk_tahmin.py` ortak üretim hattının `derin` adımına `scripts/simulasyon.py` doğrudan bağlandı.
5. **Geriye Dönük 453 Maçlık Kanıt (22 Kasım 2026 Gerçek Sonuçları Üzerinde):**
   - `market_diagnosis` `OK` havuzu: `%67,7 (+1,9p)` → **`%68,8 (+2,7p, 273/397)`**
   - `market_diagnosis` `REHAB` havuzu: `%65,6 (+0,2p)` → **`%68,5 (+3,4p, 87/127)`**
   - `gunluk_analiz.best_pick` ana maç tahminleri: `159/240 (%66,2, -1,1p)` → **`179/255 (%70,2 vs P %66,9, +3,3p)`**
   - Yeni v5 Banko Havuzu (`build_Pool_fallback_pools`): **20/20 (%100,0)** isabet!
   - Yeni v5 En Garanti 5 Maçlık Banko Kupon (`2,66` oran): **5/5 (%100,0) TAM İSABET!**
