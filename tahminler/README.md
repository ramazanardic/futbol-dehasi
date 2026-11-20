# Yapay zekâ tahmin yarışması

Her yapay zekâ **yalnız kendi klasörüne** yazar; başkasının klasörüne dokunmaz. Kazanan, aynı günlerde aynı maçlar
üzerinde en isabetli olandır.

| Klasör | Yapay zekâ |
|---|---|
| `claudetahmin/` | Claude (QuantFoot sistemi, her gün otomatik yazılır) |
| `geminitahmin/` | Gemini |
| `antigravitytahmin/` | Antigravity |
| `chatgbttahmin/` | ChatGPT |

## Kural: yöntem ortak, tahmin bağımsız

- **Ortak olan:** depodaki bütün kod, algoritmalar, modeller ve veri kaynakları (`src/`, `scripts/`, `data/`). Her
  yapay zekâ bunları kullanabilir ve geliştirebilir.
- **Bağımsız olan:** tahminin kendisi. Her yapay zekâ kendi klasörünü **kendi çalıştırmasıyla** üretir; ortak
  raporlardan (`reports/daily/`, `reports/takip/` …) ya da başka bir yapay zekânın klasöründen kopyalamaz.
- **Kuponlar yalnız kuran yapay zekânın klasörüne yazılır** (ortak `reports/` klasörlerine değil). Her kupon kurulumu
  ayrı dosyadır; aynı hedefin son dosyası geçerli kupondur. Dosyalar hem bilgisayardaki depoda hem GitHub'da
  (`futbol-dehasi`) bulunur.
- Claude'un alanı: `scripts/ai_tahmin.py` her seferinde analizi kendisi yeniden çalıştırır (canlı Nesine bülteni,
  global keskin fiyatlar, araştırma); `scripts/nesine_kupon.py` kuponları doğrudan bu klasöre yazar
  (`kupon_<hedef>x_<SSDD>.json/.md`), maç öncesi kontrol ve kapanış fiyatı da buradadır (`kupon_kontrol.md`,
  `kupon_clv.json`, `clv.md`).

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

**`kuponlar.csv`** — kupon bacağı başına bir satır

| Sütun | Açıklama |
|---|---|
| tarih, kupon_turu, kupon, kupon_no | Kupon ailesi (`karma`, `iyms`, `altust`, `kg`, `ms12`), dosya adı ve sıra no |
| kupon_toplam_oran, kupon_tutma_olasiligi | Nesine toplam oranı ve tahmin edilen tutma olasılığı (0–1) |
| saat, mac, nesine_kodu, pazar, secim, nesine_oran, olasilik | Bacak bilgisi |

Açık (henüz sonuçlanmamış) günlerin tahminleri ve kuponları GitHub'a **konmaz**; her yapay zekâ bunları kendi bilgisayarında
tutar ve gün sonuçlandıktan sonra gönderir. Böylece hiçbir yapay zekâ ötekinin açık tahminlerinden etkilenmez.
Karşılaştırmada ölçütler: ana tercih isabeti (%), olasılık kalitesi (Brier / log-loss, 1X2), tutan kupon / bacak
oranı ve 1 birim sabit bahisle kâr/zarar (ROI).
