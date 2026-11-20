# QuantFoot Öz-Öğrenme ve Canlı Kalibrasyon Raporu

- Güncelleme: `2026-11-20 08:08 TSİ`
- Değerlendirilen günler (1): 2026-11-19
- Sonuçlanan maç: **48** · Toplam seçim: **2894** · Brier skoru: **0.1642**
- Kupon bandı (oran ≥ 1,20 & tahmin ≥ %50): **547** seçim · Ortalama tahmin **%59.3** · Gerçekleşen **%59.2** (-0.1 puan)

> Bu dosya her gece sonuçlar işlendikten sonra `scripts/auto_learn.py` tarafından otomatik üretilir. Empirical Bayes daraltması sayesinde 30–40 seçimin altındaki küçük örneklemler parametrelere dokunmaz; yeterli veri biriktiğinde sistematik sapma gösteren kaynak ve pazarların belirsizlik payı (`sigma`) `data/calibration/live_calibration.json` üzerinden kupon motoruna otomatik yansıtılır.

## Aktif Öğrenilmiş Parametre Düzeltmeleri (`live_calibration.json`)

- **Kaynak `Matchbook`**: `sigma +0.0136`
- **Kaynak `Nesine (düşük güven)`**: `sigma +0.0174`
- **Pazar ailesi `Ev sahibi golleri`**: `sigma +0.0063`
- **Pazar ailesi `İlk yarı`**: `sigma -0.0040`

## Kaynak Bazlı Gerçek Performans

| Kaynak | Tüm Seçim | Ortalama Tahmin | Gerçekleşen | Brier | Kupon Bandı (n) | Kupon Sapması | Öğrenilen Δσ |
|---|---|---|---|---|---|---|---|
| Matchbook + Smarkets | 1843 | %30.1 | %29.6 | 0.1504 | 311 | +4.4p | +0.0000 |
| Smarkets | 494 | %30.3 | %30.0 | 0.1489 | 77 | +2.7p | +0.0000 |
| Matchbook | 339 | %41.4 | %41.6 | 0.2016 | 100 | -4.3p | +0.0136 |
| Nesine (düşük güven) | 218 | %39.4 | %40.8 | 0.2571 | 59 | -20.0p | +0.0174 |

## Pazar Ailesi Bazlı Kalibrasyon

| Pazar Ailesi | Seçim | Tahmin | Gerçekleşen | Fark | Brier | Kupon Bandı Sapma | Öğrenilen Δσ |
|---|---|---|---|---|---|---|---|
| Kombine (A & B) | 886 | %13.9 | %13.9 | +0.0p | 0.0926 | +5.3p (n=27) | +0.0000 |
| İlk yarı | 355 | %45.3 | %44.8 | -0.5p | 0.2167 | +0.1p (n=117) | -0.0040 |
| Ev sahibi golleri | 243 | %45.7 | %45.3 | -0.4p | 0.2221 | -2.6p (n=84) | +0.0063 |
| Deplasman golleri | 220 | %42.5 | %41.8 | -0.7p | 0.1934 | +2.8p (n=71) | +0.0000 |
| Alt/Üst | 196 | %46.9 | %45.9 | -1.0p | 0.1921 | +1.7p (n=68) | +0.0000 |
| Handikap | 180 | %31.6 | %31.1 | -0.5p | 0.1728 | +0.8p (n=36) | +0.0000 |
| Maç sonucu | 139 | %31.3 | %30.9 | -0.4p | 0.2042 | +6.3p (n=12) | +0.0000 |
| Gol aralığı | 107 | %28.6 | %29.0 | +0.4p | 0.1704 | - | +0.0000 |
| İkinci yarı | 96 | %33.3 | %33.3 | -0.0p | 0.2205 | -23.2p (n=8) | +0.0000 |
| Karşılıklı gol | 88 | %50.0 | %50.0 | -0.0p | 0.2238 | +3.9p (n=42) | +0.0000 |
| Çifte şans | 87 | %60.1 | %63.2 | +3.1p | 0.2051 | -5.0p (n=35) | +0.0000 |
| Tek/Çift | 76 | %50.0 | %50.0 | +0.0p | 0.2509 | -4.9p (n=39) | +0.0000 |
| Diğer | 57 | %12.3 | %10.5 | -1.8p | 0.0800 | - | +0.0000 |
| İY/MS | 54 | %11.1 | %11.1 | -0.0p | 0.0748 | +45.4p (n=1) | +0.0000 |
| 2Y karşılıklı gol | 52 | %42.7 | %40.4 | -2.3p | 0.2083 | -1.6p (n=5) | +0.0000 |
| İY karşılıklı gol | 45 | %33.8 | %33.3 | -0.4p | 0.1286 | -66.6p (n=1) | +0.0000 |
| İlk gol | 13 | %26.1 | %23.1 | -3.0p | 0.1030 | +34.5p (n=1) | +0.0000 |

## Günlük Trend

| Gün | Sonuçlanan Maç | Seçim | Brier | En Güvenilir Tercih (Tahmin → Tutan) |
|---|---|---|---|---|
| 2026-11-19 | 48 | 2894 | 0.1642 | %66.0 → %62.5 (48 maç) |
