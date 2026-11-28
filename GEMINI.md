# Gemini ve Antigravity çalışma kuralları

**[KURALLAR.md](KURALLAR.md)** (Ramazan'ın kupon kuralları — her şeyden önce gelir), [AGENTS.md](AGENTS.md) ve
[ortak sistem](docs/ORTAK_SISTEM.md) bağlayıcıdır. Çıktını paylaşmadan önce
`python scripts/ai_cikti_dogrula.py --ai <klasörün> --tarih <YYYY-AA-GG>` çalıştır; çıkış kodu 1 ise önerme.

## Gemini / Antigravity için

Sen Gemini veya Antigravity'sin: yalnız kendi klasörün (`tahminler/geminitahmin/` ya da
`tahminler/antigravitytahmin/`) senin; öteki `tahminler/*tahmin/` klasörlerini hiçbir araçla açma, aramalarda
hariç tut. Kendi karneni yazma: `scripts/gun_degerlendirme.py` tek geçerli not kaynağıdır.

### Gemini'ye özel (28 Kas 2026 denetimi)

- **Kendi sonucunu yazma yasak.** `mac_tahminleri.csv` / `kuponlar.csv` içine `bacak_sonucu`, `kupon_sonucu`,
  `ana_sonuc`, `ms_skoru`, `iy_skoru`, `degerlendirme_notu` gibi sütunlar ya da KAZANDI/KAYBETTİ hücreleri yazma.
  Denetimde senin yazdığın sonuçlar 112 tercihin 17'sinde Nesine ile çelişti. Sonuçlar yalnız ortak hattan
  (`scripts/sonuc_defteri.py`, `scripts/gun_degerlendirme.py`) gelir; bilinmeyen sonuç "belirsiz" kalır.
- **Ortak şema zorunlu:** `scripts/ai_tahmin.py` `MATCH_COLS` / `COUPON_COLS`. Her bacağa `olasilik` (0–1) yaz.
- Çifte şans, handikap, KG, takım golü, İY/MS, skor ve 1,80 üstü oranlı bacak banko kupona girmez.
  Kupon 2–5 bacak, toplam oran < 20. Kurulamazsa "kupon yok" de.
