# N-row prefill architecture map — 2026-09-28

> **Current-status note (2026-10-05):** This is a historical/long-form document. For the authoritative active production configuration, Git workflow, accepted N128 optimizations, rejected experiments, and current bitsplit candidate measurements, see [CURRENT_STATUS.md](CURRENT_STATUS.md). Production is N128 with M4-8row gate+up and M4-2row down. Bitsplit is a correctness-clean ~1.97% gate+up candidate awaiting 4K serving validation and is not yet the production default.


Target: the loaded Qwen3.5-35B-A3B model, `N=16`, 40 layers, K=8, 32 value heads and 16 key heads. This note describes a benchmark-only path. It does not change the serving path or persistent state.

| Subsystem | Current one-row assumption | Minimum N-row treatment |
|---|---|---|
| Embedding | `embed_lookup` fills one 2,048-float vector; CLI/HTTP already pre-embed many rows into a contiguous buffer. | Reuse contiguous `[N][2048]` embeddings as the initial activation slab. No new embedding kernel is required. |
| Input norm, residual, post-attention norm | CPU scratch and GPU `buf_input`, `buf_residual`, `buf_h_mid`, `buf_moe_hidden` each hold one row. | Carry `[N][2048]` hidden and residual rows. Row-looped norms are an acceptable first pass; retain rows until all routed outputs for a layer are combined. |
| Q/K/V and o_proj | Projection specs and `batch_out[]` target one row; CMD1/CMD2 hand off through shared one-row buffers. | Widen projections or keep a measured row loop within each layer. A direct GPU row slab is required to preserve the current handoff without readback for every row. |
| Full attention | One Q row and one KV append per call; KV cache is persistent and position indexed. | Process rows in causal order within each full-attention layer. Each row sees the prior prefix and earlier rows in this chunk. Keep existing KV layout and compare final KV state. |
| Convolution and GDN | Each linear-attention call mutates the per-layer tail and recurrent state for one row. | Feed the N QKV rows to the validated chunked convolution/GDN kernels in causal order. No checkpoint-format change. |
| Router | One 256-logit row and one top-K list. | Store `[N][8]` expert IDs and weights, plus `[N][2048]` post-norm expert inputs. CPU grouping is acceptable initially and must be timed. |
| Expert staging | One row's eight experts in `buf_multi_expert_*`; hot experts use the malloc cache, cold 2-bit experts use scratch. | Stage each unique `(layer,expert)` once per chunk where cache capacity permits, retaining packed 4-bit/2-bit data and the current cache policy. Record cache hits/misses and bytes. |
| Routed expert arithmetic | One input vector per expert dispatch. | Gather rows assigned to an expert and use the grouped packed-weight projection/SwiGLU/down kernels once for that expert group; scatter weighted outputs to their source rows. |
| Shared expert | One gate/up/activation/down output, executed alongside routed experts in CMD3. | Retain its projection outputs per row. A measured row loop is acceptable for the first proof, but it must stay inside the layer-major N-row path. |
| Deferred CMD3 | One global `g_deferred` slot and one hidden pointer; next layer consumes its result. | Replace with per-chunk row metadata and one completion point per layer. Preserve GPU command dependencies where possible; count any CPU waits and readbacks. |
| Final norm and LM head | One final hidden row and one logits row are used for prompt completion. | Apply final norm/LM head only to the final prompt row for timing; optionally compute comparison rows for correctness. |

The existing `target_verify_grouped.inc` is a useful scalar layer-major baseline: it carries multiple hidden rows through all 40 layers, but calls `fused_layer_forward()` once per row and immediately completes each deferred expert command. It does not execute grouped multi-input MoE and loses the production cross-layer GPU handoff. Its timings cannot stand in for the requested integrated N-row result.

The minimum integrated path needs two new boundaries within each layer: (1) complete attention, o_proj, post-attention norm, shared projections, and top-K routing for all rows while preserving causal state; (2) group and execute routed experts, combine their outputs with the shared expert, and advance the entire hidden slab to the next layer. The present `fused_layer_forward()` contains both boundaries inside one large call, so a benchmark-only split or capture hook is required. A generic tensor framework or production refactor is unnecessary.

