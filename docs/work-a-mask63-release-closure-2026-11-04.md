# Workstream A: mask63 release closure — 2026-11-04

Bounded closure reviewed November10. An early memory block remains historical; later continuation has a validated mask63 32K pair and scalar running. No promotion authorized. Production, arithmetic defaults, model files and existing profiles remain unchanged. PR #2 remains draft. Work A starts from verified remote experimental HEAD `66adf92e2ea950528917000d1b59b788e1687371`; intervening commits since `3df795af` change only documentation. Runtime repair remains `ac06b920dbb7e26b804480b36eea4dbe83b40d4e`.

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
| A3 intended-capacity performance | PARTIAL / BLOCKED | Complete n=1 cold/warm16K all paths and32K ordinary;32K mask63 cold request completes before driver pipe failure; Nov10 completion blocked before model launch at34% host availability |
| A4 sustained decode / lifecycle | PASS (bounded) | Four 384-token paired responses, uninstrumented repeat, profile restart/mismatch rejection and prefill/decode RST recovery PASS |
| A5 literal-change diagnosis | COMPLETE (bounded) | Actual scalar/candidate raw IDs/state and fresh CLI agree; original wrong reply persists, latest-only/distinct/explicit override work; official template matches exactly. No general intrinsic-model claim |
| A6 release engineering | PARTIAL | Payload reproducibility and unchanged production verified; review-only deployment/rollback proposal; actual service provenance must be established before approval |

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

### Saved EOS proof (no additional inference)

The first three capture/restart traces were audited explicitly: natural EOS is the final completed token and the final effective-history token; session remains reusable, all observed KV lengths/finite-state checks pass, and later turns begin at the prior end. Capture end positions170/202/234 match restored runs exactly. Restart begins at the independently logged142-token warm-prefix position, not zero. Post-processing initially assumed a cold restart and failed that assertion; correcting the audit to require the actual restored-prefix length resolves it without a product or trace change. `tools/check_work_a_eos.py` exports only positions/component digests/file hashes. The source traces remain private.

## Final bounded handback — November 10

### 1. Source and branch

Start66adf92e2ea950528917000d1b59b788e1687371 on experiment/http-resident-prefix-reuse-20261023; all Work A changes are on work/release-mask63-final-qualification. Final HEAD is the commit containing this closure. Runtime repair remains ac06b920dbb7e26b804480b36eea4dbe83b40d4e and all45 authenticated runtime files remain unchanged. No Work B code was imported.

### 2. Changes and commits

8bf3e3da freezes candidate/harness gates;20043a57 sequences guarded workloads and exact SDK baseline;1e75d5d2 preserves every CLI sample;089601d5 records repaired32K/sustained/lifecycle results;8fad8607 isolates resumed evidence and review-only release procedure. This final commit adds saved-EOS auditing, conservative performance summary, explicit missing-mode selection and model-free selection tests. Runtime product code and production defaults are unchanged.

### 3. Repaired native numerical qualification

PASS all256 endpoints128..32768, independently evolving reference/candidate, exact active persistent fingerprints and state max0; hidden max4.76837158203125e-7, logits max5.7220458984375e-6. Greedy tokens, finite active tensors, all10 KV lengths/mirrors and GDN/conv checks PASS. Actual candidate GPU routes cover all10 full-attention layers at8192/8193/16384/16385/24576/32768. Not universal whole-model bitwise equivalence or unobservable intermediate batch-state equivalence. No extra independent long history was attempted within this budget.

### 4. Measured long-context performance

All values below are **one process trial/path** with distinct cold/warm requests; no run-to-run variability is measured. Cold means first request after fresh process/startup, not cold disk/OS cache. Launch and post-process GPU gates pass for complete trials; in-run competing GPU work cannot be separated from the model's own utilization. Ordinary arithmetic is a performance control, not the qualified numerical alternative. Expert-cache configuration matches; exact cache contents/routes need not match across arithmetic modes.

