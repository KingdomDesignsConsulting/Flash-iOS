# Resident-session release gates — 2026-10-28 engineering handback

## FE-027 follow-up: original reproduction corrected only in an opt-in prototype

See [the autonomous FE-027 investigation](fe027-n128-arithmetic-investigation-2026-10-28.md).
The preserved baseline still fails at 1920 as recorded below. Selective scalar-
arithmetic alignment passes the original 2057-token test, but the attempted 4K
run fails at 2304, after passing through 2176. **FE-001 remains BLOCKED; FE-027
ACTIVE; no production promotion.** Default serving is unchanged. Prior bounded
FE-002/003/004 qualifications retain their original scope. This follow-up does
not erase or reinterpret the original failure or diagnostic anchor evidence.


Branch `experiment/http-resident-prefix-reuse-20261023`, starting HEAD
`032eb94b4401ced1639aa83fcea3fc6be44d6fc7`.
Verified tooling commit: `120e993eead03fdae7ad5efbac9fe1583c250e7c`.
Disposition: **production NO-GO; PR #2 remains draft and unmerged.**
Architect criteria in `architect-release-gates-2026-10-28.md` remain unchanged.
Prior bounded scalar/N128 evidence remains valid within its documented scope.

## Consolidated verdict

| Gate | Verdict within executed scope | Remaining limitation |
| --- | --- | --- |
| 1. Long/many-slab N128 | **FAIL** at first failing measured endpoint 1920 | 2K completion, 4K/8K/16K/32K, capacity transitions and long HTTP EOS/continuation NOT RUN after failure |
| 2. Named-profile HTTP restart | PASS | Model/config rejection tested by controlled signature-header fault, not replacing actual weights |
| 3. Additional failure/rollback | PASS for real half-close/timeout, checked-forward failure and partial-write preservation | Real Metal/device/OOM/disk hardware failure NOT ESTABLISHED; external executors NOT APPLICABLE to infer HTTP |
| 4. Other modes | PASS for seven short within-mode references and CPU profile restart | Cross-mode numerical parity, long context and all option cross-products NOT ESTABLISHED; bypass model quality NOT APPLICABLE |

No inference kernels, routing policy, Qwen template, weights, production binary,
cache compatibility inputs or format/version constants were changed. New native
hooks are diagnostic-build-only. The sole non-diagnostic write-loop refactoring
keeps `allowed == remaining`, preserving its behavior. No full-executable cache
hashing or serving conversation snapshot pool was introduced.

## Gate 1: first failure and error growth

The existing native matched-token two-bank oracle now accepts a separately bounded
long input (up to configured context capacity, hard maximum 32,768 and the active GPU mirror capacity). HTTP tracing
stays capped at 512. Long fingerprints validate against the native input bound;
no larger serving cache or allocation cap is enabled. CPU-fallback observations
beyond the GPU mirror capacity are not supported by this oracle; snapshot and
Metal buffer extents are checked before comparison reads. Diagnostic capture/restore
continues through the existing synchronized snapshot API.

Input: first 2,057 token IDs of the EXISTING private
`prefill-4k-4096-from-1k.bin` fixture, whose 32-bit count header is validated.
This is a saved 4K-from-1K qualification fixture, not a newly generated natural
2K document or live HTTP prompt. Reference and candidate use identical IDs and
positions. Candidate schedules sixteen consecutive 128-row slabs plus a scalar
tail; reference uses the repaired scalar GPU forward path. The run stops before
completing that schedule, at the first failing measured endpoint.

Limits, selected BEFORE execution, are unchanged: state max abs **<1e-3**, hidden
max abs **<=1e-3**, logits max abs **<=1e-2**, equal greedy tokens, finite values,
exact full-attention KV lengths and CPU/GPU mirrors. Measurements cover all ten
full-attention and 30 recurrent/convolution layers, active tensor extents only.
No intermediate full-model states inside slabs are inferred.

