# Bahis aileleri denetimi — 21 Kasım 2026

Dal: `grokbot/bahis-aileleri` (origin/main üzerinden; PR açılmadı). Amaç: Nesine'deki her bahis ailesinin
fiyatlama kodunu matematik olarak denetlemek, hataları birim testiyle yakalayıp düzeltmek, walk-forward
(geleceğe bakmadan) kalibrasyon + oran karşılaştırmasıyla her değişikliği kanıtlamak ve aile bazlı değer
kurallarını merkezi ayarlara bağlamak.

**Kural:** bir değişiklik ancak log-loss farkının (yeni − eski) %95 bootstrap güven aralığının **üst ucu < 0**
ise tutuldu. Test sezonları 2016/17+ (77.503 maç), her test sezonu yalnız önceki sezonlarla eğitildi
(500 maç-düzeyi bootstrap). API-Football kotası kullanılmadı; başka yapay zekâların tahmin klasörleri açılmadı;
bahis yapılmadı.

## 1. Bulunan ve düzeltilen hatalar

| # | Yer | Hata | Düzeltme | Test |
|---|-----|------|----------|------|
| 1 | `markets/pricing.over_under_probability` | Tam-sayı çizgide (2.0, 3.0) "Alt" olasılığı iade (push) kütlesini de içeriyordu → Alt fiyatı şişikti | Kesin (P(tot>line), P(tot<line)) döner; `cli.py` EV = (1−p_push)(p·o−1) | ✓ |
| 2 | `markets/omni_markets` | "1. Yarı / 2. Yarı / 1Y ve 2Y / En Az Bir Devre KG" ayrı bağımsız bir modelden hesaplanıyordu → aynı maçın diğer pazarlarıyla tutarsız | Tırmıklanmış ortak (joint) dağılımdan hesaplanıyor | ✓ |
| 3 | `markets/bet_builder` | "İlk/Son Gol Ev/Dep" ve oyuncu "İlk/Son Golü Atar" yarı sırasını yok sayıyordu (2Y'de atan takım İY'de atan varken ilk gol sayılıyordu) | `goal_order_share` yarı sıralı | ✓ (0-1/2-0 tek-durum, toplam = 1 − P(0-0)) |
| 4 | `scripts/nesine_global.price_event` | İki gol oranı 1X2 + Ü/A (+KG) kotasyonlarını aynı anda tutturamıyor; türev pazarlar bu uyumsuzluğu miras alıyordu (beraberlik 0.8 puan düşük → 1-1, 2-2, "MS 0 & KG Var", KG Var hep düşük) | `tail_goals.rake_score_matrix_to_markets`: skor matrisinin kotasyonlara minimum-KL (IPF) izdüşümü | ✓ (kotasyonları birebir tutar, idempotent, marjinaller korunur) |
| 5 | Aynı yer | Tırmıklanmış matris büyük farkları fazla fiyatlıyordu (Fark Ev 3+ 0.104 vs gerçek 0.094; Fark Ev 1 0.205 vs 0.219) | Tırmık öncesi fark eğimi exp(−θ·max(|h−a|−1,0)), θ=0.05 **yalnız 2016 öncesi** veriyle seçildi (`settings.MARGIN_TILT`) | ✓ |
| 6 | `markets/market_calibration` | Kalibrasyon eğrisi yalnız eğrinin kaydedildiği tarafa uygulanıyordu; "2.5 Alt", "KG Yok", "Çift", `DEĞİL(x)` ham kalıyordu | Tümleyen anahtar (Alt↔Üst, Yok↔Var, Çift↔Tek): cal(Alt, p) = 1 − cal(Üst, 1−p); `DEĞİL(x)` aynı şekilde | ✓ |
| 7 | `evaluation/auto_learn.market_family` | Yanlış aile: "En Çok Gol …" → Gol aralığı, "Ev Her İki/En Az Bir Yarıyı" → Ev sahibi golleri, "Skor x-y" / "Fark …" / "İki Yarıda KG Var" / "Kart" → Diğer, "Son Gol" → Gol aralığı. Öğrenilen aile-σ'sı yanlış ailelere karışıyordu | Doğru ailelere (Yarı özel, Doğru skor, Handikap, Yarı karşılıklı gol, İlk gol, Kart) | ✓ |
| 8 | `nesine_kupon.candidates` | Model-türevi (doğrudan kotasyonu olmayan) bacaklar için hiçbir değer tabanı yoktu (yalnız PR #3 zor pazarları) | Aile bazlı EV tabanı + σ eki (bölüm 4) | ✓ |

Kontrol edilip **doğru** bulunanlar: devig çözücüleri (power, odds-ratio, Shin), Dixon-Coles τ, Asya
çeyrek çizgilerinin iki alt çizgiye bölünmesi (14 çizgi × iki taraf, skor-skor kaba kuvvetle doğrulandı),
Asya toplam ayna simetrisi, goal_timing ilk gol takım payı, borsa orta fiyat normalizasyonu, Nesine MTID 268
handikap çevirisi (SOV = ev sahibinin avansı; L. Zagreb–Hajduk ile doğrulandı), aynı maç kombineleri (tek
ortak dağılımdan fiyatlandığı için tutarlı; best_coupon maç başına tek bacak).

## 2. Aile bazında kalibrasyon (test 2016/17+, n = 77.503)

"Eski" = 21 Kasım öncesi hat (tırmıksız), "tırmık+eğim" = yapısal düzeltmeler (4+5), "son" = + yalnız
CI kuralını geçen Platt eğrileri (türev seçimlere; doğrudan kotasyonlar asla yeniden kalibre edilmez).
ECE = 10 kovalı beklenen kalibrasyon hatası (seçim ortalaması); ΣΔLL = ailedeki seçimlerin log-loss
kazancı toplamı (pozitif = iyileşme).

| Aile | Seçim | ECE eski | ECE tırmık+eğim | ECE son | ΣΔLL | Tutulan eğri |
|------|------:|------:|------:|------:|------:|------:|
| Maç Sonucu (doğrudan) | 3 | 0.0052 | 0.0052 | 0.0052 | 0 | 0 |
| Çifte Şans (doğrudan) | 3 | 0.0052 | 0.0052 | 0.0052 | 0 | 0 |
| Alt/Üst 0.5–5.5 | 6 | 0.0034 | 0.0029 | 0.0029 | 0.00029 | 0 |
| Karşılıklı Gol | 1 | **0.0173** | 0.0068 | **0.0020** | 0.00088 | 1 (lig) |
| İY Sonucu | 5 | 0.0052 | 0.0052 | 0.0049 | 0.00014 | 1 |
| İY Alt/Üst | 3 | 0.0063 | 0.0063 | 0.0040 | 0.00033 | 1 |
| 2Y Sonucu / Alt-Üst | 5 | 0.0061 | 0.0089 | 0.0041 | 0.00028 | 2 |
| İY/MS | 9 | 0.0043 | 0.0031 | 0.0022 | 0.00144 | 3 |
| Handikap (Avrupa) | 9 | **0.0111** | 0.0055 | **0.0034** | 0.00479 | 6 |
| Toplam Gol Aralığı | 4 | 0.0037 | 0.0036 | 0.0036 | 0.00016 | 0 |
| Tek/Çift | 2 | 0.0076 | 0.0066 | 0.0033 | 0.00035 | 1 |
| Doğru Skor | 17 | 0.0042 | 0.0031 | 0.0020 | 0.00249 | 5 |
| Takım Golleri | 10 | 0.0057 | 0.0043 | 0.0039 | 0.00092 | 2 |
| Yarı KG | 3 | 0.0028 | 0.0030 | 0.0021 | 0.00024 | 1 |
| Yarı Özel (En Çok Gol, Her İki/En Az Bir Yarı) | 13 | 0.0050 | 0.0047 | 0.0037 | 0.00061 | 3 |
| Fark | 7 | **0.0086** | 0.0046 | 0.0035 | 0.00280 | 4 |
| Kombine | 21 | 0.0073 | 0.0048 | 0.0032 | 0.00485 | 8 |

Eski hat → yapısal düzeltmeler (eşli, aynı maçlar): **53 seçim daha iyi, 3 daha kötü, 65 değişmedi**
(toplam ΔLL −0.0135). Öne çıkanlar (ΔLL, %95 CI):

- KG Var: tahmin 0.507 → 0.519 (gerçek 0.524), −0.00060 [−0.00080, −0.00042]
- Hnd(−1) 1 / Fark Ev 2+: −0.00085 [−0.00102, −0.00067]
- Fark 0: ECE 0.0137 → 0.0057, −0.00058 [−0.00076, −0.00039]
- MS 0 & KG Var: −0.00058 [−0.00075, −0.00041]; Skor 1-1: −0.00024 [−0.00035, −0.00015]
- Kötüleşen 3 seçim 2Y 1 / 2Y 0 / 2Y 0.5 Üst (İY modeli sabit kalıp TS farkı daraldığı için); üçünün
  ikisine Platt eğrisi tutuldu (2Y 0 ECE 0.0149 → 0.0013, 2Y 0.5 Üst 0.0118 → 0.0016).

Eğim (θ=0.05) tek başına, yalnız tırmığa göre: 44 iyi / 9 kötü / 68 değişmedi (Hnd(−1) 1 −0.00065
[−0.00079, −0.00051]). θ, 2016 öncesi 12.000 maçta {0, .05, .1, .15, .2, .3, .4} ızgarasında fark-kovası
log-loss'una göre seçildi (1.74091 → 1.74022), test verisine bakılmadı.

Kalan yapısal sapma: **ilk yarı payı biraz düşük** (İY 0.5 Üst 0.686 vs 0.697, İY 0 0.422 vs 0.414,
İY Skor 0-0 0.314 vs 0.303). Tırmık bunu değiştirmez (İY kotasyonu yok); Platt eğrileri kapatıyor
(İY 0.5 Üst ECE 0.0111 → 0.0044). Yapısal İY düzeltmesi (yarı payı a1 ≈ 0.44) açık iş.

Tüm seçim satırları (güvenilirlik eğrileri dahil): `reports/research/bahis_aileleri_kalibrasyon.json`
(son hat), `..._ham.json` (eski hat), eşli karşılaştırmalar `bahis_aileleri_karsilastirma_*.json`.
Kalibrasyon eğrileri `data/calibration/market_calibration.json` (38 eğri; her biri `oos_ll_fark` ve
`oos_ci95` taşır).

## 3. Oran karşılaştırması (ROI, test 2016/17+)

Olasılık = devig edilmiş ortalama orandan türetilen fiyat; bahis = en iyi piyasa fiyatı (Max*). Bu bir
**üst sınır göstergesi**dir (Nesine marjı en iyi fiyattan daha yüksektir). EV < %25 (absürt EV dışlandı).

| Pazar | EV ≥ 0 | EV ≥ 2 % | EV ≥ 3 % | EV ≥ 5 % | EV ≥ 8 % |
|------|------|------|------|------|------|
| MS 1 | +1.0 % [−0.2, 2.2] n=28.166 | +0.9 % [−1.8, 3.7] | +2.8 % [−1.2, 6.6] | +5.7 % [−0.6, 13.3] | **+23.9 % [2.8, 48.3]** n=355 |
| MS 0 | −0.8 % [−4.3, 2.6] | +2.0 % [−4.9, 7.6] | +0.2 % | +7.7 % [−6.8, 22.9] | −1.7 % |
| MS 2 | −1.8 % [−3.9, 0.5] | −2.2 % | −3.3 % | +0.6 % | −3.3 % (ort. oran 8.9) |
| 2.5 Üst | +1.0 % [−1.4, 3.2] | **+8.8 % [1.2, 16.4]** n=575 | **+12.4 % [0.5, 23.7]** n=262 | +15.1 % [−6.6, 34.4] | n<30 |
| 2.5 Alt | +0.1 % | +3.4 % [−3.4, 10.6] | −1.0 % | +6.5 % | n<30 |

**Asya handikabı** (tek türev aile ki arşivde gerçek oranı var; ortalama marj %4.15):

| Fiyat | Taraf | Beklenen kazanç payı | Gerçek | EV ≥ 0 | EV ≥ 2 % | EV ≥ 5 % |
|------|------|------:|------:|------|------|------|
| Eski hat (tırmıksız) | Ev | 0.4339 | 0.4247 | **−4.8 % [−6.9, −2.9]** n=7.385 | −5.6 % | −8.4 % [−15.4, −0.7] |
| Son hat (tırmık+eğim) | Ev | 0.4315 | 0.4247 | **−3.7 % [−6.5, −0.6]** n=3.326 | −7.7 % [−15.2, −1.2] | +8.8 % [−8.3, 25.8] |
| Son hat + Fark-Platt (walk-forward) | Ev | 0.4281 | 0.4247 | −3.3 % [−7.4, 0.2] n=2.145 | −2.9 % | +2.6 % |
| Son hat | Dep | 0.4302 | 0.4318 | 0.0 % [−5.0, 4.7] | −5.2 % | +1.5 % |

Sonuç: türev Asya handikabı ~%4 marjlı bir kitaba karşı **kenar taşımıyor**. Düzeltmeler ev tarafındaki
yanlış "değer" sinyallerini %55–70 azalttı (7.385 → 2.145 bahis) ve zararı küçülttü ama pozitif ROI yok
→ Handikap ailesinin tabanı yüksek tutuldu ve türev AH yalnız doğrudan kotasyonla oynanmalı.

## 4. Aile bazlı değer kuralları (merkezi: `settings.FAMILY_VALUE_RULES`)

Eşleme: `quantfoot.markets.families.bet_family(isim)`. Kupon bacağı (`nesine_kupon.candidates`):
her bacağa σ + aile σ'sı (+ zor pazar σ'sı); **model-türevi** bacak EV ≥ max(aile tabanı, zor pazarsa
HARD_MARKET_MIN_EV=0.03); doğrudan kotasyonlu bacak PR #3 kuralını korur (taban yalnız zor pazarlarda).
Ana tahmin (`derin_tahmin.choose`, `simulasyon.best_value_bet`): EV ≥ max(PICK_MIN_EV=0.02, aile tabanı).
Araştırma için kapatma: `nesine_kupon.py --aile-ev-kapali` (zor pazar kuralı yine geçerli).

