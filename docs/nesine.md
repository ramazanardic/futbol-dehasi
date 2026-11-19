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
2. **Global referans fiyat** (sırayla):
   - **Pinnacle** — dünyada "keskin" referans kabul edilen büro; The Odds API üzerinden.
     `ODDS_API_KEY` gerekir.
   - **ESPN** (DraftKings / ESPN BET) — ücretsiz yedek; keskin değil.
   - Referans yoksa maç **fiyatlanmaz**. Adil fiyat asla Nesine'nin kendi oranından türetilmez.
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

## Pinnacle anahtarı ekleme

1. [the-odds-api.com](https://the-odds-api.com) üzerinden ücretsiz anahtar alın (hesabı sizin açmanız gerekir).
2. Windows'ta kalıcı ortam değişkeni olarak kaydedin (yeni açılan terminallerde ve zamanlanmış
   görevlerde geçerli olur):

```bash
setx ODDS_API_KEY "anahtarınız"
```

**Kredi notu:** Betik, The Odds API'nin listelediği bütün futbol yarışmalarını Pinnacle fiyatıyla
çeker; her yarışma isteği yaklaşık 2 kredi harcar. Ücretsiz plan (aylık 500 kredi) günlük tam tarama
için yetmeyebilir; düzenli kullanım için ücretli plan gerekir. The Odds API Pinnacle'ın listelediği
her ligi kapsamaz (ör. Zambiya, Uganda); bu maçlar fiyatlanmadan listelenir.
