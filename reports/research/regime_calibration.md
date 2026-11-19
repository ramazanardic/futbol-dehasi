# Gol dağılımı rejiminin yeniden kalibrasyonu (piyasaya sabitlenmiş maç sonu türev pazarlar)

Kalibrasyon: 2500 maç (2019-07 – 2022-07-01); test: 6000 maç (2022-07-01+). Her maçta gol beklentisi Bet365 marjsız 1X2 + 2.5 Alt/Üst'e uydurulur; parametreler yalnızca kalibrasyon döneminde seçilir.

- Mevcut kulüp rejimi: ν=1.1, ρ=-0.07, κ=0.0
- Kalibrasyonda en iyi: **ν=1.0, ρ=-0.03, κ=0.0**

| Pazar | Gerçekleşen (test) | Mevcut tahmin | Yeni tahmin | Log-loss mevcut | Log-loss yeni |
|---|---|---|---|---|---|
| KG Var | %52.8 | %53.4 | %51.3 | 0.68631 | 0.68665 |
| 1.5 Üst | %74.4 | %76.3 | %75.0 | 0.55888 | 0.55797 |
| 3.5 Üst | %28.7 | %28.7 | %29.1 | 0.58358 | 0.58363 |
| 4.5 Üst | %13.3 | %13.8 | %14.4 | 0.37945 | 0.37990 |
| Ev 0.5 Üst | %75.8 | %77.0 | %75.9 | 0.52378 | 0.52345 |
| Dep 0.5 Üst | %69.4 | %69.3 | %68.0 | 0.59589 | 0.59627 |
| Skor 0-0 | %7.6 | %7.2 | %7.4 | 0.26588 | 0.26578 |
| Skor 1-1 | %12.3 | %12.7 | %11.5 | 0.37107 | 0.37130 |
| Skor 1-0 | %10.1 | %9.2 | %9.7 | 0.32303 | 0.32259 |
| Skor 0-1 | %7.8 | %7.3 | %7.9 | 0.26656 | 0.26651 |

Toplam test log-loss: mevcut 4.55443 → yeni 4.55406 (-0.00037).

## Kalibrasyon ızgarası (ilk 10)

| ν | ρ | κ | toplam log-loss |
|---|---|---|---|
| 1.0 | -0.03 | 0.0 | 4.61746 |
| 1.05 | -0.03 | 0.0 | 4.61747 |
| 1.05 | +0.00 | 0.0 | 4.61760 |
| 1.1 | +0.00 | 0.05 | 4.61771 |
| 1.1 | -0.03 | 0.05 | 4.61782 |
| 1.0 | +0.00 | 0.0 | 4.61786 |
| 1.0 | -0.07 | 0.0 | 4.61827 |
| 1.1 | +0.00 | 0.0 | 4.61830 |
| 1.1 | -0.03 | 0.0 | 4.61845 |
| 1.1 | +0.03 | 0.05 | 4.61847 |
