# QuantFoot — Bileşen Bazlı Akademik Literatür Taraması (Kasım 2026)

Bu belge, repodaki her tahmin bileşenini ilgili akademik literatürle karşılaştırır ve
somut iyileştirme önerileri çıkarır. Kaynaklar arXiv / PubMed üzerinden taranmıştır.
**Önemli not:** Değerlendirmeler makale özetlerine (abstract) dayanır; tam metinler
okunmadı. Uygulamaya geçmeden önce ilgili makalenin yöntem bölümü okunmalıdır.

Öncelik etiketleri: **[P1]** para kaybını doğrudan etkiler · **[P2]** ölçüm/doğrulama ·
**[P3]** model doğruluğu.

---

## 0. En önemli bulgu: model piyasaya bir şey katıyor mu?

| Makale | Bulgu | Repo için anlamı |
|---|---|---|
| Pitcan (2026), *Does a Structural Model Add Anything to the Closing Price?* — arXiv:2608.11505 | 19 Serie A sezonunda (7.220 maç) Dixon-Coles'un kapanış oranıyla logaritmik görüş havuzundaki (log opinion pool) optimal ağırlığı **0.000**. Model piyasadan daha iyi kalibre ama daha az keskin (sharp). | Doğruluk/LogLoss raporlamak yetmez. Asıl test: model ile marjsız kapanış olasılığını birleştiren havuzda modelin ağırlığı 0'dan anlamlı şekilde büyük mü? |
| Clegg, Song & Cartlidge (2026) — arXiv:2605.16066 | Canlı tahminde başarıyı belirleyen ana etken, takım güçlerini maç öncesi Betfair fiyatlarından başlatmak. | `fit_tail_rates_from_markets` + `fund_weight` yaklaşımı doğru yönde; model piyasaya yaslanmalı, piyasayı yenmeye çalışan bağımsız bir tahminci gibi kullanılmamalı. |
| Egidi, Pauli & Torelli (2018) — arXiv:1802.08848 | Gol oranlarını geçmiş veri + bahis oranlarının konveks birleşimi olarak kuran hiyerarşik Bayes modeli, tahmin doğruluğunu artırıyor. | Aynı fikir; `bayesian_log_odds_blend` buna karşılık geliyor. |
| Kaunitz, Zhong & Kreiner (2017) — arXiv:1710.02824 | Model kurmadan, piyasa konsensüs oranından sapan büroları bularak 10 yıllık simülasyonda ve gerçek parayla kâr; ama kazanan hesaplar büro tarafından kısıtlanıyor. | README'deki "Pin Open vs BestSoft" stratejisi bu literatürle uyumlu. Gerçek uygulamada hesap kısıtlaması riski var. |

**[P2] Öneri:** `evaluation/backtest.py` ve `scripts/ledger_report.py` içine Pitcan tarzı
"havuz ağırlığı" testi eklenmeli: `p = softmax((1-w)·log p_piyasa + w·log p_model)`,
w'yi doğrulama setinde log-loss ile seç; bootstrap güven aralığı 0'ı içeriyorsa modelin
piyasaya bilgi katmadığı sonucuna varılır. `bayesian_log_odds_blend` zaten bu formülü
uyguluyor; eksik olan, w'nin veriden tahmin edilmesi ve raporlanması.

---

## 1. Kupon / kombine (parlay) stratejisi — `strategy/coupon_builder.py`

| Makale | Bulgu |
|---|---|
| Long (2026), *Optimal Parlay Wagering and Whitrow Asymptotics* — arXiv:2603.26620 | Bağımsız olaylarda Kelly-optimal portföyde bir kombine **ancak her bacağı tek başına artı EV ise** aktif olur. Kombineyi yasaklamanın büyüme kaybı küçük (dördüncü mertebe). |
| Moshrefi (2026), *Prices, Probabilities, and Parlays* — arXiv:2607.14430 | Kalshi'de 23 milyon işlemde kombineler bacak fiyatlarının çarpımına göre sistematik olarak pahalı; pahalılık **bacak sayısıyla artıyor**. |
| Borghesi, Salaga & Mondello (2026), *Sportsbook Promotions and the Growth of Parlay Wagering* — doi:10.1007/s10899-026-10562-8 | Kombineler daha yüksek büro marjı ve bahis başına çok daha büyük ortalama oyuncu kaybıyla ilişkili. |
| Dehouche (2020) — arXiv:2004.08607 | Kombine seçimini ikili optimizasyon problemi olarak kuruyor (olasılık ve ödeme dengesi). |

