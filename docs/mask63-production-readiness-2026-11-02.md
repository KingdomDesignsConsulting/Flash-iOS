# Mask-63 production-readiness qualification — 2026-11-02

FINAL HANDOFF — evidence reviewed 2026-11-03. Production promotion is blocked by missing long-context performance evidence and unresolved client behavioral coverage. Production defaults, branch, binary, model, user profiles and port 11241 remain unchanged. PR #2 stays draft.

## Baseline and scope

Accepted engineering baseline: `eda0e73fd2eca1c8d48caebf9d4d124232eb0d0f`; adopted documentation-only HEAD: `64a5d51bb76c928e8d6ff0ee8535cee64286e597`. Work occurs only in the isolated experimental checkout for `experiment/http-resident-prefix-reuse-20261023`.

Inference arithmetic is unchanged from the accepted mask-63 implementation. Changes add diagnostic-only native rendering, snapshot/mirror extent checks, allocation inventories, controlled expert-worker failure and candidate routing observations, plus bounded test drivers. No template, routing, tie policy, cache format or full-binary identity changes. The confirmed ownership repair adds a narrowly scoped GPU-N128 execution marker; global execution version remains 3. Full executable hashing remains disabled.

The ordinary-N128 failures in earlier reports remain valid historical controls. Exact persistent fingerprints do not imply universally bitwise-identical hidden vectors or logits. Candidate state evolves independently; it is never periodically rebased from scalar.

## New multi-request blocker and short repair

The live SDK smoke exposed a second-stateless-prefill failure at 129 after exact state through 128. Authenticated captures show six omitted experts and maximum active-state error 18.87463927268982. Decode-prefetch phase leaked into N128 capture, leaving an unrelated short async read whose validity flags could suppress six routed experts. Disabling prefetch isolates the cause. The narrow ownership repair passes exact all-active/combine captures and three-turn stateless/resident tests through 476. [Detailed evidence and focused regression](prefetch-n128-ownership-2026-11-02.md).

This introduces a selective `nrow-prefetch-ownership-v2` identity only for eligible GPU N128; old prefetch on/off identities aliased, so both affected variants invalidate once. Scalar/CPU identities, global execution version 3, checkpoint format and disabled executable hashing remain unchanged. Post-repair cache/restart/fault/cancellation and three-turn HTTP state through 16470 now PASS. Balanced 1K/4K CLI and HTTP measurements completed. These do not establish matched 16K/32K performance or a new post-repair native 32K run.

## Final release-gate matrix

| Gate | Result | Exact scope / remaining requirement |
| --- | --- | --- |
| 1. Independent histories | PASS | Six complete histories / 455 exact observed endpoints; no intermediate whole-batch equivalence claim. Executed pre-ownership repair; unchanged single-history math path. |
| 2. Long numerical context | PASS | Complete native 16K/128 and 32K/256 slabs, all ten GPU layers through 32768, exact state fingerprints. Archived B3 build; no new full 32K run on repaired B8 binary. Repaired HTTP state passes through 16470. |
| 3. Hybrid lifecycle | PASS | Repaired default-prefetch stateless and resident three-turn tests, named-profile restart/new session, cross-build compressed restore, prefix/mode rejection, disconnect/invalidation/recovery and completed-boundary publication. |
| 4. Controlled failures | PASS | Pre-output, visible-output, expert-worker, interrupted tool, partial allocation and checkpoint-write injection; fail-closed session, stale 409, exact fresh recovery. Actual hardware reset/OOM/disk exhaustion NOT RUN. |
| 5. Resource safety | PASS | Bounded sequential tests on 24GiB M4, per-category allocations, charged footprint and RSS, guarded 32K/16K HTTP, controlled allocation/write failures. Not whole-system physical attribution or multi-client capacity certification. |
| 6. Modes / identity | PASS | Short within-mode CPU-linear/chains-off/legacy-KV/mask-zero checks and illegal-mode rejection; selective ownership marker invalidation and cross-build reuse. Long alternative-mode cross-products NOT RUN and excluded. |
| 7a. API / actual SDK transport | PASS | Five buffered/SSE pairs; thinking/tools/content+tool; exact IDs/state, logical usage before DONE; actual SDK Chat/generator/transport with mock UI controller, independent scalar-validated state. |
| 7b. SDK literal-change behavior | FAIL | Both scalar and mask63 repeat the old literal instead of the requested new one; correct request IDs/history and exact states. Not an N128 regression and not hidden by protocol-only PASS. Installed GUI NOT RUN. |
| 8a. Bounded performance | PASS | Three balanced trials/path at 1K/4K and HTTP first/warm/resident; medians/ranges below, exploratory conditions. HTTP outputs only two tokens, so no sustained decode claim. |
| 8b. Intended-capacity performance | NOT RUN | No matched scalar/ordinary/mask63 16K or 32K performance cohort; no sustained long-output HTTP benchmark. Mandatory production performance evidence remains incomplete. |

