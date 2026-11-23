# QuantFoot veri ve model geliştirme planı

23 Kasım 2026 · İncelenen sürüm `e0a9f43`

## Başlangıç noktası

İlk hedef, **maç öncesinde elde edilebilen yeni verinin 1-X-2 tahminine piyasa referansının üzerinde katkı sağlayıp sağlamadığını ölçmek**. Tek yarışma ve tek tahmin anıyla başlayıp sonuç alınırsa liglere ve pazar ailelerine genişleyeceğiz. Bu araştırma mevcut v4 hattını, ortak kota ve klasör kurallarını kullanır. [Ortak sistem](../docs/ORTAK_SISTEM.md)

Depoda maç arşivi, marjdan arındırılmış oranlar, Dixon–Coles, Elo, LightGBM, zaman sıralı geriye dönük test ve kasa koruma planlayıcısı zaten var. Maç araştırması modülleri form, kadro, dinlenme, ikili geçmiş, hakem ve hava bilgilerini kaynak kapsaması elverdiğinde topluyor. İlk geliştirme, bu bilgilerin maçtan önce ne zaman kullanılabilir olduğunu kaydetmek ve aynı maç üzerinde karşılaştırılabilir özelliklere dönüştürmek. [Maç dosyası](../src/quantfoot/data/match_dossier.py) · [Model topluluğu](../src/quantfoot/models/ensemble.py) · [Geriye dönük test](../src/quantfoot/evaluation/backtest.py)

## Yerel ön ölçüm

`data/matches.csv` 38 ligde **240.240** satır içeriyor. 1 Temmuz 2021 sonrası 55.655 satırda çift taraflı son beş maç formu alanlarının doluluk oranı **%97,39**, şut ve korner alanlarının **%67,18**, sarı kart alanlarının **%71,39**. 1-X-2 oran sütunlarının doluluğu **%99,91**, 2,5 Alt/Üst oranlarının **%71,38**. Bunlar sütun doluluğu ölçümleri. Oranın geçerliliği ve hangi anda erişilebilir olduğu ayrı doğrulanır.

Yerel walk-forward önbelleğinden dört tam sezonu karşılaştırdım. Aynı **12.894 maç**, dokuz lig, 30 Temmuz 2022–24 Mayıs 2026. 2021/22'deki 3.317 kayıt ilk karışım ağırlığının seçiminde kullanıldı. 2026/27'nin 212 erken kaydı karşılaştırma dışında tutuldu. Sınıf sırası 1, X, 2 ve önbellek etiketleri maç skorlarıyla kontrol edildi.

| Model | Log-loss ↓ | Brier ↓ | Doğruluk ↑ | Makro kesinlik ↑ | Makro duyarlılık ↑ | Makro F1 ↑ | ROC-AUC OvR ↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Marjsız Bet365 | **0,97003** | **0,57731** | **%53,45** | **%50,18** | **%46,09** | **0,39759** | **0,67513** |
| Kalibre model topluluğu | 0,98061 | 0,58449 | %52,46 | %34,60 | %45,19 | 0,38884 | 0,66344 |
| LightGBM | 0,98338 | 0,58602 | %52,18 | %45,24 | %44,90 | 0,38969 | 0,66036 |
| Elo + lojistik regresyon | 0,98578 | 0,58775 | %52,24 | %34,43 | %45,02 | 0,38736 | 0,65879 |
| Gol temelli Dixon–Coles | 0,99245 | 0,59185 | %51,66 | %44,32 | %44,74 | 0,38742 | 0,65424 |

Brier, maç başına üç sınıfın kare hataları toplamının ortalaması. Sınıf metrikleri en yüksek olasılıklı sonuç üzerinden hesaplandı. Karışım ağırlığını her sezondan önce yalnız geçmiş sezonlarda 0–1 aralığında 0,01 adımla log-loss'a göre seçtim. Dört modelin de dört sezondaki ağırlığı **0,00** çıktı. Ölçüm önbellekteki tahminleri karşılaştırır. Aynı arşiv oranının maçtan tam kaç dakika önce sunulduğu ve o anda Nesine'de hangi oranın alınabildiği bu ölçümden belirlenemez.

