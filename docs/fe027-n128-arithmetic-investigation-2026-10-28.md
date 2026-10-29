# FE-027: N128 numerical drift and selective arithmetic alignment

Experimental branch: `experiment/http-resident-prefix-reuse-20261023`.
Reference source: `c94753bb7fa3ad28bbac887cf6ab861254c738eb`.
Date: 2026-10-28, native Mac mini M4 execution.

**MORE INVESTIGATION REQUIRED. No production promotion.** The opt-in correction
passes the original 2,057-token reproduction, but the attempted 4K qualification
fails at completed position **2304** (last passing endpoint **2176**). A distinct
short two-slab resident history also fails at **303**, during scalar continuation.
It is not a
qualified replacement for ordinary N128. PR #2 remains draft and unmerged.

## Contract and observation scope

Unchanged acceptance: persistent state max absolute error **<1e-3**, hidden
**<=1e-3**, logits **<=1e-2**, identical greedy token, finite values, all ten
full-attention KV lengths equal the logical position, and exact active CPU/GPU
KV mirrors. All 30 linear layers' active GDN/convolution state is compared.
Inactive padding and scratch are not model-state equivalence claims.

The native two-bank oracle executes the same supplied token IDs from zero.
Scalar reference execution remains unchanged. Candidate comparisons are at
completed slabs and explicitly processed scalar-tail positions; no intermediate
full-model state within a slab is inferred. Routing probes are actual per-layer
decisions. All-layer traces contain 5,120 observations per path for one slab; the final
one-scalar-token trace contains 40 observations per path.

## Causal localization

1. At input position 0, layer 0, the residual entering post-attention RMSNorm is
   byte-identical. The N128 CPU normalization differs from the scalar GPU result
   in all 2,048 values, max `2.86102294921875e-6`. Applying the existing scalar
   GPU RMS kernels to that exact input reproduces the reference bit-for-bit.
   The baseline router-score difference there is `2.86102294921875e-6`.
2. On identical shared gate/up inputs, CPU versus existing GPU SwiGLU differs
   in 250/512 values, max `1.1920928955078125e-7`. CPU versus GPU expert/residual
   combine is byte-exact on the tested identical inputs; it was not rewritten.
3. With GPU input/router normalization and shared SwiGLU aligned, seven selected
   Q2 experts are exact through gate/up/activation/down, and the shared output
   is exact. The selected Q4 expert still differs: gate 206/512 values,
   max `1.7881393432617188e-7`; up 199/512, max `1.4901161193847656e-7`;
   activation 238/512, max `5.960464477539063e-8`; output 1815/2048,
   max `6.51925802230835e-9`. These comparisons have identical post-normalized
   input and identical expert order, rather than comparing inherited drift.
4. The source confirms a distinct Q4 evaluation order. Scalar V3 accumulates
   `fma(q, scale*x, bias*x)`; grouped N128 accumulates `(q*scale+bias)*x`.
   A private opt-in Q4 kernel follows scalar arithmetic while retaining M=4,
   eight output rows/256 threads for gate/up, two output rows/64 threads for
   down, lane traversal and SIMD reduction. No routing/tie policy changes.
5. With all alignments, all eight expert gate/up/activation/down vectors, shared
   output and complete layer-0 output are byte-exact in the targeted first-row
   probe. Router inputs/scores at position 0 are also exact through layers
   0, 1 and 2. The first observed residual/router difference moves to full-
   attention layer 3. Its exact responsible sub-operation is **not localized**;
   do not infer that the entire full-attention kernel is defective.

Small local error is not a sufficient criterion: enabling shared GPU SwiGLU
improves the short maximum state error but moves a later failure *earlier*.
The evidence supports multiple continuous arithmetic differences crossing hard
MoE selection boundaries, not an identified KV allocation/ownership failure.

## Executed numerical experiments

Maximum absolute errors across each run; PASS is numerical, not byte-exact.
The failing trials stop at the first failed completed endpoint.

