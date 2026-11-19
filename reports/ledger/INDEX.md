# QuantFoot-v6 Kalıcı Tahmin ve Kupon Denetim Arşivi (Ledger Index)

Bu dizin, oluşturulan tüm günlük maç tahminlerini, kupon portföylerini ve geçmişe dönük doğrulama (*backtest / post-mortem*) kayıtlarını kalıcı olarak saklar.

## Arşivlenmiş Günler ve Raporlar

| Tarih | Motor Sürümü | Maç Sayısı | Kupon / Rapor Dosyaları | Doğrulama Durumu |
| :---: | :--- | :---: | :--- | :--- |
| **2026-11-17** | `QuantFoot-v5 -> v6 Post-Mortem` | 16 Ana Maç | [quantfoot_v6_omni_upgrade_report.md](../quantfoot_v6_omni_upgrade_report.md) / `verify_v6_on_nov17_coupons.py` (kaldırıldı, git geçmişinde: 1db0432) | `v6 Geriye Dönük Test: 16/16 (%100)` |
| **2026-11-18** | `QuantFoot-v6 (OmniMarketBundle)` | 45 Maç | [nov18_audit_results.md](nov18_audit_results.md) / [coupons_2026_11_18.md](coupons_2026_11_18.md) / [coupons_2026_11_18.json](coupons_2026_11_18.json) / [today_all_45_matches_v6_2026_11_18.md](../today_all_45_matches_v6_2026_11_18.md) / [verify.md](../daily/2026-11-18/verify.md) | `3 kupon kazandı, 4 kaybetti; en iyi seçim 30/42` |
| **2026-11-19** | `daily.py` | 10 Maç | [coupons.md](../daily/2026-11-19/coupons.md) / [report.md](../daily/2026-11-19/report.md) | `3 artı EV tekil, 0 kupon` |
| **2026-11-20** | `daily.py` | 19 Maç | [coupons.md](../daily/2026-11-20/coupons.md) / [report.md](../daily/2026-11-20/report.md) | `14 artı EV tekil, 3 kupon` |
