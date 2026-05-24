# SLM Model Decision - May 2026

Status: final Week 1 model selection decision

This document selects the Small Language Model stack for the openSUSE AI onboarding assistant. It is not a benchmark plan. It records the decision after reviewing current local/offline SLM options available by May 2026.

## Decision

Use **Qwen as the production model family**.

| Tier | Final model | Repo / file | Why |
|---|---|---|---|
| `test` | TinyLlama 1.1B Chat | `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF` / `tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf` | CI/demo only; avoids large downloads |
| `lite` | Qwen3 1.7B | `Qwen/Qwen3-1.7B-GGUF` / `Qwen3-1.7B-Q8_0.gguf` | Best official low-resource local model path |
| `standard` | Qwen3 4B Instruct 2507 | `lmstudio-community/Qwen3-4B-Instruct-2507-GGUF` / `Qwen3-4B-Instruct-2507-Q4_K_M.gguf` | Best default for real users |
| `full` | Qwen3 8B | `Qwen/Qwen3-8B-GGUF` / `Qwen3-8B-Q4_K_M.gguf` | Higher quality while keeping same tokenizer/model family |

The default user-facing tier should be **standard**. The checked-in PoC config may keep `test` to avoid surprise downloads, but production setup should recommend `standard` on 8 GB systems.

## Why This Is The Right Decision

The project constraints are more important than generic leaderboard scores:

- Must run locally and offline.
- Must be usable during first boot.
- Must fit normal laptops.
- Must be redistributable through an openSUSE-friendly packaging path.
- Must support multilingual openSUSE users.
- Must avoid complex reasoning-output parsing for ordinary onboarding questions.
- Must work through llama.cpp / GGUF.

Qwen wins because it gives a coherent 1.7B / 4B / 8B ladder with Apache 2.0 licensing, llama.cpp support, strong multilingual behavior, and mature local tooling.

## Primary Default: Qwen3 4B Instruct 2507

Use `Qwen3-4B-Instruct-2507` as the **standard production model**.

Reasons:

- Apache 2.0 license.
- 4B size is realistic for 8 GB systems with Q4 quantization.
- Official model card says it is the updated non-thinking Qwen3 4B mode.
- It has native 262,144 token context.
- It does not emit `<think>` blocks, so the assistant does not need reasoning-output parsing.
- The model card reports improvements over Qwen3-4B non-thinking across instruction following, knowledge, reasoning, coding, agent tasks, writing, long-tail multilingual knowledge, and long-context understanding.
- GGUF is available through the LM Studio community repo with Q4_K_M and llama.cpp usage instructions.

This fits the assistant better than plain `Qwen3-4B-GGUF`, because onboarding is mostly concise, grounded, non-thinking instruction following. We should not make users wait for reasoning traces when they ask how `zypper dup` differs from `zypper up`.

## Final Ranking

| Rank | Model | Decision | Reason |
|---:|---|---|---|
| 1 | Qwen3 4B Instruct 2507 | **Default standard** | Best fit for 8 GB machines: Apache 2.0, non-thinking, strong instruction following, 256K context, local GGUF available |
| 2 | Qwen3 8B GGUF | **Default full** | Better quality for 16 GB systems with the same family/tooling assumptions |
| 3 | Qwen3 1.7B GGUF | **Default lite** | Official GGUF, Apache 2.0, low-resource option that is much better than TinyLlama |
| 4 | Gemma 4 E4B IT | **Rejected as default, keep as future challenger** | Excellent Apache 2.0 model with 128K/256K-era capabilities, but local GGUF/RPM path is less clean today than Qwen |
| 5 | NVIDIA Nemotron 3 Nano 4B GGUF | **Rejected as default, future benchmark only** | Strong edge model with official GGUF, but NVIDIA custom license and English-first positioning are worse for openSUSE packaging/community |
| 6 | Ministral 3 3B Instruct | **Rejected as default, future benchmark only** | Apache 2.0 and 256K context are attractive, but current public path emphasizes FP8/vLLM more than simple llama.cpp RPM packaging |
| 7 | Phi-4-mini-instruct | **Backup only** | MIT and 128K context are good, but Qwen has cleaner multilingual + GGUF + tier consistency |
| 8 | SmolLM3 3B | **Backup only** | Apache 2.0 and GGUF available, but not stronger than Qwen3 4B for the standard tier |
| 9 | IBM Granite 4.0 Micro / H Tiny | **Rejected for first release** | Enterprise-friendly Apache 2.0 models, but not enough advantage over Qwen for openSUSE onboarding |
| 10 | Llama 3.2 3B | **Rejected** | Custom Llama license is less attractive than Apache/MIT options |
| 11 | Mistral 7B Instruct v0.3 | **Rejected** | Older than current options and no longer the best full-tier choice |
| 12 | Gemma 3 / Gemma 2 / Qwen2.5 / Phi-3.5 | **Superseded** | Replaced by stronger 2025/2026 candidates |
| 13 | TinyLlama 1.1B | **CI/demo only** | Too weak and 2K context is not acceptable for users |

