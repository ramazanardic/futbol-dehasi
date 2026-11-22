# 22 Kasım 2026 günün kalan bütün maçları (14:00 → 23 Kas 06:00 TSİ) — Grok Bot

Üretim 2026-11-22 10:18 TSİ · ortak hat (bülten→tahmin→derin, 20.000'lik simülasyon) · keskin referanslar 22 Kas ~10:10 TSİ tazelendi (Smarkets 242 referans, football-data/Pinnacle; OddsMath canlı) · API-Football 11/60 · `coupon_rules.calibrate_p` · değer süzgeci yok · **tarih düzeltmesi uygulandı** (PR #12: tarih = Nesine başlama günü; 00:00–06:00 maçları 23 Kasım).

**Maç sayısı:** 14:00 sonrası 448 (bunun 26'i 23 Kas gecesi 00:00–06:00) + 13:00–14:00 tazeleme = 482. Keskin fiyatlı: 245. Düzeltilmiş P ≥ 0,70 olan keskin fiyatlı izinli bacak yalnız **2** maçta.

Uygulanan dersler (`dersler_2026-11-22.json`): verisi zayıf ligde MS 1/MS 2 bacağı yok · ev/deplasman gol pazarları kupon dışı · İY ÇŞ 1X dışı · İY 1,5 Alt, İY ÇŞ X2, 2,5/3,5 Alt, 2Y KG Yok sıralamada +2 puan önde · kupon 3–5 bacak · ligde en fazla 2 bacak · geç saatli maça küçük öncelik.

## En güçlü 15 bacak (keskin fiyat önce)

| # | Gün/saat | Maç | Lig | Seçim | Oran | P (düz.) | Ima edilen | Geçmiş |
|---:|---|---|---|---|---:|---:|---:|---|
| 1 | 15:30 | SK Beveren - KAA Gent | Belçika Pro Lig | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %70.5 | %82.6 | ✓ geçmiş destekliyor |
| 2 | **23 Kas gece** 01:30 | Bragantino - Vasco Da G. | Brezilya Serie A | 1. Yarı Çifte Şans: X-2 | 1.20 | %69.4 | %83.3 | ✓ geçmiş destekliyor |
| 3 | 16:00 | Esenler Erokspor - Antalyaspor | Türkiye 1. Lig | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %69.4 | %81.3 | geçmiş yetersiz |
| 4 | 23:00 | Getafe - Atl Madrid | İspanya La Liga | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %69.0 | %82.0 | ✓ geçmiş destekliyor |
| 5 | 20:30 | Celta Vigo B - Real Valladolid | İspanya 2. Lig | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %69.0 | %83.3 | ~ geçmiş zayıf destekliyor |
| 6 | 20:30 | Girona - Eibar | İspanya 2. Lig | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %68.9 | %82.6 | ✓ geçmiş destekliyor |
| 7 | 19:30 | Sambenedettese - Perugia | İtalya Serie C | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %68.8 | %80.0 | ✓ geçmiş destekliyor |
| 8 | 20:00 | Nordsjælland - Kopenhag | Danimarka Süper Ligi | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.6 | %82.6 | ✓ geçmiş destekliyor |
| 9 | 22:45 | Marsilya - Le Mans | Fransa Ligue 1 | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %68.3 | %83.3 | ~ geçmiş zayıf destekliyor |
| 10 | 18:30 | Saarbrucken - W. Wiesbaden | Almanya 3. Lig | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.6 | %82.6 | ✓ geçmiş destekliyor |
| 11 | 19:00 | Kristiansund - Sandefjord | Norveç Eliteserien | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.3 | %82.6 | ✓ geçmiş destekliyor |
| 12 | 17:30 | Augsburg - Mainz | Almanya Bundesliga | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.5 | %82.6 | ~ geçmiş zayıf destekliyor |
| 13 | **23 Kas gece** 00:30 | Fluminense - Mirassol SP | Brezilya Serie A | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %67.9 | %81.3 | ✓ geçmiş destekliyor |
| 14 | 17:00 | AS Avellino 1912 - Mantova 1911 | İtalya Serie B | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.3 | %82.6 | ✓ geçmiş destekliyor |
| 15 | 15:30 | Kaiserslautern - D. Dresden | Almanya Bundesliga 2 | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.4 | %82.6 | ✓ geçmiş destekliyor |

## Kupon önerileri (oynanmadı)

### A — en güçlü 3–4 bacak

| Gün/saat | Maç | Seçim | Oran | P (düz.) | Geçmiş |
|---|---|---|---:|---:|---|
| 15:30 | SK Beveren - KAA Gent | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %70.5 | ✓ geçmiş destekliyor |
| 16:00 | Esenler Erokspor - Antalyaspor | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %69.4 | geçmiş yetersiz |
| 23:00 | Getafe - Atl Madrid | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %69.0 | ✓ geçmiş destekliyor |
| **23 Kas gece** 01:30 | Bragantino - Vasco Da G. | 1. Yarı Çifte Şans: X-2 | 1.20 | %69.4 | ✓ geçmiş destekliyor |

**Toplam oran 2.18 · tutma olasılığı %23.4 · TL başına beklenen değer -0.49 · ilk başlama 2026-11-22 15:30 · 150 TL → 327 TL**

### B — ~5 bacak banko

| Gün/saat | Maç | Seçim | Oran | P (düz.) | Geçmiş |
|---|---|---|---:|---:|---|
| 19:30 | Sambenedettese - Perugia | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %68.8 | ✓ geçmiş destekliyor |
| 20:00 | Nordsjælland - Kopenhag | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.6 | ✓ geçmiş destekliyor |
| 20:30 | Celta Vigo B - Real Valladolid | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %69.0 | ~ geçmiş zayıf destekliyor |
| 20:30 | Girona - Eibar | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %68.9 | ✓ geçmiş destekliyor |
| 22:45 | Marsilya - Le Mans | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %68.3 | ~ geçmiş zayıf destekliyor |

**Toplam oran 2.64 · tutma olasılığı %15.3 · TL başına beklenen değer -0.60 · ilk başlama 2026-11-22 19:30 · 150 TL → 395 TL**

### C — en yüksek oran, her bacak P ≥ 0,65

| Gün/saat | Maç | Seçim | Oran | P (düz.) | Geçmiş |
|---|---|---|---:|---:|---|
| 14:00 | A.Club De Getxo - Real Aviles | 3,5 Gol Alt/Üst: 3,5 Alt | 1.31 | %65.1 | ✓ geçmiş destekliyor |
| 15:30 | Kaiserslautern - D. Dresden | 3,5 Gol Alt/Üst: 3,5 Alt | 1.29 | %66.3 | ✓ geçmiş destekliyor |
| 16:00 | Barcelona - Villarreal | 1. Yarı 2,5 Gol Alt/Üst: 2,5 Alt | 1.29 | %65.0 | ✓ geçmiş destekliyor |
| 22:45 | Atalanta - Inter | Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır | 1.29 | %65.1 | ~ geçmiş zayıf destekliyor |
| **23 Kas gece** 00:30 | Fluminense - Mirassol SP | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.32 | %65.0 | ✓ geçmiş destekliyor |
| **23 Kas gece** 01:30 | Bragantino - Vasco Da G. | 3,5 Gol Alt/Üst: 3,5 Alt | 1.30 | %65.1 | ✓ geçmiş destekliyor |

**Toplam oran 4.83 · tutma olasılığı %7.8 · TL başına beklenen değer -0.63 · ilk başlama 2026-11-22 14:00 · 150 TL → 724 TL**

## (d) Verimli sınır — P ≥ 0,60, keskin fiyat, takım geçmişi destekli bacaklar

Amaç: her bacak sayısında P×Oran (beklenen değer) en yüksek, eşitlikte P yüksek. Kelly payı = (P·O − 1)/(O − 1).

| Bacak | Toplam oran | Tutma P | TL başına EV | Kelly payı | Bacaklar |
|---:|---:|---:|---:|---:|---|
| 2 | 1.59 | %46.5 | -0.26 | 0.00 | 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8) |
| 3 | 2.10 | %30.2 | -0.37 | 0.00 | 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8); **23 Kas gece** 00:30 Fluminense - Mirassol SP 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.32 (%65.0) |
| 4 | 2.68 | %20.2 | -0.46 | 0.00 | 14:00 D. Moskova - Krasnodar 3,5 Gol Alt/Üst: 3,5 Alt @1.28 (%66.9); 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8); **23 Kas gece** 00:30 Fluminense - Mirassol SP 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.32 (%65.0) |
| 5 | 3.46 | %13.4 | -0.54 | 0.00 | 14:00 D. Moskova - Krasnodar 3,5 Gol Alt/Üst: 3,5 Alt @1.28 (%66.9); 15:30 Kaiserslautern - D. Dresden 3,5 Gol Alt/Üst: 3,5 Alt @1.29 (%66.3); 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8); **23 Kas gece** 00:30 Fluminense - Mirassol SP 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.32 (%65.0) |
| 6 | 4.19 | %9.4 | -0.60 | 0.00 | 14:00 D. Moskova - Krasnodar 3,5 Gol Alt/Üst: 3,5 Alt @1.28 (%66.9); 15:30 Kaiserslautern - D. Dresden 3,5 Gol Alt/Üst: 3,5 Alt @1.29 (%66.3); 15:30 SK Beveren - KAA Gent 3,5 Gol Alt/Üst: 3,5 Alt @1.21 (%70.5); 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8); **23 Kas gece** 00:30 Fluminense - Mirassol SP 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.32 (%65.0) |
| 8 | 6.59 | %4.4 | -0.71 | 0.00 | 14:00 D. Moskova - Krasnodar 3,5 Gol Alt/Üst: 3,5 Alt @1.28 (%66.9); 15:30 Kaiserslautern - D. Dresden 3,5 Gol Alt/Üst: 3,5 Alt @1.29 (%66.3); 15:30 SK Beveren - KAA Gent 3,5 Gol Alt/Üst: 3,5 Alt @1.21 (%70.5); 16:00 Konyaspor - Beşiktaş Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır @1.27 (%67.5); 16:30 S. Rotterdam - AZ Alkmaar Deplasman Herhangi Bir Yarıyı Kazanır: Evet @1.25 (%68.3); 19:30 Sambenedettese - Perugia 3,5 Gol Alt/Üst: 3,5 Alt @1.25 (%68.8); **23 Kas gece** 00:00 Nashville SC - Cincinnati Deplasman Herhangi Bir Yarıyı Kazanır: Hayır @1.26 (%67.8); **23 Kas gece** 00:30 Fluminense - Mirassol SP 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.32 (%65.0) |

**Sonuç:** Hiçbir bacakta düzeltilmiş P, Nesine'nin ima ettiği olasılığı geçmiyor (en iyisi bile TL başına ≈ −0,14; Nesine marjı ~%19–22). Kelly payı her satırda 0: matematiksel olarak "pozitif beklentili" kupon yok. Kayıp, bacak sayısıyla hızla büyüyor (2 bacak −0,26 → 8 bacak −0,71). "Tatlı nokta" en az kaybettiren yer: **2–3 bacak** (P %30–46, oran 1,6–2,1). 4+ bacakta tutma olasılığı %20'nin altına iner.

## 13:00–14:00 oran tazeleme (analiz_1000_1400 bacakları + TFF 2. Lig)

| Saat | Maç | Sabahki seçim @ oran | Şimdi en iyi seçim | Oran | P (düz.) |
|---|---|---|---|---:|---:|
| 13:00 | 68 Aksaray Bld - Isparta 32 Spor | — | Nesine oranı yok | — | — |
| 13:00 | AD Cala Pozuelo - AD Torrejon | 2,5 Gol Alt/Üst: 2,5 Üst @1.57 | 2,5 Gol Alt/Üst: 2,5 Alt | 1.67 | %46.9 |
| 13:00 | Adana Demir - Aliağa Futbol | — | Nesine oranı yok | — | — |
| 13:00 | Ankaraspor - Çorlu Spor 1947 | — | Nesine oranı yok | — | — |
| 13:00 | Budapest Honved MFA - Vasas SC II | 1. Yarı Çifte Şans: 1-X @1.26 | 2. Yarı Karşılıklı Gol: Yok | 1.28 | %60.2 |
| 13:00 | CD Leganes B - Fuenlabrada | 2,5 Gol Alt/Üst: 2,5 Alt @1.54 | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.7 |
| 13:00 | Cavigal Nice SF U19 - AS Saint Etienne U19 | 3,5 Gol Alt/Üst: 3,5 Alt @1.38 | 3,5 Gol Alt/Üst: 3,5 Alt | 1.38 | %60.0 |
| 13:00 | Estac Troyes U19 - Annecy U19 | Maç Sonucu: 1 @1.36 | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %55.2 |
| 13:00 | Kahramanmaraş İstiklal Spor - Adana 01 FK | — | Nesine oranı yok | — | — |
| 13:00 | Kastamonuspor - Erbaaspor | — | Nesine oranı yok | — | — |
| 13:00 | Kütahyaspor Futbol SK - 1461 Trabzon FK | — | Nesine oranı yok | — | — |
| 13:00 | Kırklareli - Fethiyespor | — | Nesine oranı yok | — | — |
| 13:00 | Lazio U20 - Milan U20 | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.29 | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.29 | %60.3 |
| 13:00 | Merignac Sa U19 - SC Beaucouze U19 | Maç Sonucu: 1 @1.51 | 3,5 Gol Alt/Üst: 3,5 Alt | 1.44 | %56.0 |
| 13:00 | Muş SK - Hatayspor | — | Nesine oranı yok | — | — |
| 13:00 | Nyiregyhaza Spartacus II - Fuzesabony SC Eross Ut | 2. Yarı Karşılıklı Gol: Yok @1.26 | 2. Yarı Karşılıklı Gol: Yok | 1.26 | %61.0 |
| 13:00 | Paris U19 - CA Pontarlier U19 | 3,5 Gol Alt/Üst: 3,5 Alt @1.47 | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %55.2 |
| 13:00 | Sebat SK - Gebze SK | — | Nesine oranı yok | — | — |
| 13:00 | Somaspor - Elazığspor | — | Nesine oranı yok | — | — |
| 13:00 | Ujpest II - Sandorfalvi Ske | 1. Yarı Sonucu: 1 @1.42 | 1. Yarı Sonucu: 1 | 1.42 | %59.7 |
| 13:15 | CD Santurtzi Ke - SD Erandio Club | 2,5 Gol Alt/Üst: 2,5 Alt @1.47 | 2,5 Gol Alt/Üst: 2,5 Alt | 1.47 | %54.9 |
| 13:30 | Araz Nakhchivan PFK - Neftçi | Maç Sonucu: 2 @1.20 | Maç Sonucu: 2 | 1.20 | %69.6 |
| 13:30 | Batman Petrol - Muğlaspor | 3,5 Gol Alt/Üst: 3,5 Alt @1.27 | 3,5 Gol Alt/Üst: 3,5 Alt | 1.27 | %66.5 |
| 13:30 | Erzurumspor FK - Göztepe | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.21 | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.21 | %67.8 |
| 13:30 | Galapagar - Mexico | 2,5 Gol Alt/Üst: 2,5 Üst @1.54 | 2,5 Gol Alt/Üst: 2,5 Üst | 1.54 | %48.8 |
| 13:30 | Getafe B - RSD Alcala | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst @1.22 | 1. Yarı Çifte Şans: X-2 | 1.20 | %65.3 |
| 13:30 | Pena Deportiva - Lorca Deportiva | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst @1.23 | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %65.9 |
| 13:30 | SC Torrevieja - CD Bunol | 2,5 Gol Alt/Üst: 2,5 Alt @1.42 | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.4 |
| 13:30 | Santomera - Alcantarilla | Maç Sonucu: 1 @1.21 | 2,5 Gol Alt/Üst: 2,5 Üst | 1.48 | %49.5 |
| 13:30 | Scm Ramnicu V. - AFC Metalul Buzau | — | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.30 | %57.9 |
| 13:30 | Shabana - Mara Sugar | 1,5 Gol Alt/Üst: 1,5 Üst @1.34 | 1,5 Gol Alt/Üst: 1,5 Üst | 1.34 | %59.8 |
| 13:30 | T. Valderas Alcorcon - UD Sanse | Maç Sonucu: 1 @1.47 | 2,5 Gol Alt/Üst: 2,5 Üst | 1.48 | %51.8 |
| 13:30 | Viimsi JK - Kuressaare | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt @1.24 | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %61.5 |
| 13:45 | Fundacio Esportiva G. - Peralada | 2,5 Gol Alt/Üst: 2,5 Alt @1.42 | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %57.7 |

