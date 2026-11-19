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
2. **Global referans fiyat** — maç başına en iyisi seçilir:
   1. **Pinnacle** (football-data.co.uk fikstür dosyaları)
   2. **Smarkets borsası** (alış/satış ortası; düşük komisyonlu borsa fiyatı)
   3. **ESPN** (DraftKings) — yerelde çekilir, en zayıf referans

   1 ve 2 Türkiye'den erişilemediği için GitHub'ın yurt dışındaki sunucularında
   (GitHub Actions, `.github/workflows/global-odds.yml`) günde 5 kez çekilip
   `data/global_odds/latest/references.json` olarak depoya yazılır; sabah görevi önce
   `git pull` yapar. Hiçbir referansı olmayan maç **fiyatlanmaz**; adil fiyat asla Nesine'nin kendi
   oranından türetilmez.
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

## Kaynak seçimi

Yalnızca **ücretsiz, anahtarsız ve kotasız** kaynaklar kullanılır (19 Kasım 2026 denemeleri):

| Kaynak | Durum |
|---|---|
| Pinnacle (football-data.co.uk) | Türkiye'de engelli → GitHub Actions ile yurt dışından çekilir |
| Smarkets borsası (açık API) | Türkiye'den erişilemiyor → GitHub Actions ile yurt dışından çekilir |
| Betfair, Matchbook, Pinnacle'ın kendi akışı | Hesap / anahtar gerektiriyor |
| The Odds API vb. | Anahtar ve kota gerektiriyor (kullanılmıyor) |
| Sofascore / Flashscore / OddsPortal | Kullanım koşulları otomatik toplamayı yasaklıyor (kullanılmıyor) |
| ESPN (DraftKings) | Yerelde erişilebilir; yedek |

GitHub Actions gizli depolarda aylık 2.000 dakika ücretsiz; bu iş çalışma başına ~1 dakika,
günde 5 çalışma → ayda ~150 dakika. Engelli kaynaklara yurt dışından erişme kararı kullanıcınındır.
