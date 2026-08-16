#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
LOCK_FILE="${PROJECT_ROOT}/requirements.lock"
INSTALLED_LOCK="${VENV_DIR}/.requirements.lock"

if [[ ! -x "${VENV_DIR}/bin/python" ]] || \
   [[ ! -f "${INSTALLED_LOCK}" ]] || \
   ! cmp -s "${LOCK_FILE}" "${INSTALLED_LOCK}"; then
  echo "The local toolchain is missing or stale; rebuilding it."
  "${PROJECT_ROOT}/scripts/setup.sh"
fi
