# Veri kapsam Faz 2 onarımı — İY dolgusu satır kayması (28 Kas 2026)

## Hata
`data/matches.csv`'de 230.559. fiziksel satırda tarihsel bir **boş satır** var (d3584dd'den beri). pandas boş satırı
atlar; `mac_detay_doldur.fill` ise pandas satır sırasını `get_loc(i) + 1` ile fiziksel satıra çeviriyordu. Bu yüzden
boş satırdan sonraki her yazım **bir önceki maçın satırına** düştü. #38 (Faz 2) ile ek liglere yazılan 5.809 İY
hücresinden **2.142 satır** yanlış maça yazıldı; 474 satırda İY skoru tam skoru aşıyordu (ARG 87, BRA 82, AUT 73, ROM 39,
POL 31, JAP 24, DEN 22, SWE 20, RUS 19, MEX 19, NOR 16, SUI 14, USA 14, CHN 7, IRL 3, FIN 3, G1 1).
Aynı kalıp `arsiv_guncelle._drop_lines`'ta da vardı (ESPN satırı football-data ile değiştirilirken önceki gerçek
maçı silerdi); şimdiye kadar tetiklenmedi (değiştirme olmadı, CI bu betiği çalıştırmıyor).

## Düzeltme
- `mac_detay_doldur.fill`: fiziksel satır = boş olmayan satırların sırası; satır sayısı ve takım/tarih hizası
  doğrulanmazsa yazmadan durur.
- `arsiv_guncelle._drop_lines`: veri indeksi yalnız boş olmayan satırlarda ilerler.
- `data/matches.csv`: Faz 1 dosyası (4ee7ba9) üzerinde `arsiv_delik_doldur` + düzeltilmiş `mac_detay_doldur --kaynak arsiv`
  yeniden üretildi. #38'e göre fark yalnız İY sütunları (2.144 satır, hepsi boş satırdan sonra); boş satırdan önceki
  tüm satırlar ve eklenen 1.284 maç aynı. İY > tam skor satırı: 474 → 0.
- Bağımsız doğrulama: ESPN maç özeti İY'si ↔ openfootball İY'si (NOR/SWE/DEN/AUT 2025–26, n=314):
  onarım öncesi uyum %33–45, **sonrası %99,7–100**. ESPN ↔ football-data kontrolü (E0): %100.
- Testler: `tests/test_veri_kapsam_hiza.py` (eski kodda ikisi de başarısız, yenide geçer).

## Ölçüm (yüksek oran pazarları, sızıntısız ileri yürüyen backtest; model − piyasa log-loss, negatif = iyi)
| Pazar | Faz 1 (İY dolgusu yok) | #38 (kaymış İY) | onarım |
|---|---|---|---|
| İY/MS | −0.00302 (n 17.431) | −0.00431 (n 19.274) | −0.0032 (n 19.748, t −5,1) |
| İY skoru | −0.00001 | −0.00043 | −0.0007 (t −2,3) |
| 2Y KG | −0.00015 | −0.00062 | −0.0002 |
| Kesin skor | −0.00366 | −0.00375 | −0.0037 |

Onarılmış veri Faz 1 tabanına göre dört pazarda da nötr-ya-da-daha-iyi. #38 raporundaki "üstünlük arttı" sayıları
kaymış etiketlerle ölçülmüştü; geçerli sayılar bu tablodaki onarım sütunudur. ECE (sonra) İY/MS 0,0020, İY skoru 0,0013,
2Y KG 0,0045. `data/calibration/yuksek_oran_kalibrasyon.json` değiştirilmedi; bu pazarlar banko kupona girmez.
