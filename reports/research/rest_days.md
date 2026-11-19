# Dinlenme günü piyasanın ötesinde bilgi taşıyor mu?

Veri: lig maçları 2012-07 – 2026-09; eğitim < 2021-07-01, test ≥ 2021-07-01 (51245 maç). Dinlenme = aynı veri setindeki önceki maçtan bu yana gün (kupa / Avrupa maçları veri setinde yok, bu yüzden kısa dinlenme eksik ölçülür).

- Test log-loss — marjsız piyasa: 1.00119 | yeniden kalibre piyasa: 1.00123 | piyasa + dinlenme: 1.00114
- Maç başı log-olabilirlik kazancı (dinlenme modeli − kalibre piyasa): +0.000094 (%95 GA +0.000027 – +0.000157)

| Grup (test) | n | Gerçek ev galibiyeti | Piyasanın ev olasılığı |
|---|---|---|---|
| ev kısa dinlenme (≤3 gün), dep ≥5 | 1202 | %47.6 | %45.2 |
| dep kısa dinlenme (≤3 gün), ev ≥5 | 1131 | %41.4 | %43.0 |
| ikisi de ≥5 gün | 36343 | %43.4 | %43.9 |

Yorum: güven aralığı sıfırı içeriyorsa dinlenme günü, piyasanın zaten fiyatladığı bilginin ötesinde bir şey katmıyor.
