# Veri kapsam denetimi — 28 Kasım 2026

Modelin eğitildiği ve kalibre edildiği her kaynak, lig × sezon matrisine göre tarandı ve bugünün Nesine bülteni (383 maç, 95 lig, `nesine_global` 17:42 TSİ) ile karşılaştırıldı. Bu rapor commit edilmedi. Ayrıntılı sayılar: `veri_kapsam_lig_ozet.csv`, `veri_kapsam_mac_sezon.csv`.

**Kısa hüküm:** Büyük beşli + football-data çekirdeği (İngiltere 5 kademe, Bundesliga 1–2, La Liga, Segunda, Serie A/B, Ligue 1/2, Süper Lig, Eredivisie, Primeira Liga, Belçika, İskoçya, Yunanistan) 2000’den beri skor, İY ve kapanış 1X2 ile dolu; korner/şut çoğu ligde ~2017’den sonra. Asıl boşluk üç yerde: (1) eğitim dosyasına hiç girmeyen ama kuponlarda sürekli çıkan orta Avrupa ve alt kademe ligler, (2) `matches.csv` içindeki “yeni ligler”de İY/korner/Alt-Üst’ün hiç olmaması, (3) bu sezon Portekiz ve Rusya sonuçlarının güncel olmaması. Repoda 646 bin maçlık ek arşiv var; BENIOKU’nun yazdığı gibi **model eğitimi bunu henüz kullanmıyor**.

---

## 1. Modelin baktığı kaynaklar

| Kaynak | Ne işe yarıyor | Kapsam (bugün) | Eğitimde var mı? |
|---|---|---|---|
| `data/matches.csv` (HuggingFace club-football-match-data + `arsiv_guncelle.py`) | Ana eğitim/kalibrasyon, Elo, form, korner modeli, İY/MS ve skor modelleri, pazar eğrileri | 250.608 maç, 38 lig, 2000-07-28 – 2026-11-27 | Evet |
| `data/global_odds/latest/season_2627/*.csv` (football-data.co.uk) | Bu sezon sonuç + Pinnacle kapanış (PSH/PSCH), İY, korner | 22 lig, 2.450 satır; son çekim 22 Kas 09:21 UTC | `include_season_history=True` iken evet; geriye dönük testte kapalı |
| `data/global_odds/latest/new_leagues/*.csv` | “Yeni lig” 1X2 kapanış (AvgC/MaxC, bazen PSCH) | 16 ülke dosyası; İY ve korner **yok** | `arsiv_guncelle` ile matches.csv’ye ekleniyor |
| `data/global_odds/latest/references.json` | Canlı keskin kapanış (Pinnacle/borsa) | 849 referans; **üretilme 22 Kas 09:21 UTC (~6 gün eski)** | Canlı fiyatlama |
| OddsMath (canlı, arşiv değil) | Günlük Nesine eşlemesi | Bugün 412 maçta canlı oran | Canlı; tarihçe yok |
| `data/arsiv/maclar.csv.gz` | openfootball, ESPN, Wikipedia, footballcsv, football-data 1993–2000 | 646.594 maç, 620 yarışma, 1888–2026; 149.925’inde İY | **Hayır** (BENIOKU) |
| `data/gfi/*` | Lig taban oranları, İY gol payı (223 lig) | Agregat; `wr:*` son maç çoğu 2025-09-30; GFI varsayılan **kapalı** | Kapalı (`QF_GFI_PRIORS=1`) |
| `data/form/takim_son120_form.csv` | Son 120 gün formu | 2.399 satır | Kapalı (`QF_RECENT_FORM`) |
| `data/tipsaudit.csv` | Pinnacle açılış/kapanış + soft kapanış | 7.390 maç, 84 lig, **yalnız 11 Haz – 27 Eki 2026** | Yardımcı / CLV |
| `data/international_results.csv` (martj42) | Milli maçlar | 49.940, 1872 – 2026-10-06 | Milli; kulüp bankoya girmez |
| `data/calibration/*` | Pazar, korner, canlı kalibrasyon | Korner: 37.358 maç, son 27 Kas; canlı kalibrasyon 19–21 Kas, 866 maç | Evet |
| Araştırma notları | Kupon öncesi veto/uyarı | Bugün 41 not | P’yi değiştirmez, eleyici |
| Defter / `takip_kayit` | Oturmuş Nesine tahminleri | Defter: 13 bacak (21 Kas). Takip dosyaları birkaç gün. Çok az. | Henüz yeniden kalibrasyon için yetersiz |

