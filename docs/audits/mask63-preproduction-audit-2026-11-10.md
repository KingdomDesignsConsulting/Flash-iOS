# Flash-iOS — Independent Mask63 Pre-Production Audit

**Audit started/completed:** 2026-11-10 (America/Los_Angeles)  
**Workstream:** C — runtime, integration, safety, release readiness  
**Disposition:** **AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**  
**Scope:** Proposed experimental release only. No installed production service, port, process, binary, cache, launcher, or model was inspected, contacted, restarted, altered, or deployed.

## 1. Executive summary

The frozen experimental mask63 inference candidate provides strong **reported and internally consistent** 32K numerical evidence after the N128 async-prefetch ownership repair. Independent source inspection finds no confirmed P0 defect. The original six-omitted-experts failure at position 129 has a concrete producer/consumer explanation and a narrow repair: drain prior async reads at admitted request boundaries, clear decode-prefetch state, and forbid speculative prefetch during capture-only N128 stages. Candidate-specific GPU attention routing and the numerical verifier are not generic PASS text.

The candidate is **not yet ready for final production authorization**. Outstanding P1 prerequisites concern server-side enforcement of the proposed 32K GPU-only context/resource policy, intended-capacity performance suitability, actual installed-production provenance and rollback ownership, and the explicit client feature boundary. The native HTTP reasoning controls silently ignore several common options; Work B has not been integrated or qualified against the frozen candidate in an installed GUI/Gateway environment. The 32K warm mask63 prefill is about 61.628% slower than ordinary N128 in exploratory one-process measurements; ordinary N128 is **not** numerically qualified and is only a timing control.

No additional long model run was performed. Sanitized artifacts were rechecked; the original frozen executable and private raw trace/fixture files were unavailable for independent bytewise authentication here. This limitation must remain visible in release authorization.

## 2. Audited identity and excluded production scope

- Repository: https://github.com/KingdomDesignsConsulting/Flash-iOS
- Work A candidate: **work/release-mask63-final-qualification**, exact HEAD **21a073174fb1feb828f2d28762293d1803e66a9a** (verified unchanged during audit).
- Work B candidate: **work/agent-mcp-protocol-reliability**, exact HEAD **01ae9976f541c384dd83905fc006da196971bdb2** (verified unchanged).
- Frozen runtime lineage: **66adf92e2ea950528917000d1b59b788e1687371**; repair commit **ac06b920dbb7e26b804480b36eea4dbe83b40d4e**. The ten later Work A commits modified documentation, qualification harnesses, and results, not normal runtime files.
- Reference checkout commit: **5c26430f2790b84516b7384915eb0500abc5392f**; comparison shows 23 commits/changed experimental contents, but this source checkout is **not** verified to be the installed executable.
- GitHub production branch last verified **8312a1d0fbf4fa09a14621a51cfe676be98c29b3**. Do not equate remote branch source, the observed checkout, and the live service.
- Draft PR #2: https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/2 — open/draft, broad resident-session experimental lineage.
- Draft PR #3: https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/3 — open/draft, Work A closure.
- Independent audit branch: **audit/mask63-preproduction-readiness-20261110**, based exactly on Work A candidate SHA before adding audit artifacts. Neither Work A nor Work B was merged.

Work A evidence binds to a **reported** candidate executable SHA-256 **5960178f4dbc677a4b7fa660b8a9fb46773ea3dadc495f5604b400cc7f194602**, release manifest SHA-256 **86f5ffa6bd6ce42dcc81a934fdc82040a8f1059cf14ec53ec23e575957f56fce**, and source tree **22260f90486cec991414db362b89d295865c9ca6**. The complete original executable and private input artifacts were not available for independent rehash in this review.

## 3. Source and numerical correctness

**Inspected paths:** metal_infer/infer.m (GPU/CPU attention gates, command waits, HTTP/session preflight, prefetch); prefill_nrow_grouped_async.inc (N128 capture, gated expert stages, mask bits); fe027_attention_reference.inc; fe027_combine_reference.inc; fe027_q4.inc; session_nrow_oracle.inc; warm_state_cache.inc; tools/work_a_manifest.py; Work A source/report history.

**Opt-in only:** metal_infer/Makefile release-qualification uses FLASH_FE027_NUMERICS, FLASH_SESSION_STATE_DIAGNOSTICS and FLASH_EXPERIMENTAL_LAZY_SHARED_GPU_KV_32K. Production infer is not overwritten by that target. A release build with RELEASE_QUAL_EXTRA_CFLAGS=-UFLASH_SESSION_STATE_DIAGNOSTICS still retains the opt-in FE027 and 32K compilation. The environment value FLASH_FE027_NUMERICS=63 selects all approved FE027 numerical bits; absence/zero preserves accepted default behavior.

