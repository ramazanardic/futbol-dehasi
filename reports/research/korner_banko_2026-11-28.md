# Toplam korner Alt/Üst — ileri-yürüyen kalibrasyon (2026-11-28)

- Veri: data/matches.csv, son maç 2026-11-27. Korner oranı arşivde yok → yalnız kalibrasyon ölçüldü, ROI ölçülmedi.
- Son katsayılar: toplam ≈ 4.1331 + 0.5804·beklenti, Var/Ort 1.1489 (n=37358).
- Ölçüt: P ≥ 0,70 diliminde iki dönemde n ≥ 300 maç ve gerçek ≥ tahmin − 5 puan.
- Sonuç: **ETKİN**; geçerli seçimler: Korner 6.5 Üst, Korner 7.5 Üst, Korner 8.5 Üst, Korner 10.5 Alt, Korner 11.5 Alt, Korner 12.5 Alt, Korner 13.5 Alt.

## Havuz (tüm çizgiler, P ≥ 0,70)

| Dönem | n | tahmin | gerçek | fark |
|---|---|---|---|---|
| doğrulama | 63195 | 0.803 | 0.8035 | +0.0004 |
| test | 74508 | 0.8038 | 0.8034 | -0.0004 |

## P bantları (havuz)

| Dönem | Bant | n | tahmin | gerçek | fark |
|---|---|---|---|---|---|
| doğrulama | 0.70-0.75 | 14244 | 0.7257 | 0.7228 | -0.0030 |
| doğrulama | 0.75-0.80 | 15442 | 0.7753 | 0.7744 | -0.0008 |
| doğrulama | 0.80-0.90 | 31914 | 0.8456 | 0.8478 | +0.0022 |
| doğrulama | 0.90-1.00 | 1595 | 0.9108 | 0.9191 | +0.0083 |
| test | 0.70-0.75 | 16634 | 0.7254 | 0.7221 | -0.0033 |
| test | 0.75-0.80 | 18302 | 0.7754 | 0.7747 | -0.0007 |
| test | 0.80-0.90 | 36955 | 0.8454 | 0.8469 | +0.0015 |
| test | 0.90-1.00 | 2617 | 0.912 | 0.9064 | -0.0056 |

## Seçim bazında (P ≥ 0,70)

| Seçim | Dönem | n | tahmin | gerçek | fark | z | karar |
|---|---|---|---|---|---|---|---|
| Korner 6.5 Üst | doğrulama | 14006 | 0.8417 | 0.8454 | +0.0037 | 1.2 | geçerli |
| Korner 6.5 Üst | test | 16549 | 0.837 | 0.832 | -0.0050 | -1.75 | geçerli |
| Korner 7.5 Üst | doğrulama | 12099 | 0.7588 | 0.7618 | +0.0030 | 0.77 | geçerli |
| Korner 7.5 Üst | test | 13310 | 0.7591 | 0.7539 | -0.0051 | -1.38 | geçerli |
| Korner 8.5 Üst | doğrulama | 1492 | 0.7283 | 0.7413 | +0.0129 | 1.12 | geçerli |
| Korner 8.5 Üst | test | 1887 | 0.7283 | 0.7101 | -0.0182 | -1.78 | geçerli |
| Korner 9.5 Üst | doğrulama | 39 | 0.726 | 0.7179 | -0.0080 | -0.11 | elendi |
| Korner 9.5 Üst | test | 39 | 0.7232 | 0.5641 | -0.1591 | -2.22 | elendi |
| Korner 9.5 Alt | doğrulama | 2 | 0.7104 | 1.0 | +0.2896 | 0.9 | elendi |
| Korner 9.5 Alt | test | 5 | 0.7363 | 1.0 | +0.2637 | 1.34 | elendi |
| Korner 10.5 Üst | doğrulama | 1 | 0.7197 | 1.0 | +0.2803 | 0.62 | elendi |
| Korner 10.5 Üst | test | 1 | 0.7084 | 0.0 | -0.7084 | -1.56 | elendi |
| Korner 10.5 Alt | doğrulama | 325 | 0.7184 | 0.7446 | +0.0262 | 1.05 | geçerli |
| Korner 10.5 Alt | test | 765 | 0.7198 | 0.6967 | -0.0231 | -1.42 | geçerli |
| Korner 11.5 Alt | doğrulama | 7684 | 0.7384 | 0.74 | +0.0016 | 0.32 | geçerli |
| Korner 11.5 Alt | test | 9474 | 0.7446 | 0.7489 | +0.0042 | 0.95 | geçerli |
| Korner 12.5 Alt | doğrulama | 13558 | 0.7933 | 0.789 | -0.0044 | -1.26 | geçerli |
| Korner 12.5 Alt | test | 15946 | 0.7969 | 0.803 | +0.0060 | 1.89 | geçerli |
| Korner 13.5 Alt | doğrulama | 13989 | 0.8577 | 0.8547 | -0.0030 | -1.0 | geçerli |
| Korner 13.5 Alt | test | 16532 | 0.8596 | 0.8623 | +0.0027 | 0.99 | geçerli |

## Elenenler ve gerekçe

- Korner 9.5 Üst: doğrulama: P≥0,70 diliminde yalnız 39 maç; test: P≥0,70 diliminde yalnız 39 maç
- Korner 9.5 Alt: doğrulama: P≥0,70 diliminde yalnız 2 maç; test: P≥0,70 diliminde yalnız 5 maç
- Korner 10.5 Üst: doğrulama: P≥0,70 diliminde yalnız 1 maç; test: P≥0,70 diliminde yalnız 1 maç
