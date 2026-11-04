# FE-027: actual full-attention localization and scalar-compatible operator

> Follow-up: [Phase 4 combine alignment](fe027-moe-combine-alignment-2026-10-29.md) authenticates the remaining sigmoid difference and tests mask 63. The mask-31 failures below remain valid historical controls.

Experimental branch: `experiment/http-resident-prefix-reuse-20261023`. Started from
`5c26430f2790b84516b7384915eb0500abc5392f`; incorporated the documentation-only
`f220bc6` research intake before publication. PR #2 stays draft and unmerged.
Production branch, executable, weights, template, routing policy and port 11241
are unchanged. No server was started for this investigation.

**MORE INVESTIGATION REQUIRED.** The correction passes all prior counterexamples,
but the attempted 4096-token run fails at completed position **3456**, after
passing through 3328. This is not a qualified production replacement.

## Evidence and causal conclusions

The previous [mask-15 investigation](fe027-n128-arithmetic-investigation-2026-10-28.md)
remains valid, including its failures at 303 and 2304. This follow-up adds an
independently selectable full-attention correction, not a reinterpretation of
those failures. Existing limits remain state `<1e-3`, hidden `<=1e-3`, logits
`<=1e-2`, greedy identity, finite state and exact all-ten KV lengths/mirrors.

The Architect's eight source guards and 262,144 synthetic normalization values
pass again. Their synthetic head dimension is 128; the actual model uses **16
query heads, 2 KV heads, head dimension 256 and rotary dimension 64**. The source
test alone cannot establish real model parity.

Actual layer-3 tensors were sampled at input positions/rows **0, 1, 7, 30, 31,
32, 63 and 127**, with the original execution ordering retained. CPU observations
are copied immediately; GPU observations are blitted into private buffers after
their producers in the original command buffer. Existing completion points are
used to inspect them; no early waits or reference-state repair are introduced.
The layer-3 K/V prefix is captured once per bank at row 127 (bounded to 4096
positions); this is not a pool of conversation snapshots.

The first observed discrepancy is already in **layer input at row 0**: 780/2048
values differ, maximum `1.4901161193847656e-8`, RMS `1.1660868400994243e-9`, first
different float index 0. Thus full attention is not proven to be the earliest
source of all model drift. Its intrinsic arithmetic differences are established
separately using identical captured scalar operands.

### Identical-input operator tests

| Operation | Maximum absolute difference over eight rows | Interpretation |
| --- | ---: | --- |
| Scalar vs N128 Q, K and V projections | 0 | Sampled projection arithmetic exact on identical inputs |
| CPU vs GPU Q normalization, nonrotary slice | 9.5367431640625e-7 | Intrinsic RMS normalization difference |
| CPU vs GPU Q/K preparation | 1.9073486328125e-6 | Combined normalization/RoPE; RoPE-only contribution not isolated |
| Reference attention vs original online attention, same Q/K/V/gates | 2.086162567138672e-7 | Intrinsic attention/reduction/gating difference |
| CPU vs GPU gate on identical ungated values | 5.960464477539063e-8 | Intrinsic sigmoid arithmetic difference |
| O-projection replay vs live scalar | 0 | Existing V3 pipeline reproduced exactly |
| CPU residual add vs live scalar | 0 | Sampled residual accumulation exact |

Every replay validation against the corresponding actual scalar output is
bit-exact. Synchronized active-state fingerprints before/after the private
replays are identical. Instrumented mask-15 endpoint fingerprints at 128/129
also match the prior uninstrumented artifact. The scalar reference fingerprints
match the previous investigation at every common observed endpoint: 2 short,
25 original-reproduction and 18 extended-fixture points.

The original scalar path uses CPU preparation/attention for short sequences and
GPU fused preparation with separate score/softmax/value/gate pipelines starting
at sequence length 32 in the qualified default mode. Original N128 uses CPU
preparation and an online attention kernel across the slab. Similar formulas
therefore do not imply the same floating-point execution.

Fused normalized intermediates cannot be observed independently without changing
the kernel. Nonrotary Q elements isolate normalization in a separate private
probe; no claim is made that all combined preparation differences are RoPE.
Ungated corrected CPU outputs are not captured; those comparisons are marked
unobservable. Neither first-row equality nor sampled per-layer tensors establish
intermediate whole-model state equivalence within a slab.

