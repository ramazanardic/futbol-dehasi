# Veri kapsam denetimi — Faz 1 uygulaması (28 Kas 2026)

Denetim: `reports/research/veri_kapsam_2026-11-28.md`. Bu PR ilk 3 öneriyi, #4'ün Nesine'de görülen orta Avrupa
liglerini ve #5'i (GFI/öncül yeniden testi) kapsar. Kural: her değişiklik zaman sızıntısız ölçülür; kalibrasyon/isabet
kötüleşiyorsa alınmaz. Eksik alan **hiçbir yerde uydurulmadı** (boş kalır).

## 1. global-odds iş akışı bayatlığı (öneri #3a) — ALINDI
* Kök neden (24 Kas iptal günlükleri): fetch ~8 dk + Club Elo adımı 60 sn × 6 denemeyle ~7 dk takıldı → 15 dk iş sınırı
  → iş "Commit data" adımından ÖNCE iptal; references.json 22 Kas'ta kaldı.
* Düzeltme: `Commit data` artık Club Elo'dan önce; Elo ayrı adım (`timeout-minutes: 4`, `continue-on-error`, kendi
  commit'i); fetch adımı 14 dk; iş sınırı 25 dk; `elo_gorus.py` istek zaman aşımı 60 → 20 sn.
* football-data sezon/ek lig dosyaları kutudan yeniden indirildi: değişiklik yok — P1 (08 Kas) ve RUS (02 Ağu)
  bayatlığı football-data'nın kendisinde (bizde değil). Bu yüzden ESPN dolgusu gerekli (madde 3).

## 2. data/matches.csv Pinnacle sütunları (öneri #3b) — ALINDI
* Yeni sütunlar (sona): `PSHome PSDraw PSAway PSCHome PSCDraw PSCAway PSOver25 PSUnder25 PSCOver25 PSCUnder25 Source`.
* Kaynak: football-data.co.uk `mmz4281/<1213…2526>/<div>.csv` (22 lig × 14 sezon) + `new/<KOD>.csv` (16 ek lig) +
  depodaki 2026/27 dosyaları. `scripts/pinnacle_doldur.py` metin düzeyinde yazar: **eski 48 sütun bayt bayt aynı**
  (doğrulandı: HEAD ile sütun kırpılmış dosya `diff` = 0).
* Eşleşme: 250.608 satır → 160.628 tam (lig+tarih+normalize takım), 339 tek adaylı skor eşleşmesi, 89.641 boş
  (2012 öncesi ve kaynakta Pinnacle olmayan satırlar). 2012/13+ çekirdek liglerde PSCHome dolu oranı %88–95
  (SC2/SC3 %63), ek liglerde (yalnız kapanış) %88–96; Pinnacle 2,5 Ü/A 2019/20'den beri (~%40–48).
* `arsiv_guncelle.py` MAP/NEW_MAP bu sütunları yeni satırlarda da doldurur.
* Dosya 46,9 → 53,5 MB (GitHub 100 MB sınırının altında; 50 MB uyarı eşiğinin üstünde — not).
* Nötrlük: oranlı 1X2+2,5 satır kümesi (158.582), korner kümesi (124.137), İY kümesi (186.302) önce/sonra
  **aynı özet hash**; banko bant kontrolü bant tabloları birebir aynı (yalnız başlıktaki ham maç sayısı +106).
  Pinnacle sütunlarını henüz hiçbir model okumuyor (Faz 3'te CLV/kapanış kalibrasyonu için).

## 3. P1 / RUS bu sezon — ESPN skor dolgusu (öneri #1) — ALINDI
* `scripts/espn_lig_tara.py`: ESPN lig scoreboard'u (gün başına 1 istek). `/soccer/all` taraması por.1 2026/27'de
  yalnız 27 maç getirmişti; lig ucu 99 (por.1) ve 121 (rus.1) maç verdi.
* `arsiv_guncelle.py`: football-data'nın son gününden SONRAKİ ESPN skorları eklenir (yalnız tarih, takımlar, skor,
  form; oran/İY/şut boş, `Source=espn`). Takım adları açık eşleme tablosuyla; eşlenemeyen takım satırı yazılmaz.
  **Değiştirme kuralı:** aynı maç football-data'da çıkınca (aynı takımlar, ±1 gün) ESPN satırı silinir, oranlı satır
  yazılır; diğer satırlar bayt bayt aynı (test: `tests/test_veri_kapsam_28kasim.py`).
