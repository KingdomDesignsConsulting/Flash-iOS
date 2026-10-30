# FE-027 Phase 4: MoE combine alignment and convergence

Branch: `experiment/http-resident-prefix-reuse-20261023`.
Starting HEAD: `d1b8265f2edf85b49f2f844056f96abbaabd4f54`.
Production branch/binary, weights, template, routing and port 11241 are unchanged.
PR #2 remains draft; this report is experimental evidence, not promotion approval.

**4K engineering checkpoint:** all known counterexamples and full 4096 pass;
an independent 4K repeat has identical reference/candidate state fingerprints.
Expanded 8K and performance work is still in progress at this checkpoint.

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

[Sanitized run matrix](results/fe027-combine-2026-10-29.json),
[endpoint curves including largest component/layer](results/fe027-combine-error-curve-2026-10-29.csv),
and [authenticated operator comparisons](results/fe027-combine-operators-2026-10-29.json).

## Reproduction and evidence

Run one heavyweight model process at a time. Every launch must pass three
consecutive GPU readings below 30%; the runners use bounded timeouts and fresh
private output directories. Production port 11241 is never used.

```bash
cd '/Users/knagel/.codex/worktrees/http-session-validation/Flash-iOS'
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

## Safety and remaining release boundary

Seven fail-closed combine-summary tests cover missing observations, missing stages,
live/trace mismatch, state mutation and nonfinite metrics. No claim of 16K/32K
qualification follows from this phase. Native oracle timing with snapshot/hash
overhead is not serving throughput. Performance is eligible only after the
required numerical regressions pass. Production integration still requires Lead
Architect review, and PR #2 must remain draft and unmerged.
