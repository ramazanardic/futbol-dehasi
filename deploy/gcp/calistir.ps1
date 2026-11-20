# Runs the day's analysis on the Google Cloud VM (outside Turkey) and copies the AI's private day folder back to
# this PC. Only on request (user rule: the system runs when the user asks).
#   powershell -File deploy\gcp\calistir.ps1 -Tarih 2026-11-21 [-Vm futbol-dehasi] [-Zone us-central1-a] [-Ai claudetahmin]
param(
    [string]$Tarih = (Get-Date -Format "yyyy-MM-dd"),
    [string]$Vm = "futbol-dehasi",
    [string]$Zone = "us-central1-a",
    [string]$Ai = "claudetahmin"
)
$ErrorActionPreference = "Stop"
$remote = @"
set -e
cd ~/futbol-dehasi && git pull -q --ff-only
export QUANTFOOT_AI=$Ai PYTHONIOENCODING=utf-8
P=.venv/bin/python
`$P scripts/fetch_global_odds.py
`$P scripts/elo_gorus.py --cek || true
`$P scripts/arsiv_guncelle.py
`$P scripts/nesine_global.py --date $Tarih
`$P scripts/ai_tahmin.py --tarih $Tarih
`$P scripts/derin_tahmin.py --tarih $Tarih
`$P scripts/openfootball_gecmis.py --tarih $Tarih
`$P scripts/wiki_gecmis.py --tarih $Tarih
`$P scripts/api_gecmis.py --tarih $Tarih
`$P scripts/bahis_aileleri.py --tarih $Tarih
`$P scripts/simulasyon.py --tarih $Tarih
"@
gcloud compute ssh $Vm --zone $Zone --command $remote
$dest = Join-Path $PSScriptRoot "..\..\tahminler\$Ai"
New-Item -ItemType Directory -Force $dest | Out-Null
gcloud compute scp --recurse --zone $Zone "${Vm}:~/futbol-dehasi/tahminler/$Ai/$Tarih" $dest
Write-Output "Tamam: tahminler\$Ai\$Tarih bilgisayara kopyalandı (GitHub'a gönderilmez)."
