# Flash-iOS document generator for LM Studio

This LM Studio plugin sends attached documents with the user message to Flash-iOS's OpenAI-compatible chat endpoint. It uses the LM Studio prompt preprocessor to parse each non-image attachment, inserts the filename and extracted text in the message, and consumes the file handle so history does not inject it twice.

## Install

From this directory, with Node.js 22 and LM Studio installed:

```sh
npm ci
npm run build
npm test
lms dev --install --yes
```

Select `flash-ios/openai-compat-documents` in LM Studio. Set the model ID to `qwen3.5` and the Base URL to `http://127.0.0.1:11243/v1`. To inspect outbound JSON, run `node test/capture-server.cjs` and temporarily use `http://127.0.0.1:11242/v1`.

The plugin was built against LM Studio SDK 1.4.0. It uses the SDK document parser for text, PDF, and Word attachments. Parser failures and empty or overlong extracted text produce visible errors; the attachment is not consumed on those failures. Unprocessed attachments and images fail visibly; the text endpoint never silently drops them.

## Context and cancellation

The generator assumes Flash-iOS's qualified 32K context. It reserves the configured output tokens plus 2,048 tokens for chat framing and rejects a request if serialized messages and tool definitions exceed the remaining budget **in UTF-8 bytes**. This deliberately overestimates prompt tokens. It does not silently truncate a document. This is a safety bound, not exact Qwen token accounting.

LM Studio's cancel action aborts the upstream HTTP stream. The request has a ten-minute total deadline, a two-minute stream-idle deadline, and explicit response/event limits. Engine SSE keepalives reset the idle timer. No implicit transport retries occur.

## Version 0.2.0 — experimental qualification

Node 22 / SDK 1.4.0. The shipped entry point is deliberately **stateless**.
The SDK's `GeneratorController` and `Chat` have no documented stable conversation
ID. Every invocation forwards full authoritative history, including injected
attachment text and structured tool calls/results. No SDK object identity,
filename, latest text, or user-configured shared ID is used as a chat identity.
Edits, regeneration, plugin restarts and configuration changes therefore cannot
reuse a stale resident session.

`src/resident.ts` implements a separately tested bounded resident adapter for
callers that can supply a VERIFIED stable scope and endpoint identity. It is
NOT wired to guessed identities in the LM Studio entry point. It compares exact
acknowledged history/configuration, checks pending tool-result IDs/order, creates
opaque UUIDs, replays at most once after explicit invalidation, and never retries
ambiguous failures or invalidation after partial output. Do not enable this path
until an SDK identity contract is available and live-qualified.

Raw SSE parsing requires both successful finish and `[DONE]`. Partial content may
have appeared in the UI when a later error occurs, but the generator throws and
cannot claim a completed prediction. Cancellation aborts the upstream request;
SDK owns the cancelled UI state. Tool calls are assembled by stream index and
are not published as completed until transport and all argument JSON validate.
A length-limited/incomplete tool finish never becomes executable.

Automated tests cover document extraction, actual SDK Chat forwarding, literal
UTF-8 bytes, HTTP/SSE invalidation, truncated/malformed streams, timeouts, scoped
replay/isolation, ordered tool results, partial-error retry prevention and SDK
cancellation. Run `npm run build && npm test` for exact current counts.

The earlier 0.1.1 package was UI-tested with a 9,789-character attachment and
follow-up history. That historical result does NOT qualify this 0.2.0 UI release.
New live LM Studio installation, attachment rendering, regeneration, UI cancel,
and subsequent history must still be checked manually against port 11243.

For that remaining check: install with the commands above, select
`flash-ios/openai-compat-documents`, explicitly select the experimental URL,
attach a synthetic text file containing `DOC-73941`, ask for the identifier,
continue the chat, cancel a long response, then regenerate and check that the
file contents remain available exactly once. Use the capture server for outbound
byte inspection. This package does not start/stop an inference server.
