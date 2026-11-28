# QuantFoot v8 Kapsamlı Algoritma, Veri ve Doğrulama Yükseltmesi (26 Kasım 2026)

Bu belge, `docs/research/gap_analysis_2026_11_21.md` ve `docs/research/roadmap_2026_11.md` içindeki en yüksek getirili
açıkları kapatmak üzere ortak çekirdeğe (`src/quantfoot/`, `scripts/`) entegre edilen **6 yapısal yükseltmeyi** ve
`arsiv_kod/v8_dogrulama.py` ile gerçek arşiv verisi üzerinde ölçülen örneklem dışı sonuçları belgeler. Tüm modüller
5 yapay zekâ (`claudetahmin`, `geminitahmin`, `antigravitytahmin`, `chatgbttahmin`, `grokbottahmin`) için birebir
ortak ve eşittir.

---

## 1. Kaito Goto Standart-Hata Devigging ve Topluluk (Ensemble) Marj Kaldırma

- **Kod:** `src/quantfoot/markets/devig.py` (`method="goto"`, `method="ensemble"`, ayrıca `_solve_shin` ve `_solve_odds_ratio` kök-bulma aralıkları gerçek borsa verileri için sertleştirildi).
- **Matematiksel tanım:** Kaito Goto dönüşümü, her sonucun ters oranını ($p_i = 1 / O_i$) kendi standart hata biriminin
  ($\text{se}_i = \sqrt{(p_i - p_i^2) / p_i} = \sqrt{1 - p_i}$) ortak bir katsayısı kadar aşağı kaydırır:
  $$\tilde{p}_i = p_i - \lambda \sqrt{1 - p_i}, \qquad \lambda = \frac{\sum_j p_j - 1}{\sum_j \sqrt{1 - p_j}}$$
  Sürpriz sonuçların standart hatası daha büyük olduğu için favori-sürpriz yanlılığı (favourite-longshot bias) iterasyon
  gerektirmeden kapalı formda düzeltilir. Aşırı düşük olasılıklı sürprizlerde aktif-küme projeksiyonu ile pozitif
  simpleks ve toplam $= 1$ garanti edilir.

### Gerçek Veri Doğrulaması (`arsiv_kod/v8_dogrulama.py`, toplam 9.798 maç)

#### A) Betfair Exchange Kapanış 1X2 (`data/global_odds/latest/season_2627/*.csv`, 22 Avrupa ligi, `n = 2.449`)

| Yöntem | Log-Loss (düşük iyi) | Brier 1X2 (düşük iyi) | Ev ECE | Ev MCB | Ev DSC |
|---|---:|---:|---:|---:|---:|
| **`goto`** | **0.981108** | **0.584189** | 0.017463 | 0.000568 | 0.029826 |
| **`ensemble` (Power+Shin+Goto)** | **0.981174** | 0.584227 | 0.017747 | 0.000582 | 0.029797 |
| `power` | 0.981175 | 0.584223 | 0.017848 | 0.000591 | 0.029838 |
| `shin` | 0.981243 | 0.584271 | 0.017809 | 0.000581 | 0.029715 |
| `odds_ratio` | 0.981275 | 0.584285 | **0.016335** | **0.000532** | 0.029489 |
| `multiplicative` | 0.981439 | 0.584392 | 0.017844 | 0.000562 | 0.029443 |

#### B) Pinnacle Kapanış 1X2 (`data/tipsaudit.csv`, `n = 7.349`)

| Yöntem | Log-Loss | Brier 1X2 | Ev ECE | Ev MCB | Ev DSC |
|---|---:|---:|---:|---:|---:|
| **`power`** | **0.997985** | **0.596117** | **0.007697** | **0.000169** | 0.026197 |
| **`ensemble`** | **0.997997** | 0.596132 | 0.007737 | 0.000186 | 0.026202 |
| `odds_ratio` | 0.998037 | 0.596137 | 0.008225 | 0.000228 | 0.026047 |
| `goto` | 0.998047 | 0.596167 | 0.009681 | 0.000181 | **0.026379** |
| `shin` | 0.998052 | 0.596157 | 0.007735 | 0.000215 | 0.025936 |
| `multiplicative` | 0.998476 | 0.596391 | 0.011719 | 0.000390 | 0.025952 |

