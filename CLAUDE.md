# Claude çalışma kuralları

**[KURALLAR.md](KURALLAR.md)** (Ramazan'ın kupon kuralları — her şeyden önce gelir), [AGENTS.md](AGENTS.md) ve
[ortak sistem](docs/ORTAK_SISTEM.md) bağlayıcıdır. Çıktını paylaşmadan önce
`python scripts/ai_cikti_dogrula.py --ai <klasörün> --tarih <YYYY-AA-GG>` çalıştır; çıkış kodu 1 ise önerme.

## Claude için

Sen Claude'sun: yalnız `tahminler/claudetahmin/` senin (`QUANTFOOT_AI=claudetahmin`). `tahminler/geminitahmin/`,
`tahminler/antigravitytahmin/`, `tahminler/chatgbttahmin/` ve `tahminler/grokbottahmin/` klasörlerini hiçbir
araçla (Read, Grep, Glob, ls, cat …) açma; aramalarda bu yolları hariç tut.
