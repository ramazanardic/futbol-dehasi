# 19-20 Kasım 2026 — QuantFoot-v7 Akşam & Gece Skor Tahminleri ve Kupon Portföyü

- **Veri Kaynağı:** Canlı Nesine oranları (`20:18 TSİ`) + Global Sharp Exchange (`Smarkets` + `Matchbook` + `Betfair`, `20:27 TSİ` güncellemesi) + `QuantFoot-v7` (9 katmanlı risk kalkanı & kalibre skor matrisi).
- **Kupon Kuralları:** Tüm bacaklar `≥ 1.20` canlı Nesine oranı, MBS uyumlu, kuponlar arası **0 tekrar eden tercih**, `20:45` maçları kupon dışı bırakılıp yalnızca analiz/skor tablosunda sunulmuştur.

## 1. Başlamamış Tüm 24 Maç — Exact Skor Tahminleri & QuantFoot-v7 Analizi

| # | Saat (TSİ) | Lig | Maç | Global xG | 1. Skor Tahmini | 2. Skor | 3. Skor | v7 En Güvenli Tercih (Canlı Nesine) |
|---:|---|---|---|---|---|---|---|---|
| 37 | 19.11 20:45 | UEFA Şamp. Ligi Kadınlar | FK Austria Wien (K) - B. Münih (K) | 0.65 - 4.37 | **0-3** (%8.8) | 0-2 (%8.1) | 0-4 (%8.0) | **3.5 Üst @ 1.33** (P:%61.5) |
| 38 | 19.11 20:45 | UEFA Şamp. Ligi Kadınlar | Paris (K) - HB Koege (K) | 2.59 - 1.09 | **2-0** (%8.3) | 1-0 (%8.2) | 2-1 (%7.4) | **MS 1 @ 1.27** (P:%66.2) |
| 39 | 19.11 21:00 | Arjantin Primera A Kapanış, Kadınlar | Ferro Carril (K) - CA River Plate (K) | 1.32 - 1.03 | **1-1** (%13.4) | 1-0 (%12.2) | 0-0 (%9.9) | **ÇŞ 02 @ 1.33** (P:%57.3) |
| 40 | 19.11 21:00 | Danimarka 1. Lig | Fredericia - Hilleroed | 2.80 - 0.80 | **2-0** (%10.7) | 3-0 (%10.0) | 2-1 (%8.6) | **2.5 Üst @ 1.20** (P:%70.1) |
| 41 | 19.11 21:00 | İspanya Kupası, Kadınlar | RC Celta de Vigo (K) - RCD Espanyol (K) | 0.57 - 2.46 | **0-1** (%13.4) | 0-2 (%13.1) | 0-3 (%9.8) | PAS / BLOKE |
| 42 | 19.11 21:00 | Mısır Kupası | ZED - Smouha SC | 1.15 - 0.88 | **1-0** (%14.9) | 1-1 (%14.5) | 0-0 (%12.9) | **1.5 Üst @ 1.38** (P:%61.7) |
| 43 | 19.11 22:00 | Cezayir 1. Lig | JS Kabylie - USM Alger | 1.22 - 0.84 | **1-0** (%15.2) | 1-1 (%14.3) | 0-0 (%12.3) | **2.5 Alt @ 1.28** (P:%65.3) |
| 44 | 19.11 22:30 | Uruguay Prmr Ligi, Kapanış | CA Progreso - Torque | 0.92 - 1.99 | **0-2** (%10.8) | 0-1 (%10.6) | 1-1 (%10.3) | **MS 2 @ 1.37** (P:%62.2) |
| 45 | 19.11 22:30 | Uruguay Prmr Ligi, Kapanış | Penarol - Cerro Largo | 1.86 - 0.60 | **1-0** (%15.6) | 2-0 (%14.8) | 1-1 (%9.8) | **MS 1 @ 1.21** (P:%68.3) |
| 46 | 19.11 22:30 | Uruguay Prmr Ligi, Kapanış | Boston River - D. Maldonado | 1.09 - 1.55 | **1-1** (%12.4) | 0-1 (%10.8) | 1-2 (%9.3) | **KG Var @ 1.54** (P:%54.2) |
| 47 | 19.11 22:45 | Fransa Ulusal Lig | Amiens - Caen | 1.50 - 1.16 | **1-1** (%12.5) | 1-0 (%10.1) | 2-1 (%9.1) | **ÇŞ 02 @ 1.38** (P:%56.4) |
| 48 | 19.11 23:00 | UEFA Şamp. Ligi Kadınlar | Arsenal (K) - O. Lyon (K) | 1.47 - 2.46 | **1-1** (%7.5) | 1-2 (%7.1) | 0-1 (%6.4) | **2.5 Üst @ 1.20** (P:%69.4) |
| 49 | 19.11 23:00 | UEFA Şamp. Ligi Kadınlar | Barcelona (K) - Servette (K) | 5.85 - 0.25 | **4-0** (%9.9) | 5-0 (%9.7) | 3-0 (%8.9) | PAS / BLOKE |
| 50 | 19.11 23:00 | UEFA Şamp. Ligi Kadınlar | Benfica (K) - AS Roma (K) | 2.11 - 1.65 | **1-1** (%8.2) | 2-1 (%6.9) | 1-0 (%6.3) | **KG Var @ 1.24** (P:%67.5) |
| 51 | 20.11 01:30 | Brezilya Serie A | Vitoria BA - Bragantino | 1.35 - 1.35 | **1-1** (%13.4) | 1-2 (%8.8) | 2-1 (%8.8) | **3.5 Alt @ 1.21** (P:%71.0) |
| 52 | 20.11 01:30 | Brezilya Serie A | Vasco Da G. - Internacional | 1.99 - 0.89 | **2-0** (%11.4) | 1-0 (%10.8) | 1-1 (%10.7) | **MS 1 @ 1.35** (P:%63.4) |
| 53 | 20.11 01:30 | Kolombiya Prmr B Kapanış, Yük. Gr A | U. Magdalena - Boca Juniors (Kol) | 2.15 - 0.57 | **2-0** (%15.6) | 1-0 (%13.8) | 3-0 (%11.1) | **KG Yok @ 1.40** (P:%60.2) |
| 54 | 20.11 01:30 | Kolombiya Prmr B Kapanış, Yük. Gr A | Independiente Yumbo - Envigado | 0.99 - 1.16 | **1-1** (%14.6) | 0-1 (%13.1) | 0-0 (%11.3) | **2.5 Alt @ 1.30** (P:%62.4) |
| 55 | 20.11 01:30 | Venezuela Kupası, Eleme Turu | Dep. La Gua. - Academia Anzoategui | 2.20 - 0.73 | **2-0** (%12.9) | 1-0 (%11.5) | 3-0 (%9.5) | **2.5 Üst @ 1.47** (P:%56.1) |
| 56 | 20.11 03:30 | Brezilya Serie A | Sao Paulo SP - Fluminense | 1.26 - 1.15 | **1-1** (%14.2) | 1-0 (%10.9) | 0-1 (%9.8) | **1.5 Üst @ 1.21** (P:%69.7) |
| 57 | 20.11 03:30 | ABD Major Lig Playoff | Orlando City - Cincinnati | 2.08 - 2.02 | **1-1** (%7.4) | 2-1 (%6.7) | 1-2 (%6.5) | **ÇŞ 10 @ 1.35** (P:%62.7) |
| 58 | 20.11 03:45 | Kolombiya Prmr B Kapanış, Yük. Gr B | R. Cartagena - Tigres (Kol) | 2.21 - 0.48 | **2-0** (%17.1) | 1-0 (%14.8) | 3-0 (%12.5) | **KG Yok @ 1.33** (P:%65.0) |
| 59 | 20.11 03:45 | Kolombiya Prmr B Kapanış, Yük. Gr B | R. S. Cundinamarca - Deportes Quindio | 0.92 - 1.03 | **1-1** (%14.7) | 0-1 (%14.4) | 0-0 (%13.9) | **ÇŞ 10 @ 1.28** (P:%64.2) |
| 60 | 20.11 06:00 | ABD Major Lig Playoff | S. Sounders - Real Salt Lake | 1.91 - 1.34 | **1-1** (%9.8) | 2-1 (%8.4) | 1-0 (%7.9) | **KG Var @ 1.38** (P:%62.5) |

