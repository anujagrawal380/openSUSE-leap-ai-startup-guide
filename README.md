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

> A private, offline AI assistant that helps people get started with **openSUSE Leap** —
> answering setup and troubleshooting questions in plain language, grounded in the
> official openSUSE documentation and aware of the user's actual system.

*Google Summer of Code 2026 · openSUSE · "AI-Powered Onboarding Experience for openSUSE Linux Distributions"*

**[Try the live demo on HuggingFace Spaces →](https://huggingface.co/spaces/anujagawal/opensuse-leap-ai-guide)**

---

## Why this exists

New openSUSE users — especially people arriving from other distributions — hit the
same wall: *"How do I install software? Add a repo? Open a firewall port? Roll back a
bad update? What is YaST?"* The answers exist in the documentation and wiki, but they're
scattered, and a brand-new user doesn't yet know the openSUSE vocabulary (`zypper`, YaST,
Snapper, `firewalld`) to find them.

This project puts a knowledgeable openSUSE guide **on the user's own machine** that:

- **Answers in plain language**, grounded in official docs (no hallucinated commands).
- **Knows the user's system** — it reads real state (distribution, filesystem + Snapper,
  GPU, network, firewall) and tailors answers to *this* machine, not generic Linux.
- **Runs fully offline and private** — a small local model + local vector search, no cloud
  calls, no data leaving the box. Critical for a tool meant to ship inside the distro.

## The endgoal

A newcomer installs openSUSE Leap and, from first boot, has a built-in assistant that walks
them through getting productive — eventually integrated into the installer (Agama) /
firstboot and shipped as an openSUSE package. This repository is the working
implementation and engineering groundwork toward that vision.

## Project status

**Working assistant**, validated end-to-end on an openSUSE Leap 16.0 VM (CPU-only,
fully offline):

- ✅ Local SLM + RAG over official openSUSE docs (Startup, Reference, Leap 16.0 Release
  Notes, curated wiki SDB articles incl. NVIDIA troubleshooting)
- ✅ Real system-context detection (Btrfs/Snapper, GPU, network, firewall, locale, …)
- ✅ CLI + web UI, containerized, runs offline on the VM
- ✅ Hardware-based model tiers + an answer-quality evaluation suite (judged by a neutral
  external LLM — see [`docs/evaluations/`](docs/evaluations/))
- ✅ MCP server + client integration
- 🚧 **Next:** native systemd service, RPM/OBS packaging, installer/firstboot integration

