# QuantFoot boşluk analizi — "para kaybetmemek, kazanmak" hedefine göre (21 Kasım 2026)

Hazırlayan: Grok Bot (`grokbot/tam-analiz` dalı). Kullanıcının hedefi (21 Kasım): Nesine yalnız bahis yapılan yer;
her maç oran dışında da en güvenilir kaynaklardan baştan sona incelenecek; sistemde bu hedefe engel olan her şey
düzeltilecek. Bu belgedeki her sayı ya bu depodaki verilerle yeniden üretilebilir bir betikten ya da bugün bu
bilgisayardan yapılmış bir erişim denemesinden gelir; yoksa "ölçülmedi" yazılır.

İlgili çıktılar: [kombine_dogrulama_2026_11_21.md](kombine_dogrulama_2026_11_21.md),
[devig_karsilastirma_2026_11_21.md](devig_karsilastirma_2026_11_21.md), önceki deneyler
[experiments_2026_11.md](experiments_2026_11.md), literatür [literature_review_2026_11.md](literature_review_2026_11.md).

---

## 0. Özet (önce en önemlisi)

1. **Para, modelde değil kupon yapısında kaybediliyor.** Kullanıcının Nesine geçmişinde (13–21 Kasım, 30 kupon,
   168 bacak) kupon başı ortalama 5.6 bacak var (en çok 10); 122 maçın 32'si birden çok kupona girmiş
   (Molde–Bodø/Glimt 5 kupona). Keskin global olasılığı bulunabilen 40 maç-öncesi bacağın Nesine oranına göre
   ortalama EV'si **%−16.4**, hiçbirinin EV'si pozitif değil. 5–6 bacakta bu, kupon başına beklenen kaybı
   çok büyütür (bkz. §3, deney A: gerçek sonuçlarla bacak sayısı arttıkça ROI düşüyor).
2. **Temel (fundamental) modeller piyasaya bilgi katmıyor** (önceki deney: 16.423 maçta 15 modelin hepsi için
   havuz ağırlığı 0.00). Dixon-Coles / bivariate Poisson / Weibull / durum-uzay modellerinin hepsi depoda zaten
   var; daha fazla model çeşidi kâr getirmez.
3. **Kanıtlanmış tek avantaj kaynağı keskin–yumuşak fiyat farkı** (tipsaudit, EV ≥ %2.5: ROI +%7.6, GA +2.5 – +12.8).
   Bunun için iki şart var: keskin referans **taze** olmalı ve kupona **yalnız EV > 0 bacaklar** girmeli.
4. Bugün bu bilgisayardan erişilebilen **iki yeni ücretsiz keskin kaynak** bulundu: API-Football `/odds`
   (Pinnacle dahil 10 büro, maç başına 1 istek) ve football-data.co.uk `fixtures.csv` (Betfair Borsası + 6 büro,
   büyük ligler). Önceki belgede "football-data erişime engelli" yazıyordu; bugün 200 döndü.

---

## 1. Literatür → depo eşlemesi

