# Flash-iOS Mask63 Pre-Production Release Gate Matrix

**Audit date:** 2026-11-10  
**Candidate:** Work A `21a073174fb1feb828f2d28762293d1803e66a9a`  
**Work B:** `01ae9976f541c384dd83905fc006da196971bdb2`  
**Decision:** **AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**  
**Environment:** experimental candidate only; no installed production access permitted.

## Gate matrix

| Gate | Current evidence | Status | Release condition and owner |
| --- | --- | --- | --- |
| Runtime source freeze | Exact Work A SHA verified; subsequent harness/documentation commits contain no normal runtime changes | **PASS — source** | Freeze final source/dependencies/build configuration, Architect |
| Default feature isolation | FE027 mask compile option and runtime env value explicit; ordinary `infer` unchanged | **PASS — source** | Preserve default/rollback mode, Work A |
| N128 mask63 numerical | 256 ordered published slab endpoints through 32768; independent sanitized row criteria and ten-layer route record check PASS | **PASS — published evidence** | Independently rehash private original binary/raw artifacts before final approval, Work A/auditor |
| Repaired prefetch ownership | Request-boundary drain/reset, capture exclusion, v2 selective marker; prior six omitted experts reproduced and repaired | **PASS — source and reported tests** | Preserve repeated stateless/resident restart/cancel regression, Work A |
| Checkpoint compatibility | Mode/profile/model/prefix signatures, ownership and operator variants, corruption refusal and exact state replay | **PASS within documented configuration** | Guard future backend or prefix limit changes, Architect |
| GPU 32768 numerical routing | Ten observed full-attention layers at all six named positions; CPU fallback after 32768 | **PASS — published evidence** | GPU-only policy enforcement remains separate, Work A |
| Native CPU KV capacity | 65536 preflight protects engine memory range | **PASS for memory bound; INADEQUATE for release GPU-only envelope** | Add/verify 32768 GPU-only runtime or launcher constraint and output reserve, Work A |
| Host/GPU resource admission | 35% host floor, three GPU samples <30%, 6GiB OS reserve, RSS/host watchdog are qualification-controller features | **P1 — NOT a service-level guard** | Specify native/service admission, limits and overload semantics; Architect/Work A |
| GPU command-buffer error propagation | Checked completion helper in production-sourced engine and N128 phase status checks | **PASS — source** | Keep device failure and invalidation regressions, Work A |
| Memory footprint | Bounded M4/24GiB tests reported with distinct sampled RSS, physical and Metal measurements | **BOUNDED PASS / long stress NOT RUN** | No arithmetic addition of aliasing metrics; canary headroom guard, Work A |
| 16K performance | n=1 cold/warm complete for all three paths; mask63 warm +18.541% ordinary | **EXPLORATORY** | Explicit latency acceptance and environment controls, Architect |
| 32K performance | n=1 ordinary and mask63 cold/warm complete; scalar cold only, warm incomplete; mask63 warm +61.628% ordinary | **P1 — INCOMPLETE** | Decide bounded latency threshold and scalar warm necessity; Architect/Work A |
| Repeated long HTTP decode | Four short 384-token responses and limited lifecycle reported; no sustained long-output rate certification | **BOUNDED PASS / NOT GENERAL** | Scope or controlled sustained test, Work A |
| Literal-change instruction | Both scalar and candidate repeat old literal; no scalar/candidate numerical mismatch | **OBSERVED FAIL for requested behavior** | Treat as model/assistant behavior, not proven N128 regression; owner define support envelope |
| Work B adapter parsing and tools | 44/44 reported tests; bounded SSE/UTF8, atomic complete-schema-validated tool publication, sensible stateless identity policy | **PASS — source and reported mock tests** | Integration build + same-host endpoint test before merge, Work B |
| Native thinking API | Budget/off precedence known; enable_thinking/effort none/low/medium/high ignored | **P1 if promised; P2 otherwise** | Fail clearly or normalize by approved contract, Work A/Work B |
| Answer→tool→answer | Nonwhitespace post-tool native text is invalid/recovery | **EXCLUDED** | Document unless independently qualified, Work A |
| LM Studio GUI | Current Work B report says GUI NOT RUN, installed service unreachable | **UNQUALIFIED** | Exclude or verify actual GUI attachments, cancel/reconnect/restart, Work B |
| MCP Gateway registration | External code not in repository, only mock fixture wire checks | **UNQUALIFIED** | Exclude or verify actual registry uniqueness/revision/pagination/dispatch, Gateway owner |
| Responses API | No native Responses endpoint | **UNSUPPORTED** | Exclude claim |
| Source/build provenance | Candidate SHA/manifest recorded; Mach-O normalized reproducibility reported | **PARTIAL** | Fresh final binary/shaders/source/deps fingerprints, independent artifact check, Work A |
| Installed production provenance | Old source checkout SHA is not verified live executable, launcher/PID unknown | **P1 — BLOCKED** | Future operator-only inventory after separate authorization, Architect |
| Rollback completeness | Review-only procedure explicitly preserves old files/caches and forbids blind kill/port takeover | **PLAN EXISTS; EXECUTION NOT VERIFIED** | Archive/verify all dependent assets and service-owner actions before release, operator |
| Deployment | Neither PR merged nor production altered; no canary permission from audit | **NOT AUTHORIZED** | Separate Architect release authorization only |

