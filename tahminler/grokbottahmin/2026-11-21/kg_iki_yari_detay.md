# KG İki Yarıda (1. Yarı / 2. Yarı Karşılıklı Gol → Evet/Evet) — derin araştırma, 21.11.2026
Oluşturulma: 16:51 TSİ. Nesine fiyatları 16:37 TSİ’de yenilendi (nesine_global.py; keskin referans Pinnacle/OddsMath/Smarkets). Bu pazar 163 başlamamış maçta açık.

**Uyarı: Bu bahis BANKO DEĞİL.** En iyi aday bile yaklaşık 6’da 1 (%17), diğerleri 8–9’da 1 tutar. Nesine’nin bu pazardaki marjı ~%22–27, bu yüzden 1 aday dışında hepsi −EV.

## Yöntem
- **Piyasa:** Keskin 1X2 ve Alt/Üst fiyatlarından marjsız takım gol beklentisi (μ) alındı. Motorun Evet/Evet adil olasılığı da kullanıldı (GoalTimingModel).
- **Veri (FotMob):** Her takımın tüm kulvarlardaki son 10 resmi maçı ve devre arası skorları (HT olayı). Bunlardan 1Y/2Y attığı ve yediği gol ortalaması, 1Y KG %, 2Y KG %, iki yarıda KG % ve xG lehte/aleyhte hesaplandı (xG yalnız FotMob’un verdiği liglerde var). Bugünkü maç sayfasından eksik ve cezalılar, hava durumu, H2H ve takımın sonraki maçı (Avrupa ve kupa rotasyonu) alındı.
- **Yarı bazlı model:** Toplam gol: %70 piyasa μ, %30 veri. Yarı payı: takım çiftinin 1Y/2Y gol oranı, %44.5 önseline büzüldü. Her yarı bağımsız Poisson: P(KG yarı) = (1−e^−λh)(1−e^−λa), P(Evet/Evet) = P1·P2.
- **Son P:** 0.45 × yarı modeli + 0.40 × motor (piyasa) + 0.15 × ampirik iki yarıda KG oranı. Ampirik oran 20 maçtan, %12 önseline 6 sanal maçla büzüldü. EV = P × Nesine oranı − 1.

## Sıralama (ilk 10)
| # | Kod | Saat TSİ | Maç | P(Evet/Evet) | 1Y KG | 2Y KG | Adil oran | Nesine | EV | Yarı modeli / Motor / Ampirik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3312633 | 20:00 | Young Boys - Thun | 17.0% | 37.9% | 41.8% | 5.88 | 6.43 | +9.3% | 15.8% / 13.5% / 29.7% |
| 2 | 3313406 | 18:30 | NEC Nijmegen - PSV | 13.4% | 32.8% | 39.5% | 7.44 | 5.86 | -21.3% | 13.0% / 15.1% / 10.5% |
| 3 | 3313844 | 17:30 | E. Frankfurt - Hoffenheim | 12.9% | 27.4% | 45.6% | 7.76 | 5.61 | -27.7% | 12.5% / 14.2% / 10.5% |
| 4 | 3314656 | 23:00 | Groningen - Heerenveen | 12.2% | 30.2% | 39.8% | 8.17 | 7.46 | -8.7% | 12.0% / 11.7% / 14.3% |
| 5 | 3313751 | 17:30 | Liefering - Wacker Inns. | 12.2% | 33.9% | 35.9% | 8.23 | 7.69 | -6.5% | 12.2% / 12.8% / 10.5% |
| 6 | 3314269 | 17:30 | Sturm Gr.(Amt.) - Amstetten | 11.5% | 33.2% | 31.9% | 8.67 | 9.46 | +9.1% | 10.6% / 10.1% / 18.1% |
| 7 | 3314242 | 20:45 | Utrecht - SC Cambuur | 11.0% | 27.5% | 41.8% | 9.09 | 8.03 | -11.6% | 11.5% / 10.7% / 10.5% |
| 8 | 3389687 | 02:00 | Inter Miami - Columbus Cr. | 10.7% | 29.5% | 36.1% | 9.38 | 7.87 | -16.1% | 10.6% / 10.7% / 10.5% |
| 9 | 3314768 | 01:50 | Pachuca - D. Toluca | 10.6% | 29.8% | 36.4% | 9.4 | 7.99 | -15.0% | 10.8% / 10.5% / 10.5% |
| 10 | 3313708 | 17:30 | MSK Zilina - Dukla BB | 10.6% | 25.8% | 37.9% | 9.45 | 8.13 | -14.0% | 9.8% / 10.1% / 14.3% |

