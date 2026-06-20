# OBS Registry Image and Leap VM Validation

Date: 2026-06-19

This file records the completed OBS-to-VM validation so we do not repeat the
same transfer/load/smoke-test work unless the image or runtime changes.

## Current Published Image

OBS package:

```text
home:anujagrawal:suse-assist/suse-assist-image
```

Registry image:

```text
registry.opensuse.org/home/anujagrawal/suse-assist/images/opensuse/suse-assist:latest
```

Validated OBS tag:

```text
10.3
```

Loaded VM image ID:

```text
1d04862c45ea61d226dbee80cfbde06953294a868b9bebfd5d7d7a4d889a4f33
```

Registry tag check:

```bash
curl -fsSL \
  https://registry.opensuse.org/v2/home/anujagrawal/suse-assist/images/opensuse/suse-assist/tags/list
```

Expected tags include:

```text
latest
10.3
```

## VM State

VM:

```text
ssh opensuse-gsoc-vm
```

Public demo:

```text
http://stage3.opensuse.org:19000/
```

The public demo container now runs the OBS-built image:

```bash
podman inspect opensuse-ai-guide --format '{{.ImageName}} {{.Image}}'
```

Expected:

```text
localhost/opensuse/suse-assist:latest 1d04862c45ea61d226dbee80cfbde06953294a868b9bebfd5d7d7a4d889a4f33
```

Runtime shape:

```bash
podman run -d \
  --name opensuse-ai-guide \
  --network=host \
  --user=999:999 \
  -v opensuse-ai-data:/app/data \
  -v /:/host:ro \
  -e SUSE_AI_HOST_ROOT=/host \
  -e HF_HUB_OFFLINE=1 \
  -e TRANSFORMERS_OFFLINE=1 \
  localhost/opensuse/suse-assist:latest \
  web --model-tier standard --port 19000
```

The existing VM data volume is:

```text
opensuse-ai-data
```

Validated contents:

- all six GGUF model files are present
- `gemma-4-E4B_q4_0-it.gguf` is present for the standard tier
- LanceDB vector store is present with 1982 chunks
- MiniLM embedding cache is present
- host context mount works with `/:/host:ro` and `SUSE_AI_HOST_ROOT=/host`

## Completed Validation

Completed on the offline Leap 16.0 VM without using VM outbound internet:

1. Downloaded the OBS-built image tar from OBS:

   ```text
   suse-assist-0.1.0.x86_64-10.3.tar
   ```

2. Copied the archive to the VM over SSH.
3. Verified the archive checksum on the VM.
4. Loaded it with Podman:

   ```text
   localhost/opensuse/suse-assist:latest
   localhost/opensuse/suse-assist:10.3
   ```

5. Ran `suse-assist doctor` against `opensuse-ai-data`.
6. Started the web UI from the OBS image and verified:

   ```text
   http://127.0.0.1:19001/
   http://stage3.opensuse.org:19001/
   ```

7. Ran CLI inference with the test model.
8. Ran CLI inference with the standard Gemma 4 E4B model:

   ```text
   69.8s for "What is zypper?"
   ```

9. Switched the public demo on port `19000` from the older local image to the
   OBS image and verified:

   ```text
   http://stage3.opensuse.org:19000/
   ```

## Recovery Commands

Use these only if the VM image needs to be restored from OBS again.

Download the tar from OBS on a connected machine:

```bash
mkdir -p /tmp/suse-assist-obs-image
osc -A https://api.opensuse.org getbinaries \
  home:anujagrawal:suse-assist suse-assist-image images x86_64 \
  suse-assist-0.1.0.x86_64-10.3.tar \
  -d /tmp/suse-assist-obs-image
```

Compress, checksum, and transfer:

```bash
cd /tmp/suse-assist-obs-image
sha256sum suse-assist-0.1.0.x86_64-10.3.tar > suse-assist-0.1.0.x86_64-10.3.tar.sha256
gzip -k -f suse-assist-0.1.0.x86_64-10.3.tar
sha256sum suse-assist-0.1.0.x86_64-10.3.tar.gz > suse-assist-0.1.0.x86_64-10.3.tar.gz.sha256
scp suse-assist-0.1.0.x86_64-10.3.tar.gz \
  suse-assist-0.1.0.x86_64-10.3.tar.gz.sha256 \
  opensuse-gsoc-vm:/root/
```

Verify and load on the VM:

```bash
ssh opensuse-gsoc-vm '
  cd /root &&
  sha256sum -c suse-assist-0.1.0.x86_64-10.3.tar.gz.sha256 &&
  gzip -t suse-assist-0.1.0.x86_64-10.3.tar.gz &&
  gzip -dc suse-assist-0.1.0.x86_64-10.3.tar.gz | podman load
'
```

Switch the public demo to the loaded OBS image:

```bash
ssh opensuse-gsoc-vm '
  podman rm -f opensuse-ai-guide || true
  podman run -d \
    --name opensuse-ai-guide \
    --network=host \
    --user=999:999 \
    -v opensuse-ai-data:/app/data \
    -v /:/host:ro \
    -e SUSE_AI_HOST_ROOT=/host \
    -e HF_HUB_OFFLINE=1 \
    -e TRANSFORMERS_OFFLINE=1 \
    localhost/opensuse/suse-assist:latest \
    web --model-tier standard --port 19000
'
```

Verify:

```bash
curl -fsSL http://stage3.opensuse.org:19000/ | wc -c
ssh opensuse-gsoc-vm 'podman logs --tail=80 opensuse-ai-guide'
```

## Do Not Repeat Unless Needed

Do not redo the OBS image transfer/load/public-demo switch just to prove the path
again. Redo it only when:

- `suse-assist-image` gets a new OBS revision/tag that must be validated
- the VM image is removed or corrupted
- the runtime volume layout changes
- the public demo needs to move to a different port or model tier

Next work should focus on the remaining unresolved pieces:

- offline model/vectorstore bundle artifact and OEM firstboot import test
- mentor/community decision on vendored wheels vs proper RPM dependencies
- RPM-installed Leap test host validation
