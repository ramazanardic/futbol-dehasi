# Grok Bot işletim rehberi — QuantFoot (futbol-dehasi)

Bu kutu (Linux) üzerinde QuantFoot v8.x kurulumu ve günlük komutlar. Windows örneklerindeki `.\.venv\Scripts\python.exe` / `quantfoot.exe` / `pytest.exe` burada `.venv/bin/python`, `.venv/bin/quantfoot`, `.venv/bin/pytest` olur.

**Kendi alanımız:** `tahminler/grokbottahmin/` (`QUANTFOOT_AI=grokbottahmin`). Başka bir yapay zekânın klasörü (`claudetahmin`, `geminitahmin`, `antigravitytahmin`, `chatgbttahmin`) ve `tahminler/ortak_arena` çıktıları açılmaz, okunmaz, listelenmez. Tahminler GitHub'a gönderilmez. Bahis oynanmaz, Telegram / dışarıya ileti gönderilmez, `git push` yapılmaz.

Kurulum tarihi: 21 Kasım 2026 (Europe/Istanbul).

---

## Ortam

```bash
cd /workspace/futbol-dehasi
source .venv/bin/activate          # veya doğrudan .venv/bin/python
export QUANTFOOT_AI=grokbottahmin
export PYTHONIOENCODING=utf-8
export TZ=Europe/Istanbul
```

- Python 3.13.5, sanal ortam: `/workspace/futbol-dehasi/.venv`
- Paket: `pip install -e .` (quantfoot 0.1.0, düzenlenebilir kurulum)
- İsteğe bağlı: `pip install 'quantfoot[soccerdata]'` — bu kutuda temiz kuruldu (soccerdata 2026.43.0)
- Test: `.venv/bin/pytest -q` → **1527 passed in 20.08s** (21 Kasım 2026)
- `.env` / `.secrets` yok; gizli anahtarlar tanımlı değil

Her komuttan önce `QUANTFOOT_AI=grokbottahmin` verilmezse kod varsayılan olarak `claudetahmin` klasörüne yazar — bunu yapmayın.

---

## Gizli anahtarlar (bu kutuda yok)

Kökteki git-dışı `.env` veya ortam değişkeni:

| Değişken | Ne için | Anahtarsız durum |
|---|---|---|
| `API_FOOTBALL_KEY` | `scripts/api_gecmis.py`, API-Football oran/sonuç (ücretsiz plan) | ESPN'in kapsamadığı takım geçmişi ve API-Football oranı çalışmaz. Uç nokta 403 verdi. |
| `ODDSPAPI_KEY` | İsteğe bağlı OddsPapi oranları | Devre dışı. Uç nokta anahtarsız 405 verdi. |
| `FC_API_KEY` | `scripts/footballcharts_gecmis.py` | Bu geçmiş kaynağı çalışmaz. Backend kökü 200 verdi; anahtar yine gerekir. |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | `scripts/notify_telegram.py` | Bildirim atlanır. Kullanıcı istemedikçe çalıştırılmamalı. |

Nesine, ESPN, OddsMath, FPL, Open-Meteo, openfootball, Wikipedia anahtarsızdır.

---

## Bu kutudan erişim (21 Kasım 2026, tek istek)

