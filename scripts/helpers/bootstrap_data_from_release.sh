#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATA_DIR="$ROOT_DIR/data"
BY_ICAO_DIR="$DATA_DIR/by_icao"
LIGHTNING_DIR="$DATA_DIR/lightning_by_icao"

BY_ICAO_ARCHIVE_NAME="${AVCLIMATE_BY_ICAO_ARCHIVE_NAME:-by_icao.tar.gz}"
LIGHTNING_ARCHIVE_NAME="${AVCLIMATE_LIGHTNING_ARCHIVE_NAME:-lightning_by_icao.tar.gz}"
RELEASE_BASE_URL="${AVCLIMATE_RELEASE_BASE_URL:-}"
BY_ICAO_URL="${AVCLIMATE_BY_ICAO_URL:-}"
LIGHTNING_URL="${AVCLIMATE_LIGHTNING_URL:-}"

BY_ICAO_SHA256="${AVCLIMATE_BY_ICAO_SHA256:-}"
LIGHTNING_SHA256="${AVCLIMATE_LIGHTNING_SHA256:-}"

if [[ -n "$RELEASE_BASE_URL" ]]; then
  BY_ICAO_URL="${BY_ICAO_URL:-$RELEASE_BASE_URL/$BY_ICAO_ARCHIVE_NAME}"
  LIGHTNING_URL="${LIGHTNING_URL:-$RELEASE_BASE_URL/$LIGHTNING_ARCHIVE_NAME}"
fi

has_parquet_files() {
  local dir="$1"
  [[ -d "$dir" ]] && find "$dir" -type f -name "*.parquet" -print -quit | grep -q .
}

if has_parquet_files "$BY_ICAO_DIR" && has_parquet_files "$LIGHTNING_DIR"; then
  echo "[bootstrap] local parquet data already present, skipping download"
  exit 0
fi

if [[ -z "$BY_ICAO_URL" || -z "$LIGHTNING_URL" ]]; then
  cat <<'EOF'
[bootstrap] parquet data missing and no download URLs configured.
Set either:
  - AVCLIMATE_RELEASE_BASE_URL
or both:
  - AVCLIMATE_BY_ICAO_URL
  - AVCLIMATE_LIGHTNING_URL
EOF
  exit 1
fi

mkdir -p "$DATA_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

CURL_AUTH_ARGS=()
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  CURL_AUTH_ARGS=(-H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/octet-stream")
fi

download_archive() {
  local url="$1"
  local out_path="$2"
  echo "[bootstrap] downloading $url"
  curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors "${CURL_AUTH_ARGS[@]}" "$url" -o "$out_path"
}

verify_sha256() {
  local file_path="$1"
  local expected="$2"
  if [[ -z "$expected" ]]; then
    return 0
  fi
  local actual
  actual="$(sha256sum "$file_path" | awk '{print $1}')"
  if [[ "$actual" != "$expected" ]]; then
    echo "[bootstrap] checksum mismatch for $file_path"
    echo "[bootstrap] expected=$expected"
    echo "[bootstrap] actual=$actual"
    exit 1
  fi
}

extract_archive() {
  local archive_path="$1"
  local target_dir_name="$2"
  local target_dir="$DATA_DIR/$target_dir_name"

  rm -rf "$target_dir"
  mkdir -p "$DATA_DIR"
  tar -xzf "$archive_path" -C "$DATA_DIR"

  if [[ ! -d "$target_dir" ]]; then
    echo "[bootstrap] expected directory $target_dir_name not found in archive"
    exit 1
  fi
}

BY_ICAO_ARCHIVE="$TMP_DIR/$BY_ICAO_ARCHIVE_NAME"
LIGHTNING_ARCHIVE="$TMP_DIR/$LIGHTNING_ARCHIVE_NAME"

download_archive "$BY_ICAO_URL" "$BY_ICAO_ARCHIVE"
verify_sha256 "$BY_ICAO_ARCHIVE" "$BY_ICAO_SHA256"
extract_archive "$BY_ICAO_ARCHIVE" "by_icao"

download_archive "$LIGHTNING_URL" "$LIGHTNING_ARCHIVE"
verify_sha256 "$LIGHTNING_ARCHIVE" "$LIGHTNING_SHA256"
extract_archive "$LIGHTNING_ARCHIVE" "lightning_by_icao"

if ! has_parquet_files "$BY_ICAO_DIR"; then
  echo "[bootstrap] by_icao parquet files not found after extraction"
  exit 1
fi
if ! has_parquet_files "$LIGHTNING_DIR"; then
  echo "[bootstrap] lightning parquet files not found after extraction"
  exit 1
fi

echo "[bootstrap] parquet data ready"
