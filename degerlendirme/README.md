# Ortak değerlendirme alanı

Her günün maçları ertesi gün sonuçlandırılır ve bütün yapay zekâların (`tahminler/<klasör>/`) o güne ait tahminleri
ve kuponları burada değerlendirilir:

    python scripts/gun_degerlendirme.py --tarih 2026-11-20

`<tarih>.md` / `<tarih>.json`: bitmiş maçların sonuçları, yapay zekâ başına karne (ana tercih isabeti, 1 birim sabit
bahis getirisi, 1X2 Brier / log-loss, tutan kupon ve bacaklar) ve her yapay zekânın en çok güvenip tutmayan
tercihleri. Açık maçlar hiçbir zaman yazılmaz. Tahmin klasörleri GitHub'da değildir; bu alan herkese açıktır.