| Candidate | Requested history | Last/failed endpoint | State | Hidden | Logits | Result |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| Preserved c947 reference binary / ordinary N128 | 2057 | 1792 / 1920 | 0.967838436365 | 0.006615519524 | 0.042357683182 | FAIL reproduced |
| Router GPU RMS only (mask 1) | 129 | 129 | 3.19480896e-5 | 2.86102295e-6 | 7.39097595e-6 | PASS short |
| Input GPU RMS only (mask 2) | 129 | 129 | 2.95639038e-5 | 6.67572021e-6 | 6.19888306e-6 | PASS short |
| Both GPU RMS (mask 3) | 129 | 129 | 2.55107880e-5 | 4.76837158e-6 | 6.67572021e-6 | PASS short |
| Both GPU RMS (mask 3) | 2057 | 1792 / 1920 | 0.967841833830 | 0.006614565849 | 0.042362689972 | FAIL |
| GPU RMS + shared SwiGLU (mask 7) | 129 | 129 | 1.35898590e-5 | 3.81469727e-6 | 5.24520874e-6 | PASS short, repeat confirmed |
| GPU RMS + shared SwiGLU (mask 7) | 2057 | 1024 / 1152 | 0.681759834290 | 0.264846801758 | 0.827071785927 | FAIL, repeat localized |
| Plus scalar-order Q4 (mask 15) | 129 | 129 | 5.12599945e-5 | 2.86102295e-6 | 6.49690628e-6 | PASS |
| Plus scalar-order Q4 (mask 15) | 2057 | 2057 | 0.000506043434 | 2.71797180e-5 | 9.05990601e-5 | PASS original reproduction |
| Plus scalar-order Q4 (mask 15) | 4096 | 2176 / 2304 | 0.568868160248 | 0.007261276245 | 0.014543116093 | FAIL; no 8K escalation |

At the old failing endpoint 1920, mask 15 state error is
`0.00023651123046875`, hidden `7.152557373046875e-6`, logits
`2.3603439331054688e-5`. At 2048 and through the final scalar tail it reaches
state `0.0005060434341430664`. The 4K trial uses the unchanged saved 4,096-token
fixture, testing complete slabs (`--full-final-slab`), and stops before 4K.
Greedy identity, finite state and KV geometry/mirrors still pass at the 2304
failure; these do not override the failed numerical criteria.

Mask 7 all-layer localization: first observed expert-set difference at layer
18, input position 1085, reference cutoff margin `3.337860107421875e-6`, candidate
tie, router max difference `3.814697265625e-6`. There are 70 expert-set changes
in the slab (326 order changes). Replacing only the candidate anchor at 1024
with exact scalar state reduces endpoint state error to `0.00011467933654785156`,
hidden `4.76837158203125e-6`, logits `2.6226043701171875e-5`. This is a diagnostic
counterfactual and is **never used by serving or to mark the failed run PASS**.

The corrected mask-15 all-layer recheck reproduces the 2304 failure exactly.
First observed expert-set change: layer **21**, input position **2237**; router
max difference `4.76837158203125e-6`, scalar cutoff margin
`4.76837158203125e-7`, candidate cutoff margin `9.5367431640625e-7`.
There are 109 expert-set changes and 428 order changes in the completed slab.
Both traversal orderings (layer-first and token-first) identify this same first
observed crossing; only observations within the traced slab are claimed.

**New discriminating result:** rebase to exact scalar state at 2176 still fails:
state `0.5688681602478027`, hidden `0.00726318359375`, logits
`0.014548420906066895`, greedy equal. Thus inherited pre-2176 drift is not
necessary for this corrected-path failure. Remaining within-slab arithmetic
alone is sufficient; the earlier baseline counterfactual must not be generalized
into a solution. The precise sub-operation causing the new crossing is not yet
localized. First-token-from-zero layer-3 differences are a useful starting probe,
not proof that all long-history divergence starts in that layer.

## Short resident regression, restart and isolation checks

The existing HTTP/native matrix was run against the explicit candidate binary,
with mask 15 inherited by all child processes. It stopped on the first regression:

| Case | Result |
| --- | --- |
| Threshold / no N128 slab | PASS, exact active component fingerprints |
| Minimum N128 slab | PASS, numerical oracle and HTTP/native linkage |
| Slab + scalar tail / EOS / resident follow-up | PASS, numerical oracle and HTTP/native linkage |
| Two N128 slabs + follow-up | **FAIL at 303**, state `0.3630037307739258`, hidden `0.09349822998046875`, logits `0.4539351463317871` |
| Explicit zero-prefix HTTP case | NOT RUN: matrix stopped; separate native-from-zero probes do not replace this HTTP case |

The short failure repeats with the same exact history and a one-token route
probe. First expert-set change is layer **33**, input position **302**; raw router
score max difference `1.9073486328125e-6`, scalar cutoff margin
`9.5367431640625e-7`, candidate tie. Three layers change expert sets in that
step, seven change order. Greedy, finite state and KV lengths/mirrors still pass.
Starting that **scalar** step from exact scalar state at 302 gives **zero** state,
hidden and logit error. This is inherited N128 drift crossing a scalar routing
boundary, distinct from the 2304 within-slab case. Neither rebase is a runtime fix.

At 37 common HTTP/native candidate observations through position 303, component
digests match exactly; the 14 available common scalar-control/reference points
also match. This is partial observation linkage up to the failed oracle stop,
not qualification of the missing endpoint 304 or intermediate batch states.

