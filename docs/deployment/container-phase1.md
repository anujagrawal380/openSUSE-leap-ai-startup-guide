# Phase 1 Container Deployment

Goal: make the current VM demo reproducible as an openSUSE-native container
before doing full native RPM packaging of the ML dependency stack.

## Runtime Shape

- Container base: `registry.opensuse.org/opensuse/bci/python:3.11`
- Runtime: Podman
- Assistant service: `suse-assist web`
- Persistent data: named volume mounted at `/app/data`
- Host context: host root mounted read-only at `/host`
- Public web UI: chosen host port, default `7860`

The container intentionally does not bake in GGUF model files or the LanceDB
index. Those live in the data volume so image rebuilds stay small and the same
runtime can support both networked and offline provisioning.

## Current Image

Temporary public image:

```bash
ghcr.io/anujagrawal380/opensuse-leap-ai-startup-guide:latest
```

Target Phase 1 image:

```bash
registry.opensuse.org/<project>/suse-assist:latest
```

Replace `<project>` after the OBS project/package name is agreed with mentors.

## Run On Leap

```bash
scripts/deploy_container.sh pull
scripts/deploy_container.sh ingest
scripts/deploy_container.sh web -d
```

Open:

```text
http://localhost:7860/
```

To run the public demo shape used on the Leap VM:

```bash
SUSE_ASSIST_PORT=19000 scripts/deploy_container.sh web -d
```

To use a future `registry.opensuse.org` image:

```bash
SUSE_ASSIST_IMAGE=registry.opensuse.org/<project>/suse-assist:latest \
  scripts/deploy_container.sh web -d
```

## Verify

```bash
scripts/deploy_container.sh status
curl -I http://localhost:7860/
podman logs --tail 80 suse-assist
```

Expected logs include:

```text
Opened existing LanceDB table 'opensuse_docs'
Using cached model at data/models/...
Model loaded successfully.
```

## Offline VM Testing

The current Leap 16.0 stage VM is useful for runtime validation, but not for
fresh image builds or registry pulls because outbound internet is blocked.

Validated on 2026-06-15:

```bash
SUSE_ASSIST_IMAGE=localhost/opensuse-ai-assistant:patched \
SUSE_ASSIST_CONTAINER=suse-assist-phase1-test \
SUSE_ASSIST_DATA_VOLUME=opensuse-ai-data \
SUSE_ASSIST_PORT=19001 \
SUSE_ASSIST_MODEL_TIER=test \
  /tmp/suse-assist-deploy-container-test.sh web -d
```

Result:

```text
Opened existing LanceDB table 'opensuse_docs' (1982 rows)
Using cached model at data/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
Model loaded successfully.
http://stage3.opensuse.org:19001/ -> HTTP/1.1 200 OK
```

The live demo on `http://stage3.opensuse.org:19000/` remained running during
the test.

Fresh BCI build/pull is blocked on that VM:

```text
podman pull registry.opensuse.org/opensuse/bci/python:3.11
-> i/o timeout reaching registry.opensuse.org:443
```

So the Phase 1 test split is:

- Build/publish image on OBS, GitHub Actions, or another networked openSUSE host.
- Transfer/pull the finished image to the VM only if network access is available,
  or stage it with `podman save` / `podman load`.
- Validate runtime on the VM using a staged image plus the existing
  `opensuse-ai-data` volume.

## Transfer Image To Offline VM

Yes: the container image can be built on a networked machine, transferred over
SSH, and loaded into Podman on the offline VM.

On the networked builder:

```bash
podman build -t suse-assist:bci-phase1 -f Containerfile .
scripts/export_container_image.sh suse-assist:bci-phase1 suse-assist-bci-phase1
ARCHIVE="$(find . -maxdepth 1 -type f -name 'suse-assist-bci-phase1.tar*' ! -name '*.sha256' -print -quit)"
scp "${ARCHIVE}" "${ARCHIVE}.sha256" opensuse-gsoc-vm:/var/tmp/
```

On the offline VM:

```bash
ssh opensuse-gsoc-vm '
  ARCHIVE="$(find /var/tmp -maxdepth 1 -type f -name "suse-assist-bci-phase1.tar*" ! -name "*.sha256" -print -quit)" &&
  /tmp/load_container_image.sh "${ARCHIVE}" &&
  podman images | grep suse-assist
'
```

Copy the helper first if it is not already present:

```bash
scp scripts/load_container_image.sh opensuse-gsoc-vm:/tmp/
```

Then run the transferred image without touching the live demo:

```bash
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_IMAGE=suse-assist:bci-phase1 \
  SUSE_ASSIST_CONTAINER=suse-assist-bci-test \
  SUSE_ASSIST_DATA_VOLUME=opensuse-ai-data \
  SUSE_ASSIST_PORT=19001 \
  SUSE_ASSIST_MODEL_TIER=test \
    /tmp/suse-assist-deploy-container-test.sh web -d
'
```

Expected check:

```bash
curl -I http://stage3.opensuse.org:19001/
```

After validation:

```bash
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_CONTAINER=suse-assist-bci-test \
    /tmp/suse-assist-deploy-container-test.sh stop
'
```

If `zstd` is unavailable on a builder, use `gzip` instead:

```bash
podman save suse-assist:bci-phase1 | gzip -9 > suse-assist-bci-phase1.tar.gz
```

## OBS Handoff

Phase 1 should publish the BCI-based container first. The RPM work can start
with small integration packages later:

- Quadlet unit
- desktop launcher
- firstboot/setup service
- optional model/index subpackages

Do not block Phase 1 on native RPM packaging for `llama-cpp-python`, LanceDB,
Torch, or sentence-transformers. That remains the correct long-term path, but
it is larger than the deployable product milestone.
