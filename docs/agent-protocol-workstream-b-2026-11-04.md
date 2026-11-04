# Workstream B handback — 2026-11-04

**PARTIAL QUALIFICATION — REMAINING GAPS**

## Provenance and inspected scope

Original checkout HEAD: `5c26430f2790b84516b7384915eb0500abc5392f` on `flash-moe-production`. Fetched origin, then created `/private/tmp/Flash-iOS-agent-mcp-protocol`, branch `work/agent-mcp-protocol-reliability`, from latest reference `66adf92e2ea950528917000d1b59b788e1687371`. Ending HEAD is the commit containing this report (reported by exact SHA in the final handback). No production branch merge or service change.

Read the mandatory ledger/research/readiness documents from the isolated reference, native HTTP/token/tool/parser/render/session/usage/self-test sections, LM Studio source/tests/README/VALIDATION, release paired protocol driver, existing adapter history and PR #2 body. Current production checkout lacks the newer research/readiness files; reference worktree contains them. PR #2 remains draft. Native changes in the workstream-A area were avoided.

## Regression matrix

| Goal / protocol | Executed evidence | Boundary |
| --- | --- | --- |
| B1 contract | [Protocol contract](agent-protocol-contract-2026-11-04.md), actual source inspection | Chat Completions only; Responses absent |
| B2 SDK SSE channels | Reasoning/content, literal markers, nested Unicode/escaped JSON, content→tool→content, two calls, every wire byte split, every argument character split | Mock provider with actual SDK Chat; native token-driven transitions inspected, not forced-generated |
| B3 calls | Unknown names, duplicate IDs, absent args, nested missing/type errors, extra properties, array/non-string/malformed args, valid then malformed, token-limit/incomplete finish all rejected atomically | No external executor invoked; broad schema dialect excluded |
| B4 controls | 53 cases compiled from exact native resolution statements; alias/null/clamp/conflict and stream flag matrix. Four native renderer/token-ID captures | Unsupported controls silently ignored; HTTP/profile/restore cross-products NOT RUN |
| B5 MCP duplicate identity | Two real localhost JSON-RPC fixture endpoints expose same logical name, different schemas/URLs | Fixture wire checks PASS; Gateway registration/routing NOT RUN; repository unavailable |
| B6 MCP discovery | Two/three page fixtures, duplicate tool, invalid cursor, cycle, empty middle and later error fixtures checked over HTTP | No actual client/manifest implementation; atomic refresh, reconnect, stale dispatch and page-timeout behavior NOT QUALIFIED |
| B7 completion | Reject choice events after finish, duplicate finish, multiple choices; allow usage-only after finish; incomplete calls never published | Responses NOT SUPPORTED; buffered native coverage inherited, not rerun against inference |
| B8 lost calls | Paired direct/announce prompts, identical schema/user text, native thinking on/off token captures | Prompt-only evidence; model generated tokens and live lost-call classification NOT RUN |
| B9 SDK path | Actual SDK Chat→generator→raw HTTP fixtures; existing cancellation, full-history documents, ordered tool results and resident helper tests pass | Real installed SDK document-service attempt FAILED: LM Studio unreachable. Computer-use application inventory showed no running LM Studio app. GUI NOT RUN. No model inference |
| B10 deterministic failures | UTF-8/delimiters, malformed args, premature EOF, invalid finish, ID errors, midstream errors, negative/inconsistent/cached usage | Bounded CPU tests; no GPU inference or uncontrolled fuzzing |

## Reproduced defects and fixes

Before patch, the expanded adapter protocol file ran 29 registered tests (including imported existing transport tests): **20 pass, 9 fail**. Failures accepted unknown names, duplicate IDs, absent arguments, missing nested required fields, wrong nested types, additional properties, content after finish, duplicate finish and multiple choices. The absent-argument fixture also omitted a required payload; source separately showed empty arguments substituted with `{}`.

Fixes in `generator.ts`: snapshot advertised names/schemas, reject duplicate advertised names, validate tool fragment types, reject duplicate completed IDs and unknown names, require explicit JSON object arguments, and validate all arguments against advertised schemas before any SDK tool callback. A direct pinned dependency makes schema validation independent of SDK's transitive dependency layout.

