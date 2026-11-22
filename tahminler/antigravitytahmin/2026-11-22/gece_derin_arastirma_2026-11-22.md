# 22 Kasım 2026 — Henüz Başlamamış 50 Maçın Derin Araştırması (21:07 TSİ · v2 Onarılmış Motor)

- **Kapsam:** `21:15 – 04:30 TSİ` arası henüz başlamamış **50 fiyatlı maç** (**46** keskin Matchbook+Smarkets/Pinnacle, **4** global büro).
- **Kullanılan taze veriler:** Çift-okuma canlı Nesine oranları (`21:07 TSİ`, 131 aktif maç), web sakatlık/kadro/playoff statüsü istihbaratı, onarılmış **v2 motorlar** (`market_diagnosis v2`, saha-uyarlamalı + Gamma-Poisson `κ=0,030` + deplasman 1Y asimetrik **20.000 Monte Carlo simülasyon v2**, Dixon-Coles, Club Elo, `extreme_goals`).
- **Sıkı Banko (`P_düz ≥ %70`, 0 bayrak, canlı Nesine ≥ 1,20):** Şu an kalan 50 maçta **0 adet** sıkı `%70+` bacak çıkıyor (en yüksek düzeltilmiş `P_düz`: **%69,3**). Kural gevşetilmez — dürüst tablo aşağıda.

---

## 1. Gecenin En Güçlü "Üçlü Onaylı" (`★3LU`) ve Altın Adayları (Canlı Nesine Oranlarıyla)

*(Üçlü Onay = Keskin Piyasa + Bağımsız Saha-Uyarlamalı 20.000 Monte Carlo v2 + İki Takımın Ayrı Ayrı Geçmişi aynı yönde uyumlu, `market_diagnosis v2` sıfır tuzak)*

| Saat | Lig | Maç | Seçim | Canlı Oran | `P_düz` | Sim v2 | Geçmiş | Tür / Not |
|---|---|---|---:|---:|---:|---:|---:|---|
| 23:00 | İspanya La Liga | **Getafe – Atl Madrid** | `İY 1.5 Alt` | **1,20** | **%68,7** | %81 | %79 | `DIR ★3LU` · Bordalás evinde 3G 3B 0M, katı 1Y düşük blok (⚡ Dep +5,9p steam) |
| 00:30 | Brezilya Serie A | **Fluminense – Mirassol SP** | `3.5 Alt` | **1,22** | **%68,0** | %73 | %73 | `DIR ★3LU` · 0 bayrak, Maracanã'da kontrollü Fluminense vs kapanan Mirassol |
| 23:00 | İspanya 2. Lig | **Burgos – Albacete** | `1.5 Üst` | **1,22** | **%67,8** | %75 | %75 | `DIR ★3LU` · 0 bayrak, üç görüş de %68–75 bandında tam hizalı |
| 22:45 | İtalya Serie A | **Atalanta – Inter** | `2.5 Üst` | **1,24** | **%63,1** | %65 | %73 | `DIR ★3LU` · Atalanta'da 3 stoper yok (Hien, Kossounou, Kristensen), ⚡ Inter +6,2p steam |
| 22:00 | Brezilya Serie B | **Criciúma – Fortaleza CE** | `1.5 Üst` | **1,44** | **%61,5** | — | — | `DIR ★3LU` · Oran `1,36 → 1,44` yükseldi, 0 bayrak |
| 00:00 | ABD MLS Playoff | **Nashville SC – Cincinnati** | `2.5 Üst` | **1,28** | **%60,7** | — | — | `DIR ★3LU` · Sim xG `2,71–1,50`, Nashville Doğu 1.'si (77p) |
| 22:45 | Fransa Ligue 1 | **Marsilya – Le Mans** | `2.5 Üst` | **1,40** | **%55,6** | — | — | `DIR ★3LU` · Marsilya 5 maçtır kazanıyor (Gouiri 7 gol), Le Mans hiç temiz çarşaf yapamadı |

