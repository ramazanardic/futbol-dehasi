# Dünya Futbol Bahis Algoritmaları, Piyasa Mikroyapısı ve Nicel Sendika Ansiklopedisi (2026)

Bu belge, dünya genelinde akademik literatürde (1982–2026, arXiv / JRSS-C / PNAS / IJForecasting) ve profesyonel nicel
bahis sendikalarında (Starlizard, Smartodds, Asya borsası masaları) kullanılan **tüm ana futbol tahmin, fiyatlama,
canlı bahis, kalibrasyon ve portföy yönetimi algoritmalarını** tek çatı altında özetler, her birinin `QuantFoot`
içindeki kod karşılığını ve gerçek arşiv verisi üzerindeki kanıtlanmış verimliliğini belgeler.

> **Altın Kural (Tüm Literatürün Ortak Sonucu):**
> Profesyonel düzeyde para kazanmak "en karmaşık tahmin modelini kurmak" değildir;
> **(1) keskin kapanış piyasasına (Pinnacle / Betfair Borsası) karşı ölçüm (CLV + Log-Pool testi)**,
> **(2) yumuşak büro (Nesine vb.) gecikmesi ve marj yapısını çözme**,
> **(3) fiyata henüz girmemiş bilgi (T-60 kadro şoku, canlı kırılmalar, steam yönü)** ve
> **(4) hatasız kasa/kombine disiplini (drawdown-frenli Kelly, negatif-EV bacak yasağı)** birleşimidir.

---

## 1. Gol Sayım ve Skor Dağılımı Algoritmaları

| Algoritma / Aile | Literatür Dayanağı | Temel Fikir | QuantFoot Karşılığı | Gerçek Veri Durumu |
|---|---|---|---|---|
| **Bağımsız Poisson** | Maher (1982) | $H \sim \text{Pois}(\mu_H),\; A \sim \text{Pois}(\mu_A)$ | `markets/pricing.py` | Taban model; `0-0`/`1-1`'i hafif düşük fiyatlar |
| **Dixon–Coles ($\rho$)** | Dixon & Coles (1997) | Düşük skorlarda (`0-0, 1-0, 0-1, 1-1`) bağımlılık düzeltmesi + zaman sönümü | `models/dixon_coles.py`, `markets/tail_goals.py`, `markets/inplay.py` | Canlı ve maç-öncesi beraberlik kalibrasyonunda zorunlu |
| **Bivariate / Diagonal-Inflated Poisson** | Karlis & Ntzoufras (2003) | Ortak gol bileşeni $\lambda_3$ + beraberlik köşegeni şişirme | `models/bivariate_poisson.py` | Yalnız pozitif korelasyon üretir; aşırı gol kuyruğu dar |
| **Skellam Dağılımı** | Karlis & Ntzoufras (2009) | Doğrudan gol farkı $D = H - A$ (handikap ve Asya handikabı) | `markets/pricing.py` (`skellam_probabilities`) | Handikap ve beraberlik analitiği için hızlı |
| **Weibull Sayım + Kopula** | Boshnakov, Kharrat & McHale (2017) | Aşırı/eksik dağılımlı (over/under-dispersed) gol sayımı + Frank/Gauss kopulası | `models/weibull_copula.py` | Kuyruk gol olasılıklarında Poisson'dan üstün |
| **COM-Poisson & Negatif Binom + Minimum-KL Raking** | Huang (2017/2020); Florez et al. (2024); Zhang et al. (2026) | Aşırı dağılım ($\alpha_{\text{NB}}$, $\nu_{\text{CMP}}$) + keskin 1X2/O-U/AH kotasyonlarına Csiszár I-projeksiyonu | `markets/tail_goals.py` (`rake_score_matrix_to_markets`) | **Aktif çekirdek:** AH raking ile `Hnd(-1) 1` `−0.00117` LL, `KG Var` `−0.00065` LL kazanç (`n=795`) |
| **Sarmanov / Negatif Korelasyonlu Bivariate** | Michels, Ötting & Karlis (2023); Nolan et al. (2026) | Negatif gol korelasyonu ve kadın futbolu ayrı rejimi | `markets/tail_goals.py` (kadın/kupa rejim korumaları) | Kadın futbolu erkek modeliyle karıştırılmamalı |

