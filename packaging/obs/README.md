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
`Containerfile`. The image currently builds in normal networked CI, but an OBS
build is blocked by Python dependencies downloaded with `pip` during the build:

- `torch`
- `llama-cpp-python`
- `lancedb`
- `sentence-transformers` / `transformers`
- `gradio`
- `mcp`

OBS builds run in a clean build environment and should not fetch arbitrary PyPI
artifacts. Short-term options:

- vendor wheels into the OBS package as a prototype-only step
- split the image into an OBS-built base plus a later networked layer

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

Vendored-wheel smoke result:

- `home:anujagrawal:suse-assist/suse-assist-wheelhouse-smoke`
- `images/x86_64`: succeeded
- `containerfile/x86_64`: succeeded

See [`vendored-wheel-experiment.md`](vendored-wheel-experiment.md). Generate a
larger wheelhouse with:

```bash
scripts/build_obs_wheelhouse.sh
```

## Native RPM

The draft spec is in [`../rpm/suse-assist.spec`](../rpm/suse-assist.spec). It is
not ready for Factory submission because the core ML stack is not available as
openSUSE RPM dependencies yet.
