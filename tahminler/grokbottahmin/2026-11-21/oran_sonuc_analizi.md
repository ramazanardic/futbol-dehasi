# 21 Kasım 2026 — Oran profilleri ve sonuçlar

Üretilme: 2026-11-21 21:34 (Europe/Istanbul).

## Kapsam

Evren, bugünkü derin taramadaki **573 maç**. Sonuçlar Nesine `GetUnliveMatches` ile tazelendi (20:57'deki 414 bitmiş maç artık **434**).

- Analize giren (bitmiş + 1-X-2 oranı var): **427**
- Bunlardan Nesine bülten oranı: **418**
- Nesine oranı olmadığı için sharp (OddsMath) `ref_1x2` kullanılan: **9**
- Bitmiş ama tam 1-X-2 kurulamayan: **7**
- Henüz bitmemiş, ertelenmiş veya skor eşleşmeyen: **139** (73 başlamadı, 29 hâlâ canlı/unlive'da yok, 24 eşleşmedi, 9 bekliyor, 4 ertelendi/kaldı)

Tam 1-X-2'si olmayan 7 bitmiş maç (hepsi ev kazandı): Nasaf–Mashal 2-0, Dorogi–Kiraly Sze 4-1, Gyulai–BKV Elore 4-0, Mosonmagyar.–Balatonalmadi 7-0, Nejmeh–AL Mabarrah 1-0, Vihren–Pirin 6-1, NK Brezice–NK Bilje 3-1. İlk altısında Nesine bülteninde MS 0 ve MS 2 vardı, **MS 1 açık değildi**; Brezice bültende hiç yoktu. Sharp yedek de bulunamadı, analize alınmadılar.

Sharp yedek kullanılan 9 maç (Nesine MS yok, OddsMath `ref_1x2`): 8'inde çok kısa favori kazandı, F. Karagümrük–Boluspor (1,23 / 7,37 / 18,54) 0-0 bitti.

Oran kuralı: her maç için **kickoff öncesi en son Nesine MS 1 / 0 / 2** (kaynak: `nesine_history.jsonl` saat 11:47–19:13 arası 17 anlık kare + öğleden sonra `ng_1637` / `ng_fresh` / `nesine_global`). Kullanılan Nesine karelerinin kickoff'a uzaklığı 0–2 saat, medyan yaklaşık 8 dakika. İma edilen ihtimaller Nesine payı orantılı yöntemle çıkarılmış.

Aşağıdaki tablolar **yalnızca Nesine oranlı** maçlar üzerinedir (418 maç).
Sharp yedek 9 maç ayrı tutuldu.

## Genel tablo (Nesine 1-X-2)

| Sonuç | Sayı | Gerçekleşen | Nesine ima (payı çıkarılmış) | Fark |
|---|---|---|---|---|
| Ev (1) | 182 | %43,5 | %42,1 | +1,4p |
| Beraberlik (X) | 97 | %23,2 | %25,1 | −1,9p |
| Deplasman (2) | 139 | %33,3 | %32,9 | +0,4p |
| Favori kazandı | — | %52,2 | %49,8 | +2,3p |

Ortalama Nesine 1-X-2 payı: %22,7.

## Favori oranı bantları

Favori, MS 1 ve MS 2'den kısa olan taraf. İki taraf da 2,10'un üstündeyse maç **dengeli** sayılıyor; favori sütununda yine daha kısa taraf kullanılıyor. Parantez içinde Nesine ima edilen oran var.

| Favori oranı | n | Ev (ima) | Beraberlik (ima) | Dep (ima) | Favori tuttu | İma edilen favori | Fark |
|---|---|---|---|---|---|---|---|
| ≤1,30 | 50 | %60,0 (%55,6) | %12,0 (%18,6) | %28,0 (%25,8) | %74,0 | %68,3 | +5,7p |
| 1,31–1,50 | 85 | %45,9 (%46,1) | %28,2 (%23,0) | %25,9 (%30,9) | %60,0 | %57,9 | +2,1p |
| 1,51–1,80 | 124 | %38,7 (%40,4) | %24,2 (%25,8) | %37,1 (%33,8) | %47,6 | %48,7 | −1,1p |
| 1,81–2,10 | 113 | %39,8 (%37,8) | %23,0 (%26,9) | %37,2 (%35,3) | %42,5 | %42,1 | +0,4p |
| dengeli (iki taraf >2,10) | 46 | %43,5 (%35,4) | %23,9 (%29,3) | %32,6 (%35,4) | %50,0 | %36,9 | +13,1p |

### Ev favorisi / deplasman favorisi

| Taraf | n | Ev (ima) | Beraberlik (ima) | Dep (ima) | Favori tuttu | İma | Fark |
|---|---|---|---|---|---|---|---|
| Ev favorisi | 269 | %53,9 (%50,8) | %21,6 (%24,7) | %24,5 (%24,4) | %53,9 | %50,8 | +3,1p |
| Dep favorisi | 149 | %24,8 (%26,3) | %26,2 (%25,6) | %49,0 (%48,1) | %49,0 | %48,1 | +0,9p |

| Bant × taraf | n | Ev (ima) | X (ima) | Dep (ima) | Favori tuttu | İma | Fark |
|---|---|---|---|---|---|---|---|
| ≤1,30 · ev fav | 38 | %76,3 (%68,7) | %7,9 (%18,6) | %15,8 (%12,7) | %76,3 | %68,7 | +7,6p |
| 1,31–1,50 · ev fav | 59 | %61,0 (%57,9) | %27,1 (%23,1) | %11,9 (%19,0) | %61,0 | %57,9 | +3,2p |
| 1,51–1,80 · ev fav | 79 | %46,8 (%48,8) | %22,8 (%25,8) | %30,4 (%25,4) | %46,8 | %48,8 | −1,9p |
| 1,81–2,10 · ev fav | 69 | %43,5 (%42,1) | %21,7 (%27,0) | %34,8 (%30,9) | %43,5 | %42,1 | +1,4p |
| dengeli (iki taraf >2,10) · ev fav | 24 | %54,2 (%37,2) | %25,0 (%28,4) | %20,8 (%34,3) | %54,2 | %37,2 | +16,9p |
| ≤1,30 · dep fav | 12 | %8,3 (%14,0) | %25,0 (%18,8) | %66,7 (%67,2) | %66,7 | %67,2 | −0,5p |
| 1,31–1,50 · dep fav | 26 | %11,5 (%19,4) | %30,8 (%22,7) | %57,7 (%58,0) | %57,7 | %58,0 | −0,3p |
| 1,51–1,80 · dep fav | 45 | %24,4 (%25,6) | %26,7 (%25,8) | %48,9 (%48,6) | %48,9 | %48,6 | +0,3p |
| 1,81–2,10 · dep fav | 44 | %34,1 (%31,0) | %25,0 (%26,8) | %40,9 (%42,2) | %40,9 | %42,2 | −1,3p |
| dengeli (iki taraf >2,10) · dep fav | 22 | %31,8 (%33,4) | %22,7 (%30,2) | %45,5 (%36,5) | %45,5 | %36,5 | +9,0p |

## Beraberlik oranı bantları

| Beraberlik oranı | n | Ev (ima) | Beraberlik (ima) | Dep (ima) | Favori tuttu | İma | Fark |
|---|---|---|---|---|---|---|---|
| ≤3,10 | 159 | %37,7 (%37,7) | %24,5 (%28,5) | %37,7 (%33,8) | %46,5 | %42,7 | +3,8p |
| 3,11–3,50 | 146 | %43,2 (%41,7) | %26,0 (%24,9) | %30,8 (%33,5) | %46,6 | %48,5 | −1,9p |
| 3,51–4,00 | 68 | %44,1 (%44,4) | %23,5 (%22,1) | %32,4 (%33,4) | %58,8 | %57,4 | +1,4p |
| 4,01–5,00 | 35 | %60,0 (%53,4) | %8,6 (%18,8) | %31,4 (%27,8) | %80,0 | %66,1 | +13,9p |
| ≥5,01 | 10 | %80,0 (%62,6) | %10,0 (%15,2) | %10,0 (%22,2) | %80,0 | %74,2 | +5,8p |

## Yakın oranlı maçlar (örnek: 2,20 / 3,40 / 2,00)

MS 1 ve MS 2 ikisi de 1,90–2,50 aralığında olan **65** Nesine maçı. Bu, 2,20 / 3,40 / 2,00 profiline en yakın grup.

Bu grupta sonuç dağılımı: ev %41,5 (ima %37,0), beraberlik %23,1 (ima %26,9), deplasman %35,4 (ima %36,1).

| Saat | Maç | 1 / X / 2 | MS | Skor |
|---|---|---|---|---|
| 15:30 | HNK Vukovar 1991 – NK Kustosija | 2,31 / 2,71 / 2,32 | Ev | 3-1 |
| 16:45 | Cracovia – J. Bialystok | 2,22 / 3,07 / 2,19 | Ev | 3-1 |
| 16:45 | US Quevilly – Valenciennes | 2,30 / 2,69 / 2,34 | Ev | 2-0 |
| 18:00 | Bolton – Portsmouth | 2,29 / 3,08 / 2,34 | Berabere | 1-1 |
| 15:00 | Kokand 1912 – Sogdiana | 2,31 / 2,80 / 2,26 | Dep | 0-1 |
| 15:30 | Hrvace – NK Segesta | 2,24 / 2,84 / 2,30 | Ev | 1-0 |
| 18:00 | Moyola Park – Queens Uni. | 2,25 / 3,02 / 2,19 | Dep | 1-3 |
| 19:00 | Marino  Luanco – Coruxo | 2,29 / 2,69 / 2,35 | Dep | 0-1 |
| 16:30 | Upington City – Magesi | 2,47 / 2,44 / 2,39 | Ev | 2-1 |
| 16:30 | Lerumo Lions – Cape Town City | 2,40 / 2,58 / 2,32 | Ev | 2-0 |
| 17:30 | Liefering – Wacker Inns. | 2,19 / 3,30 / 2,11 | Dep | 0-3 |
| 18:00 | Lincoln City – Wrexham | 2,44 / 2,83 / 2,36 | Dep | 0-1 |
| 17:00 | Ynyshir Albions – Llantwit Major | 2,10 / 3,33 / 2,19 | Dep | 2-3 |
| 18:30 | Cluj – Otelul Galati | 2,21 / 2,88 / 2,31 | Ev | 3-2 |
| 16:00 | Fortuna Köln – Meppen | 2,24 / 3,18 / 2,35 | Ev | 2-1 |
| 18:00 | Mansfield – MK Dons | 2,26 / 3,07 / 2,15 | Berabere | 1-1 |
| 14:30 | Chennaiyin – Punjab | 2,16 / 3,02 / 2,28 | Berabere | 1-1 |
| 16:30 | Ostia Mare – Atalanta BC U23 | 2,29 / 2,99 / 2,16 | Berabere | 0-0 |
| 17:30 | E. Frankfurt – Hoffenheim | 2,14 / 3,54 / 2,27 | Ev | 1-0 |
| 15:30 | Millwall – QPR | 2,24 / 3,11 / 2,39 | Dep | 0-1 |
| 18:00 | Workington – G'borough Tr. | 2,26 / 3,19 / 2,10 | Dep | 1-2 |
| 18:00 | Wingate&Finchley – Brentwood Town | 2,08 / 3,24 / 2,25 | Dep | 1-2 |
| 17:00 | Guilsfield – Bangor 1876 | 2,24 / 3,31 / 2,06 | Ev | 2-0 |
| 18:00 | Stoke City – Birmingham | 2,48 / 2,88 / 2,29 | Ev | 1-0 |
| 18:00 | Coquimbo U. – Everton DV | 2,13 / 3,01 / 2,32 | Ev | 2-1 |
| 18:00 | Coventry – Crystal Palace | 2,22 / 3,09 / 2,42 | Ev | 3-2 |
| 19:30 | AS Giana E. – Juventus U23 | 2,36 / 2,88 / 2,16 | Dep | 1-3 |
| 15:30 | Grobnican – Trnje | 2,29 / 3,16 / 2,08 | Dep | 0-1 |
| 19:00 | CD Tenerife C – Real Union de Tenerife | 2,23 / 2,66 / 2,44 | Dep | 0-1 |
| 19:30 | AC Savoia 1908 – Sorrento | 2,17 / 2,81 / 2,40 | Ev | 2-1 |
| 15:30 | Katwijk – Rijnsburgse Boys | 2,01 / 3,45 / 2,24 | Dep | 0-2 |
| 15:00 | Paderborn U19 – SV Meppen U19 | 1,95 / 3,77 / 2,19 | Ev | 5-1 |
| 14:30 | Parma Calcio (K) – SSD Napoli (K) | 2,09 / 3,06 / 2,33 | Ev | 2-0 |
| 18:00 | Swansea City – W. Bromwich | 2,23 / 2,98 / 2,47 | Berabere | 2-2 |
| 15:30 | Solihull Moors – Altrincham | 2,07 / 3,11 / 2,32 | Ev | 2-1 |
| 16:00 | Kamaz Chelny – Spartak Kostroma | 2,16 / 2,79 / 2,42 | Ev | 3-1 |
| 19:00 | CD San Ignacio – SD Leioa | 2,42 / 2,80 / 2,16 | Berabere | 1-1 |
| 17:00 | Lunds BK – Norrby | 2,13 / 2,88 / 2,40 | Berabere | 1-1 |
| 18:00 | Raith Rovers – P. Thistle | 2,42 / 2,82 / 2,15 | Dep | 0-2 |
| 17:00 | Banik Ostrava – Teplice | 2,08 / 3,04 / 2,36 | Dep | 1-2 |
| 18:00 | Kettering – Needham | 2,06 / 3,14 / 2,34 | Berabere | 0-0 |
| 16:00 | T. Telec Ivan – Arsenal Tula | 2,39 / 2,92 / 2,11 | Berabere | 2-2 |
| 17:45 | CD Egues – AD San Juan | 2,39 / 2,93 / 2,11 | Ev | 1-0 |
| 18:00 | Carshalton – Aveley | 2,29 / 3,34 / 2,01 | Dep | 0-2 |
| 18:00 | Kilmarnock – Aberdeen | 2,14 / 3,24 / 2,43 | Dep | 2-4 |
| 18:30 | Real Aranjuez – Cp Parla Escuela | 2,13 / 2,85 / 2,42 | Ev | 2-1 |
| 18:00 | Wimborne – Bath City | 2,11 / 2,91 / 2,41 | Dep | 0-2 |
| 18:00 | Edinburgh – Kelty Hearts | 2,07 / 3,04 / 2,38 | Dep | 0-1 |
| 15:30 | A. Bielefeld U19 – Hannover 96 U19 | 1,93 / 3,70 / 2,26 | Ev | 6-2 |
| 18:00 | RFC Liege – RSC Anderlecht U23 | 2,02 / 3,17 / 2,36 | Ev | 2-0 |
| 19:00 | OFK Belgrad – Novi Pazar | 2,10 / 2,89 / 2,44 | Dep | 0-2 |
| 18:00 | Gosport – Hav Waterloo | 2,01 / 3,21 / 2,35 | Dep | 1-2 |
| 19:00 | SC Covilha – Lusitano GC | 2,50 / 2,73 / 2,14 | Dep | 1-2 |
| 17:30 | Basel II – Paradiso | 2,00 / 3,18 / 2,39 | Dep | 0-2 |
| 18:00 | Yate Town – Hanwell Town | 2,06 / 2,96 / 2,45 | Berabere | 0-0 |
| 16:00 | Frankfurt 1899 – Freiburg II | 2,39 / 3,26 / 1,96 | Ev | 2-0 |
| 18:00 | Maidenhead – Folkestone I. | 2,00 / 3,10 / 2,43 | Berabere | 2-2 |
| 18:00 | Aldershot – Scunthorpe | 2,39 / 3,31 / 1,95 | Ev | 2-0 |
| 18:00 | Utd Of Manch. – Warrington Rylands 1906 | 2,42 / 3,26 / 1,95 | Berabere | 3-3 |
| 18:00 | Hebburn Town – Marine | 2,00 / 3,03 / 2,47 | Berabere | 2-2 |
| 18:00 | Stratford – Halesowen | 2,44 / 3,23 / 1,95 | Ev | 3-1 |
| 17:30 | Sturm Gr.(Amt.) – Amstetten | 2,46 / 3,15 / 1,96 | Berabere | 1-1 |
| 18:00 | Dorking Wanderers – Ebbsfleet Utd | 2,47 / 3,13 / 1,96 | Berabere | 2-2 |
| 16:30 | Rkav Volendam – Amsterdamsche | 1,93 / 3,26 / 2,45 | Ev | 2-1 |
| 15:00 | Komarom Vse – Puskas Akademia II | 1,94 / 3,15 / 2,49 | Ev | 3-2 |

İki tarafı da 2,10'un üstünde olan dengeli maç sayısı: **46** (Nesine). Özet yukarıdaki 'dengeli' satırında; tam liste `oran_sonuc_analizi.json` içinde.

## En büyük sürprizler (favori oranı ≤1,50 ve tutmadı)

Favorisi 1,50 veya daha kısa olan 135 Nesine maçından **47** tanesinde favori kazanamadı (31 beraberlik, 16 ters sonuç). Öne çıkanlar: West Ham–Preston 1,09 ile 1-1, Man. City–Fulham 1,21 ile 1-1, Al Wakrah 1,17 ile 2-3, Reading 1,21 ile 0-1, Kocaelispor–Fenerbahçe 1,46 ile 2-2, Rubin Kazan–Zenit 1,40 ile 3-1 (Zenit yenildi). Aşağıdaki listede bir de sharp yedek var: F. Karagümrük–Boluspor 1,23 ile 0-0.

| Saat | Maç | 1 / X / 2 | Favori | MS | Skor |
|---|---|---|---|---|---|
| 18:00 | West Ham – Preston | 1,09 / 5,95 / 9,54 | Ev 1,09 | Berabere | 1-1 |
| 16:00 | K. Red Warrior – Sabah | 6,71 / 5,02 / 1,13 | Dep 1,13 | Ev | 2-1 |
| 15:45 | Liverpool (K) – Chelsea (K) | 6,13 / 4,68 / 1,17 | Dep 1,17 | Berabere | 0-0 |
| 16:00 | AL Wakrah – Al Sailiya | 1,17 / 4,69 / 5,99 | Ev 1,17 | Dep | 2-3 |
| 19:00 | Primorje Ajdovscina – NK Krsko | 1,20 / 4,18 / 6,38 | Ev 1,20 | Dep | 0-1 |
| 15:30 | Reading – Bromley | 1,21 / 4,14 / 5,85 | Ev 1,21 | Dep | 0-1 |
| 15:30 | Man. City – Fulham | 1,21 / 4,85 / 6,48 | Ev 1,21 | Berabere | 1-1 |
| 16:00 | Bicskei TC – Tatabanya | 5,93 / 3,97 / 1,23 | Dep 1,23 | Berabere | 3-3 |
| 19:00 | F. Karagümrük – Boluspor | 1,23 / 7,37 / 18,54 * | Ev 1,23 | Berabere | 0-0 |
| 15:30 | EV Tarnova – PFK Sportist Svoge | 1,25 / 3,95 / 5,54 | Ev 1,25 | Dep | 1-2 |
| 15:45 | Khor Fakkan – AL Jazira (Bae) | 5,37 / 4,01 / 1,26 | Dep 1,26 | Berabere | 1-1 |
| 15:00 | Eskilsminne – Skara | 1,27 / 4,07 / 5,05 | Ev 1,27 | Dep | 0-1 |
| 18:00 | SD Torina – Selaya | 1,29 / 3,52 / 5,72 | Ev 1,29 | Dep | 0-1 |
| 18:00 | Ujpest – Kisvarda | 1,30 / 3,91 / 4,80 | Ev 1,30 | Berabere | 0-0 |
| 15:00 | Veszprem – Papai Perutz | 1,33 / 3,87 / 4,48 | Ev 1,33 | Dep | 1-2 |
| 16:45 | Cannes – Aubagne | 1,33 / 3,60 / 4,94 | Ev 1,33 | Berabere | 0-0 |
| 18:00 | Grimsby Town – Rotherham | 1,35 / 3,78 / 4,30 | Ev 1,35 | Berabere | 0-0 |
| 15:30 | Ratchaburi – Prachuap | 1,38 / 3,59 / 4,35 | Ev 1,38 | Dep | 0-1 |
| 18:00 | Braintree – Torquay | 4,12 / 3,74 / 1,38 | Dep 1,38 | Berabere | 0-0 |
| 15:00 | PSM Makassar – Persija Jakarta | 4,27 / 3,61 / 1,39 | Dep 1,39 | Berabere | 1-1 |
| 16:30 | AJ Auxerre U19 – Dijon U19 | 1,39 / 3,53 / 4,37 | Ev 1,39 | Berabere | 1-1 |
| 17:30 | Rubin Kazan – Zenit | 5,21 / 3,61 / 1,40 | Dep 1,40 | Ev | 3-1 |
| 18:00 | Lancaster – Ashton Utd | 1,40 / 3,48 / 4,33 | Ev 1,40 | Dep | 1-3 |
| 18:00 | Albans City – AFC Whyteleafe | 1,40 / 3,81 / 3,93 | Ev 1,40 | Dep | 3-4 |
| 15:30 | PFC Spartak Pleven – PFC Nesebar | 1,41 / 3,29 / 4,46 | Ev 1,41 | Berabere | 1-1 |
| 18:00 | Bradford – Doncaster | 1,41 / 3,42 / 4,27 | Ev 1,41 | Berabere | 2-2 |
| 18:00 | Chatham Town – Maldon & Tiptree | 1,41 / 3,78 / 3,90 | Ev 1,41 | Berabere | 3-3 |
| 18:00 | Ranchers Bees – Plateau Utd | 1,41 / 3,11 / 4,92 | Ev 1,41 | Berabere | 1-1 |
| 18:25 | Dubai Utd – AL Wahda | 4,16 / 3,52 / 1,41 | Dep 1,41 | Berabere | 1-1 |
| 19:00 | Estoril Praia – Felgueiras 1932 | 1,41 / 3,37 / 4,38 | Ev 1,41 | Dep | 2-3 |
| 17:30 | Polonia Warszawa – Stal Mielec | 1,42 / 3,42 / 4,22 | Ev 1,42 | Berabere | 1-1 |
| 18:00 | Chichester City – Basingstoke | 1,43 / 3,69 / 3,80 | Ev 1,43 | Berabere | 2-2 |
| 15:30 | Raal La Louviere (K) – OH Leuven (K) | 3,76 / 3,58 / 1,45 | Dep 1,45 | Berabere | 1-1 |
| 19:30 | Zaglebie Lubin – Gornik Zabrze | 4,29 / 3,22 / 1,45 | Dep 1,45 | Ev | 2-0 |
| 17:30 | Ruch Chorzow – Warta Poznan | 1,46 / 3,35 / 4,03 | Ev 1,46 | Dep | 1-2 |
| 18:00 | RC Warwick – Real Bedford | 3,62 / 3,70 / 1,46 | Dep 1,46 | Berabere | 1-1 |
| 19:00 | Kocaelispor – Fenerbahçe | 4,39 / 3,67 / 1,46 | Dep 1,46 | Berabere | 2-2 |
| 19:00 | SD Sarriana – Silva SD | 1,46 / 3,20 / 4,24 | Ev 1,46 | Berabere | 1-1 |
| 19:30 | Citta Di Campobasso – Vis Pesaro | 1,46 / 3,39 / 3,98 | Ev 1,46 | Berabere | 3-3 |
| 17:00 | Sochi – Veles Mos. | 1,47 / 3,24 / 4,08 | Ev 1,47 | Berabere | 2-2 |
| 17:00 | Ascoli – LR Vicenza V. | 1,47 / 3,38 / 4,75 | Ev 1,47 | Berabere | 2-2 |
| 18:00 | CD Belchite 97 – Atletico de Monzon | 4,29 / 3,16 / 1,47 | Dep 1,47 | Berabere | 1-1 |
| 15:00 | Siauliai – Minija 2017 | 1,48 / 3,41 / 3,74 | Ev 1,48 | Berabere | 1-1 |
| 15:30 | NK Jarun Zagreb – NK Hrvatski Dr. | 1,48 / 3,36 / 3,80 | Ev 1,48 | Berabere | 0-0 |
| 18:00 | Stanway Rovers – Burgess Hill | 3,42 / 3,74 / 1,48 | Dep 1,48 | Berabere | 2-2 |
| 19:00 | Osasuna B – Barbastro UD | 1,49 / 3,17 / 4,03 | Ev 1,49 | Dep | 0-1 |
| 18:00 | Eupen – Sporting Hasselt | 1,50 / 3,52 / 3,53 | Ev 1,50 | Berabere | 1-1 |
| 18:30 | Eindhoven – Waalwijk | 3,40 / 3,64 / 1,50 | Dep 1,50 | Ev | 3-2 |

## İlk yarı (aynı favori bantları, maç öncesi 1-X-2)

Bantlar hâlâ maç sonu Nesine 1-X-2'ye göre; sonuç ise ilk yarı skoru. Bu, İY 1 / İY 0 / İY 2 dağılımı.

| İY sonuç | Sayı | Gerçekleşen | MS oranından ima (referans) | Fark |
|---|---|---|---|---|
| İY Ev | 130 | %31,2 | %42,1 | −10,9p |
| İY Beraberlik | 174 | %41,7 | %25,0 | +16,7p |
| İY Dep | 113 | %27,1 | %32,8 | −5,7p |

MS ima edilen oranlar ilk yarı için fazla iddialı kalır (ilk yarıda beraberlik doğal olarak daha sık). Asıl karşılaştırma bantlar arası İY dağılımı.

| Favori oranı (MS) | n | İY Ev | İY X | İY Dep | İY'de favori önde |
|---|---|---|---|---|---|
| ≤1,30 | 50 | %42,0 | %40,0 | %18,0 | %52,0 |
| 1,31–1,50 | 85 | %29,4 | %40,0 | %30,6 | %38,8 |
| 1,51–1,80 | 124 | %36,3 | %35,5 | %28,2 | %45,2 |
| 1,81–2,10 | 113 | %26,5 | %43,4 | %30,1 | %30,1 |
| dengeli (iki taraf >2,10) | 45 | %20,0 | %60,0 | %20,0 | %24,4 |

## Notlar

- Pay çıkarılmasa Nesine ima edilen favori ihtimali şişer; tablolardaki ima payı temizlenmiş değerlerdir.
- Tek günlük örnek. Küçük bantlarda (özellikle ≤1,30) yüzde dalgalanması normal.
- 90 dakikalık resmi skor kullanıldı; bugünkü evrendeki biten maçların hepsi normal süre (MS) ile bitti.
- Dosyalar: `oran_sonuc_analizi.md` ve `oran_sonuc_analizi.json`.

