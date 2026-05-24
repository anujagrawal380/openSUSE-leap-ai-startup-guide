# SLM Evaluation and Verdict - May 2026

Status: Week 1 decision note

This is a fresh model review for the openSUSE AI onboarding assistant as of May 2026. The original PoC used TinyLlama 1.1B only to validate architecture. It should not remain the production default.

## Verdict

Use this model strategy:

- **Lite tier:** `Qwen3-1.7B-GGUF`
- **Standard tier:** `Qwen3-4B-GGUF`
- **Full tier:** `Qwen3-8B-GGUF`
- **Experimental tier:** `Gemma 4 E4B IT` and `Ministral 3 3B Instruct`
- **CI/demo fallback:** keep TinyLlama only for fast tests and constrained demos

Reason: Qwen3 gives the cleanest overall fit for openSUSE right now: Apache 2.0, official GGUF repositories, llama.cpp compatibility, strong multilingual coverage, long-enough context, and a coherent 1.7B/4B/8B tier ladder. That matters more than chasing the single highest benchmark number.

## What Changed Since the Proposal

The proposal-era shortlist centered on TinyLlama, Phi-3.5 Mini, Qwen2.5 3B, Gemma 2 2B, Mistral 7B, and Llama 3.1/3.2. That is now stale.

Newer candidates that materially change the decision:

- Qwen3 dense models: 1.7B, 4B, 8B with Apache 2.0, official GGUF, 32K native context, and strong multilingual support.
- Gemma 4: Apache 2.0, E2B/E4B edge models, 128K context, native system prompt support, multimodal/audio features.
- Ministral 3 3B: Apache 2.0, 256K context, function calling, strong edge positioning.
- SmolLM3 3B: Apache 2.0, official GGUF through ggml-org, useful small fallback.
- Phi-4-mini-instruct: still strong, MIT, 128K context, but weaker as default because official GGUF/package path is less clean than Qwen3.

## Ranked Shortlist

| Rank | Model | Params | Context | License | GGUF Path | Verdict |
|---:|---|---:|---:|---|---|---|
| 1 | Qwen3 4B | 4.0B | 32K native, 128K with YaRN | Apache 2.0 | Official `Qwen/Qwen3-4B-GGUF` | Default standard tier |
| 2 | Qwen3 1.7B | 1.7B | 32K | Apache 2.0 | Official `Qwen/Qwen3-1.7B-GGUF` | Default lite tier |
| 3 | Qwen3 8B | 8.2B | 32K native, 128K with YaRN | Apache 2.0 | Official `Qwen/Qwen3-8B-GGUF` | Default full tier |
| 4 | Gemma 4 E4B IT | 4.5B effective / 8B incl. embeddings | 128K | Apache 2.0 | Official weights; GGUF path must be verified for llama.cpp | Evaluate as standard-tier challenger |
| 5 | Ministral 3 3B Instruct | 3.4B LM + 0.4B vision | 256K | Apache 2.0 | Needs GGUF/llama.cpp packaging verification | Evaluate as edge/agentic challenger |
| 6 | Phi-4-mini-instruct | 3.8B | 128K | MIT | Community GGUF | Strong backup, not default |
| 7 | SmolLM3 3B | 3B | long context, model-card details need local validation | Apache 2.0 | `ggml-org/SmolLM3-3B-GGUF` | Backup for small systems |
| 8 | Gemma 3 4B IT | 4B | 128K | Gemma terms | Available | Superseded by Gemma 4 |
| 9 | Llama 3.2 3B | 3B | 128K upstream | Llama Community License | Available | Do not default due to license |
| 10 | TinyLlama 1.1B | 1.1B | 2K | Apache 2.0 | Available | CI/demo only |

## Tier Decision

| Tier | Recommended Model | Why |
|---|---|---|
| `lite` | Qwen3 1.7B GGUF | Apache 2.0, official GGUF, 32K context, much better than TinyLlama while still small |
| `standard` | Qwen3 4B GGUF | Best balance of quality, licensing, multilingual support, llama.cpp support, and 8 GB laptop target |
| `full` | Qwen3 8B GGUF | Same family and license as standard tier; better quality without changing prompt/template assumptions |
| `experimental` | Gemma 4 E4B IT | Promising Apache 2.0 challenger with 128K context and stronger newer architecture |
| `experimental` | Ministral 3 3B Instruct | Very attractive edge model, but local GGUF/packaging path needs validation |

## Why Qwen3 Should Be the Default Family

Qwen3 is the best production baseline because:

- Apache 2.0 is acceptable for openSUSE packaging review.
- Official GGUF repositories exist for the important sizes.
- The model family has a clean tier ladder from 1.7B to 8B.
- Qwen3 supports 100+ languages/dialects, which matters for openSUSE's global community.
- Qwen3 supports thinking/non-thinking modes; for onboarding, default to non-thinking for latency and concise output.
- Local use through llama.cpp is explicitly supported by the model card.

Operational note:

- For firstboot onboarding, run Qwen3 in **non-thinking mode** by default. Thinking mode increases latency and can expose distracting `<think>` output unless the chat template/parser is handled carefully.

