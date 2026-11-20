# Nesine bülteni — global referans fiyatına göre analiz

```bash
python scripts/nesine_global.py --date 2026-11-19
```

Çıktı: `tahminler/<yapay zekâ>/<tarih>/nesine_global.md` ve `.json` (`QUANTFOOT_AI`, Claude için `claudetahmin`).
Yalnız kullanıcı istediğinde çalıştırılır (20 Kasım: zamanlanmış görev yok); ayrıntı: [../AGENTS.md](../AGENTS.md).

## Nasıl çalışır

1. **Nesine bülteni** sitenin kendi kullandığı herkese açık JSON akışından çekilir
   (`quantfoot.data.nesine`). Pazar kodları (MTID) Nesine'nin kendi tanım tablosuyla çözülür
   (`src/quantfoot/data/nesine_markets.json`, sitenin `CCAll.min.js` dosyasından; 599 pazar) —
   tahmin edilmez.
2. **Global referans fiyat** — maç başına en iyisi seçilir (3 katmanlı güven sınıflandırması):
   1. **Pinnacle** (football-data.co.uk fikstür dosyaları, 1X2 + O/U 2.5 + Asya Handikap `AHh/PAHH/PAHA`) — *keskin*
   2. **Smarkets / Matchbook borsası** — alış/satış ortası; alış-satış farkı 4 puandan geniş (likit olmayan)
      pazarlar referans sayılmaz. Bir maç hem Smarkets'te hem Matchbook'ta likitse iki borsanın marjsız
      olasılıkları ortalanır ("Matchbook + Smarkets"); fark `consensus_gap` olarak kaydedilir — *keskin*
   3. **Betfair borsası** (football-data.co.uk `BFE*`) ve **OddsMath (`BetInAsia/Pinnacle`, `Borsa`)** —
      Türkiye'den doğrudan erişilebilir; açılıştan canlıya sharp olasılık kayması (`steam_1x2`) ve
      doğrudan doğrulanmış O/U 1.5 / 2.5 / 3.5 çizgileri dahil — *keskin*
   4. **Global Büro (Orta Güven):** **OddsMath (`Marathonbet / 1XBET / Bet365`)** ve **ESPN (DraftKings)** —
      küçük/egzotik ligler için Nesine'den bağımsız global fiyat ve skor dağılımı üretir (`price_tier = "global_buro"`).
      OddsMath orta güven maçları, **her iki takımın da canlı araştırması (ESPN/Transfermarkt) varsa, risk/steam
      uyarısı yoksa ve olasılık ≥ %62 ise** `+2` puan ek belirsizlik payıyla (`sigma += 0.020`) kupona aday
      olabilir (`--yalniz-keskin` ile tamamen kapatılabilir).
   5. **Düşük Güven:** Hiçbir global kaynakta bulunmayan ultra-niş maçlar yalnızca bilgi amaçlı Nesine
      oranından tahmin edilir (`price_tier = "dusuk_guven"`, kupona asla girmez).

   `--no-oddsmath` / `--no-tm` ile yerel OddsMath ve Transfermarkt çekimleri istenirse kapatılabilir.
   **Eşleştirme güvenliği:** maç adı (yaygın kısaltma sözlüğü dahil) + başlama saati (±3 saat) benzerliğiyle
   eşlenir; kadın/erkek ve genç/rezerv/A-takım ayrımı kesin olarak korunur. Her global fiyat en çok benzeyen
   tek Nesine maçına aittir ve Nesine'nin kendi 1X2'si (marjsız) referanstan 15 puandan fazla ayrışırsa
   eşleşme reddedilir. İki borsa 1X2'de 8 puandan fazla ayrışırsa maç fiyatlanmaz.
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
kupona alınmaz. Kupon ayrıca 3 saatten eski global fiyatı hiç kullanmaz. Bunu kısaltmak için
bilgisayar, Nesine'de fiyatlı bir maç 40–100 dakika sonra başlayacaksa `gh workflow run` ile yalnız
önümüzdeki 2 saatin maçlarını yeniletir (kadro saati, en çok 50 dakikada bir). Depo herkese açık olduğu
için Actions dakikası sınırsız ve ücretsiz. Kapsam: ESPN'in yayınladığı ligler (Brezilya, Uruguay, MLS, Avrupa ligleri, kadın
Şampiyonlar Ligi…); küçük liglerde veri yok.

Denenip alınmayanlar: Polymarket ve Kalshi (erişilebilir, ama futbolda neredeyse yalnız uzun vadeli
pazarlar), ClubElo (sunucu yurt dışından da 502 veriyor).

## Borsa hareket etti, Nesine güncellemedi

