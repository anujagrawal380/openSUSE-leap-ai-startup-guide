#!/usr/bin/env bash
# ============================================================================
# setup-leap-vm.sh — Deploy the openSUSE AI Onboarding Assistant on a Leap VM
#
# Usage:
#   curl -fsSL <raw-url>/deploy/setup-leap-vm.sh | bash
#   # or:
#   ./deploy/setup-leap-vm.sh [--native|--container]
#
# Options:
#   --native      Install directly with pip + systemd (default)
#   --container   Use Podman container deployment
#   --model-tier  Model tier: test, lite, standard, full, auto (default: auto)
#   --help        Show this help message
# ============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
DEPLOY_MODE="native"
MODEL_TIER="auto"
APP_DIR="/opt/suse-assist"
DATA_DIR="/var/lib/suse-assist"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_USER="suseai"
REPO_URL="https://github.com/anujagrawal380/opensuse-leap-ai-guide.git"

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --native)    DEPLOY_MODE="native"; shift ;;
        --container) DEPLOY_MODE="container"; shift ;;
        --model-tier)
            MODEL_TIER="$2"; shift 2 ;;
        --help|-h)
            head -n 14 "$0" | tail -n +2 | sed 's/^# *//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
info()  { echo -e "\033[1;32m[INFO]\033[0m  $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (or with sudo)."
    fi
}

check_leap() {
    if [[ ! -f /etc/os-release ]]; then
        error "Cannot detect OS. /etc/os-release not found."
    fi
    # shellcheck disable=SC1091
    source /etc/os-release
    if [[ "${ID:-}" != "opensuse-leap" && "${ID:-}" != "opensuse" ]]; then
        warn "This script is designed for openSUSE Leap. Detected: ${PRETTY_NAME:-unknown}"
        read -rp "Continue anyway? [y/N] " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || exit 0
    fi
    info "Detected: ${PRETTY_NAME:-openSUSE Leap}"
}

# ── Native deployment ─────────────────────────────────────────────────────────
deploy_native() {
    info "=== Native deployment ==="

    # 1. Install system dependencies
    info "Installing system packages..."
    zypper --non-interactive install --no-recommends \
        python311 python311-pip python311-devel \
        gcc gcc-c++ cmake \
        git \
        || true  # Don't fail if already installed

    # 2. Create service user
    if ! id "$SERVICE_USER" &>/dev/null; then
        info "Creating service user: ${SERVICE_USER}"
        useradd --system --create-home --shell /sbin/nologin "$SERVICE_USER"
    fi

    # 3. Clone or update the repository
    if [[ -d "${APP_DIR}/.git" ]]; then
        info "Updating existing repository..."
        git -C "$APP_DIR" pull --ff-only
    else
        info "Cloning repository to ${APP_DIR}..."
        git clone "$REPO_URL" "$APP_DIR"
    fi

    # 4. Create data directory
    mkdir -p "$DATA_DIR"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "$DATA_DIR"

    # 5. Create virtual environment and install
    info "Setting up Python virtual environment..."
    python3.11 -m venv "$VENV_DIR"
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
    pip install "${APP_DIR}"
    deactivate

    # 6. Update config for this deployment
    info "Configuring for model tier: ${MODEL_TIER}"
    cat > "${APP_DIR}/config-vm.yaml" <<EOF
model:
  inference_mode: "local"
  tier: "${MODEL_TIER}"
  n_gpu_layers: 0  # CPU-only unless CUDA/ROCm is available
  n_threads: $(nproc)

rag:
  persist_directory: "${DATA_DIR}/vectorstore"
  backend: "lancedb"

data_dir: "${DATA_DIR}"
log_level: "INFO"
EOF
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "$APP_DIR"

    # 7. Ingest documentation (first run)
    if [[ ! -d "${DATA_DIR}/vectorstore" ]] || [[ -z "$(ls -A "${DATA_DIR}/vectorstore" 2>/dev/null)" ]]; then
        info "Ingesting openSUSE documentation (first run)..."
        sudo -u "$SERVICE_USER" "${VENV_DIR}/bin/suse-assist" \
            --config "${APP_DIR}/config-vm.yaml" \
            ingest --max-pages 50
    else
        info "Vector store already populated, skipping ingest."
    fi

    # 8. Install systemd service
    info "Installing systemd service..."
    cp "${APP_DIR}/deploy/suse-assist.service" /etc/systemd/system/
    # Patch the service file with actual paths
    sed -i "s|__VENV_DIR__|${VENV_DIR}|g" /etc/systemd/system/suse-assist.service
    sed -i "s|__APP_DIR__|${APP_DIR}|g" /etc/systemd/system/suse-assist.service
    sed -i "s|__DATA_DIR__|${DATA_DIR}|g" /etc/systemd/system/suse-assist.service
    sed -i "s|__SERVICE_USER__|${SERVICE_USER}|g" /etc/systemd/system/suse-assist.service
    systemctl daemon-reload
    systemctl enable suse-assist.service

    # 9. Start the service
    info "Starting suse-assist service..."
    systemctl start suse-assist.service

    info "=== Deployment complete ==="
    info "Web UI: http://$(hostname -I | awk '{print $1}'):7860"
    info "Check status: systemctl status suse-assist"
    info "View logs: journalctl -u suse-assist -f"
}