**Repo ile çelişki:** `select_best_valid_bet` bacakları EV'ye göre değil `prob^1.35`
"güvenlik skoru"na göre sıralıyor; `build_target_odds_coupon` hedef orana ulaşmak için
eksi EV'li bacakları çarpıyor. 18 Kasım defterinde (bkz. `reports/ledger/`) oynanan
bacakların model EV ortalaması −%15.8 çıktı.

**[P1] Öneriler:**
1. Kupon oluşturucuya "yalnızca model EV > eşik olan bacaklar" kuralı (Long 2026).
2. Bacak sayısına üst sınır ve kupon EV'sinin (Π p·Π o − 1) zorunlu raporlanması.
3. Tahmini oranla (`_estimate_offered_odds`) kurulan kuponların "değer" kuponu sayılmaması:
   tahmini oran tanımı gereği eksi EV üretiyor.

---

## 2. Marj temizleme (devig) — `markets/devig.py`

| Makale | Bulgu |
|---|---|
| Goto, Takeishi & Yairi (2026), *Forecast Sports Outcomes under Efficient Market Hypothesis* — arXiv:2604.17194 | 90.014 maçlık veride yeni OO-EPC yöntemi çoğu büroda Multiplicative/Shin/Power'dan iyi. Ayrıca **tek parametreli favori–sürpriz yanlılığı (FL-GLM)** düzeltmesi, çok parametreli GLM'lerden iyi. |
| Yip ve ark. (2021) — arXiv:2112.13001 | Çapraz-pazar oranlarından bilgi çıkarma ve marj uygulama yöntemlerinin karşılaştırılması (korner pazarı). |

**[P3] Öneri:** `devig.py`'ye FL-GLM benzeri tek parametreli bir yöntem eklenip
`tipsaudit.csv` / Pinnacle verisi üzerinde Power ve Shin ile log-loss karşılaştırması
yapılmalı. Mevcut çözücüler matematiksel olarak doğru (bkz. inceleme notları).

---

## 3. Skor bağımlılığı ve Dixon-Coles — `models/dixon_coles.py`, `markets/pricing.py`, `markets/tail_goals.py`

| Makale | Bulgu |
|---|---|
| Michels, Ötting & Karlis (2023), *Extending the Dixon and Coles model: an application to women's football data* — arXiv:2307.02139 | Dixon-Coles, Sarmanov çarpımsal ailesinin özel hali. Bu aileyle daha uygun modeller kuruluyor; **kadın futbolu skorları erkeklerden farklı özellikler gösteriyor.** |
| Petretta, Schiavon & Diquigiovanni (2021), *Mar-Co* — arXiv:2103.07272 | Bağımlılık yapısının değiştirilmesiyle birçok bahis senaryosunda Dixon-Coles'tan iyi sonuç. |
| Nolan ve ark. (2026), Bayes bivariate conditional Poisson — arXiv:2608.07168 | Premier Lig'de ev ve deplasman golleri arasında **negatif korelasyon**; standart bivariate Poisson yalnızca pozitif korelasyona izin veriyor. |
| van der Wurp ve ark. (2019), GJRM — arXiv:1908.00823 | Kopula tabanlı ortak sayım regresyonu, Dünya Kupası verisinde standart yaklaşımla rekabetçi. |
| Ley, Van de Wiele & Van Eetvelde (2017) — arXiv:1705.09575 | Zaman ağırlıklı ML tahmininde en iyi modeller bivariate ve bağımsız Poisson. |
| Winkelmann, Michels & Deutscher (2025) — arXiv:2508.20075 | Yeni Şampiyonlar Ligi formatında (2024/25+) **beraberlik oranı düştü**; draw parametresinin formata göre güncellenmesi gerekiyor. |

**Repo durumu:** `DiagonalBivariatePoisson` yalnızca pozitif bağımlılık verebilir; DC ρ
negatif bağımlılığı yalnızca düşük skorlarda yakalıyor. Bu incelemede omni ikinci yarı
matrislerinde DC (1,0)/(0,1) düzeltmelerinin yer değiştirmiş olduğu bulundu ve düzeltildi
(`tail_goals._apply_dixon_coles_low_scores` ortak kullanılıyor; test:
`test_dixon_coles_low_score_convention`).

**[P3] Öneriler:** (a) UCL/UEL için sezon-format bazlı ayrı ρ / beraberlik kalibrasyonu;
(b) negatif korelasyona izin veren bir alternatif (Sarmanov veya kopula) backtest'te denenmeli.

---

## 4. Kadın futbolu — tüm modeller