- **Sonuç:** `goto` Betfair Exchange üzerinde hem Log-Loss hem Brier'da #1 oldu; `power` ve `ensemble` Pinnacle üzerinde
  en düşük Log-Loss'u verdi. Tüm FLB-duyarlı yöntemler `multiplicative` karşısında anlamlı biçimde üstün.

---

## 2. Asya Handikabı (Tam / Yarım / Çeyrek Hat) Kesin Sıfır-EV Fiyatlaması ve Minimum-KL Skor Matrisi Rakingi

- **Kod:** `src/quantfoot/markets/tail_goals.py` (`_ah_payoff_weights`, `matrix_ah_outcomes`, `matrix_ah_home_win_share`,
  `fit_tail_rates_from_markets(..., ah_lines=...)`, `rake_score_matrix_to_markets(..., ah_lines=...)`) ve
  `scripts/nesine_global.py` (`price_event` + `consensus`).
- **Kök neden ve matematiksel iyileştirme:**
  - `data/global_odds/latest/references.json` keskin Asya Handikabı (`ref["ah"]`) oranlarını zaten taşıyordu ancak
    `price_event` bunları skor matrisi uydurmasına ve IPF rakingine hiç bağlamıyordu.
  - Çeyrek hatlarda (`-0.25`, `-0.75`, `-1.25`, `+0.75`, ...) bahis iki komşu hatta %50/%50 bölünür. Her skor hücresi
    $(h, a)$ için ev/deplasman kazanma ağırlıkları $w_H(h,a), w_A(h,a) \in \{0, 0.5, 1\}$ tanımlandığında sıfır-EV
    adil ev olasılığı tam olarak:
    $$p_H^{\text{adil}} = \frac{\mathbb{E}[w_H]}{\mathbb{E}[w_H] + \mathbb{E}[w_A]}$$
    olur. `rake_score_matrix_to_markets`, 1X2 ile örtüşen $|\text{AH}| \le 0.5$ hatlarını çakışma olmaması için atlar,
    **$|\text{AH}| \ge 0.75$ hatlarını** ise tam/yarım hatlarda koşullu ölçekleme, çeyrek hatlarda ise
    $M_{\text{yeni}} \propto M \exp(\eta [(1 - p_H) w_H - p_H w_A])$ (Csiszár minimum-KL I-projeksiyonu) ile skor
    matrisine kilitler.

### Gerçek Veri Doğrulaması (`season_2627/*.csv`, Betfair Exchange kapanış `$|\text{AH}| \ge 0.75$`, `n = 795`)

| Türev Pazar | Taban Log-Loss (1X2+O/U) | AH-Raked Log-Loss | $\Delta$ Log-Loss | Taban Brier | AH-Raked Brier | $\Delta$ Brier |
|---|---:|---:|---:|---:|---:|---:|
| **`Hnd(-1) 1`** | 0.550677 | **0.549503** | **−0.001174** | 0.189783 | **0.189251** | **−0.000532** |
| **`KG Var`** | 0.674793 | **0.674141** | **−0.000652** | 0.240957 | **0.240645** | **−0.000312** |
| **`3.5 Üst`** | 0.660816 | **0.660662** | **−0.000155** | 0.234253 | **0.234168** | **−0.000085** |
| **`Dep 1.5 Üst`** | 0.576567 | **0.576430** | **−0.000137** | 0.195577 | **0.195539** | **−0.000038** |
| **`Ev 1.5 Üst`** | 0.595526 | **0.595487** | **−0.000039** | 0.203532 | **0.203513** | **−0.000018** |
| `1.5 Üst` | 0.446852 | 0.447284 | +0.000432 | 0.138195 | 0.138343 | +0.000148 |
| `Hnd(+1) 2` | 0.301904 | 0.302430 | +0.000525 | 0.092362 | 0.092595 | +0.000233 |

- **Sonuç:** 7 türev pazarın 5'inde (özellikle `Hnd(-1) 1` ve `KG Var`) örneklem dışı iyileşme ve 7 pazar toplamında
  **−0.00120 Log-Loss** kazancı elde edildi.

