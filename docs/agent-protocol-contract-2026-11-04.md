# Workstream B protocol contract — 2026-11-04

Baseline: `66adf92e2ea950528917000d1b59b788e1687371`. Tests establish the adapter contract before repairs; no native inference source is changed. This is experimental qualification, not production approval.

## Actual ownership

| Layer | Inspected implementation | Responsibility |
| --- | --- | --- |
| Native HTTP engine | `metal_infer/infer.m` | POST `/v1/chat/completions`, GET `/v1/models`, GET `/health`; prompt rendering, token-aware channel separation, schema normalization, structured calls, finish/usage/session publication |
| LM Studio generator | `clients/lmstudio-documents/src/generator.ts` | Actual SDK Chat history and definitions to HTTP; reasoning/content display; collect and validate every call before SDK publication |
| Transport | `clients/lmstudio-documents/src/transport.ts` | Bounded UTF-8/SSE decode; HTTP/error/invalidation detection; terminal integrity; no automatic HTTP retries |
| Resident helper | `clients/lmstudio-documents/src/resident.ts` | Optional verified scope, endpoint/config/history identity, ordered tool results; one retry only after explicit pre-output invalidation |
| Documents | `clients/lmstudio-documents/src/documents.ts` | SDK parsing/injection and attachment consumption; unsupported images fail visibly |
| Native interactive client | `metal_infer/chat.m`, `chat_transport.inc` | Separate client/tool execution boundary; not modified in this workstream |
| Gateway / MCP | Not implemented in inspected repository source | External owner must supply repository, registry and client. No local registry invented |
| Responses API | No route in native HTTP dispatch | Unsupported; no Responses conformance claim |
| External executor | Outside generator | SDK call publication is the handoff boundary; fixtures execute no external actions |

## Canonical events and completion

One choice (index 0, or omitted for existing Flash fixtures) is supported. Reasoning is `delta.reasoning_content`, visible text is `delta.content`. Neither channel is reparsed for printable markers. Tool fragments are keyed by `delta.tool_calls[].index`; ID is stable nonempty text; function name/arguments are string fragments. Only function tools are accepted. Arguments must be explicit complete JSON objects, satisfy the advertised schema, and refer to an advertised unique name. Completed calls have unique IDs and are ordered by stream index. The whole batch validates before the first SDK tool callback.

`stop` and `length` can complete ordinary text. `tool_calls` requires at least one validated call; any call fragments paired with `stop`/`length` fail. Tool completion requires both successful finish and `[DONE]`. A later choice event or second finish fails; usage-only events remain allowed after finish and before DONE. Multiple choices fail instead of silently dropping choice 1. JSON/UTF-8 failures, unexpected EOF, upstream error/invalidation and timeout fail the prediction. Partial visible text may already be displayed; no tool callbacks occur on validation failure. Errors are never automatically replayed by the transport.

Usage, when present, requires nonnegative safe-integer prompt/completion/total counts, exact total sum, and cached tokens between zero and logical prompt tokens. This checks internal consistency, not authentic accounting against unseen engine state. Existing native usage tests cover full logical prompt totals on reuse. Usage is not required when the provider omits it.

The adapter adds pinned `jsonschema` 1.5.0 as an explicit dependency (already installed transitively by SDK 1.4.0). Nested required/type/additional-property checks are tested. This does not broaden the native engine's supported schema dialect: native rejects unions such as `anyOf`/`oneOf`, general multi-types, strict schemas and schema-valued additionalProperties. Arbitrary schema-dialect certification is excluded.

## Native controls and identity: observed contract, unresolved API gap

The compiled-source characterization runs the actual HTTP resolution statements, not a Python reimplementation. Observed precedence:

1. `thinking_token_budget` wins over `reasoning_budget_tokens`; null/absent primary permits alias fallback.
2. Numeric budget clamps to `[0,max_gen]`; **zero enables unlimited thinking**, it does not disable thinking.
3. `reasoning_effort="off"` wins over any budget and disables thinking.
4. Without explicit supported controls, existing automatic output/prompt-length policy applies. Short prompts can force thinking off, including resident rendering and DSH profile handling.

`enable_thinking` and effort `none/low/medium/high` are silently ignored in the inspected native handler. The SDK plugin exposes no explicit thinking setting. This violates the desired clear rejection/normalization policy and remains open for Architect coordination in shared `infer.m`. Recommended future contract: retain existing `off`/budget precedence, reject unsupported settings explicitly; decide compatibility before changing established clients. No Qwen template rewrite is proposed.

Native render-only evidence records complete synthetic prompt IDs for direct/announce instructions, each with thinking on/off. Think token IDs are 248068/248069; tool IDs are 248058/248059. The live decode loop transitions on token IDs, not text resembling delimiters. Regex parsing occurs inside captured native tool envelopes. Literal markers *within* nested native argument strings and token provenance through every native delimiter edge remain unqualified. The adapter never has tokenizer provenance and treats all dedicated channel fields as authoritative.

Resident history is exact acknowledged messages plus configuration/endpoint signature. The shipped SDK path is stateless because SDK 1.4.0 has no verified stable chat identity. Tool definitions/config changes rebuild the separately tested scoped helper's identity. Rendered token changes naturally affect prefix matching, but profile/restored-checkpoint cross-products for conflicting controls were not executed in this workstream. Do not infer checkpoint compatibility from adapter tests.

## Native tool semantics requiring coordination

Native output before a tool is supported by existing paired live evidence. Nonwhitespace output after the first tool sets `tool_suffix_nonspace`; native treats answer→tool→answer as invalid rather than losslessly returning the suffix. Default recovery emits assistant rejection text with `stop`, invalidates reuse, and exposes no executable calls; strict mode emits `invalid_tool_call`. This is an inspected limitation, not a newly run forced-generation result. The adapter itself preserves content before/after calls when the provider supplies valid structured fields.

Truncated/incomplete native envelopes cannot become successful calls under the inspected completion checks. Default malformed recovery differs from strict protocol errors; clients must not interpret recovery text as a tool request. No Responses `output_item.done` or `function_call_arguments.done` events exist here. The [llama.cpp reference proposal](https://github.com/ggml-org/llama.cpp/pull/31638) concerns another endpoint and was not copied into this implementation.

## External MCP acceptance contract (not implemented here)

Fixtures in `clients/lmstudio-documents/test/mcp-fixture.cjs` expose two separate localhost JSON-RPC endpoints with identical `serverInfo.name`, differing schemas and two/three tool pages. They also offer duplicate-tool, empty-middle-page, cyclic-cursor, later-error and delayed-page modes. Wire checks validate fixture behavior only. No Gateway under test exists.

Required Gateway behavior: reject duplicate registrations explicitly; never combine one endpoint's schema with another's dispatch URL. Re-registration must replace an immutable endpoint/schema revision atomically. Dispatch must bind to that revision or reject stale calls. Reconnect/unavailability must retain a visibly stale last-good manifest or fail closed.

Discovery must follow every nextCursor, preserve stable page order, reject duplicate tool names per namespace and cursor cycles/invalid cursors, and enforce finite limits (proposed 32 pages, 4096 tools, bounded per-page/total deadlines). Publish only a fully validated catalog. Schema/endpoint changes must advance manifest identity and prompt-cache signature together. Later-page failure must never publish the partial catalog. These are acceptance criteria for the external owner, not implemented or qualified behavior.