### Yüksek Olasılıklı Keskin / Rehabilite Altın Havuz (`P_düz = %66,5–69,3`, 0 Bayrak)
| Saat | Lig | Maç | Seçim | Canlı Oran | `P_düz` | Sim v2 | Kaynak |
|---|---|---|---:|---:|---:|---:|---|
| 01:30 | Brezilya Serie A | **Bragantino – Vasco Da G.** | `İY ÇŞ 1X` | 1,21 | **%69,3** | %75 | `MOD` |
| 22:00 | Brezilya Serie A | **Paranaense – Clube do Remo** | `DEĞİL(Dep En Az Bir Yarı)` | 1,24 | **%69,1** | — | `MOD` · 5. vs 19. (Remo küme hattı, yorgun) |
| 01:00 | Arjantin Playoff | **River Plate – Lanús** | `Hnd(-2) 2` *(Lanús +2)* | 1,21 | **%68,7** | — | `MOD REHAB` · Tek maç eleme, River'da Montiel cezalı / Moreno & Ruberto yok |
| 04:30 | ABD MLS Playoff | **V. Whitecaps – Real Salt Lake** | `Ev 1.5 Üst` | 1,21 | **%68,5** | %64 | `MOD REHAB` · Batı 1.'si (T. Müller), RSL'de Diego Luna (menisküs) yok |
| 22:00 | Arjantin Playoff | **Rosario C. – Gimnasia Y.** | `MS 1` | 1,23 | **%68,3** | — | `DIR` · B Grubu lideri (34p) vs A Grubu 8.'si, tek maç evinde |
| 21:30 | Almanya 3. Lig | **Duisburg – H. Rostock** | `Hnd(+1) 1` | 1,20 | **%68,1** | %82 | `MOD REHAB` · Sim xG `2,30–1,17` |
| 02:30 | ABD MLS Playoff | **Chicago Fire – Charlotte** | `4.5 Alt` | 1,21 | **%67,9** | %77 | `MOD` · Normal sezonda 2-1 ve 1-0 bitti, Playoff Maç 1 kontrollü |
| 02:30 | Şili Premier Lig | **Deportes Limache – D. La Serena** | `2Y KG Yok` | 1,20 | **%67,8** | — | `MOD` |
| 00:00 | ABD MLS Playoff | **Nashville SC – Cincinnati** | `DEĞİL(Dep En Az Bir Yarı)` | 1,25 | **%67,5** | — | `MOD` · Supporters' Shield şampiyonu evinde |
| 02:07 | Meksika Liga MX | **CD Guadalajara – Cruz Azul** | `DEĞİL(Ev İki Yarıda Gol)` | 1,21 | **%66,7** | — | `MOD` · 1.'lik maçı, Cruz Azul 5 maçtır kazanıyor |
| 04:00 | Arjantin Playoff | **Instituto – CA Huracán** | `2.5 Alt` | 1,28 | **%65,3** | — | `DIR` · Mkt xG `1,27–0,77`, tek maç eleme |

---

## 2. Öne Çıkan Büyük Maç Dosyaları (Sakatlık + Taktik + Piyasa İstihbaratı)

1. **`22:45` Atalanta – Inter (İtalya Serie A · Mkt xG `1,18–2,37` · Sim xG `1,49–1,91`)**
   - **Kadro/Sakatlık:** Atalanta'da savunma hattı dağılmış durumda — **Isak Hien, Odilon Kossounou, Thomas Kristensen** (3 stoper) ve **Gaetano** yok! Inter'de Bonny, Zielinski, Luis Henrique yok; Akanji şüpheli; **Lautaro Martínez** kadroya döndü (yedek bekleniyor), **Thuram + P. Esposito** çok formda.
   - **Piyasa:** Inter lehine **⚡ +6,2p sharp steam**.
   - **En güçlü tercih:** **`2.5 Üst @1,24` (`★3LU`, P_düz %63,1, Sim %65, Geçmiş %73)**; alternatif `Ev 0.5 Üst @1,22 (%70)` veya `MS 2` / `Dep 1.5 Üst` (Atalanta stoper krizi).
