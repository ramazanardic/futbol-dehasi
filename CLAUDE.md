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
4. **Tahminler ve kuponlar ortak alanlara yazılmaz** (`reports/`, `docs/data/` …) ve GitHub'a gönderilmez
   (`.gitignore`: `tahminler/*/*`). Sistemi çalıştırmadan önce `QUANTFOOT_AI=<klasörünüz>` zorunludur (varsayılan yoktur; geçersiz değer hata verir).
5. **Sistem yalnız kullanıcı sorduğunda çalışır**; kullanıcı hangi yapay zekâya sorduysa yalnız o yapay zekâ
   araştırır ve kendi klasörüne yazar.
   Kullanıcının onayladığı tek zamanlanmış görev: Windows `QuantFoot\KuponIzle` (15 dakikada bir geçerli kuponların
   bacaklarını Nesine'de kontrol eder ve günde bir kez dünün API-Football sonuçlarını yerel arşive ekler); analiz yapmaz.
6. **Tek istisna — ertesi gün değerlendirmesi:** kullanıcı isteyince önceki günün tahminleri yalnız
   `scripts/gun_degerlendirme.py --tarih <gün>` ile, bitmiş maçlar üzerinden değerlendirilir ve sonuç ortak
   `degerlendirme/<gün>.md` dosyasına yazılır. Bu araç dışında öteki klasörlerin içeriği açılmaz.

Ayrıntılar ve ortak dosya biçimi: [tahminler/README.md](tahminler/README.md).

## Claude için

Sen Claude'sun: yalnız `tahminler/claudetahmin/` senin. `tahminler/geminitahmin/`, `tahminler/antigravitytahmin/`,
`tahminler/chatgbttahmin/` ve `tahminler/grokbottahmin/` klasörlerini hiçbir araçla (Read, Grep, Glob, ls, cat …)
açma; aramalarda bu yolları hariç tut.