| Completed position | State max abs | Hidden max abs | Logits max abs | Greedy | Result |
| ---: | ---: | ---: | ---: | --- | --- |
| 128 | 2.28881836e-5 | 3.81469727e-6 | 7.86781311e-6 | equal | PASS |
| 1024 | 6.10351563e-5 | 1.62124634e-5 | 1.90734863e-5 | equal | PASS |
| 1152 | 2.39133835e-4 | 7.62939453e-6 | 2.82526016e-5 | equal | PASS |
| 1792 | 2.39133835e-4 | 5.24520874e-6 | 2.38418579e-5 | equal | PASS |
| **1920** | **0.967838436** | **0.006615520** | **0.042357683** | equal | **FAIL** |

All measured KV lengths/mirrors remain correct and state is finite, including at
failure. Greedy agreement does NOT override the numerical failure. A public CSV
contains every observed endpoint. Peak child RSS was 8,149,336,064 bytes; this is
RSS, not a measurement of total unified-memory/GPU physical footprint.

Initial run: **01:26:45–01:30:12 PDT**, October 28, exit 3.
No 4K or larger case was launched after this failure.

### Localization rather than tolerance relaxation

1. Executing only the final slab (1792–1919) scalarly, while preserving previous
   N128 candidate prefix drift, still fails at 1920: state 0.967843503,
   hidden 0.006617069, logits 0.042359352. This is not solely a defect introduced
   by batching that final slab. Run 01:31:54–01:35:03, exit 3.
2. A reproducible route probe observes REAL per-layer expert decisions in the
   failing slab, limited to layers 0–11. It is not a claim to observe intermediate
   full-model state. Both paths provide 1,536 route records. The first expert-SET
   difference in this probed range is **layer 9, input position 1829**. The
   reference cutoff margin is 9.5367431640625e-7; the candidate has an exact tie.
   Maximum raw router-score difference there is 3.337860107421875e-6.
3. The changed expert selection is followed by larger downstream differences.
   The first component exceeding state tolerance at the measured slab endpoint
   is layer-10 GDN (0.001254067); layer-11 K reaches 0.575195789. Largest state
   difference is layer-19 K (0.967838436). The probe does not establish the first
   ever route difference before this slab or the first per-token state breach.
4. A separate counterfactual restores the EXACT scalar anchor at 1792, then runs
   one real N128 slab. State max abs becomes 1.08718872e-4, hidden 1.28746033e-5,
   logits 2.55107880e-5, same greedy. This supports upstream drift causing a
   near-tied hard-routing discontinuity. The baseline result stays **FAIL**;
   rebasing is NOT a qualification pass, proposed serving fix or altered policy.
   One extra probe-only anchor is freed afterward; no serving pool is created.
5. Route reproduction 01:36:55–01:40:07 exits 3 with the original failure values.

The evidence is consistent with small floating-point differences crossing a
non-smooth MoE top-K boundary, not KV length corruption, nonfinite state or a
Metal command failure. It is a genuine failure of the REQUIRED state-equivalence
limits, not a demonstrated wrong final answer. No arbitrary tie band, new routing
policy, relaxed criterion, silent scalar fallback/rebase or kernel change was
used to manufacture PASS. Targeted numerical alignment requires architectural
review; the existing scalar reference remains the safe qualification baseline.

## Gate 2: actual named-profile HTTP lifecycle

A diagnostic-only cache-root override isolates ALL test sources, state files,
cleanup/pruning and profile inventory in a new private directory. Normal builds
retain executable/project anchoring. Real API/CLI and existing selective save/
load paths are used, not a substitute serializer.

Executed with a unique `qual-*` profile:

- API first capture and two resident turns; source JSON and Zstd checkpoint exist.
- Idle server SIGTERM after completed requests; new process selects
  `--flash-profile NAME` and logs a valid restored snapshot.
- Old `session_id` is rejected with 409: profile restores a STATIC prefix, not an
  evolving conversation. A NEW session repeats the same two turns.
- Exact effective IDs and all shared observable fingerprints agree with the
  uninterrupted first process. Initial capture observes 0–39; cached restart
  begins at prefix 11. Only actually observed positions 11 onward are compared.
- A different system prefix falls back without overwriting the source/checkpoint;
  subsequent original-profile inference remains exact.
- Unsupported checkpoint version and foreign model/config compatibility signature
  are injected into the isolated header; startup rejects, rebuilds, and produces
  exact state/behavior. These are controlled header faults, not changed weights.
- A REAL runtime N128/scalar switch rejects the incompatible mode identity and
  rebuilds safely. Short-prefix inference remains exact.

