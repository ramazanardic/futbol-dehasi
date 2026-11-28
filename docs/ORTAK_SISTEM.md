# Ortak sistem (v4) — her yapay zekâ için tek bağlayıcı yöntem

Bu depoya bağlanan **her** yapay zekâ (**Claude, Gemini, Antigravity, ChatGPT/Codex, Grok Bot**) tahmin, araştırma,
kupon, kasa koruma, denetim ve öz-geliştirmeyi **birebir bu belgedeki ortak hatla** yürütür. Amaç tek: herkes aynı
ortak yerden, aynı en güncel sistemle, eşit veri erişimiyle çalışsın; kuponlar daha az yatsın; kasa korunsun; notlar
dürüst olsun.

- Bu belge 23 Kasım 2026'da v4 kasa koruma yükseltmesiyle (21 Kasım 2.924 tahmin + 22 Kasım 439 bitmiş maç / 1.864
  kupon-bölgesi seçimi denetimleri) güncellendi.
- Çelişki olursa bu belge eski README / rapor metinlerinden önce gelir; klasör gizliliği kuralı
  ([AGENTS.md](../AGENTS.md)) her şeyden önce gelir.
- Tüm AI giriş dosyaları (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`) birebir aynı temel
  sözleşmeyi taşır ve `tests/test_common_ai_parity.py` tarafından GitHub CI'da otomatik denetlenir.

## 0. Bağlanınca ilk yapılacaklar (tüm 5 yapay zekâ için birebir aynı)

1. `AGENTS.md`'yi ve bu belgeyi oku. Kendi klasörünü bil: `QUANTFOOT_AI` = `claudetahmin` · `geminitahmin` ·
   `antigravitytahmin` · `chatgbttahmin` · `grokbottahmin`. Başka bir yapay zekânın klasörünü açma.
2. `git pull` → `pip install -e .` (gerekirse) → `pytest -q` yeşil olmalı.
3. Kullanıcı günlük tahmin/kupon isterse **tek ortak komut**:

   ```bash
   QUANTFOOT_AI=<klasörün> python scripts/gunluk_tahmin.py --tarih <YYYY-AA-GG>
   # Windows: $env:QUANTFOOT_AI="<klasörün>"; .\.venv\Scripts\python.exe scripts\gunluk_tahmin.py --tarih <gün>
   ```

4. Kullanıcı ertesi gün öz-denetim isterse **tek ortak komut**:

   ```bash
   QUANTFOOT_AI=<klasörün> python scripts/oz_gelistirme.py
   ```

5. Kullanıcı ertesi gün tüm yapay zekâların ortak karnesini isterse **tek ortak komut**:

   ```bash
   python scripts/gun_degerlendirme.py --tarih <YYYY-AA-GG>
   ```

6. Sonucu kullanıcıya `mac_tahminleri.csv`, `kuponlar.csv`, `kupon_denetim.md` ve (varsa) `ekstrem_gol_analiz.md`'den
   aktar: her kupon için bacaklar, toplam oran, **toplam tutma olasılığı** ve çapraz portföy yoğunlaşması. Kendi
   kafandan, hattın dışında tahmin veya kupon uydurma.

## 1. Zorunlu ortak hat (sırası ve kuralları herkes için aynı)

`scripts/gunluk_tahmin.py` aşağıdaki ortak betikleri her yapay zekâ için aynı ortam değişkenleriyle
(`PYTHONIOENCODING=utf-8`, `TZ=Europe/Istanbul`) sırayla çalıştırır (`--yalniz` / `--atla` ile tek adım, `--kuru` ile
yalnız komutları görürsün):

| # | Adım | Komut | Ne yapar |
|---|---|---|---|
| 1 | `bulten` | `scripts/nesine_global.py --date D` | Nesine bülteni + keskin referanslar (Pinnacle, Smarkets, Matchbook, OddsMath/BetInAsia; ESPN en zayıf). Marj güç yöntemiyle kaldırılır, gol oranları referansa uydurulur (Dixon-Coles), bütün Nesine pazarları fiyatlanır, arşiv Platt (`market_calibration`) + kuyruk düzeltmeleri (`market_tail_calibration.json`, `market_reliability.py`) uygulanır. Nesine oranından adil fiyat türetilmez. |
| 2 | `tahmin` | `scripts/ai_tahmin.py --tarih D --hazir-bulten` | `mac_tahminleri.csv` (ortak biçim; başlamış maçların satırı dondurulur — sonradan değiştirilmez). |
| 3 | `derin` | `scripts/derin_tahmin.py --tarih D` + `scripts/ekstrem_gol_analiz.py --tarih D` | Her maçın ana tercihi takım geçmişi (ev/dep ayrı ayrı), H2H, Avrupa/rotasyon, eksikler ve 20.000'lik kalibre simülasyonla sınanır (`⚠` düşer); paralelinde `6+ Gol` ve `İki Yarıda KG Var` uzman taraması (`ekstrem_gol_analiz.md/.json`) üretilir. |
| 4 | `kupon` | `scripts/kupon_kur.py --hedef H --mod banko` | `nesine_kupon.py` banko modu + `coupon_rules` + `market_diagnosis` v3 kalkanları + bacak bacak derin araştırma; temiz kupon yoksa kupon **yok**. `kuponlar.csv` yazılır. |
| 5 | `denetim` | (aynı betikte `run_audit`) | `kuponlar.csv` §3 kurallarına ve `PortfolioExposureGuard` çapraz yoğunlaşma bekçisine göre yeniden denetlenir → `kupon_denetim.md`. İhlal varsa çıkış kodu 3: o kupon önerilmez. |

**Eşit veri erişimi:** Tüm 5 yapay zekâ aynı veri kaynaklarına (Nesine bülteni, `data/global_odds/latest/`, ESPN,
API-Football ortak kota `quantfoot.data.api_budget`, FotMob `quantfoot.data.fotmob` — tüm geçerli `QUANTFOOT_AI` için
varsayılan eşit açık — ve ortak kalibrasyon dosyaları) birebir eşit erişir.

**Süre ve kota (22 Kas canlı deneme, 476 maçlık bülten):** bülten ≈ 3,5 dk, tahmin ≈ 3,5 dk, derin araştırma ≈ 19 dk
(bahis aileleri + 20.000'lik simülasyon + ekstrem gol taraması dahil), kupon ≈ 4 dk/tur. API-Football yalnız maç öncesi
kullanılır, canlı takipte asla; her istek `quantfoot.data.api_budget` bütçesinden düşer (`API_FOOTBALL_MAX_REQ`,
varsayılan 60/gün). Banko kurallarına uyan bacak yoksa kupon **çıkmaz** — bu doğru sonuçtur; sabah keskin referanslar
tazelenince yeniden dene.

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
  Banko kuralları §3’teki ve [KURALLAR.md](../KURALLAR.md)’deki gibidir: **2–5 maç (en çok 6), toplam oran < 20**. Kurallara uyan kupon yoksa **dürüst ret** verilir; kural gevşetilmez. Bahis işlemi için kullanıcının açık onayı gerekir.

## 2. Olasılık kalibrasyonu ve v3 kök-neden kalkanları

- **Kaynak sırası:** doğrudan keskin fiyat > keskin fiyattan türetilmiş pazar > model. Türetilmiş P'ler %50'ye doğru
  0,10 büzülür, "diğer" lig katmanında +0,10 (`src/quantfoot/settings.py`).
- **Aile ve patern kalibrasyonu:** `data/calibration/coupon_family_calibration.json` (James-Stein büzüştürmeli;
  pozitif sapma P'ye **eklenmez**; `^İY ÇŞ 12$` paterni `^İY ÇŞ` paterninden önce eşleşir).
- **v4 Teşhis & Kasa Koruma Kalkanları (`src/quantfoot/markets/market_diagnosis.py`, `scripts/nesine_kupon.py`):**
  - `İY ÇŞ 12` banko kuponlarda **koşulsuz yasak** (22 Kas: genel 48/99 = %48,5, en ekstrem dilim bile 8/15 = %53,3).
  - `İY 1.5 Alt` sıkı tempo sınırı: `mu_tot ≤ 2,65`, `min_mu < 1,00`, `steam < 5,0p`, kaleci sağlam (22 Kas: geçenler %66,7, dışarısı %56,0).
  - `İY 1/2` ve `2Y 1/2` 45 dk yarı-sonucu varyans kalkanı (22 Kas: `2Y 1 P≥%65` 2/5 = %40,0).
  - Keskin borsa sert steam (`parse_steam_pp`) kalkanı artık `nesine_kupon.py` içine de doğrudan `flags` ile bağlı: `≥6,0p` sert steam'de `MS 1/2` (22 Kas: %38,5 vs steam yokken %71,4), `≥5,0p` sert steam'de `İY 1.5 Alt` kupon dışı.
  - `Dep İY 0.5 Üst` (9/24 = %37,5) ve `İY Çift` / Tek-Çift parite gürültüsü (26/58 = %44,8) engelli.
  - `DEĞİL(Ev/Dep İki Yarıda Gol)` eşiği `mu ≥ 1,45` ile sıkılaştırıldı (22 Kas: `1,50–1,60` 0/3 = %0,0, `≥1,60` %56,7).
  - **Ağır Nesine Marjı Freni (`BANKO_DEFAULT_MIN_EV = -0,115`):** 22 Kas’ta `EV < −%14` bacaklar −%17,3 tekil ROI (5’li kombinede −%61 beklenen kayıp) üretirken `EV ≥ −%10` bacaklar %85 isabet / +%20,8 ROI verdi. Banko modunda `mac_limit = 1` (aynı maç iki kupona girmez) ve her 4–7 maçlık banko kupona otomatik **100 TL Tek-Bacak Sigorta (`Sistem n-1, n`)** karşılaştırması eklenir.
  - **Kasa Koruma Planlayıcı (`scripts/kasa_koruma.py` + `build_capital_shield_plan`):** 5–6’lı ağır marjlı kombine yerine 3 maçlı (MBS uyumlu), `EV ≥ −%10`, sıfır ortak maçlı, kupon başı maks %3 / günlük maks %10 kasa riskli koruma planı üretir.
  - Tek-taraf geçmiş maskelemesi engeli: iki takımın ayrı ayrı geçmişinden zayıf olanı `<%45` ise reddedilir.
  - `İY KG Yok & 2Y KG Yok` düşük toplamlı (`mu_tot ≤ 2,65`) keskin maçlarda rehabilite edilir (19/26 = %73,1).
- **Beraberlik riski:** banko MS 1 / MS 2 bacağında adil P(X) ≥ 0,27 → ret; ≥ 0,24 → uyarı (`strategy/banko_guard.py`).
- **Dürüstlük:** Kendi olasılığın her zaman `olasilik` sütununa 0–1 arası yazılır; "garanti", "%90 kesin" gibi ifadeler yok.

## 3. Kupon kuralları (banko — varsayılan ve zorunlu)

| Kural | Değer |
|---|---|
| Bacak olasılığı | **düzeltilmiş P ≥ 0,70** (`coupon_rules.MIN_CALIBRATED_P`); eski %65 tabanı kupon için geçersiz |
| Bacak oranı | Nesine ≥ 1,20, ≤ 1,80 |
| Bacak sayısı | **2–5 bacak** (`BANKO_MIN_LEGS = 2`, `BANKO_MAX_LEGS = 5`; gerekçeliyse açıkça en çok 6 = `BANKO_HARD_MAX_LEGS`). Tek maçlık banko kupon yok. Kurallara uyan 2 bacak bile yoksa kupon **yok** (dürüst ret, kural gevşetilmez). |
| Toplam oran | Banko kupon toplam oranı **< 20** (`BANKO_MAX_TOTAL_ODDS`); varsayılan olarak 20+ oranlı kupon üretilmez |
| Maç | Bir kuponda aynı maçtan tek bacak; birden çok kuponda çapraz yoğunlaşma `PortfolioExposureGuard` ile ölçülür |
| İzinli aileler | İlk yarı (İY 0,5/1,5 Alt-Üst …; İY ÇŞ 12 ve İY Çift hariç), maç sonu Alt/Üst, Yarı özel, Maç sonucu (yalnız 1/2 + beraberlik & sert steam süzgeci), yasak parça içermeyen Kombine. 2Y KG Yok dahil hiçbir KG bacağı girmez (28 Kas kural onarımı). Liste veriden gelir (`family_allowed`). |
| Yasak | Beraberlik bacağı (MS 0, İY 0, skor 0-0 …), Karşılıklı gol (KG Var/Yok), "iki yarıda da KG var", İlk gol, Ev sahibi / Deplasman gol sayısı ve takım "iki yarıda gol atar/atamaz", İY/MS, İY/2Y, skor, Tek/Çift (İY Çift dahil), şu an Çifte şans ve Handikap |
| Piyango yok | Skor, İY/MS, "+6 gol" gibi kuyruk bacakları, 100+ oranlı kuponlar banko kuponuna girmez. |
| Tekrar yok | Aynı tercih iki kupona konmaz (`PortfolioExposureGuard` + `audit_coupons`). |
| Şeffaflık | Her kuponda toplam oran, toplam tutma olasılığı (= düzeltilmiş P'lerin çarpımı) ve portföy yoğunlaşma skoru yazılır. |
| Para | Hiçbir yapay zekâ kullanıcı açıkça onaylamadan bahis oynamaz, para yatırmaz/çekmez, kupon bozdurmaz. Oynamadan önce oranlar yeniden kontrol edilir. |

### 3.1. Kullanıcı açıkça istediğinde ortak özel modüller

Kullanıcı **açıkça** tek-bacak sigortalı sistem kuponu, yüksek oranlı `2/1–1/2` sistem kuponu veya `6+ Gol / İki Yarıda KG Var`
istediğinde her yapay zekâ kendi kafasından hesap yapmak yerine **aynı ortak modülleri** kullanır:

- **Sistem kuponu optimizeri (`src/quantfoot/coupons/system_builder.py`):** `evaluate_system` ve `optimize_system`
  (`mode="banko_sigorta"` ile 4/5+5/5 veya 5/6+6/6 tek-bacak sigortası; `mode="yuksek_oran"` ile bütçe ve MBS uyumlu
  yüksek oranlı sistemler; kesin Poisson-Binomial `P(≥k)`, `P(kâr)`, min/max TL ödeme tablosu).
- **Ekstrem gol tarayıcısı (`src/quantfoot/markets/extreme_goals.py` + `scripts/ekstrem_gol_analiz.py`):** Overdispersed
  kuyruk olasılıkları, `Sim >> Mkt` şişkin-form tuzağı freni, savunma krizi desteği, %64–70+ güvenli gol merdiveni ve
  `build_extreme_system` 100 TL sistem önerisi.

Kod karşılığı: `src/quantfoot/coupons/coupon_rules.py`, `src/quantfoot/coupons/system_builder.py`,
`src/quantfoot/markets/market_diagnosis.py`, `src/quantfoot/markets/extreme_goals.py`, `scripts/nesine_kupon.py`,
`scripts/gunluk_tahmin.py`.

## 4. Dürüst notlama ve çok-günlük öz-geliştirme

- **Ortak karne (notu kendin vermezsin):** ertesi gün `python scripts/gun_degerlendirme.py --tarih <gün>` bütün yapay
  zekâları Nesine sonuç akışıyla (aynı Nesine kodu) puanlar → `degerlendirme/<gün>.md/.json`. Kendi "x/y tuttu" raporun
  yalnız bu çıktıdan alıntıdır.
- **Kendi çok-günlük öz-geliştirme denetimin:** `QUANTFOOT_AI=<klasörün> python scripts/oz_gelistirme.py`
  (`src/quantfoot/evaluation/self_improve.py`) yalnızca kendi klasöründeki bitmiş günleri okur; alt-pazar bazında
  James-Stein büzüştürülmüş artık, steam kırılımı, `market_diagnosis` v3 ayrıştırması, altın havuzlar ve zehirli
  alarmları `tahminler/<QUANTFOOT_AI>/oz_gelistirme_raporu.md/.json` olarak üretir.
- Tek günlük örnek küçüktür; kalibrasyon dosyaları büzülerek güncellenir, tek günle kural tersine çevrilmez.

## 5. Çıktı biçimi ve klasör

`tahminler/<QUANTFOOT_AI>/<YYYY-AA-GG>/` (yalnız kendi klasörün; ayrıntılı sütunlar: [tahminler/README.md](../tahminler/README.md)):

| Dosya | Zorunlu sütunlar (İngilizce karşılık) |
|---|---|
| `mac_tahminleri.csv` | `tarih, saat, lig, mac, nesine_kodu` (code), `olasilik_1, olasilik_X, olasilik_2`, `beklenen_gol_ev, beklenen_gol_dep, en_olasi_skor`, `ana_secim_pazar` (market), `ana_secim` (selection), `nesine_oran` (odds), `olasilik` (p), `fiyat_kaynagi, guven, not`, `secim_adi` (settlement name — doldur), `en_yuksek_5_olasilik` (beş farklı ailenin maç özeti) |
| `kuponlar.csv` | `tarih, kupon_turu, kupon, kupon_no, kupon_toplam_oran, kupon_tutma_olasiligi, saat, mac, nesine_kodu` (code), `pazar` (market), `secim` (selection), `nesine_oran` (odds), `olasilik` (p), `secim_adi` |
| `kupon_denetim.md` | §3 bacak kuralları + `PortfolioExposureGuard` çapraz yoğunlaşma denetimi (hat yazar) |
| `ekstrem_gol_analiz.md/.json` | 6+ Gol / İki Yarıda KG Var uzman taraması + güvenli merdiven (hat yazar) |

UTF-8, virgül ayraç, ondalık nokta, olasılık 0–1. `secim_adi` boş kalırsa takım golü, yarı KG, kombine pazarlar
notlanamaz. Ortak alanlara (`reports/`, `docs/data/`) tahmin yazılmaz.

## 6. Dersler (21–22 Kasım 2026 denetimleri)

### 6.1. 21 Kasım (Grok Bot, 2.924 bitmiş tahmin)

| Aile | n | Verilen | Gerçek | Fark | Kupon |
|---|---:|---:|---:|---:|---|
| 2Y KG (çoğu "Yok") | 94 | 64,5 | 72,3 | +7,8 | Yalnız 2Y KG Yok |
| Yarı özel | 139 | 63,5 | 66,9 | +3,4 | İzinli |
| Maç sonucu | 117 | 62,2 | 63,2 | +1,1 | İzinli (beraberlik + steam süzgeci) |
| İlk yarı | 588 | 62,1 | 62,6 | +0,5 | İzinli (İY ÇŞ 12 ve İY Çift hariç) |
| Alt/Üst | 330 | 61,5 | 60,6 | −0,9 | İzinli (sert steam + kaleci süzgeci) |
| Çifte şans | 224 | 62,3 | 60,3 | −2,0 | Şimdilik yasak |
| Handikap | 168 | 61,1 | 58,9 | −2,1 | Şimdilik yasak |
| Ev sahibi golleri | 427 | 61,5 | 57,8 | −3,6 | Yasak |
| Karşılıklı gol | 229 | 61,6 | 56,8 | −4,8 | Yasak |
| İlk gol | 36 | 61,3 | 52,8 | −8,5 | Yasak |

### 6.2. 22 Kasım v3 Denetimi (428 bitmiş maç · 1.808 kupon-bölgesi seçimi)

- **`İY ÇŞ 12` gizli tuzağı:** 48/99 (%48,5 vs %62,9 = −14,4p) → özel kalibrasyon paterni ve teşhis engeli eklendi.
- **Keskin borsa sert steam (≥6p):** `MS 1/2` steam yokken 40/56 (%71,4, +4,8p), sert steam'de 5/13 (%38,5, −27,3p);
  `ALT` sert steam'de 9/17 (%52,9, −10,5p) → `parse_steam_pp` kalkanı tüm AI'lar için aktif edildi.
- **Çapraz kupon korelasyonu & tek-bacak fireleri:** Aynı tek bacak (Getafe İY 1.5 Alt) 3 kuponu birlikte gömdü; 5
  tek-bacak kuponda düz kombine 0/500 TL iken `Sistem (n-1, n)` 272,65/500 TL (%54,5 kurtarma) sağladı →
  `system_builder.py` ve `PortfolioExposureGuard` ortak hatta bağlandı.
- **Şişkin form tuzağı (`Sim >> Mkt`):** Bağımsız form simülasyonu piyasadan +0,60 xG fazla şiştiğinde gerçek maç 2,00
  golde kaldı (%0 6+ Gol, %0 2Y KG) → `extreme_goals.py` v3 frenine eklendi.

### 6.3. 26 Kasım v8 Ortak Çekirdek Yükseltmeleri (ayrıntılar: `docs/research/v8_kapsamli_gelistirme_2026_11.md`)

- **Kaito Goto & Ensemble Devigging (`src/quantfoot/markets/devig.py`):** Kapalı form standart-hata marj kaldırma
  (`method="goto"`) ve Power+Shin+Goto topluluğu (`method="ensemble"`) eklendi; Betfair Exchange kapanış 1X2
  (`n = 2.449`) üzerinde `goto` en düşük Log-Loss (`0.981108`) ve Brier (`0.584189`) skorunu verdi.
- **Asya Handikabı Kesin Sıfır-EV Fiyatlama & Minimum-KL Raking (`tail_goals.py`, `scripts/nesine_global.py`):**
  Tam/yarım/çeyrek Asya Handikabı (`ref["ah"]`) artık `price_event` içinde hem gol oranı uydurmasına hem de
  `rake_score_matrix_to_markets(..., ah_lines=...)` I-projeksiyonuna bağlı (`season_2627`, `n = 795`: `Hnd(-1) 1`
  Log-Loss `−0.00117`, `KG Var` `−0.00065`).
- **Genişletilmiş Keskin Kaynak & Türev Kotasyonlar (`sharp_sources.py`, `api_football.py`, `.env.example`):**
  İsteğe bağlı `THE_ODDS_API_KEY` ile canlı Pinnacle/Betfair/Matchbook/Smarkets çekimi + sıfır ek kotalı
  API-Football BTTS, 1.5/2.5/3.5/4.5 Alt/Üst, Asya Handikabı ve 1Y doğrudan kotasyon ayrıştırması.
- **T-60 Kadro Şoku, Üstel NPxG, Hakem ve Motivasyon (`lineup_xg.py`, `market_diagnosis.py`):**
  Çift-sayımı önleyen `news_fresher_than_odds` disiplini (±%12 sınırlı `Δμ`), 126 hakemlik kart/tempo profili ve
  `dead_rubber` / sert hakem teşhis sinyalleri.
- **CLV Anlamlılık, Brier MCB/DSC, CORP İzotonik Güvenilirlik ve Güvenli Kalibrasyon Önericisi (`clv_tracker.py`, `scripts/clv_analiz.py`, `scripts/v8_dogrulama.py`):**
  Student-t + bootstrap %95 GA CLV ölçümü, Murphy/Dimitriadis `Brier = MCB − DSC + UNC` ve kutusuz $O(n)$ PAVA
  **CORP** ayrıştırması (`tipsaudit`, `n = 7.349`: `ensemble` `CORP MCB = 0.001447` vs `multiplicative` `0.001765`),
  log-opinion-pool ağırlık testi ve James-Stein negatif-artık kalibrasyon önerisi.
- **Keskin–Yumuşak (Sharp-vs-Soft) Gecikme & Steam Yönü Motoru (`line_movement.py`, `scripts/clv_analiz.py --steam`):**
  `tipsaudit.csv` (`n = 7.348`) üzerinde açılış Pinnacle vs en iyi yumuşak büro `EV ≥ %2` adaylarında steam uyumlu
  (`≥ +2p`, `n = 469`) bacaklar **+%19,18 ROI** (`t = +2,85`, `p = 0,0023`), steam karşıtı (`≤ −2p`, `n = 891`)
  bacaklar **−%10,28 ROI** üretir.
- **Uyarlamalı Drawdown-Frenli Kelly & Canlı Bağlam Kalkanları (`strategy/kelly.py`, `nesine_global.py`, `nesine_kupon.py`, `derin_tahmin.py`, `self_improve.py` / `kasa_koruma.py`):**
  `adaptive_kelly_stake` (%5 günlük, %12 haftalık, %25 drawdown devre kesicileri; 400-yol MC testinde %95-dilim maks.
  düşüşü `%33,5 → %17,8`, `DD ≥ %25` ihlalini `%17,5 → %0,0` indirir) ve `motivation_regime`/`dead_rubber` ile
  `referee_card_zscore` sinyallerinin tüm canlı tahmin/kupon/kasa-koruma hatlarına uçtan uca bağlanması.
- **Çoklu-Büro Hassasiyet Konsensüsü, Canlı Hawkes/Maia Motoru ve Otomatik Nesine CLV Defteri (`markets/consensus.py`, `markets/inplay.py`, `evaluation/clv_ledger.py`, `scripts/clv_defteri.py`):**
  Ters-marj ağırlıklı log-havuz konsensüsü + bürolar arası sapma (`prob_std`, `KL`) → Baker–McHale Kelly bağlantısı,
  1X2↔ÇŞ↔DNB sentetik tutarlılık denetimi, canlıda 2+ fark aciliyeti + Hawkes gol ivmesi + `Sıradaki Gol` fiyatlaması ve
  yapay zekâ başına izole otomatik CLV defteri. Tüm dünya literatürü haritası: `docs/research/dunya_futbol_bahis_algoritmalari_2026.md`.

## 7. Yeni ders eklemek

Yeni bir günün denetimi bu tabloyu değiştiriyorsa: kalibrasyon JSON'unu güncelle, testleri çalıştır (`pytest -q`,
`tests/test_common_ai_parity.py` dahil), bu belgeyi ve gerekirse `coupon_rules.py` / `market_diagnosis.py`'yi aynı PR'da
değiştir. Tüm yapay zekâ giriş dosyaları (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`)
buraya işaret eder ve birebir eşgüdümlü kalır.
