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
The opt-in build records bounded (512-token) actual completed prefill/decode
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


## Corrective revision and executed regressions

The unconditional startup upload of inactive CPU linear state has been removed.
The completed GPU prefix is now preserved and snapshotted directly. No Qwen
rendering, tokenization, sampler, attention kernel or model weight changes were
made. The CPU-linear path was already excluded from that upload.

`WARM_STATE_EXECUTION_VERSION` advances from 2 to 3 because lifecycle state can
change; old potentially affected persistent states must fail compatibility.
The explicit selective compatibility contract remains intact. Executable hashing
stays disabled; unrelated future rebuilds do not invalidate states. Existing
cache files are not deleted.

The suspected adjacent tool-reset omission was investigated and **not found**:
new tool requests fold the configured system into an explicit system block before
reset selection. The existing explicit-system reset correctly covers that case;
no speculative reset patch was applied.

| Actual case | Effective completed tokens | Result |
| --- | ---: | --- |
| Pre-fix cached default prefix | divergence at 13 | FAIL, reproduced twice |
| Repaired cached default + resident follow-up | 73 | Exact component fingerprints PASS |
| Explicit system + resident follow-up | 71 | Exact component fingerprints PASS |
| Tool schema + resident follow-up | 415 | Exact component fingerprints PASS |
| Thinking budget 1 | 77 | Exact component fingerprints PASS; 15 sample/forward substitutions |
| One-token limit + continuation without EOS | 66 | Exact component fingerprints PASS |
| Two tool conversations, dynamic prefix restore | 415 each | Exact fingerprints PASS, restored 355 tokens |
| Canonical full replay and explicit recreation | 69 each | Identical tokens/answers; exact fingerprints PASS |

All checked full-attention K/V lengths match the logical position on all ten
full-attention layers, not merely layers 3/7/11. CPU and GPU K/V plus all 30
linear recurrent/convolution components are fingerprinted independently. No
nonfinite values were observed. Request-boundary fingerprints are unchanged.
The 415-token case required raising the diagnostic-only limit from 256 to 512;
the first oversized attempt was stopped and is not counted as a pass.

Layer-0 GPU GDN localization at completed position 13 used 524,288 float32
values: pre-fix actual state was entirely zero; the uninterrupted reference had
14,336 zeros. There were 509,952 differing elements, max absolute error
13.947830200195312 and RMS error 0.1325950803352789, with no nonfinite values.
All 60 GPU GDN/conv components across 30 layers changed during the destructive
upload; full-attention K/V components did not. Before that upload, the startup
state matched control. After removing it, startup state and subsequent resident
execution match control.

Six model-free trace regressions pass. In addition to nonce-based collection,
the older four-path HTTP harness now actually sends its trace nonce; the
regression intercepts the outgoing request. Effective-history comparison includes
cached prefix tokens on both resident and canonical sides. Thinking traces record
raw samples separately from successful forwarded/completed token IDs. The
one-token-limit behavioral identifier check is deliberately false: a one-token
reply cannot return the whole identifier. That is not relabelled as a behavior
pass; the state comparison passes independently.

## Scope of the conclusion

The repaired **short scalar-prefill** path establishes exact SHA256 fingerprint
equality of the instrumented persistent components for identical effective IDs
and positions. This is stronger than matching text; it is not a full-memory
memcmp proof. GPU fences precede fingerprints, active tensor extents exclude
padding, and even inactive CPU shadows are compared. Intermediate scratch hidden
vectors/logits and unused GPU allocation padding are not fingerprinted. Hashing
and fencing add substantial overhead, so these timings are diagnostic and cannot
be used to claim a serving-performance improvement.

N128/batched prefill is deliberately disabled for these experiments; batch steps
are labelled incomplete rather than fabricated as per-token observations.
Long context, production readiness, cancellation/error rollback state equivalence,
persistent disk restore, and CPU-linear mode equivalence are NOT ESTABLISHED by
this matrix. Existing client functional tests are not repeated or converted into
persistent-state claims. Dynamic RAM prefix restore and canonical/recreation results are recorded below.
Production is neither changed nor merged.