Full matrix: **01:44:13–01:45:36 PDT**, all owned processes stopped between phases.
An earlier harness attempt failed because it demanded identical observation
coverage before a cached prefix. Common positions already matched. The corrected
comparator requires equal token histories, equal end positions, and identical
coverage/hashes from the shared observable start onward; it does NOT invent
restored-prefix intermediate observations. Three new model-free regressions
prove cached coverage is accepted and mismatched/missing observations reject.
The earlier attempt is preserved as an infrastructure failure.

CPU-linear named-profile restart also passes. A final unrelated-rebuild check
uses a different executable SHA to restore that SAME compatible test checkpoint
and reproduce exact state without rebuilding it (02:00:50–02:01:02). Full-binary
invalidation remains disabled. Only isolated test profiles were created/mutated.

## Gate 3: real transport and bounded faults

- Actual `shutdown(SHUT_WR)` preserves the response-reading direction: successful
  HTTP response and resident follow-up, exact state versus ordinary requests.
- Once-per-process, post-layer-4 checked-forward failures during prefill (position
  20) and decode (40) produce HTTP **500**, `session_invalidated` and
  `resend_full_history`; stale continuation returns **409**. Both fresh recoveries
  exactly match baseline and uninterrupted scalar control. Injection sets the
  checked-forward error after real partial advancement; it is NOT an actual
  hardware/Metal command-buffer failure. 01:47:20–01:48:18 including control.
- A REAL streaming client receive deadline of 50 ms followed by TCP RST during
  prefill invalidates the interrupted session; stale 409 and exact fresh recovery
  pass (01:55:58–01:56:10). This is a client timeout, not a server timeout claim.
- A diagnostic byte quota injects EIO after a partial temporary checkpoint write.
  The normal writer fails, removes its temporary file and leaves the previous
  final checkpoint byte-for-byte intact. Focused synthetic warm-state regression
  passes. No real disk hardware failure/ENOSPC was induced.

The contract is explicit invalidation/recreation, not preservation of the failed
turn or physical zeroing of every partial buffer. No tainted session is reused.
Infer HTTP returns tool calls; it does not execute external tools, so external
executor/callback failure is NOT APPLICABLE to this server. Real device faults,
OOM and all malformed-stream/other fault permutations remain NOT ESTABLISHED.

## Gate 4: supported modes and configuration constraints

| Executed configuration | End position | Exact within-mode state | Identifier recall | Restoration |
| --- | ---: | --- | --- | --- |
| `--cpu-linear --no-cmd12-chain` | 73 | PASS | PASS | Named-profile HTTP restart PASS |
| Legacy GPU KV, separate non-lazy build | 73 | PASS | PASS | Cached system prefix/resident continuation |
| Both CMD1→CMD2 chains disabled | 73 | PASS | PASS | Cached system prefix/resident continuation |
| GPU-resident MoE off, both chains disabled | 73 | PASS | PASS | Cached system prefix/resident continuation |
| o-proj V3 off | 73 | PASS | PASS | Cached system prefix/resident continuation |
| tiny-matvec-fast off | 73 | PASS | PASS | Cached system prefix/resident continuation |
| `--skip-linear --no-cmd12-chain` ablation | 112 | PASS | NOT APPLICABLE to normal Qwen quality | Cached system prefix/resident continuation |

Each server and independent continuous control receives the SAME mode flags,
effective tokens and positions. These are short within-mode comparisons, NOT
cross-mode equivalence or long-context/legacy-capacity qualification. Bypass does
not retain the identifier and is explicitly NOT a normal-model quality PASS.
Other quantization payloads/overlays, prediction modes and all flag combinations
were not qualified. Aliases such as `--gpu-linear` are not separate mode claims.

An initial bare `--cpu-linear` launch correctly rejected its incompatible default
GPU linear CMD12 chain before model initialization; it is recorded as an
unsupported COMBINATION, not evidence that CPU-linear is unsupported. The source
also requires both chains off when GPU-resident MoE is disabled. Focused synthetic
regressions verify identity changes for GPU-resident MoE, o-proj, tiny matvec,
CPU-linear, bypass, N128 and both chain switches. No new compatibility inputs or
format/version bump were needed in this assignment.

## Engineering changes and reproducibility