API-Football geçmiş için kullanılmıyor (ücretsiz plan 60 istek/gün, yalnız maç öncesi). Transfermarkt, Sofascore, FBref, Understat, FotMob arşivi kullanım şartı/bot koruması nedeniyle alınmıyor; bu yüzden maç bazlı xG yok (şut vekili denendi, 28 Kas ölçümünde kazanç yok, kapalı).

`matches.csv` içindeki `OddHome/OddDraw/OddAway` genel/ortalama kapanış; Pinnacle kapanışı (`PSH`/`PSCH`) sezon CSV’lerinde var, ana dosyaya ayrı sütun olarak girmiyor.

---

## 2. `matches.csv` — lig özeti

38 lig, 250.608 maç. “Çekirdek” (football-data klasik kodları) İY skorunda ~%100, 1X2 oranında ~%97–99, 2,5 Alt/Üst’te ~%82–99 (çoğu 2012’den sonra). “Yeni ligler” (ARG, AUT, BRA, CHN, DEN, FIN, IRL, JAP, MEX, NOR, POL, ROM, RUS, SUI, SWE, USA) yalnız FT skor + 1X2/max oran taşır; **İY, korner, kart, şut, 2,5 Alt/Üst hepsi %0**.

| Lig | n | İlk–son | Sezon | İY % | Korner % | 1X2 % | 2,5 A/Ü % | Bayat (gün) |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| E0 Premier Lig | 9900 | 2000-08-19 – 2026-11-23 | 27 | 100 | 100 | 99 | 82 | 5 |
| E1 Championship | 14362 | 2000-08-12 – 2026-11-25 | 27 | 100 | 100 | 99 | 82 | 3 |
| E2 / E3 / EC | 13,9k / 13,5k / 7,9k | 2000/2011 – 24–25 Kas | 27/16 | 100 | 100 / 100 / 38 | 98–99 | 83–99 | 3–4 |
| D1 Bundesliga | 7918 | 2000-08-11 – 2026-11-22 | 27 | 100 | 96 | 99 | 82 | 6 |
| D2 | 7575 | 2000-08-11 – 2026-11-22 | 27 | 100 | 48 | 99 | 86 | 6 |
| SP1 / SP2 | 9517 / 11121 | 2000 – 2026-11-23 | 26 | 100 | 81 / 39 | 99 / 97 | 81 / 84 | 5 |
| I1 / I2 | 9512 / 10431 | 2000 – 23–25 Kas | 27 | 100 | 85 / 34 | 99 / 97 | 85 / 87 | 3–5 |
| F1 / F2 | 9161 / 9100 | 2000-07-28 – 22–23 Kas | 27 | 100 | 80 / 36 | 99 / 96 | 85 / 86 | 5–6 |
| T1 Süper Lig | 7872 | 2000-08-11 – 2026-11-23 | 26 | 100 | 40 | 97 | 82 | 5 |
| N1 Eredivisie | 7711 | 2000-08-18 – 2026-11-22 | 27 | 100 | 36 | 99 | 83 | 6 |
| P1 Primeira Liga | 7030 | 2000-08-18 – **2026-11-08** | 26 | 100 | 41 | 99 | 81 | **20** |
| B1 Belçika | 6978 | 2000-08-12 – 2026-11-22 | 27 | 100 | 38 | 99 | 83 | 6 |
| SC0–SC3 İskoçya | 5,4k–4,3k | 2001 – 21–24 Kas | 26 | 100 | 100 / ~40 | 99 | 86–88 | 4–7 |
| G1 Yunanistan | 4440 | 2005-08-27 – 2026-11-23 | 19 | 99 | 38 | 98 | 99 | 5 |
| AUT / SUI | 2716 / 2759 | 2012 – 2026-11-22 | 16 | **0** | **0** | 100 | **0** | 6 |
| RUS | 3416 | 2012-01-09 – **2026-08-02** | 16 | **0** | **0** | 98 | **0** | **118** |
| POL / ROM / DEN / NOR / SWE | 3,0–4,3k | 2012 – 22–23 Kas | 16 | 0 | 0 | 100 | 0 | 5–6 |
| ARG / BRA / MEX / USA / JAP | 4,7–6,5k | 2012 – 25–27 Kas | 16 | 0 | 0 | 100 | 0 | 1–3 |
| CHN / FIN / IRL | 2,7–3,0k | 2012/14 – **2026-11-07/08** | 14–16 | 0 | 0 | 100 | 0 | 20–21 |