## 2. QuantFoot-v7 Sıfır-Tekrarlı Akşam & Gece Kuponları (`≥ 21:00 TSİ`)

### KUPON 1 — Gece Çekirdek Güven (3 Maç, ~2.4x)
**Toplam Oran:** `2.42x` | **Maç Sayısı:** `3` | **Ort. Global Olasılık:** `%63.8` | **Birleşik Tutma Olasılığı:** `%25.99`

| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |
|---|---|---:|---|---:|---:|---:|---:|
| 20.11 01:30 | Vitoria BA - Bragantino | 1 | **ÇŞ 02** | 1.32 | 1.56 | %64.0 | -15.6% |
| 20.11 03:45 | R. Cartagena - Tigres (Kol) | 3 | **KG Yok** | 1.33 | 1.54 | %65.0 | -13.5% |
| 20.11 06:00 | S. Sounders - Real Salt Lake | 1 | **KG Var** | 1.38 | 1.60 | %62.5 | -13.8% |

### KUPON 2 — Dengeli Akşam & Gece (4 Maç, ~4.8x)
**Toplam Oran:** `4.81x` | **Maç Sayısı:** `4` | **Ort. Global Olasılık:** `%56.9` | **Birleşik Tutma Olasılığı:** `%10.42`

| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |
|---|---|---:|---|---:|---:|---:|---:|
| 19.11 22:00 | JS Kabylie - USM Alger | 3 | **KG Yok** | 1.43 | 1.72 | %58.2 | -16.8% |
| 20.11 03:30 | Orlando City - Cincinnati | 1 | **3.5 Üst** | 1.55 | 1.83 | %54.7 | -15.2% |
| 20.11 06:00 | S. Sounders - Real Salt Lake | 1 | **2.5 Üst** | 1.41 | 1.65 | %60.5 | -14.8% |
| 19.11 22:30 | Boston River - D. Maldonado | 3 | **KG Var** | 1.54 | 1.85 | %54.2 | -16.6% |