First correctness gate: compare a short deterministic prompt against scalar prefill for final hidden, logits, next token, final KV/GDN/convolution state, and several deterministic decode steps. Only then measure uncached 1K prefill. Record route-grouping time, GPU waits, command-buffer count, cache hit/miss counts, and incremental memory, since the initial CPU grouping may negate kernel gains.

## Initial 16-row control (2026-09-28 13:37:44–13:38:08 PDT)

The benchmark-only `--bench-prefill-nrow-control` path carries a contiguous 16×2,048 hidden slab through all 40 layers using the existing one-row `fused_layer_forward()` inside each layer. It is compiled only with `FLASH_PREFILL_NROW_BENCH`; the production binary has no such option. This is an activation-order and state-correctness control, not the grouped expert or chunked GDN implementation.

The CLI prompt began `Count these words and describe the pattern: cedar river stone...` and tokenized to 50 tokens. The control compared its first 16 tokens against scalar token-major prefill. Final hidden maximum absolute difference was `7.1525574e-06`; logits difference was `9.7751617e-06`; both selected token `4105`. The existing layer-state report passed with maximum KV difference `1.14441e-05`, GPU convolution difference `2.67029e-05`, and GPU GDN difference `1.90735e-05`. Four deterministic decode tokens matched: `4105, 25, 328, 14556`. The N-row hidden slab used 131,072 bytes.

The first scalar trial took 4,036.623 ms and the immediately following layer-major trial took 1,015.271 ms. This is **not** a controlled speed comparison: the scalar trial warmed the expert cache for the second trial. No grouped multi-input expert kernel or chunked GDN/convolution kernel participated in this control.

## Grouped full-model correctness prototype

`--bench-prefill-nrow-grouped` uses the same 16-row hidden slab and the real per-row attention, o_proj, router, and shared-expert projections. A benchmark-only capture point after top-K routing stores 16×8 expert assignments and the corresponding post-norm inputs. The executor groups assignments by expert, reads the native tiered 4-bit or 2-bit packed representation, performs one multi-input gate/up/SwiGLU/down kernel sequence per unique expert, scatters outputs to their original route slots, and accumulates slots in top-K order. Hot weights use the existing malloc cache; cold weights use the existing scratch buffer. Shared expert down projection remains a measured row loop. The current production one-row convolution/GDN kernels still run for each row; the isolated chunked versions are not connected to this full-model path yet.

The first test used prompt positions 0–15. It matched scalar final hidden (`4.0531158e-06` maximum difference), logits (`8.3446503e-06`), next token `4105`, all state classes within the existing state-report tolerance, and four decode tokens `4105,25,328,14556`. Across 40 layers it grouped 5,120 routed assignments into 2,142 expert groups, with 2,978 repeated assignments. It made 2,142 GPU waits. Grouped expert execution took 825.971 ms and the row-looped shared path 126.396 ms. The route-grouping CPU loop took 0.083 ms. These component numbers include the temporary per-expert synchronization design.

The second test first processed 32 prefix tokens and compared positions 32–47. It matched scalar final hidden (`3.9935112e-06`), logits (`3.6239624e-05`), next token `248069`, state-report tolerances, and four decode tokens `248069,271,8160,369`. It grouped 5,120 assignments into 1,923 expert groups (3,197 repeated), including 629 hot and 1,294 cold groups. It made 1,923 GPU waits; grouped expert execution took 783.866 ms, shared work 126.498 ms, and CPU grouping 0.077 ms.

For the prefixed test, scalar trial wall time was 2,058.822 ms and grouped layer-major trial wall time was 1,533.204 ms. The order was fixed and cache state differed, so these are **not** a valid speedup comparison. Expert prefetch was disabled in both arms while the capture path is active; this also prevents a production-equivalent throughput claim. The slab itself used 131,072 bytes, with additional grouped input/output buffers and about 1 MiB for per-route outputs. A complete peak-RSS measurement has not been taken.