CHN/FIN/IRL yaz ligleridir; kasım başı kapanmış olabilir (bayatlık tek başına alarm değil). P1 ve RUS devam eden sezonlardır.

Kornerlerin %80’i geçen ilk sezon (çekirdek): E0–E3 ve SC0 baştan beri; D1/F1/I1/SP1 ≈ 2005–2012; T1, N1, P1, B1, D2, I2, F2, SP2, G1, SC1–SC3, EC çoğunlukla **2017/18’den sonra**. Korner modeli (`n_egitim=37.358`) bu yüzden dar bir lig kümesinde eğitildi.

---

## 3. Sezon delikleri ve bozuk alanlar

Son yedi sezonun maç sayıları (`veri_kapsam_mac_sezon.csv`):

- **Yunanistan (G1):** `2011/12` yok; **`2022/23` ve `2023/24` tamamen boş** (0 maç). `2024/25` geç başlıyor (22 Kas) ve yalnız 156 maç (tam sezon ~240). İY/korner kalibrasyonu bu ligde kırık.
- **İngiltere Ulusal Lig (EC):** `2024/25` yalnız 180 maç; önceki/sonraki sezonlar 552.
- **Rusya 2026/27:** 16 maç, son tarih **2 Ağustos 2026**. Sezon devam ediyor (bugün Kaliningrad–Akhmat bültende). football-data “yeni lig” dosyası da aynı tarihte kesiliyor. Buna karşılık arşivdeki `espn/rus.1` **22 Kasım’a** kadar dolu (3.704 maç, İY yok).
- **Portekiz P1 2026/27:** 98 maç, son tarih **8 Kasım** (20 gün geri). Hem `matches.csv` hem `season_2627/P1.csv` aynı. football-data.co.uk gecikmiş görünüyor. Arşiv `espn/por.1` **27 Kasım’a** kadar güncel (İY yok).
- Avusturya açıkfootball Bundesliga ve İsviçre Super Lig arşivi 20 Eylül’de duruyor; ESPN karşılıkları 27–28 Kasım’a kadar geliyor.
- “Yeni lig” dosyalarının hiçbirinde İY veya korner sütunu yok (yapısal, sezon deliği değil).
- Wikipedia matrisleri (163 bin satır) çoğunlukla **tarihsiz** ve İY’siz; 164.040 arşiv satırının tarihi boş. Eğitimde kullanılmıyor.

Lig küçülmeleri (F1 2023/24’te 380→306, 18 takıma iniş) gerçek fixture değişikliği, delik değil.

---

## 4. Bayatlık (28 Kas itibarıyla)

| Kaynak | Son tarih | Sorun |
|---|---|---|
| `references.json` / GitHub Actions global-odds | 22 Kas 09:21 UTC | ~6 gün eski; canlı keskin kapanış gecikiyor (OddsMath bugünü kısmen kurtarıyor) |
| football-data çekirdek sezon CSV | çoğu 21–25 Kas | Normal (1–6 gün); **P1 8 Kas** |
| football-data RUS yeni lig | 2 Ağu | 118 gün |
| `matches.csv` genel max | 27 Kas | Meksika/ABD güncel; Avrupa çekirdeği 22–25 Kas |
| GFI `wr:*` agregat | çoğu 2025-09-30 | Bir yıldan eski; ayrıca varsayılan kapalı |
| tipsaudit | 27 Eki 2026 | Son bir ay yok |
| Canlı kalibrasyon | 19–21 Kas (26 Kas’ta üretilmiş) | 866 maç, yalnız üç gün; 28 Kas kuponları henüz yok |
| Araştırma notu etkisi | n=41 | Kural: n&lt;50 iken sonuç çıkarma |

