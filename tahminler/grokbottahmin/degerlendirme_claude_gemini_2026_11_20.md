# Claude ve Gemini — 20 Kasım 2026 Tahmin Değerlendirmesi (Grok Bot, bağımsız)

- Hazırlanma: 21 Kasım 2026 (İstanbul saati, UTC+3). Ramazan'ın isteğiyle yapılan tek seferlik ertesi gün değerlendirmesi. Günlük rutin değildir.
- Sonuç kaynağı: Nesine'nin canlı skor ve sonuç akışı (`ls.nesine.com … GetUnliveMatches`, 20 ve 21 Kasım), 90. dakika ve ilk yarı skorları. Nesine kuponları 90. dakika skoruna göre ödediği için bu skor kullanıldı.
- Çapraz kontrol: ESPN skor tablosunda bulunan 26 maçın hepsi Nesine skoruyla birebir aynı çıktı.
- Piyasa kıyası: depodaki `data/global_odds` anlık görüntüleri (Betfair, Matchbook, Smarkets). Her maç için başlama saatinden önceki son görüntü alındı. Ortanca süre başlamadan yaklaşık 38 dakika önce. Gemini'nin 103 maçından 83'ü eşleşti.
- Hiçbir tahmin dosyası değiştirilmedi. Hiçbir şey GitHub'a gönderilmedi.

## 0. Önce veri durumu (önemli)

| Kaynak | Durum |
|---|---|
| Gemini `mac_tahminleri.csv` (103 maç), `kuponlar.csv` (9 kupon, 44 ayak), sniper ve kasa dosyası, öz-karne | Tam. Hepsi değerlendirildi. |
| **Claude'un 20 Kasım tahmin ve kupon dosyaları** | **Git geçmişinde yok.** `1baa197`, `0da04fc`, `1f1e0f3`, `31ee09c` ve `fa117fc` commit'leri yalnızca `tahminler/claudetahmin/README.md` dosyasına dokunuyor. `038c5d1` ve `4fb0451` ("today's open predictions removed") boş commit'ler, yani geçmiş sonradan temizlenmiş. Uzak depoda başka dal da yok. `reports/daily/2026-11-20/` hiç oluşmamış, ama `reports/ledger/INDEX.md` hâlâ bu klasöre bağlantı veriyor (kırık bağlantı). |
| Claude'dan elde kalan tek iz | `tahminler/ortak_arena/2026-11-20/` raporundaki 28 maçlık karşılaştırma tablosu. Bu tablo ikinci el bilgi ve seçilmiş bir örnek. Claude'un olasılıkları ve kuponları yok. |
| Nesine'nin maç öncesi oranları (20 Kasım) | Bu bilgisayarda saklanmış bir bülten kopyası yok. Gemini'nin yazdığı oranlar doğrulanamadı. |

Sonuç: **Gemini tam olarak değerlendirildi. Claude yalnızca 28 maçlık ikinci el örnekle değerlendirilebildi.** Claude'un tam karnesi için Claude'un çalıştığı bilgisayardaki `tahminler/claudetahmin/2026-11-20/` klasörü gerekiyor.

---

## 1. Gemini — genel karne (ana seçim, 103 maç)

| Ölçü | Değer |
|---|---|
| Tutan / toplam | **53 / 103 (%51,5)** |
| Gemini'nin verdiği ortalama olasılık | %62,6 (beklenen tutan sayısı 64,5, standart sapma 4,9) |
| Fark | 11,5 maç eksik, yani yaklaşık −2,4 standart sapma |
| Ortalama Nesine oranı | 1,347 |
| 1 birim sabit bahis, net | **−34,24 birim** |
| ROI | **−%33,2** |
| Gemini'nin kendi olasılığına göre beklenen değeri (EV) negatif olan seçim | **102 / 103** (ortalama EV −%16,4) |
| En olası skor tutan | 7 / 103 |

### 1.1 Gemini'nin öz-karnesindeki hatalar

Gemini'nin `mac_sonuclari_ve_karne_2026_11_20.csv` dosyası 21 Kasım 00:28'de, son maçlar hâlâ oynanırken yazılmış.

| Maç | Gemini'nin yazdığı | Gerçek (Nesine 90') | Etki |
|---|---|---|---|
| **Red Star - Pau** (ÇŞ X-2) | "1-1 (Ksl.)", **DOĞRU** | **2-1, YANLIŞ** | Kesinleşmiş diye bir maç yanlış puanlanmış |
| Cliftonville - Glentoran (3.5 Alt) | 82'de 2-1, "CANLI_TUTUYOR" | 3-2, YANLIŞ | Canlı skor kesin sonuç gibi sayılmış |
| Troyes - Le Havre (3.5 Alt) | 82'de 2-1, "CANLI_TUTUYOR" | 3-1, YANLIŞ | Aynı hata |
| Porto - Paredes (3.5 Üst) | 37'de 0-0 | 1-1 (90'), uzatmaya gitti | YANLIŞ, Gemini de "geride" demişti |

- Gemini'nin açıkladığı karne 51 doğru / 43 yanlış, canlılar dahil 56 / 47. **Gerçek karne 53 / 50.**
- Ortak arena raporundaki "Gemini v8.0: 59/49, −31,20 birim" (108 maç) rakamını yeniden kurdum. 103 maça gece kuponunun 5 maçı eklenince doğru rakam **58/50 ve −32,74 birim** oluyor. Aradaki fark tamamen Red Star - Pau'nun yanlış puanlanmasından geliyor: +1 tutan ve +1,54 birim.
- 21 Kasım gece kuponu raporunda (`kupon_gece_500tl…md`) iki tutarsızlık var:
  - (a) Dört ayağın oranları çarpılınca (1,48 × 1,24 × 1,22 × 1,24) **2,776** çıkıyor, raporda yazan **2,62** ile uyuşmuyor. Beş ayaktan seçilebilecek hiçbir 4'lü kombinasyon da 2,62 vermiyor. Ödeme rakamı (1.310 TL) doğrulanamadı.
  - (b) FC Juárez - Atlas için yazılan "45+4' Sepúlveda, ilk yarı 2-1" olay akışı Nesine'nin resmi gol akışıyla çelişiyor. Resmî akış: 19' 0-1, 23' 1-1, **ilk yarı 1-1**, 76' 2-1, 84' 2-2, 90' 2-3, 90' 3-3. "v8.1 düzeltmesi" bu uydurma anlatıya dayanıyor.