Fixes in `transport.ts`: single-choice terminal state checks, nonnegative exact usage arithmetic and cached≤logical-prompt validation. Additional usage regressions were added during the repair; they were not part of the original nine-failure run. Helper extraction prevents re-registering existing tests when new tests reuse localhost fixtures. Final suite: **44/44 PASS**, including 25 new cases over the original 19. A test case may loop through many split points.

Unmodified native `--self-test-tools`: PASS (45 PASS output lines including summary). `--self-test-api`: PASS (29 PASS lines including aggregate/other layout suites). A binary placed directly in `/private/tmp` initially failed the executable-relative tool-cache location assertion; the identical binary passes from the project's `metal_infer` directory. This is test placement evidence, not a parser fix. Initial build attempts invoked an implicit make rule with an overridden target; corrected explicit target build passes with the actual Makefile framework flags. No native source changes.

## Remaining reliability gaps and handback to Architect

- FE-012/017: native silently ignores unsupported thinking controls; request-level precedence is characterized, not repaired. Make shared-file ownership/compatibility decision before a focused `infer.m` patch.
- FE-011/028: native post-tool answer text is rejected/recovered, not preserved. Ordinary-token literal markers inside native tool arguments and every native delimiter/truncation edge need a dedicated forced-token harness. Adapter field handling is qualified separately.
- FE-030: no fresh live model evidence distinguishes model prose choice from native parser loss. Existing scalar/candidate literal-change failure remains open and was not investigated in duplicate.
- FE-040/041: no Gateway/MCP registry/client code or external repository identity was found. Fixture provision is not registration/pagination qualification. Obtain actual repository authorization and run the contract against its real implementation.
- FE-025: GUI NOT RUN. Existing GUI claims remain historical; this service attempt could not connect. Do not start/restart production to make this pass.
- FE-034/037: adapter error and accounting consistency PASS; no new live engine state/accounting claim. Existing five paired native response results retain their original bounds.

Ledger is intentionally untouched because it is shared and has concurrent work. This report is the scoped integration artifact for FE-011/012/013/014/017/025/028/030/034/037/040/041. No FE item is promoted to universal qualification.

## Exact reproduction

From the new worktree root (Node 22.19.0 / SDK 1.4.0):

```sh
cd clients/lmstudio-documents
npm ci --ignore-scripts
npm run build
node --test test/*.test.cjs
cd ../..
python3 tools/qualify_agent_controls.py --out /private/tmp/agent-controls-new.json
make -C metal_infer "$PWD/metal_infer/infer-protocol-selftest" INFER_TARGET="$PWD/metal_infer/infer-protocol-selftest"
./metal_infer/infer-protocol-selftest --self-test-tools
./metal_infer/infer-protocol-selftest --self-test-api
make -C metal_infer release-qualification RELEASE_QUAL_BINARY=/private/tmp/flash-protocol-render
python3 tools/qualify_agent_render.py --binary /private/tmp/flash-protocol-render --model '/Users/Shared/Main Hard Drive/AI Storage/AI Models/Reasoning/alexintosh/Qwen3.5-35B-A3B-Q4-Tiered-FlashMoE' --out /private/tmp/agent-render-new
```

Render output directory must be new. Renderer exits before weights/Metal allocation. Native build links frameworks but self-tests do not launch inference. Use ephemeral localhost ports in fixtures; no service uses production port 11241 (or historical production ports). Raw test logs reside under `/private/tmp/protocol-*.log`; exact synthetic token arrays are in `/private/tmp/protocol-render-evidence/native-render.json`, not GitHub. Sanitized counts/hashes are committed in `docs/results/agent-protocol-2026-11-04.json`. The failed optional service command was `node test/live-sdk-documents.cjs --out /private/tmp/protocol-sdk-documents.json`; it produced no passing report.

## Adapter integration strategy

Review and cherry-pick focused Workstream B commits into the experimental integration branch only after Architect review. Keep the shipped SDK generator stateless; do not infer chat identity from SDK object references. Supply a verified scope plus endpoint/config/schema identity before enabling resident helper reuse. Install/test the plugin GUI against an explicitly isolated experimental endpoint later; validate real attachments, cancellation and reconnect separately. Gateway owner can import the MCP fixture for real registry/discovery tests; no replacement Gateway is shipped. No automatic merge, deployment, tool retry or production restart is authorized by these results.
