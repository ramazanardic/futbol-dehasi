# QuantFoot — GitHub sürüm incelemesi ve tüm AI tahmin/kupon denetimi
**Hazırlanma:** 28 Kasım 2026, 11:46 TSİ · **Kapsam:** 8ff235c (22 Kas 17:56 TSİ) → origin/main bac5554 (28 Kas 05:21 TSİ), 60 commit
**Skor kaynağı:** Nesine GetUnliveMatches 18–28 Kas (İY + 90'), 3.290 maç. Bulunamayan sonuç = *belirsiz*; hiçbir skor tahmin edilmedi.
**Yöntem:** Yerel main'e dokunulmadı. `git fetch` + ayrı worktree'ler: `/workspace/fd_origin_ro` (origin/main) ve `/workspace/fd_base_8ff235c` (eski sürüm). Silinmiş tahmin arşivleri git geçmişinden (8f1d4ea, 04b8b7b) çıkarıldı.
Ham veriler: `rows.json` (2.591 seçim/bacak), `coupons.json` (170 kupon), betikler `betik/`.

## 1. Commit/PR özeti
- 60 commit (6'sı PR birleştirme: #13, #14, #15, #17, #18 Codex; #20 denetim). Hepsi `ramazanardic` hesabından. 15'inde `Co-Authored-By: Claude Opus 5.5` var. Geri kalanların yazarını commit mesajından tahmin ettim: Codex/ChatGPT (Türkçe PR'lar), Antigravity/Gemini (v3–v8.1, v5, unified engine) ve Gemini (`geminitahmin` dosyaları).
- Benim PR #12 tarih düzeltmem (ESD) main'de var.
- Birleşmemiş iki dal var: `docs/readme-2026-11-24` ve `fix/core-integrity-2026-11-24`.
- Testler: origin/main **1943 geçti**, eski 8ff235c **1786 geçti**. Ama hiçbir test yeni motorda takım-gol/KG yasağını ya da P≥0,70 hedefini denetlemiyor.

### Kritik değişiklikler (kural etkisi)
| Commit | Ne değişti | Ramazan'ın kuralına etkisi |
|---|---|---|
| **3e63ede + bac5554** (28 Kas) unified_engine + temiz_kupon | Gold Core: Ev İY 0.5 Alt, Dep İY 0.5 Alt, Ev 1.5 Üst/Alt, KG Yok, İY&2Y KG Yok. P tabanı 0,56 (pazara göre 0,57–0,65). Varsayılan **2 adet 20+ oranlı kupon**. `--ozel` ile skor, İY/MS dönüşü ve İki Yarıda KG Var kuponları. | **BOZAR:** takım-gol yasağı, KG yasağı, P≥0,70 ve piyango kupon yasağı |
| **9b9aa73** (24 Kas) + settings | BANKO_MIN_LEGS 5→**1**, MAX 6→5. kupon_kur'a "asla hayır deme" yedek turu. | **BOZAR:** "banko bacakla olmuyorsa dürüstçe söyle" kuralı |
| **9b9aa73/875b1cd/9f845e0** nesine_kupon | Kademeli havuz: P_cal 0,68 → **0,65** + kupa maçları + orta güven global büro, EV tabanı −%18. `--model-bacak` varsayılan. | **GEVŞETİR:** 0,70 hedefi sessizce düşüyor |
| **9f845e0/e0a9f43** kasa_koruma | P≥**%60**, EV≥−%10 | **BOZAR:** 0,65 alt sınırının altında |
| **c40d6ca + a3a24db/58ebf83** (27 Kas) | Yüksek oran motoru günlük hattın "derin" adımına girdi. v8 zip: Kelly, CLV, prop, simülatör (~30 bin satır). | RİSK: ölçülmemiş yüksek oran önerileri |
| **68a21c8** (26 Kas) | **340 dosya, 1,67 milyon satır silindi**: grokbot 21–22 Kas arşivi, antigravity 22 Kas, oynanan_kuponlar.json, nesine_kupon_gecmisi.csv. Aynı commit'te kupon kodu da değişti, mesajda silme yazmıyor. | **BOZAR:** denetim izini yok etti |
| 68a21c8/9f845e0 coupon_rules | Yasak ailelere Çifte şans ve Handikap eklendi. "Rehabilite" bacak artık yasak aileyi delemiyor. mac_limit=1. | SIKILAŞTIRIR, tut |
| 06e8000, a4253a6, 574bc66, 1715e40, c954188, 79b58b2 | market_diagnosis kalkanları: İY 1.5 Alt tempo, model-KG freni, İY ÇŞ 12, steam | Çoğu sıkılaştırma, tut |
| f062627…f6ee603, 8f1d4ea (Claude) | Lig bazında ilk yarı gol payı | Tut, izle |
| 5d315da, e12c76f, 1087c83, 0cb3094, 5996bae (Claude) | UTF-8, auto_learn çift sayım, kalibrasyon, getiri raporu, LightGBM | Tut |

## 2. AI başına performans (Nesine ile yeniden notlandı)
**Ana seçimler** (ROI = her seçime 1 birim, Nesine oranıyla)
| AI | Sürüm | Tutan/notlanan | İsabet | Ort. P | Fark | ROI |
|---|---|---|---|---|---|---|
| grokbottahmin (ben) | eski (21–22 Kas) | 309/431 | **%71,7** | %67,5 | +4,2 | −%11,3 |
| claudetahmin | eski (20–21 Kas) | 366/535 | %68,4 | %66,7 | +1,7 | −%14,1 |
| antigravitytahmin | eski (22 Kas) | 131/198 | %66,2 | %67,2 | −1,0 | −%17,4 |
| antigravitytahmin | **yeni (24–25 Kas)** | 58/93 | **%62,4** | %69,0 | **−6,6** | −%22,8 |
| chatgbttahmin | eski (21 Kas) | 254/412 | %61,7 | %62,8 | −1,1 | −%16,3 |
| geminitahmin | eski (20–21 Kas) | 85/150 | %56,7 | %66,1 | −9,4 | −%25,9 |
| geminitahmin | yeni (24–26 Kas) | 67/112 (+7 belirsiz) | %59,8 | %65,2* | — | −%8,9 |
*26 Kas'ta P yazılmamış.

**Kuponlar**
| AI | Sürüm | Kupon | Tutan | Bacak isabeti | Ort. bacak | Ort. oran | Oynanan / TL |
|---|---|---|---|---|---|---|---|
| grokbot | eski | 24 | 2 (ikisi de oynanmadı: A banko 2,70; 10'lu 3,48) | %67,2 | 5,5 | 10,1 | 13 kupon, 1.720 TL yatırıldı, 0 döndü (hepsi 21–22 Kas) |
| antigravity | eski | 8 | 0 | %52,9 | 6,4 | çok yüksek (30'lu maksimum oran dahil) | — |
| antigravity | yeni | 2 | 0 | %60,0 | 5,0 | 2,7 | — |
| chatgbt | eski | 6 | 1 | %50,0 | 3,0 | 4,6 | — |
| claude | eski | 2 | 0 | %62,5 | 4,0 | 5,3 | — |
| gemini | eski | 11 | 1 | %54,9 | 4,9 | 13,9 | CSV'de "500 TL/400 TL" yazıyor, oynandığı kanıtlanmadı |
| gemini | **yeni** | **117** | **13** (+7 belirsiz) | %56,1 | 4,0 | **83** | — |

**Gerçek para defteri (repoda, Nesine hesabından çekilmiş):**
- 20 Eki–10 Kas: 151 kupon, 3 tuttu, 20.835 TL yatırıldı, 5.313,54 TL döndü.
- 13–21 Kas: 30 kupon, 8 tuttu, 2 açık, 4.597 TL yatırıldı, 7.301,95 TL döndü.
- **23–28 Kas arasında oynanan hiçbir kupon repoda yok.**

## 3. Eski ve yeni sürüm karşılaştırması
| Ölçüt | Eski (≤22 Kas) | Yeni (≥23 Kas) |
|---|---|---|
| Ana seçim isabeti | %66,3 (1.726) | %61,0 (205) |
| P %70–75 bandı (seçim+bacak) | %76,3 (P %71,1) | **%65,5 (P %72,7)**: aşırı güven |
| P %65–70 bandı | %70,1 | %64,8 |
| P<%65 bacaklar | %54,3 | %50,7 |
| P yazılmamış bacak | 21 | **265** (%50,7 isabet) |
| Oran >1,80 bacak | 33 (%39) | **178** (%39,4) |
| Kupon bacağı, kurala uygun | %68,9 (103) | %67,6 (176) |
| Kupon bacağı, **kural dışı** | %57,0 (79) | **%48,0 (250, ort. oran 2,49)** |
| Kural dışı bacak içeren kupon | 33/35 | **113/117** |
| 15+ oranlı kupon | 0/13 | **0/25** |
| 3–4 bacaklı kupon (yeni sürüm ort. oran 81–159) | — | 7/70, bacak isabeti %42–48 |
| 5 bacaklı kupon | 1/12 | 6/31 (bacak %71) |
| Aynı AI (Antigravity) temiz bacaklar | %72,3 (112) | **%61,3 (80)** |
| Antigravity 2Y KG Yok / MS | %72 / 7/10 | %55,6 / 1/5 |
Pazar ailesine göre yeni sürüm: İY/MS 2/14, Skor 0/4, İY sonucu 4/12, kombine %47,8 (111), 2. yarı 7/15, MS %56,3 (P %66). İY Alt/Üst %67,2 ve 2Y KG Yok %66,7 göreceli olarak dayandı.

## 4. Kaybın ana nedenleri
1. **Kural dışı bacaklar kupona girdi.** Yeni dönemde kupon bacaklarının %62'si (287/464) Ramazan'ın kurallarını ihlal ediyor: oran >1,80, İY/MS, skor, İY sonucu, KG ve takım golü. Bunlar %48 tuttu, kurala uygun bacaklar %68. Bu ihlaller 28 Kas'ta unified_engine ile koda da yazıldı: takım-gol ve KG "Gold Core" listesinde, 20x kuponlar varsayılan.
2. **Yüksek oran hedefi ve az bacakta büyük oran.** 15+ oranlı 25 kuponun hiçbiri tutmadı. 3–4 bacaklı kuponların ortalama oranı 81–159, bacak isabeti %42–48. Yüksek oran motoru ve 20x kurucular her gün bu kuponları üretiyor.
3. **P eşiği düştü, kalibrasyon da kaydı.** P eşiği kademeli olarak 0,68/0,65'e, kasa korumada 0,60'a, yeni motorda 0,56'ya indi. Yeni dönemde "%70–75" denen bacaklar %65,5 tuttu. Antigravity'nin aynı kurallara uyan bacakları %72'den %61'e düştü. Bunun bir kısmı UEFA haftasındaki sürprizler (Lille–Bayern, PSG–Roma, Plzeň–Benfica), yani şans olabilir.
4. **"Asla hayır deme" ve aşırı kupon sayısı.** Asgari bacak 1'e indi ve ret yolu kapatıldı. Gemini günde 55–57 kupon yazdı ve aynı seçimi 3 kupona kadar tekrar kullandı (`secenek_kullanim_sayisi` 3/3). Bu, korelasyonlu toplu kayıp demek.
5. **Kayıplar görünmez oldu.** Gemini kendi sonuçlarını yanlış yazdı: 112 seçimin 17'sinde Nesine'yle çelişiyor (kendi beyanı %73, gerçek %67; örnek: Feyenoord 2-3 kaybetti ama "TUTTU" yazılmış). Ortak karne Gemini'yi şema uyumsuz diye hiç notlamadı. 68a21c8 de oynanan kupon arşivini sildi. Sonuçta kimse kaybı fark etmedi.

## 5. Öneri (UYGULANMADI, yalnız öneri)
**Geri al ya da devre dışı bırak:**
- 3e63ede + bac5554 (unified_engine/temiz_kupon): tamamen geri al. Tutulacaksa: takım-gol ve KG Gold Core'dan çıksın, `--adet-20x` varsayılanı 0 olsun, `--ozel` kaldırılsın, P≥0,70 ve oran 1,20–1,80 olsun.
- 9b9aa73'teki "asla hayır deme" yedek turu ve BANKO_MIN_LEGS=1 geri alınsın. Önerim 2–4 (en çok 5) bacak ve dürüst ret.
- nesine_kupon Kademe 3 (P 0,65 + kupa + EV −%18) ve `--model-bacak` varsayılanı kaldırılsın. Kademe 2'deki 0,68 tartışılır.
- kasa_koruma `min_p` 0,60 → 0,70.
- c40d6ca: `yuksek_oran_motoru.py` ve `yuksek_oran_analiz.py` günlük hattın "derin" adımından çıkarılsın. Modüller kalabilir, kupona girmesin.
- 68a21c8: yalnız silme kısmı geri alınsın (`tahminler/` arşivleri 8f1d4ea'dan geri gelsin). Commit'in kod kısmı ayrıca incelensin.
- Gemini çıktıları ortak şemaya (Nesine kodu, P, oran) zorlansın. Kendi TUTTU/YATTI sütunu yasaklansın, not yalnız `gun_degerlendirme.py` ile verilsin.

**Tut:** coupon_rules sıkılaştırmaları (Çifte şans/Handikap yasağı, rehabilitasyon deliği kapandı, mac_limit=1), market_diagnosis kalkanları (06e8000, a4253a6, 574bc66, 1715e40, c954188, 79b58b2), Claude'un düzeltmeleri (5d315da, e12c76f, 1087c83, 0cb3094, 5996bae), yarı pazarları (izleyerek), PR #13/#14/#15/#20 denetim araçları ve tarih düzeltmesi.

**Yerel main için:** origin/main körlemesine çekilmesin. Ayrı bir dalda yalnız "tut" listesi cherry-pick edilsin, testler ve kural testleri koşulsun.

## 6. Belirsiz kalanlar
- 23–28 Kas'ta gerçekten oynanan kuponlar ve TL kaybı repoda yok. Bunun için Nesine "Kuponlarım" sayfasının salt okunur incelenmesi gerekir.
- 23 Kas ve 27–28 Kas için hiçbir AI çıktısı yok, 26 Kas'ta yalnız Gemini var. Yeni sürüm kuponlarının %98'i Gemini'nin kendi şeması; ortak hattın çıktısı değil.
- Antigravity 24–25 Kas ham CSV'leri yok, yalnız ortak karne var.
- Gemini 25 Kas'ın 107 bacağı (skor, handikap, "farkla kazanır", korner) notlanamadı.
- Braga–KuPS, Maritzburg–Polokwane Nesine'de bulunamadı. Al-Faisaly–Al-Diriyah eşleşmesi tahmini.
- Commit yazarları imzadan değil, mesajdan tahmin edildi.
- Örnek küçük ve 24–26 Kas UEFA haftası. Kurala uygun bacaklardaki düşüşün bir kısmı şans olabilir.