### 1.2 Pazar ailesine göre (Gemini ana seçim)

| Pazar | n | Tutan | İsabet | Ort. olasılık | Ort. oran | Net | ROI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Çifte Şans | 32 | 19 | %59,4 | %62,0 | 1,345 | −7,57 | −%23,7 |
| KG Var/Yok | 24 | 11 | %45,8 | %59,0 | 1,398 | −8,92 | −%37,2 |
| 3.5 Alt | 19 | 12 | %63,2 | %70,4 | 1,278 | −3,76 | −%19,8 |
| MS (1/2) | 16 | 5 | %31,2 | %61,7 | 1,366 | −9,71 | −%60,7 |
| 3.5 Üst | 4 | 0 | %0 | %54,0 | 1,418 | −4,00 | −%100 |
| 1.5 Üst | 3 | 2 | %66,7 | %65,4 | 1,267 | −0,48 | −%16,0 |
| 2.5 Alt | 3 | 2 | %66,7 | %61,7 | 1,357 | −0,29 | −%9,7 |
| 2.5 Üst | 2 | 2 | %100 | %61,7 | 1,245 | +0,49 | +%24,5 |

Seçim bazında:

| Seçim | n | Tutan | İsabet | Ort. olasılık | ROI |
|---|---:|---:|---:|---:|---:|
| 3.5 Alt | 19 | 12 | %63,2 | %70,4 | −%19,8 |
| KG Var | 19 | 11 | %57,9 | %59,0 | −%20,6 |
| ÇŞ X-2 | 18 | 8 | %44,4 | %60,2 | −%41,1 |
| ÇŞ 1-X | 12 | 9 | %75,0 | %64,0 | −%5,2 |
| MS 1 | 12 | 3 | %25,0 | %62,2 | −%68,8 |
| KG Yok | 5 | 0 | %0 | %59,2 | −%100 |
| MS 2 | 4 | 2 | %50,0 | %60,4 | −%36,5 |
| 3.5 Üst | 4 | 0 | %0 | %54,0 | −%100 |
| 1.5 Üst | 3 | 2 | %66,7 | %65,4 | −%16,0 |
| 2.5 Alt | 3 | 2 | %66,7 | %61,7 | −%9,7 |
| 2.5 Üst | 2 | 2 | %100 | %61,7 | +%24,5 |
| ÇŞ 1-2 | 2 | 2 | %100 | %66,5 | +%22,0 |

Gemini'nin kendi pazar tablosu KG ve MS için doğru. Alt/Üst ve ÇŞ ise canlı skorlar ve Red Star hatası yüzünden fazla görünüyor. Gerçek değerler Alt/Üst için 18/31 (Gemini 20/31 demiş), ÇŞ için 19/32 (Gemini 20/32 demiş).

### 1.3 Oran aralığına göre

| Nesine oranı | n | Tutan | İsabet | Ort. olasılık | Net | ROI |
|---|---:|---:|---:|---:|---:|---:|
| ≤1,25 | 28 | 22 | %78,6 | %68,1 | −1,19 | −%4,3 |
| 1,26–1,40 | 49 | 23 | %46,9 | %64,0 | −18,99 | −%38,8 |
| 1,41–1,60 | 21 | 7 | %33,3 | %55,1 | −10,69 | −%50,9 |
| 1,61–2,00 | 4 | 1 | %25,0 | %50,0 | −2,37 | −%59,2 |
| >2,00 | 1 | 0 | %0 | %49,9 | −1,00 | −%100 |

### 1.4 Kalibrasyon (olasılık aralığına göre)

| Gemini olasılığı | n | Tutan | Gerçekleşen | Ort. olasılık |
|---|---:|---:|---:|---:|
| <%50 | 2 | 0 | %0 | %47,8 |
| %50–60 | 40 | 15 | **%37,5** | %56,0 |
| %60–70 | 47 | 29 | %61,7 | %66,0 |
| %70–80 | 14 | 9 | %64,3 | %72,2 |

"Güven" etiketi de bilgi taşımıyor. **"yüksek" etiketli 35 seçim 17 tuttu (%48,6, ROI −%37,7). "orta" etiketli 68 seçim 36 tuttu (%52,9, ROI −%30,9).**

### 1.5 1X2 olasılık kalitesi (Brier ve log loss, 90. dakika sonucu)

| Model | Örnek | Brier (3 sınıf) ↓ | Log loss ↓ |
|---|---:|---:|---:|
| Gemini | 103 | 0,6748 | 1,1158 |
| Sabit taban oran (%45 / %27 / %28) | 103 | **0,6464** | **1,0692** |
| Eşit olasılık (1/3) | 103 | 0,6667 | 1,0986 |
| Gemini | 83 (piyasa eşleşen) | 0,6745 | 1,1150 |
| Keskin borsa (marjı ayrılmış, son görüntü) | 83 | 0,6722 | 1,1064 |
| Sabit taban oran | 83 | 0,6550 | 1,0812 |
| Eşit olasılık | 83 | 0,6667 | 1,0986 |

- Gemini'nin 1X2 olasılıkları keskin borsaya çok yakın: ortalama mutlak fark 2,2 puan. Yani model, piyasanın marjsız fiyatını büyük ölçüde kopyalıyor. **Piyasaya karşı kendi bilgisi yok.**
- **Bu gün sürprizli bir gündü.** Keskin borsa bile eşit olasılıktan kötü sonuç verdi. Borsanın favorisi 83 maçın %47'sini kazandı, beklenen %51'di. Gemini'nin MS/ÇŞ seçimlerinde borsa 23,0 tutan bekliyordu, 16 tuttu (−2,3 standart sapma). **Kötü isabetin bir kısmı şanssızlık. Tek bir günden model ağırlığı öğrenmek bu yüzden yanlış** (bkz. 4. bölüm).
- Beraberlik: Gemini ortalama %26,0 verdi, gerçekleşen %22,3.

### 1.6 Piyasaya göre değer: asıl sistematik hata

38 MS/ÇŞ ana seçimde keskin borsa fiyatıyla doğrudan kıyas yapılabildi:

| Ölçü | Değer |
|---|---|
| Gemini olasılığı (ortalama) | %60,7 |
| Keskin borsa marjsız olasılığı (ortalama) | %60,5 |
| Nesine oranının ima ettiği olasılık (ortalama) | %73,9 |
| Nesine ima / borsa oranı | MS'de ortalama 1,19, ÇŞ'de 1,24 |
| Borsa fiyatına göre +EV olan seçim | **0 / 38** |
| Borsa fiyatına göre ortalama EV | **−%18,1** |

