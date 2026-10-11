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
phantom_download_pid=""
trap 'if [[ -n "$phantom_download_pid" ]]; then kill "$phantom_download_pid" 2>/dev/null || true; fi; rm -rf -- "$phantom_temp"' EXIT
trap 'exit 130' INT
echo "Đang tải PhantomScrape Local từ GitHub…"
curl --fail --silent --show-error --location \
    "https://codeload.github.com/dangnhatphi001-vibe-AI/PhantomScrape-Local/tar.gz/refs/heads/main" \
    -o "$phantom_temp/source.tar.gz" 2>"$phantom_temp/download-error.log" &
phantom_download_pid=$!
if [[ -t 1 ]]; then
    phantom_frames=("◐" "◓" "◑" "◒")
    phantom_tick=0
    while kill -0 "$phantom_download_pid" 2>/dev/null; do
        printf '\r%s Đang tải source từ GitHub…' "${phantom_frames[$((phantom_tick % 4))]}"
        phantom_tick=$((phantom_tick + 1))
        sleep 0.12
    done
    printf '\r                                         \r'
fi
if wait "$phantom_download_pid"; then
    phantom_download_pid=""
    echo "✓ Đã tải source từ GitHub."
else
    phantom_status=$?
    phantom_download_pid=""
    cat "$phantom_temp/download-error.log" >&2
    exit "$phantom_status"
fi
mkdir "$phantom_temp/source"
tar -xzf "$phantom_temp/source.tar.gz" --strip-components=1 -C "$phantom_temp/source"
python3 "$phantom_temp/source/scripts/install.py" "$@"
