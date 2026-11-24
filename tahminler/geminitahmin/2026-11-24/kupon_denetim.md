# 2026-11-24 Gemini Tahmin ve Kupon Denetim Raporu

- **Tarih:** 2026-11-24
- **Kapsam:** 30 başlamamış maç (`>= 22:00 TSİ`), 55 kupon (`5.10x – 10.35x`), toplam 246 bacak (`kuponlar.csv`)
- **Seçenek Limiti:** Her `(Maç, Tercih)` çifti portföy genelinde en fazla `3/3` kez kullanılmıştır
- **Denetim Sonucu:** `0 ihlal (exit code 0)` – Tüm kuponlar ve bacaklar kural denetiminden geçmiştir.

## 1. Kupon Stilleri Özeti (6 Stil / 55 Kupon)

| Stil | Kupon Aralığı | Kupon Sayısı | Mod | Bacak Yapısı | Oran Aralığı |
| --- | --- | --- | --- | --- | --- |
| `BANKO_5X_KOMBINE` | 01 – 12 | 12 | `banko` | 5'li | 5.10x – 5.23x |
| `DEGER_4LU_5X_8X` | 13 – 22 | 10 | `risk` | 4'lü | 5.15x – 5.32x |
| `GOL_VE_KOMBINE_4LU` | 23 – 32 | 10 | `risk` | 4'lü | 5.26x – 5.37x |
| `TAKTIK_ALT_VE_KALKAN_5LI` | 33 – 40 | 8 | `banko` | 5'li | 5.12x – 5.34x |
| `KESKIN_3LU_YUKSEK_ORAN` | 41 – 48 | 8 | `yuksek_oran` | 3'lü | 5.15x – 5.27x |
| `AVRUPA_6LI_SISTEM_10X_25X` | 49 – 55 | 7 | `yuksek_oran` | 6'lı | 7.51x – 10.35x |

## 2. 55 Kuponluk Portföy Özet Tablosu

