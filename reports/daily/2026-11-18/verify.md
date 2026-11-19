# 2026-11-18 — Tahmin ve Kupon Denetimi

- Sonuçlanan maç: **42**; en iyi seçim isabeti: **30/42**

## Model piyasaya bilgi katıyor mu?

- 1X2 log-loss (14 maç) — piyasa: **0.7526**, model: **0.7533**, en iyi havuz: 0.7525
- Havuzda modelin ağırlığı **w = 0.14** (%95 güven aralığı 0.00 – 1.00). Aralık 0'ı içeriyor: model piyasaya **kanıtlanmış bilgi katmıyor**.

## Değer tekilleri: kapanış çizgisi (CLV) ve kâr/zarar

- Kapanış oranı yok: maçlardan önce `snapshot` çalıştırılmalı.

_Karar kuralı: haftalar boyunca adil CLV'nin güven aralığı sıfırın üstünde değilse bahis yapılmamalı._

## Kuponlar

- KUPON 1 — 3 Maçlık Çekirdek Güven Kuponu (En Düşük Varyans): 3/3 bacak tuttu — **KAZANDI**
- KUPON 2 — 4 Maçlık Avrupa & Brezilya İdeal Denge Kuponu: 4/4 bacak tuttu — **KAZANDI**
- KUPON 3 — 5 Maçlık Orta Ölçekli Favori Kuponu: 5/5 bacak tuttu — **KAZANDI**
- KUPON 4 — Hedef 10x Optimize Kupon (%100 Canlı Piyasa Oranlı): 4/5 bacak tuttu — **KAYBETTİ**
- KUPON 5 — Hedef 20x Optimize Kupon (%100 Canlı Piyasa Oranlı): 4/7 bacak tuttu — **KAYBETTİ**
- KUPON 6 — Nesine 2. Lig Gündüz (13:00 & 15:00) Kuponu: 2/4 bacak tuttu — **KAYBETTİ**
- KUPON 7 — İlk Yarı / Maç Sonucu (İY/MS) Özel Kuponu: 1/4 bacak tuttu — **KAYBETTİ**

## Maçlar

| Maç | Skor | En iyi seçim | Sonuç | Piyasa kaynağı |
|---|---|---|---|---|
| 12 Bingölspor - Sakaryaspor | 0-1 (İY 0-0) | 1.5 Üst | ✗ | - |
| 1461 Trabzon FK - Kahramanmaraş İstiklalspor | 1-0 (İY 0-0) | 3.5 Alt | ✓ | - |
| Adana Demirspor - GMG Kastamonuspor | 2-2 (İY 2-1) | İY 0.5 Üst | ✓ | - |
| Ankara Demirspor - 52 Orduspor FK | 0-2 (İY 0-1) | İY 0.5 Üst | ✓ | - |
| Hatayspor - İnegöl Kafkas SK | 0-2 (İY 0-1) | 3.5 Alt | ✓ | - |
| ISBAŞ Isparta 32 Spor - Somaspor | 0-0 (İY 0-0) | 3.5 Alt | ✓ | - |
| MKE Ankaragücü - Kırklarelispor | 1-1 (İY 0-0) | 3.5 Alt | ✓ | - |
| Serik Spor - Erzincanspor | 0-1 (İY 0-0) | 3.5 Alt | ✓ | - |
| Seza Çimento Elazığspor - Menemen FK | 1-1 (İY 1-0) | MS 1 | ✗ | - |
| Şanlıurfaspor - Efor Çay Erbaaspor | 2-1 (İY 1-0) | 3.5 Alt | ✓ | - |
| Aliağa Futbol A.Ş. - Sebat Gençlik Spor | 2-0 (İY 1-0) | 3.5 Alt | ✓ | - |
| Arnavutköy Belediyesi Futbol SK - 68 Aksaray Belediyespor | 2-3 (İY 1-1) | 3.5 Alt | ✗ | - |
| Fethiyespor - Kütahyaspor | 2-1 (İY 1-0) | 3.5 Alt | ✓ | - |
| Güzide Gebze Spor - Ankaraspor | 2-1 (İY 2-1) | İY 0.5 Üst | ✓ | - |
| Karacabey Belediyespor - Beyoğlu Yeni Çarşı | 0-3 (İY 0-1) | 3.5 Alt | ✓ | - |
| Çorluspor 1947 - Muş Spor | 1-4 (İY 0-2) | 3.5 Alt | ✗ | - |
| İnegölspor - İskenderunspor A.Ş. | 2-0 (İY 1-0) | 3.5 Alt | ✓ | - |
| Bengaluru United FC - Sreenidi Deccan FC | 2-2 (İY 1-2) | 3.5 Alt | ✗ | - |
| Levante - Eibar | 0-1 (İY 0-0) | 1.5 Üst | ✗ | - |
| BK Häcken - Manchester City | 0-2 (İY 0-0) | MS 2 | ✓ | tahmin anı |
| Real Madrid - Internazionale | 3-1 (İY 1-1) | MS 1 | ✓ | tahmin anı |
| CP Cacereño - Alavés | 1-1 (İY 1-0) | 3.5 Alt | ✓ | - |
| Portugalete - Real Unión Irun | 0-0 (İY 0-0) | 1.5 Üst | ✗ | tahmin anı |
| Utebo - CD Sabadell | 0-3 (İY 0-3) | 1.5 Üst | ✓ | tahmin anı |
| London City Lionesses - Brighton & Hove Albion | 0-1 (İY 0-0) | 1.5 Üst | ✗ | - |
| Manchester United - Everton | 2-1 (İY 2-0) | İY 1.5 Alt | ✗ | - |
| Nottingham Forest - Liverpool | 1-4 (İY 0-3) | 3.5 Alt | ✗ | - |
| Tottenham Hotspur - Leicester City | 7-0 (İY 4-0) | 1.5 Üst | ✓ | - |
| West Ham United - Wolverhampton | 3-0 (İY 0-0) | 1.5 Üst | ✓ | - |
| Alcoyano - Mallorca | 1-1 (İY 1-1) | 1.5 Üst | ✓ | tahmin anı |
| Badajoz - Tenerife | 2-5 (İY 0-3) | 3.5 Alt | ✗ | - |
| CD Samper - Valencia | 0-3 (İY 0-1) | 3.5 Alt | ✓ | - |
| CD Minera - FC Cartagena | 1-1 (İY 0-0) | 2Y 0.5 Üst | ✓ | tahmin anı |
| Reus FC Reddis - Barakaldo | 1-1 (İY 0-0) | İY 1.5 Alt | ✓ | tahmin anı |
| Alianza Atlético - Melgar | 1-1 (İY 0-1) | 3.5 Alt | ✓ | tahmin anı |
| Chelsea - Paris Saint-Germain | 1-0 (İY 0-0) | MS 1 | ✓ | tahmin anı |
| Juventus - OH Leuven | 2-0 (İY 0-0) | MS 1 | ✓ | tahmin anı |
| Coritiba - Santos | 0-1 (İY 0-0) | ÇŞ 02 | ✓ | tahmin anı |
| Remo - Chapecoense | 2-0 (İY 2-0) | İY 0.5 Üst | ✓ | tahmin anı |
| Cruzeiro - Palmeiras | 2-1 (İY 0-0) | İY 0.5 Üst | ✗ | tahmin anı |
| Flamengo - Athletico-PR | 2-1 (İY 2-1) | MS 1 | ✓ | tahmin anı |
| Always Ready - Real Potosí | 3-1 (İY 2-1) | İY 0.5 Üst | ✓ | - |