## Candidate Evaluations

### Qwen3 4B Instruct 2507

Verdict: **select as default**.

Use it for the `standard` tier.

Strengths:

- Apache 2.0.
- 4B parameter count.
- Native 262K context.
- Non-thinking-only output, no `<think>` handling.
- Strong multilingual and long-tail knowledge improvements.
- Tool/agent improvements are useful for the MCP direction.
- Q4_K_M GGUF is about 2.5 GB in the LM Studio community repo.

Risk:

- The canonical model is official Qwen, but the Q4_K_M GGUF repo is community-hosted. For RPM packaging, pin exact file checksums and prefer reproducing the GGUF conversion from the official upstream safetensors if openSUSE packaging policy requires it.

Decision impact:

- This should replace `Qwen/Qwen3-4B-GGUF` as the standard tier.

### Qwen3 1.7B GGUF

Verdict: **select as lite**.

Strengths:

- Apache 2.0.
- Official Qwen GGUF repo.
- Official file is small enough for low-resource machines.
- Better model quality and context than TinyLlama.

Risk:

- The official GGUF repo exposes Q8_0 rather than a Q4_K_M file, so the file is larger than a community Q4. That is acceptable because supply-chain cleanliness matters more than shaving several hundred MB in the lite tier.

Decision impact:

- Use `Qwen3-1.7B-Q8_0.gguf` for now.
- Do not call TinyLlama the lite tier anymore.

### Qwen3 8B GGUF

Verdict: **select as full**.

Strengths:

- Apache 2.0.
- Official Qwen GGUF repo.
- Q4_K_M file is available.
- Higher quality than the 4B tier while preserving prompt/template behavior.
- A better full tier than Mistral 7B because it keeps the model family consistent.

Risk:

- 8B Q4 still needs a real 16 GB machine for comfortable use alongside embeddings, vector DB, desktop, and firstboot services.

Decision impact:

- Use only when the setup wizard detects enough RAM or the user explicitly chooses `full`.

### Gemma 4 E4B IT

Verdict: **do not select for first release**.

Strengths:

- Apache 2.0.
- Effective 4.5B edge model.
- 128K context for E2B/E4B and broader Gemma 4 context support up to 256K in larger variants.
- Multimodal, audio, function-calling, and strong edge positioning.
- Good future fit for installer screenshots, OCR, or voice onboarding.

Why it loses today:

- The assistant is text-first. Gemma 4's multimodal/audio capabilities are not needed for the initial deliverable.
- Memory behavior is less obvious because E4B is 4.5B effective but 8B total including embeddings.
- The local GGUF/RPM path is not as clean as Qwen's current GGUF ladder.

Decision impact:

- Keep it as the first challenger for a post-baseline benchmark.
- Do not make it the production default before packaging and memory behavior are proven.

### Gemma 4 E2B IT

Verdict: **do not select for lite**.

Strengths:

- Apache 2.0.
- Edge/mobile positioning.
- Multimodal/audio support.
- 128K context.

Why it loses today:

- Qwen3 1.7B has a cleaner official GGUF text-only path.
- The openSUSE assistant does not need audio or image input in the first release.

### NVIDIA Nemotron 3 Nano 4B GGUF

Verdict: **do not select for default**.

Strengths:

- Official Q4_K_M GGUF exists.
- Designed for edge agentic use.
- Strong published RULER and instruction-following numbers.
- Long-context capabilities are compelling.

Why it loses today:

- NVIDIA Nemotron Open Model License is a custom license, not Apache/MIT.
- Model card positions supported language as English, while openSUSE needs stronger multilingual confidence.
- Hybrid architecture may complicate distro packaging/testing compared with the Qwen llama.cpp path.

Decision impact:

- Benchmark later if mentors want an edge-agent comparison, but do not choose it for the GSoC baseline.

### Ministral 3 3B Instruct

Verdict: **do not select for first release**.

Strengths:

- Apache 2.0.
- 256K context.
- Small 3B class.
- Vision, function calling, structured output, and agent features.
- Strong edge-device positioning.

Why it loses today:

- Public model card emphasizes FP8, vLLM, and Mistral serving path.
- The assistant needs a boring llama.cpp/GGUF/RPM route first.
- Vision and advanced tool features are not part of the first release.

