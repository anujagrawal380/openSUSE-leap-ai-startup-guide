# Weekly Progress — AI-Powered Onboarding for openSUSE

Stand-up style log for weekly meetings. Newest week first.

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