**Arithmetic:** FE027 mask bit 16 reuses explicit scalar-compatible Q/K preparation and per-row causal attention order; bit 32 reuses the unchanged scalar Metal MoE combine and slot order. Source checks success status after the prepare, attention and combine command buffers. The older 1920/2304/3456 state failures are valid evidence for prior ordinary or partial-alignment paths; do not mark them erased, merely superseded for the mask63 candidate within the tested configuration. The test oracle does not rebase a failed candidate from a scalar anchor.

**llama.cpp PR #31688 (merged 2026-11-05):** upstream issue is graph-node-count-dependent changes to automatic Metal command-buffer split boundaries that inhibit fusion and amplify small rounding changes through top-K. Flash explicitly constructs command buffers/encoders rather than splitting a ggml graph by its node count. The *same* upstream mechanism is not established in Flash source. Flash has demonstrated its *own* CPU/GPU sigmoid/combine reassociation sensitivities; retain exact scalar/mask63 regression gates, and treat any future encoder partition refactor as state-affecting until tested. Do not port llama.cpp's fix without an analogous failing Flash mechanism.

## 4. Async prefetch, memory ownership and allocation safety

The pre-repair failure is independently understandable from current source: infer.m:21220–21225 waits for any active async pread **before** restoring state and resets g_pred_generating and g_expert_prefetch_generating. infer.m:13248–13258 explicitly excludes g_prefill_nrow_capture from decode-prefetch launch. The async read completion consumes a generation and checks per-expert chunk lengths/valid flags (infer.m:10523–10633); any selected incomplete read triggers a checked inference error rather than a valid expert. The original failure captured only two of eight routed experts and could not be waived as floating-point tolerance.

The candidate's Metal command-buffer wait helper checks nil buffers, completion status and error details (infer.m:12829–12845). Deferred CMD3 reads complete before CPU combination or state snapshot. The lazy shared-KV backing uses separate page-aligned K/V mappings with Metal no-copy view deallocators. Cache free drops only the matching current view; queued Metal work can retain an older view. 32K attention is admitted through 32768, then scalar CPU fallback is used. N128 checks full-attention cache lengths against both CPU and GPU ranges before a complete slab. These are source-supported mitigations, not proof under every hardware fault or concurrent execution mode.

Unproven possibilities: cancellation between every asynchronous read/capture edge, forced allocation failures beyond existing synthetic cases, derived expert views under every cache eviction/race, and sustained system-level pressure on the 24GiB host. No source-confirmed UAF/double free was identified in the inspected normal supported path. Real OOM was intentionally not attempted.

## 5. Checkpoint identity and restore safety

warm_state_cache.inc:108–166 hashes selective FE027 operator identities, the present runtime/config shape, mode flags and the opt-in `nrow-prefetch-ownership-v2` marker for eligible tiered GPU N128. Global execution version is 3, layout 2, storage raw 1 / zstd 2. The source/hash contract leaves whole-executable hashing disabled, intentionally preserving compatibility across unrelated builds. Default mask 0 retains its identity; the affected prefetch-ownership class must rebuild once. The source also hashes relevant model/stat identities, manifest/vocab/shader bytes/paths, mapped expert overlay metadata, and exact rendered-prefix token signature.

**Future-change guard:** the mode hash records g_kv_seq_len but not the compile-time GPU_KV_SEQ. Present persisted tool prefixes are limited to 8192 tokens (infer.m:8614 and cache/source preflight), while supported GPU capacities are >=8192; the current prefix cannot cross the backend decision point due only to the GPU cap. Therefore no unsafe current checkpoint acceptance is established. If the prefix limit rises, GPU capacity falls, or an alternative attention backend is enabled, add an explicit identity discriminator or demonstrate equivalence. This is not grounds for automatic whole-binary hashing.

Snapshot restore fences deferred GPU work and validates complete KV/recurrent members before mutation. Existing tests report corrupt/foreign checkpoint refusal, partial-write preservation, cross-build same-compatible identity and exact replay; independent on-host validation was not run in this audit. A profile checkpoint is a static prefix, **not** a durable full conversation.

## 6. Numerical evidence verification

