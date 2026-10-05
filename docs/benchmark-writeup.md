# Benchmarking by Progressive Decomposition

> **Current-status note (2026-10-05):** This is a historical/long-form document. For the authoritative active production configuration, Git workflow, accepted N128 optimizations, rejected experiments, and current bitsplit candidate measurements, see [CURRENT_STATUS.md](CURRENT_STATUS.md). Production is N128 with M4-8row gate+up and M4-2row down. Bitsplit is a correctness-clean ~1.97% gate+up candidate awaiting 4K serving validation and is not yet the production default.


## Purpose

This document describes the benchmarking method we used while optimizing the Flash-iOS N-row prefill path, with particular emphasis on how the benchmark instrumentation became progressively narrower as we tried to locate "missing" time.

The main lesson is that the expensive part of the process was not writing optimizations. It was repeatedly discovering that a supposedly measured component still contained several unrelated subcomponents, or that a large amount of wall-clock time was not attributed to any timer at all.

If starting a similar optimization effort again, the better approach is to instrument the pipeline at a much finer granularity from the beginning so that nearly all wall-clock time is accounted for.

The examples below are from the benchmark-only N=16 prefill path for Qwen3.5-35B-A3B on Apple Silicon.

---

# 1. The original problem: total time told us almost nothing

The earliest useful comparison was simply:

```text
scalar prefill time
vs
N-row prefill time
```

On the original 1008-token benchmark:

```text
scalar: 72936 ms = 13.820 tok/s
N=16:  196654 ms =  5.126 tok/s
ratio: 0.371x
```

Correctness passed, so the problem was performance rather than arithmetic.

At that stage, the benchmark answered only:

> "The N-row implementation is much slower."

It did not tell us why.

The first broad counters were:

```text
group count
repeated expert routes
GPU wait count
expert time
chunked linear-attention time
shared-expert time
grouping time
```

The old 1008-token result showed:

```text
groups = 105772
repeated routes = 216788
GPU waits = 107662

expert = 83680 ms
chunked linear = 26530 ms
shared = 13117 ms
grouping = 7.2 ms
```

This immediately showed two things:

1. CPU grouping itself was essentially free.
2. Synchronization was catastrophic.

The benchmark was still broad, but it had already narrowed the problem from "the model is slow" to "the grouped execution structure is spending enormous time around expert and linear work, with more than 100,000 CPU-visible GPU waits."

---

# 2. First narrowing step: benchmark synchronization separately from arithmetic

## V1 — routed-expert synchronization

The first important architectural change did not try to make the expert math itself faster.

Instead, we changed the submission structure.

Old behavior:

```text
for each unique expert group:
    encode group
    commit command buffer
    wait for completion
```

V1:

```text
for each layer:
    encode all unique expert groups into disjoint scratch ranges
    commit once
    wait once
```

The short benchmark changed from approximately:

```text
1953 counted waits
```

to:

```text
70 counted waits
```

The 70 consisted of:

```text
40 routed-expert layer waits
30 linear-attention layer waits
```

This was an important benchmarking principle:

> Count synchronization events explicitly instead of assuming wall time tells you whether synchronization is expensive.

At this point, `expert_ms` still represented a large composite region, but we had proved that the old synchronization strategy was a major defect.

---

# 3. Second narrowing step: split shared-expert work away from routed experts

After V1, a hidden synchronization cost remained in the shared expert.

The routed-expert counter said only 70 waits, but the shared path was still effectively doing:

```text
16 rows
× 40 layers
= 640 synchronous shared-down submissions
```

Those waits were not included in the historical `gpu_waits` counter.

This was a key lesson:

> A counter can be correct and still give a misleading picture if it does not cover every path that performs the same type of operation.

## V2 — shared-down batching

We kept CPU SwiGLU semantics unchanged, but changed the shared down projection from:

```text
16 independent row submissions
```

to:

```text
16 dispatches encoded into one command buffer
one wait per layer
```

The measured shared component dropped from:

```text
131.731 ms
```

to:

```text
30.205 ms
```

about a 4.36x improvement in that component.

This was the first time the benchmark began acting like a profiler rather than just a throughput test.

---

# 4. Third narrowing step: time the dense projection block separately

After the routed/shared synchronization problems were reduced, the next hidden source of waits was the linear-attention projection block.

