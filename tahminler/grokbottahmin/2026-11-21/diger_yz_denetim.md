# Diğer yapay zekâların tahmin denetimi (18–21 Kasım 2026)

- Hazırlanma: 21 Kasım 2026, yaklaşık 22:15 TSİ (Europe/Istanbul, UTC+3).
- Sonuç kaynağı: Nesine `GetUnliveMatches` (18–22 Kasım), 90. dakika skoru (tip 3) ve ilk yarı (tip 2). Uzatma ve penaltı, Nesine kupon ödemesinde olduğu gibi yok sayıldı.
- Hiçbir yapay zekânın kendi karnesine, öz-öğrenme yazısına veya “4/4 tuttu” iddiasına güvenilmedi; hepsi bağımsız notlandı.
- Başka klasörlerdeki dosyalar değiştirilmedi. Bu rapor yalnız `tahminler/grokbottahmin/2026-11-21/` altına yazıldı.

## 0. Depoda ne var, ne yok

| Kaynak | Durum |
|---|---|
| ChatGPT `2026-11-21/mac_tahminleri.csv` (629 maç) + `kuponlar.csv` (6 kupon) | Var, notlandı. 18–20 Kasım dosyası yok. |
| Gemini `2026-11-20` (103 ana seçim, 9 kupon, öz-karne) | Var, notlandı. 18–19 Kasım dosyası yok. |
| Gemini `2026-11-21` | Yalnız gece 500 TL kupon yazısı var; `mac_tahminleri.csv` yok. |
| Claude `tahminler/claudetahmin/` | Yalnız README. Git geçmişinde (`1baa197`, `0da04fc`, `1f1e0f3`, `31ee09c`, `fa117fc`) hiç `mac_tahminleri.csv` / `kuponlar.csv` yok; 20 Kasım’tan sonra bu klasör gitignore’a alındı. |
| Claude 18 Kasım | Var: `reports/today_v6_predictions_2026_11_18.json` (45 maç, `best_valid_bet`) + ledger kuponları + oynanan kuponlar. |
| Claude 19 Kasım | Var: `reports/nov19_nesine_global_analysis.json` (59 maç, `best_nesine_bet`) + 3 resmi kupon seti + oynanan kuponlar. `reports/daily/2026-11-19/` içindeki her `kupon_10x_HHMM` yeniden üretimi ayrı “resmi kupon” sayılmadı. |
| Claude 20 Kasım kendi dosyaları | Yok. `reports/daily/2026-11-20/` hiç oluşmamış (INDEX’te kırık bağlantı). Elde kalan tek iz: `tahminler/ortak_arena/2026-11-20/` içindeki 28 satırlık ikinci el tablo (Gemini’nin yazdığı rapor, 108 maç iddia ediyor). |
| Claude 21 Kasım | Yok. |
| Antigravity | Yalnız README; tahmin dosyası yok, git geçmişinde de yok. |

## 1. Özet tablo (ana seçimler, bitmiş maçlar)

| Yapay zekâ | Gün | Notlanan | Tutan | İsabet | Verdiği ortalama % | Fark | 1 birim bahis |
|---|---|---|---|---|---|---|---|
| ChatGPT | 21 Kasım | 329 / 415 ana seçim | 204 | **%62,0** | %62,7 | −0,7 puan | −51,14 br (**%−15,5**) |
| Gemini | 20 Kasım | 103 / 103 | 53 | **%51,5** | %62,6 | **−11,1 puan** | −34,24 br (**%−33,2**) |
| Claude | 18 Kasım | 43 / 45 (aşağıda) | 30 | **%69,8** | ~%71,7 | ≈ −2 puan | otomatik sette %−11,8 |
| Claude | 19 Kasım | 58 / 59 | 31 | **%53,4** | %63,1 | **−9,7 puan** | −16,42 br (**%−28,3**) |
| Claude | 20 Kasım | 28 satırlık ikinci el örnek | 13 | %46,4 | yok | — | örnek yanlı, tam karne değil |
| Grok (referans) | 21 Kasım | 2.924 seçim / 383 ana |  | %60,7 / **%63,7** | %61,9 / %67,0 | −1,2 / −3,3 puan | — |

Claude 18 düzeltmesi: otomatik eşleşme 29/41 (%70,7, verdiği %71,7) verdi. Nesine’den doğrulanan iki kadınlar maçı eklendi (Real Madrid 3-1 Inter, MS 1 tuttu; London City 0-1 Brighton, 1.5 Üst yattı). Bengaluru Nesine’de yok, Lye Town ertelendi. Böylece **30/43 (%69,8)**.

