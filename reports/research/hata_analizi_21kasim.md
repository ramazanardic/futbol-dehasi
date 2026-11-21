# 21 Kasım 2026 hata analizi — bütün bahis aileleri, beraberlik ve yüksek oranlı pazarlar

Kapsam: 21 Kasım'da derin taranan 573 maçın, 21:00 (TSİ) itibarıyla **bitmiş 383 maçı**. Bu maçlarda eşiği geçen **2.907 seçim**
ve maç başına seçilen **382 ana tahmin** notlandı. Sonuçlar Nesine GetUnliveMatches (İY + MS) ve FotMob herkese açık JSON'dan
alındı; API-Football kullanılmadı. Her bulgu arşivle sınandı: `data/matches.csv`, 115.871 maç, 2011/12+, üretim fiyatlama
hattı + `market_calibration.json`. Test 2016/17+ (77,5 bin maç); walk-forward doğrulama 2011–2020 eğitim, 2021/22+ test.
Bir değişiklik yalnız **arşivde de doğrulanırsa** yapıldı. Tek günün sapmaları maç içi korelasyonlu: aynı maçtan 5–10 seçim
aynı skorla notlanır, yani gerçek örnek ≈ 383 maçtır ve z değerleri iyimserdir.

Betik: `scripts/hata_analizi_21kasim.py` (arşiv). Günlük satırlar özel klasörde tutulur; bu raporda yalnız toplamlar var.

## 1. Özet

| | n | Tutan | Beklenen P | Fark | Brier | Ortalama oran | Düz ROI (Nesine) |
|---|---|---|---|---|---|---|---|
| Bütün seçimler | 2.907 | %60,7 | %61,9 | −1,2 puan | 0,237 | 1,35 | **−18,7 %** |
| Ana tahminler | 382 | %63,6 | %67,0 | −3,4 puan | 0,230 | 1,26 | −20,5 % |

* Olasılıklar genelde doğru: bütün seçimlerde yalnız 1,2 puan iyimserlik var. **Para kaybının ana nedeni olasılık hatası değil,
  Nesine'nin bacak başına ≈ %22 payı.** Bu pay yüzünden tahminler P kadar tutsa bile düz ROI ≈ −%19 çıkıyor. Kombine kuponda
  pay katlanır: 5 bacakta ≈ %70.
* Ana tahminlerdeki −3,4 puan seçim yanlılığından geliyor (kazanan laneti). Her maçın en yüksek EV'li seçimi seçildiği için,
  modelin yukarı yanıldığı seçimler öne çıkıyor. PR #5'teki türetilmiş P büzmesi (0,10) bugün tam bu kadar düzeltiyor:
  %65'te −1,5 puan.
* Doğrudan keskin fiyatlı 501 seçim kusursuz kalibre: %61,9'a %61,8. Matristen türetilen 2.406 seçim −1,5 puan sapıyor.
  Bu sapma arşivdeki ligler için **tekrar etmiyor**: türetilmiş P orada ±1 puan içinde kalibre. Sapma, arşivin kapsamadığı
  "diğer" liglerde yoğun (−2,1 puan).

## 2. Hata kalıpları — bugün ve arşiv

