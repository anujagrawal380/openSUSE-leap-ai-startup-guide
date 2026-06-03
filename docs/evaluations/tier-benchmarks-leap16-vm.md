# Model Tier Benchmarks — openSUSE Leap 16.0 VM

Date: 2026-06-03 · openSUSE Leap 16.0 VM, 4 vCPU, 15 GB RAM, CPU-only, fully offline.
`suse-assist benchmark`: 8 standard onboarding queries per tier, RAG context included.

## Results

| Tier | Model | Quant | tok/s | Avg latency | P95 latency | Peak RAM |
|------|-------|-------|-------|-------------|-------------|----------|
| test | TinyLlama 1.1B | Q4_K_M | 120.6 | 12.5 s | 13.5 s | 1.9 GB |
| lite | Qwen3-1.7B | Q8_0 | 52.1 | 53 s | 54 s | 6.2 GB |
| **standard** | Qwen3-4B-Instruct-2507 | Q4_K_M | 30.6 | 94 s | 115 s | 8.7 GB |
| full | Qwen3-8B | Q4_K_M | 15.2 | 204 s | 222 s | 11.5 GB |

Note: tok/s counts prompt + completion tokens — comparable across tiers, overstates pure generation speed.

## Recommendations

- **standard** — default for ≥8 GB systems: best quality per second on CPU.
- **lite** — 4 GB systems or impatient users: half the latency, acceptable quality.
- **full** — not viable CPU-only (~3.4 min/answer); GPU machines only.
- **test** — CI/smoke tests only.

## Reproducing

```bash
podman run -i --rm -v opensuse-ai-data:/app/data \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  localhost/opensuse-ai-assistant:patched benchmark --model-tier <tier>
```

Stop the web UI container first — 8B benchmark + resident 4B web instance can OOM the VM.
