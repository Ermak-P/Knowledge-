#!/usr/bin/env sh
set -eu
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "${1:-}" = "--mcp-dir" ]; then
  exec "${KNOWLEDGE_PYTHON:-python3}" "$SCRIPT_DIR/machine-install.py" "$@"
fi
exec "${KNOWLEDGE_PYTHON:-python3}" "$SCRIPT_DIR/install.py" "$@"
