# N128 resident-state, cancellation and disk restoration — 2026-10-27

Experimental branch: `experiment/http-resident-prefix-reuse-20261023`.
Starting HEAD: `c35dc78be19bc9e4ba141252fe2cc300b8d30d40`.
Selective compatibility correction: `0b49e08bb5948897a2b43774971213cdba0eec8a`.
PR #2 stays draft. Production branch/binary, model weights and Qwen template are unchanged.

## Verdict and acceptance contract

**Bounded N128 resident execution is NUMERICALLY QUALIFIED on the tested M4
lazy-shared GPU path, not bit-exact to scalar.** Real TCP-reset cancellation and
fresh recovery pass. Actual compressed warm-state serialization survives a
separate-process restart with exact prefix/continuation fingerprints.

No numerical limit was chosen after observing results. The starting source's
`target_verify_layer_state_report()` requires component state max error <1e-3;
`prefill_nrow_control.inc` requires hidden max error <=1e-3, logits max error
<=1e-2 and equal greedy tokens. This qualification retains those thresholds,
requires finite values, and additionally requires exact KV lengths and CPU/GPU
KV mirror equality. Hash equality is reported separately and is never described
as passing where these paths differ.

## Execution semantics inspected before testing

`prefill_nrow_runtime_chunk()` advances one complete 128-row slab layer by layer.
Full attention publishes active K/V and advances its cache length by 128; GPU
convolution and GDN kernels advance their recurrent state over the slab. Command
completion is checked before the endpoint is observed. Intermediate row states
are not available as full-model states and are NOT inferred or claimed.

HTTP enters N128 only for complete slabs in the intermediate prompt region. It
leaves the scalar remainder and final prompt token on the scalar path, completing
the final token before logits/decode. A pending system/tool-prefix capture also
keeps that region scalar. Eligibility uses actual KV lengths and capacities.

The extension records the exact completed IDs of the entire slab but just one
state observation at its endpoint. Successful scalar tails, generated effective
IDs, EOS and request boundaries retain their existing per-position observations.
GPU fences precede fingerprint reads. Active tensor dimensions exclude unused
allocation padding. All ten full-attention layers and all 30 linear layers are
checked, including CPU shadows and GPU K/V mirrors.

## Investigation and actual results

1. The first attempt was GPU-gated (mostly 65–81%); no model launched. A bounded
   per-process counter sample showed WindowServer dominating at that time, with
   lesser Codex rendering. No competing app was stopped.
2. Cached prefix position 13 remained exact. The first observable N128 endpoint
   at 141 differed from scalar by hash. This is NOT evidence that token 14 was
   the earliest divergence; the slab's intermediate full-model states were not
   observed. Subsequent categories were paused for localization.
3. Layer 0 GDN/conv remained exact; layer 1 was the first differing recurrent
   layer. A targeted 524,288-float layer-1 GDN dump measured max_abs
   2.86102294921875e-6, RMS 1.6620027057225405e-8 (475,659 differing floats).
   No full-state disk dump was required. The difference begins downstream of
   layer-0 post/experts; differing grouped/scalar arithmetic is consistent with
   this pattern. No attention/kernel math was changed to force a pass.
4. A native two-bank oracle then measured every active component plus hidden,
   logits and greedy identity using the pre-existing numerical criteria. It
   restores the same state before each scalar/candidate advancement and executes
   the actual production N128 function. Banks are diagnostic-only and bounded;
   capture uses the existing snapshot allocator, not a new serving snapshot pool.
5. A final linkage pass requires the oracle's candidate SHA256 at EVERY observed
   HTTP position to match the actual resident trace exactly. Its scalar reference
   also matches the available independent continuous-replay fingerprints. This
   closes the gap between a standalone kernel check and HTTP resident behavior.

| HTTP case | Batch endpoints | Final position | Max state abs | Max hidden abs | Max logits abs | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Below slab threshold, scalar fallback | none | 175 | 0 | — | — | Exact persistent fingerprints PASS |
| Minimum batch plus final scalar token | 141 | 176 | 1.07765198e-4 | 2.28881836e-5 | 4.91142273e-5 | Numerical + exact HTTP linkage PASS |
| Batch, partial scalar tail, EOS and resident continuation | 141 | 205 | 1.30176544e-4 | 1.93119049e-5 | 9.48905945e-5 | Numerical + exact HTTP linkage PASS |
| Consecutive slabs and continuation | 141, 269 | 304 | 2.60353088e-4 | 1.43051147e-5 | 9.48905945e-5 | Numerical + exact HTTP linkage PASS |
| Explicit system, batching from position zero | 128 | 203 | 2.55107880e-4 | 1.81198120e-5 | 3.91006470e-5 | Numerical + exact HTTP linkage PASS |

Each numerical case had identical scalar/candidate greedy tokens at all measured
positions, exact lengths/mirrors, and no nonfinite values. There are no fabricated
observations inside slabs. These are short synthetic histories, not long-context
or output-distribution qualification. Greedy comparisons after the slab also
cover scalar prefill/decode handoff and the actual completed EOS/history tokens.

## Confirmed compatibility omission and correction

