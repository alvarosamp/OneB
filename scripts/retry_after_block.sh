#!/usr/bin/env bash
# Refaz o que a falha da Dukascopy de 08/10/2026 pode ter afetado, pelo feed clássico gratuito
# (scripts/dukascopy_feed.py: uma requisição a cada 8 s; 429 pausa 15-60 min). Pequeno primeiro.
# Uso: bash scripts/retry_after_block.sh > D:/OneB/market-data/retry_after_block.log 2>&1
set -u
cd "$(dirname "$0")/.."
echo "== diário: refazendo excluídos $(date '+%d/%m %H:%M')"
python scripts/download_dukascopy_daily.py ausidxaud hkgidxhkd eusidxeur brentcmdusd gascmdusd coppercmdusd 2>&1 | grep --line-buffered -E "linhas=|FALHA|429|Traceback|Error"
echo "== WTI M5: reverificando lacunas $(date '+%d/%m %H:%M')"
python scripts/reverify_source_gaps.py D:/OneB/market-data/dukascopy-wti-2019-2026 2>&1 | grep --line-buffered -E "removidas|Error|Traceback"
bash scripts/download_lab_assets.sh
echo "== XAUUSD M5 $(date '+%d/%m %H:%M')"
python scripts/download_dukascopy_intraday.py --instrument XAUUSD --timeframe m5 --start 2019-03-01 --end 2026-09-26 --chunk-days 30 --batch-pause-ms 3000 --retry-wait-max 120 --output-root D:/OneB/market-data/dukascopy-xau-2019-2026 > D:/OneB/market-data/dukascopy-xau-2019-2026-rebuild.log 2>&1
echo "XAUUSD EXIT=$? $(date '+%d/%m %H:%M')"
