# KURALLAR — Ramazan'ın kupon kuralları (bağlayıcı, tek kaynak)

> Kural onarımı: 28 Kasım 2026 (`grokbot/kural-onarim-2026-11-28`). Bu dosya **her yapay zekâ için** (Claude, Gemini,
> Antigravity, ChatGPT, Grok Bot) bağlayıcıdır ve [AGENTS.md](AGENTS.md) / [docs/ORTAK_SISTEM.md](docs/ORTAK_SISTEM.md)
> ile çelişirse **bu dosya geçerlidir**. Kurallar `tests/test_ramazan_kurallari.py` ve `tests/test_ai_cikti_dogrula.py`
> ile kilitlidir: bu testleri kıran ya da gevşeten değişiklik birleştirilmez.

## Neden

22–28 Kasım denetimi (`tahminler/grokbottahmin/2026-11-28/surum_denetimi/rapor.md`):

- Kural dışı bacaklar %48 tuttu (250 bacak); kurala uyan bacaklar %68 (kurallar: P ≥ 0,70, oran 1,20–1,80, maç başına tek bacak, 2–5 bacak).
- 15+ oranlı 25 kuponun **25'i de** yattı.
- "Asla hayır deme" yedeği, 0,65 kademesi ve birleşik motor, kuralları sessizce gevşetiyordu.
- Gemini'nin kendi yazdığı sonuçlar 112 tercihin 17'sinde Nesine sonucuyla çelişti.

## Banko kupon (varsayılan ve zorunlu mod)

| # | Kural | Değer | Kodda |
|---|---|---|---|
| 1 | Bacak olasılığı | Düzeltilmiş **P ≥ 0,70** (0,65 kademesi yok) | `coupon_rules.MIN_CALIBRATED_P`, `kasa_koruma --min-p 0.70` |
| 2 | Bacak oranı | Nesine **1,20 – 1,80** | `settings.MIN_LEG_ODDS`, `BANKO_MAX_LEG_ODDS` |
| 3 | Maç | **Maç başına tek bacak**; bir maç en çok tek kupona girer (`mac_limit = 1`) | `build_rules_coupon`, `audit_coupons` |
| 4 | Bacak sayısı | **2–5 bacak**; gerekçeliyse açıkça **en çok 6**; tek maçlık banko kupon yok | `DEFAULT_MIN_LEGS=2`, `DEFAULT_MAX_LEGS=5`, `HARD_MAX_LEGS=6` |
| 5 | Toplam oran | Banko kupon toplam oranı **< 20**; varsayılan olarak 20+ oranlı ("loto") kupon üretilmez | `settings.BANKO_MAX_TOTAL_ODDS` |
| 6 | Yasak bacaklar | Beraberlik (MS 0/X, İY 0/X, 2Y 0 …) · **maç geneli KG / BTTS** (Var ve Yok), **2Y KG Var**, İY KG · **ilk gol** · **takım golü** (Ev/Dep gol, Ev/Dep Alt-Üst, "iki yarıda gol atar/atamaz", `DEĞİL(Ev İki Yarıda Gol)`) · **İY/MS** · İY/2Y · **skor** · **çifte şans** (`DEĞİL(MS 0)` = 12, `DEĞİL(MS 1)`, `DEĞİL(MS 2)` dahil) · handikap · tek/çift |
| 6a | İzinli istisnalar (28 Kas ince ayar) | **2Y KG Yok** (2. Yarı KG Yok) — P ≥ 0,70 ve oran 1,20–1,80 ile; denetimde 13'te 10. **Takımın yarı kazanma pazarları** ("Ev/Dep En Az Bir (Herhangi Bir) Yarıyı Kazanır/Kazanamaz", "Her İki Yarıyı Kazanır") — takım golü sayılmaz. Kombine bacakta her parça ayrı denetlenir ("MS 1 & 2Y KG Yok" izinli, "MS 1 & KG Var" yasak). | `coupon_rules.hard_banned_reason`, `BANNED_FAMILIES`, `is_draw_leg` |
| 7 | Rehabilitasyon | Kalibrasyon ya da "rehabilite" işareti yasak bir bacağı **açamaz** | `leg_decision` |
| 8 | Dürüst ret | Kurallara uyan banko kupon yoksa sonuç **boş** ve açık mesaj verilir: "kupon kurulamadı, kural gevşetilmedi". Yedek kademe, model türevi zorlaması ya da kuralsız "son çare" kupon **yok**. | `nesine_kupon.HONEST_NO_COUPON`, `kupon_kur.py` |
| 9 | Şeffaflık | Her kuponda bacaklar, toplam oran ve **toplam tutma olasılığı** (düzeltilmiş P'lerin çarpımı) yazılır | `honest_line`, `audit_markdown` |

Varsayılan olarak bacaklar doğrudan Nesine fiyatlıdır. Model türevi bacaklar yalnız `--model-bacak` ile, açık istek
üzerine eklenir. Yüksek oran motoru (`yuksek_oran_motoru.py`, `yuksek_oran_analiz.py`) **günlük ortak hatta yok**.
Araştırma modülü olarak durur ve yalnız kullanıcı açıkça isterse `--mod yuksek_oran` / `--mod risk` ile çalışır.
O durumda tutma ihtimali dürüstçe yazılır.

## Çıktı ve sonuç kuralları (her yapay zekâ, Gemini dahil)

1. **Ortak şema:** `mac_tahminleri.csv` ve `kuponlar.csv`, `scripts/ai_tahmin.py` sütunlarıyla yazılır (`MATCH_COLS`,
   `COUPON_COLS`). Kendi uydurduğun sütun düzeni yasak.
2. **Kendi sonucunu yazma yasak:** tahmin ve kupon dosyalarına `bacak_sonucu`, `kupon_sonucu`, `ana_sonuc`,
   `ms_skoru`, `iy_skoru` gibi sonuç/skor sütunları ya da KAZANDI/KAYBETTİ/TUTTU/YATTI hücreleri yazılmaz.
   Sonuçlar yalnız ortak hattan gelir: `scripts/sonuc_defteri.py` ve `scripts/gun_degerlendirme.py`. Kaynak
   önceliği Nesine → FotMob → web. Bilinmeyen sonuç **"belirsiz"** kalır; skor asla uydurulmaz.
3. **Doğrulama zorunlu:** her gün çıktıyı paylaşmadan önce şunu çalıştır:
   `python scripts/ai_cikti_dogrula.py --ai <klasörün> --tarih <YYYY-AA-GG>`
   Çıkış kodu 1 ise o çıktı kullanıcıya **önerilmez**.
4. **Klasör izolasyonu:** her yapay zekâ yalnız `tahminler/<kendi>tahmin/` klasörüne yazar. Başkasının çıktısını
   silmez ya da üzerine yazmaz. Arşiv silmek yasak; toplu silme yapan commit geri alınır.

## Para ve onay

- Kullanıcı (Ramazan) açıkça onaylamadan bahis oynanmaz.
- Para yatırılmaz ya da çekilmez, kupon bozdurulmaz.
- Oynanmadan önce oranlar yeniden kontrol edilir.
- API-Football günde en çok 60 istek.

## Değişiklik süreci

Bu kurallar yalnız Ramazan'ın açık talimatıyla değişir. Değişiklik şu üç yerde **birlikte** yapılır, yoksa
testler kırılır:

- bu dosya;
- `tests/test_ramazan_kurallari.py`;
- ilgili sabitler.

"Kuponu her koşulda kur", "kural gevşet", "0,65'e in" gibi değişiklikler **kabul edilmez**.
