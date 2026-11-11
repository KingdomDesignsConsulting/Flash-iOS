# Workstream C — mask63 independent pre-production audit

Audit start label: November 10, 2026. Inspection, bounded tests and completion: **November 11, 2026**, America/Los_Angeles. This is advice to the Lead Architect, not deployment authorization.

## 1. Executive summary

**Conditional pass.** No confirmed P0 correctness/safety failure was found in the pinned candidate's qualified configuration. The six-missing-expert repair is present, the repaired native32K evidence is authenticated, and model-free tool/API/checkpoint tests pass. Five P1 release prerequisites remain: enforce the qualified capacity/resource envelope; establish deployment and rollback provenance; resolve the prospective adapter's total deadline; qualify or exclude actual client/Gateway claims; and explicitly disposition incomplete/confounded performance acceptance. Two P2 hardening findings concern optimized Python gates and checkpoint directory durability.

The source audit and independent artifact recomputation support the measured mask63 result; they do not certify every input, arithmetic mode, intermediate tensor, allocation failure or concurrent workload. No model was loaded, no heavyweight benchmark ran, and no installed production service, process, port, cache, launcher or configuration was inspected or changed.

This audit uses an independent worktree and fresh checks. The chat's earlier Work A participation is disclosed; this is not represented as a second human reviewer. Mandatory reports are inputs to audit, not substitutes for the source and raw-evidence checks below.

## 2. Audited candidate identity and excluded production scope

| Object | Pinned/observed Git identity |
|---|---|
| Work A release candidate | `21a073174fb1feb828f2d28762293d1803e66a9a` |
| Candidate branch / draft | `work/release-mask63-final-qualification`, [PR3](https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/3) |
| Runtime lineage | `66adf92e2ea950528917000d1b59b788e1687371` |
| Ownership repair | `ac06b920dbb7e26b804480b36eea4dbe83b40d4e` |
| Work B, separately audited | `01ae9976f541c384dd83905fc006da196971bdb2`, `work/agent-mcp-protocol-reliability` |
| PR2 | Draft, [experimental resident-prefix lineage](https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/2), head66adf92 / base8312a1d |
| Historical production-source comparison | `5c26430f2790b84516b7384915eb0500abc5392f` |
| Remote production Git branch comparison | `8312a1d0fbf4fa09a14621a51cfe676be98c29b3` |
| Audit branch / worktree | `audit/mask63-preproduction-readiness-20261110`, `/private/tmp/flash-ios-audit-mask63-20261110` |

GitHub heads were checked before inspection and again before publication; both nominated engineering revisions remained current. No newer revision was silently substituted. GitHub PR metadata/comments are saved in [github-review.json](evidence/github-review.json). PR3 has no returned discussion; PR2's returned discussion preserves historical failures, repairs and dated GUI observations. Neither draft was changed or merged.

All 12 mandatory documents are versioned in [document-versions.json](evidence/document-versions.json), including SHA256 and exact commit. Work B documents are read from B's commit, where they actually exist, not presumed present on A. Older reports retain their historical failures; later evidence supersedes only their specifically repeated gates. The shared ledger was not edited.

Publication encountered an existing November10 audit at `e5aa43e`, based on the same pinned engineering revisions. That report and its findings are preserved verbatim in [history/2026-11-10](history/2026-11-10/). Its private-evidence access limitation is now resolved by actual artifact rehash and raw numerical/staging checks. November11 findings use a distinct **C11-xx** namespace: original C-01→C11-01, C-02→C11-05, C-03→C11-02; original thinking/integration/tool-order C-04/C-05/C-07 are addressed in C11-04 and the supported-contract sections. Original C-06 (raw authentication gap) is resolved; C-08 remains a future-change guard; C-09 retains unproven causal hypotheses despite independently verified phase totals. New C11-03/C11-06/C11-07 add deadline/assertion/durability findings. Original IDs are not reassigned. Prior reports remain historical, not current raw-evidence limitations.

