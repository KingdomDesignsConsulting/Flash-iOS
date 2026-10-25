# Flash-iOS N128 lazy-KV duplicate-copy experiment — 2026-10-24

Status: **SOURCE PATCH ONLY; requires compilation and runtime qualification on Mac mini M4.** No production binary changed.

Branch: `experiment/n128-lazy-kv-copy-elision-20261024`
Changed: `metal_infer/prefill_nrow_grouped_async.inc`, near N128 full-attention K/V publication.

## Hypothesis

When `FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV[_32K]` is active, `buf_kv_k/v[fa_idx]` are newBufferWithBytesNoCopy views of `kv->k_cache/v_cache`. The N128 row loop has already written identical K/V values to canonical CPU mappings. A second memcpy of 128 rows into their Metal aliases needlessly rereads/writes same bytes. This occurs at ten full-attention layers. Guard mirror copy under legacy separate-buffer build only.

The experiment also checks both pointer identities and returns failure on unexpected alias mismatch. Validate whether that failure propagates correctly through prefill, and that session invalidation occurs.

## Safe compilation (disposable worktree; no production executable overwrite)

```bash
cd "/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS"
git fetch origin experiment/n128-lazy-kv-copy-elision-20261024
git worktree add --detach ../Flash-iOS-kv-copy-test origin/experiment/n128-lazy-kv-copy-elision-20261024
make -C ../Flash-iOS-kv-copy-test/metal_infer lazy32k-experiment
```

Build outputs remain under the disposable worktree. Production `metal_infer/infer` and `infer-candidate-lazy32k` are untouched.

## Required gates

1. Confirm build succeeds; qualify K/V pointer alias identity and no runtime alias failures.
2. Use same model, options, N128 128-row batch, static prompt, fixed deterministic decoding, no `--timing`. Compare unmodified 32K control in a **separate clone/worktree** versus new candidate, never concurrent processes, with idle criteria.
3. Measure server log `[serve] ... prefill=... forward=... nrow_chunks=...` and p50/p95 across >=5 warmed runs; record RSS/physical footprint.
4. Check exact output and hidden/state parity for 8K/16K/32K; sample boundary 32768/32769 and snapshot capture/restore. Preserve baseline tool-prefix behavior.
5. Force an abort during prefill and verify session invalidation; never compare partially completed request as success.
6. If no measurable speedup in uncontended baseline, keep patch experimental.

## Storage

All output belongs in `Testing/N128-Lazy-KV-Copy-Elision/<run-id>/` (Google-Drive-synced project path); include console logs, benchmark summary, git SHA, model manifest identity and build flags.

## Important note

This does **not** solve redundant multi-turn prefill. Independent resident-session prefix reuse PR #2 addresses that. The K/V copy-elision experiment addresses per-token prefill cost only.


## Preliminary result (2026-10-24)

Observed with identical 1,372-token prefill and exact-match generated response:

| Candidate | Prefill ms | Prefill tok/s |
|---|---:|---:|
| Lazy K/V copy elision | 56,453.669 | 24.303 |
| Unmodified 32K control | 48,453.3 | 28.32 |

**Preliminary verdict: no speedup; modified run is 16.5% slower by elapsed
time.** Single A/B order not thermally, memory or contention controlled. One
control server launch failed `bind: Address already in use`; its failed startup
is not a benchmark result. Later run returned control measurements. No production
promotion recommended.

A sequential crossover harness is now at
`tools/benchmark_n128_kv_copy_abba.py`. It uses the order **control,
modified, modified, control**, restarts only servers it spawned on an
otherwise-free port, records executable SHA-256, input payload, actual response,
server logs, prefill metrics and swap/memory status, and writes each run under
`Testing/N128-Lazy-KV-Copy-Elision/<timestamp>/`. It does not automatically
terminate services on 11241 or 11243. Stop existing test server and avoid
running another active model concurrently before invocation. This is a
follow-up repeatability screen, not full idle/thermal qualification.


## Idle-GPU ABBA crossover (2026-10-24, Drive run 20261024-152541)

Source manifest: `Flash-iOS/Testing/N128-Lazy-KV-Copy-Elision/20261024-152541/manifest.json`
(synchronized Drive folder `1GUyRqWTbD6sBjbdsI91BG1X7ZfKrV96s`).

Control prefill durations: 45,269.890 and 40,602.940 ms.
Modified: 40,038.413 and 40,320.963 ms. All trials used 1,372 prefill tokens
with 13 cached-prefix tokens, no warm-prefix reuse, and identical response text.
Control median 42,936.415 ms; modified median 40,179.688 ms, apparent 6.42%
prefill reduction. Control's first trial differs from its second by 4.67s,
whereas modified trials differ by 0.28s. The last control is only 0.42s
slower than modified median. Reported swap remained ~5.51 GiB and
`vm.memory_pressure` was nonzero in one modified trial. Thus keep status
**inconclusive, candidate only**; the original negative 1-shot A/B is also
confounded by background GPU work.

Next trial script: `tools/benchmark_n128_kv_copy_abba.py` now accepts
`--warmup 1 --measure 2` (defaults). Fresh server in each ABBA slot;
warmup excluded and individual repeated requests logged, with all sample-level
prefill token counts and cached-prefix counts. This helps distinguish per-server
first-request effects from stable throughput. Results go to fresh timestamped
Testing subdirectory. No merges until persistent benefit and correctness
under 8K/16K/32K/cache/continuation conditions.


## Warmup-controlled ABBA conclusion (2026-10-24)

Data: `Flash-iOS/Testing/N128-Lazy-KV-Copy-Elision/20261024-153747/`,
Drive folder `1oHvxbkSXNCfPQ039ju1ksm20yrPhVCAv`.

Protocol: fresh server per ABBA leg, one warmup excluded per server, two
measurements per leg, identical request payload; no `--timing`.

| Leg | Variant | Warmup (ms) | Timed prefill (ms) |
|---|---|---:|---:|
| 1 | control | 39,202.707 | 38,984.986; 40,702.271 |
| 2 | modified | 40,870.302 | 40,539.578; 40,734.515 |
| 3 | modified | 41,128.756 | 41,021.550; 40,479.820 |
| 4 | control | 40,934.613 | 40,547.751; 40,621.129 |

Control median **40,584.440 ms**. Modified median **40,637.046 ms**.
Copy elision **0.13% slower**, effectively no gain versus observed
sample variation. All eight measured outputs identical, 1,372 prefill tokens,
13 cached-prefix tokens, no reported warm-prefix reuse.

**Disposition: reject optimization for now; DO NOT merge source change to
production.** Preserve experimental branch and all measurements. Focus
next on session-history prefill avoidance; no further copy-elision throughput
runs unless GPU profiling identifies material memcpy costs. Output equality
alone does not prove hidden-state/KV state equality.
