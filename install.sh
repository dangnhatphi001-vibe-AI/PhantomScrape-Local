#!/usr/bin/env bash
set -euo pipefail
if ! command -v python3 >/dev/null 2>&1; then
    echo "Cần Python 3.11 trở lên. Cài Python rồi chạy lại lệnh này." >&2
    exit 1
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Cần Python 3.11 trở lên.")'

# Local checkout: use its sources. From a GitHub one-liner: download the sources.
phantom_script="${BASH_SOURCE[0]:-}"
if [[ -f "$phantom_script" ]]; then
    phantom_source="$(cd -- "$(dirname -- "$phantom_script")" && pwd)"
    if [[ -f "$phantom_source/scripts/install.py" && -f "$phantom_source/requirements-local.txt" ]]; then
        exec python3 "$phantom_source/scripts/install.py" "$@"
    fi
fi

if ! command -v curl >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1; then
    echo "Cần curl và tar để tải source từ GitHub." >&2
    exit 1
fi
phantom_temp="$(mktemp -d)"
trap 'rm -rf -- "$phantom_temp"' EXIT
echo "Đang tải PhantomScrape Local từ GitHub…"
curl --fail --silent --show-error --location \
    "https://codeload.github.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/tar.gz/refs/heads/main" \
    -o "$phantom_temp/source.tar.gz"
mkdir "$phantom_temp/source"
tar -xzf "$phantom_temp/source.tar.gz" --strip-components=1 -C "$phantom_temp/source"
python3 "$phantom_temp/source/scripts/install.py" "$@"
