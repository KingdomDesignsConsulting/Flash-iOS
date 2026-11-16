# Grouped MoE Metal research — architectural feasibility (2026-11-16)

**Scope:** Static source research and experiment design only. No M4 execution, inference, runtime changes, checkpoint changes, branch integration or production inspection. Baseline experimental candidate `21a073174fb1feb828f2d28762293d1803e66a9a`; this is **not** a release candidate patch. Work A's admission/remediation and Work B's protocol work must not be rebased or changed by this investigation.

## Primary upstream reference

- [ml-explore/mlx-lm PR #2044](https://github.com/ml-explore/mlx-lm/pull/2044): grouped quantized-expert kernels, open at latest inspection, contributor Tigerly1.
- [Tigerly1/moe-lab](https://github.com/Tigerly1/moe-lab): independently inspect methodology, scripts, data/provenance before any M4 adoption.

PR's currently visible description (November 16 inspection) says: T=1 fused gate/up and grouped down; T>1 tiles up to 8 routed token slots per expert, dequant/weight reuse, Metal simdgroup execution. Its eligibility is **affine 4-bit/group64/no bias**, BF16/FP16, top-k <=8, and specific per-expert batch thresholds. Author reports M4 Pro 48GB Qwen3-30B-A3B 91->98 tok/s B1, 166->200 B8, 220->345 B32; results reflect independent concurrent requests, not Flash speculative verification. The updated PR claims 413 unit tests and relative per-slot error <1e-2 against a FP32 dequantized reference. PR also now reports B1 prefill 8–20% in some tests; this contradicts any older blanket statement that prefill is unchanged, and is not an M4 base / Flash measurement. Do not transpose any reported acceleration to Flash.

## What Flash already implements

Verified by reading exact experimental source:
- `metal_infer/prefill_nrow_grouped_async.inc:21-27`: groups N128 token/expert routes by unique expert, stages otherwise unsafe expert weights, and submits unique groups in a layer command buffer. **Expert grouping already exists**; a port that merely reproduces grouping would be redundant.
- Same file: separate Q4/Q2 Metal pipelines, including `projection_m4_2row_q4/q2` and `gate_up_projection_m4_8row_q4/q2`; grouped stage/cold/cache counters include `expert_stage_ms` and `expert_cache_ms` as overlapping host scopes.
- `metal_infer/infer.m:781+`: tiered **per-expert** 2-bit or 4-bit metadata. `infer.m:1240+`: expert layout and quantization dispatch are selected per routed expert. This differs materially from upstream's uniform affine-Q4 eligibility.
- `metal_infer/fe027_q4.inc`: existing scalar-reference alignment kernels and BF16 conversion arithmetic are important acceptance controls; do not silently replace them with upstream FP32-relative error gates.

## Feasibility determination

**YES for a bounded kernel microexperiment; NO for a direct source port or a release change.** Focus on *additional* weight reuse, dequant fusion, GPU tiling, and occupancy relative to the existing grouped N128 implementation. The biggest practical risk is that the current 32K end-to-end wall time is dominated by environment-dependent expert staging, not necessarily compute. Compare matched residency, input route overlap and tiered expert layout first; do not attribute a kernel win to a change in cache conditions.

## Experiment acceptance contract (for a later, separate owner)

1. **Measurement-only first:** capture representative existing `N=1,2,4,8,16,128` expert routing/group histograms by layer, unique expert counts, Q2/Q4 mix, repeated-token overlap, staged/cache-hit bytes and timings; identify which per-expert M values are actually populated. Use synthetic/model-free data if live access unavailable.
2. **Isolated per-layer kernels:** compare the incumbent grouped Q2 and Q4 matmul paths separately with a prototype that groups up to eight rows per expert. Ensure identical expert IDs/order, inputs, hot/cold packed weights and decode/scales/zero points. Measure GPU timestamps, CPU staging, command-buffer count, page residency and peak RSS under pinned identical conditions. No permanent mode flag until microbench qualification.
3. **Numerical gate:** compare against the frozen scalar/mask63 reference, exact greedy output and expert routing margins; preserve exact active GDN/convolution/KV fingerprints on any integrated prefill/verification experiment. Upstream's <=1e-2 relative output error is NOT Flash's accepted persistent-state criterion. Near-tie routing divergence is a blocker.
4. **Economics:** require improvement in total GPU+CPU+I/O wall time and per-token throughput, not isolated math. For any N2/N4/N8 speculative path, retain baseline serial verifier N1/N2/N4/N8=49.6/98.6/194.1/432.4 ms (layer-major N4 ~247.8 ms); full accepted-token economics include drafter and accepted-prefix commit/rejected-suffix rollback.
5. **Isolation:** no production/Work A/Work B edits; do not change arithmetic mask63, checkpoint identity, model files or promote DFlash/DSpark. Record PASS/FAIL/NOT RUN, toolchain, memory, thermal conditions and exact source SHA.

## Related new findings and routing

- SGLang #49133 GDN gate-projection shape sensitivity: assign actual base-M4 chunk/bucket/cached-state differential testing to Work A, but only on a separate numerical-regression branch. Test exact logical tokens under alternate M/chunk shapes, checkpoint restore, suffix extension and the already-qualified mask63 reference. Do not infer an existing Flash defect from SGLang CUDA behavior.
- SGLang #49550 Responses late-system-message normalization: assign actual template/rendered-prefix/client/Gateway validation to Work B. Flash's current inspected adapter is Chat Completions; Responses is **unsupported unless separately proven**. Test cache reuse only where a supported endpoint exists; never demote system/developer content to user content to increase hit rate.
- Audit C11-01 and C11-02 remediation takes priority over this experimental work. The independent preproduction audit already concluded that llama.cpp PR #31688's graph partition mechanism is not established in Flash's fixed Metal routing.

**Architect recommendation:** Keep grouped Metal optimization in its own research queue until release safety closes. Start with existing route/staging histograms and source-level gap analysis, not a wholesale kernel transplant. No claimed Flash speedup.