- Extended existing native oracle bound, grouped scalar control slabs and targeted
  route/anchor probes. No per-row full-model claims inside a batch.
- Added opt-in isolated cache roots, once-only checked-forward failures and byte-
  quota write errors; all hooks compile only in diagnostic builds.
- Added separately named legacy diagnostic target and mode arguments shared by
  server and scalar replay. Production `infer` is never overwritten.
- Added actual HTTP profile/fault/timeout/rebuild runners and strict sparse-
  coverage comparison tests. Existing six trace tests plus three new coverage
  tests pass. Both isolated targets build warning-free; focused warm tests pass.

Private root: `Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-28-release-gates/`.
Raw fixture tokens, route scores, float/state logs, profile checkpoints and HTTP
traces stay PRIVATE. Public JSON/CSV contain aggregate metrics only. Commands,
source/binary IDs, fixture SHA, timestamps and GPU preflights accompany evidence.
All heavy model executions are sequential and require three GPU readings <30%.
An initial Mac command approval review timed out before execution; its one
permitted retry succeeded. No safety finding or test PASS is inferred from that.

From the isolated experimental checkout, reproducible commands are:

```sh
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer session-state-experiment session-state-legacy-experiment
release_run="/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/release-repro-$(date +%Y%m%d-%H%M%S)"
python3 tools/qualify_session_accumulation.py --out "$release_run/accumulation"
# Expected exit 3 at position 1920 on the recorded fixture/model; do NOT advance
# automatically to longer contexts after a confirmed failure.
python3 tools/qualify_session_accumulation.py --count 1921 --scalar-slab 1792 --out "$release_run/scalar-last"
python3 tools/qualify_session_accumulation.py --count 1921 --route-probe-start 1792 --out "$release_run/routes"
```

Independent gates (not chained to the expected failing accumulation command):

```sh
python3 tools/qualify_named_profile_http.py --out "$release_run/profiles"
python3 tools/qualify_session_faults.py --out "$release_run/faults"
python3 tools/qualify_session_timeout.py --reference "$release_run/faults/control/continuous-replay-state.json" --out "$release_run/timeout"
python3 tools/run_session_state_mission.py --engine-arg=--cpu-linear --engine-arg=--no-cmd12-chain --out "$release_run/cpu"
python3 tools/qualify_named_profile_http.py --compatible-only --engine-arg=--cpu-linear --engine-arg=--no-cmd12-chain --out "$release_run/cpu-profile"
python3 tools/run_session_state_mission.py --binary "$PWD/metal_infer/infer-session-state-legacy-experiment" --out "$release_run/legacy"
python3 tools/run_session_state_mission.py --engine-arg=--no-cmd12-chain --engine-arg=--no-cmd12-full-chain --out "$release_run/unchained"
python3 tools/run_session_state_mission.py --engine-arg=--no-gpu-resident-moe --engine-arg=--no-cmd12-chain --engine-arg=--no-cmd12-full-chain --out "$release_run/nonresident"
python3 tools/run_session_state_mission.py --engine-arg=--no-oproj-v3 --out "$release_run/oproj"
python3 tools/run_session_state_mission.py --engine-arg=--no-tiny-matvec-fast --out "$release_run/tiny"
python3 tools/run_session_state_mission.py --engine-arg=--skip-linear --engine-arg=--no-cmd12-chain --out "$release_run/ablation"
metal_infer/infer-session-state-experiment --self-test-warm-state "$release_run/identity-and-write"
python3 tools/test_session_trace_collection.py
python3 tools/test_session_gate_coverage.py
```

`qualify_profile_rebuild.py --previous TEST_CPU_PROFILE_DIRECTORY --out NEW_DIR`
requires an actually different diagnostic executable SHA; rerunning the same
binary is deliberately rejected as insufficient evidence of rebuild compatibility.

## Recommendation

**Do not promote.** Preserve accepted short qualification, the scalar reference,
all failing evidence and PR draft. Resolve the demonstrated long-context MoE
branch sensitivity under the architect's existing contract before 4K+ escalation
or production integration. Any proposed exact numerical alignment or revised
routing policy needs targeted architectural review and regression; neither
threshold relaxation nor the diagnostic anchor intervention is a production fix.
No urgent user-run step remains for the executed tests.
