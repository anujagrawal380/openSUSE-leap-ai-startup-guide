# Weekly Progress — AI-Powered Onboarding for openSUSE

Stand-up style log for weekly meetings. Newest week first.

---

## Week of Jun 15, 2026

**Done**
- Moved the container to an openSUSE/SUSE BCI Python base and added the first OEM appliance scaffolding: KIWI description, Podman Quadlet unit, and a firstboot path for preparing the assistant data volume.
- Added the missing first-run/admin commands:
  - `suse-assist doctor` checks whether a local install has the model, vector store, embedding cache, host mount, web port, and container runtime pieces it needs.
  - `suse-assist setup` handles model tier selection, optional offline bundle import, model download/cache, docs ingest, and final doctor check.
  - `suse-assist setup native-service` renders/installs the native systemd unit.
- Added offline bundle support with `suse-assist bundle export/import`. This gives us a concrete path for machines that cannot fetch models/docs during first boot: build the bundle once, then import the GGUF model, MiniLM cache, LanceDB index, and manifest offline.
- Improved the web UI for the real VM behavior: CPU-only answers can take over a minute, so the UI now shows model/tier state, lazy first-load guidance, elapsed “thinking” progress, and clearer errors when the model or index is missing.
- Added desktop launcher packaging assets (`.desktop`, icon, launcher script) so the assistant can be opened like a normal desktop tool once packaged or hooked into welcome/firstboot.
- Hardened the assistant and runtime: prompt-injection guardrails, hidden-reasoning cleanup, warnings around destructive/vendor-change commands, command-answer references, container healthcheck, read-only runtime defaults, dropped capabilities, resource limits, and clearer volume/log docs.
- Expanded the evaluation set with more common openSUSE onboarding issues: Packman/vendor change, codecs, Wi-Fi/Bluetooth, disk-full Btrfs snapshots, and failed systemd services.
- Added a reusable demo smoke script for prepared environments. It checks the CLI path, RAG retrieval, and web endpoint without having to manually click through the demo.
- Added OBS/RPM packaging scaffolding and proved the vendored-wheel path at real scale in `home:anujagrawal:suse-assist/suse-assist-image`. OBS now builds the BCI container with a ~467 MB CPython 3.11 wheelhouse, including Torch, LanceDB, Gradio, MCP, Transformers, and a locally built `llama-cpp-python` wheel.
- Published the OBS-built BCI container to `registry.opensuse.org` from the home project. The current pull path is `registry.opensuse.org/home/anujagrawal/suse-assist/images/opensuse/suse-assist:latest`.
- Tested the OBS registry image path on the offline Leap VM without using VM internet: downloaded the OBS image tar on a connected machine, transferred it over SSH, verified the checksum on the VM, loaded it with Podman, and ran it against the existing offline model/vectorstore volume.
- Switched the public VM demo at `http://stage3.opensuse.org:19000/` to the OBS-built image (`localhost/opensuse/suse-assist:latest`) while keeping the existing `opensuse-ai-data` model/vectorstore volume.
- Verified the OBS image on the VM with `suse-assist doctor`, web startup, test-tier CLI inference, and standard Gemma 4 E4B CLI inference. Standard-tier CPU response for "What is zypper?" was about 70 seconds with cited RAG output.
- Fixed the container volume ownership issue found during VM validation by making the runtime `suseai` UID/GID stable at `999:999`, matching the existing VM data volume.
- Did a cleanup/validation pass after the new work; the repo is in a cleaner state and the web/RAG/smoke paths were exercised locally where possible.

**Next**
- Decide whether the vendored-wheel OBS package is acceptable as the short-term publishing path, or start packaging the missing Python dependencies as proper RPMs.
- Produce an actual offline bundle from the VM’s model/vectorstore data and test the OEM firstboot import path against it.
- Start RPM-installed Leap test host validation once RPM packaging is ready enough to install.

**Blockers**
- Need mentor/community direction on whether vendored wheels are acceptable as a short-term OBS prototype or whether we should invest immediately in proper openSUSE RPMs for the ML stack.
- Need final decision on model/index distribution for offline OEM images: KIWI overlay, RPM payload/subpackage, separate artifact, or firstboot fetch.
- RPM runtime validation still needs an RPM-installed Leap test host; the OBS container runtime path is validated on the Leap VM and now powers the public demo.

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