## 2. ChatGPT — 21 Kasım

Dosyada 629 maç var; bunların 415’inde ana seçim (`secim_adi`) var, 214’ünde yalnız 1X2 olasılığı var. 21 Kasım 22:15 TSİ itibarıyla 329 ana seçim kesinleşti, 83’ü bekliyor (43 başlamadı, 40’ı `GetUnliveMatches` içinde yok — bu uç nokta canlı maçları vermiyor; Feyenoord, Schalke, Ponferradina buna denk geliyor), 3’ü void.

**Kalibrasyon iyi.** %62,7 dedi, %62,0 tuttu. 1X2’de en olası sonucu seçince 267/497 (%53,7), verdiği %52,9 — bu da tutarlı. Grok’un 21 Kasım tam setine (2.924 seçim, %61,9 / %60,7) en yakın karne bu.

Aileler (bitenler):

| Aile | Tutan / notlanan | İsabet | Verdiği % |
|---|---|---|---|
| Alt/Üst | 129/214 | %60,3 | %62,0 |
| Maç sonucu | 58/89 | %65,2 | %63,1 |
| Çifte şans | 12/18 | %66,7 | %68,2 |
| Karşılıklı gol | 1/3 | %33,3 | %60,9 |
| İlk yarı | 2/3 | %66,7 | %69,8 |
| Kombine | 2/2 | %100 | %60,1 |

Yine de 1 birim düz bahis **%15,5 zarar** — Nesine payı ve oran bandı. Tahminler doğru kalibre, kupon ve değer tarafı ayrı.

**Kuponlar (6):** 0 kazandı, 4 yattı, 2 bekliyor (akşam maçları henüz bitmedi).

- `kupon_2x_1426` (2,09): 2/3. Yıkan bacak Hebburn–Marine 3.5 Alt, 2-2.
- `kupon_3x_1426` (3,02): 2/4. Glenavon–Newry 2.5 Üst 1-0 ve Eupen–Hasselt 2.5 Üst 1-1 yattı. İkisi de 1,22–1,27 arası “kolay üst”.
- `kupon_6x_1522` (6,06): Hoffenheim II–Preussen Münster 3.5 Alt 4-0 ile yattı (3/5, bir bacak eşleşmedi).
- `kupon_5x_iyms_1727` (5,07): Kocaelispor–Fenerbahçe İY/MS 2/2 yattı (2-2, İY 0-0). Schalke bacağı o an canlıydı, zaten kupon ölmüştü.
- `kupon_1.5x_1857` ve `kupon_10x_1905`: Feyenoord, Lens, Groningen, Zulte henüz kesinleşmedi.

README, dosyaların 21 Kasım 20:20 TSİ’de yerel kayıttan aktarıldığını ve GitHub saatinin maç öncesi üretimi kanıtlamadığını açıkça söylüyor. 415 ana seçimin büyük kısmının başlangıcı bu saatten önce. Suçlama için yeterli kanıt yok, ama bağımsız ön-kanıt da yok.

Sistematik hata: tek maç tahmini fena değil; kuponlar düşük oranlı Alt/Üst ve İY/MS üzerine çok bacak bağladığı için bir bacak yetiyor. Bu, bizim de yaptığımız hata.

## 3. Gemini — 20 Kasım ve 21 Kasım gece kuponu

### 3.1 Ana seçimler (103/103 bitti)

**53/103 (%51,5).** Verdiği ortalama %62,6. Beklenen tutan ≈ 64,5; **11,1 puan iyimser**, 1 birim bahiste **−34,24 birim (%−33,2)**.

Öz-karnesi: kesin 51/94 (%54,3), canlı dahil 56/103 (%54,4). Bağımsız sonuç: **53/103 (%51,5)**. Farkın kaynağı:

- 9 “canlı” maçın 5’i “şu an tutuyor” yazılmıştı; bunların yalnız 3’ü 90 dakikayı tutarak bitirdi, 2’si son dakikada yattı (Troyes 3-1, Cliftonville 3-2 — ikisi de 3.5 Alt).
- **Red Star–Pau:** karnede `1-1 (Ksl.)` ve ÇŞ X2 **DOĞRU**. Nesine kod 3310218, resmi durum **MS**, skor **2-1** (İY 1-0). ÇŞ X2 **yattı**. Hem skor hem hüküm hatası.

“Yüksek güven” 17/35 (**%48,6**, verdiği %63,4) — orta güvenden **daha kötü** (%52,9).

Aileler:

