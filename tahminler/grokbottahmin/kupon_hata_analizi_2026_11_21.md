# Kupon hata analizi ve pazar kalibrasyonu — 21 Kasım 2026

Hazırlayan: Grok Bot. Dal: `grokbot/pazar-kalibrasyonu`.

Amaç: kaybettiren pazarları (2.5/3.5 Üst, KG Var, zayıf favori MS 1, skor, İY/MS) yasaklamak değil. Sistemin ve seçimlerin neden kaybettiğini bulup modeli düzeltmek.

Kaynaklar:
- `scripts/kupon_postmortem.py` → `kupon_postmortem.json` ve `kupon_postmortem_bacaklar.csv`
- `scripts/pazar_kalibrasyonu.py` → `reports/research/pazar_kalibrasyonu.md`

## 1. Kupon post-mortem

### Genel tablo

| Dönem | Kupon | Kazanan | Yatırılan | Dönen | ROI |
|---|---|---|---|---|---|
| Tüm kayıtlar (yanlı) | 179 sonuçlanmış | 10 | 25 232 TL | 12 615,49 TL | −%50,0 |
| Eksiksiz dönem: 20 Eki–10 Kas liste + 20–21 Kas detay | 172 | 4 | 24 235 TL | 7 444,47 TL | **−%69,3** (net −16 790,53 TL) |

Uyarı: 13–19 Kasım için yalnız kazanan kuponlar kayıtlı (7 kupon, 6 kazanan, 997 TL → 5 171 TL). Tüm kayıtlardaki ROI bu yüzden iyimser. Doğru ölçü eksiksiz dönemdir.

### Bacak sayısına göre (eksiksiz dönem)

| Bacak | Kupon | Kazanan | ROI |
|---|---|---|---|
| 1–2 | 16 | 0 | −%100 |
| 3–4 | 53 | 1 | −%76,5 |
| 5–6 | 46 | 2 | −%31,9 |
| 7–8 | 38 | 1 | −%70,9 |
| 9+ | 19 | 0 | −%100 |

### Toplam orana göre
- <3, 3–5, 10–20 ve 20–50 bantlarının hepsi −%100.
- 5–10: 72 kupon, 3 kazanan, −%61,1.
- ≥50: 19 kupon, 1 kazanan, +%166,7. Bu tek bir kupondan geliyor; örneklem çok küçük, anlamsız.

### Yapısal hatalar
- 181 kuponun 43'ü 7 bacaktan fazla.
- 20 kuponun toplam oranı ≥50.
- 1,20 altı oranlı 9 bacak var.
- 4,00 ve üstü oranlı 11 bacak var; **hiçbiri tutmadı**.
- Kupondaş'tan kopyalanan 7 kuponun hiçbiri kazanmadı.

### Tek bacakla kaybedilen kuponlar
Bacak detayı olan 20 kaybeden kuponun 5'i tek bacakla kaybedildi (bekleyen bacağı olmayan 4 tanesi). Kaybettiren bacaklar:
- Gamba Ev 0.5 Üst 2,37 (şüpheli eşleşme)
- Seongnam İY 1.5 Üst 2,21
- ES Setif MS1 1,42
- Jong Utrecht–Emmen 2.5 Üst 1,20
- Kashima KG Yok 1,48

### Korelasyonlu risk
32 maç en az 2 kuponda yer aldı. Örnekler:
- Molde–Bodø: 5 kupon, 580 TL
- Troyes–Le Havre: 4 kupon
- Volendam–Jong Ajax: 4 kupon
- Andorra–Leganés: 4 kupon

### Canlı bahis
- 13 bacak maç başladıktan sonra oynandı: 7 kaybetti, 4 tuttu, 2 bekliyordu.
- Bunlar fiyat karşılaştırmasının dışında tutuldu.

### Fiyat
- Global adil fiyatla eşleşen 40 maç-öncesi bacakta ortalama EV **−%16,4**.
- Nesine marjı ortalama ~%22 (21 Kasım verisi).
- Eşleme kapsamı: başlama saati bulunan 102 bacak, lig bulunan 93 bacak. Kalanlar CSV'de "eşleşmedi" diye işaretli.

### Aile bazında örtük (Nesine, marjsız) ve gerçek isabet

