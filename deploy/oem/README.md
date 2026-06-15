# OEM image — openSUSE Leap with the AI assistant preinstalled

Builds a Leap OEM appliance that ships the onboarding assistant and runs it
from boot. The endgoal artifact: a user installs the image and has a built-in,
system-aware openSUSE guide immediately.

## Approach

The assistant is not yet an RPM, so the appliance runs it as a **container via
a Podman Quadlet unit** instead of a packaged binary:

| File | Role |
|------|------|
| `appliance.kiwi` | kiwi OEM image description (Leap base + podman + tools) |
| `config.sh` | image-config hook — enables services |
| `root/` | overlay tree copied into the image root |
| `root/etc/containers/systemd/suse-assist.container` | Quadlet unit — runs the published container as a systemd service |
| `root/etc/systemd/system/suse-assist-firstboot.service` | one-shot firstboot: pull image + build the doc index into the data volume |

Phase 1 keeps the assistant containerized and moves the image from GHCR to
`registry.opensuse.org` via OBS. Once the assistant ships as a native RPM
(later roadmap item), swap the container for `<package>suse-assist</package>` in
`appliance.kiwi` and the native systemd unit in
[`../suse-assist.service`](../suse-assist.service).

## Building

Not buildable on the offline VM or on macOS — needs kiwi + openSUSE repos.
On OBS (preferred) or a networked openSUSE host:

```bash
kiwi-ng --profile Leap16 system build \
    --description deploy/oem \
    --target-dir /tmp/oem-build
```

## Open item — offline models

The container deliberately excludes the ~5 GB model + LanceDB index (they live
in the `suse-assist-data` volume). `suse-assist-firstboot.service` populates
them over the network on first boot.

A **fully offline** OEM image must instead bundle that content into the image
(overlay the volume directory, or ship the model in an RPM). This bundle-vs-fetch
decision is the main blocker for a true offline appliance and is tracked on the
project roadmap.
