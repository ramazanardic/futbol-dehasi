# QuantFoot v8.0 (`QUANTFOOT_AI=geminitahmin`) — 20 Kasım 2026 Cuma Maç Sonuçları, Kupon Karnesi ve Öz-Öğrenme (`auto_learn`) Raporu

## 1. 103 Maçlık Genel Tahmin Karnesi Özeti (`00:28 TSİ` İtibarıyla)
- **Toplam Tahmin Üretilen Maç:** `103`
- **Kesinleşen (90 Dakikası Biten / Matematiksel Olarak Kilitlenen) Maç:** `94`
  - **Kesin Doğru (Tutan):** **`51` Maç (`%54.26` İsabet)**
  - **Kesin Yanlış (Yatan):** **`43` Maç**
- **Son Dakikaları Oynanan Canlı Maç (`22:45–23:45` Seansı):** `9` (`5` Canlı Tutuyor / Önde, `4` Canlı Geride)
- **Canlı Skorlar Dahil Genel Tablo:** **`56 Doğru / 47 Yanlış (%54.37 İsabet)`**

| Pazar Ailesi | Kesinleşen Maç | Kesin Doğru | Kesin Yanlış | Kesin İsabet % | Canlı Tutuyor | Canlı Geride | Canlı Dahil Toplam (`103` Maç) |
|---|---|---|---|---|---|---|---|
| **Alt / Üst (`1.5 / 2.5 / 3.5`)** | `27` | **`17`** | `10` | **`%63.0`** | `3` | `1` | **`20 Doğru / 11 Yanlış (%64.5)`** |
| **Çifte Şans (`1X / X2 / 12`)** | `30` | **`19`** | `11` | **`%63.3`** | `1` | `1` | **`20 Doğru / 12 Yanlış (%62.5)`** |
| **Karşılıklı Gol (`KG Var / Yok`)** | `23` | **`11`** | `12` | **`%47.8`** | `0` | `1` | **`11 Doğru / 13 Yanlış (%45.8)`** |
| **Maç Sonucu (`MS 1 / MS 2`)** | `14` | **`4`** | `10` | **`%28.6`** | `1` | `1` | **`5 Doğru / 11 Yanlış (%31.3)`** |

## 2. Empirical-Bayes (`auto_learn`) Ertesi Gün Kalibrasyon Güncellemeleri
1. **Pazar Ağırlık Güncellemesi:** `Çifte Şans (%63.3)` ve `Alt/Üst (%63.0)` pazarlarına kupon motorunda `+0.06` Empirical-Bayes kalite bonusu tanımlanırken, düşük oranlı (`1.25–1.55`) düz `MS 1` seçimlerine `-0.05` daraltma uygulandı.
2. **Hollanda Eerste Divisie `3.5 Üst` Kalkanı:** Nesine'de `2.5 Üst < 1.15` olduğu için `3.5 Üst` seçimine zorlanan maçlar (`Heracles - Jong PSV 2-1`, `Volendam - Jong Ajax 1-2`) `5x` banko kuponlardan çıkarılıp yalnızca `10x+` çarpanlı kuponlarla sınırlandırıldı.
3. **Kuponlar Arası Maç Tekrar Sınırı (`max_coupon_exposure = 2`):** Aynı maçın en fazla 2 kuponda yer alması kuralı sabitlendi.