**Independently executed model-free static check on sanitized JSON:** docs/results/work-a-mask63-release-closure-2026-11-04.json contains 256 distinct, ordered endpoints `[128,256,...,32768]`, all passed. Each reported row has exact active-state fingerprints, finite values, complete KV lengths/mirrors, equal greedy tokens (serialized as integer 1), state error <0.001, hidden error <=0.001 and logit error <=0.01. Recomputed maxima: state **0**, hidden **4.76837158203125e-7**, logits **5.7220458984375e-6**. The sanitizer's manifest and binary identifiers match the top-level identifiers. Strict-verification output contains ten candidate GPU-attention layers [3,7,11,15,19,23,27,31,35,39] for each of 8192, 8193, 16384, 16385, 24576 and 32768.

**Method inspected:** tools/work_a_manifest.py:verify_native_gate enforces strict endpoint ordering, error limits, nonempty matching reference/candidate digests and ten-layer GPU markers parsed from the native engine log. session_nrow_oracle.inc:sn_oracle maintains independent scalar and candidate snapshots and compares after completed slabs; it does not claim intermediate intra-slab identity. The original verification also authenticates model file metadata and hashes in tools/work_a_manifest.py:verify_bound_build.

**Evidence limit:** recomputation here validates the **published sanitized output** and source verifier logic. The private raw nrow-oracle.json, engine log, model fixtures, manifest bytes and executable were not independently opened or rehashed. Thus an independent original-run replay/source-hash certification is **NOT RUN**. Reported equality of active persistent state does not imply bitwise equality of every intermediate tensor, hidden vector or logit.

## 7. Performance evidence and expert-staging anomaly

Published 16K prefill seconds (cold/warm): ordinary N128 1325.305/995.824; mask63 1174.335/1180.462; scalar 2123.869/2148.034. At 16K mask63 warm is **18.541% slower than ordinary** and about **1.820x scalar throughput**.

