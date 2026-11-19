# QuantFoot Gelişim Yol Haritası (Kasım 2026)

Önceki taramalar: [literature_review_2026_11.md](literature_review_2026_11.md) (bileşen bazlı),
[../markets.md](../markets.md) (20 pazar). Bu belge, sistemi "daha iyi tahmin eden" değil
**piyasaya karşı ölçülebilir avantajı olan** bir sisteme dönüştürmek için öncelik sırası verir.
Değerlendirmeler makale özetlerine dayanır.

> **Güncelleme (19 Kasım):** Deneyler yapıldı, bkz. [experiments_2026_11.md](experiments_2026_11.md).
> 16.423 maçlık ileri-yürüyen testte 15 modelin hiçbiri piyasaya bilgi katmadı (w = 0.00);
> keskin–yumuşak oran farkı ise pozitif CLV ve ROI verdi. Öncelik buna göre değişti: P1-4 birinci,
> model iyileştirmeleri (P2) ancak yeni bir bilgi kaynağıyla anlamlı.

## Önce dürüst tespit

1. **Modelin piyasaya bilgi kattığı henüz gösterilmedi.** 18 Kasım'da oranı olan 14 maçta 1X2
   log-loss model 0.7533, marjsız piyasa 0.7526; havuz ağırlığı w = 0.14, %95 güven aralığı
   0.00–1.00 (yani hiçbir şey söylenemez). Literatürde de yapısal modellerin kapanış oranına bilgi
   katmadığı sık görülür: Serie A'da 19 sezonda Dixon-Coles'un piyasayla havuzdaki ağırlığı 0
   (Pitcan 2026, arXiv:2608.11505).
2. **"Uzmanlık" tek başına tahmini iyileştirmez.** Euro 2008'de uzmanlar, amatörler ve futbolla
   ilgisizler skor tahmininde farklı değildi; bu bir "kontrol yanılsaması" (Khazaal ve ark. 2012,
   doi:10.1186/1747-597X-7-18).
3. **Bu repodaki en güçlü kanıt bir model değil, bir fiyat farkı stratejisi.** README'deki
   "Pinnacle açılış oranı vs en iyi yumuşak büro" testleri ve Kaunitz ve ark. (2017,
   arXiv:1710.02824) aynı fikri destekliyor: model kurmak yerine konsensüs / keskin oran ile
   yumuşak büro arasındaki farkı oynamak. Kaunitz ve ark. gerçek parayla kâr etti, ama kazanan
   hesaplar büro tarafından kısıtlandı.

Sonuç: "futbol dehası" olmanın yolu daha karmaşık model değil; (a) her şeyi piyasaya karşı
ölçmek, (b) fiyatta olmayan bilgiyi bulmak, (c) yanlış fiyatlanan büroyu bulmak.

---

## P0 — Ölçüm altyapısı (her şeyden önce)

| # | İş | Neden | Kaynak |
|---|---|---|---|
| 1 | **CLV takibi:** `daily.py predict` anındaki oranı ve maç başlamadan hemen önceki (kapanış) oranı kaydet; her seçim için CLV = alınan oran / kapanış oranı − 1 | Kapanışı yenmek, sonuçlardan çok daha az örneklemle avantajın en güvenilir göstergesi. `tipsaudit.csv` zaten CLV içeriyor | Kaunitz ve ark. 2017; README §3 |
| 2 | **Havuz ağırlığı testi:** `verify` çıktısına model + marjsız piyasa log-opinion-pool ağırlığı ve bootstrap güven aralığı | Model bilgi katmıyorsa ağırlık 0 çıkar; bahis yapmadan bunu bilmek gerekir | Pitcan 2026 |
| 3 | **Haftalık kalibrasyon raporu:** CORP güvenilirlik diyagramı, MCB/DSC ayrıştırması, log skoru | Bahiste model seçimi doğruluğa değil kalibrasyona göre yapılmalı | Dimitriadis ve ark. 2023 (arXiv:2301.10803); Walsh & Joshi 2023 (arXiv:2303.06021); Wheatcroft 2019 (arXiv:1908.08980) |

## P1 — Fiyatta olmayan bilgi kaynakları

