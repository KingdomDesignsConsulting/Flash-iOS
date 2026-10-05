# Prefill prototype results — 2026-09-28

## Scope

The production server, API/session behavior, warm-state format, compatibility identity, and `main-agent` checkpoint were left unchanged. The prototype lives under `metal_infer/prefill_probe/` and is benchmark-only.

## Audit cleanup

The liveness probe no longer treats read-side EOF/POLLHUP as a definitive response disconnect. A legal client half-close completed successfully for both non-streaming and streaming requests, and same-session follow-ups reported `session_reused: 1`. A true TCP reset after the first streamed content token returned `/health` in 0.14 seconds, logged session invalidation, and the follow-up reported `session_reused: 0`.

JSON validation covers the four GGUF overlay loaders, tiered manifest numeric fields, model manifest/config scalar fields, tensor containers, and malformed nested shapes. Isolated malformed fixtures passed. The real 1,397-tensor model manifest still passed layout validation.

## Kernel prototypes

The first pass used an isolated Metal source file with two GDN kernels and a grouped tiered-expert projection kernel. It was not linked into `infer` and did not run a full transformer prefill.

The initial pass compared scalar versus chunked causal GDN and compared scalar versus genuinely multi-input grouped expert arithmetic. Both paths produced zero maximum state/output difference in the probe. Preliminary timings on the Apple M4 were:

| Path | Rows | Scalar ms | Grouped/chunk ms | Speedup |
|---|---:|---:|---:|---:|
| GDN | 4 | 0.637 | 0.368 | 1.73x |
| GDN | 8 | 0.903 | 0.545 | 1.66x |
| GDN | 16 | 1.444 | 0.831 | 1.74x |
| GDN | 32 | 2.745 | 1.331 | 2.06x |
| GDN | 64 | 4.564 | 2.036 | 2.24x |
| 4-bit expert | 4 | 0.770 | 0.557 | 1.38x |
| 4-bit expert | 16 | 2.392 | 1.317 | 1.82x |
| 2-bit expert | 4 | 0.498 | 0.404 | 1.23x |
| 2-bit expert | 16 | 1.483 | 1.007 | 1.47x |

**Geometry correction:** the loaded model's `config.json` and `validate_target_architecture()` both specify 32 value heads, 16 key heads, and 128 dimensions for each. The actual ratio is 2:1, the recurrent state is `32*128*128` floats, and value/output rows have 4,096 elements. The earlier instruction claiming 64 value heads was incorrect. A subsequent 64-head run measured a different, synthetic geometry and is excluded from the actual-model result. The first table above used the actual 32-head dimensions; a fresh actual-model run with convolution continuation follows.

### Actual-model isolated GDN, Apple M4

Five measured repetitions followed one warmup at each size. Times are CPU wall-clock medians including Metal command submission and completion. Both output rows and final recurrent state had zero measured maximum absolute difference for every tested size; byte identity was not separately checked. The probe accepts already projected Q/K/V/decay/beta inputs, so it does not validate full-layer behavior.

| Chunk | Scalar median ms | Chunk median ms | Chunk rows/s | Speedup | Max output/state error |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.490 | 0.315 | 3,175 | 1.56x | 0 / 0 |
| 4 | 0.528 | 0.517 | 7,737 | 1.02x | 0 / 0 |
| 8 | 0.844 | 0.519 | 15,414 | 1.63x | 0 / 0 |
| 16 | 1.484 | 0.687 | 23,290 | 2.16x | 0 / 0 |
| 32 | 2.335 | 1.256 | 25,478 | 1.86x | 0 / 0 |
| 64 | 4.718 | 2.007 | 31,888 | 2.35x | 0 / 0 |

The earlier approximate gain survives at chunk 16 and 64, but the run-to-run variation is visible at chunk 4 and 32. The largest measured speedup was 2.35x at chunk 64; chunk 32 had the highest absolute throughput among the preferred 16/32 candidates. These figures include dispatch overhead and are not full-model prefill speedups.

### Convolution and continuation, Apple M4

The benchmark-only convolution kernels mirror the production depthwise kernel's four-tap BF16 weights, SiLU, 8,192-channel input, and three-row tail. Initial tail, inputs, and BF16 weights were synthetic. At chunks 16 and 32, scalar and chunked convolution had zero measured maximum output/tail difference. After one identical additional scalar row, the next output and tail still had zero difference. The independently tested GDN recurrence also had zero state/output difference after the same form of one-row continuation at chunks 16 and 32.