| Aile | n | Tutan | Gerçek | Örtük |
|---|---|---|---|---|
| MS 1 | 25 | 12 | %48 | %56,1 |
| 2.5 Üst | 19 | 12 | %63,2 | %59,2 |
| KG Var | 15 | 12 | %80 | %56,6 (p=0,074) |
| İY/MS | 14 | 4 | %28,6 | %28,6 |
| İY Gol Üst | 12 | 10 | %83 | %61 |
| MS 2 | 10 | 7 | %70 | %56,4 |
| MS 1 zayıf favori (1,70–2,30) | 7 | 3 | %42,9 | %45 |
| Bilinmeyen uzun atışlar (≥4) | 7 | 0 | %0 | %16,7 |
| 3.5 Üst | 6 | 4 | %66,7 | %54,4 |

Oran bandına göre:
- 1,70–2,29: 20 bacak, 6 tuttu (%30, örtük %42,9).
- ≥4,00: 0/11.
- <1,20: 4/8 (%50, örtük %74,9).

**Sonuç:** "Zor" pazarlar örtük olasılığın altında kalmıyor. Hiçbir fark p<0,05 değil ve örneklemler küçük (n=6–25). Kayıp pazar seçiminden değil şunlardan geliyor:
- Nesine marjı;
- çok bacaklı kuponlar;
- uzun atışlar;
- canlı bahis;
- aynı maça yığılma;
- kopya kuponlar.

## 2. Walk-forward kalibrasyon (sızıntısız)

Kurulum:
- 123 074 maç (2010-07-30 – 2026-11-16, 22 lig).
- Test: 2016+ sezonları, 77 519 maç. Kalibratör yalnız önceki sezonlarla kurulur.
- "Ham" = üretim hattı (marjsız 1X2 + 2.5 A/Ü → gol tensörü). 2.5 Üst ve MS 1 için ham değer doğrudan piyasanın marjsız olasılığıdır.
- Tutma kuralı: log-loss farkının %95 bootstrap güven aralığının (GA) tamamı 0'ın altında olmalı.

| Pazar | Gerçek | Ham ort. | Ham LL / Brier / ECE | Platt+lig − ham (LL) | Karar |
|---|---|---|---|---|---|
| 2.5 Üst | %50,3 | %50,1 | 0,67699 / 0,24208 / 0,0024 | +0,000072 [7e-06, 1,46e-04] | Tutulmadı (piyasa zaten kalibre) |
| 3.5 Üst | %28,1 | %28,5 | 0,57887 / 0,19591 / 0,0036 | +0,000109 [1e-05, 2,01e-04] | Tutulmadı |
| KG Var | %52,4 | **%50,7** | 0,68684 / 0,24687 / 0,0172 | **−0,000847 [−0,001144, −0,000532]** | **Tutuldu**. Brier 0,24645, ECE 0,0015 |
| MS 1 | %43,5 | %43,8 | 0,62619 / 0,21869 / 0,0042 | −0,000014 [−1,26e-04, 9,1e-05] | Tutulmadı |
| MS 1 zayıf favori (n=27 785) | %47,9 | %48,2 | 0,68802 / 0,24745 / 0,0026 | +0,000112 [−3,2e-05, 2,63e-04] | Tutulmadı (aşırı güven yok) |

### Lig bazında en büyük sapmalar (ham ortalama → gerçek)

**KG Var**, ham değerin gerçeğin altında kaldığı ligler:
- SP2: %44,5 → %48,4
- I2: %47,8 → %53,2
- I1: %50,5 → %54,0

KG Var'da ham değerin gerçeğin üstünde kaldığı lig:
- SC3: %54,8 → %52,3

**2.5 Üst:**
- SC3: %54,0 → %52,1
- SC1: %49,5 → %47,7
- D2: %54,9 → %56,5

**3.5 Üst:**
- SP1: %27,7 → %26,1
- G1: %22,7 → %21,4

**Zayıf favori MS 1:**
- SC1: %42,4 → %40,2
- I2: %43,3 → %41,4
- I1: %43,8 → %42,1

Bu sapmalar 1–2 puanlık ve lig başına n≈1 700–5 700. Lig kalibratörü yine de toplamda LL kazandırmadı. Tek istisna KG Var.

### Diğer denemeler
- **Form özelliği** (EWMA gol ve KG artığı): 2.5 Üst'te Platt+lig'e göre −0,000033 [−6,1e-05, −4e-06], ama yine de ham değerden kötü. KG Var'da +0,00001 ile zararlı. Tutulmadı.
- **Bağımsız istatistik modeli** (EWMA Poisson): LL piyasadan ~0,024 kötü.
- **Rotasyon / Avrupa kupası özelliği:** arşivde kupa fikstürü olmadığı için sınanamadı.

## 3. Yapılan değişiklikler

