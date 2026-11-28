# Öz-Geliştirme ve Kalibrasyon Denetim Raporu — `antigravitytahmin`

- **Oluşturulma:** 2026-11-24T11:34+03:00
- **Denetlenen günler:** 2026-11-22 (453 bitmiş fiyatlı maç)
- **Kupon bölgesi (P ≥ %60, oran ≥ 1.20):** **1266/1952 (%64.9)** vs beklenen %64.8 (artık **+0.1p**, Brier `0.2268`)
- **Ana tahminler (`mac_tahminleri.csv`):** **159/240 (%66.2)** vs beklenen %67.3 (artık **-1.1p**)

## 1. `market_diagnosis` v3 Ayrıştırma Başarımı

| Sınıf | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **REHAB** | 127 | 87 | %68.5 | %65.1 | +3.4p | 0.2140 | %-12.2 |
| **OK** | 389 | 268 | %68.9 | %66.0 | +2.9p | 0.2122 | %-12.2 |
| **TUZAK_RED** | 1436 | 911 | %63.4 | %64.4 | -1.0p | 0.2319 | %-18.1 |

## 2. Keskin Borsa Steam Kırılımı (v3 Kalkan Doğrulaması)

| Pazar / Steam Dilimi | Adet | İsabet | Gerçek % | Beklenen % | Artık |
|---|---:|---:|---:|---:|---:|
| ALT · orta_steam (3-6p) | 9 | 6 | %66.7 | %65.9 | +0.7p |
| ALT · sert_steam (>=6p) | 21 | 11 | %52.4 | %63.3 | -10.9p |
| ALT · steam_yok (<3p) | 209 | 137 | %65.5 | %64.8 | +0.8p |
| MS 1/2 · orta_steam (3-6p) | 6 | 5 | %83.3 | %67.1 | +16.2p |
| MS 1/2 · sert_steam (>=6p) | 14 | 6 | %42.9 | %65.5 | -22.7p |
| MS 1/2 · steam_yok (<3p) | 61 | 43 | %70.5 | %66.4 | +4.0p |

## 3. Altın Havuzlar (En Yüksek İsabet & Pozitif Artık)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Alt** | 90 | 68 | %75.6 | %64.8 | +10.8p | +4.0p | %-2.5 |
| **İY KG Yok & 2Y KG Yok** | 27 | 20 | %74.1 | %63.1 | +10.9p | +1.7p | %-5.0 |
| **KG Yok** | 23 | 17 | %73.9 | %63.3 | +10.6p | +1.4p | %-0.7 |
| **Ev 1.5 Alt** | 85 | 62 | %72.9 | %64.6 | +8.4p | +3.0p | %-6.1 |
| **İY 0.5 Üst** | 60 | 43 | %71.7 | %66.1 | +5.6p | +1.6p | %-10.1 |
| **Dep 0.5 Üst** | 95 | 66 | %69.5 | %65.5 | +4.0p | +1.6p | %-11.5 |

## 4. Zehirli Alt-Pazar Alarmları (Aksiyon Gerektirenler)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Üst** | 20 | 9 | %45.0 | %63.2 | -18.2p | -2.1p | %-39.9 |
| **DEĞİL(Ev İki Yarıda Gol)** | 37 | 19 | %51.3 | %66.4 | -15.1p | -3.0p | %-34.3 |
| **İY ÇŞ 12** | 107 | 53 | %49.5 | %62.9 | -13.4p | -5.6p | %-36.1 |
| **Ev İY 0.5 Üst** | 37 | 20 | %54.0 | %64.2 | -10.2p | -2.0p | %-29.6 |
| **KG Var** | 83 | 45 | %54.2 | %63.9 | -9.7p | -3.4p | %-28.5 |

## 5. Olasılık Dilimleri ve Fiyat Kaynağı

| Dilim / Kaynak | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier |
|---|---:|---:|---:|---:|---:|---:|
| 60-65% | 1085 | 680 | %62.7 | %62.5 | +0.2p | 0.2335 |
| 65-70% | 761 | 518 | %68.1 | %67.2 | +0.9p | 0.2163 |
| 70-75% | 105 | 67 | %63.8 | %71.0 | -7.1p | 0.2357 |
| 75-85% | 1 | 1 | %100.0 | %76.1 | +23.9p | 0.0571 |
| kaynak: `direct` | 277 | 180 | %65.0 | %65.5 | -0.5p | 0.2263 |
| kaynak: `derived` | 1675 | 1086 | %64.8 | %64.7 | +0.2p | 0.2269 |
