# Canary-02 assessment and missing-case follow-up — November17,2026

Updated November17,2026, America/Los_Angeles. Work A examined the user-run canary-02 rather than rerunning its passed cases. Candidate source remains **e58cc0d95ad9f49d87fe8a5c553e7575e63fbd83**; binary remains **9f6ffea0ea70de6409e51978381968d57df9c2ee158a42bef3a35c063ce08da4**. No runtime change, rebuild, production request, external tool action or production operation.

## Evidence and completed scope

`mask63-live-evidence-2026-11-17.json` binds raw result, server log and telemetry hashes for both runs. Original private reports are unchanged. Canary-02 ran07:12:00–07:12:12PST from the persistent candidate-source checkout, port11248, owned PID52564. GPU[21,22,17],22telemetry samples, minimum host8,322,695,168bytes, peak RSS1,895,809,024bytes, one unchanged process birth identity. Owned cleanup exited-15, operator_cancel. The source/binary IDs, usage sums, cached/logical counts,32KGPU initialization and profile capture were cross-checked.

| Scenario | Actual status/evidence | Scope |
|---|---|---|
| Cold start/health; buffered response |PASS canary02 |Ready07:12:04, prompt27/completion2/total29 |
| Resident follow-up, streamed usage before DONE |PASS canary02 |Logical46=cached29+prefill17; completion2. Harness verified final usage before DONE; raw SSE not preserved |
| Oversize rejection and subsequent resident continuation |PASS canary02 |Original generation32769was clamped32768; with46input it was an oversize request, NOT exactly32769total |
| Exact32768reserved budget |PASS canary02 |27input+32741generation reservation, small actual output; NOT32768prefill |
| Stale409/fresh recovery after short disconnect |PASS canary02 |Disconnect hit final SSE delivery, not proof of early autoregressive interruption |
| Profile capture/checkpoint save |PASS canary02 |11token prefix, Zstd checkpoint saved with checked directory sync |
| Restart/profile restore/exact prefix reuse |PASS missing-live01 |Valid11token snapshot,196,567,040uncompressed bytes, load324ms; source/checkpoint unchanged during tested profile turns |
| Natural EOS + subsequent turn |PASS missing-live01 |READY then OK, each2completion tokens, finish_reason=stop with max32and no stop strings; resident reuse |
| Exact32769total rejection |PASS missing-live01 |27input+32742requested generation;400before new conversation replaces completed resident; its next turn succeeds. No new byte-exact KV/GDN comparison |
| Bounded real N128 prefill |PASS missing-live01 |276logical tokens,11cached,265prefilled: two128row chunks plus9tail, output READY,2completion tokens |
| Complete model tool call + tool-result follow-up |PASS missing-live02 |Exactly echo({"payload":"alpha"}), finish=tool_calls; synthetic result continues resident session and ends naturally |
| Truncated tool output / client invalidation notification |PASS missing-live02 |One-token partial call publishes no executable call; both session_invalidated/resend_full_history=true |
| Long active-decode cancellation / prompt health / stale409 |PASS missing-live02 |Client disconnected inside decode; generation stopped after1token of128budget, health+stale409 completed in64ms |
| Controlled external telemetry loss during decode |PASS missing-live02 |Owned supervisor stops after visible decode,0.528safter first delta; EOF without successful finish/DONE. No real pressure induced |
| Scalar versus N128 visible-output comparison |BLOCKED_RESOURCE scalar-live02 |Scalar started but host reserve fell below6GiBbefore response; no comparison result or numerical mismatch |

## New resource interruption — preserved, not hidden

Missing-live01 started **07:21:46.817524PST**, stopped **07:22:05.377029PST**, owned PID53439 exit-15 after orderly harness cleanup. Two grouped PASS records were saved before the tool request. The native guard logged:

```text
[serve-resource] request aborted reason=2 host_available=6244499456 rss=8114176000; session invalidated
prefill aborted: forward failure after 33/390 tokens
```

Required reserve is6,442,450,944bytes. This demonstrates an actual native prefill resource abort on the frozen diagnostic-free binary, not a decoder defect, synthetic pressure test or successful tool request. The supervisor's stop_reason=operator_cancel reflects subsequent harness cleanup, not the cause of the failed request. The original runner recorded FAIL/“complete tool call missing”; a separate assessment classifies BLOCKED_NATIVE_RESOURCE without editing that failed artifact. The exact HTTP error body was not retained, so no claim is made about its fields or transport status. Client-observed invalidation/continued use after this abort remains untested.

The initial GPU gate was enforced by the retained executed runner, but that version did not save its per-arm values. An earlier independent preflight[17,16,25] is not falsely relabeled as exact launch readings. The future runner now retains per-arm readings, every HTTP request/response privately, and recognizes native as well as supervisor resource stops.

No automatic heavyweight retry occurred. No other application was stopped. Scalar, tool-completion and decode-interruption cases remain pending; the existing numerical256endpoint evidence is not rerun or relabeled as new live state equality. The276token prefill measured11,444ms, but cache/warmup and pressure conditions were not matched to a scalar arm: this is a bounded observation, not a performance comparison or release-latency acceptance.

## Authorized resumed window and remaining scalar-only gate

After the user confirmed “Memory is ready—resume pending tests,” missing-live02 ran the **four unfinished tool/interruption cases only**, retaining earlier passes. N128 server started08:42:13.271944PST and stopped08:43:05.472732PST, exit-15, controlled external telemetry loss. Its102samples remained at/above6,703,333,376host bytes, peak RSS2,064,531,456. All four cases passed and raw HTTP responses are saved privately. The original report is FAIL only because the next scalar arm's GPU prelaunch gate saw[67,15,17]; no scalar model started in that runner.

A scalar-only prelaunch attempt also held at[30,24,24], with no model launch. The test harness was corrected to **wait up to60seconds for three consecutive readings strictly below30%**, without changing the threshold or retrying a running model. The next scalar arm passed[17,26,21] and started **08:46:54.245514PST**. It reached readiness and received the identical276token input but the supervisor stopped it **08:46:59.895117PST**, exit-15, host_reserve. Prelaunch host9,061,318,656bytes fell to6,171,131,904below6,442,450,944; peak RSS1,362,690,048. Client saw EOF before any completed response. This is **not a scalar/N128 numerical mismatch**. No automatic retry followed this actual resource failure.

Only the scalar visible-output comparison remains in the bounded live set. Fresh memory-ready/exclusive-window confirmation is required before the following **NOT RUN** command:

```bash
cd '/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source'
PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 tools/qualify_mask63_scalar_tail.py \
 --out '/Users/knagel/Flash-iOS-Release/2026-11-17/scalar-live-03' \
 --reference-report '/Users/knagel/Flash-iOS-Release/2026-11-17/missing-live-01/result.json' \
 --prior-report '/Users/knagel/Flash-iOS-Release/2026-11-17/scalar-live-02/result.json' \
 --operator-exclusive-model --resource-retry-authorized
```

This does not rerun EOS, profile, tool or interruption tests. It requires explicit renewed resource-window confirmation after the actual stop, threeGPU<30readings, frozen source/binary hashes and unchanged6GiB/16GiBguards. Scalar comparison covers identical input/greedy visible content, finish and usage; production API does not expose hidden/logit/KV tensors. Historical256endpoint tensor evidence remains separately authenticated. No inference arithmetic, tolerances, installed files or production endpoint changed.

Native-only release remains CONDITIONAL: scalar comparison and pre-existing C11-02 recovery-policy/metadata/disaster-independence decisions plus C11-05 performance acceptance remain open. Raw failed reports and GPU holds are retained, not relabeled as overall PASS.