The final N=16 prototype also collects QKV/Z/beta/alpha for all rows, runs the corrected 32-value-head chunked convolution and GDN kernels, and feeds the 16 resulting outputs to the existing o_proj/router path. QKV projection, full attention, o_proj/router, and shared-expert projection still contain per-row work inside the layer-major chunk. The route executor genuinely shares one packed expert representation across the rows assigned to each expert, but waits after each unique expert command. This is a complete model path with important scalar subpaths, not an optimized all-kernel N-row implementation.

## Combined chunked-linear and grouped-expert correctness

The short 50-token prompt tested positions 32–47 on 2026-09-28 at 13:50 PDT. The combined path matched scalar final hidden (maximum difference `3.9935112e-06`), logits (`3.6239624e-05`), next token `248069`, and four decode continuation tokens `248069,271,8160,369`. The state report passed: KV maximum `1.69277e-05`, GPU convolution `2.86102e-05`, GPU GDN `4.29153e-06`. It used 1,953 GPU waits, including 30 chunked-linear layer waits. The scalar arm took 2,436 ms and the N-row arm 3,351 ms; order/cache effects make this a diagnostic, not a stable performance estimate.

## First full-model 1K gate

The isolated `--bench-prefill-nrow-1k` binary compared both paths from the same empty state on a reproducible synthetic 1,008-token prompt (`id[i] = 1000 + (73*i mod 1000)`). The command started at 13:53:00 PDT and finished by 13:57:53 PDT on 2026-09-28. Neither path restored a warm prefix. Expert prefetch was disabled in **both** arms because the capture prototype cannot preserve production's prefetch behavior. Scalar ran first, N-row second, so the N-row arm could benefit from a warmer expert cache; no warm repeated median was collected after the negative first gate.

| Path | Chunk | Time | Prompt tok/s | Relative throughput |
|---|---:|---:|---:|---:|
| Scalar | 1 | 72,936 ms | 13.820 | 1.00× |
| Combined N-row | 16 | 196,654 ms | 5.126 | 0.371× |

The N-row result retained correct model state and output: final hidden maximum difference `1.7166138e-05`, logits `1.5258789e-05`, same next token `1584`, KV `3.33786e-05`, GPU convolution `2.28882e-05`, and GPU GDN `1.43051e-05`. The benchmark did not run a decode continuation for this 1K case; the short combined test did.

Across 63 chunks and 40 layers, 322,560 routed assignments collapsed to 105,772 unique expert groups (216,788 repeats). The prototype performed 107,662 counted GPU waits, of which 1,890 were chunked-linear waits. Expert execution took 83,680 ms, chunked-linear preparation 26,530 ms, shared-expert row work 13,117 ms, and CPU route grouping 7.2 ms. Hot and cold group counts were 23,141 and 82,631. The malloc expert cache reported 13,336 hits and 9,805 misses. These components overlap imperfectly with total wall time and leave substantial per-row attention/router, command handling, and other work uninstrumented. The 16×2,048 activation slab is 128 KiB. The grouped path adds several MiB of temporary Metal buffers and about 1 MiB of per-route output; whole-process peak memory was not measured. The correctness harness also holds full state snapshots, which are outside the path's normal activation footprint.

The result is materially slower even with the second-arm cache advantage. The immediate limits are the 107,662 per-group synchronization points, serial full-attention/o_proj/router work, and row-looped QKV projection. The current architecture loses the production CMD1→CMD2/CMD3 handoff. Per the prescribed negative gate, N=32 and 4K were not run. TTFT was not separately measured; these prefill times end before the final LM head. No production integration is recommended from this prototype.

The benchmark code remains under `FLASH_PREFILL_NROW_BENCH`. The ordinary build compiled successfully without the flag, `git diff --check` passed, the `main-agent` checkpoint SHA-256 remained `00dd9742a8764b9ace6b26067ab78a8187d8d98164fa0098d1e450c20595c284`, and no isolated test server was started (port 11437 had no listener).

---

## Current implementation status — 2026-10-01

