#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAYWRIGHT="${PROJECT_ROOT}/.venv/bin/playwright"

if [[ ! -x "${PLAYWRIGHT}" ]]; then
  echo "Run ./scripts/setup.sh before installing browsers." >&2
  exit 1
fi

echo "Installing the Playwright-managed Chromium renderer..."
"${PLAYWRIGHT}" install chromium
