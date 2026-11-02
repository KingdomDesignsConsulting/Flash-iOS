# Mask-63 production-readiness qualification — 2026-11-02

WORKING REPORT — long-context and final safety checks are still running. This file is not a promotion decision. Production defaults, branch, binary, model, user profiles and port 11241 remain unchanged. PR #2 stays draft.

## Baseline and scope

Accepted engineering baseline: `eda0e73fd2eca1c8d48caebf9d4d124232eb0d0f`; adopted documentation-only HEAD: `64a5d51bb76c928e8d6ff0ee8535cee64286e597`. Work occurs only in the isolated experimental checkout for `experiment/http-resident-prefix-reuse-20261023`.

Inference arithmetic is unchanged from the accepted mask-63 implementation. Changes add diagnostic-only native rendering, snapshot/mirror extent checks, allocation inventories, controlled expert-worker failure and candidate routing observations, plus bounded test drivers. No template, routing, tie policy, cache format, execution version or full-binary identity changes. Full executable hashing remains disabled.

The ordinary-N128 failures in earlier reports remain valid historical controls. Exact persistent fingerprints do not imply universally bitwise-identical hidden vectors or logits. Candidate state evolves independently; it is never periodically rebased from scalar.

## Current release-gate matrix

| Gate | Current result | Scope and outstanding evidence |
| --- | --- | --- |
| 1. Independent histories | PASS | Six complete native-rendered histories, 455 observed completed endpoints/tail positions; exact fingerprints, finite values, greedy identity, all ten KV/mirror checks |
| 2. Long context | 16K PASS; 32K PASS | All 128 slabs at 16K have exact fingerprints, zero state error, hidden max 9.53674316e-7 and logits max 3.81469727e-6. Independent 32K completed 06:47:26 PST: 256 exact endpoints, zero state error, hidden max 4.76837158e-7, logits max 5.72204590e-6; all ten layers on GPU through 32768. Runtime-capacity rejection and recovery PASS |
| 3. Lifecycle | PASS for short executed cases | Three resident turns; profile capture/restart; prefix/version/model-signature/mode mismatch; completed-prefix publication inside a slab; reset during N128 prefill/decode. Long serving remains pending |
| 4. Controlled failures | PARTIAL | Before output, after six visible deltas, and expert-worker EIO PASS with explicit SSE errors, zero reusable state, stale 409 and exact scalar recovery. Actual incomplete tool-envelope interruption, partial snapshot-allocation failure and checkpoint-write EIO now PASS; failed sessions reject and recovery remains exact |
| 5. 24GB memory | PARTIAL | Measured categories and conservative preflight available; watchdog/resource tests PASS. 32K observed native RSS 10,177,478,656 bytes; charged-footprint peak 9,376,072,264 bytes. Partial allocation cleanup PASS; final serving-capacity analysis pending |
| 6. Modes | PASS within short scope | Default GPU; CPU-linear + no linear chain; both chains off; legacy KV; disabled arithmetic. Two illegal combinations rejected before model loading. Not cross-mode or long other-mode qualification |
| 7. Protocol | PASS within executed scope | Five buffered/SSE pairs, thinking off/on, structured tools, actual content+tool, exact native IDs/state, logical usage and usage-before-DONE. LM Studio build + 19 mock tests PASS; installed GUI/live adapter not claimed |
| 8. Performance | NOT RUN in this assignment | Mandatory gates must finish first. Previous accepted 1K exploratory results remain historical evidence, not a new long-context measurement |

## Independent histories

| History | Tokens | Observed endpoints |
| --- | ---: | ---: |
| Technical | 664 | 29 |
| Programming | 1068 | 52 |
| Conversation | 993 | 104 |
| Reasoning | 621 | 113 |
| Tool schema/result | 843 | 81 |
| Structured repetition stress | 2108 | 76 |

All 455 recorded persistent fingerprints match exactly. Maximum state error is 0, hidden error `1.9073486328125e-6`, logit error `3.814697265625e-6`. Limits remain state strictly `<1e-3`, hidden `<=1e-3`, logits `<=1e-2`, identical greedy token, finite state and exact active lengths/mirrors. Whole-model intermediate states inside a slab are not observable and are not claimed.

The corpus builder calls the unchanged native renderer/tokenizer before weights or Metal initialize. Complete 16,384- and 32,768-token technical histories are also prepared without truncating token IDs. The structured case is explicitly stress-only; repeated technical material is not a broad natural-document coverage claim.

## Completed 16K qualification

The 16,384-token legal history passed at 04:05:55 PST, exit 0, after starting at 03:15:08 PST. All 128 completed slabs have exact recorded persistent fingerprints. Greedy tokens, finite values, ten KV lengths and mirrors pass at every observation. Candidate-specific dispatch evidence shows all ten layers on GPU at 8192, 8193 and 16384; no long-context CPU substitution.

