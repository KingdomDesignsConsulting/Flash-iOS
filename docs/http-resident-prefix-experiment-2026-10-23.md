# HTTP resident-prefix reuse — isolated experiment (2026-10-23)

**Status:** implemented, **not yet run on the user's Mac**. Branch `experiment/http-resident-prefix-reuse-20261023`. Production left untouched.

## Why

The current HTTP server caches the exact system/tools prefix but only supports full
conversation reuse when the client provides an active `session_id` and sends a
**single new user turn**. LM Studio's generator currently sends full history;
therefore successive attached-document requests re-prefill ~5K tokens at ~21 tok/s.
Never assume a session survives restart, replacement, cancellation, or another
stateless client. The bundled `chat.m` resume problem (audit F32K-01) is a
warning about this behavior.

## Test

```sh
cd "/Users/Shared/Main Hard Drive/AI Storage/Apps/Flash-iOS"
git fetch origin experiment/http-resident-prefix-reuse-20261023
git show origin/experiment/http-resident-prefix-reuse-20261023:tools/experiment_http_resident_prefix.py > /tmp/experiment_http_resident_prefix.py
python3 /tmp/experiment_http_resident_prefix.py --base http://127.0.0.1:11241/v1 > ~/prefix-reuse-probe.json
cat ~/prefix-reuse-probe.json
```

**Run against a disposable server on a dedicated port if possible**: the test will
replace the server's active resident session. Do not run alongside LM Studio's active
chat on the same server. No model or cache files are deliberately modified.

Optional document test:
```sh
python3 /tmp/experiment_http_resident_prefix.py --base http://127.0.0.1:11241/v1 --context-file /path/to/crash.log > ~/prefix-reuse-document-probe.json
```

The probe first establishes a uniquely named resident session. It then sends
**only** one follow-up question with the same session ID, and finally sends a
stateless full-history control with the first assistant reply embedded.
Output includes both responses, `flash_timings`, token usage, duration and
comparison. Exit 2 means content mismatch; exit 3 means no prefill saving.

## Acceptance gates

1. Identical generated text on the resident continuation versus the stateless
   full-history control, with deterministic decoding and identical reasoning policy.
2. Continued response prefill is dramatically smaller than the control (ideally
   <100 tokens for the short test); record actual `prefill_tokens`.
3. No unintended session mixing after a replacement, restart, or abort. **Not yet
   tested** by this first probe.
4. Same continuation answer and hybrid state equivalence (KV, GDN, convolution)
   in a later qualified build; mere identical text is not sufficient for promotion.
5. Repeat with attached crash log after the short test to measure user-visible gain.

## Critical caveat

Source inspection showed that when an unrecognized `session_id` arrives, the
server can process the single user turn as a **new** conversation, rather than
always returning `resend_full_history`. A production generator must never assume
an unchanged ID proves the server retained history. Before enabling automatic
LM Studio continuation, add a robust validated epoch/ack or exact-history
checkpoint mechanism and a safe replay protocol, or modify server to reject
unknown continuation IDs explicitly. A request/response failure only fallback
does not catch **silent** context loss.

## Next engineering stage (not implemented by this probe)

Build opt-in server-side full-history token-LCP resume with exact position/
rendering checks and a safe turn-boundary snapshot, or a continuity handshake
with server-issued generation IDs. Validate failure, cancellation, eviction,
model/thinking/tool-context mismatch, replay and transcript parity. Leave
production default 8K and qualified lazy32K binaries untouched.
