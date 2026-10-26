# Session continuity: client engineering and qualification (2026-10-25)

Experimental branch: `experiment/http-resident-prefix-reuse-20261023`, PR #2.
Starting revision: `0b9a4937f484f3743c8985081e2efa446a7d0b1f`.
**Production rollout: NO-GO; keep PR in draft.**

## Implemented and compiled

### Native terminal

`metal_infer/chat.m` and `chat_transport.inc` now use structured Foundation JSON
for HTTP errors and SSE events, including Unicode, multiline data fields and
literal error-like text. Both successful finish and `[DONE]` are required.
Malformed/truncated JSON, missing headers, missing finish/DONE, oversized data,
wrong response types and incomplete Content-Length bodies cannot commit an
assistant turn. Header bytes, event/response bytes and transcript sizes are
bounded. Loopback connect is bounded to five seconds; socket idle timeout is
120 seconds by default, with a ten-minute response-window check. The latter is
checked between reads and can overshoot by at most an idle-read interval.
SIGINT interrupts the response and clears resident confidence. Chunked transfer
encoding is explicitly rejected by the native direct-engine reader; it supports
the engine's connection-close SSE and complete Content-Length framing. This is
not a general HTTP proxy client. The generator's fetch transport supports normal
HTTP transfer framing, including chunking.

Only explicit parsed invalidation signals authorize one automatic replay. Any
partial content/reasoning, ambiguous disconnect, timeout, generic server error,
failed send or cancellation clears reuse confidence without blind retry. The
next operator request creates a fresh remote UUID from complete successful
canonical local history. An unsuccessful user turn is not saved. Visible partial
terminal text is labelled failed; it is not retracted or committed.

A logical user/assistant exchange is saved with fsync + atomic rename, rather
than two independent appends. A short file lock plus exact prior-history check
rejects a reply generated against a concurrently changed transcript. Invalid,
partial, non-alternating or absent explicitly resumed transcripts fail visibly.
UTF-8 text is decoded by JSON, not substring escapes. Overlong input is rejected
rather than shortened. `/clear` changes both local and remote identities.
`FLASH_CHAT_STATE_DIR` isolates test/operator state without changing HOME.
`FLASH_CHAT_TIMEOUT_MS` permits bounded idle-timeout testing (50..600000 ms).

Legacy textual `<tool_call>` assistant content is preserved byte-for-byte in
JSONL. Operator confirmation is still required before actual shell execution.
Once output exists, it is saved in a pending sidecar before the model follow-up.
Explicit invalidation replays that output, never the command. On ambiguous tool
follow-up failure, `/retry-tool` sends saved output; unrelated input is blocked
until retry or `/clear`. An anchored sidecar detects output already committed
before a crash/cleanup window and refuses duplicate submission. This is not a
claim about surviving power failure between command execution and saving its
output. Structured OpenAI tool calls are explicitly unsupported in the terminal
and fail visibly without execution; the generator supports those calls.

### LM Studio package 0.2.0

The existing Drive generator was copied into `clients/lmstudio-documents/` and
built against the actual installed `@lmstudio/sdk` 1.4.0 declarations. A connected
GitHub search found no existing default-branch package under this account; the
Drive source is preserved in this versioned experimental repository.

The verified SDK `GeneratorController` and `Chat` APIs do not expose stable chat
identity. The shipped generator therefore remains **stateless full-history**.
It does not invent APIs or identify a conversation by SDK object reference,
latest message, filename or matching text. It preserves supported system,
developer, user, assistant/tool-call and ordered tool-result history; the server
accepts developer/system instructions only before conversation messages. Parsed
attachment text stays in canonical messages across every invocation. Remaining
unprocessed files/images fail visibly, rather than being silently omitted.
The conservative serialized-byte input bound remains; no document is truncated.

