# Kalibrasyon dersleri — 21 Kasım 2026 akşam denetimi

**Örnek küçük:** tek gün, ~320 bitmiş maçın ana tercihi (tüm seçimler: 2.490). Aşağıdaki ayarlar bilinçli olarak
**ılımlı** tutuldu ve tek günlük gürültüye aşırı uyum riskine karşı birkaç günlük sonuç defteriyle
(`scripts/sonuc_defteri.py`, `scripts/gun_degerlendirme.py`) yeniden gözden geçirilmeli.

## Gözlem (yalnız toplu sayılar)

| Kesit | n | İsabet | Ort. P | Fark |
|---|---:|---:|---:|---:|
| Ana tercih (maç başı en yüksek P) | 320 | %63,4 | %67,0 | −3,5 |
| Tüm uygun seçimler | 2.490 | %61,3 | %61,9 | −0,6 |
| Ana tercih, P %60–65 | 46 | %50,0 | %63,2 | −13,2 |
| Ana tercih, P %65–70 | 193 | %66,3 | %67,5 | −1,2 |
| Ana tercih, P %70–75 | 59 | %64,4 | %71,1 | −6,7 |
| Ana tercih, "diğer" kademe ligler | 116 | %59,5 | %66,7 | −7,2 |
| Ana tercih, ev sahibi golleri | 35 | %48,6 | %67,3 | −18,7 |
| Ana tercih, çifte şans | 34 | %50,0 | %65,5 | −15,5 |
| Tüm seçimler, Alt/Üst | 272 | %61,4 | %61,6 | −0,2 |

Yorum: tüm seçimlerde kalibrasyon iyi; şişme, maç başı **en yüksek P'yi seçerken** ortaya çıkıyor (seçim yanlılığı /
"kazananın laneti"). Bu en çok türetilmiş (matris/gol modeli) fiyatlarda ve zayıf ailelerde görüldü.

## Uygulanan kurallar (`src/quantfoot/strategy/banko_guard.py`, parametreler `src/quantfoot/settings.py`)

| Parametre | Varsayılan | Etki |
|---|---:|---|
| `SHRINK_DERIVED` | 0.10 | Doğrudan keskin fiyatı olmayan P: `p' = 0.5 + (p − 0.5)(1 − k)` → %70 → %68, %66 → %64,4 |
| `SHRINK_DIRECT` | 0.0 | Doğrudan keskin fiyat zaten piyasa P'si, büzülmez |
| `SHRINK_OTHER_TIER_EXTRA` | 0.10 | "Diğer" kademe ligde ek büzme (türetilmişte tam, doğrudanda yarısı) → türetilmiş %70 → %66,2 |
| `WEAK_FAMILIES` | ev_golleri, cifte_sans | Banko modunda yalnız doğrudan keskin fiyatla (`WEAK_FAMILY_REQUIRE_DIRECT`) |
| `WEAK_FAMILY_EXTRA_MIN_PROB` | 0.05 | Zayıf aile doğrudan fiyatlıysa banko tabanı %65 → %70 |

* Büzme yalnız p > 0.5 için aşağı düzeltir; düşük P asla yükseltilmez. Canlı bacaklar mevcut piyasa tavanını
  (piyasa P + 5 puan) kullanır.
* Kaynağı bilinmeyen P (bacakta `direct` alanı yok) temkinli olarak türetilmiş sayılır.
* Banko P tabanı (%65) ve P(kupon) **büzülmüş** P ile hesaplanır; `nesine_kupon.filter_pools_for_mode` aday havuzunu da
  aynı kuralla süzer (`kupon_modu.leg_mode_ok`). Risk modunda büzme uygulanır, aile kuralı uygulanmaz.
* Lig kademesi denetim betiğiyle aynı kaba lig-adı sınıflamasıdır (`banko_guard.league_tier`).

## Yeniden bakılacaklar

* Birkaç günlük defterle bant/aile/kademe kalibrasyonunu yeniden hesapla; fark kapanırsa büzmeyi azalt, sürerse
  `SHRINK_DERIVED` 0.15–0.20'ye ve %60–65 bandı için ayrı ceza düşünülebilir.
* Ev sahibi golleri / çifte şans için n≈35; tek günlük sonuç. Doğrudan fiyatlı örnekler ayrı ölçülmeli.
