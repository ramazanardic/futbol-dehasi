# Yüksek oran katmanı: aday ek pazarlar — ileri-yürüyen değerlendirme (2026-11-28)

- Veri: data/matches.csv, son maç 2026-11-27. Pazar oranı arşivde yok → olasılık kalitesi (log-loss, ECE) ölçüldü, ROI ölçülmedi.
- **piyasa türevi** = 1X2 + 2.5 Alt/Üst'ten ters çevrilmiş λ,μ; sabit %44,4 İY payı; bağımsız yarılar. **sonra** = mevcut yeni model (harman λ, lig İY payı, devre-arası durum çarpanı, aylık geçmişle kalibrasyon). **sonra_ham** = kalibrasyonsuz.
- Karar: doğrulamada t ≤ -2, testte t ≤ -3 (log-loss farkı < 0) ve test ECE'si kıyastan kötü değil.
- **Eklenen:** yok.
- Nesine'nin sunmadığı pazar (2. yarı skoru) değerlendirilmedi. İY/MS'nin dokuz hücresi zaten katmanda.

| Pazar | Dönem | n | log-loss piyasa | sonra_ham | sonra | sonra−piyasa (t) | ham−piyasa (t) | ECE piyasa → sonra |
|---|---|---|---|---|---|---|---|---|
| Toplam gol aralığı (0-1 / 2-3 / 4-5 / 6+) | doğrulama | 15113 | 1.1876 | 1.1878 | 1.1880 | +0.00038 (1.67) | +0.00014 (1.8) | 0.00389 → 0.00414 |
| Toplam gol aralığı (0-1 / 2-3 / 4-5 / 6+) | test | 17431 | 1.1852 | 1.1854 | 1.1849 | -0.00025 (-1.7) | +0.00022 (3.52) | 0.00389 → 0.00184 |
| İY gol sayısı (0 / 1 / 2+) | doğrulama | 15113 | 1.0827 | 1.0827 | 1.0826 | -0.00002 (-0.07) | +0.00001 (0.04) | 0.01088 → 0.00616 |
| İY gol sayısı (0 / 1 / 2+) | test | 17431 | 1.0833 | 1.0835 | 1.0834 | +0.00007 (0.35) | +0.00014 (0.84) | 0.00683 → 0.00317 |
| 2Y gol sayısı (0 / 1 / 2+) | doğrulama | 15113 | 1.0444 | 1.0449 | 1.0444 | +0.00007 (0.26) | +0.00053 (2.69) | 0.00601 → 0.00321 |
| 2Y gol sayısı (0 / 1 / 2+) | test | 17431 | 1.0442 | 1.0443 | 1.0438 | -0.00044 (-2.1) | +0.00009 (0.59) | 0.00300 → 0.00269 |
| En çok gol olacak yarı (1Y / Eşit / 2Y) | doğrulama | 15113 | 1.0741 | 1.0744 | 1.0740 | -0.00011 (-0.32) | +0.00027 (1.03) | 0.00225 → 0.00223 |
| En çok gol olacak yarı (1Y / Eşit / 2Y) | test | 17431 | 1.0705 | 1.0706 | 1.0705 | -0.00001 (-0.03) | +0.00006 (0.27) | 0.00065 → 0.00243 |
| Her iki yarıda da 1,5 üst | doğrulama | 15113 | 0.4380 | 0.4380 | 0.4373 | -0.00069 (-2.0) | +0.00001 (0.35) | 0.01222 → 0.00169 |
| Her iki yarıda da 1,5 üst | test | 17431 | 0.4287 | 0.4287 | 0.4290 | +0.00029 (1.2) | +0.00002 (0.54) | 0.00212 → 0.00820 |
| 2. yarı sonucu (1 / X / 2) | doğrulama | 15113 | 1.0494 | 1.0497 | 1.0495 | +0.00008 (0.47) | +0.00038 (2.94) | 0.00435 → 0.00701 |
| 2. yarı sonucu (1 / X / 2) | test | 17431 | 1.0516 | 1.0518 | 1.0517 | +0.00012 (0.72) | +0.00023 (1.99) | 0.00272 → 0.00509 |
| İY / 2Y karşılıklı gol | doğrulama | 15113 | 1.0561 | 1.0565 | 1.0565 | +0.00045 (1.71) | +0.00039 (2.01) | 0.00313 → 0.00186 |
| İY / 2Y karşılıklı gol | test | 17431 | 1.0681 | 1.0684 | 1.0684 | +0.00031 (1.65) | +0.00030 (1.88) | 0.00271 → 0.00211 |
| İlk yarı skoru / maç skoru | doğrulama | 15113 | 3.9133 | 3.9110 | 3.9155 | +0.00222 (1.58) | -0.00223 (-4.45) | 0.00003 → 0.00004 |
| İlk yarı skoru / maç skoru | test | 17431 | 3.9260 | 3.9238 | 3.9240 | -0.00192 (-1.85) | -0.00217 (-4.33) | 0.00002 → 0.00004 |

## Elenme gerekçeleri

- Toplam gol aralığı (0-1 / 2-3 / 4-5 / 6+): doğrulama: log-loss farkı +0.00038 (t=1.67), eşik t ≤ -2.0; test: log-loss farkı -0.00025 (t=-1.7), eşik t ≤ -3.0
- İY gol sayısı (0 / 1 / 2+): doğrulama: log-loss farkı -0.00002 (t=-0.07), eşik t ≤ -2.0; test: log-loss farkı +0.00007 (t=0.35), eşik t ≤ -3.0
- 2Y gol sayısı (0 / 1 / 2+): doğrulama: log-loss farkı +0.00007 (t=0.26), eşik t ≤ -2.0; test: log-loss farkı -0.00044 (t=-2.1), eşik t ≤ -3.0
- En çok gol olacak yarı (1Y / Eşit / 2Y): doğrulama: log-loss farkı -0.00011 (t=-0.32), eşik t ≤ -2.0; test: log-loss farkı -0.00001 (t=-0.03), eşik t ≤ -3.0; test ECE kötü: 0.00243 > 0.00065
- Her iki yarıda da 1,5 üst: test: log-loss farkı +0.00029 (t=1.2), eşik t ≤ -3.0; test ECE kötü: 0.0082 > 0.00212
- 2. yarı sonucu (1 / X / 2): doğrulama: log-loss farkı +0.00008 (t=0.47), eşik t ≤ -2.0; test: log-loss farkı +0.00012 (t=0.72), eşik t ≤ -3.0; test ECE kötü: 0.00509 > 0.00272
- İY / 2Y karşılıklı gol: doğrulama: log-loss farkı +0.00045 (t=1.71), eşik t ≤ -2.0; test: log-loss farkı +0.00031 (t=1.65), eşik t ≤ -3.0
- İlk yarı skoru / maç skoru: doğrulama: log-loss farkı +0.00222 (t=1.58), eşik t ≤ -2.0; test: log-loss farkı -0.00192 (t=-1.85), eşik t ≤ -3.0; test ECE kötü: 4e-05 > 2e-05
