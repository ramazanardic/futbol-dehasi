# Yapay zekâ tahmin yarışması

Her yapay zekâ **yalnız kendi klasörüne** yazar; başkasının klasörüne dokunmaz. Kazanan, aynı günlerde aynı maçlar
üzerinde en isabetli olandır.

| Klasör | Yapay zekâ |
|---|---|
| `claudetahmin/` | Claude (QuantFoot sistemi, her gün otomatik yazılır) |
| `geminitahmin/` | Gemini |
| `antigravitytahmin/` | Antigravity |
| `chatgbttahmin/` | ChatGPT |
| `grokbottahmin/` | Grok Bot |

## Kural: yöntem ortak, tahmin gizli, değerlendirme ortak

- **Her yapay zekâ yalnız kendi klasörüne yazar ve kendi klasöründen devam eder. Başka bir yapay zekânın
  klasörünü açmak, okumak, listelemek, kopyalamak, değiştirmek yasaktır** (Claude'unkini Gemini, Gemini'ninkini
  ChatGPT, ChatGPT'ninkini Antigravity … görmez). Bütün yapay zekâlar için bağlayıcı kural metni: kökteki
  [AGENTS.md](../AGENTS.md) (aynısı `GEMINI.md` ve `CLAUDE.md`).
- **Ortak olan:** depodaki bütün kod, algoritmalar, modeller ve veri kaynakları (`src/`, `scripts/`, `data/`).
- **Sistem yalnız kullanıcı sorduğunda çalışır**; otomatik zamanlanmış analiz yoktur. Kullanıcı hangi yapay zekâya
  sorduysa o yapay zekâ araştırır ve yazar.
  Onaylı tek zamanlanmış görev `QuantFoot\KuponIzle`: kupon bacaklarını kontrol eder, dünün API-Football sonuçlarını
  arşive ekler; analiz yapmaz.
- **Tahminler gizlidir:** her yapay zekâ analizini, tahminlerini ve kuponlarını yalnız kendi klasörüne
  (`tahminler/<klasör>/<tarih>/`) ve yalnız kendi bilgisayarına yazar. Bu klasörler GitHub'a **hiç** gönderilmez
  (`.gitignore`: `tahminler/*/*`, yalnız README'ler izlenir); ortak alanlara (`reports/`, `docs/data/`) tahmin yazılmaz.
  Kod bunu zorunlu `QUANTFOOT_AI=<klasör>` ile yapar (varsayılan yoktur).
- **Değerlendirme ortaktır:** ertesi gün, önceki günün maçları sonuçlandırılır ve bütün yapay zekâların tahminleri
  `scripts/gun_degerlendirme.py --tarih <gün>` ile değerlendirilir; sonuç herkesin görebileceği
  `degerlendirme/<tarih>.md` / `.json` dosyasına yazılır. Bu dosyada yalnız **bitmiş** maçlar yer alır.

## Günlük standart kupon talebi (20 Kasım'dan itibaren, her yapay zekâ aynısını yapar)

| Kupon | Aile | En az toplam oran | En çok maç |
|---|---|---|---|
| Karma 5x, 10x | bütün bahis aileleri | 5, 10 | 7 |
| Karma 20x, 30x, 50x | bütün bahis aileleri | 20, 30, 50 | 8 |
| İY/MS kuponu | yalnız İlk Yarı / Maç Sonucu (1/1, 1/0, 1/2, 0/1, 0/0, 0/2, 2/1, 2/0, 2/2) | 5 | 7 |
| Alt/Üst kuponu | yalnız maç sonu toplam gol Alt/Üst | 5 | 7 |
| KG kuponu | yalnız Karşılıklı Gol Var / Yok | 5 | 7 |
| MS 1-2 kuponu | yalnız Maç Sonucu 1 ya da 2 | 5 | 7 |

Kurallar (hepsi için): toplam Nesine oranı **en az** hedef kadar (fazlası olabilir, altı asla); hedefe daha az
maçla ulaşılabiliyorsa daha az maç; bacak başına Nesine oranı ≥ 1,20; karma kuponlarda bir tercih iki kuponda
tekrar edilmez (aynı maçta başka tercih serbest). Amaç: kuponun tamamının tutma olasılığı en yüksek olsun.

Dosya adları: karma `kupon_<hedef>x_<SSDD>.json/.md`, tek aile `kupon_<hedef>x_<aile>_<SSDD>.json/.md`
(aile: `iyms`, `altust`, `kg`, `ms12`). Aynı hedef ve ailenin en son dosyası geçerli kupondur.

## Ortak biçim

Her gün için `tahminler/<klasör>/<YYYY-AA-GG>/` altında iki CSV (UTF-8, virgülle ayrılmış, ondalık nokta):

**`mac_tahminleri.csv`** — maç başına bir satır

| Sütun | Açıklama |
|---|---|
| tarih, saat | Nesine bülten günü ve TSİ başlama saati |
| lig, mac | Nesine'deki adlarla (`Ev - Deplasman`) |
| nesine_kodu | Nesine maç kodu (eşleştirme bununla yapılır; yoksa boş bırakın) |
| olasilik_1, olasilik_X, olasilik_2 | 0–1 arası, toplamı 1 |
| beklenen_gol_ev, beklenen_gol_dep | Beklenen gol (xG) |
| en_olasi_skor | Örn. `1-1 (0.115)` |
| ana_secim_pazar, ana_secim | Maç için tek ana tercih (Nesine pazar ve seçim adıyla, örn. `2,5 Gol Alt/Üst`, `2,5 Üst`) |
| nesine_oran, olasilik | Ana tercihin Nesine oranı ve tahmin edilen olasılığı (0–1) |
| fiyat_kaynagi, guven, not | Serbest |
| secim_adi | İsteğe bağlı ama önerilir (21 Kasım): tercihin sonuçlandırma adı (örn. `Dep İY 0.5 Alt`, `MS 1 & 2.5 Üst`, `2Y KG Yok`). Doluysa değerlendirme bunu kullanır; boşsa pazar/seçim adından çıkarmaya çalışır ve takım golü, yarı KG, kombine gibi pazarlarda başarısız olabilir |

**`kuponlar.csv`** — kupon bacağı başına bir satır

| Sütun | Açıklama |
|---|---|
| tarih, kupon_turu, kupon, kupon_no | Kupon ailesi (`karma`, `iyms`, `altust`, `kg`, `ms12`), dosya adı ve sıra no |
| kupon_toplam_oran, kupon_tutma_olasiligi | Nesine toplam oranı ve tahmin edilen tutma olasılığı (0–1) |
| saat, mac, nesine_kodu, pazar, secim, nesine_oran, olasilik | Bacak bilgisi |
| secim_adi | Bacağın sonuçlandırma adı (yukarıdaki gibi, önerilir) |

Karşılaştırmada ölçütler: ana tercih isabeti (%), olasılık kalitesi (Brier / log-loss, 1X2), tutan kupon / bacak
oranı ve 1 birim sabit bahisle kâr/zarar (ROI).
