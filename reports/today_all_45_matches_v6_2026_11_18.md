# 18 Kasım 2026 Çarşamba — Tüm Maçlar QuantFoot-v6 Derinlemesine Omni-Market Analizi ve Kuponlar

Bugün (**18 Kasım 2026 Çarşamba `13:00 TSİ` – 19 Kasım `03:30 TSİ`**) oynanacak **45 karşılaşmanın tamamı**, dünkü 9 kuponun post-mortem analiziyle güçlendirilen **`QuantFoot-v6` (`OmniMarketBundle` + `5 Katmanlı Risk Kalkanı`)** algoritmasından geçirilmiştir.

> [!IMPORTANT]
> **QuantFoot-v6 Aktif Koruma Kuralları (Tüm 45 Maçta Uygulandı):**
> 1. **Kesin `>= 1.20` Oran Tabanı (`MIN_ALLOWED_ODDS = 1.20`):** `1.20` altındaki hiçbir seçenek kuponlara ve en geçerli tahminlere dahil edilmemiştir.
> 2. **Asimetrik `2.5 Alt` Yasağı:** Favorinin gol beklentisi yüksek (`max_mu >= 1.28` veya `|mu_h - mu_a| >= 0.42`) olan maçlarda `2.5 Alt` tuzak olarak işaretlenip engellenmiştir.
> 3. **`İY 0` Kırılganlık Kalkanı:** Erken gol riski taşıyan maçlarda `İY 0` genel kuponlardan çıkarılmış, yerine `İY 1.5 Alt` veya `2Y 0.5 Üst` seçilmiştir.
> 4. **Kademeli Güvenlik İndirimi (`Adaptive Step-Down`):** `+6 Gol` için `P < %45` (`xG < 5.35`) olan maçlarda zorlama yapılmamış; otomatik olarak `2.5 Üst / 3.5 Üst / 3-5 Gol` kademesine inilmiştir.

---

## 1. QuantFoot-v6 Bugünün Hazır Garanti Kuponları (`10x / 20x / 30x` & Çekirdek Banko)

### A. Avrupa & Brezilya Çekirdek Favori Kuponu (`%71.5` Ortalama İsabet Olasılığı — `8.50` / `13.26` Oran)
| Saat (TSİ) | Lig | Karşılaşma | Tercih | Canlı Oran | Model Olasılığı | Adil Oran | Risk & xG Özeti |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `20:45` | UEFA Women's Champions League | **Real Madrid - Internazionale** | **`MS 1`** | **`1.20`** | **%79.2** | `1.26` | `xG: 3.17-0.74` (`2.5 Alt` engellendi) |
| `02:30` | Brazilian Serie A | **Flamengo - Athletico-PR** | **`MS 1`** | **`1.26`** | **%77.8** | `1.29` | `xG: 2.52-0.68` (`2.5 Alt` engellendi) |
| `23:00` | UEFA Women's Champions League | **Chelsea - Paris Saint-Germain** | **`MS 1`** | **`1.28`** | **%75.2** | `1.33` | `xG: 2.77-0.72` (`2.5 Alt` engellendi) |
| `23:00` | UEFA Women's Champions League | **Juventus - OH Leuven** | **`MS 1`** | **`1.32`** | **%72.8** | `1.37` | `xG: 2.65-0.76` (`2.5 Alt` engellendi) |
| `20:45` | UEFA Women's Champions League | **BK Häcken - Manchester City** | **`MS 2`** | **`1.34`** | **%72.8** | `1.37` | `xG: 0.91-2.87` (`2.5 Alt` engellendi) |
| `02:00` | Brazilian Serie A | **Remo - Chapecoense** | **`MS 1`** | **`1.59`** | **%60.8** | `1.64` | `xG: 2.04-1.01` (`2.5 Alt` engellendi) |
| `21:00` | Spanish Copa del Rey | **Utebo - CD Sabadell** | **`MS 2`** | **`1.56`** | **%60.1** | `1.66` | `xG: 0.82-1.91` (`2.5 Alt` engellendi) |
| `22:00` | Spanish Copa del Rey | **Alcoyano - Mallorca** | **`MS 2`** | **`1.56`** | **%59.9** | `1.67` | `xG: 0.81-1.88` (`2.5 Alt` engellendi) |

- **7 Maçlık Toplam Oran (İlk 7 Maç):** **`8.49`** | **8 Maçlık Toplam Oran (Tamamı):** **`13.25`** (Tamamı `>= 1.20` canlı piyasa oranlıdır).

### B-TARGET_10X. QuantFoot-v6 Bugün Hedef 10x Garanti Kupon (16 Canlı Piyasa Oranlı Ana Maç) — Toplam Oran: `10.08` (Ort. Ayak Olasılığı: `%60.7`)
| Saat (TSİ) | Lig | Karşılaşma | En Geçerli Tercih | Oran | Model Olasılığı | Adil Oran | Oran Kaynağı |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `20:45` | UEFA Women's Champions League | **BK Häcken - Manchester City** | **`MS 2`** | **`1.34`** | **%72.8** | `1.37` | **Canlı Piyasa** |
| `01:30` | Brazilian Serie A | **Coritiba - Santos** | **`2.5 Üst`** | **`1.71`** | **%55.3** | `1.81` | **Canlı Piyasa** |
| `22:30` | Spanish Copa del Rey | **CD Minera - FC Cartagena** | **`2.5 Alt`** | **`1.59`** | **%60.3** | `1.66` | **Canlı Piyasa** |
| `02:00` | Brazilian Serie A | **Remo - Chapecoense** | **`MS 1`** | **`1.59`** | **%60.8** | `1.64` | **Canlı Piyasa** |
| `02:30` | Brazilian Serie A | **Cruzeiro - Palmeiras** | **`2.5 Üst`** | **`1.74`** | **%54.3** | `1.84` | **Canlı Piyasa** |

