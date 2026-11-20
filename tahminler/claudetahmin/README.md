# claudetahmin

Claude'un (QuantFoot) kendi tahminleri ve kuponları. Ortak raporlardan kopyalanmaz.

| Dosya | İçerik |
|---|---|
| `<tarih>/mac_tahminleri.csv` | Kendi analiz çalıştırmasından her maçın 1X2, xG, en olası skor ve ana tercihi |
| `<tarih>/kupon_<hedef>x_<SSDD>.json/.md` | Her kupon kurulumu ayrı dosya (`scripts/nesine_kupon.py`); aynı hedefin son dosyası geçerli |
| `<tarih>/kuponlar.csv` | Geçerli kuponların bütün bacakları (ortak biçim) |
| `<tarih>/kupon_kontrol.md`, `kupon_clv.json` | Maç öncesi bacak kontrolü ve kapanış fiyatı |
| `clv.md` | Bütün günlerin kapanış fiyatı (CLV) özeti |

Sabah işinde, her kupon kurulduğunda ve kadro saatlerinde (:10, :30) güncellenir ve GitHub'a gönderilir; başlamış
maçın satırı değişmez. Ortak biçim: [../README.md](../README.md).