---

## 2. Dinamik Takım Gücü ve Derecelendirme Sistemleri

| Algoritma | Literatür Dayanağı | Temel Fikir | QuantFoot Karşılığı | Kapanış Piyasasına Katkı |
|---|---|---|---|---|
| **Elo (Gol Farkı Ağırlıklı)** | Hvattum & Arntzen (2010) | Maç sonucuna ve gol farkına göre özyinelemeli puan güncelleme | `models/ratings.py` | Tek başına `w = 0.00` (piyasa zaten fiyatlar) |
| **Pi-Ratings** | Constantinou & Fenton (2013) | Ev/deplasman ayrı dinamik güç derecesi + öngörü hatası güncellemesi | `models/ratings.py` | ML özellik setinde en güçlü taban özellik |
| **Glicko-2 / Modified Glicko** | Glickman (2001); Shelopugin & Sirotkin (2026, 1.2M maç) | Belirsizlik ($RD$) + lig-farkındalıklı terfi/küme düşme taşınması | `models/glicko2.py`, `models/pyramid.py` | Uluslararası kulüp/milli maçlarda Elo'dan üstün |
| **Kalman / Durum-Uzayı (State-Space)** | Koopman & Lit (2015); Duffield, Power & Rimella (2024) | Atak/savunma gizli durumları; sezon arası varyans sıçraması | `models/kalman.py` | Yapısal kırılma (hoca/transfer) takibinde etkili |
| **GAS-Poisson (Score-Driven)** | Creal et al. (2013); Koopman & Lit (2019) | Log-olabilirlik skoru ile otomatik adım ayarlı gol yoğunluğu | `models/gas_poisson.py` | Sağlam dinamik taban, ancak kapanış oranına `w = 0` |
| **GAP Ratings (Maç İstatistikleri)** | Wheatcroft (2020); Wheatcroft & Sienkiewicz (2021) | Şut/isabetli şut/korner beklentisini gol öncesi öngörme | `models/gap_ratings.py` | Süreç metriği olarak faydalı |
| **ML Toplulukları (LightGBM / CatBoost + Stacking)** | Berrar et al. (2019); Bunker et al. (2024); Groll et al. (2024) | Pi-ratings + GAP + oran özellikleri + gradyan artırma | `models/ensemble.py` | 16.423 maçta temel modellerin hepsi kapanışa `w = 0.00` |

---

## 3. Süreç Metrikleri (xG / EPV / VAEP) ve Kadro Etkisi

| Kavram | Literatür Dayanağı | Temel Fikir | QuantFoot Karşılığı | Pratik Kural |
|---|---|---|---|---|
| **xG / NPxG & xG+** | Mead et al. (2023); *xG+* (2025/2026) | Penaltısız şut kalitesi + şut oluşma olasılığı (sonuç gürültüsünü temizler) | `markets/lineup_xg.py` (`compute_team_xg_profiles`), `data/fotmob.py`, `data/understat.py` | Tarihsel xG Betfair kapanışına `w=0.00`; yalnız teşhis ve taze şok için kullanılır |
| **EPV / VAEP / xT** | Decroos et al. (2019); Fernández et al. (2021); Forcher et al. (2025) | Topa sahip olma zincirindeki her pas/taşıma/baskı aksiyonunun gol değerlemesi | Ücretli olay/takip akışı (Opta/StatsBomb) gerektirir | Ücretsiz canlı kaynak olmadığı için eklenmedi |
| **Oyuncu RAPM & T-60 Kadro Şoku** | Kharrat et al. (2017); Peters & Pacheco (2022); Bajons & Hornik (2024) | Eksik kaleci/gol kralı/as oyuncuların $\Delta\mu$ etkisi | `markets/lineup_xg.py` (`compute_lineup_shock`) | **Çift-sayım yasağı (`news_fresher_than_odds`):** yalnız keskin orandan *sonra* gelen T-60 şokunda ±%12 uygulanır |
| **Hakem, Hava, Dinlenme, Motivasyon** | Julian et al. (2021); den Hollander et al. (2024) | Sert kartlı hakem ($z \ge 2.0$), ölü maç (`dead_rubber`), yoğun fikstür | `markets/lineup_xg.py`, `markets/market_diagnosis.py`, `data/weather.py` | Canlı tahmin, kupon ve kasa-koruma kalkanlarına uçtan uca bağlı |