| # | Kalıp (bugün) | Bugün | Arşiv (2016/17+, P .55–.90 bölgesi) | Karar |
|---|---|---|---|---|
| 1 | **Ev İY 0,5 Üst** | 68'de %44,1, beklenen %60,6 (z −2,8) | 14.695 seçim: %63,3, beklenen %62,1. Test 2021+: +2,6 puan (model hafif **düşük** tahmin ediyor) | **Gürültü.** Arşiv tersini söylüyor; çok küçük yukarı kayma δ +0,013 tutuldu |
| 2 | **2,5 Üst** | 124'te %49,2, beklenen %60,2 (z −2,5). Bütün gün: 300 maçta keskin P %54,7, gerçek %51,0 | 20.945 seçim: +0,2 puan | **Gürültü / gün etkisi.** Az gollü bir gün; bütün Üst seçimleri birlikte yattı |
| 3 | KG Var %58,1 (P %61,7) ve KG Yok %48,6 (P %61,1) | İki taraf da düşük | KG Var +0,1, KG Yok +0,3 puan | **Gürültü.** İki zıt taraf aynı anda kötü olamaz; sistematik değil |
| 4 | **Dep İY 0,5 Alt** | 110'da %55,5, beklenen %62,4 | 57.440 seçim: −0,6 puan, 11 sezonun 8'inde negatif. Test −0,84 puan | **Doğrulandı (küçük).** δ −0,024 |
| 5 | Çifte şans (ÇŞ X2 %54,3 / P %61,2) | Aile −2,0 puan | ÇŞ X2 +0,5, ÇŞ 1X +0,4 puan (hafif düşük tahmin); **ÇŞ 12 −0,6 puan** (11 sezonun 8'i) | ÇŞ 1X/X2 **gürültü**. ÇŞ 12 **doğrulandı**: beraberlik hafif düşük fiyatlı, δ −0,022 |
| 6 | Ev sahibi golleri ailesi | 424'te %58,0, beklenen %61,5 | Ev 1,5 Üst +0,8, Ev 0,5 Üst +0,1, Ev 1,5 Alt +0,4 puan | **Gürültü.** PR #5'in "zayıf aile" kuralı arşivce desteklenmiyor; banko'da temkin olarak bırakıldı |
| 7 | İlk Gol | 36'da %52,8, beklenen %61,3 | Arşivde sınanamıyor: ilk golü atan takım verisi yok | **Sınanamaz.** Arşivde sınanamayan türetilmiş pazarlara +0,05 ek büzme |
| 8 | "Geçmiş yetersiz" kararı (takım geçmişi yok) | 1.848'de %59,0, beklenen %61,6 (z −2,3). "⚠ desteklemiyor" ise %66,1 tuttu | Arşivde bu değişken yok | Geçmiş kararı bugün **bilgi taşımadı**. Etki "diğer" lig büzmesiyle zaten karşılanıyor; ek değişiklik yok |
| 9 | P %60–65 bandı | 1.038'de %59,9, beklenen %62,5 | Arşiv ligleri bu bantta kalibre | Türetilmiş + "diğer" lig büzmesiyle (PR #5) karşılanıyor |
| 10 | Erken saat (<15:00, Asya) | 39'da %48,7 | — | Örnek çok küçük, işlem yok |
| 11 | Aleyhte piyasa hareketi (steam) | 34'te %55,9 (P %60,5); lehte 55'te %65,5 | Arşivde açılış/kapanış çifti yok | Örnek küçük, sınanamaz. Bilgi notu |

Bütün aileler (bugün, bitmiş maçlar):

| Aile | n | Tutan | P | Fark |
|---|---|---|---|---|
| İlk gol | 36 | %52,8 | %61,3 | −8,5 |
| Karşılıklı gol | 228 | %56,6 | %61,6 | −5,0 |
| Ev sahibi golleri | 424 | %58,0 | %61,5 | −3,4 |
| İkinci yarı | 26 | %57,7 | %60,2 | −2,5 |
| Handikap | 167 | %58,7 | %61,0 | −2,3 |
| Deplasman golleri | 419 | %59,9 | %62,1 | −2,2 |
| Çifte şans | 224 | %60,3 | %62,3 | −2,0 |
| Alt/Üst | 328 | %60,4 | %61,5 | −1,1 |
| Kombine (A & B) | 108 | %59,3 | %59,8 | −0,5 |
| İlk yarı | 585 | %62,7 | %62,1 | +0,6 |
| Maç sonucu | 117 | %63,2 | %62,2 | +1,1 |
| Yarı özel | 136 | %67,7 | %63,4 | +4,2 |
| 2Y karşılıklı gol | 93 | %72,0 | %64,5 | +7,5 |

Kademe: büyük ligler +2,5 puan (n=275); ikinci/orta −1,5; "diğer" −2,1 (n=1.330); alt/genç/kadın −0,5.
Favori gücüne göre (keskin 1X2) fark −1,6 ile −0,2 arasında. Belirgin bir favori etkisi yok.

## 3. Beraberlik

**Bugün:** 383 maçın 90'ı beraberlik (%23,5). Keskin piyasanın ortalama beraberlik P'si %23,6'ydı, yani **piyasa beraberliği
doğru fiyatladı**. Kaybedilen 43 MS 1/MS 2 seçiminin 28'i beraberlikle yattı (%65). Seçimlerin P'lerinden beklenen pay %56
(≈ 24 maç). Fark ≈ 1,2 standart sapma, yani gürültü.

**Arşiv:** test 2016/17+, 77.503 maç. Ortalama büro oranları, marjsız power P.

* Genel olarak piyasa beraberliği **+0,6 puan düşük** fiyatlıyor (%26,2'ye %25,6; 11 sezonun 8'i). Fark düşük toplamlı ve
  dengeli maçlarda yoğunlaşıyor: P(2.5Ü) < .45 iken **+1,6 puan**, 11 sezonun 11'i.
* **Banko bandında (favori oranı 1,10–1,80) piyasa beraberliği doğru fiyatlıyor** (fark ±0,15 puan). Banko bandındaki favoriler
  (P .55–.80) testte P'lerinden **fazla** kazandı: %63,9'a %65,1. MS 1/MS 2 banko bacakları beraberliğe karşı sistematik olarak
  zayıf değil. Bugünkü beraberlik kayıpları bu yüzden gürültü.
* Matris: 0-0 %0,3 puan fazla, 1-1 %0,5 ve 2-2 %0,35 puan az tahmin ediliyor (11 sezonun 10–11'i). Bu bir rho sorunu değil:
  rho 0-0 ile 1-1'i birlikte şişirir, burada ise yönleri zıt. Bu skorlar `market_calibration.json`'daki skor Platt eğrileriyle
  zaten düzeltiliyor. Rho değiştirilmedi.
* Beraberlik düzeltmesi: logit P(0) + a + c·1[P(2.5Ü) < .45], a = −0,013, c = +0,099. 2021+ testte Brier 0,19028'den 0,19023'e
  indi, ama log-loss iyileşmesinin GA'sı 0'ı kesti: [−0,00032, +0,00011]. Bu yüzden **kalibrasyon olarak uygulanmadı, yalnız
  risk puanı olarak** kullanılıyor.
* **Değer (+EV) bölgesi yok.** En iyi bölgede (P(2.5Ü) < .45 ve piyasa beraberliği ≥ .28, 17.718 maç) ROI ortalama büro
  oranıyla −0,9 %, en iyi oranla +3,7 %. Nesine'nin MS payı ≈ %22, ortalama büroların ≈ %5–6'sının çok üstünde. Nesine
  oranıyla bu bölge de −%15 civarında.

**Favori oranı (ortalama büro)**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| 1.10-1.30 | 3.796 | %12.0 | %12.0 | +0.1 | %29.6 | %2.5 / %5.5 / %3.4 | 7.15 | -17.8 % | -9.4 % |
| 1.30-1.50 | 6.127 | %18.5 | %18.7 | -0.1 | %35.7 | %4.7 / %8.2 / %4.6 | 4.79 | -11.8 % | -5.9 % |
| 1.50-1.80 | 14.633 | %23.8 | %23.6 | +0.1 | %39.7 | %6.0 / %11.0 / %5.5 | 3.89 | -8.2 % | -3.1 % |
| 1.80-2.10 | 18.308 | %27.5 | %26.7 | +0.8 | %43.0 | %8.0 / %12.9 / %5.4 | 3.49 | -4.7 % | -0.2 % |
| 2.10+ (dengeli) | 34.639 | %29.4 | %28.6 | +0.8 | %43.7 | %8.7 / %14.0 / %5.5 | 3.28 | -4.1 % | +0.3 % |

**|P(ev) − P(dep)|**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| <.10 | 18.488 | %29.9 | %28.7 | +1.2 | %44.0 | %8.8 / %14.2 / %5.6 | 3.27 | -2.8 % | +1.7 % |
| .10-.20 | 17.121 | %28.5 | %28.1 | +0.4 | %42.9 | %8.3 / %13.6 / %5.5 | 3.33 | -5.7 % | -1.3 % |
| .20-.35 | 19.180 | %27.4 | %26.6 | +0.7 | %42.9 | %8.1 / %12.8 / %5.3 | 3.50 | -4.8 % | -0.3 % |
| .35-.50 | 11.980 | %23.8 | %23.7 | +0.1 | %40.0 | %6.1 / %10.9 / %5.4 | 3.88 | -8.4 % | -3.4 % |
| ≥.50 | 10.734 | %16.6 | %16.6 | -0.0 | %33.7 | %4.0 / %7.5 / %4.2 | 5.57 | -13.5 % | -6.7 % |

**Beraberlik oranı**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| <3.00 | 2.883 | %34.6 | %32.4 | +2.2 | %49.6 | %12.9 / %17.1 / %4.1 | 2.89 | -0.2 % | +5.8 % |
| 3.00-3.30 | 18.103 | %30.9 | %29.5 | +1.4 | %46.3 | %10.2 / %14.6 / %5.1 | 3.16 | -2.5 % | +2.4 % |
| 3.30-3.60 | 25.241 | %27.4 | %27.1 | +0.3 | %42.2 | %7.6 / %13.1 / %5.6 | 3.42 | -6.1 % | -1.8 % |
| 3.60-4.00 | 15.528 | %25.2 | %24.8 | +0.4 | %39.6 | %6.3 / %11.6 / %5.9 | 3.73 | -6.2 % | -1.7 % |
| 4.00+ | 15.748 | %18.2 | %18.3 | -0.1 | %34.9 | %4.1 / %8.3 / %4.6 | 5.14 | -12.1 % | -6.1 % |

**Marjsız P(2.5 Üst) — toplam gol beklentisi**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| <.40 | 8.935 | %32.4 | %30.4 | +1.9 | %48.8 | %11.9 / %15.5 / %4.3 | 3.08 | -0.7 % | +3.9 % |
| .40-.45 | 14.169 | %29.8 | %28.4 | +1.4 | %45.1 | %9.8 / %14.2 / %5.0 | 3.29 | -2.5 % | +1.8 % |
| .45-.50 | 17.122 | %26.8 | %26.9 | -0.1 | %42.8 | %7.8 / %12.4 / %5.4 | 3.47 | -7.4 % | -3.2 % |
| .50-.55 | 16.142 | %25.6 | %25.2 | +0.3 | %40.2 | %6.5 / %12.2 / %5.5 | 3.69 | -6.9 % | -2.1 % |
| .55-.60 | 11.040 | %23.3 | %23.2 | +0.1 | %38.2 | %5.1 / %10.8 / %6.0 | 4.01 | -8.9 % | -3.6 % |
| ≥.60 | 10.095 | %18.5 | %18.2 | +0.3 | %33.1 | %3.5 / %8.4 / %5.1 | 5.32 | -10.7 % | -4.2 % |

**Lig kademesi**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| üst lig | 40.862 | %25.0 | %24.5 | +0.5 | %40.6 | %6.8 / %11.8 / %5.2 | 4.01 | -6.2 % | -1.2 % |
| alt/ikinci lig | 36.641 | %27.5 | %26.9 | +0.6 | %42.4 | %8.1 / %12.9 / %5.3 | 3.47 | -6.3 % | -1.6 % |

**Ligin önceki 3 sezon beraberlik oranı**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| <%24 | 15.989 | %24.6 | %23.7 | +0.9 | %39.5 | %6.2 / %11.4 / %5.6 | 4.12 | -5.8 % | -0.3 % |
| %24-26 | 24.624 | %25.2 | %24.6 | +0.5 | %40.2 | %6.6 / %12.1 / %5.3 | 3.89 | -6.1 % | -1.4 % |
| %26-28 | 19.758 | %26.1 | %26.2 | -0.1 | %42.1 | %7.7 / %12.1 / %5.3 | 3.63 | -8.5 % | -4.0 % |
| ≥%28 | 16.896 | %29.1 | %28.1 | +1.0 | %44.4 | %9.3 / %13.8 / %5.0 | 3.35 | -4.6 % | +0.2 % |

**Sezon evresi**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| sezon başı (Tem-Eki) | 24.813 | %26.3 | %25.7 | +0.5 | %41.0 | %7.3 / %12.1 / %5.7 | 3.72 | -6.1 % | -1.3 % |
| sezon ortası (Kas-Şub) | 31.302 | %26.4 | %25.6 | +0.8 | %41.7 | %7.5 / %12.7 / %5.1 | 3.75 | -5.4 % | -0.5 % |
| sezon sonu (Mar-Haz) | 21.388 | %25.6 | %25.4 | +0.2 | %41.6 | %7.4 / %12.0 / %5.1 | 3.79 | -7.7 % | -2.9 % |

**Birleşik bölge**

| Kova | Maç | Gerçek beraberlik | Piyasa P | Fark (puan) | İY beraberlik | 0-0 / 1-1 / 2-2 | Ort. oran | ROI ort. oran | ROI en iyi oran |
|---|---|---|---|---|---|---|---|---|---|
| 2.5Ü<.45 & piyasa beraberlik ≥.28 | 17.718 | %31.9 | %30.1 | +1.8 | %47.4 | %11.1 / %15.3 / %4.8 | 3.12 | -0.9 % | +3.7 % |
| diğer | 59.785 | %24.5 | %24.3 | +0.2 | %39.7 | %6.3 / %11.4 / %5.4 | 3.94 | -7.9 % | -2.9 % |


**Bugünün 7 beraberlik seçimi.** Sharp/Nesine oranları 21 Kas 11:47 anlık görüntüsünden. İkisi tuttu; P toplamı 2,18 olduğu için
beklenen ≈ 2,2. Yeni süzgeç yedisinin de hiçbirini geçirmezdi:

| Maç | Nesine oranı | P(0) | P(2.5Ü) | Skor | Sonuç | Kova / süzgeç |
|---|---|---|---|---|---|---|
| Charleroi – St. Truidense | 3,31 | %24,9 | %62,5 | 2-2 | ✓ | Yüksek toplam, dengeli. Bölge dışı, EV −%18 |
| Bolton – Portsmouth | 3,10 | %27,9 | %51,7 | 1-1 | ✓ | Dengeli, orta toplam. Bölge dışı, EV −%14 |
| Fleury 91 – Rouen | 2,75 | %32,1 | %50,5 | 1-0 | ✗ | Dengeli, orta toplam. EV −%13 |
| Carrarese – V. Entella | 2,79 | %31,2 | %43,2 | 1-0 | ✗ | **Bölge içinde** (düşük toplam), risk %33,1. EV −%8 |
| Hibernian – Dundee Utd | 3,57 | %24,5 | %60,4 | 0-4 | ✗ | Yüksek toplam. Bölge dışı |
| Sampdoria – Benevento | 2,91 | %30,3 | %45,9 | 3-1 | ✗ | Sınırda (.459). EV −%12 |
| Al Julan – Al Naft | 1,92 | %45,1 (model) | — | 2-3 | ✗ | Keskin fiyat yok. Süzgeç reddeder |

**Beraberlik riski (seçicilerde kullanılıyor):** risk = logit P(0) + a + c·1[düşük toplam].
* Banko: MS 1/MS 2 bacağında risk ≥ %27 ise ret, ≥ %24 ise "ÇŞ / Hnd(+1) daha güvenli" uyarısı. MS P'si riskteki fazlalık
  kadar düşürülür.
* Risk modu: MS 0 seçimi yalnız düşük toplam bölgesinde, piyasa P(0) ≥ .28 ve risk P'siyle EV ≥ %3 ise geçer.
* Ayarlar: `BANKO_DRAW_RISK_MAX`, `BANKO_DRAW_RISK_WARN`, `DRAW_ZONE_MAX_OVER25`, `DRAW_PICK_MIN_P`, `DRAW_PICK_MIN_EV`.

## 4. Yüksek oranlı pazarlar (İY/MS, İY/2Y sonucu, iki yarıda KG, skor)

Arşiv test 2016/17+, 77.503 maç. Üretim P'si, uygulanan yerlerde Platt'lı. "Ek kalibrasyon" şöyle bir modeldi:
logit p' = a + b·logit p + c·(P_ev − P_dep) + d·(P(2.5Ü) − .5), eğitim ≤2020 ve test 2021+ ile walk-forward.
Nesine ROI tahmini, Nesine ödeme oranından hesaplandı. Ödeme oranı = oran × marjsız P; 21 Kas bülteninde İY/MS için ≈ 0,75,
İY/2Y sonucu için ≈ 0,82, iki yarıda KG için ≈ 0,85.

| Çıktı | P (ort.) | Gerçek | Fark (puan) | Brier | Log-loss | Güvenilirlik: en düşük / en yüksek P kovası (P→gerçek) | Ek kalibrasyon (2021+ test) | En sık görüldüğü profil | En iyi gerçek/P profili → Nesine ROI tahmini |
|---|---|---|---|---|---|---|---|---|---|
| İY/MS 1/1 | %26.3 | %26.0 | -0.32 | 0.1784 | 0.5367 | %11.8→%12.2 / %44.5→%44.1 | reddedildi (ΔLL +0.000098) | ev güçlü fav, yüksek toplam (≥.55): %47.0 | dep güçlü fav, düşük toplam (2.5Ü<.45) (n=513): 1.22 → -12 % |
| İY/MS 1/0 | %5.3 | %5.3 | +0.05 | 0.0506 | 0.2081 | %4.0→%4.1 / %6.1→%6.1 | reddedildi (ΔLL +0.000096) | dengeli, yüksek toplam (≥.55): %6.3 | dep güçlü fav, düşük toplam (2.5Ü<.45) (n=513): 1.21 → -11 % |
| İY/MS 1/2 | %2.1 | %2.2 | +0.11 | 0.0215 | 0.1040 | %1.0→%1.0 / %3.3→%3.5 | reddedildi (ΔLL -0.000011) | dep hafif fav, yüksek toplam (≥.55): %4.3 | dep hafif fav, yüksek toplam (≥.55) (n=2075): 1.20 → -10 % |
| İY/MS 0/1 | %14.9 | %14.9 | -0.04 | 0.1247 | 0.4121 | %8.6→%8.1 / %20.1→%20.5 | reddedildi (ΔLL +0.000176) | ev güçlü fav, orta (.45–.55): %20.1 | dep hafif fav, yüksek toplam (≥.55) (n=2075): 1.04 → -21 % |
| İY/MS 0/0 | %16.0 | %15.7 | -0.32 | 0.1307 | 0.4283 | %10.8→%10.0 / %20.3→%21.2 | reddedildi (ΔLL -0.000082) | dengeli, düşük toplam (2.5Ü<.45): %21.2 | dep güçlü fav, düşük toplam (2.5Ü<.45) (n=513): 1.12 → -16 % |
| İY/MS 0/2 | %11.0 | %10.9 | -0.11 | 0.0950 | 0.3332 | %4.9→%4.8 / %17.6→%17.4 | reddedildi (ΔLL +0.000074) | dep güçlü fav, yüksek toplam (≥.55): %19.8 | ev güçlü fav, düşük toplam (2.5Ü<.45) (n=3467): 1.11 → -17 % |
| İY/MS 2/1 | %2.6 | %2.6 | +0.08 | 0.0257 | 0.1211 | %1.6→%1.7 / %3.5→%3.5 | reddedildi (ΔLL +0.000012) | ev güçlü fav, yüksek toplam (≥.55): %3.7 | ev güçlü fav, düşük toplam (2.5Ü<.45) (n=3467): 1.19 → -10 % |
| İY/MS 2/0 | %5.1 | %5.1 | +0.07 | 0.0487 | 0.2017 | %3.7→%3.8 / %5.9→%6.2 | reddedildi (ΔLL +0.000119) | dengeli, yüksek toplam (≥.55): %6.4 | dengeli, orta (.45–.55) (n=8156): 1.11 → -17 % |
| İY/MS 2/2 | %17.2 | %17.2 | +0.02 | 0.1330 | 0.4270 | %6.3→%6.4 / %32.4→%32.8 | reddedildi (ΔLL +0.000149) | dep güçlü fav, yüksek toplam (≥.55): %43.5 | ev güçlü fav, orta (.45–.55) (n=8356): 1.08 → -18 % |
| İY 1 | %33.3 | %33.5 | +0.23 | 0.2112 | 0.6115 | %19.6→%20.4 / %49.6→%50.0 | reddedildi (ΔLL +0.000142) | ev güçlü fav, yüksek toplam (≥.55): %52.8 | dep güçlü fav, düşük toplam (2.5Ü<.45) (n=513): 1.24 → -2 % |
| İY 0 | %41.7 | %41.4 | -0.28 | 0.2403 | 0.6734 | %34.4→%34.1 / %47.6→%47.8 | reddedildi (ΔLL +0.000150) | dengeli, düşük toplam (2.5Ü<.45): %47.2 | ev hafif fav, orta (.45–.55) (n=9800): 1.00 → -18 % |
| İY 2 | %24.5 | %25.0 | +0.53 | 0.1784 | 0.5384 | %12.9→%13.9 / %39.0→%39.8 | reddedildi (ΔLL -0.000056) | dep güçlü fav, yüksek toplam (≥.55): %49.6 | ev güçlü fav, orta (.45–.55) (n=8356): 1.10 → -10 % |
| 2Y 1 | %36.1 | %36.9 | +0.79 | 0.2183 | 0.6264 | %21.0→%21.3 / %53.7→%55.0 | reddedildi (ΔLL -0.000135) | ev güçlü fav, yüksek toplam (≥.55): %57.6 | dep güçlü fav, yüksek toplam (≥.55) (n=3576): 1.06 → -12 % |
| 2Y 0 | %35.3 | %35.3 | +0.00 | 0.2264 | 0.6449 | %28.5→%28.4 / %40.5→%41.0 | reddedildi (ΔLL -0.000018) | dengeli, düşük toplam (2.5Ü<.45): %41.6 | dep hafif fav, düşük toplam (2.5Ü<.45) (n=2529): 1.05 → -14 % |
| 2Y 2 | %27.2 | %27.8 | +0.68 | 0.1897 | 0.5636 | %14.1→%15.0 / %43.2→%44.0 | reddedildi (ΔLL -0.000064) | dep güçlü fav, yüksek toplam (≥.55): %54.3 | ev güçlü fav, düşük toplam (2.5Ü<.45) (n=3467): 1.11 → -8 % |
| İki Yarıda KG Var | %5.1 | %5.1 | -0.03 | 0.0477 | 0.1980 | %3.0→%3.3 / %7.7→%7.2 | reddedildi (ΔLL -0.000122) | dengeli, yüksek toplam (≥.55): %7.8 | dep güçlü fav, düşük toplam (2.5Ü<.45) (n=513): 1.61 → +39 % |
| Skor 2-1 | %8.6 | %8.8 | +0.28 | 0.0802 | 0.2963 | %5.7→%5.9 / %10.3→%10.8 | reddedildi (ΔLL -0.000048) | ev güçlü fav, orta (.45–.55): %10.9 | dep güçlü fav, orta (.45–.55) (n=2429): 1.16 → -30 % |
| Skor 1-2 | %6.9 | %7.0 | +0.05 | 0.0645 | 0.2487 | %3.6→%3.7 / %9.8→%10.4 | reddedildi (ΔLL -0.000069) | dep güçlü fav, yüksek toplam (≥.55): %11.6 | dep güçlü fav, yüksek toplam (≥.55) (n=3576): 1.14 → -31 % |
| Skor 3-1 | %4.2 | %4.0 | -0.18 | 0.0386 | 0.1655 | %1.9→%1.7 / %6.9→%6.8 | tutuldu (ΔLL -0.000112) | ev güçlü fav, yüksek toplam (≥.55): %7.4 | dep güçlü fav, orta (.45–.55) (n=2429): 1.19 → -28 % |
| Skor 1-3 | %2.9 | %2.7 | -0.13 | 0.0262 | 0.1200 | %0.9→%0.8 / %5.5→%5.2 | reddedildi (ΔLL -0.000018) | dep güçlü fav, yüksek toplam (≥.55): %6.5 | ev hafif fav, yüksek toplam (≥.55) (n=3073): 1.15 → -31 % |
| Skor 2-2 | %5.3 | %5.3 | -0.01 | 0.0500 | 0.2060 | %4.0→%4.0 / %6.4→%6.6 | reddedildi (ΔLL +0.000092) | dengeli, yüksek toplam (≥.55): %7.5 | dengeli, yüksek toplam (≥.55) (n=2600): 1.11 → -33 % |

* **Model bu pazarlarda kalibre.** İY/MS'in 9 çıktısında da fark ≤ ±0,3 puan. Geri dönüşler: ilk yarıyı önde kapatan ev
  sahibinin maçı kaybetmesi modelde %6,3, gerçekte %6,6; deplasman için %10,5'e %10,6. Ligler arasında İY gol payı
  %42,8–45,7 arasında ve İY 0,5 Üst lig farkları ±2 puan içinde.
* Bu yüzden **İY/MS modeli yeniden yazılmadı**: lig bazlı İY payı, ayrı İY rho'su ve duruma bağlı 2. yarı yoğunluğu
  eklenmedi. Arşiv düzeltilecek bir yanlılık göstermiyor ve ekleme aşırı uyum riski taşır. Ek kalibrasyon 21 çıktıdan
  yalnız **Skor 3-1**'de GA'yı geçti; o da dosyaya yazıldı, ama üretimdeki skor eğrileri zaten var.
* En iyi gerçek/P oranları (1,1–1,2) çoğunlukla "dep güçlü favori + düşük toplam" kovasında (n=513, nadir profil). 315
  kova × çıktı içinde rastlantı beklenir. Tek pozitif ROI'li kova (iki yarıda KG, +%39, ≈ 16 isabet) çoklu karşılaştırma
  gürültüsü sayıldı. **Nesine marjıyla (İY/MS ödeme ≈ 0,75) hiçbir kovada güvenilir değer yok.**
* Yeni **`yuksek_oran` modu** (`kupon_modu.policy("yuksek_oran")`, `market_reliability.high_odds_pick_ok`):
  * Keskin fiyat varsa model ile keskin P'nin göreli farkı ≤ %15 olmalı, EV ikisinin küçüğüyle hesaplanır.
  * Keskin fiyat yoksa pazar arşivde sınanmış olmalı ve P × 0,90 alınır.
  * EV ≥ max(%6, aile tabanı), oran ≤ 15, kupon en çok 2 maç.

## 5. Yapılan değişiklikler

1. **`data/calibration/market_tail_calibration.json`.** Banko bölgesinde (P .55–.90) 70 seçim/karşı taraf walk-forward
   sınandı. Yalnız 2021+ test log-loss farkının %95 GA'sı < 0 olan **5'i** tutuldu: ÇŞ 12, İY ÇŞ 1X, Dep İY 0,5 Alt,
   DEĞİL(Ev Her İki Yarıyı Kazanır) aşağı, Ev İY 0,5 Üst yukarı. Hepsi ≤ 1 puanlık düzeltme. Dosyada ayrıca 70 seçimin
   güvenilirlik tablosu, beraberlik düzeltmesi, ligin son 4 sezon beraberlik oranı ve İY/MS ek kalibrasyonu var.
2. **`markets/market_reliability.py`:** `tail_adjust`, `is_archive_tested`, `draw_risk`, `ms_prob_after_draw_risk`,
   `draw_pick_ok`, `high_odds_pick_ok`, `select_high_odds`.
3. **`strategy/banko_guard.py`:** `effective_prob` önce kuyruk düzeltmesini ve MS beraberlik riskini, sonra büzmeleri uygular.
   Arşivde sınanmamış türetilmiş pazara `UNTESTED_MARKET_SHRINK` (0,05) eklenir. `check_leg` beraberlik riskini, risk modu MS 0
   süzgecini ve yüksek oran süzgecini çalıştırır.
4. **`strategy/kupon_modu.py`:** `yuksek_oran` modu eklendi. `to_leg` artık ad, P(0), P(2.5Ü), p_model ve p_sharp taşır.
   Havuz süzgeci yeni ret nedenlerini tanır.
5. **`scripts/nesine_kupon.py`:** bacaklara maçın P(0) ve P(2.5Ü) değerleri eklendi.
6. **`settings.py`:** bütün eşikler burada ayarlanabilir; kuyruk düzeltmesi `TAIL_CALIBRATION_ON` ile kapatılabilir.
7. PR #5 kuralları (türetilmiş büzme 0,10, "diğer" lig büzmesi, zayıf aileler) **değiştirilmedi**. Arşiv "zayıf aile"
   kuralını desteklemiyor, ama banko modunda temkin pahalı değil. Birkaç günlük sonuç birikince yeniden bakılmalı.

## 6. Beklenen etki (dürüst)

* Arşiv 2021+ test (held-out): tutulan 5 kuyruk düzeltmesinin her biri seçim başına log-loss'u 0,00006–0,00032 azaltıyor.
  Örnek Brier: Ev İY 0,5 Üst 0,22525 → 0,22510; Dep İY 0,5 Alt 0,22949 → 0,22943. Beraberlik risk puanı Brier'i
  0,19028 → 0,19023 yapıyor. Bunlar **küçük** iyileşmeler, çünkü hat zaten kalibre.
* Bugünkü 2.907 seçimde (PR #5 büzmesine göre) Brier 0,23688 → 0,23689 ve log-loss 0,66651 → 0,66653: değişmedi. 397 seçimin
  P'si değişti. Bugünkü hataların büyük kısmı arşivde tekrar etmeyen gün gürültüsü; onları "düzeltmek" aşırı uyum olurdu.
* Asıl kazanç süzgeçlerde: banko'da düşük toplamlı maçta MS bacağı reddediliyor ya da uyarılıyor, Nesine'de −EV beraberlik
  seçimleri risk modunda engelleniyor (bugünkü 7'nin 7'si), yüksek oranlı pazarlarda modelle keskin fiyat uyuşmadan seçim
  yapılmıyor.
* **Değişmeyen gerçek:** Nesine payı bacak başı ≈ %22, İY/MS'te ≈ %25–29. Kalibre P'lerle bile düz ROI ≈ −%19. Uzun vadede
  kazanmanın tek yolu payı aşan, keskin fiyatla doğrulanmış değer. Banko kuponlar ise kaybı küçültür, kazanç garanti etmez.
