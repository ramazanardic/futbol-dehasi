# QuantFoot — Tüm Bahis Pazarları (20 aile) ve Bet Builder

Tek komutla bir maçın bütün pazarlarını fiyatlamak:

```bash
quantfoot markets --mu-home 1.8 --mu-away 1.0 --league eng.1 --division E0 \
  --corners 6.1 4.0 --yellows 1.7 1.9 \
  --player "Haaland;Ev;0.42;0.08;85;3.8;1.9;0.1" \
  --builder "MS 1" "2.5 Üst" "Haaland: Gol Atar" "Korner 9.5 Üst" --builder-odds 3.6
```

- `--mu-home / --mu-away`: beklenen goller (ör. `fit_tail_rates_from_markets` ile piyasadan veya modelden).
- `--league`: gol rejimi için yarışma kodu (COM-Poisson / Gamma-Poisson, ilk yarı payı).
- `--division`: korner/kart lig tabanı (E0, T1, SP1 ...; bilinmeyen lig → genel ortalama).
- `--player`: `Ad;Ev|Dep;gol_payı;asist_payı;dakika;şut90;isabetli90;sarı90` (tekrarlanabilir).
- `--family "Korner"`: yalnızca adı eşleşen aileleri yazdırır; `--json dosya.json` hepsini dışa aktarır.

Python'dan: `quantfoot.markets.build_market_book(...)` ve `quantfoot.markets.price_bet_builder(...)`.

---

## Mimari: tek tutarlı ortak dağılım

Bütün gol pazarları tek bir 4 boyutlu dağılımdan türetilir:
`J[h1, a1, h2, a2]` = ev/deplasman golleri, ilk ve ikinci yarı ayrı.

1. İlk yarı skor matrisi (COM-Poisson + FGM bağımlılığı) ve ilk yarı skoruna göre ikinci
   yarı matrisleri (oyun durumu çarpanları) çarpılarak J kurulur.
2. J, **iteratif oransal uydurma (IPF)** ile hem maç sonu skor matrisine (15×15, kuyruk-gol
   rejimi) hem ilk yarı skor matrisine tam olarak hizalanır (`rake_joint_to_margins`).
3. Her seçim J üzerinde bir olaydır; kombineler olayların kesişimidir. Böylece bütün
   pazarlar birbiriyle tutarlıdır: ör. İY/MS satırları İY sonucuna, sütunları MS'ye eşit;
   İY + 2Y gol beklentisi = MS gol beklentisi; "Ev gol yemeden kazanır" = "MS 1 & Dep 0.5 Alt".

Bu, kombine fiyatlarının tek bir tutarlı dağılımın marjinalleri olması ilkesidir
(Rana ve ark. 2026, *ParlayMarket*, arXiv:2603.22596).

---

## Pazar ailesi → model → dayanak

| # | Pazar | Kaynak modül | Model / yöntem | Kanıt / not |
|---|---|---|---|---|
| 1 | Maç Sonucu | `goal_markets` | J üzerinde olay | — |
| 2 | Çifte Şans | `goal_markets` | J üzerinde olay | — |
| 3 | Beraberlikte İade | `goal_markets.draw_no_bet` | Asya 0 ile özdeş; iade olasılığı = P(beraberlik) | Test: adil oran = (1−P(X))/P(1) |
| 4 | Alt/Üst 0.5–5.5 | `goal_markets` | J; ayrıca Asya alt/üst 1.50–4.50 (çeyrek çizgiler) | Kulüplerde COM-Poisson ν=1.10, milli/genç maçlarda Gamma-Poisson (bkz. `tail_goals.py`; Zhang ve ark. 2026, arXiv:2607.18009; Florez ve ark. 2024, arXiv:2409.17129) |
| 5 | Toplam Gol Aralığı | `goal_markets` | 0-1, 2-3, 4-5, 6+ (ayrıca 2-4, 3-5) | — |
| 6 | Tek/Çift | `goal_markets` | MS ve İY | — |
| 7 | Karşılıklı Gol | `goal_markets` | MS, İY, 2Y, iki yarıda KG | Devre içi FGM bağımlılığı `halves_btts` ile aynı parametrizasyon |
| 8 | Avrupa Handikabı | `goal_markets` | `Hnd(-1) 1/0/2` … ±3 | Test: Hnd(−1) 1 = Asya −1.5 |
| 9 | Asya Handikabı | `goal_markets.asian_handicap` | Tam / yarım / çeyrek çizgi; kazan, yarım kazan, iade, yarım kayıp | Test: adil oranda EV = 0 |
| 10 | Doğru Skor | `goal_markets` | 0-0…6-6 + "Diğer" | Kuyruk 15×15 matristen |
| 11 | İlk Yarı | `goal_markets` | İY sonucu, İY Alt/Üst, İY skoru | İlk yarı gol payı ~%44 (184.276 maç, repo verisi) |
| 12 | İkinci Yarı | `goal_markets` | 2Y sonucu, 2Y Alt/Üst | Oyun durumu çarpanları: 1 gol geride +%10 (Maia ve ark. 2023, arXiv:2312.04338 ile uyumlu); 2 gol geride çarpan literatürle çelişiyor, bkz. `literature_review_2026_11.md` §7 |
| 13 | İY/MS | `goal_markets` | 9 sonuç | Satır/sütun marjinalleri tam tutarlı |
| 14 | Takım Golleri | `goal_markets` | Takım Alt/Üst, gol atar, gol yemez, gol yemeden kazanır, iki yarıda gol, her iki yarıyı kazanır | — |
| 15 | Gol Zamanı | `goal_timing` | Parçalı sabit yoğunluklu Poisson süreci (6 × 15 dk) | Aşağıya bakın |
| 16 | Golcü | `player_markets` | Takım golü başına binom/multinom inceltme; ilk/son golcü zaman modeliyle | Whitaker ve ark. 2017 (arXiv:1710.00001); oyuncu bitiricilik etkisi: Scholtes & Karakuş 2023 (arXiv:2311.13707) |
| 17 | Oyuncu Özel | `player_markets` | Asist (inceltme), şut / isabetli şut / pas (Negatif Binom) | Oyuncu verisi repoda yok → girdiler kullanıcıdan |
| 18 | Korner | `corners_cards` | Toplam ~ NB, ev payı ~ Beta-Binom; takım reytingleri | Aşağıya bakın |
| 19 | Kart | `corners_cards` | Sarılar çift değişkenli Poisson, kırmızılar Poisson; kart puanı 10/25 | Aşağıya bakın |
| 20 | Kombine / Bet Builder | `goal_markets`, `bet_builder` | Tüm bacakların tek dağılımda kesişimi | Aşağıya bakın |