| Konu | Literatürdeki en iyi uygulama | Depoda | Durum |
|---|---|---|---|
| Gol modeli | Dixon & Coles (1997) + zaman ağırlığı; Maher (1982) | `models/dixon_coles.py`, `scripts/dc_model.py` (penaltyblog) | Var |
| Skor bağımlılığı | Bivariate / diagonal-inflated Poisson (Karlis & Ntzoufras 2003) | `models/bivariate_poisson.py` | Var |
| Aşırı/eksik dağılım | Weibull sayım + kopula (Boshnakov, Kharrat & McHale 2017); COM-Poisson | `models/weibull_copula.py`, `markets/tail_goals.py` | Var |
| Gol farkı | Skellam (Karlis & Ntzoufras 2009) | Skor matrisinden türetiliyor (`markets/pricing.py`) | Dolaylı var |
| Dinamik güç | Durum-uzay / skor güdümlü (Koopman & Lit 2015; Duffield 2024) | `models/kalman.py`, `models/gas_poisson.py` | Var |
| Reytingler | Elo (Hvattum & Arntzen 2010), Pi-ratings (Constantinou & Fenton 2013), Berrar ve ark. (2019) reyting özellikleri + gradyan artırma | `models/ratings.py`, `models/pyramid.py`, `models/glicko2.py`, `models/ensemble.py` | Var |
| xG tabanlı güç | Şut bazlı xG (Understat/FBref/Opta tipi) | `data/xg_proxy.py` (yalnız vekil: şut/isabetli şut) | **Eksik: gerçek xG yok** |
| Kadro / sakatlık | Oyuncu puanı, plus-minus (Kharrat ve ark. 2017); karışık kanıt (Peters & Pacheco 2022) | `data/absences.py` (Transfermarkt — buradan erişilemiyor), `data/match_research.py` (ESPN tahmini eksik) | **Kısmi** → bugün API-Football sakat/cezalı eklendi |
| Dinlenme / yoğunluk / seyahat | Julian ve ark. 2021 meta-analiz | ESPN lig dinlenmesi; arşiv deneyi (kupa maçları eksik) | **Kısmi** → bütün turnuvalar API-Football'dan (birikerek) |
| Hava | Yağış/rüzgâr gol ve tempo etkisi | `data/weather.py` (lig ülkesi koordinatı) | Kısmi → stat şehri koordinatı eklendi |
| Hakem | Kart/faul eğilimi | Yok | **Eksik** → İngiltere/İskoçya için eklendi |
| Motivasyon | Puan durumu, ölü maç, kupa | `match_research.motivation`, `coupon_builder.is_cup_competition` | Kısmi → puan bayrakları eklendi |
| Piyasa modelleri | Kapanış en iyi tahmin; keskin vs yumuşak; steam | `scripts/nesine_global.py` (keskin referans, steam bayrağı), `evaluation/market_benchmark.py` | Var ama **referans bayat kalabiliyor** (11 saat) |
| Marj temizleme | Shin (Štrumbelj 2014), power, odds-ratio | `markets/devig.py` (power) | Var — bugün 7 yöntemle karşılaştırıldı, power en iyi/eşit (§4) |
| Kalibrasyon | İzotonik / beta (Kull ve ark. 2017) / sıcaklık (Guo ve ark. 2017); doğruluk değil kalibrasyonla seçim (Walsh & Joshi 2023) | `evaluation/auto_learn.py`, `evaluation/metrics.py` | Var; pazar bazında **ayrı işçi** (`grokbot/pazar-kalibrasyonu`) |
| Topluluk | Stacking (Wolpert 1992) | `models/ensemble.py` | Var (piyasaya ağırlık 0) |
| Başarı ölçüsü | CLV (Kaunitz ve ark. 2017) | `tipsaudit.csv` CLV, `scripts/nesine_takip.py` | **Nesine bahisleri için sistematik CLV yok** |
| Pay | Kesirli Kelly, parametre belirsizliği (Baker & McHale 2013), korelasyonlu Kelly | `strategy/kelly.py` | Var ama **kupona uygulanmıyordu** → eklendi |
| Kombine / aynı maç | Marj bileşikleşmesi; aynı maç bacakları ortak dağılımla fiyatlanmalı | `markets/bet_builder.py`; `nesine_kupon.py` 7–8 bacak hedefli | **Politika eksik** → eklendi |

---

## 2. Boşluklar — beklenen kâr etkisine göre sıralı (ilk 10)

