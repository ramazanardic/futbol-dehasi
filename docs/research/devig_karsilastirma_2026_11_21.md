# Marj temizleme yöntemi karşılaştırması (21 Kasım 2026)

Repo varsayılanı `power` (markets/devig.py) ile penaltyblog 1.13 (MIT) yöntemleri. Fark = yöntem − power log-loss'u (negatif = daha iyi), eşleştirilmiş bootstrap %95 GA.

## matches.csv ortalama piyasa oranı (2021-07+, 20.000 rastgele maç) — 20000 maç, medyan marj 6.4%

| Yöntem | Log-loss | Brier | Fark (power'a göre) | %95 GA |
|---|---|---|---|---|
| power (repo) | 0.99844 | 0.59685 | — | — |
| multiplicative | 0.99933 | 0.59730 | +0.00089 | +0.00047 – +0.00132 |
| additive | 0.99843 | 0.59687 | -0.00001 | -0.00011 – +0.00008 |
| power | 0.99844 | 0.59685 | -0.00000 | -0.00000 – +0.00000 |
| shin | 0.99860 | 0.59693 | +0.00016 | -0.00000 – +0.00031 |
| differential_margin_weighting | 0.99843 | 0.59687 | -0.00001 | -0.00011 – +0.00008 |
| odds_ratio | 0.99868 | 0.59695 | +0.00024 | +0.00008 – +0.00040 |
| logarithmic | 0.99868 | 0.59695 | +0.00024 | +0.00008 – +0.00040 |

## tipsaudit Pinnacle kapanış (2026-06 – 2026-10) — 7349 maç, medyan marj 5.0%

| Yöntem | Log-loss | Brier | Fark (power'a göre) | %95 GA |
|---|---|---|---|---|
| power (repo) | 0.99798 | 0.59612 | — | — |
| multiplicative | 0.99848 | 0.59639 | +0.00049 | -0.00020 – +0.00123 |
| additive | 0.99802 | 0.59614 | +0.00003 | -0.00013 – +0.00018 |
| power | 0.99798 | 0.59612 | -0.00000 | -0.00000 – +0.00000 |
| shin | 0.99805 | 0.59616 | +0.00007 | -0.00021 – +0.00033 |
| differential_margin_weighting | 0.99802 | 0.59614 | +0.00003 | -0.00014 – +0.00019 |
| odds_ratio | 0.99804 | 0.59614 | +0.00005 | -0.00024 – +0.00033 |
| logarithmic | 0.99804 | 0.59614 | +0.00005 | -0.00024 – +0.00035 |

## tipsaudit Pinnacle açılış (2026-06 – 2026-10) — 7350 maç, medyan marj 6.6%

| Yöntem | Log-loss | Brier | Fark (power'a göre) | %95 GA |
|---|---|---|---|---|
| power (repo) | 1.00162 | 0.59828 | — | — |
| multiplicative | 1.00234 | 0.59873 | +0.00072 | -0.00011 – +0.00152 |
| additive | 1.00168 | 0.59832 | +0.00007 | -0.00011 – +0.00022 |
| power | 1.00162 | 0.59828 | +0.00000 | -0.00000 – +0.00000 |
| shin | 1.00175 | 0.59836 | +0.00013 | -0.00018 – +0.00043 |
| differential_margin_weighting | 1.00168 | 0.59832 | +0.00007 | -0.00009 – +0.00023 |
| odds_ratio | 1.00171 | 0.59834 | +0.00010 | -0.00023 – +0.00041 |
| logarithmic | 1.00171 | 0.59834 | +0.00010 | -0.00022 – +0.00041 |
