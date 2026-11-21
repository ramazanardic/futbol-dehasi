# Akşam denetimi — 21 Kasım 2026

**Kesim:** 20:00 TSİ (Europe/Istanbul, UTC+3). Nesine biten-maç feed’i ve FotMob listesi 19:56–20:00 civarı çekildi. 20:00 maçları bu kesimde henüz başlamamıştı.

**Kaynaklar:** Nesine `GetUnliveMatches` (biten maç, İY + 90’); FotMob açık JSON (canlı ≥80’ geçici not, İY için `matchDetails`); ESPN public scoreboard (sabah `predictions.json`, `event_id` ile). API-Football kullanılmadı. SofaScore bu IP’den 403 verdi, kullanılmadı.

**Kapsam (dürüst):** Derin tarama 573 maç. Skoru netleşen 350 bitmiş + 20 geçici (≥80’ / uzatma) notlandı. 4 maç ertelendi/iptal (isabete katılmadı). 33 maç 80’ altında canlı, 15 maç 20:00’de başlamak üzere, 107 maç henüz başlamadı. **44 maç eşleşmedi / notlanamadı** — çoğunlukla İspanya 3. Federasyon (26), Kuzey İrlanda Championship (5), Afrika/küçük lig (8) ve birkaç alt lig; Nesine canlı skoru yayınlamıyor, FotMob’ta da yoktu ya da isim güvenli eşleşmedi. Bir yanlış eşleşme (Leonesa B ≠ Linares) bilinçli olarak geri alındı.

---

## A) Derin tarama — maç başı ana tercih (suitable, oran ≥ 1.20, en yüksek P)

Yalnız **bitmiş** maçlar (geçici ayrı):

| | Sayı |
|---|---:|
| Notlanan ana tercih | 320 |
| Doğru | **203** |
| Yanlış | **117** |
| İsabetsiz bırakılan (skorla çözülemedi) | 1 |
| İsabet | **%63,4** |
| Ortalama tahmin P | **%67,0** |
| Kalibrasyon farkı | **−3,5 puan** (biraz iyimser) |

İsabetsiz bırakılan tek ana tercih: **Khor Fakkan – AL Jazira, İlk Gol Dep**. MS 1-1, İY 0-0; ilk golün sahibi skorla belli olmuyor.

**Geçici (canlı ≥80’, ayrı):** 20 ana tercih, 11 doğru / 9 yanlış (**%55,0** vs ortalama P %67,2). Uzatmadaki 18:00 İngiltere alt lig maçları burada; skor hâlâ değişebilir. Örnek: Swansea–West Brom 97’ 2-2 (İY 1,5 Alt, İY 2-2, geçici yanlış); Zaragoza–Majadahonda 88’ 2-0 (MS 1, geçici doğru).

---

## B) Tüm suitable seçimler (oran ≥ 1.20)

| | Bitmiş | Geçici ≥80’ |
|---|---:|---:|
| Notlanan | 2.490 | 137 |
| Doğru / yanlış | 1.527 / 963 | 83 / 54 |
| İsabet | **%61,3** | %60,6 |
| Ortalama P | **%61,9** | %62,0 |
| Kalibrasyon | **−0,6 puan** (neredeyse kalibre) | −1,4 puan |

Bitmiş 350 maçın 29’unda suitable seçim yoktu; onlar bu tabloya girmedi. 10 seçim (hepsi “İlk Gol”) her iki takım da aynı yarıda gol atınca notlanamadı.

Tüm seçimlerde kalibrasyon iyi; ana tercihte P şişmesi var. Çünkü ana tercih çoğu zaman %65–72 bandındaki kısa oranlı seçimler ve bu bant beklenenin altında kaldı.

---

## Kalibrasyon (yalnız bitmiş ana tercihler)

