#!/usr/bin/env bash
# Load a transferred container image archive into local Podman.

set -euo pipefail

usage() {
    cat <<EOF
Usage: $0 <image-archive>

Examples:
  $0 /var/tmp/suse-assist-bci-phase1.tar.zst
  $0 /var/tmp/suse-assist-bci-phase1.tar.gz
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -lt 1 ]]; then
    usage
    exit 0
fi

ARCHIVE="$1"

if [[ ! -f "${ARCHIVE}" ]]; then
    echo "archive not found: ${ARCHIVE}" >&2
    exit 1
fi

if [[ -f "${ARCHIVE}.sha256" ]]; then
    (cd "$(dirname "${ARCHIVE}")" && sha256sum -c "$(basename "${ARCHIVE}").sha256")
fi

case "${ARCHIVE}" in
    *.tar.zst)
        zstd -dc "${ARCHIVE}" | podman load
        ;;
    *.tar.gz|*.tgz)
        gzip -dc "${ARCHIVE}" | podman load
        ;;
    *.tar)
        podman load -i "${ARCHIVE}"
        ;;
    *)
        echo "unsupported archive extension: ${ARCHIVE}" >&2
        exit 1
        ;;
esac