### B-TARGET_20X. QuantFoot-v6 Bugün Hedef 20x Garanti Kupon (16 Canlı Piyasa Oranlı Ana Maç) — Toplam Oran: `21.08` (Ort. Ayak Olasılığı: `%61.8`)
| Saat (TSİ) | Lig | Karşılaşma | En Geçerli Tercih | Oran | Model Olasılığı | Adil Oran | Oran Kaynağı |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `20:45` | UEFA Women's Champions League | **Real Madrid - Internazionale** | **`MS 1`** | **`1.20`** | **%79.2** | `1.26` | **Canlı Piyasa** |
| `21:00` | Spanish Copa del Rey | **Utebo - CD Sabadell** | **`MS 2`** | **`1.56`** | **%60.1** | `1.66` | **Canlı Piyasa** |
| `01:30` | Brazilian Serie A | **Coritiba - Santos** | **`2.5 Üst`** | **`1.71`** | **%55.3** | `1.81` | **Canlı Piyasa** |
| `22:30` | Spanish Copa del Rey | **CD Minera - FC Cartagena** | **`2.5 Alt`** | **`1.59`** | **%60.3** | `1.66` | **Canlı Piyasa** |
| `22:00` | Spanish Copa del Rey | **Alcoyano - Mallorca** | **`MS 2`** | **`1.56`** | **%59.9** | `1.67` | **Canlı Piyasa** |
| `02:00` | Brazilian Serie A | **Remo - Chapecoense** | **`MS 1`** | **`1.59`** | **%60.8** | `1.64` | **Canlı Piyasa** |
| `03:30` | Brazilian Serie A | **Grêmio - Bahia** | **`2.5 Üst`** | **`1.67`** | **%57.0** | `1.75` | **Canlı Piyasa** |

### B-TARGET_30X. QuantFoot-v6 Bugün Hedef 30x Garanti Kupon (16 Canlı Piyasa Oranlı Ana Maç) — Toplam Oran: `30.13` (Ort. Ayak Olasılığı: `%62.7`)
| Saat (TSİ) | Lig | Karşılaşma | En Geçerli Tercih | Oran | Model Olasılığı | Adil Oran | Oran Kaynağı |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `23:00` | UEFA Women's Champions League | **Chelsea - Paris Saint-Germain** | **`MS 1`** | **`1.28`** | **%75.2** | `1.33` | **Canlı Piyasa** |
| `20:45` | UEFA Women's Champions League | **BK Häcken - Manchester City** | **`MS 2`** | **`1.34`** | **%72.8** | `1.37` | **Canlı Piyasa** |
| `21:00` | Spanish Copa del Rey | **Utebo - CD Sabadell** | **`MS 2`** | **`1.56`** | **%60.1** | `1.66` | **Canlı Piyasa** |
| `01:30` | Brazilian Serie A | **Coritiba - Santos** | **`2.5 Üst`** | **`1.71`** | **%55.3** | `1.81` | **Canlı Piyasa** |
| `22:30` | Spanish Copa del Rey | **CD Minera - FC Cartagena** | **`2.5 Alt`** | **`1.59`** | **%60.3** | `1.66` | **Canlı Piyasa** |
| `22:00` | Spanish Copa del Rey | **Alcoyano - Mallorca** | **`MS 2`** | **`1.56`** | **%59.9** | `1.67` | **Canlı Piyasa** |
| `02:00` | Brazilian Serie A | **Remo - Chapecoense** | **`MS 1`** | **`1.59`** | **%60.8** | `1.64` | **Canlı Piyasa** |
| `03:30` | Brazilian Serie A | **Grêmio - Bahia** | **`2.5 Üst`** | **`1.67`** | **%57.0** | `1.75` | **Canlı Piyasa** |

### B-TUR3_10X. QuantFoot-v6 Nesine 2. Lig Gündüz (13:00-15:00) Kuponu — Toplam Oran: `10.02` (Ort. Ayak Olasılığı: `%56.2`)
| Saat (TSİ) | Lig | Karşılaşma | En Geçerli Tercih | Oran | Model Olasılığı | Adil Oran | Oran Kaynağı |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `13:00` | Nesine 2. Lig (12. Hafta) | **12 Bingölspor - Sakaryaspor** | **`KG Var`** | **`1.65`** | **%54.0** | `1.85` | Tahmini (Model) |
| `15:00` | Nesine 2. Lig (12. Hafta) | **Çorluspor 1947 - Muş Spor** | **`KG Var`** | **`1.56`** | **%57.1** | `1.75` | Tahmini (Model) |
| `13:00` | Nesine 2. Lig (12. Hafta) | **1461 Trabzon FK - Kahramanmaraş İstiklalspor** | **`KG Var`** | **`1.55`** | **%57.5** | `1.74` | Tahmini (Model) |
| `13:00` | Nesine 2. Lig (12. Hafta) | **ISBAŞ Isparta 32 Spor - Somaspor** | **`KG Var`** | **`1.58`** | **%56.3** | `1.78` | Tahmini (Model) |
| `13:00` | Nesine 2. Lig (12. Hafta) | **Şanlıurfaspor - Efor Çay Erbaaspor** | **`KG Var`** | **`1.59`** | **%56.0** | `1.79` | Tahmini (Model) |

---

## 2. Özel Bahis Seçenekleri İçin En Güçlü Maçlar (`İY/MS`, `Gol Aralıkları`, `1Y/2Y & KG`, `Kesin Skor`)

