# 28 Kasım 2026 — Post-mortem ve kendini geliştirme

Hazırlanma: 28 Kas 2026, 22:25 TSİ. Sonuç kaynağı: Nesine herkese açık sonuç akışı (90 dk skoru + İY), korner için ESPN
herkese açık scoreboard. Bahis tutarı/bakiye bu raporda yok (açık depo). Sonuçlanmamış maçlar "bekliyor" sayıldı,
skor uydurulmadı.

## 1) Günün özeti: model kalibre, kayıp çoğunlukla varyans

- Ana tahminler (`mac_tahminleri.csv`, 233 seçim): o an biten **163** seçimin **110**'u tuttu (%67,5). Modelin aynı
  seçimlere verdiği olasılıkların toplamı **108,6** → beklenen ile gerçek arasındaki fark +1,4 seçim (z = +0,24).
  Yani bugün model "kötü" değildi; söylediği oranda tuttu.
- Banko bölgesi (P ≥ 0,70): 26 seçimde 24 isabet (%92; ortalama P %71,8). Kaçan iki: Empoli Ev 1.5 Alt (2-2),
  Man Utd Hnd(+1) 1 (0-4).
- Kaçan 53 ana seçimin 50'si keskin Pinnacle fiyatlıydı (OddsMath/BetInAsia), 3'ü Marathonbet. Yani seçimlerin
  dayanağı piyasanın en keskin fiyatıydı; hata "yanlış veri / yanlış fiyat" değil, olasılığın doğası (P = 0,68 olan
  seçim 3'te 1 kaybeder).

Aile bazında (biten seçimler; "beklenen" = P toplamı):

| Aile | n | ort. P | isabet | beklenen | gerçek |
|---|---|---|---|---|---|
| Yarı (İY/2Y gol, 2Y KG, İY ÇŞ) | 63 | %67.4 | %76.2 | 42.5 | 48 |
| Çifte şans | 25 | %66.9 | %60.0 | 16.7 | 15 |
| Takım golü | 24 | %68.6 | %75.0 | 16.5 | 18 |
| Maç alt/üst | 19 | %67.1 | %57.9 | 12.7 | 11 |
| KG (maç) | 13 | %62.5 | %53.8 | 8.1 | 7 |
| MS | 12 | %64.0 | %58.3 | 7.7 | 7 |
| Kombine | 4 | %59.9 | %50.0 | 2.4 | 2 |
| Handikap | 3 | %64.6 | %66.7 | 1.9 | 2 |

Ailelerin hiçbiri beklenenden istatistiksel olarak sapmadı (en büyük sapma maç alt/üst: 12,7 beklenen, 11 gerçek).
"Takım golü %75, MS %58" farkı büyük ölçüde ailelerin **ortalama P'sinin** farklı olmasından geliyor (KG/MS
seçimleri zaten %62–64 olasılıklı).

## 2) Kuponlardaki kaçan bacaklar — neden seçildi, ne oldu

