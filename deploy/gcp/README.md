# Sistemi Türkiye dışında çalıştırmak — Google Cloud ücretsiz sunucu

Bazı kaynaklar (keskin borsalar, football-data.co.uk, Club Elo, bazı maç önizleme siteleri) Türkiye'den açılmıyor.
Google Cloud'un **ücretsiz katmanındaki** küçük bir sanal makinede (ABD) sistem bunlara doğrudan ulaşır. Tahminler
sunucuda ve bilgisayarında gizli kalır; GitHub'a gönderilmez (`tahminler/*/*` git'e girmez).

## Senin yapacakların (bir kez, ~15 dakika)

Hesap açmak ve kart doğrulaması kişisel bilgi gerektirdiği için bunları yalnız sen yapabilirsin.

1. https://cloud.google.com/free adresinden hesap aç (kart doğrulaması istenir; ücretsiz katmanda ücret alınmaz,
   bütçe uyarısı kurman önerilir: Faturalandırma → Bütçeler ve uyarılar → 1 USD).
2. Google Cloud CLI'yi kur: https://cloud.google.com/sdk/docs/install , sonra PowerShell'de:

   ```powershell
   gcloud init
   ```

3. Ücretsiz sunucuyu oluştur (ücretsiz katman yalnız bu üç bölgede ve `e2-micro` için geçerlidir):

   ```powershell
   gcloud compute instances create futbol-dehasi --zone us-central1-a --machine-type e2-micro --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud --boot-disk-size 30GB --boot-disk-type pd-standard
   ```

## Benim yapacaklarım (sen "kur" deyince)

```powershell
gcloud compute scp deploy\gcp\kurulum.sh futbol-dehasi:~ --zone us-central1-a
```

```powershell
gcloud compute ssh futbol-dehasi --zone us-central1-a --command "bash kurulum.sh"
```

Sonra API anahtarı sunucudaki `.env` dosyasına yazılır (GitHub'a gitmez).

## Kullanım (yalnız sen istediğinde)

```powershell
powershell -File deploy\gcp\calistir.ps1 -Tarih 2026-11-21
```

Sunucuda o günün bütün analizi (fiyatlar, Club Elo, arşiv güncellemesi, derin araştırma, bütün geçmiş kaynakları,
bahis aileleri, simülasyon) çalışır ve `tahminler/claudetahmin/<gün>` klasörü bilgisayarına kopyalanır.

## Sınırlar

- `e2-micro` 1 GB bellekli; kurulum 2 GB takas alanı açar. Analiz bilgisayardakinden yavaş çalışabilir.
- Ücretsiz katman koşullarını Google değiştirebilir; bütçe uyarısı bu yüzden önemli.
- Sunucu 7/24 açık durur ama sistem kendiliğinden çalışmaz (kural: yalnız sen istediğinde).
