# data/gfi — GLOBAL FOOTBALL INTELLIGENCE'dan türetilmiş tablolar

Bu tablolar 28 Kas 2026'da `scripts/gfi_turet.py` ile GFI gzip CSV dışa aktarımından üretildi. Ham dışa aktarım repoda yok.
Burada maç satırı bulunmaz; tabloların hepsi agregattır.

| Dosya | İçerik |
|---|---|
| `lig_taban_gfi.csv` | 223 yarışmanın taban oranları: n, ilk/son tarih, gol ortalaması (ev/dep), 1.5/2.5/3.5 alt, KG, 1X2. İY skoru olanlarda ayrıca İY 0.5 üst, İY 1.5 alt, İY gol payı ve 2Y KG yok. FT penceresi 2023-07-01 sonrası. |
| `takim_form_gfi.csv` | Arşiv (`data/matches.csv`) dışındaki liglerde takım bazında son 10 maç / son 10 ev / son 10 deplasman atılan ve yenilen gol ortalaması. |
| `lig_yari_dakika_gfi.csv` | world_incidents gol dakikalarından 12 lig için İY gol payı ve 15 dakikalık dağılım. `_genel` satırı da var. |

## Kaynaklar ve lisans

- **openfootball/football.json ve txt depoları:** CC0.
- **openligadb:** yalnız agregat olarak kullanıldı.
- **world_results ve world_incidents:** lisansları belirsiz. Bu yüzden bunlardan yalnız oran ve ortalama türetildi; maç satırı konmadı.
- `wr:<ülke>` anahtarı, world_results'ta o ülkenin üst ligi demek. Bu verinin son maçı 2025-09-30.

## Kullanım

Tabloları `src/quantfoot/markets/gfi_priors.py` okur. Varsayılan olarak **KAPALI**: `settings.GFI_PRIORS_ENABLED = False`, açmak için `QF_GFI_PRIORS=1`.

Açıkken iki şey değişir:
- `league_halves.league_first_half_share` lig profili olmayan ligler için GFI ya da genel İY payına düşer.
- `nesine_global.price_event` yalnız gol-toplamı seçimlerini (X.5 Alt/Üst, İY/2Y X.5, KG) GFI öncülüne karıştırır. Ağırlık model 0.6, öncül 0.4.

Neden kapalı olduğu `reports/research/gfi_etki_2026-11-28.md` içinde anlatılıyor.
