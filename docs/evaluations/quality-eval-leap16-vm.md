# Answer-Quality Evaluation — Qwen3-4B vs Gemma 3 4B

openSUSE Leap 16.0 VM · 4 vCPU · 15 GB RAM · CPU-only · fully offline.
`suse-assist eval --models standard,gemma3-4b --judge full --demo`

## Method

Each model answers the same 8 onboarding questions through the full RAG +
system-context pipeline. Answers are then scored two ways, both offline:

- **Quality (1-5)** — LLM-as-judge: Qwen3-8B (the `full` tier) scores each
  answer against a gold reference answer and an expected-fact checklist
  (accuracy, grounding, openSUSE-correctness). Judge runs with `/no_think`.
- **Similarity (0-1)** — embedding cosine between the answer and the gold
  reference (cached MiniLM-L6-v2).

Generation and judging run in separate phases so only one large model is
resident at a time — required on the 15 GB VM. Gold answers and the fact
checklists live in `opensuse_ai/eval_dataset.py`.

## Results

| Model | Quality (1-5) | Similarity | Avg latency | tok/s |
|-------|---------------|------------|-------------|-------|
| **Qwen3-4B-Instruct (standard)** | **5.00** | 0.673 | 107.8 s | 27.7 |
| Gemma 3 4B (gemma3-4b) | 4.75 | 0.628 | 76.2 s | 39.4 |

8 questions: package install, add repo, update, Snapper rollback, firewall,
NVIDIA driver, YaST, Leap vs Tumbleweed.

## Reading

- **Quality**: Qwen3-4B scored 5/5 on all 8. Gemma 3 4B scored 5/5 on 6 and
  4/5 on two (Snapper rollback — omitted the snapshot number argument; YaST —
  thinner coverage). Both are strong, grounded openSUSE answers.
- **Speed**: Gemma 3 4B is ~30 % faster (76 s vs 108 s average) and higher
  throughput, at a small quality cost.
- **Recommendation**: keep Qwen3-4B-Instruct as the default for best answer
  quality; Gemma 3 4B is a viable faster alternative where latency matters more
  than the last increment of accuracy.

tok/s counts prompt + completion tokens (comparable across models, overstates
pure generation speed).

## Reproducing

```bash
# Stop the web UI first so the 8B judge + generation don't contend for RAM.
podman run --rm -v opensuse-ai-data:/app/data \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  --entrypoint suse-assist localhost/opensuse-ai-assistant:patched \
  eval --models standard,gemma3-4b --judge full --demo

# Re-judge cached answers without regenerating (fast iteration on the judge):
suse-assist eval --models standard,gemma3-4b --judge full --reuse-answers
```
