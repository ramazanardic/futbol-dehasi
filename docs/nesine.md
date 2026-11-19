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
   1. **Pinnacle** (football-data.co.uk fikstür dosyaları, varsa)
   2. **Smarkets borsası** — alış/satış ortası; alış-satış farkı 4 puandan geniş (likit olmayan)
      pazarlar referans sayılmaz
   2b. **Matchbook borsası** — herkese açık fiyat akışı (hesap gerekmez), aynı 4 puan likidite
      kuralı. Bir maç hem Smarkets'te hem Matchbook'ta likitse iki borsanın marjsız olasılıkları
      ortalanır ("Matchbook + Smarkets"); aradaki en büyük fark `consensus_gap` olarak kaydedilir.
   3. **Betfair borsası** (football-data.co.uk dosyalarındaki BFE sütunları)
   4. **ESPN** (DraftKings) — yerelde çekilir, en zayıf referans

   1–3 Türkiye'den erişilemediği için GitHub'ın yurt dışındaki sunucularında (GitHub Actions,
   `.github/workflows/global-odds.yml`) günde 5 kez çekilip `data/global_odds/latest/` altına
   yazılır; sabah görevi önce `git pull` yapar. Hiçbir referansı olmayan maç **fiyatlanmaz**;
   adil fiyat asla Nesine'nin kendi oranından türetilmez.
   **Eşleştirme güvenliği:** maç adı + başlama saati (±3 saat) benzerliğiyle eşlenir; her global fiyat
   en çok benzeyen tek Nesine maçına aittir ve Nesine'nin kendi 1X2'si (marjsız) referanstan 15 puandan
   fazla ayrışırsa eşleşme reddedilir (19 Kasım: Al Salt – Al Yarmouk, Katar'daki Al-Ahli – Al-Shamal'a
   bağlanmıştı). İki borsa 1X2'de 8 puandan fazla ayrışırsa maç fiyatlanmaz, Alt/Üst'te ayrışırsa
   Alt/Üst kullanılmaz.
3. Referans 1X2 (+ varsa Alt/Üst) marjdan arındırılır (power yöntemi), gol beklentileri hiçbir
   model önseli olmadan (fund_weight = 0) bu fiyata uydurulur ve Nesine'nin her seçimi — İY/MS,
   KG, gol aralığı, handikap, kombineler, ilk gol — tek tutarlı gol dağılımından fiyatlanır
   ([markets.md](markets.md)). Kulüp gol rejimi bu kullanım için yeniden kalibre edildi
   ([research/experiments_2026_11.md](research/experiments_2026_11.md) §4–5).
   **Doğrudan fiyat önceliği:** Smarkets bir seçimin kendisini de fiyatlıyorsa (KG, 0,5–6,5 tüm
   Alt/Üst çizgileri, İY sonucu, İY/MS, İY Alt/Üst, Tek/Çift, 0-1 / 2-3 gol aralığı, MS & KG,
   MS & Alt/Üst, KG & Alt/Üst) olasılık modelden değil o borsa fiyatından alınır; yalnızca tüm
   sonuçları kote edilmiş ve alış-satış farkı ≤ 4 puan olan defterler kullanılır. Raporda/kuponda
   bu bacaklar "doğrudan", diğerleri "model" olarak işaretlenir. 19 Kasım: 1.622 seçimin 577'si
   doğrudan; model ile doğrudan fiyat arasındaki ortalama fark 0,6 puan (384 seçim), en büyük
   fark 7 puan (Amiens 1,5 Üst).
4. **EV = global adil olasılık × Nesine oranı − 1.** EV'si +%25'i aşan seçimler öneri listesine
   alınmaz, "referans hatası şüphesi" tablosunda ayrıca gösterilir.
   Kalibre edilmemiş yarışmalarda (kadın
   futbolu) yalnızca doğrudan referansı olan pazarlar (1X2, aynı çizgideki Alt/Üst) fiyatlanır.

## Maç araştırması (ESPN)

Her fiyatlanan maç için ESPN'in ücretsiz, anahtarsız sitesinden (`quantfoot.data.match_research`):
son 5 maç formu, dinlenme günü, aralarındaki son 5 maç, puan durumu ve tablo baskısı (yalnız yerel
liglerde: zirve yarışı / orta / küme hattı), haber başlıkları ve ilk 11 (maçtan ~1 saat önce).
İlk 11 açıklandığında son 5 maçın ≥ 4'ünde ilk 11'de olup bugün olmayan oyuncular, kaleci ve gol
kralı ayrıca işaretlenir.