The compatibility key did not distinguish `--prefill-nrow` from
`--no-prefill-nrow`. Measured N128/scalar states are not bit-identical, and the
real warm-state serializer accepts these states, so the selective execution key
now includes that runtime mode. A synthetic mode-toggle regression and a live
load rejection under the opposite mode pass. This is a conservative execution
identity safeguard; regular system/tool-prefix capture currently uses the scalar
path, so this report does NOT claim an observed corrupted production profile.

No full-executable hash was reintroduced, no format/layout or execution-version
constant was bumped, and compatible files are not deleted. This relevant mode
field causes one-time old-identity misses; unrelated rebuilds remain compatible.

## Cancellation / invalidation and recovery

The diagnostic progress hook is opt-in and does not alter cancellation decisions.
A real TCP RST is sent only after observing partial N128 layer progress or a
completed decode forward. This uses actual network disconnection, not a forced
error substituted for cancellation.

| Case | Observed partial state | Observed cancellation completion | Health latency after invalidation | Old session | Fresh recovery |
| --- | --- | ---: | ---: | --- | --- |
| Partial N128 prefill | layer 3 KV=141; other nine full layers=13 | 222.34 ms | 0.65 ms | HTTP 409, full history required | Exact 41-token state PASS |
| Decode | all ten full-attention KV lengths=40 | 74.80 ms | 0.47 ms | HTTP 409, full history required | Exact 41-token state PASS |

Logical session position is zero and the interrupted session is not reusable.
Partial buffers need not be physically zeroed: the contract invalidates the
transaction, then restores the correct base prefix for fresh work. Both fresh
recoveries match each other and uninterrupted scalar replay exactly. This is
invalidation/recreation, not a promise to preserve the interrupted conversation.
The measured cancellation latency includes diagnostic fingerprint I/O and is not
an uncontended serving-performance benchmark.

Cancellation server: 18:44:46–18:45:02 PDT on October 27. Recovery control exited
0 at 18:45:09. No request was sent to production port 11241.

## Persistent warm-state restart

A real N128-produced prefix at position 141 is captured with the existing
snapshot API, actual model/configuration compatibility and exact token signature.
The existing selected Zstd warm-state save path writes it. That process exits;
a separate process loads via `warm_state_load_selected()` and restores via
`serve_state_snapshot_restore()`.

The prefix and all 64 subsequent positions through 205 have EXACT per-component
fingerprints and correct KV lengths; no nonfinite values. Wrong-prefix and
opposite-execution-mode loads reject and leave the valid live state unchanged.

- Checkpoint: 67,374,473 bytes (64.25 MiB), private dedicated test directory.
- Save: 520.88 ms; load + restore: 444.84 ms (single observations, not benchmarks).
- Save process 18:45:13–18:45:29; load process 18:45:32–18:45:44 PDT.
- Uses the normal atomic temp-write, fsync, rename and directory-fsync serializer.
- No existing profile/checkpoint/cache was overwritten or deleted.
- This qualifies the native serializer/restart path. A named-profile HTTP startup
  plus restart integration run is a separate remaining check.

## Reproduction and evidence

Private Drive root:
`Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-27-n128-state-equivalence/`.
Raw tokens, targeted floats, logs and the checkpoint remain PRIVATE. Public
`docs/results/n128-resident-state-2026-10-27.json` contains aggregate metrics only.
Source/binary hashes, commands, timestamps and GPU preflights accompany results.
Every launch requires three consecutive GPU readings below 30%; a failed gate is
NOT RUN. Model processes run sequentially with stdin DEVNULL and bounded timeouts.
No production executable is built or overwritten.

From the experimental checkout (not the production checkout):

```sh
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer session-state-experiment
python3 tools/test_session_trace_collection.py
qualification_run="/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/reproduce-$(date +%Y%m%d-%H%M%S)"
python3 tools/qualify_session_nrow.py --out "$qualification_run/n128" &&
python3 tools/qualify_session_lifecycle.py --out "$qualification_run/lifecycle" &&
python3 tools/qualify_session_disk.py \
  --history "$qualification_run/n128/batch-tail-eos-http/http-records.json" \
  --out "$qualification_run/disk"
```

For the focused model-free compatibility regression, use a NEW directory:

```sh
metal_infer/infer-session-state-experiment --self-test-warm-state "$qualification_run/identity"
```

Build passed warning-free; six collector/history model-free regressions and the
focused synthetic warm-state tests passed. Full broad suites were not rerun.

## Remaining release gates

- Matched-state long-context and many-slab error accumulation; no 4K/32K claim.
- CPU-linear/bypass, legacy GPU KV and other non-default execution modes.
- Named-profile HTTP restart integration (native serializer restart passed).
- Other rollback/error modes: transport half-close, executor failures, OOM/Metal
  errors and disk faults were not added to this bounded matrix.
- Production promotion requires architectural review; PR stays draft.
- LM Studio GUI Regenerate was inspected and unavailable: CLOSED as unsupported
  UI operation, not a pending/failed regeneration test. SDK/mock-controller
  checks do not establish other GUI installation/cancellation/attachment behavior.