* Sonuç: RUS +105 maç (08 Ağu → 28 Kas), P1 +1 (27 Kas; P1'de 08 Kas sonrası milli ara vardı).
* Doğruluk: ESPN ↔ football-data çakışan maçlarda skor uyumu P1 280/280, RUS 225/225 (%100).
* Ölçüm: oranlı/korner/İY backtest kümeleri değişmedi (ESPN satırlarında oran yok) → kalibrasyon nötr; kazanç canlı
  tarafta (RUS takımlarının form/son maç geçmişi 02 Ağu yerine güncel).

## 4. Orta Avrupa arşiv dolgusu (#4, Faz 1 kısmı) — VERİ ALINDI
`scripts/arsiv_ek_kaynak.py` → `data/arsiv/maclar.csv.gz` (+3.931 satır; eski satırlar bayt bayt aynı; matches.csv'de
olan maçlar arsiv_kur kuralıyla ayıklanır):
* OpenLigaDB 3. Liga 2023/24–2026/27: 1.281 maç, **yalnız tam skor**. OpenLigaDB İY'si openfootball ile takım eşlemeli
  karşılaştırmada %89–92 uyumlu; uyuşmayanların neredeyse tamamı 0:0 yer tutucusu → İY yazılmadı (uydurma riski).
* Wikipedia sonuç matrisleri 2023/24–2026/27 (tarihsiz, İY yok): 3. Liga 380, Avusturya 2. Lig 326, Çekya 431,
  İsviçre Challenge 342, Sırbistan 403, Slovakya 140, Slovenya 114, TFF 1. Lig 509.
* Bulunamayanlar: HNL, Bosna, Macaristan NB I, Serie C 2025/26+ (Wikipedia başlık/matris yok; ESPN bu ligleri
  kapsamıyor; API-Football ücretsiz planı geçmiş sezon vermiyor). FBref/Sofascore vb. kullanılmadı.
* ESPN P1/RUS lig taraması: +4 / +1 (diğerleri zaten matches.csv'de).

## 5. Arşivden orta Avrupa yarı öncülleri (öneri #2) — ALINMADI (ölçüm kötü/nötr)
`scripts/arsiv_yari_oranlari.py --olc`: her test sezonu için yalnız ÖNCEKİ sezonlardan lig İY gol payı + LEAGUE_BLEND
oranları; A = bugünkü üretim (mevcut satır ya da 0,440 / genel oran), B = arşiv. Ölçü: İY/2Y 0,5 ve 1,5 Üst log-loss,
yarı-aile oranları Brier. (A'nın mevcut satırları test sezonunu da içerebilir → A lehine; ama eşlenmemiş liglerde
A = sabit 0,440, sızıntısız.)

| Nesine ligi | test maç | yarı gol LL A → B | blend Brier A → B | karar |
|---|---|---|---|---|
| Hırvatistan 1. Hnl | 161 | 0.59814 → 0.60041 | 0.17827 → 0.18200 | alma |
| Bosna Hersek Premier Lig | 188 | 0.59951 → 0.59922 | 0.17166 → 0.17308 | alma |
| Slovakya Superliga | 175 | 0.59367 → 0.59478 | 0.18279 → 0.18211 | alma |
| Slovenya Prvaliga | 167 | 0.57632 → 0.57642 | 0.17249 → 0.17333 | alma |
| Sırbistan Superliga | 274 | 0.58533 → 0.58549 | 0.18007 → 0.17252 | alma |
| Macaristan 1. Ligi | 548 | 0.57785 → 0.57787 | 0.16885 → 0.16990 | alma |
| Çekya 1. Lig | 861 | 0.58706 → 0.58706 | 0.17443 → 0.17453 | alma |
| İsviçre Challenge Ligi | 458 | 0.57644 → 0.57963 | 0.16759 → 0.16795 | alma |
| Avusturya 2. Lig | 1448 | 0.57459 → 0.57469 | 0.17546 → 0.17570 | alma |
| Almanya 3. Lig | 3582 | 0.58851 → 0.58849 | 0.17384 → 0.17391 | alma |

Hiçbir lig iki ölçüde birden nötr-ya-da-iyi değil → `lig_yari_oranlari.csv` ve eşleme DEĞİŞMEDİ. Ders: lig başına
İY gol payı sezondan sezona ±0,03 oynuyor; küçük örneklemli lig payı 0,440 sabitinden iyi tahmin etmiyor.
(TFF 1. Lig ve Serie C: İY'li eğitim sezonu yetersiz, ölçülemedi.)

## 6. GFI / lig taban öncülü yeniden testi (#5) — ALINMADI
GFI dışa aktarımı kutuda artık yok; aynı fikir arşivle sızıntısız ölçüldü (`scripts/arsiv_oncul_olcumu.py`): seçim
günü D için yalnız D öncesi tarihli maçlar, lig = iki takımın son 400 günde birlikte oynadığı yarışma, oran = son
730 gün. Seçimler: sürüm denetimi rows.json gol aileleri (Alt/Üst, İY Alt/Üst, KG), 18–23 Kas.

| küme | n | P log-loss | 0,8P+0,2·oran | 0,6P+0,4·oran |
|---|---|---|---|---|
| hepsi | 538 | 0.6338 | 0.6336 | 0.6350 |
| geçmişsiz lig | 106 | 0.6334 | 0.6314 | 0.6313 |
| geçmişsiz lig (tekil seçim) | 97 | 0.6548 | 0.6504 | 0.6477 |
| kapsanan lig | 432 | 0.6339 | 0.6341 | 0.6359 |
| **P ≥ 0,70 (banko bölgesi)** | 131 | **0.5479** | 0.5562 | 0.5659 |
| geçmişsiz lig, P ≥ 0,70 | 12 | 0.5941 | 0.6068 | 0.6237 |

Geçmişsiz liglerde küçük kazanç (n≈100, gürültü içinde), banko bölgesinde belirgin kötüleşme (yüksek P'yi taban
orana çekiyor) → banko kalibrasyonu dürüst kalsın diye GFI/öncül **kapalı kalır**. "Yalnız P<0,70'te aç" kuralı aynı
veride seçilmiş olacağından önerilmez; daha fazla çözülmüş seçimle (≥300 geçmişsiz lig) yeniden bakılmalı.

## Testler
Tam takım: 2149 → 2154 geçti (yeni: `tests/test_veri_kapsam_28kasim.py`, 5 test).