**Premier Lig sakat / cezalı listesi:** resmî Fantasy Premier League akışından (ücretsiz, anahtarsız):
sakat, cezalı, şüpheli oyuncular, oynama ihtimali (%) ve haber notu; düzenli ilk 11 oyuncuları "kilit"
olarak işaretlenir. ESPN'in futbol sakatlık alanları boş geldiği için diğer liglerde ilk 11 karşılaştırması
kullanılır. Transfermarkt kullanım koşulları otomatik veri toplamayı yasakladığı için kullanılmaz.

Olasılık yine global fiyattan gelir (piyasa bu haberleri dakikalar içinde fiyatlar). Araştırmanın
işi **eski fiyat koruması**dır: önemli bir eksik varsa ve global fiyat 75 dakikadan eskiyse maç
kupona alınmaz. Bunu kısaltmak için Actions saatte bir (12:40–06:40 TSİ) yalnız önümüzdeki 3 saatte
başlayacak maçları yeniler (~1 dk; tam çekim günde 5 kez, ~5 dk; toplam ayda ~1.200 dk, ücretsiz
kota 2.000 dk). Kapsam: ESPN'in yayınladığı ligler (Brezilya, Uruguay, MLS, Avrupa ligleri, kadın
Şampiyonlar Ligi…); küçük liglerde veri yok.

Denenip alınmayanlar: Polymarket ve Kalshi (erişilebilir, ama futbolda neredeyse yalnız uzun vadeli
pazarlar), ClubElo (sunucu yurt dışından da 502 veriyor).

## Borsa hareket etti, Nesine güncellemedi