This note began as the N=16 architecture plan. The benchmark implementation has since progressed to an accepted N=32 slab and fixed-small-M routed expert kernels. The original sections above remain useful as historical architecture context; this section records the current benchmark state.

### Current benchmark slab

```text
PREFILL_NROW_CAPTURE_ROWS = 32   (with FLASH_PREFILL_NROW_N32)
K                          = 8
routed assignments/slab    = 256
full-prompt fixture         = 1024 tokens
```

The 1024-token fixture uses:

```text
token[i] = 1000 + ((73 * i) % 1000)
```

so it is divisible by both N16 and N32 and supports a clean slab-width A/B.

### Current routed expert organization

The capture path still records per-row top-K routing and post-norm expert inputs, then groups assignments by expert. With N32, the same 1024-token workload produces fewer unique expert groups than N16:

```text
N16 unique groups: 107,492
N32 unique groups:  74,701
```

while total routed assignments are unchanged. Counted GPU waits fall from 4,480 to 2,240 because there are half as many slabs.

The current accepted benchmark uses fixed M=4 tiles for both large routed projections:

```text
gate+up:
  kernel  grouped_tiered_gate_up_m4_2row
  flag    FLASH_PREFILL_NROW_GATEUP_M4_2ROW
  tile    up to 4 activations
  TG      64 threads / 2 SIMD groups
  owner   1 output row per SIMD

down:
  kernel  grouped_tiered_projection_m4_2row
  flag    FLASH_PREFILL_NROW_DOWN_M4_2ROW
  tile    up to 4 activations
  TG      64 threads / 2 SIMD groups
  owner   1 output row per SIMD
```

Each SIMD uses explicit scalar accumulators for four activation rows. Groups larger than four are processed as multiple M4 tiles and partial final tiles are supported. The native tiered Q4/Q2 affine formats and per-row reduction/output semantics are preserved.

### Current measured result

On the common 1024-token fixture, V13B produced a 3-run median:

```text
nrow_ms                  46962.990
nrow_tps                    21.804
expert_ms                10974.525
expert_gate_up_gpu_ms      5327.446
expert_swiglu_gpu_ms        107.766
expert_down_gpu_ms         4525.955
```

All three runs passed:

```text
hidden_max  = 1.0490417e-05
logits_max  = 1.3828278e-05
next        = 1752/1752
state_equal = 1
```

Relative to V13A N32's dynamic gate+up kernel, fixed-M4 gate+up reduced gate+up GPU time from 8256.407 ms to 5327.446 ms (-35.48%) while down GPU time remained effectively flat (4515.876 → 4525.955 ms).

### Architectural interpretation

The current results support larger expert-major slabs, but also show that widening N can expose compiler/register-pressure problems in kernels whose accumulator extent depends on expert-group size. The accepted pattern is therefore not simply "increase N." It is:

```text
increase N
→ observe denser expert grouping
→ specialize the dominant small-M projection
→ verify direct GPU phase timing and exact state/output correctness
```

At this point in the chronology the next planned gate was N64. That gate has since been completed and promoted to production; see the production-status section below. The Q36-style larger-M / matrix-multiply crossover remains future research.



---

## Production status — updated 2026-10-03

The historical N16/N32/N64 sections above describe the path by which the N-row
architecture was developed. N128 has now passed benchmark, continuation,
serving-path, and DSH-scale gates and is the accepted production prefill
geometry.

### Production geometry

```text
N                             128
top-K                         8
routed assignments/slab       1024
gate+up kernel                grouped_tiered_gate_up_m4_8row
routed-down kernel            grouped_tiered_projection_m4_2row
gate+up activation tile       M=4, 8 rows/threadgroup
down activation tile          M=4, 2 rows/threadgroup
expert staging slots          min(model experts, routed assignments)
current model staging slots   256
```

`FLASH_PREFILL_NROW_PRODUCTION` and `FLASH_PREFILL_NROW_ASYNC` remain the
normal production Makefile flags. Unless an explicit candidate macro overrides
them, `infer.m` now selects N128, M4-8row gate+up, and M4-2row routed down as
the production defaults.