| Kupon | Maç | Seçim | Oran | Model P | Sonuç | Neden seçildi | Teşhis |
|---|---|---|---|---|---|---|---|
| ~20 / ~30 | Wil 1900 - Yverdon | MS 2 | 1.93 | %46,2 | 4-2 (İY 2-0) | Pinnacle 1X2 (Yverdon %46 favori), hedef orana ulaşmak için 2'ye yakın oranlı bacak | Bacak zaten %54 kaybedecekti; araştırma notu yoktu. Hata değil, risk kuponunun doğası |
| ~20 / ~30 | Grasshoppers - Basel | MS 2 | 1.98 | %43,5 | 2-1 | Aynı mantık | Aynı (%56 kayıp ihtimali) |
| İY/MS | Arouca - Rio Ave | İY/MS 1/1 | 2.28 | %36,2 | 0-0 | 9 kombinasyon içinde en olası | %64 kayıp ihtimali; 0-0 bitti |
| Skor | Albacete - Tenerife | Skor 1-1 | 5.13 | %13,5 | 4-0 | En olası skor | Kesin skor bacağı %86,5 kaybeder |
| Skor | B. Kaliningrad - Akhmat | Skor 1-1 | 5.52 | %13,5 | 1-0 | En olası skor | Aynı |
| İY skoru | Moreirense - Santa Clara | İY 0-0 | 2.20 | %35,6 | İY 0-1 | En olası İY skoru | %64 kayıp ihtimali |
| İY skoru | Eibar - Burgos | İY 0-0 | 2.45 | %32,2 | İY 2-0 | Aynı | Aynı |
| 2Y KG Var | Rosenborg - Molde | 2Y KG Var | 2.05 | %42,7 | 2-1 (İY 1-1; 2Y 1-0) | En yüksek 2Y KG olasılığı | %57 kayıp ihtimali |
| 20'li | NS Mura - NK Maribor | 3.5 Alt | 1.15 | %74,6 | 0-4 | Pinnacle 3.5 çizgisi | Deplasman 2. yarıda 4 attı — kuyruk olayı |
| 20'li | Ospitaletto - Union Brescia | 1.5 Üst | 1.19 | %73,8 | 0-0 | Pinnacle toplam gol | Golsüz maç (%26 ihtimal) |
| Banko A | Lumezzane - Desenzano | 3.5 Alt | 1.21 | %71,0 | 2-2 (İY 2-0) | Pinnacle 3.5 çizgisi | 4. gol 2. yarıda; kuyruk olayı |
| Korner 2.4x | Leeds - Coventry | Korner 10.5 Alt | 1.34 | %70,6 | 12 korner (9-3) | Korner modeli (takım korner beklentisi) | Güçlü favori çok korner kazandı; arşivde favori etkisi test edildi, sistematik değil (bkz. 4c) |

Kupon düzeyinde asıl ders: **kupon tutma olasılığı bacak olasılıklarının çarpımıdır.** 20'li "güven" kuponunun
tutma ihtimali %0,3'tü (her bacak %72–79 olsa bile); İY/MS, skor, İY skoru, 2Y KG kuponları %1,8–6,9 idi. Bunların
kaybetmesi beklenen sonuçtur. Banko A (5 bacak, %21,3) de 5 kezden 4'ünde kaybeder. Tek tutan 1.7x kupon (3 bacak,
%36,6) — en kısa kupon.

## 3) Kaçan ana tahminler (53, biten maçlar, P'ye göre)

