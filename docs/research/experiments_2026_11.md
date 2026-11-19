# Deney Sonuçları (Kasım 2026) — sistemde gerçekten avantaj nerede?

Hepsi örneklem dışıdır ve `scripts/research_experiments.py` ile yeniden üretilebilir; ham çıktılar
`reports/research/` altındadır.

## 1. Modeller piyasaya bilgi katıyor mu? — Hayır

`research_experiments.py cache` + `pool` · ayrıntı: [pooling_test.md](../../reports/research/pooling_test.md)

İleri-yürüyen backtest (her sezon yalnızca önceki verilerle yeniden eğitim), 16.423 test maçı,
9 lig, 2021-08 – 2026-09. Model ile Bet365'in marjsız fiyatı logaritmik havuzda birleştirildi.

- **15 modelin tamamında havuz ağırlığı w = 0.00** (%95 GA 0.00 – 0.00; en geniş: GAP-Elo 0.00 – 0.01).
- Log-loss: piyasa **0.97211**; en iyi model (kalibre topluluk) 0.98305.
- Sezon sezon: hiçbir sezonda güven aralığı sıfırdan ayrışmıyor.

Bu, Pitcan (2026, arXiv:2608.11505) bulgusunun bu repo verisinde bağımsız tekrarıdır. README'deki
"ECE piyasadan düşük" bulgusu doğrudur ama bahis için önemsizdir: piyasa daha keskindir (daha iyi ayırt eder).

**Sonuç:** Temel (fundamental) modellerin olasılığına göre "değer" aramak avantaj sağlamaz.

## 2. Dinlenme günü piyasanın ötesinde bilgi taşıyor mu? — Pratikte hayır

`research_experiments.py rest` · ayrıntı: [rest_days.md](../../reports/research/rest_days.md)

51.245 test maçı (2021-07+). Piyasa logitlerine dinlenme özellikleri eklenince maç başı log-olabilirlik
kazancı +0.00009 (%95 GA +0.00003 – +0.00016): istatistiksel olarak anlamlı ama log-loss
1.00123 → 1.00114 gibi ihmal edilebilir. Kupa / Avrupa maçları veri setinde olmadığı için kısa
dinlenme eksik ölçülüyor; daha iyi fikstür verisiyle tekrar edilebilir.

## 3. Keskin–yumuşak oran farkı — Evet, güçlü kanıt

`research_experiments.py sharp-soft` · ayrıntı: [sharp_soft.md](../../reports/research/sharp_soft.md)

`tipsaudit.csv`, 7.348 maç (2026-06 – 2026-10). Kural: marjsız Pinnacle açılış olasılığı × en iyi
yumuşak oran − 1 ≥ eşik.

| EV eşiği (oran ≤ 3.5) | Bahis | ROI (%95 GA) | Adil CLV (%95 GA) |
|---|---|---|---|
| %0 | 3.668 | +4.0% (+0.4 – +7.6) | +3.5% (+3.1 – +3.7) |
| %2.5 | 2.067 | +7.6% (+2.5 – +12.8) | +5.5% (+5.1 – +6.0) |
| %5 | 1.198 | +12.4% (+5.5 – +19.4) | +7.8% (+7.2 – +8.5) |

Yalnızca geleneksel bürolar (borsalar hariç, eşik %2.5): 1.954 bahis, ROI +6.7% (+1.6 – +12.0),
adil CLV +5.6%.

**Çekinceler:** (a) "en iyi yumuşak oran" ~17 büronun en iyisi; tek bir büroda bu fiyatlar yok.
(b) Yumuşak oranların hangi anda alındığı veride yok; seçilen oranların medyanı Pinnacle kapanışının
%9.9 üstünde — eski / limitli fiyatlar içeriyor olabilir. (c) Kazanan hesaplar kısıtlanır
(Kaunitz ve ark. 2017). (d) Yalnızca yaşadığın yerde yasal olan bürolarla oynanmalı.

Canlı uygulama: `scripts/sharp_scan.py` (The Odds API anahtarı gerekir) ve kendi büronun oranlarını
Pinnacle'a karşı kontrol etmek için `sharp_scan.py check --my-odds`.

## 4. Türev pazarların kalibrasyonu (piyasaya sabitlenmiş motor)

`research_experiments.py derivative` · ayrıntı: [derivative_calibration.md](../../reports/research/derivative_calibration.md)

12.000 rastgele maç (2022-07+). Gol beklentisi Bet365 marjsız 1X2 + 2.5 Alt/Üst'e uydurulup türev
olasılıklar ortak tensörden hesaplandı. Piyasanın kendisi kalibre (2.5 Üst: piyasa %50.9, gerçekleşen
%51.4), ama motor **sistematik olarak az gol** öngörüyordu:

| Pazar | Motor | Gerçekleşen |
|---|---|---|
| KG Var | %48.1 | %53.1 |
| 3.5 Üst | %24.0 | %29.4 |
| Dep 0.5 Üst | %64.9 | %69.3 |
| Skor 0-0 | %8.3 | %6.9 |
| Skor 1-1 | %12.9 | %11.5 |

İY/MS ve İY sonucu pazarları ise iyi kalibre (ECE 0.006 – 0.02). Neden: kulüp rejimindeki COM-Poisson
ν = 1.10 (aşırı dar gol dağılımı) ve Dixon-Coles ρ = −0.07 (0-0 ve 1-1'i şişirir). Yeniden kalibrasyon:
bkz. §5.

## 5. Gol dağılımı rejiminin yeniden kalibrasyonu

`research_experiments.py calibrate-regime` · ayrıntı: [regime_calibration.md](../../reports/research/regime_calibration.md)

ν (COM-Poisson) × ρ (Dixon-Coles) × κ (ortak tempo) ızgarası yalnızca kalibrasyon döneminde
(2019-07 – 2022-07, 2.500 maç) tarandı; en iyisi **ν = 1.0, ρ = −0.03, κ = 0** (eski: 1.10 / −0.07 / 0).
Bağımsız test (2022-07+, 6.000 maç) — her satırda iyileşme:

| Pazar | Gerçekleşen | Eski | Yeni |
|---|---|---|---|
| KG Var | %52.8 | %48.1 | %51.3 |
| 3.5 Üst | %28.7 | %24.0 | %29.1 |
| 4.5 Üst | %13.3 | %10.5 | %14.4 |
| Dep 0.5 Üst | %69.4 | %65.0 | %68.0 |
| Skor 0-0 | %7.6 | %8.3 | %7.4 |

Toplam test log-loss 4.611 → 4.554. Motora uygulandı (`tail_goals.CLUB_REGIME`, `DEFAULT_RHO`).
README'deki "ν = 1.10 kulüp rejimi" bulgusu bu sabitlenmiş kullanımda geçerli değil.
