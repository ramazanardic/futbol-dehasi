# QuantFoot v4 — Kantitatif Futbol Tahmin ve Bahis Algoritması

Akademik literatür (Dixon & Coles; Koopman & Lit; Wheatcroft; Duffield, Power & Rimella JRSS-C 2024; Baker & McHale; Constantinou & Fenton) ve **238.858+ tarihsel kulüp maçı** (`matches.csv` + canlı ESPN 2026-27 senkronizasyonu) + **10.660 uluslararası milli maç** (2016–2026) + **7.348 Pinnacle 2026 açılış/kapanış oran verisi** üzerinde sıfır veri sızıntısı (*zero look-ahead leakage*, genişleyen *walk-forward*) ile araştırılmış, kalibre edilmiş ve doğrulanmış kantitatif futbol tahmin ve bahis motoru.

---

## Araştırma Bulguları ve v4 Yükseltmeleri (Ampirik Kanıtlar)

1. **Doğru Skorlama Kuralları & v4-Pyramid Expanding Süper Topluluk (*cal=9.629 -> genişleyen, n_test=16.423, 2021–2026, 9 lig*):**
   - **L2-Düzenlileştirilmiş Kronolojik OOF Simplex + Sezonluk Genişleyen Yeniden Eğitim (*Expanding Yearly Causal Refit*):** 10 alt-modelin ağırlıkları (`gap_ordered=0.204`, `gap_elo=0.187`, `lgbm=0.151`, `kalman=0.107`, `mlp=0.102`, `pyramid_rating=0.096`, `gas_poisson=0.051`, `pi=0.049`, `dc_goals=0.034`, `dc_hybrid=0.020`, `Temperature=0.939`) COVID seyircisiz sezon ağırlıklandırması (`0.55x`) ve yumuşak zaman azalmasıyla sıfır sızıntıyla optimize edilmiştir.
   - **V4-Pyramid Expanding (Calibrated):** `LogLoss = 0.98305 | RPS = 0.19955 | Brier = 0.58602 | ECE = 0.00717` (v1 `0.98789`, v2 `0.98640`, v3 `0.98631` modellerinin tamamını geride bıraktı; `ECE=0.00717` kalibrasyon hatası `Market B365 Power`'ın `0.00978` skorundan dahi düşüktür).
   - **Lig Piramidi Terfi/Küme Düşme Taşıması (`pyramid.py` + `E3/E2/E1/E0, SP2/SP1, D2/D1, I2/I1, F2/F1`):** Alt liglerden gelen takımlara katman merkezi regresyonu uygulanarak:
     - `Pyramid Causal Elo`: `LogLoss = 0.98825 | RPS = 0.20106 | ECE = 0.00964` (harici `ClubElo` `0.99153` referansını geçti).
     - `Pyramid Glicko-2`: `LogLoss = 0.98901 | RPS = 0.20135 | ECE = 0.00648` (en düşük kalibrasyon hatası).
     - `Pyramid Pi-Ratings`: `LogLoss = 0.99077 | RPS = 0.20192 | ECE = 0.00716`.
   - **Tier-Aware GAP + Oyun-Durumu Düzeltilmiş xG (`OrderedLogit3Class`):** Devre arası skor (`HTHome/HTAway`) sönümlemeli nedensel xG vekili ve `H < D < A` sıralı eşik yapısıyla tekil doğrusal model olarak `LogLoss = 0.98358 | RPS = 0.19968 | ECE = 0.00708` elde etti.
   - **Laplace-Kalman Durum-Uzayı Poisson (`KalmanPoissonModel`):** Takım hücum/savunma belirsizlik kovaryansını (`P_att`, `P_def`), terfi/sezon-arası belirsizlik sıçramasını ve dinamik `mu0 / HFA` parametrelerini gol + xG + SOT üzerinden günceller (`LogLoss = 0.99482`, `ECE = 0.01351`).
   - **Dixon-Coles Hybrid (`Goals + 0.25 * GS_xG`):** Standart `Dixon-Coles Goals` (`0.99487`) üzerine `0.25` oyun-durumu xG ağırlığıyla `LogLoss = 0.99284 | RPS = 0.20239` skoruna iyileşti.
2. **Çapraz-Pazar Marj Temizleme (`AH + O/U -> Fair 1X2`) ve Gerçek +EV Bulguları:**
   - Bet365 Asya Handikap (`3.27%` vig) marjı `1X2` (`5.34%`) ve `O/U 2.5` (`5.24%`) pazarlarından neredeyse yarı yarıya daha keskindir; `invert_ah_ou_1x2` çıkarımı tek başına **`LogLoss = 0.97224 | RPS = 0.19619 | ECE = 0.00996`** üretir.
   - **`Cross-Mkt (70% 1X2+30% AH/OU) vs MaxBook (EV>=1.5%)`:** `1.254` bahis, **`+7.32%` flat ROI (`t = +2.08`, `p = 0.0186`)**, Çeyrek-Kelly ile `MaxDD = 19.8%` (`Market-Power vs MaxBook` tekil `+5.10%` / `DD = 26.4%` stratejisinden hem daha yüksek ROI hem daha düşük düşüş).
   - **`Joint Multi-Market Portfolio (1X2 + O/U 2.5)`:** Aynı maçta `0.85` korelasyon sönümlemesi + `Baker-McHale Kelly` ile `2.349` bahis, `win = 0.539`, **`+4.98%` flat ROI (`t = +2.29`, `p = 0.0109`)**, `$1,000 -> $1,730.48` (`MaxDD = 22.8%`).
3. **2026 Pinnacle Açılış vs Yumuşak Büro & Walk-Forward ML CLV Filtresi (`n = 7.348`):**
   - `Pin Open vs BestSoft (Base)` (`EV>=2.5%, O<=4.0`): `2.112` bahis, `+5.07%` flat ROI (`t=+1.85, p=0.0324`), `+5.57%` CLV, `Kelly = $7,263.37` (`MaxDD = 50.2%`).
   - **`Pin Open High-Liq (Books>=12, O<=3.5)`:** `1.457` bahis, **`+6.49%` flat ROI (`t = +2.09`, `p = 0.0183`)**, `+5.21%` CLV, `Kelly = $3,225.40` (`MaxDD = 26.6%`).
   - **`Pin Open WF CLV-ML Filter (P_hold >= 0.70, O<=3.5)` (`CLVPreservationFilter`):** Kapanış çizgisi değerinin (`CLV > 0`) korunacağını piyasa mikro-yapısından öngören nedensel walk-forward LGBM filtresi ve Baker-McHale Kelly boyutlandırmasıyla `1.052` bahis, `win = 0.495`, **`+8.77%` flat ROI (`t = +2.41`, `p = 0.0081`)**, **`+7.53%` CLV**, `Kelly = $2,735.38` (`MaxDD = 32.3%`).
4. **QuantFoot-v5 Kuyruk Golü (`Over 5.5 / 6+`) & Yarı-Devre `KG` Yükseltmeleri (`184.276` İY+MS & `34.463` Holdout Test `2022–2026`):**
   - **Çift Rejimli Skor Matrisi (`tail_goals.py`):** Kulüp liglerinde `COM-Poisson (nu = 1.10)` ile standart Poisson'u aynı anda `5+` (`LL 0.39055 -> 0.39041`), **`6+` (`LL 0.21304 -> 0.21279`, `%5.84` vs gerçek `%5.81`)** ve **`BTTS` (`LL 0.68621 -> 0.68563`)** pazarlarında geçti; `49.940` milli maçta gözlenen yüksek varyans (`Var/Mean = 1.286`) nedeniyle milli/genç/kadın turnuvalarında ise Gamma-Poisson aşırı dağılım rejimi (`15x15` matris) korundu.
   - **Devre Bazlı İlişkili `KG` (`halves_btts.py`):** `184.276` maçta küresel ilk yarı gol payı `0.4403` ölçüldü; **FGM Copula (`fgm_1h`) + Gauss-Laguerre tempo integrasyonu (`match_kappa`)** `34.463` örneklem dışı maçta `1Y KG` (`LL 0.48771 -> 0.48756`), `2Y KG` (`LL 0.56894 -> 0.56891`) ve `1Y+2Y KG` (`LL 0.20363 -> 0.20359`) skorlarını iyileştirdi.
   - **Genişletilmiş Değer Tarayıcı (`strategy/value.py`):** `BTTS`, `Alt-O/U (3.5 / 4.5 / 5.5)` ve `evaluate_halves_btts_value` (`1H / 2H / Both-Halves BTTS`) entegrasyonu (`28 passed` birim testi).

---

## Paket Yapısı

- `src/quantfoot/data/` — Veri indirici/temizleyici (`loader.py`), canlı ESPN Kulüp + UCL + Milli maç tarayıcı/senkronizasyon & Open-Meteo/The Odds API bağlayıcıları (`live_espn.py`), nedensel Box-Score xG vekili (`xg_proxy.py`).
- `src/quantfoot/markets/` — `Power`, `Shin`, `Odds Ratio`, `Multiplicative` devig çözücüleri (`devig.py`); `1X2`, `Çifte Şans`, `O/U`, `KG Var/Yok`, `Skellam`, çeyrek-top (`.25 / .75`) Asya Handikap fiyatlama ve `invert_ah_ou_1x2` çapraz-pazar çözücüsü (`pricing.py`); çift rejimli `COM-Poisson + Gamma-Poisson` `6+` kuyruk golü motoru (`tail_goals.py`); küme tutarlı FGM Copula + Gauss-Laguerre yarı-devre `KG` motoru (`halves_btts.py`).
- `src/quantfoot/models/` — Piramit katman regresyonu (`pyramid.py`), `KalmanPoissonModel` (`kalman.py`), `FootballGlicko2` (`glicko2.py`), `OrderedLogit3Class` (`ordinal.py`), `TimeDecayedDixonColes` (`dixon_coles.py`), Dual-Signal `GASPoissonModel` (`gas_poisson.py`), `WheatcroftGAPRatings` (`gap_ratings.py`), `weibull_copula`, `DiagonalBivariatePoisson`, `CausalRatingEngine` (`ratings.py`), `FundamentalEnsemble` (10-model L2 OOF Simplex + MLP + LightGBM + Temperature / Dirichlet ODIR).
- `src/quantfoot/strategy/` — `CLVPreservationFilter` (`clv_filter.py`), +EV değer tarayıcı (`value.py`: `1X2`, `O/U`, `AH`, `BTTS`, `1H/2H/Both-Halves BTTS`) ve Baker-McHale / Çeyrek-Kelly / Korelasyonlu Portföy Kelly (`kelly.py`).
- `src/quantfoot/evaluation/` — `RPS`, `Log-Loss`, `Brier`, `ECE`, genişleyen piramit walk-forward backtester (`backtest.py`) ve grafik raporlama (`reporting.py`).

---

## Kullanım

```powershell
# 1. Tam walk-forward v4 backtest + grafikler
.\.venv\Scripts\quantfoot.exe backtest --report-dir reports

# 2. Tekil maç analizi (canlı ESPN 2026-27 Süper Lig / Premier Lig senkronizasyonlu)
.\.venv\Scripts\quantfoot.exe analyze --league T1 --home Galatasaray --away Fenerbahce `
  --odds 2.15 3.40 3.30 --sharp-odds 2.02 3.45 3.65 --ou25 1.85 2.00 --ah -0.25 1.88 2.02

# 3. Canlı günlük Milli + Avrupa Kulüp Ligleri + Şampiyonlar Ligi bülteni & +EV portföyü
.\.venv\Scripts\quantfoot.exe slate --mode all --dates 20261116 20261117 --fund-weight 0.25 --min-ev 0.02

# 4. Korelasyonlu portföy Kelly optimizasyonu
.\.venv\Scripts\quantfoot.exe portfolio --bets-json examples/matchday_portfolio.json --bankroll 1000

# 5. Birim testler
.\.venv\Scripts\pytest.exe -v
```
