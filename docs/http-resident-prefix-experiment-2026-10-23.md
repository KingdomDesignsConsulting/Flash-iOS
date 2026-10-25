# Flash-iOS HTTP resident-session continuity — experiment status (2026-10-25)

**Branch:** `experiment/http-resident-prefix-reuse-20261023`  
**Production:** unchanged. Draft [PR #2](https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/2) remains unmerged.  
**Verdict:** server-side live functional tests PASS for the tested cases; client integration and deeper correctness qualification remain open. **Do not merge yet.**

## Motivation and original defect

Flash-iOS can retain inference state for an active resident session, allowing the next turn to prefill only newly submitted tokens rather than replaying the entire conversation. The original HTTP server could accept an unknown or evicted `session_id` as a fresh conversation without explicitly notifying the client. A single-turn client could therefore silently lose prior history. Separately, the terminal client `chat.m` displays saved `--resume` transcripts without replaying them into a newly started server.

## Implemented experimental server behavior

- A request that names a **new** resident `session_id` must explicitly set `"flash_session_create": true`; requests without `session_id` remain stateless.
- Continuing a matching active session uses its saved resident context.
- An unknown, evicted or post-restart session ID without the creation flag is rejected with `session_invalidated:true` and `resend_full_history:true`.
- Non-streaming stale-session requests receive HTTP **409 Conflict**.
- Streaming stale-session requests receive valid **HTTP SSE response headers first**, then an explicit invalidation SSE event. The initial live test exposed a missing-header `BadStatusLine` defect, fixed at commit `f6ccd9c`.
- Creating a resident session over an already-active matching session ID is rejected to avoid inadvertent replacement.

These are **experimental breaking protocol changes** for session-aware clients; clients must be updated before production rollout.

## Live tests performed on the Mac mini M4

### Resident continuation versus full-history control (2026-10-23)

The early short-context probe observed 31 new prefill tokens and 2,725.6 ms for active continuation, versus 105 new prefill tokens and 9,891.6 ms for the full-history stateless control. Exact generated-text match observed. This is roughly 70.5% fewer new prefill tokens and 72.4% less prefill time in that specific test, **not** an all-layer state-equivalence proof.

### Deliberate eviction (2026-10-24)

An experimental session A remembered a unique code. Creating session B evicted A. Before the mandatory server guard, stale A could silently lose context. After the patch, the live non-streaming probe verified:

- Initial A: HTTP 200.
- Replacement B: HTTP 200.
- Stale A continuation: **HTTP 409** with `session_invalidated:true`, `resend_full_history:true`; approximately 1 ms.
- Stateless full-history recovery reproduced the original code `AXIOM-167CA515F8DA`.
- `unsafe_silent_loss_observed:false`.

### Active-session and streaming matrix (2026-10-25)

`tools/experiment_http_live_session_matrix.py` passed **7/7** live checks:
`create_a_200`, `active_session_reused`, `active_session_retains_code`,
`create_b_200`, `stale_nonstream_409_signal`,
`stale_stream_explicit_signal`, `stateless_replay_recovers_code`.

The first streaming run failed with Python `http.client.BadStatusLine` because server-side early stale-session rejection emitted `data:` before the HTTP response headers. Commit `f6ccd9c` corrected this. The repeated live matrix then passed all seven checks.

### Restart and safe recovery (2026-10-25)

`tools/experiment_http_restart_recovery.py` passed **5/5** live checks:
`initial_created`, `prior_session_reused`, `prior_context_retained`,
`stale_after_restart_rejected`, `new_session_replay_recovers_code`.

Before restart: active continuation reused 70 cached-prefix tokens, prefilled 26 new tokens in 2,981.1 ms, and recovered the exact `RESTART-82E103CE2403` identifier. After restart: stale ID received HTTP 409 with explicit invalidation/replay flags. Complete-history replay under a new ID succeeded (79 new prefill tokens, 10,121.3 ms). These are illustrative timings rather than a matched throughput benchmark.

## Regression scripts and results

Committed tests on this experimental branch:
- `tools/experiment_http_resident_prefix.py`
- `tools/experiment_http_session_eviction.py`
- `tools/experiment_http_live_session_matrix.py`
- `tools/experiment_http_restart_recovery.py`

Result files from the user's Mac are stored separately in the Google Drive-synchronized `Flash-iOS/Testing/HTTP-Prefix-Reuse/` directory, including `2026-10-24/session-eviction-result.json`, `2026-10-24/live-session-matrix-result.json` and `2026-10-24/restart-recovery-result.json`. The remote GitHub repository backs up the source and scripts; the test outputs are not asserted to be committed in Git.

## Outstanding blockers — do not merge

1. **Terminal client `metal_infer/chat.m`:** currently sends only the latest user turn; does not request new resident-session creation using `flash_session_create`; lacks explicit SSE invalidation detection and automatic full-transcript replay; `--resume` displays history without reconstructing server-side context. This is pre-existing audit issue F32K-01 and related stream error-handling issue F32K-02.
2. **LM Studio generator:** must be upgraded to maintain proper conversation IDs, safely create sessions, distinguish full history from incremental continuation, detect invalidation and replay all prior turns exactly. Do not enable incremental mode until client behavior is qualified.
3. **More qualification:** interrupted/cancelled generation, streaming recovery, profile/tool-context changes, session replacement across clients, token-rendering parity and exact KV/GDN/convolution state equivalence. Matching text is not sufficient proof of identical internal state.
4. **Mac runtime:** verify any additional changes by building in an isolated checkout and running the appropriate integration tests; preserve existing production binaries/cache format and 8K-default behavior.

## Disposition

**Server correctness for tested resident-session eviction, continuation, streaming invalidation, restart and recovery: PASS. Production rollout: BLOCKED pending client implementation and additional qualification.**

This page supersedes the initial 2026-10-23 experiment plan, which incorrectly remained marked "not yet run" after the tests completed.


## Experimental terminal client implementation (2026-10-25)

`metal_infer/chat.m` now includes a source-level implementation of
session creation and recovery, committed after the server live-test matrix:

- Creates a fresh remote resident-session ID for each terminal client process.
  The persistent local JSONL session ID is deliberately separate. The first
  prompt sends `flash_session_create:true` along with complete local transcript
  and the pending user turn. This also protects `--resume` after a restart.
- A successful subsequent turn normally transmits only the new turn with its
  active server session ID.
- On HTTP 409 or streamed `session_invalidated` / `resend_full_history`,
  it generates a new remote session ID and replays the complete validated
  local JSONL transcript plus pending message. Only one automatic retry
  is permitted.
- Pending user/assistant turns are saved only after a completed SSE response.
  Corrupt JSONL transcript blocks replay rather than silently discarding history.
- Tool follow-up output is preserved as a user turn only after successful model
  response, and is replayed without rerunning the command.

**Qualification status: SOURCE IMPLEMENTED, NOT YET COMPILED OR LIVE-TESTED
ON THE USER'S MAC.** This client patch is on the experimental branch only.
The parser is still a lightweight TUI/SSE implementation; cancellation,
SSE end-of-stream truncation, JSON Unicode handling, and tool transcript parity
need live tests. The LM Studio generator remains a separate client to update.
No production merge until client build and end-to-end tests pass.

Isolated qualification:
```sh
cd "/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS"
git fetch origin experiment/http-resident-prefix-reuse-20261023
git -C ../Flash-iOS-session-test checkout --detach origin/experiment/http-resident-prefix-reuse-20261023
make -C ../Flash-iOS-session-test/metal_infer chat
../Flash-iOS-session-test/metal_infer/chat --port 11243
```

Run `--resume <local-session-id>` after restarting the TUI; check that it
retains a unique prior factual identifier without sending only the last turn.
Evict the active server-side ID using a separate test client and verify the next
TUI turn detects invalidation, replays complete history, and recovers the exact
identifier. Save build and test logs beneath `Flash-iOS/Testing/HTTP-Prefix-Reuse/`.

### chat.m Mac compile result (2026-10-25)

The user compiled `make -C ../Flash-iOS-session-test/metal_infer chat`
from commit `fb746cb` successfully using Apple Clang with ARC. It emitted
three non-fatal warnings: two for the pre-existing `MdState` aggregate
initializer and one for an unused `t_start` variable. Follow-up commit
`dead7a9` uses a designated initializer and the actual request-start clock
to report TTFT, addressing these warnings. This follow-up commit is **not yet
compiled or live-tested on the user's Mac**. No production changes.

Next live client check: with hardened server on port 11243, launch the isolated
`chat --port 11243`, provide an identifier, ask it back in a second turn,
quit, relaunch with `--resume <local-id>`, ask it again, then evict its active
resident session using a distinct session-creation request and verify automatic
replay. Preserve isolated logs in `Testing/HTTP-Prefix-Reuse/`.