| # | Boşluk | Neden kâr etkisi büyük | Kanıt | Durum |
|---|---|---|---|---|
| 1 | **Kombine politikası yok**: uzun kupon, EV'siz dolgu bacak, aynı maçın birçok kupona girmesi, kupon payı kuralı yok | Her negatif-EV bacak kupon EV'sini çarpımsal düşürür; aynı maç birden çok kuponu birlikte yakar | Kullanıcı verisi (§0); deney A (§3) | **Yapıldı**: `strategy/accumulator_policy.py`, `scripts/kupon_politikasi.py` (henüz `nesine_kupon.py`'ye bağlanmadı) |
| 2 | **Keskin referans tazeliği / kapsamı** | Avantajın tek kanıtlı kaynağı keskin fiyat; bayat referansla EV yanlış | 21 Kasım: referans 11 saat eski; kupon kuralı 3 saat | Yeni kaynaklar bulundu (API-Football Pinnacle, football-data Betfair Borsası); `nesine_global` entegrasyonu **sonraki adım** |
| 3 | **Nesine bahisleri için CLV defteri yok** | Kazanan/kaybeden kupon gürültü; kapanışı yenmek gerçek ölçü | Kaunitz ve ark. 2017; tipsaudit | Maç dosyası her fikstür için oran anlık görüntüsü kaydetmeye başladı; Nesine oranıyla CLV **sonraki adım** |
| 4 | **Türev pazarlarda Nesine marjı (~%20)** | Üst/KG/İY pazarlarında EV genelde çok negatif | `nesine_kupon.py` notu; kullanıcı bacakları | Pazar kalibrasyonu + EV-temelli seçim **ayrı işçide** |
| 5 | **Kadro / sakatlık bilgisi yapılandırılmış değil** | Haber fiyata girmeden önce davranmak tek "bilgi" avantajı olabilir | Peters & Pacheco 2022 (karışık) | **Yapıldı** (bilgi katmanı): API-Football sakat/cezalı + ilk 11 (maçtan ≤75 dk önce), ESPN eksik tahmini ile çapraz kontrol. Olasılığa etkisi **doğrulanmadı** |
| 6 | **Gerçek xG yok** | xG gelecek golü geleneksel istatistikten iyi öngörür (Mead ve ark. 2023) | — | FBref 403 (Cloudflare), Understat veri ucu HTML döndürüyor; API-Football maç istatistiğinde `expected_goals` var (maç başına 1 istek, ücretsiz kota dar) |
| 7 | **Bütün turnuvaları kapsayan dinlenme/yoğunluk** | Avrupa/kupa maçı sonrası rotasyon | Önceki deney: lig-içi dinlenme etkisi ihmal edilebilir (+0.00009/maç) | **Yapıldı** (bilgi katmanı). Ücretsiz plan yalnız dün/bugün/yarın'ı verdiği için geçmiş her gün birikerek oluşur; yeterli veri birikince tekrar test edilmeli |
| 8 | **Hakem eğilimi** | Kart/faul pazarlarında doğrudan; golde dolaylı | — | **Yapıldı** (İngiltere/İskoçya, football-data). Başka ligler için kaynak yok |
| 9 | **Motivasyon / puan durumu bayrakları** | Ölü maç, küme hattı | — | **Yapıldı** (ESPN puan durumu → bayrak). Olasılığa etkisi doğrulanmadı |
| 10 | **Aynı maç (SGP) bacak korelasyonu** | Aynı maçta "MS 1 + Üst" bağımsız sayılırsa olasılık yanlış | — | Politika motoru ortak olasılık verilmedikçe aynı maçta 2 bacağı reddediyor; ortak fiyat `markets/bet_builder.py` skor matrisinden alınabilir |

Model tarafı (Dixon-Coles varyantları, Weibull, durum-uzay, Pi/Elo, LightGBM) listede yok: hepsi depoda var ve
piyasaya bilgi katmadığı ölçüldü. Bunlara emek harcamak kâr getirmez.

---

## 3. Kombine politikası — kanıt (`scripts/kombine_dogrulama.py`)

**Deney A — marj bileşikleşmesi, gerçek sonuçlar** (`data/matches.csv`, 2021-07+, 15.483 favori bacak, medyan 1X2
marjı %6.4; bacak = marjsız olasılığı ≥ %55 ve oranı ≥ 1.20 olan favori, ortalama piyasa oranından; aynı günden
rastgele k maç; gün-kümeli bootstrap %95 GA):

| Bacak | Tutma | ROI (%95 GA) |
|---|---|---|
| 1 | 64.6% | −2.6% (−4.6 – −0.4) |
| 2 | 42.5% | −2.7% (−6.2 – +1.1) |
| 3 | 27.2% | −6.0% (−11.6 – −0.3) |
| 4 | 17.4% | −7.9% (−14.8 – −0.4) |
| 5 | 10.8% | −14.1% (−23.6 – −4.5) |
| 6 | 7.0% | −15.7% (−27.7 – −3.6) |
| 7 | 4.8% | −12.2% (−28.7 – +6.3) |
| 8 | 3.1% | −17.5% (−35.7 – +2.1) |
| 9 | 2.1% | −20.3% (−40.9 – +5.5) |

"Güvenli favorileri biriktirmek" %6'lık marjda bile her bacakta kaybı büyütüyor. Nesine marjı türev pazarlarda
çok daha yüksek olduğundan gerçek kayıp daha büyüktür.

**Deney B — politika motoru** (`data/tipsaudit.csv`, 7.349 maç, olasılık = Pinnacle açılışı marjsız, oran = ~17
büronun en iyisi). EV'ye bakmadan favori biriktirmek bu veri setinde de pozitif çıktı (en iyi-büro oranı zaten
Pinnacle'ın üstünde olduğu için), dolayısıyla bu deney politikanın Nesine'deki etkisini ölçmez; yalnız EV filtreli
kuponların bu veri setinde kârlı kaldığını gösterir. En çok 2 bacak + bacak EV ≥ %2.5: 321 kupon, ROI +33.6%
(GA +8.2 – +60.2); 1 bacak: 348 tekli, ROI +8.1% (GA −5.5 – +21.8). 3–4 bacakta GA sıfırı kapsıyor.
Tam tablo: [kombine_dogrulama_2026_11_21.md](kombine_dogrulama_2026_11_21.md).

Politika motorunun kuralları (varsayılan): bacak EV ≥ 0 (dolgu yok), kupon EV ≥ %2, en çok 4 bacak, oran ≥ 1.20,
kupon oranı ≤ 60, maç başına tek bacak, aynı maç gün içinde tek kupona, çeyrek Kelly + Baker-McHale küçültmesi,
kupon başı ≤ kasanın %2'si, gün toplamı ≤ %6. Bu kurallar olasılık değiştirmez; yalnız oynama kararını verir.

---

## 4. Marj temizleme yöntemi (`scripts/devig_karsilastirma.py`)

Repo varsayılanı `power`, penaltyblog'un (MIT) 7 yöntemiyle karşılaştırıldı (eğitim yok → tamamen örneklem dışı):

| Veri | Maç | power log-loss | En iyi alternatif | Fark (GA) |
|---|---|---|---|---|
| matches.csv ortalama oran | 20.000 | 0.99844 | additive / DMW 0.99843 | −0.00001 (−0.00011 – +0.00008) |
| Pinnacle kapanış | 7.349 | 0.99798 | additive / DMW 0.99802 | +0.00003 (−0.00013 – +0.00018) |
| Pinnacle açılış | 7.350 | 1.00162 | additive / DMW 1.00168 | +0.00007 (−0.00011 – +0.00022) |

Multiplicative (oranları oranlayarak bölmek) ortalama oranda anlamlı biçimde kötü (+0.00089, GA +0.00047 –
+0.00132). **Karar: `power` kalıyor, değişiklik yok.**

---

## 5. Veri kaynakları — bu bilgisayardan erişim (21 Kasım 2026, her biri 1 deneme)

| Kaynak | Uç nokta | Sonuç | Kullanılabilir veri |
|---|---|---|---|
| API-Football (ücretsiz) | `/fixtures?date=` | ✅ (yalnız dün/bugün/yarın; diğer günler "plan" hatası) | Bütün turnuvalar, hakem, stat, şehir |
| API-Football | `/injuries?fixture=` | ✅ | Sakat/cezalı/şüpheli + neden |
| API-Football | `/predictions?fixture=` | ✅ | Son 5 maç atak/savunma/gol, lig formu, karşılaşma geçmişi |
| API-Football | `/odds?fixture=` | ✅ | **Pinnacle**, Betfair, Bet365, 1xBet, Marathonbet … (10 büro) |
| API-Football | `/fixtures?id=` (biten maç) | ✅ | İlk 11, olaylar, maç istatistiği (`expected_goals` dahil) |
| API-Football | `/standings?season=2026`, `/players?season=2026` | ❌ ücretsiz plan yalnız 2022–2024 | — |
| API-Football | `last=` parametresi (`/fixtures?team=&last=`, `/headtohead`) | ❌ ücretsiz planda yok | — |
| football-data.co.uk | `mmz4281/2526/E0.csv`, `fixtures.csv` | ✅ | Sezon sonuçları + hakem (İng./İsk.), yaklaşan maçlar için Betfair Borsası + 6 büro oranı |
| Open-Meteo | forecast + geocoding | ✅ | Başlama saatinde yağış/rüzgâr/kar |
| ESPN | site.api scoreboard/summary | ✅ | Puan durumu, son 5, lig dinlenmesi, ilk 11 |
| openfootball | raw.githubusercontent `football.json` | ✅ | Fikstür/sonuç (CC0) |
| OpenLigaDB | getmatchdata | ✅ | Almanya |
| FPL | bootstrap-static | ✅ | Premier Lig oyuncu durumu/şüphe yüzdesi |
| eloratings.net | World.tsv | ✅ | Milli takım Elo |
| FotMob | `/api/data/matches`, `matchDetails`, `teams` | ✅ (resmî olmayan uç; kullanım koşulları otomatik erişimi kısıtlayabilir) | xG, ilk 11, eksikler, stat koordinatı, hakem, bütün turnuva fikstürü — **entegre edilmedi**, kullanıcı kararı |
| Understat | sayfa ✅, `getLeagueData` | ⚠️ veri ucu JSON yerine HTML döndürüyor | Kullanılamadı |
| FBref | lig sayfası | ❌ 403 (Cloudflare) | — |
| Sofascore | api.sofascore.com | ❌ 403 | — |
| Club Elo | api.clubelo.com | ❌ 500 | — |
| Transfermarkt | sakatlık sayfası | ❌ 202 boş gövde | — |

API-Football kullanımı bugün: erişim denemeleri 10 istek; maç dosyası geliştirme/deneme 26 istek (16'sı ücretsiz
planın tarih penceresi dışındaki günlerdi; plan hatası artık önbelleğe alınmıyor ve pencere dışı günler istek
harcamadan atlanıyor). Toplam yaklaşık 36/100.

---

## 6. Açık kaynak projeler (GitHub taraması, 21 Kasım 2026)

Lisans ve son güncelleme GitHub API'sinden. "Numpy 2" yalnız kurulu olanlarda test edildi (venv: Python 3.13,
numpy 2.5.5).

