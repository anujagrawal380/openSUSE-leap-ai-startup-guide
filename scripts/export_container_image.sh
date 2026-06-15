#!/usr/bin/env bash
# Export a container image as a compressed archive for transfer to an offline VM.

set -euo pipefail

usage() {
    cat <<EOF
Usage: $0 <image> [archive-prefix]

Examples:
  $0 suse-assist:bci-phase1
  $0 registry.opensuse.org/.../suse-assist:latest suse-assist-bci-phase1

Output:
  <archive-prefix>.tar.zst or <archive-prefix>.tar.gz
  matching .sha256 file
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -lt 1 ]]; then
    usage
    exit 0
fi

IMAGE="$1"
PREFIX="${2:-${IMAGE//[^A-Za-z0-9_.-]/_}}"

if command -v podman >/dev/null 2>&1; then
    RUNTIME=podman
elif command -v docker >/dev/null 2>&1; then
    RUNTIME=docker
else
    echo "podman or docker is required to export an image" >&2
    exit 1
fi

if command -v zstd >/dev/null 2>&1; then
    ARCHIVE="${PREFIX}.tar.zst"
    "${RUNTIME}" save "${IMAGE}" | zstd -T0 -19 -o "${ARCHIVE}"
elif command -v gzip >/dev/null 2>&1; then
    ARCHIVE="${PREFIX}.tar.gz"
    "${RUNTIME}" save "${IMAGE}" | gzip -9 > "${ARCHIVE}"
else
    ARCHIVE="${PREFIX}.tar"
    "${RUNTIME}" save "${IMAGE}" > "${ARCHIVE}"
fi

sha256sum "${ARCHIVE}" > "${ARCHIVE}.sha256"

echo "Wrote ${ARCHIVE}"
echo "Wrote ${ARCHIVE}.sha256"

