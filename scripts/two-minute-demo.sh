#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"

echo "Vaipex Test Reliability & Release Confidence Control Plane"
echo "============================================================"
echo
echo "1/5 Validate the locked Playwright reliability toolchain"
"${PROJECT_ROOT}/scripts/validate-toolchain.sh"
echo
echo "2/5 Verify policy, governance, and decision logic"
"${PYTHON}" -m pytest -q tests/unit
echo
echo "3/5 Execute and correlate two healthy-profile shards"
"${PROJECT_ROOT}/scripts/run-reliability-shard.sh" healthy 0 2 "${PROJECT_ROOT}/reports/shards/healthy-0.json"
"${PROJECT_ROOT}/scripts/run-reliability-shard.sh" healthy 1 2 "${PROJECT_ROOT}/reports/shards/healthy-1.json"
"${PYTHON}" -m vaipex_test_reliability.control_plane merge \
  --output "${PROJECT_ROOT}/reports/healthy-evidence.json" \
  "${PROJECT_ROOT}/reports/shards/healthy-0.json" \
  "${PROJECT_ROOT}/reports/shards/healthy-1.json"
echo
echo "4/5 Prove the healthy evidence produces RELEASE"
"${PYTHON}" -m vaipex_test_reliability.control_plane decide \
  --input "${PROJECT_ROOT}/reports/healthy-evidence.json" \
  --output "${PROJECT_ROOT}/reports/healthy-decision.json" \
  --html "${PROJECT_ROOT}/reports/healthy-release.html" \
  --expect release
echo
echo "5/5 Inject a critical failure and prove policy produces HOLD"
"${PROJECT_ROOT}/scripts/run-reliability-shard.sh" incident 0 2 "${PROJECT_ROOT}/reports/shards/incident-0.json"
"${PROJECT_ROOT}/scripts/run-reliability-shard.sh" incident 1 2 "${PROJECT_ROOT}/reports/shards/incident-1.json"
"${PYTHON}" -m vaipex_test_reliability.control_plane merge \
  --output "${PROJECT_ROOT}/reports/incident-evidence.json" \
  "${PROJECT_ROOT}/reports/shards/incident-0.json" \
  "${PROJECT_ROOT}/reports/shards/incident-1.json"
"${PYTHON}" -m vaipex_test_reliability.control_plane decide \
  --input "${PROJECT_ROOT}/reports/incident-evidence.json" \
  --output "${PROJECT_ROOT}/reports/incident-decision.json" \
  --html "${PROJECT_ROOT}/reports/incident-hold.html" \
  --expect hold
echo
echo "Demo complete. Review reports/healthy-release.html and reports/incident-hold.html."
