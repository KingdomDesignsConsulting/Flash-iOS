# Resident state equivalence investigation — 2026-10-27

Branch `experiment/http-resident-prefix-reuse-20261023`; starting HEAD
`dacd5b9b2f27eac8f63441737c67bd6912f960f1`. Production remains protected.
The Qwen template is deliberately unchanged. Actual token traces and model-state
float dumps are PRIVATE under `Testing/HTTP-Prefix-Reuse/2026-10-27-state-equivalence/`.

## Diagnostic baseline (before corrective changes)

Four model-free collector regressions pass: unique request correlation, delayed
post-response generated-trace publication, stale trace rejection and restart
filename overwrite compatibility. New callers supply a UUID trace identity;
prompt/generated/state traces must agree with the running server PID. A startup
manifest is required before inference. Old mixed-run files are not trusted.

A separate `make -C metal_infer session-state-experiment` target builds
`infer-session-state-experiment`; normal/default executables are not overwritten.
The opt-in build records bounded (256-token) actual completed prefill/decode
histories, including the cached system prefix, per-position KV lengths, active
float32 component SHA256 and nonfinite counts. GPU command completion is fenced
before reading state. CPU and GPU K/V plus recurrent/convolution state are
fingerprinted separately; active GPU geometry excludes allocation padding.
No conversation snapshot pool or full-state disk checkpoint is added.

The controlled sequence is collected through real HTTP resident requests. That
server is stopped before a separate process executes the exact same token IDs
and positions uninterrupted from zero using the normal forward function. The
control completes each forward, does not sample substitute tokens, and stops at
the earliest fingerprint mismatch. No tolerance is relaxed to obtain a pass.

### Executed cycles so far

1. Existing trace paths resolve to the same Drive directory, but request counter
   reuse had overwritten earlier records. Generated traces are published after
   response delivery and must be polled independently. Effective-history
   reconstruction also omitted the 13 cached system tokens. Collection and
   actual-history instrumentation corrected these diagnostic limitations.
2. Initial controlled launch hit a shutdown/port-release race and aborted before
   any model launch or inference. Bounded repeated port-release checks fixed the
   harness; the failed attempt remains labelled infrastructure-only.
3. First matched-token run: DIVERGENCE at position 13, before the first user token.
   Before the startup CPU-to-GPU synchronization, all component fingerprints
   matched uninterrupted control. Afterwards, GPU GDN and convolution differed
   across all 30 linear layers; all full-attention KV fingerprints still matched.
4. Targeted reproduction confirmed the entire active layer-0 GPU GDN tensor was
   zeroed. Only that one component was dumped on each path, rather than writing
   a large checkpoint. Raw dumps and numerical comparisons remain private.

The normal GPU path advances authoritative GPU state during system warmup. The
unconditional CPU-to-GPU copy afterwards overwrites it with inactive/stale CPU
state. This is a lifecycle bug, not a Qwen wrapper or kernel arithmetic issue.
Per the escalation rule, unrelated categories are deferred until this earliest
state divergence is corrected and the same experiment passes.

## Commands

```sh
make -C metal_infer session-state-experiment
python3 tools/test_session_trace_collection.py
python3 tools/run_session_state_mission.py --case implicit --out /ABSOLUTE/PRIVATE/FRESH-RUN
```

The runner requires isolated 11243 to be free. If intentionally replacing its
existing experimental process, supply `--replace-pid PID`; it verifies ownership
of 11243 before sending SIGTERM. It never touches 11241, overlaps model instances,
or automatically SIGKILLs an unresponsive process. All starts/stops are timestamped.
For targeted localization add `--dump-component gpu_gdn:0 --dump-position 13`.
Private artifacts contain synthetic prompt tokens and must not be committed to
public GitHub. The source tree and build/binary hashes accompany the evidence.

**Current verdict: state equivalence FAIL on the pre-fix startup transition.
Production merge remains blocked.** Corrective and regression results follow in
subsequent commits; this revision preserves a reproducible pre-fix baseline.
