# Gol dağılımı rejiminin yeniden kalibrasyonu (piyasaya sabitlenmiş maç sonu türev pazarlar)

Kalibrasyon: 2500 maç (2019-07 – 2022-07-01); test: 6000 maç (2022-07-01+). Her maçta gol beklentisi Bet365 marjsız 1X2 + 2.5 Alt/Üst'e uydurulur; parametreler yalnızca kalibrasyon döneminde seçilir.

- Mevcut kulüp rejimi: ν=1.1, ρ=-0.07, κ=0.0
- Kalibrasyonda en iyi: **ν=1.0, ρ=-0.03, κ=0.0**

| Pazar | Gerçekleşen (test) | Mevcut tahmin | Yeni tahmin | Log-loss mevcut | Log-loss yeni |
|---|---|---|---|---|---|
| KG Var | %52.8 | %48.1 | %51.3 | 0.70037 | 0.68665 |
| 1.5 Üst | %74.4 | %73.0 | %75.0 | 0.56225 | 0.55797 |
| 3.5 Üst | %28.7 | %24.0 | %29.1 | 0.59523 | 0.58363 |
| 4.5 Üst | %13.3 | %10.5 | %14.4 | 0.38840 | 0.37990 |
| Ev 0.5 Üst | %75.8 | %74.7 | %75.9 | 0.52683 | 0.52345 |
| Dep 0.5 Üst | %69.4 | %65.0 | %68.0 | 0.60802 | 0.59627 |
| Skor 0-0 | %7.6 | %8.3 | %7.4 | 0.26735 | 0.26578 |
| Skor 1-1 | %12.3 | %12.9 | %11.5 | 0.37151 | 0.37130 |
| Skor 1-0 | %10.1 | %10.6 | %9.7 | 0.32389 | 0.32259 |
| Skor 0-1 | %7.8 | %8.1 | %7.9 | 0.26719 | 0.26651 |

Toplam test log-loss: mevcut 4.61105 → yeni 4.55406 (-0.05698).

## Kalibrasyon ızgarası (ilk 10)

| ν | ρ | κ | toplam log-loss |
|---|---|---|---|
| 1.0 | -0.03 | 0.0 | 4.61746 |
| 1.0 | +0.00 | 0.0 | 4.61786 |
| 1.0 | -0.07 | 0.0 | 4.61827 |
| 1.0 | +0.03 | 0.0 | 4.61911 |
| 1.0 | -0.03 | 0.05 | 4.62048 |
| 1.0 | +0.00 | 0.05 | 4.62077 |
| 1.0 | -0.07 | 0.05 | 4.62148 |
| 1.0 | +0.03 | 0.05 | 4.62193 |
| 1.0 | +0.00 | 0.1 | 4.62839 |
| 1.0 | -0.03 | 0.1 | 4.62844 |
