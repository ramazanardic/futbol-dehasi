# data/arsiv — genişletilmiş maç arşivi (açık/izinli kaynaklar)

`data/matches.csv` (Elo/form özellikli, 2000–bugün) ve `data/international_results.csv` (milli maçlar, 1872–bugün) **olduğu gibi kalır**.
Bu klasör onlara **ek** bir arşivdir: aynı maç (±1 gün, normalize takım adı, aynı skor) o iki dosyada varsa buraya **alınmaz**
(`ozet.json → tekrar_ayiklanan.dis_tekrar`). Model eğitimi bu dosyaları henüz kullanmaz; yalnız veri/araştırma amaçlıdır.

| Dosya | İçerik |
|---|---|
| `maclar.csv.gz` | tekrarsız maç satırları: `tarih,sezon,yarisma,tur,ev,dep,hg,ag,iy_ev,iy_dep,durum,ham_skor,kaynak` |
| `yarismalar.csv` | yarışma kataloğu (tür, ilk/son sezon, maç ve takım sayısı) |
| `takimlar.csv.gz` | takım kataloğu (normalize anahtar, yarışma sayısı, ilk/son tarih, maç) |
| `oyuncular.csv.gz` | oyuncu×yarışma×sezon özeti: gol, penaltı golü, kendi kalesine, sarı/kırmızı, maç, ilk 11 |
| `oyuncu_kunye.csv.gz` | oyuncu künyesi (doğum, boy, mevki; openfootball/players) |
| `espn_ligler.csv` | ESPN lig kimliği → ad/slug (ESPN core API) |
| `ozet.json` | sayımlar (maç, yarışma, takım, yıl, kaynak/tür dağılımı) |

Kurallar
* `tur`: `lig`, `kupa`, `kita_kulup`, `milli`, `hazirlik` (kulüp hazırlık).
* `hg/ag` **90 dakika** skorudur. Uzatma/penaltıya giden maçta kaynak yalnız son skoru veriyorsa `hg/ag` boş, `ham_skor` dolu, `durum` = `AET`/`PEN`.
* `iy_*` yoksa boş. İY, final skorunu aşıyorsa (kaynak hatası) atılır.
* `tarih` boş olabilir: Wikipedia sonuç matrisleri ve bazı eski turnuva dosyaları tarih vermez (yalnız `sezon`). Bu satırlar tarihli satırlarla (sezon+takım+skor) tekrar kontrolünden geçer.
* Kadın ligleri/turnuvaları alınmadı (ESPN `women/.w./nwsl/ncaa` süzgeci). Sezon adı yıl taşımayan ESPN yarışmalarında `sezon` = maç yılı.
* Kaynak önceliği (tekrarda kazanan): football-data > openfootball > footballcsv > jfjelstul/worldcup > martj42 > Wikipedia > ESPN.

