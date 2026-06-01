#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
OUT_DIR="${1:-$ROOT_DIR/artifacts}"

mkdir -p "$OUT_DIR"

if [[ ! -d "$DATA_DIR/by_icao" || ! -d "$DATA_DIR/lightning_by_icao" ]]; then
  echo "Expected data/by_icao and data/lightning_by_icao to exist."
  exit 1
fi

BY_ICAO_ARCHIVE="$OUT_DIR/by_icao.tar.gz"
LIGHTNING_ARCHIVE="$OUT_DIR/lightning_by_icao.tar.gz"

# Archive folders with stable root paths expected by bootstrap_data_from_release.sh.
tar -czf "$BY_ICAO_ARCHIVE" -C "$DATA_DIR" by_icao
tar -czf "$LIGHTNING_ARCHIVE" -C "$DATA_DIR" lightning_by_icao

sha256sum "$BY_ICAO_ARCHIVE" "$LIGHTNING_ARCHIVE" > "$OUT_DIR/data_archives.sha256"

echo "Created archives:"
ls -lh "$BY_ICAO_ARCHIVE" "$LIGHTNING_ARCHIVE"
echo "Checksums: $OUT_DIR/data_archives.sha256"