Sanitized full row/stage comparisons, dimensions, exact/numeric counts, first
different indices, RMS and execution-path labels:
[tensor evidence](results/fe027-full-attention-tensors-2026-10-29.json).
The separate [mask-15 control observations](results/fe027-full-attention-control-tensors-2026-10-29.json)
retain the original online-attention path; the validated private replay report
uses mask 31 while explicitly replaying the original online kernel as a control.
Raw tensors, token histories, routes and checkpoint bytes remain private.

## Opt-in corrective experiment

Compile `fe027-experiment` or `fe027-performance` and select
`FLASH_FE027_NUMERICS=31`. Bits 1/2/4/8 retain the previous alignment; **bit 16**
selects scalar-compatible full attention. Mask 15 preserves the old online
attention control. Mask 0 retains the ordinary numerical path and identity.

The correction reuses unchanged scalar preparation and attention pipelines with
explicit row offsets, preserves CPU/GPU selection around length 32, and retains
batched QKV projections and grouped MoE. It uses existing score scratch, ordered
command buffers and checked completion. Legacy GPU/CPU KV mirrors are maintained;
lazy-shared storage continues to alias the same backing. No accepted-token replay,
periodic scalar anchor, routing/tie-policy change or template normalization.

This is an intentionally conservative operator-alignment experiment, not an
optimized new attention kernel. It is qualified only for the tested native MLX4,
tiered, default GPU execution configuration. Other execution-mode cross-products
and long HTTP serving must not be inferred from native saved-token tests.

Compatibility is selective: masks 0–15 retain their previous identities; bit 16
adds explicit `fe027-reference-attention-v1`. Any future state-affecting change
to that operator must advance this identifier or an independently hashed execution
field. Full-executable hashing remains disabled; format and ordinary execution
versions are unchanged.

## Executed regressions

The first three mandatory regressions passed before opening the 4096-token run.
Completed slabs and scalar tails are compared; no unavailable intermediate batch
state is claimed. Scalar/N128 results are **numerically qualified, not bit-exact**.

| Case | State max | Hidden max | Logits max | Result |
| --- | ---: | ---: | ---: | --- |
| Original 2057-token reproduction | 0.00013172626495361328 | 1.621246337890625e-5 | 6.198883056640625e-5 | PASS |
| Saved two-slab history through 304 | 0.0001971721649169922 | 6.67572021484375e-6 | 3.11732292175293e-5 | PASS |
| Extended fixture through 2305 | 0.0003581047058105469 | 6.67572021484375e-6 | 1.621246337890625e-5 | PASS |
| Attempted 4096, stopped at 3456 | 0.001438140869140625 | 8.58306884765625e-6 | 1.621246337890625e-5 | **FAIL** |

Specific former failures now pass: position 303 state `0.0001971721649169922`,
hidden `2.1457672119140625e-6`, logits `8.165836334228516e-6`; position 1920
state `0.00011205673217773438`, hidden `5.7220458984375e-6`, logits
`8.106231689453125e-6`; position 2304 state `0.0003581047058105469`, hidden
`1.9073486328125e-6`, logits `8.58306884765625e-6`.

The 304-token regression reuses the exact saved HTTP history's token IDs with
`--history-for-tokens-only`. It does **not** claim that the new candidate matches
old mask-15 HTTP state fingerprints. Default strict HTTP linkage remains enabled
unless this option is explicitly supplied.

[Sanitized run matrix](results/fe027-full-attention-2026-10-29.json) and
[complete endpoint error curves](results/fe027-full-attention-error-curve-2026-10-29.csv)
retain successful endpoints as well as the negative result.

Seven fail-closed tensor-summary tests pass, covering missing samples, absent or
failed replay validation, state mutation, missing stages and invalid geometry.

The new failure is in stored layer-23 K (`0.001438140869140625`) and V
(`0.0010395050048828125`). All ten KV lengths/mirrors remain valid and state is
finite. Final-position hidden/logit errors are only `2.1457672119140625e-6` and
`1.1920928955078125e-5`, with identical greedy tokens; these facts do not override
the strict state failure. No positions beyond 3456 were executed. Performance
trials were deliberately **NOT RUN** after this failure. The benchmark runner's
new `--candidate-numerics` selector is prepared but conveys no timing result.

## Final-slab localization and checkpoint safeguards