Gemini seçimleri değere göre değil, yüksek olasılığa göre yapıyor. Nesine'nin MS/ÇŞ'deki marjı bu seçimlerde %19–24 arası. Bu marjla "olası olanı seç" yaklaşımı uzun vadede kesin zarar ettirir. Gemini'nin kendi dosyası da bunu söylüyor: 103 seçimin 102'sinde kendi olasılığı × oran < 1.

Not: Gemini'nin notlarının 71'inde "Nesine canlı" ifadesi geçiyor. Ama oran / borsa oranı çok dar bir bantta (standart sapma yaklaşık 0,05). Bu, oranların canlı oynanmış fiyatlar değil, normal maç öncesi Nesine marjı olduğunu gösteriyor. Maç öncesi bülten saklanmadığı için kesin doğrulanamadı.

### 1.7 xG gerçekçiliği

| Ölçü | Gemini xG | Gerçek gol |
|---|---:|---:|
| Maç başı toplam | 2,93 | 2,91 |
| Ev sahibi | 1,68 | 1,52 |
| Deplasman | 1,25 | 1,39 |
| Toplam xG ile toplam gol korelasyonu | 0,20 | |
| xG farkı ile gol farkı korelasyonu | 0,22 | |

Ortalama gol seviyesi doğru. Ev sahibi biraz fazla, deplasman biraz az tahmin edilmiş. Maç bazında ayırt etme gücü zayıf (tek gün, n=103). Alt/Üst ve KG olasılıkları xG'ye dayalı Poisson hesabıyla tutarlı: ortalama fark 2,6 puan, en fazla 9,6 puan.

### 1.8 En büyük ıskalar (en yüksek güvenle yanlış çıkanlar)

| Saat | Maç | Seçim @ oran | Olasılık | Güven | Skor (İY) | Gemini xG |
|---|---|---|---:|---|---|---|
| 22:45 | Troyes - Le Havre | 3.5 Alt @ 1,20 | %75,2 | yüksek | 3-1 (1-1) | 1,56–1,16 |
| 22:45 | Cliftonville - Glentoran | 3.5 Alt @ 1,21 | %73,3 | orta | 3-2 (1-1) | 1,34–1,48 |
| 22:30 | Andorra - Leganes | 3.5 Alt @ 1,22 | %72,4 | yüksek | 1-3 (1-2) | 1,67–1,20 |
| 21:30 | Rapperswil - Aarau | ÇŞ X-2 @ 1,21 | %71,4 | orta | 2-1 (1-0) | 1,43–1,85 |
| 22:00 | Jong Utrecht - Emmen | ÇŞ X-2 @ 1,28 | %70,1 | yüksek | 1-0 (0-0) | 1,52–1,92 |
| 20:30 | Ahli Saudi - Al Nassr | 3.5 Alt @ 1,38 | %69,7 | yüksek | 3-1 (1-1) | 1,30–1,70 |
| 18:00 | Sumgayit - Sabah | 3.5 Alt @ 1,37 | %69,4 | orta | 1-5 (1-2) | 0,80–2,25 |
| 22:00 | C. Brugge U23 - Excelsior V. | 3.5 Alt @ 1,35 | %69,3 | orta | 2-2 (1-1) | 1,60–1,42 |
| 18:30 | Botoșani - Voluntari | 3.5 Alt @ 1,32 | %69,3 | orta | 3-3 (2-0) | 1,98–1,05 |
| 15:00 | Shkendija - Baskimi | MS 1 @ 1,32 | %69,3 | orta | 0-1 (0-0) | 2,32–0,75 |
| 14:30 | East Bengal - Hyderabad | MS 1 @ 1,28 | %68,8 | orta | 2-2 (1-1) | 2,70–1,05 |
| 19:00 | ES Sétif - US Biskra | KG Yok @ 1,34 | %67,8 | orta | 1-1 (0-1) | 1,71–0,50 |

- 3.5 Alt toplamda kâr bırakmadı ama en büyük ıskaların 7'si 3.5 Alt. Isabet %63, verilen olasılık %70. Gerekçe: 1,20–1,38 oranla 4+ gollü maç riski karşılanmıyor.
- MS 1 ev favorileri 12'de 3 tuttu. Verilen olasılık %62'ydi.
- KG Yok 5'te 0 tuttu.

## 2. Gemini kuponları (9 kupon, 44 ayak)

| # | Kupon | Oran | Gemini'nin tutma olasılığı | Tutan ayak | Yatıran ayaklar |
|---|---|---:|---:|---:|---|
| 1 | Karma 5x | 5,07 | %14,97 | 1/5 | Shkendija MS 1 (0-1), Ahli Saudi 3.5 Alt (3-1), Heracles 3.5 Üst (2-1), Volendam 3.5 Üst (1-2) |
| 2 | Karma 10x | 10,26 | %7,26 | 2/5 | Sétif MS 1 (1-1), Heracles Hnd(0:2) 1 (2-1), Volendam MS 1 (1-2) |
| 3 | Karma 20x | 20,10 | %2,68 | 3/6 | East Bengal İY 1 (İY 1-1), Jong Utrecht 3.5 Üst (1-0), Bilbao KG Var (0-1) |
| 4 | Karma 30x | 30,21 | %2,27 | 3/6 | East Bengal Hnd(0:1) 1 (2-2), Shkendija İY 1 (İY 0-0), Aarhus F. MS 1 (1-1) |
| 5 | Karma 50x | 58,26 | %0,92 | 4/7 | Shkendija Hnd(0:1) 1 (0-1), Hammam-Lif 1.5 Alt (0-3), Molde ÇŞ 1-X (2-4) |
| 6 | MS 1-2 5x | 5,02 | %15,67 | 1/4 | Shkendija, Sétif, Verona MS 1 |
| 7 | Alt/Üst 5x | 5,11 | %13,83 | 2/5 | Ahli Saudi 3.5 Alt, Heracles 3.5 Üst, Volendam 3.5 Üst |
| 8 | KG 5x | 5,02 | %13,75 | 2/4 | Cercle KG Var (1-0), Bilbao KG Var (0-1) |
| 9 | İY/MS 5x | 6,30 | %13,21 | 1/2 | Bilbao İY/MS 1/1 (0-1) |