| Sıra | Proje | Lisans | Son itme | Bize kattığı | Numpy 2 | Karar |
|---|---|---|---|---|---|---|
| 1 | martineastwood/penaltyblog | MIT | 2026-10 | DC, bivariate, Weibull, ZIP, NB, hiyerarşik Bayes; Pi/Elo/Massey/Colley; 7 devig yöntemi; RPS | ✅ (1.13.1 kurulu) | Zaten bağımlılık. Devig yöntemleri ölçüldü → kazanç yok (§4). Modeller depoda var, piyasaya ağırlık 0 |
| 2 | probberechts/soccerdata | Apache-2.0 | 2026-11 | FBref, Understat, FotMob, ClubElo, ESPN, Sofascore kazıyıcıları | ✅ (kurulu) | Zaten isteğe bağlı. Buradan FBref/Understat/ClubElo/Sofascore çalışmıyor → bugün değer katmıyor |
| 3 | georgedouzas/sports-betting | MIT | 2026-11 | football-data üzerinde değer-bahis backtest çerçevesi | test edilmedi | `evaluation/backtest.py` ile örtüşüyor; eklenmedi |
| 4 | ML-KULeuven/socceraction | MIT | 2026-10 | VAEP/xT oyuncu değerleri | test edilmedi | Olay verisi gerekir (ücretsiz canlı kaynak yok); eklenmedi |
| 5 | PySport/kloppy | BSD-3 | 2026-11 | Olay/takip verisi standardı | test edilmedi | Aynı neden; eklenmedi |
| 6 | betcode-org/betfair (betfairlightweight) | MIT | 2026-11 | Betfair Borsası API'si | test edilmedi | Hesap + bölge erişimi gerekir; eklenmedi |
| 7 | kochlisGit/ProphitBet | MIT | 2026-10 | football-data üzerinde ML tahmin arayüzü | test edilmedi | Piyasayı yenmediği kanıtlanmış model türü; eklenmedi |
| 8 | amosbastian/understat | MIT | 2025-12 | Understat xG istemcisi | test edilmedi | Veri ucu buradan HTML döndürüyor; eklenmedi |
| 9 | Torvaney/mezzala | Apache-2.0 | 2021-10 | Esnek DC + zaman ağırlığı | test edilmedi | Bakımsız, depoda karşılığı var |
| 10 | octosport/octopy | MIT | 2022-04 | DC/Elo yardımcıları | test edilmedi | Bakımsız, depoda karşılığı var |
| — | opisthokonta/goalmodel | GPL-3 (R) | 2024-03 | DC/Weibull/CMP modelleri | — | Lisans uyumsuz (yalnız fikir) |
| — | Lisandro79/BeatTheBookie | GPL-3 (MATLAB) | 2021-10 | Kaunitz ve ark. 2017 stratejisi | — | Lisans uyumsuz; fikir zaten `nesine_global`'de |
| — | JaseZiv/worldfootballR | lisans belirtilmemiş, arşivlenmiş (R) | 2025-09 | FBref/TM kazıyıcı | — | Kullanılamaz |
| — | hudl/statsbombpy | GitHub'da lisans görünmüyor | 2026-10 | StatsBomb açık veri | — | Yalnız geçmiş turnuvalar; eklenmedi |