---

## 4. Piyasa Mikroyapısı, Devigging ve Keskin–Yumuşak (Sharp-vs-Soft) Arbitraj

| Yöntem | Literatür Dayanağı | Temel Fikir | QuantFoot Karşılığı | Gerçek Veri Sonucu |
|---|---|---|---|---|
| **Multiplicative / Additive** | Klasik oran normalizasyonu | Marjı orantılı veya eşit siler | `markets/devig.py` | FLB'yi kaçırır; en kötü Log-Loss (`0.998476`) |
| **Power & Shin & Odds-Ratio** | Shin (1993); Štrumbelj (2014); Clarke et al. (2017) | İçeriden bilgi ve favori-sürpriz yanlılığını (FLB) doğrusal olmayan biçimde temizler | `markets/devig.py` | Pinnacle'da `power` #1 (`0.997985` LL) |
| **Kaito Goto Standart-Hata & Ensemble** | Goto, Takeishi & Yairi (2026, arXiv:2604.17194) | Kapalı form $\tilde{p}_i = p_i - \lambda \sqrt{1 - p_i}$; sürprizlere daha fazla marj yükler | `markets/devig.py` (`goto`, `ensemble`) | Betfair'de `goto` #1 (`0.981108` LL); Pinnacle'da `ensemble` en düşük CORP MCB (`0.001447`) |
| **Hassasiyet Ağırlıklı Çoklu-Büro Log-Havuz Konsensüsü** | Sendika fiyat keşfi & belirsizlik ölçümü | Betfair + Pinnacle + Matchbook + piyasa oranlarını $w_b \propto \text{prior}_b / \sqrt{\text{vig}_b}$ ile log-olasılıkta birleştirir; bürolar arası sapmayı (`prob_std`, `KL`) Kelly'ye besler | `markets/consensus.py` (`precision_weighted_consensus`, `adaptive_kelly_from_consensus`) | `season_2627` (`n=2.435`): **en iyi Brier (`0.584134`)**, tekil Betfair (`0.981217` LL, `0.002907` MCB) ve piyasa ortalamasından (`0.981034` LL) üstün (`0.980902` LL, `0.002748` CORP MCB) |
| **Sentetik Çapraz-Pazar Tutarlılığı (1X2 ↔ ÇŞ ↔ DNB)** | Çapraz-pazar arbitraj / Dutching | `MS 1 + MS X` Dutching oranının sunulan `ÇŞ 1X` veya `DNB` oranından yüksek olduğu yumuşak-büro sızıntılarını yakalar | `markets/consensus.py` (`check_synthetic_coherence`) | Yumuşak büro marj kaybını doğrudan önler |
| **Sharp-vs-Soft Gecikme & Steam Yönü** | Kaunitz et al. (2017); Hanyu et al. (2026) | Keskin piyasa hareketi (`p_close - p_open`) ile uyumlu yumuşak-büro gecikmelerini oynar, steam karşıtını eler | `markets/line_movement.py`, `scripts/clv_analiz.py --steam` | `tipsaudit` (`n=7.348`): **Steam uyumlu `+%19,18` ROI (`p=0.0023`)** vs **Steam karşıtı `−%10,28` ROI** |

---

## 5. Türev Pazarlar, Asya Handikabı ve Aynı Maç Kombinesi (Bet Builder / SGP)

| Alan | Literatür Dayanağı | QuantFoot Karşılığı | Not |
|---|---|---|---|
| **Asya Handikabı (Tam/Yarım/Çeyrek)** | Sıfır-EV bölünmüş ödeme fiyatlaması | `markets/tail_goals.py` (`matrix_ah_outcomes`, `rake_score_matrix_to_markets`) | `|AH| >= 0.75` hatları doğrudan skor matrisine kilitlenir |
| **Devre / İY–MS / BTTS / Ekstrem Goller** | Dixon & Robinson (1998); Baert & Amez (2018) | `markets/omni_markets.py`, `markets/halves_btts.py`, `markets/extreme_goals.py` | 4B ortak tensör `J[h1, a1, h2, a2]` |
| **Same-Game Parlay (SGP / Bet Builder)** | Rana et al. (2026, *ParlayMarket*, arXiv:2603.22596) | `markets/bet_builder.py` (`price_bet_builder`) | Tüm gol/oyuncu/korner/kart bacaklarını tek ortak dağılımdan fiyatlar ve `correlation_ratio` verir |

