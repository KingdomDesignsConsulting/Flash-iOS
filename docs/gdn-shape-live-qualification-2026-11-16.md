# GDN shape sensitivity — bounded actual-model qualification, November16,2026

## Disposition

**GDN SHAPE REGRESSION: PASS — within the executed bounded matrix.** No Flash-specific persistent-state, routing or greedy-token divergence was reproduced. This is not a universal proof for all inputs, contexts, platforms or experimental kernels. It does not close C11-01 or authorize production integration.

This follows the [component-stage report](gdn-shape-qualification-2026-11-16.md). After the user confirmed an exclusive model window and compressed memory, the eight short actual-model comparisons and a new-file persistent restart were executed sequentially under resource safeguards. No broad16K/32K benchmark or256-endpoint qualification was repeated.

## Source and build provenance

Research branch `experiment/gdn-shape-qualification-20261116` is based on qualified native commit **21a073174fb1feb828f2d28762293d1803e66a9a**. Actual native N32/N64/N128 binaries use its unchanged45 runtime inputs, mask63, tiered K8, existing Makefile optimization/dependencies and lazy32K backend. Separate filenames preserve the qualified reference. Exact binary hashes appear per case in `docs/results/gdn-shape-live-2026-11-16.json`; all45 baseline source hashes, diagnostic variant hashes and compiler-log hashes are in `gdn-shape-native-builds-2026-11-16.json`.

The checkpoint follow-up adds only an early invalid-path guard in the diagnostic `session_disk_oracle.inc`, built as a new `infer-gdn-disk-guarded`. It changes no kernel, arithmetic, routing, serializer, checkpoint compatibility identity or ordinary serving behavior. Work A admission and Work B branches were not merged. The native source baseline and later reporting/test commits are distinguished; a repository HEAD alone is not presented as the source of every older executable.

## Matrix and numerical results

All cases use the exact prefix of the saved technical fixture (full fixture SHA256 `59471a6b8a9215ebc7c0358c36b6d841b8c8efc98aee2d47c0f8e2cd91717f89`). Actual token IDs remain in private `input.json` artifacts; no re-tokenization or expensive prefix generation was done. Scalar and candidate banks evolve independently through the same logical history. Shared completed positions agree across the shape cases; no reference rebase occurs.

| Native slab | Actual tokens | Dispatch configuration | Observed endpoints | Result |
|---:|---:|---|---:|---|
|32|33|Default chains|2|PASS|
|64|65|Default chains|2|PASS|
|128|128|Default chains, exact final slab|1|PASS|
|128|129|Default chains, partial tail|2|PASS|
|32|129|Default chains|5|PASS|
|64|129|Default chains|3|PASS|
|128|257|Default chains, two slabs + tail/common suffix|3|PASS|
|128|129|Both CMD12 chains disabled, all-layer route capture|2|PASS|

Across all20 completed endpoints:

- Maximum persistent-state error **0**, equal nonempty fingerprints and zero differing active state values.
- Maximum final hidden error **2.384185791015625e-7**; maximum logit error **2.86102294921875e-6**.
- Greedy identities, finite-state checks and all ten full-attention KV lengths/mirrors PASS.
- All30 GDN/convolution layers and ten full-attention layers are included in the160-component active-state comparisons. No unobservable intermediate whole-model state inside a slab is claimed.
- Existing limits remain state<1e-3, hidden<=1e-3, logits<=1e-2 plus exact greedy/finite/length/mirror checks. No tolerance or routing policy was changed.

The initial controller passed N32/33 then blocked a second launch on GPU activity. That result was preserved. A fresh continuation controller waited up to60s for three consecutive readings<30% and started only the remaining cases. This is not a bypass, a discarded numerical failure or an extra complete trial. Every launched model had its own GPU and host/RSS admission record, stdin=DEVNULL, timeout and owned-process exit check. All successful native processes exited0.

Default-chain case timestamps ranged15:15:11–15:17:58 PST; the alternative-chain case ran15:26:38–15:26:53. These timings identify tests, not performance claims. Host memory was explicitly compressed before the cohort; no comparison with pre-compression speeds is inferred.

## Routing and per-layer observations

The alternative-chain probe captured128 rows across all40 layers: **5,120 reference and5,120 candidate routing decisions**. Expert IDs and slot order match in every observation; router-score and routed-weight maximum differences are0. Minimum observed raw-score top8/top9 margin is **1.3828277587890625e-5**. All observed incoming-mid/post hidden hashes match; no first routing divergence was found. These are actual per-layer operands/decisions at the existing capture points, not a claim that all other intermediate tensors are bitwise equal.