1. **KG Var/KG Yok Platt + lig kalibrasyonu.** Dosya: `data/calibration/market_calibration.json`, a=0,0686, b=0,879.
   - Yalnız türetilmiş (borsada doğrudan kote edilmeyen) seçimlerde uygulanır.
   - Etkisi: %45 → %47,3, %50 → %51,7, %60 → %60,5.
2. **Zor pazarlarda EV tabanı (yasak değil).** Kapsam: 2.5/3.5 Üst, KG Var, İY/MS, Skor ve 1,70–2,30 arası MS 1.
   - Kalibre olasılık × oran − 1 ≥ **+0,03** olmalı.
   - Belirsizlik payı (sigma) +0,010 artırılır.
   - Gerekçe (arşiv ROI vekili, Max fiyat): 2.5 Üst ham EV≥0: +%0,96 (n=5 771, GA −1,4/+3,3); EV≥0,02: +%7,92 (n=595, GA +0,1/+15,3). Zayıf favori MS 1 EV≥0,04: +%8,25 (n=1 058, GA +2,4/+14,5).
3. **EV tabanlı ana tercih** (`derin_tahmin.choose`, `simulasyon.best_value_bet`, `PICK_MIN_EV = 0,02`). Kanıt filtre olarak kalıyor, karar EV'ye göre veriliyor.
   - En olası seçimi oynamak: Max fiyatla −%0,09 (52 261 seçim, GA −0,84/+0,58); tek büro fiyatıyla −%3,36 (GA −3,93/−2,73).
   - EV seçimi: Max fiyatla +%2,15 (4 237 seçim, GA +0,1/+4,5). Tek büro fiyatında yalnız 3 seçim kalıyor, bu yüzden anlamsız.
4. **Claude/Gemini denetim düzeltmeleri:**
   - `datalake_lig` kademe hatası düzeltildi (Bundesliga 2 → 2. Bundesliga, La Liga 2, İngiltere/Hollanda 1./2. Lig, Serie C ≠ Serie A). Lig ortalamaları "yalnız bilgi" diye etiketlendi.
   - "geçmiş yetersiz" hükmünde geçmiş oranı artık kullanılmıyor.
   - Serbest notlar hükmü ezmiyor.
   - `--saat` gece yarısını aşan pencereyi destekliyor ve biçimi doğruluyor.
   - Simülasyon docstring'i düzeltildi; piyasa sütunu "Piyasa (keskin, marjsız)" diye etiketlendi.
   - v82 çapraz öğrenici "DENEYSEL" diye işaretlendi (`docs/research/deneysel_kod.md`).
5. **Aynı gün yapılan ayarların arşiv testi:**
   - 141e724 rho taper'ı: KG Var'ı anlamlı kötüleştiriyor (+0,0000159 [9,3e-06, 2,34e-05]; toplam beklenti >2,8'de +0,0000476). **Kapatıldı.**
   - v7 rejim tokenları ve 7cb38ea KG Var ağırlıkları sınanamıyor (arşivde lig ve KG fiyatı yok). **Nötr değere döndürüldü.**
   - `verify_v7_repair_on_nov19.py` "kanıt değil (in-sample)" diye işaretlendi.
   - `live_calibration.json` (60 maç): KG Var kayması LL'yi +0,00085 [+0,00065, +0,00105] kötüleştiriyor, diğer kaymalar anlamsız. 300 sonuçlanmış maçın altında **nötr** kalacak.

## 4. Önce / sonra

| Ölçü | Önce | Sonra |
|---|---|---|
| KG Var LL (77 519 maç) | 0,68684 | 0,68599 |
| KG Var Brier | 0,24687 | 0,24645 |
| KG Var ECE | 0,0172 | 0,0015 |
| Ana tercih ROI (Max fiyat) | −%0,09 (olasılıkla seçim) | +%2,15 (EV ≥ 0,02) |
| Taper (KG Var LL) | 0,686852 | 0,686836 |

Kupon düzeyinde Nesine fiyatlarıyla önce/sonra backtest yapılamadı: elimizde yalnız 168 bacaklık Nesine fiyatı var.

## 5. Sınırlar
- Arşiv tek bürodan (Bet365 tipi) ve kapanış oranı olduğu garanti değil. Max fiyat ROI'si iyimser.
- 3.5 Üst ve KG Var için arşivde fiyat yok, ROI hesaplanamıyor.
- Post-mortem örneklemleri küçük (aile başına n=6–25). Canlı bahisler ayrı tutuldu.
- Kupon ve bahis miktarı politikası bu dalın kapsamı dışında (`grokbot/tam-analiz` → `strategy/accumulator_policy.py`).

## 6. Testler
Tam pytest: **1559 geçti, 0 kaldı.**