The code still effectively did, for every linear-attention layer:

```text
for row in 16:
    RMS norm
    synchronous QKV projection
    synchronous Z projection
    synchronous beta projection
    synchronous alpha projection
```

There are 30 linear-attention layers, so there were roughly:

```text
16 × 30 = 480
```

hidden projection submission/wait cycles per 16-row chunk.

Again, these were not visible in the historical `gpu_waits` counter.

## V3 — batch dense linear-attention projections

V3 changed this into:

```text
CPU RMS norm all 16 rows

one command buffer:
    QKV × 16
    Z × 16
    beta × 16
    alpha × 16
    conv
    GDN-related work

one wait per layer
```

We also added:

```text
linear_ms
```

This was an important instrumentation change.

Before `linear_ms`, we knew the total N-row wall time and some expert/shared times.

After `linear_ms`, we could say:

```text
all 30 linear-attention layers together cost only about 125–139 ms
```

on the short benchmark.

That immediately told us:

> Linear attention was no longer the dominant short-path problem.

Without the component timer, we could easily have spent another iteration optimizing the wrong code.

---

# 5. Fourth narrowing step: split full-attention projections from the rest of full attention

After V3, a large amount of time was still unaccounted for.

The 10 full-attention layers were still executing row by row:

```text
10 layers × 16 rows = 160 row calls
```

Each row performed its own Q/K/V projections.

## V4 — batch full-attention Q/K/V

V4 precomputed Q/K/V for all 16 rows in one command buffer per full-attention layer.

The downstream path remained unchanged:

```text
Q/K normalization
RoPE
KV publication
causal attention
Q gate
o_proj
residual
post-attention norm
router
shared gate/up capture
```

Instead of adding a single broad "full attention" timer, we added two:

```text
full_qkv_ms
full_attn_ms
```

where:

```text
full_qkv_ms =
    16-row input RMS norm
    + Q/K/V batch projection
    + projection wait

full_attn_ms =
    full_qkv_ms
    + all remaining row-wise full-attention work
```

This gave us a directly derived value:

```text
full_attn_downstream_ms =
    full_attn_ms - full_qkv_ms
```

On the controlled 1008-token V4 benchmark, the median was approximately:

```text
full_qkv_ms = 1603 ms
full_attn_ms = 8522 ms

downstream full attention =
8522 - 1603
= 6919 ms
```

That one subtraction told us that Q/K/V projection was no longer the main full-attention cost.

The remaining row-wise full-attention work was about 4.3x larger than Q/K/V itself.

---

# 6. Controlled benchmark design became increasingly important

During short tests we discovered that scalar timings could move dramatically depending on prompt, cache state, ordering, and expert reuse.

That made broad "speedup" claims unreliable.

We therefore moved to a fixed 1008-token binary token fixture:

```text
token[i] = 1000 + ((73 * i) % 1000)
```

Both scalar and N=16 arms started from the same captured empty state.

The benchmark code disabled expert prefetch in both arms.

This let us compare the exact same token sequence over time.

The original old N=16 result was:

```text
scalar = 13.820 tok/s
N=16   =  5.126 tok/s
```

By V4, the same fixture produced median values of approximately:

```text
scalar = 17.848 tok/s
N=16   = 17.663 tok/s
ratio  = 0.996x
```

The most important conclusion was not "V4 is faster than scalar."

It was:

> The original N-row synchronization penalty had essentially been eliminated.

That meant the benchmark could now be used to investigate actual arithmetic and memory costs rather than gross orchestration defects.

---

# 7. The next problem: measured components still did not add up to wall time

At V4 1K, median component times were approximately:

```text
linear_ms                7501 ms
full_attn_ms             8522 ms
expert_ms               19816 ms
shared_ms                1319 ms
grouping_ms                 6 ms
```

Their rough sum was:

```text
~37.2 seconds
```

but total N-row wall time was:

```text
~57.1 seconds
```

So roughly:

```text
~20 seconds
```

was still not directly attributed.

This was exactly the same pattern we had encountered repeatedly:

1. optimize a broad region;
2. add a timer around it;
3. discover that the unmeasured remainder is now the important part;
4. subdivide again.

This is the iterative narrowing process the other thread can skip.

---

