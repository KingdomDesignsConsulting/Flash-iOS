# Flash-iOS exact-M2 repair and qualification — October 17, 2026

The final build passed all 30 oracle cases: 15 raw and 15 zero-block. Every case reports serial tokens, committed state, GPU KV coherence, and continuation exact, with exit status 0 and the intended accepted-draft count.

## Root cause and repair

The geometry correction reduced each GPU DeltaNet snapshot to its correct 2,097,152-byte allocation, but the shared oracle comparator retained a 4,194,304-byte comparison. AddressSanitizer proves an illegal read at the first byte after the allocation, GPU linear layer 0. The pre-geometry implementation passes the same raw/32/accept0 case. The bounded hidden-state comparison matches in the instrumented failing build. The comparator now uses the same geometry helper as capture and restore. The adjacent layer-state diagnostic had the same stale element count and was corrected.

The audit also found the fixed 4 MiB assumption in persisted GPU checkpoint payload sizing and both raw/memory transfer paths. Those paths now use model geometry. Disk layout version 2 safely rejects layout 1 and changes compatibility hashing. The new 32/64-head transfer regression fails with the original 32-head transfer code and passes with the repair under AddressSanitizer. Existing live checkpoint files were preserved; the repaired runtime must recapture incompatible warm caches.

No transformer math, acceptance policy, or checkpoint ownership was changed. Permanent edits are limited to target_verify_batch.inc, target_verify_grouped.inc, warm_state_cache.inc, and tools/benchmark_warm_state.py. The complete changes are in state-integrity-fix.patch. Optional diagnostic instrumentation was compiled separately from a temporary copy and is supplied in its own patch.

## Old versus new

| Build | raw/32/accept0 | Evidence |
|---|---|---|
| Paired pre-geometry backups | PASS, exit 0 | baseline-raw-32-accept0.log |
| Geometry-corrected, original comparator | FAIL, exit 1 | diagnostic-raw-32-accept0.log |
| Same diagnostic build with AddressSanitizer | Heap-buffer-overflow, abort | diagnostic-asan-raw-32-accept0.log |
| Repaired final build | PASS, exit 0 | repaired-raw-32-accept0.log |

## Full final matrix

| Codec | Context | Outcome | Accepted | Exit | Elapsed s | Peak footprint GiB | Max RSS GiB |
|---|---:|---|---:|---:|---:|---:|---:|
| raw | 32 | accept0 | 0 | 0 | 9.002 | 1.180 | 4.278 |
| raw | 32 | accept1 | 1 | 0 | 2.254 | 1.179 | 4.264 |
| raw | 32 | accept2 | 2 | 0 | 2.130 | 1.179 | 4.215 |
| zero4k | 32 | accept0 | 0 | 0 | 2.240 | 1.300 | 4.399 |
| zero4k | 32 | accept1 | 1 | 0 | 2.173 | 1.300 | 4.385 |
| zero4k | 32 | accept2 | 2 | 0 | 2.130 | 1.300 | 4.336 |
| raw | 4096 | accept0 | 0 | 0 | 138.693 | 2.649 | 10.065 |
| raw | 4096 | accept1 | 1 | 0 | 154.709 | 2.649 | 9.853 |
| raw | 4096 | accept2 | 2 | 0 | 136.400 | 2.649 | 9.961 |
| raw | 8191 | accept0 | 0 | 0 | 341.649 | 3.628 | 10.236 |
| raw | 8191 | accept1 | 1 | 0 | 336.019 | 3.627 | 10.280 |
| raw | 8191 | accept2 | 2 | 0 | 332.264 | 3.628 | 10.235 |
| raw | 8192 | accept0 | 0 | 0 | 335.201 | 3.628 | 9.676 |
| raw | 8192 | accept1 | 1 | 0 | 362.696 | 3.628 | 9.276 |
| raw | 8192 | accept2 | 2 | 0 | 348.662 | 3.628 | 9.492 |
| raw | 8193 | accept0 | 0 | 0 | 351.523 | 3.563 | 9.561 |
| raw | 8193 | accept1 | 1 | 0 | 368.907 | 3.563 | 9.663 |
| raw | 8193 | accept2 | 2 | 0 | 343.206 | 3.563 | 9.599 |
| zero4k | 4096 | accept0 | 0 | 0 | 156.858 | 2.771 | 9.256 |
| zero4k | 4096 | accept1 | 1 | 0 | 139.804 | 2.770 | 9.452 |
| zero4k | 4096 | accept2 | 2 | 0 | 162.413 | 2.770 | 9.301 |
| zero4k | 8191 | accept0 | 0 | 0 | 347.803 | 3.749 | 9.373 |
| zero4k | 8191 | accept1 | 1 | 0 | 348.214 | 3.749 | 9.526 |
| zero4k | 8191 | accept2 | 2 | 0 | 348.183 | 3.749 | 9.329 |
| zero4k | 8192 | accept0 | 0 | 0 | 350.165 | 3.749 | 9.439 |
| zero4k | 8192 | accept1 | 1 | 0 | 352.603 | 3.749 | 9.497 |
| zero4k | 8192 | accept2 | 2 | 0 | 346.296 | 3.749 | 9.458 |
| zero4k | 8193 | accept0 | 0 | 0 | 336.091 | 3.685 | 9.504 |
| zero4k | 8193 | accept1 | 1 | 0 | 350.548 | 3.685 | 9.252 |
| zero4k | 8193 | accept2 | 2 | 0 | 343.359 | 3.685 | 9.446 |

