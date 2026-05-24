# Leap 16 Agama Integration PoC

Status: planned concrete PoC

The meeting notes elevate Agama from exploratory design to a working Leap 16 proof of concept. This document scopes the smallest useful demo.

## Goal

Demonstrate that an Agama-based Leap 16 installation can install or enable the openSUSE AI onboarding assistant during or immediately after installation.

## Integration Surface

Use Agama profile scripts first. Agama supports installation profiles with scripts for installation-time and post-installation tasks, and installs an `agama-scripts` service to run configured scripts.

References:

- Agama scripts reference: https://agama-project.github.io/docs/user/reference/profile/scripts
- openSUSE documentation index, Leap 16 Agama Installer Guide: https://doc.opensuse.org/

## PoC 1: Enable Assistant Service After Install

Assumption: `suse-assist` package or local RPM is available to the installed system.

Agama post-install script intent:

```bash
#!/bin/bash
set -euo pipefail

if command -v suse-assist >/dev/null 2>&1; then
    systemctl enable suse-assist.socket
fi
```

Acceptance criteria:

- Leap 16 install completes.
- Installed system boots successfully.
- `systemctl is-enabled suse-assist.socket` returns enabled when package is present.
- If the package is missing, installation does not fail.

## PoC 2: Install Local RPM Then Enable Socket

Assumption: local RPMs are provided through installation media, an HTTP repo, or a local directory mounted during the install.

Script intent:

```bash
#!/bin/bash
set -euo pipefail

if [ -d /run/agama/suse-assist-rpms ]; then
    zypper --non-interactive install /run/agama/suse-assist-rpms/*.rpm
    systemctl enable suse-assist.socket
fi
```

Acceptance criteria:

- RPM installation succeeds without user interaction.
- Service/socket is enabled in the installed system.
- Missing RPM directory is handled gracefully.

Security notes:

- Do not curl remote scripts into shell.
- Use a repository or local signed RPMs for real packaging.
- Do not enable network-facing services by default without explicit user/mentor sign-off.
- Prefer socket activation and localhost binding for first PoC.

## PoC 3: First-Boot User Choice

If mentors do not want the assistant enabled by default, install the package but leave activation to first boot:

```bash
#!/bin/bash
set -euo pipefail

if command -v suse-assist >/dev/null 2>&1; then
    systemctl enable suse-assist-firstboot.service
fi
```

Acceptance criteria:

- First boot prompts the user to opt in.
- The assistant does not consume resources until selected.

## VM Test Matrix

| Scenario | Expected Result |
|---|---|
| Leap 16 VM, package preinstalled | socket enabled |
| Leap 16 VM, package absent | install succeeds, no assistant |
| Leap 16 VM, local RPM path present | RPM installed and socket enabled |
| No network after install | assistant setup still explains offline model path |

## Deliverable for Mentors

- Agama profile/script file committed under `packaging/agama/` or `agama/`.
- Screenshot or terminal log showing Leap 16 installed system with the socket enabled.
- Short notes on what should move into RPM packaging versus Agama profile configuration.

## Open Questions

- Should Agama merely install/enable `suse-assist`, or should it show a native installer UI affordance?
- Should the first PoC bind only to localhost?
- Should the default post-install state be installed-but-disabled, socket-enabled, or firstboot-prompted?
