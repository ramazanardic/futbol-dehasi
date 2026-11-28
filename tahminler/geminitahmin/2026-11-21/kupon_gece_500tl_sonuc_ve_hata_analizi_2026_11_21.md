# QuantFoot v8.0 -> v8.1 — 21 Kasım 2026 Gece Seansı 500 TL Master Kupon Kesin Sonuçları ve Kök-Hata Raporu

- **Kupon Kodu:** `kupon_gece_500tl_v80`
- **Ana Kupon Durumu:** **4 / 4 DOĞRU (%100 İsabet) — KAZANDI**
- **Opsiyonel 5. Ayak Dahil Durum:** **5 / 5 DOĞRU (%100 İsabet) — TAM İSABET**
- **Ana Kupon Toplam Oran & Kazanç:** `2.62x` | Misli: `500.00 TL` | **Net Ödeme: `1,310.00 TL` (+810.00 TL Net Kâr)**

## 1. Gece Seansı Maç Sonuçları Tablosu

| Kod | Saat | Lig | Karşılaşma | Seçim & Oran | 90 Dk Skoru (İY) | Durum | Maç İçi Kritik Olaylar |
| :--- | :---: | :---: | :--- | :--- | :---: | :---: | :--- |
| `MBS1-301` | 02:00 | ARG | **Vélez Sarsfield - Belgrano** | **`2.5 Alt @ 1.48`** | **`1-1`** (`0-1`) | **DOĞRU** | 11' R. Hernandes (0-1), 59' R. Martínez (1-1); Uzatma 2-2, Pen 3-1 |
| `MBS1-302` | 02:30 | CHI | **Palestino - Unión La Calera** | **`3.5 Alt @ 1.24`** | **`0-1`** (`0-0`) | **DOĞRU** | 26' D. Glaby Kırmızı Kart, 86' C. Moya Kırmızı Kart, 90+1' M. Campos (0-1) |
| `MBS1-303` | 04:00 | MEX | **Puebla - Atlético San Luis** | **`1.5 Üst @ 1.22`** | **`1-1`** (`1-0`) | **DOĞRU** | 4' M. Tomás (1-0), 48' F. Mora (1-1) — 48. dakikada erken kapandı |
| `MBS1-304` | 06:00 | MEX | **FC Juárez - Atlas** | **`ÇŞ X-2 @ 1.24`** | **`3-3`** (`2-1`) | **DOĞRU** | 19' V. Ríos, 23' Estupiñán, 45+4' Sepúlveda, Montiel, 80' Dupuy, 88' Purata |
| `MBS1-305` | 06:10 | MEX | **Tijuana - Atlante** *(Ops. 5. Ayak)* | **`3.5 Alt @ 1.32`** | **`1-0`** (`0-0`) | **DOĞRU** | 77' Gilberto Mora (Penaltı) |

## 2. Gece Seansı ve 20 Kasım Bülteni Kök-Hata Teşhisi (Yasaksız Yapısal Evrim v8.1/v8.2)

1. **Hata 1 (Asimetrik Motivasyon / Elen종 Ev Sahibi Açık Oyun Rejimi - `FC Juárez 3-3 Atlas`):** Elenmiş ev sahibi Juárez'in taktik disiplini bırakıp tamamen açık oynayacağı gözden kaçırıldı. `ÇŞ X-2` 88'de Purata'nın golüyle kurtulurken, maç 45+4'te `2-1` (3 gol) olmuştu. **v8.1 Çözümü:** Elenmiş ev sahibi + Play-In iddiasındaki deplasman eşleşmelerinde açık oyun çarpanı ($\times 1.24$) ve **Yutucu Engel (Absorbing-Barrier) Erken Kapanma Ödülü** eklendi; model seçimini doğrudan **`1.5 Üst @ 1.22`** (%82.5) olarak güncelledi.
2. **Hata 2 (Erken Kırmızı Kart Kuyruk Şoku - `Palestino 0-1 Unión La Calera`):** 26'da VAR ile gelen kırmızı kart ve 43 şuta rağmen `3.5 Alt` tuttu; ancak taraf bahsi (`1-X`) 90+1'de çöktü. **v8.1 Çözümü:** 3-Durumlu Kırmızı Kart Karışım Tensörü ($S_0=0.82, S_{\text{EvRC}}=0.095, S_{\text{DepRC}}=0.085$) ve Tam Kırmızı Kart CVaR Düşüş Cezası ($\Delta_{\text{RC}}$) eklendi.
3. **Hata 3 (Tek Maçlık Eleme 90 Dk Beraberlik Çekimi - `Vélez 1-1 Belgrano`, `Porto 1-1 Paredes`):** Tek maçlık kupa/play-off maçlarında 70. dakikadan sonra takımların riski kesip uzatma/penaltıya razı olması modellendi ($\rho_{\text{DC}} = -0.19$).
4. **Hata 4 (5-4-1 Derin Blok Sıkıştırması - `Bayern 1-1 Köln`, `Ath Bilbao 0-1 Espanyol`, `Verona 0-2 Cesena`):** Ağır favoriye karşı 5-4-1 derin blok kapanan deplasmanlarda favorinin $\lambda_{\text{ev}}$ beklentisi doğrusal kırpıldı ($\times 0.72$).
5. **Hata 5 (75'–90+5' Tek Farklı `2-1 / 1-2` Skor-Durumu Markov Kaos Tehlikesi - `Andorra 1-3 Leganes`, `Troyes 3-1 Le Havre`, `Guingamp 1-3 Rodez`):** 75. dakikaya `2-1` veya `1-2` girilen maçlarda gerideki takımın kaleci dahil yüklenmesiyle 4. gol olasılığı (`2-2` veya `3-1/1-3`) analitik Markov geçişiyle eklendi ($\gamma_{\text{chaos}} = 0.24$).
