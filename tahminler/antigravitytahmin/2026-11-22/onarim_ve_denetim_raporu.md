# 22 Kasım 2026 — Öz-Denetim, Kök-Neden Onarım ve Geliştirme Raporu (antigravitytahmin)

- **Tarih / Saat:** 2026-11-22 20:58 TSİ
- **Kapsam:** Yalnız `tahminler/antigravitytahmin/2026-11-22/` tahminleri ve Nesine resmi sonuç akışından kesinleşen **324 bitmiş fiyatlı maç** (~2.105 yüksek olasılıklı seçim).
- **Bütünlük kuralı:** Maç öncesi dondurulmuş `mac_tahminleri.csv` ve `kuponlar.csv` dosyalarına geriye dönük hiçbir değişiklik yapılmadı.

---

## 1. 20:30 TSİ Kontrol Özeti (Resmi Biten Maçlar)

- **455 Maçlık Ana Tahmin (`mac_tahminleri.csv`):** 298 bitmiş maç (140 ana tercihli) → **90 / 140 (%64,3)** vs model ortalaması **%67,2** (−2,9 puan), sabit 1 br **−27,23 br**, 1X2 Brier **0,553** (294 maç).
- **17:00 Sonrası Özel Kuponlar (`#31`, `#32`, `#33`):** Üçü de 0 kayıpla devam ediyor (`#32` En Emin 5'li 2,91x: `2✓/0✗/3⏳`; `#33` En Emin 6'lı 3,63x: `2✓/0✗/4⏳`; `#31` 10,01x: `1✓/0✗/5⏳`).
- **30 Maksimum Oranlı Kupon (`#1–#30`):** 0 TUTTU · 4 DEVAM (`#1`, `#7`, `#15` canlı yarışta; `#9` ilk yarı 0-0 nedeniyle canlıda fiilen elendi) · 26 YATTI; biten bacak isabeti `51/108 (%47,2)`.
- **3 Sıkı Banko Adayı (`P_düz ≥ %70`):** `2/2 (%100)` tuttu (`AC Horsens İY 0.5 Üst ✓`, `Kortrijk MS 2 ✓`), `Sambenedettese 3.5 Alt` devam ediyor.
- **Ekstrem Gol Önerileri:**
  - `6+ Gol / 5,5 Üst`: `1/4` (**S. Rotterdam – AZ Alkmaar 1-5 `@5,89` ✓**) → **+1,89 br (+%47,3 ROI)**; Barcelona – Villarreal `3-2` ile 1 golle kaçtı.
  - `İki Yarıda KG Var`: `0/3` (`-3,00 br`); canlıda `Aalesunds – Rosenborg` (`1Y 1-1 ✓`, 2Y `0-1`) tek gole bakıyor.

---

## 2. Tespit Edilen ve Onarılan 6 Sistematik Kök Hata

1. **`Dep İY 0.5 Üst` dal hatası (`market_diagnosis.py`):** `"0.5 Üst"` ile bittiği için tam-maç takım golü kuralına (`xG ≥ 1,25`) düşüp rehabilite ediliyordu; gerçek deplasman 1Y gol payı **%41,7** (ev **%43,5**) iken sahada **9/24 (%37,5 · −21,5p)** ve kuponda **0/4** yaptı. Tüm `Ev/Dep İY/2Y` pazarları tam-maç dalından ayrıldı, `Dep İY 0.5 Üst` için −8p kırpma ve sıkı 1Y profili eklendi (`coupon_family_calibration.json` kalıbıyla birlikte).
2. **`İY Çift` aile sızıntısı (`market_diagnosis.py`, `gunluk_analiz.py`, `derin_tahmin.py`):** `market_family("İY Çift")` bunu `"İlk yarı"` olarak sınıfladığı için `Tek/Çift` yasağından sızıyordu (**26/58 = %44,8 vs %56,4 · −11,6p**). Artık tüm parite pazarları isme göre en başta engelleniyor.
3. **Gizli tuzaklar ve fazla-katı ret dengesi (`market_diagnosis.py`):**
   - `DEĞİL(Ev İki Yarıda Gol)` güçlü ev hücumunda (`mu_h ≥ 1,75` veya `h_gf ≥ 1,85`) **16/32 (%50,0 · −14,8p)** ile tuzağa düşüyordu → engellendi.
   - `Dep 1.5 Üst` türetilmiş model fiyatında (`4/9 = %44,4`) zayıf kaldı → doğrudan keskin fiyat veya `mu_a ≥ 2,15` şartı getirildi. `ÇŞ 1X` güçlü deplasmana (`p2 ≥ 0,36` / `mu_a ≥ 1,30`) karşı engellendi.
   - Gereksiz elenen güçlü dilimler açıldı: `3.5 Alt` (`mu_tot` tavanı `2,90 → 3,10`), `Ev 2.5 Alt` (`1,55 → 1,68`), `Ev/Dep 1.5 Alt` (`1,05 → 1,12`).