---

## 5. Ek arşiv — var ama eğitimde yok

`data/arsiv` 646.594 tekrarsız maç (openfootball CC0, ESPN sonuç satırı, Wikipedia CC BY-SA, footballcsv, football-data 1993–2000). İY skoru 149.925 maçta var (~%23; openfootball liglerinde genelde %90+). **Oran, korner, şut yok.**

Nesine’de sık çıkan ve `matches.csv`’de olmayan (veya çok eksik) ligler için arşiv durumu:

| Lig (Nesine) | Arşiv | Son tarih | İY | Not |
|---|---|---|---|---|
| Avusturya 2. Lig | `austria/2-liga2` (1.776) | 2025-11-02 | %94 | Bu sezon (2026/27) yok |
| İsviçre Challenge Lig | `europe/switzerland/ch2` (670) | 2025-03-16 | %94 | 2024/25 bile yarım; ESPN’de ch2 yok |
| Hırvatistan 1. HNL | `europe/croatia/hr1` (360) | 2025-05-25 | %91 | Yalnız 2023/24–2024/25 |
| Slovenya PrvaLiga | `si1` (360) | 2025-05-25 | %93 | Aynı, bu sezon yok |
| Bosna Premier Lig | `ba1` (396) | 2025-05-31 | %95 | Aynı |
| Macaristan 1. Lig | `hu1` (792) | 2025-05-25 | %93 | 2018/19–2024/25; bu sezon yok |
| Çekya 1. Lig | `cz1` (1.207) | 2026-09-20 | %93 | Bu sezon var, 2 ay geride |
| Slovakya / Sırbistan | `sk1` 387, `rs1` 592 | May 2025 | ~%92 | Bu sezon yok |
| Almanya 3. Lig | `deutschland/3-liga3` (4.267) | 2025-11-02 | %92 | Bu sezon yok |
| İtalya Serie C | `italy/3-seriec_a/b/c` (~925) | 2025-03-23 | ~%90 | Tek sezon, yarım, 2024/25 |
| Türkiye 1. Lig | `europe/turkey/tr2` (311) | 2020-07-30 | %90 | Yalnız 2019/20 |
| Rusya | `espn/rus.1` (3.704) | **2026-11-22** | %0 | football-data boşluğunu doldurur |
| Portekiz 1 | `espn/por.1` (2.199) | **2026-11-27** | %0 | P1 20 günlük gecikmeyi doldurur |
| MLS / Libertadores | ESPN + openfootball | 2026-10/11 | 0 | Skor var, İY/oran yok |
| Kosta Rika, Guatemala, Honduras, El Salvador | ESPN `crc/gua/hon/slv.1` (3,8–5,1k) | 23–28 Kas | 0 | Orta Amerika skor tarihi var |
| İspanya Primera/Segunda RFEF, 3. Federasyon | Yok | — | — | Bugün bültende 11+28+32 maç |
| Portekiz 2. Lig / 3. Lig | Yok (por.2 ESPN’de de yok) | — | — | |
| İsviçre Challenge, Avusturya 2 bu sezon | ESPN’de de yok | — | — | En kritik operasyonel boşluk |

GFI tablosunda `at.2`, `ch.2`, `de.3`, `tr.2`, `hu.1`, `cz.1`, `wr:croatia/slovenia/bosnia/serbia/slovakia` agregat taban oranları **var** ama GFI kapalı ve `wr:*` Eylül 2025’te duruyor.

---

## 6. Bugünkü Nesine bülteni ile karşılaştırma

28 Kas: 95 lig, 383 maç. `NESINE_TO_DIVISION` yalnız ~24 ismi football-data koduna bağlar; eşleşmeyen lig lig-özel kalibrasyon eğrisi alamaz (küresel eğri).

**Çekirdek tarihçe iyi (A):** Premier Lig, Championship, Lig 1–2, Ulusal Lig (kuzey/güney hariç), Bundesliga 1–2, La Liga, 2. Lig, Serie A/B, Ligue 1, Süper Lig, Eredivisie, Primeira Liga (son 20 gün eksik), Belçika, İskoçya Premiership, Yunanistan.

