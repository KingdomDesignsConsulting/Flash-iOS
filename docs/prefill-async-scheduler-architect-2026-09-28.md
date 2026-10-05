# N-row grouped-MoE async scheduler candidate — Architect note

Date: 2026-09-28

## Scope

This is a benchmark-only follow-up to the validated N=16 full-model prefill prototype. It does **not** change production inference, checkpoint format, session/API behavior, or the normal grouped benchmark unless the additional compile flag `FLASH_PREFILL_NROW_ASYNC` is set.

The candidate source is:

- `metal_infer/prefill_nrow_grouped_async.inc`
- selected from `infer.m` only when both `FLASH_PREFILL_NROW_BENCH` and `FLASH_PREFILL_NROW_ASYNC` are defined.

The previous known-correct benchmark remains `prefill_nrow_grouped.inc` and remains the default benchmark implementation.

## Exact wait-source map from the completed 1,008-token run

The previous result reported 107,662 counted GPU waits.

Those waits decompose exactly as:

| Source | Count | Why |
|---|---:|---|
| Unique routed-expert groups | 105,772 | `prefill_nrow_grouped_layer()` created one command buffer and called `waitUntilCompleted` once for every unique expert group. |
| Chunked linear layers | 1,890 | 63 N=16 chunks × 30 linear-attention layers; `prefill_nrow_linear_layer()` has one layer-level wait because its output is consumed by the CPU-driven row path. |
| **Total** | **107,662** | Matches the benchmark counter exactly. |

The expert waits are an implementation artifact. The layer-level waits are currently required by the CPU-driven layer-major prototype because subsequent CPU work consumes the completed buffers.

## Candidate scheduling change

The old routed-expert path effectively did:

```text
for each unique expert:
    gather assigned rows
    stage/read expert
    encode gate/up/SwiGLU/down
    commit
    CPU wait
    copy output
```

The candidate instead does:

```text
group all 16×8 routed assignments
pack the 128 assignments into disjoint scratch rows
resolve/stage every unique expert's weight buffer
encode every unique expert group into one layer command buffer
commit once
CPU wait once
combine route outputs in original top-K order
```

### Scratch packing

The sum of all group counts is exactly 128 routed assignments, regardless of the number of unique experts. Therefore the candidate uses 128-row scratch slabs instead of allocating 16 rows per possible expert:

- input: `128 × HIDDEN_DIM`
- gate/up/act: `128 × MOE_INTERMEDIATE`
- output: `128 × HIDDEN_DIM`

Each group receives a disjoint `[start, start+count)` range. The existing grouped Metal projection kernel already accepts arbitrary bound buffer offsets, so no Metal-kernel change is required for this first scheduler experiment.

### Expert-weight lifetime safety

Simply deleting the waits from the old code would be incorrect:

1. cold experts all reused `buf_multi_expert_data[0]`, so later `pread()` calls would overwrite bytes still referenced by in-flight GPU commands;
2. inserting hot cache misses before the command completes could evict a cache-hit buffer already referenced by an encoded group.

The candidate avoids both hazards:

- existing hot 4-bit cache **hits** are referenced directly;
- all cold 2-bit groups and hot-cache misses are staged into private, 256-byte-aligned slices of one benchmark-only `expert_stage` Metal buffer;
- hot misses are inserted/copied into the normal malloc cache **after** the layer command buffer completes, preserving cache warming for later chunks without allowing in-flight eviction.

The staging buffer is sized for the theoretical maximum of 128 simultaneous staged unique groups using `max_expert_size_for_current_config()`. For the current 2048×512, group-size-64 geometry this is about 216 MiB at the 4-bit max expert size. This is benchmark-only memory and should be measured on the M4 before considering any production design.

## Expected wait count

For one N=16 chunk on the current 40-layer model:

- 40 routed-MoE layer waits;
- 30 chunked-linear waits;
- expected counted total: 70 waits/chunk.

For the same 1,008-token benchmark (63 chunks):

```text
63 × (40 + 30) = 4,410 waits
```

Compared with the previous 107,662 waits, this is an expected **24.4× reduction** in counted CPU-visible GPU waits.

This is a structural prediction, not a measured speedup. GPU execution may still be slow because:

- QKV remains row-looped;
- full attention remains row-looped;
- o_proj/router work remains row-looped;
- shared-expert down projection remains row-looped;
- the single command buffer still contains many compute encoders;
- serial expert I/O/staging remains in the benchmark prototype;
- production prefetch remains disabled in the existing correctness benchmark.

## First test gate

Do **not** start with the 1K benchmark.

Build the benchmark candidate with the same benchmark flags plus:

```text
-DFLASH_PREFILL_NROW_ASYNC
```

Then run the existing short `--bench-prefill-nrow-grouped` correctness path.

Required checks:

- build succeeds;
- ordinary non-benchmark build still succeeds;
- `git diff --check` passes;
- final hidden/logit tolerances remain within the existing gate;
- next token matches;
- four decode-continuation tokens match;
- KV, convolution and GDN state comparisons pass;
- counted GPU waits drop from ~1,953 to approximately 70 for the combined short path (exact count can vary only if the exercised layer structure differs);
- record short scalar and async N=16 wall time;
- record grouped expert time and shared-expert time;
- record process peak RSS because the benchmark staging slab is intentionally larger.

Only if correctness passes and the wait count collapses as expected should a performance conclusion be drawn.

## 1K gate

Do not rerun 1K solely because the code compiles. Rerun when the short path either:

- approaches scalar wall time, or
- demonstrates the expected order-of-magnitude wait reduction and profiling indicates a plausible remaining optimization path.

For comparison, the previous 1K result was:

```text
Scalar:     72.94 s / 13.82 tok/s
Old N=16:  196.65 s /  5.13 tok/s
Old waits: 107,662
```

If the scheduler candidate remains materially slower after the wait reduction, profile the next dominant components before changing chunk size. The likely next targets are the row-by-row shared expert and QKV projections.

## Production status

No production integration is recommended from this source alone. This candidate has not been compiled or run on Apple Metal by the Architect thread. The Work thread or user must compile and run it on the M4 before the candidate can replace the known-correct benchmark implementation.