| Aile | Min EV | Ek σ | Gerekçe |
|------|------:|------:|------|
| Maç Sonucu | 0.03 | 0 | MS 1 ancak EV ≥ 3 %'ten itibaren pozitif eğilim; MS 2 her eşikte zayıf |
| Çifte Şans | 0.02 | 0 | doğrudan, düşük varyans |
| Alt/Üst | 0.03 | 0 | 2.5 Üst EV ≥ 2–3 %'te CI pozitif |
| Karşılıklı Gol | 0.03 | 0 | eğri sonrası ECE 0.002 |
| Takım Golleri | 0.03 | 0 | iyi kalibre |
| Toplam Gol Aralığı, İY/2Y Sonucu, İY/2Y Alt/Üst, Yarı KG, Yarı Özel, Tek/Çift | 0.04 | 0.005 | kalan İY/2Y sapması, eğriyle kapatılmış |
| Handikap | 0.05 | 0.005 | türev AH arşivde zarar etti |
| Kombine | 0.05 | 0.010 | çok parçalı, kalan korelasyon hatası |
| İlk Gol | 0.05 | 0.010 | arşivde ilk gol verisi yok → test edilemedi |
| İY/MS, Fark | 0.06 | 0.010 | uzun oran, yüksek varyans |
| Doğru Skor | 0.08 | 0.010 | en uzun oranlar |
| Korner, Kart | 0.05 | 0.015 | yalnız doğrudan borsa kotasyonu; arşivde oran yok |
| Diğer | 0.05 | 0.010 | bilinmeyen |