**matches.csv’de var, İY/korner yok (B):** Avusturya Bundesliga, İsviçre Süper Lig, Rusya (bayat), Polonya, Romanya, Norveç, MLS playoff (USA), Meksika, Arjantin, Brezilya, Şili yok (sadece ESPN arşiv).

**Arşivde skor var, eğitimde yok veya durmuş (C) — kuponlarda sık çıkıyor:** Avusturya 2. Lig, İsviçre Challenge Lig, Hırvatistan, Slovenya, Bosna, Macaristan, Çekya, Slovakya, Sırbistan, Almanya 3. Lig, Serie C (zayıf), Türkiye 1. Lig (neredeyse yok), Libertadores, Orta Amerika.

**Neredeyse hiç tarihçe yok (D) — bugünün hacmi burada:**

| Lig | Bugün maç |
|---|---:|
| İspanya 3. Federasyon | 32 |
| İspanya Segunda RFEF | 28 |
| İskoçya Kupası | 19 |
| İspanya Gençler Onur Klasmanı | 13 |
| İngiltere Ulusal Lig Güney / Kuzey | 12+12 |
| İngiltere Isthmian / Güney / Kuzey Premier | 11+11+10 |
| İspanya Primera RFEF | 11 |
| İtalya Serie C | 5 (arşiv zayıf) |
| Portekiz 2. Lig / 3. Lig | 3+2 |
| Senegal, Yeni Zelanda, Bahreyn, Umman, Ürdün, Irak, Malta, Andorra, Galler, Azerbaycan, Arnavutluk, Fas 2, Fransa U19, vs. | 1–6 |

Bugün oynanan ve “tarihçesiz / zayıf” sınıfa giren örnek kupon ligleri: Wil–Yverdon (Challenge), Blau Weiss Linz / Lustenau (Avusturya 2), Mura, Osijek, Lumezzane, Ospitaletto (Serie C), Algeciras / Extremadura (Primera RFEF), Muğlaspor (Türkiye 1. Lig). Banko P’si keskin piyasadan geldiği için skor arşivi kapanış oranının yerini tutmaz; ama lig-özel kalibrasyon, form, İY/korner modeli ve “ölü maç” teşhisi bu liglerde kör çalışır.

---

## 7. Önerilen iyileştirmeler (banko isabetine göre)

Hepsi ücretsiz, izinli kaynak. API-Football geçmiş doldurmak için uygun değil (60/gün × ~300 maç/lig/sezon = aylar; zaten yalnız maç öncesi).

### 1. Portekiz ve Rusya bu sezonunu ESPN sonuçlarıyla doldur (etki: yüksek, efor: düşük)

football-data P1 8 Kas’ta, RUS 2 Ağu’da kesilmiş; `espn/por.1` 27 Kas’a, `espn/rus.1` 22 Kas’a kadar hazır (repoda var). Primeira Liga bugün kuponlarda var; Rusya da bültende. İY/korner yine olmaz ama Elo, form, “son sonuç” ve basit Poisson güncel kalır. Kaynak: ESPN herkese açık scoreboard (mevcut `arsiv_espn_tara.py`, kimlik yok, nazik hız). İstek limiti yok (mevcut kazıyıcı ~3 istek/sn kuralına uyuyor).

### 2. Mevcut arşivi orta Avrupa ligleri için eğitime bağla (etki: yüksek, efor: orta)

Avusturya 2, İsviçre Challenge, HNL, PrvaLiga, Bosna, Macaristan, Çekya, Slovakya, Sırbistan, Almanya 3. Lig, kısmen Serie C. Skor + çoğu İY zaten repoda. Yapılacak: takım adı eşlemesi, lig kodu, `load_matches` / form / lig yarı payı / pazar kalibrasyonuna “odds’suz lig” yolu. Kapanış oranı olmadığı için EV kalibrasyonu değil, gol/İY öncülü ve form. Banko bacaklarının bir kısmı tam bu liglerden geliyor. Kaynak: openfootball (CC0) + mevcut arşiv. Maliyet: 0 istek (yerel dosya). Sonra 2025/26–2026/27 için açıkfootball/ESPN tazelemesi gerekir (birçok dosya Mayıs 2025’te duruyor; Challenge Lig 16 Mart 2025).