# ── Container deployment ──────────────────────────────────────────────────────
deploy_container() {
    info "=== Container deployment ==="

    # 1. Install Podman
    info "Installing Podman..."
    zypper --non-interactive install --no-recommends podman || true

    # 2. Clone or update the repository
    if [[ -d "${APP_DIR}/.git" ]]; then
        info "Updating existing repository..."
        git -C "$APP_DIR" pull --ff-only
    else
        info "Cloning repository to ${APP_DIR}..."
        zypper --non-interactive install --no-recommends git || true
        git clone "$REPO_URL" "$APP_DIR"
    fi

    # 3. Create data directory
    mkdir -p "$DATA_DIR"

    # 4. Build the container
    info "Building container image..."
    podman build -t suse-assist -f "${APP_DIR}/Containerfile" "$APP_DIR"

    # 5. Run initial ingestion
    info "Ingesting documentation..."
    podman run --rm \
        -v "${DATA_DIR}:/app/data:Z" \
        -e "MODEL_TIER=${MODEL_TIER}" \
        suse-assist ingest --max-pages 50

    # 6. Install systemd service for container
    info "Installing systemd service (container mode)..."
    cat > /etc/systemd/system/suse-assist.service <<EOF
[Unit]
Description=openSUSE AI Onboarding Assistant (Container)
After=network.target
Wants=network.target

[Service]
Type=simple
Restart=on-failure
RestartSec=10
ExecStartPre=-/usr/bin/podman stop suse-assist-web
ExecStartPre=-/usr/bin/podman rm suse-assist-web
ExecStart=/usr/bin/podman run --name suse-assist-web \\
    --rm \\
    -p 7860:7860 \\
    -v ${DATA_DIR}:/app/data:Z \\
    --memory=4g --cpus=4 \\
    suse-assist web --demo --port 7860
ExecStop=/usr/bin/podman stop suse-assist-web

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable suse-assist.service

    # 7. Start the service
    info "Starting suse-assist container service..."
    systemctl start suse-assist.service

    info "=== Container deployment complete ==="
    info "Web UI: http://$(hostname -I | awk '{print $1}'):7860"
    info "Check status: systemctl status suse-assist"
    info "View logs: journalctl -u suse-assist -f"
}

# ── Main ──────────────────────────────────────────────────────────────────────
require_root
check_leap

info "Deploy mode: ${DEPLOY_MODE}"
info "Model tier:  ${MODEL_TIER}"
echo

case "$DEPLOY_MODE" in
    native)    deploy_native ;;
    container) deploy_container ;;
    *)         error "Unknown deploy mode: ${DEPLOY_MODE}" ;;
esac