---

## 15. Gol zamanı

- Her yarının "gol olma" tehlikesi `−log P(o yarıda gol yok)` olarak J'den alınır ve takımlara
  o yarıdaki beklenen gollerine göre bölünür. Böylece "İY gol yok" = İY 0.5 Alt tam tutar.
- Yarı içindeki dağılım `DEFAULT_BIN_SHARES = (12.5, 14.5, 17.0, 16.5, 18.0, 21.5)%`:
  gol yoğunluğu maç ilerledikçe artar ve her yarının ilk dakikaları en sakindir
  (Ayana ve ark. 2025, arXiv:2501.18606); son 15 dakika en yüksek paya sahiptir
  (Dünya Kupaları 1966–2018'de %22.7; Mićović ve ark. 2023, doi:10.3389/fpsyg.2023.954876).
  **Bu bir literatür önselidir**; repoda dakika bazlı gol verisi yok. ESPN `keyEvents`
  verisinden tahmin edilip `bin_shares` ile değiştirilmelidir.
- İlk / son golü atan takım: iki takımın yoğunluk profili aynıysa
  P(ev ilk golü atar | skor h-a) = h/(h+a); bu, Bet Builder'da "İlk Gol Ev & MS 1" gibi
  kombinelerin tutarlı fiyatlanmasını sağlar.
- Sınırlamalar: golden sonra aynı takımın tekrar atma eğilimi (Ayana ve ark. 2025) ve
  skora bağlı yoğunluk değişimi (Heuer & Rubner 2012) zaman modeline dahil değil.

## 18. Korner — veriyle kalibre (2018/19+, 56.743 maç, 22 lig)

| Ölçüm | Değer |
|---|---|
| Ev / deplasman korner ortalaması | 5.35 / 4.47 |
| Takım kornerinde Varyans/Ortalama | ~1.55 (aşırı dağılım) |
| Toplam kornerde Varyans/Ortalama | 1.18 |
| Ev–deplasman korner korelasyonu | **−0.24** |
| Korner ile gol korelasyonu | −0.01 |

Model: toplam T ~ Negatif Binom, ev kornerleri H | T ~ Beta-Binom(T, s, ρ); ρ moment
denklemlerinden çözülür. Lig ortalaması parametreleriyle model takım aşırı dağılımını
(1.52 / 1.58), korelasyonu (−0.237) ve toplam dağılımı (1.18) birlikte yakalıyor.
Kornerler kümeli geldiği için aşırı dağılımlı model gerekir (Yip ve ark. 2021, arXiv:2112.13001).

Takım reytingleri (`CornerCardRatings`): kazanılan / verilen korner oranlarının üstel
ağırlıklı ortalaması. **İleri-yürüyen test** (`scripts/evaluate_corner_card_models.py`,
test 2023-07+ 21.691 maç, maç kendi sonucu görülmeden önce tahmin edilir):

| Log-loss (düşük = iyi) | Lig ort. | α=0.01 | **α=0.02** | α=0.03 | α=0.06 | α=0.10 |
|---|---|---|---|---|---|---|
| Korner 8.5 Üst | 0.65611 | **0.65278** | 0.65363 | 0.65529 | 0.66242 | 0.67375 |
| Korner 9.5 Üst | 0.68916 | **0.68646** | 0.68780 | 0.68988 | 0.69830 | 0.71123 |
| Korner 10.5 Üst | 0.66843 | **0.66521** | 0.66622 | 0.66798 | 0.67570 | 0.68820 |
| Ev Korner 4.5 Üst | 0.68057 | 0.66021 | **0.65822** | 0.65861 | 0.66432 | 0.67566 |
| Dep Korner 4.5 Üst | 0.68342 | 0.66325 | 0.66026 | **0.65975** | 0.66299 | 0.67133 |
| En çok korner: Ev | 0.68968 | 0.66059 | 0.65581 | **0.65440** | 0.65679 | 0.66572 |
| Kart 3.5 Üst | 0.66086 | 0.65160 | **0.65060** | 0.65175 | 0.65873 | 0.66892 |
| Kart 4.5 Üst | 0.67064 | 0.66096 | **0.65990** | 0.66090 | 0.66750 | 0.67748 |
| Ev Kart 1.5 Üst | 0.66949 | 0.65884 | **0.65724** | 0.65768 | 0.66321 | 0.67319 |
| Kırmızı Kart Var | 0.44245 | 0.44143 | **0.44115** | 0.44108 | 0.44138 | 0.44189 |

Sonuç: reytingler bütün satırlarda lig ortalamasını yeniyor; kazanç **takım korneri, en çok
korner ve kart** pazarlarında büyük, **toplam kornerde** küçük. Varsayılan α=0.02 (genel en
iyi). Not: α aynı test döneminde seçildi, bu yüzden bu farklar hafif iyimserdir; yeni bir
dönemde yeniden doğrulanmalıdır.

İlk yarı korner payı (varsayılan 0.47) ve ilk korner verisi repoda yok → varsayım.

## 19. Kart — veriyle kalibre

| Ölçüm | Değer |
|---|---|
| Ev / deplasman sarı kart | 1.90 / 2.14 (deplasman daha fazla; Goumas 2014, doi:10.1080/17461391.2012.686062) |
| Takım sarısında Varyans/Ortalama | ~0.96 (Poisson'a yakın) |
| Ev–deplasman sarı korelasyonu | +0.21 (ortak hakem / maç sertliği bileşeni) |
| En az bir kırmızı kart | %17.5 |
| Kart ile gol / korner korelasyonu | −0.04 / −0.04 |

Model: sarılar çift değişkenli Poisson (ortak bileşen λ₃ = Kov(Y_ev, Y_dep), lig bazlı),
kırmızılar takım başına Poisson. Kart puanı = 10 × sarı + 25 × kırmızı (yaygın kural;
büroya göre değişebilir). Hakem verisi repoda yok; hakem etkisi literatürde güçlü
(McCarrick ve ark. 2020, doi:10.1186/s40359-020-0370-4; Gasparetto & Loktionov 2023,
doi:10.1371/journal.pone.0294507) → hakem bilgisi gelirse `yellow_factor_*` ile eklenmeli.

## 20. Kombine / Bet Builder

`price_bet_builder(["MS 1", "2.5 Üst", "Haaland: Gol Atar", "Korner 9.5 Üst"], joint, ...)`

- Gol bacakları J üzerinde tam kesişim.
- Golcü bacakları her durumda takımın gol sayısına koşullu, multinom dağılımla
  ("iki oyuncu da gol atar" dahil).
- Korner ve kart bacakları kendi ortak dağılımlarında tam kesişim; gollerden bağımsız
  kabul edilir (veride korelasyon ≈ 0).
- Çıktı: olasılık, adil oran, **bacakların bağımsız çarpımı** ve **korelasyon oranı**
  (ör. favori ev sahibi için "MS 1 & 2.5 Üst" ≈ 1.16 → büro bunu daha düşük oranla
  fiyatlar; "MS 2 & ev golcüsü 2+ gol" ≈ 0.10).
- Literatür uyarısı: kombineler bacak sayısıyla artan marjla fiyatlanır (Moshrefi 2026,
  arXiv:2607.14430) ve oyuncu kayıplarını büyütür (Borghesi ve ark. 2026). Verilen oran
  girilirse EV hesaplanır; EV negatifse kombine oynanmamalıdır.

---

## Bilinen sınırlamalar

1. Oyuncu pazarları (16–17) kullanıcının verdiği oyuncu girdilerine dayanır; repoda oyuncu
   verisi yok. Gol payı ve oranlar küçük örneklemlerde konumsal ortalamaya doğru büzülmelidir.
2. Gol zamanı profili literatür önselidir (dakika verisi yok).
3. İlk yarı korner payı, ilk korner ve hakem etkisi veriyle doğrulanmadı.
4. Gol beklentileri (`mu`) modelden geliyorsa, modelin piyasaya karşı bilgi katıp katmadığı
   ayrıca sınanmalıdır (bkz. `literature_review_2026_11.md` §0). Kadın futbolu gibi kalibre
   edilmemiş yarışmalarda bu pazarlar kullanılmamalıdır.