- **Kazanan kupon 0/9.** Tek ayakla kaçan kupon yalnızca 9 numara (2 ayaklı İY/MS kuponu, Bilbao İY/MS 1/1 yattı). Öteki 8 kupon 2–4 ayak kaybetti.
- Ayak isabeti **19/44 (%43,2)**, verilen ortalama olasılık %58,0.
- Kasa dağılımında 100 birimin tamamı bu 9 kupona ayrılmış. Oynansaydı 100 birimin hepsi giderdi.
- Handikap ayakları 0/3, İY ayakları 0/2, 3.5 Üst ayakları 4/9 tuttu.
- **Aynı seçime kuponda daha yüksek olasılık yazılmış.** Ana dosya ile kupon dosyası aynı seçim için farklı olasılık kullanıyor:

| Maç / seçim | Ana dosya | Kupon dosyası |
|---|---:|---:|
| Heracles - Jong PSV 3.5 Üst | %58,1 | %69,6 |
| Volendam - Jong Ajax 3.5 Üst | %56,3 | %66,4 |
| Dinamo Tiflis - Torpedo KG Var | %57,1 | %64,5 |
| AGF - Lyngby KG Var | %56,8 | %64,2 |
| Cercle Brugge - Westerlo KG Var | %60,5 | %65,3 |
| Shkendija - Baskimi MS 1 | %69,3 | %72,4 |

  Kuponların "tutma olasılığı" ve "+%10,9 avantaj" rakamları bu şişirilmiş olasılıklarla hesaplanmış.
- **Maç tekrarı:** Shkendija 4 kuponda, Andorra - Leganes 4 kuponda, Heracles, Volendam, East Bengal, Rostov ve Bilbao 3'er kuponda var. Shkendija'nın 0-1 bitmesi tek başına 4 kuponu yaktı. Gemini kendi öz-öğrenme notunda "en fazla 2 kupon" kuralını koymuş ama bunu kupon kurulduktan sonra yazmış.
- **Kendi kalkanını çiğniyor.** Sniper dosyası Molde - Bodø için "Yasaklı: MS 1, ÇŞ 1-X" diyor (borsada MS 2 oranı %10,5 düşmüş). Buna rağmen hem ana seçim hem 50x kuponun bir ayağı **ÇŞ 1-X**. Maç 2-4 bitti.
- **"Gecikme sniper" tekli bahisleri:** 9 seçim, 4 tuttu, önerilen 3,6 birimle net −2,49 birim. Bu 9 seçimin 8'inde Gemini'nin kendi EV'si negatif yazılmış (−%3,8 ile −%8,4 arası), yine de birim önerilmiş. "global_adil_olasilik" sütunu da Gemini'nin kendi olasılığıyla aynı, örneğin Ahli Saudi'de %69,71. Yani bu sütun piyasa fiyatı değil.

## 3. Claude — elde kalan 28 maçlık örnek (ikinci el)

**Uyarı:** Bu 28 maç, ortak arena raporunu yazan tarafın seçtiği "ayrışma / uzlaşı" örnekleri. Rastgele değiller. 3'ü 21 Kasım sabahı oynanan maçlar. Claude'un olasılıkları yok, bu yüzden kalibrasyon, Brier ve kupon analizi yapılamadı. Tablodaki skorları ve doğru/yanlış etiketlerini Nesine akışıyla tek tek kontrol ettim. **28 maçın 28'i doğru çıktı.**

| Ölçü (aynı 28 maç) | Claude | Gemini |
|---|---:|---:|
| Tutan | 13 / 28 (%46,4) | 16 / 28 (%57,1) |
| Ortalama oran | 1,47 | 1,36 |
| 1 birim net | −9,05 | −6,99 |
| ROI | −%32,3 | −%25,0 |
| Yalnız 20 Kasım maçları (25) | 11/25, −9,39 | 13/25, −7,77 |
| Farklı seçim yapılan 20 maç | 10/20, −4,87 | 13/20, −2,81 |
| **Birebir aynı seçim** | 8 maç, 3 tuttu | aynı |

Claude'un bu örnekteki pazar dağılımı:

| Pazar | n | Tutan | Ort. oran | Net |
|---|---:|---:|---:|---:|
| MS (1/2) | 12 | 5 | 1,46 | −4,49 |
| KG Var/Yok | 5 | 2 | 1,48 | −2,31 |
| 2.5 Alt | 4 | 2 | 1,84 | −0,32 |
| Çifte Şans | 4 | 3 | 1,25 | −0,21 |
| 3.5 Alt | 2 | 1 | 1,32 | −0,72 |
| 3.5 Üst | 1 | 0 | 1,24 | −1,00 |

- **Claude'un bu örnekte görünen hatası ev sahibi favorisine MS 1.** 12 MS seçiminden 7'si yattı: East Bengal 2-2, Dewa 0-1, AGMK 0-1, Shkendija 0-1, Verona 0-2, Andorra 1-3, Bilbao 0-1.
- **8 maçta Claude ve Gemini aynı seçimi aynı oranla yapmış:** East Bengal, Dewa, AGMK ve Shkendija'da MS 1, Bayern'de 3.5 Üst, Beijing'de 3.5 Alt, Zob Ahan'da ÇŞ 1-2, Lokomotiv'de KG Var. Bu, iki yapay zekânın da depodaki aynı `nesine_global` ana seçim çıktısını kullandığını düşündürüyor. Yani bu maçlarda birbirinden bağımsız tahmin yok, hata ortak.
- Arena raporundaki "Claude: 108 maç, 62/46, −23,80 birim" rakamı **doğrulanamadı.** Kaynak tahmin dosyası yok.

## 4. Ortak arena raporu (v8.1 / "meta v8.2") hakkında

- "Gemini v8.1: %63,9" ve "ortak meta v8.2: %70,4 (76/32)" skorları **sonuçlar bilindikten sonra seçilen tahminlerle** hesaplanmış. Örnek: Juárez maçı için "model seçimini doğrudan 1.5 Üst olarak güncelledi" yazıyor. Bu, maçtan sonra yapılmış bir geriye dönük uyum. Örneklem dışı bir başarı ölçüsü değil, gerçek performans olarak kullanılamaz.
- `multi_ai_learned_weights_v82.json` ağırlıkları tek günden, pazar başına 11–35 seçimden öğrenilmiş. Bu gün piyasanın bile eşit olasılıktan kötü kaldığı sürprizli bir gündü (1.5. bölüm). Bu ağırlıklar büyük ölçüde gürültü.