| Chunk | Conv prefix output | Conv prefix tail | Conv next output | Conv next tail | GDN next output | GDN next state |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0 | 0 | 0 | 0 | 0 | 0 |
| 32 | 0 | 0 | 0 | 0 | 0 | 0 |

These convolution and GDN checks are separate isolated paths. They do not establish full-layer or full-model equivalence.

### Corrected grouped-expert baseline, Apple M4

One real layer-0 hot 4-bit expert (`id=1`, 1,769,472 packed bytes) and one cold 2-bit expert (`id=0`, 983,040 packed bytes) were read from the tiered model. Scalar and grouped output had zero measured maximum absolute difference at every size. The grouped path uses native packed expert weights and multiple input rows in one dispatch.

| Rows | Hot scalar ms | Hot grouped ms | Hot speedup | Cold scalar ms | Cold grouped ms | Cold speedup |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.343 | 0.338 | 1.02x | 0.374 | 0.384 | 0.97x |
| 4 | 0.859 | 0.578 | 1.49x | 0.734 | 0.591 | 1.24x |
| 8 | 1.247 | 0.783 | 1.59x | 1.216 | 0.925 | 1.31x |
| 16 | 2.364 | 1.249 | 1.89x | 2.158 | 1.477 | 1.46x |

Hot expert grouping improved most at 16 rows among the requested 1/4/8/16 rows in this run. Cold expert gains remained modest. The isolated results do not include real routing, staging, cache misses, scatter, or cross-layer command handoff.

The grouped expert kernel decodes native packed 4-bit and 2-bit weights directly, processes multiple input rows in one dispatch, and avoids expanded weight materialization. It does not yet include routing, SwiGLU/down projection fusion across the full transformer, GPU grouping, attention, command chaining, or cache/prefetch orchestration.

## Routing overlap diagnostic

A 148-token real prompt trace recorded 5,920 layer/token route samples. For contiguous windows, average adjacent-row overlap was approximately 2.8 of K=8 experts. At window size 16, the trace contained 29,593 repeated routed occurrences and an idealized 40.1 GB of stored expert bytes that would not need to be staged a second time if each layer/expert were loaded once per window. This is an upper bound: it excludes cache state, prefetch, synchronization, and the cost of grouping/scattering.

The route trace and summarizer are `/private/tmp/flash-prefill-routes.bin`, [analyze_prefill_routes.py](</Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/tools/analyze_prefill_routes.py), and [prefill-route-overlap-2026-09-28.json](</Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/docs/prefill-route-overlap-2026-09-28.json).

## Current decision

The isolated kernels show that causal GDN chunking, convolution continuation, and true multi-input tiered expert arithmetic are technically promising with the actual model geometry. Production integration is not justified by these isolated results. The current prototype does not yet connect convolution to GDN or run attention, routing, or the production cross-layer command pipeline. The next experiment is a benchmark-only chunk through a real linear-attention/MoE layer, measuring synchronization and cache costs and comparing hidden state against scalar prefill before attempting 1K or 4K prompts.

## Integrated-path inspection and remaining work

The production prefill loop calls `run_all_layers_checked()` once per token; that function runs all 40 layers before the next token. Each `fused_layer_forward()` uses one-token scratch buffers and one global deferred-expert slot. To route and group 16 or 32 real prompt rows at a layer, a benchmark-only path must retain those rows' hidden states through that layer, preserve causal KV/convolution/GDN updates, then group actual K=8 routes and scatter weighted expert results before the next layer. The current isolated probe does none of this.

A simple layer-major loop around the existing one-token forward call would permit route collection, but it would forfeit the current CMD1/CMD2/CMD3 cross-layer GPU handoff and reuse the single deferred-expert slot serially. Its wall time would measure that synchronization penalty rather than the proposed combined path. A representative benchmark needs chunk-sized hidden/routing buffers, a per-chunk command handoff, and a grouped expert dispatch attached to the actual router outputs. Full-attention layers may remain causal/token-wise inside the chunk, but their cost and KV state must be included.

No integrated 1K/4K timing, final-logit comparison, KV-state comparison, or decode-continuation result exists yet. The isolated GDN and expert gains cannot establish an end-to-end speedup or justify production integration.
