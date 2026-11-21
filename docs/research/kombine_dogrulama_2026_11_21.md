# Kombine politikası — örneklem-dışı doğrulama (21 Kasım 2026)

Üretim: `python scripts/kombine_dogrulama.py`. Sonuçlar gerçek maç sonuçlarıyla; güven aralığı gün-kümeli bootstrap.

## A. Marj bileşikleşmesi — `data/matches.csv` 2021-07+ (15483 favori bacak, medyan 1X2 marjı 6.4%)

Bacak: marjsız olasılığı ≥ %55 ve oranı ≥ 1.20 olan favori, ortalama piyasa oranından. Aynı günden rastgele k maç.

| Bacak | Kupon | Tutma | ROI (%95 GA) |
|---|---|---|---|
| 1 | 45540 | 64.6% | -2.6% (-4.6% – -0.4%) |
| 2 | 39780 | 42.5% | -2.7% (-6.2% – +1.1%) |
| 3 | 34830 | 27.2% | -6.0% (-11.6% – -0.3%) |
| 4 | 30750 | 17.4% | -7.9% (-14.8% – -0.4%) |
| 5 | 27150 | 10.8% | -14.1% (-23.6% – -4.5%) |
| 6 | 24240 | 7.0% | -15.7% (-27.7% – -3.6%) |
| 7 | 21720 | 4.8% | -12.2% (-28.7% – +6.3%) |
| 8 | 19080 | 3.1% | -17.5% (-35.7% – +2.1%) |
| 9 | 17640 | 2.1% | -20.3% (-40.9% – +5.5%) |

## B. Politika — `data/tipsaudit.csv` (7349 maç, olasılık = Pinnacle açılışı marjsız, oran = en iyi yumuşak büro)

**Önce (EV'ye bakmadan favori biriktirmek, aynı günden rastgele k maç):**

| Bacak | Kupon | Tutma | Ortalama ex-ante EV | ROI (%95 GA) |
|---|---|---|---|---|
| 1 | 3840 | 70.6% | +1.1% | +10.4% (+4.6% – +16.4%) |
| 2 | 3450 | 46.1% | +2.6% | +14.3% (+1.8% – +28.0%) |
| 3 | 3150 | 30.7% | +3.6% | +19.4% (-2.7% – +42.1%) |
| 4 | 2820 | 18.4% | +5.2% | +16.7% (-12.2% – +51.2%) |
| 5 | 2700 | 13.3% | +6.3% | +35.5% (-7.6% – +90.2%) |
| 6 | 2430 | 9.9% | +7.5% | +48.0% (-6.7% – +110.3%) |
| 7 | 2310 | 7.1% | +7.9% | +60.4% (-14.6% – +160.2%) |

**Sonra (accumulator_policy: bacak EV ≥ 2.5%, günde en çok 3 kupon, aynı maç tek kuponda):**

| En çok bacak | Kupon | Ort. bacak | Tutma | Ortalama ex-ante EV | ROI (%95 GA) |
|---|---|---|---|---|---|
| 1 | 348 | 1.00 | 46.8% | +11.0% | +8.1% (-5.5% – +21.8%) |
| 2 | 321 | 1.91 | 29.0% | +19.3% | +33.6% (+8.2% – +60.2%) |
| 3 | 294 | 2.77 | 16.7% | +27.3% | +43.5% (-2.2% – +95.1%) |
| 4 | 279 | 3.41 | 13.3% | +34.1% | +31.6% (-22.7% – +98.2%) |

Çekinceler: tipsaudit'teki 'en iyi yumuşak oran' ~17 büronun en iyisidir (tek büroda yok) ve alınma anı bilinmiyor; Nesine marjı bu bürolardan yüksektir, dolayısıyla gerçek Nesine ROI'si daha düşük olur. Deney B'deki ROI'ler 5 aylık tek bir dönemdir.