## Büyük lig maçları — en olası 3 skor

| Gün/saat | Lig | Maç | 1 / X / 2 | xG | En olası 3 skor | Haber |
|---|---|---|---|---|---|---|
| 14:15 | Hollanda Eredivisie | Twente - Willem II | %90 / %7 / %3 | 3.61–0.63 | 3-0 (%11), 4-0 (%10), 2-0 (%9) |  |
| 14:30 | İtalya Serie A | Juventus - Venezia | %70 / %19 / %11 | 2.31–0.83 | 2-0 (%12), 1-0 (%10), 2-1 (%10) | Serie A, 14:30. Juventus'ta Kalulu, González, Grabara, Locatelli, Thuram, Yıldız yok (6 eksik). Venezia'da Sverko ve Franjic yok. (IlBianconero, Eurosport) |
| 15:00 | İngiltere Championship | Burnley - Blackburn R. | %50 / %26 / %24 | 1.69–1.10 | 1-1 (%11), 1-0 (%10), 2-1 (%10) |  |
| 15:30 | Almanya Bundesliga 2 | E. Cottbus - Hertha Berlin | %19 / %20 / %61 | 1.26–2.35 | 1-2 (%9), 1-1 (%8), 0-2 (%8) |  |
| 15:30 | Almanya Bundesliga 2 | Kaiserslautern - D. Dresden | %46 / %26 / %28 | 1.65–1.24 | 1-1 (%11), 2-1 (%9), 1-0 (%9) |  |
| 15:30 | Almanya Bundesliga 2 | Karlsruhe - Osnabrück | %40 / %26 / %34 | 1.57–1.44 | 1-1 (%11), 2-1 (%9), 1-2 (%8) |  |
| 15:30 | Belçika Pro Lig | SK Beveren - KAA Gent | %25 / %26 / %49 | 1.07–1.60 | 1-1 (%12), 0-1 (%11), 1-2 (%10) |  |
| 16:00 | İspanya La Liga | Barcelona - Villarreal | %83 / %10 / %6 | 3.58–1.06 | 3-1 (%8), 3-0 (%7), 4-1 (%7) | La Liga, 16:00. Barça lider; Christensen (baldır), Rodri, Espart, Bardghji yok; Cubarsí yedek, Koundé ve Olmo yedekten dönüyor. (Sport, Marca, AS) |
| 16:00 | Türkiye Süper Ligi | Kasımpaşa - Alanyaspor | %52 / %27 / %21 | 1.67–1.01 | 1-1 (%12), 1-0 (%11), 2-1 (%10) | Süper Lig, 16:00. Kasımpaşa'da Kamil Ahmet, Frimpong, Diabate, Mouanga, Baldursson sakat, Mendes cezalı; Alanyaspor tam kadro. İki takım da son maçını 2-0 kaybetti. (Ajansspor) |
| 16:00 | Türkiye Süper Ligi | Konyaspor - Beşiktaş | %17 / %22 / %61 | 0.94–1.97 | 0-1 (%11), 0-2 (%11), 1-1 (%10) | Süper Lig 12. hafta, 16:00. Beşiktaş 4. (22 p) ama deplasmanda 5 maçta 1G 1B 3M; kaptan Orkun Kökçü cezalı, Agbadou/Miretti kadroda. Emirhan ve Trossard ceza sınırında (gelecek hafta GS derbisi). Konyaspor 15. (8 p), 8 puanın 7'sini iç sahada aldı; Adil Demirbağ ve Awaziem sakat. Hakem Çağdaş Altay. (12punto, Hürriyet, Ajansspor, Sabah) |
| 16:30 | Hollanda Eredivisie | Ajax - ADO Den Haag | %83 / %11 / %7 | 3.13–0.81 | 3-0 (%10), 2-0 (%10), 3-1 (%8) |  |
| 16:30 | Hollanda Eredivisie | S. Rotterdam - AZ Alkmaar | %22 / %23 / %55 | 1.31–2.12 | 1-2 (%10), 1-1 (%9), 0-2 (%7) |  |
| 17:00 | Yunanistan Süper Lig | APO Levadeiakos - Atromitos | %38 / %33 / %29 | 1.17–0.99 | 1-0 (%14), 1-1 (%13), 0-0 (%12) |  |
| 17:00 | İtalya Serie A | Bologna - Udinese | %54 / %26 / %20 | 1.68–0.94 | 1-0 (%12), 1-1 (%12), 2-0 (%10) |  |
| 17:00 | İngiltere Premier Lig | Hull City - Brighton | %13 / %21 / %66 | 0.84–2.09 | 0-2 (%12), 0-1 (%11), 1-2 (%10) |  |
| 17:00 | Fransa Ligue 1 | Paris - Angers | %74 / %17 / %9 | 2.53–0.82 | 2-0 (%11), 3-0 (%9), 2-1 (%9) |  |
| 17:00 | İtalya Serie A | Sassuolo - Genoa | %35 / %30 / %36 | 1.30–1.32 | 1-1 (%12), 0-1 (%10), 1-0 (%10) |  |
| 17:30 | Almanya Bundesliga | Augsburg - Mainz | %35 / %25 / %40 | 1.68–1.80 | 1-1 (%9), 1-2 (%8), 2-1 (%8) |  |
| 18:00 | Belçika Pro Lig | Kortrijk - U. S. Gilloise | %11 / %18 / %71 | 0.79–2.30 | 0-2 (%12), 0-1 (%10), 1-2 (%10) |  |
| 18:00 | Yunanistan Süper Lig | Paneitolikos - Volos | %42 / %30 / %28 | 1.34–1.07 | 1-1 (%13), 1-0 (%12), 0-1 (%10) |  |
| 18:15 | İspanya La Liga | Santander - R. Sociedad | %29 / %24 / %48 | 1.56–2.03 | 1-2 (%9), 1-1 (%9), 2-2 (%7) |  |
| 18:30 | Yunanistan Süper Lig | Panathinaikos - Ofi Crete | %80 / %13 / %7 | 2.69–0.69 | 2-0 (%12), 3-0 (%11), 1-0 (%9) |  |
| 18:45 | Hollanda Eredivisie | Go Ahead Eagles - F. Sittard | %53 / %24 / %23 | 1.92–1.19 | 1-1 (%10), 2-1 (%10), 1-0 (%8) |  |
| 19:00 | Türkiye Süper Ligi | Trabzonspor - Eyüpspor | %87 / %9 / %4 | 3.08–0.57 | 3-0 (%13), 2-0 (%12), 4-0 (%10) | Süper Lig, 19:00. Trabzonspor 2. (25 p), iç sahada 5'te 5; Nwaiwu cezalı, Okay, Aral, Malinovskyi, Batagov, Franculino sakat. Eyüpspor son sırada (3 p); Giordano, Talha, Abdullahi, Boutobba sakat (kaynaklar arasında çelişki var). (Hürriyet, A Haber, Ajansspor, Fanatik) |
| 19:15 | Fransa Ligue 1 | Lorient - Rennes | %32 / %28 / %40 | 1.17–1.33 | 1-1 (%13), 0-1 (%11), 1-0 (%10) |  |
| 19:30 | İngiltere Premier Lig | Liverpool - Man. Utd | %57 / %23 / %21 | 2.08–1.21 | 2-1 (%10), 1-1 (%9), 2-0 (%8) | Premier Lig, 19:30. Liverpool'da Van Dijk ve Szoboszlai hazır, Gravenberch ve Frimpong dönebilir; Bradley, Leoni, Ekitike yok. United'da Pochettino'nun ilk maçı; Sesko, Rashford, Ugarte dışarıda, Baleba ve Shaw şüpheli; Lisandro Martínez cezadan döndü. (liverpoolfc.com, ESPN) |
| 19:30 | Almanya Bundesliga | Werder Bremen - Hamburg | %61 / %22 / %17 | 2.08–1.04 | 2-1 (%10), 2-0 (%10), 1-1 (%10) | Bundesliga, 19:30, Kuzey derbisi. Werder'de Weiser, Grüll, Musah, Stage, Topp, Alvero, Ndiaye yok; HSV'de Lokonga, Poulsen, Remberg, Nadir, Torunarigha yok. (Weser-Kurier, Mopo) |
| 20:00 | İtalya Serie A | AC Milan - Frosinone | %60 / %21 / %19 | 2.26–1.22 | 2-1 (%10), 1-1 (%8), 2-0 (%8) | Serie A, 20:00. Milan'da Terracciano, Gabbia, Tomori, Saelemaekers, Loftus-Cheek, Chukwueze yok; Frosinone'de Bracaglia cezalı, Raimondo, Grillitsch, Terzic yok. (Eurosport) |
| 20:00 | Yunanistan Süper Lig | Olympiakos - POT Iraklis | %84 / %12 / %4 | 2.66–0.47 | 2-0 (%15), 3-0 (%14), 1-0 (%12) |  |
| 20:30 | Belçika Pro Lig | Anderlecht - O. H. Leuven | %65 / %20 / %15 | 2.20–0.96 | 2-0 (%10), 2-1 (%10), 1-0 (%9) |  |
| 20:30 | İspanya La Liga | Osasuna - Malaga | %53 / %26 / %21 | 1.60–0.94 | 1-0 (%13), 1-1 (%12), 2-0 (%10) |  |
| 20:30 | Yunanistan Süper Lig | PAOK - AE Kifisia | %72 / %18 / %10 | 2.23–0.72 | 2-0 (%13), 1-0 (%12), 3-0 (%10) |  |
| 21:15 | Belçika Pro Lig | Lommel SK - Standard Liege | %30 / %25 / %45 | 1.39–1.76 | 1-1 (%10), 1-2 (%9), 0-1 (%8) |  |
| 22:00 | Brezilya Serie A | Paranaense - Clube do Remo | %67 / %19 / %14 | 2.12–0.88 | 2-0 (%11), 1-0 (%11), 2-1 (%10) |  |
| 22:00 | Arjantin Primera Lpf, Clausura Playoff | Rosario C. - Gimnasia Y. | %69 / %20 / %11 | 2.04–0.67 | 2-0 (%14), 1-0 (%14), 3-0 (%9) |  |
| 22:45 | İtalya Serie A | Atalanta - Inter | %17 / %20 / %63 | 1.19–2.36 | 1-2 (%10), 1-1 (%8), 0-2 (%8) | Serie A, 22:45. Atalanta'da Hien, Kossounou, Pompei (ve Kristensen) yok; Inter'de Bonny ve Stankovic yok, Lautaro dönüyor. Cezalı yok. (Sky Sport, Gazzetta, PianetaAtalanta) |
| 22:45 | Fransa Ligue 1 | Marsilya - Le Mans | %67 / %19 / %14 | 2.26–0.95 | 2-0 (%10), 2-1 (%10), 1-0 (%9) |  |
| 23:00 | İspanya La Liga | Getafe - Atl Madrid | %13 / %24 / %64 | 0.67–1.75 | 0-1 (%16), 0-2 (%14), 1-1 (%10) | La Liga, 23:00. Getafe'de Gudelj cezalı, Uche ve Juanmi sakat; Atlético'da Lookman, Cuti Romero, Pubill yok. (Comuniate, Infobae) |
| **23 Kas gece** 00:00 | ABD Major Lig Playoff | Nashville SC - Cincinnati | %65 / %19 / %16 | 2.33–1.08 | 2-1 (%10), 2-0 (%9), 1-1 (%8) |  |
| **23 Kas gece** 00:30 | Brezilya Serie A | Fluminense - Mirassol SP | %60 / %23 / %17 | 1.88–0.92 | 1-0 (%11), 2-0 (%11), 1-1 (%10) |  |
| **23 Kas gece** 01:00 | Arjantin Primera Lpf, Clausura Playoff | River Plate - Lanus | %58 / %26 / %16 | 1.59–0.72 | 1-0 (%16), 2-0 (%12), 1-1 (%11) |  |
| **23 Kas gece** 01:30 | Brezilya Serie A | Bragantino - Vasco Da G. | %36 / %27 / %37 | 1.46–1.48 | 1-1 (%11), 1-2 (%8), 2-1 (%8) |  |
| **23 Kas gece** 02:07 | Meksika Prmr Ligi, Açılış | CD Guadalajara - Cruz Azul | %45 / %23 / %32 | 1.69–1.40 | 1-1 (%11), 2-1 (%9), 1-0 (%8) |  |
| **23 Kas gece** 02:30 | ABD Major Lig Playoff | Chicago Fire - Charlotte | %60 / %21 / %19 | 2.36–1.32 | 2-1 (%9), 1-1 (%8), 3-1 (%7) |  |
| **23 Kas gece** 04:00 | Arjantin Primera Lpf, Clausura Playoff | Instituto - CA Huracan | %47 / %31 / %22 | 1.21–0.73 | 1-0 (%17), 0-0 (%14), 1-1 (%13) |  |
| **23 Kas gece** 04:10 | Meksika Prmr Ligi, Açılış | Queretaro - Necaxa | %46 / %25 / %29 | 1.72–1.33 | 1-1 (%11), 2-1 (%9), 1-0 (%8) |  |
| **23 Kas gece** 04:30 | ABD Major Lig Playoff | V. Whitecaps - Real Salt Lake | %65 / %19 / %16 | 2.43–1.17 | 2-1 (%9), 2-0 (%8), 1-1 (%8) |  |

## Bütün maçlar

