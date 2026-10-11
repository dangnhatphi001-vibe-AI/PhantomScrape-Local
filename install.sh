#!/usr/bin/env bash
set -euo pipefail
phantom_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo "Cần Python 3.11 trở lên. Cài Python rồi chạy lại lệnh này." >&2
    exit 1
fi
exec python3 "$phantom_source/scripts/install.py" "$@"
