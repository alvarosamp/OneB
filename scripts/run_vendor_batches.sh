#!/usr/bin/env bash
# Roda em sequência as capturas MT5 (validação + anos) de uma família. Uso:
#   bash scripts/run_vendor_batches.sh 100pips_H1 pilot45
#   bash scripts/run_vendor_batches.sh london_H1 pilot46
set -u
cd "$(dirname "$0")/.."
case_="$1"; prefix="$2"
for b in m1 dkval dk2019 dk2020 dk2021 dk2022 dk2023 dk2024 dk2025 dk2026; do
  if ls "D:/OneB/research/ex5_dukascopy/${prefix}${b}/"*objects.csv >/dev/null 2>&1; then echo "${prefix}${b} já capturado"; continue; fi
  start=$(date +%s)
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& .\scripts\run_mt5_vendor_pilots.ps1 -Cases $case_ -Batch ${prefix}${b} -MaxTestSeconds 3600 -DestinationRoot 'D:\OneB\research\ex5_dukascopy'" 2>&1 | grep -E "COMPLETED|truncated_snapshots|Timeout|UNSUPPORTED|throw" | tr '\n' ' '
  echo " ${prefix}${b} $(( $(date +%s) - start ))s"
  while tasklist | grep -qi terminal64; do sleep 20; done
done