| Gün/saat | Lig | Maç | 1 / X / 2 | xG | En olası skor | En iyi seçim | Oran | P (düz.) | Güven | Fiyat |
|---|---|---|---|---|---|---|---:|---:|---|---|
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | 68 Aksaray Bld - Isparta 32 Spor | %55 / %23 / %23 | 1.91–1.16 | 1-1 (%10) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | İspanya 3. Federasyon | AD Cala Pozuelo - AD Torrejon | %36 / %28 / %36 | 1.42–1.41 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.67 | %46.9 | düşük | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Adana Demir - Aliağa Futbol | %3 / %6 / %90 | 0.64–3.72 | 0-3 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Ankaraspor - Çorlu Spor 1947 | %24 / %24 / %52 | 1.17–1.80 | 1-1 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Macaristan NB III, Güneydoğu Grubu | Budapest Honved MFA - Vasas SC II | %31 / %23 / %46 | 1.51–1.89 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.28 | %60.2 | düşük | OddsMath (Marathonbet) |
| 13:00 | İspanya 3. Federasyon | CD Leganes B - Fuenlabrada | %39 / %28 / %33 | 1.32–1.20 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.7 | düşük | OddsMath (Marathonbet) |
| 13:00 | Fransa U19 Ulusal Şampiyonası | Cavigal Nice SF U19 - AS Saint Etienne U19 | %50 / %23 / %27 | 2.12–1.46 | 2-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.38 | %60.0 | düşük | OddsMath (Marathonbet) |
| 13:00 | Fransa U19 Ulusal Şampiyonası | Estac Troyes U19 - Annecy U19 | %65 / %19 / %16 | 2.74–1.21 | 2-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %55.2 | düşük | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | Kahramanmaraş İstiklal Spor - Adana 01 FK | %49 / %26 / %26 | 1.64–1.14 | 1-1 (%12) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Kastamonuspor - Erbaaspor | %3 / %7 / %90 | 0.46–3.26 | 0-3 (%14) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | Kütahyaspor Futbol SK - 1461 Trabzon FK | %48 / %25 / %27 | 1.71–1.23 | 1-1 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | Kırklareli - Fethiyespor | %34 / %30 / %36 | 1.15–1.19 | 1-1 (%13) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | İtalya Campionato Primavera 1 | Lazio U20 - Milan U20 | %40 / %26 / %34 | 1.51–1.37 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.29 | %60.3 | düşük | OddsMath (Marathonbet) |
| 13:00 | Fransa U19 Ulusal Şampiyonası | Merignac Sa U19 - SC Beaucouze U19 | %56 / %21 / %22 | 2.44–1.43 | 2-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.44 | %56.0 | düşük | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Muş SK - Hatayspor | %98 / %2 / %1 | 4.09–0.14 | 4-0 (%17) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Macaristan NB III, Kuzeydoğu Grubu | Nyiregyhaza Spartacus II - Fuzesabony SC Eross Ut | %36 / %25 / %38 | 1.63–1.67 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.26 | %61.0 | düşük | OddsMath (Marathonbet) |
| 13:00 | Fransa U19 Ulusal Şampiyonası | Paris U19 - CA Pontarlier U19 | %75 / %16 / %9 | 3.06–0.87 | 3-0 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %55.2 | düşük | OddsMath (Marathonbet) |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Sebat SK - Gebze SK | — | — | — | — | — | — | yok | — |
| 13:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Somaspor - Elazığspor | %11 / %16 / %73 | 0.81–2.43 | 0-2 (%12) | — | — | — | yok | OddsMath (Marathonbet) |
| 13:00 | Macaristan NB III, Güneydoğu Grubu | Ujpest II - Sandorfalvi Ske | %78 / %14 / %8 | 2.90–0.87 | 2-0 (%10) | 1. Yarı Sonucu: 1 | 1.42 | %59.7 | düşük | OddsMath (Marathonbet) |
| 13:15 | İspanya 3. Federasyon | CD Santurtzi Ke - SD Erandio Club | %44 / %28 / %29 | 1.39–1.08 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.47 | %54.9 | düşük | OddsMath (Marathonbet) |
| 13:30 | Azerbaycan Premier Lig | Araz Nakhchivan PFK - Neftçi | %11 / %18 / %71 | 0.83–2.36 | 0-2 (%12) | Maç Sonucu: 2 | 1.20 | %69.6 | orta | Smarkets (borsa) |
| 13:30 | Türkiye 1. Lig | Batman Petrol - Muğlaspor | %56 / %24 / %20 | 1.84–1.03 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.27 | %66.5 | orta | Smarkets (borsa) |
| 13:30 | Türkiye Süper Ligi | Erzurumspor FK - Göztepe | %33 / %29 / %38 | 1.19–1.29 | 1-1 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.21 | %67.8 | orta | Smarkets (borsa) |
| 13:30 | İspanya 3. Federasyon | Galapagar - Mexico | %48 / %25 / %27 | 1.65–1.17 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.54 | %48.8 | düşük | Nesine (yerel, düşük güven) |
| 13:30 | İspanya Segunda RFEF | Getafe B - RSD Alcala | %45 / %26 / %28 | 1.45–1.09 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.20 | %65.3 | orta | OddsMath (BetInAsia/Pinnacle) |
| 13:30 | İspanya Segunda RFEF | Pena Deportiva - Lorca Deportiva | %30 / %28 / %42 | 1.14–1.40 | 1-1 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %65.9 | orta | OddsMath (BetInAsia/Pinnacle) |
| 13:30 | İspanya 3. Federasyon | SC Torrevieja - CD Bunol | %38 / %30 / %32 | 1.21–1.11 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.4 | düşük | OddsMath (Marathonbet) |
| 13:30 | İspanya 3. Federasyon | Santomera - Alcantarilla | %72 / %17 / %11 | 2.19–0.68 | 2-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.48 | %49.5 | düşük | OddsMath (Marathonbet) |
| 13:30 | Romanya 2. Lig | Scm Ramnicu V. - AFC Metalul Buzau | %31 / %25 / %44 | 1.37–1.66 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.30 | %57.9 | düşük | Smarkets (borsa) |
| 13:30 | Kenya Premier Lig | Shabana - Mara Sugar | %44 / %33 / %23 | 1.22–0.80 | 1-0 (%16) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.34 | %59.8 | düşük | OddsMath (Marathonbet) |
| 13:30 | İspanya 3. Federasyon | T. Valderas Alcorcon - UD Sanse | %61 / %22 / %17 | 2.00–0.96 | 2-0 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.48 | %51.8 | düşük | Nesine (yerel, düşük güven) |
| 13:30 | Estonya Premium Ligi Düş./Yük. | Viimsi JK - Kuressaare | %21 / %24 / %55 | 1.03–1.78 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %61.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 13:45 | İspanya 3. Federasyon | Fundacio Esportiva G. - Peralada | %52 / %27 / %22 | 1.49–0.87 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %57.7 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Primera RFEF | A.Club De Getxo - Real Aviles | %38 / %27 / %35 | 1.51–1.45 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.22 | %66.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | Portekiz Kupası | AD Sanjoanense - Academica | %18 / %22 / %60 | 0.96–1.94 | 0-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.29 | %60.0 | düşük | Smarkets (borsa) |
| 14:00 | İspanya Segunda RFEF | Alaves II - Compostela | %53 / %27 / %21 | 1.61–0.92 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.21 | %66.9 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Primera RFEF | Alcorcon - Algeciras | %66 / %17 / %17 | 2.06–0.91 | 2-0 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.24 | %66.3 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Arenas Armilla - Granada B | %52 / %27 / %22 | 1.47–0.85 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.40 | %58.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | Belarus Premier Lig | Arsenal Dzerzhinsk - Neman Grodno | %19 / %25 / %56 | 0.79–1.58 | 0-1 (%15) | 1. Yarı / 2. Yarı Karşılıklı Gol: Hayır/Hayır | 1.21 | %65.6 | orta | Pinnacle (API-Football) |
| 14:00 | İspanya 3. Federasyon | Atl Mancha Real - Malagueno | %17 / %23 / %59 | 0.82–1.75 | 0-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %52.5 | düşük | OddsMath (Marathonbet) |
| 14:00 | Tayland 1.Lig | Bangkok Utd - Ayutthaya Utd | %71 / %18 / %11 | 2.38–0.84 | 2-0 (%11) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %63.9 | düşük | Smarkets (borsa) |
| 14:00 | Bulgaristan Parva Ligi | Botev Vratsa - CSKA 1948 Sofia | %21 / %25 / %54 | 0.94–1.65 | 0-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %66.0 | orta | Smarkets (borsa) |
| 14:00 | İspanya 3. Federasyon | Burgos Promesas - Atl Bembibre | %67 / %21 / %12 | 1.95–0.68 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.56 | %50.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | CD A. Baleares - Real Murcia B | %81 / %12 / %7 | 2.56–0.57 | 2-0 (%14) | 1. Yarı Çifte Şans: 1-2 | 1.23 | %65.8 | orta | Nesine (yerel, düşük güven) |
| 14:00 | İspanya Segunda RFEF | CD Atletico Paso - Real Valladolid B | %41 / %28 / %32 | 1.58–1.37 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %67.0 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Segunda RFEF | CD Castellon B - UD Castellonense | %53 / %25 / %23 | 1.92–1.21 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.23 | %65.8 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | CD Cayon - Castro | %72 / %18 / %10 | 2.09–0.63 | 2-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.67 | %48.9 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | CD Guarnizo - CD Tropezon | %19 / %26 / %56 | 0.77–1.54 | 0-1 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.41 | %58.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | CD Huetor Vega - Atletico Porcuna | %53 / %26 / %21 | 1.62–0.94 | 1-0 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.53 | %52.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Gençler Onur Klasmanı | CD Roda U19 - UCAM Murcia U19 | %27 / %23 / %50 | 1.35–1.91 | 1-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.37 | %56.1 | düşük | Nesine (yerel, düşük güven) |
| 14:00 | İspanya 3. Federasyon | CD Subiza - CD Pamplona | %50 / %25 / %25 | 1.66–1.10 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.63 | %48.0 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Gençler Onur Klasmanı | CD Utrera U19 - Alhendin Balompie U19 | %18 / %20 / %62 | 1.12–2.21 | 1-2 (%10) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 14:00 | İspanya 3. Federasyon | CE Europa B - Mollerussa | %54 / %25 / %22 | 1.66–0.96 | 1-0 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.59 | %51.4 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | CE Mercadal - Manacor | %21 / %26 / %53 | 0.87–1.52 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.45 | %56.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Cartagena B - Mazarron | %32 / %26 / %42 | 1.29–1.53 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.72 | %46.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Chiclana - UD Tomares | %48 / %27 / %25 | 1.47–1.00 | 1-0 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.44 | %54.9 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Club Atletico Central - CD Xerez | %23 / %30 / %47 | 0.86–1.35 | 0-1 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.35 | %58.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Condal Club - Sporting Gijon B | %19 / %27 / %55 | 0.84–1.60 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.49 | %55.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Cuarte - CD Binefar | %59 / %24 / %17 | 1.73–0.81 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.1 | düşük | OddsMath (Marathonbet) |
| 14:00 | Rusya Premier Lig | D. Moskova - Krasnodar | %46 / %27 / %28 | 1.64–1.23 | 1-1 (%12) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.4 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | De San Vicente - CD Utiel | %47 / %28 / %25 | 1.39–0.94 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.44 | %58.4 | düşük | OddsMath (Marathonbet) |
| 14:00 | Ukrayna Premier Ligi | Dinamo Kiev - Obolon Kiev | %82 / %12 / %6 | 2.68–0.59 | 2-0 (%14) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %67.1 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Segunda RFEF | Don Benito - Marbella | %44 / %29 / %27 | 1.38–1.04 | 1-1 (%13) | 1. Yarı Çifte Şans: X-2 | 1.20 | %66.1 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Gençler Onur Klasmanı | Ef Mareo Logrono U19 - SD Leioa U19 | %13 / %18 / %69 | 0.99–2.47 | 0-2 (%10) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 14:00 | İspanya 3. Federasyon | El San Martin Ra - UP Langreo | %19 / %26 / %55 | 0.81–1.58 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.45 | %56.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | Erzincan FY - Karacabey Bld Spor | %67 / %20 / %13 | 2.21–0.90 | 2-0 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 14:00 | Kuzey Makedonya 1. MFL | FK Bregalnica Stip - Struga Trim | %19 / %23 / %58 | 0.93–1.82 | 0-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.27 | %63.5 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Girona B - UD Logrones B | %74 / %17 / %9 | 2.44–0.76 | 2-0 (%12) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %64.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Primera Ligi Kadınlar | Granada (K) - Real Madrid (K) | %6 / %11 / %83 | 0.82–3.74 | 0-3 (%9) | — | — | — | yok | Smarkets (borsa) |
| 14:00 | İspanya 3. Federasyon | Hercules B - Atl Saguntino | %33 / %30 / %38 | 1.10–1.20 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | Vietnam V-Ligi | Hong Linh - TP HO Chi Minh | %39 / %31 / %30 | 1.14–0.98 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.35 | %62.2 | düşük | Nesine (yerel, düşük güven) |
| 14:00 | İspanya Primera RFEF | Huesca - I. Eivissa | %45 / %28 / %27 | 1.35–0.98 | 1-0 (%13) | 1. Yarı Çifte Şans: X-2 | 1.20 | %66.1 | orta | Nesine (yerel, düşük güven) |
| 14:00 | Polonya 2. Lig | Hutnik Krakow - Resovia | %55 / %24 / %21 | 1.93–1.14 | 1-1 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.29 | %64.2 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Illescas - Toledo | %26 / %29 / %45 | 0.94–1.34 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.36 | %59.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | Tayvan Premier Ligi | Kaohsiung Attackers - AC Taipei | %49 / %24 / %27 | 1.77–1.27 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %66.8 | orta | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | LAS Rozas - Cdb Siello | %77 / %16 / %7 | 2.53–0.69 | 2-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.37 | %54.4 | düşük | OddsMath (Marathonbet) |
| 14:00 | Fransa U19 Ulusal Şampiyonası | Lyon U19 - Stade Reims U19 | %66 / %19 / %14 | 2.66–1.09 | 2-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.38 | %57.5 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Martinenc - UE Cornella | %22 / %25 / %54 | 1.03–1.75 | 1-1 (%11) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %47.5 | düşük | OddsMath (Marathonbet) |
| 14:00 | Türkiye Nesine  2. Lig, Beyaz Grup | Menemen FK - Şanlıurfaspor | %13 / %19 / %68 | 0.89–2.23 | 0-2 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Mijas Las Lagunas - Las Palmas B | %55 / %25 / %20 | 1.82–1.03 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %60.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Montanesa - Atletic Lleida CE | %32 / %31 / %37 | 1.07–1.17 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.39 | %58.7 | düşük | OddsMath (Marathonbet) |
| 14:00 | Tayland Şampiyonası | Nakhon R. - Khon Kaen Utd | %46 / %26 / %28 | 1.60–1.19 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.71 | %46.9 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Naxara CD - CD Ebro | %23 / %27 / %50 | 0.99–1.55 | 0-1 (%12) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %66.0 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | Özbekistan Süper Ligi | PFK Dinamo Samarqand - Bunyodkor | %62 / %18 / %20 | 2.06–1.05 | 2-1 (%10) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.34 | %58.9 | düşük | Pinnacle (API-Football) |
| 14:00 | İspanya 3. Federasyon | Palencia - Guijuelo | %42 / %28 / %30 | 1.33–1.07 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.46 | %56.3 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Pozuelo De Alarcon - Mostoles Urjc | %26 / %27 / %47 | 1.15–1.60 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.63 | %48.3 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Gençler Onur Klasmanı | RC Celta de Vigo U19 - CD Marina U19 | — | — | — | — | — | — | yok | — |
| 14:00 | İspanya Segunda RFEF | RCD Mallorca B - CD Cieza | %37 / %27 / %36 | 1.35–1.33 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %64.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Racing Club Portuense - Cordoba B | %66 / %21 / %13 | 1.95–0.74 | 1-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.67 | %49.5 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Racing Club Villalbes - CD Barco | %36 / %29 / %35 | 1.12–1.09 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.38 | %59.0 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Real Oviedo B - Atletico Astorga | %58 / %25 / %17 | 1.86–0.92 | 1-0 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.8 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | Moldova Ulusal Lig  | Real Sireti - Petrocub | %11 / %17 / %71 | 0.79–2.29 | 0-2 (%12) | 1. Yarı Çifte Şans: 1-2 | 1.28 | %61.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Primera Ligi Kadınlar | Real Sociedad (K) - Sevilla (K) | %66 / %20 / %14 | 2.29–0.86 | 2-0 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.54 | %52.3 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Gençler Onur Klasmanı | Real Valladolid U19 - CD Un. Salamanca U19 | %80 / %12 / %8 | 3.21–0.99 | 3-0 (%8) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 14:00 | İspanya 3. Federasyon | SD Formentera - CD Cardassar | %55 / %25 / %20 | 1.65–0.88 | 1-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.53 | %53.1 | düşük | OddsMath (Marathonbet) |
| 14:00 | Vietnam V-Ligi | SHB Da Nang - Phu Dong | %28 / %25 / %47 | 1.20–1.63 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.27 | %61.1 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | San Cristobal Cp - UE Tona | %37 / %30 / %33 | 1.20–1.13 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.4 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Sevilla C - RB Linense | %30 / %29 / %41 | 1.01–1.25 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.41 | %60.0 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Gençler Onur Klasmanı | Sevilla U19 - Granada U19 | %69 / %18 / %13 | 2.28–0.88 | 2-0 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.41 | %53.8 | düşük | Nesine (yerel, düşük güven) |
| 14:00 | Tayland Şampiyonası | Songkhla - SGB Kanchanaburi | %36 / %26 / %38 | 1.42–1.47 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.47 | %50.0 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Torre Del Mar - UD San Pedro | %37 / %30 / %33 | 1.13–1.06 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.34 | %59.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | Torrent - Levante B | %29 / %29 / %42 | 1.06–1.33 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %56.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya 3. Federasyon | UC Ceares - Covadonga | %9 / %17 / %75 | 0.58–2.20 | 0-2 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.73 | %47.2 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Primera RFEF | UD Ourense - Racing  Ferrol | %21 / %27 / %52 | 0.89–1.56 | 0-1 (%14) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.25 | %67.9 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | UD Socuellamos - Villacanas | %36 / %32 / %33 | 1.08–1.02 | 1-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.32 | %62.0 | düşük | OddsMath (Marathonbet) |
| 14:00 | İspanya Segunda RFEF | Ucam Murcia - Y.Deportivo | %55 / %27 / %18 | 1.63–0.85 | 1-0 (%14) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %65.1 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | Polonya 1. Lig | Unia Skier - Pogon Siedl. | %48 / %24 / %28 | 1.83–1.36 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.25 | %64.3 | düşük | Smarkets (borsa) |
| 14:00 | İspanya Segunda RFEF | Utebo - Calamocha | %69 / %20 / %12 | 1.99–0.67 | 1-0 (%14) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %64.8 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya Gençler Onur Klasmanı | Valencia U19 - Cartagena U19 | — | — | — | — | — | — | yok | — |
| 14:00 | İspanya 3. Federasyon | Varea - Casalarreina | %88 / %8 / %3 | 2.98–0.41 | 2-0 (%15) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.39 | %56.8 | düşük | OddsMath (Marathonbet) |
| 14:00 | Ukrayna Premier Ligi | Veres Rivne - Bukovina Chernovtsy | %25 / %26 / %49 | 1.16–1.70 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %60.7 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:00 | İspanya 3. Federasyon | Viveiro - UD Somozas | %29 / %29 / %42 | 1.02–1.27 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.41 | %59.6 | düşük | OddsMath (Marathonbet) |
| 14:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | İskenderunspor - Ankaragücü | %12 / %19 / %69 | 0.80–2.19 | 0-2 (%12) | — | — | — | yok | OddsMath (Marathonbet) |
| 14:15 | Polonya Ekstraklasa | Rakow C. - Widzew Lodz | %48 / %26 / %27 | 1.70–1.22 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.26 | %65.4 | orta | Smarkets (borsa) |
| 14:15 | Hollanda Eredivisie Kadınlar | SC Heerenveen (K) - ADO Den Haag (K) | %58 / %21 / %21 | 2.38–1.30 | 2-1 (%9) | Maç Sonucu: 1 | 1.50 | %58.3 | düşük | OddsMath (Marathonbet) |
| 14:15 | Hollanda Eredivisie | Twente - Willem II | %90 / %7 / %3 | 3.61–0.63 | 3-0 (%11) | 1. Yarı 2,5 Gol Alt/Üst: 2,5 Alt | 1.22 | %68.5 | orta | Smarkets (borsa) |
| 14:15 | İspanya Gençler Onur Klasmanı | Ural U19 - G. de Torrelavega U19 | %55 / %23 / %23 | 2.03–1.27 | 2-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.35 | %57.1 | düşük | Nesine (yerel, düşük güven) |
| 14:30 | İspanya 3. Federasyon | A. Coruna Montaneros - Pontevedra B | %44 / %27 / %29 | 1.46–1.15 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %51.4 | düşük | OddsMath (Marathonbet) |
| 14:30 | İspanya Segunda RFEF | CA Antoniano - Salerm Puente Genil | %43 / %30 / %27 | 1.32–0.98 | 1-0 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.29 | %61.4 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:30 | Tayland 1.Lig | Chiangrai Utd - Lamphun Warrior | %40 / %29 / %31 | 1.36–1.17 | 1-1 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %65.9 | orta | Smarkets (borsa) |
| 14:30 | İtalya Serie A, Kadınlar | Como (K) - AS Roma (K) | %15 / %18 / %67 | 1.01–2.52 | 1-2 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.39 | %59.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:30 | Singapur Premier Lig | Hougang Utd - Tampines Rov. | %13 / %16 / %70 | 0.99–2.50 | 0-2 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.23 | %66.5 | orta | Smarkets (borsa) |
| 14:30 | İtalya Serie A | Juventus - Venezia | %70 / %19 / %11 | 2.31–0.83 | 2-0 (%12) | Maç Sonucu: 1 | 1.23 | %68.7 | orta | Smarkets (borsa) |
| 14:30 | İspanya 3. Federasyon | Lanzarote UD - CD Union Sur Yaiza | %43 / %28 / %29 | 1.34–1.07 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.46 | %56.3 | düşük | OddsMath (Marathonbet) |
| 14:30 | Singapur Premier Lig | Lion C. Sailors - Geylang | %76 / %15 / %9 | 2.63–0.80 | 2-0 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.57 | %56.1 | düşük | Smarkets (borsa) |
| 14:30 | İspanya 3. Federasyon | Moralo CP - AD Llerenense | %55 / %26 / %20 | 1.58–0.83 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.45 | %56.3 | düşük | OddsMath (Marathonbet) |
| 14:30 | Tayland Şampiyonası | Muang Loei Utd - Uttaradit | %31 / %26 / %43 | 1.29–1.55 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.50 | %48.8 | düşük | OddsMath (Marathonbet) |
| 14:30 | Polonya 2. Lig | Olimpia - G. Leczna | %39 / %28 / %34 | 1.50–1.39 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %64.7 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:30 | İtalya Serie C | Pro Vercelli - Novara Calcio | %31 / %30 / %39 | 1.16–1.33 | 1-1 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %67.6 | orta | Smarkets (borsa) |
| 14:30 | İspanya 3. Federasyon | Rayo Vallecano B - AD Union Adarve | %38 / %28 / %34 | 1.42–1.33 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.64 | %48.3 | düşük | OddsMath (Marathonbet) |
| 14:30 | İspanya Segunda RFEF | Reus Reddis - UE Olot | %47 / %29 / %24 | 1.34–0.87 | 1-0 (%15) | 1. Yarı Çifte Şans: X-2 | 1.22 | %65.1 | orta | OddsMath (BetInAsia/Pinnacle) |
| 14:30 | İtalya Serie C | Scafatese Calcio 1922 - Foggia | %38 / %27 / %35 | 1.35–1.29 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %65.2 | orta | Smarkets (borsa) |
| 14:30 | İtalya Serie A, Kadınlar | Ternana (K) - Inter (K) | %11 / %16 / %74 | 0.80–2.65 | 0-2 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.37 | %53.8 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 14:30 | İspanya 3. Federasyon | UD Los Garres - Atl Santa Cruz | %22 / %27 / %51 | 0.88–1.49 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %57.2 | düşük | OddsMath (Marathonbet) |
| 14:30 | İtalya Serie C | Union Brescia - AC Renate | %68 / %20 / %12 | 2.10–0.76 | 2-0 (%13) | Maç Sonucu: 1 | 1.24 | %66.8 | orta | Smarkets (borsa) |
| 14:30 | İspanya 3. Federasyon | Xerez Deportivo - Cd Pozoblanco | %67 / %20 / %13 | 2.02–0.74 | 2-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.69 | %48.0 | düşük | OddsMath (Marathonbet) |
| 14:45 | Hırvatistan Prva NL | NK Croatia Zmijavci - NK Karlovac 1919 | %50 / %26 / %25 | 1.57–1.03 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %51.4 | düşük | OddsMath (Marathonbet) |
| 15:00 | Kosova Superliga | Ballkani - SC Gjilani | %42 / %28 / %30 | 1.37–1.12 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.51 | %54.2 | düşük | OddsMath (Marathonbet) |
| 15:00 | Türkiye Nesine 2. Lig, Kırmızı Grup | Beyoğlu Y. Çarşı - İnegölspor | %64 / %22 / %14 | 2.06–0.88 | 2-0 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 15:00 | İngiltere Kadınlar Süper Ligi | Birmingham City (K) - Man. Utd (K) | %16 / %20 / %63 | 0.98–2.26 | 0-2 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.36 | %58.6 | düşük | Smarkets (borsa) |
| 15:00 | İngiltere Championship | Burnley - Blackburn R. | %50 / %26 / %24 | 1.69–1.10 | 1-1 (%11) | — | — | — | yok | Smarkets (borsa) |
| 15:00 | Macaristan NB III, Güneydoğu Grubu | Dabas - Bss Monor | %40 / %24 / %36 | 1.74–1.67 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.27 | %59.7 | düşük | OddsMath (Marathonbet) |
| 15:00 | Macaristan NB III, Güneydoğu Grubu | Esmtk Budapest - Csepel | %74 / %16 / %9 | 2.69–0.90 | 2-0 (%10) | 1. Yarı Sonucu: 1 | 1.50 | %56.4 | düşük | OddsMath (Marathonbet) |
| 15:00 | Çekya 1. Lig | FK Pardubice - Brno | %53 / %25 / %22 | 1.80–1.11 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %65.7 | orta | Smarkets (borsa) |
| 15:00 | Kenya Premier Lig | KCB Nairobi - 3K | %56 / %26 / %18 | 1.50–0.71 | 1-0 (%16) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.36 | %59.2 | düşük | OddsMath (Marathonbet) |
| 15:00 | Türkiye Nesine 3. Lig, 2. Grup | Karşıyaka - Alanya 1221 Futbol SK | %84 / %11 / %5 | 2.76–0.54 | 2-0 (%14) | — | — | — | yok | OddsMath (Marathonbet) |
| 15:00 | İspanya Segunda RFEF | Linares Dep. - A. Sanluqueno | %48 / %26 / %26 | 1.55–1.06 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %65.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 15:00 | İngiltere Kadınlar Süper Ligi | Man. City (K) - Tottenham Hotspur (K) | %69 / %17 / %14 | 2.93–1.18 | 2-1 (%8) | — | — | — | yok | Smarkets (borsa) |
| 15:00 | Macaristan NB III, Güneybatı Grubu | PTE Peac - Budafoki Mte | %38 / %23 / %39 | 1.58–1.60 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %64.4 | düşük | OddsMath (Marathonbet) |
| 15:00 | Endonezya 1. Lig | Persib Bandung - Bali Utd | %62 / %21 / %17 | 2.12–1.03 | 2-1 (%10) | — | — | — | yok | Smarkets (borsa) |
| 15:00 | Tayland Şampiyonası | Phrae Utd - Nongbua Pitc. | %36 / %25 / %38 | 1.46–1.50 | 1-1 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.46 | %51.8 | düşük | OddsMath (Marathonbet) |
| 15:00 | Sırbistan Superliga | Radnicki - FK Cukaricki | %48 / %26 / %26 | 1.66–1.18 | 1-1 (%11) | 1. Yarı Çifte Şans: X-2 | 1.26 | %61.3 | düşük | Smarkets (borsa) |
| 15:00 | Tayland 1.Lig | Rayong - Rasisalai Utd | %63 / %20 / %16 | 2.17–1.01 | 2-1 (%10) | Maç Sonucu: 1 | 1.32 | %61.3 | düşük | Smarkets (borsa) |
| 15:00 | Macaristan 2. Ligi | Szentlorinc SE - Kecskemeti TE | %11 / %18 / %71 | 0.79–2.29 | 0-2 (%12) | 1. Yarı Çifte Şans: 1-2 | 1.25 | %61.6 | düşük | OddsMath (Marathonbet) |
| 15:00 | İspanya Gençler Onur Klasmanı | UD Las Palmas U19 - Longuera Toscal U19 | — | — | — | — | — | — | yok | — |
| 15:00 | Türkiye Nesine  2. Lig, Beyaz Grup | İnegöl Kafkas SK - Arnavutköy Bld FSK | %76 / %15 / %9 | 2.48–0.71 | 2-0 (%13) | — | — | — | yok | OddsMath (Marathonbet) |
| 15:15 | Lübnan Premier Lig | AL Tadamon Sour - Jwaaya | %11 / %21 / %68 | 0.68–2.00 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.60 | %49.8 | düşük | OddsMath (Marathonbet) |
| 15:15 | Lübnan Premier Lig | Tripoli AC - Reyady Abaseya | %56 / %26 / %19 | 1.62–0.83 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.47 | %55.2 | düşük | OddsMath (Marathonbet) |
| 15:30 | Türkiye Nesine 2. Lig, Kırmızı Grup | 52 Orduspor FK - 12 Bingöl Spor | %74 / %18 / %9 | 2.37–0.71 | 2-0 (%13) | — | — | — | yok | OddsMath (Marathonbet) |
| 15:30 | Filipinler Futbol Ligi | Davao Aguilas - Stallion | %66 / %17 / %17 | 2.53–1.23 | 2-1 (%9) | 1. Yarı Çifte Şans: 1-2 | 1.22 | %65.9 | orta | OddsMath (Marathonbet) |
| 15:30 | Almanya Bundesliga 2 | E. Cottbus - Hertha Berlin | %19 / %20 / %61 | 1.26–2.35 | 1-2 (%9) | Gol Alt/Üst: 4.5 Alt | 1.21 | %68.2 | orta | Smarkets (borsa) |
| 15:30 | Etiyopya Premier Lig | Ethiopia Electricity - Halaba Ketema | %45 / %32 / %23 | 1.12–0.70 | 1-0 (%18) | 1. Yarı Tek/Çift: Çift | 1.37 | %58.2 | düşük | OddsMath (Marathonbet) |
| 15:30 | Arnavutluk Süper Ligi | FK Vora - KF Tirana | %31 / %26 / %44 | 1.30–1.58 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.29 | %60.4 | düşük | OddsMath (Marathonbet) |
| 15:30 | Almanya Bundesliga 2 | Kaiserslautern - D. Dresden | %46 / %26 / %28 | 1.65–1.24 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.4 | orta | Smarkets (borsa) |
| 15:30 | Almanya Bundesliga 2 | Karlsruhe - Osnabrück | %40 / %26 / %34 | 1.57–1.44 | 1-1 (%11) | Ev Sahibi İki Yarıda da Gol: Atamaz | 1.21 | %69.4 | orta | Smarkets (borsa) |
| 15:30 | Bulgaristan 2. Lig | Montana 1921 - Dobrudzha Dobrich | %60 / %22 / %18 | 1.95–0.99 | 1-0 (%10) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.30 | %59.4 | düşük | OddsMath (Marathonbet) |
| 15:30 | Hırvatistan Prva NL | NK Jadran LP - HNK Cibalia Vinkovci | %55 / %24 / %21 | 1.74–1.00 | 1-0 (%11) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.68 | %48.3 | düşük | OddsMath (Marathonbet) |
| 15:30 | Norveç Eliteserien, Düş./Yük. | Odds BK - Bryne | %46 / %24 / %30 | 1.85–1.45 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.31 | %62.2 | düşük | Smarkets (borsa) |
| 15:30 | Kenya Premier Lig | Posta Ranger - Gor Mahia | %17 / %28 / %55 | 0.65–1.42 | 0-1 (%18) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.31 | %60.7 | düşük | OddsMath (Marathonbet) |
| 15:30 | Çekya 2. Lig | S B Vlasim - SK Prostej | %51 / %25 / %24 | 1.68–1.06 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.30 | %63.6 | düşük | Smarkets (borsa) |
| 15:30 | Belçika Pro Lig | SK Beveren - KAA Gent | %25 / %26 / %49 | 1.07–1.60 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %70.5 | yüksek | Smarkets (borsa) |
| 15:30 | Çekya 2. Lig | SK Kladno - Jihlava | %34 / %27 / %39 | 1.45–1.57 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.22 | %65.9 | orta | Smarkets (borsa) |
| 15:30 | Türkiye Nesine 2. Lig, Kırmızı Grup | Sakaryaspor - Serik Spor | %67 / %20 / %13 | 2.22–0.90 | 2-0 (%11) | — | — | — | yok | OddsMath (Marathonbet) |
| 15:30 | Almanya 3. Lig | Stuttgart II - Ingolstadt | %33 / %25 / %42 | 1.39–1.60 | 1-1 (%11) | — | — | — | yok | Smarkets (borsa) |
| 15:30 | Macaristan 1. Ligi | Zalaegerszeg - Vasas | %44 / %26 / %30 | 1.53–1.22 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 15:35 | Suudi Arabistan 2. Lig, 1. Grup | Hetten - Arar | %41 / %25 / %33 | 1.45–1.27 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.64 | %49.1 | düşük | Nesine (yerel, düşük güven) |
| 15:35 | Umman Ligi | Sur SC - Sohar | %34 / %28 / %38 | 1.27–1.37 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.60 | %50.8 | düşük | OddsMath (Marathonbet) |
| 15:40 | BAE 1.Lig | Emirates Club - AL Ittifaq | %60 / %22 / %18 | 2.10–1.07 | 2-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.36 | %54.4 | düşük | OddsMath (Marathonbet) |
| 15:40 | BAE 1.Lig | Fujairah - Al Urooba (Bae) | %22 / %24 / %54 | 1.07–1.81 | 1-1 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.49 | %50.0 | düşük | OddsMath (Marathonbet) |
| 15:45 | İspanya Gençler Onur Klasmanı | Elche U19 - Kelme U19 | — | — | — | — | — | — | yok | — |
| 16:00 | Danimarka Süper Ligi | AC Horsens - Silkeborg | %42 / %27 / %31 | 1.54–1.31 | 1-1 (%12) | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %68.0 | orta | Smarkets (borsa) |
| 16:00 | Ruanda Ulusal Lig | Al Merrikh (Sdn) - Gorilla | %71 / %20 / %9 | 1.74–0.41 | 1-0 (%20) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.35 | %62.2 | düşük | Nesine (yerel, düşük güven) |
| 16:00 | İsveç Allsvenskan | BK Hacken - IF Elfsborg | %53 / %22 / %25 | 1.96–1.29 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.26 | %64.6 | düşük | Smarkets (borsa) |
| 16:00 | Moldova Ulusal Lig  | Balti - Dacia Buiucani | %1 / %2 / %98 | 0.08–3.62 | 0-3 (%20) | — | — | — | yok | OddsMath (Marathonbet) |
| 16:00 | İspanya La Liga | Barcelona - Villarreal | %83 / %10 / %6 | 3.58–1.06 | 3-1 (%8) | Gol Alt/Üst: 5.5 Alt | 1.24 | %66.8 | orta | Smarkets (borsa) |
| 16:00 | İngiltere U21 Premier Lig Kupası | Brentford U21 - Hull City U21 | %55 / %17 / %28 | 2.76–1.90 | 2-1 (%7) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %68.4 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:00 | Mozambik Mocambola | CD Maxaquene - Baia de Pemba | %25 / %30 / %45 | 0.74–1.11 | 0-1 (%17) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.44 | %58.4 | düşük | OddsMath (Marathonbet) |
| 16:00 | İspanya 2. Lig | Cordoba - Real Oviedo | %49 / %25 / %26 | 1.78–1.26 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.24 | %66.6 | orta | Smarkets (borsa) |
| 16:00 | Almanya Böl. Lig, Kuzey  | Eintracht Norder. - FSV Schoningen 2011 | %32 / %22 / %46 | 1.76–2.11 | 1-2 (%8) | 1. Yarı Çifte Şans: 1-2 | 1.25 | %64.3 | düşük | OddsMath (Marathonbet) |
| 16:00 | Türkiye 1. Lig | Esenler Erokspor - Antalyaspor | %54 / %24 / %22 | 1.74–1.01 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %69.4 | orta | Smarkets (borsa) |
| 16:00 | Ruanda Ulusal Lig | Etincelles - AS Kigali | %38 / %31 / %31 | 1.09–0.96 | 1-0 (%14) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 16:00 | Azerbaycan Premier Lig | FK Kapaz - Karabağ | %10 / %20 / %70 | 0.62–2.02 | 0-2 (%14) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %65.3 | orta | Smarkets (borsa) |
| 16:00 | Ruanda Ulusal Lig | Gicumbi - Musanze | %46 / %30 / %25 | 1.27–0.86 | 1-0 (%15) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 16:00 | Zambiya Süper Lig, Grup B | Green Eagles - Red Arrows | %37 / %33 / %30 | 0.99–0.85 | 0-0 (%16) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 16:00 | Almanya Böl. Lig, Kuzey  | Hannoverscher - Lubeck | %31 / %24 / %45 | 1.50–1.84 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.27 | %61.3 | düşük | OddsMath (Marathonbet) |
| 16:00 | İsveç Allsvenskan | IK Sirius - Djurgarden | %40 / %27 / %33 | 1.52–1.37 | 1-1 (%12) | 2. Yarı Karşılıklı Gol: Yok | 1.22 | %67.5 | orta | Smarkets (borsa) |
| 16:00 | Türkiye Süper Ligi | Kasımpaşa - Alanyaspor | %52 / %27 / %21 | 1.67–1.01 | 1-1 (%12) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %68.0 | orta | Smarkets (borsa) |
| 16:00 | Türkiye Süper Ligi | Konyaspor - Beşiktaş | %17 / %22 / %61 | 0.94–1.97 | 0-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.28 | %66.2 | orta | Smarkets (borsa) |
| 16:00 | Türkiye 1. Lig | Manisa FK - Pendikspor | %43 / %25 / %31 | 1.57–1.31 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 16:00 | Ruanda Ulusal Lig | Mukura - Sunrise | %55 / %27 / %18 | 1.50–0.73 | 1-0 (%16) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 16:00 | Zambiya Süper Lig, Grup A | Nchanga Rangers - Trident | %44 / %32 / %24 | 1.15–0.76 | 1-0 (%17) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 16:00 | Etiyopya Premier Lig | Negelle Arsi - Gamo Chencha | %42 / %31 / %27 | 1.10–0.81 | 1-0 (%16) | 1. Yarı Tek/Çift: Çift | 1.38 | %59.7 | düşük | OddsMath (Marathonbet) |
| 16:00 | Almanya Böl. Lig, Bavyera | Nürnberg (Amt) - Vilzing | %62 / %19 / %19 | 2.42–1.31 | 2-1 (%9) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %65.2 | orta | OddsMath (Marathonbet) |
| 16:00 | İngiltere U21 Premier Lig Kupası | Peterborough Utd U21 - Luton Town U21 | %65 / %14 / %21 | 3.23–1.74 | 3-1 (%7) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Üst | 1.49 | %64.4 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 16:00 | Almanya Böl. Lig, Kuzey  | Phonix Lubeck - St. Pauli II | %71 / %17 / %13 | 2.58–1.03 | 2-1 (%9) | Maç Sonucu: 1 | 1.23 | %69.0 | orta | OddsMath (Marathonbet) |
| 16:00 | Almanya Kadınlar Bundesliga | SC Freiburg (K) - VfB Stuttgart (K) | %36 / %24 / %39 | 1.76–1.83 | 1-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.39 | %59.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 16:00 | Almanya Böl. Lig, Güney Batı | Sandhausen - Stuttgarter Kickers | %41 / %24 / %35 | 1.70–1.57 | 1-1 (%10) | 1. Yarı Çifte Şans: X-2 | 1.20 | %65.8 | orta | OddsMath (Marathonbet) |
| 16:00 | Slovenya 2. Lig | Tabor Sezana - NK Jesenice | %66 / %20 / %15 | 2.13–0.89 | 2-0 (%11) | 1. Yarı Çifte Şans: 1-2 | 1.27 | %60.3 | düşük | OddsMath (Marathonbet) |
| 16:00 | Danimarka Süper Ligi | Viborg - Randers | %62 / %20 / %17 | 2.23–1.10 | 2-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.24 | %65.5 | orta | Smarkets (borsa) |
| 16:00 | İsviçre Süper Lig | Zürih - St. Gallen | %29 / %24 / %47 | 1.46–1.90 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.33 | %60.9 | düşük | Smarkets (borsa) |
| 16:30 | Hollanda Eredivisie | Ajax - ADO Den Haag | %83 / %11 / %7 | 3.13–0.81 | 3-0 (%10) | Gol Alt/Üst: 4.5 Alt | 1.33 | %61.5 | düşük | Smarkets (borsa) |
| 16:30 | İtalya Serie C | Alcione Milano - Acd Ospitaletto | %33 / %28 / %39 | 1.17–1.31 | 1-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 16:30 | Avusturya Bundesliga | Altach - Sturm Graz | %25 / %26 / %49 | 1.13–1.66 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.24 | %68.3 | orta | Smarkets (borsa) |
| 16:30 | İtalya Serie C | Altamura - Casarano | %42 / %29 / %29 | 1.44–1.17 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.6 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Amiens U19 - C Chartres Football U19 | %73 / %16 / %11 | 3.03–1.00 | 3-0 (%8) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.51 | %54.2 | düşük | OddsMath (Marathonbet) |
| 16:30 | Tunus 1. Lig | Club Africain - Esperance T. | %29 / %39 / %32 | 0.88–0.94 | 0-0 (%16) | 1. Yarı Tek/Çift: Çift | 1.37 | %58.2 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 16:30 | Rusya Premier Lig | Dyn. Makhachkala - S. Moskova | %14 / %20 / %65 | 0.84–2.04 | 0-2 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %67.2 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:30 | Tunus 1. Lig | ES Zarzis - US Ben Guerdane | %39 / %33 / %28 | 1.08–0.87 | 1-0 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.21 | %67.5 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:30 | Polonya 1. Lig | Lechia Gdansk - Odra Opole | %49 / %25 / %26 | 1.74–1.22 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.28 | %65.0 | orta | Smarkets (borsa) |
| 16:30 | Bulgaristan Parva Ligi | Levski Sofya - Loko Sofya | %80 / %15 / %5 | 2.55–0.56 | 2-0 (%15) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.41 | %58.9 | düşük | Smarkets (borsa) |
| 16:30 | İtalya Serie C | Livorno - Ravenna 1913 | %22 / %26 / %52 | 0.92–1.58 | 0-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 16:30 | Güney Afrika Lig Kupası | Mamel Sundow - Kaizer Chiefs | %58 / %24 / %18 | 1.76–0.86 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.5 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Metz U19 - Nancy-Lorraine U19 | %54 / %23 / %23 | 2.07–1.25 | 2-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.40 | %54.2 | düşük | OddsMath (Marathonbet) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Racing U19 - US Orleans U19 | %56 / %22 / %22 | 2.31–1.33 | 2-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.38 | %59.1 | düşük | OddsMath (Marathonbet) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Rouen U19 - SM Caen U19 | %20 / %20 / %60 | 1.38–2.57 | 1-2 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.50 | %54.5 | düşük | OddsMath (Marathonbet) |
| 16:30 | Hollanda Eredivisie | S. Rotterdam - AZ Alkmaar | %22 / %23 / %55 | 1.31–2.12 | 1-2 (%10) | Deplasman Herhangi Bir Yarıyı Kazanır: Evet | 1.25 | %68.3 | orta | Smarkets (borsa) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Stade Briochin U19 - Stade Laval U19 | %21 / %22 / %57 | 1.32–2.37 | 1-2 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.41 | %58.4 | düşük | OddsMath (Marathonbet) |
| 16:30 | İtalya Serie C | Torres Sassari - Spezia | %15 / %25 / %60 | 0.71–1.66 | 0-1 (%16) | Maç Sonucu: 2 | 1.42 | %59.8 | düşük | Smarkets (borsa) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | US Cap D Ail U19 - Bastia U19 | %24 / %24 / %52 | 1.21–1.96 | 1-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.44 | %51.3 | düşük | OddsMath (Marathonbet) |
| 16:30 | İtalya Serie C | US Pianese - AS Gubbio 1910 | %48 / %27 / %25 | 1.54–1.06 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.6 | orta | Smarkets (borsa) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | USL Dunkerque U19 - Le Havre U19 | %39 / %25 / %37 | 1.68–1.62 | 1-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.40 | %54.2 | düşük | OddsMath (Marathonbet) |
| 16:30 | Fransa U19 Ulusal Şampiyonası | Valenciennes U19 - Versailles 78 U19 | %77 / %15 / %8 | 3.09–0.78 | 3-0 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %56.8 | düşük | OddsMath (Marathonbet) |
| 16:30 | Avusturya Bundesliga | Wolfsberger - SV Ried | %34 / %25 / %42 | 1.45–1.63 | 1-1 (%11) | Deplasman İki Yarıda da Gol: Atamaz | 1.22 | %68.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 16:45 | Polonya Ekstraklasa | Katowice - Lech Poznan | %31 / %24 / %45 | 1.57–1.92 | 1-1 (%9) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.23 | %61.7 | düşük | Smarkets (borsa) |
| 17:00 | Yunanistan Süper Lig | APO Levadeiakos - Atromitos | %38 / %33 / %29 | 1.17–0.99 | 1-0 (%14) | 1. Yarı / 2. Yarı Karşılıklı Gol: Hayır/Hayır | 1.21 | %65.4 | orta | Smarkets (borsa) |
| 17:00 | İtalya Serie B | AS Avellino 1912 - Mantova 1911 | %38 / %30 / %32 | 1.39–1.26 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.3 | orta | Smarkets (borsa) |
| 17:00 | Fransa U19 Ulusal Şampiyonası | AS Beziers U19 - US Colomiers U19 | %69 / %18 / %13 | 2.92–1.14 | 2-1 (%8) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.20 | %63.4 | düşük | OddsMath (1XBET) |
| 17:00 | İsviçre Yükselme 1.Ligi | BSC Young Boys - YF Juventus | %31 / %24 / %45 | 1.74–2.11 | 1-2 (%8) | 3,5 Gol Alt/Üst: 3,5 Üst | 1.58 | %51.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | İsviçre Yükselme 1.Ligi | Biel Bienne - Bellinzona | %64 / %19 / %17 | 2.36–1.14 | 2-1 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.49 | %55.3 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | İtalya Serie A | Bologna - Udinese | %54 / %26 / %20 | 1.68–0.94 | 1-0 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %66.4 | orta | Smarkets (borsa) |
| 17:00 | İsviçre Yükselme 1.Ligi | Bulle - SC Bruhl ST Gallen | %41 / %25 / %34 | 1.95–1.78 | 1-1 (%8) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.61 | %50.2 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | İtalya Serie C | Calcio Catania - SSC Bari | %49 / %27 / %24 | 1.46–0.93 | 1-0 (%13) | — | — | — | yok | Smarkets (borsa) |
| 17:00 | İngiltere Kadınlar Süper Ligi | Charlton Ath (K) - Aston Villa (K) | %15 / %21 / %64 | 0.91–2.22 | 0-2 (%11) | — | — | — | yok | Smarkets (borsa) |
| 17:00 | Hindistan Süper Ligi | Churchill B. SC - Mohun Bagan | %14 / %20 / %66 | 0.90–2.14 | 0-2 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.31 | %63.8 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | Belarus Premier Lig | D. Minsk - Minsk | %81 / %14 / %6 | 2.40–0.47 | 2-0 (%16) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %68.2 | orta | OddsMath (Marathonbet) |
| 17:00 | Hırvatistan 1. HNL | D. Zagreb - NK Istra 61 | %80 / %13 / %7 | 2.89–0.82 | 2-0 (%10) | 1. Yarı Sonucu: 1 | 1.36 | %58.1 | düşük | Smarkets (borsa) |
| 17:00 | İngiltere Kadınlar Süper Ligi | Everton (K) - Brighton (K) | %26 / %27 / %48 | 1.13–1.66 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %50.1 | düşük | Smarkets (borsa) |
| 17:00 | Sırbistan Superliga | FK IMT Novi Beograd - Partizan | %35 / %26 / %39 | 1.34–1.44 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 17:00 | İtalya Serie A, Kadınlar | Fiorentina (K) - Como 1907 (K) | %51 / %24 / %26 | 1.99–1.32 | 1-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.39 | %54.4 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | Portekiz Kupası | Gil Vicente - SC Olhanense | %93 / %6 / %1 | 3.37–0.29 | 3-0 (%16) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.61 | %51.0 | düşük | Smarkets (borsa) |
| 17:00 | Almanya Böl. Lig, Kuzey  | Hamburg II - W. Bremen II | %35 / %22 / %43 | 1.87–2.07 | 1-2 (%8) | 1. Yarı Çifte Şans: 1-2 | 1.24 | %64.6 | düşük | OddsMath (Marathonbet) |
| 17:00 | Malta Premier Lig Top 6 İlk Etap | Hamrun Spartans - Sliema Wanderers | %21 / %21 / %58 | 0.97–1.81 | 0-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %61.9 | düşük | OddsMath (Marathonbet) |
| 17:00 | İngiltere Premier Lig | Hull City - Brighton | %13 / %21 / %66 | 0.84–2.09 | 0-2 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.28 | %65.4 | orta | Smarkets (borsa) |
| 17:00 | Belarus Premier Lig | Isloch - Torpedo Belaz Z. | %65 / %22 / %13 | 1.90–0.70 | 1-0 (%14) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %65.7 | orta | Pinnacle (API-Football) |
| 17:00 | Kosova Superliga | KF Drita - Feronikeli | %71 / %20 / %9 | 2.09–0.64 | 2-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.63 | %48.9 | düşük | OddsMath (Marathonbet) |
| 17:00 | Belarus Premier Lig | M. Rogachev - Slavia Mozyr | %80 / %14 / %6 | 2.47–0.55 | 2-0 (%15) | 1. Yarı / 2. Yarı Karşılıklı Gol: Hayır/Hayır | 1.28 | %66.6 | orta | Pinnacle (API-Football) |
| 17:00 | Botsvana Premier Ligi | Mochudi Centre C. - Matebele | %68 / %22 / %10 | 1.75–0.51 | 1-0 (%18) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.41 | %58.6 | düşük | Nesine (yerel, düşük güven) |
| 17:00 | Bosna Hersek Premier Lig | NK Celik Zenica - FK Sloga Doboj | %43 / %29 / %29 | 1.29–1.00 | 1-1 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.30 | %61.3 | düşük | OddsMath (Marathonbet) |
| 17:00 | Slovenya PrvaLiga | NK Maribor - Nafta | %67 / %20 / %13 | 2.18–0.86 | 2-0 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.28 | %62.0 | düşük | Smarkets (borsa) |
| 17:00 | Fransa Kadınlar 1. Lig | O. Lyon (K) - RC Strasbourg (K) | %96 / %3 / %1 | 6.50–0.55 | 6-0 (%9) | — | — | — | yok | OddsMath (1XBET) |
| 17:00 | Fransa Kadınlar 1. Lig | Paris (K) - Fleury (K) | %69 / %19 / %12 | 2.35–0.80 | 2-0 (%12) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.46 | %51.3 | düşük | OddsMath (Marathonbet) |
| 17:00 | Fransa Ligue 1 | Paris - Angers | %74 / %17 / %9 | 2.53–0.82 | 2-0 (%11) | Ev Sahibi Her İki Yarıyı da Kazanır: Hayır | 1.26 | %66.5 | orta | Smarkets (borsa) |
| 17:00 | İsveç Allsvenskan Kad. Düş/Yük | Rosengard (K) - KIF Orebro DFF (K) | %62 / %20 / %18 | 2.18–1.09 | 2-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.22 | %66.2 | orta | OddsMath (Marathonbet) |
| 17:00 | İtalya Serie A | Sassuolo - Genoa | %35 / %30 / %36 | 1.30–1.32 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.27 | %66.4 | orta | Smarkets (borsa) |
| 17:00 | İsviçre Yükselme 1.Ligi | Schaffhausen - SC Cham | %48 / %24 / %28 | 1.96–1.46 | 1-1 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.47 | %56.3 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | Çekya 1. Lig | Slovacko - H. Kralove | %34 / %28 / %37 | 1.36–1.43 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %67.9 | orta | Smarkets (borsa) |
| 17:00 | İngiltere U21 Premier Lig Kupası | Stoke City U21 - Stockport U21 | %51 / %21 / %28 | 2.78–2.02 | 2-2 (%6) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %68.8 | orta | OddsMath (BetInAsia/Pinnacle) |
| 17:00 | Fas Botola 2 | U. Sp. Musulmane Oujda - JS Massira | %42 / %31 / %26 | 1.15–0.84 | 1-0 (%16) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.35 | %59.8 | düşük | OddsMath (Marathonbet) |
| 17:00 | Portekiz Kupası | Vianense - Rio Ave | %26 / %25 / %50 | 1.16–1.71 | 1-1 (%11) | — | — | — | yok | Smarkets (borsa) |
| 17:00 | Portekiz Kupası | Vitoria Sernache - Lusitania | %25 / %26 / %48 | 1.10–1.60 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %64.3 | düşük | Smarkets (borsa) |
| 17:00 | Portekiz 2. Lig | Vizela - CD Feirense | %49 / %28 / %23 | 1.47–0.92 | 1-0 (%14) | 1. Yarı Çifte Şans: X-2 | 1.23 | %62.0 | düşük | Smarkets (borsa) |
| 17:30 | İngiltere Kadınlar Süper Ligi | Arsenal (K) - West Ham Utd (K) | %85 / %10 / %5 | 3.92–0.84 | 3-0 (%9) | — | — | — | yok | Smarkets (borsa) |
| 17:30 | Almanya Bundesliga | Augsburg - Mainz | %35 / %25 / %40 | 1.68–1.80 | 1-1 (%9) | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.5 | orta | Smarkets (borsa) |
| 17:30 | Slovakya Superliga | FK Kosice - Skalica | %64 / %20 / %16 | 2.22–1.02 | 2-1 (%10) | 1. Yarı Çifte Şans: 1-2 | 1.25 | %61.7 | düşük | Smarkets (borsa) |
| 17:30 | İsviçre Yükselme 1.Ligi | Lugano II - Breitenrain | %31 / %25 / %45 | 1.51–1.85 | 1-1 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.44 | %56.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 17:45 | İspanya 3. Federasyon | Colunga - Llanes | %35 / %27 / %38 | 1.35–1.44 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %47.5 | düşük | OddsMath (Marathonbet) |
| 18:00 | Umman Ligi | AL Musannah SC - Dhofar Scsc | %31 / %30 / %39 | 1.00–1.17 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.33 | %60.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | Nijerya Premier Ligi | Abia Warriors - Enyimba | %47 / %28 / %25 | 1.31–0.86 | 1-0 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.33 | %60.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya Segunda RFEF | Albacete Balompie B - CD Guadalajara | %33 / %28 / %39 | 1.35–1.47 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.3 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | İspanya 3. Federasyon | Algar - CD Bala Azul | %11 / %20 / %69 | 0.63–1.98 | 0-1 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.58 | %51.4 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya 3. Federasyon | Andorra - CD Caspe | %26 / %29 / %45 | 0.88–1.26 | 0-1 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.32 | %61.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya Primera RFEF | Barakaldo - Unionistas | %56 / %24 / %19 | 1.67–0.87 | 1-0 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.25 | %66.0 | orta | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | Gana Premier Lig | Bechem Utd - Asante Kotoko | %54 / %29 / %17 | 1.43–0.68 | 1-0 (%17) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.30 | %62.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | Belçika 2. Lig, İlk Etap | Beerschot - J. KRC Genk U23 | %73 / %15 / %12 | 2.73–1.03 | 2-1 (%9) | Gol Alt/Üst: 4.5 Alt | 1.20 | %66.5 | orta | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | Gana Premier Lig | Bibiani Gold Stars - Swedru All Blacks | %69 / %24 / %6 | 1.77–0.41 | 1-0 (%20) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.34 | %60.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya 3. Federasyon | CDJ Tamarite - CD La Almunia | %30 / %27 / %43 | 1.13–1.41 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.1 | düşük | OddsMath (Marathonbet) |
| 18:00 | Fas Botola 2 | CJ Ben Guerir - US Yacoub Mansour | %26 / %33 / %41 | 0.80–1.07 | 0-1 (%16) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.41 | %57.6 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya Primera RFEF | Cartagena - Real Jaen | %59 / %24 / %17 | 1.86–0.91 | 1-0 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %62.0 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | Gana Premier Lig | Dreams - Samartex | %56 / %27 / %17 | 1.48–0.70 | 1-0 (%17) | — | — | — | yok | OddsMath (Marathonbet) |
| 18:00 | Nijerya Premier Ligi | Eng. Rangers - Shooting Stars | %65 / %24 / %12 | 1.75–0.60 | 1-0 (%17) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | Uganda Premier Ligi | Express - Vipers SC | %12 / %23 / %65 | 0.61–1.76 | 0-1 (%16) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.26 | %62.4 | düşük | OddsMath (Marathonbet) |
| 18:00 | İspanya Gençler Onur Klasmanı | Getafe U19 - R. Majadahonda U19 | %69 / %18 / %13 | 2.35–0.94 | 2-0 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.36 | %56.6 | düşük | Nesine (yerel, düşük güven) |
| 18:00 | Gana Premier Lig | Hearts of Oak - Aduana Stars | %66 / %25 / %9 | 1.59–0.44 | 1-0 (%21) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.34 | %59.2 | düşük | OddsMath (Marathonbet) |
| 18:00 | Şili Premier Lig | Huachipato - Dep. Concepcion | %37 / %28 / %35 | 1.32–1.29 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.6 | orta | Smarkets (borsa) |
| 18:00 | Tanzanya Premier Lig | Kagera Sugar - Tabora Utd | %26 / %29 / %45 | 0.98–1.36 | 0-1 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.30 | %62.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | Belçika Pro Lig | Kortrijk - U. S. Gilloise | %11 / %18 / %71 | 0.79–2.30 | 0-2 (%12) | Maç Sonucu: 2 | 1.21 | %69.5 | orta | Smarkets (borsa) |
| 18:00 | Nijerya Premier Ligi | Kun Khalifat - Katsina Utd | %49 / %28 / %24 | 1.42–0.90 | 1-0 (%14) | — | — | — | yok | OddsMath (Marathonbet) |
| 18:00 | Gana Premier Lig | Medeama SC - Ashanti Gold | %73 / %19 / %8 | 2.04–0.52 | 2-0 (%16) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %66.3 | orta | OddsMath (Marathonbet) |
| 18:00 | Nijerya Premier Ligi | Nasarawa Utd - Warri Wolves | %76 / %18 / %6 | 2.15–0.47 | 2-0 (%17) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.58 | %51.4 | düşük | OddsMath (Marathonbet) |
| 18:00 | Macaristan 1. Ligi | Nyiregyhaza - Debrecen | %35 / %26 / %39 | 1.44–1.53 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %66.4 | orta | Smarkets (borsa) |
| 18:00 | Yunanistan Süper Lig | Paneitolikos - Volos | %42 / %30 / %28 | 1.34–1.07 | 1-1 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.27 | %64.1 | düşük | Smarkets (borsa) |
| 18:00 | Gana Premier Lig | Port City - Heart of Lions | %55 / %27 / %18 | 1.61–0.83 | 1-0 (%14) | — | — | — | yok | OddsMath (Marathonbet) |
| 18:00 | Almanya Kadınlar Bundesliga | RB Leipzig (K) - Wolfsburg (K) | %7 / %11 / %82 | 0.95–3.78 | 0-3 (%8) | 3,5 Gol Alt/Üst: 3,5 Üst | 1.41 | %57.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | İspanya Primera RFEF | RC Deportivo Fabril - CD Coria | %49 / %26 / %26 | 1.71–1.19 | 1-1 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.22 | %67.8 | orta | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | Nijerya Premier Ligi | Rivers Utd - Niger Tornadoes | %72 / %21 / %7 | 1.81–0.41 | 1-0 (%20) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.34 | %59.0 | düşük | OddsMath (Marathonbet) |
| 18:00 | Portekiz Kupası | S. Farense - CD De Fatima | %78 / %16 / %6 | 2.39–0.54 | 2-0 (%15) | 1. Yarı Çifte Şans: 1-2 | 1.21 | %63.8 | düşük | Smarkets (borsa) |
| 18:00 | Fas Botola 2 | S.C. Mhammedia - Mouloudia | %29 / %31 / %39 | 0.94–1.13 | 0-1 (%14) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.31 | %61.8 | düşük | OddsMath (Marathonbet) |
| 18:00 | Ürdün Kupası | Shabab AL Ordon - Ittihad AL Ramtha | %37 / %28 / %35 | 1.20–1.15 | 1-1 (%13) | — | — | — | yok | OddsMath (Marathonbet) |
| 18:00 | Danimarka Süper Ligi | Sonderjyske - Odense | %32 / %25 / %43 | 1.41–1.64 | 1-1 (%11) | Deplasman İki Yarıda da Gol: Atamaz | 1.23 | %68.2 | orta | Smarkets (borsa) |
| 18:00 | İspanya Segunda RFEF | UD Llanera - Ourense | %43 / %27 / %31 | 1.49–1.23 | 1-1 (%12) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.25 | %68.3 | orta | OddsMath (BetInAsia/Pinnacle) |
| 18:00 | İspanya 3. Federasyon | Ucam Murcia B - U. Molinense 2020 | %43 / %27 / %30 | 1.41–1.13 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.1 | düşük | OddsMath (Marathonbet) |
| 18:15 | İspanya 3. Federasyon | CD Cenicero - Alfaro | %10 / %20 / %70 | 0.66–2.08 | 0-2 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %48.6 | düşük | OddsMath (Marathonbet) |
| 18:15 | İspanya 2. Lig | S. Gijon - Las Palmas | %45 / %28 / %27 | 1.49–1.11 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %65.9 | orta | Smarkets (borsa) |
| 18:15 | İspanya 3. Federasyon | SFC Minerva - Atletico Pulpileno | %23 / %28 / %49 | 0.94–1.47 | 0-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %56.8 | düşük | OddsMath (Marathonbet) |
| 18:15 | İspanya La Liga | Santander - R. Sociedad | %29 / %24 / %48 | 1.56–2.03 | 1-2 (%9) | Ev Sahibi İki Yarıda da Gol: Atamaz | 1.21 | %69.2 | orta | Smarkets (borsa) |
| 18:30 | İspanya 3. Federasyon | Alondras - Gran Pena | %50 / %25 / %25 | 1.66–1.12 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.77 | %47.5 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | Ath Torrellano - Crevillente Deportivo | %36 / %28 / %36 | 1.23–1.23 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.49 | %55.2 | düşük | OddsMath (Marathonbet) |
| 18:30 | İsviçre Süper Lig | Basel - Luzern | %43 / %23 / %34 | 1.97–1.75 | 1-1 (%8) | Gol Alt/Üst: 4.5 Alt | 1.22 | %66.8 | orta | Smarkets (borsa) |
| 18:30 | İsveç Allsvenskan | Brommapojkarna - Halmstads | %46 / %25 / %29 | 1.67–1.29 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.22 | %67.5 | orta | Smarkets (borsa) |
| 18:30 | İspanya 3. Federasyon | Bullas Deportivo - Cotillas CD | %43 / %27 / %30 | 1.32–1.05 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.47 | %56.8 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | CD Boiro - Portonovo SD | %66 / %23 / %12 | 1.81–0.63 | 1-0 (%16) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.44 | %55.6 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | CD Gevora - Villanovense | %26 / %27 / %48 | 1.00–1.46 | 0-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.80 | %39.8 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | Cd Torrijos - AD San Clemente | %38 / %31 / %31 | 1.23–1.09 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.42 | %58.8 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | Deportivo Maritimo - Aguilas B | %21 / %25 / %54 | 0.92–1.61 | 0-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.54 | %53.1 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | Epila - AD Almudevar | %35 / %31 / %34 | 1.02–0.99 | 1-0 (%14) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.33 | %60.2 | düşük | OddsMath (Marathonbet) |
| 18:30 | İsviçre Süper Lig | Lausanne - Vaduz | %47 / %24 / %29 | 1.95–1.51 | 1-1 (%9) | 1. Yarı Çifte Şans: X-2 | 1.34 | %60.1 | düşük | Smarkets (borsa) |
| 18:30 | İspanya 3. Federasyon | Malaga City - CD Alhaurino | %34 / %29 / %37 | 1.27–1.34 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.59 | %51.4 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya Segunda RFEF | Navalcarnero - Gimnastica Segoviana | %43 / %28 / %29 | 1.46–1.17 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.21 | %66.0 | orta | OddsMath (BetInAsia/Pinnacle) |
| 18:30 | Yunanistan Süper Lig | Panathinaikos - Ofi Crete | %80 / %13 / %7 | 2.69–0.69 | 2-0 (%12) | Ev Sahibi Her İki Yarıyı da Kazanır: Hayır | 1.32 | %60.6 | düşük | Smarkets (borsa) |
| 18:30 | Almanya 3. Lig | Saarbrucken - W. Wiesbaden | %36 / %26 / %38 | 1.54–1.60 | 1-1 (%11) | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.6 | orta | Smarkets (borsa) |
| 18:30 | İspanya 3. Federasyon | Santa Amalia - Jaraiz | %40 / %28 / %32 | 1.30–1.13 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.47 | %55.8 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | UD Vall de Uxo - CD Roda | %52 / %28 / %20 | 1.46–0.81 | 1-0 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.34 | %60.0 | düşük | OddsMath (Marathonbet) |
| 18:30 | İspanya 3. Federasyon | UE Porreres - Ibiza Islas Pitiusas | %30 / %30 / %40 | 1.09–1.30 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.46 | %57.2 | düşük | OddsMath (Marathonbet) |
| 18:30 | Romanya 1. Lig | UTA Arad - Un. Craiova | %19 / %26 / %55 | 0.89–1.67 | 0-1 (%13) | Deplasman İki Yarıda da Gol: Atamaz | 1.20 | %67.7 | orta | Smarkets (borsa) |
| 18:45 | İspanya 3. Federasyon | CD Mosconia - Aviles Stadium | %66 / %21 / %13 | 1.90–0.69 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.53 | %52.0 | düşük | OddsMath (Marathonbet) |
| 18:45 | Hollanda Eredivisie Kadınlar | Feyenoord (K) - Twente (K) | %9 / %14 / %78 | 0.87–3.13 | 0-3 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.52 | %54.2 | düşük | OddsMath (Marathonbet) |
| 18:45 | Hollanda Eredivisie | Go Ahead Eagles - F. Sittard | %53 / %24 / %23 | 1.92–1.19 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.24 | %66.6 | orta | Smarkets (borsa) |
| 18:45 | Hollanda Eredivisie Kadınlar | PSV Eindhoven (K) - PEC Zwolle (K) | %81 / %12 / %7 | 3.20–0.72 | 3-0 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.46 | %55.6 | düşük | OddsMath (Marathonbet) |
| 18:45 | Hollanda Eredivisie Kadınlar | Utrecht (K) - AZ Alkmaar (K) | %31 / %25 / %44 | 1.46–1.78 | 1-1 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.39 | %53.4 | düşük | OddsMath (Marathonbet) |
| 18:45 | Hollanda Eredivisie Kadınlar | de Graafschap (K) - Ajax (K) | %9 / %14 / %78 | 0.90–3.18 | 0-3 (%9) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.54 | %52.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | Norveç Eliteserien | Aalesunds - Rosenborg | %20 / %20 / %60 | 1.37–2.41 | 1-2 (%9) | Gol Alt/Üst: 4.5 Alt | 1.26 | %65.6 | orta | Smarkets (borsa) |
| 19:00 | İspanya 3. Federasyon | Arandina - Mirandes B | %50 / %27 / %23 | 1.44–0.88 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.41 | %58.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya Segunda RFEF | Arosa SC - SD Eibar B | %31 / %28 / %41 | 1.29–1.52 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.27 | %61.4 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | İspanya 3. Federasyon | Atl Club Pueblonuevo - SP Villafranca | %31 / %26 / %43 | 1.22–1.48 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %49.2 | düşük | OddsMath (Marathonbet) |
| 19:00 | Avusturya Bundesliga | Austria Wien - Salzburg | %21 / %22 / %57 | 1.19–2.05 | 1-2 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.24 | %65.4 | orta | Smarkets (borsa) |
| 19:00 | İspanya 3. Federasyon | Badalona - Pobla de Mafumet | %63 / %23 / %14 | 1.86–0.74 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.58 | %52.0 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya Segunda RFEF | Bergantinos - CD Basconia | %60 / %23 / %17 | 2.02–1.00 | 2-1 (%10) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.33 | %58.1 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | İspanya 3. Federasyon | Bollullos - Cadiz B | %41 / %29 / %30 | 1.20–0.99 | 1-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.36 | %59.6 | düşük | OddsMath (Marathonbet) |
| 19:00 | Bulgaristan Parva Ligi | Botev Plovdiv - CSKA Sofya | %19 / %24 / %56 | 1.03–1.88 | 1-1 (%10) | 1. Yarı Çifte Şans: 1-2 | 1.30 | %58.0 | düşük | Smarkets (borsa) |
| 19:00 | Türkiye 1. Lig | Bursaspor - Sivasspor | %81 / %13 / %6 | 2.71–0.60 | 2-0 (%13) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.42 | %58.5 | düşük | Smarkets (borsa) |
| 19:00 | İspanya 3. Federasyon | CD Barquereno - UM Escobedo | %34 / %26 / %40 | 1.32–1.44 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.67 | %48.0 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya Gençler Onur Klasmanı | CD Espanyol Barca U19 - R. Club Zaragoza U19 | — | — | — | — | — | — | yok | — |
| 19:00 | İspanya Gençler Onur Klasmanı | CD Mosquito U19 - Arenas Armilla CD U19 | %69 / %17 / %13 | 2.53–1.04 | 2-1 (%9) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 19:00 | İspanya 3. Federasyon | CD Quintanar Del Rey - La Solana | %43 / %28 / %29 | 1.33–1.05 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.45 | %56.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya 3. Federasyon | CD Tarancon - CD Huracan de Balazote | %70 / %19 / %10 | 1.99–0.61 | 1-0 (%15) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.57 | %51.4 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya 3. Federasyon | CP Villarrobledo - Marchamalo CD | %55 / %26 / %19 | 1.61–0.83 | 1-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.44 | %55.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya 3. Federasyon | Cd Estradense - Arenteiro | %58 / %24 / %18 | 1.75–0.87 | 1-0 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.57 | %51.1 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya 3. Federasyon | Cdfc La Calzada - Oyonesa | %41 / %27 / %32 | 1.42–1.21 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.61 | %50.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya 3. Federasyon | Comillas - Calahorra | %4 / %8 / %88 | 0.50–3.12 | 0-3 (%14) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.52 | %52.8 | düşük | OddsMath (Marathonbet) |
| 19:00 | Sırbistan Superliga | FK M. Sabac - FK Vojvodina | %14 / %22 / %64 | 0.82–1.99 | 0-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.6 | düşük | Smarkets (borsa) |
| 19:00 | İspanya Primera Ligi Kadınlar | Granadilla (K) - Madrid Ccf (K) | %57 / %23 / %19 | 1.97–1.00 | 1-0 (%10) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.69 | %46.9 | düşük | Nesine (yerel, düşük güven) |
| 19:00 | İspanya 3. Federasyon | Javier Mar Menor - Olimpico Totana | %40 / %28 / %32 | 1.30–1.15 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.50 | %55.2 | düşük | OddsMath (Marathonbet) |
| 19:00 | Norveç Eliteserien | Kfum Oslo - Brann | %33 / %25 / %42 | 1.55–1.78 | 1-1 (%10) | Deplasman İki Yarıda da Gol: Atamaz | 1.26 | %64.8 | düşük | Smarkets (borsa) |
| 19:00 | Norveç Eliteserien | Kristiansund - Sandefjord | %36 / %25 / %39 | 1.56–1.63 | 1-1 (%10) | 1. Yarı Çifte Şans: X-2 | 1.21 | %68.3 | orta | Smarkets (borsa) |
| 19:00 | İspanya 3. Federasyon | Marbelli - UD Almeria B | %41 / %30 / %30 | 1.25–1.02 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.38 | %59.6 | düşük | OddsMath (Marathonbet) |
| 19:00 | İspanya Segunda RFEF | Orihuela - La Nucia | %45 / %29 / %26 | 1.40–0.99 | 1-0 (%13) | 1. Yarı Çifte Şans: X-2 | 1.21 | %65.3 | orta | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | İspanya Gençler Onur Klasmanı | Rayo Ciudad U19 - Leganes U19 | %15 / %21 / %64 | 0.92–2.07 | 0-2 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.47 | %52.4 | düşük | Nesine (yerel, düşük güven) |
| 19:00 | İspanya Segunda RFEF | Real Avila - UB Conquense | %27 / %27 / %46 | 0.94–1.32 | 0-1 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.39 | %59.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | Rusya Premier Lig | Rodina Moscow - L. Moskova | %36 / %26 / %38 | 1.46–1.51 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.23 | %66.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | Slovenya 2. Lig | Rudar - ND Beltinci | %29 / %25 / %46 | 1.30–1.67 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %67.3 | orta | OddsMath (Marathonbet) |
| 19:00 | İspanya Segunda RFEF | SD Gernika Club - Rayo Cantabria | %48 / %27 / %25 | 1.62–1.10 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %63.9 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | İspanya Segunda RFEF | Salamanca - C. Sotelo Puertollano | %64 / %22 / %14 | 1.99–0.83 | 1-0 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.2 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | Macaristan 2. Ligi | Soroksar - Szeged G. A. | %41 / %27 / %32 | 1.42–1.22 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.2 | orta | OddsMath (Marathonbet) |
| 19:00 | Polonya 1. Lig | Stal Rzeszow - Polonia Bytom | %35 / %26 / %39 | 1.39–1.47 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 19:00 | İspanya Segunda RFEF | Talavera R. - Atl Tordesillas | %60 / %25 / %16 | 1.83–0.84 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %64.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | Türkiye Süper Ligi | Trabzonspor - Eyüpspor | %87 / %9 / %4 | 3.08–0.57 | 3-0 (%13) | Gol Alt/Üst: 4.5 Alt | 1.20 | %67.8 | orta | Smarkets (borsa) |
| 19:00 | İspanya Segunda RFEF | Tudelano - Pena Sport | %55 / %23 / %22 | 1.82–1.05 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.29 | %60.4 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:00 | Estonya Esiliiga, Düş./Yük. | V. Tulevik - Tallinn | %29 / %25 / %46 | 1.26–1.66 | 1-1 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.31 | %59.7 | düşük | OddsMath (1XBET) |
| 19:00 | İspanya 3. Federasyon | Vianes - Yague | %53 / %24 / %24 | 1.79–1.13 | 1-1 (%11) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.51 | %50.6 | düşük | OddsMath (Marathonbet) |
| 19:15 | Fransa Ligue 1 | Lorient - Rennes | %32 / %28 / %40 | 1.17–1.33 | 1-1 (%13) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.20 | %69.2 | orta | Smarkets (borsa) |
| 19:15 | İtalya Serie B | SS Arezzo - Padova | %42 / %30 / %28 | 1.41–1.11 | 1-1 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %67.1 | orta | Smarkets (borsa) |
| 19:30 | İtalya Serie C | AZ Picerno - Giugliano 1928 | %46 / %28 / %26 | 1.41–1.01 | 1-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | İspanya Segunda RFEF | Ciudad De Lucena - Betis D. Balompie | %33 / %29 / %38 | 1.30–1.41 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %63.9 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:30 | İtalya Serie C | Desenzano Calvina - US Albinoleffe | %36 / %31 / %34 | 1.09–1.04 | 1-1 (%14) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | İtalya Serie C | Dolomiti Bellunesi - Ath Carpi | %34 / %30 / %37 | 1.08–1.15 | 1-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | İtalya Serie C | Forli - Reggiana | %34 / %29 / %37 | 1.14–1.21 | 1-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | Malta Premier Lig Top 6 İlk Etap | Hibernians - Marsaxlokk | %35 / %26 / %40 | 1.36–1.47 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.1 | düşük | OddsMath (Marathonbet) |
| 19:30 | İngiltere Premier Lig | Liverpool - Man. Utd | %57 / %23 / %21 | 2.08–1.21 | 2-1 (%10) | Ev Sahibi Herhangi Bir Yarıyı Kazanır: Evet | 1.21 | %68.7 | orta | Smarkets (borsa) |
| 19:30 | Ekvador Pro Lig, Düşme Turu | Manta - Delfin | %34 / %29 / %37 | 1.14–1.19 | 1-1 (%13) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | Slovenya PrvaLiga | NK Celje - NK Brinje Grosuplje | %69 / %19 / %12 | 2.20–0.79 | 2-0 (%12) | — | — | — | yok | Smarkets (borsa) |
| 19:30 | İspanya Segunda RFEF | Recreativo - Badajoz | %62 / %24 / %14 | 1.79–0.72 | 1-0 (%15) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %67.2 | orta | OddsMath (BetInAsia/Pinnacle) |
| 19:30 | İspanya Segunda RFEF | SD Logrones - CD Arnedo | %55 / %26 / %19 | 1.64–0.86 | 1-0 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.21 | %65.5 | orta | OddsMath (BetInAsia/Pinnacle) |
| 19:30 | İtalya Serie C | Sambenedettese - Perugia | %33 / %27 / %40 | 1.29–1.43 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.25 | %68.8 | orta | Smarkets (borsa) |
| 19:30 | İspanya 3. Federasyon | San Roque - Conil | %71 / %19 / %11 | 2.04–0.64 | 2-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.60 | %49.8 | düşük | OddsMath (Marathonbet) |
| 19:30 | Bosna Hersek Premier Lig | Sarajevo - Siroki Brijeg | %70 / %20 / %10 | 1.93–0.55 | 1-0 (%16) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.21 | %67.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 19:30 | İspanya Segunda RFEF | Sestao River Club - Amorebieta | %51 / %28 / %21 | 1.46–0.85 | 1-0 (%14) | 1. Yarı Çifte Şans: X-2 | 1.26 | %61.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 19:30 | Senegal Premier Lig | Stade de Mbour - Ajel de Rufisque | %18 / %31 / %51 | 0.60–1.21 | 0-1 (%20) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.46 | %57.2 | düşük | OddsMath (Marathonbet) |
| 19:30 | Senegal Premier Lig | Teungueth - ASC Diambars | %40 / %33 / %27 | 1.02–0.78 | 1-0 (%17) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.47 | %56.0 | düşük | OddsMath (Marathonbet) |
| 19:30 | İspanya 3. Federasyon | Torredonjimeno - CD Cantoria 2017 | %72 / %18 / %10 | 2.13–0.63 | 2-0 (%14) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.66 | %48.0 | düşük | OddsMath (Marathonbet) |
| 19:30 | İspanya 3. Federasyon | UE Vilassar de Mar - Vilanova Geltru | %36 / %29 / %36 | 1.20–1.20 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.46 | %56.8 | düşük | OddsMath (Marathonbet) |
| 19:30 | Senegal Premier Lig | US Ouakam - Hlm | %32 / %32 / %35 | 0.90–0.96 | 0-0 (%16) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.37 | %58.0 | düşük | OddsMath (Marathonbet) |
| 19:30 | Almanya Bundesliga | Werder Bremen - Hamburg | %61 / %22 / %17 | 2.08–1.04 | 2-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.0 | orta | Smarkets (borsa) |
| 19:30 | Polonya Ekstraklasa | Wisla Plock - L. Varşova | %30 / %28 / %42 | 1.20–1.46 | 1-1 (%12) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.21 | %68.8 | orta | Smarkets (borsa) |
| 20:00 | İtalya Serie A | AC Milan - Frosinone | %60 / %21 / %19 | 2.26–1.22 | 2-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.30 | %61.6 | düşük | Smarkets (borsa) |
| 20:00 | İspanya 3. Federasyon | Astur - L. Entregu | %27 / %29 / %44 | 1.05–1.40 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.53 | %55.8 | düşük | OddsMath (Marathonbet) |
| 20:00 | İspanya Segunda RFEF | Atl Madrid C - San Sebastian R. | %31 / %29 / %41 | 1.20–1.42 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %65.5 | orta | OddsMath (BetInAsia/Pinnacle) |
| 20:00 | Slovakya Superliga | Dunajska S. - KFC Komarno | %69 / %19 / %12 | 2.35–0.91 | 2-0 (%11) | 1. Yarı Çifte Şans: 1-2 | 1.22 | %62.6 | düşük | Smarkets (borsa) |
| 20:00 | Senegal Premier Lig | Guediawaye - ASC Jaraaf | %25 / %31 / %43 | 0.80–1.15 | 0-1 (%16) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 20:00 | Almanya Böl. Lig, Batı | Gutersloh 2000 - Oberhausen | %24 / %22 / %54 | 1.31–2.05 | 1-2 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.24 | %62.0 | düşük | OddsMath (Marathonbet) |
| 20:00 | Fas Botola 2 | IZK Itihad Z Khemisset - Sportive Boujaad | %45 / %31 / %24 | 1.16–0.77 | 1-0 (%17) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.40 | %57.4 | düşük | OddsMath (Marathonbet) |
| 20:00 | Danimarka Süper Ligi | Nordsjælland - Kopenhag | %38 / %27 / %34 | 1.46–1.37 | 1-1 (%12) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %68.6 | orta | Smarkets (borsa) |
| 20:00 | Yunanistan Süper Lig | Olympiakos - POT Iraklis | %84 / %12 / %4 | 2.66–0.47 | 2-0 (%15) | Deplasman Hangi Yarıda Daha Çok Gol Atar?: Eşit | 1.31 | %62.4 | düşük | Smarkets (borsa) |
| 20:00 | Botsvana Premier Ligi | Police Xi - Jwaneng Galaxy | %18 / %27 / %55 | 0.70–1.44 | 0-1 (%17) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.36 | %61.7 | düşük | Nesine (yerel, düşük güven) |
| 20:00 | İspanya 3. Federasyon | RC Alcobendas - Colonia Moscardo | %26 / %25 / %49 | 1.14–1.66 | 1-1 (%12) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.71 | %47.2 | düşük | OddsMath (Marathonbet) |
| 20:00 | Hırvatistan 1. HNL | Rijeka - HNK Gorica | %72 / %18 / %9 | 2.18–0.65 | 2-0 (%14) | — | — | — | yok | Smarkets (borsa) |
| 20:00 | Çekya 1. Lig | Sparta Prag - Slovan Liberec | %57 / %24 / %19 | 1.90–1.01 | 1-1 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.24 | %65.7 | orta | Smarkets (borsa) |
| 20:00 | İspanya Segunda RFEF | Terrassa - Manresa | %53 / %25 / %22 | 1.55–0.89 | 1-0 (%14) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.25 | %64.5 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 20:00 | İspanya Segunda RFEF | Valencia M. - CD Alcoyano | %45 / %28 / %26 | 1.50–1.09 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %66.0 | orta | OddsMath (BetInAsia/Pinnacle) |
| 20:15 | İspanya Primera RFEF | Cultural Leonesa - Zamora | %47 / %30 / %24 | 1.40–0.92 | 1-0 (%14) | 1,5 Gol Alt/Üst: 1,5 Üst | 1.21 | %67.8 | orta | OddsMath (BetInAsia/Pinnacle) |
| 20:15 | İspanya Primera RFEF | Merida AD - Union Irun | %43 / %26 / %31 | 1.57–1.29 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.24 | %65.2 | orta | OddsMath (BetInAsia/Pinnacle) |
| 20:30 | Belçika Pro Lig | Anderlecht - O. H. Leuven | %65 / %20 / %15 | 2.20–0.96 | 2-0 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.39 | %59.5 | düşük | Smarkets (borsa) |
| 20:30 | Macaristan 1. Ligi | B. Honved - Paksi | %35 / %24 / %40 | 1.50–1.62 | 1-1 (%11) | — | — | — | yok | Smarkets (borsa) |
| 20:30 | İspanya 2. Lig | Celta Vigo B - Real Valladolid | %28 / %26 / %45 | 1.21–1.59 | 1-1 (%12) | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %69.0 | orta | Smarkets (borsa) |
| 20:30 | Tanzanya Premier Lig | Geita Gold - Mashujaa | %34 / %30 / %36 | 1.13–1.15 | 1-1 (%13) | 2,5 Gol Alt/Üst: 2,5 Alt | 1.40 | %59.6 | düşük | OddsMath (Marathonbet) |
| 20:30 | İspanya 2. Lig | Girona - Eibar | %50 / %26 / %24 | 1.67–1.08 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.21 | %68.9 | orta | Smarkets (borsa) |
| 20:30 | Almanya Kadınlar Bundesliga | Mainz 05 (K) - Nürnberg (K) | %20 / %22 / %58 | 1.25–2.31 | 1-2 (%10) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.40 | %59.8 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 20:30 | İspanya La Liga | Osasuna - Malaga | %53 / %26 / %21 | 1.60–0.94 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %67.5 | orta | Smarkets (borsa) |
| 20:30 | Yunanistan Süper Lig | PAOK - AE Kifisia | %72 / %18 / %10 | 2.23–0.72 | 2-0 (%13) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.24 | %65.0 | orta | Smarkets (borsa) |
| 21:00 | İspanya Primera Ligi Kadınlar | Barcelona (K) - Ath Bilbao (K) | %97 / %3 / %1 | 5.11–0.18 | 5-0 (%15) | — | — | — | yok | OddsMath (1XBET) |
| 21:00 | Portekiz Kupası | Estrela - Portimonense | %57 / %26 / %17 | 1.58–0.75 | 1-0 (%15) | — | — | — | yok | Smarkets (borsa) |
| 21:00 | İspanya Gençler Onur Klasmanı | Real Sociedad U19 - Santutxu U19 | %72 / %16 / %12 | 2.75–1.08 | 2-1 (%9) | — | — | — | yok | Nesine (yerel, düşük güven) |
| 21:15 | Belçika 2. Lig, İlk Etap | KAA Gent II - Francs Borains | %36 / %26 / %37 | 1.35–1.37 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 21:15 | Belçika Pro Lig | Lommel SK - Standard Liege | %30 / %25 / %45 | 1.39–1.76 | 1-1 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.28 | %64.3 | düşük | Smarkets (borsa) |
| 21:15 | Norveç Eliteserien | Sarpsborg 08 - Lillestrom | %46 / %23 / %32 | 2.02–1.68 | 2-1 (%8) | Gol Alt/Üst: 4.5 Alt | 1.23 | %66.8 | orta | Smarkets (borsa) |
| 21:30 | Romanya 1. Lig | A. Pitesti - FCSB | %23 / %28 / %50 | 0.88–1.44 | 0-1 (%14) | — | — | — | yok | Smarkets (borsa) |
| 21:30 | Almanya 3. Lig | Duisburg - H. Rostock | %43 / %26 / %31 | 1.64–1.36 | 1-1 (%11) | Ev Sahibi İki Yarıda da Gol: Atamaz | 1.23 | %68.3 | orta | Smarkets (borsa) |
| 21:30 | Polonya 2. Lig | Zawisza Bydgoszcz - Podhale Nowy Targ | %39 / %26 / %35 | 1.54–1.43 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %66.9 | orta | OddsMath (BetInAsia/Pinnacle) |
| 22:00 | Brezilya Serie B, Yükselme | Criciuma - Fortaleza CE | %47 / %31 / %22 | 1.32–0.84 | 1-0 (%15) | 1. Yarı Çifte Şans: X-2 | 1.21 | %66.1 | orta | Smarkets (borsa) |
| 22:00 | Ekvador Pro Lig, Düşme Turu | Orense SC - Mushuc Runa | %55 / %26 / %19 | 1.64–0.87 | 1-0 (%13) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.23 | %65.7 | orta | Smarkets (borsa) |
| 22:00 | Brezilya Serie A | Paranaense - Clube do Remo | %67 / %19 / %14 | 2.12–0.88 | 2-0 (%11) | Deplasman Herhangi Bir Yarıyı Kazanır: Hayır | 1.25 | %70.9 | orta | Nesine (yerel, düşük güven) |
| 22:00 | Bolivya Profesyonel Ligi | Real Potosi - Club Bolivar | %13 / %19 / %67 | 0.87–2.20 | 0-2 (%11) | 1. Yarı Çifte Şans: 1-2 | 1.27 | %60.8 | düşük | OddsMath (Marathonbet) |
| 22:00 | Arjantin Primera Lpf, Clausura Playoff | Rosario C. - Gimnasia Y. | %69 / %20 / %11 | 2.04–0.67 | 2-0 (%14) | — | — | — | yok | Smarkets (borsa) |
| 22:30 | İspanya Primera RFEF | CP Cacereno Sad - Logrones | %37 / %28 / %36 | 1.38–1.35 | 1-1 (%12) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %67.7 | orta | OddsMath (BetInAsia/Pinnacle) |
| 22:30 | İtalya Serie A, Kadınlar | Lazio (K) - Juventus (K) | %19 / %21 / %60 | 1.12–2.23 | 1-2 (%10) | 2,5 Gol Alt/Üst: 2,5 Üst | 1.35 | %54.9 | düşük | OddsMath (BetInAsia/Pinnacle) |
| 22:30 | Portekiz Kupası | Uniao Leiria - Leca | %66 / %21 / %13 | 1.98–0.75 | 1-0 (%13) | — | — | — | yok | Smarkets (borsa) |
| 22:45 | İtalya Serie A | Atalanta - Inter | %17 / %20 / %63 | 1.19–2.36 | 1-2 (%10) | Ev Sahibi Herhangi Bir Yarıyı Kazanır: Hayır | 1.29 | %65.1 | orta | Smarkets (borsa) |
| 22:45 | Fransa Ligue 1 | Marsilya - Le Mans | %67 / %19 / %14 | 2.26–0.95 | 2-0 (%10) | 2. Yarı Karşılıklı Gol: Yok | 1.20 | %68.3 | orta | Smarkets (borsa) |
| 23:00 | İspanya 2. Lig | Burgos - Albacete | %46 / %29 / %24 | 1.45–0.99 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.21 | %67.9 | orta | Smarkets (borsa) |
| 23:00 | Jamaika Premier Lig | Chapelton Maroons - Cavalier | %26 / %26 / %48 | 1.08–1.54 | 1-1 (%12) | 1. Yarı 0,5 Gol Alt/Üst: 0,5 Üst | 1.22 | %67.0 | orta | OddsMath (Marathonbet) |
| 23:00 | İspanya La Liga | Getafe - Atl Madrid | %13 / %24 / %64 | 0.67–1.75 | 0-1 (%16) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.22 | %69.0 | orta | Smarkets (borsa) |
| 23:00 | Peru Prmr Ligi, Kapanış | Huancayo - U. Deportes | %46 / %26 / %28 | 1.57–1.17 | 1-1 (%12) | — | — | — | yok | Smarkets (borsa) |
| 23:00 | Jamaika Premier Lig | Montego Bay Utd - Waterhouse | %46 / %30 / %24 | 1.59–1.11 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %64.1 | düşük | OddsMath (Marathonbet) |
| 23:00 | Jamaika Premier Lig | Mount Pleasant - Humble Lions | %92 / %7 / %2 | 3.43–0.39 | 3-0 (%15) | 1. Yarı Sonucu: 1 | 1.22 | %71.1 | orta | OddsMath (Marathonbet) |
| 23:00 | Peru Prmr Ligi, Kapanış | S. Cristal - CS Cienciano | %69 / %18 / %13 | 2.32–0.89 | 2-0 (%11) | — | — | — | yok | Smarkets (borsa) |
| 23:45 | Portekiz Kupası | Torreense - Benfica | %6 / %12 / %83 | 0.67–2.92 | 0-2 (%12) | — | — | — | yok | Smarkets (borsa) |
| **23 Kas gece** 00:00 | Guatemala Ulusal Lig, Açılış | CSD Imperial - Dep. San Pedro | %60 / %25 / %15 | 1.82–0.82 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.26 | %65.2 | orta | OddsMath (BetInAsia/Pinnacle) |
| **23 Kas gece** 00:00 | Şili Premier Lig | Colo Colo - Uni. Catolica | %43 / %25 / %32 | 1.65–1.41 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.21 | %65.4 | orta | Smarkets (borsa) |
| **23 Kas gece** 00:00 | El Salvador Primera Division, Açılış | Fuerte San Francisco - CD Inca | %45 / %29 / %27 | 1.51–1.13 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.24 | %65.2 | orta | OddsMath (BetInAsia/Pinnacle) |
| **23 Kas gece** 00:00 | Venezuela Prmr Lig, Kapanış, Ana Tur | Metropolitan - Dep. La Gua. | %44 / %28 / %28 | 1.55–1.20 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.21 | %64.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| **23 Kas gece** 00:00 | ABD Major Lig Playoff | Nashville SC - Cincinnati | %65 / %19 / %16 | 2.33–1.08 | 2-1 (%10) | Deplasman Herhangi Bir Yarıyı Kazanır: Hayır | 1.26 | %67.8 | orta | Smarkets (borsa) |
| **23 Kas gece** 00:15 | Bolivya Profesyonel Ligi | Strongest - Blooming | %72 / %16 / %12 | 2.79–1.11 | 2-1 (%9) | — | — | — | yok | Smarkets (borsa) |
| **23 Kas gece** 00:30 | Brezilya Serie B, Yükselme | Atl Goianiense - Vila Nova | %47 / %29 / %23 | 1.38–0.91 | 1-0 (%14) | 1. Yarı Çifte Şans: X-2 | 1.21 | %65.6 | orta | Smarkets (borsa) |
| **23 Kas gece** 00:30 | Brezilya Serie A | Fluminense - Mirassol SP | %60 / %23 / %17 | 1.88–0.92 | 1-0 (%11) | 3,5 Gol Alt/Üst: 3,5 Alt | 1.23 | %67.9 | orta | Smarkets (borsa) |
| **23 Kas gece** 00:30 | Ekvador Pro Lig | LDU Quito - SD Aucas | %52 / %26 / %21 | 1.54–0.88 | 1-0 (%14) | — | — | — | yok | Smarkets (borsa) |
| **23 Kas gece** 01:00 | Kosta Rika Prmr Ligi, Açılış | Inter San Carlos - Sporting San Jose | %28 / %30 / %42 | 1.24–1.54 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.28 | %61.9 | düşük | Smarkets (borsa) |
| **23 Kas gece** 01:00 | Arjantin Primera Lpf, Clausura Playoff | River Plate - Lanus | %58 / %26 / %16 | 1.59–0.72 | 1-0 (%16) | Deplasman Herhangi Bir Yarıyı Kazanır: Hayır | 1.20 | %69.7 | orta | Smarkets (borsa) |
| **23 Kas gece** 01:30 | Brezilya Serie A | Bragantino - Vasco Da G. | %36 / %27 / %37 | 1.46–1.48 | 1-1 (%11) | 1. Yarı Çifte Şans: X-2 | 1.20 | %69.4 | orta | Smarkets (borsa) |
| **23 Kas gece** 02:00 | Nikaragua Prmr Ligi, Açılış | Walter Ferretti - Sebaco | %60 / %22 / %18 | 2.08–1.07 | 2-1 (%10) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.38 | %58.3 | düşük | OddsMath (Marathonbet) |
| **23 Kas gece** 02:05 | Guatemala Ulusal Lig, Açılış | Municipal - Antigua | %55 / %24 / %21 | 1.71–0.96 | 1-0 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.25 | %64.6 | düşük | OddsMath (BetInAsia/Pinnacle) |
| **23 Kas gece** 02:07 | Meksika Prmr Ligi, Açılış | CD Guadalajara - Cruz Azul | %45 / %23 / %32 | 1.69–1.40 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.25 | %65.7 | orta | Smarkets (borsa) |
| **23 Kas gece** 02:15 | Honduras Ulusal Lig, Açılış | Motagua - CD Olimpia | %36 / %27 / %38 | 1.35–1.40 | 1-1 (%12) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.25 | %63.3 | düşük | OddsMath (Marathonbet) |
| **23 Kas gece** 02:30 | ABD Major Lig Playoff | Chicago Fire - Charlotte | %60 / %21 / %19 | 2.36–1.32 | 2-1 (%9) | Gol Alt/Üst: 4.5 Alt | 1.22 | %67.4 | orta | Smarkets (borsa) |
| **23 Kas gece** 02:30 | Şili Premier Lig | Deportes Limache - D. La Serena | %43 / %26 / %31 | 1.59–1.32 | 1-1 (%11) | 1. Yarı Çifte Şans: X-2 | 1.22 | %65.2 | orta | Smarkets (borsa) |
| **23 Kas gece** 02:30 | Bolivya Profesyonel Ligi | S. A. Bulo Bulo - Always Ready | %18 / %18 / %64 | 1.19–2.39 | 1-2 (%10) | 1. Yarı Çifte Şans: 1-2 | 1.20 | %64.4 | düşük | Smarkets (borsa) |
| **23 Kas gece** 03:00 | Arjantin Prmr Nacional, Yük. PO | Gimnasia Y Tiro - T. Suarez | %34 / %35 / %32 | 0.91–0.87 | 0-0 (%17) | 1. Yarı Tek/Çift: Çift | 1.34 | %58.6 | düşük | Smarkets (borsa) |
| **23 Kas gece** 04:00 | Nikaragua Prmr Ligi, Açılış | Diriangen - Managua | %40 / %27 / %33 | 1.52–1.34 | 1-1 (%12) | 1. Yarı Çifte Şans: X-2 | 1.20 | %66.8 | orta | OddsMath (Marathonbet) |
| **23 Kas gece** 04:00 | Arjantin Primera Lpf, Clausura Playoff | Instituto - CA Huracan | %47 / %31 / %22 | 1.21–0.73 | 1-0 (%17) | — | — | — | yok | Smarkets (borsa) |
| **23 Kas gece** 04:10 | Guatemala Ulusal Lig, Açılış | CD Marquense - Aurora | %56 / %26 / %18 | 1.69–0.86 | 1-0 (%13) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.23 | %66.6 | orta | OddsMath (BetInAsia/Pinnacle) |
| **23 Kas gece** 04:10 | Meksika Prmr Ligi, Açılış | Queretaro - Necaxa | %46 / %25 / %29 | 1.72–1.33 | 1-1 (%11) | 2. Yarı Karşılıklı Gol: Yok | 1.26 | %65.8 | orta | Smarkets (borsa) |
| **23 Kas gece** 04:30 | Honduras Ulusal Lig, Açılış | Juticalpa - Olancho | %12 / %19 / %69 | 0.87–2.30 | 0-2 (%11) | 1. Yarı 1,5 Gol Alt/Üst: 1,5 Alt | 1.40 | %58.1 | düşük | OddsMath (Marathonbet) |
| **23 Kas gece** 04:30 | ABD Major Lig Playoff | V. Whitecaps - Real Salt Lake | %65 / %19 / %16 | 2.43–1.17 | 2-1 (%9) | Gol Alt/Üst: 4.5 Alt | 1.20 | %68.8 | orta | Smarkets (borsa) |