## Maç maç gerekçeler
### 1. Young Boys - Thun — 20:00 TSİ — P 17.0%, Nesine 6.43, EV +9.3%
- **Önceki listeye göre: ONAYLANDI ve 1. sıraya çıktı.** Thun son 10 maçının 5’inde iki yarıda da KG oldu (xGA 1.90); YB ilk yarılarda maç başı 1.8 gol atıyor, 1Y KG %60. YB’nin Avrupa maçı yok (sonraki maç 29.11 lig). Thun 26.11’de Conference League’de Ajax’la oynayacak; hafif rotasyon riski var. +EV’nin çoğu ampirik %50’den geliyor. Yalnız yarı modeliyle EV +%2, yalnız motorla −%13. Bu yüzden değer sınırda, kesin değil.
- Ev son 10: 1Y 1.8-0.9, 2Y 1.2-1.0 (attığı-yediği/maç); 1Y KG %60, 2Y KG %30, iki yarıda KG %20; xG 2.18/1.72. Seri (takım bakışı, 1Y|2Y): `H:3-2|0-1 A:2-1|2-1 H:1-0|2-3 A:2-1|0-1 H:1-2|2-0 A:0-0|2-0 A:5-0|0-0 H:0-0|2-0 H:3-2|0-3 A:1-1|2-1`
- Dep son 10: 1Y 0.9-1.0, 2Y 1.1-1.3 (attığı-yediği/maç); 1Y KG %50, 2Y KG %80, iki yarıda KG %50; xG 1.66/1.90. Seri (takım bakışı, 1Y|2Y): `H:1-2|1-2 A:1-0|1-1 A:1-2|1-2 A:0-0|0-1 A:0-0|1-1 H:0-1|0-0 H:1-1|1-2 A:1-2|4-2 H:2-0|1-1 H:2-2|1-1`
- λ 1Y 1.484/0.673, 2Y 1.427/0.8. Nesine 1Y KG Var 2.63, 2Y KG Var 2.1, KG Var 1.26. Pazar marjı 1.224.
- Young Boys sonraki maç: 2026-11-29 Super League vs Sion (7.9 gün sonra)
- Young Boys eksikler (1): Loris Benito (injury)
- Thun sonraki maç: 2026-11-26 Conference League vs Ajax (5.0 gün sonra)
- Thun eksikler (3): Fabio Saiz (injury), Mats Seiler (injury), Genís Montolio (injury)
- Hava: {'temp_c': 6, 'wind': 1, 'precip': 0, 'desc': 'Partly Cloudy'}