### KUPON 3 — Hedef 10x+ Global Exchange Kombinesi
**Toplam Oran:** `10.21x` | **Maç Sayısı:** `7` | **Ort. Global Olasılık:** `%60.5` | **Birleşik Tutma Olasılığı:** `%2.94`

| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |
|---|---|---:|---|---:|---:|---:|---:|
| 20.11 03:30 | Sao Paulo SP - Fluminense | 1 | **ÇŞ 02** | 1.37 | 1.61 | %62.1 | -14.9% |
| 20.11 01:30 | Vasco Da G. - Internacional | 1 | **2.5 Üst** | 1.49 | 1.80 | %55.4 | -17.4% |
| 20.11 03:45 | R. S. Cundinamarca - Deportes Quindio | 3 | **1.5 Üst** | 1.40 | 1.70 | %59.0 | -17.5% |
| 20.11 03:30 | Orlando City - Cincinnati | 1 | **ÇŞ 10** | 1.35 | 1.59 | %62.7 | -15.3% |
| 19.11 22:30 | CA Progreso - Torque | 3 | **MS 2** | 1.37 | 1.61 | %62.2 | -14.8% |
| 19.11 21:00 | ZED - Smouha SC | 3 | **1.5 Üst** | 1.38 | 1.62 | %61.7 | -14.8% |
| 20.11 01:30 | U. Magdalena - Boca Juniors (Kol) | 3 | **KG Yok** | 1.40 | 1.66 | %60.2 | -15.8% |

