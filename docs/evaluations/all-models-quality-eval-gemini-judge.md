# All-Model Quality & Latency Evaluation — External Gemini Judge

openSUSE Leap 16.0 VM · 4 vCPU · 15 GB RAM · CPU-only · fully offline (generation).
Judge: **Google Gemini 2.5 Flash-Lite** (external API, run off-VM on cached answers).

> Earlier iterations judged with the local Qwen3-8B — biased, since it graded
> Qwen models (and itself). This report uses a neutral frontier model from a
> different family, removing that bias.

## Method

Two decoupled phases:

1. **Generate (on the VM, offline, real CPU)** — every model answers the same 8
   onboarding questions through the full RAG + system-context pipeline. Answers,
   latency and throughput are cached to `eval_answers.json`.
2. **Judge (off-VM, internet)** — the cached answers are scored by Gemini against
   a gold reference and an expected-fact checklist. Answers are batched one API
   call per model (6 calls total, not 48) to stay within rate limits. Embedding
   similarity (cached MiniLM) is computed locally.

Decoupling matters: generation is hardware-bound (must run on the target VM);
judging is model-choice-bound (must be neutral). The VM has no outbound internet,
so the external judge necessarily runs elsewhere on the cached answers.

## Results (ranked by quality)

| Rank | Model | Tier | Quality (1-5) | Similarity | Avg latency | tok/s |
|------|-------|------|---------------|------------|-------------|-------|
| 1 | Qwen3-4B-Instruct | standard | **4.88** | 0.673 | 105.8 s | 28.2 |
| 2 | Qwen3-8B | full | 4.75 | 0.686 | 136.4 s | 19.9 |
| 3 | Gemma 4 E4B | gemma4-e4b | 4.62 | 0.693 | 75.9 s | 36.9 |
| 4 | Gemma 3 4B | gemma3-4b | 4.50 | 0.628 | 76.7 s | 39.3 |
| 5 | Qwen3-1.7B | lite | 4.00 | 0.682 | 41.8 s | 64.3 |
| 6 | TinyLlama 1.1B | test | 2.62 | 0.669 | 11.9 s | 137.6 |

8 questions: package install, add repo, update, Snapper rollback, firewall,
NVIDIA driver, YaST, Leap vs Tumbleweed. Gold answers and fact checklists in
`opensuse_ai/eval_dataset.py`.

Gemma 4 E4B is the smallest Gemma 4 (the edge/effective-4B MatFormer variant;
the dense Gemma 4 line starts at 12B, too large for CPU). Its q4_0 GGUF is
~4.9 GB on disk — larger than Gemma 3 4B (2.4 GB) but fits the 15 GB VM.

## Reading

- **Neutral judge, no same-vendor inflation**: Gemini (Google) ranked both its
  own-vendor Gemma models *below* the Qwen 4B/8B tiers (Gemma 4 E4B 4.62, Gemma 3
  4B 4.50). The feared same-vendor bias did not appear.
- **Standard wins**: Qwen3-4B-Instruct (4.88) edges Qwen3-8B (4.75) while running
  ~30 s faster per answer — best quality-per-second. Both lost the same point on
  `update_system` (omitted `zypper dup` for full version upgrades).
- **Gemma 4 E4B (4.62)**: the new Gemma 4 edge model beats Gemma 3 4B (4.50) at
  the same speed (~76 s) and has the highest similarity of any model (0.693).
  Sits third overall, just under the Qwen 4B/8B tiers; lost a point only on
  `update_system` (vague, omitted the exact `zypper` commands).
- **Gemma 3 4B (4.50)**: fast (77 s); strong but lost points on Snapper (wrong
  rollback detail) and NVIDIA driver specifics.
- **Qwen3-1.7B lite (4.00)**: best value for low-resource boxes — solid at 42 s;
  weakest on Snapper rollback (missed `snapper list`/exact command).
- **TinyLlama test (2.62)**: unreliable — wrong firewalld steps (referenced
  `/etc/sysconfig/nfs`, `init.d`), bad NVIDIA commands, miscategorised Tumbleweed.
  CI/smoke only.
- **Discrimination vs the biased judge**: the local Qwen3-8B judge scored both
  Qwen tiers a flat 5.00; the neutral Gemini judge separates them (4.88 vs 4.75)
  and is harsher overall — exactly why an external judge is the trustworthy one.

## Recommendation

- **Default**: Qwen3-4B-Instruct (standard) — top quality, half the 8B's latency.
- **Low-resource / impatient**: Qwen3-1.7B (lite) — 4.00 at 42 s.
- **Faster 4B-class alternative**: Gemma 4 E4B — 4.62 at 76 s (beats Gemma 3 4B).
- **full (Qwen3-8B)**: no quality advantage here; not worth the extra latency.
- **test (TinyLlama)**: CI/smoke only.

tok/s counts prompt + completion tokens (comparable across models, overstates
pure generation speed).

## Reproducing

```bash
# 1. Generate answers on the VM (offline). Writes data/eval_answers.json.
suse-assist eval --models test,lite,standard,full,gemma3-4b,gemma4-e4b \
  --judge-backend local --judge full --demo      # local judge, or skip judging

# 2. Judge the cached answers anywhere with internet, using the external judge.
#    GEMINI_API_KEY must be exported; it is never stored in the repo.
export GEMINI_API_KEY=...   # a Google AI Studio key
suse-assist eval --models test,lite,standard,full,gemma3-4b,gemma4-e4b \
  --judge-backend gemini --judge-model gemini-2.5-flash-lite --reuse-answers --demo
```

Batched judging = one API call per model (6 calls for 6 models). Per-question
detail (score + judge reason for all 48 answers) is written to `data/eval_report.md`.