`resident.ts` is an independently tested adapter for a future caller that can
supply verified scope AND endpoint identity. It checks exact acknowledged
history/configuration, handles ordered pending tool-result IDs, bounds scopes to
128, uses fresh UUIDs for create/replay, rejects concurrent same-scope generation,
clears state on unknown failure, and retries at most once after explicit
invalidation before partial output. It is NOT enabled by the SDK entry point.
Do not claim live LM Studio resident reuse from these adapter tests.

The generator now reads bounded raw SSE with idle/total timeouts and explicit
finish/DONE validation. No SDK implicit HTTP retry occurs. Reasoning fragments
use the verified SDK `reasoningType` option. Parallel tool fragments accumulate
by index. No tool is reported complete until transport completion, a tool-call
finish and all argument JSON have validated. Partial tool/length-limited output
cannot become an executable call. Cancellation aborts upstream; the SDK owns the
cancelled prediction/UI state. Actual GUI behavior still needs validation.

## Evidence and limitations

- Native build: Apple Clang/ARC/Foundation, using project Makefile, no warnings.
- Native deterministic tests: 20 tests PASS, using the actual executable and loopback fault server; see
  `chat-continuity-mock-20261025.{json,log}` for exact current test count/result.
  Covers initial/multiple turns, resume, HTTP/SSE invalidation, one-retry limit,
  manual retry, Unicode, clear, concurrent transcript mutation, truncated frames,
  timeouts, cancellation, size/header limits, legacy tool reconstruction and
  pending-output idempotency.
- Tool-pipeline tests compile `tools/chat_tool_fixture.m`, which replaces popen
  with an in-memory fixture. No test command is executed. Stub count remains one
  across invalidation and interrupted-follow-up/manual retry.
- Generator: TypeScript build and 19 tests passed. Actual SDK Chat objects and
  loopback HTTP exercise forwarding; SDK document parsing is mocked. The tests
  verify safe default stateless forwarding and scoped protocol behavior separately.
- Real LM Studio 0.4.26 build 4 file service: PASS. Synthetic Unicode text was
  prepared and parsed by the actual SDK/file service, then forwarded unchanged
  once in each of two SDK Chat histories. The prediction controller/capture
  endpoint are mocks, so this is not GUI or model-output qualification. Reproduce
  with `node test/live-sdk-documents.cjs --out ../../benchmark-logs/live-sdk-documents.json`.
- Earlier live server 7/7 and restart 5/5 matrices, plus terminal resume/eviction
  tests recorded in the prior report, are retained evidence. Those experiments
  were not needlessly repeated. Updated terminal failure semantics are mock-tested;
  live GUI cancellation/transport presentation remains a manual check.
- No inference/server arithmetic, model weights, warm-state format, selective
  compatibility identity, normal 8K/32K builds or production branch was modified.

### Live paired short results

Two paired rounds ran sequentially on existing experimental server 11243.
Server source checkout `f8235bab67784b938dc26f1d4dbcfa13d561ceba` differs from
starting branch only by later documentation. Binary SHA-256:
`d0bda715533649a2b5039360270e8486c12e8e4e6983029777f9a05df0637dd6`.
Command: `infer-lazy32k-experiment --model MODEL --tiered --serve 11243 --prefill-nrow`.
Production N128 flags; no `--timing`; no second model launched.

| Measure | Resident follow-up | Stateless full history |
| --- | --- | --- |
| Logical context tokens | 69 | 65 |
| Cached-prefix tokens | 44 | 13 |
| Newly prefetched tokens | 25 | 52 |
| Prefill ms, round 0 / 1 | 2533.49 / 1183.57 | 3652.69 / 2623.88 |
| TTFT median [min,max], ms | 1863.85 [1188.06,2539.64] | 3149.75 [2633.41,3666.09] |
| End-to-end median [min,max], ms | 2573.76 [1635.15,3512.37] | 3711.20 [3192.61,4229.80] |
| Decode tok/s, round 0 / 1 | 9.21 / 19.96 | 15.86 / 15.98 |
| Exact answer | ORBIT-73941 | ORBIT-73941 |

