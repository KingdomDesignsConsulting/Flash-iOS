# Workstream A: mask63 release closure — 2026-11-04

IN PROGRESS. No promotion disposition yet. Production, arithmetic defaults, model files and existing profiles remain unchanged. PR #2 remains draft. Work A starts from verified remote experimental HEAD `66adf92e2ea950528917000d1b59b788e1687371`; intervening commits since `3df795af` change only documentation. Runtime repair remains `ac06b920dbb7e26b804480b36eea4dbe83b40d4e`.

## Isolation and integration

Dedicated branch: `work/release-mask63-final-qualification`; worktree `/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS`. Work A owns inference/release harnesses. Work B owns Gateway/MCP/agent validation. No Work B code is imported or edited. Integrate separate focused commits only after testing and Architect review; do not merge/cherry-pick automatically. Neither production port 11241 nor another thread's worktree is used for inference.

One heavyweight model process at a time. The currently running native oracle is `infer-work-a-release`; all later harnesses require its completed manifest-bound numerical and actual-GPU-routing evidence. No speculative integration, state rebasing, new KV pool, template change or tolerance relaxation.

## Frozen candidate and A1 evidence

- Source tree `22260f90486cec991414db362b89d295865c9ca6`, 45 runtime source hashes.
- Candidate SHA256 `5960178f4dbc677a4b7fa660b8a9fb46773ea3dadc495f5604b400cc7f194602`.
- Manifest SHA256 `86f5ffa6bd6ce42dcc81a934fdc82040a8f1059cf14ec53ec23e575957f56fce`.
- Configuration: Qwen3.5-35B-A3B tiered Q2/Q4, 40 layers, 256 experts, K8; production N128/M4-8row gate-up bitsplit/M4-2row down, opt-in mask63, default GPU linear attention, lazy shared 32768 GPU KV window. Decode prefetch stays enabled; ownership revision `nrow-prefetch-ownership-v2`.
- Global execution version 3, layout version 2, raw storage version 1 / Zstd storage version 2. Full executable hashing remains disabled. No cache-policy change.
- Existing warm-state self-test PASS, including all 64 arithmetic identities, unaffected scalar/CPU identities, selective ownership epoch, malformed/corrupt state and partial-write preservation. This is synthetic evidence, distinct from later live restore.
- 257-token preflight PASS, 14:35:08–14:35:58 PST. State error 0, hidden `1.1920928955078125e-7`, logits `1.9073486328125e-6`; observed RSS 7,404,044,288 bytes. GPU launch readings 22/25/21 percent.
- Separate rebuild under the same executable basename has identical file-backed sections and normalized payload, but different Mach-O UUID/ad-hoc signature bytes. Normalized SHA256 `d9f44e6e8db04973efe4d03190759241cc98552e664f288f5f2391e41d485e69`. This is not whole-file binary equality and is not a cache key. The actual tested executable is never overwritten. Three model-free comparator tests PASS and prove real payload changes are not excluded.

The complete repaired-build native 32K test entered inference at **14:36:49 PST**. Estimated conservative process bound 13,630,038,016 bytes, host availability 55% at launch, process ceiling 18GiB plus 6GiB system reserve; actual watchdog limit 16GiB RSS, host free floor 15%, 10800-second timeout. No conclusion is drawn before all 256 endpoints and actual ten-layer GPU boundary markers pass. These overlapping memory measures must not be added as independent unified-memory allocations.

## Gate status at engineering checkpoint

| Goal | Status | Scope |
| --- | --- | --- |
| A1 freeze / identity | PASS | Manifest, source/model metadata, isolated variants, synthetic identity and measured short preflight |
| A2 repaired native 32K | RUNNING | Full independent scalar/candidate history from zero; original fixture copied read-only |
| A3 intended-capacity performance | NOT RUN | Cold/warm paired long HTTP harness prepared; no performance launch before A2 |
| A4 sustained decode / lifecycle | NOT RUN | Actual length criterion, scalar/candidate sampled IDs and active states; uninstrumented timing follows only actual sustained PASS |
| A5 literal-change diagnosis | NOT RUN | Exact original SDK input, controlled history/thinking/sampling variations and identical-token fresh scalar CLI; no assumed model-only cause |
| A6 release engineering | PARTIAL | Build reproducibility characterized; deployment and rollback remain review-only |