| Aile | Tutan / notlanan | İsabet | Verdiği % |
|---|---|---|---|
| Çifte şans | 19/32 | %59,4 | %62,0 |
| Alt/Üst | 18/31 | %58,1 | %66,4 |
| Karşılıklı gol | 11/24 | %45,8 | %59,0 |
| Maç sonucu | **5/16** | **%31,2** | **%61,8** |

MS 1/2 seçimleri felaket: %62 dedi, %31 tuttu. KG de 13 puan iyimser. En büyük özgüven kaçakları: Troyes 3.5 Alt %75,2 (3-1), Shkendija MS 1 %72,4 (0-1).

Oran 1,00–1,30 bandında 34/47 (%72) tuttu; 1,30–1,50’de 15/44 (**%34**). Kısa favori değil, “1,30’un üstü banko” yanıltıcı oldu.

Bütün 103 kod `MBS1-231` tarzı etiket; Nesine olay kodu değil. İsimle eşleştirildi, 103/103 doğru maça oturdu.

### 3.2 Yirmi Kasım kuponları: 0/9

Dokuz kuponun hiçbiri tutmadı. Aynı zayıf bacak birçok kupona tekrar kondu:

- Shkendija MS 1 / İY 1 / Hnd(−1) 1 — 0-1. En az dört kuponu kesti (`5x`, `5x_ms12`, `30x`, `50x`).
- Heracles–Jong PSV ve Volendam–Jong Ajax 3.5 Üst — 2-1 ve 1-2. `5x`, `5x_altust`, `10x` yattı. Gemini bunu kendi karnesinde “Hollanda Eerste 3.5 Üst kalkanı” diye sonradan yazmış; kuponlar zaten oynanmıştı.
- Athletic Bilbao KG Var / İY/MS 1/1 — 0-1. `20x`, `5x_kg`, `5x_iyms` yattı.
- East Bengal MS 1 / İY 1 / Hnd(−1) — 2-2.

### 3.3 Gece 500 TL kuponu (21 Kasım, `kupon_gece_500tl_v80`)

İddia: ana kupon **4/4**, opsiyonel 5. ayakla **5/5**, 2,62 oran, 500 TL → 1.310 TL. **90 dakika skorları bu iddiayı doğruluyor:**

| Maç | Seçim | Nesine 90 dk (İY) | Durum |
|---|---|---|---|
| Vélez Sarsfield–Belgrano (PEN) | 2.5 Alt 1,48 | 1-1 (0-1); uzatma 2-2, pen 3-1 | Tuttu |
| Palestino–Unión La Calera | 3.5 Alt 1,24 | 0-1 (0-0) | Tuttu |
| Puebla–Atlético San Luis | 1.5 Üst 1,22 | 1-1 (1-0) | Tuttu |
| Juárez–Atlas | ÇŞ X2 1,24 | 3-3 (**İY 1-1**) | Tuttu |
| Tijuana–Atlante (opsiyonel) | 3.5 Alt 1,32 | 1-0 (0-0) | Tuttu |

Tek olgusal hata: Gemini Juárez ilk yarıyı **2-1** yazmış; Nesine **1-1**. Kupon sonucunu değiştirmez, olay anlatısı yanlış.

Bu kuponun tutmasının nedeni pazar seçimi: kısa Alt/Üst ve çifte şans, 4 (veya 5) bacak, toplam 2,62. 20 Kasım’ın 5–7 bacaklı MS 1 / 3.5 Üst kuponlarından tamamen farklı.

## 4. Claude

### 4.1 18 Kasım — en iyi tekil karne, kuponlar karışık

45 maçlık `best_valid_bet` seti. Nesine doğrulamasıyla **30/43 (%69,8)**. Öz-denetim raporu 04:02 TSİ’de 29/41 (%70,7) demişti; o sırada bazı maçlar hâlâ canlıydı. Canlı oranlı maçlarda 11/15 (%73,3), tahmini oranlı alt lig/kadın maçlarında otomatik sette 18/26 (%69,2). Kalibrasyon neredeyse birebir (otomatik sette verdiği %71,7, tutan %70,7).

Aileler (otomatik set): Alt/Üst 17/25 (%68), ilk yarı 6/9 (%67), maç sonucu 4/5 (%80). Kaçan yüksek güvenliler çoğunlukla 3.5 Alt: Badajoz 2-5, Nottingham Kadın 1-4, Arnavutköy 2-3, Çorlu 1-4, Corinthians 4-0.

**Resmi 7 kupon (ledger), Nesine 90 dk ile:**