The first-run control and resident runs do NOT have identical rendered tokens.
The Qwen renderer drops historical thinking wrappers before the last user query;
resident KV retains its original empty thinking prelude. The observed four-token
difference agrees with this source behavior. Therefore full canonical replay is
not a byte-exact internal-state oracle for resident execution. Repeating the same
create/delta sequence after replacement does reproduce the same short output.
KV/GDN/convolution byte comparisons between those different histories are
**NOT TESTED and cannot be inferred from matching text**. Sampling-temperature
zero output equality is limited to these tested prompts, not a general guarantee.

Pre-run GPU samples were [0,22,0] percent; latency varied substantially. These are
exploratory paired measurements, not uncontended throughput qualification.
The earlier restart/resume timings remain illustrative; no new paired restart
benchmark is claimed. A document-sized two-round paired test also passed; detailed results follow below.

Native memory sample during document work: physical 2,497,539,784 bytes,
process-lifetime physical peak 2,497,556,168 bytes, RSS 7,883,620,352 bytes.
These are existing-server observations, not a before/after allocation attribution.
No model process was started/stopped by this pass. Port 11241 was never queried.

## Exact reproduction

From this experimental checkout (not production):

```sh
make -C metal_infer chat chat-tool-fixture-test
python3 tools/test_chat_continuity.py --out benchmark-logs/chat-continuity-mock.json
cd clients/lmstudio-documents
npm ci --ignore-scripts
npm run build
npm test
```

With the already qualified experimental server running alone on 11243:

```sh
python3 tools/benchmark_session_continuity.py --base http://127.0.0.1:11243/v1 --rounds 2 --out benchmark-logs/session-paired-short.json
python3 tools/benchmark_session_continuity.py --base http://127.0.0.1:11243/v1 --rounds 2 --document-lines 450 --out benchmark-logs/session-paired-document.json
```

Each benchmark invocation is sequential, refuses production port 11241 and
requires three GPU samples below 30% at its start. Later contention is recorded;
it does not justify a production performance claim. Keep source and binary hashes
with results. Fresh source records replay-create latency and total recovery time;
the initial short run recorded replay-follow-up latency only, not complete recovery.

## Remaining Mac-specific checks / rollout blocks

1. Install the 0.2.0 package from its directory with Node 22:
   `npm ci && npm run build && npm test && lms dev --install --yes`.
   This is an explicit operator action; this pass did NOT replace the installed
   LM Studio plugin. Select `flash-ios/openai-compat-documents` and explicitly
   point it to `http://127.0.0.1:11243/v1`. Use synthetic attached text containing
   `DOC-73941`, follow up, cancel, regenerate and verify full attachment retained
   exactly once. Inspect capture-server payloads if needed:
   `node test/capture-server.cjs`. SDK 1.4.0 entry point must remain stateless.
2. Optional human terminal display smoke (automated updated native regression passed), with isolated state:
   ```sh
   continuity_state=$(mktemp -d /tmp/flash-chat-live.XXXXXX)
   printf 'State directory: %s\n' "$continuity_state"
   FLASH_CHAT_STATE_DIR="$continuity_state" ./metal_infer/chat --port 11243 --max-tokens 256
   # After quitting, reuse both that directory and the printed LOCAL session ID:
   FLASH_CHAT_STATE_DIR="$continuity_state" ./metal_infer/chat --port 11243 --max-tokens 256 --resume PRINTED_LOCAL_ID
   ```
   Use synthetic facts, then quit/resume the printed local ID with the SAME state
   directory. For tool tests, never approve a shell command unless explicitly
   intended; automated fixtures exercise the tool pipeline without a shell.
3. Actual UI cancellation/regeneration, actual approved tool executor recovery,
   new-client near-capacity behavior on independent 8K and long-context builds,
   and live LM Studio resident reuse are NOT TESTED here. Resident SDK reuse is
   blocked by absent verified identity, not enabled optimistically.
4. Exact-state parity requires a defined common token transcript and appropriate
   engine state instrumentation. Different canonical/resident renderings cannot
   satisfy an equality claim. No inference-template change was made to hide this.