4. **Monte Carlo simülasyon hatası (`scripts/simulasyon.py`):** Eski `(th["gf"] + ta["ga"]) / 2` formülü ev sahibi avantajını sıfırlayıp güçlü favorileri eziyor, bu yüzden sahte `çelişki` üretiyordu (eski `çelişki %72,0`). Saha-uyarlamalı form xG'si (`home_adv=True`), lig modeline %60 ağırlık, ortak maç-temposu **Gamma-Poisson (`κ = 0,030`)**, **asimetrik deplasman 1Y payı (`−1,5p`)** ve `min_side < 0,45` tek-taraf maskeleme kalkanı eklendi.
5. **Ana tercih sıralaması (`scripts/gunluk_analiz.py`, `scripts/gunluk_tahmin.py`):** `research.teams` profilleri bağlama eklendi; tüm bantlarda türetilmiş fiyattan +2 ila +7p daha kalibre çıkan doğrudan keskin borsa fiyatlarına (`direct=True`) olasılığı şişirmeden `+1,5p` sıralama önceliği verildi.
6. **Yeni 6+ Gol & İki Yarıda KG Var Uzman Motoru (`src/quantfoot/markets/extreme_goals.py`, `scripts/ekstrem_gol_analiz.py`):** Overdispersed kuyruk (`tail_goals`) + asimetrik yarı-tempo (`halves_btts`) üzerine iki ayrı 0–100 DNA skorlayıcı + aynı yüksek-DNA maçlar için **%70+ güvenli gol merdiveni** kuruldu ve hem `scripts/gunluk_tahmin.py` hem `.github/workflows/daily-autonomous.yml` akışlarına bağlandı.

---

## 3. Önce vs Sonra — 324 Bitmiş Maçta Ölçülmüş Sonuçlar

| Metrik | Önce | Sonra |
|---|---:|---:|
| Rehabilite edilen seçimler (`rehabilitated=True`) | `67/112` (**%59,8** vs P %63,0 · −3,2p) | `48/72` (**%66,7** vs P %64,5 · **+2,2p**) |
| İzinli (`OK`) seçimler | `348/607` (**%57,3** · −4,6p) | `316/530` (**%59,6** · −2,9p) |
| Engellenen tuzaklar (`ok=False`) | `426/711` (%59,9) | `477/828` (**%57,6**; yeni yakalanan Tek/Çift **%40,8**, Dep İY 0.5 Üst **%38,9**) |
| `gunluk_analiz.best_pick` | `90/140` (**%64,3** · −2,9p) | `102/154` (**%66,2** · **−0,7p**) |
| `simulasyon.py` sıralaması | `Çelişki %72,0 > Üçlü %70,5 > Kısmi %51,3` | **Monotonik:** `Üçlü %67,2 > Kısmi %61,9 > Çelişki %58,8 > Eksik %52,3` |
| `extreme_goals` Güvenli Merdiven #1 (6+ Gol adayları) | — | **5 / 7 (%71,4)** |
| Toplam birim test suiti (`pytest`) | 1.786 geçti | **1.793 / 1.793 geçti (0 hata)** |
