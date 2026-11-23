# Yapay zekâ tahmin yarışması

Her yapay zekâ **yalnız kendi klasörüne** yazar; başkasının klasörüne dokunmaz. Kazanan, aynı günlerde aynı maçlar
üzerinde en isabetli olandır.

| Klasör | Yapay zekâ |
|---|---|
| `claudetahmin/` | Claude |
| `geminitahmin/` | Gemini |
| `antigravitytahmin/` | Antigravity |
| `chatgbttahmin/` | ChatGPT |
| `grokbottahmin/` | Grok Bot |

## Ortak depo ve tahmin yayını

- **Her yapay zekâ yalnız kendi klasörüne yazar ve kendi klasöründen devam eder. Başka bir yapay zekânın
  klasörünü açmak, okumak, listelemek, kopyalamak, değiştirmek yasaktır** (Claude'unkini Gemini, Gemini'ninkini
  ChatGPT, ChatGPT'ninkini Antigravity … görmez). Bütün yapay zekâlar için bağlayıcı kural metni: kökteki
  [AGENTS.md](../AGENTS.md) (aynısı `GEMINI.md` ve `CLAUDE.md`).
- **Ortak olan:** depodaki bütün kod, algoritmalar, modeller, kalibrasyon dosyaları ve veri kaynakları (`src/`,
  `scripts/`, `data/` — FotMob dahil tüm kaynaklara 5 yapay zekâ eşit erişir). Tek ortak giriş komutu:
  `QUANTFOOT_AI=<klasör> python scripts/gunluk_tahmin.py --tarih <gün>`, kasa koruma planı:
  `QUANTFOOT_AI=<klasör> python scripts/kasa_koruma.py --tarih <gün> --kasa <TL>`, öz-denetim:
  `QUANTFOOT_AI=<klasör> python scripts/oz_gelistirme.py`.
- **Sistem yalnız kullanıcı sorduğunda çalışır**; otomatik zamanlanmış analiz yoktur. Kullanıcı hangi yapay zekâya
  sorduysa o yapay zekâ araştırır ve yazar.
  Onaylı tek zamanlanmış görev `QuantFoot\KuponIzle`: kupon bacaklarını kontrol eder, dünün API-Football sonuçlarını
  arşive ekler; analiz yapmaz.
- **Yayın:** ChatGPT'nin istek üzerine hazırladığı günlük `mac_tahminleri.csv` ve `kuponlar.csv`,
  [ChatGPT klasöründe](chatgbttahmin/) herkese açık olarak da yayımlanır. Diğer yapay zekâlar için kendi
  klasör kuralları ve yayın izinleri geçerlidir. Ortak alanlara (`reports/`, `docs/data/`) tahmin yazılmaz.
  Yerel çalıştırmada `QUANTFOOT_AI=<klasör>` zorunludur.
- **Değerlendirme ortaktır:** ertesi gün, önceki günün maçları sonuçlandırılır ve bütün yapay zekâların tahminleri
  `scripts/gun_degerlendirme.py --tarih <gün>` ile değerlendirilir; sonuç herkesin görebileceği
  `degerlendirme/<tarih>.md` / `.json` dosyasına yazılır. Bu dosyada yalnız **bitmiş** maçlar yer alır.

## Günlük kupon (22 Kasım'dan itibaren, her yapay zekâ aynısını yapar)

Bağlayıcı yöntem ve kurallar: [docs/ORTAK_SISTEM.md](../docs/ORTAK_SISTEM.md). Kısaca: `scripts/gunluk_tahmin.py`
ile banko kupon — her bacak düzeltilmiş P ≥ %70, Nesine oranı ≥ 1,20 (≤ 1,80), 5 bacak (gerekçeliyse 6), maç başına
tek bacak, izinli aileler (İlk yarı, Alt/Üst, Yarı özel, MS 1/2, Kombine, 2Y KG Yok), beraberlik / KG / ilk gol /
takım golü / piyango bacağı yok, bir tercih iki kuponda tekrar edilmez, toplam tutma olasılığı yazılır.

Eski "karma 5x–50x, 7–8 maç, İY/MS / KG kuponu" talebi **kaldırıldı** (21 Kasım denetimi: bu kuponların bacakları
%47 tuttu, piyango kuponlarının hiçbiri tutmadı). Yüksek hedef yalnız kullanıcı açıkça isterse `--mod risk` ile ve
dürüst tutma olasılığıyla kurulur; banko kurallarıyla ulaşılamayan hedef kullanıcıya açıkça söylenir.

Dosya adları: `kupon_<hedef>x_<SSDD>.json/.md` (tek aile: `kupon_<hedef>x_<aile>_<SSDD>`). Aynı hedef ve ailenin
en son dosyası geçerli kupondur; `kupon_denetim.md` kural denetimini içerir.

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