---

## 3. Keskin Veri Kaynağı Genişletmesi ve Sıfır Ek Kotalı Doğrudan Türev Pazarlar

- **Kod:** `src/quantfoot/data/sharp_sources.py`, `src/quantfoot/data/api_football.py`, `scripts/nesine_global.py`, `.env.example`.
- **Neler eklendi:**
  1. **The Odds API v4 bağlayıcısı (`THE_ODDS_API_KEY`):** Ayarlandığında canlı Pinnacle, Betfair Exchange, Matchbook
     ve Smarkets 1X2 (`h2h`), çoklu Alt/Üst (`totals`) ve Asya Handikabı (`spreads`) oranlarını çeker; anahtar yoksa
     sessizce boş liste döner.
  2. **Yerel `football-data` `fixtures.csv` ayrıştırıcısı (`load_football_data_fixtures`):** Pinnacle ve Betfair
     Exchange 1X2 + 2.5 Alt/Üst + Asya Handikabı kayıtlarını tazelik denetimiyle (`reference_age_hours`,
     `filter_fresh_references`) doğrudan bülten biçimine çevirir.
  3. **API-Football `/odds` genişletmesi (sıfır ek kota):** Aynı `/odds` yanıtından artık yalnız 1X2 ve 2.5 Alt/Üst
     değil; `1.5/2.5/3.5/4.5 Alt/Üst`, `KG Var/Yok`, `Asya Handikabı`, `İY 0.5/1.5 Alt/Üst` ve `İY 1X2` doğrudan
     marjsız kotasyon olarak `direct_probabilities()` hattına aktarılır.

---

## 4. Nicel T-60 Kadro Şoku (`Δμ`), Üstel NPxG Profili, Hakem ve Motivasyon Motoru

- **Kod:** `src/quantfoot/markets/lineup_xg.py` ve `src/quantfoot/markets/market_diagnosis.py` (opsiyonel bağlam sinyalleri).
- **Çift-sayımı önleme kuralı (`news_fresher_than_odds`):**
  - 2026/27 sezonunun `HxG`/`AxG` kayıtları üzerinde katı kronolojik walk-forward testinde (`n = 1.015`,
    `arsiv_kod/v8_dogrulama.py`), salt tarihsel xG modelinin Betfair Exchange kapanış 1X2'sine karşı optimal log-opinion-pool
    ağırlığı **`w = 0.0000`** çıktı (`piyasa log-loss = 0.961450`, `model = 1.008288`).
  - Bu kanıt nedeniyle `compute_lineup_shock`, haber keskin oran çekiminden **önce** zaten fiyatlandıysa
    (`news_fresher_than_odds=False`) keskin $(\mu_{\text{ev}}, \mu_{\text{dep}})$ değerlerini **asla değiştirmez**,
    yalnız teşhis bayraklarını üretir. Yalnız T-60 kadro açıklaması keskin oran çekiminden **sonra** düştüğünde
    (`news_fresher_than_odds=True`), kaleci (+%6 rakip xG), gol kralı (−%4 ila −%10 kendi xG) ve ek as oyuncu
    eksiklerini **±%12 tavan** içinde uygular.
- **Hakem ve Motivasyon:** `build_referee_profiles` 2026/27 verisinde `n ≥ 5` maç yöneten **126 hakemi** profilledi
  (ör. `L Doughty: 6.00 kart/maç, z=+2.46`, `B Toner: 5.50 kart/maç, z=+2.38`, `J Brooks: 0.57 kırmızı/maç, z=+2.28`).
  `market_diagnosis.py` içinde `dead_rubber=True` veya `referee_card_zscore >= 2.0` açıkça verildiğinde ilgili Alt / KG Yok
  ve hedefsiz maç tuzakları ek risk koruması altına alınır.

---

## 5. Sistematik CLV Anlamlılık, Brier MCB/DSC Ayrıştırması ve Güvenli Kalibrasyon Önericisi

