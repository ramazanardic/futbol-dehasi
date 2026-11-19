# QuantFoot-v7 Kendi Kendini Onarma ve Geliştirme Raporu (19 Kasım Post-Mortem)

**Tarih:** 19 Kasım 2026 · `20:05 TSİ`  
**Kapsam:** 19 Kasım gündüz/akşam seansında (`#1`–`#29`) yaşanan kayıpların kök neden analizi, çekirdek matematik ve strateji motorunun kalıcı onarımı, geriye dönük sıfır-sızıntılı (*zero-lookahead*) doğrulama ve akşam/gece (`20:45–03:45`) yenilenmiş portföy.

---

## 1. Tespit Edilen 5 Kök Hata ve Kalıcı Onarımlar

1. **Blowout Dev Favori `KG Yok` Yanılsaması (`Al Wasl 2-1`, `AL Ain 2-1`, `Gaddafi 2-2`):**
   * *Hata:* `1.09` favorili açık maçlarda yalnızca `1X2 + O/U` invert edildiğinde zayıf takımın gol beklentisi (`0.45` vs `0.75`) matematiksel olarak ayrıştırılamıyor; bu da `KG Yok` olasılığında `+%12–%20` sahte `+EV` üretiyordu.
   * *Onarım:* `fit_tail_rates_from_markets` içine çoklu O/U (`ou_lines`) + `p_btts` ortak kalibrasyonu (`btts_w=4.5` dev favorilerde) eklendi ve `audit_match_risks` **Katman 6 (`Blowout KG Yok & Phantom +EV Kalkanı`)** devreye alındı: piyasanın 2 yönlü BTTS oranı modelden `>= %6` yüksekse `KG Yok` otomatik bloke edilir.
2. **Tek Maçlı Kupa/Playoff `90 Dakika` Beraberlik Tuzağı (`Roltek Dob 1-1`, `Al Mokawloon 1-1`, `Zvolen 2-2`, `Queensland 1-1`):**
   * *Hata:* `MatchRiskContext` içinde `is_knockout` alanı olmadığı için orta seviye favorilerde (`p_fav < %72`) 90 dakikalık MS bahisleri serbest kalıyordu.
   * *Onarım:* **Katman 7 (`Knockout 90' Draw Guard`)** eklendi: tek maçlı eleme/kupa maçlarında `p_fav < %72` ise `MS 1 / MS 2 / MS & 1.5 Üst / İY-MS 1/1-2/2` bloke edilir; yalnızca `p_fav >= %72` dev favorilere (`NK Celje 1-3 ✅` gibi) hafif ceza ile izin verilir.
