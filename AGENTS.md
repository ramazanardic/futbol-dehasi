# Yapay zekâ çalışma kuralı (futbol-dehası) — her yapay zekâ için tek ortak sözleşme

> **TÜM YAPAY ZEKÂLAR AYNI ORTAK SİSTEMDEN, AYNI ŞEKİLDE ÇALIŞIR (kullanıcı kuralı, 23 Kasım 2026):**
> Bağlanır bağlanmaz [docs/ORTAK_SISTEM.md](docs/ORTAK_SISTEM.md)'yi oku ve tahmin, araştırma, kupon, denetim ile
> öz-geliştirme işlemlerinin **tamamını** yalnızca oradaki tek ortak hattan yürüt:
>
> 1. **Günlük tek ortak üretim hattı:** `QUANTFOOT_AI=<klasörün> python scripts/gunluk_tahmin.py --tarih <YYYY-AA-GG>`
>    (bülten + keskin referans → tahmin → derin araştırma + ekstrem gol taraması → banko kupon → kural & portföy denetimi).
> 2. **Kendi çok-günlük kalibrasyon öz-denetimi:** `QUANTFOOT_AI=<klasörün> python scripts/oz_gelistirme.py`
>    (yalnız kendi klasörünü okur, altın havuzları ve zehirli alt-pazar alarmlarını çıkarır).
> 3. **Ertesi gün ortak nesnel karne:** `python scripts/gun_degerlendirme.py --tarih <YYYY-AA-GG>`
>    (notu hiçbir yapay zekâ kendisi vermez).
>
> Banko kupon: her bacak düzeltilmiş P ≥ %70, oran ≥ 1,20 (≤ 1,80), 5 bacak (gerekçeliyse 6), maç başına tek bacak,
> beraberlik / KG / ilk gol / takım golü / piyango bacağı yok, `market_diagnosis` v3 kalkanları (İY ÇŞ 12, sert steam,
> Dep İY 0.5 Üst, İY Çift) aktif, aynı tercih iki kupona girmez, toplam tutma olasılığı ve portföy yoğunlaşması yazılır.
> Kullanıcı açıkça isterse sistem kuponları `quantfoot.coupons.system_builder`, ekstrem gol taraması
> `scripts/ekstrem_gol_analiz.py` ortak modülleriyle üretilir. Kullanıcı onayı olmadan bahis oynanmaz, para
> yatırılmaz/çekilmez. Tüm 5 yapay zekâ aynı kod, aynı kalibrasyon ve aynı veri kaynaklarına (FotMob dahil) **eşit**
> erişir. Bu dosyadaki klasör izolasyonu kuralları her şeyden önce gelir.

> **Her maçta Nesine’nin açtığı bütün futbol bahis ailelerini ve seçimlerini değerlendir.** Kupon önerisine,
> araştırma ve seçilen kupon modunun kurallarını geçen en uygun seçimler girer. [Ayrıntılar](docs/ORTAK_SISTEM.md#tüm-futbol-bahis-aileleri)

Bu depoda beş yapay zekâ çalışır ve tahminleri eşit koşullarda yarıştırılır. Kullanıcının kuralı (20–23 Kasım 2026):

1. **Her yapay zekâ yalnız kendi tahmin klasörüne yazar ve kendi klasöründen devam eder.**

   | Yapay zekâ | Kendi klasörü | `QUANTFOOT_AI` |
   |---|---|---|
   | Claude | `tahminler/claudetahmin/` | `claudetahmin` |
   | Gemini | `tahminler/geminitahmin/` | `geminitahmin` |
   | Antigravity | `tahminler/antigravitytahmin/` | `antigravitytahmin` |
   | ChatGPT | `tahminler/chatgbttahmin/` | `chatgbttahmin` |
   | Grok Bot | `tahminler/grokbottahmin/` | `grokbottahmin` |

2. **Başka bir yapay zekânın tahmin klasörünü açmak, okumak, listelemek, kopyalamak, değiştirmek veya silmek yasaktır.**
   Claude'un klasörünü Gemini, Gemini'ninkini ChatGPT, ChatGPT'ninkini Antigravity … görmez; hiçbiri ötekinin
   tahminlerine bakarak tahmin yapmaz. Arama/listeleme komutlarında öteki klasörleri hariç tutun.
3. **Geri kalan her şey herkese açıktır ve herkes için aynıdır:** kod (`src/`, `scripts/`), testler (`tests/`), veriler
   (`data/`), araştırma, belgeler (`docs/`) ve ortak değerlendirme alanı (`degerlendirme/`). Hiçbir veri kaynağı veya
   kural tek bir yapay zekâya özel ayrıcalık tanıyamaz (`tests/test_common_ai_parity.py` CI'da zorunlu kılar).
4. **GitHub ana ortak depodur.** Ortak kod, veri ve belgeler burada kullanılır ve tüm yapay zekâlar aynı `main` dalından
   (`git pull` → `pytest -q`) çalışır. Kullanıcının 21 Kasım 2026 talimatıyla ChatGPT, istek üzerine hazırladığı günlük
   `mac_tahminleri.csv` ve `kuponlar.csv` dosyalarını `tahminler/chatgbttahmin/<tarih>/` yoluna da yayımlar. Diğer yapay
   zekâlar için kendi klasör kuralları ve yayın izinleri geçerlidir. Tahminler `reports/` veya `docs/data/` alanına
   yazılmaz. Sistemi çalıştırmadan önce `QUANTFOOT_AI=<klasörünüz>` açıkça ayarlanır.
5. **Sistem yalnız kullanıcı sorduğunda çalışır**; kullanıcı hangi yapay zekâya sorduysa yalnız o yapay zekâ
   araştırır ve kendi klasörüne yazar.
   Kullanıcının onayladığı tek zamanlanmış görev: Windows `QuantFoot\KuponIzle` (15 dakikada bir geçerli kuponların
   bacaklarını Nesine'de kontrol eder ve günde bir kez dünün API-Football sonuçlarını yerel arşive ekler); analiz yapmaz.
6. **Tek istisna — ertesi gün değerlendirmesi:** kullanıcı isteyince önceki günün tahminleri yalnız
   `scripts/gun_degerlendirme.py --tarih <gün>` ile, bitmiş maçlar üzerinden değerlendirilir ve sonuç ortak
   `degerlendirme/<gün>.md` dosyasına yazılır. Bu araç dışında öteki klasörlerin içeriği açılmaz.

Ayrıntılar ve ortak dosya biçimi: [tahminler/README.md](tahminler/README.md) · Tek ortak sistem: [docs/ORTAK_SISTEM.md](docs/ORTAK_SISTEM.md).
