#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for knowledge_python in python3.12 python3 python; do
  if command -v "$knowledge_python" >/dev/null 2>&1 && "$knowledge_python" -c 'import sys; sys.exit(sys.version_info[:2] != (3,12))'; then
    exec "$knowledge_python" -I "$source_dir/install.py" "$@"
  fi
done
printf '%s\n' 'Python 3.12 is required. Install Python 3.12 from python.org, then rerun this command.' >&2
exit 1