### 2.1. İlk Yarı / Maç Sonucu (`İY/MS` — `1/1, 2/2, 0/1, 0/2, 0/0, 1/2, 2/1`) En Güçlü Maçlar
| Saat | Karşılaşma | Lig | #1 İY/MS Tercihi | Olasılık (Adil Oran) | #2 Sürpriz / Devre Kilidi İY/MS | Olasılık (Adil Oran) | Geri Dönüş (`1/2` + `2/1`) |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `20:45` | **Real Madrid - Internazionale** | UEFA Women's Champions League | **`İY/MS 1/1`** | **%57.2** (`1.75`) | `İY/MS 0/1` | %19.1 (`5.25`) | %3.7 |
| `23:00` | **Chelsea - Paris Saint-Germain** | UEFA Women's Champions League | **`İY/MS 1/1`** | **%52.0** (`1.92`) | `İY/MS 0/1` | %20.3 (`4.91`) | %3.6 |
| `02:30` | **Flamengo - Athletico-PR** | Brazilian Serie A | **`İY/MS 1/1`** | **%51.3** (`1.95`) | `İY/MS 0/1` | %23.7 (`4.22`) | %3.5 |
| `20:45` | **BK Häcken - Manchester City** | UEFA Women's Champions League | **`İY/MS 2/2`** | **%49.9** (`2.01`) | `İY/MS 0/2` | %19.4 (`5.17`) | %4.8 |
| `23:00` | **Juventus - OH Leuven** | UEFA Women's Champions League | **`İY/MS 1/1`** | **%49.4** (`2.02`) | `İY/MS 0/1` | %20.4 (`4.90`) | %3.9 |
| `13:00` | **Seza Çimento Elazığspor - Menemen FK** | Nesine 2. Lig (12. Hafta) | **`İY/MS 1/1`** | **%44.4** (`2.25`) | `İY/MS 0/1` | %22.7 (`4.41`) | %3.8 |
| `22:00` | **Tottenham Hotspur - Leicester City** | English WSL Players Cup | **`İY/MS 1/1`** | **%38.5** (`2.60`) | `İY/MS 0/1` | %21.0 (`4.76`) | %3.7 |
| `15:00` | **Güzide Gebze Spor - Ankaraspor** | Nesine 2. Lig (12. Hafta) | **`İY/MS 1/1`** | **%38.1** (`2.62`) | `İY/MS 0/1` | %21.4 (`4.67`) | %4.2 |
| `02:30` | **Always Ready - Real Potosí** | Copa Bolivia | **`İY/MS 1/1`** | **%37.5** (`2.67`) | `İY/MS 0/1` | %21.6 (`4.64`) | %4.2 |
| `02:00` | **Remo - Chapecoense** | Brazilian Serie A | **`İY/MS 1/1`** | **%36.5** (`2.74`) | `İY/MS 0/1` | %20.9 (`4.78`) | %5.0 |
| `21:00` | **Utebo - CD Sabadell** | Spanish Copa del Rey | **`İY/MS 2/2`** | **%36.1** (`2.77`) | `İY/MS 0/2` | %21.2 (`4.73`) | %4.0 |
| `22:00` | **Alcoyano - Mallorca** | Spanish Copa del Rey | **`İY/MS 2/2`** | **%35.9** (`2.79`) | `İY/MS 0/2` | %21.3 (`4.70`) | %3.9 |

### 2.2. Toplam Gol Aralıkları (`0-1`, `2-3`, `3-5`, `+6 Gol` & Kademe İndirimli Üst) En Güçlü Maçlar
| Saat | Karşılaşma | Toplam xG (`1Y / 2Y`) | `0-1 Gol` | `2-3 Gol` | `3-5 Gol` | `+6 Gol` | Algoritma Gol Bandı / Üst Kararı |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `20:45` | **Real Madrid - Internazionale** | `3.92` (`1.73/2.20`) | %15.7 | **%33.8** | **%44.5** | %23.3 | **`3-5 Gol`** (%44.5) / **`2.5 Üst`** (%67.8) *(+6 Gol İndirimi)* |
| `20:45` | **BK Häcken - Manchester City** | `3.78` (`1.67/2.13`) | %16.5 | **%34.9** | **%44.7** | %21.5 | **`3-5 Gol`** (%44.7) / **`2.5 Üst`** (%66.2) *(+6 Gol İndirimi)* |
| `23:00` | **Chelsea - Paris Saint-Germain** | `3.50` (`1.55/1.96`) | %19.4 | **%36.9** | **%43.9** | %17.9 | **`2-3 Gol`** (%36.9) / **`1.5 Üst`** (%80.5) |
| `23:00` | **Juventus - OH Leuven** | `3.41` (`1.51/1.92`) | %20.3 | **%37.5** | **%43.7** | %16.8 | **`2-3 Gol`** (%37.5) / **`1.5 Üst`** (%79.7) |
| `02:30` | **Flamengo - Athletico-PR** | `3.21` (`1.34/1.87`) | %15.5 | **%44.6** | **%53.0** | %10.0 | **`2-3 Gol`** (%44.6) / **`1.5 Üst`** (%84.5) |
| `02:00` | **Remo - Chapecoense** | `3.05` (`1.28/1.77`) | %17.5 | **%46.2** | **%51.1** | %8.3 | **`2-3 Gol`** (%46.2) / **`1.5 Üst`** (%82.5) |
| `03:30` | **Grêmio - Bahia** | `2.95` (`1.23/1.72`) | %19.0 | **%47.1** | **%49.8** | %7.3 | **`2-3 Gol`** (%47.1) / **`1.5 Üst`** (%81.0) |
| `13:00` | **Seza Çimento Elazığspor - Menemen FK** | `2.93` (`1.27/1.67`) | %19.4 | **%47.1** | **%49.5** | %7.1 | **`2-3 Gol`** (%47.1) / **`1.5 Üst`** (%80.6) |
| `20:00` | **Levante - Eibar** | `2.91` (`1.28/1.64`) | %26.1 | **%40.6** | **%41.1** | %10.9 | **`2-3 Gol`** (%40.6) / **`1.5 Üst`** (%73.9) |
| `13:00` | **Adana Demirspor - GMG Kastamonuspor** | `2.90` (`1.25/1.65`) | %19.7 | **%47.4** | **%49.1** | %6.9 | **`2-3 Gol`** (%47.4) / **`1.5 Üst`** (%80.3) |
| `01:30` | **Coritiba - Santos** | `2.88` (`1.20/1.68`) | %20.1 | **%47.6** | **%48.7** | %6.6 | **`2-3 Gol`** (%47.6) / **`1.5 Üst`** (%79.9) |
| `15:00` | **Güzide Gebze Spor - Ankaraspor** | `2.84` (`1.23/1.61`) | %20.7 | **%47.8** | **%48.2** | %6.3 | **`2-3 Gol`** (%47.8) / **`1.5 Üst`** (%79.3) |