| # | İş | Kanıt | Not |
|---|---|---|---|
| 4 | **Keskin–yumuşak oran farkı stratejisini canlıya taşı:** Pinnacle / konsensüs oranını yumuşak büro (ör. Nesine) oranıyla karşılaştır | Kaunitz ve ark. 2017; README'deki 2026 testi (+%5–9 ROI, p < 0.05) | Canlı oran kaynağı gerekir (The Odds API bağlayıcısı kodda var: `fetch_the_odds_api_slate`). Hesap kısıtlaması riski |
| 5 | **Gerçek xG verisi** (şut bazlı) ile `xg_proxy` yerine takım reytingi | xG, geleneksel istatistiklerden daha iyi gelecek tahmini (Mead ve ark. 2023, doi:10.1371/journal.pone.0282295); maç öncesi tahminde EPV xG'den de iyi (Forcher ve ark. 2025, doi:10.3389/fspor.2025.1713852); isabetli şut modeli gol modeline bilgi katıyor (Pitcan 2026) | Veri kaynağının kullanım koşulları kontrol edilmeli |
| 6 | **Kadro / eksik oyuncu etkisi:** oyuncu bazlı plus-minus ile eksik oyuncunun gol beklentisine etkisi | Plus-minus ve xG plus-minus (Kharrat, López Peña & McHale 2017, arXiv:1706.04943); düzenlileştirilmiş RAPM (Bajons & Hornik 2024, arXiv:2407.17832). **Karışık kanıt:** EPL'de kadro bilgisi tahmini iyileştirmedi (Peters & Pacheco 2022, arXiv:2210.06327); Transfermarkt değeri ≈ Elo, birleşince küçük iyileşme (Csurilla & Csató 2026, arXiv:2609.21674) | Asıl değer, kadro açıklandığı an (maçtan ~1 saat önce) piyasa tam fiyatlamadan önce davranmakta olabilir |
| 7 | **Fikstür yoğunluğu / dinlenme günü / seyahat** özellikleri | Meta-analiz: yoğun fikstür toplam koşu mesafesini etkilemiyor, taktik performansı etkileyebilir (Julian ve ark. 2021, doi:10.1007/s40279-020-01359-9); yoğunluk ve seyahat sakatlık riskini artırıyor (den Hollander ve ark. 2024) | **Ucuz deney:** `matches.csv` tarihlerinden dinlenme günü hesaplanıp etkisi hemen ölçülebilir |
| 8 | **Oran hareketi:** açılıştan kapanışa hareket bilgili bahisçiyi yansıtır; son dakika düşüşü olan seçimler daha yüksek getiri (at yarışı) | Hanyu ve ark. 2026 (arXiv:2509.14645); canlı bahiste piyasa haberlere aşırı tepki veriyor (Ötting ve ark. 2021, arXiv:2108.00821) | `tipsaudit.csv` açılış/kapanış içeriyor → hareket yönü özelliği test edilebilir |

## P2 — Model iyileştirmeleri (ancak P0 ölçümüyle doğrulanırsa)

| # | İş | Kaynak |
|---|---|---|
| 9 | Modified Glicko (açık veri/kod, 1.2 milyon maç) ile `pyramid` / Glicko karşılaştırması | Shelopugin & Sirotkin 2026 (arXiv:2611.15378) |
| 10 | Uyarlanabilir önselli dinamik Bayes model (transfer / hoca değişimi kırılmaları) | Macrì-Demartino ve ark. 2025 (arXiv:2508.05891, `footBayes`) |
| 11 | CatBoost + pi-ratings karşılaştırma modeli | Bunker ve ark. 2024 (arXiv:2403.07669) |
| 12 | Kadın futbolu için ayrı model (şimdilik devre dışı) | Michels ve ark. 2023 (arXiv:2307.02139) |
| 13 | Gol zamanında aynı takımın art arda gol eğilimi; iki gol geride çarpanının yeniden tahmini | Ayana ve ark. 2025 (arXiv:2501.18606); Maia ve ark. 2023 (arXiv:2312.04338) |
| 14 | Tek parametreli favori–sürpriz yanlılığı düzeltmeli devig | Goto ve ark. 2026 (arXiv:2604.17194) |

## P3 — Para yönetimi ve disiplin

| # | İş | Kaynak |
|---|---|---|
| 15 | Uyarlanabilir kesirli Kelly; günlük/haftalık kayıp limiti; kombine yerine tekil | Uhrín ve ark. 2021 (arXiv:2107.08827); Long 2026 (arXiv:2603.26620) |
| 16 | Bahis defterini her gün tutmak (`ledger_report.py`) ve CLV ile birlikte değerlendirmek | — |

---

## Önerilen sıra

1. **P0-1 CLV takibi** + **P0-2 havuz testi** (birkaç gün içinde veri birikmeye başlar).
2. **P1-7 dinlenme günü deneyi** (elimizdeki veriyle bugün yapılabilir, maliyeti düşük).
3. **P1-4 keskin–yumuşak oran farkı** (repodaki en güçlü kanıt; canlı oran kaynağı gerekiyor).
4. P1-5 / P1-6 veri kaynakları netleşince; P2 maddeleri ancak P0 ölçümü bir sinyal gösterirse.

Birkaç hafta boyunca CLV ortalaması sıfırın altındaysa, model ne kadar karmaşık olursa olsun
bahis yapılmamalıdır.
