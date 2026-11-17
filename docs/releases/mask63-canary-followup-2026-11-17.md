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
| Complete model tool call + tool-result follow-up |BLOCKED_NATIVE_RESOURCE |Tool request390tokens aborted at33during prefill; no completed tool was returned |
| Truncated tool output / client invalidation notification |NOT RUN |Stopped before this case |
| Long active-decode cancellation / prompt health / stale409 |NOT RUN |Distinct from short final-delivery case |
| Controlled external telemetry loss during decode |NOT RUN |Native pressure interruption observed in prefill is not this test |
| Scalar versus N128 visible-output comparison |NOT RUN |Scalar arm never started; historical tensor qualification remains separate |

## New resource interruption — preserved, not hidden

Missing-live01 started **07:21:46.817524PST**, stopped **07:22:05.377029PST**, owned PID53439 exit-15 after orderly harness cleanup. Two grouped PASS records were saved before the tool request. The native guard logged:

```text
[serve-resource] request aborted reason=2 host_available=6244499456 rss=8114176000; session invalidated
prefill aborted: forward failure after 33/390 tokens
```

Required reserve is6,442,450,944bytes. This demonstrates an actual native prefill resource abort on the frozen diagnostic-free binary, not a decoder defect, synthetic pressure test or successful tool request. The supervisor's stop_reason=operator_cancel reflects subsequent harness cleanup, not the cause of the failed request. The original runner recorded FAIL/“complete tool call missing”; a separate assessment classifies BLOCKED_NATIVE_RESOURCE without editing that failed artifact. The exact HTTP error body was not retained, so no claim is made about its fields or transport status. Client-observed invalidation/continued use after this abort remains untested.

The initial GPU gate was enforced by the retained executed runner, but that version did not save its per-arm values. An earlier independent preflight[17,16,25] is not falsely relabeled as exact launch readings. The future runner now retains per-arm readings, every HTTP request/response privately, and recognizes native as well as supervisor resource stops.

No automatic heavyweight retry occurred. No other application was stopped. Scalar, tool-completion and decode-interruption cases remain pending; the existing numerical256endpoint evidence is not rerun or relabeled as new live state equality. The276token prefill measured11,444ms, but cache/warmup and pressure conditions were not matched to a scalar arm: this is a bounded observation, not a performance comparison or release-latency acceptance.

## Resume only unfinished cases

After restoring host capacity and reconfirming an exclusive model window, use a fresh output directory. **NOT RUN:**

```bash
cd '/Users/knagel/Flash-iOS-Release/2026-11-17/candidate-source'
PYTHONPYCACHEPREFIX=/private/tmp/mask63-pycache python3 tools/qualify_mask63_missing.py \
 --out '/Users/knagel/Flash-iOS-Release/2026-11-17/missing-live-02' \
 --resume-report '/Users/knagel/Flash-iOS-Release/2026-11-17/missing-live-01/result.json' \
 --operator-exclusive-model
```

This retains the successful EOS/profile/exact-rejection and276token N128 reference, then runs only unfinished tool, partial-call, long-decode cancellation, controlled external loss and scalar-output comparison cases. Two sequential owned processes, port11249,600slimit each; no production. It verifies binary and47runtime hashes, threeGPU<30readings and native/external6GiB/16GiB safeguards. Real resource failure aborts the sequence. Controlled external telemetry loss, if reached, is explicitly distinguished from real host pressure before the planned scalar process. No native diagnostic fault arm is enabled.

Scalar/target comparison is same-input greedy visible content/usage only: it cannot expose hidden/logit/KV tensors in the production binary. Full tensor numerical evidence remains the authenticated historical source-equivalent qualification. Do not change arithmetic/tolerances or rebuild the candidate to force these API scenarios through.

Native-only release remains CONDITIONAL. C11-02 recovery-policy/metadata/disaster-independence gates and C11-05 performance acceptance remain open and were not waived by this follow-up.
