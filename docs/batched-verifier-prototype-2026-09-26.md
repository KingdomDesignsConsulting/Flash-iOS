# Partially batched target-verifier prototype — 2026-09-26

## What was batched

The prototype projects 1, 2, 4, or 8 candidate-position hidden states through the quantized LM head in **one Metal dispatch and one command buffer**. Its kernel reuses each quantized output row across all positions. The 40 transformer layers remain position-serial, including full attention, DeltaNet/GDN, depthwise convolution, dense projections, MoE routing, and expert execution. This is a partial multi-position verifier, not a full block transformer or a production speculative decoder.

The architecture/design note is [batched-verifier-design-2026-09-26.md](batched-verifier-design-2026-09-26.md). The historical serial benchmark in [target-verifier-benchmark-2026-09-26.md](target-verifier-benchmark-2026-09-26.md) is unchanged.

## Method

- Model: Qwen3.5-35B-A3B, tiered 4/2-bit experts, K=8, on Apple M4.
- Runtime: GPU-resident MoE, oproj-v3, tiny matvec, CMD1/2 and full-attention chaining, expert prefetch, 512-entry malloc expert cache. No drafter, checkpoint, profile capture, server, or production session.
- Prefix: the same disposable 25-token synthetic ChatML prefix and deterministic full-acceptance greedy candidates as the serial benchmark.
- One warm-up and five measured paired serial/batch trials per block. The order alternated. Before each trial, a full KV/DeltaNet/convolution/GPU state snapshot was restored; restore time was excluded. Existing cache telemetry ran in both paths.
- The batch time includes serial transformer execution of N known candidate tokens, collecting and normalizing the N hidden states, and one batched LM-head command. It excludes candidate generation, initial prefill, state restore, and correctness comparison.
- A separate serial reference projected the same hidden states individually. Each position's argmax and every logit were compared. The final captured KV, DeltaNet, convolution, and GPU recurrent state was compared byte-for-byte.

| Block | Paired serial median ms | Partial batch median ms | Verified tok/s | Sequential equivalent ms | Target-only advantage | Batch transformer ms | Batch LM-head ms | Unique experts avg | Expert-cache hits / misses avg |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 53.355 | 57.548 | 17.38 | 53.355 | 0.927× | 47.605 | 9.943 | 135 | 135 / 0 |
| 2 | 103.036 | 115.917 | 17.25 | 106.710 | 0.921× | 97.914 | 17.233 | 197 | 290 / 0 |
| 4 | 207.775 | 231.161 | 17.30 | 213.420 | 0.923× | 197.057 | 32.710 | 290 | 657 / 0 |
| 8 | 469.389 | 501.686 | 15.95 | 426.840 | 0.851× | 439.153 | 63.142 | 554 | 731 / 357 |

The one-token ordinary decode baseline for this paired run was 53.355 ms. The sequential-equivalent column is N times that baseline. The historical one-token baseline was 50.163 ms; the paired baseline is used above to reduce run-to-run confounding.

## Correctness

All candidate positions matched the serial argmax: 1/1, 2/2, 4/4, and 8/8. Maximum absolute logit differences were 2.38e-6, 2.62e-6, 2.62e-6, and 2.86e-6 respectively; RMS differences stayed below 3.7e-7. Final captured model state matched byte-for-byte for all four block sizes.

## Interpretation and limits

The custom batch LM head is slower than the optimized per-token LM head. At N=8, roughly 439 ms of the 502 ms partial-batch time is still serial transformer work. The block again touches 554 distinct layer/expert pairs and averages 357 expert-cache misses; batching only the LM head cannot improve MoE locality. Expert bytes and per-layer I/O times were not measured in this run. The prototype adds about 8 MiB of shared output buffer and a small input buffer, plus disposable state snapshots for correctness; it does not add a persistent cache.

No tested block size shows target-side headroom; N=4 is merely the least unfavorable among the multi-token choices. This **does not settle** whether a future full block transformer with grouped MoE execution could be sublinear. That would require new layer-level multi-position kernels, especially correct ordered DeltaNet and convolution state updates and grouped expert work. The present evidence does not justify production rollback or DFlash integration.

The benchmark was compiled to a separate temporary binary. The production `infer` binary and warm-state compatibility identity were not changed.