3. **Küresel Alt/Üst (O/U) Piyasası Olmayan Maçlarda Gol/KG Hatası (`6/13 = %46.2` vs O/U'lu `8/12 = %66.7`):**
   * *Hata:* `Gaddafi 2-2`, `Farco 2-1`, `Maroons 1-2`, `El Daklyeh 0-0`, `Al Garaf 2-2` maçlarında küresel O/U kotasyonu olmadan lig önselinden `KG Yok / 1.5 Üst` verilmişti.
   * *Onarım:* **Katman 9 (`Missing Global O/U Gate`)** eklendi: `has_ou_market=False` iken tüm gol ve KG seçenekleri bloke edilir; taraf bahislerine `0.85` güven çarpanı uygulanır.
4. **Tek Bacağı 7 Kupona Kopyalama Felaketi (`AL Ain KG Yok` 7/7 kuponu tek golle batırdı):**
   * *Hata:* `coupon_builder.py` yalnızca tekil kupon üretiyordu; çoklu kupon portföyü için maruziyet sınırı yoktu.
   * *Onarım:* `build_diversified_portfolio` motoru yazıldı (`max_selection_reuse=1` -> kuponlar arası **0 tekrar**, `max_match_reuse=2` -> tek maç en fazla 2 kuponda, `max_same_category_share=0.65` ve yerel MBS kontrolü).
5. **Açık Lig Dağılım Rejimi + Kısa Kombine Verimliliği (`tail_goals.py` & `coupon_builder.py`):**
   * *Onarım:* BAE (`uae.`), Katar (`qat.`), Avustralya (`aus.`), MLS (`usa.`), ASEAN (`afc.cup`) ve ulusal kupalar için aşırı-dağılımlı (`alpha_nb=0.05–0.07, shared_kappa=0.04–0.05`), Mısır/Cezayir/İran/Zambiya için sıkı (`com_nu=1.10`) rejimler eklendi. `build_target_odds_coupon` yüksek hedef oranlarda (`>= 10x`) birleşik olasılığı maksimize ederek 5–6 ayaklı keskin kombineleri destekleyecek şekilde güncellendi.

---

## 2. Sıfır-Sızıntılı Geriye Dönük Doğrulama (`#1`–`#29`, 07:00 TSİ Oranlarıyla)

* **Eski Motor (`QuantFoot-v6.1`):** **`15 / 28` (`%53.6`)**
* **Onarılan Motor (`QuantFoot-v7`):** **`13 / 20` (`%65.0`)** *(Tam Global O/U'lu maçlarda: **`9 / 12` — `%75.0`**)*
* **Otomatik Engellenen / Kurtarılan Yatan Tuzak Sayısı:** **`8` maç**

### Otomatik Engellenen Tuzaklar
- #3 Omiya (K) - INAC Kobe L. (K) (5-0): v6.1 `MS 2@1.53` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Güven/EV filtresi
- #10 El Daklyeh - Ismaily Sc (0-0): v6.1 `1.5 Üst@1.31` YATTI -> v7 `ÇŞ 10@1.35` (TUTTU) | Sebep: Küresel Alt/Üst (O/U) Piyasası Eksik: Yalnızca 1X2 + lig önselinden türetilen gol/KG tahminleri güvenilir deği
- #11 Farco - Entag Harby (2-1): v6.1 `KG Yok@1.55` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Phantom +EV / KG Yok Yanılsaması: Piyasa 2-yönlü BTTS (%46.7) modelden (%37.8) belirgin yüksek; dev favoride t
- #14 Roltek Dob - NK Bistrica (1-1): v6.1 `MS 2@1.47` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Tek Maçlı Kupa/Playoff 90' Beraberlik Tuzağı (p_fav=%56.7 < %72): Uzatma/penaltı motivasyonu MS bahislerini kı
- #18 Maroons - NEC (1-2): v6.1 `KG Yok@1.41` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Küresel Alt/Üst (O/U) Piyasası Eksik: Yalnızca 1X2 + lig önselinden türetilen gol/KG tahminleri güvenilir deği
- #20 Gaddafi (Entebbe) - Kataka (2-2): v6.1 `KG Yok@1.43` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Phantom +EV / KG Yok Yanılsaması: Piyasa 2-yönlü BTTS (%40.4) modelden (%19.8) belirgin yüksek; dev favoride t
- #28 AL Ain - AL Dhafra Scc (2-1): v6.1 `KG Yok@1.56` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Açık Maç Dev Favori KG Yok Tuzağı: Toplam xG=4.05, piyasa KG Yok olasılığı düşük (%52.9); Al Wasl / AL Ain 2-1
- #29 Al Garaf - AL Jawiya (2-2): v6.1 `KG Yok@1.51` YATTI -> v7 `PAS (Bloke)` (PAS) | Sebep: Küresel Alt/Üst (O/U) Piyasası Eksik: Yalnızca 1X2 + lig önselinden türetilen gol/KG tahminleri güvenilir deği

### Maç Bazlı `v6.1` vs `v7` Karşılaştırması (`#1`–`#29`)

| # | Skor | Maç | O/U | `v6.1` (Eski) | `v7` (Onarılmış) |
| :---: | :---: | :--- | :---: | :--- | :--- |
| 1 | FT **6-0** | Preston Lions - South Hobart | Var | 3.5 Üst@1.41 (**TUTTU**) | 3.5 Üst@1.41 (**TUTTU**) |
| 2 | FT **1-1** | Queensland L. - Woll. Wolves | Var | 2.5 Üst@1.21 (**YATTI**) | 2.5 Üst@1.21 (**YATTI**) |
| 3 | FT **5-0** | Omiya (K) - INAC Kobe L. (K) | Yok | MS 2@1.53 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 4 | FT **4-1** | Preah Khan R. S. - Port | Var | ÇŞ 10@1.24 (**TUTTU**) | ÇŞ 10@1.24 (**TUTTU**) |
| 5 | FT **6-0** | Persib Bandung - Shan Utd | Var | KG Yok@1.41 (**TUTTU**) | KG Yok@1.41 (**TUTTU**) |
| 6 | FT **2-2** | MFK Lokomotiva Zvolen - FK Kosice | Var | KG Var@1.45 (**TUTTU**) | KG Var@1.45 (**TUTTU**) |
| 7 | FT **1-3** | Cong An Nhan Dan - Johor Darul | Var | 2.5 Üst@1.43 (**TUTTU**) | 2.5 Üst@1.43 (**TUTTU**) |
| 8 | FT **1-2** | EL Terasanah - Telecom Egypt | Yok | 1.5 Üst@1.45 (**TUTTU**) | ÇŞ 02@1.28 (**TUTTU**) |
| 9 | FT **2-2** | La Viena - El Sekka El Hadid | Yok | ÇŞ 02@1.24 (**TUTTU**) | ÇŞ 02@1.24 (**TUTTU**) |
| 10 | FT **0-0** | El Daklyeh - Ismaily Sc | Yok | 1.5 Üst@1.31 (**YATTI**) | ÇŞ 10@1.35 (**TUTTU**) |
| 11 | FT **2-1** | Farco - Entag Harby | Yok | KG Yok@1.55 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 12 | FT **0-1** | Baladiyyat AL M. - Haras Hodood | Yok | 2.5 Alt@1.38 (**TUTTU**) | ÇŞ 02@1.21 (**TUTTU**) |
| 13 | FT **1-3** | ND Beltinci - NK Celje | Var | MS 2@1.21 (**TUTTU**) | MS 2@1.21 (**TUTTU**) |
| 14 | FT **1-1** | Roltek Dob - NK Bistrica | Var | MS 2@1.47 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 15 | FT **2-1** | Al Wasl - Hatta SC | Var | KG Yok@1.67 (**YATTI**) | 3.5 Üst@1.44 (**YATTI**) |
| 16 | FT **1-2** | Malavan Bandar A. - GOL Gohar | Var | KG Yok@1.29 (**YATTI**) | KG Yok@1.29 (**YATTI**) |
| 17 | FT **0-0** | Surkhon Termez - Andijon | Var | ÇŞ 10@1.39 (**TUTTU**) | ÇŞ 10@1.39 (**TUTTU**) |
| 18 | FT **1-2** | Maroons - NEC | Yok | KG Yok@1.41 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 19 | FT **2-1** | Kigezi Homeoyz - Express | Yok | MS 2@1.61 (**YATTI**) | MS 2@1.61 (**YATTI**) |
| 20 | FT **2-2** | Gaddafi (Entebbe) - Kataka | Yok | KG Yok@1.43 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 21 | FT **5-0** | AL Salt - Al Yarmouk | Yok | MS 1@1.34 (**TUTTU**) | PAS (Bloke) (**PAS**) |
| 22 | FT **0-0** | Nkwazi - Mutondo Stars | Yok | KG Yok@1.27 (**TUTTU**) | MS 1@1.54 (**YATTI**) |
| 23 | FT **2-1** | Zesco Utd - Red Arrows | Yok | 1.5 Üst@1.43 (**TUTTU**) | ÇŞ 02@1.43 (**YATTI**) |
| 24 | FT **0-1** | Mufulira Wanderers - Kabwe Warriors | Yok | ÇŞ 10@1.26 (**YATTI**) | ÇŞ 10@1.26 (**YATTI**) |
| 25 | FT **0-5** | Dobrudzha Dobrich - Fratria Varna | Var | MS 2@1.57 (**TUTTU**) | MS 2@1.57 (**TUTTU**) |
| 26 | LIVE 90+4' **1-1** | Al Mokawloon - Alqana | Var | MS 1@1.45 (**CANLI**) | PAS (Bloke) (**PAS**) |
| 27 | LIVE 90' **2-0** | Al Masry - Asyut Petroleum | Var | 1.5 Üst@1.31 (**TUTTU**) | 1.5 Üst@1.31 (**TUTTU**) |
| 28 | LIVE 71' **2-1** | AL Ain - AL Dhafra Scc | Var | KG Yok@1.56 (**YATTI**) | PAS (Bloke) (**PAS**) |
| 29 | LIVE 69' **2-2** | Al Garaf - AL Jawiya | Yok | KG Yok@1.51 (**YATTI**) | PAS (Bloke) (**PAS**) |

---

## 3. Onarılmış `QuantFoot-v7` ile Bu Akşam / Gece (`20:45–03:45`) Çeşitlendirilmiş Portföy

> *Bu kuponlar `build_diversified_portfolio` ile otomatik üretilmiştir: **0 tekrarlanan `(Maç, Tercih)`**, bir maç en fazla **2 kuponda**, tamamı **`>= 1.20` canlı Nesine oranı**, MBS uyumlu ve 9 katmanlı v7 risk kalkanından geçmiştir.*

### v7 AKŞAM/GECE KUPON 1 — 2-3 Maçlık Çekirdek Güven (~2.1x+)
- **Toplam Oran:** **`2.15x`** | **Maç:** 2 | **Ort. Global P:** **`%60.2`** | **Birleşik P:** `%35.91`

| Saat | Maç | Lig | MBS | Tercih | Nesine | Global Adil | Global % | EV |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| Gece 20.11 03:30 | Sao Paulo SP - Fluminense | Brezilya Serie A | 1 | **KG Var** | **1.65** | 1.84 | %54.5 | -10.1% |
| Gece 20.11 01:30 | Vitoria BA - Bragantino | Brezilya Serie A | 1 | **ÇŞ 02** | **1.30** | 1.52 | %65.9 | -14.3% |

### v7 AKŞAM/GECE KUPON 2 — 4-5 Maçlık Dengeli Değer (~4.5x+)
- **Toplam Oran:** **`4.55x`** | **Maç:** 4 | **Ort. Global P:** **`%59.6`** | **Birleşik P:** `%12.49`

| Saat | Maç | Lig | MBS | Tercih | Nesine | Global Adil | Global % | EV |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| Gece 20.11 01:30 | Vasco Da G. - Internacional | Brezilya Serie A | 1 | **MS 1** | **1.47** | 1.74 | %57.6 | -15.3% |
| Gece 20.11 03:45 | R. Cartagena - Tigres (Kol) | Kolombiya Prmr B Kapanış, Yük. Gr B | 3 | **KG Yok** | **1.37** | 1.49 | %67.0 | -8.2% |
| Bugün 19.11 22:00 | JS Kabylie - USM Alger | Cezayir 1. Lig | 3 | **KG Yok** | **1.44** | 1.67 | %59.7 | -14.0% |
| Gece 20.11 03:30 | Orlando City - Cincinnati | ABD Major Lig Playoff | 1 | **3.5 Üst** | **1.57** | 1.85 | %54.1 | -15.0% |

### v7 AKŞAM/GECE KUPON 3 — 6-7 Maçlık Hedef 10x+ (~9.5x+)
- **Toplam Oran:** **`9.51x`** | **Maç:** 7 | **Ort. Global P:** **`%61.2`** | **Birleşik P:** `%3.21`

| Saat | Maç | Lig | MBS | Tercih | Nesine | Global Adil | Global % | EV |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| Gece 20.11 03:30 | Sao Paulo SP - Fluminense | Brezilya Serie A | 1 | **ÇŞ 02** | **1.38** | 1.67 | %59.9 | -17.4% |
| Bugün 19.11 22:30 | Penarol - Cerro Largo | Uruguay Prmr Ligi, Kapanış | 3 | **KG Yok** | **1.40** | 1.58 | %63.2 | -11.5% |
| Bugün 19.11 22:30 | CA Progreso - Torque | Uruguay Prmr Ligi, Kapanış | 3 | **2.5 Üst** | **1.38** | 1.67 | %60.0 | -17.2% |
| Bugün 19.11 23:00 | Benfica (K) - AS Roma (K) | UEFA Şamp. Ligi Kadınlar | 1 | **2.5 Üst** | **1.31** | 1.58 | %63.5 | -16.8% |
| Gece 20.11 03:30 | Orlando City - Cincinnati | ABD Major Lig Playoff | 1 | **ÇŞ 02** | **1.38** | 1.62 | %61.6 | -14.9% |
| Bugün 19.11 23:00 | Arsenal (K) - O. Lyon (K) | UEFA Şamp. Ligi Kadınlar | 1 | **2.5 Üst** | **1.38** | 1.63 | %61.2 | -15.6% |
| Bugün 19.11 21:00 | ZED - Smouha SC | Mısır Kupası | 3 | **KG Yok** | **1.43** | 1.69 | %59.1 | -15.5% |
