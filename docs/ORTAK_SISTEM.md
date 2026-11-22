# Ortak sistem — her yapay zekâ için tek bağlayıcı yöntem

Bu depoya bağlanan **her** yapay zekâ (Claude, Gemini, ChatGPT/Codex, Antigravity, Grok Bot) tahmin ve kuponu bu
belgedeki hatla üretir. Amaç tek: herkes aynı en iyi sistemi kullansın, kuponlar daha az yatsın, notlar dürüst olsun.
Belge 22 Kasım 2026'da 21 Kasım denetimlerinden (Grok Bot; 2.924 notlanmış tahmin, 11 oynanmış kupon, diğer yapay
zekâların 18–21 Kasım dosyaları) çıkan derslerle yazıldı. Çelişki olursa bu belge eski README / rapor metinlerinden
önce gelir; klasör gizliliği kuralı ([AGENTS.md](../AGENTS.md)) her şeyden önce gelir.

## 0. Bağlanınca ilk yapılacaklar

1. `AGENTS.md`'yi ve bu belgeyi oku. Kendi klasörünü bil: `QUANTFOOT_AI` = `claudetahmin` · `geminitahmin` ·
   `antigravitytahmin` · `chatgbttahmin` · `grokbottahmin`. Başka bir yapay zekânın klasörünü açma.
2. `git pull` → `pip install -e .` (gerekirse) → `pytest -q` yeşil olmalı.
3. Kullanıcı tahmin/kupon isterse **tek komut**:

   ```bash
   QUANTFOOT_AI=<klasörün> python scripts/gunluk_tahmin.py --tarih <YYYY-AA-GG>
   # Windows: $env:QUANTFOOT_AI="<klasörün>"; .\.venv\Scripts\python.exe scripts\gunluk_tahmin.py --tarih <gün>
   ```

4. Sonucu kullanıcıya `mac_tahminleri.csv`, `kuponlar.csv` ve `kupon_denetim.md`'den aktar: her kupon için bacaklar,
   toplam oran ve **toplam tutma olasılığı**. Kendi kafandan, hattın dışında tahmin veya kupon uydurma.

## 1. Zorunlu hat (sırası değişmez)

`scripts/gunluk_tahmin.py` aşağıdaki mevcut betikleri sırayla çalıştırır (`--yalniz` / `--atla` ile tek adım,
`--kuru` ile yalnız komutları görürsün):

| # | Adım | Komut | Ne yapar |
|---|---|---|---|
| 1 | `bulten` | `scripts/nesine_global.py --date D` | Nesine bülteni + keskin referanslar (Pinnacle, Smarkets, OddsMath/BetInAsia; ESPN en zayıf). Marj güç yöntemiyle kaldırılır, gol oranları referansa uydurulur (Dixon-Coles birleşik dağılım), bütün Nesine pazarları fiyatlanır, arşiv Platt kalibrasyonu (`market_calibration`) ve kuyruk düzeltmeleri (`data/calibration/market_tail_calibration.json`, `markets/market_reliability.py`) uygulanır. Nesine'nin kendi oranından adil fiyat türetilmez. |
| 2 | `tahmin` | `scripts/ai_tahmin.py --tarih D` | `mac_tahminleri.csv` (başlamış maçların satırı dondurulur — sonradan değiştirilmez). |
| 3 | `derin` | `scripts/derin_tahmin.py --tarih D` | Her maçın ana tercihi takım geçmişiyle (yarı skorları, H2H, Avrupa/rotasyon, eksikler) sınanır; ⚠ çıkan aday düşer. |
| 4 | `kupon` | `scripts/kupon_kur.py --hedef H --mod banko` | `nesine_kupon.py` banko modu + `quantfoot.coupons.coupon_rules` süzgeci + bacak bacak derin araştırma; temiz kupon yoksa kupon **yok**. `kuponlar.csv` yazılır. |
| 5 | `denetim` | (aynı betikte) | `kuponlar.csv` §3 kurallarına göre yeniden denetlenir → `kupon_denetim.md`. İhlal varsa çıkış kodu 3: o kupon önerilmez. |