The 3456 failure reproduces with the final diagnostic build. All 27 completed
endpoints, including both reference and candidate fingerprints, match the first
failed 4K attempt exactly. The final slab contains **5120 actual route observations
per bank** (128 inputs × 40 layers): **zero expert-set changes**, three expert-order
changes (layer/position 15/3361, 26/3392, 28/3367). There is no new top-K set flip
in this slab. This does not establish that earlier slabs had no route changes.

The diagnostic exact scalar anchor at 3328 reduces the end-state maximum to
`9.918212890625e-5`, hidden `6.854534149169922e-7`, logits
`5.9604644775390625e-6`, with the same greedy token. Thus inherited state materially
contributes to the new failure; remaining within-slab arithmetic is nonzero.
The intervention **retains FAIL** and is never used as a serving workaround.

### Preceding layer-2 combine

A final short first-row diagnostic selects layer 2 without changing its serving
math. Reference/candidate `h_mid` and post-normalization input are byte-exact,
routing weights/order match, all eight expert output vectors are exact, and the
shared output vector is exact. The resulting layer output differs in **780/2048
floats**, max `1.4901161193847656e-8`, RMS `1.1660868400994243e-9`—the same measured
signature as the incoming layer-3 difference. Independently applying the existing
CPU combine formula to actual scalar operands gives the same error signature
against the actual scalar GPU combine. This establishes an intrinsic combine
arithmetic difference and strongly localizes the remaining first-row seed before
full attention. The diagnostic's endpoint reference/candidate fingerprints still
match the earlier 129-token run exactly.

The GPU `moe_combine_residual` versus CPU weighted accumulation/sigmoid/final-add
is now the next bounded operator to align; its internal suboperation has not been
isolated. Shared-gate-score identity and byte-for-byte CPU-replay-to-candidate
confirmation are **not established** by the retained diagnostic. An extra proof
extension could not run: the GPU stayed at 100%, the three-below-30 gate returned
NOT RUN, no model launched, and that unexecuted extension was reverted. There is
no new timing claim. Do not treat matching error signatures as a stronger proof
than the actual checked operands provide.

| Independent safeguard | Result |
| --- | --- |
| Final-build 129-token tensor/replay check | PASS; private replay leaves active state unchanged |
| Experiment disabled, positions 128 and 129 | Exact old ordinary-N128 candidate fingerprints |
| Synthetic selective identity test | PASS, all 32 masks distinct; zero unchanged |
| Mask-31 native Zstd process restart | Exact state fingerprints at 65 positions, 141–205 |
| Wrong prefix/runtime mode/arithmetic mask | Rejected; valid checkpoint preserved |
| Old mask-15 checkpoint with new binary | Exact prior 65 fingerprints and compatibility; file preserved |

Mask-31 checkpoint: **67,376,487 bytes**; observed save **427.762 ms**, restore
**493.025 ms**. These diagnostic transfer times are not a serving-performance
qualification. The copied old mask-15 checkpoint is 67,380,091 bytes and was
loaded without changing the original artifact. No user profile was touched.

## Reproduction

Use a fresh private output directory for each command; GPU runners require three
consecutive utilization readings below 30%, isolated model execution and bounded
timeouts. The fixture is the existing private `prefill-4k-4096-from-1k.bin`, SHA256
`6a33afc46eb145523728289bbaffc37bcfa9e2215b7f4c5558b9bf4d339514d8`.

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer fe027-experiment fe027-performance
python3 -m unittest discover -s tools -p test_fe027_tensor_summary.py
python3 tools/test_fe027_full_attention_prepare.py

python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 31 \
  --count 2057 --gpu-wait 60 --timeout 900 --out "$PRIVATE_OUT/original-2057"

FLASH_FE027_NUMERICS=31 python3 tools/run_session_nrow_oracle.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" \
  --history "$PRIVATE_HISTORY/two-slabs-http/http-records.json" \
  --history-for-tokens-only --starts 13,141 --count 304 \
  --out "$PRIVATE_OUT/resident-304"

python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 31 \
  --count 2305 --gpu-wait 60 --timeout 900 --out "$PRIVATE_OUT/extended-2305"

python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 31 \
  --count 4096 --full-final-slab --gpu-wait 60 --timeout 900 \
  --out "$PRIVATE_OUT/full-4096"

# Expected FAIL at 3456; counterfactual is diagnosis, never serving policy.
python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 31 \
  --count 3456 --full-final-slab --route-probe-start 3328 \
  --route-probe-layers 40 --gpu-wait 60 --timeout 900 \
  --out "$PRIVATE_OUT/localize-3456"