Against historical source5c26430, the candidate changes13 `metal_infer` files (+909/-40). Against remote PR2 base8312a1d, it changes18 runtime/client files and includes earlier transport/session work. The comparisons are not interchangeable minimal patches. Work A's ten commits after66adf92 add harnesses/evidence/docs; the 45 runtime inputs remain identical to the frozen manifest. Work B's delta from the common experimental ancestor affects the adapter/tests/docs/tools, not native inference. No branches were combined.

The installed executable's build provenance cannot be inferred from any of these Git references. Previously recorded production binary/shader hashes were considered only as historical documentation. Current production was expressly outside this audit.

## 3. Source and numerical correctness findings

Reviewed the candidate runtime diff and its dependencies: N128 grouped routing/staging, FE027 normalization/Q4/reference attention/combine, scalar fused-forward sequencing, snapshot/capacity paths and selective identity. Key references at the candidate pin:

- [`infer.m:13252`](https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/metal_infer/infer.m#L13252): capture-prefetch exclusion.
- [`prefill_nrow_grouped_async.inc:814`](https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/metal_infer/prefill_nrow_grouped_async.inc#L814): bit16 selects reference attention.
- Same file2068–2098: bit32 combine eligibility preserves scalar final-layer CPU combine and expert-slot order.
- `fe027_alignment.inc`: explicit scalar GPU RMS/SwiGLU pipelines, completed before CPU access.
- `fe027_attention_reference.inc`: bounds checked against CPU and GPU extents; scalar preparation and attention pipelines; explicit command completion/status checks; correct tiny-context CPU branch.
- `fe027_combine_reference.inc`: eight ordered routed contributions with the unchanged scalar GPU combine pipeline and private/dead scratch reuse.

Mask63 changes numerical implementation to match the scalar reference; it does not alter the MoE top-K/tie policy, rebase state or relax tolerances. Ordinary N128 remains a historical **numerically failing** performance control, not an acceptable production alternative. The environment default remains mask0; enabling mask63 is an explicit release configuration requirement, not a new default.

### Upstream command-buffer fusion question

Reviewed primary [llama.cpp PR31688](https://github.com/ggml-org/llama.cpp/pull/31688), merged November5 (`44f91a02b2dfea240610851cdc2fd691e8e8205c`; reviewed head473528f). Its graph partition could split a fusible group at a node-count-derived command-buffer boundary, selecting unfused arithmetic and changing rounding/top-K. Its repair advances boundaries using `ggml_metal_fusion_max`.

No analogous graph-node partition/fusion scheduler was found in the inspected Flash scalar/N128 paths. Flash explicitly encodes selected Metal pipelines. Scalar CMD1/2/3 and N128 row commands do have mode-dependent CPU/GPU/combined routes; those can change arithmetic, as FE027 itself demonstrated, and are not assumed equivalent across modes. `infer.m:13408–13423` selects full chaining only when the entire GPU route is known and within capacity. Reference attention explicitly commits/waits before shared CPU reads. Thus upstream's specific mechanism is **not established as a Flash defect**. This is a scoped source conclusion, not proof that arbitrary future dispatch layouts preserve bitwise results. No upstream implementation was imported.

## 4. Async prefetch and memory safety

The reported defect is addressed by two necessary source changes, not merely by a new test:

1. `fused_layer_forward`, `infer.m:13252–13260`, forbids temporal expert prefetch when `g_prefill_nrow_capture` is active. Capture returns before the ordinary expert-read consumer and must not leave a short read/validity array in that slot.
2. `serve_loop:21223–21225` drains active asynchronous scratch writes and resets decode prediction/prefetch phase flags before restoring/recycling model buffers for another admitted request.

The published six stale/omitted expert diagnosis is consistent with these ownership paths. The repair does not disable normal decode prefetch. Existing multi-request repaired evidence has a different scope from the freshly authenticated single-history32K oracle; neither substitutes for the other.

I/O workers retain task pointers until generation completion under mutex/condition synchronization (`infer.m:10257–10499`). Grouped staging starts and waits for its generation before consuming results (`prefill_nrow_grouped_async.inc:1743`). Cache-hit expert buffers and layout metadata are held for the grouped command; missing experts use private stage slices. Cache insertion/possible eviction is delayed until command completion (1683–1746,2005–2030). Derived projection offsets/layouts are recomputed from the current expert's bit width/size rather than persisted as unversioned pointers across eviction. This audit did not identify a surviving stale-derived-view path in this reviewed sequence; it is not a concurrency stress certification.

Lazy KV allocation uses page-aligned anonymous mappings and Metal no-copy views (`infer.m:8472–8565`). GPU view extent is bounded; CPU backing includes the larger CPU capacity. The view deallocator owns the mapping; failure paths unmap only unwrapped allocations. Teardown detaches a global view only if it is still the same cache's view, preventing an old cache from detaching its replacement. Shared addressing is not treated as synchronization: deferred expert completion, explicit queue waits, and restore fencing are separately required.

Snapshots (`infer.m:8640–8950`) capture completed GPU state, active KV lengths, CPU recurrent shadows and authoritative GPU GDN/convolution state. Partial allocation frees the partial snapshot. Restore fences independently of a pre-existing forward-error latch and validates extents/pointers before copying. Failure/cancellation invalidates the resident identity; discarded partial arrays need not be physically zeroed to satisfy this contract. New requests reset/restore before reuse. Streaming failed-state responses do not publish executable partial tool calls; strict and compatibility recovery notify session invalidation (`22000–22285`).

At32K, reviewed size calculations use `size_t`/widened accounting; bounded KV/view sizes are representable on arm64. No confirmed overflow, premature no-copy unmap, double release or active-cache eviction defect was found in the examined supported path. Actual OOM, device reset, concurrent inference and every flag cross-product remain unqualified. **C11-01** addresses admission policy, not a demonstrated memory corruption.

## 5. Checkpoint identity and restore safety

Selective identity is appropriate for the intended design. `warm_state_cache.inc:108–165,168–274` includes layout/execution versions, model geometry, quantization/storage flags, CPU capacity, relevant compute switches (resident MoE, oproj, tiny matvec, CPU/GPU linear, bypass, N128 and both chains), FE mask/operator identities, shader/small-authoritative-file contents and large-artifact stat identities. Exact token IDs are signed and compared via token count/signature alongside tool/profile/source identities. Profile is the reusable static prefix; session is evolving resident conversation.

`nrow-prefetch-ownership-v2` invalidates the affected eligible GPU-N128 class, including old aliased prefetch-off state, without invalidating unrelated scalar/CPU classes. Arithmetic changes not represented by hashed inputs still require execution/operator version discipline. Full executable hashing remains disabled intentionally; the audit does **not** recommend restoring it. Unrelated rebuild stability is supported by synthetic identity tests and recorded cross-build restore; it is not an automatic guarantee if developers omit a necessary version bump. Large-model stat fingerprints are a deliberate performance compromise, not full-content authentication.

### GPU-window reasoning

Serving static-prefix snapshots are capped at8192 tokens (`infer.m:8616`,20129,20951); supported GPU windows are at least8192. Therefore changing only an8K/16K/32K GPU window does not change the backend used while producing a currently persisted prefix, provided all other hashed modes/artifacts remain the same. This is valid for the present envelope. Increasing the prefix cap, shrinking the window below it, or changing backend eligibility/arithmetic invalidates that proof and must change an identity input/operator version plus regression tests. This is a **future-change guard**, not an existing stale-cache finding.

Header/storage validation checks format/layout/model geometry, exact prefix/profile/compatibility, bounded payload/stored lengths, complete file length/no trailing bytes and raw/compressed checksums before publication. Compressed decode is bounded. Partial transfer failure frees the staged snapshot; resident restore is a separate fenced step (`warm_state_cache.inc:315–609`). Raw1/Zstd2 storage and layout2/execution3 are unchanged. Atomic temp creation, checked writes/file fsync/close and rename preserve the final file on pre-rename errors. **C11-07** notes unchecked directory durability after rename. Checksums detect accidental corruption; these local files are not an authenticated hostile-input format.

The five static slots, pinned exclusion,768MiB dynamic snapshot budget and8192 cap remain. Source files are limited to128 profiles/64MiB (protected entries can prevent full eviction); state disk cleanup targets4GiB and protects current/fallback files. These are cache policies, not host physical-memory admission. Rebuild on incompatible/missing checkpoint is intentional; caches must be backed up before a separately approved migration.

## 6. Numerical evidence verification

Executed the independent [verify_mask63_evidence.py](verify_mask63_evidence.py), using explicit checks rather than importing Work A's PASS parser. It reads existing experimental evidence only. [Machine-readable result](evidence/independent-native-evidence.json):

| Check | Independently verified result |
|---|---|
| Manifest SHA256 | `86f5ffa6bd6ce42dcc81a934fdc82040a8f1059cf14ec53ec23e575957f56fce` |
| Actual saved executable SHA256 | `5960178f4dbc677a4b7fa660b8a9fb46773ea3dadc495f5604b400cc7f194602` |
| Runtime manifest/source freeze |45/45 current candidate and frozen copies match |
| Native and wrapper statuses / native exit | PASS / NUMERICAL_PASS /0; manifest and binary bindings agree |
| Endpoint sequence |256 ordered endpoints128..32768, no duplicates/missing endpoint |
| Active state |160 components/endpoint; zero differing values, nonfinite count0, equal nonempty persistent fingerprints |
| Maximum state error |0 |
| Maximum hidden error |`4.76837158203125e-7` |
| Maximum logit error |`5.7220458984375e-6` |
| Greedy / lengths / mirrors / finite flags |PASS at every endpoint |
| Actual candidate GPU routing |All ten layers3,7,11,15,19,23,27,31,35,39 at8192,8193,16384,16385,24576,32768 |

Inspected the oracle producer (`session_nrow_oracle.inc`): scalar and candidate evolve separate snapshot banks from the same token history; comparisons use synchronized active extents. Counterfactual rebasing is a separate diagnostic after failure, not a qualification repair. Existing tolerances remain state<1e-3, hidden<=1e-3, logits<=1e-2 plus greedy/finite/length/mirror checks; this actual run additionally has exact persistent fingerprints. It does **not** prove bitwise identity of hidden/logits or unobservable intermediate whole-model states inside an N128 slab.

Historical failures at1920,2304,3456 and stale experts at129 remain valid evidence for their builds/modes. No expensive numerical requalification was warranted by an evidence-integrity defect in the authenticated repaired result. The controller has an optimization-mode hardening issue (**C11-06**), but actual recorded ordinary Python invocations and independent verification do not exhibit that bypass.

Read-only EOS reanalysis of saved capture/restart traces also passes: end positions170/202/234, final EOS is completed and in effective history, all observed KV lengths/finite flags valid, continuation begins at prior end, restarted first turn begins at the logged restored prefix142. Capture/restart final digests match. [Result](evidence/saved-eos-review.json). This reruns a source-audited saved-trace checker, not live restore. Named-profile67,427,311-byte restore, real disconnect recovery and1536 generated tokens across four responses remain historical bounded evidence, not newly executed model tests.

## 7. Performance evidence and staging confounds

No new performance benchmark was launched. Private results and public sanitized figures agree for these completed trials:

| Context | Mode | Cold prefill s | Warm prefill s | Complete process trials |
|---|---|---:|---:|---:|
|16K|Ordinary N128 control|1325.305|995.824|1|
|16K|Mask63|1174.335|1180.462|1|
|16K|Scalar|2123.869|2148.034|1|
|32K|Ordinary N128 control|3098.961|3145.699|1|
|32K|Mask63|5128.867|5084.331|1|
|32K|Scalar|6741.074|Interrupted|0 complete cold/warm pairs|

The scalar32K cold **request** completed inside an interrupted process trial. It is not a complete cold/warm trial. The earlier interrupted mask63 cold request likewise is not an additional complete repetition. n=1 provides no run-to-run variance estimate. Different dates, page residency and environment prevent treating the apparent32K overhead as an isolated arithmetic cost. The ordinary path is numerically unqualified regardless of its timing.

Independently summed first128 phase records in both saved same-binary/input logs: linear staging49.685588→747.928412s, rowwise full attention52.196747→54.655568s. [Recomputation](evidence/staging-recomputation.json). The staging delta is about698.243s, a major measured increase relative to the approximately1042s elapsed-prefix difference. Full-grouped and linear-grouped scopes also increase; they overlap inner counters and must not be added as disjoint costs. These host counters are not GPU timestamps or proof of cache-hit rates.

Model page residency, filesystem cache, pressure, CPU/GPU competition and recorded Memory Cleaner auto-cleaning are plausible confounds; none is isolated causally. Only the previously recorded environment observation was reviewed; no current preferences/apps were queried or changed. Low launch GPU readings are admission observations, not proof that an entire hour-long run was uncontended.

**C11-05 recommendation:** missing scalar warm is not a universal correctness blocker. The Architect could explicitly permit a separately authorized, bounded native-only canary with accepted latency, enforced capacity/resource policy and rollback readiness. That would be a documented waiver/limited decision, not closure of the full32K comparison or authorization by this audit. General performance suitability remains unresolved.

## 8. Work B compatibility

B was exported into `/private/tmp/flash-ios-audit-work-b-20261110` with `git archive`, without changing B's worktree or merging. `npm ci --ignore-scripts --no-audit --no-fund`, TypeScript build and all44 tests pass. The initial sandbox run had34 localhost-listen EPERM failures and10 passes; rerun outside sandbox passes44/44. Those initial failures were environmental, not suppressed product failures. Only ephemeral fixture servers ran.

Source inspection supports the reported improvements: advertised-name and completed-ID duplicate rejection; unknown tool rejection; object/JSON and nested schema validation with locked `jsonschema` dependency; all calls validate before the first tool publication callback; incomplete/truncated streams never become executable tool requests; finish plus DONE required; consistent usage totals/cached bounds checked; malformed UTF8/JSON, invalidation, cancellation, byte/event caps and HTTP errors fail closed without automatic replay. Content and reasoning channels are normalized separately. UI text can be displayed provisionally before a later error; it is not a committed successful tool call. Callback failure itself is not an atomic rollback of already-run SDK callbacks.

The shipped generator sends full canonical history without guessed conversation IDs. Optional resident helpers have a narrower tested scope; they do not make the shipped generator resident. Source APIs use Chat Completions; **Responses API is unsupported**. Native usage/finish/invalidation shape is compatible with B's stricter parser in inspected cases. No runtime file overlap requires a merge conflict, but absence of overlapping edits is not combined end-to-end qualification.

53 actual-source native thinking-resolution cases were extracted/compiled against candidate A and pass expected characterization. `enable_thinking` and efforts none/low/medium/high are ignored; `off` and native budget/alias/clamp semantics differ from generic OpenAI expectations. Budget0 is not an off synonym. Same-completion answer text after native tools is rejected/recovered, not transparently preserved. Applications must translate supported controls and accept the documented tool contract, or those features need repair before support claims.

**C11-03:** B's600s total timer is incompatible with unbounded long-prefill support even while keepalives arrive. A fetch-only100ms scaled test reproduces the distinction from idle timeout. The conservative byte-based input cap restricts reachable requests but does not prove their latency. **C11-04:** actual MCP Gateway identity/registration, all-page catalog merging/cycle handling and correct endpoint dispatch remain NOT RUN. Fixture behavior alone cannot establish Gateway behavior. No Gateway implementation is presumed to exist in this repository. Current B GUI and live model tools are unqualified. PR2's older Oct26 GUI observations are retained as historical evidence only. Either exclude these features or qualify an isolated combined revision before claiming them.

## 9. Context/resource admission

| Property | Enforcement / evidence |
|---|---|
| Native request allocation bound |Actual `context_preflight`, widened sum, default65536; before active session mutation/restore |
| Generation request bound |HTTP clamps1..32768; this is output bound, not total context bound |
| GPU window |Backend selection bounds32768; CPU fallback above, not request rejection |
| Proposed total context<=32768 |Operator/client policy only in current serving build (**C11-01**) |
| Qualification capacity override |`FLASH_QUAL_CONTEXT`, only under qualification compile guard |
| Dynamic-prefix RAM |Five slots;8192 cap;768MiB dynamic budget, pinned entry excluded |
| Disk/source limits |Bounded cleanup with protected-file exceptions; not hard universal quota |
| Host6GiB reserve / RSS16GiB / host-free floor / launch GPU<30% |Benchmark/qualification controller checks; not ordinary HTTP product admission |
| One heavyweight model process |Operational test procedure; no host-global runtime arbiter |
| One evolving resident conversation |Native single active-session design; not a pool of conversation snapshots |

Eight compiled actual-source model-free boundary cases pass, including capacity+one rejection, negative accounting and INT_MAX-scale sums. They also prove accepting a request beyond32768 under the default65536. This is an unsupported-envelope admission gap, not evidence that a65536 allocation is overrun. No intentional OOM or heavyweight boundary test was performed.

## 10. Release procedure and rollback review

The November6 procedure accurately identifies the two source baselines, opt-in flag, exact tested Makefile form, shader/dependency co-location, cache migration, isolated profile naming and unresolved launcher ownership. Its source/build/backup outline is sound as a proposal. It deliberately does not establish an executable authorized deployment plan.

The diagnostic-free state-path performance variant has its own provenance and visible-output evidence; a new binary named like it is not the same artifact. Whole-file reproducibility differs in UUID/ad-hoc signature metadata; section/normalized comparisons are narrower evidence, not a whole-binary identity or cache key. Preserve compiler/SDK/link dependencies and runtime-loaded Metal sources, not just an executable. Model content/stat identity must be rechecked under a future approved build provenance process.

Before authorization an operator must, in a separately authorized task: establish actual service/launcher owner and executable mapping; pin intended source/config; record exact environment (especially mask63, profile paths and supported flags); archive/hash/verify binary, shader/include dependencies and both cache roots; verify free disk and restorable cache backup; define capacity and resource enforcement; specify owned-process commands and maintenance window; select isolated canary checks; define stop criteria and rollback after HTTP, state, tool or capacity errors. Rollback restores the complete previous dependency/config/cache set while stopped, uses captured arguments, creates new resident IDs and verifies health/request/follow-up. Profile rebuild/pruning means old binary alone is insufficient rollback.

These are future operator instructions, not commands executed by this audit. No production inventory or request was used to fill the gaps. No canary is authorized. Keep PR2/PR3 draft.

## 11. Open findings ranked by severity

Full ten-field records, static proofs, owners and scope conditions: [findings JSON](mask63-audit-findings-2026-11-10.json).

| ID | Severity | Finding | Owner |
|---|---|---|---|
|C11-01|P1|Qualified32K/resource admission is not enforced by serving policy|Work A / Architect|
|C11-02|P1|Deployment ownership and complete rollback provenance unresolved|Architect / operator|
|C11-03|P1, combined long-prefill scope|B total deadline expires despite healthy keepalives|Work B / Architect|
|C11-04|P1, claimed client scope|Actual combined Gateway/GUI/live-tool qualification missing|Work B / Architect|
|C11-05|P1|Incomplete/confounded performance gate needs explicit disposition|Architect / Work A|
|C11-06|P2|Python optimization removes release-gate assertions|Work A|
|C11-07|P2|Checkpoint directory-sync errors ignored after rename|Work A / future engineering|

No P0 confirmed. C11-03/C11-04 can be resolved by a clearly restricted native-only supported scope; they cannot be silently promoted to PASS. Speculation, GDN replay, cold-expert CPU routing, broad performance tuning and other platforms are P3/deferred research, not release repairs established by this audit.

## 12. Required remediation owners

Work A: implement/review bounded context admission and resource policy with Architect; harden evidence gate assertions; improve directory durability reporting. Work B: resolve supported timeout/control/tool contract and qualify actual advertised client paths on an isolated combined source selection. Architect: choose feature/latency envelope, disposition scalar-warm/performance limitations, and obtain verified deployment/rollback prerequisites. The audit branch contains no runtime repair and no authorization to integrate either engineering branch.

## 13. Executed checks and remaining evidence

| Executed on November11 | Result |
|---|---|
|Candidate45-file/frozen executable/manifest and256-row evidence recomputation|PASS|
|Ten-layer GPU markers at six specified boundaries|PASS from saved evidence|
|Independent staging-log phase recomputation|PASS|
|Saved EOS/profile trace reanalysis|PASS,170/202/234|
|Native build, separate `infer-audit-model-free`|PASS|
|`--self-test-tools`|PASS,45 PASS markers including summary|
|`--self-test-api`|PASS,29 PASS markers|
|`--self-test-warm-state` isolated synthetic directory|PASS,37 PASS markers including summary|
|Work A model-free `test_work_a_*.py`|26/26 PASS|
|Work B TypeScript / mock suite|PASS /44 of44 PASS after sandbox-only bind denial|
|Actual-source control resolution|53 cases PASS characterization|
|Actual-source context accounting|8 cases PASS; envelope gap reproduced|
|Keepalive versus total timeout|Gap REPRODUCED with fetch mock|
|Optimized Python gate|Bypass REPRODUCED with synthetic evidence|
|New heavyweight numerical/performance/model tests|NOT RUN; outside audit scope|
|Actual current GUI/Gateway/combined live model tools|NOT RUN|
|Any production operation/inventory|NOT PERMITTED / NOT PERFORMED|

Commands and reproduction details: [test commands](mask63-audit-commands-2026-11-10.md). Logs and sanitized results are in [evidence](evidence). The new evidence checker initially assumed a controller-style `--binary` entry in a native command array; that audit-script assumption was corrected to the recorded executable at argv0 before success. No product evidence/assertion was changed to obtain PASS.

Remaining model tests, if a future combined feature scope requires them, should be short isolated client/tool/cancellation checks with exact selected source/build/profile, guarded resources, private trace collection, explicit tool executor mock and before/after session evidence. They require separate scheduling; no full32K rerun is proposed without a specific failure/evidence need. Production is never their target.

## 14. Supported versus unsupported configurations

Evidence supports the pinned experimental candidate on baseM4/24GiB, stated tiered Q2/Q4 model,40 layers/256 experts/K8, N128 M4-8row gate-up bitsplit/M4-2row down, explicit mask63, default GPU-linear/resident-MoE/oproj/tiny/chains/prefetch, lazy32K attention, exact effective-token histories and bounded sequential resident/static-prefix behavior. This is a qualified numerical envelope, subject to C11-01/C11-02/C11-05 before release authorization.

Excluded: default ordinary-N128 as a correctness alternative,64K supported serving, arbitrary mode cross-products, iOS/other hardware/weights, multi-model resource arbitration, complete current GUI/Gateway claims, Responses API, arbitrary JSON-schema interoperability, universally correct model instructions, actual hardware-OOM/device-reset robustness and uncontended production speed claims. Matching scalar's wrong literal is parity evidence, not successful instruction following.

## 15. Final release-readiness recommendation

Preserve the candidate and its scalar reference. Resolve mandatory P1 prerequisites, explicitly narrow or qualify prospective clients, and retain historical negative evidence. Do not conflate numerical success with deployment readiness or incomplete performance with invalid arithmetic. A restricted canary could be considered only by the Architect after admission/provenance/rollback/latency prerequisites are addressed; this report grants no operational permission.

## 16. Publication and ledger addendum

Reports and model-free audit tools are committed only to [`audit/mask63-preproduction-readiness-20261110`](https://github.com/KingdomDesignsConsulting/Flash-iOS/tree/audit/mask63-preproduction-readiness-20261110). The publication commit is the Git commit containing this report; its exact SHA is supplied in the delivery message and `git log -1` on that branch. Candidate [21a0731](https://github.com/KingdomDesignsConsulting/Flash-iOS/commit/21a073174fb1feb828f2d28762293d1803e66a9a) and B [01ae997](https://github.com/KingdomDesignsConsulting/Flash-iOS/commit/01ae9976f541c384dd83905fc006da196971bdb2) remain separate and unmodified.

Proposed ledger delta, **not applied**: “November11 Workstream C: candidate21a0731 audited; repaired32K evidence independently authenticated; no confirmedP0; C11-01..C11-05 release prerequisites and C11-06/C11-07 hardening recorded in audit branch. Actual combined Gateway/GUI support and performance disposition remain bounded/unresolved. Production excluded, drafts retained, no deployment authorized.”

**AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**
