# FE-027 Phase 4: MoE combine alignment and convergence

Branch: `experiment/http-resident-prefix-reuse-20261023`.
Starting HEAD: `d1b8265f2edf85b49f2f844056f96abbaabd4f54`.
Production branch/binary, weights, template, routing and port 11241 are unchanged.
PR #2 remains draft; this report is experimental evidence, not promotion approval.

**Correctness through 8192:** all known counterexamples, complete 4K twice and
the 8K fixture pass. Active persistent-state fingerprints are exact at every
observed endpoint. All nine conditional timing trials completed. **READY FOR
ARCHITECT REVIEW**, within the tested scope; production remains NO-GO.

## Proven cause at the preceding combine

Two bounded banks observe actual operands/output at layers **0, 2, 3 and 23**,
rows **0, 1, 7, 31, 63 and 127**. This covers linear and full-attention layers and
24 observed expert configurations. GPU captures are ordered private blits after
the actual scalar CMD3 combine, before its buffers are reused. Grouped operands
are copied after completion. No early GPU wait or model-state repair is used.

At layer 2, row 0, **all operands are authenticated as identical**: residual,
post-normalization input (prior probe), eight expert outputs, expert IDs/order,
eight weights, shared output, and the shared-gate score. The CPU replay matches
the actual mask-31 candidate output byte-for-byte; the original GPU-kernel replay
matches the actual scalar output byte-for-byte. The previously unauthenticated
780/2048-value difference is therefore causal, not just a matching error signature.

The first discrepancy is **sigmoid evaluation**: CPU `expf`/division versus Metal's
fast-math `exp`/division. At this row the sigmoid absolute difference is
`1.4901161193847656e-8`; final-layer-output max is the same, RMS
`1.1660868400994243e-9`, first different float index 0. This becomes the observed
incoming layer-3 difference. This does not isolate exponential versus reciprocal
approximation internally, or prove it is the only possible error in every mode.

### Same-input stages across all 48 captured observations

| Stage | Maximum absolute CPU/GPU difference |
| --- | ---: |
| Each of eight rounded weighted contributions | 0 |
| Accumulation after each of eight experts | 0 |
| Shared sigmoid | 2.2351741790771484e-8 |
| Gated shared contribution | 2.9802322387695312e-8 |
| Residual plus routed experts | 0 |
| Final output | 2.9802322387695312e-8 |

22 observations first differ at sigmoid; 26 are exact throughout. Both live-path
replays authenticate all 48 observations. Seven reference/candidate row pairs
have entirely identical actual operands; the other pairs are still valid private
same-input replays but are not claimed to have identical inherited model inputs.
Replay leaves synchronized active state unchanged. Original scalar fingerprints
remain exact against prior evidence at every common observed endpoint.

Rounded weighted-product stages are diagnostic counterfactual intermediates;
the original fused expression need not materialize them. The staged GPU replay
is accepted only after its final output matches the unchanged original kernel.
No intermediate whole-model state within an N128 slab is inferred.

### Preserved negative experiments

The first build failed because a runtime-sized C array had an initializer; it was
fixed with explicit zeroing. No model ran from that failed build.

The first staged Metal trace failed authentication at all 48 observations. Its
final expression had lost the original kernel's fused final addition. Those
stages were rejected by the fail-closed summary. Explicit final `fma` restores
exact original-kernel output across all 48 observations. Thus the apparent
final-add discrepancy in that rejected trace was a **diagnostic artifact**, not
a second runtime defect. Negative artifacts remain private and are not promoted
to a causal PASS.

A provisional mask-63 pilot used GPU combine on the final layer too. Source
inspection established that scalar CMD3 uses CPU combine there; the final
candidate preserves that eligibility decision. The provisional pilot is not the
final qualification binary.

## Narrow opt-in correction

New bit **32**, combined with the previous mask 31 as **63**, reuses the **unchanged
`moe_combine_residual` GPU pipeline** with the original expert-slot order. It
copies captured residuals/parameters into existing dead post-projection scratch,
binds each routed output at its existing assignment offset, and copies the
completed output back to the slab. No new persistent buffer or snapshot pool.
Batched expert projections/staging and routing remain unchanged. The final layer
and disabled GPU-combine debug path retain CPU combine, matching scalar behavior.