| P bandı | n | Doğru | İsabet | Ort. P | Fark |
|---|---:|---:|---:|---:|---:|
| < %60 | 20 | 12 | %60,0 | %57,4 | +2,6 |
| **%60–65** | **46** | **23** | **%50,0** | **%63,2** | **−13,2** |
| %65–70 | 193 | 128 | %66,3 | %67,5 | −1,2 |
| %70–75 | 59 | 38 | %64,4 | %71,1 | −6,7 |
| %75+ | 2 | 2 | %100 | %75,8 | n=2, anlamsız |

En zayıf nokta **%60–65 bandı: 23/46 (%50)**. “Garanti” diye görülen %70–75 de 38/59 (%64). Büyük örnek %65–70’te neredeyse kalibre.

---

## Lig kademesi (bitmiş ana tercih)

Kademe, lig adından kaba sınıflama (otomatik; sınırda ligler “2-diğer”e düşebilir).

| Kademe | n | İsabet | Ort. P | Fark |
|---|---:|---:|---:|---:|
| 1 — büyük lig (PL, La Liga, Süper Lig, Serie A, Ligue 1, Bundesliga, Eredivisie, Premiership vb.) | 48 | 32/48 **%66,7** | %68,4 | −1,7 |
| 2 — ikinci/orta (Championship, 1–2. ligler, Serie B…) | 68 | 45/68 **%66,2** | %68,1 | −1,9 |
| 2 — diğer | 116 | 69/116 **%59,5** | %66,7 | −7,2 |
| 3 — alt / genç / kadın | 88 | 57/88 **%64,8** | %65,7 | −0,9 |

“Diğer” liglerde ana tercih belirgin iyimser. Büyük liglerde örnek küçük (birçok 18:00–20:00 maçı kesimde hâlâ canlı veya başlamamıştı).

---

## Bahis ailesi

**Ana tercih (bitmiş):** ev sahibi golleri 17/35 (**%48,6** vs P %67,3, −18,7 puan) ve çifte şans 17/34 (**%50** vs %65,5) en zayıf; deplasman golleri 31/55 (%56,4 vs %67,0). İlk yarı 32/42 (**%76,2** vs %68,2) ve maç sonucu 24/34 (%70,6 vs %64,6) daha iyi. 2Y KG Yok 17/19 iyi görünüyor ama örnek küçük, şişirme.

**Tüm seçimler (bitmiş, n≥20):** Alt/Üst 167/272 (%61,4, P %61,6, kalibre); ilk yarı 319/512 (%62,3, kalibre); maç sonucu 65/98 (%66,3 vs %62,1); karşılıklı gol 112/194 (%57,7 vs %61,7); ev golleri 215/370 (%58,1 vs %61,4).

---

## En net ana tercih kaçanları (bitmiş, yüksek P)

| Maç | Seçim | P | Oran | Skor (İY / MS) |
|---|---|---:|---:|---|
| Middlesbrough – Bristol City | DEĞİL(Ev Her İki Yarıyı Kazanır) | 0,726 | 1,20 | 1-0 / 2-0 (iki yarıyı da ev aldı) |
| Galatasaray – Samsunspor | 2Y KG Yok | 0,724 | 1,21 | 1-0 / **2-1** |
| Vihren – Pirin Blagoevgrad | Dep 0,5 Alt | 0,722 | 1,20 | 3-0 / **6-1** |
| Manchester City – Fulham | MS 1 | 0,717 | 1,22 | 0-1 / **1-1** |
| Hibernian – Dundee Utd | ÇŞ 1X | 0,716 | 1,20 | 0-2 / **0-4** |
| Bicskei – Tatabanya | MS 2 | 0,716 | 1,23 | 2-2 / 3-3 |
| Kilmarnock – Aberdeen | DEĞİL(Ev İki Yarıda Gol) | 0,713 | 1,20 | 1-3 / 2-4 |
| Wolfsburg – Holstein Kiel | Dep 0,5 Üst | 0,713 | 1,22 | 0-0 / **3-0** (dep gol atamadı) |
| Aston Villa – Sunderland | İY 0,5 Üst | 0,712 | 1,20 | **0-0** / 0-0 |
| West Ham – Preston | Dep İY 0,5 Alt | 0,711 | 1,21 | **0-1** / 1-1 (B10 yakan bacak) |
| HamKam – Fredrikstad | ÇŞ 12 | 0,711 | 1,20 | **0-0** / 0-0 |
| Sheffield Utd – Watford | Ev 2,5 Alt | 0,708 | 1,21 | 2-0 / **4-0** |
| Chelsea – Leeds | Dep 1,5 Alt | 0,708 | 1,21 | 1-1 / **1-4** |
| Reading – Bromley | MS 1 | 0,705 | 1,21 | 0-0 / **0-1** |

