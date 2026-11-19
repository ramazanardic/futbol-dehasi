# Türev pazarların kalibrasyonu (Bet365 1X2 + 2.5 Alt/Üst'e sabitlenmiş motor)

Test: 12000 rastgele maç, 2022-07-01 sonrası, 22 lig. Her maçta gol beklentisi Bet365 marjsız 1X2 ve 2.5 Alt/Üst olasılığına uydurulur (fund_weight=0), sonra ortak gol tensöründen türev olasılıklar hesaplanır.

Ölçütler: ECE = 10 kovalı beklenen kalibrasyon hatası; log-loss, 2016–test öncesi sabit taban oranıyla karşılaştırılır.

| Pazar | Ort. tahmin | Gerçekleşen | ECE | Log-loss motor | Log-loss taban oran | Kazanç |
|---|---|---|---|---|---|---|
| KG Var | %48.1 | %53.1 | 0.0504 | 0.69922 | 0.69163 | -0.00759 |
| 1.5 Üst | %73.0 | %75.5 | 0.0351 | 0.55118 | 0.55728 | +0.00610 |
| 3.5 Üst | %24.0 | %29.4 | 0.0539 | 0.60385 | 0.60677 | +0.00292 |
| İY 0.5 Üst | %67.0 | %71.2 | 0.0414 | 0.60039 | 0.60205 | +0.00166 |
| İY 1.5 Üst | %30.5 | %34.4 | 0.0391 | 0.64219 | 0.64478 | +0.00258 |
| İY 1 | %33.3 | %34.3 | 0.0127 | 0.61613 | 0.64325 | +0.02712 |
| İY 0 | %43.3 | %40.2 | 0.0304 | 0.67125 | 0.67492 | +0.00367 |
| İY 2 | %23.5 | %25.5 | 0.0205 | 0.54710 | 0.56801 | +0.02091 |
| Ev 0.5 Üst | %74.9 | %76.9 | 0.0199 | 0.51641 | 0.54102 | +0.02460 |
| Dep 0.5 Üst | %64.9 | %69.3 | 0.0442 | 0.60231 | 0.61701 | +0.01470 |
| İY/MS 1/1 | %26.7 | %26.6 | 0.0106 | 0.54330 | 0.57952 | +0.03622 |
| İY/MS 0/0 | %16.8 | %14.6 | 0.0216 | 0.41399 | 0.41757 | +0.00358 |
| İY/MS 2/2 | %16.7 | %17.3 | 0.0085 | 0.42762 | 0.46010 | +0.03247 |
| İY/MS 0/1 | %15.4 | %14.8 | 0.0056 | 0.41270 | 0.41975 | +0.00705 |
| Skor 0-0 | %8.3 | %6.9 | 0.0142 | 0.24973 | 0.25180 | +0.00207 |
| Skor 1-1 | %12.9 | %11.5 | 0.0141 | 0.35560 | 0.35725 | +0.00165 |
| Skor 1-0 | %10.7 | %10.2 | 0.0059 | 0.32529 | 0.32928 | +0.00399 |
| Tek | %48.2 | %50.5 | 0.0226 | 0.69412 | 0.69353 | -0.00059 |
| En Çok Gol 2Y | %43.8 | %44.3 | 0.0055 | 0.68674 | 0.68671 | -0.00002 |

Yorum: ECE küçük ve ortalama tahmin ≈ gerçekleşen ise motor, keskin bir 1X2 + Alt/Üst fiyatından türev pazarlar için güvenilir adil fiyat üretir; yumuşak büronun türev oranları bu adil fiyatlarla karşılaştırılabilir.