### KUPON 4 — Hedef 20x+ Ana Gece Kombinesi (0 Tekrar)
**Toplam Oran:** `20.14x` | **Maç Sayısı:** `9` | **Ort. Global Olasılık:** `%59.4` | **Birleşik Tutma Olasılığı:** `%0.91`

| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |
|---|---|---:|---|---:|---:|---:|---:|
| 20.11 01:30 | Vitoria BA - Bragantino | 1 | **ÇŞ 10** | 1.31 | 1.56 | %64.0 | -16.2% |
| 20.11 03:30 | Sao Paulo SP - Fluminense | 1 | **2.5 Alt** | 1.50 | 1.78 | %56.3 | -15.6% |
| 19.11 23:00 | Arsenal (K) - O. Lyon (K) | 1 | **MS 2** | 1.43 | 1.76 | %57.0 | -18.5% |
| 20.11 01:30 | Vasco Da G. - Internacional | 1 | **MS 1** | 1.35 | 1.58 | %63.4 | -14.4% |
| 20.11 01:30 | Independiente Yumbo - Envigado | 3 | **2.5 Alt** | 1.30 | 1.60 | %62.4 | -18.9% |
| 20.11 03:30 | Orlando City - Cincinnati | 1 | **ÇŞ 02** | 1.36 | 1.64 | %60.9 | -17.2% |
| 19.11 21:00 | ZED - Smouha SC | 3 | **KG Yok** | 1.39 | 1.71 | %58.5 | -18.6% |
| 20.11 01:30 | Dep. La Gua. - Academia Anzoategui | 3 | **2.5 Üst** | 1.47 | 1.78 | %56.1 | -17.6% |
| 19.11 22:30 | CA Progreso - Torque | 3 | **2.5 Üst** | 1.47 | 1.79 | %56.0 | -17.7% |

### KUPON 5 — Yüksek Olasılıklı Zırhlı Alternatif (8 Maç, Ort P=%67.7, ~5.5x)
**Toplam Oran:** `5.51x` | **Maç Sayısı:** `8` | **Ort. Global Olasılık:** `%67.7` | **Birleşik Tutma Olasılığı:** `%4.34`

| Saat (TSİ) | Maç | MBS | Tercih | Canlı Nesine | Global Adil | Global Olasılık | EV |
|---|---|---:|---|---:|---:|---:|---:|
| 20.11 01:30 | Vitoria BA - Bragantino | 1 | **3.5 Alt** | 1.21 | 1.41 | %71.0 | -14.1% |
| 19.11 21:00 | Fredericia - Hilleroed | 3 | **2.5 Üst** | 1.20 | 1.43 | %70.1 | -15.8% |
| 20.11 03:30 | Sao Paulo SP - Fluminense | 1 | **1.5 Üst** | 1.21 | 1.44 | %69.7 | -15.7% |
| 19.11 23:00 | Arsenal (K) - O. Lyon (K) | 1 | **2.5 Üst** | 1.20 | 1.44 | %69.4 | -16.7% |
| 19.11 22:30 | Penarol - Cerro Largo | 3 | **MS 1** | 1.21 | 1.46 | %68.3 | -17.3% |
| 19.11 23:00 | Benfica (K) - AS Roma (K) | 1 | **KG Var** | 1.24 | 1.48 | %67.5 | -16.3% |
| 19.11 22:00 | JS Kabylie - USM Alger | 3 | **2.5 Alt** | 1.28 | 1.53 | %65.3 | -16.4% |
| 20.11 03:45 | R. S. Cundinamarca - Deportes Quindio | 3 | **KG Yok** | 1.36 | 1.67 | %59.8 | -18.7% |