City’nin 1-1’i, Hibernian’ın 0-4’ü, Villa’nın 0-0’ı ve West Ham iç saha İY’de gol yemesi “kısa oranlı banko” varsayımını bozan sonuçlar.

---

## C) 19:33’te verilen 10 “en garanti” tercih

Kesim anında **hiçbiri bitmemişti.** Lugano–Grasshoppers 20:00’de başlamak üzereydi; diğerleri 20:30–04:00. Not yok, şişirme yok.

| Maç | Seçim | Başlangıç (TSİ) | Durum |
|---|---|---|---|
| Lugano – Grasshoppers | MS 1 | 20:00 | Başlamak üzere |
| Sevilla – Real Betis | 3,5 Alt | 20:30 | Başlamadı |
| Feyenoord – Excelsior | Dep İY 0,5 Alt | 20:45 | Başlamadı |
| Mechelen – Club Brugge | MS 2 | 22:45 | Başlamadı |
| Strasbourg – Brest | İY 0,5 Üst | 22:45 | Başlamadı |
| RC Lens – Toulouse | Ev iki yarıda gol atamaz | 22:45 | Başlamadı |
| Lille – Lyon | ÇŞ 1-2 | 22:45 | Başlamadı |
| Real Madrid – Celta Vigo | 2,5 Üst | 23:00 | Başlamadı |
| Inter Miami – Columbus | 4,5 Alt | 02:00 | Başlamadı |
| Pumas – Monterrey | İY 0,5 Üst | 04:00 | Başlamadı |

---

## D) Bugün oynanan kuponlar

Toplam yatırılan 1.370 TL. Kesimde **9 kupon kaybetti (970 TL)**, 2 kupon hâlâ açık (400 TL: MS10 100 TL, K2000 300 TL). Kazanan kupon yok, iade 0.

| ID | Tutar | Oran | Durum | Bacak (D/Y/bek) | Yakan / not |
|---|---:|---:|---|---|---|
| K1 | 50 | 24,97 | **KAYBETTİ** | 0/1/2 | Radnik Bijeljina – Velez **1-1**, MS 2 yattı. Espanyol B 20:00’de bekliyor (artık önemsiz). |
| K3 | 50 | 26,11 | **KAYBETTİ** | 2/1/0 | Gala 2-1, “2,5 Üst & KG Yok” yattı (KG var). Soton 2-0 ve Charleroi 2-2 (geçici) tuttu. |
| K4 | 50 | 24,72 | **KAYBETTİ** | 1/2/0 | Fleury 1-0 (MS 0 yattı); Vallecano 0-1 geçici, “MS 1 & 2,5 Üst” yattı. Bolton 1-1 tuttu. |
| K5 | 50 | 20,49 | **KAYBETTİ** | 0/1/2 | **Carrarese 1-0**, MS 0 yattı. CSKA hâlâ 80’ altı; Yeovil 20:30. |
| K6 | 50 | 20,82 | **KAYBETTİ** | 1/2/0 | Norwich İY 0-0 (İY 2 yattı). Millwall İY 0-1 tuttu. Elche B **2-2**, MS 2 de yattı. |
| **B5** | **400** | 7,27 | **KAYBETTİ** | 1/1/3 | **Barendrecht 2-3**, MS 1 yattı. Coleraine 1-3 tuttu. Antequera canlı <80; GAK ve Lille başlamadı. |
| MS10 | 100 | 7,67 | **açık** | **5/0/5** | Tutulan: Ljubljana 1-0, Zilina 2-0, Truro 4-0, Dungannon 3-1, Zaragoza 2-0 (geçici). Lugano 20:00; Bükreş, Castellon, Larne, CD Fas bekliyor. Henüz yanan bacak yok. |
| CANLI | 70 | 7,64 | **KAYBETTİ** | 0/3/0 | Kokand 0-1, Khor Fakkan 1-1, Reading 0-1 (üçü de yandı). |
| A5 | 100 | 5,00 | **KAYBETTİ** | 1/2/2 | Milan kadın 3-2 (3,5 Alt); Sturm Amt. **1-1** (2,5 Üst yattı). Lazio 3-0 tuttu. Catanzaro canlı; Napoli 22:45. |
| B10 | 150 | 6,84 | **KAYBETTİ** | 2/2/6 | **Hibernian 0-4** ÇŞ 1X ve **West Ham İY 0-1** Dep İY 0,5 Alt. Linfield 5-0 ve Stoke İY 0-0 tuttu. |
| K2000 | 300 | 7,21 | **açık** | 0/0/5 | İlk bacak Pontevedra 20:45. Hepsi bekliyor. |