# 8. V5: instrument the previously unmeasured pieces directly

At this point we added several narrower timers at once instead of waiting for another iteration.

## `expert_stage_ms`

Measures work before the grouped expert GPU command:

```text
expert lookup
cache lookup
hot/cold classification
pread of cold experts
pread of hot-cache misses
copy/staging into expert_stage
```

This separates storage/cache preparation from GPU expert arithmetic.

## `expert_ms`

Measures the grouped routed-expert GPU execution itself.

It should no longer be interpreted as "all expert-related time."

## `expert_cache_ms`

Measures post-GPU cache insertion/copy work for hot misses.

This catches another previously hidden CPU/memory region.

## `combine_ms`

Measures the CPU final routed/shared weighted accumulation.

This is nested inside `shared_ms`.

That nesting is intentional.

It allows both:

```text
shared total
```

and:

```text
CPU combine portion of shared total
```

to be known.

Do not sum both independently.

## `linear_post_ms`

Measures the row-wise `fused_layer_forward()` work that remains on linear-attention layers after the N-row linear helper has already completed the recurrent/dense block.

This was one of the major missing regions in V4.

---

# 9. Kernel-level instrumentation followed architectural instrumentation

Once orchestration overhead was mostly controlled, we inspected the actual grouped expert kernel.

The kernel already does real cross-row reuse:

```text
decode one quantized expert weight
apply it to every row in that expert group
```

So expert time was not merely duplicated weight decoding.

However, we found:

```metal
float acc[64];
```

per SIMD lane.

The host guarantees:

```text
group_count <= 16
```

and rejects larger groups.

So V5 reduced it to:

```metal
float acc[16];
```

The goal is to reduce register/private-memory pressure and possible spills.

The important benchmarking principle here is:

> Do not micro-optimize kernels until the benchmark has already proved that kernel execution itself is a dominant component.

Earlier in the project, an expert-kernel micro-optimization would have been largely hidden by synchronization and orchestration costs.

By V5, `expert_ms` was approximately 19.8 seconds of a 57-second benchmark, so it had become a justified target.

---

# 10. What we should have instrumented from the beginning

For a new optimization thread, skip the progressive discovery process and start with a near-complete timing decomposition.

The objective should be:

```text
total wall time
≈
sum of mutually understood component regions
+
small known bookkeeping remainder
```

Do not expect exact equality if timers overlap.

Instead, label timers explicitly as either:

```text
exclusive
inclusive
nested
```

---

# 11. Recommended full benchmark timer map

The following timer layout would have saved us many iterations.

## A. Top-level wall times

```text
total_scalar_ms
total_nrow_ms
```

Also record:

```text
tokens
tokens_per_second
ratio
```

---

## B. Per-layer-family totals

```text
linear_layer_total_ms
full_attention_layer_total_ms
moe_layer_total_ms
```

These should be inclusive family-level timers.

---

## C. Linear-attention decomposition

Recommended:

```text
linear_input_norm_ms
linear_projection_ms
linear_conv_ms
linear_qk_norm_ms
linear_decay_beta_ms
linear_split_qkv_ms
linear_gdn_ms
linear_gated_norm_ms

linear_post_ms
```

If command-buffer boundaries make individual GPU stage timing expensive, at minimum use:

```text
linear_projection_ms
linear_recurrence_ms
linear_post_ms
```

where:

```text
linear_recurrence_ms =
    conv
    + Q/K normalization
    + decay/beta
    + split
    + GDN
    + gated norm
```

---

## D. Full-attention decomposition

Recommended:

```text
full_input_norm_ms
full_qkv_ms
full_qk_norm_ms
full_rope_ms
full_kv_publish_ms
full_attention_kernel_ms
full_q_gate_ms
full_oproj_ms
full_residual_ms
full_post_norm_ms
full_router_ms
full_shared_gate_up_ms
```

At minimum:

```text
full_qkv_ms
full_attention_core_ms
full_oproj_post_ms
full_router_capture_ms
```

The V4 benchmark only had:

```text
full_qkv_ms
full_attn_ms
```

which was enough to identify a 6.9-second downstream remainder, but not enough to tell which downstream operation owns it.

The next implementation should skip that intermediate stage and split downstream attention immediately.

---

# 12. Routed MoE decomposition