### 2. NEC Nijmegen - PSV — 18:30 TSİ — P 13.4%, Nesine 5.86, EV -21.3%
- **Önceki listeye göre: ZAYIFLADI, değer yok.** NEC de PSV de son 10 maçın yalnız 1’inde iki yarıda KG gördü. PSV 24.11’de Real Madrid (CL) maçına çıkacak, rotasyon riski var. NEC’in stoperleri Schuurs ve Nuytinck eksik, bu gol olasılığını artırır. Nesine 5.86 veriyor, adil oran ~7.4, EV −%21.
- Ev son 10: 1Y 0.7-1.2, 2Y 1.0-0.6 (attığı-yediği/maç); 1Y KG %40, 2Y KG %20, iki yarıda KG %10; xG 1.65/1.94. Seri (takım bakışı, 1Y|2Y): `A:0-3|0-2 H:1-1|0-0 A:1-1|0-0 H:0-1|1-0 H:1-1|1-1 A:2-2|2-0 H:0-2|2-0 A:0-0|0-1 H:0-1|3-0 A:2-0|1-2`
- Dep son 10: 1Y 1.2-0.4, 2Y 1.2-0.8 (attığı-yediği/maç); 1Y KG %30, 2Y KG %20, iki yarıda KG %10; xG 2.10/1.51. Seri (takım bakışı, 1Y|2Y): `H:2-1|2-0 A:2-1|0-2 H:1-0|1-0 A:0-0|0-1 A:1-0|0-2 A:0-0|1-0 H:1-0|0-1 H:2-0|5-0 H:0-1|1-1 A:3-1|2-1`
- λ 1Y 0.615/1.253, 2Y 0.916/1.075. Nesine 1Y KG Var 2.53, 2Y KG Var 1.99, KG Var 1.18. Pazar marjı 1.22.
- Bayraklar: NEC Nijmegen kilit oyuncu eksik: Perr Schuurs; rotasyon riski: PSV 3.2 gün sonra Champions League
- NEC Nijmegen sonraki maç: 2026-11-26 Europa League vs Rennes (5.2 gün sonra)
- NEC Nijmegen eksikler (4): Dennis Geiger (injury), Bram Nuytinck (injury), Perr Schuurs (injury), Emre Mor (injury)
- PSV sonraki maç: 2026-11-24 Champions League vs Real Madrid (3.2 gün sonra)
- PSV eksikler (5): Paul Wanner (injury), Adamo Nagalo (injury), Jerdy Schouten (injury), Sami Ouaissa (injury), Alassane Pléa (injury)
- Hava: {'temp_c': 8, 'wind': 3, 'precip': 0, 'desc': 'Partly Cloudy'}

### 3. E. Frankfurt - Hoffenheim — 17:30 TSİ — P 12.9%, Nesine 5.61, EV -27.7%
- **Önceki listeye göre: DÜŞTÜ (değer yok).** Frankfurt ve Hoffenheim son 10 maçın yalnız 1’inde iki yarıda KG gördü. Hoffenheim ilk yarılarda az gol yiyor (1Y gol yediği maç oranı %30). Nesine 5.61 çok düşük (adil ~7.8), EV −%28. Hoffenheim’da 6 eksik var (Hranáč ve Hajdari stoper), bu gol olasılığını artırır ama fiyatı kurtarmıyor.
- Ev son 10: 1Y 0.8-0.7, 2Y 1.1-1.1 (attığı-yediği/maç); 1Y KG %30, 2Y KG %30, iki yarıda KG %10; xG 1.77/2.11. Seri (takım bakışı, 1Y|2Y): `H:1-0|0-4 A:2-0|1-1 H:2-1|0-1 H:1-0|3-0 A:0-4|0-2 H:0-0|1-0 A:0-0|0-1 A:0-0|3-1 H:1-1|2-0 A:1-1|1-1`
- Dep son 10: 1Y 0.7-0.4, 2Y 1.0-1.1 (attığı-yediği/maç); 1Y KG %20, 2Y KG %40, iki yarıda KG %10; xG 1.62/1.31. Seri (takım bakışı, 1Y|2Y): `A:0-2|1-1 H:1-1|1-2 H:0-0|2-3 A:1-0|1-1 H:1-0|2-0 H:0-0|3-0 A:1-1|0-0 A:0-0|0-2 A:1-0|0-1 H:2-0|0-1`
- λ 1Y 0.711/0.772, 2Y 1.155/1.095. Nesine 1Y KG Var 2.48, 2Y KG Var 1.94, KG Var 1.15. Pazar marjı 1.219.
- Bayraklar: Hoffenheim kilit oyuncu eksik: Bambasé Conté
- E. Frankfurt sonraki maç: 2026-11-28 Bundesliga vs VfB Stuttgart (7.1 gün sonra)
- E. Frankfurt eksikler (3): Elias Baum (suspension), Mario Götze (injury), Jessic Ngankam (injury)
- Hoffenheim sonraki maç: 2026-11-26 Europa League vs Sturm Graz (5.2 gün sonra)
- Hoffenheim eksikler (6): Robin Hranác (injury), Bambasé Conté (injury), Valentin Gendrey (injury), Nathan De Cat (injury), Albian Hajdari (injury), Patrick Wimmer (injury)
- Hava: {'temp_c': 7, 'wind': 3, 'precip': 0, 'desc': 'Mostly Sunny'}