18:33 denetimine göre yeni yanan büyük kupon: **B5 (400 TL, Barendrecht 2-3)**; ayrıca K1 (Velez berabere) ve K5 (Carrarese).

---

## Sabah `predictions.json` (122 maç, 11:42, ESPN)

Ayrı hat: her maçta Nesine’de sunulan oran ≥ 1,20 olan piyasalar içinden en yüksek P’li seçim. ESPN skorboard’u ~19:50 kopyası (canlı çekim 403 verdi).

- Bitmiş 31 ana tercih: **19 doğru / 12 yanlış (%61,3)**, ortalama P %61,0 (kalibre).
- Geçici 44: 32/44 (%72,7) — uzatma/geç karar, resmi değil.
- 38 başlamamış, 6 canlı <80’, 3 seçimsiz / ESPN’de yok.

Bitmiş kaçanlar arasında: Man City MS 1 (1-1), Reading MS 1 (0-1), Gençlerbirliği 2,5 Üst (1-0), Frankfurt 3,5 Üst (1-0).

---

## Ertelenen / notlanamayan

**Void (4):** Borussia M’gladbach II – Bonner (Ert.), Spartans Edinburgh – Dumbarton (PP), Dunfermline – Morton (PP), Warrington Town – Guiseley (PP).

**Eşleşmeyen 44:** ağırlık İspanya 3. Federasyon ve benzeri alt ligler + Kuzey İrlanda Championship + Senegal/Fas/Etiyopya/Ürdün/Malta/Andorra. Bilinçli olarak zorlama eşleşme yapılmadı.

---

## Kısa hüküm

Bugünün bitmiş ana tercihlerinde isabet **%63,4**, modelin söylediği **%67,0**. Felaket bir sapma değil ama “banko” dili abartılı: %60–65 bant 23/46 (%50), City 1-1, Hibernian 0-4, Villa 0-0, West Ham İY’de gol yedi. Tüm 2.490 seçimde kalibrasyon neredeyse düz (%61,3 vs %61,9).

Oynanan kuponlarda kesimde **970 TL** yatmış görünüyor (B5’in 400 TL’si dahil); açıkta 400 TL (MS10’daki 5/5 devam ediyor, henüz yanmadı; K2000 başlamadı). 19:33’teki 10’lu listenin hiçbiri bu kesimde bitmedi.

Yarın sabah `gun_degerlendirme.py` resmi 90’ sonuçlarıyla bir kez daha bakılmalı; geçici 20 maç ve 20:00 sonrası kart bu rapora dahil değil.
