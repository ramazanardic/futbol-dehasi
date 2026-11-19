# Gol modeli — doğrudan borsa fiyatlarına kalibrasyon (38 maç)

Kayıp = doğrudan kote edilen, modele girdi olmayan seçimlerde ortalama KL(borsa || model). Düşük = daha iyi.

| Uydurma girdisi | Seçilen ρ / ν / κ / İY payı | Test kaybı (mevcut ayar) | Test kaybı (seçilen ayar) |
|---|---|---|---|
| 1X2 + 2,5 Alt/Üst (bugünkü üretim) | -0.03 / 1.08 / 0.00 / 0.44 | 0.00018 | 0.00017 |
| 1X2 + tüm Alt/Üst çizgileri + KG | -0.03 / 1.08 / 0.00 / 0.44 | 0.00019 | 0.00017 |

## Pazar ailesine göre test kaybı (seçilen ayar)

| Aile | basic | full |
|---|---|---|
| Gol aralığı | 0.00030 | 0.00030 |
| KG&AÜ | 0.00009 | 0.00010 |
| MS | 0.00010 | 0.00009 |
| Tek | 0.00010 | 0.00011 |
| Çift | 0.00010 | 0.00011 |
| İY | 0.00021 | 0.00022 |
| İY/MS | 0.00053 | 0.00060 |
