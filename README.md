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
│  │   Engine     │◄─┤  (ChromaDB)  │  │  Detector     │  │
│  │              │  │              │  │               │  │
│  │  TinyLlama   │  │  Embeddings  │  │  OS signals   │  │
│  │  1.1B (GGUF) │  │  MiniLM-L6   │  │  zypper/YaST  │  │
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
| **TinyLlama 1.1B (Q4 GGUF)** | ~700MB RAM, runs on laptops, good quality for guided Q&A |
| **llama-cpp-python** | CPU-first inference, no CUDA required, easy containerization |
| **ChromaDB** | Embedded vector DB, no external service needed |
| **sentence-transformers (MiniLM)** | Fast, lightweight embeddings (~80MB model) |
| **System context detection** | Makes responses openSUSE-specific, not generic Linux |
| **Multi-stage Containerfile** | Small image, non-root user, security hardened |

## Quick Start

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
```

All commands support `--demo` to simulate an openSUSE Leap environment on non-openSUSE machines.

## Project Structure

```
opensuse_ai/
├── __init__.py
├── config.py           # Centralized configuration (YAML + dataclasses)
├── scraper.py          # Documentation crawler for doc.opensuse.org
├── rag.py              # RAG pipeline: chunking, embedding, retrieval
├── assistant.py        # SLM engine with prompt engineering
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
└── llm-comparison.md   # Comparison of candidate LLMs

Containerfile           # Multi-stage OCI container build
compose.yaml            # Compose file with resource constraints
config.yaml             # Default configuration
pyproject.toml          # Python packaging (PEP 621)
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
- **Model upgrades**: Evaluate Phi-3.5 Mini, Qwen2.5 3B, Mistral 7B (see [docs/llm-comparison.md](docs/llm-comparison.md))
- **Snapper integration**: Context-aware rollback guidance
- **Offline RPM packaging**: Package as an openSUSE RPM with bundled model
- **Security hardening**: Sandboxed execution, prompt injection defenses
- **Telemetry**: Opt-in usage analytics for improving responses

