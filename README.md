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
git clone https://github.com/anujagrawal380/opensuse-leap-ai-guide.git
cd opensuse-leap-ai-guide

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

### Available Commands

```bash
suse-assist chat       # Interactive CLI chat (main experience)
suse-assist web        # Launch Gradio web UI in browser
suse-assist ingest     # Scrape docs and build vector store
suse-assist benchmark  # Run performance benchmarks
suse-assist sysinfo    # Show detected system context
suse-assist models recommend  # Recommend a local model tier based on RAM
```

All commands support `--demo` to simulate an openSUSE Leap environment on non-openSUSE machines.
`chat`, `web`, and `benchmark` also support `--model-tier auto|test|lite|standard|full|custom`.

## Project Structure

```
opensuse_ai/
├── __init__.py
├── config.py           # Centralized configuration (YAML + dataclasses)
├── scraper.py          # Documentation crawler for doc.opensuse.org
├── rag.py              # RAG pipeline: chunking, embedding, retrieval
├── assistant.py        # LLM engine: dual-mode (local llama-cpp / HF Inference API)
├── system_context.py   # OS-level context detection (zypper, systemd, etc.)
├── benchmark.py        # Performance measurement and reporting
├── cli.py              # Rich-powered CLI interface
└── web_ui.py           # Gradio web UI

tests/
├── test_config.py
├── test_scraper.py
├── test_system_context.py
└── test_rag.py

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