Runtime N-row prefill is enabled by default. `--no-prefill-nrow` immediately
restores the established scalar path; `--prefill-nrow` remains accepted as an
explicit enable switch.

### Request execution

For an ordinary prompt, complete 128-token slabs use N128. Any final remainder
smaller than 128 stays on scalar prefill. Prompt accounting, final-token
handling, completion generation, and decode remain on the established paths.

Tool-prefix snapshot boundaries are not crossed by an N-row slab: scalar
processing is retained until the exact boundary is captured, after which N128
may resume.

The N-row workspace is persistent within the process so its Metal buffers are
not reallocated for every request.

The server's progress log label currently remains `N64 prefill progress` for
historical reasons. It is not authoritative for the active geometry. The
runtime geometry is identified by:

```text
[prefill-nrow] slab_rows=128 assignments=1024
[prefill-nrow] routed down candidate=M4-2row
[prefill-nrow] routed gate+up candidate=M4-8row
[prefill-nrow] production runtime ready N=128 assignments=1024 stage_slots=256
```

### Correctness gates

The accepted N128/M4-8row/M4-2row arithmetic passed scalar-vs-N-row comparison
with:

```text
hidden_max  = 4.7683716e-06
logits_max  = 5.9604645e-06
next        = 363/363
state_equal = 1
```

The same validation then decoded four deterministic continuation tokens from
the resulting state and matched scalar exactly:

```text
decode_match = 1
tokens       = 363,313,198,262
```

This specifically validates that the larger slab preserves recurrent/KV state,
not just final logits.

### Geometry selection results

N128 first beat the former N64 production geometry with M4-2row gate+up and
M4-2row down. The N128 median controlled benchmark was:

```text
nrow_ms   = 40583.904
nrow_tps  = 25.232
gate+up   = 5717.553 ms
down      = 4046.419 ms
```

Relative to the N64 median, N128 improved throughput by about 8.84% and reduced
N-row latency by about 8.12%.

Gate+up packing was then tuned independently at N128:

```text
M4-4row median throughput  25.489 tok/s
M4-8row median throughput  25.659 tok/s
M4-16row median throughput 25.199 tok/s
M8-2row median throughput  24.062 tok/s
```

M4-8row was therefore accepted for gate+up. M4-16row regressed, and widening
the activation tile to M8 also regressed. Routed down remains M4-2row.

### Serving validation

A 4099-token aligned serving comparison kept scalar tails effectively equal:

```text
N64   202.424 s, 20.250 tok/s
N128  185.576 s, 22.088 tok/s
```

This is approximately 8.32% lower prefill latency and 9.08% higher reported
prefill throughput.

A larger 5895-token DSH-scale comparison also kept the same seven-token scalar
tail for both geometries:

```text
former N64 production     311.808 s, 18.906 tok/s
N128 candidate            302.127 s, 19.512 tok/s
production ./infer N128   296.349 s, 19.892 tok/s
```

The final `./infer` verification confirmed that the regular production binary,
not only the isolated candidate binary, reports N128/M4-8row/M4-2row and
completes the workload successfully.

Run-to-run differences between the candidate and final production verification
should be treated as normal cache/thermal/I/O variation rather than a separate
optimization.

### Memory

Expert staging is sized by the maximum number of unique experts that can appear
in a layer, not by all routed assignments:

```text
expert_stage_slots =
    min(g_cfg.num_experts, PREFILL_NROW_ASSIGNMENTS)
```

For the current 256-expert model, both N64 and N128 therefore stage at most 256
expert slices. N128 increases activation/routing slab storage, but does not
double the expert-stage allocation merely because routed assignments rise from
512 to 1024.

### Current baseline and future research

The production baseline for subsequent prefill work is now:

```text
N128
gate+up: M4-8row
down:    M4-2row
```

Do not use the former N64/M4-2row geometry as the production reference except
when reproducing historical comparisons.

The next useful research generation is not blind slab widening. N=256,
larger-M/Q36-style matrix-multiply crossovers, and other packing changes should
be isolated behind benchmark candidates and compared against the N128
production baseline with the existing scalar/state correctness gates.
