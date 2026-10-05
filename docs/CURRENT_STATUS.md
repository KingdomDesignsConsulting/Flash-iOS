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
N=128
1024 routed assignments/slab
gate+up: grouped_tiered_gate_up_m4_8row
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
- grouped routed MoE with accepted gate+up M4-8row and down M4-2row kernels
- parallel expert staging through the existing 8-thread I/O pool
- persistent N-row workspace and production serving integration

Representative later serving measurements reached about 134.98 s / 30.37 tok/s after linear-post batching and about 130.47 s / 31.42 tok/s after parallel staging. Staging is I/O-sensitive, so direct GPU phase timings are preferred for microkernel decisions.

## Rejected/deferred expert experiments

- gate+up M8-2row: rejected; materially slower than M4-8row
- gate+up M4-16row: rejected
- M4-8row cooperative input cache (`xcache`): correctness clean but gate+up about 5.642 s on the 1K test versus roughly 4.33 s for accepted M4-8row
- streaming Zstd checkpoint restore/save: deferred; live compressed restore measured about +314 MiB transient peak RSS, not enough to justify persistence-path complexity now

## Fixed-bit Q4/Q2 gate+up candidate (`bitsplit`)

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

That is about a 1.97% gate+up improvement versus the bracketed baseline midpoint. Bitsplit is accepted for production-style 4K serving validation but is **not yet the production default**.

Build targets:

```text
make n128gateup8bits
make n128serve8bits
```

The serving candidate must stay isolated from production `./infer` and production port 11436; serving A/B validation uses port 11437.

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

## Pending

1. 4K serving A/B: ordinary M4-8row vs bitsplit on port 11437.
2. Promote bitsplit only if that end-to-end gate passes; otherwise document/reject it.
3. Physical-iPhone model loading/generation remains separately unvalidated for the current iOS snapshot.