| Makale | Bulgu |
|---|---|
| Michels, Ötting & Karlis (2023) — arXiv:2307.02139 | Kadın futbolu skor dağılımı erkeklerden farklı; ayrı modelleme gerekiyor. |
| Iván-Baragaño ve ark. (2024) — PMC11694205 | 2019→2023 Dünya Kupası arasında oyun yapısı hızla değişti (daha fazla topa sahip olma, daha fazla denge). Yapı durağan değil. |

**Repo durumu:** Eğitim verisi (`matches.csv`) erkek ligleri. 18 Kasım'da UWCL
maçlarında model, piyasadan belirgin şekilde düşük favori olasılığı verdi (ör. Chelsea
%75 model / %89 oran). `half_model_params` ve `league_tail_regime` kadın ligleri için
yalnızca birkaç sabit profil içeriyor.

**[P1] Öneri:** Kadın maçları için ayrı veri ve kalibrasyon gelene kadar bu maçlarda
model olasılığı **kullanılmamalı** veya yalnızca piyasa olasılığı (devig) temel alınmalı.
En azından `MatchRiskContext`'e "kalibre edilmemiş rekabet" bayrağı eklenmeli.

---

## 5. Dinamik takım gücü — `models/kalman.py`, `models/gas_poisson.py`, `models/glicko2.py`, `models/ratings.py`

| Makale | Bulgu |
|---|---|
| Duffield, Power & Rimella (2024, JRSS-C) — arXiv:2308.02414 | Durum-uzayı perspektifi; filtreleme/düzleştirme/parametre tahmini; açık kaynak `abile`. README'de zaten referans. |
| Szczecinski & Tihon (2021) — arXiv:2104.14012 | Elo, Glicko ve TrueSkill, yaklaşık bir Kalman filtresinin özel halleri; Bayes yaklaşımının kazancı ancak belirli koşullarda gerçekleşiyor. |
| Macrì-Demartino, Egidi & Torelli (2025, JRSS-C) — arXiv:2508.05891 | Dönem bazlı "commensurate prior" ve spike-and-slab ile **transfer dönemi / hoca değişimi** gibi kırılmalarda hızlı uyum; diğer dinamik modellerden iyi. R paketi `footBayes`. |
| Shelopugin & Sirotkin (2026), *A Modified Glicko Model for Rating Soccer Clubs and National Teams Worldwide* — arXiv:2611.15378 | 252 lig, 1.2 milyon kulüp maçı: lig farkındalıklı başlangıç ve **ligleri şişirmeyen terfi/küme düşme kuralları**; Elo'dan açıkça iyi, gradient boosting + Dixon-Coles kadar iyi; uluslararası kulüp maçlarında belirgin şekilde daha iyi. Rating modeli + Markov zinciri modelinin ortalaması ikisinden de iyi. **Veri ve kod açık.** |
| Nguyen & Tran (2026) — arXiv:2607.01722 | Glicko-2'ye gol farkı ayarı, yapısal şoklar ve ordered-logit beraberlik modeli ekleniyor. |
| Ingram (2019) — arXiv:1902.07378 | Markov dinamikleri yerine Gauss süreci önceli; kovaryat eklemek kolay. |

**[P3] Öneriler:**
1. `pyramid.py` (terfi/küme düşme taşıması) ile Shelopugin & Sirotkin'in kuralları
   karşılaştırılmalı; açık veri/kodla doğrudan kıyas yapılabilir (UCL/UEL ve milli maçlar
   için özellikle değerli).
2. Kalman/GAS'a yapısal kırılma (transfer dönemi, hoca değişimi) için varyans sıçraması —
   kalman.py'de sezon arası sıçrama var; sezon içi hoca değişimi yok.

---

## 6. Dağılım: COM-Poisson / aşırı dağılım — `markets/tail_goals.py`

| Makale | Bulgu |
|---|---|
| Zhang, Rastelli & Friel (2026) — arXiv:2607.18009 | COM-Poisson + spike-and-slab ile **takım bazlı** dağılım parametresi; EPL'de takımlar arasında dağılım heterojenliği ve Poisson'a göre daha iyi tahmin. |
| Florez, Guindani & Vannucci (2024) — arXiv:2409.17129 | Bivariate COM-Poisson, Poisson ve Negatif Binom'a eşit veya daha iyi; spor sayım verisi için varsayılan model önerisi. |
| Huang (2017) — arXiv:1606.03214; Huang (2020) — arXiv:2011.07503 | Ortalama-parametreli COM-Poisson; repodaki `com_poisson_pmf` (bisection ile ortalama eşleme) bu yaklaşımla tutarlı. |
| Philipson & Huang (2023) — doi:10.1007/s11222-023-10244-0 | Ortalama-parametreli COM-Poisson için hızlı tablo (look-up) yöntemi. |