### 4. Groningen - Heerenveen — 23:00 TSİ — P 12.2%, Nesine 7.46, EV -8.7%
- **Önceki listeye göre: KISMEN ONAYLANDI.** Groningen son 10 maçta ilk yarıda maç başı 1.3 gol atıp 1.1 yedi, 1Y KG %50. Kaleci Vaessen ve Hateboer cezalı. Heerenveen ikinci yarılarda maç başı 1.6 gol atıyor. EV −%9; listedeki en az kötü fiyatlardan biri.
- Ev son 10: 1Y 1.3-1.1, 2Y 0.9-1.2 (attığı-yediği/maç); 1Y KG %50, 2Y KG %30, iki yarıda KG %20; xG 1.85/2.16. Seri (takım bakışı, 1Y|2Y): `H:1-2|1-1 H:2-2|0-0 A:1-0|0-1 H:2-0|1-0 A:2-1|3-0 H:0-2|2-3 A:2-0|0-2 H:0-1|0-1 H:2-2|0-1 A:1-1|2-3`
- Dep son 10: 1Y 0.7-0.4, 2Y 1.6-0.8 (attığı-yediği/maç); 1Y KG %20, 2Y KG %30, iki yarıda KG %10; xG 1.86/1.44. Seri (takım bakışı, 1Y|2Y): `A:0-0|2-2 H:2-1|0-2 H:0-0|0-0 A:2-0|2-0 A:0-1|0-1 H:1-0|3-0 A:1-0|2-2 A:0-0|2-0 H:0-0|1-0 H:1-2|4-1`
- λ 1Y 0.81/0.787, 2Y 0.866/1.159. Nesine 1Y KG Var 2.88, 2Y KG Var 2.21, KG Var 1.25. Pazar marjı 1.22.
- Groningen sonraki maç: 2026-11-27 Eredivisie vs Willem II (6.0 gün sonra)
- Groningen eksikler (6): Ryan Metu (injury), Etienne Vaessen (suspension), Rijk Janse (injury), Hans Hateboer (suspension), Malcolm Jeng (injury), Travis Hernes (injury)
- Heerenveen sonraki maç: 2026-11-29 Eredivisie vs Fortuna Sittard (7.7 gün sonra)
- Heerenveen eksikler (1): Hristiyan Petrov (injury)
- Hava: {'temp_c': 4, 'wind': 3, 'precip': 0, 'desc': 'Partly Cloudy'}

### 5. Liefering - Wacker Inns. — 17:30 TSİ — P 12.2%, Nesine 7.69, EV -6.5%
- **Önceki listeye göre: ZAYIFLADI.** Wacker İnnsbruck son 10 maçta iki yarıda KG’yi 0 kez gördü ve 2. yarıda 10 maçın sadece 2’sinde gol attı. Liefering’de ise 1Y/2Y KG %50/%50. Bu ligde xG verisi yok. EV −%6.5 (en az kötü), ama veri piyasaya göre aşağı yönlü.
- Ev son 10: 1Y 0.9-0.8, 2Y 1.1-1.3 (attığı-yediği/maç); 1Y KG %50, 2Y KG %50, iki yarıda KG %20; xG yok. Seri (takım bakışı, 1Y|2Y): `A:1-0|1-2 H:1-0|1-1 A:1-1|2-1 H:0-1|1-2 A:0-1|0-3 H:2-1|1-0 A:1-1|0-3 H:1-1|1-1 A:2-1|0-0 H:0-1|4-0`
- Dep son 10: 1Y 0.9-0.9, 2Y 0.4-0.6 (attığı-yediği/maç); 1Y KG %40, 2Y KG %10, iki yarıda KG %0; xG yok. Seri (takım bakışı, 1Y|2Y): `A:0-2|0-0 A:0-2|3-0 H:1-0|0-1 A:2-1|0-1 A:1-0|1-1 H:0-0|0-1 A:0-1|0-0 H:1-1|0-0 H:1-1|0-1 A:3-1|0-1`
- λ 1Y 0.881/0.865, 2Y 0.904/0.926. Nesine 1Y KG Var 2.78, 2Y KG Var 2.18, KG Var 1.24. Pazar marjı 1.269.
- Liefering sonraki maç: 2026-11-28 2. Liga vs Admira Wacker (7.0 gün sonra)
- Liefering: FotMob eksik listesi boş/yok
- Wacker Inns. sonraki maç: 2026-11-27 2. Liga vs First Vienna FC (6.2 gün sonra)
- Wacker Inns.: FotMob eksik listesi boş/yok
- Hava: FotMob’da yok

