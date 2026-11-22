# 22 Kasım 2026 Pazar — Her Olasılık Katmanında Maksimum Oranlı 30 Kupon Portföyü (`QuantFoot-v8.0`)

- **Üretim Zamanı:** `22.11.2026 12:48 TSİ` · **Kapsam:** Başlamamış (`≥ 13:00 TSİ`) maçlardan **`30` farklı kupon**, toplam **`295` sıfır-tekrarlı bacak** (`165` farklı maç).
- **Mimari:** Tüm olasılık spektrumu **6 ayrı olasılık ve strateji katmanına (her katmanda 5'er kupon = 30 kupon)** bölünmüş ve her katmanda o olasılık bandının izin verdiği **maksimum birleşik Nesine oranı** optimize edilmiştir.
- **Kurallar:** Tüm bacaklar `≥ 1.20` canlı Nesine oranlı, MBS uyumlu ve 30 kuponun tamamında **aynı `(Maç, Tercih)` ikilisi yalnızca 1 kez** kullanılmıştır (`0` tekrar).

## 1. 30 Kuponluk Hızlı Özet Tablosu

| Kupon | Olasılık / Strateji Katmanı | Maç | Canlı Nesine Toplam Oran | Ort. Bacak Olasılığı | Birleşik Tutma Olasılığı |
|---|---|---:|---:|---:|---:|
| **Kupon 1** | GRUP 1 — Ultra-Yüksek Olasılık Bandı | 9 | **7.90x** | %70.6 | %4.3356 |
| **Kupon 2** | GRUP 1 — Ultra-Yüksek Olasılık Bandı | 9 | **7.34x** | %70.2 | %4.1470 |
| **Kupon 3** | GRUP 1 — Ultra-Yüksek Olasılık Bandı | 9 | **6.49x** | %69.7 | %3.8981 |
| **Kupon 4** | GRUP 1 — Ultra-Yüksek Olasılık Bandı | 9 | **6.93x** | %68.2 | %3.1949 |
| **Kupon 5** | GRUP 1 — Ultra-Yüksek Olasılık Bandı | 9 | **6.64x** | %68.1 | %3.1305 |
| **Kupon 6** | GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı | 10 | **29.77x** | %65.0 | %1.3391 |
| **Kupon 7** | GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı | 10 | **22.43x** | %63.9 | %1.1266 |
| **Kupon 8** | GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı | 10 | **17.81x** | %64.3 | %1.1995 |
| **Kupon 9** | GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı | 10 | **13.95x** | %65.1 | %1.3587 |
| **Kupon 10** | GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı | 10 | **17.50x** | %63.7 | %1.0899 |
| **Kupon 11** | GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı | 10 | **65.51x** | %59.5 | %0.5492 |
| **Kupon 12** | GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı | 10 | **48.33x** | %59.7 | %0.5754 |
| **Kupon 13** | GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı | 10 | **41.85x** | %59.8 | %0.5805 |
| **Kupon 14** | GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı | 10 | **33.01x** | %60.7 | %0.6760 |
| **Kupon 15** | GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı | 10 | **35.94x** | %59.3 | %0.5325 |
| **Kupon 16** | GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı | 10 | **283.90x** | %52.4 | %0.1556 |
| **Kupon 17** | GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı | 10 | **244.03x** | %51.5 | %0.1303 |
| **Kupon 18** | GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı | 10 | **167.02x** | %52.8 | %0.1681 |
| **Kupon 19** | GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı | 10 | **149.82x** | %53.4 | %0.1858 |
| **Kupon 20** | GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı | 10 | **123.55x** | %53.3 | %0.1836 |
| **Kupon 21** | GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı | 10 | **1,084.12x** | %45.5 | %0.0375 |
| **Kupon 22** | GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı | 10 | **629.59x** | %46.3 | %0.0445 |
| **Kupon 23** | GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı | 10 | **481.39x** | %47.4 | %0.0558 |
| **Kupon 24** | GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı | 10 | **534.97x** | %46.1 | %0.0426 |
| **Kupon 25** | GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı | 10 | **493.99x** | %46.8 | %0.0492 |
| **Kupon 26** | GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı | 10 | **210,591.77x** | %28.4 | %0.0003 |
| **Kupon 27** | GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı | 10 | **108,085.27x** | %28.9 | %0.0004 |
| **Kupon 28** | GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı | 10 | **103,118.81x** | %27.9 | %0.0003 |
| **Kupon 29** | GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı | 10 | **54,857.50x** | %28.9 | %0.0004 |
| **Kupon 30** | GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı | 10 | **63,443.41x** | %27.9 | %0.0003 |

---

## GRUP 1 — Ultra-Yüksek Olasılık Bandı (P ≥ %67 · Keskin Borsa Zırhlı Maksimum Oran)

### KUPON 1 — Ultra-Yüksek Olasılık Bandı #1
**Canlı Nesine Toplam Oran:** **`7.90x`** · **Maç Sayısı:** `9` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%70.6` · **Birleşik Olasılık:** `%4.3356`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:30 | İtalya Serie A | Juventus - Venezia | **MS 1** | 1.24 | %71.7 | 1.40 | 1 | 2.28-0.75 (2-0) | Matchbook + Smarkets |
| 2 | 22.11 15:30 | Norveç Eliteserien, Düş./Yük. | Odds BK - Bryne | **KG Var** | 1.32 | %67.5 | 1.48 | 2 | 1.88-1.50 (1-1) | OddsMath |
| 3 | 22.11 15:30 | Çekya 2. Lig | SK Kladno - Jihlava | **KG Var** | 1.31 | %68.7 | 1.46 | 3 | 1.69-1.65 (1-1) | OddsMath |
| 4 | 22.11 17:30 | Almanya Bundesliga | Augsburg - Mainz | **2.5 Üst** | 1.28 | %68.5 | 1.46 | 1 | 1.71-1.80 (1-1) | Matchbook + Smarkets |
| 5 | 22.11 18:00 | Belçika Pro Lig | Kortrijk - U. S. Gilloise | **MS 2** | 1.21 | %71.3 | 1.40 | 1 | 0.79-2.31 (0-2) | Matchbook + Smarkets |
| 6 | 22.11 18:15 | İspanya La Liga | Santander - R. Sociedad | **2.5 Üst** | 1.22 | %71.9 | 1.39 | 1 | 1.62-2.09 (1-2) | Matchbook + Smarkets |
| 7 | 22.11 19:15 | Fransa Ligue 1 | Lorient - Rennes | **1.5 Üst** | 1.20 | %75.7 | 1.32 | 1 | 1.28-1.43 (1-1) | Matchbook + Smarkets |
| 8 | 22.11 19:30 | İspanya Segunda RFEF | Recreativo - Badajoz | **İY 1.5 Alt** | 1.28 | %69.1 | 1.45 | 3 | 1.79-0.72 (1-0) | OddsMath |
| 9 | 22.11 20:00 | İtalya Serie A | AC Milan - Frosinone | **2.5 Üst** | 1.27 | %71.1 | 1.41 | 1 | 2.44-1.23 (2-1) | Matchbook + Smarkets |

### KUPON 2 — Ultra-Yüksek Olasılık Bandı #2
**Canlı Nesine Toplam Oran:** **`7.34x`** · **Maç Sayısı:** `9` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%70.2` · **Birleşik Olasılık:** `%4.1470`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Segunda RFEF | Utebo - Calamocha | **MS 1** | 1.34 | %68.6 | 1.46 | 3 | 2.03-0.70 (2-0) | OddsMath |
| 2 | 22.11 15:00 | İngiltere Championship | Burnley - Blackburn R. | **İY 0.5 Üst** | 1.21 | %71.7 | 1.40 | 1 | 1.72-1.16 (1-1) | Matchbook + Smarkets |
| 3 | 22.11 15:30 | Almanya 3. Lig | Stuttgart II - Ingolstadt | **KG Var** | 1.27 | %69.2 | 1.45 | 2 | 1.60-1.85 (1-1) | OddsMath |
| 4 | 22.11 19:30 | Polonya Ekstraklasa | Wisla Plock - L. Varşova | **İY 0.5 Üst** | 1.21 | %71.6 | 1.40 | 2 | 1.31-1.57 (1-1) | OddsMath |
| 5 | 22.11 20:30 | İspanya 2. Lig | Celta Vigo B - Real Valladolid | **İY 0.5 Üst** | 1.21 | %71.8 | 1.39 | 1 | 1.23-1.66 (1-1) | Matchbook |
| 6 | 22.11 23:00 | İspanya 2. Lig | Burgos - Albacete | **1.5 Üst** | 1.20 | %72.2 | 1.39 | 1 | 1.50-1.02 (1-1) | Matchbook + Smarkets |
| 7 | 22.11 23:00 | İspanya La Liga | Getafe - Atl Madrid | **1.5 Üst** | 1.21 | %71.6 | 1.40 | 1 | 0.72-1.80 (0-1) | Matchbook + Smarkets |
| 8 | 23.11 00:00 | ABD Major Lig Playoff | Nashville SC - Cincinnati | **2.5 Üst** | 1.27 | %68.4 | 1.46 | 1 | 2.42-1.10 (2-1) | Matchbook |
| 9 | 23.11 00:30 | Brezilya Serie A | Fluminense - Mirassol SP | **İY 1.5 Alt** | 1.32 | %67.1 | 1.49 | 1 | 1.87-0.92 (1-1) | Matchbook |

### KUPON 3 — Ultra-Yüksek Olasılık Bandı #3
**Canlı Nesine Toplam Oran:** **`6.49x`** · **Maç Sayısı:** `9` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%69.7` · **Birleşik Olasılık:** `%3.8981`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 15:30 | Almanya Bundesliga 2 | E. Cottbus - Hertha Berlin | **4.5 Alt** | 1.21 | %71.6 | 1.40 | 1 | 1.25-2.33 (1-2) | Matchbook |
| 2 | 22.11 15:30 | Belçika Pro Lig | SK Beveren - KAA Gent | **İY 0.5 Üst** | 1.21 | %70.4 | 1.42 | 1 | 1.13-1.65 (1-1) | Matchbook + Smarkets |
| 3 | 22.11 17:00 | İtalya Serie B | AS Avellino 1912 - Mantova 1911 | **İY 1.5 Alt** | 1.26 | %67.8 | 1.47 | 1 | 1.40-1.19 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 17:00 | İtalya Serie A | Bologna - Udinese | **İY 0.5 Üst** | 1.23 | %69.5 | 1.44 | 1 | 1.76-0.94 (1-0) | Matchbook + Smarkets |
| 5 | 22.11 18:15 | İspanya 2. Lig | S. Gijon - Las Palmas | **İY 0.5 Üst** | 1.26 | %68.8 | 1.45 | 1 | 1.52-1.13 (1-1) | Matchbook + Smarkets |
| 6 | 22.11 19:30 | Bosna Hersek Premier Lig | Sarajevo - Siroki Brijeg | **MS 1** | 1.21 | %70.4 | 1.42 | 3 | 1.93-0.55 (1-0) | OddsMath |
| 7 | 22.11 20:30 | İspanya 2. Lig | Girona - Eibar | **İY 0.5 Üst** | 1.21 | %71.3 | 1.40 | 1 | 1.79-1.05 (1-1) | Matchbook |
| 8 | 22.11 20:30 | İspanya La Liga | Osasuna - Malaga | **İY 1.5 Alt** | 1.25 | %68.8 | 1.45 | 1 | 1.60-0.92 (1-0) | Matchbook + Smarkets |
| 9 | 22.11 22:45 | İtalya Serie A | Atalanta - Inter | **2.5 Üst** | 1.24 | %69.2 | 1.45 | 1 | 1.21-2.35 (1-2) | Matchbook + Smarkets |

### KUPON 4 — Ultra-Yüksek Olasılık Bandı #4
**Canlı Nesine Toplam Oran:** **`6.93x`** · **Maç Sayısı:** `9` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%68.2` · **Birleşik Olasılık:** `%3.1949`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 16:30 | Hollanda Eredivisie | Ajax - ADO Den Haag | **MS 1 & 2.5 Üst** | 1.25 | %67.8 | 1.48 | 1 | 3.19-0.82 (3-0) | Smarkets |
| 2 | 22.11 16:30 | Tunus 1. Lig | ES Zarzis - US Ben Guerdane | **2.5 Alt** | 1.21 | %68.6 | 1.46 | 3 | 1.08-0.87 (1-0) | OddsMath |
| 3 | 22.11 17:00 | İtalya Serie A | Sassuolo - Genoa | **İY 0.5 Üst** | 1.24 | %68.6 | 1.46 | 1 | 1.31-1.34 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 17:00 | İsviçre Yükselme 1.Ligi | Schaffhausen - SC Cham | **KG Var** | 1.25 | %68.0 | 1.47 | 3 | 1.96-1.46 (1-1) | OddsMath |
| 5 | 22.11 17:30 | İsviçre Yükselme 1.Ligi | Lugano II - Breitenrain | **KG Var** | 1.25 | %67.6 | 1.48 | 3 | 1.51-1.85 (1-1) | OddsMath |
| 6 | 22.11 19:15 | İtalya Serie B | SS Arezzo - Padova | **İY 1.5 Alt** | 1.23 | %69.0 | 1.45 | 1 | 1.37-1.15 (1-1) | Matchbook |
| 7 | 22.11 19:30 | İspanya Segunda RFEF | Ciudad De Lucena - Betis D. Balompie | **İY 1.5 Alt** | 1.27 | %67.3 | 1.48 | 3 | 1.26-1.36 (1-1) | OddsMath |
| 8 | 22.11 19:30 | İtalya Serie C | Forli - Reggiana | **İY 1.5 Alt** | 1.23 | %68.4 | 1.46 | 3 | 1.25-1.31 (1-1) | OddsMath |
| 9 | 23.11 04:10 | Guatemala Ulusal Lig, Açılış | CD Marquense - Aurora | **İY 1.5 Alt** | 1.23 | %68.5 | 1.46 | 3 | 1.69-0.86 (1-0) | OddsMath |

### KUPON 5 — Ultra-Yüksek Olasılık Bandı #5
**Canlı Nesine Toplam Oran:** **`6.64x`** · **Maç Sayısı:** `9` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%68.1` · **Birleşik Olasılık:** `%3.1305`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | İspanya Segunda RFEF | Pena Deportiva - Lorca Deportiva | **İY 0.5 Üst** | 1.24 | %67.2 | 1.49 | 3 | 1.14-1.41 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | Alaves II - Compostela | **İY 1.5 Alt** | 1.21 | %68.8 | 1.45 | 3 | 1.61-0.92 (1-0) | OddsMath |
| 3 | 22.11 14:30 | İtalya Serie C | Scafatese Calcio 1922 - Foggia | **İY 1.5 Alt** | 1.24 | %67.3 | 1.48 | 3 | 1.37-1.25 (1-1) | OddsMath |
| 4 | 22.11 16:30 | İtalya Serie C | US Pianese - AS Gubbio 1910 | **İY 1.5 Alt** | 1.22 | %68.4 | 1.46 | 3 | 1.58-0.97 (1-1) | OddsMath |
| 5 | 22.11 17:00 | İtalya Serie C | Calcio Catania - SSC Bari | **İY 1.5 Alt** | 1.22 | %68.7 | 1.46 | 3 | 1.61-0.92 (1-0) | OddsMath |
| 6 | 22.11 18:00 | İspanya Primera RFEF | Barakaldo - Unionistas | **İY 0.5 Üst** | 1.25 | %67.2 | 1.49 | 3 | 1.67-0.87 (1-0) | OddsMath |
| 7 | 22.11 18:30 | İspanya Segunda RFEF | Navalcarnero - Gimnastica Segoviana | **İY 0.5 Üst** | 1.22 | %68.4 | 1.46 | 3 | 1.46-1.17 (1-1) | OddsMath |
| 8 | 22.11 19:30 | İspanya Segunda RFEF | SD Logrones - CD Arnedo | **İY 1.5 Alt** | 1.21 | %69.2 | 1.45 | 3 | 1.64-0.86 (1-0) | OddsMath |
| 9 | 22.11 20:30 | Belçika Pro Lig | Anderlecht - O. H. Leuven | **MS 1** | 1.30 | %67.3 | 1.49 | 1 | 2.27-0.93 (2-0) | Matchbook + Smarkets |


---

## GRUP 2 — Yüksek Olasılık & Yapısal Gol/KG Bandı (P %62–%69 · 0 Taraf MS · Maksimum Oran)

### KUPON 6 — Yüksek Olasılık & Yapısal Gol/KG Bandı #1
**Canlı Nesine Toplam Oran:** **`29.77x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%65.0` · **Birleşik Olasılık:** `%1.3391`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 15:30 | Norveç Eliteserien, Düş./Yük. | Odds BK - Bryne | **2.5 Üst** | 1.34 | %65.4 | 1.53 | 2 | 1.88-1.50 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Almanya 3. Lig | Stuttgart II - Ingolstadt | **2.5 Üst** | 1.31 | %66.4 | 1.51 | 2 | 1.60-1.85 (1-1) | OddsMath |
| 3 | 22.11 16:00 | İngiltere U21 Premier Lig Kupası | Brentford U21 - Hull City U21 | **İY 1.5 Üst** | 1.57 | %62.0 | 1.61 | 3 | 2.76-1.90 (2-1) | OddsMath |
| 4 | 22.11 16:00 | İngiltere U21 Premier Lig Kupası | Peterborough Utd U21 - Luton Town U21 | **İY 1.5 Üst** | 1.49 | %65.6 | 1.53 | 3 | 3.23-1.74 (2-1) | OddsMath |
| 5 | 22.11 17:00 | İngiltere U21 Premier Lig Kupası | Stoke City U21 - Stockport U21 | **İY 1.5 Üst** | 1.51 | %63.6 | 1.57 | 3 | 2.78-2.02 (2-1) | OddsMath |
| 6 | 22.11 19:15 | Fransa Ligue 1 | Lorient - Rennes | **İY 0.5 Üst** | 1.28 | %69.4 | 1.44 | 1 | 1.28-1.43 (1-1) | Matchbook + Smarkets |
| 7 | 22.11 19:30 | Almanya Bundesliga | Werder Bremen - Hamburg | **2.5 Üst** | 1.40 | %62.4 | 1.60 | 1 | 2.06-1.15 (2-1) | Matchbook + Smarkets |
| 8 | 22.11 20:00 | İtalya Serie A | AC Milan - Frosinone | **KG Var** | 1.34 | %66.1 | 1.51 | 1 | 2.44-1.23 (2-1) | Matchbook + Smarkets |
| 9 | 22.11 23:00 | Peru Prmr Ligi, Kapanış | Huancayo - U. Deportes | **KG Var** | 1.47 | %64.0 | 1.56 | 3 | 1.75-1.37 (1-1) | OddsMath |
| 10 | 23.11 01:30 | Brezilya Serie A | Bragantino - Vasco Da G. | **İY 1.5 Alt** | 1.36 | %65.1 | 1.54 | 1 | 1.52-1.41 (1-1) | Matchbook |

### KUPON 7 — Yüksek Olasılık & Yapısal Gol/KG Bandı #2
**Canlı Nesine Toplam Oran:** **`22.43x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%63.9` · **Birleşik Olasılık:** `%1.1266`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 16:30 | Avusturya Bundesliga | Wolfsberger - SV Ried | **KG Var** | 1.38 | %63.2 | 1.58 | 2 | 1.45-1.63 (1-1) | OddsMath |
| 2 | 22.11 18:15 | İspanya La Liga | Santander - R. Sociedad | **2.5 Üst & KG Var** | 1.39 | %63.1 | 1.58 | 1 | 1.62-2.09 (1-2) | Matchbook + Smarkets |
| 3 | 22.11 18:30 | Almanya 3. Lig | Saarbrucken - W. Wiesbaden | **KG Var** | 1.34 | %65.2 | 1.53 | 2 | 1.61-1.57 (1-1) | OddsMath |
| 4 | 22.11 19:30 | İngiltere Premier Lig | Liverpool - Man. Utd | **2.5 Üst** | 1.32 | %65.0 | 1.54 | 1 | 2.11-1.23 (2-1) | Matchbook + Smarkets |
| 5 | 22.11 22:00 | Brezilya Serie A | Paranaense - Clube do Remo | **İY 1.5 Alt** | 1.37 | %64.0 | 1.56 | 1 | 2.10-0.89 (2-0) | Matchbook |
| 6 | 22.11 22:45 | İtalya Serie A | Atalanta - Inter | **KG Var** | 1.35 | %65.0 | 1.54 | 1 | 1.21-2.35 (1-2) | Matchbook + Smarkets |
| 7 | 22.11 22:45 | Fransa Ligue 1 | Marsilya - Le Mans | **2.5 Üst** | 1.36 | %63.2 | 1.58 | 1 | 2.28-0.97 (2-0) | Matchbook + Smarkets |
| 8 | 23.11 00:00 | ABD Major Lig Playoff | Nashville SC - Cincinnati | **KG Var** | 1.40 | %62.4 | 1.60 | 1 | 2.42-1.10 (2-1) | Matchbook |
| 9 | 23.11 02:07 | Meksika Prmr Ligi, Açılış | CD Guadalajara - Cruz Azul | **KG Var** | 1.37 | %64.0 | 1.56 | 2 | 1.69-1.51 (1-1) | Matchbook |
| 10 | 23.11 02:30 | Şili Premier Lig | Deportes Limache - D. La Serena | **KG Var** | 1.37 | %63.4 | 1.58 | 3 | 1.73-1.40 (1-1) | OddsMath |

### KUPON 8 — Yüksek Olasılık & Yapısal Gol/KG Bandı #3
**Canlı Nesine Toplam Oran:** **`17.81x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%64.3` · **Birleşik Olasılık:** `%1.1995`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Rusya Premier Lig | D. Moskova - Krasnodar | **İY 1.5 Alt** | 1.35 | %63.4 | 1.58 | 1 | 1.64-1.23 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Almanya Bundesliga 2 | E. Cottbus - Hertha Berlin | **KG Var** | 1.31 | %65.6 | 1.53 | 1 | 1.25-2.33 (1-2) | Matchbook |
| 3 | 22.11 15:30 | Almanya Bundesliga 2 | Kaiserslautern - D. Dresden | **İY 1.5 Alt** | 1.37 | %63.1 | 1.59 | 1 | 1.61-1.27 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 16:00 | İspanya La Liga | Barcelona - Villarreal | **KG Var** | 1.33 | %64.6 | 1.55 | 1 | 3.46-1.05 (3-1) | Matchbook + Smarkets |
| 5 | 22.11 16:30 | Avusturya Bundesliga | Altach - Sturm Graz | **İY 1.5 Alt** | 1.34 | %63.8 | 1.57 | 2 | 1.14-1.71 (1-1) | Matchbook + Smarkets |
| 6 | 22.11 19:00 | Avusturya Bundesliga | Austria Wien - Salzburg | **2.5 Üst** | 1.36 | %62.5 | 1.60 | 2 | 1.15-2.07 (1-2) | Matchbook + Smarkets |
| 7 | 22.11 20:00 | Slovakya Superliga | Dunajska S. - KFC Komarno | **2.5 Üst** | 1.31 | %64.3 | 1.55 | 3 | 2.32-1.02 (2-1) | OddsMath |
| 8 | 22.11 20:30 | Yunanistan Süper Lig | PAOK - AE Kifisia | **MS 1 & 1.5 Üst** | 1.37 | %62.8 | 1.59 | 3 | 2.40-0.79 (2-0) | Matchbook + Smarkets |
| 9 | 22.11 22:00 | Arjantin Primera Lpf, Clausura Playoff | Rosario C. - Gimnasia Y. | **İY 1.5 Alt** | 1.32 | %65.6 | 1.52 | 2 | 2.09-0.64 (2-0) | Matchbook + Smarkets |
| 10 | 22.11 23:00 | İspanya 2. Lig | Burgos - Albacete | **İY 0.5 Üst** | 1.28 | %66.9 | 1.49 | 1 | 1.50-1.02 (1-1) | Matchbook + Smarkets |

### KUPON 9 — Yüksek Olasılık & Yapısal Gol/KG Bandı #4
**Canlı Nesine Toplam Oran:** **`13.95x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%65.1` · **Birleşik Olasılık:** `%1.3587`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 17:00 | İsviçre Yükselme 1.Ligi | Biel Bienne - Bellinzona | **KG Var** | 1.35 | %63.1 | 1.58 | 3 | 2.36-1.14 (2-1) | OddsMath |
| 2 | 22.11 17:00 | İngiltere Premier Lig | Hull City - Brighton | **İY 1.5 Alt** | 1.36 | %62.6 | 1.60 | 1 | 0.87-2.06 (0-2) | Matchbook + Smarkets |
| 3 | 22.11 17:00 | İtalya Serie A | Sassuolo - Genoa | **İY 1.5 Alt** | 1.27 | %67.0 | 1.49 | 1 | 1.31-1.34 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 18:00 | Yunanistan Süper Lig | Paneitolikos - Volos | **İY 0.5 Üst** | 1.27 | %66.8 | 1.50 | 3 | 1.35-1.17 (1-1) | Matchbook |
| 5 | 22.11 19:00 | Türkiye 1. Lig | Bursaspor - Sivasspor | **2.5 Üst** | 1.28 | %65.4 | 1.53 | 1 | 2.72-0.60 (2-0) | OddsMath |
| 6 | 22.11 19:15 | İtalya Serie B | SS Arezzo - Padova | **İY 0.5 Üst** | 1.27 | %66.8 | 1.50 | 1 | 1.37-1.15 (1-1) | Matchbook |
| 7 | 22.11 20:00 | Yunanistan Süper Lig | Olympiakos - POT Iraklis | **2.5 Üst** | 1.34 | %62.6 | 1.60 | 3 | 2.71-0.52 (2-0) | Matchbook + Smarkets |
| 8 | 22.11 20:30 | Macaristan 1. Ligi | B. Honved - Paksi | **2.5 Üst** | 1.31 | %63.9 | 1.56 | 2 | 1.46-1.84 (1-1) | OddsMath |
| 9 | 22.11 22:30 | İspanya Primera RFEF | CP Cacereno Sad - Logrones | **İY 1.5 Alt** | 1.30 | %65.6 | 1.52 | 3 | 1.38-1.35 (1-1) | OddsMath |
| 10 | 22.11 23:00 | İspanya La Liga | Getafe - Atl Madrid | **İY 0.5 Üst** | 1.27 | %66.8 | 1.50 | 1 | 0.72-1.80 (0-1) | Matchbook + Smarkets |

### KUPON 10 — Yüksek Olasılık & Yapısal Gol/KG Bandı #5
**Canlı Nesine Toplam Oran:** **`17.50x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%63.7` · **Birleşik Olasılık:** `%1.0899`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Segunda RFEF | CD Atletico Paso - Real Valladolid B | **İY 1.5 Alt** | 1.36 | %62.2 | 1.61 | 3 | 1.58-1.37 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | CD Castellon B - UD Castellonense | **KG Var** | 1.36 | %62.5 | 1.60 | 3 | 1.92-1.21 (1-1) | OddsMath |
| 3 | 22.11 15:30 | Almanya Bundesliga 2 | Karlsruhe - Osnabrück | **KG Var** | 1.36 | %62.5 | 1.60 | 1 | 1.62-1.42 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 15:30 | Macaristan 1. Ligi | Zalaegerszeg - Vasas | **KG Var** | 1.36 | %62.2 | 1.61 | 2 | 1.70-1.37 (1-1) | OddsMath |
| 5 | 22.11 16:30 | Hollanda Eredivisie | Ajax - ADO Den Haag | **İY 1** | 1.33 | %63.9 | 1.56 | 1 | 3.19-0.82 (3-0) | Smarkets |
| 6 | 22.11 16:30 | Rusya Premier Lig | Dyn. Makhachkala - S. Moskova | **İY 1.5 Alt** | 1.34 | %63.3 | 1.58 | 1 | 0.84-2.04 (0-2) | OddsMath |
| 7 | 22.11 17:00 | İtalya Serie B | AS Avellino 1912 - Mantova 1911 | **İY 0.5 Üst** | 1.24 | %67.8 | 1.47 | 1 | 1.40-1.19 (1-1) | Matchbook + Smarkets |
| 8 | 22.11 17:00 | Çekya 1. Lig | Slovacko - H. Kralove | **İY 1.5 Alt** | 1.28 | %66.1 | 1.51 | 3 | 1.31-1.38 (1-1) | OddsMath |
| 9 | 22.11 21:15 | Belçika Pro Lig | Lommel SK - Standard Liege | **KG Var** | 1.32 | %64.0 | 1.56 | 1 | 1.37-1.79 (1-1) | Matchbook |
| 10 | 22.11 21:30 | Almanya 3. Lig | Duisburg - H. Rostock | **KG Var** | 1.37 | %62.1 | 1.61 | 2 | 1.64-1.42 (1-1) | OddsMath |


---

## GRUP 3 — Dengeli Keskin Borsa Maksimum Oran Bandı (P %57–%64 · 12-Katman Temiz)

### KUPON 11 — Dengeli Keskin Borsa Maksimum Oran Bandı #1
**Canlı Nesine Toplam Oran:** **`65.51x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%59.5` · **Birleşik Olasılık:** `%0.5492`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Ukrayna Premier Ligi | Dinamo Kiev - Obolon Kiev | **İY 1** | 1.51 | %60.9 | 1.64 | 3 | 2.72-0.61 (2-0) | OddsMath |
| 2 | 22.11 15:00 | İngiltere Championship | Burnley - Blackburn R. | **KG Var** | 1.54 | %57.4 | 1.74 | 1 | 1.72-1.16 (1-1) | Matchbook + Smarkets |
| 3 | 22.11 17:00 | Fransa Ligue 1 | Paris - Angers | **İY 1.5 Alt** | 1.55 | %59.4 | 1.68 | 1 | 2.38-0.74 (2-0) | Matchbook + Smarkets |
| 4 | 22.11 18:00 | İspanya Segunda RFEF | UD Llanera - Ourense | **KG Var** | 1.60 | %57.1 | 1.75 | 3 | 1.51-1.25 (1-1) | OddsMath |
| 5 | 22.11 19:30 | Almanya Bundesliga | Werder Bremen - Hamburg | **KG Var** | 1.48 | %61.0 | 1.64 | 1 | 2.06-1.15 (2-1) | Matchbook + Smarkets |
| 6 | 22.11 19:30 | Polonya Ekstraklasa | Wisla Plock - L. Varşova | **KG Var** | 1.50 | %60.0 | 1.67 | 2 | 1.31-1.57 (1-1) | OddsMath |
| 7 | 22.11 20:00 | İtalya Serie A | AC Milan - Frosinone | **MS 1 & 1.5 Üst** | 1.57 | %57.4 | 1.74 | 1 | 2.44-1.23 (2-1) | Matchbook + Smarkets |
| 8 | 22.11 20:00 | Slovakya Superliga | Dunajska S. - KFC Komarno | **KG Var** | 1.48 | %59.4 | 1.68 | 3 | 2.32-1.02 (2-1) | OddsMath |
| 9 | 22.11 23:00 | Peru Prmr Ligi, Kapanış | Huancayo - U. Deportes | **2.5 Üst** | 1.54 | %60.0 | 1.67 | 3 | 1.75-1.37 (1-1) | OddsMath |
| 10 | 23.11 02:07 | Meksika Prmr Ligi, Açılış | CD Guadalajara - Cruz Azul | **2.5 Üst** | 1.43 | %62.0 | 1.61 | 2 | 1.69-1.51 (1-1) | Matchbook |

### KUPON 12 — Dengeli Keskin Borsa Maksimum Oran Bandı #2
**Canlı Nesine Toplam Oran:** **`48.33x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%59.7` · **Birleşik Olasılık:** `%0.5754`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:30 | İtalya Serie A | Juventus - Venezia | **İY 1.5 Alt** | 1.43 | %60.9 | 1.64 | 1 | 2.28-0.75 (2-0) | Matchbook + Smarkets |
| 2 | 22.11 16:00 | İsveç Allsvenskan | IK Sirius - Djurgarden | **KG Var** | 1.42 | %61.4 | 1.63 | 2 | 1.59-1.41 (1-1) | Matchbook + Smarkets |
| 3 | 22.11 17:00 | Sırbistan Superliga | FK IMT Novi Beograd - Partizan | **KG Var** | 1.45 | %60.5 | 1.65 | 3 | 1.35-1.57 (1-1) | OddsMath |
| 4 | 22.11 18:00 | Belçika Pro Lig | Kortrijk - U. S. Gilloise | **İY 1.5 Alt** | 1.46 | %59.9 | 1.67 | 1 | 0.79-2.31 (0-2) | Matchbook + Smarkets |
| 5 | 22.11 18:45 | Hollanda Eredivisie | Go Ahead Eagles - F. Sittard | **MS 1** | 1.63 | %57.7 | 1.73 | 1 | 1.95-1.06 (1-1) | Smarkets |
| 6 | 22.11 20:15 | İspanya Primera RFEF | Merida AD - Union Irun | **KG Var** | 1.48 | %59.2 | 1.69 | 3 | 1.58-1.29 (1-1) | OddsMath |
| 7 | 22.11 20:30 | İspanya 2. Lig | Celta Vigo B - Real Valladolid | **KG Var** | 1.48 | %58.7 | 1.70 | 1 | 1.23-1.66 (1-1) | Matchbook |
| 8 | 22.11 22:00 | Arjantin Primera Lpf, Clausura Playoff | Rosario C. - Gimnasia Y. | **KG Yok** | 1.53 | %57.2 | 1.75 | 2 | 2.09-0.64 (2-0) | Matchbook + Smarkets |
| 9 | 22.11 23:00 | Peru Prmr Ligi, Kapanış | S. Cristal - CS Cienciano | **KG Var** | 1.47 | %59.6 | 1.68 | 3 | 2.38-1.02 (2-1) | OddsMath |
| 10 | 23.11 01:30 | Brezilya Serie A | Bragantino - Vasco Da G. | **KG Var** | 1.40 | %62.3 | 1.60 | 1 | 1.52-1.41 (1-1) | Matchbook |

### KUPON 13 — Dengeli Keskin Borsa Maksimum Oran Bandı #3
**Canlı Nesine Toplam Oran:** **`41.85x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%59.8` · **Birleşik Olasılık:** `%0.5805`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Türkiye 1. Lig | Batman Petrol - Muğlaspor | **KG Var** | 1.46 | %59.1 | 1.69 | 1 | 2.00-1.09 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Almanya 3. Lig | Stuttgart II - Ingolstadt | **2.5 Üst & KG Var** | 1.48 | %58.2 | 1.72 | 2 | 1.60-1.85 (1-1) | OddsMath |
| 3 | 22.11 16:00 | İsveç Allsvenskan | BK Hacken - IF Elfsborg | **İY 1.5 Alt** | 1.46 | %59.3 | 1.69 | 2 | 1.90-1.23 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 17:30 | Almanya Bundesliga | Augsburg - Mainz | **2.5 Üst & KG Var** | 1.44 | %60.4 | 1.66 | 1 | 1.71-1.80 (1-1) | Matchbook + Smarkets |
| 5 | 22.11 17:30 | Slovakya Superliga | FK Kosice - Skalica | **KG Var** | 1.41 | %61.0 | 1.64 | 3 | 2.08-1.13 (2-1) | OddsMath |
| 6 | 22.11 19:00 | Rusya Premier Lig | Rodina Moscow - L. Moskova | **KG Var** | 1.40 | %61.5 | 1.63 | 1 | 1.46-1.51 (1-1) | OddsMath |
| 7 | 22.11 20:30 | Yunanistan Süper Lig | PAOK - AE Kifisia | **2.5 Üst** | 1.47 | %62.0 | 1.61 | 3 | 2.40-0.79 (2-0) | Matchbook + Smarkets |
| 8 | 22.11 21:15 | Belçika Pro Lig | Lommel SK - Standard Liege | **İY 1.5 Alt** | 1.46 | %58.8 | 1.70 | 1 | 1.37-1.79 (1-1) | Matchbook |
| 9 | 22.11 22:45 | Fransa Ligue 1 | Marsilya - Le Mans | **KG Var** | 1.51 | %57.2 | 1.75 | 1 | 2.28-0.97 (2-0) | Matchbook + Smarkets |
| 10 | 23.11 04:00 | Arjantin Primera Lpf, Clausura Playoff | Instituto - CA Huracan | **İY 0.5 Üst** | 1.44 | %60.2 | 1.66 | 2 | 1.27-0.82 (1-0) | Matchbook |

### KUPON 14 — Dengeli Keskin Borsa Maksimum Oran Bandı #4
**Canlı Nesine Toplam Oran:** **`33.01x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%60.7` · **Birleşik Olasılık:** `%0.6760`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Ukrayna Premier Ligi | Veres Rivne - Bukovina Chernovtsy | **KG Var** | 1.47 | %58.3 | 1.72 | 3 | 1.16-1.70 (1-1) | OddsMath |
| 2 | 22.11 16:00 | İspanya 2. Lig | Cordoba - Real Oviedo | **İY 1.5 Alt** | 1.41 | %60.9 | 1.64 | 1 | 1.79-1.24 (1-1) | Matchbook |
| 3 | 22.11 18:30 | İsveç Allsvenskan | Brommapojkarna - Halmstads | **KG Var** | 1.41 | %60.7 | 1.65 | 2 | 1.66-1.32 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 19:00 | İspanya Segunda RFEF | Arosa SC - SD Eibar B | **KG Var** | 1.44 | %59.4 | 1.68 | 3 | 1.30-1.53 (1-1) | OddsMath |
| 5 | 22.11 19:00 | Avusturya Bundesliga | Austria Wien - Salzburg | **KG Var** | 1.41 | %61.0 | 1.64 | 2 | 1.15-2.07 (1-2) | Matchbook + Smarkets |
| 6 | 22.11 19:00 | İspanya Segunda RFEF | Salamanca - C. Sotelo Puertollano | **MS 1** | 1.40 | %63.7 | 1.57 | 3 | 2.00-0.84 (2-0) | OddsMath |
| 7 | 22.11 19:30 | İngiltere Premier Lig | Liverpool - Man. Utd | **KG Var** | 1.35 | %63.9 | 1.56 | 1 | 2.11-1.23 (2-1) | Matchbook + Smarkets |
| 8 | 22.11 19:30 | İtalya Serie C | Sambenedettese - Perugia | **KG Var** | 1.41 | %60.9 | 1.64 | 3 | 1.38-1.55 (1-1) | OddsMath |
| 9 | 22.11 20:30 | Belçika Pro Lig | Anderlecht - O. H. Leuven | **MS 1 & 1.5 Üst** | 1.47 | %57.9 | 1.73 | 1 | 2.27-0.93 (2-0) | Matchbook + Smarkets |
| 10 | 23.11 01:00 | Kosta Rika Prmr Ligi, Açılış | Inter San Carlos - Sporting San Jose | **KG Var** | 1.42 | %60.4 | 1.66 | 3 | 1.37-1.53 (1-1) | OddsMath |

### KUPON 15 — Dengeli Keskin Borsa Maksimum Oran Bandı #5
**Canlı Nesine Toplam Oran:** **`35.94x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%59.3` · **Birleşik Olasılık:** `%0.5325`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Segunda RFEF | CD Castellon B - UD Castellonense | **İY 1.5 Alt** | 1.43 | %59.3 | 1.69 | 3 | 1.92-1.21 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | Girona B - UD Logrones B | **İY 1.5 Alt** | 1.46 | %58.1 | 1.72 | 3 | 2.44-0.76 (2-0) | OddsMath |
| 3 | 22.11 14:00 | Polonya 2. Lig | Hutnik Krakow - Resovia | **KG Var** | 1.41 | %60.1 | 1.66 | 3 | 1.93-1.14 (1-1) | OddsMath |
| 4 | 22.11 14:00 | Vietnam V-Ligi | SHB Da Nang - Phu Dong | **KG Var** | 1.46 | %57.9 | 1.73 | 3 | 1.20-1.63 (1-1) | OddsMath |
| 5 | 22.11 14:30 | İtalya Serie C | Union Brescia - AC Renate | **MS 1 & 1.5 Üst** | 1.45 | %58.2 | 1.72 | 3 | 2.15-0.78 (2-0) | OddsMath |
| 6 | 22.11 15:00 | Tayland 1.Lig | Rayong - Rasisalai Utd | **KG Var** | 1.42 | %59.7 | 1.68 | 3 | 2.25-1.03 (2-1) | OddsMath |
| 7 | 22.11 15:30 | Almanya Bundesliga 2 | Karlsruhe - Osnabrück | **İY 1.5 Alt** | 1.40 | %60.8 | 1.65 | 1 | 1.62-1.42 (1-1) | Matchbook + Smarkets |
| 8 | 22.11 18:00 | Belçika 2. Lig, İlk Etap | Beerschot - J. KRC Genk U23 | **KG Var** | 1.38 | %61.6 | 1.62 | 3 | 2.73-1.03 (2-1) | OddsMath |
| 9 | 22.11 18:00 | İspanya Primera RFEF | RC Deportivo Fabril - CD Coria | **KG Var** | 1.43 | %59.4 | 1.68 | 3 | 1.71-1.19 (1-1) | OddsMath |
| 10 | 22.11 19:00 | İspanya Segunda RFEF | Bergantinos - CD Basconia | **KG Var** | 1.47 | %57.5 | 1.74 | 3 | 2.02-1.00 (1-1) | OddsMath |


---

## GRUP 4 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı (P %50–%61 · Kombine & Üst/KG)

### KUPON 16 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı #1
**Canlı Nesine Toplam Oran:** **`283.90x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%52.4` · **Birleşik Olasılık:** `%0.1556`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Polonya 2. Lig | Hutnik Krakow - Resovia | **2-3 Gol** | 1.81 | %50.1 | 2.00 | 3 | 1.93-1.14 (1-1) | OddsMath |
| 2 | 22.11 14:00 | Moldova Ulusal Lig  | Real Sireti - Petrocub | **KG Yok** | 1.66 | %59.6 | 1.68 | 3 | 0.57-2.26 (0-2) | OddsMath |
| 3 | 22.11 14:30 | İtalya Serie C | Scafatese Calcio 1922 - Foggia | **2-3 Gol** | 1.74 | %51.9 | 1.93 | 3 | 1.37-1.25 (1-1) | OddsMath |
| 4 | 22.11 16:30 | İtalya Serie C | Livorno - Ravenna 1913 | **2-3 Gol** | 1.74 | %52.3 | 1.91 | 3 | 1.02-1.68 (1-1) | OddsMath |
| 5 | 22.11 17:00 | Fransa Ligue 1 | Paris - Angers | **KG Yok** | 1.76 | %51.3 | 1.95 | 1 | 2.38-0.74 (2-0) | Matchbook + Smarkets |
| 6 | 22.11 18:00 | İspanya Segunda RFEF | UD Llanera - Ourense | **2.5 Üst** | 1.79 | %52.6 | 1.90 | 3 | 1.51-1.25 (1-1) | OddsMath |
| 7 | 22.11 19:15 | Fransa Ligue 1 | Lorient - Rennes | **2.5 Üst** | 1.87 | %51.2 | 1.95 | 1 | 1.28-1.43 (1-1) | Matchbook + Smarkets |
| 8 | 22.11 19:30 | İtalya Serie C | AZ Picerno - Giugliano 1928 | **2-3 Gol** | 1.75 | %51.6 | 1.94 | 3 | 1.64-1.15 (1-1) | OddsMath |
| 9 | 22.11 19:30 | İtalya Serie C | Desenzano Calvina - US Albinoleffe | **2-3 Gol** | 1.72 | %52.6 | 1.90 | 3 | 1.25-1.22 (1-1) | OddsMath |
| 10 | 22.11 19:30 | Almanya Bundesliga | Werder Bremen - Hamburg | **2.5 Üst & KG Var** | 1.76 | %51.1 | 1.95 | 1 | 2.06-1.15 (2-1) | Matchbook + Smarkets |

### KUPON 17 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı #2
**Canlı Nesine Toplam Oran:** **`244.03x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%51.5` · **Birleşik Olasılık:** `%0.1303`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Primera RFEF | Alcorcon - Algeciras | **2-3 Gol** | 1.78 | %50.0 | 2.00 | 3 | 2.07-0.92 (2-0) | OddsMath |
| 2 | 22.11 14:00 | İspanya Primera RFEF | UD Ourense - Racing  Ferrol | **KG Yok** | 1.69 | %52.6 | 1.90 | 3 | 0.87-1.53 (0-1) | OddsMath |
| 3 | 22.11 14:30 | İtalya Serie A | Juventus - Venezia | **KG Yok** | 1.74 | %51.4 | 1.95 | 1 | 2.28-0.75 (2-0) | Matchbook + Smarkets |
| 4 | 22.11 16:00 | Slovenya 2. Lig | Tabor Sezana - NK Jesenice | **KG Yok** | 1.74 | %53.6 | 1.87 | 3 | 2.39-0.68 (2-0) | OddsMath |
| 5 | 22.11 17:00 | İtalya Serie A | Bologna - Udinese | **KG Var** | 1.69 | %52.3 | 1.91 | 1 | 1.76-0.94 (1-0) | Matchbook + Smarkets |
| 6 | 22.11 18:00 | İspanya Primera RFEF | RC Deportivo Fabril - CD Coria | **2-3 Gol** | 1.77 | %50.1 | 2.00 | 3 | 1.71-1.19 (1-1) | OddsMath |
| 7 | 22.11 18:15 | İspanya La Liga | Santander - R. Sociedad | **3.5 Üst** | 1.73 | %50.8 | 1.97 | 1 | 1.62-2.09 (1-2) | Matchbook + Smarkets |
| 8 | 22.11 19:30 | İtalya Serie C | Dolomiti Bellunesi - Ath Carpi | **2-3 Gol** | 1.72 | %51.5 | 1.94 | 3 | 1.23-1.28 (1-1) | OddsMath |
| 9 | 22.11 19:30 | İtalya Serie C | Forli - Reggiana | **2-3 Gol** | 1.73 | %51.2 | 1.95 | 3 | 1.25-1.31 (1-1) | OddsMath |
| 10 | 22.11 20:30 | Yunanistan Süper Lig | PAOK - AE Kifisia | **MS 1 & 2.5 Üst** | 1.74 | %51.2 | 1.95 | 3 | 2.40-0.79 (2-0) | Matchbook + Smarkets |

### KUPON 18 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı #3
**Canlı Nesine Toplam Oran:** **`167.02x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%52.8` · **Birleşik Olasılık:** `%0.1681`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 16:30 | İtalya Serie C | Altamura - Casarano | **2-3 Gol** | 1.73 | %50.5 | 1.98 | 3 | 1.44-1.17 (1-1) | OddsMath |
| 2 | 22.11 16:30 | Güney Afrika Lig Kupası | Mamel Sundow - Kaizer Chiefs | **2-3 Gol** | 1.72 | %50.5 | 1.98 | 2 | 1.76-0.86 (1-0) | OddsMath |
| 3 | 22.11 19:00 | Sırbistan Superliga | FK M. Sabac - FK Vojvodina | **KG Var** | 1.66 | %53.3 | 1.87 | 3 | 0.88-2.07 (0-2) | OddsMath |
| 4 | 22.11 19:30 | İspanya Segunda RFEF | Recreativo - Badajoz | **KG Yok** | 1.58 | %56.4 | 1.77 | 3 | 1.79-0.72 (1-0) | OddsMath |
| 5 | 22.11 20:15 | İspanya Primera RFEF | Cultural Leonesa - Zamora | **2-3 Gol** | 1.71 | %50.9 | 1.96 | 3 | 1.40-0.93 (1-0) | OddsMath |
| 6 | 22.11 22:00 | Ekvador Pro Lig, Düşme Turu | Orense SC - Mushuc Runa | **KG Var** | 1.69 | %51.9 | 1.93 | 3 | 1.63-0.98 (1-1) | OddsMath |
| 7 | 22.11 22:00 | Brezilya Serie A | Paranaense - Clube do Remo | **MS 1 & 1.5 Üst** | 1.60 | %55.4 | 1.81 | 1 | 2.10-0.89 (2-0) | Matchbook |
| 8 | 22.11 23:00 | İspanya 2. Lig | Burgos - Albacete | **KG Var** | 1.70 | %51.8 | 1.93 | 1 | 1.50-1.02 (1-1) | Matchbook + Smarkets |
| 9 | 23.11 00:30 | Brezilya Serie A | Fluminense - Mirassol SP | **KG Var** | 1.65 | %53.8 | 1.86 | 1 | 1.87-0.92 (1-1) | Matchbook |
| 10 | 23.11 02:07 | Meksika Prmr Ligi, Açılış | CD Guadalajara - Cruz Azul | **2.5 Üst & KG Var** | 1.65 | %53.7 | 1.86 | 2 | 1.69-1.51 (1-1) | Matchbook |

### KUPON 19 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı #4
**Canlı Nesine Toplam Oran:** **`149.82x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%53.4` · **Birleşik Olasılık:** `%0.1858`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Bulgaristan Parva Ligi | Botev Vratsa - CSKA 1948 Sofia | **KG Var** | 1.60 | %54.6 | 1.83 | 3 | 1.05-1.70 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Bulgaristan 2. Lig | Montana 1921 - Dobrudzha Dobrich | **KG Var** | 1.65 | %55.5 | 1.80 | 3 | 1.95-0.99 (1-1) | OddsMath |
| 3 | 22.11 15:30 | Belçika Pro Lig | SK Beveren - KAA Gent | **KG Var** | 1.56 | %56.1 | 1.78 | 1 | 1.13-1.65 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 16:30 | Rusya Premier Lig | Dyn. Makhachkala - S. Moskova | **KG Var** | 1.69 | %50.9 | 1.97 | 1 | 0.84-2.04 (0-2) | OddsMath |
| 5 | 22.11 17:00 | İngiltere Premier Lig | Hull City - Brighton | **KG Var** | 1.66 | %52.3 | 1.91 | 1 | 0.87-2.06 (0-2) | Matchbook + Smarkets |
| 6 | 22.11 17:00 | Belarus Premier Lig | M. Rogachev - Slavia Mozyr | **MS 1 & KG Yok** | 1.70 | %53.3 | 1.87 | 3 | 2.46-0.53 (2-0) | OddsMath |
| 7 | 22.11 18:00 | İspanya Primera RFEF | Barakaldo - Unionistas | **2-3 Gol** | 1.71 | %50.0 | 2.00 | 3 | 1.67-0.87 (1-0) | OddsMath |
| 8 | 22.11 18:15 | İspanya 2. Lig | S. Gijon - Las Palmas | **KG Var** | 1.59 | %54.9 | 1.82 | 1 | 1.52-1.13 (1-1) | Matchbook + Smarkets |
| 9 | 22.11 19:30 | Polonya Ekstraklasa | Wisla Plock - L. Varşova | **2.5 Üst** | 1.66 | %55.5 | 1.80 | 2 | 1.31-1.57 (1-1) | OddsMath |
| 10 | 22.11 20:30 | İspanya La Liga | Osasuna - Malaga | **KG Yok** | 1.69 | %50.6 | 1.98 | 1 | 1.60-0.92 (1-0) | Matchbook + Smarkets |

### KUPON 20 — Özel Kombine & Gollü Geçiş Maksimum Oran Bandı #5
**Canlı Nesine Toplam Oran:** **`123.55x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%53.3` · **Birleşik Olasılık:** `%0.1836`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Estonya Premium Ligi Düş./Yük. | Viimsi JK - Kuressaare | **KG Var** | 1.57 | %55.2 | 1.81 | 3 | 1.04-1.80 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | Club Atletico Central - CD Xerez | **KG Yok** | 1.58 | %54.7 | 1.83 | 3 | 0.87-1.36 (0-1) | OddsMath |
| 3 | 22.11 14:00 | İspanya Segunda RFEF | Don Benito - Marbella | **KG Var** | 1.65 | %51.6 | 1.94 | 3 | 1.41-1.06 (1-1) | OddsMath |
| 4 | 22.11 15:30 | Norveç Eliteserien, Düş./Yük. | Odds BK - Bryne | **2.5 Üst & KG Var** | 1.54 | %56.7 | 1.76 | 2 | 1.88-1.50 (1-1) | OddsMath |
| 5 | 22.11 16:30 | İtalya Serie C | Torres Sassari - Spezia | **KG Var** | 1.53 | %56.7 | 1.76 | 3 | 0.97-1.93 (1-1) | OddsMath |
| 6 | 22.11 16:30 | Avusturya Bundesliga | Wolfsberger - SV Ried | **2.5 Üst & KG Var** | 1.67 | %51.2 | 1.95 | 2 | 1.45-1.63 (1-1) | OddsMath |
| 7 | 22.11 17:00 | Belarus Premier Lig | Isloch - Torpedo Belaz Z. | **2-3 Gol** | 1.73 | %51.2 | 1.95 | 3 | 1.93-0.71 (1-0) | OddsMath |
| 8 | 22.11 19:00 | İspanya Segunda RFEF | Orihuela - La Nucia | **KG Var** | 1.67 | %50.9 | 1.96 | 3 | 1.43-1.01 (1-1) | OddsMath |
| 9 | 23.11 00:00 | ABD Major Lig Playoff | Nashville SC - Cincinnati | **2.5 Üst & KG Var** | 1.59 | %54.0 | 1.85 | 1 | 2.42-1.10 (2-1) | Matchbook |
| 10 | 23.11 00:30 | Ekvador Pro Lig | LDU Quito - SD Aucas | **KG Var** | 1.67 | %50.8 | 1.97 | 3 | 1.60-0.96 (1-1) | OddsMath |


---

## GRUP 5 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı (P %43–%54 · Yüksek Oranlı Borsa)

### KUPON 21 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı #1
**Canlı Nesine Toplam Oran:** **`1,084.12x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%45.5` · **Birleşik Olasılık:** `%0.0375`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Primera RFEF | A.Club De Getxo - Real Aviles | **2-3 Gol** | 1.82 | %49.9 | 2.00 | 3 | 1.51-1.45 (1-1) | OddsMath |
| 2 | 22.11 14:00 | Ukrayna Premier Ligi | Dinamo Kiev - Obolon Kiev | **İY 1.5 Üst** | 2.17 | %43.9 | 2.28 | 3 | 2.72-0.61 (2-0) | OddsMath |
| 3 | 22.11 14:00 | Kuzey Makedonya 1. MFL | FK Bregalnica Stip - Struga Trim | **İY 2** | 2.05 | %46.1 | 2.17 | 3 | 0.85-2.01 (0-2) | OddsMath |
| 4 | 22.11 14:30 | İtalya Serie C | Pro Vercelli - Novara Calcio | **2.5 Üst & KG Var** | 1.99 | %43.9 | 2.28 | 3 | 1.29-1.37 (1-1) | OddsMath |
| 5 | 22.11 14:30 | İspanya Segunda RFEF | Reus Reddis - UE Olot | **MS 1** | 2.13 | %46.9 | 2.13 | 3 | 1.36-0.89 (1-0) | OddsMath |
| 6 | 22.11 17:00 | Fransa Ligue 1 | Paris - Angers | **2-3 Gol** | 2.00 | %44.5 | 2.25 | 1 | 2.38-0.74 (2-0) | Matchbook + Smarkets |
| 7 | 22.11 20:15 | İspanya Primera RFEF | Merida AD - Union Irun | **2.5 Üst & KG Var** | 1.88 | %47.7 | 2.10 | 3 | 1.58-1.29 (1-1) | OddsMath |
| 8 | 22.11 20:30 | İspanya 2. Lig | Girona - Eibar | **MS 1 & 1.5 Üst** | 2.09 | %43.8 | 2.28 | 1 | 1.79-1.05 (1-1) | Matchbook |
| 9 | 22.11 22:00 | Brezilya Serie A | Paranaense - Clube do Remo | **MS 1 & 2.5 Üst** | 2.00 | %44.1 | 2.27 | 1 | 2.10-0.89 (2-0) | Matchbook |
| 10 | 22.11 23:00 | İspanya La Liga | Getafe - Atl Madrid | **KG Var** | 2.01 | %43.9 | 2.28 | 1 | 0.72-1.80 (0-1) | Matchbook + Smarkets |

### KUPON 22 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı #2
**Canlı Nesine Toplam Oran:** **`629.59x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%46.3` · **Birleşik Olasılık:** `%0.0445`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Polonya 1. Lig | Unia Skier - Pogon Siedl. | **2-3 Gol** | 1.88 | %46.3 | 2.16 | 3 | 1.82-1.36 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | Utebo - Calamocha | **İY 1** | 1.83 | %49.0 | 2.04 | 3 | 2.03-0.70 (2-0) | OddsMath |
| 3 | 22.11 15:00 | İngiltere Championship | Burnley - Blackburn R. | **2.5 Üst & KG Var** | 1.91 | %45.8 | 2.18 | 1 | 1.72-1.16 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 15:30 | Belçika Pro Lig | SK Beveren - KAA Gent | **2.5 Üst & KG Var** | 1.98 | %44.0 | 2.27 | 1 | 1.13-1.65 (1-1) | Matchbook + Smarkets |
| 5 | 22.11 15:30 | Çekya 2. Lig | SK Kladno - Jihlava | **İY 1.5 Üst** | 1.99 | %43.9 | 2.28 | 3 | 1.69-1.65 (1-1) | OddsMath |
| 6 | 22.11 16:30 | Avusturya Bundesliga | Wolfsberger - SV Ried | **2-3 Gol** | 1.86 | %47.2 | 2.12 | 2 | 1.45-1.63 (1-1) | OddsMath |
| 7 | 22.11 17:00 | İngiltere U21 Premier Lig Kupası | Stoke City U21 - Stockport U21 | **İY 1** | 1.96 | %44.2 | 2.26 | 3 | 2.78-2.02 (2-1) | OddsMath |
| 8 | 22.11 21:30 | Polonya 2. Lig | Zawisza Bydgoszcz - Podhale Nowy Targ | **2-3 Gol** | 1.80 | %49.1 | 2.04 | 3 | 1.54-1.43 (1-1) | OddsMath |
| 9 | 22.11 22:00 | Arjantin Primera Lpf, Clausura Playoff | Rosario C. - Gimnasia Y. | **MS 1 & KG Yok** | 1.93 | %44.9 | 2.23 | 2 | 2.09-0.64 (2-0) | Matchbook + Smarkets |
| 10 | 22.11 23:00 | Jamaika Premier Lig | Mount Pleasant - Humble Lions | **KG Var** | 1.92 | %48.2 | 2.08 | 3 | 3.07-0.66 (3-0) | OddsMath |

### KUPON 23 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı #3
**Canlı Nesine Toplam Oran:** **`481.39x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%47.4` · **Birleşik Olasılık:** `%0.0558`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Azerbaycan Premier Lig | Araz Nakhchivan PFK - Neftçi | **İY 2** | 1.75 | %53.5 | 1.87 | 3 | 0.83-2.46 (0-2) | OddsMath |
| 2 | 22.11 14:30 | İtalya Serie C | Union Brescia - AC Renate | **2-3 Gol** | 1.78 | %49.4 | 2.02 | 3 | 2.15-0.78 (2-0) | OddsMath |
| 3 | 22.11 16:00 | İsveç Allsvenskan | BK Hacken - IF Elfsborg | **2-3 Gol** | 1.93 | %44.2 | 2.26 | 2 | 1.90-1.23 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 16:00 | Almanya Böl. Lig, Kuzey  | Eintracht Norder. - FSV Schoningen 2011 | **3.5 Üst** | 1.83 | %49.5 | 2.02 | 3 | 1.79-1.96 (1-1) | OddsMath |
| 5 | 22.11 16:30 | Tunus 1. Lig | Club Africain - Esperance T. | **2-3 Gol** | 1.80 | %48.6 | 2.06 | 3 | 0.88-0.94 (0-0) | OddsMath |
| 6 | 22.11 18:00 | İspanya Primera RFEF | Cartagena - Real Jaen | **İY 1** | 1.97 | %43.1 | 2.32 | 3 | 1.86-0.91 (1-0) | OddsMath |
| 7 | 22.11 18:00 | Macaristan 1. Ligi | Nyiregyhaza - Debrecen | **2-3 Gol** | 1.81 | %48.2 | 2.07 | 2 | 1.45-1.55 (1-1) | OddsMath |
| 8 | 22.11 19:00 | İspanya Segunda RFEF | Salamanca - C. Sotelo Puertollano | **İY 1** | 1.87 | %46.5 | 2.15 | 3 | 2.00-0.84 (2-0) | OddsMath |
| 9 | 22.11 20:30 | İspanya 2. Lig | Celta Vigo B - Real Valladolid | **2.5 Üst & KG Var** | 1.86 | %46.8 | 2.13 | 1 | 1.23-1.66 (1-1) | Matchbook |
| 10 | 22.11 22:30 | İspanya Primera RFEF | CP Cacereno Sad - Logrones | **KG Yok** | 1.96 | %43.7 | 2.29 | 3 | 1.38-1.35 (1-1) | OddsMath |

### KUPON 24 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı #4
**Canlı Nesine Toplam Oran:** **`534.97x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%46.1` · **Birleşik Olasılık:** `%0.0426`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | İspanya Primera RFEF | Alcorcon - Algeciras | **2.5 Üst & KG Var** | 1.96 | %43.1 | 2.32 | 3 | 2.07-0.92 (2-0) | OddsMath |
| 2 | 22.11 16:00 | İngiltere U21 Premier Lig Kupası | Brentford U21 - Hull City U21 | **İY 1** | 1.89 | %45.2 | 2.21 | 3 | 2.76-1.90 (2-1) | OddsMath |
| 3 | 22.11 16:30 | İtalya Serie C | Torres Sassari - Spezia | **2-3 Gol** | 1.77 | %49.6 | 2.01 | 3 | 0.97-1.93 (1-1) | OddsMath |
| 4 | 22.11 17:00 | İtalya Serie A | Bologna - Udinese | **MS 1 & 1.5 Üst** | 1.93 | %44.2 | 2.26 | 1 | 1.76-0.94 (1-0) | Matchbook + Smarkets |
| 5 | 22.11 17:00 | Belarus Premier Lig | M. Rogachev - Slavia Mozyr | **2-3 Gol** | 1.83 | %49.8 | 2.01 | 3 | 2.46-0.53 (2-0) | OddsMath |
| 6 | 22.11 17:30 | Slovakya Superliga | FK Kosice - Skalica | **2-3 Gol** | 1.87 | %45.8 | 2.18 | 3 | 2.08-1.13 (2-1) | OddsMath |
| 7 | 22.11 18:30 | Almanya 3. Lig | Saarbrucken - W. Wiesbaden | **2-3 Gol** | 1.89 | %45.3 | 2.21 | 2 | 1.61-1.57 (1-1) | OddsMath |
| 8 | 22.11 19:00 | İspanya Segunda RFEF | Bergantinos - CD Basconia | **İY 1** | 1.91 | %44.7 | 2.24 | 3 | 2.02-1.00 (1-1) | OddsMath |
| 9 | 22.11 19:00 | Rusya Premier Lig | Rodina Moscow - L. Moskova | **2-3 Gol** | 1.83 | %47.2 | 2.12 | 1 | 1.46-1.51 (1-1) | OddsMath |
| 10 | 22.11 19:00 | Polonya 1. Lig | Stal Rzeszow - Polonia Bytom | **2-3 Gol** | 1.87 | %45.8 | 2.18 | 3 | 1.53-1.60 (1-1) | OddsMath |

### KUPON 25 — Agresif Değer & Orta Olasılık Maksimum Oran Bandı #5
**Canlı Nesine Toplam Oran:** **`493.99x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%46.8` · **Birleşik Olasılık:** `%0.0492`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:00 | Rusya Premier Lig | D. Moskova - Krasnodar | **2-3 Gol** | 1.82 | %47.4 | 2.11 | 1 | 1.64-1.23 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Bulgaristan 2. Lig | Montana 1921 - Dobrudzha Dobrich | **İY 1** | 2.00 | %43.7 | 2.29 | 3 | 1.95-0.99 (1-1) | OddsMath |
| 3 | 22.11 16:30 | Güney Afrika Lig Kupası | Mamel Sundow - Kaizer Chiefs | **KG Var** | 1.76 | %49.6 | 2.01 | 2 | 1.76-0.86 (1-0) | OddsMath |
| 4 | 22.11 17:00 | Hindistan Süper Ligi | Churchill B. SC - Mohun Bagan | **2-3 Gol** | 1.83 | %46.9 | 2.13 | 3 | 0.90-2.14 (0-2) | OddsMath |
| 5 | 22.11 17:30 | Almanya Bundesliga | Augsburg - Mainz | **3.5 Üst** | 1.84 | %46.8 | 2.14 | 1 | 1.71-1.80 (1-1) | Matchbook + Smarkets |
| 6 | 22.11 18:00 | Belçika Pro Lig | Kortrijk - U. S. Gilloise | **2-3 Gol** | 1.90 | %44.6 | 2.24 | 1 | 0.79-2.31 (0-2) | Matchbook + Smarkets |
| 7 | 22.11 18:45 | İspanya 3. Federasyon | CD Mosconia - Aviles Stadium | **KG Var** | 1.85 | %48.6 | 2.06 | 3 | 1.79-0.83 (1-0) | OddsMath |
| 8 | 22.11 19:30 | İngiltere Premier Lig | Liverpool - Man. Utd | **İY 1** | 1.94 | %43.3 | 2.31 | 1 | 2.11-1.23 (2-1) | Matchbook + Smarkets |
| 9 | 22.11 21:15 | Belçika Pro Lig | Lommel SK - Standard Liege | **2-3 Gol** | 1.93 | %43.8 | 2.29 | 1 | 1.37-1.79 (1-1) | Matchbook |
| 10 | 22.11 22:00 | Bolivya Profesyonel Ligi | Real Potosi - Club Bolivar | **İY 2** | 1.74 | %53.0 | 1.88 | 3 | 0.79-2.39 (0-2) | OddsMath |


---

## GRUP 6 — Ekstrem Maksimum Oran / Jackpot Bandı (P %26–%44 · İY/MS, 3.5 Üst & Kombine)

### KUPON 26 — Ekstrem Maksimum Oran / Jackpot Bandı #1
**Canlı Nesine Toplam Oran:** **`210,591.77x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%28.4` · **Birleşik Olasılık:** `%0.0003`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 14:30 | İtalya Serie C | Pro Vercelli - Novara Calcio | **İY 1** | 3.27 | %27.4 | 3.65 | 3 | 1.29-1.37 (1-1) | OddsMath |
| 2 | 22.11 14:30 | İspanya Segunda RFEF | Reus Reddis - UE Olot | **İY 1** | 2.85 | %33.8 | 2.96 | 3 | 1.36-0.89 (1-0) | OddsMath |
| 3 | 22.11 16:00 | Türkiye Süper Ligi | Kasımpaşa - Alanyaspor | **MS 0** | 3.22 | %27.4 | 3.65 | 1 | 1.46-0.90 (1-0) | Smarkets |
| 4 | 22.11 16:30 | Tunus 1. Lig | ES Zarzis - US Ben Guerdane | **MS 2** | 3.66 | %28.0 | 3.58 | 3 | 1.08-0.87 (1-0) | OddsMath |
| 5 | 22.11 16:30 | Fransa U19 Ulusal Şampiyonası | Stade Briochin U19 - Stade Laval U19 | **MS 1** | 3.57 | %27.7 | 3.62 | 3 | 1.39-1.97 (1-1) | OddsMath |
| 6 | 22.11 16:30 | İtalya Serie C | Torres Sassari - Spezia | **MS 0** | 3.32 | %26.4 | 3.79 | 3 | 0.97-1.93 (1-1) | OddsMath |
| 7 | 22.11 17:00 | Malta Premier Lig Top 6 İlk Etap | Hamrun Spartans - Sliema Wanderers | **İY 1** | 4.06 | %29.7 | 3.37 | 3 | 1.33-1.22 (1-1) | OddsMath |
| 8 | 22.11 18:15 | İspanya 2. Lig | S. Gijon - Las Palmas | **MS 1 & 2.5 Üst** | 3.30 | %27.2 | 3.68 | 1 | 1.52-1.13 (1-1) | Matchbook + Smarkets |
| 9 | 22.11 20:30 | İspanya 2. Lig | Girona - Eibar | **MS 1 & KG Var** | 3.51 | %26.1 | 3.84 | 1 | 1.79-1.05 (1-1) | Matchbook |
| 10 | 22.11 23:00 | Jamaika Premier Lig | Montego Bay Utd - Waterhouse | **MS 2** | 3.44 | %30.6 | 3.26 | 3 | 1.54-1.26 (1-1) | OddsMath |

### KUPON 27 — Ekstrem Maksimum Oran / Jackpot Bandı #2
**Canlı Nesine Toplam Oran:** **`108,085.27x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%28.9` · **Birleşik Olasılık:** `%0.0004`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Romanya 2. Lig | Scm Ramnicu V. - AFC Metalul Buzau | **MS 0** | 3.30 | %27.2 | 3.67 | 3 | 1.31-1.50 (1-1) | OddsMath |
| 2 | 22.11 15:30 | Almanya Bundesliga 2 | Kaiserslautern - D. Dresden | **MS 0** | 3.22 | %26.4 | 3.78 | 1 | 1.61-1.27 (1-1) | Matchbook + Smarkets |
| 3 | 22.11 16:00 | Mozambik Mocambola | CD Maxaquene - Baia de Pemba | **MS 1** | 3.11 | %33.4 | 3.00 | 3 | 0.92-0.92 (0-0) | OddsMath |
| 4 | 22.11 18:00 | İspanya Segunda RFEF | Albacete Balompie B - CD Guadalajara | **İY 1** | 3.22 | %27.5 | 3.63 | 3 | 1.34-1.46 (1-1) | OddsMath |
| 5 | 22.11 18:00 | İspanya Primera RFEF | Barakaldo - Unionistas | **MS 1 & 2.5 Üst** | 2.76 | %34.1 | 2.93 | 3 | 1.67-0.87 (1-0) | OddsMath |
| 6 | 22.11 18:15 | İspanya 3. Federasyon | SFC Minerva - Atletico Pulpileno | **MS 1** | 3.33 | %30.1 | 3.32 | 3 | 1.05-1.27 (1-1) | OddsMath |
| 7 | 22.11 20:00 | Danimarka Süper Ligi | Nordsjælland - Kopenhag | **MS 0** | 3.19 | %26.8 | 3.73 | 2 | 1.34-1.32 (1-1) | Smarkets |
| 8 | 22.11 20:30 | Macaristan 1. Ligi | B. Honved - Paksi | **MS 2 & KG Var** | 3.24 | %27.4 | 3.65 | 2 | 1.46-1.84 (1-1) | OddsMath |
| 9 | 22.11 21:30 | Almanya 3. Lig | Duisburg - H. Rostock | **MS 2 & 1.5 Üst** | 3.26 | %26.6 | 3.76 | 2 | 1.64-1.42 (1-1) | OddsMath |
| 10 | 22.11 23:00 | Peru Prmr Ligi, Kapanış | Huancayo - U. Deportes | **MS 2** | 3.28 | %29.2 | 3.42 | 3 | 1.75-1.37 (1-1) | OddsMath |

### KUPON 28 — Ekstrem Maksimum Oran / Jackpot Bandı #3
**Canlı Nesine Toplam Oran:** **`103,118.81x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%27.9` · **Birleşik Olasılık:** `%0.0003`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Kenya Premier Lig | Shabana - Mara Sugar | **MS 2** | 3.40 | %28.4 | 3.52 | 3 | 1.12-0.88 (1-0) | OddsMath |
| 2 | 22.11 14:00 | İspanya Primera RFEF | UD Ourense - Racing  Ferrol | **MS 0** | 3.11 | %27.1 | 3.69 | 3 | 0.87-1.53 (0-1) | OddsMath |
| 3 | 22.11 16:00 | İsveç Allsvenskan | IK Sirius - Djurgarden | **MS 1 & 2.5 Üst** | 3.15 | %27.6 | 3.62 | 2 | 1.59-1.41 (1-1) | Matchbook + Smarkets |
| 4 | 22.11 16:30 | Fransa U19 Ulusal Şampiyonası | US Cap D Ail U19 - Bastia U19 | **MS 1** | 3.29 | %30.1 | 3.32 | 3 | 1.33-1.72 (1-1) | OddsMath |
| 5 | 22.11 18:30 | Almanya 3. Lig | Saarbrucken - W. Wiesbaden | **MS 1 & 2.5 Üst** | 3.24 | %26.7 | 3.75 | 2 | 1.61-1.57 (1-1) | OddsMath |
| 6 | 22.11 19:30 | Ekvador Pro Lig, Düşme Turu | Manta - Delfin | **İY 1** | 2.96 | %30.0 | 3.33 | 3 | 1.32-1.17 (1-1) | OddsMath |
| 7 | 22.11 20:30 | İspanya La Liga | Osasuna - Malaga | **MS 0** | 3.18 | %26.2 | 3.82 | 1 | 1.60-0.92 (1-0) | Matchbook + Smarkets |
| 8 | 23.11 01:00 | Kosta Rika Prmr Ligi, Açılış | Inter San Carlos - Sporting San Jose | **İY 1** | 3.17 | %27.4 | 3.65 | 3 | 1.37-1.53 (1-1) | OddsMath |
| 9 | 23.11 01:30 | Brezilya Serie A | Bragantino - Vasco Da G. | **MS 0** | 3.15 | %26.7 | 3.74 | 1 | 1.52-1.41 (1-1) | Matchbook |
| 10 | 23.11 04:00 | Arjantin Primera Lpf, Clausura Playoff | Instituto - CA Huracan | **2.5 Üst & KG Var** | 3.09 | %28.3 | 3.53 | 2 | 1.27-0.82 (1-0) | Matchbook |

### KUPON 29 — Ekstrem Maksimum Oran / Jackpot Bandı #4
**Canlı Nesine Toplam Oran:** **`54,857.50x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%28.9` · **Birleşik Olasılık:** `%0.0004`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | İspanya Segunda RFEF | Pena Deportiva - Lorca Deportiva | **İY 2** | 2.85 | %31.6 | 3.17 | 3 | 1.14-1.41 (1-1) | OddsMath |
| 2 | 22.11 14:00 | İspanya Segunda RFEF | Alaves II - Compostela | **MS 0** | 3.10 | %26.6 | 3.76 | 3 | 1.61-0.92 (1-0) | OddsMath |
| 3 | 22.11 14:00 | Rusya Premier Lig | D. Moskova - Krasnodar | **MS 0** | 3.11 | %26.7 | 3.75 | 1 | 1.64-1.23 (1-1) | OddsMath |
| 4 | 22.11 14:00 | İspanya Segunda RFEF | Ucam Murcia - Y.Deportivo | **MS 0** | 3.09 | %26.8 | 3.73 | 3 | 1.63-0.85 (1-0) | OddsMath |
| 5 | 22.11 15:30 | Çekya 2. Lig | SK Kladno - Jihlava | **İY 1** | 2.83 | %31.8 | 3.14 | 3 | 1.69-1.65 (1-1) | OddsMath |
| 6 | 22.11 17:00 | İtalya Serie B | AS Avellino 1912 - Mantova 1911 | **MS 0** | 2.93 | %29.4 | 3.40 | 1 | 1.40-1.19 (1-1) | Matchbook + Smarkets |
| 7 | 22.11 19:00 | Rusya Premier Lig | Rodina Moscow - L. Moskova | **MS 2 & 1.5 Üst** | 2.87 | %31.1 | 3.22 | 1 | 1.46-1.51 (1-1) | OddsMath |
| 8 | 22.11 19:15 | İtalya Serie B | SS Arezzo - Padova | **MS 0** | 2.91 | %29.7 | 3.37 | 1 | 1.37-1.15 (1-1) | Matchbook |
| 9 | 22.11 20:00 | İspanya Segunda RFEF | Valencia M. - CD Alcoyano | **MS 0** | 3.00 | %28.3 | 3.53 | 3 | 1.50-1.09 (1-1) | OddsMath |
| 10 | 23.11 00:30 | Brezilya Serie A | Fluminense - Mirassol SP | **MS 1 & KG Var** | 3.11 | %27.4 | 3.65 | 1 | 1.87-0.92 (1-1) | Matchbook |

### KUPON 30 — Ekstrem Maksimum Oran / Jackpot Bandı #5
**Canlı Nesine Toplam Oran:** **`63,443.41x`** · **Maç Sayısı:** `10` (MBS `3` Uygun) · **Ort. Bacak Olasılığı:** `%27.9` · **Birleşik Olasılık:** `%0.0003`

| # | Saat | Lig | Maç | Tercih | Canlı Nesine | Global % | Adil | MBS | xG (1. Skor) | Kaynak |
|---:|---|---|---|---|---:|---:|---:|---:|---|---|
| 1 | 22.11 13:30 | Türkiye Süper Ligi | Erzurumspor FK - Göztepe | **MS 0** | 2.91 | %29.2 | 3.42 | 1 | 1.08-1.20 (1-1) | Smarkets |
| 2 | 22.11 14:00 | İspanya Primera RFEF | A.Club De Getxo - Real Aviles | **MS 0** | 3.02 | %27.3 | 3.66 | 3 | 1.51-1.45 (1-1) | OddsMath |
| 3 | 22.11 14:00 | İspanya Segunda RFEF | CD Atletico Paso - Real Valladolid B | **İY 2** | 3.16 | %26.6 | 3.76 | 3 | 1.58-1.37 (1-1) | OddsMath |
| 4 | 22.11 14:00 | Ukrayna Premier Ligi | Veres Rivne - Bukovina Chernovtsy | **MS 0** | 3.13 | %26.1 | 3.84 | 3 | 1.16-1.70 (1-1) | OddsMath |
| 5 | 22.11 14:30 | Polonya 2. Lig | Olimpia - G. Leczna | **MS 0** | 2.98 | %27.8 | 3.60 | 3 | 1.49-1.38 (1-1) | OddsMath |
| 6 | 22.11 16:00 | İspanya 2. Lig | Cordoba - Real Oviedo | **MS 1 & KG Var** | 3.16 | %26.6 | 3.76 | 1 | 1.79-1.24 (1-1) | Matchbook |
| 7 | 22.11 16:00 | Almanya Böl. Lig, Kuzey  | Eintracht Norder. - FSV Schoningen 2011 | **İY 1** | 2.98 | %30.4 | 3.28 | 3 | 1.79-1.96 (1-1) | OddsMath |
| 8 | 22.11 17:00 | İtalya Serie C | Calcio Catania - SSC Bari | **MS 1 & KG Yok** | 2.89 | %30.1 | 3.32 | 3 | 1.61-0.92 (1-0) | OddsMath |
| 9 | 22.11 21:30 | Romanya 1. Lig | A. Pitesti - FCSB | **MS 0** | 3.01 | %27.5 | 3.64 | 3 | 1.00-1.43 (1-1) | Betfair Borsası |
| 10 | 22.11 22:30 | İspanya Primera RFEF | CP Cacereno Sad - Logrones | **MS 0** | 2.99 | %27.6 | 3.62 | 3 | 1.38-1.35 (1-1) | OddsMath |

