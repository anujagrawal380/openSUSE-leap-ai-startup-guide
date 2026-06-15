#!/usr/bin/env bash
# Run the assistant as an openSUSE-native Podman container.
#
# This is the Phase 1 deployment path: keep the ML stack inside the BCI-based
# container, keep models/vectorstore in a persistent volume, and expose a local
# web UI while preserving host system-context detection.

set -euo pipefail

IMAGE="${SUSE_ASSIST_IMAGE:-ghcr.io/anujagrawal380/opensuse-leap-ai-startup-guide:latest}"
CONTAINER_NAME="${SUSE_ASSIST_CONTAINER:-suse-assist}"
DATA_VOLUME="${SUSE_ASSIST_DATA_VOLUME:-suse-assist-data}"
PORT="${SUSE_ASSIST_PORT:-7860}"
MODEL_TIER="${SUSE_ASSIST_MODEL_TIER:-standard}"

usage() {
    cat <<EOF
Usage: $0 <command>

Commands:
  pull       Pull the configured image
  ingest     Build/update the documentation index in the persistent volume
  web        Run the web UI in the foreground
  web -d     Run the web UI detached
  stop       Stop and remove the web container
  status     Show container status and listening port

Environment:
  SUSE_ASSIST_IMAGE        Container image
                            default: ${IMAGE}
  SUSE_ASSIST_CONTAINER    Container name
                            default: ${CONTAINER_NAME}
  SUSE_ASSIST_DATA_VOLUME  Persistent data volume
                            default: ${DATA_VOLUME}
  SUSE_ASSIST_PORT         Host/web port
                            default: ${PORT}
  SUSE_ASSIST_MODEL_TIER   Model tier: test, lite, standard, full, auto
                            default: ${MODEL_TIER}

Examples:
  $0 pull
  $0 ingest
  $0 web -d
  SUSE_ASSIST_PORT=19000 $0 web -d
  SUSE_ASSIST_IMAGE=registry.opensuse.org/.../suse-assist:latest $0 web -d
EOF
}

need_podman() {
    if ! command -v podman >/dev/null 2>&1; then
        echo "podman is required. On openSUSE: sudo zypper install podman" >&2
        exit 1
    fi
}

stop_container() {
    podman stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    podman rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}

pull_image() {
    podman pull "${IMAGE}"
}

ingest_docs() {
    podman run --rm \
        -v "${DATA_VOLUME}:/app/data" \
        "${IMAGE}" ingest
}

run_web() {
    local detach_flag=()
    if [[ "${1:-}" == "-d" || "${1:-}" == "--detach" ]]; then
        detach_flag=(-d)
    fi

    stop_container
    podman run "${detach_flag[@]}" \
        --name "${CONTAINER_NAME}" \
        --network=host \
        --restart=unless-stopped \
        -v "${DATA_VOLUME}:/app/data" \
        -v /:/host:ro \
        -e SUSE_AI_HOST_ROOT=/host \
        -e HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}" \
        -e TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-0}" \
        "${IMAGE}" web --model-tier "${MODEL_TIER}" --port "${PORT}"
}

show_status() {
    podman ps --filter "name=${CONTAINER_NAME}" \
        --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"
    echo
    echo "Web UI: http://localhost:${PORT}/"
}

main() {
    case "${1:-}" in
        help|--help|-h|"")
            usage
            ;;
        pull)
            need_podman
            pull_image
            ;;
        ingest)
            need_podman
            ingest_docs
            ;;
        web)
            need_podman
            run_web "${2:-}"
            ;;
        stop)
            need_podman
            stop_container
            ;;
        status)
            need_podman
            show_status
            ;;
        *)
            echo "Unknown command: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
}

main "$@"