Observed native RSS peak: 9,559,293,952 bytes; child high-water RSS: 9,612,099,584 bytes. Mach charged-footprint peak: 5,783,074,832 bytes; maximum sampled resident size: 9,561,391,104 bytes. Metal allocation remained 5,357,207,552 bytes. Two oracle snapshot banks reached 1,734,410,240 malloc bytes. The 16GiB RSS watchdog did not trip. A separate 04:02:08 sample showed 47% host memory free. These overlapping metrics are not additive physical allocations.

The outer driver was deliberately paused while the native 16K process and its watchdog continued. After PASS it was retired with SIGTERM/SIGCONT (exit 143); this is not a native failure. The 32K run validates the saved 16K evidence and identical binary before starting independently from zero, with a 10,800-second timeout and unchanged 16GiB RSS limit. A separate ownership-checked host guard stops only this native process group after three readings below 15% host memory availability.

## Completed 32K and final safety follow-up

The independent 32,768-token history completed at **06:47:26 PST**, exit 0, after starting at 04:07:33. All 256 observed slab endpoints have exact persistent fingerprints, zero state error, identical greedy tokens, finite state and valid ten-layer KV/mirrors. Maximum hidden/logit errors are `4.76837158203125e-7` / `5.7220458984375e-6`. GPU routing includes all ten layers through position 32768.

Observed native RSS was 10,177,478,656 bytes; child high-water RSS 10,238,558,208; charged-footprint peak 9,376,072,264; sampled resident maximum 10,136,109,056; Metal allocation 5,357,207,552; two diagnostic banks 3,076,587,520 bytes. These overlapping measurements must not be summed. Host availability never fell below 29% across 936 external guard samples. No safety guard fired.

The original partial-tool follow-up used an invalid mixed tool/user resident delta; preserve that failed harness attempt. The corrected tool-only retry passed: interrupted tool envelope produced an explicit error rather than an executable partial call, invalidated the session, rejected its stale ID, and recovered with exact fresh and tool-result continuation state. Servers ran 11:42:15–11:43:21 and 11:43:24–11:44:39; independent scalar control finished 11:45:49 PST.

Live diagnostic partial snapshot-allocation failure and a 4096-byte checkpoint-write EIO both passed recovery/restart checks, finishing 11:49:57 PST. These simulate controlled failures, not real system OOM or disk exhaustion. Exact capacity-plus-one admission (`65537` required tokens) rejected fresh and resident requests before mutation, preserving all existing KV/state and allowing an exact valid follow-up.

Native compressed state save and reload across different diagnostic executables passed **11:50:00–11:51:59 PST** with the same selective compatibility identity; wrong numerical mode was rejected without changing the checkpoint. The long HTTP resident test started 11:52:01 PST and remains pending. The actual LM Studio SDK/adapter harness is prepared; installed GUI remains untested.

The optional global host-memory guard stops only its owned process group after three low readings. Missing memory or RSS monitors fail closed. A denied `ps` call originally escaped as an exception in a model-free test; the runner now handles it as `RSS_MONITOR_ERROR`, terminates the child and returns 125. Six focused watchdog tests pass, including this regression. No inference code was changed by this repair.

## Failure and protocol observations

The initial expert-worker injection fired during startup warmup: the process cleanly exited 1 before listening. This was a test-targeting mistake, not an API failure. The corrected diagnostic is armed by a private marker only after health readiness.

Real HTTP 200 SSE responses then reported explicit error objects and session invalidation for pre-output failure, decode failure after six content deltas, and simulated expert-worker EIO. Each emitted exactly one DONE, no successful finish, rejected the old session with 409, and permitted exact fresh recovery. These are controlled failures, not actual hardware reset, disk failure or system OOM.

Five normal protocol pairs passed: plain thinking off/on, tools thinking off/on, and actual content followed by a tool call. Normalized output, native prompt/sample IDs and resident fingerprints match between buffered and streamed responses. Usage includes the full logical prompt even on prefix reuse, and is sent before DONE. Tools are returned, never executed by the harness.

Profile restart used a 67,427,311-byte compressed checkpoint and private UUID profile. Three turns match after restart; old conversation IDs reject, while the same static profile serves new IDs. Profile and session are distinct lifetimes. Header version/model-signature mutations and a real runtime-prefill-mode switch exercise safe rejection/rebuild; real foreign weight files were not substituted.

## Memory methodology

`release_memory_diag.inc` inventories unique Metal buffer objects by category and records Mach process footprint/peak, resident memory, Metal current allocation/recommended working set, actual malloc sizes for the two oracle banks, CPU recurrent/conv state and CPU/Metal KV aliases. It allocates no speculative or new GPU state.

At the 257-token preflight endpoint:

- Resident memory: 8,592,031,744 bytes; observed maximum across samples: 8,855,683,072 bytes.
- Charged physical footprint/peak: 2,240,638,352 bytes.
- Metal current allocation: 5,357,207,552 bytes; inventoried reserved lengths: 5,356,534,836 bytes.
- Reserved Metal categories: immutable tensors 2,395,996,160; expert cache 905,969,664; attention KV 1,342,177,280; N128 workspace 511,115,776; expert staging 35,323,904; GDN 125,829,120; convolution 4,423,680; scalar workspace 35,699,252 bytes.
- CPU GDN/conv malloc: 62,914,560 / 2,949,120 bytes.
- CPU KV reservation: 2,684,354,560 bytes, sharing its initial GPU-window backing with Metal. Reservation is not committed residency.
- Two oracle snapshot banks: 413,859,840 bytes at position 257.
- Speculative/drafter state allocated by this task: 0.

These quantities overlap and MUST NOT be summed as independent physical allocations. In particular RSS alone is not total unified memory. Mach footprint is charged ownership, not a complete attribution of mapped shared pages; the inventory also does not fully attribute paged expert backing or host runtime overhead.

The initial alias counter reported the full CPU reservation upon matching base pointers. Diagnostic schema 2 corrects it to the actual overlap bounded by Metal view lengths. A model-free native unit checks partial overlap, full overlap and non-aliasing using the real helper. Schema-1 public summaries retain the base-alias reservation separately and expose the bounded shared span; raw artifacts are not rewritten. This counter is not used by memory preflight or inference.

Long-test preflight takes the maximum of process peak, resident memory, and Metal allocation plus host snapshots/GDN/conv, then adds growth for one active KV plus two oracle banks and a 2GiB unattributed margin. Initial conservative bounds: 12,984,852,480 bytes at 16K; 14,998,118,400 at 32K, below an 18GiB estimated ceiling with 6GiB reserved for the system. Every native run additionally has a 16GiB RSS watchdog, a timeout and GPU launch gating. The 32K bound is recomputed from actual 16K measurements before escalation.

Serving retains five prefix slots, an 8K prefix-token cap, a 768MiB dynamic snapshot budget and the existing excluded pinned slot. Oracle banks are diagnostic allocations, not a new serving pool. Final admission analysis must compare these bounded serving allocations with measured long-context peaks.

## Research applicability

The pending 56-findings Library artifact was not discoverable through available connected searches. Canonical Drive metadata still points to the October 29 version; no staging replacement or canonical write occurred.

Handoff findings are treated as test prompts, not assumed Flash defects: Ollama #19458 motivates actual mid-stream error checks; SGLang #47830 motivates explicit recurrent/snapshot accounting; vLLM #65035 motivates logical cached-token parity. Existing native MLX4/tiered shape/layout validation remains the supported model contract; vLLM #65034 does not establish a Flash quantization bug. Earlier Q4/attention numerical findings remain addressed only within the measured mask-63 scope.

## Reproduction and evidence

Private artifacts: `/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-11-02-mask63-release/`. Root project logs: `benchmark-logs/mask63-release-*.log`. Raw tokens, tensor fingerprints, checkpoints and SSE payloads remain private.

Build provenance includes phases: unchanged corpus binary A; memory/unarmed-worker diagnostic B1; corrected armed HTTP diagnostic B2; candidate boundary logging B3. The phase-A oracle source is reconstructed and hash-checked against its first launch; later source-at-launch hashes may reflect diagnostic edits made while that unchanged binary ran. Exact phase-B1 source hashes were independently reconstructed and checked. Private source manifests retain 45 files per B phase. B4 adds partial-allocation injection and corrected alias accounting; B5 adds explicitly bounded 32768-token sparse HTTP tracing. The B3 binary is unchanged between the 16K and 32K runs. Final committed source will be distinguished from these tested build variants.

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer release-qualification release-legacy-qualification
# Use a new directory for every test invocation.
python3 tools/build_release_corpus.py --binary "$PWD/metal_infer/infer-release-qualification" --out "$PRIVATE_OUT/corpus"
python3 tools/qualify_release_histories.py --binary "$PWD/metal_infer/infer-release-qualification" --corpus "$PRIVATE_OUT/corpus/corpus.json" --out "$PRIVATE_OUT/independent"
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-release-qualification" --fixture "$PRIVATE_OUT/corpus/technical.bin" --count 257 --numerics 63 --gpu-wait 60 --timeout 240 --max-rss-gib 16 --out "$PRIVATE_OUT/preflight257"
python3 tools/qualify_release_long.py --binary "$PWD/metal_infer/infer-release-qualification" --corpus "$PRIVATE_OUT/corpus/corpus.json" --preflight "$PRIVATE_OUT/preflight257/memory-observations.json" --timeout 10800 --out "$PRIVATE_OUT/long"
```

The opt-in extended HTTP diagnostic raises its history bound to 32768 and records actual slab endpoints, selected scalar-prefill positions, final prefill, every decode/EOS and request boundaries. Sparse scalar replay requires a final expected digest and checks exactly the observed positions. Default diagnostics retain 512 tokens/every scalar step. Native model-free checks of these guards pass; the live long HTTP experiment remains pending.

Final disposition and remaining commands will be completed after the running gates finish. No production promotion is authorized by this working report.