- C1 çekirdek 3’lü (2,03): **3/3 kazandı** (Real Madrid Kadın 3-1, Flamengo 2-1, Häcken 0-2).
- C2 dengeli 4’lü (2,85): **4/4 kazandı**.
- C3 değer 5’li (5,28): **5/5 kazandı**.
- C4 10x: 4/5, Coritiba–Santos 2.5 Üst (0-1) yıktı.
- C5 20x: Alcoyano beraberliği, Coritiba ve Grêmio 0-0 yıktı.
- C6 2. Lig gündüz: Elazığspor 1-1 ve Bingöl 0-1 yıktı.
- C7 İY/MS: Chelsea İY/MS 1/1 (İY 0-0, MS 1-0) ve Häcken İY/MS 2/2 (İY 0-0, MS 0-2) yattı. Real Madrid İY/MS 1/1 de İY 1-1 olduğu için yatardı.

Yani tasarlanmış portföyün **düşük varyanslı 3 kuponu tuttu**, yüksek çarpanlı ve İY/MS kuponları yatı.

**Oynanan 17 kuponun hiçbiri tutmadı.** Aralarında `+6 Gol` gibi piyango bacakları var: toplam oran 912, 549, 620, hatta 321.367. Bunlar resmi 7’li portföy değil; hem pazar seçimi hem kupon inşası bozulmuş.

### 4.2 19 Kasım — tekil kalibrasyon bozuldu, resmi kuponlar 0/17

59 maçlık Nesine-global set, `best_nesine_bet`: **31/58 (%53,4)**, verdiği %63,1, **−9,7 puan**, 1 birim **%−28,3**. (Bir maç notlanamadı / bekliyor değil, 58 bitti.)

Aileler:

| Aile | Tutan / notlanan | İsabet | Verdiği % |
|---|---|---|---|
| Alt/Üst | 13/18 | **%72,2** | %64,5 (beklenenden iyi) |
| Çifte şans | 6/9 | %66,7 | %60,8 |
| Karşılıklı gol | 8/17 | **%47,1** | %63,2 |
| Maç sonucu | **4/13** | **%30,8** | %62,2 |

MS ve KG, Gemini’nin 20 Kasım karnesiyle neredeyse aynı çöküşü gösteriyor. En özgüvenli kaçan: Gaddafi–Kataka KG Yok %77,5 (2-2).

**Resmi kupon setleri: 7 + 5 (20x) + 5 (gece v7) = 17 kupon, 0 kazandı.** Birkaç tanesi tek bacaktan yattı:

- C1 ikili banko ve C2 3’lü: AL Ain KG Yok, 2-1.
- 20x set 2: 9/10 tuttu, Arsenal Kadın–Lyon 2.5 Üst 0-2 yıktı.
- Gece çekirdek 3’lü: Vitória–Bragantino ÇŞ X2, 2-1.

`reports/takip/ozet.md` 3.083 seçimlik (tüm pazarlar, yalnız ana seçim değil) kalibrasyonu neredeyse doğru gösteriyor (%66,0 / %63,3 ana tercih). Bu, “her pazarı fiyatlamak” ile “kupona konan en iyi seçim”in farklı şeyler olduğunu gösteriyor: geniş set kalibre, kupon bacağı iyimser ve kırılgan.

**Oynanan kuponlar: 2 kazandı, 10 yattı, 1 bozuk satır.** Tutanlar: P02 (200 TL, 6,39, 5/5) ve P06 (150 TL, 5,30, 5/5). Yıkan bacakların tekrarı var (Maroons KG Yok, Farco KG Yok, Boston River MS 2). P11 ve P12, 0-0 / MS 0 bacaklı 567x ve 160x piyango kuponları; hepsi yattı.

### 4.3 20 Kasım — tam dosya yok

Claude’un kendi 20 Kasım tahmin ve kupon dosyaları ne depoda ne git tarihinde var. Ortak arena raporu Claude için 62/108 (%57,4) diyor; bu sayı **doğrulanamaz**. Tabloda tek tek yazılan 28 maç Nesine ile notlandı: Claude hücreleri **13/28 (%46,4)**, aynı tablodaki Gemini hücreleri 16/28 (%57,1). Skor ve hüküm çelişkisi çıkmadı, ama 28 satır ayrışma/örnek tablosu — rastgele örnek değil, yanlı. Claude’un gerçek 20 Kasım karnesi için kendi makinesindeki `tahminler/claudetahmin/2026-11-20/` gerekir.

## 5. Antigravity

Klasörde yalnız README var. Son 2–3 güne ait tahmin veya kupon dosyası depoda ve git geçmişinde yok. Notlanacak bir şey yok.

## 6. Grok (21 Kasım) ile kısa kıyas