### 6. Sturm Gr.(Amt.) - Amstetten — 17:30 TSİ — P 11.5%, Nesine 9.46, EV +9.1%
- Sturm II ve Amstetten son 10 maçın 2’şer tanesinde iki yarıda KG gördü; 1Y KG %50 ve %40. Bu ligde xG ve eksik listesi yok. Nesine 9.46 veriyor; motora göre adil ~9.9, EV yalnız yarı modeliyle ≈ %0, motorla −%4. +%9’un kaynağı ampirik %18. 17:30’da başlıyor.
- Ev son 10: 1Y 0.7-1.2, 2Y 1.0-0.7 (attığı-yediği/maç); 1Y KG %50, 2Y KG %30, iki yarıda KG %20; xG yok. Seri (takım bakışı, 1Y|2Y): `H:0-1|0-1 A:1-2|0-1 H:2-1|3-1 A:1-1|2-2 H:1-2|1-0 A:1-2|0-1 H:0-2|0-0 A:0-1|0-0 H:0-0|2-0 A:1-0|2-1`
- Dep son 10: 1Y 0.8-1.1, 2Y 0.9-0.7 (attığı-yediği/maç); 1Y KG %40, 2Y KG %40, iki yarıda KG %20; xG yok. Seri (takım bakışı, 1Y|2Y): `A:1-2|1-0 H:0-0|1-1 A:0-1|0-0 H:2-1|2-1 A:2-1|2-2 H:0-1|1-0 A:0-0|0-0 H:2-0|1-2 A:0-2|0-1 H:1-3|1-0`
- λ 1Y 0.799/0.924, 2Y 0.82/0.842. Nesine 1Y KG Var 3.06, 2Y KG Var 2.39, KG Var 1.32. Pazar marjı 1.267.
- Sturm Gr.(Amt.) sonraki maç: 2026-11-28 2. Liga vs BW Linz (7.1 gün sonra)
- Sturm Gr.(Amt.): FotMob eksik listesi boş/yok
- Amstetten sonraki maç: 2026-11-27 2. Liga vs SKN St. Pölten (6.1 gün sonra)
- Amstetten: FotMob eksik listesi boş/yok
- Hava: FotMob’da yok