See [`docs/`](docs/) for the design decisions, model/vector-DB evaluations, and integration
plans behind each of these. Roadmap detail at the [end of this README](#roadmap).

---

## Deployment Modes

The assistant supports two inference backends, configurable via `config.yaml` or environment:

| Mode | Backend | Use Case | Dependencies |
|------|---------|----------|--------------|
| **`local`** (default) | `llama-cpp-python` (Gemma 4 E4B default; Qwen3 tiers, GGUF) | CLI, containers, fully offline & private | `llama-cpp-python`, C++ toolchain |
| **`api`** | HuggingFace Inference API (Qwen3-235B-A22B) | HF Spaces, lightweight cloud deployment | `huggingface-hub` (no compilation) |

Both modes use the **same RAG pipeline** (LanceDB + MiniLM embeddings) for document retrieval — only the LLM generation step differs.

Set via `config.yaml`:
```yaml
model:
  inference_mode: "local"   # or "api"
  tier: "standard"          # Gemma 4 E4B for local mode (or "auto")
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
| **Gemma 4 E4B (standard/full default)** | Mentor-preferred; edge/effective-4B, ~4.9GB q4_0, needs llama-cpp ≥ 0.3.25. Qwen3 tiers remain benchmarkable via `EXTRA_MODELS` |
| **Qwen3 family (lite + baselines)** | Apache 2.0, non-thinking, strong multilingual; Qwen3-1.7B is the lite tier, Qwen3-4B/8B kept as benchmark baselines |
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
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=512m \
  --security-opt no-new-privileges --cap-drop=all \
  --memory=6g --cpus=4 --pids-limit=512 \
  opensuse-ai-assistant web --model-tier standard --port 7860
```

Notes:
- Use `opensuse-ai-data` as the persistent volume name for manual runs; OEM
  Quadlet uses `suse-assist-data`.
- Check runtime health with `podman ps --filter name=opensuse-ai-guide` and
  logs with `podman logs -f opensuse-ai-guide`. For OEM/systemd deployments,
  use `systemctl status suse-assist` and `journalctl -u suse-assist -f`.
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
- openSUSE Wiki SDB articles via the MediaWiki API (zypper usage, system
  upgrade, repositories, NVIDIA drivers, audio troubleshooting, …) — the wiki
  blocks HTML scraping, so these are fetched through `api.php`

Retrieval is plain vector search by default; set `rag.rerank: true` in
`config.yaml` to enable cross-encoder reranking (better relevance, slower,
needs the reranker model cached for offline machines).

Repeated chat/web prompts are cached by default in `data/prompt_cache.json`.
The cache key includes the normalized prompt plus model, RAG settings, and
detected system context, so changing those inputs generates a fresh answer.
Set `prompt_cache.enabled: false` in `config.yaml` to disable it.

### Available Commands

```bash
suse-assist chat       # Interactive CLI chat (main experience)
suse-assist web        # Launch Gradio web UI in browser
suse-assist ingest     # Scrape docs and build vector store
suse-assist benchmark  # Run performance benchmarks (latency/throughput)
suse-assist eval       # Compare models on answer quality + latency
suse-assist sysinfo    # Show detected system context
suse-assist doctor     # Check local models, vector store, cache, and web port
suse-assist bundle     # Export/import offline model + RAG runtime data
suse-assist setup      # First-run setup: model cache, docs ingest, doctor check
suse-assist setup native-service  # Render/install a native systemd web service
suse-assist models recommend  # Recommend a local model tier based on RAM
suse-assist mcp        # Run MCP server exposing tools over stdio
```

`chat`, `web`, and `benchmark` support `--demo` to simulate an openSUSE Leap environment on
non-openSUSE machines (`sysinfo` always shows the real detected context), and
`--model-tier auto|test|lite|standard|full|custom` to pick the local model.

### Quality evaluation

`suse-assist eval` compares models head-to-head on the same openSUSE question
set, scoring both **answer quality** and **latency** — fully offline:

- **Quality (1-5)**: a strong local model (default `--judge full` = Qwen3-8B)
  scores each answer against a gold reference and an expected-fact checklist.
- **Similarity (0-1)**: embedding cosine similarity between answer and gold
  reference (reuses the cached MiniLM model).

It runs in two phases — generate all answers per model (one resident at a
time), then load the judge once — so the memory-constrained VM never holds two
large models. Gold answers live in `opensuse_ai/eval_dataset.py`.

```bash
suse-assist eval --models standard,gemma3-4b --judge full
```

`gemma3-4b` (Google Gemma 3 4B) is registered as a benchmark rival to the
standard tier but kept out of the auto-selection ladder.

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
opensuse_ai/             # The Python package (installed as the `suse-assist` CLI)
├── config.py            # Config: model tiers, RAG params, doc sources (YAML + dataclasses)
├── scraper.py           # Doc ingestion: crawls doc.opensuse.org + MediaWiki API (wiki SDB)
├── rag.py               # RAG pipeline: chunk, dedup, embed, retrieve (+ optional reranker)
├── assistant.py         # LLM engine: dual-mode (local llama-cpp / HF Inference API)
├── prompt_cache.py      # Persistent response cache for repeated prompts
├── system_context.py    # OS-level context detection (distro, Btrfs/Snapper, GPU, network…)
├── cli.py               # Rich-powered CLI — the `suse-assist` entrypoint
├── web_ui.py            # Gradio web UI
├── benchmark.py         # Latency / throughput / memory benchmarking
├── eval_dataset.py      # Gold Q&A set for answer-quality evaluation
├── quality.py           # Quality scorers: embedding similarity + LLM judge (local or Gemini)
├── evaluation.py        # Eval orchestrator: generate answers per model, then judge
├── mcp_server.py        # MCP server — exposes system context + doc search as tools
├── mcp_client.py        # MCP client — calls tools on external MCP servers
└── vectorstore/         # Pluggable vector store backend
    ├── base.py          # Backend interface
    └── lance_backend.py # LanceDB implementation

scripts/local_ingest.py  # Build the vector store on a networked host (for offline VMs)
scripts/demo_smoke_test.sh # Prepared-runtime smoke test: CLI, RAG, web endpoint
deploy/                  # systemd unit + Leap VM setup script for native deployment
tests/                   # pytest suite (config, RAG, system context, eval, MCP, …)

docs/                    # Project narrative, decisions, evaluations — see docs/README.md
├── README.md            # Index / map of all documentation
├── gsoc-proposal.md     # The accepted GSoC proposal (full project plan)
├── evaluations/         # Model & vector-DB decisions and benchmark reports
├── integration/         # Installer (Agama) / firstboot integration design
└── action-items/        # Mentor action-item breakdowns

Containerfile            # Multi-stage OCI container build
compose.yaml             # Compose file with resource constraints
config.yaml              # Default configuration (inference_mode, model tier, RAG settings)
app.py                   # HuggingFace Spaces entrypoint (api mode)
requirements.txt         # HF Spaces deps (API mode, no llama-cpp-python)
pyproject.toml           # Python packaging (PEP 621; `.[mcp]` extra for MCP support)
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

## Roadmap

The path from today's working assistant to one shipped inside openSUSE:

**Phase 1 — Core assistant (done)**
- ✅ Local SLM + RAG over official openSUSE docs & wiki; offline & private
- ✅ System-context awareness (Btrfs/Snapper, GPU, network, firewall, locale)
- ✅ CLI + web UI, containerized, validated on a Leap 16.0 VM
- ✅ Model tiers + answer-quality evaluation suite (neutral external-LLM judge)
- ✅ MCP server + client integration

**Phase 2 — Productionization (in progress)**
- 🚧 Native systemd service (removes the container host-mount crutch)
- 🚧 RPM packaging via OBS — installable with `zypper`
- 🚧 Prompt-injection defenses and output sanitization hardening

**Phase 3 — Distro integration (the endgoal)**
- ⬜ Installer (Agama) / `jeos-firstboot` hook — onboarding from first boot
- ⬜ OEM-image-based deployment (preloaded assistant)
- ⬜ Deeper Snapper integration — context-aware rollback guidance

See [`docs/integration/`](docs/integration/) for the integration design notes.

## Contributing

This is an openSUSE GSoC 2026 project and community input is very welcome. Good starting
points: read [`docs/README.md`](docs/README.md) for the project map, try the
[Quick Start](#quick-start), and open an issue with ideas, doc sources to add, or feedback
on answer quality.