## 5. Korner / kart

`scripts/evaluate_corner_card_models.py` (test 2023-07+, 23.073 maç, log-loss): takım-rating modeli
(α=0.03) lig ortalamasına göre takım kornerlerinde (Ev Korner 4.5 Üst 0.6592 vs 0.6809; Dep 0.6599 vs 0.6837)
ve kartlarda (Kart 3.5 Üst 0.6514 vs 0.6608) belirgin iyi, toplam kornerde fark yok (9.5 Üst 0.6894 vs 0.6891).
Uyarılar: CI hesaplanmıyor, lig tabanları test dönemini de içeren veriden. Arşivde korner/kart oranı yok →
ROI ölçülemez. Bu yüzden korner/kart yalnız doğrudan kotasyonla fiyatlanmaya devam ediyor.

## 6. Açık kalan boşluklar (test edilemediği için uygulanmadı)

- **Nesine korner/kart pazarlarının çoğu çevrilmiyor:** MTID 798/799 (korner handikap), 338/340 (aralık),
  220/222 (en çok korner), 224 (ilk korner), 299 (korner tek/çift), 601/602 (takım kornerleri),
  301/800 (kart puanı), 603, 225. Modeli var (`corners_cards.py`) ama arşivde oran yok.
- **Çeviri eksikleri:** MTID 528/529 SOV=0.0 (çizgi bilinmiyor); MTID 571'de "4+" içeren sonuçlar; MTID 777
  (büyük olasılıkla doğru skor) ve birçok 7xx/8xx MTID `nesine_markets.json`'da tanımsız.