| Kaynak | Sonuç |
|---|---|
| Nesine bülten (`cdnbulten.nesine.com`) | 200, kullanılabilir |
| Nesine canlı skor (`ls.nesine.com`) | 200, kullanılabilir |
| ESPN (`site.api.espn.com`) | 200, kullanılabilir |
| OddsMath (`/api/v1/events-by-day.json?...`) | 200, kullanılabilir (kök `/api/v1` 404; kodun tam URL'si gerekir) |
| FPL, Open-Meteo, Wikipedia, openfootball, OpenLigaDB, football-charts backend | 200 |
| football-data.co.uk `fixtures.csv` | 200 — bu kutudan açık (Türkiye'den genelde kapalı olduğu için asıl çekim GitHub Actions'ta) |
| Smarkets ` /v3/events/` | 200 (kök `/v3` 404) |
| Transfermarkt (`transfermarkt.com.tr`) | HTTP 202, kısa/boş veya ara HTML; `nesine_global` **0/686** maç eşleştirdi — pratikte kullanılamıyor |
| Club Elo (`api.clubelo.com`) | Erişilemedi (HTTP 500 / SSL hatası). `data/global_odds/latest/clubelo.csv` yok |
| Matchbook deneme URL'si | 403 (yerel arşivde önceki Actions çekimi var) |
| API-Football / OddsPapi | Anahtar yok; 403 / 405 |

Yerel keskin oran anlığı: `data/global_odds/latest/` (son çekim 20 Kasım 2026 21:26:33 UTC = **21 Kasım 00:26:33 Europe/Istanbul**). `nesine_global` bunu **681 dakika eski** buldu. Kupon kuralı: 3 saatten eski global fiyat kullanılmaz. Yenilemek için (bu ajan otomatik çalıştırmaz; Actions `git push` yapar):

```bash
# Kullanıcı isterse, yurt dışı iş akışı:
gh workflow run global-odds.yml
# bittikten sonra:
git pull
```

Bu Linux kutusundan `scripts/fetch_global_odds.py` de denenebilir (football-data.co.uk ve Smarkets açık görünüyor) ama paylaşılan `data/global_odds/` yazar; uzaktan gönderilmemelidir. Club Elo yine de bu kutudan çekilemez (`elo_gorus.py --cek`).

---

## Günlük tahmin (ESPN, anahtarsız)

`scripts/daily.py` ESPN fikstür + canlı oranlarla fiyatlar; çıktı `tahminler/grokbottahmin/<tarih>/`.

```bash
cd /workspace/futbol-dehasi
export QUANTFOOT_AI=grokbottahmin PYTHONIOENCODING=utf-8 TZ=Europe/Istanbul

.venv/bin/python scripts/daily.py run --date 2026-11-21        # predict + coupons + report
.venv/bin/python scripts/daily.py snapshot --date 2026-11-21   # kapanış oranları (CLV)
.venv/bin/python scripts/daily.py results --date 2026-11-21    # İY / 90' skorları
.venv/bin/python scripts/daily.py verify --date 2026-11-21     # isabet, kupon, havuz, CLV
.venv/bin/python scripts/daily.py summary                      # tüm günler; reports/daily/summary.md (ortak alan)
```

`run` alt komutları ayrı da çalışır: `predict`, `coupons`, `report`.

**Duman testi (21 Kasım 2026, 11:42 Europe/Istanbul):** `daily.py run --date 2026-11-21` çıkış kodu 0, ~6,3 sn.

- 122 maç bulundu, 119 fiyatlandı, 3 atlandı; `fund_weight=0` (saf piyasa)
- Yazılanlar: `tahminler/grokbottahmin/2026-11-21/predictions.json`, `coupons.json`, `coupons.md`, `report.md`
- +%2 EV eşiğini geçen tekil yok; 3x / 5x / 10x kupon kurulmadı (gol beklentisi aynı büro oranına uydurulduğu için beklenen sonuç)

---

## Nesine analizi ve kupon (ana günlük akış)

Sıra: global anlık (gerekirse yenile) → Nesine analizi → (isteğe bağlı) derin araştırma / simülasyon → kupon.

```bash
export QUANTFOOT_AI=grokbottahmin PYTHONIOENCODING=utf-8 TZ=Europe/Istanbul

.venv/bin/python scripts/nesine_global.py --date 2026-11-21
# Transfermarkt bu kutuda işe yaramıyorsa:
.venv/bin/python scripts/nesine_global.py --date 2026-11-21 --no-tm

.venv/bin/python scripts/gunluk_analiz.py --tarih 2026-11-21
.venv/bin/python scripts/mac_dosyasi.py --tarih 2026-11-21          # veya --mac "Takım"
.venv/bin/python scripts/ai_tahmin.py --tarih 2026-11-21             # mac_tahminleri.csv biçimi
.venv/bin/python scripts/derin_tahmin.py --tarih 2026-11-21          # nesine_global sonrası; uzun sürebilir
.venv/bin/python scripts/derin_tahmin.py --tarih 2026-11-21 --saat 18:00-22:00
.venv/bin/python scripts/derin_arastirma.py --tarih 2026-11-21 --kuponlar
.venv/bin/python scripts/simulasyon.py --tarih 2026-11-21
.venv/bin/python scripts/bahis_aileleri.py --tarih 2026-11-21
.venv/bin/python scripts/elo_gorus.py                               # yerel clubelo.csv gerekir; bu kutuda yok
```

Standart kupon talebi (`tahminler/README.md`): karma 5x, 10x, 20x, 30x, 50x; aile kuponları İY/MS, Alt/Üst, KG, MS 1-2 (hedef 5x). Güvenli kurucu önce derin araştırma yapar:

```bash
.venv/bin/python scripts/kupon_kur.py --hedef 5 --tarih 2026-11-21
.venv/bin/python scripts/kupon_kur.py --hedef 10 --tarih 2026-11-21
# doğrudan nesine_kupon (kupon_kur tercih edilir):
.venv/bin/python scripts/nesine_kupon.py --hedef 5 --tarih 2026-11-21 --kupasiz --ana-pazar --no-tm
```

`kupon_kur.py --kanitsiz` takım geçmişiyle test edilmemiş bacaklara izin verir. `nesine_kupon.py --help` kaynakta bozuk bir yardım dizgesi yüzünden hata verir; seçenekler betiğin `add_argument` satırlarındadır (`--yontem optimum|guvenli`, `--aile karma|iyms|altust|kg|ms12`, `--dogrudan`, `--yalniz-keskin`, `--no-pull`, …).

Kupon izleme (Windows `kupon_izle.cmd` burada yok; aynı iş):

```bash
.venv/bin/python scripts/kupon_kontrol.py kontrol --date 2026-11-21 --sessiz
.venv/bin/python scripts/kupon_kontrol.py ozet
```

`--sessiz` pop-up / Telegram uyarısını kapatır. Uyarı göndermeyin.

**Duman testi (21 Kasım 2026, 11:47:34 Europe/Istanbul):** `nesine_global.py --date 2026-11-21` çıkış kodu 0, ~254 sn (~4,2 dk). Anahtar gerekmedi.

- 686 futbol maçı (+4 özel bahis); 933 global referans (anı 20 Kasım 21:26:33 UTC, eski)
- OddsMath canlı oran: 618 maç; ESPN oran: 141 maç; Transfermarkt: 0/686
- 615/690 maç fiyatlandı; 64 seçim EV ≥ 0
- Yazılanlar: `nesine_global.md`, `nesine_global.json`, `nesine_history.jsonl`, `takim_dosyalari.md`, `takip_kayit.json` (hepsi `tahminler/grokbottahmin/2026-11-21/`)
- `derin_tahmin.py` bu kurulumda çalıştırılmadı (önkoşul dosyası artık duruyor; tüm gün uzun sürer)

---

## Değerlendirme ve sonuç

```bash
export QUANTFOOT_AI=grokbottahmin

.venv/bin/python scripts/daily.py results --date 2026-11-21
.venv/bin/python scripts/daily.py verify --date 2026-11-21
.venv/bin/python scripts/nesine_takip.py sonuc --date 2026-11-21
.venv/bin/python scripts/nesine_takip.py rapor          # tahminler/grokbottahmin/takip/ozet.md
.venv/bin/python scripts/ledger_report.py --date 2026_11_21
```

**Ortak değerlendirme** (kullanıcı istediğinde; resmi istisna — bütün yapay zekâ klasörlerini okur, `degerlendirme/<gün>.md` yazar):

```bash
.venv/bin/python scripts/gun_degerlendirme.py --tarih 2026-11-21
```

Bunu kullanıcı açıkça istemeden çalıştırmayın.

Kalibrasyon (çıktı `data/calibration/`, ortak):

```bash
.venv/bin/python scripts/auto_learn.py --daily-dir tahminler/grokbottahmin
```

---

## quantfoot CLI (paket komutları)

```bash
.venv/bin/quantfoot backtest --report-dir reports
.venv/bin/quantfoot analyze --league T1 --home Galatasaray --away Fenerbahce \
  --odds 2.15 3.40 3.30 --sharp-odds 2.02 3.45 3.65 --ou25 1.85 2.00 --ah -0.25 1.88 2.02
.venv/bin/quantfoot slate --mode all --dates 20261121 --fund-weight 0.25 --min-ev 0.02
.venv/bin/quantfoot portfolio --bets-json examples/matchday_portfolio.json --bankroll 1000
.venv/bin/quantfoot markets --mu-home 1.8 --mu-away 1.0 --league eng.1 --division E0
.venv/bin/quantfoot soccerdata --action leagues
.venv/bin/quantfoot soccerdata --action espn-schedule --league T1 --season 2627 --force-cache
.venv/bin/quantfoot intel --date 2026-11-21 --oddsmath --limit 10
```

`markets` bu kutuda çevrimdışı çalıştı. `soccerdata --action leagues` çalıştı. FBref / SoFIFA / WhoScored kaynakları tarayıcı (Selenium) ister; ESPN / ClubElo / MatchHistory / Understat HTTP. Club Elo yine de bu ağdan kapalı.

Diğer yardımcı betikler: `wiki_gecmis.py`, `openfootball_gecmis.py`, `openligadb_gecmis.py`, `openmatchday_gecmis.py`, `arsiv_guncelle.py` (football-data.co.uk sezon dosyaları — bu kutudan erişilebilir), `dc_model.py`, `scheduled.py` (eski zamanlanmış giriş; görevler kapalı). `scripts/kupon_izle.cmd` yalnız Windows.

---

## Bu kutuda ne çalışır / ne takılır

**Çalıştı veya anahtarsız çalışması beklenir:** `daily.py` (predict/run/report/coupons; results/verify/snapshot ESPN ile), `nesine_global.py` (OddsMath + ESPN; TM etkisiz), `gunluk_analiz`, `mac_dosyasi`, `derin_tahmin` / `derin_arastirma` / `simulasyon` (Nesine çıktısı üstüne), `kupon_kur` / `nesine_kupon` (global fiyat 3 saatten yeniyse), `kupon_kontrol --sessiz`, `nesine_takip`, `quantfoot markets` / `soccerdata leagues` / `intel --oddsmath`, Wikipedia / openfootball geçmişi, `pytest`.

**Anahtar veya taze veri ister:** `api_gecmis.py`, API-Football oranları, OddsPapi, Football Charts, Telegram. Kupon kurmak için taze `data/global_odds/` (şimdiki anı eski).

**Bu kutudan tıkalı veya yararsız:** Transfermarkt sakat/cezalı, Club Elo canlı çekimi, `elo_gorus.py` (yerel CSV yok). Matchbook canlısı şüpheli; arşivdeki eski referanslar duruyor.

**Yapılmaz:** `git push`, bahis, Telegram / `kupon_kontrol` uyarısı (sessiz değilse), kullanıcı istemeden `gun_degerlendirme.py`, başka yapay zekâ klasörüne yazmak veya bakmak, ortak alanlara (`reports/`, `docs/data/`) bugünün tahmini yazmak.

---

## Sistem ne yapar (kısa)

QuantFoot, tarihsel kulüp/milli maç arşivi ve canlı Nesine + ESPN + keskin global oranlar (Pinnacle / Smarkets / Matchbook / OddsMath) üzerinde çalışan kantitatif bir tahmin ve kupon motorudur. Gol pazarları tek tutarlı dağılımdan (20 aile + Bet Builder) fiyatlanır. Repodaki walk-forward testte modeller Bet365 kapanışına bilgi katmamıştır (havuz ağırlığı 0); asıl bakılan şey keskin–yumuşak fiyat farkı ve CLV'dir. Günlük Nesine akışı her seçimi global adil fiyata göre ev'ler, ESPN araştırması ve (mümkünse) takım geçmişiyle ana tercihi süzgeçler, sonra hedef oranlı kupon kurar. Sistem yalnız kullanıcı sorduğunda çalışır.

---

## Yeni araçlar (21 Kasım, dal `grokbot/tam-analiz`)

Hepsi `QUANTFOOT_AI=grokbottahmin` ister ve hiçbir zaman bahis yapmaz. Dal birleşmeden önce `/tmp/fd-upgrade`
çalışma ağacından `PYTHONPATH=src` ile çalıştırılır; birleşince ana depodan.

### Tam maç dosyası — `scripts/tam_analiz.py`
```bash
export QUANTFOOT_AI=grokbottahmin QUANTFOOT_DOSSIER_CACHE=/workspace/futbol-dehasi/data/cache/dossier
python scripts/tam_analiz.py --ev "Manchester City" --dep Fulham [--tarih 2026-11-21] [--gecmis-yok] [--kota 90]
```
API-Football (fikstür/hakem/stat, sakat-cezalı, form + karşılaşma geçmişi, Pinnacle dahil oranlar + hareket, ≤75 dk
kala ilk 11), ESPN (puan durumu, dinlenme), Open-Meteo (stat şehrinde hava), football-data (İng./İsk. hakem kart
eğilimi), FotMob (tahmini/kesin ilk 11, eksikler, hakem; `QUANTFOOT_FOTMOB=0` kapatır), Understat (şu an bakımda),
yerel xG birikimi. Maç başına ≈3 API-Football isteği (sonra önbellek). Ücretsiz plan yalnız dün/bugün/yarın fikstürü
verir; pencere dışı günler istek harcamadan atlanır. Çıktı: `tahminler/grokbottahmin/<tarih>/mac_dosyalari_tam/`.

### Gerçek xG birikimi — `scripts/xg_doldur.py --butce 10`
Dün/bugünün biten maçlarından (önbellekteki fikstür) öncelikli liglerde API-Football `/fixtures?id=` → `data/xg/api_football_xg.csv`.
Ortak kota koruması varsayılan 80 (maç öncesine yer bırakır).

### Kupon / kasa politikası — `scripts/kupon_politikasi.py`
```bash
python scripts/kupon_politikasi.py --bacaklar kupon.csv --kasa 250 --gunluk-limit-oran 1.0 --kupon-limit-oran 0.2
python scripts/kupon_politikasi.py --adaylar adaylar.csv --kasa 250 --adet 5            # en çok 5 kupon, aynı maç tek kuponda
python scripts/kupon_politikasi.py --adaylar adaylar.csv --kasa 250 --hedef-kat 10 --canli-rezerv 100
python scripts/kupon_politikasi.py --gecmis tahminler/grokbottahmin/nesine_kupon_gecmisi.csv
```
CSV: `match_id,selection,odds,prob[,prob_sd][,coupon]` (odds = Nesine, prob = keskin/adil olasılık). Sert kurallar: her
bacak EV ≥ 0, kupon EV ≥ %2, en çok 4 bacak, oran ≥ 1.20, aynı maç tek kupon. Paylar Kelly ağırlığıyla günlük bütçeyi
doldurur (varsayılan %100 kasa, kupon başı %20), 5 TL katları; +EV yoksa 0 TL. Risk: bugün hepsini kaybetme olasılığı,
30 gün tekrar edilirse medyan kasa / yarıya düşme / batma, stres testi. Hedef katlama: P(gün sonu ≥ hedef) en yüksek
plan + Markov üst sınırı + Kelly karşılaştırması. `--canli-rezerv` değeri `canli/rezerv.json`'a yazılır.
Eşikler: `src/quantfoot/settings.py` (STAKE_DAILY_FRAC, STAKE_COUPON_FRAC, STAKE_STEP_TL, MIN_STAKE_TL, MIN_COUPON_EV, LIVE_MIN_EV).

### Canlı tarayıcı — `scripts/canli_tarama.py`
```bash
python scripts/canli_tarama.py --bir-kez                 # zamanlayıcı her 5 dakikada bunu çağırır
python scripts/canli_tarama.py --bir-kez --canli-rezerv 100 --ayrintili
python scripts/canli_tarama.py --aralik 300 --sure 120   # elle döngü
```
API-Football KULLANMAZ. Nesine canlı bülten (oran; okuma), ESPN scoreboard/summary, ESPN'de olmayan maçlar için FotMob
canlı listesi + en çok 8 maç ayrıntısı/tarama (4 dk önbellek). Canlı gol modeli: maç öncesi λ (Nesine maç öncesi
bülteni, 30 dakikada bir önbelleğe alınır → **yalnız tarayıcı çalışırken başlamamış maçlar fiyatlanır**; ESPN
DraftKings oranı yedek) × kalan süre (artan yoğunluk), skor durumu, kırmızı kart, canlı xG/şut baskısı. Uyarı eşiği EV ≥ %5,
dakika < 85, oran ≥ 1.20. Tekrar engeli `canli/durum.json`: aynı fırsat yalnız oran ≥ %3 iyileşirse yeniden yazılır.
Çıktı `tahminler/grokbottahmin/canli/<tarih>.jsonl` + `.md`; hiçbir şey yoksa tek satır "Fırsat yok". Bir tarama ≈4–7 sn.
Model parametreleri (kırmızı kart, skor durumu, baskı) varsayımdır, doğrulanmadı: uyarılar karar değil, inceleme listesidir.
