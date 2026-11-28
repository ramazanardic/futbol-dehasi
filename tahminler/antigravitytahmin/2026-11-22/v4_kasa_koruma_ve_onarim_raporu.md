# QuantFoot v3 → v4 Kasa Koruma, Sistem Temizliği ve 5-AI Eşitlik Raporu (22–23 Kasım 2026)

- **Klasör:** `tahminler/antigravitytahmin/2026-11-22/`
- **Güncelleme:** 2026-11-23 03:12 TSİ (439 bitmiş fiyatlı maç · 1.864 kupon-bölgesi seçimi)
- **Not:** Dondurulmuş `mac_tahminleri.csv` ve `kuponlar.csv` dosyalarına **hiç dokunulmamıştır**.

## 1. 439 Maçlık v4 Ayrıştırma Özeti (`oz_gelistirme_raporu.md`)

- **v4 `OK` havuzu:** **325/479 (%67,8 vs %65,8 = +2,0p · Brier `0,2176` · 1u ROI −%13,4)**
- **v4 `REHAB` havuzu:** **77/116 (%66,4 vs %65,3 = +1,1p · Brier `0,2204`)**
- **v4 `TUZAK_RED` (reddedilenler):** **812/1.269 (%64,0 vs %64,3 = −0,3p · Brier `0,2300` · 1u ROI −%17,3)**
- **Keskin Borsa Steam Kalkanı:**
  - `MS 1/2` steam yok: **41/58 (%70,7, +4,2p)** vs sert steam (`≥6p`): **6/14 (%42,9, −22,7p)**
  - `ALT` steam yok: **128/198 (%64,6)** vs sert steam (`≥6p`): **11/19 (%57,9, −5,6p)**

## 2. Kasa Koruma Karşı-Olgusal Kanıt (`kasa_koruma_plani.md`)

- **Eski yöntem (33 düz 5–7’li kombine, ağır `EV < −%14` Nesine marjı, ortak maç tekrarı):** **0/33 tuttu (−%100)**
- **Yeni v4 `scripts/kasa_koruma.py` (`EV ≥ −%10`, 3 maç/kupon, sıfır ortak maç, kupon başı maks %3 / günlük maks %10 kasa):**
  - 623 ağır marjlı bacak elendi → **3 kupon · toplam risk 90 TL (%9 kasa)**
  - Gerçek sonuç: **2/3 kupon tuttu (8/9 bacak = %88,9)** · Ödeme **192,00 TL / 90 TL** → **Net +102,00 TL (+%113,3 ROI)**

## 3. Tüm 5 AI İçin Kalıcı Ortak Altyapı

- **v3 + v4 kod çekirdeği:** `market_diagnosis.py`, `extreme_goals.py`, `system_builder.py`, `self_improve.py`, `nesine_kupon.py`, `kasa_koruma.py`, `oz_gelistirme.py`, `kupon_kontrol.py`.
- **5-AI eşitliği:** FotMob ve tüm ortak veri kaynakları `VALID_AIS` için eşit açık; `AGENTS.md`, `CLAUDE.md`, `GEMINI.md` ve `.github/copilot-instructions.md` satır satır eşgüdümlü ve `tests/test_common_ai_parity.py` ile CI’da zorunlu.
- **GitHub & Yerel Temizlik:** 3 workflow Node 24 (`@v7`), 27 Windows UTF-8 kodlama + 2 dosya kolu sızıntısı onarıldı, 2 ölü script ve 3 birleşmiş uzak dal temizlendi.