This should be highly detailed because MoE combines I/O, cache management, CPU grouping, GPU arithmetic, and CPU reduction.

Recommended:

```text
route_group_build_ms
assignment_pack_ms

expert_cache_lookup_ms
expert_pread_ms
expert_stage_copy_ms

expert_gpu_gate_ms
expert_gpu_up_ms
expert_gpu_swiglu_ms
expert_gpu_down_ms

expert_gpu_total_ms

expert_cache_insert_ms

routed_weighted_combine_ms
```

Also record structural quantities:

```text
route assignments
unique groups
repeated routes

group-size histogram:
    count=1
    count=2
    count=3-4
    count=5-8
    count=9-16

hot groups
cold groups
cache hits
cache misses

bytes read from disk
bytes staged
bytes copied into hot cache
```

This last group-size histogram is especially useful.

The theoretical benefit of grouped expert arithmetic depends heavily on whether most expert groups contain:

```text
1 row
```

or:

```text
many rows
```

A total `groups` count is not enough to understand weight reuse efficiency.

---

# 13. Shared-expert decomposition

Recommended:

```text
shared_gate_up_ms
shared_swiglu_ms
shared_down_ms
shared_combine_ms
shared_total_ms
```

Mark:

```text
shared_combine_ms
```

as nested inside `shared_total_ms`.

---

# 14. CPU/GPU synchronization accounting

Do not maintain only one generic wait counter.

Record waits by category:

```text
wait_routed_expert
wait_shared_expert
wait_linear_projection
wait_linear_recurrence
wait_full_qkv
wait_full_attention
wait_oproj
wait_other
```

Also record command-buffer counts separately:

```text
cmd_routed_expert
cmd_linear
cmd_full_qkv
cmd_full_attention
cmd_shared
```

A command-buffer count and a CPU-visible wait count are not the same thing.

That distinction mattered repeatedly in our work.

---

# 15. I/O and memory-movement accounting

Once kernel execution becomes efficient, storage and memory traffic can become dominant.

Recommended counters:

```text
expert_pread_calls
expert_pread_bytes
expert_pread_ms

expert_stage_memcpy_bytes
expert_stage_memcpy_ms

hot_cache_insert_bytes
hot_cache_insert_ms

CPU->shared-buffer bytes
shared-buffer->CPU bytes
```

For long benchmarks, also report:

```text
effective expert read bandwidth
effective staging bandwidth
```

---

# 16. Correctness must remain part of every performance benchmark

Every optimization benchmark should continue to report:

```text
hidden max diff
logits max diff
same next token
decode continuation equality
state_equal
KV max diff
conv-state max diff
GDN/SSM-state max diff
```

Performance data without state equivalence is not useful for this project.

This mattered particularly because the model has:

```text
full-attention KV state
convolution state
GatedDeltaNet recurrent state
```

A path can produce plausible logits while leaving future recurrent state wrong.

---

# 17. Use controlled fixtures earlier

The other thread should avoid natural-language prompts for serious performance comparisons.

Use:

```text
binary token fixtures
fixed token count
fixed token IDs
same initial state
same prefetch setting
same cache policy
same run order where possible
```

For this project the canonical controlled fixture is:

```text
1008 tokens
token[i] = 1000 + ((73 * i) % 1000)
```

The short natural-language benchmark is useful for fast correctness gating, but not as the primary throughput benchmark.

---

# 18. Always report raw repetitions

Do not report only an average.

We repeatedly saw cache/order outliers.

Use at least:

```text
run 1
run 2
run 3
median
```

Keep all raw values.

If one run is anomalous, preserve it and explain that it is an outlier rather than deleting it.

---

# 19. Add an "unaccounted time" line to every report

This is the most useful thing the other thread can add immediately.

For each run compute something like:

```text
known_exclusive_ms =
    linear_helper_ms
    + linear_post_ms
    + full_attention_ms
    + expert_stage_ms
    + expert_gpu_ms
    + expert_cache_ms
    + shared_ms
    + grouping_ms
```

Then:

```text
unaccounted_ms =
    total_nrow_ms - known_exclusive_ms
```

and:

```text
unaccounted_percent =
    unaccounted_ms / total_nrow_ms * 100
```

Be careful not to double-count nested timers such as:

```text
combine_ms inside shared_ms
full_qkv_ms inside full_attn_ms
```

A healthy late-stage benchmark should make:

```text
unaccounted_percent
```

small.

If it is still 20–30%, do not immediately optimize the largest measured region.

First instrument the missing time.

---

# 20. Recommended timer hierarchy

A useful way to implement this is with a hierarchy.

Example:

```text
TOTAL NROW
|
+-- LINEAR LAYERS
|   |
|   +-- input norm
|   +-- dense projections
|   +-- conv/GDN recurrent block
|   +-- row-wise post path
|
+-- FULL ATTENTION
|   |
|   +-- input norm
|   +-- QKV
|   +-- QK norm + RoPE
|   +-- KV publish
|   +-- causal attention
|   +-- q gate
|   +-- o_proj
|   +-- residual/post norm
|   +-- router/shared capture
|
+-- ROUTED EXPERTS
|   |
|   +-- grouping
|   +-- assignment packing
|   +-- cache lookup
|   +-- pread
|   +-- stage copy
|   +-- GPU gate
|   +-- GPU up
|   +-- GPU SwiGLU
|   +-- GPU down
|   +-- cache insertion
|
+-- SHARED EXPERT
|   |
|   +-- activation
|   +-- down projection
|   +-- final combine
|
+-- OTHER
    |
    +-- snapshots/state copying
    +-- command-buffer setup
    +-- benchmark bookkeeping
```

Ideally, every top-level child of `TOTAL NROW` is exclusive.

Fine-grained nested timers can then live under those children.

---

# 21. Why this is better than "optimize the largest timer"

The largest timer can be misleading if it is inclusive.

For example:

```text
full_attn_ms
```

contained:

```text
full_qkv_ms
```

So optimizing both independently and adding their savings would double-count.

Similarly:

```text
shared_ms
```

contains:

```text
combine_ms
```

The report should always distinguish:

```text
inclusive timer
exclusive timer
nested sub-timer
```

Otherwise the benchmark eventually becomes internally inconsistent.

---

# 22. What the other thread should do immediately

If the goal is to skip our iterative narrowing process, instrument the target path before further optimization.

At minimum add:

```text
TOTAL
scalar_ms
nrow_ms

LINEAR
linear_projection_ms
linear_recurrence_ms
linear_post_ms

FULL ATTENTION
full_qkv_ms
full_qk_rope_ms
full_kv_attention_ms
full_oproj_post_ms
full_router_capture_ms

ROUTED EXPERT
route_group_ms
assignment_pack_ms
expert_cache_lookup_ms
expert_pread_ms
expert_stage_copy_ms
expert_gpu_ms
expert_cache_insert_ms

SHARED / COMBINE
shared_activation_ms
shared_down_ms
combine_ms

STRUCTURE
command buffers by category
waits by category
expert group-size histogram
bytes read/staged/copied

REMAINDER
unaccounted_ms
unaccounted_percent
```

Then run:

```text
one short correctness fixture
three controlled 1008-token runs
```

Only after seeing that report should another optimization be chosen.

---

# 23. Current benchmark state at the time of this writeup

The progression was approximately:

```text
Old prototype
    ↓
find 107k waits
    ↓
V1: one routed-expert wait/layer
    ↓
find hidden shared waits
    ↓
V2: batch shared-down
    ↓
find hidden linear projection waits
    ↓
V3: batch linear dense projections
    ↓
measure linear_ms
    ↓
find row-wise full-attention QKV
    ↓
V4: batch full-attention QKV
    ↓
measure full_qkv_ms + full_attn_ms
    ↓
controlled 1K reaches scalar parity
    ↓
find routed experts now largest measured component
    ↓
V5: reduce grouped-kernel accumulator footprint
    + add expert_stage/cache/combine/linear_post timers
```

The important meta-pattern was:

```text
broad wall time
→ broad component timer
→ subcomponent timer
→ synchronization counter
→ I/O/cache timer
→ kernel-level timer
→ unaccounted-time analysis
```

Each iteration reduced the size of the unknown region.

---

# 24. Main takeaway

The benchmarking strategy that ultimately worked was not:

> "benchmark every optimization."

It was:

> "make the benchmark explain almost all of the wall-clock time."

Once the benchmark can account for nearly every millisecond, optimization becomes much less speculative.

