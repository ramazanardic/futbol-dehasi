#!/usr/bin/env bash
# Linux equivalent of scripts/kupon_izle.cmd (not installed as cron; run on request or from your own timer).
# Re-reads every in-force coupon leg on the live Nesine bulletin; archives yesterday's API-Football results once.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONIOENCODING=utf-8
export TZ="${TZ:-Europe/Istanbul}"
if [[ -z "${QUANTFOOT_AI:-}" ]]; then
  echo "QUANTFOOT_AI tanımlı değil. Örnek: export QUANTFOOT_AI=grokbottahmin" >&2
  echo "Geçerli değerler: claudetahmin, geminitahmin, antigravitytahmin, chatgbttahmin, grokbottahmin" >&2
  exit 1
fi
mkdir -p reports/daily/logs
LOG="reports/daily/logs/kupon_izle.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] QUANTFOOT_AI=${QUANTFOOT_AI}" >> "$LOG"
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
else
  PY=python3
fi
"$PY" scripts/kupon_kontrol.py kontrol >> "$LOG" 2>&1
"$PY" scripts/api_gecmis.py --arsiv >> "$LOG" 2>&1
