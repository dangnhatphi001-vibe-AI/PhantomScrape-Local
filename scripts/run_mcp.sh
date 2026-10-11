#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
    echo "Missing .venv. Install requirements-local.txt first (see README)." >&2
    exit 1
fi
exec "$project_dir/.venv/bin/python" -m phantom_local mcp