Instead of asking:

```text
What should we optimize next?
```

the report should make the answer obvious:

```text
Where is the time?
```

For future work, build that level of instrumentation first.

It is cheaper than rediscovering it one bottleneck at a time.

---

# 25. Update — accepted N32 / fixed-M4 expert path (2026-10-01)

The benchmark path has advanced substantially beyond the V5 state described above. The current accepted benchmark configuration is still isolated from production, but now uses a 32-row slab and fixed-small-M kernels for both routed gate+up and routed down.

Current accepted benchmark geometry:

```text
slab rows:                32
routed assignments/slab:  32 × 8 = 256
gate+up:                  fixed M=4, 2 SIMD groups / 64 threads per TG
down:                     fixed M=4, 2 SIMD groups / 64 threads per TG
quantization:             native tiered Q4/Q2
1K fixture:               1024 tokens
fixture sequence:         token[i] = 1000 + ((73*i) % 1000)
```

The accepted routed-down kernel is selected with:

```text
FLASH_PREFILL_NROW_DOWN_M4_2ROW
```

The accepted routed gate+up candidate is selected with:

```text
FLASH_PREFILL_NROW_GATEUP_M4_2ROW
```

At this point in the experiment chronology both were benchmark-only; the accepted V13B/V12C kernels are now also used by the production N64 path described in §§25.5–25.6.

## 25.1 Routed-down progression

The routed-down sequence established that compiler-visible fixed-small-M geometry mattered more than simply packing larger workgroups:

```text
V11 acc32                       5422.360 ms
V12A M4 / 1 SIMD / 32 threads  4931.185 ms
V12C M4 / 2 SIMD / 64 threads  4783.718 ms  accepted
V12B M4 / 4 SIMD / 128 threads 4984.232 ms  rejected
```

V12C's accepted clean median excludes one clearly system-wide slow run. Its clean runs were 4756.654 / 4883.341 / 4783.718 ms, giving a median of 4783.718 ms, about 2.99% faster than V12A.

The important interpretation is not that larger threadgroups are always better. The 64-thread midpoint won; the 128-thread form regressed. The kernel already reused each decoded packed weight across the active rows in an expert group, so the gain came from fixed-M code shape / scheduling rather than introducing weight reuse for the first time.

## 25.2 N16 → N32 slab experiment

V13A rebuilt the accepted V12C path against a common 1024-token fixture and compared N16 with N32. All six runs passed correctness.

Median N16 → N32:

```text
nrow_ms                  49089.076 -> 48502.435   -1.20%
expert_ms                14236.038 -> 13877.178   -2.52%
expert_down_gpu_ms        4977.319 ->  4515.876   -9.27%
Q4 down                    858.257 ->   723.871  -15.66%
Q2 down                   4119.062 ->  3792.005   -7.94%
shared_ms                 1254.564 ->   896.648  -28.53%
expert_gate_up_gpu_ms     7262.618 ->  8256.407  +13.68%
```

For the same total routed assignment count, N32 reduced unique routed expert groups from 107,492 to 74,701 and reduced counted GPU waits from 4,480 to 2,240. The larger slab therefore exposed denser expert-major work, but the old dynamic gate+up kernel became the new bottleneck.

## 25.3 V13B fixed-M4 gate+up

V13B replaced the dynamic `gate_acc[64]` / `up_acc[64]` gate+up kernel with a fixed-M=4 kernel using the same accepted 2-SIMD / 64-thread geometry as V12C down.

Three 1024-token runs passed exact correctness:

```text
hidden_max  = 1.0490417e-05
logits_max  = 1.3828278e-05
next        = 1752/1752
state_equal = 1
```

V13B gate+up GPU runs:

```text
5405.997 ms
5303.633 ms
5327.446 ms
median = 5327.446 ms
```

Compared with the V13A N32 median of 8256.407 ms, fixed-M4 gate+up is 35.48% faster.

The rest of the expert path remained stable:

```text
metric                    V13A N32     V13B median     change
gate+up GPU               8256.407      5327.446      -35.48%
down GPU                  4515.876      4525.955       +0.22%
expert total             13877.178     10974.525      -20.92%
N-row total              48502.435     46962.990       -3.17%
N-row throughput            21.112        21.804       +3.28%
```