## Kaynaklar ve lisans
| Kaynak | Ne alındı | Lisans / şart |
|---|---|---|
| openfootball (github.com/openfootball/*) | Avrupa/dünya ligleri, kupalar, Şampiyonlar Ligi, Libertadores, Euro, Copa América, Dünya Kupası, oyuncu künyeleri | CC0 / kamu malı |
| footballcsv (github.com/footballcsv/*) | İngiltere, Almanya, İspanya, Avusturya, MLS, Şampiyonlar Kupası geçmişi | CC0 |
| martj42/international_results | milli maç sonuçları, gol atanlar (oyuncu toplamları) | CC0 |
| football-data.co.uk | 1993/94–1999/00 arşiv CSV'leri (mevcut repo 2000+ ile birleşir) | ücretsiz araştırma verisi, robots.txt izinli; yalnız sonuç/İY satırları (bahis oranı alınmadı) |
| ESPN herkese açık scoreboard (site.api.espn.com) | 2003-01 → bugün, ~220 lig/kupa/kıta/milli turnuva; yalnız sonuç satırı (tarih, takımlar, skor, durum) | herkese açık API, kimlik doğrulamasız; ham JSON saklanmadı, yalnız olgusal sonuç |
| jfjelstul/worldcup | Dünya Kupası maçları ve oyuncu (gol/kart/maç) toplamları | **CC BY-SA 4.0** — atıf: Joshua C. Fjelstul, Ph.D., “The Fjelstul World Cup Database”, © 2023; türev veri de aynı lisansla paylaşılır |
| Wikipedia sezon sayfaları (`/wiki/` HTML, robots izinli, ~3 istek/sn) | ~63 ligin sonuç matrisi ve gol krallığı (1995–2025) | **CC BY-SA 4.0** — atıf: Wikipedia katkıcıları; `kaynak=wikipedia` satırları aynı lisansla |

Not: CC BY-SA kaynaklar (jfjelstul, Wikipedia) yalnız `kaynak` sütunuyla işaretli satırlardadır; bu satırları yeniden dağıtırken atıf ve aynı lisans gerekir.

## Alınmayanlar
* **footballsquads / cache.footballsquads** — lisansı belirsiz: alınmadı. Takım kadro verisi eksik.
* Sofascore, FotMob, FBref/Opta, WhoScored, Understat, FootyStats, Flashscore, Transfermarkt — koruma, ücret ya da kullanım şartı nedeniyle girilmedi. Bu yüzden kulüp ligleri için **maç bazlı oyuncu istatistiği (şut, pas, dakika, xG)** yok.
* API-Football geçmiş verisi: ücretsiz plan (60/gün) arşiv için yetersiz, kullanılmadı.
* Oyuncu düzeyi yalnız: Dünya Kupası (maç/gol/kart), milli maç gol atanlar, Wikipedia gol krallığı (ilk 10), openfootball künyeleri.
* Vaastav FPL arşivi (lisans NOASSERTION) alınmadı.
* Wikipedia: 70 hedef ligin 67'sinden sonuç matrisi alındı; ABD (MLS), Avustralya (A-League), Fas (Botola) sayfalarında ayrıştırılabilir 'Home \ Away' matrisi yok (grup/oynatma formatı). Latin Amerika ligleri (Apertura/Clausura) ve Afrika ligleri yalnız kısmen (2–18 sezon). Matris yalnız skor verir (tarih, İY yok).
* Wikipedia matrisi satırları başka kaynaktaki aynı maçla takım adı farkı yüzünden çakışabilir; tarihsiz oldukları için en iyi çaba (sezon+takım+skor) ayıklaması yapılır, kalıntı yinelenme olasıdır.
* Maç tarihi/saati olmayan eski turnuvalar ve Wikipedia matrisleri `tarih` boş kalır.

## Yeniden kurma
Ham veri repoya girmez. Ham klasör düzeni `scripts/arsiv_kur.py` başlığında. Adımlar:
```
python scripts/arsiv_espn_ligler.py                       # espn_ligler.csv
python scripts/arsiv_espn_tara.py --bas 2003-01-01 --bit <bugün> --cikti <ham>/espn
python scripts/arsiv_wiki_tara.py --bas 1995 --bit 2025 --cikti <ham>/wiki
python scripts/arsiv_kur.py --ham <ham> --cikti data/arsiv
```
Tek dosya sınırı 50 MB; en büyük dosya `maclar.csv.gz` (~8–10 MB).

## Ek kaynaklar (28 Kas 2026, `scripts/arsiv_ek_kaynak.py`)
Yalnız ekleme (eski satırlar bayt bayt aynı); matches.csv'de olan maçlar `arsiv_kur` kuralıyla ayıklanır.
| Kaynak | Ne alındı | Lisans / şart |
|---|---|---|
| ESPN lig scoreboard (`scripts/espn_lig_tara.py`, `/soccer/<slug>/scoreboard`) | por.1, rus.1 2026/27 (yalnız skor) | herkese açık API; yalnız olgusal sonuç |
| OpenLigaDB (`api.openligadb.de/getmatchdata/bl3/<yıl>`) | 3. Liga 2023/24–2026/27, **yalnız tam skor** (İY'de 0:0 yer tutucuları olduğu için İY alınmadı) | ODbL — "Daten: OpenLigaDB" |
| Wikipedia (`/wiki/` HTML) | 2023/24–2026/27: 3. Liga, Avusturya 2. Lig, Çekya, İsviçre Challenge, Sırbistan, Slovakya, Slovenya, TFF 1. Lig (tarihsiz) | CC BY-SA 4.0 |