Her analiz çalıştırması doğrudan borsa fiyatlı seçimlerin (Nesine oranı, borsa olasılığı) bir kaydını
`tahminler/<yapay zekâ>/<tarih>/nesine_history.jsonl` dosyasına ekler (git'e girmez). Raporun ilk bölümü, son 8
saatte borsa olasılığı **en az 3 puan artan** ama Nesine'nin **aynı oranı** vermeye devam ettiği seçimleri
listeler: haber ya da kadro sonrası geç kalan oran. Saatlik `QuantFoot\Analiz` görevi bu kaydı biriktirir.

## Tetikleme (istek üzerine)

Global çekim yalnız istek üzerine çalışır: analizden önce `gh workflow run global-odds.yml` (bitince `git pull`);
`gh` çalışmazsa `data/global_odds/trigger.txt` dosyasını göndermek de iş akışını tetikler. Kupon 3 saatten eski
global fiyatı kullanmaz. Aynı anda biten iki çalıştırma JSON dosyalarını satır satır birleştirmez:
geç kalan, en yeni veriyi alıp kendi sonucunu onun üzerine yeniden kurar. Raporların başında verinin yaşı yazar.

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

Her analiz, başlamamış her maçın son tahminini `tahminler/<yapay zekâ>/<tarih>/takip_kayit.json` dosyasına yazar
(tüm seçimler: global olasılık, Nesine oranı, doğrudan/model). Dünü istek üzerine sonuçlandırmak için:

```bash
python scripts/nesine_takip.py sonuc --date 2026-11-19   # ESPN'den İY ve 90' skor, her seçim tuttu/tutmadı
python scripts/nesine_takip.py rapor                      # tahminler/<yapay zekâ>/takip/ozet.md
python scripts/gun_degerlendirme.py --tarih 2026-11-19     # bütün yapay zekâlar → ortak degerlendirme/<gün>.md
```

Rapor: olasılık bandına göre tahmin vs gerçekleşen (kalibrasyon), Brier skoru, doğrudan fiyat vs model,
bahis ailesine göre, maç başına en güvenilir tercih ve üretilen her kuponun sonucu. ESPN'de olmayan
maçlar sonuçlanamaz.

## Sistem durumu ve uyarı

Zamanlanmış görevler kapalıyken (20 Kasım) durum dosyası yazılmaz; analiz raporunun başında global verinin
yaşı yazar, kupon 3 saatten eski fiyatı kullanmaz.

## İlk 11 saati

`QuantFoot\Kadro10` ve `QuantFoot\Kadro30` görevleri her saatin 10. ve 30. dakikasında bugünü yeniden
analiz eder (saatlik `Analiz` :50'de): kadrolar maçtan ~1 saat önce açıklandığında eksik kilit oyuncu ve
geç kalan fiyat 20 dakika içinde rapora ve kupon filtresine yansır.

## Yeni bahis aileleri (19 Kasım)

1. Yarı Çifte Şans; ev / deplasman 1. yarı gol Alt/Üst; herhangi bir yarıyı kazanır; deplasman her iki
yarıyı kazanır; takımın en çok gol attığı yarı; kaç farkla kazanır; 1. yarı / 2. yarı KG'nin dört sonucu;
İlk Yarı / Maç Skoru. Hepsi aynı ortak gol dağılımından; tutarlılık testleri `tests/test_full_markets.py`.
**Korner** Alt/Üst (maç ve 1. yarı) yalnızca borsanın kendi korner fiyatı olan maçlarda fiyatlanır.

## Maç dosyası (her bahis ailesi, en garantiden aşağıya + skorlar)

```bash
python scripts/mac_dosyasi.py --mac "Vasco"          # tek maç
python scripts/mac_dosyasi.py --tarih 2026-11-21     # günün tüm başlamamış maçları
```

Her maç için: araştırma (form, son maçlar, puan durumu, golcüler, asistler, kaleci, kartlar, takım
istatistikleri, sakat/cezalı, kadroda olmayanlar, haberler), **tüm bahis ailelerinin her sonucu yüzdesiyle**
(maç sonucu, çifte şans, tüm Alt/Üst çizgileri, KG, İY/2Y sonuç-Alt/Üst-KG, İY/MS, kaç farkla, handikap,
takım golleri, yarı bahisleri, kombineler, ilk gol) en yüksekten düşüğe sıralı; kaynağı (doğrudan borsa /
model) ve Nesine'de varsa oranı; maç sonu, ilk yarı ve İY/MS skor olasılıkları. Çıktı:
`tahminler/<yapay zekâ>/<tarih>/mac_dosyalari/<kod>.md`.

## Haftalık analiz

```bash
python scripts/nesine_global.py --date 2026-11-19 --hafta 7 --haftalik   # yalnız kullanıcı isterse
```

Her bahis günü (07:00–07:00 TSİ) için ayrı rapor + `tahminler/<yapay zekâ>/hafta/<başlangıç>_nesine_hafta.md` özeti
(gün başına kapsam ve haftanın Nesine'nin global adil fiyatın üstünde ödediği seçimleri). Global çekim
1X2 ve Alt/Üst için 7 gün, türev pazarlar için 48 saat ileriye bakar; maç öncesi saatlik yenileme tüm
pazarları tazeler.

## Kupon: olasılık globalden, oran Nesine'den

**Güvenilirlik düzeltmeli seçim (19 Kasım):** her tercihin olasılığına kaynağına göre bir belirsizlik payı
(σ) verilir; seçim, olasılığın %90 alt sınırına (p − 1,28σ) göre yapılır. σ: doğrudan borsa fiyatı 1 puan,
gol modeli 2,5 puan, yarı pazarları (İY/2Y, en çok gol olan yarı…) 3,5 puan; tek borsa +0,5, araştırma yok
+1, kadro/haber uyarısı +2 puan. Böylece "en garanti" tercih, en yüksek olasılık değil, en kötü ihtimalle
bile en yüksek kalan olasılıktır. Rapor hem olasılığı hem güvenilir alt sınırı gösterir.

**Hedef = en az oran (kullanıcı kuralı 20 Kasım):** "5 oranlık" en az 5 demektir; 6–7 olabilir, 5'in altı asla.
Optimizasyon zaten Π oran ≥ hedef koşuluyla tutma olasılığını en yükseğe çıkarır. Canlı oranla yeniden okunduğunda
hedefin altına düşen kupon en çok 3 denemede güncel oranlarla yeniden kurulur, yine altındaysa hiç verilmez;
`kupon_kontrol.md` her kuponun canlı toplam oranını bilgi için gösterir; verilen kupon sonradan yeniden kurulmaz ve bunun için uyarı gönderilmez (kullanıcı kararı 20 Kasım).

**Kuponların yeri (20 Kasım):** Claude'un kuponları yalnız `tahminler/claudetahmin/<tarih>/` altına yazılır
(yapay zekâ yarışması, [tahminler/README.md](../tahminler/README.md)); 19 Kasım ve öncesi `reports/daily/` altında kalır.

**Kuponlar arası tutarlılık (varsayılan, kullanıcı kuralı 20 Kasım):** kuponlar aynı maçı paylaşabilir ama aynı bahsi ve
birbirini kesin yatıran bahisleri (hiçbir İY/MS skorunda ikisinin birden tutmadığı çiftler, ör. "Çifte şans
1-2" ile "İY 0-0 / MS 0-0") alamaz (`compatible()`, `drop_conflicts()`).

Örn. `--adet 10`: 1. kuponda "MS 1" seçilen maç, 2. kuponda uygunsa "2,5 Üst" ya da "KG Var" ile yer alabilir, "MS 1"
ile asla. Bu kural aynı günün öteki hedefli kuponlarındaki (son dosya) tercihleri de kapsar. Eski "her maç tek kupon"
davranışı: `--ayri-mac`. İsteğe bağlı `--max-ortak N`: öteki hedefin ana kuponuyla en çok N maç paylaşılır.

**Oran okuma (20 Kasım):** Nesine bülteni aynı seçime dakikalar içinde iki fiyat verebiliyor (bir seçimde
1.65 / 1.71 okundu). Kupon, bülten iki kez okunup **düşük** oran esas alınarak kurulur (`read_bulletin_odds`,
`apply_live_odds`), kurulduktan sonra yine iki okumayla kontrol edilir; bir kupon hedefin altına düşerse güncel
oranlarla bir kez yeniden kurulur.

**Maç öncesi kontrol ve CLV (20 Kasım, istek üzerine):** ilk 11'ler açıklandıktan sonra yeni bir analizin
ardından `scripts/kupon_kontrol.py kontrol` günün bütün kupon bacaklarını yeni analizle ve canlı oranlarla karşılaştırır:
olasılık %55 altı ya da 5+ puan düşüş, askıya alınan seçim, 1,20 altı oran, sonradan açıklanan önemli eksik ve
risk/steam uyarısı → `tahminler/<yapay zekâ>/<tarih>/kupon_kontrol.md` (+ isteğe bağlı Windows/Telegram uyarısı).
Aynı adım başlama öncesi son global olasılığı (kapanış) `kupon_clv.json`'a yazar; CLV = kapanış − kupon anı.
`kupon_kontrol.py ozet` bütün günleri `tahminler/<yapay zekâ>/clv.md`'de toplar.


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

- `--yontem optimum` (varsayılan, 19 Kasım kararı): hedefe ulaşanlar arasında kuponun tamamının tutma
  olasılığı en yüksek kupon (kesin DP); en çok 7 maç, her bacak ≥ %55 ve ≥ 1.20. `--yontem guvenli`: her maçın
  en olası seçimi, %100'e en yakından başlanarak hedefe kadar eklenir.
  19 Kasım, hedef 20: guvenli 20 maç, her biri %70–80, birleşik **%0.2**; optimum 3 maç **%4.1**.
  Her bacak tek başına güvenli görünse de 20 tane %72'lik bacağın birlikte tutma şansı %0.2'dir.
- `--dogrudan`: yalnızca doğrudan global fiyatı olan bacaklar (model türevi hiç kullanılmaz).

Çıktı: `tahminler/<yapay zekâ>/<tarih>/kupon_<hedef>x_<SSDD>.md` ve `.json` (yalnız o yapay zekânın bilgisayarında).

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