**Süre ve kota (22 Kas canlı deneme, 476 maçlık bülten):** bülten ≈ 3,5 dk, tahmin ≈ 3,5 dk, derin araştırma ≈ 19 dk
(bahis aileleri + 20.000'lik simülasyon dahil), kupon ≈ 4 dk/tur. API-Football yalnız maç öncesi kullanılır, canlı
takipte asla; her istek `quantfoot.data.api_budget` bütçesinden düşer (`API_FOOTBALL_MAX_REQ`, varsayılan 60/gün;
sayaç `data/cache/api_football/butce_<gün>.json`), günün oranları 3 saat önbellekte tutulur. Bir tam çalıştırma ≈ 9 istek.
Banko kurallarına uyan bacak yoksa kupon **çıkmaz** — bu doğru sonuçtur; sabah keskin referanslar tazelenince yeniden dene.

Varsayılan hedef 2,5 (5 bacak × ~1,21–1,25). Daha yüksek hedef banko kurallarıyla kurulamıyorsa bunu kullanıcıya
açıkça söyle; kuralları gevşeterek hedefe ulaşma.

### Tüm futbol bahis aileleri

- Her başlamamış maçta Nesine’nin açık tuttuğu bütün aileleri ve seçimleri tara. Maç sonucu, gol pazarları, yarılar, özel
  pazarlar ve kombineler aynı araştırma kapsamına girer. Aile başına aday sınırı yoktur.
- Doğrulanmış fiyatı olan seçimleri kaynak, kalibre olasılık, Nesine oranı ve beklenen değerle karşılaştır. Araştırma eşiğini
  geçen seçimleri iki takımın geçmişiyle sınamaya çalış. Fiyatı ya da pazar eşlemesi bulunmayan seçenekleri gerekçesiyle yaz.
- Her maç özetinde farklı ailelerden en yüksek beş kalibre olasılığı göster. Önce her ailede en yüksek olasılıklı
  seçimi bul, sonra aileleri olasılığa göre sırala. Beşten az aile fiyatlandıysa eldeki aileleri göster. Tam aile
  tablosunda diğer olasılıklar da görünür. Kupon uygunluğu kendi denetiminde belirlenir.
- Varsayılan kupon taraması doğrudan fiyatları ve mevcut model, değer ve güven filtrelerini geçen türetilmiş fiyatları
  değerlendirir. Kupon önerisine yalnız seçilen modun kurallarını ve son canlı denetimi geçen en uygun bacaklar girer.
  Banko kuralları §3’teki gibidir. Uygun bacak bulunamazsa kupon çıkmaz. Bahis işlemi için kullanıcının açık onayı gerekir.

## 2. Olasılık kalibrasyonu (tahminin kendisi)

- Kaynak sırası: doğrudan keskin fiyat > keskin fiyattan türetilmiş pazar > model. Doğrudan fiyatlı seçimler
  21 Kasım'da neredeyse birebir tuttu; türetilmiş P'ler %50'ye doğru 0,10 büzülür, "diğer" lig katmanında +0,10
  (PR #5, `src/quantfoot/settings.py`).
- Aile düzeltmesi: `data/calibration/coupon_family_calibration.json` (aile ve olasılık bandı artıkları, büzülerek;
  pozitif sapma P'ye **eklenmez**).
- Beraberlik riski: banko MS 1 / MS 2 bacağında adil P(X) ≥ 0,27 → ret; ≥ 0,24 → uyarı, ÇŞ/handikap düşün
  (`strategy/banko_guard.py`).
- Kendi olasılığın her zaman `olasilik` sütununa 0–1 arası yazılır; "garanti", "%90 kesin" gibi ifadeler yok.

## 3. Kupon kuralları (banko — varsayılan ve zorunlu)

| Kural | Değer |
|---|---|
| Bacak olasılığı | **düzeltilmiş P ≥ 0,70** (`coupon_rules.MIN_CALIBRATED_P`); eski %65 tabanı kupon için geçersiz |
| Bacak oranı | Nesine ≥ 1,20, ≤ 1,80 |
| Bacak sayısı | 5 (gerekçeliyse 6); 1–2 bacaklı düşük oranlı kupon yok |
| Maç | Bir kuponda aynı maçtan tek bacak; aynı saat/aynı ligde yığılma varsa uyar |
| İzinli aileler | İlk yarı (İY 0,5/1,5 Alt-Üst …), maç sonu Alt/Üst, Yarı özel, Maç sonucu (yalnız 1/2 + beraberlik süzgeci), yasak parça içermeyen Kombine, 2Y KG **Yok**. Liste veriden gelir (`family_allowed`); yeni denetimle güncellenir. |
| Yasak | Beraberlik bacağı (MS 0, İY 0, skor 0-0 …), Karşılıklı gol (KG Var/Yok), "iki yarıda da KG var", İlk gol, Ev sahibi / Deplasman gol sayısı, şu an Çifte şans ve Handikap (21 Kas: banko seçimlerinde −10 / −18 puan) |
| Piyango yok | Skor, İY/MS, "+6 gol" gibi kuyruk bacakları, 100+ oranlı kuponlar banko kuponuna girmez. Yalnız kullanıcı açıkça "risk"/"yüksek oran" isterse `--mod risk` ve dürüst tutma olasılığıyla. |
| Tekrar yok | Aynı tercih iki kupona konmaz (21 Kas: tek zayıf bacak birden çok kuponu birlikte yaktı). |
| Şeffaflık | Her kuponda toplam oran ve toplam tutma olasılığı (= düzeltilmiş P'lerin çarpımı) yazılır. 5 × 0,70 ≈ %17: kullanıcıya bunu söyle. |
| Para | Hiçbir yapay zekâ kullanıcı açıkça onaylamadan bahis oynamaz, para yatırmaz/çekmez, kupon bozdurmaz. Oynamadan önce oranlar yeniden kontrol edilir. |

Kod karşılığı: `src/quantfoot/coupons/coupon_rules.py` (`leg_decision`, `build_rules_coupon`), `scripts/nesine_kupon.py`
(`apply_coupon_rules_to_pools`, banko modunda), `scripts/gunluk_tahmin.py` (`audit_coupons`).

## 4. Dürüst notlama

- Notu **sen vermezsin**: ertesi gün `python scripts/gun_degerlendirme.py --tarih <gün>` bütün yapay zekâları Nesine
  sonuç akışıyla (aynı Nesine kodu) puanlar → `degerlendirme/<gün>.md/.json`. Kendi "x/y tuttu" raporun yalnız bu
  çıktıdan alıntıdır. (21 Kas: bir yapay zekâ 20 Kasım için 56/103 demiş, gerçek 53/103; tutmayan bacağı tuttu yazmış.)
- Rapor: verdiğin ortalama P ile gerçekleşen oran yan yana; fark −2 puandan kötü ise o aileyi kupondan çıkar.
- Tek günlük örnek küçüktür; kalibrasyon dosyaları büzülerek güncellenir, tek günle kural tersine çevrilmez.

## 5. Çıktı biçimi ve klasör

`tahminler/<QUANTFOOT_AI>/<YYYY-AA-GG>/` (yalnız kendi klasörün; ayrıntılı sütunlar: [tahminler/README.md](../tahminler/README.md)):

| Dosya | Zorunlu sütunlar (İngilizce karşılık) |
|---|---|
| `mac_tahminleri.csv` | `tarih, saat, lig, mac, nesine_kodu` (code), `olasilik_1, olasilik_X, olasilik_2`, `beklenen_gol_ev, beklenen_gol_dep, en_olasi_skor`, `ana_secim_pazar` (market), `ana_secim` (selection), `nesine_oran` (odds), `olasilik` (p), `fiyat_kaynagi, guven, not`, `secim_adi` (settlement name — doldur), `en_yuksek_5_olasilik` (beş farklı ailenin maç özeti) |
| `kuponlar.csv` | `tarih, kupon_turu, kupon, kupon_no, kupon_toplam_oran, kupon_tutma_olasiligi, saat, mac, nesine_kodu` (code), `pazar` (market), `secim` (selection), `nesine_oran` (odds), `olasilik` (p), `secim_adi` |
| `kupon_denetim.md` | §3 denetimi (hat yazar) |

UTF-8, virgül ayraç, ondalık nokta, olasılık 0–1. `secim_adi` boş kalırsa takım golü, yarı KG, kombine pazarlar
notlanamaz. Ortak alanlara (`reports/`, `docs/data/`) tahmin yazılmaz.

## 6. Dersler (21 Kasım 2026 denetimleri — tek gün, küçük örnek)

**Aile kalibrasyonu (Grok Bot, 2.924 bitmiş tahmin; verilen % → gerçekleşen %):**

| Aile | n | Verilen | Gerçek | Fark | Kupon |
|---|---:|---:|---:|---:|---|
| 2Y KG (çoğu "Yok") | 94 | 64,5 | 72,3 | +7,8 | Yalnız 2Y KG Yok |
| Yarı özel | 139 | 63,5 | 66,9 | +3,4 | İzinli |
| Maç sonucu | 117 | 62,2 | 63,2 | +1,1 | İzinli (beraberlik süzgeci) |
| İlk yarı | 588 | 62,1 | 62,6 | +0,5 | İzinli |
| Alt/Üst | 330 | 61,5 | 60,6 | −0,9 | İzinli |
| Çifte şans | 224 | 62,3 | 60,3 | −2,0 | Şimdilik yasak |
| Handikap | 168 | 61,1 | 58,9 | −2,1 | Şimdilik yasak |
| Ev sahibi golleri | 427 | 61,5 | 57,8 | −3,6 | Yasak |
| Karşılıklı gol | 229 | 61,6 | 56,8 | −4,8 | Yasak |
| İlk gol | 36 | 61,3 | 52,8 | −8,5 | Yasak |

- P ≥ 0,60 bantlarında 1,5–4 puan fazla iyimseriz (%70–75 dedik, %67 tuttu) → bacak tabanı 0,70 ve band düzeltmesi.
- "İki yarıda da KG var": 15 bitmiş adaydan 1'i tuttu (model zaten %10–17 diyordu) → aday listesinde bile gösterme.
- Oynanan kuponlar: 32 kesinleşen bacağın 15'i tuttu (%47) — bacaklara ortalama yalnız %53 P verilmişti. Kuponları
  beraberlik bacakları, ~%55'lik MS tahminleri, Alt/Üst ve kombine/KG bacakları yaktı. Sorun tahmin değil, bacak seçimi.
- 1X2 oranı → sonuç (418 maç): favori %52,2 kazandı (oranlar %49,8 ima ediyordu); favori 1,50 altı 135 maçın 47'sinde
  favori kazanamadı (31 beraberlik). Beraberlik oranı ≤ 3,10 iken beraberlik ima edilenden az geldi (%24,5 / %28,5).
  İlk yarı beraberliği yaygın (%42; dengeli maçlarda %60).
- Diğer yapay zekâlar (Nesine sonuçlarıyla yeniden notlandı): ChatGPT 21 Kas %62,0 (verdiği %62,7 — en gerçekçi);
  Gemini 20 Kas %51,5 (verdiği %62,6; öz-rapor şişik); Claude 18 Kas %69,8, 19 Kas %53,4 (verdiği %63,1).
  Gemini/Claude MS tahminleri ~%31 tuttu (verilen ~%62); KG %46–47. Aynı zayıf bacak birden çok kupona girdi;
  900–300.000 oranlı piyango kuponları hiç tutmadı. Tutan tek örnek: Gemini'nin 21 Kas gecesi 4 bacaklı, kısa oranlı
  Alt/Üst + ÇŞ kuponu (2,62).

## 7. Yeni ders eklemek

Yeni bir günün denetimi bu tabloyu değiştiriyorsa: kalibrasyon JSON'unu güncelle, testleri çalıştır, bu belgeyi ve
gerekirse `coupon_rules.py`'yi aynı PR'da değiştir. Tüm yapay zekâ giriş dosyaları (AGENTS.md, CLAUDE.md, GEMINI.md)
buraya işaret eder; kuralları orada çoğaltma.
