# Vendored wheel OBS experiment

Purpose: prove whether OBS can build a container that installs Python wheels
from package sources instead of fetching from PyPI during the build.

## Smoke package

OBS package:

```text
home:anujagrawal:suse-assist/suse-assist-wheelhouse-smoke
```

What it contains:

- `Dockerfile`
- `wheelhouse.tar.gz`
- one small vendored wheel: `click-8.1.8-py3-none-any.whl`

Build mechanism:

```dockerfile
ADD wheelhouse.tar.gz /wheelhouse/
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-index --find-links=/wheelhouse click
```

Result on 2026-06-17:

```text
images        x86_64  succeeded
containerfile x86_64  succeeded
```

This proves the basic OBS/container mechanism works for vendored wheels.

## What this does not prove

The real assistant wheelhouse is much larger and riskier:

- `torch`
- `llama-cpp-python`
- `lancedb`
- `sentence-transformers`
- `transformers`
- `gradio`
- `mcp`

The next experiment should generate a full Linux x86_64 wheelhouse and upload it
to `suse-assist-image`, or to a separate staging package, then replace networked
`pip install` with:

```bash
pip install --no-index --find-links=/wheelhouse ".[mcp]"
```

If any dependency has no compatible wheel, it must either be built into the
wheelhouse ahead of time or packaged properly as an openSUSE RPM.