Kaggle tarzı çözümler: yayınlanmış en iyi örnek 2017 Soccer Prediction Challenge (Berrar, Lopes & Dubitzky 2019):
reyting özellikleri + gradyan artırma; bu depoda `models/ensemble.py` olarak var ve piyasaya bilgi katmıyor.

**Sonuç:** Hiçbir kütüphane ileri-yürüyen ölçümde iyileşme getirmedi; yeni bağımlılık eklenmedi.

---

## 7. Bu dalda yapılanlar

1. `src/quantfoot/strategy/accumulator_policy.py` + `scripts/kupon_politikasi.py` + 9 test.
2. `src/quantfoot/data/match_dossier.py` + `scripts/tam_analiz.py` + 9 test (çevrimdışı sahte istemciyle).
3. `scripts/kombine_dogrulama.py`, `scripts/devig_karsilastirma.py` (yeniden üretilebilir kanıt).

## 8. Sonraki adımlar (öncelik sırası)

1. `accumulator_policy`'yi `nesine_kupon.py` / `kupon_kur.py` / Kupon Denetçisi akışına bağla: hedef oran yerine
   EV'ye göre en çok 4 bacak; aynı maç tek kupon; pay = Kelly önerisi. (Pazar kalibrasyonu dalı birleşince.)
2. API-Football `/odds` (Pinnacle) ve football-data `fixtures.csv` (Betfair Borsası) kaynaklarını `nesine_global`
   keskin referans zincirine taze yedek olarak ekle; böylece 3 saat kuralı GitHub iş akışını beklemeden sağlanır.
3. Nesine CLV defteri: oynanan her bacak için oynama anı Nesine oranı + kapanıştaki keskin fiyat.
4. Maç dosyası her gün çalıştıkça biriken bütün-turnuva fikstürüyle dinlenme/rotasyon etkisini piyasaya karşı yeniden test et.
5. Kullanıcı onaylarsa FotMob (xG, ilk 11, eksikler) — kullanım koşulları nedeniyle şimdilik kapalı.