Native selected Zstd checkpoint restart passes exact active-state fingerprints
at all **65** observed positions, prefix **141** through **205**. Checkpoint size
**67,380,091 bytes**; diagnostic save **400.080 ms**, restore **354.598 ms**.
Wrong prefix, opposite N128 runtime mode and separate mask-zero process reject.
The different-mask load returns the expected code **3**, reports a different
compatibility key and FAIL with no restored rows, and preserves checkpoint bytes.
These are native restart tests, not a new named-profile HTTP qualification.

Final synthetic warm-state/identity suite PASS: zero experimental mask preserves
the old identity, all 16 masks have distinct keys, and existing corruption,
geometry, atomic-write and identity regressions pass. With the experiment
disabled, positions **128 and 129** reproduce the preserved baseline's active
candidate fingerprints byte-for-byte. This is equality to ordinary N128, not a
claim that N128 is byte-exact to scalar. All four isolated build targets compile
without warnings; 5 route-analysis + 6 collector + 3 coverage tests PASS.

### Exploratory non-diagnostic timing

Same 1,025 saved prompt IDs, same default expert-cache configuration, fresh
processes/cache allocations, eight generated-token limit, alternating order,
three trials per implementation. Every process exits 0; all launches meet the
three-reading GPU gate. Source/build flags and private logs are retained.
Measured interval is **1,024-token prefill including initial N128 workspace/JIT
setup**, excluding model loading and the final scalar prompt token. It is not
resident steady-state throughput. No source compile ran during these trials.

| Non-diagnostic build | Median prefill | Trial range | Median-interval rate |
| --- | ---: | ---: | ---: |
| Ordinary N128 control | 34.289 s | 33.928–36.568 s | 29.86 token/s |
| Mask-15 alignment | 35.100 s | 33.493–36.246 s | 29.17 token/s |

Observed median ratio **1.02365** (candidate +2.37% time), with strongly overlapping
ranges. **No meaningful regression or benefit is established** by this small
exploratory sample; OS-cache/residency and background GPU conditions are not
controlled tightly enough for a causal small-percent claim. Numerical failures
block promotion regardless. Performance optimization is deferred until the
remaining correctness counterexamples are resolved.

## Implementation and selective compatibility

All numeric alternatives require the separate `FLASH_FE027_NUMERICS` build and
`FLASH_FE027_NUMERICS` environment mask. Bits: 1 linear router RMS; 2 layer>0
input RMS; 4 shared GPU SwiGLU; 8 scalar-order Q4 gate/up/down. Mask zero keeps
ordinary arithmetic and the exact existing compatibility hash. Production
build flags, executable, port 11241, user caches, model weights and Qwen chat
template are unchanged.

The new Q4 Metal text is embedded in `fe027_q4.inc` and appended only when bit 8
is selected. Existing production shader files are not changed. Enabled modes
hash an explicit experiment version/mask; bit 8 additionally hashes the exact
selected Metal text. The ordinary format/layout/execution versions and disabled
mode identity remain unchanged. Full executable hashing remains disabled.
Changes to other experimental CPU/host arithmetic must advance the experiment
version or a hashed mode, under the existing cache correctness contract.

GPU RMS uses private 512-byte sum scratch and the existing scalar kernels,
with a completion check. No scalar-reference resets, periodic state repair,
new serving snapshot bank/pool, routing bands, top-K changes or template edits.
The existing full-snapshot oracle remains diagnostic-only. Read-only probes
copy bounded first-row vectors and use private buffers rather than overwriting
serving scratch. Raw token histories, selected expert data and floats stay private.

## Reproduction

Use a fresh private output directory for every run. All drivers require three
consecutive GPU readings below 30%, DEVNULL stdin and bounded execution.

```sh
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
make -C metal_infer fe027-probe fe027-experiment fe027-control fe027-performance
fe_run='/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/FE027-new-run'
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-fe027-probe" --count 2057 --out "$fe_run/baseline"
# The baseline FAIL is expected; run following commands independently.
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 15 --count 129 --route-probe-start 0 --operations --out "$fe_run/same-input"
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 15 --count 2057 --out "$fe_run/original"
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 15 --count 4096 --full-final-slab --timeout 900 --out "$fe_run/4k"
# Stop escalation after the expected 2304 failure. Localize instead:
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 15 --count 2305 --route-probe-start 2176 --route-probe-layers 40 --out "$fe_run/new-failure"
python3 tools/analyze_nrow_routes.py "$fe_run/new-failure/route-probe.json" --out "$fe_run/new-failure/route-summary.json"
```

