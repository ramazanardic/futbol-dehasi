# Yapay zekâ çalışma kuralı (futbol-dehası) — her yapay zekâ için bağlayıcı

> **Bağlanır bağlanmaz: [docs/ORTAK_SISTEM.md](docs/ORTAK_SISTEM.md)'yi oku ve tahmin/kuponu yalnız oradaki ortak hatla üret:**
> `QUANTFOOT_AI=<klasörün> python scripts/gunluk_tahmin.py --tarih <gün>` (bülten + keskin referans → tahmin → derin
> araştırma → banko kupon → kural denetimi). Banko kupon: her bacak düzeltilmiş P ≥ %70, oran ≥ 1,20, 5 bacak (gerekçeliyse 6),
> maç başına tek bacak, beraberlik / KG / ilk gol / takım golü / piyango bacağı yok, aynı tercih iki kupona girmez,
> toplam tutma olasılığı yazılır. Notu kendin vermezsin: `scripts/gun_degerlendirme.py`. Kullanıcı onayı olmadan bahis
> oynanmaz, para yatırılmaz/çekilmez. Bu dosyadaki klasör kuralları ortak sistemden de önce gelir.

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

## Gemini / Antigravity için

Sen Gemini'sin (Antigravity de bu dosyayı ve AGENTS.md'yi okur): yalnız kendi klasörün (`tahminler/geminitahmin/` ya da
`tahminler/antigravitytahmin/`) senin; öteki `tahminler/*tahmin/` klasörlerini hiçbir araçla açma, aramalarda hariç tut.
Kendi karneni yazma: 20 Kasım öz-raporu 56/103 diyordu, Nesine sonuçlarıyla gerçek 53/103 çıktı (docs/ORTAK_SISTEM.md §4).