### 7. Utrecht - SC Cambuur — 20:45 TSİ — P 11.0%, Nesine 8.03, EV -11.6%
- Utrecht ilk yarılarda zayıf (maç başı 0.4 gol), 2Y KG %60. Cambuur 1Y’de 1.2 gol atıyor. İki tarafta da 5’er eksik var. EV −%12.
- Ev son 10: 1Y 0.4-1.2, 2Y 1.3-1.3 (attığı-yediği/maç); 1Y KG %20, 2Y KG %60, iki yarıda KG %10; xG 1.40/1.99. Seri (takım bakışı, 1Y|2Y): `H:1-2|0-4 H:0-1|3-2 A:1-0|1-1 A:0-3|0-2 H:0-0|3-1 A:0-1|2-0 H:0-0|1-1 A:1-0|0-0 A:1-3|1-1 H:0-2|2-1`
- Dep son 10: 1Y 1.2-0.6, 2Y 1.2-0.9 (attığı-yediği/maç); 1Y KG %20, 2Y KG %40, iki yarıda KG %10; xG 1.47/1.52. Seri (takım bakışı, 1Y|2Y): `H:0-2|1-2 A:0-0|2-2 H:1-0|2-0 A:1-0|0-1 A:0-0|1-0 H:2-1|0-1 A:3-0|3-1 A:1-0|1-0 H:3-0|1-0 H:1-3|1-2`
- λ 1Y 0.669/0.828, 2Y 1.217/0.9. Nesine 1Y KG Var 2.98, 2Y KG Var 2.3, KG Var 1.28. Pazar marjı 1.221.
- Utrecht sonraki maç: 2026-11-29 Eredivisie vs ADO Den Haag (7.7 gün sonra)
- Utrecht eksikler (5): Alonzo Engwanda (injury), Kevin Paredes (injury), Victor Jensen (injury), Miliano Jonathans (injury), Noah Ohio (injury)
- SC Cambuur sonraki maç: 2026-11-28 Eredivisie vs Sparta Rotterdam (7.1 gün sonra)
- SC Cambuur eksikler (5): Wout Asselman (injury), Daan Visser (injury), Jasper Meijster (injury), Jamal Amofa (injury), Damian Westerhof (injury)
- Hava: {'temp_c': 4, 'wind': 2, 'precip': 0, 'desc': 'Clear'}

### 8. Inter Miami - Columbus Cr. — 02:00 TSİ — P 10.7%, Nesine 7.87, EV -16.1%
- **Önceki listeye göre: DÜŞTÜ.** Maç MLS playoff serisinde; seri 28.11’de aynı rakiple devam ediyor, bu da temkinli oyun demek. Miami ilk yarılarda az gol yiyor (maç başı 0.3), Columbus ikinci yarılarda az yiyor (0.3). İki takım da son 10 maçın yalnız 1’inde iki yarıda KG gördü. EV −%16.
- Ev son 10: 1Y 1.1-0.3, 2Y 1.0-1.0 (attığı-yediği/maç); 1Y KG %20, 2Y KG %40, iki yarıda KG %10; xG 1.50/1.57. Seri (takım bakışı, 1Y|2Y): `H:1-0|1-0 H:1-1|1-1 A:1-1|0-1 H:2-0|2-0 H:2-0|0-0 A:1-0|2-1 A:0-1|0-1 H:0-0|2-2 A:0-0|2-1 H:3-0|0-3`
- Dep son 10: 1Y 1.1-0.7, 2Y 1.3-0.3 (attığı-yediği/maç); 1Y KG %40, 2Y KG %20, iki yarıda KG %10; xG 2.05/1.57. Seri (takım bakışı, 1Y|2Y): `A:0-0|2-0 H:1-1|1-0 A:1-2|1-1 H:1-1|2-0 A:1-0|1-0 H:0-0|0-0 H:2-0|2-2 A:1-0|1-0 H:2-0|1-0 A:2-3|2-0`
- λ 1Y 1.11/0.58, 2Y 0.96/0.878. Nesine 1Y KG Var 2.93, 2Y KG Var 2.28, KG Var 1.3. Pazar marjı 1.221.
- Inter Miami sonraki maç: 2026-11-28 Major League Soccer Playoff vs Columbus (6.1 gün sonra)
- Inter Miami eksikler (4): Ezequiel Abadia-Reda (injury), Fricio Caicedo (injury), Mateo Silvetti (injury), Tadeo Allende (injury)
- Columbus Cr. sonraki maç: 2026-11-28 Major League Soccer Playoff vs Inter Miami CF (6.1 gün sonra)
- Columbus Cr. eksikler (1): Wessam Abou Ali (injury)
- Hava: {'temp_c': 26, 'wind': 4, 'precip': 0, 'desc': 'Partly Cloudy'}