| Saat | Lig | Maç | Seçim | Oran | Model P | Skor (İY) | Kayıp türü |
|---|---|---|---|---|---|---|---|
| 17:00 | İtalya Serie B | Empoli - Hellas Verona | Ev 1.5 Alt | 1.22 | %72.4 | 2-2 (İY 1-1) | gol patlaması (kuyruk olayı) |
| 18:00 | İngiltere Premier Lig | Man. Utd - Brentford | Hnd(+1) 1 | 1.23 | %70.2 | 0-4 (İY 0-2) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Championship | West Ham - Stoke City | İY 0.5 Üst | 1.20 | %70.0 | 1-0 (İY 0-0) | golsüz ilk yarı |
| 18:00 | İngiltere 2. Lig | Colchester - York City | ÇŞ X2 | 1.20 | %69.2 | 2-1 (İY 2-1) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig, Güney | Weston Super Mare - Maidenhead | Dep 1.5 Alt | 1.21 | %69.1 | 4-3 (İY 1-0) | gol patlaması (kuyruk olayı) |
| 18:15 | İspanya La Liga | Malaga - Ath Bilbao | 3.5 Alt | 1.21 | %69.0 | 3-4 (İY 1-4) | gol patlaması (kuyruk olayı) |
| 18:00 | İngiltere 2. Lig | Port Vale - Newport | İY 0.5 Üst | 1.23 | %68.9 | 3-2 (İY 0-0) | golsüz ilk yarı |
| 17:30 | Polonya 1. Lig | Odra Opole - Polonia Warszawa | 3.5 Alt | 1.20 | %68.7 | 1-3 (İY 1-2) | gol patlaması (kuyruk olayı) |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Radcliffe - Chester | 2Y KG Yok | 1.24 | %68.7 | 1-3 (İY 0-0) | iki takım da 2. yarıda attı |
| 18:00 | İngiltere Ulusal Lig, Güney | Truro City - Dover | MS 1 | 1.24 | %68.6 | 3-3 (İY 0-2) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig | Boreham Wood - Gateshead | Ev İki Yarıda Gol | 1.21 | %68.5 | 3-1 (İY 0-1) | takım gol sayısı beklenti dışı |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Morecambe - Spalding Utd | 2Y KG Yok | 1.21 | %68.4 | 3-3 (İY 2-1) | iki takım da 2. yarıda attı |
| 18:00 | Norveç Eliteserien | Bodo Glimt - Kfum Oslo | 5.5 Alt | 1.23 | %68.3 | 6-0 (İY 3-0) | gol patlaması (kuyruk olayı) |
| 17:00 | İtalya Serie B | Carrarese C. 1908 - Juve Stabia | İY 0.5 Üst | 1.22 | %68.2 | 3-1 (İY 0-0) | golsüz ilk yarı |
| 18:30 | İspanya Primera RFEF | Logrones - Barakaldo | İY 0.5 Üst | 1.22 | %68.1 | 0-1 (İY 0-0) | golsüz ilk yarı |
| 20:00 | İsviçre Süper Lig | Grasshoppers - Basel | ÇŞ X2 | 1.25 | %68.0 | 2-1 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 1. Lig | Luton Town - Oxford | 2Y KG Yok | 1.22 | %67.8 | 2-2 (İY 0-1) | iki takım da 2. yarıda attı |
| 18:00 | Yunanistan Süper Lig | Volos - Asteras T. | 1.5 Üst | 1.28 | %67.7 | 0-0 (İY 0-0) | tek taraflı/golsüz maç |
| 18:00 | İngiltere Championship | Wrexham - Portsmouth | İY ÇŞ X2 | 1.21 | %67.7 | 1-0 (İY 1-0) | sonuç ters döndü (sürpriz) |
| 17:00 | Çekya 1. Lig | Mlada Boleslav - Sigma Olomouc | 3.5 Alt | 1.26 | %67.4 | 3-2 (İY 3-0) | gol patlaması (kuyruk olayı) |
| 18:00 | Portekiz 3. Lig A Grubu | Varzim - CD Trofense | İY 0.5 Üst | 1.22 | %67.2 | 0-1 (İY 0-0) | golsüz ilk yarı |
| 19:30 | İspanya Segunda RFEF | Barcelona B - Terrassa | İY 0.5 Üst | 1.24 | %67.2 | 2-1 (İY 0-0) | golsüz ilk yarı |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Buxton - Spennymoor | MS 1 | 1.21 | %67.0 | 2-3 (İY 1-1) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig, Güney | Slough Town - Tonbridge Angels | KG Var | 1.23 | %66.8 | 1-0 (İY 0-0) | tek taraflı/golsüz maç |
| 20:00 | Fransa Kupası | Chambly - US Avranches | Dep 0.5 Üst | 1.23 | %66.8 | 1-0 (İY 0-0) | takım gol sayısı beklenti dışı |
| 19:00 | Rusya Premier Lig | B. Kaliningrad - Akhmat Grozny | 1.5 Üst | 1.26 | %66.7 | 1-0 (İY 0-0) | tek taraflı/golsüz maç |
| 18:00 | İspanya Segunda RFEF | CD Ebro - Espanyol II | ÇŞ 1X | 1.28 | %66.3 | 0-1 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig | Eastleigh - Halifax Town | 2Y KG Yok | 1.21 | %66.3 | 3-1 (İY 0-0) | iki takım da 2. yarıda attı |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Chorley - Harborough Town | 2Y KG Yok | 1.21 | %66.3 | 4-1 (İY 1-0) | iki takım da 2. yarıda attı |
| 17:15 | BAE - Arap Körfez Ligi | Al Wasl - AL Dhafra Scc | Ev 3.5 Alt | 1.24 | %66.1 | 4-2 (İY 3-0) | gol patlaması (kuyruk olayı) |
| 17:30 | Slovakya Superliga | Dukla BB - Ruzomberok | ÇŞ X2 | 1.25 | %65.9 | 1-0 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 17:00 | Kuzey İrlanda Premiership | Crusaders - Linfield | DEĞİL(Dep Her İki Yarıyı Kazanır) | 1.24 | %65.8 | 0-3 (İY 0-1) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 1. Lig | S. Wednesday - Reading | 3.5 Alt | 1.26 | %65.8 | 1-4 (İY 1-2) | gol patlaması (kuyruk olayı) |
| 17:00 | Fransa Kupası | Epinal - Amiens | İY 0.5 Üst | 1.26 | %65.7 | 2-0 (İY 0-0) | golsüz ilk yarı |
| 20:00 | Senegal Premier Lig | AS Pikine - Stade de Mbour | ÇŞ 12 | 1.21 | %65.6 | 0-0 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 20:00 | İsviçre Challenge Ligi | Wil 1900 - Yverdon | 2Y KG Yok | 1.23 | %65.6 | 4-2 (İY 2-0) | iki takım da 2. yarıda attı |
| 18:45 | Bulgaristan Parva Ligi | Cherno More - Botev Plovdiv | ÇŞ X2 | 1.27 | %65.4 | 4-2 (İY 3-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 2. Lig | Salford City - Gillingham | MS 1 | 1.30 | %65.3 | 1-2 (İY 0-1) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 2. Lig | Rotherham - Oldham | ÇŞ X2 | 1.22 | %64.8 | 5-0 (İY 2-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 2. Lig | Crewe Alexandra - Grimsby Town | 3.5 Alt | 1.26 | %64.7 | 2-3 (İY 0-2) | gol patlaması (kuyruk olayı) |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Kings Lynn - Macclesfield | KG Var | 1.38 | %62.2 | 0-0 (İY 0-0) | tek taraflı/golsüz maç |
| 17:30 | Avusturya 2. Lig | Admira Wacker - Liefering | 2Y KG Yok | 1.37 | %61.7 | 2-1 (İY 1-0) | iki takım da 2. yarıda attı |
| 18:00 | İspanya Segunda RFEF | SD Eibar B - Marino  Luanco | MS 1 | 1.32 | %61.3 | 0-0 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 19:00 | İspanya Segunda RFEF | Coruxo - Gimnastica Torrelavega | MS 1 | 1.34 | %61.0 | 1-1 (İY 0-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere 2. Lig | Walsall - Northampton | ÇŞ X2 | 1.38 | %60.0 | 3-0 (İY 2-0) | sonuç ters döndü (sürpriz) |
| 19:30 | İtalya Serie C | U.S. Pergolettese - AS Giana E. | İY KG Yok & 2Y KG Yok | 1.34 | %59.6 | 2-1 (İY 1-1) | takım gol sayısı beklenti dışı |
| 19:00 | İspanya Segunda RFEF | Compostela - Bergantinos | ÇŞ X2 | 1.37 | %59.4 | 3-1 (İY 2-1) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig | Hornchurch - Solihull Moors | KG Var | 1.46 | %59.2 | 1-0 (İY 0-0) | tek taraflı/golsüz maç |
| 19:00 | İspanya Segunda RFEF | Ourense - SD Gernika Club | ÇŞ X2 | 1.41 | %58.8 | 3-0 (İY 1-0) | sonuç ters döndü (sürpriz) |
| 18:00 | İngiltere Ulusal Lig, Güney | Salisbury - Dagenham Red | KG Var | 1.42 | %58.7 | 0-0 (İY 0-0) | tek taraflı/golsüz maç |
| 18:00 | İngiltere Ulusal Lig | Boston Utd - Kidderminster Harriers | KG Var | 1.47 | %58.7 | 0-2 (İY 0-2) | tek taraflı/golsüz maç |
| 16:30 | İtalya Serie C | Ath Carpi - C. Lecco | KG Var | 1.46 | %58.4 | 0-0 (İY 0-0) | tek taraflı/golsüz maç |
| 18:00 | İngiltere Ulusal Lig, Kuzey | Oxford City - Southport | MS 1 & 1.5 Üst | 1.31 | %58.1 | 0-0 (İY 0-0) | tek taraflı/golsüz maç |

Kayıp türlerinin dağılımı: sonuç sürprizi (ÇŞ/MS/handikap/yarı kazanma, 18), gol patlaması (3.5/5.5 Alt, Ev/Dep 1.5 Alt, 9),
golsüz/tek taraflı maç (KG Var, 1.5 Üst, MS 1 & 1.5 Üst, 9), golsüz ilk yarı (İY 0.5 Üst, 7), 2Y'de iki takım da gol
(2Y KG Yok, 7), takım gol sayısı (3). Hiçbir tür aile/lig bazında arşiv beklentisinden sapmıyor (bölüm 4).

## 4) Hipotezler — büyük arşivde sızıntısız test (bugünün örnekleri yalnız hipotez kaynağı)

Veri: `data/matches.csv` (PR #37–#41 sonrası, 250 bin maç; Pinnacle kapanış 160 bin maç). Eğitim < 2023-07, test ≥ 2023-07
(4a, 4b); Pinnacle türev testi 2019/20+ (48.491 maç), test sezonları 2021/22+ (33.974 maç).

**4a. "3.5 Alt / maç alt-üst banko bacakları kötü" — REDDEDİLDİ.** Pinnacle 1X2 + 2.5'ten türetilen olasılıkla, P 0,70–0,80
bandında test: 3.5 Alt tahmin %74,7 / gerçek %74,8 (n 12.246); 1.5 Üst %75,2 / %75,0 (n 14.556). Alt ligler (EFL, Serie B,
Segunda vb.) ayrı: 3.5 Alt %74,7 / %74,9; 1.5 Üst %75,0 / %74,9. İkisi de kalibre; birini diğerine tercih için veri yok.

**4b. "Alt lig / İngiliz 5-6. kademe banko güvenilmez" — REDDEDİLDİ.** Bugün İngiliz Ulusal Lig seçimleri 31'de 17 (beklenen 20,2;
z ≈ −1,2). Arşivde (Pinnacle, 2021/22+, P 0,62–0,75) National League: tahmin %69,5 / gerçek %69,5; League One/Two,
Segunda, Serie B de ±0,3 puan içinde.

**4c. Korner Alt'ta güçlü favori etkisi — REDDEDİLDİ.** Korner modeline |p1−p2| eklendi (aylık ileri-yürüyen): doğrulamada
favori-Alt dilimi düzeldi (z −2,4 → −0,3) ama testte ters yöne kaydı (+0,3 → z +2,7). Mevcut model testte favori maçlarda
kalibre (P≥0,70 Alt: %80,6 / %80,7). Değişiklik yok.

**4d. MS/ÇŞ marj ayırma (favori-uzun ihtimal yanlılığı) — DEĞİŞİKLİK YOK.** Üretim zaten `power` yöntemini kullanıyor.
Pinnacle kapanışta orantısal yöntem favoriyi 0,70–0,80'de 3,3 puan küçümsüyor, power 2,0 puan (test, n 1.691, z ≈ 1,9).
Üstüne öğrenilmiş sıcaklık (t = 1,012) test log-loss'unu değiştirmedi (fark +0,000002, t 0,08). Sonuç: MS 1/2 banko
bacakları gösterilen P'den biraz daha güvenli; düzeltme eklenmedi.

**4e. Üretim türev kalibrasyonu Pinnacle girdilerde doğru mu? — DOĞRULANDI, 5 yeni eğri EKLENDİ.** Arşiv Platt eğrileri ortalama
büro oranlarıyla kurulmuştu; canlı motor Pinnacle'dan fiyatlıyor. `scripts/pinnacle_kalibrasyon_olcumu.py` aynı üretim
hattını (power + tırmıklı skor matrisi + omni tensör) Pinnacle kapanışla fiyatladı:
- Mevcut 38 eğrinin 25'i Pinnacle test sezonlarında log-loss'u anlamlı iyileştiriyor, hiçbiri kötüleştirmiyor; Pinnacle'la
  yeniden kurmak hiçbirinde daha iyi değil (14'ünde anlamlı kötü). Mevcut eğriler korundu.
- Eğrisi olmayan 76 türev seçime aynı tutma kuralı (OOS log-loss farkı %95 GA üst ucu < 0) + banko bölgesi koşulu
  uygulandı. Geçen 5 seçim eklendi: **Dep İY 0.5 Üst/Alt** (lig sapmalı; banko bölgesinde Dep İY 0.5 Alt %73,3 tahmin /
  %71,5 gerçek → eğriyle %73,3 / %72,8), **0.5 Üst ↔ Skor 0-0**, **İY/MS 0/0**, **En Çok Gol 2Y**. 1.5 Üst ve 3.5 Alt için eğri
  kuralı geçmedi (zaten kalibre).
- Banko bölgesinde üretim P'si: İY 0.5 Üst %73,7 tahmin / %74,6 gerçek; 2Y KG Yok %74,7 / %75,3 (ikisi de hafif temkinli).
- İzlemeye alınan (kuralı geçmedi): İY ÇŞ 1X 0,70–0,75 bandında −1,6 puan, 5 sezonun 5'inde eksi.

**4f. Yüksek oran motoru (İY/MS, skor, İY skoru, 2Y KG).** Yeni veriyle (İY verisi eklenen 11 lig) ileri-yürüyen test
yeniden koşuldu ve üretim kalibrasyonu yenilendi (`yuksek_oran_kalibrasyon.json`): lig İY payları artık gerçek veriden
(ör. Japonya 0,418, Danimarka 0,474, Norveç 0,467; önce hepsi genel 0,449). Test (2024-07+): İY/MS model−piyasa log-loss
−0,0032 (t −5,7), kesin skor −0,0037 (t −8,4), İY skoru −0,0006 (t −2,5), 2Y KG −0,0002 (t −1,4). Seçim bandı güvenilirliği
86/98.
- Bulgu: İY/MS'de model en olası hücreye ≥%50 verdiğinde gerçekleşme ~6 puan daha yüksek (n 935: %55,2 → %61,5); 35–50%
  bandında +1,6 puan. Denenen iki düzeltme **REDDEDİLDİ**: (i) favori kovasını 3'ten 5/7'ye çıkarmak (test log-loss −0,0002,
  t −1,2; doğrulamada t −0,3), (ii) hücre başı logit kalibrasyonu (t −0,2). Anlamlı değil → model değişmedi.
- Kesin skor 1-1 (%10–20 bandı): tahmin %12,7 / gerçek %12,8 — kalibre. İY 0-0 (%20–35): %28,4 / %28,3 — kalibre.

**4g. Sonuç notlayıcı hataları — DÜZELTİLDİ.** `leg_grading.grade` şu seçimleri hiç notlamıyordu (None): `Hnd(+1) …`
(artı işaretli handikap), `MS 1 & 1.5 Üst` (Nesine seçimi "1 & Üst" kısa yazılınca), "Her İki Yarıyı Kazanır",
"En Az Bir/Herhangi Bir Yarıyı Kazanır", "İki Yarıda Gol". Bunlar sonuç defterinde ve kalibrasyon ölçümlerinde eksik
kalıyordu. Testli düzeltildi.

## 5) Değişiklikler (bu PR)

| Değişiklik | Ölçüm | Karar |
|---|---|---|
| 5 yeni türev Platt eğrisi (Pinnacle, ileri-yürüyen) | OOS log-loss −0,0002…−0,0003, GA üst ucu < 0; banko bölgesi iyileşti/aynı | TUTULDU |
| Yüksek oran kalibrasyonu yeni veriyle yenilendi | İY/MS −0,0032 (t −5,7), ECE 0,0021 | TUTULDU |
| Notlayıcı düzeltmeleri | 16 yeni test | TUTULDU |
| MS sıcaklık düzeltmesi | Δlog-loss +0,000002 | REDDEDİLDİ |
| İY/MS 5/7 favori kovası | t −1,2 (test), −0,3 (doğrulama) | REDDEDİLDİ |
| İY/MS hücre logit kalibrasyonu | t −0,2 | REDDEDİLDİ |
| Korner + favori gücü | testte ters | REDDEDİLDİ |
| Lig kademesi büzmesi | arşivde sapma yok | REDDEDİLDİ |

## 6) Kupon kurma kuralı önerileri (skill'e uygulanabilir)

1. **Bacak sayısı en büyük risk.** Kupon tutma olasılığı = P'lerin çarpımı. 5 × %74 = %22; 8 bacak = %9; 20 bacak = %0,3.
   Hedef orana kısa oranlı bacak yığarak ulaşma; 2–4 bacak tercih et, kullanıcı ~5 isterse toplam P'yi açıkça yaz.
   Aynı hedefe az ve çok bacaklı seçenekleri yan yana hesapla, toplam P'si yüksek olanı öner (t206u).
2. **Aile tercihi bugünkü sonuçla değişmez.** 1.5 Üst, 3.5 Alt, İY 0.5 Üst, 2Y KG Yok, MS favori banko bölgesinde
   arşivde kalibre (±1 puan). "Maç alt/üstünü kupona az al" kuralı veriyle desteklenmiyor; 21:53 özetindeki aile farkları
   ortalama P farkından ve küçük örneklemden geliyor.
3. **MS 1/2 favori bacakları** (power marjsız P 0,70–0,80) gösterilenden ~2 puan daha güvenli; uygun oran varsa tercih edilebilir.
4. **Dep/Ev İY 0.5 Alt** (takım golü, banko dışı) artık eğriyle ~0,5 puan düşük gösterilecek; ana tahminde dikkat.
   **İY ÇŞ 1X** 0,70–0,75'te hafif fazla iyimser (izlemede).
5. **Yüksek oranlı pazarlar piyango:** kesin skor bacağı ~%12–14, İY skoru ~%30–36, İY/MS en olası hücre ~%35–45. İki skorlu
   kupon ≈ %2. Bunları yalnız kullanıcı isterse ve kasanın %0,5–1'iyle sun. İY/MS 1/1'de model ≥%50 diyorsa gerçek
   isabet daha yüksek (~%61); 2/2 kalibre.
6. **Tek günle kural değiştirme.** Bir aile/çizgi için karar ≥150 sonuçlanmış banko seçimi veya arşiv testiyle verilir.

## 7) Bekleyenler

Rapor anında 65 ana seçim ve gece maçları (Amerika, 29 Kas 00:00–04:00) sonuçlanmamıştı; bunlar daha sonra
`scripts/sonuc_defteri.py notla` veya aynı Nesine akışıyla notlanmalı.

## Yeniden üretim

```bash
QF_AILE_VARYANT=pinnacle python scripts/bahis_aileleri_kalibrasyon.py onbellek   # ≈45 sn, 8 çekirdek
python scripts/pinnacle_kalibrasyon_olcumu.py [--yaz]
python scripts/yuksek_oran_pazarlar.py backtest --half-lives 240                  # ≈4 dk
```