### 2.3. `1. ve 2. Yarı KG Var`, `2. Yarı KG Var` ve Devre Alt/Üst Seçkisi
| Saat | Karşılaşma | `Genel KG Var` | `1. Yarı KG` | `2. Yarı KG` | `1Y ve 2Y KG` | `İY 0.5 Üst` | `2Y 1.5 Üst` | Önerilen Devre/KG Tercihi |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `20:45` | **BK Häcken - Manchester City** | **%52.2** | %24.1 | **%31.8** | %8.2 | %79.4 | %63.5 | **`KG Var`** (%52.2) / **`2. Yarı KG Var`** (%31.8) *(Kademe İndirimi)* |
| `03:30` | **Grêmio - Bahia** | **%61.7** | %21.5 | **%32.8** | %7.4 | %69.2 | %52.1 | **`KG Var`** (%61.7) / **`2. Yarı KG Var`** (%32.8) *(Kademe İndirimi)* |
| `01:30` | **Coritiba - Santos** | **%59.7** | %20.5 | **%31.4** | %6.8 | %68.2 | %50.8 | **`KG Var`** (%59.7) / **`2. Yarı KG Var`** (%31.4) *(Kademe İndirimi)* |
| `02:30` | **Cruzeiro - Palmeiras** | **%60.0** | %20.5 | **%31.4** | %6.8 | %67.6 | %50.0 | **`KG Var`** (%60.0) / **`2. Yarı KG Var`** (%31.4) *(Kademe İndirimi)* |
| `13:00` | **Adana Demirspor - GMG Kastamonuspor** | **%58.5** | %21.1 | **%29.8** | %6.7 | %69.9 | %49.9 | **`KG Var`** (%58.5) / **`2. Yarı KG Var`** (%29.8) *(Kademe İndirimi)* |
| `13:00` | **Ankara Demirspor - 52 Orduspor FK** | **%59.0** | %20.9 | **%29.7** | %6.6 | %68.2 | %47.7 | **`KG Var`** (%59.0) / **`2. Yarı KG Var`** (%29.7) *(Kademe İndirimi)* |
| `22:00` | **London City Lionesses - Brighton & Hove Albion** | **%51.3** | %21.2 | **%28.5** | %6.6 | %67.7 | %45.9 | **`KG Var`** (%51.3) / **`2. Yarı KG Var`** (%28.5) *(Kademe İndirimi)* |
| `02:00` | **Remo - Chapecoense** | **%57.6** | %20.2 | **%30.8** | %6.6 | %70.6 | %53.9 | **`KG Var`** (%57.6) / **`2. Yarı KG Var`** (%30.8) *(Kademe İndirimi)* |
| `20:45` | **Real Madrid - Internazionale** | **%46.9** | %21.4 | **%28.2** | %6.5 | %80.8 | %65.2 | **`KG Var`** (%46.9) / **`2. Yarı KG Var`** (%28.2) *(Kademe İndirimi)* |
| `16:00` | **Bengaluru United FC - Sreenidi Deccan FC** | **%57.2** | %20.8 | **%28.4** | %6.2 | %68.1 | %45.9 | **`KG Var`** (%57.2) / **`2. Yarı KG Var`** (%28.4) *(Kademe İndirimi)* |

### 2.4. Kesin Skor & En Düşük Entropili Dar Skor Kümeleri (`Top-2 / Top-3 Skor`)
| Saat | Karşılaşma | Lig | Entropi | #1 Kesin Skor | #2 Kesin Skor | #3 Kesin Skor | Top-3 Skor Kümesi Toplam Olasılığı (Adil Oran) | #1 İY Skoru |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `22:30` | **CD Minera - FC Cartagena** | Spanish Copa del Rey | `2.84` | **`0-0`** (%13.6) | `1-1` (%12.5) | `0-1` (%11.1) | **%37.2** (`2.69`) | `0-0` (%39.5) |
| `22:00` | **Manchester United - Everton** | English WSL Players Cup | `2.90` | **`0-0`** (%13.3) | `1-0` (%12.4) | `1-1` (%11.5) | **%37.1** (`2.69`) | `0-0` (%37.2) |
| `22:30` | **Reus FC Reddis - Barakaldo** | Spanish Copa del Rey | `2.88` | **`0-0`** (%12.6) | `0-1` (%12.3) | `1-1` (%11.9) | **%36.8** (`2.72`) | `0-0` (%37.8) |
| `22:30` | **CD Samper - Valencia** | Spanish Copa de la Reina | `2.97` | **`0-0`** (%12.6) | `1-1` (%11.5) | `1-0` (%10.9) | **%35.1** (`2.85`) | `0-0` (%35.8) |
| `21:00` | **CP Cacereño - Alavés** | Spanish Copa de la Reina | `2.98` | **`0-0`** (%12.0) | `1-0` (%11.9) | `1-1` (%10.9) | **%34.8** (`2.88`) | `0-0` (%34.5) |
| `13:00` | **MKE Ankaragücü - Kırklarelispor** | Nesine 2. Lig (12. Hafta) | `2.85` | **`1-1`** (%13.6) | `1-0` (%10.8) | `2-1` (%10.0) | **%34.4** (`2.90`) | `0-0` (%34.6) |
| `22:00` | **Tottenham Hotspur - Leicester City** | English WSL Players Cup | `2.98` | **`1-0`** (%12.8) | `2-0` (%11.1) | `0-0` (%10.6) | **%34.4** (`2.91`) | `0-0` (%31.9) |
| `13:00` | **Serik Spor - Erzincanspor** | Nesine 2. Lig (12. Hafta) | `2.85` | **`1-1`** (%13.3) | `0-1` (%10.9) | `1-2` (%10.2) | **%34.4** (`2.91`) | `0-0` (%34.2) |
| `13:00` | **Hatayspor - İnegöl Kafkas SK** | Nesine 2. Lig (12. Hafta) | `2.86` | **`1-1`** (%12.1) | `0-1` (%11.2) | `0-2` (%11.1) | **%34.4** (`2.91`) | `0-0` (%32.7) |
| `21:00` | **Portugalete - Real Unión Irun** | Spanish Copa del Rey | `2.95` | **`1-1`** (%12.1) | `0-0` (%11.8) | `0-1` (%10.4) | **%34.3** (`2.92`) | `0-0` (%36.2) |
| `22:00` | **Alcoyano - Mallorca** | Spanish Copa del Rey | `2.94` | **`0-1`** (%12.7) | `0-2` (%11.0) | `0-0` (%10.3) | **%34.1** (`2.94`) | `0-0` (%33.6) |
| `13:00` | **Seza Çimento Elazığspor - Menemen FK** | Nesine 2. Lig (12. Hafta) | `2.86` | **`2-0`** (%12.8) | `1-0` (%10.8) | `2-1` (%10.2) | **%33.9** (`2.95`) | `0-0` (%29.5) |
| `22:45` | **Lye Town - Peterborough United** | English Women's FA Cup | `3.00` | **`0-0`** (%11.8) | `1-1` (%11.5) | `1-0` (%10.5) | **%33.9** (`2.95`) | `0-0` (%34.5) |
| `02:30` | **Flamengo - Athletico-PR** | Brazilian Serie A | `2.89` | **`2-0`** (%13.2) | `3-0` (%11.1) | `1-0` (%9.5) | **%33.8** (`2.96`) | `1-0` (%27.3) |

