# Workstream A: mask63 release closure — 2026-11-04

IN PROGRESS. No promotion disposition yet. Production, arithmetic defaults, model files and existing profiles remain unchanged. PR #2 remains draft. Work A starts from verified remote experimental HEAD `66adf92e2ea950528917000d1b59b788e1687371`; intervening commits since `3df795af` change only documentation. Runtime repair remains `ac06b920dbb7e26b804480b36eea4dbe83b40d4e`.

## Isolation and integration

Dedicated branch: `work/release-mask63-final-qualification`; worktree `/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS`. Work A owns inference/release harnesses. Work B owns Gateway/MCP/agent validation. No Work B code is imported or edited. Integrate separate focused commits only after testing and Architect review; do not merge/cherry-pick automatically. Neither production port 11241 nor another thread's worktree is used for inference.

One heavyweight model process at a time. The completed native oracle is `infer-work-a-release`; all later harnesses require its manifest-bound numerical and actual-GPU-routing evidence. No speculative integration, state rebasing, new KV pool, template change or tolerance relaxation.

## Frozen candidate and A1 evidence

- Source tree `22260f90486cec991414db362b89d295865c9ca6`, 45 runtime source hashes.
- Candidate SHA256 `5960178f4dbc677a4b7fa660b8a9fb46773ea3dadc495f5604b400cc7f194602`.
- Manifest SHA256 `86f5ffa6bd6ce42dcc81a934fdc82040a8f1059cf14ec53ec23e575957f56fce`.
- Configuration: Qwen3.5-35B-A3B tiered Q2/Q4, 40 layers, 256 experts, K8; production N128/M4-8row gate-up bitsplit/M4-2row down, opt-in mask63, default GPU linear attention, lazy shared 32768 GPU KV window. Decode prefetch stays enabled; ownership revision `nrow-prefetch-ownership-v2`.
- Global execution version 3, layout version 2, raw storage version 1 / Zstd storage version 2. Full executable hashing remains disabled. No cache-policy change.
- Existing warm-state self-test PASS, including all 64 arithmetic identities, unaffected scalar/CPU identities, selective ownership epoch, malformed/corrupt state and partial-write preservation. This is synthetic evidence, distinct from later live restore.
- 257-token preflight PASS, 14:35:08–14:35:58 PST. State error 0, hidden `1.1920928955078125e-7`, logits `1.9073486328125e-6`; observed RSS 7,404,044,288 bytes. GPU launch readings 22/25/21 percent.
- Separate rebuild under the same executable basename has identical file-backed sections and normalized payload, but different Mach-O UUID/ad-hoc signature bytes. Normalized SHA256 `d9f44e6e8db04973efe4d03190759241cc98552e664f288f5f2391e41d485e69`. This is not whole-file binary equality and is not a cache key. The actual tested executable is never overwritten. Three model-free comparator tests PASS and prove real payload changes are not excluded.

The complete repaired-build native 32K test entered inference at **14:36:49 PST** and completed **17:33:47 PST**, exit 0. Estimated conservative process bound 13,630,038,016 bytes, host availability 55% at launch, process ceiling 18GiB plus 6GiB system reserve; actual watchdog limit 16GiB RSS, host free floor 15%, 10800-second timeout. All 256 endpoints and all ten candidate GPU layers at each required boundary PASS. These overlapping memory measures must not be added as independent unified-memory allocations.

## Gate status at engineering checkpoint

| Goal | Status | Scope |
| --- | --- | --- |
| A1 freeze / identity | PASS | Manifest, source/model metadata, isolated variants, synthetic identity and measured short preflight |
| A2 repaired native 32K | PASS | 256 exact endpoints; state max 0, hidden max 4.76837158203125e-7, logits max 5.7220458984375e-6; all ten candidate GPU layers at 8192/8193/16384/16385/24576/32768 |
| A3 intended-capacity performance | RUNNING | Matched 16K cohort began 17:58:10 PST after A2; 32K remains NOT RUN |
| A4 sustained decode / lifecycle | PASS (bounded) | Four 384-token paired responses, uninstrumented repeat, profile restart/mismatch rejection and prefill/decode RST recovery PASS |
| A5 literal-change diagnosis | COMPLETE (bounded) | Actual scalar/candidate raw IDs/state and fresh CLI agree; original wrong reply persists, latest-only/distinct/explicit override work; official template matches exactly. No general intrinsic-model claim |
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

