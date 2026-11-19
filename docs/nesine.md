# Nesine bülteni — global referans fiyatına göre analiz

```bash
python scripts/nesine_global.py --date 2026-11-19
```

Çıktı: `reports/daily/<tarih>/nesine_global.md` ve `.json`. Her sabah 09:00'da zamanlanmış görev
(`scripts/scheduled.py morning`) bunu otomatik çalıştırır.

## Nasıl çalışır

1. **Nesine bülteni** sitenin kendi kullandığı herkese açık JSON akışından çekilir
   (`quantfoot.data.nesine`). Pazar kodları (MTID) Nesine'nin kendi tanım tablosuyla çözülür
   (`src/quantfoot/data/nesine_markets.json`, sitenin `CCAll.min.js` dosyasından; 599 pazar) —
   tahmin edilmez.
2. **Global referans fiyat:** ESPN'in herkese açık oran akışı (DraftKings) — ücretsiz, anahtarsız,
   kotasız. Referansı olmayan maç **fiyatlanmaz**; adil fiyat asla Nesine'nin kendi oranından türetilmez.
3. Referans 1X2 (+ varsa Alt/Üst) marjdan arındırılır (power yöntemi), gol beklentileri hiçbir
   model önseli olmadan (fund_weight = 0) bu fiyata uydurulur ve Nesine'nin her seçimi — İY/MS,
   KG, gol aralığı, handikap, kombineler, ilk gol — tek tutarlı gol dağılımından fiyatlanır
   ([markets.md](markets.md)). Kulüp gol rejimi bu kullanım için yeniden kalibre edildi
   ([research/experiments_2026_11.md](research/experiments_2026_11.md) §4–5).
4. **EV = global adil olasılık × Nesine oranı − 1.** Kalibre edilmemiş yarışmalarda (kadın
   futbolu) yalnızca doğrudan referansı olan pazarlar (1X2, aynı çizgideki Alt/Üst) fiyatlanır.

## İlk bulgu: Nesine marjı (19 Kasım 2026, 60 maç)

- Maç sonucu marjı **%18.4 – %23.5** (Pinnacle'da tipik olarak %2–3).
- Neredeyse bütün pazarlarda ortalama marj **%19 – %23**; kombine ve skor pazarlarında daha yüksek.
- Bu, Nesine'de rastgele bir bahsin uzun vadede yatırılan paranın yaklaşık beşte birini
  kaybettireceği anlamına gelir. Global fiyatı olan 9 maçta adil fiyatın üstünde yalnızca 3 küçük
  seçim çıktı (ESPN referansıyla; güvenilirliği düşük).

Sonuç: Nesine'de kalıcı avantaj ancak tek tek yanlış fiyatlanmış seçimlerde ve keskin bir referansla
ölçülerek aranabilir. Her gün raporun ilk tablosu tam olarak bunu listeler.

## Neden Pinnacle değil? (kaynak seçimi)

Sistemin ileride bozulmaması için yalnızca **ücretsiz, anahtarsız, kotasız ve Türkiye'den
erişilebilir** kaynaklar kullanılır. 19 Kasım 2026'da denenenler:

| Kaynak | Durum |
|---|---|
| football-data.co.uk (Pinnacle oranlı fikstür dosyaları) | Türkiye'de erişime engelli |
| Polymarket, Kalshi (açık tahmin piyasası verisi) | Türkiye'den erişilemiyor (sertifika hatası) |
| Pinnacle | Ücretsiz resmi veri akışı yok |
| The Odds API vb. | Anahtar ve kota gerektiriyor (kaldırıldı) |
| Sofascore / Flashscore / OddsPortal | Yalnızca kazıma ile; kullanım koşulları otomatik toplamayı yasaklıyor ve yapı değişince bozulur |
| **ESPN (DraftKings)** | **Ücretsiz, anahtarsız, erişilebilir — kullanılan kaynak** |

Sınırlamalar: ESPN küçük ligleri (ör. Mısır 2. Lig, Zambiya, Uganda, Irak) kapsamıyor; 19 Kasım'da
61 Nesine maçının 9'u fiyatlanabildi. DraftKings keskin bir büro değildir, bu yüzden küçük artı
EV'ler gürültü olabilir; asıl güçlü sinyal Nesine'nin yüksek marjıdır.