The disposition is NO-GO because the intended-capacity performance gate lacks evidence and the client behavioral failure remains unresolved. Numerical success is not withdrawn; neither is it a blanket release certification.

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

Native compressed state save and reload across different diagnostic executables passed **11:50:00–11:51:59 PST** with the same selective compatibility identity; wrong numerical mode was rejected without changing the checkpoint. The long HTTP server ran 11:52:01–12:12:52 PST. All three turns completed, ending at position 16470; both follow-ups retained the identifier, with valid recorded KV/finite-state checks. Independent scalar replay ran 12:12:54–12:49:10 PST and PASSed all 150 observed fingerprints through 16470, before the subsequent ownership repair. The actual SDK/adapter subsequently ran against the repaired server; protocol/native state PASS and literal-change behavior FAIL are recorded separately below. Installed GUI remains untested.

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

Serving retains five prefix slots, an 8K prefix-token cap, a 768MiB dynamic snapshot budget and the existing excluded pinned slot. Oracle banks are diagnostic allocations, not a new serving pool. At 32K the measured diagnostic charged peak is 8.73GiB and observed RSS 9.48GiB, with two oracle banks totaling 2.87GiB. Serving uses a different bounded snapshot policy, so subtracting diagnostic banks from RSS is not a valid serving footprint calculation. The 768MiB dynamic budget, excluded pinned entry and one active conversation remain unchanged; no extra KV pool is introduced. The conservative 13.97GiB preflight bound plus 6GiB system reserve stayed below 24GiB. This establishes safe execution for the sequential tested workloads, not worst-case admission under arbitrary concurrent applications.

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

The opt-in extended HTTP diagnostic raises its history bound to 32768 and records actual slab endpoints, selected scalar-prefill positions, final prefill, every decode/EOS and request boundaries. Sparse scalar replay requires a final expected digest and checks exactly the observed positions. Default diagnostics retain 512 tokens/every scalar step. Native model-free checks of these guards pass; the repaired live long HTTP experiment completed as recorded below.

No production promotion is authorized. See the final handoff below.


## Post-repair completion and provenance

Repair commit: `ac06b920dbb7e26b804480b36eea4dbe83b40d4e`; prior evidence commits `bcf431b5d8c2555dc55b462101b80f44fbe024ea` and `24d6cc4cef2c8b852b63f4d3af3dcf55b30090c6`. Starting engineering/documentation SHAs appear above. Final reporting commit is the commit containing this report; runtime source remains exactly the repair revision.

The repaired suite ran **2026-11-02 13:55:53–14:23:04 PST**, exit 0. It rejected the actual old GPU-N128 checkpoint while preserving its bytes, saved and restored a 67,370,561-byte checkpoint between different repaired executables, rejected prefix/mode/mask mismatch, and repeated streaming failure, named-profile restart and actual connection-reset checks. Save/restore were **405.068 / 369.328ms**, single diagnostic sample, not a latency distribution. Profiles identify static prefixes, not conversations.

