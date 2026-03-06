# LLM Options for openSUSE AI Onboarding

All models run **100% locally** via llama.cpp (GGUF Q4_K_M quantisation). No cloud APIs required. This document compares viable Small Language Models for the project.

## Overview

| Model | Params | GGUF Q4 Size | Context Window | Min RAM | License | Quality |
|---|---|---|---|---|---|---|
| TinyLlama 1.1B | 1.1B | ~670 MB | 2,048 | 4 GB | Apache 2.0 | 2/5 |
| Gemma 2 2B | 2.6B | ~1.6 GB | 8,192 | 4–8 GB | Gemma | 3/5 |
| Phi-3.5 Mini | 3.8B | ~2.2 GB | 128,000 | 6–8 GB | MIT | 4/5 |
| Qwen2.5 3B | 3B | ~1.8 GB | 32,768 | 6–8 GB | Apache 2.0 | 4/5 |
| StableLM Zephyr 3B | 3B | ~1.8 GB | 4,096 | 6–8 GB | StabilityAI | 3/5 |
| Mistral 7B v0.3 | 7.2B | ~4.1 GB | 32,768 | 10–16 GB | Apache 2.0 | 5/5 |
| Llama 3.1 8B | 8B | ~4.7 GB | 128,000 | 12–16 GB | Llama 3.1 | 5/5 |

---

## TinyLlama 1.1B

- **Repo:** `TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF`
- Smallest viable chat model at ~670 MB
- Inference speed: ~230 tokens/s on Apple Silicon
- Apache 2.0 — fully permissive

**Pros:** Runs on nearly any hardware (4 GB RAM), extremely fast inference, great for testing and CI pipelines.

**Cons:** Frequent hallucinations, only 2K context window severely limits RAG context injection, poor multi-step reasoning, output quality not suitable for end-user deployment.

---

## Gemma 2 2B

- **Repo:** `bartowski/gemma-2-2b-it-GGUF`
- Google's compact model, surprisingly capable for 2.6B parameters
- Outperforms several older 7B models on standard benchmarks

**Pros:** Very compact (~1.6 GB), good accuracy for its size, runs on 4–8 GB RAM, decent safety alignment.

**Cons:** 8K context window limits RAG usage, Gemma license is more restrictive than Apache/MIT (no commercial redistribution without agreement), fewer community fine-tunes available, weaker on long-form generation.

---

## Phi-3.5 Mini

- **Repo:** `bartowski/Phi-3.5-mini-instruct-GGUF`
- Microsoft's 3.8B model, designed to punch above its weight class
- 128K context window — largest in the sub-4B category

**Pros:** Excellent instruction following, 128K context allows injecting large RAG chunks without truncation, MIT license (fully permissive), strong on technical and coding tasks, well-supported by llama.cpp ecosystem, fits in 8 GB RAM.

**Cons:** English-centric (weaker multilingual support), ~2.2 GB download, less creative writing ability compared to larger models.

---

## Qwen2.5 3B

- **Repo:** `Qwen/Qwen2.5-3B-Instruct-GGUF`
- Alibaba's multilingual model supporting 29 languages
- 32K context window, Apache 2.0 licensed

**Pros:** Best multilingual support in this size class (relevant for openSUSE's global user base — German, Spanish, Japanese communities), 32K context is sufficient for most RAG use cases, actively developed with frequent updates, Apache 2.0 license.

**Cons:** Slightly behind Phi-3.5 on English-only benchmarks, smaller community ecosystem compared to Meta/Microsoft models, context window is 4x smaller than Phi-3.5.

---

## StableLM Zephyr 3B

- **Repo:** `TheBloke/stablelm-zephyr-3b-GGUF`
- Stability AI's chat-optimised model with DPO alignment
- Purpose-built for conversational helpfulness

**Pros:** Good chat alignment out of the box, ~1.8 GB download, fits 8 GB RAM easily, decent technical knowledge.

**Cons:** Only 4K context window (limits RAG injection), benchmark scores below Phi-3.5 and Qwen2.5, development pace has slowed, smaller community.

---

## Mistral 7B v0.3

- **Repo:** `TheBloke/Mistral-7B-Instruct-v0.3-GGUF`
- The established standard for open 7B models
- Strong instruction following and reasoning capabilities

**Pros:** High-quality coherent answers, 32K context window, Apache 2.0 license, massive ecosystem of fine-tunes and community support, well-tested with llama.cpp.

**Cons:** ~4.1 GB download, requires 10–16 GB RAM (excludes low-end machines), slower inference than 3B models (~100–150 tok/s on Apple Silicon).

---

## Llama 3.1 8B

- **Repo:** `bartowski/Meta-Llama-3.1-8B-Instruct-GGUF`
- Meta's flagship open-weight model, state-of-the-art in the 8B class
- 128K context window with strong safety training

**Pros:** Best overall answer quality in this comparison, 128K context window, excellent at following complex multi-step instructions, massive community and tooling support.

**Cons:** ~4.7 GB download, requires 12–16 GB RAM, Llama 3.1 license has usage restrictions (700M monthly active user cap, must display "Built with Llama"), slower inference on CPU-only machines.

---

## Hardware-Based Recommendations

| Available RAM | Recommended Model | Rationale |
|---|---|---|
| 4 GB | TinyLlama 1.1B or Gemma 2 2B | Only models that fit comfortably |
| 8 GB | Phi-3.5 Mini 3.8B | Best quality/size ratio at this tier |
| 8 GB (multilingual) | Qwen2.5 3B | Better non-English support |
| 16+ GB | Mistral 7B or Llama 3.1 8B | Best answer quality, no size constraints |

Ideally the model should be **user-configurable** so people can choose based on their hardware and language needs.
