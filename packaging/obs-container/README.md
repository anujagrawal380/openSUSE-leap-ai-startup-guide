# OBS Container Handoff

This folder documents the Phase 1 OBS target: build the existing BCI-based
container in Open Build Service and publish it through `registry.opensuse.org`.

## Proposed Package

Package name:

```text
suse-assist-container
```

Image name:

```text
registry.opensuse.org/<project>/suse-assist:latest
```

The exact OBS project should be confirmed with mentors. Likely candidates are a
GSoC/home project first, then the project used by the Leap 16 OEM image work.

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

## After Registry Publication

Update these files from GHCR to `registry.opensuse.org`:

- `deploy/oem/root/etc/containers/systemd/suse-assist.container`
- `deploy/oem/root/etc/systemd/system/suse-assist-firstboot.service`
- `docs/deployment/container-phase1.md`

Keep GHCR documented only as a temporary fallback until the OBS image is live.

