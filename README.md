# Futbol Dehası | QuantFoot

[![CI](https://github.com/ramazanardic/futbol-dehasi/actions/workflows/ci-tests.yml/badge.svg)](https://github.com/ramazanardic/futbol-dehasi/actions/workflows/ci-tests.yml)

**24 Kasım 2026 — güncel ortak çalışma hattı (v5 kupon/teşhis güncellemesi).** Python paketinin sürümü `0.1.0` (`pyproject.toml`); araştırma ve çalışma hattı sürümleri paket sürümünden farklıdır.

QuantFoot, futbol maçları için istatistiksel olasılık tahmini, piyasa fiyatı karşılaştırması, takım araştırması, kalibrasyon ve sonuç denetimi yapan bir Python araştırma projesidir. Nesine bülteni ile küresel fiyatları eşleştirir; veri bulunmayan pazarları kesin tahmin olarak sunmaz. Beş yapay zekâ ortak kod ve veriyle, birbirlerinin tahminlerinden bağımsız çalışır.

> **Önemli:** Model olasılıkları kesin sonuç değildir. 19 Kasım araştırmasında modellerin piyasanın marjsız fiyatına ilave tahmin gücü sağladığı gösterilemedi. Geçmiş isabet ve ROI, gelecek performansı garanti etmez. Depo otomatik bahis uygulaması değildir.

## 1. Başlangıç ve ortak kurallar

Önce [AGENTS.md](AGENTS.md) ve [Ortak sistem](docs/ORTAK_SISTEM.md) okunmalıdır. Bunlar çalışma sözleşmesidir; eski araştırma raporları güncel üretim talimatı değildir. Belgeler ile uygulama arasındaki bilinen farklar aşağıdaki **Sınırlamalar ve açık konular** bölümünde belirtilmiştir.

| Yapay zekâ | `QUANTFOOT_AI` |
|---|---|
| Claude | `claudetahmin` |
| Gemini | `geminitahmin` |
| Antigravity | `antigravitytahmin` |
| ChatGPT / Codex | `chatgbttahmin` |
| Grok Bot | `grokbottahmin` |

Her yapay zekâ yalnız kendi `tahminler/<QUANTFOOT_AI>/<YYYY-AA-GG>/` klasörüne yazar ve kendi geçmişini kullanır. Ortak kaynak kodu, veri ve kalibrasyon herkese eşittir. Bağımsız ortak değerlendirme, yetkili değerlendirme araçlarıyla gerçekleştirilir; diğer tahmin klasörleri kişisel araştırma girdisi değildir. Bu izolasyon bir çalışma kuralıdır; **herkese açık GitHub deposunda teknik erişim engeli değildir.**

Futbol araştırması, oran yenileme ve sonuç işlemleri yalnız istek üzerine başlatılır. Eski otomatik sabah raporları ve 15 dakikalık izleyici aktif zamanlanmış görev olarak kabul edilmemelidir. Saat dilimi: Europe/Istanbul.

## 2. Kurulum

Gereksinimler: Git, Python 3.11 veya üzeri (CI: 3.12), veri kaynaklarına erişim için internet. GitHub CLI yalnız elle oran iş akışı tetiklemek için gereklidir.

**Windows PowerShell**

```powershell
git clone https://github.com/ramazanardic/futbol-dehasi.git
cd futbol-dehasi
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e . pytest lxml
$env:QUANTFOOT_AI = "chatgbttahmin"
$env:PYTHONIOENCODING = "utf-8"
.\.venv\Scripts\python.exe -m pytest -q
```

**Linux / macOS**

```bash
git clone https://github.com/ramazanardic/futbol-dehasi.git
cd futbol-dehasi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest lxml
export QUANTFOOT_AI=chatgbttahmin
export PYTHONIOENCODING=utf-8
export TZ=Europe/Istanbul
python -m pytest -q
```

Mevcut kurulumda önce `git pull --ff-only` ve gerekirse yeniden paket kurulumu yapılır. Örnek AI kimliğini kendi kimliğinizle değiştirin. İsteğe bağlı soccerdata bağlayıcısı: `python -m pip install -e ".[soccerdata]"`. API-Football kullanılacaksa `API_FOOTBALL_KEY` yerel ortamda veya git'e gönderilmeyen `.env` dosyasında tutulur. Ortak istek bütçesi `API_FOOTBALL_MAX_REQ` ile yönetilir (belgelenen varsayılan 60/gün). Anahtarları depoya veya raporlara koymayın.

## 3. Güncel üretim ve araştırma akışı

`scripts/gunluk_tahmin.py` tek ortak giriş noktasıdır. Aşağıdaki sıra kaynak kodundaki adımları yansıtır:

| Adım | İşlev |
|---|---|
| Bülten | `nesine_global.py`: Nesine karşılaşma/pazar eşlemesi, global referans, marj temizleme ve fiyatlama |
| Tahmin | `ai_tahmin.py`: ortak CSV biçimi; başlamış maçların tahminlerini değiştirmeme |
| Derin araştırma | `derin_tahmin.py`, `simulasyon.py`, `ekstrem_gol_analiz.py`: takım geçmişi, eksikler, simülasyon ve özel gol pazarları |
| Kupon değerlendirmesi | `kupon_kur.py`: aday kuralları, araştırma ve güncel fiyat kontrolü |
| Denetim | Ortak hattın `run_audit` adımı: bacak kuralları, yoğunlaşma ve ihlaller |

Komut seçenekleri ve çıktı sözleşmesi [Ortak sistem](docs/ORTAK_SISTEM.md) belgesindedir. `--kuru` komutları çalıştırmadan gösterir; `--derin-veri` henüz başlamamış maçlarda fiyat durumundan bağımsız takım araştırmasını açar. Analiz, kapsama giren tüm doğrulanabilir Nesine pazarlarını ele alır; fiyatı veya eşlemesi olmayan seçimler eksik olarak belirtilir.

### QuantFoot Terminal

Windows (yukarıdaki kurulum ve AI kimliği ile):

```powershell
.\.venv\Scripts\python.exe scripts/terminal.py
```

Linux/macOS (sanal ortam etkin):

```bash
python scripts/terminal.py
```

Tarayıcı: <http://127.0.0.1:8765/>. **Derin araştırmayı başlat** işlemi bülten, tahmin ve derin araştırma adımlarını çağırır; tek başına tüm kupon/denetim hattının tamamlandığı anlamına gelmez. Terminal, takım verilerini, arşivi ve dosya yüklemeyi destekler. Eksik form, kadro, sakatlık, hava veya istatistik bilgisi eksik olarak gösterilir.

[Yayımlanan web paneli](https://quantfoot-terminal-ramazan.ramazanardic.chatgpt.site) GitHub tahminleri ve yerel terminalden alınan araştırma JSON'u için arayüzdür; canlı araştırma yerel Python motorunda gerçekleşir. Dış panelin erişilebilirliği bu README güncellemesinde ayrıca sınanmamıştır.

## 4. Veri ve model mimarisi

| Katman | Kaynak / yöntem |
|---|---|
| Bülten ve oranlar | Nesine; Pinnacle, Smarkets, Matchbook, OddsMath/BetInAsia ve ESPN referansları; kaynak ve güncellik farklılıkları dikkate alınır |
| Takım verisi | ESPN, API-Football (kotalı, maç öncesi), FotMob, openfootball ve diğer tarihsel bağlayıcılar |
| Ek bağlam | Club Elo, Understat, Transfermarkt, hava verisi ve isteğe bağlı soccerdata bağlayıcısı; erişim ve kapsam garanti değildir |
| İstatistiksel modeller | Dixon-Coles, Poisson/COM-Poisson, Gamma-Poisson, Elo/Glicko, Kalman, GAP, GAS, topluluk modelleri |
| Pazar fiyatlama | Marj temizleme, tutarlı skor ve devre dağılımları, türetilmiş pazarlar, Bet Builder, kalibrasyon |
| Denetim | Brier, log-loss, RPS, ECE, CLV, sonuçlandırma, veri ve olasılık tutarlılığı |

20 teorik pazar ailesi [pazar modeli belgesinde](docs/markets.md) tanımlanır; Bet Builder bu tablodaki 20. ailenin parçasıdır. Nesine'nin operasyonel seçim sınıflandırması ayrı bir şemadır (`src/quantfoot/markets/families.py)); iki taksonominin sayısı eşit kabul edilmemelidir. Maç sonucu, Alt/Üst, devre sonucu, KG, gol aralığı, skor, handikap, korner, kart, oyuncu ve kombine gibi pazarlar modellenebilir. Teorik model desteği her maç için doğrulanmış veri veya canlı kotasyon bulunduğu anlamına gelmez.

Oran kaynağı ve yaşı, maç kimliği, maçın başlangıç durumu, doğrudan/türetilmiş fiyat ayrımı ve sonuçlandırma adı kayıt altına alınmalıdır. Eski fiyatlar güncel fiyat olarak gösterilmemelidir. [Nesine entegrasyonu](docs/nesine.md) ve [veri/model araştırmaları](docs/research/) ayrıntıları içerir.

## 5. 24 Kasım v5 güncellemesi ve güvenilirlik

24 Kasım kodunda maksimum 5 bacaklı banko modu, kademeli aday havuzu genişletme, derin tahmine teşhis/simülasyon bağlantısı ve yeni kök-neden kayıp kontrolleri bulunur. İlgili kod: `scripts/nesine_kupon.py`, `scripts/gunluk_tahmin.py`, `src/quantfoot/coupons/coupon_rules.py`, `src/quantfoot/markets/market_diagnosis.py` ve `src/quantfoot/settings.py`.

**Banko**, ürün içindeki mod adıdır; kesin kazanma anlamına gelmez. Katı kurallar ve daha gevşek aday havuzları aynı güvenilirlik düzeyi değildir. Nihai denetimi geçmeyen bir sonuç onaylı olarak sunulmamalıdır. Sistem kuponu da kayıp riskini ortadan kaldırmaz. Birleşik olasılık, bacak bağımsızlığı varsayımına duyarlıdır.

**Bilinen belge/kod çelişkisi:** Ortak sözleşmede katı %70 düzeltilmiş olasılık tabanı korunurken 24 Kasım kodunda havuzu genişleten daha düşük eşikli aday kademeleri eklenmiştir. Ortak günlük denetim ayrıca `leg_decision` çağırır. Dolayısıyla aday üretilmesi nihai denetimden geçildiğini kanıtlamaz. Ortak belge ve kodun bu davranış için eşgüdümlü hale getirilmesi ve test edilmesi gerekmektedir.

## 6. Çıktılar, değerlendirme ve denetim

| Yol | İçerik |
|---|---|
| `tahminler/<AI>/<tarih>/mac_tahminleri.csv` | Maç kimliği, 1X2 olasılıkları, ana seçim ve kaynak bilgileri |
| `tahminler/<AI>/<tarih>/kuponlar.csv` | Kupon kayıtları ve seçimler |
| `tahminler/<AI>/<tarih>/kupon_denetim.md` | Ortak kurallara uygunluk ve yoğunlaşma |
| `tahminler/<AI>/<tarih>/ekstrem_gol_analiz.*` | 6+ gol / iki yarıda KG araştırma çıktısı |
| `tahminler/<AI>/oz_gelistirme_raporu.*` | Kendi geçmişine dayalı kalibrasyon ve hata denetimi |
| `degerlendirme/<tarih>.md/.json` | Ortak sonuç karnesi |

Dosya şeması: [tahminler/README.md](tahminler/README.md). Standart CSV UTF-8, ondalık nokta ve 0–1 aralığında olasılık kullanır. Sonuçlandırma adı (`secim_adi`) özellikle devre ve kombine pazarlarında önemlidir.

23 Kasım'da eklenen bağımsız tarihsel denetim (`scripts/ai_history_audit.py`), erişilebilir kayıtları salt okunur olarak değerlendirir; sonuç etiketleri yerine ortak skor arşivinden pazar çözümü, yayın zamanı, eksik veri, 1X2 olasılıkları, tekrar eden riskler ve fiilî bahis defteri ayrımını inceler. CI bu denetimi çalıştırır ve makine okunabilir raporu artefakt olarak saklar.

[23 Kasım bağımsız denetim raporu](docs/research/tum_ai_tarihsel_denetim_2026_11_23.md) 1.900 ham ana tahmin satırı, 66.985 fiyatlanan seçim ve 57.962 sonuçlandırılabilir seçim bildirir. Bunlar bağımsız maç veya oynanmış bahis sayıları değildir. Eksik ham CSV'ler, tamamlanmamış maçlar ve maç öncesi yayın kanıtı eksikliği nedeniyle kesin AI sıralaması çıkarılamaz. Raporlanan ana seçim kümelerinde varsayımsal ROI negatiftir.

## 7. Proje dizinleri ve bakım

```text
src/quantfoot/
  data/         Veri kaynakları, bağlayıcılar ve maç araştırması
  models/       İstatistiksel tahmin modelleri
  markets/      Fiyatlama, pazar aileleri ve teşhis
  coupons/      Ortak kupon kuralları ve sistem hesapları
  strategy/     Risk ve portföy modülleri
  evaluation/   Backtest, kalibrasyon, sonuçlandırma ve öz-denetim
scripts/        Ortak giriş noktaları, terminal ve denetim araçları
tests/          Birim ve regresyon testleri
data/           Arşivler, oran anlık görüntüleri ve kalibrasyon
docs/           Ortak sözleşme, araştırma ve yöntem belgeleri
reports/        Araştırma ve tarihsel raporlar
tahminler/      AI bazında ayrı çıktılar
degerlendirme/  Ortak değerlendirme
.github/        CI ve elle tetiklenen oran iş akışı
```

- [ci-tests](.github/workflows/ci-tests.yml): PR, ilgili kod değişiklikleri ve manuel tetikleme; testler ile tarihsel denetim.
- [global-odds](.github/workflows/global-odds.yml): yalnız manuel tetikleme; `data/global_odds/latest/` anlık görüntülerini günceller. İş akışının tamamlanması ve yeni verinin yerel depoya alınması gerekir.
- Kod ve ortak kurallar PR üzerinden değiştirilir; testler ve AI eşitliği kontrol edilir. Yerel anahtarlar, geçici dosyalar ve kişisel veriler gönderilmez.

## 8. Araştırma geçmişi ve açık konular

- [Kasım 2026 model deneyleri](docs/research/experiments_2026_11.md): 16.423 maçlık ileri-yürüyen testte 15 modelin hiçbiri Bet365 marjsız referansına ek tahmin bilgisi sağlamadı (havuz ağırlığı sıfır).
- [Literatür incelemesi](docs/research/literature_review_2026_11.md) ve [yol haritası](docs/research/roadmap_2026_11.md): model, veri ve araştırma kararları.
- [Bahis ailesi araştırması](docs/research/bahis_aileleri_2026_11_21.md) ve [deneysel kod](docs/research/deneysel_kod.md): tarihsel incelemeler.
- [Önceki README (19–21 Kasım ağırlıklı)](https://github.com/ramazanardic/futbol-dehasi/blob/875b1cd358b54d1b6662d7a8fc081fb9b677597e/README.md): eski v4–v8.2 araştırma skorları ve tarihsel komutlar. Güncel üretim rehberi değildir.

### Sınırlamalar ve açık konular

- Modelin piyasayı sürekli yendiği veya pozitif canlı ROI ürettiği kanıtlanmış değildir. Tek günlük veya geriye dönük yüksek isabet, yeni maçlarda başarı kanıtı değildir.
- Güncel arşivdeki maç sayısı yeniden sayılmadan eski sabit veri büyüklükleri kullanılmamalıdır.
- Tüm dünya liglerinde eksiksiz oyuncu, hakem, korner, kart ve dakika bazlı veri erişimi garanti edilmez. Modellerin varlığı gerçek zamanlı tam kapsam anlamına gelmez.
- 24 Kasım katı denetim ile aday havuzu genişletme arasındaki fark ortak belgelerde netleştirilmeli; gerçek zamanlı ve yeni dönem örneklerinde yeniden doğrulanmalıdır.
- Otomatik 24/7 veri toplama, saniyelik eksiksiz kayıt veya kesintisiz yüzlerce maç takibi bu belgenin doğruladığı aktif çalışma modu değildir.
- Herkese açık depo, hassas kayıtların erişim kontrolü için uygun kabul edilmemelidir.

**Güncelleme kuralı:** Yeni özellikler, veri kaynakları, üretim politikaları ve doğrulanmış araştırma sonuçları değiştikçe README ile ortak belgeler birlikte güncellenmelidir.
