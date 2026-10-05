# Target-only candidate verification benchmark — 2026-09-26

## Scope and limitation

This is an isolated **serial teacher-forcing** benchmark of the current Flash-iOS target, not a batched verifier. `run_all_layers_checked()` and the DeltaNet/convolution kernels advance one token at a time. The result measures whether the current target path has any verification advantage; it cannot predict the cost of a future genuinely batched implementation or full speculative decoding.

## Method

- Hardware: Apple M4 Mac mini; Qwen3.5-35B-A3B tiered 4/2-bit model, K=8.
- Runtime defaults: GPU-resident MoE, oproj-v3, tiny-matvec-fast, CMD1/2 chaining, full-attention CMD1/2 chaining, expert prefetch, 512-entry malloc expert cache.
- CLI: `./infer-target-verify-bench --model <model directory> --bench-target-verifier` from `metal_infer`; the benchmark binary was temporary and is not the production `infer` binary.
- Prefill: a synthetic 25-token ChatML prompt. Its KV, DeltaNet, convolution, and GPU state was captured in a disposable in-memory snapshot. No persistent checkpoint or resident server session was used.
- Candidates: eight deterministic greedy tokens generated from that snapshot. Every candidate matched target greedy output in the measured trials.
- For each block size, one warm-up and five paired greedy/teacher-forced trials were run, alternating order. The full target forward and LM head ran for each token in both modes. The snapshot was restored before every trial; restore time is excluded from timing.
- The baseline is the median ordinary one-token greedy trial (50.163 ms). The sequential equivalent is N times that value.
- Existing cache telemetry tracked unique layer/expert pairs and expert-cache hits/misses. Instrumentation overhead is present in both paired modes. The production server on port 11436 was left running, so system-level contention was possible.

| Block | Median verify ms | Range ms | Verified tok/s | Sequential equivalent ms | Target-only advantage | Unique experts avg | Expert-cache hits/misses avg |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 49.602 | 48.351–52.558 | 20.16 | 50.163 | 1.011× | 135 | 135 / 0 |
| 2 | 98.578 | 92.957–108.655 | 20.29 | 100.326 | 1.018× | 197 | 290 / 0 |
| 4 | 194.054 | 183.722–243.493 | 20.61 | 200.652 | 1.034× | 290 | 657 / 0 |
| 8 | 432.434 | 408.999–444.931 | 18.50 | 401.305 | 0.928× | 554 | 731 / 357 |

The 8-token block exceeded the 512-entry expert cache's capacity in this sequence and averaged 357 cache misses per verification trial. The timing grows roughly linearly through four tokens and becomes worse at eight. We did not test 16 because eight was already unfavorable.

## Interpretation

The current serial path offers no meaningful target-side verification advantage. Four tokens was the least unfavorable block; its 1.034× result is within ordinary timing variation. Eight tokens was slower and showed a substantially larger expert working set. A drafter and rollback implementation is not justified by this result alone.

The unanswered question is whether a new multi-token target kernel could make verification sublinear despite stateful DeltaNet/convolution layers and MoE expert traffic. That would require a separate batched-verifier prototype and its own state-correctness tests. This benchmark must not be reported as full speculative-decoding speedup.
