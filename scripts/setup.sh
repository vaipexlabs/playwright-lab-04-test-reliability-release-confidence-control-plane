#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python 3.12 is required. Install it and rerun this command." >&2
  exit 1
fi

python_series="$(${PYTHON_BIN} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "${python_series}" != "3.12" ]]; then
  echo "Python 3.12 is required; ${PYTHON_BIN} reports ${python_series}." >&2
  exit 1
fi

echo "Creating the locked Python environment..."
"${PYTHON_BIN}" -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install --upgrade "pip==26.2.1"
"${VENV_DIR}/bin/python" -m pip install --requirement "${PROJECT_ROOT}/requirements.lock"
"${VENV_DIR}/bin/pip-sync" "${PROJECT_ROOT}/requirements.lock"
"${VENV_DIR}/bin/python" -m pip install \
  --no-deps \
  --no-build-isolation \
  --editable "${PROJECT_ROOT}"

cp "${PROJECT_ROOT}/requirements.lock" "${VENV_DIR}/.requirements.lock"

"${PROJECT_ROOT}/scripts/install-browsers.sh"
"${PROJECT_ROOT}/scripts/validate-toolchain.sh"

echo
echo "Toolchain ready. Activate it with: source .venv/bin/activate"
