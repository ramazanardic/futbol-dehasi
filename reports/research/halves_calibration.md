# İlk yarı / oyun durumu kalibrasyonu (27 maç, doğrudan borsa fiyatları)

Kayıp = ortalama KL(borsa || model), yarı pazarlarında. Düşük = daha iyi.

| Parametre | Mevcut | Kalibre |
|---|---|---|
| a1 | 0.440 | 0.446 |
| z | 0.960 | 0.800 |
| g | 1.025 | 1.200 |
| l1 | 0.958 | 0.915 |
| t1 | 1.100 | 1.105 |
| l2 | 1.010 | 1.250 |
| t2 | 1.015 | 1.395 |

| | Kalibrasyon kaybı | Test kaybı |
|---|---|---|
| Mevcut | 0.00018 | 0.00028 |
| Kalibre | 0.00015 | 0.00026 |

## Test kaybı, pazar ailesine göre

| Aile | n | Mevcut | Kalibre |
|---|---|---|---|
| İY | 89 | 0.00021 | 0.00018 |
| İY 0 | 6 | 0.00007 | 0.00002 |
| İY 1 | 6 | 0.00001 | 0.00002 |
| İY 2 | 6 | 0.00004 | 0.00006 |
| İY/MS | 45 | 0.00053 | 0.00051 |
| İki | 2 | 0.00018 | 0.00017 |