### 9. Pachuca - D. Toluca — 01:50 TSİ — P 10.6%, Nesine 7.99, EV -15.0%
- Toluca’da 2Y KG %60 ama iki yarıda KG yalnız 10’da 1. Helinho cezalı. EV −%15.
- Ev son 10: 1Y 0.9-0.8, 2Y 1.2-0.4 (attığı-yediği/maç); 1Y KG %20, 2Y KG %30, iki yarıda KG %10; xG 1.43/1.68. Seri (takım bakışı, 1Y|2Y): `A:0-0|2-0 A:3-0|0-0 H:0-2|2-0 A:0-1|0-0 H:1-2|2-1 A:0-2|1-0 H:1-1|0-1 A:1-0|1-1 H:1-0|2-0 A:2-0|2-1`
- Dep son 10: 1Y 1.0-0.7, 2Y 1.3-1.0 (attığı-yediği/maç); 1Y KG %30, 2Y KG %60, iki yarıda KG %10; xG 1.99/1.44. Seri (takım bakışı, 1Y|2Y): `H:3-0|2-2 A:0-0|1-0 H:2-1|0-2 A:0-2|3-1 A:1-2|1-1 H:0-0|1-1 H:0-1|2-1 A:1-1|0-0 A:1-0|1-2 H:2-0|2-0`
- λ 1Y 0.733/0.852, 2Y 0.98/0.875. Nesine 1Y KG Var 2.97, 2Y KG Var 2.28, KG Var 1.28. Pazar marjı 1.224.
- Bayraklar: D. Toluca kilit oyuncu eksik: Helinho
- Pachuca eksikler (2): Carlos Sánchez (injury), Alexéi Domínguez (injury)
- D. Toluca eksikler (3): Helinho (suspension), Iván López (injury), Marcel Ruíz (injury)
- Hava: {'temp_c': 20, 'wind': 3, 'precip': 0, 'desc': 'Cloudy'}

### 10. MSK Zilina - Dukla BB — 17:30 TSİ — P 10.6%, Nesine 8.13, EV -14.0%
- Žilina’nın 2. yarı gücü yüksek (2Y KG %70, iki yarıda KG 10’da 3), ama Dukla’nın 1Y KG oranı %10. Žilina 24.11’de kupa maçı oynayacak. EV −%14.
- Ev son 10: 1Y 1.5-0.5, 2Y 1.7-1.0 (attığı-yediği/maç); 1Y KG %40, 2Y KG %70, iki yarıda KG %30; xG yok. Seri (takım bakışı, 1Y|2Y): `H:2-0|1-1 A:2-0|3-0 A:1-0|2-3 H:1-0|1-1 A:2-2|0-0 A:3-0|2-0 H:1-1|1-2 A:1-1|1-1 H:1-0|3-1 A:1-1|3-1`
- Dep son 10: 1Y 0.5-0.6, 2Y 0.7-0.7 (attığı-yediği/maç); 1Y KG %10, 2Y KG %30, iki yarıda KG %0; xG yok. Seri (takım bakışı, 1Y|2Y): `A:0-3|0-0 H:1-0|2-2 A:0-0|0-1 A:1-0|0-0 A:2-0|0-0 H:0-0|1-0 A:0-0|2-2 H:0-1|0-1 H:1-1|1-0 H:0-1|1-1`
- λ 1Y 1.162/0.47, 2Y 1.358/0.714. Nesine 1Y KG Var 2.84, 2Y KG Var 2.26, KG Var 1.32. Pazar marjı 1.267.
- Bayraklar: rotasyon riski: MSK Zilina 3.1 gün sonra FA Cup; takımlardan biri son maçlarında ilk yarıda nadiren KG (<%15)
- MSK Zilina sonraki maç: 2026-11-24 FA Cup vs Ružomberok (3.1 gün sonra)
- MSK Zilina: FotMob eksik listesi boş/yok
- Dukla BB sonraki maç: 2026-11-28 1. Liga vs Ružomberok (7.0 gün sonra)
- Dukla BB: FotMob eksik listesi boş/yok
- Hava: {'temp_c': 5, 'wind': 5, 'precip': 0, 'desc': 'Partly Cloudy'}