### 3. football-data sezon senkronunu ve `references.json` tazeliğini onar (etki: yüksek, efor: düşük, operasyon)

Global-odds 22 Kas’tan beri yenilenmemiş (bilinen uyarı: 148 saat). Çekirdek liglerde İY+korner+Pinnacle kapanış 1–6 gün geride kalabiliyor; P1 gibi kaynak gecikmeleri görünmeden uzuyor. GitHub Actions’ı düzeltmek veya günlük `arsiv_guncelle` + referans çekimini kutuda çalıştırmak. Kaynak: football-data.co.uk (ücretsiz, robots izinli). Pinnacle kapanış sütunlarını (`PSH`/`PSCH`) `matches.csv`’ye taşımak da aynı işin parçası — keskin kapanışla kalibrasyon bugünkü ortalama orandan daha temiz olur.

### 4. Bu sezonu ESPN/openfootball ile “C” liglerine yaz (etki: orta-yüksek, efor: orta)

Challenge Lig, Avusturya 2, HNL, PrvaLiga, Bosna, Macaristan, 3. Lig, Türkiye 1. Lig, Serie C için 2025/26 ve 2026/27 sonuçları. ESPN’de aut.2 / sui.2 / cro / svn / bih / hun / ger.3 / ita.3 / tur.2 **şu an katalogda yok**; openfootball güncellemesi veya Wikipedia sezon sayfası (CC BY-SA, robots izinli, ~3 istek/sn; matrislerde tarih/İY çoğu kez yok) gerekir. OpenLigaDB (Almanya/Avusturya, ücretsiz API) 3. Lig ve Avusturya 2 için uygun aday. Limit: ESPN/Wikipedia nazik tarama; OpenLigaDB herkese açık. API-Football’a başvurma.

### 5. GFI öncülünü, n birikince, yalnız boş liglerde tekrar ölç (etki: orta, efor: düşük)

`at.2`, `ch.2`, `de.3`, `tr.2`, `hu.1`, `cz.1` ve `wr:croatia` vb. taban oranları duruyor ama bayrak kapalı (28 Kas ölçümü çekirdekte kazanç göstermedi). Boş lig alt kümesinde yeniden `gfi_etki_olcumu.py` — yeni veri çekmeden. `wr:*` 2025-09-30’da durduğu için 2026 sezonu için zayıf kalır; yine de hiç öncül olmamasından iyidir.

### Bilerek sonraya bırakılanlar

- **RFEF, Portekiz 2/3, İngiltere 6–7. kademe, İskoçya Kupası:** Bugün hacim büyük ama banko kalitesi düşük; ücretsiz, düzenli, İY+oranlı kaynak yok. Düşük öncelik.
- **xG / FBref / Understat / Transfermarkt:** Şart ihlali. Şut vekili zaten denendi, kapalı.
- **API-Football geçmişi:** 60/gün ile yıllarca sürer; kadro/sakat için maç öncesi bütçeyi yakmamalı.
- **Oturmuş Nesine kupon defteri:** 13 bacak. Araştırma notu ve pazar güvenirliği için 50–150 oturmuş bacak beklenmeli (zaten planda).
- **Orta Amerika ESPN skorları:** Gece kuponlarında işe yarar; banko çekirdeği değil. Düşük eforla form katmanına eklenebilir (4. maddenin yan ürünü).

---

## 8. Sonuç

Eksik, “hiç veri yok” değil: çekirdek ligler 25 yıllık ve alan olarak zengin. Bankoyu asıl zayıflatan şey, Nesine’nin her gün fiyatladığı orta liglerin eğitim setine girmemesi, yeni liglerde İY/kornerin hiç olmaması, Portekiz/Rusya’nın bu sezon kesilmesi ve keskin referans dosyasının 6 gündür yenilenmemesi. İlk üç adımın verisi büyük ölçüde zaten repoda veya aynı ücretsiz boru hattında.