## 5. Sistematik hatalar: özet

**Gemini**
1. Değer yerine olasılığa göre seçim yapıyor. Kendi olasılığına göre 103 seçimin 102'si −EV, borsa fiyatına göre 38'in 38'i −EV. ROI −%33.
2. Olasılıklar piyasanın kopyası. 1X2'de borsaya ortalama 2,2 puan uzak, Brier ve log loss'ta borsadan kötü. Sabit taban orandan bile kötü.
3. Aşırı güven, özellikle %50–60 aralığında: %56 verdi, %37,5 gerçekleşti. 1,26–1,60 oran bandında 70 seçim, 30 tuttu, ROI yaklaşık −%42.
4. Kuponda olasılık şişirme, aynı maçı çok kupona koyma ve kendi koyduğu yasakları çiğneme (Molde).
5. Öz-karnede canlı skoru kesin sonuç saymak, bir yanlış puanlama (Red Star) ve uydurma maç anlatısı (Juárez).
6. Tek günden "öğrenme" ve sonuçtan sonra seçilmiş tahminlerle başarı ilan etmek.
7. Dosyalar maçlar bittikten sonra GitHub'a yüklenmiş (21 Kasım 00:00–00:32). Maç öncesine ait zaman damgası yok, maç öncesi oranlar doğrulanamıyor.

**Claude (28 maçlık sınırlı örnek)**
1. Düşük oranlı ev favorisine MS 1: 12 MS seçiminden 5'i tuttu.
2. Seçimlerin bir kısmı Gemini'yle birebir aynı. Bağımsız bir görüş yok.
3. Tahmin dosyaları paylaşılan yerde saklanmadığı için ertesi gün denetlenemiyor.

## 6. Somut öneriler

**Gemini için**
1. Ana seçimi "en olası seçim" değil, **EV ≥ +%2 (keskin borsa marjsız fiyatına göre, Nesine oranıyla)** kuralıyla seçsin. Hiç seçim kalmazsa "oynanmaz" desin.
2. Ana dosya, kupon ve sniper için **tek bir olasılık kaynağı** kullansın. Kupon dosyası olasılığı kendisi üretmesin.
3. Maç tekrarı sınırı (en fazla 2 kupon) ve kendi kalkan yasakları kupon kurulmadan önce zorunlu kontrol olsun.
4. Öz-karne yalnızca resmî akış maçı "MS" (bitti) gösterdikten sonra yazılsın. "Ksl." ya da canlı skor ile puanlama yapılmasın. Ertesi gün `scripts/gun_degerlendirme.py` kullanılsın.
5. Tahmin dosyası maç başlamadan önce zaman damgasıyla yazılsın. Oranın çekildiği saat ve maç öncesi mi canlı mı olduğu sütun olarak eklensin.
6. Model ağırlıkları en az birkaç yüz seçimlik, örneklem dışı pencereden öğrenilsin. v8.1 / v8.2'nin tek günlük ağırlıkları kullanılmasın.
7. Hata analizinde yalnızca resmî olay verisi kullanılsın (Nesine MEWS, ESPN). Hatırlanan ya da üretilen olay akışı kullanılmasın.

**Claude için**
1. 20 Kasım tahmin dosyası (`tahminler/claudetahmin/2026-11-20/`) Claude'un bilgisayarında duruyorsa orada `scripts/gun_degerlendirme.py --tarih 2026-11-20` çalıştırılsın, ya da dosyanın bir kopyası ortak `degerlendirme/` alanına konsun. Tam karne ancak böyle çıkar.
2. Düşük oranlı ev favorisine MS 1'de keskin borsa fiyatına göre EV kontrolü zorunlu olsun.
3. Gemini'yle aynı ana seçim çıktısını kullanıyorsa, "iki AI karşılaştırması" aslında aynı sinyali iki kez sayıyor. Bağımsız bir görüş katmanı (kendi modeli ya da kendi araştırması) eklensin.

**Ortak sistem için**
- `reports/ledger/INDEX.md` içindeki 20 Kasım satırı var olmayan `reports/daily/2026-11-20/` klasörüne işaret ediyor, düzeltilmeli.
- 20 Kasım'ın maç öncesi Nesine bülteni saklanmamış. Gelecekte değerlendirme için bülten anlık görüntüsü tahminle birlikte saklanmalı.

---

## Ek A — Gemini ana seçimlerinin tamamı (Nesine 90. dakika skoru)

Handikap kuralı: Nesine'nin `Hnd(0:N) 1` yazımı deplasmana +N gol verir, ev sahibinin N+1 farkla kazanmasını gerektirir. Uzatmaya giden iki maçta (Kahrabaa Ismailia ve Porto) 90. dakika skoru kullanıldı.

