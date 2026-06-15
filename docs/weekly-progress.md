# Weekly Progress — AI-Powered Onboarding for openSUSE

Stand-up style log for weekly meetings. Newest week first.

---

## Week of Jun 15, 2026

**Done / in progress**
- Confirmed the Leap 16.0 VM is reachable with a dedicated GSoC SSH key.
- Confirmed the public demo is running at `http://stage3.opensuse.org:19000/` from the `opensuse-ai-guide` Podman container.
- Confirmed the VM data volume has six local GGUF models plus the MiniLM embedding cache.
- Started Phase 1 productionization: openSUSE-native container deployment path before full native RPM packaging.

**Next**
- Publish the BCI-based container via OBS to `registry.opensuse.org`.
- Replace GHCR references in the OEM Quadlet/firstboot units once the OBS image is live.
- Build the Leap 16 OEM image around the container service.
- Decide whether the first offline OEM image bundles Qwen3-4B + LanceDB index or keeps networked firstboot fetch as the first milestone.

**Blockers / decisions needed**
- OBS project/package name for the container image.
- Whether a large offline AI OEM image that includes a ~2.5 GB GGUF model is acceptable.
- Whether Phase 1 should ship only the container image or also a small RPM containing the Quadlet + launcher.

---

## Week of Jun 8, 2026

**Done**
- Built an **answer-quality evaluation suite** (`suse-assist eval`): generates answers per model on the VM, then scores them on quality + latency. Two-phase so only one model is resident at a time.
- Made the judge **unbiased** — replaced the local Qwen3-8B judge (graded Qwen with Qwen) with a **neutral external LLM (Google Gemini)**. Decoupled generation (on-VM, offline) from judging (off-VM), with batched scoring (one API call per model, not per answer) to stay under rate limits.
- Benchmarked **all models incl. Gemma 3 4B and Gemma 4 E4B** under the neutral judge. Ranking: Qwen3-4B 4.88, Qwen3-8B 4.75, Gemma 4 E4B 4.62, Gemma 3 4B 4.50, Qwen3-1.7B 4.00, TinyLlama 2.62. Report in `docs/evaluations/all-models-quality-eval-gemini-judge.md`.
- Added **NVIDIA troubleshooting** docs to the RAG index (driver install, SUSE Prime/Optimus, general troubleshooting) — a common user pain point.
- Switched the **standard/full tiers to Gemma 4 E4B** (mentor preference); Qwen3 kept as benchmark baselines. Needs llama-cpp ≥ 0.3.25.
- **Repo legibility pass** for community traction: README reframed around the project's purpose, endgoal, status, and a phased roadmap; added a `docs/` index; removed superseded reports; dropped "proof-of-concept" framing.
- **Published a container image** to ghcr.io via a GitHub Actions workflow (models excluded — mount as a volume) to enable OEM deployment prototyping.

**Next**
- Rebase the container onto an **openSUSE base** (SUSE BCI) and build/publish via **OBS → registry.opensuse.org** (the current GitHub image is Debian-based, not openSUSE-native).
- Native **systemd service**; **RPM packaging** via OBS.
- Decide **model bundling** strategy for an offline OEM image (bundle vs firstboot-fetch).

**Blockers**
- **Repo transfer to the openSUSE org** — needed so the project lives under openSUSE (not a personal account) for community ownership, CI, and registry/OBS integration. Pending org decision/access.
- (Gemini free-tier daily quota throttled mid-week; worked around with batched calls + a fresh key.)

---

## Week of Jun 1, 2026

**Done**
- Migrated to Qwen3 model family with 4 hardware tiers (test/lite/standard/full); standard = Qwen3-4B-Instruct
- Deployed end-to-end on the mentor-provided Leap 16.0 VM, fully offline (models, embeddings, vector store all cached); public demo at http://stage3.opensuse.org:19000/
- Real host system context from inside the container (`-v /:/host:ro`): distro, kernel, zypper, btrfs + Snapper, GPU, locale, network, firewall
- Ingested Leap 16.0 Release Notes + 8 curated wiki SDB articles via MediaWiki API; store now 1958 deduped chunks; optional cross-encoder reranker
- Benchmarked all 4 tiers on the VM (report in `docs/evaluations/`); standard confirmed as default
- MCP PoCs: `suse-assist mcp` server (system context + doc search tools) and `suse-assist mcp-tools` client — full loop verified offline on the VM
- Fixed: context-window overflow on small tiers, Qwen3 chain-of-thought rambling, SELinux bind-mount denials, removed unused ChromaDB backend

**Next**
- Native systemd service on the VM (closes pending-updates/failed-services gap)
- RPM packaging via OBS
- Sync HF Space demo with new code

**Blockers**
- None. (VM has no outbound internet — solved with offline wheel/model shipping.)

---

## Week of May 25, 2026

**Done**
- Working PoC from proposal phase: local SLM assistant (llama.cpp) + RAG over official openSUSE docs (Chroma vector store), Rich CLI, Gradio web UI, container image, HF Spaces demo (API mode)
- Evaluated and documented GSoC action items: SLM selection (settled on Qwen3 family), vector DB options, model routing, installer/firstboot integration approaches
- Got mentor VM access (Leap 16.0, 4 vCPU / 15 GB, CPU-only)

**Next**
- Deploy on the VM with a real Leap 16.0 environment
- Replace TinyLlama/Chroma stack with the chosen Qwen3/LanceDB stack

**Blockers**
- VM outbound internet blocked (no huggingface.co) — need an offline deployment strategy