```

For the preceding-layer combine probe, use `FLASH_FE027_OPERATION_LAYER=2`
with a 129-token run and `--operations --route-probe-start 0 --route-probe-layers 4`.
The default diagnostic layer remains zero. This selector never changes serving
arithmetic.

For actual layer tensors add `FLASH_FE027_FULL_ATTENTION=1` to a 129-token run;
then run `tools/summarize_fe027_full_attention.py PRIVATE_RUN --out SUMMARY.json`.
Do not publish the raw run directory.

Private evidence cohort:
`/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-28-fe027-full-attention/`.
Execution timestamps are actual ISO timestamps in private manifests; native runs
span October 28–29 PDT; most native runs occurred on October 29 despite the
cohort's October 28 name.
Build logs are under the project root `benchmark-logs/fe027-fa-*`.

Additional bounded checkpoint and disabled-mode commands, plus a prepared
performance command to use **only after correctness is established**:

```bash
FLASH_FE027_NUMERICS=31 python3 tools/qualify_session_disk.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" \
  --history "$PRIVATE_HISTORY/batch-tail-eos-http/http-records.json" \
  --reject-numerics 15 --out "$PRIVATE_OUT/disk-mask31"

FLASH_FE027_NUMERICS=31 metal_infer/infer-fe027-experiment \
  --self-test-warm-state "$PRIVATE_OUT/identity32"

FLASH_FE027_NUMERICS=0 python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 0 \
  --count 129 --gpu-wait 60 --timeout 300 --out "$PRIVATE_OUT/disabled-129"

make -C metal_infer fe027-control fe027-performance
python3 tools/benchmark_fe027.py \
  --control "$PWD/metal_infer/infer-fe027-control" \
  --candidate "$PWD/metal_infer/infer-fe027-performance" \
  --candidate-numerics 31 --count 1025 --repeats 3 \
  --fixture '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin' \
  --out "$PRIVATE_OUT/performance-mask31"
```

`PRIVATE_HISTORY` is the private `2026-10-28-fe027/http-mask15` directory;
`PRIVATE_OUT` must be a fresh private cohort. These commands do not start HTTP
servers. Do not substitute an existing user profile's checkpoint directory.

## Remaining release boundary

No production approval follows from these tests. Larger contexts, more token
histories, full HTTP/lifecycle coverage with the new arithmetic, and execution-mode
cross-products remain separate gates. Existing mask-0 and mask-15 failures are
retained. A tiny inherited layer-3 input difference remains; the correction does
not establish universal bitwise equivalence or immunity to every near-tie route
crossing. Architect review is required before changing defaults or promotion.
The next experiment should align/validate the preceding expert-combine operator
on identical operands across multiple rows, then rerun the known cases and the
3456 counterexample. Do not replace this with routing stabilization or periodic
reference-state restoration.

## Changed implementation surface

- `metal_infer/infer.m`: diagnostic observation points and mask range 0–31;
  original scalar arithmetic unchanged.
- `metal_infer/fe027_full_attention_diag.inc`: bounded actual tensor captures and
  private identical-input operator replays.
- `metal_infer/fe027_attention_reference.inc`: shared encoders for diagnostic
  replay and opt-in scalar-compatible N128 attention.
- `metal_infer/prefill_nrow_grouped_async.inc`: bit-16 selection and diagnostics;
  batched QKV, grouped experts and default online attention retained.
- `metal_infer/session_nrow_oracle.inc`: observation lifecycle and active-state
  preservation assertion around private replay; selected preceding-layer combine
  operand/replay checks, defaulting to the original layer-zero diagnostic.
- `metal_infer/warm_state_cache.inc`: explicit bit-16 execution identity, contract
  comment, 32-mask identity self-test; old identities preserved.
- `metal_infer/Makefile`: isolated target dependencies; production flags unchanged.
- `tools/qualify_session_accumulation.py`: new source-header provenance.
- `tools/run_session_nrow_oracle.py`: explicit saved-token-only mode; strict HTTP
  fingerprint linkage remains the default.
- `tools/summarize_fe027_full_attention.py` and its seven-test companion: fail-closed
  sanitized comparison report; raw tensors are not included.
- `tools/benchmark_fe027.py`: explicit candidate mask selector, default still 15;
  performance not run following the numerical failure.
- Ledger, historical-report follow-up pointer, this report and sanitized evidence.
