#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---headless}"

"${PROJECT_ROOT}/scripts/ensure-toolchain.sh"

case "${MODE}" in
  --headless)
    exec "${PROJECT_ROOT}/.venv/bin/pytest" -q tests/e2e
    ;;
  --headed)
    exec "${PROJECT_ROOT}/.venv/bin/pytest" -q tests/e2e --headed
    ;;
  *)
    echo "Usage: ./scripts/test-e2e.sh [--headless|--headed]" >&2
    exit 2
    ;;
esac
