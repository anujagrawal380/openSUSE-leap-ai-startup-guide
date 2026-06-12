#!/bin/bash
# kiwi image-config hook — runs inside the appliance root during the build.
# Unit files are delivered by the root/ overlay tree; here we just enable them.
set -euo pipefail

echo "Configuring openSUSE AI Onboarding appliance..."

# Core services
systemctl enable podman.socket || true
systemctl enable NetworkManager || true
systemctl enable firewalld || true
systemctl enable sshd || true

# Firstboot population of models + vector index into the suse-assist-data
# volume (networked firstboot only — see the offline caveat in appliance.kiwi).
systemctl enable suse-assist-firstboot.service || true

# The assistant service itself is generated from the Quadlet unit
# (/etc/containers/systemd/suse-assist.container) by podman-system-generator at
# boot, then started on multi-user.target.

echo "Appliance configuration complete."
