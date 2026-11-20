# QuantFoot Öz-Öğrenme ve Canlı Kalibrasyon Raporu

- Güncelleme: `2026-11-20 09:03 TSİ`
- Değerlendirilen günler (1): 2026-11-19
- Sonuçlanan maç: **49** · Toplam seçim: **3083** · Brier skoru: **0.1618**
- Kupon bandı (oran ≥ 1,20 & tahmin ≥ %50): **567** seçim · Ortalama tahmin **%59.2** · Gerçekleşen **%59.6** (+0.4 puan)

> Bu dosya her gece sonuçlar işlendikten sonra `scripts/auto_learn.py` tarafından otomatik üretilir. Empirical Bayes daraltması sayesinde 30–40 seçimin altındaki küçük örneklemler parametrelere dokunmaz; yeterli veri biriktiğinde sistematik sapma gösteren kaynak ve pazarların belirsizlik payı (`sigma`) `data/calibration/live_calibration.json` üzerinden kupon motoruna otomatik yansıtılır.

## Aktif Öğrenilmiş Parametre Düzeltmeleri (`live_calibration.json`)

- **Kaynak `Matchbook`**: `sigma +0.0136`
- **Kaynak `Nesine (düşük güven)`**: `sigma +0.0174`
- **Pazar ailesi `Ev sahibi golleri`**: `sigma +0.0031`
- **Pazar ailesi `Tek/Çift`**: `sigma +0.0065`
- **Pazar ailesi `İlk yarı`**: `sigma -0.0040`

## Kaynak Bazlı Gerçek Performans

| Kaynak | Tüm Seçim | Ortalama Tahmin | Gerçekleşen | Brier | Kupon Bandı (n) | Kupon Sapması | Öğrenilen Δσ |
|---|---|---|---|---|---|---|---|
| Matchbook + Smarkets | 2032 | %29.7 | %29.2 | 0.1481 | 331 | +4.9p | +0.0000 |
| Smarkets | 494 | %30.3 | %30.0 | 0.1489 | 77 | +2.7p | +0.0000 |
| Matchbook | 339 | %41.4 | %41.6 | 0.2016 | 100 | -4.3p | +0.0136 |
| Nesine (düşük güven) | 218 | %39.4 | %40.8 | 0.2571 | 59 | -20.0p | +0.0174 |

## Pazar Ailesi Bazlı Kalibrasyon

| Pazar Ailesi | Seçim | Tahmin | Gerçekleşen | Fark | Brier | Kupon Bandı Sapma | Öğrenilen Δσ |
|---|---|---|---|---|---|---|---|
| Kombine (A & B) | 970 | %13.7 | %13.7 | +0.1p | 0.0928 | +3.3p (n=28) | +0.0000 |
| İlk yarı | 368 | %45.3 | %44.8 | -0.5p | 0.2152 | -0.3p (n=121) | -0.0040 |
| Ev sahibi golleri | 258 | %45.5 | %45.0 | -0.5p | 0.2187 | -1.8p (n=88) | +0.0031 |
| Deplasman golleri | 235 | %42.5 | %41.7 | -0.8p | 0.1905 | +3.1p (n=74) | +0.0000 |
| Alt/Üst | 205 | %46.5 | %45.4 | -1.1p | 0.1893 | +1.3p (n=70) | +0.0000 |
| Handikap | 189 | %31.7 | %31.2 | -0.5p | 0.1675 | +2.1p (n=37) | +0.0000 |
| Maç sonucu | 142 | %31.3 | %31.0 | -0.4p | 0.2061 | +6.3p (n=12) | +0.0000 |
| Gol aralığı | 114 | %28.6 | %28.9 | +0.3p | 0.1715 | - | +0.0000 |
| İkinci yarı | 99 | %33.3 | %33.3 | -0.0p | 0.2220 | -23.2p (n=8) | +0.0000 |
| Karşılıklı gol | 90 | %50.0 | %50.0 | -0.0p | 0.2219 | +4.7p (n=43) | +0.0000 |
| Çifte şans | 90 | %60.3 | %63.3 | +3.0p | 0.2081 | -3.5p (n=36) | +0.0000 |
| Tek/Çift | 78 | %50.0 | %50.0 | +0.0p | 0.2507 | -3.5p (n=40) | +0.0065 |
| Diğer | 65 | %12.4 | %10.8 | -1.7p | 0.0809 | - | +0.0000 |
| İY/MS | 63 | %11.1 | %11.1 | +0.0p | 0.0808 | +45.4p (n=1) | +0.0000 |
| 2Y karşılıklı gol | 54 | %43.0 | %40.7 | -2.2p | 0.2046 | +4.2p (n=6) | +0.0000 |
| İY karşılıklı gol | 47 | %34.5 | %34.0 | -0.4p | 0.1256 | -66.6p (n=1) | +0.0000 |
| İlk gol | 16 | %27.4 | %25.0 | -2.4p | 0.1069 | +39.9p (n=2) | +0.0000 |

## Günlük Trend

| Gün | Sonuçlanan Maç | Seçim | Brier | En Güvenilir Tercih (Tahmin → Tutan) |
|---|---|---|---|---|
| 2026-11-19 | 49 | 3083 | 0.1618 | %66.0 → %63.3 (49 maç) |