| Context | Path | Cold prefill s | Warm prefill s | Warm prefill tok/s | Warm visible TTFT s | Warm generation-wall tok/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 16384 | ordinary | 1325.305 | 995.824 | 16.453 | 995.882 | 4.467 |
| 16384 | mask63 | 1174.335 | 1180.462 | 13.879 | 1180.488 | 3.950 |
| 16384 | scalar | 2123.869 | 2148.034 | 7.627 | 2148.090 | 3.987 |
| 32768 | ordinary | 3098.961 | 3145.699 | 10.417 | 3145.816 | 1.180 |
| 32768 | mask63, completed request in interrupted trial | 3580.765 | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| 32768 | scalar | BLOCKED | BLOCKED | NOT RUN | NOT RUN | NOT RUN |

All completed requests processed the full logical context with cached_prefix_tokens=0 and generated32 tokens. GPU allocation/length observers report every full-attention KV length at16416 or32800 as appropriate. At16K, warm mask63 costs18.541% versus ordinary and yields1.820x scalar prefill throughput in this single cohort. Its cold time is lower than ordinary's cold time, illustrating order/cache sensitivity; no causal speedup claim follows. These HTTP wall-time results cannot be treated as a matched continuation of the historical1K/4K CLI medians. No arithmetic optimization is justified from this evidence alone.

Complete16K sequence: November6 00:46:38–03:16:52, results finalized03:16:55. Complete32K ordinary server03:16:58–05:02:00. Mask63 server started05:02:04; its cold request finished at06:02:15 with prefill3580.765s, decode27.084s,32 tokens. Driver BrokenPipeError occurred during progress output after the completed record was saved; context cleanup stopped its server. This is a harness/console lifetime defect, not evidence of model failure. The parent status file remained stale RUNNING; a separate reconciliation record preserves that discrepancy. The interrupted request is retained separately, never upgraded to a complete cold/warm process trial.

November10 completion selected only mask63/scalar, direct stdout/stderr file logging, stdin DEVNULL and an explicit bounded4-hour process cap/6-hour phase cap. Existing3-hour process default remains unchanged. It stopped before any model launch with HOST_MEMORY_LAUNCH_BLOCKED; independently observed host availability34%, required35%. No automatic retry or threshold reduction. New GPU readings are not claimed because launch stopped before that stage.

Hardware GPU timestamp latency and HTTP per-expert cache-hit counters are **NOT MEASURED**. Existing per-request host wall-phase counters are preserved, including staging/cache/expert/combine totals; their overlapping scopes must not be summed as isolated hardware latency. They are not a replacement for missing GPU timestamp measurements. Second/third long-context repetitions are NOT RUN. The32K complete three-way warm comparison is still a release gate.

### 5. Sustained decode, EOS and resident sessions

Four384-token responses/path (1536 each) preserve scalar/candidate sampled IDs, visible output and observed state. Three resident turns and stateless N128 replacement exercise repeated decode-to-prefill ownership. Thinking on/off included. Non-observer repeats produce7.716–13.690 full-generation-wall tok/s across different short contexts, not a fixed-context repetition distribution or isolated steady-state kernel metric. Saved natural-EOS capture/restart proof passes at170/202/234; EOS is committed into effective history and subsequent turns start from the previous end.

### 6. Literal-change classification

The original wrong reply persists in scalar and mask63, and independent scalar CLI reproduces all9 sampled IDs. Exact531-byte official text/no-tools/nonthinking rendering and198-token marker counts match. Original256-token limit is not reached. Latest-only/distinct-literal/explicit-override variations succeed. This is history-dependent native model/input-response behavior in the current model; transport/template/resident mismatch is not demonstrated for this case. Independent full-precision model verification is NOT RUN. No template/post-generation rewrite hides the failure. Product instruction-following remains a separate behavioral limitation for Architect review.

### 7. Checkpoint and identity

