# OBS Container Handoff

This folder documents the Phase 1 OBS target: build the existing BCI-based
container in Open Build Service and publish it through `registry.opensuse.org`.

## Staging Project

OBS project:

```text
home:anujagrawal:suse-assist
```

Build package:

```text
suse-assist-image
```

Repository:

```text
containerfile / x86_64
```

Target image reference after a successful build:

```text
registry.opensuse.org/home/anujagrawal/suse-assist/images/suse-assist:latest
```

This is intentionally in the user home namespace for the first staging build.
After it builds cleanly and the OEM image consumes it, mentors can decide the
official openSUSE project.

## Source Inputs

Use the repository root `Containerfile`. It already builds from:

```text
registry.opensuse.org/opensuse/bci/python:3.11
```

The image excludes models and the vector index. Those are runtime data mounted
at `/app/data`.

## Runtime Contract

The image must support:

```bash
suse-assist ingest
suse-assist web --model-tier standard --port 7860
suse-assist chat --demo --model-tier test
```

Required volume:

```text
/app/data
```

Optional host context mount:

```text
/:/host:ro
SUSE_AI_HOST_ROOT=/host
```

## Local Build Smoke Test

```bash
podman build -t suse-assist:phase1 -f Containerfile .
podman run --rm -it -v suse-assist-data:/app/data suse-assist:phase1 chat --demo --model-tier test
```

## Current OBS State

The project/package exist on OBS and the container build is recognized.

Current blocker:

```text
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch==2.4.1+cpu"
ERROR: Temporary failure in name resolution
ERROR: No matching distribution found for torch==2.4.1+cpu
```

That confirms the expected OBS constraint: the build runs in a network-isolated
environment. Next options:

- vendor the required wheels into the OBS package as a fast staging path
- package the Python/ML dependencies as RPMs for the correct long-term path
- keep GitHub Actions as the networked image builder until OBS dependency
  packaging is ready

## After Registry Publication

After OBS succeeds, update these files from GHCR to `registry.opensuse.org`:

- `deploy/oem/root/etc/containers/systemd/suse-assist.container`
- `deploy/oem/root/etc/systemd/system/suse-assist-firstboot.service`
- `docs/deployment/container-phase1.md`

Keep GHCR documented only as a temporary fallback until the OBS image is live.
