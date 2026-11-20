#!/usr/bin/env bash
# One-time setup of the system on a Google Cloud "e2-micro" free-tier VM (Ubuntu 24.04, us-central1 / us-east1 /
# us-west1). Run ON THE VM:  bash kurulum.sh
# Why: some sources the system needs (sharp exchanges, football-data.co.uk, Club Elo, several preview sites) are not
# reachable from Turkey; from the VM they are. Predictions stay private on the VM (tahminler/*/* is git-ignored) and
# are copied back to the PC with deploy/gcp/calistir.ps1 — never pushed to GitHub.
set -euo pipefail

REPO="https://github.com/ramazanardic/futbol-dehasi.git"
DIR="$HOME/futbol-dehasi"

# e2-micro has 1 GB RAM: a 2 GB swap file keeps pandas / model fits from being killed
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv python3-pip

if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q --ff-only; else git clone -q "$REPO" "$DIR"; fi
cd "$DIR"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -e .

# Keys stay on the VM only (.env is git-ignored). Write it once by hand:
#   echo "API_FOOTBALL_KEY=..." > ~/futbol-dehasi/.env
[ -f .env ] || echo "# API_FOOTBALL_KEY=... (kendi anahtarını yaz)" > .env
chmod 600 .env

.venv/bin/python -m pytest -q -p no:cacheprovider | tail -1
echo "Kurulum tamam: $DIR"
