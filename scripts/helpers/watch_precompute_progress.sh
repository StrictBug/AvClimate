#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/AvClimate

total=212
fog=$(find statistics/precomputed/fog_low_cloud -maxdepth 1 -type f -name '*.json.gz' | wc -l)
smoke=$(find statistics/precomputed/smoke_dust -maxdepth 1 -type f -name '*.json.gz' | wc -l)
fog_mb=$(du -sb statistics/precomputed/fog_low_cloud | awk '{printf "%.3f", $1/1024/1024}')
smoke_mb=$(du -sb statistics/precomputed/smoke_dust | awk '{printf "%.3f", $1/1024/1024}')
pct=$(awk -v n="$fog" -v t="$total" 'BEGIN {printf "%.1f", (n/t)*100}')

printf 'fog: %s/%s (%.1f%%)\n' "$fog" "$total" "$pct"
printf 'smoke: %s/%s\n' "$smoke" "$total"
printf 'fog size: %s MB\n' "$fog_mb"
printf 'smoke size: %s MB\n' "$smoke_mb"
ps -ef | grep -E 'scripts/helpers/precompute_fog_low_cloud.py|scripts/helpers/precompute_smoke_dust.py' | grep -v grep || true