This chooses the scalar's existing numerical implementation rather than changing
its sigmoid, summation, expert order or top-K policy. No tie band, template change,
threshold relaxation or reference-state rebase. Default mode remains unchanged.
The qualified configuration is the current native tiered MLX4 model/default GPU
path; other-mode cross-products are separate gates.

Mask representation now explicitly permits **0–63** (six bits), retaining 255 as
the invalid sentinel. Selective identity adds `fe027-scalar-gpu-combine-v1` only
when bit 32 is set. Masks 0/15/31 retain their prior identities. The version must
advance for future state-affecting combine changes not covered by another hashed
execution field. No executable hash, checkpoint-format or ordinary execution
version change.

## Mandatory regression evidence

The table records maxima over **all observed completed endpoints**, not just the
final position. Persistent fingerprints cover active KV/GDN/convolution and the
established CPU-shadow representation; they do not cover scratch or allocation
padding. Hidden/logit differences remain numerical, so this is not a claim of
whole-model bitwise equivalence.

| History | Persistent state max | Hidden max | Logits max | Result |
| --- | ---: | ---: | ---: | --- |
| Short 129 | 0 | 2.384185791015625e-7 | 1.9073486328125e-6 | PASS |
| Saved resident 304 | 0 | 1.1920928955078125e-7 | 1.9073486328125e-6 | PASS |
| Original 2057 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |
| Extended 2305 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |
| Former failure 3456 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |
| Full 4096 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |
| Independent repeat 4096 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |
| Full 8192 | 0 | 1.9073486328125e-6 | 3.814697265625e-6 | PASS |

Reference/candidate persistent-state SHA256 fingerprints match at every observed
endpoint in these runs: 2, 50, 25, 19 and 27 endpoints respectively. In particular,
303, 1920, 2304 and 3456 no longer have the prior state error. All greedy tokens,
finite-state checks and ten full-attention KV lengths/mirrors pass. The oracle
maintains each path's own evolving bank; it never rebases candidate state from
the scalar bank as a serving workaround.

Both full 4K runs cover all 32 completed slabs. Peak child RSS in the first was
10,103,357,440 bytes (about 9.41 GiB); RSS is not a physical-footprint measurement.
For subsequent accumulation runs, a CPU-only tested watchdog caps the owned
native process at 16 GiB RSS by default (`--max-rss-gib`), with distinct resource
or timeout status rather than a numerical PASS. It never stops unrelated apps.

### Resident continuation and compatibility

Five fresh isolated HTTP cases pass exact active-state fingerprints against an
independent scalar replay: threshold/scalar fallback, minimum slab, slab plus
scalar tail/EOS, two slabs, and explicit system prefix. Four corresponding native
numerical oracles also pass. Each case ends its first response with EOS and then
successfully reuses the resident session for a follow-up. This supplies alternate
conversation histories; it is not a second independent long-document fixture.
The longest HTTP history in this matrix is 304 tokens.

All test servers used 11243 and are stopped before their continuous references
start. The driver now gates both independent model launches on three consecutive
GPU readings below 30%. Server timestamps, exact commands and logs are private.

The native mask-63 Zstd save/process-exit/load sequence matches all 65 observed
positions (141–205). Wrong prefix, execution mode and arithmetic mask 31 are
rejected without changing the valid checkpoint. Old mask-31 and mask-15 files
restore the original 65 fingerprints under their respective modes using the new
binary. Mask zero reproduces the original N128 baseline at 128/129. The synthetic
identity test confirms all **64** enabled-mask identities are distinct and zero's
identity is unchanged. No user profile/checkpoint was overwritten.

The 8K fixture covers all **64 completed slabs**, with identical active-state
fingerprints at every endpoint. Peak child RSS was **10,274,308,096 bytes** (about
9.57 GiB); the live watcher observed 10,193,682,432 bytes and never hit its 16-GiB
limit. Startup GPU readings were `[0, 0, 0]`. This is the longest successfully
qualified native context in this phase. It does not establish 16K/32K numerical
convergence or long independent-document diversity: the supplied 8K fixture
extends the original 4K sequence. Alternate fresh HTTP histories remain short.

[Sanitized run matrix](results/fe027-combine-2026-10-29.json),
[endpoint curves including largest component/layer](results/fe027-combine-error-curve-2026-10-29.csv),
and [authenticated operator comparisons](results/fe027-combine-operators-2026-10-29.json).

