# Maç başına web-araştırma adımı

`src/quantfoot/data/web_research.py` — günlük analizde (`nesine_global.build`) fiyatlama ve ESPN araştırmasından sonra,
**yalnız kupona aday maçlar** için (fiyatlanmış, özel bahis değil, en az bir seçimi P ≥ 0,62 ve oran ≥ 1,20) çalışır.
Elle: `python scripts/mac_web_arastirma.py --tarih 2026-11-22`. Kapatmak: `QF_WEB_RESEARCH=0`.

Sonuç `research["web"]` altına yazılır (bilgi kaydı). **Olasılığa ve kupon uygunluğuna dokunmaz**; mevcut ESPN `teams[taraf]`
kaydının boş alanları (form, last5, table) tamamlanır, üzerine yazılmaz, ESPN kaydı olmayan maça yeni `teams` açılmaz
(`teams` varlığı `_has_full_research` ile kupon uygunluğunu belirler). Banko kalkanına etkisi `FREE_ABSENCES_ENABLED`
(`QF_FREE_ABSENCES=1`) bayrağına bağlıdır; açıkken Transfermarkt yoksa `tm_absences` aynı şekilde yazılır.

## Kayıt şeması

```
research.web = {surum, tarih, sure_sn,
  takimlar.{home,away} = {name, son_maclar[{tarih,rakip,saha,skor,sonuc,kaynak,xg_vekil?}] (≤10), form (son 5), gol_ort,
      xg {xg,xga,kaynak} | xg_vekil {xf,xa,n,kaynak}, puan_durumu {rank,points,played,…,kaynak},
      hoca_degisikligi [ ... ] | "son 90 günde kayıt yok" | "bilinmiyor", sakat_cezali {..tm_absences şekli..} | "bilinmiyor",
      ilk11 "açıklandı" | "bilinmiyor (…)"},
  haber [{baslik,kaynak,zaman,hoca_degisikligi,takim}] | "bilinmiyor", alerts[], bilinmiyor[alan listesi],
  kaynaklar [{kaynak,url,ok,sn,onbellek,eski?,zaman,hata?}]}
```

Her istek `Http` sınıfından geçer: disk önbelleği (TTL), 12 sn zaman aşımı, ana makine başına en az 0,15 sn ara,
kaynak çökerse eski kopya (`eski: true`, kendi zamanıyla), robots.txt denetimi (Wikipedia). Bulunamayan alan uydurulmaz,
`"bilinmiyor"` yazılır ve `bilinmiyor[]` listesine eklenir. Toplam süre bütçesi 240 sn; aşılırsa kalan maçlar atlanır.

## Kaynaklar: ne alınabildi

| Kaynak | Alınan | Kapsam / tazelik | Şart, maliyet |
|---|---|---|---|
| ESPN scoreboard (`site.api.espn.com`, günde 1 istek) | biten maç skorları (son 120 gün) | ~220 lig, aynı gün | herkese açık, anahtarsız |
| ESPN maç özeti + takım uçları (mevcut `match_research`) | puan durumu, son 5, ilk 11 + düzenli oyuncular, sezon xG/xGA, takım haberleri | yalnız ESPN'in kapsadığı maçlar; **maç başı ~16 sn** (özet ×11) | aynı |
| Open Matchday CSV (GitHub, 75 yarışma) | skor, bazı ligde şut → xG vekili, puan durumu hesabı | 2026/27 sezonu, günlük | ticari olmayan kullanım + atıf |
| Nesine `GetUnliveMatches` | son ~14 günün sonuçları (havuza ek) | Nesine ligleri | mevcut kaynak |
| FPL bootstrap-static | Premier Lig sakat/cezalı/şüpheli, oynama şansı, önem | yalnız PL, saatlik | herkese açık |
| API-Football `injuries?date=` | günlük sakat listesi (mevki/dakika yok → önem UNKNOWN) | büyük 12 lig, bugün ±1 | günde 1 istek (kota); varsayılan KAPALI (`QF_WEB_AF=1`) |
| Wikipedia sezon sayfaları (`/wiki/` HTML, robots.txt izinli) | puan durumu, "Managerial changes" (hoca değişikliği, son 90 gün) | ~37 haritalı lig (`WIKI_TITLES`) | CC BY-SA, atıf; `/w/` ve `/api/` kullanılmaz |

Kullanılmayan / erişilemeyen: **Google Haberler RSS** (robots.txt `Disallow: /`, akış şartı yalnız kişisel okuyucu),
**GDELT DOC API** (denemede 429 + boş yanıt + ~18 sn), **Transfermarkt** (WAF), **Sofascore / FBref / WhoScored / Understat /
FootyStats / Flashscore** (bot koruması, bakım sayfası, robots veya ücretli), **kulüp siteleri** (tek tip biçim yok; güvenilir
ayrıştırma mümkün değil, `bilinmiyor` bırakılır), **TheSportsDB** (ücretsiz anahtar günde birkaç maç).

## Kapsam (2026-11-22 aday maçları, 300 maç = 600 takım tarafı, ağ çağrısı sonrası)

son maçlar %52 · puan durumu %31 (ESPN 74, Open Matchday'den hesap 114) · gerçek xG %13 (yalnız ESPN kapsamı) ·
hoca değişikliği kaydı (Wikipedia) %11 + 53 "son 90 günde yok" · sakat/cezalı %1 (yalnız FPL; API-Football kapalı) ·
açıklanmış ilk 11: ESPN'in kapsadığı maçlarda, maçtan ~1 sa önce. Geri kalanı `bilinmiyor`. Kapsam küçük liglerde
(İspanya 3. Federasyon, İtalya Serie C grupları, Asya alt ligleri) düşüktür; bu ligler için ücretsiz ve izinli kaynak bulunamadı.

## Süre

Havuz hazırlığı (günde bir): ESPN 120 gün soğuk ~20 sn (6 paralel), sonraki çalıştırmalarda yalnız yeni gün (~1 sn) +
Open Matchday 75 CSV ~12 sn (6 saatlik önbellek). Önbellek sıcakken maç başı **0,0–0,3 sn** (bellek içi eşleme + önbellekli
Wikipedia). Soğuk Wikipedia sayfası 0,1–0,3 sn, lig başına bir kez. ESPN araştırması (mevcut) maç başı ~16 sn, 8 iş parçacığı.
