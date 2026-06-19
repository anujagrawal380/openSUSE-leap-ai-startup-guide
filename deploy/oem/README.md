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
| `root/etc/systemd/system/suse-assist-firstboot.service` | one-shot firstboot: populate the data volume before the web service starts |
| `root/usr/libexec/suse-assist-firstboot` | firstboot helper: import an offline bundle if present, otherwise pull + ingest |

Once the assistant ships as an RPM (roadmap Phase 2), swap the container for
`<package>suse-assist</package>` in `appliance.kiwi` and the native systemd unit
in [`../suse-assist.service`](../suse-assist.service).

## Runtime ownership

The container runs as a non-root `suseai` user with stable UID/GID `999:999`.
The Quadlet unit sets the same `--user=999:999` explicitly so the
`suse-assist-data` volume stays writable even if the BCI base image changes its
system-user allocation behavior. If an existing volume was created by an older
image with different ownership, fix the volume owner or run a one-time migration
before enabling the service.

## Building

Not buildable on the offline VM or on macOS — needs kiwi + openSUSE repos.
On OBS (preferred) or a networked openSUSE host:

```bash
kiwi-ng --profile Leap16 system build \
    --description deploy/oem \
    --target-dir /tmp/oem-build
```

## Offline runtime bundle

The container deliberately excludes the ~5 GB model + LanceDB index (they live
in the `suse-assist-data` volume). Firstboot now supports both paths:

- If `/usr/share/suse-assist/offline-bundle.tar.gz` exists, it runs
  `suse-assist bundle import` into the Podman volume.
- If no bundle exists, it falls back to the current networked prototype:
  pull the container image and run `suse-assist ingest`.

Create the bundle on a prepared machine or VM:

```bash
suse-assist bundle export --model-tier standard \
  --output offline-bundle.tar.gz
```

A fully offline OEM image must include both the container image and
`offline-bundle.tar.gz` in the KIWI overlay or in RPM payloads. The firstboot
logic is ready for that layout; the remaining policy decision is where the
multi-GB bundle should be published and how it should be licensed/rebuilt.
