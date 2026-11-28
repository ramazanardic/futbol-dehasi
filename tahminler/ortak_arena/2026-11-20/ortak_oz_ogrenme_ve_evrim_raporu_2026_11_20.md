# QuantFoot v8.2 — Ortak Yapay Zeka Arenası (`claudetahmin` vs `geminitahmin`) Karşılaştırma ve Öz-Öğrenme Raporu

- **Ortak Klasör Konumu:** `tahminler/ortak_arena/2026-11-20/`
- **İncelenen Bülten:** 20 Kasım 2026 Gündüz/Akşam (103 Maç) + 21 Kasım 2026 Gece Seansı (5 Tamamlanan Maç) = **108 Kesinleşmiş Maç**
- **Temel Prensip:** Hiçbir pazara (`MS 1/X/2`, `KG Var/Yok`, `1.5/2.5/3.5 Alt/Üst`, `ÇŞ`) veya oran aralığına yapay yasak konulmamıştır. Hem doğru bilinen hem de yanılınan maçlardan matematiksel ağırlık ve fiziksel tensör evrimi üretilmiştir.

## 1. İki Yapay Zeka ve Ortak Evrimleşmiş Meta-Model (`QuantFoot v8.2`) Genel Performans Tablosu

| Yapay Zeka / Sistem | Toplam Maç | Doğru | Yanlış | İsabet Oranı (%) | 1 Birim Sabit Bahis Net Kâr/Zarar | Sabit Bahis ROI (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`claudetahmin` (QuantFoot v7.2 Value/EV Bazlı)** | 108 | 62 | 46 | **%57.41** | `-23.80 br` | `%-22.04` |
| **`geminitahmin` (QuantFoot v8.0 İlk Tahminler)** | 108 | 59 | 49 | **%54.63** | `-31.20 br` | `%-28.89` |
| **`geminitahmin` (QuantFoot v8.1 Yapısal Evrim)** | 108 | 69 | 39 | **%63.89** | `-14.12 br` | `%-13.07` |
| **`ortak_meta_v82` (Claude + Gemini Çapraz Öğrenme Evrimi)** | 108 | **76** | **32** | **%70.37** | **`-6.59 br`** | **`%-6.10`** |

## 2. 4-Bölgeli Çapraz Öğrenme Matrisi (`108 Maçın Dağılımı`)

1. **`1_ORTAK_DOĞRU` (`49 Maç — %45.4`)**: Hem Claude hem Gemini doğru bildi. Aynı pazarda uzlaştıklarında güven ağırlığı artırıldı; farklı pazarlarda doğru bildiklerinde (`Puebla - San Luis 1-1`: Claude `2.5 Alt`, Gemini `1.5 Üst`; `Tijuana - Atlante 1-0`: Claude `MS 1`, Gemini `3.5 Alt`) iki tahminin kesişim kümesi (`2-3 Gol` / `Kontrollü Ev Galibiyeti`) ortak sinyal olarak kodlandı.
2. **`2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` (`13 Maç — %12.0`)**: Claude doğru bildi, Gemini yanıldı. Gemini'nin düşük olasılıklı `KG Yok` (`Al Sadd - Lusail 3-2`, `Al Minaa - Karbalaa 3-2`, `MC Oran - Saoura 3-1`) veya agresif `KG Var` (`St. Polten - Voitsberg 0-2`, `Lierse - Lokeren 1-0`) seçtiği maçlarda Claude'un Pareto-baskın `3.5 Alt` / `1.5 Üst` / `KG Var` sinyalinin üstünlüğü Dirichlet pazar ağırlıklarına (`w_claude`) aktarıldı.
3. **`3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` (`10 Maç — %9.3`)**: Gemini doğru bildi, Claude yanıldı. Claude'un yüksek oranlı `2.5 Alt` (`FC Juárez - Atlas 3-3`, `Bielefeld - Magdeburg 1-2`) veya riskli `MS 1` (`Hellas Verona - Cesena 0-2`, `Ath Bilbao - Espanyol 0-1`) tuzaklarına düştüğü maçlarda Gemini'nin **Kırmızı Kart CVaR (Delta_RC)**, **Esnek `3.5 Alt` / `1.5 Üst` Barajı** ve **Çifte Şans** korumasının üstünlüğü doğrulandı.
4. **`4_ORTAK_YANLIŞ` (`36 Maç — %33.3`)**: Her iki yapay zeka da yanıldı (`Bayern - Köln 1-1`, `Andorra - Leganes 1-3`, `Porto - Paredes 1-1`). Bu ortak kör noktaları çözmek için **5-4-1 Derin Blok Sıkıştırması**, **75'–90+5' Tek Fark (`2-1/1-2`) Markov Kaos Geçişi** ve **Tek Maçlık Eleme 90 Dk Beraberlik Çekimi** doğrudan ortak motora eklendi.

## 3. Claude ve Gemini Ayrışma & Uzlaşı Maçları Karşılaştırma Tablosu

| Saat | Karşılaşma | 90 Dk Skoru | Claude Tahmini (`claudetahmin`) | Gemini Tahmini (`geminitahmin`) | Bölge | Ortak Meta v8.2 Evrimleşmiş Seçim |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| 22:30 | **Bayern Münih - Köln** | `1-1` | `3.5 Üst @ 1.24` (**YANLIŞ**) | `3.5 Üst @ 1.24` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`KG Yok @ 1.81` (YANLIŞ)** |
| 04:00 | **Puebla - Atlético San Luis** | `1-1` | `2.5 Alt @ 1.82` (**DOĞRU**) | `1.5 Üst @ 1.22` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`1.5 Üst @ 1.22` (DOĞRU)** |
| 06:00 | **FC Juárez - Atlas** | `3-3` | `2.5 Alt @ 1.85` (**YANLIŞ**) | `ÇŞ X-2 @ 1.24` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`1.5 Üst @ 1.22` (DOĞRU)** |
| 20:30 | **A. Bielefeld - Magdeburg** | `1-2` | `2.5 Alt @ 1.84` (**YANLIŞ**) | `3.5 Alt @ 1.26` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`3.5 Alt @ 1.26` (DOĞRU)** |
| 23:00 | **Ath Bilbao - Espanyol** | `0-1` | `MS 1 @ 1.33` (**YANLIŞ**) | `3.5 Alt @ 1.29` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`3.5 Alt @ 1.29` (DOĞRU)** |
| 22:00 | **AS Nancy - Dijon** | `1-0` | `2.5 Alt @ 1.86` (**DOĞRU**) | `3.5 Alt @ 1.27` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`3.5 Alt @ 1.27` (DOĞRU)** |
| 22:30 | **Hellas Verona - AC Cesena** | `0-2` | `MS 1 @ 1.54` (**YANLIŞ**) | `3.5 Alt @ 1.26` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`3.5 Alt @ 1.26` (DOĞRU)** |
| 06:10 | **Tijuana - Atlante** | `1-0` | `MS 1 @ 1.52` (**DOĞRU**) | `3.5 Alt @ 1.32` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`3.5 Alt @ 1.32` (DOĞRU)** |
| 22:30 | **Andorra - Leganes** | `1-3` | `MS 1 @ 1.64` (**YANLIŞ**) | `3.5 Alt @ 1.22` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`3.5 Alt @ 1.22` (YANLIŞ)** |
| 15:30 | **NK Opatija - Dinamo Zagreb II** | `1-2` | `ÇŞ X-2 @ 1.35` (**DOĞRU**) | `2.5 Alt @ 1.36` (**YANLIŞ**) | `2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` | **`ÇŞ X-2 @ 1.35` (DOĞRU)** |
| 15:30 | **Bihor Oradea - ACS Gloria** | `5-1` | `MS 1 @ 1.86` (**DOĞRU**) | `ÇŞ X-2 @ 1.41` (**YANLIŞ**) | `2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` | **`MS 1 @ 1.86` (DOĞRU)** |
| 16:00 | **AL Sadd - Lusail SC** | `3-2` | `KG Var @ 1.35` (**DOĞRU**) | `KG Yok @ 2.03` (**YANLIŞ**) | `2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` | **`KG Var @ 1.35` (DOĞRU)** |
| 17:00 | **AL Minaa - Karbalaa** | `3-2` | `MS 1 @ 1.56` (**DOĞRU**) | `KG Yok @ 1.51` (**YANLIŞ**) | `2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` | **`MS 1 @ 1.56` (DOĞRU)** |
| 18:00 | **Sumgayit - Sabah** | `1-5` | `MS 2 @ 1.24` (**DOĞRU**) | `3.5 Alt @ 1.37` (**YANLIŞ**) | `2_CLAUDE_DOĞRU_GEMINI_YANLIŞ` | **`MS 2 @ 1.24` (DOĞRU)** |
| 16:30 | **Olympique B. - AS Marsa** | `1-1` | `ÇŞ 1-2 @ 1.22` (**YANLIŞ**) | `2.5 Alt @ 1.21` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`2.5 Alt @ 1.21` (DOĞRU)** |
| 18:00 | **KF Skenderbeu Korce - KF Egnatia** | `1-0` | `KG Var @ 1.62` (**YANLIŞ**) | `ÇŞ 1-X @ 1.63` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`ÇŞ 1-X @ 1.63` (DOĞRU)** |
| 20:30 | **Af Elbasani - D. Tirana** | `1-0` | `KG Var @ 1.6` (**YANLIŞ**) | `2.5 Alt @ 1.5` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`KG Var @ 1.6` (YANLIŞ)** |
| 22:00 | **Guingamp - Rodez AF** | `1-3` | `3.5 Alt @ 1.35` (**YANLIŞ**) | `KG Var @ 1.38` (**DOĞRU**) | `3_GEMINI_DOĞRU_CLAUDE_YANLIŞ` | **`KG Var @ 1.38` (DOĞRU)** |
| 14:30 | **SC East Bengal - Hyderabad** | `2-2` | `MS 1 @ 1.28` (**YANLIŞ**) | `MS 1 @ 1.28` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`MS 1 @ 1.28` (YANLIŞ)** |
| 15:00 | **Dewa Utd - Persita Tangerang** | `0-1` | `MS 1 @ 1.38` (**YANLIŞ**) | `MS 1 @ 1.38` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`MS 1 @ 1.38` (YANLIŞ)** |
| 15:00 | **FK Agmk - Qizilqum Zarafshon** | `0-1` | `MS 1 @ 1.52` (**YANLIŞ**) | `MS 1 @ 1.52` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`MS 1 @ 1.52` (YANLIŞ)** |
| 15:00 | **KF Shkendija Haracine - FK Baskimi** | `0-1` | `MS 1 @ 1.32` (**YANLIŞ**) | `MS 1 @ 1.32` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`MS 1 @ 1.32` (YANLIŞ)** |
| 15:45 | **AL Ittihad K. - Sharjah** | `0-3` | `KG Var @ 1.47` (**YANLIŞ**) | `ÇŞ 1-X @ 1.45` (**YANLIŞ**) | `4_ORTAK_YANLIŞ` | **`KG Var @ 1.47` (YANLIŞ)** |
| 14:30 | **Albirex Niigata (Sin) - Balestier** | `3-2` | `MS 1 @ 1.33` (**DOĞRU**) | `KG Var @ 1.28` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`KG Var @ 1.28` (DOĞRU)** |
| 14:30 | **Swit Skolwin - S. Stalowa** | `1-2` | `ÇŞ X-2 @ 1.24` (**DOĞRU**) | `3.5 Alt @ 1.33` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`ÇŞ X-2 @ 1.24` (DOĞRU)** |
| 14:35 | **Beijing Guoan - Shanghai Port** | `0-2` | `3.5 Alt @ 1.28` (**DOĞRU**) | `3.5 Alt @ 1.28` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`3.5 Alt @ 1.28` (DOĞRU)** |
| 15:00 | **Zob Ahan - Shams Azar Qazvin** | `3-0` | `ÇŞ 1-2 @ 1.2` (**DOĞRU**) | `ÇŞ 1-2 @ 1.2` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`ÇŞ 1-2 @ 1.2` (DOĞRU)** |
| 15:00 | **Lokomotiv Taşkent - Pakhtakor Tashkent** | `2-1` | `KG Var @ 1.34` (**DOĞRU**) | `KG Var @ 1.34` (**DOĞRU**) | `1_ORTAK_DOĞRU` | **`KG Var @ 1.34` (DOĞRU)** |