## GPU-window identity audit — resolved without policy change

The queue was held before its first model launch to trace the apparent omission of GPU_KV_SEQ from the persistent compatibility key. Full-path inspection rules out a serving defect for current windows: infer.m bounds named/dynamic and startup warm prefixes to TOOL_PREFIX_CACHE_MAX_TOKENS=8192; warm_state_cache.inc independently rejects larger token_count headers. All supported serving GPU windows are at least 8192. A larger base-system snapshot is process-local, not a persistent warm checkpoint. Qualification-only builds deliberately relax the prefix cap and are not a serving compatibility guarantee. The initial suspected blocker was premature; no identity/source/runtime change was made. If future serving raises the persistent-prefix cap above a supported GPU window, backend/window identity must be reconsidered under the cache-correctness contract. Original interrupted controller evidence remains in sequence/; a fresh sequence-after-cache-audit/ controller waits on the SAME running native test, without rerunning a model.

## Completed repaired native 32K

All 256 observed slab endpoints PASS direct numerical comparison and exact persistent fingerprints. State max **0**, hidden **4.76837158203125e-7**, logits **5.7220458984375e-6**. Greedy identity, finite active tensors, all ten KV lengths/mirrors pass. Candidate-specific GPU markers cover all ten full-attention layers at 8192, 8193, 16384, 16385, 24576 and 32768. No intermediate whole-model batch states or reference rebasing are claimed.

Native observed RSS peak **10,279,452,672 bytes**, child high-water **10,319,511,552**, charged-footprint peak **9,407,890,040**, sampled resident maximum **10,257,645,568**. Metal allocation **5,357,207,552**, two diagnostic banks **3,076,587,520** bytes. Metrics overlap; do not sum as unified physical allocations. The 16GiB RSS/host/time guards did not fire. Host availability was 55% before launch; no minimum-over-entire-run claim is inferred from isolated samples.

## Literal-change isolation

Scalar server: 17:33:56–17:37:20; mask63 server: 17:37:23–17:39:55. Deterministic paired requests preserve native input IDs, raw sampled IDs and observed state. The original, shortened-history and thinking variants repeat the old literal. Latest-user-only, distinct BLUE and explicit override return their requested literals. The original completes after 9 tokens, below its unchanged 256-token limit. Sampling variation is kept separate from deterministic parity claims.

Fresh scalar CLI 17:40:00–17:40:19 reproduces all nine sampled IDs and the same decoded wrong reply, bypassing HTTP, SDK and resident reuse. Separate stdout/stderr avoid losing the first LM-head token or conflating progress logs with decoded content. This establishes a history-dependent native model/input-response behavior, not a mask63 or adapter regression; it does not establish a universal intrinsic-model limitation or independent full-precision-model equivalence. No compensating rewrite is introduced.

