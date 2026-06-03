---
title: opensuse-leap-ai-startup-guide
emoji: 🦎
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: "6.9.0"
python_version: "3.13"
app_file: app.py
pinned: false
---

# openSUSE Leap AI Startup Guide

A locally-running, containerized AI assistant that helps new users get started with **openSUSE Leap**. It combines a **Small Language Model (SLM)** with a **Retrieval-Augmented Generation (RAG)** pipeline over official openSUSE documentation to provide accurate, context-aware guidance.

**[Try the live demo on HuggingFace Spaces →](https://huggingface.co/spaces/anujagawal/opensuse-leap-ai-guide)**

---

## Deployment Modes

The assistant supports two inference backends, configurable via `config.yaml` or environment:

| Mode | Backend | Use Case | Dependencies |
|------|---------|----------|--------------|
| **`local`** (default) | `llama-cpp-python` (Qwen3 family, GGUF) | CLI, containers, fully offline & private | `llama-cpp-python`, C++ toolchain |
| **`api`** | HuggingFace Inference API (Qwen3-235B-A22B) | HF Spaces, lightweight cloud deployment | `huggingface-hub` (no compilation) |

Both modes use the **same RAG pipeline** (LanceDB + MiniLM embeddings) for document retrieval — only the LLM generation step differs.

Set via `config.yaml`:
```yaml
model:
  inference_mode: "local"   # or "api"
  tier: "standard"          # auto-selects Qwen3-4B for local mode
  api_model_id: "Qwen/Qwen3-235B-A22B"  # used in api mode
```

Or in code (as done in `app.py` for HF Spaces):
```python
config.model.inference_mode = "api"
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          CLI (Rich) / Gradio Web UI                     │
│    suse-assist chat / web / ingest / benchmark          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │   Assistant  │  │ RAG Pipeline │  │ System Context│  │
│  │   Engine     │◄─┤  (LanceDB)   │  │  Detector     │  │
│  │  (dual mode) │  │              │  │               │  │
│  │              │  │  Embeddings  │  │  OS signals   │  │
│  │    local:    │  │  MiniLM-L6   │  │  zypper/YaST  │  │
│  │  Qwen3 (GGUF)│  │              │  │               │  │
│  │    api:      │  │              │  │               │  │ 
│  │  HF Inf. API │  │              │  │               │  │
│  └──────────────┘  └──────┬───────┘  └───────────────┘  │
│                           │                             │
│                    ┌──────┴───────┐                     │
│                    │  Doc Scraper │                     │
│                    │  (openSUSE   │                     │
│                    │   docs)      │                     │
│                    └──────────────┘                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│              Containerfile + compose.yaml               │
│           (OCI container, resource-constrained)         │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Qwen3 model family** | Apache 2.0, 1.7B/4B/8B ladder, non-thinking, strong multilingual, mature GGUF support |
| **Qwen3-4B-Instruct-2507 (default)** | ~2.5GB Q4, 256K native context, no `<think>` output, strong instruction following |
| **Dual inference mode** | `local` (llama-cpp-python) for offline/CLI, `api` (HF Inference API) for cloud/Spaces |
| **HF Inference API for Spaces** | Eliminates C++ compilation and large model downloads in cloud builds |
| **LanceDB** | Embedded vector DB, local filesystem, Apache 2.0, Lance/Arrow format, no daemon |
| **sentence-transformers (MiniLM)** | Fast, lightweight embeddings (~80MB model) |
| **System context detection** | Makes responses openSUSE-specific, not generic Linux |
| **Multi-stage Containerfile** | Small image, non-root user, security hardened |

## Quick Start

### Demo

![Demo Recording](demo.gif)

*Watch the assistant in action:* [View on asciinema](https://asciinema.org/a/O8ubkqKc6Ih6U6LC)

### Prerequisites
- Python 3.10+
- ~4 GB RAM available
- (Optional) Podman or Docker for containerized usage

### Local Development

```bash
# Clone and install
git clone https://github.com/anujagrawal380/openSUSE-leap-ai-startup-guide.git
cd openSUSE-leap-ai-startup-guide

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Step 1: Ingest openSUSE documentation (scrape + vectorize)
suse-assist ingest --max-pages 20    # small run for testing

# Step 2: Start interactive chat
suse-assist chat --demo              # --demo simulates openSUSE Leap context

# Step 3: Or launch the web UI
suse-assist web --demo               # opens browser at http://localhost:7860
```

### Container Usage

```bash
# Build the container
podman build -t opensuse-ai-assistant -f Containerfile .

# Or use compose
podman-compose up --build

# Run directly with resource limits
podman run -it --rm \
  --memory=4g --cpus=4 \
  -v model-data:/app/data \
  opensuse-ai-assistant chat --demo
```

### Containerized deployment on an openSUSE host (real system context)

The container base image is not openSUSE, so by default system context detection
reports the container, not the host. Mount the host root read-only and set
`SUSE_AI_HOST_ROOT` to detect the real host (distro, package manager, disk):

```bash
podman run -d --name opensuse-ai-guide --network=host \
  -v opensuse-ai-data:/app/data \
  -v /:/host:ro \
  -e SUSE_AI_HOST_ROOT=/host \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  opensuse-ai-assistant web --model-tier standard --port 7860
```

Notes:
- `HF_HUB_OFFLINE=1` runs fully offline once the GGUF model, the MiniLM embedding
  snapshot (`data/models/embeddings/`), and the vector store are present in the
  data volume. Build the store on a networked machine with
  `scripts/local_ingest.py` and copy `data/vectorstore/` over if the host has no
  internet access.
- Pending-update and failed-service detection require running `zypper`/`systemctl`
  on the host, so they are skipped in containerized mode; a native (non-container)
  install reports them.

### Documentation sources

The RAG index is built from official openSUSE documentation
(see `doc_sources` in `config.py`):

- openSUSE Leap Startup Guide (current = 15.6)
- openSUSE Leap Reference (current = 15.6)
- openSUSE Leap 16.0 Release Notes (the only 16.0-specific manual published so far)

### Available Commands

```bash
suse-assist chat       # Interactive CLI chat (main experience)
suse-assist web        # Launch Gradio web UI in browser
suse-assist ingest     # Scrape docs and build vector store
suse-assist benchmark  # Run performance benchmarks
suse-assist sysinfo    # Show detected system context
suse-assist models recommend  # Recommend a local model tier based on RAM
suse-assist mcp        # Run MCP server exposing tools over stdio
```

`chat`, `web`, and `benchmark` support `--demo` to simulate an openSUSE Leap environment on
non-openSUSE machines (`sysinfo` always shows the real detected context), and
`--model-tier auto|test|lite|standard|full|custom` to pick the local model.

### MCP server (Model Context Protocol)

`suse-assist mcp` runs an MCP server over stdio that exposes two tools to any
MCP-capable client (Claude Desktop, IDE agents, other LLM frontends):

- `get_system_context` — live detection of the openSUSE system state
  (distribution, kernel, filesystem + Snapper, GPU, network, firewall, …)
- `search_docs` — semantic search over the indexed openSUSE documentation

The assistant also works as an MCP **client** (`suse-assist mcp-tools`),
calling tools hosted by any external MCP server over stdio:

```bash
suse-assist mcp-tools list                                  # discover tools
suse-assist mcp-tools call get_system_context               # call one
suse-assist mcp-tools call search_docs --args '{"query": "snapper rollback"}'
suse-assist mcp-tools list --command "some-other-mcp-server"  # third-party server
```

Both directions require the optional extra: `pip install -e ".[mcp]"`.
Example Claude Desktop config entry:

```json
{
  "mcpServers": {
    "opensuse-onboarding": {
      "command": "suse-assist",
      "args": ["mcp"]
    }
  }
}
```

## Project Structure

```
opensuse_ai/
├── __init__.py
├── config.py           # Centralized configuration (YAML + dataclasses, model tiers, doc sources)
├── scraper.py          # Documentation crawler for doc.opensuse.org
├── rag.py              # RAG pipeline: chunking, dedup, embedding, retrieval
├── assistant.py        # LLM engine: dual-mode (local llama-cpp / HF Inference API)
├── system_context.py   # OS-level context detection (zypper, systemd, etc.)
├── benchmark.py        # Performance measurement and reporting
├── cli.py              # Rich-powered CLI interface
├── web_ui.py           # Gradio web UI
└── vectorstore/        # Vector store backend (LanceDB)
    ├── base.py         # Backend interface
    └── lance_backend.py

scripts/
└── local_ingest.py     # Build the vector store on a networked host (for offline VMs)

tests/
├── test_config.py
├── test_scraper.py
├── test_system_context.py
├── test_rag.py
└── test_vectorstore_backends.py

docs/
├── llm-comparison.md   # Original comparison of candidate LLMs
├── action-items/       # GSoC mentor action item breakdowns
├── evaluations/        # LLM/vector DB evaluation notes
└── integration/        # Agama/firstboot integration notes

Containerfile           # Multi-stage OCI container build
compose.yaml            # Compose file with resource constraints
config.yaml             # Default configuration (inference_mode, model, RAG settings)
requirements.txt        # HF Spaces dependencies (API mode, no llama-cpp-python)
pyproject.toml          # Python packaging (PEP 621, includes llama-cpp-python for local)
```


## Running Tests

```bash
pytest tests/ -v
```

## Guided Onboarding Topics

The assistant includes pre-built onboarding flows accessible via `topic <name>`:

- `welcome` — openSUSE overview
- `package_management` — zypper essentials
- `yast` — YaST system administration
- `repositories` — Repo management
- `desktop` — Desktop customization
- `firewall` — Firewall configuration
- `updates` — System updates
- `troubleshooting` — Common issues
- `community` — Getting involved

## Future Work

- **Installer integration**: Hook into YaST firstboot module or linuxrc
- **MCP integration**: Model Context Protocol servers for system context, docs, and onboarding flows
- **Snapper integration**: Context-aware rollback guidance
- **Offline RPM packaging**: Package as an openSUSE RPM with bundled model
- **Security hardening**: Sandboxed execution, prompt injection defenses
- **Telemetry**: Opt-in usage analytics for improving responses