- Grok geniş set: 2.924 seçim, %61,9 dedi, %60,7 tuttu (≈ −1,2 puan).
- Grok ana başlık: 383 seçim, %67,0 dedi, %63,7 tuttu (≈ −3,3 puan).
- ChatGPT’nin ana seçim kalibrasyonu (329 maç, −0,7 puan) Grok geniş sete çok yakın, hatta biraz daha sıkı. İsabet %62,0 vs Grok ana %63,7 — Grok biraz daha seçici, ChatGPT daha geniş.
- Gemini 20 Kasım ve Claude 19 Kasım, “en iyi seçim”de Grok’tan belirgin biçimde daha iyimser (−11 ve −10 puan) ve MS 1 / KG’de aynı çukura düşmüş.
- Claude 18 Kasım tekil isabet ve kalibrasyon olarak günün en iyisi; yine de yüksek çarpanlı kuponları ve oynanan piyango kuponları yatmış.

## 7. Ortak hatalar ve alınması gereken dersler

1. **Tekil isabet yetmiyor, kupon inşası asıl kırılma noktası.** ChatGPT %62, Claude 18 %70 tutsa da çok bacaklı kuponlar bir seçimle yatıyor. Bunu Ramazan’ın dediği gibi düzeltmek lazım: daha az bacak, daha yüksek düzeltilmiş olasılık, aynı maçı / aynı zayıf pazarı birkaç kupona kopyalamamak.
2. **Kısa fiyatlı MS 1 kupon bacağı sistematik tuzak.** Gemini 5/16 (%31, verdiği %62), Claude 19 4/13 (%31, verdiği %62). East Bengal, Shkendija, Setif, Verona, Athletic, MC Alger — hepsi “favori kazanır” diye girdi, berabere veya ters bitti. Bundan sonra MS 1’i 5’li kuponun omurgası yapmamak.
3. **KG Var/Yok fazla iyimser.** Gemini %46 vs %59, Claude 19 %47 vs %63. AL Ain KG Yok ve Maroons KG Yok, birden fazla kuponu kesti.
4. **Alt/Üst ve çifte şans daha duruyor; ama “kolay üst/alt” da yetmiyor.** Claude 19 Alt/Üst %72, ChatGPT Alt/Üst kalibre, Gemini gece kuponunun 4/4’ü kısa Alt/Üst + ÇŞ. Buna karşılık Glenavon 1-0, Eupen 1-1, Hoffenheim II 4-0, Troyes 3-1 gibi maçlar düşük oranlı eşiği yıktı. Eşik ve lig filtresi şart (Gemini’nin sonradan yazdığı Eerste 3.5 Üst uyarısı doğru, ama iş işten geçtikten sonra).
5. **Özgüven etiketi tek başına işe yaramıyor.** Gemini “yüksek güven” %48,6 ile “orta”dan kötü. Bandı %65–70 olanlarda sapma var; %70+ “banko”yu olduğu gibi kupona yazmamak, 2–3 puan kısmek (Grok’ta da gördüğümüz şey).
6. **Aynı zayıf bacağı 4–5 kupona koymak zararı çarpıyor.** Shkendija, Heracles/Volendam, Athletic, AL Ain, Maroons. Bir maç en fazla bir (en fazla iki) kuponda olmalı.
7. **Piyango pazarları (`+6 Gol`, 0-0, 100x–300.000x) resmi portföye veya oynanan kuponlara girmemeli.** Claude 18’de 17 oynanan kuponun sıfırı tuttu; birkaçının toplam oranı üç haneli veya daha büyük.
8. **Tutması tesadüf olmayan örnek: Gemini gece 2,62’lik 4–5 bacak, kısa Alt/Üst ve ÇŞ.** Bunu kopyalamaya değer; 10x–50x, 6–7 bacak, MS 1 karışımını değil.
9. **Kendi karnesini olduğu gibi almamak.** Gemini canlı skoru “doğru” saymış, Red Star’ı hükmen 1-1 bitmiş yazmış, Juárez ilk yarısını yanlış vermiş. 4/4 gece kuponu ise gerçekten tutmuş. İkisi bir arada olabilir; bu yüzden bağımsız not şart.
10. **ChatGPT’nin olasılık kalibrasyonu örnek alınabilir**; kupon motoru değil. Claude 18’in düşük varyanslı 3–5’li kısa kuponları (C1–C3) da örnek; C4–C7 ve 19 Kasım seti değil.

Karşılaştırma için Claude’un 20–21 Kasım kendi dosyaları ve Antigravity/ChatGPT’nin 18–20 Kasım çıktıları hâlâ eksik. Gelince aynı yöntemle eklenebilir.
