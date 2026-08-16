#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${1:-healthy}"
SHARD_INDEX="${2:-0}"
SHARD_COUNT="${3:-1}"
OUTPUT="${4:-${PROJECT_ROOT}/reports/shards/${PROFILE}-${SHARD_INDEX}.json}"

"${PROJECT_ROOT}/scripts/ensure-toolchain.sh"
exec "${PROJECT_ROOT}/.venv/bin/python" \
  -m vaipex_test_reliability.control_plane run-shard \
  --profile "${PROFILE}" \
  --shard-index "${SHARD_INDEX}" \
  --shard-count "${SHARD_COUNT}" \
  --output "${OUTPUT}"
