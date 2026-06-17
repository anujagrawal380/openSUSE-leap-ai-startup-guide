#!/usr/bin/env bash
# Open the local suse-assist web UI, starting the system service when available.

set -euo pipefail

URL="${SUSE_ASSIST_URL:-http://localhost:7860/}"
SERVICE="${SUSE_ASSIST_SERVICE:-suse-assist.service}"

service_exists() {
    command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files "$SERVICE" >/dev/null 2>&1
}

if service_exists && ! systemctl is-active --quiet "$SERVICE"; then
    systemctl start "$SERVICE" >/dev/null 2>&1 || true
fi

if command -v xdg-open >/dev/null 2>&1; then
    exec xdg-open "$URL"
fi

printf '%s\n' "$URL"