**[P3] Öneriler:** (a) `nu` şu an lig bazlı sabit (1.10); takım bazlı `nu` (Zhang ve ark.)
denenebilir. (b) `com_poisson_pmf` her çağrıda 24 adımlık bisection yapıyor; omni motoru
maç başına çok sayıda çağırıyor → Philipson & Huang tarzı ön-hesaplanmış tablo hız
kazandırır.

---

## 7. Devre bazlı gol zamanlaması ve İY/MS — `markets/omni_markets.py`, `markets/halves_btts.py`

| Makale | Bulgu |
|---|---|
| Maia ve ark. (2023), *Stochastic modelling of football matches* — arXiv:2312.04338 | Brezilya Serie A, 8 yıl: kırmızı kart gol yoğunluğunu **%30+** düşürüyor; bir gol geride olan takımın gol yoğunluğu **+%10**, iki gol geride olanın **+%20**; uzatma süreleri skora bağlı. |
| Heuer & Rubner (2012) — PMC3511508 | Bundesliga'da Poisson varsayımı genel olarak tutuyor ama skora bağlı sapmalar anlamlı; deplasman önde olduğunda maç sonunda büyük etkiler; beraberliklerin beklenenden fazla olmasının nedeni bu. |
| Baert & Amez (2018) — PMC5843336 | Devre arasından hemen önce atılan gol, ikinci yarıda o takımın gol olasılığını düşürüyor. |

**Repo ile karşılaştırma (`raw_mults`):** Bir gol gerideki takım için çarpan 1.095–1.105
(Maia'nın +%10'u ile **uyumlu**). Ama iki gol gerideki takım için çarpan **0.99**
(`h_plus2` deplasman: 0.990, `a_plus2` ev: 0.990); Maia +%20 buluyor. Çarpanların
kaynağı (184.276 maç kalibrasyonu) repoda belgelenmemiş.

**[P3] Öneri:** `h_plus2` / `a_plus2` çarpanları İY+MS verisinden yeniden tahmin edilip
belgelenmeli; literatürle çelişki ya doğrulanmalı ya düzeltilmeli. İY/MS ters dönüş
(1/2, 2/1) olasılıkları bu çarpanlara en duyarlı pazar.

---

## 8. Atak istatistikleri ve xG vekili — `models/gap_ratings.py`, `data/xg_proxy.py`

| Makale | Bulgu |
|---|---|
| Wheatcroft (2020), *Forecasting football matches by predicting match statistics* — arXiv:2001.09097 | GAP ratings ile maç istatistiklerini önceden tahmin etmek, oranlarda olmayan bilgi taşıyor; iki bahis stratejisiyle uzun vadeli kâr. |
| Wheatcroft & Sienkiewicz (2021) — arXiv:2101.02104 | Takımlar arası **şut başarı olasılığı farkı** modellenince maç sonucu ve 2.5 Üst tahminleri iyileşiyor; bahis performansında karışık kanıt. |
| Pitcan (2026) — arXiv:2608.11505 | İsabetli şut modeli gol modeline 0.35 ağırlıkla bilgi katıyor ama piyasaya karşı ağırlığı yine 0. |

**[P3] Öneri:** `WheatcroftGAPRatings` şut başarı oranını takımlar arasında eşit
varsayıyorsa, Wheatcroft & Sienkiewicz'in parametrik şut-başarı modeli eklenebilir.

---

## 9. Makine öğrenmesi topluluğu — `models/ensemble.py`

| Makale | Bulgu |
|---|---|
| Bunker, Yeung & Fujii (2024), *Machine Learning for Soccer Match Result Prediction* — arXiv:2403.07669 | Yalnızca gol verisi olan veri setlerinde en iyi sonuç: **pi-ratings + CatBoost** (gradient boosting). |
| Yeung ve ark. (2023) — arXiv:2309.14807 | 2023 Soccer Prediction Challenge: pi-ratings + CatBoost; derin öğrenme karşılaştırması. |
| Groll ve ark. (2021, 2024) — arXiv:2106.05799, arXiv:2410.09068 | Hibrit modeller: tarihsel güç + bahis oranlarından güç + oyuncu reytingleri. |

**Repo durumu:** LGBM + pi-ratings + 10 alt model zaten var; literatürle uyumlu.
**[P2] Öneri:** README'deki ağırlıkların (ör. `gap_ordered=0.204`) zaman içinde
kararlılığı raporlanmalı; ağırlıklar sezondan sezona çok oynuyorsa aşırı uyum işareti.

---

