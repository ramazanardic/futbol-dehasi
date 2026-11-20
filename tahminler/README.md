# Yapay zekâ tahmin yarışması

Her yapay zekâ **yalnız kendi klasörüne** yazar; başkasının klasörüne dokunmaz. Kazanan, aynı günlerde aynı maçlar
üzerinde en isabetli olandır.

| Klasör | Yapay zekâ |
|---|---|
| `claudetahmin/` | Claude (QuantFoot sistemi, her gün otomatik yazılır) |
| `geminitahmin/` | Gemini |
| `antigravitytahmin/` | Antigravity |
| `chatgbttahmin/` | ChatGPT |

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
| tarih, kupon, kupon_no | Kupon dosyası/adı ve sıra numarası |
| kupon_toplam_oran, kupon_tutma_olasiligi | Nesine toplam oranı ve tahmin edilen tutma olasılığı (0–1) |
| saat, mac, nesine_kodu, pazar, secim, nesine_oran, olasilik | Bacak bilgisi |

Tahminler **maç başlamadan önce** commit edilmelidir; git geçmişindeki zaman damgası bunun kanıtıdır.
Karşılaştırmada ölçütler: ana tercih isabeti (%), olasılık kalitesi (Brier / log-loss, 1X2), tutan kupon / bacak
oranı ve 1 birim sabit bahisle kâr/zarar (ROI).
