# arsiv_kod — emekli / tek seferlik araştırma betikleri

Bu betikler günlük akışta, testlerde ve `src/` içinde **kullanılmaz** (28 Kas 2026 temizliğinde `rg` ile doğrulandı).
Üretikleri raporlar `docs/research/` ve `reports/research/` altında kayıtlı durur; betikler yalnız yeniden üretmek için
saklanır. Bakımı yapılmaz; çalıştırmak için depo kökünden: `PYTHONPATH=src python arsiv_kod/<betik>.py`.

| Betik | Ne yapmıştı |
|---|---|
| `hata_analizi_21kasim.py` | 21 Kas hata analizi (arşivde kalıcı mı gürültü mü); sonuçlar `data/calibration/market_tail_calibration.json` ve `src/quantfoot/markets/market_reliability.py` içinde |
| `research_experiments.py` | piyasanın fiyatlamadığı bilgi var mı deneyleri → `docs/research/experiments_2026_11.md` |
| `calibrate_direct.py`, `calibrate_halves.py` | gol modelini doğrudan borsa fiyatlarına / yarı payına kalibre etme |
| `devig_karsilastirma.py`, `kombine_dogrulama.py` | marj temizleme ve kombine politikası kanıtları (`docs/research/gap_analysis_2026_11_21.md`) |
| `v8_dogrulama.py` | v8 yükseltmeleri için ampirik kıyas (`docs/research/v8_kapsamli_gelistirme_2026_11.md`) |