The per-case logs include the exact command, selected codec/oracle environment, full runtime output and /usr/bin/time -l statistics. matrix-results.json records each oracle line and return status. The 8K cases include positions 8191, 8192, and 8193 around GPU_KV_SEQ=8192.

## Production and cache qualification

Production inference generated at least two tokens and exited 0. API, tool/schema/session validation, and warm-state self-tests passed. The warm self-test includes both GPU geometries, raw and memory transfers, compressed/raw fallback, corruption rejection, and rejection of the old layout. Real HTTP tests exercise repeated tool-prefix restore, identical output after repeated restore, resident user-turn continuation, tool-result continuation, process restart and persisted GPU checkpoint reload. HTTP requests/responses, timings, assertions, and server logs are included. The final actual Metal oracle also passes under AddressSanitizer.

An initial HTTP test sent unsupported tool_choice=required and received HTTP 400 before generation. The corrected harness uses the supported auto mode and records the expected-400 rejection control separately; no runtime source change was needed for that protocol mismatch. Initial extra tool self-tests failed only their executable-location assertion because the isolated binary was outside a directory named metal_infer. They passed when placed in the required layout. The deliberately restored old warm transfer code fails its new 32-head regression as expected. An intermediate comparison-only matrix controller was stopped after the serialization defect was found; those logs are retained separately and are not counted in the final 30 cases.

## Memory and copy observations

The measured MTLBuffer lengths are 2,097,152 bytes per DeltaNet layer, 30 layers: 60 MiB of recurrence matrices, a 60 MiB allocation reduction from the old geometry. The unchanged convolution buffers are measured separately. Raw runtime checkpoint banks total 191.273 MiB, versus 311.273 MiB in the old geometry: a 120 MiB reduction across two banks. Zero-block bank allocation and measured capture/restore timing by case are recorded in memory-copy-measurements.json. These are allocation/counter measurements; process peak footprint and maximum RSS are separately measured and include the oracle’s extra full serial snapshots, model mappings, and prefill buffers. They are not isolated checkpoint residency.