| Saat | Maç | Seçim | Oran | Olasılık | Skor (İY) | Sonuç |
|---|---|---|---:|---:|---|:-:|
| 14:30 | SC East Bengal - Hyderabad | MS 1 | 1.28 | 68.8% | 2-2 (1-1) | ✗ |
| 14:30 | Albirex Niigata (Sin) - Balestier | KG Var | 1.28 | 61.5% | 3-2 (1-1) | ✓ |
| 14:30 | Swit Skolwin - S. Stalowa | 3.5 Alt | 1.33 | 69.0% | 1-2 (1-1) | ✓ |
| 14:35 | Beijing Guoan - Shanghai Port | 3.5 Alt | 1.28 | 64.3% | 0-2 (0-1) | ✓ |
| 15:00 | Dewa Utd - Persita Tangerang | MS 1 | 1.38 | 60.6% | 0-1 (0-0) | ✗ |
| 15:00 | FK Agmk - Qizilqum Zarafshon | MS 1 | 1.52 | 56.5% | 0-1 (0-0) | ✗ |
| 15:00 | Lokomotiv Taşkent - Pakhtakor Tashkent | KG Var | 1.34 | 59.4% | 2-1 (0-1) | ✓ |
| 15:00 | Lee Man Warriors - Golik North D. | ÇŞ 1-X | 1.22 | 67.5% | 3-1 (0-0) | ✓ |
| 15:00 | KF Shkendija Haracine - FK Baskimi | MS 1 | 1.32 | 69.3% | 0-1 (0-0) | ✗ |
| 15:00 | Zob Ahan - Shams Azar Qazvin | ÇŞ 1-2 | 1.20 | 66.5% | 3-0 (0-0) | ✓ |
| 15:15 | CLB Viettel - Song Lam | ÇŞ X-2 | 1.52 | 55.2% | 0-0 (0-0) | ✓ |
| 15:30 | NK Opatija - Dinamo Zagreb II | 2.5 Alt | 1.36 | 61.1% | 1-2 (0-2) | ✗ |
| 15:30 | Bihor Oradea - ACS Gloria | ÇŞ X-2 | 1.41 | 51.0% | 5-1 (2-0) | ✗ |
| 15:45 | Persepolis - Paykan | 1.5 Üst | 1.20 | 66.9% | 3-0 (1-0) | ✓ |
| 15:45 | AL Ittihad K. - Sharjah | ÇŞ 1-X | 1.45 | 56.0% | 0-3 (0-1) | ✗ |
| 16:00 | AL Duhail SC - Katar SC | 2.5 Üst | 1.21 | 58.9% | 1-2 (0-1) | ✓ |
| 16:00 | AL Sadd - Lusail SC | KG Yok | 2.03 | 49.9% | 3-2 (3-2) | ✗ |
| 16:00 | Terengganu - Brunei Dpmm | KG Var | 1.35 | 57.9% | 1-2 (1-0) | ✓ |
| 16:30 | Hammam Sousse - A Sakiet Edayer | ÇŞ X-2 | 1.21 | 68.8% | 0-0 (0-0) | ✓ |
| 16:30 | CS Hammam - ES Metlaoui | ÇŞ 1-2 | 1.24 | 66.6% | 0-3 (0-1) | ✓ |
| 16:30 | Olympique B. - AS Marsa | 2.5 Alt | 1.21 | 67.2% | 1-1 (0-0) | ✓ |
| 16:30 | N. Namangan - FK Neftchi Fargona | ÇŞ X-2 | 1.37 | 60.7% | 3-2 (1-1) | ✗ |
| 17:00 | Bengaluru - Mumbai City | KG Var | 1.54 | 54.8% | 2-0 (0-0) | ✗ |
| 17:00 | AL Minaa - Karbalaa | KG Yok | 1.51 | 54.3% | 3-2 (2-2) | ✗ |
| 17:30 | SN Abadan - Esteghlal K. | ÇŞ 1-X | 1.20 | 69.4% | 2-1 (2-0) | ✓ |
| 18:00 | KF Skenderbeu Korce - KF Egnatia | ÇŞ 1-X | 1.63 | 51.4% | 1-0 (1-0) | ✓ |
| 18:00 | Sumgayit - Sabah | 3.5 Alt | 1.37 | 69.4% | 1-5 (1-2) | ✗ |
| 18:00 | Kahrabaa Ismailia - Cer. Cleopatra | MS 2 | 1.36 | 53.5% | 2-2 (1-2) | ✗ |
| 18:25 | Al Ahli Dubai - Ajman Club | MS 1 | 1.21 | 66.6% | 3-1 (2-0) | ✓ |
| 18:30 | Botosani - Voluntari | 3.5 Alt | 1.32 | 69.3% | 3-3 (2-0) | ✗ |
| 18:30 | AL Gharrafa - Arabi Doha | ÇŞ X-2 | 1.24 | 66.1% | 3-2 (1-2) | ✗ |
| 19:00 | Shakhtar D. - Levy Bereg Kiev | KG Yok | 1.44 | 58.8% | 1-1 (0-1) | ✗ |
| 19:00 | FK Septemvri Sofia - Loko Plovdiv | ÇŞ 1-X | 1.21 | 70.2% | 0-0 (0-0) | ✓ |
| 19:00 | Dinamo Tiflis - Torpedo | KG Var | 1.43 | 57.1% | 1-1 (0-1) | ✓ |
| 19:00 | ASO Chlef - USM Khenchela | 1.5 Üst | 1.32 | 63.6% | 2-0 (0-0) | ✓ |
| 19:00 | ES Setif - US Biskra | KG Yok | 1.34 | 67.8% | 1-1 (0-1) | ✗ |
| 19:00 | Taborsko - Slavia Praha B | KG Var | 1.33 | 58.6% | 3-1 (1-0) | ✓ |
| 19:00 | Nd Dravinja - NK Ilirija | ÇŞ X-2 | 1.24 | 68.6% | 2-2 (0-0) | ✓ |
| 19:30 | FK Rostov - Krylia Sovetov | ÇŞ 1-X | 1.21 | 78.9% | 3-0 (1-0) | ✓ |
| 20:00 | Iğdır FK - Ümraniyespor | KG Var | 1.58 | 50.6% | 2-2 (1-1) | ✓ |
| 20:00 | Piast Gliwice - Korona Kielce | 3.5 Alt | 1.26 | 70.1% | 2-0 (1-0) | ✓ |
| 20:00 | Independiente D. - CSD Macara | MS 1 | 1.28 | 62.3% | 0-1 (0-1) | ✗ |
| 20:00 | Karvina - Banik Ostrava B | MS 1 | 1.29 | 64.5% | 1-3 (1-1) | ✗ |
| 20:00 | Pribram - Usti Nad Labem | KG Var | 1.33 | 59.5% | 1-0 (0-0) | ✗ |
| 20:00 | C. Glogow - Puszcza | ÇŞ X-2 | 1.34 | 58.5% | 0-2 (0-1) | ✓ |
| 20:00 | Lechia Zielona G. - Chojniczanka | ÇŞ 1-X | 1.28 | 63.8% | 1-1 (1-0) | ✓ |
| 20:30 | A. Bielefeld - Magdeburg | 3.5 Alt | 1.26 | 71.9% | 1-2 (0-2) | ✓ |
| 20:30 | Darmstadt 98 - Heidenheim | KG Var | 1.33 | 60.8% | 3-1 (2-1) | ✓ |
| 20:30 | Ahli Saudi - AL Nassr | 3.5 Alt | 1.38 | 69.7% | 3-1 (1-1) | ✗ |
| 20:30 | St. Polten - ASK Voitsberg | KG Var | 1.33 | 58.9% | 0-2 (0-1) | ✗ |
| 20:30 | Kapfenberger - Wsc Hertha | 3.5 Alt | 1.26 | 70.5% | 1-0 (0-0) | ✓ |
| 20:30 | R. Wien (Amt) - Blau Weiss L. | MS 2 | 1.24 | 67.9% | 1-6 (1-3) | ✓ |
| 20:30 | Floridsdorfer - Austria Wien II | ÇŞ X-2 | 1.39 | 56.7% | 3-1 (1-0) | ✗ |
| 20:30 | Af Elbasani - D. Tirana | 2.5 Alt | 1.50 | 56.9% | 1-0 (0-0) | ✓ |
| 21:00 | Molde - Bodo Glimt | ÇŞ 1-X | 1.83 | 50.7% | 2-4 (0-2) | ✗ |
| 21:00 | AGF Aarhus - Lyngby BK | KG Var | 1.41 | 56.8% | 2-1 (2-1) | ✓ |
| 21:00 | TSV Havelse - Viktoria Köln | MS 2 | 1.30 | 65.7% | 1-6 (0-2) | ✓ |
| 21:00 | Aarhus Fremad - Hobro | MS 1 | 1.80 | 52.2% | 1-1 (1-0) | ✗ |
| 21:00 | Kolding - Aalborg BK | 3.5 Alt | 1.23 | 67.6% | 1-1 (0-1) | ✓ |
| 21:00 | CD Teruel - Hercules | 1.5 Üst | 1.28 | 65.7% | 0-1 (0-1) | ✗ |
| 21:30 | Farul Cons. - U. Cluj | ÇŞ X-2 | 1.21 | 66.0% | 2-3 (1-1) | ✓ |
| 21:30 | Stade Ouchy - Kriens | MS 1 | 1.26 | 65.3% | 3-1 (1-1) | ✓ |
| 21:30 | Rapperswil - Aarau | ÇŞ X-2 | 1.21 | 71.4% | 2-1 (1-0) | ✗ |
| 21:30 | Std. Nyonnis - Wil 1900 | KG Var | 1.32 | 59.8% | 0-1 (0-0) | ✗ |
| 21:30 | N. Xamax - Etoile Carouge | 3.5 Alt | 1.23 | 69.4% | 1-0 (0-0) | ✓ |
| 22:00 | AS Nancy - Dijon | 3.5 Alt | 1.27 | 71.7% | 1-0 (0-0) | ✓ |
| 22:00 | Annecy - Clermont | ÇŞ X-2 | 1.49 | 53.2% | 4-2 (2-0) | ✗ |
| 22:00 | Guingamp - Rodez AF | KG Var | 1.38 | 59.5% | 1-3 (1-1) | ✓ |
| 22:00 | Metz - US Boulogne | ÇŞ X-2 | 1.49 | 54.9% | 2-1 (1-1) | ✗ |
| 22:00 | Red Star - Pau | ÇŞ X-2 | 1.54 | 53.2% | 2-1 (1-0) | ✗ |
| 22:00 | Almere City - NAC Breda | ÇŞ X-2 | 1.22 | 66.5% | 1-4 (0-3) | ✓ |
| 22:00 | Graafschap - Maastricht | 2.5 Üst | 1.28 | 64.4% | 3-0 (0-0) | ✓ |
| 22:00 | Den Bosch - VVV Venlo | ÇŞ X-2 | 1.45 | 53.0% | 1-0 (1-0) | ✗ |
| 22:00 | Volendam - Jong Ajax | 3.5 Üst | 1.42 | 56.3% | 1-2 (1-0) | ✗ |
| 22:00 | Helmond - Dordrecht | ÇŞ 1-X | 1.21 | 67.4% | 5-1 (3-0) | ✓ |
| 22:00 | Heracles - Jong PSV | 3.5 Üst | 1.39 | 58.1% | 2-1 (1-0) | ✗ |
| 22:00 | Jong Utrecht - Emmen | ÇŞ X-2 | 1.28 | 70.1% | 1-0 (0-0) | ✗ |
| 22:00 | TOP Oss - Roda | KG Var | 1.39 | 61.7% | 1-0 (1-0) | ✗ |
| 22:00 | Vitesse - Jong AZ Alkmaar | KG Var | 1.31 | 64.0% | 0-3 (0-3) | ✗ |
| 22:00 | C. Brugge U23 - Excelsior V. | 3.5 Alt | 1.35 | 69.3% | 2-2 (1-1) | ✗ |
| 22:00 | Lierse K. - KSC Lokeren Temse | KG Var | 1.28 | 59.3% | 1-0 (1-0) | ✗ |
| 22:00 | MC Oran - JS Saoura | KG Yok | 1.27 | 65.3% | 3-1 (2-0) | ✗ |
| 22:00 | FK Mornar Bar - FK Sutjeska | ÇŞ X-2 | 1.42 | 55.2% | 0-0 (0-0) | ✓ |
| 22:15 | Yverdon - Winterthur | ÇŞ 1-X | 1.22 | 68.1% | 2-0 (1-0) | ✓ |
| 22:30 | Bayern Münih - Köln | 3.5 Üst | 1.24 | 56.0% | 1-1 (1-1) | ✗ |
| 22:30 | Hellas Verona - AC Cesena | 3.5 Alt | 1.26 | 72.7% | 0-2 (0-1) | ✓ |
| 22:30 | Andorra - Leganes | 3.5 Alt | 1.22 | 72.4% | 1-3 (1-2) | ✗ |
| 22:30 | Pogon Szczecin - Slask Wroclaw | KG Var | 1.40 | 56.8% | 1-2 (0-0) | ✓ |
| 22:30 | Inverness - Ayr Utd | MS 1 | 1.40 | 58.4% | 0-0 (0-0) | ✗ |
| 22:30 | SV Austria Salzburg - Admira Wacker | 3.5 Alt | 1.33 | 68.8% | 1-2 (1-1) | ✓ |
| 22:30 | Casertana - Salernitana | ÇŞ 1-X | 1.20 | 69.5% | 2-2 (0-1) | ✓ |
| 22:30 | M. Legnica - LKS Lodz | 3.5 Alt | 1.24 | 71.9% | 1-1 (0-0) | ✓ |
| 22:30 | Ca Cerro - Nacional | MS 2 | 1.49 | 54.7% | 2-0 (1-0) | ✗ |
| 22:45 | Troyes - Le Havre | 3.5 Alt | 1.20 | 75.2% | 3-1 (1-1) | ✗ |
| 22:45 | Cercle Brugge - Westerlo | KG Var | 1.39 | 60.5% | 1-0 (0-0) | ✗ |
| 22:45 | Southend - Boreham Wood | ÇŞ 1-X | 1.45 | 55.6% | 2-3 (0-3) | ✗ |
| 22:45 | Cliftonville - Glentoran | 3.5 Alt | 1.21 | 73.2% | 3-2 (1-1) | ✗ |
| 22:45 | Penybont - Haverfordwest C. | MS 1 | 1.28 | 64.3% | 2-0 (1-0) | ✓ |
| 23:00 | Ath Bilbao - Espanyol | 3.5 Alt | 1.29 | 70.5% | 0-1 (0-0) | ✓ |
| 23:00 | Barnsley - S. Wednesday | KG Var | 1.25 | 62.9% | 1-2 (1-2) | ✓ |
| 23:00 | Villarreal B - Gimnastic | MS 1 | 1.45 | 57.5% | 2-2 (1-2) | ✗ |
| 23:15 | Real Madrid B - Murcia | ÇŞ X-2 | 1.45 | 54.8% | 0-2 (0-2) | ✓ |
| 23:45 | Porto - Paredes | 3.5 Üst | 1.62 | 45.8% | 1-1 (1-0) | ✗ |

