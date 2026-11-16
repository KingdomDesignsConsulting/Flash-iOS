# Workstream B continuation — November 16, 2026

**PREFIX-CACHE REGRESSION: PASS** — bounded native parser/render/tokenizer negative finding, not live cache performance qualification.

**C11-03 DEADLINE: RESOLVED** — configurable finite total/idle deadlines, unchanged defaults; long-prefill operators must explicitly increase total duration.

**C11-04 CLIENT INTEGRATION: NOT RUN** — actual Gateway and installed GUI remain unqualified.

Adapter fix commit: `3bfc22970457a57a3247f546bb7108ad8efa4388`.

## Source and ownership

Fetched origin and verified both existing Work B local/remote HEADs remain `01ae9976f541c384dd83905fc006da196971bdb2`. The former `/private/tmp/Flash-iOS-agent-mcp-protocol` worktree no longer exists; its Git registration is prunable. Created `/private/tmp/Flash-iOS-work-b-20261116`, branch `work/agent-prefix-deadline-20261116`, from that exact remote HEAD. Ending HEAD is the commit containing this handback, reported by SHA in the final response. No existing branch was overwritten.

Read the prior contract, handback, JSON evidence, SDK transport/generator/config/resident code, actual native message parsing/template/cache lookup, and the audit document using `git show audit/mask63-preproduction-readiness-20261110:docs/audits/mask63-preproduction-audit-2026-11-10.md`. Work A's `21a0731` and audit/verification branches were inspected as references only; nothing was merged or modified there. Native production source, templates, admission, state format and kernels are unchanged. PRs #2/#3, production binaries/services and port 11241 were not touched. No model inference or GPU work ran.

## Supported endpoint and role contract

Native HTTP dispatch implements POST `/v1/chat/completions` (buffered JSON and SSE), GET `/v1/models`, GET `/health`. The LM Studio generator consumes **streaming Chat Completions only**, sends full stateless history, displays dedicated reasoning/content fields, and publishes validated tool calls after finish plus DONE. A new test explicitly rejects buffered JSON at this adapter boundary. Native buffered generation was not live-tested in this continuation.

The separate resident helper accepts verified caller scope and endpoint/config identity; the shipped SDK path remains stateless. Tool/result history IDs and order remain authoritative. No MCP registry/discovery/dispatcher implementation exists in the inspected `clients`/`tools` source; existing MCP fixtures are not that implementation. Responses API tests are **NOT APPLICABLE** to the current adapter.

