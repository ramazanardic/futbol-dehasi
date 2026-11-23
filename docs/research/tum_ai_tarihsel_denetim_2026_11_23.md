# Futbol Dehası | Beş yapay zekânın tarihsel denetimi
**Tarih:** 23 Kasım 2026

## Yöntem ve sınırlar
- Tahminlerin dosya içindeki TUTTU/YATTI etiketleri gerçek sonuç yerine kullanılmadı. Nesine esaslı ortak arşivdeki 90 dakika skorları ile bağımsız pazar çözümü uygulandı. Bu, sonuç kaynağını başka bir yayıncıdan tamamen bağımsız doğruladığımız anlamına gelmez.
- 22 Kasım ortak sonuçları 22.57 TSİ itibarıyla ara karnedir. Başlamamış/belirsiz/puanlanamayan maçlar otomatik kayıp sayılmaz.
- Beş AI'nin erişilebilir standart CSV'leri, alternatif kupon JSON taslakları, üç büyük fiyatlama JSON'u, eski ortak karneler ve gerçekten oynandığı bildirilen ekran aktarımı bahis defterleri tarandı.
- GitHub'da **1.900 ham ana tahmin satırı**, **66.985 fiyatlanan pazar seçimi** ve bunlardan **57.962 sonuçlandırılabilen pazar seçimi** saptandı. Pazar seçimleri farklı maçlar değildir ve birbirleriyle yüksek oranda korelasyonludur.
- Claude ham AI CSV'leri GitHub'da yok; ortak değerlendirme sayıları *ikincil* olarak tutuluyor.
- Bilgisayardaki henüz GitHub'a gönderilmemiş kayıtlar cihaz çevrimdışı olduğundan kapsam dışında.

## Puanlanan ana tercihler (sabit 1 birim varsayımsal ROI)
| AI | Tarihler | Tutan / sonuçlanan | İsabet | ROI |
|---|---|---:|---:|---:|
| ChatGPT | 21 Kasım | 254/412 | %61,7 | −%16,3 |
| Gemini | 20–21 Kasım, güvenle eşleşen | 45/88 | %51,1 | −%33,6 |
| Antigravity | 22 Kasım, ara | 131/198 | %66,2 | −%17,4 |
| Grok | 22 Kasım, ara | 136/189 | %72,0 | −%10,7 |

**İkincil Claude ortak karne:** 20 Kasım 66/93 (−%4,4 ROI); 21 Kasım 300/442 (−%16,1). Ham CSV'den bu raporda yeniden puanlanmadı. Tüm bu kümeler farklı günlerde/farklı maçlarda oynanmış ve tarih/tahmin üretim zaman damgası tam doğrulanmamıştır. Bu tablo nihai AI sıralaması değildir.

Ana seçim yapılmayanlar dahil kayıtlı 1X2 tahminlerin ilk bağımsız puanlaması: Antigravity n=395 Brier=0,5583; ChatGPT n=613 Brier=0,5842; Gemini n=75 Brier=0,6675; Grok n=606 Brier=0,5749. Brier düşük daha iyidir; farklı maç dağılımları doğrudan karşılaştırmayı bozar.

## Kazanan ve kaybeden tercihlerde bulduğumuz sorunlar
1. **Hatalı sonucun başarı olarak yazılması:** Gemini 21 Kasım CSV'sinde Nesine esaslı ortak arşivle eşleşen 13 maçın 11'inde yazılı skor farklı; 6 TUTTU/YATTI etiketi de bağımsız çözümle çelişiyor. Gemini kendi değerlendirme sütunu doğrudan başarı kriteri sayılamaz.
2. **Sessiz veri kaybı:** Gemini'nin sentetik MBS maç kodları ve farklı sütun yapısı ortak değerlendirmeden kayboluyordu. Grok'un 21 Kasım CSV'sinde 188 maçta 1X2 olasılıkları olmasına rağmen ana seçim boş; bunlar 0 doğru ana seçim sayılmaz, fakat Brier/log-loss ile değerlendirilir. Claude ham CSV eksik.
3. **Yayım zamanı ve geleceğe bakma riski:** ChatGPT 21 Kasım CSV'sindeki 629 maçtan 556'sının maç başlama saati ilk Git yüklemesinden önce; Gemini 20 Kasım 103/103 ve 21 Kasım 47/47; Antigravity 22 Kasım 83/455. Git yayımlanma saati maç öncesi tahmin kanıtı değildir, ancak bunun yokluğu otomatik manipülasyon da değildir.
4. **Kazanan ama negatif beklenen değer:** Ham P ve kaydedilen Nesine oranı negatif EV (P×oran−1 negatif) gösterirken tek maç kazanabilir. Bir galibiyet model lehine kanıt değildir; bağımsız denetim bu durumları ayrıca sayar.
5. **Kaybeden ama pozitif beklenen değer:** Pozitif EV iddiasına sahip bir bahis tek maçta yatabilir. Bu nedenle sonucu değil olasılık kalibrasyonunu, fiyat avantajını, CLV'yi ve zaman içinde gerçekleşen ROI'yi takip etmek gerekir.
6. **Her pazar ailesinin oynanmış bahis sayılması:** Antigravity 22 Kasım kombine fiyat seçimlerinde (7.014 sonuçlanan seçim) varsayımsal tüm-seçimler ROI yaklaşık −%32,3; Grok 22 Kasım aynı ailede (5.621 seçim) −%30,9. Bir maçın iç içe geçen onlarca pazarı bağımsız 13 bin yatırım değildir; fiyatlama stres testidir.
7. **Çifte olasılık kırpması ve çelişen kupon üst olasılığı:** Aday P önce geçmiş/piyasa kalibrasyonundan, sonra kural ve guard kontrollerinden geçiyor. Önceden üst başlıkta son güvenlik hesabından farklı bir tutma olasılığı gösterilebiliyordu. Bu PR son guard P'sini yayımlayıp tüm aşamaları ayrı kaydediyor; türetilmiş bahislerin kalibrasyonunu kanıt olmadan sıfırlamıyor.
8. **Aynı maçın çoklu kuponlara yayılması:** Antigravity 22 Kasım'ın 33 standart kuponunda 75 maç birden fazla kuponda. Maçlar farklı kuponlarda tekrar edildiğinde portföy kayıpları korelasyonlu olur.

