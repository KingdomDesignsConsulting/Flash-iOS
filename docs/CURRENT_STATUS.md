# Flash-iOS current development status

Status: 2026-10-05

This file is the canonical summary of the active `flash-moe-production` development state. Dated architecture and benchmark documents remain historical evidence; when a dated section conflicts with this file, this file describes the current state.

## Repository workflow

- writable fork: `KingdomDesignsConsulting/Flash-iOS`
- active branch: `flash-moe-production`
- `origin`: writable fork
- `upstream`: `Anemll/Flash-iOS`
- upstream is ancestry/reference and must not overwrite newer local work
- meaningful source/documentation changes should be diffed, tested when practical, documented, and committed as focused changes
- do not version models, checkpoints, executables, benchmark logs, caches, temporary test data, credentials, or other generated/private assets

## Current desktop target

Qwen3.5-35B-A3B on Apple Silicon: 40 layers (30 GDN/linear, 10 full-attention), hidden 2048, 256 routed experts, native K=8, MoE hidden 512, tiered Q4/Q2 experts.

## Production N-row prefill

The normal `metal_infer/infer` build remains:

```text
FLASH_PREFILL_NROW_PRODUCTION
FLASH_PREFILL_NROW_ASYNC
FLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT
N=128
1024 routed assignments/slab
gate+up Q4: grouped_tiered_gate_up_m4_8row_q4
gate+up Q2: grouped_tiered_gate_up_m4_8row_q2
routed down: grouped_tiered_projection_m4_2row
expert staging slots: 256
```

`--no-prefill-nrow` remains the scalar fallback. Full 128-token slabs use N128; smaller tails stay scalar; decode is unchanged.

Accepted correctness reference:

```text
hidden_max  = 4.7683716e-06
logits_max  = 5.9604645e-06
next        = 363/363
state_equal = 1
decode_match = 1
tokens      = 363,313,198,262
```

Representative serving results:

```text
4099-token prefill
N64   202.424 s, 20.250 tok/s
N128  185.576 s, 22.088 tok/s

5895-token DSH-scale prefill
N64                 311.808 s, 18.906 tok/s
N128 production     296.349 s, 19.892 tok/s
```

## Major accepted N128 work

- batched N128 full-attention preparation and causal attention
- batched 30-layer linear post-processing (o_proj/residual/post-attn RMSNorm/router/shared gate+up/gate-score)
- grouped routed MoE with accepted gate+up M4-8row fixed-bit Q4/Q2 (bitsplit) and down M4-2row kernels
- parallel expert staging through the existing 8-thread I/O pool
- persistent N-row workspace and production serving integration

Representative later serving measurements reached about 134.98 s / 30.37 tok/s after linear-post batching and about 130.47 s / 31.42 tok/s after parallel staging. Staging is I/O-sensitive, so direct GPU phase timings are preferred for microkernel decisions.

## Rejected/deferred expert experiments

- gate+up M8-2row: rejected; materially slower than M4-8row
- gate+up M4-16row: rejected
- M4-8row cooperative input cache (`xcache`): correctness clean but gate+up about 5.642 s on the 1K test versus roughly 4.33 s for accepted M4-8row
- streaming Zstd checkpoint restore/save: deferred; live compressed restore measured about +314 MiB transient peak RSS, not enough to justify persistence-path complexity now

## Fixed-bit Q4/Q2 gate+up production kernel (`bitsplit`)

Bitsplit keeps accepted M4-8row geometry but selects dedicated fixed-Q4 and fixed-Q2 pipelines, removing dynamic unpack width/mask/shift arithmetic from the inner loop.

Repeated 1K correctness:

```text
hidden_max  = 1.0490417e-05
logits_max  = 1.3828278e-05
next        = 1752/1752
state_equal = 1
```

Bracketed ordinary M4-8row gate+up timings:

```text
baseline A                4339.669 ms
baseline B                4373.211 ms
baseline midpoint         4356.440 ms
```

Repeated bitsplit timings:

```text
bitsplit run 1            4266.738 ms
bitsplit run 2 (warm)     4274.861 ms
bitsplit spread              0.19%
bitsplit average          4270.800 ms
```

That is about a 1.97% gate+up improvement versus the bracketed baseline midpoint.

The subsequent 4K production-style A/B on port 11437 also passed. The final bracket measured:

```text
bitsplit prefill mean      123.818 s
ordinary M4-8row mean      124.914 s
end-to-end improvement        0.88%

bitsplit linear_expert      786.410 / 787.590 ms (final measured pair; mean 787.000 ms)
ordinary linear_expert      799.051 / 803.342 / 816.776 ms (mean 806.390 ms)
linear_expert improvement      2.40% versus the ordinary three-run mean
```

Staging remained I/O/cache-sensitive, but the routed-expert timing stayed directionally consistent with the 1K microbenchmark. **Bitsplit is therefore promoted to the production default** for N128 gate+up. The ordinary M4-8row kernel remains available as an explicit fallback/benchmark candidate.

Build targets:

```text
make n128gateup8bits
make n128serve8bits
```

The separate serving target remains isolated from production `./infer` and is useful for regression/A/B testing on port 11437. Normal production `./infer` now uses bitsplit and continues to serve on port 11436. The normal Makefile selects bitsplit explicitly in `INFER_CFLAGS`; benchmark/diagnostic targets can still select ordinary M4-8row or other candidates without changing the production binary.

## Warm state

Named Flash profiles identify reusable static prefixes while `session_id` identifies resident conversation state. Persistent warm state supports raw and Zstd forms; Zstd level 1 is the default storage representation. The selective compatibility identity excludes transient filesystem device ID but retains state-affecting model/configuration/source/runtime identity.

Measured checkpoint baseline:

```text
raw checkpoint       224.42 MiB
Zstd level 1          88.27 MiB
compressed restore     ~0.44 s benchmark class
```

## Promotion policy

Do not promote a microbenchmark result alone. For state-producing changes use the applicable hidden/logit comparison, exact next-token match, state equality, deterministic continuation, direct GPU phase timing, and an end-to-end serving comparison.

## Production smoke after promotion

The rebuilt normal production `./infer` passed a 4099-token serving smoke test on port 11437 after the bitsplit promotion:

```text
prefill=132.452 s
prefill throughput=30.947 tok/s
linear_expert=808.317 ms
linear_stage=622.779 ms
generated=1 token at 10.47 tok/s
```

The smoke was staging-heavy, but completed normally through 32 N-row chunks with no correctness/runtime failure.

## Pending

1. Physical-iPhone model loading/generation remains separately unvalidated for the current iOS snapshot.
2. Continue profiling the next material N128 bottleneck after the gate+up promotion.