- **İlk gol / takım ilk golü:** arşivde gol dakikası/sırası yok → backtest yapılamadı (matematik birim
  testiyle doğrulandı).
- **İlk yarı payı:** yapısal düzeltme (a1) yapılmadı; Platt eğrileriyle kapatıldı.
- **2Y pazarları:** eğim sonrası ham hâli kötüleşti; 2Y 0 ve 2Y 0.5 Üst eğrili, 2Y 1 eğrisiz (CI kuralı geçmedi).

## 7. Testler ve yeniden üretim

- Yeni `tests/test_bahis_aileleri.py`: **73 test** (O/U iadesi, yarı KG'nin ortak dağılımdan gelmesi, ilk gol
  yarı sırası, 14 Asya çizgisi × 2 taraf kaba kuvvet, Asya toplam simetrisi, tırmık doğruluğu/idempotentlik,
  fark eğimi, MTID 268, tümleyen/DEĞİL kalibrasyonu, aile sınıflandırıcı, aile tabanları, kupon ve ana tahmin
  entegrasyonu, auto_learn aile düzeltmeleri).
- Tüm paket: **1670 geçti** (`PYTHONPATH=src` ile; venv'deki editable kurulum ana repoyu gösterdiği için
  worktree'de bu gerekli).
- Yeniden üretim:
  ```
  python scripts/bahis_aileleri_kalibrasyon.py onbellek --isci 6          # son hat (≈10 dk)
  QF_AILE_VARYANT=ham python scripts/bahis_aileleri_kalibrasyon.py onbellek
  python scripts/bahis_aileleri_kalibrasyon.py analiz --yaz --isci 6     # eğriler + json
  python scripts/bahis_aileleri_kalibrasyon.py karsilastir ham ""        # eşli karşılaştırma
  ```