## 10. Değerlendirme ve kalibrasyon — `evaluation/metrics.py`, `scripts/ledger_report.py`

| Makale | Bulgu |
|---|---|
| Wheatcroft (2019), *The case against the Ranked Probability Score* — arXiv:1908.08980 | Simülasyonlarda **ignorance (log) skoru**, RPS ve Brier'dan daha iyi model ayırt ediyor. |
| Foulley (2021) — arXiv:2106.14345 | Skor ayrıştırmaları (güvenilirlik / ayırt edicilik), güvenilirlik diyagramları; Poisson modelleri UCL'de bahis oranlarına kıyasla iyi güvenilirlik. |
| Dimitriadis, Gneiting, Jordan & Vogel (2023), *The Triptych* — arXiv:2301.10803 | CORP yöntemi: PAV ile güvenilirlik diyagramı ve ortalama skoru **MCB (kalibrasyon hatası) / DSC (ayırt edicilik) / UNC** bileşenlerine ayırma. |
| Walsh & Joshi (2023) — arXiv:2303.06021 | Bahiste model seçimi doğruluğa değil **kalibrasyona** göre yapılınca ROI +%34.7, doğruluğa göre −%35.2 (NBA). |

**[P2] Öneriler:** (a) Model seçiminde birincil ölçüt log-loss / ignorance olmalı (README
zaten LogLoss raporluyor); (b) `ledger_report.py`'ye CORP tarzı MCB/DSC ayrıştırması ve
güvenilirlik tablosu eklenmeli — birkaç hafta veri birikince anlamlı olur.

---

## 11. Bahis boyutlandırma — `strategy/kelly.py`

| Makale | Bulgu |
|---|---|
| Uhrín, Šourek, Hubáček & Železný (2021), *Optimal sports betting strategies in practice* — arXiv:2107.08827 | At yarışı, basketbol ve futbolda risk-kontrol modifikasyonları pratikte zorunlu; **uyarlanabilir (adaptive) kesirli Kelly** geniş bir yelpazede uygun seçim. |
| Metel (2017) — arXiv:1701.02814 | Olasılıklar multinomial lojistikle tahmin edildiğinde tahmin hatasını hesaba katan stokastik optimizasyon daha iyi getiri veriyor. |
| Hsieh, Barmish & Gubner (2017) — arXiv:1710.01786 | Bazı durumlarda teorik Kelly fazla temkinli olabilir (ampirik dağılıma göre). |
| Hakobyan & Lototsky (2025) — arXiv:2503.17927 | Kelly portföy büyümesinin asimptotik varyansıyla iki yeni risk ölçüsü. |

**Repo durumu:** Baker-McHale küçültmesi var (bu incelemede tavan/küçültme sırası
düzeltildi). Korelasyonlu portföy Kelly'si Gauss kopulasıyla doğru kurulmuş.
**[P3] Öneri:** Sabit 0.25 çarpanı yerine Uhrín ve ark.'nın uyarlanabilir kesirli
Kelly'si backtest'te denenebilir.

---

## 12. Öncelikli yapılacaklar listesi

| # | Öncelik | İş | Dayanak |
|---|---|---|---|
| 1 | P1 | Kupon oluşturucuda yalnızca artı EV bacaklar, bacak sayısı sınırı, kupon EV'si raporu | Long 2026; Moshrefi 2026; Borghesi ve ark. 2026 |
| 2 | P1 | Kadın futbolu maçlarında model olasılığını devre dışı bırak / piyasa olasılığına düş | Michels ve ark. 2023; 18 Kasım defteri |
| 3 | P2 | Backtest ve deftere "piyasaya karşı havuz ağırlığı" testi | Pitcan 2026 |
| 4 | P2 | Defter raporuna CORP güvenilirlik ayrıştırması (MCB/DSC) ve log skoru | Dimitriadis ve ark. 2023; Wheatcroft 2019 |
| 5 | P3 | İki gol geride takım çarpanlarını yeniden tahmin et ve belgele | Maia ve ark. 2023 |
| 6 | P3 | FL-GLM tarzı tek parametreli devig yöntemi | Goto ve ark. 2026 |
| 7 | P3 | Modified Glicko (açık kod/veri) ile pyramid/Glicko karşılaştırması | Shelopugin & Sirotkin 2026 |
| 8 | P3 | Takım bazlı COM-Poisson `nu`; COM-Poisson için ön-hesaplı tablo | Zhang ve ark. 2026; Philipson & Huang 2023 |
| 9 | P3 | UCL yeni format için beraberlik / ρ kalibrasyonu | Winkelmann ve ark. 2025 |
