#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation ./packages/knowledge ./packages/harness
.venv/bin/python -m pip check