- **Kod:** `src/quantfoot/evaluation/clv_tracker.py` ve `scripts/clv_analiz.py`.
- **Özellikler:**
  - `compute_clv` ve `clv_significance`: Student-t, tek yönlü p-değeri, deterministik 2.000-tekrarlı bootstrap %95 GA ve
    %95 güç için gereken örneklem büyüklüğü (Kaunitz et al. 2017).
  - `brier_decomposition`: Tam Murphy / Dimitriadis (2023) `Brier = MCB − DSC + UNC` ve `ECE` ayrıştırması.
  - `optimal_log_pool_weight`: Herhangi bir modelin kapanış keskin piyasasına gerçekten yeni bilgi ekleyip eklemediğini
    ölçen log-opinion-pool testi.
  - `propose_family_calibration_update`: James-Stein büzüştürmeli (`prior_n=150`, `min_n=40`), **yalnız negatif**
    artık uygulayan, üretim kalibrasyon dosyalarını otomatik ezmeden denetlenebilir öneri üreten güncelleme motoru.
- **`data/tipsaudit.csv` (`n = 7.349`) CLV Bulgusu:** Ham isabet oranı `%72.3` görünse de ortalama CLV **`−%0.92`**
  (`t = −19.06`, %95 GA `[−%1.02, −%0.83]`) çıktı; açılış Pinnacle fiyatının kapanış Pinnacle'a karşı log-pool ağırlığı
  yalnız `w = 0.041` (`+0.000007` log-loss). Bu sonuç, ham isabet oranı yerine **CLV ve Brier MCB/DSC** takibinin
  zorunluluğunu sayısal olarak kanıtlar.

---

## 6. CORP İzotonik Güvenilirlik ve Kutusuz (Bin-Free) MCB/DSC Ayrıştırması (v8.5)

- **Kod:** `src/quantfoot/evaluation/clv_tracker.py` (`pav_isotonic`, `corp_reliability_decomposition`, `CORPDecomposition`) ve `scripts/clv_analiz.py`.
- **Matematiksel temel (Dimitriadis, Gneiting & Jordan 2021/2023):**
  - Sabit kutulu (10-bin) güvenilirlik diyagramları kutu genişliğine duyarlıdır. `pav_isotonic`, $O(n)$ Pool-Adjacent-Violators
    algoritmasıyla izotonik koşullu olay olasılıklarını ($\text{CEP} = \text{PAVA}(y \mid p)$) hesaplar ve tam özdeşliği sağlayan
    kutusuz ayrıştırmayı üretir:
    $$\text{MCB} = S(p, y) - S(\text{CEP}, y) \ge 0, \qquad \text{DSC} = S(\bar{y}, y) - S(\text{CEP}, y) \ge 0, \qquad \text{Brier} \equiv \text{MCB} - \text{DSC} + \text{UNC}$$
- **Gerçek Veri Doğrulaması (Ev sahibi 1X2):**
  - **Pinnacle kapanış (`data/tipsaudit.csv`, `n = 7.349`):** `ensemble` en düşük `CORP MCB` (**`0.001447`** vs `multiplicative` `0.001765`, **%18 daha az kalibrasyon hatası**), `goto` ise en düşük `CORP ECE` (**`0.01826`**) ve en yüksek `CORP DSC` (**`0.028519`**) değerini verdi.
  - **Betfair Exchange kapanış (`season_2627/*.csv`, `n = 2.449`):** `ensemble` en düşük `CORP MCB` (**`0.002812`** vs `multiplicative` `0.002920`), `goto` en düşük `CORP ECE` (**`0.025945`**) ve en yüksek `CORP DSC` (**`0.033072`**) değerini verdi.

---

## 7. Keskin–Yumuşak (Sharp-vs-Soft) Gecikme ve Steam Yönü Motoru (v8.5)

- **Kod:** `src/quantfoot/markets/line_movement.py` (`analyze_line_movement`, `sharp_soft_edge`, `backtest_sharp_soft_and_steam`) ve `scripts/clv_analiz.py --steam`.
- **Gerçek Veri Doğrulaması (`data/tipsaudit.csv`, `n = 7.348` maç, açılış Pinnacle Power-devig vs `best_soft_*`, maç başına en fazla 1 bacak):**