## Conditional non-diagnostic performance

Three independent fresh processes per path, balanced rotating order, identical
1025 supplied token IDs, greedy temperature zero/seed 73941, eight requested
generation tokens, identical tiered model/cache policy. Every launch ends its
preflight with three readings below 30% (all three were zero in this cohort).
Reported generated IDs agree across all nine runs. No compilation or concurrent
owned model ran during measurement. Servers were already stopped.

The table measures **1024 prefilled tokens**, excluding the final scalar prompt
token/first LM head from the prefill timer. TTFT includes that additional work.
First N128 workspace/setup and cold process expert-cache effects are included;
these are not steady-state whole-prefill numbers. OS page cache was not purged.

| Path | Median prefill | Range | Sample SD | Median prefill tok/s | Median TTFT | Median process wall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Ordinary N128 | 29.345 s | 29.166–30.888 s | 0.947 s | 34.90 | 29.528 s | 30.165 s |
| Corrected mask 63 | 31.434 s | 31.344–31.703 s | 0.187 s | 32.58 | 31.658 s | 32.386 s |
| Unchanged scalar | 49.001 s | 48.900–49.606 s | 0.382 s | 20.90 | 49.145 s | 49.783 s |

Observed corrected/ordinary median ratio **1.07119**: about **7.12% more prefill
time**, or 2.089 s at this size. Corrected prefill is **1.559× scalar throughput**
(35.85% less time). The corrected and ordinary ranges do not overlap here, but
N=3 and setup-inclusive conditions support only a bounded exploratory result,
not a universal slowdown percentage or production latency SLO. Ordinary N128 is
a performance control; its historical longer-context numerical failures remain.

This comparison covers the entire mask-63 alignment, not bit 32 in isolation.
Existing linear-layer combine timing totals have medians **72.401 ms ordinary**
versus **220.272 ms corrected** across the eight slabs. That measured subset adds
about 148 ms, so the full 2.089-s difference must not be attributed solely to the
new combine correction. Other alignment/attention stages and cold/setup effects
also differ; no unsupported causal optimization claim is made.

First-slab linear-batch component medians are 1504.312/1589.921 ms (ordinary/
corrected), versus 832.380/850.314 ms mean per later slab. This distinguishes
observed first-slab overhead from later component operation; it does **not**
separately isolate JIT from page/cache/setup costs. Both N128 paths finish every
trial with the same reported malloc-cache counters: 444 hits, 7987 misses and
512/512 entries. Scalar's access cadence differs; its policy and fresh-process
initial conditions are matched, not its hit count. Child fault/I/O counters are
preserved in the sanitized measurements.

Post-prefill CLI decode medians are 17.26, 17.07 and 17.73 tok/s (ordinary,
corrected, scalar), respectively. Those are only seven post-first-token steps;
the duration is printed rounded to 0.4 s. They are **insufficient to establish
steady-state continuation differences**. Instrumented HTTP timing is not used
as a performance result, and warm repeated-full-prefill/API latency was not
separately measured. No global guarantee of an uncontended desktop is inferred
from the startup gate alone.

Recommendation: retain the correction as explicit opt-in pending Architect
review. It resolves the measured correctness blocker while retaining batching's
benefit, with a measured cost that must be considered before adoption. Future
dispatch-overhead optimization must preserve authenticated scalar sigmoid/final
arithmetic and rerun the numerical matrix; no expert-union/speculation work is
introduced here.

## Reproduction and evidence

Run one heavyweight model process at a time. Every launch must pass three
consecutive GPU readings below 30%; the runners use bounded timeouts and fresh
private output directories. Production port 11241 is never used.

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
PRIVATE_OUT='/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/fe027-combine-manual-fresh'
make -C metal_infer fe027-experiment
python3 -m unittest discover -s tools -p test_fe027_combine_summary.py

# Authenticate the old CPU/GPU difference before enabling the correction.
FLASH_FE027_COMBINE=1 python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 31 \
  --count 129 --gpu-wait 60 --timeout 300 --out "$PRIVATE_OUT/operator31"
python3 tools/summarize_fe027_combine.py "$PRIVATE_OUT/operator31" \
  --out "$PRIVATE_OUT/operator31/sanitized-combine.json"