## Kuponlar ve fiilî bahis defteri — farklı kanıt türleri
**Standart tahmin kuponları:** ChatGPT 21 Kasım 6 kuponun 6'sı sonuçlanabildi, 1'i tuttu. Gemini 20 Kasım 9 kupondan yalnız 3'ü tam sonuçlandırıldı, 0 isabet; Gemini 21 Kasım 2 kuponu mevcut kaynaklarla tam sonuçlandırılamıyor, 0 olarak sınıflandırmak hatalı. Antigravity 22 Kasım 33 kupondan 8'i ara sonuçlarda tam değerlendirildi, 0 tuttu. Grok standart CSV'si boş ama alternatif JSON'larda kupon taslakları var.

**JSON taslakları:** Grok 21 Kasım hazırlık amaçlı banko JSON'unda 4 taslaktan 4'ü o tarih arşivinde puanlanabilir ve 3'ü doğru çıkmış görünüyor; 7 banko taslağında 4/4 puanlanıp hiçbiri tam tutmadı. Antigravity 22 Kasım 30 maçlık maksimum oran dosyasında 30 taslak, ancak ara karnede yalnız 8'i kesinleşmiş, 0'ı tutmuş. Bunlar gerçek oynanmış bahis değildir; diğer CSV kuponlarıyla çakışma olabilir.

**Gerçek oynandığı belirtilen kayıtlar:**
- 18 Kasım: ekran kaynaklı CSV'de 17 kupon kimliği / 75 bacak satırı. Tutarlar kısmen var ancak ödeme alanı yok; hiçbir kuponun fiilî net kârını bu CSV'den doğrudan güvenle hesaplayamayız.
- 19 Kasım: 13 kupon kimliği / 71 bacak. P02 ve P06 5 bacaklı kazançlı kuponlar olarak aktarılmış. P04 tutar eksik; P05 bacaklar eksik; P07 bekleyen statüde ve 0 TL geçici ödeme gerçek kayıp değildir. Kazanç/zarar yalnız tüm bacak ve ödeme bilgisi mevcut **sonuçlanmış** kuponlarla sınırlı raporlanmalı. Ödeme her bacakta tekrarlandığından **kupon başına bir kere** toplanmalıdır.

Ekranlardan yazıya aktarılan bahis kaydı Nesine hesabı/banka tarafından bağımsız doğrulanmış işlem değildir. Piyasa bültendeki fiyatlama, önerilen kupon ve oynanmış kupon birbirinden ayrı veri tipleridir.

## Bu PR'de uygulanan düzeltmeler
- **scripts/ai_history_audit.py**: tüm 5 AI tarihli CSV ve alternatif JSON kupon taslaklarını, 66.985 fiyatlanan pazar seçimini, tam 1X2 olasılık vektörlerini, kazanan negatif EV/kaybeden pozitif EV işaretlerini, maç sonuç eşleşmesini, skor çelişkilerini ve ekran bazlı oynanmış kuponları okuyarak MD/JSON raporu üretir; tahminleri değiştirmez.
- **scripts/gun_degerlendirme.py**: uyumsuz CSV/kimlik ve bozuk 1X2 olasılık vektörünü görünür kılar, eksik ana seçimleri raporlar; hata nedeniyle sessizce eksilen maçları ölçer.
- **scripts/nesine_kupon.py**: son guard'ın kabul ettiği tutma olasılığını kuponun asıl P'si/EV'si olarak gösterir. Önceki P ve kural aşamalarını loglar, güven alt sınırını en fazla nihai P yapar.
- **CI / testler**: GitHub Actions tüm pytest testlerini, bağımsız tarihsel denetimi ve indirilebilir MD/JSON kanıt dosyasını her PR için üretir. Tahmin kayıtları, kasalar ve gerçek bahisler değişmez.

## Yasaklanan yöntem hataları ve ileri kontroller
- Kazanan maçlara bakarak zorla 2–3 maç / sabit play-off −0,35 xG / ev golü 2,00 / KG 1,15 gibi yeni parametreleri kanıtsız canlı sisteme yerleştirme. Bunlar ayrı hipotezdir; geçmiş maça uydurmadan walk-forward ve yeni günlerde test edilmelidir.
- Maç öncesi olasılık, oran, Nesine maç kodu, piyasa, referans borsa, fiyat zamanı ve model commit SHA'sının ayrı anlık kaydı olmadan “kesin maç öncesi tahmin başarısı” ilan etme.
- Tamamlanmamış kuponu kayıp sayma; aynı birden çok pazar seçimini bağımsız maç sayma; ekran aktarımı fişini kesin banka hareketi kabul etme.

**Uyarı:** Bu sürüm veri güvenilirliğini ve raporlanan kupon olasılığının doğruluğunu artırır. Yeni bir gerçek bahis kârlılığı gösterilmemiştir; sonucu bilinmeyen kayıtların kesin karneye alınması doğru değildir.