The exact text-only/no-tools/nonthinking prompt matches the [official Qwen template](https://huggingface.co/Qwen/Qwen3.5-35B-A3B/blob/59d61f3ce65a6d9863b86d2e96597125219dc754/chat_template.jinja) rendered in an existing sandboxed Jinja2 3.1.6 environment: 531 bytes, 198 native tokens, matching role/thinking-marker counts. The current reference is pinned and is not asserted to be the original quantization-export revision. Other template branches are not inferred. No template edit or package installation occurred.

## Production observation for later rollback planning

Read-only observation at 17:16: local production source HEAD **5c26430f2790b84516b7384915eb0500abc5392f**, clean tracked checkout; remote PR #2 base **8312a1d0fbf4fa09a14621a51cfe676be98c29b3**. These are distinct source baselines and neither is asserted to identify the build source of the observed executable. Default root infer SHA256 **7ae16f0a22ca9e871406bb0a9566e366432df6074027c7feeb246a239203bfbb**, shader SHA256 **7067f44056fa947f54ab7095d7461f10c30d507f11c90ca484c09ad5e15aac6b**; small read-only copies/manifest are outside Drive in production-observation/. No running-service executable mapping is asserted. Production was neither executed nor modified by this observation.

## Substantial generation and uninstrumented repeat

Paired scalar server 17:40:26–17:46:24; mask63 17:46:26–17:51:40. Each produces **1536 completion tokens across four responses**, three resident turns plus a full stateless replacement. All raw sampled IDs, visible content and observed active-state fingerprints match. End positions 444/872/1302/808; candidate observations 445/429/431/428. Each response completes 384 tokens; visible-content deltas 384/296/384/384. The thinking-budget case includes hidden/forced-handoff tokens. The replacement really enters N128 after long decode, exercising the repaired ownership transition. No intermediate within-slab whole-model state is inferred.

The uninstrumented-state-path server runs 17:51:43–17:55:03 and repeats all four responses exactly in visible content and completion count. Full-generation wall rates: **13.690 / 9.901 / 10.919 / 7.716 tok/s**, respectively. Context/content/thinking policy differ, so these are not four repetitions of one fixed-context benchmark and no combined speedup is claimed. This metric includes first LM-head and EOS/length handling; it is not an isolated steady-state kernel rate. Per-request memory trends and RSS guard are retained in sanitized results.

Model-free checks now include four native-CLI stdout/token-capture regressions and three sanitized-summary regressions. The official Jinja comparison uses the existing Conda Python/Jinja2 environment; no dependency is added to production. The vendor source remains private, with only its URL/revision/hash and comparison result published.

## Named-profile restart and cancellation

Profile capture/restart/mismatch tests ran 17:55:06–17:57:41 PST. The 67,427,311-byte checkpoint restores exact state; old resident sessions are rejected after restart. Controlled version/model-configuration header faults and a real execution-mode change reject the incompatible checkpoint and reproduce fresh state. These are isolated private profiles; profile identity remains distinct from conversation identity. Peak sampled RSS across these servers was 1,885,683,712 bytes.

Cancellation server 17:57:43–17:57:58; scalar recovery control 17:58:01–17:58:07. Real disconnects during N128 prefill and decode invalidate the session, reject stale continuation with 409 and allow exact fresh recovery. Cancellation latency 204.849 ms / 58.302 ms; subsequent health latency 0.406 / 0.420 ms. Peak server RSS 1,695,154,176 bytes. This establishes invalidation and clean reuse after reset, not immediate zeroing of discarded partial arrays. Resource guards did not fire.

Model-free invocation: `PYTHONPATH=tools python3 -m unittest test_work_a_summary test_work_a_cli_samples test_macho_rebuild test_work_a_gate test_profile_watchdog` — 17 PASS. An initial invocation omitted PYTHONPATH and failed imports before executing tests; corrected invocation passes without source changes.

## November 6 authorized resume

User pause at November4 18:03:23 PST stopped the owned queue/test server and preserved the interrupted first16K trial without promoting it to a timing row. Resume at November6 00:46:35 uses fresh performance-resume-20261106-{16384,32768}/ outputs outside Drive. First server started00:46:38. The bounded initial cohort is one complete cold/warm process trial per ordinary/mask63/scalar path at each capacity, sequentially; n=1 cannot establish run-to-run variability and is explicitly exploratory. Additional repeats depend on elapsed/resource budget. Six-hour phase and per-process memory/time guards remain; no native correctness rerun. Source/model/binary binding is rechecked.

The summary now accepts --performance-prefix performance-resume-20261106 so interrupted and resumed cohorts cannot silently mix. Four summary tests plus the existing14 model-free checks PASS (18 total). Release/rollback planning is [review-only](work-a-mask63-release-procedure-2026-11-06.md); the actual production launcher/executable provenance must be verified before approval. No deployment/production commands were executed.
