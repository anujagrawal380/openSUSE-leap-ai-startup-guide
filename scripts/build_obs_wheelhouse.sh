#!/usr/bin/env bash
# Build a wheelhouse archive for OBS/offline container experiments.

set -euo pipefail

OUT_DIR="${OUT_DIR:-dist/obs-wheelhouse}"
ARCHIVE="${ARCHIVE:-dist/wheelhouse.tar.gz}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements.txt}"

mkdir -p "$OUT_DIR" "$(dirname "$ARCHIVE")"

if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    printf 'pip is required. Install python3-pip or use PYTHON_BIN pointing to a venv.\n' >&2
    exit 1
fi

"$PYTHON_BIN" -m pip download \
    --dest "$OUT_DIR" \
    --only-binary=:all: \
    --requirement "$REQUIREMENTS_FILE"

tar -C "$OUT_DIR" -czf "$ARCHIVE" .
printf 'wrote %s\n' "$ARCHIVE"