The separate timed pre-geometry 32-token baseline reported peak footprint 1.535 GiB and maximum RSS 4.430 GiB; the final 32-token raw/accept0 case reported 1.180 GiB footprint and 4.278 GiB maximum RSS. These whole-process observations were collected at different points in the run.
raw: bank allocation 191.273–191.273 MiB; median anchor capture 27.176 ms, row-0 capture 11.627 ms. These are observations across qualification cases, not a controlled speedup benchmark.
zero4k: bank allocation 188.464–188.464 MiB; median anchor capture 30.345 ms, row-0 capture 15.921 ms. These are observations across qualification cases, not a controlled speedup benchmark.

The ordinary two-token production smoke reported peak footprint 208.5 MiB and maximum RSS 2.993 GiB. This short workload is distinct from the long-context oracle harness.

Zero-block processes reported a median 124.0 MiB higher peak footprint than the matching raw cases, despite 2.809 MiB smaller bank allocations. This is an observed whole-process result across sequential qualification runs; allocator/lifetime causes were not isolated. The bank-size reduction must not be presented as a measured resident-memory saving.

A separate post-qualification 32-token accept1 copy profile measured raw anchor+row0 capture at 24.470 ms and rollback at 8.128 ms; zero-block capture at 32.297 ms and rollback at 12.327 ms. These are individual observations, not a controlled speedup benchmark. Keep raw as the baseline while profiling CPU-state copies and allocator retention.

Real 361-token GPU warm checkpoints contained 147,988,480 payload bytes. The raw file was 147,988,848 bytes including its header; the Zstd payload stored 75,739,006 bytes. Reload and checksum validation succeeded for both. Startup restore probes measured the subsequent CPU-to-Metal copy at 15 ms raw and 17 ms Zstd. The matching next output after restart was verified in both formats.

The opt-in copy profile records logical GPU capture/rollback byte counters and each actual Metal buffer length. Raw banks each copy 67,338,240 bytes of GPU recurrence/convolution state; row 0 borrows 65,863,680 bytes of byte-identical CPU state from the anchor. The anchor still owns/copies that CPU state. Zero-block counters describe logical input size; compressed payload sizes are reported separately.

## Next engineering step and remaining limits

Profile the anchor’s CPU-state capture/restore and the mandatory GPU copies separately, establishing which state is canonical in GPU mode before proposing selective serialization. The CPU section is about 62.8 MiB per anchor; this is a measured candidate to investigate, not an implemented saving. The zero-block memory benefit is modest after removing unused DeltaNet padding. Keep the exact 30-case matrix and actual GPU warm reload as gates for any copy reduction or later multi-row Q2/Q4 kernel experiment. The source-backed research comparison is in research-review.md. No performance optimization was applied during the repair.

Qualification covers this local Qwen3.5-35B-A3B tiered model, fixtures, flags, and M4. It is not a general-model or stochastic-sampling qualification. Allocation-failure injection, dedicated zero-block corruption injection, and combined speculative HTTP serving are not claimed. The existing CPU-only/synthetic checkpoint tests alone were insufficient to qualify GPU persistence.

## Reproduction, paths, and provenance

Tested/repaired project: /Users/knagel/My Drive/Flash-iOS. It is a real local directory without .git. The separate external-drive Git checkout has different source hashes and remains separate. Its recorded HEAD is 6df482c167ee529e5ce922ec399097957cb16c16. No Git commit or push was made. Existing production binaries were preserved.

Live backups are named *.pre-state-integrity-20261017-*.bak beside each edited file; copies are included in backups/. The full compiler command arrays, binary/source SHA-256 values, fixture/resource hashes, machine/compiler metadata, and baseline identities are included in the JSON manifests and build logs. All temporary binaries and reproducible runners are under the chat’s work/exact-m2 directory.

All deliverables and logs: /Users/knagel/Documents/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/outputs/exact-m2-repair-20261017
Final verifier binary (temporary): /Users/knagel/Documents/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/work/exact-m2/infer-repaired-verify
Final production binary (temporary): /Users/knagel/Documents/Codex/2026-10-16/referenced-chatgpt-conversation-this-is-an/work/exact-m2/infer-repaired-production
