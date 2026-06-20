# OBS packaging notes

Current staging project:

```bash
osc -A https://api.opensuse.org ls home:anujagrawal:suse-assist
```

Current package:

```text
home:anujagrawal:suse-assist/suse-assist-image
```

Use this home project until mentors pick the final devel project.

## Container image

The first OBS target is the BCI-based container image from the repository
`Containerfile`. The staging package is:

```text
home:anujagrawal:suse-assist/suse-assist-image
```

The package now builds in OBS with a vendored CPython 3.11 wheelhouse:

```text
images/x86_64: succeeded
OBS package revision: 10
Published image tags: latest, 10.3
Image tar size: ~692 MB
Wheelhouse source size: ~467 MB
```

Published image:

```bash
podman pull registry.opensuse.org/home/anujagrawal/suse-assist/images/opensuse/suse-assist:latest
```

Validation status:

- registry tag `10.3` was downloaded from OBS as
  `suse-assist-0.1.0.x86_64-10.3.tar`
- the tar was copied to the offline Leap 16.0 VM over SSH, checksum-verified,
  and loaded with Podman
- loaded VM tags:
  - `localhost/opensuse/suse-assist:latest`
  - `localhost/opensuse/suse-assist:10.3`
- the image passed `suse-assist doctor`, web startup, test-tier CLI inference,
  and standard-tier Gemma 4 E4B CLI inference against the existing
  `opensuse-ai-data` volume
- the public demo at `http://stage3.opensuse.org:19000/` now runs from the OBS
  image

See
[`../../docs/deployment/obs-registry-vm-validation.md`](../../docs/deployment/obs-registry-vm-validation.md)
before redoing any image transfer or VM validation work.

The build installs the Python stack offline with:

```bash
pip install --no-index --find-links=/wheelhouse "torch==2.4.1+cpu"
pip install --no-index --find-links=/wheelhouse ".[mcp]"
```

OBS builds run in a clean build environment and should not fetch arbitrary PyPI
artifacts. The vendored wheelhouse is the short-term prototype path. The
wheelhouse includes the large packages that blocked the networked build:

- `torch==2.4.1+cpu`
- `llama-cpp-python` built locally as a CPython 3.11 Linux wheel
- `lancedb`
- `sentence-transformers` / `transformers`
- `gradio`
- `mcp`
- build-system wheels: `setuptools`, `wheel`

Long-term option:

- package the missing Python dependencies as openSUSE RPMs, then build the
  container from RPM packages only

Useful commands:

```bash
osc -A https://api.opensuse.org co home:anujagrawal:suse-assist suse-assist-image
cd home:anujagrawal:suse-assist/suse-assist-image
cp /path/to/repo/Containerfile Dockerfile
osc add Dockerfile
osc commit -m "Update suse-assist BCI container"
osc build openSUSE_Tumbleweed x86_64
```

Registry publishing is enabled for the home project. If the registry tag has
not appeared yet, wait for the publisher and check:

```bash
curl https://registry.opensuse.org/v2/home/anujagrawal/suse-assist/images/opensuse/suse-assist/tags/list
```

Vendored-wheel smoke result:

- `home:anujagrawal:suse-assist/suse-assist-wheelhouse-smoke`
- `images/x86_64`: succeeded
- registry image: `home/anujagrawal/suse-assist/images/suse-assist-wheelhouse-smoke`
- purpose: small proof that OBS can install from a vendored wheelhouse with
  `pip --no-index --find-links=/wheelhouse`

See [`vendored-wheel-experiment.md`](vendored-wheel-experiment.md). Generate a
larger wheelhouse with:

```bash
scripts/build_obs_wheelhouse.sh
```

Note: the current real wheelhouse was generated with a CPython 3.11 `uv` venv
because the local Ubuntu environment did not have `python3-pip`/`ensurepip`.
`llama-cpp-python` had no compatible prebuilt wheel, so it was built locally
with:

```bash
CMAKE_ARGS="-DGGML_NATIVE=OFF -DGGML_OPENMP=ON" FORCE_CMAKE=1 \
  python -m pip wheel --wheel-dir /tmp/suse-assist-built-wheels \
  "llama-cpp-python>=0.2.56"
```

## Native RPM

The draft spec is in [`../rpm/suse-assist.spec`](../rpm/suse-assist.spec). It is
not ready for Factory submission because the core ML stack is not available as
openSUSE RPM dependencies yet.