Her analiz çalıştırması doğrudan borsa fiyatlı seçimlerin (Nesine oranı, borsa olasılığı) bir kaydını
`reports/daily/<tarih>/nesine_history.jsonl` dosyasına ekler (git'e girmez). Raporun ilk bölümü, son 8
saatte borsa olasılığı **en az 3 puan artan** ama Nesine'nin **aynı oranı** vermeye devam ettiği seçimleri
listeler: haber ya da kadro sonrası geç kalan oran. Saatlik `QuantFoot\Analiz` görevi bu kaydı biriktirir.

## Yedek tetikleyici (GitHub zamanlayıcısı atlarsa)

GitHub'ın ücretsiz zamanlayıcısı "en iyi çaba" ile çalışır; 19 Kasım'da hiçbir zamanlanmış çalışma başlamadı.
Saatlik yerel görev (`scheduled.py analiz`) global verinin yaşına bakar: 5 saatten eskiyse
`data/global_odds/trigger.txt` dosyasını güncelleyip normal bir `git push` yapar; iş akışı bu dosyaya
gelen gönderimle hemen çalışır. En fazla 3 saatte bir tetikler. Raporların başında verinin yaşı yazar.

## Sizin sağladığınız sakatlık / ceza dosyası

`reports/haftalik_sakatlik_ceza_*.json` (en yenisi) varsa takım dosyalarına Nesine maç koduyla eklenir:
sakatlar, cezalılar, eksik kaleci ve uyarılar; kupon gerekçelerinde de sayıları görünür. Sistem bu veriyi
kendisi çekmez (kaynağın koşulları otomatik çekimi yasaklıyor); yalnızca klasöre konan dosyayı okur.
Dosya git'e girmez.

## Global fiyatı olmayan maçlar: düşük güven tahmini

Hiçbir keskin kaynağın fiyatlamadığı maçlar (alt ligler, gençlik ligleri…) için olasılıklar Nesine'nin
kendi 1X2 (+ 2,5 Alt/Üst) oranlarından marj arındırılarak hesaplanır ve **"düşük güven"** olarak
işaretlenir. Bu tahminler yalnızca analiz içindir: **kupona hiçbir zaman girmez** (`candidates()` yalnız
global fiyatlı maçları kabul eder). Sonuç takibinde ayrı izlenir (kaynak alanı "Nesine").

## Sonuç takibi (tahminler gerçekten doğru mu?)

Her analiz, başlamamış her maçın son tahminini `reports/daily/<tarih>/takip_kayit.json` dosyasına yazar
(tüm seçimler: global olasılık, Nesine oranı, doğrudan/model). Sabah görevi dünü sonuçlandırır:

```bash
python scripts/nesine_takip.py sonuc --date 2026-11-19   # ESPN'den İY ve 90' skor, her seçim tuttu/tutmadı
python scripts/nesine_takip.py rapor                      # reports/takip/ozet.md
```

Rapor: olasılık bandına göre tahmin vs gerçekleşen (kalibrasyon), Brier skoru, doğrudan fiyat vs model,
bahis ailesine göre, maç başına en güvenilir tercih ve üretilen her kuponun sonucu. ESPN'de olmayan
maçlar sonuçlanamaz.

## Sistem durumu ve uyarı

Her saatlik / kadro çalışması `reports/DURUM.md` yazar (global veri yaşı, son yedek tetikleme). Veri 8
saatten eskiyse bilgisayarda Windows uyarı penceresi açılır.

## İlk 11 saati

`QuantFoot\Kadro10` ve `QuantFoot\Kadro30` görevleri her saatin 10. ve 30. dakikasında bugünü yeniden
analiz eder (saatlik `Analiz` :50'de): kadrolar maçtan ~1 saat önce açıklandığında eksik kilit oyuncu ve
geç kalan fiyat 20 dakika içinde rapora ve kupon filtresine yansır.

## Yeni bahis aileleri (19 Kasım)

1. Yarı Çifte Şans; ev / deplasman 1. yarı gol Alt/Üst; herhangi bir yarıyı kazanır; deplasman her iki
yarıyı kazanır; takımın en çok gol attığı yarı; kaç farkla kazanır; 1. yarı / 2. yarı KG'nin dört sonucu;
İlk Yarı / Maç Skoru. Hepsi aynı ortak gol dağılımından; tutarlılık testleri `tests/test_full_markets.py`.
**Korner** Alt/Üst (maç ve 1. yarı) yalnızca borsanın kendi korner fiyatı olan maçlarda fiyatlanır.

## Haftalık analiz

```bash
python scripts/nesine_global.py --date 2026-11-19 --hafta 7
```

Her bahis günü (07:00–07:00 TSİ) için ayrı rapor + `reports/weekly/<başlangıç>_nesine_hafta.md` özeti
(gün başına kapsam ve haftanın Nesine'nin global adil fiyatın üstünde ödediği seçimleri). Global çekim
1X2 ve Alt/Üst için 7 gün, türev pazarlar için 48 saat ileriye bakar; maç öncesi saatlik yenileme tüm
pazarları tazeler.

## Kupon: olasılık globalden, oran Nesine'den

```bash
python scripts/nesine_kupon.py --hedef 10                                   # matematiksel en iyi
python scripts/nesine_kupon.py --hedef 10 --min-mac 4 --min-olasilik 0.55  # kombine
```

- Her bacağın tutma olasılığı **yalnızca keskin referanstan** (Pinnacle / Smarkets / Betfair) gelir;
  ESPN referanslı maçlar `--espn` verilmedikçe kullanılmaz.
- Hedef **Nesine oranlarının çarpımıdır**: "10 oranlık kupon" Nesine'de oynandığında 10'un üstündedir.
  Global orana göre kurulup Nesine'de 4'e düşen kupon sorunu böylece ortadan kalkar.
- Hedefe ulaşan kuponlar arasında global birleşik olasılığı en yüksek olan, kesin bir dinamik
  programlamayla seçilir (kaba kuvvetle doğrulanır, `tests/test_nesine_kupon.py`). Maç başına tek seçim,
  Nesine MBS kuralı, başlamış maçlar hariç. `--adet` maçları ayrı alternatif kuponlar verir.
- **Önemli:** her ek maç Nesine marjını (~%20) yeniden ekler. Bu yüzden aynı hedef için az maçlı kupon
  çoğu zaman daha olasıdır (19 Kasım, hedef 10: tek bacak %8.1, 6 bacaklı kombine %4.6).
  `--min-mac` kombine ister, ama bunun bedeli tutma olasılığıdır.

- `--yontem guvenli` (varsayılan): her maçın en olası seçimi, %100'e en yakından başlanarak hedefe kadar
  eklenir. `--yontem optimum`: hedefe ulaşanlar arasında birleşik olasılığı en yüksek kupon (kesin DP).
  19 Kasım, hedef 20: guvenli 20 maç, her biri %70–80, birleşik **%0.2**; optimum 3 maç **%4.1**.
  Her bacak tek başına güvenli görünse de 20 tane %72'lik bacağın birlikte tutma şansı %0.2'dir.
- `--dogrudan`: yalnızca doğrudan global fiyatı olan bacaklar (model türevi hiç kullanılmaz).

Çıktı: `reports/daily/<tarih>/kupon_<hedef>x_<SSDD>.md` ve `.json`.

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