Synthetic corruption/identity checks, all64 numerical identities, unchanged unrelated-build policy,67,427,311-byte named-profile restore, stale-session409, prefix mismatch without overwrite, header-version/model-signature rejection and actual mode-switch rebuild PASS. Prior repaired cross-build restore remains accepted within its original scope. Selective epochv2 invalidates affected old GPU-N128 checkpoints; scalar/CPU identities and global execution3/layout2/storage formats remain unchanged. Full-binary cache hashing stays disabled.

### 8. Memory and safety

| Measured complete trial | RSS watchdog high water GiB | Charged physical peak GiB | Metal allocated bytes |
| --- | ---: | ---: | ---: |
| 16384 ordinary | 8.634 | 2.561 | 5357207552 |
| 16384 mask63 | 8.783 | 1.948 | 5357207552 |
| 16384 scalar | 1.326 | 2.067 | 4845830144 |
| 32768 ordinary | 8.631 | 3.264 | 5357207552 |

Charged footprint, RSS, mapped file residency, allocation reservations and CPU/Metal aliases overlap. Do not add these columns or call them total unified-memory attribution. Diagnostic32K RSS high-water10,319,511,552 bytes and charged peak9,407,890,040 include two3,076,587,520-byte total oracle banks. Serving measurements do not allocate that oracle pair. Complete trials trip no memory/time guards. The later34% availability block is preserved as a safety success, not a model execution result.

### 9. Gate matrix

| Gate | Result |
| --- | --- |
| A1 authenticated repaired candidate/selective identity | PASS |
| A2 repaired native32K,256 endpoints/all10 GPU layers | PASS |
| A3 matched16K three paths,cold/warm | PASS for n=1 exploratory cohort |
| A3 complete32K three paths/cold+warm/repetitions | PARTIAL; remaining launch BLOCKED |
| A3 hardware-timestamp attention latency/expert hit counters | NOT RUN / NOT MEASURED |
| A4 substantial outputs,thinking,resident/replacement,EOS | PASS in bounded tested scope |
| A4 restart/mismatch/cancellation/RST/fresh recovery | PASS in bounded tested scope |
| A5 original literal requested response | FAIL behavior on scalar and candidate; bounded diagnosis COMPLETE |
| A6 build payload/provenance/cache policy | PASS in documented scope |
| A6 production launcher ownership/approved deployment | NOT ESTABLISHED / NOT AUTHORIZED |
| Installed GUI,real hardware faults,other long modes | NOT RUN |

### 10. Proposed configuration

Only the documented M4/24GiB,tieredK8,defaultGPU-linear/chaining/prefetch/N128/mask63,lazy32K envelope is a proposed candidate. One evolving resident conversation, existing5-slot/pinned/768MiB dynamic-prefix policy,8192 static-prefix cap. Do not infer64K or arbitrary concurrent-model support. Operator/client GPU-only admission should bound prompt+maximum output to32768; this report adds no server-side limit enforcement.

### 11. Remaining restrictions

Complete the missing32K comparison after host memory satisfies launch admission. n=3 and hardware latency/cache attribution remain unmeasured; no uncontended performance or production win is claimed. Retain the literal behavior failure, separate Work B client/GUI qualification, actual service provenance and architectural acceptance. No large workload is automatically retried after the memory block.

### 12. Reproduction, deployment and rollback

[Review-only release procedure](work-a-mask63-release-procedure-2026-11-06.md) contains actual Makefile build form, source-baseline distinction, supported flags, intentional checkpoint rebuild, backup and rollback preconditions. No merge/deploy/production stop or restart is executed. Observed production HEAD5c26430f2790b84516b7384915eb0500abc5392f, clean tracked checkout; installed binary/shader SHA256 still7ae16f0a22ca9e871406bb0a9566e366432df6074027c7feeb246a239203bfbb /7067f44056fa947f54ab7095d7461f10c30d507f11c90ca484c09ad5e15aac6b on November10. These hashes do not establish the installed executable's build-source identity.

After a fresh resource check and explicit resume, the exact missing-case runner command is below. A fresh output directory is mandatory; direct file output avoids the prior pipe lifetime failure. The runner itself fails closed if host availability is below35% or GPU readings fail. No need to rerun A2 or the complete ordinary32K pair.

