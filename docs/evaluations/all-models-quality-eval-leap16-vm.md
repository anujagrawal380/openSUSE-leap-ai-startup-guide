# All-Model Quality & Latency Evaluation — openSUSE Leap 16.0 VM

openSUSE Leap 16.0 VM · 4 vCPU · 15 GB RAM · CPU-only · fully offline.
`suse-assist eval --models test,lite,standard,full,gemma3-4b --judge full --demo`

## Method

Every model answers the same 8 onboarding questions through the full RAG +
system-context pipeline. Answers are scored two ways, both offline:

- **Quality (1-5)** — LLM-as-judge: Qwen3-8B (`full` tier) scores each answer
  against a gold reference and an expected-fact checklist, judging openSUSE
  correctness (zypper, YaST, firewalld, Btrfs/Snapper). Judge runs `/no_think`.
- **Similarity (0-1)** — embedding cosine between answer and gold reference
  (cached MiniLM-L6-v2).

Generation and judging run in separate phases so only one model is resident at
a time. Questions: package install, add repo, update, Snapper rollback,
firewall, NVIDIA driver, YaST, Leap vs Tumbleweed. Gold answers live in
`opensuse_ai/eval_dataset.py`.

## Results (ranked by quality)

| Rank | Model | Tier | Quality (1-5) | Similarity | Avg latency | tok/s |
|------|-------|------|---------------|------------|-------------|-------|
| 1 | Qwen3-4B-Instruct | standard | **5.00** | 0.673 | 105.8 s | 28.2 |
| 1 | Qwen3-8B | full | **5.00** | 0.686 | 136.4 s | 19.9 |
| 3 | Gemma 3 4B | gemma3-4b | 4.75 | 0.628 | 76.7 s | 39.3 |
| 4 | Qwen3-1.7B | lite | 4.62 | 0.682 | 41.8 s | 64.3 |
| 5 | TinyLlama 1.1B | test | 2.62 | 0.669 | 11.9 s | 137.6 |

> The judge (Qwen3-8B) also appears as a benchmarked model (`full`), so its own
> 5.00 carries mild self-evaluation bias. `standard` scoring 5.00 under the same
> judge is unaffected by this.

## Reading

- **Quality**: Qwen3-4B (standard) and Qwen3-8B (full) both score a perfect
  5.00 — every answer correct and grounded. Gemma 3 4B (4.75) and Qwen3-1.7B
  (4.62) are close behind, each losing points mainly on the Snapper-rollback
  question (omitted the snapshot-number argument / Btrfs detail). TinyLlama
  (2.62) is unreliable: hallucinated repository URLs, wrong firewalld steps, and
  miscategorised Tumbleweed as a repository.
- **Speed vs quality**: clear trade-off. TinyLlama is ~10× faster than full but
  fails on accuracy. Qwen3-1.7B (lite) is the value pick — 4.62 quality at 42 s.
  Gemma 3 4B sits between lite and standard: faster than both Qwen3-4B and 8B
  with near-top quality.
- **Diminishing returns at the top**: Qwen3-8B (full) costs +29 % latency over
  Qwen3-4B (standard) for no quality gain on this question set.

## Recommendation

- **Default**: Qwen3-4B-Instruct (standard) — best quality per second; full 5.00
  at half the latency of the 8B.
- **Low-resource / impatient**: Qwen3-1.7B (lite) — 4.62 at 42 s.
- **Faster 4B alternative**: Gemma 3 4B — 4.75 at 77 s.
- **full (Qwen3-8B)**: no quality advantage here; reserve for harder workloads.
- **test (TinyLlama)**: CI/smoke only — not fit for end-user answers.

tok/s counts prompt + completion tokens (comparable across models, overstates
pure generation speed).

## Reproducing

```bash
# Stop the web UI first so generation + the 8B judge don't contend for RAM.
podman run --rm -v opensuse-ai-data:/app/data \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  --entrypoint suse-assist localhost/opensuse-ai-assistant:patched \
  eval --models test,lite,standard,full,gemma3-4b --judge full --demo
```

Per-question detail (judge score + reason for all 40 answers) is written to
`data/eval_report.md` by the run.