Repaired long HTTP ran **14:02:09–14:23:03 PST**. Three resident turns end at **16406 / 16438 / 16470**. All **150 observed fingerprints** match the independently completed scalar replay, with exact full effective-token-history and observation-coverage checks before reference reuse. Reuse reads only evidence; candidate state is never restored/rebased from reference. Scalar reference ran 12:12:54–12:49:10 using unchanged scalar math. This is not a second post-repair native 32K run. Repaired server RSS high water: **9,531,375,616 bytes**; no guard fired.

Actual SDK Chat → generator → completionEvents → Flash tests pass full-history request IDs and state fingerprints against separate validated scalar controls. The UI prediction controller is mocked; documents, external tools, GUI attachment/cancellation presentation were not exercised. `--protocol-only` is explicit and requires validated state evidence; default literal assertions remain strict. Both paths' incorrect repeated literal remains FAIL.

### Exact tested builds

Private `build-provenance/phase-b8-final-repair/` contains source manifests and exact commands for 45 runtime inputs. All builds use the actual Makefile dependencies/optimization flags and separate names; production `infer` is untouched.

| Build | SHA256 | Scope |
| --- | --- | --- |
| B3 archived native long oracle | `18ca5bf2c1a19590c8ca95a23e00adf875d9831378527896ed14328bc050274e` | Complete native 16K/32K |
| B7 repaired short | `4b77108f5afd1b47e48346599e8690dac845e33e408f7e2fb622899ed2525225` | Capture/three-turn and save |
| B8 repaired short alternate | `67591cf85ff9c2105a1ca88df98ba3b934a125d2d18db5ad56c60c1bbc1a3c83` | Restart/SDK/faults |
| B8 repaired long HTTP | `93eaab13c68b1aa081c33a554b4eff2f2570abe497f0e7b70deabd31bf9fa25f` | 16470 resident state |
| Repaired ordinary/scalar performance | `02f12ff6477fedf2a748136c51458ac6e960b2bd1ba53336da87c0f0355db7b4` | No state trace; scalar uses --no-prefill-nrow |
| Repaired mask63 performance | `9a0cbf721ea27401f22b3d06c1766033318e51466c866ec61c996b5e79bc66fb` | No state trace; mask63 |

## Measured performance

Performance ran **14:23:04–15:47:53 PST**; final owned server stopped **15:47:50 PST**. Three balanced independent process trials per path, identical fixture/seed 73941/temperature 0, K=8 and expert-cache settings. Every launch required three GPU readings below 30%; pre/post readings and cache counters are private and sanitized in JSON. OS page cache was not purged. Low launch utilization does not prove globally uncontended execution; especially scalar HTTP 4K varied widely. These are exploratory wall-time measurements, not a causal kernel attribution or statistically powered speed claim.

Both performance binaries include the same ownership repair. Using an unrepaired warmed control could omit six experts and create an invalid speed advantage. Ordinary arithmetic remains the performance reference, not a correctness-qualified replacement.

### CLI prefill seconds: median [min–max], n=3/path

| Processed tokens / input | Ordinary N128 | Mask63 | Scalar | Mask63 cost vs ordinary |
| --- | ---: | ---: | ---: | ---: |
| 1024 / 1025 | 32.073 [31.960–34.947] | 34.679 [34.447–34.943] | 51.532 [51.476–51.547] | +8.13% |
| 4095 / 4096 | 157.471 [156.451–162.121] | 180.699 [175.376–187.625] | 257.957 [255.499–261.248] | +14.75% |

Mask63 prefill throughput is approximately **1.486× scalar at 1K** and **1.428× at 4K**. Input reserves its last prompt token for scalar advancement; 4K is 31 slabs plus 127-token tail. No acceptance threshold was changed to recover speed.

CLI median TTFT seconds (ordinary/mask63/scalar): **32.312/34.899/51.669** at 1K and **157.620/180.846/258.128** at 4K. CLI reported steady-after-first decode tok/s medians: **16.28/15.90/16.59** and **12.60/12.59/12.38**, respectively. These short 32-requested-token samples have 31 reported IDs, all matched across paths; they are not a new complete-token correctness oracle. Exact per-trial ranges, cache counters and hashes are in sanitized JSON.