## Risk-ranked minimal remediation matrix

| Order | Finding | Minimal bounded next action | Acceptance criterion |
| ---: | --- | --- | --- |
| 1 | C-01, context/resource admission | Define explicit GPU-only limit and output reserve; implement native or verified launcher cap in release candidate | At 32768 accepted and at 32769 rejected **when GPU-only mode is requested**, without loss of an existing resident state; CPU fallback remains available where explicitly supported |
| 2 | C-03, provenance/rollback | Obtain operator-authenticated service mapping and preserve verified installed binary/shaders/source/config and caches; document exact owned stop/start | Original environment and cache can be restored in a documented, unambiguous order; no unknown PIDs or broad process kills |
| 3 | C-02, intended-capacity suitability | Define release latency/SLO and decide whether n=1 32K scalar warm is indispensable; use resource admission before any authorized repeat | No fabricated complete scalar pair; explicit acceptance or continued performance block |
| 4 | C-04, thinking controls | Resolve native/client precedence; fail visibly on unsupported values | Same rendered token identity and buffered/SSE behavior for supported controls; no silent ignore |
| 5 | C-05, external integrations | Explicitly exclude GUI/Gateway/Responses, or qualify actual external implementations separately | No mocked fixture substituted for actual Gateway registration or installed GUI |
| 6 | C-06, raw attestation | Independent read-only check of original Work A manifest, runtime hashes, executable and private raw oracle/log | Source, model and binary hashes match; raw endpoint checks and native-route log genuinely produced the sanitized summary |
| 7 | C-07/C-08/C-09 | Document output-order limitation, future backend hash guard and staging confounds | No unsupported feature claim or unconditional performance causality claim |

## Proposed future operator checklist (NOT EXECUTED)

1. Under a distinct approved maintenance operation, identify the **actual** production service owner/launcher, PID, executable mapping, path and environment. Do not assume a launchctl label or port-owning process.
2. Read-only fingerprint the installed executable, its matching Metal source/shader and framework dependencies, model/config, launch args, static profiles, state caches and disk free space. Verify all backups and preserve timestamps.
3. Independently authenticate the reviewed candidate binary against source manifest and original raw qualification evidence. A new build requires its own fingerprint and short gate; same filename is insufficient.
4. Set a supported feature envelope and 32768 GPU-only admission/latency policy; keep 16K fallback and an exact old artifact/cache rollback snapshot.
5. Only after explicit authorization, execute a separately documented isolated canary with a separate profile and port, then perform bounded health, actual client, resident follow-up and profile-restart checks.
6. If later release or canary checks fail, stop only the **recorded owned candidate process**, restore the old complete cache/config while stopped, and restart the exact old service with previously captured arguments and dependencies.
7. Do not reuse a resident session ID after restart; clients must replay full canonical history on explicit invalidation.

**No production inventory, port probe, model launch, OOM test, service restart or deployment was run by this audit.**

## Numerical evidence verification note

The static sanitized check was independently executed against `docs/results/work-a-mask63-release-closure-2026-11-04.json` (Work A SHA). It found 256 distinct positions exactly 128..32768 step 128, reported PASS, finite/error bounds, unchanged active fingerprints, greedy identity encoded as numeric `1`, and all ten candidate GPU layers at 8192/8193/16384/16385/24576/32768. The raw original binary/log/fixture was unavailable. The native oracle compares completed full-model states only at observed endpoints; exact persistent fingerprints do not assert identical all-intermediate floating-point arithmetic.

## Source links

- [Independent audit report](mask63-preproduction-audit-2026-11-10.md)
- [Machine-readable findings](mask63-audit-findings-2026-11-10.json)
- [Work A frozen candidate](https://github.com/KingdomDesignsConsulting/Flash-iOS/tree/21a073174fb1feb828f2d28762293d1803e66a9a)
- [Work B qualified candidate](https://github.com/KingdomDesignsConsulting/Flash-iOS/tree/01ae9976f541c384dd83905fc006da196971bdb2)
- [Release procedure](https://github.com/KingdomDesignsConsulting/Flash-iOS/blob/21a073174fb1feb828f2d28762293d1803e66a9a/docs/work-a-mask63-release-procedure-2026-11-06.md)
- [llama.cpp PR #31688](https://github.com/ggml-org/llama.cpp/pull/31688)

**Final disposition:** **AUDIT CONDITIONAL PASS — SPECIFIC REMEDIATIONS REQUIRED**. This is a recommendation to the Lead Architect, not authorization to deploy, merge or modify production.
