# Flash-iOS — Architect disposition and remaining engineering gates (2026-10-28)

**Status:** Experimental evidence accepted within declared scope; **production NO-GO**. PR #2 remains draft and unmerged. No Qwen-template or inference-kernel change is authorized by this disposition.

## Verified evidence and decisions

- **Resident short scalar GPU:** Matched effective-token, position and active persistent component SHA256 comparisons PASS on seven bounded cases after startup GPU-state repair `dc77d12c`. This is component fingerprint equivalence, not whole-allocation memcmp. See `docs/resident-state-equivalence-2026-10-27.md`.
- **N128 short bounded GPU:** Numerical PASS within *pre-existing* tolerances (state max abs <1e-3, hidden <=1e-3, logits <=1e-2), same greedy tokens, finite state, exact KV lengths/mirrors. Worst observed state `2.60353088e-4`, hidden `2.28881836e-5`, logits `9.48905945e-5`. The native N128 candidate fingerprints reproduce observed resident HTTP fingerprints exactly at measured endpoints; N128 is not bit-exact against scalar. No intermediate within-slab full-model states were measured or inferred. See `docs/n128-resident-state-qualification-2026-10-27.md`.
- **Lifecycle:** Actual TCP reset during partial slab and decode invalidates the interrupted session; HTTP 409 rejects reuse and exact fresh recovery PASS. It does not promise preservation of the interrupted turn.
- **Warm state:** Native Zstd checkpoint process-exit/reload at prefix 141 plus 64 subsequent positions PASS exact fingerprint reproduction, wrong-prefix and opposite execution-mode rejection PASS. Named-profile *HTTP* restart path is not thereby qualified.
- **Selective compatibility:** `dc77d12c` raises execution version to 3 after correcting GPU prefix state. `0b49e08` includes runtime N128 versus scalar mode in selective compatibility identity; full-executable hashing remains disabled and no format bump is implied. These changes are accepted for experimental qualification.
- **Four-token Qwen thinking wrapper:** Canonical visible-content reconstruction omits empty wrapper retained in resident history. Each history is correct for its own effective tokens; do not normalize the template to manufacture equivalence.
- Prior GUI Regenerate control was not available in inspected LM Studio GUI. This is closed as unsupported UI, **not** a claim that all other GUI delivery tests passed.

## Engineering delegation: gates 1–4

The Work engineer is empowered to inspect implementation, build instrumentation, design and execute evidence-led experiments, correct verified defects, and commit solely to `experiment/http-resident-prefix-reuse-20261023`, without automatic production promotion. Do not rigidly execute a preset checklist if evidence points elsewhere.

### Gate 1 — Long-context / many-slab N128 accumulation (highest priority)

Measure numerical state, hidden and logits error growth and greedy identity after many real N128 slabs at representative 2K/4K/8K lengths, escalating toward the **qualified** 32K configuration only when resources and measured stability permit. Include KV-capacity/page boundaries, nonmultiples of 128, final scalar token, EOS, and continuation. Compare **identical effective tokens and logical positions** against scalar using existing thresholds; use bounded checkpoints, reproducible hashes and sampling at actual observable endpoints. Do not infer intermediate within-slab state. Stop and localize at first threshold breach, nonfinite, KV mismatch, or greedy divergence. Keep error curves and max-error provenance; do not modify tolerances to force PASS.

### Gate 2 — Named-profile HTTP restart integration

Exercise actual profile creation, selective Zstd save, clean server shutdown, fresh server startup, profile selection and HTTP continuation with matching token signature/mode; compare active state fingerprints and subsequent outputs to uninterrupted control. Reject wrong prefix/model/config/version/mode without mutating valid state. Validate atomic save semantics and compatibility with existing profile inventory; never overwrite user profiles or production state.

### Gate 3 — Failure/rollback robustness

Cover true transport half-close, cancellation at distinct phases, client timeout, malformed/aborted stream where applicable, bounded executor/GPU failure injection and disk save faults. Test session invalidation or rollback contract, no tainted state reuse, HTTP error semantics and fresh recovery. Simulated OOM/Metal failures are NOT actual hardware OOM/Metal failures; classify evidence honestly. Do not induce unbounded real OOM or damage other services. Never send destructive tests to port 11241.

### Gate 4 — Other supported modes

Inventory deployed modes before testing: CPU-linear, bypass, legacy GPU KV and relevant quantization/Metal execution switches. Verify which are actually supported, distinct and user-facing; prioritize reachable configurations. Where matched-state comparisons are mathematically applicable, qualify within mode against exact-token uninterrupted controls. Check selective warm-state execution identity across incompatible mode switches. Record unsupported modes as NOT APPLICABLE, not PASS. Avoid expanding into unrelated optimization research.

## Operational boundaries and deliverables

- Experimental repo branch above; isolated checkout/build/port **11243** only. Protect production `flash-moe-production` and **11241**, weights, existing user profiles and cache files.
- Keep PR #2 draft. Do not merge, force-push, rewrite Qwen template, weaken thresholds, substitute text-only matching for state checks, introduce blanket binary-hash invalidation, or claim performance from diagnostic-instrumented timings.
- Use source/binary/model/config IDs, token signatures, run timestamps and per-case outcomes. Raw token histories, float dumps, log payloads and checkpoints must remain PRIVATE in Drive; only sanitized summaries go to GitHub.
- Stop when resources unavailable and label NOT RUN. Distinguish NOT ESTABLISHED, FAIL and PASS.
- For each gate: update its report and a cumulative qualification matrix, commit source/tests/docs; include the earliest divergence when failed, reproducible Mac commands, remaining risks and recommendation. Preserve prior evidence and report what was *actually run*.
- Final handback to Lead Architect for production decision, with PR still draft.

### Starting references

- Baseline experimental head: `b3cc330124f6e574be940fbf67f049a1a61bfd65` (verify live head before modifying).
- Draft PR: https://github.com/KingdomDesignsConsulting/Flash-iOS/pull/2
- Bounded N128 report: `docs/n128-resident-state-qualification-2026-10-27.md`
- Short scalar report: `docs/resident-state-equivalence-2026-10-27.md`
