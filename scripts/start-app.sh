#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8000}"

"${PROJECT_ROOT}/scripts/ensure-toolchain.sh"
exec "${PROJECT_ROOT}/.venv/bin/python" -m uvicorn \
  vaipex_test_reliability.app:app \
  --app-dir "${PROJECT_ROOT}/src" \
  --host 127.0.0.1 \
  --port "${PORT}"
