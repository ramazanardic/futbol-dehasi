# Yapay zekâ çalışma kuralı (futbol-dehası) — her yapay zekâ için bağlayıcı

Bu depoda beş yapay zekâ çalışır ve tahminleri yarıştırılır. Kullanıcının kuralı (20 Kasım 2026):

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
3. **Geri kalan her şey herkese açıktır:** kod (`src/`, `scripts/`), testler, veriler (`data/`), araştırma, belgeler
   (`docs/`) ve ortak değerlendirme alanı (`degerlendirme/`). Herkes bunları kullanabilir ve geliştirebilir.
4. **GitHub ana ortak depodur.** Ortak kod, veri ve belgeler burada kullanılır. Kullanıcının 21 Kasım 2026
   talimatıyla ChatGPT, istek üzerine hazırladığı günlük `mac_tahminleri.csv` ve `kuponlar.csv` dosyalarını
   `tahminler/chatgbttahmin/<tarih>/` yoluna da yayımlar. Depo herkese açıktır. Diğer yapay zekâlar için
   kendi klasör kuralları ve yayın izinleri geçerlidir. Tahminler `reports/` veya `docs/data/` alanına yazılmaz.
   Sistemi çalıştırmadan önce `QUANTFOOT_AI=<klasörünüz>` açıkça ayarlanır.
5. **Sistem yalnız kullanıcı sorduğunda çalışır**; kullanıcı hangi yapay zekâya sorduysa yalnız o yapay zekâ
   araştırır ve kendi klasörüne yazar.
   Kullanıcının onayladığı tek zamanlanmış görev: Windows `QuantFoot\KuponIzle` (15 dakikada bir geçerli kuponların
   bacaklarını Nesine'de kontrol eder ve günde bir kez dünün API-Football sonuçlarını yerel arşive ekler); analiz yapmaz.
6. **Tek istisna — ertesi gün değerlendirmesi:** kullanıcı isteyince önceki günün tahminleri yalnız
   `scripts/gun_degerlendirme.py --tarih <gün>` ile, bitmiş maçlar üzerinden değerlendirilir ve sonuç ortak
   `degerlendirme/<gün>.md` dosyasına yazılır. Bu araç dışında öteki klasörlerin içeriği açılmaz.

Ayrıntılar ve ortak dosya biçimi: [tahminler/README.md](tahminler/README.md).
