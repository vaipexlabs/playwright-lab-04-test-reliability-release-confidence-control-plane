#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Run ./scripts/setup.sh before validating the toolchain." >&2
  exit 1
fi

"${PYTHON}" - <<'PY'
from importlib.metadata import version
import sys

from playwright.sync_api import sync_playwright

expected = {
    "fastapi": "0.141.1",
    "httpx2": "2.10.0",
    "playwright": "1.62.0",
    "pytest": "9.1.1",
    "pytest-html": "4.2.0",
    "pytest-playwright": "0.9.0",
    "pytest-rerunfailures": "16.4",
    "pytest-xdist": "3.8.0",
    "ruff": "0.16.3",
}

assert sys.version_info[:2] == (3, 12), sys.version
for distribution, required_version in expected.items():
    installed_version = version(distribution)
    assert installed_version == required_version, (
        f"{distribution}: expected {required_version}, found {installed_version}"
    )

print("Toolchain contract validated:")
print(f"  Python {sys.version.split()[0]}")
for distribution, required_version in expected.items():
    print(f"  {distribution} {required_version}")

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    print(f"  Chromium {browser.version} (managed by Playwright)")
    browser.close()
PY

"${PYTHON}" -m pip check