### HTTP wall seconds: median [min–max], n=3/path

| Request | Ordinary N128 | Mask63 | Scalar |
| --- | ---: | ---: | ---: |
| First 1064-token prompt | 39.561 [39.200–39.903] | 42.454 [40.310–43.066] | 58.921 [56.874–63.539] |
| Same-process warm 1064-token prompt | 37.599 [37.117–39.319] | 40.470 [39.824–41.460] | 61.630 [59.906–79.665] |
| Same-process warm 4008-token prompt | 143.739 [142.500–148.243] | 161.406 [161.276–173.237] | 278.649 [247.298–386.339] |
| Resident follow-up, 4010 cached +17 new | 1.598 [1.510–1.606] | 1.600 [1.595–1.613] | 1.802 [1.744–1.862] |

Median wire TTFT (ordinary/mask63/scalar): **39.333/42.188/58.698**, **37.392/40.246/61.415**, **143.546/161.196/278.364**, **1.448/1.450/1.625** seconds in table order. All actual outputs were two completion tokens: visible `1` on fresh prompts and `READY` on follow-up, then EOS. The configured 64-token maximum was not reached; HTTP decode TPS is not sustained throughput evidence. Fresh requests used zero cached prefix tokens; warm means process/expert cache warmth, not prompt-prefix reuse. Resident follow-up reports actual reuse.

### Physical sampling during performance

A read-only libproc probe sampled charged footprint, lifetime peak and RSS once per second, using process birth time to avoid PID reuse. It allocated no model/Metal state. There are 4230 raw samples. Observer began during the 4K cohort: ordinary has two sampled processes, other paths three; no 1K physical samples. All nine HTTP processes were sampled.

| Scope / path | n | Median observed peak charged bytes | Range | Median sampled max RSS bytes |
| --- | ---: | ---: | ---: | ---: |
| CLI 4K ordinary | 2 | 1,899,179,360 | 1,899,097,464–1,899,261,256 | 9,616,777,216 |
| CLI 4K mask63 | 3 | 1,732,832,392 | 1,732,815,960–1,732,881,496 | 9,665,626,112 |
| CLI 4K scalar | 3 | 1,285,656,032 | 1,285,361,048–1,286,197,280 | 1,293,631,488 |
| HTTP ordinary | 3 | 2,222,042,800 | 2,221,993,624–2,222,255,792 | 9,915,793,408 |
| HTTP mask63 | 3 | 2,056,138,104 | 2,056,039,800–2,056,220,000 | 9,908,699,136 |
| HTTP scalar | 3 | 1,645,234,984 | 1,645,071,168–1,648,413,456 | 1,431,617,536 |

These are charged process ownership and overlapping RSS, not additive physical/unified usage or proof of a mask63 memory reduction. Mapped/shared pages and file-backed expert residency differ. The original observer classified ordinary HTTP by the presence of an earlier overridden `--no-prefill-nrow`; 654 labels were corrected in the derived summary using sequential launch times and the actual final flag. Raw evidence is preserved. `summarize_benchmark_memory.py` reproduces this correction; future observer uses last-flag precedence.

## Files, checks and remaining release work

Runtime repair in ac06b920 changes `metal_infer/infer.m`, `metal_infer/warm_state_cache.inc` and bounded diagnostics in `metal_infer/session_state_diag.inc`; focused tests/reporting retain their separate source commits. This final handoff changes only harness/reporting files: `tools/benchmark_fe027.py`, `benchmark_release_http.py`, `http_memory_probe.c`, `observe_benchmark_memory.py`, `summarize_benchmark_memory.py`, `test_benchmark_memory_labels.py`, `qualify_prefetch_cache_epoch.py`, `qualify_release_adapter.py`, `qualify_release_long_http.py`, `summarize_release_qualification.py`, the live SDK test, ledger and three sanitized result files/two reports. No additional runtime edit is made.

