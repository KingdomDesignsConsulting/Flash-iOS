# C11-01 live admission and resource qualification — November16,2026

This follows the source/build/model-free work in [the resource policy](c11-release-resource-policy-2026-11-16.md). User confirmed an exclusive heavyweight-model window, then requested a90-second pause to compress memory. No model started during that pause. Afterwards, free+inactive availability was13,266,272,256 bytes and GPU readings18/24/19%. This is a correctness/safety exercise, not a performance comparison across memory-cleaning conditions.

## Actual isolated tests

All model executions were sequential on a separately named candidate binary, port11248, with the owned supervisor's6GiB host reserve,16GiB RSS ceiling,300s test lifetime and per-launch GPU gate. A diagnostic-only system-text override isolates startup from installed user prompt configuration; HOME was not changed. All caches/profile files are isolated. Production processes, ports, launchers, user caches, model files, Work B and PR2/3 were not inspected or modified.

| Run | Start / ready / stop PST | Result |
|---|---|---|
|Initial live admission/cancellation|15:12:30 /15:12:34 /15:12:45|PASS|
|Final source-bound run, including controlled resource fault|15:19:42 /15:19:45 /15:20:09|PASS|

The final tested binary SHA256 is **4db5d613f61e04c0ac1854ed9c1ec894f44e38491007ec011c41b1f79b67f7b7**. `docs/results/c11-live-2026-11-16.json` binds all46 runtime source hashes, the actual executable, controller, launch/supervision records and raw-log hash. Earlier binaries and results remain separate; the prior candidate manifest is not claimed to authenticate this new executable.

### Capacity and resident preservation

A real rendered/count-only observer measured logical prompt size. The actual inference request reserved output so prompt+maximum generation equaled32768; it was admitted and naturally completed a short response.32769 was rejected with HTTP400. This does **not** claim a32768-token prefill/generation workload was executed.

After the first turn, resident position was29. Three continuation requests exceeding32768 were rejected. Before/after observers showed the same position29, all ten full-attention KV lengths29 and the same persistent-state hash (covering KV plus recurrent/convolution state). A continuation whose total budget was exactly32768 succeeded. Rejected requests did not destroy the completed conversation.

### Cancellation and resource failure

The client began real decode, received visible content, then reset its socket. The partial session was invalidated, its stale ID returned409, and an explicit fresh request succeeded.

A second test requested enough input to enter real N128 prefill (two completed N128 chunks were observed), then began decode. After visible output, the test armed one **diagnostic-only simulated host-telemetry failure**. The real resource poll latched reason1 and ran the existing checked-forward cleanup. The stream delivered an error with session_invalidated/resend_full_history followed by DONE, with no successful finish. The stale ID returned409 and a fresh request succeeded in the same process. This was not real host-memory exhaustion or a hardware telemetry fault.

No partial tool call was involved or made executable. Failure invalidates the failed turn; it does not roll it back into the preceding resident conversation. The full actual post-recovery state was not independently scalar-replayed in this admission test; the test proves stale-ID rejection and fresh successful recovery. Separate GDN state comparisons remain separately scoped.

The supervisor stopped only the owned model after the driver completed (SIGTERM/operator_cancel, expected exit-15). No resource emergency or monitor failure occurred during the passing live runs. Fatal supervisor termination is a different nonrecoverable path, covered with tiny owned-process tests; it closes the stream rather than fabricating a successful completion and requires a new session after restart.

## Code and test changes

- The admitted-request guard uses existing scalar layer checks and N128 poll callbacks; no arithmetic, routing, template, model weights or checkpoint identity change.
- New `FLASH_SESSION_TEST_SYSTEM_TEXT` and `FLASH_SESSION_TEST_RESOURCE_ARM` hooks compile **only** with state diagnostics. The latter injects one telemetry failure per process when an explicit isolated test file is armed. They are absent from the ordinary build.
- `tools/qualify_c11_live.py` starts/stops only its owned supervisor, contacts only its isolated endpoint after that child reports Ready, and preserves exact results and timestamps. It performs no production listener/process inventory.
- Recompiled native target and its tools/API/warm-state self-tests pass.40 integrated admission cases,20 resource-guard checks,18 extracted actual-source failure/cancellation checks,11 supervisor tests and12 synthetic provenance cases retain their scopes. An ordinary default binary also builds separately and passes its API self-test. No broad numerical oracle or performance cohort was repeated for admission.

Reproduction, only in an operator-confirmed exclusive window and after safeguards pass:

```sh
make -C metal_infer serve-resource-probe release-qualification \
 RELEASE_QUAL_BINARY=infer-c11-live-resource-fault
python3 tools/qualify_c11_live.py \
 --out "$PWD/benchmark-logs/c11-live-$(date +%Y%m%d-%H%M%S)" \
 --operator-exclusive-model
```

Diagnostic hooks do not constitute production fault-injection support. A separately approved diagnostic-free release build still needs its own source/binary fingerprint and bounded deployment smoke checks; no deployment occurred here.

## Disposition

**C11-01: PARTIAL — implementation, model-free tests and focused live verification PASS.** The remaining decision is the Lead Architect's acceptance of the documented supported launch envelope: supervised/cooperating single-model launch, sampled rather than reserved memory, sticky request invalidation, and hard-stop/restart behavior for stalls or monitor failure. Work does not invent that final release-policy acceptance. Engineering evidence is ready for that decision; no additional broad benchmark is proposed.

C11-02 remains OPEN. No synthetic manifest, successful live candidate test or operating-window confirmation verifies actual production ownership, backups or rollback. Those require separately authorized operator work. No merge, canary or deployment authorization is implied.
