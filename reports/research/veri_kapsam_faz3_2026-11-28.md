# Veri kapsam — Faz 3 (28 Kas 2026): ESPN maç özeti ile İY ve maç istatistikleri

Kaynak: ESPN herkese açık maç özeti (`scripts/espn_detay_tara.py`, 2025-01-01 → 2026-11-28; kullanıcı kuralı: yalnız son
2 sezon). Doldurma `scripts/mac_detay_doldur.py --kaynak espn`: aynı lig, ±1 gün, AYNI tam skor, iki takım adı benzer,
tek aday; yalnız BOŞ hücre (dolu hücre değişmedi: 0), İY > tam skor yazılmaz (İY>FT satırı 0).
Ligler: NOR, SWE, DEN, AUT, RUS, ARG, BRA, MEX, USA, JAP. **CHN bekliyor** (indirme sürüyor; sonraki koşuda aynı komut).

## Doğrulama
- ESPN ↔ football-data (E0 kontrol örneği, n=43): İY %100, korner/şut/isabetli/faul %97,7, sarı %95,3, kırmızı %100.
- ESPN İY ↔ openfootball İY (bu 10 lig, n=834): HTHome %99,9, HTAway %100.

## Eksik % (2025-01-01 sonrası satırlar, önce → sonra; yazılan alanlar)
| Lig | n | HT eksik% önce→sonra | Korner eksik% önce→sonra | Sut eksik% önce→sonra | IsSut eksik% önce→sonra | Faul eksik% önce→sonra | Kart eksik% önce→sonra |
|---|---|---|---|---|---|---|---|
| ARG | 1012 | 95.1→0.7 | 100.0→100.0 | 100.0→0.7 | 100.0→0.7 | 100.0→0.7 | 100.0→0.7 |
| AUT | 366 | 37.4→0.0 | 100.0→100.0 | 100.0→16.4 | 100.0→16.4 | 100.0→16.4 | 100.0→16.4 |
| BRA | 742 | 52.8→0.0 | 100.0→100.0 | 100.0→0.0 | 100.0→0.0 | 100.0→0.0 | 100.0→0.0 |
| CHN | 480 | 98.3→98.3 | 100.0→100.0 | 100.0→100.0 | 100.0→100.0 | 100.0→100.0 | 100.0→100.0 |
| DEN | 372 | 86.0→28.5 | 100.0→100.0 | 100.0→32.8 | 100.0→32.8 | 100.0→32.8 | 100.0→32.8 |
| JAP | 537 | 90.7→0.0 | 100.0→100.0 | 100.0→0.0 | 100.0→0.0 | 100.0→0.0 | 100.0→0.0 |
| MEX | 663 | 96.1→11.6 | 100.0→100.0 | 100.0→11.6 | 100.0→11.6 | 100.0→11.6 | 100.0→11.6 |
| NOR | 456 | 96.9→12.7 | 100.0→100.0 | 100.0→12.7 | 100.0→12.7 | 100.0→12.7 | 100.0→12.7 |
| RUS | 457 | 92.3→9.2 | 100.0→100.0 | 100.0→9.6 | 100.0→9.6 | 100.0→9.6 | 100.0→9.6 |
| SWE | 472 | 92.6→0.2 | 100.0→100.0 | 100.0→0.2 | 100.0→0.2 | 100.0→0.2 | 100.0→0.2 |
| USA | 1060 | 99.1→13.0 | 100.0→100.0 | 100.0→13.1 | 100.0→13.1 | 100.0→13.1 | 100.0→13.1 |

Kalan boşluklar: eşleşmeyen maçlar (DEN %33: büyük kısmı küme/play-off turu ve ad farkı; AUT %16 benzer), ESPN'de
özeti olmayan maçlar. Uydurulmadı. Kart sütunu = sarı (HomeYellow/AwayYellow); kırmızı da aynı oranda doldu.

## Ölçüm (sızıntısız ileri yürüyen)
| Ölçüm | önce | sonra |
|---|---|---|
| İY/MS model−piyasa log-loss (t), ECE | −0.0032 (−5,13), 0,0020 · n 19.748 | −0.0030 (−5,32), 0,0022 · n 24.429 |
| İY skoru model−piyasa (t), ECE | −0.0007 (−2,31), 0,0013 | −0.0006 (−2,48), 0,0010 |
| 2Y KG model−piyasa, ECE | −0.0002, 0,0045 | −0.0002, 0,0068 |
| Kesin skor model−piyasa | −0.0037 | −0.0037 (aynı) |
| Korner banko P≥0,70 test (n, tahmin/gerçek) | 75.390, 0,8042/0,8038 | aynı (korner yazılmadı) |
| Kart/korner rating log-loss (evaluate_corner_card_models) | — | aynı (kart değerlendirmesi korner satırı ister) |
| Şut xG vekili (fit_shot_xg) 12 şut/4 isabet ev | 1,1445 (n 121.691) | 1,1457 (n 125.807) |

İY pazarları: model−piyasa farkı ve t aynı düzeyde (test kümesi büyüdüğü için birebir değil); İY/MS ve İY skoru ECE
nötr, 2Y KG ECE 0,0045 → 0,0068 (hâlâ < 0,01; banko dışı analiz pazarı). Üretim kalibrasyon dosyaları değişmedi.

## Reddedilenler
- **Korner (ESPN) — alınmadı.** Yazıldığında korner banko P≥0,70 test dilimi 75.390 → 93.940 maç, fark −0,0003 → −0,0023
  (z −1,76; yeni liglerde ≈ −0,95 puan, aşırı özgüven) ve katsayı 4,03 → 3,88 kaydı. Banko kalibrasyonu kötüleştiği için
  korner hücreleri boş bırakıldı. (Rating modeli korner çizgilerinde karışık: 8,5/9,5/10,5 Üst iyileşti, ev/dep 4,5 ve
  Korner 1 biraz kötüleşti; kartta belirgin iyileşme vardı ama kart değerlendirmesi korner satırı gerektiriyor.)
- **football-data `PPH/PPD/PPA` → Pinnacle eşlemesi — yapılmadı.** notes.txt: PP* = **Paddy Power**; Pinnacle = PSH/PH,
  P>2.5. Pinnacle değil, uydurulmadı. 2026/27 dosyalarında Pinnacle sütunu yok.

## Ek: Çin Süper Ligi (CHN, chn.1) — indirme tamamlandıktan sonra
Aynı kurallar (yalnız boş hücre, korner yok). ESPN İY ↔ mevcut İY uyumu %100 (n=8); 479/480 maç eşleşti; İY>FT 0.
CHN eksik % (2025-01-01+, n=480): İY 98,3 → 0,2; şut/isabetli/faul/kart 100 → 0,2; korner 100 (alınmadı).
Ölçüm (model−piyasa log-loss, ECE; #40 → CHN eklendi): İY/MS −0,0030 → −0,0032 (t −5,69), ECE 0,0022 → 0,0021;
İY skoru −0,0006 → −0,0006, ECE 0,0010 → 0,0012; 2Y KG −0,0002 → −0,0002, ECE 0,0068 → 0,0071; kesin skor aynı.
Nötr; üretim kalibrasyon dosyaları değişmedi.