## Why Gemma 4 Is Not the Default Yet

Gemma 4 is the most important new model family to evaluate next.

Pros:

- Apache 2.0.
- E2B/E4B edge models are explicitly designed for local devices.
- 128K context for small models.
- Native system prompt support.
- Multimodal/audio capabilities may become useful for installer screenshots or spoken onboarding later.

Risks:

- E4B has 4.5B effective parameters but 8B total including embeddings, so memory behavior must be measured rather than inferred from the "E4B" name.
- The assistant is text-first; Gemma 4's multimodal strengths do not matter for the first deliverable.
- Need to confirm clean GGUF/llama.cpp packaging flow for the exact instruction model before making it default.

Verdict: evaluate as the strongest standard-tier challenger, but do not replace Qwen3 until local GGUF packaging and memory behavior are proven.

## Why Ministral 3 Is Not the Default Yet

Ministral 3 3B is highly relevant because it is a modern edge model with Apache 2.0, 256K context, multilingual support, function calling, JSON output, and strong small-model benchmark claims.

Risks:

- The Hugging Face model card emphasizes FP8/vLLM usage.
- Need to verify a clean GGUF/llama.cpp path before depending on it for offline RPM packaging.
- Vision/function-calling capability is not required for the first onboarding MVP.

Verdict: evaluate seriously, especially for MCP/tool-routing work, but keep Qwen3 as the default until llama.cpp packaging is boring.

## Rejected or Demoted Models

| Model | Decision | Reason |
|---|---|---|
| TinyLlama 1.1B | Demote to CI/demo only | 2K context and weak answer quality are not acceptable for users |
| Phi-3.5 Mini | Superseded | Phi-4 mini and Qwen3 are better current candidates |
| Qwen2.5 3B | Superseded | Qwen3 1.7B/4B are cleaner choices now |
| Gemma 2 2B | Superseded | Gemma 4 and Qwen3 are stronger |
| Gemma 3 4B | Superseded | Gemma 4 moves Gemma to Apache 2.0 with stronger capabilities |
| Llama 3.2 3B | Do not default | License is less clean than Apache/MIT options |
| Mistral 7B Instruct v0.3 | Demote | Still useful, but Qwen3 8B is a cleaner same-family full tier |

## Implementation Update Needed

Code tier mapping should be:

- `test`: `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`
- `lite`: `Qwen/Qwen3-1.7B-GGUF`
- `standard`: `Qwen/Qwen3-4B-GGUF`
- `full`: `Qwen/Qwen3-8B-GGUF`

Keep TinyLlama as `test`, not as the user-facing lite tier. The checked-in PoC config may still default to `test` to avoid surprise multi-GB downloads during local demos.

## Validation Checklist

Before final mentor sign-off, run these local checks on Leap:

- `Qwen3-1.7B-Q4_K_M`: 4 GB VM, CPU-only.
- `Qwen3-4B-Q4_K_M`: 8 GB VM, CPU-only and GPU-accelerated if available.
- `Qwen3-8B-Q4_K_M`: 16 GB VM.
- `Gemma 4 E4B IT`: 8 GB and 16 GB VM, measure actual load memory.
- `Ministral 3 3B`: verify llama.cpp/GGUF route before benchmarking.

Benchmark query set:

- zypper install/remove/update
- YaST module discovery
- Snapper rollback
- Btrfs snapshot explanation
- repository priorities
- firewall basics
- failed systemd service troubleshooting
- openSUSE community/help channels
- German and Spanish versions of two onboarding questions

Decision gate:

- If Qwen3 4B answers are grounded, concise, and fit under 8 GB, keep it as default.
- If Gemma 4 E4B is significantly better and fits under 8 GB with clean GGUF packaging, promote it to standard.
- If Ministral 3 3B has clean llama.cpp support and better latency/quality than Qwen3 4B, consider it for lite/standard.

## Sources

- Qwen3 1.7B model card: https://huggingface.co/Qwen/Qwen3-1.7B
- Qwen3 1.7B GGUF: https://huggingface.co/Qwen/Qwen3-1.7B-GGUF
- Qwen3 4B model card: https://huggingface.co/Qwen/Qwen3-4B
- Qwen3 4B GGUF: https://huggingface.co/Qwen/Qwen3-4B-GGUF
- Qwen3 8B model card: https://huggingface.co/Qwen/Qwen3-8B
- Qwen3 8B GGUF: https://huggingface.co/Qwen/Qwen3-8B-GGUF
- Gemma 4 overview: https://ai.google.dev/gemma/docs/core
- Gemma 4 E4B IT model card: https://huggingface.co/google/gemma-4-E4B-it
- Ministral 3 3B docs: https://docs.mistral.ai/models/model-cards/ministral-3-3b-25-12
- Ministral 3 3B HF model card: https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512
- Phi-4-mini-instruct: https://huggingface.co/microsoft/Phi-4-mini-instruct
- SmolLM3 3B: https://huggingface.co/HuggingFaceTB/SmolLM3-3B
- SmolLM3 3B GGUF: https://huggingface.co/ggml-org/SmolLM3-3B-GGUF