```bash
cd '/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS'
ROOT='/Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release'
STAMP=$(date +%Y%m%d-%H%M%S)
python3 -u tools/benchmark_work_a_long.py \
  --control "$PWD/metal_infer/infer-work-a-control" \
  --candidate "$PWD/metal_infer/infer-work-a-performance" \
  --variants "$ROOT/build-variants.json" \
  --render-input "$ROOT/long-32768-input.json" \
  --render-output "$ROOT/long-32768-render.json" \
  --probe "$ROOT/physical-probe" --count 32768 --repeats 1 \
  --modes mask63,scalar --max-process-seconds 14400 --max-seconds 21600 \
  --manifest "$ROOT/release-manifest.json" \
  --native-gate "$ROOT/repaired-32768/result.json" \
  --out "$ROOT/performance-missing-$STAMP" \
  > "/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/benchmark-logs/work-a-missing-$STAMP.log" 2>&1 < /dev/null
```

### 13. Evidence and disposition

[Draft Work A PR #3](https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/3); [PR #2 remains draft](https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/2). [Sanitized evidence](results/work-a-mask63-release-closure-2026-11-04.json). Private tokens/checkpoints/log records stay in /Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release; small controller logs stay in root benchmark-logs. Original Drive fixtures and failed/interrupted results are retained. All owned test processes/listeners are stopped. Final model-free checks21/21 PASS; EOS audit PASS.

**NO-GO — BLOCKERS REMAIN**

## Architect continuation — admitted November 10, 11:19 PST

Starting HEAD9759b0265b64b51320ffb07166ff00d2f9ee483a. No tracked edits at admission; all45 frozen runtime files, binaries/model/fixtures and completed native proof revalidated. Host availability47%; mask63 launch GPU readings6/19/15%. Actual server start11:19:31.255 PST. Only missing32K mask63/scalar cold/warm pairs are running, repeats1; ordinary32K and native correctness are not repeated. No measurement from this attempt is accepted before complete pair/lifecycle/resource checks.

Private output: `/Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release/performance-missing-20261110-111928`; durable log: root `benchmark-logs/work-a-missing-20261110-111928.log`. Driver launch/command/PID are preserved in private `latest-missing-case-launch.json` and its timestamped copy. Existing4-hour native/6-hour phase bounds,16GiB RSS watchdog, host floor and35% admission, three low GPU readings and one model remain unchanged. The prior34% block and interrupted cold request remain separate historical evidence.

The user reports19% remaining five-hour quota. Priority is the n=1 missing cohort; no extra repetitions are scheduled. File-based logs and bounded native cleanup do not depend on the chat pipe. New post-processing validates complete cold/warm output, logical context/cached count, usage, binary/input signatures, finite timings, all10 backend-boundary layers, allocation lengths, launch/post GPU, host admission and actual server start/stop markers.28 model-free checks PASS. It accepts only n=1 exploratory evidence and labels reuse of the November6 control against a later cohort; cache/host conditions are not identical. No hardware latency or per-expert-hit data is invented.

After successful completion, the exact read-only validation/aggregation commands are:

```bash
cd '/Users/knagel/.codex/worktrees/release-mask63-final-qualification/Flash-iOS'
ROOT='/Users/knagel/Flash-iOS-Work-A/2026-11-04-mask63-release'
OUT="$ROOT/performance-missing-20261110-111928"
LOG='/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS/benchmark-logs/work-a-missing-20261110-111928.log'
python3 tools/validate_work_a_missing.py --root "$ROOT" --completion "$OUT" \
  --driver-log "$LOG" --out "$OUT/validated-completion.json"
python3 tools/summarize_work_a_performance.py --root "$ROOT" --completion "$OUT" \
  --validation "$OUT/validated-completion.json" --out "$OUT/performance-closure.json"
```

An incomplete/blocked run cannot generate an accepted completion proof. Before publishing final evidence, inspect result/lifecycle/log timestamps and rerun frozen bindings; do not equate background launch or supervisor exit with a completed inference test. Whole-release promotion requirements remain separate. Runtime/arithmetic/checkpoint identity/production remain untouched.

A bounded read-only completion supervisor is running alongside the driver. Its state/logs are in this attempt's private directory: `completion-supervisor-result.json`, `completion-supervisor.log`, `validated-completion.json` and, only after valid completion, `performance-closure.json`. It performs no model launches, retries, Git writes or deployment. If the parent chat quota ends, inspect these files before doing anything; do not start a duplicate model. A final GitHub result update remains pending actual evidence. The committed RUNNING checkpoint is not a completed-performance assertion.

### Live matched-prefix anomaly and reserve enforcement

At the same16384-token prefix of the same32768-token request, the prior interrupted32K mask63 attempt records1152.414s elapsed; the new attempt records2194.556s. Each window contains128 completed N128 profile records, using the same frozen binary/fixture. Linear expert staging host counter rises49.686s→747.928s; linear grouped176.741s→923.706s; full grouped60.234s→328.571s. Full rowwise attention52.197s→54.656s, QKV22.926s→24.965s, linear batch109.191s→114.904s and linear post50.990s→51.872s change much less. These are overlapping host-wall scopes, not GPU hardware times; no sum or causal percentage is asserted. This supports memory/cache/I/O staging conditions as the main observed anomaly, not a demonstrated arithmetic regression. Current full-request timing is still incomplete. Prefix-log hashes and exact phase sums are preserved privately in `matched-prefix-staging-anomaly.json`.

Read-only observation11:56 PST: memory availability31%, WindowServer24.6% CPU, wallpaper extension7.3% CPU, no reported thermal warning. CPU percentages do not prove per-process GPU attribution; GPU utilization includes the benchmark itself. No unrelated app is closed or changed.

An additional bounded six-GiB reserve guard began11:58:10 PST. It estimates available bytes from the existing host-availability percentage and physical memory, stops only verified native child process groups of this exact driver after three below-reserve readings, and fails closed on an unavailable reserve monitor. Existing35% launch admission,16GiB RSS,15% floor, process/phase bounds remain unchanged. Its source, launch and state/log files are private in this attempt directory (`reserve-guard.py`, `reserve-guard-result.json`); it is additional supervision, not an inference/runtime modification.

### Validated mask63 32K process trial — November 10, 14:10 PST

The complete same-process pair is accepted as one exploratory trial, separate from the November6 interrupted cold observation. Cold prefill5128.867s, warm5084.331s; both consume32768 logical and physically prefetched prompt tokens, cached0,32 generated,32800 total. Warm visible TTFT5084.491s and generation-wall0.853 tok/s. Both resident allocation observations show all10 KV lengths32800 and Metal allocated5,357,207,552 bytes. Actual routing covers all10 GPU layers at32768 and CPU at32769; this does not extend native numerical qualification beyond the GPU window.

Server started11:19:31.255, cold finished12:45:32.040, warm finished14:10:53.980 and server stopped14:10:54.104 PST with expected SIGTERM(-15). No watchdog fired. RSS watchdog peak7,291,469,824 bytes, charged lifetime peak3,524,718,904 bytes, launch host47%, GPU6/19/15% and post14/12/14%. Metrics overlap; not total unified memory. Lifecycle/provenance/usage/routes validated independently with the same row checks used for the full cohort.28 model-free tests PASS.

Warm mask63 is about61.6% more time than the retained November6 ordinary warm observation; comparison is cross-date and confounded by staging/cache conditions, not a causal arithmetic overhead estimate. The new cold result is43.2% slower than its own earlier interrupted-request observation with the same binary. Read-only app preferences show Memory Cleaner5.1 AutoCleaning=true; plausible cache-eviction confound, causation unproven, no setting or app changed. No production change or runtime repair is justified by this result.

Scalar admitted sequentially after mask63 stopped, with GPU0/12/13%; actual start14:10:58.761 PST. Scalar cold/warm and complete cohort disposition remain pending. No repeats or duplicate server are launched. The bounded post-processing and reserve supervision remain active.
