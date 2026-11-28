# Veri kapsam — Faz 2 (28 Kas 2026)

Eksik alan **uydurulmadı**; yalnız boş hücre/eksik maç gerçek kaynaktan dolduruldu.

## Yapılanlar
1. **football-data sezon delikleri** (`scripts/arsiv_delik_doldur.py`, football-data.co.uk mmz4281 dosyaları):
   +1.284 maç — G1 2011/12, 2022/23, 2023/24 (tamamen), G1 2024/25 +77, EC (National League) 2024/25 +372,
   SC0–SC3 / T1 2024/25 sezon sonu maçları, E1–E3/F1/F2 birkaç maç. Eşleşme: ±1 gün + normalize takım ya da aynı gün aynı
   skor; ±20 günde aynı eşleşme kontrolü: 0 olası erteleme çifti. Oran, İY, korner, Pinnacle kaynakta ne varsa.
2. **Ek liglerin İY skoru** (`scripts/mac_detay_doldur.py --kaynak arsiv`): data/arsiv openfootball İY skorları,
   ±1 gün + aynı tam skor + iki takım adı benzer + tek aday şartıyla 5.811 boş İY hücresine yazıldı.
   Kalite: aynı eşleştiriciyle İY'si dolu E0/G1/EC/BRA satırlarında openfootball ↔ football-data uyumu
   HTHome %97,5, HTAway %98,0 (n=5.562). Yani doldurulan İY'lerin ~%2'si kaynak hatası olabilir (belgelendi).
3. **Arşiv (yalnız veri):** Wikipedia 2023/24–2026/27 Liga Portugal 2 (1.003), Liga 3 (45), National League North
   (1.104) / South (1.104), Primera Federación (1.271), Segunda Federación (720) → data/arsiv/maclar.csv.gz.
   İskoçya Kupası zaten arşivde (ESPN sco.tennents, 2023/24+ 354 maç).

## Lig başına eksik % (2023-07-01 sonrası satırlar; önce → sonra)
| Lig | n önce→sonra | HT eksik% önce→sonra | Korner eksik% önce→sonra | Sut eksik% önce→sonra | OU25 eksik% önce→sonra | Oran eksik% önce→sonra | PinKap eksik% önce→sonra |
|---|---|---|---|---|---|---|---|
| ARG | 1877→1877 | 100.0→86.4 | 100.0 | 100.0 | 100.0 | 0.0 | 29.2 |
| AUT | 655→655 | 100.0→51.0 | 100.0 | 100.0 | 100.0 | 0.0 | 31.3 |
| B1 | 1043→1043 | 0.1 | 0.1 | 0.1 | 0.0 | 0.0 | 31.0 |
| BRA | 1349→1349 | 100.0→63.7 | 100.0 | 100.0 | 100.0 | 0.0 | 30.1 |
| CHN | 848→848 | 100.0→94.3 | 100.0 | 100.0 | 100.0 | 0.0 | 30.2 |
| D1 | 1008→1008 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 24.5 |
| D2 | 1026→1026 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 31.9 |
| DEN | 657→657 | 100.0→78.5 | 100.0 | 100.0 | 100.0 | 0.0 | 31.1 |
| E0 | 1250→1250 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 22.4 |
| E1 | 1858→1860 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 26.1 |
| E2 | 1832→1835 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 30.9→30.8 |
| E3 | 1840→1844 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 31.1 |
| EC | 1508→1880 | 0.0 | 85.1→88.1 | 85.1→88.1 | 0.9→0.7 | 0.9→0.7 | 38.9→31.2 |
| F1 | 1016→1017 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 24.8 |
| F2 | 1108→1108 | 0.0 | 0.1 | 0.1 | 0.0 | 0.0 | 29.2 |
| FIN | 613→613 | 100.0→85.2 | 100.0 | 100.0 | 100.0 | 0.0 | 30.7 |
| G1 | 468→785 | 0.0 | 0.0→0.1 | 0.0→0.1 | 0.0 | 0.0 | 54.9→32.7 |
| I1 | 1260→1260 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 24.0 |
| I2 | 1270→1270 | 0.0 | 0.0 | 0.0 | 0.1 | 0.1 | 33.1 |
| IRL | 616→616 | 100.0→98.4 | 100.0 | 100.0 | 100.0 | 0.0 | 30.4 |
| JAP | 1060→1060 | 100.0→86.2 | 100.0 | 100.0 | 100.0 | 0.0 | 15.8 |
| MEX | 1181→1181 | 100.0→88.5 | 100.0 | 100.0 | 100.0 | 0.0 | 32.7 |
| N1 | 1035→1035 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 27.1 |
| NOR | 829→829 | 100.0→83.6 | 100.0 | 100.0 | 100.0 | 0.0 | 30.2 |
| P1 | 1017→1017 | 0.1 | 0.1 | 0.1 | 0.1 | 0.1 | 24.8 |
| POL | 1043→1043 | 100.0→75.2 | 100.0 | 100.0 | 100.0 | 0.0 | 31.4 |
| ROM | 1073→1073 | 100.0→83.3 | 100.0 | 100.0 | 100.0 | 0.0 | 31.5 |
| RUS | 835→835 | 100.0→85.9 | 100.0 | 100.0 | 100.0 | 22.3 | 30.8 |
| SC0 | 739→767 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 34.6→33.4 |
| SC1 | 596→617 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 33.1→31.9 |
| SC2 | 603→619 | 0.0 | 0.0→0.2 | 0.0→0.2 | 0.0 | 0.0 | 34.5→33.6 |
| SC3 | 603→614 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 33.8→33.2 |
| SP1 | 1269→1269 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 25.3 |
| SP2 | 1548→1548 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 27.5 |
| SUI | 760→760 | 100.0→85.8 | 100.0 | 100.0 | 100.0 | 0.0 | 33.3 |
| SWE | 847→847 | 100.0→76.9 | 100.0 | 100.0 | 100.0 | 0.0 | 29.3 |
| T1 | 1108→1136 | 0.1→0.2 | 0.1→0.2 | 0.1→0.2 | 0.0 | 0.0 | 25.2→24.6 |
| USA | 1815→1815 | 100.0→96.4 | 100.0 | 100.0 | 100.0 | 0.1 | 29.5 |

