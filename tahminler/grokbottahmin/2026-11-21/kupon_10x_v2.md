# 10x kupon v2 (tam arama) — 2026-11-21, 19:27 TSİ

**OYNANMADI.** Risk modu. Veri: canlı OddsMath (BetInAsia/Pinnacle) keskin referans 19:21 TSİ, Nesine bülteni 19:26 TSİ'de iki kez okundu, oranlar aynı.

## Yöntem
- Havuz: uygun her maçın Nesine bültenindeki tüm seçimleri (MS, ÇŞ, A/Ü, KG, MS+A/Ü, MS+KG, A/Ü+KG, handikap, takım golleri, İY; İY/MS sadece doğrudan keskin fiyat varsa). P = keskin 1X2 + A/Ü (+KG) ile oturtulmuş Dixon-Coles skor matrisi + kalibrasyon. Matristen türetilen (doğrudan keskin fiyatı olmayan) seçimlerden ayrıca −1,5 puan güvenlik payı düşüldü. Piyasadan iyimser tahmin yok.
- Maç başına (oran, P) Pareto cephesi alındı. Hem oranı hem P'si başka bir seçimden düşük olan seçim hiçbir en iyi kuponda yer alamaz, bu yüzden bu budama kayıpsız. Sonra **3, 4 ve 5 maçın tüm kombinasyonları tek tek sayıldı** (DP + kaba kuvvet, ikisi aynı sonucu verdi).
- Filtreler: kickoff ≥ 25 dk; açık kupon maçları hariç; kupa, genç/rezerv ve play-off yok; keskin referans şart; sakatlık, rotasyon ya da kaleci bayrağı yok; dinlenme > 3 gün; steam'in tersine seçim yok; bacak P ≥ %45 ve oran 1,25–2,10 (risk guard tavanı); takım araştırması olmayan alt ligler çıkarıldı (Guatemala, Orta Amerika, Arjantin play-off vb.).
- Önceki kupondaki Parma – Roma çıktı: yeni araştırma bayrağına göre Parma'nın golcüsü ve Roma'nın 4 düzenli oyuncusu ilk 11'de yok.

## Seçilen kupon: 4 maç · Nesine 10,24 · tutma %7,1 (yaklaşık 14'te 1) · EV −27% · ilk maç 22:30 TSİ

| Saat (TSİ) | Maç | Seçim | Nesine | Adil P | Adil oran | Fiyat | Gerekçe |
|---|---|---|---|---|---|---|---|
| 22:30 | Palmeiras – Flamengo (Brezilya A) | MS 2 | 1,85 | %50,5 | 1,98 | doğrudan | Keskin steam Flamengo lehine (+16 puan), seçim steam'le aynı yönde. Palmeiras 28 Kasım'daki Libertadores finali için rotasyon yapabilir; Barboza, Piquerez, Murilo ve Paulinho yok. Flamengo'da Léo Pereira ve Pulgar cezalı. ⚠ Flamengo'ya beraberlik yetiyor, kadrolar 21:30 civarı açıklanınca tekrar bakılmalı. |
| 22:45 | Strasbourg – Brest (Ligue 1) | 2,5 Üst & KG Var | 1,93 | %47,7 | 2,10 | matris | λ 1,59–1,33, iki takımın da gol atma ihtimali yüksek. Bayrak yok, dinlenme 13–15 gün. |
| 22:45 | Monaco – Auxerre (Ligue 1) | 2,5 Üst & KG Var | 2,02 | %46,1 | 2,17 | matris | λ 2,33–0,93. Monaco gol atar; Auxerre'in gol atma ihtimali yaklaşık %60. Bayrak yok. |
| 23:00 | Telstar – Zwolle (Eredivisie) | 3,5 Alt | 1,42 | %64,0 | 1,56 | doğrudan | Keskin A/Ü'den doğrudan fiyat; λ toplamı 3,0. Bayrak yok. |

Risk guard (`banko_kontrol.py --mod risk --bulten`): **GEÇTİ**. Toplam 10,24, tutma ihtimali %7,1. 50 TL → 512 TL, beklenen değer −14 TL.

## Oran ↔ olasılık eğrisi (bacak ≤ 2,10, P ≥ %45)
| Maç | ≥10 | ≥11 | ≥12 |
|---|---|---|---|
| 3 | kurulamaz (bacak başı ortalama 2,15 gerekir, tavan 2,10) | – | – |
| 4 | %7,11 (10,24) | %6,48 (11,03) | %5,87 (12,12) |
| 5 | %6,14 (10,09) | %5,81 (11,02) | %5,19 (12,13) |

- **En iyi 5'li:** Palmeiras MS 2 1,85 · Lens "Ev en az bir yarıyı kazanır" 1,43 (%63) · Napoli MS 1 1,33 (%66) · Monaco 2,5Ü&KG 2,02 · Telstar 3,5 Alt 1,42 → 10,09, **%6,1**.
- **En iyi 3'lü (tavan 2,50'ye açılırsa):** Palmeiras "Dep en çok gol 2Y" 2,26 (%40) · Telstar 2,5 Alt 2,19 (%43) · Pumas "Ev 1,5 Üst" 2,04 (%44) → 10,10, %7,5. Bacaklar %45'in altında, biri egzotik matris türevi. Risk guard'dan geçmez, önerilmez.
- **Palmeiras'sız alternatif 4'lü:** Lens "Ev 1,5 Üst" 1,80 · Monaco 2,5Ü&KG 2,02 · Zulte Waregem "Ev 1,5 Üst" 1,96 · Telstar 3,5 Alt 1,42 → 10,12, %7,0.
- İlk 20 adet 4'lü kuponun hepsi %6,9–7,2 arasında: tavan yaklaşık %7, hangi kombinasyon olursa olsun.

## Neden 4 maç
10 orana 5 maçla ulaşmak için 2 kısa (1,33–1,43, %63–66) bacak eklemek gerekiyor; bu iki bacağın birlikte tutma ihtimali yaklaşık %42. Kazanılan oran ise sadece 1,9 kat; kayıp, yerlerine giren tek bacağın (~%48) kaybından büyük. Sonuçta P %7,1'den %6,1'e düşüyor. 3 maçta ise her bacak 2,15+ olmak zorunda, yani %40–44'lük piyango bacakları. 4 maç bu ikisinin arasındaki en iyi nokta.

## Dürüst uyarı
Tutma ihtimali yaklaşık 14'te 1 (önceki 4'lü %6,9 idi; bu tam aramayla en fazla %7,1'e çıkılabiliyor). Kupon EV'si −27%: Nesine'nin payı yüzünden hiçbir 10 oranlı kupon artı değil. Oynamadan önce oranları tekrar kontrol edin, toplamda 0,24'lük bir tampon var. Palmeiras'ın kadrosu 21:30 civarında açıklanacak. **Bu taslak oynanmadı.**