## Önceki 6 adayın durumu
- **Young Boys - Thun** (20:00): ONAYLANDI ve 1. sıraya çıktı. P 17.0%, Nesine 6.43 (16:27’de 6.43), EV +9.3%. Thun son 10 maçının 5’inde iki yarıda da KG oldu (xGA 1.90); YB ilk yarılarda maç başı 1.8 gol atıyor, 1Y KG %60. YB’nin Avrupa maçı yok (sonraki maç 29.11 lig). Thun 26.11’de Conference League’de Ajax’la oynayacak; hafif rotasyon riski var. +EV’nin çoğu ampirik %50’den geliyor. Yalnız yarı modeliyle EV +%2, yalnız motorla −%13. Bu yüzden değer sınırda, kesin değil.
- **NEC Nijmegen - PSV** (18:30): ZAYIFLADI, değer yok. P 13.4%, Nesine 5.86 (16:27’de 5.86), EV -21.3%. NEC de PSV de son 10 maçın yalnız 1’inde iki yarıda KG gördü. PSV 24.11’de Real Madrid (CL) maçına çıkacak, rotasyon riski var. NEC’in stoperleri Schuurs ve Nuytinck eksik, bu gol olasılığını artırır. Nesine 5.86 veriyor, adil oran ~7.4, EV −%21.
- **E. Frankfurt - Hoffenheim** (17:30): DÜŞTÜ (değer yok). P 12.9%, Nesine 5.61 (16:27’de 5.61), EV -27.7%. Frankfurt ve Hoffenheim son 10 maçın yalnız 1’inde iki yarıda KG gördü. Hoffenheim ilk yarılarda az gol yiyor (1Y gol yediği maç oranı %30). Nesine 5.61 çok düşük (adil ~7.8), EV −%28. Hoffenheim’da 6 eksik var (Hranáč ve Hajdari stoper), bu gol olasılığını artırır ama fiyatı kurtarmıyor.
- **Groningen - Heerenveen** (23:00): KISMEN ONAYLANDI. P 12.2%, Nesine 7.46 (16:27’de 7.46), EV -8.7%. Groningen son 10 maçta ilk yarıda maç başı 1.3 gol atıp 1.1 yedi, 1Y KG %50. Kaleci Vaessen ve Hateboer cezalı. Heerenveen ikinci yarılarda maç başı 1.6 gol atıyor. EV −%9; listedeki en az kötü fiyatlardan biri.
- **Liefering - Wacker Inns.** (17:30): ZAYIFLADI. P 12.2%, Nesine 7.69 (16:27’de 7.69), EV -6.5%. Wacker İnnsbruck son 10 maçta iki yarıda KG’yi 0 kez gördü ve 2. yarıda 10 maçın sadece 2’sinde gol attı. Liefering’de ise 1Y/2Y KG %50/%50. Bu ligde xG verisi yok. EV −%6.5 (en az kötü), ama veri piyasaya göre aşağı yönlü.
- **Inter Miami - Columbus Cr.** (02:00): DÜŞTÜ. P 10.7%, Nesine 7.87 (16:27’de 7.87), EV -16.1%. Maç MLS playoff serisinde; seri 28.11’de aynı rakiple devam ediyor, bu da temkinli oyun demek. Miami ilk yarılarda az gol yiyor (maç başı 0.3), Columbus ikinci yarılarda az yiyor (0.3). İki takım da son 10 maçın yalnız 1’inde iki yarıda KG gördü. EV −%16.

## Kaynaklar ve eksikler
- Nesine bülteni (scripts/nesine_global.py, 16:37 TSİ). Keskin referanslar: Pinnacle/Smarkets (GitHub Actions), OddsMath, ESPN.
- FotMob herkese açık JSON: maç listesi, matchDetails (HT/FT olayları, xG, eksikler, hava, H2H), takım fikstürleri. Kurallara uygun okundu: önbellekli, istekler arası ≥0.8 sn, bot korumasını aşma yok.
- Avusturya 2. Liga, Slovakya, National League ve Belçika 1B için FotMob xG vermiyor. 2. Liga ve National League için eksik listesi de yok. Bunlar 'yok' olarak işaretlendi, uydurulmadı.
- Hakem profili ve ilk yarı gol zamanlaması (dakika dağılımı) kullanılmadı. Son 10 maç küçük örneklem; ampirik oranlara %15 ağırlık verildi.
- API-Football kullanılmadı. Bahis oynanmadı.