Notlar: Ek liglerde korner/şut/2,5 Ü-A oranı football-data'da yok (Faz 3: ESPN maç özeti, indirme sürüyor).
PinKap (Pinnacle kapanış) 2023-07+ penceresinde ~%30 boş: football-data Pinnacle'ı 2025/26 ortasında bıraktı
(E0 2025/26: 210/380), 2026/27 dosyalarında Pinnacle yok — kaynakta olmadığı için doldurulamaz.

## Ölçüm (yüksek oran pazarları, sızıntısız ileri yürüyen backtest, önce/sonra veri)
Test kümesi büyüdü (İY/MS ve İY skoru 17.431 → 19.274 maç: yeni İY'li ek lig maçları + delik sezonları), bu yüzden
mutlak sayılar doğrudan kıyaslanmaz; aynı koşuda **model − piyasa** log-loss farkı (negatif = model daha iyi):

| Pazar | önce (model−piyasa) | sonra (model−piyasa) |
|---|---|---|
| İY/MS | 1.88372−1.88674 = −0.00302 | 1.89328−1.89759 = −0.00431 |
| İY skoru | 1.91392−1.91393 = −0.00001 | 1.90418−1.90461 = −0.00043 |
| 2Y KG | 0.57772−0.57787 = −0.00015 | 0.58333−0.58395 = −0.00062 |
| Skor | 2.79659−2.80025 = −0.00366 | 2.79626−2.80001 = −0.00375 |

Modelin piyasaya üstünlüğü dört pazarda da arttı. data/calibration/yuksek_oran_kalibrasyon.json bu PR'da
DEĞİŞTİRİLMEDİ (üretim kalibrasyonu aynı). Bu pazarlar banko kupona girmez (KURALLAR). Banko 1X2/2,5 bant kontrolü:
oranlı 1X2+O/U kümesine yalnız G1/EC delik maçları eklendi (gerçek oranlı maç).