Önbellekteki `comp_epistemic_std` model belirsizliği ölçüsüdür ve satır toplamı 1 değildir. Eski deney betiği tüm `comp_*` dizilerini model olarak tarıyor. Bu ön ölçümde dört isimli olasılık dizisini ayrı seçip normalizasyonlarını doğruladım. Sonraki deneyden önce bu ayrımı betikte de uygulamak gerekiyor. [Deney betiği](../scripts/research_experiments.py) · [Önceki deneyler](../docs/research/experiments_2026_11.md)

## Veri kaynakları ve işleme

| Kaynak | İlk kullanımı | Doğrulanacak konu |
| --- | --- | --- |
| Ortak arşiv, Football-Data, Nesine ve keskin piyasa referansları | Maç kimliği, sonuç, oran, marj ve karşılaştırma tabanı | Aynı maç ve pazar tanımı, gerçek alım zamanı ve oran değişimi. Football-Data 23 Temmuz 2025 sonrasında Pinnacle alanları için güncellik sorunu bildiriyor. [Football-Data veri notu](https://football-data.co.uk/data.php) |
| Mevcut ESPN, API-Football ve FotMob kaynakları | Kadro, eksikler, son maçlar, fikstür, hakem | Kaynak ve lig bazında alan doluluğu, kadronun açıklanma zamanı, takım eşleşmesi ve ortak API kotası. [Mevcut bağlayıcılar](../src/quantfoot/data/match_dossier.py) |
| Hudl StatsBomb Open Data | Şut bazlı xG ve olay verisiyle araştırma | Açık lig/sezonların oran arşiviyle kesişimi, kaynak atfı ve yayın koşulları. [Açık veri ve lisans](https://github.com/hudl/open-data) |
| Opta | Ücretli erişim değerlendirmesinde olay ve oyuncu verisi | Hedef lig kapsaması, tarihsel kayıt zamanı ve ortak depoda kullanım hakları. [Opta veri akışları](https://www.statsperform.com/products/opta-data-feeds/) |
| FBref | Kapsaması doğrulanan tablo ve temel istatistikler | Sağlayıcı verilerinin kaldırıldığı duyuruldu. Gelişmiş alanlar veri sözleşmesine girmeden lig ve sezon bazında teyit edilir. [Sports Reference veri duyurusu](https://www.sports-reference.com/blog/category/advanced-stats/) |
| Open-Meteo ve resmî saha/hakem kayıtları | Stadyum, maç saati tahmini, saha türü, hakem geçmişi | Tahmin anında yayımlanmış hava koşusu ve stadyum koordinatı. Hakem geçmişinde maç sayısı ve küçük örneklem. [Arşivlenmiş hava tahminleri](https://open-meteo.com/en/docs/historical-forecast-api) |
| Kulüp açıklamaları ve resmî mali kayıtlar | Kadro değişimi, saha ve kulübe özgü belgelenmiş olaylar | Yayın zamanı, kapsama ve ölçülebilir tanım. Ülke veya sosyal bağlama ilişkin genellemeler yerine doğrulanabilir takım olayları kullanılır. |

Veri sözleşmesi her alan için maç kimliği, kaynak, alınma ve kullanılabilirlik zamanı, yararlanılan sezon ve eksiklik durumu tutar. Başlama ve veri zamanları UTC saklanır, raporda TSİ gösterilir. Aynı maçın tekrarları ve ertelenen maçlar kimlik bazında çözülür. Sayısal eksik alanlar ayrı işaretlenir. Gerekli doldurma ve ölçekleme parametreleri yalnız eğitim diliminde öğrenilir.

## Özellikler ve deney tasarımı

- **İlk örneklem.** `E0` ve 1-X-2, maçtan 60 dakika önce tek karşılaştırma anı. İlk pilotta geçmiş beş maçta maç başına puan, atılan/yenen gol, ev/deplasman ayrımı, dinlenme, rakip gücü ve iki takımın farkları kullanılır. Maç öncesi oran görüntüsü bulunmayan satırlar tarihsel kaynak karşılaştırmasında ayrıca işaretlenir.
- **İkinci deney.** Kadro, oyuncu dakika yükü, sakat ve cezalılar, maç aşaması, hava ve hakem bilgilerini tek aile halinde sırayla ekle. Form için 5 ve 10 maçlık pencerelerin tutarlılığını ölç. İkili geçmişi küçük örneklem olarak büzüştür. Hakem ve saha etkisini önce ilgili kart veya gol pazarında sınamayı planla.
- **Sızıntı denetimi.** Yalnız daha önce bitmiş maçlardan özellik üret. Güncel maçın şutları, maçtan sonra teyit edilen kadro, gelecekte alınmış oran ve maçtan sonra derlenen hava ölçümü tahmin anına giremez. Tarihsel arşivde aynı gün maç saati güvenilir değilse o günün önceki sonuçlarını eğitim özelliğine katma.
- **Model seçimi.** Marjsız piyasa ile Dixon–Coles ve Elo + lojistik taban modellerini kur. Sonra Random Forest ve mevcut LightGBM'yi aynı maçlarda aynı özelliklerle kıyasla. XGBoost ve CatBoost ancak aynı koşullarda ek katkıyı ölçen deney olarak devreye girsin. Üretim ortamında NumPy, pandas, scikit-learn ve LightGBM zaten mevcut. XGBoost ve CatBoost bu çalışma ortamında kurulu değildi. [scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) · [LightGBM](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMClassifier.html) · [XGBoost](https://xgboost.readthedocs.io/en/stable/python/python_api.html) · [CatBoost](https://catboost.ai/docs/en/)
- **Tuning ve trend.** İç zaman bölmelerinde küçük bir rastgele parametre araması, ardından ayrı kalibrasyon dilimi ve dış sezon testi. Sezon ve lig bazında log-loss, Brier, güvenilirlik grafiği, veri kapsaması ve makro sınıflandırma metrikleri. Piyasa farkının belirsizliğini maç haftası bloklarıyla hesapla. Önceden tanımlanan sezonlarda istikrarlı ölçüm elde edilirse sonraki maçlarda paralel denemeye geç.

## Risk, yayın ve izleme

- **Risk ve simülasyon.** Mevcut v4 kurallarıyla önce sanal portföy. Banko ve kasa koruma modlarının kuralları kendi eşikleriyle çalışır. Sonuçta bacak ve kupon bazında beklenen değer, kapanış çizgisi farkı (CLV), net getiri, tepe-dip düşüşü ve toplam açık risk raporlanır. Negatif EV eşiği bir kayıp freni olarak değerlendirilir. Veri eskimişse veya uygun seçim yoksa sonuç **PAS**. [Kasa koruma](../scripts/kasa_koruma.py) · [Kupon sistemi](../src/quantfoot/coupons/system_builder.py)
- **Backend.** Mevcut Python komutları ve ortak veri katmanı. Sağlayıcılar ham veriyi, özellik üretimi maç öncesi görüntüyü, değerlendirme ise gerçekleşen sonucu ayrı tutar. Geriye dönük testler veri sürümü ve parametreleri kaydeder. Yerel kurulum ve CI mevcut `pyproject.toml` üzerinden çalışır. [Bağımlılıklar](../pyproject.toml) · [CI](../.github/workflows/ci-tests.yml)
- **Frontend.** Mevcut [panoyu](../docs/index.html) kullan. Paylaşılan panoda yalnız toplu kalite, kapsama ve risk metrikleri. Maç tahminleri ve kuponlar normal ortak akışın belirlediği yapay zekâ klasöründe kalır. Pano veri zamanı, örneklem sayısı ve PAS gerekçesini gösterir.
- **Canlı kullanım.** Onaylı ortak kaynaklardan salt okunur fiyat alımı ve sanal deneme. Bir bookmaker hesabında işlem yapmak için proje kurallarındaki açık kullanıcı onayı gerekir. Otomatik analiz programı eklemek yerine mevcut elle tetiklenen ortak akış ve onaylı takip görevi kullanılır. [Çalıştırma akışı](../.github/workflows/daily-autonomous.yml) · [Depo kuralları](../AGENTS.md)

Uygulama sırası ve kabul ölçütleri [görev listesinde](todo.md).
