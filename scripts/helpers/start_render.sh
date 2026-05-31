#!/usr/bin/env bash
set -euo pipefail

PORT_VALUE="${PORT:-10000}"
echo "[start] launching uvicorn on port ${PORT_VALUE}"

exec python -m uvicorn webapp.backend.main:app --host 0.0.0.0 --port "${PORT_VALUE}"