Evidence root: private Drive `Testing/HTTP-Prefix-Reuse/2026-10-28-fe027`.
Controller/build logs: project `benchmark-logs/fe027-*-20261028.log`.
Each result records token-fixture and executable hashes, source hashes, exact
command, GPU gate readings, times, exit code and per-component errors. Failed
initial GPU gating launched no model. One relative-binary-path launch failed
before inference; the runner now resolves explicit binary paths. Earlier source
hashes describe the working tree at launch; numerical-stage binary provenance
and build commands/logs are retained. Subsequent probe/identity instrumentation
changes were isolated from the tested arithmetic; final binaries are separately
hashed. No runtime-source/binary/patch bundles were uploaded to Drive.

Sanitized metrics: [JSON](results/fe027-arithmetic-2026-10-28.json) and
[error curves](results/fe027-error-curves-2026-10-28.csv).

## Remaining engineering decision

Do not enable this alternative by default. The short-history 303 failure is an
additional counterexample, even though the original 2057-token history passes. The original case alone is no longer
a sufficient release gate: the new 2304 failure must remain visible. First
localize the remaining matched-input operations in the failing slab from the
exact scalar anchor, and the first-token full-attention-layer difference (QKV,
Q/K normalization/RoPE, attention output, o-projection). Expand the
identical-input shared weighting/combine and projection probes across rows too:
first-row exactness does not establish that every row is exact. This is a smaller discriminating step than changing routing semantics
or guessing a global precision/tie adjustment.

Options for Architect review:

- Continue exact arithmetic alignment, retaining batching and unchanged model
  policy. Qualification must cover new histories and larger contexts; current
  first-row exactness is not global equivalence.
- Evaluate a deliberately scalar-compatible full-attention preparation/evaluation
  path while retaining grouped MoE, measuring its cost. This is a future opt-in
  experiment, not implemented or claimed qualified here.
- Retain the already-validated scalar reference for the strict equivalence path.
  This trades prefill throughput for the established within-mode state contract.

No route tolerance bands, changed top-K/tie policy, threshold relaxation or
periodic exact-anchor restoration is authorized or implemented.

## Additional exact commands and changed files

Run independent regressions with fresh output folders. The HTTP matrix is
expected to stop at two-slabs until the remaining issue is repaired.

```sh
FLASH_FE027_NUMERICS=15 python3 tools/qualify_session_nrow.py --binary "$PWD/metal_infer/infer-fe027-experiment" --out "$fe_run/http"
FLASH_FE027_NUMERICS=15 python3 tools/run_session_nrow_oracle.py --binary "$PWD/metal_infer/infer-fe027-experiment" --history "$fe_run/http/two-slabs-http/http-records.json" --starts 13,141 --count 304 --route-probe-start 302 --route-probe-count 1 --route-probe-layers 40 --out "$fe_run/scalar-303"
python3 tools/analyze_nrow_routes.py "$fe_run/scalar-303/route-probe.json"
FLASH_FE027_NUMERICS=15 python3 tools/qualify_session_disk.py --binary "$PWD/metal_infer/infer-fe027-experiment" --history "$fe_run/http/batch-tail-eos-http/http-records.json" --reject-numerics 0 --out "$fe_run/disk"
FLASH_FE027_NUMERICS=15 metal_infer/infer-fe027-experiment --self-test-warm-state "$fe_run/identity"
python3 tools/benchmark_fe027.py --control "$PWD/metal_infer/infer-fe027-control" --candidate "$PWD/metal_infer/infer-fe027-performance" --fixture '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin' --out "$fe_run/performance"
python3 tools/test_nrow_route_analysis.py
python3 tools/test_session_trace_collection.py
python3 tools/test_session_gate_coverage.py
```

Runtime/experimental files: `metal_infer/infer.m`,
`prefill_nrow_grouped_async.inc`, `warm_state_cache.inc`, new
`fe027_alignment.inc` and `fe027_q4.inc`, `session_nrow_oracle.inc`, and `Makefile`.
Only the explicit feature build/mask enables alternative arithmetic.

Drivers: `tools/qualify_session_accumulation.py`, `qualify_session_nrow.py`,
`run_session_nrow_oracle.py`, `qualify_session_disk.py`, and new
`analyze_nrow_routes.py`, `test_nrow_route_analysis.py`, `benchmark_fe027.py`.
Changes add explicit binaries, bounded GPU waiting, complete-final-slab sampling,
strict route coverage, one-step versus slab probes, and different-mode rejection.

Documentation: this report, sanitized JSON/CSV, `FUTURE_ENGINEERING_LEDGER.md`,
and a link from the original release-gate report. PR #2 remains draft.
No production modifications; no model or inference process left running.