The [SGLang issue #49550](https://github.com/sgl-project/sglang/issues/49550) reports late trusted-message relocation on its Responses path. That is a test hypothesis, not a Flash defect. Flash's actual `parse_chat_messages` merges only **leading** system/developer messages into the initial system instruction block, in input order with double-newline separators. Once conversation starts, either trusted role returns nil; the HTTP handler emits 400 `invalid messages` before session/cache operations. The renderer likewise rejects late system messages and has no separate developer branch. This matches the inspected Qwen contract requiring initial system instructions. This work neither expands that role contract nor rewrites the template.

The adapter forwards role/order verbatim and propagates the native rejection. It never demotes trusted reminders to user text. A changed user reminder is a semantic control only, not an optimization recommendation. Tests include untrusted user/tool text asking to ignore trusted instructions; that text stays in its original user/tool serialization boundary. These tests check serialization and authority handling, not whether a model resists all prompt injection or arbitrary embedded control-token attacks.

## Native prefix experiment

`tools/qualify_agent_prefix.py` copies the exact native `infer.m` into a temporary build directory and replaces only its diagnostic include with `tools/agent_prefix_diag.inc`. The diagnostic calls the **actual** production `parse_chat_messages`, tool schema/history validators, Qwen renderer, tokenizer, signature helpers and cache metadata selector. Normal runtime source remains unchanged. Existing render-only startup exits before weights load or Metal initializes; output verifies both flags false.

Thirteen synthetic histories include first/repeated request, assistant lookup/tool-result continuation, unchanged/number-changed late system and developer reminders, unchanged/number-changed user reminders, changed leading system instructions, and leading developer configuration. Input JSON retains original order; native JSON records normalized order, exact rendered bytes and complete token IDs. Fixtures preserve identical tool schema throughout. Four late-trusted cases fail closed without rendering or cache lookup. Nine supported histories render successfully.

| Comparison | Left/right prompt tokens | Common prefix tokens | First differing token, zero-based | Common bytes |
| --- | --- | --- | --- | --- |
| First vs identical repeat | 396 / 396 | 396 | None | 1884 |
| First vs tool-result history | 396 / 463 | 396 | 396 (left ends) | 1884 |
| Tool-result vs added user reminder | 463 / 478 | 392 | 392 | 1867 |
| User reminder budget 12000 vs 11900 | 478 / 478 | 464 | 464 | 2165 |
| Tool-result vs changed leading instructions | 463 / 472 | 370 | 370 | 1753 |
| Leading budget 12000 vs 11900 (same length) | 472 / 472 | 374 | 374 | 1772 |

Adding a real user turn changes the template's historical-reasoning treatment after the last user query, explaining the 392-token boundary in the third row; it does not indicate late trusted-message relocation. Changing just the user reminder's numeric text leaves the earlier 464 tokens intact. Changing the leading trusted instructions legitimately changes early tokens: an ordinary cache miss is correct here.

The native system/tools prefix is 372 tokens for the stable histories. A synthetic metadata cache entry seeded with its actual context/token signatures is found by the production selector for repeated/tool/user-reminder histories. Leading system/developer changes produce 381-token prefixes and lookup `-1`. An additional pair varies only a leading budget number (12000→11900): both prefixes are 381 tokens, yet the changed signature correctly returns `-1` against metadata seeded with the original budget. This covers equal-length token-distinct prefixes as well as length changes. Every accepted full prompt starts with its computed system/tools prefix. This tests real selection logic with synthetic metadata only: **no KV/GDN/convolution snapshot is captured, restored or reused**. Actual reused/restored tokens, prompt-cache hits, TTFT, generated content and generated tool validity are NOT RUN/null. No live cache correctness or speed claim is made. The rejection contract means there is no rendered late-system prefix to compare.

The actual resident helper is separately tested: leading instruction changes, appended system/developer reminders, a user→developer role change, schema changes, and endpoint changes all send a fresh identifier and full history. The native endpoint then rejects unsupported late roles; helper rebuild is not evidence that those roles become supported. On ambiguous timeout the helper drops its acknowledgement and does not retry; the next request rebuilds. No serialization/cache optimization is justified by these findings.

## C11-03 implementation and configuration

Global SDK settings now expose:

| Setting | Default | Allowed range | Effect |
| --- | --- | --- | --- |
| `totalDeadlineSeconds` | 600 | Whole seconds 1–86400 | Bounds the complete HTTP request/stream regardless of progress |
| `idleDeadlineSeconds` | 120 | Whole seconds 1–86400 | Bounds time without received bytes, including connection/header wait |

`requestDeadlines` validates settings before connecting. Direct `completionEvents` callers retain the existing positional millisecond arguments with finite integer validation (1–86400000 ms). Existing defaults are unchanged. An intended long-prefill configuration can choose total 7200 seconds and idle 120 seconds; this allows two hours but does not certify that model workloads complete in that time. There is no unbounded setting, automatic duration extension, or capacity change.

Both clocks begin before fetch. Before response headers, timeout phase is `headers`; after headers it is `body`. These are the only reliably identified phases. Response headers and nonempty body chunks refresh idle activity, never total duration; SSE comments/keepalives count as body activity. No separate prefill clock is fabricated. Transport byte/event caps still apply. Monotonic elapsed checks supplement timers around reads and event processing so delayed timer delivery cannot silently admit an expired stream. Event-loop suspension/OS scheduling still bounds how promptly code can react; this is not a real-time system guarantee.

`DeadlineError` distinguishes `deadline=total|idle` and `phase=headers|body`, retains accurate partial-output evidence, and does not claim server invalidation. Caller AbortSignal reasons propagate. Cleanup clears timers, removes cancellation listeners and cancels the reader; a fixture verifies response closure and one request only. The resident helper's existing deletion-before-send provides local fail-closed acknowledgement handling. Server rollback cannot be inferred from a disconnected client.

Tool arguments never become executable after transport deadline failure, even if a tool finish arrived but DONE did not. Every batch still validates completely first. Two new regressions exposed a separate cancellation defect: cancellation inside a tool-name callback still allowed completion, and cancellation after the first completed call still published the second. Checks between SDK callbacks now stop those publications. A previously published completed call cannot be recalled; no automatic retry occurs. Request deadlines end at validated HTTP stream completion; local synchronous schema/UI processing is not a separate timeout phase.

## Regression matrix and evidence

Node 22.19.0, SDK 1.4.0; TypeScript build PASS.

| Test group | Executed result | Evidence boundary |
| --- | --- | --- |
| Original Work B tests | **44/44 PASS**, before modification | Existing mock SDK/HTTP/MCP fixture coverage only |
| Deadline/cancellation additions | **16/16 PASS** | Scaled millisecond streams plus actual 1-second configured generator deadlines; not hours of inference |
| Role/resident additions | **10/10 PASS** | Actual resident helper plus generator/HTTP fixtures; hand-built message interface for roles SDK may not expose |
| Combined final suite | **70/70 PASS** | Same original 44 plus 26 additions |
| Native parser/template/tokenizer | **13 cases PASS** | Nine accepted/four rejected, exact token capture and actual metadata selector; no inference |
| Cancellation failing-before proof | Two failures before callback guards, both PASS after | Initial 14-test deadline suite: 12 PASS / 2 FAIL; those two failures are genuine adapter defects |
| Fixture correction during development | Two initial authority tests failed before HTTP due to missing assistant mock method; corrected mock, PASS | Harness issue, not a product defect |

New deadline tests cover healthy keepalives across scaled prefill, idle silence, total expiry despite continued keepalives, header wait, pre-cancellation and reason propagation, truncated JSON at deadline, finish without DONE, configured generator deadlines, complete args without DONE, callback cancellation immediately before/after completion, finite setting validation, response cleanup and no retry. Existing malformed-final-state and atomic schema validation tests remain passing. New authority tests cover unchanged outbound roles/order, leading developer forwarding, untrusted text preservation, changed identities, no mismatched-prefix reuse and buffered-response rejection.

Sanitized evidence: `docs/results/agent-prefix-deadline-2026-11-16.json`; raw synthetic inputs/rendered prompts/token arrays and compiler log: `/private/tmp/work-b-prefix-budget-20261116/`. Raw test logs: `/private/tmp/work-b-baseline44.log`, `/private/tmp/work-b-deadline-before.log`, `/private/tmp/work-b-final70.log`. Raw token arrays are not committed.

## C11-04 and release recommendation

C11-04 remains **NOT RUN**. Computer-use inventory shows no running LM Studio application; there is no source-bound isolated GUI/client/model endpoint established for this continuation. No GUI was launched or installed, and no inference service was contacted. An actual MCP Gateway repository/client, registration store, discovery-refresh lifecycle and schema→execution-endpoint dispatcher are missing. Tests of the two mock MCP endpoints continue to pass but do not qualify duplicate isolation, atomic refresh, reconnection or dispatch in an actual Gateway.

Recommend Architect review of these continuation commits for experimental adapter integration only. C11-03 source incompatibility is resolved through explicit settings; default600s users still need to configure a larger total for long prefills. C11-04 cannot be closed by that fix. No combined Work A/B live model, GUI, resource admission, long-prefill TTFT, cache restore or release performance qualification is implied. Retain native-only/explicitly bounded client claims until an isolated combined source selection and real client/Gateway are available. Other audit findings retain their owners/status; the audit branch and shared ledger are untouched.

## Reproduction

From `work/agent-prefix-deadline-20261116`:

```sh
cd clients/lmstudio-documents
npm ci --ignore-scripts
npm run build
node --test test/*.test.cjs
cd ../..
python3 tools/qualify_agent_prefix.py --out /private/tmp/agent-prefix-rerun
```

Use a new output directory; optional `--model` overrides the documented local tokenizer/config path. The native script has a 180-second build bound, 60-second render bound, input/case/token bounds and no model-weight load. Its temporary source/binary are removed after evidence collection. Raw outputs remain in the supplied directory. Rerunning tests requires permission to bind ephemeral localhost fixture sockets; no fixed production port is used.
