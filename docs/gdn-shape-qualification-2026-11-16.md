# GDN shape-sensitivity component qualification — November16,2026

## Isolation, source and verdict

Separate branch: `experiment/gdn-shape-qualification-20261116`, created from the numerically qualified candidate **21a073174fb1feb828f2d28762293d1803e66a9a**. No admission-branch code, production, Work B, PR2/3, model weights, checkpoint identities or existing tolerance changed. Native runtime files are unchanged; only a standalone probe/driver and research evidence/docs are added.

**GDN SHAPE REGRESSION: INCOMPLETE.** Actual M4 synthetic component tests PASS with byte-exact results, but full-model state/logit/routing/disk-restoration coverage is NOT RUN. Do not describe the bounded component result as proof that all supported serving shapes are equivalent. The requested full-model single-heavyweight window was not inferred by inspecting production; operator confirmation/resource admission remains necessary.

## Primary upstream evidence

Read [SGLang issue49133](https://github.com/sgl-project/sglang/issues/49133) and its returned comments, not only the TechWatch synopsis at research commit1ea6ab3e01ba183472c2886fb2598e21a08c8a25. [B300 localization](https://github.com/sgl-project/sglang/issues/49133#issuecomment-6719225779) identifies shape-dependent BF16 gate GEMM selection, small gate differences and downstream amplification. Later SM120 reports implicate multiple projections and retain some unexplained lengths. These are upstream CUDA/model-specific observations, not a Flash defect or a kernel to port.

The research handoff correctly prioritizes admission work. The Flash model/layout differs: default gate projections are native affine MLX4 at2048→32, versus the upstream skinny BF16 case. `tiny_matvec_target_shape`/`tiny_matvec_select_v3` in infer.m selects `dequant_matvec_4bit_fast` for this shape. `prefill_nrow_encode_dense_rows` loops over rows, dispatching the same M1 kernel per row. There is no logical M parameter passed to that kernel; grouping changes encoder/command count, not a cuBLAS-style shape autotuner. The optional dense-M2 experiment is not the qualified default and is not silently enabled here.

Flash's existing N128 recurrence is `gdn_chunk` in `prefill_probe/chunk_kernels.metal`. Scalar uses `gated_delta_net_step` in shaders.metal. Conv chunk owns its three-token tail; logical counts are explicit. Native N32/N64/N128 compile choices exist; N16 is the original benchmark geometry rather than an advertised default production choice. Component chunk1/8/16/32/64/128 tests below do not create six newly qualified full-model serving geometries.

## Executed M4 probe

The driver extracts the **unchanged** current projection, decay/beta and scalar recurrence kernels from the pinned shaders, plus the original chunk recurrence/convolution source. It compiles a small independent Metal library with the runtime's Metal3.1/Fast math settings. No model is loaded. Deterministic synthetic Q4 weights, BF16 scales/biases, inputs and recurrent operands use seed7719; generated operands are reproducible, not model token IDs.

Projection dispatch preserves production32×2048,group64,64-thread M1 geometry. Tested logical input row counts17,32,33,129, with command/recurrence chunk widths1,8,16,32,64,128: **24 cases**. A fixed logical history is compared at its completed final position, not at unobservable intermediate positions inside a batch. The extra rows in longer inputs retain identical first17 projection inputs; first17 output rows are compared explicitly across all four lengths. GDN consumes computed projection gates, while convolution is independently tested with synthetic input (it is not claimed to drive the same full QKV/model graph).

| Measurement | Result |
|---|---|
|Actual final-run GPU admission|21%,22%,26%, three readings below30%|
|Cases|24/24 PASS, all24 byte-exact|
|Alpha/beta gate projection maximum error|0 /0|
|Final GDN-state maximum error|0|
|GDN-output maximum error|0|
|Convolution-tail maximum error|0|
|Nonfinite values|0|
|Common first17 projection rows at lengths17/32/33/129|Byte-exact|
|Completed-boundary RAM snapshot and common suffix|GDN and convolution tails byte-exact|
|Metal allocated buffer bytes|18,776,064 (about17.91MiB), not total process peak|

The RAM test advances to64 using chunk16, captures completed state and conv tail, appends the same suffix through129 using chunk32, restores the64-position bytes after GPU completion, then replays that same suffix using chunk8. Final GDN and conv diffs are zero. This is a RAM round trip, not serialized warm-state format/identity qualification.

No first divergence was observed in these components. No inference-kernel correction was justified or made. Exact state checks are reported in addition to unchanged numerical gates; no tolerance was relaxed. The component probe's numeric ceiling is not substituted for the full model's state<1e-3, hidden<=1e-3, logits<=1e-2, greedy/routing/finite/KV criteria. Actual model hidden/logit/token tests are absent.

## Matrix and explicit gaps

| Requested category | Executed evidence / status |
|---|---|
|Chunk1/8/16/32/64/128|PASS synthetic projection/recurrence/conv components|
|Exact/nonexact bucket counts|PASS component rows17/32/33/129; no graph padding/serving claim|
|Cold versus restored continuation|PASS synthetic zero-state and completed RAM anchor; model disk restart NOT RUN|
|Same prefix, appended common suffix|PASS component projection prefix and RAM GDN/conv suffix|
|Fixed versus alternative command partition|PASS same fixed kernel under changed command boundaries|
|Other math pipelines/dense-M2 autotuning|NOT RUN, not qualified default|
|Scalar reference versus full mask63 N128|NOT RUN at actual full-model level|
|Actual token IDs / first differing token|NOT RUN; synthetic row indices are not tokenizer IDs|
|Per-layer model hidden/projection capture|NOT RUN; one synthetic component shape only|
|Expert IDs/routing margins|NOT RUN; no MoE/model instantiated|
|Logits/greedy/final decoded suffix|NOT RUN|
|All-layer GDN/conv/KV fingerprints and KV lengths|NOT RUN in full model; component state hashes retained|
|Serialized checkpoint identity/reload|NOT RUN; no existing checkpoints rewritten|
|Longer full-model contexts|NOT RUN; no broad16K/32K benchmark or256-endpoint rerun|

Thus the defensible bounded negative result is **no shape/command-partition defect reproduced in the executed synthetic fixed-M1 gate/GDN/conv matrix**. It is not the full “all supported shapes pass” go/no-go condition.

## Reproduction and provenance

```sh
python3 tools/run_gdn_shape_micro.py \
 --out "$PWD/benchmark-logs/gdn-shape-$(date +%Y%m%d-%H%M%S)"
```

Requires native Apple Metal access (outside the restricted execution sandbox) and enforces three GPU readings<30%. Each probe has a90-second timeout, stdin=DEVNULL and explicit exit status. It compiles only the standalone probe, never production infer. `build.json` records baseline, kernel/input-source hashes, harness hash, binary hash and prelaunch readings. Generated Metal source and binaries/logs remain in the evidence output. The harness was new/uncommitted while measured; its exact source hash is recorded and the publication commit retains that source. No claim of an already-clean baseline-only executable is made.

Durable synthetic artifact archive: `/Users/knagel/My Drive/Flash-iOS/Testing/2026-11-16-c11-gdn-work/gdn-logs/`. Original passing and failed-before-GPU attempts are retained.

Sanitized evidence: `docs/results/gdn-shape-micro-2026-11-16.json`. Raw/reproducible synthetic artifacts and build logs: `benchmark-logs/gdn-shape-20261116/`. First compile failed before GPU use because helper `pipe` collided with POSIX pipe; it was renamed without changing kernels. The initial passing component probe and final extra prefix/conv checks are preserved as separate attempts. Source/binary hashes distinguish them.

Future confirmed-exclusive short full-model command (NOT RUN):

```sh
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-gdn-shape-mask63
python3 tools/qualify_session_accumulation.py \
 --binary "$PWD/metal_infer/infer-gdn-shape-mask63" \
 --count 129 --numerics 63 --gpu-wait 60 --timeout 300 \
 --max-rss-gib 16 --min-host-free-percent 35 \
 --out "$PWD/benchmark-logs/gdn-model-129-$(date +%Y%m%d-%H%M%S)"
```

The existing saved fixture is read-only. This command has its own GPU/host/RSS/time checks but is not proof of the admission branch's ongoing supervisor. Only run after independent resource/exclusivity approval; preserve its original fixture SHA and exact IDs privately. If it fails, stop at the first measured divergence and localize before broader expansion. If it passes, extend narrowly to257 and supported N32/N64 builds with matched positions, then actual disk/continuation tests. Do not infer unobservable per-token state in a slab. A separate full-model gate-projection capture hook would be needed to localize a newly reproduced model divergence; none was added speculatively to the release candidate.

No release integration is proposed from this component experiment.
