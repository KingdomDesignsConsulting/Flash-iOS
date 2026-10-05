# Layer-major target verifier result — 2026-09-26

## Scope

This benchmark advances four known candidate positions through the complete 40-layer transformer **layer by layer**, retaining causal position order inside each layer. Full attention KV, GPU DeltaNet, and convolution state are updated in order. It batches the final LM head. Routed experts are still dispatched per position: the experiment changes their temporal locality, but does not group multiple inputs for one expert into a single kernel. This is not a production target verifier.

The production server on port 11436 was left running. Isolated benchmark processes ran at 18:01:57–18:02:05, 18:03:07–18:03:18, 18:06:15–18:06:25, and 18:08:21–18:08:31 PDT on 2026-09-26. The first pass stopped at an exact-state comparison. The last pass added benchmark-only per-layer cold-weight staging. No benchmark server or persistent profile/checkpoint was created.

## Correctness

The first pass selected the same token at all four positions and had a maximum logit difference of `2.48e-5`. Its final snapshot was not byte-identical to the serial run. A second pass measured the difference by state component:

| Component | Maximum absolute difference |
|---|---:|
| Full-attention KV | 1.29e-5 |
| CPU convolution / recurrent | 0 |
| GPU convolution | 2.67e-5 |
| GPU DeltaNet | 3.28e-6 |

State dimensions and positions matched. The small differences are consistent with changing the GPU handoff/readback and normalization order between positions, though this experiment does not prove that is their sole cause. The benchmark required each component's maximum difference to stay below `1e-3` and every selected token to match before timing.

## Paired timing

Same model/configuration as the earlier serial and LM-head prototypes: Qwen3.5-35B-A3B tiered 4/2-bit experts, K=8, base Apple M4, GPU-resident MoE, oproj-v3, tiny matvec, normal command chaining and prefetch, 512-entry malloc expert cache. One warm-up and five alternating paired trials; snapshot restore and correctness checks were outside timing.

| N=4 variant | Paired serial median | Layer-major median | Relative speed | Transformer | LM head | Hot-cache hits / misses | Cold routed loads / reuses |
|---|---:|---:|---:|---:|---:|---:|---:|
| Basic layer-major | 195.224 ms | 247.753 ms | 0.788× | 215.552 ms | 32.116 ms | 657 / 0 | 623 / 0 |
| With per-layer cold-weight staging | 199.178 ms | 247.513 ms | 0.805× | 214.943 ms | 32.560 ms | 657 / 0 | 377 / 246 |

The basic layer-major path was 26.9% slower and the cold-staging variant was 24.3% slower. N=8 was not run because N=4 failed the preset 15% improvement gate. The earlier LM-head-only result at N=4 was 231.161 ms in its paired run; these are separate runs, so each paired serial control above is the more reliable comparison.

The N=4 block routed 623 cold 2-bit expert occurrences but only 377 distinct layer/expert pairs. Their summed stored sizes are approximately 584.1 MiB by occurrence and 353.4 MiB by distinct pair. The staging variant actually avoided 246 main-path repeated cold loads. This is **not** a measured 230.7 MiB reduction in physical SSD reads: OS page caching and speculative prefetch can alter physical I/O, and the route counter does not include prefetch reads. The 290 unique-expert count in the earlier telemetry was for the hot cache, not all routed experts.

## Limiting components and decision

The hot-cache path had zero misses, but cold 2-bit experts bypass that cache and are loaded for each routed occurrence unless the benchmark staging cache catches them. Saving 246 repeated main-path cold loads did not make N=4 faster. Layer-major execution also completes each layer's deferred expert result before switching positions, giving up the usual cross-layer GPU handoff and command chaining. Its transformer time alone exceeded the complete serial block time. This is a likely explanation for the slowdown, not a per-kernel causal profile.

This result **does not measure grouped multi-input expert arithmetic or total GPU weight bytes**. It does execute the whole candidate block layer-major and groups cold-weight staging by layer; expert kernels still execute per position. A fully grouped MoE implementation could reuse dequantized weights across positions, but would require routing all positions at a layer, per-position scratch, grouping by expert, and new multi-input kernels. The current path provides no end-to-end headroom to pay for that refactor. The requested stop gate was reached at N=4. This is a negative result for the tested locality/staging approach, not a proof that all possible grouped kernels are uneconomic. DFlash and production rollback/state transactions remain deferred.

The historical [serial benchmark](target-verifier-benchmark-2026-09-26.md) and [LM-head-only benchmark](batched-verifier-prototype-2026-09-26.md) are preserved.
