# Öz-Geliştirme ve Kalibrasyon Denetim Raporu — `antigravitytahmin`

- **Oluşturulma:** 2026-11-23T03:12+03:00
- **Denetlenen günler:** 2026-11-22 (439 bitmiş fiyatlı maç)
- **Kupon bölgesi (P ≥ %60, oran ≥ 1.20):** **1214/1864 (%65.1)** vs beklenen %64.8 (artık **+0.4p**, Brier `0.2262`)
- **Ana tahminler (`mac_tahminleri.csv`):** **150/228 (%65.8)** vs beklenen %67.2 (artık **-1.4p**)

## 1. `market_diagnosis` v3 Ayrıştırma Başarımı

| Sınıf | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **REHAB** | 116 | 77 | %66.4 | %65.3 | +1.1p | 0.2204 | %-15.0 |
| **OK** | 479 | 325 | %67.8 | %65.8 | +2.0p | 0.2176 | %-13.4 |
| **TUZAK_RED** | 1269 | 812 | %64.0 | %64.3 | -0.3p | 0.2300 | %-17.3 |

## 2. Keskin Borsa Steam Kırılımı (v3 Kalkan Doğrulaması)

| Pazar / Steam Dilimi | Adet | İsabet | Gerçek % | Beklenen % | Artık |
|---|---:|---:|---:|---:|---:|
| ALT · orta_steam (3-6p) | 9 | 6 | %66.7 | %65.9 | +0.7p |
| ALT · sert_steam (>=6p) | 19 | 11 | %57.9 | %63.5 | -5.6p |
| ALT · steam_yok (<3p) | 198 | 128 | %64.6 | %64.7 | -0.1p |
| MS 1/2 · orta_steam (3-6p) | 6 | 5 | %83.3 | %67.1 | +16.2p |
| MS 1/2 · sert_steam (>=6p) | 14 | 6 | %42.9 | %65.5 | -22.7p |
| MS 1/2 · steam_yok (<3p) | 58 | 41 | %70.7 | %66.5 | +4.2p |

## 3. Altın Havuzlar (En Yüksek İsabet & Pozitif Artık)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Alt** | 85 | 66 | %77.6 | %64.9 | +12.7p | +4.6p | %+0.2 |
| **İY KG Yok & 2Y KG Yok** | 27 | 20 | %74.1 | %63.1 | +10.9p | +1.7p | %-5.0 |
| **KG Yok** | 23 | 17 | %73.9 | %63.3 | +10.6p | +1.4p | %-0.7 |
| **Ev 1.5 Alt** | 83 | 61 | %73.5 | %64.5 | +8.9p | +3.2p | %-5.3 |
| **İY 0.5 Üst** | 60 | 43 | %71.7 | %66.1 | +5.6p | +1.6p | %-10.1 |
| **Hnd(-1) 2** | 38 | 27 | %71.0 | %63.9 | +7.2p | +1.5p | %-9.3 |
| **Dep 0.5 Üst** | 92 | 65 | %70.7 | %65.5 | +5.2p | +2.0p | %-10.0 |

## 4. Zehirli Alt-Pazar Alarmları (Aksiyon Gerektirenler)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Üst** | 20 | 9 | %45.0 | %63.2 | -18.2p | -2.1p | %-39.9 |
| **DEĞİL(Ev İki Yarıda Gol)** | 35 | 18 | %51.4 | %66.4 | -14.9p | -2.8p | %-34.1 |
| **İY ÇŞ 12** | 101 | 50 | %49.5 | %62.9 | -13.4p | -5.4p | %-36.1 |
| **Ev İY 0.5 Üst** | 34 | 18 | %52.9 | %64.3 | -11.3p | -2.1p | %-31.2 |
| **KG Var** | 76 | 43 | %56.6 | %63.9 | -7.4p | -2.5p | %-25.4 |

## 5. Olasılık Dilimleri ve Fiyat Kaynağı

| Dilim / Kaynak | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier |
|---|---:|---:|---:|---:|---:|---:|
| 60-65% | 1041 | 658 | %63.2 | %62.5 | +0.8p | 0.2322 |
| 65-70% | 725 | 496 | %68.4 | %67.2 | +1.2p | 0.2149 |
| 70-75% | 97 | 59 | %60.8 | %70.9 | -10.1p | 0.2483 |
| 75-85% | 1 | 1 | %100.0 | %76.1 | +23.9p | 0.0571 |
| kaynak: `direct` | 265 | 173 | %65.3 | %65.5 | -0.2p | 0.2251 |
| kaynak: `derived` | 1599 | 1041 | %65.1 | %64.6 | +0.5p | 0.2264 |