| Filtre / Kırılım | n | Düz 1u ROI | İsabet % | Kapanış CLV | Student-t | p (tek yön) |
|---|---:|---:|---:|---:|---:|---:|
| Sharp–Soft `EV ≥ %1` | 3.515 | +3,28% | %40,2 | +4,00% | +1,30 | 0.0973 |
| Sharp–Soft `EV ≥ %2` | 2.960 | +3,97% | %39,7 | +4,74% | +1,42 | 0.0779 |
| Sharp–Soft `EV ≥ %3` | 2.456 | +5,08% | %39,2 | +5,71% | +1,62 | 0.0529 |
| **Sharp–Soft `EV ≥ %5`** | **1.705** | **+6,57%** | %37,9 | **+7,43%** | **+1,67** | **0.0472** |
| `EV ≥ %2` · **Steam Uyumlu (`≥ +2p`)** | **469** | **+19,18%** | **%49,7** | **+20,42%** | **+2,85** | **0.0023** |
| `EV ≥ %2` · Steam Nötr (`−2p..+2p`) | 1.600 | +7,45% | %39,1 | +6,52% | +1,86 | 0.0316 |
| `EV ≥ %2` · **Steam Karşıtı (`≤ −2p`)** | **891** | **−10,28%** | %35,4 | **−6,72%** | **−2,21** | 0.9863 |

- **Sonuç:** Keskin açılış-kapanış hareketiyle **uyumlu** yumuşak-büro fırsatları **+%19,18 ROI** (`p = 0.0023`) üretirken,
  keskin piyasanın **tersine** düşen aynı `EV ≥ %2` adayları **−%10,28 ROI** ile net zarar yazmaktadır.

---

## 8. Uyarlamalı Drawdown-Frenli Kelly ve Canlı Hat Bağlantısı (v8.5)

- **Kod:**
  - `src/quantfoot/strategy/kelly.py` (`adaptive_kelly_stake`): Zirveden düşüş (drawdown) büyüdükçe Kelly çarpanını yumuşakça
    `min_drawdown_scale` (%25) düzeyine indirir; günlük **%5**, haftalık **%12** kayıp ve **%25** toplam drawdown devre
    kesicileriyle bahsi otomatik durdurur, Baker–McHale parametre belirsizliği büzüştürmesi (`prob_std`) uygular.
  - **Canlı hat bağlam bağlantısı:** `scripts/nesine_global.py` (`attach_research` → `motivation_regime`),
    `scripts/nesine_kupon.py`, `scripts/derin_tahmin.py` ve `src/quantfoot/evaluation/self_improve.py` (`_build_diag_ctx`,
    `scripts/kasa_koruma.py` tarafından doğrudan kullanılır) artık `dead_rubber` ve `referee_card_zscore` sinyallerini
    uçtan uca `diagnose_selection` kalkanına taşır.
- **Tekrarlanabilir Monte Carlo Doğrulaması (`arsiv_kod/v8_dogrulama.py`, 400 yol × 250 bahis, +%2,5 gerçek kenar, ±%2,5 tahmin gürültüsü, 1.000 TL başlangıç):**

| Strateji | Ortanca Maks. Düşüş | %95-Dilim Maks. Düşüş | `DD ≥ %25` İhlal Oranı | %5-Dilim Kuyruk Kasa | Ortanca Kasa |
|---|---:|---:|---:|---:|---:|
| Sabit Çeyrek-Kelly | %16,65 | %33,54 | %17,5 | 742,11 TL | 1.060,52 TL |
| **`adaptive_kelly_stake`** | **%11,38** | **%17,84** | **%0,0** | **854,55 TL** | 1.019,54 TL |

---

## 9. Komutlar ve Test Doğrulaması

```bash
# Tüm v8 + v8.5 ampirik doğrulama tablosunu yeniden üret (gerçek veri üzerinde):
PYTHONPATH=src python arsiv_kod/v8_dogrulama.py

# CLV + Devig + CORP izotonik güvenilirlik + Sharp-Soft & Steam yönü denetimi:
PYTHONPATH=src python scripts/clv_analiz.py --tipsaudit --steam
QUANTFOOT_AI=<klasörün> PYTHONPATH=src python scripts/clv_analiz.py --kendi-kalibrasyon
```
