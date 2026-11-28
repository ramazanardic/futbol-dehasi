# Son-120-gün form ve xG vekili: 18–28 Kas denetim ölçümü

Betik: `scripts/kaynak_etki_olcumu.py` (ham sayılar: `kaynak_etki_2026-11-28.json`). Form yalnız seçim gününden önceki maçlardan
okunur. Sonra = 0,6·P + 0,4·öncül.

* Kapsam: 1147 maçın 444'ünde (%38,7) iki takımın da formu var (ESPN + Open Matchday + Nesine). GFI + football-data'da olmayan
  küçük liglerin bir kısmı (Belarus, Hırvatistan 2., Sırbistan, Güney Kore K-Lig 2 …) hâlâ formsuz.
* Tüm seçimler (n=904): log-loss 0,6285 → 0,6272 (form) / 0,6244 (yalnız gol aileleri, xG vekili).
* Gol aileleri (n=496): 0,6227 → 0,6159; eşleştirilmiş bootstrap farkı −0,0068, %95 aralığı [−0,0161; +0,0037] (sıfırı kapsıyor).
* xG vekili (şut tabanlı Poisson, gerçek xG değil) form üzerine: fark −0,0034 [−0,022; +0,0135] (n=198).
* P ≥ 0,70 gol bacakları (n=129): fark −0,0022 [−0,0215; +0,0238]; ham P ≥ 0,70 kümesinde form karışımı log-loss'u hafif kötüleştirir.

**Karar:** anlamlı iyileşme yok → `RECENT_FORM_ENABLED=False` (varsayılan kapalı). Kod hazır: `QF_RECENT_FORM=1`
(`QF_RECENT_FORM_XG=1` xG vekili için).

# ESPN ilk-11 kalkanı (sakat/cezalı + kadro)

Betik: `scripts/kalkan_etki_olcumu.py` (`kalkan_etki_2026-11-28.json`). ESPN kadrosu bulunan 260 maç / 758 seçim (toplam 2228).
Düzenli ilk 11 = önceki 5 maçın ≥ %60'ında ilk 11. Kalkan, düzenli oyuncu açıklanan ilk 11'de yoksa işaretler.

| Kural | işaretli maç | işaretli isabet / ort. P | işaretsiz isabet / ort. P | (isabet−P) farkı, %95 maç-kümesi bootstrap |
|---|---|---|---|---|
| gevşek (kaleci, ≥2 savunma, ≥2 hücum, ≥3 toplam) | 199/260 | 0,639 / 0,659 | 0,749 / 0,657 | +0,111 [0,002; 0,211] |
| yalnız kaleci | 54/260 | 0,556 / 0,663 | 0,691 / 0,658 | +0,140 [0,015; 0,261] |
| P ≥ 0,70 · gevşek | 105 maç | 0,702 / 0,728 (n=191) | 0,792 / 0,730 (n=48) | +0,088 [−0,107; 0,255] |
| P ≥ 0,70 · yalnız kaleci | 34 maç | 0,667 / 0,725 (n=54) | 0,735 / 0,729 (n=185) | +0,062 [−0,105; 0,225] |

Yön tutarlı: işaretli bacaklar fiyatlarının altında kalıyor. Tüm seçimlerde fark anlamlı, banko aşamasında (P ≥ 0,70) örnek küçük
ve aralık sıfırı kapsıyor. Gevşek kural maçların %76'sını işaretliyor (rotasyon gürültüsü), yalnız-kaleci kuralı daha seçici.
Yalnız ESPN kadrosu olan liglerde ölçüldü; sekiz karşılaştırma yapıldı (çoklu karşılaştırma uyarısı).

**Karar:** banko aşamasında anlamlı kanıt yok → `FREE_ABSENCES_ENABLED=False` (varsayılan kapalı). Veri toplanmaya devam eder
(`research["web"]`); birkaç hafta daha örnek birikince `yalnız_kaleci` kuralı yeniden ölçülmeli (hedef: P ≥ 0,70'te n ≥ 150 maç).
