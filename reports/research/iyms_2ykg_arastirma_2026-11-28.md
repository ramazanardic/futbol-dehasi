# İY/MS ve 2Y KG Var araştırması (28 Kas 2026)

Soru: İY/MS (Ramazan'ın tutan 6'lı kuponu gibi) ve 2Y KG Var kuponlarını "en olası seçimlerle" nasıl kurarız?
Yöntem: `scripts/iyms_2ykg_arastirma.py`; ileri-yürüyen, sızıntısız (takım oranları her hafta yalnız önceki maçlarla, kalibrasyon her ay yalnız önceki
ayların örneklem-dışı tahminleriyle). **Test: 2024-07-01 sonrası, 24.900 maç** (İY'si olan, piyasa oranı olan). Veri: football-data + PR #37–#42 ile
genişleyen veri. Kaynak yok / uydurma yok.

**Sınır:** arşivde İY/MS ve 2Y KG oranı **yok**. Kupon tutma oranları gerçektir; ROI, 28 Kas Nesine bülteninden ölçtüğüm çarpanlarla
(107 maçta İY/MS, 232 maçta 2Y KG fiyatı) kurulan **sentetik** Nesine oranıyla hesaplandı. Nesine'nin gerçek geçmiş fiyatı birikmedikçe ROI kesin değildir.

## Ana sonuç (dürüst)
1. **Nesine bu iki pazarda payı yüksek tutuyor:** İY/MS'de 9 hücrenin 1/oran toplamı ortalama **1,324** (pay %32); 2Y KG'de %22. Modelin
   kendi P'siyle bile beklenen getiri: İY/MS en olası hücre **−%20**, 2Y KG Var **−%20**, 2Y KG Yok **−%17**. Hiçbir P kovasında pozitif beklenti yok.
2. **Kupon bacağı arttıkça beklenen kayıp büyür** (≈ 0,8^k − 1): 1 bacak −%20, 2 bacak −%36, 3 bacak −%50, 5 bacak −%67. Geçmiş simülasyon da bunu doğruladı.
3. Yani "en olası" seçmek tutma ihtimalini artırır ama parayı kazandırmaz. Bu pazarlar eğlence/lottery; küçük sabit tutar.
4. **Model değişikliği bulunamadı** (PR yalnız araştırma kodu ve rapor). Reddedilenler aşağıda.

## 1. İY/MS: hücre ve profiller
- Model P'si yalnız **1/1 ve 2/2** için 0,25'i geçiyor (test: 1/1 maks 0,73; 2/2 0,63; X/X 0,44 ender; **X/1 en çok 0,245**; 1/2, 2/1, 1/X, 2/X ≤ 0,07).
  Kullanıcının tutan kuponundaki X/1 bacağı modelde hiçbir zaman %25'i aşmaz.
- En olası hücre tahmin vs gerçek (test, Wilson %95 GA):

| Model P bandı | n | tahmin | gerçek | GA |
|---|---|---|---|---|
| 0,20–0,25 | 8.091 | 0,225 | 0,225 | 0,216–0,234 |
| 0,30–0,35 | 4.642 | 0,324 | 0,311 | 0,298–0,325 |
| 0,35–0,40 | 2.894 | 0,372 | 0,387 | 0,369–0,405 |
| 0,40–0,45 | 1.572 | 0,423 | 0,433 | 0,409–0,458 |
| 0,45–0,50 | 974 | 0,472 | 0,502 | 0,471–0,533 |
| 0,50–0,55 | 531 | 0,524 | 0,584 | 0,541–0,625 |
| 0,55–0,60 | 267 | 0,571 | 0,637 | 0,578–0,692 |
| ≥ 0,60 | 140 | 0,631 | 0,700 | 0,620–0,770 |

  Genel: en olası hücre %30,7 tutuyor (tahmin %30,6).
- **Güçlü ev favorisi 1/1 en güvenilir yüksek-P profili.** Favori P(MS1) ≥ 0,75: 1/1 tahmin 0,565 → gerçek 0,644 (n 661); 0,65–0,75: 0,461 → 0,500 (n 1.447).
  Model burada **temkinli**: 1/1 P ≥ 0,45'te 2021–2026 sezonlarının 6'sında 6'sı gerçek ≥ tahmin (toplam n ≈ 3.170; ort. tahmin 0,52, gerçek ≈ 0,57).
- **Deplasman favorisi 2/2 bu kadar iyi değil:** P(MS2) ≥ 0,75'te 2/2 tahmin 0,551 → gerçek 0,480 (n 102); ≥0,45 bandında gerçek ≈ tahmin. 2/2 ≥ 0,5 bacağı 1/1'den zayıf.
- Yüksek-P profilinde toplam gol beklentisi yüksekse (> 3,5) isabet daha yüksek: 0,63 vs 0,52 (P ≥ 0,45 alt kümesi, favori gücüyle iç içe).
- Lig bazlı (P ≥ 0,45, n ≥ 25): en iyi gerçekleşen NOR, BRA, P1, T1, E1, SC0, D1, SP1; en zayıf G1 (0,47 vs 0,52), E2, B1, I1. Çoğu fark gürültü düzeyinde; kural yapma.
- Büyük-5 / orta / alt lig: P ≥ 0,45'te gerçek 0,548 / 0,565 / 0,541 → lig kademesi anlamlı ayırmıyor.
- **Günde kaç bacak çıkar (test, 766 gün):** P ≥ 0,45'te ortalama 4,0 bacak/gün (≥3 bacak olan gün 234, ≥5 olan gün 158); P ≥ 0,50'de 2,7/gün (≥3: 144, ≥5: 64); P ≥ 0,55'te 1,8/gün (≥5: yalnız 6 gün).

### Nesine fiyatı vs model adil oranı (28 Kas bülteni, 107 maç)
| Model P kovası | n | ort. P | ort. Nesine oranı | beklenen getiri |
|---|---|---|---|---|
| 0,30–0,40 | 32 | 0,338 | 2,40 | −%19 |
| 0,40–0,50 | 13 | 0,441 | 1,85 | −%19 |
| ≥ 0,50 | 9 | 0,588 | 1,35 | −%21 |
| 0,10–0,15 | 169 | 0,126 | 5,72 | −%29 |
| < 0,03 | 136 | 0,020 | 31,8 | −%36 |

Nesine'nin "değer" sunduğu bir kova yok. Tek tek bacaklarda pozitif beklenti yalnız 3 uzun-oranlı 1/2 hücresinde çıktı (Gaziantep–Amed +%6, Cambuur–Sparta +%2, Rosenborg–Molde +%2; P ≈ %4); P'ler küçük (≈ %4) ve küçük bir kalibrasyon sapması bile beklenti işaretini çevirir; **değer olarak sayma**.

## 2. 2Y KG Var
- Bu pazar **doğası gereği düşük olasılıklı**: gerçek oran %26,7; model P'si 0,18–0,38 arasında, **tavan ≈ 0,40**. P ≥ 0,35 yalnız 268 maç (%1).
- Kalibrasyon iyi (test): 0,25–0,30 bandı tahmin 0,273 / gerçek 0,274 (n 11.385); 0,30–0,35: 0,317 / 0,330 (n 3.445); 0,35–0,40: 0,364 / 0,358 (n 268).
- Neyin P'yi artırdığı: toplam gol beklentisi. Beşliklerde gerçek: ≤2,4 gol → %22,7; 2,4–2,6 → %24,8; 2,6–2,78 → %26,3; 2,78–3,02 → %28,95; > 3,02 → %31,1 (model tahminleriyle uyumlu).
- Favori gücü, devre skoru ya da İY gol sayısı (maç öncesi bilgi değil, kontrol) 2Y KG'yi **ayırmıyor** (favori kovalarında 0,26–0,28; İY durumuna göre 0,267 sabit).
- Lig farkı: D1 gerçek 0,345 (tahmin 0,294, n 702), USA 0,326, N1 0,325, CHN 0,320, DEN/MEX ~0,30; düşük: ARG 0,195, SC1 0,199, G1 0,213, P1 0,227. Lig ofseti walk-forward testte **iyileştirme getirmedi** (aşağıda), yani farkların çoğu gürültü; D1/USA/N1 yine de yüksek toplam-gol ligleri.
- **Kupon sonucu:** en iyi 3 bacağın tutma ihtimali ≈ %4 (P ≥ 0,33: tahmin 0,043 / gerçek 0,047). 2Y KG Var kuponu pratikte yalnız 1–2 bacak.
- **2Y KG Yok** (banko ailesi): P ≥ 0,75'te hafif iyimser: 0,75–0,80 bandı tahmin 0,769 / gerçek 0,758 (GA 0,748–0,767); 0,80–0,85: 0,817 / 0,801. 28 Kas bülteninde 2Y KG Yok oranı medyan 1,15; **P ≥ 0,75 olan 43 maçın hiçbirinde oran ≥ 1,20 değil**, yani banko oran tabanını sağlamıyor.

## 3. Kupon simülasyonu (test 2024-07+, günlük, P'ye göre sıralı, maç başı tek bacak, ayrık k'lı kuponlar)
Tutma = gerçek; oran/ROI = sentetik Nesine. Tahmin = P çarpımı.

**İY/MS en olası hücre, P ≥ 0,45:**
| Bacak | kupon n | tahmin | gerçek | ort. oran | ROI (±SE) |
|---|---|---|---|---|---|
| 1 | 1.912 | 0,512 | 0,558 | 1,6 | −%13 (±1,8) |
| 2 | 809 | 0,268 | 0,326 | 2,5 | −%22 (±4) |
| 3 | 466 | 0,143 | 0,193 | 3,8 | −%30 (±7) |
| 4 | 311 | 0,076 | 0,116 | 5,9 | −%38 (±10) |
| 5 | 206 | 0,042 | 0,068 | 8,7 | −%47 (±15) |
| 6 | 158 | 0,022 | 0,044 | 13,4 | −%39 (±23) |

P ≥ 0,50: 1 bacak 0,616 gerçek (n 938, ROI −%12), 2 bacak 0,365 (n 364, −%26), 3 bacak 0,204 (n 191, −%44), 4 bacak 0,118 (n 110).
**Yalnız 1/1 (P ≥ 0,45):** 1 bacak 0,567 (n 1.556), 2 bacak 0,323 (n 637), 3 bacak 0,198 (n 354), 4 bacak 0,127 (n 221); ROI −%12 … −%35.
Yalnız 2/2 (P ≥ 0,45): 1 bacak 0,520 (n 356), 2 bacak 0,278 (n 115), 3 bacak 0,105 (n 38); 1/1'den kötü.
Eşiksiz (her gün en olası k hücre): 3 bacak 0,040 tutma, 6 bacak 0,0039 (ROI −%51 / −%71).
**Çıkarım:** ROI hiçbir bacak sayısı/eşikte pozitif değil (en iyi −%12, tek bacak, ≥0,50). Tutma ihtimali ile kayıp dengesi: **P ≥ 0,45 ile 2–3 bacak** (%33 / %19 tutma). 5–6 bacakta tutma %4–7, ROI daha kötü ve oynak.

**2Y KG Var:** 1 bacak −%18; P ≥ 0,33'te 1 bacak 0,355 (n 893), 2 bacak 0,126 (n 342), 3 bacak 0,047 (n 192). Tüm bacak sayılarında ROI negatif (−%18…−%100).
**2Y KG Yok (P ≥ 0,78):** 1 bacak tutma 0,785 (tahmin 0,802), 2 bacak 0,623 (0,646), 3 bacak 0,494 (0,520), 4 bacak 0,412, 5 bacak 0,336, 6 bacak 0,262; sentetik oran 1,03–1,19, ROI −%19…−%70.
Gerçek tutma çarpım tahmininin 1–2,5 puan altında, yani P çarpımı hafif iyimser.

## 4. Seçim kuralları (skill'e yapıştırılabilir)
1. İY/MS ve 2Y KG Var banko kupona girmez (KURALLAR.md); yalnız kullanıcı isterse, "lottery" olarak, kasanın en çok %0,5–1'i.
2. **İY/MS bacağı = en olası hücre**; yalnız **P ≥ 0,45** olanlar. Tercih sırası: ev favorisi 1/1 (P(MS1) ≥ 0,65, model P ≥ 0,45–0,60 → gerçek ≈ gösterilenden +%3–6) > 2/2 (P(MS2) ≥ 0,55; gösterilen P'ye güven, ≥ 0,75 favoride iyimser) > diğer hücreler.
   X/1, X/2, 1/2, 2/1 bacağını "en olası" diye önerme: P ≤ 0,25 (X/1) ve ≤ 0,07 (1/2, 2/1).
3. **Bacak sayısı:** 2–3 bacak önerilir (toplam tutma %33 / %19 civarı). 4–6 bacakta toplam tutma %4–12; ancak kullanıcı isterse, toplam P'yi açıkça yaz. Hiç eşik yoksa kupon kurma: P < 0,40 bacakla İY/MS kuponu yapma.
4. **Gün başına bacak sayısı sınırlı:** P ≥ 0,50 yalnız günlerin %45'inde en az 1, %19'unda ≥3 bacak veriyor. Yoksa "kupon kurulamadı" de, eşiği düşürme.
5. İki aynı lig / aynı gün favorisi arasında korelasyon yok sayıldı (çarpım P hafif iyimser, 1–2,5 puan); toplam P'yi yazarken "yaklaşık" de.
6. **Fiyat:** Nesine'nin 9 hücre 1/oran toplamı ≈ 1,32; seçim başına beklenen getiri −%19…−%36. "Nesine oranı adil orandan yüksek" şartı bu bültende hiçbir bacak için sağlanmadı; sağlanmayan bacağı "değerli" diye sunma.
7. **2Y KG Var:** yalnız yüksek toplam-gol ligleri (D1, N1, USA, CHN, NOR) ve P ≥ 0,33; en çok 1–2 bacak (tutma %35 / %13). 3+ bacak %5'in altında. ARG, SC1, G1, P1 gibi düşük-gol liglerinden kaçın.
8. **2Y KG Yok**, oran ≥ 1,20 ise banko ailesinde kalır; P ≥ 0,78 isabeti ~%78,5 (tahminden −1,7 puan): gösterilen P'den ~0,015–0,02 düşük kabul et.
9. Çelişki kontrolü: aynı maçtan iki seçim yok; İY/MS 1/1 ile aynı maçta "2Y KG Var" ya da "MS 2" yok. Skor/İY skor/İY/MS ayrı küçük kupon.
10. Hâlâ geçerli: tek gün sonucuyla kural değiştirme; ROI için Nesine'nin gerçek fiyat geçmişi birikmeli (`nesine_history.jsonl` yalnız 1X2/alt-üst/ÇŞ tutuyor, İY/MS ve 2Y KG tutmuyor).

## 5. Model iyileştirme adayları (hepsi REDDEDİLDİ)
Ölçüt: OOS log-loss farkı %95 GA üst ucu < 0, doğrulama (2022-07 … 2024-06) ve test (2024-07+) ikisinde. İY/MS ve 2Y KG banko kuponda yasaktır; banko bölgesi değişmedi.
| Aday | Doğrulama Δ [GA] | Test Δ [GA] | Karar |
|---|---|---|---|
| İY/MS 4. kova: güçlü ev favorisi (d > 0,45) | −0,00007 [−0,00045, +0,00031] | −0,00012 [−0,00040, +0,00016] | RED |
| aynı, eşik 0,35 | −0,00011 [−0,00055, +0,00033] | −0,00009 [−0,00042, +0,00024] | RED |
| 5 kova (ev 0,30/0,50) | −0,00027 [−0,00076, +0,00023] | −0,00032 [−0,00072, +0,00009] | RED (GA 0'ı kesiyor) |
| 5 kova simetrik ±0,45 | +0,00007 [−0,00040, +0,00053] | −0,00009 [−0,00041, +0,00022] | RED |
| 2Y KG lig ofseti, K=100 | +0,00062 [+0,00008, +0,00117] (kötü) | +0,00002 [−0,00043, +0,00046] | RED |
| 2Y KG lig ofseti, K=200 / 400 / 800 | +0,00045 / +0,00028 / +0,00016 | −0,00007 / −0,00013 / −0,00015 (GA 0'ı kesiyor) | RED |

Not: 1/1 yüksek-P eksik tahmini sezonlar arası tutarlı (yön doğru), ancak etkilenen maç oranı küçük (%4) olduğu için tüm-örneklem log-loss kazancı GA'yı sıfırın altına itmiyor. Bu yüzden modele koymadım; yalnız okuma kuralı olarak (madde 2) bıraktım. daha fazla sezon verisi veya Nesine gerçek fiyat geçmişi birikince yeniden ölç.

## Yeniden üretim
```bash
python scripts/iyms_2ykg_arastirma.py --cache <feat_240.pkl> --nesine tahminler/<ai>/<gün>/nesine_global.json --model-testleri --damga 2026-11-28   # ≈5 dk
```
Çıktı: `iyms_2ykg_arastirma_2026-11-28.json` (tüm bantlar, lig tabloları, simülasyon tabloları).

---

# EK: "İki Yarıda KG Var" (iki yarıda da karşılıklı gol) — düzeltme (28 Kas 2026)

Kullanıcı "2 yarıda KG" ile **2Y KG Var'ı değil, İY'de de 2Y'de de iki takımın gol atmasını** kastetti. Nesine'de bu seçim
"1. Yarı / 2. Yarı Karşılıklı Gol" pazarında **"İki Yarıda KG Var"** (diğer üç seçim: İY Yok & 2Y Yok, İY Var & 2Y Yok, İY Yok & 2Y Var).
Hazır bir not/kalibrasyon yok (`families.py` yalnız "Yarı KG" ailesi adı veriyor); bu yüzden P, 2Y KG ile aynı hattan kuruldu:
P = Σ(devre durumu) P(İY'de iki takım da attı ∧ durum) · P(2Y KG | durum), ardından aylık sızıntısız logit kalibrasyonu.
Kod: `scripts/iki_yari_kg_arastirma.py`; çıktı: `iki_yari_kg_arastirma_2026-11-28.json`. Test 2024-07+, n = 24.900.

## Sonuç: pratikte kupon pazarı değil
- **Gerçek oran %5,54**; model ort. P %5,27 (ham %5,19). **Model P'si en çok 0,154**; medyan 0,051, %90 dilimi 0,074, %99 dilimi 0,098.
  Yani hiçbir maçta "en olası" bir seçim değil; bu bir **uzun-oranlı lottery** (tek bacak ≈ 1/18).
- **Kalibrasyon (test):** P < 0,08: tahmin 0,050 / gerçek 0,0525 (n 23.445); 0,08–0,10: 0,087 / 0,095 (n 1.261, GA 0,080–0,113);
  0,10–0,12: 0,108 / **0,173** (n 173, GA 0,124–0,237) → üst uçta model temkinli (az maç).
- Toplam-gol beşlikleri (tahmin / gerçek): ≤2,4: 0,033 / 0,037; 2,4–2,6: 0,045 / 0,046; 2,6–2,78: 0,053 / 0,056; 2,78–3,02: 0,061 / 0,062; > 3,02: **0,073 / 0,077**.
- İki takımın da atak gücü (min(λ, μ)) dörtlükleri: 0,040 / 0,043 → 0,049 / 0,053 → 0,055 / 0,055 → **0,068 / 0,071**.
- Favori gücü ayırmıyor (0,051–0,056 tahmin; gerçek 0,053–0,063).
- **P'yi en çok yükselten profil: yüksek toplam gol + dengeli güçlü iki hücum.** P ≥ 0,074 (üst %10): tahmin 0,085 / gerçek **0,091** (n 2.490); bu grup D1 (319), USA (299), D2 (295), N1 (240), E0 (172), EC (161), NOR (155), CHN (136).
  Lig gerçek oranları: N1 %8,8, USA %8,4, DEN %8,3, D1 %8,0, NOR %7,5, D2 %7,4; en düşük: ARG %2,4, SC1 %3,0, E1 %3,4, SC2 %3,6, G1 %3,7. (Lig farkı için ayrı model testi yapılmadı.)
- Model, bağımsız çarpıma (P(İY KG)·P(2Y KG)) göre log-loss −0,00008 [−0,00017, +0,00001]; kalibrasyon ham modele göre −0,00010 [−0,00026, +0,00005].
  İkisi de GA'yı sıfırın altına itmiyor → **model değişikliği YOK** (kalibrasyon hattı üretime eklenmedi, RED).

## Nesine fiyatı (28 Kas bülteni, 173 maçta bu pazar var)
- "İki Yarıda KG Var" oranı **medyan 12,7 (en az 5,91, en çok 34,5)**. Pazarın 4 seçiminin 1/oran toplamı **1,239** (pay ≈ %24).
- Modelle (kalibrasyonsuz, genel lig payı) beklenen getiri **−%17,8**; 173 maçın 9'unda hesaplanan beklenti pozitif (ort. P 0,081, ort. oran 15,9) ama P ≈ %8 küçük bir sapmayla işaret değiştirir; **değer olarak sayma**.

## Kupon simülasyonu (1–4 bacak; günlük P'ye göre sıralı, ayrık kuponlar; tutma gerçek, oran sentetik Nesine)
| Eşik | Bacak | kupon n | tahmin | gerçek tutma | GA | ort. oran | ROI |
|---|---|---|---|---|---|---|---|
| hepsi | 1 | 24.900 | 0,0527 | 0,0554 | 0,053–0,058 | 16,9 | −%16 (±2) |
| hepsi | 2 | 12.260 | 0,0031 | 0,0033 | 0,002–0,004 | 323 | −%44 |
| hepsi | 3 | 8.039 | 0,0002 | 0,0002 | 0,0001–0,0009 | 10.930 | −%70 |
| P ≥ 0,07 | 1 | 3.490 | 0,081 | 0,088 | 0,079–0,098 | 10,0 | −%14 (±5) |
| P ≥ 0,07 | 2 | 1.603 | 0,0067 | 0,0094 | 0,006–0,015 | 99 | −%11 (±23) |
| P ≥ 0,08 | 1 | 1.455 | 0,090 | 0,103 | 0,089–0,120 | 8,9 | −%9 (±7) |
| P ≥ 0,09 | 1 | 553 | 0,100 | 0,123 | 0,098–0,153 | 8,1 | −%2 (±11) |
| P ≥ 0,07 / 0,08 / 0,09 | 3–4 | 109–985 | ≈ 0,001 | 0 – 0,002 | — | 500–10.000 | tutma ≈ sıfır |

2 bacakta tutma %0,3–1; 3–4 bacakta fiilen sıfır (tek tük şans eseri tutmalar ROI'yi sahte şekilde artırır, ör. P ≥ 0,07 / 3 bacak: 985 kuponda 2 tutma, ROI +%144 ±173 → gürültü).

## Kurallar (skill'e eklenebilir)
1. "İki Yarıda KG Var" **yalnız kullanıcı isterse, tek bacak ya da en çok 2 bacak, kasanın ≤ %0,5'i**; kupon tutma ihtimali 1 bacakta ≈ %5–10, 2 bacakta ≈ %1'in altında. 3+ bacak önerme.
2. Kullanıcı "en olası" isterse: model P'si en yüksek maçları seç, yalnız **P ≥ 0,08** (üst %5; gerçek tutma ≈ %10) ve yüksek toplam gol (> 3,0) + iki takım da güçlü hücum (min(λ, μ) > 1,2); ligler D1, D2, N1, USA, NOR, DEN, E0, CHN. ARG, SC1/SC2, E1, G1'den kaçın.
3. Nesine oranı ≥ ~12 ise sunulan pay ≈ %24; "değer" iddiası yok, beklenen getiri ≈ −%18. Model P'sini mutlaka yaz (tipik %5–9).
4. Bu pazarı "2Y KG Var" (P ≈ %27) ile karıştırma: 2Y KG Var tek yarıdır ve çok daha olasıdır; iki yarıda KG ≈ 5 kat daha nadirdir.
5. Dürüst not: İY/MS (en olası hücre %45+) ve 2Y KG Yok bu pazardan çok daha olası seçeneklerdir; "en olası" hedefiyse bunlar tercih edilir.
