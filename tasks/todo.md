# QuantFoot geliştirme görevleri

Temel ölçüm ve kaynak kararları [planda](plan.md). Görevler bağımlılık sırasındadır.

## 1. Karşılaştırma tabanını düzelt ve sabitle

- [ ] Önbellek yazarı yalnız geçerli olasılık dizilerini kaydetsin. Eski önbellek okuyucusu belirsizlik dizisini model dışında tutsun.
- [ ] Tahmin sınıf sırasını, maç eşleşmesini ve olasılık toplamını doğrula. Karışım ağırlığını geçmiş dilimlerde seç.
- **Doğrulama** — Yerel önbellekte 12.894 maçlık dört sezon sonucu yeniden üretilsin. Geçersiz dizi model listesine girmesin.
- **Dosyalar** — `scripts/research_experiments.py`, `src/quantfoot/evaluation/market_benchmark.py` ve ilgili testler.

## 2. Bir ligde maç öncesi veri sözleşmesini kur

- [ ] E0 1-X-2 maçlarında arşiv ve piyasa satırlarını kararlı bir kimlikle eşleştir. Kaynak, veri zamanı ve eksikliği tut.
- [ ] Örneklem, eşleşmeyen satır sayısı, çift kayıt ve alan doluluğunu tarih ve kaynak bazında raporla.
- **Doğrulama** — Tekrarlanan içe aktarma çift maç üretmesin. Başlama sonrasında yayımlanan kayıt pilot özelliklere girmesin.
- **Bağımlılık** — 1. **Dosyalar** — `src/quantfoot/data/loader.py` ve ilgili veri testleri.

## 3. Form ve kadro özelliklerini ayrı ayrı sınayarak ekle

- [ ] Önce son 5 maç, saha ve dinlenme özelliklerini üret. Ardından kadro ve dış kaynakları aile bazında ekle.
- [ ] Eksik kadro, değişen maç kimliği ve aynı gün saatsiz maç örneklerini doğrula.
- **Doğrulama** — Bir maçın gelecekteki satırları değiştirildiğinde o maçın özellikleri sabit kalsın. Her ek aile için veri kapsaması ve örneklem dışı fark raporlansın.
- **Bağımlılık** — 2. **Dosyalar** — Mevcut maç araştırması ve özellik üretimi modülleri.

## 4. Modelleri zaman sıralı karşılaştır

- [ ] Piyasa, lojistik/Elo, Dixon–Coles, Random Forest ve LightGBM'yi aynı dış test maçlarında karşılaştır.
- [ ] İç bölmede ayarla, ayrı dilimde kalibre et ve dış sezonda log-loss, Brier, F1, AUC ve haftalık blok belirsizliğini raporla.
- **Doğrulama** — Test sezonu parametre seçimine veya kalibrasyona girmesin. Üretim adayı aynı piyasa referansına karşı ölçülebilir, istikrarlı iyileşme göstermeli.
- **Bağımlılık** — 1–3. **Dosyalar** — `src/quantfoot/evaluation/backtest.py`, `src/quantfoot/models/ensemble.py`.

İlk doğrulama noktası. Veri ve zaman sınırı testleri ile tam `pytest -q` yeşil. Veri kapsaması ve model karşılaştırması yeniden üretilebilir.

## 5. Sanal portföyü denetle

- [ ] Ölçüm anı fiyatlarıyla mevcut banko ve kasa koruma modlarını simüle et. Ücret, iptal, eski fiyat ve aynı maç yoğunlaşması durumlarını değerlendir.
- **Doğrulama** — Günlük risk ve kupon başı limit ortak kurallarla uyumlu. Fiyat bulunamazsa PAS. ROI, CLV ve azami düşüş raporda örneklemle birlikte var.
- **Bağımlılık** — 4. **Dosyalar** — `scripts/kasa_koruma.py`, `src/quantfoot/coupons/system_builder.py` ve portföy değerlendirmesi.

## 6. Ortak panoda raporla ve izle

- [ ] Mevcut elle çalıştırılan hatta veri kapsaması, referans zamanı, log-loss, Brier ve sanal portföy özetini ekle.
- [ ] Veri kaynağı veya dağılım değiştiğinde önce eski ve yeni sürümü aynı maçlarda karşılaştır.
- **Doğrulama** — Bir örnek rapor ortak hattın çıktısıyla tutarlı. Her metrikte zaman aralığı ve maç sayısı var. CI'da ortak araç ve klasör eşitliği testi geçiyor.
- **Bağımlılık** — 5. **Dosyalar** — `scripts/build_dashboard.py`, `docs/index.html` ve mevcut CI kontrolleri.