## Ek B — Claude ve Gemini, ortak arena raporundaki 28 maç (skorlar Nesine akışından)

| Saat | Maç | Skor (İY) | Claude seçimi | Sonuç | Gemini seçimi | Sonuç |
|---|---|---|---|:-:|---|:-:|
| 22:30 | Bayern Münih - Köln | 1-1 (1-1) | 3.5 Üst @ 1.24 | ✗ | 3.5 Üst @ 1.24 | ✗ |
| 04:00 | Puebla - Atlético San Luis | 1-1 (1-0) | 2.5 Alt @ 1.82 | ✓ | 1.5 Üst @ 1.22 | ✓ |
| 06:00 | FC Juárez - Atlas | 3-3 (1-1) | 2.5 Alt @ 1.85 | ✗ | ÇŞ X-2 @ 1.24 | ✓ |
| 20:30 | A. Bielefeld - Magdeburg | 1-2 (0-2) | 2.5 Alt @ 1.84 | ✗ | 3.5 Alt @ 1.26 | ✓ |
| 23:00 | Ath Bilbao - Espanyol | 0-1 (0-0) | MS 1 @ 1.33 | ✗ | 3.5 Alt @ 1.29 | ✓ |
| 22:00 | AS Nancy - Dijon | 1-0 (0-0) | 2.5 Alt @ 1.86 | ✓ | 3.5 Alt @ 1.27 | ✓ |
| 22:30 | Hellas Verona - AC Cesena | 0-2 (0-1) | MS 1 @ 1.54 | ✗ | 3.5 Alt @ 1.26 | ✓ |
| 06:10 | Tijuana - Atlante | 1-0 (0-0) | MS 1 @ 1.52 | ✓ | 3.5 Alt @ 1.32 | ✓ |
| 22:30 | Andorra - Leganes | 1-3 (1-2) | MS 1 @ 1.64 | ✗ | 3.5 Alt @ 1.22 | ✗ |
| 15:30 | NK Opatija - Dinamo Zagreb II | 1-2 (0-2) | ÇŞ X-2 @ 1.35 | ✓ | 2.5 Alt @ 1.36 | ✗ |
| 15:30 | Bihor Oradea - ACS Gloria | 5-1 (2-0) | MS 1 @ 1.86 | ✓ | ÇŞ X-2 @ 1.41 | ✗ |
| 16:00 | AL Sadd - Lusail SC | 3-2 (3-2) | KG Var @ 1.35 | ✓ | KG Yok @ 2.03 | ✗ |
| 17:00 | AL Minaa - Karbalaa | 3-2 (2-2) | MS 1 @ 1.56 | ✓ | KG Yok @ 1.51 | ✗ |
| 18:00 | Sumgayit - Sabah | 1-5 (1-2) | MS 2 @ 1.24 | ✓ | 3.5 Alt @ 1.37 | ✗ |
| 16:30 | Olympique B. - AS Marsa | 1-1 (0-0) | ÇŞ 1-2 @ 1.22 | ✗ | 2.5 Alt @ 1.21 | ✓ |
| 18:00 | KF Skenderbeu Korce - KF Egnatia | 1-0 (1-0) | KG Var @ 1.62 | ✗ | ÇŞ 1-X @ 1.63 | ✓ |
| 20:30 | Af Elbasani - D. Tirana | 1-0 (0-0) | KG Var @ 1.60 | ✗ | 2.5 Alt @ 1.50 | ✓ |
| 22:00 | Guingamp - Rodez AF | 1-3 (1-1) | 3.5 Alt @ 1.35 | ✗ | KG Var @ 1.38 | ✓ |
| 14:30 | SC East Bengal - Hyderabad | 2-2 (1-1) | MS 1 @ 1.28 | ✗ | MS 1 @ 1.28 | ✗ |
| 15:00 | Dewa Utd - Persita Tangerang | 0-1 (0-0) | MS 1 @ 1.38 | ✗ | MS 1 @ 1.38 | ✗ |
| 15:00 | FK Agmk - Qizilqum Zarafshon | 0-1 (0-0) | MS 1 @ 1.52 | ✗ | MS 1 @ 1.52 | ✗ |
| 15:00 | KF Shkendija Haracine - FK Baskimi | 0-1 (0-0) | MS 1 @ 1.32 | ✗ | MS 1 @ 1.32 | ✗ |
| 15:45 | AL Ittihad K. - Sharjah | 0-3 (0-1) | KG Var @ 1.47 | ✗ | ÇŞ 1-X @ 1.45 | ✗ |
| 14:30 | Albirex Niigata (Sin) - Balestier | 3-2 (1-1) | MS 1 @ 1.33 | ✓ | KG Var @ 1.28 | ✓ |
| 14:30 | Swit Skolwin - S. Stalowa | 1-2 (1-1) | ÇŞ X-2 @ 1.24 | ✓ | 3.5 Alt @ 1.33 | ✓ |
| 14:35 | Beijing Guoan - Shanghai Port | 0-2 (0-1) | 3.5 Alt @ 1.28 | ✓ | 3.5 Alt @ 1.28 | ✓ |
| 15:00 | Zob Ahan - Shams Azar Qazvin | 3-0 (0-0) | ÇŞ 1-2 @ 1.20 | ✓ | ÇŞ 1-2 @ 1.20 | ✓ |
| 15:00 | Lokomotiv Taşkent - Pakhtakor Tashkent | 2-1 (0-1) | KG Var @ 1.34 | ✓ | KG Var @ 1.34 | ✓ |
