#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT_VALUE="${PORT:-10000}"

# Bootstrap parquet data (downloads from GitHub Releases using env vars)
echo "[start] running data bootstrap..."
bash "$ROOT_DIR/scripts/helpers/bootstrap_data_from_release.sh"

echo "[start] bootstrap complete, launching server..."

export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-40}"
GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-10}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-300}"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
	PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
	PYTHON_BIN="python"
fi

echo "[start] launching gunicorn on port ${PORT_VALUE} workers=${WEB_CONCURRENCY} max_requests=${GUNICORN_MAX_REQUESTS} jitter=${GUNICORN_MAX_REQUESTS_JITTER}"

exec "$PYTHON_BIN" -m gunicorn webapp.backend.main:app \
	--worker-class uvicorn.workers.UvicornWorker \
	--workers "${WEB_CONCURRENCY}" \
	--bind "0.0.0.0:${PORT_VALUE}" \
	--max-requests "${GUNICORN_MAX_REQUESTS}" \
	--max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER}" \
	--timeout "${GUNICORN_TIMEOUT}"
