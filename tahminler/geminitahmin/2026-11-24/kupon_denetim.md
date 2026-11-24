# 2026-11-24 Gemini Tahmin ve Kupon Denetim Raporu (v5)

- **Tarih:** 2026-11-24
- **Kapsam:** 40 aktif maç (`mac_tahminleri.csv`) ve 3 ayrık kupon (`kuponlar.csv`)
- **Denetim Sonucu:** `0 ihlal` (`exit code 0`) — Tüm bacaklar v5 kalkan ve kural denetiminden geçmiştir.

## 1. Ayrık Kupon Özeti (Disjoint Coupons)

### KUPON_1_ANA_BANKO (Mod: `banko` | Toplam Oran: `2.23x` | Birleşik P_kalibre: `0.4495` | Kelly: `50.0 TL`)
1. **Como 1907 - AEK Athens** (23:00, UEFA Şampiyonlar Ligi) — `MS 1` @ `1.26` (`P_kalibre=0.7580`, `r_draw=0.1530`, `gk1_out=False`, `top_scorer_out=False` - Douvikas 6 gol aktif)
2. **Wolverhampton - Derby County** (23:00, İngiltere Championship) — `MS 1` @ `1.32` (`P_kalibre=0.7240`, `r_draw=0.1790`, Kural G1: Derby `mu=0.72<0.75`)
3. **Orlando Pirates - Golden Arrows** (20:30, Güney Afrika PSL) — `2Y KG Yok` @ `1.34` (`P_kalibre=0.8190`, `EV=+9.75%`, `FAMILY_NAME_ALLOW`)

### KUPON_2_ALT_BANKO (Mod: `banko` | Toplam Oran: `2.17x` | Birleşik P_kalibre: `0.4200` | Kelly: `40.0 TL`)
1. **Slovan Bratislava - Real Betis** (23:00, UEFA Şampiyonlar Ligi) — `MS 2` @ `1.24` (`P_kalibre=0.7780`, `r_draw=0.1440`, Kural G1: Slovan `mu=0.68<0.75`)
2. **Glasgow Rangers - Aberdeen** (23:00, İskoçya Premiership) — `MS 1` @ `1.24` (`P_kalibre=0.7690`, `r_draw=0.1520`, Kural G1: Aberdeen `mu=0.68<0.75`)
3. **Palermo - FC Südtirol** (22:00, İtalya Serie B) — `MS 1` @ `1.41` (`P_kalibre=0.7020`, `r_draw=0.1980`, Palermo evinde 5/5 galibiyet)

### KUPON_3_DEGER_RISK (Mod: `risk` | Toplam Oran: `3.31x` | Birleşik P_kalibre: `0.3377` | Kelly: `25.0 TL`)
1. **RB Leipzig - RC Lens** (23:00, UEFA Şampiyonlar Ligi) — `2,5 Üst` @ `1.44` (`P_kalibre=0.6840`, Kural G3: `tot_xG=3.53>=2.85`, `min_mu=1.15>=0.95`)
2. **Galatasaray - Aston Villa** (20:45, UEFA Şampiyonlar Ligi) — `KG Var` @ `1.48` (`P_kalibre=0.6820`, `EV=+0.94%`, Kural G10 Rehabilitated: `min_mu=1.48>=1.15`)
3. **Al-Nassr - Al-Sadd** (21:15, AFC Şampiyonlar Ligi Elite) — `Ev 1,5 Üst` @ `1.55` (`P_kalibre=0.7240`, `EV=+12.22%`, Kural G10 Rehabilitated: `mu_fav=2.28>=2.00`)

## 2. Reddedilen Tuzak Maçlar (6 Kategori)

1. **Arsenal - Borussia Dortmund (`Arsenal MS 1` Reddedildi):** Kaleci David Raya (`home_gk1_out=True`), Saka ve Zubimendi eksikleri nedeniyle v5 Kaleci/Golcü Kalkanı devreye alındı; `3,5 Alt` (`%67.0`) koruma tercihine geçildi.
2. **Real Madrid - PSV Eindhoven (`Real Madrid MS 1` Reddedildi):** MS 1 oranı `1.18 < MIN_LEG_ODDS (1.20)` eşiğinin altında kaldığı için Banko havuzundan çıkarıldı; `Ev 2,5 Üst` (`1.52`) olarak değer havuzuna alındı.
3. **Hibernian - Dundee FC (`Hibernian MS 1` Reddedildi):** `1.63` favori oranına karşın Hibernian'ın evindeki son 10 maçlık çöküşü (`0G 1B 9M`) nedeniyle Tuzak Filtresi ile MS 1 elendi; `3,5 Alt` (`%71.0`) kalkanı uygulandı.
4. **Virtus Entella - Hellas Verona & Charlton Athletic - Lincoln City (`MS` Reddedildi):** Beraberlik riski (`r_draw >= %27`; Entella `%34.7`, Charlton `%34.2`) ve düşük gol beklentisi (Kural G2 & G9) nedeniyle düz taraf bahisleri elenerek `2,5 Alt` tercihine yönlendirildi.
5. **Coquimbo Unido - Unión La Calera (`Coquimbo MS 1` Reddedildi):** Şili Kupası eleme maçında Kural G8 Kupa Kalkanı gereği `-0.35 xG` baskısı uygulandı; kupa `MS 1` ve `2,5 Üst` yasaklanarak `3,5 Alt` (`%81.3`) seçildi.
6. **EFL Trophy U21 Maçları:** Yüksek rotasyon ve öngörülemezlik nedeniyle aktif 40 maçlık tahmin ve kupon havuzu dışında bırakıldı.