The unchanged native oracle records greedy equality rather than individual generated token IDs; it is a matched-input forward comparison, not a decoded conversation. Private inputs retain the actual history IDs. Raw gate-projection tensors from the *full model* were not newly dumped; the synthetic component experiment separately captured the actual projection kernel's outputs and found zero differences. No new full-model gate-capture hook was necessary to localize a failure because none appeared. These boundaries remain explicit.

## Persistent restart and common suffix

A new private checkpoint was generated from a real128-token mask63/N128 prefix. A separate process loaded it and advanced the identical saved suffix through257 using scalar target steps. This used the normal selective identity and compressed warm-state save/load functions, not a replacement serializer.

- Save15:25:27–15:25:52 PST, exit0; load15:25:55–15:26:11, exit0.
- **130 matching persistent observations**, positions128..257, including finite/KV checks.
- Save/load compatibility `5823bd807a6318d9`; prefix signature `7142768065e4961c` match.
- Checkpoint size **66,902,082 bytes**. Exact file hash is in the sanitized result.
- Shared positions128,256,257 also match the independent complete N128/scalar oracle fingerprints, tying the restart test to the same token history.
- The existing diagnostic load additionally rejects foreign prefix/mode identities without publishing them. No existing profile/checkpoint was overwritten.

The checkpoint oracle compares persistent state through the suffix; it does not produce decoded text or record a final LM-head sample. The independent forward matrix separately verifies final hidden/logits/greedy equality at257. Do not conflate these observation scopes.

### Preserved diagnostic failure and correction

The first disk driver supplied `gdn-new-profile.state`, shorter than the cache helpers'24-character basename contract. Save failed to produce a checkpoint; the diagnostic report attempted to insert the resulting nil path into an NSDictionary and the owned test process aborted(SIGABRT) at15:21:04. No machine crash or invalid Metal access is inferred. The own-process crash report identifies `sn_disk`/NSDictionary construction; no production inventory was performed.

The driver now uses a normal profile-style basename. The diagnostic oracle validates the derived path **before state advancement**, returning2 for invalid input rather than reaching nil report construction. A three-case Foundation/no-model regression plus source-order check passes. The corrected same logical checkpoint test uses a new directory; the failed artifacts and crash report are retained. Inference arithmetic, existing serialization checks, numerical assertions and compatibility versions were not weakened to obtain PASS.

## Provenance, artifacts and reproduction

Sanitized results: `docs/results/gdn-shape-live-2026-11-16.json`, `gdn-shape-native-builds-2026-11-16.json`, `gdn-disk-path-validation-2026-11-16.json`. Raw input IDs, route scores, state fingerprints, engine logs and reports are private under project-root `benchmark-logs/gdn-shape-20261116/`, archived in `/Users/knagel/My Drive/Flash-iOS/Testing/2026-11-16-c11-gdn-work/live-followup/gdn-all-attempts/`. The own-process crash report and binaries are preserved in that live-followup archive. New checkpoint files stay under `/Users/knagel/Flash-iOS-Work-A/2026-11-16-c11-gdn/`; existing checkpoints are untouched.

Read-only aggregation is reproducible:

```sh
python3 tools/summarize_gdn_short_qualification.py \
 --root benchmark-logs/gdn-shape-20261116 \
 --out /private/tmp/gdn-summary-recheck.json
python3 tools/test_gdn_disk_path_input.py
```

Build the native variants with the actual Makefile:

```sh
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-gdn-shape-128
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-gdn-shape-64 RELEASE_QUAL_EXTRA_CFLAGS=-DFLASH_PREFILL_NROW_N64
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-gdn-shape-32 RELEASE_QUAL_EXTRA_CFLAGS=-DFLASH_PREFILL_NROW_N32
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-gdn-disk-guarded
```

`tools/qualify_gdn_short_matrix.py` and `tools/qualify_gdn_disk_suffix.py` record exact commands, input/binary hashes and timestamps, and require the operator-exclusive flag plus the separately built Work A resource probe/supervisor. Use new output/checkpoint directories. The tested native binaries are archived; future builds need their own fingerprints rather than inheriting a filename's evidence.

## Limits and recommendation

This is a bounded negative result for the tested native32/64/128 shapes, common suffixes and one supported alternative dispatch configuration. Component1/8/16/32/64/128 checks remain separately scoped; N8/N16 were not newly qualified as full-model serving modes. Other histories/seeds, true long context, all mode cross-products, other weights/devices, hardware faults and full-model raw gate-tensor capture remain outside this evidence. No causal CUDA mechanism was assumed present in Flash. No GDN kernel correction or release integration is proposed.

**GDN SHAPE REGRESSION: PASS (bounded tested matrix).**