---

## 3. Bugün Oynanacak Tüm 45 Maçın Saat Sıralı Tam Omni-Market Analiz Tablosu

### BÖLÜM 3.1: Türkiye Nesine 2. Lig (12. Hafta — 13:00 & 15:00 TSİ, 17 Maç)

| # | Saat | Karşılaşma | Beklenen Gol (`xG: Ev-Dep / 1Y-2Y`) | `MS 1 / X / 2` | `2.5 Üst / Alt` | `İY 1.5 Alt` & `2Y 0.5 Üst` | `KG Var` (`1Y / 2Y KG`) | Gol Bandı & `#1 İY/MS` | En Olası 3 Skor | Engellenen Tuzak | **En Geçerli Tahmin (`>=1.20`)** |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| 1 | `13:00` | **12 Bingölspor - Sakaryaspor** | `1.15-1.40` (`1.10/1.45`) | %29.7 / %28.5 / %41.8 | %47.2 / %52.8 | %68.5 / %76.7 | %54.0 (%18.3/%26.3) | `2-4 Gol` (%63.1) & `İY/MS 2/2` (%22.5) | `1-1` (%14.2), `0-1` (%10.0), `1-2` (%9.3) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.20`** (%74.1) |
| 2 | `13:00` | **1461 Trabzon FK - Kahramanmaraş İstiklalspor** | `1.35-1.35` (`1.17/1.53`) | %36.0 / %27.9 / %36.0 | %51.0 / %49.0 | %66.2 / %78.6 | %57.5 (%20.1/%28.6) | `2-4 Gol` (%63.8) & `İY/MS 1/1` (%19.2) | `1-1` (%13.8), `1-2` (%8.8), `2-1` (%8.8) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.24`** (%71.7) |
| 3 | `13:00` | **Adana Demirspor - GMG Kastamonuspor** | `1.78-1.12` (`1.25/1.65`) | %52.3 / %25.1 / %22.6 | %55.9 / %44.1 | %63.2 / %80.9 | %58.5 (%21.1/%29.8) | `2-4 Gol` (%64.1) & `İY/MS 1/1` (%30.6) | `1-1` (%12.3), `2-1` (%10.4), `1-0` (%8.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.24`** (%69.9) |
| 4 | `13:00` | **Ankara Demirspor - 52 Orduspor FK** | `1.40-1.38` (`1.20/1.58`) | %36.7 / %27.5 / %35.8 | %53.0 / %47.0 | %65.0 / %79.6 | %59.0 (%20.9/%29.7) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%19.8) | `1-1` (%13.5), `2-1` (%8.9), `1-2` (%8.8) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.28`** (%68.2) |
| 5 | `13:00` | **Hatayspor - İnegöl Kafkas SK** | `0.90-1.82` (`1.17/1.55`) | %16.9 / %24.3 / %58.8 | %51.5 / %48.5 | %66.0 / %79.0 | %52.0 (%18.0/%25.7) | `2-4 Gol` (%63.8) & `İY/MS 2/2` (%34.6) | `1-1` (%12.1), `0-1` (%11.2), `0-2` (%11.1) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.25`** (%71.3) |
| 6 | `13:00` | **ISBAŞ Isparta 32 Spor - Somaspor** | `1.69-1.08` (`1.20/1.57`) | %51.1 / %26.0 / %22.9 | %52.8 / %47.2 | %65.1 / %79.5 | %56.3 (%19.8/%28.2) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%29.4) | `1-1` (%12.9), `2-1` (%10.3), `1-0` (%9.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.27`** (%70.1) |
| 7 | `13:00` | **MKE Ankaragücü - Kırklarelispor** | `1.56-1.03` (`1.12/1.47`) | %49.0 / %27.3 / %23.7 | %48.2 / %51.8 | %67.8 / %77.2 | %53.2 (%18.1/%26.0) | `2-4 Gol` (%63.3) & `İY/MS 1/1` (%27.6) | `1-1` (%13.6), `1-0` (%10.8), `2-1` (%10.0) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.20`** (%74.2) |
| 8 | `13:00` | **Serik Spor - Erzincanspor** | `1.00-1.62` (`1.13/1.49`) | %22.0 / %26.7 / %51.3 | %49.0 / %51.0 | %67.5 / %77.7 | %53.1 (%18.2/%26.0) | `2-4 Gol` (%63.4) & `İY/MS 2/2` (%29.0) | `1-1` (%13.3), `0-1` (%10.9), `1-2` (%10.2) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.21`** (%73.5) |
| 9 | `13:00` | **Seza Çimento Elazığspor - Menemen FK** | `2.17-0.76` (`1.27/1.67`) | %69.9 / %19.5 / %10.6 | %56.6 / %43.4 | %62.7 / %81.3 | %49.0 (%17.4/%24.8) | `2-4 Gol` (%63.9) & `İY/MS 1/1` (%44.4) | `2-0` (%12.8), `1-0` (%10.8), `2-1` (%10.2) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 1` @ `1.27`** (%69.9) |
| 10 | `13:00` | **Şanlıurfaspor - Efor Çay Erbaaspor** | `1.74-1.05` (`1.21/1.58`) | %53.1 / %25.4 / %21.5 | %53.3 / %46.7 | %64.8 / %79.7 | %56.0 (%19.8/%28.1) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%30.9) | `1-1` (%12.6), `2-1` (%10.4), `1-0` (%9.8) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.28`** (%69.7) |
| 11 | `15:00` | **Aliağa Futbol A.Ş. - Sebat Gençlik Spor** | `1.66-1.12` (`1.20/1.58`) | %49.4 / %26.2 / %24.4 | %53.0 / %47.0 | %65.0 / %79.6 | %57.1 (%20.2/%28.6) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%28.2) | `1-1` (%13.0), `2-1` (%10.2), `1-0` (%9.4) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.27`** (%69.9) |
| 12 | `15:00` | **Arnavutköy Belediyesi Futbol SK - 68 Aksaray Belediyespor** | `1.08-1.60` (`1.16/1.52`) | %24.4 / %26.9 / %48.8 | %50.5 / %49.5 | %66.6 / %78.4 | %55.2 (%19.1/%27.3) | `2-4 Gol` (%63.7) & `İY/MS 2/2` (%27.4) | `1-1` (%13.4), `1-2` (%10.1), `0-1` (%10.1) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.23`** (%72.2) |
| 13 | `15:00` | **Fethiyespor - Kütahyaspor** | `1.23-1.44` (`1.15/1.52`) | %31.1 / %27.9 / %41.0 | %50.3 / %49.7 | %66.7 / %78.2 | %56.6 (%19.6/%28.0) | `2-4 Gol` (%63.7) & `İY/MS 2/2` (%22.2) | `1-1` (%13.9), `1-2` (%9.4), `0-1` (%9.0) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.23`** (%72.4) |
| 14 | `15:00` | **Güzide Gebze Spor - Ankaraspor** | `1.96-0.88` (`1.23/1.61`) | %62.5 / %22.6 / %14.9 | %54.5 / %45.5 | %64.0 / %80.3 | %52.4 (%18.5/%26.4) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%38.1) | `2-0` (%11.4), `1-1` (%11.2), `1-0` (%10.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.26`** (%69.2) |
| 15 | `15:00` | **Karacabey Belediyespor - Beyoğlu Yeni Çarşı** | `1.33-1.29` (`1.13/1.49`) | %36.8 / %28.4 / %34.8 | %49.0 / %51.0 | %67.4 / %77.6 | %55.9 (%19.2/%27.5) | `2-4 Gol` (%63.5) & `İY/MS 1/1` (%19.6) | `1-1` (%14.1), `2-1` (%8.8), `1-0` (%8.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.21`** (%73.5) |
| 16 | `15:00` | **Çorluspor 1947 - Muş Spor** | `1.27-1.42` (`1.16/1.53`) | %32.5 / %27.9 / %39.6 | %50.8 / %49.2 | %66.4 / %78.5 | %57.1 (%19.9/%28.4) | `2-4 Gol` (%63.8) & `İY/MS 2/2` (%21.3) | `1-1` (%13.8), `1-2` (%9.2), `0-1` (%8.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.24`** (%71.9) |
| 17 | `15:00` | **İnegölspor - İskenderunspor A.Ş.** | `1.77-0.97` (`1.19/1.56`) | %55.8 / %25.0 / %19.2 | %52.0 / %48.0 | %65.6 / %79.1 | %53.8 (%18.8/%26.8) | `2-4 Gol` (%63.9) & `İY/MS 1/1` (%32.8) | `1-1` (%12.4), `1-0` (%10.6), `2-1` (%10.5) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.26`** (%70.8) |

### BÖLÜM 3.2: UEFA Kadınlar Şampiyonlar Ligi (`20:45 & 23:00 TSİ`, 4 Maç — Canlı Oranlı)

| # | Saat | Karşılaşma | Beklenen Gol (`xG: Ev-Dep / 1Y-2Y`) | `MS 1 / X / 2` | `2.5 Üst / Alt` | `İY 1.5 Alt` & `2Y 0.5 Üst` | `KG Var` (`1Y / 2Y KG`) | Gol Bandı & `#1 İY/MS` | En Olası 3 Skor | Engellenen Tuzak | **En Geçerli Tahmin (`>=1.20`)** |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| 20 | `20:45` | **BK Häcken - Manchester City** | `0.91-2.87` (`1.67/2.13`) | %10.3 / %16.9 / %72.8 | %66.2 / %33.8 | %49.9 / %87.6 | %52.2 (%24.1/%31.8) | `2-4 Gol` (%50.2) & `İY/MS 2/2` (%49.9) | `0-2` (%9.3), `0-1` (%8.2), `0-3` (%7.6) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 2` @ `1.34`** (%72.8) |
| 21 | `20:45` | **Real Madrid - Internazionale** | `3.17-0.74` (`1.73/2.20`) | %79.2 / %14.1 / %6.7 | %67.8 / %32.2 | %47.8 / %88.4 | %46.9 (%21.4/%28.2) | `2-4 Gol` (%49.1) & `İY/MS 1/1` (%57.2) | `2-0` (%10.1), `3-0` (%8.9), `1-0` (%8.4) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 1` @ `1.20`** (%79.2) |
| 37 | `23:00` | **Chelsea - Paris Saint-Germain** | `2.77-0.72` (`1.55/1.96`) | %75.2 / %16.7 / %8.1 | %61.8 / %38.2 | %53.5 / %85.4 | %44.9 (%19.6/%26.2) | `2-4 Gol` (%51.8) & `İY/MS 1/1` (%52.0) | `2-0` (%11.1), `1-0` (%10.1), `3-0` (%8.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 1` @ `1.28`** (%75.2) |
| 38 | `23:00` | **Juventus - OH Leuven** | `2.65-0.76` (`1.51/1.92`) | %72.8 / %17.9 / %9.4 | %60.5 / %39.5 | %54.8 / %84.7 | %46.1 (%20.1/%26.8) | `2-4 Gol` (%52.3) & `İY/MS 1/1` (%49.4) | `2-0` (%10.9), `1-0` (%10.2), `3-0` (%8.4) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 1` @ `1.32`** (%72.8) |

### BÖLÜM 3.3: İspanya Kral Kupası (`Copa del Rey` & `Copa de la Reina` — `20:00–22:30 TSİ`, 9 Maç)

| # | Saat | Karşılaşma | Beklenen Gol (`xG: Ev-Dep / 1Y-2Y`) | `MS 1 / X / 2` | `2.5 Üst / Alt` | `İY 1.5 Alt` & `2Y 0.5 Üst` | `KG Var` (`1Y / 2Y KG`) | Gol Bandı & `#1 İY/MS` | En Olası 3 Skor | Engellenen Tuzak | **En Geçerli Tahmin (`>=1.20`)** |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| 19 | `20:00` | **Levante - Eibar** | `1.98-0.94` (`1.28/1.64`) | %58.1 / %24.3 / %17.6 | %52.0 / %48.0 | %62.4 / %80.0 | %48.4 (%20.0/%27.5) | `2-4 Gol` (%54.2) & `İY/MS 1/1` (%35.6) | `1-0` (%11.1), `0-0` (%9.7), `1-1` (%9.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.20`** (%73.9) |
| 22 | `21:00` | **CP Cacereño - Alavés** | `1.63-0.97` (`1.14/1.46`) | %50.1 / %27.7 / %22.3 | %45.6 / %54.4 | %67.2 / %76.2 | %46.2 (%18.2/%25.2) | `2-4 Gol` (%54.0) & `İY/MS 1/1` (%28.9) | `0-0` (%12.0), `1-0` (%11.9), `1-1` (%10.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.22`** (%72.7) |
| 23 | `21:00` | **Portugalete - Real Unión Irun** | `1.17-1.33` (`1.09/1.42`) | %31.9 / %29.3 / %38.9 | %44.3 / %55.7 | %68.9 / %75.3 | %48.2 (%18.2/%25.7) | `2-4 Gol` (%55.6) & `İY/MS 2/2` (%20.6) | `1-1` (%12.1), `0-0` (%11.8), `0-1` (%10.4) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.30`** (%68.7) |
| 24 | `21:00` | **Utebo - CD Sabadell** | `0.82-1.91` (`1.19/1.55`) | %15.6 / %24.3 / %60.1 | %49.0 / %51.0 | %65.6 / %78.2 | %45.4 (%17.5/%24.5) | `2-4 Gol` (%55.9) & `İY/MS 2/2` (%36.1) | `0-1` (%12.4), `0-2` (%10.9), `1-1` (%10.0) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.23`** (%72.3) |
| 30 | `22:00` | **Alcoyano - Mallorca** | `0.81-1.88` (`1.17/1.52`) | %15.5 / %24.6 / %59.9 | %48.1 / %51.9 | %66.2 / %77.7 | %44.6 (%17.0/%23.9) | `2-4 Gol` (%55.8) & `İY/MS 2/2` (%35.9) | `0-1` (%12.7), `0-2` (%11.0), `0-0` (%10.3) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.24`** (%71.6) |
| 31 | `22:00` | **Badajoz - Tenerife** | `1.30-1.23` (`1.10/1.43`) | %37.0 / %29.2 / %33.8 | %44.7 / %55.3 | %68.5 / %75.5 | %48.7 (%18.5/%26.0) | `2-4 Gol` (%55.7) & `İY/MS 1/1` (%19.7) | `1-1` (%12.1), `0-0` (%11.6), `1-0` (%9.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.20`** (%74.2) |
| 32 | `22:30` | **CD Samper - Valencia** | `1.40-1.12` (`1.10/1.42`) | %41.4 / %29.3 / %29.3 | %43.9 / %56.1 | %68.4 / %75.2 | %46.9 (%18.3/%25.5) | `2-4 Gol` (%53.9) & `İY/MS 1/1` (%22.7) | `0-0` (%12.6), `1-1` (%11.5), `1-0` (%10.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.20`** (%74.2) |
| 33 | `22:30` | **CD Minera - FC Cartagena** | `1.13-1.18` (`1.00/1.31`) | %33.3 / %30.8 / %35.9 | %39.7 / %60.3 | %71.8 / %72.4 | %44.7 (%16.2/%23.0) | `2-4 Gol` (%54.3) & `İY/MS 0/0` (%21.5) | `0-0` (%13.6), `1-1` (%12.5), `0-1` (%11.1) | `İY 0`, `+6 Gol`, `5.5 Üst` | **`2Y 0.5 Üst` @ `1.20`** (%72.4) |
| 34 | `22:30` | **Reus FC Reddis - Barakaldo** | `0.97-1.44` (`1.05/1.37`) | %24.8 / %29.2 / %46.0 | %42.1 / %57.9 | %70.3 / %74.0 | %45.2 (%16.6/%23.6) | `2-4 Gol` (%54.9) & `İY/MS 2/2` (%25.2) | `0-0` (%12.6), `0-1` (%12.3), `1-1` (%11.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 1.5 Alt` @ `1.24`** (%70.3) |

### BÖLÜM 3.4: İngiltere Kadınlar Lig Kupası & FA Cup (`22:00 & 22:45 TSİ`, 6 Maç)

| # | Saat | Karşılaşma | Beklenen Gol (`xG: Ev-Dep / 1Y-2Y`) | `MS 1 / X / 2` | `2.5 Üst / Alt` | `İY 1.5 Alt` & `2Y 0.5 Üst` | `KG Var` (`1Y / 2Y KG`) | Gol Bandı & `#1 İY/MS` | En Olası 3 Skor | Engellenen Tuzak | **En Geçerli Tahmin (`>=1.20`)** |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| 25 | `22:00` | **London City Lionesses - Brighton & Hove Albion** | `1.49-1.26` (`1.22/1.53`) | %40.9 / %27.9 / %31.2 | %48.9 / %51.1 | %64.5 / %77.9 | %51.3 (%21.2/%28.5) | `2-4 Gol` (%54.8) & `İY/MS 1/1` (%22.7) | `1-1` (%11.2), `0-0` (%10.7), `1-0` (%9.5) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.24`** (%71.8) |
| 26 | `22:00` | **Manchester United - Everton** | `1.46-0.97` (`1.07/1.35`) | %46.1 / %29.4 / %24.5 | %42.0 / %58.0 | %69.2 / %73.7 | %44.5 (%17.2/%23.4) | `2-4 Gol` (%53.6) & `İY/MS 1/1` (%25.7) | `0-0` (%13.3), `1-0` (%12.4), `1-1` (%11.5) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 1.5 Alt` @ `1.26`** (%69.2) |
| 27 | `22:00` | **Nottingham Forest - Liverpool** | `1.32-1.27` (`1.15/1.45`) | %36.5 / %29.1 / %34.4 | %45.5 / %54.5 | %66.9 / %75.9 | %48.9 (%19.6/%26.5) | `2-4 Gol` (%54.4) & `İY/MS 1/1` (%19.6) | `0-0` (%11.9), `1-1` (%11.6), `1-0` (%9.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.22`** (%72.9) |
| 28 | `22:00` | **Tottenham Hotspur - Leicester City** | `1.99-0.78` (`1.23/1.54`) | %62.1 / %23.9 / %14.1 | %49.1 / %50.9 | %64.1 / %78.1 | %43.6 (%17.6/%23.7) | `2-4 Gol` (%54.3) & `İY/MS 1/1` (%38.5) | `1-0` (%12.8), `2-0` (%11.1), `0-0` (%10.6) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.24`** (%71.7) |
| 29 | `22:00` | **West Ham United - Wolverhampton** | `1.67-1.07` (`1.21/1.53`) | %48.9 / %27.1 / %24.1 | %48.6 / %51.4 | %64.6 / %77.8 | %49.4 (%20.3/%27.2) | `2-4 Gol` (%54.6) & `İY/MS 1/1` (%28.3) | `1-1` (%10.8), `1-0` (%10.8), `0-0` (%10.8) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`1.5 Üst` @ `1.24`** (%71.5) |
| 35 | `22:45` | **Lye Town - Peterborough United** | `1.45-1.15` (`1.15/1.45`) | %42.1 / %28.7 / %29.2 | %45.7 / %54.3 | %66.7 / %76.0 | %48.5 (%19.5/%26.3) | `2-4 Gol` (%54.4) & `İY/MS 1/1` (%23.3) | `0-0` (%11.8), `1-1` (%11.5), `1-0` (%10.5) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.22`** (%72.7) |

### BÖLÜM 3.5: Brezilya Série A & Güney Amerika / Hindistan (`16:00 & 23:00–03:30 TSİ`, 9 Maç — Canlı Oranlı)

| # | Saat | Karşılaşma | Beklenen Gol (`xG: Ev-Dep / 1Y-2Y`) | `MS 1 / X / 2` | `2.5 Üst / Alt` | `İY 1.5 Alt` & `2Y 0.5 Üst` | `KG Var` (`1Y / 2Y KG`) | Gol Bandı & `#1 İY/MS` | En Olası 3 Skor | Engellenen Tuzak | **En Geçerli Tahmin (`>=1.20`)** |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| 18 | `16:00` | **Bengaluru United FC - Sreenidi Deccan FC** | `1.46-1.27` (`1.20/1.53`) | %40.6 / %27.7 / %31.7 | %51.5 / %48.5 | %65.0 / %78.4 | %57.2 (%20.8/%28.4) | `2-4 Gol` (%62.9) & `İY/MS 1/1` (%22.5) | `1-1` (%13.4), `2-1` (%9.1), `1-0` (%8.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.26`** (%70.9) |
| 36 | `23:00` | **Alianza Atlético - Melgar** | `1.53-1.16` (`1.14/1.55`) | %45.1 / %27.4 / %27.5 | %50.8 / %49.2 | %67.3 / %79.1 | %56.3 (%18.9/%28.6) | `2-4 Gol` (%63.8) & `İY/MS 1/1` (%24.8) | `1-1` (%13.6), `2-1` (%9.8), `1-0` (%9.4) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.24`** (%71.9) |
| 39 | `01:30` | **Coritiba - Santos** | `1.23-1.65` (`1.20/1.68`) | %27.3 / %26.2 / %46.4 | %55.3 / %44.7 | %65.0 / %81.5 | %59.7 (%20.5/%31.4) | `2-4 Gol` (%64.1) & `İY/MS 2/2` (%25.5) | `1-1` (%12.8), `1-2` (%10.0), `0-1` (%8.3) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`ÇŞ 02` @ `1.20`** (%72.7) |
| 40 | `02:00` | **Remo - Chapecoense** | `2.04-1.01` (`1.28/1.77`) | %60.8 / %22.3 / %16.8 | %59.4 / %40.6 | %62.4 / %83.2 | %57.6 (%20.2/%30.8) | `2-4 Gol` (%63.8) & `İY/MS 1/1` (%36.5) | `1-1` (%10.9), `2-1` (%10.7), `2-0` (%9.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.23`** (%70.6) |
| 41 | `02:30` | **Cruzeiro - Palmeiras** | `1.40-1.44` (`1.18/1.65`) | %35.6 / %27.2 / %37.3 | %54.3 / %45.7 | %65.6 / %81.0 | %60.0 (%20.5/%31.4) | `2-4 Gol` (%64.1) & `İY/MS 2/2` (%19.5) | `1-1` (%13.3), `1-2` (%9.0), `2-1` (%8.7) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.29`** (%67.6) |
| 42 | `02:30` | **Flamengo - Athletico-PR** | `2.52-0.68` (`1.34/1.87`) | %77.8 / %15.2 / %6.9 | %62.9 / %37.1 | %60.0 / %84.9 | %47.1 (%16.6/%25.2) | `2-4 Gol` (%63.0) & `İY/MS 1/1` (%51.3) | `2-0` (%13.2), `3-0` (%11.1), `1-0` (%9.5) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`MS 1` @ `1.26`** (%77.8) |
| 43 | `02:30` | **Always Ready - Real Potosí** | `1.95-0.88` (`1.21/1.62`) | %62.1 / %22.9 / %15.1 | %53.9 / %46.1 | %64.6 / %80.2 | %51.9 (%18.2/%26.5) | `2-4 Gol` (%63.0) & `İY/MS 1/1` (%37.5) | `2-0` (%11.3), `1-1` (%11.1), `1-0` (%10.9) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.27`** (%68.5) |
| 44 | `03:30` | **Corinthians - Botafogo** | `1.70-1.03` (`1.14/1.58`) | %52.6 / %25.9 / %21.5 | %51.6 / %48.4 | %67.1 / %79.7 | %54.8 (%18.2/%28.2) | `2-4 Gol` (%63.8) & `İY/MS 1/1` (%29.8) | `1-1` (%12.8), `2-1` (%10.4), `1-0` (%10.3) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`3.5 Alt` @ `1.25`** (%71.2) |
| 45 | `03:30` | **Grêmio - Bahia** | `1.59-1.35` (`1.23/1.72`) | %42.3 / %26.4 / %31.4 | %57.0 / %43.0 | %63.9 / %82.2 | %61.7 (%21.5/%32.8) | `2-4 Gol` (%64.0) & `İY/MS 1/1` (%23.2) | `1-1` (%12.7), `2-1` (%9.6), `1-2` (%8.1) | `2.5 Alt`, `1.5 Alt`, `0-1 Gol` | **`İY 0.5 Üst` @ `1.26`** (%69.2) |