### Phi-4-mini-instruct

Verdict: **backup only**.

Strengths:

- MIT license.
- 3.8B size.
- 128K context.
- Strong technical/coding reputation.

Why it loses today:

- We do not get the clean 1.7B/4B/8B family ladder.
- Qwen is stronger for multilingual openSUSE community use.
- Community GGUF/package path is less compelling than Qwen's ecosystem.

### SmolLM3 3B

Verdict: **backup only**.

Strengths:

- Apache 2.0.
- GGUF available through `ggml-org`.
- Good small-model engineering story.

Why it loses today:

- It is not clearly better than Qwen3 4B as the standard model.
- Qwen's multilingual/tooling ecosystem is stronger for this project.

### IBM Granite 4.0 Micro / H Tiny

Verdict: **not first release**.

Strengths:

- Apache 2.0.
- Enterprise-friendly positioning.
- Granite cards mention RAG, function calling, multilingual enterprise tasks, and permissive training-source emphasis.

Why it loses today:

- Granite is attractive for enterprise assistants, but this project needs openSUSE desktop/firstboot onboarding.
- It does not beat Qwen on combined local tooling, community adoption, multilingual breadth, and GGUF availability.

### Llama 3.2 3B

Verdict: **reject**.

Reason:

- Good model, but the Llama community license is less clean for distribution than Apache 2.0 or MIT. It should not be chosen when comparable Apache models exist.

### TinyLlama 1.1B

Verdict: **CI/demo only**.

Reason:

- It validates the architecture, but 2K context and weak answer quality are not acceptable for a production onboarding assistant.

## Operational Defaults

Use these defaults in code and packaging:

```yaml
model:
  default_user_tier: standard
  test:
    repo_id: TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF
    filename: tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf
    n_ctx: 2048
  lite:
    repo_id: Qwen/Qwen3-1.7B-GGUF
    filename: Qwen3-1.7B-Q8_0.gguf
    n_ctx: 32768
  standard:
    repo_id: lmstudio-community/Qwen3-4B-Instruct-2507-GGUF
    filename: Qwen3-4B-Instruct-2507-Q4_K_M.gguf
    n_ctx: 32768
  full:
    repo_id: Qwen/Qwen3-8B-GGUF
    filename: Qwen3-8B-Q4_K_M.gguf
    n_ctx: 32768
```

Do not default to the model's maximum context at first boot. Even though Qwen3 4B Instruct 2507 supports 262K context, start with 32K to control RAM and latency. Increase context only through config on systems that can afford it.

## Final Answer For Mentors

The model decision is:

> Use Qwen3-4B-Instruct-2507 as the default standard model for the openSUSE AI onboarding assistant. Use Qwen3-1.7B for low-memory systems and Qwen3-8B for full-tier systems. Keep TinyLlama only as a CI/demo model. Do not choose Gemma 4, Nemotron, Ministral, Phi, SmolLM, Granite, Llama, or Mistral as the first production baseline because each has a worse packaging, licensing, multilingual, or operational fit for this specific openSUSE firstboot use case.

## Sources

- Qwen3 4B Instruct 2507 model card: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Qwen3 4B Instruct 2507 GGUF: https://huggingface.co/lmstudio-community/Qwen3-4B-Instruct-2507-GGUF
- Qwen3 1.7B model card: https://huggingface.co/Qwen/Qwen3-1.7B
- Qwen3 1.7B GGUF: https://huggingface.co/Qwen/Qwen3-1.7B-GGUF
- Qwen3 8B model card: https://huggingface.co/Qwen/Qwen3-8B
- Qwen3 8B GGUF: https://huggingface.co/Qwen/Qwen3-8B-GGUF
- Gemma 4 E2B IT model card: https://huggingface.co/google/gemma-4-E2B-it
- Gemma 4 E4B IT model card: https://huggingface.co/google/gemma-4-E4B-it
- NVIDIA Nemotron 3 Nano 4B GGUF: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF
- NVIDIA Nemotron 3 family: https://research.nvidia.com/labs/nemotron/Nemotron-3/
- Ministral 3 3B model card: https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512
- Ministral 3 3B docs: https://docs.mistral.ai/models/model-cards/ministral-3-3b-25-12
- Phi-4-mini-instruct: https://huggingface.co/microsoft/Phi-4-mini-instruct
- SmolLM3 3B: https://huggingface.co/HuggingFaceTB/SmolLM3-3B
- SmolLM3 3B GGUF: https://huggingface.co/ggml-org/SmolLM3-3B-GGUF
- Granite 4.0 Micro GGUF: https://huggingface.co/ibm-granite/granite-4.0-micro-base-GGUF
