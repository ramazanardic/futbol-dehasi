# QuantFoot — Çok Günlük Model ve CLV Özeti

Günler: 2026-11-18

## Model piyasaya bilgi katıyor mu?

- 1X2 log-loss (14 maç) — piyasa: **0.7526**, model: **0.7533**, en iyi havuz: 0.7525
- Havuzda modelin ağırlığı **w = 0.14** (%95 güven aralığı 0.00 – 1.00). Aralık 0'ı içeriyor: model piyasaya **kanıtlanmış bilgi katmıyor**.

## Değer tekilleri: kapanış çizgisi (CLV) ve kâr/zarar

- Kapanış oranı yok: maçlardan önce `snapshot` çalıştırılmalı.

_Karar kuralı: haftalar boyunca adil CLV'nin güven aralığı sıfırın üstünde değilse bahis yapılmamalı._