## Veri kalitesi / dürüst notlar
- Keskin fiyatlı ve P ≥ 0,70 bacak yalnız 2 maçta var; A/B kuponları bu yüzden 0,67 / 0,65 tabanıyla kuruldu. Kural hedefi (0,70) tam karşılanmıyor.
- Hiçbir bacakta pozitif beklenen değer yok (Nesine marjı). Kupon kâr beklentisi değil, en düşük kayıp/en yüksek tutma olasılığı tercihidir.
- Oranlar 22 Kas ~10:10 TSİ bültenine aittir; özellikle akşam ve gece maçlarında oynamadan önce yeniden kontrol edilmeli. Kadrolar maç saatinde netleşir.
- Kadın, U19/U21/U23, kupa ve alt lig maçlarının çoğunda takım geçmişi yok ("geçmiş yetersiz"); bunlar kupon dışında tutuldu ya da güven düşük işaretlendi.
- En olası skorlar bağımsız Poisson (μ ev, μ dep); tek skor en fazla ~%12–20.
- Web haber özetlerinde oynanmamış maçlar için "sonuç" uyduran özetler görüldü; yalnız maç öncesi bilgiler kullanıldı. Trabzonspor/Eyüpspor eksik listelerinde kaynaklar çelişiyor.
- Hiçbir kupon oynanmadı, Nesine hesabına dokunulmadı.