This is a clean isolation result: the large improvement is in gate+up while routed down remains essentially unchanged.

## 25.4 Current optimization lesson

The current evidence favors this sequence:

```text
increase slab size to expose more expert-major reuse
→ measure which expert phase regresses
→ specialize that phase for compiler-visible small M
→ retain only geometries that improve direct GPU component time
```

Activity Monitor also shows substantial unused GPU headroom during Flash relative to more naturally parallel workloads. That visual signal is useful, but acceptance decisions continue to use direct GPU phase timing rather than utilization percentage alone.

At this point in the experiment chronology, the next planned gate was N64 / larger expert-major work. That gate has since been completed and accepted; see §§25.5–25.6. The Q36-style matrix-multiply crossover remains future research.



## 25.5 V14A N64 — accepted

V14A widened only the slab from N32 to N64 while retaining the accepted
fixed-M4 / 2-SIMD expert kernels. The common 1024-token fixture is divisible by
64, so this was a direct slab-width comparison with no remainder confound.

Three successful N64 benchmark runs passed the established exact correctness
gate:

```text
hidden_max  = 1.0490417e-05
logits_max  = 1.3828278e-05
next        = 1752/1752
state_equal = 1
```

Accepted N64 medians:

```text
nrow_ms                  44171.393
nrow_tps                    23.182
expert_ms                10123.869
expert_gate_up_gpu_ms      5250.445
expert_down_gpu_ms         4174.042
Q4 down                     632.239
Q2 down                    3541.803
groups                        49812
repeated                     277868
gpu_waits                      1120
```

Relative to accepted V13B N32:

```text
nrow_ms      46962.990 -> 44171.393   -5.94%
nrow_tps        21.804 ->    23.182   +6.32%
expert_ms    10974.525 -> 10123.869   -7.75%
gate+up GPU   5327.446 ->  5250.445   -1.45%
down GPU      4525.955 ->  4174.042   -7.78%
groups           74701 ->     49812  -33.32%
repeated        252979 ->    277868   +9.84%
gpu_waits          2240 ->      1120  -50.00%
```

The same routed assignment count is therefore represented by substantially
fewer unique expert groups. N64 exposes more expert-major reuse and cuts the
counted slab/layer synchronization points in half.

The production-form single-command-buffer expert path was then tested twice
without the phase-timing/Q4-Q2 diagnostic command-buffer split. It retained the
same exact correctness result and produced 23.339 and 23.302 tok/s.

## 25.6 Production integration — accepted default

The accepted production geometry is now:

```text
slab                      N64
routed assignments/slab   512
gate+up                    grouped_tiered_gate_up_m4_2row
down                       grouped_tiered_projection_m4_2row
tile                       M=4
threadgroup                64 threads / 2 SIMD groups
expert format              native tiered Q4/Q2
remainder                  scalar fallback
decode                     unchanged
```

Real HTTP serving on a 211-token actual-prefill request exercised three full
N64 slabs (192 tokens) plus a 19-token scalar remainder. The warmed comparison
from the same production-capable code was:

```text
scalar warmed: 15611.806 ms, 13.515 tok/s
N64 warmed:     8443.312 ms, 24.990 tok/s
```

That is a 45.9% reduction in measured prefill latency and an 84.9% increase in
reported prompt-prefill throughput for this request. Generated output matched
between scalar and N64.

Production staging is allocated once per possible unique expert, not once per
route assignment:

```text
stage_slots = min(g_cfg.num_experts, PREFILL_NROW_ASSIGNMENTS)
```

For the current model this is 256 slots rather than 512, reducing the N64 expert
staging allocation from roughly 864 MiB to roughly 432 MiB.

Session continuation was also checked. A first turn containing one N64 slab
created session state at position 90; the second request reused all 90 cached
tokens (`session_reused=1`) and prefetched only 37 new scalar tokens. A scalar
control reproduced the same continuation output, so no N64-specific
state-handoff discrepancy was observed.

The normal Makefile `infer` target now compiles
`FLASH_PREFILL_NROW_PRODUCTION` + `FLASH_PREFILL_NROW_ASYNC`, and N64 is the
runtime default. `--no-prefill-nrow` remains the immediate scalar fallback.

Future N96/N128 work is experimental and should not block use of the accepted
N64 production path.