Eight focused model-free checks pass: three Mach-O comparison tests and five fail-closed native-gate tests. Gate validation requires all positions 128..32768 in order, exact nonempty fingerprints, unchanged numerical limits, finite state/greedy/KV checks, and candidate-specific GPU markers in all ten layers at 8192, 8193, 16384, 16385, 24576 and 32768. Generic scalar-first routing logs cannot substitute for candidate evidence.

## Storage and provenance

Raw artifacts are outside Google Drive: `/Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release/`. This includes copied original token fixtures, original SDK record, source/runner freeze, binary variants, manifests and raw traces. Original Drive artifacts are read-only and retained. No historical artifact or checkpoint is deleted. Only sanitized summaries and harness code go to GitHub.

Small build/controller logs use project-root `benchmark-logs/work-a-*-20261104.log`; that path resolves into the Drive mirror, so large state/tensor outputs are explicitly kept in the non-synced root above. Oracle snapshot banks stay in RAM. RSS, libproc charged footprint, Metal reservations and CPU aliases are separate overlapping metrics.

## Reproduction

Use fresh output directories; do not overwrite the currently running executable. Future manifest creation can copy and authenticate the existing complete fixtures automatically:

```bash
cd '/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS'
OUT="/Users/knagel/Flash-iOS-Work-A/rerun-$(date +%Y%m%d-%H%M%S)"
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=infer-work-a-release
python3 tools/create_work_a_manifest.py --binary metal_infer/infer-work-a-release \
  --fixtures-root '/Users/knagel/My Drive/Flash-iOS/Testing/HTTP-Prefix-Reuse/2026-11-02-mask63-release/corpus' \
  --out "$OUT/release-manifest.json"
python3 tools/qualify_session_accumulation.py --binary "$PWD/metal_infer/infer-work-a-release" \
  --fixture "$OUT/technical-16384.bin" --count 257 --numerics 63 --gpu-wait 30 \
  --timeout 300 --max-rss-gib 16 --min-host-free-percent 15 --out "$OUT/preflight257"
python3 tools/qualify_work_a_native.py --manifest "$OUT/release-manifest.json" \
  --binary "$PWD/metal_infer/infer-work-a-release" --preflight "$OUT/preflight257/memory-observations.json" \
  --count 32768 --out "$OUT/repaired-32768"
```

Later harnesses have `--native-gate` and `--manifest` requirements. They reject unverified binaries/model metadata, incomplete endpoints or missing actual GPU routing. Their prepared status is not execution evidence. Final results and the promotion/rollback review will be appended after execution.

## Bounded execution queue

`tools/run_work_a_closure.py` waits for the running native gate, then validates all 256 endpoints and actual GPU markers before sequential literal diagnosis, paired sustained output, uninstrumented sustained timing, named-profile restart, real RST cancellation, and matched 16K/32K cold/warm performance. Defaults request three balanced process trials/path at each length. Each performance phase has a six-hour bound; the queue checks its 14-hour budget before each new stage. Incomplete cohorts remain explicit partial/NOT RUN; no automatic retry. Later native processes retain individual time/RSS/host-memory guards. Small controller logs relay actual server start/stop timestamps. Legacy profile/cancellation drivers now use the same bounded watchdogs; two cleanup/fail-closed wrapper tests and six watchdog tests PASS.

The original literal baseline retains the exact SDK request fields, including its 256-token limit, and checks the 198 native prompt IDs against the saved SDK trace before attributing any behavior. Variations remain separate. The direct native CLI bypasses both SDK and HTTP. Failure to reproduce is reported as unresolved, never as proof of an intrinsic model limitation.