Published 32K prefill seconds (cold/warm): ordinary 3098.961/3145.699; mask63 5128.867/5084.331; scalar 6741.074/**INCOMPLETE warm**. Mask63 warm is **61.628% slower than ordinary** (not a comparison to a numerically approved production mode). The interrupted scalar run's completed cold request cannot be counted as a complete two-request process trial. The fresh scalar-only follow-up did not launch because GPU idle admission readings failed the gate. These are n=1, cross-date, variable page-cache/host/GPU conditions; no causal mask63 kernel-speed claim can be made.

At the same 16,384-token prefix, observed linear expert staging expanded from 49.686 s to 747.928 s whereas rowwise attention changed from 52.197 s to 54.656 s. This supports an observed staging bottleneck difference, **not a proven cause**. Model page residency, external SSD I/O, filesystem cache, memory pressure, competing CPU/GPU activity and Memory Cleaner automatic cleaning remain confounds. Do not modify unrelated processes or preferences to validate a hypothesis.

**Recommendation:** missing scalar warm is an important completeness gap, but not intrinsically a hard mathematical correctness failure. A future explicitly authorized, restricted canary could be considered without that comparison **only if** the Architect approves a bounded latency/throughput envelope and independent state/cancellation/resource gates and records the missing scalar baseline as an unclosed performance uncertainty. This audit neither authorizes such a canary nor treats partial data as a completed matched trial. An ordinary N128 alternative cannot be promoted based only on better timing while its numerical gate fails.

## 8. Work B agent/LM Studio compatibility

Work B branch has 14 candidate-only files relative to the Work A HEAD with merge base 66adf92e2; it changes LM Studio adapter generator/transport, tests, dependency lock and reports, **not** the shared native infer.m. This reduces direct source conflict but is not an integrated-build test. Work B reports 44/44 adapter tests PASS, native tool/API self-tests PASS and 53 source-extracted thinking-control cases characterized. Its actual LM Studio service was unreachable during the current qualification, GUI NOT RUN, Gateway absent; MCP wire fixture tests are not real registration or pagination tests.

**Inspected adapter:** transport.ts parses bounded raw UTF-8 SSE and requires terminal finish + DONE, rejects HTTP/SSE invalidation, malformed JSON, extra choices/finish, timeout/EOF and inconsistent usage. generator.ts collects tool fragments by index and validates every complete argument JSON object and advertised schema before making **any** SDK tool callback; duplicate IDs and names reject. It preserves reasoning_content separately from content and forwards complete document/history. resident.ts restricts replay to verified scope/identity and only retries explicit pre-output invalidation once. The shipped SDK entry deliberately passes no stable scope and therefore uses stateless full-history replay. These are source-backed properties; no actual external tool execution was performed.

**Native compatibility gaps:** infer.m:20470–20489 implements thinking_token_budget and reasoning_budget_tokens precedence and reasoning_effort='off', but silently ignores enable_thinking and effort none/low/medium/high. A numeric zero means unlimited, **not disabled**. The SDK plugin does not expose an independently verified thinking setting. Native tool generation currently treats nonwhitespace answer text after the first tool envelope as malformed/recovery; this is not automatic support for answer→tool→answer. The native server implements Chat Completions, not Responses API. The actual MCP Gateway registry and pagination are external; fixtures do not establish its behavior. GUI attachment/Stop/reconnect semantics are not established by the current Work B qualification and should not be called production ready.

**Integration decision:** safe candidate for an **isolated integration trial**, no merge recommendation yet. Use focused Work B commits on a new integration branch, perform build/test against exact Work A frozen source and an isolated nonproduction endpoint, verify reasoning settings, tool schemas/cancellation and GUI/Gateway acceptance before adding those features to release claims. Never turn on SDK resident reuse without a real stable conversation identity.

## 9. Context and memory/resource admission

The native runtime enforces **CPU** KV admission using g_kv_seq_len=65536 and a preflight sum current+prefill+requested output (infer.m:454–477; HTTP preflight near 21202). The compiled lazy GPU attention limit is **32768**, not the HTTP admission limit. A prompt plus output in the interval (32768,65536] can be accepted and runs full-attention CPU fallback beyond 32768; that is outside the proposed GPU-only release guarantee and its performance tests.

A 35% host-availability floor, three GPU utilization samples <30%, 6GiB reserve, 16GiB RSS watchdog and 15% remaining-host floor exist in **Work A controllers/procedure**, not as generally enforced resident HTTP admission. This distinction is a confirmed P1 release control gap. To support a GPU-only release, a configurable native/launcher/API 32768 **logical prompt+max output** gate and clear overload/backpressure policy must be specified and tested without breaking the deliberately available CPU fallback mode. Document what is guard-railed externally and validate it against the actual service launch environment; do not claim that a benchmark guard is a production invariant.

The 8192 tool-prefix cap and 768MiB dynamic-prefix budget are native constants; they are not conversation-wide 32K memory admission. Physical footprint, RSS, Metal current allocations and aliasing no-copy buffers overlap; never add them as disjoint unified-memory charges.

## 10. Release procedure and rollback

The November 6 document specifies isolated build options, environment flag, canary-only port 11243, static profile namespace, selective checkpoint invalidation, backup requirements, fail-closed restoration and a prospective production maintenance sequence. It correctly avoids fabricating a launchctl service label/PID or stopping an unknown process.

Missing approval-time facts: actual installed process ownership and executable mapping; true launcher/launch environment and command-line args; actual source/shader/binary dependency provenance; captured and verified full cache/profile/weights/config backup; exact operator-controlled pause/resume and rollback commands; safe free-space/resource policy; intended-capacity latency bounds. Neither the old binary hash nor the local checkout commit substitutes for these. **No production inventory/probe was performed**; an operator must perform it later under distinct authorization. Rollback must restore cache/state **with the old binary and exact prior config while stopped**, not merely replace the executable.

## 11–12. Ranked findings and owners

| ID | Severity | Status | Finding / release impact | Minimal action | Owner |
| --- | --- | --- | --- | --- | --- |
| C-01 | **P1** | Confirmed | Native 65536 context admission and GPU 32768 capacity do not enforce proposed GPU-only release envelope; benchmark-only resource guards are not service guards | Configurable 32768 policy and actual launch-time memory/overload enforcement; regression at 32768/32769 | Work A + Architect |
| C-02 | **P1** | Evidence gap | Intended-capacity suitability unproven: complete 32K scalar warm missing; mask63 32K warm cost +61.628% vs ordinary unqualified N128 | Accept explicit latency SLO with safe conditional review, or finish matched bounded scalar/eligible performance when resources allow | Architect + Work A |
| C-03 | **P1** | Confirmed prerequisite | Actual installed binary/launcher/process/cache provenance and complete rollback steps are unverified | Future authorized operator inventory, hashes, verified backup and stop/restore checklist | Architect / operator |
| C-04 | **P1 if supported; P2 if excluded** | Confirmed | Native silently ignores enable_thinking and effort none/low/medium/high; Work B integration cannot claim those controls | Reject unsupported values clearly or normalize after approved precedence contract; same-token/prefix tests | Work B + Work A + Architect |
| C-05 | **P1 if supported; P2 if excluded** | Not qualified | Actual LM Studio GUI and MCP Gateway discovery/pagination/registry are not tested; Responses API absent | Exclude from release envelope or qualify on actual external system with permission | Work B + Gateway owner |
| C-06 | **P2** | Evidence limit | Auditor checked 256 sanitized records and verifier, not private original frozen executable/raw logs; cannot independently authenticate originating bits | At approval, independent read-only digest/check of original manifest, binary, logs and fixtures | Work A + independent reviewer |
| C-07 | **P2** | Existing limitation | Native tool envelope cannot safely expose arbitrary answer text after first tool call | Document unsupported output ordering or add independently qualified handling | Work A / Work B |
| C-08 | **P2 future guard** | Confirmed current-safe | GPU_KV_SEQ not selectively hashed, but native persisted prefix <=8192 and GPU window >=8192 in current envelope | Reevaluate if prefix cap, GPU limit, or backend semantics change | Architect |
| C-09 | **P3** | Measurement question | Staging regression cause is undetermined; no stable kernel attribution | Targeted low-impact native I/O/cache/memory observers after release gates | Future engineering |

**No P0 finding is confirmed.** The six-omitted-expert defect was historical and is repaired in the nominated candidate; do not count it as a still-open candidate defect. A P1 prerequisite is not automatically a demonstrated arithmetic error.

## 13. Remaining tests / evidence gaps

- Bounded 32768/32769 GPU-only admission and CPU-fallback opt-out behavior, including simultaneous output reserve.
- Exact original executable/manifest/raw trace rehash; currently sanitized evidence only.
- Optional matched scalar 32K warm trial under the same process guard, if a release decision still requires its latency comparison; **NOT RUN** here.
- Long non-CLI decode, peak memory pressure and controlled cancellation at more N128/async ownership boundaries; **NOT RUN**.
- Work B installed GUI integration (documents, reasoning modes, abort/reconnect), real MCP Gateway registry/pagination with immutable endpoint/schema IDs; **NOT RUN**.
- Actual service source/binary provenance and verified reversible rollback: **future authorized operator step only**, not a test in this audit.

No heavyweight model was launched. No intentional OOM was attempted. No production port, process, cache or service was touched.

## 14. Supported versus unsupported configurations

**Numerically evidenced candidate (reported):** Apple base M4, 24GiB unified memory, macOS26.7.1, Qwen3.5-35B-A3B tiered Q2/Q4, 40 layers, 256 experts, K8, N128/M4-8row Q4/Q2 gate-up, M4-2row down, mask63 explicitly enabled, GPU linear recurrence, default resident-MoE/chain/oproj/tiny/prefetch, lazy shared GPU KV through 32768; single heavyweight model process and one evolving resident session; profile/cache/rollback limited to qualified settings.

**Not established:** default promotion, numeric parity of ordinary N128 at long positions, 64K fast GPU attention, iOS/other Apple models, concurrent model processes, all mode cross-products, arbitrary Qwen weights/overlays, actual LM Studio GUI tool lifecycle, real external Gateway/MCP registry, Responses API, unknown process-manager deployment, hardware-OOM safety, and guaranteed throughput under contention.

## 15. Final recommendation

**AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**

The experimental candidate is suitable for continued isolated qualification and later explicit release-authorization review once the P1 prerequisites are bounded. **Do not merge PR #2 or #3, change the installed production runtime, or authorize a deployment on this audit alone.** A restricted canary could be a separate future approval option only after required source/provenance/admission safeguards and explicit supported-feature/latency policy are settled; this report does not authorize it.

## 16. Sources and publication

- Work A source and reports: https://github.com/KingdomDesignsConsulting/Flash-iOS/tree/21a073174fb1feb828f2d28762293d1803e66a9a
- Work B source and reports: https://github.com/KingdomDesignsConsulting/Flash-iOS/tree/01ae9976f541c384dd83905fc006da196971bdb2
- Work A source verification: https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/tools/work_a_manifest.py
- Native oracle: https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/metal_infer/session_nrow_oracle.inc
- Sanitized qualification: https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/docs/results/work-a-mask63-release-closure-2026-11-04.json
- Work B contract: https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/01ae9976f541c384dd83905fc006da196971bdb2/docs/agent-protocol-contract-2026-11-04.md
- Review-only release procedure: https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/docs/work-a-mask63-release-procedure-2026-11-06.md
- Upstream comparison: https://github.com/ggml-org/llama.cpp/pull/31688
- Companion machine-readable findings and release matrix: docs/audits/mask63-audit-findings-2026-11-10.json and docs/audits/mask63-release-gate-matrix-2026-11-10.md

**Ledger policy:** FUTURE_ENGINEERING_LEDGER.md left unchanged; findings above are a scoped proposed delta for Architect triage. Audit content only; no fixes to product source.
