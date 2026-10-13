#!/usr/bin/env bash
# Baixa, um ativo por vez (evita HTTP 429), os dados M5 bid/ask 2019-2026 do laboratório.
# Retomável: blocos completos são pulados. Uso: bash scripts/download_lab_assets.sh
set -u
cd "$(dirname "$0")/.."
for asset in NAS100 SPX500 EURUSD WTI; do
  root="D:/OneB/market-data/dukascopy-$(echo "$asset" | tr 'A-Z' 'a-z')-2019-2026"
  if ls "$root/normalized/"*_M5_2019-03-01_2026-09-26.csv.gz >/dev/null 2>&1; then
    echo "$asset já completo"; continue
  fi
  echo "== $asset $(date +%H:%M)"
  python scripts/download_dukascopy_intraday.py --instrument "$asset" --timeframe m5 --start 2019-03-01 --end 2026-09-26 \
    --chunk-days 30 --batch-pause-ms 3000 --retry-wait-max 120 --output-root "$root" > "$root.log" 2>&1
  echo "$asset EXIT=$?"
done