# Short operator validation, then 304, 2057, 2305, 3456 and full 4096, in order.
python3 tools/qualify_fe027_combine.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" \
  --history '/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-28-fe027/http-mask15/two-slabs-http/http-records.json' \
  --out "$PRIVATE_OUT/mandatory"

# Only after the mandatory suite passes: independent full 4K repeat.
python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 63 \
  --count 4096 --full-final-slab --gpu-wait 60 --timeout 900 \
  --out "$PRIVATE_OUT/repeat-4096"

FLASH_FE027_NUMERICS=63 python3 tools/qualify_session_nrow.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --out "$PRIVATE_OUT/http"
FLASH_FE027_NUMERICS=63 metal_infer/infer-fe027-experiment \
  --self-test-warm-state "$PRIVATE_OUT/identity64"
FLASH_FE027_NUMERICS=63 python3 tools/qualify_session_disk.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" \
  --history '/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-28-fe027/http-mask15/batch-tail-eos-http/http-records.json' \
  --reject-numerics 31 --out "$PRIVATE_OUT/disk63"

# Only after those gates pass; memory-limited and bounded to 8K.
python3 tools/qualify_session_accumulation.py \
  --binary "$PWD/metal_infer/infer-fe027-experiment" --numerics 63 \
  --fixture '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-8192.bin' \
  --count 8192 --full-final-slab --gpu-wait 60 --timeout 2400 \
  --max-rss-gib 16 --out "$PRIVATE_OUT/full-8192"

# Conditional performance only after correctness, with the GPU gate each time.
make -C metal_infer fe027-control fe027-performance
python3 tools/benchmark_fe027.py \
  --control "$PWD/metal_infer/infer-fe027-control" \
  --candidate "$PWD/metal_infer/infer-fe027-performance" \
  --scalar-reference "$PWD/metal_infer/infer-fe027-control" \
  --candidate-numerics 63 --count 1025 --repeats 3 \
  --fixture '/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/Testing/Temporary Testing Files/Resources/prefill-4k-4096-from-1k.bin' \
  --out "$PRIVATE_OUT/performance"
```

The mandatory runner stops at the first failure; it does not escalate or run
timing afterward. It retains every completed endpoint and its maximum-error
component/layer. The saved 304-token history supplies exact token IDs only;
new live HTTP qualification is recorded separately, not inferred from old
different-arithmetic HTTP fingerprints.

Private evidence cohort:
`/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-10-29-fe027-combine/`.
Controller/build logs: project-root `benchmark-logs/fe027-phase4-*.log`.
Raw tokens, expert IDs, operands, routes and checkpoints remain private.

The implementation/4K checkpoint is commit
`4fa23a66a12ed9cb92eb400be9b651825a3ac284`. Run manifests preserve the original
working HEAD and exact runtime-source/binary SHA256 values, including runs begun
before that commit was published. Follow-up documentation records expanded
results separately; no uncommitted numeric change is implied by the HEAD label.

## Safety and remaining release boundary

Seven fail-closed combine-summary tests cover missing observations, missing stages,
live/trace mismatch, state mutation and nonfinite metrics. No claim of 16K/32K
qualification follows from this phase. Native oracle timing with snapshot/hash
overhead is not serving throughput. Performance is eligible only after the
required numerical regressions pass. Production integration still requires Lead
Architect review, and PR #2 must remain draft and unmerged.

Three CPU-only owned-process tests also pass: successful child exit, RSS-limit
termination and timeout termination. Corrected isolated diagnostic, ordinary
control and non-diagnostic candidate builds pass without compiler warnings.

## Implementation surface

- `metal_infer/fe027_combine_reference.inc`: opt-in original-pipeline combine;
  grouped dispatch selects it without changing routed expert computation.
- `metal_infer/fe027_combine_diag.inc` and `fe027_combine_trace.metal`: bounded
  actual observations, private authenticated replays and staged comparisons.
- `infer.m`, `prefill_nrow_grouped_async.inc`, `session_nrow_oracle.inc`: hooks,
  mask range, selection and active-state preservation check.
- `warm_state_cache.inc`: bit-32 versioned identity and 64-mask self-test;
  Makefile: isolated dependencies only.
- Qualification/summary tools, seven provenance tests, three process-budget
  tests, gated HTTP reference launch and optional three-way benchmark collection.
- Ledger and sanitized reports; raw model data remains private.