---

## 6. Canlı (In-Play) Stokastik Gol Süreçleri

| Bileşen | Literatür Dayanağı | QuantFoot Karşılığı |
|---|---|---|
| **Zamanla Artan Gol Yoğunluğu + Uzatma Süresi** | Dixon & Robinson (1998); Mićović et al. (2023) | `markets/inplay.py` (`remaining_share`), `markets/goal_timing.py` |
| **Canlı Dixon–Coles Beraberlik Korelasyonu ($\rho$)** | Dixon & Coles (1997) | `markets/inplay.py` (`_grid`, `DEFAULT_INPLAY_RHO = -0.08`) |
| **Skor Durumu Dinamiği (1 Fark & 2+ Fark Aciliyeti)** | Heuer & Rubner (2012); Maia et al. (2023) | `markets/inplay.py` (`TRAIL_BOOST=1.10`, `TRAIL_BOOST_2=1.18`, `LEAD_DAMP_2=0.90`) |
| **Hawkes Kendini Tetikleyen Gol İvmesi (Self-Excitation)** | Ayana et al. (2025, arXiv:2501.18606) | `markets/inplay.py` (`hawkes_goal_boost`, 7 dk yarı ömürlü üstel sönüm) |
| **Kırmızı Kart Yoğunluk Kayması & Sıradaki Gol Fiyatlaması** | Ridder et al. (1994); Vecer et al. (2009) | `markets/inplay.py` (`remaining_lambdas`, `next_goal_probabilities`) |

---

## 7. Değerlendirme, Kalibrasyon ve Kasa / Portföy Yönetimi

| Yöntem | Literatür Dayanağı | QuantFoot Karşılığı | Kanıt / Etki |
|---|---|---|---|
| **Closing Line Value (CLV) + Otomatik Defter** | Kaunitz et al. (2017) | `evaluation/clv_tracker.py`, `evaluation/clv_ledger.py`, `scripts/clv_defteri.py` | Şans gürültüsünü eleyen tek erken gerçek yetenek ölçüsü |
| **Log-Opinion-Pool Piyasa Ağırlık Testi** | Pitcan (2026, arXiv:2608.11505) | `evaluation/clv_tracker.py` (`optimal_log_pool_weight`) | Model piyasaya bilgi katmıyorsa `w = 0.00` gösterir |
| **Kutusuz CORP İzotonik Güvenilirlik (MCB / DSC / UNC)** | Dimitriadis, Gneiting & Jordan (2021/2023); Walsh & Joshi (2023) | `evaluation/clv_tracker.py` (`pav_isotonic`, `corp_reliability_decomposition`) | `Brier ≡ MCB − DSC + UNC` tam özdeşliği, sıfır hiperparametre |
| **Kesirli & Baker–McHale Belirsizlik Kelly'si** | Kelly (1956); Baker & McHale (2013); MacLean–Thorp–Ziemba | `strategy/kelly.py` | Parametre ve büro sapması büyüdükçe payı küçültür |
| **Korelasyonlu Portföy Kelly'si (Gauss Kopulası)** | Çoklu eşzamanlı bahis optimizasyonu | `strategy/kelly.py` (`optimize_correlated_kelly`) | Aynı gün/lig korelasyonunda aşırı riski önler |
| **Uyarlamalı Drawdown-Frenli Kelly & Devre Kesiciler** | Uhrín et al. (2021); Long (2026); Hakobyan & Lototsky (2025) | `strategy/kelly.py` (`adaptive_kelly_stake`) | %5 günlük / %12 haftalık / %25 drawdown freni: `DD≥%25` riski `%17,5 → %0,0` |
| **Kombine Politikası & Tek-Bacak Sistem Sigortası** | Long (2026); Moshrefi (2026); Borghesi et al. (2026) | `strategy/accumulator_policy.py`, `coupons/system_builder.py`, `coupons/portfolio_guard.py` | Marj bileşikleşmesini ve ortak-maç çöküşünü durdurur |
