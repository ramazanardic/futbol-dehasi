# 21 Kasım 2026 Cumartesi — Gemini (`geminitahmin`) Tahmin ve Kupon Denetim Raporu

## 1. Genel Performans Özeti
- **Gece 500 TL Kuponu (`2.62x`):** **4/4 (Yedek ayakla 5/5) TUTTU** (+810 TL net kâr).
- **Akşam 400 TL Canlı Nesine Kuponu (`4.54x`):** **5/6 isabet** (Yalnızca `Newcastle United 2-2 Arsenal` maçından yattı; alternatif bacak `Atlético Mineiro 0-0 Boca Juniors: 2,5 Alt @ 1.33` de tuttu).
- **Tüm Bülten Maç Tahminleri:** **38 / 49 (%77.6)** genel isabet.

## 2. Akşam Kuponu Ayak Bazlı Denetim ve Kök-Hata Analizi
1. **20:00 — Parma 1-3 AS Roma:** `2,5 Üst @ 1.25` — **TUTTU** (`MS 2 @ 1.28` de tuttu).
2. **20:00 — BSC Young Boys 4-2 FC Thun:** `KG Var @ 1.28` — **TUTTU** (`2,5 Üst @ 1.33` de tuttu).
3. **20:30 — Newcastle United 2-2 Arsenal:** `MS 2 @ 1.35` (`3,5 Alt @ 1.24`) — **YATTI**
   - **Kök Neden (`market_reliability.py` Doğrulaması):** Maç öncesi modelde `P(2.5 Üst) = %46.2` ile düşük toplam gol bölgesine (`DRAW_ZONE_MAX_OVER25 = 0.45`) çok yakındı ve St. James' Park deplasmanında beraberlik riski `r >= 0.24` uyarı sınırındaydı. Ayrıca `Real Madrid 5-1 Celta Vigo` maçında `87'` dakikada gelen teselli golü, `coupon_rules.py` içinde `Karşılıklı gol` (`KG Yok`) ailesinin banko kuponlardan çıkarılmasının (`BANNED_FAMILIES`) ne kadar doğru olduğunu kanıtladı.
4. **20:30 — Sevilla FC 0-2 Real Betis:** `ÇŞ X-2 @ 1.26` — **TUTTU**.
5. **22:45 — Napoli 2-0 Torino:** `MS 1 @ 1.34` — **TUTTU**.
6. **23:00 — Real Madrid 5-1 Celta Vigo:** `2,5 Üst @ 1.20` — **TUTTU** (Yedek ayak `22:30 Atlético Mineiro 0-0 Boca Juniors: 2,5 Alt @ 1.33` — **TUTTU**).