**Gate status: source/build/mock work is implemented; basic server live tests are
retained; short paired performance is measured. Production merge remains blocked
on the listed live-client gates and unresolved exact-state contract.**

## Completed final live regressions

The updated native executable passed `tools/test_chat_live_continuity.py` against
port 11243. A loopback relay fixed reasoning effort to off while preserving all
session fields and SSE bytes. It checked new/continued requests, external
resident eviction, exactly one automatic replay, fresh-process resume, correct
`ORBIT-73941` recall, and exactly eight alternating JSONL turns. Full replay
contained five messages; resumed creation contained seven. No shell tools ran.
The script starts/stops only its own native client and relay, not the model.
Reproduce after other inference tests have finished:

```sh
python3 tools/test_chat_live_continuity.py --base http://127.0.0.1:11243/v1 --out benchmark-logs/chat-continuity-live.json
```

Document-sized paired measurements completed twice with 7,692 initial prompt
tokens. Resident follow-up context was 7,719 (7,694 cached + 25 prefill), versus
canonical stateless context 7,715 (13 cached + 7,702 prefill). Both returned the
exact identifier; resident replay after replacement returned the same answer.

| Document measure | Resident follow-up | Stateless replay |
| --- | --- | --- |
| Prefill ms, round 0 / 1 | 2630.10 / 2520.33 | 304782.06 / 310513.00 |
| TTFT median [min,max], ms | 2581.60 [2526.64,2636.57] | 307756.76 [304848.09,310665.44] |
| End-to-end median [min,max], ms | 3688.38 [3638.22,3738.54] | 308799.93 [305949.79,311650.07] |
| Decode tok/s, round 0 / 1 | 8.95 / 7.40 | 8.09 / 9.09 |

The large prefill-token reduction is observed directly; the timings remain
exploratory under possible background GPU load and different expert-cache warmth.
No general throughput or all-state equivalence claim is inferred.

### Fresh short recovery pair and final gate summary

A final two-round short run additionally timed explicit complete canonical
recovery with a new session ID. Median end-to-end [min,max] was 1,717.11
[1,550.44,1,883.77] ms for resident continuation; 2,866.21 [2,799.29,2,933.14] ms
for stateless replay; and 2,801.87 [2,791.72,2,812.03] ms for explicit full-history
recovery. Recovery prefilled 52 tokens (65 logical, 13 cached), versus 25 new
resident tokens. Recovery TTFT median was 2,365.58 ms. All answers matched.
These are fresh short pairs, separate from the earlier colder short table.
They measure explicit replay, not a newly repeated server-restart benchmark.

| Final check | Status / evidence |
| --- | --- |
| Native client build | PASS, warning-free in isolated checkout |
| Native transcript/fault suite | PASS, 20 tests including subtest fault matrices |
| Legacy tool pipeline replay | PASS, actual pipeline with compile-time no-shell stub |
| Native live continuation/eviction/resume | PASS, exactly 8 turns and one replay |
| Generator TypeScript build | PASS, SDK 1.4.0 / Node 22.19.0 |
| Generator/transport/scoped-protocol tests | PASS, 19 tests |
| Real LM Studio document parsing and byte forwarding | PASS, local 0.4.26 build 4 service; mock prediction controller |
| LM Studio new GUI package cancellation/regeneration | NOT TESTED |
| LM Studio resident-mode entry point | DISABLED; no verified SDK conversation identity |
| Short and 7,692-token document pairs | PASS, 2 rounds each; exploratory timings |
| Exact canonical/resident KV/GDN/convolution equality | NOT ESTABLISHED; input token streams differ |
| Independent new-client near-limit 8K/32K runs | NOT TESTED; existing engine qualification retained |
| Production branch/binary | UNCHANGED; no request sent to 11241 |

The existing experimental model on 11243 was left running as found. Every client,
mock server, relay and SDK connection started by these tests was closed. No
second inference model, production restart, plugin replacement or shell tool
execution occurred. Full machine-readable data is in
`docs/results/session-continuity-2026-10-25.json` and the Drive result bundle.