Final model-free checks: seven fail-closed release-summary tests, six watchdog/resource tests and three memory-label tests PASS; changed Python files compile, live SDK JavaScript syntax and `git diff --check` PASS. Earlier TypeScript build and 19 mock transport/generator tests remain PASS; they were not rerun after test-only output flags. The actual modified live harness was executed successfully against repaired native inference as described above.

### Recommended configuration and rollback

- Matched 16K/32K scalar/ordinary/mask63 prefill/TTFT/continuation performance is NOT RUN. Current 1K/4K penalty is real observed cost, not a reason to relax arithmetic. Architect must decide whether it is acceptable.
- Sustained long-output HTTP decode and broader independent long documents are NOT RUN. Actual SDK literal-change behavior is FAIL on both scalar/candidate; isolate model behavior separately from transport/state. GUI installation/presentation remains NOT RUN.
- Repaired B8 native full 32K repeat is NOT RUN; archived single-history B3 32K and repaired B8 16K resident evidence remain separately scoped. Long alternative modes, concurrent sessions, real Metal reset/OOM/disk exhaustion, 64K GPU and iOS are not qualified here.
- Research artifact recovery/persistence remains unavailable; no canonical Drive replacement was made.
- Recommendation: retain explicit experimental opt-in only: M4 24GiB, tiered K8, default GPU linear/attention, lazy32K path, N128, mask63, repaired prefetch. No default/production promotion. Long alternative modes excluded.
- Production never changed, so rollback now requires no action. If a later approved deployment uses this repair, rollback must restore its previously archived binary plus matching state-identity policy; reject/rebuild incompatible state rather than renaming a checkpoint into compatibility. Do not alter a running production service from these test commands.

### Focused exact reproduction (not executed again for this final report)

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
PRIVATE_OUT="/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/mask63-rerun-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$PRIVATE_OUT"
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-release-prefetch-fixed-alt RELEASE_QUAL_EXTRA_CFLAGS='-DSESSION_DIAG_LIMIT=512 -DSESSION_PREFILL_OBSERVE_STRIDE=1'
python3 tools/qualify_prefetch_phase.py --binary "$PWD/metal_infer/infer-release-prefetch-fixed-alt" --turns 3 --out "$PRIVATE_OUT/stateless"
python3 tools/qualify_prefetch_phase.py --binary "$PWD/metal_infer/infer-release-prefetch-fixed-alt" --resident --turns 3 --out "$PRIVATE_OUT/resident"
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-release-prefetch-control RELEASE_QUAL_EXTRA_CFLAGS='-UFLASH_SESSION_STATE_DIAGNOSTICS -UFLASH_FE027_NUMERICS'
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-release-prefetch-performance RELEASE_QUAL_EXTRA_CFLAGS='-UFLASH_SESSION_STATE_DIAGNOSTICS'
FIXTURE='/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin'
python3 tools/benchmark_fe027.py --control "$PWD/metal_infer/infer-release-prefetch-control" --candidate "$PWD/metal_infer/infer-release-prefetch-performance" --scalar-reference "$PWD/metal_infer/infer-release-prefetch-control" --fixture "$FIXTURE" --count 4096 --decode-tokens 32 --repeats 3 --candidate-numerics 63 --timeout 1200 --max-rss-gib 16 --out "$PRIVATE_OUT/performance4096"
python3 tools/benchmark_release_http.py --control "$PWD/metal_infer/infer-release-prefetch-control" --candidate "$PWD/metal_infer/infer-release-prefetch-performance" --out "$PRIVATE_OUT/http-performance"
```

All model drivers enforce the launch GPU gate and owned time/memory guards. Redirect any new logs to the project-root `benchmark-logs/`. The private archived controller scripts preserve exact executed commands for the completed 16K/32K and repaired suite; public drivers provide reproducible new-output invocations. Sanitized results contain source/binary/fixture/checkpoint hashes. Private `build-provenance`, `controllers`, `postfix`, `performance` and `performance-http` retain original artifacts. No private token arrays, tensors or checkpoints are committed.

**NO-GO — BLOCKERS REMAIN**