2. **`23:00` Getafe – Atlético Madrid (İspanya La Liga · Mkt xG `0,67–1,76` · Sim xG `0,95–1,41`)**
   - **Kadro/Sakatlık:** Getafe 12 puanının **tamamını evinde** aldı (`3G 3B 0M` Coliseum'da!); **Zaid Romero** iyileşip döndü. Atlético'da **Cristian Romero** kas sorunu nedeniyle şüpheli; **Grimaldo** iyileşti, Oblak/Alvarez/Sørloth/Baena tam kadro, üst üste 5. deplasman galibiyeti hedefi.
   - **En güçlü tercih:** **`İY 1.5 Alt @1,20` (`★3LU`, P_düz %68,7, Sim %81, Geçmiş %79)**; alternatif `KG Yok`. `MS 2`'ye Getafe'nin evindeki namağlup direnci nedeniyle temkin.
3. **`22:45` Marsilya – Le Mans (Fransa Ligue 1 · Mkt xG `2,26–0,95` · Sim xG `2,26–1,25`)**
   - **Kadro/Form:** Marsilya üst üste 6. Ligue 1 galibiyeti peşinde (**Amine Gouiri** 7 gol); yeni yükselen Le Mans 5 maçtır galibiyetsiz, deplasmanda kazanamadı ve sezon başından beri gol yemediği maç yok.
   - **En güçlü tercih:** **`2.5 Üst @1,40` (`★3LU`)**; Marsilya hücum ağırlıklı.
4. **`22:00` Rosario Central – Gimnasia Mendoza & `01:00` River Plate – Lanús (Arjantin Clausura Son 16 — Tek Maç Eleme)**
   - **Format:** 90' berabere biterse uzatma + penaltı.
   - **Rosario C. (B Grubu 1.'si, 34p) – Gimnasia M. (A Grubu 8.'si):** Ev sahibi büyük güç farkıyla **`MS 1 @1,23` (`DIR`, P_düz %68,3)**.
   - **River Plate – Lanús:** River'da **Gonzalo Montiel** kırmızı kart cezalısı, **Aníbal Moreno** ve **Ruberto** yok; Lanús'ta Loaiza yok. River istikrarsız olduğu için `MS 1` yerine **`Hnd(-2) 2 @1,21` (`REHAB`, P_düz %68,7)** (Lanús'un 3+ fark yememesi) çok daha güvenli!
5. **`22:00` Paranaense – Remo & `00:30` Fluminense – Mirassol (Brezilya Serie A — 36. Hafta)**
   - **Paranaense (5., 54p) – Remo (19., 29p):** Remo yorgun ve düşme hattında; **`DEĞİL(Dep En Az Bir Yarı) @1,24` (P_düz %69,1)**.
   - **Fluminense (57p, Libertadores yarışı) – Mirassol (41p, savunma bloğu):** **`3.5 Alt @1,22` (`★3LU`, P_düz %68,0, Sim %73, Geçmiş %73)**.
6. **`00:00` Nashville – Cincinnati, `02:30` Chicago Fire – Charlotte, `04:30` Vancouver Whitecaps – Real Salt Lake (MLS Playoff Best-of-3 Maç 1)**
   - **Vancouver – RSL:** Vancouver Batı 1.'si (**Thomas Müller**); RSL'de en büyük yıldız **Diego Luna (menisküs)** ve **Petković** YOK → **`Ev 1.5 Üst @1,21` (`REHAB`, P_düz %68,5)** ve **`2.5 Üst @1,22` (%70)**.
   - **Chicago – Charlotte:** Chicago normal sezonda 2-1 ve 1-0 yendi → **`4.5 Alt @1,21` (P_düz %67,9, Sim %77)**.
   - **Nashville – Cincinnati:** Supporters' Shield şampiyonu Nashville evinde → **`2.5 Üst @1,28` (`★3LU`)** ve **`DEĞİL(Dep En Az Bir Yarı) @1,25` (P_düz %67,5)**.
7. **`02:07` Chivas Guadalajara – Cruz Azul (Meksika Liga MX — Son Hafta 1.'lik Maçı)**
   - Cruz Azul 32p ile lider (5 maçtır kazanıyor; uzun süreli eksikler Levy, Morales, Jiménez), Chivas 30p ile 3. (tam kadro, evinde yenilgisiz seri). Sıkı 1.'lik taktik maçı → **`DEĞİL(Ev İki Yarıda Gol) @1,21` (P_düz %66,7)**.

---

## 3. Gecenin `6+ Gol` & `İki Yarıda KG Var` Adayları (Canlı Oran + %70 Güvenli Merdiven)

| Kategori | Saat | Maç | Arketip | DNA | Kuyruk P | Canlı Oran | Güvenli Gol Merdiveni |
|---|---|---|---|---:|---:|---:|---|
| **6+ Gol** | 22:45 | **Atalanta – Inter** | yıkım | **76,3** | %16,3 | **5,39** | `Ev 0.5 Üst @1,22 (%70)`, `2.5 Üst @1,24 (%69)` |
| **6+ Gol** | 04:30 | **V. Whitecaps – Real Salt Lake** | yıkım | **68,5** | %16,8 | **5,14** | `Dep 0.5 Üst @1,24 (%70)`, `2.5 Üst @1,22 (%70)` |
| **6+ Gol** | 21:15* | **Sarpsborg 08 – Lillestrom** | düello | **67,2** | %18,6 | **5,16** | `KG Var @1,23 (%72)`, `2.5 Üst @1,23 (%72)` |
| **6+ Gol** | 02:30 | **Chicago Fire – Charlotte** | düello | **66,3** | %17,9 | **4,94** | `2.5 Üst @1,21 (%71)`, `KG Var @1,28 (%67)` |
| **İki Yarıda KG** | 21:15* | **Sarpsborg 08 – Lillestrom** | dengeli_tempo | **74,0** | %13,3 | **7,01** | `KG Var @1,23 (%72)`, `2.5 Üst @1,23 (%72)` |
| **İki Yarıda KG** | 02:30 | **Chicago Fire – Charlotte** | dengeli_tempo | **70,7** | %11,2 | **7,64** | `2.5 Üst @1,21 (%71)`, `KG Var @1,28 (%67)` |
| **İki Yarıda KG** | 02:07 | **CD Guadalajara – Cruz Azul** | dengeli_tempo | **68,2** | %8,4 | **11,45** | — |
| **İki Yarıda KG** | 21:15* | **Lommel SK – Standard Liege** | dengeli_tempo | **68,0** | %9,6 | **8,81** | `KG Var @1,31 (%66)` |

*\*21:15 maçları birkaç dakika içinde başlıyor.*

---

## 4. Tuzak ve Sert Steam Uyarıları (Uzak Durulacaklar)

- **⚠ `23:45` Torreense – Benfica (Portekiz Kupası):** Torreense **son kupa şampiyonu**, maç Jamor'da, Benfica'da 8 maçlık seri sonrası kupa rotasyonu bekleniyor. Keskin borsada **Benfica aleyhine −5,3p tersine steam (`Ber +3,3p`)** var! Benfica ağır handikap / yüksek oranlı MS 2 tuzaktır.
- **⚠ `00:00` Colo Colo – Uni. Catolica (Şili):** Lider Colo Colo evinde favori görünse de keskin borsada **Ev −9,2p / Dep +7,6p** sert tersine steam var! Derbi (`Clásico Albucruzado`) sürprizine açık — MS 1'den uzak durulmalı.
- **⚠ `04:10` Queretaro – Necaxa (Meksika):** **Ev −17,9p / Dep +12,4p** devasa tersine steam! Bilinmeyen kadro/rotasyon haberi fiyatlanıyor — taraf bahsine kesinlikle girilmez.
- **⚠ `03:00` Gimnasia Y Tiro – T. Suarez (Arjantin):** **Ev +14,8p / Dep −19,3p** sert steam (`MS 1: 2,41 → 2,10`, `MS 2: 2,47 → 2,90`).
- **⚠ `23:00` S. Cristal – CS Cienciano & Huancayo – U. Deportes (Peru):** Ev sahiplerine **+10p ila +12p** sert steam; `S. Cristal` maçında güvenli eşiği geçen temiz tercih yok.
- **⚠ `22:30` Lazio (K) – Juventus (K):** Piyasa Juventus'u favori gösterirken (`1,12–2,23`), bağımsız form simülasyonu tam tersini (`1,80–1,03`) veriyor — **çelişkili**, pas geçilmeli.