| No | Kupon ID | Stil | Bacak | Toplam Oran | Birleşik P_kalibre | Bacaklar (`Maç: Tercih @ Oran`) |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | `KUPON_01_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.13 | 0.1509 | Benevento - Empoli: İY 1,5 Alt @ 1.37; Crawley Town - Barnet: ÇŞ X2 & 1,5 Üst @ 1.46; Bristol City - Wrexham: 2Y KG Yok @ 1.31; Middlesbrough - Swansea City: MS 1 @ 1.58; Charlton Athletic - Lincoln City: 2Y KG Yok @ 1.24 |
| 02 | `KUPON_02_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.21 | 0.1454 | Charlton Athletic - Lincoln City: İY 1,5 Alt @ 1.32; Bromley - Wycombe Wanderers: 2Y KG Yok @ 1.29; RB Leipzig - RC Lens: Ev 1,5 Üst @ 1.38; Middlesbrough - Swansea City: MS 1 & 1,5 Üst @ 1.63; Manchester City - SSC Napoli: Ev 1,5 Üst @ 1.36 |
| 03 | `KUPON_03_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.12 | 0.1523 | Middlesbrough - Swansea City: Ev 1,5 Üst @ 1.69; Palermo - FC Südtirol: MS 1 @ 1.40; Wolverhampton - Derby County: MS 1 @ 1.32; Feyenoord - FC Porto: İY 0,5 Üst @ 1.28; Stevenage - Sheffield Wednesday: 2Y KG Yok @ 1.28 |
| 04 | `KUPON_04_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.16 | 0.1492 | Norwich City - Queens Park Rangers: İY 0,5 Üst @ 1.33; Sheffield United - Southampton: İY 0,5 Üst @ 1.32; Benevento - Empoli: 2Y KG Yok @ 1.26; Slovan Bratislava - Real Betis: MS 2 @ 1.24; Middlesbrough - Swansea City: 2Y 1 @ 1.88 |
| 05 | `KUPON_05_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.19 | 0.1526 | Como 1907 - AEK Athens: MS 1 @ 1.26; Slovan Bratislava - Real Betis: Dep 1,5 Üst @ 1.32; Middlesbrough - Swansea City: MS 1 @ 1.58; Bristol City - Wrexham: 3,5 Alt @ 1.30; Blackpool - Leicester City: ÇŞ X2 & 1,5 Üst @ 1.52 |
| 06 | `KUPON_06_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.12 | 0.1504 | Glasgow Rangers - Aberdeen: MS 1 @ 1.24; Coquimbo Unido - Unión La Calera: ÇŞ 1X & 3,5 Alt @ 1.44; Bromley - Wycombe Wanderers: İY 1,5 Alt @ 1.39; Sheffield United - Southampton: KG Var @ 1.60; Palermo - FC Südtirol: 2Y KG Yok @ 1.29 |
| 07 | `KUPON_07_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.14 | 0.1474 | Bromley - Wycombe Wanderers: 3,5 Alt @ 1.28; Norwich City - Queens Park Rangers: ÇŞ 1X & 1,5 Üst @ 1.54; Glasgow Rangers - Aberdeen: Ev 1,5 Üst @ 1.39; Hibernian - Dundee FC: 3,5 Alt @ 1.33; Bristol City - Wrexham: İY 1,5 Alt @ 1.41 |
| 08 | `KUPON_08_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.23 | 0.1457 | Manchester City - SSC Napoli: MS 1 @ 1.28; Coquimbo Unido - Unión La Calera: İY 1,5 Alt @ 1.28; Hibernian - Dundee FC: 2Y KG Yok @ 1.32; Chapecoense - Palmeiras: ÇŞ X2 & 1,5 Üst @ 1.60; Palermo - FC Südtirol: Ev 1,5 Üst @ 1.51 |
| 09 | `KUPON_09_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.19 | 0.1448 | Como 1907 - AEK Athens: Ev 1,5 Üst @ 1.31; Benevento - Empoli: 3,5 Alt @ 1.26; RB Leipzig - RC Lens: MS 1 @ 1.38; Port Vale - Northampton Town: İY 1,5 Alt @ 1.34; Norwich City - Queens Park Rangers: KG Var @ 1.70 |
| 10 | `KUPON_10_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.15 | 0.1463 | Bradford City - Barnsley: 2Y KG Yok @ 1.27; Middlesbrough - Swansea City: MS 1 & 1,5 Üst @ 1.63; Hibernian - Dundee FC: İY 1,5 Alt @ 1.43; Cardiff City - Preston North End: 2Y KG Yok @ 1.27; Como 1907 - AEK Athens: MS 1 & 1,5 Üst @ 1.37 |
| 11 | `KUPON_11_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.10 | 0.1475 | Stevenage - Sheffield Wednesday: 3,5 Alt @ 1.25; Cardiff City - Preston North End: 3,5 Alt @ 1.29; Glasgow Rangers - Aberdeen: 2Y KG Yok @ 1.24; Port Vale - Northampton Town: 2,5 Alt @ 1.69; Feyenoord - FC Porto: KG Var @ 1.51 |
| 12 | `KUPON_12_BANKO_5X_KOMBINE` | `BANKO_5X_KOMBINE` | 5 | 5.13 | 0.1478 | Bradford City - Barnsley: 3,5 Alt @ 1.31; Wolverhampton - Derby County: 2Y KG Yok @ 1.24; Blackpool - Leicester City: MS 2 @ 1.78; Glasgow Rangers - Aberdeen: MS 1 & 1,5 Üst @ 1.42; Cesena - Ascoli: 3,5 Alt @ 1.25 |
| 13 | `KUPON_13_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.17 | 0.1569 | Crawley Town - Barnet: KG Var @ 1.68; Stevenage - Sheffield Wednesday: İY 1,5 Alt @ 1.37; Glasgow Rangers - Aberdeen: MS 1 @ 1.24; Bromley - Wycombe Wanderers: ÇŞ X2 & 3,5 Alt @ 1.81 |
| 14 | `KUPON_14_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.26 | 0.1518 | LR Vicenza Virtus - Carrarese: İY 1,5 Alt @ 1.35; Portsmouth - West Ham United: KG Var @ 1.56; Glasgow Rangers - Aberdeen: 2Y 1 @ 1.57; Arsenal - Borussia Dortmund: MS 1 & 1,5 Üst @ 1.59 |
| 15 | `KUPON_15_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.17 | 0.1550 | Cardiff City - Preston North End: İY 1,5 Alt @ 1.40; Blackpool - Leicester City: 2,5 Üst @ 1.77; Portsmouth - West Ham United: 2,5 Üst @ 1.63; Virtus Entella - Hellas Verona: İY 1,5 Alt @ 1.28 |
| 16 | `KUPON_16_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.15 | 0.1550 | Bradford City - Barnsley: İY 1,5 Alt @ 1.41; Real Madrid - PSV Eindhoven: MS 1 & 1,5 Üst @ 1.31; Benevento - Empoli: ÇŞ 1X & 3,5 Alt @ 1.65; Crawley Town - Barnet: Dep 1,5 Üst @ 1.69 |
| 17 | `KUPON_17_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.24 | 0.1538 | Wolverhampton - Derby County: Ev 1,5 Üst @ 1.44; LR Vicenza Virtus - Carrarese: 2Y KG Yok @ 1.26; Bradford City - Barnsley: MS 1 @ 1.72; Feyenoord - FC Porto: ÇŞ X2 & 1,5 Üst @ 1.68 |
| 18 | `KUPON_18_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.16 | 0.1547 | Cesena - Ascoli: İY 1,5 Alt @ 1.37; Charlton Athletic - Lincoln City: 2,5 Alt @ 1.63; Port Vale - Northampton Town: ÇŞ 1X & 3,5 Alt @ 1.54; Real Madrid - PSV Eindhoven: 2Y 1 @ 1.50 |
| 19 | `KUPON_19_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.26 | 0.1517 | Palermo - FC Südtirol: MS 1 & 1,5 Üst @ 1.52; Portsmouth - West Ham United: ÇŞ X2 & 1,5 Üst @ 1.59; Crawley Town - Barnet: MS 2 @ 1.70; Cesena - Ascoli: 2Y KG Yok @ 1.28 |
| 20 | `KUPON_20_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.25 | 0.1517 | Benevento - Empoli: 3,5 Alt @ 1.26; Manchester City - SSC Napoli: MS 1 & 1,5 Üst @ 1.41; Crawley Town - Barnet: 2,5 Üst @ 1.68; Palermo - FC Südtirol: 2Y 1 @ 1.76 |
| 21 | `KUPON_21_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.32 | 0.1504 | Cesena - Ascoli: 3,5 Alt @ 1.25; Slovan Bratislava - Real Betis: 2Y KG Yok @ 1.25; LR Vicenza Virtus - Carrarese: 2,5 Alt @ 1.71; Bradford City - Barnsley: TG 2-3 @ 1.99 |
| 22 | `KUPON_22_DEGER_4LU_5X_8X` | `DEGER_4LU_5X_8X` | 4 | 5.16 | 0.1542 | Como 1907 - AEK Athens: 2,5 Üst @ 1.43; Sheffield United - Southampton: 2,5 Üst @ 1.72; Bromley - Wycombe Wanderers: 3,5 Alt @ 1.28; Cardiff City - Preston North End: ÇŞ 1X & 3,5 Alt @ 1.64 |
| 23 | `KUPON_23_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.26 | 0.1510 | Sheffield United - Southampton: İY 0,5 Üst @ 1.32; Como 1907 - AEK Athens: 2Y 1 @ 1.56; RB Leipzig - RC Lens: MS 1 & 1,5 Üst @ 1.46; Cesena - Ascoli: 2,5 Alt @ 1.75 |
| 24 | `KUPON_24_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.26 | 0.1521 | Slovan Bratislava - Real Betis: 2Y 2 @ 1.50; Manchester City - SSC Napoli: 2,5 Üst @ 1.48; Cesena - Ascoli: İY 1,5 Alt @ 1.37; Blackpool - Leicester City: KG Var @ 1.73 |
| 25 | `KUPON_25_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.28 | 0.1510 | Bradford City - Barnsley: ÇŞ 1X & 3,5 Alt @ 1.64; Manchester City - SSC Napoli: İY 1 @ 1.81; Bromley - Wycombe Wanderers: 2Y KG Yok @ 1.29; RB Leipzig - RC Lens: 2,5 Üst @ 1.38 |
| 26 | `KUPON_26_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.28 | 0.1487 | Wolverhampton - Derby County: 2Y 1 @ 1.64; Como 1907 - AEK Athens: Hnd(-1) 1 @ 1.81; Arsenal - Borussia Dortmund: MS 1 @ 1.38; Real Madrid - PSV Eindhoven: 2,5 Üst @ 1.29 |
| 27 | `KUPON_27_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.36 | 0.1493 | Wolverhampton - Derby County: MS 1 & 1,5 Üst @ 1.46; Cesena - Ascoli: 2Y KG Yok @ 1.28; Blackpool - Leicester City: Dep 1,5 Üst @ 1.78; Arsenal - Borussia Dortmund: Ev 1,5 Üst @ 1.61 |
| 28 | `KUPON_28_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.37 | 0.1498 | Coquimbo Unido - Unión La Calera: 2,5 Alt @ 1.53; RB Leipzig - RC Lens: Ev 1,5 Üst @ 1.38; Palermo - FC Südtirol: 2Y KG Yok @ 1.29; Cesena - Ascoli: TG 2-3 @ 1.97 |
| 29 | `KUPON_29_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.29 | 0.1512 | Blackpool - Leicester City: ÇŞ X2 & 1,5 Üst @ 1.52; Slovan Bratislava - Real Betis: İY 2 @ 1.67; Charlton Athletic - Lincoln City: İY 1,5 Alt @ 1.32; Feyenoord - FC Porto: 2,5 Üst @ 1.58 |
| 30 | `KUPON_30_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.35 | 0.1518 | Chapecoense - Palmeiras: 2,5 Üst @ 1.83; Wolverhampton - Derby County: MS 1 @ 1.32; Como 1907 - AEK Athens: MS 1 & 2,5 Üst @ 1.73; Virtus Entella - Hellas Verona: İY 1,5 Alt @ 1.28 |
| 31 | `KUPON_31_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.26 | 0.1514 | Manchester City - SSC Napoli: 2Y 1 @ 1.63; Benevento - Empoli: 2,5 Alt @ 1.77; Hibernian - Dundee FC: 3,5 Alt @ 1.33; Como 1907 - AEK Athens: MS 1 & 1,5 Üst @ 1.37 |
| 32 | `KUPON_32_GOL_VE_KOMBINE_4LU` | `GOL_VE_KOMBINE_4LU` | 4 | 5.27 | 0.1531 | Chapecoense - Palmeiras: KG Var @ 1.74; Coquimbo Unido - Unión La Calera: İY 1,5 Alt @ 1.28; Charlton Athletic - Lincoln City: KG Yok @ 1.85; Manchester City - SSC Napoli: MS 1 @ 1.28 |
| 33 | `KUPON_33_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.20 | 0.1482 | Bristol City - Wrexham: 2Y KG Yok @ 1.31; Slovan Bratislava - Real Betis: MS 2 @ 1.24; RB Leipzig - RC Lens: 2,5 Üst @ 1.38; Sheffield United - Southampton: ÇŞ 1X & 1,5 Üst @ 1.87; Wolverhampton - Derby County: 2Y KG Yok @ 1.24 |
| 34 | `KUPON_34_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.14 | 0.1466 | Benevento - Empoli: İY 1,5 Alt @ 1.37; Manchester City - SSC Napoli: MS 1 & 1,5 Üst @ 1.41; Charlton Athletic - Lincoln City: 2Y KG Yok @ 1.24; Glasgow Rangers - Aberdeen: 2Y KG Yok @ 1.24; Como 1907 - AEK Athens: İY 1 @ 1.73 |
| 35 | `KUPON_35_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.16 | 0.1497 | Cesena - Ascoli: 2Y KG Yok @ 1.28; Como 1907 - AEK Athens: MS 1 @ 1.26; Coquimbo Unido - Unión La Calera: ÇŞ 1X & 3,5 Alt @ 1.44; Bradford City - Barnsley: 2Y KG Yok @ 1.27; Port Vale - Northampton Town: MS 1 @ 1.75 |
| 36 | `KUPON_36_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.15 | 0.1460 | Norwich City - Queens Park Rangers: İY 0,5 Üst @ 1.33; Bradford City - Barnsley: İY 1,5 Alt @ 1.41; Feyenoord - FC Porto: İY 0,5 Üst @ 1.28; Bristol City - Wrexham: 3,5 Alt @ 1.30; Real Madrid - PSV Eindhoven: İY 1 @ 1.65 |
| 37 | `KUPON_37_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.26 | 0.1448 | Palermo - FC Südtirol: MS 1 @ 1.40; Virtus Entella - Hellas Verona: 2,5 Alt @ 1.54; Bradford City - Barnsley: 3,5 Alt @ 1.31; Bristol City - Wrexham: İY 1,5 Alt @ 1.41; Hibernian - Dundee FC: 2Y KG Yok @ 1.32 |
| 38 | `KUPON_38_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.12 | 0.1441 | Port Vale - Northampton Town: İY 1,5 Alt @ 1.34; Arsenal - Borussia Dortmund: MS 1 @ 1.38; Stevenage - Sheffield Wednesday: 3,5 Alt @ 1.25; Charlton Athletic - Lincoln City: 2,5 Alt @ 1.63; Manchester City - SSC Napoli: Ev 1,5 Üst @ 1.36 |
| 39 | `KUPON_39_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.31 | 0.1424 | Palermo - FC Südtirol: MS 1 & 1,5 Üst @ 1.52; Feyenoord - FC Porto: KG Var @ 1.51; RB Leipzig - RC Lens: MS 1 @ 1.38; Cardiff City - Preston North End: 2Y KG Yok @ 1.27; Slovan Bratislava - Real Betis: Dep 1,5 Üst @ 1.32 |
| 40 | `KUPON_40_TAKTIK_ALT_VE_KALKAN_5LI` | `TAKTIK_ALT_VE_KALKAN_5LI` | 5 | 5.34 | 0.1416 | Manchester City - SSC Napoli: Ev 1,5 Üst @ 1.36; Stevenage - Sheffield Wednesday: İY 1,5 Alt @ 1.37; Bromley - Wycombe Wanderers: İY 1,5 Alt @ 1.39; Virtus Entella - Hellas Verona: ÇŞ X2 & 3,5 Alt @ 1.65; Slovan Bratislava - Real Betis: 2Y KG Yok @ 1.25 |
| 41 | `KUPON_41_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.24 | 0.1602 | LR Vicenza Virtus - Carrarese: KG Yok @ 1.93; Stevenage - Sheffield Wednesday: 2,5 Alt @ 1.75; Real Madrid - PSV Eindhoven: MS 1 & 2,5 Üst @ 1.55 |
| 42 | `KUPON_42_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.16 | 0.1629 | Real Madrid - PSV Eindhoven: Hnd(-1) 1 @ 1.68; Stevenage - Sheffield Wednesday: ÇŞ X2 & 3,5 Alt @ 1.83; Crawley Town - Barnet: KG Var @ 1.68 |
| 43 | `KUPON_43_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.27 | 0.1643 | Sheffield United - Southampton: 2Y 1,5 Üst @ 1.95; Cardiff City - Preston North End: MS 1 @ 1.85; Crawley Town - Barnet: ÇŞ X2 & 1,5 Üst @ 1.46 |
| 44 | `KUPON_44_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.15 | 0.1656 | Bristol City - Wrexham: KG Yok @ 2.08; Chapecoense - Palmeiras: MS 2 @ 1.92; Cardiff City - Preston North End: 3,5 Alt @ 1.29 |
| 45 | `KUPON_45_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.24 | 0.1608 | Glasgow Rangers - Aberdeen: İY 1 @ 1.75; Stevenage - Sheffield Wednesday: 2,5 Alt @ 1.75; Arsenal - Borussia Dortmund: 2,5 Üst @ 1.71 |
| 46 | `KUPON_46_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.24 | 0.1606 | Manchester City - SSC Napoli: MS 1 & 2,5 Üst @ 1.83; Port Vale - Northampton Town: ÇŞ 1X & 3,5 Alt @ 1.54; Bristol City - Wrexham: 2,5 Alt @ 1.86 |
| 47 | `KUPON_47_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.17 | 0.1636 | Bristol City - Wrexham: TG 2-3 @ 1.98; Stevenage - Sheffield Wednesday: 2Y KG Yok @ 1.28; Slovan Bratislava - Real Betis: İY/MS 2/2 @ 2.04 |
| 48 | `KUPON_48_KESKIN_3LU_YUKSEK_ORAN` | `KESKIN_3LU_YUKSEK_ORAN` | 3 | 5.21 | 0.1629 | Feyenoord - FC Porto: 2Y 1,5 Üst @ 1.81; Port Vale - Northampton Town: TG 2-3 @ 1.97; RB Leipzig - RC Lens: MS 1 & 1,5 Üst @ 1.46 |
| 49 | `KUPON_49_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.15 | 0.0654 | Hibernian - Dundee FC: MS 1 @ 1.63; Cardiff City - Preston North End: 3,5 Alt @ 1.29; Norwich City - Queens Park Rangers: 2,5 Üst @ 1.75; LR Vicenza Virtus - Carrarese: 2Y KG Yok @ 1.26; Slovan Bratislava - Real Betis: Hnd(-1) 2 @ 1.71; Manchester City - SSC Napoli: MS 1 @ 1.28 |
| 50 | `KUPON_50_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.03 | 0.0698 | Real Madrid - PSV Eindhoven: MS 1 & 1,5 Üst @ 1.31; Como 1907 - AEK Athens: Ev 1,5 Üst @ 1.31; Coquimbo Unido - Unión La Calera: MS 1 @ 1.69; Portsmouth - West Ham United: Dep 1,5 Üst @ 1.82; Wolverhampton - Derby County: Ev 1,5 Üst @ 1.44; Sheffield United - Southampton: İY 0,5 Üst @ 1.32 |
| 51 | `KUPON_51_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.35 | 0.0684 | RB Leipzig - RC Lens: 2Y 1 @ 1.78; Bradford City - Barnsley: 2,5 Alt @ 1.88; Real Madrid - PSV Eindhoven: 2,5 Üst @ 1.29; Benevento - Empoli: 2Y KG Yok @ 1.26; Port Vale - Northampton Town: İY 1,5 Alt @ 1.34; Glasgow Rangers - Aberdeen: MS 1 & 1,5 Üst @ 1.42 |
| 52 | `KUPON_52_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.01 | 0.0744 | Palermo - FC Südtirol: Ev 1,5 Üst @ 1.51; LR Vicenza Virtus - Carrarese: İY 1,5 Alt @ 1.35; Sheffield United - Southampton: KG Var @ 1.60; Slovan Bratislava - Real Betis: MS 2 @ 1.24; Blackpool - Leicester City: MS 2 @ 1.78; Glasgow Rangers - Aberdeen: Ev 1,5 Üst @ 1.39 |
| 53 | `KUPON_53_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.01 | 0.0710 | Benevento - Empoli: 2Y KG Yok @ 1.26; Hibernian - Dundee FC: İY 1,5 Alt @ 1.43; Palermo - FC Südtirol: 2Y KG Yok @ 1.29; Bromley - Wycombe Wanderers: 2,5 Alt @ 1.81; Bristol City - Wrexham: 3,5 Alt @ 1.30; Wolverhampton - Derby County: İY 1 @ 1.83 |
| 54 | `KUPON_54_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 10.09 | 0.0707 | Stevenage - Sheffield Wednesday: 3,5 Alt @ 1.25; Manchester City - SSC Napoli: 2,5 Üst @ 1.48; Real Madrid - PSV Eindhoven: Ev 2,5 Üst @ 1.75; Bromley - Wycombe Wanderers: 2Y KG Yok @ 1.29; Como 1907 - AEK Athens: 2,5 Üst @ 1.43; Middlesbrough - Swansea City: Ev 1,5 Üst @ 1.69 |
| 55 | `KUPON_55_AVRUPA_6LI_SISTEM_10X_25X` | `AVRUPA_6LI_SISTEM_10X_25X` | 6 | 7.51 | 0.0944 | Coquimbo Unido - Unión La Calera: 2,5 Alt @ 1.53; Cardiff City - Preston North End: İY 1,5 Alt @ 1.40; Virtus Entella - Hellas Verona: 2,5 Alt @ 1.54; RB Leipzig - RC Lens: 2,5 Üst @ 1.38; LR Vicenza Virtus - Carrarese: 2Y KG Yok @ 1.26; Bristol City - Wrexham: 2Y KG Yok @ 1.31 |

## 3. `(Maç, Tercih)` Kullanım Sıklığı Denetim Tablosu (30 Maç / Maksimum 3/3)

| Saat (TSİ) | Lig | Maç | Tercih | Kullanım | Durum |
| --- | --- | --- | --- | --- | --- |
| 22:00 | İtalya Serie B | Benevento - Empoli | 2Y KG Yok | 3/3 | Uygun |
| 22:00 | İtalya Serie B | Benevento - Empoli | İY 1,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Benevento - Empoli | 3,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Benevento - Empoli | ÇŞ 1X & 3,5 Alt | 1/3 | Uygun |
| 22:00 | İtalya Serie B | Benevento - Empoli | 2,5 Alt | 1/3 | Uygun |
| 22:00 | İtalya Serie B | Cesena - Ascoli | 2Y KG Yok | 3/3 | Uygun |
| 22:00 | İtalya Serie B | Cesena - Ascoli | 3,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Cesena - Ascoli | İY 1,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Cesena - Ascoli | 2,5 Alt | 1/3 | Uygun |
| 22:00 | İtalya Serie B | Cesena - Ascoli | TG 2-3 | 1/3 | Uygun |
| 22:00 | İtalya Serie B | LR Vicenza Virtus - Carrarese | 2Y KG Yok | 3/3 | Uygun |
| 22:00 | İtalya Serie B | LR Vicenza Virtus - Carrarese | İY 1,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | LR Vicenza Virtus - Carrarese | 2,5 Alt | 1/3 | Uygun |
| 22:00 | İtalya Serie B | LR Vicenza Virtus - Carrarese | KG Yok | 1/3 | Uygun |
| 22:00 | İtalya Serie B | Palermo - FC Südtirol | 2Y KG Yok | 3/3 | Uygun |
| 22:00 | İtalya Serie B | Palermo - FC Südtirol | MS 1 | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Palermo - FC Südtirol | Ev 1,5 Üst | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Palermo - FC Südtirol | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Palermo - FC Südtirol | 2Y 1 | 1/3 | Uygun |
| 22:00 | İtalya Serie B | Virtus Entella - Hellas Verona | İY 1,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Virtus Entella - Hellas Verona | 2,5 Alt | 2/3 | Uygun |
| 22:00 | İtalya Serie B | Virtus Entella - Hellas Verona | ÇŞ X2 & 3,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere League One | Blackpool - Leicester City | ÇŞ X2 & 1,5 Üst | 2/3 | Uygun |
| 22:45 | İngiltere League One | Blackpool - Leicester City | MS 2 | 2/3 | Uygun |
| 22:45 | İngiltere League One | Blackpool - Leicester City | 2,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere League One | Blackpool - Leicester City | KG Var | 1/3 | Uygun |
| 22:45 | İngiltere League One | Blackpool - Leicester City | Dep 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | 2Y KG Yok | 2/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | 3,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | MS 1 | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | TG 2-3 | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | ÇŞ 1X & 3,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bradford City - Barnsley | 2,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | 2Y KG Yok | 3/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | 3,5 Alt | 3/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | KG Yok | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | 2,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Bristol City - Wrexham | TG 2-3 | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bromley - Wycombe Wanderers | 2Y KG Yok | 3/3 | Uygun |
| 22:45 | İngiltere League One | Bromley - Wycombe Wanderers | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Bromley - Wycombe Wanderers | 3,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Bromley - Wycombe Wanderers | ÇŞ X2 & 3,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere League One | Bromley - Wycombe Wanderers | 2,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Cardiff City - Preston North End | 3,5 Alt | 3/3 | Uygun |
| 22:45 | İngiltere Championship | Cardiff City - Preston North End | 2Y KG Yok | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Cardiff City - Preston North End | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Cardiff City - Preston North End | ÇŞ 1X & 3,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Cardiff City - Preston North End | MS 1 | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Charlton Athletic - Lincoln City | 2Y KG Yok | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Charlton Athletic - Lincoln City | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Charlton Athletic - Lincoln City | 2,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Charlton Athletic - Lincoln City | KG Yok | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Crawley Town - Barnet | ÇŞ X2 & 1,5 Üst | 2/3 | Uygun |
| 22:45 | İngiltere League Two | Crawley Town - Barnet | KG Var | 2/3 | Uygun |
| 22:45 | İngiltere League Two | Crawley Town - Barnet | Dep 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Crawley Town - Barnet | MS 2 | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Crawley Town - Barnet | 2,5 Üst | 1/3 | Uygun |
| 22:45 | İskoçya Premiership | Hibernian - Dundee FC | 3,5 Alt | 2/3 | Uygun |
| 22:45 | İskoçya Premiership | Hibernian - Dundee FC | 2Y KG Yok | 2/3 | Uygun |
| 22:45 | İskoçya Premiership | Hibernian - Dundee FC | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İskoçya Premiership | Hibernian - Dundee FC | MS 1 | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Middlesbrough - Swansea City | MS 1 | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Middlesbrough - Swansea City | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Middlesbrough - Swansea City | Ev 1,5 Üst | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Middlesbrough - Swansea City | 2Y 1 | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Norwich City - Queens Park Rangers | İY 0,5 Üst | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Norwich City - Queens Park Rangers | ÇŞ 1X & 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Norwich City - Queens Park Rangers | KG Var | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Norwich City - Queens Park Rangers | 2,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Port Vale - Northampton Town | İY 1,5 Alt | 3/3 | Uygun |
| 22:45 | İngiltere League Two | Port Vale - Northampton Town | ÇŞ 1X & 3,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League Two | Port Vale - Northampton Town | 2,5 Alt | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Port Vale - Northampton Town | MS 1 | 1/3 | Uygun |
| 22:45 | İngiltere League Two | Port Vale - Northampton Town | TG 2-3 | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Portsmouth - West Ham United | KG Var | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Portsmouth - West Ham United | 2,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Portsmouth - West Ham United | ÇŞ X2 & 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Portsmouth - West Ham United | Dep 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Sheffield United - Southampton | İY 0,5 Üst | 3/3 | Uygun |
| 22:45 | İngiltere Championship | Sheffield United - Southampton | KG Var | 2/3 | Uygun |
| 22:45 | İngiltere Championship | Sheffield United - Southampton | 2,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Sheffield United - Southampton | ÇŞ 1X & 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere Championship | Sheffield United - Southampton | 2Y 1,5 Üst | 1/3 | Uygun |
| 22:45 | İngiltere League One | Stevenage - Sheffield Wednesday | 3,5 Alt | 3/3 | Uygun |
| 22:45 | İngiltere League One | Stevenage - Sheffield Wednesday | 2Y KG Yok | 2/3 | Uygun |
| 22:45 | İngiltere League One | Stevenage - Sheffield Wednesday | İY 1,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Stevenage - Sheffield Wednesday | 2,5 Alt | 2/3 | Uygun |
| 22:45 | İngiltere League One | Stevenage - Sheffield Wednesday | ÇŞ X2 & 3,5 Alt | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Arsenal - Borussia Dortmund | MS 1 | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Arsenal - Borussia Dortmund | MS 1 & 1,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Arsenal - Borussia Dortmund | Ev 1,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Arsenal - Borussia Dortmund | 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | MS 1 | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | Ev 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | 2,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | 2Y 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | Hnd(-1) 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | MS 1 & 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Como 1907 - AEK Athens | İY 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Feyenoord - FC Porto | İY 0,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Feyenoord - FC Porto | KG Var | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Feyenoord - FC Porto | ÇŞ X2 & 1,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Feyenoord - FC Porto | 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Feyenoord - FC Porto | 2Y 1,5 Üst | 1/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | MS 1 | 2/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | Ev 1,5 Üst | 2/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | 2Y KG Yok | 2/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | 2Y 1 | 1/3 | Uygun |
| 23:00 | İskoçya Premiership | Glasgow Rangers - Aberdeen | İY 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | Ev 1,5 Üst | 3/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | MS 1 | 3/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | 2,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | İY 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | 2Y 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Manchester City - SSC Napoli | MS 1 & 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | RB Leipzig - RC Lens | 2,5 Üst | 3/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | RB Leipzig - RC Lens | Ev 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | RB Leipzig - RC Lens | MS 1 | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | RB Leipzig - RC Lens | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | RB Leipzig - RC Lens | 2Y 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | MS 1 & 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | 2,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | 2Y 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | İY 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | MS 1 & 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | Hnd(-1) 1 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Real Madrid - PSV Eindhoven | Ev 2,5 Üst | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | MS 2 | 3/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | Dep 1,5 Üst | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | 2Y KG Yok | 2/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | 2Y 2 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | İY 2 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | İY/MS 2/2 | 1/3 | Uygun |
| 23:00 | UEFA Şampiyonlar Ligi | Slovan Bratislava - Real Betis | Hnd(-1) 2 | 1/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | MS 1 | 2/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | 2Y KG Yok | 2/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | Ev 1,5 Üst | 2/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | 2Y 1 | 1/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | MS 1 & 1,5 Üst | 1/3 | Uygun |
| 23:00 | İngiltere Championship | Wolverhampton - Derby County | İY 1 | 1/3 | Uygun |
| 00:00 | Brezilya Serie A | Chapecoense - Palmeiras | ÇŞ X2 & 1,5 Üst | 1/3 | Uygun |
| 00:00 | Brezilya Serie A | Chapecoense - Palmeiras | 2,5 Üst | 1/3 | Uygun |
| 00:00 | Brezilya Serie A | Chapecoense - Palmeiras | KG Var | 1/3 | Uygun |
| 00:00 | Brezilya Serie A | Chapecoense - Palmeiras | MS 2 | 1/3 | Uygun |
| 01:00 | Şili Kupası | Coquimbo Unido - Unión La Calera | ÇŞ 1X & 3,5 Alt | 2/3 | Uygun |
| 01:00 | Şili Kupası | Coquimbo Unido - Unión La Calera | İY 1,5 Alt | 2/3 | Uygun |
| 01:00 | Şili Kupası | Coquimbo Unido - Unión La Calera | 2,5 Alt | 2/3 | Uygun |
| 01:00 | Şili Kupası | Coquimbo Unido - Unión La Calera | MS 1 | 1/3 | Uygun |