Private root: `Testing/HTTP-Prefix-Reuse/2026-10-27-state-equivalence/`.
Each run preserves commands, source/binary hashes, request-correlated prompt and
generation traces, per-position component fingerprints, logs, replay input and
structured result. Environment metadata records the M4, OS, model metadata hashes
and greedy configuration. Raw tokens and targeted float dumps stay private.

Additional bounded cases:

```sh
python3 tools/run_session_state_mission.py --case explicit --out /ABSOLUTE/PRIVATE/FRESH-EXPLICIT
python3 tools/run_session_state_mission.py --case thinking --out /ABSOLUTE/PRIVATE/FRESH-THINKING
python3 tools/run_session_state_mission.py --case length --out /ABSOLUTE/PRIVATE/FRESH-LENGTH
python3 tools/run_session_state_mission.py --case warmtools --out /ABSOLUTE/PRIVATE/FRESH-CACHE
python3 tools/run_session_state_mission.py --case canonical --out /ABSOLUTE/PRIVATE/FRESH-REPLAY
```

Every model launch requires three GPU readings below 30%. A rejected gate means
NOT RUN, not model failure. Servers are isolated on 11243 and stopped between
HTTP and continuous control. The runner never changes production port 11241.


## Final executed result and architectural interpretation

Corrective commit: `dc77d12c7691958750ff7cbbf8f635d7e29a262a`.
Diagnostic pre-fix baseline: `9e5f30813700d738b5dcc33fee0986c7169a9896`.

Dynamic-cache regression ran two independent conversations in one server. The
first processed a 381-token prompt from zero. The second restored the existing
355-token tool prefix and processed 26 new prompt tokens. Both completed their
first turn at 383 and their resident continuation at 415. Every overlapping
fingerprint and the uninterrupted exact-token control matched. This tests RAM
prefix restoration, not process-restart/disk checkpoint restoration.

Canonical full-history replay and explicit resident recreation independently
completed at 69. Their token histories, answers, and all overlapping persistent
fingerprints were identical; their exact-token continuous control also passed.
The canonical prompt had 61 effective tokens, compared with 65 for the resident
prompt at the corresponding turn. The common prefix is 35 tokens; the only
difference is deletion of four tokens representing the empty thinking wrapper
`<think>`, two newlines, `</think>`, two newlines. Canonical reconstruction from
visible assistant content omits it. Neither sequence is normalized or rewritten
for qualification. Each reaches the correct state for **its own** effective IDs;
state identity across those different sequences is not the protocol guarantee.

| Qualification property | Evidence / verdict |
| --- | --- |
| Exact completed effective history including cached base | PASS on bounded runs |
| Sampled versus forwarded trace lifecycle | PASS, 15 thinking substitutions observed |
| Persistent K/V, GDN, convolution at matched positions | Exact fingerprints PASS on repaired short scalar cases |
| EOS and request-boundary continuity | PASS |
| Length-truncated continuation | PASS for state; identifier behavior intentionally token-limited |
| Dynamic prefix capture/restore | PASS, 355-token restore |
| Canonical versus recreated history/state | PASS |
| Resident versus canonical effective IDs | DIFFERENT by the four-token empty wrapper; expected and preserved |
| Cancellation/error rollback state equality | NOT ESTABLISHED by this instrumentation |
| Persistent disk checkpoint restore | NOT RUN in this mission |
| N128 / long context / CPU-linear state equality | NOT ESTABLISHED |
| Production performance/readiness | NOT ESTABLISHED; no production merge |

Last experimental server stopped at **2026-10-27 01:59:34 -07:00**. Final
continuous replay exited 0 at **01:59:44 -07:00**. Port 11243 was checked free
subsequently. GPU-gated attempts launched no model and are retained separately.
The GPU preflight now permits up to ten readings, requiring three consecutive
readings below 30% before launch; it records NOT RUN if that cannot be obtained.
No inference test was rerun to relax a failed correctness assertion.

**Verdict: confirmed startup state corruption repaired; short matched-token
resident-state equivalence qualified for the tested scalar GPU path.** Next
architectural gates are N128 and long-context matched-state comparisons, plus
cancellation/error and persistent-disk restoration comparisons. These should
precede production promotion. Do not modify the Qwen template to conceal the
canonical/resident wrapper distinction.
