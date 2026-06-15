# Phase 1 Test Log

## 2026-06-15 — Leap 16 Stage VM

Host:

```text
stage3.opensuse.org:22019
openSUSE Leap 16.0
```

Live demo before test:

```text
http://stage3.opensuse.org:19000/ -> HTTP/1.1 200 OK
container: opensuse-ai-guide
image: localhost/opensuse-ai-assistant:patched
```

Runtime smoke test:

```bash
scp scripts/deploy_container.sh opensuse-gsoc-vm:/tmp/suse-assist-deploy-container-test.sh
ssh opensuse-gsoc-vm 'chmod +x /tmp/suse-assist-deploy-container-test.sh'
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_IMAGE=localhost/opensuse-ai-assistant:patched \
  SUSE_ASSIST_CONTAINER=suse-assist-phase1-test \
  SUSE_ASSIST_DATA_VOLUME=opensuse-ai-data \
  SUSE_ASSIST_PORT=19001 \
  SUSE_ASSIST_MODEL_TIER=test \
    /tmp/suse-assist-deploy-container-test.sh web -d
'
```

Result:

```text
Opened existing LanceDB table 'opensuse_docs' (1982 rows)
Using cached model at data/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
Model loaded successfully.
http://127.0.0.1:19001/ -> HTTP/1.1 200 OK
http://stage3.opensuse.org:19001/ -> HTTP/1.1 200 OK
```

Cleanup:

```bash
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_CONTAINER=suse-assist-phase1-test \
    /tmp/suse-assist-deploy-container-test.sh stop
'
```

Post-test:

```text
Only opensuse-ai-guide remained running.
http://stage3.opensuse.org:19000/ -> HTTP/1.1 200 OK
```

Build/pull test:

```bash
ssh opensuse-gsoc-vm 'timeout 60 podman pull registry.opensuse.org/opensuse/bci/python:3.11'
```

Result:

```text
pinging container registry registry.opensuse.org:
Get "https://registry.opensuse.org/v2/": dial tcp 195.135.223.221:443: i/o timeout
```

Conclusion:

- The VM is valid for offline runtime tests.
- The VM is not valid for fresh image builds or registry-pull tests.
- Fresh BCI image build must happen on OBS, GitHub Actions, or another networked
  openSUSE host.

## 2026-06-16 — BCI Image Artifact Loaded On Offline VM

Builder:

```text
GitHub Actions workflow_dispatch
run: 27565292034
branch: phase1-container-artifact-test
```

Build result:

```text
Build image archive: success
Save image archive: success
Compress and checksum archive: success
Upload image archive: success
artifact: suse-assist-bci-phase1.tar.zst
artifact size after download: 422 MB
```

The workflow deploy step failed after artifact upload, but the archive was
successfully transferred to the VM:

```text
/var/tmp/suse-assist-bci-phase1.tar.zst       422 MB
/var/tmp/suse-assist-bci-phase1.tar.zst.sha256
```

Manual load on the offline VM:

```bash
ssh opensuse-gsoc-vm '
  cd /var/tmp &&
  sha256sum -c suse-assist-bci-phase1.tar.zst.sha256 &&
  /var/tmp/load_container_image.sh /var/tmp/suse-assist-bci-phase1.tar.zst
'
```

Result:

```text
suse-assist-bci-phase1.tar.zst: OK
Loaded image: docker.io/library/suse-assist:bci-phase1
image size: 2.28 GB
```

Runtime smoke test:

```bash
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_IMAGE=docker.io/library/suse-assist:bci-phase1 \
  SUSE_ASSIST_CONTAINER=suse-assist-bci-test \
  SUSE_ASSIST_DATA_VOLUME=opensuse-ai-data \
  SUSE_ASSIST_PORT=19001 \
  SUSE_ASSIST_MODEL_TIER=test \
    /var/tmp/deploy_container.sh web -d
'
```

Result:

```text
Opened existing LanceDB table 'opensuse_docs' (1982 rows)
Using cached model at data/models/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
Model loaded successfully.
http://127.0.0.1:19001/ -> HTTP/1.1 200 OK
http://stage3.opensuse.org:19001/ -> HTTP/1.1 200 OK
```

Cleanup:

```bash
ssh opensuse-gsoc-vm '
  SUSE_ASSIST_CONTAINER=suse-assist-bci-test /var/tmp/deploy_container.sh stop
'
```

Post-test:

```text
Only opensuse-ai-guide remained running.
Temporary GitHub Actions SSH key removed from VM authorized_keys.
Temporary GitHub secret STAGE3_TMP_SSH_KEY deleted.
```
