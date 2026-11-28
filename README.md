# QuantFoot — futbol tahmin ve kupon sistemi (futbol-dehası)

Nesine bülteninin her seçimini **keskin global referans fiyata** (Pinnacle, Smarkets, Matchbook, BetInAsia, OddsMath)
göre fiyatlar, olasılığı arşivle kalibre eder ve Ramazan'ın kurallarına uyan **banko kuponu** kurar. Kurallara uyan
kupon yoksa sonuç dürüstçe "kupon yok"tur; kural gevşetilmez. Kullanıcı onayı olmadan bahis oynanmaz.

Bağlayıcı kurallar tek yerdedir: **[KURALLAR.md](KURALLAR.md)** (P ≥ 0,70 · oran 1,20–1,80 · maç başına tek bacak ·
2–5 bacak · yasak aileler). Yapay zekâ çalışma sözleşmesi: [AGENTS.md](AGENTS.md) ve [docs/ORTAK_SISTEM.md](docs/ORTAK_SISTEM.md).
Beş yapay zekâ (`claudetahmin`, `geminitahmin`, `antigravitytahmin`, `chatgbttahmin`, `grokbottahmin`) aynı koddan
çalışır ve yalnız kendi `tahminler/<klasör>/` dizinine yazar (`QUANTFOOT_AI` zorunlu).

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .\.venv\Scripts\Activate.ps1
pip install -e . pytest
pytest -q                                              # tamamı yeşil olmalı
```

API anahtarları (API-Football, Telegram) yalnızca git'e girmeyen `.env` dosyasındadır. API-Football günde en çok 60 istek.

## Günlük akış (yalnız kullanıcı isteyince)

```bash
export QUANTFOOT_AI=<klasörün>
python scripts/gunluk_tahmin.py --tarih YYYY-AA-GG     # bülten → tahmin → derin araştırma → banko kupon → denetim (--kuru: yalnız komutları göster)
python scripts/ai_cikti_dogrula.py --ai $QUANTFOOT_AI --tarih YYYY-AA-GG   # paylaşmadan önce; çıkış 1 ise önerme
python scripts/gun_degerlendirme.py --tarih YYYY-AA-GG # ertesi gün ortak nesnel karne → degerlendirme/
python scripts/kasa_koruma.py --tarih YYYY-AA-GG --kasa <TL>   # 3 maçlık düşük marjlı plan
python scripts/oz_gelistirme.py                        # kendi klasörünün çok-günlük öz-denetimi
```

Tek tek adımlar: `scripts/nesine_global.py --date D` (fiyatlama), `scripts/gunluk_analiz.py --tarih D`,
`scripts/kupon_kur.py --hedef 2.5 --tarih D --mod banko`. Ayrıntı: [docs/nesine.md](docs/nesine.md).

## Katmanlar

| Katman | Ne yapar | Durum |
|---|---|---|
| Banko kupon | `nesine_kupon.py` + `coupon_rules` + `market_diagnosis` kalkanları + 20.000'lik bağımsız simülasyon | günlük hatta, zorunlu |
| Yüksek oranlı pazarlar | kesin skor, İY skoru, İY/MS, 2Y KG, korner için **yalnız analiz**: `python scripts/yuksek_oran_pazarlar.py backtest` / `tahmin --lig E0 --ev A --dep B --oran 1 X 2`. Banko kupona **girmez** | isteğe bağlı |
| Web araştırma | kupon adayı maçlarda ESPN/Wikipedia/Open Matchday/FPL bilgi kaydı ([docs/WEB_ARASTIRMA.md](docs/WEB_ARASTIRMA.md)); olasılığı değiştirmez | açık (`QF_WEB_RESEARCH=0` kapatır) |
| GFI, form, sakat/kadro kalkanı | GFI öncülleri, son-120-gün formu, ücretsiz sakat/cezalı kalkanı; ölçümde anlamlı iyileşme yok | **varsayılan kapalı** (`settings.py`) |
| Arşiv genişletme | `data/arsiv/` ~646 bin ek maç (1888–2026), yarışma/takım katalogları, oyuncu özetleri; lisans ve kapsam: [data/arsiv/BENIOKU.md](data/arsiv/BENIOKU.md) | veri |

## Veri

`data/matches.csv` (kulüp maçları, Elo/form özellikli, 2000–bugün), `data/international_results.csv` (milli maçlar),
`data/global_odds/latest/` (keskin fiyatlar; GitHub iş akışı `global-odds.yml` ile istek üzerine yenilenir),
`data/calibration/` (kalibrasyon dosyaları), `data/arsiv/` (ek arşiv), `data/gfi/`, `data/form/`.
Arşiv `python scripts/arsiv_guncelle.py` ile güncellenir (yalnız yeni maçlar eklenir). **Veri ve tahmin arşivleri silinmez.**

## Depo düzeni

`src/quantfoot/` çekirdek (veri, pazarlar, modeller, kupon, değerlendirme) · `scripts/` komut satırı araçları ·
`tests/` · `docs/` belgeler (`ORTAK_SISTEM.md`, `nesine.md`, `markets.md`, `WEB_ARASTIRMA.md`, `REHBER.md` eski ayrıntılı rehber,
`research/` araştırma notları) · `tahminler/` her yapay zekânın kayıtları · `degerlendirme/` ortak karne ·
`reports/` rapor ve kayıtlar · `terminal/` + `server.js` yerel web paneli (`python scripts/terminal.py`) ·
`arsiv_kod/` emekli tek seferlik betikler.

## Test ve CI

`pytest -q` yerelde ve GitHub'da (`ci-tests`: tam test paketi + salt-okunur yapay zekâ geçmişi denetimi) çalışır.
Kural testleri (`tests/test_ramazan_kurallari.py`, `tests/test_ai_cikti_dogrula.py`) KURALLAR.md'ye kilitlidir;
bunları gevşeten değişiklik birleştirilmez. Değişiklik için dal + PR açın, CI yeşilken birleştirin; force-push yok.

Eski ayrıntılı komut kataloğu ve çalışma notları: [docs/REHBER.md](docs/REHBER.md).
