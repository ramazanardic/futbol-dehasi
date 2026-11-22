# Öz-Geliştirme ve Kalibrasyon Denetim Raporu — `antigravitytahmin`

- **Oluşturulma:** 2026-11-23T01:44+03:00
- **Denetlenen günler:** 2026-11-22 (428 bitmiş fiyatlı maç)
- **Kupon bölgesi (P ≥ %60, oran ≥ 1.20):** **1178/1808 (%65.1)** vs beklenen %64.7 (artık **+0.4p**, Brier `0.2260`)
- **Ana tahminler (`mac_tahminleri.csv`):** **143/217 (%65.9)** vs beklenen %67.2 (artık **-1.4p**)

## 1. `market_diagnosis` v3 Ayrıştırma Başarımı

| Sınıf | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **REHAB** | 111 | 74 | %66.7 | %65.2 | +1.4p | 0.2188 | %-14.5 |
| **OK** | 515 | 343 | %66.6 | %65.8 | +0.8p | 0.2222 | %-14.8 |
| **TUZAK_RED** | 1182 | 761 | %64.4 | %64.2 | +0.1p | 0.2282 | %-16.8 |

## 2. Keskin Borsa Steam Kırılımı (v3 Kalkan Doğrulaması)

| Pazar / Steam Dilimi | Adet | İsabet | Gerçek % | Beklenen % | Artık |
|---|---:|---:|---:|---:|---:|
| ALT · orta_steam (3-6p) | 9 | 6 | %66.7 | %65.9 | +0.7p |
| ALT · sert_steam (>=6p) | 17 | 9 | %52.9 | %63.5 | -10.5p |
| ALT · steam_yok (<3p) | 193 | 124 | %64.2 | %64.7 | -0.4p |
| MS 1/2 · orta_steam (3-6p) | 6 | 5 | %83.3 | %67.1 | +16.2p |
| MS 1/2 · sert_steam (>=6p) | 13 | 5 | %38.5 | %65.7 | -27.3p |
| MS 1/2 · steam_yok (<3p) | 56 | 40 | %71.4 | %66.6 | +4.8p |

## 3. Altın Havuzlar (En Yüksek İsabet & Pozitif Artık)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Alt** | 83 | 64 | %77.1 | %64.8 | +12.2p | +4.4p | %-0.4 |
| **Ev 1.5 Alt** | 81 | 60 | %74.1 | %64.6 | +9.5p | +3.3p | %-4.6 |
| **KG Yok** | 23 | 17 | %73.9 | %63.3 | +10.6p | +1.4p | %-0.7 |
| **İY KG Yok & 2Y KG Yok** | 26 | 19 | %73.1 | %63.0 | +10.0p | +1.5p | %-6.0 |
| **İY 0.5 Üst** | 57 | 41 | %71.9 | %66.2 | +5.7p | +1.6p | %-9.9 |
| **Hnd(-1) 2** | 38 | 27 | %71.0 | %63.9 | +7.2p | +1.5p | %-9.3 |
| **Dep 0.5 Üst** | 89 | 63 | %70.8 | %65.5 | +5.3p | +2.0p | %-9.9 |
| **Ev 1.5 Üst** | 30 | 21 | %70.0 | %62.8 | +7.2p | +1.2p | %-5.2 |

## 4. Zehirli Alt-Pazar Alarmları (Aksiyon Gerektirenler)

| Alt-Pazar | Adet | İsabet | Gerçek % | Beklenen % | Artık | Büzüştürülmüş | Düz 1u ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Dep 1.5 Üst** | 20 | 9 | %45.0 | %63.2 | -18.2p | -2.1p | %-39.9 |
| **DEĞİL(Ev İki Yarıda Gol)** | 33 | 17 | %51.5 | %66.4 | -14.8p | -2.7p | %-34.2 |
| **İY ÇŞ 12** | 99 | 48 | %48.5 | %62.9 | -14.4p | -5.7p | %-37.4 |
| **Ev İY 0.5 Üst** | 33 | 18 | %54.5 | %64.2 | -9.7p | -1.8p | %-29.1 |

## 5. Olasılık Dilimleri ve Fiyat Kaynağı

| Dilim / Kaynak | Adet | İsabet | Gerçek % | Beklenen % | Artık | Brier |
|---|---:|---:|---:|---:|---:|---:|
| 60-65% | 1019 | 642 | %63.0 | %62.5 | +0.5p | 0.2326 |
| 65-70% | 694 | 478 | %68.9 | %67.2 | +1.7p | 0.2133 |
| 70-75% | 94 | 57 | %60.6 | %70.9 | -10.3p | 0.2490 |
| 75-85% | 1 | 1 | %100.0 | %76.1 | +23.9p | 0.0571 |
| kaynak: `direct` | 256 | 167 | %65.2 | %65.5 | -0.3p | 0.2252 |
| kaynak: `derived` | 1552 | 1011 | %65.1 | %64.6 | +0.5p | 0.2261 |
